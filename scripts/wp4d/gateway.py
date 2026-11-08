"""Closed normal/emergency gateway; installed configuration owns project choice."""
import json


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("E1_WP4D_DUPLICATE_REQUEST_KEY")
        value[key] = item
    return value


def request(kind, event):
    if type(event) is not dict or set(event) != {"operation_id", "body"} or type(event["body"]) is not str:
        raise ValueError("E1_WP4D_REQUEST_REJECTED")
    from scripts.normal_delivery.delivery import identity
    identity(event["operation_id"])
    raw = event["body"].encode("utf-8")
    if len(raw) > 4096:
        raise ValueError("E1_WP4D_REQUEST_REJECTED")
    value = json.loads(raw, object_pairs_hook=_pairs)
    if type(value) is not dict:
        raise ValueError("E1_WP4D_REQUEST_REJECTED")
    if kind == "emergency":
        if value != {}:
            raise ValueError("E1_WP4D_REQUEST_REJECTED")
    elif kind == "normal":
        from scripts.normal_delivery import authorization as a
        from scripts.normal_delivery import delivery as d
        if set(value) not in ({"action", "release_id", "replicas"},
                              {"action", "release_id", "replicas", "reason"},
                              {"action", "history", "replicas"},
                              {"action", "history", "replicas", "reason"}):
            raise ValueError("E1_WP4D_REQUEST_REJECTED")
        # The protected controller remains the final authorizer. This gate only
        # closes the shape before allocating a durable operation identity.
        if value.get("action") == "deliver":
            a.request(a.canonical({k: v for k, v in value.items() if k != "action"}))
        elif value.get("action") == "rollback-release":
            d.identity(value["history"])
            if type(value["replicas"]) is not int or not 1 <= value["replicas"] <= 100:
                raise ValueError("E1_WP4D_REQUEST_REJECTED")
        else:
            raise ValueError("E1_WP4D_REQUEST_REJECTED")
    else:
        raise ValueError("E1_WP4D_REQUEST_REJECTED")
    return raw, value


def start(kind, event, config, operations, codebuild):
    """No StartBuild override is accepted or passed through from the request."""
    raw, value = request(kind, event)
    operation = event["operation_id"]
    payload = json.dumps({"operation": operation, "binding": config["binding"],
                          "request": value}, sort_keys=True, separators=(",", ":")).encode()
    key = "operations/" + operation + ".json"
    retained = operations.read(key)
    if retained is None:
        operations.create(key, payload)
        retained = operations.read(key)
    if retained is None or retained["bytes"] != payload:
        raise ValueError("E1_WP4D_OPERATION_REJECTED")
    attempt_key = "attempts/" + operation + ".json"
    started_key = "starts/" + operation + ".json"
    attempted = operations.read(attempt_key)
    if attempted is not None:
        if attempted["bytes"] != payload:
            raise ValueError("E1_WP4D_ATTEMPT_REJECTED")
        started = operations.read(started_key)
        if started is None:
            return {"operation": operation, "state": "UNCERTAIN"}
        recorded = json.loads(started["bytes"])
        build_id = recorded.get("build_id")
        bridge = operations.read("builds/" + build_id + ".json") if type(build_id) is str else None
        if bridge is None or json.loads(bridge["bytes"]) != {"operation": operation}:
            return {"operation": operation, "state": "UNCERTAIN"}
        return {"operation": operation, "state": "ACCEPTED"}
    operations.create(attempt_key, payload)
    attempted = operations.read(attempt_key)
    if attempted is None or attempted["bytes"] != payload:
        raise ValueError("E1_WP4D_ATTEMPT_REJECTED")
    response = codebuild.start_build(projectName=config["project"])
    build_id = response["build"]["id"]
    expected = config["project"] + ":"
    if type(build_id) is not str or not build_id.startswith(expected):
        raise ValueError("E1_WP4D_BUILD_ID_REJECTED")
    operations.create("builds/" + build_id + ".json",
                      json.dumps({"operation": operation}, sort_keys=True, separators=(",", ":")).encode())
    operations.create(started_key,
                      json.dumps({"build_id": build_id}, sort_keys=True, separators=(",", ":")).encode())
    return {"operation": operation, "state": "ACCEPTED"}
