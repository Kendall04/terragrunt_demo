"""Hermetic contract regressions. Fixtures are not Terraform or AWS acceptance."""
import copy
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from contextlib import redirect_stdout

import prepare
import host
import bundle


def deny_external(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.spawn'):
        raise AssertionError('OFFLINE_TEST_EXTERNAL_EFFECT_DENIED')


sys.addaudithook(deny_external)
NAME = 'r20261021test'
BOOT = Path(__file__).with_name('bootstrap.sh').read_text()
ROOT, SECURITY = prepare.render(NAME, BOOT)
IDENTITY = {'accountId': prepare.ACCOUNT, 'region': prepare.REGION, 'instanceId': 'i-11111111111111111', 'availabilityZone': 'us-east-1a'}
TARGET = dict(IDENTITY, instanceId='i-22222222222222222', availabilityZone='us-east-1b')


def plan(action='create'):
    result = {'complete': True, 'resource_changes': [
        {'address': kind + '.' + name, 'mode': 'managed', 'type': kind, 'name': name,
         'change': {'actions': [action], 'after': copy.deepcopy(value)}}
        for kind, items in ROOT['resource'].items() for name, value in items.items()]}
    if action == 'create':
        for change in result['resource_changes']:
            if change['type'] == 'aws_instance':
                after = change['change']['after']
                after['volume_tags'] = after['root_block_device'][0].pop('tags')
    return result


def state():
    prefixes = {'aws_vpc': 'vpc-', 'aws_internet_gateway': 'igw-', 'aws_subnet': 'subnet-',
                'aws_route_table': 'rtb-', 'aws_eip': 'eipalloc-', 'aws_nat_gateway': 'nat-',
                'aws_security_group': 'sg-', 'aws_vpc_endpoint': 'vpce-', 'aws_instance': 'i-'}
    return {'resources': [{'type': kind, 'mode': 'managed', 'instances': [
        {'attributes': {'id': prefixes[kind] + f'{i:017x}', 'tags': {'Trial': NAME}}}
        for i, name in enumerate(items, 1)]} for kind, items in ROOT['resource'].items() if kind in prefixes]}


class FakePort:
    def __init__(self):
        self.rows = []
        self.commands = []
        self.restoring = False
        self.ready = True

    def secret(self, arn):
        return 'Synthetic!not-a-real-password'

    def sql(self, password, statement):
        self.commands.append(statement)
        return ''

    @contextmanager
    def api(self, executable, password, database, migrate):
        self.commands.append(('api', database, migrate))
        yield

    def http(self, method, route, body=None):
        if method == 'POST':
            row = {'id': len(self.rows) + 1, 'text': body['text']}
            self.rows.append(row)
            return row
        return self.rows

    def backup(self, executable, config, password, restore=None):
        if restore:
            self.rows = [{'id': restore['PreMarkerId'], 'text': restore['PreMarker']}]
            return {'Status': 'RESTORED_CHECKDB_READABLE', 'Rows': 1}
        now = host.utc()
        return {'Status': 'REMOTE_VERIFIED', 'Receipt': {
            'ManifestKey': prepare.BASE + '/' + NAME + '/runs/' + 'a' * 32 + '/manifest.json',
            'ManifestVersion': 'synthetic-manifest-version',
            'Manifest': {'StartedUtc': now, 'CompletedUtc': host.utc(), 'NativeChecksumVerified': True,
                         'BackupVersion': 'synthetic-backup-version'}}}

    def run(self, args, **kwargs):
        self.commands.append(args)
        return 'inactive\n'


class BlueprintTests(unittest.TestCase):
    def test_inventory_has_no_legacy_runtime(self):
        self.assertEqual(sum(map(len, ROOT['resource'].values())), 20)
        self.assertEqual(set(ROOT['resource']), {'aws_vpc', 'aws_internet_gateway', 'aws_subnet', 'aws_route_table',
            'aws_route_table_association', 'aws_eip', 'aws_nat_gateway', 'aws_route', 'aws_security_group', 'aws_vpc_endpoint', 'aws_instance'})
        self.assertFalse(SECURITY['AllowsCreation'])

    def test_source_target_privacy_and_disk_retirement(self):
        for value in ROOT['resource']['aws_instance'].values():
            self.assertFalse(value['associate_public_ip_address'])
            self.assertTrue(value['root_block_device'][0]['encrypted'])
            self.assertTrue(value['root_block_device'][0]['delete_on_termination'])
            self.assertEqual(value['metadata_options'][0]['http_tokens'], 'required')
            self.assertEqual(value['credit_specification'][0]['cpu_credits'], 'standard')
        self.assertEqual(ROOT['resource']['aws_security_group']['host']['ingress'], [])

    def test_azs_backend_and_bootstrap_are_bounded(self):
        self.assertIn('var.az_b != var.az_a', json.dumps(ROOT['variable']))
        self.assertNotIn('default', ROOT['variable']['sql_ami_id'])
        self.assertEqual(ROOT['terraform']['backend'], {'s3': {}})
        self.assertIn("for attempt in $(seq 1 90)", BOOT)
        self.assertNotIn('CREATE DATABASE', BOOT)
        self.assertNotIn('set -x', BOOT)

    def test_prefix_security_and_no_old_secret_writes(self):
        statements = SECURITY['RoleInlineAddition']['Statement']
        self.assertEqual(statements[0]['Resource'], f'arn:aws:s3:::{prepare.BUCKET}/{prepare.BASE}/{NAME}/*')
        self.assertEqual(statements[2]['Resource'], prepare.TEXT_KEY)
        self.assertEqual(SECURITY['BackupKeyStatementAddition']['Principal']['AWS'], prepare.ROLE)
        self.assertNotIn('DeleteObject', json.dumps(SECURITY))
        self.assertNotIn('PutSecretValue', json.dumps(SECURITY))

    def test_bad_trial_is_rejected(self):
        for value in ('../old', 'r20261021*', 'r20261021/escape', ''):
            with self.assertRaises(ValueError):
                prepare.render(value, BOOT)

    def test_publish_scope_is_exact_artifact_only(self):
        p = prepare.publisher_policy(NAME, 'a' * 64)
        resources = p['IdentityPolicyAddition']['Statement']
        self.assertNotIn('*', resources[0]['Resource'])
        context = resources[1]['Condition']['StringEquals']['kms:EncryptionContext:aws:s3:arn']
        self.assertTrue(context.endswith('/recovery.tar'))
        self.assertNotIn('/runs/', context)

    def test_backend_permissions_cannot_delete_state_or_touch_original_states(self):
        statements = prepare.backend_policy(NAME)['IdentityPolicyAddition']['Statement']
        self.assertEqual(statements[0]['Action'], ['s3:GetObject', 's3:PutObject'])
        self.assertTrue(statements[1]['Resource'].endswith(NAME + '/terraform.tfstate.tflock'))
        self.assertNotIn('/global/', json.dumps(statements))
        self.assertNotIn('/data/', json.dumps(statements))

    def test_create_delete_review_does_not_authorize(self):
        for action in ('create', 'delete'):
            self.assertFalse(prepare.review_plan(plan(action), ROOT, action)['AllowsCreation'])

    def test_reject_replacement_foreign_and_incomplete_plans(self):
        for change in ('replacement', 'foreign', 'missing', 'drift', 'deferred'):
            value = plan()
            if change == 'replacement':
                value['resource_changes'][0]['change']['actions'] = ['delete', 'create']
            elif change == 'foreign':
                value['resource_changes'][0]['address'] = 'aws_db_instance.foreign'
            elif change == 'missing':
                value['resource_changes'].pop()
            elif change == 'drift':
                value['resource_drift'] = [{}]
            else:
                value['complete'] = False
            with self.assertRaises(ValueError):
                prepare.review_plan(value, ROOT, 'create')

    def test_reject_public_unencrypted_and_widened_egress(self):
        for field, value in [('associate_public_ip_address', True), ('root_block_device', [{'encrypted': False}])]:
            p = plan()
            next(c for c in p['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after'][field] = value
            with self.assertRaises(ValueError):
                prepare.review_plan(p, ROOT, 'create')
        p = plan()
        next(c for c in p['resource_changes'] if c['type'] == 'aws_security_group')['change']['after']['egress'][0]['ipv6_cidr_blocks'] = ['::/0']
        with self.assertRaises(ValueError):
            prepare.review_plan(p, ROOT, 'create')

    def test_effective_volume_tags_accept_only_absent_null_or_empty_nested_tags(self):
        for left in ('absent', 'null', 'empty'):
            for right in ('absent', 'null', 'empty'):
                value = plan()
                hosts = [c['change']['after'] for c in value['resource_changes'] if c['type'] == 'aws_instance']
                for host, representation in zip(hosts, (left, right)):
                    if representation != 'absent':
                        host['root_block_device'][0]['tags'] = None if representation == 'null' else {}
                with self.subTest(left=left, right=right):
                    result = prepare.review_plan(value, ROOT, 'create')
                    self.assertFalse(result['AllowsCreation'])
                    self.assertFalse(result['LiveAuthorizationProven'])

    def test_effective_volume_tags_reject_missing_wrong_extra_or_malformed_tags(self):
        wanted = ROOT['resource']['aws_instance']['a']['root_block_device'][0]['tags']
        for tags in (None, {}, dict(wanted, Trial='r20261021foreign'), dict(wanted, Extra='unexpected'),
                     {k: v for k, v in wanted.items() if k != 'Purpose'}, [], 'invalid'):
            value = plan()
            host = next(c for c in value['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after']
            host['volume_tags'] = tags
            with self.subTest(tags=tags), self.assertRaisesRegex(ValueError, '^PLAN_HOST_CONTROL_CHANGED$'):
                prepare.review_plan(value, ROOT, 'create')
        value = plan()
        del next(c for c in value['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after']['volume_tags']
        with self.assertRaisesRegex(ValueError, '^PLAN_HOST_CONTROL_CHANGED$'):
            prepare.review_plan(value, ROOT, 'create')

    def test_effective_volume_tags_reject_nonempty_or_malformed_nested_tags(self):
        wanted = ROOT['resource']['aws_instance']['a']['root_block_device'][0]['tags']
        for tags in (wanted, dict(wanted, Extra='unexpected'), {'Trial': 'foreign'}, [], 'invalid', False, 0):
            value = plan()
            host = next(c for c in value['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after']
            host['root_block_device'][0]['tags'] = copy.deepcopy(tags)
            with self.subTest(tags=tags), self.assertRaisesRegex(ValueError, '^PLAN_HOST_CONTROL_CHANGED$'):
                prepare.review_plan(value, ROOT, 'create')

    def test_effective_tag_normalization_preserves_all_host_controls(self):
        cases = [('root_block_device', 'encrypted', False), ('root_block_device', 'volume_size', 31),
                 ('root_block_device', 'volume_type', 'gp2'), ('root_block_device', 'delete_on_termination', False),
                 ('metadata_options', 'http_tokens', 'optional'), ('credit_specification', 'cpu_credits', 'unlimited')]
        for field, key, replacement in cases:
            value = plan()
            host = next(c for c in value['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after']
            host[field][0][key] = replacement
            with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                prepare.review_plan(value, ROOT, 'create')
        for field, replacement in [('instance_type', 't3.large'), ('associate_public_ip_address', True),
                                   ('iam_instance_profile', 'foreign-profile'), ('tags', {'Trial': 'foreign'})]:
            value = plan()
            next(c for c in value['resource_changes'] if c['address'] == 'aws_instance.a')['change']['after'][field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare.review_plan(value, ROOT, 'create')

    def test_authorization_override_integrates_with_review_create_cli_offline(self):
        # Faithful provider *tag-map shapes*, not an evaluated Terraform/AWS plan.
        import authorization
        original, _ = prepare.render(authorization.TRIAL, BOOT)
        effective = copy.deepcopy(original)
        for name, replacement in authorization.configuration()['provider_override.tf.json']['resource']['aws_instance'].items():
            effective['resource']['aws_instance'][name].update(copy.deepcopy(replacement))
        for representation in ('absent', 'null', 'empty'):
            value = {'complete': True, 'resource_changes': [
                {'address': kind + '.' + name, 'mode': 'managed', 'type': kind, 'name': name,
                 'change': {'actions': ['create'], 'after': copy.deepcopy(config)}}
                for kind, items in effective['resource'].items() for name, config in items.items()]}
            for change in value['resource_changes']:
                if change['type'] == 'aws_instance' and representation != 'absent':
                    change['change']['after']['root_block_device'][0]['tags'] = None if representation == 'null' else {}
            with self.subTest(representation=representation), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'structural-plan.json'
                path.write_text(json.dumps(value))
                stream = io.StringIO()
                args = ['prepare.py', 'review-create', '--trial', authorization.TRIAL, '--input', str(path)]
                with patch.object(sys, 'argv', args), redirect_stdout(stream):
                    prepare.main()
                result = json.loads(stream.getvalue())
                self.assertEqual(result['Objects'], 20)
                self.assertFalse(result['AllowsCreation'])
                self.assertFalse(result['LiveAuthorizationProven'])

    def test_retirement_includes_companion_resources(self):
        policy = prepare.retirement_policy(state(), NAME)
        statements = {s['Action']: s for s in policy['Statement']}
        for action, expected in [('ec2:DetachInternetGateway', 2), ('ec2:DisassociateRouteTable', 6)]:
            resources = statements[action]['Resource']
            self.assertEqual(len(resources), expected)
            self.assertTrue(all('*' not in r and prepare.ACCOUNT in r and prepare.REGION in r for r in resources))
        self.assertNotIn('ec2:DeleteVolume', statements)
        self.assertNotIn('ec2:DisassociateAddress', statements)

    def test_duplicate_ids_within_each_multi_resource_type_refused(self):
        for kind in ('aws_instance', 'aws_subnet', 'aws_route_table'):
            value = state()
            resource = next(r for r in value['resources'] if r['type'] == kind)
            resource['instances'][1]['attributes']['id'] = resource['instances'][0]['attributes']['id']
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, '^DUPLICATE_RESOURCE_ID$'):
                prepare.retirement_policy(value, NAME)

    def test_duplicate_id_alias_across_state_blocks_refused(self):
        for kind in ('aws_instance', 'aws_subnet', 'aws_route_table'):
            value = state()
            resource = next(r for r in value['resources'] if r['type'] == kind)
            resource['instances'].pop()
            alias = copy.deepcopy(resource)
            alias['name'] = 'imported_alias'
            alias['instances'] = [copy.deepcopy(resource['instances'][0])]
            value['resources'].append(alias)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, '^DUPLICATE_RESOURCE_ID$'):
                prepare.retirement_policy(value, NAME)

    def test_missing_second_host_refused_and_distinct_hosts_bound(self):
        value = state()
        resource = next(r for r in value['resources'] if r['type'] == 'aws_instance')
        resource['instances'].pop()
        with self.assertRaisesRegex(ValueError, '^INCOMPLETE_RUNTIME_INVENTORY$'):
            prepare.retirement_policy(value, NAME)
        value = state()
        policy = prepare.retirement_policy(value, NAME)
        statement = next(s for s in policy['Statement'] if s['Action'] == 'ec2:TerminateInstances')
        expected = {f"arn:aws:ec2:{prepare.REGION}:{prepare.ACCOUNT}:instance/" + i['attributes']['id']
                    for r in value['resources'] if r['type'] == 'aws_instance' for i in r['instances']}
        self.assertEqual(len(expected), 2)
        self.assertEqual(len(statement['Resource']), 2)
        self.assertEqual(set(statement['Resource']), expected)

    def test_foreign_partial_retirement_state_refused(self):
        for modify in ('foreign', 'partial', 'deposed'):
            value = state()
            if modify == 'foreign':
                value['resources'][0]['instances'][0]['attributes']['tags']['Trial'] = 'other'
            elif modify == 'partial':
                value['resources'].pop()
            else:
                value['resources'][0]['instances'][0]['deposed'] = 'old'
            with self.assertRaises(ValueError):
                prepare.retirement_policy(value, NAME)

    def test_fixed_window(self):
        result = prepare.timeline('2026-10-21T20:00:00Z')
        self.assertEqual(result['RetireNoLaterThanUtc'], '2026-10-21T22:30:00+00:00')
        self.assertEqual(result['AbsoluteDeadlineUtc'], '2026-10-22T00:00:00+00:00')
        self.assertFalse(result['AutomaticShutdown'])
        with self.assertRaises(ValueError):
            prepare.timeline('2026-10-21T20:00:00')


class HostTests(unittest.TestCase):
    def test_dependency_denial_is_never_readiness_polled(self):
        port = host.Port()
        process = Mock(pid=123, poll=Mock(return_value=None))
        port.http = Mock(side_effect=[{'status': 'Healthy'}, host.urllib.error.HTTPError('http://127.0.0.1', 503, 'fixture', {}, None)])
        with patch.object(host.subprocess, 'Popen', return_value=process), patch.object(host.os, 'killpg', create=True):
            with self.assertRaisesRegex(ValueError, 'API_DEPENDENCY_FAILURE_REVIEW'):
                with port.api(Path('/fixture/api'), 'Synthetic!password', 'fixture', False):
                    self.fail('dependency denial must not yield')
        self.assertEqual(port.http.call_count, 2)
        self.assertEqual(port.http.call_args_list[0].args, ('GET', '/health'))
        self.assertEqual(port.http.call_args_list[1].args, ('GET', '/ready'))

    def test_default_command_has_no_host_or_cloud_effects(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['host.py', 'source', '--trial', NAME, '--directory', '/does-not-exist']), redirect_stdout(output):
            host.main()
        self.assertFalse(json.loads(output.getvalue())['ReadsSecrets'])

    def test_host_requires_exact_operator_bound_identity(self):
        host.bind_identity(IDENTITY, IDENTITY['instanceId'], IDENTITY['availabilityZone'])
        for value in (TARGET, dict(IDENTITY, accountId='000000000000')):
            with self.assertRaises(ValueError):
                host.bind_identity(value, IDENTITY['instanceId'], IDENTITY['availabilityZone'])

    def records(self):
        port = FakePort()
        source = host.source(port, NAME, Path('/fixture/config'), Path('/fixture/backup'), Path('/fixture/api'), IDENTITY)
        failure = host.quiesce(port, source, IDENTITY)
        return port, source, failure

    def test_full_fake_flow_is_only_contract_evidence(self):
        p, s, f = self.records()
        result = host.restore(p, NAME, None, None, None, TARGET, s, f)
        self.assertEqual(result['Status'], 'TARGET_RECOVERED_REVIEW_EVIDENCE')
        self.assertFalse(result['CloudLifecycleClosed'])
        self.assertFalse(result['FullEcsRecoveryProven'])
        self.assertGreaterEqual(result['RtoWarmTargetSeconds'], 0)
        self.assertNotIn('Synthetic!not-a-real-password', json.dumps(result))

    def test_same_host_az_active_source_and_bad_order_refused(self):
        for case in ('host', 'az', 'active', 'order', 'prefix'):
            p, s, f = self.records()
            target = dict(TARGET)
            if case == 'host':
                target['instanceId'] = IDENTITY['instanceId']
            elif case == 'az':
                target['availabilityZone'] = IDENTITY['availabilityZone']
            elif case == 'active':
                f['ActiveState'] = 'active'
            elif case == 'order':
                f['FailureDeclaredUtc'] = '2000-01-01T00:00:00Z'
            else:
                s['Receipt']['ManifestKey'] = 'another-prefix/manifest.json'
            with self.assertRaises(ValueError):
                host.restore(p, NAME, None, None, None, target, s, f)

    def test_missing_decrypt_marker_and_unexpected_post_marker_fail(self):
        for case in ('missing', 'post'):
            p, s, f = self.records()
            original = p.http
            def http(method, route, body=None):
                if method == 'GET':
                    return [] if case == 'missing' else [{'id': s['PreMarkerId'], 'text': s['PreMarker']}, {'id': 2, 'text': s['PostMarker']}]
                return original(method, route, body)
            p.http = http
            with self.assertRaises(ValueError):
                host.restore(p, NAME, None, None, None, TARGET, s, f)

    def test_connection_escapes_password_and_config_stays_public(self):
        self.assertIn('Password="a;""b";', host.connection('sa', 'a;"b', 'master'))
        self.assertNotIn('password', json.dumps(host.options(NAME)).lower())


class BundleTests(unittest.TestCase):
    def publish(self, root, name, web=False):
        root.mkdir()
        (root / name).write_bytes(b'fixture-linux-binary')
        (root / 'libcoreclr.so').write_bytes(b'fixture-runtime')
        frameworks = [{'name': 'Microsoft.NETCore.App', 'version': '10.0.13'}]
        if web:
            frameworks.append({'name': 'Microsoft.AspNetCore.App', 'version': '10.0.13'})
        (root / (name + '.runtimeconfig.json')).write_text(json.dumps({'runtimeOptions': {'includedFrameworks': frameworks}}))

    def test_deterministic_bundle_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.publish(root / 'api', 'terragrunt-demo', True)
            self.publish(root / 'backup', 'SqlBackup')
            hashes = []
            for i in range(2):
                output = root / f'out{i}.tar'
                result = bundle.build(root / 'api', root / 'backup', output, 'a' * 40)
                hashes.append(result['Sha256'])
                self.assertEqual(bundle.inspect(output, result['Sha256'])['Runtime'], '10.0.13')
            self.assertEqual(hashes[0], hashes[1])
            with self.assertRaises(ValueError):
                bundle.inspect(output, 'b' * 64)

    def test_traversal_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'unsafe.tar'
            with tarfile.open(output, 'w') as archive:
                item = tarfile.TarInfo('../escape')
                item.mode = 0o644
                item.size = 1
                archive.addfile(item, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                bundle.inspect(output, hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
