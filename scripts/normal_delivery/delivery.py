"""WP4B protected normal delivery. No AWS client, IAM grant or public entrypoint.

One protected runner owns an operation. Append-only writes precede mutations;
observations, never acknowledgements, prove effects. The existing E3 final-read
to-listener race remains: these APIs have no shared compare-and-swap transaction.
"""
from abc import ABC, abstractmethod
import copy
from scripts.normal_delivery import authorization as a
from scripts.normal_delivery.model_consistency import validate as model_consistency
from scripts.normal_delivery.e3 import Gate


class Uncertain(Exception): pass


class JournalError(Exception):
    def __init__(self, key): self.key = key


class Absent(Exception): pass


class EvidenceWrite(JournalError): pass


STAGES = ('register', 'drain', 'attach', 'start', 'switch', 'candidate', 'cleanup')


class Records(ABC):
    """Environment/controller-owned, conditional-create immutable objects.

    read(key): None only for authoritative absence; otherwise observed storage
    {version_id, bytes}. Canonical bytes, no caller records, no overwrite/delete.
    create uses If-None-Match:*; ambiguous writes are reconciled by exact read.
    Storage namespace and writer authentication are WP4D adapter obligations.
    """
    @abstractmethod
    def read(self, key): raise NotImplementedError
    @abstractmethod
    def create(self, key, raw): raise NotImplementedError


class Runtime(ABC):
    """Protected bounded ports, installed separately for dev and prod.

    All methods MUST finish within supplied deadline; no credentials from caller.
    snapshot returns fresh authoritative normalized ECS/ALB state, closed below.
    effect returns {token, request_sha256, state, result}; state is APPLIED,
    ABSENT or UNKNOWN. APPLIED requires independently observed exact operation
    attribution AND resulting identity, not a matching resource alone or an ACK.
    A registration lookup must disambiguate all revisions for the operation; do
    not select latest. Ports may not claim an effect solely from tags/names.
    read_task independently describes the exact revision, never registration ACK.
    cleanup uses fixed installed environment schedule/function/delay; its only
    dynamic payload is the old protected service. No recovery execution here.
    These are future adapter contracts; no SDK implementation or live proof.
    """
    @abstractmethod
    def now(self): raise NotImplementedError
    @abstractmethod
    def snapshot(self, intent, deadline): raise NotImplementedError
    @abstractmethod
    def effect(self, token, deadline): raise NotImplementedError
    @abstractmethod
    def read_task(self, revision, deadline): raise NotImplementedError
    @abstractmethod
    def register(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def drain(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def attach(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def start(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def switch(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def candidate(self, token, request, deadline): raise NotImplementedError
    @abstractmethod
    def cleanup(self, token, request, deadline): raise NotImplementedError


def identity(value):
    a.match(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value)
    return value


class Delivery:
    def __init__(self, authorizer, runtime, records, gate):
        a.require(type(authorizer) is a.Authorizer and isinstance(runtime, Runtime)
                  and isinstance(records, Records) and type(gate) is Gate)
        self.auth, self.runtime, self.records, self.gate = authorizer, runtime, records, gate
        self.env = a.ENDPOINTS[authorizer.endpoint]

    def read(self, key, object_required=False):
        try:
            observed = self.records.read(self.env + '/' + key)
            if observed is None: return None
            a.keys(observed, ('version_id', 'bytes'))
            a.version(observed['version_id'])
            value = a.decode(observed['bytes'])
            a.require(a.canonical(value) == observed['bytes'])
            if object_required: a.require(type(value) is dict)
            return value
        except Exception:
            raise JournalError(key) from None

    def put(self, key, value):
        raw = a.canonical(value)
        try: self.records.create(self.env + '/' + key, raw)
        except Exception: pass  # An acknowledgement, including an error, is not evidence.
        observed = self.read(key)
        if observed is None: raise EvidenceWrite(key)
        a.exact(observed, value, 'persisted')
        return copy.deepcopy(observed)

    def current(self, op):
        # Do not duplicate qualification, eligibility, runtime or membership logic.
        a.exact(self.auth.authorize(a.canonical(op['request'])), op['intent'], 'current intent')

    def bounded(self, op):
        now = self.runtime.now()
        a.require(type(now) is int and op['started'] <= now < op['deadline'])
        return now

    def resources(self, intent):
        observed = self.auth.facts.membership(self.env)
        record = a.envelope(observed, 'environment', self.env)
        a.exact(dict(version_id=observed['version_id'], sha256=a.sha(observed['bytes'])),
                intent['membership'], 'membership observation')
        return record['colors']

    def snapshot(self, op):
        now = self.bounded(op)
        s = self.runtime.snapshot(copy.deepcopy(op['intent']), op['deadline'])
        a.keys(s, ('environment', 'color', 'cluster', 'service', 'listener', 'rule',
                   'normal_target', 'candidate_target', 'task_definition', 'desired',
                   'running', 'pending', 'cohort', 'deployment', 'service_snapshot', 'observed_at'))
        i = op['intent']
        for key, expected in dict(environment=self.env, color=i['color'],
                cluster=i['service']['cluster'], service=i['service']['service'],
                listener=i['routing']['listener_arn'], rule=i['routing']['candidate_rule_arn']).items():
            a.exact(s[key], expected, 'snapshot.' + key)
        a.require(type(s['observed_at']) is int and now <= s['observed_at'] <= self.runtime.now())
        for key in ('desired', 'running', 'pending'):
            a.require(type(s[key]) is int and 0 <= s[key] <= 200)
        a.match(r'arn:aws:ecs:' + self.auth.region + ':' + self.auth.account
                + ':task-definition/' + i['task']['family'] + r':[1-9][0-9]*', s['task_definition'])
        a.match(r'[A-Za-z0-9:/._-]{1,256}', s['deployment'])
        a.require(type(s['cohort']) is list and len(s['cohort']) <= 100
                  and all(type(x) is str for x in s['cohort'])
                  and s['cohort'] == sorted(set(s['cohort'])))
        for task in s['cohort']:
            a.match(r'arn:aws:ecs:' + self.auth.region + ':' + self.auth.account + r':task/[A-Za-z0-9/_-]+', task)
        expected = copy.deepcopy(i['service'])
        expected.update(desiredCount=s['desired'], taskDefinition=s['task_definition'])
        a.exact(s['service_snapshot'], expected, 'service settings')
        return copy.deepcopy(s)

    def routes(self, op, snapshot, switched=False, candidate=False):
        a.exact(snapshot['normal_target'], op['target'] if switched else op['active_target'], 'listener')
        a.exact(snapshot['candidate_target'], op['active_target'] if candidate else op['target'], 'rule')

    def prepared(self, op, snapshot, revision, count):
        a.exact(snapshot['task_definition'], revision, 'selected revision')
        a.exact(snapshot['desired'], count, 'replicas')
        a.require(snapshot['pending'] == 0 and snapshot['running'] == count
                  and len(snapshot['cohort']) == count)

    def preparation_state(self, snapshot):
        # Observation time is evidence, not a state precondition.
        return {k: v for k, v in snapshot.items() if k != 'observed_at'}

    def guard_preparation(self, op, stage, request, expected):
        self.current(op)
        fresh = self.snapshot(op); self.routes(op, fresh)
        a.exact(self.preparation_state(fresh), expected, 'preparation precondition')
        if stage == 'attach':
            a.require(fresh['running'] == fresh['pending'] == fresh['desired'] == 0
                      and not fresh['cohort'])
        elif stage == 'start':
            self.prepared(op, fresh, request['taskDefinition'], 0)
        # Drain may stop an old revision, but only the exact inactive state seen
        # when planning. Attach requires that drained state; start requires the
        # independently registered revision at zero. No storage I/O follows.
        self.bounded(op)

    def guard_post_switch(self, op, stage):
        """Fresh guards after write-ahead I/O, before rule/schedule mutation."""
        self.current(op)
        plan = self.stage_plan(op, 'switch')
        proof = self.activation(op, plan['activation_sha256'])
        revision = proof['registration']['task_definition_arn']
        task = self.runtime.read_task(revision, op['deadline'])
        a.exact(self.auth.validate_registration_readback(op['intent'], task),
                proof['registration'], 'post-switch registration')
        fresh = self.snapshot(op)
        self.routes(op, fresh, switched=True, candidate=stage == 'cleanup')
        self.prepared(op, fresh, revision, op['intent']['service']['desiredCount'])
        for field in ('cohort', 'deployment'):
            a.exact(fresh[field], proof['e3']['context'][field], 'post-switch ' + field)
        self.auth.validate_readback(op['intent'], a.canonical(dict(
            taskDefinition=a.decode(task), service=fresh['service_snapshot'])))
        self.bounded(op)

    def observe_effect(self, op, stage, token, request, possible):
        try:
            observation = self.runtime.effect(token, op['deadline'])
            self.validate_effect(op, stage, observation, token, request)
            return observation
        except Exception:
            if possible: raise Uncertain('mutation effect unprovable') from None
            raise

    def validate_effect(self, op, stage, observation, token, request):
        self.check_effect(observation, token, request)
        if observation['state'] == 'APPLIED':
            if stage == 'register':
                a.keys(observation['result'], ('task_definition_arn',))
                a.match(r'arn:aws:ecs:' + self.auth.region + ':' + self.auth.account
                        + ':task-definition/' + op['intent']['task']['family']
                        + r':[1-9][0-9]*', observation['result']['task_definition_arn'])
            else:
                a.exact(observation['result'], request, 'observed effect')

    def stage_request(self, op, stage):
        i = op['intent']
        service = dict(cluster=i['service']['cluster'], service=i['service']['service'])
        if stage == 'register': return i['task']
        if stage == 'drain': return dict(service, desiredCount=0)
        if stage in ('attach', 'start'):
            registration = self.stored_effect(op, 'register')
            a.require(registration is not None and registration['state'] == 'APPLIED')
            return dict(service, taskDefinition=registration['result']['task_definition_arn'],
                        desiredCount=0 if stage == 'attach' else i['service']['desiredCount'])
        if stage == 'switch': return dict(listener=i['routing']['listener_arn'], target=op['target'])
        if stage == 'candidate': return dict(rule=i['routing']['candidate_rule_arn'], target=op['active_target'])
        a.require(stage == 'cleanup')
        return dict(environment=self.env, cluster=service['cluster'], service=op['active_service'])

    def stage_plan(self, op, stage):
        key = op['operation_id'] + '/' + stage
        plan = self.read(key + '/plan')
        fields = ('token', 'request', 'intent_sha256')
        extra = ('expected_state',) if stage in ('drain', 'attach', 'start') else (('activation_sha256',) if stage == 'switch' else ())
        a.keys(plan, fields + extra)
        a.exact(plan['token'], self.env + '/' + key, 'plan token')
        a.exact(plan['intent_sha256'], op['intent']['intent_sha256'], 'plan intent')
        a.exact(plan['request'], self.stage_request(op, stage), 'plan request')
        attempt = self.read(key + '/attempt')
        a.exact(attempt, dict(token=plan['token'], plan_sha256=a.sha(a.canonical(plan))), 'attempt plan')
        return plan

    def stored_effect(self, op, stage):
        key = op['operation_id'] + '/' + stage
        # A separately retained reconciliation never overwrites damaged evidence.
        for suffix in ('reconciled', 'observed'):
            value = self.read(key + '/' + suffix)
            if value is not None:
                plan = self.stage_plan(op, stage)
                self.validate_effect(op, stage, value, plan['token'], plan['request'])
                return value
        return None

    def reconcile(self, op):
        # Read-only effect recovery has its own bounded budget; this does not
        # extend the immutable deadline for E3 or any subsequent mutation.
        for stage in STAGES:
            key = op['operation_id'] + '/' + stage
            try:
                if self.records.read(self.env + '/' + key + '/attempt') is None: continue
                plan = self.stage_plan(op, stage)
                try: observed = self.stored_effect(op, stage)
                except Exception: observed = None
                if observed is None or observed['state'] == 'UNKNOWN':
                    now = self.runtime.now()
                    a.require(type(now) is int and now > 0)
                    observed = self.runtime.effect(plan['token'], now + 30)
                    self.validate_effect(op, stage, observed, plan['token'], plan['request'])
                    if observed['state'] == 'UNKNOWN': raise Uncertain('unresolved prior effect')
                    self.put(key + '/reconciled', observed)
                if observed['state'] == 'ABSENT': raise Absent()
            except Absent: raise
            except Exception: raise Uncertain('prior effect reconciliation unproved') from None

    def receipt_effects(self, op, effects):
        a.keys(effects, STAGES)
        for stage in STAGES:
            plan = self.stage_plan(op, stage)
            self.validate_effect(op, stage, effects[stage], plan['token'], plan['request'])
            a.require(effects[stage]['state'] == 'APPLIED')
            a.exact(effects[stage], self.stored_effect(op, stage), 'receipt effect')

    def journal_uncertain(self, operation, key):
        # Only durable attempt provenance can make decoding failure ambiguous.
        parts = key.split('/')
        stages = (parts[1],) if len(parts) > 1 and parts[1] in STAGES else STAGES
        try:
            return any(self.records.read(self.env + '/' + operation + '/' + stage + '/attempt')
                       is not None for stage in stages)
        except Exception:
            return True  # Attempt provenance itself is unavailable, not absent.

    def effect(self, op, stage, request, mutate=True, preparation=None, activation_sha256=None):
        """Write-ahead token; never repeat an ambiguous mutation on retry."""
        key = op['operation_id'] + '/' + stage
        token = self.env + '/' + key
        plan = dict(token=token, request=copy.deepcopy(request), intent_sha256=op['intent']['intent_sha256'])
        retained = self.read(key + '/plan')
        if stage in ('drain', 'attach', 'start'):
            plan['expected_state'] = (retained['expected_state'] if retained is not None
                                      else self.preparation_state(preparation))
        if stage == 'switch':
            if activation_sha256 is None:
                a.require(retained is not None)
                activation_sha256 = retained['activation_sha256']
            plan['activation_sha256'] = activation_sha256
            proof = self.activation(op, activation_sha256)
        if retained is not None:
            a.exact(retained, plan, 'immutable stage plan')
            # A plan without an attempt cannot have invoked this V3 runtime.
            # Preserve no-resend, but do not manufacture effect uncertainty.
            a.require(self.read(key + '/attempt') is not None)
        observation = self.stored_effect(op, stage)
        if observation is None:
            observation = self.observe_effect(op, stage, token, request, retained is not None)
        if observation['state'] != 'APPLIED':
            if retained is not None or observation['state'] != 'ABSENT' or not mutate:
                raise Uncertain('mutation may already have happened')
            self.bounded(op)
            self.current(op)
            self.preparing_stage = stage
            self.put(key + '/plan', plan)
            self.put(key + '/attempt', dict(token=token, plan_sha256=a.sha(a.canonical(plan))))
            if stage in ('drain', 'attach', 'start'):
                self.guard_preparation(op, stage, request, plan['expected_state'])
            if stage in ('candidate', 'cleanup'):
                self.guard_post_switch(op, stage)
            if stage == 'switch':
                self.current(op)
                final = self.snapshot(op); self.routes(op, final)
                self.prepared(op, final, proof['registration']['task_definition_arn'],
                              op['intent']['service']['desiredCount'])
                for field in ('cohort', 'deployment'):
                    a.exact(final[field], proof['e3']['context'][field], 'last switch observation')
                self.bounded(op)
            self.preparing_stage = None
            try: getattr(self.runtime, stage)(token, copy.deepcopy(request), op['deadline'])
            except Exception: pass
            observation = self.observe_effect(op, stage, token, request, True)
            if observation['state'] != 'APPLIED': raise Uncertain('mutation not observed')
        else:
            # An unplanned effect cannot be adopted from another operation.
            a.require(retained is not None)
        try:
            if self.read(key + '/reconciled') is None: self.put(key + '/observed', observation)
        except Exception: raise Uncertain('mutation evidence persistence unproved') from None
        return copy.deepcopy(observation['result'])

    def check_effect(self, value, token, request):
        a.keys(value, ('token', 'request_sha256', 'state', 'result'))
        a.exact(value['token'], token, 'effect token')
        a.require(value['state'] in ('ABSENT', 'UNKNOWN', 'APPLIED'))
        if value['state'] == 'APPLIED':
            a.exact(value['request_sha256'], a.sha(a.canonical(request)), 'effect request')
        else: a.require(value['result'] is None and value['request_sha256'] is None)

    def e3_context(self, op, revision, startup):
        i = op['intent']
        return dict(operation_id=op['operation_id'], environment=self.env, region=self.auth.region,
            cluster=i['service']['cluster'], service=i['service']['service'], revision=revision,
            image=i['task']['containerDefinitions'][0]['image'], app=i['task']['containerDefinitions'][0]['name'],
            probe=i['task']['containerDefinitions'][1]['name'], target=op['target'],
            listener=i['routing']['listener_arn'], rule=i['routing']['candidate_rule_arn'],
            active_target=op['active_target'], replicas=i['service']['desiredCount'],
            started=op['started'], deadline=op['deadline'], cohort=startup['cohort'], deployment=startup['deployment'])

    def activation_key(self, op, digest):
        a.match(r'[0-9a-f]{64}', digest)
        return op['operation_id'] + '/activations/' + digest

    def activation(self, op, digest):
        """Resolve the exact immutable proof named by the switch plan, never latest."""
        proof = self.read(self.activation_key(op, digest))
        a.require(proof is not None)
        a.exact(a.sha(a.canonical(proof)), digest, 'activation bytes')
        a.keys(proof, ('operation_id', 'environment', 'startup', 'e3', 'pre_switch',
                       'intent_sha256', 'registration'))
        for field in ('operation_id', 'environment'):
            a.exact(proof[field], op[field], 'activation.' + field)
        a.exact(proof['intent_sha256'], op['intent']['intent_sha256'], 'activation intent')
        registered = self.read(op['operation_id'] + '/registered')
        startup = self.read(op['operation_id'] + '/startup')
        a.require(registered is not None and startup is not None)
        a.exact(proof['registration'], registered, 'activation registration')
        for field in ('cohort', 'deployment', 'task_definition', 'service_snapshot'):
            a.exact(proof['startup'][field], startup[field], 'activation startup')
        context = self.e3_context(op, registered['task_definition_arn'], startup)
        evidence = proof['e3']
        a.exact(evidence['context'], context, 'activation E3 context')
        a.exact(evidence['observation']['context_sha256'], a.sha(a.canonical(context)), 'activation E3 identity')
        a.exact(evidence['observation']['cohort'], context['cohort'], 'activation E3 cohort')
        a.exact(self.read(op['operation_id'] + '/e3/' + a.sha(a.canonical(evidence))),
                evidence, 'persisted E3 evidence')
        final = proof['pre_switch']; self.routes(op, final)
        self.prepared(op, final, registered['task_definition_arn'], context['replicas'])
        for field in ('cohort', 'deployment'):
            a.exact(final[field], context[field], 'activation pre-switch')
        return proof

    def retained_operation(self, operation):
        """Validate protected evidence before comparing any caller retry fields.

        Invalid structure has the same attempt-aware classification as unreadable
        bytes. This does not reauthorize or reconstruct the retained operation.
        """
        key = operation + '/intent'
        retained = self.read(key, object_required=True)
        if retained is None: return None
        try:
            a.keys(retained, ('schema', 'operation_id', 'environment', 'action',
                'request', 'history', 'intent', 'started', 'deadline', 'active_color',
                'active_service', 'active_target', 'target', 'initial'))
            a.require(retained['schema'] == 'E1_DELIVERY_OPERATION_V1')
            a.exact(retained['operation_id'], operation, 'stored operation')
            a.exact(retained['environment'], self.env, 'stored environment')
            a.require(retained['action'] in ('deliver', 'rollback-release'))
            a.request(a.canonical(retained['request']))
            if retained['action'] == 'deliver':
                a.require(retained['history'] is None)
            else:
                a.keys(retained['history'], ('operation_id', 'sha256'))
                identity(retained['history']['operation_id'])
                a.match(r'[0-9a-f]{64}', retained['history']['sha256'])
            a.require(type(retained['started']) is int and retained['started'] > 0
                      and type(retained['deadline']) is int
                      and retained['deadline'] == retained['started'] + 1800)
            a.require(retained['active_color'] in ('blue', 'green'))
            for field in ('active_service', 'active_target', 'target'):
                a.require(type(retained[field]) is str and bool(retained[field]))
            a.require(type(retained['initial']) is dict)
            intent = retained['intent']
            a.keys(intent, ('schema', 'endpoint', 'environment', 'color', 'release',
                'membership', 'qualification_sha256', 'eligibility', 'binding',
                'promotion', 'task', 'service', 'routing', 'intent_sha256'))
            a.require(intent['schema'] == 'E1_AUTHORIZED_RUNTIME_INTENT_V1')
            a.exact(intent['environment'], self.env, 'stored intent environment')
            a.exact(intent['endpoint'], self.auth.endpoint, 'stored intent endpoint')
            for field in ('release', 'membership', 'eligibility', 'binding', 'task', 'service', 'routing'):
                a.require(type(intent[field]) is dict)
            a.exact(intent['intent_sha256'], a.sha(a.canonical(
                {k: v for k, v in intent.items() if k != 'intent_sha256'})), 'stored intent hash')
        except Exception:
            raise JournalError(key) from None
        return retained

    def accept(self, operation, raw):
        identity(operation)
        model_consistency()
        request = a.decode(raw)
        a.keys(request, ('action', 'replicas'), ('release_id', 'history', 'reason'))
        action = request['action']
        a.require(action in ('deliver', 'rollback-release'))
        request = copy.deepcopy(request)
        if action == 'rollback-release':
            a.require('release_id' not in request and 'history' in request)
            historical = self.read(identity(request['history']) + '/success')
            a.require(historical is not None and historical['status'] == 'SUCCESS'
                      and historical['environment'] == self.env)
            release = historical['intent']['release']['release_id']
            history = dict(operation_id=request.pop('history'), sha256=a.sha(a.canonical(historical)))
        else:
            a.require('history' not in request and 'release_id' in request)
            release = request.pop('release_id'); history = None
        request.pop('action')
        request['release_id'] = release
        a.request(a.canonical(request))
        retained = self.retained_operation(operation)
        if retained is not None:
            a.exact(retained['request'], request, 'retry request')
            a.exact(retained['history'], history, 'retry history')
            a.exact(retained['action'], action, 'retry action')
            a.require(retained['operation_id'] == operation and retained['environment'] == self.env)
            return retained
        intent = self.auth.authorize(a.canonical(request))
        started = self.runtime.now()
        a.require(type(started) is int and started > 0)
        op = dict(schema='E1_DELIVERY_OPERATION_V1', operation_id=operation,
                  environment=self.env, action=action, request=request, history=history,
                  intent=intent, started=started, deadline=started + 1800)
        snapshot = self.snapshot(op)
        colors = self.resources(intent)
        active = [color for color, resources in colors.items()
                  if resources['target_group'] == snapshot['normal_target']]
        a.require(len(active) == 1 and active[0] != intent['color'])
        old = colors[active[0]]
        a.require(old['cluster'] == intent['service']['cluster']
                  and old['service'] != intent['service']['service']
                  and old['listener'] == intent['routing']['listener_arn']
                  and old['candidate_rule'] == intent['routing']['candidate_rule_arn'])
        op.update(active_color=active[0], active_service=old['service'], active_target=old['target_group'],
                  target=intent['service']['loadBalancers'][0]['targetGroupArn'], initial=snapshot)
        self.routes(op, snapshot)
        return self.put(operation + '/intent', op)

    def owned(self, operation, raw, authority):
        """Require the existing invocation's exact E2 grant; never take over."""
        from scripts.environment_mutation import Authority, canonical, require
        require(type(authority) is Authority and authority.value is not None)
        require(authority.store.environment == self.env and
                authority.store.selected == 'application' and
                authority.binding == 'normal-delivery/' + self.auth.endpoint and
                authority.operation == operation and
                authority.request_sha256 == a.sha(canonical(a.decode(raw))))
        authority.acquire()  # Existing grant only: rechecks owner/generation/body.

    def recovery_blocked(self, operation, checkpoint):
        result = dict(schema='E1_DELIVERY_OUTCOME_V1', operation_id=operation,
                      environment=self.env, status='UNCERTAIN',
                      code='POST_SWITCH_RECOVERY_BLOCKED', checkpoint=checkpoint)
        try: self.put(operation + '/outcomes/' + a.sha(a.canonical(result)), result)
        except Exception: pass
        return result

    def recover_post_switch(self, operation, raw, authority):
        """One bounded same-invocation continuation, no attempted-stage resend.

        Journals prove historical effects; fresh effect/readback proves current
        post-switch reality. No new deadline, owner, release or compensation.
        """
        checkpoint = 'ownership'
        try:
            self.owned(operation, raw, authority)
            checkpoint = 'retained-operation'
            op = self.retained_operation(operation)
            a.require(op is not None)
            a.exact(self.accept(operation, raw), op, 'recovery operation')
            if self.read(operation + '/success') is not None:
                return self.run(operation, raw)  # Historical receipt only.
            checkpoint = 'switch-attempt-and-activation'
            plan = self.stage_plan(op, 'switch')
            proof = self.activation(op, plan['activation_sha256'])
            checkpoint = 'immutable-effects'
            self.reconcile(op)
            # Do not reobserve superseded drain/attach states. Only post-switch
            # effects have current readback meaning at this boundary.
            for stage in ('switch', 'candidate', 'cleanup'):
                checkpoint = 'current-' + stage + '-effect'
                if self.read(operation + '/' + stage + '/attempt') is None:
                    a.require(self.read(operation + '/' + stage + '/plan') is None)
                    a.require(stage != 'switch')
                    continue
                stage_plan = self.stage_plan(op, stage)
                now = self.runtime.now()
                a.require(type(now) is int and now > 0)
                observed = self.runtime.effect(stage_plan['token'], now + 30)
                self.validate_effect(op, stage, observed, stage_plan['token'], stage_plan['request'])
                self.put(operation + '/post-switch-readbacks/' + a.sha(a.canonical(observed)), observed)
                a.require(observed['state'] == 'APPLIED')
                a.exact(observed, self.stored_effect(op, stage), 'current effect versus journal')
            checkpoint = 'current-authorization-and-topology'
            self.current(op)
            fresh = self.snapshot(op)
            self.put(operation + '/post-switch-snapshots/' + a.sha(a.canonical(fresh)), fresh)
            a.exact(fresh['normal_target'], op['target'], 'recovery listener')
            candidate = self.stored_effect(op, 'candidate')
            self.routes(op, fresh, switched=True, candidate=candidate is not None)
            self.prepared(op, fresh, proof['registration']['task_definition_arn'],
                          op['intent']['service']['desiredCount'])
            for field in ('cohort', 'deployment'):
                a.exact(fresh[field], proof['e3']['context'][field], 'recovery ' + field)
            self.owned(operation, raw, authority)
            checkpoint = 'continuation'
            result = self.run(operation, raw)
            if result['status'] != 'SUCCESS':
                return self.recovery_blocked(operation, checkpoint)
            return result
        except Exception:
            return self.recovery_blocked(operation, checkpoint)

    def run_owned(self, operation, raw, authority):
        """Installed entry: at most one recovery pass while this owner lives."""
        try: self.owned(operation, raw, authority)
        except Exception: return self.recovery_blocked(operation, 'ownership')
        result = self.run(operation, raw)
        if result['status'] == 'UNCERTAIN':
            try:
                attempted = self.records.read(self.env + '/' + operation + '/switch/attempt')
            except Exception:
                return self.recovery_blocked(operation, 'switch-attempt')
            if attempted is not None:
                return self.recover_post_switch(operation, raw, authority)
        return result

    def run(self, operation, raw):
        """Only bounded identity + closed release/count/history inputs; no AWS args."""
        op = None
        self.preparing_stage = None
        try:
            op = self.accept(operation, raw)
            self.reconcile(op)
            prior = self.read(operation + '/success')
            if prior is not None:
                # Return historical completion only, never authorize another switch.
                a.exact(prior['intent'], op['intent'], 'completed intent')
                self.receipt_effects(op, prior['effects'])
                a.exact(prior['activation'], self.activation(op, prior['activation_sha256']), 'receipt proof')
                a.exact(prior['activation_sha256'], self.read(operation + '/switch/plan')['activation_sha256'], 'receipt selection')
                return prior
            self.current(op)
            self.bounded(op)
            return self.deliver(op)
        except Exception as error:
            status = 'UNCERTAIN' if isinstance(error, Uncertain) else 'FAILURE'
            if isinstance(error, JournalError) and self.preparing_stage is None and self.journal_uncertain(operation, error.key):
                status = 'UNCERTAIN'
            if isinstance(error, EvidenceWrite) and self.journal_uncertain(operation, operation):
                status = 'UNCERTAIN'
            if op is not None:
                # Any attempted switch may have happened; a later failure cannot
                # promise that old traffic was preserved.
                try:
                    if (not isinstance(error, Absent) and self.preparing_stage != 'switch'
                            and self.records.read(self.env + '/' + operation + '/switch/attempt') is not None):
                        status = 'UNCERTAIN'
                except Exception: status = 'UNCERTAIN'
            result = dict(schema='E1_DELIVERY_OUTCOME_V1', operation_id=operation,
                          environment=self.env, status=status, code='DELIVERY_NOT_CONFIRMED')
            if op is not None:
                result['intent_sha256'] = op['intent']['intent_sha256']
                try: self.put(operation + '/outcomes/' + a.sha(a.canonical(result)), result)
                except Exception: pass  # Outcome storage cannot invent a runtime effect.
            return result

    def deliver(self, op):
        i, operation = op['intent'], op['operation_id']
        registration = self.effect(op, 'register', i['task'])
        a.keys(registration, ('task_definition_arn',))
        revision = registration['task_definition_arn']
        task = self.runtime.read_task(revision, op['deadline'])
        checked = self.auth.validate_registration_readback(i, task)
        a.exact(checked['task_definition_arn'], revision, 'registration identity')
        self.put(operation + '/registered', checked)
        service = dict(cluster=i['service']['cluster'], service=i['service']['service'])
        switch_request = dict(listener=i['routing']['listener_arn'], target=op['target'])
        switch_planned = self.read(operation + '/switch/plan') is not None
        if not switch_planned:
            # Completed preparation steps are reused, never reapplied to a running cohort.
            for stage, request, count, selected in (
                    ('drain', dict(service, desiredCount=0), 0, None),
                    ('attach', dict(service, desiredCount=0, taskDefinition=revision), 0, revision),
                    ('start', dict(service, desiredCount=i['service']['desiredCount'], taskDefinition=revision),
                     i['service']['desiredCount'], revision)):
                retained_effect = self.stored_effect(op, stage)
                if retained_effect is not None:
                    a.require(retained_effect['state'] == 'APPLIED')
                    continue
                planned = self.read(operation + '/' + stage + '/plan') is not None
                s = None
                if not planned:
                    s = self.snapshot(op); self.routes(op, s)
                    if stage == 'attach':
                        a.require(s['running'] == s['pending'] == s['desired'] == 0 and not s['cohort'])
                    if stage == 'start': self.prepared(op, s, revision, 0)
                result = self.effect(op, stage, request, preparation=s)
                a.exact(result, request, 'mutation result')
                s = self.snapshot(op); self.routes(op, s)
                if selected: self.prepared(op, s, selected, count)
                else: a.require(s['running'] == s['pending'] == s['desired'] == 0 and not s['cohort'])
            startup = self.snapshot(op); self.routes(op, startup)
            self.prepared(op, startup, revision, i['service']['desiredCount'])
            retained_startup = self.read(operation + '/startup')
            if retained_startup is None:
                self.put(operation + '/startup', startup)
            else:
                for field in ('cohort', 'deployment', 'task_definition', 'service_snapshot'):
                    a.exact(startup[field], retained_startup[field], 'retained startup.' + field)
            self.auth.validate_readback(i, a.canonical(dict(taskDefinition=a.decode(task), service=startup['service_snapshot'])))
            context = self.e3_context(op, revision, startup)
            # Rerun E3 on every pre-switch retry; stored readiness is not authority.
            evidence = self.gate.run(context, self.bounded(op))
            self.put(operation + '/e3/' + a.sha(a.canonical(evidence)), evidence)
            self.current(op)
            final = self.snapshot(op); self.routes(op, final)
            self.prepared(op, final, revision, i['service']['desiredCount'])
            a.exact(final['cohort'], context['cohort'], 'final cohort')
            a.exact(final['deployment'], context['deployment'], 'final deployment')
            self.auth.validate_readback(i, a.canonical(dict(taskDefinition=a.decode(task), service=final['service_snapshot'])))
            self.bounded(op)
            proof = dict(operation_id=operation, environment=self.env,
                         startup=startup, e3=evidence, pre_switch=final,
                         intent_sha256=i['intent_sha256'], registration=checked)
            proof_sha256 = a.sha(a.canonical(proof))
            self.put(self.activation_key(op, proof_sha256), proof)
            self.effect(op, 'switch', switch_request, activation_sha256=proof_sha256)
        else:
            # Never repeat a listener write whose ACK is ambiguous. A retry can
            # finish only if exact operation-linked switch effect is established.
            self.effect(op, 'switch', switch_request, mutate=False)
        switch_plan = self.read(operation + '/switch/plan')
        proof = self.activation(op, switch_plan['activation_sha256'])
        s = self.snapshot(op)
        a.exact(s['normal_target'], op['target'], 'switched listener')
        self.prepared(op, s, revision, i['service']['desiredCount'])
        a.exact(s['cohort'], proof['e3']['context']['cohort'], 'activated cohort')
        a.exact(s['deployment'], proof['e3']['context']['deployment'], 'activated deployment')
        candidate_request = dict(rule=i['routing']['candidate_rule_arn'], target=op['active_target'])
        a.require(s['candidate_target'] in (op['target'], op['active_target']))
        self.effect(op, 'candidate', candidate_request)
        after_rule = self.snapshot(op); self.routes(op, after_rule, switched=True, candidate=True)
        self.prepared(op, after_rule, revision, i['service']['desiredCount'])
        self.effect(op, 'cleanup', dict(environment=self.env, cluster=service['cluster'], service=op['active_service']))
        final = self.snapshot(op); self.routes(op, final, switched=True, candidate=True)
        self.prepared(op, final, revision, i['service']['desiredCount'])
        a.exact(final['cohort'], proof['e3']['context']['cohort'], 'receipt cohort')
        a.exact(final['deployment'], proof['e3']['context']['deployment'], 'receipt deployment')
        self.current(op)
        receipt = dict(schema='E1_DELIVERY_RECEIPT_V1', status='SUCCESS', environment=self.env,
                       operation_id=operation, action=op['action'], history=op['history'], intent=i,
                       registration=checked, activation=proof, activation_sha256=switch_plan['activation_sha256'], final=final,
                       effects={stage: self.stored_effect(op, stage) for stage in STAGES})
        self.receipt_effects(op, receipt['effects'])
        return self.put(operation + '/success', receipt)


def dev_prerequisite(receipt):
    """Protected receipt adapter projection, not a caller proof or prod grant.

    Caller must have authenticated the immutable dev success record. The matching
    prod approval remains an independent WP4A port; it is never synthesized here.
    """
    a.require(receipt['schema'] == 'E1_DELIVERY_RECEIPT_V1' and receipt['status'] == 'SUCCESS'
              and receipt['environment'] == 'dev')
    i = receipt['intent']; q = i['release']
    return dict(schema='E1_DEV_ACTIVATION_RECEIPT_V1', writer='NORMAL_DELIVERY_DEV',
        outcome='ACTIVATED', release_id=q['release_id'], source_commit=q['source_commit'],
        image_uri=i['task']['containerDefinitions'][0]['image'], runtime_contract=q['runtime_contract'],
        manifest_version_id=q['manifest']['version_id'], manifest_sha256=q['manifest']['sha256'],
        qualification_sha256=i['qualification_sha256'], account=q['account'], region=q['region'])
