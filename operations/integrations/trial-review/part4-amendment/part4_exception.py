"""Pure transformation of captured Part4; contains no AWS client or mutation code."""
from copy import deepcopy

BUCKET_ARN = 'arn:aws:s3:::ecs-sentinel-r20261023b1-341936017254'
EXPECTED_DENY = {
    'Effect': 'Deny',
    'Action': ['iam:CreateRole', 'iam:PutRolePolicy', 'iam:AttachRolePolicy',
               's3:PutBucketPolicy', 's3:DeleteBucket', 'kms:ScheduleKeyDeletion',
               'secretsmanager:DeleteSecret'],
    'Resource': ['*'],
}

def propose(original):
    """Fail closed if the observed source shape differs; change exactly one deny."""
    statements = original.get('Statement')
    if original.get('Version') != '2012-10-17' or not isinstance(statements, list):
        raise ValueError('Unexpected policy schema')
    matches = [i for i, s in enumerate(statements) if s == EXPECTED_DENY]
    if len(matches) != 1:
        raise ValueError('Expected exactly one unchanged captured mixed deny')
    i = matches[0]
    result = deepcopy(original)
    remaining = deepcopy(EXPECTED_DENY)
    remaining['Action'].remove('s3:DeleteBucket')
    scoped = {'Sid': 'DenyDeleteBucketExceptEcsSentinelR20261023b1', 'Effect': 'Deny',
              'Action': ['s3:DeleteBucket'], 'NotResource': [BUCKET_ARN]}
    if any(s.get('Sid') == scoped['Sid'] for s in statements):
        raise ValueError('Sid collision')
    result['Statement'][i:i+1] = [remaining, scoped]
    return result
