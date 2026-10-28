"""Disposable in-memory production mutants. Only assertion failures detect.

Compile/import/setup errors are invalid controls, never security detections.
Unchanged production executes the same behavioral oracles successfully.
"""
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import e1_contract
import workers
import exchange
import publisher
import services
import test_adapters as behavior

CASES=[
    (e1_contract,'observe',"status = found[0].get('phaseStatus')","status = 'SUCCEEDED'",'test_phase_failure_cannot_be_stdout_pass'),
    (e1_contract,'observe',"if b.get('buildStatus') == 'SUCCEEDED':","if True:",'test_terminal_worker_status_cannot_pass_mapped_phase'),
    (workers,'Workers',"request['imagePullCredentialsTypeOverride'] = 'CODEBUILD'","request['imagePullCredentialsTypeOverride'] = 'CODEBUILD'\n            request['serviceRoleOverride'] = 'controller'",'test_closed_worker_request_and_exact_probe'),
    (exchange,'Exchange',"'IfNoneMatch': '*'}, ExpiresIn=900, HttpMethod='PUT')","}, ExpiresIn=900, HttpMethod='PUT')",'test_capabilities_and_conditional_output'),
    (exchange,'Exchange',"value = self.s3.get_object(Bucket=self.bucket, Key=key, VersionId=exact)","value = self.s3.get_object(Bucket=self.bucket, Key=key)",'test_capabilities_and_conditional_output'),
    (publisher,'publish','require(identity == expected)','require(True)','test_publisher_rejects_false_digest_and_confirms_exact_retry'),
    (services,'Gateway',"closed(request, ('source_commit',))","pass # removed request closure",'test_gateway_closed_and_outer_only'),
]


class Mutation(unittest.TestCase):
    def oracle(self,test):
        result=unittest.TestResult();behavior.Adapters(test).run(result);return result

    def test_unchanged_source_control(self):
        for *_,oracle in CASES:
            result=self.oracle(oracle)
            self.assertEqual(result.testsRun,1);self.assertEqual(result.errors,[]);self.assertEqual(result.failures,[])

    def test_behavioral_mutants_detected_without_invalid_execution(self):
        for module,symbol,before,after,oracle in CASES:
            with self.subTest(module=module.__name__,oracle=oracle):
                source=Path(module.__file__).read_text();self.assertEqual(source.count(before),1)
                mutant=types.ModuleType('wp3c_mutant');mutant.__file__=module.__file__
                exec(compile(source.replace(before,after),module.__file__,'exec'),mutant.__dict__)
                with patch.object(module,symbol,getattr(mutant,symbol)):
                    result=self.oracle(oracle)
                self.assertEqual(result.testsRun,1)
                self.assertEqual(result.errors,[], 'invalid execution must not count as detection')
                self.assertTrue(result.failures,'security-significant survivor')

    def test_invalid_syntax_is_separate_control(self):
        with self.assertRaises(SyntaxError):compile('def broken(', '<invalid-control>', 'exec')
