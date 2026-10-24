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


def retirement_policy(state, name, cold=False):
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
    if cold:
        expected.update(aws_subnet=2, aws_route_table=2, aws_instance=1)
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


def cold_target(name, ami, az):
    """Reduce the existing az6 template to one fresh host/one private subnet."""
    root, _ = render(name, Path(__file__).with_name('bootstrap.sh').read_text(encoding='utf-8'))
    resources = root['resource']
    for kind in ('aws_subnet', 'aws_route_table', 'aws_route_table_association', 'aws_route', 'aws_instance'):
        del resources[kind]['b']
    resources['aws_vpc_endpoint']['s3']['route_table_ids'] = ['${aws_route_table.a.id}']
    instance = resources['aws_instance']['a']
    instance['ami'] = ami
    instance['depends_on'] = [r for r in instance['depends_on']
                              if r not in ('aws_route.b', 'aws_route_table_association.b')]
    root['output'] = {'target': {'value': '${aws_instance.a.id}'}}
    root['variable'] = {'az_a': {'type': 'string', 'default': az,
                               'validation': [{'condition': '${var.az_a == "' + az + '"}',
                                               'error_message': 'Use the bound target AZ.'}]}}
    return root


def cold_path(request, evidence=None):
    """Offline review only: supplied metadata is not authenticated AWS evidence."""
    # Python -I removes the script directory. Resolve only our reviewed sibling modules.
    import sys
    module_dir = str(Path(__file__).resolve().parent)
    original_path = sys.path[:]
    try:
        sys.path.insert(0, module_dir)
        from host import timestamp, event_order, bind_identity
    finally:
        sys.path[:] = original_path
    name = trial(request['Trial'])
    source = request['SourceRecord']
    origin = source['Source']
    bind_identity(origin, origin['instanceId'], origin['availabilityZone'])
    require(source['Status'] == 'SOURCE_BACKED_UP', 'VERIFIED_SOURCE_REQUIRED')
    mode, az = request['Mode'], request['TargetAz']
    require(mode in ('SAME_AZ', 'CROSS_AZ'), 'INVALID_RECOVERY_MODE')
    require(isinstance(az, str) and re.fullmatch('us-east-1[a-f]', az), 'EXPECTED_AZ_REQUIRED')
    require((az == origin['availabilityZone']) == (mode == 'SAME_AZ'), 'MODE_AZ_MISMATCH')
    receipt, manifest = source['Receipt'], source['Receipt']['Manifest']
    require(receipt['ManifestKey'].startswith(BASE + '/' + trial(source['Trial']) + '/runs/')
            and receipt['ManifestKey'].endswith('/manifest.json'), 'MANIFEST_OUTSIDE_SOURCE_SCOPE')
    require(all(isinstance(v, str) and v and v != 'null' for v in
                (receipt['ManifestVersion'], manifest['BackupVersion'])), 'BACKUP_VERSION_MISSING')
    require(manifest['NativeChecksumVerified'] is True, 'BACKUP_NOT_VERIFIED')
    start, now = request['RecoveryRequestedUtc'], request['NowUtc']
    require(event_order(manifest['StartedUtc'], manifest['CompletedUtc'], start, now), 'INVALID_EVENT_ORDER')
    age = (timestamp(start) - timestamp(manifest['CompletedUtc'])).total_seconds()
    maximum = request['MaxBackupAgeSeconds']
    require(type(maximum) is int and 0 < maximum <= 604800 and age <= maximum, 'BACKUP_TOO_OLD_OR_INVALID_BOUND')
    require(re.fullmatch('[0-9a-f]{64}', request['ArtifactSha256']) is not None, 'ARTIFACT_HASH_REQUIRED')
    require(re.fullmatch('ami-[0-9a-f]{17}', request['SqlAmiId']) is not None
            and request['SqlAmiId'] != 'ami-00000000000000000', 'REVIEWED_AMI_REQUIRED')
    # Bind every parameter and the complete selected source receipt, not a caller label.
    binding = hashlib.sha256(encoded(request)).hexdigest()
    result = {'Status': 'COLD_PATH_OFFLINE_PLAN', 'Trial': name, 'Mode': mode, 'TargetAz': az,
              'RequestSha256': binding, 'AllowsCreation': False, 'AllowsActivation': False,
              'EvidenceAuthenticated': False, 'RecoveryRequestedUtc': start,
              'TargetCountToCreate': 1, 'PreparedTargetAllowed': False,
              'TerraformProposal': cold_target(name, request['SqlAmiId'], az),
              'ManifestKey': receipt['ManifestKey'], 'ManifestVersion': receipt['ManifestVersion'],
              'BackupAgeSecondsAtRequest': age,
              'Steps': ['validate-versioned-backup-and-artifact', 'fence-exact-source-incarnation',
                        'create-one-fresh-target', 'bootstrap-and-restore-with-existing-helper',
                        'CHECKDB-and-decrypt-read-write', 'refresh-ECS-connections-and-probe-deployed-API',
                        'record-total-time', 'owner-live-review-window', 'retire-and-reverse-access'],
              'RequiredFence': 'TERMINATED_SOURCE_AND_POST_FENCE_WRITE_UNAVAILABLE',
              'Limits': ['No cloud executor or role assumption',
                         'A stopped SQL service or unreachable AZ is insufficient',
                         'A JSON receipt cannot prove its own authenticity',
                         'No prepared-target RTO may be reported as cold recovery']}
    if evidence is None:
        return result
    require(evidence['RequestSha256'] == binding, 'REQUEST_BINDING_MISMATCH')
    fence, target, checks = evidence['Fence'], evidence['Target'], evidence['Checks']
    require(fence['Source'] == origin and fence['State'] == 'terminated', 'SOURCE_TERMINATION_REQUIRED')
    require(fence['WriteProbe'] == 'ENDPOINT_UNAVAILABLE' and fence['ExistingConnectionsClosed'] is True,
            'NO_WRITES_NOT_DEMONSTRATED')
    require(re.fullmatch('[0-9a-f]{64}', fence['ControlPlaneReceiptSha256']) is not None,
            'CONTROL_PLANE_RECEIPT_REQUIRED')
    bind_identity(target['Identity'], target['Identity']['instanceId'], az)
    require(target['Identity']['instanceId'] != origin['instanceId'], 'FRESH_TARGET_REQUIRED')
    require(target['ArtifactSha256'] == request['ArtifactSha256'], 'ARTIFACT_HASH_MISMATCH')
    require(evidence['ManifestVersion'] == receipt['ManifestVersion']
            and evidence['BackupVersion'] == manifest['BackupVersion'], 'RESTORE_VERSION_MISMATCH')
    require(all(checks.get(k) is True for k in ('Checkdb', 'DecryptedPreMarker', 'Read', 'Write',
            'EcsConnectionsRenewed', 'DeployedApiReady')), 'END_TO_END_CHECKS_REQUIRED')
    ready = evidence['ApiReadyUtc']
    require(event_order(start, fence['ConfirmedUtc'], fence['WriteProbeUtc'], target['CreatedUtc'],
                        evidence['RestoreStartedUtc'], evidence['RestoreVerifiedUtc'], ready, fence['ObservedUtc'], now),
            'COLD_EVENT_ORDER_REQUIRED')
    # Source evidence must remain fresh at the decision, not merely at plan time.
    require((timestamp(now) - timestamp(fence['ObservedUtc'])).total_seconds() <= 900,
            'FENCE_EVIDENCE_TOO_OLD')
    result.update(Status='COLD_PATH_REVIEW_CONSISTENT',
                  RtoTotalSeconds=(timestamp(ready) - timestamp(start)).total_seconds(),
                  RpoQualification='Not measured by metadata admission; retain controlled marker evidence.')
    return result


def service_plan(value):
    """Offline consistency only; never acquires E2, changes a secret or switches traffic."""
    import ipaddress
    import sys
    original_path = sys.path[:]
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scripts.workflow_requests.contract import request as workflow_request
        from scripts.normal_delivery.authorization import connection_secret_arn
        from host import timestamp, event_order
    finally:
        sys.path[:] = original_path
    require(set(value) == {'Trial', 'ColdReceipt', 'Network', 'Connection', 'Release', 'Delivery',
                           'PublicApiId', 'PublicUrl', 'ReviewedUtc', 'RecoveryRequestedUtc'}, 'SERVICE_PLAN_SHAPE')
    name = trial(value['Trial'])
    receipt, net, conn, release, delivery = (value[k] for k in ('ColdReceipt','Network','Connection','Release','Delivery'))
    require(receipt['Trial'] == name and receipt['Status'] == 'TARGET_RECOVERED_REVIEW_EVIDENCE'
            and receipt['Checkdb'] == 'RESTORED_CHECKDB_READABLE', 'COLD_RESTORE_REQUIRED')
    fence = receipt['ColdFence']
    require(fence and fence['Status'] == 'EXACT_SOURCE_TERMINATED'
            and fence['Source'] == receipt['Source'] and fence['Target'] == receipt['Target']
            and receipt['Source']['instanceId'] != receipt['Target']['instanceId'], 'SOURCE_FENCE_REQUIRED')
    require(re.fullmatch('[a-f0-9]{64}', fence['ControlPlaneSha256']) is not None, 'FENCE_RECEIPT_REQUIRED')
    require(all(i['accountId'] == ACCOUNT and i['region'] == REGION
                and re.fullmatch('i-[0-9a-f]{17}',i['instanceId']) for i in (receipt['Source'],receipt['Target'])),
            'WRONG_ACCOUNT_REGION_OR_HOST')
    require(event_order(value['RecoveryRequestedUtc'], fence['TargetLaunchUtc'],
                        receipt['ReadyAndDecryptedMarkersConfirmedUtc'], fence['ObservedUtc'], value['ReviewedUtc'])
            and (timestamp(value['ReviewedUtc'])-timestamp(fence['ObservedUtc'])).total_seconds() <= 900,
            'STALE_OR_PREPARED_TARGET')
    require(set(net) == {'AppVpcId','DbVpcId','DbInstanceId','DbPrivateIp','DbSubnetCidr','DbSgId',
                         'TaskSgId','DbIngress','SqlBoundAddresses','HasPublicIpv4'}, 'NETWORK_METADATA_ONLY')
    require(net['AppVpcId'] == net['DbVpcId'] and re.fullmatch('vpc-[0-9a-f]{17}', net['AppVpcId']), 'APP_VPC_REQUIRED')
    require(net['DbInstanceId'] == receipt['Target']['instanceId'], 'WRONG_SQL_ENDPOINT_INSTANCE')
    ip = ipaddress.ip_address(net['DbPrivateIp'])
    subnet = ipaddress.ip_network(net['DbSubnetCidr'])
    private_ranges = [ipaddress.ip_network(c) for c in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    require(ip.version == subnet.version == 4 and ip in subnet
            and ip not in (subnet.network_address,subnet.broadcast_address)
            and any(subnet.subnet_of(r) for r in private_ranges), 'PRIVATE_BOUND_ENDPOINT_REQUIRED')
    require(net['SqlBoundAddresses'] == [str(ip)] and net['HasPublicIpv4'] is False, 'APPLICATION_LISTENER_MODE_REQUIRED')
    for key in ('DbSgId','TaskSgId'):
        require(re.fullmatch('sg-[0-9a-f]{17}', net[key]) is not None, 'OWN_SECURITY_GROUP_REQUIRED')
    require(net['DbSgId'] != net['TaskSgId'] and net['DbIngress'] ==
            [{'Protocol':'tcp','FromPort':1433,'ToPort':1433,'SourceSecurityGroupId':net['TaskSgId']}],
            'ONLY_TASK_SG_SQL_INGRESS')
    require(set(conn) == {'SecretArn','VersionId','Endpoint','Database','TextKeyArn','BackupKeyArn','SecretKeyArn'}, 'NO_SECRET_VALUES_ALLOWED')
    require(conn['Endpoint'] == str(ip) and conn['Database'] == 'recoverydb_restore_' + name, 'CONNECTION_TARGET_MISMATCH')
    try: connection_secret_arn(conn['SecretArn'], 'dev', ACCOUNT, REGION)
    except ValueError: raise ValueError('PROTECTED_CONNECTION_SECRET_REQUIRED') from None
    require(re.fullmatch('[A-Za-z0-9-]{32,64}',conn['VersionId']) is not None, 'IMMUTABLE_SECRET_VERSION_REQUIRED')
    require(conn['TextKeyArn'] == TEXT_KEY and conn['BackupKeyArn'] == BACKUP_KEY
            and conn['SecretKeyArn'] == TEXT_KEY, 'KEY_PURPOSE_MISMATCH')
    require(set(release) == {'release_id','image_uri','schema_sha256','restored_schema_sha256',
                             'rollback_history','rollback_schema_sha256'}, 'RELEASE_SHAPE')
    require(re.fullmatch('[a-f0-9]{64}',release['restored_schema_sha256']) is not None
            and release['schema_sha256'] == release['restored_schema_sha256'] == release['rollback_schema_sha256'],
            'SCHEMA_OR_ROLLBACK_INCOMPATIBLE')
    image = re.fullmatch(re.escape(f'{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/')+
                         r'[a-z0-9][a-z0-9._/-]*@sha256:([a-f0-9]{64})',release['image_uri'])
    require(image is not None and release['release_id'] == 'sha256-' + image[1], 'QUALIFIED_DIGEST_BINDING_REQUIRED')
    require(set(delivery) == {'operation_id','rollback_operation_id','active_color','candidate_color','replicas',
                              'listener_arn','rule_arn','active_target_arn','candidate_target_arn'}, 'DELIVERY_SHAPE')
    require(delivery['candidate_color'] in ('blue','green') and delivery['active_color'] in ('blue','green')
            and delivery['candidate_color'] != delivery['active_color'] and type(delivery['replicas']) is int
            and delivery['replicas'] in (1,2), 'BOUNDED_DISTINCT_CANDIDATE_REQUIRED')
    for key, kind in [('listener_arn','listener'),('rule_arn','listener-rule')]:
        require(re.fullmatch(re.escape(f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:{kind}/app/demo-dev-internal-alb/')+
                             r'[A-Za-z0-9/]+',delivery[key]) is not None, 'OWN_ROUTING_REQUIRED')
    for prefix,color in [('active',delivery['active_color']),('candidate',delivery['candidate_color'])]:
        require(re.fullmatch(re.escape(f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:targetgroup/demo-dev-{color}/')+
                             '[a-z0-9]+',delivery[prefix+'_target_arn']) is not None, 'OWN_TARGET_GROUP_REQUIRED')
    require(re.fullmatch('[a-z0-9]{10}',value['PublicApiId']) is not None and value['PublicUrl'] ==
            f'https://{value["PublicApiId"]}.execute-api.{REGION}.amazonaws.com', 'OWN_PUBLIC_API_REQUIRED')
    require(len({delivery['operation_id'],delivery['rollback_operation_id'],release['rollback_history']}) == 3,
            'DISTINCT_DURABLE_OPERATIONS_REQUIRED')
    payload = {'action':'deliver','release_id':release['release_id'],'replicas':delivery['replicas']}
    rollback = {'action':'rollback-release','history':release['rollback_history'],'replicas':delivery['replicas']}
    # Use the actual closed gateway validator; no new endpoint/secret override fields.
    normal_request = workflow_request('deploy-dev',json.dumps(payload),delivery['operation_id'])
    rollback_request = workflow_request('deploy-dev',json.dumps(rollback),delivery['rollback_operation_id'])
    color = delivery['candidate_color']
    return {'Status':'SERVICE_CUTOVER_DRY_PLAN','Trial':name,'AllowsActivation':False,'AwsExecuted':False,
            'EvidenceAuthenticated':False,'FullEcsRecoveryProven':False,
            'InputSha256':hashlib.sha256(encoded(value)).hexdigest(),
            'ConnectionMetadata':{'Endpoint':str(ip),'Port':1433,'Database':conn['Database'],
                                  'SecretReference':conn['SecretArn']+':::'+conn['VersionId'],
                                  'PlaintextConnectionStringIncluded':False},
            'RendererArguments':['bash','scripts/render-demo-api-taskdef.sh','--env','dev','--region',REGION,
                '--account-id',ACCOUNT,'--color',color,'--image-uri',release['image_uri'],'--db-secret-id',
                conn['SecretArn']+':::'+conn['VersionId'],'--kms-key-id',TEXT_KEY,'--recovery','--output','candidate-taskdef.review.json'],
            'GatewayRequest':normal_request,'RollbackRequest':rollback_request,
            'ProposedTaskEnvironmentAppend':[{'name':'Database__RunMigrationsOnStartup','value':'false'}],
            'TaskTemplateAutomaticallyChanged':False,'RecoveryProfileEnforcedByRenderer':True,
            'RequiredTaskRoles':{'Execution':f'arn:aws:iam::{ACCOUNT}:role/demo-dev-app-api-{color}-exec-role',
                                 'Task':f'arn:aws:iam::{ACCOUNT}:role/demo-dev-app-api-{color}-task-role'},
            'IamReviewOnly':{'ExecutionRole':['GetSecretValue exact connection ARN/version','Decrypt connection-secret key '+conn['SecretKeyArn']],
                             'TaskRole':['Encrypt/Decrypt application-text key '+TEXT_KEY],
                             'SqlRole':['Read selected backup S3 version and decrypt backup key '+BACKUP_KEY]},
            'Steps':['verify-native-fence-and-network-listener','read-durable-operation-history-stop-if-uncertain','acquire-existing-E2-owner',
                     'create-connection-secret-version-outside-Terraform-and-pin-installed-binding',
                     'deliver-qualified-release-through-existing-WP4-new-tasks',
                     'run-existing-task-local-readiness-and-E3-final-revalidation',
                     'WP4-controlled-routing-switch','public-ready-decrypt-old-marker-write-read',
                     'mark-service-ready-and-measure-total-RTO','owner-LIVE-window','retire-owned-runtime'],
            'RollbackRule':'Only schema-compatible image against the SAME restored endpoint/version; never old terminated SQL.',
            'PublicChecks':{'BaseUrl':value['PublicUrl'],'BeforeMarkingReady':True,'BeforeTrafficSwitch':False,
                            'Requests':[{'Method':'GET','Path':'/ready','Expectation':'Healthy SQL/KMS dependencies'},
                                        {'Method':'GET','Path':'/text?page=1&pageSize=100','Expectation':'Verified restored marker decrypted'},
                                        {'Method':'POST','Path':'/text','Expectation':'One new unique synthetic marker returned'},
                                        {'Method':'GET','Path':'/text?page=1&pageSize=100','Expectation':'Same new marker ID and plaintext read back'}],
                            'MarkerBindings':'Require verified restore receipt and fresh POST result; do not infer from HTTP 200',
                            'Required':['/ready dependency check','decrypt recovered marker','fresh POST /text','read same marker']},
            'BlockingLiveGates':['Supplied metadata is not native proof or an acquired E2 token',
                'Current recovery verifier/bootstrap is loopback-only: private-listener mode needs review/qualification',
                'Current WP4 caller cannot override a secret: protected installed binding must pin the reviewed version',
                'Verify Fargate Linux platform >=1.4.0 for secret version selection',
                'Protected installed WP4 binding must select the recovery profile with startup migrations disabled; renderer alone does not change it',
                'Schema compatibility must come from protected qualified release and restore facts, not caller assertions',
                'Existing E3 plus public API checks and same-VPC routes/NACLs need native receipts',
                'SSM transport, full resource plan/IAM/budget not approved here']}




def application_listener_plan(value):
    """Explicit post-restore listener transition plan; no setting/service executor."""
    service = service_plan(value)
    return {'Status':'APPLICATION_LISTENER_PLAN_ONLY','Trial':value['Trial'],
            'ServiceInputSha256':service['InputSha256'], 'Network':value['Network'],
            'Source':value['ColdReceipt']['Source'],'Target':value['ColdReceipt']['Target'],
            'DefaultUnchanged':'127.0.0.1','ProposedEndpoint':value['Network']['DbPrivateIp'],
            'ReviewedHostSteps':[['systemctl','stop','mssql-server'],
                ['/opt/mssql/bin/mssql-conf','set','network.ipaddress',value['Network']['DbPrivateIp']],
                ['systemctl','start','mssql-server']],
            'BeforeAnyHostChange':['Reconfirm exact source terminated and target incarnation; no uncertain fencing',
                                  'Verify exact native VPC/SG ingress and private-only node',
                                  'Separate future approval of host changes and complete lifecycle required'],
            'AfterHostChange':'host.py listener-check with this service input; then protected config and new Fargate tasks',
            'AllowsHostChanges':False,'AllowsActivation':False,'EvidenceAuthenticated':False,'AwsExecuted':False}


def service_taskdef(value, candidate):
    """Check the complete rendered projection; never emits or registers a task."""
    plan = service_plan(value)
    template_path = Path(__file__).resolve().parents[3] / 'demo-api/deploy/task-definition.template.json'
    expected = json.loads(template_path.read_text(encoding='utf-8'))
    color = value['Delivery']['candidate_color']
    family = 'demo-dev-app-api-' + color
    expected.update(family=family, executionRoleArn=plan['RequiredTaskRoles']['Execution'],
                    taskRoleArn=plan['RequiredTaskRoles']['Task'])
    env = {'AWS_REGION':REGION, 'APP_ENV':'dev', 'DEPLOYMENT':color, 'KMS_KEY_ID':TEXT_KEY}
    for i, container in enumerate(expected['containerDefinitions']):
        name = family + ('-readiness-probe' if i else '')
        container.update(name=name, image=value['Release']['image_uri'])
        container['logConfiguration']['options'].update({
            'awslogs-group':'/aws/ecs/' + family, 'awslogs-region':REGION,
            'awslogs-stream-prefix':name})
    app = expected['containerDefinitions'][0]
    for row in app['environment']:
        row['value'] = env[row['name']]
    app['environment'] = [row for row in app['environment'] if row['name'] != 'Database__RunMigrationsOnStartup']
    app['environment'].append({'name':'Database__RunMigrationsOnStartup','value':'false'})
    app['secrets'][0]['valueFrom'] = plan['ConnectionMetadata']['SecretReference']
    require(candidate == expected, 'RECOVERY_TASKDEF_NOT_EXACT_REVIEWED_PROJECTION')
    return {'Status':'OFFLINE_RECOVERY_TASKDEF_REVIEW_PASS','Trial':value['Trial'],
            'TaskDefinitionSha256':hashlib.sha256(encoded(candidate)).hexdigest(),
            'TemplateLfSha256':hashlib.sha256(template_path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
            'ServiceInputSha256':plan['InputSha256'],'RequiresNewTasks':True,
            'RequiredLinuxFargatePlatform':'>=1.4.0; native installed platform still unverified',
            'StartupMigrations':False,'AllowsActivation':False,'EvidenceAuthenticated':False,
            'AwsExecuted':False,'PublicApiRecoveryProven':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['render', 'review-create', 'review-delete', 'bind-retirement', 'timeline', 'publisher', 'cold-plan', 'cold-review', 'bind-cold-retirement', 'service-plan', 'service-taskdef', 'listener-plan'])
    p.add_argument('--trial', required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--input', type=Path)
    p.add_argument('--first-billable-utc')
    p.add_argument('--sha256')
    p.add_argument('--evidence', type=Path)
    a = p.parse_args()
    if a.action in ('service-plan','service-taskdef','listener-plan'):
        value = json.loads(a.input.read_text(encoding='utf-8'))
        require(value['Trial'] == a.trial, 'WRONG_TRIAL')
        require(a.action != 'service-taskdef' or a.evidence is not None, 'RENDERED_TASKDEF_REQUIRED')
        result = application_listener_plan(value) if a.action == 'listener-plan' else service_plan(value) if a.action == 'service-plan' else service_taskdef(value, json.loads(a.evidence.read_text(encoding='utf-8')))
        print(json.dumps(result, indent=2))
        return
    if a.action == 'bind-cold-retirement':
        print(json.dumps(retirement_policy(json.loads(a.input.read_text(encoding='utf-8')), a.trial, cold=True), indent=2))
        return
    if a.action in ('cold-plan', 'cold-review'):
        request = json.loads(a.input.read_text(encoding='utf-8'))
        require(request['Trial'] == a.trial, 'WRONG_TRIAL')
        evidence = json.loads(a.evidence.read_text(encoding='utf-8')) if a.action == 'cold-review' else None
        print(json.dumps(cold_path(request, evidence), indent=2))
        return
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
