"""Hermetic WP2B foundation suite, not live installation or E1 acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import socket  # Load before the hermetic audit guard.
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE.parent / "security_root"), str(HERE.parent / "authority")]
from hermetic import install


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    install()
    from inventory import verify, scan
    from model import validate_repository
    errors = verify(ROOT)
    try:
        validate_repository(ROOT)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        errors.append(str(exc))
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py"))
    good = result.wasSuccessful() and result.testsRun > 0 and not result.skipped and not errors
    report = {"result": "WP2B_FOUNDATION_PASS" if good else "WP2B_FOUNDATION_FAIL",
              "classification": "E1_WP2B_PROTECTED_CONTROL_BUNDLE_FOUNDATION",
              "counts": {"executed": result.testsRun, "failures": len(result.failures),
                         "errors": len(result.errors), "skipped": len(result.skipped)},
              "admission_errors": errors, "installation": "UNVERIFIED", "operational": False,
              "source_digest": hashlib.sha256(json.dumps(scan(ROOT), sort_keys=True).encode()).hexdigest(),
              "target_acceptance": "NOT_EVALUATED_INCOMPLETE",
              "platform_gaps": {"git_bash_selector": "FAILED_UNRESOLVED_CLEANUP", "linux": "UNVALIDATED",
                                "provider_validation": "UNVERIFIED_NOT_INITIALIZED", "live_bootstrap": "UNVERIFIED"}}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
