"""Read-only S3 backup observation; no SQL credentials, journal writes or remediation."""
import datetime as dt
import hashlib
import json
import os
import re


class Unverified(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Unverified(code)


def utc(value):
    value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(value.tzinfo is not None, 'TIMESTAMP_WITHOUT_ZONE')
    return value.astimezone(dt.timezone.utc)


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'DUPLICATE_FIELD')
            result[key] = value
        return result
    require(len(raw) <= 65536, 'MANIFEST_TOO_LARGE')
    return json.loads(raw, object_pairs_hook=pairs)


def encrypted(response, config, version=None):
    require(response.get('ServerSideEncryption') == 'aws:kms' and
            response.get('SSEKMSKeyId') == config['backupKeyArn'], 'WRONG_ENCRYPTION')
    require(response.get('VersionId') not in (None, '', 'null'), 'UNVERSIONED_OBJECT')
    require(version is None or response['VersionId'] == version, 'VERSION_MISMATCH')


def inspect(s3, config, now):
    """Verify newest committed manifest and its full exact-version backup, with bounds.

    A newer invalid commit is an error, never a reason to fall back to an old success.
    This proves storage integrity plus the producer's native-checksum receipt, not CHECKDB.
    """
    prefix = config['prefix'].rstrip('/') + '/runs/'
    listing = s3.list_objects_v2(Bucket=config['bucket'], Prefix=prefix, MaxKeys=1000)
    require(not listing.get('IsTruncated'), 'LIST_BOUND_EXCEEDED')
    candidates = [x for x in listing.get('Contents', []) if x['Key'].endswith('/manifest.json')]
    require(candidates, 'BACKUP_MISSING')
    latest = max(candidates, key=lambda x: (x['LastModified'], x['Key']))
    return inspect_manifest(s3, config, now, latest['Key'])


def inspect_manifest(s3, config, now, manifest_key):
    """Read one immutable pair; used by observation and retention admission."""
    prefix = config['prefix'].rstrip('/') + '/runs/'
    latest = {'Key': manifest_key}
    match = re.fullmatch(re.escape(prefix) + r'([a-f0-9]{32})/manifest.json', latest['Key'])
    require(match is not None, 'MANIFEST_SCOPE')
    head = s3.head_object(Bucket=config['bucket'], Key=latest['Key'])
    encrypted(head, config)
    require(0 < head['ContentLength'] <= 65536, 'MANIFEST_TOO_LARGE')
    response = s3.get_object(Bucket=config['bucket'], Key=latest['Key'], VersionId=head['VersionId'])
    encrypted(response, config, head['VersionId'])
    try:
        raw = response['Body'].read(65537)
    finally:
        response['Body'].close()
    m = unique_json(raw)
    expected = set('SchemaVersion Id Database StartedUtc CompletedUtc SqlVersion RecoveryModel Length Sha256 NativeChecksumVerified TextKeyArn BackupKey BackupVersion'.split())
    require(set(m) == expected and type(m['SchemaVersion']) is int and m['SchemaVersion'] == 1,
            'MANIFEST_SCHEMA')
    require(m['Id'] == match[1] and m['Database'] == config['database'], 'DATABASE_OR_RUN_MISMATCH')
    require(m['BackupKey'] == prefix + m['Id'] + '/database.bak', 'BACKUP_SCOPE')
    require(m['TextKeyArn'] == config['textKeyArn'] and m['NativeChecksumVerified'] is True and
            m['SqlVersion'].startswith('16.'), 'PRODUCER_RECEIPT_UNVERIFIED')
    require(type(m['Length']) is int and 0 < m['Length'] <= config['maxBytes'] <= 536870912,
            'BACKUP_SIZE_BOUND')
    require(re.fullmatch('[a-f0-9]{64}', m['Sha256']) is not None and
            isinstance(m['BackupVersion'], str) and m['BackupVersion'] not in ('', 'null'),
            'BACKUP_IDENTITY')
    started, completed = utc(m['StartedUtc']), utc(m['CompletedUtc'])
    require(dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) <= started <= completed <= now + dt.timedelta(minutes=5),
            'BACKUP_TIME')
    backup = s3.get_object(Bucket=config['bucket'], Key=m['BackupKey'], VersionId=m['BackupVersion'])
    try:
        encrypted(backup, config, m['BackupVersion'])
        require(backup['ContentLength'] == m['Length'], 'BACKUP_LENGTH')
        digest, count = hashlib.sha256(), 0
        while chunk := backup['Body'].read(1048576):
            count += len(chunk)
            require(count <= m['Length'], 'BACKUP_LENGTH')
            digest.update(chunk)
        require(count == m['Length'] and digest.hexdigest() == m['Sha256'], 'BACKUP_HASH')
    finally:
        backup['Body'].close()
    return {'code': 'EXACT_S3_VERSION_SHA256_VERIFIED', 'dataAt': started.isoformat(),
            'runId': m['Id'], 'manifestKey': latest['Key'], 'manifestVersion': head['VersionId'],
            'backupVersion': m['BackupVersion'], 'sha256': m['Sha256'], 'bytes': m['Length']}


def reports(config, observation, now, invocation):
    """Keep installed monitor/resource/generation identities; no fabricated host receipts."""
    valid = observation['code'] == 'EXACT_S3_VERSION_SHA256_VERIFIED'
    identity = hashlib.sha256(json.dumps([invocation, observation], sort_keys=True).encode()).hexdigest()
    entries = []
    for monitor in config['monitors']:
        backup = monitor['kind'] == 'sql-backup'
        detail = ('S3 exact-version hash and SSE-KMS checked; producer checksum receipt verified. '
                  'No claim of SQL availability, latest local attempt or restore success.' if valid else observation['code'])
        report = {'schemaVersion': 1, 'monitor': monitor['id'], 'producer': 'sql-observer',
                  'id': hashlib.sha256((identity + monitor['id']).encode()).hexdigest(),
                  'resource': monitor['resource'], 'generation': monitor['generation'],
                  'observedAt': now.isoformat(), 'dataAt': observation['dataAt'] if backup and valid else now.isoformat(),
                  'verdict': 'Pass' if valid or not backup else 'Unknown',
                  'assurance': 'Artifact' if backup and valid else 'Reported',
                  'runId': observation['runId'] if backup and valid else identity,
                  'detail': detail if backup else 'External storage observer heartbeat; not SQL health.',
                  'backupType': 'full' if backup else None}
        entries.append({'EventBusName': config['bus'], 'Source': 'sentinel.report.sql-observer',
                        'DetailType': 'Sentinel Observation v1', 'Detail': json.dumps(report, separators=(',', ':'))})
    return entries


def handler(event, context):
    import boto3
    from botocore.config import Config
    now = dt.datetime.now(dt.timezone.utc)
    config = json.loads(os.environ['BACKUP_OBSERVER_CONFIG'])
    require(now < utc(config['expiresAt']), 'OBSERVATION_WINDOW_EXPIRED')
    require(event.get('source') in ('aws.events', 'dev.backup-observer.validation'), 'INVOCATION_SOURCE')
    require(isinstance(event.get('id'), str) and 0 < len(event['id']) <= 128, 'INVOCATION_ID')
    clients = Config(retries={'total_max_attempts': 1}, connect_timeout=5, read_timeout=30)
    if event.get('resources') == ['arn:aws:events:us-east-1:341936017254:rule/ecs-portable-r20261026p1-nat-observer']:
        import nat_observer
        return nat_observer.handler(event, context, lambda name: boto3.client(name, config=clients), config['nat'])
    try:
        observation = inspect(boto3.client('s3', config=clients), config, now)
    except Unverified as error:
        observation = {'code': str(error)}
    except Exception:
        # No raw AWS/SQL error strings enter observation text or notifications.
        observation = {'code': 'STORAGE_CHECK_UNAVAILABLE'}
    result = boto3.client('events', config=clients).put_events(Entries=reports(config, observation, now, event['id']))
    require(result['FailedEntryCount'] == 0, 'OBSERVATION_DELIVERY_UNCONFIRMED')
    if config.get('retentionEnabled'):
        import backup_retention
        s3 = boto3.client('s3', config=clients)
        try:
            reviewed = backup_retention.plan(s3, config, now)
            retention = backup_retention.apply_plan(s3, config, reviewed)
        except Unverified as error:
            if str(error) != 'TWO_RECOVERABLE_PAIRS_REQUIRED':
                raise
            retention = {'status': 'WAITING_FOR_TWO_PAIRS', 'deletedObjects': 0}
        print(json.dumps({'retention': retention}))
    print(json.dumps({'observation': observation, 'eventIds': [x['EventId'] for x in result['Entries']]}))
    return {'code': observation['code'], 'eventIds': [x['EventId'] for x in result['Entries']]}
