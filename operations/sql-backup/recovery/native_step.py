#!/usr/bin/env python3
"""Dispatch one fixed native SQL host step; no provisioning or automatic replay.

Use the existing Data Terraform owner separately. The request contains metadata,
not credentials. Human authorization for interruption is external to this CLI;
the confirmation string is only an operator safeguard, never an approval receipt.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_host import ACCOUNT, REGION, timestamp, validate, require

CLUSTER = 'demo-dev-platform-main-cluster'
SERVICES = ['demo-dev-app-api-blue-svc', 'demo-dev-app-api-green-svc']
PROFILE = f'arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile'
SUBNETS = {'us-east-1a': 'subnet-0cc3c5f388072d13d', 'us-east-1b': 'subnet-00ac2e41219ad7803'}


def instance(ec2, identity):
    groups = ec2.describe_instances(InstanceIds=[identity])['Reservations']
    rows = [x for group in groups for x in group['Instances']]
    require(len(rows) == 1 and rows[0]['InstanceId'] == identity, 'INSTANCE_READBACK')
    return rows[0]


def verify_host(host, request):
    require(host['State']['Name'] == 'running' and
            host['ImageId'] == 'ami-062944a84867f2386' and
            host['InstanceType'] == 't3a.small' and
            host['Placement']['AvailabilityZone'] == request['targetAz'] and
            host['SubnetId'] == SUBNETS[request['targetAz']] and
            host['VpcId'] == 'vpc-00faf317507b09b03' and
            host.get('IamInstanceProfile', {}).get('Arn') == PROFILE and
            host['MetadataOptions']['HttpTokens'] == 'required' and
            not host.get('PublicIpAddress') and
            {x['GroupId'] for x in host['SecurityGroups']} == {'sg-09d69b4eda335675d'},
            'SQL_HOST_CONFIGURATION')
    tags = {x['Key']: x['Value'] for x in host.get('Tags', [])}
    require(tags.get('Project') == 'demo' and tags.get('Environment') == 'dev', 'SQL_HOST_OWNERSHIP')


def source_disk(ec2, source, volume_id, terminated):
    # Before termination the exact root association is checked. After termination
    # the controller still requires the original identity/launch-time and the
    # same separately retained volume, not merely an inaccessible SQL endpoint.
    if not terminated:
        roots = [x['Ebs'] for x in source['BlockDeviceMappings'] if x['DeviceName'] == source['RootDeviceName']]
        require(len(roots) == 1 and roots[0]['VolumeId'] == volume_id and
                roots[0]['DeleteOnTermination'] is False, 'SOURCE_DISK_NOT_RETAINED')
    rows = ec2.describe_volumes(VolumeIds=[volume_id])['Volumes']
    require(len(rows) == 1 and rows[0]['VolumeId'] == volume_id and rows[0]['Encrypted'] is True and
            rows[0]['KmsKeyId'].endswith('/585f0833-6a1c-465d-ab40-a6c8278cae39'), 'SOURCE_DISK_IDENTITY')
    if terminated:
        require(rows[0]['State'] == 'available' and not rows[0]['Attachments'], 'SOURCE_DISK_STILL_ATTACHED')
    return rows[0]


def preflight(ec2, ecs, request, action, volume_id):
    validate(request, inspect=action == 'inspect')
    host = instance(ec2, request['instanceId'])
    verify_host(host, request)
    source = instance(ec2, request['sourceInstanceId'])
    require(source['LaunchTime'] == timestamp(request['sourceLaunchTime']), 'SOURCE_IDENTITY_CHANGED')
    if action == 'inspect':
        return request
    services = ecs.describe_services(cluster=CLUSTER, services=SERVICES)
    require(not services.get('failures') and len(services['services']) == 2 and
            all(s['desiredCount'] == s['runningCount'] == s['pendingCount'] == 0
                for s in services['services']), 'ECS_WRITERS_NOT_DRAINED')
    terminated = source['State']['Name'] == 'terminated'
    require((action == 'fence' and not terminated and request['instanceId'] == request['sourceInstanceId']) or
            (action == 'restore' and terminated and request['instanceId'] != request['sourceInstanceId']),
            'POSITIVE_SOURCE_FENCE_REQUIRED')
    volume = source_disk(ec2, source, volume_id, terminated)
    request = json.loads(json.dumps(request))
    if action == 'restore':
        # Construct this proof from APIs now; never trust a caller's boolean.
        request['sourceFence'] = {'ec2State': 'terminated', 'instanceId': source['InstanceId'],
            'launchTime': request['sourceLaunchTime'], 'retainedVolumeVerified': True,
            'volumeId': volume['VolumeId'], 'verifiedAt': dt.datetime.now(dt.timezone.utc).isoformat()}
    return request


def verify_prior_fence(ssm, directory, request, volume_id):
    stem = request['trial'] + '-fence'
    intent = json.loads((directory / (stem + '.dispatch-intent.json')).read_text())
    dispatched = json.loads((directory / (stem + '.dispatch-result.json')).read_text())
    before = intent['request']
    require(intent['sourceVolumeId'] == volume_id and
            before['instanceId'] == before['sourceInstanceId'] == request['sourceInstanceId'] and
            all(before[k] == request[k] for k in ('sourceLaunchTime', 'expectedRows', 'expectedDataHash')),
            'FENCE_RECEIPT_IDENTITY')
    # Re-read the authentic SSM result instead of accepting a local "fenced" flag.
    result = ssm.get_command_invocation(CommandId=dispatched['Command']['CommandId'],
                                       InstanceId=request['sourceInstanceId'])
    require(result['Status'] == 'Success' and result['ResponseCode'] == 0, 'SQL_FENCE_NOT_CONFIRMED')
    receipt = json.loads(result['StandardOutputContent'])
    require(receipt['sourceFence']['accessMode'] == 'READ_ONLY' and
            receipt['sourceFence']['runtimeDisabled'] is True and
            receipt['sourceFence']['otherSessions'] == 0 and
            receipt['backupReceipt'] == request['backupReceipt'], 'SQL_FENCE_OR_BACKUP_MISMATCH')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'fence', 'restore'])
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--source-volume', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--host-sha256', required=True)
    parser.add_argument('--profile', default='cnp-cert-dev')
    parser.add_argument('--confirm-step')
    parser.add_argument('--dispatch', action='store_true', help='Otherwise preflight only')
    args = parser.parse_args()
    raw = Path(__file__).with_name('native_host.py').read_bytes().replace(b'\r\n', b'\n')
    require(hashlib.sha256(raw).hexdigest() == args.host_sha256, 'HOST_SOURCE_CHANGED')
    request = json.loads(args.request.read_text())
    import boto3
    from botocore.config import Config
    session = boto3.Session(profile_name=args.profile, region_name=REGION)
    config = Config(retries={'total_max_attempts': 1}, connect_timeout=8, read_timeout=30)
    client = lambda name: session.client(name, config=config)
    require(client('sts').get_caller_identity()['Arn'] == f'arn:aws:iam::{ACCOUNT}:user/cnp-cert-admin',
            'ADMIN_IDENTITY')
    ssm = client('ssm')
    if args.action == 'restore':
        verify_prior_fence(ssm, args.evidence, request, args.source_volume)
    request = preflight(client('ec2'), client('ecs'), request, args.action, args.source_volume)
    if not args.dispatch:
        print(json.dumps({'preflight': 'PASS', 'action': args.action, 'dispatched': False}))
        return
    require(args.confirm_step == args.action + ' ' + request['trial'], 'EXPLICIT_STEP_REQUIRED')
    rows = ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds', 'Values': [request['instanceId']]}])['InstanceInformationList']
    require(len(rows) == 1 and rows[0]['PingStatus'] == 'Online', 'SSM_NOT_ONLINE')
    token = None
    for _ in range(20):
        commands = ssm.list_commands(InstanceId=request['instanceId'], MaxResults=50,
                                    **({'NextToken': token} if token else {}))
        require(not any(c['Status'] in ('Pending', 'InProgress', 'Delayed')
                        for c in commands['Commands']), 'CONCURRENT_SSM')
        token = commands.get('NextToken')
        if not token:
            break
    require(not token, 'UNBOUNDED_SSM_HISTORY')
    args.evidence.mkdir(parents=True, exist_ok=True)
    stem = request['trial'] + '-' + args.action
    # All payload bytes are public source or private metadata, never secret values.
    script = "import base64,pathlib,hashlib,subprocess,os\nos.umask(0o077)\n"
    script += "p=pathlib.Path('/run/" + stem + "');p.mkdir(mode=0o700)\n"
    script += "raw=base64.b64decode(" + repr(base64.b64encode(raw).decode()) + ")\n"
    script += "assert hashlib.sha256(raw).hexdigest()==" + repr(args.host_sha256) + "\n"
    script += "(p/'native_host.py').write_bytes(raw)\n"
    script += "(p/'request.json').write_bytes(base64.b64decode(" + repr(base64.b64encode(json.dumps(request).encode()).decode()) + "))\n"
    script += "subprocess.run(['python3','-I','-B',str(p/'native_host.py')," + repr(args.action) + ",'--request',str(p/'request.json')],check=True)\n"
    with (args.evidence / (stem + '.dispatch-intent.json')).open('x') as stream:
        json.dump({'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'request': request,
                   'hostSha256': args.host_sha256, 'sourceVolumeId': args.source_volume}, stream, indent=2)
    result = ssm.send_command(InstanceIds=[request['instanceId']], DocumentName='AWS-RunShellScript',
        Comment='Explicit native SQL recovery step ' + stem, TimeoutSeconds=60,
        Parameters={'commands': ["python3 - <<'PY'\n" + script + "PY"], 'executionTimeout': ['900']})
    (args.evidence / (stem + '.dispatch-result.json')).write_text(json.dumps(result, default=str, indent=2))
    print(json.dumps({'commandId': result['Command']['CommandId'], 'status': 'DISPATCHED_READBACK_REQUIRED'}))


if __name__ == '__main__':
    main()
