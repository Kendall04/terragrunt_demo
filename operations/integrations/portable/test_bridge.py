"""Pure projection tests; generated events are synthetic, no command/transport executed."""
from pathlib import Path
import copy,json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bridge
T='2026-10-26T03:00:00Z'
def example(status='HEALTHY'):
 pairs=bridge.signals.PAIRS
 return {'SchemaVersion':1,'Source':'SqlBackup.Observer','Subject':'dev-sql-backups','ObservedUtc':T,'Status':status,'Code':pairs[status],'Severity':'OK' if status=='HEALTHY' else 'UNKNOWN' if status=='UNKNOWN' else 'MAINTENANCE' if status=='MAINTENANCE' else 'ATTENTION','LastSuccessUtc':'2026-10-26T02:59:00Z' if status=='HEALTHY' else '2026-10-26T00:00:00Z' if status=='STALE' else None,'ProducerFailureCoverage':'LOCAL_RECEIPT_ONLY','Emit':status not in ('HEALTHY','MAINTENANCE'),'Reason':'BASELINE_HEALTHY' if status=='HEALTHY' else 'MAINTENANCE' if status=='MAINTENANCE' else 'INITIAL_ATTENTION','Delivery':'NONE','SentinelIntegrated':False,'RemediationAllowed':False,'Evaluation':'EXPECTED_UP_FALSE' if status=='MAINTENANCE' else 'LOCAL_RECEIPT_REPLAY','CheckInvoked':False}
def configs():
 d=Path(__file__).parent;return json.loads((d/'bridge.local.json').read_text()),json.loads((d/'sentinel.local.json').read_text())
class BridgeTests(unittest.TestCase):
 def setUp(self):self.c,self.m=configs()
 def send(self,e=None,**kw):return bridge.project(json.dumps(e if e is not None else example()),self.c,self.m,T,kw.get('mode','local-replay'))
 def test_two_expectations_only_no_false_restore_or_sql_probe(self):
  r=self.send();self.assertEqual(len(r),2);a,b=map(lambda x:json.loads(x['Detail']),r)
  self.assertEqual((a['monitor'],a['verdict'],a['assurance'],a['backupType']),('sql-backup','Pass','Artifact','full'))
  self.assertEqual((b['monitor'],b['verdict'],b['assurance']),('sql-telemetry','Pass','Reported'))
  self.assertNotIn('RestoreTested',json.dumps(r));self.assertIn('COPY_ONLY',a['detail'])
 def test_duplicate_and_json_reorder_keep_ids(self):
  e=example();a=self.send(e);self.assertEqual(a,self.send(dict(reversed(list(e.items())))));self.assertEqual(a,self.send(e))
 def test_old_backup_new_tick_preserves_data_time_and_run_not_id(self):
  a=json.loads(self.send()[0]['Detail']);e=example();e['ObservedUtc']='2026-10-26T03:05:00Z'
  b=json.loads(bridge.project(json.dumps(e),self.c,self.m,e['ObservedUtc'],'local-replay')[0]['Detail'])
  self.assertEqual((a['dataAt'],a['runId']),(b['dataAt'],b['runId']));self.assertNotEqual(a['id'],b['id'])
 def test_stale_is_old_data_not_fresh_success(self):
  a=json.loads(self.send(example('STALE'))[0]['Detail']);self.assertEqual(a['dataAt'],'2026-10-26T00:00:00Z');self.assertNotEqual(a['dataAt'],a['observedAt'])
 def test_ambiguous_failure_missing_unknown_never_claim_confirmed_failure(self):
  for status in ['FAILED','MISSING','UNKNOWN']:
   a,b=map(lambda x:json.loads(x['Detail']),self.send(example(status)));self.assertEqual(a['verdict'],'Unknown');self.assertEqual(b['verdict'],'Pass')
 def test_missing_private_producer_receipt_never_healthy(self):
  e=example();e['ProducerFailureCoverage']='NOT_PROVIDED';a=json.loads(self.send(e)[0]['Detail']);self.assertEqual((a['verdict'],a['assurance']),('Unknown','Reported'))
 def test_maintenance_silent_and_no_false_external_health(self):self.assertEqual(self.send(example('MAINTENANCE')),[])
 def test_strict_input_no_secret_or_false_delivery_field(self):
  for k,v in [('Password','DO_NOT_PRINT'),('Delivery','EMAIL'),('SentinelIntegrated',True),('RemediationAllowed',True),('Source','aws.cloudwatch'),('Subject','other'),('Code','fake'),('Emit','false'),('Reason','fake')]:
   e=example();e[k]=v
   with self.assertRaises((ValueError,TypeError)):self.send(e)
 def test_duplicate_property_and_oversize_refused(self):
  with self.assertRaisesRegex(ValueError,'DUPLICATE'):bridge.project(json.dumps(example()).replace('"SchemaVersion": 1','"SchemaVersion": 1, "SchemaVersion": 1'),self.c,self.m,T,'local-replay')
  with self.assertRaises(ValueError):bridge.read_unique('x'*65537)
 def test_modes_cannot_promote_replay_as_native(self):
  with self.assertRaisesRegex(ValueError,'EVALUATION'):self.send(mode='check-result')
  e=example();e.update(Evaluation='CHECK_COMMAND_RESULT',CheckInvoked=True);self.assertEqual(len(self.send(e,mode='check-result')),2)
 def test_future_observation_or_success_refused(self):
  for k in ['ObservedUtc','LastSuccessUtc']:
   e=example();e[k]='2099-01-01T00:00:00Z'
   with self.assertRaises(ValueError):self.send(e)
 def test_copy_only_must_be_explicit(self):
  self.c['includeCopyOnly']=False
  with self.assertRaisesRegex(ValueError,'COPY_ONLY'):self.send()
 def test_foreign_account_and_extra_monitor_refused(self):
  self.m['account']='000000000000'
  with self.assertRaises(ValueError):self.send()
  self.c,self.m=configs();self.m['monitors'].append(copy.deepcopy(self.m['monitors'][0]))
  with self.assertRaises(ValueError):self.send()
 def test_foreign_source_assurance_or_native_reader_refused(self):
  for field,value in [('sources',['aws-observer']),('requiredAssurance','RestoreTested'),('kind','rds-backup')]:
   self.c,self.m=configs();self.m['monitors'][0][field]=value
   with self.assertRaises(ValueError):self.send()
if __name__=='__main__':unittest.main(verbosity=2)
