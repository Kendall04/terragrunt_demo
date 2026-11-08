"""Regression for the actual missing parent-resource classes; no AWS/processes."""
import copy
import json
from pathlib import Path
import unittest
from scripts import retirement_preflight as preflight

ROOT = Path(__file__).resolve().parents[3]
ACCOUNT = '341936017254'
REGION = 'us-east-1'
PREFIX = f'arn:aws:ec2:{REGION}:{ACCOUNT}:'


def allow(action, *resources):
    return {'Statement': [{'Effect': 'Allow', 'Action': action, 'Resource': list(resources)}]}


class RetirementPreflightTests(unittest.TestCase):
    def legacy(self):
        return [json.loads(path.read_text()) for path in sorted((ROOT / 'scripts/first_deployment').glob('operator-policy-*.json'))]

    def test_actual_legacy_operator_exports_reproduce_both_missing_dependencies(self):
        result = preflight.audit(self.legacy(), ACCOUNT, REGION)
        self.assertEqual(result['Missing'], [
            {'Action': 'ec2:DetachInternetGateway', 'MissingResourceType': 'vpc'},
            {'Action': 'ec2:DisassociateRouteTable', 'MissingResourceType': 'subnet'},
        ])
        self.assertEqual(result['Status'], 'BLOCKED_MISSING_COMPANION_RESOURCE_TYPES')
        self.assertFalse(result['AllowsCreation'])

    def test_partial_fix_still_blocks_other_companion(self):
        policies = self.legacy() + [allow('ec2:DetachInternetGateway', PREFIX + 'vpc/vpc-11111111111111111')]
        self.assertEqual(preflight.audit(policies, ACCOUNT, REGION)['Missing'], [
            {'Action': 'ec2:DisassociateRouteTable', 'MissingResourceType': 'subnet'}])

    def test_complete_scoped_shapes_never_claim_live_authorization(self):
        policies = self.legacy() + [
            allow('ec2:DetachInternetGateway', PREFIX + 'vpc/vpc-11111111111111111'),
            allow('ec2:DisassociateRouteTable', PREFIX + 'subnet/subnet-22222222222222222'),
        ]
        original = copy.deepcopy(policies)
        result = preflight.audit(policies, ACCOUNT, REGION)
        self.assertEqual(result['Missing'], [])
        self.assertEqual(result['Status'], 'STRUCTURAL_ONLY_LIVE_IAM_REVIEW_REQUIRED')
        self.assertFalse(result['AllowsCreation'])
        self.assertFalse(result['LiveAuthorizationProven'])
        self.assertEqual(policies, original)

    def test_wrong_action_scope_and_deny_are_not_missing_parent_allows(self):
        additions = [allow('ec2:AttachInternetGateway', PREFIX + 'vpc/*'),
                     allow('ec2:AssociateRouteTable', PREFIX + 'subnet/*'),
                     allow('ec2:DetachInternetGateway', 'arn:aws:ec2:us-west-2:' + ACCOUNT + ':vpc/*'),
                     allow('ec2:DisassociateRouteTable', 'arn:aws:ec2:' + REGION + ':999999999999:subnet/*')]
        denied = allow('ec2:*', PREFIX + 'vpc/*', PREFIX + 'subnet/*')
        denied['Statement'][0]['Effect'] = 'Deny'
        self.assertEqual(len(preflight.audit(self.legacy() + additions + [denied], ACCOUNT, REGION)['Missing']), 2)

    def test_bare_resource_star_does_not_substitute_scoped_resource_review(self):
        self.assertEqual(len(preflight.audit([allow('ec2:*', '*')], ACCOUNT, REGION)['Missing']), 4)

    def test_get_role_policy_wrapper_and_single_statement_are_supported(self):
        policies = [{'PolicyDocument': {'Statement': {'Effect': 'Allow', 'Action': 'ec2:*',
                    'Resource': [PREFIX + kind + '/*' for kind in ('vpc', 'subnet', 'route-table', 'internet-gateway')]}}}]
        self.assertEqual(preflight.audit(policies, ACCOUNT, REGION)['Missing'], [])
