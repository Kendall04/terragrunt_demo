"""Restricted same-account IAM evidence engine, not an AWS authorization emulator.

No I/O, SDK, credentials or network. Unsupported syntax is observable UNKNOWN.
Policy decisions are distinct from complete API authorization (see authorize).
"""
from dataclasses import dataclass
from enum import Enum
import re


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Result:
    decision: Decision
    reasons: tuple[str, ...]


class Unsupported(ValueError):
    pass


def many(value):
    return value if isinstance(value, list) else [value]


def matches(pattern, value, insensitive=False):
    """IAM * and ? only; unlike fnmatch, [] is NOT a character class."""
    if not isinstance(pattern, str) or not isinstance(value, str):
        raise Unsupported("non-string matching operand")
    expression = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(expression, value, re.S | (re.I if insensitive else 0)) is not None


def normalized_context(context):
    if not isinstance(context, dict):
        raise Unsupported("invalid context mapping")
    result = {}
    for key, value in context.items():
        if not isinstance(key, str) or key.lower() in result:
            raise Unsupported("invalid/ambiguous case-insensitive context key")
        result[key.lower()] = value
    return result


def arn_matches(pattern, value):
    # The resource component may itself contain colons; the first five may not.
    parts, actual = pattern.split(":", 5), value.split(":", 5)
    if len(parts) != 6 or len(actual) != 6 or parts[0] != "arn" or actual[0] != "arn":
        raise Unsupported("invalid ARN condition operand")
    return all(matches(p, v) for p, v in zip(parts, actual))


def principal_form(category, value, kind):
    """Admission precedes matching, including nonmatching/conditioned principals."""
    if not isinstance(value, str) or not value:
        return "INVALID"
    if "*" in value or "?" in value:
        return "UNSUPPORTED"
    if category == "AWS":
        if re.fullmatch(r"arn:aws:iam::[0-9]{12}:role/[^\s]+", value):
            return "SUPPORTED_AND_MODELED"
        if re.fullmatch(r"arn:aws:sts::[0-9]{12}:assumed-role/[^/\s]+/[^/\s]+", value):
            return "SUPPORTED_AND_MODELED" if kind == "resource" else "UNSUPPORTED"
        if re.fullmatch(r"[0-9]{12}|arn:[^:]+:iam::[0-9]{12}:(root|user/.+)", value):
            return "UNSUPPORTED"
    elif category == "Service" and re.fullmatch(r"[a-z0-9.-]+\.amazonaws\.com", value):
        return "SUPPORTED_AND_MODELED" if kind == "trust" else "UNSUPPORTED"
    elif category == "Federated" and re.fullmatch(r"arn:aws:iam::[0-9]{12}:oidc-provider/[^\s]+", value):
        return "SUPPORTED_AND_MODELED" if kind == "trust" else "UNSUPPORTED"
    return "UNSUPPORTED" if value.startswith("arn:") else "INVALID"


def condition(conditions, context):
    context = normalized_context(context)
    if not isinstance(conditions, dict):
        raise Unsupported("invalid condition mapping")
    answers = []
    for operator, tests in conditions.items():
        quantifier = None
        if ":" in operator:
            quantifier, operator = operator.split(":", 1)
            if quantifier not in ("ForAllValues", "ForAnyValue"):
                raise Unsupported("unknown condition set operator")
        if_exists = operator.endswith("IfExists")
        if if_exists:
            operator = operator[:-8]
        if quantifier and if_exists:
            raise Unsupported("combined set operator/IfExists not modeled")
        supported = {"StringEquals", "StringLike", "ArnEquals", "ArnLike", "Bool", "Null"}
        if operator not in supported or (operator == "Null" and (if_exists or quantifier)):
            raise Unsupported("condition operator " + operator)
        if not isinstance(tests, dict):
            raise Unsupported("condition must be a mapping")
        for key, expected in tests.items():
            key = key.lower()
            values = many(expected)
            if not values or any(not isinstance(x, str) for x in values):
                raise Unsupported("condition values must be nonempty string lists")
            if operator == "Bool" and any(x not in ("true", "false") for x in values):
                raise Unsupported("invalid Bool literal")
            present = key in context and context[key] is not None
            actual = many(context[key]) if present else []
            if actual and all(x == "" for x in actual):
                actual = []
            elif "" in actual:
                raise Unsupported("mixed null/non-null dataset")
            if any(not isinstance(x, str) for x in actual):
                raise Unsupported("request context requires typed string values")
            if operator == "Null":
                if any(x not in ("true", "false") for x in values):
                    raise Unsupported("invalid Null literal")
                answers.append(str(not present or not actual).lower() in values)
                continue
            if not present or not actual:
                answers.append(if_exists or quantifier == "ForAllValues")
                continue
            if len(actual) > 1 and not quantifier:
                raise Unsupported("multivalued key without set operator")
            if operator == "Bool" and any(x not in ("true", "false") for x in values + actual):
                raise Unsupported("invalid Bool literal")
            compare = arn_matches if operator.startswith("Arn") else (matches if operator.endswith("Like") else lambda a, b: a == b)
            checks = [any(compare(wanted, got) for wanted in values) for got in actual]
            answers.append(all(checks) if quantifier == "ForAllValues" else any(checks))
    return all(answers)


def _validate_statement(statement, kind):
    allowed = {"Sid", "Effect", "Action", "Resource", "Condition", "_source"}
    if kind in ("resource", "trust"):
        allowed.add("Principal")
    extra = set(statement) - allowed
    if extra:
        raise Unsupported("unsupported statement keys: " + ",".join(sorted(extra)))
    if statement.get("Effect") not in ("Allow", "Deny") or "Action" not in statement:
        raise Unsupported("missing/invalid effect or action")
    if "${" in str(statement):
        raise Unsupported("policy variables")
    for field in ("Action", "Resource"):
        if field not in statement and (field != "Resource" or kind != "trust"):
            raise Unsupported("missing " + field)
        if field in statement and (not many(statement[field]) or
                                  any(not isinstance(x, str) for x in many(statement[field]))):
            raise Unsupported("invalid " + field)


def _principal(statement, request, kind):
    if kind == "identity":
        return "identity"
    principal = statement.get("Principal")
    if not isinstance(principal, dict) or len(principal) != 1:
        raise Unsupported("wildcard/unknown principal shape")
    category, identities = next(iter(principal.items()))
    if category not in ("AWS", "Federated", "Service"):
        raise Unsupported("principal category")
    identities = many(identities)
    if not identities:
        raise Unsupported("INVALID empty principal")
    for identity in identities:
        admission = principal_form(category, identity, kind)
        if admission != "SUPPORTED_AND_MODELED":
            raise Unsupported(admission + " principal: " + str(identity))
    if kind == "resource" and category != "AWS":
        raise Unsupported("service-specific resource delegation")
    if request.get("principal") in identities:
        return "session" if ":assumed-role/" in request["principal"] else "role"
    if category == "AWS" and request.get("role_arn") in identities:
        return "role"
    return None


def _statements(policies, request, kind):
    allows, denies, unknown = [], [], []
    for policy in policies:
        if set(policy) - {"Version", "Statement", "Id"} or not isinstance(policy.get("Statement"), (list, dict)):
            unknown.append("unsupported/missing policy document")
            continue
        for statement in many(policy["Statement"]):
            try:
                if not isinstance(statement, dict):
                    raise Unsupported("statement is not an object")
                _validate_statement(statement, kind)
                # Validate conditions even on nonmatching statements: unsupported is never hidden.
                condition_match = condition(statement.get("Condition", {}), request.get("context", {}))
                grant_type = _principal(statement, request, kind)
                action_match = any(matches(x, request["action"], True) for x in many(statement["Action"]))
                resource_match = kind == "trust" or any(
                    matches(x, request["resource"]) for x in many(statement["Resource"]))
                if condition_match and grant_type and action_match and resource_match:
                    trace = statement.get("_source", statement.get("Sid", "unnamed statement"))
                    (allows if statement["Effect"] == "Allow" else denies).append((grant_type, trace))
            except (Unsupported, TypeError, KeyError) as exc:
                unknown.append(str(exc))
    return allows, denies, unknown


def evaluate(request, identities=(), boundary=None, resources=(), trust=None):
    """Evaluate policy permission. None boundary differs from an empty boundary.

    Exact same-account role/session grants supported. Wildcard principals, users,
    account-root delegation and KMS resource authorization are deliberately UNKNOWN.
    """
    if not isinstance(request.get("resource"), str) or not isinstance(request.get("action"), str):
        return Result(Decision.UNKNOWN, ("invalid or multi-resource request",))
    if resources and request["action"].lower().startswith("kms:"):
        return Result(Decision.UNKNOWN, ("KMS key policy/grant semantics unsupported",))
    if resources:
        caller = request.get("role_arn", request.get("principal", ""))
        parts = caller.split(":")
        if len(parts) < 6 or request.get("resource_account") != parts[4]:
            return Result(Decision.UNKNOWN, ("same-account resource-policy context not established",))
    ia, ideny, iu = _statements(identities, request, "identity")
    ba, bdeny, bu = _statements(boundary or [], request, "identity")
    ra, rdeny, ru = _statements(resources, request, "resource")
    if trust is not None:
        ta, td, tu = _statements(trust, request, "trust")
        if td:
            return Result(Decision.DENY, tuple(x[1] for x in td))
        if tu:
            return Result(Decision.UNKNOWN, tuple(tu))
        return Result(Decision.ALLOW if ta else Decision.DENY,
                      tuple(x[1] for x in ta) or ("no matching trust grant",))
    denies = ideny + bdeny + rdeny
    if denies:
        return Result(Decision.DENY, tuple(x[1] for x in denies))
    unknown = iu + bu + ru
    if unknown:
        return Result(Decision.UNKNOWN, tuple(unknown))
    direct_session = any(x[0] == "session" for x in ra)
    allowed = direct_session or ((ia or ra) and (boundary is None or ba))
    return Result(Decision.ALLOW if allowed else Decision.DENY,
                  tuple(x[1] for x in ia + ra) if allowed else ("implicit deny/boundary intersection",))


def authorize(request, capabilities, **policies):
    """Restricted action applicability admission. Unknown service behavior fails visibly.

    Dependent permissions must be explicit subrequests; never infer PassRole from
    a registration allow. This is still repository-model evidence, not live proof.
    """
    cap = capabilities.get(request.get("action", "").lower())
    if not cap:
        return Result(Decision.UNKNOWN, ("unmodeled action/delegation",))
    if not isinstance(request.get("resource"), str):
        return Result(Decision.UNKNOWN, ("multi-resource API unsupported",))
    if not any(matches(x, request["resource"]) for x in cap["resources"]):
        return Result(Decision.UNKNOWN, ("resource/action applicability",))
    if {k.lower() for k in request.get("context", {})} - {k.lower() for k in cap.get("context", [])}:
        return Result(Decision.UNKNOWN, ("condition-key applicability",))
    for kind in ("identities", "resources", "boundary"):
        for doc in policies.get(kind) or ():
            for st in many(doc.get("Statement", [])):
                if any(matches(a, request["action"], True) for a in many(st.get("Action", []))):
                    keys = {k for tests in st.get("Condition", {}).values() for k in tests}
                    if {k.lower() for k in keys} - {k.lower() for k in cap.get("context", [])}:
                        return Result(Decision.UNKNOWN, ("policy condition-key applicability",))
    dependencies = request.get("dependencies", [])
    if sorted(x["action"].lower() for x in dependencies) != sorted(cap.get("dependencies", [])):
        return Result(Decision.UNKNOWN, ("dependent action coverage",))
    own = evaluate(request, **policies)
    checks = [own] + [authorize(x, capabilities, **policies) for x in dependencies]
    if any(x.decision == Decision.DENY for x in checks):
        return Result(Decision.DENY, tuple(y for x in checks for y in x.reasons))
    if any(x.decision == Decision.UNKNOWN for x in checks):
        return Result(Decision.UNKNOWN, tuple(y for x in checks for y in x.reasons))
    return own
