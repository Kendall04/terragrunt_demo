"""Controlled interleavings of E1 delivery journals and actual E2 grants."""
import copy
import json
import unittest
from unittest.mock import patch

from scripts import environment_mutation as e
from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.tests.delivery.fixtures import setup, OP, NEXT
from scripts.tests.mutation.test_mutation import S3, bootstrap


class Recovery(unittest.TestCase):
    def setUp(self):
        self.configure()

    def configure(self, endpoint='deploy-dev'):
        self.f, self.auth, self.records, self.world, self.process, self.core, self.raw = setup(endpoint)
        self.env = a.ENDPOINTS[endpoint]
        self.s3 = S3()
        self.store = self.s3.seed(self.env)
        self.owner = e.Authority(self.store, 'normal-delivery/' + endpoint, OP, a.decode(self.raw))
        for stage in d.STAGES:
            original = getattr(self.world, stage)
            def guarded(*args, method=original, selected=stage):
                if selected == 'cleanup': self.owner.schedule()
                return self.owner.call(method, *args)
            setattr(self.world, stage, guarded)

    def original(self):
        return e.execute(self.owner, lambda _: self.core.run(OP, self.raw))

    def recover(self):
        return e.execute(self.owner, lambda grant: self.core.recover_post_switch(OP, self.raw, grant))

    def stages(self):
        return [stage for stage, _ in self.world.calls]

    def partial(self):
        self.records.fail = '/switch/observed'
        self.assertEqual(self.original()['status'], 'UNCERTAIN')
        self.assertEqual(self.world.state['normal_target'], self.world.intent['service']['loadBalancers'][0]['targetGroupArn'])
        self.assertEqual(self.stages(), ['register', 'drain', 'attach', 'start', 'e3', 'switch'])
        self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')
        self.records.fail = None

    def blocked(self, checkpoint=None):
        calls = copy.deepcopy(self.world.calls)
        result = self.recover()
        self.assertEqual(result['status'], 'UNCERTAIN')
        if checkpoint:
            if 'checkpoint' in result: self.assertEqual(result['checkpoint'], checkpoint)
            else: self.assertEqual(result['reason'], 'E2 mutation ownership unavailable')
        self.assertEqual(self.world.calls, calls)
        self.assertNotIn(self.env + '/' + OP + '/success', self.records.data)
        self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')

    def test_successful_original_path_unchanged(self):
        result = e.execute(self.owner, lambda grant: self.core.run_owned(OP, self.raw, grant))
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(self.stages(), ['register', 'drain', 'attach', 'start', 'e3', 'switch', 'candidate', 'cleanup'])
        self.assertEqual(self.store.read()[0]['state'], 'RELEASED')

    def test_failure_immediately_after_switch_then_exact_continuation(self):
        self.partial()
        self.assertEqual(self.recover()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('switch'), 1)
        self.assertEqual(self.stages().count('e3'), 1)
        self.assertEqual(self.stages()[-2:], ['candidate', 'cleanup'])
        self.assertIn(self.env + '/' + OP + '/switch/reconciled', self.records.data)
        self.assertEqual(self.store.read()[0]['state'], 'RELEASED')

    def test_installed_owned_path_one_automatic_continuation(self):
        create = self.records.create
        dropped = []
        def once(key, raw):
            if key.endswith('/switch/observed') and not dropped:
                dropped.append(key)
                raise OSError('one lost evidence write')
            return create(key, raw)
        self.records.create = once
        result = e.execute(self.owner, lambda grant: self.core.run_owned(OP, self.raw, grant))
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('switch'), 1)

    def test_installed_adapter_invokes_owned_boundary(self):
        module = bootstrap()
        from scripts.wp4d import adapters, aws_runtime
        config = dict(binding='normal-delivery/deploy-dev', environment='dev',
                      account=self.auth.account, region=self.auth.region,
                      evidence_bucket='protected-dev', admin_bucket='fixed',
                      dev_evidence_bucket='fixed', repository='fixed', resources={})
        self.owner.acquire()
        create = self.records.create
        dropped = []
        def once(key, raw):
            if key.endswith('/switch/observed') and not dropped:
                dropped.append(key)
                raise OSError()
            return create(key, raw)
        self.records.create = once
        # Use the actual controller/ownership/publication sequencing. SDK/facts,
        # process and storage ports alone are replaced, never run_owned/recover.
        with patch.object(adapters, 'Objects', return_value=self.records), \
             patch.object(adapters, 'Facts', return_value=self.f), \
             patch.object(adapters.History, 'publish') as publish, \
             patch.object(aws_runtime, 'Delivery', return_value=self.world), \
             patch.object(aws_runtime, 'BoundedProcess', return_value=self.process):
            clients = dict(s3=self.s3, ecs=None, elbv2=None, events=None, ecr=None)
            result = e.execute(self.owner, lambda grant: module._normal_owned(
                clients, config, OP, a.decode(self.raw), grant))
        self.assertEqual(result['status'], 'SUCCESS')
        publish.assert_called_once()
        self.assertEqual(self.stages().count('switch'), 1)

    def test_lost_response_applied_effect_independently_observed(self):
        self.world.ambiguous.add('switch')
        self.partial()
        self.assertEqual(self.recover()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('switch'), 1)

    def test_lost_response_without_attribution_stays_uncertain(self):
        self.partial()
        self.world.hidden.add('switch')
        self.blocked('immutable-effects')

    def test_definitely_failed_candidate_not_resent_or_compensated(self):
        self.world.fail.add('candidate')
        self.assertEqual(self.original()['status'], 'UNCERTAIN')
        self.world.fail.clear()
        self.blocked('immutable-effects')
        self.assertEqual(self.stages().count('candidate'), 1)
        self.assertNotIn('cleanup', self.stages())

    def test_definitely_failed_cleanup_not_resent(self):
        self.world.fail.add('cleanup')
        self.assertEqual(self.original()['status'], 'UNCERTAIN')
        self.world.fail.clear()
        self.blocked('immutable-effects')
        self.assertEqual(self.stages().count('cleanup'), 1)

    def test_valid_journal_cannot_override_contradictory_effect_readback(self):
        self.records.fail = '/success'
        self.assertEqual(self.original()['status'], 'UNCERTAIN')
        self.records.fail = None
        self.world.effects[self.env + '/' + OP + '/switch'] = dict(
            token=self.env + '/' + OP + '/switch', request_sha256=None, state='ABSENT', result=None)
        self.blocked('current-switch-effect')

    def test_valid_effect_cannot_override_contradictory_listener_readback(self):
        self.partial()
        self.world.state['normal_target'] = 'newer-target'
        self.blocked('current-authorization-and-topology')

    def test_replaced_cohort_or_revision_or_deployment_rejects(self):
        for field, value in (('cohort', []), ('task_definition', self.world.revision.rsplit(':', 1)[0] + ':99'),
                             ('deployment', 'ecs-svc/replaced')):
            with self.subTest(field=field):
                self.configure(); self.partial(); self.world.state[field] = value
                self.blocked('current-authorization-and-topology')

    def test_repeated_recovery_returns_historical_terminal_no_mutation(self):
        self.partial()
        result = self.recover()
        calls = copy.deepcopy(self.world.calls)
        for _ in range(2):
            self.assertEqual(self.recover()['status'], 'SUCCESS')
        self.assertEqual(self.world.calls, calls)
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(self.store.read()[0]['generation'], 1)

    def test_receipt_write_recovery_revalidates_all_post_switch_effects(self):
        self.records.fail = '/success'
        self.assertEqual(self.original()['status'], 'UNCERTAIN')
        self.records.fail = None
        calls = copy.deepcopy(self.world.calls)
        self.assertEqual(self.recover()['status'], 'SUCCESS')
        self.assertEqual(self.world.calls, calls)

    def test_crashed_after_switch_retains_owner_without_automatic_takeover(self):
        class Crash(BaseException): pass
        create = self.records.create
        def crash(key, raw):
            if key.endswith('/switch/observed'): raise Crash()
            return create(key, raw)
        self.records.create = crash
        with self.assertRaises(Crash): self.original()
        self.assertEqual(self.stages()[-1], 'switch')
        self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')
        contender = e.Authority(self.store, self.owner.binding, OP, a.decode(self.raw))
        calls = copy.deepcopy(self.world.calls)
        self.assertEqual(e.execute(contender, lambda _: self.fail('crash takeover'))['status'], 'UNCERTAIN')
        self.assertEqual(self.world.calls, calls)

    def test_stale_owner_generation_rejects_before_progress(self):
        self.partial()
        head, etag = self.store.read()
        self.store.exchange(dict(head, generation=2, owner=NEXT, operation=NEXT), etag)
        self.blocked('ownership')

    def test_same_operation_new_invocation_cannot_borrow_interrupted_owner(self):
        self.partial()
        other = e.Authority(self.store, self.owner.binding, OP, a.decode(self.raw))
        calls = copy.deepcopy(self.world.calls)
        result = e.execute(other, lambda grant: self.core.recover_post_switch(OP, self.raw, grant))
        self.assertEqual(result['status'], 'UNCERTAIN')
        self.assertEqual(self.world.calls, calls)
        self.assertEqual(self.store.read()[0]['owner'], self.owner.owner)

    def test_competing_new_deployment_blocked_by_recovery_owner(self):
        self.partial()
        contender = e.Authority(self.store, self.owner.binding, NEXT, a.decode(self.raw))
        self.assertEqual(e.execute(contender, lambda _: self.fail('contender entered'))['status'], 'UNCERTAIN')
        self.assertEqual(self.recover()['status'], 'SUCCESS')

    def test_newer_owner_fences_old_recovery_and_old_cleanup(self):
        self.partial()
        proof = self.owner.schedule()
        head, etag = self.store.read()
        # Synthetic authenticated administrative release, never an E4 API.
        self.store.exchange(dict(head, state='RELEASED'), etag)
        newer = e.Authority(self.store, self.owner.binding, NEXT, a.decode(self.raw)).acquire()
        self.blocked('ownership')
        newer.finish(True)
        cleanup = e.Authority(self.store, 'cleanup-recovery/cleanup-dev', OP, {}, cleanup=proof)
        self.assertEqual(e.execute(cleanup, lambda _: self.fail('stale cleanup entered'))['status'], 'UNCERTAIN')
        self.assertEqual(self.stages().count('switch'), 1)

    def test_dev_prod_independent_while_dev_retains_ownership(self):
        self.partial()
        prod = e.Authority(self.s3.seed('prod'), 'normal-delivery/promote-prod', NEXT, {})
        self.assertEqual(e.execute(prod, lambda grant: (grant.call(lambda: None) or {'status': 'SUCCESS'}))['status'], 'SUCCESS')
        self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')
        self.assertEqual(self.recover()['status'], 'SUCCESS')

    def test_unavailable_or_corrupt_arbitration_fails_closed(self):
        for corrupt in (False, True):
            self.configure(); self.partial()
            if corrupt: self.s3.values[self.store.bucket, self.store.key] = (b'{}\n', 99)
            else: self.s3.fail_read = True
            calls = copy.deepcopy(self.world.calls)
            result = self.core.recover_post_switch(OP, self.raw, self.owner)
            self.assertEqual(result['status'], 'UNCERTAIN')
            self.assertEqual(result['checkpoint'], 'ownership')
            self.assertEqual(self.world.calls, calls)

    def test_missing_or_corrupt_operation_activation_attempt_and_reconciled(self):
        for suffix, raw in (('intent', None), ('intent', b'{}\n'), ('switch/attempt', b'{}\n'),
                            ('switch/attempt', None),
                            ('switch/plan', None), ('switch/reconciled', b'{}\n')):
            self.configure(); self.partial()
            key = self.env + '/' + OP + '/' + suffix
            if raw is None: self.records.data.pop(key)
            else: self.records.data[key] = raw
            self.blocked()
        self.configure(); self.partial()
        for key in list(self.records.data):
            if '/activations/' in key: self.records.data.pop(key)
        self.blocked('switch-attempt-and-activation')

    def test_production_approval_or_eligibility_failure(self):
        for revoke in (False, True):
            self.configure('promote-prod'); self.partial()
            if revoke: self.f.e['state'] = 'REVOKED'
            else: self.f.approval['bytes'] = b'{}\n'
            self.blocked('current-authorization-and-topology')

    def test_expired_original_deadline_never_extended(self):
        self.partial(); self.world.time = 2801
        self.blocked('current-authorization-and-topology')

    def test_rule_and_cleanup_plan_io_drift_blocks_mutation(self):
        for stage in ('candidate', 'cleanup'):
            for drift in ('routing', 'authorization', 'cohort', 'ownership'):
                self.configure(); self.partial()
                create = self.records.create
                def changed(key, raw):
                    create(key, raw)
                    if key.endswith('/' + stage + '/attempt'):
                        if drift == 'routing': self.world.state['normal_target'] = 'changed'
                        elif drift == 'authorization': self.f.e['state'] = 'REVOKED'
                        elif drift == 'cohort': self.world.state['cohort'] = []
                        else:
                            head, etag = self.store.read()
                            self.store.exchange(dict(head, generation=2, owner=NEXT, operation=NEXT), etag)
                self.records.create = changed
                result = self.recover()
                self.assertEqual(result['status'], 'UNCERTAIN')
                self.assertNotIn(stage, self.stages())
                self.assertNotIn(self.env + '/' + OP + '/success', self.records.data)
                self.assertEqual(self.stages().count('switch'), 1)

    def test_wrong_request_or_environment_grant_rejected(self):
        self.partial()
        changed = dict(a.decode(self.raw), replicas=1)
        result = self.core.recover_post_switch(OP, a.canonical(changed), self.owner)
        self.assertEqual(result['checkpoint'], 'ownership')
        prod = e.Authority(self.s3.seed('prod'), 'normal-delivery/promote-prod', OP, a.decode(self.raw)).acquire()
        result = self.core.recover_post_switch(OP, self.raw, prod)
        self.assertEqual(result['checkpoint'], 'ownership')
        self.assertEqual(self.stages()[-1], 'switch')

    def test_actual_runtime_missing_ack_cannot_infer_switch_from_matching_route(self):
        from scripts.wp4d.aws_runtime import Effects
        self.partial()
        runtime = Effects(self.records)
        runtime.now = lambda: 1000
        # No durable call-linked ACK exists in this domain fixture. A valid
        # switch journal and matching listener are deliberately insufficient.
        observed = runtime.effect(self.env + '/' + OP + '/switch', 1030)
        self.assertEqual(observed['state'], 'UNKNOWN')

    def test_actual_schedule_readback_requires_enabled_exact_generation(self):
        from scripts.wp4d.aws_runtime import Delivery
        self.owner.acquire()
        self.owner.schedule()
        class Events:
            state = 'ENABLED'
            def describe_rule(events, **kw):
                return dict(ScheduleExpression='rate(5 minutes)', State=events.state)
            def list_targets_by_rule(events, **kw):
                return dict(Targets=[events.target])
        events = Events()
        runtime = object.__new__(Delivery)
        runtime.events = e.Client(events, 'events', self.owner)
        target = dict(Id='scale-down', Arn='fixed-function')
        events.target = e.scheduled_target(runtime.events, target)
        schedule = dict(rule='fixed', expression='rate(5 minutes)')
        self.assertTrue(runtime._schedule_matches(schedule, target))
        events.state = 'DISABLED'
        self.assertFalse(runtime._schedule_matches(schedule, target))
        events.state = 'ENABLED'
        events.target['InputTransformer'] = e.cleanup_transformer(dict(self.owner.value['schedule'], generation=2))
        self.assertFalse(runtime._schedule_matches(schedule, target))

    def test_unresolved_repeated_owned_invocation_has_bounded_passes(self):
        self.world.on_mutation = lambda world, stage: world.hidden.add(stage) if stage == 'switch' else None
        with patch.object(self.core, 'recover_post_switch', wraps=self.core.recover_post_switch) as recover:
            for _ in range(2):
                result = e.execute(self.owner, lambda grant: self.core.run_owned(OP, self.raw, grant))
                self.assertEqual(result['status'], 'UNCERTAIN')
            self.assertEqual(recover.call_count, 2)
        self.assertEqual(self.stages().count('switch'), 1)
        self.assertNotIn('candidate', self.stages())


if __name__ == '__main__': unittest.main()
