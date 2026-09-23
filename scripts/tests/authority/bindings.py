"""Narrow current module-instance bindings. No provider or HCL execution.

Values unknown to this resolver do not inherit an allowlist identity. Each
resource result includes its declaration and the exact relationships checked.
"""
import json
import re
from pathlib import Path
from evaluator import Unsupported
from discovery import declaration_id


class Bindings:
    def __init__(self, model):
        self.model, self.root = model, model.root
        self.evidence = []

    def declarations(self, directory):
        from source import blocks
        result = []
        seen = set()
        for path in sorted((self.root / directory).glob("*.tf*")):
            if path.suffix != ".tf" or path.name == "override.tf" or path.name.endswith("_override.tf"):
                raise Unsupported("SOURCE_BINDING_FAILURE JSON/override module: " + str(path))
            children, remainder = blocks(path.read_text())
            if remainder.strip():
                raise Unsupported("SOURCE_BINDING_FAILURE unparsed module remainder")
            for k, t, n, b in children:
                ident = (k, t, n)
                if k != "locals" and ident in seen:
                    raise Unsupported("SOURCE_BINDING_FAILURE duplicate module declaration")
                seen.add(ident)
                result.append((k, t, n, b, path.relative_to(self.root).as_posix()))
        return result

    def one(self, directory, kind, typ, name=None):
        from source import attributes, blocks, digest
        found = [(b, p) for k, t, n, b, p in self.declarations(directory) if (k, t, n) == (kind, typ, name)]
        if len(found) != 1:
            raise Unsupported("SOURCE_BINDING_FAILURE missing/ambiguous declaration: " + str((directory, kind, typ, name)))
        body, path = found[0]
        attrs = attributes(blocks(body)[1])
        ident = declaration_id(path, kind, typ, name)
        self.evidence.append(dict(source=path, sha256=digest(self.root / path), declaration=ident,
                                  admitted_construct="scalar identity/reference attributes", expressions=attrs))
        return attrs

    def locals(self, directory):
        from source import attributes
        result = {}
        for k, t, n, b, p in self.declarations(directory):
            if k == "locals":
                more = attributes(b)
                if set(result) & set(more):
                    raise Unsupported("SOURCE_BINDING_FAILURE duplicate locals")
                result.update(more)
        return result

    def scalar(self, expression, directory, values=None):
        model = self.model
        old_locals, old_values = model.locals, model.values
        try:
            model.locals = self.locals(directory)
            model.values = old_values | (values or {})
            value = model.value(expression)
            if not isinstance(value, str):
                raise Unsupported("SOURCE_BINDING_FAILURE non-scalar identity")
            return value
        finally:
            model.locals, model.values = old_locals, old_values

    def require(self, attrs, expected):
        for key, value in expected.items():
            if attrs.get(key) != value:
                raise Unsupported("SOURCE_BINDING_FAILURE unresolved relationship: " + key)
        if set(attrs) & {"count", "for_each", "providers"}:
            raise Unsupported("SOURCE_BINDING_FAILURE expanded/aliased module instance")

    def layer_inputs(self, layer, source):
        """Validate the live wrapper which supplies a concrete module instance."""
        from source import blocks, attributes, digest
        path = f"terraform/live/{self.model.env}/{layer}/terragrunt.hcl"
        children, rest = blocks((self.root / path).read_text())
        expected = {("include", "env"): {"path": 'find_in_parent_folders("root.hcl")'},
                    ("locals", None): {"parent": 'read_terragrunt_config(find_in_parent_folders("root.hcl"))'},
                    ("terraform", None): {"source": json.dumps(source)}}
        for identity, fields in expected.items():
            bodies = [b for k, t, n, b in children if (k, t) == identity and n is None]
            if len(bodies) != 1:
                raise Unsupported("SOURCE_BINDING_FAILURE ambiguous layer wrapper")
            self.require(attributes(bodies[0]), fields)
        if any((k, t) not in expected and k not in ("dependency", "dependencies") for k, t, n, b in children):
            raise Unsupported("SOURCE_BINDING_FAILURE unmodeled layer generation/hooks")
        attrs = attributes(rest)
        if set(attrs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown layer inputs")
        self.require(attributes(attrs["inputs"][1:-1]), {
            "env": "local.parent.locals.env", "project": "local.parent.locals.project_name"})
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "layer source/environment/project relationship"})

    def task_policy_controls(self, base, child, module):
        """Prove only absence of an existing task identity-policy Deny.

        This narrow jsonencode grammar does not claim its resource grants are
        effective. Unknown policy sources/expressions invalidate broadening.
        """
        from source import attributes, split_top
        def obj(text):
            if not (text.startswith("{") and text.endswith("}")):
                raise Unsupported("unmodeled policy object")
            return attributes("\n".join(x.rstrip(",") for x in split_top(text[1:-1], "\n")))
        attachments = []
        for k, t, n, b, p in self.declarations(child):
            if k == "resource" and t in ("aws_iam_role_policy", "aws_iam_role_policy_attachment"):
                attrs = attributes(b)
                if attrs.get("role") not in ("aws_iam_role.task_role.name", "aws_iam_role.execution_role.name"):
                    raise Unsupported("unresolved workload policy destination")
                if attrs.get("role") == "aws_iam_role.task_role.name":
                    if t != "aws_iam_role_policy_attachment" or set(attrs) != {"role", "policy_arn", "for_each"}:
                        raise Unsupported("unmodeled task policy attachment")
                    if attrs["for_each"] != "{ for idx, arn in var.task_policy_arns : idx => arn }" or attrs["policy_arn"] != "each.value":
                        raise Unsupported("unmodeled task policy expansion")
                    attachments.append(n)
        if len(attachments) != 1:
            raise Unsupported("unmodeled task policy attachment set")
        expr = module.get("task_policy_arns", "[]")
        if not (expr.startswith("[") and expr.endswith("]")):
            raise Unsupported("unresolved task policy inputs")
        for reference in split_top(expr[1:-1]):
            match = re.fullmatch(r"aws_iam_policy\.(\w+)\.arn", reference)
            if not match:
                raise Unsupported("unsnapshotted task managed policy")
            attrs = self.one(base, "resource", "aws_iam_policy", match[1])
            if set(attrs) - {"name", "description", "policy", "tags"}:
                raise Unsupported("unmodeled task policy declaration")
            expr = attrs["policy"]
            if not (expr.startswith("jsonencode(") and expr.endswith(")")):
                raise Unsupported("unmodeled task policy content")
            doc = obj(expr[11:-1])
            if set(doc) != {"Version", "Statement"} or doc["Version"] != '"2012-10-17"':
                raise Unsupported("unmodeled task policy envelope")
            statements = doc["Statement"]
            if not (statements.startswith("[") and statements.endswith("]")):
                raise Unsupported("unmodeled task statements")
            for statement in split_top(statements[1:-1]):
                fields = obj(statement)
                if set(fields) - {"Sid", "Effect", "Action", "Resource"} or not {"Effect", "Action", "Resource"} <= set(fields) or fields["Effect"] != '"Allow"':
                    raise Unsupported("task policy may contain a Deny or unmodeled control")
                # Even in an Allow-only admission, do not accept dynamic policy
                # construction disguised as a value in this closed grammar.
                actions = json.loads(fields["Action"])
                if not isinstance(actions, list) or not actions or not all(isinstance(a, str) and a for a in actions):
                    raise Unsupported("unmodeled task policy actions")
                if not re.fullmatch(r"var\.\w+|\"[^\"$]*\"", fields["Resource"]):
                    raise Unsupported("unmodeled task policy resource expression")
        return {"status": "ADMITTED_ALLOW_ONLY_TASK_POLICIES", "scope": "no existing identity Deny; no resource-policy/KMS grant asserted"}

    def github(self):
        self.environment_inputs()
        attrs = self.one("terraform/infra/shared", "module", "iam_github")
        self.require(attrs, {"source": '"./modules/iam_github"', "env": "var.env", "project": "var.project",
            "github_owner": "var.github_owner", "github_repo": "var.github_repo",
            "tf_state_bucket_name": "var.tf_state_bucket_name", "tf_state_lock_table_name": "var.tf_state_lock_table_name",
            "github_oidc_provider_arn": "var.github_oidc_provider_arn",
            "create_github_oidc_provider": "var.create_github_oidc_provider",
            "release_artifacts_bucket_name": "local.release_artifacts_bucket_name",
            "shared_artifact_ecr_repository_name": "local.shared_artifact_ecr_repository_name"})
        name = self.scalar(attrs["name"], "terraform/infra/shared")
        if name != self.model.values["var.name"]:
            raise Unsupported("SOURCE_BINDING_FAILURE IAM module name differs from synthetic instance")
        # The root's optional coalesce inputs are fixture parameters; the fallback
        # expressions themselves must remain the reviewed wiring, not overridden.
        self.require(self.locals("terraform/infra/shared"), {
            "release_artifacts_bucket_name": 'coalesce(\n    var.release_artifacts_bucket_name,\n    "${var.project}-release-artifacts-${data.aws_caller_identity.current.account_id}",\n  )',
            "shared_artifact_ecr_repository_name": 'coalesce(\n    var.shared_artifact_ecr_repository_name,\n    "${var.project}-shared-demo-ms",\n  )'})
        return self.evidence

    def environment_inputs(self):
        """Admit current Terragrunt input relationships, never run get_env/hooks.

        Provider/account and backend values are explicitly supplied fixture
        parameters. GitHub/project literals must agree with that fixture.
        """
        from source import blocks, attributes, digest
        env = self.model.env
        path = f"terraform/live/{env}/root.hcl"
        children, rest = blocks((self.root / path).read_text())
        if [(k, t, n) for k, t, n, b in children] != [("locals", None, None), ("remote_state", None, None), ("generate", "provider", None)]:
            raise Unsupported("SOURCE_BINDING_FAILURE unreviewed Terragrunt generation/hooks")
        local = attributes(children[0][3])
        self.require(local, {"env": f'get_env("TG_ENV", "{env}")',
                            "aws_region": 'get_env("AWS_REGION", "us-east-1")',
                            "github_owner": json.dumps(self.model.values["var.github_owner"]),
                            "github_repo": json.dumps(self.model.values["var.github_repo"]),
                            "project_name": json.dumps(self.model.values["var.project"])})
        inputs = attributes(rest)
        if set(inputs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown root input mechanism")
        self.require(attributes(inputs["inputs"][1:-1]), {"env": "local.env", "aws_region": "local.aws_region",
            "github_owner": "local.github_owner", "github_repo": "local.github_repo", "project": "local.project_name"})
        generator = children[2][3]
        prefix, marker, content = generator.partition("contents = <<-EOT")
        expected = 'provider "aws" { region = "${local.aws_region}" } data "aws_region" "current" {} EOT'
        if not marker or " ".join(content.split()) != expected:
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported provider generation")
        self.require(attributes(prefix), {"path": '"provider.tf"', "if_exists": '"overwrite"'})
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "fixed root environment/project/OIDC input relationships",
                              "synthetic": "TG_ENV/AWS_REGION/account/backend stand-ins; no host environment evaluated"})
        path = f"terraform/live/{env}/shared/terragrunt.hcl"
        children, rest = blocks((self.root / path).read_text())
        if [(k, t, n) for k, t, n, b in children] != [("include", "env", None), ("locals", None, None), ("terraform", None, None)]:
            raise Unsupported("SOURCE_BINDING_FAILURE unreviewed shared wrapper")
        self.require(attributes(children[0][3]), {"path": 'find_in_parent_folders("root.hcl")'})
        self.require(attributes(children[1][3]), {"parent": 'read_terragrunt_config(find_in_parent_folders("root.hcl"))'})
        self.require(attributes(children[2][3]), {"source": '"../../../infra/shared"'})
        inputs = attributes(rest)
        if set(inputs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown wrapper input mechanism")
        self.require(attributes(inputs["inputs"][1:-1]), {"env": "local.parent.locals.env",
            "github_owner": "local.parent.locals.github_owner", "github_repo": "local.parent.locals.github_repo",
            "project": "local.parent.locals.project_name", "tf_state_bucket_name": "local.parent.locals.tf_state_bucket",
            "tf_state_lock_table_name": "local.parent.locals.tf_state_table"})
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "shared wrapper input references to the admitted root"})

    def workload(self):
        from source import admit_resource
        base = "terraform/infra/apps/fargate"
        child = base + "/modules/ecs_service"
        self.layer_inputs("apps/fargate", "../../../../infra//apps/fargate")
        self.layer_inputs("platform", "../../../infra/platform")
        from source import blocks, attributes
        tg = self.root / f"terraform/live/{self.model.env}/apps/fargate/terragrunt.hcl"
        tg_blocks, tg_rest = blocks(tg.read_text())
        tg_inputs = attributes(tg_rest)["inputs"]
        self.require(attributes(tg_inputs[1:-1]), {"env": "local.parent.locals.env", "project": "local.parent.locals.project_name",
            "aws_region": "local.parent.locals.aws_region", "cluster_arn": "dependency.platform.outputs.cluster_arn",
            "cluster_name": "dependency.platform.outputs.cluster_name"})
        platform_dependencies = [attributes(b) for k,t,n,b in tg_blocks if k == "dependency" and t == "platform"]
        if len(platform_dependencies) != 1:
            raise Unsupported("SOURCE_BINDING_FAILURE platform dependency")
        self.require(platform_dependencies[0], {"config_path": '"../../platform"'})
        module = self.one(base, "module", "demo_api_blue")
        self.require(module, {"source": '"./modules/ecs_service"', "cluster_arn": "var.cluster_arn"})
        if "family" in module:
            raise Unsupported("SOURCE_BINDING_FAILURE task-family override")
        name = self.scalar(module["name"], base)
        values = {"var.name": name}
        roles, trusts = {}, {}
        docs = {}
        for k, t, n, b, p in self.declarations(child):
            if k == "data" and t == "aws_iam_policy_document":
                docs[n] = (b, p)
            if k == "resource" and t == "aws_iam_role":
                roles[n] = admit_resource(t, b)
        if set(roles) != {"task_role", "execution_role"}:
            raise Unsupported("SOURCE_BINDING_FAILURE workload role set")
        old_docs, old_values = self.model.docs, self.model.values
        try:
            # Scope documents to their own module. Equal local names in other
            # modules cannot satisfy a missing workload reference.
            self.model.docs = docs
            self.model.values = old_values | values
            for role, attrs in roles.items():
                if not self.model.exists(attrs):
                    raise Unsupported("SOURCE_BINDING_FAILURE absent workload role")
                trusts[role] = self.model.document_reference(attrs["assume_role_policy"])
        finally:
            self.model.docs, self.model.values = old_docs, old_values
        cluster_module = self.one("terraform/infra/platform", "module", "ecs_cluster")
        self.require(cluster_module, {"source": '"./modules/ecs_cluster"'})
        cluster_input = self.scalar(cluster_module["name"], "terraform/infra/platform")
        cluster_decl = self.one("terraform/infra/platform/modules/ecs_cluster", "resource", "aws_ecs_cluster", "this")
        cluster = self.scalar(cluster_decl["name"], "terraform/infra/platform/modules/ecs_cluster", {"var.name": cluster_input})
        for field in ("cluster_arn", "cluster_name"):
            self.require(self.one("terraform/infra/platform", "output", field), {"value": "module.ecs_cluster." + field})
            self.require(self.one("terraform/infra/platform/modules/ecs_cluster", "output", field),
                         {"value": "aws_ecs_cluster.this." + ("arn" if field == "cluster_arn" else "name")})
        service = self.one(child, "resource", "aws_ecs_service", "this")
        self.require(service, {"cluster": "var.cluster_arn", "task_definition": "aws_ecs_task_definition.this.arn"})
        task = self.one(child, "resource", "aws_ecs_task_definition", "this")
        self.require(task, {"family": "coalesce(var.family, var.name)",
                           "execution_role_arn": "aws_iam_role.execution_role.arn", "task_role_arn": "aws_iam_role.task_role.arn"})
        family_var = self.one(child, "variable", "family")
        self.require(family_var, {"default": "null"})
        account, region = self.model.values["local.account_id"], self.model.values["local.aws_region"]
        result = {"family": f"arn:aws:ecs:{region}:{account}:task-definition/{name}:42",
                  "service": f"arn:aws:ecs:{region}:{account}:service/{cluster}/{self.scalar(service['name'], child, values)}",
                  "binding_status": "BINDING_VALIDATED", "trusts": trusts}
        for key, role in (("task_role", "task_role"), ("exec_role", "execution_role")):
            self.one(child, "resource", "aws_iam_role", role)
            result[key] = "arn:aws:iam::" + account + ":role/" + self.scalar(roles[role]["name"], child, values)
        if result["task_role"].lower() == result["exec_role"].lower():
            raise Unsupported("SOURCE_BINDING_FAILURE colliding workload role identities")
        try:
            result["task_policy_controls"] = self.task_policy_controls(base, child, module)
        except (Unsupported, ValueError, KeyError) as exc:
            result["task_policy_controls"] = {"status": "UNKNOWN", "reason": str(exc)}
        result["provenance"] = self.evidence
        return result

    def routing(self):
        base, child = "terraform/infra/global", "terraform/infra/global/modules/alb"
        self.layer_inputs("global", "../../../infra//global")
        module = self.one(base, "module", "alb")
        self.require(module, {"source": '"./modules/alb"'})
        name = self.scalar(module["name"], base)
        alb = self.one(child, "resource", "aws_lb", "demo_internal_alb")
        self.require(alb, {"load_balancer_type": '"application"'})
        name = self.scalar(alb["name"], child, {"var.name": name})
        listener = self.one(child, "resource", "aws_lb_listener", "demo_http_listener")
        self.require(listener, {"load_balancer_arn": "aws_lb.demo_internal_alb.arn"})
        rule = self.one(child, "resource", "aws_lb_listener_rule", "candidate_rule")
        self.require(rule, {"listener_arn": "aws_lb_listener.demo_http_listener.arn"})
        account, region = self.model.values["local.account_id"], self.model.values["local.aws_region"]
        return {"listener": f"arn:aws:elasticloadbalancing:{region}:{account}:listener/app/{name}/0000000000000001/0000000000000002",
                "identity_kind": "DECLARED_RESOURCE_WITH_SYNTHETIC_PROVIDER_IDS", "provenance": self.evidence}
