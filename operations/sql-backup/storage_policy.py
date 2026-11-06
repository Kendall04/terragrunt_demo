"""Small, pure DEV storage delta. Existing statements and objects are retained."""
import copy
import re

ACCOUNT = '341936017254'
REGION = 'us-east-1'
BUCKET = 'terragrunt-demo-sql-backup-341936017254-fa48a32dc9'
KEY = f'arn:aws:kms:{REGION}:{ACCOUNT}:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced'
ROLE = f'arn:aws:iam::{ACCOUNT}:role/demo-dev-data-sql-ec2-role'
ADMIN = f'arn:aws:iam::{ACCOUNT}:user/cnp-cert-admin'


def prepare(key_policy, bucket_policy, operation, package_sha, expires):
    if not re.fullmatch(r'v2-[0-9]{8}', operation):
        raise ValueError('EXACT_DEV_OPERATION_REQUIRED')
    if not re.fullmatch(r'[0-9a-f]{64}', package_sha):
        raise ValueError('PACKAGE_SHA_REQUIRED')
    from datetime import datetime, timezone
    end = datetime.strptime(expires, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    if end <= datetime.now(timezone.utc):
        raise ValueError('FUTURE_EXPIRY_REQUIRED')
    prefix = f'terragrunt-demo/dev/sql-backups/{operation}'
    artifact_key = f'terragrunt-demo/dev/sql-backup-artifacts/{operation}/{package_sha}/SqlBackup.tar'
    objects = f'arn:aws:s3:::{BUCKET}/{prefix}/*'
    artifact = f'arn:aws:s3:::{BUCKET}/{artifact_key}'
    time = {'DateLessThan': {'aws:CurrentTime': expires}}
    s3_context = {'StringEquals': {'kms:ViaService': f's3.{REGION}.amazonaws.com',
                                 'kms:CallerAccount': ACCOUNT},
                  'StringLike': {'kms:EncryptionContext:aws:s3:arn': [objects, artifact]}, **time}
    role_policy = {'Version': '2012-10-17', 'Statement': [
        {'Sid': 'CreateOnlyEncryptedBackups', 'Effect': 'Allow', 'Action': 's3:PutObject',
         'Resource': objects, 'Condition': {**time, 'StringEquals': {
             's3:x-amz-server-side-encryption': 'aws:kms',
             's3:x-amz-server-side-encryption-aws-kms-key-id': KEY, 's3:if-none-match': '*'}}},
        {'Sid': 'ReadOwnExactVersions', 'Effect': 'Allow',
         'Action': ['s3:GetObject', 's3:GetObjectVersion'], 'Resource': objects, 'Condition': time},
        {'Sid': 'ReadExactPackage', 'Effect': 'Allow', 'Action': 's3:GetObjectVersion',
         'Resource': artifact, 'Condition': time},
        {'Sid': 'BackupKeyViaS3Only', 'Effect': 'Allow',
         'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': KEY, 'Condition': s3_context}]}
    suffix = operation.replace('-', '')
    key_delta = [
        {'Sid': 'SqlBackup' + suffix, 'Effect': 'Allow', 'Principal': {'AWS': ROLE},
         'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': '*', 'Condition': s3_context},
        {'Sid': 'SqlPackagePublisher' + suffix, 'Effect': 'Allow', 'Principal': {'AWS': ADMIN},
         'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': '*', 'Condition': {
             **time, 'StringEquals': {'kms:ViaService': f's3.{REGION}.amazonaws.com',
                                     'kms:CallerAccount': ACCOUNT,
                                     'kms:EncryptionContext:aws:s3:arn': artifact}}}]
    bucket_delta = []
    for label, resource in [('Data', objects), ('Package', artifact)]:
        for name, field, value in [('Encryption', 's3:x-amz-server-side-encryption', 'aws:kms'),
                                   ('Key', 's3:x-amz-server-side-encryption-aws-kms-key-id', KEY),
                                   ('CreateOnly', 's3:if-none-match', '*')]:
            bucket_delta.append({'Sid': 'SqlBackup' + suffix + label + name, 'Effect': 'Deny',
                                 'Principal': '*', 'Action': 's3:PutObject', 'Resource': resource,
                                 'Condition': {'StringNotEquals': {field: value}}})

    def append(original, delta):
        result = copy.deepcopy(original)
        if {s['Sid'] for s in delta} & {s.get('Sid') for s in result['Statement']}:
            raise ValueError('EXISTING_DELTA_REQUIRES_RECONCILIATION')
        result['Statement'].extend(delta)
        return result

    return {'Prefix': prefix, 'ArtifactKey': artifact_key, 'RolePolicy': role_policy,
            'KeyPolicy': append(key_policy, key_delta), 'BucketPolicy': append(bucket_policy, bucket_delta),
            'Expiry': expires, 'LifecycleChanged': False, 'ExistingObjectsChanged': False}
