"""V6 invariants through production module resolution, discovery and coverage."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from bindings import Bindings
from coverage import ClosedUniverse
from evaluator import CONTEXT_KEYS, CONTEXT_AVAILABILITY, Decision as D, Unsupported, evaluate
from graph import baseline, closure
from source import Adapter
import test_v3

ROOT = Path(__file__).resolve().parents[3]


class ModuleScopeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="e1-v6-scope-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.bindings = Bindings(SimpleNamespace(root=self.root, values={"var.env": "ambient", "local.aws_region": "ambient"}))
        for name in ("parent", "child", "sibling"):
            (self.root / name).mkdir()
        self.put("parent", 'variable "env" {\n type = string\n default = "dev"\n}\n')
        self.put("child", 'variable "env" {\n type = string\n default = "prod"\n}\nlocals {\n aws_region = "child-region"\n label = "role-${var.env}"\n}\n')
        self.put("sibling", 'variable "env" {\n type = string\n default = "sibling"\n}\n')
        self.parent = self.bindings.instance("parent", "root", {})

    def put(self, directory, text):
        (self.root / directory / "main.tf").write_text(text)

    def child(self, supplied=None, name="blue"):
        return self.bindings.instance("child", "root/module." + name, supplied or {}, self.parent)

    def test_variable_default_omitted_argument(self):
        self.assertEqual(self.child().scalar("local.label"), "role-prod")
        self.assertEqual(self.parent.scalar("var.env"), "dev")

    def test_variable_explicit_argument(self):
        self.assertEqual(self.child({"env": '"dev"'}).scalar("var.env"), "dev")
        self.assertEqual(self.child({"env": "var.env"}).scalar("var.env"), "dev")

    def test_module_two_invocations(self):
        blue, green = self.child({"env": '"blue"'}), self.child({"env": '"green"'}, "green")
        self.assertEqual([blue.scalar("local.label"), green.scalar("local.label"), blue.scalar("local.label")],
                         ["role-blue", "role-green", "role-blue"])
        self.assertNotEqual(blue.identity, green.identity)

    def test_module_sibling_defaults(self):
        sibling = self.bindings.instance("sibling", "root/module.sibling", {}, self.parent)
        self.assertEqual([self.child().scalar("var.env"), sibling.scalar("var.env")], ["prod", "sibling"])

    def test_local_collision_with_synthetic_namespace(self):
        self.assertEqual(self.child().scalar("local.aws_region"), "child-region")

    def test_synthetic_cannot_supply_undeclared_symbols(self):
        for expression in ("var.name", "local.account_id", "local.unknown"):
            with self.assertRaises(Unsupported):
                self.child().scalar(expression)

    def test_variable_unsupported_argument_no_default_fallback(self):
        child = self.child({"env": 'get_env("ENV")'})
        with self.assertRaises(Unsupported):
            child.scalar("var.env")
        self.assertEqual(child.scalar("local.aws_region"), "child-region")

    def test_variable_missing_and_unsupported_default(self):
        for default in ("", '\n default = var.env'):
            self.put("child", 'variable "env" {\n type = string' + default + '\n}\n')
            with self.assertRaises(Unsupported):
                self.child().scalar("var.env")

    def test_local_unsupported_and_cycle_are_not_ambient(self):
        self.put("child", 'locals {\n aws_region = unsupported()\n loop = local.loop\n}\n')
        for expression in ("local.aws_region", "local.loop"):
            with self.assertRaises(Unsupported):
                self.child().scalar(expression)


class RepositoryScopeTests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def test_synthetic_scope_metadata_cannot_move_binding(self):
        root = self.fixture()
        path = root / "ci/authority/synthetic-context.json"
        data = json.loads(path.read_text())
        data["source_bindings"]["local.aws_region"]["module_instance"] = "another/root"
        path.write_text(json.dumps(data))
        with self.assertRaises(Unsupported):
            Adapter(root, "dev")

    def test_local_cluster_collision_uses_own_literal(self):
        root = self.fixture()
        path = root / "terraform/infra/platform/modules/ecs_cluster/main.tf"
        import re
        path.write_text(re.sub(r'name\s*=\s*var.name', 'name = local.aws_region', path.read_text()) +
                        '\nlocals {\n aws_region = "v6-own-cluster"\n}\n')
        self.acknowledge(root, pins=True)
        workload = Adapter(root, "dev").workload()
        self.assertIn("service/v6-own-cluster/", workload["service"])
        self.assertNotIn("service/us-east-1/", workload["service"])

    def test_variable_unsupported_security_argument_unbinds_workload(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/demo.tf"
        path.write_text(path.read_text().replace('name        = local.api_blue_name', 'name = unsupported()'))
        self.acknowledge(root, pins=True)
        record = baseline(root, environments=("dev",))[0]
        self.assertEqual(record["provenance"]["workload"]["task_role"], "UNBOUND")
        self.assertEqual(record["states"]["delivery:runtime"], "UNKNOWN")
        self.assertEqual(record["states"]["acquire:github_dev_deploy"], "ALLOW")

    def test_variable_repository_false_witness_default_and_explicit(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/variables.tf"
        path.write_text(path.read_text() + '\nvariable "env" {\n type = string\n default = "prod"\n}\n')
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        path.write_text(path.read_text().replace('${var.name}-task-role', 'demo-${var.env}-app-api-blue-task-role')
                        .replace('${var.name}-exec-role', 'demo-${var.env}-app-api-blue-exec-role'))
        path = root / "terraform/infra/apps/fargate/demo.tf"
        path.write_text(path.read_text().replace('module "demo_api_green" {', 'module "demo_api_green" {\n env = "green"'))
        self.acknowledge(root, pins=True)
        workload = Adapter(root, "dev").workload()
        self.assertIn("demo-prod-app", workload["task_role"])
        record = baseline(root, environments=("dev",))[0]
        self.assertEqual(record["states"]["delivery:runtime"], "UNKNOWN")
        self.assertNotEqual(record["outcomes"]["delivery:runtime"]["verdict"], "WITNESS_ALLOW")
        path.write_text(path.read_text().replace('module "demo_api_blue" {', 'module "demo_api_blue" {\n env = "dev"'))
        self.acknowledge(root, pins=True)
        self.assertIn("demo-dev-app", Adapter(root, "dev").workload()["task_role"])
        self.assertEqual(baseline(root, environments=("dev",))[0]["states"]["delivery:runtime"], "ALLOW")


class ContextAvailabilityTests(unittest.TestCase):
    def request(self, principal="arn:aws:sts::111122223333:assumed-role/Reader/review-session", context=None):
        return {"action": "s3:GetObject", "resource": "arn:aws:s3:::review-v6/key", "principal": principal, "context": context or {}}

    def policy(self, effect="Allow"):
        return {"Statement": [{"Effect": effect, "Action": "s3:GetObject", "Resource": "*",
            "Condition": {"ArnEquals": {"aws:SourceArn": "arn:aws:events:us-east-1:111122223333:rule/review"}}}]}

    def test_sourcearn_omitted_valid_and_malformed_both_effects(self):
        for context in ({}, {"aws:SourceArn": "arn:aws:events:us-east-1:111122223333:rule/review"}, {"aws:SourceArn": "bad"}):
            for effect in ("Allow", "Deny"):
                self.assertEqual(evaluate(self.request(context=context), identities=[self.policy(effect)]).decision, D.UNKNOWN)

    def test_sourcearn_service_and_role_unsupported(self):
        for principal in ("ecs-tasks.amazonaws.com", "arn:aws:iam::111122223333:role/Reader"):
            self.assertEqual(evaluate(self.request(principal), identities=[self.policy()]).decision, D.UNKNOWN)

    def test_sourcearn_supplied_even_without_condition_is_invalid(self):
        self.assertEqual(evaluate(self.request(context={"aws:SourceArn": "arn:aws:events:us-east-1:111122223333:rule/review"}),
                                  identities=[]).decision, D.UNKNOWN)

    def test_certificate_false_effective_deny_cannot_be_issued(self):
        with tempfile.TemporaryDirectory(prefix="e1-v6-context-") as d:
            root = Path(d)
            (root / "universe.json").write_text(json.dumps({"kind": "CLOSED_SYNTHETIC_UNIVERSE", "seeds": ["seed"],
                "subjects": ["reader"], "mechanisms": ["read"], "outcomes": ["out"]}))
            for effect in ("Allow", "Deny"):
                policies = [self.policy(effect)]
                if effect == "Deny":
                    policies.insert(0, {"Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "*"}]})
                (root / "routes.json").write_text(json.dumps({"routes": [{"id": "read", "mechanism": "read", "target": "out",
                    "prerequisites": ["seed"], "subjects": ["reader"], "request": self.request(context={"aws:SourceArn": "arn:aws:events:us-east-1:111122223333:rule/review"}),
                    "policies": {"identities": policies}}]}))
                universe = ClosedUniverse(root)
                self.assertEqual(closure(universe.seeds, universe.rules, universe=universe)[0]["out"], D.UNKNOWN)
                with self.assertRaises(Unsupported):
                    universe.certificate("out")

    def test_registry_every_key_has_availability_rule(self):
        self.assertEqual(set(CONTEXT_KEYS), set(CONTEXT_AVAILABILITY))
        for env in ("dev", "prod"):
            for role in Adapter(ROOT, env).roles.values():
                for document in role["policies"] + [role["trust"]]:
                    for statement in document["Statement"]:
                        self.assertNotIn("aws:sourcearn", {key.lower() for tests in statement.get("Condition", {}).values() for key in tests})

    def test_other_request_keys_wrong_action_are_unknown(self):
        for key, value in (("iam:PassedToService", "ecs-tasks.amazonaws.com"),
                           ("iam:PolicyARN", "arn:aws:iam::111122223333:policy/read"), ("s3:prefix", "folder/")):
            self.assertEqual(evaluate(self.request(context={key: value}), identities=[]).decision, D.UNKNOWN)


class ConsumerTests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge

    def source(self, consumer, native=False):
        root = self.fixture()
        directory = root / "terraform/infra/shared/modules/v6_literal"
        directory.mkdir()
        if native:
            (directory / "main.tf").write_text('output "note" {\n value = "literal"\n}\n')
        else:
            (directory / "main.tf.json").write_text(json.dumps({"output": {"note": {"value": "literal"}}}))
        (root / "terraform/infra/shared/v6_consumer.tf").write_text('module "v6_literal" {\n source = "./modules/v6_literal"\n}\n' + consumer)
        self.acknowledge(root)
        return root

    def check(self, consumer, expected, native=False):
        root = self.source(consumer, native)
        record = baseline(root, environments=("dev",))[0]
        for node in ("acquire:github_dev_deploy", "delivery:runtime", "github_app_rollback:direct-routing"):
            self.assertEqual(record["states"][node], expected, node)
        return root

    def test_terminal_json_unused_local(self):
        self.check('locals {\n unused = module.v6_literal.note\n}\n', "ALLOW")

    def test_terminal_native_unused_local(self):
        self.check('locals {\n unused = module.v6_literal.note\n}\n', "ALLOW", native=True)

    def test_terminal_two_exact_locals(self):
        self.check('locals {\n first = module.v6_literal.note\n second = local.first\n}\n', "ALLOW")

    def test_security_sink_through_local(self):
        self.check('locals {\n first = module.v6_literal.note\n}\nresource "aws_iam_role_policy" "v6" {\n role = local.first\n policy = "opaque"\n}\n', "UNKNOWN")

    def test_unresolved_dynamic_use(self):
        self.check('locals {\n first = module.v6_literal.note\n second = local["first"]\n}\n', "UNKNOWN")

    def test_unresolved_transformed_local(self):
        self.check('locals {\n first = module.v6_literal.note\n second = upper(local.first)\n}\n', "UNKNOWN")

    def test_unresolved_spaced_reference_cannot_prove_terminal(self):
        self.check('locals {\n first = module.v6_literal.note\n}\noutput "use" {\n value = local . first\n}\n', "UNKNOWN")

    def test_unresolved_cycle_not_terminal(self):
        self.check('locals {\n first = module.v6_literal.note\n second = "${local.first}-${local.second}"\n}\n', "UNKNOWN")

    def test_other_environment_consumer_not_dev_applicable(self):
        root = self.source('locals {\n unused = module.v6_literal.note\n}\n')
        # A prod-only local module has a security consumer of the same source.
        directory = root / "terraform/infra/v6_prod"
        directory.mkdir()
        (directory / "main.tf").write_text('module "v6_literal" {\n source = "../shared/modules/v6_literal"\n}\nresource "aws_iam_role_policy" "v6" {\n role = module.v6_literal.note\n policy = "opaque"\n}\n')
        wrapper = root / "terraform/live/prod/v6_prod"
        wrapper.mkdir()
        (wrapper / "terragrunt.hcl").write_text('terraform {\n source = "../../../infra/v6_prod"\n}\n')
        self.acknowledge(root)
        self.assertEqual(baseline(root, environments=("dev",))[0]["states"]["delivery:runtime"], "ALLOW")
        self.assertEqual(baseline(root, environments=("prod",))[0]["states"]["delivery:runtime"], "UNKNOWN")
