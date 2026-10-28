"""Actual durable journal with explicit collector/CLI doubles; no AWS requests."""
import copy,datetime as dt,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import publisher as pub
from test_bridge import configs,example,T
class PublisherTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.c,self.m=configs();self.now=dt.datetime.fromisoformat(T.replace('Z','+00:00'));self.checks=0;self.calls=[];self.responses=[]
  self.backup=self.root/'backup.json';self.backup.write_text('{"Database":"synthetic"}')
  self.args=SimpleNamespace(action='run',aws=True,ec2_role=True,portable=True,account=self.m['account'],region=self.m['region'],subject=self.c['subject'],expires_at=(self.now+dt.timedelta(hours=23)).isoformat(),state_directory=self.root/'state',config=self.backup,aws_cli=Path(sys.executable).resolve())
 def tearDown(self):self.temp.cleanup()
 def observe(self):
  self.checks+=1;e=example();e.update(ObservedUtc=self.now.isoformat(),Evaluation='CHECK_COMMAND_RESULT',CheckInvoked=True);return e
 def port(self,cmd,**options):
  self.calls.append((cmd,options));entries=json.loads(cmd[cmd.index('--entries')+1]);value=self.responses.pop(0) if self.responses else {'FailedEntryCount':0,'Entries':[{'EventId':'accepted-'+str(len(self.calls))+'-'+str(i)} for i,_ in enumerate(entries)]}
  if isinstance(value,BaseException):raise value
  if isinstance(value,subprocess.CompletedProcess):return value
  return subprocess.CompletedProcess(cmd,0,json.dumps(value).encode(),b'')
 def tick(self):return pub.run(self.args,self.c,self.m,self.port,lambda:self.now,self.observe)
 def ledger(self):return json.loads((self.args.state_directory/'portable-delivery/journal.json').read_text())
 def sent(self,i=-1):return json.loads(self.calls[i][0][self.calls[i][0].index('--entries')+1])
 def test_first_batch_counts_two_entries_and_does_not_claim_sentinel_delivery(self):
  result=self.tick();self.assertEqual((result['Status'],result['Attempts'],result['AcceptedEntries']),('ACCEPTED',2,2));self.assertEqual(len(self.sent()),2);self.assertIn('NOT_SENTINEL_OR_EMAIL',result['Acceptance'])
 def test_partial_success_retries_only_failed_entry_before_collecting_new(self):
  self.responses=[{'FailedEntryCount':1,'Entries':[{'EventId':'accepted-backup'},{'ErrorCode':'ThrottlingException'}]}];self.assertEqual(self.tick()['Status'],'PENDING');payload=self.sent()[1]
  self.now+=dt.timedelta(minutes=5);r=self.tick();self.assertEqual((r['Attempts'],self.checks),(3,1));self.assertEqual(self.sent(),[payload]);self.assertEqual(self.ledger()['Entries'][0]['EventId'],'accepted-backup')
 def test_reordered_response_is_applied_by_position_not_event_id_sort(self):
  self.responses=[{'FailedEntryCount':1,'Entries':[{'ErrorCode':'ThrottlingException'},{'EventId':'accepted-heartbeat'}]}];self.tick();payload=self.sent()[0];self.tick();self.assertEqual(self.sent(),[payload])
 def test_unknown_response_preserves_exact_reports_and_debits_before_retry(self):
  self.responses=[{'FailedEntryCount':0,'Entries':[]}];self.assertTrue(self.tick()['MayDuplicateOnRetry']);first=self.sent();self.tick();self.assertEqual(self.sent(),first);self.assertEqual(self.checks,1);self.assertEqual(sum(e['Attempts'] for e in self.ledger()['Entries']),4)
 def test_global_budget_is_twenty_entries_not_twenty_batches(self):
  for _ in range(10):self.tick();self.now+=dt.timedelta(minutes=5)
  self.assertEqual(len(self.calls),10);self.assertEqual(sum(len(self.sent(i)) for i in range(10)),20)
  with self.assertRaisesRegex(ValueError,'TOTAL_ENTRY_ATTEMPTS'):self.tick()
  self.assertEqual(self.checks,10);self.assertTrue((self.args.state_directory/'portable-delivery/journal.json').is_file())
 def test_max_three_attempts_per_pending_entry_survives_reconstruction(self):
  self.responses=[{'FailedEntryCount':2,'Entries':[{'ErrorCode':'ThrottlingException'},{'ErrorCode':'InternalFailure'}]}]*3
  for _ in range(3):self.tick()
  with self.assertRaisesRegex(ValueError,'PER_ENTRY_ATTEMPTS'):self.tick()
  self.assertEqual((len(self.calls),self.checks),(3,1));self.assertEqual([e['Attempts'] for e in self.ledger()['Entries']],[3,3])
 def test_crash_after_reservation_consumes_attempts_with_no_new_observation(self):
  self.responses=[KeyboardInterrupt()]
  with self.assertRaises(KeyboardInterrupt):self.tick()
  self.assertEqual([e['Attempts'] for e in self.ledger()['Entries']],[1,1]);self.tick();self.assertEqual(self.checks,1);self.assertEqual([e['Attempts'] for e in self.ledger()['Entries']],[2,2])
 def test_access_denied_blocks_instead_of_automatic_retry(self):
  self.responses=[subprocess.CompletedProcess([],255,b'',b'An error occurred (AccessDeniedException) SECRET-DO-NOT-ECHO')];self.assertEqual(self.tick()['Status'],'BLOCKED')
  with self.assertRaisesRegex(ValueError,'BLOCKED_REQUIRES_REVIEW'):self.tick()
  self.assertEqual((len(self.calls),self.checks),(1,1));self.assertNotIn('SECRET-DO-NOT-ECHO',json.dumps(self.ledger()))
 def test_partial_denial_preserves_accepted_and_blocks_remaining(self):
  self.responses=[{'FailedEntryCount':1,'Entries':[{'EventId':'accepted'},{'ErrorCode':'NotAuthorizedForSourceException'}]}];self.tick();self.assertEqual([e['Status'] for e in self.ledger()['Entries']],['ACCEPTED','BLOCKED'])
  with self.assertRaisesRegex(ValueError,'BLOCKED'):self.tick()
 def test_inconsistent_failure_count_is_unknown_not_false_success(self):
  self.responses=[{'FailedEntryCount':0,'Entries':[{'EventId':'one'},{'ErrorCode':'InternalFailure'}]}];r=self.tick();self.assertEqual((r['Status'],r['AcceptedEntries']),('PENDING',0))
 def test_timeout_never_discards_or_relabels_unknown_as_healthy(self):
  self.responses=[subprocess.TimeoutExpired('local-double',1)];r=self.tick();self.assertEqual(r['Status'],'PENDING');self.assertFalse(r['CloudHealthProven']);self.assertEqual(len(self.ledger()['Entries']),2)
 def test_changed_binding_expiry_config_or_cap_cannot_reset_budget(self):
  self.tick();self.args.expires_at=(self.now+dt.timedelta(hours=22)).isoformat()
  with self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):self.tick()
  self.assertEqual(len(self.calls),1)
 def test_corrupt_payload_refuses_before_transport(self):
  self.tick();p=self.args.state_directory/'portable-delivery/journal.json';j=self.ledger();j['Entries'][0]['Entry']['Source']='aws.fake';p.write_text(json.dumps(j))
  with self.assertRaisesRegex(ValueError,'DRIFT'):self.tick()
  self.assertEqual(len(self.calls),1)
 def test_same_observation_never_republishes_accepted_entries(self):self.tick();self.assertEqual(self.tick()['Status'],'NO_PENDING');self.assertEqual(len(self.calls),1)
 def test_expiry_refuses_before_collection_and_existing_pending_is_kept(self):
  self.responses=[OSError('synthetic')];self.tick();before=self.ledger();self.now+=dt.timedelta(hours=24)
  with self.assertRaisesRegex(ValueError,'WINDOW_EXPIRED'):self.tick()
  self.assertEqual(self.ledger(),before);self.assertEqual(self.checks,1)
 def test_credentials_endpoints_profiles_and_cli_v2_flags_are_not_forwarded(self):
  old=dict(os.environ)
  try:
   os.environ.update(AWS_ACCESS_KEY_ID='DO_NOT_FORWARD',AWS_SECRET_ACCESS_KEY='DO_NOT_FORWARD',AWS_SESSION_TOKEN='DO_NOT_FORWARD',AWS_PROFILE='DO_NOT_FORWARD',AWS_ENDPOINT_URL='DO_NOT_FORWARD',SQL_BACKUP_CONNECTION_STRING='DO_NOT_FORWARD');self.tick()
  finally:os.environ.clear();os.environ.update(old)
  cmd,options=self.calls[0];self.assertNotIn('DO_NOT_FORWARD',json.dumps(options));self.assertNotIn('--profile',cmd);self.assertNotIn('--endpoint-url',cmd);self.assertNotIn('--no-cli-pager',cmd);self.assertEqual(options['env']['AWS_MAX_ATTEMPTS'],'1')
 def test_stale_owner_lock_is_not_stolen_or_force_cleaned(self):
  self.args.state_directory.mkdir(mode=0o700);directory=self.args.state_directory/'portable-delivery';directory.mkdir(mode=0o700);(directory/'observer.lock').write_text('prior-unknown-owner')
  with self.assertRaisesRegex(ValueError,'ACTIVE_OR_INTERRUPTED'):self.tick()
  self.assertEqual(len(self.calls),0);self.assertTrue((directory/'observer.lock').exists())
 def test_no_implicit_portable_opt_in(self):
  self.args.portable=False
  with self.assertRaisesRegex(ValueError,'OPT_IN'):self.tick()
  self.assertEqual(self.checks,0)
 def test_last_global_slot_sends_one_entry_and_keeps_other_pending(self):
  self.responses=[{'FailedEntryCount':1,'Entries':[{'EventId':'backup'},{'ErrorCode':'InternalFailure'}]}];self.tick();self.tick()
  for _ in range(8):self.now+=dt.timedelta(minutes=5);self.tick()
  self.now+=dt.timedelta(minutes=5);result=self.tick();self.assertEqual((result['Attempts'],result['PendingEntries']),(20,1));self.assertEqual(len(self.sent()),1)
  pending=[e for e in self.ledger()['Entries'] if e['Status']=='PENDING'];self.assertEqual(len(pending),1);self.assertEqual(pending[0]['Attempts'],0)
  with self.assertRaisesRegex(ValueError,'TOTAL_ENTRY_ATTEMPTS'):self.tick()
if __name__=='__main__':unittest.main(verbosity=2)
