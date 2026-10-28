"""E15-H provider-free tests; no sockets, credentials or child processes."""
import json
from pathlib import Path
import sys
import unittest
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[2]), str(HERE.parent/'authority'),
               str(HERE.parent/'security_root'), str(HERE.parent/'wp4d'),
               str(HERE.parent/'lifecycle'), str(HERE.parent/'nat'), str(HERE.parent/'nat_quiescence'),
               str(HERE.parent/'exact_destroy'), str(HERE.parent/'dev_down'),
               str(HERE.parent/'handoff'), str(HERE.parent/'operational_teardown'), str(HERE.parent/'ecs_quiescence'),
               str(HERE.parent/'combined_quiescence')]
if __name__ == '__main__':
    from hermetic import install
    install()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), 'test_*.py'))
    print(json.dumps(dict(executed=result.testsRun, failures=len(result.failures),
                         errors=len(result.errors), skipped=len(result.skipped))))
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)
