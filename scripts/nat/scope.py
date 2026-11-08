"""Closed DEV NAT scope shared by E15-F/H; no lifecycle execution dependency."""
import copy
import re
from scripts.lifecycle import contract as c
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
