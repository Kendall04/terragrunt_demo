"""WP3C split-plane constants. No credentials, AWS discovery or activation."""
import hashlib
import json
import re

CORE_BUILD = 'ef9ce1edd5331ea6dccebfa4ea9783c40650fd6b075e87c2ce0f3c6553701ec4'
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


def worker_buildspec(kind):
    """Fixed phases; commands never loaded from application source.

    Worker support binaries are in the admin-approved immutable worker runtime.
    The probe uses the exact application digest as its environment, so only sh
    and the application's dotnet executable are required there.
    """
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
    return {'version': '0.2', 'phases': {k: {'on-failure': 'ABORT', 'commands': v} for k, v in phases.items()}}


def observe(response, expected_id, project, stage):
    """AWS response, never stdout. Return a WP3B process observation.

    Correlation is to the ID returned by the controller's own StartBuild call.
    Terminal failed builds may have successful completed prerequisite phases.
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
            state, code = 'COMPLETED', (1 if stage == 'probe_no_server' else 0)
        elif status in ('FAILED', 'FAULT', 'TIMED_OUT', 'STOPPED'):
            state, code = 'COMPLETED', (0 if stage == 'probe_no_server' else 1)
    return {'stage': stage, 'state': state, 'exit_code': code,
            'capability': stage == 'probe_capability' and code == 0 and state == 'COMPLETED'}
