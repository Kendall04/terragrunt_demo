"""A3: source input mutations flow through adapter, primitive checks and graph.

All mutations use disposable source copies and acknowledge their new inventory.
No test changes an expected graph output or a synthetic binding to excuse drift.
"""
import json
import unittest

from evaluator import Decision as D, Unsupported, evaluate
from graph import baseline
from source import Adapter
import test_v3


class EffectiveBindingsV4Tests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def shared(self, root, **inputs):
        path = root / "terraform/live/dev/shared/terragrunt.hcl"
        text = path.read_text()
        # Replace known keys without depending on attribute padding; insert new
        # keys only in the actual wrapper inputs object.
        import re
        for key, expression in inputs.items():
            pattern = r"(?m)^\s*" + key + r"\s*=.*$"
            replacement = "  " + key + " = " + expression
            if re.search(pattern, text):
                text = re.sub(pattern, lambda _: replacement, text)
            else:
                start = text.index("inputs = {") + len("inputs = {")
                text = text[:start] + "\n" + replacement + text[start:]
        path.write_text(text)
        self.acknowledge(root)

    def current(self, root):
        return {record["environment"]: record for record in baseline(root)}

    def test_provider_creation_false_binds_lookup_instead_of_claiming_creation(self):
        root = self.fixture()
        self.shared(root, create_github_oidc_provider="false")
        model = Adapter(root, "dev")
        self.assertIs(model.effective_inputs["create_github_oidc_provider"], False)
        self.assertEqual(model.effective_inputs["github_oidc_provider_mode"], "LOOKUP_PROVIDER_REFERENCE")
        result = self.current(root)["dev"]
        self.assertEqual(result["states"]["acquire:github_dev_deploy"], "ALLOW")
        self.assertEqual(result["provenance"]["identity"]["effective_inputs"]["github_oidc_provider_mode"],
                         "LOOKUP_PROVIDER_REFERENCE")

    def test_explicit_equivalent_provider_reference_is_bound(self):
        root = self.fixture()
        provider = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"
        self.shared(root, create_github_oidc_provider="false", github_oidc_provider_arn=json.dumps(provider))
        model = Adapter(root, "dev")
        self.assertEqual(model.value("local.github_oidc_provider_arn"), provider)
        self.assertEqual(model.effective_inputs["github_oidc_provider_mode"], "EXPLICIT_PROVIDER_REFERENCE")
        self.assertEqual(self.current(root)["dev"]["states"]["delivery:runtime"], "ALLOW")

    def test_alternate_provider_cannot_retain_original_github_binding(self):
        root = self.fixture()
        for provider in ("arn:aws:iam::111122223333:oidc-provider/different.example",
                         "arn:aws:iam::999999999999:oidc-provider/token.actions.githubusercontent.com"):
            with self.subTest(provider=provider):
                self.shared(root, create_github_oidc_provider="false", github_oidc_provider_arn=json.dumps(provider))
                with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE.*provider identity"):
                    Adapter(root, "dev")
        # The independent prod source instance remains admitted.
        self.assertEqual(Adapter(root, "prod").binding_status, "BINDING_VALIDATED")

    def test_conflicting_creation_and_explicit_provider_are_not_collapsed(self):
        root = self.fixture()
        self.shared(root, create_github_oidc_provider="true",
                    github_oidc_provider_arn='"arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"')
        with self.assertRaisesRegex(Unsupported, "creation conflicts"):
            Adapter(root, "dev")

    def test_changed_release_bucket_reaches_policy_before_evaluation(self):
        root = self.fixture()
        self.shared(root, release_artifacts_bucket_name='"changed-artifact-bucket"')
        model = Adapter(root, "dev")
        role = model.roles["github_app_cd"]
        request = {"action": "s3:PutObject", "resource": "arn:aws:s3:::changed-artifact-bucket/deployments/prod/review.json"}
        self.assertEqual(evaluate(request, identities=role["policies"]).decision, D.ALLOW)
        request["resource"] = "arn:aws:s3:::demo-release-artifacts-111122223333/deployments/prod/review.json"
        self.assertEqual(evaluate(request, identities=role["policies"]).decision, D.DENY)
        record = self.current(root)["dev"]
        self.assertEqual(record["states"]["legacy:prod-record-write"], "ALLOW")
        self.assertEqual(record["provenance"]["policy_scope_only"]["release_object"],
                         "arn:aws:s3:::changed-artifact-bucket/deployments/prod/fixture.json")

    def test_changed_owner_repo_reaches_actual_trust_subject(self):
        root = self.fixture()
        self.shared(root, github_owner='"new-owner"', github_repo='"new.repository"')
        model = Adapter(root, "dev")
        token = {"action": "sts:AssumeRoleWithWebIdentity", "resource": "synthetic-role",
                 "principal": model.value("local.github_oidc_provider_arn"), "context": {
                     "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                     "token.actions.githubusercontent.com:sub": "repo:new-owner/new.repository:environment:dev"}}
        trust = [model.roles["github_dev_deploy"]["trust"]]
        self.assertEqual(evaluate(token, trust=trust).decision, D.ALLOW)
        token["context"]["token.actions.githubusercontent.com:sub"] = "repo:Kendall04/terragrunt_demo:environment:dev"
        self.assertEqual(evaluate(token, trust=trust).decision, D.DENY)
        self.assertEqual(self.current(root)["dev"]["states"]["delivery:runtime"], "ALLOW")

    def test_fixed_environment_region_and_account_overrides_fail_binding(self):
        for key, value in (("env", '"prod"'), ("aws_region", '"us-west-2"'),
                           ("project", '"different-project"'), ("account_id", '"999999999999"'),
                           ("aws_account_id", '"111122223333"')):
            with self.subTest(input=key):
                root = self.fixture()
                self.shared(root, **{key: value})
                with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                    Adapter(root, "dev")

    def test_equivalent_literal_inputs_and_null_fallback_keep_witness(self):
        root = self.fixture()
        self.shared(root, env='"dev"', project='"demo"', aws_region='"us-east-1"',
                    github_owner='"Kendall04"', github_repo='"terragrunt_demo"',
                    release_artifacts_bucket_name="null")
        model = Adapter(root, "dev")
        self.assertEqual(model.effective_inputs["release_artifacts_bucket_name"], "demo-release-artifacts-111122223333")
        self.assertEqual(self.current(root)["dev"]["states"]["delivery:runtime"], "ALLOW")

    def test_unknown_security_expression_cannot_use_old_substitution(self):
        for key, expression in (("release_artifacts_bucket_name", "dependency.storage.outputs.bucket"),
                                ("github_owner", "local.unknown_owner"),
                                ("github_oidc_provider_arn", '"${dependency.provider.outputs.arn}"'),
                                ("create_github_oidc_provider", '"false"')):
            with self.subTest(input=key):
                root = self.fixture()
                self.shared(root, **{key: expression})
                with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                    Adapter(root, "dev")

    def test_irrelevant_extra_input_has_explicit_nonapplicable_classification(self):
        root = self.fixture()
        self.shared(root, review_note="dependency.unrelated.outputs.metadata")
        model = Adapter(root, "dev")
        entries = [value for record in model.module_binding for value in record.get("inputs", [])]
        self.assertTrue(any(x["input"] == "review_note" and x["status"] == "NOT_APPLICABLE" for x in entries))
        self.assertEqual(self.current(root)["dev"]["states"]["delivery:runtime"], "ALLOW")

    def test_root_security_override_is_not_shadowed_by_synthetic_defaults(self):
        root = self.fixture()
        path = root / "terraform/live/dev/root.hcl"
        text = path.read_text()
        start = text.index("inputs = {") + len("inputs = {")
        path.write_text(text[:start] + '\n  release_artifacts_bucket_name = "root-artifact-bucket"\n' + text[start:])
        self.acknowledge(root)
        self.assertEqual(Adapter(root, "dev").value("local.release_artifacts_bucket_arn"), "arn:aws:s3:::root-artifact-bucket")
        self.shared(root, release_artifacts_bucket_name='"wrapper-artifact-bucket"')
        self.assertEqual(Adapter(root, "dev").value("local.release_artifacts_bucket_arn"), "arn:aws:s3:::wrapper-artifact-bucket")

    def test_layer_cluster_override_invalidates_workload_binding(self):
        root = self.fixture()
        path = root / "terraform/live/dev/apps/fargate/terragrunt.hcl"
        path.write_text(path.read_text().replace("dependency.platform.outputs.cluster_arn", '"arn:aws:ecs:us-east-1:111122223333:cluster/other"'))
        self.acknowledge(root, pins=True)
        model = Adapter(root, "dev")
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
            model.workload()
        record = self.current(root)["dev"]
        self.assertEqual(record["states"]["delivery:runtime"], "UNKNOWN")
        self.assertEqual(record["states"]["acquire:github_dev_deploy"], "ALLOW")

    def test_module_forwarding_cannot_override_bound_release_bucket(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/main.tf"
        path.write_text(path.read_text().replace("release_artifacts_bucket_name       = local.release_artifacts_bucket_name",
                                               'release_artifacts_bucket_name = "different-module-bucket"'))
        self.acknowledge(root)
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE.*release_artifacts_bucket_name"):
            Adapter(root, "dev")

    def test_include_merge_strategy_cannot_silently_remove_inherited_inputs(self):
        root = self.fixture()
        path = root / "terraform/live/dev/shared/terragrunt.hcl"
        path.write_text(path.read_text().replace('include "env" {', 'include "env" {\n  merge_strategy = "no_merge"'))
        self.acknowledge(root)
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE.*wrapper control"):
            Adapter(root, "dev")

    def test_changed_variable_default_cannot_keep_old_storage_value(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/variables.tf"
        text = path.read_text()
        start = text.index('variable "release_artifacts_bucket_name"')
        path.write_text(text[:start] + text[start:].replace("default     = null", 'default     = "changed-default"', 1))
        self.acknowledge(root)
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
            Adapter(root, "dev")

    def test_task_no_deny_control_rejects_malformed_action_even_after_pins_refresh(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/demo.tf"
        path.write_text(path.read_text().replace('"kms:Encrypt"', '"malformed action"'))
        self.acknowledge(root, pins=True)
        record = self.current(root)["dev"]
        self.assertEqual(record["states"]["infra:broaden-role"], "ALLOW")
        self.assertEqual(record["states"]["infra:stronger-workload-compute"], "UNKNOWN")
        self.assertEqual(record["provenance"]["workload"]["task_policy_controls"]["status"], "UNKNOWN")
