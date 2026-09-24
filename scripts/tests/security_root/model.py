"""WP2A closed target source and fixed Terraform wiring. No HCL interpretation.

Only the reviewed templates below are target mechanisms. The legacy snapshot is
an explicit transitional exclusion, never an accepted target authority universe.
"""
import hashlib
import json
from pathlib import Path
import re

from contracts import load_json
from evaluator import Unsupported
import bundles

BASELINE = "c8e880b552b5782e9bca94891b75a71b45ddc113"
AUTHORITY = "terraform/infra/security/authority.json"
LEGACY = "ci/authority/target/legacy-sources.json"
LEGACY_DIGEST = "dfdbe2987310cbc8982c821f80d82bcf959ab517d9097e7420c8aaf5324f5019"
CATEGORIES = {"SECURITY_ROOT_OWNED", "ORDINARY_LIFECYCLE_OWNED",
              "HIGH_RISK_LIFECYCLE_OWNED", "DELIVERY_CONTROLLER_OWNED",
              "RECOVERY_CONTROLLER_OWNED", "EXTERNAL_GOVERNANCE", "UNVERIFIED"}
PROTECTED = {"oidc", "request_identities", "workload_iam", "recovery_iam",
             "controller_iam", "permissions_boundaries", "kms_authority",
             "secret_metadata_and_policy", "artifact_and_evidence_protection",
             "shared_ecr_security", "controller_code_and_configuration",
             "security_state_and_lock"}
REQUESTS = {"plan-dev", "plan-prod", "infra-dev", "infra-prod",
            "infra-high-risk-dev", "infra-high-risk-prod", "release",
            "deploy-dev", "promote-prod", "emergency-dev", "emergency-prod"}
INTERFACES = {"workload_role_arns", "recovery_role_arns", "kms_key_arns",
              "secret_metadata_arns", "artifact_and_evidence_ids",
              "shared_ecr_ids", "qualified_controller_endpoints"}


def require(condition, reason):
    if not condition:
        raise Unsupported("WP2A_SOURCE_ADMISSION_FAILURE: " + reason)


def sha(raw):
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + " closed fields")


def load_authority(root):
    doc = load_json((Path(root) / AUTHORITY).read_text())
    keys(doc, {"format_version", "classification", "stage", "security_admin",
               "backend", "ownership", "request_identities", "policies",
               "governance", "interfaces", "control_bundles"}, "authority")
    require(doc["format_version"] == 1 and doc["classification"] == "TARGET_REQUIREMENT"
            and doc["stage"] == "E1_WP2A_PROTECTED_SECURITY_ROOT_FOUNDATION", "stage")
    admin = doc["security_admin"]
    keys(admin, {"owner", "authentication", "created_by_this_root", "verification"}, "admin")
    require(admin == {"owner": "SECURITY_ROOT_OWNED", "authentication": "SEPARATELY_HELD_HUMAN_AUTHORITY",
                      "created_by_this_root": False, "verification": "UNVERIFIED"}, "external admin boundary")
    backend = doc["backend"]
    keys(backend, {"owner", "bootstrap", "bucket_input", "region_input", "key",
                   "encrypt", "use_lockfile", "ordinary_access", "prerequisites"}, "backend")
    require(backend["owner"] == "SECURITY_ROOT_OWNED" and backend["bootstrap"] == "EXTERNAL_ADMIN_PRECONDITION"
            and backend["ordinary_access"] == "NONE" and backend["encrypt"] is True
            and backend["use_lockfile"] is True and backend["key"] == "e1/security/terraform.tfstate"
            and backend["bucket_input"] == "E1_SECURITY_STATE_BUCKET"
            and backend["region_input"] == "E1_SECURITY_STATE_REGION", "backend ownership/selection")
    require(backend["prerequisites"] == ["DEDICATED_ADMIN_ONLY_BUCKET", "VERSIONING", "PUBLIC_ACCESS_BLOCK",
            "TLS_ONLY", "ADMIN_ONLY_STATE_AND_LOCK_ACCESS", "NO_ORDINARY_REMOTE_STATE_READ"], "backend prerequisites")
    own = doc["ownership"]
    keys(own, {"categories", "protected_classes", "operational_classes"}, "ownership")
    require(isinstance(own["categories"], list) and len(own["categories"]) == len(CATEGORIES)
            and set(own["categories"]) == CATEGORIES, "owner categories")
    keys(own["protected_classes"], PROTECTED, "protected classes")
    for name, item in own["protected_classes"].items():
        keys(item, {"owner", "implementation"}, name)
        require(item["owner"] == "SECURITY_ROOT_OWNED", "ordinary ownership of " + name)
        implementation = ("WP2A_DECLARED_INERT" if name == "request_identities" else
                          "WP2B_BUNDLE_FOUNDATION_ONLY" if name in {"controller_code_and_configuration", "artifact_and_evidence_protection"}
                          else "DEFERRED")
        require(item["implementation"] == implementation, name + " implementation")
    expected_owners = {"network_and_platform_skeletons": "ORDINARY_LIFECYCLE_OWNED",
                       "data_and_apps_skeletons": "HIGH_RISK_LIFECYCLE_OWNED",
                       "normal_revision_count_and_forwarding": "DELIVERY_CONTROLLER_OWNED",
                       "existing_color_restore_and_bounded_repair": "RECOVERY_CONTROLLER_OWNED",
                       "github_protections": "EXTERNAL_GOVERNANCE", "live_account_conformance": "UNVERIFIED"}
    require(own["operational_classes"] == expected_owners, "operational ownership contract")
    keys(doc["request_identities"], REQUESTS, "request identities")
    names, contexts = set(), set()
    for ident, role in doc["request_identities"].items():
        keys(role, {"name", "owner", "stage", "environment", "oidc_expectation"}, ident)
        require(role["name"] == "e1-request-" + ident and role["name"] not in names, "unique protected name")
        names.add(role["name"])
        require(role["owner"] == "SECURITY_ROOT_OWNED" and role["stage"] == "INERT", "inert owner")
        require(role["environment"] == ("neutral" if ident == "release" else ident.rsplit("-", 1)[1]), "environment")
        oidc = role["oidc_expectation"]
        keys(oidc, {"context", "job_workflow_ref", "commit", "verification"}, "OIDC expectation")
        context = "e1-" + {"deploy-dev": "dev-deploy", "promote-prod": "prod-promote",
                           "emergency-dev": "dev-emergency", "emergency-prod": "prod-emergency"}.get(ident, ident)
        require(oidc["context"] == context and context not in contexts, "exact responsibility context")
        contexts.add(context)
        require(oidc["job_workflow_ref"] == "Kendall04/terragrunt_demo/.github/workflows/" + context + ".yml"
                and oidc["commit"] is None and oidc["verification"] == "UNVERIFIED", "unbound future pinned job")
    governance = doc["governance"]
    require(governance == {"owner": "EXTERNAL_GOVERNANCE", "verification": "UNVERIFIED",
                          "include_claim_keys": ["repo", "context", "job_workflow_ref"],
                          "oidc_cutover": "NOT_IMPLEMENTED"}, "external governance")
    keys(doc["interfaces"], INTERFACES, "protected interfaces")
    for item in doc["interfaces"].values():
        require(item == {"owner": "SECURITY_ROOT_OWNED", "status": "UNAVAILABLE",
                         "transport": "ADMIN_PUBLISHED_ARN_ID_RECORD", "secret_values": False,
                         "security_state_access": False}, "future sanitized interface")
    keys(doc["policies"], {"inert_trust", "inert_permissions"}, "policies")
    for kind, policy in doc["policies"].items():
        keys(policy, {"Version", "Statement"}, "policy")
        require(policy["Version"] == "2012-10-17" and isinstance(policy["Statement"], list)
                and len(policy["Statement"]) == 1, "one inert statement")
        statement = policy["Statement"][0]
        keys(statement, {"Effect", "Action", "Principal" if kind == "inert_trust" else "Resource"}, "statement")
        require(statement["Effect"] == "Deny", "no operational Allow in WP2A")
        if kind == "inert_trust":
            require(statement["Action"] == "sts:AssumeRole" and
                    statement["Principal"] == {"AWS": "${security_admin_principal_arn}"}, "disabled trust")
        else:
            require(statement["Action"] == "*" and statement["Resource"] == "*", "deny-only operational ceiling")
    # templatefile may interpolate exactly this one admin identity, nowhere else.
    encoded = json.dumps(doc)
    require(encoded.count("${") == 1 and "%{" not in encoded and "$${" not in encoded, "unadmitted template mechanism")
    bundles.validate_catalog(root, doc)
    return doc


def expression(text):
    return "${" + text + "}"


def wiring(doc):
    """Single fixed generator for target plumbing; IAM truth stays in authority.json."""
    root = {
        "terraform": {"required_version": ">= 1.10.0, < 2.0.0", "backend": {"s3": {
            key: doc["backend"][key] for key in ("key", "encrypt", "use_lockfile")}},
                      "required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.50"}}},
        "variable": {
            "aws_account_id": {"type": "string", "nullable": False, "validation": {
                "condition": expression('can(regex("^[0-9]{12}$", var.aws_account_id))'), "error_message": "Supply the admin-selected account ID."}},
            "aws_region": {"type": "string", "nullable": False, "validation": {
                "condition": expression('can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]+$", var.aws_region))'), "error_message": "Supply the admin-selected AWS region."}},
            "security_admin_principal_arn": {"type": "string", "nullable": False, "validation": {
                "condition": expression('can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/[A-Za-z0-9+=,.@_/-]+$", var.security_admin_principal_arn)) && split(":", var.security_admin_principal_arn)[4] == var.aws_account_id'),
                "error_message": "Supply an existing separately held IAM admin principal in the selected account, never root/session/requester credentials."}}},
        "provider": {"aws": {"region": expression("var.aws_region"), "allowed_account_ids": [expression("var.aws_account_id")]}},
        "locals": {"authority": expression('jsondecode(templatefile("${path.module}/authority.json", { security_admin_principal_arn = var.security_admin_principal_arn }))')},
        "module": {"request_identities": {"source": "./modules/request_identities", "authority": expression("local.authority")}},
        "output": {
            "foundation": {"value": {"stage": expression("local.authority.stage"), "authority_sha256": expression('filesha256("${path.module}/authority.json")'),
                                       "target_accepted": False, "request_role_arns": expression("module.request_identities.role_arns")}},
            "protected_interface_contract": {"value": expression("local.authority.interfaces"),
                                             "description": "Reserved ARN/ID-only publication interfaces; unavailable until later slices. Do not give consumers remote-state access."}}}
    child = {
        "terraform": {"required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.50"}}},
        "variable": {"authority": {"type": "any", "description": "Only the closed security-root authority source may call this module."}},
        "resource": {
            "aws_iam_role": {"request": {"for_each": expression("var.authority.request_identities"),
                "name": expression("each.value.name"), "assume_role_policy": expression("jsonencode(var.authority.policies.inert_trust)"),
                "description": "WP2A inert request identity; no OIDC acquisition or operational grant.",
                "tags": {"E1Owner": expression("each.value.owner"), "E1Stage": expression("each.value.stage")}}},
            "aws_iam_role_policy": {"inert": {"for_each": expression("var.authority.request_identities"), "name": "wp2a-inert",
                "role": expression("aws_iam_role.request[each.key].id"), "policy": expression("jsonencode(var.authority.policies.inert_permissions)")}}},
        "output": {"role_arns": {"value": expression("{ for key, role in aws_iam_role.request : key => role.arn }")}}}
    root["module"]["control_bundle_storage"] = {
        "source": "./modules/control_bundle_storage", "catalog": expression("local.authority.control_bundles"),
        "account_id": expression("var.aws_account_id"), "region": expression("var.aws_region"),
        "admin_arn": expression("var.security_admin_principal_arn")}
    root["output"]["control_bundle_reservation"] = {"value": expression("module.control_bundle_storage.reservation"),
        "description": "TARGET reservation only; no installed bundle, consumer read grant or operational controller."}
    return {"terraform/infra/security/main.tf.json": root,
            "terraform/infra/security/modules/request_identities/main.tf.json": child,
            bundles.MODULE: bundles.wiring(doc["control_bundles"])}


def wrapper(doc):
    # No include, dependency, remote_state auto-creation, hook, run_cmd or fallback.
    return '''# Admin-only neutral root. Backend must already be separately bootstrapped.
# Bucket/region are external partial-backend inputs; see the security root README.
terraform {
  source = "../../infra/security"
}

inputs = {
  aws_account_id               = get_env("E1_SECURITY_ACCOUNT_ID")
  aws_region                   = get_env("E1_SECURITY_AWS_REGION")
  security_admin_principal_arn = get_env("E1_SECURITY_ADMIN_PRINCIPAL_ARN")
}
'''


def configuration_paths(root):
    """Closed repo IaC surface, including alternate roots and wrapper inputs.

    Cache contents aren't target mechanisms: all admitted module/source paths are
    fixed templates or exact legacy bytes, so none can redirect into a cache.
    """
    found = set()
    for path in Path(root).rglob("*"):
        rel = path.relative_to(root)
        if set(rel.parts) & {".git", ".terraform", ".terragrunt-cache", "node_modules", "__pycache__"}:
            continue
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise Unsupported("WP2A_SOURCE_ADMISSION_FAILURE: linked source " + rel.as_posix())
        if path.is_file() and (path.suffix in {".tf", ".hcl", ".tfvars"} or path.name.endswith((".tf.json", ".tfvars.json"))):
            found.add(rel.as_posix())
    return found


def validate_repository(root):
    root = Path(root)
    doc = load_authority(root)
    legacy_raw = (root / LEGACY).read_bytes()
    require(sha(legacy_raw) == LEGACY_DIGEST, "legacy exclusion snapshot changed; cannot admit new target authority as legacy")
    legacy = load_json(legacy_raw.decode())
    require(legacy["baseline"] == BASELINE and legacy["classification"] == "TRANSITIONAL_LEGACY_NOT_TARGET_ACCEPTED", "legacy classification")
    expected = wiring(doc)
    wrapper_path = "terraform/live/security/terragrunt.hcl"
    require(configuration_paths(root) == set(legacy["sources"]) | set(expected) | {wrapper_path}, "unadmitted/missing IaC surface")
    for name, digest in legacy["sources"].items():
        require(sha((root / name).read_bytes()) == digest, "competing/changed legacy source " + name)
    for name, configuration in expected.items():
        require(load_json((root / name).read_text()) == configuration, "target wiring drift " + name)
    require((root / wrapper_path).read_text() == wrapper(doc), "security wrapper drift")
    # Non-IaC payloads under the protected roots are closed too.
    permitted = set(expected) | {AUTHORITY, "terraform/infra/security/README.md", wrapper_path, bundles.SOURCE}
    for directory in (root / "terraform/infra/security", root / "terraform/live/security"):
        for path in directory.rglob("*"):
            if path.is_file():
                require(path.relative_to(root).as_posix() in permitted, "unadmitted protected-root file")
    return doc


def rendered_policies(doc, admin="arn:aws:iam::111122223333:role/SeparateHumanAdmin"):
    """One literal substitution, equivalent to the admitted templatefile operand."""
    require(bool(re.fullmatch(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+", admin)), "synthetic admin identity")
    return load_json(json.dumps(doc["policies"]).replace("${security_admin_principal_arn}", admin))
