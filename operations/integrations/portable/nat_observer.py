"""Observe real ASG/EC2 routing and a bounded private HTTPS probe; never repair."""
import datetime as dt
import hashlib
import json
from storage_observer import require, utc


def control_plane(clients, c):
    groups = clients('autoscaling').describe_auto_scaling_groups(AutoScalingGroupNames=[c['asg']])['AutoScalingGroups']
    require(len(groups) == 1 and groups[0]['AutoScalingGroupName'] == 'demo-dev-asg-nat-a', 'ASG_IDENTITY')
    group = groups[0]
    members = [m for m in group['Instances'] if m['LifecycleState'] == 'InService' and m['HealthStatus'] == 'Healthy']
    evidence = {'asg': group['AutoScalingGroupName'], 'desired': group['DesiredCapacity'], 'healthyMembers': [m['InstanceId'] for m in members]}
    failures = []
    if group['DesiredCapacity'] != 1 or len(members) != 1:
        failures.append('ONE_HEALTHY_NAT_NOT_PRESENT')
    else:
        reservations = clients('ec2').describe_instances(InstanceIds=[members[0]['InstanceId']])['Reservations']
        instances = [i for r in reservations for i in r['Instances']]
        require(len(instances) == 1, 'EC2_IDENTITY')
        i = instances[0]
        evidence.update(instance=i['InstanceId'], state=i['State']['Name'], subnet=i.get('SubnetId'),
                        launchTemplate=members[0].get('LaunchTemplate'), sdc=i.get('SourceDestCheck'), eni=next((x['NetworkInterfaceId'] for x in i.get('NetworkInterfaces', [])), None))
        if i['State']['Name'] != 'running' or i.get('SubnetId') != c['publicSubnet'] or i.get('VpcId') != c['vpc'] or members[0].get('LaunchTemplate', {}).get('LaunchTemplateId') != c['lt'] or str(members[0].get('LaunchTemplate', {}).get('Version')) != '4' or i.get('SourceDestCheck') is not False:
            failures.append('NAT_CONFIGURATION_NOT_RECOVERED')
    routes = clients('ec2').describe_route_tables(RouteTableIds=[c['routeTable']])['RouteTables']
    require(len(routes) == 1 and routes[0]['VpcId'] == c['vpc'], 'ROUTE_TABLE_IDENTITY')
    default = [r for r in routes[0]['Routes'] if r.get('DestinationCidrBlock') == '0.0.0.0/0']
    evidence['defaultRoutes'] = default
    if len(default) != 1 or default[0].get('State') != 'active' or default[0].get('NetworkInterfaceId') != evidence.get('eni'):
        failures.append('PRIVATE_ROUTE_NOT_RECOVERED')
    addresses = clients('ec2').describe_addresses(AllocationIds=[c['allocationId']])['Addresses']
    require(len(addresses) == 1 and addresses[0]['PublicIp'] == c['expectedEip'], 'EIP_IDENTITY')
    evidence['eip'] = {k: addresses[0].get(k) for k in ('AllocationId', 'PublicIp', 'NetworkInterfaceId', 'AssociationId')}
    if addresses[0].get('NetworkInterfaceId') != evidence.get('eni'):
        failures.append('EIP_NOT_RECOVERED')
    return {'verdict': 'Fail' if failures else 'Pass', 'failures': failures, 'evidence': evidence}


def connectivity(clients, c, now, invocation):
    payload = json.dumps({'operation': 'https-egress-a', 'observationId': invocation}).encode()
    result = clients('lambda').invoke(FunctionName=c['probeArn'], InvocationType='RequestResponse', Payload=payload)
    try:
        require(not result.get('FunctionError'), 'PROBE_EXECUTOR_FAILED')
        raw = result['Payload'].read(4097)
    finally:
        if result.get('Payload') is not None:
            result['Payload'].close()
    require(len(raw) <= 4096, 'PROBE_RESPONSE_BOUND')
    probe = json.loads(raw)
    require(probe['observationId'] == invocation and abs((utc(probe['at'])-now).total_seconds()) <= 30 and probe['httpsRequests'] == 1, 'PROBE_CORRELATION')
    require(probe.get('status') in ('HTTPS_SUCCESS', 'HTTPS_FAILED'), 'PROBE_STATUS')
    failed = probe['status'] != 'HTTPS_SUCCESS' or probe.get('egressIp') != c['expectedEip']
    return {'verdict': 'Fail' if failed else 'Pass',
            'failures': ['PRIVATE_HTTPS_EGRESS_FAILED'] if failed else [], 'evidence': {'probe': probe}}


def observe(clients, c, now, invocation):
    require(now < utc(c['expiresAt']), 'NAT_OBSERVER_WINDOW_EXPIRED')
    checks = {}
    for name, call in [('controlPlane', lambda: control_plane(clients, c)),
                       ('connectivity', lambda: connectivity(clients, c, now, invocation))]:
        try:
            checks[name] = call()
        except Exception as error:
            checks[name] = {'verdict': 'Unknown', 'failures': [name.upper() + '_UNAVAILABLE'],
                            'errorType': type(error).__name__, 'evidence': {}}
    control, network = checks['controlPlane'], checks['connectivity']
    # A failed real request is evidence even if an AWS read failed. A missing
    # probe result is never proof of lost connectivity, including a replacement.
    verdict = ('Fail' if network['verdict'] == 'Fail' else
               'Unknown' if 'Unknown' in (control['verdict'], network['verdict']) else
               control['verdict'])
    return {'verdict': verdict, 'checks': checks,
            'failures': control['failures'] + network['failures'],
            'evidence': {**control['evidence'], **network['evidence']}}


def handler(event, context, clients, c):
    now = dt.datetime.now(dt.timezone.utc)
    invocation = event['id']
    try:
        result = observe(clients, c, now, invocation)
    except Exception as error:
        # An unavailable observer is unknown health, never proof of NAT failure.
        result = {'verdict': 'Unknown', 'failures': ['OBSERVER_UNAVAILABLE'], 'errorType': type(error).__name__}
    identity = hashlib.sha256(json.dumps([invocation, result], sort_keys=True).encode()).hexdigest()
    report = {'schemaVersion': 1, 'monitor': 'nat-a-egress', 'producer': 'nat-observer', 'id': identity,
              'resource': 'nat/dev/a', 'generation': 'lt4-e13v6', 'observedAt': now.isoformat(), 'dataAt': now.isoformat(),
              'verdict': result['verdict'], 'assurance': 'Reported', 'runId': invocation,
              'detail': 'AWS control=' + result.get('checks', {}).get('controlPlane', {}).get('verdict', 'Unknown') +
                        '; private HTTPS=' + result.get('checks', {}).get('connectivity', {}).get('verdict', 'Unknown') +
                        '; ' + (','.join(result['failures']) or 'EIP_ROUTE_SDC_HTTPS_VERIFIED')}
    response = clients('events').put_events(Entries=[{'EventBusName': c['bus'], 'Source': 'sentinel.report.nat-observer',
        'DetailType': 'Sentinel Observation v1', 'Detail': json.dumps(report, separators=(',', ':'))}])
    require(response['FailedEntryCount'] == 0, 'NAT_OBSERVATION_DELIVERY_UNCONFIRMED')
    receipt = {'observationId': invocation, 'at': now.isoformat(), 'result': result, 'eventId': response['Entries'][0]['EventId'], 'reportId': identity}
    print(json.dumps(receipt))
    return receipt
