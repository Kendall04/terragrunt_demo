"""Offline source-contract checks only; not Terraform provider/schema/plan execution."""
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'terraform/infra/sentinel-backup'
MODULE=BASE/'modules/pipeline/main.tf.json'
class TerraformContractTests(unittest.TestCase):
    def setUp(self):
        self.x=json.loads(MODULE.read_text());self.r=self.x['resource'];self.root=json.loads((BASE/'main.tf.json').read_text())
    def test_one_owner_no_cloudformation_or_provisioner(self):
        self.assertEqual(self.root['module']['pipeline']['source'],'./modules/pipeline')
        self.assertNotRegex(json.dumps(self.x).lower(),r'cloudformation|local-exec|remote-exec|provisioner|ignore_changes|aws_secretsmanager|aws_instance|aws_autoscaling|aws_nat|aws_kms')
    def test_boundaries_and_inline_same_narrow_capabilities(self):
        for component in ['ingest','dispatch']:
            b=self.r['aws_iam_policy'][component+'_boundary']['policy']
            self.assertEqual(b,self.r['aws_iam_role_policy'][component]['policy'])
            d=json.loads(b[len('${jsonencode('):-2])
            for s in d['Statement']:
                if s['Effect']=='Allow':
                    self.assertNotIn('*',s['Action'])
                    self.assertTrue(all(a.split(':')[0] in ['dynamodb','logs','sqs','s3','sns'] for a in s['Action']))
            self.assertEqual(self.r['aws_iam_role_policy'][component]['role'],'${aws_iam_role.'+component+'.id}')
    def test_original_physical_table_schema(self):
        t=self.r['aws_dynamodb_table']['state']
        self.assertEqual((t['hash_key'],t['range_key']),('PK','SK'))
        self.assertEqual({i['name']:(i['hash_key'],i['range_key'],i['projection_type']) for i in t['global_secondary_index']},{'Due':('DuePK','DueSK','KEYS_ONLY'),'Active':('ActivePK','ActiveSK','KEYS_ONLY'),'Cleanup':('CleanPK','CleanSK','KEYS_ONLY')})
    def test_original_namespace_derived_no_arbitrary_override(self):
        self.assertEqual(self.x['locals']['binding_hash'],'${sha256(jsonencode([var.config.project,"sandbox",var.config.run_id]))}')
        self.assertNotIn('runtime_binding',self.x['variable'])
    def test_immutable_artifact_with_runtime_binding(self):
        c=self.r['aws_s3_object']['code']
        self.assertEqual(c['key'],'packages/${var.config.artifact_sha256}.zip')
        self.assertIn('filesha256',json.dumps(c['lifecycle']))
        for f in self.r['aws_lambda_function'].values():
            self.assertEqual(f['s3_object_version'],'${aws_s3_object.code.version_id}')
            self.assertEqual(f['runtime'],'dotnet10');self.assertNotIn('filename',f)
            self.assertIn('filebase64sha256',f['source_code_hash'])
            self.assertEqual(f['environment']['variables']['SENTINEL_MODE'],'${var.config.mode}')
    def test_old_artifact_refused_by_manifest_contract(self):
        v=json.dumps(self.x['variable']['config']['validation'])
        for field in ['integrationContractVersion','ecs-backup-managed-v3','supportedModes','sourceCommit','zipSha256','upstreamCommit']:self.assertIn(field,v)
    def test_data_guards_and_default_disabled_ingress(self):
        self.assertFalse(self.x['variable']['enable_ingestion']['default'])
        self.assertFalse(self.x['variable']['allow_data_retirement']['default'])
        self.assertEqual(self.r['aws_dynamodb_table']['state']['deletion_protection_enabled'],'${!var.allow_data_retirement}')
        self.assertFalse(self.r['aws_s3_bucket']['archive']['force_destroy'])
        self.assertEqual(self.r['aws_s3_bucket_versioning']['archive']['versioning_configuration']['status'],'Enabled')
        self.assertTrue(all(v is True for k,v in self.r['aws_s3_bucket_public_access_block']['archive'].items() if k!='bucket'))
    def test_each_queue_policy_has_scalar_exact_resource(self):
        for name,p in self.r['aws_sqs_queue_policy'].items():
            d=json.loads(p['policy'][len('${jsonencode('):-2])
            self.assertTrue(all(isinstance(s['Resource'],str) for s in d['Statement']))
            if name=='ingestion':self.assertIn('sender_role_arn',p['policy'])
    def test_sender_iam_is_proposal_not_existing_role_mutation(self):
        self.assertIn('sender_policy_proposal',self.x['output'])
        self.assertEqual(set(self.r['aws_iam_role']),{'ingest','dispatch'})
        self.assertNotIn('aws_iam_role_policy_attachment',self.r)
    def test_no_unreviewed_dispatch_schedule(self):
        self.assertFalse(self.x['variable']['enable_dispatch_schedule']['default'])
        self.assertFalse(self.x['variable']['dispatch_schedule_enabled']['default'])
        self.assertIn('var.dispatch_schedule_enabled',self.r['aws_cloudwatch_event_rule']['dispatch']['state'])
        self.assertIsNone(self.x['variable']['dispatch_schedule_expression']['default'])
        self.assertEqual(self.r['aws_cloudwatch_event_rule']['dispatch']['count'],'${var.enable_dispatch_schedule ? 1 : 0}')
        permission=self.r['aws_lambda_permission']['dispatch_schedule']
        self.assertEqual(permission['principal'],'events.amazonaws.com')
        self.assertEqual(permission['source_arn'],'${aws_cloudwatch_event_rule.dispatch[0].arn}')
        self.assertEqual(permission['source_account'],'${var.config.account}')
        self.assertNotIn('aws_scheduler_schedule',self.r)
        self.assertEqual(self.r['aws_lambda_function']['dispatch']['handler'],'Ecs.Backup.Managed::Ecs.Backup.Managed.DispatchFunction::Reconcile')
    def test_isolated_partial_backend_no_credentials_or_account_default(self):
        tg=(ROOT/'terraform/live/sentinel-backup/terragrunt.hcl').read_text()
        for key in ['SENTINEL_STATE_BUCKET','SENTINEL_STATE_ID','SENTINEL_STATE_REGION','SENTINEL_INPUTS_FILE']:self.assertIn('get_env("'+key+'")',tg)
        self.assertNotIn('profile',tg);self.assertNotIn('assume_role',tg);self.assertIn('sentinel-backup/',tg)
        self.assertEqual(self.root['provider']['aws']['allowed_account_ids'],['${var.config.account}'])
    def test_runtime_utc_and_integer_duration_admission(self):
        for source in [self.x,self.root]:
            rules=json.dumps(source['variable']['config']['validation'])
            for field in ['evidence_seconds','budget_seconds','check_seconds','hold_seconds','dedup_seconds','signal_age_seconds','audit_seconds','effect_seconds']:
                self.assertIn('floor(var.config.'+field+')',rules)
            self.assertIn('Z$',rules)
    def test_provider_pin_isolated_no_fake_lock(self):
        self.assertEqual(self.root['terraform']['required_providers']['aws']['version'],'= 6.27.0')
        self.assertIn('version     = "6.27.0"',(BASE/'.terraform.lock.hcl').read_text())
        self.assertIn('h1:',(BASE/'.terraform.lock.hcl').read_text())
        self.assertIn('version     = "5.100.0"',(ROOT/'terraform/infra/security/.terraform.lock.hcl').read_text())
if __name__=='__main__':unittest.main()
