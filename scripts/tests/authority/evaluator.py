"""Restricted same-account IAM evidence engine, not an AWS authorization emulator.

No I/O, SDK, credentials or network. Unsupported syntax is observable UNKNOWN.
Policy decisions are distinct from complete API authorization (see authorize).
"""
from dataclasses import asdict, dataclass
from enum import Enum
import re


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class PolicyKind(str, Enum):
    IDENTITY_POLICY = "IDENTITY_POLICY"
    RESOURCE_POLICY = "RESOURCE_POLICY"
    TRUST_POLICY = "TRUST_POLICY"
    PERMISSIONS_BOUNDARY = "PERMISSIONS_BOUNDARY"


KINDS = {"identity": PolicyKind.IDENTITY_POLICY, "resource": PolicyKind.RESOURCE_POLICY,
         "trust": PolicyKind.TRUST_POLICY, "boundary": PolicyKind.PERMISSIONS_BOUNDARY}


@dataclass(frozen=True)
class Result:
    decision: Decision
    reasons: tuple[str, ...]
    provenance: tuple = ()


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
    if not isinstance(pattern, str) or not isinstance(value, str):
        raise Unsupported("invalid ARN condition operand")
    parts, actual = pattern.split(":", 5), value.split(":", 5)
    for operand, components in ((pattern, parts), (value, actual)):
        if (len(components) != 6 or components[0] != "arn" or
                not components[1] or not components[2] or not components[5] or
                re.search(r"\s", operand) or "${" in operand):
            raise Unsupported("invalid ARN condition operand")
        if (not re.fullmatch(r"[a-z0-9*?-]+", components[1]) or
                not re.fullmatch(r"[a-z0-9*?-]+", components[2]) or
                not re.fullmatch(r"[a-z0-9*?-]*", components[3]) or
                (components[4] and not re.fullmatch(r"[0-9*?]+", components[4]) and not
                 (components[1:5] == ["aws", "iam", "", "aws"] and components[5].startswith("policy/")))):
            raise Unsupported("invalid ARN component")
        if components[4].isdigit() and len(components[4]) != 12:
            raise Unsupported("invalid ARN account length")
    return all(matches(p, v) for p, v in zip(parts, actual))


ROLE = re.compile(r"arn:aws:iam::([0-9]{12}):role/((?:[A-Za-z0-9+=,.@_-]+/)*)([A-Za-z0-9+=,.@_-]{1,64})")
SESSION = re.compile(r"arn:aws:sts::([0-9]{12}):assumed-role/([A-Za-z0-9+=,.@_-]{1,64})/([A-Za-z0-9+=,.@_-]{2,64})")


@dataclass(frozen=True)
class Identity:
    category: str
    principal: str
    account: str = ""
    role_name: str = ""
    role_arn: str = ""


def request_identity(request):
    """IAM role names are account-unique; STS session ARNs omit the IAM path.

    Compare an admitted policy role's account/name rather than inventing its path.
    A supplied full role ARN must agree with this relationship.
    """
    principal, alias = request.get("principal"), request.get("role_arn")
    if not isinstance(principal, str):
        raise Unsupported("INVALID_IDENTITY missing principal")
    role, session = ROLE.fullmatch(principal), SESSION.fullmatch(principal)
    if role:
        identity = Identity("role", principal, role[1], role[3], principal)
        if alias is not None and alias != principal:
            raise Unsupported("INVALID_IDENTITY contradictory role alias")
    elif session:
        identity = Identity("session", principal, session[1], session[2])
        if alias is not None:
            parent = ROLE.fullmatch(alias) if isinstance(alias, str) else None
            if not parent or (parent[1], parent[3]) != (session[1], session[2]):
                raise Unsupported("INVALID_IDENTITY contradictory session parent")
            identity = Identity("session", principal, session[1], session[2], alias)
    elif principal_form("Service", principal, "trust") == "SUPPORTED_AND_MODELED":
        identity = Identity("service", principal)
    elif principal_form("Federated", principal, "trust") == "SUPPORTED_AND_MODELED":
        identity = Identity("oidc", principal, principal.split(":")[4])
    else:
        raise Unsupported("INVALID_IDENTITY unsupported principal")
    if identity.category in ("service", "oidc") and alias is not None:
        raise Unsupported("INVALID_IDENTITY non-role principal with role alias")
    return identity


# Only these resource families have an admitted account location. S3 bucket and
# object ARNs have no account: an explicit, source-bound account is required for
# resource-policy evaluation. Identity-only checks remain policy-scope evidence.
ACCOUNT_SERVICES = {"iam", "sts", "sqs", "sns", "ecs", "ecr", "lambda", "kms",
                    "ssm", "secretsmanager", "events", "logs", "elasticloadbalancing",
                    "ec2", "dynamodb"}
PRINCIPAL_CONTEXT = {"aws:principalarn", "aws:principalaccount", "aws:principaltype"}


def normalized_request(request, identity_required=False, resource_policy=False):
    """Build one fact set; supplied context can confirm but never replace it.

    A role-session ARN omits the IAM path. Without a bound role_arn alias we know
    its account/name, but cannot manufacture a full aws:PrincipalArn. A policy
    using that unavailable fact is UNKNOWN rather than a nonmatching DENY.
    """
    if not isinstance(request, dict):
        raise Unsupported("INVALID_REQUEST request is not an object")
    supported_fields = {"action", "resource", "principal", "role_arn", "resource_account", "context", "dependencies"}
    if set(request) - supported_fields:
        raise Unsupported("INVALID_REQUEST unadmitted request fields/identity aliases")
    action, resource = request.get("action"), request.get("resource")
    if not isinstance(action, str) or not re.fullmatch(r"[A-Za-z0-9-]+:[A-Za-z0-9]+", action):
        raise Unsupported("INVALID_REQUEST invalid action")
    if not isinstance(resource, str) or not resource or re.search(r"\s", resource):
        raise Unsupported("INVALID_RESOURCE invalid or multi-resource request")
    context = normalized_context(request.get("context", {}))
    for value in context.values():
        if value is not None and (not isinstance(value, (str, list)) or
                                  any(not isinstance(x, str) for x in many(value))):
            raise Unsupported("INVALID_REQUEST context requires typed string values")
    identity = None
    derived, unavailable = {}, set()
    if identity_required or "principal" in request or "role_arn" in request:
        identity = request_identity(request)
        if identity.category in ("role", "session"):
            derived = {"aws:principalaccount": identity.account}
            if identity.category == "session":
                derived["aws:principaltype"] = "AssumedRole"
            else:
                # A role ARN is a policy principal, not proof of an STS session.
                unavailable.add("aws:principaltype")
            if identity.role_arn:
                derived["aws:principalarn"] = identity.role_arn
            else:
                unavailable.add("aws:principalarn")
        else:
            # Service and web-identity request context is deliberately smaller.
            # WP1 does not map provider principals to IAM role global facts.
            unavailable.update(PRINCIPAL_CONTEXT)
    else:
        unavailable.update(PRINCIPAL_CONTEXT)
    for key in PRINCIPAL_CONTEXT:
        if key in context:
            if key not in derived or context[key] not in (derived[key], [derived[key]]):
                raise Unsupported("INVALID_IDENTITY contradictory/unresolved " + key)
    context.update(derived)

    account, service = "", ""
    if resource.startswith("arn:"):
        arn_matches(resource, resource)
        _, partition, service, region, encoded_account, name = resource.split(":", 5)
        if partition != "aws" or "*" in resource or "?" in resource:
            raise Unsupported("INVALID_RESOURCE unsupported concrete ARN")
        if service in ACCOUNT_SERVICES:
            if not re.fullmatch(r"[0-9]{12}", encoded_account):
                raise Unsupported("INVALID_RESOURCE invalid encoded account")
            if service in ("iam", "sts"):
                if region:
                    raise Unsupported("INVALID_RESOURCE invalid global-service region")
            elif not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region):
                raise Unsupported("INVALID_RESOURCE unsupported regional ARN")
            account = encoded_account
        elif service == "s3" and not region and not encoded_account:
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*(?:/[^\s]+)?", name):
                raise Unsupported("INVALID_RESOURCE unsupported S3 resource shape")
        elif resource_policy:
            raise Unsupported("INVALID_RESOURCE account semantics unsupported for " + service)
    elif resource_policy:
        raise Unsupported("INVALID_RESOURCE resource-policy request requires concrete ARN")
    supplied = request.get("resource_account")
    if supplied is not None:
        if not isinstance(supplied, str) or not re.fullmatch(r"[0-9]{12}", supplied):
            raise Unsupported("INVALID_RESOURCE invalid resource_account")
        if account and supplied != account:
            raise Unsupported("INVALID_RESOURCE contradictory resource_account")
        if not account and service == "s3":
            account = supplied
        elif not account:
            raise Unsupported("INVALID_RESOURCE account semantics unresolved")
    resource_context = {"aws:resourceaccount": account} if account else {}
    if service == "s3" and account:
        resource_context["s3:resourceaccount"] = account
    for key in ("aws:resourceaccount", "s3:resourceaccount"):
        if key in context and (key not in resource_context or
                               context[key] not in (resource_context[key], [resource_context[key]])):
            raise Unsupported("INVALID_RESOURCE contradictory/unresolved " + key)
        if key not in resource_context:
            unavailable.add(key)
    context.update(resource_context)
    if resource_policy and (not identity or identity.category not in ("role", "session") or
                            not account or account != identity.account):
        raise Unsupported("INVALID_RESOURCE same-account resource-policy context not established")
    facts = {"identity": asdict(identity) if identity else {"category": "unbound_policy_scope"},
             "principal_context": derived, "unavailable_principal_context": sorted(unavailable & PRINCIPAL_CONTEXT),
             "unavailable_resource_context": sorted(unavailable - PRINCIPAL_CONTEXT),
             "resource_context": resource_context,
             "resource": resource, "resource_service": service, "resource_account": account,
             "action": action, "requested_service": action.split(":")[0].lower()}
    return request | {"_identity": identity, "context": context,
                      "_unavailable_context": unavailable, "_facts": facts}


def principal_form(category, value, kind):
    """Admission precedes matching, including nonmatching/conditioned principals."""
    if not isinstance(value, str) or not value:
        return "INVALID"
    if "*" in value or "?" in value:
        return "UNSUPPORTED"
    if category == "AWS":
        if ROLE.fullmatch(value):
            return "SUPPORTED_AND_MODELED"
        if SESSION.fullmatch(value):
            return "SUPPORTED_AND_MODELED" if kind == "resource" else "UNSUPPORTED"
        if re.fullmatch(r"[0-9]{12}|arn:[^:]+:iam::[0-9]{12}:(root|user/.+)", value):
            return "UNSUPPORTED"
    elif category == "Service" and re.fullmatch(r"[a-z0-9.-]+\.amazonaws\.com", value):
        return "SUPPORTED_AND_MODELED" if kind == "trust" else "UNSUPPORTED"
    elif category == "Federated" and re.fullmatch(r"arn:aws:iam::[0-9]{12}:oidc-provider/[^\s]+", value):
        return "SUPPORTED_AND_MODELED" if kind == "trust" else "UNSUPPORTED"
    return "UNSUPPORTED" if value.startswith("arn:") else "INVALID"


def admit_conditions(conditions):
    """Validate the whole policy expression before any request-dependent truth."""
    if not isinstance(conditions, dict):
        raise Unsupported("invalid condition mapping")
    admitted = []
    for operator, tests in conditions.items():
        if not isinstance(operator, str) or not operator:
            raise Unsupported("invalid condition operator")
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
        if not isinstance(tests, dict) or not tests:
            raise Unsupported("condition must be a nonempty mapping")
        seen = set()
        for key, expected in tests.items():
            if not isinstance(key, str) or not key or key.lower() in seen:
                raise Unsupported("invalid/duplicate condition key")
            key = key.lower()
            seen.add(key)
            values = many(expected)
            if not values or any(not isinstance(x, str) for x in values):
                raise Unsupported("condition values must be nonempty string lists")
            if operator in ("Bool", "Null") and any(x not in ("true", "false") for x in values):
                raise Unsupported("invalid boolean literal")
            if operator in ("Bool", "Null") and len(values) != 1:
                raise Unsupported("invalid boolean condition cardinality")
            if operator.startswith("Arn"):
                for value in values:
                    arn_matches(value, value)
            admitted.append((operator, quantifier, if_exists, key, tuple(values)))
    return tuple(admitted)


def condition(conditions, context):
    admitted = admit_conditions(conditions)
    context = normalized_context(context)
    answers = []
    for operator, quantifier, if_exists, key, values in admitted:
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
        if operator == "Bool" and any(x not in ("true", "false") for x in actual):
            raise Unsupported("invalid Bool literal")
        if operator.startswith("Arn"):
            for value in actual:
                arn_matches(value, value)
        compare = arn_matches if operator.startswith("Arn") else (matches if operator.endswith("Like") else lambda a, b: a == b)
        checks = [any(compare(wanted, got) for wanted in values) for got in actual]
        answers.append(all(checks) if quantifier == "ForAllValues" else any(checks))
    return all(answers)


def _kind(kind):
    if kind in KINDS:
        return KINDS[kind]
    try:
        return PolicyKind(kind)
    except (ValueError, TypeError):
        raise Unsupported("unsupported policy document kind") from None


def _string_values(value, field):
    if not isinstance(value, (str, list)):
        raise Unsupported("invalid " + field + " container")
    values = many(value)
    if not values or any(not isinstance(x, str) or not x for x in values):
        raise Unsupported("invalid/empty " + field + " values")
    return values


def _admit_principal(principal, kind):
    if not isinstance(principal, dict) or len(principal) != 1:
        raise Unsupported("wildcard/unknown principal shape")
    category, values = next(iter(principal.items()))
    if category not in ("AWS", "Federated", "Service"):
        raise Unsupported("principal category")
    short_kind = "trust" if kind == PolicyKind.TRUST_POLICY else "resource"
    for identity in _string_values(values, "Principal"):
        admission = principal_form(category, identity, short_kind)
        if admission != "SUPPORTED_AND_MODELED":
            raise Unsupported(admission + " principal: " + str(identity))
    return category


def _validate_statement(statement, kind):
    if not isinstance(statement, dict) or any(not isinstance(k, str) for k in statement):
        raise Unsupported("statement must be an object with string keys")
    allowed = {"Sid", "Effect", "Action", "Condition", "_source"}
    if kind != PolicyKind.TRUST_POLICY:
        allowed.add("Resource")
    if kind in (PolicyKind.RESOURCE_POLICY, PolicyKind.TRUST_POLICY):
        allowed.add("Principal")
    if set(statement) - allowed:
        raise Unsupported("unsupported statement keys for " + kind.value + ": " +
                          ",".join(sorted(set(statement) - allowed)))
    if statement.get("Effect") not in ("Allow", "Deny") or "Action" not in statement:
        raise Unsupported("missing/invalid effect or action")
    for optional in ("Sid", "_source"):
        if optional in statement and (not isinstance(statement[optional], str) or not statement[optional]):
            raise Unsupported("invalid " + optional)
    if "Sid" in statement and not re.fullmatch(r"[A-Za-z0-9]+", statement["Sid"]):
        raise Unsupported("unsupported Sid grammar")
    if "${" in str(statement):
        raise Unsupported("policy variables")
    actions = _string_values(statement["Action"], "Action")
    for action in actions:
        if action != "*" and not re.fullmatch(r"[A-Za-z0-9-]+:[A-Za-z0-9*?]+", action):
            raise Unsupported("invalid Action operand")
    if kind != PolicyKind.TRUST_POLICY:
        if "Resource" not in statement:
            raise Unsupported("missing Resource")
        for resource in _string_values(statement["Resource"], "Resource"):
            if resource != "*":
                arn_matches(resource, resource)
                if resource.split(":", 5)[1] != "aws":
                    raise Unsupported("unsupported resource ARN partition")
    if kind in (PolicyKind.RESOURCE_POLICY, PolicyKind.TRUST_POLICY):
        category = _admit_principal(statement.get("Principal"), kind)
        if kind == PolicyKind.TRUST_POLICY:
            supported = "sts:assumerolewithwebidentity" if category == "Federated" else "sts:assumerole"
            if any(action.lower() != supported for action in actions):
                raise Unsupported("unsupported principal/action trust combination")
    if "Condition" in statement:
        if not isinstance(statement["Condition"], dict) or not statement["Condition"]:
            raise Unsupported("empty/invalid explicit Condition")
        admit_conditions(statement["Condition"])


def admit_policy(policy, kind):
    """Admit the complete kind-specific document before matching any statement.

    Version omission is admitted for legacy fixture envelopes without variables;
    the only explicit supported version is 2012-10-17. NotAction/NotResource/
    NotPrincipal and all other unmodeled keys fail visibly, never as a nonmatch.
    """
    kind = _kind(kind)
    if not isinstance(policy, dict) or any(not isinstance(k, str) for k in policy):
        raise Unsupported("policy document must be an object")
    if set(policy) - {"Version", "Statement", "Id"}:
        raise Unsupported("unsupported policy envelope")
    if "Version" in policy and policy["Version"] != "2012-10-17":
        raise Unsupported("unsupported/invalid policy Version")
    if "Id" in policy and (not isinstance(policy["Id"], str) or not policy["Id"]):
        raise Unsupported("invalid policy Id")
    if "Id" in policy and kind in (PolicyKind.IDENTITY_POLICY, PolicyKind.PERMISSIONS_BOUNDARY):
        raise Unsupported("unsupported Id for identity policy/boundary")
    statements = policy.get("Statement")
    if not isinstance(statements, (dict, list)) or not statements:
        raise Unsupported("missing/empty/invalid Statement container")
    statements = many(statements)
    sids = set()
    for statement in statements:
        _validate_statement(statement, kind)
        if "Sid" in statement:
            if statement["Sid"] in sids:
                raise Unsupported("duplicate Sid")
            sids.add(statement["Sid"])
    return tuple(statements)


def admit_policies(policies, kind):
    """An empty list is a known empty set; false, null and objects are not lists."""
    if not isinstance(policies, (list, tuple)):
        raise Unsupported("invalid " + _kind(kind).value + " policy container")
    return tuple(admit_policy(policy, kind) for policy in policies)


def _principal(statement, request, kind):
    if kind in ("identity", "boundary"):
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
    caller = request["_identity"]
    categories = {"AWS": ("role", "session"), "Service": ("service",), "Federated": ("oidc",)}
    if caller.category not in categories[category]:
        return None
    if caller.principal in identities:
        return "session" if caller.category == "session" else "role"
    if category == "AWS" and caller.category == "session":
        for value in identities:
            parent = ROLE.fullmatch(value)
            if parent and (parent[1], parent[3]) == (caller.account, caller.role_name):
                if caller.role_arn and caller.role_arn != value:
                    raise Unsupported("INVALID_IDENTITY inconsistent role path")
                return "role"
    return None


def _statements(admitted_documents, request, kind):
    allows, denies = [], []
    for statements in admitted_documents:
        for statement in statements:
            conditions = statement.get("Condition", {})
            used = {key.lower() for tests in conditions.values() for key in tests}
            if used & request["_unavailable_context"]:
                raise Unsupported("INVALID_REQUEST unresolved normalized condition facts")
            # Request-dependent checks also precede statement matching. A malformed
            # context operand cannot be hidden behind a false action/condition.
            condition_match = condition(conditions, request["context"])
            grant_type = _principal(statement, request, kind)
            action_match = any(matches(x, request["action"], True) for x in many(statement["Action"]))
            resource_match = kind == "trust" or any(
                matches(x, request["resource"]) for x in many(statement["Resource"]))
            if condition_match and grant_type and action_match and resource_match:
                trace = statement.get("_source", statement.get("Sid", "unnamed statement"))
                (allows if statement["Effect"] == "Allow" else denies).append((grant_type, trace))
    return allows, denies


def evaluate(request, identities=(), boundary=None, resources=(), trust=None):
    """Evaluate policy permission. None boundary differs from an empty boundary.

    Exact same-account role/session grants supported. Wildcard principals, users,
    account-root delegation and KMS resource authorization are deliberately UNKNOWN.
    """
    admission, documents = [], {}
    for kind, container in (("identity", identities), ("boundary", boundary),
                            ("resource", resources), ("trust", trust)):
        if container is None and kind in ("boundary", "trust"):
            continue
        try:
            documents[kind] = admit_policies(container, kind)
            admission.append({"document_kind": KINDS[kind].value, "admission": "SUPPORTED_AND_MODELED",
                              "documents": len(documents[kind]),
                              "source_statements": [[st.get("_source", st.get("Sid", "unnamed statement"))
                                                     for st in doc] for doc in documents[kind]]})
        except (Unsupported, TypeError, ValueError) as exc:
            admission.append({"document_kind": KINDS[kind].value, "admission": "ADMISSION_FAILURE",
                              "reason": str(exc)})
    invalid = [a for a in admission if a["admission"] == "ADMISSION_FAILURE"]
    provenance = {"policy_admission": admission, "normalized_request": None,
                  "applicable_unknown": [], "evidence_scope": "PRIMITIVE_POLICY_PERMISSION"}
    if invalid:
        reasons = tuple("SEMANTIC_ADMISSION_UNKNOWN " + a["document_kind"] + ": " + a["reason"] for a in invalid)
        provenance["applicable_unknown"] = list(reasons)
        return Result(Decision.UNKNOWN, reasons, (provenance,))
    try:
        has_resources = len(documents["resource"]) != 0
        request = normalized_request(request, identity_required=has_resources or trust is not None,
                                     resource_policy=has_resources)
        provenance["normalized_request"] = request["_facts"]
        if has_resources and request["action"].lower().startswith("kms:"):
            raise Unsupported("KMS key policy/grant semantics unsupported")
        ia, ideny = _statements(documents["identity"], request, "identity")
        ba, bdeny = _statements(documents.get("boundary", ()), request, "boundary")
        ra, rdeny = _statements(documents["resource"], request, "resource")
        if trust is not None:
            if documents["identity"] or documents.get("boundary") or has_resources:
                raise Unsupported("combined trust and permission authorization unsupported")
            ta, td = _statements(documents["trust"], request, "trust")
            return Result(Decision.DENY if td else Decision.ALLOW if ta else Decision.DENY,
                          tuple(x[1] for x in td or ta) or ("no matching trust grant",), (provenance,))
        denies = ideny + bdeny + rdeny
        if denies:
            return Result(Decision.DENY, tuple(x[1] for x in denies), (provenance,))
        direct_session = any(x[0] == "session" for x in ra)
        allowed = direct_session or ((ia or ra) and (boundary is None or ba))
        return Result(Decision.ALLOW if allowed else Decision.DENY,
                      tuple(x[1] for x in ia + ra) if allowed else ("implicit deny/boundary intersection",),
                      (provenance,))
    except (Unsupported, TypeError, KeyError, ValueError) as exc:
        reason = "NORMALIZED_REQUEST_UNKNOWN " + str(exc)
        provenance["applicable_unknown"] = [reason]
        return Result(Decision.UNKNOWN, (reason,), (provenance,))


def _authorize(request, capabilities, **policies):
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
    if any(x.decision == Decision.UNKNOWN for x in checks):
        return Result(Decision.UNKNOWN, tuple(y for x in checks for y in x.reasons),
                      tuple(p for x in checks for p in x.provenance))
    if any(x.decision == Decision.DENY for x in checks):
        return Result(Decision.DENY, tuple(y for x in checks for y in x.reasons),
                      tuple(p for x in checks for p in x.provenance))
    return own


def authorize(request, capabilities, **policies):
    try:
        return _authorize(request, capabilities, **policies)
    except (Unsupported, TypeError, KeyError, AttributeError, ValueError) as exc:
        return Result(Decision.UNKNOWN, ("invalid API/policy admission: " + str(exc),))
