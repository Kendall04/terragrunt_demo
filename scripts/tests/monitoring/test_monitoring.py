"""Active TARGET contracts, generated packages and bounded authority witnesses.

The local math evaluator covers only the documented IF/FILL/arithmetic subset.
It tests absent operands without claiming CloudWatch delivery/evaluation evidence.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

import model
import retired
import wp5
import wp5_iam
from source import attributes, blocks
from test_wp4d import permits

ROOT = Path(__file__).resolve().parents[3]
DOC = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
METRIC_ACTIONS = {"autoscaling:EnableMetricsCollection", "autoscaling:DisableMetricsCollection"}
ECS = "apps/modules/ecs_service/alarm_ecs_service.tf"
ALB = "global/modules/alb/alarms_tg.tf"
EXPECTED = {
    ECS: {"ecs_tasks_gap"},
    "data/ordinary-main.tf": {"statuscheck_failed", "cpu_credit_low", "cpu_high"},
    ALB: {"tg_blue_5xx", "tg_green_5xx", "tg_blue_latency", "tg_green_latency"},
    "global/wp5-nat-alarms-a.tf": {"nat_a_inservice_low", "nat_a_capacity_gap"},
    "global/wp5-nat-alarms-b.tf": {"nat_b_inservice_low", "nat_b_capacity_gap"},
}


def read(env, name):
    return (ROOT / "terraform/modules/target" / env / name).read_text()


def alarms(text):
    return {label: body for kind, resource, label, body in blocks(text)[0]
            if kind == "resource" and resource == "aws_cloudwatch_metric_alarm"}


def attrs(body):
    return attributes(blocks(body)[1])


def metrics(body):
    result = {}
    for kind, _, _, query in blocks(body)[0]:
        if kind != "metric_query":
            continue
        label = json.loads(attrs(query)["id"])
        nested = blocks(query)[0]
        result[label] = (attrs(nested[0][3]) if nested else attrs(query))
    return result


def dimensions(metric):
    return attributes(metric["dimensions"][1:-1])


def math_value(expression, values):
    """Execute the actual expression with documented missing-value semantics."""
    node = ast.parse(expression.replace(" AND ", " and "), mode="eval").body
    def evaluate(n):
        if isinstance(n, ast.Name):
            return values[n.id]
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -evaluate(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id == "FILL" and len(n.args) == 2:
                value = evaluate(n.args[0])
                return evaluate(n.args[1]) if value is None else value
            if n.func.id == "IF" and len(n.args) == 2:
                return evaluate(n.args[1]) if evaluate(n.args[0]) else None
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.And):
            return all(evaluate(v) for v in n.values)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.GtE):
            return (evaluate(n.left) or 0) >= (evaluate(n.comparators[0]) or 0)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub):
            return (evaluate(n.left) or 0) - (evaluate(n.right) or 0)
        raise ValueError("Unsupported documented math subset: " + ast.dump(n))
    return evaluate(node)


class Monitoring(unittest.TestCase):
    def test_ecs_documented_metrics_dimensions_and_collection(self):
        for env in ("dev", "prod"):
            with self.subTest(env=env):
                alarm = alarms(read(env, ECS))["ecs_tasks_gap"]
                queries = metrics(alarm)
                self.assertEqual(set(queries), {"m_running", "m_desired", "e_gap"})
                for label, metric_name in (("m_running", "RunningTaskCount"), ("m_desired", "DesiredTaskCount")):
                    metric = queries[label]
                    self.assertEqual(json.loads(metric["namespace"]), "ECS/ContainerInsights")
                    self.assertEqual(json.loads(metric["metric_name"]), metric_name)
                    self.assertEqual(metric["period"], "60")
                    self.assertEqual(metric["stat"], '"Average"')
                    self.assertEqual(dimensions(metric), {
                        "ClusterName": 'var.cluster_arn != null ? split("/", var.cluster_arn)[1] : ""',
                        "ServiceName": "aws_ecs_service.this.name"})
                cluster = read(env, "platform/modules/ecs_cluster/main.tf")
                setting = blocks(blocks(cluster)[0][0][3])[0][0][3]
                self.assertEqual(attrs(setting), {"name": '"containerInsights"', "value": '"enabled"'})
                # Both supported colors consume the same corrected service module.
                modules = blocks(read(env, "apps/ordinary-demo.tf"))[0]
                self.assertEqual({label for kind, label, _, body in modules if kind == "module"},
                                 {"demo_api_blue", "demo_api_green"})
                self.assertTrue(all(attrs(body)["source"] == '"./modules/ecs_service"' for _, _, _, body in modules))

    def test_nat_collection_metrics_dimensions_and_gates(self):
        for env in ("dev", "prod"):
            asg = json.loads(read(env, "global/wp5-nat.tf.json"))["resource"]["aws_autoscaling_group"]["wp5_nat"]
            self.assertEqual(asg["enabled_metrics"], ["GroupDesiredCapacity", "GroupInServiceInstances"])
            self.assertEqual(asg["metrics_granularity"], "1Minute")
            self.assertEqual(asg["for_each"], "${var.protected_nat_launch}")
            for side in ("a", "b"):
                for label, body in alarms(read(env, "global/wp5-nat-alarms-" + side + ".tf")).items():
                    values = attrs(body)
                    self.assertEqual(values["count"], 'contains(keys(var.protected_nat_launch), "' + side + '") ? 1 : 0')
                    samples = [values] if label.endswith("_low") else [v for v in metrics(body).values() if "metric_name" in v]
                    self.assertEqual({json.loads(v["metric_name"]) for v in samples},
                        {"GroupInServiceInstances"} if label.endswith("_low") else set(asg["enabled_metrics"]))
                    for sample in samples:
                        self.assertEqual(json.loads(sample["namespace"]), "AWS/AutoScaling")
                        self.assertEqual(sample["period"], "60")
                        self.assertEqual(dimensions(sample), {"AutoScalingGroupName": 'aws_autoscaling_group.wp5_nat["' + side + '"].name'})

    def test_missing_data_gauges_unknown_sparse_errors_nonbreaching(self):
        for env in ("dev", "prod"):
            for name in EXPECTED:
                for label, body in alarms(read(env, name)).items():
                    policy = json.loads(attrs(body).get("treat_missing_data", '"missing"'))
                    self.assertEqual(policy, "notBreaching" if label.endswith("_5xx") else "missing", (env, name, label))
                    self.assertEqual(attrs(body)["alarm_actions"], "[var.alerts_topic_arn]")
                    self.assertEqual(attrs(body)["ok_actions"], "[var.alerts_topic_arn]")
                    self.assertNotIn("insufficient_data_actions", attrs(body))

    def test_math_missing_either_operand_never_becomes_zero_gap(self):
        for env in ("dev", "prod"):
            for name, label, query, desired, running in (
                (ECS, "ecs_tasks_gap", "e_gap", "m_desired", "m_running"),
                ("global/wp5-nat-alarms-a.tf", "nat_a_capacity_gap", "gap", "desired", "inservice"),
                ("global/wp5-nat-alarms-b.tf", "nat_b_capacity_gap", "gap", "desired", "inservice")):
                expression = json.loads(metrics(alarms(read(env, name))[label])[query]["expression"])
                for left, right, expected in ((1, 1, 0), (1, 0, 1), (0, 0, 0), (0, 1, -1),
                                              (None, 1, None), (1, None, None), (None, None, None),
                                              (None, 0, None), (0, None, None)):
                    self.assertEqual(math_value(expression, {desired: left, running: right}), expected)
                # Control: the retired expression silently produces a false zero.
                self.assertEqual(math_value(desired + " - " + running, {desired: None, running: 0}), 0)

    def test_no_alarm_removed_or_added_and_non_e7_fields_preserved(self):
        originals = {
            ECS: "terraform/infra/apps/fargate/modules/ecs_service/alarm_ecs_service.tf",
            ALB: "terraform/infra/global/modules/alb/alarms_tg.tf",
            "data/ordinary-main.tf": "terraform/infra/data/main.tf"}
        for env in ("dev", "prod"):
            found = {}
            for path in (ROOT / "terraform/modules/target" / env).rglob("*.tf"):
                names = set(alarms(path.read_text()))
                if names:
                    found[path.relative_to(ROOT / "terraform/modules/target" / env).as_posix()] = names
            self.assertEqual(found, EXPECTED)
            for name, original in originals.items():
                before = alarms(retired.source(ROOT, original).read_text())
                after = alarms(read(env, name))
                for label in before:
                    # Namespace, expression and missing policy are the only ECS
                    # differences; dimensions, thresholds/actions/counts stay fixed.
                    def normalize(body):
                        return re.sub(r'(?m)^\s*(namespace|expression|treat_missing_data)\s*=.*$', '', body).strip()
                    self.assertEqual(normalize(before[label]), normalize(after[label]))

    def test_generation_package_identity_and_dev_prod_consistency(self):
        generated = model.wiring(DOC)
        for env in ("dev", "prod"):
            for name in EXPECTED:
                self.assertEqual(read(env, name), generated["terraform/modules/target/" + env + "/" + name])
                self.assertEqual(alarms(read("dev", name)), alarms(read("prod", name)))
            for name, content in wp5.package_files(ROOT, DOC, "environment-lifecycle/infra-" + env).items():
                if name.startswith("terraform/modules/target/"):
                    actual = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
                    if name.endswith(".tf.json"):
                        self.assertEqual(json.loads(actual), json.loads(content))
                    else:
                        self.assertEqual(actual, content)
        self.assertEqual(DOC["wp5"], wp5.contract(ROOT, DOC))
        self.assertEqual(model.validate_repository(ROOT), DOC)

    def test_metric_authority_is_bounded_to_fixed_tagged_nat_names(self):
        policies = {}
        for key in wp5.BINDINGS:
            env = key.rsplit("-", 1)[1]
            members = {kind: [kind + "-EXACT-MEMBER"] for kind in wp5_iam.INVENTORY}
            members["_sql_launch"] = {"image": "EXACT_IMAGE", "subnet": "EXACT_SUBNET", "security_group": "EXACT_SG", "instance_type": "t3a.small"}
            policy = wp5_iam.policy(key, "123456789012", "us-east-1", members, "a" * 64, "EXACT_VERSION")
            grants = [s for s in policy["Statement"] if METRIC_ACTIONS & set(s["Action"])]
            if key.startswith("request-gateway/"):
                self.assertEqual(grants, [])
            else:
                self.assertEqual(len(grants), 1)
                self.assertEqual(set(grants[0]["Action"]), METRIC_ACTIONS)
                self.assertEqual(grants[0]["Resource"], [f"arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:*:autoScalingGroupName/demo-{env}-asg-nat-{side}" for side in ("a", "b")])
                self.assertEqual(grants[0]["Condition"], {"StringEquals": {"autoscaling:ResourceTag/Environment": env}})
                for action in METRIC_ACTIONS:
                    arn = f"arn:aws:autoscaling:us-east-1:123456789012:autoScalingGroup:EXACT_ID:autoScalingGroupName/demo-{env}-asg-nat-a"
                    self.assertTrue(permits(policy, action, arn, {"autoscaling:ResourceTag/Environment": env}))
                    self.assertFalse(permits(policy, action, arn))
                    self.assertFalse(permits(policy, action, arn, {"autoscaling:ResourceTag/Environment": "other"}))
                    for bad in (arn + "-other", arn.replace("-nat-a", "-nat-c"), arn.replace("123456789012", "999999999999"), arn.replace("us-east-1", "us-west-2"), arn.replace("demo-" + env, "demo-other")):
                        self.assertFalse(permits(policy, action, bad, {"autoscaling:ResourceTag/Environment": env}))
            policies[key] = {**policy, "Statement": [s for s in policy["Statement"] if not METRIC_ACTIONS & set(s["Action"])]}
        # Baseline cc223d8 policies: no other action/resource/condition changed.
        self.assertEqual(hashlib.sha256(json.dumps(policies, sort_keys=True).encode()).hexdigest(),
                         "26ca1c7ae15602e3f7fa1a5eda1c83ddfe54263bc0664d4781ee3bea03db9c0a")

    def test_protected_security_contracts_unchanged_except_package_digests(self):
        doc = copy.deepcopy(DOC)
        for kind in ("wp4d", "wp5"):
            for value in doc[kind]["selected"].values():
                value.pop("package_sha256")
        # Integrated 72141a7 authority, excluding only source-derived WP4D/WP5 hashes.
        # Their exact current values are independently checked by model.validate_repository.
        self.assertEqual(hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(),
                         "588f99a5cdfe3ef9c01b6577fa9f2d94d6f879f597737a07b31925a4b328d0f7")
        self.assertEqual(doc["wp6"]["approvals"], {})
        for kind in ("wp4d", "wp5"):
            for field in ("installations", "runtime_approvals", "environment_bindings"):
                self.assertEqual(doc[kind][field], {})
        for env in ("dev", "prod"):
            service = read(env, "apps/modules/ecs_service/service.tf")
            self.assertIn("desired_count", service)
            self.assertIn("ignore_changes", service)
            self.assertIn("task_definition", service)
