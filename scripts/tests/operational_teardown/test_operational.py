"""E15-G real protected protocols; fakes cannot install complete DOWN."""
import copy
import uuid
from pathlib import Path
from unittest.mock import patch
import unittest
from scripts import environment_mutation as e
from scripts.lifecycle import operational as o, ecs_quiescence as q, contract as c, runtime, handoff
from scripts.nat import quiescence as nat
import test_ecs_quiescence as ef
import test_combined as cf
import test_dev_down as df
import test_handoff as hf
from scripts.tests.nat_quiescence import test_quiescence as nf
from scripts.tests.nat import test_nat
from test_lifecycle import ACCOUNT, REGION

ROOT = Path(__file__).resolve().parents[3]


class ECSOperational(unittest.TestCase):
    setUp = ef.Protocol.setUp
    make = ef.Protocol.make
    assert_held = ef.Protocol.assert_held

    def gone(self):
        self.aws.describe_clusters = lambda **kw:dict(clusters=[], failures=[
            {'arn':self.selected['cluster'], 'reason':'MISSING'}])

    def test_cooperative_drain_real_requests_and_actual_stopped_tasks(self):
        self.assertEqual(self.protocol.drain_until_quiet()['state'], 'QUIET')
        self.assertEqual(len(self.aws.calls), 2)
        self.assertTrue(all(t['lastStatus'] == 'STOPPED' for t in self.aws.tasks.values()))
        self.assert_held()

    def test_bounded_polling_pending_then_stopped_without_second_update(self):
        self.aws.drain_effect = False
        original = self.aws.describe_services
        count = [0]
        def read(**kw):
            count[0] += 1
            if count[0] == 4:
                for s in self.selected['services']:self.aws.zero(s)
            return original(**kw)
        self.aws.describe_services = read
        receipt = self.protocol.drain_until_quiet()
        self.assertEqual(receipt['state'], 'QUIET');self.assertGreater(receipt['sample'], 0)
        self.assertEqual(len(self.aws.calls), 2)

    def test_nonterminal_bounded_exhaustion_holds_original_owner(self):
        self.aws.drain_effect = False
        with self.assertRaises(q.Blocked):self.protocol.drain_until_quiet()
        self.assertEqual(len(self.aws.calls), 2)
        self.assertIsNotNone(self.journal.read('sample-15'));self.assert_held()

    def test_lost_update_response_no_automatic_retry(self):
        self.aws.fail = 'ambiguous-after'
        with self.assertRaises(TimeoutError):self.protocol.drain_until_quiet()
        self.assertEqual(len(self.aws.calls), 1);self.assert_held()

    def test_missing_task_is_not_pollable_nonterminal_evidence(self):
        original = self.aws.update_service
        def send(**kw):
            original(**kw);self.aws.tasks.clear()
        self.aws.update_service = send
        with self.assertRaises(ValueError):self.protocol.drain_until_quiet()
        self.assertIsNone(self.journal.read('sample-0'));self.assert_held()

    def test_seal_before_delete_consumes_stopped_cohort_after_absence(self):
        self.protocol.drain_until_quiet()
        seal = self.protocol.seal_before_cluster_delete()
        self.assertEqual(seal['owner'], self.owner.value)
        reads = len(self.aws.reads);self.gone()
        result = self.protocol.require_terminal_handoff('data')
        self.assertEqual(result['state'], 'TERMINAL_HANDOFF')
        self.assertEqual(len(self.aws.reads), reads)  # no DescribeTasks on deleted cluster
        self.assert_held()

    def test_service_absence_preserves_remembered_stopped_tasks(self):
        self.protocol.drain_until_quiet()
        self.aws.describe_services = lambda **kw:dict(services=[], failures=[
            {'arn':s, 'reason':'MISSING'} for s in self.selected['services']])
        seal = self.protocol.seal_before_cluster_delete()
        sample = self.journal.read('sample-' + str(seal['sample']['sample']))
        self.assertEqual(set(sample['observation']['tasks']), set(self.aws.tasks))

    def test_deletion_without_terminal_seal_stays_blocked(self):
        self.protocol.drain_until_quiet();self.gone()
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('data')
        self.assertIsNotNone(self.journal.read('terminal-invalid'))

    def test_live_cluster_contradicts_terminal_handoff_permanently(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete()
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('data')
        self.gone()
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('global')
        self.assert_held()

    def test_absence_read_error_retains_invalid_evidence(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete();self.aws.fail = 'read'
        with self.assertRaises(OSError):self.protocol.require_terminal_handoff('data')
        self.assertIsNotNone(self.journal.read('terminal-invalid'))

    def test_terminal_seal_never_outlives_original_intent(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete();self.gone();self.now += 301
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('global')

    def test_terminal_seal_generation_drift_rejected(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete();self.gone()
        head = dict(self.owner.value,generation=99)
        self.s3.replace_fixture(self.store.bucket,self.store.key,e.canonical(head))
        with self.assertRaises(e.CoordinationError):self.protocol.require_terminal_handoff('data')

    def test_corrupt_sealed_sample_is_not_terminal(self):
        self.protocol.drain_until_quiet();seal=self.protocol.seal_before_cluster_delete();self.gone()
        key='sample-'+str(seal['sample']['sample']);sample=self.journal.read(key)
        next(iter(sample['observation']['tasks'].values()))['lastStatus']='RUNNING'
        self.s3.replace_fixture(self.journal.bucket,self.journal.key(key),c.canonical(sample))
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('global')

    def test_controller_closure_must_remain_valid_after_delete(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete();self.gone();self.boundary.closed=False
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('data')

    def test_foreign_cluster_missing_is_not_exact_absence(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete()
        self.aws.describe_clusters=lambda **kw:dict(clusters=[],failures=[{'arn':'prod','reason':'MISSING'}])
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('global')

    def test_empty_cluster_response_is_not_absence(self):
        self.protocol.drain_until_quiet();self.protocol.seal_before_cluster_delete()
        self.aws.describe_clusters=lambda **kw:dict(clusters=[],failures=[])
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('data')

    def test_repeated_predelete_boundary_keeps_identical_seal(self):
        self.protocol.drain_until_quiet();first=self.protocol.require_predelete_seal()
        second=self.protocol.require_predelete_seal();self.assertEqual(first,second)
        self.assertEqual(len(self.aws.calls),2)

    def test_failed_invalid_marker_write_does_not_revive_terminal_handoff(self):
        self.protocol.drain_until_quiet();self.protocol.require_predelete_seal()
        self.s3.write_fault=('before',self.journal.key('terminal-invalid'))
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('data')
        self.gone();self.s3.write_fault=None
        self.assertIsNone(self.journal.read('terminal-invalid'))
        with self.assertRaises(ValueError):self.protocol.require_terminal_handoff('global')
        self.assert_held()

    def test_failed_invalid_marker_write_does_not_revive_predelete_seal(self):
        self.protocol.drain_until_quiet();self.protocol.require_predelete_seal()
        self.s3.write_fault=('before',self.journal.key('terminal-invalid'))
        task=next(iter(self.aws.tasks.values()));task['lastStatus']='RUNNING'
        with self.assertRaises(ValueError):self.protocol.require_predelete_seal()
        task['lastStatus']='STOPPED';self.s3.write_fault=None
        with self.assertRaises(ValueError):self.protocol.require_predelete_seal()
        self.assert_held()

    def test_contradiction_invalidates_already_sealed_predelete_evidence(self):
        self.protocol.drain_until_quiet();self.protocol.require_predelete_seal()
        task=next(iter(self.aws.tasks.values()));task['lastStatus']='RUNNING'
        with self.assertRaises(ValueError):self.protocol.require_predelete_seal()
        task['lastStatus']='STOPPED'
        with self.assertRaises(ValueError):self.protocol.require_predelete_seal()
        self.assertIsNotNone(self.journal.read('terminal-invalid'))

    def test_nonterminal_task_blocks_predelete_seal(self):
        self.protocol.drain_until_quiet()
        next(iter(self.aws.tasks.values())).update(lastStatus='STOPPING')
        with self.assertRaises(ValueError):self.protocol.require_predelete_seal()
        self.assertIsNone(self.journal.read('terminal-seal'))

    def test_installed_handoff_does_not_gain_closure_from_new_protocol(self):
        self.protocol=self.make(q.ProtectedBoundary())
        with self.assertRaises(q.Blocked):self.protocol.drain_until_quiet()
        self.assertEqual(self.aws.calls,[])


def fixture():
    binding,p,_,_=cf.prepared('edge')
    requests=[]
    for layer in df.down.DOWN:
        _,candidate,value,_=cf.prepared(layer)
        p['layers'][layer]=candidate['layers'][layer]
        value['operation_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,'e15g/'+layer))
        requests.append(value)
        p['operation_approvals'][value['operation_id']]=dict(request_sha256=c.digest(c.canonical(value)),environment='dev')
        p['teardown_approvals'][value['operation_id']]=dict(revision=value['revision'],layer=layer,environment='dev')
    selected=df.down.scope(requests[3],p)
    consent=dict(schema='E15B_DEV_CONSENT_V1',scope_sha256=selected['scope_sha256'],issued_at=900,expires_at=2000,
                 **df.down.acknowledgements(selected))
    p['teardown_approvals']['dev-sql-loss/'+requests[3]['operation_id']]=consent
    return binding,p,requests


class WholeOperation(unittest.TestCase):
    def setUp(self):
        self.binding,self.p,self.requests=fixture();self.s3=hf.SDK()
        self.store=e.Store(self.s3,f'e1-wp4-dev-{ACCOUNT}-{REGION}','dev');self.store.initialize()
        self.authority=e.Authority(self.store,self.binding,self.requests[0]['operation_id'],self.requests[0],layer='edge')
        self.records=runtime.Records(self.s3,f'e1-lifecycle-dev-{ACCOUNT}-{REGION}','operations/'+self.binding+'/')
        self.operation=o.Operation(self.requests,self.p,self.authority,self.records,lambda:1000)

    def start(self):
        self.authority.acquire();self.operation.owner=copy.deepcopy(self.authority.value);self.operation.running=True
        self.operation.retain(self.operation.key,dict(manifest=self.operation.manifest,owner=self.operation.owner,state='UNKNOWN'))

    def test_all_five_children_retain_one_original_e2_context(self):
        self.start();owner=copy.deepcopy(self.authority.value)
        for index,value in enumerate(self.requests):
            self.operation.index=index
            self.assertEqual(self.operation.owns_request(value,self.p,self.authority),owner)
            self.assertEqual(self.store.read()[0],owner)
            self.operation.retain(self.operation.key + '/stages/' + value['layer'] + '/verified',
                dict(owner=owner,request_sha256=c.digest(c.canonical(value)),state='VERIFIED',result=dict(state='SUCCESS')))
        self.assertEqual(owner['request_sha256'],c.digest(c.canonical(self.requests[0])))

    def test_wrong_stage_request_cannot_borrow_current_owner(self):
        self.start()
        with self.assertRaises(ValueError):self.operation.owns_request(self.requests[1],self.p,self.authority)

    def test_wrong_account_or_prod_context_rejected(self):
        for name,value in [('environment','prod'),('account','222222222222')]:
            p=copy.deepcopy(self.p);p[name]=value
            with self.assertRaises(ValueError):o.Operation(self.requests,p,self.authority,self.records,lambda:1000)

    def test_shared_or_secrets_layer_never_in_whole_down(self):
        for name in ('shared','secrets'):
            values=copy.deepcopy(self.requests);values[4]['layer']=name
            with self.assertRaises(ValueError):o.Operation(values,self.p,self.authority,self.records,lambda:1000)

    def test_wrong_order_rejected_before_admission(self):
        values=list(reversed(self.requests))
        with self.assertRaises(ValueError):o.Operation(values,self.p,self.authority,self.records,lambda:1000)
        self.assertEqual(self.store.read()[0]['state'],'RELEASED')

    def test_missing_stage_approval_rejected_before_admission(self):
        p=copy.deepcopy(self.p);p['operation_approvals'].pop(self.requests[2]['operation_id'])
        with self.assertRaises(ValueError):o.Operation(self.requests,p,self.authority,self.records,lambda:1000)

    def test_sql_loss_ack_separate_and_required_before_any_stage(self):
        p=copy.deepcopy(self.p)
        p['teardown_approvals']['dev-sql-loss/'+self.requests[3]['operation_id']]['sql_loss_ack']='DESTROY'
        with self.assertRaises(ValueError):o.Operation(self.requests,p,self.authority,self.records,lambda:1000)

    def test_competing_wp4_delivery_and_wp5_lifecycle_cannot_acquire(self):
        self.start()
        for binding,layer in [('normal-delivery/deploy-dev',None),('environment-lifecycle/infra-dev','global')]:
            peer=e.Authority(self.store,binding,df.NEXT,dict(peer=True),layer=layer)
            result=e.execute(peer,lambda _:self.fail('competing mutation entered'),state_key='state')
            self.assertEqual(result['state'],'UNKNOWN')
        self.assertEqual(self.store.read()[0],self.operation.owner)

    def test_nat_under_original_owner_diagnoses_but_does_not_enable_down(self):
        self.start();config=test_nat.AWS().config
        nq=nat.Quiescence(self.authority,self.requests[-1],self.p,config,self.records,
            nf.Observations(config),now=lambda:1000,operation=self.operation)
        with self.assertRaises(ValueError):nq.require_network_teardown()
        self.assertEqual(nq.owner,self.operation.owner)
        self.assertEqual(self.records.read(nq.key)['state'],'UNKNOWN')

    def test_missing_installed_nat_adapter_no_stage_dispatch_and_durable_hold(self):
        def missing(context):
            return runtime.quiescence.InstalledNAT().protocol(self.authority,self.requests[-1],self.p,self.records,lambda:1000)
        result=self.operation.execute(None,lambda *args:self.fail('stage dispatched'),missing)
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(result['completed_layers'],[])
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')
        self.assertIsNotNone(self.records.read(self.operation.key+'/blocked'))

    def test_repeated_uuid_does_not_resume_or_replace_owner(self):
        first=self.operation.execute(None,None,lambda context:(_ for _ in ()).throw(OSError()))
        second=self.operation.execute(None,None,lambda context:self.fail('repeat'))
        self.assertEqual(first['state'],second['state']);self.assertEqual(self.store.read()[0]['generation'],1)

    def test_interrupted_owner_and_e4_uncertain_remain_held(self):
        self.start();self.authority.finish(False,'UNCERTAIN')
        peer=e.Authority(self.store,self.binding,self.requests[0]['operation_id'],self.requests[0],layer='edge')
        op=o.Operation(self.requests,self.p,peer,self.records,lambda:1000)
        result=op.execute(None,None,None)
        self.assertEqual(result['state'],'UNKNOWN');self.assertEqual(self.store.read()[0],self.operation.owner)

    def test_manifest_corruption_blocks_child_authority(self):
        self.start();self.operation.manifest['order'].reverse()
        with self.assertRaises(ValueError):self.operation.owns_request(self.requests[0],self.p,self.authority)

    def test_original_generation_drift_never_transfers_child_authority(self):
        self.start();head=dict(self.authority.value,generation=22)
        self.s3.replace_fixture(self.store.bucket,self.store.key,e.canonical(head))
        with self.assertRaises(e.CoordinationError):self.operation.owns_request(self.requests[0],self.p,self.authority)

    def test_stage_index_alone_cannot_skip_prior_durable_verification(self):
        self.start();self.operation.index=1
        with self.assertRaises(ValueError):self.operation.owns_request(self.requests[1],self.p,self.authority)

    def test_reusing_an_old_child_uuid_cannot_skip_destruction(self):
        self.records.create(self.requests[2]['operation_id'],dict(state='SUCCESS'))
        with self.assertRaises(ValueError):self.operation.execute(None,None,None)
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')

    def test_old_single_layer_success_never_becomes_whole_success(self):
        self.authority.acquire();self.authority.finish(True,'SUCCESS')
        with self.assertRaises(ValueError):self.operation.execute(None,None,None)

    def test_uninstalled_residual_port_is_fail_closed(self):
        with self.assertRaises(q.Blocked):o.Residual().observe(self.operation.manifest,dict())

    def test_installed_runtime_missing_identity_never_dispatches_terraform(self):
        with patch.object(runtime.subprocess,'run',side_effect=AssertionError('Terraform dispatched')):
            with self.assertRaises(Exception):runtime.execute_down(self.requests,dict(binding=self.binding,
                account=ACCOUNT,region=REGION,package={}),dict(s3=self.s3))


class ResidualEvidence(unittest.TestCase):
    def setUp(self):
        self.manifest=dict(residual_keys=['dev-runtime','retained:backend'],retained_keys=['retained:backend'])
        self.owner=dict(generation=1)
        self.value=dict(operation_sha256=c.digest(c.canonical(self.manifest)),owner=self.owner,complete=True,
            resources=[dict(key='dev-runtime',disposition='ABSENT',evidence_sha256='a'*64),
                dict(key='retained:backend',disposition='RETAINED',evidence_sha256='b'*64)])

    def test_complete_absence_retains_backend(self):
        self.assertEqual(o.residual_result(self.value,self.manifest,self.owner),self.value)

    def test_present_unknown_unqueried_failed_partial_cannot_finish_down(self):
        for disposition in ('PRESENT','UNKNOWN_OWNERSHIP','NOT_QUERIED','READBACK_FAILED','PARTIAL'):
            value=copy.deepcopy(self.value);value['resources'][0]['disposition']=disposition
            with self.assertRaises(ValueError):o.residual_result(value,self.manifest,self.owner)

    def test_missing_material_inventory_is_not_success(self):
        value=copy.deepcopy(self.value);value['resources'].pop(0)
        with self.assertRaises(ValueError):o.residual_result(value,self.manifest,self.owner)

    def test_retained_backend_absence_is_a_failure(self):
        value=copy.deepcopy(self.value);value['resources'][1]['disposition']='ABSENT'
        with self.assertRaises(ValueError):o.residual_result(value,self.manifest,self.owner)

    def test_unexpected_discovered_dev_resource_blocks_success(self):
        value=copy.deepcopy(self.value);value['resources'].append(dict(key='orphan-eni',disposition='PRESENT',evidence_sha256='c'*64))
        with self.assertRaises(ValueError):o.residual_result(value,self.manifest,self.owner)

    def test_inventory_from_other_operation_never_finishes(self):
        value=copy.deepcopy(self.value);value['operation_sha256']='c'*64
        with self.assertRaises(ValueError):o.residual_result(value,self.manifest,self.owner)


class SourceBoundary(unittest.TestCase):
    def test_no_authority_activation_or_e2_primitive_change(self):
        import json
        doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        self.assertFalse(doc['wp5']['installations']);self.assertFalse(doc['wp5']['active_contracts'])
        self.assertFalse(doc['wp4d']['installations'])

    def test_local_operator_still_has_no_authority_bypass(self):
        source=(ROOT/'scripts/ephemeral_lab.py').read_text()
        self.assertIn('down-execute',source)
        self.assertNotIn('execute_down(',source)
        self.assertNotIn('terraform destroy -auto-approve',(ROOT/'scripts/lifecycle/operational.py').read_text())


class ChildApprovalBoundary(unittest.TestCase):
    """Exact approval consumption only; no positive whole-DOWN or installed proof."""
    def setUp(self):
        import tempfile
        from scripts.lifecycle import exact_destroy as x
        from test_exact_destroy import TrustedFixture
        from test_lifecycle import quiescent
        self.binding,self.p,self.requests=fixture();self.sdk=hf.SDK()
        self.store=e.Store(self.sdk,f'e1-wp4-dev-{ACCOUNT}-{REGION}','dev');self.store.initialize()
        self.owner=e.Authority(self.store,self.binding,self.requests[0]['operation_id'],self.requests[0],layer='edge')
        self.records=runtime.Records(self.sdk,f'e1-lifecycle-dev-{ACCOUNT}-{REGION}','operations/'+self.binding+'/')
        self.operation=o.Operation(self.requests,self.p,self.owner,self.records,lambda:1000)
        self.owner.acquire();self.operation.owner=copy.deepcopy(self.owner.value);self.operation.running=True
        self.operation.retain(self.operation.key,dict(manifest=self.operation.manifest,owner=self.operation.owner,state='UNKNOWN'))
        # Synthetic predecessor records isolate the current child approval seam;
        # these fixtures do not run/claim a successful five-stage teardown.
        for value in self.requests[:2]:
            self.operation.retain(self.operation.key+'/stages/'+value['layer']+'/verified',
                dict(owner=self.owner.value,request_sha256=c.digest(c.canonical(value)),state='VERIFIED',result=dict(state='SUCCESS')))
        self.operation.index=2;self.value=self.requests[2]
        temporary=tempfile.TemporaryDirectory(prefix='e15g-child-approval-');self.addCleanup(temporary.cleanup)
        directory=Path(temporary.name)
        self.engine=runtime.Terraform(directory,None,self.p,self.owner,request=self.value)
        self.engine.down_operation=self.operation;self.engine.directory=directory
        self.engine.layer=self.p['layers']['platform'];self.engine.reference=self.p['installations'][self.value['revision']]
        self.engine.environment=dict(TF_WORKSPACE='default');(directory/'wp5.auto.tfvars.json').write_bytes(b'{}')
        self.engine.observe=lambda env:quiescent(env)
        self.plan=cf.prepared('platform')[3];self.binary=b'exact child binary - synthetic protected channel'
        self.engine.call=lambda args:c.canonical(self.plan) if args[0]=='show' else self.fail('unexpected command')
        seal=dict(binary_sha256=c.digest(self.binary),json_sha256=c.digest(c.canonical(self.plan)),context_sha256=self.engine.destroy_context())
        self.channel=TrustedFixture(self.value,self.p,self.binary,self.plan,seal)
        selected=df.down.scope(self.value,self.p)
        confirm=dict(schema='E15B_DEV_CONSENT_V1',scope_sha256=selected['scope_sha256'],issued_at=900,expires_at=1100,
                     **df.down.acknowledgements(selected))
        x.issue(self.channel,self.value,self.p,confirm,900,1050,1000)
        self.journal=x.DecisionJournal(self.sdk,selected)
        self.execution=x.Execution(self.channel,self.journal,lambda:1000);self.engine.exact_destroy=self.execution
        self.engine.plan(True)

    def test_exact_child_binary_claim_uses_original_edge_owner(self):
        self.execution.before_dispatch(self.engine)
        self.assertEqual(self.journal.read('decision')['generation'],self.owner.value['generation'])
        self.assertEqual(self.journal.read('decision')['request_sha256'],c.digest(c.canonical(self.value)))
        self.assertEqual(self.journal.read('attempt')['binary_sha256'],c.digest(self.binary))
        self.assertEqual(self.store.read()[0]['operation'],self.requests[0]['operation_id'])
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')

    def test_child_generation_mismatch_fails_before_claim(self):
        self.channel.approval['expected_generation']=99
        self.channel.ref['sha256']=c.digest(c.canonical(self.channel.approval))
        with self.assertRaises(ValueError):self.execution.before_dispatch(self.engine)
        self.assertIsNone(self.journal.read('decision'))

    def test_quietness_missing_keeps_valid_child_approval_unconsumed(self):
        self.channel.closed=False
        with self.assertRaises(ValueError):self.execution.before_dispatch(self.engine)
        self.assertIsNone(self.journal.read('decision'));self.assertEqual(self.store.read()[0]['state'],'ACTIVE')

    def test_abstract_approval_channel_cannot_install_runtime_quiescence(self):
        with self.assertRaises(ValueError):self.engine.require_combined_quiescence('pre-dispatch')

    def test_child_cannot_reuse_consumed_exact_plan(self):
        self.execution.before_dispatch(self.engine)
        with self.assertRaises(Exception):self.execution.before_dispatch(self.engine)
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')
