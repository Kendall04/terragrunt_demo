"""Synthetic metadata only. Never AWS, SQL or actual fencing acceptance."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import prepare


def deny_external(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn'):
        raise AssertionError('OFFLINE_TEST_EXTERNAL_EFFECT_DENIED')

sys.addaudithook(deny_external)


def fixture(mode='CROSS_AZ'):
    source = {'accountId': prepare.ACCOUNT, 'region': prepare.REGION,
              'instanceId': 'i-' + '1' * 17, 'availabilityZone': 'us-east-1a'}
    request = {'Trial': 'r20261024cold', 'Mode': mode,
               'TargetAz': 'us-east-1a' if mode == 'SAME_AZ' else 'us-east-1b',
               'RecoveryRequestedUtc': '2026-10-24T12:00:00Z', 'NowUtc': '2026-10-24T12:10:00Z',
               'SqlAmiId': 'ami-'+'3'*17, 'MaxBackupAgeSeconds': 7200, 'ArtifactSha256': 'a' * 64,
               'SourceRecord': {'Trial': 'r20261023az6', 'Status': 'SOURCE_BACKED_UP', 'Source': source,
                   'Receipt': {'ManifestKey': prepare.BASE + '/r20261023az6/runs/' + 'b'*32 + '/manifest.json',
                               'ManifestVersion': 'fixture-manifest-v1', 'Manifest': {
                                   'StartedUtc': '2026-10-24T11:55:00Z', 'CompletedUtc': '2026-10-24T11:56:00Z',
                                   'NativeChecksumVerified': True, 'BackupVersion': 'fixture-backup-v1'}}}}
    evidence = {'RequestSha256': hashlib.sha256(prepare.encoded(request)).hexdigest(),
                'ManifestVersion': 'fixture-manifest-v1', 'BackupVersion': 'fixture-backup-v1',
                'Fence': {'Source': source, 'State': 'terminated', 'ConfirmedUtc': '2026-10-24T12:01:00Z',
                          'ObservedUtc': '2026-10-24T12:09:30Z', 'WriteProbeUtc': '2026-10-24T12:01:30Z', 'WriteProbe': 'ENDPOINT_UNAVAILABLE',
                          'ExistingConnectionsClosed': True, 'ControlPlaneReceiptSha256': 'c'*64},
                'Target': {'Identity': dict(source, instanceId='i-'+'2'*17, availabilityZone=request['TargetAz']),
                           'CreatedUtc': '2026-10-24T12:02:00Z', 'ArtifactSha256': 'a'*64},
                'RestoreStartedUtc': '2026-10-24T12:04:00Z', 'RestoreVerifiedUtc': '2026-10-24T12:08:00Z',
                'ApiReadyUtc': '2026-10-24T12:09:00Z', 'Checks': dict.fromkeys(
                    ('Checkdb', 'DecryptedPreMarker', 'Read', 'Write', 'EcsConnectionsRenewed', 'DeployedApiReady'), True)}
    return request, evidence


class ColdPathTests(unittest.TestCase):
    def test_modes_one_target_total_clock_and_no_authority(self):
        for mode in ('SAME_AZ', 'CROSS_AZ'):
            request, evidence = fixture(mode)
            plan = prepare.cold_path(request)
            self.assertEqual(plan['TargetCountToCreate'], 1)
            root = plan['TerraformProposal']
            self.assertEqual(list(root['resource']['aws_instance']), ['a'])
            self.assertEqual(root['resource']['aws_instance']['a']['ami'], request['SqlAmiId'])
            self.assertEqual(sum(len(v) for v in root['resource'].values()), 15)
            self.assertEqual(root['variable']['az_a']['default'], request['TargetAz'])
            self.assertNotIn('az_b', json.dumps(root))
            self.assertNotIn('aws_route.b', json.dumps(root))
            result = prepare.cold_path(request, evidence)
            self.assertEqual(result['RtoTotalSeconds'], 540)
            self.assertFalse(result['AllowsCreation'])
            self.assertFalse(result['AllowsActivation'])
            self.assertFalse(result['EvidenceAuthenticated'])

    def test_wrong_az_account_source_or_mode(self):
        for key, value in [('Mode', 'OUTAGE'), ('TargetAz', 'us-east-1a')]:
            r, _ = fixture(); r[key] = value
            with self.assertRaises(ValueError): prepare.cold_path(r)
        r, _ = fixture(); r['SourceRecord']['Source']['accountId'] = '000000000000'
        with self.assertRaises(ValueError): prepare.cold_path(r)

    def test_backup_stale_unverified_wrong_scope_or_unversioned(self):
        for mutation in (
            lambda r: r.update(MaxBackupAgeSeconds=1),
            lambda r: r['SourceRecord']['Receipt']['Manifest'].update(NativeChecksumVerified=False),
            lambda r: r['SourceRecord']['Receipt'].update(ManifestVersion='null'),
            lambda r: r['SourceRecord']['Receipt'].update(ManifestKey='unrelated/manifest.json')):
            r, _ = fixture(); mutation(r)
            with self.assertRaises(ValueError): prepare.cold_path(r)

    def test_unknown_fence_sql_stop_auth_failure_and_stale_evidence_refuse(self):
        for key, value in [('State', 'stopped'), ('State', 'inactive'), ('State', 'unknown'),
                           ('WriteProbe', 'AUTHORIZATION_DENIED'), ('ExistingConnectionsClosed', False),
                           ('ControlPlaneReceiptSha256', '')]:
            r, e = fixture(); e['Fence'][key] = value
            with self.assertRaises(ValueError): prepare.cold_path(r, e)
        r, e = fixture(); r['NowUtc'] = '2026-10-24T12:30:00Z'
        e['RequestSha256'] = hashlib.sha256(prepare.encoded(r)).hexdigest()
        with self.assertRaisesRegex(ValueError, 'TOO_OLD'): prepare.cold_path(r, e)

    def test_wrong_incarnation_versions_hash_or_request_refuse(self):
        for mutation in (
            lambda e: e.update(RequestSha256='f'*64),
            lambda e: e.update(BackupVersion='another'),
            lambda e: e['Target'].update(ArtifactSha256='f'*64),
            lambda e: e['Target']['Identity'].update(instanceId='i-'+'1'*17),
            lambda e: e['Fence']['Source'].update(instanceId='i-'+'9'*17)):
            r, e = fixture(); e = copy.deepcopy(e); mutation(e)
            with self.assertRaises(ValueError): prepare.cold_path(r, e)

    def test_prepared_target_future_events_and_missing_end_to_end_checks_refuse(self):
        for mutation in (
            lambda e: e['Target'].update(CreatedUtc='2026-10-24T11:59:00Z'),
            lambda e: e.update(ApiReadyUtc='2026-10-24T12:11:00Z'),
            lambda e: e['Checks'].update(Checkdb=False),
            lambda e: e['Checks'].update(DecryptedPreMarker=False),
            lambda e: e['Checks'].pop('DeployedApiReady')):
            r, e = fixture(); mutation(e)
            with self.assertRaises(ValueError): prepare.cold_path(r, e)

    def test_cli_emits_only_an_offline_plan(self):
        request, _ = fixture()
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'request.json'; path.write_text(json.dumps(request), encoding='utf-8')
            with patch.object(sys, 'argv', ['prepare.py', 'cold-plan', '--trial', request['Trial'], '--input', str(path)]), \
                 redirect_stdout(io.StringIO()) as out:
                prepare.main()
            self.assertEqual(json.loads(out.getvalue())['Status'], 'COLD_PATH_OFFLINE_PLAN')


if __name__ == '__main__':
    unittest.main()
