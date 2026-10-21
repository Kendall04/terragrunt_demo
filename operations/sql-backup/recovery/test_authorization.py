"""Offline syntax/scope regressions. These tests never assert AWS authorization."""
from copy import deepcopy
import json
import unittest

import authorization as a


def example_backend():
    # Structural fixture only: it contains no assertion about installed authority.
    original = [f'arn:aws:s3:::{a.p.BACKEND}/e1/lifecycle/dev/{k}/terraform.tfstate' + suffix
                for k in ('global', 'data', 'platform', 'apps', 'edge') for suffix in ('', '.tflock')]
    return {'Version': '2012-10-17', 'Statement': [
        {'Sid': 'Unrelated', 'Effect': 'Deny', 'Action': 's3:DeleteBucket', 'Resource': '*', 'Principal': '*'},
        {'Sid': 'E16NoOtherDevObjects', 'Effect': 'Deny', 'Principal': '*',
         'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'], 'NotResource': original,
         'Condition': {'ArnEquals': {'aws:PrincipalArn': a.OPERATOR}}}]}


class AuthorizationScopeTests(unittest.TestCase):
    def test_exact_two_objects_and_reversible_edit(self):
        before = example_backend()
        after = a.backend_edit(before)
        self.assertEqual(a.backend_edit(after, restore=True), before)
        self.assertEqual(after['Statement'][0], before['Statement'][0])
        self.assertEqual(after['Statement'][1]['Effect'], 'Deny')
        added = set(after['Statement'][1]['NotResource']) - set(before['Statement'][1]['NotResource'])
        base = f'arn:aws:s3:::{a.p.BACKEND}/e1/lifecycle/dev/recovery/{a.TRIAL}/terraform.tfstate'
        self.assertEqual(added, {base, base + '.tflock'})
        self.assertEqual(before, example_backend())

    def test_backend_rejects_wildcard_prefix_lookalike_lock_or_unknown_objects(self):
        for suffix in ('*', '../bad', a.TRIAL + 'x', 'terraform.tfstate.lock', 'terraform.tfstate.tflock/*'):
            with self.subTest(suffix=suffix):
                doc = example_backend()
                doc['Statement'][1]['NotResource'].append(f'arn:aws:s3:::{a.p.BACKEND}/e1/lifecycle/dev/recovery/{suffix}')
                with self.assertRaisesRegex(ValueError, 'BACKEND_EXCEPTION_CHANGED'):
                    a.backend_edit(doc)

    def test_backend_rejects_double_install_or_partial_restore(self):
        doc = a.backend_edit(example_backend())
        with self.assertRaises(ValueError):
            a.backend_edit(doc)
        doc['Statement'][1]['NotResource'].pop()
        with self.assertRaises(ValueError):
            a.backend_edit(doc, restore=True)

    def test_backend_rejects_duplicate_sid_or_object(self):
        doc = example_backend()
        doc['Statement'].append(deepcopy(doc['Statement'][1]))
        with self.assertRaisesRegex(ValueError, 'BACKEND_SID_NOT_UNIQUE'):
            a.backend_edit(doc)
        doc = example_backend()
        doc['Statement'][1]['NotResource'].append(doc['Statement'][1]['NotResource'][0])
        with self.assertRaises(ValueError):
            a.backend_edit(doc)

    def test_backend_guard_cannot_change_principal_effect_actions_or_condition(self):
        for field, value in [('Effect', 'Allow'), ('Principal', a.HUMAN), ('Action', ['s3:*']), ('Condition', {})]:
            doc = example_backend()
            doc['Statement'][1][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'BACKEND_GUARD_CHANGED'):
                a.backend_edit(doc)

    def test_no_state_delete_only_exact_native_lock_delete(self):
        s = a.p.backend_policy(a.TRIAL)['IdentityPolicyAddition']['Statement']
        self.assertNotIn('s3:DeleteObject', s[0]['Action'])
        self.assertEqual(s[1]['Resource'], s[0]['Resource'] + '.tflock')
        self.assertEqual(s[2]['Condition']['StringLike']['s3:prefix'], [f'e1/lifecycle/dev/recovery/{a.TRIAL}/*'])

    def test_launch_type_ami_profile_imds_and_disks_are_bound(self):
        s = {x.get('Sid'): x for x in a.operator_policy()['Statement']}
        c = s['LaunchHost']['Condition']['StringEquals']
        self.assertEqual(c['ec2:InstanceType'], 't3.medium')
        self.assertEqual(c['ec2:MetadataHttpTokens'], 'required')
        self.assertEqual(c['ec2:InstanceProfile'], a.p.PROFILE)
        self.assertEqual(c['ec2:AvailabilityZone'], ['us-east-1a', 'us-east-1b'])
        self.assertEqual(s['LaunchAmi']['Resource'], [f'arn:aws:ec2:{a.p.REGION}::image/{a.AMI}'])
        v = s['LaunchRootVolume']['Condition']
        self.assertEqual(v['Bool'], {'ec2:Encrypted': 'true'})
        self.assertEqual(v['NumericEquals'], {'ec2:VolumeSize': 30})
        self.assertEqual(v['StringEquals']['ec2:VolumeType'], 'gp3')
        self.assertEqual(s['LaunchIncidentalEni']['Condition']['Bool'], {'ec2:AssociatePublicIpAddress': 'false'})

    def test_all_three_tags_on_new_and_existing_and_ssm_targets(self):
        s = {x.get('Sid'): x for x in a.operator_policy()['Statement']}
        for sid in ['CreateVpc', 'CreateInternetGateway', 'CreateSubnet', 'CreateRouteTable', 'AllocateAddress',
                    'CreateSecurityGroup', 'CreateNatGateway', 'CreateVpcEndpoint', 'LaunchHost', 'LaunchRootVolume']:
            for k, v in a.TAGS.items():
                self.assertEqual(s[sid]['Condition']['StringEquals']['aws:RequestTag/' + k], v)
        for k, v in a.TAGS.items():
            self.assertEqual(s['OwnedNetworkAndRetirement']['Condition']['StringEquals']['aws:ResourceTag/' + k], v)
            self.assertEqual(s['HostCommand']['Condition']['StringEquals']['ssm:resourceTag/' + k], v)
        self.assertEqual(s['TagOnlyDuringCreation']['Condition']['StringEquals']['ec2:CreateAction'],
                         ['CreateVpc', 'CreateInternetGateway', 'CreateSubnet', 'CreateRouteTable', 'AllocateAddress',
                          'CreateSecurityGroup', 'CreateNatGateway', 'CreateVpcEndpoint', 'RunInstances'])

    def test_companion_resources_and_forbidden_actions(self):
        policy = a.operator_policy()
        s = next(x for x in policy['Statement'] if x.get('Sid') == 'OwnedNetworkAndRetirement')
        self.assertTrue({'ec2:DetachInternetGateway', 'ec2:DisassociateRouteTable'} <= set(s['Action']))
        self.assertTrue({a.EC2 + k + '/*' for k in ['vpc', 'internet-gateway', 'route-table', 'subnet']} <= set(s['Resource']))
        actions = {v for x in policy['Statement'] for v in (x['Action'] if isinstance(x['Action'], list) else [x['Action']])}
        self.assertFalse(actions & {'ec2:DeleteVolume', 'ec2:DisassociateAddress', 'ec2:DeleteTags',
                                   'ec2:AuthorizeSecurityGroupIngress', 'iam:PutRolePolicy', 's3:PutBucketPolicy'})
        self.assertFalse(any('*' in action for action in actions))
        self.assertLessEqual(len(json.dumps(policy, separators=(',', ':'))), 10240)

    def test_wildcard_resources_are_only_regional_read_receipts(self):
        wildcard = [s for s in a.operator_policy()['Statement'] if s['Resource'] == ['*']]
        self.assertEqual({s['Sid'] for s in wildcard}, {'MissingProviderReads', 'CommandReceipts'})
        for s in wildcard:
            self.assertEqual(s['Condition']['StringEquals']['aws:RequestedRegion'], a.p.REGION)

    def test_artifact_publisher_context_is_exact_not_database_prefix(self):
        s = a.p.publisher_policy(a.TRIAL, a.SHA)['BackupKeyStatementAddition']
        ctx = s['Condition']['StringEquals']['kms:EncryptionContext:aws:s3:arn']
        self.assertNotIn('*', ctx)
        self.assertTrue(ctx.endswith('/artifacts/' + a.SHA + '/recovery.tar'))
        self.assertEqual(s['Principal'], {'AWS': a.HUMAN})

    def test_same_operator_hourly_refresh_and_default_workspace(self):
        c = a.configuration()
        role = c['provider_override.tf.json']['provider']['aws']['assume_role'][0]
        self.assertEqual(role, c['backend-config']['assume_role'])
        self.assertEqual(role, {'role_arn': a.OPERATOR, 'session_name': a.TRIAL, 'duration': '1h'})
        self.assertEqual(c['Workspace'], 'default')
        self.assertTrue(c['backend-config']['use_lockfile'])
        self.assertFalse(c['CredentialsPersisted'])
        for forbidden in ['access_key', 'secret_key', 'token', 'credential_process', 'skip_credentials_validation']:
            self.assertNotIn(forbidden, json.dumps(c))

    def test_override_tags_root_volumes_at_launch_not_post_creation(self):
        c = a.configuration()['provider_override.tf.json']['resource']['aws_instance']
        self.assertEqual(set(c), {'a', 'b'})
        for host in c.values():
            self.assertEqual(host['volume_tags'], a.TAGS)
            self.assertEqual(host['root_block_device'], [{'volume_size': 30, 'volume_type': 'gp3',
                'encrypted': True, 'delete_on_termination': True}])
            self.assertNotIn('tags', host['root_block_device'][0])


if __name__ == '__main__':
    unittest.main()
