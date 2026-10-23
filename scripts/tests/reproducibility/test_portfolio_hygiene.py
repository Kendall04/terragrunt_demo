"""Source wiring only; never execute hosted workflows or install tools."""
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

    def test_backup_observer_paths_select_hygiene_without_gate_narrowing(self):
        for name in ('observer.py','signals.py','test_observer.py','test_local_signals.py','sql-backup-observer.service.in','sql-backup-observer.timer.in'):
            self.assertTrue(selection.classify(['operations/sql-backup/'+name])['hygiene'])

    def test_backup_observer_and_signal_suites_run_before_known_repro_blocker(self):
        source=(ROOT/'.github/workflows/ci-repo-hygiene.yml').read_text(encoding='utf-8')
        start=source.index('      - name: Validate backup observer and signal contracts')
        end=source.index('      - name:',start+1);step=source[start:end]
        self.assertLess(start,source.index('      - name: Test infrastructure and CI reproducibility'))
        self.assertLess(start,source.index('      - name: Install verified hygiene tools'))
        for name in ('test_observer.py','test_local_signals.py'):
            self.assertIn('python3 -I -B -m unittest discover -s operations/sql-backup -p '+name+' -v',step)
        for forbidden in ('pip install','npm ','npx ','systemctl','aws ','--aws','configure-aws-credentials','id-token:'):
            self.assertNotIn(forbidden,step)
        self.assertIn('set -euo pipefail',step)

if __name__=='__main__':unittest.main()
