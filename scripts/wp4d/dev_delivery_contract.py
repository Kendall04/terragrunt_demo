"""Owner-approved DEV compatibility only; installed in two exact DEV bundles.

The storage response, not an eligibility body, owns S3 VersionId. ECS defaults
are normalized only when their complete values are inert and understood.
"""
import copy
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
