"""Narrow current module-instance bindings. No provider or HCL execution.

Values unknown to this resolver do not inherit an allowlist identity. Each
resource result includes its declaration and the exact relationships checked.
"""
import json
import re
from pathlib import Path
from evaluator import Unsupported
from discovery import declaration_id


# Deliberately closed input vocabulary. These names can affect a current
# witness; unknown extras do not become security controls merely by existing.
# Defaults and forwarding expressions are checked separately at each boundary.
SHARED_INPUTS = {
    "env": "fixed", "project": "fixed", "aws_region": "fixed",
    "account_id": "unsupported", "aws_account_id": "unsupported",
    "github_owner": "identifier", "github_repo": "identifier",
    "create_github_oidc_provider": "bool", "github_oidc_provider_arn": "nullable-string",
    "release_artifacts_bucket_name": "nullable-string",
    "shared_artifact_ecr_repository_name": "nullable-string",
    "tf_state_bucket_name": "string", "tf_state_lock_table_name": "string",
    # Creation is distinct from policy scope. These toggles are resolved but
    # do not assert an existing bucket or repository.
    "create_release_artifacts_bucket": "bool", "create_shared_artifact_ecr_repository": "bool",
}
LAYER_INPUTS = {
    "env": "fixed", "project": "fixed", "aws_region": "fixed",
    "account_id": "unsupported", "aws_account_id": "unsupported",
}
WORKLOAD_INPUTS = LAYER_INPUTS | {
    "cluster_arn": "relationship:dependency.platform.outputs.cluster_arn",
    "cluster_name": "relationship:dependency.platform.outputs.cluster_name",
}


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

    def require_exact(self, attrs, expected):
        self.require(attrs, expected)
        if set(attrs) != set(expected):
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported wrapper control: " + str(sorted(set(attrs) - set(expected))))

    def input_object(self, expression):
        from source import attributes
        if not (expression.startswith("{") and expression.endswith("}")):
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported input object")
        return attributes(expression[1:-1])

    def inputs(self, path, expressions, references, schema):
        """Resolve literals and exact admitted references, never execute HCL.

        Unknown names are not implicitly security relevant. Known names are
        fully classified even when not used in a particular positive route.
        """
        from source import digest
        result, records = {}, []
        fixed = {"env": self.model.env, "project": self.model.values["var.project"],
                 "aws_region": self.model.values["local.aws_region"]}
        for key, expression in expressions.items():
            kind = schema.get(key)
            if kind is None:
                records.append({"input": key, "status": "NOT_APPLICABLE",
                                "reason": "not consumed by the current witness input schema"})
                continue
            if kind == "unsupported":
                raise Unsupported("SOURCE_BINDING_FAILURE UNSUPPORTED_APPLICABLE input " + path + ":" + key)
            if kind.startswith("relationship:"):
                if expression != kind.partition(":")[2]:
                    raise Unsupported("SOURCE_BINDING_FAILURE unresolved effective relationship " + key)
                records.append({"input": key, "expression": expression,
                                "status": "SUPPORTED_FIXED_EXPECTATION",
                                "value_kind": "SOURCE_RELATIONSHIP_VALIDATED_BY_WORKLOAD_BINDING"})
                continue
            if expression in references:
                value = references[expression]
            else:
                try:
                    value = json.loads(expression)
                except (ValueError, TypeError):
                    raise Unsupported("SOURCE_BINDING_FAILURE UNSUPPORTED_APPLICABLE input " + path + ":" + key) from None
                if isinstance(value, str) and ("${" in value or "%{" in value):
                    raise Unsupported("SOURCE_BINDING_FAILURE unexpanded input " + key)
            valid = ((kind == "bool" and type(value) is bool) or
                     (kind == "nullable-string" and (value is None or type(value) is str and bool(value))) or
                     (kind in ("string", "fixed", "identifier") and type(value) is str and bool(value)))
            if not valid or kind == "identifier" and not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
                raise Unsupported("SOURCE_BINDING_FAILURE malformed effective input " + key)
            if kind == "fixed" and value != fixed[key]:
                raise Unsupported("SOURCE_BINDING_FAILURE unsupported fixed identity override " + key)
            result[key] = value
            records.append({"input": key, "expression": expression, "value": value,
                            "status": "SUPPORTED_FIXED_EXPECTATION" if kind == "fixed" else "SUPPORTED_AND_RESOLVED"})
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "explicit security-relevant input schema", "inputs": records})
        return result

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
            self.require_exact(attributes(bodies[0]), fields)
        if any((k, t) not in expected and k not in ("dependency", "dependencies") for k, t, n, b in children):
            raise Unsupported("SOURCE_BINDING_FAILURE unmodeled layer generation/hooks")
        attrs = attributes(rest)
        if set(attrs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown layer inputs")
        expressions = self.input_object(attrs["inputs"])
        self.require(expressions, {"env": "local.parent.locals.env", "project": "local.parent.locals.project_name"})
        references = {"local.parent.locals.env": self.model.env,
                      "local.parent.locals.project_name": self.model.values["var.project"],
                      "local.parent.locals.aws_region": self.model.values["local.aws_region"]}
        self.inputs(path, expressions, references, WORKLOAD_INPUTS if layer == "apps/fargate" else LAYER_INPUTS)
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
            parsed_statements = split_top(statements[1:-1])
            if not parsed_statements:
                raise Unsupported("empty task policy statements")
            for statement in parsed_statements:
                fields = obj(statement)
                if set(fields) - {"Sid", "Effect", "Action", "Resource"} or not {"Effect", "Action", "Resource"} <= set(fields) or fields["Effect"] != '"Allow"':
                    raise Unsupported("task policy may contain a Deny or unmodeled control")
                # Even in an Allow-only admission, do not accept dynamic policy
                # construction disguised as a value in this closed grammar.
                actions = json.loads(fields["Action"])
                if not isinstance(actions, list) or not actions or not all(isinstance(a, str) and
                        (a == "*" or re.fullmatch(r"[A-Za-z0-9-]+:[A-Za-z0-9*?]+", a)) for a in actions):
                    raise Unsupported("unmodeled task policy actions")
                if not re.fullmatch(r"var\.\w+|\"[^\"$]*\"", fields["Resource"]):
                    raise Unsupported("unmodeled task policy resource expression")
                if fields["Resource"].startswith("var."):
                    declaration = self.one(base, "variable", fields["Resource"][4:])
                    self.require(declaration, {"type": "string"})
                    # Admit every literal envelope/statement field even for an
                    # unresolved scalar Resource. The wildcard here validates
                    # structure only; it is never evaluated as a policy grant.
                    from evaluator import admit_policy, PolicyKind
                    literal = {k: json.loads(v) for k, v in fields.items() if k != "Resource"}
                    literal["Resource"] = "*"
                    admit_policy({"Version": "2012-10-17", "Statement": [literal]}, PolicyKind.IDENTITY_POLICY)
                else:
                    from evaluator import admit_policy, PolicyKind
                    # Literal documents receive the same kind grammar as other
                    # primitives. Symbolic scalar resources above support only
                    # this structural no-Deny claim, never a resource grant.
                    literal = {k: json.loads(v) for k, v in fields.items()}
                    admit_policy({"Version": "2012-10-17", "Statement": [literal]}, PolicyKind.IDENTITY_POLICY)
        return {"status": "ADMITTED_ALLOW_ONLY_TASK_POLICIES", "document_kind": "IDENTITY_POLICY",
                "admission": "STRUCTURAL_ALLOW_ONLY_TEMPLATE", "scope": "no existing identity Deny; scalar resource dependency remains unresolved; no resource-policy/KMS grant asserted"}

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
                            "tf_state_bucket": 'get_env("TF_STATE_BUCKET", "tfstate-demo-${local.env}")',
                            "tf_state_table": 'get_env("TF_STATE_TABLE", "tfstate-locks")',
                            "github_owner": json.dumps(self.model.values["var.github_owner"]),
                            "github_repo": json.dumps(self.model.values["var.github_repo"]),
                            "project_name": json.dumps(self.model.values["var.project"])})
        inputs = attributes(rest)
        if set(inputs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown root input mechanism")
        root_expressions = self.input_object(inputs["inputs"])
        self.require(root_expressions, {"env": "local.env", "aws_region": "local.aws_region",
            "github_owner": "local.github_owner", "github_repo": "local.github_repo", "project": "local.project_name"})
        local_values = {"env": env, "aws_region": self.model.values["local.aws_region"],
                        "github_owner": self.model.values["var.github_owner"],
                        "github_repo": self.model.values["var.github_repo"],
                        "project_name": self.model.values["var.project"],
                        "tf_state_bucket": self.model.values["var.tf_state_bucket_name"],
                        "tf_state_table": self.model.values["var.tf_state_lock_table_name"]}
        effective = self.inputs(path, root_expressions, {"local." + k: v for k, v in local_values.items()}, SHARED_INPUTS)
        generator = children[2][3]
        prefix, marker, content = generator.partition("contents = <<-EOT")
        expected = 'provider "aws" { region = "${local.aws_region}" } data "aws_region" "current" {} EOT'
        if not marker or " ".join(content.split()) != expected:
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported provider generation")
        self.require_exact(attributes(prefix), {"path": '"provider.tf"', "if_exists": '"overwrite"'})
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "fixed root environment/project/OIDC input relationships",
                              "synthetic": "TG_ENV/AWS_REGION/account/backend stand-ins; no host environment evaluated"})
        path = f"terraform/live/{env}/shared/terragrunt.hcl"
        children, rest = blocks((self.root / path).read_text())
        if [(k, t, n) for k, t, n, b in children] != [("include", "env", None), ("locals", None, None), ("terraform", None, None)]:
            raise Unsupported("SOURCE_BINDING_FAILURE unreviewed shared wrapper")
        self.require_exact(attributes(children[0][3]), {"path": 'find_in_parent_folders("root.hcl")'})
        self.require_exact(attributes(children[1][3]), {"parent": 'read_terragrunt_config(find_in_parent_folders("root.hcl"))'})
        self.require_exact(attributes(children[2][3]), {"source": '"../../../infra/shared"'})
        inputs = attributes(rest)
        if set(inputs) != {"inputs"}:
            raise Unsupported("SOURCE_BINDING_FAILURE unknown wrapper input mechanism")
        expressions = self.input_object(inputs["inputs"])
        effective.update(self.inputs(path, expressions,
            {"local.parent.locals." + k: v for k, v in local_values.items()}, SHARED_INPUTS))
        required = {"env", "project", "aws_region", "github_owner", "github_repo",
                    "tf_state_bucket_name", "tf_state_lock_table_name"}
        if not required <= set(effective):
            raise Unsupported("SOURCE_BINDING_FAILURE missing effective inputs: " + str(sorted(required - set(effective))))
        # Defaults are also source evidence. Editing a root variable default must
        # not leave a synthetic effective value behind.
        defaults = {"create_github_oidc_provider": ("bool", "false"), "github_oidc_provider_arn": ("string", "null"),
                    "release_artifacts_bucket_name": ("string", "null"),
                    "shared_artifact_ecr_repository_name": ("string", "null"),
                    "create_release_artifacts_bucket": ("bool", "false"),
                    "create_shared_artifact_ecr_repository": ("bool", "false")}
        for key, (typ, default) in defaults.items():
            declaration = self.one("terraform/infra/shared", "variable", key)
            self.require(declaration, {"type": typ, "default": default})
            if key not in effective:
                effective[key] = json.loads(default)
                self.evidence.append({"input": key, "status": "SUPPORTED_AND_RESOLVED", "value": effective[key],
                                      "default_declaration": "terraform/infra/shared/variables.tf#" + key})
        if effective["create_github_oidc_provider"] and effective["github_oidc_provider_arn"] is not None:
            raise Unsupported("SOURCE_BINDING_FAILURE provider creation conflicts with explicit provider ARN")
        account = self.model.values["local.account_id"]
        provider = effective["github_oidc_provider_arn"]
        expected_provider = f"arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com"
        if provider is not None and provider != expected_provider:
            raise Unsupported("SOURCE_BINDING_FAILURE UNSUPPORTED_APPLICABLE GitHub issuer/provider identity: " + provider)
        effective["github_oidc_provider_arn"] = provider or expected_provider
        effective["github_oidc_provider_mode"] = ("DECLARED_PROVIDER" if effective["create_github_oidc_provider"] else
                                                  "EXPLICIT_PROVIDER_REFERENCE" if provider else "LOOKUP_PROVIDER_REFERENCE")
        effective["release_artifacts_bucket_name"] = (effective["release_artifacts_bucket_name"] or
                                                       f'{effective["project"]}-release-artifacts-{account}')
        effective["shared_artifact_ecr_repository_name"] = (effective["shared_artifact_ecr_repository_name"] or
                                                            f'{effective["project"]}-shared-demo-ms')
        for key in ("release_artifacts_bucket_name", "tf_state_bucket_name"):
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", effective[key]):
                raise Unsupported("SOURCE_BINDING_FAILURE unsupported storage identity " + key)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", effective["tf_state_lock_table_name"]):
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported lock-table identity")
        if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", effective["shared_artifact_ecr_repository_name"]):
            raise Unsupported("SOURCE_BINDING_FAILURE unsupported ECR identity")
        self.model.effective_inputs = effective
        for key in ("github_owner", "github_repo", "tf_state_bucket_name", "tf_state_lock_table_name",
                    "release_artifacts_bucket_name", "shared_artifact_ecr_repository_name"):
            self.model.values["var." + key] = effective[key]
        self.model.values["local.github_oidc_provider_arn"] = effective["github_oidc_provider_arn"]
        self.evidence.append({"source": path, "sha256": digest(self.root / path),
                              "admitted_construct": "effective shared inputs before policy interpolation",
                              "effective_inputs": effective,
                              "scope": "policy scope and declaration/reference identity; no deployed-resource existence asserted"})

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
