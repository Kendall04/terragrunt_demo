"""Exercise production WP5/E2 and NAT code with controlled ports, never AWS."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.lifecycle import dev_down as down, runtime, contract as c
from scripts.lifecycle.controller import Controller
from scripts import ephemeral_lab as lab, environment_mutation as e
from test_lifecycle import projection, request, Memory, Engine, Checked, quiescent, plan, DOC, ACCOUNT, REGION
from scripts.tests.mutation.test_mutation import S3 as Coordination
from scripts.tests.ephemeral.test_ephemeral import notes
from scripts.tests.post_switch import test_post_switch
from scripts.tests.nat import test_nat

ROOT=Path(__file__).resolve().parents[3]
NOW=1000
UUID='11111111-1111-4111-8111-111111111111'
NEXT='22222222-2222-4222-8222-222222222222'


def fixture(layer='data',env='dev'):
    _,_,bindings=projection();binding='environment-lifecycle/infra-high-risk-'+env
    protected=bindings[binding]['configuration'];revision=DOC['wp5']['selected'][binding]['package_sha256']
    value=request(revision,layer,'teardown')
    address='aws_instance.db' if layer=='data' else 'resource.exact'
    kind='aws_instance' if layer=='data' else 'aws_ecs_cluster'
    protected['layers'][layer]['addresses']={address:kind}
    protected['layers'][layer]['membership']={address:'exact-'+env+'-id'}
    observed_plan=plan(kind,'delete',dict(id='exact-'+env+'-id'),address=address)
    observed_plan['resource_changes'][0]['change']['after']=None
    observed_plan.update(complete=True)
    protected['operation_approvals'][UUID]=dict(request_sha256=c.digest(c.canonical(value)),environment=env)
    protected['teardown_approvals'][UUID]=dict(revision=revision,layer=layer,environment=env)
    return binding,protected,value,observed_plan


def consent(value,protected,issued=900,expires=1100):
    selected=down.scope(value,protected)
    return dict(schema='E15B_DEV_CONSENT_V1',scope_sha256=selected['scope_sha256'],
                issued_at=issued,expires_at=expires,**down.acknowledgements(selected))


def install_consent(value,protected):
    record=consent(value,protected)
    protected['teardown_approvals']['dev-sql-loss/'+value['operation_id']]=record
    return record


def reviewed():
    _,protected,value,document=fixture();binary=b'exact offline binary fixture, never installed'
    selected=down.scope(value,protected)
    context=dict(schema='E15B_DESTROY_REVIEW_V1',scope_sha256=selected['scope_sha256'],
        created_at=900,expires_at=1100,binary_sha256=c.digest(binary),json_sha256=c.digest(c.canonical(document)),
        state=dict(lineage=UUID,serial=4,version_id='exact-local-state-version',sha256='d'*64),workspace='default')
    return protected,value,binary,document,context


class Consent(unittest.TestCase):
    def test_dev_scope_exact_identity_backend_and_source(self):
        _,p,v,_=fixture();s=down.scope(v,p)
        self.assertEqual(s['environment'],'dev');self.assertEqual(s['account'],ACCOUNT)
        self.assertEqual(s['backend']['key'],'e1/lifecycle/dev/data/terraform.tfstate')
        self.assertEqual(s['revision'],v['revision']);self.assertEqual(s['source_commit'],'b'*40)

    def test_prod_shared_secrets_and_other_project_scope_reject(self):
        for layer in ('shared','secrets'):
            _,p,v,_=fixture(layer)
            with self.assertRaises(ValueError):down.scope(v,p)
        _,p,v,_=fixture(env='prod')
        with self.assertRaises(ValueError):down.scope(v,p)
        _,p,v,_=fixture();p['layers']['data']['root']='terraform/modules/target/other/data'
        with self.assertRaises(ValueError):down.scope(v,p)

    def test_two_meaningful_exact_confirmations(self):
        _,p,v,_=fixture();record=consent(v,p);s=down.scope(v,p)
        self.assertNotEqual(record['destroy_ack'],record['sql_loss_ack'])
        self.assertIn('PERMANENTLY LOSE',record['sql_loss_ack'])
        self.assertIsInstance(down.confirm(s,record,NOW),str)

    def test_missing_incorrect_conflicting_confirmation_rejects(self):
        _,p,v,_=fixture();record=consent(v,p);s=down.scope(v,p)
        for field in ('destroy_ack','sql_loss_ack','scope_sha256'):
            for bad in ('',None,True,'yes','prod','--force'):
                with self.assertRaises(ValueError):down.confirm(s,{**record,field:bad},NOW)
            wrong=copy.deepcopy(record);del wrong[field]
            with self.assertRaises(ValueError):down.confirm(s,wrong,NOW)
        with self.assertRaises(ValueError):down.confirm(s,None,NOW)

    def test_expired_future_missing_invalid_window_rejects(self):
        _,p,v,_=fixture();s=down.scope(v,p)
        for issued,expires in ((900,1000),(1001,1100),(1100,900),(True,1100),(900,None)):
            with self.assertRaises(ValueError):down.confirm(s,consent(v,p,issued,expires),NOW)

    def test_consent_replay_other_operation_revision_environment_and_layer_rejects(self):
        _,p,v,_=fixture();record=consent(v,p)
        wrong={**v,'operation_id':NEXT}
        with self.assertRaises(ValueError):down.confirm(down.scope(wrong,p),record,NOW)
        p['layers']['data']['membership']['aws_instance.db']='new-instance'
        with self.assertRaises(ValueError):down.confirm(down.scope(v,p),record,NOW)
        _,p,v,_=fixture('apps')
        with self.assertRaises(ValueError):down.confirm(down.scope(v,p),record,NOW)

    def test_missing_consent_blocks_real_controller_before_prepare_or_apply(self):
        binding,p,v,document=fixture();engine=Engine(document);prepared=[]
        engine.prepare=lambda *args:prepared.append(True)
        with patch('scripts.lifecycle.controller.time.time',return_value=NOW),self.assertRaises(ValueError):
            Controller(binding,p,Checked(),engine,Memory()).run(v)
        self.assertEqual(engine.applies,0);self.assertEqual(prepared,[])

    def test_valid_dev_data_teardown_uses_existing_controller_and_retained_retry(self):
        binding,p,v,document=fixture();install_consent(v,p);engine=Engine(document);records=Memory()
        controller=Controller(binding,p,Checked(),engine,records)
        with patch('scripts.lifecycle.controller.time.time',return_value=NOW):self.assertEqual(controller.run(v)['state'],'SUCCESS')
        with patch('scripts.lifecycle.controller.time.time',return_value=5000):self.assertEqual(controller.run(v)['state'],'SUCCESS')
        self.assertEqual(engine.applies,1)
        with self.assertRaises(ValueError):controller.run({**v,'parameters':dict(enable_alarms=False)})

    def test_consent_expires_after_plan_or_evidence_write_no_apply(self):
        binding,p,v,document=fixture();install_consent(v,p);engine=Engine(document);records=Memory()
        with patch('scripts.lifecycle.controller.time.time',side_effect=[1000,1100]):
            result=Controller(binding,p,Checked(),engine,records).run(v)
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(engine.applies,0)
        self.assertEqual(records.read(UUID)['state'],'UNKNOWN')

    def test_consent_does_not_override_existing_wp5_operator_approval(self):
        binding,p,v,document=fixture();install_consent(v,p);p['operation_approvals']={}
        with patch('scripts.lifecycle.controller.time.time',return_value=NOW),self.assertRaises(ValueError):
            Controller(binding,p,Checked(),Engine(document),Memory()).run(v)

    def test_prod_teardown_contract_unchanged_and_dev_consent_never_authorizes_it(self):
        binding,p,v,document=fixture(env='prod');engine=Engine(document)
        self.assertEqual(Controller(binding,p,Checked(),engine,Memory()).run(v)['state'],'SUCCESS')
        self.assertEqual(engine.applies,1)
        with self.assertRaises(ValueError):down.scope(v,p)


class Review(unittest.TestCase):
    def test_exact_binary_json_revision_scope_summary(self):
        p,v,b,document,context=reviewed();r=down.review(v,p,b,document,context,NOW)
        self.assertEqual(r['destructive_changes'],[dict(address='aws_instance.db',type='aws_instance',id='exact-dev-id',actions=['delete'])])
        self.assertEqual(r['context']['binary_sha256'],c.digest(b));self.assertFalse(r['plan_authenticated'])
        self.assertFalse(r['execution_authorized'])

    def test_text_summary_no_binary_or_wrong_binary_rejected(self):
        p,v,b,document,context=reviewed()
        for wrong in (b'',None,b+b'changed'):
            with self.assertRaises(ValueError):down.review(v,p,wrong,document,context,NOW)

    def test_different_plan_same_context_rejected(self):
        p,v,b,document,context=reviewed();wrong=copy.deepcopy(document)
        wrong['resource_changes'][0]['change']['actions']=['no-op']
        with self.assertRaises(ValueError):down.review(v,p,b,wrong,context,NOW)

    def test_create_update_foreign_or_security_scope_rejected_even_if_hash_claim_matches(self):
        for change in ('create','update','foreign','security'):
            p,v,b,document,context=reviewed();resource=document['resource_changes'][0]
            if change in ('create','update'):resource['change']['actions']=[change]
            elif change=='foreign':resource['change']['before']['id']='prod-id'
            else:
                resource['type']='aws_ecr_repository';p['layers']['data']['addresses']['aws_instance.db']='aws_ecr_repository'
                context['scope_sha256']=down.scope(v,p)['scope_sha256']
            context['json_sha256']=c.digest(c.canonical(document))
            with self.assertRaises(ValueError):down.review(v,p,b,document,context,NOW)

    def test_expired_missing_malformed_review_rejected(self):
        p,v,b,document,context=reviewed()
        with self.assertRaises(ValueError):down.review(v,p,b,document,context,1100)
        for field in ('state','workspace','scope_sha256','binary_sha256'):
            wrong=copy.deepcopy(context);del wrong[field]
            with self.assertRaises(ValueError):down.review(v,p,b,document,wrong,NOW)

    def test_changed_state_snapshot_invalidates_local_review_consistency(self):
        p,v,b,document,context=reviewed();r=down.review(v,p,b,document,context,NOW)
        for field,bad in (('serial',5),('lineage',NEXT),('version_id','replaced'),('sha256','f'*64)):
            state={**context['state'],field:bad}
            with self.assertRaises(ValueError):down.check_current_review(r,down.scope(v,p),state,b,document,NOW)
        self.assertFalse(down.check_current_review(r,down.scope(v,p),context['state'],b,document,NOW)['execution_authorized'])

    def test_edited_review_or_replay_other_operation_rejected(self):
        p,v,b,document,context=reviewed();r=down.review(v,p,b,document,context,NOW)
        bad=copy.deepcopy(r);bad['destructive_changes']=[]
        with self.assertRaises(ValueError):down.check_current_review(bad,down.scope(v,p),context['state'],b,document,NOW)
        with self.assertRaises(ValueError):down.check_current_review(r,down.scope({**v,'operation_id':NEXT},p),context['state'],b,document,NOW)
        with self.assertRaises(ValueError):down.check_current_review(r,down.scope(v,p),context['state'],b,document,1100)

    def test_local_review_and_boolean_confirmations_cannot_enable_down_execute(self):
        with self.assertRaises(ValueError):lab.report('down-execute',ACCOUNT,REGION,confirm_dev=True,confirm_sql_loss=True,sql_policy='DISPOSABLE')
        tree=ast.parse((ROOT/'scripts/ephemeral_lab.py').read_text(encoding='utf-8'))
        imports=[ast.unparse(x) for x in ast.walk(tree) if isinstance(x,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any(word in line for word in ('subprocess','boto3','workflow_requests.client','urllib') for line in imports))

    def test_residual_unknown_ownership_partial_and_retained_resources(self):
        value=notes();rows=lab.declarations();key=next(r['key'] for r in rows if r['type']=='aws_eip')
        value['resources'][key]='UNKNOWN_OWNERSHIP'
        result=lab.report('residual',ACCOUNT,REGION,notes=value)
        self.assertIn('UNPROVEN_RESOURCE_OWNERSHIP',result['gates'])
        self.assertFalse(result['aws_verified'])
        self.assertTrue(any(r['treatment']=='RETAIN' for r in result['local_notes_review']['residual']))



class CLI(unittest.TestCase):
    def invoke(self, extras=(), mutate=None):
        protected,value,binary,document,context=reviewed()
        document['resource_changes'][0]['change']['before']['password']='sensitive-fixture-not-for-output'
        context['json_sha256']=c.digest(c.canonical(document))
        selected=down.scope(value,protected)
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            envelope=dict(request=value,protected=protected,review_context=context)
            if mutate:mutate(envelope)
            (base/'context.json').write_text(json.dumps(envelope),encoding='utf-8')
            (base/'plan.json').write_text(json.dumps(document),encoding='utf-8')
            (base/'plan.bin').write_bytes(binary)
            args=['down-review','--account',ACCOUNT,'--region',REGION,
                  '--review-context',str(base/'context.json'),'--plan-json',str(base/'plan.json'),
                  '--plan-binary',str(base/'plan.bin'),*extras]
            output=io.StringIO()
            with patch.object(lab.time,'time',return_value=NOW),patch('sys.stdout',output):
                self.assertEqual(lab.main(args),0)
            raw=output.getvalue();self.assertNotIn('sensitive-fixture-not-for-output',raw)
            return json.loads(raw),selected,binary,document,context

    def test_real_cli_review_redacts_values_and_preserves_consistency_digest(self):
        result,selected,binary,document,context=self.invoke()
        checked=down.check_current_review(result['destroy_review'],selected,context['state'],binary,document,NOW)
        self.assertTrue(checked['local_consistency']);self.assertFalse(result['execution_authorized'])
        self.assertEqual(len(result['declaration_inventory']),217)

    def test_real_cli_drafts_two_confirmations_without_publishing_approval(self):
        p,v,_,_,_=reviewed();acks=down.acknowledgements(down.scope(v,p))
        result,selected,binary,document,context=self.invoke(
            ['--destroy-ack',acks['destroy_ack'],'--sql-loss-ack',acks['sql_loss_ack'],
             '--issued-at','900','--expires-at','1100'])
        self.assertEqual(result['consent_provenance'],'LOCAL_DRAFT_NOT_PROTECTED_APPROVAL')
        down.confirm(selected,result['consent_draft'],NOW)
        down.check_current_review(result['destroy_review'],selected,context['state'],binary,document,NOW)
        self.assertFalse(result['destroy_review']['execution_authorized'])

    def test_real_cli_rejects_partial_confirmations_wrong_identity_and_corrupt_artifacts(self):
        with self.assertRaises(ValueError):self.invoke(['--destroy-ack','yes'])
        with self.assertRaises(ValueError):self.invoke(mutate=lambda x:x['protected'].update(account='999999999999'))
        with self.assertRaises(ValueError):self.invoke(mutate=lambda x:x['review_context'].update(binary_sha256='0'*64))


class Binary(unittest.TestCase):
    def engine(self,layer='platform'):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        binding,p,v,document=fixture(layer);engine=runtime.Terraform(root,None,p,request=v)
        engine.directory=root;engine.layer=p['layers'][layer];engine.reference=p['installations'][v['revision']]
        engine.environment=dict(TF_WORKSPACE='default');(root/'wp5.auto.tfvars.json').write_bytes(b'{}')
        engine.observe=lambda env:quiescent(env);calls=[]
        def call(args):
            calls.append(args)
            if args[0]=='plan':(root/'wp5.tfplan').write_bytes(b'binary fixed')
            return c.canonical(document)
        engine.call=call;engine.plan(True)
        return engine,document,calls

    def test_dev_consent_expiry_during_final_readback_blocks_subprocess(self):
        engine,document,calls=self.engine('data');install_consent(engine.request,engine.protected)
        engine.destroy_seal['context_sha256']=engine.destroy_context()
        observed=[]
        def observe(env):observed.append('readback');return quiescent(env)
        engine.observe=observe
        with patch.object(runtime.time,'time',return_value=1100),patch.object(runtime.subprocess,'run') as process:
            with self.assertRaises(ValueError):engine._call(['apply','-input=false','wp5.tfplan'])
            process.assert_not_called()
        self.assertEqual(observed,['readback'])

    def test_dev_final_dispatch_requires_exact_request_and_current_consent(self):
        for fault in ('missing','wrong-layer','missing-consent'):
            engine,document,calls=self.engine('data')
            if fault!='missing-consent':install_consent(engine.request,engine.protected)
            if fault=='missing':engine.request=None
            elif fault=='wrong-layer':engine.request['layer']='apps'
            engine.destroy_seal['context_sha256']=engine.destroy_context()
            with patch.object(runtime.time,'time',return_value=NOW),patch.object(runtime.subprocess,'run') as process:
                with self.assertRaises(ValueError):engine._call(['apply','-input=false','wp5.tfplan'])
                process.assert_not_called()

    def test_exact_sealed_binary_only_no_replanning_after_selection(self):
        engine,document,calls=self.engine();before=len(calls)
        engine.apply(c.digest(c.canonical(document)))
        self.assertEqual([x[0] for x in calls[before:]],['show','apply'])
        self.assertEqual(calls[-1],['apply','-input=false','wp5.tfplan'])

    def test_binary_substitution_same_json_is_rejected(self):
        engine,document,calls=self.engine();(engine.directory/'wp5.tfplan').write_bytes(b'different binary')
        with self.assertRaises(ValueError):engine.apply(c.digest(c.canonical(document)))
        self.assertFalse(any(x[0]=='apply' for x in calls))

    def test_missing_plan_seal_file_workspace_or_changed_inputs_rejects(self):
        for fault in ('seal','file','workspace','variables','backend'):
            engine,document,calls=self.engine()
            if fault=='seal':engine.destroy_seal=None
            elif fault=='file':(engine.directory/'wp5.tfplan').unlink()
            elif fault=='workspace':engine.environment['TF_WORKSPACE']='prod'
            elif fault=='variables':(engine.directory/'wp5.auto.tfvars.json').write_bytes(b'{"changed":true}')
            else:engine.layer['backend']['bucket']='foreign'
            with self.assertRaises(ValueError):engine.apply(c.digest(c.canonical(document)))
            self.assertFalse(any(x[0]=='apply' for x in calls))

    def test_zero_requested_running_pending_and_positive_desired_all_block(self):
        for field in ('desired','running','pending'):
            engine,document,calls=self.engine();q=quiescent();next(iter(q['services'].values()))[field]=1
            engine.observe=lambda env:q
            with self.assertRaises(ValueError):engine.apply(c.digest(c.canonical(document)))
            self.assertFalse(any(x[0]=='apply' for x in calls))

    def test_task_list_or_missing_readback_blocks(self):
        for observed in ({}, {**quiescent(),'tasks':['running']},{**quiescent(),'complete':False}):
            engine,document,calls=self.engine();engine.observe=lambda env:observed
            with self.assertRaises(ValueError):engine.apply(c.digest(c.canonical(document)))
            self.assertFalse(any(x[0]=='apply' for x in calls))

    def test_final_runtime_pre_subprocess_recheck_catches_growth_after_earlier_read(self):
        engine,document,calls=self.engine();engine._call=runtime.Terraform._call.__get__(engine)
        q=quiescent();next(iter(q['services'].values()))['running']=1;engine.observe=lambda env:q
        with patch('scripts.lifecycle.runtime.subprocess.run') as process,self.assertRaises(ValueError):
            engine._call(['apply','-input=false','wp5.tfplan'])
        process.assert_not_called()

    def test_quiet_workload_snapshot_does_not_prove_controller_or_schedule_closure(self):
        c.quiescent(quiescent(),'dev')
        result=lab.report('down-preview',ACCOUNT,REGION,confirm_dev=True,confirm_sql_loss=True,sql_policy='DISPOSABLE')
        self.assertFalse(result['execution_authorized'])
        self.assertIn('ACTIVE_COLOR_QUIESCENCE_AUTHORITY_MISSING',result['gates'])


class Interruption(unittest.TestCase):
    def test_e2_active_or_interrupted_owner_blocks_real_wp5_controller(self):
        for interrupted in (False,True):
            s3=Coordination();store=s3.seed('dev');binding,p,v,document=fixture('platform')
            old=e.Authority(store,'normal-delivery/deploy-dev',NEXT,{});old.acquire()
            peer=e.Authority(store,binding,UUID,v,layer='platform');engine=Engine(document)
            result=e.execute(peer,lambda _:Controller(binding,p,Checked(),engine,Memory()).run(v),state_key='state')
            self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(engine.applies,0)
            self.assertEqual(store.read()[0]['owner'],old.owner)

    def test_e4_uncertain_owner_blocks_down_and_no_takeover(self):
        case=test_post_switch.Recovery();case.configure();case.partial();binding,p,v,document=fixture('platform')
        engine=Engine(document);peer=e.Authority(case.store,binding,UUID,v,layer='platform')
        result=e.execute(peer,lambda _:Controller(binding,p,Checked(),engine,Memory()).run(v),state_key='state')
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(engine.applies,0)
        self.assertEqual(case.store.read()[0]['state'],'ACTIVE')

    def test_protected_reverse_layer_progression_and_partial_failure_stops(self):
        # Compose existing controllers in a fixture only: no production batch
        # orchestrator or uninterrupted multi-layer grant is introduced.
        for failing in (None,'data'):
            s3=Coordination();store=s3.seed('dev');completed=[];calls=[]
            for index,layer in enumerate(down.DOWN):
                binding,p,v,document=fixture(layer);v['operation_id']=f'{index+1:08x}-1111-4111-8111-111111111111'
                p['operation_approvals']={v['operation_id']:dict(request_sha256=c.digest(c.canonical(v)),environment='dev')}
                p['teardown_approvals']={v['operation_id']:dict(revision=v['revision'],layer=layer,environment='dev')}
                if layer=='data':install_consent(v,p)
                owner=e.Authority(store,binding,v['operation_id'],v,layer=layer);engine=Engine(document)
                def apply(*args):
                    def effect():
                        calls.append(layer)
                        if layer==failing:raise TimeoutError('ambiguous')
                    owner.call(effect)
                engine.apply=apply;records=Memory();controller=Controller(binding,p,Checked(),engine,records)
                with patch('scripts.lifecycle.controller.time.time',return_value=NOW):result=e.execute(owner,lambda _:controller.run(v),state_key='state')
                if result['state']!='SUCCESS':
                    self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(store.read()[0]['state'],'ACTIVE')
                    self.assertEqual(controller.run(v)['state'],'UNKNOWN');break
                completed.append(layer)
            self.assertEqual(completed,list(down.DOWN) if failing is None else ['edge','apps','platform'])
            self.assertEqual(calls,list(down.DOWN) if failing is None else ['edge','apps','platform','data'])

    def test_failed_independent_readback_is_never_success(self):
        binding,p,v,document=fixture();install_consent(v,p);engine=Engine(document)
        engine.verify=lambda *args:False;records=Memory()
        with patch('scripts.lifecycle.controller.time.time',return_value=NOW):result=Controller(binding,p,Checked(),engine,records).run(v)
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(engine.applies,1)


class NatBoundary(unittest.TestCase):
    def run_nat(self,aws,store,event=None,operation=UUID):
        module=test_nat.bootstrap();aws.config['binding']='nat-recovery/nat-dev/assign_eip'
        return module._nat(dict(ec2=aws,autoscaling=aws,iam=aws,s3=store),aws.config,operation,event or aws.event)

    def test_late_event_can_still_reach_actual_nat_mutation_after_local_quiet_request(self):
        with patch.dict(sys.modules):
            aws=test_nat.AWS();store=test_nat.S3();aws.quiet_requested=True
            self.assertEqual(self.run_nat(aws,store)['status'],'SUCCESS')
            self.assertEqual([x[0] for x in aws.calls],['assign_eip'])
            self.assertIn('NAT_EVENT_AND_INFLIGHT_RETIREMENT_REQUIRED',lab.report('down-preview',ACCOUNT,REGION)['gates'])

    def test_e2_down_owner_is_not_a_nat_mutation_fence(self):
        with patch.dict(sys.modules):
            s3=Coordination();head=s3.seed('dev');binding,p,v,_=fixture('global')
            owner=e.Authority(head,binding,UUID,v,layer='global');owner.acquire()
            aws=test_nat.AWS();self.assertEqual(self.run_nat(aws,test_nat.S3())['status'],'SUCCESS')
            self.assertEqual(len(aws.calls),1);self.assertEqual(head.read()[0]['state'],'ACTIVE')

    def test_inflight_nat_effect_can_finish_after_quiet_request_controlled_interleaving(self):
        with patch.dict(sys.modules):
            module=test_nat.bootstrap();aws=test_nat.AWS();store=test_nat.S3()
            aws.config['binding']='nat-recovery/nat-dev/assign_eip'
            entered=threading.Event();release=threading.Event();results=[];errors=[]
            original=aws.associate_address
            def paused(**kwargs):
                entered.set()
                if not release.wait(5):raise TimeoutError('fixture release absent')
                original(**kwargs)
            aws.associate_address=paused
            def worker():
                try:results.append(module._nat(dict(ec2=aws,autoscaling=aws,iam=aws,s3=store),aws.config,UUID,aws.event))
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start()
            try:
                self.assertTrue(entered.wait(5));self.assertEqual(aws.calls,[])
                aws.quiet_requested=True;release.set();thread.join(5)
                self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
                self.assertEqual(results[0]['status'],'SUCCESS');self.assertEqual(len(aws.calls),1)
            finally:release.set();thread.join(5)

    def test_delayed_retry_retains_unknown_without_resending_and_cannot_prove_quiet(self):
        with patch.dict(sys.modules):
            aws=test_nat.AWS();store=test_nat.S3()
            def ambiguous(**kwargs):aws.calls.append(('assign_eip',kwargs));raise TimeoutError('unknown')
            aws.associate_address=ambiguous
            with self.assertRaises(ValueError):self.run_nat(aws,store)
            with self.assertRaises(ValueError):self.run_nat(aws,store)
            self.assertEqual(len(aws.calls),1)
            self.assertTrue(any(b'UNCERTAIN' in raw for raw in store.values.values()))

    def test_wrong_environment_or_missing_nat_membership_rejects(self):
        with patch.dict(sys.modules):
            aws=test_nat.AWS();event=copy.deepcopy(aws.event);event['account']='999999999999'
            with self.assertRaises(ValueError):self.run_nat(aws,test_nat.S3(),event)
            self.assertEqual(aws.calls,[])

    def test_no_new_nat_fence_authority_or_alternative_terraform_cli(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        for kind in ('wp4d','wp5'):
            for field in ('installations','runtime_approvals','environment_bindings'):self.assertEqual(authority[kind][field],{})
        self.assertEqual(authority['wp6']['approvals'], __import__('wp6').dev_trial_approvals(authority))
        self.assertEqual(lab.DOWN,down.DOWN)
        self.assertEqual(lab.RETAINED_LAYERS,('shared','secrets'))
