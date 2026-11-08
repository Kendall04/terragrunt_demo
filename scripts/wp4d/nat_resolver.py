"""Protected two-slot NAT membership from admin config and fresh AWS describes."""
import base64
import hashlib


def require(ok):
    if not ok:
        raise ValueError("E1_WP4D_NAT_MEMBERSHIP_REJECTED")


def one(items):
    require(type(items) is list and len(items) == 1)
    return items[0]


def tags(items):
    require(type(items) is list and all(set(item) >= {"Key", "Value"} for item in items))
    value = {item["Key"]: item["Value"] for item in items}
    require(len(value) == len(items))
    return value


class Resolver:
    """A slot is identified by exact protected ASG/VPC/AZ/EIP/RT/LT values.

    Dynamic instance and ENI IDs come only from the unique current InService,
    Healthy member of that exact ASG and independent EC2 observations. A caller
    event cannot add a slot or nominate a foreign instance.
    """
    def __init__(self, environment, slots):
        require(environment in ("dev", "prod") and type(slots) is list and len(slots) == 2)
        require(all(type(slot) is dict and slot.get("environment") == environment
                    for slot in slots))
        require(len({slot["asg"] for slot in slots}) == 2
                and len({slot["az"] for slot in slots}) == 2
                and len({slot["vpc"] for slot in slots}) == 1
                and len({slot["eip"] for slot in slots}) == 2
                and len({slot["route_table"] for slot in slots}) == 2)
        self.environment, self.slots = environment, slots

    def _slot(self, ec2, autoscaling, iam, slot):
        asg = one(autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[slot["asg"]]).get("AutoScalingGroups", []))
        require(asg["AutoScalingGroupName"] == slot["asg"] and
                len(asg.get("Instances", [])) == 1 and
                len(asg.get("VPCZoneIdentifier", "").split(",")) == 1 and
                asg["VPCZoneIdentifier"] == slot["subnet"])
        member = one(asg["Instances"])
        require(member.get("LifecycleState") == "InService" and member.get("HealthStatus") == "Healthy")
        lt = member.get("LaunchTemplate", {})
        require(lt.get("LaunchTemplateId") == slot["spec"]["launch_template"]
                and lt.get("Version") == str(slot["spec"]["launch_template_version"]))
        instance_id = member["InstanceId"]
        reservations = ec2.describe_instances(InstanceIds=[instance_id]).get("Reservations", [])
        instance = one(one(reservations).get("Instances", []))
        require(instance["InstanceId"] == instance_id and instance["State"]["Name"] == "running"
                and instance["VpcId"] == slot["vpc"] and instance["SubnetId"] == slot["subnet"]
                and instance["Placement"]["AvailabilityZone"] == slot["az"]
                and instance["ImageId"] == slot["spec"]["ami"]
                and instance["InstanceType"] == slot["spec"]["instance_type"]
                and instance["IamInstanceProfile"]["Arn"] == slot["spec"]["instance_profile"]
                and instance["MetadataOptions"]["HttpTokens"] == slot["spec"]["http_tokens"])
        profile_arn = slot["spec"]["instance_profile"]
        profile = iam.get_instance_profile(
            InstanceProfileName=profile_arn.rsplit("/", 1)[-1])["InstanceProfile"]
        require(profile["Arn"] == profile_arn and len(profile["Roles"]) == 1
                and profile["Roles"][0]["Arn"] == slot["spec"]["role"])
        observed_tags = tags(instance.get("Tags", []))
        require(all(observed_tags.get(k) == v for k, v in slot["spec"]["tags"].items()))
        security_groups = sorted(x["GroupId"] for x in instance.get("SecurityGroups", []))
        require(security_groups == sorted(slot["spec"]["security_groups"]))
        eni_ref = one(instance.get("NetworkInterfaces", []))
        eni_id = eni_ref["NetworkInterfaceId"]
        eni = one(ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id]).get("NetworkInterfaces", []))
        require(eni["NetworkInterfaceId"] == eni_id and eni["VpcId"] == slot["vpc"]
                and eni["SubnetId"] == slot["subnet"]
                and eni["AvailabilityZone"] == slot["az"]
                and eni["Attachment"]["InstanceId"] == instance_id
                and eni["Attachment"].get("DeleteOnTermination") is slot["spec"]["delete_on_termination"]
                and eni_ref["NetworkInterfaceId"] == eni_id)
        lt_info = one(ec2.describe_launch_template_versions(
            LaunchTemplateId=slot["spec"]["launch_template"],
            Versions=[str(slot["spec"]["launch_template_version"])]).get("LaunchTemplateVersions", []))
        require(lt_info["VersionNumber"] == slot["spec"]["launch_template_version"])
        data = lt_info["LaunchTemplateData"]
        user_data = base64.b64decode(data["UserData"], validate=True)
        require(hashlib.sha256(user_data).hexdigest() == slot["spec"]["user_data_sha256"]
                and data["ImageId"] == slot["spec"]["ami"]
                and data["InstanceType"] == slot["spec"]["instance_type"]
                and data["IamInstanceProfile"]["Name"] == slot["spec"]["instance_profile"].rsplit("/", 1)[-1]
                and data["MetadataOptions"]["HttpTokens"] == slot["spec"]["http_tokens"])
        actual_user_data = ec2.describe_instance_attribute(InstanceId=instance_id, Attribute="userData")
        require(actual_user_data.get("InstanceId") == instance_id and
                hashlib.sha256(base64.b64decode(actual_user_data["UserData"]["Value"], validate=True)).hexdigest()
                == slot["spec"]["user_data_sha256"])
        lt_network = one(data.get("NetworkInterfaces", []))
        require(lt_network.get("AssociatePublicIpAddress") is slot["spec"]["associate_public_ip"]
                and lt_network.get("DeleteOnTermination") is slot["spec"]["delete_on_termination"]
                and sorted(lt_network.get("Groups", [])) == security_groups)
        address = one(ec2.describe_addresses(AllocationIds=[slot["eip"]]).get("Addresses", []))
        require(address["AllocationId"] == slot["eip"]
                and tags(address.get("Tags", [])).get("Environment") == self.environment)
        table = one(ec2.describe_route_tables(RouteTableIds=[slot["route_table"]]).get("RouteTables", []))
        require(table["RouteTableId"] == slot["route_table"] and table["VpcId"] == slot["vpc"])
        defaults = [route for route in table.get("Routes", [])
                    if route.get("DestinationCidrBlock") == "0.0.0.0/0"]
        require(len(defaults) <= 1)
        check = ec2.describe_instance_attribute(InstanceId=instance_id, Attribute="sourceDestCheck")
        require(check.get("InstanceId") == instance_id and
                type(check.get("SourceDestCheck", {}).get("Value")) is bool)
        membership = {k: v for k, v in slot.items() if k not in ("account", "region")}
        membership.update(instance=instance_id, eni=eni_id)
        observed = {**membership, "lifecycle": member["LifecycleState"],
                    "health": member["HealthStatus"],
                    "eni_instance": eni["Attachment"]["InstanceId"],
                    "route_vpc": table["VpcId"], "eip_environment": self.environment,
                    "association_eni": address.get("NetworkInterfaceId"),
                    "default_route_eni": defaults[0].get("NetworkInterfaceId") if defaults else None,
                    "source_dest_check": check["SourceDestCheck"]["Value"]}
        return {"membership": membership, "observed": observed,
                "route_exists": bool(defaults)}

    def observe(self, ec2, autoscaling, iam, action, now, selected_asg=None):
        states = [self._slot(ec2, autoscaling, iam, slot) for slot in self.slots]
        if selected_asg is not None:
            selected = [state for state in states if state["membership"]["asg"] == selected_asg]
            require(len(selected) == 1)
            return {**selected[0], "observed_at": now}
        def needs(state):
            m, o = state["membership"], state["observed"]
            if action == "assign_eip": return o["association_eni"] != m["eni"]
            if action == "change_rt": return o["default_route_eni"] != m["eni"]
            if action == "disable_sdc": return o["source_dest_check"] is True
            raise ValueError("E1_WP4D_NAT_ACTION_REJECTED")
        candidates = [state for state in states if needs(state)]
        require(len(candidates) == 1)
        return {**candidates[0], "observed_at": now}
