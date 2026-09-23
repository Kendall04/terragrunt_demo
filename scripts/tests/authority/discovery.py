"""Configuration discovery and conclusion-specific applicability, without Terraform.

Discovery is independent of the editable freshness inventory. JSON/overrides and
unresolved attachment destinations are uncertainty, never implicit extra Allows.
MODELED is issued only for declaration IDs actually consumed by an adapter.
"""
from pathlib import Path
import json
import re
from evaluator import Unsupported, matches

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


class Discovery:
    def __init__(self, root, modeled=(), names=()):
        from source import blocks, attributes, digest
        self.root = Path(root)
        self.records = []
        self.modules = []
        modeled = set(modeled)
        ignored = {".git", ".terraform", ".terragrunt-cache", "node_modules", "__pycache__"}
        paths = sorted(p for p in self.root.rglob("*") if p.is_file() and
                       not (set(p.relative_to(self.root).parts) & ignored) and
                       (p.suffix == ".tf" or p.name.endswith(".tf.json")))
        parsed = {}
        for path in paths:
            rel = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                raise Unsupported("SOURCE_ADMISSION_UNKNOWN symlink: " + rel)
            if path.name.endswith(".tf.json") or path.name == "override.tf" or path.name.endswith("_override.tf"):
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
        # Resolve foreign attachment destinations structurally, not by directory prefix.
        foreign_roles = {}
        for rel, children in parsed.items():
            for kind, typ, name, body in children:
                if kind == "resource" and typ == "aws_iam_role":
                    try:
                        attrs = attributes(blocks(body)[1])
                        value = json.loads(attrs["name"])
                        pattern = re.sub(r"\$\{[^}]+\}", "*", value)
                        if not any(matches(pattern, known, insensitive=True) for known in names):
                            foreign_roles[(str(Path(rel).parent), name)] = "role:" + declaration_id(rel, kind, typ, name)
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
                        target = (self.root / rel).parent.joinpath(source).resolve()
                        target.relative_to(self.root.resolve())
                        if not source.startswith(("./", "../")) or not target.is_dir():
                            raise Unsupported("unresolved/nonlocal module")
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

    def taints(self, *subjects):
        wanted = set(subjects)
        return [r for r in self.records if r["admission"] == "UNSUPPORTED_APPLICABLE" and
                ("*" in r["affects"] or wanted.intersection(r["affects"]))]

    def evidence(self, *subjects):
        return {"subjects": list(subjects), "applicable_unknown": self.taints(*subjects),
                "sources": self.records, "module_invocations": self.modules}
