# Native DEV lifecycle

Owner decision, 28 October 2026: use native Terraform for the five original DEV
roots. E16 sessions, approvals, shutdown receipts and Python execution are retired.
This guide is an operating procedure, not execution authorization. Every plan,
apply, controller change and destructive operation needs its own explicit scope.

## Owners and prerequisites

`terraform/modules/target/dev/{global,data,platform,apps,edge}` are checked-in,
self-contained **Terraform roots**, including local modules and provider locks.
There are no active Terragrunt wrappers for those five roots. Do not generate a
parallel topology, copy the project or run the retired `terraform/infra` roots.
`terraform/live/security` and `terraform/live/sentinel-backup` have their own
Terragrunt owners; the portable Sentinel trial has separate Terraform ownership.
None belongs to ordinary runtime destroy.

Use Terraform **1.13.4**, locked AWS **5.100.0**, PowerShell **7.4+** and AWS CLI v2.
Terragrunt **0.93.3** is needed only for its actual owners. Do not upgrade locks.
Re-use the checkout and native provider cache, initialize only the next root,
and check disk space before downloads. Do not create another repository/session
copy or edit provider files. Source/input/plan changes invalidate the review.

Use source profile `cnp-cert-dev` to assume only
`arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`, in `us-east-1`.
The existing same-profile AWS configuration can do this without Python: set
`role_arn` to that role, `source_profile=cnp-cert-dev`, `duration_seconds=3600`,
a new identifiable `role_session_name` and the existing approved CA bundle.
Keep credentials in the existing shared credential store, never in this config.
Do not substitute direct administrator credentials or another profile on denial.
The source user's administrative permissions are not operator permissions.

Before authorization, record UTC start/deadline, budget, retirement reserve
(at least 90 minutes for a full trial), exact source commit and selected layer.
No historical USD 12/eight-hour proposal is a renewed budget or an AWS cap.
Ensure permissions last through the approved retirement window; expiration does
not delete resources. No unattended multi-layer execution or automatic retry.

## Before each native operation

1. Require a clean checkout at the owner-reviewed commit: `git status --porcelain`
   and `git rev-parse HEAD`. Preserve pending branches and historical worktrees.
   Also inspect ignored/untracked Terraform sources and automatic var-files in
   the selected root: clean Git status alone does not reveal ignored overrides.
   Reject extra `.tf`, `.tf.json`, `.auto.tfvars*` or override files; only the
   reviewed tracked source and explicit external var-file may configure the root.
2. Reject inherited access-key/session-token, web-identity, role-override and
   `TF_CLI_ARGS*` / unreviewed `TF_VAR_*` variables. Set only the approved profile/config and region;
   use the same environment for CLI and Terraform. Run `aws sts get-caller-identity`:
   require account `341936017254` and an assumed-role ARN for exactly
   `TerragruntDemoDevOperator`. Record ARN and UTC, never credentials.
3. Verify the backend below: region, versioning Enabled, private access, AES256,
   TLS Deny and the installed exclusive state-writer policy. The historical
   `E16*` policy Sids remain valid independent security controls. Never rename or
   remove them merely because the executor retired. Other principals, including
   WP5, must not write these five states concurrently.
4. Read the existing E2 application head privately from
   `e1-wp4-dev-341936017254-us-east-1/arbitration/dev/application.json` with its
   VersionId. Require RELEASED, no cleanup schedule, no active protected builds
   or conflicting delivery/recovery. Freeze dispatches while operating; do not
   manufacture/release an E2 owner. For full lifecycle, retain WP3/WP4/E13 guards.
5. HEAD all five exact state objects and record VersionId/ETag privately. List
   exact `.tflock` objects. An existing lock or ambiguous operation means stop;
   never force-unlock. State values are read internally by Terraform, not printed
   into public logs. Read no secret values or security state.
6. Use an existing external private directory. On Windows verify owner=current
   user, inheritance disabled, only that user and SYSTEM with inheritable
   FullControl; reject links/junctions and broad access. Store inputs, plans,
   show JSON, raw stderr and inventories there. Verify new files inherit those
   permissions. Raw diagnostics can be sensitive; publish only sane counts/errors.

These are human-reviewed native readbacks, not a new session manifest or approval
engine. Stop on missing permission; never disable locking or security software.

## Backend and command pattern

For **every** runtime root: bucket
`e1-lifecycle-dev-341936017254-us-east-1`, key
`e1/lifecycle/dev/<layer>/terraform.tfstate`, default workspace,
workspace prefix `e1/lifecycle/dev/<layer>/terraform.tfstate/workspaces`.
Keep S3 encryption and `use_lockfile=true`; no local/alternate state or migration.

The following commands are examples for a separately authorized operation. Check
`$LASTEXITCODE` immediately after **each** native command; nonzero means stop.
Do not execute the block as an unattended script.

```powershell
$Repo = 'C:\proyectos\terragrunt_demo'
$Layer = 'global' # Explicitly select the single next approved root.
$Root = Join-Path $Repo "terraform\modules\target\dev\$Layer"
$Bucket = 'e1-lifecycle-dev-341936017254-us-east-1'
$Key = "e1/lifecycle/dev/$Layer/terraform.tfstate"
$env:AWS_PROFILE = 'cnp-cert-dev'
$env:AWS_REGION = 'us-east-1'; $env:AWS_DEFAULT_REGION = 'us-east-1'
$env:AWS_CONFIG_FILE = Read-Host 'Approved same-profile operator config path'
$env:AWS_PAGER = ''; $env:CHECKPOINT_DISABLE = '1'
$Private = (Resolve-Path (Read-Host 'Existing ACL-verified private directory')).Path
$Vars = Join-Path $Private "$Layer.tfvars.json"
$Plan = Join-Path $Private "$Layer-up.tfplan" # New unused filename per review.
terraform -chdir="$Root" init -input=false -lockfile=readonly `
  "-backend-config=bucket=$Bucket" '-backend-config=region=us-east-1' `
  "-backend-config=key=$Key" "-backend-config=workspace_key_prefix=$Key/workspaces"
terraform -chdir="$Root" workspace show # Require default.
terraform -chdir="$Root" plan -input=false -lock-timeout=60s "-var-file=$Vars" "-out=$Plan"
terraform -chdir="$Root" show -json "$Plan" > "$Plan.json"
terraform -chdir="$Root" show -no-color "$Plan" # Sensitive: review privately.
Get-FileHash -LiteralPath $Plan -Algorithm SHA256
python -I -B scripts/check_native_plan.py --plan-json "$Plan.json" `
  --layer $Layer --direction up --account 341936017254 --region us-east-1
# Add --network-only only for the first global network bootstrap.
```

The optional Python check only reads JSON/declarations, rejects foreign addresses,
tags/ARN scope, replacements, destructive UP, constructive DOWN and delivery-field
changes. It never authorizes/executes apply or proves effective IAM/ownership.
Inspect native state and AWS IDs, retained dependencies, drift, replacements,
unknown values and cost. Any unexpected change blocks; replan only under renewed
authorization. Never use `-refresh=false`, `-lock=false`, `-target` to evade scope,
`state rm`, import/adoption, backend bootstrap or `run --all apply/destroy`.

After **explicit owner approval** of layer, source, input hash, binary SHA256,
counts, cost/window and retention, recheck clean source, input/binary hashes,
identity, E2, locks and the recorded state VersionId/ETag. Abort on drift. Then:

```powershell
terraform -chdir="$Root" apply -input=false -lock-timeout=60s "$Plan"
terraform -chdir="$Root" state list
terraform -chdir="$Root" output -json > "$Private\$Layer.outputs.json"
```

Native apply verifies saved-plan state freshness; the procedure also binds the
reviewed source/inputs. Record new state versions and verify actual native IDs,
tags, counts and absence of locks. Partial apply/timeout/lost response: stop,
preserve evidence and inspect native state; never blindly resend. A fresh reviewed
plan may be required. Do not infer functional health from state reconciliation.

## Inputs and staged UP

Keep one reviewed external tfvars file per layer, including during DOWN. Do not
place values in Git or command-line arguments. No root/backend/provider override.
Supply `account_id`, `region` and the exact `protected_inputs` from available
administrator-promoted records in `terraform/infra/security/authority.json`, using
`ownership_closure.consumers['dev/<layer>']` and the account/region publication.
Missing/unavailable records stop; Terraform's protected-input precondition stays.
Set `alerts_topic_arn=arn:aws:sns:us-east-1:341936017254:demo-dev-shared-alerts`
where the root declares it. No secret values, passwords or connection strings.

| Step | Inputs and completion barrier |
| --- | --- |
| Global network | `protected_nat_launch={}`. VPC/subnets/EIPs/internal ALB only; reject ASG/instance creation. Verify real new IDs and preserve outputs. |
| Global NAT HA | Separate security-owner installation binds those actual subnet/SG/EIP/route IDs into existing launch templates and E13 handlers. Read back both `a`/`b` launch IDs, numeric versions, matching subnets and genuine recovery admission; then set `protected_nat_launch` and review a new global plan. Do not restore old bindings or invent IDs. |
| Data | Real global `private_subnet_ids`, `db_instance_sg_id`, approved `protected_sql_ami`. Existing SQL profile, metadata-only migration/cohost inputs and recovery-subnet membership retain their Terraform/host validations. Backup/observer activation, SQL secrets, TLS/migrations and installation require their existing separate admissions. |
| Platform | Original ECS root, no invented dependency IDs. Verify `cluster_arn`/`cluster_name`. |
| Apps | Real global `private_subnet_ids`, `alb_listener_arn`, `demo_sg_id`, `demo_blue_tg_arn`, `demo_green_tg_arn`, plus real platform outputs. Seed connection secret separately after actual SQL bootstrap. Skeletons remain at zero tasks; WP4 owns revisions/counts and listener forwarding. |
| Edge | Real global `private_subnet_ids`, `alb_listener_arn`, `vpc_link_sg_id`; verify API/VPC Link IDs and service-created ENIs. |

During the security-owner NAT installation, keep `dev_nat_inhibited=true` and
`dev_delivery_inhibited=true` (safe defaults). The [E13 installation contract](e13-nat-reliability.md#current-dev-installation-and-version-transition)
defines the six possible version-bound auxiliary replacements and inhibited
failure/rollback handling. Review the full owner plan; no targeted or manual
state workaround. After the separate NAT plan/budget approval, authorize and
verify E13 activation (`dev_nat_inhibited=false`) before applying that ASG plan;
keep gateway/cleanup inhibited. SNS/KMS notification readiness is a separate
activation prerequisite, not part of this local declaration change.

Obtain real outputs with native `terraform output -json`, keeping the result private;
transfer only declared metadata into the next layer's reviewed tfvars. Do not use
mocks for an AWS plan. No all-layer plan substitutes for these dependency barriers.
WP3 qualification, digest-based WP4 deployment, blue/green and rollback keep their
existing entry/OIDC/E2 contracts. `original_dev.py release/deploy` remains shared
WP6 functionality; its retired `dev` subcommand cannot execute Terraform.
Verify native networking/NAT egress, SQL recovery, service/task readiness, API
readiness and SQL/KMS writes through existing functional procedures with their
own authorization. Native plan/apply success is not that certification.

## DOWN, including network-only bootstrap

Agree on exact resource IDs/state owners, backup/secret retention and explicit
SQL/EBS data-loss approval first. Retain backend versions, security root, KMS,
selected secrets/backups, ECR and E2/E13 evidence. The operator cannot destroy
protected owners. Record before/after native IDs, not a new teardown journal.

1. Freeze dispatches, builds, deployment/recovery and SQL/application writers.
   Observe E2 RELEASED/no schedule and terminate/reconcile active owner work using
   its existing procedure, not an administrative takeover. Inventory existing
   components by state **and** native APIs; a denied read never proves absence.
2. If ECS exists, set only its exact owned services to zero through their native
   service owner and wait for STOPPED tasks. Inhibit/settle SQL backup/observer,
   migrations and host operations using their existing runbooks; preserve selected
   backups and secret metadata. Keep NAT egress until consumers are finished.
3. If NAT ASGs exist, separately authorize disabling the exact
   `e1-wp4-dev-nat-launch` rule and setting concurrency zero only on relevant DEV
   handlers/executors. Read current configuration/targets first; already inhibited
   controls need only readback. Suspend replacement processes on the two actual
   ASGs, preserve prior instances, wait for attributable in-flight E13 effects and
   failure messages, then set exact capacities zero and observe termination and
   completed ASG activities. Do not suspend Terminate. Do not restore controllers
   while resources they can mutate are being removed.
4. Conciliate uncertain effects that can affect **these exact instances, EIPs,
   route tables, ASGs or VPC**. Use native activity, journal/request targets,
   logs/CloudTrail and resource readbacks. Empty metrics/approximate queues or
   elapsed time alone are insufficient. Retain old SDC UNKNOWN unchanged; compare
   target IDs/generation and current controller bindings. Unrelated terminated
   historical targets do not require an E16 disposition or synthetic ACK to
   remove new independent resources. A demonstrable link or unresolved current
   effect blocks until reviewed. Never invoke a handler just to manufacture logs.
5. Prepare/apply one separately approved native destroy plan at a time in
   **edge → apps → platform → data → global** order. Skip only components proven
   absent; preserve recorded input files so removed dependency outputs are not
   needed. Use the same plan pattern with `plan -destroy`, the original var-file,
   a new saved filename and `check_native_plan.py --direction down`; reject
   creation, updates, replacements and retained/foreign resources. Apply only that
   reviewed binary with native locking and explicit destruction approval.
6. After each apply, check state plus exact AWS IDs. Wait for VPC Link/ALB/ECS
   service ENIs before subnet/SG/VPC deletion. Let Terraform/service owners remove
   their children; never directly delete service-owned ENIs. On DependencyViolation
   inspect references and stop; do not force or broaden deletion. Interrupted DOWN
   requires inspection of actual state/IDs and a newly approved plan, not replay.
7. Verify no owned operational EC2/ASG/tasks, EBS, EIP, ALB/TG/listener, VPC Link,
   ENI, SG/rules, routes, subnets, IGW, VPC, Flow Logs or runtime alarms remain.
   Read tags **and recorded VPC/parent IDs** to include untagged service children.
   Confirm all five state inventories, preserved versions and absent locks;
   classify retained, pending, unexpected and unverified resources explicitly.
   Retained storage/keys/secrets/logs can bill; DOWN never means zero AWS cost.
8. Restore only deliberately changed retained controls to their approved prior
   configuration, when no new/retained resources depend on inhibition. Do not
   reactivate old NAT targets. Remove only the temporary IAM deltas; retain old
   versions and Deny protections. If expiration interrupts cleanup, request an
   exact extension from the owner, never use another identity.

**Only bootstrap network exists:** verify the other four states have no runtime,
both NAT ASGs and project EC2/ECS/API resources are absent, and no active retained
controller is bound to the new IDs. Skip task draining, SQL shutdown, ASG capacity,
NAT invocation-history and termination requirements for nonexistent components.
Read back retained rule/concurrency; do not rewrite them merely for a receipt.
Review a global-only saved destroy against its actual state/inputs. Terraform
owns the ALB/listener/rules/TGs, SG rules/groups, Flow Log/log group/alarms, two
EIPs, routes/associations/tables, four subnets, IGW and VPC. Wait for ALB ENIs and
verify exact IDs absent. Counts come from the real destroy plan, not a hardcoded
43. Preserve its final state/version history and independent native readbacks.

## IAM admission and history

The existing operator trust and S3 exclusive writer do not depend on a Python
wrapper. Review installed identity policies, boundary/SCP, backend/key policies
and effective reads before any operation. Planning grants no apply/destroy right.
Do not replace Part4, delete historical IAM versions or grant protected writes.
The known minimal network-retirement delta adds `ec2:DetachInternetGateway` on
the new VPC alongside its IGW and `ec2:DisassociateRouteTable` on the four subnets
alongside their route tables. Before IDs exist, bound account/region, actual
planned Name/Project=demo/Environment=dev tags and approved UTC expiry; reject
existing matching foreign objects. After creation verify finite state-owned IDs
and all companion resources. Offline shape checks and IAM simulation are not
effective native authorization; authorized EC2 DryRun on real IDs can verify the
supported actions without deletion. No default/EKS VPC is a permission probe.
Controller mutation/read grants are needed only for controls actually used and
changed by the selected scope; retain ARN-exact native observations and rollback.

The optional `scripts/retirement_preflight.py` checks exported companion-resource
Allow shapes only. It does not install policies, evaluate effective IAM or create
resources. Close permission gaps through the legitimate separate IAM owner.
The [minimal companion delta](../../scripts/native-dev-retirement-permissions.template.json)
must be bound to the new plan's Name tags and approved start/end before installation;
it deliberately adds no primary-resource, controller or protected-resource grant.
For a live NAT shutdown, separately review `events:DisableRule` on
`arn:aws:events:us-east-1:341936017254:rule/e1-wp4-dev-nat-launch` and
`lambda:PutFunctionConcurrency` only on relevant exact
`arn:aws:lambda:us-east-1:341936017254:function:e1-nat-recovery-nat-dev-{assign-eip,change-rt,disable-sdc}`
functions (expand the three names, never a literal brace expression). Only if
delivery/cleanup can still mutate this generation include their exact
`e1-gateway-deploy-dev` / `e1-cleanup-recovery-cleanup-dev` function ARNs.
Already inhibited, unrelated controls need no mutation or blanket C3 log grant.

History remains in Git, local tag `archive/e16-supervised-20261028` at
`29b30011b3a4dc9e22ffad6e3351494ae8f1e838`, preserved branches/worktrees and
private evidence. The session-04 plan `ab9524fd-0fb6-4e16-9e9f-83423ad6ad56`,
SHA256 `f97ad3acdd75fb9a4418c84f18eaa745e8ae14d498770feb1ebfcb7018eba8f9`,
is **historical only**. Do not apply it through this procedure: obtain a new
authorized native plan from the reviewed new source. No cloud operation occurred
to implement this extraction. The EKS PR #102 cleanup informed native ownership,
reviewed plans, explicit retention and residual checks; none of its resources,
identities or state layouts is used here.
