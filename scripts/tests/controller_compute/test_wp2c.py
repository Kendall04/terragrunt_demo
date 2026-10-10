"""WP2C actual-source tests. No Lambda/CodeBuild or AWS execution."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import bundles
import compute
from contracts import load_json
from evaluator import evaluate, Decision
from model import SUPPORT_FILES
from model import AUTHORITY, LEGACY, configuration_paths, validate_repository, wiring

ROOT = Path(__file__).resolve().parents[3]


class ComputeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = validate_repository(ROOT)
        cls.sources = configuration_paths(ROOT) | set(SUPPORT_FILES) | {AUTHORITY, LEGACY, bundles.SOURCE, "terraform/infra/security/README.md"}

    def fixture(self):
        tmp = tempfile.TemporaryDirectory(prefix="e1-wp2c-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in self.sources:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        return root

    def mutate(self, change, reason="WP2C_SOURCE_ADMISSION_FAILURE"):
        root = self.fixture()
        doc = copy.deepcopy(self.doc)
        change(doc)
        (root / AUTHORITY).write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, reason):
            validate_repository(root)

    def test_01_actual_terraform_consumes_canonical_source(self):
        generated = wiring(self.doc)
        for path, value in generated.items():
            self.assertEqual((ROOT / path).read_text() if isinstance(value, str) else load_json((ROOT / path).read_text()), value)
        root = generated["terraform/infra/security/main.tf.json"]
        self.assertEqual(root["module"]["controller_compute"]["authority"], "${local.authority}")
        self.assertIn("var.authority.control_bundles.consumer_references[n.bundle_binding]",
                      generated[compute.MODULE]["locals"]["nodes"])

    def test_02_existing_classes_and_binding_counts_preserved(self):
        c = self.doc["controller_compute"]
        self.assertEqual(set(c["classes"]), set(self.doc["control_bundles"]["classes"]))
        self.assertEqual(len(self.doc["control_bundles"]["consumer_references"]), 26)
        self.assertEqual(len(c["nodes"]), 18)
        self.assertEqual(sum(n["kind"] == "gateway" for n in c["nodes"].values()), 9)
        self.assertEqual(sum(v == "RESERVED_ONLY" for v in c["classes"].values()), 4)

    def test_03_every_node_security_owned(self):
        for key in self.doc["controller_compute"]["nodes"]:
            for owner in ("ORDINARY_LIFECYCLE_OWNED", "HIGH_RISK_LIFECYCLE_OWNED",
                          "DELIVERY_CONTROLLER_OWNED", "RECOVERY_CONTROLLER_OWNED", "request"):
                self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(owner=owner))

    def test_04_gateway_downstream_is_same_responsibility(self):
        c = self.doc["controller_compute"]
        for key, node in c["nodes"].items():
            if node["kind"] != "gateway":
                continue
            downstream = c["nodes"][node["downstream"]]
            g = self.doc["control_bundles"]["consumer_references"][key]
            p = self.doc["control_bundles"]["consumer_references"][downstream["bundle_binding"]]
            self.assertEqual(g["consumer"], p["consumer"])
            self.assertEqual(compute.describe_start(ROOT, self.doc, key), {"projectName": downstream["name"]})
            other = next(k for k, n in c["nodes"].items() if n["kind"] == "controller" and k != node["downstream"])
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(downstream=other))
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(downstream="CALLER_SELECTED"))

    def test_05_alternate_admitted_bundle_rejected(self):
        for key in self.doc["controller_compute"]["nodes"]:
            other = next(k for k in self.doc["control_bundles"]["consumer_references"] if k != key)
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(bundle_binding=other))

    def test_06_all_reservations_block_activation(self):
        for key in self.doc["controller_compute"]["nodes"]:
            result = compute.activation_status(ROOT, self.doc, key)
            self.assertTrue(result["declared"])
            self.assertFalse(result["operational"])
            self.assertIn("exact_installed_version", result["missing"])
            self.assertIn("later_reviewed_activation_implementation", result["missing"])
            self.assertTrue(set(compute.PREREQUISITES) <= set(result["missing"]))

    def test_07_no_superficial_activation_flag(self):
        for key in ("operational", "creation_supported"):
            self.mutate(lambda d: d["controller_compute"].update({key: True}))
        for key in self.doc["controller_compute"]["nodes"]:
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(operational=True))
            for prerequisite in compute.PREREQUISITES:
                self.mutate(lambda d: d["controller_compute"]["nodes"][key]["prerequisites"].update({prerequisite: True}))

    def test_08_fabricating_all_prerequisites_is_not_implementation(self):
        def change(d):
            c = d["controller_compute"]
            c.update(creation_supported=True, operational=True)
            for node in c["nodes"].values():
                node.update(operational=True, image_digest_uri="example/image@sha256:" + "a" * 64)
                node["prerequisites"] = dict.fromkeys(node["prerequisites"], True)
        self.mutate(change)

    def test_09_exact_version_not_latest_or_fabricated(self):
        for key in self.doc["control_bundles"]["consumer_references"]:
            for version in ("latest", "null", "", "fabricated-version"):
                self.mutate(lambda d: d["control_bundles"]["consumer_references"][key].update(version_id=version), "fixed consumer references")
        c = self.doc["controller_compute"]["consumption"]
        self.assertIn("version_id", c["identity_fields"])
        self.assertEqual(c["readback"], "VERIFY_EXACT_BYTES_BEFORE_EXECUTION")
        self.mutate(lambda d: d["controller_compute"]["consumption"].update(version="LATEST"))
        self.mutate(lambda d: d["controller_compute"]["consumption"].update(readback="SKIP"))

    def test_10_startbuild_closed_override_grammar(self):
        for field in compute.START_OVERRIDES:
            self.mutate(lambda d: d["controller_compute"]["invocation"]["requester_overrides"].update({field: "ALLOWED"}))
            self.mutate(lambda d: d["controller_compute"]["invocation"]["requester_overrides"].pop(field))
        self.mutate(lambda d: d["controller_compute"]["invocation"]["start_build_fields"].append("sourceVersion"))

    def test_11_request_payload_has_no_control_selection(self):
        c = self.doc["controller_compute"]
        payload = c["invocation"]["envelope"]
        self.assertEqual(compute.parse_envelope(c, json.dumps(payload).encode()), payload)
        forbidden = compute.START_OVERRIDES | {"controller", "class", "gateway", "bundle_id", "sha256", "digest", "key",
            "version_id", "VersionId", "role", "account", "region", "environment", "principal", "approved", "mode",
            "terraform_path", "module", "routing_target", "payload", "data"}
        for field in forbidden:
            with self.assertRaisesRegex(ValueError, "closed inactive request envelope"):
                compute.parse_envelope(c, json.dumps(dict(payload, **{field: "attacker"})).encode())

    def test_12_malformed_duplicate_oversized_envelopes(self):
        c = self.doc["controller_compute"]
        for raw in (b'{', b'[]', b'null', b'{"schema":"x","schema":"E1_WP2C_INACTIVE_V1"}',
                    b'x' * 257, b'\xff', b'{"schema":NaN}'):
            with self.assertRaises(ValueError):
                compute.parse_envelope(c, raw)

    def test_13_valid_request_still_cannot_start(self):
        raw = json.dumps(self.doc["controller_compute"]["invocation"]["envelope"]).encode()
        for key, node in self.doc["controller_compute"]["nodes"].items():
            if node["kind"] == "gateway":
                with self.assertRaisesRegex(PermissionError, "WP2C_INACTIVE"):
                    compute.request_start(ROOT, self.doc, key, raw)
        # No callable transport/API/client argument exists to accidentally send the preview.
        import inspect
        self.assertEqual(list(inspect.signature(compute.request_start).parameters), ["root", "doc", "protected_gateway", "raw"])

    def test_14_runtime_configuration_substitution_rejected(self):
        for field in self.doc["controller_compute"]["runtime"]["overrides"]:
            self.mutate(lambda d: d["controller_compute"]["runtime"]["overrides"].update({field: "ALLOWED"}))
        for key in self.doc["controller_compute"]["nodes"]:
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(image_digest_uri="aws/codebuild/standard:latest"))
            self.mutate(lambda d: d["controller_compute"]["nodes"][key].update(role_name="attacker"))
        self.mutate(lambda d: d["controller_compute"]["runtime"]["buildspec"]["phases"]["build"].update(commands=["aws ecs update-service"]))
        self.mutate(lambda d: d["controller_compute"]["runtime"]["environment_keys"].append("CALLER_SOURCE"))

    def test_15_execution_roles_deny_all_domain_and_control_actions(self):
        policy = self.doc["policies"]["inert_permissions"]
        actions = ("ecs:RegisterTaskDefinition", "ecs:DeregisterTaskDefinition", "ecs:RunTask", "ecs:StartTask",
            "ecs:UpdateService", "ecs:CreateService", "ecs:CreateTaskSet", "iam:PassRole", "iam:PutRolePolicy",
            "elasticloadbalancing:ModifyListener", "elasticloadbalancing:ModifyRule", "elasticloadbalancing:RegisterTargets",
            "kms:PutKeyPolicy", "kms:CreateGrant", "secretsmanager:PutResourcePolicy", "s3:PutObject", "s3:GetObject",
            "s3:DeleteObjectVersion", "ecr:PutImage", "ec2:RunInstances", "codebuild:StartBuild", "codebuild:UpdateProject",
            "lambda:InvokeFunction", "lambda:UpdateFunctionConfiguration", "lambda:UpdateFunctionCode", "sts:AssumeRole")
        for node in self.doc["controller_compute"]["nodes"].values():
            for action in actions:
                self.assertEqual(evaluate({"principal": "arn:aws:iam::111122223333:role/" + node["role_name"],
                    "action": action, "resource": "*"}, identities=[policy]).decision, Decision.DENY)
        self.mutate(lambda d: d["controller_compute"].update(role_permissions_source="ECS_AND_PASSROLE"))
        for action in actions:
            self.mutate(lambda d: d["policies"]["inert_permissions"]["Statement"].append(
                {"Effect": "Allow", "Action": action, "Resource": "*"}), "one inert statement")

    def test_16_execution_trust_has_no_allow(self):
        for engine, policy in self.doc["controller_compute"]["role_trust"].items():
            self.assertTrue(all(s["Effect"] == "Deny" for s in policy["Statement"]))
            self.mutate(lambda d: d["controller_compute"]["role_trust"][engine]["Statement"][0].update(Effect="Allow"))

    def test_17_request_identities_still_inert(self):
        self.assertEqual(len(self.doc["request_identities"]), 11)
        self.assertTrue(all(s["Effect"] == "Deny" for s in self.doc["policies"]["inert_trust"]["Statement"]))
        for action in ("lambda:InvokeFunction", "codebuild:StartBuild"):
            self.mutate(lambda d: d["policies"]["inert_permissions"]["Statement"].append(
                {"Effect": "Allow", "Action": action, "Resource": "*"}), "one inert statement")

    def test_18_unknown_compute_iam_and_ordinary_root_rejected(self):
        for prefix in ("terraform/infra/security", "terraform/live/dev", "terraform/live/prod", "alternate"):
            for resource in ("aws_lambda_function", "aws_codebuild_project", "aws_iam_role", "aws_iam_policy", "aws_lambda_permission"):
                root = self.fixture()
                p = root / prefix / "extra.tf.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({"resource": {resource: {"extra": {}}}}))
                with self.assertRaisesRegex(ValueError, "unadmitted/missing IaC surface"):
                    validate_repository(root)

    def test_19_extra_buildspec_source_config_rejected(self):
        for name in ("buildspec.yml", "handler.py", "source.json", "runtime.env", "other-catalog.json"):
            root = self.fixture()
            (root / "terraform/infra/security" / name).write_text("unadmitted")
            with self.assertRaisesRegex(ValueError, "unadmitted protected-root file"):
                validate_repository(root)

    def test_20_actual_terraform_drift_rejected(self):
        changes = [lambda tf: tf["resource"]["aws_codebuild_project"]["controller"].update(for_each="${local.nodes}"),
            lambda tf: tf["resource"]["aws_lambda_function"]["gateway"].update(role="attacker"),
            lambda tf: tf["resource"]["aws_codebuild_project"]["controller"]["source"].update(type="GITHUB", location="attacker"),
            lambda tf: tf["resource"]["aws_codebuild_project"]["controller"]["environment"].update(image="latest"),
            lambda tf: tf["resource"]["aws_iam_role_policy"]["inert"].update(policy='{"Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'),
            lambda tf: tf["resource"]["aws_codebuild_project"].update(second={}),
            lambda tf: tf["locals"].update(nodes="${var.other_catalog}"),
            lambda tf: tf["resource"]["terraform_data"]["declaration"].pop("lifecycle")]
        for change in changes:
            root = self.fixture()
            p = root / compute.MODULE
            tf = json.loads(p.read_text())
            change(tf)
            p.write_text(json.dumps(tf))
            with self.assertRaisesRegex(ValueError, "target wiring drift"):
                validate_repository(root)

    def test_21_unknown_missing_duplicate_canonical_nodes(self):
        key = next(iter(self.doc["controller_compute"]["nodes"]))
        self.mutate(lambda d: d["controller_compute"]["nodes"].pop(key))
        self.mutate(lambda d: d["controller_compute"]["nodes"].update(extra=copy.deepcopy(d["controller_compute"]["nodes"][key])))
        root = self.fixture()
        p = root / AUTHORITY
        s = p.read_text().replace('"controller_compute": {', '"controller_compute": {}, "controller_compute": {')
        p.write_text(s)
        with self.assertRaises(ValueError):
            validate_repository(root)
        self.mutate(lambda d: d["controller_compute"].update(operational=0))

    def test_22_live_state_and_reserved_classes_cannot_activate(self):
        self.mutate(lambda d: d["controller_compute"].update(live="VERIFIED"))
        for name, status in self.doc["controller_compute"]["classes"].items():
            if status == "RESERVED_ONLY":
                self.mutate(lambda d: d["controller_compute"]["classes"].update({name: "SKELETON_DECLARED"}))
        self.assertFalse(self.doc["controller_compute"]["consumption"]["reservation_authorizes_invocation"])

    def test_23_fixed_templates_have_no_invocation_or_extra_permissions(self):
        tf = wiring(self.doc)[compute.MODULE]
        # WP2 skeleton remains inert; WP3C additions have their own exact gates
        # and acceptance matrix. Enumerate additions rather than allowing any.
        self.assertEqual(set(tf["resource"]), {"terraform_data", "aws_iam_role", "aws_iam_role_policy", "aws_lambda_function", "aws_codebuild_project",
            "aws_cloudwatch_log_group", "aws_s3_bucket", "aws_s3_bucket_versioning",
            "aws_s3_bucket_public_access_block", "aws_s3_bucket_server_side_encryption_configuration",
            "aws_s3_bucket_lifecycle_configuration", "aws_s3_bucket_policy", "aws_cloudwatch_event_rule",
        "aws_cloudwatch_event_target", "aws_lambda_permission", "aws_lambda_alias", "aws_ecr_repository", "aws_ecr_repository_policy", "aws_iam_policy", "aws_iam_role_policy_attachment"})
        self.assertEqual(tf["resource"]["aws_lambda_function"]["gateway"]["for_each"], "${local.gateways}")
        self.assertEqual(tf["resource"]["aws_codebuild_project"]["controller"]["for_each"], "${local.projects}")
        self.assertEqual(tf["resource"]["aws_iam_role_policy"]["inert"]["policy"], "${jsonencode(var.authority.policies.inert_permissions)}")
        for name in ("gateways", "projects"):
            self.assertIn("creation_supported", tf["locals"][name])
            self.assertIn("version_id", tf["locals"][name])
            self.assertIn("alltrue(values(n.prerequisites))", tf["locals"][name])

    def test_24_bundle_bytes_still_verify(self):
        c = self.doc["control_bundles"]
        for name in c["classes"]:
            raw = bundles.artifact(ROOT, c, name)
            bundles.verify_artifact(ROOT, c, name, raw)
            with self.assertRaisesRegex(ValueError, "bundle digest mismatch"):
                bundles.verify_artifact(ROOT, c, name, raw + b' ')
        self.assertEqual(c["installation"]["active_set"], [])
        self.assertTrue(all(r["version_id"] is None and not r["operational"] for r in c["consumer_references"].values()))


if __name__ == "__main__":
    unittest.main()
