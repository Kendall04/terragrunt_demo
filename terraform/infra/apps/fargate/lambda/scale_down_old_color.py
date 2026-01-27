import os
import logging

import boto3

log = logging.getLogger()
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))

ecs = boto3.client("ecs")
elbv2 = boto3.client("elbv2")
events = boto3.client("events")

CLUSTER = os.environ["CLUSTER_ARN"]
SERVICE_BLUE = os.environ["SERVICE_BLUE_NAME"]
SERVICE_GREEN = os.environ["SERVICE_GREEN_NAME"]
LISTENER_ARN = os.environ["LISTENER_ARN"]
TG_BLUE_ARN = os.environ["TG_BLUE_ARN"]
TG_GREEN_ARN = os.environ["TG_GREEN_ARN"]
EVENT_RULE_NAME = os.getenv("EVENT_RULE_NAME")


def _get_default_tg_arn(listener_arn: str) -> str | None:
    """Return the TargetGroupArn used in the ALB listener default action."""
    resp = elbv2.describe_listeners(ListenerArns=[listener_arn])
    listener = resp["Listeners"][0]
    default_actions = listener.get("DefaultActions", [])

    if not default_actions:
        log.warning("Listener %s has no DefaultActions", listener_arn)
        return None

    default = default_actions[0]

    # Case 1: simple forward
    tg_arn = default.get("TargetGroupArn")
    if tg_arn:
        return tg_arn

    # Case 2: ForwardConfig with multiple target groups
    fwd_cfg = default.get("ForwardConfig", {})
    tgs = fwd_cfg.get("TargetGroups") or []
    if tgs:
        return tgs[0].get("TargetGroupArn")

    log.warning("Listener %s default action has no TargetGroupArn", listener_arn)
    return None


def _cleanup_event_rule() -> None:
    """Best-effort cleanup of the EventBridge rule that triggered this Lambda."""
    if not EVENT_RULE_NAME:
        log.info("EVENT_RULE_NAME not set; skipping EventBridge cleanup.")
        return

    log.info("Cleaning up EventBridge rule %s", EVENT_RULE_NAME)

    try:
        events.remove_targets(Rule=EVENT_RULE_NAME, Ids=["scale-down"])
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to remove targets for rule %s: %s", EVENT_RULE_NAME, e)

    try:
        events.delete_rule(Name=EVENT_RULE_NAME)
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to delete rule %s: %s", EVENT_RULE_NAME, e)


def lambda_handler(event, context):
    log.info("Received event: %s", event)

    # 1) Determine which TG is active on the listener
    default_tg = _get_default_tg_arn(LISTENER_ARN)
    if not default_tg:
        return {"status": "no_default_tg"}

    log.info("Default target group on listener: %s", default_tg)

    if default_tg == TG_BLUE_ARN:
        active_service = SERVICE_BLUE
        inactive_service = SERVICE_GREEN
    elif default_tg == TG_GREEN_ARN:
        active_service = SERVICE_GREEN
        inactive_service = SERVICE_BLUE
    else:
        log.warning(
            "Default TG %s is neither BLUE (%s) nor GREEN (%s). "
            "Aborting scale-down.",
            default_tg,
            TG_BLUE_ARN,
            TG_GREEN_ARN,
        )
        return {"status": "unknown_default_tg"}

    log.info("Active service  : %s", active_service)
    log.info("Inactive service: %s", inactive_service)

    # 2) Describe both services (for safety & logging)
    desc = ecs.describe_services(
        cluster=CLUSTER,
        services=[SERVICE_BLUE, SERVICE_GREEN],
    )
    services_by_name = {s["serviceName"]: s for s in desc.get("services", [])}

    def svc_state(name: str):
        s = services_by_name.get(name)
        if not s:
            return None, None
        return s.get("desiredCount", 0), s.get("runningCount", 0)

    desired_active, running_active = svc_state(active_service)
    desired_inactive, running_inactive = svc_state(inactive_service)

    log.info(
        "Active   %s -> desired=%s running=%s",
        active_service,
        desired_active,
        running_active,
    )
    log.info(
        "Inactive %s -> desired=%s running=%s",
        inactive_service,
        desired_inactive,
        running_inactive,
    )

    if desired_inactive is None:
        log.warning("Inactive ECS service %s not found. Aborting.", inactive_service)
        return {"status": "inactive_service_not_found"}

    # 3) If inactive already at 0, nothing to do (idempotent)
    if (desired_inactive or 0) == 0 and (running_inactive or 0) == 0:
        log.info(
            "Inactive service %s is already scaled down to 0. Nothing to do.",
            inactive_service,
        )
        _cleanup_event_rule()
        return {"status": "already_zero"}

    # 4) Safety check: ensure active service actually has tasks
    if (desired_active or 0) == 0 or (running_active or 0) == 0:
        log.warning(
            "Active service %s has no desired/running tasks. "
            "Refusing to scale down %s for safety.",
            active_service,
            inactive_service,
        )
        return {"status": "active_not_healthy"}

    # 5) Scale down inactive service
    log.info("Scaling down inactive service %s to desiredCount=0", inactive_service)
    ecs.update_service(
        cluster=CLUSTER,
        service=inactive_service,
        desiredCount=0,
    )

    log.info("Successfully scaled down %s", inactive_service)

    _cleanup_event_rule()

    return {
        "status": "scaled_down",
        "active_service": active_service,
        "inactive_service": inactive_service,
    }
