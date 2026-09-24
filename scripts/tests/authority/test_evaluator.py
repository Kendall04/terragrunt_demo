import unittest
from evaluator import Decision as D, Unsupported, authorize, condition, evaluate, matches


def policy(action="s3:GetObject", resource="arn:aws:s3:::dev/*", effect="Allow", **extra):
    return {"Statement": [{"Effect": effect, "Action": action, "Resource": resource, **extra}]}


REQUEST = {"action": "s3:GetObject", "resource": "arn:aws:s3:::dev/object",
           "resource_account": "111122223333",
           "principal": "arn:aws:sts::111122223333:assumed-role/test/session",
           "role_arn": "arn:aws:iam::111122223333:role/test"}


class EvaluatorTests(unittest.TestCase):
    def test_allow_deny_unknown_distinct(self):
        self.assertEqual(evaluate(REQUEST, [policy()]).decision, D.ALLOW)
        self.assertEqual(evaluate(REQUEST).decision, D.DENY)
        self.assertEqual(evaluate(REQUEST, [policy(NotAction="s3:DeleteObject")]).decision, D.UNKNOWN)
        self.assertEqual(len({D.ALLOW, D.DENY, D.UNKNOWN}), 3)

    def test_identity_union_and_explicit_deny(self):
        self.assertEqual(evaluate(REQUEST, [policy("s3:PutObject"), policy()]).decision, D.ALLOW)
        self.assertEqual(evaluate(REQUEST, [policy(), policy(effect="Deny")]).decision, D.DENY)

    def test_boundary_intersection_and_empty_boundary(self):
        for boundary, expected in (([policy()], D.ALLOW), ([], D.DENY), ([policy("s3:PutObject")], D.DENY)):
            with self.subTest(boundary=boundary):
                self.assertEqual(evaluate(REQUEST, [policy()], boundary).decision, expected)
        self.assertEqual(evaluate(REQUEST, [], [policy()]).decision, D.DENY)

    def test_exact_role_versus_session_resource_grant(self):
        role = policy(Principal={"AWS": REQUEST["role_arn"]})
        session = policy(Principal={"AWS": REQUEST["principal"]})
        self.assertEqual(evaluate(REQUEST, boundary=[], resources=[role]).decision, D.DENY)
        self.assertEqual(evaluate(REQUEST, boundary=[], resources=[session]).decision, D.ALLOW)
        self.assertEqual(evaluate(REQUEST, boundary=[policy(effect="Deny")], resources=[session]).decision, D.DENY)
        self.assertEqual(evaluate(REQUEST, identities=[policy(effect="Deny")], resources=[session]).decision, D.DENY)

    def test_unsupported_constructs_visible(self):
        cases = [{"NotAction": "s3:PutObject"}, {"NotResource": "*"}, {"NotPrincipal": {"AWS": "*"}},
                 {"Resource": "arn:aws:s3:::${aws:username}/*"}, {"Condition": {"StringNotEquals": {"fixture:k": "v"}}},
                 {"Condition": {"NumericEquals": {"fixture:k": "1"}}}, {"Condition": {"StringEqualsIfExistsUnknown": {"fixture:k": "v"}}}]
        for extra in cases:
            with self.subTest(extra=extra):
                st = policy()["Statement"][0] | extra
                self.assertEqual(evaluate(REQUEST, [{"Statement": [st]}]).decision, D.UNKNOWN)

    def test_wildcard_principal_and_kms_unknown(self):
        for principal in ("*", {"AWS": "*"}, {"AWS": "arn:aws:iam::111122223333:root"}):
            with self.subTest(principal=principal):
                doc = policy(Principal=principal, Condition={"ArnEquals": {"aws:PrincipalArn": REQUEST["role_arn"]}})
                self.assertEqual(evaluate(REQUEST, resources=[doc]).decision, D.UNKNOWN)
        self.assertEqual(evaluate(REQUEST | {"action": "kms:Decrypt"}, resources=[policy()]).decision, D.UNKNOWN)
        self.assertEqual(evaluate(REQUEST | {"resource_account": "999999999999"},
                                 resources=[policy(Principal={"AWS": REQUEST["principal"]})]).decision, D.UNKNOWN)

    def test_missing_condition_truth_table(self):
        for operator, expected in (("StringEquals", False), ("StringLike", False), ("ArnEquals", False),
                                   ("Bool", False), ("StringEqualsIfExists", True),
                                   ("ForAllValues:ArnEquals", True), ("ForAnyValue:ArnEquals", False)):
            value = "true" if operator == "Bool" else "arn:aws:s3:::bucket/key" if "Arn" in operator else "v"
            with self.subTest(operator=operator):
                self.assertEqual(condition({operator: {"fixture:k": value}}, {}), expected)
        self.assertTrue(condition({"Null": {"fixture:k": "true"}}, {}))
        self.assertFalse(condition({"Null": {"fixture:k": "false"}}, {}))
        self.assertFalse(condition({"ForAllValues:ArnEquals": {"fixture:k": "arn:aws:s3:::bucket/key"}, "Null": {"fixture:k": "false"}}, {}))

    def test_condition_sets_and_types(self):
        self.assertTrue(condition({"ForAnyValue:StringLike": {"fixture:k": "dev*"}}, {"fixture:k": ["prod", "dev1"]}))
        self.assertFalse(condition({"ForAllValues:StringEquals": {"fixture:k": "dev"}}, {"fixture:k": ["dev", "prod"]}))
        self.assertTrue(condition({"ArnLike": {"fixture:k": "arn:aws:s3:::dev/*"}}, {"fixture:k": REQUEST["resource"]}))
        self.assertTrue(condition({"Bool": {"fixture:k": "false"}}, {"fixture:k": "false"}))
        for test, context in (({"StringEquals": {"fixture:k": "v"}}, {"fixture:k": ["v", "w"]}),
                              ({"Bool": {"fixture:k": "yes"}}, {"fixture:k": "yes"}),
                              ({"NullIfExists": {"fixture:k": "true"}}, {})):
            with self.assertRaises(Unsupported):
                condition(test, context)

    def test_iam_wildcards_not_shell_character_classes(self):
        self.assertTrue(matches("arn:*:role/a?", "arn:aws:role/ab"))
        self.assertFalse(matches("a[bc]", "ab"))
        self.assertTrue(matches("s3:get*", "S3:GetObject", True))
        self.assertFalse(matches("arn:aws:s3:::DEV/*", REQUEST["resource"]))

    def test_trust_identity_and_service(self):
        for principal in ("ecs-tasks.amazonaws.com", "lambda.amazonaws.com"):
            req = {"action": "sts:AssumeRole", "resource": "role", "principal": principal}
            trust = {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"Service": "ecs-tasks.amazonaws.com"}}]}
            self.assertEqual(evaluate(req, trust=[trust]).decision, D.ALLOW if principal.startswith("ecs") else D.DENY)

    def test_action_resource_context_and_dependency_admission(self):
        cap = {"s3:getobject": {"resources": ["arn:aws:s3:::*/*"], "context": [], "dependencies": []}}
        self.assertEqual(authorize(REQUEST, cap, identities=[policy()]).decision, D.ALLOW)
        for request in (REQUEST | {"resource": [REQUEST["resource"]]}, REQUEST | {"resource": "wrong"},
                        REQUEST | {"context": {"unsupported:key": "x"}}, REQUEST | {"action": "iam:CreateServiceLinkedRole"}):
            self.assertEqual(authorize(request, cap, identities=[policy()]).decision, D.UNKNOWN)
        with_condition = policy(Condition={"StringEqualsIfExists": {"unsupported:key": "x"}})
        self.assertEqual(authorize(REQUEST, cap, identities=[with_condition]).decision, D.UNKNOWN)
        cap["s3:getobject"]["dependencies"] = ["iam:passrole"]
        self.assertEqual(authorize(REQUEST, cap, identities=[policy()]).decision, D.UNKNOWN)

    def test_exact_environment_positive_and_negative(self):
        self.assertEqual(evaluate(REQUEST, [policy()]).decision, D.ALLOW)
        self.assertEqual(evaluate(REQUEST | {"resource": "arn:aws:s3:::prod/object"}, [policy()]).decision, D.DENY)

    def test_passrole_service_bound(self):
        req = {"action": "iam:PassRole", "resource": REQUEST["role_arn"], "context": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}}
        doc = policy("iam:PassRole", REQUEST["role_arn"], Condition={"StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}})
        self.assertEqual(evaluate(req, [doc]).decision, D.ALLOW)
        self.assertEqual(evaluate(req | {"context": {}}, [doc]).decision, D.DENY)
        self.assertEqual(evaluate(req | {"context": {"iam:PassedToService": "lambda.amazonaws.com"}}, [doc]).decision, D.DENY)
