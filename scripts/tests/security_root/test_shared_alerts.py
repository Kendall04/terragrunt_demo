"""Closed DEV notification declaration; no AWS calls or delivery claims."""
import json
from pathlib import Path
import re
import unittest

import ordinary

ROOT = Path(__file__).resolve().parents[3]


class SharedAlertsTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
        self.files = ordinary.wiring(self.doc)
        self.main = self.files['terraform/modules/target/dev/shared/ordinary-main.tf']

    def test_generated_sources_match(self):
        for name in ('ordinary-main.tf', 'ordinary-variables.tf'):
            path = 'terraform/modules/target/dev/shared/' + name
            self.assertEqual((ROOT / path).read_text(), self.files[path])

    def test_topic_and_subscription_keep_their_addresses(self):
        self.assertEqual(self.main.count('resource "aws_sns_topic" "alerts"'), 1)
        self.assertEqual(self.main.count('resource "aws_sns_topic_subscription" "alerts_email"'), 1)
        self.assertIn('count     = var.alert_email == null ? 0 : 1', self.main)
        self.assertIn('endpoint  = var.alert_email', self.main)
        self.assertIn('kms_master_key_id = aws_kms_key.alerts.arn', self.main)
        variables = self.files['terraform/modules/target/dev/shared/ordinary-variables.tf']
        self.assertIn('sensitive   = true', variables)
        self.assertNotIn('@', self.main + variables)
        outputs = self.files['terraform/modules/target/dev/shared/ordinary-outputs.tf']
        self.assertIn('nonsensitive(var.alert_email != null)', outputs)
        self.assertNotIn('value       = var.alert_email\n', outputs)

    def test_exact_fourteen_alarm_names(self):
        text = self.main.split('alerts_alarm_names = ', 1)[1].split('\n', 1)[0]
        names = json.loads(text)
        expected = {
            'e1-nat-recovery-nat-dev-' + duty + '-destination-failed'
            for duty in ('assign_eip', 'change_rt', 'disable_sdc')
        } | {
            'e1-wp4-dev-nat-dlq-delivery-failed',
            'e1-wp4-dev-delivery-nat-failures',
            'e1-wp4-dev-execution-nat-failures',
        } | {
            'demo-dev-nat-' + slot + '-' + alarm
            for slot in ('a', 'b') for alarm in ('capacity-gap', 'inservice-low')
        } | {
            'demo-dev-tg-' + color + '-' + alarm
            for color in ('blue', 'green') for alarm in ('5xx', 'latency')
        }
        self.assertEqual(len(names), 14)
        self.assertEqual(set(names), expected)
        self.assertIn('arn:aws:cloudwatch:${var.region}:${var.account_id}:alarm:${name}', self.main)

    def test_publisher_grant_is_not_generic(self):
        grant = self.main.split('Sid       = "ExactCloudWatchAlarmPublisherUse"', 1)[1].split('lifecycle', 1)[0]
        self.assertIn('Service = "cloudwatch.amazonaws.com"', grant)
        self.assertIn('["kms:GenerateDataKey*", "kms:Decrypt"]', grant)
        self.assertIn('"aws:SourceAccount" = var.account_id', grant)
        self.assertIn('"aws:SourceArn" = local.alerts_alarm_arns', grant)
        self.assertNotIn('EncryptionContext', grant)
        self.assertNotIn('ViaService', grant)
        self.assertNotIn('events.amazonaws.com', self.main)
        self.assertNotIn('kms:*', self.main)

    def test_key_has_retention_rotation_and_exact_administrator(self):
        for expected in ('SYMMETRIC_DEFAULT', 'enable_key_rotation      = true',
                         'deletion_window_in_days  = 30', 'prevent_destroy = true',
                         'arn:aws:iam::${var.account_id}:user/cnp-cert-admin'):
            self.assertIn(expected, self.main)
        self.assertNotIn('bypass_policy_lockout_safety_check', self.main)

    def test_policy_keeps_original_statements_and_rejects_duplicate_owned_sid(self):
        self.assertIn('jsonencode(merge(local.alerts_policy_base', self.main)
        self.assertIn('concat(local.alerts_policy_base.Statement', self.main)
        self.assertIn('try(statement.Sid, "") != "AllowExactEcsDevCloudWatchAlarms"', self.main)
        self.assertIn('Action    = "sns:Publish"', self.main)
        self.assertIn('Resource  = local.alerts_topic_arn', self.main)
        variables = self.files['terraform/modules/target/dev/shared/ordinary-variables.tf']
        policy_input = variables.split('variable "alerts_topic_policy_base"', 1)[1]
        self.assertNotIn('default', policy_input.split('validation', 1)[0])

    def test_prod_does_not_gain_dev_key_or_policy(self):
        main = self.files['terraform/modules/target/prod/shared/ordinary-main.tf']
        self.assertIn('kms_master_key_id = "alias/aws/sns"', main)
        self.assertNotIn('aws_kms_key', main)
        self.assertNotIn('AllowExactEcsDevCloudWatchAlarms', main)

    def test_new_resource_surface_is_bounded(self):
        resources = set(re.findall(r'^resource "([^"]+)" "([^"]+)"', self.main, re.M))
        self.assertEqual(resources, {('aws_sns_topic', 'alerts'),
                                    ('aws_sns_topic_subscription', 'alerts_email'),
                                    ('aws_kms_key', 'alerts'), ('aws_sns_topic_policy', 'alerts')})

    def test_shared_lock_reuses_authenticated_aws_pin_without_upgrade(self):
        import wp5
        lock = wp5.configuration(self.doc)['terraform/modules/target/dev/shared/.terraform.lock.hcl']
        self.assertEqual(lock, wp5.dev_runtime_lock(ROOT))
        self.assertIn('version     = "5.100.0"', lock)
        self.assertIn('h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs=', lock)


if __name__ == '__main__':
    unittest.main()
