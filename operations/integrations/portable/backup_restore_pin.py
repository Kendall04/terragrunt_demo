"""Stage an exact backup pair outside Lifecycle BEFORE fencing any SQL source.

No restore or deletion. The copy has genuine destination VersionIds; the original
manifest and source binding remain as evidence. Ambiguous writes stop, no retry.
"""
import datetime as dt
import hashlib
import json
import re
from backup_retention import BUCKET, PREFIX, HOLD_PREFIX, canonical, scope
from storage_observer import inspect_manifest, encrypted, require, unique_json


def read(s3, config, key, version, maximum):
    obj = s3.get_object(Bucket=BUCKET, Key=key, VersionId=version)
    try:
        encrypted(obj, config, version)
        require(obj['ContentLength'] <= maximum, 'PIN_SIZE_BOUND')
        data = obj['Body'].read(maximum + 1)
        require(len(data) == obj['ContentLength'], 'PIN_LENGTH')
        return data
    finally:
        obj['Body'].close()


def pin(s3, config, manifest_key, operation, now):
    scope(config)
    require(re.fullmatch('[a-z0-9][a-z0-9-]{7,63}', operation), 'PIN_OPERATION')
    checked = inspect_manifest(s3, config, now, manifest_key)
    raw = read(s3, config, manifest_key, checked['manifestVersion'], 65536)
    original = unique_json(raw)
    backup = read(s3, config, original['BackupKey'], checked['backupVersion'], config['maxBytes'])
    require(hashlib.sha256(backup).hexdigest() == checked['sha256'], 'PIN_BACKUP_CHANGED')
    prefix = HOLD_PREFIX + operation
    destination = prefix + '/runs/' + checked['runId'] + '/'
    versions = s3.list_object_versions(Bucket=BUCKET, Prefix=prefix + '/', MaxKeys=1)
    require(not versions.get('Versions') and not versions.get('DeleteMarkers'), 'PIN_ALREADY_EXISTS_STOP')

    def put(key, data):
        result = s3.put_object(Bucket=BUCKET, Key=key, Body=data, IfNoneMatch='*',
            ServerSideEncryption='aws:kms', SSEKMSKeyId=config['backupKeyArn'],
            ChecksumSHA256=__import__('base64').b64encode(hashlib.sha256(data).digest()).decode())
        version = result.get('VersionId')
        require(version not in (None, '', 'null'), 'PIN_WRITE_UNCONFIRMED')
        require(read(s3, config, key, version, max(len(data), 65536)) == data, 'PIN_READBACK_MISMATCH')
        return version

    backup_version = put(destination + 'database.bak', backup)
    original_version = put(destination + 'original-manifest.json', raw)
    rebound = {**original, 'BackupKey': destination + 'database.bak', 'BackupVersion': backup_version}
    manifest_version = put(destination + 'manifest.json', canonical(rebound))
    pinned_config = {**config, 'prefix': prefix}
    actual = inspect_manifest(s3, pinned_config, now, destination + 'manifest.json')
    require(actual['manifestVersion'] == manifest_version and actual['sha256'] == checked['sha256'], 'PIN_FINAL_READBACK')
    receipt = {'schemaVersion': 1, 'at': now.isoformat(), 'operation': operation,
               'source': checked, 'pinned': actual, 'originalManifestVersion': original_version,
               'restoreConfigPrefix': prefix, 'automaticDeletion': False, 'sqlMutations': 0}
    receipt_version = put(prefix + '/pin-receipt.json', canonical(receipt))
    return {**receipt, 'receiptVersion': receipt_version}


def main():
    import argparse
    from pathlib import Path
    import boto3
    from botocore.config import Config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--manifest-key', required=True)
    parser.add_argument('--operation', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'RECEIPT_ALREADY_EXISTS')
    session = boto3.Session(region_name='us-east-1')
    require(session.client('sts').get_caller_identity()['Account'] == '341936017254', 'PIN_ACCOUNT')
    s3 = session.client('s3', config=Config(retries={'total_max_attempts': 1}, connect_timeout=5, read_timeout=60))
    result = pin(s3, json.loads(args.config.read_text()), args.manifest_key, args.operation, dt.datetime.now(dt.timezone.utc))
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2)
    print(json.dumps({'status': 'PIN_VERIFIED', 'operation': args.operation, 'sqlMutations': 0}))


if __name__ == '__main__':
    main()
