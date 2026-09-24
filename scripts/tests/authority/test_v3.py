"""R1-R6 production-path regressions, including independent permutations.

Source mutations edit disposable repository copies, then deliberately acknowledge
the freshness inventory. No test changes expected answers or graph output.
"""
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from evaluator import Decision as D, Unsupported, evaluate, authorize, condition
from source import Adapter, IAM, digest, semantic_inventory
from inventory import scan, verify
from graph import baseline, closure
from coverage import ClosedUniverse
from fixture_support import write_universe
import test_repository


ROLE = "arn:aws:iam::111122223333:role/caller"
SESSION = "arn:aws:sts::111122223333:assumed-role/caller/session"
REQUEST = {"action": "s3:GetObject", "resource": "arn:aws:s3:::bucket/key",
           "principal": SESSION, "resource_account": "111122223333"}


def policy(effect="Allow", conditions=None, principal=None):
    statement = {"Effect": effect, "Action": "s3:GetObject", "Resource": "*"}
    if conditions is not None:
        statement["Condition"] = conditions
    if principal is not None:
        statement["Principal"] = {"AWS": principal}
    return {"Statement": [statement]}


def principal_policy(kind, principal):
    """R2 identity probes use a valid envelope for each evaluated policy kind."""
    doc = policy(principal=principal)
    if kind == "trust":
        doc["Statement"][0].pop("Resource")
        doc["Statement"][0]["Action"] = "sts:AssumeRole"
    return doc


class ConditionAdmissionTests(unittest.TestCase):
    def test_r1_complete_operand_admission_permutations(self):
        valid = "arn:aws:s3:::bucket/*"
        for malformed in ("bad", "arn:::::", "arn:aws:s3:::bad value", None, 7, [], {}):
            for values in itertools.permutations([valid, malformed, "arn:aws:s3:::other/*"]):
                for effect in ("Allow", "Deny"):
                    with self.subTest(values=values, effect=effect):
                        doc = policy(effect, {"ArnEquals": {"fixture:k": list(values)}})
                        result = evaluate(REQUEST | {"context": {"fixture:k": REQUEST["resource"]}}, [policy(), doc])
                        self.assertEqual(result.decision, D.UNKNOWN)

    def test_r1_missing_key_does_not_hide_bad_structure(self):
        for op in ("ArnEquals", "ArnLike", "ArnEqualsIfExists", "ForAllValues:ArnLike", "ForAnyValue:ArnEquals"):
            for context in ({}, {"fixture:k": []}, {"fixture:k": None}):
                self.assertEqual(evaluate(REQUEST | {"context": context}, [policy(conditions={op: {"fixture:k": "bad"}})]).decision, D.UNKNOWN)
        for cond in ({"StringEquals": {}}, {"Bool": {}}, {"StringEquals": {"": "v"}},
                     {"StringEquals": {3: "v"}}, {"StringEquals": {"fixture:k": [], "other": "v"}},
                     {"StringEquals": {"fixture:k": "x", "FIXTURE:K": "x"}}, {"ArnLike": []}, {None: {"fixture:k": "v"}}):
            self.assertEqual(evaluate(REQUEST, [policy(conditions=cond)]).decision, D.UNKNOWN)

    def test_r1_admitted_multi_value_allow_and_deny(self):
        patterns = ["arn:aws:s3:::other/*", "arn:aws:s3:::bucket/*"]
        for values in itertools.permutations(patterns):
            for op in ("ArnEquals", "ArnLike", "ForAllValues:ArnEquals", "ForAnyValue:ArnLike"):
                cond = {op: {"FIXTURE:K": list(values)}}
                req = REQUEST | {"context": {"fixture:k": REQUEST["resource"]}}
                self.assertEqual(evaluate(req, [policy(conditions=cond)]).decision, D.ALLOW)
                self.assertEqual(evaluate(req, [policy(), policy("Deny", cond)]).decision, D.DENY)
        with self.assertRaises(Unsupported):
            condition({"ForAllValues:ArnEqualsIfExists": {"fixture:k": patterns}}, {})


class IdentityAdmissionTests(unittest.TestCase):
    def test_r2_conflicting_alias_permutations(self):
        for principal in (SESSION.replace("111122223333", "999999999999"), SESSION.replace("caller", "stranger"),
                          "lambda.amazonaws.com", "arn:aws:iam::111122223333:oidc-provider/idp.example"):
            for kind in ("resources", "trust"):
                for alias in (ROLE, ROLE.replace("role/caller", "role/path/caller")):
                    request = REQUEST | {"principal": principal, "role_arn": alias}
                    if kind == "trust":
                        request = request | {"action": "sts:AssumeRole"}
                    self.assertEqual(evaluate(request, **{kind: [principal_policy(kind, ROLE)]}).decision, D.UNKNOWN)

    def test_r2_derived_and_explicit_parent_including_paths(self):
        for role in (ROLE, ROLE.replace("role/caller", "role/team/app/caller")):
            for alias in ({}, {"role_arn": role}):
                for kind in ("resources", "trust"):
                    request = REQUEST | alias
                    if kind == "trust":
                        request = request | {"action": "sts:AssumeRole"}
                    self.assertEqual(evaluate(request, **{kind: [principal_policy(kind, role)]}).decision, D.ALLOW)
                self.assertEqual(evaluate(REQUEST | alias, resources=[policy(principal=role)], boundary=[]).decision, D.DENY)
                self.assertEqual(evaluate(REQUEST | alias, resources=[policy(principal=SESSION)], boundary=[]).decision, D.ALLOW)
                self.assertEqual(evaluate(REQUEST | alias, resources=[policy(principal=SESSION)], boundary=[policy("Deny")]).decision, D.DENY)

    def test_r2_malformed_and_unsupported_identities(self):
        for principal in (SESSION + "/extra", SESSION.replace("/session", "/"), SESSION.replace("caller", "bad role"),
                          "arn:aws:sts::111122223333:assumed-role/path/caller/session", "111122223333", "*",
                          "arn:aws:iam::111122223333:root", "arn:aws:iam::111122223333:user/caller"):
            self.assertEqual(evaluate(REQUEST | {"principal": principal}, resources=[policy(principal=ROLE)]).decision, D.UNKNOWN)


class SourceAdmissionTests(unittest.TestCase):
    fixture = test_repository.RepositoryTests.fixture

    def acknowledge(self, root, pins=False):
        path = root / "ci/authority/source-inventory.json"
        manifest = json.loads(path.read_text())
        for name, record in scan(root).items():
            manifest["sources"].setdefault(name, {"semantic_status": "UNVERIFIED"}).update(record)
        path.write_text(json.dumps(manifest))
        if pins:
            path = root / "ci/authority/synthetic-context.json"
            manifest = json.loads(path.read_text())
            for name, record in manifest["workload_binding_files"].items():
                record["sha256"] = digest(root / name)
            path.write_text(json.dumps(manifest))
        self.assertEqual(verify(root), [])

    def assert_unknown(self, root, outcome="delivery:runtime"):
        result = baseline(root)[0]
        self.assertEqual(result["states"][outcome], "UNKNOWN")
        self.assertNotEqual(result["outcomes"][outcome]["verdict"], "WITNESS_ALLOW")
        return result

    def test_r3_json_policy_and_attachment_with_fresh_inventory(self):
        root = self.fixture()
        role = Adapter(root, "dev").roles["github_dev_deploy"]["name"]
        path = root / "terraform/infra/shared/review.tf.json"
        for typ, attrs in (("aws_iam_role_policy", {"role": role, "name": "deny", "policy": json.dumps(policy("Deny"))}),
                           ("aws_iam_role_policy_attachment", {"role": role, "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"})):
            path.write_text(json.dumps({"resource": {typ: {"review": attrs}}}))
            self.acknowledge(root)
            # JSON in the binding module invalidates source admission itself;
            # no graph may be evaluated using the pre-override declarations.
            with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                baseline(root)
            records = [r for r in semantic_inventory(root) if r["source"].endswith("review.tf.json")]
            self.assertEqual(records[0]["admission"], "UNSUPPORTED_APPLICABLE")

    def test_r3_nested_allow_and_deny_never_falsely_modeled(self):
        root = self.fixture()
        parent = root / "terraform/infra/shared/review.tf"
        parent.write_text('module "review" {\n source = "./modules/iam_github/nested_review"\n}\n')
        child = root / IAM / "nested_review/policy.tf"
        child.parent.mkdir()
        name = Adapter(root, "dev").roles["github_dev_deploy"]["name"]
        for effect in ("Allow", "Deny"):
            child.write_text('resource "aws_iam_role_policy" "extra" {\n name = "extra"\n role = "' + name +
                             '"\n policy = jsonencode({Version="2012-10-17",Statement=[{Effect="' + effect + '",Action="*",Resource="*"}]})\n}\n')
            self.acknowledge(root)
            result = self.assert_unknown(root)
            records = [r for r in semantic_inventory(root) if r["source"].endswith("nested_review/policy.tf")]
            self.assertTrue(records)
            self.assertTrue(all(r["admission"] != "MODELED" for r in records))
            self.assertTrue(result["provenance"]["source_admission"])

    def test_r3_all_override_forms_taint(self):
        root = self.fixture()
        base = root / "terraform/infra/apps/fargate/modules/ecs_service"
        for filename in ("override.tf", "review_override.tf", "override.tf.json", "review_override.tf.json"):
            path = base / filename
            body = {"resource": {"aws_iam_role": {"execution_role": {"permissions_boundary": "arn:aws:iam::111122223333:policy/b"}}}}
            path.write_text(json.dumps(body) if filename.endswith("json") else
                            'resource "aws_iam_role" "execution_role" {\n permissions_boundary = "arn:aws:iam::111122223333:policy/b"\n}\n')
            self.acknowledge(root)
            self.assert_unknown(root)
            path.unlink()
            manifest = json.loads((root / "ci/authority/source-inventory.json").read_text())
            manifest["sources"].pop(path.relative_to(root).as_posix())
            (root / "ci/authority/source-inventory.json").write_text(json.dumps(manifest))

    def test_r3_unrelated_literal_output_does_not_taint(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/review.tf"
        path.write_text('output "review_note" {\n value = "non-security literal"\n}\n')
        self.acknowledge(root)
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "ALLOW")
        record = next(r for r in semantic_inventory(root) if r["source"].endswith("review.tf"))
        self.assertEqual(record["admission"], "NON_SECURITY_RELEVANT")
        self.assertTrue(record["reason"])

    def test_new_resource_mechanism_and_embedded_policy_are_unknown(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/review.tf"
        for body in ('resource "new_security_provider_grant" "extra" {}',
                     'resource "aws_s3_bucket" "extra" {\n bucket = "fixture"\n policy = "{}"\n}'):
            path.write_text(body)
            self.acknowledge(root)
            self.assert_unknown(root)

    def test_r4_each_actual_trust_reference_after_pin_refresh(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        original = path.read_text()
        extra = '\ndata "aws_iam_policy_document" "other" {\n statement {\n actions = ["sts:AssumeRole"]\n principals {\n type = "Service"\n identifiers = ["lambda.amazonaws.com"]\n }\n }\n}\n'
        for selected in (("task_role",), ("execution_role",), ("task_role", "execution_role")):
            changed = original
            for role in selected:
                start = changed.index('resource "aws_iam_role" "' + role + '"')
                end = changed.index('\n}', start)
                changed = changed[:start] + changed[start:end].replace("ecs_tasks_assume.json", "other.json") + changed[end:]
            path.write_text(changed + extra)
            self.acknowledge(root, pins=True)
            record = self.assert_unknown(root)
            self.assertEqual(record["states"]["delivery:role-field-substitution"], "UNKNOWN")
            self.assertIn("ecs_tasks_assume", path.read_text())  # unused old grant cannot satisfy reference
            workload = Adapter(root, "dev").workload()
            for role in ("task_role", "execution_role"):
                check = evaluate({"action": "sts:AssumeRole", "resource": "target", "principal": "ecs-tasks.amazonaws.com"}, trust=[workload["trusts"][role]])
                self.assertEqual(check.decision, D.DENY if role in selected else D.ALLOW)

    def test_r4_missing_used_document_and_unsupported_reference(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        original = path.read_text()
        for text in (original.replace('"ecs_tasks_assume"', '"unused_equivalent"', 1),
                     original.replace("data.aws_iam_policy_document.ecs_tasks_assume.json", 'jsonencode({Statement=[]})')):
            path.write_text(text)
            self.acknowledge(root, pins=True)
            self.assert_unknown(root)

    def test_r4_override_trust_and_legitimate_independent_trusts(self):
        root = self.fixture()
        model = Adapter(root, "dev")
        workload = model.workload()
        for role in ("task_role", "execution_role"):
            self.assertEqual(evaluate({"action": "sts:AssumeRole", "resource": "target", "principal": "ecs-tasks.amazonaws.com"}, trust=[workload["trusts"][role]]).decision, D.ALLOW)
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/review_override.tf"
        path.write_text('resource "aws_iam_role" "execution_role" {\n assume_role_policy = jsonencode({Statement=[]})\n}\n')
        self.acknowledge(root)
        self.assert_unknown(root)

    def test_r5_module_inputs_do_not_inherit_fixture_values(self):
        root = self.fixture()
        path = root / "terraform/infra/shared/main.tf"
        original = path.read_text()
        for old, new in (("github_owner = var.github_owner", 'github_owner = "OtherOwner"'),
                         ("github_repo  = var.github_repo", 'github_repo = "OtherRepo"'),
                         ("env     = var.env", 'env = "unbound"'),
                         ('name    = "${local.name}-github"', 'name = "other-role-prefix"')):
            self.assertIn(old, original)
            path.write_text(original.replace(old, new))
            self.acknowledge(root)
            with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
                Adapter(root, "dev")

    def test_r5_root_literals_and_extra_iam_instance(self):
        root = self.fixture()
        path = root / "terraform/live/dev/root.hcl"
        original = path.read_text()
        path.write_text(original.replace('github_owner = "Kendall04"', 'github_owner = "OtherOwner"'))
        self.acknowledge(root)
        with self.assertRaisesRegex(Unsupported, "SOURCE_BINDING_FAILURE"):
            Adapter(root, "dev")
        path.write_text(original)
        extra = root / "terraform/infra/shared/extra.tf"
        extra.write_text('module "another_iam" {\n source = "./modules/iam_github"\n name = "collision"\n}\n')
        self.acknowledge(root)
        self.assert_unknown(root)

    def test_r5_alb_rename_uses_declaration_not_permission_scope(self):
        root = self.fixture()
        path = root / "terraform/infra/global/modules/alb/alb.tf"
        path.write_text(path.read_text().replace("${var.name}-internal-alb", "${var.name}-different-alb"))
        self.acknowledge(root)
        result = self.assert_unknown(root, "github_dev_deploy:direct-routing")
        self.assertIn("different-alb", result["provenance"]["routing"]["listener"])
        self.assertIn("internal-alb", Adapter(root, "dev").value("local.app_elbv2_blue_green_mutation_arns")[0])

    def test_r5_listener_and_rule_relationships(self):
        root = self.fixture()
        path = root / "terraform/infra/global/modules/alb/alb.tf"
        original = path.read_text()
        for old, new in (("load_balancer_arn = aws_lb.demo_internal_alb.arn", 'load_balancer_arn = "unresolved-alb"'),
                         ("listener_arn = aws_lb_listener.demo_http_listener.arn", 'listener_arn = "unresolved-listener"')):
            path.write_text(original.replace(old, new))
            self.acknowledge(root)
            self.assert_unknown(root, "github_dev_deploy:direct-routing")

    def test_r5_cluster_service_and_module_identifiers(self):
        root = self.fixture()
        cases = [("terraform/infra/platform/modules/ecs_cluster/main.tf", "name = var.name", 'name = "different-cluster"'),
                 ("terraform/infra/apps/fargate/modules/ecs_service/service.tf", '"${var.name}-svc"', '"unbound-service"'),
                 ("terraform/infra/apps/fargate/demo.tf", "cluster_arn = var.cluster_arn", 'cluster_arn = "unbound-cluster"')]
        for name, old, new in cases:
            path = root / name
            original = path.read_text()
            self.assertIn(old, original)
            path.write_text(original.replace(old, new))
            self.acknowledge(root, pins=True)
            self.assert_unknown(root)
            path.write_text(original)
            self.acknowledge(root, pins=True)

    def test_provenance_and_current_partial_positive_witness(self):
        root = self.fixture()
        record = baseline(root)[0]
        outcome = record["outcomes"]["delivery:runtime"]
        self.assertEqual(outcome["verdict"], "WITNESS_ALLOW")
        self.assertEqual(outcome["coverage"]["status"], "PARTIAL")
        self.assertTrue(record["provenance"]["identity"]["admitted_declarations"])
        self.assertTrue(record["provenance"]["identity"]["substitution_bindings"])
        self.assertTrue(record["provenance"]["workload"]["provenance"])
        for check in record["traces"]["delivery:runtime"]["checks"]:
            self.assertTrue(check["provenance"])
            self.assertEqual(check["provenance"][0]["applicable_unknown"], [])

    def test_new_dependency_output_and_wrapper_identity_mutations(self):
        root = self.fixture()
        cases = [("terraform/infra/platform/outputs.tf", "module.ecs_cluster.cluster_arn", '"unbound-cluster"'),
                 ("terraform/infra/platform/modules/ecs_cluster/outputs.tf", "aws_ecs_cluster.this.arn", '"unbound-cluster"'),
                 ("terraform/live/dev/platform/terragrunt.hcl", "project = local.parent.locals.project_name", 'project = "other"'),
                 ("terraform/live/dev/apps/fargate/terragrunt.hcl", "../../../../infra//apps/fargate", "../../../../infra/shared")]
        for filename, old, new in cases:
            path = root / filename
            original = path.read_text()
            self.assertIn(old, original)
            path.write_text(original.replace(old, new))
            self.acknowledge(root, pins=True)
            self.assert_unknown(root)
            path.write_text(original)
            self.acknowledge(root, pins=True)

    def test_new_task_policy_controls_cannot_be_ignored(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/demo.tf"
        original = path.read_text()
        for text in (original.replace('Effect = "Allow"', 'Effect = "Deny"'),
                     original.replace("aws_iam_policy.task_use_kms.arn", '"arn:aws:iam::aws:policy/Unsnapshotted"')):
            path.write_text(text)
            self.acknowledge(root, pins=True)
            record = self.assert_unknown(root, "infra:stronger-workload-compute")
            self.assertEqual(record["states"]["infra:broaden-role"], "ALLOW")  # mutation permission survives
            self.assertEqual(record["provenance"]["workload"]["task_policy_controls"]["status"], "UNKNOWN")
        path.write_text(original)
        extra = root / "terraform/infra/apps/fargate/modules/ecs_service/extra.tf"
        extra.write_text('resource "aws_iam_role_policy" "deny" {\n name = "deny"\n role = aws_iam_role.task_role.id\n policy = "{}"\n}\n')
        self.acknowledge(root, pins=True)
        self.assert_unknown(root, "infra:stronger-workload-compute")

    def test_new_workload_identity_collision(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        path.write_text(path.read_text().replace('"${var.name}-exec-role"', '"${var.name}-task-role"'))
        self.acknowledge(root, pins=True)
        self.assert_unknown(root)

    def test_new_case_variant_role_is_not_disjoint(self):
        root = self.fixture()
        name = Adapter(root, "dev").roles["github_dev_deploy"]["name"]
        path = root / "terraform/infra/shared/review.tf"
        path.write_text('resource "aws_iam_role" "collision" {\n name = "' + name.upper() +
                        '"\n assume_role_policy = "{}"\n}\n')
        self.acknowledge(root)
        self.assert_unknown(root)


class CompletenessCertificateTests(unittest.TestCase):
    def fixture(self, decisions=None):
        temp = tempfile.TemporaryDirectory(prefix="e1-complete-")
        self.addCleanup(temp.cleanup)
        return write_universe(Path(temp.name), decisions or {"A": D.DENY, "B": D.DENY, "C": D.DENY})

    def result(self, universe, certificate=None):
        coverage = {} if certificate is None else {"out": certificate}
        return closure(universe.seeds, universe.rules, coverage, universe)[0]["out"]

    def test_r6_complete_abc_and_partial_negative(self):
        universe = self.fixture()
        self.assertEqual(self.result(universe, universe.certificate("out")), D.DENY)
        self.assertEqual(closure(universe.seeds, universe.rules)[0]["out"], D.UNKNOWN)
        label = {"out": {"status": "COMPLETE_FOR_CURRENT_ADMITTED_MODEL", "reason": "manually asserted"}}
        self.assertEqual(closure(universe.seeds, universe.rules, label)[0]["out"], D.UNKNOWN)

    def test_r6_fourth_route_invalidates_old_certificate(self):
        universe = self.fixture()
        old = universe.certificate("out")
        fresh = write_universe(universe.directory, {"A": D.DENY, "B": D.DENY, "C": D.DENY, "D": D.ALLOW})
        self.assertEqual(self.result(universe, old), D.UNKNOWN)
        self.assertEqual(self.result(fresh, old), D.ALLOW)  # new proven witness does not need completeness
        self.assertEqual(self.result(fresh, fresh.certificate("out")), D.ALLOW)

    def test_r6_unsupported_source_taints_even_positive(self):
        for decisions in ({"A": D.DENY, "B": D.DENY, "C": D.DENY}, {"A": D.ALLOW}):
            universe = self.fixture(decisions)
            old = universe.certificate("out")
            (universe.directory / "extra.tf.json").write_text('{"resource":{"aws_iam_role_policy":{"extra":{}}}}')
            self.assertEqual(self.result(universe, old), D.UNKNOWN)
            fresh = ClosedUniverse(universe.directory)
            self.assertTrue(fresh.unknown)
            with self.assertRaises(Unsupported):
                fresh.certificate("out")

    def test_r6_changed_hash_cannot_reuse_negative_certificate(self):
        universe = self.fixture()
        old = universe.certificate("out")
        path = universe.directory / "routes.json"
        path.write_text(path.read_text() + "\n")
        self.assertEqual(self.result(universe, old), D.UNKNOWN)
        fresh = ClosedUniverse(universe.directory)
        self.assertEqual(self.result(fresh, old), D.UNKNOWN)
        self.assertEqual(self.result(fresh, fresh.certificate("out")), D.DENY)

    def test_r6_explicit_deny_recomputed_from_source(self):
        universe = self.fixture({"A": D.ALLOW, "B": D.DENY, "C": D.DENY})
        old = universe.certificate("out")
        path = universe.directory / "routes.json"
        doc = json.loads(path.read_text())
        doc["routes"][0]["policies"]["identities"].append(policy("Deny"))
        path.write_text(json.dumps(doc))
        self.assertEqual(self.result(universe, old), D.UNKNOWN)
        fresh = ClosedUniverse(universe.directory)
        self.assertEqual(self.result(fresh, fresh.certificate("out")), D.DENY)

    def test_r6_structurally_unrelated_output_preserves_certificate(self):
        universe = self.fixture()
        certificate = universe.certificate("out")
        (universe.directory / "note.json").write_text(json.dumps({"kind": "LITERAL_OUTPUT", "value": "unrelated"}))
        self.assertEqual(self.result(universe, certificate), D.DENY)
        fresh = ClosedUniverse(universe.directory)
        self.assertTrue(fresh.non_applicable)
        self.assertEqual(self.result(fresh, certificate), D.DENY)

    def test_r6_source_routes_abc_permutations(self):
        for allowed in (3, 2, 1, 0):
            universe = self.fixture({name: D.ALLOW if i < allowed else D.DENY for i, name in enumerate("ABC")})
            self.assertEqual(self.result(universe, universe.certificate("out")), D.ALLOW if allowed else D.DENY)
