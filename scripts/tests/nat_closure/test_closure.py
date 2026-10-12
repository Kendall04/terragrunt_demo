"""E15-H real E13/SDK/WP5 boundaries. Synthetic storage never proves installation."""
import copy
import json
import threading
import unittest
from unittest.mock import patch
from scripts import environment_mutation as e
from scripts.lifecycle import contract as c
from scripts.nat import closure as n, native
from scripts.recovery.nat import Nat as Controller
from scripts.wp4d.aws_runtime import Nat as Transport
from scripts.wp4d.nat_resolver import Resolver
from scripts.wp4d.adapters import Objects
from scripts.tests.mutation.test_mutation import S3
import test_quiescence as baseline
from test_quiescence import OP, OTHER
from test_nat import AWS


class SDK(S3):
    def get_object(self, **args):
        return dict(super().get_object(**args), ServerSideEncryption='AES256')


class Identity(n.Authentication):
    def __init__(self, config):
        self.values = {action:dict(qualified_arn=f'arn:aws:lambda:{config["region"]}:{config["account"]}:function:e1-nat-recovery-nat-dev-{action}:1',
            package_sha256='a'*64, role_id='AROA'+'B'*17, invocation_id=OTHER) for action in n.ACTIONS}
    def executor(self, action):return copy.deepcopy(self.values[action])


class Case(unittest.TestCase):
    owner = baseline.Contract.owner
    protocol = baseline.Contract.protocol
    def setUp(self):
        baseline.Contract.setUp(self)
        self.s3 = SDK();self.store = e.Store(self.s3,self.config['evidence_bucket'],'dev');self.store.initialize()
        from scripts.lifecycle.runtime import Records
        self.records=Records(self.s3,self.protected['layers']['global']['backend']['bucket'],'operations/'+self.binding+'/')
        self.auth=Identity(self.config)
        self.versions={action:[{k:v for k,v in self.auth.values[action].items() if k!='invocation_id'}] for action in n.ACTIONS}
        self.head=n.Head(self.s3,self.config)
        self.s3.put_object(Bucket=self.head.bucket,Key=n.KEY,Body=c.canonical(n.initial(self.config,self.store.read()[0],OTHER)),IfNoneMatch='*')
        self.coordinator=n.Coordinator(self.head,self.store,self.config,self.auth,self.versions)
        self.action='assign_eip';self.token='dev/recovery/'+self.action+'/'+OP+'/'+self.action
        self.request_api=dict(AllocationId=self.aws.slots[0]['eip'],NetworkInterfaceId='eni-00000001',AllowReassociation=True)

    def admit(self):return self.coordinator.admit(self.action,self.token,self.request_api)
    def close(self):
        owner=self.owner();self.active=owner
        from scripts.lifecycle import dev_down
        self.selected=dev_down.scope(self.request,self.protected)
        return self.coordinator.close(owner,self.selected,'b'*64)
    def row(self):return self.head.read()[0]['permits'][self.token]
    def controller(self, action='assign_eip'):
        records=Objects(self.s3,self.config['evidence_bucket'],'recovery/')
        transport=Transport(self.aws,self.aws,self.aws,records,Resolver('dev',self.aws.slots),action,OP,self.aws.slots[0]['asg'],'i-00000001')
        cooperative=n.Cooperative(transport,self.coordinator,records)
        return Controller('dev',action,records,cooperative),transport,cooperative

    def test_01_exact_dev_scope(self):self.assertEqual(self.head.read()[0]['scope'],n.scope(self.config))
    def test_02_prod_and_shared_rejected(self):
        config=copy.deepcopy(self.config);config['environment']='prod'
        with self.assertRaises(ValueError):n.Head(self.s3,config)
        with self.assertRaises(ValueError):n.Coordinator(self.head,e.Store(self.s3,self.head.bucket,'dev','shared'),self.config,self.auth,self.versions)
    def test_03_original_owner_generation(self):
        value,_=self.close();self.assertEqual(value['closure']['owner'],self.active.value)
        self.assertEqual(self.store.read()[0],self.active.value)
    def test_04_admit_before_close_retained(self):
        self.admit();value,_=self.close();self.assertEqual(value['permits'][self.token]['state'],'ADMITTED')
    def test_05_admission_after_close_denied(self):
        self.close()
        with self.assertRaises(ValueError):self.admit()
    def test_06_atomic_admit_close_race(self):
        entered=threading.Event();resume=threading.Event();errors=[];original=self.head.exchange
        def paused(prior,ref,value):
            if value['state']=='OPEN':entered.set();self.assertTrue(resume.wait(5))
            return original(prior,ref,value)
        self.head.exchange=paused
        def worker():
            try:self.admit()
            except Exception as err:errors.append(err)
        thread=threading.Thread(target=worker);thread.start()
        try:
            self.assertTrue(entered.wait(5));self.close();resume.set();thread.join(5)
            self.assertFalse(thread.is_alive());self.assertEqual(len(errors),1)
            self.assertEqual(self.head.read()[0]['permits'],{})
        finally:resume.set();thread.join(5)
    def test_07_concurrent_admissions_cas_loser_denies(self):
        barrier=threading.Barrier(2);results=[];original=self.head.exchange
        def exchange(*args):barrier.wait(5);return original(*args)
        self.head.exchange=exchange
        def worker(operation):
            try:
                token=self.token.replace(OP,operation);self.coordinator.admit(self.action,token,self.request_api);results.append('ADMITTED')
            except ValueError:results.append('REJECTED')
        threads=[threading.Thread(target=worker,args=(operation,)) for operation in (OP,OTHER)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(5);self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(results),['ADMITTED','REJECTED']);self.assertEqual(len(self.head.read()[0]['permits']),1)
    def test_08_paused_before_admission_closed(self):
        original=self.auth.executor
        def paused(action):identity=original(action);self.close();return identity
        self.auth.executor=paused
        with self.assertRaises(ValueError):self.admit()
        self.assertEqual(self.aws.calls,[])
    def test_09_paused_after_admission_cancels(self):
        executor=self.admit();self.close()
        with self.assertRaises(ValueError):self.coordinator.transition(self.token,executor,'ADMITTED','DISPATCHED')
        self.coordinator.transition(self.token,executor,'ADMITTED','CANCELLED',dict(api='NOT_SENT'))
        self.assertEqual(self.row()['state'],'CANCELLED');self.assertEqual(self.aws.calls,[])
    def paused_dispatch(self,after=False,lost=False):
        controller,transport,cooperative=self.controller();entered=threading.Event();resume=threading.Event();results=[]
        original=self.aws.associate_address
        def dispatch(**args):
            if after:original(**args)
            entered.set();self.assertTrue(resume.wait(5))
            if not after:original(**args)
            if lost:raise TimeoutError('lost response')
            return {}
        self.aws.associate_address=dispatch
        if lost:transport.effect=lambda token,deadline:dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        thread=threading.Thread(target=lambda:results.append(controller.run(OP,b'{}\n')));thread.start()
        try:
            self.assertTrue(entered.wait(5));self.close();self.assertEqual(self.row()['state'],'DISPATCHED')
            self.assertEqual(self.coordinator.inspect(self.active,self.selected,'b'*64)['cooperative_executors'],'UNKNOWN')
            resume.set();thread.join(5);self.assertFalse(thread.is_alive());self.assertEqual(len(self.aws.calls),1)
            return results[0]
        finally:resume.set();thread.join(5)
    def test_10_pause_immediately_before_sdk_call_accounted(self):
        self.assertEqual(self.paused_dispatch()['status'],'SUCCESS');self.assertEqual(self.row()['state'],'SEALED')
    def test_11_dispatched_aws_call_accounted(self):self.assertEqual(self.paused_dispatch(after=True)['status'],'SUCCESS')
    def test_12_lost_response_remains_unknown(self):
        self.assertEqual(self.paused_dispatch(after=True,lost=True)['status'],'UNCERTAIN');self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_13_crash_before_dispatch_never_expires(self):
        self.admit();self.close();self.assertEqual(self.row()['state'],'ADMITTED')
        self.assertEqual(self.coordinator.inspect(self.active,self.selected,'b'*64)['cooperative_executors'],'UNKNOWN')
    def test_14_crash_after_dispatch(self):
        controller,transport,_=self.controller()
        transport.mutate=lambda *args:(_ for _ in ()).throw(SystemExit('crash'))
        with self.assertRaises(SystemExit):controller.run(OP,b'{}\n')
        self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_15_remote_success_before_ack_crash(self):
        controller,transport,_=self.controller()
        transport.remembered=lambda *args:(_ for _ in ()).throw(SystemExit('crash'))
        with self.assertRaises(SystemExit):controller.run(OP,b'{}\n')
        self.assertEqual(self.aws.eip[0],'eni-00000001');self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_16_duplicate_event_no_resend(self):
        controller,_,_=self.controller();self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS');self.assertEqual(len(self.aws.calls),1)
    def test_17_delayed_retry_no_new_permit(self):
        executor=self.admit();self.close();self.auth.values[self.action]['invocation_id']=OP
        with self.assertRaises(ValueError):self.admit()
        with self.assertRaises(ValueError):self.coordinator.transition(self.token,executor,'ADMITTED','CANCELLED',dict(api='NOT_SENT'))
    def test_18_old_version_rejected(self):
        self.auth.values[self.action]['qualified_arn']=self.auth.values[self.action]['qualified_arn'][:-1]+'2'
        with self.assertRaises(ValueError):self.admit()
    def test_19_uninstrumented_package_rejected(self):
        self.auth.values[self.action]['package_sha256']='f'*64
        with self.assertRaises(ValueError):self.admit()
    def test_20_journal_mismatch_before_admission(self):
        controller,_,cooperative=self.controller();records=cooperative.records
        records.create(self.token+'/plan',c.canonical(dict(token=self.token,request={})))
        records.create(self.token+'/attempt',c.canonical(dict(token=self.token,plan_sha256='a'*64)))
        with self.assertRaises(ValueError):cooperative.mutate(self.action,self.token,self.request_api,1000)
        self.assertEqual(self.head.read()[0]['permits'],{})
    def test_21_unknown_executor_no_timeout_settlement(self):self.test_13_crash_before_dispatch_never_expires()
    def test_22_cooperative_executor_seal_all_duties(self):
        for action in n.ACTIONS:
            self.setUp();controller,_,_=self.controller(action)
            self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
            row=next(iter(self.head.read()[0]['permits'].values()))
            self.assertEqual(row['state'],'SEALED');self.assertEqual(row['evidence']['effect'],'APPLIED_OBSERVED')
    def test_23_observed_effect_never_claims_remote_finality(self):
        controller,_,_=self.controller();controller.run(OP,b'{}\n');self.close()
        report=self.coordinator.inspect(self.active,self.selected,'b'*64)
        self.assertEqual(report['cooperative_executors'],'SEALED');self.assertEqual(report['effect_finality'],'UNPROVED')
    def test_24_unknown_effect_cannot_seal(self):
        controller,transport,_=self.controller();transport.effect=lambda token,deadline:dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN');self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_25_conflicting_effect_readback(self):
        controller,transport,_=self.controller();original=transport.mutate
        def changed(*args):original(*args);self.aws.eip[0]='eni-ffffffff'
        transport.mutate=changed;transport.effect=lambda token,deadline:dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN');self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_26_missing_head_version(self):
        original=self.s3.get_object
        def invalid(**args):result=original(**args);result['VersionId']='null';return result
        self.s3.get_object=invalid
        with self.assertRaises(ValueError):self.head.read()
    def test_27_foreign_operation_generation(self):
        self.close();selected=copy.deepcopy(self.selected);selected['request_sha256']='e'*64
        with self.assertRaises(ValueError):self.coordinator.close(self.active,selected,'b'*64)
    def test_31_interrupted_owner_cannot_resume_closure(self):
        self.close();replacement=e.Authority(self.store,self.binding,OP,self.request,layer='global')
        with self.assertRaises(e.CoordinationError):replacement.acquire()
        with self.assertRaises(e.CoordinationError):self.coordinator.close(replacement,self.selected,'b'*64)
    def test_32_e4_uncertain_retains_owner(self):
        self.close();self.active.touched=True
        self.active.finish(status='UNCERTAIN')
        self.assertEqual(self.store.read()[0]['state'],'ACTIVE')
    def test_33_wp5_approval_cannot_skip_missing_nat(self):
        owner=self.owner();protocol=self.protocol(owner)
        with self.assertRaisesRegex(ValueError,'SETTLEMENT_REQUIRED'):protocol.require_network_teardown()
    def test_34_stale_e2_closure_denied(self):
        self.close();self.active.finish(status='FAILURE')
        with self.assertRaises(e.CoordinationError):self.coordinator.inspect(self.active,self.selected,'b'*64)
    def test_35_cross_account_and_prod_executor_rejected(self):
        for segment in ('nat-prod','000000000000'):
            self.setUp();self.auth.values[self.action]['qualified_arn']=self.auth.values[self.action]['qualified_arn'].replace('nat-dev',segment).replace(self.config['account'],segment)
            with self.assertRaises(ValueError):self.admit()
    def test_36_no_iam_expansion(self):
        from test_nat import DOC
        self.assertEqual(DOC['wp4d']['installations'],{})
        self.assertEqual(DOC['wp4d']['environment_bindings'],{})
    def test_37_no_alternative_terraform_authority(self):
        self.assertFalse(hasattr(n.Coordinator,'apply'));self.assertFalse(hasattr(n.Head,'initialize'))
        self.assertFalse(hasattr(n.Coordinator,'release'))
    def test_38_guard_no_false_down_success(self):
        controller,_,_=self.controller();controller.run(OP,b'{}\n');owner=self.owner()
        protocol=__import__('scripts.nat.quiescence',fromlist=['Quiescence']).Quiescence(owner,self.request,self.protected,self.config,self.records,self.observation,now=lambda:1000,closure=self.coordinator)
        with self.assertRaisesRegex(ValueError,'SETTLEMENT_REQUIRED'):protocol.require_network_teardown()
        self.assertEqual(self.head.read()[0]['state'],'CLOSED');self.assertEqual(self.store.read()[0],owner.value)
    def test_39_e13_without_wrapper_still_works(self):
        controller,transport,_=self.controller();transport.ec2=self.aws;controller.runtime=transport;controller.journal.runtime=transport
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS');self.assertEqual(self.head.read()[0]['permits'],{})
    def test_40_synthetic_installed_denial(self):
        with self.assertRaisesRegex(ValueError,'INSTALLATION_REQUIRED'):n.Installed().protocol()
    def test_41_lost_cas_ack_exact_readback(self):
        self.s3.lost_ack=True;self.admit();self.assertEqual(self.row()['state'],'ADMITTED')
    def test_42_failed_cas_no_api_dispatch(self):
        self.s3.drop_write=True
        with self.assertRaises(ValueError):self.admit()
        self.assertEqual(self.aws.calls,[])
    def test_43_terminal_permit_cannot_issue_second_call(self):
        controller,_,_=self.controller();controller.run(OP,b'{}\n')
        with self.assertRaises(ValueError):self.admit()
        self.assertEqual(len(self.aws.calls),1)
    def test_44_journal_ack_version_missing(self):
        controller,transport,cooperative=self.controller();original=cooperative.records.read
        def corrupt(key):
            observed=original(key)
            if key.endswith('/ack') and observed:observed['version_id']='null'
            return observed
        cooperative.records.read=corrupt
        transport.effect=lambda token,deadline:dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN');self.assertEqual(self.row()['state'],'DISPATCHED')

    def test_49_whole_operation_original_edge_owner_exact_global_child(self):
        import test_operational as whole
        fixture=whole.WholeOperation();fixture.setUp();config=AWS().config
        head=n.Head(fixture.s3,config)
        fixture.s3.put_object(Bucket=head.bucket,Key=n.KEY,Body=c.canonical(n.initial(config,fixture.store.read()[0],OTHER)),IfNoneMatch='*')
        coordinator=n.Coordinator(head,fixture.store,config,Identity(config),self.versions)
        fixture.start()
        from scripts.nat.quiescence import Quiescence
        protocol=Quiescence(fixture.authority,fixture.requests[-1],fixture.p,config,fixture.records,
            baseline.Observations(config),now=lambda:1000,operation=fixture.operation,closure=coordinator)
        with self.assertRaisesRegex(ValueError,'SETTLEMENT_REQUIRED'):protocol.require_network_teardown()
        closure=head.read()[0]['closure']
        self.assertEqual(closure['owner'],fixture.operation.owner)
        self.assertEqual(closure['operation_sha256'],c.digest(c.canonical(fixture.operation.manifest)))
        self.assertEqual(closure['global_request_sha256'],c.digest(c.canonical(fixture.requests[-1])))
        self.assertEqual(fixture.store.read()[0],fixture.operation.owner)
    def test_50_sdk_response_identity_retained_separately_from_effect(self):
        original=self.aws.associate_address
        def responded(**args):
            original(**args);return dict(ResponseMetadata=dict(RequestId='service-request-1'),AssociationId='eipassoc-1')
        self.aws.associate_address=responded
        controller,_,cooperative=self.controller();self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
        observed=cooperative.records.read(self.token+'/api-response');value=json.loads(observed['bytes'])
        self.assertEqual(value['request_id'],'service-request-1');self.assertEqual(value['remote_finality'],'UNPROVED')
    def test_51_crash_after_ack_before_seal_preserves_unknown(self):
        controller,transport,_=self.controller();original=transport.mutate
        def crashed(*args):original(*args);raise SystemExit('crash after ACK')
        transport.mutate=crashed
        with self.assertRaises(SystemExit):controller.run(OP,b'{}\n')
        self.assertEqual(self.row()['state'],'DISPATCHED')
    def test_52_unknown_effect_retry_never_resends(self):
        controller,transport,_=self.controller()
        def lost(**args):self.aws.calls.append(('assign_eip',args));raise TimeoutError()
        self.aws.associate_address=lost
        transport.effect=lambda token,deadline:dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN')
        self.assertEqual(controller.run(OP,b'{}\n')['status'],'UNCERTAIN');self.assertEqual(len(self.aws.calls),1)

    def test_53_sdk_boundary_cannot_reuse_consumed_permit(self):
        controller,_,cooperative=self.controller();self.assertEqual(controller.run(OP,b'{}\n')['status'],'SUCCESS')
        with self.assertRaisesRegex(ValueError,'single-use'):cooperative.capture.associate_address(**self.request_api)
        self.assertEqual(len(self.aws.calls),1)
    def test_54_sdk_boundary_no_unadmitted_call(self):
        _,_,cooperative=self.controller()
        with self.assertRaises(ValueError):cooperative.capture.associate_address(**self.request_api)
        self.assertEqual(self.aws.calls,[])


class NativeCase(unittest.TestCase):
    def setUp(self):
        self.aws=AWS();self.config=self.aws.config;self.groups={s['asg']:dict(AutoScalingGroupName=s['asg'],
            VPCZoneIdentifier=s['subnet'],MinSize=0,MaxSize=0,DesiredCapacity=0,Instances=[],
            SuspendedProcesses=[dict(ProcessName=p) for p in native.PROCESSES]) for s in self.aws.slots}
        self.activities={name:[] for name in self.groups}
        self.prior={name:[] for name in self.groups}
        self.sdk=type('ASG',(),{})()
        self.sdk.describe_auto_scaling_groups=lambda AutoScalingGroupNames:dict(AutoScalingGroups=[copy.deepcopy(self.groups[n]) for n in AutoScalingGroupNames])
        self.sdk.describe_scaling_activities=lambda AutoScalingGroupName,**args:dict(Activities=copy.deepcopy(self.activities[AutoScalingGroupName]))
        self.protocol=native.Native(self.sdk,self.aws,self.config)
    def test_28_replacement_in_progress(self):
        name=next(iter(self.groups));self.activities[name]=[dict(AutoScalingGroupName=name,ActivityId='a',StatusCode='InProgress')]
        self.assertIn('NATIVE_ACTIVITY_UNSETTLED',self.protocol.observe(self.prior)['blockers'])
    def test_29_desired_zero_live_members(self):
        name=next(iter(self.groups));self.groups[name]['Instances']=[dict(InstanceId='i-00000001')]
        self.assertIn('NATIVE_MEMBERS_REMAIN',self.protocol.observe(self.prior)['blockers'])
    def test_30_terminal_asg_snapshot_not_finality(self):
        report=self.protocol.observe(self.prior);self.assertEqual(report['snapshot'],'TERMINAL_OBSERVED')
        self.assertEqual(report['service_finality'],'UNPROVED');self.assertFalse(report['installed'])
    def test_45_prior_member_termination_required(self):
        name=next(iter(self.groups));self.prior[name]=['i-00000001']
        self.assertIn('PRIOR_INSTANCE_TERMINATION_UNPROVED',self.protocol.observe(self.prior)['blockers'])
        self.aws.describe_instances=lambda InstanceIds:dict(Reservations=[dict(Instances=[dict(InstanceId=i,State=dict(Name='terminated')) for i in InstanceIds])])
        self.assertEqual(self.protocol.observe(self.prior)['snapshot'],'TERMINAL_OBSERVED')
    def test_46_native_plan_exact_two_slots_and_no_execution(self):
        commands=self.protocol.commands();self.assertEqual(len(commands),2)
        self.assertTrue(all('Terminate' not in item['suspend']['ScalingProcesses'] and item['capacity']['MaxSize']==0 for item in commands))
        self.assertFalse(hasattr(self.protocol,'execute'));self.assertEqual(self.aws.calls,[])
    def test_47_resumed_controller_blocks(self):
        self.groups[next(iter(self.groups))]['SuspendedProcesses']=[]
        self.assertIn('NATIVE_INHIBITION_UNPROVED',self.protocol.observe(self.prior)['blockers'])
    def test_48_failed_activity_without_end_is_unsettled(self):
        name=next(iter(self.groups));self.activities[name]=[dict(AutoScalingGroupName=name,ActivityId='a',StatusCode='Failed')]
        self.assertIn('NATIVE_ACTIVITY_UNSETTLED',self.protocol.observe(self.prior)['blockers'])
