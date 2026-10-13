"""Production-facing local lab commands/configuration, never AWS certification."""
import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts import simple_lab as lab, ephemeral_lab as operator

ROOT=Path(__file__).resolve().parents[3]
CONFIG=json.loads((ROOT/'ci/ephemeral/lab.example.json').read_text())


class Lab(unittest.TestCase):
    def setUp(self):self.config=copy.deepcopy(CONFIG);self.scope=lab.select(self.config)
    def artifacts(self):
        tags=dict(Environment='lab',Project='terragrunt-demo-lab',LabId=self.config['lab_id'],ManagedBy='Terraform')
        rows=[dict(address=address,id='id-'+str(i),tags={} if address.startswith('terraform_data.') or address in lab.UNTAGGED else tags)
              for i,address in enumerate(lab.composition_address_names())]
        state=dict(lineage='22222222-2222-4222-8222-222222222222',serial=1,backend=self.scope['backend'],workspace='default',resources=rows)
        plan=dict(format_version='1.2',errored=False,complete=True,applyable=True,resource_changes=[
            dict(address=row['address'],mode='managed',change=dict(actions=['delete'],before=dict(id=row['id'],tags=row['tags']),after=None)) for row in rows])
        ids={row['address']:row['id'] for row in rows}
        for change in plan['resource_changes']:
            for field,parent in lab.UNTAGGED.get(change['address'],{}).items():change['change']['before'][field]=ids[parent]
        binary=b'OFFLINE_SYNTHETIC_SAVED_PLAN'
        context=dict(configuration_sha256=self.scope['configuration_sha256'],binary_sha256=lab.sha(binary),
            json_sha256=lab.sha(lab.canonical(plan)),state_sha256=lab.sha(lab.canonical(state)))
        return binary,plan,context,state
    def test_01_isolated_lab_selection_and_secret_free_metadata(self):
        self.assertEqual(self.scope['environment'],'lab');self.assertNotIn('password',self.config)
        with self.assertRaises(ValueError):lab.select(dict(self.config,password='do-not-store'))
    def test_02_protected_dev_prod_shared_rejected(self):
        for environment in ('dev','prod','shared'):
            with self.subTest(environment=environment),self.assertRaises(ValueError):lab.select(dict(self.config,environment=environment))
    def test_03_separate_backend_and_workspace(self):
        self.assertTrue(self.scope['backend']['bucket'].startswith('terragrunt-demo-lab-state-'))
        self.assertEqual(self.scope['backend']['key'],'labs/'+self.config['lab_id']+'/terraform.tfstate')
        self.assertNotIn('e1/lifecycle',self.scope['backend']['key']);self.assertEqual(self.scope['workspace'],'default')
    def test_04_names_tags_and_dedicated_role_repository(self):
        template=lab.composition(self.config)
        self.assertEqual(template['provider']['aws']['allowed_account_ids'],[self.config['account']])
        self.assertEqual(template['provider']['aws']['default_tags']['tags']['LabId'],self.config['lab_id'])
        for field in ('task_role','sql_profile','execution_role','image'):
            value=self.config[field].replace(self.scope['name'],'demo-dev')
            with self.subTest(field=field),self.assertRaises(ValueError):lab.select(dict(self.config,**{field:value}))
    def test_05_no_shared_deletion_or_iam_resources(self):
        template=lab.composition(self.config)
        self.assertFalse(any(kind.startswith(('aws_iam','aws_kms','aws_secretsmanager','aws_ecr','aws_s3')) for kind in template['resource']))
        self.assertNotIn('data',template);self.assertNotIn('module',template)
        self.assertEqual(set(lab.composition_address_names()),{kind+'.'+label for kind,items in template['resource'].items() for label in items})
    def test_06_dependency_order_and_task_bootstrap_zero(self):
        template=lab.composition(self.config)['resource']
        self.assertIn('aws_route.egress',template['aws_instance']['sql']['depends_on'])
        self.assertIn('aws_instance.sql',template['aws_ecs_service']['app']['depends_on'])
        self.assertEqual(template['aws_ecs_service']['app']['desired_count'],0)
        self.assertTrue(template['aws_instance']['sql']['root_block_device']['delete_on_termination'])
    def test_07_existing_image_probe_sql_kms_capability_preserved(self):
        template=lab.composition(self.config)['resource'];task=json.loads(template['aws_ecs_task_definition']['app']['container_definitions'])
        self.assertEqual(task[1]['command'],['readiness-probe']);self.assertFalse(task[1]['essential'])
        self.assertEqual(task[0]['image'],self.config['image']);self.assertEqual(task[0]['secrets'][0]['valueFrom'],self.config['connection_secret'])
        self.assertIn(self.config['sa_secret'],template['aws_instance']['sql']['user_data'])
        self.assertNotIn('DB_CONN_STRING=',template['aws_instance']['sql']['user_data'])
    def test_08_up_requires_explicit_infrastructure_confirmation(self):
        with self.assertRaises(ValueError):lab.report('up',self.config)
        expected='PREPARE LAB '+self.config['account']+' '+self.config['region']+' '+self.config['lab_id']
        value=lab.report('up',self.config,confirm=expected)
        self.assertEqual(value['stage'],'LOCAL_DRAFT_PREPARED_NOT_PROVISIONED');self.assertFalse(value['execution_authorized'])
    def test_09_sql_confirmation_independent(self):
        reviewed=lab.review(self.config,*self.artifacts())
        with self.assertRaisesRegex(ValueError,'independent'):lab.report('down',self.config,reviewed=reviewed,confirm=reviewed['destroy_confirmation'])
        with self.assertRaises(ValueError):lab.report('down',self.config,reviewed=reviewed,confirm=reviewed['sql_confirmation'],sql_confirm=reviewed['sql_confirmation'])
        value=lab.report('down',self.config,reviewed=reviewed,confirm=reviewed['destroy_confirmation'],sql_confirm=reviewed['sql_confirmation'])
        self.assertFalse(value['execution_authorized']);self.assertEqual(value['stage'],'LOCAL_DESTROY_REVIEWED_NOT_EXECUTED')
        foreign=dict(reviewed,configuration_sha256='f'*64)
        with self.assertRaises(ValueError):lab.report('down',self.config,reviewed=foreign,confirm=foreign['destroy_confirmation'],sql_confirm=foreign['sql_confirmation'])
    def test_10_exact_saved_binary_json_config_state_binding(self):
        binary,plan,context,state=self.artifacts()
        for field in context:
            damaged=dict(context,**{field:'b'*64})
            with self.subTest(field=field),self.assertRaises(ValueError):lab.review(self.config,binary,plan,damaged,state)
    def test_11_failure_stops_without_execution_or_automatic_retry(self):
        tree=ast.parse((ROOT/'scripts/simple_lab.py').read_text())
        imports={node.names[0].name for node in ast.walk(tree) if isinstance(node,ast.Import)}
        self.assertFalse(imports & {'boto3','subprocess','socket','requests'})
        value=lab.report('status',self.config);self.assertIn('STOP',value['failure']);self.assertIn('no blind retry',value['failure'])
    def test_12_partial_destroy_never_complete(self):
        notes=dict(scope=self.scope,stage='FAILED',resources={'EC2':'PRESENT','EBS':'UNKNOWN'},app_readiness='FAILED')
        value=lab.report('residual',self.config,notes=notes)
        self.assertFalse(value['aws_verified']);self.assertTrue(value['observations']['possible_charges'])
        self.assertEqual(value['classification'],'PARTIALLY_READY')
    def test_13_residual_and_retained_costs(self):
        value=lab.report('residual',self.config);self.assertEqual(value['observations'],'MISSING_UNKNOWN_POTENTIAL_COSTS')
        self.assertFalse(value['resources']['zero_cost_claim']);self.assertTrue(value['resources']['retained'])
        notes=dict(scope=self.scope,stage='DOWN',resources={'EC2':'ABSENT'},app_readiness='NOT_CHECKED')
        self.assertTrue(lab.report('residual',self.config,notes=notes)['observations']['possible_charges'])
    def test_14_no_unapproved_authority_even_synthetic_positive(self):
        template=lab.composition(self.config)
        self.assertIn('false',template['resource']['terraform_data']['installation_required']['lifecycle']['precondition'][0]['condition'])
        notes=dict(scope=self.scope,stage='UP',resources={'EC2':'PRESENT'},app_readiness='OBSERVED_READY')
        value=lab.report('verify',self.config,notes=notes)
        self.assertFalse(value['aws_verified']);self.assertFalse(value['execution_authorized'])
    def test_15_wp5_state_and_foreign_resource_rejected(self):
        binary,plan,context,state=self.artifacts()
        state['backend']['bucket']='e1-lifecycle-dev-'+self.config['account']+'-'+self.config['region']
        with self.assertRaises(ValueError):lab.review(self.config,binary,plan,context,state)
        binary,plan,context,state=self.artifacts();state['resources'][0]['address']='module.protected.aws_instance.db'
        with self.assertRaises(ValueError):lab.ownership(state,self.scope)
    def test_16_fresh_lab_has_no_nat_controller_or_reactivation_automation(self):
        template=lab.composition(self.config);kinds=set(template['resource'])
        self.assertFalse(kinds & {'aws_autoscaling_group','aws_lambda_function','aws_cloudwatch_event_rule','aws_cloudwatch_event_target','aws_sqs_queue','aws_appautoscaling_target','aws_lb','aws_eip'})
        self.assertEqual(len(template['resource']['aws_subnet']),1);self.assertEqual(len(template['resource']['aws_ecs_service']),1)
        service=template['resource']['aws_ecs_service']['app']
        self.assertEqual(service['desired_count'],0);self.assertNotIn('lifecycle',service) # native ECS reconciliation explicitly remains until service deletion
    def test_17_repeated_review_requires_current_supplied_state(self):
        binary,plan,context,state=self.artifacts();state['serial']+=1
        with self.assertRaises(ValueError):lab.review(self.config,binary,plan,context,state)
        binary,plan,context,state=self.artifacts();plan['resource_changes'].pop()
        context['json_sha256']=lab.sha(lab.canonical(plan))
        with self.assertRaises(ValueError):lab.review(self.config,binary,plan,context,state)
    def test_18_existing_entrypoint_routes_lab_without_affecting_dev(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'lab.json';config.write_bytes(lab.canonical(self.config));stream=io.StringIO()
            with contextlib.redirect_stdout(stream):self.assertEqual(operator.main(['lab','status','--config',str(config)]),0)
            self.assertEqual(json.loads(stream.getvalue())['scope']['environment'],'lab')
        with self.assertRaises(ValueError):operator.report('down-execute',self.config['account'],self.config['region'])
    def test_19_up_writes_only_inert_new_external_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'input.json';config.write_bytes(lab.canonical(self.config));output=Path(temp)/'draft'
            args=['lab','up','--config',str(config),'--output',str(output),'--confirm','PREPARE LAB '+self.config['account']+' '+self.config['region']+' '+self.config['lab_id']]
            with contextlib.redirect_stdout(io.StringIO()):operator.main(args)
            self.assertEqual({p.name for p in output.iterdir()},{'lab.draft.json','review.json'})
            self.assertFalse(list(output.glob('*.tf.json')))
            with self.assertRaises(ValueError):operator.main(args)
    def test_20_controller_migration_import_and_tag_forgery_cannot_authorize(self):
        binary,plan,context,state=self.artifacts();state['resources'][1]['tags']['Environment']='dev'
        with self.assertRaises(ValueError):lab.ownership(state,self.scope)
        binary,plan,context,state=self.artifacts();plan['resource_changes'][1]['change']['actions']=['delete','create']
        context['json_sha256']=lab.sha(lab.canonical(plan))
        with self.assertRaises(ValueError):lab.review(self.config,binary,plan,context,state)

    def test_21_untaggable_route_rule_association_require_exact_tagged_parent(self):
        binary,plan,context,state=self.artifacts()
        self.assertFalse(lab.review(self.config,binary,plan,context,state)['execution_authorized'])
        for address,parents in lab.UNTAGGED.items():
            binary,plan,context,state=self.artifacts()
            change=next(row for row in plan['resource_changes'] if row['address']==address)
            change['change']['before'][next(iter(parents))]='foreign-id'
            context['json_sha256']=lab.sha(lab.canonical(plan))
            with self.subTest(address=address),self.assertRaises(ValueError):lab.review(self.config,binary,plan,context,state)
