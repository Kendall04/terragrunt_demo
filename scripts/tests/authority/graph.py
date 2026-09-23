"""Finite conjunctive authority graph. A witness is not an executed exploit.

Every derived edge retains the evaluated action statements and prerequisites.
UNKNOWN is propagated on applicable paths; it is never a missing/denied edge.
"""
from dataclasses import dataclass
from evaluator import Decision, Result, Unsupported, authorize, evaluate
from source import Adapter, blocks
import json


@dataclass
class Rule:
    target: str
    prerequisites: tuple[str, ...]
    checks: tuple[Result, ...]
    meaning: str


def closure(seeds, rules, coverage=None):
    # Coverage is an explicit claim about the outcome, never inferred from edges.
    coverage = coverage or {}
    targets = {r.target for r in rules} | {p for r in rules for p in r.prerequisites}
    states, traces = {}, {}
    for target in sorted(targets):
        claim = coverage.get(target, {"status": "PARTIAL", "reason": "No exhaustive path-space proof"})
        if claim["status"] not in ("COMPLETE_FOR_CURRENT_ADMITTED_MODEL", "PARTIAL", "UNKNOWN") or not claim.get("reason"):
            raise ValueError("invalid outcome coverage")
        complete = claim["status"] == "COMPLETE_FOR_CURRENT_ADMITTED_MODEL"
        states[target] = Decision.DENY if complete else Decision.UNKNOWN
        traces[target] = {"coverage": claim, "meaning": "All modeled alternatives denied" if complete else "UNKNOWN_INCOMPLETE_PATH_COVERAGE"}
    states.update({x: Decision.ALLOW for x in seeds})
    traces.update({x: {"seed": True} for x in seeds})
    changed = True
    while changed:
        changed = False
        for rule in rules:
            if not all(x in states for x in rule.prerequisites):
                continue
            decisions = [states[x] for x in rule.prerequisites] + [x.decision for x in rule.checks]
            if Decision.DENY in decisions:
                state = Decision.DENY
            elif Decision.UNKNOWN in decisions:
                state = Decision.UNKNOWN
            else:
                state = Decision.ALLOW
            previous = states.get(rule.target)
            # Existential path join: proven path > possible path > denied path.
            rank = {None: -1, Decision.DENY: 0, Decision.UNKNOWN: 1, Decision.ALLOW: 2}
            if state == Decision.UNKNOWN and previous == Decision.UNKNOWN and "prerequisites" not in traces[rule.target]:
                traces[rule.target].update({"prerequisites": rule.prerequisites, "checks": [{"decision": x.decision.value, "reasons": x.reasons} for x in rule.checks]})
            if rank[state] > rank[previous]:
                states[rule.target] = state
                traces[rule.target] = {"coverage": coverage.get(rule.target, {"status": "PARTIAL", "reason": "No exhaustive path-space proof"}), "prerequisites": rule.prerequisites, "meaning": rule.meaning,
                                      "checks": [{"decision": x.decision.value, "reasons": x.reasons}
                                                 for x in rule.checks]}
                changed = True
    return states, traces


def baseline(root):
    contexts = {env: Adapter(root, env) for env in ("dev", "prod")}
    capabilities = json.loads((root / "ci/authority/capabilities.json").read_text())["actions"]
    records = []
    for env, model in contexts.items():
        binding_error = None
        try:
            workload = model.workload()
        except Unsupported as exc:
            binding_error = str(exc)
            workload = {key: "UNBOUND" for key in ("task_role", "exec_role", "family", "service")}
        task_role, exec_role = workload["task_role"], workload["exec_role"]
        family, service = workload["family"], workload["service"]
        listener = model.value("local.app_elbv2_blue_green_mutation_arns")[0].replace("*", "synthetic")
        oidc = model.value("local.github_oidc_provider_arn")
        iam_path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        if binding_error:
            workload_assume = Result(Decision.UNKNOWN, (binding_error,))
        else:
            for kind, typ, name, body in blocks(iam_path.read_text())[0]:
                if kind == "data" and typ == "aws_iam_policy_document":
                    model.docs[name] = (body, iam_path.relative_to(root).as_posix())
            workload_trust = model.document_reference("data.aws_iam_policy_document.ecs_tasks_assume.json")
            workload_assume = evaluate({"action": "sts:AssumeRole", "resource": task_role,
                                       "principal": "ecs-tasks.amazonaws.com"}, trust=[workload_trust])

        def permission(role, action, resource, context=None, dependencies=None):
            if binding_error:
                return Result(Decision.UNKNOWN, (binding_error,))
            known = model.roles[role]
            if known["unknown"]:
                return Result(Decision.UNKNOWN, tuple(known["unknown"]))
            return authorize({"action": action, "resource": resource, "context": context or {},
                              "dependencies": dependencies or []}, capabilities,
                             identities=known["policies"])

        def passing(role, arn):
            return permission(role, "iam:PassRole", arn, {"iam:PassedToService": "ecs-tasks.amazonaws.com"})

        delivery = "github_dev_deploy" if env == "dev" else "github_prod_promote"
        rules = []
        for role_name, role in model.roles.items():
            token = {"action": "sts:AssumeRoleWithWebIdentity", "resource": role["name"],
                     "principal": oidc, "context": {
                         "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                         "token.actions.githubusercontent.com:sub": model.value("local.github_environment_subject")}}
            rules.append(Rule("acquire:" + role_name, ("environment-token",),
                              (evaluate(token, trust=[role["trust"]]),), "shared environment OIDC trust"))
        # API checks below are primitive permissions. Runtime role-dependent actions
        # are expressed explicitly in the conjunctive rule, rather than omitted.
        for principal in (delivery, "github_terragrunt_cd"):
            prefix = "delivery" if principal == delivery else "infra"
            rules.append(Rule(prefix + ":registration", ("acquire:" + principal,),
                              (permission(principal, "ecs:RegisterTaskDefinition", family),),
                              "family-compatible definition with caller-selected runtime content"))
            rules.append(Rule(prefix + ":runtime", (prefix + ":registration",),
                              (passing(principal, task_role), passing(principal, exec_role), workload_assume,
                               permission(principal, "ecs:UpdateService", service)),
                              "registration + both PassRole checks + service activation; before helper validation"))
        rules.append(Rule("infra:broaden-role", ("acquire:github_terragrunt_cd",),
                          (permission("github_terragrunt_cd", "iam:PutRolePolicy", task_role),),
                          "install broader identity policy on reachable task role; no boundary declared"))
        # A newly created managed policy can contain the attacker-selected grants.
        # This needs no pre-existing policy or version, and is independent of inline mutation.
        managed = model.value('"arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-app-authority-fixture"')
        rules.append(Rule("infra:broaden-role", ("acquire:github_terragrunt_cd",),
                          (permission("github_terragrunt_cd", "iam:CreatePolicy", managed),
                           permission("github_terragrunt_cd", "iam:AttachRolePolicy", task_role,
                                      {"iam:PolicyARN": managed})),
                          "create attacker-authored managed policy and attach to bound task role"))
        # These primitive mutation capabilities do not prove their complete downstream
        # paths (default selection, existing attachment, role acquisition, mutable code).
        for label, action, resource in (
                ("create-policy-version", "iam:CreatePolicyVersion", managed),
                ("select-default-version", "iam:SetDefaultPolicyVersion", managed),
                ("mutate-trust", "iam:UpdateAssumeRolePolicy", task_role),
                ("mutate-existing-code", "lambda:UpdateFunctionCode", model.value("local.app_scale_down_lambda_arn")),
                ("invoke-existing-compute", "lambda:InvokeFunction", model.value("local.app_scale_down_lambda_arn"))):
            rules.append(Rule("infra:capability:" + label, ("acquire:github_terragrunt_cd",),
                              (permission("github_terragrunt_cd", action, resource),),
                              "primitive permission only; downstream authority remains PARTIAL"))
        rules.append(Rule("infra:stronger-workload-compute", ("infra:broaden-role", "infra:runtime"), (),
                          "attacker content executes under broadened role; not proof of any KMS key-policy grant"))
        rules.append(Rule("delivery:role-field-substitution", ("delivery:runtime",),
                          (passing(delivery, exec_role), workload_assume),
                          "PassRole service condition cannot distinguish executionRoleArn from taskRoleArn"))
        for principal in (delivery, "github_app_rollback"):
            rules.append(Rule(principal + ":direct-routing", ("acquire:" + principal,),
                              (permission(principal, "elasticloadbalancing:ModifyListener", listener),),
                              "direct listener API contains no release/readiness predicate"))
        prod_record = model.value("local.release_artifacts_bucket_arn") + "/deployments/prod/fixture.json"
        rules.append(Rule("legacy:prod-record-write", ("acquire:github_app_cd",),
                          (permission("github_app_cd", "s3:PutObject", prod_record),),
                          "legacy role writes prod deployment records, including from dev instance"))
        rules.append(Rule("legacy:combined-publish-route", ("acquire:github_app_cd",),
                          (permission("github_app_cd", "ecr:PutImage", model.value("local.app_ecr_repository_arn")),
                           permission("github_app_cd", "elasticloadbalancing:ModifyListener", listener)),
                          "publication and routing in one legacy identity"))
        coverage = {r.target: {"status": "PARTIAL", "reason":
                    "Concrete witness only. Other acquisitions, managed-policy defaults/attachments, trust mutation, resource controls and mutable executable/config paths are not exhaustively expanded."} for r in rules}
        states, traces = closure(["environment-token"], rules, coverage)
        # Independent token: current prod high-risk trust accepts dev approval.
        cross = evaluate({"action": "sts:AssumeRoleWithWebIdentity", "resource": "synthetic-role",
                          "principal": oidc, "context": {
                              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                              "token.actions.githubusercontent.com:sub": "repo:Kendall04/terragrunt_demo:environment:dev-infra-approval"}},
                         trust=[model.roles["github_terragrunt_cd_high_risk"]["trust"]])
        records.append({"environment": env, "classification": "CURRENT_FACT",
                        "evidence_type": "REPOSITORY_MODEL_REACHABILITY_NOT_EXECUTED_EXPLOIT",
                        "states": {k: v.value for k, v in states.items()}, "traces": traces,
                        "outcomes": {k: {"verdict": "WITNESS_ALLOW" if v == Decision.ALLOW else
                                         "EFFECTIVE_DENY" if v == Decision.DENY else "UNKNOWN",
                                         "coverage": coverage.get(k, {"status": "COMPLETE_FOR_CURRENT_ADMITTED_MODEL", "reason": "explicit seed"})}
                                     for k, v in states.items()},
                        "source_binding": binding_error or model.binding_status,
                        "remaining_path_gaps": ["existing managed-policy default/attachment expansion", "trust mutation followed by acquisition", "existing compute executable/config and state dependencies"],
                        "dev_approval_to_high_risk": cross.decision.value,
                        "dev_approval_evidence": {"verdict": "WITNESS_ALLOW" if cross.decision == Decision.ALLOW else "UNKNOWN",
                                                  "coverage": "PARTIAL", "scope": "exact supplied token and current trust only"},
                        "unknowns": {k: v["unknown"] for k, v in model.roles.items() if v["unknown"]}})
    return records
