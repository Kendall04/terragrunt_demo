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
 def test_dev_alert_email_optional_preserves_topic_and_prod(self):
  main=(ROOT/'terraform/modules/target/dev/shared/ordinary-main.tf').read_text()
  variables=(ROOT/'terraform/modules/target/dev/shared/ordinary-variables.tf').read_text()
  self.assertIn('resource "aws_sns_topic" "alerts"',main)
  self.assertIn('kms_master_key_id = "alias/aws/sns"',main)
  self.assertIn('count     = var.alert_email == null ? 0 : 1',main)
  self.assertIn('default     = null',variables)
  prod=(ROOT/'terraform/modules/target/prod/shared/ordinary-variables.tf').read_text()
  self.assertNotIn('default     = null',prod)
  self.assertNotIn('count = var.alert_email', (ROOT/'terraform/modules/target/prod/shared/ordinary-main.tf').read_text())
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

 def test_nat_launch_permission_uses_actual_two_templates_and_no_state_authority(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-5.json').read_text())
  expected=['arn:aws:ec2:us-east-1:341936017254:launch-template/'+v for v in ('lt-04ab8d2ec1f975f96','lt-0b3ed490a53f8dfe7')]
  for stmt in policy['Statement']:
   self.assertTrue(set(stmt['Action']) <= {'ec2:RunInstances','ec2:CreateTags'})
   self.assertNotIn('*',stmt['Resource']);self.assertNotIn('prod',json.dumps(stmt))
   self.assertEqual(stmt['Condition']['StringEquals']['aws:RequestedRegion'],'us-east-1')
   if stmt['Action']==['ec2:RunInstances']:
    self.assertEqual(stmt['Condition']['ArnEquals']['ec2:LaunchTemplate'],expected)
  self.assertEqual(policy['Statement'][1]['Condition']['StringEquals']['ec2:MetadataHttpTokens'],'required')
  self.assertEqual(policy['Statement'][2]['Condition']['StringEquals']['ec2:CreateAction'],'RunInstances')

 def test_second_cycle_nat_launch_rebinds_only_observed_network(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-5.json').read_text())
  resources=policy['Statement'][0]['Resource']
  self.assertEqual({r for r in resources if ':subnet/' in r or ':security-group/' in r},{
   'arn:aws:ec2:us-east-1:341936017254:subnet/subnet-0c0015acb0147b62e',
   'arn:aws:ec2:us-east-1:341936017254:subnet/subnet-07cfc3b9ed3fe5a77',
   'arn:aws:ec2:us-east-1:341936017254:security-group/sg-05a0c795917e7b133'})
  for row in policy['Statement']:
   self.assertEqual(row['Condition']['StringEquals']['aws:RequestedRegion'],'us-east-1')
   self.assertTrue(set(row['Action'])<={'ec2:RunInstances','ec2:CreateTags'})

 def test_sql_permission_has_exact_profile_ami_subnet_sg_and_no_state_authority(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-6.json').read_text())
  self.assertEqual(policy['Statement'][0]['Resource'][:3],[
   'arn:aws:ec2:us-east-1::image/ami-062944a84867f2386',
   'arn:aws:ec2:us-east-1:341936017254:subnet/subnet-08302f1ff29ca5338',
   'arn:aws:ec2:us-east-1:341936017254:security-group/sg-0b1d1c8829de734e6'])
  cond=policy['Statement'][1]['Condition']
  self.assertEqual(cond['ArnEquals']['ec2:InstanceProfile'],'arn:aws:iam::341936017254:instance-profile/demo-dev-data-sql-ec2-profile')
  self.assertEqual(cond['StringEquals']['ec2:MetadataHttpTokens'],'required')
  self.assertEqual(cond['StringEquals']['aws:RequestTag/Environment'],'dev')
  self.assertEqual(cond['StringEquals']['aws:RequestTag/Project'],'demo')
  for row in policy['Statement']:
   self.assertTrue(set(row['Action'])<={'ec2:RunInstances','ec2:CreateTags','ec2:DescribeInstanceCreditSpecifications','ec2:DescribeInstanceTypes','secretsmanager:DescribeSecret'})
   self.assertNotIn('prod',json.dumps(row))

 def test_dev_inert_task_has_no_awslogs_without_execution_role(self):
  import ordinary
  doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());generated=ordinary.wiring(doc)
  dev=generated['terraform/modules/target/dev/apps/modules/ecs_service/locals.tf']
  self.assertNotIn('logConfiguration',dev)
  self.assertNotIn('execution_role_arn',generated['terraform/modules/target/dev/apps/modules/ecs_service/taskdef.tf'])
  self.assertEqual(generated['terraform/modules/target/dev/apps/ordinary-demo.tf'].count('enable_execute_command = false'),2)
  self.assertNotIn('enable_execute_command = false',generated['terraform/modules/target/prod/apps/ordinary-demo.tf'])
  self.assertIn('aws_cloudwatch_log_group',generated['terraform/modules/target/dev/apps/modules/ecs_service/logs.tf'])
  self.assertNotIn('aws_region',generated['terraform/modules/target/dev/apps/modules/ecs_service/logs.tf'])
  self.assertIn('logConfiguration',generated['terraform/modules/target/prod/apps/modules/ecs_service/locals.tf'])
  template=json.loads((ROOT/'demo-api/deploy/task-definition.template.json').read_text())
  self.assertTrue(all(c['logConfiguration']['logDriver']=='awslogs' for c in template['containerDefinitions']))
  self.assertIn('executionRoleArn',template)
 def test_secret_preflight_only_metadata_of_three_installed_dev_secrets(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-6.json').read_text())
  rows=[s for s in policy['Statement'] if 'secretsmanager:DescribeSecret' in s['Action']]
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['Action'],['secretsmanager:DescribeSecret'])
  self.assertEqual(set(rows[0]['Resource']),{'arn:aws:secretsmanager:us-east-1:341936017254:secret:'+v for v in ('demo/dev/db/sql-sa-password-30fCjc','demo/dev/db/sql-app-password-2Shh56','demo/dev/app/db-connection-string-72ytze')})
  self.assertNotIn('GetSecretValue',json.dumps(policy));self.assertEqual(rows[0]['Condition']['StringEquals']['aws:RequestedRegion'],'us-east-1')
 def test_original_log_permissions_and_api_create_scopes(self):
  logs=json.loads((ROOT/'scripts/first_deployment/operator-policy-7.json').read_text())
  expected={'arn:aws:logs:us-east-1:341936017254:log-group:'+name+suffix for name in ('/aws/ecs/demo-dev-app-api-blue','/aws/ecs/demo-dev-app-api-green','/aws/apigw/demo-dev-edge-http-access') for suffix in ('',':*')}
  for row in logs['Statement'][:2]:
   self.assertEqual(set(row['Resource']),expected);self.assertEqual(row['Condition']['StringEquals']['aws:RequestedRegion'],'us-east-1')
   self.assertTrue(set(row['Action'])<={'logs:CreateLogGroup','logs:TagResource','logs:PutRetentionPolicy','logs:DeleteLogGroup','logs:ListTagsForResource'})
  api=json.loads((ROOT/'scripts/first_deployment/operator-policy-8.json').read_text())
  self.assertEqual(api['Statement'][0]['Condition']['StringEquals']['apigateway:Request/ApiName'],'demo-dev-edge')
  self.assertEqual(api['Statement'][1]['Condition']['StringEquals']['aws:RequestTag/Name'],'demo-dev-edge-vpc-link')
  for row in api['Statement']:
   self.assertTrue(all(a.startswith('apigateway:') for a in row['Action']));self.assertEqual(row['Condition']['StringEquals']['aws:RequestedRegion'],'us-east-1')
   self.assertNotIn('prod',json.dumps(row));self.assertNotIn('iam:',json.dumps(row))

 def test_first_down_permissions_only_read_exact_deleting_resources(self):
  logs=json.loads((ROOT/'scripts/first_deployment/operator-policy-7.json').read_text())
  self.assertEqual(len(logs['Statement']),3);row=logs['Statement'][2]
  self.assertEqual(row['Action'],['logs:ListLogDeliveries']);self.assertEqual(row['Resource'],['*'])
  self.assertEqual(row['Condition'],{'StringEquals':{'aws:RequestedRegion':'us-east-1'}})
  api=json.loads((ROOT/'scripts/first_deployment/operator-policy-8.json').read_text())
  self.assertEqual(len(api['Statement']),6);row=api['Statement'][5]
  self.assertEqual(row['Action'],['apigateway:GET'])
  self.assertEqual(set(row['Resource']),{'arn:aws:apigateway:us-east-1::/apis/427id1ezuk','arn:aws:apigateway:us-east-1::/apis/427id1ezuk/*','arn:aws:apigateway:us-east-1::/vpclinks/xt9msp'})
  self.assertEqual(row['Condition'],{'StringEquals':{'aws:RequestedRegion':'us-east-1'}})
  self.assertNotIn('DELETE',json.dumps(row));self.assertNotIn('Put',json.dumps(logs['Statement'][2]))

 def test_ecs_definition_read_has_only_required_regional_wildcard(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-9.json').read_text())
  self.assertEqual(policy['Version'],'2012-10-17');self.assertEqual(policy['Statement'][0],{'Sid':'RegionalDescribeTaskDefinitionRequiresWildcard','Effect':'Allow','Action':['ecs:DescribeTaskDefinition'],'Resource':['*'],'Condition':{'StringEquals':{'aws:RequestedRegion':'us-east-1'}}})
 def test_task_read_is_limited_to_original_dev_cluster_and_never_mutates(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-9.json').read_text())
  self.assertEqual(len(policy['Statement']),8)
  self.assertEqual(policy['Statement'][1],{'Sid':'DescribeOnlyOriginalDevClusterTasks','Effect':'Allow','Action':['ecs:DescribeTasks'],'Resource':['arn:aws:ecs:us-east-1:341936017254:task/demo-dev-platform-main-cluster/*'],'Condition':{'StringEquals':{'aws:RequestedRegion':'us-east-1'}}})
  self.assertEqual({a for row in policy['Statement'][:2] for a in row['Action']},{'ecs:DescribeTaskDefinition','ecs:DescribeTasks'})
  for row,action,suffix in zip(policy['Statement'][2:4],('logs:DescribeLogStreams','logs:GetLogEvents'),(':*',':log-stream:*')):
   self.assertEqual(row['Action'],[action]);self.assertEqual(row['Condition'],{'StringEquals':{'aws:RequestedRegion':'us-east-1'}})
   self.assertEqual(set(row['Resource']),{'arn:aws:logs:us-east-1:341936017254:log-group:/aws/lambda/e1-nat-recovery-nat-dev-'+d+suffix for d in ('assign-eip','change-rt','disable-sdc')})
   self.assertNotIn('prod',json.dumps(row));self.assertNotIn('s3:',json.dumps(row));self.assertNotIn('Delete',json.dumps(row))
 def test_shutdown_observation_additions_are_read_only_and_region_bound(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-9.json').read_text())
  rows=policy['Statement'][4:];self.assertEqual(len(rows),4)
  self.assertEqual(set(rows[0]['Resource']),{'arn:aws:lambda:us-east-1:341936017254:function:e1-nat-recovery-nat-dev-'+d for d in ('assign-eip','change-rt','disable-sdc')})
  self.assertEqual(rows[0]['Action'],['lambda:ListVersionsByFunction'])
  self.assertEqual(rows[1]['Resource'],['arn:aws:events:us-east-1:341936017254:rule/e1-wp4-dev-nat-launch']);self.assertEqual(rows[1]['Action'],['events:DescribeRule'])
  self.assertEqual(set(rows[2]['Resource']),{'arn:aws:sqs:us-east-1:341936017254:e1-wp4-dev-nat-'+d+'-failed' for d in ('delivery','execution')})
  self.assertEqual(set(rows[2]['Action']),{'sqs:GetQueueUrl','sqs:GetQueueAttributes'})
  self.assertEqual(rows[3]['Resource'],['*']);self.assertEqual(set(rows[3]['Action']),{'autoscaling:DescribeLifecycleHooks','autoscaling:DescribeWarmPool','autoscaling:DescribeScheduledActions','autoscaling:DescribePolicies','cloudwatch:GetMetricStatistics'})
  for row in rows:
   self.assertEqual(row['Condition'],{'StringEquals':{'aws:RequestedRegion':'us-east-1'}})
   self.assertTrue(all(a.split(':')[1].startswith(('Get','List','Describe')) for a in row['Action']))
   self.assertNotIn('prod',json.dumps(row));self.assertNotIn('s3:',json.dumps(row));self.assertNotIn('iam:',json.dumps(row))

 def test_sql_existing_volume_tagging_is_exact_not_general_mutation(self):
  policy=json.loads((ROOT/'scripts/first_deployment/operator-policy-6.json').read_text())
  row=next(v for v in policy['Statement'] if v.get('Sid')=='TagOnlyObservedOriginalSqlRootVolume')
  self.assertEqual(row['Action'],['ec2:CreateTags']);self.assertEqual(row['Resource'],['arn:aws:ec2:us-east-1:341936017254:volume/vol-0206bcb0b6b243e3a'])
  self.assertEqual(row['Condition']['StringEquals'],{'aws:RequestedRegion':'us-east-1','aws:RequestTag/Environment':'dev','aws:RequestTag/Project':'demo','aws:RequestTag/ManagedBy':'terraform','aws:RequestTag/Owner':'kendall','aws:RequestTag/Role':'root-ebs'})
  self.assertEqual(set(row['Condition']['ForAllValues:StringEquals']['aws:TagKeys']),{'Environment','Project','ManagedBy','Owner','Role'})

if __name__=='__main__':
 from hermetic import install
 install();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));raise SystemExit(not result.wasSuccessful())
