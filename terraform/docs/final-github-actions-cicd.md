# Real GitHub CI/CD — pre-publication checkpoint

Date: 2026-10-14 local / 2026-10-15 UTC. This is preparation evidence, not a
successful GitHub Actions, WP3 qualification or WP4 deployment claim.

## Verified Git/GitHub boundary

The owner-authorized local main fast-forward preserved history and advanced
`c80257bac43bb1d0cf04016872ec481d0092d733` to the verified second-UP commit
`2a442f667fdb34c3110487ada58ad5f56501b46c`. Work continues exclusively on
`codex/final-github-actions-cicd`. No new clone/worktree, reset, rebase, force push
or remote publication was performed. No subsequent feature changes enter main.

Remote: <https://github.com/Kendall04/terragrunt_demo>, **PUBLIC**, default branch
`main`. Observed remote main is `305e3a7e4e486836baa3889746affa97b9f22733`;
local second-UP main is 96 commits ahead, with no remote-main-only commits.
Observed remote develop is `399cc900ec3068284ca982bde163427c80e70de3` and is
**not** an ancestor of this branch. Do not overwrite it or presume a fast-forward.
Its branch-protection API returned Branch not protected. Actions are enabled.
Only the name of the repository's Infracost secret was observed; no secret value
was read. GitHub currently uses its default OIDC subject, without customization.

A bounded scan examined all 96 unpublished commits' reachable objects: 2313 Git
objects and 1078 blobs, plus commit messages and current tracked artifact names.
No AWS access-key literals, GitHub tokens, private-key blocks, committed state or
private Terraform plans were detected. Four SQL-password regex candidates are
four versions of the same unused loopback documentation fixture: network none,
startup migrations disabled, database/user explicitly unused. Values were not
printed or included in the report. Public account/resource IDs are deliberately
present in existing deployment reports/policy snapshots; private runtime state,
plans, logs, credentials and secret values must remain outside publication.
This is heuristic, bounded evidence, not a universal secret-scanner guarantee.
The final documentation-only commit requires the same bounded recheck before push.

## Authentic AWS installation completed

Profile `cnp-cert-dev`, account `341936017254`, region `us-east-1` only.
STS confirmed `arn:aws:iam::341936017254:user/cnp-cert-admin`.
IAM initially listed no OIDC providers and CodeBuild listed no project controllers
for this application. The only existing E1 controller roles were the three NAT
handlers; the exclusive `TerragruntDemoDevOperator` remains separate.

The source-defined
`module.protected_resources.aws_iam_openid_connect_provider.neutral_oidc`
was installed using a targeted, saved and reviewed security-root plan containing
**one creation**, with no runtime, PROD or existing shared-resource mutations.
Terraform 1.13.4 / AWS provider 5.100.0 and native S3 locking were used. Binary
SHA-256: `854d0c085ec3987f0fc1895d38cbe4470e37263574d84d5cd135decad7e94ab9`.
Native IAM readback confirms provider
`arn:aws:iam::341936017254:oidc-provider/token.actions.githubusercontent.com`,
URL `token.actions.githubusercontent.com`, audience `sts.amazonaws.com`.
No role trust or permissions were activated by creating this provider alone.
The provider is tracked in the retained security Terraform backend; no competing
runtime state writer or hand-edited state was introduced.

OIDC is **not yet functionally proven**. Only a GitHub-issued token followed by
successful STS assumption and identity verification can establish that result.
No permanent AWS credentials were installed in GitHub, no JWT was logged and no
credentials were copied to the VM. No additional running compute was created.

## Existing real path and exact missing prerequisites

| Phase | Existing implementation | Current evidence / next prerequisite |
| --- | --- | --- |
| GitHub source validation | `ci.yml` -> `ci-dotnet.yml` | New branch push selects all gates; exact .NET SDK 8.0.425, tests, Docker build and packaged probe checks already exist. Not run in GitHub yet. |
| WP3 request | `release-build.yml` -> pinned `e1-release.yml` | Public caller remains intentionally inactive until genuine immutable pin, gateway/version and governance installation. |
| WP3 qualification | `scripts/internal_release`, `scripts/build_supervision`, `scripts/qualification` | Existing gateway/controller, three subordinate workers, finalizer/status and immutable runtime/bundle installation are absent. Do not substitute CI defaults or fabricate qualification. |
| ECR publication | Existing WP3 protected OCI publisher | Actual contract publishes `demo-shared-demo-ms`, not the manually bootstrapped `demo-dev-shared-demo-ms`. The former is not installed. Do not silently change shared/PROD ownership or relabel the current image qualified. |
| WP4 DEV | `deploy-dev.yml` -> pinned `e1-dev-deploy.yml`, normal-delivery and WP4D runtime | Install only DEV gateway/controller/cleanup, protected eligibility/membership and authentic current ECS/listener/rule/target bindings. No WP5/PROD activation is needed. |
| Promotion/rollback | Existing normal delivery and protected history paths | Keep their independent approvals/qualification/history requirements. Neither traffic promotion nor rollback has been tested in this task. |

WP3's declared neutral artifacts bucket is
`demo-release-artifacts-341936017254`; its existing separate quarantine/exchange
contract also remains required. These are the reviewed source architecture,
not permission to modify existing unrelated/shared resources. Before installation,
review the exact neutral release resource scope against the owner's shared-resource
restriction; never map the DEV image repository into neutral/PROD authority as a
shortcut. No additional deployment system or credentials platform is proposed.

The existing request-role names are `e1-request-release` and
`e1-request-deploy-dev`. Their permitted Actions path is numeric-version gateway
invocation plus reading only their own sanitized completion prefix. ECR writes
belong to the existing WP3 publisher, not those request roles. WP4's execution
role may register only the two DEV task families, pass only the four exact DEV
execution/task roles with `iam:PassedToService=ecs-tasks.amazonaws.com`, update
the two DEV services and modify the current exact ALB listener/candidate rule.
No Terraform state write, IAM administration, PROD/shared mutation or broad role
chaining is part of either GitHub request identity. Do not install these roles
with fictional gateway versions or mark missing G1-G9 evidence verified.

Current WP6 release/deploy source-ref guards require `refs/heads/develop`.
The first proposed publication is the feature branch only: it can genuinely run
CI, but it cannot secretly activate the develop-only deployment route. Preserve
remote develop history. Resolve its normal reviewed integration, or an explicit
DEV-only branch-contract change with focused/full protected-contract validation,
before claiming an end-to-end deployment. No force push or implicit develop/main
publication is authorized by a feature-branch push.

## Publication gate and execution order

Before the first push obtain explicit approval naming the public repository,
exact feature branch, current commit range/count and intended workflows.
The first proposed push runs the existing `ci.yml`, including `ci-dotnet.yml`,
repo hygiene, infrastructure static checks and the complete E1 acceptance gate
selected for a new branch. It grants no application deployment authority.

After publication, observe actual run IDs, jobs, test/build results and immutable
source identity. Complete only the necessary existing WP3/WP4 DEV installation
and OIDC/ref/environment protections, with authentic readbacks and exact package/
image versions. Then invoke the qualified release and normal delivery routes,
retain any independent promotion gate, verify digest/task/target identity and
exercise readiness plus real SQL/KMS. Do not replace this with direct ECS writes
from a newly broad GitHub role. Do not report end-to-end success before it occurs.

Provider creation and focused hermetic validation do not certify Actions/OIDC,
WP3, image publication or WP4 success. No Actions run was dispatched and no push
has occurred at this checkpoint. The image remains the second cycle's known
`sha256:9671c5484c60de9db50f54abade794bb86263a5d636bca96a5eb3522c8643a50`.

## Cost and preservation

Original DEV remains running at the second-cycle endpoint
<https://427id1ezuk.execute-api.us-east-1.amazonaws.com/ready>.
The estimated base remains about USD 0.102/hour plus variable and retained costs.
OIDC provider creation adds no always-on project compute. KMS/secrets, ECR,
backends/evidence, both NATs, SQL, ECS blue/green, internal ALB and API remain
preserved. No DOWN, NAT failover, repository GC or PROD deployment occurred.
If publication/installation must wait for a prolonged session, recommend the
previously tested supervised DOWN to the owner; do not execute it automatically.


## Completed focused validation

278 hermetic tests passed without failures/errors/skips: WP3 internal release 33,
WP4 authorization 20, WP4 delivery 98, WP4D materialization/adapters 33, WP6/OIDC
61 and CI selection/enforcement 33. These are repository tests, not Actions or
AWS application-deployment evidence. No protected contract, package, generated
workflow or Terraform source was changed, so the complete historical E1 gate was
not rerun locally. Source inventory remained exact, documentation links and
`git diff --check` passed. Final AWS readbacks show both services steady 1/1,
NAT rule enabled and public readiness Healthy. No temporary inline grants were
added to the DEV Terraform operator.
