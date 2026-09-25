"""WP2D neutral ownership and fixed, non-executing consumer interfaces.

Legacy roots remain CURRENT exclusions. No controller or recovery activation.
The catalog is consumed by Terraform and record validation, not an AWS simulator.
"""
import hashlib
import json

OWNER = "SECURITY_ROOT_OWNED"
MODULE = "terraform/infra/security/modules/protected_resources/main.tf.json"
STAGE = "E1_WP2D_PROTECTED_OWNERSHIP_PUBLICATION_CLOSURE"
RECOVERY_SOURCES = {
    "terraform/infra/apps/fargate/lambda/scale_down_old_color.py": "e3cdf48ad7056068475704cf8ec7a528c571e3944d2e41ada529bddc33ab656e",
    "terraform/infra/global/modules/nat/lambda/assign_eip.py": "ea0a2b5f8bee20d348bb805333822f27dfc47f320767e5886f3ead40167a41bd",
    "terraform/infra/global/modules/nat/lambda/change_rt.py": "bb239c6e800f60bc07f6c7681654c435cc7e1081e083f3fc3c4c110adb3cbeab",
    "terraform/infra/global/modules/nat/lambda/disable_sdc.py": "ab8864f9ca81e39a02aa070a708154c5d283c37815bde73628bbbc821d333a98",
    "terraform/infra/global/modules/nat/launch_template.tf": "091c4fc897e200981f08769109036d4e84a2661be628d5f02608e1b786472691",
}


def require(ok, message):
    if not ok:
        raise ValueError("WP2D_SOURCE_ADMISSION_FAILURE: " + message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def catalog():
    """Closed extraction grammar. No account-specific or invented deployed IDs."""
    resources = {}
    def add(logical, kind, name, source, scope, **extra):
        resources[logical] = dict(kind=kind, name=name, source=source, scope=scope,
                              owner=OWNER, declaration="module.protected_resources/" + logical, **extra)
    for env in ("dev", "prod"):
        prefix = "demo-" + env
        for ident, name, service, source, mode in (
            ("sql", prefix + "-data-sql-ec2-role", "ec2.amazonaws.com", "data/main.tf", "SQL"),
            ("flow", prefix + "-vpc-flow-logs-role", "vpc-flow-logs.amazonaws.com", "global/modules/vpc/vpc.tf", "FLOW"),
            ("nat", prefix + "-nat-role", "ec2.amazonaws.com", "global/modules/nat/iam_nat.tf", "NAT_INSTANCE"),
            ("nat-recovery", prefix + "-lambda-nat-role", "lambda.amazonaws.com", "global/modules/nat/iam_lambda_nat.tf", "INERT"),
            ("cleanup", prefix + "-scale-down-old-color-role", "lambda.amazonaws.com", "apps/fargate/iam_lambda_scale_down.tf", "INERT"),
        ):
            add(env + "/" + ident, "role", name, "terraform/infra/" + source, env, service=service, mode=mode)
        for color in ("blue", "green"):
            for role in ("task", "exec"):
                add(env + "/" + color + "-" + role, "role", prefix + "-app-api-" + color + "-" + role + "-role",
                    "terraform/infra/apps/fargate/modules/ecs_service/iam.tf", env,
                    service="ecs-tasks.amazonaws.com", mode=role.upper())
        for ident, name in (("sql", prefix + "-data-sql-ec2-profile"), ("nat", prefix + "-nat-instance-profile")):
            add(env + "/" + ident + "-profile", "profile", name, resources[env + "/" + ident]["source"], env, role=env + "/" + ident)
        add(env + "/kms", "key", "alias/" + env + "-kms-service", "terraform/infra/shared/modules/kms_key/key.tf", env)
        for ident, suffix in (("sa", "db/sql-sa-password"), ("db-user", "db/sql-app-password"), ("connection", "app/db-connection-string")):
            add(env + "/" + ident, "secret", "demo/" + env + "/" + suffix,
                "terraform/infra/secrets/modules/secret_metadata/main.tf", env, key=env + "/kms")
        add(env + "/repository", "repository", prefix + "-shared-demo-ms", "terraform/infra/shared/modules/ecr/main.tf", env)
    add("neutral/repository", "repository", "demo-shared-demo-ms", "terraform/infra/shared/modules/ecr/main.tf", "neutral")
    add("neutral/artifacts", "bucket", "demo-release-artifacts-", "terraform/infra/shared/release_artifacts_bucket.tf", "neutral")
    add("neutral/oidc", "oidc", "token.actions.githubusercontent.com", "terraform/infra/shared/modules/iam_github/github_terragrunt_ci.tf", "neutral")
    recovery = {}
    for env in ("dev", "prod"):
        for ident, source, role, bundle in (
            ("cleanup", "apps/fargate/lambda_scale_down.tf", "cleanup", "cleanup-recovery/cleanup-" + env),
            ("nat-functions", "global/modules/nat/lambda_nat.tf", "nat-recovery", "nat-recovery/nat-" + env),
            ("nat-events", "global/modules/nat/events_nat.tf", "nat-recovery", "nat-recovery/nat-" + env),
            ("nat-launch", "global/modules/nat/launch_template.tf", "nat", "nat-recovery/nat-" + env),
        ):
            recovery[env + "/" + ident] = {"owner": OWNER, "scope": env, "state": "DISABLED_RESERVED",
                "operational": False, "available": False, "value": None, "materialization": "WP4_OPERATIONAL_ACTIVATION",
                "foundation": "WP2_PROTECTED_FOUNDATION", "legacy_source": "terraform/infra/" + source,
                "legacy_classification": "CURRENT_TRANSITIONAL_EXCLUSION", "role": env + "/" + role,
                "bundle": bundle, "events_enabled": False, "invocation_enabled": False,
                "configuration": "ADMIN_INSTALLED_ONLY", "user_data": "PROTECTED_NOT_ORDINARY_SELECTED" if ident == "nat-launch" else None}
    consumers = {}
    for env in ("dev", "prod"):
        consumers[env + "/shared"] = [env + "/kms", env + "/repository", "neutral/repository", "neutral/artifacts", "neutral/oidc"]
        consumers[env + "/data"] = [env + "/sql-profile", env + "/sa", env + "/db-user", env + "/kms"]
        consumers[env + "/apps"] = [env + "/" + c + "-" + r for c in ("blue", "green") for r in ("task", "exec")] + [env + "/connection", env + "/kms"]
        consumers[env + "/global"] = [env + "/flow", env + "/nat-profile"]
        consumers[env + "/secrets"] = [env + "/" + k for k in ("sa", "db-user", "connection", "kms")]
    dependencies = {}
    for key, item in resources.items():
        deps = ["authority.ownership_closure", "protected-publication/" + key]
        deps += [item[k] for k in ("role", "key") if k in item]
        if item["kind"] == "role":
            deps += ["fixed-trust/" + key, "fixed-permissions/" + key]
            if item["mode"] in ("SQL", "TASK", "EXEC"):
                deps += [item["scope"] + "/kms"]
            if item["mode"] == "SQL":
                deps += [item["scope"] + "/sa", item["scope"] + "/db-user"]
            if item["mode"] == "EXEC":
                deps += [item["scope"] + "/connection"]
        dependencies[key] = {"writer": OWNER, "phase": "WP2_PROTECTED_FOUNDATION", "depends_on": deps}
    for key, item in recovery.items():
        dependencies["recovery/" + key] = {"writer": OWNER, "phase": "WP4_OPERATIONAL_ACTIVATION",
            "depends_on": [item["role"], item["bundle"], "protected-config/" + key, "protected-publication/recovery/" + key]}
        env = item["scope"]
        item["reserved_relations"] = ({"function": "demo-" + env + "-scale-down-old-color-lambda",
            "rule": "demo-" + env + "-scale-down-old-color-rule", "services": ["demo-" + env + "-app-api-" + color + "-svc" for color in ("blue", "green")]}
            if key.endswith("/cleanup") else {"functions": ["demo-" + env + "-" + f + "-lambda" for f in ("assign-eip", "change-rt", "disable-sdc")],
            "rule": "demo-" + env + "-on-ec2-running", "asgs": ["demo-" + env + "-asg-nat-" + az for az in ("a", "b")],
            "profile": env + "/nat-profile", "launch_templates": ["demo-" + env + "-nat-" + az + "-" for az in ("a", "b")]})
    return {"stage": STAGE, "resources": resources, "recovery": recovery, "consumers": consumers,
        "dependencies": dependencies, "legacy": "CURRENT_TRANSITIONAL_EXCLUSION",
        "publication": "ADMIN_PUBLISHED_ARN_ID_RECORD", "live": "UNVERIFIED",
        "state_migration": "NOT_PERFORMED", "record_schema": "E1_PROTECTED_OUTPUT_V1",
        "installed_schema": "E1_INSTALLED_REFERENCE_V1", "installation_activates_compute": False,
        "legacy_automation": "EXCLUDED_NOT_COPIED_WP6_WP7", "backend": "EXTERNAL_ADMIN_PRECONDITION",
        "publications": {}, "recovery_source_identities": RECOVERY_SOURCES,
        "recovery_source_use": "CURRENT_IDENTIFICATION_ONLY_NOT_APPROVED_EXECUTABLE",
        "extraction_inventory": {
            "shared": {"security": ["IAM/OIDC", "KMS key/alias", "ECR/repository lifecycle", "release bucket/controls/lifecycle"], "ordinary": ["SNS alerts"], "legacy_automation": "CURRENT_TRANSITIONAL_EXCLUSION"},
            "data": {"security": ["SQL role/trust/inline policy/managed attachment/profile"], "ordinary": ["SQL EC2/storage/alarms"]},
            "apps": {"security": ["color task/execution roles/trust/attachments", "DB secret/KMS policies", "cleanup role/policy", "disabled cleanup code/config/invocation"], "ordinary": ["ECS service/logs/alarms", "zero-count skeleton; WP5 execution"]},
            "global": {"security": ["flow-log IAM", "NAT role/profile", "inert NAT recovery role/policy", "disabled NAT code/config/events/invocation/launch/user-data"], "ordinary": ["VPC/subnets/SG", "NAT ASGs/EIPs", "ALB/TGs", "flow log/log group"]},
            "secrets": {"security": ["secret metadata/KMS linkage"], "ordinary": []},
            "security": {"security": ["WP2A requests", "WP2B storage", "WP2C compute/roles", "WP2D declarations/publication"], "ordinary": []},
            "external": {"security": ["admin authentication", "security backend/lock"], "ordinary": []}}}


def validate(doc):
    c = doc.get("ownership_closure")
    require(isinstance(c, dict), "ownership closure required")
    require({**c, "publications": {}} == catalog(), "closed ownership/dependency/consumer/recovery contract drift")
    require(isinstance(c["publications"], dict), "admin publication registry")
    # Validated separately after structural admission to avoid recursive validation.
    return c


def authority_digest(c):
    return digest({**c, "publications": {}})


def validate_publications(doc):
    import publication
    c = validate(doc)
    for context, pub in c["publications"].items():
        require(isinstance(context, str) and context.count("/") == 1, "publication context")
        account, region = context.split("/")
        publication.validate_publication(doc, pub, account, region)


def consumer_wiring(doc):
    """TARGET module input boundary; lifecycle execution is WP5.

    The fixed authority path is admin-controlled source, never security state.
    Only admin-verified publications promoted to this registry are consumable.
    No supplied identifier can override the pinned record, including for KMS UUIDs.
    """
    result = {}
    for consumer, bindings in doc["ownership_closure"]["consumers"].items():
        result["terraform/modules/target/" + consumer + "/main.tf.json"] = {
            "provider": {"aws": {"region": ex("var.region"), "allowed_account_ids": [ex("var.account_id")]}},
            "variable": {"account_id": {"type": "string", "nullable": False}, "region": {"type": "string", "nullable": False},
                         "protected_inputs": {"type": "map(string)", "nullable": False}},
            "locals": {"authority": ex('jsondecode(file("${path.module}/../../../../infra/security/authority.json"))'),
                "publication": ex('try(local.authority.ownership_closure.publications["${var.account_id}/${var.region}"], null)'),
                "expected": ex('try({ for k in ' + json.dumps(bindings) + ' : k => local.publication.records[k].value if local.publication.records[k].available }, {})')},
            "resource": {"terraform_data": {"protected_input": {"input": ex("var.protected_inputs"), "lifecycle": {"precondition": {
                "condition": ex("local.publication != null && length(local.expected) == " + str(len(bindings)) + " && var.protected_inputs == tomap(local.expected)"),
                "error_message": "Missing/unavailable/substituted protected publication. No local security-resource fallback."}}}}},
            "output": {"protected_inputs": {"value": ex("terraform_data.protected_input.output")}}}
    return result


def ex(s):
    return "${" + s + "}"


def wiring(doc):
    c = doc["ownership_closure"]
    tags = {"E1Owner": OWNER, "E1Stage": STAGE}
    resources = {}
    def put(kind, name, body):
        resources.setdefault(kind, {})[name] = body
    def stmt(actions, targets):
        return {"Effect": "Allow", "Action": actions, "Resource": targets}
    # Policy JSON with Terraform interpolations is encoded as literal JSON rather
    # than HCL object syntax. jsonencode(jsondecode(...)) is not needed: AWS accepts JSON strings.
    def policy(statements):
        return json.dumps({"Version": "2012-10-17", "Statement": statements})
    def ident(key):
        return key.replace("/", "_").replace("-", "_")
    def ref(key, attr="arn"):
        kind = {"role": "aws_iam_role", "profile": "aws_iam_instance_profile", "key": "aws_kms_key",
                "secret": "aws_secretsmanager_secret", "repository": "aws_ecr_repository", "bucket": "aws_s3_bucket", "oidc": "aws_iam_openid_connect_provider"}[c["resources"][key]["kind"]]
        return ex(kind + "." + ident(key) + "." + attr)
    records = {}
    for key, item in c["resources"].items():
        name, env, kind = item["name"], item["scope"], item["kind"]
        label = ident(key)
        if kind == "role":
            mode = item["mode"]
            trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Deny" if mode == "INERT" else "Allow",
                "Principal": {"Service": item["service"]}, "Action": "sts:AssumeRole"}]}
            put("aws_iam_role", label, {"name": name, "assume_role_policy": json.dumps(trust), "tags": tags})
            statements = []
            if mode == "INERT":
                statements = [{"Effect": "Deny", "Action": "*", "Resource": "*"}]
            elif mode == "TASK":
                statements = [stmt(["kms:Encrypt", "kms:Decrypt"], ref(env + "/kms"))]
            elif mode in ("SQL", "EXEC"):
                secrets = [env + "/" + k for k in (("sa", "db-user") if mode == "SQL" else ("connection",))]
                statements = [stmt(["secretsmanager:GetSecretValue"] + (["secretsmanager:DescribeSecret"] if mode == "EXEC" else []), [ref(k) for k in secrets]), stmt(["kms:Decrypt"], ref(env + "/kms"))]
                put("aws_iam_role_policy_attachment", label, {"role": ref(key, "name"), "policy_arn": "arn:aws:iam::aws:policy/" + ("AmazonSSMManagedInstanceCore" if mode == "SQL" else "service-role/AmazonECSTaskExecutionRolePolicy")})
            elif mode == "NAT_INSTANCE":
                statements = [stmt(["ec2:DescribeInstances", "ec2:DescribeRouteTables", "ec2:DescribeNetworkInterfaces"], "*")]
            elif mode == "FLOW":
                statements = [stmt(["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"], "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/vpc/demo-" + env + "-flow-logs")]
            put("aws_iam_role_policy", label, {"name": "wp2d-" + label, "role": ref(key, "id"), "policy": policy(statements)})
        elif kind == "profile":
            put("aws_iam_instance_profile", label, {"name": name, "role": ref(item["role"], "name"), "tags": tags})
        elif kind == "key":
            put("aws_kms_key", label, {"description": "KMS for the encryption microservice", "key_usage": "ENCRYPT_DECRYPT",
                "is_enabled": True, "enable_key_rotation": True, "deletion_window_in_days": 30, "multi_region": False,
                "policy": policy([{"Sid": "EnableIAMUserPermissions", "Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::${var.account_id}:root"}, "Action": "kms:*", "Resource": "*"}]), "tags": tags})
            put("aws_kms_alias", label, {"name": name, "target_key_id": ref(key, "key_id")})
        elif kind == "secret":
            put("aws_secretsmanager_secret", label, {"name": name, "kms_key_id": ref(item["key"]), "recovery_window_in_days": 0, "tags": tags})
        elif kind == "repository":
            put("aws_ecr_repository", label, {"name": name, "image_tag_mutability": "IMMUTABLE", "image_scanning_configuration": {"scan_on_push": True}, "tags": tags})
            put("aws_ecr_lifecycle_policy", label, {"repository": ref(key, "name"), "policy": json.dumps({"rules": [{"rulePriority": 1, "description": "Keep last 15 images", "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": 15}, "action": {"type": "expire"}}]})})
        elif kind == "bucket":
            put("aws_s3_bucket", label, {"bucket": name + "${var.account_id}", "tags": tags})
            put("aws_s3_bucket_public_access_block", label, {"bucket": ref(key, "id"), **dict.fromkeys(("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"), True)})
            put("aws_s3_bucket_versioning", label, {"bucket": ref(key, "id"), "versioning_configuration": {"status": "Enabled"}})
            put("aws_s3_bucket_ownership_controls", label, {"bucket": ref(key, "id"), "rule": {"object_ownership": "BucketOwnerEnforced"}})
            put("aws_s3_bucket_server_side_encryption_configuration", label, {"bucket": ref(key, "id"), "rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "AES256"}}})
            # Retention remains CURRENT-equivalent. WP3 must separate/protect qualification prefixes.
            put("aws_s3_bucket_lifecycle_configuration", label, {"bucket": ref(key, "id"), "rule": {"id": "retain-release-history", "status": "Enabled", "filter": {"prefix": ""}, "abort_incomplete_multipart_upload": {"days_after_initiation": 7}, "noncurrent_version_expiration": {"noncurrent_days": 365}}})
        elif kind == "oidc":
            # AWS obtains the provider thumbprint. No TLS data-source/network lookup at generation time.
            put("aws_iam_openid_connect_provider", label, {"url": "https://" + name, "client_id_list": ["sts.amazonaws.com"], "tags": tags})
        records[key] = {"schema": c["record_schema"], "owner": OWNER, "scope": env, "class": kind, "logical_id": key,
            "declaration": item["declaration"], "authority_digest": authority_digest(c), "available": True,
            "value": ref(key), "publication": "ADMIN_OUTPUT_CANDIDATE_NOT_AUTHENTICATED"}
    for key, item in c["recovery"].items():
        records["recovery/" + key] = {"schema": c["record_schema"], "owner": OWNER, "scope": item["scope"], "class": "recovery",
            "logical_id": "recovery/" + key, "declaration": "reservation/recovery/" + key,
            "authority_digest": authority_digest(c), "available": False, "value": None, "publication": "ADMIN_OUTPUT_CANDIDATE_NOT_AUTHENTICATED"}
    return {"terraform": {"required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.50"}}},
        "variable": {"account_id": {"type": "string"}, "region": {"type": "string"}},
        "resource": resources, "output": {"protected_output_candidates": {"value": records}}}
