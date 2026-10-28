"""V4 kind admission and normalized facts through production evaluators/sources.

Permutations deliberately combine malformed nonmatching statements with an
otherwise conclusive Allow/Deny. Source and certificate probes use disposable
inputs, never detached expected graph decisions.
"""
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from coverage import ClosedUniverse
from evaluator import Decision as D, PolicyKind, Unsupported, admit_policy, evaluate
from fixture_support import write_universe
from graph import baseline, closure
import test_v3


ACCOUNT = "111122223333"
ROLE = "arn:aws:iam::111122223333:role/team/caller"
SESSION = "arn:aws:sts::111122223333:assumed-role/caller/session+=,.@_-"
QUEUE = "arn:aws:sqs:us-east-1:111122223333:queue"
PROVIDER = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"
REQUEST = {"action": "sqs:SendMessage", "resource": QUEUE, "principal": SESSION, "role_arn": ROLE}


def policy(effect="Allow", **extra):
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": effect, "Action": "sqs:SendMessage", "Resource": QUEUE, **extra}]}


def trust(category="Service", principal="ecs-tasks.amazonaws.com", action="sts:AssumeRole", **extra):
    return {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": action, "Principal": {category: principal}, **extra}]}


class V4PolicyKindTests(unittest.TestCase):
    def assert_admission_unknown(self, result):
        self.assertEqual(result.decision, D.UNKNOWN)
        self.assertTrue(any("SEMANTIC_ADMISSION_UNKNOWN" in reason for reason in result.reasons), result)
        self.assertTrue(any(x["admission"] == "ADMISSION_FAILURE"
                            for x in result.provenance[0]["policy_admission"]))

    def test_version_wrong_type_and_unsupported_version_all_kinds(self):
        for version in ([], {}, False, 20121017, None, "", "2099-01-01", "2008-10-17"):
            for kind in PolicyKind:
                doc = trust() if kind == PolicyKind.TRUST_POLICY else policy()
                if kind == PolicyKind.RESOURCE_POLICY:
                    doc["Statement"][0]["Principal"] = {"AWS": SESSION}
                doc["Version"] = version
                with self.subTest(version=version, kind=kind), self.assertRaises(Unsupported):
                    admit_policy(doc, kind)
                arg = {PolicyKind.IDENTITY_POLICY: "identities", PolicyKind.RESOURCE_POLICY: "resources",
                       PolicyKind.TRUST_POLICY: "trust", PolicyKind.PERMISSIONS_BOUNDARY: "boundary"}[kind]
                self.assert_admission_unknown(evaluate(REQUEST, **{arg: [doc]}))

    def test_statement_and_document_envelopes_cannot_be_empty_or_coerced(self):
        for doc in (False, [], None, "policy", {}, {"Statement": False}, {"Statement": {}},
                    {"Statement": []}, {"Statement": None}, {"Statement": [None]},
                    policy() | {"Unexpected": "ignored?"}, policy() | {"Id": []}):
            with self.subTest(doc=doc):
                self.assert_admission_unknown(evaluate(REQUEST, identities=[doc]))

    def test_every_policy_container_has_explicit_type(self):
        for kind in ("identities", "resources", "boundary", "trust"):
            for container in (False, {}, "", 0, policy()):
                with self.subTest(kind=kind, container=container):
                    self.assert_admission_unknown(evaluate(REQUEST, **{kind: container}))
        self.assertEqual(evaluate(REQUEST, identities=[policy()], boundary=[]).decision, D.DENY)
        self.assertEqual(evaluate(REQUEST, identities=[policy()], boundary=None).decision, D.ALLOW)

    def test_document_kind_rejects_disallowed_statement_members(self):
        for kind in ("identities", "boundary"):
            self.assert_admission_unknown(evaluate(REQUEST, **{kind: [policy(Principal={"AWS": ROLE})]}))
        for resource in ("*", QUEUE, ["*"]):
            self.assert_admission_unknown(evaluate(REQUEST, trust=[trust(Resource=resource)]))
        for extra in ({"NotAction": "sqs:DeleteMessage"}, {"NotResource": "*"},
                      {"NotPrincipal": {"AWS": ROLE}}):
            self.assert_admission_unknown(evaluate(REQUEST, identities=[policy(**extra)]))

    def test_malformed_action_resource_effect_and_principal_shapes(self):
        bad_values = ([], ["sqs:SendMessage", None], False, {}, "", [7])
        for field in ("Action", "Resource"):
            for value in bad_values:
                self.assert_admission_unknown(evaluate(REQUEST, identities=[policy(**{field: value})]))
        for effect in (None, False, [], "allow", "ALLOW"):
            self.assert_admission_unknown(evaluate(REQUEST, identities=[policy(effect)]))
        for value in ({}, [], "*", {"AWS": []}, {"AWS": ROLE, "Service": "ecs-tasks.amazonaws.com"},
                      {"AWS": [SESSION, {}]}, {"Service": "ecs-tasks.amazonaws.com"}):
            self.assert_admission_unknown(evaluate(REQUEST, resources=[policy(Principal=value)]))

    def test_novel_malformed_arn_and_action_operands(self):
        for value in ("arn:aws:sqs:us east-1:111122223333:queue", "arn:aws:sqs:us-east-1:x:queue",
                      "arn:aws:sqs:us-east-1:111122223333:", "arn::sqs:us-east-1:111122223333:queue",
                      "arn:aws-cn:sqs:cn-north-1:111122223333:queue", "arn:aws:sqs:us-east-1:123:queue"):
            self.assert_admission_unknown(evaluate(REQUEST, identities=[policy(Resource=value)]))
        for value in ("sqs:", "sqs:Send Message", "*:SendMessage", ":SendMessage", "sqs:SendMessage:extra"):
            self.assert_admission_unknown(evaluate(REQUEST, identities=[policy(Action=value)]))

    def test_unsupported_and_ambiguous_statement_identifiers(self):
        for doc in (policy(Sid="ambiguous sid"), policy() | {"Id": "unsupported-on-identity"},
                    {"Statement": [policy(Sid="Same")["Statement"][0], policy("Deny", Sid="Same")["Statement"][0]]}):
            self.assert_admission_unknown(evaluate(REQUEST, identities=[doc]))

    def test_bool_and_null_cardinality_type_complete_admission(self):
        for operator in ("Bool", "BoolIfExists", "ForAnyValue:Bool", "Null"):
            for values in (["true", "false"], ["true", "true"], [True], [], False, {"true": "false"}):
                self.assert_admission_unknown(evaluate(REQUEST, identities=[
                    policy(Condition={operator: {"aws:SecureTransport": values}})]))
        for value in ("true", ["true"]):
            result = evaluate(REQUEST | {"context": {"aws:SecureTransport": "true"}},
                              identities=[policy(Condition={"Bool": {"aws:SecureTransport": value}})])
            self.assertEqual(result.decision, D.ALLOW)

    def test_nonmatching_and_reordered_statements_cannot_hide_admission_failure(self):
        malformed = policy(Action="sqs:DeleteMessage", Condition={"Bool": {"fixture:k": ["true", "false"]}})["Statement"][0]
        for effect in ("Allow", "Deny"):
            for statements in itertools.permutations([policy(effect)["Statement"][0], malformed]):
                self.assert_admission_unknown(evaluate(REQUEST, identities=[{"Statement": list(statements)}]))
                for documents in itertools.permutations([policy(effect), {"Statement": malformed}]):
                    self.assert_admission_unknown(evaluate(REQUEST, identities=list(documents)))

    def test_trust_principal_action_compatibility_entire_list(self):
        pairs = [("AWS", ROLE, "sts:AssumeRole"), ("Service", "ecs-tasks.amazonaws.com", "sts:AssumeRole"),
                 ("Federated", PROVIDER, "sts:AssumeRoleWithWebIdentity")]
        for category, principal, action in pairs:
            request = {"action": action, "resource": ROLE, "principal": principal}
            self.assertEqual(evaluate(request, trust=[trust(category, principal, action)]).decision, D.ALLOW)
            for bad_action in ("sts:GetCallerIdentity", "sts:AssumeRoleWithSAML",
                               "sts:AssumeRole" if category == "Federated" else "sts:AssumeRoleWithWebIdentity"):
                for actions in ([action, bad_action], [bad_action, action], bad_action):
                    self.assert_admission_unknown(evaluate(request, trust=[trust(category, principal, actions)]))

    def test_equivalent_scalar_list_and_singleton_statement_positives(self):
        for action, resource in itertools.product(("sqs:SendMessage", ["sqs:SendMessage"]), (QUEUE, [QUEUE])):
            doc = policy(Action=action, Resource=resource)
            for singleton in (False, True):
                candidate = copy.deepcopy(doc)
                if singleton:
                    candidate["Statement"] = candidate["Statement"][0]
                self.assertEqual(evaluate(REQUEST, identities=[candidate], boundary=[candidate]).decision, D.ALLOW)
                resource_doc = copy.deepcopy(candidate)
                statement = resource_doc["Statement"] if singleton else resource_doc["Statement"][0]
                statement["Principal"] = {"AWS": SESSION}
                self.assertEqual(evaluate(REQUEST, resources=[resource_doc]).decision, D.ALLOW)

    def test_admission_and_fact_provenance_is_present_on_definitive_result(self):
        result = evaluate(REQUEST, identities=[policy()], boundary=[policy()])
        self.assertEqual(result.decision, D.ALLOW)
        record = result.provenance[0]
        self.assertEqual(record["normalized_request"]["identity"]["role_arn"], ROLE)
        kinds = {x["document_kind"] for x in record["policy_admission"]}
        self.assertIn("IDENTITY_POLICY", kinds)
        self.assertIn("PERMISSIONS_BOUNDARY", kinds)
        self.assertTrue(all(x["admission"] == "SUPPORTED_AND_MODELED" for x in record["policy_admission"]))
        self.assertEqual(record["applicable_unknown"], [])


class V4IdentityFactTests(unittest.TestCase):
    def test_principal_context_contradictions_cannot_allow_or_deny(self):
        wrong = {"aws:PrincipalArn": ROLE.replace(ACCOUNT, "999999999999"),
                 "aws:PrincipalAccount": "999999999999", "aws:PrincipalType": "User"}
        for key, value in wrong.items():
            for supplied in (value, [value]):
                for effect in ("Allow", "Deny"):
                    result = evaluate(REQUEST | {"context": {key: supplied}}, identities=[policy(effect,
                                      Condition={"StringEquals": {key: value}})])
                    self.assertEqual(result.decision, D.UNKNOWN)
                    self.assertIn("INVALID_IDENTITY", " ".join(result.reasons))

    def test_valid_derived_and_matching_explicit_global_facts(self):
        facts = {"aws:PrincipalArn": ROLE, "aws:PrincipalAccount": ACCOUNT, "aws:PrincipalType": "AssumedRole"}
        doc = policy(Condition={"StringEquals": facts})
        for context in ({}, facts, {key.upper(): [value] for key, value in facts.items()}):
            result = evaluate(REQUEST | {"context": context}, identities=[doc])
            self.assertEqual(result.decision, D.ALLOW)
            self.assertEqual(result.provenance[0]["normalized_request"]["principal_context"]["aws:principalarn"], ROLE)

    def test_session_role_path_must_be_bound_for_principalarn_condition(self):
        request = {key: value for key, value in REQUEST.items() if key != "role_arn"}
        self.assertEqual(evaluate(request, identities=[policy()]).decision, D.ALLOW)
        for context in ({}, {"aws:PrincipalArn": ROLE}):
            result = evaluate(request | {"context": context}, identities=[policy(
                              Condition={"ArnEquals": {"aws:PrincipalArn": ROLE}})])
            self.assertEqual(result.decision, D.UNKNOWN)
        self.assertEqual(evaluate(request, resources=[policy(Principal={"AWS": ROLE})]).decision, D.ALLOW)

    def test_service_and_oidc_cannot_receive_role_global_facts(self):
        for category, principal, action in (("Service", "ecs-tasks.amazonaws.com", "sts:AssumeRole"),
                                            ("Federated", PROVIDER, "sts:AssumeRoleWithWebIdentity")):
            for key, value in (("aws:PrincipalArn", ROLE), ("aws:PrincipalAccount", ACCOUNT),
                               ("aws:PrincipalType", "AssumedRole")):
                request = {"action": action, "resource": ROLE, "principal": principal, "context": {key: value}}
                self.assertEqual(evaluate(request, trust=[trust(category, principal, action)]).decision, D.UNKNOWN)

    def test_identity_contradiction_even_when_policy_does_not_reference_fact(self):
        for request in (REQUEST | {"role_arn": ROLE.replace("caller", "other")},
                        REQUEST | {"context": {"aws:PrincipalType": "FederatedUser"}},
                        REQUEST | {"context": {"aws:PrincipalAccount": ACCOUNT, "AWS:PRINCIPALACCOUNT": ACCOUNT}},
                        REQUEST | {"principal": SESSION.replace(ACCOUNT, "999999999999")}):
            self.assertEqual(evaluate(request, identities=[policy("Deny")]).decision, D.UNKNOWN)

    def test_unadmitted_top_level_identity_aliases_cannot_override_fact_model(self):
        for field, value in (("principal_account", "999999999999"), ("principal_type", "User"),
                             ("principal_arn", ROLE.replace(ACCOUNT, "999999999999"))):
            self.assertEqual(evaluate(REQUEST | {field: value}, identities=[policy()]).decision, D.UNKNOWN)


class V4ResourceAccountTests(unittest.TestCase):
    def test_derived_resource_account_context_cannot_be_replaced(self):
        for resource, key, supplied in ((QUEUE, "aws:ResourceAccount", {}),
                                       ("arn:aws:s3:::bucket/key", "s3:ResourceAccount", {"resource_account": ACCOUNT}),
                                       ("arn:aws:s3:::bucket/key", "aws:ResourceAccount", {"resource_account": ACCOUNT})):
            request = REQUEST | {"resource": resource} | supplied
            positive = policy(Resource="*", Condition={"StringEquals": {key: ACCOUNT}})
            self.assertEqual(evaluate(request, identities=[positive]).decision, D.ALLOW)
            self.assertEqual(evaluate(request | {"context": {key.upper(): [ACCOUNT]}},
                                      identities=[positive]).decision, D.ALLOW)
            for effect in ("Allow", "Deny"):
                bad = policy(effect, Resource="*", Condition={"StringEquals": {key: "999999999999"}})
                result = evaluate(request | {"context": {key: "999999999999"}}, identities=[bad])
                self.assertEqual(result.decision, D.UNKNOWN)
                self.assertIn("INVALID_RESOURCE", " ".join(result.reasons))

    def test_unavailable_resource_account_context_is_unknown_not_nonmatch(self):
        request = REQUEST | {"resource": "arn:aws:s3:::bucket/key"}
        for context in ({}, {"aws:ResourceAccount": ACCOUNT}):
            result = evaluate(request | {"context": context}, identities=[policy(Resource="*",
                              Condition={"StringEquals": {"aws:ResourceAccount": ACCOUNT}})])
            self.assertEqual(result.decision, D.UNKNOWN)

    def test_resource_arn_account_contradiction_unknown_before_policy_matching(self):
        for actual in (QUEUE, QUEUE.replace(ACCOUNT, "999999999999")):
            supplied = "999999999999" if actual == QUEUE else ACCOUNT
            request = REQUEST | {"resource": actual, "resource_account": supplied}
            for effect in ("Allow", "Deny"):
                for kind in ("identities", "resources"):
                    doc = policy(effect, Resource="*")
                    if kind == "resources":
                        doc["Statement"][0]["Principal"] = {"AWS": SESSION}
                    result = evaluate(request, **{kind: [doc]})
                    self.assertEqual(result.decision, D.UNKNOWN)
                    self.assertIn("contradictory resource_account", " ".join(result.reasons))

    def test_resource_account_derived_and_matching_supplied_same_account(self):
        for extras in ({}, {"resource_account": ACCOUNT}):
            result = evaluate(REQUEST | extras, resources=[policy(Principal={"AWS": SESSION})], boundary=[])
            self.assertEqual(result.decision, D.ALLOW)
            self.assertEqual(result.provenance[0]["normalized_request"]["resource_account"], ACCOUNT)

    def test_cross_account_and_unknown_resource_account_semantics_fail_closed(self):
        for resource in (QUEUE.replace(ACCOUNT, "999999999999"), "arn:aws:unmodeled:us-east-1:111122223333:resource",
                         "arn:aws:s3:::bucket/key", "*", "arn:aws:sqs::111122223333:queue"):
            request = REQUEST | {"resource": resource}
            self.assertEqual(evaluate(request, resources=[policy(Resource="*", Principal={"AWS": SESSION})]).decision, D.UNKNOWN)
        unknown = REQUEST | {"resource": "arn:aws:unmodeled:us-east-1:111122223333:resource", "resource_account": ACCOUNT}
        self.assertEqual(evaluate(unknown, resources=[policy(Resource="*", Principal={"AWS": SESSION})]).decision, D.UNKNOWN)


class V4SourceAdmissionTests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def test_actual_role_trust_resource_mutation_cannot_ground_runtime(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        original = path.read_text()
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "ALLOW")
        path.write_text(original.replace('actions = ["sts:AssumeRole"]',
                                        'actions = ["sts:AssumeRole"]\n    resources = ["*"]'))
        self.acknowledge(root, pins=True)
        record = baseline(root)[0]
        for outcome in ("delivery:runtime", "infra:stronger-workload-compute"):
            self.assertEqual(record["states"][outcome], "UNKNOWN")
        self.assertIn("SEMANTIC_ADMISSION_UNKNOWN", json.dumps(record["traces"]))

    def test_fresh_certificate_rejects_malformed_boundary_and_envelope(self):
        temp = tempfile.TemporaryDirectory(prefix="e1-v4-kind-")
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        write_universe(directory, {"direct": D.DENY})
        path = directory / "routes.json"
        original = json.loads(path.read_text())
        for bad in (False, {}, [{"Version": "2099-01-01", "Statement": policy()["Statement"]}]):
            changed = copy.deepcopy(original)
            changed["routes"][0]["policies"]["boundary"] = bad
            path.write_text(json.dumps(changed))
            universe = ClosedUniverse(directory)
            self.assertEqual(closure(universe.seeds, universe.rules, universe=universe)[0]["out"], D.UNKNOWN)
            with self.assertRaises(Unsupported):
                universe.certificate("out")
