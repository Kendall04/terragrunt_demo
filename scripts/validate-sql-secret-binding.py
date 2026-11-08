"""Offline renderer admission against an independently installed environment binding.

The administrative caller supplies an authenticated current E1_DELIVERY_BINDING_V1
readback, never a record synthesized from --db-secret-id. This tool validates its
closed existing contract, not its transport provenance or live AWS permissions.
It never reads a secret value or contacts AWS. Missing PROD binding fails closed.
"""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.normal_delivery import authorization as authority


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('binding', 'environment', 'account', 'region', 'color', 'secret'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    try:
        raw = Path(a.binding).read_bytes()
        record = authority.binding(authority.decode(raw),
            {'dev': 'deploy-dev', 'prod': 'promote-prod'}[a.environment], a.account, a.region)
        authority.require(record['color'] == a.color)
        versioned = re.fullmatch(r'(.+):::([A-Za-z0-9-]{32,64})', a.secret)
        authority.require(versioned is not None)
        authority.require(versioned[1] == record['secret_arn'])
        # Also require the destination's closed name/account/region contract;
        # a mislabeled PROD record containing a DEV ARN is not authority.
        authority.connection_secret_arn(versioned[1], a.environment, a.account, a.region)
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit('SQL_SECRET_ENVIRONMENT_BINDING_REFUSED') from None


if __name__ == '__main__':
    main()
