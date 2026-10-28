import json
from pathlib import Path
import unittest
from contracts import ContractError, check_runtime_inventory, classify_runtime, load_json, oidc_subject, validate, validate_schema
from evaluator import Decision as D, evaluate

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "ci/authority"


def read(name):
    return load_json((CONTRACTS / name).read_text())


class ContractTests(unittest.TestCase):
    def test_json_unique_and_finite(self):
        for text in ('{"x":1,"x":2}', '{"x": NaN}', '{"x": Infinity}'):
            with self.assertRaises(ContractError):
                load_json(text)
        for path in CONTRACTS.glob("*.json"):
            load_json(path.read_text())

    def test_all_responsibilities_and_ownership_status(self):
        responsibilities = read("responsibilities.json")
        self.assertEqual(responsibilities["classification"], "TARGET_REQUIREMENT")
        self.assertEqual(len({x["id"] for x in responsibilities["responsibilities"]}), 11)
        self.assertTrue(all(x["authorized_outcome"] and x["excluded"] for x in responsibilities["responsibilities"]))
        self.assertEqual(read("ownership.json")["classification"], "TARGET_REQUIREMENT")

    def test_closed_request_schemas_and_positive_examples(self):
        schemas = read("requests.json")["schemas"]
        examples = {"build": {"source_commit": "a" * 40},
                    "deploy": {"qualification_id": "q-1", "replicas": 1},
                    "rollback-release": {"history_id": "h-1", "replicas": 1},
                    "emergency": {"color": "blue", "replicas": 1, "reason": "restore"},
                    "lifecycle": {"installed_revision": "a" * 40, "layer": "data", "operation": "reconcile"},
                    "status": {"operation_id": "op-1"}}
        for name, schema in schemas.items():
            with self.subTest(name=name):
                validate(examples[name], schema)
                for field in ("environment", "role", "taskDefinition", "image", "approved", "buildspecOverride"):
                    with self.assertRaises(ContractError):
                        validate(examples[name] | {field: "attacker"}, schema)
        with self.assertRaises(ContractError):
            validate({"qualification_id": "../escape", "replicas": 1}, schemas["deploy"])
        with self.assertRaises(ContractError):
            validate({"qualification_id": "q", "replicas": True}, schemas["deploy"])

    def test_schema_unknown_semantics_rejected(self):
        with self.assertRaises(ContractError):
            validate_schema({"type": "string", "oneOf": []})
        with self.assertRaises(ContractError):
            validate_schema({"type": "object", "additionalProperties": True})

    def test_runtime_inventory_completeness_and_unknown_fields(self):
        contract, vocabulary = read("runtime-fields.json"), read("runtime-vocabulary.json")
        check_runtime_inventory(contract, vocabulary)
        for name in ("container.newExecutionHook", "task.unknown", "service.futureRouting"):
            self.assertEqual(classify_runtime(contract, name)["disposition"], "REJECT_UNKNOWN")
        for name in ("task.taskRoleArn", "task.executionRoleArn", "container.image", "container.command",
                     "container.environmentFiles", "container.mountPoints", "container.firelensConfiguration",
                     "container.privileged", "container.linuxParameters", "service.enableExecuteCommand",
                     "service.serviceConnectConfiguration", "container.restartPolicy", "response.revision"):
            self.assertIn(name, contract["fields"])
        vocabulary["fields"].append("container.newInjection")
        with self.assertRaises(ContractError):
            check_runtime_inventory(contract, vocabulary)

    def test_runtime_structural_schema_positive_and_rejections(self):
        schema = read("runtime.schema.json")
        template = json.loads((ROOT / "demo-api/deploy/task-definition.template.json").read_text())
        template["family"] = "demo-dev-app-api-blue"
        template["taskRoleArn"] = "arn:aws:iam::111122223333:role/task"
        template["executionRoleArn"] = "arn:aws:iam::111122223333:role/execution"
        for i, container in enumerate(template["containerDefinitions"]):
            container["name"] = "app" if i == 0 else "probe"
            container["image"] = "111122223333.dkr.ecr.us-east-1.amazonaws.com/demo@sha256:" + "a" * 64
            for entry in container.get("environment", []):
                entry["value"] = "synthetic-binding"
            for entry in container.get("secrets", []):
                entry["valueFrom"] = "synthetic-secret-arn"
            container["logConfiguration"]["options"] = {k: "synthetic-binding" for k in container["logConfiguration"]["options"]}
        validate(template, schema)
        for extra in ({"volumes": []}, {"newField": "execute"}):
            with self.assertRaises(ContractError):
                validate(template | extra, schema)
        template["containerDefinitions"][0]["environmentFiles"] = []
        with self.assertRaises(ContractError):
            validate(template, schema)

    def test_external_expectations_remain_unverified(self):
        governance = read("governance.json")
        self.assertEqual(governance["classification"], "EXTERNAL_PREREQUISITE")
        self.assertEqual(governance["verification"], "UNVERIFIED")
        self.assertTrue(all(x["verification"] == "UNVERIFIED" for x in governance["expectations"]))
        self.assertEqual(governance["include_claim_keys"], ["repo", "context", "job_workflow_ref"])

    def test_oidc_formats_and_exact_synthetic_target_acquisition(self):
        workflow = "Kendall04/terragrunt_demo/.github/workflows/e1-dev-deploy.yml"
        for mode in ("name", "immutable_ids"):
            subject = oidc_subject("Kendall04/terragrunt_demo", "prod:eastus", workflow, "a" * 40, mode, "123", "456")
            self.assertIn("prod%3Aeastus", subject)
            self.assertIn("job_workflow_ref:" + workflow + "@" + "a" * 40, subject)
            if mode == "immutable_ids":
                self.assertIn("Kendall04@123/terragrunt_demo@456", subject)
            trust = {"Statement": [{"Effect": "Allow", "Action": "sts:AssumeRoleWithWebIdentity",
                                    "Principal": {"Federated": "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"},
                                    "Condition": {"StringEquals": {"token.actions.githubusercontent.com:sub": subject, "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"}}}]}
            request = {"action": "sts:AssumeRoleWithWebIdentity", "resource": "synthetic-role", "principal": "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com",
                       "context": {"token.actions.githubusercontent.com:sub": subject, "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"}}
            self.assertEqual(evaluate(request, trust=[trust]).decision, D.ALLOW)
            for bad in (subject.replace("a" * 40, "b" * 40), "repo:Kendall04/terragrunt_demo:environment:prod"):
                self.assertEqual(evaluate(request | {"context": {"token.actions.githubusercontent.com:sub": bad, "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"}}, trust=[trust]).decision, D.DENY)
        with self.assertRaises(ContractError):
            oidc_subject("o/r", "env", workflow, "main")

    def test_synthetic_planning_positive_prevents_deny_all(self):
        policy = {"Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::dev-state/*"}]}
        req = {"action": "s3:GetObject", "resource": "arn:aws:s3:::dev-state/global/state"}
        self.assertEqual(evaluate(req, [policy]).decision, D.ALLOW)
        self.assertNotEqual(evaluate(req, []).decision, D.ALLOW)
        self.assertEqual(evaluate(req | {"action": "s3:PutObject"}, [policy]).decision, D.DENY)
