"""E15-F dormant DEV NAT fence and durable fail-closed WP5 diagnostic.

No client creation, installation, inhibition mutation, executor termination,
E2 release, retry, Terraform or positive teardown authorization exists here.
An E2 read cannot revoke an EC2 request after dispatch (or after its last check).
"""
import copy
import re
import time
from abc import ABC, abstractmethod

from scripts import environment_mutation as e
from scripts.lifecycle import contract as c, dev_down
from scripts.recovery.nat import ACTIONS, MEMBERSHIP, Nat
from scripts.wp4d.nat_resolver import Resolver


VERBS = {'assign_eip': ('associate_address',),
         'change_rt': ('create_route', 'replace_route'),
         'disable_sdc': ('modify_instance_attribute',)}
READS = ('describe_instances', 'describe_network_interfaces', 'describe_addresses',
         'describe_route_tables', 'describe_launch_template_versions',
         'describe_instance_attribute', 'get_console_output')


def slots(config):
    """Use administrator-installed two-slot membership, never event metadata."""
    c.require(config['environment'] == 'dev', 'DEV NAT only')
    account, region = config['account'], config['region']
    c.require(type(account) is str and re.fullmatch('[0-9]{12}', account), 'account')
    c.require(type(region) is str and re.fullmatch('[a-z]{2}(?:-[a-z]+)+-[0-9]', region), 'region')
    value = copy.deepcopy(config['nat_slots'])
    Resolver('dev', value)  # existing two-slot uniqueness contract
    c.require(len({s['subnet'] for s in value}) == 2, 'distinct NAT subnets')
    for s in value:
        c.keys(s, ('environment', 'account', 'region', 'vpc', 'subnet', 'az', 'asg',
                   'eip', 'route_table', 'spec'), 'protected NAT slot')
        c.require(s['account'] == account and s['region'] == region and
                  s['spec']['tags'].get('Environment') == 'dev' and
                  s['spec']['tags'].get('Role') == 'nat', 'DEV membership')
        c.require(s['spec']['role'] == f'arn:aws:iam::{account}:role/demo-dev-nat-role' and
                  s['spec']['instance_profile'] ==
                  f'arn:aws:iam::{account}:instance-profile/demo-dev-nat-instance-profile', 'DEV profile')
    return value


class FencedEC2:
    """Dormant wrapper for the actual WP4D Nat transport's EC2 client.

    context must be the existing recovery.Nat.context, which independently
    validates current ASG/EC2/launch membership. The original journal owns
    attempts/ACKs/readbacks; this wrapper adds no resend or effect finality.
    Install on all three DEV duties/all callable versions before claiming coverage.
    CURRENT IAM cannot read E2 as a NAT handler; failure denies the mutation.
    """
    def __init__(self, client, store, config, action, context):
        c.require(action in ACTIONS and callable(context), 'installed NAT duty')
        self.members = slots(config)
        c.require(config.get('binding') == 'nat-recovery/nat-dev/' + action, 'exact duty binding')
        c.require(type(store) is e.Store and store.environment == 'dev' and
                  store.selected == 'application' and store.bucket ==
                  f'e1-wp4-dev-{config["account"]}-{config["region"]}', 'exact E2 read scope')
        self.client, self.store, self.action, self.context = client, store, action, context
        self.head, _ = store.read()
        c.require(self.head['state'] == 'RELEASED', 'NAT admission inhibited by ACTIVE E2')

    def check(self):
        head, _ = self.store.read()
        c.require(head == self.head and head['state'] == 'RELEASED', 'stale NAT admission generation')

    def __getattr__(self, name):
        c.require(name in READS or name in VERBS[self.action], 'narrow EC2 boundary')
        function = getattr(self.client, name)
        if name in READS:
            return function
        def send(**request):
            self.check()
            current = self.context()
            m = current['membership']
            c.keys(m, MEMBERSHIP, 'exact NAT membership')
            protected = {k: v for k, v in m.items() if k not in ('instance', 'eni')}
            c.require(protected in [{k: v for k, v in s.items() if k not in ('account', 'region')}
                                    for s in self.members], 'current member of protected DEV slot')
            expected = Nat.actions(self, current)[self.action]
            if self.action == 'change_rt':
                c.require(name == expected.pop('action'), 'exact route verb')
            c.require(request == expected, 'exact duty request')
            # Last read at the SDK boundary; a pause immediately AFTER this
            # check still permits dispatch. Never call this downstream fencing.
            self.check()
            return function(**copy.deepcopy(request))
        return send


class Observation(ABC):
    """Read-only protected port, NOT an installed/live AWS implementation.

    No caller payload supplies proof. Implementations must collect complete,
    exact independent reads and retain unavailable/unknown distinctions. SQS
    approximate counts and Lambda concurrency are diagnostics, never queue drain
    or executor/remote-call settlement evidence.
    """
    @abstractmethod
    def observe(self, scope, members, deadline):
        raise NotImplementedError


def readback(value, scope, members, started, ended):
    c.keys(value, ('environment', 'account', 'region', 'observed_at', 'rule',
                   'functions', 'queues', 'slots', 'effects'), 'NAT readback')
    c.require(all(value[k] == scope[k] for k in ('environment', 'account', 'region')), 'observation identity')
    c.require(type(value['observed_at']) is int and type(started) is int and
              type(ended) is int and started <= value['observed_at'] <= ended < started + 30, 'fresh bounded readback')
    account, region = scope['account'], scope['region']
    rule = f'arn:aws:events:{region}:{account}:rule/e1-wp4-dev-nat-launch'
    c.keys(value['rule'], ('arn', 'enabled'), 'exact NAT rule readback')
    c.require(value['rule']['arn'] == rule and type(value['rule']['enabled']) is bool, 'DEV rule')
    blockers = ['EXECUTOR_AND_DISPATCHED_EFFECT_SETTLEMENT_UNPROVED',
                'ALL_CALLABLE_VERSION_FENCE_INSTALLATION_UNPROVED',
                'ASG_SERVICE_ACTIVITY_FINALITY_UNPROVED']
    if value['rule']['enabled']: blockers.append('EVENTBRIDGE_ENABLED')
    c.require(type(value['functions']) is dict and set(value['functions']) == set(ACTIONS), 'all three duties')
    for action, function in value['functions'].items():
        c.keys(function, ('qualified_arn', 'reserved_concurrency'), 'function readback')
        c.require(type(function['qualified_arn']) is str and re.fullmatch(
            re.escape(f'arn:aws:lambda:{region}:{account}:function:e1-nat-recovery-nat-dev-{action}:') +
            '[1-9][0-9]*', function['qualified_arn']), 'exact DEV qualified function')
        c.require(type(function['reserved_concurrency']) is int and function['reserved_concurrency'] >= 0,
                  'function concurrency')
        if function['reserved_concurrency'] != 0: blockers.append('LAMBDA_ADMISSION_NOT_INHIBITED')
    expected_queues = {f'arn:aws:sqs:{region}:{account}:e1-wp4-dev-nat-{kind}-failed'
                       for kind in ('delivery', 'execution')}
    c.require(type(value['queues']) is dict and set(value['queues']) == expected_queues, 'both retained E13 queues')
    for counts in value['queues'].values():
        c.keys(counts, ('visible', 'not_visible', 'delayed'), 'queue diagnostic')
        c.require(all(type(n) is int and n >= 0 for n in counts.values()), 'queue counts')
        if any(counts.values()): blockers.append('DLQ_PENDING_EVIDENCE_REQUIRES_ADMIN_DIAGNOSIS')
    c.require(type(value['slots']) is dict and set(value['slots']) == {s['asg'] for s in members}, 'exact ASG slots')
    for member in members:
        s = value['slots'][member['asg']]
        c.keys(s, ('vpc', 'subnet', 'az', 'eip', 'route_table', 'min', 'max', 'desired',
                   'instances', 'activities', 'launch_suspended', 'association_eni',
                   'default_route_eni', 'route_state'), 'slot readback')
        c.require(all(s[k] == member[k] for k in ('vpc', 'subnet', 'az', 'eip', 'route_table')), 'slot identity')
        c.require(all(type(s[k]) is int and s[k] >= 0 for k in ('min', 'max', 'desired')) and
                  type(s['launch_suspended']) is bool and type(s['instances']) is list and
                  type(s['activities']) is list, 'ASG diagnostic')
        c.require(s['route_state'] in ('active', 'blackhole', 'absent') and
                  all(s[k] is None or type(s[k]) is str for k in ('association_eni', 'default_route_eni')),
                  'route/address diagnostic')
        for instance in s['instances']:
            c.keys(instance, ('instance', 'eni', 'state', 'source_dest_check'), 'nonsensitive instance diagnostic')
            c.require(type(instance['instance']) is str and type(instance['eni']) is str and
                      instance['state'] in ('Pending', 'InService', 'Terminating', 'Terminated') and
                      type(instance['source_dest_check']) is bool, 'instance/SDC diagnostic')
        for activity in s['activities']:
            c.keys(activity, ('id', 'status'), 'nonsensitive ASG activity diagnostic')
            c.require(type(activity['id']) is str and type(activity['status']) is str, 'activity identity/status')
        if not s['launch_suspended'] or s['min'] or s['desired']: blockers.append('ASG_NOT_INHIBITED')
        if s['instances'] or s['activities']: blockers.append('ASG_MEMBERS_OR_ACTIVITY_REMAIN')
        # This conservative drained snapshot requires no attached address/next
        # hop. It never instructs deletion/route removal or proves remote finality.
        if s['association_eni'] is not None or s['default_route_eni'] is not None or s['route_state'] != 'absent':
            blockers.append('NETWORK_ATTACHMENT_OR_ROUTE_UNSETTLED')
    c.require(type(value['effects']) is list, 'effect inventory')
    for effect in value['effects']:
        c.keys(effect, ('token', 'action', 'state'), 'effect diagnostic')
        c.require(effect['action'] in ACTIONS and effect['state'] in ('APPLIED', 'ABSENT', 'UNKNOWN', 'UNSETTLED')
                  and type(effect['token']) is str and effect['token'].startswith(
                      'dev/recovery/' + effect['action'] + '/'), 'effect scope')
        if effect['state'] in ('UNKNOWN', 'UNSETTLED'): blockers.append('PRIOR_EFFECT_UNSETTLED')
    c.require(len(c.canonical(value)) <= 65536, 'bounded nonsensitive diagnostic')
    return sorted(set(blockers))


class Quiescence:
    """WP5 seam: preserve original ACTIVE owner; record UNKNOWN before observing.

    records is existing WP5 Records at operations/<high-risk binding>/. No quiet
    boolean/hold release is published. Request repetition never clears an earlier
    unknown; diagnostics append immutable content-addressed observations. No
    SUCCESS/READY is representable under the current settlement architecture.
    """
    def __init__(self, authority, request, protected, nat_config, records, observation, now=time.time, operation=None):
        self.scope = dev_down.scope(request, protected)
        c.require(self.scope['layer'] == 'global', 'NAT networking teardown stage only')
        self.members = slots(nat_config)
        self.nat_configuration_sha256 = c.digest(c.canonical(nat_config))
        installed_ids = set(protected['layers']['global']['membership'].values())
        c.require(all(s[k] in installed_ids for s in self.members
                      for k in ('vpc', 'subnet', 'asg', 'eip', 'route_table')), 'WP5/NAT membership agreement')
        c.require(all(nat_config[k] == self.scope[k] for k in ('environment', 'account', 'region')), 'WP5/NAT identity')
        if operation is None:
            c.require(type(authority) is e.Authority and authority.store.environment == 'dev' and
                      authority.store.selected == 'application' and authority.store.bucket ==
                      f'e1-wp4-dev-{self.scope["account"]}-{self.scope["region"]}' and
                      authority.binding == self.scope['binding'] and authority.operation == self.scope['operation_id'] and
                      authority.request_sha256 == self.scope['request_sha256'], 'original WP5 owner')
        else:
            from scripts.lifecycle.operational import Operation
            c.require(type(operation) is Operation and operation.authority is authority
                and operation.requests[-1] == request and operation.protected == protected,
                'original whole DOWN NAT scope')
            operation.check()
        c.require(records.bucket == self.scope['backend']['bucket'] and
                  records.prefix == 'operations/' + self.scope['binding'] + '/', 'existing WP5 evidence location')
        c.require(isinstance(observation, Observation), 'protected observation port')
        authority._check()
        self.authority, self.records, self.observation, self.now = authority, records, observation, now
        self.owner = copy.deepcopy(authority.value)
        self.key = self.scope['operation_id'] + '/nat-quiescence'

    def check(self):
        self.authority._check()
        c.require(self.authority.value == self.owner, 'original operation owner/generation hold')

    def request(self):
        self.check()
        intent = dict(schema='E15F_NAT_QUIESCENCE_V1', scope=self.scope, e2=self.owner,
                      nat_slots_sha256=c.digest(c.canonical(self.members)),
                      nat_configuration_sha256=self.nat_configuration_sha256, state='UNKNOWN',
                      execution_authorized=False, settlement='UNPROVED')
        retained = self.records.read(self.key)
        if retained is None:
            try: self.records.create(self.key, intent)
            except Exception: pass  # Only exact durable readback settles write ACK.
            retained = self.records.read(self.key)
        c.require(retained == intent, 'durable unresolved NAT intent')
        self.check()
        return copy.deepcopy(intent)

    def inspect(self):
        intent = self.request()  # Persist UNKNOWN before any observation.
        blockers = ['READBACK_UNAVAILABLE_OR_CONTRADICTORY']
        observed = None
        try:
            started = int(self.now())
            candidate = self.observation.observe(copy.deepcopy(self.scope), copy.deepcopy(self.members), started + 30)
            blockers = readback(candidate, self.scope, self.members, started, int(self.now()))
            observed = copy.deepcopy(candidate)
            self.check()
        except Exception:
            observed = None
            blockers = ['READBACK_OR_CURRENT_OWNER_UNPROVED']
        report = dict(intent, observed=observed, blockers=blockers, aws_verified=False,
                      classification='PARTIALLY_READY', inhibition='UNPROVED' if observed is None else 'DIAGNOSTIC_ONLY')
        key = self.key + '/observations/' + c.digest(c.canonical(report))
        retained = self.records.read(key)
        if retained is None:
            try: self.records.create(key, report)
            except Exception: pass
            retained = self.records.read(key)
        c.require(retained == report, 'durable unresolved effect diagnostic')
        # Lost owner never gets a fresh permission; the durable UNKNOWN survives.
        return report

    def require_network_teardown(self):
        """Future WP5 pre-apply seam: durable evidence, then unconditional denial.

        Replacing this denial requires an accepted settlement mechanism and its
        installation/live proof, not a Boolean in an Observation implementation.
        """
        self.inspect()
        c.require(False, 'E15F_NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_REQUIRED')