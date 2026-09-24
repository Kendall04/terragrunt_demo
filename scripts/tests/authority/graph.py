"""Finite conjunctive authority graph. A witness is not an executed exploit.

Every derived edge retains the evaluated action statements and prerequisites.
UNKNOWN is propagated on applicable paths; it is never a missing/denied edge.
"""
from dataclasses import dataclass
from evaluator import Decision, Result, Unsupported, authorize, evaluate
from source import Adapter
from bindings import Bindings
from coverage import Certificate, fingerprint
import json


@dataclass
class Rule:
    target: str
    prerequisites: tuple[str, ...]
    checks: tuple[Result, ...]
    meaning: str
    mechanism: str = "repository-witness"


VALIDITY_AXES = ("ADMISSION", "IDENTITY_FACTS", "SOURCE_BINDING", "APPLICABILITY",
                 "ROUTE_GROUNDING", "NEGATIVE_COMPLETENESS")


def merge_validity(items):
    """Keep input-validity dimensions separate; a verdict never fills a gap."""
    result = {}
    for axis in VALIDITY_AXES[:4]:
        supplied = [item[axis] for item in items if axis in item]
        values = [value for value in supplied if value != "NOT_APPLICABLE"]
        result[axis] = ("UNKNOWN" if "UNKNOWN" in values else
                        "NOT_APPLICABLE" if supplied and not values else
                        "NOT_EVALUATED" if not values or "NOT_EVALUATED" in values else
                        "SUPPORTED" if all(x == "SUPPORTED" for x in values) else "UNKNOWN")
    return result


def check_validity(checks):
    items = []
    for check in checks:
        supplied = [p["evidence_validity"] for p in check.provenance if "evidence_validity" in p]
        items.append(merge_validity(supplied))
    return merge_validity(items)


def route_validity(rule, states, traces, complete=False):
    items = ([check_validity(rule.checks)] if rule.checks else [])
    items += [traces[p].get("evidence_validity", {}) for p in rule.prerequisites]
    axes = merge_validity(items)
    grounded = (all(states[p] == Decision.ALLOW for p in rule.prerequisites) and
                all(c.decision == Decision.ALLOW for c in rule.checks))
    axes.update({"ROUTE_GROUNDING": "SUPPORTED" if grounded else "NO_GROUNDED_WITNESS",
                 "NEGATIVE_COMPLETENESS": "SUPPORTED" if complete else "NOT_PROVEN"})
    return axes


def unknown_codes(checks):
    reasons = " ".join(y for x in checks for y in x.reasons)
    codes = []
    if "SOURCE_BINDING" in reasons:
        codes.append("SOURCE_BINDING_UNKNOWN")
    if "SEMANTIC_ADMISSION" in reasons or "INVALID_IDENTITY" in reasons or "INVALID_RESOURCE" in reasons:
        codes.append("SEMANTIC_ADMISSION_UNKNOWN")
    if "UNKNOWN_APPLICABLE_CONTROL" in reasons:
        codes.append("UNKNOWN_APPLICABLE_CONTROL")
    if "UNKNOWN_ROUTE_ALTERNATIVE" in reasons:
        codes.append("UNKNOWN_ROUTE_ALTERNATIVE")
    return codes or ["UNKNOWN_INCOMPLETE_PATHS"]


def closure(seeds, rules, coverage=None, universe=None):
    # Coverage is an explicit claim about the outcome, never inferred from edges.
    coverage = coverage or {}
    targets = {r.target for r in rules} | {p for r in rules for p in r.prerequisites}
    states, traces = {}, {}
    for target in sorted(targets):
        claim = coverage.get(target, {"status": "PARTIAL", "reason": "No exhaustive path-space proof"})
        if isinstance(claim, Certificate):
            complete = universe is not None and universe.validates(claim, target, seeds, rules)
            claim = {"status": "COMPLETE_FOR_CURRENT_ADMITTED_MODEL" if complete else "UNKNOWN",
                     "reason": "Validated source-bound certificate" if complete else "Invalid/stale completeness certificate",
                     "certificate": claim.__dict__}
        elif claim["status"] not in ("COMPLETE_FOR_CURRENT_ADMITTED_MODEL", "PARTIAL", "UNKNOWN") or not claim.get("reason"):
            raise ValueError("invalid outcome coverage")
        else:
            complete = False
            if claim["status"] == "COMPLETE_FOR_CURRENT_ADMITTED_MODEL":
                claim = {"status": "UNKNOWN", "reason": "A label is not completeness evidence"}
        states[target] = Decision.DENY if complete else Decision.UNKNOWN
        traces[target] = {"coverage": claim, "reason_codes": ["EFFECTIVE_DENY" if complete else "UNKNOWN_INCOMPLETE_PATHS"],
                          "meaning": "All modeled alternatives denied" if complete else "UNKNOWN_INCOMPLETE_PATH_COVERAGE"}
    states.update({x: Decision.ALLOW for x in seeds})
    traces.update({x: {"seed": True, "evidence_validity": {
        **dict.fromkeys(VALIDITY_AXES[:4], "NOT_APPLICABLE"), "ROUTE_GROUNDING": "SUPPORTED",
        "NEGATIVE_COMPLETENESS": "NOT_REQUIRED_FOR_SEED"}} for x in seeds})
    if universe is not None and not universe.current(seeds, rules):
        return {x: Decision.UNKNOWN for x in states}, {x: {"meaning": "STALE_SOURCE_UNIVERSE", "reason_codes": ["SOURCE_BINDING_UNKNOWN"],
                "evidence_validity": {**dict.fromkeys(VALIDITY_AXES, "NOT_EVALUATED"), "SOURCE_BINDING": "UNKNOWN"}} for x in states}
    if universe is not None and universe.positive_taints():
        return {x: Decision.UNKNOWN for x in states}, {x: {"meaning": "UNKNOWN_APPLICABLE_CONTROL",
                "reason_codes": ["UNKNOWN_APPLICABLE_CONTROL"], "applicable_unknown": universe.positive_taints(),
                "evidence_validity": {**dict.fromkeys(VALIDITY_AXES, "NOT_EVALUATED"), "APPLICABILITY": "UNKNOWN"}} for x in states}
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
                traces[rule.target].update({"route": rule.meaning, "reason_codes": unknown_codes(rule.checks),
                    "prerequisites": rule.prerequisites, "checks": [{"decision": x.decision.value,
                    "reasons": x.reasons, "provenance": x.provenance} for x in rule.checks]})
            if rank[state] > rank[previous]:
                states[rule.target] = state
                traces[rule.target] = {"coverage": traces[rule.target].get("coverage"), "prerequisites": rule.prerequisites, "meaning": rule.meaning,
                                      "route": rule.meaning, "reason_codes": ["WITNESS_ALLOW"] if state == Decision.ALLOW else unknown_codes(rule.checks),
                                      "checks": [{"decision": x.decision.value, "reasons": x.reasons, "provenance": x.provenance}
                                                 for x in rule.checks]}
                changed = True
    # Keep every final alternative, including denied paths which never raised
    # the fixed-point rank. A certificate alone is not primitive provenance.
    # Compute witness axes in prerequisite order. Cyclic references without a
    # grounded seed never acquire a witness merely from reporting metadata.
    for _ in range(len(targets) + 1):
        for target in targets:
            trace = traces[target]
            if trace.get("seed"):
                continue
            selected = next((r for r in rules if r.target == target and r.meaning == trace.get("route")), None)
            complete = (trace.get("coverage") or {}).get("status") == "COMPLETE_FOR_CURRENT_ADMITTED_MODEL"
            if selected:
                trace["evidence_validity"] = route_validity(selected, states, traces, complete)
            else:
                checks = [c for r in rules if r.target == target for c in r.checks]
                trace["evidence_validity"] = {**check_validity(checks),
                    "ROUTE_GROUNDING": "CERTIFIED_NO_GROUNDED_PATH" if complete else "NO_GROUNDED_WITNESS",
                    "NEGATIVE_COMPLETENESS": "SUPPORTED" if complete else "NOT_PROVEN"}
    for target in targets:
        traces[target]["alternatives"] = [
            {"route": rule.meaning, "mechanism": rule.mechanism,
             "prerequisites": {p: states[p].value for p in rule.prerequisites},
             "evidence_validity": route_validity(rule, states, traces,
                 (traces[target].get("coverage") or {}).get("status") == "COMPLETE_FOR_CURRENT_ADMITTED_MODEL"),
             "applicable_unknown": [unknown for p in rule.prerequisites if states[p] == Decision.UNKNOWN
                 for unknown in [{"scope": "UNKNOWN_ROUTE_PREREQUISITE", "prerequisite": p, "route": rule.meaning}]] +
                 [unknown for c in rule.checks for p in c.provenance for unknown in p.get("applicable_unknown", [])],
             "checks": [{"decision": x.decision.value, "reasons": x.reasons,
                         "provenance": x.provenance} for x in rule.checks]}
            for rule in rules if rule.target == target]
    return states, traces


def baseline(root, environments=("dev", "prod")):
    contexts = {env: Adapter(root, env) for env in environments}
    capabilities = json.loads((root / "ci/authority/capabilities.json").read_text())["actions"]
    records = []
    for env, model in contexts.items():
        discovery = model.discovery()
        binding_error = None
        try:
            workload = model.workload()
        except Unsupported as exc:
            binding_error = str(exc)
            workload = {key: "UNBOUND" for key in ("task_role", "exec_role", "family", "service")}
        service_binding_error = workload.get("service_binding_error")
        task_role, exec_role = workload["task_role"], workload["exec_role"]
        family, service = workload["family"], workload["service"]
        routing_error, routing = None, {}
        try:
            routing = Bindings(model).routing()
            listener = routing["listener"]
        except Unsupported as exc:
            routing_error, listener = str(exc), "UNBOUND"
        oidc = model.value("local.github_oidc_provider_arn")
        source_snapshot = fingerprint({"sources": discovery.records, "identity": model.provenance(),
                                       "workload": workload, "routing": routing})

        def admitted(result, subject, action, resource, extra_error=None):
            taints = discovery.taints("github", "api:" + action.split(":")[0].lower())
            if subject in ("task_role", "execution_role") and not binding_error:
                external = discovery.taints_for_role(resource, "terraform/infra/apps/fargate/modules/ecs_service")
                taints = taints + [r for r in external if r not in taints]
            provenance = ({"subject": subject, "action": action, "resource": resource,
                           "source_snapshot": source_snapshot, "policy_statements": result.reasons,
                           "applicable_unknown": taints,
                           "binding_error": extra_error, "effective_bindings_snapshot": fingerprint(model.module_binding),
                           "binding_provenance": "provenance.identity.module_binding",
                           "dependency_output_selection": workload.get("dependency_output_selection")
                               if action == "ecs:UpdateService" else None,
                           "evidence_validity": {"SOURCE_BINDING": "UNKNOWN" if extra_error else "SUPPORTED",
                                                 "APPLICABILITY": "UNKNOWN" if taints else "SUPPORTED"}},) + result.provenance
            if taints or extra_error:
                return Result(Decision.UNKNOWN, tuple(["UNKNOWN_APPLICABLE_CONTROL " + r["source"] + ": " + r["reason"] for r in taints] +
                              ([extra_error] if extra_error else [])), provenance)
            return Result(result.decision, result.reasons, provenance)

        def role_trust(role, arn):
            if binding_error:
                return admitted(Result(Decision.UNKNOWN, (binding_error,)), role, "sts:AssumeRole", arn, binding_error)
            result = evaluate({"action": "sts:AssumeRole", "resource": arn, "principal": "ecs-tasks.amazonaws.com"},
                              trust=[workload["trusts"][role]])
            return admitted(result, role, "sts:AssumeRole", arn)

        task_assume = role_trust("task_role", task_role)
        execution_assume = role_trust("execution_role", exec_role)
        task_controls = workload.get("task_policy_controls", {"status": "UNKNOWN", "reason": binding_error})
        broadening = admitted(Result(Decision.ALLOW if task_controls["status"] != "UNKNOWN" else Decision.UNKNOWN,
                                    (json.dumps(task_controls, sort_keys=True),), ({
                                        "evidence_scope": "STRUCTURAL_TASK_POLICY_CONTROL_ADMISSION",
                                        "source": task_controls,
                                        "evidence_validity": {"ADMISSION": "UNKNOWN" if task_controls["status"] == "UNKNOWN" else "SUPPORTED",
                                            "IDENTITY_FACTS": "NOT_APPLICABLE"}},)),
                               "task_role", "iam:PutRolePolicy", task_role)

        def permission(role, action, resource, context=None, dependencies=None):
            if binding_error and (action.startswith("ecs:") or action == "iam:PassRole" or resource == "UNBOUND"):
                return admitted(Result(Decision.UNKNOWN, (binding_error,)), role, action, resource, binding_error)
            if service_binding_error and action == "ecs:UpdateService":
                return admitted(Result(Decision.UNKNOWN, (service_binding_error,)), role, action, resource, service_binding_error)
            known = model.roles[role]
            if known["unknown"]:
                return Result(Decision.UNKNOWN, tuple(known["unknown"]))
            result = authorize({"action": action, "resource": resource, "context": context or {},
                              "principal": "arn:aws:iam::" + model.values["local.account_id"] + ":role/" + known["name"],
                              "dependencies": dependencies or []}, capabilities,
                             identities=known["policies"])
            return admitted(result, role, action, resource,
                            routing_error if action.startswith("elasticloadbalancing:") else None)

        def passing(role, arn):
            return permission(role, "iam:PassRole", arn, {"iam:PassedToService": "ecs-tasks.amazonaws.com"})

        delivery = "github_dev_deploy" if env == "dev" else "github_prod_promote"
        rules = []
        for role_name, role in model.roles.items():
            token = {"action": "sts:AssumeRoleWithWebIdentity", "resource": "arn:aws:iam::" + model.values["local.account_id"] + ":role/" + role["name"],
                     "principal": oidc, "context": {
                         "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                         "token.actions.githubusercontent.com:sub": model.value("local.github_environment_subject")}}
            rules.append(Rule("acquire:" + role_name, ("environment-token",),
                              (admitted(evaluate(token, trust=[role["trust"]]), role_name, token["action"], token["resource"]),), "shared environment OIDC trust"))
        # API checks below are primitive permissions. Runtime role-dependent actions
        # are expressed explicitly in the conjunctive rule, rather than omitted.
        for principal in (delivery, "github_terragrunt_cd"):
            prefix = "delivery" if principal == delivery else "infra"
            rules.append(Rule(prefix + ":registration", ("acquire:" + principal,),
                              (permission(principal, "ecs:RegisterTaskDefinition", family),),
                              "family-compatible definition with caller-selected runtime content"))
            rules.append(Rule(prefix + ":runtime", (prefix + ":registration",),
                              (passing(principal, task_role), passing(principal, exec_role), task_assume, execution_assume,
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
        rules.append(Rule("infra:stronger-workload-compute", ("infra:broaden-role", "infra:runtime"), (broadening,),
                          "attacker content executes under broadened role; not proof of any KMS key-policy grant"))
        rules.append(Rule("delivery:role-field-substitution", ("delivery:runtime",),
                          (passing(delivery, exec_role), execution_assume),
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
        high_risk = "arn:aws:iam::" + model.values["local.account_id"] + ":role/" + model.roles["github_terragrunt_cd_high_risk"]["name"]
        cross = evaluate({"action": "sts:AssumeRoleWithWebIdentity", "resource": high_risk,
                          "principal": oidc, "context": {
                              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                              "token.actions.githubusercontent.com:sub": "repo:" + model.values["var.github_owner"] + "/" + model.values["var.github_repo"] + ":environment:dev-infra-approval"}},
                         trust=[model.roles["github_terragrunt_cd_high_risk"]["trust"]])
        cross = admitted(cross, "github_terragrunt_cd_high_risk", "sts:AssumeRoleWithWebIdentity", high_risk)
        records.append({"environment": env, "classification": "CURRENT_FACT",
                        "evidence_type": "REPOSITORY_MODEL_REACHABILITY_NOT_EXECUTED_EXPLOIT",
                        "states": {k: v.value for k, v in states.items()}, "traces": traces,
                        "outcomes": {k: {"verdict": "WITNESS_ALLOW" if v == Decision.ALLOW else
                                         "EFFECTIVE_DENY" if v == Decision.DENY else "UNKNOWN",
                                         "coverage": coverage.get(k, {"status": "COMPLETE_FOR_CURRENT_ADMITTED_MODEL", "reason": "explicit seed"})}
                                     for k, v in states.items()},
                        "source_binding": binding_error or ("PARTIAL" if service_binding_error else model.binding_status),
                        "provenance": {"identity": model.provenance(), "source_snapshot": source_snapshot,
                                       "source_admission": discovery.records,
                                       "workload": workload, "routing": routing,
                                       "service_binding_error": service_binding_error,
                                       "routing_error": routing_error,
                                       "witness_scope": "Declared role/service/listener identities with synthetic account/region/provider IDs; policy permission and trust prerequisites, not successful cloud execution",
                                       "policy_scope_only": {"managed_policy": managed,
                                           "lambda": model.value("local.app_scale_down_lambda_arn"),
                                           "ecr": model.value("local.app_ecr_repository_arn"),
                                           "release_object": prod_record}},
                        "remaining_path_gaps": ["existing managed-policy default/attachment expansion", "trust mutation followed by acquisition", "existing compute executable/config and state dependencies"],
                        "dev_approval_to_high_risk": cross.decision.value,
                        "dev_approval_evidence": {"verdict": "WITNESS_ALLOW" if cross.decision == Decision.ALLOW else "UNKNOWN",
                                                  "coverage": "PARTIAL", "scope": "exact supplied token and current trust only",
                                                  "reasons": cross.reasons, "provenance": cross.provenance},
                        "unknowns": {k: v["unknown"] for k, v in model.roles.items() if v["unknown"]}})
    return records
