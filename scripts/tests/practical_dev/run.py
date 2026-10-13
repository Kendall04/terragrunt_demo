"""Provider-free production CLI/plan tests; no AWS/socket/process escape."""
import json
from pathlib import Path
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parents[2]),str(HERE.parent/'authority'),str(HERE.parent/'security_root')]
if __name__=='__main__':
    from hermetic import install
    install()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE),'test_*.py'))
    print(json.dumps(dict(executed=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped))))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)
