import boto3
import os

ec2 = boto3.client('ec2')
autoscaling = boto3.client('autoscaling')

# Environment variables provided by Terraform
SUBNET_A_ID = os.environ.get('SUBNET_A_ID')
SUBNET_B_ID = os.environ.get('SUBNET_B_ID')
EIP_A_ALLOCATION_ID = os.environ.get('EIP_A_ALLOCATION_ID')
EIP_B_ALLOCATION_ID = os.environ.get('EIP_B_ALLOCATION_ID')
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


def lambda_handler(event, context):
    detail = event.get('detail', {})
    instance_id = _extract_instance_id(detail)
    state = detail.get('state')
    asg_name = _extract_asg_name(detail)

    if not instance_id:
        instance_id = _instance_id_from_asg(asg_name)
        if not instance_id:
            print(f"Ignoring event without resolvable instance ID: {event}")
            return

    # Legacy EC2 events include state; keep compatibility.
    if state and state != 'running':
        print(f"Ignoring event: instance_id={instance_id}, state={state}")
        return

    if ASG_PREFIX and asg_name and not asg_name.startswith(ASG_PREFIX):
        print(f"Ignoring instance {instance_id} from non-NAT ASG {asg_name}")
        return

    print(f"Assigning EIP to NAT instance: {instance_id}")

    # Retrieve instance information
    resp = ec2.describe_instances(InstanceIds=[instance_id])
    instance = resp['Reservations'][0]['Instances'][0]

    subnet_id = instance.get('SubnetId')
    eni_id = instance['NetworkInterfaces'][0]['NetworkInterfaceId']

    # Choose the correct EIP based on the subnet (AZ)
    if subnet_id == SUBNET_A_ID:
        allocation_id = EIP_A_ALLOCATION_ID
    elif subnet_id == SUBNET_B_ID:
        allocation_id = EIP_B_ALLOCATION_ID
    else:
        print(f"Subnet {subnet_id} does not match A/B, skipping.")
        return

    print(f"Associating EIP {allocation_id} to ENI {eni_id}")

    ec2.associate_address(
        AllocationId=allocation_id,
        NetworkInterfaceId=eni_id,
        AllowReassociation=True
    )

    print("EIP successfully associated.")
