"""Exact positive and negative WP4D authority tuples; no AWS calls."""
import fnmatch
import hashlib
import json
import base64
from pathlib import Path
import io
import tempfile
import unittest
from evaluator import condition

import wp4d
from scripts.wp4d import gateway
from scripts.wp4d.installed import load
from scripts.wp4d.adapters import RecoveryObjects
from scripts.wp4d.aws_runtime import Observer, Effects, Delivery
from scripts.wp4d.nat_resolver import Resolver
from scripts.normal_delivery import authorization as auth

ROOT = Path(__file__).resolve().parents[3]
ACCOUNT = "123456789012"
REGION = "us-east-1"


def fixture(env):
    arn = lambda service, kind, name: f"arn:aws:{service}:{REGION}:{ACCOUNT}:{kind}/{name}"
    cluster_name = f"demo-{env}-ecs-cluster"
    colors = {}
    for color in ("blue", "green"):
        service = f"demo-{env}-app-api-{color}-svc"
        colors[color] = {
            "service_arn": arn("ecs", "service", cluster_name + "/" + service),
            "target_group": arn("elasticloadbalancing", "targetgroup", f"demo-{env}-{color}/abc123"),
            "family": f"demo-{env}-app-api-{color}",
            "task_role": f"arn:aws:iam::{ACCOUNT}:role/demo-{env}-app-api-{color}-task-role",
            "execution_role": f"arn:aws:iam::{ACCOUNT}:role/demo-{env}-app-api-{color}-exec-role",
        }
    return {"package_sha256": "a" * 64, "name": f"e1-controller-{env}",
            "project": f"e1-controller-{env}", "cluster_name": cluster_name,
            "cluster_arn": arn("ecs", "cluster", cluster_name), "colors": colors,
            "listener": arn("elasticloadbalancing", "listener", f"app/demo-{env}-alb/abc/def"),
            "candidate_rule": arn("elasticloadbalancing", "listener-rule", f"app/demo-{env}-alb/abc/def/ghi"),
            "cleanup": {"rule_arn": arn("events", "rule", f"demo-{env}-scale-down-old-color-rule"),
                        "function_arn": f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-cleanup-recovery-cleanup-{env}:wp4d"},
            "repository": "demo-shared-demo-ms",
            "nat_slots": [{"eip": f"eipalloc-{i}", "route_table": f"rtb-{i}",
                           "subnet": f"subnet-{i}",
                           "instance_profile": f"arn:aws:iam::{ACCOUNT}:instance-profile/demo-{env}-nat-{i}"}
                          for i in (1, 2)]}


def permits(policy, action, resource, context=None):
    context = context or {}
    allowed = False
    for statement in policy["Statement"]:
        if action not in statement["Action"] or not any(
                fnmatch.fnmatchcase(resource, pattern) for pattern in statement["Resource"]):
            continue
        # WP1 deliberately has a smaller service-key registry. Reuse its
        # tested operator/set/null semantics with explicit fixture aliases;
        # AWS key applicability is documented separately, never inferred here.
        facts = {key.lower(): value for key, value in context.items()}
        matches_conditions = all(condition({operator: {'fixture:k': expected}},
            {'fixture:k': facts[key.lower()]} if key.lower() in facts else {})
            for operator, fields in statement.get("Condition", {}).items()
            for key, expected in fields.items())
        if matches_conditions:
            if statement["Effect"] == "Deny":
                return False
            allowed = True
    return allowed


def policy(binding):
    resources = fixture(wp4d.RESERVED[binding][0])
    if binding.startswith("request-gateway/"):
        resources["project"] = "e1-controller-" + binding.split("/", 1)[1]
    return wp4d.policy(binding, resources, ACCOUNT, REGION, "version-1")


def installed_projection(authority):
    installs, images, bindings = {}, {}, {}
    for key, selected in authority["wp4d"]["selected"].items():
        digest = selected["package_sha256"]
        installs[key] = {"binding": key, "sha256": digest,
                         "bucket": f"e1-control-bundles-{ACCOUNT}-{REGION}",
                         "key": f"bundles/sha256/{digest}.json", "version_id": "exact-v1",
                         "installation": "VERIFIED", "readback": "EXACT_VERSION_BYTES_VERIFIED",
                         "version_origin": "CONDITIONAL_WRITE_RETURN",
                         "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}
        repository = "e1-wp4d-" + key.replace("/", "-").replace("_", "-")
        images[key] = {"binding": key, "owner": "SECURITY_ROOT_OWNED",
                       "approval": "ADMIN_VERIFIED", "package_sha256": digest,
                       "uri": f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{repository}@sha256:" + "a"*64}
    for env in ("dev", "prod"):
        base = fixture(env)
        colors = {}
        for color in ("blue", "green"):
            colors[color] = {"cluster": base["cluster_arn"],
                             "service": f"demo-{env}-app-api-{color}-svc",
                             "listener": base["listener"], "candidate_rule": base["candidate_rule"],
                             "target_group": base["colors"][color]["target_group"],
                             "roles": {"task": base["colors"][color]["task_role"],
                                       "execution": base["colors"][color]["execution_role"]}}
            colors[color].update(secret_arn=f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/{env}/app/db-connection-string-ABC123",
                                 kms_key_arn=f"arn:aws:kms:{REGION}:{ACCOUNT}:key/12345678-1234-1234-1234-123456789abc",
                                 log_group=f"/aws/ecs/demo-{env}-app-api-{color}",
                                 subnets=["subnet-12345678", "subnet-abcdef12"],
                                 security_groups=["sg-12345678"])
        slots = []
        for i in (1,2):
            slots.append({"environment": env, "account": ACCOUNT, "region": REGION,
                          "asg": f"demo-{env}-nat-{i}", "az": f"{REGION}{chr(96+i)}",
                          "vpc": "vpc-12345678", "subnet": f"subnet-{i:08x}",
                          "eip": f"eipalloc-{i:08x}", "route_table": f"rtb-{i:08x}",
                          "spec": {"instance_profile": f"arn:aws:iam::{ACCOUNT}:instance-profile/demo-{env}-nat-instance-profile",
                                   "role": f"arn:aws:iam::{ACCOUNT}:role/demo-{env}-nat-role",
                                   "launch_template_version": 3,
                                   "ami": "ami-12345678", "launch_template": f"lt-{i:08x}",
                                   "user_data_sha256": hashlib.sha256(b"approved").hexdigest(),
                                   "security_groups": ["sg-12345678"], "http_tokens": "required",
                                   "instance_type": "t3.micro", "associate_public_ip": True,
                                   "delete_on_termination": True,
                                   "tags": {"Environment": env, "Role": "nat"}}})
        bindings[env] = {"schema": "E1_WP4D_PROTECTED_ENVIRONMENT_V1",
                         "owner": "SECURITY_ROOT_OWNED", "environment": env,
                         "account": ACCOUNT, "region": REGION, "repository": base["repository"],
                         "colors": colors,
                         "cleanup": {"rule": f"demo-{env}-scale-down-old-color-rule",
                                     "function_arn": base["cleanup"]["function_arn"], "expression": "rate(5 minutes)"},
                         "nat_slots": slots}
    return installs, images, bindings


class Authority(unittest.TestCase):
    def test_exact_normal_dev_and_prod_passrole(self):
        for env, suffix in (("dev", "deploy-dev"), ("prod", "promote-prod")):
            p, resources = policy("normal-delivery/" + suffix), fixture(env)
            exact = resources["colors"]["blue"]["task_role"]
            self.assertTrue(permits(p, "iam:PassRole", exact,
                                    {"iam:PassedToService": "ecs-tasks.amazonaws.com"}))
            self.assertFalse(permits(p, "iam:PassRole", exact,
                                     {"iam:PassedToService": "lambda.amazonaws.com"}))
            self.assertFalse(permits(p, "iam:PassRole", fixture("prod" if env == "dev" else "dev")["colors"]["blue"]["task_role"],
                                     {"iam:PassedToService": "ecs-tasks.amazonaws.com"}))
            self.assertFalse(permits(p, "iam:PassRole", f"arn:aws:iam::{ACCOUNT}:role/unrelated",
                                     {"iam:PassedToService": "ecs-tasks.amazonaws.com"}))

    def test_normal_service_routing_and_registration(self):
        for env, suffix in (("dev", "deploy-dev"), ("prod", "promote-prod")):
            p, r = policy("normal-delivery/" + suffix), fixture(env)
            self.assertTrue(permits(p, "ecs:RegisterTaskDefinition",
                                    f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/demo-{env}-app-api-blue:8"))
            self.assertTrue(permits(p, "ecs:UpdateService", r["colors"]["green"]["service_arn"]))
            self.assertTrue(permits(p, "elasticloadbalancing:ModifyListener", r["listener"]))
            self.assertTrue(permits(p, "elasticloadbalancing:ModifyRule", r["candidate_rule"]))
            self.assertTrue(permits(p, "events:PutTargets", r["cleanup"]["rule_arn"],
                                    {"events:TargetArn": r["cleanup"]["function_arn"]}))
            self.assertFalse(permits(p, "events:PutTargets", r["cleanup"]["rule_arn"],
                                     {"events:TargetArn": "arn:aws:lambda:us-east-1:123456789012:function:foreign"}))
            for action in ("ecs:RunTask", "ecs:StartTask", "ecs:ExecuteCommand",
                           "iam:CreateRole", "codebuild:UpdateProject"):
                self.assertFalse(permits(p, action, "*"))
            foreign = fixture("prod" if env == "dev" else "dev")
            self.assertFalse(permits(p, "ecs:UpdateService", foreign["colors"]["blue"]["service_arn"]))
            self.assertFalse(permits(p, "elasticloadbalancing:ModifyListener", foreign["listener"]))
            self.assertFalse(permits(p, "elasticloadbalancing:ModifyRule", foreign["candidate_rule"]))

    def test_normal_cannot_write_admin_records(self):
        for suffix in ("deploy-dev", "promote-prod"):
            p = policy("normal-delivery/" + suffix)
            for prefix in ("qualifications", "eligibility", "membership", "bindings", "prod-approvals"):
                self.assertFalse(permits(p, "s3:PutObject",
                    f"arn:aws:s3:::demo-release-artifacts-{ACCOUNT}/{prefix}/x.json",
                    {"s3:if-none-match": "*"}))

    def test_emergency_has_only_existing_content_authority(self):
        for env in ("dev", "prod"):
            p, r = policy(f"emergency-recovery/emergency-{env}"), fixture(env)
            self.assertTrue(permits(p, "ecs:UpdateService", r["colors"]["blue"]["service_arn"]))
            self.assertTrue(permits(p, "elasticloadbalancing:ModifyListener", r["listener"]))
            for action in ("ecs:RegisterTaskDefinition", "iam:PassRole", "ecr:PutImage",
                           "ecs:RunTask", "ecs:StartTask", "iam:UpdateRole"):
                self.assertFalse(permits(p, action, "*"))
            self.assertFalse(permits(p, "ecs:UpdateService",
                fixture("prod" if env == "dev" else "dev")["colors"]["blue"]["service_arn"]))

    def test_cleanup_exact_rule_and_service(self):
        for env in ("dev", "prod"):
            p, r = policy(f"cleanup-recovery/cleanup-{env}"), fixture(env)
            self.assertTrue(permits(p, "ecs:UpdateService", r["colors"]["green"]["service_arn"]))
            self.assertTrue(permits(p, "events:RemoveTargets", r["cleanup"]["rule_arn"]))
            self.assertFalse(permits(p, "events:RemoveTargets", fixture("prod" if env == "dev" else "dev")["cleanup"]["rule_arn"]))
            for action in ("ecs:RegisterTaskDefinition", "iam:PassRole", "elasticloadbalancing:ModifyListener"):
                self.assertFalse(permits(p, action, "*"))

    def test_nat_three_distinct_mutation_verb_sets(self):
        exact = {"assign_eip": {"ec2:AssociateAddress"},
                 "change_rt": {"ec2:CreateRoute", "ec2:ReplaceRoute"},
                 "disable_sdc": {"ec2:ModifyInstanceAttribute"}}
        for env in ("dev", "prod"):
            for handler, verbs in exact.items():
                p = policy(f"nat-recovery/nat-{env}/{handler}")
                present = {action for statement in p["Statement"] for action in statement["Action"]}
                self.assertEqual(present & set().union(*exact.values()), verbs)
                self.assertIn("iam:GetInstanceProfile", present)
                self.assertTrue(permits(p, "iam:GetInstanceProfile",
                    fixture(env)["nat_slots"][0]["instance_profile"]))
                self.assertFalse(permits(p, "iam:GetInstanceProfile",
                    fixture("prod" if env == "dev" else "dev")["nat_slots"][0]["instance_profile"]))
                if handler == "change_rt":
                    exact_rt = f"arn:aws:ec2:{REGION}:{ACCOUNT}:route-table/rtb-1"
                    self.assertTrue(permits(p, "ec2:ReplaceRoute", exact_rt))
                    self.assertFalse(permits(p, "ec2:ReplaceRoute",
                                             f"arn:aws:ec2:{REGION}:{ACCOUNT}:route-table/rtb-foreign"))
                if handler == "assign_eip":
                    exact_eip = f"arn:aws:ec2:{REGION}:{ACCOUNT}:elastic-ip/eipalloc-1"
                    self.assertTrue(permits(p, "ec2:AssociateAddress", exact_eip))
                    self.assertFalse(permits(p, "ec2:AssociateAddress",
                                             f"arn:aws:ec2:{REGION}:{ACCOUNT}:elastic-ip/eipalloc-foreign"))

    def test_gateway_invocation_exact_per_environment_and_kind(self):
        for suffix in ("deploy-dev", "promote-prod", "emergency-dev", "emergency-prod"):
            p = policy("request-gateway/" + suffix)
            env = "prod" if suffix.endswith("prod") else "dev"
            project = f"arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-{suffix}"
            self.assertTrue(permits(p, "codebuild:StartBuild", project))
            self.assertFalse(permits(p, "codebuild:StartBuild", project + "-foreign"))

    def test_request_closure(self):
        envelope = {"operation_id": "123e4567-e89b-42d3-a456-426614174000", "body": "{}"}
        self.assertEqual(gateway.request("emergency", envelope)[1], {})
        for body in ('{"release_id":"x"}', '{"ready":true}', '{"service":"x"}'):
            with self.assertRaises(ValueError): gateway.request("emergency", {**envelope, "body": body})
        with self.assertRaises(ValueError): gateway.request("emergency", {**envelope, "environment": "prod"})

    def test_cleanup_schedule_preserves_native_event_envelope(self):
        class Records:
            def create(self, key, raw): self.last = (key, raw)
        class Events:
            def put_rule(self, **args): self.rule = args
            def put_targets(self, **args):
                self.target = args
                return {"FailedEntryCount": 0}
        resources = {"environment": "dev",
                     "colors": {"blue": {"cluster": "exact-cluster", "service": "exact-blue"}},
                     "cleanup": {"rule": "exact-rule", "expression": "rate(5 minutes)",
                                 "function_arn": "exact-function"}}
        events, records = Events(), Records()
        transport = Delivery(None, None, events, records, resources)
        transport.cleanup("dev/op/cleanup", {"environment": "dev", "cluster": "exact-cluster",
                                             "service": "exact-blue"}, transport.now() + 30)
        self.assertEqual(events.target["Targets"], [{"Id": "scale-down", "Arn": "exact-function"}])

    def test_bundle_deterministic_and_source_bound(self):
        authority = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
        for binding, selected in authority["wp4d"]["selected"].items():
            raw = wp4d.artifact(ROOT, authority["control_bundles"], binding)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), selected["package_sha256"])
            self.assertEqual(raw, wp4d.artifact(ROOT, authority["control_bundles"], binding))
            package = json.loads(raw)
            self.assertEqual(package["binding"], binding)
            self.assertIn("scripts/normal_delivery/authorization.py", package["files"])
            self.assertIn("scripts/normal_delivery/delivery.py", package["files"])

    def test_exact_version_install_readback(self):
        authority = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
        binding = "cleanup-recovery/cleanup-dev"
        raw = wp4d.artifact(ROOT, authority["control_bundles"], binding)
        digest = hashlib.sha256(raw).hexdigest()
        reference = {"bucket": "protected", "key": f"bundles/sha256/{digest}.json",
                     "version_id": "exact-version", "sha256": digest, "binding": binding}
        class Store:
            def __init__(self, payload, version): self.payload, self.version = payload, version
            def get_object(self, **args):
                self.args = args
                return {"Body": io.BytesIO(self.payload), "VersionId": self.version}
        with tempfile.TemporaryDirectory() as directory:
            store = Store(raw, "exact-version")
            self.assertEqual(load(store, reference, directory)["binding"], binding)
            self.assertEqual(store.args["VersionId"], "exact-version")
        for payload, version in ((raw + b" ", "exact-version"), (raw, "wrong-version")):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError): load(Store(payload, version), reference, directory)

    def test_selected_compute_and_external_inert(self):
        authority = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
        self.assertEqual(len(authority["wp4d"]["selected"]), 16)
        self.assertEqual(authority["wp4d"]["installations"], {})
        self.assertEqual(authority["wp4d"]["runtime_approvals"], {})
        self.assertEqual(authority["wp4d"]["external_invocation"], [])
        self.assertTrue(all(x["stage"] == "INERT" for x in authority["request_identities"].values()))

    def test_service_trust_and_no_external_invocation(self):
        tf = json.loads((ROOT / "terraform/infra/security/modules/controller_compute/main.tf.json").read_text())
        templates = tf["locals"]["wp4d_policy_templates"]
        self.assertEqual(tf["resource"]["aws_iam_role_policy"]["wp4d"]["depends_on"],
                         ["aws_iam_role.execution", "aws_iam_role.wp4d_reserved"])
        self.assertEqual(set(templates), set(wp4d.RESERVED))
        self.assertTrue(all("${var.account_id}" not in value and
                            "${var.region}" not in value for value in templates.values()))
        self.assertIn('"__ACCOUNT__", var.account_id',
                      tf["resource"]["aws_iam_role_policy"]["wp4d"]["policy"])
        role = tf["resource"]["aws_iam_role"]
        self.assertIn("lambda.amazonaws.com", role["wp4d_reserved"]["assume_role_policy"])
        self.assertIn("codebuild.amazonaws.com", role["execution"]["assume_role_policy"])
        self.assertNotIn("token.actions.githubusercontent.com", json.dumps(role))
        self.assertNotIn('"AWS":', json.dumps(role))
        permissions = tf["resource"]["aws_lambda_permission"]
        self.assertTrue({"wp4d_cleanup", "wp4d_nat"} <= set(permissions))
        self.assertEqual(permissions["wp4d_cleanup"]["principal"], "events.amazonaws.com")

    def test_wp4d_activation_gates_and_live_membership_adapter(self):
        tf = json.loads((ROOT / "terraform/infra/security/modules/controller_compute/main.tf.json").read_text())
        gate = tf["locals"]["wp4d_ready"]
        for marker in ("EXACT_VERSION_BYTES_VERIFIED", "ADMIN_VERIFIED", "package_sha256",
                       "instance_profile", "targetgroup/demo-", "roles.task"):
            self.assertIn(marker, gate)
        source = (ROOT / "scripts/wp4d/aws_runtime.py").read_text()
        self.assertIn('target_id == target_id.strip()', source)
        self.assertIn('== required', source)
        self.assertIn('len(deployments) == 1', source)

    def test_selective_compute_projection_positive_and_cross_env_negative(self):
        authority = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
        installs, images, bindings = installed_projection(authority)
        evaluate = lambda i, r, b: wp4d.creation_supported(authority, i, r, b, ACCOUNT, REGION)
        self.assertEqual(evaluate({}, {}, {}), [])
        self.assertEqual(len(evaluate(installs, images, bindings)), 16)
        self.assertEqual(evaluate({k:v for k,v in installs.items() if k.startswith("nat-recovery/nat-dev/")},
                                  images, bindings),
                         sorted(k for k in authority["wp4d"]["selected"] if k.startswith("nat-recovery/nat-dev/")))
        wrong = json.loads(json.dumps(bindings))
        wrong["dev"]["colors"]["blue"]["roles"]["task"] = fixture("prod")["colors"]["blue"]["task_role"]
        self.assertTrue(all("dev" not in key for key in evaluate(installs, images, wrong)))
        wrong = json.loads(json.dumps(bindings))
        wrong["prod"]["colors"]["green"]["target_group"] = fixture("dev")["colors"]["green"]["target_group"]
        self.assertTrue(all("prod" not in key for key in evaluate(installs, images, wrong)))


class Membership(unittest.TestCase):
    def assert_denied_get_requires_independent_complete_exact_prefix_absence(self):
        from scripts.wp4d.dev_nat_objects import NatObjects as Objects
        class Denied(Exception):
            response = {"Error": {"Code": "AccessDenied"}}
        class Store:
            def __init__(self): self.entries=[];self.truncated=False;self.denied=False;self.calls=[]
            def get_object(self, **kw): raise Denied()
            def list_objects_v2(self, **kw):
                self.calls.append(kw)
                if self.denied: raise Denied()
                return {"Prefix":kw["Prefix"],"IsTruncated":self.truncated,"Contents":self.entries}
        s3=Store();records=Objects(s3,"protected","recovery/")
        self.assertIsNone(records.read("dev/recovery/assign_eip/op/intent"))
        self.assertEqual(s3.calls,[{"Bucket":"protected","Prefix":"recovery/dev/recovery/assign_eip/op/intent","MaxKeys":2}])
        s3.entries=[{"Key":s3.calls[0]["Prefix"]}]
        with self.assertRaises(Denied): records.read("dev/recovery/assign_eip/op/intent")
        s3.entries=[];s3.truncated=True
        with self.assertRaises(ValueError): records.read("dev/recovery/assign_eip/op/intent")
        s3.truncated=False;s3.denied=True
        with self.assertRaises(Denied): records.read("dev/recovery/assign_eip/op/intent")

    def test_recovery_journal_and_wp4b_receipt_use_distinct_protected_paths(self):
        self.assert_denied_get_requires_independent_complete_exact_prefix_absence()
        class Store:
            def __init__(self): self.items = {}
            def put_object(self, **kw):
                self.items[kw["Key"]] = kw["Body"]
            def get_object(self, **kw):
                return {"Body": io.BytesIO(self.items[kw["Key"]]), "VersionId": "exact"}
        s3 = Store()
        s3.items["delivery/dev/123e4567-e89b-42d3-a456-426614174000/success"] = b"proof"
        records = RecoveryObjects(s3, "protected", "dev")
        receipt = records.read("dev/123e4567-e89b-42d3-a456-426614174000/success")
        self.assertEqual(receipt["bytes"], b"proof")
        records.create("dev/recovery/emergency/op/intent", b"journal")
        self.assertEqual(s3.items["recovery/dev/recovery/emergency/op/intent"], b"journal")
        with self.assertRaises(ValueError):
            records.create("dev/123e4567-e89b-42d3-a456-426614174000/success", b"forged")

    def test_health_is_exact_task_ip_set(self):
        class ELB:
            def __init__(self, ids): self.ids = ids
            def describe_target_health(self, **kw):
                return {"TargetHealthDescriptions": [{"Target": {"Id": value, "Port": 8080},
                         "TargetHealth": {"State": "healthy"}} for value in self.ids]}
        config = {"colors": {"blue": {"target_group": "exact"}}}
        tasks = [{"lastStatus": "RUNNING", "attachments": [{"type": "ElasticNetworkInterface",
                  "status": "ATTACHED", "details": [{"name": "privateIPv4Address", "value": "10.0.1.2"}]}]}]
        self.assertEqual(Observer(None, ELB(["10.0.1.2"]), config).targets("blue", tasks),
                         [{"id": "10.0.1.2", "state": "healthy"}])
        for ids in ([""], [" "], ["10.0.1.3"], ["10.0.1.2", "10.0.1.3"]):
            with self.assertRaises(ValueError): Observer(None, ELB(ids), config).targets("blue", tasks)

    def test_attempt_without_ack_never_resends_or_succeeds(self):
        class Records:
            def __init__(self): self.items = {"dev/op/scale/attempt": b"attempt"}
            def read(self, key):
                return {"bytes": self.items[key]} if key in self.items else None
            def create(self, key, raw):
                if key in self.items: raise ValueError("duplicate")
                self.items[key] = raw
        class Port(Effects):
            def __init__(self, records):
                super().__init__(records)
                self.tick = 0
                self.observed = False
            def now(self):
                self.tick += 1
                return self.tick
            def verify_saved(self, token, request, result, deadline):
                return self.observed and result == request
        records = Records()
        port = Port(records)
        self.assertEqual(port.effect("dev/op/scale", 100)["state"], "UNKNOWN")
        request = {"desiredCount": 2}
        port.remembered("dev/op/scale", request, request, lambda: True)
        retry = Port(records)
        retry.observed = True
        self.assertEqual(retry.effect("dev/op/scale", 100), {
            "token": "dev/op/scale", "request_sha256": auth.sha(auth.canonical(request)),
            "state": "APPLIED", "result": request})
        self.assertEqual(len(records.items), 2)

    def test_nat_resolver_exact_role_eni_and_eip_relationship(self):
        env = "dev"
        slots = []
        for i in (1, 2):
            slots.append({"environment": env, "vpc": "vpc-1", "subnet": f"subnet-{i}",
                          "az": f"us-east-1{chr(96+i)}", "asg": f"demo-dev-nat-{i}",
                          "eip": f"eipalloc-{i}", "route_table": f"rtb-{i}",
                          "spec": {"ami": "ami-1", "launch_template": f"lt-{i}",
                                   "launch_template_version": 3,
                                   "user_data_sha256": hashlib.sha256(b"approved").hexdigest(),
                                   "instance_profile": f"arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-nat-{i}",
                                   "role": f"arn:aws:iam::{ACCOUNT}:role/demo-dev-nat-{i}",
                                   "security_groups": ["sg-1"], "http_tokens": "required",
                                   "associate_public_ip": True, "delete_on_termination": True,
                                   "instance_type": "t3.micro",
                                   "tags": {"Environment": "dev", "Role": "nat"}}})
        class AWS:
            def __init__(self):
                self.bad_role = False; self.bad_eni = False; self.bad_eip = False; self.bad_userdata = False; self.both = False
            def _slot(self, value):
                return slots[int(value.rsplit("-", 1)[-1]) - 1]
            def describe_auto_scaling_groups(self, AutoScalingGroupNames):
                slot = self._slot(AutoScalingGroupNames[0]); i = slot["asg"][-1]
                return {"AutoScalingGroups": [{"AutoScalingGroupName": slot["asg"],
                    "VPCZoneIdentifier": slot["subnet"], "Instances": [{"InstanceId": "i-" + i,
                    "LifecycleState": "InService", "HealthStatus": "Healthy",
                    "LaunchTemplate": {"LaunchTemplateId": slot["spec"]["launch_template"], "Version": "3"}}]}]}
            def describe_instances(self, InstanceIds):
                i = InstanceIds[0][-1]; slot = slots[int(i)-1]
                return {"Reservations": [{"Instances": [{"InstanceId": "i-" + i,
                    "State": {"Name": "running"}, "VpcId": slot["vpc"], "SubnetId": slot["subnet"],
                    "Placement": {"AvailabilityZone": slot["az"]}, "ImageId": "ami-1",
                    "InstanceType": "t3.micro", "IamInstanceProfile": {"Arn": slot["spec"]["instance_profile"]},
                    "MetadataOptions": {"HttpTokens": "required"}, "Tags": [
                        {"Key": k, "Value": v} for k,v in slot["spec"]["tags"].items()],
                    "SecurityGroups": [{"GroupId": "sg-1"}],
                    "NetworkInterfaces": [{"NetworkInterfaceId": "eni-" + i}]}]}]}
            def get_instance_profile(self, InstanceProfileName):
                slot = self._slot(InstanceProfileName)
                return {"InstanceProfile": {"Arn": slot["spec"]["instance_profile"],
                    "Roles": [{"Arn": ("arn:aws:iam::" + ACCOUNT + ":role/foreign") if self.bad_role
                               else slot["spec"]["role"]}]}}
            def describe_network_interfaces(self, NetworkInterfaceIds):
                i = NetworkInterfaceIds[0][-1]; slot = slots[int(i)-1]
                return {"NetworkInterfaces": [{"NetworkInterfaceId": "eni-" + i,
                    "VpcId": slot["vpc"], "SubnetId": slot["subnet"], "AvailabilityZone": slot["az"],
                    "Attachment": {"InstanceId": "i-foreign" if self.bad_eni else "i-" + i,
                                   "DeleteOnTermination": True}}]}
            def describe_launch_template_versions(self, LaunchTemplateId, Versions):
                return {"LaunchTemplateVersions": [{"VersionNumber": 3,
                    "LaunchTemplateData": {"UserData": base64.b64encode(b"approved").decode(),
                    "ImageId": "ami-1", "InstanceType": "t3.micro",
                    "IamInstanceProfile": {"Name": "demo-dev-nat-" + LaunchTemplateId[-1]},
                    "MetadataOptions": {"HttpTokens": "required"},
                    "NetworkInterfaces": [{"AssociatePublicIpAddress": True,
                                           "DeleteOnTermination": True, "Groups": ["sg-1"]}]}}]}
            def describe_addresses(self, AllocationIds):
                i = AllocationIds[0][-1]
                return {"Addresses": [{"AllocationId": "eipalloc-foreign" if self.bad_eip
                                       else "eipalloc-" + i,
                                       "Tags": [{"Key": "Environment", "Value": env}],
                                       "NetworkInterfaceId": None if i == "1" or self.both else "eni-2"}]}
            def describe_route_tables(self, RouteTableIds):
                i = RouteTableIds[0][-1]
                return {"RouteTables": [{"RouteTableId": RouteTableIds[0], "VpcId": "vpc-1",
                                        "Routes": [{"DestinationCidrBlock": "0.0.0.0/0",
                                                    "NetworkInterfaceId": "eni-" + i}]}]}
            def describe_instance_attribute(self, InstanceId, Attribute):
                if Attribute == 'userData':
                    return {"InstanceId": InstanceId, "UserData": {"Value": base64.b64encode(
                        b'foreign' if self.bad_userdata else b'approved').decode()}}
                return {"InstanceId": InstanceId, "SourceDestCheck": {"Value": False}}
        aws = AWS(); resolver = Resolver(env, slots)
        self.assertEqual(resolver.observe(aws, aws, aws, "assign_eip", 10)["membership"]["asg"],
                         slots[0]["asg"])
        for field in ("bad_role", "bad_eni", "bad_eip", "bad_userdata"):
            setattr(aws, field, True)
            with self.assertRaises(ValueError): resolver.observe(aws, aws, aws, "assign_eip", 10)
            setattr(aws, field, False)
        aws.both = True
        with self.assertRaises(ValueError): resolver.observe(aws, aws, aws, "assign_eip", 10)
        self.assertEqual(resolver.observe(aws, aws, aws, "assign_eip", 10,
                                          selected_asg=slots[1]["asg"])["membership"]["asg"],
                         slots[1]["asg"])
        with self.assertRaises(ValueError): resolver.observe(aws, aws, aws, "assign_eip", 10,
                                                            selected_asg="foreign-asg")
