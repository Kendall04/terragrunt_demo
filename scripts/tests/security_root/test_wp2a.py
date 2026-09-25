"""Mutations attack admission/ownership, not arbitrary Terraform semantics."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from contracts import load_json
from coverage import ClosedUniverse
from evaluator import Decision as D, Unsupported, evaluate
from graph import baseline, closure
from bundles import SOURCE
from model import SUPPORT_FILES
from model import (AUTHORITY, LEGACY, PROTECTED, CATEGORIES, REQUESTS, configuration_paths,
                   load_authority, rendered_policies, sha, validate_repository, wiring)

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = ("ecs:RegisterTaskDefinition", "iam:PassRole", "ecs:UpdateService",
             "elasticloadbalancing:ModifyListener", "elasticloadbalancing:ModifyRule",
             "codebuild:StartBuild", "codebuild:UpdateProject", "lambda:UpdateFunctionCode",
             "lambda:UpdateFunctionConfiguration", "iam:PutRolePolicy", "iam:UpdateAssumeRolePolicy",
             "iam:PutRolePermissionsBoundary", "iam:DeleteRolePermissionsBoundary",
             "iam:CreatePolicyVersion", "kms:CreateGrant", "kms:PutKeyPolicy",
             "secretsmanager:PutResourcePolicy", "s3:PutObject", "s3:PutBucketPolicy",
             "ecr:SetRepositoryPolicy", "sts:AssumeRole")


class FoundationTests(unittest.TestCase):
    def fixture(self):
        tmp = tempfile.TemporaryDirectory(prefix="e1-wp2a-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in configuration_paths(ROOT) | set(SUPPORT_FILES) | {AUTHORITY, LEGACY, "terraform/infra/security/README.md", SOURCE}:
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        return root

    def mutate(self, change):
        root = self.fixture()
        path = root / AUTHORITY
        doc = load_json(path.read_text())
        change(doc)
        path.write_text(json.dumps(doc))
        with self.assertRaises((Unsupported, ValueError)):
            validate_repository(root)

    def test_closed_source_and_terraform_match(self):
        doc = validate_repository(ROOT)
        self.assertEqual(set(doc["request_identities"]), REQUESTS)
        self.assertEqual(len(doc["request_identities"]), 11)
        self.assertEqual(set(doc["ownership"]["categories"]), CATEGORIES)

    def test_all_protected_classes_have_external_security_owner(self):
        doc = load_authority(ROOT)
        self.assertEqual(set(doc["ownership"]["protected_classes"]), PROTECTED)
        self.assertTrue(all(c["owner"] == "SECURITY_ROOT_OWNED" for c in doc["ownership"]["protected_classes"].values()))
        self.assertFalse(doc["security_admin"]["created_by_this_root"])
        resource_types = set(wiring(doc)["terraform/infra/security/modules/request_identities/main.tf.json"]["resource"])
        self.assertEqual(resource_types, {"aws_iam_role", "aws_iam_role_policy"})

    def test_ordinary_and_high_risk_cannot_own_any_protected_class(self):
        for name in sorted(PROTECTED):
            for owner in ("ORDINARY_LIFECYCLE_OWNED", "HIGH_RISK_LIFECYCLE_OWNED"):
                with self.subTest(name=name, owner=owner):
                    self.mutate(lambda d: d["ownership"]["protected_classes"][name].update(owner=owner))

    def test_requester_cannot_own_itself_or_activate(self):
        self.mutate(lambda d: d["request_identities"]["infra-dev"].update(owner="ORDINARY_LIFECYCLE_OWNED"))
        self.mutate(lambda d: d["request_identities"]["infra-dev"].update(stage="ACTIVE"))
        self.mutate(lambda d: d["security_admin"].update(created_by_this_root=True))

    def test_all_requests_have_no_acquisition_or_operational_authority(self):
        doc = load_authority(ROOT)
        policies = rendered_policies(doc)
        for ident, role in doc["request_identities"].items():
            for action in FORBIDDEN:
                with self.subTest(role=ident, action=action):
                    result = evaluate({"principal": "arn:aws:iam::111122223333:role/" + role["name"],
                                       "action": action, "resource": "*"}, identities=[policies["inert_permissions"]])
                    self.assertEqual(result.decision, D.DENY)
                    # Policy-permission scope, not unsupported service API simulation.
                    self.assertEqual(result.provenance[0]["normalized_request"]["resource_normalization"], "SYMBOLIC_POLICY_SCOPE")
            for principal in ("arn:aws:iam::111122223333:role/SeparateHumanAdmin",
                              "arn:aws:iam::111122223333:role/" + role["name"]):
                self.assertEqual(evaluate({"principal": principal, "action": "sts:AssumeRole",
                    "resource": "arn:aws:iam::111122223333:role/" + role["name"]}, trust=[policies["inert_trust"]]).decision, D.DENY)

    def test_oidc_tokens_cannot_acquire_inert_roles(self):
        policies = rendered_policies(load_authority(ROOT))
        result = evaluate({"action": "sts:AssumeRoleWithWebIdentity", "resource": "arn:aws:iam::111122223333:role/e1-request-infra-dev",
            "principal": "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com",
            "context": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                        "token.actions.githubusercontent.com:sub": "repo:Kendall04/terragrunt_demo:environment:e1-infra-dev"}}, trust=[policies["inert_trust"]])
        self.assertEqual(result.decision, D.DENY)

    def test_added_allow_removed_deny_and_policy_controls_fail_admission(self):
        for action in FORBIDDEN:
            with self.subTest(action=action):
                self.mutate(lambda d: d["policies"]["inert_permissions"]["Statement"].append(
                    {"Effect": "Allow", "Action": action, "Resource": "*"}))
        self.mutate(lambda d: d["policies"]["inert_permissions"].update(Statement=[]))
        self.mutate(lambda d: d["policies"]["inert_trust"]["Statement"][0].update(Effect="Allow"))
        self.mutate(lambda d: d["policies"]["inert_permissions"]["Statement"][0].update(Condition={"Bool": {"aws:SecureTransport": "false"}}))

    def test_unsupported_authority_fields_and_template_execution_rejected(self):
        self.mutate(lambda d: d.update(extra_policy={"Effect": "Allow"}))
        self.mutate(lambda d: d["request_identities"]["infra-dev"].update(managed_policy_arns=["AdministratorAccess"]))
        self.mutate(lambda d: d["policies"]["inert_trust"]["Statement"][0].update(Principal={"AWS": "${file(\"elsewhere\")}"}))

    def test_duplicate_json_key_rejected(self):
        root = self.fixture()
        path = root / AUTHORITY
        path.write_text(path.read_text().replace('"format_version": 1', '"format_version": 1, "format_version": 1'))
        with self.assertRaises(ValueError):
            validate_repository(root)

    def test_backend_neutral_admin_owned_no_state_consumers(self):
        doc = validate_repository(ROOT)
        self.assertEqual(doc["backend"]["ordinary_access"], "NONE")
        self.assertEqual(doc["backend"]["bootstrap"], "EXTERNAL_ADMIN_PRECONDITION")
        backend = wiring(doc)["terraform/infra/security/main.tf.json"]["terraform"]["backend"]["s3"]
        self.assertEqual(backend, {k: doc["backend"][k] for k in ("key", "encrypt", "use_lockfile")})
        self.assertNotIn("bucket", backend)
        self.assertNotIn("region", backend)
        self.assertNotIn("remote_state", (ROOT / "terraform/live/security/terragrunt.hcl").read_text())
        self.mutate(lambda d: d["backend"].update(owner="ORDINARY_LIFECYCLE_OWNED"))
        self.mutate(lambda d: d["backend"].update(key="dev/shared/terraform.tfstate"))
        self.mutate(lambda d: d["backend"].update(ordinary_access="WRITE"))

    def test_interfaces_remain_unavailable_ids_only(self):
        doc = load_authority(ROOT)
        self.assertTrue(all(v["status"] == "UNAVAILABLE" and not v["secret_values"] and not v["security_state_access"] for v in doc["interfaces"].values()))
        self.mutate(lambda d: d["interfaces"]["workload_role_arns"].update(security_state_access=True))
        self.mutate(lambda d: d["interfaces"]["kms_key_arns"].update(status="DEPLOYED"))

    def test_external_governance_and_future_pins_are_unverified(self):
        doc = load_authority(ROOT)
        self.assertEqual(doc["governance"]["include_claim_keys"], ["repo", "context", "job_workflow_ref"])
        self.mutate(lambda d: d["governance"].update(verification="VERIFIED"))
        self.mutate(lambda d: d["request_identities"]["infra-high-risk-prod"]["oidc_expectation"].update(context="e1-infra-high-risk-dev"))

    def test_target_tf_policy_and_reference_drift_fail(self):
        for mode in ("policy", "extra_resource", "source", "backend", "provider"):
            with self.subTest(mode=mode):
                root = self.fixture()
                name = "terraform/infra/security/" + ("modules/request_identities/" if mode in ("policy", "extra_resource") else "") + "main.tf.json"
                path = root / name
                doc = load_json(path.read_text())
                if mode == "policy":
                    doc["resource"]["aws_iam_role_policy"]["inert"]["policy"] = '{"Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'
                elif mode == "extra_resource":
                    doc["resource"]["aws_iam_policy"] = {"bypass": {"policy": "opaque"}}
                elif mode == "source":
                    doc["locals"]["authority"] = '${jsondecode(file("other.json"))}'
                elif mode == "backend":
                    doc["terraform"]["backend"] = {"local": {}}
                else:
                    doc["provider"]["aws"]["assume_role"] = {"role_arn": "untrusted"}
                path.write_text(json.dumps(doc))
                with self.assertRaises(Unsupported):
                    validate_repository(root)

    def test_duplicate_out_of_model_roots_and_policy_surfaces_rejected(self):
        for name, text in (("terraform/infra/security/extra.tf", 'resource "aws_iam_policy" "new" {}'),
                           ("terraform/infra/security/override.tf.json", '{"resource":{}}'),
                           ("terraform/infra/ordinary/competing.tf", 'resource "aws_iam_role" "security_admin" {}'),
                           ("other-root/policy.tf.json", '{"resource":{"aws_iam_role":{}}}'),
                           ("terraform/live/dev/rogue/terragrunt.hcl", 'terraform { source = "../../../infra/security" }'),
                           ("terraform/infra/security/override.auto.tfvars.json", '{}'),
                           ("terraform/infra/security/program.py", 'print("not admitted")')):
            with self.subTest(name=name):
                root = self.fixture()
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                with self.assertRaises(Unsupported):
                    validate_repository(root)

    def test_legacy_cannot_silently_become_target_owner_or_consumer(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/main.tf"
        path.write_text(path.read_text() + '\nmodule "security" {\n source = "../security"\n}\n')
        with self.assertRaises(Unsupported):
            validate_repository(root)
        # A mere inventory refresh cannot bless the new owner.
        path = root / LEGACY
        legacy = load_json(path.read_text())
        legacy["sources"]["terraform/infra/shared/main.tf"] = sha((root / "terraform/infra/shared/main.tf").read_bytes())
        path.write_text(json.dumps(legacy))
        with self.assertRaises(Unsupported):
            validate_repository(root)

    def test_wrapper_cannot_inherit_ordinary_credentials_or_backend(self):
        root = self.fixture()
        path = root / "terraform/live/security/terragrunt.hcl"
        path.write_text(path.read_text() + '\ninclude "dev" { path = "../dev/root.hcl" }\n')
        with self.assertRaises(Unsupported):
            validate_repository(root)

    def test_current_baseline_retains_positive_partial_characterization(self):
        for record in baseline(ROOT):
            for node in ("acquire:github_terragrunt_cd", "delivery:runtime", "delivery:role-field-substitution",
                         "infra:stronger-workload-compute", "github_app_rollback:direct-routing", "legacy:combined-publish-route"):
                self.assertEqual(record["outcomes"][node]["verdict"], "WITNESS_ALLOW")
                self.assertEqual(record["outcomes"][node]["coverage"]["status"], "PARTIAL")
            self.assertEqual(record["dev_approval_evidence"]["verdict"], "WITNESS_ALLOW")
            self.assertFalse(any(x["verdict"] == "EFFECTIVE_DENY" for x in record["outcomes"].values()))

    def test_closed_synthetic_projection_and_stale_negative_evidence(self):
        # This directory owns ONLY synthetic policy-permission routes, not the
        # target repository or account. The authority source supplies policies.
        doc = validate_repository(ROOT)
        policies = rendered_policies(doc)
        with tempfile.TemporaryDirectory(prefix="e1-wp2a-closed-fixture-") as tmp:
            root = Path(tmp)
            (root / "universe.json").write_text(json.dumps({"kind": "CLOSED_SYNTHETIC_UNIVERSE",
                "seeds": ["hypothetical-session"], "subjects": ["ordinary-requester"], "mechanisms": ["identity-policy"], "outcomes": ["operation"]}))
            route = {"id": "state-write", "mechanism": "identity-policy", "target": "operation",
                     "prerequisites": ["hypothetical-session"], "subjects": ["ordinary-requester"],
                     "request": {"principal": "arn:aws:iam::111122223333:role/e1-request-infra-dev",
                                 "action": "s3:PutObject", "resource": "arn:aws:s3:::synthetic-admin-state/e1/security/terraform.tfstate"},
                     "policies": {"identities": [policies["inert_permissions"]]}}
            path = root / "routes.json"
            path.write_text(json.dumps({"routes": [route]}))
            universe = ClosedUniverse(root)
            certificate = universe.certificate("operation")
            self.assertEqual(closure(universe.seeds, universe.rules, {"operation": certificate}, universe)[0]["operation"], D.DENY)
            # A changed policy universe must not reuse the previous certificate.
            route["policies"]["identities"][0]["Statement"][0]["Effect"] = "Allow"
            path.write_text(json.dumps({"routes": [route]}))
            changed = ClosedUniverse(root)
            self.assertFalse(changed.validates(certificate, "operation", changed.seeds, changed.rules))
            self.assertEqual(closure(changed.seeds, changed.rules, universe=changed)[0]["operation"], D.ALLOW)
            (root / "unknown.tf").write_text('resource "unadmitted" "control" {}')
            unknown = ClosedUniverse(root)
            with self.assertRaises(Unsupported):
                unknown.certificate("operation")
            self.assertEqual(closure(unknown.seeds, unknown.rules, universe=unknown)[0]["operation"], D.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
