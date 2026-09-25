"""Hermetic WP3A production-path acceptance. No deployment or execution."""
import argparse
import json
from pathlib import Path
import sys
import unittest
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'scripts/tests/authority'),str(ROOT/'scripts/tests/security_root')]
from hermetic import install

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path);args=parser.parse_args()
    install()
    from inventory import verify
    from model import validate_repository
    errors=verify(ROOT);validate_repository(ROOT)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE)))
    good=result.wasSuccessful() and result.testsRun>0 and not result.skipped and not errors
    report={'result':'WP3A_PASS' if good else 'WP3A_FAIL','counts':{'executed':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)},'inventory_errors':errors,'live_qualification':'UNVERIFIED_NOT_PERFORMED','operational':False}
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0 if good else 1
if __name__=='__main__':raise SystemExit(main())
