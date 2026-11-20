# Delivery and retained deployment evidence

The current operational reference is [automatic API delivery](../../docs/DEV-DELIVERY-DESIGN.md).
A protected application merge to `develop` waits for exact-SHA CI and deploys DEV
through Docker, ECR and the common ECS blue/green executor. Documentation-only
merges do not publish an image or obtain deployment credentials. PROD is disabled
and unqualified; [CI and branch protection](../../docs/CI-CD-REVIEW.md) are separate
from future PROD activation requirements.

Terraform uses the [native lifecycle](native-dev-lifecycle.md). The public DEMO
uses its independent [static hosting procedure](../../portfolio/product/HOSTING.md).
The [E1 final acceptance contract](e1-final-acceptance.md) and historical gateways
remain source/test dependencies; they are not the current application delivery path.

## Demonstrated V2 delivery

- [First automatic DEV deployment](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835): merge-triggered execution, ECR digest, healthy ECS and observable HTTP change.
- [CA-only SQL TLS delivery](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2): definitive DEV trust without the temporary bridge.
- [Current failure/rollback procedure](../../docs/DEV-DELIVERY-DESIGN.md#failure-rollback-and-reconciliation): current configuration and live SQL/KMS compatibility are required; image rollback does not roll back schema.

## Historical V1 qualification

The following original record is preserved because the historical portfolio and
its tests cite its exact images and SQL/KMS continuity. It proves the October
V1 experiment, not PROD recovery or current V2 controller behavior. Earlier
installation/debugging chronology is available in the
[pre-consolidation record](https://github.com/Kendall04/terragrunt_demo/blob/1a39c46cc02f262c04f438207647acc1282393a0/terraform/docs/deployment.md).

## Real SourceTransport qualification and distinct-digest DEV rollback

Verified on 2026-10-15 in Costa Rica (the rollback Actions run is dated October
16 UTC). Only account `341936017254`, region `us-east-1`, profile `cnp-cert-dev`
and `codex/final-github-actions-cicd` were used. No PROD/shared changes, IAM
expansion, CreateOnly exception, Terraform-state operation, NAT failover or DOWN
was part of this trial. The existing controller, workers, publisher, WP4 and
cleanup were used; no direct ECS/listener replacement for WP4 was performed.

### SourceTransport and the HTTP failure

The installed controller used OCI digest
`sha256:2643aa2efb14db3672959194451e6b361223be9517029083435cb3e0b4744860`.
Its metadata request is an unauthenticated HTTPS GET to the fixed public
repository's `/git/commits/<exact SHA>` followed by `/git/trees/<tree SHA>?recursive=1`.
The failed [38824573732 run](https://github.com/Kendall04/terragrunt_demo/actions/runs/38824573732)
left authentic source FAILED evidence and seven NOT_RUN checks; only its waiting
Actions job was cancelled after native terminal reconciliation. No worker/image
or qualification came from that failure. Its bounded diagnostic recorded HTTP
403 but no response headers/body, so its precise rejection reason cannot be
retroactively asserted. Earlier independent quota-zero observations are not
proof of the cause of this particular 403.

New native CodeBuild diagnostics used the installed Source implementation and
its original Git checks. Equivalent metadata requests returned 200 with anonymous
limit 60 and available quota; Windows anonymous and authenticated controls also
returned 200. A complete native acquisition passed **2 REST metadata requests
plus 40 immutable raw downloads**, verified every Git blob SHA-1 and obtained
source seal `fb2ba65d5d44231300b0de8cdae103cf2be9b70ffa0be2d6da962a0fe7fa7378`.
It did not launch workers or count as a qualification. This verified the already
installed reduction from 42 REST requests before another business request.
[GitHub documents](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
the anonymous quota by originating IP. Two metadata reads still require GitHub
availability; neither IAM expansion, token transfer, blind retry nor guaranteed
immunity from future HTTP denials is claimed.

### Genuine qualification and version difference

[WP3 38825575655](https://github.com/Kendall04/terragrunt_demo/actions/runs/38825575655)
completed SUCCESS for published source
`f55f52f501bbec6138d3eed994ab08e19510ef8a`. Native controller and all three worker
builds completed SUCCEEDED. All seven protected checks passed; the .NET worker
reported 103 passed tests. The authorized publisher published the image into
neutral `demo-shared-demo-ms`, not the manual DEV registry. Qualification,
manifest VersionId/hash, actual ECR digest and DEV eligibility were read back.

| Identity | Original A | Qualified B |
| --- | --- | --- |
| Source | `b1e59975c0dae7cd4baf0d897f77d04192744ccc` | `f55f52f501bbec6138d3eed994ab08e19510ef8a` |
| Release | `sha256-b22f33f93bdac5608da1dcd1e17f372f638dcaa766c1e758f34ee6f396673f44` | `sha256-279f48b8311d9c5dfaa8f93f7ae060e0598cece03ec0f35817398eeba8976f53` |
| Image | `sha256:ca7d92532de8cfeee7a7a59a80f78714a26083ff323019d512d8be20f83ebfb8` | `sha256:7aa96288aa4449de35864d87a86fd9a89024fba13b95c88a1027c1b11cbcd654` |

B includes the harmless fixed startup message `Application revision: rollback-proof-v2.`;
HTTP, SQL schema and KMS contracts are unchanged. The real blue task's CloudWatch
startup log contained that marker with digest B, so this was not merely a changed
build timestamp/label. Controller digest `2643aa2e...` is not an application digest.

### Protected delivery, rollback and automatic cleanup

| Phase | Actions result | Real traffic/digest | Automatic cleanup |
| --- | --- | --- | --- |
| Deliver B | [38825984998 SUCCESS](https://github.com/Kendall04/terragrunt_demo/actions/runs/38825984998) | blue:9, B | green tasks/targets empty; temporary rule absent; E2 generation 12 RELEASED |
| Roll back A | [38827037528 SUCCESS](https://github.com/Kendall04/terragrunt_demo/actions/runs/38827037528) | green:8, A | blue tasks/targets empty; temporary rule absent; E2 generation 14 RELEASED |

The published DEV `rollback-manifest.yml` caller already allowed exactly the
trial branch, workflow_dispatch and pinned `e1-dev-deploy.yml@f0ba8ad1d6528d362693c8de932f935c8084529d`.
No new caller publication or trust weakening was needed. Its PROD job was skipped.
CloudTrail independently confirmed actual AssumeRoleWithWebIdentity, exact
Environment subjects/audience and the existing request roles for WP3 and both
WP4 requests. Numeric gateways were release:2 and deploy-dev:3; pins/trusts stayed
unchanged.

Rollback consumed original protected SUCCESS history
`6471310a-0a3a-489a-81dd-42213a00ad80`. It recreated green revision 8 from the
qualified original digest; it did not restart deleted green:7 tasks or relabel B.
The old SUCCESS receipt/version remained unchanged. Both promotions and cleanups
have native protected SUCCESS receipts. No manual drain, rule deletion, E2 CAS
reconciliation, history rewrite or forced settlement was needed. A draining ALB
target was kept nonterminal until AWS reported actual absence.

Both served versions passed `/ready` and POST/GET `/text` SQL/KMS round trips.
After rollback, A also read/decrypted the text written by B. This is live
application/database/key compatibility for this unchanged schema, not database
backup/restore evidence. Final native observations show green:8 healthy, blue:9
at zero with no tasks/targets, listener on green, no temporary rule and E2 released
with no schedule. API Gateway/VPC Link and the original full topology remain.

Focused hermetic validation passed 33 internal-release and 33 WP4D tests, no
failures/errors/skips. The 103 .NET tests and Docker/probe checks above ran in the
real qualified workers. The local documentation follow-up did not rerun the
full offline gate or assert new Terraform provider validation/lint comparison;
the prior activation's acceptance is recorded above, and normal CI enforces the
repository gate when this branch is published.

DEV remains running and billable. The trial added one qualified application image,
short CodeBuild executions, logs and protected S3 versions; no new permanent
infrastructure or IAM authority. ECR images, evidence and backends remain retained.
A destructive NAT replacement experiment and the final DOWN/data-loss decisions
are separate gates; no completion of either is implied by application rollback.
