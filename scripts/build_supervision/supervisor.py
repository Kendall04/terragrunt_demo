"""Protected WP3B orchestration. Trusted ports are injected by admin runtime code.

No AWS/process adapter, credentials, qualification writer or activation is supplied.
Execution ports must isolate payload files/processes from these objects, disable
credential/metadata endpoints and retain immutable source/image handles. A closed
environment alone is not an OS sandbox. Application output is never evidence.
"""
from abc import ABC, abstractmethod
import copy
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/qualification'))
import finalizer as contract

COMMANDS = {
    'dotnet_restore': ('dotnet', 'restore', './demo-api/terragrunt-demo.sln'),
    'dotnet_build': ('dotnet', 'build', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-restore'),
    'dotnet_test': ('dotnet', 'test', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-build', '--verbosity', 'normal'),
}
# Number of completed checks, and (where applicable) the failing check index.
TERMINAL_PREFIX = {'source': (0, None), 'dotnet_restore': (0, 0),
    'dotnet_build': (1, 1), 'dotnet_test': (2, 2), 'image_context': (3, None),
    'image_build': (3, 3), 'image_publish': (4, 4),
    'manifest_publish': (5, None), 'manifest_readback': (5, None),
    'result_publish': (5, None)}
STAGES = tuple(TERMINAL_PREFIX)
CONTEXT_KEYS = {'operation_id', 'project', 'build_id', 'source_commit', 'account', 'region', 'repository'}


class Rejected(ValueError):
    pass


class SourceIntegrity(Rejected):
    """Bounded diagnostic; never includes paths, file contents or adapter errors."""


def intact(ok):
    if not ok:
        raise SourceIntegrity('SOURCE_INTEGRITY_VIOLATION')


def source_path(relative):
    """Portable, unambiguous relative names; no links, ADS or platform aliases."""
    intact(type(relative) is str and len(relative) <= 1024)
    parts = relative.split('/')
    intact(parts[0] == 'demo-api')
    for part in parts:
        intact(bool(part) and part not in ('.', '..') and not part.endswith(('.', ' ')))
        intact(not any(ord(c) < 32 or c in '\\:<>"|?*' for c in part))
        intact(part.split('.')[0].upper() not in
               {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                *(f'LPT{i}' for i in range(1, 10))})
    return parts


def source_node(root, relative):
    """Read only after lstat of every component; reject reparse points/hardlinks.

    Host adapters must quiesce payload descendants between stages and isolate
    the supervisor and protected context. These checks are not an OS sandbox.
    """
    path = Path(root)
    root_stat = path.lstat()
    intact(stat.S_ISDIR(root_stat.st_mode) and not
           getattr(root_stat, 'st_file_attributes', 0) & 0x400)
    parts = source_path(relative)
    for index, part in enumerate(parts):
        path = path / part
        info = path.lstat()
        intact(not stat.S_ISLNK(info.st_mode) and not
               getattr(info, 'st_file_attributes', 0) & 0x400)
        if index < len(parts) - 1:
            intact(stat.S_ISDIR(info.st_mode))
    if stat.S_ISDIR(info.st_mode):
        return (relative, 'directory', 0, b'')
    intact(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    intact(info.st_size <= 16 * 1024 * 1024)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        intact((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino))
        raw = stream.read(16 * 1024 * 1024 + 1)
    intact(len(raw) == info.st_size)
    return (relative, 'file', 0o755 if info.st_mode & stat.S_IXUSR else 0o644, raw)


def source_tree(root):
    """Capture the committed export, not an execution tree with bin/obj output."""
    nodes = []
    names = set()
    size = 0
    def visit(relative):
        nonlocal size
        source_path(relative)
        intact(relative.casefold() not in names)
        names.add(relative.casefold())
        intact(not set(relative.split('/')) & {'bin', 'obj', '.git'})
        node = source_node(root, relative)
        nodes.append(node)
        size += len(node[3])
        intact(len(nodes) <= 10000 and size <= 64 * 1024 * 1024)
        if node[1] == 'directory':
            for child in sorted((Path(root) / relative).iterdir(), key=lambda p: p.name):
                visit(relative + '/' + child.name)
    visit('demo-api')
    paths = {n[0] for n in nodes if n[1] == 'file'}
    intact({'demo-api/Dockerfile', 'demo-api/.dockerignore',
            'demo-api/terragrunt-demo.sln',
            'demo-api/terragrunt-demo/terragrunt-demo.csproj'} <= paths)
    return tuple(nodes)


def source_seal(repository, commit, nodes):
    # Only portable metadata/digests enter the seal. Retained immutable bytes are
    # private supervisor data and never serialized into evidence or diagnostics.
    description = {'repository': repository, 'commit': commit, 'root': 'demo-api',
        'nodes': [{'path': p, 'type': kind, 'mode': mode,
                   'sha256': contract.checksum(raw) if kind == 'file' else None}
                  for p, kind, mode, raw in nodes]}
    return contract.checksum(contract.canonical(description))


def materialize_source(nodes, destination):
    """Fresh core-owned context from retained bytes, never copy the test workspace."""
    root = Path(destination)
    root.mkdir(exist_ok=False)
    for relative, kind, mode, raw in nodes:
        source_path(relative)
        path = root / relative
        if kind == 'directory':
            path.mkdir(exist_ok=False)
        else:
            with path.open('xb') as stream:
                stream.write(raw)
            path.chmod(mode)


def verify_execution(nodes, workspace):
    # Extra output is allowed here but never adopted into the retained snapshot.
    for expected in nodes:
        intact(source_node(workspace, expected[0]) == expected)


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

    acquire exports only committed demo-api content for the exact repository and
    commit at the requested path (no Git metadata or existing build outputs).
    The core captures/seals bytes, derives a separate execution workspace, checks
    it after every stage, and materializes/verifies a fresh image context itself.
    execute must return only after all payload descendants have stopped. The host
    must deny payload access to the core's memory, acquisition and image roots.
    image_build receives only the protected context, not the execution workspace.
    No supervisor
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
    def image_build(self, image_context, context, dockerfile, env): ...


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
    stage = value['terminal_stage']
    require(stage == 'source' or observed_source == value['source_commit'])
    prefix, failed = TERMINAL_PREFIX[stage]
    checks = [value['checks'][k] for k in contract.REQUIRED_CHECKS]
    require(all(v == 'PASS' for v in checks[:prefix]))
    if stage == 'result_publish':
        # Probes already ran: either all PASS, or a failed probe followed by NOT_RUN.
        stopped = False
        for value_check in checks[prefix:]:
            require(not stopped or value_check == 'NOT_RUN')
            stopped = stopped or value_check != 'PASS'
    else:
        if failed is not None:
            require(checks[failed] != 'PASS')
        require(all(v == 'NOT_RUN' for v in checks[prefix + (failed is not None):]))
    if value['classification'] == 'SOURCE_INTEGRITY_VIOLATION':
        require(stage in ('source', *COMMANDS, 'image_context', 'image_build'))
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
            with tempfile.TemporaryDirectory(prefix='e1-supervisor-') as directory:
                return self._run(wakeup, Path(directory))
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

    def _run(self, wakeup, directory):
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
            workspace = (directory / 'acquired').as_posix()
            Path(workspace).mkdir()
            acquired = self.payload.acquire(op['repository'], op['source_commit'], workspace)
            closed(acquired, {'repository', 'commit', 'workspace'})
            require(acquired['repository'] == op['repository'] and acquired['commit'] == op['source_commit'])
            require(acquired['workspace'] == workspace and str(PurePosixPath(workspace)) == workspace)
            snapshot = source_tree(workspace)
            seal = source_seal(op['repository'], op['source_commit'], snapshot)
            workspace = (directory / 'execution').as_posix()
            materialize_source(snapshot, workspace)
            verify_execution(snapshot, workspace)
            source = acquired['commit']
            for stage, argv in COMMANDS.items():
                checks[stage] = 'UNKNOWN'
                try:
                    checks[stage] = observed(self.payload.execute(stage, argv, workspace, environment(stage), None), stage)
                finally:
                    verify_execution(snapshot, workspace)
                require(checks[stage] == 'PASS')
            stage = 'image_context'
            image_context = (directory / 'image').as_posix()
            materialize_source(snapshot, image_context)
            intact(source_seal(op['repository'], source, source_tree(image_context)) == seal)
            stage = 'image_build'
            checks[stage] = 'UNKNOWN'
            built = self.payload.image_build(image_context, image_context + '/demo-api', image_context + '/demo-api/Dockerfile', environment(stage))
            intact(source_seal(op['repository'], source, source_tree(image_context)) == seal)
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
        except Exception as exc:
            if stage in checks and checks[stage] == 'PASS':
                checks[stage] = 'FAIL'
            integrity_stage = stage in ('source', *COMMANDS, 'image_context', 'image_build')
            integrity_error = isinstance(exc, (SourceIntegrity, FileNotFoundError, NotADirectoryError))
            classification = 'SOURCE_INTEGRITY_VIOLATION' if integrity_stage and integrity_error else 'EXECUTION_OR_PUBLICATION_FAILED'
            return self.terminal(attempt, common, source, checks, stage, classification)
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

    def terminal(self, attempt, common, source, checks, stage, classification='EXECUTION_OR_PUBLICATION_FAILED'):
        record = {**common, 'schema': 'E1_BUILD_ATTEMPT_TERMINAL_V1', 'writer': 'BUILD_SUPERVISOR',
                  'observed_source_commit': source, 'state': 'FAILED', 'terminal_stage': stage,
                  'checks': checks, 'classification': classification}
        validate_terminal(record)
        return self.persist(attempt, record)
