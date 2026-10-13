"""Production contract/journal/E2/runtime under explicitly synthetic trust ports."""
import ast
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.lifecycle import exact_destroy as x, runtime, contract as c, dev_down as down
from scripts.lifecycle.controller import Controller
from scripts import environment_mutation as e, ephemeral_lab as lab
from test_dev_down import fixture, consent, install_consent, NOW, UUID, NEXT
from test_lifecycle import quiescent, Memory, Checked, DOC, ACCOUNT, REGION
from scripts.tests.mutation.test_mutation import S3 as Coordination
from scripts.tests.post_switch import test_post_switch

ROOT=Path(__file__).resolve().parents[3]


class Error(Exception):
    def __init__(self,code):self.response={'Error':{'Code':code}}


class Objects:
    """SDK-shaped atomic fixture; lock models S3, not production process safety."""
    def __init__(self):
        self.values={};self.mutex=threading.Lock();self.calls=[];self.fail=None;self.barrier=None;self.after=None
    def put_object(self,**args):
        self.calls.append(args);key=(args['Bucket'],args['Key'])
        if self.barrier and key[1].endswith('/decision.json'):self.barrier.wait(5)
        with self.mutex:
            if key in self.values:raise Error('PreconditionFailed')
            if self.fail=='before':raise TimeoutError('write not acknowledged')
            assert args['IfNoneMatch']=='*'
            version='version-'+str(len(self.values)+1);self.values[key]=(args['Body'],version)
        if self.after:self.after(key)
        if self.fail=='after':raise TimeoutError('write acknowledged only remotely')
        return dict(VersionId=version)
    def get_object(self,**args):
        key=(args['Bucket'],args['Key'])
        with self.mutex:
            if key not in self.values:raise Error('NoSuchKey')
            raw,version=self.values[key]
        return dict(Body=io.BytesIO(raw),VersionId=version)


class TrustedFixture(x.ProtectedPlanChannel):
    """Not an installation or authentication implementation. No SDK/network."""
    def __init__(self,value,protected,binary,plan,seal):
        self.value,self.protected=value,protected;self.binary,self.document=binary,plan
        self.role=f'arn:aws:iam::{ACCOUNT}:role/security-root-admin'
        self.identity=dict(account=ACCOUNT,role_arn=self.role,
            principal_arn=f'arn:aws:sts::{ACCOUNT}:assumed-role/security-root-admin/offline-fixture')
        selected=down.scope(value,protected)
        context=dict(schema='E15B_DESTROY_REVIEW_V1',scope_sha256=selected['scope_sha256'],
            created_at=900,expires_at=1100,binary_sha256=c.digest(binary),json_sha256=c.digest(c.canonical(plan)),
            state=dict(lineage=UUID,serial=4,version_id='state-v4',sha256='d'*64),workspace='default')
        review=down.review(value,protected,binary,plan,context,NOW);bucket,prefix=x.location(selected)
        self.packet=dict(binary=binary,plan=plan,review=review,seal=seal,preparation_generation=0,
            artifacts=dict(binary=dict(bucket=bucket,key=prefix+'plan.bin',version_id='binary-v1',sha256=c.digest(binary)),
                json=dict(bucket=bucket,key=prefix+'plan.json',version_id='json-v1',sha256=c.digest(c.canonical(plan)))))
        self.current_value=dict(state=context['state'],configuration_sha256=c.digest(c.canonical(protected)))
        self.approval=None;self.ref=None;self.closed=True;self.effect=None;self.calls=[]
    def administrator_role(self):return self.role
    def authenticate_admin(self):return copy.deepcopy(self.identity)
    def read_prepared(self,*args):return copy.deepcopy(self.packet)
    def inspect_binary(self,binary):
        if binary!=self.binary:raise ValueError('unrecognized trusted fixture binary')
        return copy.deepcopy(self.document)
    def write_approval(self,value,approval):
        if self.approval is not None:raise Error('PreconditionFailed')
        self.approval=copy.deepcopy(approval);bucket,key=x.approval_location(down.scope(value,self.protected))
        self.ref=dict(bucket=bucket,key=key,version_id='admin-approved-v1',sha256=c.digest(c.canonical(approval)))
        return copy.deepcopy(self.ref)
    def approved_reference(self,*args):return copy.deepcopy(self.ref)
    def read_approval(self,ref):return dict(reference=copy.deepcopy(self.ref),approval=copy.deepcopy(self.approval))
    def current(self,*args):return copy.deepcopy(self.current_value)
    def require_down_quiescence(self,*args):
        self.calls.append('quiescence')
        if self.effect:self.effect()
        if not self.closed:raise ValueError('no accepted ECS/NAT settlement')


class Base(unittest.TestCase):
    def setup_case(self,layer='platform',approve=True,objects=None):
        self.binding,self.p,self.v,self.document=fixture(layer)
        self.confirm=consent(self.v,self.p)
        if layer=='data':install_consent(self.v,self.p)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.objects=objects or Objects()
        self.coordination=Coordination();self.head=self.coordination.seed('dev')
        self.owner=e.Authority(self.head,self.binding,UUID,self.v,layer=layer);self.owner.acquire()
        self.engine=runtime.Terraform(self.root,None,self.p,self.owner,request=self.v)
        self.engine.directory=self.root;self.engine.layer=self.p['layers'][layer]
        self.engine.reference=self.p['installations'][self.v['revision']]
        self.engine.environment=dict(TF_WORKSPACE='default')
        (self.root/'wp5.auto.tfvars.json').write_bytes(b'{}')
        self.engine.observe=lambda env:quiescent(env)
        self.binary=b'protected fixture binary; no AWS/provider'
        seal=dict(binary_sha256=c.digest(self.binary),json_sha256=c.digest(c.canonical(self.document)),
                  context_sha256=self.engine.destroy_context())
        self.channel=TrustedFixture(self.v,self.p,self.binary,self.document,seal)
        self.journal=x.DecisionJournal(self.objects,down.scope(self.v,self.p))
        self.execution=x.Execution(self.channel,self.journal,lambda:NOW);self.engine.exact_destroy=self.execution
        self.calls=[]
        def call(args):
            self.calls.append(args)
            if args[0]=='show':return c.canonical(self.document)
            if args[0]=='apply':return self.owner.call(runtime.Terraform._call.__get__(self.engine),args)
            raise AssertionError('unapproved fresh plan or command')
        self.engine.call=call
        if approve:self.approve()
        return self.engine
    def approve(self):return x.issue(self.channel,self.v,self.p,self.confirm,900,1050,NOW)
    def load(self):return self.engine.plan(True)
    def dispatch(self,response=None):
        with patch.object(runtime.subprocess,'run',return_value=response or SimpleNamespace(returncode=0,stdout=b'')) as process:
            self.engine.apply(c.digest(c.canonical(self.document)))
        return process
    def denied(self,fn):
        with patch.object(runtime.subprocess,'run') as process,self.assertRaises(Exception):fn()
        process.assert_not_called()


class Approval(Base):
    def test_correct_dev_approval_preserves_exact_e15b_review(self):
        self.setup_case();a=self.channel.approval
        self.assertEqual(a['review'],self.channel.packet['review']);self.assertEqual(a['state'],'APPROVED')
        self.assertEqual(a['expected_generation'],1);self.assertEqual(a['seal']['binary_sha256'],c.digest(self.binary))
        x.validate(self.channel,self.v,self.p,NOW)
    def test_admin_context_never_comes_from_caller_approved_by(self):
        self.setup_case(approve=False);self.channel.identity['approved_by']='admin'
        self.denied(self.approve)
    def test_foreign_admin_account_or_role_or_session_rejected(self):
        for field,bad in (('account','999999999999'),('role_arn',f'arn:aws:iam::{ACCOUNT}:role/e1-request-infra-high-risk-dev'),
                          ('principal_arn',f'arn:aws:sts::{ACCOUNT}:assumed-role/e1-request-infra-high-risk-dev/fixture')):
            self.setup_case(approve=False);self.channel.identity[field]=bad;self.denied(self.approve)
    def test_dict_cannot_supply_trusted_channel(self):
        self.setup_case();self.denied(lambda:x.issue(dict(approved_by='admin'),self.v,self.p,self.confirm,900,1050,NOW))
    def test_missing_infrastructure_confirmation_rejects(self):
        self.setup_case(approve=False);self.confirm['destroy_ack']='';self.denied(self.approve)
    def test_missing_sql_confirmation_rejects(self):
        self.setup_case('data',approve=False);self.confirm['sql_loss_ack']='';self.denied(self.approve)
    def test_changed_protected_sql_consent_rejected(self):
        self.setup_case('data');self.p['teardown_approvals']['dev-sql-loss/'+UUID]['expires_at']=999
        self.denied(self.load)
    def test_binary_substitution_same_summary_rejected(self):
        self.setup_case();self.channel.packet['binary']=b'another binary';self.denied(self.load)
    def test_json_must_correspond_to_protected_binary_render(self):
        self.setup_case(approve=False);packet=self.channel.packet
        packet['plan']['terraform_version']='another'
        packet['review']['context']['json_sha256']=c.digest(c.canonical(packet['plan']))
        packet['review']=down.review(self.v,self.p,packet['binary'],packet['plan'],packet['review']['context'],NOW)
        packet['seal']['json_sha256']=packet['review']['context']['json_sha256'];self.denied(self.approve)
    def test_different_layer_environment_backend_request_revision_rejected(self):
        for key,bad in (('layer','apps'),('revision','0'*64),('operation_id',NEXT)):
            self.setup_case();self.engine.request[key]=bad;self.denied(self.load)
        self.setup_case();self.p['environment']='prod';self.denied(self.load)
        self.setup_case();self.p['layers']['platform']['backend']['bucket']='foreign';self.denied(self.load)
    def test_changed_preparation_context_rejected(self):
        self.setup_case();(self.root/'wp5.auto.tfvars.json').write_bytes(b'{"changed":true}');self.denied(self.load)
    def test_approval_bytes_and_version_cannot_be_substituted(self):
        self.setup_case();self.channel.approval['expires_at']=1099;self.denied(self.load)
        self.setup_case();original=self.channel.read_approval
        self.channel.read_approval=lambda ref:{**original(ref),'reference':{**ref,'version_id':'other'}}
        self.denied(self.load)
    def test_corrupt_incomplete_approval_and_artifact_identity_rejected(self):
        for fault in ('missing','corrupt','foreign','version'):
            self.setup_case()
            if fault=='missing':del self.channel.approval['approver']
            elif fault=='corrupt':self.channel.ref['sha256']='0'*64
            elif fault=='foreign':self.channel.packet['artifacts']['binary']['bucket']='other'
            else:self.channel.packet['artifacts']['binary']['version_id']='latest'
            self.denied(self.load)
    def test_expired_missing_and_withdrawn_approval_rejected(self):
        self.setup_case();self.execution.clock=lambda:1050;self.denied(self.load)
        self.setup_case();self.channel.ref=None;self.denied(self.load)
        self.setup_case();self.channel.approval['state']='WITHDRAWN';self.denied(self.load)
    def test_no_invented_approval_ttl(self):
        self.setup_case(approve=False)
        for issued,expires in ((None,1050),(900,None),(1001,1050),(900,1200),(900,900)):
            self.denied(lambda:x.issue(self.channel,self.v,self.p,self.confirm,issued,expires,NOW))
    def test_stale_state_before_approval_rejected(self):
        self.setup_case(approve=False);self.channel.current_value['state']['serial']=5;self.denied(self.approve)


class Consumption(Base):
    def test_actual_saved_executor_consumes_once_no_fresh_plan(self):
        self.setup_case();self.load();process=self.dispatch()
        self.assertEqual(process.call_count,1)
        self.assertEqual(process.call_args.args[0],['/opt/e1/bin/terraform','apply','-input=false','wp5.tfplan'])
        self.assertFalse(any(args[0]=='plan' for args in self.calls))
        self.assertEqual(self.journal.read('decision')['state'],'CONSUMPTION_CLAIMED')
        self.assertEqual(self.journal.read('attempt')['state'],'EXECUTION_ATTEMPTED')
        self.assertTrue(all(x['IfNoneMatch']=='*' for x in self.objects.calls))
    def test_replay_same_executor_never_redispatches(self):
        self.setup_case();self.load();self.dispatch();self.denied(self.dispatch)
    def test_parallel_consumers_only_one_conditional_claim(self):
        self.setup_case();self.load();peer=x.Execution(self.channel,x.DecisionJournal(self.objects,down.scope(self.v,self.p)),lambda:NOW)
        peer.loaded=copy.deepcopy(self.execution.loaded);self.objects.barrier=threading.Barrier(2)
        outcomes=[]
        def worker(executor):
            try:executor.before_dispatch(self.engine);outcomes.append('claimed')
            except Exception:outcomes.append('blocked')
        threads=[threading.Thread(target=worker,args=(executor,)) for executor in (self.execution,peer)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10);self.assertFalse(thread.is_alive())
        self.assertCountEqual(outcomes,['claimed','blocked'])
        self.assertEqual(sum(k[1].endswith('/decision.json') for k in self.objects.values),1)
    def test_claim_and_authenticated_withdrawal_compete_atomically(self):
        self.setup_case();self.load();self.objects.barrier=threading.Barrier(2);outcomes=[]
        def claimant():
            try:self.execution.before_dispatch(self.engine);outcomes.append('claim')
            except Exception:outcomes.append('claim-blocked')
        def withdrawal():
            try:x.withdraw(self.channel,self.v,self.p,self.journal,NOW);outcomes.append('withdraw')
            except Exception:outcomes.append('withdraw-blocked')
        threads=[threading.Thread(target=fn) for fn in (claimant,withdrawal)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10);self.assertFalse(thread.is_alive())
        self.assertEqual(sum(outcome in ('claim','withdraw') for outcome in outcomes),1)
        self.assertEqual(self.journal.read('decision')['state'],
            'WITHDRAWN' if 'withdraw' in outcomes else 'CONSUMPTION_CLAIMED')

    def test_executor_render_differs_from_reviewed_json_blocks(self):
        self.setup_case();self.document=copy.deepcopy(self.document);self.document['terraform_version']='changed'
        self.denied(self.load);self.assertIsNone(self.journal.read('decision'))

    def test_source_commit_and_installed_configuration_changes_block(self):
        self.setup_case();self.p['installations'][self.v['revision']]['source_commit']='c'*40;self.denied(self.load)
        self.setup_case();self.p['layers']['platform']['membership']['resource.exact']='different-id';self.denied(self.load)

    def test_failure_after_claimed_state_drift_never_attempts_or_reopens(self):
        self.setup_case();self.load()
        self.objects.after=lambda key:self.channel.current_value['state'].update(serial=6) if key[1].endswith('/decision.json') else None
        self.denied(self.dispatch);self.assertIsNotNone(self.journal.read('decision'))
        self.assertIsNone(self.journal.read('attempt'));self.denied(self.dispatch)

    def test_incorrect_generation_rejected_before_claim(self):
        self.setup_case();self.load();self.owner.value['generation']=2;self.denied(self.dispatch)
        self.assertIsNone(self.journal.read('decision'))
    def test_withdrawal_before_claim_consumes_same_slot(self):
        self.setup_case();self.load();x.withdraw(self.channel,self.v,self.p,self.journal,NOW)
        self.denied(self.dispatch);self.assertEqual(self.journal.read('decision')['state'],'WITHDRAWN')
    def test_withdrawal_cannot_cancel_consumed_or_issued_effect(self):
        self.setup_case();self.load();self.dispatch()
        with self.assertRaises(Exception):x.withdraw(self.channel,self.v,self.p,self.journal,NOW)
        self.assertEqual(self.journal.read('decision')['state'],'CONSUMPTION_CLAIMED')
    def test_crash_after_claim_before_attempt_does_not_reopen_approval(self):
        self.setup_case();self.load()
        def fail_after_decision(key):
            if key[1].endswith('/decision.json'):raise TimeoutError('crash after claim')
        self.objects.after=fail_after_decision;self.denied(self.dispatch)
        self.assertIsNotNone(self.journal.read('decision'));self.assertIsNone(self.journal.read('attempt'))
        self.objects.after=None;self.denied(self.dispatch)
    def test_lost_claim_or_attempt_ack_never_dispatches(self):
        self.setup_case();self.load();self.objects.fail='after';self.denied(self.dispatch)
        self.assertIsNotNone(self.journal.read('decision'));self.objects.fail=None;self.denied(self.dispatch)
        self.setup_case();self.load()
        self.objects.after=lambda key: (_ for _ in ()).throw(TimeoutError('attempt ack lost')) if key[1].endswith('/attempt.json') else None
        self.denied(self.dispatch);self.assertIsNotNone(self.journal.read('attempt'))
    def test_changed_state_lineage_serial_version_digest_rejected(self):
        for field,bad in (('lineage',NEXT),('serial',5),('version_id','state-v5'),('sha256','0'*64)):
            self.setup_case();self.load();self.channel.current_value['state'][field]=bad;self.denied(self.dispatch)
    def test_state_change_during_quiescence_rejected(self):
        self.setup_case();self.load();self.channel.effect=lambda:self.channel.current_value['state'].update(serial=5)
        self.denied(self.dispatch);self.assertIsNone(self.journal.read('decision'))
    def test_revocation_or_expiry_during_quiescence_blocks(self):
        self.setup_case();self.load();self.channel.effect=lambda:setattr(self.channel,'ref',None)
        self.denied(self.dispatch)
        self.setup_case();self.load();self.channel.effect=lambda:setattr(self.execution,'clock',lambda:1050)
        self.denied(self.dispatch)
    def test_changed_saved_file_after_load_rejected(self):
        self.setup_case();self.load();(self.root/'wp5.tfplan').write_bytes(b'changed');self.denied(self.dispatch)
    def test_missing_journal_readback_blocks_even_successful_write(self):
        self.setup_case();self.load();original=self.objects.get_object
        self.objects.get_object=lambda **args:{**original(**args),'VersionId':'null'}
        self.denied(self.dispatch)


class Boundaries(Base):
    def test_valid_approval_missing_ecs_controller_closure_blocks(self):
        self.setup_case();self.load();self.channel.closed=False;self.denied(self.dispatch)
        self.assertIsNone(self.journal.read('decision'))
    def test_valid_approval_nat_late_effect_settlement_unproved_blocks(self):
        self.setup_case();self.load()
        def blocked(*args):raise NotImplementedError('NAT issued effect unresolved')
        self.channel.require_down_quiescence=blocked;self.denied(self.dispatch)
    def test_missing_readback_or_reactivated_workload_blocks(self):
        for observation in ({}, {**quiescent(),'tasks':['late-task']}):
            self.setup_case();self.load();self.engine.observe=lambda env:observation;self.denied(self.dispatch)
    def test_default_installed_runtime_denies_without_protected_adapter(self):
        self.setup_case();self.load();self.engine.exact_destroy=None;self.denied(self.dispatch)
    def test_approval_dict_cannot_enable_runtime(self):
        self.setup_case();self.load();self.engine.exact_destroy=self.channel.approval;self.denied(self.dispatch)
    def test_e2_active_interrupted_or_stale_owner_is_not_overridden(self):
        self.setup_case();self.load();old=self.owner;head=self.head.read()[0]
        self.head.exchange(dict(head,owner=NEXT),self.head.read()[1])
        self.denied(self.dispatch);self.assertEqual(self.head.read()[0]['state'],'ACTIVE')
        self.assertIsNone(self.journal.read('decision'))
    def test_e4_unknown_owner_blocks_before_approval_execution(self):
        case=test_post_switch.Recovery();case.configure();case.partial()
        self.setup_case();peer=e.Authority(case.store,self.binding,UUID,self.v,layer='platform');called=[]
        self.assertEqual(e.execute(peer,lambda _:called.append(True),state_key='state')['state'],'UNKNOWN')
        self.assertEqual(called,[])
    def test_public_cli_never_provides_approval_or_executes_down(self):
        self.setup_case();self.denied(lambda:lab.report('down-execute',ACCOUNT,REGION,confirm_dev=True,
            confirm_sql_loss=True,sql_policy='DISPOSABLE'))
        tree=ast.parse((ROOT/'scripts/ephemeral_lab.py').read_text())
        self.assertFalse(any(isinstance(n,(ast.Import,ast.ImportFrom)) and 'exact_destroy' in ast.unparse(n) for n in ast.walk(tree)))
    def test_controller_retains_exact_approval_attempt_and_unknown_without_resend(self):
        self.setup_case('data');engine=self.engine
        engine.prepare=lambda *args:None;engine.verify=lambda *args:False
        records=Memory();controller=Controller(self.binding,self.p,Checked(),engine,records)
        with patch.object(runtime.time,'time',return_value=NOW),patch.object(runtime.subprocess,'run',side_effect=TimeoutError('response lost')) as process:
            result=controller.run(self.v);self.assertEqual(result['state'],'UNKNOWN')
            self.assertEqual(result['exact_destroy_approval'],self.channel.ref)
            self.assertEqual(controller.run(self.v),result);self.assertEqual(process.call_count,1)
        self.assertIsNotNone(self.journal.read('attempt'))
    def test_success_requires_actual_controller_independent_readback(self):
        self.setup_case('data');self.engine.prepare=lambda *args:None;self.engine.verify=lambda *args:True
        records=Memory();controller=Controller(self.binding,self.p,Checked(),self.engine,records)
        with patch.object(runtime.time,'time',return_value=NOW),patch.object(runtime.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'')):
            result=controller.run(self.v)
        self.assertEqual(result['state'],'SUCCESS')  # synthetic port only, no AWS acceptance
        self.assertEqual(records.read(UUID)['binary_sha256'],c.digest(self.binary))
    def test_no_false_success_from_nonzero_apply_or_failed_readback(self):
        self.setup_case('data');self.engine.prepare=lambda *args:None;self.engine.verify=lambda *args:True
        records=Memory()
        with patch.object(runtime.time,'time',return_value=NOW),patch.object(runtime.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'private diagnostic withheld')):
            result=Controller(self.binding,self.p,Checked(),self.engine,records).run(self.v)
        self.assertEqual(result['state'],'UNKNOWN');self.assertNotIn('completed',str(records.values))
    def test_normal_and_prod_lifecycle_remain_outside_dev_approval(self):
        self.setup_case();self.engine.destroy=False
        with patch.object(runtime.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'')) as process:
            self.engine._call(['apply','-input=false','wp5.tfplan'])
        self.assertEqual(process.call_count,1);self.assertIsNone(self.journal.read('decision'))
        self.setup_case();self.p['environment']='prod';self.denied(self.load)
    def test_authority_unchanged_except_derived_package_hashes(self):
        import hashlib
        authority=copy.deepcopy(DOC)
        import ownership
        ownership.validate_publications(authority)
        # Authenticated first-session output metadata is now explicitly allowed;
        # the rest of the historical protected authority snapshot stays fixed.
        authority['ownership_closure']['publications']={}
        for group in ('wp4d','wp5'):
            for item in authority[group]['selected'].values():del item['package_sha256']
        self.assertEqual(hashlib.sha256(json.dumps(authority,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            '7a2a26aa8cbaf40411c8b7d4ebedcf1c53bc2492ce9a92a5cbdbe3142dac40ca')
        for kind in ('wp4d','wp5'):
            for field in ('installations','runtime_approvals','environment_bindings'):self.assertEqual(DOC[kind][field],{})
        self.assertEqual(DOC['wp6']['approvals'],{})
