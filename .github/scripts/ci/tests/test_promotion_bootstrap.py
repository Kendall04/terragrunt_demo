"""The default-branch evaluator install must select and execute its own tests."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('bootstrap_selection', ROOT / '.github/scripts/ci/select-checks.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class PromotionBootstrapCI(unittest.TestCase):
    def test_evaluator_paths_select_acceptance_and_hygiene(self):
        for name in ('api-promotion.yml', 'api-evaluate.yml'):
            selection = selector.classify(['.github/workflows/' + name])
            self.assertTrue(selection['acceptance'] and selection['hygiene'])
        for path in ('scripts/api_delivery/receipts.py', 'scripts/tests/api_promotion/test_pr_target_history.py'):
            selection = selector.classify([path])
            self.assertTrue(selection['acceptance'] and selection['hygiene'])

    def test_hygiene_runs_normal_and_optimized_evaluator_regressions(self):
        text = (ROOT / '.github/workflows/ci-repo-hygiene.yml').read_text()
        self.assertIn('python3 -I -B -m unittest discover -s scripts/tests/api_promotion -v', text)
        self.assertIn('python3 -I -O -B -m unittest discover -s scripts/tests/api_promotion -v', text)
        for forbidden in ('id-token:', 'configure-aws-credentials', 'role-to-assume', 'environment:'):
            self.assertNotIn(forbidden, text)
