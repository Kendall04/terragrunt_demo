"""Hermetic WP2D repository checks; never deployment or WP2 acceptance."""
import argparse
import json
from pathlib import Path
import socket
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
    from inventory import verify
    from model import validate_repository
    errors = verify(ROOT)
    try:
        validate_repository(ROOT)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        errors.append(str(exc))
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py"))
    good = result.wasSuccessful() and result.testsRun > 0 and not result.skipped and not errors
    report = {"result": "WP2D_FOUNDATION_PASS" if good else "WP2D_FOUNDATION_FAIL",
        "counts": {"executed": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
        "admission_errors": errors, "operational": False, "live_installation": "UNVERIFIED_NOT_PERFORMED",
        "live_migration": "UNVERIFIED_NOT_PERFORMED", "live_compute": "UNVERIFIED_NOT_DEPLOYED",
        "target_acceptance": "PENDING_INDEPENDENT_REVIEW"}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
