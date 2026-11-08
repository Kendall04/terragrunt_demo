"""WP4B hermetic acceptance: python -I -B scripts/tests/delivery/run.py."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts/tests/authority')]
from hermetic import install


if __name__ == '__main__':
    install()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(HERE), pattern='test_*.py'))
    print(json.dumps(dict(executed=result.testsRun, failures=len(result.failures),
                         errors=len(result.errors), skipped=len(result.skipped),
                         live='UNVERIFIED_NOT_DEPLOYED')))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)
