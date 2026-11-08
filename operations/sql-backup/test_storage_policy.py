import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import storage_policy as p


class StoragePolicy(unittest.TestCase):
    def setUp(self):
        self.old = {'Version': '2012-10-17', 'Statement': [{'Sid': 'Keep', 'Effect': 'Deny'}]}

    def test_delta_preserves_history_and_has_no_delete_or_secret_grants(self):
        before = copy.deepcopy(self.old)
        result = p.prepare(self.old, self.old, 'v2-20261105', 'a' * 64, '2099-11-07T04:00:00Z')
        self.assertEqual(before, self.old)
        for key in ('KeyPolicy', 'BucketPolicy'):
            self.assertEqual(before['Statement'][0], result[key]['Statement'][0])
        self.assertFalse(result['LifecycleChanged'])
        actions = {a for s in result['RolePolicy']['Statement'] for a in
                   (s['Action'] if isinstance(s['Action'], list) else [s['Action']])}
        self.assertEqual(actions, {'s3:PutObject', 's3:GetObject', 's3:GetObjectVersion',
                                   'kms:GenerateDataKey', 'kms:Decrypt'})
        self.assertTrue(all(s['Resource'] != '*' for s in result['RolePolicy']['Statement']))
        self.assertTrue(all('DateLessThan' in s['Condition'] for s in result['RolePolicy']['Statement']))

    def test_scope_and_existing_delta_fail_closed(self):
        for operation in ('prod', 'v2-20261105/../prod', 'v2-*'):
            with self.assertRaises(ValueError):
                p.prepare(self.old, self.old, operation, 'a' * 64, '2099-11-07T04:00:00Z')
        first = p.prepare(self.old, self.old, 'v2-20261105', 'a' * 64, '2099-11-07T04:00:00Z')
        with self.assertRaisesRegex(ValueError, 'EXISTING_DELTA'):
            p.prepare(first['KeyPolicy'], self.old, 'v2-20261105', 'a' * 64, '2099-11-07T04:00:00Z')
