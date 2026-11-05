"""WP3C split-plane constants. No credentials, AWS discovery or activation."""
import hashlib
import json
import re

CORE_BUILD = '8f0712c72fe148bab19a5a091044abe13f3b1c6fa07db3efd70b22e3356c35f7'
CORE_FINALIZER = '0e34a5cd928e91694083a46aba1291b1526b7c1c47faaed4fe51a4ea60eb8fae'
CONTROLLERS = {
    'request-gateway/release': ('e1-gateway-release', 'LAMBDA'),
    'build/release': ('e1-controller-release', 'CODEBUILD'),
    'qualification-finalizer/qualification': ('e1-qualification-finalizer', 'LAMBDA'),
    'status/status-neutral': ('e1-status-neutral', 'LAMBDA'),
}
WORKERS = {k: 'e1-controller-release-payload-' + k for k in ('dotnet', 'image', 'probe')}
WORKER_ROLE = 'e1-controller-release-payload-exec'
PHASES = {'dotnet_restore': 'PRE_BUILD', 'dotnet_build': 'BUILD',
          'dotnet_test': 'POST_BUILD', 'image_build': 'BUILD',
          'probe_capability': 'PRE_BUILD', 'probe_no_server': 'BUILD'}
ORDER = ('SUBMITTED', 'QUEUED', 'PROVISIONING', 'DOWNLOAD_SOURCE', 'INSTALL',
         'PRE_BUILD', 'BUILD', 'POST_BUILD', 'UPLOAD_ARTIFACTS', 'FINALIZING', 'COMPLETED')
UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
STANDARD_RECIPE = 'STANDARD_V1'
DEV_SQL_LAB_RECIPE = 'DEV_SQL_LAB_V1'
SQL_CERTIFICATE = '206095fa0ba9e17a84c80eff5021db93d05e2dc377e982a64d517696ed21a1e7'
SQL_RECIPE_SHA256 = '8045c87604e515389f41413534a30a51b0edcc49f32d905b49e1021f28fd2c91'
DEV_DOTNET_SDK = '10.0.402'
DEV_RECIPE_FIELDS = ('schema', 'environment', 'account', 'region', 'source_commit',
                     'recipe', 'certificate_der_sha256', 'recipe_sha256', 'previous_build_runtime', 'dotnet_runtime')


class Rejected(ValueError):
    pass


def require(ok):
    if not ok:
        raise Rejected('E1_INTERNAL_RELEASE_REJECTED')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def operation_id(value):
    require(type(value) is str and re.fullmatch(UUID, value) is not None)
    return value


def build_id(value, project):
    require(type(value) is str and re.fullmatch(re.escape(project) + ':' + UUID, value) is not None)
    return value


def version(value):
    require(type(value) is str and 0 < len(value) <= 1024 and value.strip() == value
            and value.lower() not in ('null', 'latest') and all(ord(c) >= 32 for c in value))
    return value


def image_uri(value, account, region, repository):
    require(type(value) is str and re.fullmatch(re.escape(
        account + '.dkr.ecr.' + region + '.amazonaws.com/' + repository) + '@sha256:[0-9a-f]{64}', value))
    return value


def select_recipe(authorization, commit, account, region):
    """Administrator configuration, never gateway parameters or source hints."""
    if authorization is None:
        return STANDARD_RECIPE
    closed(authorization, DEV_RECIPE_FIELDS)
    previous = authorization['previous_build_runtime']
    closed(previous, ('uri','support_sha256'))
    image_uri(previous['uri'], account, region, 'e1-controller-build')
    require(type(previous['support_sha256']) is str and re.fullmatch('[0-9a-f]{64}',previous['support_sha256']))
    dotnet = authorization['dotnet_runtime']
    closed(dotnet, ('uri','support_sha256','sdk','approval'))
    image_uri(dotnet['uri'], account, region, 'e1-payload-dotnet')
    require(dotnet['sdk'] == DEV_DOTNET_SDK and dotnet['approval'] == 'ADMIN_VERIFIED'
            and type(dotnet['support_sha256']) is str and re.fullmatch('[0-9a-f]{64}',dotnet['support_sha256']))
    require(authorization['schema'] == 'E1_WP3_DEV_SQL_LAB_V1'
            and authorization['environment'] == 'dev'
            and authorization['account'] == account and authorization['region'] == region
            and type(authorization['source_commit']) is str
            and re.fullmatch('[0-9a-f]{40}', authorization['source_commit'])
            and authorization['recipe'] == DEV_SQL_LAB_RECIPE
            and authorization['certificate_der_sha256'] == SQL_CERTIFICATE
            and authorization['recipe_sha256'] == SQL_RECIPE_SHA256)
    return DEV_SQL_LAB_RECIPE if commit == authorization['source_commit'] else STANDARD_RECIPE


def worker_buildspec(kind, selectable=False):
    """Fixed phases; commands never loaded from application source.

    Worker support binaries are in the admin-approved immutable worker runtime.
    The probe uses the exact application digest as its environment, so only sh
    and the application's dotnet executable are required there.
    """
    require(type(selectable) is bool and (not selectable or kind == 'image'))
    if kind == 'dotnet':
        phases = {'install': ['python3 /opt/e1/scripts/internal_release/worker.py source'],
                  'pre_build': ['dotnet restore ./demo-api/terragrunt-demo.sln'],
                  'build': ['dotnet build ./demo-api/terragrunt-demo.sln --configuration Release --no-restore'],
                  'post_build': ['dotnet test ./demo-api/terragrunt-demo.sln --configuration Release --no-build --verbosity normal']}
    elif kind == 'image':
        phases = {'install': ['python3 /opt/e1/scripts/internal_release/worker.py source',
                             'mkdir -p /etc/docker; printf \'%s\' \'{"features":{"containerd-snapshotter":true}}\' > /etc/docker/daemon.json',
                             'nohup dockerd --host=unix:///var/run/docker.sock >/tmp/e1-dockerd.log 2>&1 &',
                             'i=0; until docker info >/dev/null 2>&1; do i=$((i+1)); test "$i" -lt 30 || exit 1; sleep 1; done'],
                  'build': ['docker buildx build --provenance=false --sbom=false --platform linux/amd64 --output type=oci,dest=/tmp/e1-image.tar -f demo-api/Dockerfile demo-api',
                            'python3 /opt/e1/scripts/internal_release/worker.py output']}
    else:
        require(kind == 'probe')
        phases = {'pre_build': ["out=$(dotnet /app/terragrunt-demo.dll readiness-probe --check-capability) && test \"$out\" = readiness-probe-capability=available"],
                  'build': ['rc=0; READINESS_PROBE_TIMEOUT_SECONDS=1 READINESS_PROBE_REQUEST_TIMEOUT_SECONDS=1 READINESS_PROBE_INTERVAL_SECONDS=1 dotnet /app/terragrunt-demo.dll readiness-probe || rc=$?; test "$rc" -eq 1']}
    if selectable:
        # Fixed commands; no interpolation of a caller-supplied path or command.
        standard = phases['build'][0]
        lab = standard.replace('-f demo-api/Dockerfile ', '-f demo-api/deploy/sql-lab/Dockerfile ')
        phases['build'][0] = ('case "$E1_BUILD_RECIPE" in '
            '""|STANDARD_V1) ' + standard + ' ;; DEV_SQL_LAB_V1) ' + lab +
            ' ;; *) exit 1 ;; esac')
    return {'version': '0.2', 'phases': {k: {'on-failure': 'ABORT', 'commands': v} for k, v in phases.items()}}


def observe(response, expected_id, project, stage):
    """AWS response, never stdout. Return a WP3B process observation.

    Correlation is to the ID returned by the controller's own StartBuild call.
    A mapped phase contributes success only if the worker build also succeeds.
    """
    build_id(expected_id, project)
    require(not response.get('buildsNotFound') and len(response.get('builds', [])) == 1)
    b = response['builds'][0]
    require(b.get('id') == expected_id and b.get('projectName') == project)
    require(b.get('buildComplete') is True and b.get('buildStatus') in
            ('SUCCEEDED', 'FAILED', 'FAULT', 'TIMED_OUT', 'STOPPED'))
    phases = b.get('phases', [])
    names = [p.get('phaseType') for p in phases]
    require(len(names) == len(set(names)) and all(n in ORDER for n in names))
    require(names == sorted(names, key=ORDER.index))
    wanted = PHASES[stage]
    found = [p for p in phases if p['phaseType'] == wanted]
    state, code = 'UNKNOWN', None
    if found:
        status = found[0].get('phaseStatus')
        if status == 'SUCCEEDED':
            # All preceding command phases must actually have succeeded.
            predecessors = [p for p in ('INSTALL', 'PRE_BUILD', 'BUILD', 'POST_BUILD')
                            if ORDER.index(p) < ORDER.index(wanted)]
            require(all(any(x['phaseType'] == p and x.get('phaseStatus') == 'SUCCEEDED'
                            for x in phases) for p in predecessors))
            # A successful phase in a failed/stopped worker is not a completed
            # qualification check, even if failure happened in a later phase.
            if b.get('buildStatus') == 'SUCCEEDED':
                state, code = 'COMPLETED', (1 if stage == 'probe_no_server' else 0)
        elif status in ('FAILED', 'FAULT', 'TIMED_OUT', 'STOPPED'):
            state, code = 'COMPLETED', (0 if stage == 'probe_no_server' else 1)
    return {'stage': stage, 'state': state, 'exit_code': code,
            'capability': stage == 'probe_capability' and code == 0 and state == 'COMPLETED'}
