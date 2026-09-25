"""Disposable source mutations: reached behavior assertions only, never setup kills."""
import types
import unittest
import test_supervisor as a

EVIDENCE = {}


def source():
    return a.Path(a.s.__file__).read_text(encoding='utf-8')


def evaluate(text, names=None, base=a.Tests):
    report = dict(status='HARNESS_INVALID', executed=0, failures=0, errors=0, outcomes=[])
    try:
        module = types.ModuleType('disposable_supervisor');module.__file__=a.s.__file__
        exec(compile(text,'<mutant>','exec'),module.__dict__)
        class Bound(base):
            def setUp(self):
                self.ready=False;self.module=module;super().setUp();self.ready=True
        names=names or unittest.defaultTestLoader.getTestCaseNames(Bound)
        cases=[Bound(name) for name in names]
    except Exception:
        return report
    class Result(unittest.TestResult):
        def addFailure(self,test,err):
            super().addFailure(test,err)
            if type(err[1]) is a.Behavior and getattr(test,'ready',False) and getattr(test,'invoked',0)>0:
                report['outcomes'].append(test._testMethodName)
    result=Result();unittest.TestSuite(cases).run(result)
    report.update(executed=result.testsRun,failures=len(result.failures),errors=len(result.errors))
    if not result.errors and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses and len(report['outcomes'])==len(result.failures):
        report['status']='DETECTED' if result.failures else 'SURVIVED'
    return report


MUTATIONS = {
 'full_environment': ("return env", "return dict(__import__('os').environ)", 'test_closed_environment'),
 'credential_reintroduced': ("return env", "env['AWS_ACCESS_KEY_ID'] = __import__('os').environ.get('AWS_ACCESS_KEY_ID', ''); return env", 'test_closed_environment'),
 'caller_commands': ("contract.validate('wakeup', wakeup)", "wakeup = {'operation_id': wakeup['operation_id']}", 'test_override_commands'),
 'caller_environment': ("contract.validate('wakeup', wakeup)", "wakeup = {'operation_id': wakeup['operation_id']}", 'test_override_environment'),
 'caller_repository': ("contract.validate('wakeup', wakeup)", "wakeup = {'operation_id': wakeup['operation_id']}", 'test_override_repository'),
 'source_identity': ("require(acquired['repository'] == op['repository'] and acquired['commit'] == op['source_commit'])", 'pass', 'test_source_mismatch'),
 'repository_identity': ("require(acquired['repository'] == op['repository'] and acquired['commit'] == op['source_commit'])", 'pass', 'test_source_repository'),
 'workspace': ("require(acquired['workspace'] == workspace and str(PurePosixPath(workspace)) == workspace)", 'pass', 'test_workspace_outside'),
 'image_context': ("workspace + '/demo-api', workspace + '/demo-api/Dockerfile'", "'/outside', '/outside/Dockerfile'", 'test_image_context'),
 'command_substitution': ("'dotnet', 'restore', './demo-api/terragrunt-demo.sln'", "'dotnet', 'restore', './attacker.sln'", 'test_positive_fixed_pipeline'),
 'application_digest': ("uri = registry + '/' + self.repository + '@' + image['digest']", "image['digest'] = self.payload.claim; uri = registry + '/' + self.repository + '@' + image['digest']", 'test_digest_from_trusted_publisher'),
 'tag_only': ("require(type(image['digest']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image['digest']) is not None)", 'pass', 'test_tag_only'),
 'tag_promoted_to_fake_digest': ("require(type(image['digest']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image['digest']) is not None)", "image['digest'] = 'sha256:' + '0' * 64", 'test_tag_only'),
 'image_repository': ("require(image['registry'] == registry and image['repository'] == self.repository)", 'pass', 'test_image_repository'),
 'caller_manifest_version': ("contract.validate('wakeup', wakeup)", "wakeup = {'operation_id': wakeup['operation_id']}", 'test_override_version_id'),
 'manifest_readback': ("self.manifests.read_exact(self.bucket, key, receipt['version_id'])", "dict(receipt, bytes=raw, sha256=contract.checksum(raw))", 'test_manifest_read_failure'),
 'manifest_checksum': ("require(persisted['sha256'] == contract.checksum(persisted['bytes']) == manifest['sha256'])", 'pass', 'test_manifest_checksum'),
 'failed_stage_pass': ("return 'PASS' if success else 'FAIL'", "return 'PASS'", 'test_restore_failure'),
 'fabricated_result': ("return self.terminal(attempt, common, source, checks, stage)", "return dict(common, schema='E1_SUPERVISED_RESULT_V1', state='SUCCEEDED', checks=dict.fromkeys(checks,'PASS'), image_digest='sha256:'+'0'*64, manifest={})", 'test_source_failure'),
 'application_terminal_writer': ("contract._validate(value, schema, contract.CONTRACT)", 'pass', 'test_application_writer'),
 'untrusted_stdout': ("'runtime_contract': contract.RUNTIME, 'manifest': manifest}", "'runtime_contract': contract.RUNTIME, 'manifest': manifest, 'stdout': 'untrusted'}", 'test_positive_fixed_pipeline'),
}


class Sensitivity(unittest.TestCase):
    def test_unchanged(self):
        r=evaluate(source());EVIDENCE['unchanged']=r
        self.assertEqual(r['status'],'SURVIVED',r);self.assertEqual(r['errors'],0)
        self.assertEqual(r['executed'],unittest.defaultTestLoader.loadTestsFromTestCase(a.Tests).countTestCases())
    def test_invalid_controls(self):
        class BadSetup(a.Tests):
            def setUp(self):raise a.Behavior('setup')
        class Unrelated(a.Tests):
            def test_unrelated(self):self.run_core();self.fail('unrelated')
        class WrongPorts(a.Tests):
            def setUp(self):self.module.Supervisor(*a.fixture(a.s))
        for label,r in [('syntax',evaluate('def broken(')),('import',evaluate('raise ImportError()')),
                        ('setup',evaluate(source(),['test_positive_fixed_pipeline'],BadSetup)),
                        ('unrelated',evaluate(source(),['test_unrelated'],Unrelated)),
                        ('type',evaluate(source(),['test_positive_fixed_pipeline'],WrongPorts))]:
            EVIDENCE[label]=r;self.assertEqual(r['status'],'HARNESS_INVALID');self.assertEqual(r['outcomes'],[])


def mutation(label,old,new,name):
    def test(self):
        text=source();self.assertEqual(text.count(old),1)
        r=evaluate(text.replace(old,new),[name]);EVIDENCE[label]=r
        r['category']='SECURITY'
        # The independent candidate schema still rejects tag-only publication.
        if label=='tag_only':
            r['category']='REDUNDANT'
            self.assertEqual(r['status'],'SURVIVED');self.assertEqual(r['errors'],0)
        else:
            self.assertEqual(r['status'],'DETECTED',r);self.assertEqual(r['outcomes'],[name]);self.assertEqual(r['errors'],0)
    return test
for label,args in MUTATIONS.items():setattr(Sensitivity,'test_mutation_'+label,mutation(label,*args))
