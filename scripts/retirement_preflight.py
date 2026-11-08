"""Offline EC2 retirement resource-type audit; never grants execution authority.

Inspect exported current operator policy documents before billable creation.
This checks explicit Allow resource shapes only, not IAM conditions, Deny, SCP,
boundaries, installed versions or live authorization. It never calls AWS.
"""
import argparse
import fnmatch
import json
from pathlib import Path
import re

REQUIRED = {
    'ec2:DetachInternetGateway': ('internet-gateway', 'vpc'),
    'ec2:DisassociateRouteTable': ('route-table', 'subnet'),
}


def values(value):
    if isinstance(value, str): return [value]
    if isinstance(value, list) and all(isinstance(x, str) for x in value): return value
    return []


def audit(documents, account, region):
    if not re.fullmatch(r'[0-9]{12}', account) or not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]', region):
        raise ValueError('EXPLICIT_ACCOUNT_AND_REGION_REQUIRED')
    prefix = f'arn:aws:ec2:{region}:{account}:'
    missing = []
    for action, required in REQUIRED.items():
        covered = set()
        for document in documents:
            document = document.get('PolicyDocument', document)
            statements = document.get('Statement', [])
            if isinstance(statements, dict): statements = [statements]
            for statement in statements:
                if statement.get('Effect') != 'Allow': continue
                if not any(fnmatch.fnmatchcase(action.lower(), pattern.lower()) for pattern in values(statement.get('Action'))): continue
                for resource in values(statement.get('Resource')):
                    if resource.startswith(prefix) and '/' in resource[len(prefix):]:
                        covered.add(resource[len(prefix):].split('/', 1)[0])
        missing.extend({'Action': action, 'MissingResourceType': kind} for kind in required if kind not in covered)
    return {
        'Status': 'BLOCKED_MISSING_COMPANION_RESOURCE_TYPES' if missing else 'STRUCTURAL_ONLY_LIVE_IAM_REVIEW_REQUIRED',
        'Account': account, 'Region': region, 'Missing': missing,
        'AllowsCreation': False, 'LiveAuthorizationProven': False,
        'Limit': 'Explicit Allow resource types only. Review actual resource ARNs, conditions, Deny, boundaries/SCP and complete live multi-resource simulation before any cost.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--policy', type=Path, nargs='+', required=True,
                        help='Current exported IAM policy documents; not credentials or state')
    args = parser.parse_args(argv)
    documents = []
    for path in args.policy:
        if path.stat().st_size > 1024 * 1024: raise ValueError('POLICY_INPUT_TOO_LARGE')
        document = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(document, dict): raise ValueError('POLICY_OBJECT_REQUIRED')
        documents.append(document)
    result = audit(documents, args.account, args.region)
    print(json.dumps(result, separators=(',', ':')))
    return 1 if result['Missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
