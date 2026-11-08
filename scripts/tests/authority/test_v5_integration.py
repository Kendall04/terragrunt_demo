"""V5 cross-layer transitions use fresh source files, never patched decisions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from coverage import ClosedUniverse
from evaluator import Decision as D, Unsupported, evaluate
from graph import baseline, closure


ROOT = Path(__file__).resolve().parents[3]
ROLE = "arn:aws:iam::111122223333:role/review/Reader"
SESSION = "arn:aws:sts::111122223333:assumed-role/Reader/review-session"


def route(name, grants=True):
    return {"id": name, "mechanism": "read", "target": "out", "prerequisites": ["seed"],
            "subjects": ["reader"], "request": {"action": "s3:GetObject",
                "resource": "arn:aws:s3:::review-fixture/key", "principal": SESSION, "role_arn": ROLE},
            "policies": {"identities": [{"Statement": [{"Effect": "Allow", "Action": "s3:GetObject",
                                                        "Resource": "arn:aws:s3:::review-fixture/*"}]}] if grants else []}}


class V5MutationMatrixTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="e1-v5-matrix-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "universe.json").write_text(json.dumps({"kind": "CLOSED_SYNTHETIC_UNIVERSE",
            "seeds": ["seed"], "subjects": ["reader"], "mechanisms": ["read"], "outcomes": ["out"]}))

    def source(self, routes, controls=()):
        (self.root / "routes.json").write_text(json.dumps({"routes": routes}))
        (self.root / "controls.json").write_text(json.dumps({"controls": list(controls)}))
        return ClosedUniverse(self.root)

    def state(self, universe, complete=False):
        coverage = {"out": universe.certificate("out")} if complete else None
        return closure(universe.seeds, universe.rules, coverage, universe)[0]["out"]

    def test_allow_survives_independent_route_then_valid_removal_proves_deny(self):
        first, second = route("first"), route("second")
        self.assertEqual(self.state(self.source([first, second])), D.ALLOW)
        first["policies"]["identities"] = []
        self.assertEqual(self.state(self.source([first, second])), D.ALLOW)
        second["policies"]["identities"] = []
        closed = self.source([first, second])
        self.assertEqual(self.state(closed), D.UNKNOWN)
        self.assertEqual(self.state(closed, complete=True), D.DENY)

    def test_new_possible_then_admitted_authority_invalidates_negative_certificate(self):
        denied = route("empty", False)
        old = self.source([denied])
        certificate = old.certificate("out")
        self.assertEqual(self.state(old, complete=True), D.DENY)
        possible = route("new")
        possible["mechanism"] = "not-yet-admitted-alternative"
        unknown = self.source([denied, possible])
        self.assertEqual(self.state(unknown), D.UNKNOWN)
        self.assertFalse(unknown.validates(certificate, "out", unknown.seeds, unknown.rules))
        with self.assertRaises(Unsupported):
            unknown.certificate("out")
        possible["mechanism"] = "read"
        admitted = self.source([denied, possible])
        self.assertEqual(self.state(admitted), D.ALLOW)
        self.assertFalse(admitted.validates(certificate, "out", admitted.seeds, admitted.rules))

    def test_allow_to_unknown_with_shared_boundary_then_complete_restrictive_boundary(self):
        allowed = route("allowed")
        self.assertEqual(self.state(self.source([allowed])), D.ALLOW)
        control = {"id": "ceiling", "subjects": ["reader"], "policies": {"boundary": {}}}
        uncertain = self.source([allowed], [control])
        self.assertEqual(self.state(uncertain), D.UNKNOWN)
        with self.assertRaises(Unsupported):
            uncertain.certificate("out")
        control["policies"]["boundary"] = []
        self.assertEqual(self.state(self.source([allowed], [control]), complete=True), D.DENY)

    def test_invalid_resource_list_member_cannot_certify_either_effect(self):
        for effect in ("Allow", "Deny"):
            with self.subTest(effect=effect):
                invalid = route("invalid")
                statement = invalid["policies"]["identities"][0]["Statement"][0]
                statement.update(Effect=effect, Resource=[statement["Resource"], "arn:aws:s?:::review-fixture/*"])
                universe = self.source([invalid])
                self.assertEqual(universe.rules[0].checks[0].decision, D.UNKNOWN)
                self.assertEqual(self.state(universe), D.UNKNOWN)
                with self.assertRaises(Unsupported):
                    universe.certificate("out")

    def test_forged_authoritative_fact_cannot_supply_positive_or_negative_evidence(self):
        candidate = route("conditional")
        statement = candidate["policies"]["identities"][0]["Statement"][0]
        statement["Condition"] = {"Bool": {"aws:PrincipalIsAWSService": "false"}}
        self.assertEqual(self.state(self.source([candidate])), D.ALLOW)
        candidate["request"]["context"] = {"AWS:PrincipalIsAWSService": "true"}
        universe = self.source([candidate])
        self.assertEqual(self.state(universe), D.UNKNOWN)
        with self.assertRaises(Unsupported):
            universe.certificate("out")
        candidate["request"]["context"] = {"aws:PrincipalIsAWSService": "false"}
        self.assertEqual(self.state(self.source([candidate])), D.ALLOW)

    def test_new_unclassified_source_breaks_completeness_inert_source_does_not(self):
        universe = self.source([route("empty", False)])
        certificate = universe.certificate("out")
        (self.root / "metadata.json").write_text(json.dumps({"kind": "LITERAL_OUTPUT", "value": "review metadata"}))
        inert = ClosedUniverse(self.root)
        self.assertTrue(inert.validates(certificate, "out", inert.seeds, inert.rules))
        (self.root / "new-module.tf.json").write_text(json.dumps({"module": {"unknown": {"source": "./new"}}}))
        changed = ClosedUniverse(self.root)
        self.assertFalse(changed.validates(certificate, "out", changed.seeds, changed.rules))
        self.assertEqual(self.state(changed), D.UNKNOWN)
        with self.assertRaises(Unsupported):
            changed.certificate("out")


class V5PositiveControlTests(unittest.TestCase):
    def test_read_and_service_trust_require_actual_positive_primitives(self):
        candidate = route("read")
        request, policies = candidate["request"], candidate["policies"]["identities"]
        self.assertEqual(evaluate(request, identities=policies).decision, D.ALLOW)
        self.assertEqual(evaluate(request, identities=[]).decision, D.DENY)
        invalid = copy.deepcopy(policies)
        invalid[0]["Statement"][0]["NotAction"] = "s3:DeleteObject"
        self.assertEqual(evaluate(request, identities=invalid).decision, D.UNKNOWN)
        service_request = {"action": "sts:AssumeRole", "resource": ROLE, "principal": "ecs-tasks.amazonaws.com"}
        trust = {"Statement": {"Effect": "Allow", "Action": "sts:AssumeRole",
                               "Principal": {"Service": "ecs-tasks.amazonaws.com"}}}
        self.assertEqual(evaluate(service_request, trust=[trust]).decision, D.ALLOW)
        self.assertEqual(evaluate(service_request, trust=[]).decision, D.DENY)

    def test_current_witnesses_stay_partial_and_are_not_execution_claims(self):
        for record in baseline(ROOT):
            with self.subTest(environment=record["environment"]):
                for target in ("acquire:github_terragrunt_cd", "acquire:github_terragrunt_ci",
                               "infra:broaden-role", "infra:stronger-workload-compute", "delivery:runtime",
                               "delivery:role-field-substitution", "github_app_rollback:direct-routing",
                               "legacy:combined-publish-route", "legacy:prod-record-write"):
                    self.assertEqual(record["outcomes"][target]["verdict"], "WITNESS_ALLOW")
                    self.assertEqual(record["outcomes"][target]["coverage"]["status"], "PARTIAL")
                self.assertEqual(record["dev_approval_to_high_risk"], "ALLOW")
                self.assertEqual(record["evidence_type"], "REPOSITORY_MODEL_REACHABILITY_NOT_EXECUTED_EXPLOIT")


if __name__ == "__main__":
    unittest.main()
