"""Configuration discovery and conclusion-specific applicability, without Terraform.

Discovery is independent of the editable freshness inventory. JSON/overrides and
unresolved attachment destinations are uncertainty, never implicit extra Allows.
MODELED is issued only for declaration IDs actually consumed by an adapter.
"""
from pathlib import Path
import json
import math
import re
from contracts import load_json
from evaluator import Unsupported, matches

IGNORED_DIRECTORIES = {".git", ".terraform", ".terragrunt-cache", "node_modules", "__pycache__"}


def local_source_target(root, parent, value):
    """Resolve only sources whose entire directory is covered by discovery.

    Excluded cache/vendor directories cannot become an admitted blind spot merely
    because an otherwise literal module source references them.
    """
    if not isinstance(value, str) or not value.startswith(("./", "../")) or "${" in value or "%{" in value:
        raise Unsupported("unsupported local source/dependency expression")
    raw = parent / value
    target = raw.resolve()
    relative = target.relative_to(root)
    if set(relative.parts) & IGNORED_DIRECTORIES:
        raise Unsupported("local source points into an uninspected directory")
    for path in (raw, *raw.parents):
        if path == root.parent:
            break
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise Unsupported("symlinked/junction local source")
    if not target.is_dir():
        raise Unsupported("missing local source")
    return target

# These mechanisms do not attach a caller policy by themselves. Their execution,
# routing and delegation paths remain unclosed, and any embedded policy or
# provisioner is separately rejected. Unknown resource types get no exemption.
OTHER_MECHANISMS = set("""archive_file aws_ami aws_apigatewayv2_api aws_apigatewayv2_integration
aws_apigatewayv2_route aws_apigatewayv2_stage aws_apigatewayv2_vpc_link aws_autoscaling_group
aws_availability_zones aws_caller_identity aws_cloudwatch_event_rule aws_cloudwatch_event_target
aws_cloudwatch_log_group aws_cloudwatch_metric_alarm aws_ecr_repository aws_ecs_cluster
aws_ecs_cluster_capacity_providers aws_ecs_service aws_ecs_task_definition aws_eip aws_flow_log
aws_instance aws_internet_gateway aws_lambda_function aws_launch_template aws_lb aws_lb_listener
aws_lb_listener_rule aws_lb_target_group aws_region aws_route aws_route_table
aws_route_table_association aws_s3_bucket aws_s3_bucket_lifecycle_configuration
aws_s3_bucket_ownership_controls aws_s3_bucket_public_access_block
aws_s3_bucket_server_side_encryption_configuration aws_s3_bucket_versioning
aws_secretsmanager_secret aws_security_group aws_security_group_rule aws_sns_topic
aws_sns_topic_subscription aws_subnet aws_vpc""".split())


def declaration_id(path, kind, typ, name):
    return f"{path}#{kind}:{typ or ''}:{name or ''}"


def literal_json_outputs(document):
    """A deliberately small, reference-free JSON subset that cannot grant authority."""
    def literal(value):
        if value is None or isinstance(value, (bool, int)):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        if isinstance(value, str):
            return "${" not in value and "%{" not in value
        if isinstance(value, list):
            return all(literal(item) for item in value)
        if isinstance(value, dict):
            return all(isinstance(key, str) and literal(item) for key, item in value.items())
        return False
    if not isinstance(document, dict) or set(document) != {"output"} or not isinstance(document["output"], dict):
        return False
    for name, body in document["output"].items():
        if not isinstance(name, str) or not name or not isinstance(body, dict):
            return False
        if "value" not in body or set(body) - {"value", "description", "sensitive"}:
            return False
        if not literal(body["value"]) or ("description" in body and not isinstance(body["description"], str)):
            return False
        if "sensitive" in body and not isinstance(body["sensitive"], bool):
            return False
    return True


class Applicability:
    """Local module-directory reachability, never module execution or input evaluation.

    A file is non-applicable only with a structural reason: an uninvoked module
    directory, an entry point exclusive to another environment, or inert content.
    Undeclared roots and unresolved invocations remain conservative uncertainty.
    """
    def __init__(self, root, parsed, json_documents, env):
        from source import blocks, attributes
        self.root, self.env = Path(root).resolve(), env
        self.edges, self.entries, self.wrapper_edges = {}, {}, {}
        self.module_links, self.dependency_links = [], []
        self.parsed, self.json_documents = parsed, json_documents
        self.targets, self.errors = set(), []

        def local_target(parent, value):
            return local_source_target(self.root, parent, value)

        for rel, children in parsed.items():
            parent = (self.root / rel).parent
            for kind, typ, name, body in children:
                if kind != "module":
                    continue
                try:
                    target = local_target(parent, json.loads(attributes(body)["source"]))
                    self.edges.setdefault(parent, set()).add(target)
                    self.targets.add(target)
                    self.module_links.append((target, parent, typ, rel))
                except (Unsupported, ValueError, KeyError, TypeError):
                    pass  # The declaration record supplies applicable uncertainty.
        # JSON remains semantically unsupported; read only literal source edges so
        # a child reached through JSON cannot incorrectly be called uninvoked.
        for rel, document in json_documents.items():
            parent = (self.root / rel).parent
            modules = document.get("module", {}) if isinstance(document, dict) else {}
            if not isinstance(modules, dict):
                continue
            for label, attrs in modules.items():
                try:
                    target = local_target(parent, attrs["source"])
                    self.edges.setdefault(parent, set()).add(target)
                    self.targets.add(target)
                    self.module_links.append((target, parent, label, rel))
                except (Unsupported, ValueError, KeyError, TypeError):
                    pass

        live = self.root / "terraform/live"
        for path in sorted(live.rglob("terragrunt.hcl")):
            rel = path.relative_to(self.root).as_posix()
            owner = path.relative_to(live).parts[0]
            parent = path.parent
            self.entries[parent] = {"environment": owner, "targets": set()}
            try:
                children, _ = blocks(path.read_text())
                sources = [attributes(body)["source"] for kind, _, _, body in children if kind == "terraform"]
                if len(sources) != 1:
                    raise Unsupported("missing/ambiguous Terraform source")
                target = local_target(parent, json.loads(sources[0]))
                self.entries[parent]["targets"].add(target)
                self.targets.add(target)
                for kind, label, _, body in children:
                    if kind == "dependency":
                        deps = [json.loads(attributes(blocks(body)[1])["config_path"])]
                    elif kind == "dependencies":
                        deps = json.loads(attributes(body)["paths"])
                        if not isinstance(deps, list):
                            raise Unsupported("unsupported dependency collection")
                    else:
                        continue
                    for dependency in deps:
                        dependency_target = local_target(parent, dependency)
                        self.wrapper_edges.setdefault(parent, set()).add(dependency_target)
                        if kind == "dependency":
                            self.dependency_links.append((dependency_target, path, label))
            except (Unsupported, ValueError, KeyError, TypeError) as exc:
                self.errors.append((rel, owner, str(exc)))

        def expand(starts, edges):
            reached = set(starts)
            pending = list(starts)
            while pending:
                for target in edges.get(pending.pop(), ()):
                    if target not in reached:
                        reached.add(target)
                        pending.append(target)
            return reached
        wrappers = expand({p for p, item in self.entries.items() if env is None or item["environment"] == env}, self.wrapper_edges)
        entries = set().union(*(self.entries.get(p, {}).get("targets", set()) for p in wrappers)) if wrappers else set()
        self.reached = expand(entries, self.edges)
        self.reached_wrappers = wrappers
        self.all_reached = expand(set().union(*(x["targets"] for x in self.entries.values())) if self.entries else set(), self.edges)

    def output_relationships(self, source, outputs):
        """Find collisions and potential consumers without evaluating expressions.

        An ordinary, unused literal output cannot attach a control. A consumed
        output still needs a binding consumer to prove its meaning; this small
        JSON adapter does not substitute it into security expressions. Detect
        whole-module references too, rather than relying on a selected attribute.
        """
        from source import clean
        path = self.root / source
        directory = path.parent
        relationships = []
        for rel, children in self.parsed.items():
            if (self.root / rel).parent == directory:
                for kind, name, _, _ in children:
                    if kind == "output" and name in outputs:
                        relationships.append({"kind": "DUPLICATE_OUTPUT", "source": rel, "output": name})
        for rel, document in self.json_documents.items():
            if rel != source and (self.root / rel).parent == directory and isinstance(document, dict):
                other = document.get("output", {})
                if isinstance(other, dict):
                    for name in outputs.keys() & other.keys():
                        relationships.append({"kind": "DUPLICATE_OUTPUT", "source": rel, "output": name})
        def consumes(text, prefix):
            # A literal access to another output is demonstrably disjoint. Whole
            # objects and indexed/dynamic selection cannot establish that fact.
            pattern = prefix + r"(?![A-Za-z0-9_])(?:\.([A-Za-z_][A-Za-z0-9_]*))?"
            return any(match[1] is None or match[1] in outputs for match in re.finditer(pattern, clean(text)))

        for target, parent, label, invocation in self.module_links:
            if target != directory:
                continue
            pattern = r"\bmodule\." + re.escape(label)
            for candidate in sorted(parent.glob("*.tf*")):
                if consumes(candidate.read_text(), pattern):
                    relationships.append({"kind": "POTENTIAL_MODULE_OUTPUT_CONSUMER",
                        "source": candidate.relative_to(self.root).as_posix(), "invocation": invocation})
        for target, wrapper, label in self.dependency_links:
            if directory in self.entries.get(target, {}).get("targets", ()) and consumes(
                    wrapper.read_text(), r"\bdependency\." + re.escape(label) + r"\.outputs"):
                relationships.append({"kind": "POTENTIAL_DEPENDENCY_OUTPUT_CONSUMER",
                    "source": wrapper.relative_to(self.root).as_posix()})
        return relationships

    def classify(self, source):
        path = self.root / source
        directory = path.parent
        relative = path.relative_to(self.root)
        if directory in self.reached:
            return True, "Directory reachable from selected environment's local source/dependency graph"
        if directory in self.all_reached:
            return False, "Module reached only by another environment; no selected dependency reaches it"
        if relative.parts[:2] == ("terraform", "live") and len(relative.parts) > 2:
            if self.env is not None and relative.parts[2] != self.env and directory not in self.reached_wrappers:
                return False, "Other environment wrapper; no selected dependency reaches it"
            return True, "Selected or shared dependency wrapper"
        if "modules" in relative.parts or directory in self.targets:
            return False, "Uninvoked local module directory; Terraform does not load child directories recursively"
        return True, "Unbound root: applicability unresolved; no absence of authority inferred"


class Discovery:
    def __init__(self, root, modeled=(), names=(), env=None):
        from source import blocks, attributes, digest
        self.root = Path(root)
        self.records = []
        self.modules = []
        self.role_scope_patterns = {}
        modeled = set(modeled)
        paths = sorted(p for p in self.root.rglob("*") if p.is_file() and
                       not (set(p.relative_to(self.root).parts) & IGNORED_DIRECTORIES) and
                       (p.suffix == ".tf" or p.name.endswith(".tf.json")))
        parsed, json_documents = {}, {}
        for path in paths:
            rel = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                raise Unsupported("SOURCE_ADMISSION_UNKNOWN symlink: " + rel)
            if path.name.endswith(".tf.json"):
                try:
                    document = load_json(path.read_text())
                    json_documents[rel] = document
                    inert = literal_json_outputs(document)
                except (ValueError, TypeError):
                    inert = False
                self.records.append(dict(source=rel, sha256=digest(path), declaration=None,
                    admission="NON_SECURITY_RELEVANT" if inert else "UNSUPPORTED_APPLICABLE", affects=[] if inert else ["*"],
                    reason="Literal JSON outputs contain no reference or authority" if inert else
                    "Terraform JSON may replace declarations or attach Allow/Deny; no merge interpreter",
                    literal_json_outputs=inert))
                continue
            if path.name == "override.tf" or path.name.endswith("_override.tf"):
                self.records.append(dict(source=rel, sha256=digest(path), declaration=None,
                    admission="UNSUPPORTED_APPLICABLE", affects=["*"],
                    reason="Terraform JSON/override may replace declarations or attach Allow/Deny; no merge interpreter"))
                continue
            try:
                children, remainder = blocks(path.read_text())
                if remainder.strip():
                    raise Unsupported("unparsed top-level configuration")
                parsed[rel] = children
            except (Unsupported, ValueError) as exc:
                self.records.append(dict(source=rel, sha256=digest(path), declaration=None,
                    admission="UNSUPPORTED_APPLICABLE", affects=["*"], reason=str(exc)))
        # Expand only literal local string templates to disjointness patterns.
        # Unresolved variables/locals are wildcards, not fixed synthetic values.
        # In particular ${local.name}-role must not hide a known name prefix,
        # nor may arbitrary Terraform expressions manufacture a narrow pattern.
        local_strings = {}
        for rel, children in parsed.items():
            for kind, _, _, body in children:
                if kind == "locals":
                    try:
                        for key, value in attributes(body).items():
                            ident = (str(Path(rel).parent), key)
                            local_strings[ident] = value if ident not in local_strings else None
                    except Unsupported:
                        pass

        def name_pattern(expression, directory, seen=()):
            if not isinstance(expression, str):
                return "*"
            local = re.fullmatch(r"local\.(\w+)", expression)
            if local:
                key = (directory, local[1])
                return "*" if key in seen else name_pattern(local_strings.get(key), directory, seen + (key,))
            try:
                literal = json.loads(expression)
            except ValueError:
                return "*"
            if not isinstance(literal, str) or "%{" in literal:
                return "*"
            # Nested/escaped interpolation and expression syntax are outside
            # this string-template subset. They cannot establish disjointness.
            if "$${" in literal or re.search(r"\$\{(?![a-zA-Z_]\w*\.\w+\})", literal):
                return "*"
            return re.sub(r"\$\{([^}]+)\}", lambda match:
                          name_pattern(match[1], directory, seen), literal)

        # Resolve foreign attachment destinations structurally, not by directory prefix.
        foreign_roles = {}
        for rel, children in parsed.items():
            for kind, typ, name, body in children:
                if kind == "resource" and typ == "aws_iam_role":
                    try:
                        attrs = attributes(blocks(body)[1])
                        pattern = name_pattern(attrs["name"], str(Path(rel).parent))
                        if not any(matches(pattern, known, insensitive=True) for known in names):
                            scope = "role:" + declaration_id(rel, kind, typ, name)
                            foreign_roles[(str(Path(rel).parent), name)] = scope
                            self.role_scope_patterns[scope] = pattern
                    except (Unsupported, ValueError, KeyError, TypeError):
                        pass
        for rel, children in parsed.items():
            for kind, typ, name, body in children:
                ident = declaration_id(rel, kind, typ, name)
                decl = dict(kind=kind, type=typ, name=name, id=ident)
                record = dict(source=rel, sha256=digest(self.root / rel), declaration=decl)
                status, affects, reason = "UNSUPPORTED_APPLICABLE", ["*"], "Unresolved security relationship"
                if ident in modeled:
                    status, affects, reason = "MODELED", [], "Declaration consumed by the semantic adapter/binding resolver for the stated witness"
                elif kind == "module":
                    try:
                        attrs = attributes(body)
                        source = json.loads(attrs["source"])
                        target = local_source_target(self.root.resolve(), (self.root / rel).parent, source)
                        if any(k in attrs for k in ("count", "for_each", "providers")):
                            raise Unsupported("unmodeled module expansion/provider mapping")
                        if target.as_posix().endswith("/modules/iam_github") and not (rel == "terraform/infra/shared/main.tf" and typ == "iam_github"):
                            raise Unsupported("additional IAM module instance lacks an identity binding")
                        self.modules.append(dict(source=rel, declaration=ident,
                                                 target=target.relative_to(self.root.resolve()).as_posix(), inputs=attrs))
                        # Children are discovered independently; binding consumers must
                        # validate inputs. This does not certify module execution.
                        affects, reason = ["alternate-paths"], "Local module discovered; children inspected; input semantics require a binding consumer"
                    except (Unsupported, ValueError, KeyError, TypeError):
                        reason = "Unresolved module invocation can contribute authority"
                elif kind in ("variable", "locals", "output", "terraform"):
                    status, affects, reason = "NON_SECURITY_RELEVANT", [], "Declaration/configuration only; no grant. Referenced expressions require consumer admission; no provider is executed"
                elif kind == "data" and typ == "aws_iam_policy_document":
                    affects, reason = ["document:" + ident], "Unconsumed document cannot grant independently; every used reference requires semantic admission"
                elif kind == "resource" and typ in ("aws_iam_role_policy", "aws_iam_role_policy_attachment", "aws_iam_instance_profile"):
                    try:
                        attrs = attributes(blocks(body)[1])
                        role = re.fullmatch(r"aws_iam_role\.(\w+)\.(?:name|id)", attrs["role"])
                        scope = foreign_roles.get((str(Path(rel).parent), role[1])) if role else None
                        if scope:
                            affects, reason = [scope], "Attachment targets a module-local role with a name pattern disjoint from queried GitHub principals; its own permissions remain UNKNOWN"
                    except (Unsupported, KeyError):
                        pass
                elif kind == "resource" and typ == "aws_iam_role":
                    scope = foreign_roles.get((str(Path(rel).parent), name))
                    if scope:
                        affects, reason = [scope], "Declared role name pattern disjoint from queried GitHub identities; no foreign trust/permission conclusion admitted"
                elif kind in ("resource", "data") and typ == "aws_iam_policy":
                    # A definition alone does not grant. Every attachment is independently
                    # discovered; unresolved literal/foreign references taint all subjects.
                    affects, reason = ["policy:" + ident], "Managed policy definition; applicable attachment must separately resolve content"
                elif typ and typ.startswith("aws_kms_"):
                    affects, reason = ["api:kms"], "KMS-specific resource authority; KMS authorization remains unsupported"
                elif typ == "aws_lambda_permission":
                    affects, reason = ["api:lambda"], "Unmodeled Lambda resource delegation"
                elif typ == "aws_ecr_lifecycle_policy":
                    affects, reason = ["artifact-retention"], "Lifecycle controls retention, not IAM caller authorization; operational image availability is not evaluated"
                elif typ and ("policy" in typ or typ.startswith("aws_iam_")):
                    reason = "Unsupported policy/identity mechanism may alter queried principals"
                elif kind in ("resource", "data"):
                    if typ in OTHER_MECHANISMS and not re.search(r'\b(policy|permissions_boundary|managed_policy_arns|provisioner|connection)\s*[={"]', body):
                        affects, reason = ["declaration:" + ident, "alternate-paths"], "Known non-policy resource mechanism without embedded policy/provisioner; alternate execution paths remain unclosed. Used identities require binding"
                    else:
                        reason = "Unknown resource mechanism or embedded authority/execution hook"
                else:
                    reason = "Unknown configuration construct"
                record.update(admission=status, affects=affects, reason=reason)
                self.records.append(record)

        applicability = Applicability(self.root, parsed, json_documents, env)
        for rel, owner, error in applicability.errors:
            self.records.append(dict(source=rel, sha256=digest(self.root / rel), declaration=None,
                admission="UNSUPPORTED_APPLICABLE", affects=["*"],
                reason="Unresolved wrapper source/dependency: " + error))
        for record in self.records:
            applicable, reason = applicability.classify(record["source"])
            if record.get("literal_json_outputs"):
                source = record["source"]
                filename = Path(source).name
                override = filename == "override.tf.json" or filename.endswith("_override.tf.json")
                relationships = applicability.output_relationships(source, json_documents[source]["output"])
                record["construct_kind"] = "LITERAL_JSON_OUTPUT"
                record["consumer_relationships"] = relationships
                if override or applicable and relationships:
                    record.update(admission="UNSUPPORTED_APPLICABLE", affects=["*"],
                        reason="JSON output override/collision or potential consumer requires binding admission")
                else:
                    record["reason"] = "Literal JSON outputs have no override, collision, or discovered consumer; module reachability alone adds no control"
                record["security_relevance"] = "UNRESOLVED_CONSUMER_OR_OVERRIDE" if override or applicable and relationships else "INERT_LITERAL_OUTPUT"
            record["applicability"] = {"status": "APPLICABLE" if applicable else "NOT_APPLICABLE",
                                       "environment": env, "reason": reason}
            record["source_support"] = record["admission"]
            if not applicable and record["admission"] == "UNSUPPORTED_APPLICABLE":
                record["admission"] = "UNSUPPORTED_NOT_APPLICABLE"
                record["affects"] = []

    def taints(self, *subjects):
        wanted = set(subjects)
        return [r for r in self.records if r["admission"] == "UNSUPPORTED_APPLICABLE" and
                ("*" in r["affects"] or wanted.intersection(r["affects"]))]

    def taints_for_role(self, role_name, admitted_directory):
        """Additional applicable declarations colliding with a bound workload role.

        A name disjoint from GitHub callers can still name the workload role used
        by a runtime witness. The binding consumer admits that role's own module;
        no sibling/child module is covered by that admission.
        """
        if ":role/" in role_name:
            role_name = role_name.split(":role/", 1)[1].rsplit("/", 1)[-1]
        directory = Path(admitted_directory).as_posix()
        return [record for record in self.records
                if record["admission"] == "UNSUPPORTED_APPLICABLE"
                and Path(record["source"]).parent.as_posix() != directory
                and ("*" in record["affects"] or any(
                    scope in self.role_scope_patterns and matches(self.role_scope_patterns[scope], role_name, insensitive=True)
                    for scope in record["affects"]))]

    def evidence(self, *subjects):
        return {"subjects": list(subjects), "applicable_unknown": self.taints(*subjects),
                "sources": self.records, "module_invocations": self.modules}
