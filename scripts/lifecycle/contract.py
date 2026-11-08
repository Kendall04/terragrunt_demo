"""Closed WP5 lifecycle input and plan boundary; no AWS or Terraform I/O."""
import copy
import hashlib
import json
import re

LAYERS = ('shared', 'secrets', 'global', 'data', 'platform', 'apps', 'edge')
ORDINARY = frozenset(('shared', 'secrets', 'global', 'platform', 'edge'))
HIGH_RISK = frozenset(LAYERS)
OPERATIONS = frozenset(('plan', 'create', 'reconcile', 'teardown'))
RUNTIME_FIELDS = {
    'aws_ecs_service': ('task_definition', 'desired_count'),
    'aws_lb_listener': ('default_action',),
    'aws_lb_listener_rule': ('action',),
}
EXECUTION_FIELDS = {
    'aws_ecs_service': ('cluster', 'launch_type', 'platform_version',
                        'network_configuration', 'load_balancer', 'enable_execute_command'),
    'aws_instance': ('ami', 'user_data', 'user_data_base64', 'iam_instance_profile',
                     'subnet_id', 'vpc_security_group_ids', 'key_name', 'metadata_options'),
    'aws_autoscaling_group': ('launch_template', 'vpc_zone_identifier'),
}
PROTECTED_TYPES = ('aws_iam_', 'aws_kms_', 'aws_secretsmanager_', 'aws_s3_',
                   'aws_lambda_', 'aws_codebuild_', 'aws_ecr_', 'aws_launch_template',
                   'aws_cloudwatch_event_')


def require(ok, reason):
    if not ok:
        raise ValueError('E1_WP5_REJECTED: ' + reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def keys(value, expected, reason):
    require(type(value) is dict and set(value) == set(expected), reason)


def request(binding, value):
    keys(value, ('operation_id', 'operation', 'layer', 'revision', 'parameters'), 'closed request')
    require(type(value['operation_id']) is str and bool(re.fullmatch(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', value['operation_id'])), 'operation UUID')
    require(value['operation'] in OPERATIONS, 'operation')
    high_risk = '/infra-high-risk-' in binding
    require(value['layer'] in (HIGH_RISK if high_risk else ORDINARY), 'responsibility/layer')
    require(value['operation'] != 'teardown' or high_risk, 'teardown requires high-risk')
    require(type(value['revision']) is str and bool(re.fullmatch('[0-9a-f]{64}', value['revision'])), 'exact contract revision')
    # Initial public contract permits no executable/network/identity parameters.
    # The only routine knob is a boolean controlling pre-existing alarms.
    require(type(value['parameters']) is dict and set(value['parameters']) <= {'enable_alarms'}, 'bounded parameters')
    require(not value['parameters'] or value['layer'] == 'data', 'alarm parameter layer')
    require(all(type(v) is bool for v in value['parameters'].values()), 'parameter types')
    return copy.deepcopy(value)


def quiescent(observation, environment):
    """Authoritative adapter must observe both exact services and all tasks."""
    keys(observation, ('environment', 'services', 'tasks', 'complete'), 'live quiescence shape')
    require(observation['environment'] == environment and observation['complete'] is True, 'complete live environment')
    expected = {'demo-' + environment + '-app-api-' + color + '-svc' for color in ('blue', 'green')}
    require(type(observation['services']) is dict and set(observation['services']) == expected, 'exact two services')
    require(observation['tasks'] == [], 'no live/pending tasks')
    for service in observation['services'].values():
        if service == {'absence':'EXACT_ECS_MISSING'}:continue
        keys(service, ('desired', 'running', 'pending'), 'service counts')
        require(all(type(v) is int and v == 0 for v in service.values()), 'bounded quiescence')


def authorize(binding, value, protected, installed):
    value = request(binding, value)
    keys(protected, ('binding', 'environment', 'account', 'region', 'active_contracts', 'installations',
                     'layers', 'bootstrap', 'operation_approvals', 'teardown_approvals'), 'protected configuration')
    require(protected['binding'] == binding, 'fixed execution binding')
    environment = binding.rsplit('-', 1)[1]
    require(environment in ('dev', 'prod') and protected['environment'] == environment, 'environment')
    revision = value['revision']
    require(revision in protected['active_contracts'], 'active contract required')
    reference = protected['installations'].get(revision)
    keys(reference, ('bucket', 'key', 'version_id', 'sha256', 'binding', 'source_commit'), 'installation identity')
    require(reference['sha256'] == revision and reference['binding'] == binding and
            reference['key'] == 'bundles/sha256/' + revision + '.json', 'immutable package selection')
    require(type(reference['version_id']) is str and reference['version_id'].strip() == reference['version_id']
            and bool(reference['version_id']) and reference['version_id'].lower() not in ('null', 'latest'), 'exact version')
    require(bool(re.fullmatch('[0-9a-f]{40}', reference['source_commit'])), 'reviewed immutable source revision')
    require(installed == reference, 'verified readback identity')
    layer = protected['layers'].get(value['layer'])
    keys(layer, ('root', 'variables', 'addresses', 'membership', 'backend'), 'protected layer')
    require(layer['root'] == 'terraform/modules/target/' + environment + '/' + value['layer'], 'fixed root')
    backend = layer['backend']
    keys(backend, ('bucket', 'key', 'region'), 'fixed backend')
    require(backend['key'] == 'e1/lifecycle/' + environment + '/' + value['layer'] + '/terraform.tfstate', 'separate layer state')
    require(backend['bucket'] == 'e1-lifecycle-' + environment + '-' + protected['account'] + '-' + protected['region']
            and backend['region'] == protected['region'], 'separate environment state')
    require(layer['variables'].get('account_id') == protected['account'] and
            layer['variables'].get('region') == protected['region'], 'protected provider identity')
    require(type(layer['addresses']) is dict and type(layer['membership']) is dict and
            set(layer['membership']) <= set(layer['addresses']), 'protected graph membership')
    if value['layer'] in ('data', 'apps'):
        prerequisite = 'sql_passwords' if value['layer'] == 'data' else 'connection_string'
        require(protected['bootstrap'].get(prerequisite) == 'ADMIN_VERIFIED_READY', 'secret bootstrap prerequisite')
    if '/infra-high-risk-' in binding and value['operation'] != 'plan':
        require(protected['operation_approvals'].get(value['operation_id']) == {
            'request_sha256':digest(canonical(value)), 'environment':environment}, 'exact protected operator approval')
    if value['operation'] == 'teardown':
        require(protected['teardown_approvals'].get(value['operation_id']) ==
                {'revision': revision, 'layer': value['layer'], 'environment': environment}, 'exact protected teardown approval')
    return value, copy.deepcopy(layer)


def validate_plan(value, layer, plan, observation=None, environment=None):
    """Validate the actual saved plan before execution; unknown decisions reject.

    Fixed package admission protects code *before* plan generation. This checker
    adds runtime-state/ownership enforcement and is not a hostile-HCL sandbox.
    """
    require(type(plan) is dict and plan.get('format_version') == '1.2', 'supported Terraform plan format')
    require(plan.get('errored', False) is False, 'complete plan')
    require(not plan.get('deferred_changes'), 'unresolved deferred work')
    # Normal delivery legitimately changes fields that Terraform ignores.
    # Admit only that drift, with exact published resource membership. Other
    # drift needs protected reconciliation rather than silently adopting it.
    for drift in plan.get('resource_drift',[]):
        address,kind=drift.get('address'),drift.get('type')
        require(address in layer['addresses'] and layer['addresses'][address]==kind and kind in RUNTIME_FIELDS,'unexpected drift')
        change=drift['change'];before,after=change['before'],change['after']
        require(before['id']==after['id']==layer['membership'].get(address),'drift exact membership')
        require(not any(change.get('after_unknown',{}).values()),'unknown drift')
        changed={k for k in set(before)|set(after) if before.get(k)!=after.get(k)}
        require(changed<=set(RUNTIME_FIELDS[kind]),'non-runtime drift')
    changes = plan.get('resource_changes')
    require(type(changes) is list, 'resource changes')
    require(plan.get('applyable',True) is True or all(x.get('change',{}).get('actions')==['no-op'] for x in changes),'nonapplyable changed plan')
    seen = set()
    needs_quiescence = value['operation'] == 'teardown'
    for resource in changes:
        address, kind = resource.get('address'), resource.get('type')
        require(type(address) is str and address not in seen and address in layer['addresses'], 'exact installed address')
        seen.add(address)
        require(kind == layer['addresses'][address], 'installed resource type')
        if resource.get('mode') == 'data':
            require(resource['change']['actions'] in (['read'], ['no-op']), 'read-only data source')
            continue
        require(type(kind) is str and not kind.startswith(PROTECTED_TYPES), 'security-root ownership')
        change = resource.get('change')
        keys(change, ('actions', 'before', 'after', 'after_unknown', 'before_sensitive', 'after_sensitive'), 'closed change')
        actions = change['actions']
        require(actions in (['no-op'], ['create'], ['update'], ['delete'], ['delete', 'create'], ['create', 'delete']), 'bounded actions')
        if value['operation'] == 'create':require(actions in (['create'], ['no-op']), 'create cannot mutate existing resources')
        if value['operation'] == 'reconcile':require(actions in (['no-op'], ['update']), 'replacement needs approved teardown/recreate')
        if value['operation'] == 'teardown':require(actions in (['delete'], ['no-op']), 'teardown cannot introduce resources')
        if actions == ['no-op']:continue
        before, after = change['before'], change['after']
        if before is not None and after is not None:
            for field in ('tags', 'tags_all'):
                require(not change['after_unknown'].get(field) and before.get(field) == after.get(field), 'immutable authorizing tags')
        if before is not None:
            require(before.get('id') == layer['membership'].get(address), 'protected existing resource membership')
        if actions == ['update']:
            for field in RUNTIME_FIELDS.get(kind, ()) + EXECUTION_FIELDS.get(kind, ()):
                require(not change['after_unknown'].get(field) and before.get(field) == after.get(field), 'runtime/security binding mutation: ' + field)
        if 'create' in actions and kind == 'aws_ecs_service':
            require(not change['after_unknown'].get('desired_count') and after.get('desired_count') == 0 and
                    after.get('enable_execute_command') is False and after.get('launch_type') == 'FARGATE', 'inert bootstrap service')
        if 'create' in actions and kind == 'aws_ecs_task_definition':
            require(not after.get('task_role_arn') and not after.get('execution_role_arn'), 'no bootstrap workload authority')
            containers = json.loads(after['container_definitions'])
            require(all(not c.get('secrets') for c in containers), 'no bootstrap secret injection')
        if kind in RUNTIME_FIELDS and ('delete' in actions or (before is not None and 'create' in actions)):
            needs_quiescence = True
    if needs_quiescence:
        quiescent(observation, environment)
    return digest(canonical(plan))
