"""Actual WP5 verification and E2/E4 holds; local notes never gain authority."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts import ephemeral_lab as lab, environment_mutation as e
from scripts.lifecycle import contract as c, runtime
from scripts.lifecycle.controller import Controller
from scripts.tests.mutation.test_mutation import S3
from scripts.tests.post_switch import test_post_switch
from test_lifecycle import projection, request, quiescent, Memory, Checked, ACCOUNT, REGION, DOC
import model

ROOT = Path(__file__).resolve().parents[3]
UUID = '11111111-1111-4111-8111-111111111111'


def readback(module=None):
    return dict(format_version='1.2', complete=True, errored=False, resource_changes=[],
                planned_values=dict(root_module={} if module is None else module))


def notes():
    return dict(schema='E15_LOCAL_NOTES_V1', environment='dev', account=ACCOUNT, region=REGION,
        e2={domain:dict(version_id='local-version',head=e.initial('dev',domain))
            for domain in ('application','shared','secrets')}, operations=[], resources={})


class Ephemeral(unittest.TestCase):
    def report(self, action='status', **kwargs):
        return lab.report(action, ACCOUNT, REGION, **kwargs)

    def test_dev_context_and_repository_inventory(self):
        value=self.report()
        self.assertEqual(value['environment'],'dev')
        self.assertFalse(value['aws_verified'])
        self.assertFalse(value['execution_authorized'])
        self.assertTrue(value['declaration_inventory'])
        self.assertIn('WP5_INSTALLATION_MISSING',value['gates'])

    def test_prod_shared_and_mismatched_context_rejected(self):
        for env in ('prod','shared','neutral','DEV'):
            with self.assertRaises(ValueError):self.report(environment=env)
        for account,region in (('123','us-east-1'),(ACCOUNT,'latest')):
            with self.assertRaises(ValueError):lab.report('status',account,region)

    def test_dependency_order_and_reverse_down(self):
        positions={layer:n for n,layer in enumerate(lab.UP)}
        for layer,parents in lab.DEPENDENCIES.items():
            for parent in parents:self.assertLess(positions[parent],positions[layer])
        self.assertEqual(lab.DOWN,('edge','apps','platform','data','global'))
        self.assertEqual(lab.DOWN,tuple(x for x in reversed(lab.UP) if x not in lab.RETAINED_LAYERS))
        sources={name:(ROOT/'terraform/modules/target/dev'/name).read_text() for name in
            ('edge/ordinary-main.tf','apps/ordinary-demo.tf','data/ordinary-variables.tf','global/ordinary-main.tf')}
        self.assertIn('var.alb_listener_arn',sources['edge/ordinary-main.tf'])
        for token in ('var.cluster_arn','var.private_subnet_ids','var.demo_blue_tg_arn','var.alerts_topic_arn'):
            self.assertIn(token,sources['apps/ordinary-demo.tf'])
        self.assertIn('variable "private_subnet_ids"',sources['data/ordinary-variables.tf'])
        self.assertIn('module.vpc.private_subnet_ids',sources['global/ordinary-main.tf'])

    def test_backend_all_layer_keys_protected_and_retained(self):
        backend=self.report('down-preview')['protected_backend']
        self.assertFalse(backend['deletion_permitted'])
        self.assertEqual(backend['bucket'],f'e1-lifecycle-dev-{ACCOUNT}-{REGION}')
        self.assertEqual(len(backend['keys']),7)
        self.assertNotIn('shared',lab.DOWN)
        self.assertNotIn('secrets',lab.DOWN)
        for row in lab.declarations():
            if row['owner'] in ('security','shared','secrets'):self.assertEqual(row['treatment'],'RETAIN')

    def test_independent_destruction_and_sql_confirmations(self):
        value=self.report('down-preview')
        self.assertIn('DEV_DESTRUCTION_CONFIRMATION_REQUIRED',value['gates'])
        self.assertIn('SQL_DATA_DECISION_AND_INDEPENDENT_CONFIRMATION_REQUIRED',value['gates'])
        value=self.report('down-preview',confirm_dev=True)
        self.assertNotIn('DEV_DESTRUCTION_CONFIRMATION_REQUIRED',value['gates'])
        self.assertIn('SQL_DATA_DECISION_AND_INDEPENDENT_CONFIRMATION_REQUIRED',value['gates'])
        value=self.report('down-preview',confirm_dev=True,confirm_sql_loss=True,sql_policy='DISPOSABLE')
        self.assertNotIn('SQL_DATA_DECISION_AND_INDEPENDENT_CONFIRMATION_REQUIRED',value['gates'])
        self.assertFalse(value['execution_authorized'])
        with self.assertRaises(ValueError):self.report('down-preview',confirm_sql_loss=True)

    def test_preserve_sql_requires_unimplemented_e5_contract(self):
        value=self.report('down-preview',confirm_dev=True,sql_policy='PRESERVE')
        self.assertIn('E5_APPROVED_BACKUP_RESTORE_NOT_IMPLEMENTED',value['gates'])
        source=(ROOT/'terraform/modules/target/dev/data/ordinary-main.tf').read_text()
        self.assertIn('delete_on_termination = true',source)

    def test_down_execute_never_bypasses_wp5_even_with_confirmations(self):
        with self.assertRaises(ValueError):
            self.report('down-execute',confirm_dev=True,confirm_sql_loss=True,sql_policy='DISPOSABLE')
        tree=ast.parse((ROOT/'scripts/ephemeral_lab.py').read_text())
        imports=[node for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any(any(x in ast.unparse(node) for x in ('boto3','subprocess','urllib','socket','workflow_requests.client')) for node in imports))

    def test_active_e2_notes_block_even_interrupted_owner(self):
        s3=S3();store=s3.seed('dev')
        owner=e.Authority(store,'normal-delivery/deploy-dev',UUID,{'action':'deliver'})
        owner.acquire()
        value=notes();value['e2']['application']['head']=store.read()[0]
        result=self.report('down-preview',notes=value)
        self.assertIn('E2_ACTIVE_application',result['gates'])
        self.assertEqual(store.read()[0]['state'],'ACTIVE')
        peer=e.Authority(store,'environment-lifecycle/infra-high-risk-dev',UUID,{},layer='global')
        called=[]
        self.assertEqual(e.execute(peer,lambda _:called.append(True),state_key='state')['state'],'UNKNOWN')
        self.assertEqual(called,[])

    def test_e4_partial_real_journal_blocks_down_review(self):
        case=test_post_switch.Recovery();case.configure();case.partial()
        value=notes();value['e2']['application']['head']=case.store.read()[0]
        value['operations']=[dict(binding='normal-delivery/deploy-dev',operation_id=case.owner.operation,
                                 state='UNCERTAIN',layer=None)]
        result=self.report('down-preview',notes=value)
        self.assertIn('UNRESOLVED_UNCERTAIN',result['gates'])
        self.assertIn('E2_ACTIVE_application',result['gates'])
        self.assertNotIn('dev/'+case.owner.operation+'/success',case.records.data)

    def test_unknown_active_operation_notes_block(self):
        for state in ('ACTIVE','UNKNOWN','UNCERTAIN'):
            value=notes();value['operations']=[dict(binding='environment-lifecycle/infra-high-risk-dev',
                operation_id=UUID,state=state,layer='global')]
            self.assertIn('UNRESOLVED_'+state,self.report('verify',notes=value)['gates'])

    def test_missing_corrupt_foreign_evidence_rejected_or_unknown(self):
        self.assertIn('MISSING_LOCAL_NOTES',self.report('verify')['gates'])
        for change in (lambda n:n.pop('e2'),lambda n:n.update(environment='prod'),
                       lambda n:n.update(account='999999999999'),lambda n:n['e2'].pop('application'),
                       lambda n:n['e2']['application'].update(version_id='latest')):
            value=notes();change(value)
            with self.assertRaises((ValueError,KeyError)):self.report('verify',notes=value)
        with self.assertRaises(ValueError):lab.decode('{"environment":"dev","environment":"prod"}')

    def test_residual_present_partial_unknown_and_missing_are_not_absence(self):
        row=next(x for x in lab.declarations() if x['type']=='aws_eip')
        for status in ('PRESENT','PARTIAL','UNKNOWN'):
            value=notes();value['resources'][row['key']]=status
            result=self.report('residual',notes=value)['local_notes_review']
            self.assertIn(row['key'],[x['key'] for x in result['residual']])
            self.assertFalse(result['aws_verified'])
        value=notes();result=self.report('residual',notes=value)
        self.assertIn('INCOMPLETE_RESIDUAL_EVIDENCE',result['gates'])

    def test_all_absence_notes_cannot_manufacture_teardown_success(self):
        value=notes();value['resources']={r['key']:'ABSENT' for r in lab.declarations()}
        result=self.report('verify',notes=value)
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['aws_verified'])
        self.assertEqual(result['classification'],'PARTIALLY_READY')

    def test_ecr_images_evidence_state_and_security_are_retained(self):
        rows=lab.declarations()
        for row in rows:
            if row['type'].startswith(('aws_ecr_','aws_s3_','aws_kms_','aws_iam_')):
                self.assertEqual(row['treatment'],'RETAIN')
        self.assertFalse(any(r['type']=='aws_ecr_lifecycle_policy' for r in rows))
        self.assertTrue(any(r['type']=='aws_ecr_repository' for r in rows))

    def test_cost_model_no_zero_claim_and_all_resources_mapped(self):
        value=self.report('residual')
        self.assertIsNone(value['cost_model']['estimate'])
        self.assertFalse(value['cost_model']['zero_cost_claim'])
        self.assertTrue(all(x['cost_dimension'] for x in value['declaration_inventory']))
        eip=next(x for x in value['declaration_inventory'] if x['type']=='aws_eip')
        self.assertIn('including idle',eip['cost_dimension'])

    def test_budget_defaults_require_owner_and_never_install(self):
        draft=json.loads((ROOT/'ci/ephemeral/budget-draft.json').read_text())
        result=lab.budget(draft)
        self.assertEqual(set(result['missing_owner_decisions']),set(draft))
        self.assertFalse(result['hard_billing_cap'])
        self.assertFalse(result['automatic_shutdown'])
        self.assertEqual(result['installation'],'NOT_INSTALLED')
        self.assertIsNone(draft['monthly_limit'])

    def test_configurable_actual_forecast_and_recipient_draft(self):
        value=dict(monthly_limit='7.25',currency='USD',actual_percent='81',forecast_percent='105',
                   recipients=['owner@example.invalid'],scope='ACCOUNT_TOTAL')
        result=lab.budget(value)
        self.assertEqual(result['missing_owner_decisions'],[])
        self.assertEqual(result['classification'],'PARTIALLY_READY')
        self.assertFalse(result['hard_billing_cap'])
        for bad in ('NaN','-1','0','Infinity'):
            with self.assertRaises(ValueError):lab.budget({**value,'monthly_limit':bad})

    def test_new_unmapped_resource_cannot_be_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'terraform/modules/target/dev/global';folder.mkdir(parents=True)
            (folder/'bad.tf').write_text('resource "aws_nat_gateway" "unexpected" {}')
            with self.assertRaises(ValueError):lab.declarations(root)

    def test_reconstruction_uses_retained_interfaces_and_fresh_bindings(self):
        value=self.report('up-prepare')
        self.assertEqual(value['up_order'],c.LAYERS)
        self.assertIn('WP6 infra-high-risk-dev',value['existing_interfaces'])
        self.assertIn('WP6 release',value['existing_interfaces'])
        self.assertIn('WP6 deploy-dev',value['existing_interfaces'])
        self.assertTrue(all('prod' not in x for x in value['existing_interfaces']))
        self.assertTrue(all(r['reconstruction'] for r in value['declaration_inventory']))

    def test_generated_sources_inactive_and_no_authority_activation(self):
        model.validate_repository(ROOT)
        for kind in ('wp4d','wp5'):
            for field in ('installations','runtime_approvals','environment_bindings'):
                self.assertEqual(DOC[kind][field],{})
        self.assertEqual(DOC['wp6']['approvals'],{})

    def test_empty_teardown_values_and_data_only_readback(self):
        runtime.teardown_readback(readback())
        runtime.teardown_readback(readback(dict(resources=[dict(mode='data')],child_modules=[{}])))

    def test_partial_managed_resources_nested_or_root_block(self):
        for module in (dict(resources=[dict(mode='managed',type='aws_instance')]),
                       dict(child_modules=[dict(address='module.inner',resources=[dict(mode='managed')])])):
            with self.assertRaises(ValueError):runtime.teardown_readback(readback(module))

    def test_missing_or_corrupt_readback_never_establishes_absence(self):
        for value in ({},dict(planned_values={}),dict(planned_values=dict(root_module=None)),
                      readback(dict(resources=None)),readback(dict(child_modules={})),
                      readback(dict(resources=[{}])),readback(dict(unknown=[]))):
            with self.assertRaises(ValueError):runtime.teardown_readback(value)

    def engine(self, value, observation=None):
        engine=runtime.Terraform(ROOT,None,dict(environment='dev'))
        engine.call=lambda args:c.canonical(value)
        engine.observe=lambda env:quiescent() if observation is None else observation
        return engine

    def test_actual_runtime_requires_empty_state_and_post_destroy_quiescence(self):
        # Empty state is necessary; protected combined quietness is still absent.
        with self.assertRaisesRegex(ValueError, 'concrete administrative handoff'):
            self.engine(readback()).verify('a'*64,{},'teardown')
        with self.assertRaises(ValueError):
            self.engine(readback(dict(resources=[dict(mode='managed')]))).verify('a'*64,{},'teardown')
        q=quiescent();q['services'][next(iter(q['services']))]['running']=1
        with self.assertRaises(ValueError):self.engine(readback(),q).verify('a'*64,{},'teardown')

    def test_reconcile_readback_contract_remains_unchanged(self):
        value=readback(dict(resources=[dict(mode='managed')]))
        self.assertTrue(self.engine(value).verify('a'*64,{},'reconcile'))

    def test_partial_teardown_no_success_retains_e2_and_safe_status_retry(self):
        installations,images,bindings=projection();binding='environment-lifecycle/infra-high-risk-dev'
        protected=bindings[binding]['configuration'];revision=DOC['wp5']['selected'][binding]['package_sha256']
        value=request(revision=revision,layer='platform',operation='teardown')
        layer=protected['layers']['platform'];address=next(iter(layer['addresses']))
        layer['membership'][address]='exact-cluster-id'
        protected['operation_approvals'][value['operation_id']]=dict(request_sha256=c.digest(c.canonical(value)),environment='dev')
        protected['teardown_approvals'][value['operation_id']]=dict(revision=revision,layer='platform',environment='dev')
        plan=dict(format_version='1.2',resource_changes=[dict(address=address,type='aws_ecs_cluster',mode='managed',
            change=dict(actions=['delete'],before=dict(id='exact-cluster-id'),after=None,
                        after_unknown={},before_sensitive={},after_sensitive={}))])
        engine=self.engine(readback(dict(resources=[dict(mode='managed',type='aws_ecs_cluster')])))
        engine.prepare=lambda *args:None;engine.plan=lambda **kwargs:copy.deepcopy(plan)
        s3=S3();store=s3.seed('dev');owner=e.Authority(store,binding,value['operation_id'],value,layer='platform')
        calls=[];engine.apply=lambda *args:owner.call(lambda:calls.append('apply'))
        records=Memory();controller=Controller(binding,protected,Checked(),engine,records)
        result=e.execute(owner,lambda _:controller.run(value),state_key='state')
        self.assertEqual(result['state'],'UNKNOWN')
        self.assertEqual(store.read()[0]['state'],'ACTIVE')
        self.assertEqual(calls,['apply'])
        self.assertEqual(controller.run(value)['state'],'UNKNOWN')
        self.assertEqual(calls,['apply'])
        self.assertFalse(any(x.get('state')=='SUCCESS' for x in records.values.values()))

    def test_existing_wp5_approvals_still_required(self):
        installations,images,bindings=projection();binding='environment-lifecycle/infra-high-risk-dev'
        protected=bindings[binding]['configuration'];revision=DOC['wp5']['selected'][binding]['package_sha256']
        value=request(revision=revision,layer='data',operation='teardown')
        reference=protected['installations'][revision]
        with self.assertRaises(ValueError):c.authorize(binding,value,protected,reference)
        protected['operation_approvals'][value['operation_id']]=dict(request_sha256=c.digest(c.canonical(value)),environment='dev')
        with self.assertRaises(ValueError):c.authorize(binding,value,protected,reference)

    def test_authority_unchanged_except_derived_package_hashes(self):
        authority=copy.deepcopy(DOC)
        import ownership
        ownership.validate_publications(authority)
        # Authenticated first-session output metadata is now explicitly allowed;
        # the rest of the historical protected authority snapshot stays fixed.
        authority['ownership_closure']['publications']={}
        # Owner authorized optional DEV email; validate that exact input delta
        # before restoring the historical snapshot for unrelated authority.
        for key in ('request-gateway/infra-dev','environment-lifecycle/infra-dev',
                    'request-gateway/infra-high-risk-dev','environment-lifecycle/infra-high-risk-dev'):
            inputs=authority['wp5']['selected'][key]['required_inputs']['shared']
            self.assertEqual(inputs,['account_id','protected_inputs','region'])
            inputs.insert(1,'alert_email')
        for group in ('wp4d','wp5'):
            for item in authority[group]['selected'].values():del item['package_sha256']
        self.assertEqual(hashlib.sha256(json.dumps(authority,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                         '7a2a26aa8cbaf40411c8b7d4ebedcf1c53bc2492ce9a92a5cbdbe3142dac40ca')

    def test_implicit_resources_and_external_backend_require_residual_review(self):
        rows=lab.declarations()
        related={r['key']:r for r in rows if r['origin']=='IMPLICIT_OR_EXTERNAL_DEPENDENCY'}
        self.assertIn('related:sql-root-ebs',related)
        self.assertIn('related:service-enis',related)
        self.assertIn('related:nat-instances',related)
        self.assertEqual(related['related:security-backend']['treatment'],'RETAIN')
        value=notes();value['resources']={r['key']:'ABSENT' for r in rows if r['origin']=='DECLARATION_NOT_EXPANDED'}
        result=self.report('residual',notes=value)
        self.assertIn('INCOMPLETE_RESIDUAL_EVIDENCE',result['gates'])

    def test_empty_plan_missing_changes_still_requires_protected_quiescence(self):
        value=readback();del value['resource_changes']
        with self.assertRaisesRegex(ValueError, 'concrete administrative handoff'):
            self.engine(value).verify('a'*64,{},'teardown')
        self.assertFalse(self.engine(value).verify('a'*64,{},'reconcile'))
        for key,bad in (('complete',False),('complete',None),('errored',True),('format_version','2.0')):
            self.assertFalse(self.engine({**value,key:bad}).verify('a'*64,{},'teardown'))
        value['resource_changes']=[dict(mode='managed',change=dict(actions=['no-op']))]
        with self.assertRaises(ValueError):self.engine(value).verify('a'*64,{},'teardown')
