"""Focused hermetic WP7 composed-authority and retirement regressions."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent/'security_root'), str(HERE.parent/'authority'),
                str(HERE.parent/'wp4d'), str(HERE.parent/'workflows'), str(ROOT)]


def main():
    from hermetic import install
    install()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), 'test_*.py'))
    print(json.dumps(dict(executed=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))))
    return 0 if result.wasSuccessful() and result.testsRun > 0 and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
