"""Pure promotion/source contracts. GitHub provenance is checked by github.py."""
import hashlib
import json
import re
import subprocess

REPOSITORY = 'Kendall04/terragrunt_demo'
DELIVERY = '.github/workflows/api-delivery.yml'
PROMOTION = '.github/workflows/api-promotion.yml'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def application_path(path):
    # Full build context and runtime configuration contract. Tests are included:
    # a changed qualification cannot silently reuse an older approval.
    return (path.startswith('demo-api/') and not path.endswith(('.md', '.png')) or
            path.startswith('operations/sql-backup/SqlBackup') or
            path in ('global.json', '.gitignore', 'NuGet.Config', 'Directory.Build.props',
                     'Directory.Build.targets', 'Directory.Packages.props'))


def application(root, commit):
    require(re.fullmatch('[0-9a-f]{40}', commit), 'exact commit required')
    rows = []
    for row in git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        path = name.decode('utf-8')
        if application_path(path):
            require(kind == 'blob' and mode in ('100644', '100755'), 'nonregular application input')
            rows.append([path, mode, blob])
    require(any(r[0] == 'demo-api/Dockerfile' for r in rows), 'incomplete application')
    return sha(canonical(sorted(rows)))


def eligible_pr(pr):
    require(pr['base']['ref'] == 'main' and pr['head']['ref'] == 'develop' and
            pr['head']['repo']['full_name'] == REPOSITORY and
            pr['base']['repo']['full_name'] == REPOSITORY, 'only same-repository develop may promote')


def release(record, environment=None):
    require(record['schema'] == 'API_RELEASE_V1' and record['status'] == 'HEALTHY', 'unhealthy release')
    require(record['repository'] == REPOSITORY, 'wrong repository')
    require(record['environment'] in ('dev', 'prod') and
            (environment is None or record['environment'] == environment), 'wrong environment')
    require(re.fullmatch('[0-9a-f]{40}', record['source']), 'source commit')
    for key in ('application', 'compatibility'):
        require(re.fullmatch('[0-9a-f]{64}', record[key]), key)
    require(re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9._/-]+@sha256:[a-f0-9]{64}',
                         record['image']), 'immutable ECR image required')
    require(record['profile'] == 'validated-v2' and record['per_task_ready'] is True and
            record['client_ready'] is True, 'missing real readiness evidence')
    return record


def approval(pr, app, dev):
    eligible_pr(pr)
    release(dev, 'dev')
    manifest_reference(dev['manifest_ref'])
    require(dev['application'] == app, 'DEV version differs')
    return dict(schema='API_PROMOTION_V1', repository=REPOSITORY, pr=pr['number'],
                head=pr['head']['sha'], base=pr['base']['sha'], application=app,
                deployment=True, dev=dev)


def promoted(pr, parents, app, receipt):
    eligible_pr(pr)
    require(pr['merged'] is True and len(parents) == 2, 'promotion requires a merge commit')
    require(receipt['schema'] == 'API_PROMOTION_V1' and receipt['repository'] == REPOSITORY and
            receipt['pr'] == pr['number'] and receipt['head'] == pr['head']['sha'] == parents[1] and
            receipt['base'] == parents[0] and receipt['application'] == app,
            'approval is not for this exact merged PR')
    if not receipt['deployment']:
        return None
    return release(receipt['dev'], 'dev') if receipt['dev']['application'] == app else require(False, 'changed application')


def rollback(current, previous, environment, compatibility):
    release(current, environment)
    release(previous, environment)
    require(previous['compatibility'] == current['compatibility'] == compatibility,
            'rollback requires current schema/TLS/runtime compatibility')
    require(current['image'] != previous['image'], 'no distinct previous image')
    return previous


def manifest_reference(value):
    require(type(value) is dict and set(value) == {'bucket', 'key', 'version', 'sha256'}, 'manifest reference fields')
    require(all(type(v) is str and v for v in value.values()) and
            value['version'].lower() not in ('null', 'latest') and
            re.fullmatch('[0-9a-f]{64}', value['sha256']), 'exact manifest version/hash required')
    return value


def recovery_target(value, environment, compatibility):
    require(type(value) is dict and value['schema'] == 'API_RECOVERY_TARGET_V1' and
            value['environment'] == environment and value['compatibility'] == compatibility and
            value['profile'] == 'validated-v2' and value['kind'] in ('native-admission', 'automatic'),
            'compatible recovery target missing')
    require(re.fullmatch('[0-9a-f]{40}', value['source']) and re.fullmatch('[0-9a-f]{64}', value['application']) and
            re.fullmatch(r'[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9._/-]+@sha256:[a-f0-9]{64}', value['image']),
            'recovery target identity')
    require(type(value['revision']) is str and value['revision'].startswith('arn:aws:ecs:') and
            value['color'] in ('blue', 'green'), 'recovery task identity')
    return value
