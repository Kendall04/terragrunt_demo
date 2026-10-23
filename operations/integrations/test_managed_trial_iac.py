"""Focused offline creation/retirement contract tests; not CloudFormation/IAM service validation."""
import copy,json,os,unittest
from pathlib import Path
import managed_trial_iac as iac
HERE=Path(__file__).resolve().parent
class TrialContract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Path(os.environ['SENTINEL_SOURCE_ROOT']);cls.scope=json.loads((HERE/'OPERATIONAL-SCOPE-PROPOSAL.json').read_text(encoding='utf-8'));cls.products=iac.build(cls.scope,cls.source)
  cls.main=cls.products['trial-template.json'];cls.boot=cls.products['bootstrap-template.json'];cls.trial_id=cls.scope['runId']
 def test_original_storage_reused_and_retention_not_ttl(self):
  original=json.loads((self.source/'tools/aws-sandbox/cloudformation.json').read_text(encoding='utf-8'))['Resources']
  table=self.main['Resources']['Sentinel'];self.assertEqual(table['Properties']['GlobalSecondaryIndexes'],original['Sentinel']['Properties']['GlobalSecondaryIndexes'])
  self.assertNotIn('TimeToLiveSpecification',table['Properties']);self.assertEqual(table['DeletionPolicy'],'Retain');self.assertEqual(self.main['Resources']['Archive']['DeletionPolicy'],'Retain')
  self.assertEqual(self.main['Resources']['Archive']['Properties']['BucketEncryption'],original['Archive']['Properties']['BucketEncryption'])
 def test_no_business_network_compute_or_repair_resources(self):
  types={x['Type'] for x in self.main['Resources'].values()};self.assertEqual(len(self.main['Resources']),16);self.assertEqual(len(self.boot['Resources']),3)
  self.assertFalse(any(t.startswith(('AWS::EC2','AWS::RDS','AWS::ECS','AWS::Events','AWS::Scheduler','AWS::KMS')) for t in types))
 def test_original_ingress_limits_and_inert_activation(self):
  p=self.main['Resources']['Mapping']['Properties'];self.assertEqual(p['BatchSize'],5);self.assertFalse(p['Enabled']);self.assertEqual(p['FunctionResponseTypes'],['ReportBatchItemFailures']);self.assertEqual(p['ScalingConfig']['MaximumConcurrency'],2)
  self.assertEqual(self.main['Parameters']['DeployRuntime']['Default'],'false')
  for n in ['IngestFunction','DispatchFunction']:
   p=self.main['Resources'][n]['Properties'];self.assertEqual(p['Code']['S3ObjectVersion'],{'Ref':'PackageVersion'});self.assertEqual(p['Runtime'],'dotnet10');self.assertNotIn('AWS_REGION',p['Environment']['Variables']);self.assertNotIn('VpcConfig',p)
 def test_missing_owner_decisions_have_no_invented_defaults(self):
  for n in ['NotificationEmail','NotificationMode','SenderLabel','Owner','LogRetentionDays','QueueRetentionSeconds','DlqRetentionSeconds','EvidenceSeconds','BudgetSeconds','CheckSeconds','HoldSeconds','AuditSeconds','EffectSeconds','DedupSeconds','SignalAgeSeconds','StartsAt','ExpiresAt']:
   self.assertNotIn('Default',self.main['Parameters'][n]);self.assertIsNone(self.products['required-decisions.json'][n])
 def test_runtime_permissions_have_no_iam_nat_secrets_or_email_identity_creation(self):
  for component,p in self.products['runtime-policies.json'].items():
   for s in p['Statement']:
    self.assertFalse(any(a.split(':')[0] in {'ec2','autoscaling','iam','kms','secretsmanager','ses'} for a in s['Action']))
    for resource in ([s['Resource']] if isinstance(s['Resource'],str) else s['Resource']):self.assertIn(self.trial_id,resource)
   role=self.main['Resources'][component.capitalize()+'Role']['Properties'];self.assertEqual(role['Policies'][0]['PolicyDocument'],p)
   self.assertEqual(self.boot['Resources'][component.capitalize()+'Boundary']['Properties']['PolicyDocument'],p);self.assertTrue(role['PermissionsBoundary'].endswith('-'+component+'-boundary'))
 def test_dynamo_foreign_namespace_excluded_structurally(self):
  for p in self.products['runtime-policies.json'].values():
   s=next(s for s in p['Statement'] if 'dynamodb:GetItem' in s['Action']);c=s['Condition'];self.assertEqual(c['Null'],{'dynamodb:LeadingKeys':'false'})
   self.assertEqual(c['ForAllValues:StringEquals']['dynamodb:LeadingKeys'],[self.scope['bindings']['dynamoNamespace']]);self.assertNotIn('NS#foreign',c['ForAllValues:StringEquals']['dynamodb:LeadingKeys'])
 def test_cfn_cannot_escape_runtime_boundaries_or_edit_itself(self):
  ss=self.boot['Resources']['ExecutionRole']['Properties']['Policies'][0]['PolicyDocument']['Statement'];actions={a for s in ss for a in s['Action']}
  self.assertTrue({'iam:CreateRole','iam:DeleteRole','iam:PutRolePolicy','iam:DeleteRolePolicy'}<=actions)
  self.assertFalse({'iam:CreatePolicy','iam:CreatePolicyVersion','iam:DeleteRolePermissionsBoundary','iam:AttachRolePolicy','iam:UpdateAssumeRolePolicy'}&actions)
  for s in ss:
   if 'iam:CreateRole' in s['Action']:
    self.assertIn(s['Resource'].split('/')[-1].replace('-role','-boundary'),s['Condition']['StringEquals']['iam:PermissionsBoundary'])
   for a in s['Action']:
    if a.startswith('iam:'):self.assertNotIn('-cfn',s['Resource'])
 def test_delete_path_covers_all_owned_types(self):
  ss=self.boot['Resources']['ExecutionRole']['Properties']['Policies'][0]['PolicyDocument']['Statement'];actions={a for s in ss for a in s['Action']}
  self.assertTrue({'dynamodb:DeleteTable','s3:DeleteBucket','s3:DeleteBucketPolicy','sqs:DeleteQueue','lambda:DeleteFunction','lambda:DeleteEventSourceMapping','logs:DeleteLogGroup','sns:Unsubscribe','sns:DeleteTopic','iam:DeleteRolePolicy','iam:DeleteRole'}<=actions)
  operator={a for s in self.products['operator-temporary-policy.json']['Statement'] for a in s['Action']};self.assertTrue({'s3:DeleteObject','s3:DeleteObjectVersion','s3:ListBucketVersions','s3:DeleteBucket','dynamodb:DeleteTable','cloudformation:DeleteStack'}<=operator)
 def test_mapping_unknown_uuid_wildcards_remain_function_bound(self):
  ss=self.boot['Resources']['ExecutionRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
  s=next(s for s in ss if 'lambda:CreateEventSourceMapping' in s['Action']);self.assertEqual(s['Resource'],'*');self.assertTrue(s['Condition']['ArnEquals']['lambda:FunctionArn'].endswith(self.trial_id+'-ingest'))
  for s in ss:
   if 'lambda:DeleteEventSourceMapping' in s['Action']:self.assertEqual(s['Condition']['ArnEquals']['lambda:FunctionArn'],next(x for x in ss if 'lambda:CreateEventSourceMapping' in x['Action'])['Condition']['ArnEquals']['lambda:FunctionArn'])
 def test_subscription_permissions_use_topic_arn_not_subscription_uuid(self):
  ss=self.boot['Resources']['ExecutionRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
  for s in ss:
   if 'sns:Unsubscribe' in s['Action']:self.assertTrue(s['Resource'].endswith(self.trial_id+'-notices'));self.assertNotIn('*',s['Resource'])
   if 'sns:Subscribe' in s['Action']:self.assertEqual(s['Condition']['StringEquals']['sns:Endpoint'],{'Ref':'NotificationEmail'})
 def test_account_region_guard_and_name_validation(self):
  c=self.main['Conditions']['BoundEnvironment']['Fn::And'];self.assertIn({'Fn::Equals':[{'Ref':'AWS::AccountId'},self.scope['account']]},c);self.assertIn({'Fn::Equals':[{'Ref':'AWS::Region'},self.scope['region']]},c)
  wrong=copy.deepcopy(self.scope);wrong['runId']='../../foreign';self.assertRaises(ValueError,iac.build,wrong,self.source)
 def test_frozen_package_and_base_only_version_guard(self):
  frozen=iac.build(self.scope,self.source,'a'*64)['trial-template.json']
  self.assertEqual(frozen['Parameters']['PackageKey']['AllowedValues'],['packages/'+('a'*64)+'.zip'])
  self.assertEqual(frozen['Parameters']['PackageVersion']['Default'],'BASE_ONLY_UNPUBLISHED')
  self.assertIn('RuntimePackagePublished',frozen['Rules']);self.assertRaises(ValueError,iac.build,self.scope,self.source,'untrusted-key')
 def test_templates_below_inline_cloudformation_limit(self):
  for n in ['trial-template.json','bootstrap-template.json']:self.assertLess(len(json.dumps(self.products[n],indent=2).encode()),51200)
if __name__=='__main__':unittest.main()
