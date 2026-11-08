"""DEV startup waits for ECS steady state; E3 failures expose fixed codes only."""
from scripts.normal_delivery import authorization as a


def delivery(base):
    class Delivery(base):
        def _service_matches(self, request):
            a.require(self.config["environment"] == "dev")
            color = next((c for c, m in self.config["colors"].items()
                          if m["service"] == request["service"] and m["cluster"] == request["cluster"]), None)
            a.require(color is not None)
            service, tasks, stable = self.observer.service(color)
            return (stable and service["desiredCount"] == service["runningCount"] == request["desiredCount"]
                    and service["pendingCount"] == 0 and
                    ("taskDefinition" not in request or service["taskDefinition"] == request["taskDefinition"]))
    return Delivery


def diagnostic(output):
    # Do not publish stderr, SDK responses, task values or arbitrary child output.
    for text, code in (
            (b"Candidate service changed within an evidence observation.", "SERVICE_CHANGED_DURING_E3_READ"),
            (b"Complete readiness evidence changed between observations.", "COMPLETE_E3_EVIDENCE_CHANGED"),
            (b"Completed probe lacks required task, container, image, network identity.", "PROBE_IDENTITY_INCOMPLETE"),
            (b"Candidate task, container, image, network, or startup identity is invalid.", "TASK_IDENTITY_REJECTED"),
            (b"Final readiness identity changed before traffic switching.", "FINAL_E3_IDENTITY_CHANGED")):
        if text in output:
            return "E1_DEV_E3_" + code
    return "E1_DEV_E3_UNCLASSIFIED_REJECTION"
