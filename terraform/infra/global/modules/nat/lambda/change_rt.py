import boto3
import os
from botocore.exceptions import ClientError

ec2 = boto3.client('ec2')
autoscaling = boto3.client('autoscaling')

# Environment variables provided by Terraform
ROUTE_TABLE_A_ID = os.environ.get('ROUTE_TABLE_A_ID')
ROUTE_TABLE_B_ID = os.environ.get('ROUTE_TABLE_B_ID')
SUBNET_A_ID = os.environ.get('SUBNET_A_ID')
SUBNET_B_ID = os.environ.get('SUBNET_B_ID')
ASG_PREFIX = os.environ.get('ASG_PREFIX', '').strip()


def _extract_instance_id(detail):
    return detail.get('instance-id') or detail.get('EC2InstanceId')


def _extract_asg_name(detail):
    return detail.get('AutoScalingGroupName')


def _instance_id_from_asg(asg_name):
    if not asg_name:
        return None

    resp = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[asg_name]
    )
    groups = resp.get('AutoScalingGroups', [])
    if not groups:
        print(f"ASG not found: {asg_name}")
        return None

    instances = groups[0].get('Instances', [])
    preferred = [
        i for i in instances
        if i.get('LifecycleState') == 'InService'
        and i.get('HealthStatus') == 'Healthy'
    ]
    selected = (preferred or instances or [None])[0]
    return selected.get('InstanceId') if selected else None


def _upsert_default_route(route_table_id, eni_id):
    try:
        ec2.replace_route(
            RouteTableId=route_table_id,
            DestinationCidrBlock='0.0.0.0/0',
            NetworkInterfaceId=eni_id
        )
        print("Route successfully replaced.")
        return
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', '')

        if code not in {'InvalidRoute.NotFound', 'InvalidParameterValue'}:
            print(f"Unexpected replace_route error ({code}): {e}")
            raise

    try:
        print("Default route missing, creating it now...")
        ec2.create_route(
            RouteTableId=route_table_id,
            DestinationCidrBlock='0.0.0.0/0',
            NetworkInterfaceId=eni_id
        )
        print("Route successfully created.")
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', '')

        # Handle race conditions where another workflow creates route first
        if code == 'RouteAlreadyExists':
            print("Route already exists, retrying replace_route...")
            ec2.replace_route(
                RouteTableId=route_table_id,
                DestinationCidrBlock='0.0.0.0/0',
                NetworkInterfaceId=eni_id
            )
            print("Route successfully replaced after race condition.")
            return

        print(f"Unexpected create_route error ({code}): {e}")
        raise


def lambda_handler(event, context):
    detail = event.get('detail', {})
    instance_id = _extract_instance_id(detail)
    state = detail.get('state')
    asg_name = _extract_asg_name(detail)

    # Legacy EC2 events include state; keep compatibility.
    if state and state != 'running':
        print(f"Ignoring event: instance_id={instance_id}, state={state}")
        return

    if not instance_id:
        instance_id = _instance_id_from_asg(asg_name)
        if not instance_id:
            print(f"Ignoring event without resolvable instance ID: {event}")
            return

    if ASG_PREFIX and asg_name and not asg_name.startswith(ASG_PREFIX):
        print(f"Ignoring instance {instance_id} from non-NAT ASG {asg_name}")
        return

    print(f"Processing NAT instance: {instance_id}")

    # Fetch instance metadata
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    instance = resp['Reservations'][0]['Instances'][0]

    subnet_id = instance.get('SubnetId')
    eni_id = instance['NetworkInterfaces'][0]['NetworkInterfaceId']

    # Determine which route table to update based on subnet
    if subnet_id == SUBNET_A_ID:
        route_table_id = ROUTE_TABLE_A_ID
    elif subnet_id == SUBNET_B_ID:
        route_table_id = ROUTE_TABLE_B_ID
    else:
        print(f"Subnet {subnet_id} does not match configured subnets, skipping.")
        return

    print(f"Updating default route in {route_table_id} -> ENI {eni_id}")
    _upsert_default_route(route_table_id, eni_id)
