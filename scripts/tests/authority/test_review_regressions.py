"""Independent-review counterexamples exercised against production code."""
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import test_contracts
from evaluator import Decision as D, Result, Unsupported, condition, evaluate, principal_form
from graph import Rule, baseline, closure
from inventory import scan, verify
from source import Adapter, IAM, semantic_inventory
from fixture_support import write_universe
import test_repository


class SemanticRegressions(unittest.TestCase):
    def test_arn_equality_like_sets_and_explicit_deny(self):
        arn = "arn:aws:lambda:us-east-1:111122223333:function:worker"
        for op in ("ArnEquals", "ArnLike", "ForAllValues:ArnEquals", "ForAnyValue:ArnLike"):
            for pattern, expected in (("arn:aws:lambda:us-east-1:111122223333:function:*", True),
                                      ("arn:aws:lambda:us-east-1:999999999999:function:*", False)):
                with self.subTest(op=op, pattern=pattern):
                    cond = {op: {"AWS:SourceArn": pattern}}
                    self.assertEqual(condition(cond, {"aws:SourceArn": arn}), expected)
                    allow = {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}
                    request = {"action": "s3:GetObject", "resource": "arn:aws:s3:::bucket/key", "context": {"aws:SourceArn": arn}}
                    self.assertEqual(evaluate(request, [{"Statement": [allow | {"Condition": cond}]}]).decision,
                                     D.ALLOW if expected else D.DENY)
                    self.assertEqual(evaluate(request, [{"Statement": [allow, allow | {"Effect": "Deny", "Condition": cond}]}]).decision,
                                     D.DENY if expected else D.ALLOW)

    def test_arn_component_boundaries(self):
        for op in ("ArnEquals", "ArnLike"):
            cond = {op: {"k": "arn:aws:s3:*:111122223333:*"}}
            self.assertFalse(condition(cond, {"k": "arn:aws:s3:::bucket/x:111122223333:payload"}))
            self.assertTrue(condition(cond, {"k": "arn:aws:s3:us-east-1:111122223333:accesspoint/name"}))
            with self.assertRaises(Unsupported):
                condition(cond, {"k": "not-an-arn"})

    def test_context_keys_case_insensitive_values_preserved(self):
        for op in ("StringEquals", "StringLike"):
            self.assertTrue(condition({op: {"AWS:SourceArn": "Value"}}, {"aws:sourcearn": "Value"}))
            self.assertFalse(condition({op: {"AWS:SourceArn": "Value"}}, {"aws:sourcearn": "value"}))
        with self.assertRaises(Unsupported):
            condition({"StringEquals": {"k": "a"}}, {"k": "a", "K": "b"})

    def test_missing_empty_sets_null_and_ifexists(self):
        for context in ({}, {"k": None}, {"k": []}, {"k": ""}, {"k": [""]}):
            for op in ("StringEquals", "StringLike", "ArnEquals", "ArnLike", "Bool"):
                value = "true" if op == "Bool" else "arn:aws:s3:::bucket/key" if op.startswith("Arn") else "v"
                with self.subTest(context=context, op=op):
                    self.assertTrue(condition({"ForAllValues:" + op: {"k": value}}, context))
                    self.assertFalse(condition({"ForAnyValue:" + op: {"k": value}}, context))
                    self.assertTrue(condition({"Null": {"k": "true"}}, context))
                    self.assertFalse(condition({"Null": {"k": "false"}}, context))
        for op in ("StringEqualsIfExists", "ArnEqualsIfExists", "BoolIfExists"):
            value = "true" if op.startswith("Bool") else "arn:aws:s3:::bucket/key" if op.startswith("Arn") else "v"
            self.assertTrue(condition({op: {"k": value}}, {}))
            self.assertTrue(condition({op: {"k": value}}, {"k": value}))
            other = "false" if op.startswith("Bool") else "arn:aws:s3:::other/key" if op.startswith("Arn") else "other"
            self.assertFalse(condition({op: {"k": value}}, {"k": other}))
        for op in ("NullIfExists", "ForAllValues:Null", "ForAnyValue:StringEqualsIfExists", "ForAllValues:ArnLikeIfExists"):
            with self.assertRaises(Unsupported):
                condition({op: {"k": "true"}}, {})

    def test_multivalued_sets_positive_and_negative(self):
        self.assertTrue(condition({"ForAllValues:StringEquals": {"k": ["a", "b"]}}, {"k": ["a", "b"]}))
        self.assertFalse(condition({"ForAllValues:StringEquals": {"k": "a"}}, {"k": ["a", "b"]}))
        self.assertTrue(condition({"ForAnyValue:StringEquals": {"k": "a"}}, {"k": ["a", "b"]}))
        self.assertFalse(condition({"ForAnyValue:StringEquals": {"k": "c"}}, {"k": ["a", "b"]}))
        with self.assertRaises(Unsupported):
            condition({"ForAllValues:StringEquals": {"k": "a"}}, {"k": ["", "a"]})

    def test_unsupported_principals_never_exact_allow_or_nonmatch_deny(self):
        role = "arn:aws:iam::111122223333:role/caller"
        for principal in ("*", {"AWS": "*"}, {"AWS": "111122223333"},
                          {"AWS": "arn:aws:iam::111122223333:root"},
                          {"AWS": "arn:aws:iam::111122223333:user/operator"}):
            for kind in ("trust", "resources"):
                for caller in (role, next(iter(principal.values())) if isinstance(principal, dict) else "*"):
                    request = {"principal": caller, "role_arn": role, "action": "sts:AssumeRole",
                               "resource": role, "resource_account": "111122223333"}
                    doc = {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": role,
                                          "Principal": principal, "Condition": {"StringEqualsIfExists": {"k": "v"}}}]}
                    with self.subTest(principal=principal, kind=kind, caller=caller):
                        self.assertEqual(evaluate(request, **{kind: [doc]}).decision, D.UNKNOWN)

    def test_supported_principal_admission_and_exact_matches(self):
        for category, principal in (("AWS", "arn:aws:iam::111122223333:role/caller"),
                                    ("Service", "ecs-tasks.amazonaws.com"),
                                    ("Federated", "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com")):
            self.assertEqual(principal_form(category, principal, "trust"), "SUPPORTED_AND_MODELED")
            action = "sts:AssumeRoleWithWebIdentity" if category == "Federated" else "sts:AssumeRole"
            doc = {"Statement": [{"Effect": "Allow", "Action": action, "Principal": {category: principal}}]}
            request = {"action": action, "resource": "target", "principal": principal}
            self.assertEqual(evaluate(request, trust=[doc]).decision, D.ALLOW)
            other = {"AWS": "arn:aws:iam::111122223333:role/different", "Service": "lambda.amazonaws.com",
                     "Federated": "arn:aws:iam::111122223333:oidc-provider/different.example"}[category]
            self.assertEqual(evaluate(request | {"principal": other}, trust=[doc]).decision, D.DENY)
            self.assertEqual(evaluate(request | {"principal": "different"}, trust=[doc]).decision, D.UNKNOWN)
        self.assertEqual(principal_form("AWS", None, "trust"), "INVALID")


class SourceBindingRegressions(unittest.TestCase):
    fixture = test_repository.RepositoryTests.fixture

    def acknowledge(self, root):
        path = root / "ci/authority/source-inventory.json"
        manifest = json.loads(path.read_text())
        for name, record in scan(root).items():
            manifest["sources"].setdefault(name, {"semantic_status": "UNVERIFIED"}).update(record)
        path.write_text(json.dumps(manifest))
        self.assertEqual(verify(root), [])

    def test_unmodeled_role_attributes_after_inventory_refresh(self):
        root = self.fixture()
        path = root / IAM / "github_delivery_split.tf"
        original = path.read_text()
        for attribute in ('managed_policy_arns = ["arn:aws:iam::aws:policy/AdministratorAccess"]',
                          'for_each = {}', 'permissions_boundary = "arn:aws:iam::111122223333:policy/boundary"',
                          'count = 2', 'inline_policy {\n name = "inline"\n policy = "{}"\n }'):
            with self.subTest(attribute=attribute):
                # The first role already has count; duplicate count must also fail.
                path.write_text(original.replace('resource "aws_iam_role" "github_dev_deploy" {',
                                                 'resource "aws_iam_role" "github_dev_deploy" {\n ' + attribute))
                self.acknowledge(root)
                with self.assertRaises(Unsupported):
                    Adapter(root, "dev")

    def test_unknown_attachment_and_policy_producers_after_refresh(self):
        root = self.fixture()
        path = root / IAM / "review-extra.tf"
        for typ in ("aws_iam_policy_attachment", "aws_iam_policy_version", "aws_iam_user_policy", "aws_s3_bucket_policy"):
            with self.subTest(typ=typ):
                path.write_text('resource "' + typ + '" "extra" {\n name = "extra"\n}\n')
                self.acknowledge(root)
                with self.assertRaisesRegex(Unsupported, "SOURCE_ADMISSION_UNKNOWN"):
                    Adapter(root, "dev")

    def test_dynamic_unreferenced_policy_document_rejected(self):
        root = self.fixture()
        path = root / IAM / "review-extra.tf"
        path.write_text('data "aws_iam_policy_document" "unused" {\n dynamic "statement" {\n for_each = []\n }\n}\n')
        self.acknowledge(root)
        with self.assertRaises(Unsupported):
            Adapter(root, "dev")

    def test_supported_attachment_remains_source_bound(self):
        root = self.fixture()
        model = Adapter(root, "dev")
        self.assertTrue(model.roles["github_dev_deploy"]["policies"])
        self.assertEqual(model.roles["github_dev_deploy"]["unknown"], [])
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "ALLOW")

    def test_unexpanded_security_surfaces_explicitly_unknown(self):
        root = self.fixture()
        records = semantic_inventory(root)
        self.assertTrue(any(r["admission"] == "MODELED" for r in records))
        for typ in ("aws_kms_key", "aws_lambda_permission"):
            found = [r for r in records if r["declaration"] and r["declaration"]["type"] == typ]
            self.assertTrue(found)
            self.assertTrue(all(r["admission"] == "UNSUPPORTED_APPLICABLE" for r in found))

    def test_terraform_json_rejected_after_inventory_refresh(self):
        root = self.fixture()
        (root / IAM / "extra.tf.json").write_text('{"resource":{"aws_iam_policy_attachment":{"admin":{}}}}')
        self.acknowledge(root)
        with self.assertRaisesRegex(Unsupported, "SOURCE_ADMISSION_UNKNOWN"):
            Adapter(root, "dev")

    def test_region_and_account_expression_replacement(self):
        root = self.fixture()
        path = root / IAM / "locals.tf"
        original = path.read_text()
        for old, new in (("data.aws_region.current.name", '"eu-west-1"'),
                         ("data.aws_caller_identity.current.account_id", '"999999999999"')):
            path.write_text(original.replace(old, new))
            self.acknowledge(root)
            with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                Adapter(root, "dev")

    def test_workload_role_rename_removal_and_module_drift(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        original = path.read_text()
        for changed in (original.replace('${var.name}-task-role', '${var.name}-replacement-task-role'),
                        original[:original.index('# Task Role')]):
            path.write_text(changed)
            self.acknowledge(root)
            model = Adapter(root, "dev")
            with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                model.workload()
            self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "UNKNOWN")
        path.write_text(original)
        path = root / "terraform/infra/apps/fargate/demo.tf"
        path.write_text(path.read_text().replace('name        = local.api_blue_name', 'name        = "replacement"'))
        self.acknowledge(root)
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "UNKNOWN")

    def test_mismatched_synthetic_value_rejected(self):
        root = self.fixture()
        path = root / "ci/authority/synthetic-context.json"
        manifest = json.loads(path.read_text())
        manifest["bindings"]["local.github_oidc_provider_arn"] = "arn:aws:iam::999999999999:oidc-provider/evil"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
            Adapter(root, "dev")

    def test_legitimate_synthetic_context_bound_to_actual_roles(self):
        root = self.fixture()
        for env in ("dev", "prod"):
            model = Adapter(root, env)
            self.assertEqual(model.binding_status, "BINDING_VALIDATED")
            self.assertEqual(model.value("local.aws_region"), "us-east-1")
            self.assertEqual(model.workload()["task_role"], f"arn:aws:iam::111122223333:role/demo-{env}-app-api-blue-task-role")

    def test_independent_current_mutation_routes(self):
        root = self.fixture()
        path = root / IAM / "github_terragrunt_cd.tf"
        original = path.read_text()
        for removed, expected in ((["iam:PutRolePolicy"], "ALLOW"),
                                  (["iam:CreatePolicy", "iam:AttachRolePolicy"], "ALLOW"),
                                  (["iam:PutRolePolicy", "iam:CreatePolicy", "iam:AttachRolePolicy"], "UNKNOWN")):
            changed = original
            for action in removed:
                changed = changed.replace('"' + action + '"', '"iam:ListRoles"')
            path.write_text(changed)
            record = baseline(root)[0]
            self.assertEqual(record["states"]["infra:stronger-workload-compute"], expected)
            self.assertEqual(record["outcomes"]["infra:stronger-workload-compute"]["coverage"]["status"], "PARTIAL")


class CompletenessRegressions(unittest.TestCase):
    def test_positive_controls_reject_deny_all_and_all_unknown(self):
        for decision in (D.DENY, D.UNKNOWN):
            with patch.object(test_contracts, "evaluate", return_value=Result(decision, ("controlled corruption",))):
                suite = unittest.TestSuite([
                    test_contracts.ContractTests("test_synthetic_planning_positive_prevents_deny_all"),
                    test_contracts.ContractTests("test_oidc_formats_and_exact_synthetic_target_acquisition")])
                result = unittest.TestResult()
                suite.run(result)
                self.assertEqual(result.testsRun, 2)
                self.assertEqual(len(result.failures), 2)
                self.assertEqual(result.errors, [])

    def test_two_independent_witnesses_and_explicit_completeness(self):
        for a, b, expected in ((D.ALLOW, D.ALLOW, D.ALLOW), (D.DENY, D.ALLOW, D.ALLOW),
                               (D.ALLOW, D.DENY, D.ALLOW), (D.DENY, D.DENY, D.DENY),
                               (D.UNKNOWN, D.DENY, D.UNKNOWN)):
            with tempfile.TemporaryDirectory(prefix="e1-closed-universe-") as directory:
                universe = write_universe(Path(directory), {"A": a, "B": b})
                complete = {} if universe.unknown else {"out": universe.certificate("out")}
                self.assertEqual(closure(universe.seeds, universe.rules, complete, universe)[0]["out"], expected)
                if a == b == D.DENY:
                    self.assertEqual(closure(universe.seeds, universe.rules)[0]["out"], D.UNKNOWN)

    def test_cycles_do_not_manufacture_witness(self):
        rules = [Rule("a", ("b",), (), "cycle"), Rule("b", ("a",), (), "cycle")]
        self.assertEqual(closure([], rules)[0], {"a": D.UNKNOWN, "b": D.UNKNOWN})
        rules.append(Rule("b", ("seed",), (), "grounded witness"))
        self.assertEqual(closure(["seed"], rules)[0]["a"], D.ALLOW)
