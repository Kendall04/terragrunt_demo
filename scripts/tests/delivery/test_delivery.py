"""Production state-machine traces and finite behavioral guard mutants."""
import copy
import json
import inspect
import textwrap
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.normal_delivery.e3 import Gate
from scripts.normal_delivery.model_consistency import validate
from scripts.tests.delivery.fixtures import setup, OP, NEXT, Runtime, ProcessFixture


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.f,self.auth,self.records,self.world,self.process,self.core,self.raw=setup()
    def run_delivery(self):return self.core.run(OP,self.raw)
    def stages(self):return [x[0] for x in self.world.calls]
    def no_switch(self):
        result=self.run_delivery()
        self.assertNotEqual(result['status'],'SUCCESS')
        self.assertNotIn('switch',self.stages())
        self.assertNotIn('dev/'+OP+'/success',self.records.data)
        return result
    def test_dev_complete_order_and_receipt(self):
        result=self.run_delivery();self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(self.stages(),['register','drain','attach','start','e3','switch','candidate','cleanup'])
        self.assertEqual(result['intent']['membership'],self.world.intent['membership'])
        self.assertEqual(result['registration']['task_definition_arn'],self.world.revision)
        self.assertEqual(result['activation']['e3']['context']['cohort'],result['final']['cohort'])
        self.assertNotIn('demo-prod',a.canonical(self.world.calls).decode())
        self.assertTrue(all(result['effects'].values()))
    def test_deterministic_independent_execution(self):
        first=self.run_delivery();*_,core,raw=setup()
        self.assertEqual(first,core.run(OP,raw))
    def test_prod_consumes_real_dev_receipt_projection(self):
        dev=self.run_delivery();f,auth,records,w,p,c,raw=setup('promote-prod')
        f.receipt=dict(release_id=f.q['release_id'],version_id='dev-receipt-version',bytes=a.canonical(d.dev_prerequisite(dev)))
        prod=c.run(OP,raw)
        self.assertEqual(prod['status'],'SUCCESS')
        self.assertEqual(dev['intent']['release'],prod['intent']['release'])
        self.assertNotIn('demo-dev',a.canonical(w.calls).decode())
        self.assertEqual(prod['intent']['promotion']['dev_receipt']['sha256'],a.sha(f.receipt['bytes']))
    def history(self):
        self.assertEqual(self.run_delivery()['status'],'SUCCESS')
        f,auth,r,w,p,c,raw=setup(records=self.records)
        request=a.canonical(dict(action='rollback-release',history=OP,replicas=2))
        return f,auth,r,w,p,c,request
    def test_history_reauthorized_normal_path(self):
        f,auth,r,w,p,c,raw=self.history();result=c.run(NEXT,raw)
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(result['action'],'rollback-release')
        self.assertEqual(result['history']['operation_id'],OP)
        self.assertEqual([x[0] for x in w.calls],self.stages())
    def test_history_revoked_no_mutation(self):
        f,auth,r,w,p,c,raw=self.history();f.e['state']='REVOKED'
        self.assertEqual(c.run(NEXT,raw)['status'],'FAILURE');self.assertEqual(w.calls,[])
    def test_history_missing_artifact_no_rebuild(self):
        f,auth,r,w,p,c,raw=self.history();f.available['available']=False
        self.assertEqual(c.run(NEXT,raw)['status'],'FAILURE');self.assertEqual(w.calls,[])
    def test_history_wrong_environment_and_missing(self):
        for selected in (OP,NEXT):
            raw=a.canonical(dict(action='rollback-release',history=selected,replicas=2))
            self.assertEqual(self.core.run(NEXT,raw)['status'],'FAILURE')
    def test_closed_request(self):
        for field in ('task','image','roles','service','cluster','color','environment','ready','approved','membership'):
            with self.subTest(field=field):
                request=json.loads(self.raw);request[field]=True
                self.assertEqual(self.core.run(OP,a.canonical(request))['status'],'FAILURE')
        self.assertEqual(self.world.calls,[])
    def test_bad_operation_and_replicas(self):
        for operation in ('../prod',None,'latest'):
            self.assertEqual(self.core.run(operation,self.raw)['status'],'FAILURE')
        for replicas in (0,101,True,None,'2',4):
            request=json.loads(self.raw);request['replicas']=replicas
            self.assertEqual(self.core.run(OP,a.canonical(request))['status'],'FAILURE')
        self.assertEqual(self.world.calls,[])
    def test_authorization_missing_or_invalid(self):
        for change in (lambda:setattr(self.f,'q_raw',b'{}'),lambda:self.f.e.update(state='REVOKED'),
                       lambda:self.f.available.update(available=False),lambda:self.f.members['dev']['colors']['blue'].pop('kms_key_arn')):
            self.setUp();change();self.no_switch();self.assertEqual(self.world.calls,[])
    def test_readback_security_divergence_no_start(self):
        self.world.readback=copy.deepcopy(self.world.task)
        self.world.readback['containerDefinitions'][0]['image']='wrong'
        self.no_switch();self.assertEqual(self.stages(),['register'])
    def test_readback_revision_mismatch(self):
        self.world.readback=copy.deepcopy(self.world.task)
        self.world.readback['revision']=18
        self.no_switch();self.assertNotIn('start',self.stages())
    def test_wrong_candidate_color_service_cluster(self):
        for field in ('color','service','cluster','listener','rule'):
            self.setUp();self.world.state[field]='wrong';self.no_switch();self.assertEqual(self.world.calls,[])
    def test_candidate_is_active_rejects(self):
        self.world.state['normal_target']=self.world.state['candidate_target'];self.no_switch()
        self.assertEqual(self.world.calls,[])
    def test_ambiguous_initial_mapping(self):
        self.world.state['candidate_target']='unknown';self.no_switch()
    def test_startup_failure_uncertain_no_e3(self):
        self.world.fail.add('start');result=self.no_switch()
        self.assertEqual(result['status'],'UNCERTAIN');self.assertNotIn('e3',self.stages())
    def test_partial_candidate_e3_failure_no_switch(self):
        self.process.exit=1;self.no_switch()
        self.assertEqual(self.world.state['running'],2)
    def test_e3_timeout_and_unavailable(self):
        for code in (124,137,1,None):
            self.setUp();self.process.exit=code;self.no_switch()
    def test_e3_incomplete_unknown_and_wrong_cohort(self):
        for mutate in (lambda e:e.pop('fingerprint'),lambda e:e.update(ready=True),
                       lambda e:e.update(cohort=[]),lambda e:e.update(fingerprint='bad')):
            self.setUp();self.process.mutate=mutate;self.no_switch()
    def test_e3_wrong_operation_revision_attempt_context(self):
        self.process.mutate=lambda e:e.update(context_sha256='0'*64);self.no_switch()
    def test_e3_deadline_expired_before_switch(self):
        self.process.after=lambda:setattr(self.world,'time',2801);self.no_switch()
    def test_revocation_between_e3_and_switch(self):
        self.process.after=lambda:self.f.e.update(state='REVOKED');self.no_switch()
    def test_membership_and_binding_drift_before_switch(self):
        for change in (lambda:self.f.members['dev']['colors']['blue'].update(kms_key_arn='changed'),
                       lambda:self.f.bindings['deploy-dev'].update(max_replicas=2)):
            self.setUp();self.process.after=change;self.no_switch()
    def test_listener_mapping_changes_after_e3(self):
        self.process.after=lambda:self.world.state.update(normal_target='changed');self.no_switch()
    def test_revision_cohort_deployment_changes_after_e3(self):
        for field,value in [('task_definition','wrong'),('cohort',[]),('deployment','ecs-svc/replaced')]:
            self.setUp();self.process.after=lambda:self.world.state.update({field:value});self.no_switch()
    def test_prod_missing_dev_evidence_or_wrong_image(self):
        for mutate in (lambda f:setattr(f,'receipt',dict(release_id=f.q['release_id'],version_id='x',bytes=b'{}')),
                       lambda f:setattr(f,'receipt',{**f.receipt,'bytes':f.receipt['bytes'].replace(b'bbbbbbbb',b'cccccccc')}),
                       lambda f:setattr(f,'approval',dict(release_id=f.q['release_id'],version_id='x',bytes=b'{}'))):
            f,auth,r,w,p,c,raw=setup('promote-prod');mutate(f)
            self.assertEqual(c.run(OP,raw)['status'],'FAILURE');self.assertEqual(w.calls,[])
    def test_ambiguous_ack_with_exact_observation_succeeds(self):
        self.world.ambiguous.update(('register','start','switch','candidate','cleanup'))
        self.assertEqual(self.run_delivery()['status'],'SUCCESS')
        self.assertEqual(self.stages().count('register'),1)
    def test_ambiguous_registration_observe_before_retry(self):
        def hide(w,stage):
            if stage=='register':w.hidden.add(stage)
        self.world.on_mutation=hide
        self.assertEqual(self.run_delivery()['status'],'UNCERTAIN')
        self.world.hidden.clear();self.world.on_mutation=None
        self.assertEqual(self.run_delivery()['status'],'SUCCESS')
        self.assertEqual(self.stages().count('register'),1)
    def test_ambiguous_start_retry_reconciles_same_revision(self):
        self.world.on_mutation=lambda w,s:w.hidden.add(s) if s=='start' else None
        self.assertEqual(self.no_switch()['status'],'UNCERTAIN')
        self.world.hidden.clear();self.world.on_mutation=None
        self.assertEqual(self.run_delivery()['status'],'SUCCESS');self.assertEqual(self.stages().count('start'),1)
    def test_ambiguous_switch_not_success_until_observed(self):
        self.world.on_mutation=lambda w,s:w.hidden.add(s) if s=='switch' else None
        self.assertEqual(self.run_delivery()['status'],'UNCERTAIN')
        self.assertNotIn('dev/'+OP+'/success',self.records.data)
        self.world.hidden.clear();self.world.on_mutation=None
        self.assertEqual(self.run_delivery()['status'],'SUCCESS');self.assertEqual(self.stages().count('switch'),1)
        self.assertEqual(self.stages().count('e3'),1)
    def test_unsettled_switch_not_repeated(self):
        self.world.fail.add('switch')
        self.assertEqual(self.run_delivery()['status'],'UNCERTAIN')
        self.world.fail.clear()
        # Authoritative ABSENT is retained and terminal; never resend.
        self.assertEqual(self.run_delivery()['status'],'FAILURE');self.assertEqual(self.stages().count('switch'),1)
    def test_cleanup_failure_after_switch_is_uncertain(self):
        self.world.fail.add('cleanup');result=self.run_delivery()
        self.assertEqual(result['status'],'UNCERTAIN');self.assertIn('switch',self.stages())
        self.assertNotIn('dev/'+OP+'/success',self.records.data)
    def test_receipt_write_failure_after_switch_retry(self):
        self.records.fail='/success'
        self.assertEqual(self.run_delivery()['status'],'UNCERTAIN')
        self.records.fail=None
        self.assertEqual(self.run_delivery()['status'],'SUCCESS');self.assertEqual(self.stages().count('switch'),1)
    def test_evidence_ack_lost_exact_readback(self):
        self.records.ack_lost=True;self.assertEqual(self.run_delivery()['status'],'SUCCESS')
    def test_write_ahead_failure_prevents_mutation(self):
        self.records.fail='/register/plan';self.no_switch();self.assertEqual(self.world.calls,[])
    def test_retry_immutable_request(self):
        self.world.fail.add('register');self.run_delivery()
        request=json.loads(self.raw);request['replicas']=1
        self.assertEqual(self.core.run(OP,a.canonical(request))['status'],'FAILURE')
        self.assertEqual(self.stages().count('register'),1)
    def test_completed_retry_is_historical_no_mutation(self):
        first=self.run_delivery();calls=copy.deepcopy(self.world.calls)
        self.f.e['state']='REVOKED'
        self.assertEqual(self.run_delivery(),first);self.assertEqual(self.world.calls,calls)
    def test_unproven_effect_identity_rejects(self):
        original=self.world.effect
        def bad(token,deadline):
            result=original(token,deadline)
            if result['state']=='APPLIED':result['request_sha256']='0'*64
            return result
        self.world.effect=bad;self.no_switch();self.assertNotIn('start',self.stages())
    def test_model_consistency_canonical_control(self):validate()
    def test_model_contradictions_reject_acceptance(self):
        for mutate in (lambda m:m['forbidden_container'].append('image'),
                       lambda m:m['task_return_only'].append('taskRoleArn'),
                       lambda m:m['forbidden_service'].append('desiredCount'),
                       lambda m:m['task_required'].update(cpu='ENVIRONMENT_CONFIGURATION'),
                       lambda m:m['container_required']['app'].update(image='ENVIRONMENT_CONFIGURATION')):
            model=copy.deepcopy(a.MODEL);mutate(model)
            with self.assertRaises(a.Rejected):validate(model)
    def test_model_inconsistent_rejects_before_runtime(self):
        model=copy.deepcopy(a.MODEL);model['forbidden_container'].append('image')
        with patch.object(a,'MODEL',model):self.no_switch()
        self.assertEqual(self.world.calls,[])
    def test_retry_replacement_cohort_cannot_reuse_attempt(self):
        self.process.exit=1;self.no_switch()
        self.process.exit=0
        self.world.state['cohort']=[x+'new' for x in self.world.state['cohort']]
        self.no_switch();self.assertEqual(len(self.process.calls),1)
    def test_switch_plan_write_cannot_hide_last_moment_routing_change(self):
        original=self.records.create
        def changed(key,raw):
            original(key,raw)
            if key.endswith('/switch/plan'):self.world.state['normal_target']='changed'
        self.records.create=changed;self.no_switch()
    def test_switch_plan_write_cannot_hide_last_moment_revocation(self):
        original=self.records.create
        def changed(key,raw):
            original(key,raw)
            if key.endswith('/switch/plan'):self.f.e['state']='REVOKED'
        self.records.create=changed;self.no_switch()
    def test_effect_observation_failure_after_mutation_is_uncertain(self):
        original=self.world.effect
        def unavailable(token,deadline):
            if token.endswith('/start') and 'start' in self.stages():raise OSError()
            return original(token,deadline)
        self.world.effect=unavailable
        self.assertEqual(self.no_switch()['status'],'UNCERTAIN')
    def test_actual_green_candidate_positive(self):
        from scripts.tests.normal_delivery.test_authorization import make_binding, response
        from scripts.tests.delivery.fixtures import Runtime, ProcessFixture
        self.f.bindings['deploy-dev']=make_binding('dev','green')
        intent=self.auth.authorize(a.canonical(dict(release_id=self.f.q['release_id'],replicas=2)))
        w=Runtime(intent,self.records,self.f.members['dev']['colors']);p=ProcessFixture(w)
        c=d.Delivery(self.auth,w,self.records,Gate(p))
        result=c.run(OP,self.raw)
        self.assertEqual(result['status'],'SUCCESS');self.assertEqual(result['intent']['color'],'green')
    def test_e3_exact_arguments_and_bound(self):
        self.run_delivery();argv,budget=self.process.calls[0]
        self.assertEqual(budget,1800);self.assertEqual(argv[-1],'--use-instance-role')
        for key,value in [('service',self.world.intent['service']['service']),('task-definition-arn',self.world.revision),
                          ('desired-count','2'),('attempt-start-epoch','1000'),('deadline-epoch','2800')]:
            self.assertEqual(argv[argv.index('--'+key)+1],value)
    def test_e3_wrapper_uses_accepted_gate_without_reimplementation(self):
        text=(a.ROOT/'scripts/normal_delivery/e3-evidence.sh').read_text()
        self.assertIn('source "$wrapper_dir/../ecs-readiness-gate.sh"',text)
        self.assertLess(text.index('main "$@"'),text.index('jq -cn'))
        self.assertIn('$FROZEN_COHORT',text);self.assertIn('$OBSERVATION_FINGERPRINT',text)


class MutationTests(unittest.TestCase):
    """Every mutant starts from importable production code and a successful control.

    Acceptance assertions detect actual forbidden mutations, not syntax/setup
    failures. Each case also runs unchanged and proves its attack is rejected.
    """
    def test_behavioral_sequencing_mutants(self):
        reports=[]
        for name in ('authorization','readback','candidate','e3_failure','e3_identity',
                     'revalidation','early_switch','ambiguous_ack','prod','rollback'):
            with self.subTest(name=name):
                self.exercise(name,False)
                with self.assertRaises(AssertionError):self.exercise(name,True)
                reports.append(name)
        self.assertEqual(len(reports),10)
    def exercise(self,name,mutant):
        from contextlib import ExitStack
        endpoint='promote-prod' if name=='prod' else 'deploy-dev'
        f,auth,r,w,p,c,raw=setup(endpoint)
        baseline=copy.deepcopy(w.intent)
        if setup()[5].run(OP,setup()[6])['status'] != 'SUCCESS':
            raise RuntimeError('HARNESS_INVALID: unchanged positive control')
        operation=OP
        if name=='rollback':
            *_,seed,seedraw=setup(records=r)
            if seed.run(OP,seedraw)['status'] != 'SUCCESS':
                raise RuntimeError('HARNESS_INVALID: history setup')
            operation=NEXT;raw=a.canonical(dict(action='rollback-release',history=OP,replicas=2));f.e['state']='REVOKED'
        if name=='authorization':f.e['state']='REVOKED'
        if name=='prod':f.receipt['bytes']=b'{}'
        if name=='readback':w.readback=copy.deepcopy(w.task);w.readback['containerDefinitions'][0]['image']='wrong'
        if name=='candidate':w.state['service']='foreign-service'
        if name in ('e3_failure','early_switch'):p.exit=1
        if name=='e3_identity':p.mutate=lambda e:e.update(context_sha256='0'*64)
        if name=='revalidation':p.after=lambda:f.e.update(state='REVOKED')
        if name=='ambiguous_ack':
            w.on_mutation=lambda world,stage:world.hidden.add(stage) if stage=='switch' else None
        with ExitStack() as stack:
            if mutant:
                if name in ('authorization','prod','rollback','revalidation'):
                    stack.enter_context(patch.object(auth,'authorize',return_value=baseline))
                elif name=='readback':
                    checked=dict(task_definition_arn=w.revision,revision=17,intent_sha256=baseline['intent_sha256'])
                    stack.enter_context(patch.object(auth,'validate_registration_readback',return_value=checked))
                    stack.enter_context(patch.object(auth,'validate_readback',return_value=checked))
                elif name=='candidate':
                    original=c.snapshot
                    def bypass(op):
                        saved=w.state['service'];w.state['service']=baseline['service']['service']
                        try:return original(op)
                        finally:w.state['service']=saved
                    stack.enter_context(patch.object(c,'snapshot',side_effect=bypass))
                elif name in ('e3_failure','e3_identity'):
                    source=textwrap.dedent(inspect.getsource(Gate.run))
                    target=("a.require(type(result['exit_code']) is int and result['exit_code'] == 0)"
                            if name=='e3_failure' else
                            "a.exact(evidence['context_sha256'], identity, 'e3.context')")
                    if source.count(target) != 1: raise RuntimeError('HARNESS_INVALID: mutation location')
                    namespace=dict(Gate.run.__globals__)
                    exec(compile(source.replace(target,'pass'),'<behavioral-e3-mutant>','exec'),namespace)
                    stack.enter_context(patch.object(Gate,'run',namespace['run']))
                elif name=='early_switch':
                    source=textwrap.dedent(inspect.getsource(d.Delivery.deliver))
                    target='evidence = self.gate.run(context, self.bounded(op))'
                    if source.count(target) != 1: raise RuntimeError('HARNESS_INVALID: mutation location')
                    source=source.replace(target,"self.runtime.switch('mutant', switch_request, op['deadline'])\n        "+target)
                    namespace=dict(d.Delivery.deliver.__globals__)
                    exec(compile(source,'<behavioral-early-switch-mutant>','exec'),namespace)
                    stack.enter_context(patch.object(d.Delivery,'deliver',namespace['deliver']))
                elif name=='ambiguous_ack':
                    original=c.effect
                    def ack(op,stage,request,mutate=True,**kwargs):
                        try:return original(op,stage,request,mutate,**kwargs)
                        except d.Uncertain:
                            if stage=='switch':return request
                            raise
                    stack.enter_context(patch.object(c,'effect',side_effect=ack))
            result=c.run(operation,raw)
        if name=='ambiguous_ack':
            self.assertNotEqual(result['status'],'SUCCESS')
            self.assertNotIn('candidate',[x[0] for x in w.calls])
        elif name=='readback':self.assertNotIn('start',[x[0] for x in w.calls])
        elif name=='candidate':self.assertEqual(w.calls,[])
        elif name=='e3_identity':
            # V2 also checks the selected proof before switching. The original
            # Gate mutant must still be caught at admission of invalid evidence,
            # even when that independent later guard prevents activation.
            self.assertFalse(any('/e3/' in key for key in r.data))
            self.assertNotIn('switch',[x[0] for x in w.calls])
        else:self.assertNotIn('switch',[x[0] for x in w.calls])


if __name__=='__main__':unittest.main()
