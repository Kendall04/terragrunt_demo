"""Actual-source mutations for the WP2B supply boundary; never executes bundles."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from bundles import (SOURCE, MODULE, OWNER, artifact, digest, reference, consumer_reference,
                     resolve_consumer, verify_artifact, installation_proposal)
from model import AUTHORITY, LEGACY, configuration_paths, validate_repository, wiring, rendered_policies
from evaluator import evaluate, Decision

ROOT = Path(__file__).resolve().parents[3]


class BundleTests(unittest.TestCase):
    def fixture(self):
        tmp = tempfile.TemporaryDirectory(prefix="e1-wp2b-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in configuration_paths(ROOT) | {AUTHORITY, LEGACY, SOURCE, "terraform/infra/security/README.md"}:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        return root

    def mutate(self, change, reason):
        root = self.fixture()
        p = root / AUTHORITY
        doc = json.loads(p.read_text())
        change(doc)
        p.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, reason):
            validate_repository(root)

    def test_canonical_catalog_is_consumed_by_actual_terraform(self):
        doc = validate_repository(ROOT)
        tf = json.loads((ROOT / "terraform/infra/security/main.tf.json").read_text())
        self.assertEqual(tf, wiring(doc)["terraform/infra/security/main.tf.json"])
        self.assertEqual(tf["module"]["control_bundle_storage"]["catalog"], "${local.authority.control_bundles}")
        child = json.loads((ROOT / MODULE).read_text())
        self.assertIn("var.catalog.storage.policy", child["resource"]["aws_s3_bucket_policy"]["bundles"]["policy"])
        self.assertEqual(child["output"]["reservation"]["value"]["catalog"], "${var.catalog}")

    def test_all_classes_and_consumers_are_reserved_security_owned(self):
        catalog = validate_repository(ROOT)["control_bundles"]
        self.assertEqual(len(catalog["classes"]), 9)
        self.assertEqual(len(catalog["consumer_references"]), 26)
        for entry in catalog["classes"].values():
            self.assertEqual(entry["owner"], OWNER)
            self.assertFalse(entry["operational"])
        self.assertEqual(catalog["installation"]["active_set"], [])

    def test_pack_and_verify_positive_for_every_class(self):
        catalog = validate_repository(ROOT)["control_bundles"]
        ids = set()
        for name in catalog["classes"]:
            raw = artifact(ROOT, catalog, name)
            self.assertEqual(raw, artifact(ROOT, catalog, name))
            self.assertEqual(verify_artifact(ROOT, catalog, name, raw), reference(catalog, name))
            self.assertEqual(digest(raw), catalog["classes"][name]["sha256"])
            ids.add(digest(raw))
        self.assertEqual(len(ids), len(catalog["classes"]))

    def test_modified_actual_source_rejected(self):
        root = self.fixture()
        with (root / SOURCE).open("a") as f:
            f.write("Modified source.\n")
        with self.assertRaisesRegex(ValueError, "bundle digest mismatch"):
            validate_repository(root)

    def test_modified_artifact_bytes_rejected(self):
        catalog = validate_repository(ROOT)["control_bundles"]
        for name in catalog["classes"]:
            raw = artifact(ROOT, catalog, name)
            with self.assertRaisesRegex(ValueError, "bundle digest mismatch"):
                verify_artifact(ROOT, catalog, name, raw + b" ")

    def test_new_content_requires_new_identity_and_all_fixed_references(self):
        root = self.fixture()
        doc = validate_repository(root)
        c = doc["control_bundles"]
        old = copy.deepcopy(c["consumer_references"])
        with (root / SOURCE).open("a") as f:
            f.write("Additional reviewed reservation documentation.\n")
        for name, entry in c["classes"].items():
            entry["sha256"] = digest(artifact(root, c, name))
        (root / AUTHORITY).write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "fixed consumer references"):
            validate_repository(root)
        for key in c["consumer_references"]:
            name, consumer = key.split("/")
            c["consumer_references"][key] = consumer_reference(c, name, consumer)
            self.assertNotEqual(old[key]["bundle_id"], c["consumer_references"][key]["bundle_id"])
        (root / AUTHORITY).write_text(json.dumps(doc))
        validate_repository(root)  # Explicit admin-reviewed replacement model; still inactive.

    def test_source_eol_normalization_is_explicit_and_deterministic(self):
        root = self.fixture()
        doc = validate_repository(root)
        p = root / SOURCE
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        validate_repository(root)
        self.assertEqual(artifact(root, doc["control_bundles"], "build"), artifact(ROOT, doc["control_bundles"], "build"))

    def test_floating_alias_and_unbound_digest_rejected(self):
        for value in ("latest", "main", "sha256:latest", "0" * 64):
            with self.subTest(value=value):
                self.mutate(lambda d: d["control_bundles"]["classes"]["build"].update(sha256=value), "exact digest|digest mismatch")
        self.mutate(lambda d: d["control_bundles"]["consumer_references"]["build/release"].update(key="bundles/latest.json"),
                    "fixed consumer references")

    def test_ordinary_and_high_risk_owners_rejected(self):
        for owner in ("ORDINARY_LIFECYCLE_OWNED", "HIGH_RISK_LIFECYCLE_OWNED"):
            self.mutate(lambda d: d["control_bundles"]["storage"].update(owner=owner), "protected storage controls")
            self.mutate(lambda d: d["control_bundles"]["classes"]["environment-lifecycle"].update(owner=owner), "class ownership")

    def test_unknown_and_duplicate_class_or_consumer_rejected(self):
        self.mutate(lambda d: d["control_bundles"]["classes"].update(other=copy.deepcopy(d["control_bundles"]["classes"]["build"])), "controller classes")
        self.mutate(lambda d: d["control_bundles"]["classes"]["build"]["consumers"].update(other="prod"), "fixed consumer responsibility")
        root = self.fixture()
        p = root / AUTHORITY
        p.write_text(p.read_text().replace('"control_bundles": {', '"control_bundles": {}, "control_bundles": {'))
        with self.assertRaises(ValueError):
            validate_repository(root)

    def test_storage_protection_and_no_current_readers(self):
        for field, value in (("readers", ["requester"]), ("versioning", "Suspended"), ("force_destroy", True),
                             ("public_access_block", False), ("prevent_destroy", False), ("bucket_prefix", "dev-artifacts-")):
            self.mutate(lambda d: d["control_bundles"]["storage"].update({field: value}), "protected storage controls")

    def test_policy_grant_or_weakened_deny_rejected(self):
        self.mutate(lambda d: d["control_bundles"]["storage"]["policy"]["Statement"][0].update(Effect="Allow"), "storage policy boundary")
        self.mutate(lambda d: d["control_bundles"]["storage"]["policy"]["Statement"].pop(), "storage policy statements")
        self.mutate(lambda d: d["control_bundles"]["storage"]["policy"]["Statement"][0]["Condition"]["ArnNotEquals"].update({"aws:PrincipalArn": "*"}), "storage policy boundary")

    def test_request_roles_still_deny_bundle_and_operation_actions(self):
        doc = validate_repository(ROOT)
        policies = rendered_policies(doc)
        for role in doc["request_identities"].values():
            for action in ("s3:PutObject", "s3:DeleteObject", "s3:DeleteObjectVersion", "s3:PutBucketPolicy",
                           "kms:PutKeyPolicy", "kms:CreateGrant", "codebuild:StartBuild", "lambda:InvokeFunction",
                           "ecs:RunTask", "iam:PassRole", "elasticloadbalancing:ModifyListener"):
                result = evaluate({"principal": "arn:aws:iam::111122223333:role/" + role["name"],
                                   "action": action, "resource": "*"}, identities=[policies["inert_permissions"]])
                self.assertEqual(result.decision, Decision.DENY)
        self.assertTrue(all(s["Effect"] == "Deny" for s in policies["inert_trust"]["Statement"]))

    def test_inert_request_mutation_grant_rejected(self):
        self.mutate(lambda d: d["policies"]["inert_permissions"]["Statement"].append(
            {"Effect": "Allow", "Action": "s3:PutObject", "Resource": "*"}), "one inert statement")
        self.mutate(lambda d: d["policies"]["inert_trust"]["Statement"][0].update(Effect="Allow"), "no operational Allow")

    def test_extra_storage_policy_iam_and_ordinary_duplicate_rejected(self):
        for name, resource in (("terraform/infra/security/extra.tf.json", "aws_s3_bucket"),
                               ("terraform/infra/shared/extra.tf.json", "aws_s3_bucket"),
                               ("other-root/main.tf.json", "aws_ecr_repository"),
                               ("terraform/infra/security/key.tf.json", "aws_kms_key"),
                               ("terraform/infra/security/policy.tf.json", "aws_s3_bucket_policy"),
                               ("terraform/infra/security/role.tf.json", "aws_iam_role")):
            root = self.fixture()
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"resource": {resource: {"competing": {}}}}))
            with self.assertRaisesRegex(ValueError, "unadmitted/missing IaC surface"):
                validate_repository(root)

    def test_actual_terraform_policy_source_and_catalog_drift_rejected(self):
        for mode in ("policy", "catalog", "extra"):
            root = self.fixture()
            p = root / (MODULE if mode != "catalog" else "terraform/infra/security/main.tf.json")
            tf = json.loads(p.read_text())
            if mode == "policy":
                tf["resource"]["aws_s3_bucket_policy"]["bundles"]["policy"] = '{}'
            elif mode == "catalog":
                tf["module"]["control_bundle_storage"]["catalog"] = '${jsondecode(file("detached.json"))}'
            else:
                tf["resource"]["aws_s3_bucket"]["competing"] = {"bucket": "other"}
            p.write_text(json.dumps(tf))
            with self.assertRaisesRegex(ValueError, "target wiring drift"):
                validate_repository(root)

    def test_outside_catalog_payload_and_alternate_root_invocation_rejected(self):
        for name, text in (("terraform/infra/security/bundles/alternate.json", '{}'),
                           ("terraform/live/dev/other/terragrunt.hcl", 'terraform { source = "../../../infra/security" }')):
            root = self.fixture()
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
            with self.assertRaisesRegex(ValueError, "unadmitted"):
                validate_repository(root)

    def test_all_reserved_consumers_resolve_exactly_and_cannot_override(self):
        c = validate_repository(ROOT)["control_bundles"]
        for ref in c["consumer_references"].values():
            self.assertEqual(resolve_consumer(c, ref), ref)
            for field, value in (("key", "latest"), ("sha256", "0" * 64), ("version_id", "latest"), ("operational", True)):
                changed = dict(ref, **{field: value})
                with self.assertRaisesRegex(ValueError, "noncanonical consumer reference"):
                    resolve_consumer(c, changed)
            with self.assertRaisesRegex(ValueError, "closed fields"):
                resolve_consumer(c, dict(ref, buildspecOverride="arbitrary"))

    def test_runtime_override_prohibitions_cannot_be_weakened(self):
        c = validate_repository(ROOT)["control_bundles"]
        for field in c["runtime_contract"]["overrides"]:
            self.mutate(lambda d: d["control_bundles"]["runtime_contract"]["overrides"].update({field: "CALLER_SELECTED"}), "runtime substitution")
        self.mutate(lambda d: d["control_bundles"]["runtime_contract"].update(image="latest"), "uninstalled runtime")

    def test_activation_and_false_installation_rejected(self):
        self.mutate(lambda d: d["control_bundles"]["classes"]["build"].update(operational=True), "class ownership/activation")
        self.mutate(lambda d: d["control_bundles"]["installation"].update(active_set=["build"]), "installation must remain inactive")
        self.mutate(lambda d: d["control_bundles"]["storage"].update(live="VERIFIED"), "protected storage controls")
        self.mutate(lambda d: d["governance"].update(verification="VERIFIED"), "external governance")

    def test_install_proposal_is_admin_only_unverified_and_not_execution(self):
        c = validate_repository(ROOT)["control_bundles"]
        proposal = installation_proposal(ROOT, c, "build", artifact(ROOT, c, "build"))
        self.assertEqual(proposal["installer"], OWNER)
        self.assertEqual(proposal["if_none_match"], "*")
        self.assertEqual(proposal["approval"], "EXTERNAL_UNVERIFIED")
        self.assertFalse(proposal["activation"])
        self.assertIsNone(proposal["reference"]["version_id"])

    def test_no_compute_or_operational_identity_resources(self):
        doc = validate_repository(ROOT)
        types = set()
        for tf in wiring(doc).values():
            types.update(tf.get("resource", {}))
        self.assertFalse(any(t.startswith(("aws_lambda", "aws_codebuild", "aws_sqs", "aws_ecs")) for t in types))
        role_module = json.loads((ROOT / "terraform/infra/security/modules/request_identities/main.tf.json").read_text())
        self.assertEqual(set(role_module["resource"]), {"aws_iam_role", "aws_iam_role_policy"})


if __name__ == "__main__":
    unittest.main()
