"""Offline WP2B artifact preparation; no upload, installation or activation.

python -I -B scripts/tests/security_root/pack_bundle.py CLASS --output TEMP_FILE
python -I -B scripts/tests/security_root/pack_bundle.py CLASS --verify TEMP_FILE
Outputs must be outside the repository. Existing files are never overwritten.
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent / "authority")]
from hermetic import install
from model import validate_repository
from bundles import artifact, installation_proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controller_class")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    install()
    try:
        catalog = validate_repository(ROOT)["control_bundles"]
        if args.controller_class not in catalog["classes"]:
            raise ValueError("unknown controller class")
        raw = args.verify.read_bytes() if args.verify else artifact(ROOT, catalog, args.controller_class)
        proposal = installation_proposal(ROOT, catalog, args.controller_class, raw)
        if args.output:
            if args.output.resolve().is_relative_to(ROOT):
                raise ValueError("output must be outside the repository")
            with args.output.open("xb") as dest:
                dest.write(raw)
        print(json.dumps(proposal, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print("WP2B_BUNDLE_REJECTED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
