"""V3 effect provenance, reconciliation ordering and receipt regressions."""
import copy
import inspect
import textwrap
import unittest
from unittest.mock import patch

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.tests.delivery.fixtures import setup, OP, NEXT


class F3(unittest.TestCase):
    def setUp(self):
        self.f, self.auth, self.r, self.w, self.p, self.c, self.raw = setup()

    def run_delivery(self): return self.c.run(OP, self.raw)
    def key(self, stage, suffix): return 'dev/' + OP + '/' + stage + '/' + suffix
    def calls(self, stage): return sum(s == stage for s, _ in self.w.calls)

    def uncertain(self, stage='start', applied=True):
        original = self.w.effect
        if not applied: self.w.fail.add(stage)
        def malformed(token, deadline):
            if token.endswith('/' + stage) and self.calls(stage): return {'state': 'UNKNOWN'}
            return original(token, deadline)
        self.w.effect = malformed
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        return original

    def halted(self, status='UNCERTAIN'):
        calls = copy.deepcopy(self.w.calls)
        result = self.run_delivery()
        self.assertEqual(result['status'], status)
        self.assertEqual(self.w.calls, calls)
        self.assertNotIn('dev/' + OP + '/success', self.r.data)
        return result

    def test_applied_before_revocation_rejection(self):
        self.w.effect = self.uncertain()
        self.f.e['state'] = 'REVOKED'
        self.halted('FAILURE')
        self.assertIn(self.key('start', 'reconciled'), self.r.data)
        value = a.decode(self.r.data[self.key('start', 'reconciled')])
        self.assertEqual(value['state'], 'APPLIED')
        self.assertEqual(value['result']['desiredCount'], 2)
        self.assertEqual(self.w.state['running'], 2)
        self.assertEqual(self.calls('start'), 1)

    def test_applied_before_expired_deadline_rejection(self):
        original = self.uncertain()
        self.w.time = 2801
        budgets = []
        def observe(token, deadline):
            budgets.append(deadline)
            self.assertGreater(deadline, self.w.now())
            return original(token, deadline)
        self.w.effect = observe
        self.halted('FAILURE')
        self.assertEqual(a.decode(self.r.data[self.key('start', 'reconciled')])['state'], 'APPLIED')
        self.assertEqual(budgets, [2831])
        self.assertEqual(self.c.read(OP + '/intent')['deadline'], 2800)

    def test_unknown_survives_revocation(self):
        self.uncertain()
        self.f.e['state'] = 'REVOKED'
        self.halted()

    def test_unknown_survives_expiration(self):
        self.uncertain()
        self.w.time = 2801
        self.halted()

    def test_absent_is_recorded_terminal_without_resend(self):
        self.w.effect = self.uncertain(applied=False)
        self.w.fail.clear()
        self.halted('FAILURE')
        observed = a.decode(self.r.data[self.key('start', 'reconciled')])
        self.assertEqual(observed['state'], 'ABSENT')
        self.assertIsNone(observed['result'])
        self.assertEqual(self.w.state['running'], 0)
        self.halted('FAILURE')
        self.assertEqual(self.calls('start'), 1)

    def test_corrupt_object_cannot_skip_reconciliation(self):
        self.uncertain()
        self.r.data[self.key('start', 'observed')] = a.canonical({'corrupt': True})
        self.halted()
        self.assertEqual(self.calls('e3'), 0)

    def test_wrong_effect_identity_and_result_matrix(self):
        for field in ('operation', 'environment', 'stage', 'hash', 'state', 'revision',
                      'count', 'service', 'extra', 'missing', 'type'):
            with self.subTest(field=field):
                self.setUp(); self.uncertain()
                value = copy.deepcopy(self.w.effects['dev/' + OP + '/start'])
                if field == 'operation': value['token'] = value['token'].replace(OP, NEXT)
                elif field == 'environment': value['token'] = value['token'].replace('dev/', 'prod/', 1)
                elif field == 'stage': value['token'] = value['token'].replace('/start', '/attach')
                elif field == 'hash': value['request_sha256'] = '0' * 64
                elif field == 'state': value['state'] = 'MAYBE'
                elif field == 'revision': value['result']['taskDefinition'] += '9'
                elif field == 'count': value['result']['desiredCount'] = 1
                elif field == 'service': value['result']['service'] = 'foreign'
                elif field == 'extra': value['approved'] = True
                elif field == 'missing': value.pop('request_sha256')
                else: value['result']['desiredCount'] = '2'
                self.r.data[self.key('start', 'observed')] = a.canonical(value)
                self.halted()

    def test_valid_applied_stored_observation_is_reusable(self):
        self.uncertain()
        self.r.data[self.key('start', 'observed')] = a.canonical(self.w.effects['dev/' + OP + '/start'])
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.calls('start'), 1)

    def test_valid_absent_stored_observation_is_terminal(self):
        self.uncertain(applied=False)
        self.r.data[self.key('start', 'observed')] = a.canonical(dict(
            token='dev/' + OP + '/start', state='ABSENT', result=None, request_sha256=None))
        self.halted('FAILURE')

    def test_corrupt_observation_repaired_without_overwrite(self):
        self.w.effect = self.uncertain()
        broken = a.canonical({'corrupt': True})
        self.r.data[self.key('start', 'observed')] = broken
        receipt = self.run_delivery()
        self.assertEqual(receipt['status'], 'SUCCESS')
        self.assertEqual(receipt['effects']['start']['state'], 'APPLIED')
        self.assertEqual(self.r.data[self.key('start', 'observed')], broken)
        self.assertEqual(receipt['effects']['start'], a.decode(self.r.data[self.key('start', 'reconciled')]))
        self.assertEqual(self.calls('start'), 1)

    def test_receipt_rejects_corrupt_effect_on_completed_retry(self):
        receipt = self.run_delivery()
        self.assertEqual(receipt['status'], 'SUCCESS')
        receipt['effects']['start'] = {'corrupt': True}
        self.r.data['dev/' + OP + '/success'] = a.canonical(receipt)
        calls = copy.deepcopy(self.w.calls)
        self.assertNotEqual(self.run_delivery()['status'], 'SUCCESS')
        self.assertEqual(self.w.calls, calls)

    def test_initial_intent_corruption_is_failure(self):
        create = self.r.create
        def corrupt(key, raw):
            create(key, raw)
            if key.endswith('/intent'): self.r.data[key] = b'{'
        self.r.create = corrupt
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.w.calls, [])
        self.assertFalse(any(k.endswith('/attempt') for k in self.r.data))

    def test_preparation_plan_corruption_is_failure(self):
        create = self.r.create
        def corrupt(key, raw):
            create(key, raw)
            if key.endswith('/drain/plan'): self.r.data[key] = b'{'
        self.r.create = corrupt
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.calls('drain'), 0)
        self.assertNotIn(self.key('drain', 'attempt'), self.r.data)

    def test_attempt_readback_corruption_prevents_call(self):
        create = self.r.create
        def corrupt(key, raw):
            create(key, raw)
            if key.endswith('/drain/attempt'): self.r.data[key] = b'{'
        self.r.create = corrupt
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.calls('drain'), 0)
        # Across process loss the durable ambiguous marker must fail closed.
        self.assertEqual(self.run_delivery()['status'], 'UNCERTAIN')
        self.assertEqual(self.calls('drain'), 0)

    def test_post_attempt_corruption_is_uncertain(self):
        for stage in ('start', 'switch'):
            with self.subTest(stage=stage):
                self.setUp(); self.uncertain(stage)
                self.r.data[self.key(stage, 'observed')] = b'{'
                self.halted()

    def test_attempt_persistence_window_still_has_fresh_guards(self):
        for stage in ('drain', 'attach', 'start', 'switch'):
            for change in ('routing', 'eligibility'):
                with self.subTest(stage=stage, change=change):
                    self.setUp(); create = self.r.create
                    def drift(key, raw):
                        create(key, raw)
                        if key.endswith('/' + stage + '/attempt'):
                            if change == 'routing': self.w.state['normal_target'] = 'foreign'
                            else: self.f.e['state'] = 'REVOKED'
                    self.r.create = drift
                    self.assertNotEqual(self.run_delivery()['status'], 'SUCCESS')
                    self.assertEqual(self.calls(stage), 0)

    def test_attempt_provenance_precedes_every_mutation(self):
        def observe(w, stage):
            plan = a.decode(self.r.data[self.key(stage, 'plan')])
            attempt = a.decode(self.r.data[self.key(stage, 'attempt')])
            self.assertEqual(attempt, dict(token=plan['token'], plan_sha256=a.sha(a.canonical(plan))))
        self.w.on_mutation = observe
        self.assertEqual(self.run_delivery()['status'], 'SUCCESS')

    def test_no_attempt_on_failed_plan_persistence(self):
        self.r.fail = '/register/plan'
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.w.calls, [])
        self.assertFalse(any(k.endswith('/attempt') for k in self.r.data))

    def test_plan_without_attempt_is_not_uncertainty_or_resend(self):
        self.r.fail = '/register/attempt'
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.r.fail = None
        self.assertEqual(self.run_delivery()['status'], 'FAILURE')
        self.assertEqual(self.w.calls, [])

    def test_unavailable_attempt_provenance_is_uncertain(self):
        self.uncertain()
        read = self.r.read
        def unavailable(key):
            if key.endswith('/start/attempt'): raise OSError('unavailable')
            return read(key)
        self.r.read = unavailable
        self.halted()


class RetainedOperationTests(unittest.TestCase):
    def exercise(self, stage=None, damage='object'):
        f, auth, r, w, p, c, raw = setup()
        if stage is None:
            c.accept(OP, raw)
            self.assertFalse(any(k.endswith('/attempt') for k in r.data))
        else:
            w.on_mutation = lambda world, current: world.hidden.add(current) if current == stage else None
            self.assertEqual(c.run(OP, raw)['status'], 'UNCERTAIN')
            self.assertIn('dev/' + OP + '/' + stage + '/attempt', r.data)
        key = 'dev/' + OP + '/intent'
        value = a.decode(r.data[key])
        if damage == 'object': value = {'corrupt': True}
        elif damage == 'null': value = None
        elif damage == 'list': value = []
        elif damage == 'history': value.pop('history')
        elif damage == 'nested': value['intent'].pop('service')
        r.data[key] = b'{' if damage == 'json' else a.canonical(value)
        before = copy.deepcopy(w.calls)
        reads = []
        read = r.read
        def tracked(key):
            reads.append(key)
            return read(key)
        r.read = tracked
        # No valid context can be recovered from this object. Neither fresh
        # authorization nor runtime reconciliation may reconstruct it.
        with patch.object(auth, 'authorize', side_effect=AssertionError('unexpected authorization')) as authorize, \
             patch.object(w, 'effect', side_effect=AssertionError('unexpected effect lookup')) as effect:
            result = c.run(OP, raw)
        authorize.assert_not_called(); effect.assert_not_called()
        self.assertEqual(result['status'], 'UNCERTAIN' if stage else 'FAILURE')
        self.assertTrue(any(k.endswith('/attempt') for k in reads))
        self.assertEqual(w.calls, before)
        self.assertNotIn('dev/' + OP + '/success', r.data)
        if stage:
            self.assertEqual(sum(s == stage for s, _ in w.calls), 1)
        else:
            self.assertEqual(w.calls, [])
        if stage == 'start':
            self.assertEqual(p.calls, [])
            self.assertFalse(any(s == 'switch' for s, _ in w.calls))

    def test_structure_before_attempt_is_failure(self):
        for damage in ('object', 'null', 'list'):
            with self.subTest(damage=damage): self.exercise(damage=damage)

    def test_structure_after_start_is_uncertain(self):
        for damage in ('object', 'null', 'list'):
            with self.subTest(damage=damage): self.exercise('start', damage)

    def test_structure_after_switch_is_uncertain(self):
        for damage in ('object', 'null', 'list'):
            with self.subTest(damage=damage): self.exercise('switch', damage)

    def test_missing_history_retains_attempt_classification(self):
        for stage in (None, 'start', 'switch'):
            with self.subTest(stage=stage): self.exercise(stage, 'history')

    def test_nested_intent_corruption_retains_attempt_classification(self):
        for stage in (None, 'start', 'switch'):
            with self.subTest(stage=stage): self.exercise(stage, 'nested')

    def test_invalid_json_retains_attempt_classification(self):
        for stage in (None, 'start', 'switch'):
            with self.subTest(stage=stage): self.exercise(stage, 'json')

    def test_valid_operation_retry_mismatch_remains_request_rejection(self):
        f, auth, r, w, p, c, raw = setup()
        c.accept(OP, raw)
        request = a.decode(raw); request['replicas'] = 1
        with patch.object(c, 'journal_uncertain') as classifier:
            self.assertEqual(c.run(OP, a.canonical(request))['status'], 'FAILURE')
        classifier.assert_not_called()
        self.assertEqual(w.calls, [])

    def test_structural_classification_behavioral_mutant(self):
        method = d.Delivery.retained_operation
        source = textwrap.dedent(inspect.getsource(method))
        target = 'raise JournalError(key) from None'
        if source.count(target) != 1: raise RuntimeError('HARNESS_INVALID: mutation location')
        namespace = dict(method.__globals__)
        exec(compile(source.replace(target, 'raise a.Rejected() from None'),
                     '<retained-operation-mutant>', 'exec'), namespace)
        self.exercise('start')
        with patch.object(d.Delivery, method.__name__, namespace[method.__name__]):
            with self.assertRaises(AssertionError): self.exercise('start')


class F3Mutants(unittest.TestCase):
    def test_three_behavioral_mutants(self):
        cases = (
            (d.Delivery.run, 'self.reconcile(op)', 'self.current(op)\n        self.reconcile(op)',
             'test_applied_before_revocation_rejection'),
            (d.Delivery.stored_effect, 'self.validate_effect(op, stage, value, plan[\'token\'], plan[\'request\'])',
             "return dict(value, state='APPLIED')", 'test_corrupt_object_cannot_skip_reconciliation'),
            (d.Delivery.read, 'raise JournalError(key) from None',
             "raise Uncertain('all decoding is uncertain') from None", 'test_initial_intent_corruption_is_failure'))
        for method, target, replacement, test in cases:
            with self.subTest(method=method.__name__):
                source = textwrap.dedent(inspect.getsource(method))
                if source.count(target) != 1: raise RuntimeError('HARNESS_INVALID: mutation location')
                namespace = dict(method.__globals__)
                exec(compile(source.replace(target, replacement), '<f3-behavioral-mutant>', 'exec'), namespace)
                case = F3(); case.setUp(); getattr(case, test)()
                with patch.object(d.Delivery, method.__name__, namespace[method.__name__]):
                    case = F3(); case.setUp()
                    with self.assertRaises(AssertionError): getattr(case, test)()
