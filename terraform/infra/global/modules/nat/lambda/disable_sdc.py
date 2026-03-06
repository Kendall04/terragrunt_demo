import boto3
import os
import time

ec2 = boto3.client('ec2')

# Common prefix used to validate that the instance belongs
# to one of the expected Auto Scaling Groups.
ASG_PREFIX = os.environ.get('ASG_PREFIX', '').strip()


def _extract_instance_id(detail):
    return detail.get('instance-id') or detail.get('EC2InstanceId')


def _extract_asg_name(detail):
    return detail.get('AutoScalingGroupName')


def lambda_handler(event, context):
    detail = event.get('detail', {})
    instance_id = _extract_instance_id(detail)
    state = detail.get('state')

    # Legacy EC2 events include state; keep compatibility.
    if state and state != 'running':
        print(f"Ignoring event: instance_id={instance_id}, state={state}")
        return

    if not instance_id:
        print(f"Ignoring event without instance ID: {event}")
        return

    asg_name = _extract_asg_name(detail)

    # For EC2 state-change events, try to read ASG tag (it may not appear immediately)
    if not asg_name:
        asg_name = get_asg_tag(instance_id)
        if not asg_name:
            time.sleep(5)
            asg_name = get_asg_tag(instance_id)

    print(f"Instance {instance_id} belongs to ASG={asg_name}")

    # Ensure instance belongs to the expected ASG prefix
    if ASG_PREFIX:
        if not asg_name:
            print(f"ASG name not found for {instance_id}, aborting.")
            return

        if not asg_name.startswith(ASG_PREFIX):
            print(f"Instance {instance_id} not allowed "
                  f"(asg={asg_name}, expected prefix={ASG_PREFIX})")
            return

    # Disable Source/Destination Check -> required for NAT instances
    ec2.modify_instance_attribute(
        InstanceId=instance_id,
        SourceDestCheck={'Value': False}
    )
    print(f"Source/Dest Check disabled on {instance_id}")


def get_asg_tag(instance_id):
    """Returns the Auto Scaling Group name from EC2 instance tags."""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        tags = response['Reservations'][0]['Instances'][0].get('Tags', [])
        return next(
            (t['Value'] for t in tags
             if t['Key'] == 'aws:autoscaling:groupName'),
            None
        )
    except Exception as e:
        print(f"Error retrieving tags for {instance_id}: {e}")
        return None
