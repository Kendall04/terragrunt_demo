"""Native fixture staging and real observer/publisher logic; transport/checker are doubles."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import cohost
import test_host
import test_sentinel_publish

NOW=dt.datetime(2026,10,26,1,tzinfo=dt.timezone.utc)
class Installation(unittest.TestCase):
    def setUp(self):
        test_host.PackageTests.setUp(self)
        self.archive=self.root/'cohost.tar'
        self.sha=test_host.package.build(self.publish,self.archive,'a'*40,with_observer=True)['Sha256']
        self.sentinel=self.root/'sentinel.json'
        self.value={'SchemaVersion':1,'Placement':'SQL_HOST','Account':'341936017254','Region':'us-east-1','RunId':'ecs-sentinel-cohost','Subject':'dev-sql-backups','StartsAt':'2026-10-26T00:00:00Z','ExpiresAt':'2026-10-27T00:00:00Z','CadenceSeconds':300,'ReminderSeconds':0,'PublishAttempts':3,'WatchdogSeconds':1200,'ExpectedUp':True}
        self.sentinel.write_text(json.dumps(self.value))
    def tearDown(self):test_host.PackageTests.tearDown(self)
    def stage(self):return test_host.package.install(self.archive,self.sha,self.config,self.fixture,self.user,True,None,self.sentinel)
    def test_opt_in_stages_once_without_service_control_or_credentials(self):
        self.assertEqual(self.stage()['Status'],'STAGED_NOT_ENABLED')
        self.assertEqual(self.stage()['Status'],'ALREADY_INSTALLED')
        self.assertEqual(cohost.verify(self.fixture,NOW)['FailureDomain'],'SHARED_WITH_SQL')
        self.assertFalse((self.fixture/'etc/systemd/system/timers.target.wants').exists())
        self.assertFalse((self.fixture/'run/sql-backup-credentials').exists())
        service=(self.fixture/'etc/systemd/system/sql-backup-sentinel-producer.service').read_text()
        self.assertIn('--producer-job-receipt /var/opt/mssql/backup/v2/.service/last-job.json',service)
        self.assertNotIn('LoadCredential=',service);self.assertNotIn('Requisite=mssql',service)
        self.assertIn('ExecStartPre=',service);self.assertIn('SendSIGKILL=no',service)
        self.assertIn('OnBootSec=90',(self.fixture/'etc/systemd/system/sql-backup-sentinel-producer.timer').read_text())
        target=(self.fixture/'etc/systemd/system/sql-backup-cohost.target').read_text()
        self.assertIn('WantedBy=multi-user.target',target)
        self.assertIn('Wants=sql-backup.timer sql-backup-sentinel-producer.timer',target)
        binding=self.stage()['ExternalWatchdogBinding']
        self.assertEqual(binding['sender_role_arn'],'arn:aws:iam::341936017254:role/fixture-role')
        self.assertEqual((binding['watchdog_seconds'],binding['observer_expected_up']),(1200,True))
        self.assertEqual(0o640,(self.fixture/'etc/terragrunt-demo/sql-backup/sentinel.json').stat().st_mode&0o777)
    def test_configuration_drift_is_not_silently_adopted(self):
        self.stage();self.value['Subject']='other-sql';self.sentinel.write_text(json.dumps(self.value))
        with self.assertRaisesRegex(ValueError,'REVIEWED_OBSERVER_REPLACEMENT'):self.stage()
    def test_expired_or_future_window_stops_both_units_at_integrity_gate(self):
        self.stage()
        for at in [NOW-dt.timedelta(days=1),NOW+dt.timedelta(days=1)]:
            with self.assertRaisesRegex(ValueError,'WINDOW_NOT_ACTIVE'):cohost.verify(self.fixture,at)
        drop=(self.fixture/'etc/systemd/system/sql-backup.service.d/sentinel-integrity.conf').read_text()
        self.assertIn('cohost.py verify',drop)
    def test_tamper_on_binary_config_units_or_source_blocks_startup(self):
        self.stage()
        for name in ['opt/terragrunt-demo/sql-backup/bin/SqlBackup','etc/terragrunt-demo/sql-backup/config.json','etc/terragrunt-demo/sql-backup/sentinel.json','etc/systemd/system/sql-backup-sentinel-producer.timer','opt/terragrunt-demo/sql-backup/observer.py']:
            p=self.fixture/name;raw=p.read_bytes();p.write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'FILE_DRIFT'):cohost.verify(self.fixture,NOW)
            p.write_bytes(raw)
        cohost.verify(self.fixture,NOW)
    def test_unsafe_symlink_and_writable_files_block_startup(self):
        self.stage();p=self.fixture/'opt/terragrunt-demo/sql-backup/observer.py';raw=p.read_bytes();mode=p.stat().st_mode&0o777
        p.chmod(0o777)
        with self.assertRaisesRegex(ValueError,'WRITABLE_INSTALL'):cohost.verify(self.fixture,NOW)
        p.chmod(mode);p.unlink();p.symlink_to(self.fixture/'opt/terragrunt-demo/sql-backup/cohost.py')
        with self.assertRaisesRegex(ValueError,'INSTALLED_FILE_REQUIRED'):cohost.verify(self.fixture,NOW)
        p.unlink();p.write_bytes(raw);p.chmod(mode)
    def test_no_secrets_silent_defaults_or_watchdog_too_short(self):
        backup=json.loads(self.config.read_text())
        for delta in [{'Password':'rejected-test-marker'},{'WatchdogSeconds':1140},{'ExpectedUp':'true'},{'CadenceSeconds':True},{'Placement':'INDEPENDENT'},{'Region':'us-west-2'},{'ExpiresAt':'2026-10-28T00:00:00Z'}]:
            with self.assertRaises((ValueError,TypeError)):cohost.validate(self.value|delta,backup)
    def test_legacy_package_needs_explicit_opt_in_before_new_units(self):
        plain=self.root/'legacy-layout.tar';sha=test_host.package.build(self.publish,plain,'a'*40)['Sha256']
        with self.assertRaisesRegex(ValueError,'COHOST_PACKAGE_REQUIRED'):test_host.package.install(plain,sha,self.config,self.fixture,self.user,True,None,self.sentinel)
        self.assertFalse((self.fixture/'opt').exists())
    def test_foreign_unit_preserved_and_no_partial_install(self):
        p=self.fixture/'etc/systemd/system/sql-backup-sentinel-producer.timer';p.parent.mkdir(parents=True);p.write_text('foreign')
        with self.assertRaisesRegex(ValueError,'UNMANAGED_TARGET'):self.stage()
        self.assertEqual(p.read_text(),'foreign');self.assertFalse((self.fixture/'opt').exists())

class LocalTelemetry(unittest.TestCase):
    def setUp(self):
        test_sentinel_publish.PublisherTests.setUp(self)
        self.job=self.root/'last-job.json';self.args.producer_job_receipt=self.job
    def tearDown(self):test_sentinel_publish.PublisherTests.tearDown(self)
    def runner(self,argv,**kw):return test_sentinel_publish.PublisherTests.runner(self,argv,**kw)
    def sends(self):return test_sentinel_publish.PublisherTests.sends(self)
    def tick(self):return test_sentinel_publish.PublisherTests.tick(self)
    def event(self):return json.loads(self.sends()[-1][0][self.sends()[-1][0].index('--message-body')+1])
    def test_real_local_receipt_failure_then_verified_health_recovers_no_secret_environment(self):
        self.status='HEALTHY';self.job.write_text(json.dumps({'Status':'FAILED_OR_UNCONFIRMED','Utc':test_sentinel_publish.NOW.timestamp()}))
        with patch.dict(os.environ,{'SQL_BACKUP_CONNECTION_STRING':'REJECTED-SECRET-MARKER','AWS_SECRET_ACCESS_KEY':'REJECTED-SECRET-MARKER'}):self.tick()
        self.assertEqual((self.event()['Status'],self.event()['ProducerFailureCoverage']),('FAILED','LOCAL_RECEIPT_ONLY'))
        self.assertTrue(all('REJECTED-SECRET-MARKER' not in json.dumps(x[1]['env']) for x in self.calls))
        self.job.write_text(json.dumps({'Status':'REMOTE_VERIFIED_CLEANUP_VERIFIED','Utc':test_sentinel_publish.NOW.timestamp()-120}))
        self.tick();self.assertEqual((self.event()['Status'],self.event()['Reason']),('HEALTHY','RECOVERED'))
        self.tick();self.assertFalse(self.event()['Emit']);self.assertEqual(self.event()['Evaluation'],'CHECK_COMMAND_RESULT')
    def test_absent_receipt_or_unknown_job_never_reports_healthy(self):
        self.status='HEALTHY';self.tick();self.assertEqual(self.event()['Status'],'UNKNOWN')
        self.job.write_text(json.dumps({'Status':'UNKNOWN','Code':'CLIENT_DEADLINE','Utc':test_sentinel_publish.NOW.timestamp()}))
        self.tick();self.assertEqual(self.event()['Status'],'UNKNOWN')
    def test_total_send_budget_survives_restart_and_no21st_event_is_sent(self):
        self.args.total_publish_attempts=20
        self.job.write_text(json.dumps({'Status':'REMOTE_VERIFIED_CLEANUP_VERIFIED','Utc':test_sentinel_publish.NOW.timestamp()-120}))
        for _ in range(20):self.tick()
        with self.assertRaisesRegex(test_sentinel_publish.pub.Refused,'TOTAL_PUBLISH_BUDGET_EXHAUSTED'):self.tick()
        self.assertEqual(len(self.sends()),20)
        self.assertTrue((self.args.state_directory/'delivery/pending.json').exists())
        del self.args.total_publish_attempts
        with self.assertRaisesRegex(test_sentinel_publish.pub.Refused,'TOTAL_PUBLISH_BOUND_REQUIRED'):self.tick()
        self.args.total_publish_attempts=19
        with self.assertRaisesRegex(test_sentinel_publish.pub.Refused,'TOTAL_PUBLISH_BUDGET_SCOPE'):self.tick()
        self.assertEqual(len(self.sends()),20)
    def test_missing_and_denied_checks_keep_existing_semantics(self):
        self.job.write_text(json.dumps({'Status':'REMOTE_VERIFIED_CLEANUP_VERIFIED','Utc':test_sentinel_publish.NOW.timestamp()-120}))
        self.tick();self.assertEqual(self.event()['Status'],'MISSING')
        def denied(argv,**kw):
            if argv[1]=='check':
                import subprocess
                return subprocess.CompletedProcess(argv,1,b'not JSON',b'SECRET-MARKER')
            return self.runner(argv,**kw)
        test_sentinel_publish.pub.run(self.args,denied,lambda:test_sentinel_publish.NOW)
        self.assertEqual(self.event()['Status'],'UNKNOWN');self.assertNotIn('SECRET-MARKER',json.dumps(self.event()))

if __name__=='__main__':unittest.main(verbosity=2)
