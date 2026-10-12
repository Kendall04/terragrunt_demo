"""E15-C exact DEV plan approval and immutable single-use WP5 journal.

Protected channels are trust boundaries, not caller JSON or installed adapters.
There is deliberately no live approval/artifact/quiescence adapter in this module.
"""
from abc import ABC, abstractmethod
import copy
import json
import re
import uuid
from . import contract as c, dev_down as down
from scripts import environment_mutation as e

BINDING = 'environment-lifecycle/infra-high-risk-dev'


def version(value):
    c.require(type(value) is str and value.strip() == value and value.lower() not in ('', 'null', 'latest'),
              'exact protected version')
    return value


def reference(value, bucket, key, digest=None):
    c.keys(value, ('bucket', 'key', 'version_id', 'sha256'), 'exact evidence reference')
    c.require(value['bucket'] == bucket and value['key'] == key, 'fixed protected evidence source')
    version(value['version_id'])
    c.require(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'evidence digest')
    if digest is not None:c.require(value['sha256'] == digest, 'exact evidence bytes')
    return value


def location(selected):
    return (f'e1-lifecycle-dev-{selected["account"]}-{selected["region"]}',
            'operations/' + BINDING + '/' + selected['operation_id'] + '/exact-destroy/')


class ProtectedPlanChannel(ABC):
    """Installed trusted ports; NEVER constructed from event/CLI supplied data.

    authenticate_admin must verify the current administrative execution context,
    including independently installed authority, account, role and principal.
    read_prepared/inspect_binary must acquire authenticated artifacts and render
    the same binary through approved Terraform. Local JSON/hashes do not suffice.
    Approval publication uses existing separately authenticated admin authority.
    Current-state reads and down quiescence must be independently proven. No
    subclass, SDK implementation or installation is provided by production here.
    """
    @abstractmethod
    def administrator_role(self):raise NotImplementedError
    @abstractmethod
    def authenticate_admin(self):raise NotImplementedError
    @abstractmethod
    def read_prepared(self, value, protected):raise NotImplementedError
    @abstractmethod
    def inspect_binary(self, binary):raise NotImplementedError
    @abstractmethod
    def write_approval(self, value, approval):raise NotImplementedError
    @abstractmethod
    def approved_reference(self, value, protected):raise NotImplementedError
    @abstractmethod
    def read_approval(self, reference):raise NotImplementedError
    @abstractmethod
    def current(self, value, protected):raise NotImplementedError
    @abstractmethod
    def require_down_quiescence(self, value, protected, authority):raise NotImplementedError


def admin(channel, selected, observed=None):
    c.require(isinstance(channel, ProtectedPlanChannel), 'independently installed protected plan channel')
    role = channel.administrator_role()
    c.require(type(role) is str and re.fullmatch('arn:aws:iam::' + selected['account'] + ':role/[A-Za-z0-9+=,.@_/-]+', role),
              'installed administrator role in exact account')
    identity = channel.authenticate_admin() if observed is None else observed
    c.keys(identity, ('account', 'role_arn', 'principal_arn'), 'verified administrative context')
    c.require(identity['account'] == selected['account'] and identity['role_arn'] == role,
              'exact independently authenticated administrator')
    # An AWS role session must match the independently installed role name;
    # IAM paths are absent from STS assumed-role principal ARNs.
    name = role.rsplit('/', 1)[-1]
    c.require(type(identity['principal_arn']) is str and re.fullmatch(
        'arn:aws:sts::' + selected['account'] + ':assumed-role/' + re.escape(name) + '/[A-Za-z0-9+=,.@_-]+',
        identity['principal_arn']), 'attributable administrative session')
    return copy.deepcopy(identity)


def evidence(channel, value, protected, now):
    c.require(isinstance(channel, ProtectedPlanChannel), 'protected acquisition required')
    packet = channel.read_prepared(value, protected)
    c.keys(packet, ('binary', 'plan', 'review', 'seal', 'artifacts', 'preparation_generation'), 'prepared evidence')
    review = packet['review']
    rebuilt = down.review(value, protected, packet['binary'], packet['plan'], review['context'], now)
    c.require(review == rebuilt, 'unaltered exact E15-B review')
    c.require(c.canonical(channel.inspect_binary(packet['binary'])) == c.canonical(packet['plan']),
              'JSON must be rendered from exact binary by protected acquisition')
    c.keys(packet['seal'], ('binary_sha256', 'json_sha256', 'context_sha256'), 'prepared runtime seal')
    c.require(packet['seal']['binary_sha256'] == review['context']['binary_sha256'] and
              packet['seal']['json_sha256'] == review['context']['json_sha256'] and
              type(packet['seal']['context_sha256']) is str and
              re.fullmatch('[0-9a-f]{64}', packet['seal']['context_sha256']), 'exact sealed context')
    generation = packet['preparation_generation']
    c.require(type(generation) is int and 0 <= generation < 2**63 - 1, 'preparation ownership generation')
    bucket, prefix = location(review['scope'])
    c.keys(packet['artifacts'], ('binary', 'json'), 'exact artifact versions')
    reference(packet['artifacts']['binary'], bucket, prefix + 'plan.bin', c.digest(packet['binary']))
    reference(packet['artifacts']['json'], bucket, prefix + 'plan.json', c.digest(c.canonical(packet['plan'])))
    return copy.deepcopy(packet)


def approval_location(selected):
    return ('demo-release-artifacts-' + selected['account'],
            'lifecycle/' + BINDING + '/destroy/' + selected['operation_id'] + '/approval.json')


def issue(channel, value, protected, confirmations, issued_at, expires_at, now):
    selected = down.scope(value, protected)
    c.authorize(BINDING, value, protected, protected['installations'][value['revision']])
    identity = admin(channel, selected)
    if value['layer'] == 'data':
        c.require(confirmations == protected['teardown_approvals'].get('dev-sql-loss/' + value['operation_id']),
                  'same independently protected E15-B SQL consent')
        down.check_data_consent(value, protected, now)
    packet = evidence(channel, value, protected, now)
    down.confirm(selected, confirmations, now)
    current = channel.current(value, protected)
    c.keys(current, ('state', 'configuration_sha256'), 'current approval applicability')
    c.require(current == dict(state=packet['review']['context']['state'],
        configuration_sha256=c.digest(c.canonical(protected))), 'stale preparation before approval')
    c.require(type(now) is int and type(issued_at) is int and type(expires_at) is int and 0 <= issued_at <= now < expires_at
              <= min(packet['review']['context']['expires_at'], confirmations['expires_at']), 'explicit current approval window')
    approval = dict(schema='E15C_DESTROY_APPROVAL_V1', state='APPROVED', review=packet['review'],
        seal=packet['seal'], artifacts=packet['artifacts'], expected_generation=packet['preparation_generation'] + 1,
        configuration_sha256=c.digest(c.canonical(protected)), confirmations=copy.deepcopy(confirmations),
        approver=identity, issued_at=issued_at, expires_at=expires_at)
    ref = channel.write_approval(value, copy.deepcopy(approval))
    bucket, key = approval_location(selected)
    reference(ref, bucket, key, c.digest(c.canonical(approval)))
    c.require(channel.read_approval(ref) == {'reference': ref, 'approval': approval}, 'durable exact approval readback')
    return copy.deepcopy(ref)


def validate(channel, value, protected, now):
    selected = down.scope(value, protected)
    c.authorize(BINDING, value, protected, protected['installations'][value['revision']])
    c.require(isinstance(channel, ProtectedPlanChannel), 'protected approval channel required')
    ref = channel.approved_reference(value, protected)
    bucket, key = approval_location(selected)
    reference(ref, bucket, key)
    observed = channel.read_approval(ref)
    c.keys(observed, ('reference', 'approval'), 'exact authenticated approval observation')
    c.require(observed['reference'] == ref, 'approval version substituted')
    a = observed['approval']
    c.keys(a, ('schema', 'state', 'review', 'seal', 'artifacts', 'expected_generation', 'configuration_sha256',
               'confirmations', 'approver', 'issued_at', 'expires_at'), 'closed approval record')
    c.require(c.digest(c.canonical(a)) == ref['sha256'] and a['schema'] == 'E15C_DESTROY_APPROVAL_V1'
              and a['state'] == 'APPROVED', 'exact approved protected bytes')
    admin(channel, selected, a['approver'])  # provenance comes from protected channel, never these strings alone
    c.require(type(now) is int and type(a['issued_at']) is int and type(a['expires_at']) is int
              and 0 <= a['issued_at'] <= now < a['expires_at'], 'current approval')
    packet = evidence(channel, value, protected, now)
    c.require(all(a[k] == packet[k] for k in ('review', 'seal', 'artifacts')) and
              a['expected_generation'] == packet['preparation_generation'] + 1 and
              type(a['expected_generation']) is int, 'exact reviewed plan and generation')
    c.require(a['configuration_sha256'] == c.digest(c.canonical(protected)), 'installed configuration unchanged')
    down.confirm(selected, a['confirmations'], now)
    if value['layer'] == 'data':
        c.require(a['confirmations'] == protected['teardown_approvals'].get('dev-sql-loss/' + value['operation_id']),
                  'SQL consent changed or withdrawn')
        down.check_data_consent(value, protected, now)
    c.require(a['expires_at'] <= min(a['review']['context']['expires_at'], a['confirmations']['expires_at']),
              'approval cannot outlive evidence/consent')
    return copy.deepcopy(observed), packet


class DecisionJournal:
    """Uses existing WP5 own-prefix immutable writes; no update/delete/retry.

    Decision slots are keyed by operation, NOT approval version or generation.
    Claim and authenticated withdrawal compete for the same If-None-Match slot.
    A failed/lost write acknowledgement burns the attempt; no optimistic resend.
    Live S3 semantics and deletion/admin controls remain installation prerequisites.
    """
    def __init__(self, s3, selected):
        self.s3 = s3
        self.bucket, self.prefix = location(selected)

    def put_once(self, suffix, record):
        c.require(suffix in ('decision', 'attempt'), 'fixed WP5 journal stage')
        raw = c.canonical(record)
        c.require(len(raw) <= 65536, 'bounded private decision metadata')
        key = self.prefix + suffix + '.json'
        response = self.s3.put_object(Bucket=self.bucket, Key=key, Body=raw,
                                     IfNoneMatch='*', ContentType='application/json')
        exact = dict(bucket=self.bucket, key=key, version_id=version(response.get('VersionId')), sha256=c.digest(raw))
        observed = self.s3.get_object(Bucket=self.bucket, Key=key)
        c.require(observed.get('VersionId') == exact['version_id'] and
                  observed['Body'].read(65537) == raw, 'exact immutable journal readback')
        return exact

    def read(self, suffix):
        c.require(suffix in ('decision', 'attempt'), 'fixed WP5 journal stage')
        try:observed = self.s3.get_object(Bucket=self.bucket, Key=self.prefix + suffix + '.json')
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):return None
            raise
        version(observed.get('VersionId'));raw = observed['Body'].read(65537)
        c.require(0 < len(raw) <= 65536, 'bounded journal')
        value = json.loads(raw)
        c.require(c.canonical(value) == raw, 'canonical journal')
        return value


def withdraw(channel, value, protected, journal, now):
    selected = down.scope(value, protected)
    bucket, prefix = location(selected)
    c.require(type(journal) is DecisionJournal and journal.bucket == bucket and journal.prefix == prefix,
              'exact withdrawal journal scope')
    observed, _ = validate(channel, value, protected, now)
    identity = admin(channel, down.scope(value, protected))
    return journal.put_once('decision', dict(state='WITHDRAWN', approval=observed['reference'],
                                            approver=identity, withdrawn_at=now))


class Execution:
    """Internal protected executor integration, no caller-selected path or send API.

    No live adapter is wired by runtime.execute. A default installed runtime
    therefore denies DEV destruction. Trust-port fixtures are only offline proof.
    """
    def __init__(self, channel, journal, clock):
        c.require(isinstance(channel, ProtectedPlanChannel) and type(journal) is DecisionJournal,
                  'installed exact approval and journal ports required')
        self.channel, self.journal, self.clock = channel, journal, clock
        self.consumer = str(uuid.uuid4())  # executor-generated, never caller supplied
        self.loaded = None

    def load(self, engine):
        observed, packet = validate(self.channel, engine.request, engine.protected, self.clock())
        c.require(self.journal.bucket == location(packet['review']['scope'])[0] and
                  self.journal.prefix == location(packet['review']['scope'])[1], 'exact journal domain')
        c.require(engine.destroy_context() == packet['seal']['context_sha256'], 'prepared context still installed')
        # The path is fixed inside the verified package; never supplied by an event.
        path = engine.directory / 'wp5.tfplan'
        c.require(not path.exists() and not path.is_symlink(), 'no pre-existing substitute plan')
        path.write_bytes(packet['binary'])
        shown = json.loads(engine.call(['show', '-json', 'wp5.tfplan']))
        c.require(c.canonical(shown) == c.canonical(packet['plan']), 'executor inspects approved exact binary')
        engine.destroy_seal = copy.deepcopy(packet['seal'])
        engine.check_destroy_seal()
        self.loaded = observed
        return shown

    def before_dispatch(self, engine):
        c.require(self.loaded is not None, 'exact approved artifact load required')
        observed, packet = validate(self.channel, engine.request, engine.protected, self.clock())
        c.require(observed == self.loaded, 'approval changed after load')
        engine.check_destroy_seal()
        authority = engine.authority
        c.require(type(authority) is e.Authority and authority.value is not None, 'E2 owner required')
        authority._check()  # original owner/generation, never acquire or takeover here
        operation = getattr(engine, 'down_operation', None)
        if operation is None:
            c.require(authority.binding == BINDING and authority.operation == engine.request['operation_id']
                      and authority.request_sha256 == c.digest(c.canonical(engine.request)),
                      'approved exact E2 operation')
        else:
            from .operational import Operation
            c.require(type(operation) is Operation, 'internal whole DOWN context only')
            operation.owns_request(engine.request, engine.protected, authority)
        c.require(authority.value['generation'] == observed['approval']['expected_generation'],
                  'approved original E2 generation')
        current = self.channel.current(engine.request, engine.protected)
        c.keys(current, ('state', 'configuration_sha256'), 'protected current applicability')
        c.require(current['state'] == packet['review']['context']['state'] and
                  current['configuration_sha256'] == observed['approval']['configuration_sha256'],
                  'state lineage/serial/version/bytes or configuration changed')
        # Missing accepted ECS closure/NAT effect settlement always blocks.
        self.channel.require_down_quiescence(engine.request, engine.protected, authority)
        c.quiescent(engine.observe('dev'), 'dev')
        # Re-read approval, expiry, artifacts, state and owner after potentially
        # slow quiescence reads; this does not cancel an effect after dispatch.
        final, _ = validate(self.channel, engine.request, engine.protected, self.clock())
        c.require(final == observed and self.channel.current(engine.request, engine.protected) == current,
                  'approval/applicability changed during readbacks')
        authority._check();engine.check_destroy_seal()
        claim = dict(state='CONSUMPTION_CLAIMED', approval=observed['reference'],
            consumer=self.consumer, generation=authority.value['generation'],
            request_sha256=c.digest(c.canonical(engine.request)))
        receipt = self.journal.put_once('decision', claim)
        c.require(self.channel.current(engine.request, engine.protected) == current, 'state changed after consumption claim')
        # A crash here leaves consumed/not-attempted, never a reusable approval.
        attempt = dict(state='EXECUTION_ATTEMPTED', decision=receipt, consumer=self.consumer,
                       binary_sha256=engine.destroy_seal['binary_sha256'])
        self.journal.put_once('attempt', attempt)
        authority._check();engine.check_destroy_seal()
        c.require(self.clock() < final['approval']['expires_at'], 'approval expired before dispatch')
