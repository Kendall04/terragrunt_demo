"""WP2C closed compute declarations and non-executing request boundary.

This is repository admission/contract code, not an installed Lambda handler.
No AWS transport, subprocess, artifact extraction, upload or execution exists.
"""
import copy
import json

import bundles
from contracts import load_json

STAGE = "E1_WP2C_PROTECTED_CONTROLLER_COMPUTE_FOUNDATION"
MODULE = "terraform/infra/security/modules/controller_compute/main.tf.json"
OWNER = bundles.OWNER
# Closed admission grammar for the API, not a second responsibility/binding map.
START_OVERRIDES = {
    "projectName", "sourceVersion", "sourceLocationOverride", "sourceTypeOverride",
    "secondarySourcesOverride", "secondarySourcesVersionOverride", "buildspecOverride",
    "environmentVariablesOverride", "imageOverride", "computeTypeOverride",
    "serviceRoleOverride", "artifactsOverride", "secondaryArtifactsOverride", "cacheOverride",
    "privilegedModeOverride", "command", "script", "bundle", "debugSessionEnabled",
    "environmentTypeOverride", "imagePullCredentialsTypeOverride", "registryCredentialOverride",
    "sourceAuthOverride", "insecureSslOverride", "gitCloneDepthOverride",
    "gitSubmodulesConfigOverride", "logsConfigOverride", "encryptionKeyOverride",
    "certificateOverride", "reportBuildStatusOverride", "buildStatusConfigOverride",
    "timeoutInMinutesOverride", "queuedTimeoutInMinutesOverride", "autoRetryLimitOverride",
    "fleetOverride", "hostKernelOverride", "idempotencyToken",
}
PREREQUISITES = {"installed_bundle", "verified_readback", "accepted_controller_contract",
                 "complete_role_permissions", "accepted_request_trust_wiring"}


def require(ok, message):
    if not ok:
        raise ValueError("WP2C_SOURCE_ADMISSION_FAILURE: " + message)


def expected_contract(doc):
    """Derive the closed topology from WP2B engines and exact consumer ownership.

    CodeBuild consumers already identify each non-plan request responsibility.
    No independently maintained gateway-to-class or consumer mapping exists here.
    """
    catalog = doc["control_bundles"]
    nodes = {}
    projects = {}
    for binding, ref in catalog["consumer_references"].items():
        if catalog["classes"][ref["class"]]["engine"] == "CODEBUILD":
            require(ref["consumer"] not in projects, "ambiguous downstream responsibility")
            projects[ref["consumer"]] = binding
    gateways = catalog["classes"]["request-gateway"]["consumers"]
    require(set(projects) == set(gateways), "gateway/project responsibility coverage")
    for binding, ref in catalog["consumer_references"].items():
        gateway = ref["class"] == "request-gateway"
        if not gateway and binding not in projects.values():
            continue
        kind = "gateway" if gateway else "controller"
        name = "e1-" + kind + "-" + ref["consumer"]
        nodes[binding] = {
            "name": name, "owner": OWNER, "kind": kind,
            "engine": catalog["classes"][ref["class"]]["engine"],
            "bundle_binding": binding,
            "request_identity": ref["consumer"] if gateway else None,
            "downstream": projects[ref["consumer"]] if gateway else None,
            "role_name": name + "-exec", "role_class": kind.upper() + "_EXECUTION",
            "declared": True, "operational": False,
            "prerequisites": {key: False for key in sorted(PREREQUISITES)},
            "image_digest_uri": None,
        }
    return {
        "stage": STAGE, "owner": OWNER, "declared": True, "operational": False,
        "live": "UNVERIFIED", "creation_supported": False,
        "classes": {name: ("SKELETON_DECLARED" if any(
            ref["class"] == name and key in nodes for key, ref in catalog["consumer_references"].items())
            else "RESERVED_ONLY") for name in catalog["classes"]},
        "nodes": nodes,
        "invocation": {
            "permission": "DEFERRED_NO_STARTBUILD_OR_INVOKE",
            "selection": "PROTECTED_CONFIGURATION_ONLY",
            "start_build_fields": ["projectName"],
            "requester_overrides": {key: "FORBIDDEN" for key in sorted(START_OVERRIDES)},
            "envelope": {"schema": "E1_WP2C_INACTIVE_V1"},
            "max_envelope_bytes": 256,
            "unknown_fields": "REJECT",
        },
        "consumption": {
            "selection": "PROTECTED_CONFIGURATION_ONLY",
            "identity_fields": ["class", "consumer", "sha256", "key", "version_id"],
            "version": "EXACT_NON_NULL_INSTALLED_VERSION_REQUIRED",
            "readback": "VERIFY_EXACT_BYTES_BEFORE_EXECUTION",
            "reservation_authorizes_invocation": False,
            "executable_format": "DEFERRED_WP2B_JSON_IS_NOT_EXECUTABLE",
        },
        "runtime": {
            "overrides": copy.deepcopy(catalog["runtime_contract"]["overrides"]),
            "lambda_package_type": "Image", "lambda_reserved_concurrency": 0,
            "codebuild_source_type": "NO_SOURCE", "codebuild_artifacts_type": "NO_ARTIFACTS",
            "codebuild_environment_type": "LINUX_CONTAINER", "codebuild_compute_type": "BUILD_GENERAL1_SMALL",
            "codebuild_privileged_mode": False, "codebuild_cache_type": "NO_CACHE",
            "codebuild_logs_status": "DISABLED", "codebuild_timeout_minutes": 5,
            "buildspec": {"version": "0.2", "phases": {"build": {"commands": ["exit 1"]}}},
            "entrypoint": "FAIL_CLOSED_NO_BUNDLE_EXECUTION",
            "environment_keys": ["E1_PROTECTED_CONFIGURATION"],
        },
        "role_trust": {engine: {"Version": "2012-10-17", "Statement": [{
            "Effect": "Deny", "Action": "sts:AssumeRole", "Principal": {"Service": service}}]}
            for engine, service in (("LAMBDA", "lambda.amazonaws.com"), ("CODEBUILD", "codebuild.amazonaws.com"))},
        "role_permissions_source": "authority.policies.inert_permissions",
        "future_codebuild_trust": "SERVICE_ONLY_EXACT_PROJECT_ARN_AND_ACCOUNT_REVIEW_REQUIRED",
    }


def validate_compute(root, doc):
    bundles.validate_catalog(root, doc)
    require(bundles.canonical(doc.get("controller_compute")) == bundles.canonical(expected_contract(doc)),
            "closed compute contract / ownership / binding / activation / override drift")
    return doc["controller_compute"]


def describe_start(root, doc, protected_gateway):
    """Offline reservation shape only. protected_gateway is ADMIN config, not payload.

    Must never be used as invocation authorization. No transport is accepted here.
    """
    c = validate_compute(root, doc)
    require(protected_gateway in c["nodes"], "unknown protected gateway")
    gateway = c["nodes"][protected_gateway]
    require(gateway["kind"] == "gateway", "not a gateway")
    project = c["nodes"][gateway["downstream"]]
    return {"projectName": project["name"]}


def parse_envelope(contract, raw):
    require(isinstance(raw, bytes) and len(raw) <= contract["invocation"]["max_envelope_bytes"],
            "request envelope size/type")
    payload = load_json(raw.decode("utf-8"))
    require(payload == contract["invocation"]["envelope"], "closed inactive request envelope")
    return payload


def activation_status(root, doc, protected_node):
    c = validate_compute(root, doc)
    require(protected_node in c["nodes"], "unknown protected compute")
    node = c["nodes"][protected_node]
    ref = doc["control_bundles"]["consumer_references"][node["bundle_binding"]]
    missing = [key for key, value in node["prerequisites"].items() if value is not True]
    if ref["version_id"] is None or ref["installation"] != "VERIFIED":
        missing.append("exact_installed_version")
    if node["image_digest_uri"] is None:
        missing.append("reviewed_image_digest")
    # There is no activation implementation in WP2C, even for fabricated prerequisites.
    missing.append("later_reviewed_activation_implementation")
    return {"declared": True, "operational": False, "missing": sorted(missing)}


def request_start(root, doc, protected_gateway, raw):
    c = validate_compute(root, doc)
    parse_envelope(c, raw)
    describe_start(root, doc, protected_gateway)
    status = activation_status(root, doc, protected_gateway)
    raise PermissionError("WP2C_INACTIVE: " + ",".join(status["missing"]))


def wiring():
    """Fixed templates consuming the single authority source; no embedded topology."""
    def ex(s):
        return "${" + s + "}"
    node = "each.value"
    # Deliberately non-activatable in this slice. Missing facts cannot be defaulted true.
    ready = ('var.authority.controller_compute.creation_supported && n.operational && '
             'alltrue(values(n.prerequisites)) && '
             'try(n.bundle.version_id != null && n.bundle.version_id != "" && '
             'n.bundle.version_id != "null" && n.bundle.version_id != "latest" && '
             'n.bundle.installation == "VERIFIED" && n.bundle.operational && '
             'can(regex("@sha256:[0-9a-f]{64}$", n.image_digest_uri)), false)')
    local = {
        "nodes": ex('{ for key, n in var.authority.controller_compute.nodes : key => merge(n, { '
                    'bundle = var.authority.control_bundles.consumer_references[n.bundle_binding] }) }'),
        "gateways": ex('{ for key, n in local.nodes : key => n if n.kind == "gateway" && (' + ready + ') }'),
        "projects": ex('{ for key, n in local.nodes : key => n if n.kind == "controller" && (' + ready + ') }'),
    }
    tags = {"E1Owner": ex(node + ".owner"), "E1Stage": ex("var.authority.controller_compute.stage")}
    configuration = ex('jsonencode({ node = each.value, downstream = '
                       'try(local.nodes[each.value.downstream], null) })')
    guard = {"precondition": {"condition": ex("!var.authority.controller_compute.creation_supported && !var.authority.controller_compute.operational"),
             "error_message": "WP2C cannot create or activate Lambda/CodeBuild instances; later reviewed installation required."}}
    return {
        "terraform": {"required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.50"}}},
        "variable": {"authority": {"type": "any"}},
        "locals": local,
        "resource": {
            "terraform_data": {"declaration": {"for_each": ex("local.nodes"), "input": ex("each.value"), "lifecycle": guard}},
            "aws_iam_role": {"execution": {"for_each": ex("local.nodes"), "name": ex("each.value.role_name"),
                "assume_role_policy": ex("jsonencode(var.authority.controller_compute.role_trust[each.value.engine])"),
                "description": "WP2C inert execution identity: no trust Allow, deny all AWS actions.",
                "tags": tags, "lifecycle": guard}},
            "aws_iam_role_policy": {"inert": {"for_each": ex("local.nodes"), "name": "wp2c-inert",
                "role": ex("aws_iam_role.execution[each.key].id"),
                "policy": ex("jsonencode(var.authority.policies.inert_permissions)")}},
            "aws_lambda_function": {"gateway": {"for_each": ex("local.gateways"),
                "function_name": ex("each.value.name"), "role": ex("aws_iam_role.execution[each.key].arn"),
                "package_type": ex("var.authority.controller_compute.runtime.lambda_package_type"),
                "image_uri": ex("each.value.image_digest_uri"), "publish": True,
                "reserved_concurrent_executions": ex("var.authority.controller_compute.runtime.lambda_reserved_concurrency"),
                "environment": {"variables": {"E1_PROTECTED_CONFIGURATION": configuration}}, "tags": tags}},
            "aws_codebuild_project": {"controller": {"for_each": ex("local.projects"),
                "name": ex("each.value.name"), "service_role": ex("aws_iam_role.execution[each.key].arn"),
                "build_timeout": ex("var.authority.controller_compute.runtime.codebuild_timeout_minutes"),
                "source": {"type": ex("var.authority.controller_compute.runtime.codebuild_source_type"),
                           "buildspec": ex("jsonencode(var.authority.controller_compute.runtime.buildspec)")},
                "artifacts": {"type": ex("var.authority.controller_compute.runtime.codebuild_artifacts_type")},
                "environment": {"type": ex("var.authority.controller_compute.runtime.codebuild_environment_type"),
                    "compute_type": ex("var.authority.controller_compute.runtime.codebuild_compute_type"),
                    "image": ex("each.value.image_digest_uri"),
                    "privileged_mode": ex("var.authority.controller_compute.runtime.codebuild_privileged_mode"),
                    "environment_variable": {"name": "E1_PROTECTED_CONFIGURATION", "type": "PLAINTEXT", "value": configuration}},
                "cache": {"type": ex("var.authority.controller_compute.runtime.codebuild_cache_type")},
                "logs_config": {"cloudwatch_logs": {"status": ex("var.authority.controller_compute.runtime.codebuild_logs_status")},
                                "s3_logs": {"status": ex("var.authority.controller_compute.runtime.codebuild_logs_status")}}, "tags": tags}},
        },
        "output": {"foundation": {"value": {"declared": ex("var.authority.controller_compute.declared"),
            "operational": False, "live": ex("var.authority.controller_compute.live"),
            "declarations": ex("local.nodes"), "gateway_instances": ex("keys(local.gateways)"),
            "project_instances": ex("keys(local.projects)")}}},
    }
