"""Provider-free WP4D authority, packaging and adapter tests."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "security_root"), str(HERE.parents[2]),
               str(HERE.parent / "authority")]


def main():
    from hermetic import install
    install()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py"))
    print(json.dumps({"executed": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "skipped": len(result.skipped)}, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
