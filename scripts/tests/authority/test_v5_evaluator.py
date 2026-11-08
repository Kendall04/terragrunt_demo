"""V4-01/02: admission and authoritative facts through evaluator and sources."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from coverage import ClosedUniverse
from evaluator import (CONTEXT_KEYS, Decision as D, Unsupported, admit_condition_arn,
                       admit_resource_arn, authorize, context_classification, evaluate,
                       normalize_resource_arn)
from graph import closure
from source import Adapter


ROOT = Path(__file__).resolve().parents[3]
ROLE = "arn:aws:iam::111122223333:role/team/Reader"
SESSION = "arn:aws:sts::111122223333:assumed-role/Reader/audit-session"
REQUEST = {"action": "s3:GetObject", "resource": "arn:aws:s3:::fixture/key",
           "principal": SESSION, "role_arn": ROLE}
PROVIDER = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"


def policy(effect="Allow", resource="arn:aws:s3:::fixture/*", condition=None):
    statement = {"Effect": effect, "Action": "s3:GetObject", "Resource": resource}
    if condition is not None:
        statement["Condition"] = condition
    return {"Version": "2012-10-17", "Statement": [statement]}


class ResourceArnV5Tests(unittest.TestCase):
    def test_review_service_wildcards_are_admission_failures_for_both_effects(self):
        capabilities = json.loads((ROOT / "ci/authority/capabilities.json").read_text())["actions"]
        for value in ("arn:aws:*:::fixture/key", "arn:aws:s?:::fixture/key"):
            for effect in ("Allow", "Deny"):
                with self.subTest(value=value, effect=effect):
                    for result in (evaluate(REQUEST, identities=[policy(effect, value)]),
                                   authorize(REQUEST, capabilities, identities=[policy(effect, value)])):
                        self.assertEqual(result.decision, D.UNKNOWN)
                        self.assertIn("SEMANTIC_ADMISSION_UNKNOWN", " ".join(result.reasons))
                        self.assertEqual(result.provenance[0]["evidence_validity"]["ADMISSION"], "UNKNOWN")

    def test_valid_list_member_cannot_hide_invalid_or_unsupported_second_value(self):
        for bad in ("arn:aws:s?:::fixture/*", "arn:aws:cloudfront::111122223333:distribution/review"):
            for effect in ("Allow", "Deny"):
                for resources in (["arn:aws:s3:::fixture/*", bad], [bad, "arn:aws:s3:::fixture/*"]):
                    with self.subTest(resources=resources, effect=effect):
                        self.assertEqual(evaluate(REQUEST, identities=[policy(effect, resources)]).decision, D.UNKNOWN)

    def test_supported_s3_account_bearing_and_resource_wildcard_forms(self):
        cases = [("arn:aws:s3:::fixture/key", REQUEST["resource"]),
                 ("arn:aws:s3:::fixture/*", REQUEST["resource"]),
                 ("arn:aws:sqs:us-east-1:111122223333:review-*", "arn:aws:sqs:us-east-1:111122223333:review-queue"),
                 ("arn:aws:iam::*:role/review/*", "arn:aws:iam::111122223333:role/review/Reader"),
                 ("arn:aws:lambda:*:111122223333:function:review-*", "arn:aws:lambda:us-east-1:111122223333:function:review-worker")]
        for pattern, resource in cases:
            with self.subTest(pattern=pattern):
                # This is policy-pattern matching, not API applicability proof.
                result = evaluate(REQUEST | {"resource": resource}, identities=[policy(resource=pattern)])
                self.assertEqual(result.decision, D.ALLOW)
                entries = result.provenance[0]["policy_admission"][0]["resource_arn_admission"]
                self.assertEqual(entries[0]["grammar"], "POLICY_RESOURCE_ARN_ADMISSION")

    def test_malformed_separators_location_components_and_unmodeled_form_are_unknown(self):
        for resource in ("arn:aws:s3::fixture/key", "arn:aws::s3:::fixture/key",
                         "arn::s3:::fixture/key", "arn:aws:s3:::fixture/has space",
                         "arn:aws:iam:us-east-1:111122223333:role/review",
                         "arn:aws:sqs::111122223333:review", "arn:aws:sqs:us-east-1:123:review",
                         "arn:aws-cn:sqs:cn-north-1:111122223333:review",
                         "arn:aws:unknown:us-east-1:111122223333:review",
                         "arn:aws:s3:us-east-1:111122223333:accesspoint/review"):
            with self.subTest(resource=resource):
                for effect in ("Allow", "Deny"):
                    self.assertEqual(evaluate(REQUEST, identities=[policy(effect, resource)]).decision, D.UNKNOWN)

    def test_three_arn_grammars_are_explicit_and_not_interchangeable(self):
        pattern = "arn:aws:s?:::fixture/key"
        self.assertEqual(admit_condition_arn(pattern)[2], "s?")
        with self.assertRaises(Unsupported):
            admit_resource_arn(pattern)
        with self.assertRaises(Unsupported):
            normalize_resource_arn(pattern)
        self.assertEqual(admit_resource_arn("arn:aws:s3:::fixture/*")["shape"], "s3")
        with self.assertRaises(Unsupported):
            normalize_resource_arn("arn:aws:s3:::fixture/*")
        self.assertEqual(normalize_resource_arn(REQUEST["resource"]), ("s3", ""))


class ContextFactsV5Tests(unittest.TestCase):
    def test_review_session_fact_omitted_correct_and_contradictory_for_allow_and_deny(self):
        condition = {"Bool": {"aws:PrincipalIsAWSService": "false"}}
        for context, valid in (({}, True), ({"aws:PrincipalIsAWSService": "false"}, True),
                               ({"AWS:PrincipalIsAWSService": ["false"]}, True),
                               ({"aws:PrincipalIsAWSService": "true"}, False)):
            for effect in ("Allow", "Deny"):
                with self.subTest(context=context, effect=effect):
                    docs = [policy(condition=condition)] if effect == "Allow" else [policy(), policy("Deny", condition=condition)]
                    result = evaluate(REQUEST | {"context": context}, identities=docs)
                    self.assertEqual(result.decision, (D.ALLOW if effect == "Allow" else D.DENY) if valid else D.UNKNOWN)
                    if valid:
                        fact = result.provenance[0]["context_facts"]["aws:principalisawsservice"]
                        self.assertEqual(fact["classification"], "DERIVED_AUTHORITATIVE")
                        self.assertEqual(fact["value"], "false")

    def test_role_and_direct_service_facts_are_derived_oidc_remains_unavailable(self):
        condition = {"Bool": {"aws:PrincipalIsAWSService": "false"}}
        self.assertEqual(evaluate(REQUEST | {"principal": ROLE}, identities=[policy(condition=condition)]).decision, D.ALLOW)
        trust = {"Statement": {"Effect": "Allow", "Action": "sts:AssumeRole",
            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
            "Condition": {"Bool": {"aws:PrincipalIsAWSService": "true"}}}}
        req = {"action": "sts:AssumeRole", "resource": ROLE, "principal": "ecs-tasks.amazonaws.com"}
        self.assertEqual(evaluate(req, trust=[trust]).decision, D.ALLOW)
        self.assertEqual(evaluate(req | {"context": {"aws:PrincipalIsAWSService": "false"}}, trust=[trust]).decision, D.UNKNOWN)
        trust["Statement"].update(Action="sts:AssumeRoleWithWebIdentity", Principal={"Federated": PROVIDER})
        req.update(action="sts:AssumeRoleWithWebIdentity", principal=PROVIDER)
        for context in ({}, {"aws:PrincipalIsAWSService": "false"}, {"aws:PrincipalIsAWSService": "true"}):
            self.assertEqual(evaluate(req | {"context": context}, trust=[trust]).decision, D.UNKNOWN)

    def test_other_derived_keys_cannot_be_forged_or_erased(self):
        for key, expected, wrong in (("aws:PrincipalAccount", "111122223333", "444455556666"),
                                     ("aws:PrincipalArn", ROLE, ROLE.replace("Reader", "Other")),
                                     ("aws:PrincipalType", "AssumedRole", "AWSService")):
            doc = policy(condition={"StringEquals": {key: expected}})
            for context, decision in (({}, D.ALLOW), ({key: expected}, D.ALLOW), ({key: wrong}, D.UNKNOWN)):
                with self.subTest(key=key, context=context):
                    self.assertEqual(evaluate(REQUEST | {"context": context}, identities=[doc]).decision, decision)

    def test_unknown_aws_keys_never_fall_through_even_on_nonmatching_statements(self):
        for key in ("aws:PrincipalServiceName", "aws:SourceIdentity", "aws:userid", "aws:FuturePrincipalFact", "unregistered:key"):
            self.assertEqual(context_classification(key), "UNSUPPORTED")
            for effect in ("Allow", "Deny"):
                doc = policy(effect, condition={"StringEqualsIfExists": {key: "caller-value"}})
                doc["Statement"][0]["Action"] = "s3:DeleteObject"
                result = evaluate(REQUEST | {"context": {key: "caller-value"}}, identities=[policy(), doc])
                self.assertEqual(result.decision, D.UNKNOWN)
                self.assertIn("unsupported condition context key", " ".join(result.reasons))

    def test_current_policy_keys_are_registered_and_classified(self):
        observed = set()
        for env in ("dev", "prod"):
            for role in Adapter(ROOT, env).roles.values():
                for doc in role["policies"] + [role["trust"]]:
                    for statement in doc["Statement"]:
                        observed.update(key.lower() for values in statement.get("Condition", {}).values() for key in values)
        self.assertTrue(observed)
        self.assertLessEqual(observed, set(CONTEXT_KEYS))
        self.assertTrue(all(context_classification(key) != "UNSUPPORTED" for key in observed))
        self.assertEqual(context_classification("fixture:k"), "SUPPORTED_CALLER_CONTEXT")
        self.assertEqual(context_classification("fixture:unregistered"), "UNSUPPORTED")

    def test_request_context_requires_validated_shapes(self):
        for key, bad in (("iam:PassedToService", "not-a-service"), ("iam:PolicyARN", "not-an-arn"),
                         ("aws:SecureTransport", "yes"), ("s3:prefix", ["one", "two"])):
            doc = policy(condition={"StringEquals": {key: "x"}})
            self.assertEqual(evaluate(REQUEST | {"context": {key: bad}}, identities=[doc]).decision, D.UNKNOWN)
        doc = policy(condition={"StringEquals": {"token.actions.githubusercontent.com:sub": "repo:fixture"}})
        self.assertEqual(evaluate(REQUEST, identities=[doc]).decision, D.UNKNOWN)


class CertificateAdmissionV5Tests(unittest.TestCase):
    def source(self, doc, request=REQUEST):
        temporary = tempfile.TemporaryDirectory(prefix="e1-v5-evaluator-cert-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "universe.json").write_text(json.dumps({"kind": "CLOSED_SYNTHETIC_UNIVERSE", "seeds": ["seed"],
            "subjects": ["reader"], "mechanisms": ["read"], "outcomes": ["out"]}))
        (root / "routes.json").write_text(json.dumps({"routes": [{"id": "read", "mechanism": "read", "target": "out",
            "prerequisites": ["seed"], "subjects": ["reader"], "request": request, "policies": {"identities": [doc]}}]}))
        return ClosedUniverse(root)

    def test_failed_resource_admission_never_issues_certificate_regardless_of_effect(self):
        for effect in ("Allow", "Deny"):
            for resource in ("arn:aws:*:::fixture/key", "arn:aws:s?:::fixture/key",
                             ["arn:aws:s3:::fixture/*", "arn:aws:cloudfront::111122223333:distribution/review"]):
                with self.subTest(effect=effect, resource=resource):
                    universe = self.source(policy(effect, resource))
                    self.assertEqual(universe.rules[0].checks[0].decision, D.UNKNOWN)
                    self.assertEqual(closure(universe.seeds, universe.rules, universe=universe)[0]["out"], D.UNKNOWN)
                    with self.assertRaises(Unsupported):
                        universe.certificate("out")

    def test_fact_omission_is_not_certified_deny_and_contradiction_is_not_certifiable(self):
        doc = policy(condition={"Bool": {"aws:PrincipalIsAWSService": "false"}})
        universe = self.source(doc)
        certificate = universe.certificate("out")
        self.assertEqual(closure(universe.seeds, universe.rules, {"out": certificate}, universe)[0]["out"], D.ALLOW)
        for context in ({"aws:PrincipalIsAWSService": "true"}, {"aws:PrincipalAccount": "444455556666"}):
            uncertain = self.source(doc, REQUEST | {"context": context})
            self.assertEqual(uncertain.rules[0].checks[0].decision, D.UNKNOWN)
            with self.assertRaises(Unsupported):
                uncertain.certificate("out")

    def test_valid_authoritative_conditional_deny_still_certifies(self):
        universe = self.source(policy("Deny", condition={"Bool": {"aws:PrincipalIsAWSService": "false"}}))
        cert = universe.certificate("out")
        states, traces = closure(universe.seeds, universe.rules, {"out": cert}, universe)
        self.assertEqual(states["out"], D.DENY)
        self.assertEqual(traces["out"]["reason_codes"], ["EFFECTIVE_DENY"])


if __name__ == "__main__":
    unittest.main()
