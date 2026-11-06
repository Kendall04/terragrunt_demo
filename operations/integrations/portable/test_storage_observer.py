import copy
import datetime as dt
import hashlib
import io
import json
import unittest
import storage_observer as observer

NOW = dt.datetime(2026, 11, 5, 23, tzinfo=dt.timezone.utc)
CONFIG = {'bucket': 'backup', 'prefix': 'dev/backups', 'database': 'demodb',
          'backupKeyArn': 'backup-key', 'textKeyArn': 'text-key', 'maxBytes': 100,
          'bus': 'existing-bus', 'monitors': [
              {'id': 'sql-backup', 'kind': 'sql-backup', 'resource': 'installed-db', 'generation': 'installed-v1'},
              {'id': 'sql-telemetry', 'kind': 'report', 'resource': 'installed-observer', 'generation': 'installed-v1'}]}
RUN = 'a' * 32
KEY = 'dev/backups/runs/' + RUN + '/manifest.json'
BODY = b'bounded-backup-body'
MANIFEST = {'SchemaVersion': 1, 'Id': RUN, 'Database': 'demodb', 'StartedUtc': NOW.isoformat(),
            'CompletedUtc': NOW.isoformat(), 'SqlVersion': '16.0', 'RecoveryModel': 'FULL',
            'Length': len(BODY), 'Sha256': hashlib.sha256(BODY).hexdigest(), 'NativeChecksumVerified': True,
            'TextKeyArn': 'text-key', 'BackupKey': 'dev/backups/runs/' + RUN + '/database.bak',
            'BackupVersion': 'backup-v1'}


class Store:
    def __init__(self):
        self.manifest = copy.deepcopy(MANIFEST)
        self.body = BODY
        self.missing = self.truncated = False
        self.kms = 'backup-key'
        self.calls = []

    def list_objects_v2(self, **args):
        self.calls.append(args)
        return {'IsTruncated': self.truncated, 'Contents': [] if self.missing else [
            {'Key': KEY, 'LastModified': NOW}]}

    def head_object(self, **args):
        self.calls.append(args)
        return {'ServerSideEncryption': 'aws:kms', 'SSEKMSKeyId': self.kms, 'VersionId': 'manifest-v1',
                'ContentLength': len(json.dumps(self.manifest).encode())}

    def get_object(self, **args):
        self.calls.append(args)
        body = json.dumps(self.manifest).encode() if args['Key'] == KEY else self.body
        return {'ServerSideEncryption': 'aws:kms', 'SSEKMSKeyId': self.kms, 'VersionId': args['VersionId'],
                'ContentLength': len(body), 'Body': io.BytesIO(body)}


class StorageObservationTests(unittest.TestCase):
    def test_exact_version_bytes_key_and_existing_identity(self):
        store = Store()
        result = observer.inspect(store, CONFIG, NOW)
        self.assertEqual(result['sha256'], hashlib.sha256(BODY).hexdigest())
        gets = [x for x in store.calls if 'VersionId' in x]
        self.assertEqual([x['VersionId'] for x in gets], ['manifest-v1', 'backup-v1'])
        entries = observer.reports(CONFIG, result, NOW, 'scheduled-1')
        report = json.loads(entries[0]['Detail'])
        self.assertEqual((report['verdict'], report['assurance']), ('Pass', 'Artifact'))
        self.assertEqual((report['resource'], report['generation']), ('installed-db', 'installed-v1'))
        self.assertEqual(entries, observer.reports(CONFIG, result, NOW, 'scheduled-1'))

    def test_missing_truncated_wrong_key_and_corrupt_bytes_fail_closed(self):
        for field, value, code in [('missing', True, 'BACKUP_MISSING'),
                                  ('truncated', True, 'LIST_BOUND_EXCEEDED'),
                                  ('kms', 'other-key', 'WRONG_ENCRYPTION'),
                                  ('body', b'x' * len(BODY), 'BACKUP_HASH')]:
            with self.subTest(code=code):
                store = Store()
                setattr(store, field, value)
                with self.assertRaisesRegex(observer.Unverified, code):
                    observer.inspect(store, CONFIG, NOW)

    def test_manifest_scope_checksum_receipt_and_size_are_required(self):
        for field, value in [('Database', 'prod'), ('BackupKey', 'unrelated/object'),
                             ('NativeChecksumVerified', False), ('BackupVersion', 'null'),
                             ('TextKeyArn', 'different-key'), ('Length', 101), ('Unexpected', True)]:
            with self.subTest(field=field):
                store = Store()
                store.manifest[field] = value
                with self.assertRaises(observer.Unverified):
                    observer.inspect(store, CONFIG, NOW)

    def test_old_backup_keeps_original_data_time_for_freshness_engine(self):
        store = Store()
        old = (NOW - dt.timedelta(hours=4)).isoformat()
        store.manifest.update(StartedUtc=old, CompletedUtc=old)
        result = observer.inspect(store, CONFIG, NOW)
        report = json.loads(observer.reports(CONFIG, result, NOW, 'scheduled-1')[0]['Detail'])
        self.assertEqual(report['dataAt'], old)
        self.assertNotEqual(report['dataAt'], report['observedAt'])

    def test_unavailable_is_never_artifact_success(self):
        report = json.loads(observer.reports(CONFIG, {'code': 'STORAGE_CHECK_UNAVAILABLE'}, NOW, '1')[0]['Detail'])
        self.assertEqual((report['verdict'], report['assurance']), ('Unknown', 'Reported'))

    def test_future_clock_and_duplicate_json_fail(self):
        store = Store()
        store.manifest['CompletedUtc'] = (NOW + dt.timedelta(minutes=6)).isoformat()
        with self.assertRaisesRegex(observer.Unverified, 'BACKUP_TIME'):
            observer.inspect(store, CONFIG, NOW)
        with self.assertRaisesRegex(observer.Unverified, 'DUPLICATE_FIELD'):
            observer.unique_json(b'{"Id":1,"Id":2}')


if __name__ == '__main__':
    unittest.main()
