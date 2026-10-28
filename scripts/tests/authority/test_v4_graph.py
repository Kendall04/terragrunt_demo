"""V4 positive witnesses and negative certificates from disposable source files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from coverage import ClosedUniverse
from evaluator import Decision as D, Unsupported
from graph import closure


def policy(effect="Allow"):
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": effect, "Action": "s3:GetObject", "Resource": "arn:aws:s3:::fixture/*"}]}


class V4WitnessTests(unittest.TestCase):
    def source(self, effects=("Allow", "Allow")):
        temp = tempfile.TemporaryDirectory(prefix="e1-v4-graph-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        universe = {"kind": "CLOSED_SYNTHETIC_UNIVERSE", "seeds": ["seed"],
                    "subjects": ["actor-a", "actor-b"], "mechanisms": ["direct", "delegated"], "outcomes": ["out"]}
        self.write(root, "universe.json", universe)
        routes = [{"id": str(i), "mechanism": ["direct", "delegated"][i], "target": "out",
                   "prerequisites": ["seed"], "subjects": ["actor-a" if i == 0 else "actor-b"],
                   "request": {"action": "s3:GetObject", "resource": "arn:aws:s3:::fixture/key"},
                   "policies": {"identities": [policy(effect)]}} for i, effect in enumerate(effects)]
        self.write(root, "routes.json", {"routes": routes})
        return root, routes

    def write(self, root, name, doc):
        (root / name).write_text(json.dumps(doc))

    def result(self, universe, certificate=None):
        return closure(universe.seeds, universe.rules, {"out": certificate} if certificate else {}, universe)

    def test_alternative_unknown_allow_does_not_erase_grounded_witness(self):
        root, routes = self.source()
        routes[1]["policies"]["identities"][0]["Statement"][0]["NotAction"] = "s3:DeleteObject"
        for order in (routes, list(reversed(routes))):
            self.write(root, "routes.json", {"routes": order})
            universe = ClosedUniverse(root)
            states, traces = self.result(universe)
            self.assertEqual(states["out"], D.ALLOW)
            self.assertEqual(traces["out"]["reason_codes"], ["WITNESS_ALLOW"])
            self.assertTrue(universe.unknown)
            with self.assertRaises(Unsupported):
                universe.certificate("out")

    def test_malformed_policy_in_other_principal_preserves_positive(self):
        root, routes = self.source()
        for bad in (False, {}, [{"Version": [], "Statement": []}]):
            routes[1]["policies"]["identities"] = bad
            self.write(root, "routes.json", {"routes": routes})
            universe = ClosedUniverse(root)
            self.assertEqual(self.result(universe)[0]["out"], D.ALLOW)
            with self.assertRaises(Unsupported):
                universe.certificate("out")

    def test_applicable_unknown_boundary_taints_only_affected_route(self):
        root, routes = self.source(("Allow", "Deny"))
        control = {"id": "boundary", "subjects": ["actor-a"], "policies": {"boundary": False}}
        self.write(root, "controls.json", {"controls": [control]})
        universe = ClosedUniverse(root)
        states, traces = self.result(universe)
        self.assertEqual(states["out"], D.UNKNOWN)
        self.assertIn("UNKNOWN_APPLICABLE_CONTROL", traces["out"]["reason_codes"])
        self.assertEqual(universe.rules[1].checks[0].decision, D.DENY)
        with self.assertRaises(Unsupported):
            universe.certificate("out")
        # The independent actor can still establish the same existential outcome.
        routes[1]["policies"]["identities"] = [policy()]
        self.write(root, "routes.json", {"routes": routes})
        self.assertEqual(self.result(ClosedUniverse(root))[0]["out"], D.ALLOW)

    def test_malformed_control_policy_container_keeps_admitted_subject_scope(self):
        root, routes = self.source()
        for policies in (False, [], {"not_a_policy_kind": [policy("Deny")]}):
            with self.subTest(policies=policies):
                self.write(root, "controls.json", {"controls": [{"id": "bad", "subjects": ["actor-b"],
                                                               "policies": policies}]})
                universe = ClosedUniverse(root)
                self.assertEqual(self.result(universe)[0]["out"], D.ALLOW)
                self.assertEqual([r.checks[0].decision for r in universe.rules], [D.ALLOW, D.UNKNOWN])
                self.assertFalse(universe.positive_taints())
                with self.assertRaises(Unsupported):
                    universe.certificate("out")
        # The same malformed container does control actor-a when selected.
        self.write(root, "controls.json", {"controls": [{"id": "bad", "subjects": ["actor-a", "actor-b"],
                                                       "policies": False}]})
        self.assertEqual(self.result(ClosedUniverse(root))[0]["out"], D.UNKNOWN)

    def test_same_physical_principal_cannot_escape_control_via_subject_alias(self):
        root, routes = self.source()
        principals = (
            ("arn:aws:iam::111122223333:role/path/shared", "arn:aws:iam::111122223333:role/path/shared"),
            ("arn:aws:iam::111122223333:role/path/shared", "arn:aws:sts::111122223333:assumed-role/shared/session"),
            ("arn:aws:sts::111122223333:assumed-role/shared/session", "arn:aws:sts::111122223333:assumed-role/shared/other"),
            ("ecs-tasks.amazonaws.com", "ecs-tasks.amazonaws.com"),
            ("arn:aws:iam::111122223333:oidc-provider/idp.example", "arn:aws:iam::111122223333:oidc-provider/idp.example"),
        )
        self.write(root, "controls.json", {"controls": [{"id": "deny", "subjects": ["actor-a"],
                                                       "policies": {"identities": [policy("Deny")]}}]})
        for pair in principals:
            for order in (routes, list(reversed(routes))):
                with self.subTest(principals=pair, order=[r["id"] for r in order]):
                    for route, principal in zip(routes, pair):
                        route["request"]["principal"] = principal
                    self.write(root, "routes.json", {"routes": order})
                    universe = ClosedUniverse(root)
                    self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)
                    self.assertTrue(any("conflicting subject aliases" in x["reason"] for x in universe.unknown))
                    with self.assertRaises(Unsupported):
                        universe.certificate("out")

    def test_subject_cannot_merge_different_or_symbolic_callers(self):
        root, routes = self.source()
        routes[1]["subjects"] = ["actor-a"]
        for first, second in (("arn:aws:iam::111122223333:role/shared", "arn:aws:iam::999999999999:role/shared"),
                              ("arn:aws:iam::111122223333:role/shared", "arn:aws:iam::111122223333:role/different"),
                              (None, "arn:aws:iam::111122223333:role/shared")):
            with self.subTest(first=first, second=second):
                for route, principal in zip(routes, (first, second)):
                    route["request"].pop("principal", None)
                    if principal:
                        route["request"]["principal"] = principal
                for order in (routes, list(reversed(routes))):
                    self.write(root, "routes.json", {"routes": order})
                    universe = ClosedUniverse(root)
                    self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)
                    with self.assertRaises(Unsupported):
                        universe.certificate("out")

    def test_consistent_role_and_session_binding_supports_shared_control_and_certificate(self):
        root, routes = self.source()
        routes[1]["subjects"] = ["actor-a"]
        routes[0]["request"]["principal"] = "arn:aws:iam::111122223333:role/team/shared"
        routes[1]["request"]["principal"] = "arn:aws:sts::111122223333:assumed-role/shared/session"
        self.write(root, "routes.json", {"routes": routes})
        universe = ClosedUniverse(root)
        self.assertEqual(self.result(universe)[0]["out"], D.ALLOW)
        self.assertTrue(all(r.checks[0].provenance[-1]["subject_binding"]["kind"] == "NORMALIZED_PRINCIPAL"
                            for r in universe.rules))
        self.write(root, "controls.json", {"controls": [{"id": "deny", "subjects": ["actor-a"],
                                                       "policies": {"identities": [policy("Deny")]}}]})
        universe = ClosedUniverse(root)
        self.assertFalse(universe.unknown)
        self.assertEqual(self.result(universe, universe.certificate("out"))[0]["out"], D.DENY)

    def test_shared_explicit_deny_is_evaluated_with_route_policies(self):
        root, _ = self.source()
        self.write(root, "controls.json", {"controls": [{"id": "shared-deny", "subjects": ["actor-a", "actor-b"],
                    "policies": {"identities": [policy("Deny")]}}]})
        universe = ClosedUniverse(root)
        self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)
        self.assertEqual(self.result(universe, universe.certificate("out"))[0]["out"], D.DENY)
        self.assertTrue(all(rule.checks[0].provenance[-1]["controls"] for rule in universe.rules))

    def test_global_unknown_control_taints_positive(self):
        root, _ = self.source()
        (root / "authority.tf.json").write_text('{"resource":{"aws_iam_role_policy":{"x":{}}}}')
        universe = ClosedUniverse(root)
        states, traces = self.result(universe)
        self.assertEqual(states["out"], D.UNKNOWN)
        self.assertEqual(traces["out"]["reason_codes"], ["UNKNOWN_APPLICABLE_CONTROL"])

    def test_complete_source_mutations_alternative_positive_then_negative(self):
        root, routes = self.source()
        universe = ClosedUniverse(root)
        self.assertEqual(self.result(universe, universe.certificate("out"))[0]["out"], D.ALLOW)
        routes[0]["policies"]["identities"] = [policy("Deny")]
        self.write(root, "routes.json", {"routes": routes})
        self.assertEqual(self.result(ClosedUniverse(root))[0]["out"], D.ALLOW)
        routes[1]["policies"]["identities"] = [policy("Deny")]
        self.write(root, "routes.json", {"routes": routes})
        universe = ClosedUniverse(root)
        self.assertEqual(self.result(universe, universe.certificate("out"))[0]["out"], D.DENY)

    def test_invalid_primitive_cannot_obtain_fresh_certificate(self):
        root, routes = self.source(("Deny", "Deny"))
        for version in ([], False, "2099-01-01"):
            changed = copy.deepcopy(routes)
            changed[0]["policies"]["identities"][0]["Version"] = version
            self.write(root, "routes.json", {"routes": changed})
            universe = ClosedUniverse(root)
            self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)
            with self.assertRaises(Unsupported):
                universe.certificate("out")

    def test_certificate_stale_after_primitive_admission_change(self):
        root, routes = self.source(("Deny", "Deny"))
        old = ClosedUniverse(root)
        certificate = old.certificate("out")
        routes[0]["policies"]["boundary"] = {}
        self.write(root, "routes.json", {"routes": routes})
        for universe in (old, ClosedUniverse(root)):
            self.assertEqual(self.result(universe, certificate)[0]["out"], D.UNKNOWN)
        routes[0]["policies"] = {"identities": [policy()]}
        self.write(root, "routes.json", {"routes": routes})
        self.assertEqual(self.result(ClosedUniverse(root), certificate)[0]["out"], D.ALLOW)

    def test_certificate_resource_topology_and_mechanism_replay(self):
        root, routes = self.source(("Deny", "Deny"))
        original = ClosedUniverse(root)
        certificate = original.certificate("out")
        for field, value in (("subjects", ["actor-b"]), ("prerequisites", ["out"]), ("mechanism", "unmodeled")):
            changed = copy.deepcopy(routes)
            changed[0][field] = value
            self.write(root, "routes.json", {"routes": changed})
            self.assertEqual(self.result(original, certificate)[0]["out"], D.UNKNOWN)
            self.assertEqual(self.result(ClosedUniverse(root), certificate)[0]["out"], D.UNKNOWN)

    def test_inert_source_preserves_complete_negative(self):
        root, _ = self.source(("Deny", "Deny"))
        universe = ClosedUniverse(root)
        certificate = universe.certificate("out")
        self.write(root, "note.json", {"kind": "LITERAL_OUTPUT", "value": "inert"})
        self.assertEqual(self.result(universe, certificate)[0]["out"], D.DENY)

    def test_conjunctive_prerequisites_and_ungrounded_cycles(self):
        root, routes = self.source(("Allow", "Deny"))
        manifest = json.loads((root / "universe.json").read_text())
        manifest["outcomes"].append("prerequisite")
        self.write(root, "universe.json", manifest)
        routes[0]["prerequisites"] = ["seed", "prerequisite"]
        routes[1]["target"] = "prerequisite"
        self.write(root, "routes.json", {"routes": routes})
        universe = ClosedUniverse(root)
        certs = {o: universe.certificate(o) for o in universe.outcomes}
        self.assertEqual(closure(universe.seeds, universe.rules, certs, universe)[0]["out"], D.DENY)
        routes[1]["policies"]["identities"] = [policy()]
        routes[1]["prerequisites"] = ["out"]
        self.write(root, "routes.json", {"routes": routes})
        universe = ClosedUniverse(root)
        self.assertEqual(self.result(universe)[0]["out"], D.UNKNOWN)

    def test_empty_or_ambiguous_subjects_do_not_certify(self):
        root, routes = self.source(("Deny", "Deny"))
        for subjects in ([], "actor-a", ["actor-a", "actor-a"]):
            routes[0]["subjects"] = subjects
            self.write(root, "routes.json", {"routes": routes})
            universe = ClosedUniverse(root)
            with self.assertRaises(Unsupported):
                universe.certificate("out")
