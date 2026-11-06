"""Bounded native Lifecycle admission for NEW DEV backup pairs only.

This module never deletes objects. S3 expires only explicitly admitted versions.
The two newest verified pairs and any uncommitted/ambiguous input fail closed.
Restore must stage and verify its selected input outside this lifecycle prefix
before it starts; tag removal alone is not proof that a restore input survives.
"""
import copy
import datetime as dt
import hashlib
import json
import re

from storage_observer import inspect_manifest, require

BUCKET = 'terragrunt-demo-sql-backup-341936017254-fa48a32dc9'
PREFIX = 'terragrunt-demo/dev/sql-backups/v2-20261106/'
TAG = {'Key': 'ecs-retention', 'Value': 'verified-superseded-v1'}
HOLD_PREFIX = 'terragrunt-demo/dev/sql-backup-restore-holds/v2-20261106/'
KEEP = 2
MAX_PAIRS = 8


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def scope(config):
    require(config['bucket'] == BUCKET and
            config['prefix'].rstrip('/') + '/' == PREFIX, 'RETENTION_SCOPE')


def lifecycle(existing):
    """Preserve unrelated rules exactly; never install a broad version purge."""
    result = copy.deepcopy(existing)
    ids = {'dev-v2-20261106-verified-seven-days',
           'dev-v2-20261106-empty-markers', 'dev-v2-20261106-incomplete-uploads'}
    require(not any(r.get('ID') in ids for r in result), 'RETENTION_ALREADY_CONFIGURED')
    for rule in result:
        if rule.get('Status') != 'Enabled':
            continue
        f = rule.get('Filter', {})
        prefix = f.get('Prefix', f.get('And', {}).get('Prefix', rule.get('Prefix', '')))
        require(not (PREFIX.startswith(prefix) or prefix.startswith(PREFIX)),
                'EXISTING_LIFECYCLE_OVERLAP_REQUIRES_REVIEW')
    result.extend([
        {'ID': 'dev-v2-20261106-verified-seven-days', 'Status': 'Enabled',
         'Filter': {'And': {'Prefix': PREFIX, 'Tags': [TAG.copy()]}},
         'Expiration': {'Days': 7},
         'NoncurrentVersionExpiration': {'NoncurrentDays': 1}},
        {'ID': 'dev-v2-20261106-empty-markers', 'Status': 'Enabled',
         'Filter': {'Prefix': PREFIX}, 'Expiration': {'ExpiredObjectDeleteMarker': True}},
        {'ID': 'dev-v2-20261106-incomplete-uploads', 'Status': 'Enabled',
         'Filter': {'Prefix': PREFIX},
         'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}},
    ])
    return result


def plan(s3, config, now):
    """Full verification precedes eligibility; no writes or tag removals here.

    Restore admission requires a verified independent pin before relying on a
    Lifecycle-eligible pair; a stale absence check is not a restore lease.
    """
    scope(config)
    require(now.tzinfo is not None, 'RETENTION_TIME_WITHOUT_ZONE')
    listing = s3.list_object_versions(Bucket=BUCKET, Prefix=PREFIX + 'runs/', MaxKeys=1000)
    require(not listing.get('IsTruncated'), 'RETENTION_LIST_BOUND')
    markers = {x['Key'] for x in listing.get('DeleteMarkers', []) if x['IsLatest']}
    objects = {}
    for item in listing.get('Versions', []):
        key = item['Key']
        if key in markers:
            # Lifecycle's own markers/noncurrent versions are expected. They
            # never count as a recoverable current pair or an enrollment target.
            continue
        require(key not in objects and item.get('IsLatest') is True, 'MULTIPLE_VERSIONS_REQUIRES_REVIEW')
        require(re.fullmatch(re.escape(PREFIX) + r'runs/[a-f0-9]{32}/(manifest.json|database.bak)', key),
                'UNEXPECTED_RETENTION_OBJECT')
        require(item.get('VersionId') not in (None, '', 'null'), 'UNVERSIONED_RETENTION_OBJECT')
        objects[key] = item
    manifests = sorted((x for x in objects.values() if x['Key'].endswith('/manifest.json')),
                       key=lambda x: (x['LastModified'], x['Key']), reverse=True)
    require(len(manifests) >= KEEP, 'TWO_RECOVERABLE_PAIRS_REQUIRED')
    preserved, candidates, quarantined = [], [], []
    for index, manifest in enumerate(manifests[:KEEP + MAX_PAIRS]):
        initial_tags = s3.get_object_tagging(Bucket=BUCKET, Key=manifest['Key'], VersionId=manifest['VersionId'])['TagSet']
        if index >= KEEP and TAG in initial_tags:
            # Already enrolled pairs can expire independently. Never try to
            # reconstruct, re-tag or restore a partially expired old pair here.
            continue
        checked = inspect_manifest(s3, config, now, manifest['Key'])
        require(checked['manifestVersion'] == manifest['VersionId'], 'MANIFEST_CHANGED_DURING_REVIEW')
        backup_key = manifest['Key'].removesuffix('manifest.json') + 'database.bak'
        require(backup_key in objects and objects[backup_key]['VersionId'] == checked['backupVersion'],
                'UNCOMMITTED_OR_CHANGED_PAIR')
        pair = []
        for key, version in [(manifest['Key'], checked['manifestVersion']),
                             (backup_key, checked['backupVersion'])]:
            tags = s3.get_object_tagging(Bucket=BUCKET, Key=key, VersionId=version)['TagSet']
            by_key = {x['Key']: x['Value'] for x in tags}
            require(len(by_key) == len(tags), 'DUPLICATE_OBJECT_TAG')
            require(TAG['Key'] not in by_key or by_key[TAG['Key']] == TAG['Value'],
                    'FOREIGN_RETENTION_TAG')
            if index < KEEP:
                require(TAG['Key'] not in by_key, 'LAST_BACKUP_ALREADY_ELIGIBLE_STOP')
            age = now - objects[key]['LastModified']
            require(age >= dt.timedelta(), 'FUTURE_OBJECT_TIME')
            pair.append({'Key': key, 'VersionId': version, 'BeforeTags': tags,
                         'alreadyEligible': TAG['Key'] in by_key,
                         'ageSeconds': age.total_seconds()})
        identity = {k: checked[k] for k in ('runId', 'manifestVersion', 'backupVersion', 'sha256')}
        if index < KEEP:
            preserved.append(identity)
        elif any(x['ageSeconds'] > 6 * 86400 for x in pair):
            # No surprise immediate expiry when first enrolling old data.
            quarantined.append({**identity, 'reason': 'OLDER_THAN_ENROLLMENT_MARGIN'})
        else:
            candidates.append({**identity, 'objects': pair})
    committed_keys = {x['Key'] for x in manifests} | {
        x['Key'].removesuffix('manifest.json') + 'database.bak' for x in manifests}
    orphans = sorted(set(objects) - committed_keys)
    result = {'schemaVersion': 1, 'bucket': BUCKET, 'prefix': PREFIX,
              'at': now.isoformat(), 'preserved': preserved, 'candidates': candidates,
              'quarantined': quarantined, 'uncommittedObjects': orphans,
              'olderPairsDeferred': max(0, len(manifests) - KEEP - MAX_PAIRS),
              'restoreRequiresVerifiedPin': True, 'writes': 0}
    return {**result, 'sha256': hashlib.sha256(canonical(result)).hexdigest()}


def apply_plan(s3, config, reviewed):
    """Caller saves intent first; ambiguous tag writes stop, never retry/delete."""
    scope(config)
    payload = {k: v for k, v in reviewed.items() if k != 'sha256'}
    require(hashlib.sha256(canonical(payload)).hexdigest() == reviewed['sha256'], 'RETENTION_PLAN_CHANGED')
    require(reviewed['bucket'] == BUCKET and reviewed['prefix'] == PREFIX and
            len(reviewed['preserved']) == KEEP and len(reviewed['candidates']) <= MAX_PAIRS,
            'RETENTION_PLAN_SCOPE')
    protected = {x['runId'] for x in reviewed['preserved']}
    # Recompute the reviewed selection against the actual immutable versions.
    # A new backup between preview/apply changes the plan and stops this attempt.
    fresh = plan(s3, config, dt.datetime.fromisoformat(reviewed['at']))
    require(fresh == reviewed, 'RETENTION_INPUT_CHANGED')
    written = []
    for pair in reviewed['candidates']:
        require(pair['runId'] not in protected, 'PROTECTED_PAIR')
        require(len(pair['objects']) == 2, 'PAIR_REQUIRED')
        for item in pair['objects']:
            require(item['Key'] in [PREFIX + 'runs/' + pair['runId'] + '/manifest.json',
                                    PREFIX + 'runs/' + pair['runId'] + '/database.bak'], 'PAIR_SCOPE')
            tags = s3.get_object_tagging(Bucket=BUCKET, Key=item['Key'], VersionId=item['VersionId'])['TagSet']
            require(tags == item['BeforeTags'], 'OBJECT_TAGS_CHANGED')
            if item['alreadyEligible']:
                continue
            require(len(tags) < 10, 'OBJECT_TAG_LIMIT')
            s3.put_object_tagging(Bucket=BUCKET, Key=item['Key'], VersionId=item['VersionId'],
                                  Tagging={'TagSet': tags + [TAG.copy()]})
            actual = s3.get_object_tagging(Bucket=BUCKET, Key=item['Key'], VersionId=item['VersionId'])['TagSet']
            require(sorted(actual, key=lambda t: t['Key']) == sorted(tags + [TAG], key=lambda t: t['Key']),
                    'RETENTION_TAG_READBACK_UNCONFIRMED')
            written.append({'Key': item['Key'], 'VersionId': item['VersionId']})
    return {'planSha256': reviewed['sha256'], 'taggedVersions': written, 'deletedObjects': 0}
