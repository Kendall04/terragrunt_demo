"""Actual E2/WP4C/SDK boundaries and explicit remote-finality counterexamples."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from scripts import environment_mutation as e
from scripts.lifecycle.runtime import Records
from scripts.lifecycle import contract as c
from scripts.nat import quiescence as q, reliability
from scripts.recovery.nat import Nat as Controller
from scripts.wp4d.aws_runtime import Nat as Transport
from scripts.wp4d.adapters import Objects
from scripts.wp4d.nat_resolver import Resolver
from scripts.tests.nat import test_nat
from scripts.tests.mutation.test_mutation import S3
from scripts.tests.dev_down.test_dev_down import fixture

ROOT = Path(__file__).resolve().parents[3]
OP = test_nat.UUID
OTHER = '22222222-2222-4222-8222-222222222222'


class Observations(q.Observation):
    def __init__(self, config):
        account, region = config['account'], config['region']
        self.value = dict(environment='dev', account=account, region=region, observed_at=1000,
            rule=dict(arn=f'arn:aws:events:{region}:{account}:rule/e1-wp4-dev-nat-launch', enabled=False),
            functions={a: dict(qualified_arn=f'arn:aws:lambda:{region}:{account}:function:e1-nat-recovery-nat-dev-{a}:1',
                              reserved_concurrency=0) for a in q.ACTIONS},
            queues={f'arn:aws:sqs:{region}:{account}:e1-wp4-dev-nat-{kind}-failed':
                    dict(visible=0, not_visible=0, delayed=0) for kind in ('delivery', 'execution')},
            slots={s['asg']: dict(**{k:s[k] for k in ('vpc','subnet','az','eip','route_table')},
                    min=0, max=1, desired=0, instances=[], activities=[], launch_suspended=True,
                    association_eni=None, default_route_eni=None, route_state='absent') for s in config['nat_slots']},
            effects=[])
        self.error = False
        self.hook = None
    def observe(self, scope, members, deadline):
        if self.error: raise OSError('read unavailable')
        if self.hook: self.hook()
        return copy.deepcopy(self.value)


class Contract(unittest.TestCase):
    def setUp(self):
        self.aws = test_nat.AWS()
        self.s3 = S3()
        self.config = self.aws.config
        self.store = e.Store(self.s3, self.config['evidence_bucket'], 'dev')
        self.store.initialize()
        self.binding, self.protected, self.request, _ = fixture('global')
        self.protected['layers']['global']['membership'] = {str(index): identity for index,identity in enumerate(
            sorted({s[k] for s in self.config['nat_slots'] for k in ('vpc','subnet','asg','eip','route_table')}))}
        self.records = Records(self.s3, self.protected['layers']['global']['backend']['bucket'],
                               'operations/' + self.binding + '/')
        self.observation = Observations(self.config)

    def owner(self, operation=OP):
        request = dict(self.request, operation_id=operation)
        owner = e.Authority(self.store, self.binding, operation, request, layer='global')
        owner.acquire()
        return owner

    def protocol(self, owner=None, config=None, records=None, observation=None):
        return q.Quiescence(owner or self.owner(), self.request, self.protected, config or self.config,
                            records or self.records, observation or self.observation, now=lambda:1000)

    def controller(self, action='assign_eip', operation=OP):
        self.config['binding'] = 'nat-recovery/nat-dev/' + action
        records = Objects(test_nat.S3(), self.config['evidence_bucket'], 'recovery/')
        runtime = Transport(self.aws, self.aws, self.aws, records,
                            Resolver('dev', self.aws.slots), action, operation, self.aws.slots[0]['asg'], 'i-00000001')
        controller = Controller('dev', action, records, runtime)
        wrapped = q.FencedEC2(self.aws, self.store, self.config, action, controller.context)
        runtime.ec2 = wrapped
        return controller, runtime, wrapped

    def blocked(self, report):
        self.assertEqual(report['state'], 'UNKNOWN')
        self.assertFalse(report['execution_authorized'])
        self.assertFalse(report['aws_verified'])
        self.assertTrue(report['blockers'])

    def test_exact_dev_operation_owner_generation_and_durable_unknown(self):
        owner = self.owner(); protocol = self.protocol(owner)
        report = protocol.inspect(); self.blocked(report)
        self.assertEqual(report['scope']['layer'], 'global')
        self.assertEqual(report['e2'], owner.value)
        self.assertEqual(self.records.read(protocol.key)['state'], 'UNKNOWN')
        self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')

    def test_prod_and_shared_scope_rejected(self):
        for env,layer in (('prod','global'), ('dev','shared'), ('dev','secrets')):
            _,p,r,_ = fixture(layer,env)
            with self.subTest(env=env,layer=layer), self.assertRaises(ValueError):
                q.Quiescence(self.owner(),r,p,self.config,self.records,self.observation)
            # Each case has independent ownership; no force release.
            self.setUp()

    def test_wrong_nat_slot_membership_rejected(self):
        for key in ('environment','account','region','subnet','eip','route_table','asg','az'):
            config = copy.deepcopy(self.config)
            config['nat_slots'][1][key] = config['nat_slots'][0][key] if key not in ('environment','account','region') else 'foreign'
            with self.subTest(key=key), self.assertRaises((ValueError,KeyError)): q.slots(config)

    def test_dev_prod_control_resource_sharing_rejected(self):
        config = copy.deepcopy(self.config); config['nat_slots'][0]['spec']['role'] = 'arn:aws:iam::123456789012:role/demo-prod-nat-role'
        with self.assertRaises(ValueError): self.protocol(config=config)

    def test_current_released_generation_permits_existing_recovery(self):
        for action in q.ACTIONS:
            self.setUp();controller,_,_ = self.controller(action)
            self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
            self.assertEqual([name for name,_ in self.aws.calls],[action])

    def test_wrong_generation_denies_stale_controller(self):
        controller,_,_ = self.controller(); owner=self.owner(); owner.finish(status='FAILURE')
        self.assertIn(controller.run(OP,b'{}\n')['status'],('FAILURE','UNCERTAIN'))
        self.assertEqual(self.aws.calls,[])

    def test_active_owner_inhibits_new_controller_admission(self):
        self.owner()
        with self.assertRaises(ValueError): self.controller()
        self.assertEqual(self.aws.calls,[])

    def test_stale_controller_attempt_denied_at_actual_ec2_boundary(self):
        controller,runtime,wrapped=self.controller();domain=controller.context()
        self.owner()
        with self.assertRaises(ValueError): wrapped.associate_address(**controller.actions(domain)['assign_eip'])
        self.assertEqual(self.aws.calls,[])

    def race(self, action, before_dispatch=False, lost_response=False):
        controller,_,wrapped=self.controller(action)
        entered,release=threading.Event(),threading.Event();results=[];errors=[]
        method=q.VERBS[action][0];original=getattr(self.aws,method)
        def paused(**kw):
            entered.set()
            if not release.wait(5): raise AssertionError('test barrier timeout')
            original(**kw)
            if lost_response: raise TimeoutError('lost response')
        if before_dispatch:
            original_check=wrapped.check;count=[0]
            def checked():
                original_check();count[0]+=1
                if count[0]==2:
                    entered.set()
                    if not release.wait(5): raise AssertionError('test barrier timeout')
            wrapped.check=checked
        else:
            setattr(self.aws,method,paused)
            if action=='change_rt': self.aws.replace_route=paused
        def worker():
            try: results.append(controller.run(OP,b'{}\n'))
            except BaseException as err: errors.append(err)
        thread=threading.Thread(target=worker);thread.start()
        try:
            self.assertTrue(entered.wait(5))
            protocol=self.protocol();report=protocol.inspect();self.blocked(report)
            self.assertIn('EXECUTOR_AND_DISPATCHED_EFFECT_SETTLEMENT_UNPROVED',report['blockers'])
            release.set();thread.join(5);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertEqual(len(self.aws.calls),1)
            self.blocked(protocol.inspect())
            return controller,results[0]
        finally: release.set();thread.join(5)

    def test_authorized_before_quiescence_last_check_does_not_revoke_dispatch(self): self.race('assign_eip',before_dispatch=True)
    def test_dispatched_eip_completes_after_quiescence(self): self.race('assign_eip')
    def test_dispatched_route_completes_after_quiescence(self): self.race('change_rt')
    def test_dispatched_sdc_completes_after_quiescence(self): self.race('disable_sdc')

    def test_lost_lambda_response_preserves_uncertain_and_never_resends(self):
        controller,result=self.race('assign_eip',lost_response=True)
        self.assertEqual(result['status'],'UNCERTAIN')
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN')
        self.assertEqual(len(self.aws.calls),1)

    def test_eip_applied_but_ack_journal_write_failed_remains_uncertain(self):
        controller,runtime,_=self.controller();original=runtime.records.create
        def fail(key,raw):
            if key.endswith('/ack'): raise OSError('ACK journal unavailable')
            return original(key,raw)
        runtime.records.create=fail
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN')
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN')
        self.assertEqual(len(self.aws.calls),1); self.blocked(self.protocol().inspect())

    def test_already_delivered_event_blocked_when_owner_begins(self):
        controller,_,_=self.controller(); reliability.launch_event(self.aws.event,self.config)
        self.protocol().request()
        self.assertIn(controller.run(OP,b'{}\n')['status'],('FAILURE','UNCERTAIN'));self.assertEqual(self.aws.calls,[])

    def test_late_lambda_retry_cannot_rearm_mutation(self):
        controller,_,_=self.controller(); self.protocol().request()
        for _ in range(2): self.assertIn(controller.run(OP,b'{}\n')['status'],('FAILURE','UNCERTAIN'))
        self.assertEqual(self.aws.calls,[])

    def test_duplicate_event_reconciles_existing_attempt_without_resend(self):
        controller,_,_=self.controller()
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
        self.protocol().request()
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
        self.assertEqual(len(self.aws.calls),1) # narrow historical effect, never quiet proof

    def test_wrong_environment_event_and_plausible_foreign_instance_reject(self):
        for key in ('account','region'):
            event=copy.deepcopy(self.aws.event);event[key]='foreign'
            with self.assertRaises(ValueError): reliability.launch_event(event,self.config)
        controller,_,_=self.controller();self.aws.foreign='VpcId'
        self.assertIn(controller.run(OP,b'{}\n')['status'],('FAILURE','UNCERTAIN'));self.assertEqual(self.aws.calls,[])

    def diagnostic(self, field, value):
        slot=next(iter(self.observation.value['slots'].values()));slot[field]=value
        report=self.protocol().inspect();self.blocked(report);return report

    def test_asg_replacement_after_shutdown_request_is_unsettled(self):
        report=self.diagnostic('activities',[{'id':'replacement','status':'InProgress'}])
        self.assertIn('ASG_MEMBERS_OR_ACTIVITY_REMAIN',report['blockers'])
    def test_desired_zero_with_instance_present_not_quiet(self):
        report=self.diagnostic('instances',[{'instance':'i-00000001','eni':'eni-00000001','state':'InService','source_dest_check':False}])
        self.assertIn('ASG_MEMBERS_OR_ACTIVITY_REMAIN',report['blockers'])
    def test_termination_requested_but_not_observed_remains_blocked(self):
        self.diagnostic('instances',[{'instance':'i-00000001','eni':'eni-00000001','state':'Terminating','source_dest_check':False}])
    def test_asg_launch_not_suspended_blocks(self):
        self.assertIn('ASG_NOT_INHIBITED',self.diagnostic('launch_suspended',False)['blockers'])
    def test_asg_minimum_one_blocks_even_desired_zero(self):
        self.assertIn('ASG_NOT_INHIBITED',self.diagnostic('min',1)['blockers'])

    def test_dlq_pending_visible_invisible_delayed_preserved(self):
        for field in ('visible','not_visible','delayed'):
            self.setUp(); next(iter(self.observation.value['queues'].values()))[field]=1
            report=self.protocol().inspect();self.blocked(report)
            self.assertIn('DLQ_PENDING_EVIDENCE_REQUIRES_ADMIN_DIAGNOSIS',report['blockers'])
            self.assertEqual(next(iter(report['observed']['queues'].values()))[field],1)

    def test_missing_effect_settlement_cannot_be_invented_from_empty_inventory(self):
        report=self.protocol().inspect();self.blocked(report)
        self.assertEqual(report['settlement'],'UNPROVED')
    def test_valid_inhibition_but_prior_call_unsettled(self):
        self.observation.value['effects']=[dict(token='dev/recovery/assign_eip/'+OP+'/assign_eip',action='assign_eip',state='UNSETTLED')]
        self.assertIn('PRIOR_EFFECT_UNSETTLED',self.protocol().inspect()['blockers'])
    def test_applied_or_absent_effect_is_not_global_finality(self):
        for state in ('APPLIED','ABSENT','UNKNOWN'):
            self.setUp();self.observation.value['effects']=[dict(token='dev/recovery/change_rt/'+OP+'/change_rt',action='change_rt',state=state)]
            self.blocked(self.protocol().inspect())
    def test_readback_unavailable(self):
        self.observation.error=True;report=self.protocol().inspect();self.blocked(report);self.assertIsNone(report['observed'])
    def test_readback_stale_or_future_rejected(self):
        for stamp in (999,1001):
            self.setUp();self.observation.value['observed_at']=stamp
            self.assertIsNone(self.protocol().inspect()['observed'])
    def test_contradictory_route_eip_readback_blocks(self):
        self.diagnostic('association_eni','eni-foreign'); self.setUp()
        self.diagnostic('default_route_eni','eni-foreign');self.setUp()
        self.diagnostic('route_state','blackhole')
    def test_wrong_resource_readback_rejected(self):
        for field in ('eip','route_table','vpc','subnet','az'):
            self.setUp();report=self.diagnostic(field,'foreign');self.assertIsNone(report['observed'])
    def test_repeated_request_same_owner_retains_unknown(self):
        protocol=self.protocol();first=protocol.request()
        self.assertEqual(protocol.request(),first);self.assertEqual(protocol.inspect(),protocol.inspect())
    def test_second_teardown_cannot_acquire(self):
        protocol=self.protocol();protocol.request()
        with self.assertRaises(e.CoordinationError): self.owner(OTHER)
        self.blocked(protocol.inspect())
    def test_two_controller_duties_do_not_share_effect_settlement(self):
        first,_,_=self.controller('assign_eip');second,_,_=self.controller('change_rt')
        self.assertEqual(first.run(OP,b'{}\n')['status'],'SUCCESS')
        self.protocol().request();self.assertEqual(second.run(OTHER,b'{}\n')['status'],'UNCERTAIN')
        self.assertEqual([a for a,_ in self.aws.calls],['assign_eip'])
    def test_e2r_interrupted_owner_blocks_protocol_without_takeover(self):
        old=e.Authority(self.store,'normal-delivery/deploy-dev',OTHER,{});old.acquire()
        with self.assertRaises(e.CoordinationError): self.protocol()
        self.assertEqual(self.store.read()[0]['owner'],old.owner)
    def test_e4_uncertain_owner_cannot_be_released_for_nat(self):
        old=e.Authority(self.store,'normal-delivery/deploy-dev',OTHER,{});old.acquire()
        old.call(lambda:None);old.finish(status='UNCERTAIN')
        with self.assertRaises(e.CoordinationError): self.protocol()
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')
    def test_quiet_hold_released_during_inspection_invalidates_diagnostics(self):
        owner=self.owner();protocol=self.protocol(owner)
        self.observation.hook=lambda:owner.finish(status='FAILURE')
        report=protocol.inspect();self.blocked(report);self.assertIsNone(report['observed'])
        with self.assertRaises(e.CoordinationError): protocol.request()
    def test_missing_protected_evidence_and_durable_write_failure_reject(self):
        protocol=self.protocol();self.s3.drop_write=True
        with self.assertRaises(ValueError):protocol.request()
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')
    def test_missing_e2_permission_fail_closed(self):
        self.s3.fail_read=True
        with self.assertRaises(OSError): self.controller()
        self.assertEqual(self.aws.calls,[])
    def test_caller_json_or_synthetic_live_claim_never_authorizes(self):
        with self.assertRaises(ValueError): self.protocol(observation={'ready':True})
        self.setUp();report=self.protocol().inspect();self.blocked(report)
        self.assertFalse(report['aws_verified'])
    def test_unknown_ec2_methods_and_cross_duty_mutations_reject(self):
        _,_,wrapped=self.controller()
        for name in ('terminate_instances','replace_route','modify_instance_attribute','run_instances'):
            with self.assertRaises(ValueError): getattr(wrapped,name)
    def test_wrong_ec2_request_never_dispatches(self):
        _,_,wrapped=self.controller()
        with self.assertRaises(ValueError): wrapped.associate_address(AllocationId='eipalloc-foreign',NetworkInterfaceId='eni-00000001',AllowReassociation=True)
        self.assertEqual(self.aws.calls,[])
    def test_no_iam_expansion_installation_runtime_or_terraform_bypass(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        for kind in ('wp4d','wp5'):
            for field in ('installations','runtime_approvals','environment_bindings'):self.assertEqual(authority[kind][field],{})
        self.assertNotIn('quiescence', (ROOT/'scripts/wp4d/runtime.py').read_text())
        # Combined integration now wires WP5, while installation still denies.
        from scripts.lifecycle.runtime import Terraform
        engine = Terraform(ROOT, None, dict(environment='dev'))
        with self.assertRaisesRegex(ValueError, 'concrete administrative handoff'), patch('scripts.lifecycle.runtime.subprocess.run') as process:
            engine.require_combined_quiescence('pre-dispatch')
        process.assert_not_called()
        self.assertIn('DOWN/EXECUTE unavailable', (ROOT/'scripts/ephemeral_lab.py').read_text())

    def test_missing_wp5_nat_membership_blocks(self):
        self.protected['layers']['global']['membership'] = {}
        with self.assertRaises(ValueError): self.protocol()

    def test_current_original_e2_generation_required_for_request(self):
        owner=self.owner();protocol=self.protocol(owner)
        head,etag=self.store.read()
        # Deliberately corrupt only a memory double: never a supported takeover.
        self.store.exchange(dict(head,generation=head['generation']+1),etag)
        with self.assertRaises(e.CoordinationError):protocol.request()

    def test_network_teardown_seam_records_unknown_and_denies_even_quiet_readback(self):
        protocol=self.protocol()
        with self.assertRaisesRegex(ValueError,'E15F_NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_REQUIRED'):
            protocol.require_network_teardown()
        self.assertEqual(self.records.read(protocol.key)['state'],'UNKNOWN')
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')

    def test_unknown_outcome_write_not_proven_by_successful_ack(self):
        protocol=self.protocol();protocol.request()
        original=self.records.create
        self.records.create=lambda key,value:None
        with self.assertRaises(ValueError):protocol.inspect()
        self.records.create=original
        self.assertEqual(self.records.read(protocol.key)['state'],'UNKNOWN')

    def test_existing_iam_has_no_nat_e2_or_inhibition_mutation_permissions(self):
        from test_wp4d import policy, permits
        for action in q.ACTIONS:
            admitted=policy('nat-recovery/nat-dev/'+action)
            key=f'arn:aws:s3:::{self.store.bucket}/{self.store.key}'
            self.assertFalse(permits(admitted,'s3:GetObject',key))
            for verb in ('autoscaling:SuspendProcesses','lambda:PutFunctionConcurrency',
                         'events:DisableRule','sqs:PurgeQueue','ec2:TerminateInstances'):
                self.assertFalse(permits(admitted,verb,'*'))
    def test_two_concurrent_controllers_dispatch_before_hold_and_complete_late(self):
        first,_,_=self.controller('assign_eip');second,_,_=self.controller('change_rt')
        gate=threading.Barrier(3);release=threading.Event();results=[];errors=[]
        for name in ('associate_address','create_route'):
            original=getattr(self.aws,name)
            def paused(method=original,**kwargs):
                gate.wait(timeout=5)
                if not release.wait(5):raise AssertionError('test barrier timeout')
                return method(**kwargs)
            setattr(self.aws,name,paused)
        def run(controller):
            try:results.append(controller.run(OP,b'{}\n'))
            except BaseException as error:errors.append(error)
        threads=[threading.Thread(target=run,args=(controller,)) for controller in (first,second)]
        for thread in threads:thread.start()
        try:
            gate.wait(timeout=5);protocol=self.protocol();self.blocked(protocol.inspect())
            release.set()
            for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
            self.assertEqual(errors,[]);self.assertEqual(len(results),2)
            self.assertEqual({action for action,_ in self.aws.calls},{'assign_eip','change_rt'})
            self.blocked(protocol.inspect())
        finally:
            release.set()
            for thread in threads:thread.join(5)

    def test_changed_protected_nat_configuration_cannot_reuse_hold_evidence(self):
        owner=self.owner();protocol=self.protocol(owner);protocol.request()
        changed=copy.deepcopy(self.config);changed['bundle']={'sha256':'a'*64}
        replacement=self.protocol(owner,config=changed)
        with self.assertRaises(ValueError):replacement.request()

    def test_readback_returning_after_budget_cannot_be_accepted(self):
        protocol=self.protocol();clock=iter((1000,1030));protocol.now=lambda:next(clock)
        report=protocol.inspect();self.blocked(report);self.assertIsNone(report['observed'])