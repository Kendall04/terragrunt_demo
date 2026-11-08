"""Captured az6 regressions: hermetic timestamps and disposable POSIX paths only."""
import datetime as dt
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import host


class TimestampTests(unittest.TestCase):
    def test_restore_consumer_accepts_captured_dotnet_manifest_and_refuses_submicrosecond_inversion(self):
        from test_recovery import FakePort, NAME, IDENTITY, TARGET
        port=FakePort();source=host.source(port,NAME,None,None,None,IDENTITY);failure=host.quiesce(port,source,IDENTITY)
        source.update(PreMarkerRequestUtc='2026-10-23T04:41:28.132761Z',PreMarkerConfirmedUtc='2026-10-23T04:41:28.419738Z',PostMarkerConfirmedUtc='2026-10-23T04:41:30.387806Z')
        source['Receipt']['Manifest'].update(StartedUtc='2026-10-23T04:41:29.5627332+00:00',CompletedUtc='2026-10-23T04:41:29.831222+00:00')
        failure.update(FailureDeclaredUtc='2026-10-23T04:41:48.429323Z',SourceInactiveConfirmedUtc='2026-10-23T04:41:48.633769Z')
        with patch.object(host,'utc',return_value='2026-10-23T04:44:11.060106Z'):
            self.assertEqual(host.restore(port,NAME,None,None,None,TARGET,source,failure)['Status'],'TARGET_RECOVERED_REVIEW_EVIDENCE')
            source['Receipt']['Manifest']['CompletedUtc']='2026-10-23T04:41:29.5627331+00:00'
            with self.assertRaisesRegex(ValueError,'INVALID_EVENT_ORDER'):
                host.restore(port,NAME,None,None,None,TARGET,source,failure)

    def test_actual_dotnet_timestamp_and_exact_submicrosecond_order(self):
        value='2026-10-23T04:41:29.5627332+00:00'
        self.assertEqual(host.timestamp(value),dt.datetime(2026,10,23,4,41,29,562733,tzinfo=dt.timezone.utc))
        later='2026-10-23T04:41:29.5627333+00:00'
        self.assertTrue(host.event_order(value,later))
        self.assertFalse(host.event_order(later,value))
        self.assertEqual(host.timestamp_ticks(later)-host.timestamp_ticks(value),1)

    def test_offset_equivalence_and_supported_fraction_lengths(self):
        self.assertEqual(host.timestamp_ticks('2026-10-22T22:41:29.5627332-06:00'),host.timestamp_ticks('2026-10-23T04:41:29.5627332Z'))
        for fraction in ('','1','123','123456','1234567'):
            value='2026-10-23T04:41:29'+('.'+fraction if fraction else '')+'Z'
            self.assertTrue(host.event_order(value,value))

    def test_malformed_missing_zone_and_excess_precision_refuse(self):
        for value in ('2026-10-23T04:41:29.12345678Z','2026-10-23T04:41:29.123xZ','2026-10-23T04:41:29','2026-02-30T00:00:00Z','2026-10-23T04:41:29+25:00','garbage',None):
            with self.subTest(value=value),self.assertRaises(ValueError):host.timestamp(value)


@unittest.skipUnless(os.name=='posix','Ownership/mode assertions require POSIX; Windows is not native evidence')
class StagingTests(unittest.TestCase):
    def arrange(self,root):
        parent=Path(root)/'backup';user=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())
        options={'StagingDirectory':str(parent/'trial'),'RestoreDirectory':str(parent/'trial-restores')}
        return parent,user,patch.object(host,'options',return_value=options)

    def test_parent_owner_mode_then_readable_private_config(self):
        with tempfile.TemporaryDirectory() as root:
            parent,user,options=self.arrange(root)
            with options:config=host.create_staging('fixture',user)
            host.private_write(config,{'Synthetic':True})
            self.assertEqual(config.read_text().strip(),'{\n  "Synthetic": true\n}')
            for path in (parent,config.parent,parent/'trial-restores'):
                self.assertEqual(path.stat().st_uid,user.pw_uid)
                self.assertEqual(path.stat().st_gid,user.pw_gid)
                self.assertEqual(path.stat().st_mode&0o777,0o700)
            self.assertEqual(config.stat().st_mode&0o777,0o600)

    def test_existing_shared_or_wrong_owner_parent_never_reowned(self):
        with tempfile.TemporaryDirectory() as root:
            parent,user,options=self.arrange(root);parent.mkdir(mode=0o755)
            with options,patch.object(host.os,'chown') as change,self.assertRaisesRegex(ValueError,'PRIVATE_SQL_STAGING_PARENT_REQUIRED'):
                host.create_staging('fixture',user)
            change.assert_not_called();self.assertEqual(list(parent.iterdir()),[])
            parent.chmod(0o700);wrong=SimpleNamespace(pw_uid=user.pw_uid+1,pw_gid=user.pw_gid)
            with options,patch.object(host.os,'chown') as change,self.assertRaisesRegex(ValueError,'PRIVATE_SQL_STAGING_PARENT_REQUIRED'):
                host.create_staging('fixture',wrong)
            change.assert_not_called()

    def test_symlink_and_existing_trial_refuse_without_chown(self):
        with tempfile.TemporaryDirectory() as root:
            parent,user,options=self.arrange(root);foreign=Path(root)/'foreign';foreign.mkdir();parent.symlink_to(foreign,target_is_directory=True)
            with options,patch.object(host.os,'chown') as change,self.assertRaisesRegex(ValueError,'SAFE_ABSOLUTE_PATH_REQUIRED'):
                host.create_staging('fixture',user)
            change.assert_not_called();parent.unlink();parent.mkdir(mode=0o700);(parent/'trial').mkdir(mode=0o700)
            with options,patch.object(host.os,'chown') as change,self.assertRaisesRegex(ValueError,'EXISTING_STAGING_REQUIRES_REVIEW'):
                host.create_staging('fixture',user)
            change.assert_not_called()


if __name__=='__main__':unittest.main()
