"""WP3B hermetic repository acceptance; no AWS, application launch or deployment."""
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
    errors=verify(ROOT)
    validate_repository(ROOT)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE)))
    from test_sensitivity import EVIDENCE
    from test_supervisor import Tests
    good=result.wasSuccessful() and result.testsRun>0 and not result.skipped and not errors
    report={'result':'WP3B_PASS' if good else 'WP3B_FAIL',
            'counts':dict(executed=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
            'inventory_errors':errors,'mutation_evidence':EVIDENCE,'operational':False,
            'live_build_supervision':'UNVERIFIED_NOT_PERFORMED','live_image_publication':'UNVERIFIED_NOT_PERFORMED'}
    report['breakdown']={
        'behavioral_cases':unittest.defaultTestLoader.loadTestsFromTestCase(Tests).countTestCases(),
        'detected':[k for k,v in EVIDENCE.items() if v['status']=='DETECTED'],
        'redundant':[k for k,v in EVIDENCE.items() if v.get('category')=='REDUNDANT'],
        'security_significant_survivors':[k for k,v in EVIDENCE.items() if v.get('category')=='SECURITY' and v['status']=='SURVIVED'],
        'invalid_security_mutants':[k for k,v in EVIDENCE.items() if v.get('category')=='SECURITY' and v['status']=='HARNESS_INVALID'],
        'invalid_controls':[k for k,v in EVIDENCE.items() if k in ('syntax','import','setup','unrelated','type')],
    }
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2));return 0 if good else 1


if __name__=='__main__':raise SystemExit(main())
