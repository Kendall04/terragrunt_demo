"""Offline full check-to-spool-to-SQS port tests. No real subprocess, cloud or credential lookup."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import observer
import sentinel_publish as pub

NOW=dt.datetime(2026,10,23,18,tzinfo=dt.timezone.utc)

class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=self.root/'config.json';self.config.write_text('{"SyntheticTest":true}')
        self.args=SimpleNamespace(action='run',config=self.config,state_directory=self.root/'observer',subject='backup-test',expected_up='true',repeat_after_seconds=0,observed_at=None,producer_job_receipt=None,executable=Path(sys.executable).resolve(),aws_cli=Path(sys.executable).resolve(),aws=True,ec2_role=True,publish_attempts=3,expires_at='2026-10-24T18:00:00Z',account='000000000000',region='us-east-1',run_id='ecs-sentinel-localtest')
        self.calls=[];self.accept=True;self.status='MISSING'
    def tearDown(self):self.tmp.cleanup()
    def runner(self,argv,**kwargs):
        self.calls.append((argv,kwargs))
        if argv[1]=='check':
            code={'MISSING':'NO_REMOTE_COMMIT','HEALTHY':'RECENT_REMOTE_COMMIT'}[self.status]
            body={'Status':self.status,'Code':code,'LastSuccessUtc':None if self.status=='MISSING' else '2026-10-23T17:59:00Z'}
            return subprocess.CompletedProcess(argv,1 if self.status=='MISSING' else 0,json.dumps(body).encode(),b'')
        return subprocess.CompletedProcess(argv,0 if self.accept else 1,b'{"MessageId":"offline-message-id"}' if self.accept else b'',b'PRIVATE_PROVIDER_ERROR')
    def tick(self):return pub.run(self.args,self.runner,lambda:NOW)
    def pending(self):return self.args.state_directory/'delivery/pending.json'
    def sends(self):return [x for x in self.calls if x[0][1]=='sqs']
    def test_sql_ubuntu_cli_v1_has_no_v2_only_pager_flag(self):
        self.tick();argv,options=self.sends()[0]
        self.assertNotIn('--no-cli-pager',argv)
        self.assertEqual(options['env']['AWS_PAGER'],'')
        self.assertEqual(options['env']['AWS_MAX_ATTEMPTS'],'1')
        self.assertEqual(options['env']['AWS_SHARED_CREDENTIALS_FILE'],os.devnull)
    def test_actual_check_candidate_and_explicit_acceptance(self):
        self.assertEqual(self.tick()['Acceptance'],'SQS_ONLY_NOT_SENTINEL_OR_EMAIL')
        event=json.loads(self.sends()[0][0][self.sends()[0][0].index('--message-body')+1])
        self.assertEqual((event['Evaluation'],event['CheckInvoked'],event['Status']),('CHECK_COMMAND_RESULT',True,'MISSING'))
        self.assertEqual(event['Delivery'],'NONE');self.assertFalse(event['SentinelIntegrated']);self.assertFalse(event['RemediationAllowed'])
        self.assertFalse(self.pending().exists())
    def test_unknown_acceptance_preserves_exact_payload_and_no_new_check(self):
        self.accept=False;self.assertEqual(self.tick()['Status'],'PENDING');old=self.pending().read_bytes();checks=len([x for x in self.calls if x[0][1]=='check'])
        self.assertEqual(self.tick()['Status'],'PENDING');current=json.loads(self.pending().read_text());previous=json.loads(old);self.assertEqual(current['Payload'],previous['Payload']);self.assertEqual(current['PayloadSha256'],previous['PayloadSha256']);self.assertEqual(current['Attempts'],2)
        self.accept=True;self.assertEqual(self.tick()['Status'],'ENQUEUED')
        self.assertEqual(len([x for x in self.calls if x[0][1]=='check']),checks)
        self.assertEqual(len(set(x[0][x[0].index('--message-body')+1] for x in self.sends())),1)
    def test_candidate_is_durable_before_observer_state_advances(self):
        original=observer.save
        def fail_state(path,value):
            if path.name=='observer-state.json':raise OSError('synthetic crash')
            return original(path,value)
        with patch.object(observer,'save',side_effect=fail_state),self.assertRaises(OSError):self.tick()
        self.assertTrue(self.pending().exists());self.assertFalse((self.args.state_directory/'observer-state.json').exists());self.assertEqual(len(self.sends()),0)
        self.assertEqual(self.tick()['Status'],'ENQUEUED');self.assertEqual(len([x for x in self.calls if x[0][1]=='check']),1)
    def test_scope_change_does_not_flush_old_candidate(self):
        self.accept=False;self.tick();self.args.run_id='ecs-sentinel-other'
        with self.assertRaises(pub.Refused):self.tick()
        self.assertEqual(len(self.sends()),1);self.assertTrue(self.pending().exists())
    def test_config_change_does_not_flush_old_candidate(self):
        self.accept=False;self.tick();self.config.write_text('{"Changed":true}')
        with self.assertRaises(pub.Refused):self.tick()
        self.assertEqual(len(self.sends()),1)
    def test_payload_corruption_not_sent(self):
        self.accept=False;self.tick();item=json.loads(self.pending().read_text());item['Payload']='{}';self.pending().write_text(json.dumps(item))
        with self.assertRaises(pub.Refused):self.tick()
        self.assertEqual(len(self.sends()),1)
    def test_no_credentials_profile_or_endpoint_environment_forwarded(self):
        with patch.dict(os.environ,{'AWS_PROFILE':'synthetic-profile','AWS_ACCESS_KEY_ID':'synthetic-key','AWS_SECRET_ACCESS_KEY':'synthetic-secret','AWS_ENDPOINT_URL':'https://invalid.example'}):self.tick()
        env=self.sends()[0][1]['env']
        for name in ['AWS_PROFILE','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_ENDPOINT_URL']:self.assertNotIn(name,env)
        self.assertEqual(env['AWS_SHARED_CREDENTIALS_FILE'],os.devnull);self.assertEqual(env['AWS_MAX_ATTEMPTS'],'1')
        self.assertEqual(env['AWS_EC2_METADATA_V1_DISABLED'],'true')
    def test_healthy_unchanged_forwarded_for_reducer_confirmation(self):
        self.status='HEALTHY';self.tick();self.tick()
        events=[json.loads(x[0][x[0].index('--message-body')+1]) for x in self.sends()]
        self.assertEqual([e['Reason'] for e in events],['BASELINE_HEALTHY','UNCHANGED'])
    def test_maintenance_no_check_no_send(self):
        self.args.expected_up='false';self.assertEqual(self.tick()['Status'],'SUPPRESSED');self.assertEqual(self.calls,[])
    def test_invalid_queue_and_replay_gates_refused(self):
        self.args.account='https://invalid'
        with self.assertRaises(pub.Refused):self.tick()
        self.assertEqual(self.calls,[]);self.args.account='000000000000';self.args.action='replay'
        with self.assertRaises(pub.Refused):self.tick()
        self.assertEqual(self.calls,[])
    def test_malformed_success_receipt_stays_pending(self):
        def fake(argv,**kw):
            if argv[1]=='check':return self.runner(argv,**kw)
            return subprocess.CompletedProcess(argv,0,b'{"MessageId":"bad\\nreceipt"}',b'')
        self.assertEqual(pub.run(self.args,fake,lambda:NOW)['Status'],'PENDING');self.assertTrue(self.pending().exists())
    def test_denial_blocks_future_automatic_send(self):
        def denied(argv,**kwargs):
            if argv[1]=='check':return self.runner(argv,**kwargs)
            self.calls.append((argv,kwargs));return subprocess.CompletedProcess(argv,254,b'',b'An error occurred (AccessDenied) when calling SendMessage: PRIVATE')
        with self.assertRaisesRegex(pub.Refused,'PUBLISH_ACCESS_DENIED'):pub.run(self.args,denied,lambda:NOW)
        with self.assertRaisesRegex(pub.Refused,'PUBLISH_BLOCKED'):self.tick()
        self.assertEqual(len(self.sends()),1)
    def test_attempt_bound_survives_restart(self):
        self.accept=False
        for i in range(3):self.assertEqual(self.tick()['Status'],'PENDING')
        with self.assertRaisesRegex(pub.Refused,'ATTEMPT_BUDGET_EXHAUSTED'):self.tick()
        self.assertEqual(len(self.sends()),3)
    def test_expired_window_does_not_check_or_send(self):
        self.args.expires_at='2026-10-23T18:00:00Z'
        with self.assertRaisesRegex(pub.Refused,'WINDOW_EXPIRED'):self.tick()
        self.assertEqual(self.calls,[])
    def test_private_pending_directory(self):
        self.accept=False;self.tick()
        if os.name=='posix':
            self.assertEqual(self.pending().stat().st_mode&0o777,0o600)
            self.assertEqual(self.pending().parent.stat().st_mode&0o777,0o700)

if __name__=='__main__':unittest.main()
