"""Source-bound current IAM adapter. NOT a Terraform/HCL interpreter.

Only the repository's aws_iam_policy_document blocks, literal lists, references,
concat/distinct and scalar interpolations are admitted. Terraform execution,
jsonencode policies, arbitrary expressions, loops and provider values are not
evaluated. Other surfaces are inventoried with explicit UNVERIFIED disposition.
"""
import hashlib
import json
from pathlib import Path
import re
from evaluator import Unsupported

IAM = "terraform/infra/shared/modules/iam_github"


def digest(path):
    # Git text checkouts may use CRLF on Windows and LF on Linux. Inventory
    # freshness tracks normalized text; report hashes still identify exact bytes.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def clean(text):
    # Preserve strings (including # and // in URLs) when removing comments.
    pattern = r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|\#[^\n]*|//[^\n]*'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else " " * len(m[0]), text)


def split_top(text, separator=","):
    result, start, stack, quoted, escaped = [], 0, [], False, False
    for i, c in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c in "[{(":
            stack.append(c)
        elif c in "]})":
            if not stack or "[{("["]})".index(c)] != stack.pop():
                raise Unsupported("unbalanced source delimiters")
        elif c == separator and not stack:
            if text[start:i].strip():
                result.append(text[start:i].strip())
            start = i + 1
    if stack or quoted:
        raise Unsupported("unterminated source expression")
    if text[start:].strip():
        result.append(text[start:].strip())
    return result


def blocks(text):
    """Read direct child blocks only, retaining unsupported remainder for rejection."""
    text = clean(text)
    found, spans = [], []
    header = re.compile(r'(?m)^\s*(\w+)(?:\s+"([^"\n]+)")?(?:\s+"([^"\n]+)")?\s*\{')
    cursor = 0
    while match := header.search(text, cursor):
        start, depth, quoted, escape = match.end(), 1, False, False
        for i in range(start, len(text)):
            c = text[i]
            if quoted:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    found.append((*match.groups(), text[start:i]))
                    spans.append((match.start(), i + 1))
                    cursor = i + 1
                    break
        else:
            raise Unsupported("unterminated block")
    remainder = text
    for start, end in reversed(spans):
        remainder = remainder[:start] + " " * (end - start) + remainder[end:]
    return found, remainder


def attributes(text):
    attrs = {}
    for entry in split_top(clean(text), "\n"):
        match = re.fullmatch(r"\s*(\w+)\s*=\s*([\s\S]+)", entry)
        if not match or match[1] in attrs:
            raise Unsupported("unsupported/duplicate attribute: " + entry[:80])
        attrs[match[1]] = match[2].strip()
    return attrs


class Adapter:
    def __init__(self, root, env):
        self.root, self.env = Path(root), env
        metadata = json.loads((self.root / "ci/authority/synthetic-context.json").read_text())
        self.values = {k: v.replace("{env}", env) for k, v in metadata["bindings"].items()}
        self.locals = {}
        local_blocks, _ = blocks((self.root / IAM / "locals.tf").read_text())
        for kind, _, _, body in local_blocks:
            if kind == "locals":
                self.locals.update(attributes(body))
        self.active = set()
        self.docs, self.roles, self.resources = {}, {}, []
        for path in sorted((self.root / IAM).glob("*.tf")):
            for kind, typ, name, body in blocks(path.read_text())[0]:
                if kind == "data" and typ == "aws_iam_policy_document":
                    self.docs[name] = (body, path.relative_to(self.root).as_posix())
                elif kind == "resource":
                    self.resources.append((typ, name, attributes(body), path.relative_to(self.root).as_posix()))
        for typ, name, attrs, path in self.resources:
            if typ != "aws_iam_role" or not self.exists(attrs):
                continue
            trust = self.document_reference(attrs["assume_role_policy"])
            self.roles[name] = {"name": self.value(attrs["name"]), "trust": trust,
                                "policies": [], "unknown": [], "source": path,
                                "boundary": None}
            if "permissions_boundary" in attrs:
                self.roles[name]["unknown"].append("boundary attachment requires reviewed adapter")
        for typ, name, attrs, path in self.resources:
            if typ not in ("aws_iam_role_policy", "aws_iam_role_policy_attachment") or not self.exists(attrs):
                continue
            match = re.fullmatch(r"aws_iam_role\.(\w+)(?:\[0\])?\.(?:name|id)", attrs.get("role", ""))
            if not match or match[1] not in self.roles:
                raise Unsupported("unresolved role attachment " + path + ":" + name)
            role = self.roles[match[1]]
            if typ == "aws_iam_role_policy":
                role["policies"].append(self.document_reference(attrs["policy"]))
            else:
                reference = re.fullmatch(r"aws_iam_policy\.(\w+)(?:\[0\])?\.arn", attrs["policy_arn"])
                if reference:
                    matches = [a for t, n, a, _ in self.resources if t == "aws_iam_policy" and n == reference[1]]
                    if len(matches) != 1:
                        raise Unsupported("unresolved policy attachment")
                    role["policies"].append(self.document_reference(matches[0]["policy"]))
                else:
                    role["unknown"].append("AWS-managed policy content not snapshotted: " + self.value(attrs["policy_arn"]))

    def exists(self, attrs):
        if "count" not in attrs:
            return True
        match = re.fullmatch(r'var.env == "(dev|prod)" \? 1 : 0', attrs["count"])
        if not match:
            raise Unsupported("unreviewed role/policy count")
        return match[1] == self.env

    def value(self, expression):
        expression = expression.strip()
        if expression in self.values:
            return self.values[expression]
        if expression.startswith('"'):
            text = json.loads(expression)
            return re.sub(r"\$\{([^}]+)\}", lambda m: str(self.value(m[1])), text)
        if expression.startswith("[") and expression.endswith("]"):
            return [self.value(x) for x in split_top(expression[1:-1])]
        for function in ("concat", "distinct"):
            if expression.startswith(function + "(") and expression.endswith(")"):
                values = [self.value(x) for x in split_top(expression[len(function) + 1:-1])]
                if not all(isinstance(x, list) for x in values):
                    raise Unsupported("non-list policy concatenation")
                flat = [item for value in values for item in value]
                return flat if function == "concat" else list(dict.fromkeys(flat))
        if expression.startswith("local.") and expression[6:] in self.locals:
            if expression in self.active:
                raise Unsupported("cyclic local reference")
            self.active.add(expression)
            try:
                return self.value(self.locals[expression[6:]])
            finally:
                self.active.remove(expression)
        raise Unsupported("unresolved policy expression: " + expression[:120])

    def document_reference(self, reference):
        match = re.fullmatch(r"data.aws_iam_policy_document\.(\w+)\.json", reference)
        if not match or match[1] not in self.docs:
            raise Unsupported("unsupported policy reference: " + reference)
        body, path = self.docs[match[1]]
        children, remainder = blocks(body)
        if remainder.strip():
            raise Unsupported("policy document attributes/merges unsupported")
        result = []
        for kind, label, _, statement_body in children:
            if kind != "statement" or label:
                raise Unsupported("unrecognized policy child")
            nested, rest = blocks(statement_body)
            fields = attributes(rest)
            mapping = {"effect": "Effect", "sid": "Sid", "actions": "Action", "resources": "Resource"}
            if set(fields) - set(mapping):
                raise Unsupported("unsupported IAM source fields: " + str(set(fields) - set(mapping)))
            st = {mapping[k]: self.value(v) for k, v in fields.items()}
            st.setdefault("Effect", "Allow")
            st["_source"] = path + "#" + match[1] + "/" + st.get("Sid", str(len(result)))
            for child, _, _, content in nested:
                a = attributes(content)
                if child == "principals" and set(a) == {"type", "identifiers"}:
                    typ = self.value(a["type"])
                    if typ in st.setdefault("Principal", {}):
                        raise Unsupported("duplicate principal block")
                    st["Principal"][typ] = self.value(a["identifiers"])
                elif child == "condition" and set(a) == {"test", "variable", "values"}:
                    op, key = self.value(a["test"]), self.value(a["variable"])
                    target = st.setdefault("Condition", {}).setdefault(op, {})
                    if key in target:
                        raise Unsupported("duplicate condition block")
                    target[key] = self.value(a["values"])
                else:
                    raise Unsupported("unsupported nested policy block")
            result.append(st)
        return {"Version": "2012-10-17", "Statement": result}
