"""E2-R interruption/fencing evidence; hermetic, no administrative AWS action."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2]), str(HERE.parent / "authority"),
               str(HERE.parent / "security_root"), str(HERE.parent / "wp4d")]
from hermetic import install
install()
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py"))
print(json.dumps(dict(executed=result.testsRun, failures=len(result.failures),
                      errors=len(result.errors), skipped=len(result.skipped))))
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
