"""Finite behavioral bypasses. Only assertion failures kill a mutant.

Mutated modules execute in memory; repository sources and imports remain intact.
The same selected production-path tests must first pass without modification.
"""
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts.recovery import application as app, nat, journal
from scripts.normal_delivery import authorization as auth
from scripts.tests.recovery import test_recovery as cases


def changed_method(module, cls, method, old, new):
    source = Path(module.__file__).read_text(encoding='utf-8')
    if source.count(old) != 1: raise AssertionError('mutation anchor must be unique')
    namespace = dict(__name__=module.__name__, __file__=module.__file__)
    exec(compile(source.replace(old, new), module.__file__, 'exec'), namespace)
    return getattr(namespace[cls], method)


CASES = [
    ('revoked', auth, 'Authorizer', 'authorize',
     "record['state'] == 'ELIGIBLE'", "record['state'] in ('ELIGIBLE', 'REVOKED')", cases.EmergencyTests, 'test_revoked'),
    ('history', app, 'History', 'success',
     "        d.identity(operation)\n        op =", "        return self.read(operation + '/success', True)\n        op =", cases.EmergencyTests, 'test_history_required'),
    ('revision', app, 'Emergency', 'candidate',
     "        a.exact(svc['revision'], value['revision'], 'recoverable revision still selected')", "        pass", cases.EmergencyTests, 'test_other_selected_revision'),
    ('health', app, 'Emergency', 'candidate', '        if healthy:', '        if False:', cases.EmergencyTests, 'test_health'),
    ('blank-target-id', app, 'Emergency', 'candidate',
     '                a.require(bool(canonical_id))', '                pass',
     cases.EmergencyTests, 'test_blank_target_identity'),
    ('final-authorization', app, 'Emergency', 'guard',
     "    def guard(self, op, stage, effects):\n        value = op['domain']", "    def guard(self, op, stage, effects):\n        return\n        value = op['domain']", cases.EmergencyTests, 'test_revoked_after_scale'),
    ('routing-substitution', app, 'Emergency', 'actions',
     "actions['switch'] = dict(listener=m['listener'], target=m['target_group'])",
     "actions['switch'] = dict(listener=m['listener'], target='foreign')", cases.EmergencyTests, 'test_zero_capacity'),
    ('active-cleanup', app, 'Cleanup', 'actions',
     "        initial = value['initial']['services'][value['color']]",
     "        m = value['config']['colors'][value['active']]\n        initial = value['initial']['services'][value['color']]", cases.CleanupTests, 'test_positive'),
    ('ambiguous-routing', app, 'Application', 'observe',
     "        s = self.runtime.observe(operation, now + 30)",
     "        s = self.runtime.observe(operation, now + 30)\n        s['normal_targets'] = s['normal_targets'][:1]", cases.CleanupTests, 'test_both_active'),
    ('foreign-cleanup', app, 'Application', 'observe',
     "            for key in ('cluster', 'service'): a.exact(svc[key], config['colors'][color][key], key)",
     "            pass", cases.CleanupTests, 'test_foreign_resources'),
    ('nat-membership', nat, 'Nat', 'context',
     "        for key in MEMBERSHIP: a.exact(o[key], m[key], 'observed.' + key)", "        pass", cases.NatTests, 'test_foreign_membership'),
    ('tag-only', nat, 'Nat', 'context',
     "        m = value['membership']\n        a.keys(m, MEMBERSHIP)", "        m = {k: value['observed'][k] for k in MEMBERSHIP}\n        a.keys(m, MEMBERSHIP)", cases.NatTests, 'test_tag_only'),
    ('foreign-eip', nat, 'Nat', 'actions',
     "AllocationId=m['eip']", "AllocationId='foreign'", cases.NatTests, 'test_exact_requests'),
]


class MutationTests(unittest.TestCase):
    def test_behavioral_mutants(self):
        for name, module, cls, method, old, new, test_class, test in CASES:
            with self.subTest(mutant=name):
                control = unittest.TestResult()
                test_class(test).run(control)
                self.assertTrue(control.wasSuccessful(), name + ' control failed')
                mutant = changed_method(module, cls, method, old, new)
                result = unittest.TestResult()
                with patch.object(getattr(module, cls), method, mutant):
                    test_class(test).run(result)
                self.assertFalse(result.errors, name + ' setup/runtime error does not count')
                self.assertTrue(result.failures, name + ' survived')

    def test_unknown_cannot_be_success_mutant(self):
        # Same shared effect boundary must protect all three recovery domains.
        old = "            if value['state'] == 'UNKNOWN': raise d.Uncertain()"
        new = "            if value['state'] == 'UNKNOWN': value = dict(token=plan['token'], request_sha256=a.sha(a.canonical(plan['request'])), state='APPLIED', result=plan['request'])"
        mutant = changed_method(journal, 'Journal', 'effect', old, new)
        for cls, name in ((cases.EmergencyTests, 'test_ambiguous_retry'), (cases.CleanupTests, 'test_unknown'), (cases.NatTests, 'test_retry')):
            control = unittest.TestResult(); cls(name).run(control)
            self.assertTrue(control.wasSuccessful())
            result = unittest.TestResult()
            with patch.object(journal.Journal, 'effect', mutant): cls(name).run(result)
            self.assertFalse(result.errors)
            self.assertTrue(result.failures)
