"""Build or verify exact WP4D bundle bytes offline; never uploads or installs.

python -I -B scripts/tests/security_root/pack_wp4d.py BINDING --output FILE
python -I -B scripts/tests/security_root/pack_wp4d.py BINDING --verify FILE
"""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "authority"))

import wp4d
from model import load_authority


def main():
    from hermetic import install
    install()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binding", choices=sorted(wp4d.RESERVED))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    authority = load_authority(wp4d.ROOT)
    raw = wp4d.artifact(wp4d.ROOT, authority["control_bundles"], args.binding)
    expected = authority["wp4d"]["selected"][args.binding]["package_sha256"]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise SystemExit("WP4D_SOURCE_ADMISSION_FAILURE")
    if args.verify is not None:
        if args.verify.read_bytes() != raw:
            raise SystemExit("WP4D_PACKAGE_BYTES_MISMATCH")
    else:
        if args.output.resolve().is_relative_to(wp4d.ROOT):
            raise SystemExit("WP4D_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
        with args.output.open("xb") as stream:
            stream.write(raw)
    print("WP4D exact bundle " + expected)


if __name__ == "__main__":
    main()
