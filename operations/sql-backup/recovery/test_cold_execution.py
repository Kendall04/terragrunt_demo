"""Synthetic adapters test restore write barriers; no AWS or actual SQL."""
import copy
import json
import unittest
from unittest.mock import patch
import host
import prepare
from test_cold_path import fixture
from test_recovery import FakePort, state


class ColdExecutionTests(unittest.TestCase):
    def native_fixture(self):
        r, e = fixture()
        r['SourceLaunchUtc'] = '2026-10-24T10:00:00Z'
        identity = e['Target']['Identity']
        document = {'Reservations': [{'OwnerId': prepare.ACCOUNT, 'Instances': [
            {'InstanceId': r['SourceRecord']['Source']['instanceId'], 'LaunchTime': r['SourceLaunchUtc'],
             'State': {'Name': 'terminated'}, 'Placement': {'AvailabilityZone': 'us-east-1a'}},
            {'InstanceId': identity['instanceId'], 'LaunchTime': '2026-10-24T12:02:00Z',
             'ImageId': r['SqlAmiId'], 'State': {'Name': 'running'}, 'Placement': {'AvailabilityZone': r['TargetAz']},
             'Tags': [{'Key': 'Trial', 'Value': r['Trial']}]}]}]}
        caller = {'Account': prepare.ACCOUNT, 'Arn': 'arn:aws:sts::'+prepare.ACCOUNT+':assumed-role/'+prepare.ROLE_NAME+'/fixture'}
        return r, identity, document, caller

    def test_native_adapter_exact_reads_and_unknown_results_fail_without_retry(self):
        r, identity, document, caller = self.native_fixture()
        p = host.Port()
        with patch.object(p, 'run', side_effect=[json.dumps(caller), json.dumps(document)]) as run, patch.object(host, 'utc', return_value=r['NowUtc']):
            result = p.confirm_cold_fence(r, identity)
            self.assertEqual(result['Status'], 'EXACT_SOURCE_TERMINATED')
            self.assertEqual(run.call_count, 2)
            command = run.call_args_list[1].args[0]
            self.assertIn(r['SourceRecord']['Source']['instanceId'], command)
            self.assertIn(identity['instanceId'], command)
        for mutation in (
            lambda d: d['Reservations'][0]['Instances'][0]['State'].update(Name='stopped'),
            lambda d: d['Reservations'][0]['Instances'][0].update(LaunchTime='2026-10-24T09:00:00Z'),
            lambda d: d['Reservations'][0]['Instances'][1].update(LaunchTime='2026-10-24T11:00:00Z'),
            lambda d: d['Reservations'][0]['Instances'][1].update(ImageId='ami-'+'f'*17),
            lambda d: d['Reservations'][0].update(OwnerId='000000000000'),
            lambda d: d['Reservations'][0]['Instances'].pop()):
            changed = copy.deepcopy(document); mutation(changed)
            with patch.object(p, 'run', side_effect=[json.dumps(caller), json.dumps(changed)]) as run, patch.object(host, 'utc', return_value=r['NowUtc']):
                with self.assertRaises((ValueError, KeyError)): p.confirm_cold_fence(r, identity)
                self.assertEqual(run.call_count, 2)
        for wrong in ({'Account': '000000000000', 'Arn': caller['Arn']},
                      {'Account': prepare.ACCOUNT, 'Arn': 'arn:aws:iam::'+prepare.ACCOUNT+':user/admin'}):
            with patch.object(p, 'run', return_value=json.dumps(wrong)) as run:
                with self.assertRaisesRegex(ValueError, 'IDENTITY'): p.confirm_cold_fence(r, identity)
                self.assertEqual(run.call_count, 1)
        with patch.object(p, 'run', side_effect=ValueError('CHILD_OUTCOME_UNKNOWN')) as run:
            with self.assertRaises(ValueError): p.confirm_cold_fence(r, identity)
            self.assertEqual(run.call_count, 1)

    def test_restore_rechecks_fence_before_any_write_and_refuses_uncertainty(self):
        for mode in ('SAME_AZ', 'CROSS_AZ'):
            r, e = fixture(mode)
            s = r['SourceRecord']; s.update(PreMarker='fixture-before', PreMarkerId=1, PostMarker='fixture-after', PreMarkerRequestUtc='2026-10-24T11:54:00Z')
            p = FakePort()
            s['RuntimePrecheck'] = host.checked_runtime(p, s['Source'], 'fixture')
            p.confirm_cold_fence = lambda request, identity: {'Status': 'EXACT_SOURCE_TERMINATED'}
            with patch.object(host, 'utc', return_value=r['NowUtc']), patch.object(p, 'confirm_cold_fence', wraps=p.confirm_cold_fence) as fence:
                result = host.restore(p, r['Trial'], None, None, None, e['Target']['Identity'], s, None, r)
                self.assertEqual(result['RecoveryMode'], mode)
                self.assertFalse(result['DeployedEcsApiProven'])
                self.assertIsNone(result['RtoWarmTargetSeconds'])
                self.assertEqual(result['RtoColdHostSeconds'], 600)
                self.assertEqual(fence.call_count, 4)
            for fail_at in (1, 2, 3):
                p = FakePort()
                effects = [{'Status': 'EXACT_SOURCE_TERMINATED'}]*(fail_at-1)+[ValueError('FENCE_UNKNOWN')]
                with patch.object(p, 'confirm_cold_fence', side_effect=effects, create=True), patch.object(host, 'utc', return_value=r['NowUtc']):
                    with self.assertRaisesRegex(ValueError, 'FENCE_UNKNOWN'):
                        host.restore(p, r['Trial'], None, None, None, e['Target']['Identity'], s, None, r)
                self.assertFalse(any(isinstance(c, tuple) and c[0]=='api' for c in p.commands))
                if fail_at <= 2: self.assertFalse(any(isinstance(c, str) and 'CREATE LOGIN' in c for c in p.commands))

    def test_single_target_retirement_rejects_old_or_foreign_state(self):
        snapshot = state()
        for resource in snapshot['resources']:
            count = {'aws_subnet': 2, 'aws_route_table': 2, 'aws_instance': 1}.get(resource['type'])
            if count: resource['instances'] = resource['instances'][:count]
        policy = prepare.retirement_policy(snapshot, 'r20261021test', cold=True)
        terminate = next(s for s in policy['Statement'] if s['Action']=='ec2:TerminateInstances')
        self.assertEqual(len(terminate['Resource']), 1)
        self.assertNotIn('*', terminate['Resource'])
        with self.assertRaises(ValueError): prepare.retirement_policy(state(), 'r20261021test', cold=True)
        snapshot['resources'][0]['instances'][0]['attributes']['tags']['Trial']='another'
        with self.assertRaises(ValueError): prepare.retirement_policy(snapshot, 'r20261021test', cold=True)


if __name__ == '__main__': unittest.main()
