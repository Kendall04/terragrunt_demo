"""A4 source applicability, exercised through source admission and current graph."""
import json
import unittest
from source import Adapter, semantic_inventory
from graph import baseline
import test_v3


class ApplicabilityV4Tests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def put(self, root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        self.acknowledge(root)
        return path

    def states(self, root):
        return {record["environment"]: record["states"] for record in baseline(root)}

    def test_inert_uninvoked_json_retains_current_witnesses(self):
        root = self.fixture()
        name = "terraform/infra/apps/fargate/modules/uninvoked/metadata.tf.json"
        self.put(root, name, {"output": {"note": {"value": {"nested": [True, None, 7, "inert"]}, "sensitive": False}}})
        states = self.states(root)
        for env in ("dev", "prod"):
            self.assertEqual(states[env]["delivery:runtime"], "ALLOW")
            self.assertEqual(states[env]["infra:stronger-workload-compute"], "ALLOW")
        record = next(r for r in semantic_inventory(root) if r["source"] == name)
        self.assertEqual(record["admission"], "NON_SECURITY_RELEVANT")
        self.assertEqual(record["applicability"]["status"], "NOT_APPLICABLE")

    def test_uninvoked_unsupported_application_module_cannot_poison_iam(self):
        root = self.fixture()
        name = "terraform/infra/apps/fargate/modules/not_called/application.tf.json"
        self.put(root, name, {"resource": {"unknown_application_resource": {"app": {"opaque": ["unsupported"]}}}})
        self.assertEqual(self.states(root)["dev"]["acquire:github_terragrunt_cd"], "ALLOW")
        record = next(r for r in semantic_inventory(root) if r["source"] == name)
        self.assertEqual(record["source_support"], "UNSUPPORTED_APPLICABLE")
        self.assertEqual(record["admission"], "UNSUPPORTED_NOT_APPLICABLE")

    def test_sibling_parent_normalized_nested_json_deny_and_allow_apply(self):
        root = self.fixture()
        name = "terraform/infra/shared/modules/review_sibling/deeper/policy.tf.json"
        self.put(root, "terraform/infra/shared/review.tf", 'module "review" {\n source = "./modules/iam_github/../review_sibling"\n}\n')
        self.put(root, "terraform/infra/shared/modules/review_sibling/main.tf", 'module "deeper" {\n source = "./deeper"\n}\n')
        for effect in ("Allow", "Deny"):
            with self.subTest(effect=effect):
                self.put(root, name, {"resource": {"aws_iam_role_policy": {"unknown": {
                    "role": "demo-dev-github-deploy", "policy": json.dumps({"Statement": [{"Effect": effect, "Action": "*", "Resource": "*"}]})}}}})
                states = self.states(root)
                self.assertEqual(states["dev"]["delivery:runtime"], "UNKNOWN")
                self.assertEqual(states["prod"]["delivery:runtime"], "UNKNOWN")
                record = next(r for r in Adapter(root, "dev").discovery().records if r["source"] == name)
                self.assertEqual(record["applicability"]["status"], "APPLICABLE")

    def test_json_module_source_keeps_children_reachable(self):
        root = self.fixture()
        self.put(root, "terraform/infra/shared/review.tf.json", {"module": {"review": {"source": "./modules/json_child"}}})
        name = "terraform/infra/shared/modules/json_child/main.tf"
        self.put(root, name, 'resource "aws_iam_policy_attachment" "unknown" {}\n')
        # The wrapper's JSON itself fails binding; discovery must independently
        # retain the child as applicable rather than claiming it is uninvoked.
        record = next(r for r in semantic_inventory(root) if r["source"] == name)
        self.assertEqual(record["admission"], "UNSUPPORTED_APPLICABLE")
        self.assertEqual(record["applicability"]["status"], "APPLICABLE")

    def test_invoked_override_remains_applicable(self):
        root = self.fixture()
        self.put(root, "terraform/infra/apps/fargate/modules/ecs_service/review_override.tf.json", {
            "resource": {"aws_iam_role": {"execution_role": {"permissions_boundary": "arn:aws:iam::111122223333:policy/deny"}}}})
        self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "UNKNOWN")

    def test_prod_only_source_does_not_taint_dev_until_dependency_added(self):
        root = self.fixture()
        name = "terraform/infra/prod_review/authority.tf.json"
        self.put(root, "terraform/live/prod/review/terragrunt.hcl", 'terraform {\n source = "../../../infra/prod_review"\n}\n')
        self.put(root, name, {"resource": {"aws_iam_policy_attachment": {"opaque": {"policy_arn": "unknown"}}}})
        states = self.states(root)
        self.assertEqual(states["dev"]["delivery:runtime"], "ALLOW")
        self.assertEqual(states["prod"]["delivery:runtime"], "UNKNOWN")
        wrapper = root / "terraform/live/dev/platform/terragrunt.hcl"
        wrapper.write_text(wrapper.read_text() + '\ndependency "prod_review" {\n config_path = "../../prod/review"\n}\n')
        self.acknowledge(root)
        self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "UNKNOWN")

    def test_unknown_root_never_claims_to_be_uninvoked(self):
        root = self.fixture()
        name = "unbound-root/authority.tf.json"
        self.put(root, name, {"resource": {"aws_iam_policy_attachment": {"opaque": {}}}})
        self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "UNKNOWN")
        record = next(r for r in semantic_inventory(root) if r["source"] == name)
        self.assertEqual(record["admission"], "UNSUPPORTED_APPLICABLE")

    def test_json_output_override_or_expression_in_invoked_module_is_unknown(self):
        root = self.fixture()
        self.put(root, "terraform/infra/shared/review.tf", 'module "review" {\n source = "./modules/review_output"\n}\n')
        for value in ("literal-that-could-replace-identity", "${aws_iam_role.unknown.arn}"):
            with self.subTest(value=value):
                self.put(root, "terraform/infra/shared/modules/review_output/review_override.tf.json", {"output": {"role_arn": {"value": value}}})
                self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "UNKNOWN")

    def test_local_name_pattern_does_not_hide_colliding_workload_control(self):
        root = self.fixture()
        model = Adapter(root, "dev")
        task = model.workload()["task_role"].rsplit("/", 1)[-1]
        # An unrelated Lambda role with a composed local name must not taint a
        # workload. Replacing its local with the task's name changes applicability.
        name = "terraform/infra/shared/modules/review_role/main.tf"
        self.put(root, "terraform/infra/shared/review.tf", 'module "review" {\n source = "./modules/review_role"\n}\n')
        template = ('locals {\n prefix = "NAME"\n}\n'
                    'resource "aws_iam_role" "review" {\n name = "${local.prefix}"\n}\n'
                    'resource "aws_iam_role_policy" "review" {\n role = aws_iam_role.review.name\n policy = "opaque"\n}\n')
        path = self.put(root, name, template.replace("NAME", "unrelated-lambda-role"))
        self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "ALLOW")
        path.write_text(template.replace("NAME", task))
        self.acknowledge(root)
        record = baseline(root)[0]
        self.assertEqual(record["states"]["delivery:runtime"], "UNKNOWN")
        self.assertEqual(record["states"]["infra:stronger-workload-compute"], "UNKNOWN")
        self.assertEqual(record["states"]["acquire:github_dev_deploy"], "ALLOW")
        self.assertIn(name, json.dumps(record["traces"]["delivery:runtime"]))

    def test_module_source_into_uninspected_cache_cannot_supply_certainty(self):
        root = self.fixture()
        hidden = root / "terraform/infra/shared/.terraform/hidden"
        hidden.mkdir(parents=True)
        (hidden / "policy.tf").write_text('resource "aws_iam_role_policy" "deny" {}')
        self.put(root, "terraform/infra/shared/review.tf", 'module "review" {\n source = "./.terraform/hidden"\n}\n')
        self.assertEqual(self.states(root)["dev"]["delivery:runtime"], "UNKNOWN")
