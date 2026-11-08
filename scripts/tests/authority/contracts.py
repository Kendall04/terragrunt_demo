"""Closed JSON contract validation; only the small declared schema dialect is supported."""
import json
import re


class ContractError(ValueError):
    pass


def load_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ContractError("non-JSON numeric constant: " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)


def validate_schema(schema):
    admitted = {"type", "properties", "required", "additionalProperties", "items",
                "enum", "const", "pattern", "minLength", "maxLength", "minimum", "maximum",
                "minItems", "maxItems", "description", "$schema", "title"}
    if not isinstance(schema, dict) or set(schema) - admitted:
        raise ContractError("UNSUPPORTED schema keyword")
    if schema.get("type") not in ("object", "array", "string", "integer", "boolean"):
        raise ContractError("unsupported/missing schema type")
    if schema["type"] == "object":
        if schema.get("additionalProperties") is not False:
            raise ContractError("object must be closed")
        if not set(schema.get("required", [])) <= set(schema.get("properties", {})):
            raise ContractError("required fields missing from properties")
        for child in schema.get("properties", {}).values():
            validate_schema(child)
    if schema["type"] == "array":
        validate_schema(schema["items"])


def validate(value, schema, path="$"):
    validate_schema(schema)
    typ = schema["type"]
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if type(value) is not types[typ]:
        raise ContractError(path + ": invalid type or null")
    if "const" in schema and value != schema["const"]:
        raise ContractError(path + ": constant mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(path + ": enum mismatch")
    if typ == "object":
        props = schema.get("properties", {})
        if set(value) - set(props) or set(schema.get("required", [])) - set(value):
            raise ContractError(path + ": unknown/missing fields")
        for key, item in value.items():
            validate(item, props[key], path + "." + key)
    elif typ == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ContractError(path + ": array bounds")
        for i, item in enumerate(value):
            validate(item, schema["items"], path + "[" + str(i) + "]")
    elif typ == "string":
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise ContractError(path + ": string bounds")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise ContractError(path + ": pattern mismatch")
    elif typ == "integer":
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise ContractError(path + ": integer bounds")


def oidc_subject(repo, environment, workflow, sha, mode="name", owner_id=None, repo_id=None):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ContractError("workflow must use a pinned SHA")
    if mode == "immutable_ids":
        if not owner_id or not repo_id or not str(owner_id).isdigit() or not str(repo_id).isdigit():
            raise ContractError("immutable mode requires numeric IDs")
        owner, name = repo.split("/")
        repo = f"{owner}@{owner_id}/{name}@{repo_id}"
    elif mode != "name":
        raise ContractError("unknown subject-format mode")
    return f"repo:{repo}:environment:{environment.replace(':', '%3A')}:job_workflow_ref:{workflow}@{sha}"


def classify_runtime(contract, path):
    return contract["fields"].get(path, {"disposition": "REJECT_UNKNOWN", "category": "unrecognized"})


def check_runtime_inventory(contract, snapshot):
    if contract["classification"] != "TARGET_REQUIREMENT" or contract["unknown_field"] != "REJECT_UNKNOWN":
        raise ContractError("runtime contract cannot claim current enforcement")
    if set(contract["fields"]) != set(snapshot["fields"]):
        raise ContractError("runtime field coverage mismatch")
    dispositions = {"CONSTANT", "PROTECTED_BINDING", "QUALIFIED_DIGEST", "BOUNDED_INPUT", "REJECT", "RETURN_ONLY"}
    for path, entry in contract["fields"].items():
        if entry["disposition"] not in dispositions or not entry.get("category") or not entry.get("rule"):
            raise ContractError("missing runtime classification: " + path)
    if contract.get("enforced_on_deployment") is not False:
        raise ContractError("WP1 does not enforce real deployments")
