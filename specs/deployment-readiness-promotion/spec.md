# Durable Spec — Deployment Readiness Promotion Gate

Status: Approved for implementation.

## 1. Problem

The current blue/green deployment path can promote a newly started application revision based on liveness without first proving that the candidate can use the dependencies required to serve application traffic.

The application already distinguishes:

- `/health` — process/application liveness
- `/ready` — dependency readiness, including the dependencies required by the application

A candidate that is alive but not ready must not receive promoted traffic.

## 2. Desired Outcome

Before switching traffic to a new blue/green candidate, the deployment process must prove that the candidate is ready to serve application traffic.

If readiness cannot be established, promotion must fail safely and the currently active revision must remain active.

A candidate that never became active is considered a failed promotion attempt, not a rollback of production traffic.

## 3. Required Behavior

### 3.1 Readiness before promotion

The candidate revision must satisfy the application's existing `/ready` contract before the traffic switch occurs.

Successful liveness alone is insufficient for promotion.

### 3.2 Failed readiness

If the candidate is alive but does not become ready within the deployment's bounded readiness policy:

- traffic must not be switched to the candidate;
- the currently active color/revision must remain active;
- the deployment must fail with useful diagnostic information.

The failure path must not present the candidate as successfully deployed.

### 3.3 Readiness stability

Promotion must not depend on an arbitrarily timed single probe when the existing deployment mechanism can reasonably establish readiness over a bounded polling/retry window.

The exact retry count, timing, and implementation mechanism are technical decisions for the Executor based on the current deployment system.

The policy must remain bounded and deterministic.

### 3.4 Liveness remains liveness

This feature does not redefine the normal ALB health-check contract.

`/health` remains the liveness signal unless repository evidence reveals a material incompatibility requiring human review.

`/ready` is introduced as a pre-promotion readiness gate.

### 3.5 Existing successful deployment behavior

For a candidate that becomes ready:

- the existing blue/green traffic-switch mechanism remains intact;
- existing deployment ownership and routing semantics remain unchanged;
- existing post-promotion behavior remains unchanged unless required to enforce this readiness gate.

## 4. Scope Boundaries

This feature does not:

- redesign `/ready`;
- add new application dependencies;
- redesign rollback;
- change autoscaling behavior;
- redesign the ALB or blue/green architecture;
- change the permanent ALB health check from `/health` to `/ready`;
- define recovery behavior for dependency failure after a successful promotion;
- solve unrelated deployment or release-provenance issues;
- require live AWS infrastructure for deterministic validation.

If repository evidence shows that enforcing readiness requires a material architecture, public contract, or rollback-policy change, stop and request a human decision rather than expanding scope.

## 5. Acceptance Criteria

1. A candidate cannot receive promoted traffic until its `/ready` endpoint has satisfied the deployment readiness gate.
2. `/health` success alone cannot authorize traffic promotion.
3. A candidate that remains not ready causes the deployment attempt to fail.
4. Failed readiness leaves the previously active revision/traffic target unchanged.
5. Readiness evaluation is bounded and does not wait indefinitely.
6. Transient startup readiness can be handled by an appropriate retry/polling mechanism rather than requiring an arbitrarily timed single probe.
7. A successfully ready candidate continues through the existing blue/green promotion flow without unrelated behavioral changes.
8. The permanent ALB liveness/health-check contract is not changed to `/ready` by this feature.
9. Deterministic tests demonstrate both successful readiness promotion and readiness-failure/no-switch behavior without requiring live AWS.
10. No unrelated infrastructure, rollback, application-domain, autoscaling, or deployment behavior is changed.

## 6. Execution Guidance

The Executor should follow `AGENTS.md` and relevant KDD, then inspect the repository before editing to determine:

- the actual blue/green promotion sequence;
- where candidate liveness is currently established;
- how the candidate endpoint can be addressed before promotion;
- the existing polling/wait mechanisms and failure semantics;
- the exact traffic-switch boundary;
- the safest deterministic test seams for proving that an unready candidate cannot reach that boundary.

Implementation details are intentionally not prescribed here.

Make reasonable reversible technical decisions directly.

Stop for human input only if repository evidence exposes ambiguity that materially affects architecture, production traffic semantics, security, rollback policy, or the requirements above.

## 7. Review Contract

Review the implementation directly against this specification.

The Reviewer must verify, with implementation and test evidence, that readiness is established before the traffic-switch boundary and that readiness failure preserves the previously active target.

Passing implementation tests without proving those ordering properties is insufficient.
