"""Faithful SDK interfaces are synthetic; no service/IAM/installation proof."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts.lifecycle import handoff as h, runtime, exact_destroy as x, contract as c, dev_down as down
from scripts import environment_mutation as e, ephemeral_lab as lab
from test_exact_destroy import Base, Error
from test_dev_down import NOW, UUID, NEXT
from test_lifecycle import ACCOUNT, REGION, quiescent, DOC
from scripts.tests.mutation.test_mutation import S3 as Coordination
import wp5_iam

ADMIN_ID='AROA'+'A'*17
EXEC_ID='AROA'+'B'*17
ROOT=Path(__file__).resolve().parents[3]


class SDK(Coordination):
    def __init__(self):
        super().__init__();self.history={};self.reads=[];self.write_fault=None;self.before=None
    def put_object(self,**args):
        if self.before:self.before(args)
        if self.write_fault==('before',args['Key']):raise TimeoutError('lost publication')
        if getattr(self,'decision_barrier',None) and args['Key'].endswith('/decision.json'):
            self.decision_barrier.wait(5)
        try:super().put_object(**args)
        except FileExistsError:raise Error('PreconditionFailed')
        key=args['Bucket'],args['Key'];raw,ver=self.values[key]
        self.history[(*key,str(ver))]=raw
        if self.write_fault==('after',args['Key']):raise TimeoutError('lost acknowledgement')
        return dict(VersionId=str(ver))
    def get_object(self,**args):
        self.reads.append(copy.deepcopy(args))
        if self.fail_read:raise OSError('storage unavailable')
        if 'ExpectedBucketOwner' in args:
            assert args['ExpectedBucketOwner']==ACCOUNT
        if 'VersionId' in args:
            key=args['Bucket'],args['Key'],args['VersionId']
            if key not in self.history:raise Error('NoSuchVersion')
            raw=self.history[key]
            return dict(Body=io.BytesIO(raw),VersionId=args['VersionId'],ServerSideEncryption='AES256')
        result=super().get_object(**args)
        return dict(result,ServerSideEncryption='AES256')
    def seed_object(self,bucket,key,raw):
        return self.put_object(Bucket=bucket,Key=key,Body=raw,IfNoneMatch='*')
    def replace_fixture(self,bucket,key,raw):
        # Fault injection violating installed no-overwrite assumptions.
        self.version+=1;self.values[bucket,key]=raw,self.version
        self.history[bucket,key,str(self.version)]=raw


class STS:
    """Hermetic service response double, not verified AWS identity."""
    def __init__(self,admin=False):self.admin=admin;self.override=None;self.calls=0
    def get_caller_identity(self):
        self.calls+=1
        if isinstance(self.override,Exception):raise self.override
        if self.override is not None:return copy.deepcopy(self.override)
        name='SeparateHumanAdmin' if self.admin else 'e1-controller-infra-high-risk-dev-exec'
        unique=ADMIN_ID if self.admin else EXEC_ID
        return dict(Account=ACCOUNT,Arn=f'arn:aws:sts::{ACCOUNT}:assumed-role/{name}/offline-session',UserId=unique+':offline-session')


class Case(Base):
    def setup_handoff(self,layer='platform',publish=True,approve=True,acquire_execution=True):
        self.setup_case(layer,approve=False)
        self.sdk=SDK();self.admin=STS(True);self.executor_sts=STS()
        self.install=dict(schema='E15D_HANDOFF_INSTALLATION_V1',binding=x.BINDING,account=ACCOUNT,region=REGION,
            revision=self.v['revision'],source_commit=self.p['installations'][self.v['revision']]['source_commit'],
            administrator_role=f'arn:aws:iam::{ACCOUNT}:role/SeparateHumanAdmin',administrator_role_id=ADMIN_ID,
            executor_role_id=EXEC_ID,storage_contract='E15D_PRIVATE_VERSIONED_CONDITIONAL_NO_DELETE_V1')
        bucket,key=h.installation_location(self.p)
        self.install_ref=h.Storage(self.sdk,ACCOUNT).put(bucket,key,c.canonical(self.install))
        self.p['bootstrap']['exact_destroy_handoff']=copy.deepcopy(self.install_ref)
        self.current_key='lifecycle/'+x.BINDING+'/current.json'
        self.sdk.seed_object(bucket,self.current_key,c.canonical(self.p))
        self.state=dict(lineage=UUID,serial=4,resources=[])
        backend=self.p['layers'][layer]['backend'];self.backend=backend
        self.sdk.seed_object(backend['bucket'],backend['key'],c.canonical(self.state))
        self.head=e.Store(self.sdk,f'e1-wp4-dev-{ACCOUNT}-{REGION}','dev','application');self.head.initialize()
        self.prep_request=dict(self.v,operation_id=NEXT,operation='plan')
        self.prep=e.Authority(self.head,x.BINDING,NEXT,self.prep_request,layer=layer);self.prep.acquire()
        self.engine.authority=self.prep;self.engine.protected=self.p
        self.engine.destroy=True
        self.engine.destroy_seal=dict(binary_sha256=c.digest(self.binary),json_sha256=c.digest(c.canonical(self.document)),
            context_sha256=self.engine.destroy_context())
        (self.root/'wp5.tfplan').write_bytes(self.binary)
        self.publisher=h.Handoff(self.sdk,self.executor_sts,self.p,self.v,self.engine)
        if publish:self.prepared=self.publisher.publish_prepared(self.prep,1100,NOW)
        self.prep.finish(successful=True,status='SUCCESS')
        self.owner=e.Authority(self.head,x.BINDING,UUID,self.v,layer=layer)
        if acquire_execution:self.owner.acquire()
        self.engine.authority=self.owner
        self.administrative=h.Handoff(self.sdk,self.admin,self.p,self.v,self.engine)
        if approve:self.approval=x.issue(self.administrative,self.v,self.p,self.confirm,900,1050,NOW)
        self.engine.exact_destroy=h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
        self.execution=self.engine.exact_destroy;self.channel=self.execution.channel
        self.journal=self.execution.journal
        (self.root/'wp5.tfplan').unlink()
        return self.channel
    def change_install(self,**fields):
        self.install.update(fields)
        raw=c.canonical(self.install);bucket,key=h.installation_location(self.p)
        self.sdk.replace_fixture(bucket,key,raw)
        self.p['bootstrap']['exact_destroy_handoff']=dict(bucket=bucket,key=key,version_id=str(self.sdk.version),sha256=c.digest(raw))
    def change_state(self,**fields):
        self.state.update(fields);self.sdk.replace_fixture(self.backend['bucket'],self.backend['key'],c.canonical(self.state))
    def approve_again(self):return x.issue(self.administrative,self.v,self.p,self.confirm,900,1050,NOW)


class StorageTests(Case):
    def test_real_adapter_publishes_three_exact_preparation_versions(self):
        self.setup_handoff()
        selected=self.channel.resolve();packet=self.channel.read_prepared(self.v,self.p)
        self.assertEqual(packet['binary'],self.binary);self.assertEqual(packet['plan'],self.document)
        self.assertEqual(selected['prepared'],self.prepared)
        for ref in packet['artifacts'].values():self.assertTrue(ref['version_id']);self.assertEqual(len(ref['sha256']),64)
    def test_private_conditional_encrypted_publication_calls(self):
        self.setup_handoff()
        writes=[v for v in self.sdk.calls if '/exact-destroy/' in v['Key'] or v['Key'].endswith('approval.json') or v['Key'].endswith('selection.json')]
        self.assertEqual(len(writes),5)
        for args in writes:
            self.assertEqual(args['IfNoneMatch'],'*');self.assertEqual(args['ServerSideEncryption'],'AES256')
            self.assertEqual(args['ExpectedBucketOwner'],ACCOUNT);self.assertNotIn('ACL',args)
    def test_version_pinned_load_ignores_new_foreign_binary_version(self):
        self.setup_handoff();self.channel.resolve();packet=self.channel.read_prepared(self.v,self.p)
        ref=packet['artifacts']['binary'];self.sdk.replace_fixture(ref['bucket'],ref['key'],b'foreign latest')
        self.assertEqual(self.load(),self.document)
    def test_exact_version_binary_corruption_blocks(self):
        self.setup_handoff();self.channel.resolve();packet=self.channel.read_prepared(self.v,self.p)
        ref=packet['artifacts']['binary'];self.sdk.history[ref['bucket'],ref['key'],ref['version_id']]=b'substituted'
        self.denied(self.load)
    def test_json_corruption_blocks(self):
        self.setup_handoff();self.channel.resolve();packet=self.channel.read_prepared(self.v,self.p)
        ref=packet['artifacts']['json'];self.sdk.history[ref['bucket'],ref['key'],ref['version_id']]=b'{}'
        self.denied(self.load)
    def test_context_corruption_blocks(self):
        self.setup_handoff();manifest=h.document(self.sdk.history[self.prepared['bucket'],self.prepared['key'],self.prepared['version_id']])
        manifest['packet']['seal']['context_sha256']='0'*64
        self.sdk.history[self.prepared['bucket'],self.prepared['key'],self.prepared['version_id']]=c.canonical(manifest)
        self.denied(self.load)
    def test_missing_version_or_digest_rejected(self):
        self.setup_handoff()
        for field in ('version_id','sha256'):
            ref=copy.deepcopy(self.install_ref);ref.pop(field)
            with self.assertRaises(ValueError):h.Storage(self.sdk,ACCOUNT).get(ref,*h.installation_location(self.p))
    def test_missing_exact_version_fails_closed(self):
        self.setup_handoff();del self.sdk.history[self.install_ref['bucket'],self.install_ref['key'],self.install_ref['version_id']]
        with self.assertRaises(Exception):h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
    def test_unencrypted_readback_blocks(self):
        self.setup_handoff();original=self.sdk.get_object
        self.sdk.get_object=lambda **kw:dict(original(**kw),ServerSideEncryption='aws:kms')
        self.denied(self.load)
    def test_duplicate_publication_never_overwrites_or_selects_new_plan(self):
        self.setup_handoff(approve=False)
        with self.assertRaises(Exception):self.publisher.publish_prepared(self.prep,1100,NOW)
        with self.assertRaises(Exception):
            bucket,prefix=x.location(down.scope(self.v,self.p));h.Storage(self.sdk,ACCOUNT).put(bucket,prefix+'plan.bin',b'new-plan')
    def test_partial_approval_publication_has_no_ready_selection(self):
        self.setup_handoff(approve=False)
        bucket,prefix=h.approval_prefix(down.scope(self.v,self.p));self.sdk.write_fault=('before',prefix+'selection.json')
        with self.assertRaises(TimeoutError):self.approve_again()
        self.denied(self.load)
        self.sdk.write_fault=None
        with self.assertRaises(Exception):self.approve_again()
    def test_lost_publication_ack_is_not_retried(self):
        self.setup_handoff(approve=False)
        bucket,key=x.approval_location(down.scope(self.v,self.p));self.sdk.write_fault=('after',key)
        with self.assertRaises(TimeoutError):self.approve_again()
        self.assertIn((bucket,key),self.sdk.values)
        self.sdk.write_fault=None
        with self.assertRaises(Exception):self.approve_again()
    def test_preparation_requires_current_distinct_plan_owner(self):
        self.setup_handoff(publish=False,approve=False)
        with self.assertRaises(ValueError):self.publisher.publish_prepared(self.owner,1100,NOW)
    def test_foreign_artifact_paths_rejected_before_read(self):
        self.setup_handoff();ref=dict(self.install_ref,key='unrelated/secret')
        with self.assertRaises(ValueError):h.Storage(self.sdk,ACCOUNT).get(ref,*h.installation_location(self.p))


class IdentityTests(Case):
    def test_exact_administrative_session_is_verified_by_sdk(self):
        self.setup_handoff();identity=self.administrative.authenticate_admin()
        self.assertEqual(identity['role_arn'],self.install['administrator_role']);self.assertGreater(self.admin.calls,0)
    def test_caller_json_or_environment_cannot_supply_identity(self):
        self.setup_handoff(approve=False)
        self.admin.override=OSError('no verified session')
        with patch.dict(os.environ,approved_by='admin',AWS_ROLE_ARN=self.install['administrator_role']):
            with self.assertRaises(OSError):self.approve_again()
    def test_foreign_account_or_role_or_unique_id_blocks(self):
        for field,bad in (('Account','999999999999'),('Arn',f'arn:aws:sts::{ACCOUNT}:assumed-role/e1-request-infra-high-risk-dev/offline-session'),('UserId',EXEC_ID+':offline-session')):
            self.setup_handoff(approve=False);self.admin.override=self.admin.get_caller_identity();self.admin.override[field]=bad
            with self.assertRaises(ValueError):self.approve_again()
    def test_same_role_name_recreated_with_different_id_blocks(self):
        self.setup_handoff();self.executor_sts.override=self.executor_sts.get_caller_identity()
        self.executor_sts.override['UserId']='AROA'+'C'*17+':offline-session';self.denied(self.load)
    def test_missing_identity_adapter_blocks(self):
        self.setup_handoff()
        with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,None,lambda:NOW)
    def test_missing_storage_adapter_blocks(self):
        self.setup_handoff()
        with self.assertRaises(ValueError):h.executor(self.engine,None,self.executor_sts,lambda:NOW)
    def test_uninstalled_handoff_blocks_before_sts(self):
        self.setup_handoff();self.p['bootstrap'].pop('exact_destroy_handoff');calls=self.executor_sts.calls
        with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
        self.assertEqual(calls,self.executor_sts.calls)
    def test_boolean_installation_cannot_authenticate(self):
        self.setup_handoff();self.p['bootstrap']['exact_destroy_handoff']=True
        with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
    def test_workload_role_cannot_be_installed_as_admin(self):
        self.setup_handoff();self.change_install(administrator_role=f'arn:aws:iam::{ACCOUNT}:role/e1-controller-infra-high-risk-dev-exec')
        with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
    def test_foreign_installation_scope_or_source_rejected(self):
        for field,bad in (('account','999999999999'),('binding','environment-lifecycle/infra-high-risk-prod'),('revision','0'*64),('source_commit','0'*40)):
            self.setup_handoff();self.change_install(**{field:bad})
            with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,self.executor_sts,lambda:NOW)
    def test_executor_cannot_publish_approval(self):
        self.setup_handoff(approve=False);self.administrative.sts=self.executor_sts
        with self.assertRaises(ValueError):self.approve_again()
    def test_administrator_cannot_impersonate_executor(self):
        self.setup_handoff()
        with self.assertRaises(ValueError):h.executor(self.engine,self.sdk,self.admin,lambda:NOW)


class SelectionTests(Case):
    def test_cross_invocation_resolution_loads_same_approval_and_binary(self):
        self.setup_handoff();channel=h.Handoff(self.sdk,STS(),self.p,self.v,self.engine)
        self.assertEqual(channel.approved_reference(self.v,self.p),self.approval)
        self.assertEqual(channel.read_prepared(self.v,self.p)['binary'],self.binary)
        self.assertEqual(self.load(),self.document)
    def test_wrong_operation_or_layer_has_no_selection(self):
        for field,bad in (('operation_id',NEXT),('layer','edge')):
            self.setup_handoff();value=dict(self.v,**{field:bad})
            with self.assertRaises(Exception):h.Handoff(self.sdk,self.executor_sts,self.p,value,self.engine)
    def test_conflicting_selection_is_rejected(self):
        self.setup_handoff();self.channel.resolve();bucket,prefix=h.approval_prefix(down.scope(self.v,self.p))
        record=copy.deepcopy(self.channel.selection[1]);record['approval']['version_id']='new-candidate'
        self.sdk.replace_fixture(bucket,prefix+'selection.json',c.canonical(record));self.denied(self.load)
    def test_foreign_selected_approval_bucket_rejected(self):
        self.setup_handoff();bucket,prefix=h.approval_prefix(down.scope(self.v,self.p));ref,raw=h.Storage(self.sdk,ACCOUNT).anchor(bucket,prefix+'selection.json')
        record=h.document(raw);record['approval']['bucket']='foreign-bucket';self.sdk.replace_fixture(bucket,prefix+'selection.json',c.canonical(record))
        self.denied(self.load)
    def test_missing_selection_or_approval_blocks(self):
        for suffix in ('selection.json','approval.json'):
            self.setup_handoff();bucket,prefix=h.approval_prefix(down.scope(self.v,self.p))
            if suffix=='selection.json':del self.sdk.values[bucket,prefix+suffix]
            else:
                ref=self.approval;del self.sdk.history[bucket,ref['key'],ref['version_id']]
            self.denied(self.load)
    def test_expired_approval_blocks(self):
        self.setup_handoff();self.execution.clock=lambda:1050;self.denied(self.load)
    def test_withdrawn_approval_competes_in_existing_journal(self):
        self.setup_handoff();x.withdraw(self.administrative,self.v,self.p,self.journal,NOW)
        self.assertEqual(self.journal.read('decision')['state'],'WITHDRAWN');self.load();self.denied(self.dispatch)
    def test_current_state_or_configuration_change_blocks(self):
        self.setup_handoff();self.load();self.change_state(serial=5);self.denied(self.dispatch)
        self.setup_handoff();self.load();changed=copy.deepcopy(self.p);changed['bootstrap']['sql_passwords']='UNVERIFIED'
        self.sdk.replace_fixture('demo-release-artifacts-'+ACCOUNT,self.current_key,c.canonical(changed));self.denied(self.dispatch)
    def test_protected_readback_unavailable_blocks(self):
        self.setup_handoff();self.load();self.sdk.fail_read=True;self.denied(self.dispatch)
    def test_missing_destroy_or_sql_confirmation_blocks(self):
        for field in ('destroy_ack','sql_loss_ack'):
            self.setup_handoff('data',approve=False);self.confirm[field]=''
            with self.assertRaises(ValueError):self.approve_again()
    def test_no_prod_or_shared_scope_reuse(self):
        for field,bad in (('environment','prod'),('binding','environment-lifecycle/infra-high-risk-prod')):
            self.setup_handoff();p=copy.deepcopy(self.p);p[field]=bad
            with self.assertRaises(ValueError):h.Handoff(self.sdk,self.executor_sts,p,self.v,self.engine)
        self.setup_handoff();value=dict(self.v,layer='shared')
        with self.assertRaises(ValueError):h.Handoff(self.sdk,self.executor_sts,self.p,value,self.engine)


class RuntimeTests(Case):
    def test_approved_journal_parallel_claimants_have_one_winner(self):
        self.setup_handoff();self.channel.approved_reference(self.v,self.p)
        self.sdk.decision_barrier=threading.Barrier(2);results=[]
        def contender(number):
            journal=x.DecisionJournal(self.sdk,down.scope(self.v,self.p))
            try:journal.put_once('decision',dict(state='CONSUMPTION_CLAIMED',approval=self.approval,consumer=str(number)));results.append('claimed')
            except Error:results.append('blocked')
        threads=[threading.Thread(target=contender,args=(n,)) for n in (1,2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10);self.assertFalse(thread.is_alive())
        self.assertCountEqual(results,['claimed','blocked'])
    def test_claim_competes_with_authenticated_withdrawal(self):
        self.setup_handoff();self.sdk.decision_barrier=threading.Barrier(2);results=[]
        def claim():
            try:self.journal.put_once('decision',dict(state='CONSUMPTION_CLAIMED',approval=self.approval));results.append('claim')
            except Error:results.append('claim-blocked')
        def withdraw():
            try:x.withdraw(self.administrative,self.v,self.p,self.journal,NOW);results.append('withdraw')
            except Error:results.append('withdraw-blocked')
        threads=[threading.Thread(target=fn) for fn in (claim,withdraw)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(10);self.assertFalse(thread.is_alive())
        self.assertEqual(sum(item in ('claim','withdraw') for item in results),1)
    def test_lost_claim_ack_and_replay_do_not_reopen_operation(self):
        self.setup_handoff();key=self.journal.prefix+'decision.json';self.sdk.write_fault=('after',key)
        with self.assertRaises(TimeoutError):self.journal.put_once('decision',dict(state='CONSUMPTION_CLAIMED',approval=self.approval))
        self.sdk.write_fault=None
        with self.assertRaises(Error):self.journal.put_once('decision',dict(state='CONSUMPTION_CLAIMED',approval=self.approval))
        self.assertIsNotNone(self.journal.read('decision'));self.assertIsNone(self.journal.read('attempt'))

    def test_saved_binary_runtime_path_still_blocks_ecs_and_nat_before_claim(self):
        self.setup_handoff();self.load();self.denied(self.dispatch)
        self.assertIsNone(self.journal.read('decision'));self.assertIsNone(self.journal.read('attempt'))
    def test_no_public_down_authority_or_synthetic_quietness_flag(self):
        self.setup_handoff()
        with self.assertRaises(ValueError):lab.report('down-execute',ACCOUNT,REGION,confirm_dev=True,confirm_sql_loss=True,sql_policy='DISPOSABLE')
        with self.assertRaises(ValueError):self.channel.require_down_quiescence(self.v,self.p,self.owner)
    def test_wrong_generation_blocks_before_quietness(self):
        self.setup_handoff();self.load();self.owner.value['generation']=1;self.denied(self.dispatch)
    def test_e2_active_interrupted_or_uncertain_owner_not_overridden(self):
        self.setup_handoff();self.load();head,etag=self.head.read();self.head.exchange(dict(head,owner=NEXT),etag)
        self.denied(self.dispatch);self.assertEqual(self.head.read()[0]['state'],'ACTIVE')
        peer=e.Authority(self.head,x.BINDING,NEXT,dict(self.v,operation_id=NEXT),layer=self.v['layer'])
        with self.assertRaises(e.CoordinationError):peer.acquire()
    def test_real_administrative_runtime_entry_uses_session_and_private_storage(self):
        self.setup_handoff(approve=False)
        configuration=dict(binding=x.BINDING,account=ACCOUNT,region=REGION,package=self.engine.reference)
        def prepare(engine,reference,layer,parameters):
            engine.directory=self.root;engine.layer=layer;engine.reference=reference;engine.environment={'TF_WORKSPACE':'default'}
        with patch.object(runtime.packages,'verify',return_value=self.engine.reference),patch.object(runtime.Terraform,'prepare',prepare),patch.object(runtime.Terraform,'call',return_value=c.canonical(self.document)):
            result=runtime.approve_destroy(self.v,configuration,dict(s3=self.sdk,sts=self.admin,ecs=None),self.confirm,900,1050,NOW)
        self.assertEqual(result['key'],x.approval_location(down.scope(self.v,self.p))[1]);self.assertGreater(self.admin.calls,0)
    def test_administrative_runtime_entry_rejects_workload_credentials_before_plan(self):
        self.setup_handoff(approve=False);configuration=dict(binding=x.BINDING,account=ACCOUNT,region=REGION,package=self.engine.reference)
        with patch.object(runtime.Terraform,'prepare') as prepare,self.assertRaises(ValueError):
            runtime.approve_destroy(self.v,configuration,dict(s3=self.sdk,sts=self.executor_sts,ecs=None),self.confirm,900,1050,NOW)
        prepare.assert_not_called()
    def test_protected_execute_resolves_handoff_without_enabling_terraform(self):
        self.setup_handoff(acquire_execution=False)
        build='e1-controller-infra-high-risk-dev:offline-build'
        requests='requests/infra-high-risk-dev/'
        bucket=f'e1-lifecycle-dev-{ACCOUNT}-{REGION}'
        self.sdk.seed_object(bucket,requests+UUID+'/request.json',c.canonical(self.v))
        self.sdk.seed_object(bucket,requests+'builds/'+c.digest(build.encode())+'.json',c.canonical(dict(operation_id=UUID)))
        configuration=dict(binding=x.BINDING,account=ACCOUNT,region=REGION,package=self.engine.reference)
        def prepare(engine,reference,layer,parameters):
            engine.directory=self.root;engine.layer=layer;engine.reference=reference;engine.environment={'TF_WORKSPACE':'default'}
        original=runtime.Terraform._call
        def call(engine,args):
            if args[0]=='show':return c.canonical(self.document)
            return original(engine,args)
        with patch.dict(os.environ,CODEBUILD_BUILD_ID=build),patch.object(runtime.packages,'verify',return_value=self.engine.reference),patch.object(runtime.Terraform,'prepare',prepare),patch.object(runtime.Terraform,'observe',return_value=quiescent()),patch.object(runtime.Terraform,'_call',call),patch.object(runtime.time,'time',return_value=NOW),patch.object(runtime.subprocess,'run') as process:
            result=runtime.execute(None,configuration,dict(s3=self.sdk,sts=self.executor_sts,ecs=None))
            again=runtime.execute(None,configuration,dict(s3=self.sdk,sts=self.executor_sts,ecs=None))
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(result,again)
        self.assertEqual(result['exact_destroy_approval'],self.approval);process.assert_not_called()
    def test_plan_bytes_never_enter_public_result_or_error(self):
        self.setup_handoff();self.load()
        with self.assertRaises(ValueError) as failure:self.channel.require_down_quiescence(self.v,self.p,self.owner)
        self.assertNotIn(self.binary.decode(),str(failure.exception))
        approved=self.channel.read_approval(self.approval)['approval']
        self.assertNotIn('binary',approved);self.assertNotIn('plan',approved)
    def test_permission_requirements_are_exact_and_not_installed(self):
        self.setup_handoff();requirements=h.storage_requirements(down.scope(self.v,self.p))
        for name in ('artifact_objects','administrative_objects','decision_objects'):
            self.assertTrue(all(UUID in arn and '*' not in arn for arn in requirements[name]))
        current=wp5_iam.policy(x.BINDING,ACCOUNT,REGION,{},self.v['revision'],'package-version')
        approval_arn=requirements['administrative_objects'][0]
        self.assertFalse(any(approval_arn in statement['Resource'] for statement in current['Statement']))
        for kind in ('wp4d','wp5'):
            self.assertEqual(DOC[kind]['installations'],{});self.assertEqual(DOC[kind]['runtime_approvals'],{})
    def test_non_destroy_runtime_does_not_resolve_handoff(self):
        self.setup_handoff();self.engine.destroy=False;self.engine.exact_destroy=None
        with patch.object(runtime.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'')) as process:
            self.engine._call(['apply','-input=false','wp5.tfplan'])
        self.assertEqual(process.call_count,1)
