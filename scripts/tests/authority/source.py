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


RESOURCE_ATTRIBUTES = {
    "aws_iam_role": {"name", "assume_role_policy", "count", "tags", "description"},
    "aws_iam_policy": {"name", "description", "policy", "count", "tags"},
    "aws_iam_role_policy": {"name", "role", "policy", "count"},
    "aws_iam_role_policy_attachment": {"role", "policy_arn", "count"},
}


def admit_resource(typ, body):
    if typ not in RESOURCE_ATTRIBUTES:
        raise Unsupported("SOURCE_ADMISSION_UNKNOWN resource type: " + str(typ))
    children, rest = blocks(body)
    if children:
        raise Unsupported("SOURCE_ADMISSION_UNKNOWN nested/dynamic resource block")
    attrs = attributes(rest)
    if set(attrs) - RESOURCE_ATTRIBUTES[typ]:
        raise Unsupported("SOURCE_ADMISSION_UNKNOWN attributes: " + str(sorted(set(attrs) - RESOURCE_ATTRIBUTES[typ])))
    return attrs


class Adapter:
    def __init__(self, root, env):
        self.root, self.env = Path(root), env
        if list((self.root / IAM).glob("*.tf.json")):
            raise Unsupported("SOURCE_ADMISSION_UNKNOWN Terraform JSON module")
        metadata = json.loads((self.root / "ci/authority/synthetic-context.json").read_text())
        self.metadata = metadata
        if env not in ("dev", "prod") or metadata["bindings"] != metadata["fixed_values"]:
            raise Unsupported("SOURCE_BINDING_FAILURE synthetic value/context changed")
        self.values = {k: v.replace("{env}", env) for k, v in metadata["bindings"].items()}
        self.locals = {}
        local_blocks, _ = blocks((self.root / IAM / "locals.tf").read_text())
        for kind, _, _, body in local_blocks:
            if kind == "locals":
                self.locals.update(attributes(body))
        declarations = {t: clean(b).strip() for k, t, n, b in
                        blocks((self.root / IAM / "variables.tf").read_text())[0] if k == "variable"}
        if set(metadata["source_bindings"]) != set(self.values):
            raise Unsupported("SOURCE_BINDING_FAILURE missing binding")
        for key, binding in metadata["source_bindings"].items():
            expected_source = IAM + ("/locals.tf" if key.startswith("local.") else "/variables.tf")
            if (binding.get("fact_class") != "MODULE_INSTANCE_BOUND_FACT" or
                    binding.get("module_instance") != "terraform/live/{env}/shared/terragrunt.hcl/module.iam_github" or
                    binding.get("source") != expected_source or binding.get("declaration") != key):
                raise Unsupported("SOURCE_BINDING_FAILURE synthetic instance scope " + key)
            actual = self.locals.get(key[6:]) if key.startswith("local.") else declarations.get(key[4:])
            if actual != binding["expression"]:
                raise Unsupported("SOURCE_BINDING_FAILURE " + key)
        self.binding_status = "BINDING_VALIDATED"
        self.active = set()
        self.expression_instance = None
        self.instance_identity = f"terraform/live/{env}/shared/terragrunt.hcl/module.iam_github"
        self.instance_values = {self.instance_identity: self.values}
        # Resolve effective wrapper inputs before any policy interpolation. A
        # later binding check cannot repair documents built from stale defaults.
        from bindings import Bindings
        self.module_binding = Bindings(self).github()
        self.docs, self.roles, self.resources = {}, {}, []
        self.admitted = set()
        seen = set()
        providers = []
        for path in sorted((self.root / IAM).glob("*.tf")):
            if path.name == "override.tf" or path.name.endswith("_override.tf"):
                raise Unsupported("SOURCE_ADMISSION_UNKNOWN Terraform override")
            children, remainder = blocks(path.read_text())
            if remainder.strip():
                raise Unsupported("SOURCE_ADMISSION_UNKNOWN top-level expression")
            for kind, typ, name, body in children:
                identity = (kind, typ, name)
                if kind in ("resource", "data"):
                    if identity in seen:
                        raise Unsupported("SOURCE_ADMISSION_UNKNOWN duplicate declaration")
                    seen.add(identity)
                if kind == "locals" and path.name != "locals.tf":
                    raise Unsupported("SOURCE_ADMISSION_UNKNOWN additional locals")
                if typ in ("tls_certificate", "aws_iam_openid_connect_provider"):
                    candidate = {"kind": kind, "type": typ, "name": name, "body": clean(body).strip()}
                    providers.append(candidate)
                    if candidate not in metadata["provider_blocks"]:
                        raise Unsupported("SOURCE_BINDING_FAILURE provider declaration")
                    continue
                if kind == "data" and typ == "aws_iam_policy_document":
                    self.docs[name] = (body, path.relative_to(self.root).as_posix())
                elif kind == "resource":
                    self.resources.append((typ, name, admit_resource(typ, body), path.relative_to(self.root).as_posix()))
                elif kind == "data" and typ in ("aws_region", "aws_caller_identity") and name == "current" and not body.strip():
                    continue
                elif kind not in ("locals", "variable", "output", "terraform"):
                    raise Unsupported("SOURCE_ADMISSION_UNKNOWN block: " + str((kind, typ, name)))
        if not {("data", "aws_region", "current"), ("data", "aws_caller_identity", "current")} <= seen:
            raise Unsupported("SOURCE_BINDING_FAILURE missing account/region data declaration")
        if len(providers) != len(metadata["provider_blocks"]):
            raise Unsupported("SOURCE_BINDING_FAILURE missing provider declaration")
        for name in self.docs:
            self.document_reference("data.aws_iam_policy_document." + name + ".json")
        for typ, name, attrs, path in self.resources:
            self.exists(attrs)
            if typ in ("aws_iam_policy", "aws_iam_role_policy"):
                self.document_reference(attrs["policy"])
        for typ, name, attrs, path in self.resources:
            if typ != "aws_iam_role" or not self.exists(attrs):
                continue
            trust = self.document_reference(attrs["assume_role_policy"])
            self.roles[name] = {"name": self.value(attrs["name"]), "trust": trust,
                                "policies": [], "unknown": [], "source": path,
                                "boundary": None}
        physical_names = [r["name"].lower() for r in self.roles.values()]
        if len(physical_names) != len(set(physical_names)):
            raise Unsupported("SOURCE_BINDING_FAILURE colliding physical role identities")
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
                    if len(matches) != 1 or not self.exists(matches[0]):
                        raise Unsupported("unresolved policy attachment")
                    role["policies"].append(self.document_reference(matches[0]["policy"]))
                else:
                    role["unknown"].append("AWS-managed policy content not snapshotted: " + self.value(attrs["policy_arn"]))
        # Publish admission only after the whole module has passed semantic checks.
        from discovery import declaration_id
        for path in sorted((self.root / IAM).glob("*.tf")):
            for k, t, n, b in blocks(path.read_text())[0]:
                self.admitted.add(declaration_id(path.relative_to(self.root).as_posix(), k, t, n))

    def workload(self):
        from bindings import Bindings
        for path, binding in self.metadata["workload_binding_files"].items():
            if not (self.root / path).is_file() or digest(self.root / path) != binding["sha256"]:
                raise Unsupported("SOURCE_BINDING_FAILURE workload dependency: " + path)
        return Bindings(self).workload()

    def discovery(self):
        from discovery import Discovery
        return Discovery(self.root, self.admitted, [r["name"] for r in self.roles.values()], env=self.env)

    def provenance(self):
        return {"environment": self.env, "synthetic_values": self.values,
                "module_instance": self.instance_identity,
                "instance_bound_values": self.instance_values,
                "substitution_bindings": self.metadata["source_bindings"],
                "effective_inputs": self.effective_inputs,
                "module_binding": self.module_binding,
                "admitted_declarations": sorted(self.admitted)}

    def exists(self, attrs):
        if "count" not in attrs:
            return True
        match = re.fullmatch(r'var.env == "(dev|prod)" \? 1 : 0', attrs["count"])
        if not match:
            raise Unsupported("unreviewed role/policy count")
        return match[1] == self.env

    def value(self, expression):
        if self.expression_instance is not None:
            return self.expression_instance.value(expression)
        expression = expression.strip()
        bound_values = self.instance_values[self.instance_identity]
        if expression in bound_values:
            return bound_values[expression]
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


def semantic_inventory(root):
    """Actual parser admission, not a path-prefix promise."""
    from discovery import Discovery
    admitted, names = set(), []
    for env in ("dev", "prod"):
        try:
            model = Adapter(root, env)
            admitted.update(model.admitted)
            names.extend(r["name"] for r in model.roles.values())
        except Unsupported:
            pass
    return Discovery(root, admitted, names).records
