import json
from pathlib import Path
import shutil
import tempfile
import unittest
from evaluator import Decision as D, Result, Unsupported, evaluate
from graph import Rule, baseline, closure
from inventory import scan, verify
from source import Adapter, IAM

ROOT = Path(__file__).resolve().parents[3]


class RepositoryTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory(prefix="e1-authority-")
        self.addCleanup(directory.cleanup)
        target = Path(directory.name)
        for name in scan(ROOT):
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        shutil.copytree(ROOT / "ci/authority", target / "ci/authority")
        return target

    def test_inventory_source_coverage(self):
        self.assertEqual(verify(ROOT), [])
        sources = scan(ROOT)
        kinds = {d["type"] for record in sources.values() for d in record["declarations"]}
        for kind in ("aws_iam_role", "aws_iam_role_policy", "aws_iam_policy", "aws_iam_role_policy_attachment", "aws_lambda_permission", "aws_kms_key"):
            self.assertIn(kind, kinds)
        self.assertTrue(any(x["signals"].get("credential-acquisition") for x in sources.values()))
        self.assertTrue(any(x["signals"].get("launch-or-mutation") for x in sources.values()))

    def test_new_policy_and_workflow_outside_inventory_fail(self):
        root = self.fixture()
        for name, text in (("new-root/unmodeled.tf", 'resource "aws_iam_role" "surprise" {}'),
                           (".github/workflows/unmodeled.yml", 'steps:\n  - uses: aws-actions/configure-aws-credentials@v4\n')):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        errors = verify(root)
        self.assertEqual(len([x for x in errors if x.startswith("UNMODELED_SOURCE")]), 2)

    def test_existing_policy_and_executable_dependency_drift_fail(self):
        root = self.fixture()
        for name in (IAM + "/github_delivery_split.tf", "terraform/infra/global/modules/nat/lambda/assign_eip.py"):
            path = root / name
            path.write_text(path.read_text() + "\n# reviewed content changed\n")
        self.assertEqual(len(verify(root)), 2)

    def test_current_baseline_chains(self):
        records = baseline(ROOT)
        for record in records:
            with self.subTest(environment=record["environment"]):
                states = record["states"]
                for name in ("acquire:github_terragrunt_cd", "acquire:github_terragrunt_ci",
                             "infra:broaden-role", "infra:stronger-workload-compute", "delivery:runtime",
                             "delivery:role-field-substitution", "github_app_rollback:direct-routing",
                             "legacy:prod-record-write", "legacy:combined-publish-route"):
                    self.assertEqual(states[name], "ALLOW", name)
                self.assertEqual(record["dev_approval_to_high_risk"], "ALLOW")
                self.assertIn("github_terragrunt_ci", record["unknowns"])
                self.assertEqual(record["evidence_type"], "REPOSITORY_MODEL_REACHABILITY_NOT_EXECUTED_EXPLOIT")

    def test_source_remove_and_add_passrole_changes_chain(self):
        root = self.fixture()
        path = root / IAM / "github_delivery_split.tf"
        original = path.read_text()
        path.write_text(original.replace('"iam:PassRole"', '"iam:ListRoles"'))
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "UNKNOWN")
        self.assertTrue(verify(root))
        path.write_text(original)
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "ALLOW")

    def test_source_remove_and_add_direct_alb_edge(self):
        root = self.fixture()
        path = root / IAM / "github_ecs_blue_green.tf"
        original = path.read_text()
        path.write_text(original.replace('"elasticloadbalancing:ModifyListener"', '"elasticloadbalancing:DescribeListeners"'))
        self.assertEqual(baseline(root)[0]["states"]["github_app_rollback:direct-routing"], "UNKNOWN")
        path.write_text(original)
        self.assertEqual(baseline(root)[0]["states"]["github_app_rollback:direct-routing"], "ALLOW")

    def test_source_remove_and_add_ecs_activation_edge(self):
        root = self.fixture()
        path = root / IAM / "github_delivery_split.tf"
        original = path.read_text()
        path.write_text(original.replace('"ecs:UpdateService"', '"ecs:DescribeServices"'))
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "UNKNOWN")
        path.write_text(original)
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "ALLOW")

    def test_source_old_subject_reintroduction(self):
        root = self.fixture()
        path = root / IAM / "locals.tf"
        original = path.read_text()
        old = "github_dev_deploy_subjects    = [local.github_environment_subject]"
        self.assertIn(old, original)
        isolated = 'github_dev_deploy_subjects    = ["repo:fixture:environment:dev:job_workflow_ref:pinned"]'
        path.write_text(original.replace(old, isolated))
        self.assertEqual(baseline(root)[0]["states"]["acquire:github_dev_deploy"], "UNKNOWN")
        path.write_text(original.replace(old, isolated[:-1] + ", local.github_environment_subject]"))
        self.assertEqual(baseline(root)[0]["states"]["acquire:github_dev_deploy"], "ALLOW")

    def test_source_unsupported_construct_is_not_deny(self):
        root = self.fixture()
        path = root / IAM / "github_delivery_split.tf"
        path.write_text(path.read_text().replace('actions = [', 'not_actions = [', 1))
        self.assertTrue(verify(root))
        with self.assertRaisesRegex(Unsupported, "unsupported IAM source fields"):
            Adapter(root, "dev")

    def test_source_policy_mutation_edge_not_hardcoded(self):
        root = self.fixture()
        path = root / IAM / "github_terragrunt_cd.tf"
        path.write_text(path.read_text().replace('"iam:PutRolePolicy"', '"iam:ListRoles"'))
        self.assertEqual(baseline(root)[0]["states"]["infra:stronger-workload-compute"], "ALLOW")

    def test_boundary_or_workload_trust_change_invalidates_chain(self):
        root = self.fixture()
        path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        path.write_text(path.read_text().replace('resource "aws_iam_role" "task_role" {',
                                               'resource "aws_iam_role" "task_role" {\n permissions_boundary = "unmodeled"'))
        self.assertEqual(baseline(root)[0]["states"]["infra:stronger-workload-compute"], "UNKNOWN")

    def test_actual_attachment_removal_changes_result(self):
        root = self.fixture()
        path = root / IAM / "github_delivery_split.tf"
        text = path.read_text()
        start = text.index('resource "aws_iam_role_policy_attachment" "github_dev_deploy"')
        end = text.index('\n}', start) + 2
        path.write_text(text[:start] + text[end:])
        self.assertEqual(baseline(root)[0]["states"]["delivery:runtime"], "UNKNOWN")

    def test_necessity_covers_every_evaluated_statement(self):
        necessity = json.loads((ROOT / "ci/authority/necessity.json").read_text())
        entries = {x["source"]: x for x in necessity["entries"]}
        observed = set()
        for env in ("dev", "prod"):
            for role in Adapter(ROOT, env).roles.values():
                for doc in role["policies"]:
                    for st in doc["Statement"]:
                        observed.add(st["_source"])
                        self.assertIn(st["_source"], entries)
                        self.assertTrue(entries[st["_source"]]["legitimate_purpose"])
        self.assertEqual(observed, set(entries))

    def test_principal_inventory_covers_every_role_declaration(self):
        entries = json.loads((ROOT / "ci/authority/principals.json").read_text())["principals"]
        for env in ("dev", "prod"):
            for name in Adapter(ROOT, env).roles:
                self.assertTrue(any(x["id"] == env + ":" + name for x in entries))
        for path, record in scan(ROOT).items():
            for declaration in record["declarations"]:
                if declaration["type"] == "aws_iam_role" and '/iam_github/' not in path:
                    self.assertTrue(any(x["id"] == path + '#' + declaration["name"] for x in entries))

    def test_graph_fixed_point_unknown_and_denied(self):
        rules = [Rule("end", ("middle",), (), "dependent"),
                 Rule("middle", ("seed",), (Result(D.UNKNOWN, ("unsupported",)),), "unknown edge")]
        states, traces = closure(["seed"], rules)
        self.assertEqual(states["end"], D.UNKNOWN)
        self.assertIn("middle", traces["end"]["prerequisites"])
        rules.append(Rule("middle", ("seed",), (Result(D.ALLOW, ("proven alternative",)),), "alternative"))
        self.assertEqual(closure(["seed"], rules)[0]["end"], D.ALLOW)
        deny_rules = [Rule("middle", ("seed",), (Result(D.DENY, ("denied",)),), "deny"), rules[0]]
        self.assertEqual(closure(["seed"], deny_rules)[0]["end"], D.UNKNOWN)

    def test_current_direct_secret_denial_not_inherited_by_workload(self):
        model = Adapter(ROOT, "dev")
        request = {"action": "secretsmanager:GetSecretValue", "resource": "arn:aws:secretsmanager:us-east-1:111122223333:secret:demo/dev/app/db-123456"}
        self.assertEqual(evaluate(request, model.roles["github_terragrunt_cd"]["policies"]).decision, D.DENY)
        # Consequence of authorized PutRolePolicy; synthetic payload, not a current policy.
        broadened = {"Statement": [{"Effect": "Allow", "Action": request["action"], "Resource": request["resource"]}]}
        self.assertEqual(evaluate(request, [broadened]).decision, D.ALLOW)
