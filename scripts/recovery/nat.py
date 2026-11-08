"""Closed authorization model for the three existing NAT handlers.

Protected configuration is published by the security controller, not the event
producer. Instance membership must come from independent ASG/EC2 observations.
No prefix, name or tag grants membership. No launch-template mutation port exists.
"""
import copy
from scripts.normal_delivery import authorization as a
from scripts.recovery.journal import Journal
from scripts.recovery.ports import NatRuntime


ACTIONS = ('assign_eip', 'change_rt', 'disable_sdc')
SPEC = ('ami', 'launch_template', 'launch_template_version', 'user_data_sha256',
        'instance_profile', 'role', 'security_groups', 'http_tokens',
        'associate_public_ip', 'delete_on_termination', 'instance_type', 'tags')
MEMBERSHIP = ('environment', 'vpc', 'subnet', 'az', 'asg', 'instance', 'eni',
              'eip', 'route_table', 'spec')


class Nat:
    """Installed action + protected membership resolver; caller input is {}.

    runtime.context(action, deadline) returns a fresh protected membership and
    independent observed resource context. It must verify exact current ASG
    InService/Healthy membership, ENI attachment, subnet/VPC/AZ and ownership of
    EIP/route table against protected configuration, never event tags. A changing
    replacement instance requires a new protected operation. WP4D supplies these
    read-only authenticated adapters; this slice does not install AWS handlers.
    """
    def __init__(self, environment, action, records, runtime):
        a.require(action in ACTIONS)
        a.require(isinstance(runtime, NatRuntime))
        self.environment, self.action, self.runtime = environment, action, runtime
        self.journal = Journal(environment, action, records, runtime, (action,))

    def context(self):
        now = self.runtime.now()
        value = self.runtime.context(self.action, now + 30)
        a.keys(value, ('membership', 'observed', 'observed_at', 'route_exists'))
        a.require(type(value['observed_at']) is int and now <= value['observed_at'] <= self.runtime.now())
        a.require(type(value['route_exists']) is bool)
        m = value['membership']
        a.keys(m, MEMBERSHIP)
        a.exact(m['environment'], self.environment, 'environment')
        for key in MEMBERSHIP:
            if key not in ('environment', 'spec'):
                a.require(type(m[key]) is str and bool(m[key]))
        a.keys(m['spec'], SPEC)
        spec = m['spec']
        a.require(spec['http_tokens'] == 'required' and spec['instance_type'] == 't3.micro')
        a.require(spec['associate_public_ip'] is True and spec['delete_on_termination'] is True)
        a.require(type(spec['launch_template_version']) is int and spec['launch_template_version'] > 0)
        a.match(r'[0-9a-f]{64}', spec['user_data_sha256'])
        for key in ('ami', 'launch_template', 'instance_profile', 'role'):
            a.require(type(spec[key]) is str and bool(spec[key]))
        a.require(type(spec['security_groups']) is list and len(spec['security_groups']) == 1)
        a.require(type(spec['tags']) is dict and spec['tags'].get('Role') == 'nat')
        o = value['observed']
        a.keys(o, (*MEMBERSHIP, 'lifecycle', 'health', 'eni_instance', 'route_vpc', 'eip_environment',
                   'association_eni', 'default_route_eni', 'source_dest_check'))
        for field in ('association_eni', 'default_route_eni'):
            a.require(o[field] is None or type(o[field]) is str)
        a.require(type(o['source_dest_check']) is bool)
        for key in MEMBERSHIP: a.exact(o[key], m[key], 'observed.' + key)
        a.require(o['lifecycle'] == 'InService' and o['health'] == 'Healthy')
        a.exact(o['eni_instance'], m['instance'], 'ENI attachment')
        a.exact(o['route_vpc'], m['vpc'], 'route VPC')
        a.exact(o['eip_environment'], self.environment, 'EIP ownership')
        return copy.deepcopy(dict(membership=m, route_exists=value['route_exists'],
            state={k: o[k] for k in ('association_eni', 'default_route_eni', 'source_dest_check')}))

    def prepare(self):
        return self.context()

    def validate(self, value):
        a.keys(value, ('membership', 'route_exists', 'state'))
        a.keys(value['membership'], MEMBERSHIP)
        a.exact(value['membership']['environment'], self.environment, 'retained environment')
        a.require(type(value['route_exists']) is bool)

    def actions(self, value):
        m = value['membership']
        if self.action == 'assign_eip':
            request = dict(AllocationId=m['eip'], NetworkInterfaceId=m['eni'], AllowReassociation=True)
        elif self.action == 'change_rt':
            request = dict(RouteTableId=m['route_table'], DestinationCidrBlock='0.0.0.0/0',
                           NetworkInterfaceId=m['eni'], action='replace_route' if value['route_exists'] else 'create_route')
        else:
            request = dict(InstanceId=m['instance'], SourceDestCheck=dict(Value=False))
        return {self.action: request}

    def guard(self, op, stage, effects):
        a.exact(self.context(), op['domain'], 'fresh NAT membership')

    def final(self, op, effects):
        current = self.context()
        a.exact(current['membership'], op['domain']['membership'], 'final membership')
        m = current['membership']
        field, expected = {'assign_eip': ('association_eni', m['eni']),
                           'change_rt': ('default_route_eni', m['eni']),
                           'disable_sdc': ('source_dest_check', False)}[self.action]
        a.exact(current['state'][field], expected, 'authoritative final NAT state')
        # effect() requires an independent operation-attributed readback of the
        # exact address/default route/SourceDestCheck result, not an API ACK.
        return current

    def run(self, operation, raw):
        return self.journal.run(operation, raw, self)
