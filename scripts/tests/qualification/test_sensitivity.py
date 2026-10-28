"""Small in-memory mutations; only reached outcome assertions prove detection."""
import types
import unittest
import test_finalizer as acceptance

EVIDENCE = {}


def production_source():
    return acceptance.Path(acceptance.f.__file__).read_text(encoding='utf-8')


def evaluate(source, names=None, expected='reject', case=acceptance.Tests):
    report = {'status': 'HARNESS_INVALID', 'executed': 0, 'reached': [],
              'outcome_failures': [], 'failures': 0, 'errors': 0}
    try:
        module = types.ModuleType('disposable_finalizer')
        module.__file__ = acceptance.f.__file__
        exec(compile(source, '<disposable-finalizer-mutation>', 'exec'), module.__dict__)
        class BoundTests(case):
            finalizer = module

            def setUp(self):
                self.behavioral_ready = False
                super().setUp()
                self.behavioral_ready = True

            def tearDown(self):
                self.behavioral_ready = False
                super().tearDown()

        bound = BoundTests
        names = names if names is not None else unittest.defaultTestLoader.getTestCaseNames(bound)
        cases = [bound(name) for name in names]
    except Exception:
        report['reason'] = 'LOAD_OR_CONSTRUCTION_FAILURE'
        return report

    class Outcomes(unittest.TestResult):
        def addFailure(self, test, err):
            super().addFailure(test, err)
            if (type(err[1]) is acceptance.QualificationExpectation
                    and err[1].expected == expected
                    and getattr(test, 'behavioral_ready', False)
                    and getattr(test, 'fixture_ready', False)
                    and getattr(test, 'finalize_calls', 0) > 0):
                report['outcome_failures'].append(test._testMethodName)

    result = Outcomes()
    unittest.TestSuite(cases).run(result)
    report.update(executed=result.testsRun, failures=len(result.failures), errors=len(result.errors))
    report['reached'] = [test._testMethodName for test in cases
                         if getattr(test, 'fixture_ready', False)
                         and getattr(test, 'finalize_calls', 0) > 0]
    if (not cases or result.errors or result.skipped or result.unexpectedSuccesses
            or result.expectedFailures or len(report['outcome_failures']) != len(result.failures)):
        report['reason'] = 'SETUP_OR_UNRELATED_FAILURE'
    elif result.failures:
        report['status'] = 'MUTATION_DETECTED'
    else:
        report['status'] = 'MUTANT_SURVIVED'
    return report


class Sensitivity(unittest.TestCase):
    def check(self, label, old, new, names, expected='reject', redundant=False):
        source = production_source()
        self.assertEqual(source.count(old), 1)
        report = evaluate(source.replace(old, new), names, expected)
        EVIDENCE[label] = {**report, 'category': 'redundant' if redundant else 'security'}
        self.assertEqual(report['status'], 'MUTANT_SURVIVED' if redundant else 'MUTATION_DETECTED', report)
        self.assertEqual(report['executed'], len(names))
        self.assertEqual(report['errors'], 0)
        self.assertEqual(report['reached'], names)
        self.assertEqual(report['outcome_failures'], [] if redundant else names)

    def test_unchanged_source_survives_full_behavioral_suite(self):
        source = production_source()
        report = evaluate(source.replace('import copy', 'import copy'))
        EVIDENCE['unchanged_source'] = {**report, 'category': 'control'}
        self.assertEqual(report['status'], 'MUTANT_SURVIVED', report)
        self.assertEqual(report['executed'], unittest.defaultTestLoader.loadTestsFromTestCase(acceptance.Tests).countTestCases())
        self.assertEqual(report['failures'], 0)
        self.assertEqual(report['errors'], 0)

    def test_mutant_compatible_ports(self):
        module = types.ModuleType('fixture_control')
        module.__file__ = acceptance.f.__file__
        exec(compile(production_source(), '<fixture-control>', 'exec'), module.__dict__)
        evidence, store = acceptance.ports(module)
        self.assertIsInstance(evidence, module.Evidence)
        self.assertIsInstance(store, module.Qualifications)
        self.assertNotIsInstance(evidence, acceptance.f.Evidence)
        core = module.Finalizer('111122223333', 'us-east-1', evidence, store)
        self.assertEqual(core.finalize({'operation_id': acceptance.OP})['checks'],
                         {k: 'PASS' for k in module.REQUIRED_CHECKS})

    def test_syntax_failure_is_invalid(self):
        report = evaluate('def broken(')
        EVIDENCE['syntax_failure'] = {**report, 'category': 'invalid_control'}
        self.assertEqual(report['status'], 'HARNESS_INVALID')
        self.assertEqual(report['executed'], 0)

    def test_wrong_type_setup_is_invalid(self):
        class WrongPorts(acceptance.Tests):
            def setUp(self):
                evidence, store = acceptance.ports(acceptance.f)
                self.finalizer.Finalizer('111122223333', 'us-east-1', evidence, store)
        report = evaluate(production_source(), ['test_positive_closed_contracts'], case=WrongPorts)
        EVIDENCE['wrong_type_setup'] = {**report, 'category': 'invalid_control'}
        self.assertEqual(report['status'], 'HARNESS_INVALID')
        self.assertEqual(report['errors'], 1)
        self.assertEqual(report['reached'], [])
        self.assertEqual(report['outcome_failures'], [])

    def test_setup_assertion_is_invalid(self):
        class BrokenSetup(acceptance.Tests):
            def setUp(self):
                super().setUp()
                self.run_finalizer()
                raise acceptance.QualificationExpectation('reject')
        report = evaluate(production_source(), ['test_positive_closed_contracts'], case=BrokenSetup)
        EVIDENCE['setup_assertion'] = {**report, 'category': 'invalid_control'}
        self.assertEqual(report['status'], 'HARNESS_INVALID')
        self.assertEqual(report['outcome_failures'], [])

    def test_unrelated_assertion_is_invalid(self):
        class Unrelated(acceptance.Tests):
            def test_unrelated(self):
                self.run_finalizer()
                self.fail('unrelated assertion after finalization')
        report = evaluate(production_source(), ['test_unrelated'], case=Unrelated)
        EVIDENCE['unrelated_assertion'] = {**report, 'category': 'invalid_control'}
        self.assertEqual(report['status'], 'HARNESS_INVALID')
        self.assertEqual(report['reached'], ['test_unrelated'])
        self.assertEqual(report['outcome_failures'], [])

    def test_noop_publication_cannot_hide(self):
        self.check('persisted_bytes', 'require(self.qualifications.read(key) == raw)', 'pass',
                   ['test_noop_write_is_not_success'])

    def test_source_binding_removal_detected(self):
        self.check('source', 'require(record[key] == op[key])',
                   "require(key == 'source_commit' or record[key] == op[key])",
                   ['test_mutation_wrong_source', 'test_mutation_result_wrong_source'])

    def test_build_binding_removal_detected(self):
        self.check('build_id', 'require(record[key] == op[key])',
                   "require(key == 'build_id' or record[key] == op[key])",
                   ['test_mutation_wrong_build', 'test_mutation_orphan_result'])

    def test_operation_binding_removal_detected(self):
        self.check('operation', 'require(record[key] == op[key])',
                   "require(key == 'operation_id' or record[key] == op[key])",
                   ['test_mutation_wrong_operation', 'test_mutation_actual_wrong_operation'])

    def test_image_binding_removal_detected(self):
        self.check('image', "require(candidate['image']['digest'] == result['image_digest'])", 'pass',
                   ['test_candidate_image_substitution'])

    def test_manifest_version_binding_removal_detected(self):
        self.check('manifest_version', 'require(receipt[key] == manifest[key])',
                   "require(key == 'version_id' or receipt[key] == manifest[key])",
                   ['test_mutation_wrong_version'])

    def test_checksum_removal_detected(self):
        self.check('checksum', "require(type(receipt['bytes']) is bytes and checksum(receipt['bytes']) == manifest['sha256'])",
                   "require(type(receipt['bytes']) is bytes)", ['test_mutation_wrong_checksum'])

    def test_all_pass_removal_detected_for_every_check_and_state(self):
        names = ['test_paired_' + check + '_' + state.lower()
                 for check in acceptance.f.REQUIRED_CHECKS
                 for state in acceptance.PAIRED_STATES if state not in ('missing', 'null')]
        self.check('all_pass', "require(all(record['checks'][k] == 'PASS' for k in REQUIRED_CHECKS))",
                   'pass', names)

    def test_deny_all_detected(self):
        self.check('deny_all', "validate('wakeup', wakeup)", 'require(False)',
                   ['test_positive_closed_contracts'], expected='qualify')

    def test_project_equality_redundant_with_fixed_schema(self):
        self.check('project_equality', 'require(record[key] == op[key])',
                   "require(key == 'project' or record[key] == op[key])",
                   ['test_mutation_wrong_project', 'test_positive_closed_contracts'], redundant=True)

    def test_required_fields_redundant_with_check_indexing(self):
        # Isolate finalizer indexing, without requiring the removed schema guard.
        self.check('required_fields', "require(set(schema.get('required', [])) <= set(value))",
                   'pass', ['test_missing_check', 'test_positive_closed_contracts'], redundant=True)
