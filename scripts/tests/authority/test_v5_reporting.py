"""Evidence-group summaries cannot count missing or failed checks as passed."""
import io
import unittest

from run import evidence_groups


class V5ReportingTests(unittest.TestCase):
    def test_unexecuted_and_skipped_groups_are_not_passed(self):
        result = unittest.TestResult()
        groups = evidence_groups([], result)
        self.assertTrue(all(group["status"] == "NOT_PASSED" for group in groups.values()))
        test = unittest.FunctionTestCase(lambda: None)
        test.id = lambda: "test_hermetic.HermeticTests.test_review_guard"
        result.addSkip(test, "not executed")
        group = evidence_groups([test.id()], result)["hermetic_guards"]
        self.assertEqual(group["status"], "NOT_PASSED")
        self.assertEqual(group["counts"], {"executed": 1, "failures": 0, "errors": 0, "skipped": 1})

    def test_failed_subtest_is_visible_in_its_executed_group(self):
        class FailingCase(unittest.TestCase):
            def id(self):
                return "test_v5_evaluator.ResourceArnV5Tests.test_review_permutations"

            def runTest(self):
                with self.subTest(effect="Deny"):
                    self.assertEqual("UNKNOWN", "DENY")

        case = FailingCase()
        result = unittest.TextTestRunner(stream=io.StringIO()).run(case)
        group = evidence_groups([case.id()], result)["resource_arn_admission"]
        self.assertEqual(group["status"], "NOT_PASSED")
        self.assertEqual(group["counts"]["executed"], 1)
        self.assertEqual(group["counts"]["failures"], 1)


if __name__ == "__main__":
    unittest.main()
