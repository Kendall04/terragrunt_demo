"""Synthetic protected observations, including real WP4B-generated receipts."""
import copy
from scripts.normal_delivery import authorization as a
from scripts.tests.delivery.fixtures import setup, OP, NEXT, Records
from scripts.recovery.application import Emergency, Cleanup
from scripts.recovery.nat import Nat
from scripts.recovery.ports import ApplicationRuntime, NatRuntime


class Runtime(ApplicationRuntime, NatRuntime):
    def __init__(self):
        self.time = 1000
        self.calls, self.effects, self.hidden = [], {}, set()
        self.hook = None
        self.observe_hook = None
    def now(self): return self.time
    def effect(self, token, deadline):
        if token.split('/')[-1] in self.hidden:
            return dict(token=token, request_sha256=None, state='UNKNOWN', result=None)
        return copy.deepcopy(self.effects.get(token, dict(token=token, request_sha256=None, state='ABSENT', result=None)))
    def mutate(self, stage, token, request, deadline):
        self.calls.append((stage, copy.deepcopy(request)))
        if hasattr(self, 'nat_context'):
            observed = self.nat_context['observed']
            if stage == 'assign_eip': observed['association_eni'] = request['NetworkInterfaceId']
            elif stage == 'change_rt':
                observed['default_route_eni'] = request['NetworkInterfaceId']
                self.nat_context['route_exists'] = True
            elif stage == 'disable_sdc': observed['source_dest_check'] = request['SourceDestCheck']['Value']
        if hasattr(self, 'state'):
            if stage in ('scale', 'scale_zero'):
                color = next(c for c, s in self.state['services'].items() if s['service'] == request['service'])
                s = self.state['services'][color]
                s.update(desired=request['desiredCount'], running=request['desiredCount'])
                s['settings']['desiredCount'] = request['desiredCount']
            elif stage == 'switch': self.state['normal_targets'] = [request['target']]
            elif stage == 'candidate': self.state['candidate_targets'] = [request['target']]
        self.effects[token] = dict(token=token, request_sha256=a.sha(a.canonical(request)), state='APPLIED', result=copy.deepcopy(request))
        if self.hook: self.hook(stage)
    def config(self): return copy.deepcopy(self.configuration)
    def observe(self, operation, deadline):
        if self.observe_hook: self.observe_hook(self)
        s = copy.deepcopy(self.state)
        s.update(operation=operation, observed_at=self.time)
        for color, svc in s['services'].items():
            if svc['targets'] == 'automatic':
                svc['targets'] = [dict(id='target-' + str(n), state='healthy', revision=svc['revision'],
                    service=svc['service'], target_group=self.configuration['colors'][color]['target_group'],
                    operation=operation, environment=s['environment']) for n in range(svc['running'])]
        return s
    def context(self, action, deadline):
        result = copy.deepcopy(self.nat_context)
        result['observed_at'] = self.time
        return result


def application(kind='emergency', running=0, endpoint='deploy-dev'):
    facts, auth, records, normal, process, delivery, raw = setup(endpoint)
    receipt = delivery.run(OP, raw)
    assert receipt['status'] == 'SUCCESS'
    env = a.ENDPOINTS[endpoint]
    runtime = Runtime()
    runtime.configuration = dict(environment=env, colors=copy.deepcopy(facts.members[env]['colors']),
                                 cleanup_rule='demo-' + env + '-cleanup', history=dict(blue=OP, green=None))
    colors = runtime.configuration['colors']
    runtime.state = dict(environment=env, operation=NEXT, observed_at=1000,
        listener=colors['blue']['listener'], rule=colors['blue']['candidate_rule'],
        normal_targets=[colors['green']['target_group']], candidate_targets=[colors['blue']['target_group']], services={})
    for color in ('blue', 'green'):
        settings = copy.deepcopy(receipt['intent']['service'])
        settings.update(service=colors[color]['service'], taskDefinition=normal.revision, desiredCount=running if color == 'blue' else 2)
        runtime.state['services'][color] = dict(cluster=colors[color]['cluster'], service=colors[color]['service'],
            revision=normal.revision, desired=settings['desiredCount'], running=settings['desiredCount'], pending=0,
            stable=True, targets='automatic', task=copy.deepcopy(normal.task), settings=settings)
    controller = Emergency(auth, records, runtime) if kind == 'emergency' else Cleanup(env, records, runtime)
    return controller, runtime, records, facts


def nat(action='assign_eip'):
    runtime = Runtime()
    spec = dict(ami='ami-approved', launch_template='lt-protected', launch_template_version=7,
        user_data_sha256='a'*64, instance_profile='nat-profile', role='nat-role', security_groups=['sg-nat'],
        http_tokens='required', associate_public_ip=True, delete_on_termination=True,
        instance_type='t3.micro', tags=dict(Role='nat', Group='a', Az='us-east-1a'))
    m = dict(environment='dev', vpc='vpc-dev', subnet='subnet-a', az='us-east-1a', asg='nat-a',
             instance='i-member', eni='eni-member', eip='eipalloc-a', route_table='rtb-a', spec=spec)
    observed = copy.deepcopy(m)
    observed.update(lifecycle='InService', health='Healthy', eni_instance=m['instance'], route_vpc=m['vpc'], eip_environment='dev',
                    association_eni=None, default_route_eni=None, source_dest_check=True)
    runtime.nat_context = dict(membership=m, observed=observed, observed_at=1000, route_exists=True)
    records = Records()
    return Nat('dev', action, records, runtime), runtime, records
