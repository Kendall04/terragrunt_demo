"""Protected WP3B orchestration. Trusted ports are injected by admin runtime code.

No AWS/process adapter, credentials, qualification writer or activation is supplied.
Execution ports must isolate payload files/processes from these objects, disable
credential/metadata endpoints and retain immutable source/image handles. A closed
environment alone is not an OS sandbox. Application output is never evidence.
"""
from abc import ABC, abstractmethod
import copy
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/qualification'))
import finalizer as contract

COMMANDS = {
    'dotnet_restore': ('dotnet', 'restore', './demo-api/terragrunt-demo.sln'),
    'dotnet_build': ('dotnet', 'build', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-restore'),
    'dotnet_test': ('dotnet', 'test', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-build', '--verbosity', 'normal'),
}
STAGES = ('source', *contract.REQUIRED_CHECKS, 'manifest_publish', 'manifest_readback', 'result_publish')
CONTEXT_KEYS = {'operation_id', 'project', 'build_id', 'source_commit', 'account', 'region', 'repository'}


class Rejected(ValueError):
    pass


def require(ok):
    if not ok:
        raise Rejected('E1_BUILD_SUPERVISION_REJECTED')


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys))


def environment(stage):
    # Entire environment, not an overlay. No ambient PATH/HOME/token inheritance.
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/work/home',
           'DOTNET_CLI_HOME': '/work/home', 'NUGET_PACKAGES': '/work/nuget',
           'DOTNET_NOLOGO': '1', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1',
           'AWS_EC2_METADATA_DISABLED': 'true'}
    if stage == 'probe_no_server':
        env.update({k: '1' for k in ('READINESS_PROBE_TIMEOUT_SECONDS',
                   'READINESS_PROBE_REQUEST_TIMEOUT_SECONDS', 'READINESS_PROBE_INTERVAL_SECONDS')})
    return env


class Control(ABC):
    """Authenticated dispatcher operation lookup; never application supplied."""
    @abstractmethod
    def operation(self, operation_id): ...


class Payload(ABC):
    """Trusted isolation adapter, not a payload object.

    acquire returns a sealed source snapshot at the requested path. All execution
    is confined to that attempt; the immutable source used by image_build must
    remain the acquired source (not build-generated substitutions). No supervisor
    objects, stores, credentials, host sockets or writable controller files are
    exposed to payloads. outcome is trusted process observation, never parsed JSON
    printed by the application. capability is trusted wrapper verification of the
    exact capability marker AND exit zero. no-server requires normal exit 1;
    launch failure, configuration exit 2 and outer timeout are not success.
    """
    @abstractmethod
    def acquire(self, repository, commit, workspace): ...
    @abstractmethod
    def execute(self, stage, argv, workspace, env, image): ...
    @abstractmethod
    def image_build(self, workspace, context, dockerfile, env): ...


class Images(ABC):
    """Content addition only, fixed destination. No policy/delete/admin methods.

    Stable attempt key binds the sealed built-image handle and destination.
    Retries return the original verified receipt; conflicting content fails.
    Receipt binds attempt, handle, registry, repository and resolved digest.
    No payload-provided digest, tag lookup or mutable latest adoption is allowed.
    """
    @abstractmethod
    def publish(self, attempt, handle, registry, repository): ...


class Manifests(ABC):
    """Protected candidate store; idempotent attempt + exact-byte binding.

    On retry return original write receipt, never another/latest version. Conflicts
    fail. Receipt is write-returned bucket/key/version; read_exact must echo all
    three and provide exact bytes and transport-verified checksum.
    """
    @abstractmethod
    def create(self, attempt, bucket, key, raw): ...
    @abstractmethod
    def read_exact(self, bucket, key, version_id): ...


class Records(ABC):
    """Supervisor-only atomic immutable attempt slot, shared by both envelopes.

    Application never receives this capability. create raises FileExistsError
    on occupied slot. read returns None only for authenticated absence; transport
    ambiguity raises. There are no update/delete/eligibility/qualification APIs.
    Retry after acknowledged or ambiguous write reads the exact original bytes.
    """
    @abstractmethod
    def create(self, attempt, raw): ...
    @abstractmethod
    def read(self, attempt): ...


def observed(outcome, stage):
    closed(outcome, {'stage', 'state', 'exit_code', 'capability'})
    require(outcome['stage'] == stage)
    require(outcome['state'] in ('COMPLETED', 'SKIPPED', 'NOT_RUN', 'UNKNOWN'))
    require(type(outcome['capability']) is bool)
    if outcome['state'] != 'COMPLETED':
        require(outcome['exit_code'] is None)
        return outcome['state']
    require(type(outcome['exit_code']) is int and 0 <= outcome['exit_code'] <= 255)
    expected_exit = 1 if stage == 'probe_no_server' else 0
    success = outcome['exit_code'] == expected_exit
    if stage == 'probe_capability':
        success = success and outcome['capability']
    return 'PASS' if success else 'FAIL'


def validate_terminal(value):
    schema = json.loads((ROOT / 'ci/schemas/e1-build-attempt.schema.json').read_text(encoding='utf-8'))
    contract._validate(value, schema, contract.CONTRACT)
    observed_source = value['observed_source_commit']
    require(observed_source is None or observed_source == value['source_commit'])
    require(value['terminal_stage'] in STAGES)
    require(value['terminal_stage'] != 'source' or observed_source is None)
    require(value['state'] == 'FAILED')
    return copy.deepcopy(value)


def runtime_image(value, account, region):
    """Admin protected config, not operation input; unavailable live facts stay null."""
    closed(value, {'owner', 'binding', 'uri', 'approval'})
    require(value['owner'] == 'SECURITY_ROOT_OWNED' and value['binding'] == 'build/release')
    require(value['approval'] == 'ADMIN_VERIFIED')
    require(type(value['uri']) is str and re.fullmatch(
        re.escape(account + '.dkr.ecr.' + region + '.amazonaws.com/e1-controller-build') +
        r'@sha256:[0-9a-f]{64}', value['uri']) is not None)
    return value['uri']


class Supervisor:
    def __init__(self, context, control, payload, images, manifests, records):
        closed(context, CONTEXT_KEYS | {'github_run_id', 'github_run_attempt', 'created_at', 'controller_image'})
        op = {k: context[k] for k in CONTEXT_KEYS}
        contract.validate('operation', {**op, 'schema': 'E1_RELEASE_OPERATION_V1', 'writer': 'RELEASE_GATEWAY'})
        for k in ('github_run_id', 'github_run_attempt'):
            require(type(context[k]) is str and re.fullmatch(r'[0-9]+', context[k]) is not None)
        require(type(context['created_at']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', context['created_at']) is not None)
        runtime_image(context['controller_image'], op['account'], op['region'])
        for port, interface in ((control, Control), (payload, Payload), (images, Images), (manifests, Manifests), (records, Records)):
            require(isinstance(port, interface))
        self.context = copy.deepcopy(context)
        self.control, self.payload, self.images, self.manifests, self.records = control, payload, images, manifests, records
        authority = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text(encoding='utf-8'))
        require(op['project'] == authority['controller_compute']['nodes']['build/release']['name'])
        self.repository = authority['ownership_closure']['resources']['neutral/repository']['name']
        self.bucket = authority['ownership_closure']['resources']['neutral/artifacts']['name'] + op['account']

    def run(self, wakeup):
        try:
            return self._run(wakeup)
        except Exception:
            raise Rejected('E1_BUILD_SUPERVISION_REJECTED') from None

    def persist(self, attempt, record):
        raw = contract.canonical(record)
        try:
            self.records.create(attempt, raw)
        except FileExistsError:
            pass
        require(self.records.read(attempt) == raw)
        return copy.deepcopy(record)

    def _run(self, wakeup):
        contract.validate('wakeup', wakeup)
        require(wakeup['operation_id'] == self.context['operation_id'])
        op = contract.validate('operation', self.control.operation(wakeup['operation_id']))
        require(all(op[k] == self.context[k] for k in CONTEXT_KEYS))
        common = {k: op[k] for k in CONTEXT_KEYS}
        attempt = op['operation_id'] + '/' + op['build_id']
        previous = self.records.read(attempt)
        if previous is not None:
            record = contract.decode(previous)
            if record.get('schema') == 'E1_BUILD_ATTEMPT_TERMINAL_V1':
                validate_terminal(record)
            else:
                contract.validate('result', record)
            require(all(record[k] == common[k] for k in CONTEXT_KEYS))
            require(contract.canonical(record) == previous)
            return record
        checks = dict.fromkeys(contract.REQUIRED_CHECKS, 'NOT_RUN')
        source = None
        stage = 'source'
        try:
            workspace = '/work/attempts/' + op['operation_id'] + '/' + op['build_id'].split(':')[1]
            acquired = self.payload.acquire(op['repository'], op['source_commit'], workspace)
            closed(acquired, {'repository', 'commit', 'workspace'})
            require(acquired['repository'] == op['repository'] and acquired['commit'] == op['source_commit'])
            require(acquired['workspace'] == workspace and str(PurePosixPath(workspace)) == workspace)
            source = acquired['commit']
            for stage, argv in COMMANDS.items():
                checks[stage] = 'UNKNOWN'
                checks[stage] = observed(self.payload.execute(stage, argv, workspace, environment(stage), None), stage)
                require(checks[stage] == 'PASS')
            stage = 'image_build'
            checks[stage] = 'UNKNOWN'
            built = self.payload.image_build(workspace, workspace + '/demo-api', workspace + '/demo-api/Dockerfile', environment(stage))
            closed(built, {'outcome', 'handle'})
            checks[stage] = observed(built['outcome'], stage)
            require(checks[stage] == 'PASS')
            require(type(built['handle']) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', built['handle']) is not None)
            stage = 'image_publish'
            checks[stage] = 'UNKNOWN'
            registry = op['account'] + '.dkr.ecr.' + op['region'] + '.amazonaws.com'
            image = self.images.publish(attempt, built['handle'], registry, self.repository)
            closed(image, {'attempt', 'handle', 'registry', 'repository', 'digest'})
            require(image['attempt'] == attempt and image['handle'] == built['handle'])
            require(image['registry'] == registry and image['repository'] == self.repository)
            require(type(image['digest']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', image['digest']) is not None)
            checks[stage] = 'PASS'
            uri = registry + '/' + self.repository + '@' + image['digest']
            candidate = {'schemaVersion': '1.0', 'app': 'demo-api', 'repository': op['repository'],
                         'gitSha': source, 'sourceBranch': 'develop', 'githubRunId': self.context['github_run_id'],
                         'githubRunAttempt': self.context['github_run_attempt'], 'createdAt': self.context['created_at'],
                         'image': {'registry': registry, 'repository': self.repository, 'tag': 'attempt-' + op['operation_id'],
                                   'digest': image['digest'], 'uri': uri},
                         'quality': {'dotnetTests': 'passed', 'dockerBuild': 'passed', 'scanStatus': 'unknown'}}
            legacy = json.loads((ROOT / 'ci/schemas/release-manifest.schema.json').read_text(encoding='utf-8'))
            contract._validate(candidate, legacy, {})
            raw = contract.canonical(candidate)
            key = 'releases/demo-api/by-digest/sha256-' + image['digest'][7:] + '.json'
            stage = 'manifest_publish'
            receipt = self.manifests.create(attempt, self.bucket, key, raw)
            closed(receipt, {'bucket', 'key', 'version_id'})
            require(receipt['bucket'] == self.bucket and receipt['key'] == key)
            manifest = {**receipt, 'sha256': contract.checksum(raw)}
            contract.validate('manifest', manifest)
            stage = 'manifest_readback'
            persisted = self.manifests.read_exact(self.bucket, key, receipt['version_id'])
            closed(persisted, {'bucket', 'key', 'version_id', 'bytes', 'sha256'})
            require(all(persisted[k] == receipt[k] for k in receipt))
            require(type(persisted['bytes']) is bytes and persisted['bytes'] == raw)
            require(persisted['sha256'] == contract.checksum(persisted['bytes']) == manifest['sha256'])
        except Exception:
            if stage in checks and checks[stage] == 'PASS':
                checks[stage] = 'FAIL'
            return self.terminal(attempt, common, source, checks, stage)
        # Exact artifact identity now exists; late probe failures retain it.
        for stage in ('probe_capability', 'probe_no_server'):
            try:
                argv = ('readiness-probe', '--check-capability') if stage == 'probe_capability' else ('readiness-probe',)
                checks[stage] = observed(self.payload.execute(stage, argv, workspace, environment(stage), uri), stage)
            except Exception:
                checks[stage] = 'UNKNOWN'
            if checks[stage] != 'PASS':
                break
        result = {**common, 'schema': 'E1_SUPERVISED_RESULT_V1',
                  'state': 'SUCCEEDED' if all(v == 'PASS' for v in checks.values()) else 'FAILED',
                  'checks': checks, 'image_repository': self.repository, 'image_digest': image['digest'],
                  'runtime_contract': contract.RUNTIME, 'manifest': manifest}
        contract.validate('result', result)
        try:
            return self.persist(attempt, result)
        except Exception:
            # If the write actually committed, an exact read can confirm it.
            # Otherwise a terminal record may occupy the same immutable slot.
            try:
                if self.records.read(attempt) == contract.canonical(result):
                    return copy.deepcopy(result)
            except Exception:
                raise Rejected('E1_BUILD_SUPERVISION_REJECTED') from None
            return self.terminal(attempt, common, source, checks, 'result_publish')

    def terminal(self, attempt, common, source, checks, stage):
        record = {**common, 'schema': 'E1_BUILD_ATTEMPT_TERMINAL_V1', 'writer': 'BUILD_SUPERVISOR',
                  'observed_source_commit': source, 'state': 'FAILED', 'terminal_stage': stage,
                  'checks': checks, 'classification': 'EXECUTION_OR_PUBLICATION_FAILED'}
        validate_terminal(record)
        return self.persist(attempt, record)
