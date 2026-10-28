"""WP4A authorization only. No SDK, writes, execution or deployment authority.

Ports are protected dependencies installed by the controller, not caller objects.
JSON writer/schema strings establish consistency, never authentication. A future
adapter MUST enforce the namespace/current-read contracts documented on Facts.
An intent is preparation evidence; it is NOT E3 approval or permission to switch.
"""
from abc import ABC, abstractmethod
import copy
import hashlib
import json
from pathlib import Path
import re

from scripts.qualification import finalizer as wp3

ROOT = Path(__file__).resolve().parents[2]
MODEL = json.loads((ROOT / 'ci/authority/normal-delivery-model.json').read_text())
TEMPLATE = json.loads((ROOT / 'demo-api/deploy/task-definition.template.json').read_text())
ENDPOINTS = {'deploy-dev': 'dev', 'promote-prod': 'prod'}


class Rejected(ValueError):
    """Sanitized fail-closed domain error."""


def require(condition):
    if not condition:
        raise Rejected('E1_NORMAL_DELIVERY_REJECTED')


def canonical(value):
    return wp3.canonical(value)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 1048576)
    return wp3.decode(raw)


def keys(value, required, optional=()):
    require(type(value) is dict and set(required) <= set(value)
            and set(value) <= set(required) | set(optional))


def match(pattern, value):
    require(type(value) is str and re.fullmatch(pattern, value) is not None)


def version(value):
    match(r'(?![Nn][Uu][Ll][Ll]$|[Ll][Aa][Tt][Ee][Ss][Tt]$)[A-Za-z0-9._+/=-]{1,1024}', value)


def exact(actual, expected, path):
    """Complete recursive closure, including types, collection cardinality/keys.

    Lists with set-like AWS semantics are normalized BEFORE this comparison.
    No unknown subtree is passed through or silently discarded.
    """
    require(type(actual) is type(expected))
    if type(expected) is dict:
        require(set(actual) == set(expected))
        for key in expected:
            exact(actual[key], expected[key], path + '.' + key)
    elif type(expected) is list:
        require(len(actual) == len(expected))
        for left, right in zip(actual, expected):
            exact(left, right, path + '[]')
    else:
        require(actual == expected)


class Facts(ABC):
    """Read-only protected ports. No AWS requests or caller evidence accepted.

    qualification: exact FINALIZER-only key, canonical persisted bytes.
    manifest: exact protected bucket/key/VersionId read, returned identity+bytes.
    eligibility_current: CURRENT admin-only key (NO historical version input),
      envelope {release_id, version_id, bytes}; VersionId from storage response.
    environment: admin-installed endpoint-only namespace, envelope
      {endpoint, version_id, bytes}; authenticated config/bootstrap evidence.
      color is controller-selected through protected operation state, not caller.
    membership: CURRENT admin-only environment resource universe, independently
      published from environment configuration; envelope {environment, version_id,
      bytes}. Exact color/position identities, never inferred from binding claims,
      tags or names. Adapter must authenticate membership ownership and environment.
    artifact: authoritative exact repository/digest lookup, no tag fallback.
    promotion: dev-controller activation receipt + independently authenticated
      prod approval context. Both exact protected reads, never request booleans.

    Subclassing is not authentication. Future WP4B/D adapters must provide writer
    protection/currentness; fixtures implement this contract only offline.
    """
    @abstractmethod
    def qualification(self, release_id): raise NotImplementedError
    @abstractmethod
    def manifest(self, bucket, key, version_id): raise NotImplementedError
    @abstractmethod
    def eligibility_current(self, release_id): raise NotImplementedError
    @abstractmethod
    def environment(self, endpoint): raise NotImplementedError
    @abstractmethod
    def membership(self, environment): raise NotImplementedError
    @abstractmethod
    def artifact(self, repository, digest): raise NotImplementedError
    @abstractmethod
    def promotion(self, release_id): raise NotImplementedError


def request(raw):
    value = decode(raw)
    keys(value, ('release_id', 'replicas'), ('reason',))
    match(r'sha256-[0-9a-f]{64}', value['release_id'])
    require(type(value['replicas']) is int and 1 <= value['replicas'] <= 100)
    if 'reason' in value:
        match(r'[A-Za-z0-9 .,_:/()-]{1,256}', value['reason'])
    return value


def envelope(value, identity_key, identity):
    keys(value, (identity_key, 'version_id', 'bytes'))
    require(value[identity_key] == identity)
    version(value['version_id'])
    record = decode(value['bytes'])
    require(value['bytes'] == canonical(record))
    return record



def connection_secret_arn(value, env, account, region):
    """Shared base-ARN layout; selectors belong to a separately reviewed profile."""
    require(env in ('dev','prod'))
    match(r'arn:aws:secretsmanager:' + re.escape(region) + ':' + re.escape(account)
          + ':secret:demo/' + env + r'/app/db-connection-string-[A-Za-z0-9]{6}', value)
    return value


def binding(value, endpoint, account, region):
    keys(value, ('schema', 'environment', 'color', 'account', 'region',
                 'runtime_contract', 'max_replicas', 'roles', 'secret_arn',
                 'kms_key_arn', 'log_group', 'service', 'listener_arn',
                 'candidate_rule_arn', 'bootstrap'))
    env = ENDPOINTS[endpoint]
    require(value['schema'] == 'E1_DELIVERY_BINDING_V1'
            and value['environment'] == env and value['account'] == account
            and value['region'] == region and value['runtime_contract'] == wp3.RUNTIME)
    require(value['color'] in ('blue', 'green'))
    require(type(value['max_replicas']) is int and 1 <= value['max_replicas'] <= 100)
    family = 'demo-' + env + '-app-api-' + value['color']
    keys(value['roles'], ('task', 'execution'))
    prefix = 'arn:aws:iam::' + account + ':role/' + family
    require(value['roles']['task'] == prefix + '-task-role')
    require(value['roles']['execution'] == prefix + '-exec-role')
    connection_secret_arn(value['secret_arn'], env, account, region)
    match(r'arn:aws:kms:' + region + ':' + account + r':key/[a-f0-9-]{36}', value['kms_key_arn'])
    require(value['log_group'] == '/aws/ecs/' + family)
    for field, kind in (('listener_arn', 'listener'), ('candidate_rule_arn', 'listener-rule')):
        match(r'arn:aws:elasticloadbalancing:' + region + ':' + account
              + ':' + kind + '/app/demo-' + env + r'-[A-Za-z0-9/-]+', value[field])
    service = value['service']
    keys(service, MODEL['service_required'])
    require(service['service'] == family + '-svc')
    match(r'arn:aws:ecs:' + region + ':' + account + ':cluster/demo-' + env + r'-[A-Za-z0-9-]+', service['cluster'])
    constants = dict(enableExecuteCommand=False, launchType='FARGATE',
                     schedulingStrategy='REPLICA', propagateTags='SERVICE',
                     deploymentController={'type': 'ECS'},
                     deploymentConfiguration={'minimumHealthyPercent': 100, 'maximumPercent': 200},
                     capacityProviderStrategy=[], healthCheckGracePeriodSeconds=0,
                     enableECSManagedTags=False)
    for key, expected in constants.items(): exact(service[key], expected, 'binding.service.' + key)
    match(r'[1-9][0-9]*\.[0-9]+\.[0-9]+', service['platformVersion'])
    network = service['networkConfiguration']
    keys(network, ('awsvpcConfiguration',))
    vpc = network['awsvpcConfiguration']
    keys(vpc, ('subnets', 'securityGroups', 'assignPublicIp'))
    require(vpc['assignPublicIp'] == 'DISABLED')
    for field, prefix in (('subnets', 'subnet'), ('securityGroups', 'sg')):
        items = vpc[field]
        require(type(items) is list and 1 <= len(items) <= 16 and len(set(items)) == len(items))
        for item in items: match(prefix + r'-[0-9a-f]{8,17}', item)
    lbs = service['loadBalancers']
    require(type(lbs) is list and len(lbs) == 1)
    keys(lbs[0], ('targetGroupArn', 'containerName', 'containerPort'))
    require(lbs[0]['containerName'] == family and type(lbs[0]['containerPort']) is int
            and lbs[0]['containerPort'] == 8080)
    match(r'arn:aws:elasticloadbalancing:' + region + ':' + account
          + ':targetgroup/demo-' + env + '-' + value['color'] + r'/[0-9a-f]{16}', lbs[0]['targetGroupArn'])
    # Installed bootstrap evidence represents the initial inert skeleton, not an
    # assertion that a later already-deployed service has no workload roles.
    bootstrap = value['bootstrap']
    keys(bootstrap, ('desiredCount', 'taskDefinition'))
    require(type(bootstrap['desiredCount']) is int and bootstrap['desiredCount'] == 0)
    inert = bootstrap['taskDefinition']
    keys(inert, ('family', 'networkMode', 'requiresCompatibilities', 'cpu', 'memory', 'containerDefinitions'))
    require(inert['family'] == family and inert['networkMode'] == 'awsvpc'
            and inert['requiresCompatibilities'] == ['FARGATE']
            and inert['cpu'] == '256' and inert['memory'] == '512')
    require(type(inert['containerDefinitions']) is list and len(inert['containerDefinitions']) == 1)
    container = inert['containerDefinitions'][0]
    keys(container, ('name', 'image', 'essential'))
    require(container['name'] == family and container['essential'] is True)
    match(r'[A-Za-z0-9./:@_-]{1,1024}', container['image'])
    return copy.deepcopy(value)


def qualified(facts, release_id, account, region):
    raw = facts.qualification(release_id)
    q = wp3.validate('qualification', decode(raw))
    require(raw == canonical(q) and q['release_id'] == release_id)
    content = {k: v for k, v in q.items() if k != 'release_id'}
    require(release_id == 'sha256-' + sha(canonical(content)))
    require(q['account'] == account and q['region'] == region)
    require(all(q['checks'][key] == 'PASS' for key in wp3.REQUIRED_CHECKS))
    ref = q['manifest']
    require(ref['bucket'] == 'demo-release-artifacts-' + account)
    require(ref['key'] == 'releases/demo-api/by-digest/sha256-' + q['image_digest'][7:] + '.json')
    observed = facts.manifest(ref['bucket'], ref['key'], ref['version_id'])
    keys(observed, ('bucket', 'key', 'version_id', 'bytes'))
    for key in ('bucket', 'key', 'version_id'): require(observed[key] == ref[key])
    require(type(observed['bytes']) is bytes and sha(observed['bytes']) == ref['sha256'])
    manifest = decode(observed['bytes'])
    schema = json.loads((ROOT / 'ci/schemas/release-manifest.schema.json').read_text())
    wp3._validate(manifest, schema, {})
    uri = account + '.dkr.ecr.' + region + '.amazonaws.com/' + q['image_repository'] + '@' + q['image_digest']
    require(manifest['app'] == 'demo-api' and manifest['repository'] == q['repository']
            and manifest['gitSha'] == q['source_commit'] and manifest['sourceBranch'] == 'develop')
    exact(manifest['image']['registry'], account + '.dkr.ecr.' + region + '.amazonaws.com', 'manifest.registry')
    require(manifest['image']['repository'] == q['image_repository']
            and manifest['image']['digest'] == q['image_digest'] and manifest['image']['uri'] == uri)
    require(manifest['quality']['dotnetTests'] == manifest['quality']['dockerBuild'] == 'passed')
    return q, uri


def promotion(facts, q, uri):
    observed = facts.promotion(q['release_id'])
    keys(observed, ('dev_receipt', 'prod_approval'))
    for field, schema, writer in (
            ('dev_receipt', 'E1_DEV_ACTIVATION_RECEIPT_V1', 'NORMAL_DELIVERY_DEV'),
            ('prod_approval', 'E1_PROD_APPROVAL_CONTEXT_V1', 'PROTECTED_PROD_APPROVAL')):
        env = observed[field]
        record = envelope(env, 'release_id', q['release_id'])
        required = ('schema', 'writer', 'release_id', 'source_commit', 'image_uri',
                    'runtime_contract', 'manifest_version_id', 'manifest_sha256',
                    'qualification_sha256', 'account', 'region')
        keys(record, required, ('outcome',) if field == 'dev_receipt' else ('consumer',))
        require(record['schema'] == schema and record['writer'] == writer
                and record['release_id'] == q['release_id'] and record['source_commit'] == q['source_commit']
                and record['image_uri'] == uri and record['runtime_contract'] == q['runtime_contract']
                and record['manifest_version_id'] == q['manifest']['version_id']
                and record['manifest_sha256'] == q['manifest']['sha256']
                and record['qualification_sha256'] == sha(canonical(q))
                and record['account'] == q['account'] and record['region'] == q['region'])
        if field == 'dev_receipt': require(record.get('outcome') == 'ACTIVATED')
        else: require(record.get('consumer') == 'promote-prod')
    return {field: {'version_id': observed[field]['version_id'], 'sha256': sha(observed[field]['bytes'])}
            for field in observed}



def resource_positions(config):
    """All WP4A resource identities, retaining semantic positions."""
    service = config['service']
    return dict(roles=copy.deepcopy(config['roles']), secret_arn=config['secret_arn'],
                kms_key_arn=config['kms_key_arn'], log_group=config['log_group'],
                cluster=service['cluster'], service=service['service'],
                subnets=sorted(service['networkConfiguration']['awsvpcConfiguration']['subnets']),
                security_groups=sorted(service['networkConfiguration']['awsvpcConfiguration']['securityGroups']),
                target_group=service['loadBalancers'][0]['targetGroupArn'],
                listener=config['listener_arn'], candidate_rule=config['candidate_rule_arn'])


def validate_membership(observed, config):
    env = config['environment']
    record = envelope(observed, 'environment', env)
    keys(record, ('schema', 'writer', 'environment', 'account', 'region', 'colors'))
    require(record['schema'] == 'E1_ENVIRONMENT_RESOURCES_V1'
            and record['writer'] == 'SECURITY_ADMIN'
            and record['environment'] == env and record['account'] == config['account']
            and record['region'] == config['region'])
    keys(record['colors'], ('blue', 'green'))
    # Validate every color, not only the selected member; reject ambiguous sets.
    for color, resources in record['colors'].items():
        expected_keys = resource_positions(config)
        keys(resources, expected_keys)
        keys(resources['roles'], ('task', 'execution'))
        for field in ('subnets', 'security_groups'):
            items = resources[field]
            require(type(items) is list and 1 <= len(items) <= 16
                    and all(type(item) is str for item in items)
                    and len(set(items)) == len(items))
        for field in set(resources) - {'roles', 'subnets', 'security_groups'}:
            require(type(resources[field]) is str and bool(resources[field]))
        require(all(type(v) is str and bool(v) for v in resources['roles'].values()))
        require(resources['roles']['task'] != resources['roles']['execution'])
    selected = copy.deepcopy(record['colors'][config['color']])
    for field in ('subnets', 'security_groups'): selected[field].sort()
    exact(resource_positions(config), selected, 'membership')
    return dict(version_id=observed['version_id'], sha256=sha(observed['bytes']))


def validate_task_model(task, config=None, image_uri=None):
    """One recursive model for placeholder template and fully bound output."""
    values = {}
    if config is not None:
        family = 'demo-' + config['environment'] + '-app-api-' + config['color']
        values = dict(family=family, probe=family + '-readiness-probe',
                      task_role=config['roles']['task'], execution_role=config['roles']['execution'],
                      image=image_uri, AWS_REGION=config['region'], APP_ENV=config['environment'],
                      DEPLOYMENT=config['color'], KMS_KEY_ID=config['kms_key_arn'],
                      secret=config['secret_arn'], logs=config['log_group'])
    def resolve(node):
        if type(node) is dict:
            if set(node) == {'$binding'}:
                return values[node['$binding']] if config is not None else ''
            return {key: resolve(value) for key, value in node.items()}
        if type(node) is list: return [resolve(value) for value in node]
        return node
    exact(task, resolve(MODEL['canonical_task']), 'canonical_task')


def runtime(config, image_uri, replicas):
    env, color = config['environment'], config['color']
    family = 'demo-' + env + '-app-api-' + color
    validate_task_model(TEMPLATE)
    task = copy.deepcopy(TEMPLATE)
    task.update(family=family, taskRoleArn=config['roles']['task'], executionRoleArn=config['roles']['execution'])
    app, probe = task['containerDefinitions']
    app.update(name=family, image=image_uri)
    probe.update(name=family + '-readiness-probe', image=image_uri)
    values = dict(AWS_REGION=config['region'], APP_ENV=env, DEPLOYMENT=color, KMS_KEY_ID=config['kms_key_arn'])
    app['environment'] = [{'name': key, 'value': value} for key, value in values.items()]
    app['secrets'] = [{'name': 'DB_CONN_STRING', 'valueFrom': config['secret_arn']}]
    for container in (app, probe):
        container['logConfiguration']['options'] = {
            'awslogs-group': config['log_group'], 'awslogs-region': config['region'],
            'awslogs-stream-prefix': container['name']}
    service = copy.deepcopy(config['service'])
    for field in ('subnets', 'securityGroups'):
        service['networkConfiguration']['awsvpcConfiguration'][field].sort()
    service['desiredCount'] = replicas
    return task, service


class Authorizer:
    intent_schema = 'E1_AUTHORIZED_RUNTIME_INTENT_V1'

    def read_binding(self, observed):
        return binding(envelope(observed,'endpoint',self.endpoint),self.endpoint,self.account,self.region)

    def build_runtime(self, config, uri, replicas):
        return runtime(config,uri,replicas)

    def check_task_model(self, task, config, uri):
        validate_task_model(task,config,uri)

    def intent_extension(self, config, q, uri):
        return {}

    def __init__(self, endpoint, account, region, facts):
        require(endpoint in ENDPOINTS and isinstance(facts, Facts))
        match(r'[0-9]{12}', account)
        match(r'[a-z]{2}(?:-[a-z]+)+-[0-9]', region)
        self.endpoint, self.account, self.region, self.facts = endpoint, account, region, facts

    def authorize(self, raw):
        try:
            caller = request(raw)
            observed = self.facts.environment(self.endpoint)
            config = self.read_binding(observed)
            require(caller['replicas'] <= config['max_replicas'])
            membership = validate_membership(self.facts.membership(config['environment']), config)
            q, uri = qualified(self.facts, caller['release_id'], self.account, self.region)
            eligible = self.facts.eligibility_current(q['release_id'])
            record = wp3.validate_eligibility(envelope(eligible, 'release_id', q['release_id']), q['release_id'])
            require(record['version_id'] == eligible['version_id'] and record['state'] == 'ELIGIBLE')
            available = self.facts.artifact(q['image_repository'], q['image_digest'])
            expected = dict(account=self.account, region=self.region,
                            repository=q['image_repository'], digest=q['image_digest'], available=True)
            exact(available, expected, 'artifact')
            prerequisite = promotion(self.facts, q, uri) if self.endpoint == 'promote-prod' else None
            extension = self.intent_extension(config,q,uri)
            task, service = self.build_runtime(config, uri, caller['replicas'])
            self.check_task_model(task, config, uri)
            intent = dict(schema=self.intent_schema, endpoint=self.endpoint,
                          environment=config['environment'], color=config['color'], release=q,
                          membership=membership,
                          qualification_sha256=sha(canonical(q)), eligibility=dict(version_id=eligible['version_id'],
                          sha256=sha(eligible['bytes'])), binding=dict(version_id=observed['version_id'],
                          sha256=sha(observed['bytes'])), promotion=prerequisite, task=task, service=service,
                          routing=dict(listener_arn=config['listener_arn'], candidate_rule_arn=config['candidate_rule_arn']))
            require(type(extension) is dict and not set(extension) & set(intent))
            intent.update(extension)
            intent['intent_sha256'] = sha(canonical(intent))
            return copy.deepcopy(intent)
        except Exception:
            raise Rejected('E1_NORMAL_DELIVERY_REJECTED') from None

    def validate_readback(self, intent, raw):
        """Compare exact task+service readback; no mutation or E3 approval.

        Reauthorize through fresh ports and compare the supplied retained intent
        so an arbitrary caller-authored expected object cannot authorize a runtime.
        Service response represents the future selected revision/count snapshot;
        WP4B must perform earlier task-only validation before candidate startup.
        """
        try:
            # Recheck current protected facts. WP4B must retain the original
            # authenticated operation binding; an intent is not a caller token.
            expected = self.authorize(canonical({'release_id': intent['release']['release_id'],
                                                 'replicas': intent['service']['desiredCount']}))
            exact(intent, expected, 'intent')
            response = decode(raw)
            keys(response, ('taskDefinition', 'service'))
            task = copy.deepcopy(response['taskDefinition'])
            keys(task, expected['task'].keys(), MODEL['task_return_only'] + list(MODEL['task_defaults']))
            family = expected['task']['family']
            arn = task.get('taskDefinitionArn')
            match(r'arn:aws:ecs:' + self.region + ':' + self.account + ':task-definition/' + family + r':[1-9][0-9]*', arn)
            require(type(task.get('revision')) is int and task['revision'] == int(arn.rsplit(':', 1)[1]))
            require(task.get('status') == 'ACTIVE')
            for field in MODEL['task_return_only']:
                if field in task:
                    validate_metadata(field, task.pop(field), self.account, self.region)
            defaults(task, MODEL['task_defaults'], 'task')
            containers = task['containerDefinitions']
            require(type(containers) is list and len(containers) == 2)
            for container in containers:
                expected_container = next((item for item in expected['task']['containerDefinitions']
                                           if item['name'] == container.get('name')), None)
                require(expected_container is not None)
                defaults(container, {k: v for k, v in MODEL['container_defaults'].items()
                                     if k not in expected_container}, 'container')
                if 'portMappings' in container:
                    for port in container['portMappings']:
                        if 'hostPort' in port:
                            require(type(port['hostPort']) is int and port.pop('hostPort') == 8080)
                for field in ('environment', 'secrets'):
                    if field in container:
                        container[field] = sorted(container[field], key=lambda v: v['name'])
            containers.sort(key=lambda v: v['name'])
            expected_task = copy.deepcopy(expected['task'])
            for container in expected_task['containerDefinitions']:
                for field in ('environment', 'secrets'):
                    if field in container: container[field].sort(key=lambda v: v['name'])
            expected_task['containerDefinitions'].sort(key=lambda v: v['name'])
            exact(task, expected_task, 'task')
            service = copy.deepcopy(response['service'])
            keys(service, tuple(expected['service']) + ('taskDefinition',), MODEL['service_return_only'])
            require(service.pop('taskDefinition') == arn)
            for field in MODEL['service_return_only']:
                if field in service: validate_metadata(field, service.pop(field), self.account, self.region)
            for field in ('subnets', 'securityGroups'):
                service['networkConfiguration']['awsvpcConfiguration'][field].sort()
            exact(service, expected['service'], 'service')
            return dict(task_definition_arn=arn, revision=int(arn.rsplit(':', 1)[1]),
                        intent_sha256=expected['intent_sha256'])
        except Exception:
            raise Rejected('E1_NORMAL_DELIVERY_REJECTED') from None

    def validate_registration_readback(self, intent, raw):
        """Validate registration BEFORE any service mutation/startup.

        This deliberately supplies an expected service snapshot only to reuse the
        closed task normalization. It returns task identity, never service or E3
        evidence. WP4B must separately observe/reconcile the real service.
        """
        try:
            task = decode(raw)
            require(type(task) is dict and type(task.get('taskDefinitionArn')) is str)
            synthetic = copy.deepcopy(intent['service'])
            synthetic['taskDefinition'] = task['taskDefinitionArn']
            return self.validate_readback(intent, canonical({'taskDefinition': task, 'service': synthetic}))
        except Exception:
            raise Rejected('E1_NORMAL_DELIVERY_REJECTED') from None


def defaults(value, admitted, path):
    require(type(value) is dict)
    for field, allowed in admitted.items():
        if field in value:
            require(any(type(value[field]) is type(item) and value[field] == item for item in allowed))
            value.pop(field)


def validate_metadata(field, value, account, region):
    if field == 'revision': require(type(value) is int and value > 0)
    elif field == 'status': require(value == 'ACTIVE')
    elif field in ('registeredAt', 'createdAt'):
        match(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z', value)
    elif field == 'registeredBy': match(r'arn:aws:(?:iam|sts)::' + account + r':[A-Za-z0-9_./:@-]+', value)
    elif field == 'compatibilities': require(value == ['FARGATE'])
    elif field == 'requiresAttributes': require(value == [])
    elif field == 'deregisteredAt': require(value is None)
    elif field == 'taskDefinitionArn':
        match(r'arn:aws:ecs:' + region + ':' + account + r':task-definition/[A-Za-z0-9_-]+:[1-9][0-9]*', value)
    else: require(False)
