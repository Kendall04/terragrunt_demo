"""Bounded read-only launch evidence and separately authenticated admin approval.

No command execution, instance health mutation, arbitrary probe or AMI selector.
"""
import copy
from datetime import datetime
import hashlib
import json
import re
import time
from abc import ABC, abstractmethod


def require(ok):
    if not ok:
        raise ValueError("E13_NAT_EVIDENCE_REJECTED")


def checksum(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def launch_event(event, config):
    """Event identifies an existing slot; it never enrolls a caller instance."""
    require(type(event) is dict and event.get("source") == "aws.autoscaling"
            and event.get("detail-type") == "EC2 Instance Launch Successful"
            and event.get("account") == config["account"] and event.get("region") == config["region"])
    require(type(event.get("id")) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", event["id"]))
    stamp = event.get("time")
    require(type(stamp) is str and len(stamp) <= 40)
    try:
        emitted = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("E13_NAT_EVIDENCE_REJECTED") from None
    require(emitted.tzinfo is not None and -60 <= time.time() - emitted.timestamp() <= 1800)
    detail = event.get("detail")
    require(type(detail) is dict and type(detail.get("EC2InstanceId")) is str
            and re.fullmatch(r"i-[0-9a-f]{8,17}", detail["EC2InstanceId"]))
    selected = [slot for slot in config["nat_slots"] if slot["asg"] == detail.get("AutoScalingGroupName")]
    require(len(selected) == 1)
    return selected[0]["asg"], detail["EC2InstanceId"]


def assess(ec2, state, now):
    """Fresh protected membership is supplied by Resolver, never by event flags.

    Console evidence proves fixed bootstrap completion at launch, not current
    packet forwarding. Private-subnet egress always needs separate live proof.
    Missing evidence and missing prerequisites fail closed without mutations.
    """
    m, o = state["membership"], state["observed"]
    require(o["association_eni"] == m["eni"] and o["default_route_eni"] == m["eni"]
            and o["source_dest_check"] is False and state["route_exists"])
    table = ec2.describe_route_tables(RouteTableIds=[m["route_table"]])["RouteTables"]
    require(type(table) is list and len(table) == 1 and table[0]["VpcId"] == m["vpc"]
            and table[0]["RouteTableId"] == m["route_table"])
    routes = [route for route in table[0]["Routes"] if route.get("DestinationCidrBlock") == "0.0.0.0/0"]
    require(len(routes) == 1 and routes[0].get("NetworkInterfaceId") == m["eni"]
            and routes[0].get("State") == "active")
    instance = ec2.describe_instances(InstanceIds=[m["instance"]])["Reservations"][0]["Instances"][0]
    require(instance["InstanceId"] == m["instance"] and instance["State"]["Name"] == "running")
    launched = instance["LaunchTime"]
    require(isinstance(launched, datetime))
    output = ec2.get_console_output(InstanceId=m["instance"], Latest=True)
    require(output.get("InstanceId") == m["instance"] and type(output.get("Output")) is str
            and len(output["Output"]) <= 200000)
    stamp = output.get("Timestamp")
    require(isinstance(stamp, datetime) and launched.timestamp() <= stamp.timestamp() <= now)
    # Botocore decodes GetConsoleOutput in its after-call handler.
    raw = output["Output"]
    require("\ufffd" not in raw)
    matches = re.findall(r"(?m)^E13_NAT_BOOTSTRAP_V1 (i-[0-9a-f]{8,17}) ([0-9]{1,12}) CONFIGURED\r?$", raw)
    require(len(matches) == 1 and matches[0][0] == m["instance"]
            and launched.timestamp() <= int(matches[0][1]) <= stamp.timestamp()
            and "E13_NAT_BOOTSTRAP_FAILED" not in raw)
    return {"schema": "E13_NAT_READINESS_V1", "membership": copy.deepcopy(m),
            "observed_at": now, "network_prerequisites": "VERIFIED",
            "bootstrap": "CONFIGURED_AT_LAUNCH", "private_subnet_egress": "UNVERIFIED_LIVE_PROOF_REQUIRED"}


def verify(ec2, resolve, expected_instance, now=time.time, pause=time.sleep):
    """At most 12 passes, 110 seconds sleep and a 120-second acceptance budget.

    An in-progress SDK observation can finish after the budget; it cannot become
    success. Fixed SDK timeouts and Lambda's 600-second ceiling bound execution.
    """
    deadline = now() + 120
    for attempt in range(12):
        try:
            require(now() < deadline)
            state = resolve()
            require(now() < deadline)
            require(state["membership"]["instance"] == expected_instance)
            evidence = assess(ec2, state, int(now()))
            require(now() < deadline)
            return evidence
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError):
            if attempt == 11 or now() >= deadline:
                raise ValueError("E13_NAT_READINESS_UNVERIFIED") from None
            pause(min(10, max(0, deadline - now())))
    raise ValueError("E13_NAT_READINESS_UNVERIFIED")


class ReplacementAdmin(ABC):
    """Separate authenticated human port, not implemented by the runtime.

    Must independently read both exact launch versions and all environment
    network/profile identities. Approval is obtained in the administrator's
    channel; a runtime request cannot construct or provide this observation.
    """
    @abstractmethod
    def observe(self, environment, asg):
        raise NotImplementedError


def replacement(channel, environment, asg):
    """Return a reviewable contract only; never apply or choose a launch image."""
    require(isinstance(channel, ReplacementAdmin) and environment in ("dev", "prod"))
    value = channel.observe(environment, asg)
    require(type(value) is dict and set(value) == {"old", "candidate", "approval", "readback"}
            and value["readback"] == "EXACT_LAUNCH_VERSIONS_AND_NETWORK_VERIFIED")
    old, candidate, approval = value["old"], value["candidate"], value["approval"]
    fields = {"environment", "vpc", "subnet", "az", "asg", "eip", "route_table", "spec"}
    require(type(old) is dict and type(candidate) is dict and set(old) == fields and set(candidate) == fields)
    require(type(asg) is str and asg.startswith("demo-" + environment + "-"))
    for field, prefix in (("vpc", "vpc"), ("subnet", "subnet"), ("eip", "eipalloc"), ("route_table", "rtb")):
        require(type(old[field]) is str and re.fullmatch(prefix + r"-[0-9a-f]{8,17}", old[field]))
    require(type(old["az"]) is str and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9][a-z]", old["az"]))
    require(old["environment"] == environment and old["asg"] == asg
            and all(old[k] == candidate[k] for k in fields - {"spec"}))
    from scripts.recovery.nat import SPEC
    require(set(old["spec"]) == set(SPEC) and set(candidate["spec"]) == set(SPEC))
    changed = {"ami", "launch_template_version"}
    require(all(old["spec"][k] == candidate["spec"][k] for k in set(SPEC) - changed))
    for spec in (old["spec"], candidate["spec"]):
        require(type(spec["launch_template_version"]) is int and spec["launch_template_version"] > 0
                and re.fullmatch(r"ami-[0-9a-f]{8,17}", spec["ami"])
                and re.fullmatch(r"lt-[0-9a-f]{8,17}", spec["launch_template"])
                and re.fullmatch(r"[0-9a-f]{64}", spec["user_data_sha256"])
                and spec["instance_type"] == "t3.micro" and spec["http_tokens"] == "required"
                and spec["associate_public_ip"] is True and spec["delete_on_termination"] is True
                and type(spec["security_groups"]) is list and len(spec["security_groups"]) == 1
                and re.fullmatch(r"sg-[0-9a-f]{8,17}", spec["security_groups"][0])
                and re.fullmatch(r"arn:aws:iam::[0-9]{12}:instance-profile/demo-" + environment + "-nat-instance-profile", spec["instance_profile"])
                and spec["role"] == spec["instance_profile"].replace(":instance-profile/", ":role/").replace("-instance-profile", "-role")
                and spec["tags"].get("Environment") == environment and spec["tags"].get("Role") == "nat")
    require(candidate["spec"]["launch_template_version"] > old["spec"]["launch_template_version"])
    require(type(approval) is dict and set(approval) == {"environment", "asg", "old_sha256", "candidate_sha256", "source_commit", "maintenance"}
            and approval["environment"] == environment and approval["asg"] == asg
            and approval["old_sha256"] == checksum(old) and approval["candidate_sha256"] == checksum(candidate)
            and re.fullmatch(r"[0-9a-f]{40}", approval["source_commit"])
            and approval["maintenance"] == "ADMIN_APPROVED_SINGLE_AZ_OUTAGE")
    return copy.deepcopy(value)
