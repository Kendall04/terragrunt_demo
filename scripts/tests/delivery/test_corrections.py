"""V2 production-path regressions for independent review findings F1-F3."""
import copy
import inspect
import textwrap
import unittest
from unittest.mock import patch

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.tests.delivery.fixtures import setup, OP, NEXT


class Corrections(unittest.TestCase):
    def setUp(self):
        self.f, self.auth, self.records, self.world, self.process, self.core, self.raw = setup()

    def run_delivery(self):
        return self.core.run(OP, self.raw)

    def stages(self):
        return [stage for stage, _ in self.world.calls]

    def after_plan(self, stage, change):
        create = self.records.create
        def intercept(key, raw):
            create(key, raw)
            if key.endswith('/' + stage + '/plan'): change()
        self.records.create = intercept

    def stopped_before(self, stage):
        result = self.run_delivery()
        self.assertEqual(result['status'], 'FAILURE')
        self.assertNotIn(stage, self.stages())
        self.assertNotIn('switch', self.stages())
        self.assertNotIn('dev/' + OP + '/success', self.records.data)
        return result

    def test_start_plan_routing_change(self):
        self.after_plan('start', lambda: self.world.state.update(normal_target=self.world.state['candidate_target']))
        self.stopped_before('start')
        self.assertEqual(self.world.state['running'], 0)

    def test_start_plan_revocation(self):
        self.after_plan('start', lambda: self.f.e.update(state='REVOKED'))
        self.stopped_before('start')
        self.assertEqual(self.world.state['running'], 0)

    def test_every_preparation_plan_reauthorizes(self):
        for stage in ('drain', 'attach', 'start'):
            for field in ('eligibility', 'membership', 'binding'):
                with self.subTest(stage=stage, field=field):
                    self.setUp()
                    def change():
                        if field == 'eligibility': self.f.e['state'] = 'REVOKED'
                        elif field == 'membership': self.f.members['dev']['colors']['blue']['kms_key_arn'] = 'changed'
                        else: self.f.bindings['deploy-dev']['max_replicas'] = 2
                    self.after_plan(stage, change)
                    self.stopped_before(stage)

    def test_every_preparation_plan_reobserves_topology(self):
        for stage in ('drain', 'attach', 'start'):
            for field in ('normal_target', 'candidate_target', 'service', 'color', 'cluster', 'environment'):
                with self.subTest(stage=stage, field=field):
                    self.setUp()
                    self.after_plan(stage, lambda: self.world.state.update({field: 'changed'}))
                    self.stopped_before(stage)

    def test_every_preparation_plan_reobserves_revision_counts_and_cohort(self):
        changes = dict(task_definition=':18', desired=1, running=1, pending=1,
                       deployment='ecs-svc/changed', cohort=['arn:aws:ecs:us-east-1:111122223333:task/cluster/changed'])
        for stage in ('drain', 'attach', 'start'):
            for field, value in changes.items():
                with self.subTest(stage=stage, field=field):
                    self.setUp()
                    if field == 'task_definition': value = self.world.revision.rsplit(':', 1)[0] + value
                    self.after_plan(stage, lambda: self.world.state.update({field: value}))
                    self.stopped_before(stage)

    def test_preparation_guard_allows_clock_progress_and_old_inactive_revision(self):
        self.world.state.update(desired=1, running=1,
                                cohort=['arn:aws:ecs:us-east-1:111122223333:task/cluster/old'])
        create = self.records.create
        def tick(key, raw):
            create(key, raw)
            if key.endswith('/plan'): self.world.time += 1
        self.records.create = tick
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.stages(), ['register', 'drain', 'attach', 'start', 'e3', 'switch', 'candidate', 'cleanup'])

    def test_preparation_guard_applies_to_prod(self):
        for mode in ('routing', 'revoked'):
            with self.subTest(mode=mode):
                self.f, self.auth, self.records, self.world, self.process, self.core, self.raw = setup('promote-prod')
                def change():
                    if mode == 'routing': self.world.state['normal_target'] = self.world.state['candidate_target']
                    else: self.f.e['state'] = 'REVOKED'
                self.after_plan('start', change)
                self.stopped_before('start')

    def proofs(self):
        return {key: raw for key, raw in self.records.data.items() if '/activations/' in key}

    def test_activation_retry_advancing_clock_and_exact_switch_binding(self):
        self.records.fail = '/switch/plan'
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        earlier = copy.deepcopy(self.proofs())
        self.assertEqual(len(earlier), 1)
        self.assertNotIn('switch', self.stages())
        self.records.fail = None
        self.world.time += 1
        receipt = self.run_delivery()
        self.assertEqual(receipt['status'], 'SUCCESS')
        self.assertEqual(len(self.proofs()), 2)
        for key, raw in earlier.items(): self.assertEqual(self.records.data[key], raw)
        plan = a.decode(self.records.data['dev/' + OP + '/switch/plan'])
        digest = a.sha(a.canonical(receipt['activation']))
        self.assertEqual(plan['activation_sha256'], digest)
        self.assertEqual(receipt['activation_sha256'], digest)
        self.assertEqual(self.records.data['dev/' + OP + '/activations/' + digest], a.canonical(receipt['activation']))
        self.assertEqual(self.stages().count('start'), 1)
        self.assertEqual(self.stages().count('switch'), 1)
        self.assertEqual(self.stages().count('e3'), 2)

    def test_duplicate_exact_activation_proof_is_idempotent(self):
        self.records.fail = '/switch/plan'
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        first = copy.deepcopy(self.proofs())
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        self.assertEqual(self.proofs(), first)
        self.records.fail = None
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.proofs(), first)

    def test_activation_reference_rejects_wrong_canonical_bytes(self):
        self.records.fail = '/switch/plan'
        self.run_delivery()
        key, raw = next(iter(self.proofs().items()))
        proof = a.decode(raw); proof['operation_id'] = NEXT
        self.records.data[key] = a.canonical(proof)  # Hostile protected-port response.
        op = self.core.read(OP + '/intent')
        with self.assertRaises(a.Rejected): self.core.activation(op, key.rsplit('/', 1)[1])

    def test_wrong_operation_revision_cohort_release_proof_cannot_switch(self):
        for field in ('operation', 'revision', 'cohort', 'intent', 'environment', 'service'):
            with self.subTest(field=field):
                self.setUp()
                effect = self.core.effect
                def substitute(op, stage, request, mutate=True, **kwargs):
                    if stage == 'switch':
                        good = self.core.activation(op, kwargs['activation_sha256'])
                        bad = copy.deepcopy(good)
                        if field == 'operation': bad['operation_id'] = NEXT
                        elif field == 'revision': bad['registration']['task_definition_arn'] += '8'
                        elif field == 'cohort': bad['e3']['context']['cohort'] = []
                        elif field == 'intent': bad['intent_sha256'] = '0' * 64
                        elif field == 'environment': bad['environment'] = 'prod'
                        else: bad['e3']['context']['service'] = 'foreign-service'
                        digest = a.sha(a.canonical(bad))
                        self.core.put(self.core.activation_key(op, digest), bad)
                        kwargs['activation_sha256'] = digest
                    return effect(op, stage, request, mutate, **kwargs)
                self.core.effect = substitute
                self.stopped_before('switch')

    def test_switch_retry_retains_selected_proof(self):
        self.world.on_mutation = lambda w, s: w.hidden.add(s) if s == 'switch' else None
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        plan = self.records.data['dev/' + OP + '/switch/plan']
        proofs = copy.deepcopy(self.proofs())
        self.world.hidden.clear(); self.world.on_mutation = None; self.world.time += 1
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.records.data['dev/' + OP + '/switch/plan'], plan)
        self.assertEqual(self.proofs(), proofs)
        self.assertEqual(self.stages().count('switch'), 1)
        self.assertEqual(self.stages().count('e3'), 1)

    def bad_effect(self, stage, transform=lambda _: {'state': 'UNKNOWN'}):
        original = self.world.effect
        def observe(token, deadline):
            value = original(token, deadline)
            if token.endswith('/' + stage) and stage in self.stages(): return transform(value)
            return value
        self.world.effect = observe
        return original

    def test_malformed_start_effect_is_uncertain_and_retained(self):
        self.bad_effect('start')
        result = self.run_delivery()
        self.assertEqual(result['status'], 'UNCERTAIN')
        self.assertEqual(self.world.state['running'], 2)
        self.assertIn('dev/' + OP + '/start/plan', self.records.data)
        self.assertNotIn('dev/' + OP + '/start/observed', self.records.data)
        self.assertNotIn('e3', self.stages())
        outcomes = [a.decode(v) for k, v in self.records.data.items() if '/outcomes/' in k]
        self.assertEqual([v['status'] for v in outcomes], ['UNCERTAIN'])

    def test_malformed_start_retry_reconciles_without_repeating(self):
        original = self.bad_effect('start')
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        plan = self.records.data['dev/' + OP + '/start/plan']
        self.world.effect = original; self.world.time += 1
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('start'), 1)
        self.assertEqual(self.records.data['dev/' + OP + '/start/plan'], plan)

    def test_unresolved_start_retry_never_repeats_or_continues(self):
        self.bad_effect('start')
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        calls = copy.deepcopy(self.world.calls)
        for _ in range(2):
            self.world.time += 1
            self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
            self.assertEqual(self.world.calls, calls)

    def test_malformed_switch_effect_and_reconciliation(self):
        original = self.bad_effect('switch')
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        self.assertEqual(self.world.state['normal_target'], self.world.state['candidate_target'])
        self.assertNotIn('candidate', self.stages())
        self.assertNotIn('dev/' + OP + '/success', self.records.data)
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        self.assertEqual(self.stages().count('switch'), 1)
        self.world.effect = original
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('switch'), 1)

    def test_all_mutations_unverifiable_effects_are_uncertain(self):
        for stage in ('register', 'drain', 'attach', 'start', 'switch', 'candidate', 'cleanup'):
            for kind in ('missing', 'token', 'hash', 'result', 'unavailable'):
                with self.subTest(stage=stage, kind=kind):
                    self.setUp()
                    def corrupt(value):
                        if kind == 'missing': return {'state': 'UNKNOWN'}
                        if kind == 'unavailable': raise OSError('observation unavailable')
                        if kind == 'token': value['token'] = 'foreign'
                        elif kind == 'hash': value['request_sha256'] = '0' * 64
                        else: value['result'] = {}
                        return value
                    original = self.bad_effect(stage, corrupt)
                    self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
                    calls = copy.deepcopy(self.world.calls)
                    self.assertEqual(self.stages()[-1], stage)
                    self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
                    self.assertEqual(self.world.calls, calls)
                    self.world.effect = original
                    self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
                    self.assertEqual(self.stages().count(stage), 1)

    def test_post_call_evidence_storage_error_is_uncertain(self):
        read = self.records.read
        def unavailable(key):
            if key.endswith('/start/observed'): raise OSError('unavailable')
            return read(key)
        # Fail only after the mutation, not the earlier completed-stage lookup.
        self.world.on_mutation = lambda w, s: setattr(self.records, 'read', unavailable) if s == 'start' else None
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        self.assertEqual(self.world.state['running'], 2)
        self.assertNotIn('e3', self.stages())
        calls = copy.deepcopy(self.world.calls)
        # Independent APPLIED readback can repair the unavailable original slot.
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('start'), 1)
        self.records.read = read; self.world.on_mutation = None
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.stages().count('start'), 1)

    def test_precall_invalid_effect_without_plan_is_failure(self):
        self.world.effect = lambda token, deadline: {'state': 'UNKNOWN'}
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.world.calls, [])


class CorrectionMutants(unittest.TestCase):
    def exercise(self, name, mutant):
        # Compilation happens outside the production catch-all; setup errors
        # cannot satisfy the expected behavioral AssertionError below.
        case = Corrections()
        case.setUp()
        if name == 'preparation':
            method, target, replacement = d.Delivery.effect, "self.guard_preparation(op, stage, request, plan['expected_state'])", 'pass'
            test = case.test_start_plan_routing_change
        elif name == 'reauthorization':
            method, target, replacement = d.Delivery.guard_preparation, 'self.current(op)', 'pass'
            test = case.test_start_plan_revocation
        elif name == 'single_slot':
            method, target, replacement = d.Delivery.activation_key, "op['operation_id'] + '/activations/' + digest", "op['operation_id'] + '/activations/single-slot'"
            test = case.test_activation_retry_advancing_clock_and_exact_switch_binding
        else:
            method, target, replacement = d.Delivery.observe_effect, "if possible: raise Uncertain('mutation effect unprovable') from None", 'if possible: raise a.Rejected() from None'
            test = case.test_malformed_start_effect_is_uncertain_and_retained
        source = textwrap.dedent(inspect.getsource(method))
        if source.count(target) != 1: raise RuntimeError('HARNESS_INVALID: mutation location')
        namespace = dict(method.__globals__)
        exec(compile(source.replace(target, replacement), '<wp4b-v2-behavioral-mutant>', 'exec'), namespace)
        if mutant:
            with patch.object(d.Delivery, method.__name__, namespace[method.__name__]): test()
        else: test()

    def test_four_behavioral_correction_mutants(self):
        for name in ('preparation', 'reauthorization', 'single_slot', 'uncertainty'):
            with self.subTest(name=name):
                self.exercise(name, False)
                with self.assertRaises(AssertionError): self.exercise(name, True)
