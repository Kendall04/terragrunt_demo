"""E15-E bounded DEV ECS drain/readback port; not installed or wired to DOWN.

No clients are constructed here. The concrete protected boundary deliberately
blocks until controller closure and issued-effect settlement can be installed.
QUIET is evidence under an ACTIVE E2 owner, never a WP5 SUCCESS or apply grant.
"""
import copy
import re
from . import contract as c, dev_down as down, handoff
from scripts import environment_mutation as e

BINDING = 'environment-lifecycle/infra-high-risk-dev'
MAX_SAMPLES = 16
FRESH_SECONDS = 30
HOLD_SECONDS = 300
SOURCES = ['E2_AUTHORIZED_WRITERS', 'ECS_REPLICA_ZERO', 'CLEANUP_E2_FENCED',
           'NO_NATIVE_SCALING_OR_START_SCHEDULERS', 'PRIOR_EFFECTS_SETTLED']


class Blocked(ValueError):
    pass


class Pending(ValueError):
    """Complete, valid observation which has not reached quietness yet."""
    pass


DEPLOYMENT_FIELDS = ('id', 'status', 'rolloutState', 'taskDefinition',
                     'desiredCount', 'runningCount', 'pendingCount')


def service_observation(selected, arn, service):
    if service == {'absence': 'EXACT_ECS_MISSING'}:
        return
    c.keys(service, ('desiredCount', 'runningCount', 'pendingCount', 'deployments', 'taskDefinition'),
           'closed service observation')
    family = 'arn:aws:ecs:' + selected['region'] + ':' + selected['account'] + ':task-definition/' + arn.rsplit('/', 1)[1][:-4]
    c.require(type(service['taskDefinition']) is str and re.fullmatch(re.escape(family) + ':[1-9][0-9]*',
              service['taskDefinition']), 'exact DEV color task family')
    for key in ('desiredCount', 'runningCount', 'pendingCount'):
        c.require(type(service[key]) is int and 0 <= service[key] <= 10000, 'bounded service counts')
    deployments = service['deployments']
    c.require(type(deployments) is list and 0 < len(deployments) <= 100, 'complete bounded deployment inventory')
    seen = set()
    for deployment in deployments:
        c.keys(deployment, DEPLOYMENT_FIELDS, 'closed deployment evidence')
        c.require(type(deployment['id']) is str and 0 < len(deployment['id']) <= 256
                  and deployment['id'] not in seen and deployment['status'] in ('PRIMARY', 'ACTIVE', 'INACTIVE')
                  and deployment['rolloutState'] in ('IN_PROGRESS', 'COMPLETED', 'FAILED')
                  and type(deployment['taskDefinition']) is str
                  and re.fullmatch(re.escape(family) + ':[1-9][0-9]*', deployment['taskDefinition']),
                  'exact known deployment identity/controller state')
        seen.add(deployment['id'])
        for key in ('desiredCount', 'runningCount', 'pendingCount'):
            c.require(type(deployment[key]) is int and 0 <= deployment[key] <= 10000, 'bounded deployment counts')


def scope(value, protected):
    selected = down.scope(value, protected)
    c.authorize(BINDING, value, protected, protected['installations'][value['revision']])
    cluster = f'arn:aws:ecs:{selected["region"]}:{selected["account"]}:cluster/demo-dev-platform-main-cluster'
    apps = protected['layers']['apps']
    c.require(apps['root'] == 'terraform/modules/target/dev/apps'
              and apps['variables']['cluster_arn'] == cluster, 'exact DEV ECS cluster')
    services = [cluster.replace(':cluster/', ':service/') + '/demo-dev-app-api-' + color + '-svc'
                for color in ('blue', 'green')]
    members = [apps['membership'].get(address) for address, kind in apps['addresses'].items()
               if kind == 'aws_ecs_service']
    c.require(sorted(members) == sorted(services), 'exact two installed DEV service members')
    return dict(selected, cluster=cluster, services=services,
                ecs_membership_sha256=c.digest(c.canonical(apps)))


def owner_identity(authority, selected):
    c.require(type(authority) is e.Authority, 'existing E2 authority required')
    authority._check()
    c.require(authority.binding == BINDING and authority.operation == selected['operation_id']
              and authority.request_sha256 == selected['request_sha256']
              and authority.store.environment == 'dev' and authority.store.selected == 'application'
              and authority.store.bucket == f'e1-wp4-dev-{selected["account"]}-{selected["region"]}',
              'exact DEV application owner and protected coordination bucket')
    return copy.deepcopy(authority.value)


class ProtectedBoundary:
    """Internal installed port, never supplied by a workflow/event.

    require() must authenticate source/identity, close every writer/controller,
    and settle prior AND current attempted asynchronous effects through this
    exact owner. A JSON flag, new generation or API ACK cannot implement it.
    """
    def require(self, selected, owner, attempts):
        raise Blocked('E15E_BLOCKED: protected ECS closure/settlement authority uninstalled')


class HandoffBoundary(ProtectedBoundary):
    def __init__(self, channel):
        c.require(type(channel) is handoff.Handoff, 'concrete authenticated E15-D channel required')
        self.channel = channel

    def require(self, selected, owner, attempts):
        channel = self.channel
        c.require(scope(channel.value, channel.protected) == selected, 'installed immutable ECS scope')
        channel.session(False)
        # E15-D installation authenticates the executor/storage, not ECS closure,
        # native controllers, old AWS effects or this new source's installation.
        super().require(selected, owner, attempts)


class Journal:
    """Existing WP5 operation namespace and E15-D conditional storage; no lock."""
    def __init__(self, storage, selected):
        c.require(type(storage) is handoff.Storage and storage.account == selected['account'],
                  'protected WP5 storage required')
        self.storage = storage
        self.bucket = f'e1-lifecycle-dev-{selected["account"]}-{selected["region"]}'
        self.prefix = 'operations/' + BINDING + '/' + selected['operation_id'] + '/ecs-quiescence/'

    def key(self, stage):
        c.require(stage in ('intent', 'blue-attempt', 'green-attempt', 'terminal-seal', 'terminal-invalid')
                  or stage in ['sample-' + str(i) for i in range(MAX_SAMPLES)], 'bounded ECS journal stage')
        return self.prefix + stage + '.json'

    def read(self, stage):
        try:
            _, raw = self.storage.anchor(self.bucket, self.key(stage))
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise
        return handoff.document(raw)

    def create(self, stage, record):
        return self.storage.put(self.bucket, self.key(stage), c.canonical(record))


class ECS:
    """SDK-shaped narrow adapter. Retry-free clients belong to protected caller.

    ECS lists PENDING tasks with desiredStatus RUNNING, not desiredStatus PENDING.
    DescribeTasks must cover the live listing plus every previously seen task.
    No StopTask, DeleteService, RunTask, registration, force deployment or IAM API.
    """
    def __init__(self, client, selected):
        self.client, self.selected = client, copy.deepcopy(selected)

    def drain(self, service, authority, boundary, attempts, deadline, clock):
        c.require(service in self.selected['services'], 'installed DEV service only')
        c.require(type(authority) is e.Authority and isinstance(boundary, ProtectedBoundary),
                  'protected dispatch authority and closure port required')
        owner = owner_identity(authority, self.selected)
        def send():
            c.require(owner_identity(authority, self.selected) == owner, 'original dispatch generation')
            proof = boundary.require(self.selected, owner, attempts)
            c.require(proof == dict(scope_sha256=self.selected['scope_sha256'], owner=owner, sources=SOURCES),
                      'protected controller closure at SDK dispatch')
            now = clock()
            c.require(type(deadline) is int and type(now) is int and 0 <= now < deadline,
                      'drain dispatch within protected window')
            c.require(owner_identity(authority, self.selected) == owner, 'owner current after closure readback')
            # The response is deliberately not evidence. No retry on ambiguous ACK.
            self.client.update_service(cluster=self.selected['cluster'], service=service, desiredCount=0)
        return authority.call(send)

    def observe(self, known=()):
        cluster, expected = self.selected['cluster'], self.selected['services']
        response = self.client.describe_clusters(clusters=[cluster])
        c.require(response.get('failures') == [] and len(response.get('clusters', [])) == 1
                  and response['clusters'][0]['clusterArn'] == cluster
                  and response['clusters'][0]['status'] == 'ACTIVE', 'exact active cluster readback')
        response = self.client.describe_services(cluster=cluster, services=expected)
        c.require(type(response.get('services')) is list and type(response.get('failures')) is list,
                  'complete ECS services response')
        services = {}
        for failure in response['failures']:
            arn = failure.get('arn')
            c.require(arn in expected and arn not in services and failure.get('reason') == 'MISSING',
                      'exact service absence only')
            services[arn] = {'absence': 'EXACT_ECS_MISSING'}
        for service in response['services']:
            arn = service['serviceArn']
            c.require(arn in expected and arn not in services and service['clusterArn'] == cluster
                      and service['serviceName'] == arn.rsplit('/', 1)[1], 'exact service readback identity')
            c.require(service['deploymentController'] == {'type': 'ECS'}
                      and service['schedulingStrategy'] == 'REPLICA' and service['launchType'] == 'FARGATE'
                      and service['status'] == 'ACTIVE' and not service.get('taskSets'),
                      'only installed ECS Fargate REPLICA controller supported')
            services[arn] = {key: copy.deepcopy(service[key]) for key in
                ('desiredCount', 'runningCount', 'pendingCount', 'deployments', 'taskDefinition')}
            c.require(type(service['deployments']) is list and 0 < len(service['deployments']) <= 100,
                      'complete bounded deployments')
            # SDK createdAt/updatedAt are datetime objects. Retain only the
            # required metadata, not raw SDK payloads or task/environment data.
            services[arn]['deployments'] = [{key: item[key] for key in DEPLOYMENT_FIELDS}
                                          for item in service['deployments']]
            service_observation(self.selected, arn, services[arn])
        c.require(set(services) == set(expected), 'both DEV colors observed')
        live, token, tokens = [], None, set()
        for _ in range(100):
            page = self.client.list_tasks(cluster=cluster, desiredStatus='RUNNING',
                                         **({'nextToken': token} if token else {}))
            c.require(type(page.get('taskArns')) is list, 'complete task page')
            live.extend(page['taskArns'])
            token = page.get('nextToken')
            if not token:
                break
            c.require(type(token) is str and token not in tokens, 'nonrepeating pagination')
            tokens.add(token)
        c.require(not token and len(live) <= 10000 and len(set(live)) == len(live), 'complete bounded task listing')
        arns = sorted(set(live) | set(known))
        prefix = cluster.replace(':cluster/', ':task/') + '/'
        c.require(len(arns) <= 10000 and all(type(arn) is str and re.fullmatch(
            re.escape(prefix) + '[a-zA-Z0-9-]+', arn) for arn in arns), 'exact DEV task scope')
        tasks = {}
        for offset in range(0, len(arns), 100):
            batch = arns[offset:offset + 100]
            page = self.client.describe_tasks(cluster=cluster, tasks=batch)
            c.require(page.get('failures') == [] and type(page.get('tasks')) is list, 'complete terminal task readback')
            seen = set()
            for task in page['tasks']:
                arn = task['taskArn']
                c.require(arn in batch and arn not in seen and task['clusterArn'] == cluster
                          and task['group'] in ['service:' + s.rsplit('/', 1)[1] for s in expected],
                          'exact service task membership; standalone tasks block')
                seen.add(arn)
                c.require(task['lastStatus'] in ('PROVISIONING', 'PENDING', 'ACTIVATING', 'RUNNING',
                    'DEACTIVATING', 'STOPPING', 'DEPROVISIONING', 'STOPPED')
                    and task['desiredStatus'] in ('RUNNING', 'STOPPED'), 'known task lifecycle')
                tasks[arn] = {key: task[key] for key in ('group', 'lastStatus', 'desiredStatus')}
            c.require(seen == set(batch), 'every required task described; MISSING is not STOPPED')
        return dict(services=services, tasks=tasks, live=sorted(live))


def quiet(observed):
    def ready(ok, reason):
        if not ok:
            raise Pending(reason)
    c.keys(observed, ('services', 'tasks', 'live'), 'closed observation')
    ready(not observed['live'], 'live task listing not empty')
    ready(all(t['lastStatus'] == t['desiredStatus'] == 'STOPPED' for t in observed['tasks'].values()),
              'every previously observed task actually STOPPED')
    for service in observed['services'].values():
        if service == {'absence': 'EXACT_ECS_MISSING'}:
            continue
        ready(all(service[k] == 0 for k in ('desiredCount', 'runningCount', 'pendingCount')), 'service not at zero')
        deployments = service['deployments']
        ready(len(deployments) == 1, 'old deployment remains able to reconcile')
        deployment = deployments[0]
        ready(type(deployment['id']) is str and bool(deployment['id'])
                  and deployment['status'] == 'PRIMARY' and deployment['rolloutState'] == 'COMPLETED'
                  and deployment['taskDefinition'] == service['taskDefinition']
                  and all(type(deployment[k]) is int and deployment[k] == 0
                          for k in ('desiredCount', 'runningCount', 'pendingCount')), 'deployment not settled at zero')


class Quiescence:
    """One-shot drain plus at most sixteen explicit readbacks; never releases E2.

    Domain-port doubles can exercise quietness offline. The only concrete
    authenticated boundary is still BLOCKED. There is no apply/finish method.
    """
    def __init__(self, value, protected, authority, adapter, journal, boundary, clock):
        self.selected = scope(value, protected)
        self.authority, self.adapter, self.journal = authority, adapter, journal
        c.require(type(adapter) is ECS and adapter.selected == self.selected and type(journal) is Journal,
                  'fixed ECS and WP5 journal adapters')
        c.require(journal.bucket == f'e1-lifecycle-dev-{self.selected["account"]}-{self.selected["region"]}'
                  and journal.prefix == 'operations/' + BINDING + '/' + value['operation_id'] + '/ecs-quiescence/',
                  'exact ECS journal domain')
        c.require(isinstance(boundary, ProtectedBoundary), 'protected internal closure port required')
        self.boundary, self.clock = boundary, clock
        self.owner = owner_identity(authority, self.selected)
        self.terminal_failed = False

    def check_owner(self):
        c.require(owner_identity(self.authority, self.selected) == self.owner, 'original E2 generation/owner only')

    def run(self):
        """WP5-shaped fail-closed result. Quietness never finishes its E2 owner."""
        try:
            return self.begin()
        except Blocked:
            return dict(state='UNKNOWN' if self.authority.touched else 'BLOCKED',
                        reason='E15E_PROTECTED_CLOSURE_UNINSTALLED', execution_authorized=False)
        except Exception:
            return dict(state='UNKNOWN', reason='E15E_QUIETNESS_UNPROVED', execution_authorized=False)

    def observation(self, value):
        c.keys(value, ('services', 'tasks', 'live'), 'closed retained observation')
        c.require(type(value['services']) is dict and set(value['services']) == set(self.selected['services'])
                  and type(value['tasks']) is dict and len(value['tasks']) <= 10000
                  and type(value['live']) is list and len(value['live']) <= 10000
                  and set(value['live']) <= set(value['tasks']), 'complete retained ECS membership')
        for arn, service in value['services'].items():
            service_observation(self.selected, arn, service)
        prefix = self.selected['cluster'].replace(':cluster/', ':task/') + '/'
        for arn, task in value['tasks'].items():
            c.require(type(arn) is str and re.fullmatch(re.escape(prefix) + '[a-zA-Z0-9-]+', arn),
                      'retained exact DEV task identity')
            c.keys(task, ('group', 'lastStatus', 'desiredStatus'), 'closed retained task')
            c.require(task['group'] in ['service:' + s.rsplit('/', 1)[1] for s in self.selected['services']]
                      and task['lastStatus'] in ('PROVISIONING', 'PENDING', 'ACTIVATING', 'RUNNING',
                          'DEACTIVATING', 'STOPPING', 'DEPROVISIONING', 'STOPPED')
                      and task['desiredStatus'] in ('RUNNING', 'STOPPED'), 'retained task membership/lifecycle')

    def closure(self):
        self.check_owner()
        attempts = [self.journal.read(color + '-attempt') for color in ('blue', 'green')]
        for attempt, service in zip(attempts, self.selected['services']):
            if attempt is not None:
                c.require(attempt == dict(schema='E15E_ATTEMPT_V1', owner=self.owner,
                    scope_sha256=self.selected['scope_sha256'], cluster=self.selected['cluster'],
                    service=service, desiredCount=0), 'exact retained drain attempt')
        proof = self.boundary.require(self.selected, self.owner, attempts)
        c.keys(proof, ('scope_sha256', 'owner', 'sources'), 'authenticated closure proof')
        c.require(proof == dict(scope_sha256=self.selected['scope_sha256'], owner=self.owner, sources=SOURCES),
                  'every actual source and issued effect must be closed under this owner')
        self.check_owner()
        return proof

    def begin(self):
        self.check_owner()
        retained = self.journal.read('intent')
        if retained is None:
            proof = self.closure()
            observed = self.adapter.observe()
            self.check_owner()
            now = self.clock()
            c.require(type(now) is int and now >= 0, 'trusted clock')
            retained = dict(schema='E15E_INTENT_V1', scope=self.selected, owner=self.owner,
                            started_at=now, expires_at=now + HOLD_SECONDS, baseline=observed, closure=proof)
            self.journal.create('intent', retained)
        self.intent(retained)
        for color, service in zip(('blue', 'green'), self.selected['services']):
            stage = color + '-attempt'
            attempt = dict(schema='E15E_ATTEMPT_V1', owner=self.owner,
                           scope_sha256=self.selected['scope_sha256'], cluster=self.selected['cluster'],
                           service=service, desiredCount=0)
            old = self.journal.read(stage)
            if old is not None:
                c.require(old == attempt, 'unchanged drain attempt; never resend')
                continue
            if retained['baseline']['services'][service] == {'absence': 'EXACT_ECS_MISSING'}:
                continue
            self.closure()
            # Durable attempt before send. A crash here burns this service send.
            self.journal.create(stage, attempt)
            self.intent(retained)
            self.closure()
            attempts = [self.journal.read(name + '-attempt') for name in ('blue', 'green')]
            self.adapter.drain(service, self.authority, self.boundary, attempts,
                               retained['expires_at'], self.clock)
        return self.check()

    def intent(self, retained):
        c.keys(retained, ('schema', 'scope', 'owner', 'started_at', 'expires_at', 'baseline', 'closure'), 'retained ECS intent')
        c.require(retained['schema'] == 'E15E_INTENT_V1' and retained['scope'] == self.selected
                  and retained['owner'] == self.owner, 'current operation intent only')
        self.observation(retained['baseline'])
        c.require(retained['closure'] == dict(scope_sha256=self.selected['scope_sha256'],
                  owner=self.owner, sources=SOURCES), 'retained source closure')
        now = self.clock()
        c.require(type(now) is int and type(retained['started_at']) is int
                  and retained['expires_at'] == retained['started_at'] + HOLD_SECONDS
                  and 0 <= retained['started_at'] <= now < retained['expires_at'], 'bounded quiescence window')
        self.check_owner()

    def check(self):
        """Explicit readback, including after a lost ACK; never sends mutations."""
        intent = self.journal.read('intent')
        self.intent(intent)
        known = set(intent['baseline']['tasks'])
        index = None
        for i in range(MAX_SAMPLES):
            prior = self.journal.read('sample-' + str(i))
            if prior is None:
                index = i
                break
            self.validate_sample(prior)
            known.update(prior['observation']['tasks'])
        c.require(index is not None, 'bounded readbacks exhausted; retain hold for diagnosis')
        started = self.clock()
        proof = self.closure()
        observation = self.adapter.observe(known)
        self.closure();self.intent(intent)
        ended = self.clock()
        c.require(type(started) is int and type(ended) is int and 0 <= ended - started < FRESH_SECONDS,
                  'bounded fresh readback interval')
        sample = dict(schema='E15E_SAMPLE_V1', scope=self.selected, owner=self.owner,
                      started_at=started, observed_at=ended, closure=proof, observation=observation)
        self.journal.create('sample-' + str(index), sample)
        self.closure();self.intent(intent)
        now = self.clock()
        c.require(type(now) is int and ended <= now < started + FRESH_SECONDS,
                  'quietness still fresh after evidence publication')
        quiet(observation)
        return dict(state='QUIET', sample=index, sha256=c.digest(c.canonical(sample)),
                    execution_authorized=False, down_state='UNKNOWN')

    def validate_sample(self, sample):
        c.keys(sample, ('schema', 'scope', 'owner', 'started_at', 'observed_at', 'closure', 'observation'), 'closed ECS evidence')
        c.require(sample['schema'] == 'E15E_SAMPLE_V1' and sample['scope'] == self.selected
                  and sample['owner'] == self.owner and sample['closure'] == dict(
                      scope_sha256=self.selected['scope_sha256'], owner=self.owner, sources=SOURCES), 'correlated ECS evidence')
        self.observation(sample['observation'])
        c.require(type(sample['started_at']) is int and type(sample['observed_at']) is int
                  and 0 <= sample['started_at'] <= sample['observed_at'] < sample['started_at'] + FRESH_SECONDS,
                  'bounded evidence timestamps')

    def require_quiet(self, evidence, stage):
        """Integration pre/post-stage gate only; no Terraform or release authority."""
        c.require(stage in ('edge', 'apps', 'platform', 'data', 'global'), 'DEV dependent stage only')
        c.keys(evidence, ('state', 'sample', 'sha256', 'execution_authorized', 'down_state'), 'quietness receipt')
        c.require(type(evidence['sample']) is int and 0 <= evidence['sample'] < MAX_SAMPLES
                  and evidence['state'] == 'QUIET' and evidence['execution_authorized'] is False
                  and evidence['down_state'] == 'UNKNOWN', 'quietness is not DOWN success/authority')
        sample = self.journal.read('sample-' + str(evidence['sample']))
        self.validate_sample(sample)
        c.require(c.digest(c.canonical(sample)) == evidence['sha256'], 'exact retained evidence digest')
        now = self.clock()
        c.require(type(now) is int and type(sample['observed_at']) is int
                  and sample['observed_at'] <= now < sample['started_at'] + FRESH_SECONDS, 'fresh correlated evidence')
        quiet(sample['observation'])
        # A receipt alone never starts a dependent stage. Repeat all reads and
        # source closure; the caller must retain E2 through stage and completion.
        return self.check()

    def drain_until_quiet(self):
        """One drain attempt, then bounded fresh samples; no sleeps or resend.

        Only a valid nonterminal observation permits another sample. Missing,
        corrupt, ambiguous or failed readbacks stop immediately with the hold.
        A lost mutation response also stops; this method is never recovery.
        """
        try:
            return self.begin()
        except Pending:
            pass
        for _ in range(MAX_SAMPLES - 1):
            try:
                return self.check()
            except Pending:
                continue
        raise Blocked('E15G_ECS_DRAIN_BOUNDED_SAMPLES_EXHAUSTED')

    def seal_before_cluster_delete(self):
        """Seal actual STOPPED cohort immediately before platform deletion.

        The immutable sample is captured while DescribeTasks is still possible.
        This seal is usable only in the same uninterrupted owner and bounded
        intent window, with fresh closure AND exact cluster-absence readback.
        """
        c.require(self.journal.read('terminal-seal') is None, 'terminal seal is single-use')
        receipt = self.check()
        sample = self.journal.read('sample-' + str(receipt['sample']))
        self.validate_sample(sample);quiet(sample['observation'])
        intent = self.journal.read('intent');self.intent(intent)
        sealed = dict(schema='E15G_ECS_TERMINAL_V1', scope=self.selected, owner=self.owner,
            stage='platform', sample=receipt, expires_at=intent['expires_at'])
        self.journal.create('terminal-seal', sealed)
        c.require(self.journal.read('terminal-seal') == sealed, 'durable terminal cohort seal')
        self.closure();self.intent(intent)
        return copy.deepcopy(sealed)

    def require_terminal_handoff(self, stage):
        c.require(not self.terminal_failed, 'terminal handoff failed in original invocation')
        c.require(self.journal.read('terminal-invalid') is None, 'terminal handoff invalidated')
        try:
            return self._terminal_handoff(stage)
        except Exception:
            self.terminal_failed = True
            # Never erase contradictory evidence even if a later read looks
            # quiet again. An interrupted/invalid handoff requires diagnosis.
            record = dict(schema='E15G_ECS_INVALID_V1', owner=self.owner,
                scope_sha256=self.selected['scope_sha256'], state='UNKNOWN')
            try:self.journal.create('terminal-invalid', record)
            except Exception:pass
            raise

    def _terminal_handoff(self, stage):
        c.require(stage in ('platform', 'data', 'global'), 'post-platform handoff only')
        seal = self.journal.read('terminal-seal')
        c.keys(seal, ('schema', 'scope', 'owner', 'stage', 'sample', 'expires_at'), 'terminal handoff seal')
        intent = self.journal.read('intent');self.intent(intent)
        c.require(seal['schema'] == 'E15G_ECS_TERMINAL_V1' and seal['scope'] == self.selected
            and seal['owner'] == self.owner and seal['stage'] == 'platform'
            and seal['expires_at'] == intent['expires_at'], 'original bounded terminal handoff')
        receipt = seal['sample']
        c.keys(receipt, ('state', 'sample', 'sha256', 'execution_authorized', 'down_state'), 'terminal sample receipt')
        c.require(receipt['state'] == 'QUIET' and receipt['execution_authorized'] is False
            and receipt['down_state'] == 'UNKNOWN' and type(receipt['sample']) is int
            and 0 <= receipt['sample'] < MAX_SAMPLES, 'terminal cohort receipt only')
        sample = self.journal.read('sample-' + str(receipt['sample']))
        self.validate_sample(sample)
        c.require(c.digest(c.canonical(sample)) == receipt['sha256'], 'exact sealed terminal sample')
        quiet(sample['observation'])
        # No new task/service read against deleted resources. This read is fresh
        # absence, not inference from a timeout, empty list or stale sample.
        started = self.clock();self.closure()
        response = self.adapter.client.describe_clusters(clusters=[self.selected['cluster']])
        c.require(response.get('clusters') == [] and response.get('failures') == [
            {'arn': self.selected['cluster'], 'reason': 'MISSING'}], 'authoritative exact deleted cluster')
        self.closure();self.intent(intent)
        ended = self.clock()
        c.require(type(started) is int and type(ended) is int and 0 <= ended - started < FRESH_SECONDS,
                  'fresh bounded cluster absence')
        return dict(state='TERMINAL_HANDOFF', stage=stage, seal_sha256=c.digest(c.canonical(seal)),
                    owner=copy.deepcopy(self.owner), observed_at=ended, execution_authorized=False)

    def require_predelete_seal(self):
        c.require(not self.terminal_failed, 'terminal seal failed in original invocation')
        c.require(self.journal.read('terminal-invalid') is None, 'terminal seal invalidated')
        try:
            return self._predelete_seal()
        except Exception:
            self.terminal_failed = True
            if self.journal.read('terminal-seal') is not None:
                record = dict(schema='E15G_ECS_INVALID_V1', owner=self.owner,
                    scope_sha256=self.selected['scope_sha256'], state='UNKNOWN')
                try:self.journal.create('terminal-invalid', record)
                except Exception:pass
            raise

    def _predelete_seal(self):
        c.require(self.journal.read('terminal-invalid') is None, 'terminal seal invalidated')
        seal = self.journal.read('terminal-seal')
        if seal is None:
            return self.seal_before_cluster_delete()
        # Repeated pre-dispatch guards retain the same immutable seal and
        # refresh closure/tasks while the cluster is still available.
        intent = self.journal.read('intent');self.intent(intent)
        c.require(seal == dict(schema='E15G_ECS_TERMINAL_V1', scope=self.selected, owner=self.owner,
            stage='platform', sample=seal['sample'], expires_at=intent['expires_at']), 'unchanged predelete seal')
        receipt = self.check()
        current = self.journal.read('sample-' + str(receipt['sample']))
        prior = self.journal.read('sample-' + str(seal['sample']['sample']))
        self.validate_sample(prior);quiet(prior['observation'])
        c.require(c.digest(c.canonical(prior)) == seal['sample']['sha256']
            and current['observation']['tasks'] == prior['observation']['tasks'], 'sealed terminal cohort unchanged')
        return seal
