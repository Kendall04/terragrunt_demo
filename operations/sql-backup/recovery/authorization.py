#!/usr/bin/env python3
"""Prepare the finite trial's public IAM/config packet OFFLINE; never install it.

This validates edits and documents ownership. It is not an IAM evaluator, gate,
credential provider, cloud executor or proof that a later request will succeed.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import prepare as p

TRIAL = 'r20261021az1'
AMI = 'ami-033ea4ff4a9c726dc'
SHA = 'd745816853bb22a8e5be8df7155d0bdfd367deb31fd3ddeb05ce92eefd3fffa0'
BACKEND_BASELINE = 'c95441da84a0ffc4242308d16d34641299592ef94acdde9ea542130f0c98adc5'
BACKUP_KEY_BASELINE = '4eab460760d5ddde61a0a1879a2639deb434ecb299670363c35538e7fc31e732'
OPERATOR = f'arn:aws:iam::{p.ACCOUNT}:role/TerragruntDemoDevOperator'
HUMAN = f'arn:aws:iam::{p.ACCOUNT}:user/cnp-cert-admin'
EC2 = f'arn:aws:ec2:{p.REGION}:{p.ACCOUNT}:'
TAGS = {'Project': 'terragrunt-demo', 'Purpose': 'v2-recovery', 'Trial': TRIAL}


def digest(value):
    return hashlib.sha256(p.encoded(value)).hexdigest()


def backend_edit(document, restore=False):
    """Add/remove ONLY the selected state and lock exception; fail on ambiguous Sid."""
    result = deepcopy(document)
    matches = [s for s in result['Statement'] if s.get('Sid') == 'E16NoOtherDevObjects']
    p.require(len(matches) == 1, 'BACKEND_SID_NOT_UNIQUE')
    s = matches[0]
    p.require(s['Effect'] == 'Deny' and s['Principal'] == '*' and
              set(s['Action']) == {'s3:GetObject', 's3:PutObject', 's3:DeleteObject'} and
              s['Condition'] == {'ArnEquals': {'aws:PrincipalArn': OPERATOR}}, 'BACKEND_GUARD_CHANGED')
    objects = [f'arn:aws:s3:::{p.BACKEND}/e1/lifecycle/dev/recovery/{TRIAL}/terraform.tfstate' + suffix
               for suffix in ('', '.tflock')]
    existing = s['NotResource']
    expected = [f'arn:aws:s3:::{p.BACKEND}/e1/lifecycle/dev/{layer}/terraform.tfstate' + suffix
                for layer in ('global', 'data', 'platform', 'apps', 'edge') for suffix in ('', '.tflock')]
    p.require(len(existing) == len(set(existing)) and
              set(existing) == set(expected + (objects if restore else [])), 'BACKEND_EXCEPTION_CHANGED')
    s['NotResource'] = [a for a in existing if a not in objects] if restore else existing + objects
    return result


def operator_policy():
    statements = []

    def add(sid, actions, classes=None, condition=None, resources=None):
        c = {'StringEquals': {'aws:RequestedRegion': p.REGION}}
        for op, values in (condition or {}).items():
            c.setdefault(op, {}).update(values)
        statements.append({'Sid': sid, 'Effect': 'Allow', 'Action': actions,
                           'Resource': resources if resources is not None else [EC2 + k + '/*' for k in classes],
                           'Condition': c})

    request = {'StringEquals': {'aws:RequestTag/' + k: v for k, v in TAGS.items()},
               'ForAllValues:StringEquals': {'aws:TagKeys': list(TAGS)}}
    existing = {'StringEquals': {'aws:ResourceTag/' + k: v for k, v in TAGS.items()}}
    creates = {'CreateVpc': 'vpc', 'CreateInternetGateway': 'internet-gateway', 'CreateSubnet': 'subnet',
               'CreateRouteTable': 'route-table', 'AllocateAddress': 'elastic-ip',
               'CreateSecurityGroup': 'security-group', 'CreateNatGateway': 'natgateway', 'CreateVpcEndpoint': 'vpc-endpoint'}
    for action, kind in creates.items():
        c = deepcopy(request)
        if action == 'CreateVpcEndpoint':
            c['StringEquals']['ec2:VpceServiceName'] = f'com.amazonaws.{p.REGION}.s3'
        add(action, ['ec2:' + action], [kind], c)
    for action, kinds in {
        'CreateSubnet': ['vpc'], 'CreateRouteTable': ['vpc'], 'CreateSecurityGroup': ['vpc'],
        'CreateNatGateway': ['vpc', 'subnet', 'elastic-ip'],
        'CreateVpcEndpoint': ['vpc', 'route-table'],
        'AttachInternetGateway': ['vpc', 'internet-gateway'],
        'AssociateRouteTable': ['route-table', 'subnet'],
        'CreateRoute': ['route-table'], 'DeleteRoute': ['route-table'],
        'DisassociateRouteTable': ['route-table', 'subnet'],
        'DetachInternetGateway': ['internet-gateway', 'vpc'],
        'DeleteVpc': ['vpc'], 'DeleteSubnet': ['subnet'], 'DeleteRouteTable': ['route-table'],
        'DeleteInternetGateway': ['internet-gateway'], 'ReleaseAddress': ['elastic-ip'],
        'DeleteNatGateway': ['natgateway'], 'DeleteVpcEndpoints': ['vpc-endpoint'],
        'DeleteSecurityGroup': ['security-group'], 'TerminateInstances': ['instance'],
    }.items():
        add(action + 'Owned', ['ec2:' + action], kinds, existing)
    add('HostEgress', ['ec2:AuthorizeSecurityGroupEgress', 'ec2:RevokeSecurityGroupEgress'], ['security-group'], existing)
    dns = deepcopy(existing)
    dns['StringEquals']['ec2:Attribute'] = ['enableDnsSupport', 'enableDnsHostnames']
    add('VpcDns', ['ec2:ModifyVpcAttribute'], ['vpc'], dns)
    launch = deepcopy(request)
    launch['ForAllValues:StringEquals']['aws:TagKeys'].append('Name')
    launch['StringEquals'].update({'ec2:InstanceType': 't3.medium', 'ec2:MetadataHttpTokens': 'required',
                                  'ec2:InstanceProfile': p.PROFILE, 'ec2:AvailabilityZone': ['us-east-1a', 'us-east-1b']})
    add('LaunchHost', ['ec2:RunInstances'], ['instance'], launch)
    volume = deepcopy(request)
    volume.update({'Bool': {'ec2:Encrypted': 'true'}, 'NumericEquals': {'ec2:VolumeSize': 30}})
    volume['StringEquals'].update({'ec2:VolumeType': 'gp3', 'ec2:AvailabilityZone': ['us-east-1a', 'us-east-1b']})
    add('LaunchRootVolume', ['ec2:RunInstances'], ['volume'], volume)
    add('LaunchAmi', ['ec2:RunInstances'], resources=[f'arn:aws:ec2:{p.REGION}::image/{AMI}'])
    add('LaunchOwnedNetwork', ['ec2:RunInstances'], ['subnet', 'security-group'], existing)
    add('LaunchIncidentalEni', ['ec2:RunInstances'], ['network-interface'],
        {'Bool': {'ec2:AssociatePublicIpAddress': 'false'},
         'StringEquals': {'ec2:AvailabilityZone': ['us-east-1a', 'us-east-1b']}})
    tagging = deepcopy(request)
    tagging['ForAllValues:StringEquals']['aws:TagKeys'].append('Name')
    tagging['StringEquals']['ec2:CreateAction'] = list(creates) + ['RunInstances']
    add('TagOnlyDuringCreation', ['ec2:CreateTags'], list(creates.values()) + ['instance', 'volume'], tagging)
    add('MissingProviderReads', ['ec2:DescribeNatGateways', 'ec2:DescribeVpcEndpoints', 'ec2:DescribePrefixLists'], resources=['*'])
    add('HostCommand', ['ssm:SendCommand'], resources=[f'arn:aws:ec2:{p.REGION}:{p.ACCOUNT}:instance/*'],
        condition={'StringEquals': {'ssm:resourceTag/' + k: v for k, v in TAGS.items()}})
    add('ShellDocument', ['ssm:SendCommand'], resources=[f'arn:aws:ssm:{p.REGION}::document/AWS-RunShellScript'])
    add('CommandReceipts', ['ssm:GetCommandInvocation', 'ssm:ListCommandInvocations', 'ssm:DescribeInstanceInformation'], resources=['*'])
    statements.extend(deepcopy(p.backend_policy(TRIAL)['IdentityPolicyAddition']['Statement']))
    # The same three-tag condition applies to all existing trial dependencies.
    # Consolidate that condition; EC2 still authorizes each action's resource types.
    owned = [s for s in statements if s.get('Sid', '').endswith('Owned') or s.get('Sid') == 'HostEgress']
    combined = deepcopy(owned[0])
    combined['Sid'] = 'OwnedNetworkAndRetirement'
    combined['Action'] = sorted({a for s in owned for a in s['Action']})
    combined['Resource'] = sorted({r for s in owned for r in s['Resource']})
    statements = [s for s in statements if s not in owned] + [combined]
    return {'Version': '2012-10-17', 'Statement': statements}


def configuration():
    assume = {'role_arn': OPERATOR, 'session_name': TRIAL, 'duration': '1h'}
    override = {'provider': {'aws': {'region': p.REGION, 'profile': 'cnp-cert-dev',
                'allowed_account_ids': [p.ACCOUNT], 'assume_role': [assume]}},
                'resource': {'aws_instance': {}}}
    for host in ('a', 'b'):
        override['resource']['aws_instance'][host] = {'volume_tags': TAGS,
            'root_block_device': [{'volume_size': 30, 'volume_type': 'gp3',
                                  'encrypted': True, 'delete_on_termination': True}]}
    return {'provider_override.tf.json': override,
            'backend-config': {'bucket': p.BACKEND, 'key': f'e1/lifecycle/dev/recovery/{TRIAL}/terraform.tfstate',
                'workspace_key_prefix': f'e1/lifecycle/dev/recovery/{TRIAL}/workspaces',
                'region': p.REGION, 'profile': 'cnp-cert-dev', 'encrypt': True, 'use_lockfile': True,
                'allowed_account_ids': [p.ACCOUNT], 'assume_role': assume},
            'terraform.tfvars.json': {'sql_ami_id': AMI, 'az_a': 'us-east-1a', 'az_b': 'us-east-1b'},
            'Workspace': 'default', 'SessionSeconds': 3600, 'CredentialsPersisted': False}


def build(proposal, evidence):
    p.require(proposal['Trial'] == TRIAL and proposal['AMI'] == AMI and proposal['ArtifactSha256'] == SHA,
              'PROPOSAL_BINDING_CHANGED')
    storage = evidence['Queries']['Storage']
    backend = storage['Backend']['get_bucket_policy']['Policy']
    p.require(digest(backend) == BACKEND_BASELINE == proposal['ExactBackendDecision']['ExpectedCanonicalPolicySha256'], 'BACKEND_BASELINE_CHANGED')
    backend_after = backend_edit(backend)
    _, generic = p.render(TRIAL, '')
    runtime = deepcopy(generic['RoleInlineAddition'])
    runtime['Statement'][2]['Action'] = ['kms:Encrypt']  # Existing SQL role already has Decrypt.
    additions = [generic['BackupKeyStatementAddition'], p.publisher_policy(TRIAL, SHA)['BackupKeyStatementAddition']]
    key_before = storage['Keys'][p.BACKUP_KEY]['Policy']['Policy']
    p.require(digest(key_before) == BACKUP_KEY_BASELINE, 'KEY_BASELINE_CHANGED')
    p.require(not {s['Sid'] for s in additions} &
              {s.get('Sid') for s in key_before['Statement']}, 'KEY_SID_ALREADY_EXISTS')
    key_after = deepcopy(key_before)
    key_after['Statement'].extend(additions)
    operator = operator_policy()
    # Role inline quota is shared with other inline policies; preflight observed none.
    p.require(len(json.dumps(operator, separators=(',', ':'))) <= 10240, 'OPERATOR_INLINE_QUOTA')
    result = {'SchemaVersion': 1, 'Status': 'OFFLINE_REVIEW_ONLY', 'AllowsInstallation': False, 'AllowsCreation': False,
              'Trial': TRIAL, 'SourceBaseline': proposal['SourceHead'], 'ArtifactSha256': SHA,
              'SecurityOwner': HUMAN, 'Operator': OPERATOR, 'SqlRole': p.ROLE,
              'Configuration': configuration(),
              'Install': {'OperatorInlineName': 'Recovery' + TRIAL, 'OperatorInlinePolicy': operator,
                  'SqlInlineName': 'Recovery' + TRIAL, 'SqlInlinePolicy': runtime,
                  'BackendBucket': p.BACKEND, 'BackendBefore': backend, 'BackendAfter': backend_after,
                  'BackendBeforeSha256': digest(backend), 'BackendAfterSha256': digest(backend_after),
                  'BackupKey': p.BACKUP_KEY, 'BackupKeyBefore': key_before, 'BackupKeyAfter': key_after,
                  'BackupKeyBeforeSha256': digest(key_before), 'BackupKeyAfterSha256': digest(key_after)},
              'Reverse': {'RemoveInlinePolicies': [{'Role': OPERATOR, 'Name': 'Recovery' + TRIAL},
                                                  {'Role': p.ROLE, 'Name': 'Recovery' + TRIAL}],
                  'BackendExpectedAfterSha256': digest(backend_after), 'BackendRestore': backend,
                  'BackupKeyExpectedAfterSha256': digest(key_after), 'BackupKeyRestore': key_before,
                  'Require': ['dependent host/SSM operations finished', 'normal full-root destroy and incidental absence readbacks',
                              'empty isolated state retained; no native lock; no other writer',
                              'fresh complete policy hashes match before replacement; stop on drift',
                              'read back removed inline policies and restored exact policy hashes']},
              'LifecycleDecision': {
                  'Approved': False, 'FirstBillableUtc': None, 'AbsoluteDeadlineUtc': None,
                  'CapUsdIncrementalProposed': 2, 'EstimatedWithContingencyUsd': 1.20,
                  'BaseComputeDiskNatIpv4FourHoursUsd': 0.5591, 'TtlHoursProposed': 4,
                  'StartWithdrawalMinute': 150, 'ReserveWithdrawalMinutes': 90,
                  'PriceObservationUtc': '2026-10-21', 'RepriceBeforeDispatch': True,
                  'Session': {'Mechanism': 'Existing Terraform backend/provider AWS SDK AssumeRole credential refresh',
                      'Seconds': 3600, 'SourceProfile': 'cnp-cert-dev', 'Role': OPERATOR,
                      'TemporaryCredentialsStorage': 'memory only; never export or persist',
                      'SsmClient': 'same SDK AssumeRole profile provider in memory, source_profile=cnp-cert-dev, duration_seconds=3600',
                      'Failure': 'stop new work if renewal unavailable; no administrator runtime fallback or TTL extension'},
                  'BeforeFirstCost': ['fresh legitimate owner/operator STS, source/session renewal, policy versions and absent inline names',
                      'fresh complete hashes equal Install baselines; read back every installed exact delta',
                      'effective multi-resource IAM/SSM and normal teardown capability review including VPC/subnet companions',
                      'AMI owner/architecture/SSM, distinct AZ IDs, quota/stock, inherited retention, originals/fences unchanged',
                      'default workspace; isolated state and native lock; fresh full-root plan, evaluated bindings and ownership; no targets'],
                  'Cycle': ['conditional SSE-KMS PutObject of exact artifact; bind version and inspect SHA on both hosts',
                      'normal operator locked full-root apply: exactly 20 resources, no original five-root changes',
                      'two hosts SSM Online and SQL ready; bounded AWS-RunShellScript commands, 600-second execution timeout',
                      'EC2 role reads existing two secrets in process only; Express EULA; synthetic source marker and fresh backup',
                      'source quiesce; different AZ/host exact-version restore, hash/checksum/CHECKDB, isolated API decrypt and read/write proof',
                      'record real warm-target RPO/RTO methodology/results; no cold-AZ/full-ECS equivalence',
                      'immediate normal full-root destroy after proof or abort; inspect uncertain effects before retry',
                      'incidental root disks/ENIs/default network objects absent; empty isolated state retained and lock absent',
                      'Reverse exact overlays after dependents idle; verify absence/hashes and retained originals'],
                  'Data': {'Destroy': 'new synthetic host disks, SQL data and host logs only',
                      'Retain': 'new backup/artifact versions under existing asynchronous 2-current + 2-noncurrent-day lifecycle; terminal state/evidence',
                      'NoHistoricalDependency': True, 'NoObjectDeletionOrRetentionMutation': True,
                      'AfterReversal': 'trial crypto grant removed; retained versions need separately authorized access before asynchronous expiry'},
                  'ScopeLimits': 'existing retained baseline/taxes excluded; <=2 GB processing/transfer and existing 301 MB artifact; no automatic cap/shutdown',
                  'OwnerApprovalRequired': ['the two exact temporary inline policies and shared-role effects',
                      'backend two-object Deny exception and two backup-key Sids, including exact reversals',
                      'one-hour normal-operator AssumeRole/renewal, backend/artifact writes and bounded SSM host execution',
                      'EC2-only existing-secret reads, EULA, synthetic data loss, create/test/full withdrawal and inherited S3 expiry',
                      'NEW USD2/four-hour supervised window, withdrawal minute150, no automatic extension'],
                  'PlatformApprovals': 'individual sensitive operations may still require confirmation or be denied; no bypass promised'},
              'PreserveUnchanged': ['backup bucket policy', 'all lifecycle rules', 'text key policy', 'EBS key policy',
                  'original operator and SQL policies/trust/profile', 'original secret values/metadata',
                  'original five states and policies', 'old backups and retained terminal trial state', 'inhibition/workflow settings'],
              'Limits': ['offline structure only, not effective IAM/SCP/resource-policy/SSM proof',
                  'create ARN class patterns required before IDs exist; request tags bind new resources',
                  'existing dependencies and deletion require all three exact trial resource tags',
                  'incidental launch ENI has no tag assertion: same request must also authorize tagged subnet and SG',
                  'regional Describe and SSM receipt reads need Resource:*; use only trial IDs/commands operationally',
                  'IAM does not limit resource count, egress ports, credit mode, SSM shell contents or overall bill; review actual plans/actions',
                  'no new permission for DeleteVolume, DisassociateAddress, ingress, tag mutation, IAM administration or other projects',
                  'inline/key/bucket edits persist until explicit reversal; four-hour TTL is supervised, not enforced by IAM',
                  'only additions are trial-scoped; existing legacy role permissions remain, so plan/procedure must exclude other roots',
                  'remaining unknown provider dependent calls or denials stop the action; no blind retry/admin fallback']}
    return result


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--proposal', required=True, type=Path)
    a.add_argument('--evidence', required=True, type=Path)
    a.add_argument('--output', required=True, type=Path)
    args = a.parse_args()
    packet = build(json.loads(args.proposal.read_text()), json.loads(args.evidence.read_text()))
    args.output.write_bytes(p.encoded(packet))
    print(json.dumps({'Status': packet['Status'], 'AllowsInstallation': False, 'AllowsCreation': False,
                      'PacketSha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))
