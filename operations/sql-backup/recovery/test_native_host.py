import datetime as dt
import unittest
from unittest.mock import patch
import native_host as host


def request():
    return {'trial': 'v2-cross-a-b', 'instanceId': 'i-' + 'b' * 17, 'sourceInstanceId': 'i-' + 'a' * 17,
            'sourceLaunchTime': '2026-11-04T20:15:00Z', 'targetAz': 'us-east-1b',
            'expiresAt': (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(),
            'sourceFence': None, 'backupReceipt': None, 'expectedRows': 1, 'expectedDataHash': '1' * 64}


class NativeRecoveryTests(unittest.TestCase):
    def test_sqlcmd_output_bound_and_confidential_password(self):
        sql = object.__new__(host.Sql)
        with patch.object(sql, 'password', return_value='private-test-password'), patch.object(host, 'run') as child:
            def execute(argv, **kwargs):
                self.assertEqual(argv[argv.index('-y') + 1], '8000')
                self.assertIn('-N', argv)
                self.assertNotIn('-C', argv)
                self.assertNotIn('private-test-password', argv)
                self.assertEqual(kwargs['env']['SQLCMDPASSWORD'], 'private-test-password')
                return '{"rows":3}'
            child.side_effect = execute
            self.assertEqual(sql.query(host.SNAPSHOT), {'rows': 3})
            self.assertNotIn('SQLCMDPASSWORD', child.call_args.kwargs['env'])

    def test_scope_rejects_paths_unbounded_identity_and_expiry(self):
        host.validate(request())
        for key, value in [('trial', '../other'), ('instanceId', 'other'), ('targetAz', 'eu-west-1a'),
                           ('expectedRows', -1), ('expectedDataHash', 'fake'), ('expiresAt', '2000-01-01T00:00:00Z')]:
            with self.subTest(key=key):
                r = request()
                r[key] = value
                with self.assertRaises(ValueError):
                    host.validate(r)

    def test_restore_requires_positive_ec2_fence_before_any_sql(self):
        class NoSql:
            def query(self, *_args):
                raise AssertionError('SQL must not run')
        r = request()
        r['sourceFence'] = {'ec2State': 'stopped', 'instanceId': r['sourceInstanceId'],
                            'launchTime': r['sourceLaunchTime'], 'retainedVolumeVerified': True}
        with self.assertRaisesRegex(ValueError, 'POSITIVE_SOURCE_FENCE_REQUIRED'):
            host.restore(NoSql(), r)
        r['sourceFence']['ec2State'] = 'terminated'
        r['sourceFence']['retainedVolumeVerified'] = False
        with self.assertRaisesRegex(ValueError, 'POSITIVE_SOURCE_FENCE_REQUIRED'):
            host.restore(NoSql(), r)

    def test_fence_refuses_concurrent_session_before_mutation(self):
        r = request()
        r['instanceId'] = r['sourceInstanceId']
        observation = {'edition': 4, 'rows': 1, 'dataHash': '1' * 64,
            'migrations': [{'MigrationId': x} for x in host.MIGRATIONS],
            'otherSessions': 1, 'accessMode': 'READ_WRITE'}
        class ReadOnly:
            def query(self, sql):
                assert sql == host.SNAPSHOT
                return observation
        with patch.object(host, 'run', side_effect=AssertionError('no host mutation')):
            with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_QUIESCED'):
                host.fence(ReadOnly(), r)

    def test_data_and_migration_identity_must_match(self):
        r = request()
        result = {'edition': 4, 'rows': 1, 'dataHash': '1' * 64,
                  'migrations': [{'MigrationId': x} for x in host.MIGRATIONS]}
        host.check_data(result, r)
        result['rows'] = 0
        with self.assertRaisesRegex(ValueError, 'RESTORED_DATA_MISMATCH'):
            host.check_data(result, r)

    def test_running_oneshot_backup_blocks_fence_before_mutation(self):
        r = request()
        r['instanceId'] = r['sourceInstanceId']
        observation = {'edition': 4, 'rows': 1, 'dataHash': '1' * 64,
            'migrations': [{'MigrationId': x} for x in host.MIGRATIONS],
            'otherSessions': 0, 'accessMode': 'READ_WRITE'}
        class ReadOnly:
            def query(self, sql):
                assert sql == host.SNAPSHOT
                return observation
        for state in ('active', 'activating', 'deactivating', 'reloading', 'unknown'):
            with self.subTest(state=state), patch.object(host, 'run', return_value=state) as child:
                with self.assertRaisesRegex(ValueError, 'BACKUP_IN_PROGRESS'):
                    host.fence(ReadOnly(), r)
                child.assert_called_once_with(['systemctl', 'show', 'sql-backup.service', '--property=ActiveState', '--value'])
        with patch.object(host, 'run', side_effect=['inactive', '', 'activating']) as child:
            with self.assertRaisesRegex(ValueError, 'BACKUP_IN_PROGRESS'):
                host.fence(ReadOnly(), r)
            self.assertEqual(child.call_count, 3)
            self.assertEqual(child.call_args_list[1].args[0], ['systemctl', 'stop', 'sql-backup.timer'])

    def test_dotnet_seven_digit_timestamp(self):
        self.assertEqual(host.timestamp('2026-11-05T23:01:57.6781198+00:00').microsecond, 678119)

    def test_discovery_does_not_invent_baseline_and_cannot_authorize_mutation(self):
        r = request()
        r.update(expectedRows=None, expectedDataHash=None)
        host.validate(r, inspect=True)
        with self.assertRaises(ValueError):
            host.validate(r)


if __name__ == '__main__':
    unittest.main()
