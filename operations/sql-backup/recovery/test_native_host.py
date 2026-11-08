import datetime as dt
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock, mock_open
import json
import install_native_backup as installer
import activate_native_runtime as handoff
import sys
import native_host as host


def request():
    return {'trial': 'v2-cross-a-b', 'instanceId': 'i-' + 'b' * 17, 'sourceInstanceId': 'i-' + 'a' * 17,
            'sourceLaunchTime': '2026-11-04T20:15:00Z', 'targetAz': 'us-east-1b',
            'expiresAt': (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat(),
            'sourceFence': None, 'backupReceipt': None, 'expectedRows': 1, 'expectedDataHash': '1' * 64}


class NativeRecoveryTests(unittest.TestCase):
    def test_handoff_rejects_extra_grants_and_roles_before_activation(self):
        r = request()
        before = {'edition': 4, 'rows': 1, 'dataHash': '1' * 64,
                  'runtimeDisabled': True, 'otherSessions': 0, 'accessMode': 'READ_WRITE',
                  'migrations': [{'MigrationId': x} for x in host.MIGRATIONS]}
        grants = [{'class': 1, 'schemaName': 'dbo', 'state': 'G', 'minor_id': 0,
                   'objectName': name, 'permission_name': action}
                  for name, action in [('DemoTexts', 'SELECT'), ('DemoTexts', 'INSERT'),
                                       ('__EFMigrationsHistory', 'SELECT')]]
        base = dict(databaseRoles=0, serverRoles=0, elevatedServerGrants=0, ownsDatabase=0, grants=grants)
        mutations = [dict(base, databaseRoles=1), dict(base, ownsDatabase=1),
                     dict(base, grants=grants + [dict(grants[0], permission_name='UPDATE')]),
                     dict(base, grants=[dict(grants[0], state='W')] + grants[1:]),
                     dict(base, serverRoles=None)]
        for permissions in mutations:
            sql = Mock()
            sql.query.side_effect = [before, permissions]
            module = SimpleNamespace(Sql=Mock(return_value=sql), SNAPSHOT=host.SNAPSHOT,
                check_data=host.check_data, identity=Mock(), validate=host.validate, SA=host.SA)
            with self.subTest(permissions=permissions), \
                    patch.dict('sys.modules', {'native_host': module, 'resource': SimpleNamespace(RLIMIT_CORE=0, setrlimit=Mock())}), \
                    patch.object(sys, 'argv', ['handoff', 'private-request']), \
                    patch.object(sys, 'path', list(sys.path)), \
                    patch.object(Path, 'read_text', return_value=json.dumps(r)), \
                    patch('subprocess.run') as child, patch('os.umask'):
                with self.assertRaisesRegex(ValueError, 'HANDOFF_PRECONDITION_FAILED'):
                    handoff.main()
                child.assert_not_called()
                sql.password.assert_not_called()

    def test_public_install_restores_private_umask_on_success_and_failure(self):
        for failure in (None, RuntimeError('install failed')):
            package = Mock()
            package.install.side_effect = failure
            with self.subTest(failure=bool(failure)), patch.object(installer.os, 'umask', return_value=0o077) as mask:
                if failure:
                    with self.assertRaises(RuntimeError):
                        installer.install_public_package(package, Path('/private/package'))
                else:
                    installer.install_public_package(package, Path('/private/package'))
                self.assertEqual([call.args[0] for call in mask.call_args_list], [0o022, 0o077])

    def test_restore_preserves_receipt_before_promoting_readonly_backup(self):
        r = request()
        r['sourceFence'] = {'ec2State': 'terminated', 'instanceId': r['sourceInstanceId'],
                            'launchTime': r['sourceLaunchTime'], 'retainedVolumeVerified': True}
        r['backupReceipt'] = {'ManifestKey': 'exact-key', 'ManifestVersion': 'exact-version'}
        data = {'edition': 4, 'rows': 1, 'dataHash': '1' * 64, 'runtimeDisabled': True,
                'migrations': [{'MigrationId': x} for x in host.MIGRATIONS]}
        sql = Mock()
        sql.password.return_value = 'private-fixture-only'
        opened = mock_open()
        def query(statement, **kwargs):
            if statement == host.SNAPSHOT:
                return data
            if 'COUNT(*) FROM demodb.sys.tables' in statement:
                return {'tables': 0, 'sessions': 0, 'disabled': True}
            if 'MODIFY NAME' in statement:
                self.assertTrue(opened().write.called, 'restore receipt must precede promotion')
                self.assertLess(statement.index('SET READ_WRITE'), statement.index('MODIFY NAME'))
                self.assertNotIn('DROP', statement)
                self.assertNotIn('WITH REPLACE', statement)
            return {}
        sql.query.side_effect = query
        with patch.object(Path, 'read_text', return_value=json.dumps({'RestoreDirectory': '/var/opt/mssql/backup/v2-restores'})), \
                patch.object(Path, 'open', opened), \
                patch.object(host, 'restore_identity', return_value={'user': 10001, 'group': 10001, 'extra_groups': [], 'umask': 0o077}), \
                patch.object(host, 'run', return_value=json.dumps({'Status': 'RESTORED_CHECKDB_READABLE', 'Rows': 1})) as child:
            self.assertEqual(host.restore(sql, r)['runtime'], 'DISABLED_PENDING_HANDOFF')
            self.assertEqual(child.call_args.kwargs['user'], 10001)
            self.assertNotIn('SQL_RESTORE_CONNECTION_STRING', child.call_args.kwargs['env'])

    def test_restore_runs_as_sql_with_no_supplementary_groups(self):
        folder = Path('/var/opt/mssql/backup/v2-restores')
        who = SimpleNamespace(pw_uid=10001, pw_gid=10001)
        module = SimpleNamespace(getpwnam=Mock(return_value=who))
        observed = SimpleNamespace(st_mode=0o40700, st_uid=10001, st_gid=10001)
        with patch.dict('sys.modules', {'pwd': module}), patch.object(Path, 'is_symlink', return_value=False), \
                patch.object(Path, 'exists', return_value=True), patch.object(Path, 'stat', return_value=observed):
            self.assertEqual(host.restore_identity(folder),
                             {'user': 10001, 'group': 10001, 'extra_groups': [], 'umask': 0o077})

    def test_foreign_restore_directory_is_not_silently_reowned(self):
        folder = Path('/var/opt/mssql/backup/v2-restores')
        module = SimpleNamespace(getpwnam=Mock(return_value=SimpleNamespace(pw_uid=10001, pw_gid=10001)))
        for uid, mode in ((0, 0o40700), (10001, 0o40755)):
            with self.subTest(uid=uid, mode=mode), patch.dict('sys.modules', {'pwd': module}), \
                    patch.object(Path, 'is_symlink', return_value=False), \
                    patch.object(Path, 'exists', return_value=True), \
                    patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid, st_gid=uid)), \
                    patch.object(host.os, 'chown', create=True) as chown:
                with self.assertRaisesRegex(ValueError, 'EXISTING_RESTORE_DIRECTORY'):
                    host.restore_identity(folder)
                chown.assert_not_called()

    def test_restore_rejects_unreviewed_path_and_links(self):
        with self.assertRaisesRegex(ValueError, 'RESTORE_DIRECTORY_SCOPE'):
            host.restore_identity(Path('/tmp/arbitrary'))
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'RESTORE_DIRECTORY_LINK'):
                host.restore_identity(Path('/var/opt/mssql/backup/v2-restores'))

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
