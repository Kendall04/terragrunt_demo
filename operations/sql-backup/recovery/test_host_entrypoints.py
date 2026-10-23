"""Production host.main entrypoints with real private POSIX paths and fake ports.

No engine/API/AWS/subprocess execution. These tests do not prove native recovery.
The explicit existing scratch root avoids group-writable /tmp executable parents.
"""
from contextlib import redirect_stdout
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import host
from test_recovery import FakePort, IDENTITY, TARGET, NAME


class EntrypointPort(FakePort):
    def __init__(self, identity):
        super().__init__()
        self.bound_identity = identity
        self.secret_calls = 0
        self.fail_backup = False

    def identity(self):
        return self.bound_identity

    def secret(self, arn):
        self.secret_calls += 1
        return super().secret(arn)

    def backup(self, *args, **kwargs):
        if self.fail_backup:
            raise ValueError('CHILD_FAILED_REVIEW_BEFORE_RETRY')
        result = super().backup(*args, **kwargs)
        if result['Status'] == 'REMOTE_VERIFIED':
            # Captured .NET wire format, synthetic timestamps and backup port.
            value = result['Receipt']['Manifest']['StartedUtc']
            parsed = dt.datetime.fromisoformat(value)
            result['Receipt']['Manifest']['StartedUtc'] = parsed.strftime('%Y-%m-%dT%H:%M:%S.%f') + '0+00:00'
        return result


@unittest.skipUnless(os.name == 'posix' and getattr(os, 'geteuid', lambda: -1)() == 0,
                     'Explicit POSIX root filesystem fixture; not Windows/native SQL evidence')
class HostEntrypointTests(unittest.TestCase):
    def setUp(self):
        import pwd
        scratch = Path('/opt/codex-artifacts')
        self.assertTrue(scratch.is_dir(), 'Use the existing approved local fixture root; do not install anything')
        self.temp = tempfile.TemporaryDirectory(prefix='ecs-host-entry-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assertTrue(all(not p.is_symlink() and not p.stat().st_mode & 0o022
                            for p in (self.root, *self.root.parents)))
        self.user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
        self.pwd = pwd
        self.ticks = 0

    def clock(self):
        self.ticks += 1
        return (dt.datetime(2026, 10, 23, 6, tzinfo=dt.timezone.utc)
                + dt.timedelta(milliseconds=self.ticks)).isoformat()

    def layout(self, label):
        root = self.root / label
        root.mkdir(mode=0o700)
        executables = {}
        for name in ('api', 'backup'):
            path = root / name
            path.write_bytes(b'explicitly-synthetic-never-executed-' + name.encode())
            path.chmod(0o700)
            executables[name] = path
        return root, executables

    def invoke(self, action, root, executables, port, source=None, failure=None, wrong_hash=False):
        directory = root / ('receipts-' + action)
        directory.mkdir(mode=0o700, exist_ok=True)
        args = ['host.py', action, '--trial', NAME, '--directory', str(directory), '--execute',
                '--acknowledge', NAME, '--expected-instance-id',
                (TARGET if action == 'restore' else IDENTITY)['instanceId'], '--expected-az',
                (TARGET if action == 'restore' else IDENTITY)['availabilityZone']]
        if action != 'quiesce':
            for name, path in executables.items():
                args += ['--' + name, str(path), '--' + name + '-sha256',
                         'a' * 64 if wrong_hash else hashlib.sha256(path.read_bytes()).hexdigest()]
        if source is not None:
            args += ['--source', str(source)]
        if failure is not None:
            args += ['--failure', str(failure)]
        options = dict(host.options(NAME), StagingDirectory=str(root / 'sql-backup' / NAME),
                       RestoreDirectory=str(root / 'sql-backup' / (NAME + '-restores')))
        output = io.StringIO()
        with patch.object(sys, 'argv', args), patch.object(host, 'Port', return_value=port), \
                patch.object(host, 'options', return_value=options), patch.object(host, 'utc', self.clock), \
                patch.object(self.pwd, 'getpwnam', return_value=self.user), \
                patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            host.main()
        return directory / (action + '-receipt.json'), output.getvalue()

    def test_clean_source_quiesce_restore_main_preserves_private_paths_and_dotnet_manifest(self):
        source_root, executables = self.layout('source')
        target_root, target_executables = self.layout('target')
        source_port = EntrypointPort(IDENTITY)
        source_path, stdout = self.invoke('source', source_root, executables, source_port)
        source = json.loads(source_path.read_text())
        self.assertEqual(source['Status'], 'SOURCE_BACKED_UP')
        self.assertEqual(json.loads(stdout)['Status'], 'SOURCE_BACKED_UP')
        manifest_started = source['Receipt']['Manifest']['StartedUtc']
        self.assertEqual(len(manifest_started.split('.')[1].split('+')[0]), 7)
        failure_path, _ = self.invoke('quiesce', source_root, executables, source_port, source=source_path)
        target_path, _ = self.invoke('restore', target_root, target_executables, EntrypointPort(TARGET),
                                     source=source_path, failure=failure_path)
        target = json.loads(target_path.read_text())
        self.assertEqual(target['Checkdb'], 'RESTORED_CHECKDB_READABLE')
        self.assertFalse(target['FullEcsRecoveryProven'])
        self.assertEqual(target['ManifestVersion'], source['Receipt']['ManifestVersion'])
        self.assertEqual(json.loads(source_path.read_text())['Receipt']['Manifest']['StartedUtc'], manifest_started)
        for root in (source_root, target_root):
            for path in (root / 'sql-backup', root / 'sql-backup' / NAME,
                         root / 'sql-backup' / (NAME + '-restores')):
                self.assertEqual(path.stat().st_uid, self.user.pw_uid)
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / 'sql-backup' / NAME / 'backup-config.json').stat().st_mode & 0o777, 0o600)
        for path in (source_path, failure_path, target_path):
            self.assertTrue(path.with_suffix('.started').is_file())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('Synthetic!not-a-real-password', path.read_text())

    def test_failed_backup_keeps_started_and_refuses_replay_before_more_secrets_or_ddl(self):
        root, executables = self.layout('failed')
        port = EntrypointPort(IDENTITY)
        port.fail_backup = True
        with self.assertRaisesRegex(ValueError, '^CHILD_FAILED_REVIEW_BEFORE_RETRY$'):
            self.invoke('source', root, executables, port)
        output = root / 'receipts-source/source-receipt.json'
        started = output.with_suffix('.started')
        original = started.read_bytes()
        self.assertFalse(output.exists())
        secret_count, commands = port.secret_calls, list(port.commands)
        with self.assertRaisesRegex(ValueError, '^PREVIOUS_ACTION_REQUIRES_REVIEW$'):
            self.invoke('source', root, executables, port)
        self.assertEqual(port.secret_calls, secret_count)
        self.assertEqual(port.commands, commands)
        self.assertEqual(started.read_bytes(), original)

    def test_wrong_identity_or_binary_hash_refuses_before_secrets_or_sql(self):
        for case, expected in [('identity', 'WRONG_ACCOUNT_REGION_OR_HOST'), ('hash', 'EXECUTABLE_HASH_MISMATCH')]:
            with self.subTest(case=case):
                root, executables = self.layout(case)
                port = EntrypointPort(dict(IDENTITY, accountId='000000000000') if case == 'identity' else IDENTITY)
                with self.assertRaisesRegex(ValueError, '^' + expected + '$'):
                    self.invoke('source', root, executables, port, wrong_hash=case == 'hash')
                self.assertEqual(port.secret_calls, 0)
                self.assertEqual(port.commands, [])
                self.assertFalse((root / 'sql-backup').exists())

    def test_existing_staging_never_repaired_or_reused_by_main(self):
        root, executables = self.layout('existing')
        stage = root / 'sql-backup' / NAME
        stage.mkdir(mode=0o700, parents=True)
        prior = stage / 'prior-evidence.txt'
        prior.write_text('preserve this synthetic evidence')
        port = EntrypointPort(IDENTITY)
        with self.assertRaisesRegex(ValueError, '^EXISTING_STAGING_REQUIRES_REVIEW$'):
            self.invoke('source', root, executables, port)
        self.assertEqual(prior.read_text(), 'preserve this synthetic evidence')
        self.assertEqual(port.secret_calls, 0)
        self.assertEqual(port.commands, [])


if __name__ == '__main__':
    unittest.main()
