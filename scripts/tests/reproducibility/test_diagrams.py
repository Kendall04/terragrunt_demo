"""Runs the offline diagram contract in the existing hygiene suite; no installs."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]


class DiagramContracts(unittest.TestCase):
    def test_offline_diagram_contracts(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Existing Node 20+ required, as in portfolio hygiene')
        result = subprocess.run([node, '--test', 'scripts/diagrams/test-diagrams.mjs'],
                                cwd=ROOT, text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
