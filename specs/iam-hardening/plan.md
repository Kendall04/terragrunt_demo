# E1 — IAM / effective authority implementation plan

Status: technical planning checkpoint; no implementation or deployed-security claim.

E1_SPEC_REVISION: `a8607a3ae01e48f254246e53a6918c355e671e7e`.
Authority: [approved immutable specification](spec.md). Platform documentation
checked on 2026-09-22. The specification's nine decisions are requirements.

## 1. Selected architecture and security argument

Use **responsibility-specific OIDC request principals, protected operation
controllers, and an independently administered security root** in the existing
AWS account. GitHub deployment credentials will request a deployment; they will
not possess the AWS credentials that register tasks, pass workload roles or switch
traffic. Apply the same principle to infrastructure operations whose API surface
cannot distinguish legitimate reconciliation from privilege-bearing compute
replacement. Terraform remains the skeleton owner; protected deployment tooling
remains the revision/count/forwarding owner.

This is an architectural inference from the spec and the verified platform
limitations in section 3. The controller is a real authorization boundary only
because its executable, configuration, backing state, IAM role, invocation path
and dependencies are outside the requesting principal's mutation authority.
Running the same validator in the caller's job while leaving AWS mutation grants
on that job is expressly forbidden.

Choose short Lambda request gateways and protected, on-demand CodeBuild controller
projects for long-running Bash/Python/Terragrunt operations. This reuses the Linux
E3 implementation, supports its process supervision and avoids a permanently
running service or Lambda's duration ceiling. Lambda returns an operation ID;
callers poll sanitized status. No API Gateway, new account, service mesh, signing
infrastructure or Step Functions platform is required. Separate projects/roles
where different permissions are needed: build, environment lifecycle, environment
normal delivery and environment emergency recovery. Share controller libraries,
not interchangeable authority. Small qualification/status functions need no
long-running compute. Costs are request/build-duration based; this adds control
code and dependency maintenance but no idle controller compute.

Reject two alternatives:

* IAM-only family restrictions plus a local validator cannot authorize all runtime
  properties, pair role fields, or express readiness.
* Separate untrusted registration and activation roles with a family wildcard
  still allow arbitrary revisions. A registrar-authorizer plus exact revision
  grants could work, but dynamically administering policies adds another protected
  authority and still needs protected readiness/routing mediation. One protected
  delivery controller is simpler here.

**Threat interpretation:** request principals are hostile, including their local
code, parameters and obtainable OIDC tokens. Controller code is security-admin
installed enforcement, never a privileged checkout of that hostile code. A
compromised ordinary requester cannot obtain controller credentials. Security
administration intentionally can change the contract and is outside the spec's
adversarial principal. This distinction must be represented in code, trust and
tests, not just asserted in comments. Approved malicious application source and a
separately compromised runtime remain the spec's explicit limitation.

## 2. Relevant baseline facts

These are repository facts at the spec revision, not observations of live AWS.
The owner reported no infrastructure on 2026-09-18.

| Surface | Current implementation and E1 consequence |
| --- | --- |
| [IAM locals](../../terraform/infra/shared/modules/iam_github/locals.tf) | CI, ordinary infrastructure, release build, deployment, promotion and rollback accept the same environment-shaped subject. Both environments' high-risk trust accepts `dev-infra-approval`. Role names and ARN secrets do not isolate acquisition. |
| [Infrastructure roles](../../terraform/infra/shared/modules/iam_github/github_terragrunt_cd.tf) | Normal/high-risk policies are identical. Workload roles, policy versions, profiles and trusts are mutable; PassRole spans ECS/EC2/Lambda/flow logs; service wildcards include ECS, EC2, ELB, Lambda, Events, KMS and ECR. OIDC, release bucket and secret resource-policy administration remain ordinary. Direct-secret denies do not close composed access. |
| [Delivery split](../../terraform/infra/shared/modules/iam_github/github_delivery_split.tf) | Deploy/promote register definitions, pass both colors' task and execution roles, update services/task sets, modify listener/rule and write scheduling targets. Production reads dev records; build can publish to transitional dev and shared ECR repositories. |
| [Legacy and emergency roles](../../terraform/infra/shared/modules/iam_github/github_ecs_blue_green.tf) | app-CD combines publication, activation and both environments' record writes. Emergency rollback lacks registration but has general service mutation and routing, so absence of registration alone is insufficient. |
| [Workflow orchestration](../../.github/workflows/cd.yml) | Infrastructure-ready gate still selects `AWS_ROLE_APP_CD` when dedicated dev-deploy is missing. High-risk apply still falls back to ordinary TG_CD. These are active implementation fallbacks. |
| [Build workflow](../../.github/workflows/release-build.yml), [dev deploy](../../.github/workflows/deploy-dev.yml), [prod promotion](../../.github/workflows/promote-prod.yml), [manifest rollback](../../.github/workflows/rollback-manifest.yml) | Current build/dev/promote dedicated-role selection has no executable app-CD fallback; manifest rollback explicitly rejects it. Older delivery prose overstates these fallbacks. Prod has a no-dev-record emergency override; this must not become a qualification bypass. |
| [Deployment script](../../scripts/ecs-blue-green-deploy.sh) | Discovers colors, stops inactive service, renders/registers, selects new revision, starts candidate, runs E3, changes listener/rule, schedules cleanup. Renderer inherits role identities from current definitions; target must use protected bindings instead. |
| [Task template](../../demo-api/deploy/task-definition.template.json), [E3 gate](../../scripts/ecs-readiness-gate.sh) | Essential app plus nonessential same-image probe; normal app command inherited, probe command `readiness-probe`. Existing registered-definition checks are narrower than E1 and do not prevent initial execution by a direct API caller. |
| [Workload configuration](../../terraform/infra/apps/fargate/demo.tf), [IAM](../../terraform/infra/apps/fargate/modules/ecs_service/iam.tf), [services](../../terraform/infra/apps/fargate/modules/ecs_service/service.tf) | Separate task/execution roles per color. Task uses environment KMS Encrypt/Decrypt; execution pulls/logs/injects DB secret. Terraform creates zero-count skeletons and ignores revision/count. |
| [Cleanup IAM](../../terraform/infra/apps/fargate/iam_lambda_scale_down.tf), [handler](../../terraform/infra/apps/fargate/lambda/scale_down_old_color.py) | Two-service UpdateService grant has no field-level capacity-only boundary. Handler derives inactive color and requires active desired/running tasks; mutable Lambda code/config would bypass it. |
| [NAT role](../../terraform/infra/global/modules/nat/iam_lambda_nat.tf), [handlers](../../terraform/infra/global/modules/nat/lambda), [events](../../terraform/infra/global/modules/nat/events_nat.tf) | Route tables are scoped, but address mutation is `*`, instance mutation relies on generic `Role=nat`, and event ASG checks can be optional/prefix-based. Protect code and constrain cross-environment edges. |
| [Release rendering](../../scripts/render-release-manifest.sh), [publication](../../scripts/publish-release-manifest-s3.sh), [record writing](../../scripts/write-deployment-record-s3.sh) | Quality defaults are not executed test evidence. Versioned S3 overwrites and digest pullability do not establish qualification. |
| [Architecture](../../terraform/docs/architecture.md), [dev shared root](../../terraform/live/dev/shared/terragrunt.hcl), [prod shared root](../../terraform/live/prod/shared/terragrunt.hcl) | Dev/shared owns OIDC/shared ECR/release bucket consumed by prod. Move security ownership, not the entire topology. Separate environment state buckets currently provide layer-state separation. |

Preserve the completed [E3 contract](../deployment-readiness-promotion/spec.md)
and its authoritative [validation record](../../terraform/docs/validation.md).
No live state or historical examples may substitute for these baseline facts.

## 3. Verified platform semantics and design consequences

The following are verified capabilities, followed by design inferences. They are
not claims that the repository currently uses them. The Executor must retain a
small versioned capability manifest with these sources and the exact actions,
resource types and condition operators used by final policies; unexpected policy
features fail acceptance rather than being guessed by the test evaluator.

| Verified capability | Architectural consequence |
| --- | --- |
| AWS GitHub trust supports `token.actions.githubusercontent.com:aud` and `:sub`; IAM requires a nontrivial sub restriction. [AWS OIDC trust](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html) | Use exact audience and subject equality. Do not invent AWS condition keys for arbitrary JWT claims. |
| GitHub supports customized subject templates including `repo`, `context` and `job_workflow_ref`; repository opt-in/configuration is required. [OIDC reference](https://docs.github.com/en/actions/reference/security/oidc) | Put responsibility-specific reusable workflow identity into sub, rather than using a nonexistent standalone AWS workflow predicate. |
| A reusable job's `job_workflow_ref` identifies the called workflow; caller claims remain caller context. SHA refs can identify an exact reusable workflow. [Reusable-workflow OIDC](https://docs.github.com/en/enterprise-cloud%40latest/actions/how-tos/secure-your-work/security-harden-deployments/oidc-with-reusable-workflows) | Pin privileged reusable jobs by commit; hardcode their environment/responsibility. Merely calling a reusable workflow is not permission to run arbitrary privileged steps. |
| Current ECS authorization lists `RegisterTaskDefinition` with task-definition resources and limited keys including compute compatibility, privileged, CPU/memory and tags. `UpdateService` supports service resources and `ecs:task-definition`; `RunTask` uses task-definition resources. No image/command/role-field-pair/readiness predicate is listed. [ECS authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html) | Scope controller registration to the two exact families; do not repeat the old assertion that registration necessarily requires `*`. Family scope is not content authorization. No field-level general capacity-only permission is assumed. |
| UpdateService resolves an omitted revision to latest before authorization and accepts other execution-affecting service fields. [UpdateService](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_UpdateService.html) | Always use exact returned revision. An ARN condition does not mean “previously validated” or constrain all other fields; no caller UpdateService grant. |
| Task-role and execution-role are separate registration parameters. [RegisterTaskDefinition](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RegisterTaskDefinition.html) | Contract construction, not passability of a role, fixes field placement. |
| PassRole controls a same-account role and target service; `iam:PassedToService` identifies service, not task versus execution field. [PassRole](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html), [IAM condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html) | Controller gets exact role ARNs with `ecs-tasks.amazonaws.com`; no caller PassRole. Do not depend on `iam:AssociatedResourceArn` being supplied by ECS or representing a role field. |
| Boundaries intersect identity permissions; direct grants to sessions have important implicit-deny exceptions. [Boundary evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) | Boundaries are defense in depth, not protection against arbitrary trusted-compute replacement or resource-policy grants. Prohibit session-ARN resource grants; use explicit protected denies where necessary. |
| Setting/removing a boundary is an IAM operation; managed-policy versions also change its content. [PutRolePermissionsBoundary](https://docs.aws.amazon.com/IAM/latest/APIReference/API_PutRolePermissionsBoundary.html), [DeleteRolePermissionsBoundary](https://docs.aws.amazon.com/IAM/latest/APIReference/API_DeleteRolePermissionsBoundary.html) | Only security admin may attach/change/remove ceilings, mutate policy versions, delete/recreate protected roles or alter trusts. |
| ELB ModifyListener/ModifyRule scope to listener/rule resources; available keys do not encode E3 readiness or an exact approved target transition. [ELB authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elbv2.html) | Exact resource scoping is necessary but insufficient; protect all routing mutation and alternative routing paths in controllers. |
| EventBridge PutTargets supports rule resources and `events:TargetArn` (array of ARNs); this does not constrain target input or DeadLetterConfig ARN. [EventBridge authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_events.html) | Use exact rule, `ForAllValues:ArnEquals` plus non-null TargetArn for the cleanup target; controller constructs all target/input fields. Caller cannot schedule arbitrary targets or payloads. |
| StartBuild can override buildspec, image, source, service role, environment and debug settings. [StartBuild](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html) | Never grant requesters StartBuild/RetryBuild/StartBuildBatch. Gateway constructs a fixed request, not a forwarded AWS request. |
| CodeBuild service-role trust can require exact project `aws:SourceArn` and `aws:SourceAccount`. [CodeBuild role](https://docs.aws.amazon.com/codebuild/latest/userguide/setting-up-service-role.html) | No GitHub trust on controller roles; another project cannot assume them. |
| Lambda invocation can be limited to a qualified function ARN. [Lambda permissions](https://docs.aws.amazon.com/lambda/latest/dg/lambda-api-permissions-ref.html) | Give each request role only its endpoint version; payload cannot claim a different responsibility. Lambda execution identity, not a caller-supplied ARN, determines endpoint authority. |
| S3 supports enforced conditional writes using `s3:if-none-match`. [Conditional-write policy](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html) | Use small single-PutObject qualification/receipt objects with `If-None-Match: *`, protected policy, and no nonadmin delete/version-delete/lifecycle expiration. No need for cryptographic attestation. |
| EC2 exposes resource/attribute restrictions for instance attributes and EIP/ENI scope, and route-table resources for route changes. [EC2 authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html) | Restrict recovery to its environment's EIPs, subnets, NAT instances and route tables; protect the tags used in any authorization predicate. Unsupported request-field restrictions stay inside protected recovery code. |

Do not use absence of a condition as proof of a false value. Model missing keys,
Null, set operators and IfExists explicitly. In particular, an UpdateService call
without taskDefinition must not acquire arbitrary capacity/routing authority
through an IfExists shortcut. The design does not rely on that shortcut.

## 4. Principal and trust model

### 4.1 OIDC acquisition

Configure this repository's GitHub subject template to
`include_claim_keys = ["repo", "context", "job_workflow_ref"]`. Intended shape:

```text
repo:Kendall04/terragrunt_demo:environment:e1-dev-deploy:job_workflow_ref:Kendall04/terragrunt_demo/.github/workflows/e1-dev-deploy.yml@<approved-40-character-sha>
```

The SHA is a deployment-time protected configuration value, not a moving branch
or a literal placeholder permitted by trust. Exact subject lists must be generated
and tested with GitHub's encoding (including `%3A` for colons inside values).
`aud` is exactly `sts.amazonaws.com`; provider ARN and repository are exact.
No old environment-only alternative, repository wildcard, session-name predicate,
or role chaining is retained. Branch constraints are external environment rules;
the default environment subject does not also encode branch.

Create one pinned reusable entry workflow per distinct acquisition capability.
It hardcodes its environment and role selection. In particular a single reusable
workflow with caller-controlled `environment`/role is not sufficient. Thin caller
workflows can retain current public workflow names and pass only documented
operation inputs. A hostile job may request any audience but cannot change its
GitHub-issued subject or become a different reusable job. The protected workflow
must not execute caller-supplied actions, shell, buildspec or scripts with higher
credentials. SHA updates are deliberate governance changes; old accepted SHAs
are retired rather than accumulating indefinitely.

| Request role / environment | Authorized endpoint or direct access | Intended source governance |
| --- | --- | --- |
| plan-dev / `e1-plan-dev`; plan-prod / `e1-plan-prod` | Environment-scoped metadata/state reads and plan execution with no apply identity; no secret values | Pinned plan jobs; untrusted PR code gets at most plan reads, never admin state or credentials |
| infra-dev / `e1-infra-dev`; infra-prod / `e1-infra-prod` | Corresponding ordinary lifecycle gateway | Approved develop/main respectively; safe layer selection remains |
| infra-high-risk-dev / `e1-infra-high-risk-dev`; prod equivalent | Corresponding data/apps lifecycle gateway | Explicit operator approval and environment-specific source rules; not admin |
| release / `e1-release` | Protected build/publication gateway | Approved source from develop; environment-neutral artifact responsibility |
| deploy-dev / `e1-dev-deploy` | Dev normal delivery gateway, including dev manifest rollback | Approved develop entry workflow |
| promote-prod / `e1-prod-promote` | Prod normal delivery gateway, including prod manifest rollback | Main entry workflow plus deliberate operator approval |
| emergency-dev / `e1-dev-emergency`; prod equivalent | Environment emergency-color gateway only | Manual operator approval; pinned recovery job |

The high-risk path is retained for operational approval of data/apps lifecycle,
but has no security administration grant. Its endpoint's operation allowlist is
disjoint from ordinary safe-layer reconciliation; it cannot widen code, roles or
runtime contracts. The current prod/dev-approval trust is removed. A new prod
high-risk endpoint supplies the previously unsupported legitimate lifecycle
without reusing dev approval.

Security/bootstrap administration uses **separately held human AWS administrative
authority**, as the existing local bootstrap responsibility already requires.
It has no GitHub OIDC trust and is never assumed by a workflow or controller.
Document the operator's configured admin principal as a bootstrap input; do not
invent an existing IAM Identity Center deployment or require a new organization.
An administrative session installs protected roots and controller bundles.
Secrets are bootstrapped out of band using the existing metadata/value split.
This avoids requiring a new privileged GitHub admin workflow or reviewer team.

### 4.2 Internal principals and interactions

All GitHub request principals explicitly lack IAM mutation, PassRole, role
assumption, control-code/state writes, direct activation and secret-value access.
Each can read only its sanitized operation results. Resource policies must not
grant around these restrictions. The following map is normative:

| Responsibility | AWS authority / owned actions | Explicitly excluded authority and protected controls | Interactions / prerequisite |
| --- | --- | --- | --- |
| Infrastructure planning | Dedicated read identity: required Describe/Get/List, own nonsensitive lifecycle state, protected public metadata outputs; local plans or read-only plan project | No apply/admin acquisition, state writes, secret values, qualification, publication, activation. No blanket ReadOnlyAccess as a substitute for inventory | Reads environment inputs; governed OIDC required for AWS plan; static CI needs no AWS |
| Ordinary infrastructure lifecycle | Request gateway starts protected environment Terraform project using installed bundle and bounded ordinary operations | Cannot supply Terraform/program/source, mutate IAM/security root, privileged compute code or forwarding. No direct state writes | Consumes protected identities/outputs; routine reconciliation remains automatic; OIDC governance required |
| High-risk infrastructure lifecycle | Distinct gateway can reconcile approved data/apps skeleton operations through protected project | Cannot change runtime/security contract, pass arbitrary roles, request unrelated environment or replace controller | Explicit approved data/apps action; no fallback to ordinary or admin |
| Security/bootstrap admin | Installs IAM/trust/boundaries, protected roots, KMS/secret/storage policies, controller versions/config and ownership metadata | Not acquirable by automation; secret values excluded from Terraform state even for admin | Separately authenticated operator; protected source release review |
| Release build/publication | Build request; protected project publishes content and manifest candidates. Protected finalizer alone publishes qualification | No services/traffic, workload PassRole, deployment receipts, runtime secrets, prod-state writes, control-code updates | Qualification is separate from consuming authority; source governance and exact build evidence required |
| Application deployment | Dev gateway; protected dev controller registers authorized revisions, updates exact services, runs E3 and switches exact routing; writes observed dev receipts | No arbitrary definition/input, evidence manufacture by requester, prod mutation, security change or direct APIs | Reads qualification and protected runtime bindings |
| Production promotion | Prod gateway; protected prod controller consumes same immutable image plus protected dev success receipt and prod approval context | No rebuild, dev mutation, default bypass, caller-authored success records or admin | Read-only neutral releases/dev receipt; own prod results; GitHub approval prerequisite |
| Manifest/history rollback | Same environment normal delivery authority, operation `rollback-release` | No weaker eligibility, role, runtime or readiness rules | Protected historical receipt selects identity; controller rechecks current eligibility |
| Emergency color flip | Distinct request gateway and protected recovery project: restore existing color capacity, stability/target checks, switch routing | No registration, new revision selection, PassRole, build/qualification, caller task ARN, ECS Exec or new content | Reads current services and controller-owned registration/deployment receipts; intentional no new-deployment E3 gate |
| Application runtime | ECS task trust; color/environment task role preserves KMS Encrypt/Decrypt and existing DB behavior | No delivery/security/controller/admin APIs, execution-role assumption, qualification writes | Receives approved DB connection injection; deliberately approved application code is a trust assumption |
| ECS execution | ECS service trust; exact approved ECR pull/log/DB secret bootstrap and KMS decrypt | Not passed by requester or usable as task-role; no unrelated environment authority | Protected controller fixes role pairing; retain required managed policy where necessary |
| Cleanup/recovery | Protected environment recovery functions/projects; only own inactive capacity and own schedule cleanup, or own NAT repair | No definition/content introduction, IAM mutation, cross-env address/service writes, mutable target/config by requester | Service-event trust, bounded request interfaces; code/config security-owned; no new NAT algorithm |

## 5. Protected controller contract

### 5.1 Entry and execution

A separate Lambda function/version per capability has immutable environment and
operation allowlist in its admin-installed configuration. IAM invocation scope
is the responsibility check; **do not trust a `principal`, `environment`, `role`,
`approved` or `mode` field to elevate a request**. Same-account identity policy
permits only the intended qualified endpoint, with no public function URL or
broad resource-policy grant. Internal finalizers are not publicly callable.

Gateways parse bounded, duplicate-key-free JSON, reject unknown keys and accept
only identifiers/enums/bounded counts/reasons. They store a sanitized operation
record in a controller-only prefix and start exactly the configured CodeBuild
project with a server-generated operation ID. No AWS request object is forwarded.
Source, controller image, buildspec, role, debug mode, network and logging are
fixed. A controller fetches its operation from its own protected store; shell
arguments are never synthesized from arbitrary request strings.

CodeBuild projects use a versioned, hash-checked admin-published controller
bundle and fixed buildspec, no requester-controlled Git checkout, cache, secondary
source, package plugin or mutable image tag. Protect bundle bucket versions,
image repository administration, aliases, project definitions, logs used as
evidence, status stores, and IAM. No caller can use StartBuild/RetryBuild/batch,
UpdateProject, webhook, Lambda update/config/layer/alias/permission, SSM/debug or
another service to execute under these roles. Controller roles have service-only
trust tied to exact project/account. No workflow receives their credentials.
Disable controller build caches; install reviewed dependencies into the bundle
or pinned controller image. Application build caches cannot feed control code.

Controllers must not be generic AWS proxies. Narrow operations:

* Build: exact approved source commit identity; no digest supplied as proof.
* Normal deployment: qualification ID, bounded replica count, optional history
  selector and diagnostic reason. Resolve resource bindings server-side.
* Emergency: existing opposite color (or explicit blue/green enum), bounded
  replica count, reason; no release/task definition input.
* Lifecycle: installed configuration revision, approved layer enum and operation
  enum (`plan`, `reconcile`, separately permitted teardown); no arbitrary tfvars,
  backend, plan file, Terraform target address, provider or executable upload.
* Status: operation ID within that endpoint's environment; no arbitrary S3 path.

A normal delivery controller need not trust a completion callback from the
requester. It owns authorization, AWS observations and record publication through
completion. A returned operation ID proves request acceptance, not successful
deployment. CodeBuild failure/timeout never becomes a successful result.

### 5.2 Runtime authorization before any startup

The controller constructs a complete definition from an admin-installed schema
and template plus the eligible digest and its environment/color bindings. It
does not accept caller-rendered JSON or copy unknown fields from the existing
service definition. Validate before registration and compare the returned exact
registered revision against that canonical intent **before** any UpdateService
that could run it. Do not set a nonzero desired count while an unverified revision
is selected. All bootstrap definitions must be inert (zero tasks, no workload
roles/secrets) and never eligible for emergency capacity restoration.

| Runtime property | Enforced target contract |
| --- | --- |
| Image identity | Exact account/region/approved repository plus digest from qualification; identical app/probe digest; no tag, arbitrary registry, caller repository or pullability fallback |
| Roles | Protected `(environment, color) -> taskRoleArn, executionRoleArn` mapping, exact ARN equality in distinct fields; no inheritance from mutable service/template input |
| Containers | Exactly named app and probe; app essential true, probe false; no sidecar, init-like helper, FireLens/router, privileged container or extra executable |
| Commands/entrypoint | App command and entryPoint absent; image entrypoint preserved; probe command exactly `["readiness-probe"]`, entryPoint absent. Build qualification verifies packaged capability |
| Environment/secrets | App has only AWS_REGION, APP_ENV, DEPLOYMENT, KMS_KEY_ID from protected bindings, and DB_CONN_STRING from exact environment secret ARN. No caller value, env file, extra secret, repository credential or probe injection. Reject duplicate names and explicit nulls |
| Filesystem/privilege | No volumes, mountPoints, volumesFrom, EFS/EBS, host devices, credential specs, privileged/linux capability override, user/workingDirectory override or arbitrary tmpfs. Preserve image defaults; any future addition requires admin contract revision |
| Network/process | FARGATE, awsvpc, Linux/X86_64, 256/512 initial contract; approved port 8080 and exact logs configuration; no host networking, links, extra hosts, DNS/sysctl/pid/ipc overrides, ECS Exec, service-connect, lattice, runtime hooks or alternate task-set/CodeDeploy activation |
| Probe/lifecycle | Preserve E3 absence of health/command overrides, empty/absent prohibited collections, disabled/absent restart policy and exact same-task evidence. No dependency injection or restart workaround |
| Remaining fields | Enumerate every registration and service request field in a closed schema. Known harmless AWS response defaults are normalized explicitly; unknown request fields rejected and unknown execution-relevant response fields fail before startup. Server-managed ARN/revision/status/timestamps are recognized separately |

Pin an ECS API model snapshot in tests to make newly introduced executable
properties visible. Test every writable field as allowed constant, bounded input,
rejected, or documented AWS-return-only field. Do not rely on a blacklist whose
default permits future fields. Service-level volumes, platform, network, task
overrides and alternate compute APIs belong to the same coverage inventory.

The normal controller role may register only its two families and pass only its
four task/execution role ARNs to ECS tasks. It can update only its two services,
read required task/target evidence and modify only its exact listener/candidate
rule. It has no RunTask, StartTask, CreateTaskSet, UpdateServicePrimaryTaskSet,
ExecuteCommand, CodeDeploy, scheduler/ECS target or arbitrary Lambda/EC2 path.
Its fixed code controls UpdateService fields; IAM family scope is only an outer
bound. The infrastructure and emergency paths cannot become alternate registrars.

### 5.3 Protected E3 activation

Run the existing E3 gate and response-boundary/process-supervision code from the
protected controller bundle. After authorized candidate startup, bind each
observation to operation, registered revision, digest, service deployment and
exact cohort. Preserve all-replica readiness, exact healthy target set, finite
bounds and immediate final revalidation. The switch uses that same retained
candidate, never a requester-supplied target or “ready=true”. No separate public
`activate` endpoint accepts an authorization boolean or raw readiness report.

Only normal controller completion can issue the normal listener mutation. The
emergency controller exposes its deliberately different contract in section 8.
Ordinary infrastructure callers cannot CreateListener/CreateRule, reprioritize
rules, register arbitrary targets, change service load balancers, create API
Gateway integrations around the ALB or scale arbitrary services. Terraform's
ignore_changes is preserved but is not cited as IAM enforcement.

Preserve the accepted observation-to-ModifyListener race exactly. No new lock,
transaction or release-generation scheduler is required by E1. If an authorized
concurrent operation changes observed identity, E3 aborts as today; E2/E4 remain
separate. A partial post-switch failure stays visible as failure/uncertainty,
never an invented success or automatic broader recovery.

## 6. Infrastructure ceiling and ownership

### 6.1 Security root

Introduce a neutral security/bootstrap root/state, separately backed and writable
only by admin. It owns OIDC, all responsibility/workload/recovery/controller IAM,
managed policies/versions/boundaries/trusts/profiles, KMS key/alias policies and
grants, secret metadata/resource policies, shared artifact/ECR administration,
controller code/config/projects and evidence-store policy. Environment-specific
security objects retain environment identities; neutral does not mean dev-owned.

No IAM mutation remains in ordinary lifecycle. It reads explicit protected
outputs (ARNs/IDs only), not writable remote security state. Move resources across
roots without replacement where later authorized migration finds existing state.
State administration and lock-table administration stay protected. The operator
owns any security-root migration and bootstrap sequence. Initial installation
requires no existing OIDC automation; local operator credentials break the
bootstrap cycle.

Protected customer-managed boundaries on requester and controller roles encode
their ceilings, with explicit denies for security/control mutation and unrelated
environment access where applicable. Only admin changes boundary attachments or
versions. No ordinary CreateRole, policy attachment/version, trust, profile,
resource-policy, KMS grant or service-linked-role creation path remains. Service
linked roles needed by ECS/ELB are installed through admin bootstrap; ordinary
automation cannot create alternate delegated service administrators. Boundaries
are not offered as a way to permit arbitrary task/execution/DB compute changes.

### 6.2 Legitimate lifecycle through protected Terraform execution

The request role invokes reconciliation; the protected environment lifecycle
project performs Terraform-owned changes. This is deliberate reallocation of
credentials, not removal of the lifecycle responsibility. It preserves plan/apply,
create/reconcile/authorized teardown of skeleton resources using the installed
configuration. Routine parameter changes inside a published contract do not need
security administration on every apply. Changing privileged executable content,
runtime/network security bindings or the allowed configuration bundle does.

The lifecycle bundle is a reviewed Terraform/Terragrunt configuration, including
modules, provider locks, user data and helpers. No caller-controlled Terraform is
executed with lifecycle credentials, including provisioners, external data sources,
plugins, `run_cmd`, hooks or replacement backend/provider configuration. A valid
JSON plan is not sufficient if generating it already executes hostile code.
Requests may choose only an installed bundle revision and validated bounded
parameters. Protected configuration publication accepts only reviewed immutable
repository revisions; a request SHA alone is not approval.

An installed revision is usable only while listed in the admin-controlled active
contract set. Retaining an old bundle for diagnostics does not authorize a caller
to select it after its ceiling or validation rules have been superseded. The
same rule applies to gateway versions and runtime schemas. An implementation
must not expose an old-version invocation path around a new control.

The environment lifecycle role has API permissions for its environment skeletons
and own lifecycle state only; no security-root/evidence/code-bucket writes, IAM
mutation or controller administration. Split protected compute/skeleton execution
from ordinary safe resources where needed for policy size, without creating
additional public responsibilities. The permission inventory must account for
both create-time and existing-resource actions; wildcard read requirements are
separate from mutation, and tag-scoped mutation cannot allow the caller to change
the authorizing tags. The controller validates environment membership against
protected IDs before operating on generated-ID resources. Do not expose its role
to a job that can bypass this check.

| Existing root/resources | Target owner and allowed lifecycle behavior |
| --- | --- |
| shared IAM/KMS/ECR/artifact/OIDC; secrets metadata | Security root. Ordinary apply consumes outputs. Shared artifact lifecycle/deletion is not dev lifecycle |
| global VPC/subnets/SG/NAT ASGs/ALB/TGs/listener/rule; edge API Gateway | Environment Terraform lifecycle through protected project. Configuration cannot introduce alternate serving paths or change DB/app access boundaries outside installed contract. NAT default route ownership stays recovery-owned |
| data SQL EC2/profile/user data/storage | IAM/profile/security metadata moved to security root; approved EC2 skeleton lifecycle runs only through high-risk protected project with fixed user data, AMI/profile and environment bindings. No ordinary SSM/EC2 Instance Connect, volume attach/snapshot export, user-data/launch-template injection or profile replacement bypass |
| platform ECS cluster | Environment lifecycle project; no arbitrary capacity provider/EC2-backed controller path |
| apps skeleton services/logs/alarms | High-risk Terraform project retains skeleton ownership. Initial definition inert; never starts bootstrap image with DB/KMS roles. Existing task revision/count ignored. Changes cannot replace selected runtime or remap service/TG; replacement requires bounded teardown/recreate at zero, then normal qualified deployment |
| app roles/policies and cleanup/NAT code/config/trust | Protected security control installation. Routine events invoke only fixed repair operations; no lifecycle upload of caller Lambda ZIPs |
| Runtime task revisions/counts and ALB forwarding | Protected deployment/recovery controllers, outside Terraform reconciliation |

For existing nonzero services, ordinary reconciliation cannot reapply a bootstrap
revision, alter count, turn on Exec or change execution-affecting service bindings.
Listener replacement is a skeleton operation only after explicit bounded
quiescence/teardown; it cannot create an active forwarding path to an unqualified
candidate. Legitimate full teardown is separately approved high-risk lifecycle,
not a license for state/policy deletion. Do not claim deployment availability
during intentional teardown or silently expand E1 into recovery orchestration.

This closes both halves of the original escalation: ordinary credentials cannot
broaden reachable workload IAM, and cannot change the program running under a
fixed stronger role. Protecting only one half would be inadequate.

## 7. Qualification and environment evidence

### 7.1 Minimal qualification contract

Keep current release manifests/selectors as interfaces, but treat old quality
defaults and mutable candidate pointers as discovery, never authorization.
Add a small protected qualification record keyed by immutable release identity:
account/region/repository, image digest, exact source commit, build operation/run,
schema/runtime-contract version and actual required check results. Record the
manifest's exact S3 version/checksum so a later manifest overwrite cannot change
the selected identity. No cryptographic attestation is required.

The **release build/publication responsibility**, implemented by the protected
build project and finalizer, establishes qualification outside deploy/promote.
It fetches the approved exact repository source; executes the existing dotnet
restore/build/test contract for that source, builds/publishes the image, resolves
its registry digest and executes the packaged readiness-probe capability check
against that exact image. Failed/skipped/missing checks never receive qualification.
Do not import the renderer's `passed` defaults or accept the requester's test report.

The build environment has only publication/staging permissions, no qualification
or deployment-record writes and no application/DB secret access. Application
tests/build code run without controller/admin credentials. The fixed supervisor
records each required process result and source/image binding. A protected
finalizer reads the known project's AWS build result plus its bounded result
record and verifies required phases, source, digest and check identities before
writing qualification. A notification event is only a wakeup: independently read
the build by ID and require that it belongs to a gateway-created operation and
exact protected project. The requester cannot start that project directly, change
its buildspec, submit fake completion or access the finalizer's write identity.

Build supervision and source governance are part of this bounded assurance.
Do not claim a general proof against intentionally approved malicious source
faking its own tests. Avoid running arbitrary release payloads with finalizer
credentials; its job is fixed validation/publication, not application execution.
This is the minimum exact-source/result binding missing in the baseline, not a
new universal provenance system.

### 7.2 Storage and consumption

Use neutral security-owned S3 prefixes/buckets with explicit writer inventories:

| Data | Writer | Readers / authority meaning |
| --- | --- | --- |
| Existing candidate manifests/indexes | Protected build project | Requesters/controllers may discover; never sufficient evidence |
| `qualifications/demo-api/<release-id>.json` | Protected finalizer only; conditional create, no delete or rewrite | Dev/prod controllers read exact object identity; requester read optional |
| Eligibility/revocation registry | Security admin only, versioned | Controllers re-read current eligibility before new execution; missing/ambiguous state fails |
| Protected dev success receipts | Dev controller only after its own completed authorized deployment checks | Prod controller read-only; dev requester cannot write/overwrite/delete |
| Protected prod success receipts | Prod controller only | Prod history/rollback read; no dev write |
| Existing current/history pointers | Corresponding controller only | Convenience selection; pointer cannot override qualification or runtime eligibility |
| Controller operation/input/result records and bundles | Exact gateway/controller/admin writers per prefix | No caller or application build overwrite; no cross-env write |

Enforce append-only qualification and success receipts with conditional single
PutObject and protected bucket policy; deny nonadmin DeleteObject,
DeleteObjectVersion, bucket policy/lifecycle/versioning/ACL/replication changes.
Versioning alone is not immutability. Exclude these prefixes from expiration.
Admin may revoke eligibility without rewriting history. Sanitized records contain
secret ARNs, never values; control logs are not readable workload-secret stores.

Dev consumes qualification, current eligibility, current runtime compatibility
and an extant exact ECR digest. Prod additionally requires an exact matching
protected dev success receipt (including source/digest/qualification identity)
and its separately approved prod request. Publication alone cannot authorize
prod, and the dev caller cannot fabricate the prerequisite. Receipt data is
observational, not a caller assertion of deployment. If optional smoke verification
is configured as required by the installed release contract, its failure prevents
success receipt publication; do not invent successful verification when skipped.

Remove the current caller-controlled `allow_without_dev_deploy` bypass. If the
operator needs to change qualification policy, that is explicit security admin,
not the emergency-color exception. This follows the approved qualified-release
contract; it does not remove the preserved emergency flip behavior.

Historical manifest rollback resolves a protected historical receipt to release
identity, then checks current eligibility/revocation, retained digest, manifest
binding and current runtime schema/probe support. It reuses normal registration
and E3. Expired ECR images fail closed; E1 need not redesign retention to guarantee
an unlimited rollback horizon. Never rebuild a missing historical digest.

### 7.3 Same-account isolation

Move OIDC, shared ECR and release/evidence control out of dev/shared authority.
The neutral build publisher may add candidates, not delete existing images,
rewrite immutable tags, change ECR policy/lifecycle or administer evidence.
Only admin manages these destructive controls. Dev/prod read the same immutable
qualified image; shared publication is an explicit responsibility, not dev infra.

Use distinct dev/prod controller roles, endpoints, configuration, lifecycle state
and object prefixes; no payload chooses the environment. Dev has no write to prod
roles, boundaries, keys, secrets, services, routing, controller config/state or
receipts. Protected dev success receipts are cross-environment **read** inputs;
the dev requester does not control their writer. Do not export complete sensitive
remote state to callers when a protected public output record suffices.

## 8. Emergency and bounded recovery

Emergency flip is a separate endpoint/project with no registration, release
publication or PassRole. It discovers the two mapped services and exact current
definitions itself, verifies that the selected color contains an already deployed
authorized definition, restores only its capacity within bounds, waits for bounded
service stability and healthy targets, then performs the existing color swap and
bounded cleanup scheduling. It never accepts an image/revision/roles/command.
Validate the retained revision and target mapping again before switching.

“Already deployed” is evidenced by protected controller records plus current
service identity, not merely any family-compatible task definition in the
account. A failed new candidate must not acquire emergency eligibility just by
having been registered. Existing prior color identity remains available even if
scaled to zero. Establish registration/activation records during normal delivery;
do not trust mutable current.json alone. During any migration of real services,
admin explicitly enrolls verified existing color identities before enabling this
endpoint; never auto-enroll unknown definitions.

No new-release qualification or new E3 run is required for the emergency flip;
it restores existing content and retains the accepted stability/healthy-target
checks. Ordinary history rollback cannot select this endpoint to introduce content.
Recovery IAM alone cannot express all UpdateService fields, so fixed protected
code enforces capacity-only requests and callers get no UpdateService permission.
The project's role cannot create/choose new task definitions through its interface.

Cleanup retains the existing schedule and inactive-color decision; make its code,
environment bindings and event permission protected. Remove direct cleanup-role
UpdateService authority if the role is exposed to a mutable dispatcher: dispatcher
may only invoke the protected environment capacity-cleanup function. That function
has no revision input, derives the two services/listener from protected config,
validates unambiguous mapping, requires the existing active desired/running safety
condition and submits only `desiredCount=0` for the inactive service. It can
delete/remove targets only from its exact cleanup rule. No generation-bound
scheduler or stronger health policy is added in E1.

For NAT keep the three existing repair operations. Protect functions/config,
event rules/permissions, ASG launch template/user data/profile and authorization
tags from ordinary mutation. Require verified exact ASG membership, environment
VPC/subnet and expected EIP/route table rather than an optional event prefix.
Scope address association to own EIPs and own subnet ENIs; remove unused
DisassociateAddress (current handler uses reassociation), scope route writes to
own route tables, restrict ModifyInstanceAttribute to sourceDestCheck on protected
environment NAT instances. Do not keep generic Role=nat as the sole environment
boundary. Use per-resource statements for EC2 multi-resource evaluation; tags
used on replaceable instances are installed by protected launch configuration and
cannot be edited by the recovery identity. IAM narrows resources; protected code
fixes destination and operation fields it cannot express. EventBridge invocation
permission is exact source rule/account; no caller PutEvents/PutTargets path into
broader functions. Positive tests retain per-AZ ASG replacement repair. No new
NAT health, DLQ, cross-AZ failover or networking architecture is included.

## 9. Legacy and failure contracts

Retire app-CD completely. Executable dependency discovery at this revision found
only the infra-ready fallback in cd.yml, plus Terraform role/policy/trust/outputs
and locals. Build/dev/promote already require dedicated roles; manifest rollback
explicitly refuses legacy. Remove the remaining fallback, both module/root output
exports, role/policy/attachment and subject/local grants. Update current operational
documentation during implementation to remove stale fallback instructions; this
planning checkpoint does not edit it. Search tracked scripts/actions/workflows,
bootstrap output consumers and test fixtures again during migration; a new caller
must migrate to an appropriate endpoint, never justify keeping combined authority.

Infra-ready discovery moves to dedicated read-only plan/preflight authority with
the exact Describe/GetRole/GetFunction metadata needed by
`scripts/check-deploy-resources.sh`; it receives no deploy privilege. Remove the
high-risk TG_CD fallback separately. Local deploy wrappers become callers of the
same bounded endpoints or explicit admin bootstrap operations; they must not
silently recreate the old direct deploy role.

| Failure | Required result |
| --- | --- |
| Missing dedicated role/endpoint/config | Stop before token acquisition or operation submission; name missing capability, not a substitute ARN |
| Missing/invalid OIDC, wrong audience/subject/environment/workflow SHA | STS denies; wrapper reports identity mismatch without logging JWT/credentials; no fallback |
| Missing qualification, skipped/failed check, mismatched source/digest, missing image | Reject before registration/start; discovery pointers and old manifests cannot authorize |
| Unknown runtime property, contract mismatch, ambiguous role pairing | Reject before any candidate startup; include field/category and expected contract version, no secret values |
| Missing historical eligibility or unknown existing emergency color | Reject affected rollback; no rebuild or arbitrary-definition enrollment |
| app-CD unavailable | No special handling: no code path references it as an alternative |
| Gateway/controller/finalizer unavailable, timeout, malformed AWS evidence | Fail affected operation; no direct API instructions, broader credentials, success receipt or late promotion |
| Post-start or post-switch failure | Report exact last known phase and uncertainty; preserve existing E3/E4 boundary, no speculative compensating writes |

Sanitize diagnostics to operation ID, stage, control ID, resource identity and
reason code. Do not print payloads, tokens, build environment dumps, connection
strings, raw state or secret fetch results. Negative fixtures use canary secret
strings and assert they never appear in results/logs.

## 10. Implementation work packages and migration order

These specify architecture and gates, not a line-by-line recipe. New code paths
below are proposed implementation surfaces; they do not exist at this checkpoint.

1. **Authority inventory and offline contracts.** Add a machine-readable principal,
   action/resource necessity and ownership inventory under `ci/authority/`, plus
   controller schemas/runtime contract and external-governance expectation file.
   Build the offline extraction/evaluator/tests in `scripts/tests/authority/`.
   Capture baseline negative failures so the new suite does not merely test a
   manually authored target manifest. No AWS access is required.
2. **Protected root and control bundles.** Add a neutral security Terraform root,
   separate backend configuration, protected output records and controller modules.
   Extract IAM/security/storage ownership from shared/data/apps/global modules.
   Create request identities initially with no operational grants; install gateway
   and controller artifacts through admin only. Enumerate control dependencies
   and enforce no ordinary writes to them. Bootstrap supports the empty account
   case first. If actual state later exists, admin inventories it before any
   move/import; do not guess that it exists now.
3. **Protect qualification and build.** Add build supervision/finalizer and
   qualification schema beside existing release schemas/helpers. Bind exact
   source, tests, image and probe checks; remove optimistic authorization defaults.
   Establish neutral ECR/evidence policies. Do not qualify old artifacts merely
   because old metadata says passed. Prove build positive/negative fixtures.
4. **Protect normal delivery and recovery.** Package renderer/E3/response-boundary
   tooling into installed controller bundle; add closed runtime authorization
   before startup, protected records and separate emergency operation. Constrain
   cleanup/NAT edges and all alternate invocation paths. Prove complete positive
   deploy/promote/rollback/repair traces, plus failures before startup/switch.
5. **Protected lifecycle reconciliation.** Split roots/state and implement fixed
   lifecycle bundle/operation inputs. Preserve skeleton ignore_changes and required
   secret bootstrap. Prove create/reconcile/approved teardown for all original
   layers, ordinary versus high-risk behavior, and no runtime reset on reconcile.
   Admin installs new security controls; ordinary lifecycle cannot install itself.
6. **Workflow cutover.** Replace direct AWS mutation in release-build, deploy-dev,
   promote-prod, rollback-manifest, cd-rollback, cd-terragrunt and orchestration
   with pinned responsibility entry jobs and endpoint requests. Move infra-ready
   to read-only authority. Keep exact-source plan diagnostics and current public
   outcomes. Configure subject template and external environment protections
   through separately authorized operator work, not this planning task.
7. **Remove overlap and accept.** Revoke old trusts, direct grants and residual
   sessions before operational hardening is declared; remove app-CD, default-sub
   trust, TG_CD fallback, no-dev-record promotion bypass, cross-env writes and
   caller control-code/state writes. Old controller versions with weaker contracts
   must no longer be invocable. Run full composed-path/mutation/positive evidence
   against the final model and independently review all 16 ACs. Update authoritative
   architecture/security/delivery/bootstrap/validation docs with implemented facts.

A staged code rollout may temporarily support both protocols for diagnostics;
that state is **transitional and not E1 secure**. Do not attach the old broad
policy to new request roles “until tested.” For an empty account, install only
the final target—there is no reason to deploy old bypasses first. For a later
live migration, separately authorized maintenance/cutover handles active sessions,
state moves and enrolled color identities. Offline evidence can prove workflows
and state-move intent, not live session revocation or successful migration.

The Executor must not expand this into E2 concurrency, E4 compensation, unbounded
artifact retention/provenance, full NAT redesign, general managed-policy
minimization, SQL/TLS/durability or multiple accounts. Protected compute and
neutral shared-control ownership are necessary E1 changes because those resources
otherwise let ordinary/dev authority bypass security or prod isolation.

## 11. Deterministic evidence architecture

### 11.1 Evaluate the resulting repository, not a parallel wish list

A small repository-specific authority graph/policy-contract harness is warranted.
Inputs are actual final Terraform policy/trust/controller configuration and
workflow/action/script callers. Prefer one declarative policy/contract source
consumed by Terraform and tests; otherwise parse/evaluate the supported HCL subset
with fixed synthetic account/region/env inputs. Reject unhandled expressions,
external files and unresolved security values. Compare generated policy objects
to the extractor output so a stale golden JSON cannot hide a Terraform change.
No provider initialization, Terragrunt execution, AWS SDK credential chain or
live IAM simulator is needed.

Extract every root/module instance for dev/prod/neutral, inline/attached/boundary
policy, trust and resource policy; track known AWS-managed policies using reviewed
pinned local snapshots for model evidence, explicitly noting live managed-policy
drift is external. Detect new policy/role/root definitions outside the inventory
as failures. Scan all workflow credential acquisitions and privileged launch paths,
not only the named workflows. Extract concrete request endpoint ARNs and allowed
payloads and trace calls into the installed controller bundle. Any service-wide
mutation wildcard or unsupported action/condition requires modeled semantics and
necessity, not automatic approval.

Evaluator semantics cover explicit-deny precedence, union of identity grants,
boundary intersection, principal/trust matching, resource policies and session
grant hazards, resource ARN wildcards, condition presence/type, String/Arn
equality/like, Bool/Null, set operators, supported IfExists and PassRole/service
composition. Service action metadata defines required resource checks and supported
condition keys. Unsupported constructs return UNKNOWN, which fails the applicable
AC; they never return DENY and masquerade as security. Test the evaluator itself
with fixed truth tables including absent keys and direct session resource grants.

Graph nodes: token claims, roles/sessions, policies/versions, resource controls,
states/artifacts, compute executables/configuration, role-field bindings, qualified
images, service revisions, routes and protected operations. Edges represent
acquire/pass/mutate/execute/invoke/read/write and controller state transitions.
Reachability reaches a fixed point including mutation of a policy, default
version, trust, project/image/bundle, resource policy or launch configuration.
Do not assume an arbitrary invocation runs attacker code: use the actual protected
input contract. Conversely, any writable executable or configuration dependency
makes its attached role reachable with attacker-controlled code.

### 11.2 Behavioral composition and required attack suite

Use fake service transports around production controller code, not test-only
rewrites. Each fixture evaluates IAM first, then invokes the real allowed entry
and records attempted AWS calls. Assert ordering: no startup until qualification
and registered-definition authorization; no listener mutation until E3 or the
separate emergency checks. Replay direct API calls as each requester, including
APIs absent from scripts. Negative tests must identify the exact policy statement,
trust mismatch or controller validation branch that stopped the chain.

| Starting principal/token → attempted chain | Exact stopping control to demonstrate | Legitimate counterpart |
| --- | --- | --- |
| infra → policy version/trust/profile/boundary mutation → mutable Lambda/EC2/ECS → secret/KMS | No IAM mutation/PassRole/direct compute grants; controller/config/state dependency writes denied; installed lifecycle input contract | Reconcile own skeletons with fixed protected identities |
| CI/build/deploy → new audience/session name/role ARN → infra/admin | Exact customized sub allowlist; no admin OIDC trust or AssumeRole path | Each intended token acquires only its own role |
| dev or dev high-risk → prod trust/state/shared bucket/ECR policy/NAT mutation | Distinct prod subject/endpoints and resource policy/role scope; neutral controls admin-owned | Dev lifecycle and neutral publication; prod read of protected qualification/dev receipt |
| deploy → RegisterTaskDefinition/RunTask/CreateService/task-set/CodeDeploy/EventBridge → arbitrary image execution | Requester API denies and no PassRole; gateway closed payload; controller exact qualification/template | New eligible revision starts before normal E3 evaluation |
| deploy → swap execution/task roles or colors → startup | Exact protected tuple before registration and returned-definition comparison before startup | Both legitimate color pairs in both environments |
| consumer → overwrite manifest/qualification/dev receipt → select pullable digest | Protected writer and conditional-write policies; controller rechecks identity/eligibility | Qualified dev deployment and prod promotion of same digest |
| deploy → direct UpdateService/ModifyListener/ModifyRule/RegisterTargets/new route → gate bypass | No direct mutation; installed controller E3 path cannot accept external ready evidence | Exact ready cohort switches normal traffic |
| emergency → task ARN/definition update/new release → flip | Endpoint rejects revision/content fields; protected recovery project has no registrar; existing-color identity bound | Scale zero-count previous color, bounded stability/targets, flip without E3 |
| cleanup/NAT caller → alternate target/config/event → stronger service/prod | Protected code/config, scoped event target, no arbitrary payload forwarding and environment resource restrictions | Inactive count zero; same-AZ NAT replacement |
| any ordinary principal → control-bucket state poisoning / CodeBuild override / Lambda alias / managed-policy default version | Exact protected dependency write denies and service-only internal trusts | Admin installs a new reviewed contract version |

Variants include deletion/recreation with same name, role-session resource grants,
tag edits, unknown future ECS fields, environment files/log-secret options,
malformed JSON/duplicate keys, qualified-record replay with altered image,
rollback after revocation/expiration, request path traversal, source/bundle cache
poisoning, forced service deployment, scheduler targets, SSM/Exec, new ALB rules,
service load-balancer remapping and prod high-risk using dev approval. No
unsupported resource tag predicate may be counted as the stopping control.

### 11.3 Mutation testing and anti-deny-all evidence

In disposable repository copies deliberately reintroduce: an old OIDC subject;
prod dev-approval trust; ordinary policy-version/PassRole/compute mutation;
caller StartBuild with override; direct ECS/ALB grants; qualification/receipt write;
boundary removal; recovery wildcard; runtime role swap/unknown field acceptance;
E3 bypass; app-CD fallback; controller bucket write. Every mutation must cause
the relevant acceptance case to fail, with the prohibited chain trace. Test
actual mutated policy/controller sources, not just the expected-answer file.

Positive fixtures exercise read plans, ordinary safe apply, high-risk data/apps
apply, admin bootstrap/update, exact-source build/check/publication, both color
directions for dev/prod, eligible historical rollback, emergency restore,
cleanup/NAT repair, DB injection plus app KMS and execution pull/log behavior.
Delete an essential grant or force every operation to fail and require the suite
to fail. Retain E3's hermetic fixtures and app tests; their passing alone does not
prove IAM or AWS runtime behavior.

The acceptance runner clears AWS/profile/web-identity/container credential and
proxy variables, disables metadata discovery, uses fake transports and an
outbound-network-disabled test environment, and refuses any real AWS executable.
Use checked-in synthetic metadata and preinstalled/pinned tooling; no dependency
download in acceptance. Record evaluated Git SHA/tree, spec revision, hashes of
extracted policies/contracts and capability data, test IDs actually executed,
positive/negative/mutation counts, failures and external assumptions. Dirty-tree
evidence must say so and identify the exact tree. Never label a skipped suite
passed. Report repository-model acceptance separately from external/live status.

## 12. AC1–AC16 acceptance mapping

All rows are mandatory implementation evidence, not claims of passing today.
“Governance” means the explicit prerequisites in section 13, not an assumed
existing setting. Suite identifiers below define required evidence families.

| AC | Controls and implementation surfaces | Deterministic evidence | Positive control | Residual assumption |
| --- | --- | --- | --- | --- |
| AC1 | Security root; no ordinary IAM; protected lifecycle projects/bundles/state; exact role passing | A1 fixed-point policy/trust/compute graph including versions, profiles, existing compute and dependency writes; deliberate grant mutations | Own safe/high-risk create/reconcile with protected identities | Admin and installed control code not adversarial |
| AC2 | Exact aud/custom sub, pinned dedicated reusable jobs, no role chaining/admin OIDC | A2 full token-by-role acquisition matrix including missing/custom/default claims and hostile role selection | Every intended OIDC acquisition plus human admin bootstrap | GitHub subject configuration/governance holds |
| AC3 | Separate env endpoints/state/roles and neutral shared security/evidence ownership | A3 cross-env action matrix; prod dev-approval, shared ECR/bucket and NAT mutations | Dev operation; independent prod operation; allowed cross-env receipt read | No out-of-band grants/account identities |
| AC4 | No requester activation APIs; protected normal controller; pre-start canonical definition authorization | A4 direct ECS/task-set/scheduler/compute attempts and broker trace; zero startup for invalid payload | Eligible new revision registration/start | AWS honors IAM; protected controller code installed |
| AC5 | Protected exact color/env role tuple, return-definition comparison; no caller PassRole | A5 role-field permutations, same-name/wrong-account roles, service-selected role inheritance | All four intended task/execution pairs | ECS task/execution credential semantics |
| AC6 | Protected build/finalizer qualification, append-only records, current eligibility | A6 missing/failed/skipped/rewritten evidence; source/digest mismatch; consumer write tests | Exact-source checks and image create qualification; eligible deploy/promote | Approved source/test semantics, not universal provenance |
| AC7 | Admin-only OIDC/IAM/KMS/secret/storage/control policies, versions, boundaries and state | A7 mutation graph for controls and every control dependency; deny boundary delete/replace | Admin installs/updates security root; lifecycle consumes public metadata | Separately held admin stays separate |
| AC8 | Controller-only service/routing/capacity; protected E3; recovery endpoint isolation | A8 direct/mediated mutation traces; alternate routing targets and service fields; E3 failure has zero listener writes | Ready exact cohort scale/switch; bounded recovery scale | Accepted final-observation race; E2 excluded |
| AC9 | Normal historical redeploy versus existing-color emergency contract | A9 revoked/expired history, arbitrary revision emergency inputs, unknown/bootstrap candidate rejection | Still-eligible historical E3 deployment; zero-count prior color restoration without E3 | Retained image availability; no schema rollback promise |
| AC10 | app-CD retirement and all fallback removals; read-only infra preflight | A10 caller inventory plus deletion/missing-role fixtures and mutation restoring fallback | Dedicated preflight/build/deploy/recovery entry paths | External unused role/session removal separately verified later |
| AC11 | Responsibility map and action-to-caller necessity inventory | A11 complete positive trace for every section 4 responsibility, admin included; essential-grant-removal mutation | Full create/build/dev/prod/history/emergency/runtime/recovery fixtures | Offline behavior is not deployed operation proof |
| AC12 | Closed schemas, bounded controllers, identity checks, redacted failure codes | A12 malformed/missing/contradictory input and AWS responses; outage/timeouts; secret-canary logging tests | Valid request yields truthful phase/result | AWS/API availability affects liveness, never authorizes fallback |
| AC13 | Actual-source extraction, evaluator, authority graph and controlled mutations | A13 coverage of all principals/policies/callers; mutation set in 11.3; UNKNOWN is failure | Positive matrix and deny-all mutation fail correctly | Limited evaluator semantics explicitly versioned/tested |
| AC14 | Closed runtime/service field inventory, exact template, API model snapshot | A14 property-by-property mutation of registration and service injection/override fields; response-default fixtures | Exact current template plus documented safe defaults accepted | New API fields require reviewed schema update |
| AC15 | Preserve E3 bundle and liveness, DB/KMS/secret separation, skeleton/runtime ownership | A15 existing readiness/app regression suites; no secret-valued Terraform inputs/resources; synthetic plan/reconcile ownership diff | App DB bootstrap/injection/KMS and ECS pull/log contract traces; no runtime reset on apply | Live DB/KMS operation and migrations not proven offline |
| AC16 | Hermetic authority runner, fake AWS, exact revision evidence manifest | A16 clean-environment/no-network run and attempted real-AWS guard test; deterministic replay | Entire positive/negative/mutation suite runs without AWS | Installed local tools supplied; external settings remain unverified |

## 13. External prerequisites and limits of acceptance

No GitHub/AWS setting is inspected or changed by this planning task. Required
configuration expectations must be checked into the implementation and tested
offline; external conformance must remain explicitly unverified until separately
authorized evidence is obtained.

| External prerequisite | Why required | Repository proof versus external proof |
| --- | --- | --- |
| Repository OIDC customization enabled with exact template | Makes reusable workflow/context part of the AWS-recognized subject | Test generated subjects and trusts; an offline expected-config fixture cannot prove GitHub was configured |
| Protected source refs and pinned privileged reusable workflow SHAs | Prevent replacement of acquisition logic or approved source/control bundles | Parse all uses/checkouts and expected rules; actual branch/ruleset/bypass permissions need external evidence |
| Exact branch restrictions for every responsibility environment | Prevent dev branch/caller from entering prod/high-risk jobs despite workflow reuse | Test environment names/expected allowed refs; verify actual GitHub branch/tag rules later |
| Deliberate operator approval for prod/high-risk/emergency, and admin access separate from job tokens | Distinguishes authorized public responsibilities; stops a dev job self-approving prod | Expected reviewer identities, allowed bypasses and API expectations can be represented offline; a flag such as GATE_CONFIGURED is not proof |
| No job-held repository administration token, environment-approval credential or unrestricted self-hosted runner shared with stronger jobs | Otherwise hostile job code could change governance or steal another responsibility's credentials | Inspect permissions/secrets contracts and require isolated ephemeral runners; external secret contents/runner configuration are unverified |
| Required checks protect contract/controller changes and source release eligibility; only operator may authorize security bundle/trust revisions | Keeps security administration distinct from normal code execution | Workflow/check identity and changed-file coverage can be tested; server enforcement and exceptions remain external |
| Separately authenticated AWS operator bootstrap/admin and no out-of-band grants | Allows installation/recovery without a circular ordinary-admin role | Trust/policy model proves no repository path; actual account identities/attachments/sessions cannot be proven offline |

GitHub environment approval/branch controls are documented capabilities, with
plan/repository-visibility availability constraints. A single operator may approve
a separately authorized operation; this plan does not require a second engineer
or enable prevent-self-review in a way that bricks operation. Automation tokens
must not approve themselves. If required GitHub features are unavailable, keep
that request role disabled and use the separately authenticated operator through
the **same bounded endpoint**, with explicit narrowly scoped identity policy;
never relax AWS trust to an environment-only shared subject. This is an operational
alternative, not an automatic credential fallback. [GitHub environment controls](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
and [environment API](https://docs.github.com/en/rest/deployments/environments).

Repository acceptance proves the model conditional on these prerequisites. It
does not establish absence of manually attached policies, compromised provider
infrastructure, stolen admin credentials, live drift, image retention or actual
Fargate/ALB behavior. A material unexplained model edge is a failing AC, not an
external assumption. No policy simulator, live deployment or AWS experiment is
needed or authorized for deterministic acceptance.

## 14. Planning review and forbidden shortcuts

The target was challenged against all nine original bypass classes and variants:
policy/trust/compute composition (sections 5–6), token interchange (4), dev/prod
shared/recovery mutation (7–8), arbitrary revision and role substitution (5),
consumer-fabricated qualification (7), routing/readiness bypass (5), legacy
fallback (9), and self-mutable controls (5–6). Each has a stopping control and
positive counterpart in sections 11–12. No approved security decision is reopened.

Implementation must not:

* Keep broad AWS credentials in a workflow because its checked-in script is safe.
* Pass arbitrary Terraform, task JSON, image URI, role ARN, readiness report,
  CodeBuild override or security config through a “broker”.
* Treat family names, tags, masked ARNs, default quality fields, environment labels,
  Terraform ignore_changes or boundary names as enforcement by themselves.
* Leave mutable code/state/bucket/project/alias/policy dependencies reachable by
  the principal the control constrains, or grant resource policies to sessions
  around the intended boundary.
* Make the finalizer trust an event/result authored by the consuming requester,
  qualify a missing check, or accept history/pullability as current eligibility.
* Treat emergency flip as a new-content deployment, or require it to rerun E3.
* Count transition overlap as secure, unknown policy semantics as denial, skipped
  tests as passed, or a complete deny-all implementation as success.

Planning validation is documentation-only: reread immutable spec, confirm all
16 mapping rows and nine bypass classes, review source references/local links,
verify only this plan changed, and run `git diff --check`. No implementation tests,
dependency installs, Terraform initialization, cloud access or settings mutation
are appropriate for this checkpoint. The commit SHA is reported as
E1_PLANNING_REVISION outside this file to avoid a self-referential commit hash.
