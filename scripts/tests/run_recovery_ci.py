#!/usr/bin/env python3
"""Explicit offline recovery CI: real discovery, isolated suites, zero tolerated skips.

No dependency installation, SDK/cloud invocation or native SQL. Run on POSIX;
--list also works on Windows and only discovers tests. Suites' own fake ports and
external-effect audit guards remain in force. Child environments omit credentials.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

POSIX = os.name == 'posix'
ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / 'operations/sql-backup/recovery'
SUITES = ('test_recovery.py', 'test_cold_path.py', 'test_cold_execution.py',
          'test_host_entrypoints.py', 'test_bootstrap.py', 'test_bundle_runtime.py', 'test_listener_transition.py', 'test_service_plan.py',
          'test_connection_version.py',
          'test_service_renderer.py', 'test_verify_effective.py', 'test_runtime_precheck.py',
          'test_kernel_query_binding.py', 'test_private_listener.py',
          'test_wp4_recovery_contract.py')
PORTABLE = ROOT / 'operations/integrations/portable'
PORTABLE_SUITES = ('test_bridge.py', 'test_publisher.py', 'test_wiring_proposal.py')
SUITES += PORTABLE_SUITES
CHILD = r'''
import json,sys,unittest
loader=unittest.TestLoader()
suite=loader.discover(sys.argv[1], pattern=sys.argv[2])
def ids(group):
    for test in group:
        if isinstance(test,unittest.TestSuite): yield from ids(test)
        else: yield test.id()
names=list(ids(suite))
if not names or loader.errors:
    print(json.dumps({'Suite':sys.argv[2],'Status':'DISCOVERY_FAILED','Tests':names,'Errors':loader.errors}))
    raise SystemExit(1)
if sys.argv[3]=='list':
    print(json.dumps({'Suite':sys.argv[2],'Status':'DISCOVERED_ONLY','Tests':names,'Count':len(names)}))
else:
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    ok=result.wasSuccessful() and not result.skipped and result.testsRun==len(names)
    print(json.dumps({'Suite':sys.argv[2],'Status':'PASS' if ok else 'FAIL',
                      'Tests':names,'Count':result.testsRun,'Skipped':len(result.skipped),
                      'Failures':len(result.failures),'Errors':len(result.errors)}))
    raise SystemExit(0 if ok else 1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Discover only; never counts as PASS')
    args = parser.parse_args()
    if not args.list and not POSIX:
        parser.error('Existing POSIX Python/Bash required; use the approved Linux VM or CI, no installs')
    env = {key: os.environ[key] for key in ('PATH', 'SystemRoot', 'TEMP', 'TMP', 'HOME', 'LANG', 'LC_ALL')
           if key in os.environ}
    env.update(AWS_EC2_METADATA_DISABLED='true', AWS_CONFIG_FILE=os.devnull,
               AWS_SHARED_CREDENTIALS_FILE=os.devnull)
    # Avoid world-writable /tmp in host private-parent tests, no sudo/chown of others.
    with tempfile.TemporaryDirectory(prefix='.ecs-recovery-ci-', dir=Path.home()) as scratch:
        env['ECS_RECOVERY_TEST_SCRATCH'] = scratch
        total = 0
        for name in SUITES:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(PORTABLE if name in PORTABLE_SUITES else RECOVERY),
                                     name, 'list' if args.list else 'run'],
                                    env=env, text=True, capture_output=True, timeout=180)
            if result.stderr:
                print(result.stderr, file=sys.stderr, end='', flush=True)
            print(result.stdout, end='', flush=True)
            if result.returncode:
                return result.returncode
            record = json.loads(result.stdout.strip().splitlines()[-1])
            total += record['Count']
        print(json.dumps({'Status': 'DISCOVERY_ONLY' if args.list else 'PASS',
                          'Suites':len(SUITES),'Tests':total,'CloudExecuted':False,
                          'NativeSqlExecuted':False}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
