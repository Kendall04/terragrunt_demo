"""Finite conjunctive authority graph. A witness is not an executed exploit.

Every derived edge retains the evaluated action statements and prerequisites.
UNKNOWN is propagated on applicable paths; it is never a missing/denied edge.
"""
from dataclasses import dataclass
from evaluator import Decision, Result, authorize, evaluate
from source import Adapter, blocks, attributes
import json


@dataclass
class Rule:
    target: str
    prerequisites: tuple[str, ...]
    checks: tuple[Result, ...]
    meaning: str


def closure(seeds, rules):
    states = {x: Decision.ALLOW for x in seeds}
    traces = {x: {"seed": True} for x in seeds}
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
            if rank[state] > rank[previous]:
                states[rule.target] = state
                traces[rule.target] = {"prerequisites": rule.prerequisites, "meaning": rule.meaning,
                                      "checks": [{"decision": x.decision.value, "reasons": x.reasons}
                                                 for x in rule.checks]}
                changed = True
    return states, traces


def baseline(root):
    contexts = {env: Adapter(root, env) for env in ("dev", "prod")}
    capabilities = json.loads((root / "ci/authority/capabilities.json").read_text())["actions"]
    records = []
    for env, model in contexts.items():
        task_role = model.value("local.app_task_role_arns")[1]
        exec_role = model.value("local.app_task_role_arns")[0]
        family = model.value("local.app_ecs_task_definition_arns")[0].replace("*:*", "blue:42")
        service = model.value("local.app_ecs_service_arns")[0].replace("*", "blue")
        listener = model.value("local.app_elbv2_blue_green_mutation_arns")[0].replace("*", "synthetic")
        oidc = model.value("local.github_oidc_provider_arn")
        iam_path = root / "terraform/infra/apps/fargate/modules/ecs_service/iam.tf"
        for kind, typ, name, body in blocks(iam_path.read_text())[0]:
            if kind == "data" and typ == "aws_iam_policy_document":
                model.docs[name] = (body, iam_path.relative_to(root).as_posix())
        workload_uncertainty = []
        for kind, typ, name, body in blocks(iam_path.read_text())[0]:
            if kind == "resource" and typ == "aws_iam_role":
                attrs = attributes(body)
                if attrs.get("assume_role_policy") != "data.aws_iam_policy_document.ecs_tasks_assume.json" or "permissions_boundary" in attrs:
                    workload_uncertainty.append("workload trust/boundary changed: requires graph review")
        workload_trust = model.document_reference("data.aws_iam_policy_document.ecs_tasks_assume.json")
        workload_assume = evaluate({"action": "sts:AssumeRole", "resource": task_role,
                                   "principal": "ecs-tasks.amazonaws.com"}, trust=[workload_trust])
        if workload_uncertainty:
            workload_assume = Result(Decision.UNKNOWN, tuple(workload_uncertainty))

        def permission(role, action, resource, context=None, dependencies=None):
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
        rules.append(Rule("infra:stronger-workload-compute", ("infra:broaden-role", "infra:runtime"), (),
                          "attacker content executes under broadened role; not proof of any KMS key-policy grant"))
        rules.append(Rule("delivery:role-field-substitution", ("delivery:runtime",),
                          (passing(delivery, exec_role), workload_assume),
                          "PassRole service condition cannot distinguish executionRoleArn from taskRoleArn"))
        for principal in (delivery, "github_app_rollback"):
            rules.append(Rule(principal + ":direct-routing", ("acquire:" + principal,),
                              (permission(principal, "elasticloadbalancing:ModifyListener", listener),),
                              "direct listener API contains no release/readiness predicate"))
        prod_record = "arn:aws:s3:::demo-release-artifacts-111122223333/deployments/prod/fixture.json"
        rules.append(Rule("legacy:prod-record-write", ("acquire:github_app_cd",),
                          (permission("github_app_cd", "s3:PutObject", prod_record),),
                          "legacy role writes prod deployment records, including from dev instance"))
        rules.append(Rule("legacy:combined-publish-route", ("acquire:github_app_cd",),
                          (permission("github_app_cd", "ecr:PutImage", model.value("local.app_ecr_repository_arn")),
                           permission("github_app_cd", "elasticloadbalancing:ModifyListener", listener)),
                          "publication and routing in one legacy identity"))
        states, traces = closure(["environment-token"], rules)
        # Independent token: current prod high-risk trust accepts dev approval.
        cross = evaluate({"action": "sts:AssumeRoleWithWebIdentity", "resource": "synthetic-role",
                          "principal": oidc, "context": {
                              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                              "token.actions.githubusercontent.com:sub": "repo:Kendall04/terragrunt_demo:environment:dev-infra-approval"}},
                         trust=[model.roles["github_terragrunt_cd_high_risk"]["trust"]])
        records.append({"environment": env, "classification": "CURRENT_FACT",
                        "evidence_type": "REPOSITORY_MODEL_REACHABILITY_NOT_EXECUTED_EXPLOIT",
                        "states": {k: v.value for k, v in states.items()}, "traces": traces,
                        "dev_approval_to_high_risk": cross.decision.value,
                        "unknowns": {k: v["unknown"] for k, v in model.roles.items() if v["unknown"]}})
    return records
