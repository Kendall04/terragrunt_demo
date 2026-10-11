"""WP4D package and authority admission for the accepted WP4 controllers.

The empty installation and image-approval maps describe the undeployed repository.
Synthetic records in tests exercise creation gates; they are not AWS evidence.
"""
import base64
import hashlib
import json
from pathlib import Path
import re


OWNER = "SECURITY_ROOT_OWNED"
ROOT = Path(__file__).resolve().parents[3]

# Names for the eight WP2C nodes are read from that canonical reservation. The
# remaining names are the two WP2B reserved classes expanded by environment;
# NAT's three handlers deliberately get three independent execution identities.
RESERVED = {
    "request-gateway/deploy-dev": ("dev", "LAMBDA"),
    "request-gateway/promote-prod": ("prod", "LAMBDA"),
    "request-gateway/emergency-dev": ("dev", "LAMBDA"),
    "request-gateway/emergency-prod": ("prod", "LAMBDA"),
    "normal-delivery/deploy-dev": ("dev", "CODEBUILD"),
    "normal-delivery/promote-prod": ("prod", "CODEBUILD"),
    "emergency-recovery/emergency-dev": ("dev", "CODEBUILD"),
    "emergency-recovery/emergency-prod": ("prod", "CODEBUILD"),
    "cleanup-recovery/cleanup-dev": ("dev", "LAMBDA"),
    "cleanup-recovery/cleanup-prod": ("prod", "LAMBDA"),
    **{f"nat-recovery/nat-{env}/{action}": (env, "LAMBDA")
       for env in ("dev", "prod") for action in ("assign_eip", "change_rt", "disable_sdc")},
}

COMMON = (
    "scripts/normal_delivery/authorization.py",
    "scripts/normal_delivery/delivery.py",
    "scripts/normal_delivery/e3.py",
    "scripts/normal_delivery/model_consistency.py",
    "scripts/qualification/finalizer.py",
    "ci/authority/normal-delivery-model.json",
    "ci/schemas/release-manifest.schema.json",
    "ci/schemas/e1-qualification.schema.json",
    "demo-api/deploy/task-definition.template.json",
)
RECOVERY = (
    "scripts/recovery/application.py", "scripts/recovery/journal.py",
    "scripts/recovery/nat.py", "scripts/recovery/ports.py",
)
E3 = (
    "scripts/normal_delivery/e3-evidence.sh", "scripts/bounded-process.py",
    "scripts/ecs-readiness-gate.sh", "scripts/aws-response-boundary.sh",
    "scripts/alb-route-target.jq",
)
SUPPORT = (
    "scripts/environment_mutation.py",
    "scripts/wp4d/runtime.py", "scripts/wp4d/adapters.py",
    "scripts/wp4d/gateway.py", "scripts/wp4d/installed.py",
    "scripts/wp4d/aws_runtime.py", "scripts/wp4d/nat_resolver.py",
    "scripts/nat/reliability.py",
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def package_sources(binding):
    # The fixed bootstrap imports shared adapter modules. Include their closed
    # transitive dependencies for every binding; IAM and fixed configuration
    # still separate authority. Only normal delivery needs the Bash E3 payload.
    sources = list(SUPPORT + COMMON + RECOVERY)
    if binding.startswith("normal-delivery/"):
        sources += list(E3)
    return tuple(sorted(set(sources)))


def artifact(root, catalog, binding):
    if binding not in RESERVED:
        raise ValueError("WP4D_UNKNOWN_BINDING")
    reserved = binding.rsplit("/", 1)[0] if binding.startswith("nat-recovery/") else binding
    ref = catalog["consumer_references"][reserved]
    files = {}
    for relative in package_sources(binding):
        path = Path(root) / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError("WP4D_MISSING_OR_LINKED_SOURCE")
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        if len(raw) > 1048576 or b"\r" in raw or b"\x00" in raw:
            raise ValueError("WP4D_SOURCE_ENCODING_OR_SIZE")
        files[relative] = base64.b64encode(raw).decode("ascii")
    env, engine = RESERVED[binding]
    return canonical({"format": "E1_WP4D_BUNDLE_JSON_V1", "owner": OWNER,
                      "binding": binding, "reservation": reserved,
                      "reservation_sha256": ref["sha256"], "environment": env,
                      "engine": engine, "files": files,
                      "entrypoint": "scripts/wp4d/runtime.py"})


def selected(root, authority):
    catalog = authority["control_bundles"]
    nodes = authority["controller_compute"]["nodes"]
    result = {}
    for binding, (env, engine) in RESERVED.items():
        raw = artifact(root, catalog, binding)
        if binding in nodes:
            name, role = nodes[binding]["name"], nodes[binding]["role_name"]
        else:
            suffix = binding.replace("/", "-").replace("_", "-")
            name = "e1-" + suffix
            role = name + "-exec"
        if binding.startswith("request-gateway/"):
            suffix = binding.split("/", 1)[1]
            partner = ("emergency-recovery/" if suffix.startswith("emergency-") else
                       "normal-delivery/") + suffix
            dependencies = [partner, f"cleanup-recovery/cleanup-{env}"]
        elif binding.startswith(("normal-delivery/", "emergency-recovery/")):
            dependencies = ["request-gateway/" + binding.split("/", 1)[1],
                            f"cleanup-recovery/cleanup-{env}"]
        else:
            dependencies = []
        result[binding] = {"name": name, "role": role,
                           "engine": engine, "environment": env,
                           "reservation": binding.rsplit("/", 1)[0]
                           if binding.startswith("nat-recovery/") else binding,
                           "package_sha256": digest(raw),
                           "dependencies": dependencies}
    return result


def contract(root, authority):
    return {"schema": "E1_WP4D_MATERIALIZATION_V1", "owner": OWNER,
            "selected": selected(root, authority), "installations": {},
            "runtime_approvals": {}, "environment_bindings": {},
            "external_invocation": [], "live": "UNVERIFIED_NOT_DEPLOYED"}


def validate(root, authority):
    if authority.get("wp4d") != contract(root, authority):
        raise ValueError("WP4D_SOURCE_ADMISSION_FAILURE: package or materialization drift")
    return authority["wp4d"]


def install(root, authority, binding, account, region, storage):
    """Reuse WP2D's separately authenticated conditional-write/exact-read port.

    Only returned storage identities and readback bytes can create a receipt.
    This function does not select credentials or provide an AWS transport.
    """
    from publication import AdminBundleStorage
    if not isinstance(storage, AdminBundleStorage):
        raise ValueError("WP4D_ADMIN_STORAGE_REQUIRED")
    validate(root, authority)
    if not re.fullmatch(r"[0-9]{12}", account) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region):
        raise ValueError("WP4D_INSTALLATION_CONTEXT")
    raw = artifact(root, authority["control_bundles"], binding)
    sha = digest(raw)
    bucket, key = f"e1-control-bundles-{account}-{region}", f"bundles/sha256/{sha}.json"
    result = storage.put_if_absent(bucket, key, raw, sha)
    version = result.get("version_id")
    if (result != {"bucket": bucket, "key": key, "version_id": version} or
            type(version) is not str or not re.fullmatch(
                r"(?![Nn][Uu][Ll][Ll]$|[Ll][Aa][Tt][Ee][Ss][Tt]$)[A-Za-z0-9._+/=-]{1,1024}", version)):
        raise ValueError("WP4D_INSTALLATION_IDENTITY")
    observed = storage.get_exact(bucket, key, version)
    if observed != {**result, "bytes": raw}:
        raise ValueError("WP4D_INSTALLATION_READBACK")
    return {"binding": binding, "sha256": sha, **result, "installation": "VERIFIED",
            "readback": "EXACT_VERSION_BYTES_VERIFIED", "version_origin": "CONDITIONAL_WRITE_RETURN",
            "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}


ENV_FIELDS = {"schema", "owner", "environment", "account", "region", "repository",
              "colors", "cleanup", "nat_slots"}
COLOR_FIELDS = {"roles", "secret_arn", "kms_key_arn", "log_group", "cluster", "service",
                "subnets", "security_groups", "target_group", "listener", "candidate_rule"}
SLOT_FIELDS = {"environment", "account", "region", "vpc", "subnet", "az", "asg", "eip", "route_table", "spec"}
SPEC_FIELDS = {"ami", "launch_template", "launch_template_version", "user_data_sha256",
               "instance_profile", "role", "security_groups", "http_tokens",
               "associate_public_ip", "delete_on_termination", "instance_type", "tags"}


def complete_resources(resources):
    """Reject declarations unable to satisfy the accepted WP4A/WP4C adapters."""
    if set(resources) != ENV_FIELDS or set(resources["colors"]) != {"blue", "green"}:
        return False
    for color, member in resources["colors"].items():
        if set(member) != COLOR_FIELDS or set(member["roles"]) != {"task", "execution"}:
            return False
        if any(type(member[field]) is not str or not member[field] for field in
               COLOR_FIELDS - {"roles", "subnets", "security_groups"}):
            return False
        for field, prefix in (("subnets", "subnet"), ("security_groups", "sg")):
            values = member[field]
            if (type(values) is not list or not 1 <= len(values) <= 16 or
                    len(set(values)) != len(values) or
                    any(not re.fullmatch(prefix + r"-[0-9a-f]{8,17}", v) for v in values)):
                return False
    if (set(resources["cleanup"]) != {"rule", "function_arn", "expression"} or
            not re.fullmatch(r"rate\((?:1 minute|(?:[2-9]|[1-5][0-9]|60) minutes)\)", resources["cleanup"]["expression"])):
        return False
    slots = resources["nat_slots"]
    if len({s["vpc"] for s in slots}) != 1 or len({s["subnet"] for s in slots}) != 2:
        return False
    for slot in slots:
        spec = slot["spec"]
        if set(slot) != SLOT_FIELDS or set(spec) != SPEC_FIELDS:
            return False
        for field, prefix in (("vpc", "vpc"), ("subnet", "subnet"),
                              ("eip", "eipalloc"), ("route_table", "rtb")):
            if not re.fullmatch(prefix + r"-[0-9a-f]{8,17}", slot[field]):
                return False
        if (not re.fullmatch(r"ami-[0-9a-f]{8,17}", spec["ami"]) or
                not re.fullmatch(r"lt-[0-9a-f]{8,17}", spec["launch_template"]) or
                not re.fullmatch(r"[0-9a-f]{64}", spec["user_data_sha256"]) or
                spec["http_tokens"] != "required" or spec["instance_type"] != "t3.micro" or
                spec["associate_public_ip"] is not True or spec["delete_on_termination"] is not True or
                type(spec["tags"]) is not dict or not spec["tags"] or
                any(type(k) is not str or type(v) is not str for k, v in spec["tags"].items()) or
                type(spec["security_groups"]) is not list or len(spec["security_groups"]) != 1 or
                not re.fullmatch(r"sg-[0-9a-f]{8,17}", spec["security_groups"][0])):
            return False
    return True


def creation_supported(authority, installations, runtime_approvals, environment_bindings,
                       account, region):
    """Provider-free projection of the Terraform admission gate.

    Input records may be synthetic. A returned node is creation-supported by
    declared prerequisites, never proven installed or operational in AWS.
    """
    ready = set()
    for key, selected in authority["wp4d"]["selected"].items():
        env = selected["environment"]
        try:
            install, runtime, resources = (installations[key], runtime_approvals[key],
                                           environment_bindings[env])
            digest = selected["package_sha256"]
            if not (install == {"binding": key, "sha256": digest,
                               "bucket": f"e1-control-bundles-{account}-{region}",
                               "key": f"bundles/sha256/{digest}.json",
                               "version_id": install["version_id"],
                               "installation": "VERIFIED",
                               "readback": "EXACT_VERSION_BYTES_VERIFIED",
                               "version_origin": "CONDITIONAL_WRITE_RETURN",
                               "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}
                    and type(install["version_id"]) is str and
                    install["version_id"] == install["version_id"].strip() and
                    0 < len(install["version_id"]) <= 1024 and
                    install["version_id"].lower() not in ("null", "latest")):
                continue
            repository = "e1-wp4d-" + key.replace("/", "-").replace("_", "-")
            if not (runtime == {"binding": key, "owner": OWNER,
                               "approval": "ADMIN_VERIFIED", "package_sha256": digest,
                               "uri": runtime["uri"]} and
                    re.fullmatch(rf"{account}[.]dkr[.]ecr[.]{region}[.]amazonaws[.]com/"
                                 rf"{repository}@sha256:[0-9a-f]{{64}}", runtime["uri"])):
                continue
            if not (resources["schema"] == "E1_WP4D_PROTECTED_ENVIRONMENT_V1" and
                    resources["owner"] == OWNER and resources["environment"] == env and
                    resources["account"] == account and resources["region"] == region and
                    resources["repository"] == "demo-shared-demo-ms"):
                continue
            if not complete_resources(resources):
                continue
            colors = resources["colors"]
            blue, green = colors["blue"], colors["green"]
            if any(blue[field] != green[field] for field in
                   ("cluster", "listener", "candidate_rule")):
                continue
            if not (re.match(rf"^arn:aws:ecs:{region}:{account}:cluster/demo-{env}-", blue["cluster"])
                    and re.match(rf"^arn:aws:elasticloadbalancing:{region}:{account}:listener/app/demo-{env}-", blue["listener"])
                    and re.match(rf"^arn:aws:elasticloadbalancing:{region}:{account}:listener-rule/app/demo-{env}-", blue["candidate_rule"])):
                continue
            if any(colors[color]["service"] != f"demo-{env}-app-api-{color}-svc" or
                   not re.match(rf"^arn:aws:elasticloadbalancing:{region}:{account}:targetgroup/demo-{env}-{color}/",
                                colors[color]["target_group"]) or
                   colors[color]["roles"] != {
                       "task": f"arn:aws:iam::{account}:role/demo-{env}-app-api-{color}-task-role",
                       "execution": f"arn:aws:iam::{account}:role/demo-{env}-app-api-{color}-exec-role"}
                   for color in ("blue", "green")):
                continue
            cleanup = resources["cleanup"]
            if (cleanup["rule"] != f"demo-{env}-scale-down-old-color-rule" or
                cleanup["function_arn"] != f"arn:aws:lambda:{region}:{account}:function:e1-cleanup-recovery-cleanup-{env}:wp4d"):
                continue
            slots = resources["nat_slots"]
            if len(slots) != 2 or any(len({slot[field] for slot in slots}) != 2
                                      for field in ("asg", "eip", "route_table", "az")):
                continue
            if any(slot["environment"] != env or slot["account"] != account or
                   slot["region"] != region or slot["spec"]["tags"].get("Environment") != env or
                   slot["spec"]["tags"].get("Role") != "nat" or
                   type(slot["spec"]["launch_template_version"]) is not int or
                   slot["spec"]["launch_template_version"] <= 0 or
                   slot["spec"]["instance_profile"] != f"arn:aws:iam::{account}:instance-profile/demo-{env}-nat-instance-profile" or
                   slot["spec"]["role"] != f"arn:aws:iam::{account}:role/demo-{env}-nat-role"
                   for slot in slots):
                continue
            ready.add(key)
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return sorted(key for key in ready if all(dependency in ready for dependency in
                  authority["wp4d"]["selected"][key]["dependencies"]))


def policy(binding, resources, account, region, version_id):
    """Concrete action/resource/condition tuples for one installed identity.

    The Terraform generator below instantiates the same policy with placeholders
    and replaces them only with administrator-published protected bindings.
    """
    if binding not in RESERVED:
        raise ValueError("WP4D_UNKNOWN_BINDING")
    env, engine = RESERVED[binding]
    bucket = f"e1-wp4-{env}-{account}-{region}"
    admin = f"demo-release-artifacts-{account}"
    package_digest = resources["package_sha256"]
    bundle_bucket = f"e1-control-bundles-{account}-{region}"
    package_key = f"bundles/sha256/{package_digest}.json"
    arn = lambda service, kind, name: f"arn:aws:{service}:{region}:{account}:{kind}/{name}"
    s3 = lambda name, key: f"arn:aws:s3:::{name}/{key}"
    statements = []
    def allow(actions, names, condition=None):
        statement = {"Effect": "Allow", "Action": list(actions), "Resource": list(names)}
        if condition is not None:
            statement["Condition"] = condition
        statements.append(statement)
    def read(name, *prefixes):
        allow(("s3:GetObject", "s3:GetObjectVersion"),
              [s3(name, prefix + "*") for prefix in prefixes])
    def read_exact(name, *keys):
        allow(("s3:GetObject", "s3:GetObjectVersion"), [s3(name, key) for key in keys])
    def write(name, *prefixes, create_only=True):
        allow(("s3:PutObject",), [s3(name, prefix + "*") for prefix in prefixes],
              {"StringEquals": {"s3:if-none-match": "*"}} if create_only else None)
    def service_resources():
        return [resources["colors"][color]["service_arn"] for color in ("blue", "green")]
    def target_resources():
        return [resources["colors"][color]["target_group"] for color in ("blue", "green")]
    def family_resources():
        return [arn("ecs", "task-definition", resources["colors"][color]["family"] + ":*")
                for color in ("blue", "green")]
    def roles():
        return [resources["colors"][color][field] for color in ("blue", "green")
                for field in ("task_role", "execution_role")]
    def common_app_reads():
        allow(("ecs:DescribeServices",), service_resources())
        allow(("ecs:DescribeTasks",), [arn("ecs", "task", resources["cluster_name"] + "/*")])
        allow(("ecs:ListTasks",), ["*"], {"StringEquals": {"ecs:cluster": resources["cluster_arn"]}})
        allow(("ecs:DescribeTaskDefinition",), ["*"],
              {"StringEquals": {"aws:RequestedRegion": region}})
        allow(("elasticloadbalancing:DescribeListeners", "elasticloadbalancing:DescribeRules",
               "elasticloadbalancing:DescribeTargetHealth"), ["*"],
              {"StringEquals": {"aws:RequestedRegion": region}})
    def route_mutations():
        allow(("elasticloadbalancing:ModifyListener",), [resources["listener"]])
        allow(("elasticloadbalancing:ModifyRule",), [resources["candidate_rule"]])
    def schedule_mutations():
        rule = resources["cleanup"]["rule_arn"]
        allow(("events:PutRule",), [rule])
        allow(("events:PutTargets",), [rule],
              {"ForAllValues:ArnEquals": {"events:TargetArn": resources["cleanup"]["function_arn"]},
               "Null": {"events:TargetArn": "false"}})
        allow(("events:DescribeRule", "events:ListTargetsByRule"), [rule])
    if binding.startswith("request-gateway/"):
        kind = "emergency" if "emergency-" in binding else "normal"
        allow(("codebuild:StartBuild",), [arn("codebuild", "project", resources["project"])])
        prefix = f"gateway/{env}/{kind}/"
        read(bucket, prefix)
        write(bucket, prefix)
    elif binding.startswith("normal-delivery/"):
        common_app_reads()
        allow(("ecs:RegisterTaskDefinition",), family_resources())
        allow(("iam:PassRole",), roles(),
              {"StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}})
        allow(("ecs:UpdateService",), service_resources())
        route_mutations()
        schedule_mutations()
        read(bucket, f"delivery/{env}/", f"gateway/{env}/normal/", "history/")
        write(bucket, f"delivery/{env}/")
        write(bucket, "history/", create_only=False)
        if env == "dev":
            read(bucket, "activations/by-release/")
            write(bucket, "activations/by-release/")
        else:
            read(f"e1-wp4-dev-{account}-{region}", "activations/by-release/")
            read(admin, "prod-approvals/demo-api/")
        read(admin, "qualifications/demo-api/", "releases/demo-api/by-digest/", "eligibility/demo-api/")
        read_exact(admin, "bindings/" + binding.split("/", 1)[1] + ".json", "membership/" + env + ".json")
        allow(("ecr:DescribeImages",), [arn("ecr", "repository", resources["repository"])])
    elif binding.startswith("emergency-recovery/"):
        common_app_reads()
        allow(("ecs:UpdateService",), service_resources())
        route_mutations()
        schedule_mutations()
        own = f"recovery/{env}/recovery/emergency/"
        read(bucket, f"delivery/{env}/", own, "history/", f"gateway/{env}/emergency/")
        write(bucket, own)
        read(admin, "qualifications/demo-api/", "releases/demo-api/by-digest/", "eligibility/demo-api/")
        read_exact(admin, "bindings/" + ("deploy-dev" if env == "dev" else "promote-prod") + ".json", "membership/" + env + ".json")
        if env == "prod":
            read(f"e1-wp4-dev-{account}-{region}", "activations/by-release/")
            read(admin, "prod-approvals/demo-api/")
        allow(("ecr:DescribeImages",), [arn("ecr", "repository", resources["repository"])])
    elif binding.startswith("cleanup-recovery/"):
        common_app_reads()
        allow(("ecs:UpdateService",), service_resources())
        allow(("events:RemoveTargets", "events:DeleteRule", "events:ListTargetsByRule",
               "events:DescribeRule"), [resources["cleanup"]["rule_arn"]])
        own = f"recovery/{env}/recovery/cleanup/"
        read(bucket, own, "history/")
        write(bucket, own)
        read_exact(admin, "membership/" + env + ".json")
    else:
        action = binding.rsplit("/", 1)[1]
        allow(("autoscaling:DescribeAutoScalingGroups", "ec2:DescribeInstances",
               "ec2:DescribeNetworkInterfaces", "ec2:DescribeAddresses",
               "ec2:DescribeRouteTables", "ec2:DescribeLaunchTemplateVersions"), ["*"],
              {"StringEquals": {"aws:RequestedRegion": region}})
        allow(("ec2:DescribeInstanceAttribute",), [arn("ec2", "instance", "*")],
              {"StringEquals": {"aws:ResourceTag/Environment": env,
                                "aws:ResourceTag/Role": "nat"}})
        slots = resources["nat_slots"]
        allow(("iam:GetInstanceProfile",), [slot["instance_profile"] for slot in slots])
        if action == "assign_eip":
            allow(("ec2:AssociateAddress",),
                  [arn("ec2", "elastic-ip", slot["eip"]) for slot in slots])
            for slot in slots:
                allow(("ec2:AssociateAddress",), [arn("ec2", "network-interface", "*")],
                      {"StringEquals": {"ec2:Subnet": arn("ec2", "subnet", slot["subnet"])}})
        elif action == "change_rt":
            allow(("ec2:CreateRoute", "ec2:ReplaceRoute"),
                  [arn("ec2", "route-table", slot["route_table"]) for slot in slots])
        elif action == "disable_sdc":
            allow(("ec2:ModifyInstanceAttribute",), [arn("ec2", "instance", "*")],
                  {"StringEquals": {"ec2:Attribute": "sourceDestCheck",
                                    "aws:ResourceTag/Environment": env,
                                    "aws:ResourceTag/Role": "nat"}})
        allow(("sqs:SendMessage",), [f"arn:aws:sqs:{region}:{account}:e1-wp4-{env}-nat-execution-failed"])
        if action == "disable_sdc":
            allow(("ec2:GetConsoleOutput",), [arn("ec2", "instance", "*")],
                  {"StringEquals": {"aws:ResourceTag/Environment": env, "aws:ResourceTag/Role": "nat"}})
        own = f"recovery/{env}/recovery/{action}/"
        read(bucket, own)
        write(bucket, own)
    if binding.startswith(("normal-delivery/", "emergency-recovery/", "cleanup-recovery/")):
        coordination = s3(bucket, f"arbitration/{env}/application.json")
        allow(("s3:GetObject",), [coordination])
        allow(("s3:PutObject",), [coordination], {"Null": {"s3:if-match": "false"}})
        read(bucket, f"arbitration/{env}/terminals/{binding}/")
        write(bucket, f"arbitration/{env}/terminals/{binding}/")
    allow(("s3:GetObjectVersion",), [s3(bundle_bucket, package_key)],
          {"StringEquals": {"s3:VersionId": version_id}})
    group = "/aws/lambda/" if engine == "LAMBDA" else "/aws/codebuild/"
    name = resources["name"]
    allow(("logs:CreateLogStream", "logs:PutLogEvents"),
          [f"arn:aws:logs:{region}:{account}:log-group:{group}{name}:log-stream:*"])
    return {"Version": "2012-10-17", "Statement": statements}


def _template(binding):
    colors = {color: {"service_arn": f"__{color.upper()}_SERVICE_ARN__",
                      "target_group": f"__{color.upper()}_TARGET__",
                      "family": f"__{color.upper()}_FAMILY__",
                      "task_role": f"__{color.upper()}_TASK_ROLE__",
                      "execution_role": f"__{color.upper()}_EXEC_ROLE__"}
              for color in ("blue", "green")}
    return policy(binding, {"package_sha256": "__PACKAGE_SHA__", "name": "__NAME__",
                            "project": "__PROJECT__", "cluster_name": "__CLUSTER_NAME__",
                            "cluster_arn": "__CLUSTER_ARN__", "colors": colors,
                            "listener": "__LISTENER__", "candidate_rule": "__CANDIDATE_RULE__",
                            "cleanup": {"rule_arn": "__CLEANUP_RULE_ARN__",
                                        "function_arn": "__CLEANUP_FUNCTION_ARN__"},
                            "repository": "__REPOSITORY__",
                            "nat_slots": [{"eip": f"__EIP_{i}__", "route_table": f"__RT_{i}__",
                            "subnet": f"__SUBNET_{i}__",
                            "instance_profile": f"__PROFILE_{i}__"} for i in range(2)]},
                  "__ACCOUNT__", "__REGION__", "__VERSION__")


def _policy_expression():
    """Substitute only canonical protected Terraform values, never a request."""
    replacements = {
        "__ACCOUNT__": "var.account_id",
        "__REGION__": "var.region",
        "__PACKAGE_SHA__": "each.value.package_sha256",
        "__NAME__": "each.value.name",
        "__PROJECT__": "try(local.wp4d_project_names[each.key], each.value.name)",
        "__CLUSTER_NAME__": 'split("/", each.value.resources.colors.blue.cluster)[1]',
        "__CLUSTER_ARN__": "each.value.resources.colors.blue.cluster",
        "__LISTENER__": "each.value.resources.colors.blue.listener",
        "__CANDIDATE_RULE__": "each.value.resources.colors.blue.candidate_rule",
        "__CLEANUP_RULE_ARN__": '"arn:aws:events:${var.region}:${var.account_id}:rule/${each.value.resources.cleanup.rule}"',
        "__CLEANUP_FUNCTION_ARN__": '"arn:aws:lambda:${var.region}:${var.account_id}:function:${local.wp4d_cleanup_names[each.value.environment]}:wp4d"',
        "__REPOSITORY__": "each.value.resources.repository",
        "__VERSION__": "each.value.install.version_id",
    }
    for color in ("blue", "green"):
        upper = color.upper()
        member = f"each.value.resources.colors.{color}"
        replacements.update({
            f"__{upper}_SERVICE_ARN__": '"arn:aws:ecs:${var.region}:${var.account_id}:service/${split("/", '+member+'.cluster)[1]}/${'+member+'.service}"',
            f"__{upper}_TARGET__": member + ".target_group",
            f"__{upper}_FAMILY__": f'"demo-${{each.value.environment}}-app-api-{color}"',
            f"__{upper}_TASK_ROLE__": member + ".roles.task",
            f"__{upper}_EXEC_ROLE__": member + ".roles.execution",
        })
    for index in range(2):
        member = f"each.value.resources.nat_slots[{index}]"
        replacements.update({f"__EIP_{index}__": member + ".eip",
                             f"__RT_{index}__": member + ".route_table",
                             f"__SUBNET_{index}__": member + ".subnet",
                             f"__PROFILE_{index}__": member + ".spec.instance_profile"})
    result = "local.wp4d_policy_templates[each.key]"
    for placeholder, expression in replacements.items():
        result = f'replace({result}, "{placeholder}", {expression})'
    return "${" + result + "}"


def extend(tf):
    """Extend the one WP2 controller-compute module with reviewed WP4 nodes."""
    ex = lambda source: "${" + source + "}"
    tf["variable"].update({
        "wp4d_installations": {"type": "any", "default": {}},
        "wp4d_runtime_approvals": {"type": "any", "default": {}},
        "wp4d_environment_bindings": {"type": "any", "default": {}},
    })
    local = tf["locals"]
    local["wp4d_contract"] = ex("var.authority.wp4d")
    local["wp4d_candidates"] = ex('{ for key, v in local.wp4d_contract.selected : key => merge(v, { install = try(var.wp4d_installations[key], null), runtime = try(var.wp4d_runtime_approvals[key], null), resources = try(var.wp4d_environment_bindings[v.environment], null) }) }')
    checks = [
        "v.install.binding == key", "v.install.sha256 == v.package_sha256",
        'v.install.bucket == "e1-control-bundles-${var.account_id}-${var.region}"',
        'v.install.key == "bundles/sha256/${v.package_sha256}.json"',
        "v.install.version_id != null", "length(trimspace(v.install.version_id)) > 0",
        "v.install.version_id == trimspace(v.install.version_id)",
        "length(v.install.version_id) <= 1024",
        '!contains(["null", "latest"], lower(v.install.version_id))',
        'v.install.installation == "VERIFIED"',
        'v.install.readback == "EXACT_VERSION_BYTES_VERIFIED"',
        'v.install.version_origin == "CONDITIONAL_WRITE_RETURN"',
        'v.install.publisher == "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"',
        'v.runtime.owner == "SECURITY_ROOT_OWNED"',
        'v.runtime.approval == "ADMIN_VERIFIED"',
        'v.runtime.binding == key',
        'v.runtime.package_sha256 == v.package_sha256',
        'can(regex("^${var.account_id}[.]dkr[.]ecr[.]${var.region}[.]amazonaws[.]com/e1-wp4d-${replace(replace(key, "/", "-"), "_", "-")}@sha256:[0-9a-f]{64}$", v.runtime.uri))',
        'v.resources.schema == "E1_WP4D_PROTECTED_ENVIRONMENT_V1"',
        'v.resources.owner == "SECURITY_ROOT_OWNED"',
        "v.resources.environment == v.environment", "v.resources.account == var.account_id",
        "v.resources.region == var.region",
        'v.resources.colors.blue.cluster == v.resources.colors.green.cluster',
        'v.resources.colors.blue.listener == v.resources.colors.green.listener',
        'v.resources.colors.blue.candidate_rule == v.resources.colors.green.candidate_rule',
        'v.resources.colors.blue.service == "demo-${v.environment}-app-api-blue-svc"',
        'v.resources.colors.green.service == "demo-${v.environment}-app-api-green-svc"',
        'v.resources.colors.blue.service != v.resources.colors.green.service',
        'v.resources.colors.blue.target_group != v.resources.colors.green.target_group',
        'can(regex("^arn:aws:ecs:${var.region}:${var.account_id}:cluster/demo-${v.environment}-", v.resources.colors.blue.cluster))',
        'can(regex("^arn:aws:elasticloadbalancing:${var.region}:${var.account_id}:listener/app/demo-${v.environment}-", v.resources.colors.blue.listener))',
        'can(regex("^arn:aws:elasticloadbalancing:${var.region}:${var.account_id}:listener-rule/app/demo-${v.environment}-", v.resources.colors.blue.candidate_rule))',
        'alltrue([for color in ["blue", "green"] : can(regex("^arn:aws:elasticloadbalancing:${var.region}:${var.account_id}:targetgroup/demo-${v.environment}-${color}/", v.resources.colors[color].target_group))])',
        'alltrue([for color in ["blue", "green"] : v.resources.colors[color].roles.task == "arn:aws:iam::${var.account_id}:role/demo-${v.environment}-app-api-${color}-task-role" && v.resources.colors[color].roles.execution == "arn:aws:iam::${var.account_id}:role/demo-${v.environment}-app-api-${color}-exec-role"])',
        'v.resources.cleanup.rule == "demo-${v.environment}-scale-down-old-color-rule"',
        'v.resources.cleanup.function_arn == "arn:aws:lambda:${var.region}:${var.account_id}:function:e1-cleanup-recovery-cleanup-${v.environment}:wp4d"',
        'v.resources.repository == "demo-shared-demo-ms"',
        'length(v.resources.nat_slots) == 2',
        'length(distinct([for slot in v.resources.nat_slots : slot.asg])) == 2',
        'length(distinct([for slot in v.resources.nat_slots : slot.eip])) == 2',
        'length(distinct([for slot in v.resources.nat_slots : slot.route_table])) == 2',
        'length(distinct([for slot in v.resources.nat_slots : slot.az])) == 2',
        'alltrue([for slot in v.resources.nat_slots : slot.environment == v.environment])',
        'alltrue([for slot in v.resources.nat_slots : slot.account == var.account_id && slot.region == var.region && slot.spec.tags.Environment == v.environment && slot.spec.tags.Role == "nat" && slot.spec.launch_template_version > 0 && floor(slot.spec.launch_template_version) == slot.spec.launch_template_version && can(regex("^vpc-", slot.vpc)) && can(regex("^subnet-", slot.subnet)) && can(regex("^rtb-", slot.route_table)) && can(regex("^eipalloc-", slot.eip)) && can(regex("^arn:aws:iam::${var.account_id}:instance-profile/demo-${v.environment}-", slot.spec.instance_profile)) && can(regex("^arn:aws:iam::${var.account_id}:role/demo-${v.environment}-", slot.spec.role))])',
    ]
    # Closed shapes agree with complete_resources(), including the accepted
    # WP4A positions and WP4C resolved launch-specification fields.
    def keys_equal(value, fields):
        return 'sort(keys(' + value + ')) == sort(' + json.dumps(sorted(fields)) + ')'
    checks += [keys_equal('v.resources', ENV_FIELDS),
               keys_equal('v.resources.colors', {'blue', 'green'}),
               keys_equal('v.resources.cleanup', {'rule', 'function_arn', 'expression'}),
               'can(regex("^rate\\\\((1 minute|([2-9]|[1-5][0-9]|60) minutes)\\\\)$", v.resources.cleanup.expression))',
               'length(distinct([for slot in v.resources.nat_slots : slot.vpc])) == 1',
               'length(distinct([for slot in v.resources.nat_slots : slot.subnet])) == 2']
    checks += ['alltrue([for color in ["blue", "green"] : ' +
               keys_equal('v.resources.colors[color]', COLOR_FIELDS) + ' && ' +
               keys_equal('v.resources.colors[color].roles', {'task', 'execution'}) + '])']
    for field in sorted(COLOR_FIELDS - {'roles', 'subnets', 'security_groups'}):
        checks += [f'alltrue([for color in ["blue", "green"] : length(v.resources.colors[color].{field}) > 0])']
    for field, prefix in (("subnets", "subnet"), ("security_groups", "sg")):
        checks += [f'alltrue([for color in ["blue", "green"] : length(v.resources.colors[color].{field}) >= 1 && length(v.resources.colors[color].{field}) <= 16 && length(distinct(v.resources.colors[color].{field})) == length(v.resources.colors[color].{field}) && alltrue([for id in v.resources.colors[color].{field} : can(regex("^{prefix}-[0-9a-f]{{8,17}}$", id))])])']
    checks += ['alltrue([for slot in v.resources.nat_slots : ' +
               keys_equal('slot', SLOT_FIELDS) + ' && ' + keys_equal('slot.spec', SPEC_FIELDS) + '])']
    checks += ['alltrue([for slot in v.resources.nat_slots : slot.spec.instance_profile == "arn:aws:iam::${var.account_id}:instance-profile/demo-${v.environment}-nat-instance-profile" && slot.spec.role == "arn:aws:iam::${var.account_id}:role/demo-${v.environment}-nat-role"])']
    for field, prefix in (("vpc", "vpc"), ("subnet", "subnet"), ("eip", "eipalloc"), ("route_table", "rtb")):
        checks += [f'alltrue([for slot in v.resources.nat_slots : can(regex("^{prefix}-[0-9a-f]{{8,17}}$", slot.{field}))])']
    checks += ['alltrue([for slot in v.resources.nat_slots : can(regex("^ami-[0-9a-f]{8,17}$", slot.spec.ami)) && can(regex("^lt-[0-9a-f]{8,17}$", slot.spec.launch_template)) && can(regex("^[0-9a-f]{64}$", slot.spec.user_data_sha256)) && slot.spec.http_tokens == "required" && slot.spec.instance_type == "t3.micro" && slot.spec.associate_public_ip == true && slot.spec.delete_on_termination == true && length(slot.spec.security_groups) == 1 && can(regex("^sg-[0-9a-f]{8,17}$", slot.spec.security_groups[0]))])']
    local["wp4d_ready"] = ex('{ for key, v in local.wp4d_candidates : key => v if try(' +
                             ' && '.join(checks) + ', false) }')
    local["wp4d_active"] = ex('{ for key, v in local.wp4d_ready : key => v if alltrue([for dependency in v.dependencies : contains(keys(local.wp4d_ready), dependency)]) }')
    local["wp4d_gateways"] = ex('{ for key, v in local.wp4d_active : key => v if v.engine == "LAMBDA" }')
    local["wp4d_projects"] = ex('{ for key, v in local.wp4d_active : key => v if v.engine == "CODEBUILD" }')
    local["wp4d_reserved"] = ex('{ for key, v in local.wp4d_gateways : key => v if !contains(keys(local.nodes), key) }')
    local["wp4d_cleanup_names"] = {env: f"e1-cleanup-recovery-cleanup-{env}" for env in ("dev", "prod")}
    local["wp4d_project_names"] = {
        key: ("e1-controller-" + key.split("/", 1)[1])
        for key in RESERVED if key.startswith("request-gateway/")}
    local["wp4d_policy_templates"] = {key: json.dumps(_template(key), sort_keys=True)
                                      for key in RESERVED}
    local["wp4d_config"] = ex('{ for key, v in local.wp4d_active : key => jsonencode({ binding = key, account = var.account_id, region = var.region, environment = v.environment, bundle = { binding = key, bucket = v.install.bucket, key = v.install.key, version_id = v.install.version_id, sha256 = v.install.sha256 }, runtime_image = v.runtime.uri, project = contains(keys(local.wp4d_project_names), key) ? local.wp4d_project_names[key] : v.name, evidence_bucket = "e1-wp4-${v.environment}-${var.account_id}-${var.region}", dev_evidence_bucket = "e1-wp4-dev-${var.account_id}-${var.region}", admin_bucket = local.evidence_bucket, repository = v.resources.repository, resources = v.resources, nat_slots = v.resources.nat_slots }) }')
    resources = tf["resource"]
    trust = ex('jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = each.value.engine == "LAMBDA" ? "lambda.amazonaws.com" : "codebuild.amazonaws.com" }, Condition = each.value.engine == "CODEBUILD" ? { StringEquals = { "aws:SourceAccount" = var.account_id }, ArnEquals = { "aws:SourceArn" = "arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}" } } : {} }] })')
    old = resources["aws_iam_role"]["execution"]
    old["description"] = ex('contains(keys(local.wp4d_active), each.key) ? "WP4D exact reviewed controller execution" : "WP2C inert execution identity: no trust Allow, deny all AWS actions."')
    old["assume_role_policy"] = ex('contains(keys(local.wp4d_active), each.key) ? jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = each.value.engine == "LAMBDA" ? "lambda.amazonaws.com" : "codebuild.amazonaws.com" }, Condition = each.value.engine == "CODEBUILD" ? { StringEquals = { "aws:SourceAccount" = var.account_id }, ArnEquals = { "aws:SourceArn" = "arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}" } } : {} }] }) : (' + old["assume_role_policy"][2:-1] + ')')
    resources["aws_iam_role"]["wp4d_reserved"] = {"for_each": ex("local.wp4d_reserved"),
        "name": ex("each.value.role"), "assume_role_policy": trust}
    inert = resources["aws_iam_role_policy"]["inert"]
    inert["for_each"] = ex('{ for k,v in local.nodes : k=>v if !contains(keys(local.wp3_active),k) && !contains(keys(local.wp4d_active),k) }')
    resources["aws_iam_role_policy"]["wp4d"] = {"for_each": ex("local.wp4d_active"),
        "name": "wp4d-exact", "role": ex("each.value.role"), "policy": _policy_expression()}
    resources["aws_cloudwatch_log_group"]["wp4d"] = {
        "for_each": ex("local.wp4d_active"),
        "name": ex('"/aws/${each.value.engine == "LAMBDA" ? "lambda" : "codebuild"}/${each.value.name}"'),
        "retention_in_days": 14}
    resources["aws_lambda_function"]["wp4d"] = {
        "for_each": ex("local.wp4d_gateways"), "function_name": ex("each.value.name"),
        "role": ex('contains(keys(local.nodes), each.key) ? aws_iam_role.execution[each.key].arn : aws_iam_role.wp4d_reserved[each.key].arn'),
        "package_type": "Image", "image_uri": ex("each.value.runtime.uri"), "publish": True,
        "timeout": 600, "memory_size": 256, "reserved_concurrent_executions": 1,
        "image_config": {"command": ["runtime.handler"]},
        "environment": {"variables": {"E1_PROTECTED_CONFIGURATION": ex("local.wp4d_config[each.key]")}},
        "depends_on": ["aws_cloudwatch_log_group.wp4d", "aws_iam_role_policy.wp4d"]}
    resources["aws_lambda_alias"] = {"wp4d_cleanup": {
        "for_each": ex('{ for k,v in local.wp4d_gateways : k => v if startswith(k, "cleanup-recovery/") }'),
        "name": "wp4d", "function_name": ex("aws_lambda_function.wp4d[each.key].function_name"),
        "function_version": ex("aws_lambda_function.wp4d[each.key].version")}}
    resources["aws_codebuild_project"]["wp4d"] = {
        "for_each": ex("local.wp4d_projects"), "name": ex("each.value.name"),
        "service_role": ex("aws_iam_role.execution[each.key].arn"), "build_timeout": 45,
        "source": {"type": "NO_SOURCE", "buildspec": json.dumps({"version": "0.2", "phases": {
            "build": {"on-failure": "ABORT", "commands": ["python3 /opt/e1/scripts/wp4d/runtime.py"]}}})},
        "artifacts": {"type": "NO_ARTIFACTS"},
        "environment": {"type": "LINUX_CONTAINER", "compute_type": "BUILD_GENERAL1_SMALL",
                        "image": ex("each.value.runtime.uri"),
                        "image_pull_credentials_type": "CODEBUILD", "privileged_mode": False,
                        "environment_variable": {"name": "E1_PROTECTED_CONFIGURATION", "type": "PLAINTEXT",
                                                 "value": ex("local.wp4d_config[each.key]")}},
        "cache": {"type": "NO_CACHE"},
        "logs_config": {"cloudwatch_logs": {"status": "ENABLED",
                                          "group_name": ex('"/aws/codebuild/${each.value.name}"')},
                        "s3_logs": {"status": "DISABLED"}},
        "depends_on": ["aws_cloudwatch_log_group.wp4d", "aws_iam_role_policy.wp4d"]}
    local["wp4d_buckets"] = ex('{ for env in ["dev", "prod"] : env => "e1-wp4-${env}-${var.account_id}-${var.region}" }')
    resources["aws_s3_bucket"]["wp4d"] = {"for_each": ex("local.wp4d_buckets"),
        "bucket": ex("each.value"), "force_destroy": False,
        "tags": {"E1Owner": OWNER, "E1Environment": ex("each.key")}}
    resources["aws_s3_bucket_versioning"]["wp4d"] = {
        "for_each": ex("local.wp4d_buckets"), "bucket": ex("aws_s3_bucket.wp4d[each.key].id"),
        "versioning_configuration": {"status": "Enabled"}}
    resources["aws_s3_bucket_public_access_block"]["wp4d"] = {
        "for_each": ex("local.wp4d_buckets"), "bucket": ex("aws_s3_bucket.wp4d[each.key].id"),
        **dict.fromkeys(("block_public_acls", "ignore_public_acls", "block_public_policy",
                         "restrict_public_buckets"), True)}
    resources["aws_s3_bucket_server_side_encryption_configuration"]["wp4d"] = {
        "for_each": ex("local.wp4d_buckets"), "bucket": ex("aws_s3_bucket.wp4d[each.key].id"),
        "rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}}
    # Bucket policy denies all unapproved readers/writers and non-admin delete.
    # Role identity policies then select the class-owned prefixes above.
    local["wp4d_bucket_readers"] = ex('{ for env in ["dev", "prod"] : env => concat([var.admin_arn], [for k,v in local.wp4d_active : "arn:aws:iam::${var.account_id}:role/${v.role}" if v.environment == env], env == "dev" ? [for k,v in local.wp4d_active : "arn:aws:iam::${var.account_id}:role/${v.role}" if v.environment == "prod" && (startswith(k, "normal-delivery/") || startswith(k, "emergency-recovery/"))] : []) }')
    local["wp4d_bucket_writers"] = ex('{ for env in ["dev", "prod"] : env => concat([var.admin_arn], [for k,v in local.wp4d_active : "arn:aws:iam::${var.account_id}:role/${v.role}" if v.environment == env]) }')
    resources["aws_s3_bucket_policy"]["wp4d"] = {
        "for_each": ex("local.wp4d_buckets"), "bucket": ex("aws_s3_bucket.wp4d[each.key].id"),
        "policy": ex('jsonencode({ Version = "2012-10-17", Statement = [{ Sid = "TLS", Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.wp4d[each.key].arn, "${aws_s3_bucket.wp4d[each.key].arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } }, { Sid = "Readers", Effect = "Deny", Principal = "*", Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:ListBucket"], Resource = [aws_s3_bucket.wp4d[each.key].arn, "${aws_s3_bucket.wp4d[each.key].arn}/*"], Condition = { ArnNotEquals = { "aws:PrincipalArn" = local.wp4d_bucket_readers[each.key] } } }, { Sid = "Writers", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.wp4d[each.key].arn}/*", Condition = { ArnNotEquals = { "aws:PrincipalArn" = local.wp4d_bucket_writers[each.key] } } }, { Sid = "NoNonAdminDelete", Effect = "Deny", Principal = "*", Action = ["s3:DeleteObject", "s3:DeleteObjectVersion"], Resource = "${aws_s3_bucket.wp4d[each.key].arn}/*", Condition = { ArnNotEquals = { "aws:PrincipalArn" = var.admin_arn } } }, { Sid = "ImmutableEvidence", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = ["${aws_s3_bucket.wp4d[each.key].arn}/delivery/*", "${aws_s3_bucket.wp4d[each.key].arn}/recovery/*", "${aws_s3_bucket.wp4d[each.key].arn}/gateway/*", "${aws_s3_bucket.wp4d[each.key].arn}/activations/*"], Condition = { StringNotEquals = { "s3:if-none-match" = "*" } } }] })')}
    # WP5 receives only arbitration objects, never delivery/recovery/history.
    local["e2_lifecycle_writers"] = ex('{ for env in ["dev", "prod"] : env => [for suffix in ["infra-${env}", "infra-high-risk-${env}"] : "arn:aws:iam::${var.account_id}:role/e1-controller-${suffix}-exec"] }')
    policy_source = resources["aws_s3_bucket_policy"]["wp4d"]["policy"]
    policy_source = policy_source.replace('local.wp4d_bucket_readers[each.key]', 'concat(local.wp4d_bucket_readers[each.key], local.e2_lifecycle_writers[each.key])')
    policy_source = policy_source.replace('local.wp4d_bucket_writers[each.key]', 'concat(local.wp4d_bucket_writers[each.key], local.e2_lifecycle_writers[each.key])')
    extra = ', { Sid = "E2LifecycleOnlyCoordination", Effect = "Deny", Principal = "*", Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:ListBucket"], NotResource = "${aws_s3_bucket.wp4d[each.key].arn}/arbitration/${each.key}/*", Condition = { ArnEquals = { "aws:PrincipalArn" = local.e2_lifecycle_writers[each.key] } } }, { Sid = "E2ConditionalUpdates", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.wp4d[each.key].arn}/arbitration/*", Condition = { Null = { "s3:if-match" = "true", "s3:if-none-match" = "true" } } }'
    resources["aws_s3_bucket_policy"]["wp4d"]["policy"] = policy_source.replace('}] })', '}' + extra + '] })')
    source = resources["aws_s3_bucket_policy"]["wp4d"]["policy"]
    extra = ', { Sid = "E2ImmutableTerminals", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.wp4d[each.key].arn}/arbitration/${each.key}/terminals/*", Condition = { StringNotEquals = { "s3:if-none-match" = "*" } } }'
    resources["aws_s3_bucket_policy"]["wp4d"]["policy"] = source.replace('} ] })', '}' + extra + '] })') if '} ] })' in source else source.replace('}] })', '}' + extra + '] })')
    evidence_policy = json.loads(resources['aws_s3_bucket_policy']['evidence']['policy'])
    evidence_policy['Statement'].append({
        'Sid': 'WP4ProtectedConfiguration', 'Effect': 'Deny', 'Principal': '*',
        'Action': ['s3:PutObject', 's3:DeleteObject', 's3:DeleteObjectVersion'],
        'Resource': ['arn:aws:s3:::${local.evidence_bucket}/' + p + '*' for p in
                     ('bindings/', 'membership/', 'prod-approvals/')],
        'Condition': {'ArnNotEquals': {'aws:PrincipalArn': '${var.admin_arn}'}}})
    resources['aws_s3_bucket_policy']['evidence']['policy'] = json.dumps(evidence_policy)
    resources["aws_lambda_permission"]["wp4d_cleanup"] = {
        "for_each": ex('{ for k,v in local.wp4d_gateways : k => v if startswith(k, "cleanup-recovery/") }'),
        "statement_id": "ExactCleanupRule", "action": "lambda:InvokeFunction",
        "function_name": ex("aws_lambda_function.wp4d[each.key].function_name"),
        "qualifier": "wp4d",
        "principal": "events.amazonaws.com", "source_account": ex("var.account_id"),
        "source_arn": ex('"arn:aws:events:${var.region}:${var.account_id}:rule/${each.value.resources.cleanup.rule}"'),
        "depends_on": ["aws_lambda_alias.wp4d_cleanup"]}
    local["wp4d_nat_events"] = ex('{ for env in ["dev", "prod"] : env => try(var.wp4d_environment_bindings[env], null) if alltrue([for action in ["assign_eip", "change_rt", "disable_sdc"] : contains(keys(local.wp4d_active), "nat-recovery/nat-${env}/${action}")]) }')
    resources["aws_cloudwatch_event_rule"]["wp4d_nat"] = {
        "for_each": ex("local.wp4d_nat_events"), "name": ex('"e1-wp4-${each.key}-nat-launch"'),
        "event_pattern": ex('jsonencode({ source = ["aws.autoscaling"], "detail-type" = ["EC2 Instance Launch Successful"], account = [var.account_id], region = [var.region], detail = { AutoScalingGroupName = [for slot in each.value.nat_slots : slot.asg] } })')}
    resources["aws_cloudwatch_event_target"]["wp4d_nat"] = {
        "for_each": ex('{ for k,v in local.wp4d_gateways : k => v if startswith(k, "nat-recovery/") && contains(keys(local.wp4d_nat_events), v.environment) }'),
        "rule": ex("aws_cloudwatch_event_rule.wp4d_nat[each.value.environment].name"),
        "target_id": ex('replace(each.key, "/", "-")'),
        "arn": ex("aws_lambda_function.wp4d[each.key].qualified_arn"),
        "input_transformer": {
            "input_paths": {"id": "$.id", "account": "$.account", "region": "$.region", "time": "$.time",
                            "asg": "$.detail.AutoScalingGroupName", "instance": "$.detail.EC2InstanceId"},
            "input_template": '{"id":<id>,"account":<account>,"region":<region>,"time":<time>,"source":"aws.autoscaling","detail-type":"EC2 Instance Launch Successful","detail":{"AutoScalingGroupName":<asg>,"EC2InstanceId":<instance>}}'}}
    # E13: EventBridge acceptance and Lambda execution are separate failures.
    resources["aws_cloudwatch_event_target"]["wp4d_nat"].update({
        "retry_policy": {"maximum_event_age_in_seconds": 900, "maximum_retry_attempts": 3},
        "dead_letter_config": {"arn": ex('aws_sqs_queue.nat_delivery_failed[each.value.environment].arn')},
        "depends_on": ["aws_sqs_queue_policy.nat_failures"]})
    resources["aws_lambda_function_event_invoke_config"] = {"wp4d_nat": {
        "for_each": ex('aws_cloudwatch_event_target.wp4d_nat'),
        "function_name": ex('aws_lambda_function.wp4d[each.key].function_name'),
        "qualifier": ex('aws_lambda_function.wp4d[each.key].version'),
        "maximum_event_age_in_seconds": 900, "maximum_retry_attempts": 1,
        "destination_config": {"on_failure": {"destination": ex('aws_sqs_queue.nat_execution_failed[local.wp4d_active[each.key].environment].arn')}}}}
    resources["aws_sqs_queue"] = {"nat_" + kind + "_failed": {
        "for_each": ex('local.wp4d_nat_events'),
        "name": ex('"e1-wp4-${each.key}-nat-' + kind + '-failed"'),
        "message_retention_seconds": 1209600, "sqs_managed_sse_enabled": True,
        "tags": {"E1Owner": OWNER, "Environment": ex('each.key')},
        "lifecycle": {"prevent_destroy": True}}
        for kind in ("delivery", "execution")}
    local["nat_failure_queues"] = ex('merge({for env,q in aws_sqs_queue.nat_delivery_failed : "${env}/delivery" => {environment=env,arn=q.arn,url=q.url,name=q.name,kind="delivery"}}, {for env,q in aws_sqs_queue.nat_execution_failed : "${env}/execution" => {environment=env,arn=q.arn,url=q.url,name=q.name,kind="execution"}})')
    resources["aws_sqs_queue_policy"] = {"nat_failures": {
        "for_each": ex('local.nat_failure_queues'), "queue_url": ex('each.value.url'),
        "policy": ex('jsonencode({Version="2012-10-17", Statement=concat([{Sid="TLS", Effect="Deny", Principal="*", Action="sqs:*", Resource=each.value.arn, Condition={Bool={"aws:SecureTransport"="false"}}}, {Sid="AdminReadDrain", Effect="Allow", Principal={AWS=var.admin_arn}, Action=["sqs:ReceiveMessage","sqs:DeleteMessage","sqs:ChangeMessageVisibility","sqs:GetQueueAttributes"], Resource=each.value.arn}, {Sid="OnlyAdminDrain", Effect="Deny", Principal="*", Action=["sqs:ReceiveMessage","sqs:DeleteMessage","sqs:PurgeQueue","sqs:ChangeMessageVisibility"], Resource=each.value.arn, Condition={ArnNotEquals={"aws:PrincipalArn"=var.admin_arn}}}], each.value.kind=="delivery" ? [{Sid="ExactRule", Effect="Allow", Principal={Service="events.amazonaws.com"}, Action="sqs:SendMessage", Resource=each.value.arn, Condition={ArnEquals={"aws:SourceArn"=aws_cloudwatch_event_rule.wp4d_nat[each.value.environment].arn}, StringEquals={"aws:SourceAccount"=var.account_id}}}] : [], each.value.kind=="execution" ? [{Sid="ExactExecutionRoles", Effect="Allow", Principal={AWS=[for k,v in local.wp4d_active : "arn:aws:iam::${var.account_id}:role/${v.role}" if startswith(k,"nat-recovery/") && v.environment==each.value.environment]}, Action="sqs:SendMessage", Resource=each.value.arn}] : [])})')}}
    # Reuse fixed existing environment SNS topics without owning their policies.
    resources.setdefault("aws_cloudwatch_metric_alarm", {})["nat_failure_queue"] = {
        "for_each": ex('local.nat_failure_queues'), "alarm_name": ex('"e1-wp4-${replace(each.key,"/","-")}-nat-failures"'),
        "namespace": "AWS/SQS", "metric_name": "ApproximateNumberOfMessagesVisible",
        "dimensions": {"QueueName": ex('each.value.name')}, "statistic": "Maximum",
        "period": 60, "evaluation_periods": 1, "threshold": 0,
        "comparison_operator": "GreaterThanThreshold", "treat_missing_data": "missing",
        "alarm_actions": [ex('"arn:aws:sns:${var.region}:${var.account_id}:demo-${each.value.environment}-alerts"')]}
    resources["aws_cloudwatch_metric_alarm"]["nat_async_delivery"] = {
        "for_each": ex('aws_cloudwatch_event_target.wp4d_nat'),
        "alarm_name": ex('"e1-${replace(each.key,"/","-")}-destination-failed"'),
        "namespace": "AWS/Lambda", "metric_name": "DestinationDeliveryFailures",
        "dimensions": {"FunctionName": ex('aws_lambda_function.wp4d[each.key].function_name')},
        "statistic": "Sum", "period": 60, "evaluation_periods": 1, "threshold": 0,
        "comparison_operator": "GreaterThanThreshold", "treat_missing_data": "notBreaching",
        "alarm_actions": [ex('"arn:aws:sns:${var.region}:${var.account_id}:demo-${local.wp4d_active[each.key].environment}-alerts"')]}
    resources["aws_cloudwatch_metric_alarm"]["nat_event_dlq_delivery"] = {
        "for_each": ex('local.wp4d_nat_events'), "alarm_name": ex('"e1-wp4-${each.key}-nat-dlq-delivery-failed"'),
        "namespace": "AWS/Events", "metric_name": "InvocationsFailedToBeSentToDlq",
        "dimensions": {"RuleName": ex('aws_cloudwatch_event_rule.wp4d_nat[each.key].name')},
        "statistic": "Sum", "period": 60, "evaluation_periods": 1, "threshold": 0,
        "comparison_operator": "GreaterThanThreshold", "treat_missing_data": "notBreaching",
        "alarm_actions": [ex('"arn:aws:sns:${var.region}:${var.account_id}:demo-${each.key}-alerts"')]}
    resources["aws_lambda_permission"]["wp4d_nat"] = {
        "for_each": ex("aws_cloudwatch_event_target.wp4d_nat"),
        "statement_id": "ExactNatLaunchRule", "action": "lambda:InvokeFunction",
        "function_name": ex("aws_lambda_function.wp4d[each.key].function_name"),
        "qualifier": ex("aws_lambda_function.wp4d[each.key].version"),
        "principal": "events.amazonaws.com", "source_account": ex("var.account_id"),
        "source_arn": ex('aws_cloudwatch_event_rule.wp4d_nat[local.wp4d_active[each.key].environment].arn')}
    local["wp4d_repositories"] = ex('{ for key, value in local.wp4d_contract.selected : "e1-wp4d-${replace(replace(key, "/", "-"), "_", "-")}" => { name = value.name, engine = value.engine } }')
    resources["aws_ecr_repository"]["wp4d"] = {
        "for_each": ex("local.wp4d_repositories"), "name": ex("each.key"),
        "image_tag_mutability": "IMMUTABLE", "image_scanning_configuration": {"scan_on_push": True}}
    resources["aws_ecr_repository_policy"]["wp4d"] = {
        "for_each": ex("local.wp4d_repositories"),
        "repository": ex("aws_ecr_repository.wp4d[each.key].name"),
        "policy": ex('jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = each.value.engine == "LAMBDA" ? "lambda.amazonaws.com" : "codebuild.amazonaws.com" }, Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Condition = { StringEquals = { "aws:SourceAccount" = var.account_id }, ArnEquals = { "aws:SourceArn" = each.value.engine == "LAMBDA" ? "arn:aws:lambda:${var.region}:${var.account_id}:function:${each.value.name}" : "arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}" } } }] })')}
    tf["output"]["wp4d"] = {"value": {"active_bindings": ex("keys(local.wp4d_active)"),
        "bundle_readers": ex('{ for k,v in local.wp4d_active : k => "arn:aws:iam::${var.account_id}:role/${v.role}" }'),
        "external_invocations": [], "live": "UNVERIFIED_NOT_DEPLOYED"}}
    return tf
