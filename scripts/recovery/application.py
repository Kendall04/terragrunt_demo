"""Protected emergency and existing inactive-color cleanup contracts.

Runtime ports are normalized authoritative observations, not caller assertions.
No registration, image publication, E3, role or lifecycle mutation ports exist.
"""
import copy
from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.recovery.journal import Journal
from scripts.recovery.ports import ApplicationRuntime


class History:
    """Read-only validation of actual WP4B evidence; no delivery execution port."""
    read = d.Delivery.read
    operation_contract = d.Delivery.operation_contract
    retained_operation = d.Delivery.retained_operation
    stage_request = d.Delivery.stage_request
    stage_plan = d.Delivery.stage_plan
    stored_effect = d.Delivery.stored_effect
    validate_effect = d.Delivery.validate_effect
    check_effect = d.Delivery.check_effect
    receipt_effects = d.Delivery.receipt_effects
    activation = d.Delivery.activation
    activation_key = d.Delivery.activation_key
    e3_context = d.Delivery.e3_context
    routes = d.Delivery.routes
    prepared = d.Delivery.prepared

    def __init__(self, auth, records):
        self.auth, self.records = auth, records
        self.env = a.ENDPOINTS[auth.endpoint]

    def success(self, operation):
        d.identity(operation)
        op = self.retained_operation(operation)
        a.require(op is not None)
        receipt = self.read(operation + '/success', True)
        a.keys(receipt, ('schema', 'status', 'environment', 'operation_id', 'action', 'history',
                         'intent', 'registration', 'activation', 'activation_sha256', 'final', 'effects'))
        a.require(receipt['schema'] == 'E1_DELIVERY_RECEIPT_V1' and receipt['status'] == 'SUCCESS')
        for key in ('environment', 'operation_id', 'action', 'history', 'intent'):
            a.exact(receipt[key], op[key], 'historical.' + key)
        self.receipt_effects(op, receipt['effects'])
        proof = self.activation(op, receipt['activation_sha256'])
        a.exact(proof, receipt['activation'], 'historical activation')
        a.exact(receipt['activation_sha256'], self.stage_plan(op, 'switch')['activation_sha256'], 'selected proof')
        a.exact(receipt['registration'], proof['registration'], 'historical revision')
        self.routes(op, receipt['final'], True, True)
        self.prepared(op, receipt['final'], proof['registration']['task_definition_arn'], op['request']['replicas'])
        return receipt


class Application:
    """Installed environment; config() is protected security-controller data.

    config contains exact WP4A resource positions for both colors, fixed cleanup
    schedule name and protected successful history references. observe() describes
    both services and SINGLE-target routing; weighted/ambiguous routing rejects.
    All ports finish before deadline. AWS cannot make guard+mutation atomic.
    """
    def __init__(self, environment, runtime):
        a.require(environment in ('dev', 'prod'))
        a.require(isinstance(runtime, ApplicationRuntime))
        self.environment, self.runtime = environment, runtime

    def config(self):
        c = self.runtime.config()
        a.keys(c, ('environment', 'colors', 'cleanup_rule', 'history'))
        a.exact(c['environment'], self.environment, 'installed environment')
        a.keys(c['colors'], ('blue', 'green'))
        a.keys(c['history'], ('blue', 'green'))
        for color, m in c['colors'].items():
            a.keys(m, ('roles', 'secret_arn', 'kms_key_arn', 'log_group', 'cluster', 'service',
                       'subnets', 'security_groups', 'target_group', 'listener', 'candidate_rule'))
            for field in ('cluster', 'service', 'listener', 'candidate_rule', 'target_group'):
                a.require(type(m[field]) is str and bool(m[field]))
        b, g = c['colors']['blue'], c['colors']['green']
        for field in ('cluster', 'listener', 'candidate_rule'): a.exact(b[field], g[field], field)
        a.require(b['service'] != g['service'] and b['target_group'] != g['target_group'])
        a.require(type(c['cleanup_rule']) is str and bool(c['cleanup_rule']))
        return copy.deepcopy(c)

    def observe(self, config, operation):
        a.exact(self.config(), config, 'current protected configuration')
        now = self.runtime.now()
        s = self.runtime.observe(operation, now + 30)
        a.keys(s, ('environment', 'operation', 'observed_at', 'listener', 'rule',
                   'normal_targets', 'candidate_targets', 'services'))
        a.exact(s['environment'], self.environment, 'observed environment')
        a.exact(s['operation'], operation, 'observed operation')
        a.require(type(s['observed_at']) is int and now <= s['observed_at'] <= self.runtime.now())
        a.exact(s['listener'], config['colors']['blue']['listener'], 'listener')
        a.exact(s['rule'], config['colors']['blue']['candidate_rule'], 'candidate rule')
        a.keys(s['services'], ('blue', 'green'))
        for color, svc in s['services'].items():
            a.keys(svc, ('cluster', 'service', 'revision', 'desired', 'running', 'pending',
                         'stable', 'targets', 'task', 'settings'))
            for key in ('cluster', 'service'): a.exact(svc[key], config['colors'][color][key], key)
            for key in ('desired', 'running', 'pending'):
                a.require(type(svc[key]) is int and 0 <= svc[key] <= 100)
            a.require(type(svc['stable']) is bool and type(svc['targets']) is list)
        for field in ('normal_targets', 'candidate_targets'):
            a.require(type(s[field]) is list and len(s[field]) == 1)
            a.require(s[field][0] in [m['target_group'] for m in config['colors'].values()])
        return copy.deepcopy(s)

    def inactive(self, config, snapshot):
        colors = config['colors']
        active = next(c for c in colors if colors[c]['target_group'] == snapshot['normal_targets'][0])
        inactive = 'green' if active == 'blue' else 'blue'
        a.exact(snapshot['candidate_targets'], [colors[inactive]['target_group']], 'inactive mapping')
        return active, inactive

    def topology(self, value, snapshot, effects):
        c, active, color = value['config'], value['active'], value['color']
        a.exact(snapshot['normal_targets'], [c['colors'][color if 'switch' in effects else active]['target_group']], 'normal route')
        a.exact(snapshot['candidate_targets'], [c['colors'][active if 'candidate' in effects else color]['target_group']], 'candidate route')

    def evidence(self, snapshot):
        # Deliberate projection: unused provider task/settings objects never enter
        # a success receipt. Resource identities/counts were validated above.
        return {**{k: snapshot[k] for k in ('environment', 'operation', 'observed_at',
                    'listener', 'rule', 'normal_targets', 'candidate_targets')},
                'services': {color: {k: svc[k] for k in ('cluster', 'service', 'desired', 'running', 'pending')}
                             for color, svc in snapshot['services'].items()}}


class Emergency(Application):
    def __init__(self, auth, records, runtime):
        a.require(type(auth) is a.Authorizer)
        super().__init__(a.ENDPOINTS[auth.endpoint], runtime)
        self.auth, self.history = auth, History(auth, records)
        self.journal = Journal(self.environment, 'emergency', records, runtime,
                               ('scale', 'switch', 'candidate', 'schedule'))

    def current(self, value):
        receipt = self.history.success(value['history'])
        a.exact(a.sha(a.canonical(receipt)), value['history_sha256'], 'protected history')
        intent = self.auth.authorize(a.canonical(value['request']))
        a.exact(intent, value['intent'], 'current eligibility/binding')
        for key in ('release', 'task', 'service', 'routing', 'color', 'qualification_sha256'):
            a.exact(intent[key], receipt['intent'][key], 'previously activated ' + key)
        return receipt

    def prepare(self):
        c = self.config()
        s = self.observe(c, self.operation)
        active, color = self.inactive(c, s)
        receipt = self.history.success(c['history'][color])
        a.exact(receipt['intent']['color'], color, 'historical color')
        request = dict(release_id=receipt['intent']['release']['release_id'],
                       replicas=receipt['intent']['service']['desiredCount'])
        intent = self.auth.authorize(a.canonical(request))
        value = dict(config=c, active=active, color=color, history=c['history'][color],
                     history_sha256=a.sha(a.canonical(receipt)), request=request, intent=intent,
                     revision=receipt['registration']['task_definition_arn'],
                     initial=s['services'][color])
        self.current(value)
        self.candidate(value, s, False)
        a.require(value['initial']['desired'] in (0, request['replicas']))
        return value

    def validate(self, value):
        a.keys(value, ('config', 'active', 'color', 'history', 'history_sha256', 'request', 'intent', 'revision', 'initial'))
        a.require(value['active'] in ('blue', 'green') and value['color'] in ('blue', 'green')
                  and value['active'] != value['color'])

    def candidate(self, value, snapshot, healthy):
        svc = snapshot['services'][value['color']]
        a.exact(svc['revision'], value['revision'], 'recoverable revision still selected')
        intent = value['intent']
        a.exact(a.resource_positions(a.envelope(self.auth.facts.environment(self.auth.endpoint), 'endpoint', self.auth.endpoint)),
                value['config']['colors'][value['color']], 'protected membership')
        checked = self.auth.validate_registration_readback(intent, a.canonical(svc['task']))
        a.exact(checked['task_definition_arn'], value['revision'], 'exact task content')
        settings = copy.deepcopy(intent['service'])
        settings.update(taskDefinition=value['revision'], desiredCount=svc['desired'])
        a.exact(svc['settings'], settings, 'service configuration')
        if healthy:
            count = intent['service']['desiredCount']
            a.require(svc['stable'] is True and svc['pending'] == 0
                      and svc['desired'] == svc['running'] == count and len(svc['targets']) == count)
            seen = set()
            for target in svc['targets']:
                a.keys(target, ('id', 'state', 'revision', 'service', 'target_group', 'operation', 'environment'))
                target_id = target['id']
                a.require(type(target_id) is str)
                canonical_id = target_id.strip()
                a.require(bool(canonical_id))
                # Keep the exact adapter identity; do not silently merge padded IDs.
                a.require(target_id == canonical_id and canonical_id not in seen)
                seen.add(canonical_id)
                a.exact(target['state'], 'healthy', 'target health')
                for key, expected in dict(revision=value['revision'], service=svc['service'],
                        target_group=value['config']['colors'][value['color']]['target_group'],
                        operation=self.operation, environment=self.environment).items():
                    a.exact(target[key], expected, 'target.' + key)

    def actions(self, value):
        m = value['config']['colors'][value['color']]
        old = value['config']['colors'][value['active']]
        actions = {}
        if value['initial']['desired'] == 0:
            actions['scale'] = dict(cluster=m['cluster'], service=m['service'], desiredCount=value['request']['replicas'])
        actions['switch'] = dict(listener=m['listener'], target=m['target_group'])
        actions['candidate'] = dict(rule=m['candidate_rule'], target=old['target_group'])
        actions['schedule'] = dict(environment=self.environment, cluster=old['cluster'], service=old['service'],
                                    rule=value['config']['cleanup_rule'], target_id='scale-down')
        return actions

    def guard(self, op, stage, effects):
        value = op['domain']
        self.current(value)
        s = self.observe(value['config'], self.operation)
        self.topology(value, s, effects)
        self.candidate(value, s, stage != 'scale')
        if stage == 'scale': a.exact(s['services'][value['color']], value['initial'], 'fresh pre-scale state')

    def final(self, op, effects):
        self.guard(op, 'final', effects)
        s = self.observe(op['domain']['config'], self.operation)
        self.topology(op['domain'], s, effects)
        self.candidate(op['domain'], s, True)
        result = self.evidence(s)
        candidate = s['services'][op['domain']['color']]
        result['recovered'] = dict(revision=candidate['revision'], stable=candidate['stable'], targets=candidate['targets'])
        return result

    def run(self, operation, raw):
        self.operation = operation
        return self.journal.run(operation, raw, self)


class Cleanup(Application):
    def __init__(self, environment, records, runtime):
        super().__init__(environment, runtime)
        self.journal = Journal(environment, 'cleanup', records, runtime, ('scale_zero', 'remove_target', 'delete_rule'))

    def prepare(self):
        c = self.config()
        s = self.observe(c, self.operation)
        active, color = self.inactive(c, s)
        value = dict(config=c, active=active, color=color, initial=s)
        self.safe(value, s)
        return value

    def validate(self, value):
        a.keys(value, ('config', 'active', 'color', 'initial'))
        a.require(value['active'] in ('blue', 'green') and value['color'] in ('blue', 'green')
                  and value['active'] != value['color'])

    def safe(self, value, s):
        self.topology(value, s, {})
        svc = s['services'][value['active']]
        a.require(svc['desired'] > 0 and svc['running'] > 0)

    def actions(self, value):
        m = value['config']['colors'][value['color']]
        result = {}
        initial = value['initial']['services'][value['color']]
        if initial['desired'] or initial['running']:
            result['scale_zero'] = dict(cluster=m['cluster'], service=m['service'], desiredCount=0)
        result['remove_target'] = dict(Rule=value['config']['cleanup_rule'], Ids=['scale-down'])
        result['delete_rule'] = dict(Name=value['config']['cleanup_rule'])
        return result

    def guard(self, op, stage, effects):
        s = self.observe(op['domain']['config'], self.operation)
        self.safe(op['domain'], s)
        if stage == 'scale_zero':
            for color in ('blue', 'green'):
                a.exact(s['services'][color], op['domain']['initial']['services'][color], 'fresh cleanup state')
        else:
            a.require(s['services'][op['domain']['color']]['desired'] == 0)

    def final(self, op, effects):
        self.guard(op, 'final', effects)
        s = self.observe(op['domain']['config'], self.operation)
        self.safe(op['domain'], s)
        a.require(s['services'][op['domain']['color']]['desired'] == 0)
        return self.evidence(s)

    def run(self, operation, raw):
        self.operation = operation
        return self.journal.run(operation, raw, self)
