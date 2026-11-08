"""E13 hermetic contracts; no AWS, command execution or installation."""
from pathlib import Path
import sys
import unittest
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "security_root"), str(HERE.parent / "authority"),
               str(HERE.parent / "wp4d"), str(HERE.parents[2])]
if __name__ == "__main__":
    from hermetic import install
    install()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), "test_*.py"))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
