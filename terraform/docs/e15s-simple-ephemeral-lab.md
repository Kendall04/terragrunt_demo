# E15-S â€” simple disposable portfolio lab

## Current result: preparation, not deployable authority

Baseline/main `bfe0983d696d0e13bcd429c42e635114c5b1b9c5`, explicitly authorized
by the owner after integrating E15-H. E15-H and all protected code remain intact.
Work is on `codex/e15s-simple-ephemeral-dev` in the existing batch1 checkout.
No AWS operations, credentials, provider init, remote Git or installation.

**PARTIALLY_READY.** Local `lab status/up/verify/down/residual` now exists through
[the existing helper](../../scripts/ephemeral_lab.py), using
[simple_lab.py](../../scripts/simple_lab.py). UP prepares an inert, reviewable
single-state Terraform JSON composition. DOWN reviews supplied saved binary/JSON
and state inventory and checks two independent confirmations. Neither command
provisions, destroys, builds, deploys, invokes Terraform, queries AWS, claims
readiness or certifies isolation. Output is local preparation, even with exit 0.
No executable IaC root or unrestricted destroy wrapper was introduced.

Why this boundary: E1 `model.configuration_paths/validate_repository` closes
**all** installable Terraform roots to exact admitted wiring. Existing modules
are tied to protected profiles/metadata, two colors, fixed environments and
WP4 runtime ownership. A new root could not safely become operational merely by
calling it lab; admitting another lifecycle/security root is a material decision.
The smallest alternative is this independently reviewable draft, no IAM changes,
no new control plane, followed by one narrow owner decision before activation.
The draft is saved as `lab.draft.json`, outside the repository, not `.tf.json`,
and includes an always-failing installation precondition. Do not rename/remove
that guard or apply the draft as a workaround for E1. Admission is future work.

## Proposed minimum demonstration

| Keep | Simplify / omit in the fresh lab |
| --- | --- |
| Terraform graph, exact provider/account/region, one independent S3 state | seven layer states and five-plan teardown |
| VPC, one explicit AZ/subnet, IGW, SG references | two NAT instances/ASGs/EIPs, NAT Lambda/EventBridge/DLQs and recovery |
| One Fargate service, immutable existing app image and one-shot readiness probe | blue/green slots, extra listeners, promotion controllers and autoscaling |
| SQL Server Express EC2 with encrypted termination-deleted root EBS | database backup/HA for explicitly disposable lab data |
| KMS Encrypt/Decrypt, Secrets Manager injection, metadata/value separation | protected DEV/PROD dependencies and neutral release/control infrastructure |
| One-day lab app logs | Container Insights, flow-log roles, alarms/SNS and always-running lab automation |
| API access through an authenticated operator SSH tunnel | ALB hourly/LCU cost, API Gateway/VPC Link, publicly reachable API |

This preserves the text API, ciphertext persistence, real SQL/KMS readiness,
container and AWS networking/IAM demonstrations. Public HTTPS/API Gateway and
blue/green remain available in the advanced **protected** architecture. The small
lab is an operator demonstration, not a public website. One AZ is an explicit
availability tradeoff, not production guidance.

A task and SQL host receive in-use public IPv4 addresses for ECR/KMS/secrets/package
egress; subnet automatic assignment is off. SQL port 1433 accepts only the lab
app SG. App port 8080 accepts only the SQL host SG (SSH tunnel); no public API
inbound. Host SSH is restricted to one explicit operator IPv4 /32 and a lab-only
public key. No SSH private key/password/connection value is a Terraform input.
SQL host is also the tunnel endpoint; no separate bastion is added. Once genuinely
installed, operator SSH local forwarding to the independently observed task's
private IP provides localhost API access. Task replacement requires a new observed
IP/tunnel; there is no DNS/endpoint automation or optimistic endpoint output.

The 18-AWS-resource draft (plus the blocking builtin guard) uses the same VPC/public-routing/SG graph patterns, accepted
[SQL user-data](../infra/data/user_data.sh), and actual
[app/probe template](../../demo-api/deploy/task-definition.template.json).
It does not copy or run retired bootstrap/deploy helpers. Existing VPC module
requires two AZs/four subnets/flow role, ALB module assumes two target groups and
internal listener, cluster module enables Insights, service module ignores
runtime changes and its bootstrap definition omits runtime roles. Direct unchanged
composition therefore adds coupled dependencies. This focused draft derives a
smaller graph without refactoring those protected modules. Only lab Terraform
would own task revisions/counts; WP4/WP5 never operate on its proposed state.

## Isolation: selected versus genuinely established

- Target must be `lab`, canonical fresh UUID, explicit 12-digit account/region/AZ.
- Bucket `terragrunt-demo-lab-state-<account>-<region>`, key
  `labs/<uuid>/terraform.tfstate`, workspace `default`, S3 lockfile. No WP5 bucket,
  layer key, remote-state dependency, import/adoption or state migration.
- Resource prefix `demo-lab-<uuid without hyphens>`; exact tags Project
  `terragrunt-demo-lab`, Environment `lab`, LabId UUID, ManagedBy Terraform.
- Own ECR repository, SQL profile, task/execution roles, secret ARN prefix
  `demo/lab/<uuid>/`, keypair and dedicated lab KMS key. Names/tags are only local
  constraints, **not live proof of isolation**. Key/profile association and IAM
  permissions must be independently established before activation.
- Static plan review accepts only the closed draft addresses, resource IDs/tags,
  exact backend/lineage/serial, tagged parents for untaggable objects, full delete inventory and matching supplied
  binary/JSON/configuration/state hashes. These are untrusted local inputs; they
  do not prove JSON came from the binary, that state is current or AWS ownership.
- Existing DEV, PROD, shared and security resources are excluded. An existing
  environment with any historical controller/effect cannot be adopted into this
  path. Stop and reconcile it under its existing authority; never import it.
- Fresh lab installs no NAT/recovery/ASG/scheduled mutator. Native ECS still
  maintains configured tasks until its own service is drained/deleted. Future
  supervised destroy must observe task/instance terminal state and absent ENIs;
  there is no claim that native controller activity disappears from a snapshot.

Same-account versus separate-account operation is **REQUIRES_OWNER_DECISION**.
A separate lab account reduces overlap; neither is selected or fabricated here.
For same-account admission, require exact lab-scoped permissions and denial of
protected/shared state and resource mutation. CIDR `10.77.0.0/16` is proposed;
check actual conflicts before installation. No caller flag unlocks this helper.

## Commands that exist today (all offline)

Copy/edit [lab.example.json](../../ci/ephemeral/lab.example.json) into a private
local path. Every value is illustrative and uninstalled; use metadata only.
The fictitious AMI/account/digest are not usable installation evidence.

```text
python scripts/ephemeral_lab.py lab status --config <private-lab.json>
python scripts/ephemeral_lab.py lab up --config <private-lab.json> --output <new-outside-repo-directory> --confirm "PREPARE LAB <account> <region> <uuid>"
python scripts/ephemeral_lab.py lab verify --config <private-lab.json> [--notes <local-notes.json>]
python scripts/ephemeral_lab.py lab residual --config <private-lab.json> [--notes <local-notes.json>]
python scripts/ephemeral_lab.py lab down --config <private-lab.json> --binary <saved-plan> --plan-json <saved-plan.json> --plan-context <context.json> --state-notes <state-inventory.json> --confirm "DESTROY LAB <account> <region> <uuid> <binary-sha256>" --confirm-sql-loss "PERMANENTLY LOSE LAB SQL <uuid> <binary-sha256>"
```

UP refuses an existing output directory or repository output, then writes only
`lab.draft.json` and `review.json`. It never generates provider/backend files in
the protected checkout. DOWN has **no execution port**. It never silently regenerates
or applies a plan. VERIFY/RESIDUAL accept local notes labelled UNTRUSTED; missing,
failed or superficially all-absent notes leave AWS unverified and potential costs.
There is no implemented CLEAN command. Retained cleanup remains administrator work.
No calls to shell, subprocess, SDK, AWS CLI or credential selection occur.

## Smallest future activation decision and supervised sequence

Approve the narrow **lab-only source/state/IAM boundary**, not another coordinator
or lifecycle platform. Minimum configuration/readbacks before first deployment:

1. Choose actual account, region/AZ, fresh lab UUID and AMI (Ubuntu 22.04 amd64),
   operator /32 and lab SSH public key. Independently verify no adopted resources,
   existing controllers or protected-state overlap. Freeze reviewed source.
2. Separately authenticated administrator establishes the private/versioned lab
   state bucket, encryption/public-access protection and lockfile permissions.
   Runtime may read/write/lock only its exact lab state key; cannot mutate WP5,
   neutral security/control/evidence buckets. Bucket/versions are retained.
3. Administrator creates/reviews lab-only SQL EC2 profile (read just SA/app
   secrets), task role (Encrypt/Decrypt only its lab key), execution role (pull
   only its dedicated ECR, inject only its connection secret, log only lab group),
   key/secret metadata and SSH keypair. Trust is EC2/tasks only; no protected roles,
   OIDC, role chaining or general administrative IAM for the operator. CMK key
   policy/secret encryption and exact ECS PassRole pairs need separate review.
   No IAM/security-root redesign or new role is installed in E15-S.
4. Admit the isolated lab root and restricted supervised human Terraform authority
   without altering WP5. Implement fresh identity/backend/state/resource readbacks
   and binary-to-JSON rendering before an actual apply path. Acquire/verify the
   AWS provider lock in a separately authorized installation task; the draft pins
   versions but does not pretend to contain a validated provider lock/schema.
5. Build/test the existing .NET app and Dockerfile using established local tooling,
   publish to the dedicated lab ECR and freeze digest. WP3/WP4 qualification and
   neutral repositories remain protected; no unsigned lab artifact becomes WP3
   eligible and no retired deploy wrapper is reactivated. Actual lab push is
   administrator-supervised future work, not implemented by this helper.
6. Show/review a genuine single-state UP saved plan with tasks=0. Confirm and
   provision that reviewed binary. Seed SA/app secret values outside Terraform
   before host bootstrap (existing accepted bootstrap waits for them). Observe
   SQL private IP and then seed the lab connection-string secret outside state:
   database LabDemo, login lab_app, encrypted SQL connection. Never print values.
7. Independently observe SQL readiness, image availability and secret injection;
   review a **second same-state** saved plan changing lab task count from 0 to 1.
   Confirm/apply that plan; verify its task/probe exit, `/ready`, SQL and KMS text
   round trip through the operator tunnel. This is a sequential bootstrap, not
   two atomic states. Report actual task IP/resources only after authorized reads.
8. DOWN: freshly check identity, root/workspace/backend/lineage/serial, current
   lab-only ownership and absence of unexpected controllers. Display the complete
   saved destroy binary's rendered JSON. Confirm exact binary and separately
   permanent SQL loss. Apply **that same reviewed binary**, without `destroy
   -auto-approve` or replanning. Terraform dependencies remove service before its
   cluster/task definition/network and SQL dependencies. Observe stopped tasks,
   terminated SQL/root volume and empty state, then exhaust residual AWS checks.

These future actions require separate authorization; do not run them under this
offline task. No task_count=1 command, administrator provisioning, build/push,
Terraform plan/apply or AWS observer is implemented. The purpose of this increment
is a concrete small graph and understandable workflow; it is **preparation**.

## Failure and costs

On any ambiguous or failed provision/deploy/destroy: STOP. Preserve backend state,
private saved plan, exact source/version/configuration and sanitized stage logs.
Report tasks, instance, EBS, public IPv4 and retained dependencies as potentially
billable. No automatic rollback, blind retry, force-unlock or SUCCESS. Human
reconciliation: after separate AWS authorization, compare exact lab state IDs to
fresh service observations; check service/tasks/ENIs, SQL/volumes, routes/SG/VPC;
identify orphans using owner evidence in addition to tags. Do not delete foreign
resources. Review a new exact plan only after state and ambiguous prior effects
are reconciled; obtain both confirmations again. State identity mismatch stops.

Deleted by the proposed lab graph: runtime VPC/subnet/IGW/routes/SGs, SQL instance
and encrypted root EBS, ECS service/task definitions/cluster, app logs. No EIP,
NAT, ALB or API Gateway is installed. Retained administrative dependencies:
versioned S3 state/lock evidence, ECR images, IAM/profile/public key, KMS key and
Secrets Manager metadata/values. Their cleanup requires separate administrator
confirmation/retention policy; KMS deletion is delayed and affects ciphertext.
Unknown until live inventory: detached volumes/snapshots/ENIs/tasks, public IPv4,
partial deletions and unexpected lab-owned resources. Shared resources are excluded.
No approved monthly budget/recipient is invented, no ECR GC/monitoring created,
and no zero-dollar DOWN claim. Rates/usage remain unverified.

## Offline validation and bounded self-check

21 focused deterministic tests exercise the real `ephemeral_lab.py lab` interface,
draft composition, isolation selection, confirmations, exact local plan identity,
partial failure and residual semantics. Positive fixtures are synthetic local
structural reviews, never AWS readiness. Existing E15-H is preserved and tested.
The bounded self-check identified foreign-configuration review reuse at the
report seam and a requirement for tags on intrinsically untaggable routes,
associations and SG rules. Configuration digest checks now reject foreign reviews;
untaggable objects require exact parent IDs belonging to tagged lab resources in
the same state. Deterministic tests cover each such parent relationship. No fake
tag is used to attribute these objects. No secondary reviewer/control-plane investigation was used.

The protected Terraform/Terragrunt/security generation and packages are unchanged.
Source inventory registers the local generator and example input as UNVERIFIED;
that is coverage, not admission of a new Terraform root. Existing TFLint/tfsec
comparison covers admitted repository Terraform, **not** an AWS-provider-validated
lab draft. The lab draft still needs its own provider/schema/security evaluation
at future source admission; no existing findings are suppressed by this task.
Full acceptance results are appended after completion.


## Completed acceptance and delivery

**E1_REPOSITORY_ACCEPTANCE_PASS**: 983 E1/WP tests (959 + WP7 24), AC1-AC16
PASS; all 18 suites and 24 sequential checks (42 result entries) pass. The 21
E15-S tests run through the actual local operator interface; E15-H 54 and E15-G
54 both pass. Existing E15 30 / E15-B 42 / E15-C 46 / E15-D 50 / E15-E 49 /
E15-F 51 / combined 39, E13 40, E2 41 / E2-R 23 / E4 28 and E8 18 pass.
Independent E11 selection 33 and E14-B reproducibility 19 also pass.

Final parsing: 187 Python, 51 JSON, 22 generated JSON-subset YAML. Inventory,
protected package identities, security-root/workflow generation, IAM/trust/PassRole,
DEV/PROD separation, KDD links, immutable E1 specifications and Terraform fmt pass.
All 215 inspected protected Terraform/Terragrunt/security/runtime/spec files
match baseline bytes, including E15-H. No authority.json, installation map,
package digest, policy, generated root, provider lock or protected binding changed.
Activation remains 0/11, 0/16, 0/8. The source inventory registers seven changed/new
operational inputs without certifying a lab installation.

Fresh TFLint/tfsec comparison against E15-H: exact identity AND multiplicity,
24 warnings / 46 findings, no additions/removals/suppressions in admitted Terraform.
The inert lab composition is explicitly outside that provider/security acceptance;
its future admission still requires AWS provider-schema/security validation.
Preinstalled Terraform validates the guard using only its builtin terraform_data
provider and a temporary **local** plan fails on the installation precondition.
A provider-free Terraform JSON roundtrip and rendered existing SQL Bash syntax
check pass. No external provider, backend or initialization was used. Terragrunt
check-only formatting and final staged whitespace checks pass. ShellCheck,
actionlint and native YAML parser are unavailable, not PASS. No tools installed.
No application code changed and no fresh .NET/Docker build or live readiness result
is claimed; build/publish remain documented future prerequisites.

Evidence outside the repository:
`C:/Users/PC/AppData/Local/Temp/e15s-final-acceptance-20261012/acceptance.json`,
`e15s-static-comparison.json`, `e15s-preserved-source-and-draft.json`,
`e15s-frozen-source.json`, `e15s-e11.log`, `e15s-e14b.log` in that Temp directory.
The gate's sequential lab/teardown checks ran after the bounded ownership fix;
final evaluated source hashes match the retained final source snapshot. This
results append changes docs only; final link and staged whitespace checks follow.

Initial HEAD/main: `bfe0983d696d0e13bcd429c42e635114c5b1b9c5`.
Delivery: one coherent local commit on `codex/e15s-simple-ephemeral-dev`, final
revision returned after commit and clean index/worktree verification. Main stays
unchanged; E15-H is retained. No clone/worktree, fetch/push/PR, AWS read/write,
provider init, installation, deployment or cleanup occurred.

| Capability | Classification |
| --- | --- |
| Local isolated selection, draft composition, confirmations and plan/residual review | READY_IN_REPOSITORY |
| Actual lab provisioning/deployment/destruction | PARTIALLY_READY: preparation only; no execution port |
| Account choice, dedicated state/IAM/source admission and cleanup retention | REQUIRES_OWNER_DECISION |
| Actual ownership/isolation, provider behavior, app/SQL/KMS readiness and residual absence/cost | REQUIRES_LIVE_AWS_VALIDATION |

The technical direction is feasible with a small derived composition and existing
app/SQL templates. Unchanged protected modules are not directly composable into
a cheap independent lab. The smallest next increment is narrow lab source/IAM/state
admission and fresh readbacks, followed by ordinary supervised saved-plan execution;
no NAT coordinator or distributed recovery is required for a fresh controller-free
lab. Genuine isolation and a runnable UP/DOWN cycle are not yet established.
