"""Check (default) or regenerate the fixed WP2A Terraform/Terragrunt wiring.

python -I -B scripts/tests/security_root/render.py [--write]
No provider, Terraform, Terragrunt, network or credential access.
"""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent / "authority")]
from model import load_authority, validate_repository, wiring, wrapper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    doc = load_authority(ROOT)
    if args.write:
        for name, configuration in wiring(doc).items():
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(configuration, indent=2) + "\n", newline="\n")
        (ROOT / "terraform/live/security/terragrunt.hcl").write_text(wrapper(doc), newline="\n")
    validate_repository(ROOT)
    print("WP2A closed source / Terraform wiring PASS")


if __name__ == "__main__":
    main()
