#!/usr/bin/env python3
"""Offline recovery blueprint and review. No SDK, credentials or cloud executor."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

ACCOUNT = '341936017254'
REGION = 'us-east-1'
BUCKET = 'terragrunt-demo-sql-backup-341936017254-fa48a32dc9'
BACKEND = 'e1-lifecycle-dev-341936017254-us-east-1'
ROLE_NAME = 'demo-dev-data-sql-ec2-role'
ROLE = f'arn:aws:iam::{ACCOUNT}:role/{ROLE_NAME}'
PROFILE = f'arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile'
BACKUP_KEY = f'arn:aws:kms:{REGION}:{ACCOUNT}:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced'
TEXT_KEY = f'arn:aws:kms:{REGION}:{ACCOUNT}:key/50d3fe36-8128-4d09-ac13-8f5536a230a7'
SA_SECRET = f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/dev/db/sql-sa-password-30fCjc'
APP_SECRET = f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/dev/db/sql-app-password-2Shh56'
BASE = 'terragrunt-demo/dev/sql-backups/ec2-20261016'


def require(ok, code):
    if not ok:
        raise ValueError(code)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def trial(value):
    require(isinstance(value, str) and re.fullmatch(r'r[0-9]{8}[a-z0-9]{1,8}', value), 'INVALID_TRIAL_ID')
    return value


def render(name, bootstrap):
    trial(name)
    tags = {'Project': 'terragrunt-demo', 'Purpose': 'v2-recovery', 'Trial': name}
    # One HCL JSON template layer; input is raw Bash, never pre-escaped text.
    user_data = bootstrap.replace('${', '$${').replace('%{', '%%{')
    resources = {}

    def add(kind, key, **args):
        resources.setdefault(kind, {})[key] = args

    def ref(kind, key):
        return '${' + kind + '.' + key + '.id}'

    add('aws_vpc', 'trial', cidr_block='10.237.0.0/24', enable_dns_support=True, enable_dns_hostnames=True, tags=tags)
    vpc = ref('aws_vpc', 'trial')
    add('aws_internet_gateway', 'trial', vpc_id=vpc, tags=tags)
    for key, cidr, az in [('public', '10.237.0.0/27', '${var.az_a}'), ('a', '10.237.0.32/27', '${var.az_a}'), ('b', '10.237.0.64/27', '${var.az_b}')]:
        add('aws_subnet', key, vpc_id=vpc, cidr_block=cidr, availability_zone=az, map_public_ip_on_launch=False, tags=tags)
        add('aws_route_table', key, vpc_id=vpc, tags=tags)
        add('aws_route_table_association', key, subnet_id=ref('aws_subnet', key), route_table_id=ref('aws_route_table', key))
    add('aws_eip', 'nat', domain='vpc', tags=tags)
    add('aws_nat_gateway', 'trial', allocation_id=ref('aws_eip', 'nat'), subnet_id=ref('aws_subnet', 'public'), tags=tags, depends_on=['aws_internet_gateway.trial'])
    for key in ('public', 'a', 'b'):
        gateway = {'gateway_id': ref('aws_internet_gateway', 'trial')} if key == 'public' else {'nat_gateway_id': ref('aws_nat_gateway', 'trial')}
        add('aws_route', key, route_table_id=ref('aws_route_table', key), destination_cidr_block='0.0.0.0/0', **gateway)
    outbound = [{'from_port': p, 'to_port': p, 'protocol': 'tcp', 'cidr_blocks': ['0.0.0.0/0']} for p in (80, 443)]
    outbound += [{'from_port': 53, 'to_port': 53, 'protocol': p, 'cidr_blocks': ['10.237.0.2/32']} for p in ('udp', 'tcp')]
    for rule in outbound:
        rule.update(description='', ipv6_cidr_blocks=[], prefix_list_ids=[], security_groups=[], self=False)
    add('aws_security_group', 'host', name_prefix=name + '-', vpc_id=vpc, description='SSM outbound; SQL and API loopback only', ingress=[], egress=outbound, tags=tags)
    add('aws_vpc_endpoint', 's3', vpc_id=vpc, service_name=f'com.amazonaws.{REGION}.s3', vpc_endpoint_type='Gateway', route_table_ids=[ref('aws_route_table', k) for k in ('a', 'b')], tags=tags)
    for key in ('a', 'b'):
        add('aws_instance', key, ami='${var.sql_ami_id}', instance_type='t3.medium', subnet_id=ref('aws_subnet', key),
            associate_public_ip_address=False, iam_instance_profile='demo-dev-data-sql-ec2-profile',
            vpc_security_group_ids=[ref('aws_security_group', 'host')], user_data=user_data, user_data_replace_on_change=True,
            metadata_options=[{'http_tokens': 'required', 'http_endpoint': 'enabled'}], credit_specification=[{'cpu_credits': 'standard'}],
            root_block_device=[{'volume_size': 30, 'volume_type': 'gp3', 'encrypted': True, 'delete_on_termination': True, 'tags': tags}],
            tags=dict(tags, Name=name + '-' + key), depends_on=['aws_route.public', 'aws_route.a', 'aws_route.b',
            'aws_route_table_association.public', 'aws_route_table_association.a', 'aws_route_table_association.b', 'aws_vpc_endpoint.s3'])
    variables = {
        'sql_ami_id': {'type': 'string', 'description': 'Fresh reviewed Canonical Ubuntu 22.04 x86_64 AMI with SSM agent.',
            'validation': [{'condition': '${can(regex("^ami-[0-9a-f]{17}$", var.sql_ami_id)) && var.sql_ami_id != "ami-00000000000000000"}', 'error_message': 'Actual reviewed AMI required.'}]},
        'az_a': {'type': 'string', 'validation': [{'condition': '${can(regex("^us-east-1[a-f]$", var.az_a))}', 'error_message': 'Use us-east-1.'}]},
        'az_b': {'type': 'string', 'validation': [{'condition': '${can(regex("^us-east-1[a-f]$", var.az_b)) && var.az_b != var.az_a}', 'error_message': 'Use another us-east-1 AZ.'}]}}
    root = {'terraform': {'required_version': '= 1.13.4', 'required_providers': {'aws': {'source': 'hashicorp/aws', 'version': '= 5.100.0'}}, 'backend': {'s3': {}}},
        'provider': {'aws': {'region': REGION, 'profile': 'cnp-cert-dev', 'allowed_account_ids': [ACCOUNT]}},
        'variable': variables, 'resource': resources, 'output': {k: {'value': ref('aws_instance', k)} for k in ('a', 'b')}}
    prefix = BASE + '/' + name
    objects = f'arn:aws:s3:::{BUCKET}/{prefix}/*'
    condition = {'StringEquals': {'kms:ViaService': f's3.{REGION}.amazonaws.com'}, 'StringLike': {'kms:EncryptionContext:aws:s3:arn': objects}}
    runtime = {'Version': '2012-10-17', 'Statement': [
        {'Sid': 'RecoveryObjects', 'Effect': 'Allow', 'Action': ['s3:PutObject', 's3:GetObject', 's3:GetObjectVersion'], 'Resource': objects},
        {'Sid': 'RecoveryBackupKey', 'Effect': 'Allow', 'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': BACKUP_KEY, 'Condition': condition},
        {'Sid': 'RecoveryAppTextKey', 'Effect': 'Allow', 'Action': ['kms:Encrypt', 'kms:Decrypt'], 'Resource': TEXT_KEY,
         'Condition': {'StringEquals': {'aws:RequestedRegion': REGION}}}]}
    denies = []
    for suffix, c in [('Encryption', {'StringNotEquals': {'s3:x-amz-server-side-encryption': 'aws:kms'}}), ('Key', {'StringNotEquals': {'s3:x-amz-server-side-encryption-aws-kms-key-id': BACKUP_KEY}}), ('Conditional', {'StringNotEquals': {'s3:if-none-match': '*'}})]:
        denies.append({'Sid': 'Recovery' + name + suffix, 'Effect': 'Deny', 'Principal': '*', 'Action': 's3:PutObject', 'Resource': objects, 'Condition': c})
    security = {'SchemaVersion': 1, 'Trial': name, 'Account': ACCOUNT, 'Region': REGION, 'Status': 'LOCAL_PREPARATION_ONLY', 'AllowsCreation': False,
        'RoleInlineAddition': runtime, 'BackupKeyStatementAddition': {'Sid': 'Recovery' + name, 'Effect': 'Allow', 'Principal': {'AWS': ROLE}, 'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': '*', 'Condition': condition},
        'TextKeyStatementAddition': {'Sid': 'Recovery' + name, 'Effect': 'Allow', 'Principal': {'AWS': ROLE}, 'Action': ['kms:Encrypt', 'kms:Decrypt'], 'Resource': '*', 'Condition': {'StringEquals': {'aws:RequestedRegion': REGION}}},
        'BucketDenyAdditions': denies, 'Prefix': prefix, 'ExistingRole': ROLE, 'ExistingProfile': PROFILE,
        'ExistingSecretsReadOnly': [SA_SECRET, APP_SECRET], 'ExistingTextKey': TEXT_KEY,
        'ExistingPolicyReadbackRequired': True, 'SharedRoleImpact': 'Both hosts and all other sessions of this original role while overlay exists.',
        'KeyPolicyResourceStar': 'KMS key-policy syntax: enclosing exact backup CMK only.',
        'Preserve': ['original roles/policies', 'both CMKs', 'original secrets', 'bucket/old prefixes', 'backend/evidence'],
        'Retention': 'Verify existing parent-prefix 2+2-day rule; no historical backup dependency or retention change.',
        'Publisher': 'Exact artifact keys and publisher principal must be bound after packaging; separate PutObject and KMS addition, not granted here.',
        'Pending': ['Fresh STS/AMI/AZ/SSM metadata', 'Existing role text Encrypt/Decrypt and two secret reads', 'Backend encryption and isolated key/lock authority', 'Fresh plans and complete IAM multi-resource review', 'Cloud lifecycle/security/data deletion/budget/TTL approval']}
    return root, security


def publisher_policy(name, sha256):
    trial(name)
    require(re.fullmatch('[a-f0-9]{64}', sha256), 'ARTIFACT_HASH_REQUIRED')
    key = f'{BASE}/{name}/artifacts/{sha256}/recovery.tar'
    arn = f'arn:aws:s3:::{BUCKET}/{key}'
    condition = {'StringEquals': {'kms:ViaService': f's3.{REGION}.amazonaws.com', 'kms:EncryptionContext:aws:s3:arn': arn}}
    principal = f'arn:aws:iam::{ACCOUNT}:user/cnp-cert-admin'
    return {'ArtifactKey': key, 'Principal': principal, 'AllowsCreation': False,
            'IdentityPolicyAddition': {'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['s3:PutObject', 's3:GetObjectVersion'], 'Resource': arn},
                {'Effect': 'Allow', 'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': BACKUP_KEY, 'Condition': condition}]},
            'BackupKeyStatementAddition': {'Sid': 'RecoveryPublisher' + name, 'Effect': 'Allow', 'Principal': {'AWS': principal},
                'Action': ['kms:GenerateDataKey', 'kms:Decrypt'], 'Resource': '*', 'Condition': condition}}


def backend_policy(name):
    trial(name)
    prefix = f'e1/lifecycle/dev/recovery/{name}'
    key = prefix + '/terraform.tfstate'
    arn = f'arn:aws:s3:::{BACKEND}/' + key
    return {'Status': 'REVIEW_ADDITION_ONLY', 'AllowsCreation': False,
            'BackendEncryptionKeyBindingRequired': 'Read actual bucket encryption; bind an existing exact key only if required. No new key.',
            'IdentityPolicyAddition': {'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': arn},
                {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'], 'Resource': arn + '.tflock'},
                {'Effect': 'Allow', 'Action': 's3:ListBucket', 'Resource': f'arn:aws:s3:::{BACKEND}',
                 'Condition': {'StringLike': {'s3:prefix': [prefix + '/*']}}}]}}


def review_plan(document, root, action):
    require(action in ('create', 'delete'), 'INVALID_PLAN_ACTION')
    require(not document.get('errored') and document.get('complete', True), 'INCOMPLETE_PLAN')
    require(not document.get('deferred_changes') and not document.get('resource_drift'), 'DRIFT_OR_DEFERRED')
    expected = {f'{kind}.{name}' for kind, items in root['resource'].items() for name in items}
    changes = document.get('resource_changes', [])
    require(len(changes) == len(expected) and {c['address'] for c in changes} == expected, 'PLAN_INVENTORY_CHANGED')
    for c in changes:
        require(c.get('mode', 'managed') == 'managed' and c['change']['actions'] == [action], 'PLAN_ACTION_CHANGED')
        if action == 'create':
            wanted = root['resource'][c['type']][c['name']]
            after = c['change'].get('after') or {}
            for field in ('instance_type', 'associate_public_ip_address', 'iam_instance_profile', 'user_data_replace_on_change', 'ingress', 'cidr_block', 'map_public_ip_on_launch', 'tags'):
                if field in wanted:
                    require(after.get(field) == wanted[field], 'PLAN_CONFIGURATION_CHANGED')
            if 'egress' in wanted:
                normalized = []
                for rule in after.get('egress', []):
                    require(all(value in (None, '', False, []) for key, value in rule.items() if key not in wanted['egress'][0]), 'PLAN_EXTRA_EGRESS')
                    normalized.append({key: rule.get(key) for key in wanted['egress'][0]})
                require(sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True)) == sorted(wanted['egress'], key=lambda x: json.dumps(x, sort_keys=True)), 'PLAN_CONFIGURATION_CHANGED')
            if c['type'] == 'aws_instance':
                for field in ('root_block_device', 'metadata_options', 'credit_specification'):
                    require(len(after.get(field, [])) == 1, 'PLAN_HOST_CONTROL_MISSING')
                    for key, value in wanted[field][0].items():
                        if field == 'root_block_device' and key == 'tags':
                            continue  # Concrete override sends these tags in RunInstances.
                        require(after[field][0].get(key) == value, 'PLAN_HOST_CONTROL_CHANGED')
                expected_tags = wanted.get('volume_tags', wanted['root_block_device'][0].get('tags'))
                require(isinstance(expected_tags, dict) and after.get('volume_tags') == expected_tags,
                        'PLAN_HOST_CONTROL_CHANGED')
                # The provider can encode an unconfigured optional map as absent/null/{}.
                # Nonempty nested tags would require forbidden post-launch retagging.
                require(after['root_block_device'][0].get('tags') in (None, {}), 'PLAN_HOST_CONTROL_CHANGED')
    return {'Status': 'STRUCTURAL_PLAN_REVIEW_ONLY', 'Action': action, 'Objects': len(expected), 'LiveAuthorizationProven': False, 'AllowsCreation': False}


def retirement_policy(state, name):
    """Bind exact observed IDs; freshness/ownership must still be checked live."""
    trial(name)
    ids = {}
    for r in state.get('resources', []):
        if r.get('mode') != 'managed':
            continue
        for i in r.get('instances', []):
            require(not i.get('deposed'), 'DEPOSED_REQUIRES_REVIEW')
            a = i['attributes']
            if r['type'] in ('aws_route', 'aws_route_table_association'):
                continue
            require(a.get('tags', {}).get('Trial') == name, 'FOREIGN_RESOURCE')
            resource_ids = ids.setdefault(r['type'], [])
            require(a['id'] not in resource_ids, 'DUPLICATE_RESOURCE_ID')
            resource_ids.append(a['id'])
    expected = {'aws_vpc': 1, 'aws_internet_gateway': 1, 'aws_subnet': 3, 'aws_route_table': 3, 'aws_eip': 1, 'aws_nat_gateway': 1, 'aws_security_group': 1, 'aws_vpc_endpoint': 1, 'aws_instance': 2}
    require({k: len(v) for k, v in ids.items()} == expected, 'INCOMPLETE_RUNTIME_INVENTORY')
    names = {'aws_vpc': ('vpc', 'vpc-'), 'aws_internet_gateway': ('internet-gateway', 'igw-'), 'aws_subnet': ('subnet', 'subnet-'), 'aws_route_table': ('route-table', 'rtb-'), 'aws_eip': ('elastic-ip', 'eipalloc-'), 'aws_nat_gateway': ('natgateway', 'nat-'), 'aws_security_group': ('security-group', 'sg-'), 'aws_vpc_endpoint': ('vpc-endpoint', 'vpce-'), 'aws_instance': ('instance', 'i-')}

    def arns(*types):
        result = []
        for kind in types:
            for value in ids[kind]:
                resource, prefix = names[kind]
                require(re.fullmatch(re.escape(prefix) + '[0-9a-f]{8,17}', value), 'INVALID_RESOURCE_ID')
                result.append(f'arn:aws:ec2:{REGION}:{ACCOUNT}:{resource}/{value}')
        return sorted(result)

    pairs = [('TerminateInstances', ('aws_instance',)), ('DeleteNatGateway', ('aws_nat_gateway',)), ('ReleaseAddress', ('aws_eip',)), ('DeleteVpcEndpoints', ('aws_vpc_endpoint',)), ('DeleteSecurityGroup', ('aws_security_group',)), ('DeleteRoute', ('aws_route_table',)), ('DisassociateRouteTable', ('aws_route_table', 'aws_subnet')), ('DetachInternetGateway', ('aws_internet_gateway', 'aws_vpc')), ('DeleteInternetGateway', ('aws_internet_gateway',)), ('DeleteSubnet', ('aws_subnet',)), ('DeleteRouteTable', ('aws_route_table',)), ('DeleteVpc', ('aws_vpc',))]
    return {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Action': 'ec2:' + a, 'Resource': arns(*k), 'Condition': {'StringEquals': {'aws:RequestedRegion': REGION}}} for a, k in pairs]}


def timeline(start):
    value = dt.datetime.fromisoformat(start.replace('Z', '+00:00'))
    require(value.tzinfo is not None, 'UTC_OFFSET_REQUIRED')
    return {'FirstBillableConservativeUtc': value.isoformat(), 'RetireNoLaterThanUtc': (value + dt.timedelta(minutes=150)).isoformat(), 'AbsoluteDeadlineUtc': (value + dt.timedelta(hours=4)).isoformat(), 'BudgetProposalUsd': 2, 'AutomaticShutdown': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['render', 'review-create', 'review-delete', 'bind-retirement', 'timeline', 'publisher'])
    p.add_argument('--trial', required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--input', type=Path)
    p.add_argument('--first-billable-utc')
    p.add_argument('--sha256')
    a = p.parse_args()
    root, security = render(a.trial, Path(__file__).with_name('bootstrap.sh').read_text())
    if a.action == 'render':
        require(a.output is not None and not a.output.exists(), 'NEW_OUTPUT_DIRECTORY_REQUIRED')
        a.output.mkdir(parents=True)
        files = {'main.tf.json': root, 'security-additions.json': security, 'backend-access.review.json': backend_policy(a.trial)}
        for key, value in files.items():
            (a.output / key).write_bytes(encoded(value))
        lock = Path(__file__).with_name('provider.lock.hcl').read_bytes()
        require(hashlib.sha256(lock).hexdigest() == '901a282544168f6b5d1567b13c91e9009129a2bc0cc92bf4c934e140efdae904', 'REVIEWED_PROVIDER_LOCK_REQUIRED')
        (a.output / '.terraform.lock.hcl').write_bytes(lock)
        (a.output / 'backend.hcl').write_text(f'bucket = "{BACKEND}"\nkey = "e1/lifecycle/dev/recovery/{a.trial}/terraform.tfstate"\nworkspace_key_prefix = "e1/lifecycle/dev/recovery/{a.trial}/workspaces"\nregion = "{REGION}"\nprofile = "cnp-cert-dev"\nencrypt = true\nuse_lockfile = true\n')
        result = {'Status': 'OFFLINE_PACKET', 'AllowsCreation': False, 'Files': {k: hashlib.sha256(encoded(v)).hexdigest() for k, v in files.items()}}
    elif a.action == 'timeline':
        result = timeline(a.first_billable_utc)
    elif a.action == 'publisher':
        result = publisher_policy(a.trial, a.sha256)
    else:
        value = json.loads(a.input.read_text())
        result = retirement_policy(value, a.trial) if a.action == 'bind-retirement' else review_plan(value, root, a.action.split('-')[1])
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as e:
        print(json.dumps({'Status': 'REFUSED', 'Code': str(e) if type(e) is ValueError else type(e).__name__}))
        raise SystemExit(1)
