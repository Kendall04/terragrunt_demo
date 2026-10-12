"""E15-D installed administrative handoff; SDK ports, never import-time I/O.

Only current administrator-owned WP5 configuration may select the pinned
installation. No identity, object path, adapter or approval comes from an event.
No installation/privilege/quietness is created by this module.
"""
import copy
import json
import re
from . import contract as c, dev_down as down, exact_destroy as x
from scripts import environment_mutation as e

MAX = 16777216


def installation_location(protected):
    return ('demo-release-artifacts-' + protected['account'],
            'lifecycle/' + x.BINDING + '/handoff-installation.json')


def approval_prefix(selected):
    bucket, key = x.approval_location(selected)
    return bucket, key.rsplit('/', 1)[0] + '/'


def storage_requirements(selected):
    """Installation contract/proposal only; NOT applied policies or new grants.

    Exact operation object ARNs. Identity policies plus bucket denies/ownership
    and service version/encryption readbacks must be accepted by security admin.
    """
    bucket, prefix = x.location(selected)
    admin_bucket, admin_prefix = approval_prefix(selected)
    objects = lambda b, keys: ['arn:aws:s3:::' + b + '/' + k for k in keys]
    artifacts = objects(bucket, [prefix + name for name in ('plan.bin', 'plan.json', 'prepared.json')])
    administrative = objects(admin_bucket, [admin_prefix + name for name in ('approval.json', 'selection.json')])
    decisions = objects(bucket, [prefix + name for name in ('decision.json', 'attempt.json')])
    return dict(artifact_objects=artifacts, administrative_objects=administrative, decision_objects=decisions,
        readers=['s3:GetObject', 's3:GetObjectVersion'], publisher=['s3:PutObject'],
        encryption='AES256', versioning='Enabled', conditional_create='IfNoneMatch=*',
        no_delete_or_overwrite=True, private=True, tls=True,
        approval_writer='EXISTING_SEPARATE_SECURITY_ADMIN_ONLY',
        artifact_writer='EXACT_INSTALLED_WP5_PREPARATION_OR_SECURITY_ADMIN',
        journal_writer='EXACT_INSTALLED_WP5_EXECUTOR_OR_AUTHENTICATED_WITHDRAWAL')


class Storage:
    """Private fixed-path version-pinned reads/conditional publication. No retries."""
    def __init__(self, s3, account):
        c.require(s3 is not None and type(account) is str and re.fullmatch('[0-9]{12}', account),
                  'protected storage and account required')
        self.s3, self.account = s3, account

    def get(self, ref, bucket, key):
        x.reference(ref, bucket, key)
        response = self.s3.get_object(Bucket=bucket, Key=key, VersionId=ref['version_id'],
                                      ExpectedBucketOwner=self.account)
        raw = response['Body'].read(MAX + 1)
        c.require(type(raw) is bytes and 0 < len(raw) <= MAX and response.get('VersionId') == ref['version_id']
                  and c.digest(raw) == ref['sha256'] and response.get('ServerSideEncryption') == 'AES256',
                  'exact private encrypted version bytes required')
        return raw

    def anchor(self, bucket, key):
        # Latest discovery is permitted ONLY for a fixed write-once installation
        # namespace. Re-read that exact returned version; never choose among plans.
        response = self.s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=self.account)
        raw = response['Body'].read(MAX + 1)
        c.require(type(raw) is bytes and 0 < len(raw) <= MAX, 'bounded protected anchor')
        ref = dict(bucket=bucket, key=key, version_id=x.version(response.get('VersionId')), sha256=c.digest(raw))
        c.require(self.get(ref, bucket, key) == raw, 'immutable anchor exact readback')
        return ref, raw

    def put(self, bucket, key, raw, binary=False):
        c.require(type(raw) is bytes and 0 < len(raw) <= MAX, 'bounded private publication')
        response = self.s3.put_object(Bucket=bucket, Key=key, Body=raw, IfNoneMatch='*',
            ExpectedBucketOwner=self.account, ServerSideEncryption='AES256',
            ContentType='application/octet-stream' if binary else 'application/json')
        ref = dict(bucket=bucket, key=key, version_id=x.version(response.get('VersionId')), sha256=c.digest(raw))
        c.require(self.get(ref, bucket, key) == raw, 'durable exact publication readback')
        return ref


def document(raw):
    value = json.loads(raw)
    c.require(c.canonical(value) == raw, 'canonical protected metadata')
    return value


def load_installation(storage, protected, value):
    selected = down.scope(value, protected)
    c.authorize(x.BINDING, value, protected, protected['installations'][value['revision']])
    ref = protected['bootstrap'].get('exact_destroy_handoff')
    bucket, key = installation_location(protected)
    record = document(storage.get(ref, bucket, key))
    c.keys(record, ('schema', 'binding', 'account', 'region', 'revision', 'source_commit',
                    'administrator_role', 'administrator_role_id', 'executor_role_id', 'storage_contract'),
           'installed handoff authority')
    c.require(record['schema'] == 'E15D_HANDOFF_INSTALLATION_V1' and
              all(record[k] == selected[k] for k in ('binding', 'account', 'region', 'revision', 'source_commit')),
              'exact installed handoff scope/source')
    role = record['administrator_role']
    c.require(type(role) is str and re.fullmatch('arn:aws:iam::' + selected['account'] + ':role/[A-Za-z0-9+=,.@_/-]+', role)
              and not role.rsplit('/', 1)[-1].startswith(('e1-request-', 'e1-controller-', 'e1-gateway-', 'demo-')),
              'separately held existing administrative role')
    for name in ('administrator_role_id', 'executor_role_id'):
        c.require(type(record[name]) is str and re.fullmatch('AROA[A-Z0-9]{17}', record[name]), 'installed unique role ID')
    c.require(record['administrator_role_id'] != record['executor_role_id'], 'administrative separation')
    # Contract is versioned with this package; installing this record requires
    # independent security-root verification of these guards, not a JSON flag.
    c.require(record['storage_contract'] == 'E15D_PRIVATE_VERSIONED_CONDITIONAL_NO_DELETE_V1',
              'accepted protected storage installation contract required')
    return copy.deepcopy(record)


class Handoff(x.ProtectedPlanChannel):
    """Concrete SDK adapter, admitted only from pinned admin-owned installation.

    sts/s3 are fixed SDK clients from approved code; fixtures replace them only
    inside hermetic tests. Public events cannot inject clients or a principal.
    """
    def __init__(self, s3, sts, protected, value, engine):
        c.require(sts is not None and engine is not None, 'verified identity/render adapters required')
        self.storage = Storage(s3, protected['account'])
        self.protected, self.value = copy.deepcopy(protected), copy.deepcopy(value)
        self.selected = down.scope(value, protected)
        self.installed = load_installation(self.storage, protected, value)
        self.sts, self.engine = sts, engine
        self.selection = None

    def scope(self, value, protected):
        c.require(value == self.value and protected == self.protected, 'exact immutable handoff request/configuration')
        return self.selected

    def session(self, administrator=False):
        response = self.sts.get_caller_identity()  # no env/CLI identity fallback
        if administrator is None:
            name = self.installed['administrator_role'].rsplit('/', 1)[-1]
            administrator = response.get('Arn', '').startswith('arn:aws:sts::' + self.selected['account'] + ':assumed-role/' + name + '/')
        role = self.installed['administrator_role'] if administrator else (
            'arn:aws:iam::' + self.selected['account'] + ':role/e1-controller-infra-high-risk-dev-exec')
        name = role.rsplit('/', 1)[-1]
        match = re.fullmatch('arn:aws:sts::' + self.selected['account'] + ':assumed-role/' +
                             re.escape(name) + '/([A-Za-z0-9+=,.@_-]+)', response.get('Arn', ''))
        unique = self.installed['administrator_role_id' if administrator else 'executor_role_id']
        c.require(response.get('Account') == self.selected['account'] and match is not None and
                  response.get('UserId') == unique + ':' + match[1], 'authenticated exact installed AWS role session')
        return dict(account=self.selected['account'], role_arn=role, principal_arn=response['Arn'])

    def administrator_role(self):return self.installed['administrator_role']
    def authenticate_admin(self):return self.session(True)

    def resolve(self):
        bucket, prefix = approval_prefix(self.selected)
        ref, raw = self.storage.anchor(bucket, prefix + 'selection.json')
        record = document(raw)
        c.keys(record, ('schema', 'scope_sha256', 'request_sha256', 'prepared', 'approval'), 'closed approval selection')
        c.require(record['schema'] == 'E15D_EXACT_SELECTION_V1' and
                  all(record[k] == self.selected[k] for k in ('scope_sha256', 'request_sha256')),
                  'exact operation/layer/plan selection')
        artifact_bucket, artifact_prefix = x.location(self.selected)
        x.reference(record['prepared'], artifact_bucket, artifact_prefix + 'prepared.json')
        x.reference(record['approval'], bucket, prefix + 'approval.json')
        if self.selection is not None:
            c.require(self.selection == (ref, record), 'conflicting or replaced immutable selection')
        self.selection = copy.deepcopy((ref, record))
        return record

    def read_prepared(self, value, protected):
        self.scope(value, protected)
        bucket, prefix = x.location(self.selected)
        if self.selection is None:
            # Before approval exists, authenticated admin acquires the single
            # write-once preparation. Executors must resolve selection first.
            self.authenticate_admin()
            ref, raw = self.storage.anchor(bucket, prefix + 'prepared.json')
        else:
            record = self.resolve()
            ref = record['prepared'];raw = self.storage.get(ref, bucket, prefix + 'prepared.json')
        manifest = document(raw)
        c.keys(manifest, ('schema', 'scope_sha256', 'packet'), 'prepared publication manifest')
        c.require(manifest['schema'] == 'E15D_PREPARED_V1' and manifest['scope_sha256'] == self.selected['scope_sha256'],
                  'exact preparation manifest')
        packet = manifest['packet']
        c.keys(packet, ('review', 'seal', 'artifacts', 'preparation_generation'), 'published E15-C packet')
        c.keys(packet['artifacts'], ('binary', 'json'), 'published exact artifacts')
        binary = self.storage.get(packet['artifacts']['binary'], bucket, prefix + 'plan.bin')
        plan = document(self.storage.get(packet['artifacts']['json'], bucket, prefix + 'plan.json'))
        self.prepared_reference = ref
        return dict(packet, binary=binary, plan=plan)

    def inspect_binary(self, binary):
        c.require(self.engine.request == self.value and self.engine.protected == self.protected,
                  'installed exact rendering engine')
        path = self.engine.directory / 'wp5-review.tfplan'
        c.require(not path.is_symlink(), 'fixed regular private plan')
        if not path.exists():
            with path.open('xb') as stream:stream.write(binary)
        c.require(path.is_file() and path.read_bytes() == binary, 'no rendering plan substitution')
        result = json.loads(self.engine.call(['show', '-json', 'wp5-review.tfplan']))
        c.require(path.read_bytes() == binary, 'saved binary unchanged during rendering')
        return result

    def current(self, value, protected):
        self.scope(value, protected)
        bucket = 'demo-release-artifacts-' + self.selected['account']
        response = self.storage.s3.get_object(Bucket=bucket, Key='lifecycle/' + x.BINDING + '/current.json',
                                              ExpectedBucketOwner=self.selected['account'])
        raw = response['Body'].read(1048577)
        c.require(0 < len(raw) <= 1048576 and json.loads(raw) == protected, 'current administrative configuration changed')
        backend = protected['layers'][value['layer']]['backend']
        response = self.storage.s3.get_object(Bucket=backend['bucket'], Key=backend['key'],
                                              ExpectedBucketOwner=self.selected['account'])
        state_raw = response['Body'].read(MAX + 1)
        c.require(0 < len(state_raw) <= MAX, 'bounded private state readback')
        state = json.loads(state_raw)
        c.require(type(state.get('lineage')) is str and type(state.get('serial')) is int and state['serial'] >= 0,
                  'state lineage/serial required')
        return dict(state=dict(lineage=state['lineage'], serial=state['serial'],
            version_id=x.version(response.get('VersionId')), sha256=c.digest(state_raw)),
            configuration_sha256=c.digest(c.canonical(protected)))

    def write_approval(self, value, approval):
        self.scope(value, self.protected);self.authenticate_admin()
        c.require(approval['approver'] == self.authenticate_admin(), 'same authenticated administrative session')
        c.require(getattr(self, 'prepared_reference', None) is not None, 'exact preparation acquired for review')
        bucket, prefix = approval_prefix(self.selected)
        ref = self.storage.put(bucket, prefix + 'approval.json', c.canonical(approval))
        selection = dict(schema='E15D_EXACT_SELECTION_V1', scope_sha256=self.selected['scope_sha256'],
            request_sha256=self.selected['request_sha256'], prepared=self.prepared_reference, approval=ref)
        # Publish last. Multi-object partial failures never imply approval ready;
        # no overwrite/retry/new candidate or distributed transaction is assumed.
        self.storage.put(bucket, prefix + 'selection.json', c.canonical(selection))
        c.require(self.resolve() == selection, 'durable exact selection required')
        return ref

    def approved_reference(self, value, protected):
        self.scope(value, protected);self.session(None)
        return self.resolve()['approval']

    def read_approval(self, reference):
        bucket, key = x.approval_location(self.selected)
        raw = self.storage.get(reference, bucket, key)
        return dict(reference=copy.deepcopy(reference), approval=document(raw))

    def require_down_quiescence(self, value, protected, authority):
        self.scope(value, protected);self.session(False)
        raise ValueError('E15D_DOWN_BLOCKED: ECS controller closure and NAT issued-effect settlement uninstalled')

    def publish_prepared(self, preparation, expires_at, now):
        """Internal protected preparation integration; no public planning route.

        Requires a distinct existing WP5 plan owner, not the teardown UUID. That
        owner must finish safely before execution acquires generation N+1. The
        approved preparation dispatch/installation route remains a prerequisite.
        """
        self.session(False)
        engine = self.engine
        c.require(type(preparation) is e.Authority and engine.authority is preparation and preparation.value is not None,
                  'protected preparation E2 owner required')
        preparation._check()
        planned = dict(self.value, operation_id=preparation.operation, operation='plan')
        c.request(x.BINDING, planned)
        c.require(preparation.binding == x.BINDING and preparation.operation != self.value['operation_id'] and
                  preparation.request_sha256 == c.digest(c.canonical(planned)), 'distinct exact read-only preparation operation')
        c.authorize(x.BINDING, planned, self.protected, engine.reference)
        c.require(engine.request == self.value and engine.protected == self.protected and engine.destroy is True,
                  'already prepared exact destroy runtime')
        engine.check_destroy_seal()
        binary = (engine.directory / 'wp5.tfplan').read_bytes()
        plan = self.inspect_binary(binary)
        current = self.current(self.value, self.protected)
        context = dict(schema='E15B_DESTROY_REVIEW_V1', scope_sha256=self.selected['scope_sha256'],
            created_at=now, expires_at=expires_at, binary_sha256=c.digest(binary), json_sha256=c.digest(c.canonical(plan)),
            state=current['state'], workspace='default')
        review = down.review(self.value, self.protected, binary, plan, context, now)
        c.require(engine.destroy_seal['json_sha256'] == context['json_sha256'], 'prepared JSON seal identity')
        preparation._check();engine.check_destroy_seal()
        c.require(self.current(self.value, self.protected) == current, 'state changed during publication preflight')
        bucket, prefix = x.location(self.selected)
        artifacts = dict(binary=self.storage.put(bucket, prefix + 'plan.bin', binary, binary=True),
                         json=self.storage.put(bucket, prefix + 'plan.json', c.canonical(plan)))
        packet = dict(review=review, seal=copy.deepcopy(engine.destroy_seal), artifacts=artifacts,
                      preparation_generation=preparation.value['generation'])
        preparation._check();engine.check_destroy_seal()
        c.require(self.current(self.value, self.protected) == current, 'state changed before preparation seal publication')
        return self.storage.put(bucket, prefix + 'prepared.json', c.canonical(
            dict(schema='E15D_PREPARED_V1', scope_sha256=self.selected['scope_sha256'], packet=packet)))


def executor(engine, s3, sts, clock):
    channel = Handoff(s3, sts, engine.protected, engine.request, engine)
    channel.session(False)
    journal = x.DecisionJournal(s3, down.scope(engine.request, engine.protected))
    return x.Execution(channel, journal, clock)
