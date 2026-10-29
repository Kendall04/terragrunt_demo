"""DEV installation containment and unchanged version-address contracts; offline."""
import json
from pathlib import Path
import unittest

from model import load_authority, wiring
import wp5

ROOT = Path(__file__).resolve().parents[3]
MODULE = "terraform/infra/security/modules/controller_compute/main.tf.json"


class DevInhibitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generated = wiring(load_authority(ROOT))
        cls.root = cls.generated["terraform/infra/security/main.tf.json"]
        cls.child = cls.generated[MODULE]

    def test_safe_defaults_are_forwarded_without_an_activation_side_effect(self):
        for name in ("dev_nat_inhibited", "dev_delivery_inhibited"):
            expected = {"type": "bool", "default": True, "nullable": False}
            self.assertEqual(self.root["variable"][name], expected)
            self.assertEqual(self.child["variable"][name], expected)
            self.assertEqual(self.root["module"]["controller_compute"][name], "${var." + name + "}")

    def test_only_the_five_original_dev_bindings_are_selected(self):
        expression = self.child["resource"]["aws_lambda_function"]["wp4d"]["reserved_concurrent_executions"]
        # Terraform evaluation of all four flag combinations is in nat/check_static.py.
        for key in ("nat-recovery/nat-dev/assign_eip", "nat-recovery/nat-dev/change_rt",
                    "nat-recovery/nat-dev/disable_sdc", "request-gateway/deploy-dev",
                    "cleanup-recovery/cleanup-dev"):
            self.assertIn('"' + key + '"', expression)
        self.assertNotIn("prod", expression)
        self.assertIn("var.dev_nat_inhibited", expression)
        self.assertIn("var.dev_delivery_inhibited", expression)

    def test_nat_rule_is_explicitly_inhibited_and_prod_remains_unspecified(self):
        rule = self.child["resource"]["aws_cloudwatch_event_rule"]["wp4d_nat"]
        self.assertEqual(rule["state"], '${each.key == "dev" ? (var.dev_nat_inhibited ? "DISABLED" : "ENABLED") : null}')
        self.assertNotIn("is_enabled", rule)

    def test_wp5_is_not_the_installed_deploy_gateway(self):
        # WP5 owns infra-dev/infra-high-risk-dev gateways, not deploy-dev or cleanup.
        # Changing them would broaden this correction beyond the five inhibited functions.
        self.assertNotIn("request-gateway/deploy-dev", wp5.BINDINGS)
        self.assertEqual(self.child["resource"]["aws_lambda_function"]["wp5"]["reserved_concurrent_executions"], 1)

    def test_version_bound_auxiliaries_keep_their_addresses_and_qualified_scope(self):
        resources = self.child["resource"]
        for kind in ("aws_lambda_permission", "aws_lambda_function_event_invoke_config"):
            item = resources[kind]["wp4d_nat"]
            self.assertEqual(item["for_each"], "${local.wp4d_nat_targets}")
            self.assertEqual(item["qualifier"], "${aws_lambda_function.wp4d[each.key].version}")
            self.assertNotIn("lifecycle", item)  # no ignore_changes or hidden retention engine
        self.assertNotIn("moved", self.child)  # no invented live state addresses
        permission = resources["aws_lambda_permission"]["wp4d_nat"]
        self.assertEqual(permission["principal"], "events.amazonaws.com")
        self.assertEqual(permission["source_account"], "${var.account_id}")
        async_config = resources["aws_lambda_function_event_invoke_config"]["wp4d_nat"]
        self.assertEqual(async_config["maximum_event_age_in_seconds"], 900)
        self.assertEqual(async_config["maximum_retry_attempts"], 1)
        self.assertIn("on_failure", async_config["destination_config"])

    def test_generator_matches_checked_in_outputs(self):
        for name in ("terraform/infra/security/main.tf.json", MODULE):
            self.assertEqual(self.generated[name], json.loads((ROOT / name).read_text()))
