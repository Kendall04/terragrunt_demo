"""Hermetic WP2A foundation evidence; not WP2/E1 or live security acceptance.

python -I -B scripts/tests/security_root/run.py --report <temporary-path>
WP1 remains a separate, unchanged 236-test entry point.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent / "authority")]
sys.dont_write_bytecode = True
from hermetic import install


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    install()
    from model import validate_repository, AUTHORITY, LEGACY, wiring, load_authority, reviewed_supplemental_iac, SUPPLEMENTAL_CATALOG
    from inventory import verify
    errors = verify(ROOT)
    try:
        validate_repository(ROOT)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        errors.append(str(exc))
    executed = []
    class Recorded(unittest.TextTestResult):
        def startTest(self, test):
            executed.append(test.id())
            super().startTest(test)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Recorded).run(
        unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py"))
    good = result.wasSuccessful() and result.testsRun > 0 and not result.skipped and not errors
    paths = [AUTHORITY, LEGACY, *wiring(load_authority(ROOT)), "terraform/live/security/terragrunt.hcl"]
    paths += [SUPPLEMENTAL_CATALOG, *sorted(reviewed_supplemental_iac(ROOT))]
    paths += ["scripts/tests/authority/inventory.py", "scripts/tests/authority/history.py"]
    paths += [p.relative_to(ROOT).as_posix() for p in HERE.glob("*.py")]
    report = {"result": "WP2A_FOUNDATION_PASS" if good else "WP2A_FOUNDATION_FAIL",
              "classification": "E1_WP2A_PROTECTED_SECURITY_ROOT_FOUNDATION",
              "target_acceptance": "NOT_EVALUATED_INCOMPLETE", "external_governance": "UNVERIFIED",
              "scope": "Closed WP2A declarative source and repository wiring only; legacy excluded, not secured",
              "counts": {"executed": result.testsRun, "failures": len(result.failures),
                         "errors": len(result.errors), "skipped": len(result.skipped)},
              "test_ids": executed, "admission_errors": errors,
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths},
              "platform_gaps": {"git_bash_selector": "FAILED_UNRESOLVED_CLEANUP", "linux": "UNVALIDATED"}}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("result", "counts", "admission_errors")}, indent=2))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
