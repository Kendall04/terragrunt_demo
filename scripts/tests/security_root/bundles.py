"""Closed WP2B bundle contract and deterministic, non-executing artifact codec.

Used by repository admission, the offline packager and Terraform generation.
No AWS client, subprocess, archive extraction or controller execution.
"""
import base64
import hashlib
import json
from pathlib import Path
import re

STAGE = "E1_WP2B_PROTECTED_CONTROL_BUNDLE_FOUNDATION"
SOURCE = "terraform/infra/security/bundles/NOTICE.txt"
EXECUTABLE_SOURCES = {
    "build": ("scripts/build_supervision/supervisor.py", "scripts/build_supervision/entrypoint.py",
              "scripts/qualification/finalizer.py", "ci/schemas/e1-qualification.schema.json",
              "ci/schemas/e1-build-attempt.schema.json", "ci/schemas/release-manifest.schema.json"),
    "qualification-finalizer": ("scripts/build_supervision/entrypoint.py", "scripts/qualification/finalizer.py",
                               "ci/schemas/e1-qualification.schema.json", "ci/schemas/release-manifest.schema.json"),
}
# Explicit WP3C additions; accepted build/finalizer package inputs remain unchanged.
_WP3C = tuple("scripts/internal_release/" + name + ".py" for name in
    ("e1_contract", "exchange", "publisher", "workers", "adapters", "services", "runtime", "worker"))
for _class in ("request-gateway", "status"):
    EXECUTABLE_SOURCES[_class] = EXECUTABLE_SOURCES["build"] + _WP3C

MODULE = "terraform/infra/security/modules/control_bundle_storage/main.tf.json"
OWNER = "SECURITY_ROOT_OWNED"
# Plan sections 1, 4.1, 5.1, 6.2, 8. These constrain class admission, not IAM grants.
CLASSES = {"request-gateway", "build", "qualification-finalizer", "status",
           "environment-lifecycle", "normal-delivery", "emergency-recovery",
           "cleanup-recovery", "nat-recovery"}
OVERRIDES = {"source", "source_revision", "secondary_sources", "buildspec",
             "environment_variables", "image", "command", "script", "artifact_key",
             "terraform_bundle", "terragrunt_bundle", "service_role", "debug",
             "network", "logging", "cache", "plugins"}


def require(ok, message):
    if not ok:
        raise ValueError("WP2B_SOURCE_ADMISSION_FAILURE: " + message)


def fields(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), label + " closed fields")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source_bytes(root):
    path = Path(root) / SOURCE
    require(path.is_file() and not path.is_symlink(), "missing/linked bundle source")
    raw = path.read_bytes()
    require(len(raw) <= 65536, "source size")
    # Explicit TEXT_UTF8_LF_V1 input contract; artifact hash itself is over exact bytes.
    text = raw.decode("utf-8").replace("\r\n", "\n")
    require("\r" not in text and "\x00" not in text, "source text encoding")
    return text.encode("utf-8")


def artifact(root, catalog, name):
    entry = catalog["classes"][name]
    package = {"format": catalog["format"], "class": name, "owner": entry["owner"],
                      "consumers": entry["consumers"], "engine": entry["engine"], "runtime_contract": catalog["runtime_contract"],
                      "operational": entry["operational"],
                      "files": {SOURCE: base64.b64encode(source_bytes(root)).decode("ascii")}}
    if name in EXECUTABLE_SOURCES:
        for relative in EXECUTABLE_SOURCES[name]:
            path = Path(root) / relative
            require(path.is_file() and not path.is_symlink(), "missing/linked executable source")
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            require(len(raw) <= 262144 and b"\x00" not in raw and b"\r" not in raw, "executable source encoding/size")
            package["files"][relative] = base64.b64encode(raw).decode("ascii")
        # Minimal protected runtime configuration avoids self-referential bundle hashes.
        # It derives from the same canonical authority, never a caller override.
        authority = json.loads((Path(root) / "terraform/infra/security/authority.json").read_text())
        config = {"controller_compute": {"nodes": {"build/release": {
            "name": authority["controller_compute"]["nodes"]["build/release"]["name"]}}},
            "ownership_closure": {"resources": {k: {"name": authority["ownership_closure"]["resources"][k]["name"]}
                for k in ("neutral/repository", "neutral/artifacts")}}}
        package["files"]["terraform/infra/security/authority.json"] = base64.b64encode(canonical(config)).decode("ascii")
        package["executable"] = {"language": "PYTHON", "version": ">=3.10", "dependencies": ("AWS_SDK_FROM_APPROVED_RUNTIME" if name in ("request-gateway", "status") else "STDLIB_ONLY"),
            "entrypoint": ("scripts/internal_release/runtime.py:handler" if name in ("request-gateway", "status") else "scripts/build_supervision/entrypoint.py:" + ("build" if name == "build" else "finalize")),
            "host": "ADMIN_AUTHENTICATED_ADAPTERS_REQUIRED", "activation": False,
            "controller_image": {"owner": OWNER, "binding": name + "/" + next(iter(entry["consumers"])),
                "uri": None, "approval": "UNVERIFIED", "requirement": "ADMIN_APPROVED_EXACT_REPOSITORY_AND_SHA256"}}
    return canonical(package)


def reference(catalog, name):
    item = catalog["classes"][name]
    return {"bundle_id": "sha256:" + item["sha256"], "sha256": item["sha256"],
            "storage": "control-bundles", "key": catalog["storage"]["prefix"] + item["sha256"] + ".json",
            "version_id": None, "installation": "UNVERIFIED", "operational": False}


def consumer_reference(catalog, name, consumer):
    require(name in catalog["classes"] and consumer in catalog["classes"][name]["consumers"], "unknown consumer")
    return {"class": name, "consumer": consumer, **reference(catalog, name)}


def verify_artifact(root, catalog, name, raw):
    require(name in catalog["classes"], "unknown bundle class")
    require(isinstance(raw, bytes) and len(raw) <= 1048576, "artifact bytes/size")
    require(digest(raw) == catalog["classes"][name]["sha256"], "bundle digest mismatch")
    require(raw == artifact(root, catalog, name), "bundle source/config mismatch")
    return reference(catalog, name)


def resolve_consumer(catalog, requested):
    fields(requested, {"class", "consumer", "bundle_id", "sha256", "storage", "key",
                       "version_id", "installation", "operational"}, "consumer reference")
    require(requested == consumer_reference(catalog, requested["class"], requested["consumer"]),
            "noncanonical consumer reference")
    return requested.copy()  # Reservation only; never an execution authorization.


def installation_proposal(root, catalog, name, raw):
    ref = verify_artifact(root, catalog, name, raw)
    return {"installer": OWNER, "authentication": "SEPARATELY_HELD_HUMAN_AUTHORITY",
            "reference": ref, "if_none_match": "*", "checksum_sha256": base64.b64encode(bytes.fromhex(ref["sha256"])).decode(),
            "read_back_exact_version_and_verify": True, "approval": "EXTERNAL_UNVERIFIED",
            "activation": False}


def validate_catalog(root, doc):
    catalog = doc["control_bundles"]
    fields(catalog, {"stage", "format", "owner", "source", "storage", "installation",
                     "runtime_contract", "classes", "consumer_references"}, "catalog")
    require(catalog["stage"] == STAGE and catalog["format"] == "E1_BUNDLE_JSON_V1"
            and catalog["owner"] == OWNER and catalog["source"] == SOURCE, "catalog identity/owner/source")
    require(catalog["installation"] == {"installer": OWNER, "authentication": "SEPARATELY_HELD_HUMAN_AUTHORITY",
            "approval": "EXTERNAL_UNVERIFIED", "upload": "CONDITIONAL_SINGLE_PUT",
            "replacement": "NEW_CONTENT_ID_REQUIRES_ADMIN_REVIEW", "version_capture": "READ_BACK_EXACT_VERSION_AND_VERIFY",
            "live": "UNVERIFIED", "active_set": []}, "installation must remain inactive")
    runtime = catalog["runtime_contract"]
    fields(runtime, {"overrides", "dependencies", "image", "buildspec", "execution"}, "runtime contract")
    require(runtime["overrides"] == {k: "FORBIDDEN" for k in OVERRIDES}, "runtime substitution")
    require(runtime["dependencies"] == "REVIEWED_IN_BUNDLE_OR_DIGEST_PINNED_IMAGE"
            and runtime["image"] is None and runtime["buildspec"] is None
            and runtime["execution"] == "NOT_IMPLEMENTED", "uninstalled runtime")
    storage = catalog["storage"]
    fields(storage, {"id", "owner", "bucket_prefix", "prefix", "versioning", "encryption",
                     "public_access_block", "object_ownership", "force_destroy", "prevent_destroy",
                     "live", "readers", "policy"}, "storage")
    require(storage["id"] == "control-bundles" and storage["owner"] == OWNER
            and storage["bucket_prefix"] == "e1-control-bundles-" and storage["prefix"] == "bundles/sha256/"
            and storage["versioning"] == "Enabled" and storage["encryption"] == "AES256"
            and storage["public_access_block"] is True and storage["object_ownership"] == "BucketOwnerEnforced"
            and storage["force_destroy"] is False and storage["prevent_destroy"] is True
            and storage["live"] == "UNVERIFIED" and storage["readers"] == [], "protected storage controls")
    # Closed policy grammar. Terraform consumes this canonical policy, not this validator.
    policy = storage["policy"]
    fields(policy, {"Version", "Statement"}, "storage policy")
    require(policy["Version"] == "2012-10-17" and isinstance(policy["Statement"], list)
            and len(policy["Statement"]) == 3, "storage policy statements")
    expected = [("AdminOnly", "s3:*", ["__BUCKET_ARN__", "__BUCKET_ARN__/*"],
                 {"ArnNotEquals": {"aws:PrincipalArn": "__ADMIN_ARN__"}}),
                ("RequireTLS", "s3:*", ["__BUCKET_ARN__", "__BUCKET_ARN__/*"],
                 {"Bool": {"aws:SecureTransport": "false"}}),
                ("RequireCreateOnly", "s3:PutObject", "__BUCKET_ARN__/*",
                 {"Null": {"s3:if-none-match": "true"}})]
    for statement, (sid, action, resource, condition) in zip(policy["Statement"], expected):
        require(statement == {"Sid": sid, "Effect": "Deny", "Principal": "*", "Action": action,
                              "Resource": resource, "Condition": condition}, "storage policy boundary " + sid)
    fields(catalog["classes"], CLASSES, "controller classes")
    requests = {k: v["environment"] for k, v in doc["request_identities"].items() if not k.startswith("plan-")}
    expected_consumers = {
        "request-gateway": requests, "build": {"release": "neutral"},
        "qualification-finalizer": {"qualification": "neutral"},
        "status": {"status-neutral": "neutral", "status-dev": "dev", "status-prod": "prod"},
        "environment-lifecycle": {k: v for k, v in requests.items() if k.startswith("infra-")},
        "normal-delivery": {"deploy-dev": "dev", "promote-prod": "prod"},
        "emergency-recovery": {"emergency-dev": "dev", "emergency-prod": "prod"},
        "cleanup-recovery": {"cleanup-dev": "dev", "cleanup-prod": "prod"},
        "nat-recovery": {"nat-dev": "dev", "nat-prod": "prod"}}
    refs = {}
    for name, entry in catalog["classes"].items():
        fields(entry, {"owner", "state", "operational", "consumers", "sha256", "engine"}, name)
        require(entry["owner"] == OWNER and entry["state"] == "RESERVED" and entry["operational"] is False,
                "class ownership/activation " + name)
        require(entry["consumers"] == expected_consumers[name], "fixed consumer responsibility " + name)
        require(entry["engine"] == ("CODEBUILD" if name in {"build", "environment-lifecycle", "normal-delivery", "emergency-recovery"}
                                    else "LAMBDA"), "planned consumer engine")
        require(isinstance(entry["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "exact digest")
        verify_artifact(root, catalog, name, artifact(root, catalog, name))
        for consumer in entry["consumers"]:
            refs[name + "/" + consumer] = consumer_reference(catalog, name, consumer)
    require(catalog["consumer_references"] == refs, "fixed consumer references")
    return catalog


def wiring(catalog):
    """Fixed rendering metadata; security values/policy are read from authority.json."""
    def ex(s):
        return "${" + s + "}"
    bucket = ex("aws_s3_bucket.bundles.id")
    return {"terraform": {"required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.50"}}},
        "variable": {"catalog": {"type": "any"}, "account_id": {"type": "string"}, "region": {"type": "string"},
                     "admin_arn": {"type": "string"}, "runtime_readers": {"type": "map(string)", "default": {}}},
        "resource": {
            "aws_s3_bucket": {"bundles": {"bucket": ex('"${var.catalog.storage.bucket_prefix}${var.account_id}-${var.region}"'),
                "force_destroy": ex("var.catalog.storage.force_destroy"),
                "lifecycle": {"prevent_destroy": catalog["storage"]["prevent_destroy"]},
                "tags": {"E1Owner": ex("var.catalog.storage.owner"), "E1Stage": ex("var.catalog.stage")}}},
            "aws_s3_bucket_versioning": {"bundles": {"bucket": bucket,
                "versioning_configuration": {"status": ex("var.catalog.storage.versioning")}}},
            "aws_s3_bucket_public_access_block": {"bundles": {"bucket": bucket,
                **{k: ex("var.catalog.storage.public_access_block") for k in
                   ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets")}}},
            "aws_s3_bucket_ownership_controls": {"bundles": {"bucket": bucket,
                "rule": {"object_ownership": ex("var.catalog.storage.object_ownership")}}},
            "aws_s3_bucket_server_side_encryption_configuration": {"bundles": {"bucket": bucket,
                "rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": ex("var.catalog.storage.encryption")}}}},
            "aws_s3_bucket_policy": {"bundles": {"bucket": bucket,
                "policy": ex('length(var.runtime_readers) == 0 ? replace(replace(jsonencode(var.catalog.storage.policy), "__BUCKET_ARN__", aws_s3_bucket.bundles.arn), "__ADMIN_ARN__", var.admin_arn) : jsonencode({ Version = "2012-10-17", Statement = [{ Sid = "AdminMutations", Effect = "Deny", Principal = "*", NotAction = "s3:GetObjectVersion", Resource = [aws_s3_bucket.bundles.arn, "${aws_s3_bucket.bundles.arn}/*"], Condition = { ArnNotEquals = { "aws:PrincipalArn" = var.admin_arn } } }, { Sid = "ExactRuntimeReaders", Effect = "Deny", Principal = "*", Action = "s3:GetObjectVersion", Resource = "${aws_s3_bucket.bundles.arn}/*", Condition = { ArnNotEquals = { "aws:PrincipalArn" = concat([var.admin_arn], values(var.runtime_readers)) } } }, { Sid = "TLS", Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.bundles.arn, "${aws_s3_bucket.bundles.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }, { Sid = "CreateOnly", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.bundles.arn}/*", Condition = { StringNotEquals = { "s3:if-none-match" = "*" } } }] })')}}},
        "output": {"reservation": {"value": {"bucket_id": bucket, "catalog": ex("var.catalog"),
                    "operational": False, "installation": "UNVERIFIED"}}}}
