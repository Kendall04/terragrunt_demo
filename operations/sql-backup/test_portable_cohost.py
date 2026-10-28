"""Portable mode staging uses disposable POSIX roots. No service manager, AWS or credentials."""
import copy,datetime as dt,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
import cohost,test_host
P=Path(__file__).resolve().parents[1]/'integrations/portable';sys.path.insert(0,str(P));import cohost_runtime as portable
NOW=dt.datetime(2026,10,26,3,tzinfo=dt.timezone.utc)
class PortableCohost(unittest.TestCase):
 def setUp(self):
  test_host.PackageTests.setUp(self);self.archive=self.root/'portable.tar';self.sha=test_host.package.build(self.publish,self.archive,'a'*40,True,with_portable=True)['Sha256'];self.backup=json.loads(self.config.read_text());self.backup['ProposedMaxAgeHours']=2;self.config.write_text(json.dumps(self.backup));self.settings=self.root/'sentinel.json'
  self.value={'SchemaVersion':1,'Placement':'SQL_HOST','Account':'341936017254','Region':'us-east-1','RunId':'ecs-sentinel-r20261026p1','Subject':'dev-sql-backups','StartsAt':'2026-10-26T00:00:00Z','ExpiresAt':'2026-10-27T00:00:00Z','CadenceSeconds':300,'ReminderSeconds':0,'PublishAttempts':3,'WatchdogSeconds':1200,'ExpectedUp':True,'Portable':{'SchemaVersion':1,'ContractSha256':hashlib.sha256((P/'cohost-contract.json').read_bytes()).hexdigest()}};self.settings.write_text(json.dumps(self.value))
 def tearDown(self):test_host.PackageTests.tearDown(self)
 def stage(self):return test_host.package.install(self.archive,self.sha,self.config,self.fixture,self.user,True,None,self.settings)
 def test_inert_idempotent_stage_and_eventbridge_unit(self):
  self.assertEqual(self.stage()['Status'],'STAGED_NOT_ENABLED');self.assertEqual(self.stage()['Status'],'ALREADY_INSTALLED');self.assertEqual(cohost.verify(self.fixture,NOW)['Status'],'VERIFIED_LOCAL_INSTALL')
  unit=(self.fixture/'etc/systemd/system/sql-backup-sentinel-producer.service').read_text();self.assertIn('/portable/cohost_runtime.py run',unit);self.assertNotIn('sentinel_publish.py',unit);self.assertNotIn('LoadCredential=',unit);self.assertIn('SendSIGKILL=no',unit)
  self.assertFalse((self.fixture/'etc/systemd/system/timers.target.wants').exists());self.assertFalse((self.fixture/'etc/terragrunt-demo/sql-backup/credentials').exists())
 def test_observer_activation_does_not_require_or_start_producer(self):
  self.stage();plan=cohost.activate(self.fixture,now=NOW);self.assertEqual(plan['Component'],'observer');self.assertNotIn('sql-backup-producer.target',str(plan['Actions']))
  with self.assertRaisesRegex(ValueError,'CREDENTIALS_REQUIRED'):cohost.activate(self.fixture,now=NOW,component='producer')
 def test_legacy_package_cannot_accept_portable_settings(self):
  old=self.root/'legacy.tar';sha=test_host.package.build(self.publish,old,'a'*40,True)['Sha256']
  with self.assertRaisesRegex(ValueError,'TRANSPORT_OPT_IN'):test_host.package.install(old,sha,self.config,self.fixture,self.user,True,None,self.settings)
 def test_portable_package_requires_explicit_settings(self):
  value=copy.deepcopy(self.value);value.pop('Portable');self.settings.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'TRANSPORT_OPT_IN'):self.stage()
 def test_altered_contract_hash_refused(self):
  value=copy.deepcopy(self.value);value['Portable']['ContractSha256']='0'*64
  with self.assertRaisesRegex(ValueError,'CONTRACT_HASH'):cohost.validate(value,self.backup)
 def test_identity_cadence_age_and_opt_in_are_bound(self):
  for delta in [{'RunId':'ecs-sentinel-foreign'},{'Subject':'foreign'},{'PublishAttempts':2},{'CadenceSeconds':600},{'WatchdogSeconds':1800}]:
   with self.subTest(delta=delta),self.assertRaises(ValueError):cohost.validate(self.value|delta,self.backup)
  with self.assertRaisesRegex(ValueError,'FRESHNESS'):cohost.validate(self.value,self.backup|{'ProposedMaxAgeHours':168})
 def test_damaged_installed_bridge_refuses_start(self):
  self.stage();p=self.fixture/'opt/terragrunt-demo/sql-backup/portable/bridge.py';p.write_bytes(p.read_bytes()+b'\n')
  with self.assertRaisesRegex(ValueError,'FILE_DRIFT'):cohost.verify(self.fixture,NOW)
 def test_role_delta_is_exact_bus_source_type_and_window(self):
  result=portable.integration(self.value,self.backup);s=result['SqlRoleEventBridgeDelta']['Statement'][0];self.assertEqual(s['Action'],'events:PutEvents');self.assertEqual(s['Resource'],'arn:aws:events:us-east-1:341936017254:event-bus/ecs-portable-r20261026p1');self.assertEqual(s['Condition']['StringEquals']['events:source'],'sentinel.report.sql-observer');self.assertEqual(s['Condition']['StringEquals']['events:detail-type'],'Sentinel Observation v1');self.assertFalse(result['LegacySqsSendRequired']);self.assertFalse(result['ExecutionAuthorized']);self.assertNotIn('kms:',json.dumps(s));self.assertNotIn('sqs:',json.dumps(s))
 def test_packaged_contract_cannot_override_two_expectations(self):
  raw=json.loads((P/'cohost-contract.json').read_bytes());raw['Installation']['monitors'][0]['requiredAssurance']='Reported';fake=self.root/'tampered.json';fake.write_text(json.dumps(raw));value=copy.deepcopy(self.value);value['Portable']['ContractSha256']=hashlib.sha256(fake.read_bytes()).hexdigest()
  with self.assertRaisesRegex(ValueError,'MONITOR_PROFILE'):portable.validate(value,self.backup,fake)
 def test_default_entrypoint_has_no_collector_or_transport_override(self):
  source=(P/'cohost_runtime.py').read_text();self.assertIn("sys.argv[1:]==['run']",source);self.assertIn('cohost.verify()',source);self.assertNotIn('observe=',source)
if __name__=='__main__':unittest.main(verbosity=2)
