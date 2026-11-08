"""E15-H fixed DEV native-controller inhibition plan and SDK read normalization.

No client creation or mutation execution. Applying this plan requires separately
approved administrator authority and durable attempts under the original E2
owner. Suspension does not cancel running activities. Snapshots are diagnostic.
"""
import copy
from scripts.lifecycle import contract as c
from scripts.nat.scope import slots

PROCESSES = ('Launch', 'AlarmNotification', 'AZRebalance', 'ReplaceUnhealthy',
             'ScheduledActions', 'InstanceRefresh')
TERMINAL = ('Successful', 'Failed', 'Cancelled')


class Native:
    def __init__(self, asg, ec2, config):
        self.members = slots(config)
        self.asg, self.ec2 = asg, ec2

    def commands(self):
        """No Terminate suspension, force deletion, EIP or route mutations."""
        return [dict(asg=s['asg'], suspend=dict(AutoScalingGroupName=s['asg'],
                    ScalingProcesses=list(PROCESSES)), capacity=dict(AutoScalingGroupName=s['asg'],
                    MinSize=0, MaxSize=0, DesiredCapacity=0)) for s in self.members]

    def observe(self, previous_instances):
        c.require(type(previous_instances) is dict and set(previous_instances)=={s['asg'] for s in self.members},
                  'complete prior membership captured before inhibition')
        observations = {}; blockers = []
        for member in self.members:
            name = member['asg']; prior = previous_instances[name]
            c.require(type(prior) is list and len(set(prior)) == len(prior) and
                      all(type(i) is str and i.startswith('i-') for i in prior), 'exact prior instances')
            groups = self.asg.describe_auto_scaling_groups(AutoScalingGroupNames=[name])['AutoScalingGroups']
            c.require(len(groups)==1 and groups[0]['AutoScalingGroupName']==name, 'exact group read')
            group = groups[0]
            c.require(group['VPCZoneIdentifier']==member['subnet'], 'protected DEV subnet')
            suspended = {p['ProcessName'] for p in group['SuspendedProcesses']}
            if not set(PROCESSES)<=suspended or 'Terminate' in suspended or any(
                    group[k] != 0 for k in ('MinSize','MaxSize','DesiredCapacity')):
                blockers.append('NATIVE_INHIBITION_UNPROVED')
            activities = []; seen = set(); token = None
            for _ in range(100):
                args = dict(AutoScalingGroupName=name)
                if token is not None: args['NextToken'] = token
                response = self.asg.describe_scaling_activities(**args)
                for item in response['Activities']:
                    c.require(item['AutoScalingGroupName']==name and item['ActivityId'] not in seen, 'activity identity')
                    seen.add(item['ActivityId'])
                    activities.append(dict(id=item['ActivityId'], status=item['StatusCode'], ended='EndTime' in item))
                    if item['StatusCode'] not in TERMINAL or 'EndTime' not in item:
                        blockers.append('NATIVE_ACTIVITY_UNSETTLED')
                next_token = response.get('NextToken')
                if not next_token: break
                c.require(next_token != token, 'activity pagination')
                token = next_token
            else: c.require(False, 'bounded exhaustive activity inventory')
            current = [i['InstanceId'] for i in group['Instances']]
            if current: blockers.append('NATIVE_MEMBERS_REMAIN')
            identities = sorted(set(prior+current)); instances = {}
            if identities:
                response = self.ec2.describe_instances(InstanceIds=identities)
                for reservation in response['Reservations']:
                    for instance in reservation['Instances']:
                        identity = instance['InstanceId']
                        c.require(identity in identities and identity not in instances, 'exact prior/current EC2 identity')
                        instances[identity] = instance['State']['Name']
                c.require(set(instances)==set(identities), 'all prior/current instances observed')
                if any(state != 'terminated' for state in instances.values()):
                    blockers.append('PRIOR_INSTANCE_TERMINATION_UNPROVED')
            observations[name] = dict(suspended=sorted(suspended), members=current,
                capacity={k:group[k] for k in ('MinSize','MaxSize','DesiredCapacity')},
                activities=activities, instances=instances)
        return dict(observations=copy.deepcopy(observations), blockers=sorted(set(blockers)),
                    snapshot='TERMINAL_OBSERVED' if not blockers else 'UNKNOWN',
                    service_finality='UNPROVED', installed=False)
