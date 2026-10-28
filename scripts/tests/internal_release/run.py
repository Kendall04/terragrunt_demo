"""WP3C offline adapter and authority acceptance. Never constructs real SDK clients."""
import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'scripts/internal_release'), str(ROOT/'scripts/tests/security_root'),
               str(ROOT/'scripts/tests/authority'), str(Path(__file__).parent)]
from hermetic import install


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    install()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(Path(__file__).parent)))
    report = dict(executed=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), live='UNVERIFIED_NOT_DEPLOYED')
    if args.report:
        args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return 0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
