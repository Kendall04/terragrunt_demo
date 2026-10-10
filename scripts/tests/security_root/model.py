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
import compute
import ownership
import ordinary
import internal
import wp4d
import wp5

SUPPORT_FILES = {**ownership.RECOVERY_SOURCES, "terraform/infra/data/user_data.sh": "98b4d17937711d27244c161a35832d6f05135b59f5cb5609a5016fd19b10cd7b"}

# Exact executable package inputs are copied by existing disposable fixtures.
SUPPORT_FILES.update({
    "ci/schemas/e1-build-attempt.schema.json": "359750f4c2ab7fe25b56b9d314c961bee5f5f144b29fefbbfbae44f4a3193173",
    "ci/schemas/e1-qualification.schema.json": "79ba84dfa4bd8ca5ce4955bc4a97a888cc79a28a06c8eee43063319508a8d8d0",
    "ci/schemas/release-manifest.schema.json": "d2ea7d5d27e257bc68b242c1f15518384445e41fd8ce82fac122934f2a0d5ebf",
    "scripts/build_supervision/entrypoint.py": "eab168fddef33d9591f5d6da3d3ada819cf0c2a28cbe4f75c3584bcc0ef1e3e5",
    "scripts/build_supervision/supervisor.py": "d32304df12204160c20c0ad43c489121ee683756f7f694d1038d6c4811327c53",
    "scripts/qualification/finalizer.py": "229fa9a394169538f9158b4f1d3e8d5d4e15a0c21819ed90ac33a85eba4c7098"
})

# Explicit WP3C runtime support pins; no executable glob admission.
SUPPORT_FILES.update({'scripts/internal_release/e1_contract.py': '9928b0bab7808a666de767a6d2e17614c4a540249deb7f333c7ab751a4aa39e4', 'scripts/internal_release/exchange.py': '3abebea613fefa8f07a4325a1d49bd8a5332c5c9cd82ac1ac0164a9f3e697651', 'scripts/internal_release/publisher.py': 'c36be673645092b6f003a4678c755089625a82838fa9566683c831f8ecacb64d', 'scripts/internal_release/workers.py': 'e4cfc230649374aa0aafd6bffe9deb8bff1ca7e6aeeae746d9144fab4bd1bcb7', 'scripts/internal_release/adapters.py': '4357456410d36fbb1a004d08d6eb71db47149c8bea0dfa78a86ea5ecca389d34', 'scripts/internal_release/services.py': 'f5ed39fc14a8aa6814e619f16b48629fac065e39094985447e60ff7ca30fc2ca', 'scripts/internal_release/runtime.py': 'd3971fa0f3aa4d0f9e704ace400acae4bc26fda651d23e47bcb3c93a0d65d60c', 'scripts/internal_release/worker.py': '05f027ff30df883fffa2231367e03348dd4cf91a8233b8996554d9ff74cf6d2b'})

# Existing WP2 disposable fixtures must copy the new package inputs. The fixed
# package digests in authority.json still detect any changed source bytes.
SUPPORT_FILES.update({name: hashlib.sha256((wp4d.ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                      for name in set().union(*(wp4d.package_sources(key) for key in wp4d.RESERVED))})
SUPPORT_FILES.update({name: sha for name in wp5.SOURCES for sha in
                     [hashlib.sha256((wp5.ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()]})

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
               "governance", "interfaces", "control_bundles", "controller_compute", "ownership_closure", "internal_release", "wp4d", "wp5"}, "authority")
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
                          "WP2C_INERT_COMPUTE_FOUNDATION" if name in {"controller_iam", "controller_code_and_configuration"}
                          else "WP2B_BUNDLE_FOUNDATION_ONLY" if name == "artifact_and_evidence_protection"
                          else "WP2D_EXTRACTED_DECLARATIONS" if name in {"kms_authority", "oidc", "recovery_iam", "secret_metadata_and_policy", "shared_ecr_security", "workload_iam"}
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
    compute.validate_compute(root, doc)
    ownership.validate_publications(doc)
    internal.validate(root, doc)
    wp4d.validate(root, doc)
    wp5.validate(root, doc)
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
    root["module"]["controller_compute"] = {
        "source": "./modules/controller_compute", "authority": expression("local.authority"),
        "account_id": expression("var.aws_account_id"), "region": expression("var.aws_region"),
        "admin_arn": expression("var.security_admin_principal_arn"),
        "installations": expression("local.authority.internal_release.installations"),
        "runtime_approvals": expression("local.authority.internal_release.runtime_approvals"),
        "wp4d_installations": expression("local.authority.wp4d.installations"),
        "wp4d_runtime_approvals": expression("local.authority.wp4d.runtime_approvals"),
        "wp4d_environment_bindings": expression("local.authority.wp4d.environment_bindings"),
        "depends_on": ["module.protected_resources"]}
    root["output"]["controller_compute_foundation"] = {
        "value": expression("module.controller_compute.foundation"),
        "description": "TARGET compute declarations only; zero Lambda/CodeBuild instances, no invocation authorization."}
    root["module"]["protected_resources"] = {"source": "./modules/protected_resources", "account_id": expression("var.aws_account_id"), "region": expression("var.aws_region")}
    root["output"]["protected_output_candidates"] = {"value": expression("module.protected_resources.protected_output_candidates")}
    compute_module = compute.wiring()
    wp4d.extend(compute_module)
    wp5.extend(compute_module)
    for key in ('installations','runtime_approvals','environment_bindings'):
        root['module']['controller_compute']['wp5_'+key]=expression('local.authority.wp5.'+key)
    compute_module["locals"]["evidence_bucket"] = expression('"' + doc["ownership_closure"]["resources"]["neutral/artifacts"]["name"] + '${var.account_id}"')
    root["output"]["internal_release"] = {"value": expression("module.controller_compute.internal_release")}
    root["output"]["wp4d"] = {"value": expression("module.controller_compute.wp4d")}
    root['output']['wp5']={'value':expression('module.controller_compute.wp5')}
    root["module"]["control_bundle_storage"]["runtime_readers"] = expression("merge(module.controller_compute.internal_release.bundle_readers, module.controller_compute.wp4d.bundle_readers, module.controller_compute.wp5.bundle_readers)")
    ordinary_wiring = ordinary.wiring(doc)
    # WP4A's accepted target-group identity must be creatable by the extracted
    # greenfield skeleton. Legacy files remain pinned for WP7 retirement.
    for env in ("dev", "prod"):
        path = "terraform/modules/target/" + env + "/global/modules/alb/target_group.tf"
        for color in ("blue", "green"):
            ordinary_wiring[path] = ordinary_wiring[path].replace(
                '${var.name}-' + color + '-tg', 'demo-' + env + '-' + color)
    targets={**ordinary_wiring,**ownership.consumer_wiring(doc),**wp5.configuration(doc)}
    wp5.target_overlay(targets)
    root['module']['lifecycle_foundations']={'source':'./modules/lifecycle_foundations','account_id':expression('var.aws_account_id'),
        'region':expression('var.aws_region'),'admin_arn':expression('var.security_admin_principal_arn'),
        'nat_launch_inputs':expression('local.authority.wp5.nat_launch_inputs')}
    return {**targets, 'terraform/infra/security/modules/lifecycle_foundations/main.tf.json':wp5.foundations(),
            ownership.MODULE: ownership.wiring(doc), "terraform/infra/security/main.tf.json": root,
            "terraform/infra/security/modules/request_identities/main.tf.json": child,
            bundles.MODULE: bundles.wiring(doc["control_bundles"]),
            compute.MODULE: compute_module}


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
        require(((root / name).read_text() if isinstance(configuration, str) else load_json((root / name).read_text())) == configuration, "target wiring drift " + name)
    require((root / wrapper_path).read_text() == wrapper(doc), "security wrapper drift")
    # Non-IaC payloads under the protected roots are closed too.
    permitted = set(expected) | {AUTHORITY, "terraform/infra/security/README.md", wrapper_path, bundles.SOURCE}
    for directory in (root / "terraform/infra/security", root / "terraform/live/security", root / "terraform/modules/target"):
        for path in directory.rglob("*"):
            if path.is_file():
                require(path.relative_to(root).as_posix() in permitted, "unadmitted protected-root file")
    for name, expected_digest in SUPPORT_FILES.items():
        require((root / name).is_file() and sha((root / name).read_bytes()) == expected_digest, "protected source dependency drift " + name)
    return doc


def rendered_policies(doc, admin="arn:aws:iam::111122223333:role/SeparateHumanAdmin"):
    """One literal substitution, equivalent to the admitted templatefile operand."""
    require(bool(re.fullmatch(r"arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+", admin)), "synthetic admin identity")
    return load_json(json.dumps(doc["policies"]).replace("${security_admin_principal_arn}", admin))
