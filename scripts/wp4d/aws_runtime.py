"""Bounded AWS ports for the accepted WP4 normal and recovery state machines.

Installed configuration supplies every resource identity. An in-process API
acknowledgement is only provenance for a fresh read, never success by itself.
An attempted call without that provenance reconciles as UNKNOWN on retry.
"""
import copy
import ipaddress
from datetime import datetime, timezone
import os
import signal
import subprocess
import time

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.normal_delivery.e3 import Process
from scripts.recovery.ports import ApplicationRuntime, NatRuntime


def require(ok):
    if not ok:
        raise ValueError("E1_WP4D_AWS_OBSERVATION_REJECTED")


def json_readback(value):
    """Convert SDK timestamps to the exact JSON date form WP4A validates."""
    if isinstance(value, datetime):
        require(value.tzinfo is not None)
        return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if type(value) is dict:
        return {key: json_readback(item) for key, item in value.items()}
    if type(value) is list:
        return [json_readback(item) for item in value]
    return value


def forward(actions):
    """One unweighted target group; never normalize away mixed/weighted routes."""
    require(type(actions) is list and len(actions) == 1)
    action = actions[0]
    require(action.get("Type") == "forward" and not action.get("AuthenticateCognitoConfig")
            and not action.get("AuthenticateOidcConfig"))
    target = action.get("TargetGroupArn")
    require(type(target) is str and bool(target))
    config = action.get("ForwardConfig")
    if config is not None:
        groups = config.get("TargetGroups")
        require(type(groups) is list and len(groups) == 1
                and groups[0].get("TargetGroupArn") == target
                and groups[0].get("Weight", 1) == 1)
        require(not config.get("TargetGroupStickinessConfig", {}).get("Enabled", False))
    return target


class Observer:
    def __init__(self, ecs, elb, config):
        self.ecs, self.elb, self.config = ecs, elb, copy.deepcopy(config)

    def routes(self):
        colors = self.config["colors"]
        listener = colors["blue"]["listener"]
        rule = colors["blue"]["candidate_rule"]
        listeners = self.elb.describe_listeners(ListenerArns=[listener]).get("Listeners", [])
        rules = self.elb.describe_rules(RuleArns=[rule]).get("Rules", [])
        require(len(listeners) == len(rules) == 1
                and listeners[0]["ListenerArn"] == listener and rules[0]["RuleArn"] == rule)
        return forward(listeners[0]["DefaultActions"]), forward(rules[0]["Actions"])

    def service(self, color):
        member = self.config["colors"][color]
        cluster, name = member["cluster"], member["service"]
        response = self.ecs.describe_services(cluster=cluster, services=[name])
        services = response.get("services", [])
        require(len(services) == 1 and not response.get("failures"))
        service = services[0]
        require(service["clusterArn"] == cluster and service["serviceName"] == name
                and service.get("status") == "ACTIVE")
        deployments = service.get("deployments", [])
        require(type(deployments) is list and len(deployments) == 1)
        deployment = deployments[0]
        revision = service["taskDefinition"]
        require(deployment.get("taskDefinition") == revision)
        desired, running, pending = (service[k] for k in ("desiredCount", "runningCount", "pendingCount"))
        require(all(type(n) is int and n >= 0 for n in (desired, running, pending)))
        # ECS does not set a task's desiredStatus to PENDING. Pending tasks
        # still appear in the RUNNING desired-status list.
        response = self.ecs.list_tasks(cluster=cluster, serviceName=name,
                                       desiredStatus="RUNNING", maxResults=100)
        require(not response.get("nextToken"))
        arns = response.get("taskArns", [])
        require(len(arns) == len(set(arns)) and len(arns) == running + pending)
        tasks = []
        if arns:
            result = self.ecs.describe_tasks(cluster=cluster, tasks=arns)
            require(not result.get("failures") and len(result.get("tasks", [])) == len(arns))
            tasks = result["tasks"]
            require({task["taskArn"] for task in tasks} == set(arns))
            for task in tasks:
                require(task.get("group") == "service:" + name
                        and task.get("taskDefinitionArn") == revision
                        and task.get("clusterArn") == cluster)
        stable = (deployment.get("rolloutState") == "COMPLETED" and
                  deployment.get("status") == "PRIMARY" and
                  desired == running and pending == 0 and len(tasks) == desired and
                  all(task.get("lastStatus") == "RUNNING" for task in tasks))
        require(service.get("loadBalancers") == [{
            "targetGroupArn": member["target_group"],
            "containerName": "demo-" + self.config["environment"] + "-app-api-" + color,
            "containerPort": 8080}])
        return service, tasks, stable

    def targets(self, color, tasks):
        """Prove exact task ENI IP to target ID membership with no mixed targets."""
        member = self.config["colors"][color]
        required = set()
        for task in tasks:
            require(task.get("lastStatus") == "RUNNING")
            attachments = task.get("attachments", [])
            require(len(attachments) == 1 and attachments[0].get("type") == "ElasticNetworkInterface"
                    and attachments[0].get("status") == "ATTACHED")
            items = attachments[0].get("details", [])
            detail = {item["name"]: item["value"] for item in items}
            require(len(detail) == len(items))
            ip = detail.get("privateIPv4Address")
            require(type(ip) is str and str(ipaddress.IPv4Address(ip)) == ip and ip not in required)
            required.add(ip)
        observed = self.elb.describe_target_health(TargetGroupArn=member["target_group"]).get("TargetHealthDescriptions", [])
        result = []
        for item in observed:
            target = item.get("Target", {})
            target_id = target.get("Id")
            require(type(target_id) is str and bool(target_id.strip()) and target_id == target_id.strip()
                    and target_id not in {x["id"] for x in result})
            require(target.get("Port") == 8080)
            result.append({"id": target_id, "state": item.get("TargetHealth", {}).get("State")})
        require({x["id"] for x in result} == required)
        return result


class Effects:
    def __init__(self, records):
        self.records = records
        self.applied = {}

    def now(self):
        return int(time.time())

    def prior(self, token):
        parts = token.split("/")
        require(len(parts) >= 3)
        key = "/".join(parts[:-1]) + "/" + parts[-1] + "/attempt"
        return self.records.read(key)

    def effect(self, token, deadline):
        require(self.now() < deadline)
        unknown = {"token": token, "request_sha256": None, "state": "UNKNOWN", "result": None}
        retained = self.records.read(token + "/ack")
        if retained is None:
            # A durable attempt may have reached AWS. Missing ACK is never
            # proof that the API call was not applied.
            return unknown if self.prior(token) is not None else {
                **unknown, "state": "ABSENT"}
        try:
            ack = a.decode(retained["bytes"])
            a.keys(ack, ("token", "request", "request_sha256", "result"))
            a.exact(ack["token"], token, "effect ACK token")
            a.exact(ack["request_sha256"], a.sha(a.canonical(ack["request"])), "effect ACK request")
            require(self.prior(token) is not None)
            verify = (self.applied[token][2] if token in self.applied else
                      lambda: self.verify_saved(token, ack["request"], ack["result"], deadline))
            # ECS/ALB effects are asynchronous. Poll the exact authoritative
            # readback, bounded per call, without ever resending the mutation.
            end = min(deadline, self.now() + 30)
            while self.now() < end:
                if verify() and self.now() < deadline:
                    return {"token": token, "request_sha256": ack["request_sha256"],
                            "state": "APPLIED", "result": copy.deepcopy(ack["result"])}
                time.sleep(2)
        except Exception:
            return unknown
        return unknown

    def remembered(self, token, request, result, verify):
        require(token not in self.applied)
        self.records.create(token + "/ack", a.canonical({
            "token": token, "request": request,
            "request_sha256": a.sha(a.canonical(request)), "result": result}))
        self.applied[token] = (copy.deepcopy(request), copy.deepcopy(result), verify)

    def verify_saved(self, token, request, result, deadline):
        raise NotImplementedError


class Delivery(Effects, d.Runtime):
    def __init__(self, ecs, elb, events, records, config):
        super().__init__(records)
        self.ecs, self.elb, self.events = ecs, elb, events
        self.observer = Observer(ecs, elb, config)
        self.config = copy.deepcopy(config)

    def snapshot(self, intent, deadline):
        require(self.now() < deadline)
        color = intent["color"]
        member = self.config["colors"][color]
        service, tasks, _ = self.observer.service(color)
        listener_target, rule_target = self.observer.routes()
        fields = intent["service"].keys()
        settings = {key: copy.deepcopy(service[key]) for key in fields if key in service}
        require(len(settings) == len(fields) - 2)  # cluster/service are derived from exact ARNs.
        settings["cluster"] = service["clusterArn"]
        settings["service"] = service["serviceName"]
        settings["desiredCount"] = service["desiredCount"]
        settings["taskDefinition"] = service["taskDefinition"]
        deployment = service["deployments"][0]["id"]
        require(self.now() < deadline)
        return {"environment": intent["environment"], "color": color,
                "cluster": member["cluster"], "service": member["service"],
                "listener": member["listener"], "rule": member["candidate_rule"],
                "normal_target": listener_target, "candidate_target": rule_target,
                "task_definition": service["taskDefinition"],
                "desired": service["desiredCount"], "running": service["runningCount"],
                "pending": service["pendingCount"],
                "cohort": sorted(task["taskArn"] for task in tasks if task.get("lastStatus") == "RUNNING"),
                "deployment": deployment, "service_snapshot": settings,
                "observed_at": self.now()}

    def read_task(self, revision, deadline):
        require(self.now() < deadline)
        result = self.ecs.describe_task_definition(taskDefinition=revision, include=["TAGS"])
        task = result["taskDefinition"]
        require(self.now() < deadline and task["taskDefinitionArn"] == revision)
        return a.canonical(json_readback(task))

    def register(self, token, request, deadline):
        require(self.now() < deadline and request["family"] in {
            "demo-" + self.config["environment"] + "-app-api-" + color
            for color in ("blue", "green")})
        response = self.ecs.register_task_definition(**copy.deepcopy(request))
        revision = response["taskDefinition"]["taskDefinitionArn"]
        result = {"task_definition_arn": revision}
        self.remembered(token, request, result,
                        lambda: a.decode(self.read_task(revision, deadline))["taskDefinitionArn"] == revision)

    def _service_update(self, token, request, deadline):
        require(self.now() < deadline)
        self.ecs.update_service(**copy.deepcopy(request))
        self.remembered(token, request, request,
                        lambda: self._service_matches(request))

    def _service_matches(self, request):
        color = next((c for c, m in self.config["colors"].items()
                      if m["service"] == request["service"] and m["cluster"] == request["cluster"]), None)
        require(color is not None)
        service, tasks, _ = self.observer.service(color)
        return (service["desiredCount"] == request["desiredCount"] and
                ("taskDefinition" not in request or service["taskDefinition"] == request["taskDefinition"]) and
                service["runningCount"] == request["desiredCount"] and service["pendingCount"] == 0)

    def drain(self, token, request, deadline): self._service_update(token, request, deadline)
    def attach(self, token, request, deadline): self._service_update(token, request, deadline)
    def start(self, token, request, deadline): self._service_update(token, request, deadline)

    def switch(self, token, request, deadline):
        require(self.now() < deadline and request["listener"] == self.config["colors"]["blue"]["listener"])
        self.elb.modify_listener(ListenerArn=request["listener"],
                                 DefaultActions=[{"Type": "forward", "TargetGroupArn": request["target"]}])
        self.remembered(token, request, request, lambda: self.observer.routes()[0] == request["target"])

    def candidate(self, token, request, deadline):
        require(self.now() < deadline and request["rule"] == self.config["colors"]["blue"]["candidate_rule"])
        self.elb.modify_rule(RuleArn=request["rule"],
                             Actions=[{"Type": "forward", "TargetGroupArn": request["target"]}])
        self.remembered(token, request, request, lambda: self.observer.routes()[1] == request["target"])

    def cleanup(self, token, request, deadline):
        require(self.now() < deadline and request["environment"] == self.config["environment"])
        schedule = self.config["cleanup"]
        require(any(request["cluster"] == m["cluster"] and request["service"] == m["service"]
                    for m in self.config["colors"].values()))
        # Preserve the native EventBridge Scheduled Event envelope. Cleanup
        # selects the inactive side from protected config and fresh topology.
        target = {"Id": "scale-down", "Arn": schedule["function_arn"]}
        self.events.put_rule(Name=schedule["rule"], ScheduleExpression=schedule["expression"],
                             State="ENABLED")
        response = self.events.put_targets(Rule=schedule["rule"], Targets=[target])
        require(response.get("FailedEntryCount") == 0)
        self.remembered(token, request, request, lambda: self._schedule_matches(schedule, target))

    def _schedule_matches(self, schedule, target):
        rule = self.events.describe_rule(Name=schedule["rule"])
        targets = self.events.list_targets_by_rule(Rule=schedule["rule"]).get("Targets", [])
        return (rule.get("ScheduleExpression") == schedule["expression"] and
                len(targets) == 1 and all(targets[0].get(k) == v for k, v in target.items()))

    def verify_saved(self, token, request, result, deadline):
        stage = token.rsplit("/", 1)[-1]
        if stage == "register":
            revision = result["task_definition_arn"]
            return a.decode(self.read_task(revision, deadline))["taskDefinitionArn"] == revision
        if stage in ("drain", "attach", "start"):
            return self._service_matches(request)
        if stage == "switch":
            require(request["listener"] == self.config["colors"]["blue"]["listener"] and
                    request["target"] in {m["target_group"] for m in self.config["colors"].values()})
            return self.observer.routes()[0] == request["target"]
        if stage == "candidate":
            require(request["rule"] == self.config["colors"]["blue"]["candidate_rule"] and
                    request["target"] in {m["target_group"] for m in self.config["colors"].values()})
            return self.observer.routes()[1] == request["target"]
        if stage == "cleanup":
            schedule = self.config["cleanup"]
            require(request["environment"] == self.config["environment"] and
                    any(request["cluster"] == m["cluster"] and request["service"] == m["service"]
                        for m in self.config["colors"].values()))
            target = {"Id": "scale-down", "Arn": schedule["function_arn"]}
            return self._schedule_matches(schedule, target)
        raise ValueError("E1_WP4D_EFFECT_STAGE_REJECTED")


class BoundedProcess(Process):
    def execute(self, argv, timeout):
        require(type(argv) is list and argv[:1] == ["python3"] and
                type(timeout) is int and 0 < timeout <= 1800)
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=timeout)
            require(len(output) <= 1048576)
            return {"exit_code": proc.returncode, "stdout": output}
        except Exception:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise


class Application(Effects, ApplicationRuntime):
    """Emergency and cleanup use the same protected environment observations."""
    def __init__(self, ecs, elb, events, records, config, history):
        super().__init__(records)
        self.ecs, self.elb, self.events = ecs, elb, events
        self.observer = Observer(ecs, elb, config)
        self.fixed, self.history = copy.deepcopy(config), history

    def config(self):
        value = {"environment": self.fixed["environment"],
                 "colors": copy.deepcopy(self.fixed["colors"]),
                 "cleanup_rule": self.fixed["cleanup"]["rule"],
                 "history": self.history.current()}
        return value

    def observe(self, operation, deadline):
        require(self.now() < deadline)
        routes = self.observer.routes()
        services = {}
        for color, member in self.fixed["colors"].items():
            service, tasks, stable = self.observer.service(color)
            revision = service["taskDefinition"]
            definition = self.ecs.describe_task_definition(taskDefinition=revision)["taskDefinition"]
            require(definition["taskDefinitionArn"] == revision)
            target_health = self.observer.targets(color, tasks)
            targets = [{**target, "revision": revision, "service": member["service"],
                        "target_group": member["target_group"], "operation": operation,
                        "environment": self.fixed["environment"]} for target in target_health]
            fields = a.MODEL["service_required"]
            settings = {key: copy.deepcopy(service[key]) for key in fields
                        if key not in ("cluster", "service") and key in service}
            require(len(settings) == len(fields) - 2)
            settings.update(cluster=service["clusterArn"], service=service["serviceName"],
                            taskDefinition=revision)
            services[color] = {"cluster": service["clusterArn"],
                               "service": service["serviceName"], "revision": revision,
                               "desired": service["desiredCount"],
                               "running": service["runningCount"],
                               "pending": service["pendingCount"],
                               "stable": stable, "targets": targets,
                               "task": json_readback(definition), "settings": settings}
        require(self.now() < deadline)
        return {"environment": self.fixed["environment"], "operation": operation,
                "observed_at": self.now(),
                "listener": self.fixed["colors"]["blue"]["listener"],
                "rule": self.fixed["colors"]["blue"]["candidate_rule"],
                "normal_targets": [routes[0]], "candidate_targets": [routes[1]],
                "services": services}

    def mutate(self, stage, token, request, deadline):
        require(self.now() < deadline)
        colors = self.fixed["colors"]
        if stage in ("scale", "scale_zero"):
            color = next((c for c, m in colors.items()
                          if request == {"cluster": m["cluster"], "service": m["service"],
                                         "desiredCount": request.get("desiredCount")}), None)
            require(color is not None and type(request["desiredCount"]) is int
                    and 0 <= request["desiredCount"] <= 100)
            self.ecs.update_service(cluster=request["cluster"], service=request["service"],
                                    desiredCount=request["desiredCount"])
            def verified():
                service, tasks, stable = self.observer.service(color)
                return (service["desiredCount"] == service["runningCount"] == request["desiredCount"]
                        and service["pendingCount"] == 0 and stable)
        elif stage == "switch":
            require(set(request) == {"listener", "target"}
                    and request["listener"] == colors["blue"]["listener"]
                    and request["target"] in {m["target_group"] for m in colors.values()})
            self.elb.modify_listener(ListenerArn=request["listener"],
                                     DefaultActions=[{"Type": "forward", "TargetGroupArn": request["target"]}])
            verified = lambda: self.observer.routes()[0] == request["target"]
        elif stage == "candidate":
            require(set(request) == {"rule", "target"}
                    and request["rule"] == colors["blue"]["candidate_rule"]
                    and request["target"] in {m["target_group"] for m in colors.values()})
            self.elb.modify_rule(RuleArn=request["rule"],
                                 Actions=[{"Type": "forward", "TargetGroupArn": request["target"]}])
            verified = lambda: self.observer.routes()[1] == request["target"]
        elif stage == "schedule":
            schedule = self.fixed["cleanup"]
            require(set(request) == {"environment", "cluster", "service", "rule", "target_id"}
                    and request["environment"] == self.fixed["environment"]
                    and request["rule"] == schedule["rule"] and request["target_id"] == "scale-down"
                    and any(m["cluster"] == request["cluster"] and m["service"] == request["service"]
                            for m in colors.values()))
            target = {"Id": "scale-down", "Arn": schedule["function_arn"]}
            self.events.put_rule(Name=schedule["rule"], ScheduleExpression=schedule["expression"], State="ENABLED")
            response = self.events.put_targets(Rule=schedule["rule"], Targets=[target])
            require(response.get("FailedEntryCount") == 0)
            def verified():
                rule = self.events.describe_rule(Name=schedule["rule"])
                targets = self.events.list_targets_by_rule(Rule=schedule["rule"]).get("Targets", [])
                return (rule.get("ScheduleExpression") == schedule["expression"] and
                        len(targets) == 1 and all(targets[0].get(k) == v for k, v in target.items()))
        elif stage == "remove_target":
            require(request == {"Rule": self.fixed["cleanup"]["rule"], "Ids": ["scale-down"]})
            response = self.events.remove_targets(**request)
            require(response.get("FailedEntryCount") == 0)
            verified = lambda: not self.events.list_targets_by_rule(Rule=request["Rule"]).get("Targets", [])
        elif stage == "delete_rule":
            require(request == {"Name": self.fixed["cleanup"]["rule"]})
            self.events.delete_rule(**request)
            def verified():
                try:
                    self.events.describe_rule(**request)
                    return False
                except Exception as error:
                    return getattr(error, "response", {}).get("Error", {}).get("Code") == "ResourceNotFoundException"
        else:
            raise ValueError("E1_WP4D_MUTATION_REJECTED")
        self.remembered(token, request, request, verified)

    def verify_saved(self, token, request, result, deadline):
        require(result == request)
        stage = token.rsplit("/", 1)[-1]
        if stage in ("scale", "scale_zero"):
            color = next((c for c, m in self.fixed["colors"].items()
                          if request == {"cluster": m["cluster"], "service": m["service"],
                                         "desiredCount": request.get("desiredCount")}), None)
            require(color is not None)
            service, _, stable = self.observer.service(color)
            return (stable and service["desiredCount"] == service["runningCount"] ==
                    request["desiredCount"] and service["pendingCount"] == 0)
        if stage == "switch":
            require(request["listener"] == self.fixed["colors"]["blue"]["listener"] and
                    request["target"] in {m["target_group"] for m in self.fixed["colors"].values()})
            return self.observer.routes()[0] == request["target"]
        if stage == "candidate":
            require(request["rule"] == self.fixed["colors"]["blue"]["candidate_rule"] and
                    request["target"] in {m["target_group"] for m in self.fixed["colors"].values()})
            return self.observer.routes()[1] == request["target"]
        schedule = self.fixed["cleanup"]
        if stage == "schedule":
            rule = self.events.describe_rule(Name=schedule["rule"])
            targets = self.events.list_targets_by_rule(Rule=schedule["rule"]).get("Targets", [])
            target = {"Id": "scale-down", "Arn": schedule["function_arn"]}
            return (request["environment"] == self.fixed["environment"] and
                    request["rule"] == schedule["rule"] and request["target_id"] == "scale-down" and
                    rule.get("ScheduleExpression") == schedule["expression"] and
                    len(targets) == 1 and all(targets[0].get(k) == v for k, v in target.items()))
        if stage == "remove_target":
            require(request == {"Rule": schedule["rule"], "Ids": ["scale-down"]})
            return not self.events.list_targets_by_rule(Rule=schedule["rule"]).get("Targets", [])
        if stage == "delete_rule":
            require(request == {"Name": schedule["rule"]})
            try:
                self.events.describe_rule(Name=schedule["rule"])
                return False
            except Exception as error:
                return getattr(error, "response", {}).get("Error", {}).get("Code") == "ResourceNotFoundException"
        raise ValueError("E1_WP4D_EFFECT_STAGE_REJECTED")


class Nat(Effects, NatRuntime):
    """Action-specific EC2 transport; protected resolver supplies exact membership."""
    def __init__(self, ec2, autoscaling, iam, records, resolver, action, operation, selector_asg, expected_instance=None):
        super().__init__(records)
        require(action in ("assign_eip", "change_rt", "disable_sdc"))
        self.ec2, self.autoscaling, self.iam, self.resolver, self.action = ec2, autoscaling, iam, resolver, action
        self.operation = operation
        require(type(selector_asg) is str and selector_asg in {slot["asg"] for slot in resolver.slots})
        self.selector_asg = selector_asg
        self.expected_instance = expected_instance

    def context(self, action, deadline):
        require(action == self.action and self.now() < deadline)
        # Resolver authenticates exact admin publication, ASG slot and current
        # EC2/launch state; it never accepts the event as membership evidence.
        key = self.resolver.environment + "/recovery/" + action + "/" + self.operation + "/intent"
        retained = self.records.read(key)
        selected = self.selector_asg
        if retained is not None:
            value = a.decode(retained["bytes"])
            selected = value["body"]["domain"]["membership"]["asg"]
            require(selected == self.selector_asg)
        state = self.resolver.observe(self.ec2, self.autoscaling, self.iam, action, self.now(), selected)
        require(self.expected_instance is None or state["membership"]["instance"] == self.expected_instance)
        return state

    def mutate(self, stage, token, request, deadline):
        require(stage == self.action and self.now() < deadline)
        current = self.context(stage, deadline)
        require(self.now() < deadline)
        member = current["membership"]
        if stage == "assign_eip":
            require(request == {"AllocationId": member["eip"], "NetworkInterfaceId": member["eni"],
                                "AllowReassociation": True})
            self.ec2.associate_address(**request)
            field, expected = "association_eni", member["eni"]
        elif stage == "change_rt":
            expected_request = {"RouteTableId": member["route_table"],
                                "DestinationCidrBlock": "0.0.0.0/0",
                                "NetworkInterfaceId": member["eni"],
                                "action": "replace_route" if current["route_exists"] else "create_route"}
            require(request == expected_request)
            verb = request["action"]
            args = {key: value for key, value in request.items() if key != "action"}
            getattr(self.ec2, verb)(**args)
            field, expected = "default_route_eni", member["eni"]
        else:
            require(request == {"InstanceId": member["instance"], "SourceDestCheck": {"Value": False}})
            self.ec2.modify_instance_attribute(**request)
            field, expected = "source_dest_check", False
        def verified():
            observed = self.context(stage, deadline)
            return (observed["membership"] == member and observed["observed"][field] == expected)
        self.remembered(token, request, request, verified)

    def verify_saved(self, token, request, result, deadline):
        require(result == request)
        stage = token.rsplit("/", 1)[-1]
        require(stage == self.action)
        current = self.context(stage, deadline)
        member = current["membership"]
        if stage == "assign_eip":
            require(request == {"AllocationId": member["eip"], "NetworkInterfaceId": member["eni"],
                                "AllowReassociation": True})
            return current["observed"]["association_eni"] == member["eni"]
        if stage == "change_rt":
            require(request["RouteTableId"] == member["route_table"] and
                    request["DestinationCidrBlock"] == "0.0.0.0/0" and
                    request["NetworkInterfaceId"] == member["eni"])
            return current["observed"]["default_route_eni"] == member["eni"]
        require(request == {"InstanceId": member["instance"],
                            "SourceDestCheck": {"Value": False}})
        return current["observed"]["source_dest_check"] is False
