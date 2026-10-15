"""DEV cleanup: scale-to-zero settles only after ECS and ALB deregistration.

Only the existing invocation's acknowledged scale effect may continue observing
within its original deadline. No new mutation, lease, journal or release port.
"""
import time
from scripts.normal_delivery import authorization as a


def application(base):
    class Application(base):
        def _drained(self, request):
            a.require(self.fixed["environment"] == "dev" and request["desiredCount"] == 0)
            color = next(c for c, m in self.fixed["colors"].items()
                         if m["cluster"] == request["cluster"] and m["service"] == request["service"])
            service, tasks, stable = self.observer.service(color)
            if not (stable and not tasks and service["desiredCount"] ==
                    service["runningCount"] == service["pendingCount"] == 0):
                return False
            response = self.elb.describe_target_health(
                TargetGroupArn=self.fixed["colors"][color]["target_group"])
            # Missing/malformed/error responses cannot prove absence.
            targets = response.get("TargetHealthDescriptions")
            a.require(type(targets) is list)
            return targets == []

        def mutate(self, stage, token, request, deadline):
            super().mutate(stage, token, request, deadline)
            if stage == "scale_zero":
                saved_request, result, _ = self.applied[token]
                self.applied[token] = (saved_request, result, lambda: self._drained(saved_request))
                self._drain_budget = (token, deadline)

        def verify_saved(self, token, request, result, deadline):
            verified = super().verify_saved(token, request, result, deadline)
            return verified and (not token.endswith("/scale_zero") or self._drained(request))

        def effect(self, token, deadline):
            budget = getattr(self, "_drain_budget", None)
            if budget is None or budget[0] != token or token not in self.applied:
                return super().effect(token, deadline)
            # Journal's per-observation 30s window is not the operation deadline.
            # Use only the original deadline saved by this acknowledged mutation.
            end = budget[1]
            unknown = {"token": token, "request_sha256": None, "state": "UNKNOWN", "result": None}
            while self.now() < end:
                result = super().effect(token, min(end, self.now() + 30))
                if result["state"] != "UNKNOWN":
                    return result
                if self.now() < end:
                    time.sleep(min(2, end - self.now()))
            return unknown
    return Application
