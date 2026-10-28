"""CURRENT source-scope proofs keep collisions, mutations and unknown context visible."""
import json
from pathlib import Path
import tempfile
import unittest
from current_controls import resource_policy_scope, schema_scope, SCHEMAS, disjoint_function, s3_policy_target, s3_logging_targets, disjoint_s3
from discovery import Discovery
from evaluator import Unsupported

ROOT = Path(__file__).resolve().parents[3]
KNOWN = 'demo-dev-shared-github-dev-deploy'
ROLE = '''locals {
 prefix = var.prefix
 keys = toset(["worker", "ingestion", "watchdog", "cleanup"])
}
resource "aws_iam_role" "runtime" {
 for_each = local.keys
 name = "${local.prefix}-${each.key}"
 assume_role_policy = var.trust
}
resource "aws_iam_role_policy" "runtime" {
 for_each = local.keys
 role = aws_iam_role.runtime[each.key].id
 policy = var.policy
}
'''


class CurrentSourceControls(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='e1-current-scope-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def put(self, text):
        p = self.root/'main.tf'; p.write_text(text,encoding='utf-8');return p

    def discover(self, text, names=(KNOWN,)):
        self.put(text)
        return Discovery(self.root, names=names)

    def test_finite_same_instance_attachment_keeps_own_permission_unknown(self):
        d=self.discover(ROLE)
        rows=[r for r in d.records if r['declaration']['kind']=='resource']
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['affects'],rows[1]['affects'])
        self.assertEqual(len(rows[0]['affects']),4)
        self.assertTrue(all(r['admission']=='UNSUPPORTED_APPLICABLE' for r in rows))
        self.assertEqual(d.taints('github'),[])
        self.assertEqual(len(d.taints_for_role('demo-dev-worker','elsewhere')),2)

    def test_instance_profile_metadata_preserves_target_scope(self):
        text = ROLE.split('resource "aws_iam_role_policy"')[0] + '''
resource "aws_iam_instance_profile" "node" {
 for_each = local.keys
 role = aws_iam_role.runtime[each.key].name
 name = "node-${each.key}"
 path = "/lab/"
 tags = { Project = "demo" }
}
'''
        self.assertEqual(self.discover(text).taints('github'), [])
        self.assertTrue(self.discover(text.replace('tags =', 'unreviewed_control =')).taints('github'))

    def test_finite_key_collision_with_queried_identity_stays_global(self):
        d=self.discover(ROLE.replace('"worker"','"shared-github-dev-deploy"'))
        self.assertEqual(len(d.taints('github')),2)
        self.assertTrue(all('*' in r['affects'] for r in d.taints('github')))

    def test_mismatched_index_or_expansion_cannot_inherit_role_proof(self):
        for old,new in (('runtime[each.key].id','runtime["worker"].id'),
                        ('role = aws_iam_role.runtime[each.key].id','role = var.foreign_role'),
                        ('policy = var.policy','policy = var.policy\n for_each = var.keys')):
            with self.subTest(new=new):
                d=self.discover(ROLE.replace(old,new));self.assertTrue(d.taints('github'))

    def test_dynamic_duplicate_cyclic_and_escaped_roles_fail_closed(self):
        for old,new in (('keys = toset(["worker", "ingestion", "watchdog", "cleanup"])','keys = var.keys'),
                        ('"cleanup"]','"worker"]'),
                        ('keys = toset(["worker", "ingestion", "watchdog", "cleanup"])','keys = local.keys'),
                        ('${local.prefix}-${each.key}','$${local.prefix}-${each.key}')):
            with self.subTest(new=new):self.assertTrue(self.discover(ROLE.replace(old,new)).taints('github'))

    def test_role_or_attachment_hook_is_not_scoped_away(self):
        for marker in (' assume_role_policy = var.trust',' policy = var.policy'):
            d=self.discover(ROLE.replace(marker,marker+'\n provisioner "local-exec" {\n command = "unexecuted"\n }'))
            self.assertTrue(d.taints('github'))

    def test_workload_role_collision_is_retained_even_if_github_disjoint(self):
        d=self.discover(ROLE)
        self.assertEqual(d.taints('github'),[])
        self.assertEqual(len(d.taints_for_role('arn:aws:iam::111122223333:role/name-ingestion','other/module')),2)

    def test_real_portable_files_remain_all_visible_and_unsupported(self):
        d=Discovery(ROOT,names=(KNOWN,))
        rows=[r for r in d.records if r['source'].startswith('operations/integrations/portable/')]
        # All previous declarations plus security inputs, metadata, owned logging and
        # outputs remain visible; applicable controls are still UNKNOWN.
        self.assertEqual(len(rows),86)
        receipt=[r for r in rows if r['source']=='operations/integrations/portable/trial/main.tf'
                 and r.get('declaration',{}).get('kind')=='output'
                 and r.get('declaration',{}).get('id')=='operations/integrations/portable/trial/main.tf#output:package_manifest_sha256:']
        self.assertEqual(len(receipt),1)
        self.assertEqual(receipt[0]['admission'],'NON_SECURITY_RELEVANT')
        self.assertEqual(receipt[0]['affects'],[])
        self.assertEqual(sum(r['admission']=='UNSUPPORTED_APPLICABLE' for r in rows),44)
        self.assertTrue(any(r.get('mechanism_schema')=='aws_dynamodb_table' for r in rows))
        self.assertEqual(sum(bool(r.get('policy_action_domain')) for r in rows),5)

    def test_resource_policy_action_scope_is_query_specific_not_a_grant(self):
        text='''resource "aws_sns_topic_policy" "x" {
 arn = aws_sns_topic.x.arn
 policy = jsonencode({ Version = "2012-10-17", Statement = [{Effect="Deny",Principal="*",Action="sns:*",Resource=aws_sns_topic.x.arn,Condition={Bool={"aws:SecureTransport"="false"}}}] })
}
'''
        d=self.discover(text);r=d.records[0]
        self.assertEqual(r['admission'],'UNSUPPORTED_APPLICABLE')
        self.assertEqual(len(d.taints('api:sns',action='sns:Publish',resource='arn:aws:sns:us-east-1:111122223333:x')),1)
        self.assertEqual(d.taints('github',action='sts:AssumeRole'),[])
        self.assertEqual(len(d.taints('api:sns')),1)

    def test_policy_cross_service_action_and_extra_deny_taint_actual_query(self):
        body='''resource "aws_s3_bucket_policy" "x" {
 bucket=aws_s3_bucket.x.id
 policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal="*",Action="s3:GetObject",Resource="*"}, {Effect="Deny",Principal="*",Action="iam:PassRole",Resource="*"}]})
}'''
        d=self.discover(body)
        self.assertTrue(d.taints('api:iam',action='iam:PassRole'))
        self.assertEqual(d.taints('api:sts',action='sts:AssumeRole'),[])

    def test_notaction_unmodeled_fields_and_dynamic_actions_stay_global(self):
        template='''resource "aws_sqs_queue_policy" "x" {
 queue_url=aws_sqs_queue.x.id
 policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal="*",Action="sqs:SendMessage",Resource="*"}]})
}'''
        for old,new in (('Action=','NotAction='),('Action="sqs:SendMessage"','Action=var.actions'),
                        ('Principal="*"','Principal={Unknown="*"}'),('Resource="*"','Resource=evil()'),
                        ('Effect="Allow"','Effect="Allow",Effect="Deny"')):
            with self.subTest(new=new):self.assertTrue(self.discover(template.replace(old,new)).taints('github'))

    def test_wildcard_policy_actions_stay_applicable_to_any_api(self):
        text='''resource "aws_sns_topic_policy" "x" {
 arn=aws_sns_topic.x.arn
 policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Deny",Principal="*",Action="*",Resource="*"}]})
}'''
        self.assertTrue(self.discover(text).taints('github',action='sts:AssumeRole'))

    def test_missing_context_or_resource_binding_is_not_assumed_safe(self):
        text='''resource "aws_s3_bucket_policy" "x" {
 bucket=aws_s3_bucket.x.id
 policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Deny",Principal="*",Action="s3:*",Resource=var.resource,Condition={Bool={"aws:SecureTransport"="false"}}}]})
}'''
        d=self.discover(text)
        self.assertEqual(len(d.taints('api:s3',action='s3:PutObject',resource='arn:aws:s3:::unbound/key')),1)

    def test_conditional_policy_union_and_sourcearn_comprehension_are_inspected(self):
        text='''queue_url=aws_sqs_queue.x.id
policy=jsonencode({Version="2012-10-17",Statement=length(local.producers)>0 ? [{Effect="Allow",Principal={Service="events.amazonaws.com"},Action="sqs:SendMessage",Resource=aws_sqs_queue.x.arn,Condition={ArnEquals={"aws:SourceArn"=concat([for r in aws_cloudwatch_event_rule.x : r.arn], aws_cloudwatch_event_rule.y[*].arn)}}}] : []})'''
        self.assertEqual(resource_policy_scope(text,'aws_sqs_queue_policy'),('sqs:SendMessage',))
        with self.assertRaises(Unsupported):resource_policy_scope(text.replace('r.arn','foreign.arn'),'aws_sqs_queue_policy')

    def test_schema_positive_and_unknown_hook_mutations_for_each_type(self):
        bodies={
          'aws_dynamodb_table':'name="x"\npoint_in_time_recovery {\n enabled=true\n}',
          'aws_sqs_queue':'name="x"\nredrive_policy=var.redrive',
          'aws_s3_bucket_logging':'bucket=var.bucket\nexpected_bucket_owner=var.account\ntarget_bucket=var.logs\ntarget_prefix=var.prefix',
          'aws_cloudwatch_event_bus':'name="x"',
          'aws_lambda_alias':'name="live"\nfunction_name=var.fn\nfunction_version=var.version',
          'aws_lambda_event_source_mapping':'function_name=var.fn\nevent_source_arn=var.queue',
          'aws_lambda_function_event_invoke_config':'function_name=var.fn\ndestination_config {\n on_failure {\n destination=var.queue\n }\n}',
          'aws_cloudwatch_log_metric_filter':'name="x"\nmetric_transformation {\n name="Health"\n namespace="test"\n value="1"\n}',
        }
        self.assertEqual(set(bodies),set(SCHEMAS)) # two SQS declarations share one schema
        for typ,body in bodies.items():
            with self.subTest(typ=typ):
                schema_scope(typ,body)
                for extra in ('\npolicy=var.policy','\nprovisioner "local-exec" {\n command="unexecuted"\n}'):
                    with self.assertRaises(Unsupported):schema_scope(typ,body+extra)

    def test_dynamic_table_shapes_are_checked_recursively(self):
        body='''name="x"
dynamic "attribute" {
 for_each=local.keys
 content {
  name=attribute.value
  type="S"
 }
}'''
        schema_scope('aws_dynamodb_table',body)
        for changed in (body.replace('type="S"','policy=var.policy'),body.replace('"attribute"','"provisioner"')):
            with self.assertRaises(Unsupported):schema_scope('aws_dynamodb_table',changed)

    def test_schema_scopes_do_not_hide_unknown_other_resources(self):
        d=self.discover('resource "aws_new_authority_mechanism" "x" {\n name="x"\n}')
        self.assertTrue(d.taints('github'))
        d=self.discover('resource "aws_cloudwatch_event_bus" "x" {\n name="x"\n}')
        self.assertEqual(d.taints('github'),[])
        self.assertTrue(d.taints('api:events'))

    def function_fixture(self):
        return '''locals {
 keys=toset(["worker","ingestion"])
}
resource "aws_lambda_function" "runtime" {
 for_each=local.keys
 function_name="${var.prefix}-${each.key}"
}
resource "aws_lambda_alias" "live" {
 for_each=local.keys
 name="live"
 function_name=aws_lambda_function.runtime[each.key].function_name
 function_version=aws_lambda_function.runtime[each.key].version
}
resource "aws_lambda_event_source_mapping" "reports" {
 function_name=aws_lambda_alias.live["ingestion"].arn
 event_source_arn=var.queue
}
resource "aws_lambda_permission" "tick" {
 action="lambda:InvokeFunction"
 function_name=aws_lambda_function.runtime[each.key].function_name
 principal="events.amazonaws.com"
}
'''

    def test_lambda_relationships_disjoint_only_for_concrete_target(self):
        d=self.discover(self.function_fixture())
        arn='arn:aws:lambda:us-east-1:111122223333:function:demo-scale-down-lambda'
        self.assertEqual(d.taints('api:lambda',action='lambda:InvokeFunction',resource=arn),[])
        self.assertTrue(d.taints('api:lambda',action='lambda:InvokeFunction'))
        self.assertTrue(d.taints('api:lambda',action='lambda:InvokeFunction',resource=arn.replace('demo-scale-down-lambda','demo-worker')))

    def test_foreign_alias_and_mapping_destinations_invalidate_disjointness(self):
        arn='arn:aws:lambda:us-east-1:111122223333:function:demo-scale-down-lambda'
        for old,new in (('function_name=aws_lambda_function.runtime[each.key].function_name','function_name=var.foreign'),
                        ('function_name=aws_lambda_alias.live["ingestion"].arn','function_name=var.foreign')):
            with self.subTest(new=new):self.assertTrue(self.discover(self.function_fixture().replace(old,new)).taints('api:lambda',action='lambda:InvokeFunction',resource=arn))

    def test_full_function_arn_in_alias_is_not_compared_as_a_bare_name(self):
        arn='arn:aws:lambda:us-east-1:111122223333:function:demo-scale-down-lambda'
        text=self.function_fixture().replace('function_name=aws_lambda_function.runtime[each.key].function_name',
                                            'function_name='+json.dumps(arn))
        self.assertTrue(self.discover(text).taints('api:lambda',action='lambda:InvokeFunction',resource=arn))

    def test_wildcard_or_malformed_query_resource_never_gets_disjointness_proof(self):
        for arn in ('arn:aws:lambda:us-east-1:111122223333:function:*',
                    'arn:aws:lambda:us-east-1:111122223333:function:foreign-*',
                    'arn:aws:lambda:us-east-1:111122223333:function:worker:*'):
            self.assertFalse(disjoint_function(['demo-worker'],arn))

    def test_added_permission_or_alias_hook_stays_unknown(self):
        arn='arn:aws:lambda:us-east-1:111122223333:function:demo-scale-down-lambda'
        d=self.discover(self.function_fixture().replace('name="live"','name="live"\n policy=var.policy'))
        self.assertTrue(d.taints('api:lambda',action='lambda:InvokeFunction',resource=arn))

    def test_function_disjointness_never_assumes_region_account_or_missing_arn(self):
        self.assertFalse(disjoint_function(['*'], 'arn:aws:lambda:us-east-1:111122223333:function:worker'))
        self.assertFalse(disjoint_function(['demo-worker'],None))
        self.assertFalse(disjoint_function(['demo-worker'],'arn:aws:lambda:us-west-2:444455556666:function:demo-worker:live'))




    def test_literal_table_security_children_keep_dynamodb_unknown(self):
        text='''resource "aws_dynamodb_table" "state" {
 name=var.name
 billing_mode="PAY_PER_REQUEST"
 hash_key="PK"
 tags=local.tags
 attribute { name="PK" }
 global_secondary_index { name="Due" }
 server_side_encryption { enabled=true }
 point_in_time_recovery { recovery_period_in_days=1 }
}'''
        d=self.discover(text)
        self.assertEqual(d.taints('github'),[])
        self.assertEqual(len(d.taints('api:dynamodb')),1)
        self.assertEqual(d.records[0]['admission'],'UNSUPPORTED_APPLICABLE')
        for old,new in [('tags=local.tags','tags=local.tags\n policy=var.policy'),
                        ('enabled=true','enabled=true\n kms_key_arn=var.key'),
                        ('hash_key="PK"','hash_key="PK"\n provisioner "local-exec" { command="not-run" }')]:
            self.assertTrue(self.discover(text.replace(old,new)).taints('github'))

    def test_logging_target_schema_keeps_s3_and_hooks_unknown(self):
        text='''resource "aws_s3_bucket_logging" "archive" {
 bucket=aws_s3_bucket.archive.id
 expected_bucket_owner=var.account
 target_bucket=var.log_bucket
 target_prefix=var.prefix
}'''
        d=self.discover(text)
        self.assertEqual(d.taints('github'),[])
        self.assertEqual(len(d.taints('api:s3')),1)
        self.assertEqual(d.records[0]['admission'],'UNSUPPORTED_APPLICABLE')
        for extra in ('policy=var.policy','provisioner "local-exec" { command="not-run" }','dynamic "target_object_key_format" { for_each=var.items }'):
            self.assertTrue(self.discover(text.replace(' target_prefix=var.prefix',' target_prefix=var.prefix\n '+extra)).taints('github'))

    def test_explicit_logging_dependencies_do_not_admit_dynamic_hooks(self):
        body='bucket=var.bucket\ntarget_bucket=var.logs\ndepends_on=[aws_s3_bucket_policy.logs, aws_s3_bucket_public_access_block.logs]'
        self.assertEqual(schema_scope('aws_s3_bucket_logging',body)[0],'s3')
        for dependency in ('var.dependencies','[module.logs]','[evil()]','[aws_s3_bucket_policy.logs, var.other]'):
            with self.subTest(dependency=dependency),self.assertRaises(Unsupported):
                schema_scope('aws_s3_bucket_logging',body.replace('[aws_s3_bucket_policy.logs, aws_s3_bucket_public_access_block.logs]',dependency))
        bound=body.replace('bucket=var.bucket','bucket=aws_s3_bucket.archive.id').replace('target_bucket=var.logs','target_bucket=aws_s3_bucket.logs.id')
        resources={('.', 'aws_s3_bucket', name):'bucket="'+name+'-owned"' for name in ('archive','logs')}
        proof=s3_logging_targets(bound,'.',resources,{})
        self.assertTrue(disjoint_s3(proof,'arn:aws:s3:::foreign-bucket/key'))
        for name in ('archive','logs'):
            self.assertFalse(disjoint_s3(proof,'arn:aws:s3:::'+name+'-owned/key'))
            for changed in (bound.replace('aws_s3_bucket.'+name+'.id','var.foreign'),bound.replace('aws_s3_bucket.'+name+'.id','aws_s3_bucket.missing.id')):
                with self.assertRaises((Unsupported,KeyError)):s3_logging_targets(changed,'.',resources,{})
            for declaration in ('bucket=var.unresolved','bucket="foreign-bucket"'):
                changed={**resources,('.', 'aws_s3_bucket',name):declaration}
                self.assertFalse(disjoint_s3(s3_logging_targets(bound,'.',changed,{}),'arn:aws:s3:::foreign-bucket/key'))
            with self.assertRaises(Unsupported):
                s3_logging_targets(bound,'.',{**resources,('.', 'aws_s3_bucket',name):resources[('.', 'aws_s3_bucket',name)]+'\nprovisioner "local-exec" { command="not-run" }'},{})

    def test_encryption_condition_scope_keeps_matching_permission_unknown(self):
        body='''bucket=aws_s3_bucket.archive.id
policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Deny",Principal="*",Action="s3:PutObject",Resource="${aws_s3_bucket.archive.arn}/*",Condition={StringNotEquals={"s3:x-amz-server-side-encryption"="aws:kms"},Null={"s3:x-amz-server-side-encryption"="false"}}}]})'''
        self.assertEqual(resource_policy_scope(body,'aws_s3_bucket_policy'),('s3:PutObject',))
        text='resource "aws_s3_bucket_policy" "archive" {\n'+body+'\n}'
        self.assertTrue(self.discover(text).taints('api:s3',action='s3:PutObject'))
        for old,new in (('StringNotEquals','StringNotEqualsIfExists'),('"false"','var.context'),('"s3:PutObject"','var.actions')):
            with self.subTest(new=new),self.assertRaises((Unsupported,ValueError)):
                resource_policy_scope(body.replace(old,new),'aws_s3_bucket_policy')

    def test_logging_object_suffix_cannot_change_bound_bucket_identity(self):
        body='''bucket=aws_s3_bucket.logs.id
policy=jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service="logging.s3.amazonaws.com"},Action="s3:PutObject",Resource="${aws_s3_bucket.logs.arn}/${local.prefix}*"}]})'''
        resources={('.', 'aws_s3_bucket', 'logs'):'bucket="own-logs"\nforce_destroy=false'}
        binding=s3_policy_target(body,'.',resources,{})
        self.assertEqual(binding['patterns'],['own-logs'])
        self.assertEqual(binding['resourceReferencesChecked'],1)
        for target in ('${aws_s3_bucket.foreign.arn}/${local.prefix}*','${aws_s3_bucket.logs.arn}${local.prefix}*','${aws_s3_bucket.logs.arn}/${evil()}'):
            changed=body.replace('${aws_s3_bucket.logs.arn}/${local.prefix}*',target)
            with self.subTest(target=target),self.assertRaises(Unsupported):
                s3_policy_target(changed,'.',resources,{})

if __name__=='__main__':unittest.main(verbosity=2)
