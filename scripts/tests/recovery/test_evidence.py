"""Shared write-ahead, provenance and no-resend evidence probes."""
import copy
import unittest
from scripts.normal_delivery import authorization as a
from scripts.tests.recovery.fixtures import application, nat, NEXT


class EvidenceTests(unittest.TestCase):
    def test_expiry_during_last_guard(self):
        c, r, records = nat()
        context = r.context
        calls = []
        def delayed(action, deadline):
            calls.append(action)
            if len(calls) == 3: r.time += 601
            return context(action, deadline)
        r.context = delayed
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_deterministic_receipt_bytes(self):
        first, *_ = application()
        second, *_ = application()
        self.assertEqual(a.canonical(first.run(NEXT, b'{}')), a.canonical(second.run(NEXT, b'{}')))

    def test_deleted_intent_not_reconstructed(self):
        c, r, records = nat()
        r.hidden.add('assign_eip')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        key = c.journal.env + '/' + NEXT + '/intent'
        del records.data[key]
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        self.assertNotIn(key, records.data)
        self.assertEqual(len(r.calls), 1)

    def test_unplanned_effect_is_not_adopted(self):
        c, r, records = nat()
        records.data[c.journal.env + '/' + NEXT + '/assign_eip/observed'] = a.canonical(dict(corrupt=True))
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_invalid_operation_never_reads_foreign_namespace(self):
        c, r, records = nat()
        records.read = lambda key: self.fail('invalid identity reached storage')
        self.assertEqual(c.run('../foreign', b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_attempt_precedes_every_call(self):
        for kind in ('emergency', 'cleanup', 'assign_eip', 'change_rt', 'disable_sdc'):
            values = application(kind, running=2) if kind in ('emergency', 'cleanup') else nat(kind)
            c, r, records = values[:3]
            mutate = r.mutate
            def checked(stage, token, request, deadline):
                plan = a.decode(records.data[token + '/plan'])
                attempt = a.decode(records.data[token + '/attempt'])
                self.assertEqual(attempt, dict(token=token, plan_sha256=a.sha(a.canonical(plan))))
                mutate(stage, token, request, deadline)
            r.mutate = checked
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')

    def test_non_authoritative_effects(self):
        for kind in ('emergency', 'cleanup', 'assign_eip', 'change_rt', 'disable_sdc'):
            for alteration in ('token', 'request_sha256', 'state', 'result', 'extra'):
                values = application(kind, running=2) if kind in ('emergency', 'cleanup') else nat(kind)
                c, r, records = values[:3]
                effect = r.effect
                def malformed(token, deadline):
                    result = effect(token, deadline)
                    result[alteration] = 'foreign'
                    return result
                r.effect = malformed
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN', (kind, alteration))
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
                self.assertEqual(len(r.calls), 1)

    def test_no_mutation_on_unpersisted_attempt(self):
        c, r, records = nat()
        records.fail = '/attempt'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_attempt_guard_known_rejection(self):
        c, r, records = nat()
        create = records.create
        def reject(key, raw):
            create(key, raw)
            if key.endswith('/attempt'): r.nat_context['observed']['instance'] = 'foreign'
        records.create = reject
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])
        # Retained attempt is no longer resent even if current context recovers.
        r.nat_context['observed']['instance'] = 'i-member'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_unknown_before_revocation_or_deadline(self):
        for attack in ('revoked', 'expired'):
            c, r, records, facts = application()
            r.hidden.add('scale')
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            if attack == 'revoked': facts.e['state'] = 'REVOKED'
            else: r.time += 601
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            self.assertEqual(len(r.calls), 1)
            r.hidden.clear()
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(len(r.calls), 1)
            key = c.journal.env + '/' + NEXT + '/scale/observed'
            self.assertEqual(a.decode(records.data[key])['state'], 'APPLIED')

    def test_damaged_old_effect_never_enters_receipt(self):
        c, r, records, facts = application()
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
        key = c.journal.env + '/' + NEXT + '/scale/observed'
        records.data[key] = b'{"corrupt":true}'
        result = c.run(NEXT, b'{}')
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['effects']['scale']['state'], 'APPLIED')
        self.assertEqual(len(r.calls), 4)
        self.assertEqual(records.data[key], b'{"corrupt":true}')

    def test_missing_retained_field(self):
        c, r, records, facts = application()
        r.hidden.add('switch')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        key = c.journal.env + '/' + NEXT + '/intent'
        retained = a.decode(records.data[key]); del retained['body']['domain']
        records.data[key] = a.canonical(retained)
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        self.assertEqual(len(r.calls), 2)

    def test_stale_foreign_observation(self):
        for field, value in (('observed_at', 1), ('operation', 'foreign'), ('environment', 'prod')):
            c, r, records, facts = application()
            observe = r.observe
            def invalid(operation, deadline):
                s = observe(operation, deadline); s[field] = value; return s
            r.observe = invalid
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_immutable_retry_and_no_foreign_attempt(self):
        c, r, records = nat()
        records.data['prod/recovery/assign_eip/' + NEXT + '/attempt'] = b'{}'
        records.data[c.journal.env + '/' + NEXT + '/intent'] = b'{"corrupt":true}'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])
