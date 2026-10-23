"""Source wiring only; never execute hosted workflows or install Node."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('portfolio_ci_selection',ROOT/'.github/scripts/ci/select-checks.py')
selection=importlib.util.module_from_spec(spec);spec.loader.exec_module(selection)

class PortfolioHygieneTests(unittest.TestCase):
    def test_portfolio_changes_select_hygiene_without_weakening_existing_fallback(self):
        for name in ('index.html','facts.mjs','app.mjs','server.mjs','contract.mjs','test-contract.mjs'):
            self.assertTrue(selection.classify(['portfolio/'+name])['hygiene'])
        self.assertTrue(all(selection.classify(['unmapped/new-file'])[gate] for gate in selection.GATES))

    def test_hygiene_runs_portable_suite_before_optional_tool_installs(self):
        source=(ROOT/'.github/workflows/ci-repo-hygiene.yml').read_text(encoding='utf-8')
        start=source.index('      - name: Validate local portfolio contracts')
        end=source.index('      - name:',start+1)
        self.assertLess(start,source.index('      - name: Test infrastructure and CI reproducibility'))
        step=source[start:end]
        self.assertIn('node --test portfolio/test-contract.mjs',step)
        self.assertIn('Existing Node 20+ required',step)
        for install in ('npm ','npx ','setup-node','apt-get','curl '):self.assertNotIn(install,step)
        self.assertNotIn('id-token:',source)

if __name__=='__main__':unittest.main()
