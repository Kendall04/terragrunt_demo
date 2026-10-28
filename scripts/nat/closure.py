"""E15-H bounded cooperative NAT admission. No installed identity or AWS client.

Only a separately approved narrow coordinator may write the head. Handlers have
no raw storage/E2 write authority. An injected port is not installed proof.
"""
import copy
import json
import re
import threading
from abc import ABC, abstractmethod
from scripts import environment_mutation as e
from scripts.lifecycle import contract as c
from scripts.normal_delivery import authorization as a
from scripts.recovery.ports import NatRuntime
from scripts.recovery.nat import ACTIONS

KEY = 'nat-admission/dev/head.json'
LIMIT = 128


def scope(config):
    # Lazy import avoids the WP5 diagnostic seam's circular import.
    from scripts.nat.scope import slots
    slots(config)
    return dict(environment='dev', account=config['account'], region=config['region'],
                configuration_sha256=c.digest(c.canonical(config)))


def initial(config, released, epoch):
    """Administrator seed format only; runtime cannot create or reopen it."""
    e.identity(epoch)
    e.validate(released, 'dev', 'application')
    c.require(released['state'] == 'RELEASED', 'released anchor')
    return dict(schema='E15H_NAT_ADMISSION_V1', scope=scope(config), epoch=epoch,
                revision=0, anchor=copy.deepcopy(released), state='OPEN', closure=None, permits={})


class Head:
    """Versioned single-object CAS; no delete, initialize, expiry or reopen.

    ETag is the conditional token, VersionId is retained evidence, monotone
    revision prevents content ABA. Lost ACK only settles by exact readback.
    Contention denies this call; never resend a mutation or blind retry a write.
    """
    def __init__(self, s3, config):
        self.s3, self.selected = s3, scope(config)
        self.bucket = f'e1-wp4-dev-{config["account"]}-{config["region"]}'

    def read(self):
        response = self.s3.get_object(Bucket=self.bucket, Key=KEY,
                                     ExpectedBucketOwner=self.selected['account'])
        raw = response['Body'].read(262145)
        value = json.loads(raw)
        c.require(len(raw) <= 262144 and c.canonical(value) == raw, 'canonical bounded head')
        a.version(response.get('VersionId'))
        c.require(response.get('ServerSideEncryption') == 'AES256' and
                  type(response.get('ETag')) is str and bool(response['ETag']), 'protected head')
        c.keys(value, ('schema', 'scope', 'epoch', 'revision', 'anchor', 'state', 'closure', 'permits'), 'head')
        c.require(value['schema'] == 'E15H_NAT_ADMISSION_V1' and value['scope'] == self.selected,
                  'exact DEV head scope')
        e.identity(value['epoch']); e.validate(value['anchor'], 'dev', 'application')
        c.require(value['anchor']['state'] == 'RELEASED' and type(value['revision']) is int and
                  0 <= value['revision'] < 2**63 and value['state'] in ('OPEN', 'CLOSED'), 'head state')
        c.require((value['closure'] is None) == (value['state'] == 'OPEN'), 'closure state')
        if value['closure'] is not None:
            c.keys(value['closure'], ('owner', 'operation_sha256', 'global_request_sha256'), 'closure binding')
            e.validate(value['closure']['owner'], 'dev', 'application')
            c.require(value['closure']['owner']['state'] == 'ACTIVE', 'original active owner')
            for name in ('operation_sha256', 'global_request_sha256'):
                a.match('[0-9a-f]{64}', value['closure'][name])
        c.require(type(value['permits']) is dict and len(value['permits']) <= LIMIT, 'bounded retained permits')
        for token, permit in value['permits'].items():
            c.keys(permit, ('action', 'executor', 'request_sha256', 'state', 'evidence'), 'permit')
            c.require(permit['action'] in ACTIONS and re.fullmatch(
                'dev/recovery/' + permit['action'] + '/[0-9a-f-]{36}/' + permit['action'], token), 'E13 token')
            e.identity(token.split('/')[-2])
            a.match('[0-9a-f]{64}', permit['request_sha256'])
            c.require(permit['state'] in ('ADMITTED', 'DISPATCHED', 'CANCELLED', 'SEALED') and
                      type(permit['executor']) is dict, 'permit state')
            c.require((permit['evidence'] is None) == (permit['state'] in ('ADMITTED', 'DISPATCHED')),
                      'terminal evidence')
        return value, dict(etag=response['ETag'], version_id=response['VersionId'],
                           sha256=c.digest(raw))

    def exchange(self, previous, ref, value):
        c.require(value['revision'] == previous['revision'] + 1, 'monotone revision')
        try:
            self.s3.put_object(Bucket=self.bucket, Key=KEY, Body=c.canonical(value),
                IfMatch=ref['etag'], ExpectedBucketOwner=self.selected['account'], ServerSideEncryption='AES256')
        except Exception:
            pass
        retained, result = self.read()
        c.require(retained == value, 'CAS conflict or ambiguous write; no blind retry')
        return retained, result


class Authentication(ABC):
    """Protected coordinator identity port, never an EventBridge payload.

    Must authenticate a caller's role unique ID, action, qualified immutable
    version/package and invocation incarnation. No implementation is installed.
    Interface instances and offline doubles cannot certify this property.
    """
    @abstractmethod
    def executor(self, action):
        raise NotImplementedError


class Coordinator:
    """One finite NAT epoch; no scheduler, E2 writer or lifecycle takeover."""
    def __init__(self, head, e2, config, authentication, versions):
        c.require(type(head) is Head and type(e2) is e.Store and isinstance(authentication, Authentication),
                  'protected coordinator ports')
        self.selected = scope(config)
        c.require(head.selected == self.selected and e2.environment == 'dev' and
                  e2.selected == 'application' and e2.bucket == head.bucket, 'exact E2 read scope')
        c.require(type(versions) is dict and set(versions) == set(ACTIONS), 'all duties publication')
        self.head, self.e2, self.authentication = head, e2, authentication
        self.versions = copy.deepcopy(versions)

    def executor(self, action):
        c.require(action in ACTIONS, 'installed duty')
        identity = self.authentication.executor(action)
        c.keys(identity, ('qualified_arn', 'package_sha256', 'role_id', 'invocation_id'), 'authenticated executor')
        prefix = f'arn:aws:lambda:{self.selected["region"]}:{self.selected["account"]}:function:e1-nat-recovery-nat-dev-{action}:'
        c.require(type(identity['qualified_arn']) is str and re.fullmatch(re.escape(prefix)+'[1-9][0-9]*',
                  identity['qualified_arn']), 'immutable DEV version')
        a.match('[0-9a-f]{64}', identity['package_sha256'])
        a.match('AROA[A-Z0-9]{17}', identity['role_id']); e.identity(identity['invocation_id'])
        publication = {k:v for k,v in identity.items() if k != 'invocation_id'}
        c.require(publication in self.versions[action], 'stale or uninstrumented version')
        return copy.deepcopy(identity)

    def admit(self, action, token, request):
        executor = self.executor(action)
        e.identity(token.split('/')[-2])
        c.require(token == 'dev/recovery/'+action+'/'+token.split('/')[-2]+'/'+action, 'exact E13 attempt')
        prior, ref = self.head.read(); anchor, _ = self.e2.read()
        c.require(prior['state'] == 'OPEN' and anchor == prior['anchor'] and anchor['state'] == 'RELEASED',
                  'admission closed or E2 changed')
        c.require(token not in prior['permits'] and len(prior['permits']) < LIMIT, 'duplicate or saturated epoch')
        value = copy.deepcopy(prior); value['revision'] += 1
        value['permits'][token] = dict(action=action, executor=executor,
            request_sha256=c.digest(c.canonical(request)), state='ADMITTED', evidence=None)
        self.head.exchange(prior, ref, value)  # ADMISSION LINEARIZATION POINT
        return executor

    def transition(self, token, executor, expected, target, evidence=None):
        prior, ref = self.head.read()
        c.require(token in prior['permits'], 'durable admission required')
        row = prior['permits'][token]
        c.require(row['executor'] == executor and self.executor(row['action']) == executor and
                  row['state'] == expected, 'same authenticated single-use executor')
        c.require((expected, target) in (('ADMITTED', 'DISPATCHED'), ('ADMITTED', 'CANCELLED'),
                                       ('DISPATCHED', 'SEALED')), 'closed transition vocabulary')
        if target == 'DISPATCHED':
            anchor, _ = self.e2.read()
            c.require(prior['state'] == 'OPEN' and anchor == prior['anchor'], 'dispatch closed')
        c.require((evidence is None) == (target == 'DISPATCHED'), 'terminal evidence required')
        value = copy.deepcopy(prior); value['revision'] += 1
        value['permits'][token].update(state=target, evidence=copy.deepcopy(evidence))
        return self.head.exchange(prior, ref, value)

    def close(self, authority, scope_value, operation_sha256):
        c.require(type(authority) is e.Authority and authority.store is self.e2 and
                  authority.binding == 'environment-lifecycle/infra-high-risk-dev', 'original DEV owner')
        authority._check(); owner = copy.deepcopy(authority.value)
        c.require(all(scope_value[k] == self.selected[k] for k in ('environment','account','region')) and
                  scope_value['layer'] == 'global' and
                  scope_value['binding'] == authority.binding and
                  scope_value['root'] == 'terraform/modules/target/dev/global', 'exact network child')
        a.match('[0-9a-f]{64}', operation_sha256)
        closure = dict(owner=owner, operation_sha256=operation_sha256,
                       global_request_sha256=scope_value['request_sha256'])
        prior, ref = self.head.read()
        c.require(owner['generation'] == prior['anchor']['generation'] + 1, 'original next E2 generation')
        if prior['state'] == 'CLOSED':
            c.require(prior['closure'] == closure, 'foreign or stale closure')
            authority._check(); return prior, ref
        value = copy.deepcopy(prior); value.update(state='CLOSED', closure=closure, revision=prior['revision']+1)
        result = self.head.exchange(prior, ref, value)  # CLOSURE LINEARIZATION POINT
        authority._check(); return result

    def inspect(self, authority, scope_value, operation_sha256):
        value, ref = self.close(authority, scope_value, operation_sha256)
        pending = {token:row['state'] for token,row in value['permits'].items()
                   if row['state'] not in ('CANCELLED','SEALED')}
        effects = {token:row['evidence'] for token,row in value['permits'].items() if row['state']=='SEALED'}
        return dict(head=ref, closure=value['closure'], admission='CLOSED', pending=pending,
                    cooperative_executors='SEALED' if not pending else 'UNKNOWN', effects=effects,
                    effect_finality='UNPROVED', callable_coverage='UNPROVED', installed=False)


class DispatchEvidence:
    """Narrow real EC2 boundary: retain sanitized response identity in E13.

    Missing service metadata is explicitly unattributed. A returned response is
    neither cancellation nor a terminal remote-effect certificate. No resend.
    """
    def __init__(self, client, records, action):
        self.client, self.records, self.action = client, records, action
        self.token = self.request_sha256 = None
        self.request = None
        # Local single-use protection supplements the durable coordinator;
        # this mutex is never a distributed admission/closure authority.
        self.mutex = threading.Lock()

    def __getattr__(self, name):
        from scripts.nat.scope import READS, VERBS
        c.require(name in READS or name in VERBS[self.action], 'closed EC2 duty')
        function = getattr(self.client, name)
        if name in READS: return function
        def call(**request):
            with self.mutex:
                c.require(self.token is not None, 'durable single-use dispatch required')
                expected = copy.deepcopy(self.request)
                if self.action == 'change_rt':
                    c.require(name == expected.pop('action'), 'exact route verb')
                c.require(request == expected, 'exact admitted SDK request')
                token, request_sha256 = self.token, self.request_sha256
                self.token = None  # Consume BEFORE dispatch; exceptions cannot re-arm.
            response = function(**request)
            metadata = response.get('ResponseMetadata', {}) if type(response) is dict else {}
            request_id = metadata.get('RequestId')
            association = response.get('AssociationId') if type(response) is dict else None
            for value in (request_id, association):
                c.require(value is None or (type(value) is str and re.fullmatch('[A-Za-z0-9-]{1,128}', value)),
                          'bounded nonsensitive service identifier')
            value = dict(schema='E15H_E13_API_RESPONSE_V1', token=token,
                request_sha256=request_sha256, verb=name, request_id=request_id,
                association_id=association, api='RETURNED', remote_finality='UNPROVED')
            key = token+'/api-response'
            try: self.records.create(key, c.canonical(value))
            except Exception: pass
            observed = self.records.read(key)
            c.require(observed is not None and observed['bytes'] == c.canonical(value), 'exact retained API response')
            a.version(observed['version_id'])
            return response
        return call


class Cooperative(NatRuntime):
    """Dormant wrapper at real E13 NatRuntime.mutate, one exact duty per token.

    ADMITTED may be cancelled before dispatch; DISPATCHED persists before the
    SDK boundary. Pausing after that transition remains accounted through close.
    Crashes never expire a permit. E13 owns attempts, ACKs and reconciliation.
    Returning from a synchronous transport plus E13 readback seals this permit's
    future dispatch capability, NOT the AWS service's future effect capability.
    """
    def __init__(self, delegate, coordinator, records):
        from scripts.normal_delivery.delivery import Records
        c.require(isinstance(delegate, NatRuntime) and type(coordinator) is Coordinator and
                  isinstance(records, Records), 'protected NAT runtime ports')
        from scripts.wp4d.aws_runtime import Nat as Transport
        c.require(type(delegate) is Transport, 'actual fixed E13 NAT transport')
        self.capture = DispatchEvidence(delegate.ec2, records, delegate.action)
        delegate.ec2 = self.capture
        self.delegate, self.coordinator, self.records = delegate, coordinator, records

    def now(self): return self.delegate.now()
    def context(self, action, deadline): return self.delegate.context(action, deadline)
    def effect(self, token, deadline): return self.delegate.effect(token, deadline)

    def evidence(self, token, request, effect):
        base = token; refs = {}
        values = {}
        for suffix, key in (('plan',base+'/plan'), ('attempt',base+'/attempt'), ('ack',token+'/ack'), ('api_response',token+'/api-response')):
            observed = self.records.read(key)
            c.require(type(observed) is dict, 'protected E13 journal required')
            a.keys(observed, ('version_id','bytes')); a.version(observed['version_id'])
            value = a.decode(observed['bytes']); c.require(c.canonical(value)==observed['bytes'], 'E13 canonical record')
            refs[suffix] = dict(key=key, version_id=observed['version_id'], sha256=c.digest(observed['bytes']))
            values[suffix] = value
        plan, attempt, ack = values['plan'], values['attempt'], values['ack']
        c.require(plan['token']==token and plan['request']==request and
                  attempt==dict(token=token, plan_sha256=c.digest(c.canonical(plan))), 'E13 exact attempt')
        c.require(ack['token']==token and ack['request']==request and ack['result']==request and
                  ack['request_sha256']==c.digest(c.canonical(request)), 'E13 attributable ACK')
        response = values['api_response']
        c.require(response['token'] == token and response['request_sha256'] == c.digest(c.canonical(request)) and
                  response['api'] == 'RETURNED' and response['remote_finality'] == 'UNPROVED', 'attributable response journal')
        c.require(effect==dict(token=token,request_sha256=c.digest(c.canonical(request)),
                  state='APPLIED',result=request), 'E13 independent effect readback')
        return dict(executor='COOPERATIVE_SEALED', api='RETURNED', effect='APPLIED_OBSERVED', e13=refs)

    def mutate(self, stage, token, request, deadline):
        # E13's immutable attempt precedes this boundary; validate it before admission.
        base = token
        attempt = self.records.read(base+'/attempt'); plan = self.records.read(base+'/plan')
        c.require(attempt is not None and plan is not None, 'E13 pre-dispatch accounting')
        for observed in (attempt, plan):
            a.keys(observed, ('version_id','bytes')); a.version(observed['version_id'])
            c.require(c.canonical(a.decode(observed['bytes'])) == observed['bytes'], 'canonical E13 pre-admission')
        saved = a.decode(plan['bytes'])
        c.require(saved['token'] == token and saved['request'] == request and
                  a.decode(attempt['bytes']) == dict(token=token, plan_sha256=c.digest(plan['bytes'])),
                  'matching E13 plan/attempt before admission')
        executor = self.coordinator.admit(stage, token, request)
        try:
            self.coordinator.transition(token, executor, 'ADMITTED','DISPATCHED')
        except Exception:
            # No SDK call occurred; leave ADMITTED if durable cancellation fails.
            self.coordinator.transition(token, executor, 'ADMITTED','CANCELLED', dict(api='NOT_SENT'))
            raise
        # Exceptions/lost response leave DISPATCHED forever; no forced settlement.
        self.capture.token = token
        self.capture.request_sha256 = c.digest(c.canonical(request))
        self.capture.request = copy.deepcopy(request)
        self.delegate.mutate(stage, token, request, deadline)
        effect = self.delegate.effect(token, deadline)
        evidence = self.evidence(token, request, effect)
        self.coordinator.transition(token, executor, 'DISPATCHED','SEALED', evidence)


class Installed:
    """No synthetic publication or injected port can authorize networking."""
    def protocol(self):
        c.require(False, 'E15H_NARROW_COORDINATOR_AUTHENTICATION_AND_INSTALLATION_REQUIRED')
