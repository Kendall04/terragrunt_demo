"""Owner-approved DEV compatibility only; installed in two exact DEV bundles.

The storage response, not an eligibility body, owns S3 VersionId. ECS defaults
are normalized only when their complete values are inert and understood.
"""
import copy
import time
from scripts.normal_delivery import authorization as a


def eligibility(observed, release_id, endpoint):
    a.require(endpoint == "deploy-dev")
    record = a.envelope(observed, "release_id", release_id)
    a.keys(record, ("schema", "writer", "release_id", "state"))
    a.require(record["schema"] == "E1_ELIGIBILITY_DEV_V2"
              and record["writer"] == "SECURITY_ADMIN"
              and record["release_id"] == release_id
              and record["state"] in ("ELIGIBLE", "REVOKED"))
    a.require(record["state"] == "ELIGIBLE")
    # envelope() validated the real current storage VersionId and canonical bytes.
    # Authorizer records that VersionId and the exact raw body hash in its intent.
    return record


def deployment(value):
    result = copy.deepcopy(value)
    a.require(type(result) is dict)
    defaults = {"deploymentCircuitBreaker": {"enable": False, "rollback": False},
                "strategy": "ROLLING", "bakeTimeInMinutes": 0}
    for key, expected in defaults.items():
        if key in result:
            a.exact(result.pop(key), expected, "DEV inert ECS default." + key)
    a.exact(result, {"minimumHealthyPercent": 100, "maximumPercent": 200},
            "DEV deployment configuration")
    return result


def service(value):
    result = copy.deepcopy(value)
    result["deploymentConfiguration"] = deployment(result["deploymentConfiguration"])
    if "capacityProviderStrategy" not in result:
        a.require(result.get("launchType") == "FARGATE")
        result["capacityProviderStrategy"] = []
    a.exact(result["capacityProviderStrategy"], [], "DEV has no capacity provider strategy")
    return result


def observer(base):
    class Observer(base):
        def service(self, color):
            a.require(self.config["environment"] == "dev")
            observed, tasks, stable = super().service(color)
            result = service(observed)
            # Never turn LATEST into an invented numeric pin.
            return result, tasks, stable
    return Observer


# Derived ECS response metadata observed for this exact closed Fargate task.
ATTRIBUTES = frozenset((
    "com.amazonaws.ecs.capability.logging-driver.awslogs",
    "ecs.capability.execution-role-awslogs", "com.amazonaws.ecs.capability.ecr-auth",
    "com.amazonaws.ecs.capability.docker-remote-api.1.19",
    "ecs.capability.secrets.asm.environment-variables",
    "com.amazonaws.ecs.capability.docker-remote-api.1.21",
    "com.amazonaws.ecs.capability.task-iam-role", "ecs.capability.execution-role-ecr-pull",
    "com.amazonaws.ecs.capability.docker-remote-api.1.18", "ecs.capability.task-eni"))


def task_readback(value):
    result = copy.deepcopy(value)
    a.require(result.get("requiresCompatibilities") == ["FARGATE"])
    compatible = result.get("compatibilities")
    a.require(type(compatible) is list and len(compatible) == len(set(compatible))
              and set(compatible) == {"EC2", "FARGATE", "MANAGED_INSTANCES"})
    attributes = result.get("requiresAttributes")
    a.require(type(attributes) is list and len(attributes) == len(ATTRIBUTES)
              and all(type(v) is dict and set(v) == {"name"} for v in attributes)
              and {v["name"] for v in attributes} == ATTRIBUTES)
    # These fields describe inferred capabilities, not permitted launch types.
    # Explicit requiresCompatibilities and the complete task model stay checked.
    result["compatibilities"] = ["FARGATE"]
    result["requiresAttributes"] = []
    for container in result["containerDefinitions"]:
        for key, empty in (("cpu", 0), ("systemControls", [])):
            if key in container:
                a.exact(container.pop(key), empty, "DEV empty container default." + key)
    return result


def delivery(base):
    class Delivery(base):
        def effect(self, token, deadline):
            result = super().effect(token, deadline)
            # Only this still-running invocation's own persisted ACK permits
            # more observations. No ACK, crash/retry or foreign effect stays UNKNOWN.
            if result["state"] != "UNKNOWN" or token not in self.applied:
                return result
            end = min(deadline, self.now() + 600)
            while self.now() < end:
                time.sleep(2)
                if self.now() >= end:
                    break
                result = super().effect(token, end)
                if result["state"] != "UNKNOWN":
                    return result
            return result
    return Delivery
