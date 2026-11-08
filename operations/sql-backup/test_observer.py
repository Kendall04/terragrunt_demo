"""Offline observer transitions/entrypoint; fake checker port, no SQL/AWS/installation."""
import datetime as dt
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import observer
import signals

NOW='2026-10-23T18:00:00Z'
SCOPE='a'*64
ROOT=Path(__file__).resolve().parent

def checked(status,latest=None,now=NOW):
    return observer.health({'Status':status,'Code':signals.PAIRS[status],'LastSuccessUtc':latest},now,0 if status in ('HEALTHY','MAINTENANCE') else 1)

class TransitionTests(unittest.TestCase):
    def tick(self,status,previous=None,now=NOW,repeat=0,latest=None):
        return observer.transition(checked(status,latest,now),now,previous,'dev-sql-backups',SCOPE,repeat)

    def test_missing_stale_failed_changes_and_identical_dedup(self):
        state,event=self.tick('MISSING');self.assertTrue(event['Emit']);self.assertEqual(event['Reason'],'INITIAL_ATTENTION')
        state,event=self.tick('MISSING',state,now='2026-10-23T18:05:00Z');self.assertFalse(event['Emit'])
        state,event=self.tick('STALE',state,now='2026-10-23T18:10:00Z',latest='2026-10-23T12:00:00Z');self.assertTrue(event['Emit'])
        state,event=self.tick('FAILED',state,now='2026-10-23T18:15:00Z');self.assertTrue(event['Emit']);self.assertEqual(event['Code'],'LAST_ATTEMPT_FAILED')
        self.assertEqual(event['Delivery'],'NONE');self.assertFalse(event['SentinelIntegrated']);self.assertFalse(event['RemediationAllowed'])

    def test_recovery_once_and_newer_healthy_metadata_does_not_flood(self):
        state,_=self.tick('FAILED')
        state,event=self.tick('HEALTHY',state,now='2026-10-23T18:05:00Z',latest='2026-10-23T18:04:00Z')
        self.assertTrue(event['Emit']);self.assertEqual(event['Reason'],'RECOVERED')
        state,event=self.tick('HEALTHY',state,now='2026-10-23T18:10:00Z',latest='2026-10-23T18:09:00Z');self.assertFalse(event['Emit'])
        self.assertFalse(state['IncidentOpen'])
        _,baseline=self.tick('HEALTHY',latest='2026-10-23T17:00:00Z');self.assertFalse(baseline['Emit'])

    def test_reminder_explicit_boundary_and_disabled(self):
        state,_=self.tick('MISSING',repeat=600)
        same,event=self.tick('MISSING',state,now='2026-10-23T18:09:59Z',repeat=600);self.assertFalse(event['Emit'])
        same,event=self.tick('MISSING',same,now='2026-10-23T18:10:00Z',repeat=600);self.assertTrue(event['Emit']);self.assertEqual(event['Reason'],'REMINDER_DUE')
        _,event=self.tick('MISSING',same,now='2026-10-24T18:10:00Z',repeat=0);self.assertFalse(event['Emit'])

    def test_maintenance_preserves_incident_then_recovers(self):
        state,_=self.tick('FAILED');state,event=self.tick('MAINTENANCE',state,now='2026-10-23T18:05:00Z')
        self.assertFalse(event['Emit']);self.assertTrue(state['IncidentOpen']);self.assertEqual(state['Condition'],['FAILED','LAST_ATTEMPT_FAILED'])
        _,event=self.tick('HEALTHY',state,now='2026-10-23T18:10:00Z',latest='2026-10-23T18:09:00Z');self.assertEqual(event['Reason'],'RECOVERED')

    def test_forwarded_failure_only_overrides_until_new_verified_backup(self):
        body={'Status':'HEALTHY','Code':'RECENT_REMOTE_COMMIT','LastSuccessUtc':'2026-10-23T17:00:00Z'}
        job={'Status':'FAILED_OR_UNCONFIRMED','Utc':signals.utc('2026-10-23T17:30:00Z').timestamp()}
        fail=observer.health(body,NOW,0,job);self.assertEqual(fail['Status'],'FAILED');self.assertEqual(fail['ProducerFailureCoverage'],'LOCAL_RECEIPT_ONLY');self.assertEqual(fail['LastSuccessUtc'],body['LastSuccessUtc'])
        body['LastSuccessUtc']='2026-10-23T17:45:00Z';self.assertEqual(observer.health(body,NOW,0,job)['Status'],'HEALTHY')
        self.assertEqual(observer.health(body,NOW,0)['ProducerFailureCoverage'],'NOT_PROVIDED')

    def test_future_private_duplicate_and_invalid_health_fail_closed(self):
        for body in [b'{"Status":"MISSING","Status":"HEALTHY"}',b' '*65537]:
            with self.assertRaises(observer.Refused):observer.parse_health(body)
        with self.assertRaises(signals.Refused):observer.health({'Status':'MISSING','Code':'NO_REMOTE_COMMIT','Password':'never-log'},NOW,1)
        with self.assertRaises(signals.Refused):checked('HEALTHY','2026-10-24T18:00:00Z')

    def test_scope_clock_and_corrupt_state_not_reset(self):
        state,_=self.tick('MISSING')
        for change in [{'Subject':'another'},{'ConfigSha256':'b'*64},{'LastObservedUtc':'2026-10-24T00:00:00Z'},{'IncidentOpen':False},{'Secret':'never-log'}]:
            changed=state|change
            with self.subTest(change=change),self.assertRaises((observer.Refused,signals.Refused)):self.tick('MISSING',changed)

class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.config=self.root/'config.json';self.config.write_text('{"Synthetic":true}')
        self.args=SimpleNamespace(action='run',config=self.config,state_directory=self.root/'observer',subject='dev-sql-backups',expected_up='true',repeat_after_seconds=0,observed_at=None,producer_job_receipt=None,executable=Path(sys.executable).resolve(),aws=True,ec2_role=True)
    def tearDown(self):self.tmp.cleanup()
    def clock(self):return signals.utc(NOW)
    def runner(self,body,code):
        def call(command,**kw):
            self.assertEqual(command[1:],[ 'check','--config',str(self.config),'--expected-up','true','--aws','--ec2-role'])
            self.assertFalse(any(k.startswith('SQL_') for k in kw['env']));self.assertNotIn('AWS_ACCESS_KEY_ID',kw['env']);self.assertNotIn('AWS_SECRET_ACCESS_KEY',kw['env'])
            return subprocess.CompletedProcess(command,code,json.dumps(body).encode(),b'never-log-secret-stderr')
        return call

    def test_command_is_check_only_and_state_survives_restart(self):
        runner=self.runner({'Status':'MISSING','Code':'NO_REMOTE_COMMIT'},1)
        with patch.dict(os.environ,{'SQL_BACKUP_CONNECTION_STRING':'never-output','AWS_ACCESS_KEY_ID':'never-copy','AWS_SECRET_ACCESS_KEY':'never-copy'}):first=observer.run(self.args,runner,self.clock)
        second=observer.run(self.args,runner,self.clock)
        self.assertTrue(first['Emit']);self.assertFalse(second['Emit']);self.assertTrue(first['CheckInvoked']);self.assertEqual(first['Evaluation'],'CHECK_COMMAND_RESULT')
        self.assertNotIn('never-',json.dumps(second));self.assertFalse((self.args.state_directory/'observer.lock').exists())
        self.assertTrue((self.args.state_directory/'observer-state.json').is_file())

    def test_command_denial_malformed_or_launch_failure_become_unknown_not_missing(self):
        for runner in [self.runner({'Status':'FAILED','Code':'ACCESS_DENIED'},1),self.runner({'Status':'HEALTHY','Password':'never-output'},0),lambda *a,**kw:(_ for _ in ()).throw(OSError('never-output'))]:
            event=observer.run(self.args,runner,self.clock);self.assertEqual(event['Status'],'UNKNOWN');self.assertEqual(event['Code'],'REMOTE_STORAGE_NOT_CHECKED');self.assertNotIn('never-',json.dumps(event))

    def test_maintenance_does_not_invoke_or_erase_failure(self):
        observer.run(self.args,self.runner({'Status':'FAILED','Code':'LAST_ATTEMPT_FAILED'},1),self.clock)
        self.args.expected_up='false'
        event=observer.run(self.args,lambda *a,**k:self.fail('Maintenance invoked checker'),self.clock)
        self.assertFalse(event['CheckInvoked']);self.assertEqual(event['Evaluation'],'EXPECTED_UP_FALSE')
        self.assertTrue(signals.read(self.args.state_directory/'observer-state.json')['IncidentOpen'])

    def test_read_gate_scope_and_interrupted_lock_never_retry_or_take_over(self):
        self.args.aws=False
        with self.assertRaises(observer.Refused):observer.run(self.args,lambda *a,**k:self.fail('No gate'),self.clock)
        self.args.aws=True
        observer.run(self.args,self.runner({'Status':'MISSING','Code':'NO_REMOTE_COMMIT'},1),self.clock)
        self.config.write_text('{"Synthetic":false}')
        with self.assertRaises(observer.Refused):observer.run(self.args,lambda *a,**k:self.fail('Wrong scope invoked checker'),self.clock)
        lock=self.args.state_directory/'observer.lock';lock.write_text('interrupted-owner')
        with self.assertRaises(observer.Refused):observer.run(self.args,lambda *a,**k:self.fail('Lock takeover'),self.clock)
        self.assertEqual(lock.read_text(),'interrupted-owner')

    def test_interrupted_pending_write_is_not_removed_or_adopted(self):
        self.args.state_directory.mkdir(mode=0o700);pending=self.args.state_directory/'observer-state.json.pending';pending.write_text('retained-interruption')
        with self.assertRaises(FileExistsError):observer.run(self.args,self.runner({'Status':'MISSING','Code':'NO_REMOTE_COMMIT'},1),self.clock)
        self.assertEqual(pending.read_text(),'retained-interruption');self.assertFalse((self.args.state_directory/'observer-state.json').exists())

    @unittest.skipUnless(os.name=='posix','POSIX permission/symlink qualification requires Linux')
    def test_native_private_directory_and_symlink_refused(self):
        self.args.state_directory.mkdir(mode=0o755)
        with self.assertRaisesRegex(observer.Refused,'PRIVATE_STATE_DIRECTORY_REQUIRED'):observer.run(self.args,lambda *a,**k:self.fail('Unsafe directory'),self.clock)
        self.args.state_directory.chmod(0o700);target=self.root/'other.json';target.write_text('{}');link=self.args.state_directory/'observer-state.json';link.symlink_to(target)
        with self.assertRaises(observer.Refused):observer.run(self.args,lambda *a,**k:self.fail('Symlink state'),self.clock)
        self.assertEqual(target.read_text(),'{}')

    def test_real_cli_replay_missing_to_recovery_and_no_secret_output(self):
        receipt=self.root/'health.json';receipt.write_text('{"Status":"MISSING","Code":"NO_REMOTE_COMMIT"}')
        command=[sys.executable,'-I','-B',str(ROOT/'observer.py'),'replay','--config',str(self.config),'--state-directory',str(self.args.state_directory),'--subject','dev-sql-backups','--expected-up','true','--repeat-after-seconds','0','--health-receipt',str(receipt),'--health-exit-code','1','--observed-at',NOW]
        first=subprocess.run(command,capture_output=True);self.assertEqual(first.returncode,1,first.stderr);self.assertTrue(json.loads(first.stdout)['Emit'])
        second=subprocess.run(command,capture_output=True);self.assertFalse(json.loads(second.stdout)['Emit'])
        receipt.write_text('{"Status":"HEALTHY","Code":"RECENT_REMOTE_COMMIT","LastSuccessUtc":"2026-10-23T17:55:00Z"}')
        command[command.index('--health-exit-code')+1]='0';last=subprocess.run(command,capture_output=True);self.assertEqual(last.returncode,0,last.stderr);self.assertEqual(json.loads(last.stdout)['Reason'],'RECOVERED')
        receipt.write_text('{"Password":"never-output"}');bad=subprocess.run(command,capture_output=True);self.assertEqual(bad.returncode,2);self.assertNotIn(b'never-output',bad.stdout+bad.stderr)

    def test_inert_units_are_independent_explicit_and_no_install_or_frequency_change(self):
        service=(ROOT/'sql-backup-observer.service.in').read_text();timer=(ROOT/'sql-backup-observer.timer.in').read_text()
        self.assertIn('observer.py run',service);self.assertIn('SendSIGKILL=no',service);self.assertIn('SuccessExitStatus=1',service)
        for forbidden in ['mssql-server.service','LoadCredential','SQL_BACKUP_CONNECTION_STRING','systemctl']:self.assertNotIn(forbidden,service)
        self.assertIn('OnCalendar=@OBSERVER_ON_CALENDAR@',timer);self.assertIn('@REMINDER_SECONDS@',service)
        self.assertNotIn('OnCalendar=hourly',timer)

if __name__=='__main__':unittest.main()
