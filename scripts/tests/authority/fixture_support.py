"""Source fixtures for the closed-universe graph tests (never current authority)."""
import json
from evaluator import Decision
from coverage import ClosedUniverse


def write_universe(root, decisions):
    root.mkdir(parents=True, exist_ok=True)
    (root / "universe.json").write_text(json.dumps({"kind": "CLOSED_SYNTHETIC_UNIVERSE",
        "seeds": ["seed"], "subjects": ["fixture-role"], "mechanisms": list(decisions), "outcomes": ["out"]}))
    routes = []
    for name, decision in decisions.items():
        st = {"Effect": "Allow" if decision == Decision.ALLOW else "Deny", "Action": "s3:GetObject", "Resource": "*"}
        if decision == Decision.UNKNOWN:
            st["NotAction"] = "s3:DeleteObject"
        routes.append({"id": name, "mechanism": name, "target": "out", "prerequisites": ["seed"],
                       "subjects": ["fixture-role"], "request": {"action": "s3:GetObject", "resource": "arn:aws:s3:::fixture/key"},
                       "policies": {"identities": [{"Statement": [st]}]}})
    (root / "routes.json").write_text(json.dumps({"routes": routes}))
    return ClosedUniverse(root)
