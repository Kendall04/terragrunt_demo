"""V4-03: refreshed source bytes cannot preserve stale dependency identity."""
import json
import re
import unittest

from graph import baseline
from inventory import verify
from source import Adapter
import test_v3


class DependencyBindingsV5Tests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def platform(self, root, extra="", commands='["validate", "plan"]'):
        path = root / "terraform/live/dev/apps/fargate/terragrunt.hcl"
        body = ('dependency "platform" {\n  config_path = "../../platform"\n'
                '  mock_outputs = {\n'
                '    cluster_arn = "arn:aws:ecs:us-east-1:111122223333:cluster/review-other"\n'
                '    cluster_name = "review-other"\n  }\n'
                '  mock_outputs_allowed_terraform_commands = ' + commands + '\n' + extra + '\n}')
        changed, count = re.subn(r'dependency "platform" \{[\s\S]*?\n\}', lambda _: body, path.read_text())
        self.assertEqual(count, 1)
        path.write_text(changed)
        self.acknowledge(root, pins=True)
        self.assertEqual(verify(root), [])

    def current(self, root):
        return next(record for record in baseline(root) if record["environment"] == "dev")

    def test_skip_outputs_and_apply_mocks_never_bind_old_cluster(self):
        root = self.fixture()
        before = Adapter(root, "dev").workload()
        self.platform(root, "  skip_outputs = true", '["validate", "plan", "apply"]')
        workload = Adapter(root, "dev").workload()
        self.assertEqual(workload["service"], "UNBOUND")
        self.assertEqual(workload["binding_status"], "PARTIAL")
        self.assertEqual(workload["dependency_output_selection"]["mode"], "UNSUPPORTED_OUTPUT_SELECTION")
        self.assertIn("skip_outputs", workload["service_binding_error"])
        # The real output declarations remain present and source pins are fresh;
        # neither fact establishes the selected output map.
        self.assertIn("demo-dev-platform-main-cluster", before["service"])
        for key in ("task_role", "exec_role", "family", "trusts"):
            self.assertEqual(workload[key], before[key], key)
        record = self.current(root)
        self.assertEqual(record["states"]["delivery:runtime"], "UNKNOWN")
        self.assertEqual(record["states"]["acquire:github_dev_deploy"], "ALLOW")
        self.assertEqual(record["provenance"]["workload"]["service"], "UNBOUND")

    def test_skip_false_plan_only_mocks_keep_declared_apply_relationship(self):
        root = self.fixture()
        self.platform(root, "  skip_outputs = false\n  mock_outputs_merge_with_state = true")
        workload = Adapter(root, "dev").workload()
        self.assertEqual(workload["binding_status"], "BINDING_VALIDATED")
        self.assertNotIn("review-other", workload["service"])
        selection = workload["dependency_output_selection"]
        self.assertEqual(selection["mode"], "REAL_DEPENDENCY_OUTPUTS")
        self.assertEqual(selection["mock_commands"], ["validate", "plan"])
        self.assertEqual(selection["mock_merge_strategy"], "shallow")
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "ALLOW")

    def test_same_path_with_apply_allowed_mocks_is_unknown_without_skip(self):
        root = self.fixture()
        self.platform(root, "  skip_outputs = false", '["apply"]')
        workload = Adapter(root, "dev").workload()
        self.assertEqual(workload["service"], "UNBOUND")
        self.assertIn("mocks may supply deployed identity", workload["service_binding_error"])
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "UNKNOWN")

    def test_dynamic_disabled_and_unadmitted_selection_fail_locally(self):
        for controls in ('  skip_outputs = local.choose_mocks', '  enabled = false',
                         '  mock_outputs_merge_strategy_with_state = "deep_map_only"',
                         '  new_output_selector = true', '  skip_outputs = "false"'):
            with self.subTest(controls=controls):
                root = self.fixture()
                self.platform(root, controls)
                workload = Adapter(root, "dev").workload()
                self.assertEqual(workload["service"], "UNBOUND")
                self.assertNotEqual(workload["task_role"], "UNBOUND")
                self.assertNotEqual(workload["exec_role"], "UNBOUND")
                self.assertEqual(workload["dependency_output_selection"]["mode"], "UNSUPPORTED_OUTPUT_SELECTION")

    def test_unbounded_or_dynamic_mock_commands_are_unknown(self):
        for commands in ('[]', 'local.commands', '["plan", "apply"]'):
            with self.subTest(commands=commands):
                root = self.fixture()
                self.platform(root, commands=commands)
                self.assertEqual(Adapter(root, "dev").workload()["service"], "UNBOUND")

    def test_no_mocks_explicit_enabled_real_outputs_are_supported(self):
        root = self.fixture()
        path = root / "terraform/live/dev/apps/fargate/terragrunt.hcl"
        text = re.sub(r'dependency "platform" \{[\s\S]*?\n\}',
            'dependency "platform" {\n  config_path = "../../platform"\n  skip_outputs = false\n  enabled = true\n}', path.read_text())
        path.write_text(text)
        self.acknowledge(root, pins=True)
        selection = Adapter(root, "dev").workload()["dependency_output_selection"]
        self.assertEqual(selection["mode"], "REAL_DEPENDENCY_OUTPUTS")
        self.assertEqual(selection["mock_commands"], [])
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "ALLOW")

    def test_dependency_provenance_records_effective_selection_and_current_hash(self):
        root = self.fixture()
        self.platform(root, "  skip_outputs = true")
        from source import digest
        selection = Adapter(root, "dev").workload()["dependency_output_selection"]
        self.assertEqual(selection["sha256"], digest(root / selection["source"]))
        self.assertEqual(selection["expressions"]["config_path"], '"../../platform"')
        self.assertEqual(selection["expressions"]["skip_outputs"], "true")
        self.assertIn("CURRENT_DECLARED_RESOURCE", selection["modeled_context"])
        self.assertIn("UNSUPPORTED_OUTPUT_SELECTION", selection["reason"])
