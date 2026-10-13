"""Hermetic first-session bootstrap/publication tests; never cloud proof."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT),str(HERE.parent/'authority'),str(HERE.parent/'security_root'),str(HERE.parent/'ownership_publication'),str(HERE.parent/'wp4d')]
from scripts import first_dev_bootstrap as b
import publication as pub,ownership
from test_wp2d import Admin,output_fixture
ACCOUNT='111122223333';ARN='arn:aws:iam::'+ACCOUNT+':user/BootstrapUser'

class Fake:
 def __init__(self):self.account=ACCOUNT;self.calls=[];self.collision=False;self.wrong=False;self.missing=False;self.fail=False;self.document=None
 def call(self,*args):
  self.calls.append(args);action=args[1]
  if action=='get-caller-identity':return dict(Account='999999999999' if self.wrong else ACCOUNT,Arn=ARN)
  if action=='list-buckets':return dict(Buckets=[{'Name':'terragrunt-demo-security-'+ACCOUNT+'-us-east-1'}] if self.collision else [])
  if action=='create-bucket' and self.fail:raise OSError('ambiguous dispatch')
  if action=='put-bucket-policy':self.document=json.loads(args[-1])
  if action=='get-bucket-policy':return dict(Policy=json.dumps(self.document))
  if action=='get-bucket-location':return dict(LocationConstraint=None)
  if action=='get-bucket-versioning':return dict(Status='Suspended' if self.missing else 'Enabled')
  if action=='get-public-access-block':return dict(PublicAccessBlockConfiguration={k:True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')})
  if action=='get-bucket-encryption':return dict(ServerSideEncryptionConfiguration=dict(Rules=[dict(ApplyServerSideEncryptionByDefault=dict(SSEAlgorithm='AES256'))]))
  if action=='get-bucket-ownership-controls':return dict(OwnershipControls=dict(Rules=[dict(ObjectOwnership='BucketOwnerEnforced')]))
  return {}

class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name);self.aws=Fake()
 def run_bootstrap(self):return b.bootstrap(self.aws,self.dir,'CREATE SECURITY BACKEND '+ACCOUNT+' us-east-1')
 def test_new_backend_verified_and_retained(self):
  value=self.run_bootstrap();self.assertTrue(value['retained_after_down']);self.assertEqual(value['terraform_lock_execution'],'NOT_YET_TESTED');self.assertEqual(self.aws.document,b.policy(value['bucket'],ARN))
 def test_wrong_account_before_mutation(self):
  self.aws.wrong=True
  with self.assertRaises(ValueError):self.run_bootstrap()
  self.assertEqual(len(self.aws.calls),1)
 def test_confirmation_before_cloud_access(self):
  with self.assertRaises(ValueError):b.bootstrap(self.aws,self.dir,'CREATE PROD')
  self.assertFalse(self.aws.calls)
 def test_existing_bucket_never_adopted(self):
  self.aws.collision=True
  with self.assertRaises(ValueError):self.run_bootstrap()
  self.assertNotIn('create-bucket',[x[1] for x in self.aws.calls])
 def test_readback_failure_not_success(self):
  self.aws.missing=True
  with self.assertRaises(ValueError):self.run_bootstrap()
  self.assertFalse((self.dir/'security-backend-verified.json').exists())
 def test_ambiguous_creation_never_resends(self):
  self.aws.fail=True
  with self.assertRaises(OSError):self.run_bootstrap()
  self.aws.fail=False
  with self.assertRaises(FileExistsError):self.run_bootstrap()
  self.assertEqual([x[1] for x in self.aws.calls].count('create-bucket'),1)
 def dev_records(self):
  self.doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());return {k:v for k,v in output_fixture(self.doc).items() if v['scope']=='dev'}
 def test_authentic_port_dev_scope_preserves_full_schema(self):
  records=self.dev_records();admin=Admin(records);v=pub.publish_outputs(self.doc,ACCOUNT,'us-east-1',admin,dev_only=True);self.assertEqual(v['schema'],'E1_DEV_OUTPUT_PUBLICATION_V1');self.assertTrue(all(r['scope']=='dev' for r in v['records'].values()))
  doc=pub.promote_outputs(self.doc,ACCOUNT,'us-east-1',admin,dev_only=True);ownership.validate_publications(doc)
  self.assertEqual(set(pub.consume(doc,ACCOUNT,'us-east-1','dev/data',admin)),set(doc['ownership_closure']['consumers']['dev/data']))
  with self.assertRaises(ValueError):pub.consume(doc,ACCOUNT,'us-east-1','prod/data',admin)
  with self.assertRaises(ValueError):pub.consume(doc,ACCOUNT,'us-east-1','dev/shared',admin)
  self.assertNotEqual(pub.output_key(doc,ACCOUNT,'us-east-1'),pub.output_key(doc,ACCOUNT,'us-east-1',True))
 def test_injected_prod_and_missing_dev_rejected(self):
  records=self.dev_records();records['prod/kms']=copy.deepcopy(records['dev/kms'])
  with self.assertRaises(ValueError):pub.publish_outputs(self.doc,ACCOUNT,'us-east-1',Admin(records),True)
  records=self.dev_records();records.pop('dev/kms')
  with self.assertRaises(ValueError):pub.publish_outputs(self.doc,ACCOUNT,'us-east-1',Admin(records),True)
 def test_caller_json_not_an_admin_channel(self):
  records=self.dev_records()
  with self.assertRaises(ValueError):pub.publish_outputs(self.doc,ACCOUNT,'us-east-1',records,True)
 def test_dev_runtime_lock_has_only_required_provider(self):
  for layer in ('global','data','platform','apps','edge'):
   lock=(ROOT/'terraform/modules/target/dev'/layer/'.terraform.lock.hcl').read_text();self.assertIn('hashicorp/aws',lock);self.assertNotIn('hashicorp/tls',lock)
   self.assertIn('hashicorp/tls',(ROOT/'terraform/modules/target/prod'/layer/'.terraform.lock.hcl').read_text())

 def test_public_profile_requires_same_operator_and_region(self):
  from scripts.practical_dev import Process
  config=dict(profile='cnp-cert-dev',region='us-east-1',operator_arn='arn:aws:iam::'+ACCOUNT+':role/DemoDevOperator')
  file=self.dir/'operator.config';raw='[profile cnp-cert-dev]\nregion=us-east-1\nsource_profile=cnp-cert-dev\nrole_arn='+config['operator_arn']+'\nrole_session_name=demo\nduration_seconds=3600\nca_bundle=C:/public-ca.pem\n'
  file.write_text(raw);self.assertEqual(Process(config,file).aws_config_file,file.resolve())
  for changed in (raw.replace('us-east-1','us-west-2'),raw.replace('role/DemoDevOperator','role/Foreign'),raw+'aws_access_key_id=FORBIDDEN\n',raw+'credential_process=arbitrary\n'):
   file.write_text(changed)
   with self.assertRaises(ValueError):Process(config,file)
 def test_dev_publication_does_not_change_prod_package(self):
  import wp5
  self.dev_records();before=copy.deepcopy(self.doc);before['ownership_closure']['publications']={}
  after=copy.deepcopy(before);admin=Admin(self.dev_records());pub.publish_outputs(after,ACCOUNT,'us-east-1',admin,True);after=pub.promote_outputs(after,ACCOUNT,'us-east-1',admin,True)
  for binding in wp5.BINDINGS:
   if binding.endswith('-prod'):self.assertEqual(wp5.artifact(ROOT,before,binding),wp5.artifact(ROOT,after,binding))

 def test_flow_log_creation_scopes_both_parent_and_new_resource(self):
  p2=json.loads((ROOT/'scripts/first_deployment/operator-policy-2.json').read_text())
  p4=json.loads((ROOT/'scripts/first_deployment/operator-policy-4.json').read_text())
  parent=[s for s in p2['Statement'] if 'ec2:CreateFlowLogs' in s.get('Action',[])]
  child=[s for s in p4['Statement'] if 'ec2:CreateFlowLogs' in s.get('Action',[])]
  self.assertEqual(len(parent),1);self.assertEqual(len(child),1)
  self.assertEqual(parent[0]['Resource'],['arn:aws:ec2:us-east-1:341936017254:vpc/*'])
  self.assertEqual(child[0]['Resource'],['arn:aws:ec2:us-east-1:341936017254:vpc-flow-log/*'])
  self.assertEqual(child[0]['Action'],['ec2:CreateFlowLogs'])
  self.assertEqual(child[0]['Condition']['StringEquals'],{'aws:RequestedRegion':'us-east-1','aws:RequestTag/Environment':'dev','aws:RequestTag/Project':'demo'})
  self.assertEqual(parent[0]['Condition']['StringEquals']['aws:ResourceTag/Environment'],'dev')
 def test_sql_output_references_observed_instance_ami(self):
  text=(ROOT/'terraform/modules/target/dev/data/ordinary-outputs.tf').read_text()
  self.assertIn('aws_instance.db.ami',text);self.assertNotIn('data.aws_ami.ubuntu_2204',text)

 def nat_network(self):
  import wp4d
  from test_wp4d import installed_projection,ACCOUNT as A,REGION as R
  doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());installs,images,bindings=installed_projection(doc)
  net={key:value for key,value in bindings['dev'].items() if key in wp4d.NAT_ENV_FIELDS}
  net.update(schema='E1_WP4D_PROTECTED_NAT_NETWORK_V1',repository='demo-dev-shared-demo-ms')
  for slot,side in zip(net['nat_slots'],('a','b')):slot['asg']='demo-dev-asg-nat-'+side
  return wp4d,doc,installs,images,net,A,R
 def test_dev_nat_bootstrap_needs_only_actual_network_binding(self):
  module,doc,i,r,net,a,region=self.nat_network()
  ready=module.creation_supported(doc,i,r,{'dev':net},a,region)
  self.assertEqual(set(ready),{'nat-recovery/nat-dev/'+d for d in ('assign_eip','change_rt','disable_sdc')})
  self.assertNotIn('colors',net);self.assertNotIn('cleanup',net)
 def test_nat_network_cannot_authorize_prod_or_application(self):
  module,doc,i,r,net,a,region=self.nat_network()
  self.assertEqual(module.creation_supported(doc,i,r,{'prod':net},a,region),[])
  for field,value in (('account','999999999999'),('region','us-west-2'),('owner','CALLER'),('environment','prod'),('colors',{})):
   bad=copy.deepcopy(net);bad[field]=value
   self.assertEqual(module.creation_supported(doc,i,r,{'dev':bad},a,region),[])
 def test_nat_bootstrap_preserves_installation_and_exact_slot_guards(self):
  module,doc,i,r,net,a,region=self.nat_network()
  for mutate in (lambda n:n['nat_slots'][0].update(asg='unrelated'),lambda n:n['nat_slots'][0]['spec'].update(http_tokens='optional'),lambda n:n['nat_slots'][0]['spec'].update(instance_profile='arn:aws:iam::'+a+':instance-profile/foreign')):
   bad=copy.deepcopy(net);mutate(bad);self.assertEqual(module.creation_supported(doc,i,r,{'dev':bad},a,region),[])
  i={};self.assertEqual(module.creation_supported(doc,i,r,{'dev':net},a,region),[])

if __name__=='__main__':
 from hermetic import install
 install();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));raise SystemExit(not result.wasSuccessful())
