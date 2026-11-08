"""Bounded administrative adapter tests; no credentials or AWS execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'scripts/tests/ownership_publication')]
import publish_dev_neutral as adapter
import ownership
import publication
import test_wp2d


class FakeAWS:
    def __init__(self):
        self.calls, self.versions, self.markers = [], [], []
        self.raw = None
        self.mode = 'ok'

    def call(self, *args):
        self.calls.append(args)
        action = args[1]
        def value(flag):
            return args[args.index(flag) + 1]
        if action == 'get-caller-identity':
            return {'Account': adapter.ACCOUNT, 'Arn': 'wrong' if self.mode == 'identity' else adapter.ADMIN}
        if action == 'get-bucket-location':
            return {'LocationConstraint': None}
        if action == 'get-bucket-policy':
            p = adapter.policy(adapter.BUCKET, adapter.ADMIN)
            if self.mode == 'policy':
                p['Statement'].pop()
            return {'Policy': json.dumps(p)}
        if action == 'get-bucket-versioning':
            return {'Status': 'Enabled'}
        if action == 'get-public-access-block':
            return {'PublicAccessBlockConfiguration': {k: True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')}}
        if action == 'get-bucket-encryption':
            return {'ServerSideEncryptionConfiguration': {'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}, 'BucketKeyEnabled': False}]}}
        if action == 'get-bucket-ownership-controls':
            return {'OwnershipControls': {'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]}}
        if action == 'simulate-principal-policy':
            actions = args[args.index('--action-names') + 1:args.index('--resource-arns')]
            return {'EvaluationResults': [{'EvalActionName': a, 'EvalDecision': 'allowed', 'EvalResourceName': value('--resource-arns')} for a in actions]}
        if action == 'list-object-versions':
            return {'Versions': self.versions, 'DeleteMarkers': self.markers, 'IsTruncated': False}
        if action == 'put-object':
            self.raw = Path(value('--body')).read_bytes()
            self.versions = [{'Key': value('--key'), 'VersionId': 'authentic-version'}]
            if self.mode == 'ambiguous':
                raise OSError('uncertain dispatch')
            return {'VersionId': 'authentic-version'}
        if action == 'get-object':
            if self.mode == 'read':
                raise OSError('read failed')
            path = Path(args[args.index('--version-id') + 2])
            path.write_bytes(self.raw + (b'changed' if self.mode == 'bytes' else b''))
            return {'VersionId': 'wrong-version' if self.mode == 'version' else value('--version-id'), 'ServerSideEncryption': 'AES256'}
        raise AssertionError('Unexpected action: ' + action)


class AdminPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = {'ownership_closure': ownership.catalog()}
        with mock.patch.object(test_wp2d, 'ACCOUNT', adapter.ACCOUNT):
            self.output = test_wp2d.output_fixture(self.doc)
        historical = {k: v for k, v in self.output.items() if v['scope'] == 'dev'}
        self.doc['ownership_closure']['publications'][adapter.ACCOUNT + '/' + adapter.REGION] = {'records': historical}
        records = {k: v for k, v in self.output.items() if v['scope'] == 'dev' or k in publication.NEUTRAL_KEYS}
        self.expected = {'schema': publication.DEV_NEUTRAL_SCHEMA,
                         'authority_digest': ownership.authority_digest(self.doc['ownership_closure']),
                         'account': adapter.ACCOUNT, 'region': adapter.REGION,
                         'records': records, 'publisher': 'SECURITY_ADMIN_EXTERNAL_BOOTSTRAP'}
        self.path = Path(self.tmp.name) / 'synthetic-candidate.json'
        self.raw = (json.dumps(self.expected, indent=2) + '\n').encode()
        self.path.write_bytes(self.raw)
        # Fixture checksum is never a production approval or caller input.
        patch = mock.patch.object(adapter, 'CANDIDATE_SHA256', hashlib.sha256(self.raw).hexdigest())
        patch.start()
        self.addCleanup(patch.stop)
        self.aws = FakeAWS()

    def channel(self, publish=False, output=None):
        return adapter.DevNeutralChannel(self.aws, self.doc, self.path,
                                         output or (lambda: copy.deepcopy(self.output)), publish)

    def test_wrong_identity_stops_before_storage(self):
        self.aws.mode = 'identity'
        with self.assertRaises(ValueError):
            self.channel().preflight()
        self.assertEqual([a[1] for a in self.aws.calls], ['get-caller-identity'])

    def test_prior_version_and_delete_marker_rejected(self):
        channel = self.channel(True)
        for collection in ('versions', 'markers'):
            self.aws.versions, self.aws.markers = [], []
            setattr(self.aws, collection, [{'Key': channel.key, 'VersionId': 'prior'}])
            with self.assertRaises(ValueError):
                channel.preflight()
        self.assertNotIn('put-object', [a[1] for a in self.aws.calls])
        self.aws.versions, self.aws.markers = [], []
        original = self.aws.call
        pages = []
        def paginated(*args):
            if args[1] != 'list-object-versions':
                return original(*args)
            pages.append(args)
            if len(pages) == 1:
                return {'IsTruncated': True, 'NextKeyMarker': channel.key, 'NextVersionIdMarker': 'marker'}
            self.assertIn('--version-id-marker', args)
            return {'IsTruncated': False, 'Versions': [{'Key': channel.key, 'VersionId': 'prior-on-page-two'}]}
        with mock.patch.object(self.aws, 'call', side_effect=paginated):
            with self.assertRaises(ValueError):
                channel.preflight()
        self.assertEqual(len(pages), 2)

    def test_output_failure_scope_and_candidate_drift_rejected(self):
        def failed():
            raise OSError('output read failed')
        with self.assertRaises(OSError):
            self.channel(output=failed).preflight()
        for key, field, value in [('neutral/oidc', 'available', False), ('dev/kms', 'value', 'invented')]:
            altered = copy.deepcopy(self.output)
            altered[key][field] = value
            with self.assertRaises(ValueError):
                self.channel(output=lambda: altered).preflight()
        altered = copy.deepcopy(self.output)
        altered['prod/invented'] = altered['prod/kms']
        with self.assertRaises(ValueError):
            self.channel(output=lambda: altered).preflight()
        self.assertNotIn('put-object', [a[1] for a in self.aws.calls])

    def test_preflight_is_read_only_and_publication_disabled(self):
        channel = self.channel()
        self.assertEqual(channel.preflight()['aws_writes'], 0)
        with self.assertRaises(ValueError):
            publication.publish_outputs(self.doc, adapter.ACCOUNT, adapter.REGION, channel, dev_neutral=True)
        self.assertFalse(channel.put_dispatched)
        self.assertTrue(all(a[1].startswith(('get-', 'list-', 'simulate-')) for a in self.aws.calls))

    def test_single_conditional_put_and_exact_version(self):
        channel = self.channel(True)
        channel.preflight()
        self.assertEqual(publication.publish_outputs(self.doc, adapter.ACCOUNT, adapter.REGION, channel, dev_neutral=True), self.expected)
        puts = [a for a in self.aws.calls if a[1] == 'put-object']
        self.assertEqual(len(puts), 1)
        self.assertEqual(puts[0][puts[0].index('--if-none-match') + 1], '*')
        self.assertEqual(puts[0][puts[0].index('--key') + 1], channel.key)
        self.assertNotIn('--acl', puts[0])
        self.assertEqual(channel.version_id, 'authentic-version')
        self.assertTrue(all(a[a.index('--version-id') + 1] == 'authentic-version' for a in self.aws.calls if a[1] == 'get-object'))

    def test_ambiguous_write_only_reconciles_and_never_retries(self):
        channel = self.channel(True)
        channel.preflight()
        self.aws.mode = 'ambiguous'
        with self.assertRaises(ValueError):
            publication.publish_outputs(self.doc, adapter.ACCOUNT, adapter.REGION, channel, dev_neutral=True)
        self.assertEqual(channel.reconciliation, 'EXACT_VERSION_FOUND_AFTER_FAILED_ATTEMPT')
        with self.assertRaises(ValueError):
            channel.create_publication(channel.key, self.expected)
        self.assertEqual(len([a for a in self.aws.calls if a[1] == 'put-object']), 1)
        dispatched = next(i for i, a in enumerate(self.aws.calls) if a[1] == 'put-object')
        self.assertTrue(all(a[1] in ('list-object-versions', 'get-object') for a in self.aws.calls[dispatched + 1:]))

    def test_failed_read_wrong_version_or_bytes_never_success(self):
        for mode in ('read', 'version', 'bytes'):
            self.aws = FakeAWS()
            channel = self.channel(True)
            channel.preflight()
            self.aws.mode = mode
            with self.assertRaises(ValueError):
                publication.publish_outputs(self.doc, adapter.ACCOUNT, adapter.REGION, channel, dev_neutral=True)
            self.assertEqual(channel.reconciliation, 'UNVERIFIED')
            self.assertEqual(len([a for a in self.aws.calls if a[1] == 'put-object']), 1)

    def test_bucket_runtime_exposure_and_wrong_backend_rejected(self):
        self.aws.mode = 'policy'
        with self.assertRaises(ValueError):
            self.channel().preflight()
        path = Path(self.tmp.name)
        (path / '.terraform').mkdir()
        (path / '.terraform/terraform.tfstate').write_text(json.dumps({'backend': {'type': 's3', 'config': {'bucket': 'other'}}}))
        with self.assertRaises((ValueError, KeyError)):
            adapter.terraform_output(path, {})
        (path / '.terraform/terraform.tfstate').write_text(json.dumps({'backend': {'type': 's3', 'config': {
            'bucket': adapter.BUCKET, 'key': 'e1/security/terraform.tfstate',
            'region': adapter.REGION, 'encrypt': True, 'use_lockfile': True}}}))
        results = [SimpleNamespace(returncode=0, stdout=b'{"terraform_version":"1.13.4"}'),
                   SimpleNamespace(returncode=0, stdout=json.dumps(self.output).encode())]
        with mock.patch.object(adapter.subprocess, 'run', side_effect=results) as run:
            self.assertEqual(adapter.terraform_output(path, {}), self.output)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ['terraform', 'version', '-json'])
        self.assertEqual(commands[1], ['terraform', '-chdir=' + str(path.resolve()), 'output', '-json', 'protected_output_candidates'])
