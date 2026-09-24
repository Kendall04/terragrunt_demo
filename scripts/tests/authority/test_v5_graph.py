"""V5 route scope and validity dimensions through source-bound universes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from coverage import ClosedUniverse
from evaluator import Decision as D, Unsupported
from graph import VALIDITY_AXES, baseline, closure


ROOT = Path(__file__).resolve().parents[3]


def route(name, subject, account, effect="Allow"):
    return {"id": name, "mechanism": "direct", "target": "out", "prerequisites": ["seed"],
            "subjects": [subject], "request": {"action": "s3:GetObject",
                "resource": "arn:aws:s3:::review-routes/key",
                "principal": "arn:aws:iam::" + account + ":role/review/Reader"},
            "policies": {"identities": [{"Statement": [{"Effect": effect, "Action": "s3:GetObject",
                                                        "Resource": "arn:aws:s3:::review-routes/*"}]}]}}


class V5RouteUncertaintyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="e1-v5-routes-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.manifest = {"kind": "CLOSED_SYNTHETIC_UNIVERSE", "seeds": ["seed"],
                         "subjects": ["actor-a", "actor-b"], "mechanisms": ["direct"],
                         "outcomes": ["out", "prerequisite"]}
        self.routes = [route("grounded", "actor-a", "111122223333"),
                       route("alternative", "actor-b", "444455556666")]

    def source(self, controls=()):
        for name, doc in (("universe.json", self.manifest), ("routes.json", {"routes": self.routes}),
                          ("controls.json", {"controls": list(controls)})):
            (self.root / name).write_text(json.dumps(doc))
        return ClosedUniverse(self.root)

    def result(self, universe, complete=False):
        coverage = {o: universe.certificate(o) for o in universe.outcomes} if complete else {}
        return closure(universe.seeds, universe.rules, coverage, universe)

    def test_unknown_mechanism_different_principal_preserves_independent_witness(self):
        self.routes[1]["mechanism"] = "fresh-independent-alternative"
        for order in (self.routes[:], list(reversed(self.routes))):
            self.routes = order
            universe = self.source()
            states, traces = self.result(universe)
            self.assertEqual(states["out"], D.ALLOW)
            self.assertEqual(traces["out"]["route"], "grounded")
            self.assertFalse(universe.positive_taints())
            self.assertEqual({x["scope"] for x in universe.unknown}, {"UNKNOWN_ROUTE_ALTERNATIVE"})
            axes = traces["out"]["evidence_validity"]
            self.assertEqual(set(axes), set(VALIDITY_AXES))
            self.assertTrue(all(axes[a] == "SUPPORTED" for a in VALIDITY_AXES[:-1]), axes)
            self.assertEqual(axes["NEGATIVE_COMPLETENESS"], "NOT_PROVEN")
            with self.assertRaises(Unsupported):
                universe.certificate("out")

    def test_same_subject_unknown_allow_only_alternative_preserves_witness(self):
        self.routes[1] = copy.deepcopy(self.routes[0])
        self.routes[1].update(id="other-allow", mechanism="unknown-additional-allow")
        universe = self.source()
        self.assertEqual(self.result(universe)[0]["out"], D.ALLOW)
        self.assertEqual(universe.rules[1].checks[0].decision, D.UNKNOWN)
        with self.assertRaises(Unsupported):
            universe.certificate("out")

    def test_unknown_shared_control_cannot_hide_inside_an_alternative(self):
        self.routes[1]["mechanism"] = "unknown-alternative"
        control = {"id": "shared-boundary-mutation", "subjects": ["actor-a", "actor-b"],
                   "mechanism": "unsupported-boundary-mutation", "policies": {"boundary": False}}
        universe = self.source([control])
        states, traces = self.result(universe)
        self.assertEqual(states["out"], D.UNKNOWN)
        self.assertIn("UNKNOWN_APPLICABLE_CONTROL", traces["out"]["reason_codes"])
        self.assertTrue(any(x["scope"] == "UNKNOWN_SUBJECT_CONTROL" for x in universe.unknown))
        self.assertEqual(traces["out"]["evidence_validity"]["ADMISSION"], "UNKNOWN")
        with self.assertRaises(Unsupported):
            universe.certificate("out")

    def test_unknown_prerequisite_invalidates_only_dependent_witness(self):
        self.routes[0]["prerequisites"].append("prerequisite")
        self.routes[1].update(target="prerequisite", mechanism="unknown-prerequisite-mechanism")
        universe = self.source()
        states, traces = self.result(universe)
        self.assertEqual(states["prerequisite"], D.UNKNOWN)
        self.assertEqual(states["out"], D.UNKNOWN)
        self.assertEqual(traces["out"]["evidence_validity"]["ADMISSION"], "UNKNOWN")
        self.assertIn({"scope": "UNKNOWN_ROUTE_PREREQUISITE", "prerequisite": "prerequisite",
                       "route": "grounded"}, traces["out"]["alternatives"][0]["applicable_unknown"])
        self.routes.append(route("independent", "actor-a", "111122223333"))
        self.assertEqual(self.result(self.source())[0]["out"], D.ALLOW)

    def test_disjoint_unknown_subject_control_does_not_erase_witness(self):
        control = {"id": "other-boundary", "subjects": ["actor-b"], "policies": {"boundary": False}}
        universe = self.source([control])
        states, traces = self.result(universe)
        self.assertEqual(states["out"], D.ALLOW)
        self.assertEqual(traces["out"]["evidence_validity"]["ADMISSION"], "SUPPORTED")
        self.assertEqual([r.checks[0].decision for r in universe.rules], [D.ALLOW, D.UNKNOWN])
        with self.assertRaises(Unsupported):
            universe.certificate("out")

    def test_global_unclassified_source_remains_a_control(self):
        universe = self.source()
        self.assertEqual(self.result(universe)[0]["out"], D.ALLOW)
        (self.root / "unclassified.tf").write_text('resource "aws_iam_policy" "unknown" {}')
        universe = ClosedUniverse(self.root)
        states, traces = self.result(universe)
        self.assertEqual(states["out"], D.UNKNOWN)
        self.assertEqual(traces["out"]["applicable_unknown"][0]["scope"], "UNKNOWN_GLOBAL_CONTROL")
        self.assertEqual(traces["out"]["evidence_validity"]["APPLICABILITY"], "UNKNOWN")

    def test_complete_denial_remains_source_bound_with_all_validity_axes(self):
        for candidate in self.routes:
            candidate["policies"]["identities"] = []
        universe = self.source()
        states, traces = self.result(universe, complete=True)
        self.assertEqual(states["out"], D.DENY)
        axes = traces["out"]["evidence_validity"]
        self.assertEqual(set(axes), set(VALIDITY_AXES))
        self.assertTrue(all(axes[a] == "SUPPORTED" for a in VALIDITY_AXES[:4]), axes)
        self.assertEqual(axes["NEGATIVE_COMPLETENESS"], "SUPPORTED")
        certificate = universe.certificate("out")
        self.routes[1]["mechanism"] = "new-possible-authority"
        changed = self.source()
        self.assertFalse(changed.validates(certificate, "out", changed.seeds, changed.rules))
        self.assertEqual(self.result(changed)[0]["out"], D.UNKNOWN)
        with self.assertRaises(Unsupported):
            changed.certificate("out")

    def test_certificate_refuses_semantically_invalid_deny_primitive(self):
        self.routes = [route("invalid-deny", "actor-a", "111122223333", "Deny")]
        self.routes[0]["policies"]["identities"][0]["Statement"][0]["Resource"] = [
            "arn:aws:s3:::review-routes/*", "arn:aws:s?:::review-routes/key"]
        universe = self.source()
        self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)
        with self.assertRaises(Unsupported):
            universe.certificate("out")

    def test_current_witness_trace_keeps_validity_dimensions_separate(self):
        for record in baseline(ROOT):
            for name in ("delivery:runtime", "infra:stronger-workload-compute", "legacy:combined-publish-route"):
                trace = record["traces"][name]
                self.assertEqual(trace["reason_codes"], ["WITNESS_ALLOW"])
                self.assertEqual(set(trace["evidence_validity"]), set(VALIDITY_AXES))
                self.assertEqual(trace["evidence_validity"]["NEGATIVE_COMPLETENESS"], "NOT_PROVEN")
                self.assertTrue(all(trace["evidence_validity"][a] == "SUPPORTED" for a in VALIDITY_AXES[:-1]),
                                (name, trace["evidence_validity"]))


if __name__ == "__main__":
    unittest.main()
