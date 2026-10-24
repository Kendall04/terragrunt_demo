# V2 SQL/API cross-AZ recovery packet

Current checkpoint - 2026-10-23: **controlled SQL/API cross-AZ proof closed;
unchanged full workflow acceptance pending**. Az6 passed with two explicit live
repairs and clean retirement. Artifact 65c7901 is reproducible; its new staging
helper and local-backup CLI passed native SQL, followed by an explicitly manual
SQL restore. The complete EC2/systemd/remote-restore/encrypted-API path without
manual repairs remains pending. No AWS cycle or budget is authorized by this file.

The [local completion checkpoint](../../../terraform/docs/v2-local-completion.md)
maps the current Page criteria, actual tests, backup-health improvement and
unavailable PKI/Sentinel source gates. V1 delivery and the October 21 manual/two
hourly backup acceptance retain their historical scope. Earlier dated proposals
below remain historical; generated plans and offline fixtures are not live proof.

This is one finite drill, not a lifecycle framework. It exposes a Terraform root,
public security additions, explicit host actions and sanitized receipt JSON for a
future lifecycle owner. No cloud executor, scheduled task or automatic approval is
installed. No original E16 proof, five runtime states, E13 exception or RDS owner is
reused. RDS/EKS networks and checkouts are excluded.

## Scope and owners

`prepare.py render --trial rYYYYMMDDsuffix --output <new-private-directory>` is
offline. It renders exactly **20 Terraform resources**: one VPC, one IGW, three
subnets, three route tables, three associations, three default routes, one public
NAT Gateway, one EIP, one host SG, one S3 gateway endpoint and two EC2 hosts.
Hosts use reviewed Ubuntu 22.04 x86_64, t3.medium Standard credits, 30-GB encrypted
gp3/delete-on-termination, IMDSv2, no public IP and no ingress. Egress permits
TCP 80/443 for bootstrap/SSM/AWS and DNS to the VPC resolver. One NAT in AZ A is
adequate for the controlled SQL-host loss drill; **AZ-wide egress failure is not
tested**. No ALB/ECS/API Gateway/ASG/Lambda/CloudWatch alarm or new KMS key, bucket,
secret, role or profile is created. AWS creates NAT/host ENIs, the VPC main/default
network objects and root EBS volumes incidentally; verify their removal too.

The isolated root owns only the 20 resources. A future normal security owner
installs/removes additions to existing role and key/bucket policies, comparing
fresh complete policy hashes before every merge and restoration. Preserve unrelated
statements. This is not an ordinary lifecycle permission to administer security.
The retained SQL role/profile is reused on both hosts: it already reads the two
original DB password secrets. Confirm the complete installed policy/trust first;
reusing it also preserves its broader original SA-bootstrap privilege. Secret
values are read only in future authorized EC2 processes, never Terraform or output.
Passwords are not rotated, copied into evidence or deleted.

The generic renderer's `security-additions.json` is historical preparation, not
the metadata-bound installation packet below. Its redundant bucket/text-key/
publisher additions are superseded for this trial. It originally proposed
new trial-prefix object access,
backup CMK use restricted through regional S3/encryption context, direct
Encrypt/Decrypt of the exact text CMK for the co-located API, and three scoped
bucket denies. The text-key permission is a real temporary expansion, not assumed
existing authority. All sessions of the shared role are affected while installed.
Key-policy `Resource: "*"` means its enclosing exact CMK; it is not an account-wide
key grant. Do not replace whole policies with these addition fragments.

After real artifacts exist, `prepare.py publisher --trial ... --sha256 ...`
renders exact artifact-key permissions for cnp-cert-admin and matching CMK
context. This grants no administrator read/decrypt of database backups. Prior
denials are not permission to retry. The publisher and role overlays are removed
at closure/abort after their dependent actions have finished.

Backend: retained bucket `e1-lifecycle-dev-341936017254-us-east-1`, **new isolated**
key `e1/lifecycle/dev/recovery/<trial>/terraform.tfstate`, native `.tflock`, default
workspace. Obtain explicit exact Get/Put authority for state, Get/Put/Delete for
the lock and prefix-limited bucket listing from the normal security owner. Check
bucket default encryption and any exact backend KMS authority first; no new key
or existing-five-state access is implied. Retain the terminal empty state/evidence.

## Review before first cost

1. Fresh STS solely cnp-cert-dev/account 341936017254/us-east-1, clean reviewed
   source, one operator, current policy versions, legitimate security authority,
   no unfinished original owner/mutation, workflows still disabled. Observe first;
   never replay uncertain mutations. Existing rules/concurrency remain inhibited.
2. Bind distinct real AZs and fresh Canonical AMI owner/architecture/SSM-agent
   metadata. Install no credentials on Windows. No default VPC or old resource IDs.
   Confirm 2+2-day parent lifecycle, versioning, exact keys Enabled, bucket keys
   disabled for exact S3 object contexts, bucket denies and original resources.
3. Prepare the separate security additions and a **fresh full-root create plan**,
   its JSON/hash/source/backend bindings and installed multi-resource IAM results.
   Terraform 1.13.4 / AWS provider 5.100.0 reuse the reviewed provider lock. Offline
   format/schema/fixture checks do not substitute for this live plan.
   `prepare.py review-create --trial ... --input plan.json` is a structural manual
   aid only, always `AllowsCreation:false`; review remaining provider-normalized
   values/unknowns, IDs, tags and exact ARNs. No target/replacement/foreign owner.
   It does not validate evaluated AMI/AZ bindings or destroy before-state IDs,
   tags and ownership; these remain independent mandatory preflight checks.
4. Review creation operations: EC2 CreateVpc/Subnet/RouteTable/InternetGateway,
   AttachInternetGateway, AllocateAddress, CreateNatGateway, CreateSecurityGroup,
   Authorize/RevokeSecurityGroupEgress, CreateVpcEndpoint, CreateRoute,
   AssociateRouteTable, RunInstances and CreateTags; IAM PassRole only the retained
   SQL role with PassedToService ec2.amazonaws.com. Include provider read APIs and
   default EBS encryption/KMS requirements. New IDs cannot be exact before create:
   any necessary create-resource ARN pattern/read `Resource:*` must be individually
   justified and region/request-tag constrained where the API supports it. No
   effective installed operator authority is certified by offline preparation.
   The concrete temporary policy below needs live review and installation approval.
5. Review withdrawal **before** first cost: TerminateInstances, DeleteNatGateway,
   ReleaseAddress, DeleteVpcEndpoints, DeleteSecurityGroup, DeleteRoute,
   DisassociateRouteTable on tables **and subnets**, DetachInternetGateway on IGW
   **and VPC**, DeleteInternetGateway/Subnet/RouteTable/Vpc. Check read/describe,
   policy restoration and state-lock capabilities as well. Native NAT deletion
   can take minutes. Do not assume future approval will unblock retirement.
   `bind-retirement` consumes privately exported state and emits exact observed
   ARN additions for a complete runtime; it is not a live IAM evaluation, partial
   failure resolver or substitute for precreation withdrawal authority.
   Duplicate-ID refusal proves distinct IDs per resource type, not canonical
   addresses, installed authority or live ownership.
6. Owner approves logical resources, security JSON, secret reads, synthetic
   disk/data loss, retention, new budget/TTL and any narrow same-resource API
   fallback explicitly. If authority/retirement is incomplete, do not start.


## Binding checkpoint and next consent - 2026-10-21

Baseline: 855cd57; current artifact recovery-e1f8ee3.tar, SHA-256
d745816853bb22a8e5be8df7155d0bdfd367deb31fd3ddeb05ce92eefd3fffa0.
The 20-resource blueprint hash still matches the recorded schema validation.
A fresh schema-only query used the retained central AWS 5.100.0 provider, without
backend initialization, downloads or cache copies. Profile is a string reference;
it does not create or own the retained IAM profile. The recorded 25+6 tests and
Linux publish remain evidence; no live/Linux recovery or new build ran here.

**Effective executor remains unbound.** The rendered provider names cnp-cert-dev
but contains no assume_role binding. Historical STS returned cnp-cert-admin;
that is not proof that runtime would use TerragruntDemoDevOperator. Select and
review the legitimate runtime AND backend principal before remote planning; do
not silently apply as administrator or change identity to bypass a denial.
A source/config adjustment, if needed, requires its own narrow reviewed diff.

The next requested authorization is only this bounded metadata block, starting
with STS account 341936017254/profile cnp-cert-dev/region us-east-1. It has NOT run:

| Binding | Exact read operations and bounded subjects |
| --- | --- |
| Identity/IAM | sts:GetCallerIdentity first; iam:GetUser for an IAM-user caller only, and its inline/attached-policy lists/documents; iam:GetRole/GetInstanceProfile, ListRolePolicies/GetRolePolicy, ListAttachedRolePolicies/GetPolicy/GetPolicyVersion for roles TerragruntDemoDevOperator/demo-dev-data-sql-ec2-role and profile demo-dev-data-sql-ec2-profile only, including their actual boundaries and referenced managed policies; GetContextKeysForPrincipalPolicy/SimulatePrincipalPolicy for those exact principals/actions/resources. Simulation alone does not establish SCP or explicit-Deny absence. |
| AMI/AZ/compute | ec2:DescribeImages restricted to Canonical owner 099720109477/Ubuntu 22.04/x86_64/EBS; DescribeAvailabilityZones, DescribeInstanceTypeOfferings for t3.medium; GetEbsEncryptionByDefault/GetEbsDefaultKmsKeyId. DescribeInstances/InstanceAttribute/InstanceCreditSpecifications/Volumes/NetworkInterfaces/NatGateways/Addresses/Vpcs/VpcAttribute/Subnets/RouteTables/InternetGateways/SecurityGroups/Tags, plus DescribeSnapshots for the selected AMI snapshot IDs only, for project/trial filters or returned exact IDs. AMI metadata cannot prove a running SSM agent. |
| Storage/keys | On the two exact buckets in prepare.py: GetBucketLocation, GetBucketVersioning, GetBucketEncryption, GetBucketPolicy, GetBucketLifecycleConfiguration, GetPublicAccessBlock and GetBucketOwnershipControls; HeadObject without ChecksumMode only for the proposed isolated state/lock and exact artifact key, prefix-limited ListObjectsV2/ListObjectVersions to detect collisions. kms:DescribeKey/GetKeyPolicy only for BACKUP_KEY/TEXT_KEY and the actual existing backend/EBS key if metadata identifies one. No backup or state-body download, decrypt, retention edit or key creation. |
| Secrets/SSM | secretsmanager:DescribeSecret only for SA_SECRET and APP_SECRET exact ARNs in prepare.py; ssm:GetDocument AWS-RunShellScript, and DescribeInstanceInformation only for returned trial instance IDs if any. No GetSecretValue, SendCommand, StartSession or credential/config read. |
| Existing fences/CI | events:DescribeRule e1-wp4-dev-nat-launch; lambda:GetFunctionConcurrency on e1-cleanup-recovery-cleanup-dev, e1-gateway-deploy-dev and e1-nat-recovery-nat-dev-{assign-eip,change-rt,disable-sdc}; GitHub GET only Kendall04/terragrunt_demo workflows 227405531/227408821 and their bounded queued/in-progress runs. Confirm the legitimate single operator independently; no unspecified E2 status call is included here, and no old receipt proves current ownership or permits re-enabling controls. |

Resource constants are the exact [prepare.py](prepare.py) ARNs, not permission
to enumerate other accounts, IAM identities, secrets or organization trees.
If applicable SCP evidence is unavailable, obtain it from the owner and report
the gap; do not infer it from simulation. DescribeVpcEndpoints was previously
AWS-denied for the operator: review its capability, but do not redispatch that
denied read without relevant changed-permission evidence. Administrator backup
GetObject/KMS Decrypt and SSH/config restrictions are not reopened.

This metadata block excludes Terraform remote init/plan: initializing a new S3
state manager can write initial state/lock even before resource creation. The
future approval must include exact backend state/lock writes and artifact
publication separately from metadata reads. Metadata requests can themselves
incur API charges; this local checkpoint authorizes neither them nor runtime.
A HEAD 403 is UNKNOWN, not absence; existing keys or unverified access stop planning.

Close indirect permissions before first cost: review ModifyVpcAttribute for DNS
and provider-dependent ModifySubnetAttribute, SG default-egress revocation/new
rules, CreateTags and multi-resource RunInstances (AMI, subnet, SG, ENI, volume,
instance), plus PassRole only for the existing SQL role/ec2.amazonaws.com.
Bind actual EBS/backend key permissions; any required KMS grant must identify
its key/principal/service context explicitly. Provider schema proves field
shape, not a complete API permission set. Include SSM command/observation,
host secret reads, bootstrap egress and existing text/backup KMS/S3 flows.
The normal destroy permissions and both companion resource classes remain
mandatory; do not add the previously denied optional volume/EIP operations.

The executable trial remains two private hosts in different AZs, one fresh
synthetic backup and warm-target SQL/API restore, then normal withdrawal of the
20 owned resources plus their incidental EBS/ENIs. Shared profile/role, keys,
secrets, buckets/backend, Canonical AMI/snapshots and managed SSM policy are
references, never additional destroy targets. Remove only approved policy Sids/
inline additions after their dependent actions; compare full current policies
before restoration and stop on another writer's changes. Preserve inherited
2+2-day retention; a mismatch is a blocker, not permission to edit lifecycle.

After metadata closes bindings, present ONE concrete lifecycle approval:
effective principals and fresh plans; exact backend/artifact writes; temporary
role/backend-bucket/backup-key additions and their removal; EC2-only reads of the
two original secrets; Express EULA/host execution; synthetic disk/data loss and
normal full teardown; retained originals/evidence; proposed NEW USD2/four hours,
withdrawal by minute 150 with 90 minutes reserved. No cost envelope is approved
here. Individual platform confirmations may still be required per sensitive
action; grouped owner consent does not override a platform denial. No automatic
API fallback or new permission outside that reviewed scope is implied.

## Package and explicit host sequence

Publish existing API and SqlBackup projects separately as Linux x64 self-contained
.NET 10.0.13 from a clean reviewed commit, using SDK 10.0.402 and reviewed restore
inputs. `bundle.py build --api <publish> --backup <publish> --archive <new-tar>
--commit <sha>` checks pinned runtimes and inventories a deterministic archive.
`bundle.py inspect --archive <tar> --sha256 <hash>` checks every member; no upload,
extraction or execution occurs. Inspect and extract under a new root-owned 0755
`/opt/...` directory on both hosts, preserving reviewed modes. Public bundle/config
only; never include passwords or AWS files. Upload/read exact artifact versions
using the approved publisher/role. Receipt directories on hosts are root 0700.

Bootstrap installs SQL Express, caps SQL memory at 2 GiB, binds loopback and polls
SQL readiness with bounded attempts. It creates no database, timer or API. Confirm
SSM/SQL readiness on both hosts before the drill; a failure stops the session for
review, not a replay of cloud-init. This new bootstrap is locally reviewed, **not
live-qualified**. Future execution includes Express EULA acceptance.

`host.py <source|quiesce|restore> --trial ... --directory <private-dir>` defaults
to plan-only, reading no secrets. Execution additionally requires Linux root,
`--execute --acknowledge <trial>`, actual EC2 identity in the expected account,
and approved artifact binary paths/hashes for source/restore. Its STARTED marker
survives success/failure; every uncertain or existing action requires review,
never blind replay. Receipt hashes/SSM command IDs and artifact versions must be
recorded independently by the operator; local receipt JSON is not remote attestation.

- On A, `source` creates only fresh `recoverydb` and recovery_app/db_owner, starts
  the existing API on loopback with migrations enabled, posts one synthetic marker,
  invokes the existing exact-version backup CLI, posts a second marker and stops
  the API. Backup/verification use SA in this bounded lab; this is **not proof of
  least-privilege SQL backup roles**. Secrets stay in process memory/environment;
  privileged host users can inspect them. CLI runs as mssql for SQL file access.
- Copy the sanitized source receipt to the private directory on B via the approved
  operator channel. A `quiesce --source <receipt>` stops SQL and verifies inactive;
  failure time is recorded before stop dispatch. Corroborate host/SSM timestamps
  and absence of source activity externally. Both hosts need synchronized clocks.
- On B, `restore --source <receipt> --failure <quiesce-receipt>` refuses the same
  instance/AZ, wrong trial/prefix and inconsistent times. It invokes existing
  hash/header/checksum/CHECKDB/no-overwrite restore into
  `recoverydb_restore_<trial>`, remaps the synthetic login, then runs API with
  migrations **disabled**. GET must decrypt the pre-backup marker, the post-backup
  marker must be absent, and a new POST/GET must work. API stops on exit. A failure
  retains synthetic DB/files for explicit reviewed teardown, never overwrite/retry.

Host action options for source/restore include `--backup <absolute SqlBackup>
--backup-sha256 <binary-sha> --api <absolute terragrunt-demo>
--api-sha256 <binary-sha>`. Hashes come from the inspected bundle manifest.
No full app release, traffic redirect or original database is touched.

Every executing action also requires `--expected-instance-id <actual-plan/readback-ID>
--expected-az <actual-readback-AZ>` and matches them against IMDSv2 identity. Bind
these from the approved trial, never an unrelated host. An acknowledgment string
is not an authorization system or a substitute for owner approval.

RTO is failure declaration through restored integrity and API proof, with a
**preprovisioned warm target and existing trial network**. It excludes complete
infrastructure cold recovery. Marker request/confirmation brackets commit time;
failure minus pre-marker request is a conservative observed marker-age bound.
Post-backup absence demonstrates controlled loss. This single drill does not
qualify hourly RPO <=70 minutes, a production workload or ongoing reliability.
Component RTO <=30 minutes remains an objective until measured and reviewed.

## Cost, teardown and closure

New proposal: USD 2 incremental, 4 hours maximum, start withdrawal by minute 150
(90 minutes reserved). Record conservative first-billable time **before dispatch**
and derive absolute times with `prepare.py timeline`. No automatic shutdown or
AWS spending cap exists. At minute 90, abort acceptance if insufficient time
remains for a healthy drill and teardown. No two-hour wait or hourly repeat.

2026-10-21 pricing basis (us-east-1 Linux On-Demand): 2 x t3.medium x 4h x
USD0.0416 = 0.3328; 60 GB gp3 x USD0.08/GB-month x4/730 ~=0.0263; NAT Gateway
4h x USD0.045 =0.18; one IPv4 x4h x USD0.005=0.02. Baseline ~=USD0.56; budget
USD0.25 for <=2 GB NAT processing/transfer, <=0.5 GB artifact and API/log use,
leaving >USD1 contingency. Reprice official EC2/EBS/VPC/S3/KMS inputs and bound
artifact/egress quantities before approval. No CPU surplus charge in Standard;
CPU throttling can affect timings. Existing retained KMS/secrets/S3/backend costs
are additional. This is not a guaranteed total bill or tax-inclusive quote.
Sources: https://aws.amazon.com/ec2/pricing/on-demand/ ;
https://aws.amazon.com/ebs/pricing/ ; https://aws.amazon.com/vpc/pricing/ .

Immediately after proof or abort: finish/observe in-flight host actions, stop API
and SQL on both hosts if reachable, then review a fresh **normal full-root destroy**
plan. `review-delete` must match 20 deletes/no creations/replacements/foreign owners.
On partial apply/failure, inspect current state and effects first; review the
smaller residual destroy manually (the complete-inventory helper will refuse it).
No optional DeleteVolume/DisassociateAddress permission is assumed or reinstated.
API fallback needs explicit approved scope and cannot bypass an authorization denial.

Withdraw both EC2/root disks, endpoint/routes/associations, NAT then its ENIs/EIP,
SG/subnets/IGW/VPC. Verify host/root volumes/NAT/EIP/ENIs/VPC absence, empty isolated
state and absent lock, plus unchanged original retained resources. Remove exact
temporary role/publisher/key/bucket additions and verify readback; preserve original
statements and existing parent lifecycle rules. If a read/delete is denied, report
the exact target and reason, retain evidence and continue independent cleanup.

Only newly generated synthetic data/logs on host disks are destroyed. New S3
backup/artifact versions remain under the existing parent 2+2-day lifecycle;
asynchronous expiry is not a deletion deadline. Do not delete historical objects,
keys, buckets, original roles/secrets or evidence. Retain sanitized receipts with
actual scope, timings, independent readbacks and cost-estimate limits. A successful
restore and successful lifecycle close are separate outcomes.


## Metadata-bound temporary authorization packet - 2026-10-21

`authorization.py --proposal <preflight-proposal.json> --evidence
<preflight-readonly.json> --output <authorization-packet.json>` reads existing
local metadata only and emits one finite installation/cycle/reversal packet.
It executes no SDK, subprocess, credentials or cloud requests. Both permission
flags remain false; its structural tests never certify installed IAM authority.
The external reviewed packet SHA256 is
`63a1e1b4870c4dbd57d51c3973f9513fc88e5e2362822878e54befb53f46d93e`.
Keep that original packet unchanged during independent review. Full policy hashes
use `prepare.encoded`: sorted JSON, indent 2, UTF-8, terminal newline.

Bindings: trial `r20261021az1`, Canonical Ubuntu 22.04 AMI
`ami-033ea4ff4a9c726dc`, source us-east-1a/use1-az1, restore us-east-1b/use1-az2;
these are dated observations, not stock or SSM qualification. Source profile
`cnp-cert-dev`, account 341936017254 and region us-east-1 remain explicit. Both
provider and backend assume the existing TerragruntDemoDevOperator role, session
name equal to trial, duration `1h`. They renew independently using the existing
AWS SDK AssumeRole mechanism, with credentials only in memory. No trust,
MaxSessionDuration, profile or credential files change. An SSM client must use
the same SDK AssumeRole profile provider in memory (source_profile=cnp-cert-dev,
duration_seconds=3600), not one manually exported STS result. Check effective
identity and renewability before first cost and withdrawal; loss of source
credentials stops new work. No administrator runtime fallback or deadline
extension is implied. Live AssumeRole/renewal remains untested here.

Copy `Configuration.provider_override.tf.json` alongside the existing rendered
root, use `Configuration.backend-config` for partial backend configuration, and
bind the included tfvars in the **default workspace only**. The override preserves
all 20 resources and the encrypted 30-GB gp3/delete-on-termination roots. It moves
root-device tags to equivalent `volume_tags`: provider 5.100.0 sends those in
RunInstances instead of a subsequent CreateTags request. This avoids permission
to adopt/tag arbitrary existing disks. Existing host/prepare binaries are
unchanged: retain recovery-e1f8ee3.tar, SHA256
`d745816853bb22a8e5be8df7155d0bdfd367deb31fd3ddeb05ce92eefd3fffa0`;
the local authorization/config overlay is separate, with no new build or tar.

Temporary edits, only after explicit execution approval and fresh baseline checks:

1. The original security owner adds `Recoveryr20261021az1` inline to the operator
   and SQL role using `Install` JSON. Check absent names, current policies and
   aggregate inline quota first: the operator addition is 9,527 non-whitespace
   JSON bytes against its shared 10,240-character quota; read-only preflight found
   no inline policy. Preserve ten managed policies, trust and their explicit Deny.
2. Backend: compare the full policy hash, then append **only** the new exact state
   and `.tflock` ARNs to `E16NoOtherDevObjects.NotResource`. Preserve that Deny,
   condition and ten original object exceptions. Identity grants Get/Put state,
   Get/Put/Delete lock and trial-prefix listing; no state deletion or workspace
   creation. Do not remove a global Deny or replace policies with addition fragments.
3. Backup CMK: preserve the existing administrator statement and append exactly
   two Sids: SQL-role GenerateDataKey/Decrypt through regional S3 for the new
   prefix, and publisher crypto through S3 for the exact artifact/hash only.
   Key-policy Resource:* means this enclosing CMK. No new KMS grant/CreateGrant
   is installed. SQL inline adds trial-prefix S3 access, bounded backup crypto,
   and **Encrypt only** on the exact text key; original Decrypt/secret reads remain.

No backup-bucket/lifecycle, text-key policy or EBS-key policy change; no new user
IAM policy, role, key or secret. Existing bucket conditions and 2-current +
2-noncurrent-day asynchronous lifecycle cover new backup/artifact versions.
Text Encrypt cannot distinguish synthetic plaintext and affects all sessions of
the shared SQL role while installed. Existing legacy operator permissions also
remain; only the additions are trial-scoped. These shared-role effects need consent.

New taggable resources require exact Project/Purpose/Trial request tags; existing
mutations require all three resource tags, including VPC/IGW and table/subnet
companions. Future IDs cannot be exact before create. Incidental launch ENI
permission is regional/AZ/no-public-IP scoped; the same request must authorize
tagged subnet/SG, exact AMI/profile/type and encrypted root. Regional Describe and
SSM receipt reads need Resource:* where APIs lack resource scoping. Plan/procedure
review must constrain count, ports, credit mode, SSM command contents and cost;
these JSON conditions do not enforce those dimensions. No standalone retagging,
ingress, DeleteVolume, DisassociateAddress or alternative-principal fallback.

`LifecycleDecision` preserves the finite sequence: fresh effective IAM/AMI/AZ/SSM/
quota/retention/fence checks, full operator-bound locked plan, exact conditional
artifact upload, two ready hosts, synthetic backup/quiesce/cross-AZ restore with
CHECKDB/API proof, and immediate normal full-root withdrawal after proof or abort.
Use bounded AWS-RunShellScript commands (600-second execution timeout), actual
trial IDs and sanitized receipts; no secret values in command parameters/output.
RPO/RTO and real cloud acceptance remain unmeasured. Effective IAM/SCP/resource
policies, evaluated AMI/AZ and before-state destroy ownership remain live checks.

Reverse after dependent host commands settle and normal teardown/readbacks:
retain empty isolated state, verify absent lock/hosts/root disks/NAT/EIP/ENIs/
endpoint/network, compare fresh policies to expected-after hashes, restore the
two original full policies and remove both named inline policies. Verify absence/
hashes and retained originals. Stop on other-writer drift instead of overwriting;
finish independent allowed cleanup and report the exact blocker. Keep overlays
until their dependent cleanup is complete. They persist until explicitly reversed;
no scheduled IAM removal or automatic shutdown exists. Retained backup versions
lose the trial crypto grant at reversal; their existing expiry is asynchronous.

One grouped future execution decision must cover the two temporary inline policies,
shared-role effects, exact backend exception and two CMK Sids with reversal;
one-hour operator sessions/renewal; exact artifact/backend writes; bounded SSM,
Express EULA and EC2-only original-secret reads; 20-resource creation/test/full
withdrawal and synthetic disk/data/log loss; inherited S3 expiry and retained
terminal state; proposed **NEW USD2 / four hours**, withdrawal by minute 150,
90 minutes reserved. Estimate USD1.20 with contingency (USD0.5591 base); reprice
dated October 21 inputs before dispatch. Begin the conservative clock before
first billable trial write/create. This preparation grants no expenditure or
cloud execution. Specific platform approvals may still block individual actions,
including reversal; future approval is not guaranteed.

Validation: 13 new authorization regressions + 25 existing recovery tests + six
retirement regressions passed locally. Terraform 1.13.4 and cached provider
5.100.0 validated the merged root: zero errors/warnings; no credential Configure,
remote backend init or live plan. Backend HCL parsed through fmt stdin; this is
not backend access proof. Public references:
[Terraform 1.13 S3 sessions and lock permissions](https://developer.hashicorp.com/terraform/language/v1.13.x/backend/s3),
[provider 5.100.0 volume tag placement](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/ec2/ec2_instance.go),
[AWS EC2 authorization data](https://servicereference.us-east-1.amazonaws.com/v1/ec2/ec2.json).


### Corrective review contract: effective volume tags

The concrete override above is mandatory for this authorization packet. The local
`review-create` reviewer requires exact trial `volume_tags`; the optional nested
root-device `tags` map may only be absent, null or {}. Nonempty nested tags,
incorrect/missing/additional volume tags and arbitrary representations are refused.
This correction passed 49 local tests (30 recovery, 13 authorization, six retirement).
Encryption, size/type/delete-on-termination, metadata, credit, instance/profile/
resource-tag and full-inventory/action checks remain in force. Offline integration
fixtures exercise the actual authorization override through the CLI for all three
optional-map shapes; they are not evaluated Terraform plans or IAM authority.

Only local plan-review code changed. The existing runtime tar remains
recovery-e1f8ee3.tar (`d745816853bb22a8e5be8df7155d0bdfd367deb31fd3ddeb05ce92eefd3fffa0`),
with its original source commit/manifest unchanged. Its embedded prepare.py is an
older snapshot: host.py imports only unchanged constants, require and trial from
that module. The corrected reviewer runs from this checkout, never from the tar;
it need not travel to EC2. Verify this import contract/content hashes locally.
No new tar, SDK/provider copies or Linux execution are needed for this correction.
Linux permissions/SSM/bootstrap/restore remain untested in this increment.

Approval limits remain explicit: rollback is an operator hash/read/compare/restore
procedure, not an atomic compare-and-swap. SSM permits arbitrary shell on the
trial-tagged hosts; command content is bounded by reviewed procedure, not IAM.
IAM enforces neither two hosts, TTL nor spending. The supervised plan/count,
deadline/budget and exact reversible security edits still need execution consent.


### DNS authorization diagnosis and local correction - 2026-10-22

The approved cloud attempt stopped at ModifyVpcAttribute (request
`7e9505cf-530c-48d5-8cf8-9c4bff851a94`). Its two created resources were withdrawn,
both temporary inline policies removed, and original backend/backup-key hashes
restored; closure was verified at 00:29:25 UTC. No SQL/API recovery, host installer
or new backup ran. That abort/denial remains historical evidence, not a PASS.

One authorized, read-only STS DecodeAuthorizationMessage call as the existing
cnp-cert-dev caller confirmed allowed=false, explicitDeny=false, zero matched
statements, all three correct trial resource tags, and
`ec2:Attribute=EnableDnsHostnames`. The template had required `enableDnsHostnames`.
StringEquals is case sensitive. The official AWS remediation policy documents
`EnableDnsSupport` and `EnableDnsHostnames` for this IAM condition. Local code now
corrects only these two values; it preserves StringEquals, the selector, exact
action, region, regional/account VPC ARN pattern and all three resource-tag limits.
No broader attribute, case-insensitive comparison or IAM permission is added.

Two regression tests first reproduced the old failures and then passed with the
correction; they compare documented/observed selector strings and reject other
attributes, old casing, missing and wildcard values. They do not simulate effective
IAM/SCP authority. No ModifyVpcAttribute retry, installation or second cloud cycle
was performed. This correction has no live acceptance evidence. The frozen packet
SHA256 `63a1e1b4870c4dbd57d51c3973f9513fc88e5e2362822878e54befb53f46d93e`
remains the original aborted-cycle evidence, not the corrected installation JSON.
A future proposed packet must be regenerated/reviewed before any installation;
do not reapply the old packet or reuse its failed plan. The runtime tar is unchanged
because authorization.py is an offline module outside that archive.

Sources: [AWS DNS condition example](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWS-SSM-RemediationAutomation-ExecutionRolePolicy.html),
[IAM StringEquals semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html#Conditions_String),
[ModifyVpcAttribute API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyVpcAttribute.html).

### Second attempt closure and local bootstrap correction - 2026-10-22

The separately approved corrected-DNS cycle created 20 objects at 01:01:19 UTC,
but both hosts failed bootstrap: the retained diagnostics show awscli installed,
SQL engine/tools absent, and only a 26-byte fixed failure marker in the bootstrap
log. No source backup, API recovery or RPO/RTO measurement ran. The suppressed
APT output and missing file-mode evidence do not establish whether repository
update, dependency resolution or installation failed. Do not label this V2 PASS.

Local diagnosis found a concrete bootstrap gap: umask 077 applied when creating
the public keyring, without a subsequent readable mode. APT requires Signed-By
keyrings readable by its _apt user. The correction explicitly sets only the public
keyring/source lists to 0644 and checks _apt readability. This fixes that gap;
it is a plausible contributor, **not an observed root cause of the cloud failure**.
See [APT Signed-By](https://manpages.debian.org/bookworm/apt/sources.list.5.en.html)
and [GnuPG keyring permissions](https://www.gnupg.org/blog/20250827-new-repository.html#check-permissions-make-sure-the-gnupg-key-is-readable).

Bootstrap now records fixed stage IDs, sanitized failure categories and original
command exit codes. It checks root/Linux/x64/Ubuntu 22.04, package architecture,
fresh SQL ownership, systemd, repository readability, package candidates/origin,
dependency simulation and installed binaries/packages/service before reading SA.
Public command output is classified in memory and discarded; it is never logged
verbatim. Secret stages suppress all command output and use only fixed codes.
The log stays 0600, tracing stays off, and SA/SQLCMDPASSWORD/probe are cleared on
failure/readiness completion. EC2-only value reads and ACCEPT_EULA/Express intent
remain; human consent does not prove completed runtime installation.

The exact normal-owner teardown first got DisassociateAddress 403; it was not
retried or granted. NAT deletion legitimately removed the association. Fresh
metadata and a full-root one-delete plan then released the unassociated EIP.
All owned runtime was absent, state serial 7 empty and lock absent before access
reversal. Both inline policies were removed and backend/CMK original hashes read
back; closure is 01:20:28 UTC. Later DescribeNatGateways and DescribeDhcpOptions
were denied, not retried or read through another principal. NAT deletion/zero ENIs
are evidenced before grant removal; the shared DHCP reference was outside all
deletion plans, but its current direct state remains UNKNOWN. Original closure
receipts are preserved; do not describe every final read as successful.

Run `python operations/sql-backup/recovery/test_bootstrap.py -v` separately from
`python -m unittest test_recovery test_authorization` in the recovery directory:
the latter installs an audit hook that prohibits subprocesses. Bash fixtures
reproduce the original silent failure and exercise the new diagnostics without
executing bootstrap_main, installing SQL, using AWS or changing a VM. They do not
prove real Linux permissions, repository availability, service setup or recovery.

No new tar is needed: bootstrap is Terraform user_data, not a bundle member.
Keep recovery-e1f8ee3.tar (d7458168...3fffa0) unchanged. Any future approved cycle
needs newly rendered/reviewed user_data, packet and complete plan; neither frozen
authorization JSON nor old plans authorize the changed bootstrap or another run.
No third cycle, IAM repair or environment installation is included in this change.

Local result: 14 Bash fixture tests, 45 recovery/authorization tests and 6 existing
retirement tests passed (65 total), plus Bash syntax and git diff checks. This is
offline contract evidence; native Ubuntu/SQL installation remains unqualified.

### Candidate repository binding correction - 2026-10-22

Review of 4323783 found that a Microsoft URL on a lower-version row could falsely
qualify a candidate from another repository. Before the parser change, two new
regression methods produced 10 failing negative subcases: the old code returned
success for foreign/missing/ambiguous candidate origins, wrong product/arch/suite,
and the same decoy for tools and the ODBC dependency. This is an offline P2, not
evidence establishing the earlier cloud install failure.

check_candidates now requires one matching package header, one Version table and
one exact candidate version block. Every repository row of that block must name
the expected product, Jammy suite and amd64 Packages index. SQL engine requires
the mssql-server-2022 repository; tools require prod. unixodbc-dev permits prod or
the explicit official Jammy archive/security/region mirror URLs in the parser.
Recognized Jammy security/update rows may coexist for the same dependency
version; an unrecognized row, duplicate row/block or missing repository metadata
refuses with 65. Installed dpkg status is not repository provenance. Lower-version
rows cannot satisfy the candidate check. No cache output or URI is logged; cache
command failure codes remain preserved. These are metadata checks, not a new
authentication mechanism or proof of available packages/dependencies.

After correction, 20 Bash fixture tests (including realistic installed/status and
Jammy security/update tables), 45 recovery/authorization tests and 6 retirement
tests pass, plus Bash syntax/diff checks. No SQL install, VM, AWS action, permission
change, third deployment or tar generation was performed. The keyring issue stays
a hypothesis about the prior failure, not an observed root cause.

### Literal bootstrap representation correction - 2026-10-22

Attempt3 stopped before apply: Terraform rejected Bash ${db:Status-Status} inside
the JSON user_data template. No runtime was created; inline/backend/CMK changes
were reversed and read back at closure 02:15:27 UTC. Approved packet 6e41c8c0...88acc
and that closure remain immutable. This local representation error is separate
from the earlier, still-undetermined native SQL installation failure.

render now escapes one Terraform template layer only in raw bootstrap text:
${ becomes $${ and %{ becomes %%{. Terraform resource/variable references elsewhere
are unchanged. Never pre-escape bootstrap or feed previously rendered text back
as raw Bash. Literal raw $${ / %%{ sequences are also preserved after evaluation,
rather than skipped or normalized. bootstrap.sh and its effect are unchanged.

Run test_terraform_templates.py separately: real Terraform1.13.4 creates a small
provider-free local output plan, never apply, with isolated temporary data and
scrubbed AWS/TF environment. Before correction two equality tests failed; after
correction all three pass, including raw-error reproduction, byte/SHA equality
for both actual host strings and dollar/percent/CRLF edge cases. This proves HCL
JSON template evaluation, not an EC2 installation, remote plan or recovery PASS.
No new tar is needed; bootstrap travels as user_data and host.py imports only
unchanged constants/require/trial from the tar's old prepare.py.

### Initial SQL start ordering correction - 2026-10-22

Attempt3-retry1 reached sql_restart on both hosts. Sanitized observations at
02:46:51 UTC and 02:51:46 UTC showed deactivating; the latter additionally showed
SubState=stop-sigterm and TimeoutStopUSec=30min. This establishes a pending stop
within restart, not a pending new start. The allowance is not elapsed duration or
root cause. Result=success/ExecMainStatus=0 and the successful observation command
do not prove restart completion or database readiness. No pre-setup/pre-restart
native state snapshot, exact package version or shutdown milestones were retained.
The code order and stage receipts prove setup, explicit start and late memory/IP
configuration completed; they do not prove that SQL had accepted queries then.

Microsoft documents [initial-setup environment variables](https://learn.microsoft.com/en-us/sql/linux/configure/environment-variables?view=sql-server-ver16)
including MSSQL_MEMORY_LIMIT_MB/MSSQL_IP_ADDRESS, and [setup followed by service
verification](https://learn.microsoft.com/en-us/sql/linux/install-upgrade/quickstart-install-ubuntu?view=sql-server-ver16&tabs=ubuntu2204).
The previous late configuration needed a restart to take effect. Bootstrap now
supplies the same 2048 MB and loopback values during initial setup, which starts
SQL; it removes the redundant explicit start and subsequent reconfiguration/restart.
After package/unit validation, sql_before_setup requires ActiveState=inactive
before reading SA. Unexpected active/transitional/failed states refuse with 65;
query failures retain their code. No service is stopped to force this precondition.
Existing EULA/Express intent, environment-only password, setup timeout and SQL
readiness/final active checks remain. No kill or unit timeout change was added.

This avoids an unnecessary bootstrap stop, but does not establish why SIGTERM
stalled. A future authorized native run must verify effective memory/loopback
configuration and query readiness. It must also validate the existing host.py
quiesce stop before restore: that required stop is unchanged and remains unproven.
For diagnosis if it stalls, capture fixed service state/job fields and UTC plus
monotonic start/stop timestamps before/after setup and quiesce, package/CU version,
and only allowlisted SQL startup/shutdown milestones/error numbers and resource
pressure indicators. Never publish raw journal/errorlog or secret values. Without
that evidence, do not attribute the stall to memory, first-start work or systemd's
30-minute allowance. No new diagnostic collector is implemented in this patch.

Three new regression methods were RED before correction (8 failed assertions and
1 missing-helper error), then GREEN. All 23 Bash fixture tests, 45 recovery/access
tests, 6 retirement tests and 3 real provider-free Terraform template tests pass
(77 total), plus Bash syntax and diff checks. Terraform verifies both hosts get
exactly the new bootstrap bytes. Fixtures/Git Bash do not qualify native Ubuntu,
SQL configuration persistence, readiness, graceful stop or recovery.

Closure 03:21:09 UTC remains CLOSED_PARTIAL_BOOTSTRAP_NO_RECOVERY. Closed receipts
and frozen packets stay unchanged. No AWS call, installation, VM, tar generation,
push or merge was performed for this correction. The existing tar does not contain
bootstrap and stays unchanged. Another cloud test needs separately approved scope,
budget/window and freshly rendered/reviewed user_data and complete plans; this
patch does not authorize it or make V2 PASS.

### Configuration verifier diagnosis correction - 2026-10-22

Attempt4 closed at 04:12:56 UTC as
CLOSED_PARTIAL_EFFECTIVE_CONFIGURATION_UNVERIFIED: both SQL engines had query-ready
markers, but the metadata verifier returned 65 twice. No backup, quiesce, restore
or RPO/RTO measurement occurred. Its exact failed field remains UNKNOWN. Original
packets, verifier, observations and closure are unchanged; that cycle is closed.

The historical sanitizer was demonstrably wrong: [A-Z_]+ discarded authored codes
with digits, omitted the stage, and could publish an arbitrary uppercase exception
message as a code. Three RED regressions reproduce these defects. A separate
22-case hermetic comparison against the immutable historical script reproduces
missing exact stages and the canary leak; corrected cases retain safe stages.
These fixtures do not identify which native field failed.

[verify_effective.py](verify_effective.py) keeps diagnostics local and read-only.
It uses fixed stage/code enums, permits digits only in authored allowlisted codes,
maps exception types without messages and emits one JSON line with no stderr/raw
command output. Read-command exits are preserved (negative signals mapped to
128+signal); validation refusals use 65, read failures 74 and read timeouts 124.
The original marker check outside Python now has a structured failure stage.
Explicit checks replace assert, so Python -O cannot disable them. Tests cover all
observation stages and branches, canaries in values/messages/stdout/stderr, child
exits/signals, selected-query formats, process/fd races and end-of-snapshot changes.

All previous strict checks remain: explicit persisted memory2048/IP127.0.0.1,
matching selected gets, no unit drop-ins, current service/process, config/start
correlation and SQL-owned IPv4 loopback1433 listeners. Selected-get parsing accepts
only the prior scalar/single-field INI forms, now rejecting extra defaults/options,
comments or arbitrary lines. Wrong value and unsupported representation have
different codes. No additional format was accepted to force success. The native
get output and exact package/CU were not retained; these formats are synthetic
compatibility fixtures, not a demonstrated native output contract.

The old EFFECTIVE_INITIAL_CONFIGURATION_OBSERVED claim was also too strong.
Microsoft documents [initial setup variables](https://learn.microsoft.com/en-us/sql/linux/configure/environment-variables?view=sql-server-ver16),
but [memory configuration guidance](https://learn.microsoft.com/en-us/sql/linux/configure/performance-best-practices-sql-server-memory?view=sql-server-ver16)
states that MSSQL_MEMORY_LIMIT_MB takes precedence over mssql.conf. The saved file,
selected get and approximate one-second boot-time correlation cannot rule out
that override. A stored readiness marker also does not prove a fresh query on the
current process. The helper therefore returns CONFIGURATION_OBSERVATION_ONLY,
MemoryRuntimePrecedenceProven=false, CurrentQueryReadinessProven=false and
RecoveryAcceptance=false, even when all observation checks succeed. Exit0 means
observations completed, never acceptance. No environment/secret read or new SQL
query was added. Missing settings or unsupported get output still refuse; neither
proves the actual setup was wrong without native evidence. Loopback proof covers
the observed SQL-owned listener on1433, not every possible SQL/network endpoint.

Run test_verify_effective.py separately from test_recovery/test_authorization,
whose audit hook forbids subprocesses. All new tests use in-memory metadata ports
or mocked OS/command adapters, including the -O subprocess. No native Linux/SQL
qualification, cloud call, installation, VM, tar, push or merge is performed.
This helper is not wired into bootstrap, the old SSM recipe or an automatic
acceptance gate. Those and frozen execution packages were not rewritten. The
fourth cycle budget authorizes no further deployment.

### Runtime precheck integration - local only, 2026-10-22

The 712c001 helper was observation-only. Current host.source and host.restore now
require the runtime adapter before DDL/API/backup/restore and before reading the
app secret. Observation exit0, missing/old source evidence, partial flags or extra
fields cannot satisfy this precondition. Quiesce/restore also require the source's
bound precheck receipt. Real IMDS documents are reduced to the four host-binding
fields for comparison; extra legitimate IMDS metadata is not mistaken for a
different host. The original expected-instance/AZ and execution acknowledgements
remain. Typed refusal preserves fixed stage/code/child exit in the host CLI.

The adapter retains every persisted memory/IP/get/listener check and adds:

1. MainPID/start ticks, SQL executable path and listener-owner process identities
   sampled before and after the probe. PID reuse, executable/start/config changes
   refuse. A child SQL process is accepted only if it owns the observed listener.
2. One fresh read-only SQL query via tcp:127.0.0.1,1433, bounded to15s, using the
   existing host-only SA environment boundary. SERVERPROPERTY(ProcessID) and this
   connection's local address/port must match the bound SQL listener process.
   No marker, old query receipt, cached result or alternate endpoint substitutes.
3. A fixed projection of the initial kernel environment at /proc/<that SQL PID>/environ. Only exact presence and
   equality of MSSQL_MEMORY_LIMIT_MB to2048 are returned; other names/values are
   never assembled into records, serialized or logged. Transient4096-byte buffers
   necessarily pass through Python RAM; zeroization is not guaranteed. Duplicate, oversized, absent, unreadable or unexpected values refuse. Linux permits
   EOF without a final NUL; a partial key/value still cannot satisfy the exact match. No
   environment variable is set and no SQL service setting/restart is performed.

RUNTIME_PRECHECK_INPUTS_BOUND correlates the initial kernel input with a fresh
query on a stable observed SQL process. InitialMemoryInputBoundToProcess is true,
but MemoryRuntimePrecedenceProven remains false: [proc_pid_environ](https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html)
does not reflect later putenv/environ changes and cannot prove internal consumption. It is a precondition, not
complete configuration consumption or recovery acceptance: receipts explicitly
keep ConfigurationConsumptionProven=false, MemoryConsumptionMeasured=false and
RecoveryAcceptance=false. No RSS, max_server_memory, allocated-memory counter or
fixture is used as proof of the platform cap. In particular, an absent variable
is not accepted just because the file says2048; that configuration path needs
separate evidence/review. This can reject a valid file-only setup conservatively.
The projection does not prove which internal SQL code consumed the input, nor
provide an atomic snapshot or a guarantee against later process changes. If
acceptance requires measured enforcement/consumption, that requirement remains
unproven and must not be called PASS by an operator reading the precheck receipt.

References: [SQL process identity](https://learn.microsoft.com/en-us/sql/t-sql/functions/serverproperty-transact-sql?view=sql-server-ver17),
[connection endpoint](https://learn.microsoft.com/en-us/sql/t-sql/functions/connectionproperty-transact-sql?view=sql-server-ver17),
[Linux proc identities](https://docs.kernel.org/filesystems/proc.html) and the memory
precedence guidance linked above. Native SQL2022/Ubuntu package compatibility of
these bindings is not established by fixtures. Unexpected native output refuses.

bundle.build now includes verify_effective.py with its manifest hash beside
host.py/prepare.py; its small deterministic bundle fixtures test inclusion. No
production tar was generated or replaced. The retained recovery-e1f8ee3.tar and
historical SSM recipes remain immutable and lack this new integration; they do
not become qualified for it merely because source tests pass. Future packaging
and execution would need separate review/authorization. No fifth packet exists.

Three integration regressions were RED before wiring source/restore and GREEN
afterwards. New fixtures exercise environment projection/canaries, query failures,
PID/start/executable/config rotation, parent/child PID ownership, strict receipt
shape and safe host diagnostics. These are local contracts, never native or AWS
evidence. Run test_verify_effective separately: test_runtime_precheck imports the
recovery suite's external-effect-denying audit hook. No AWS, installation, VM,
runtime tar, push or merge is part of this increment; attempt4 remains closed.

### File-only configured memory precondition correction - local, 2026-10-22

P2 review of0883ac6 found that requiring a PRESENT environment variable excluded
the valid file-only configuration path. This increment supersedes that refusal;
it does not infer the cause of any historical native failure.

The same strict persisted2048 and selected-get2048 checks run first. A complete,
readable initial-environment projection on the stable, fresh-query-bound SQL
process may then be either PRESENT with exactly2048 or ABSENT with no selected
value. The latter records InitialMemoryInputBoundToProcess=false and
MemoryConfigurationBasis=FILE_NO_INITIAL_ENV_OVERRIDE; the former records true
and FILE_AND_ALLOWED_INITIAL_ENV. Absence is not relabeled as an input present in
the process. Complete=true is emitted only after a full bounded stream read.
Unknown, missing/incomplete projection fields, duplicates, ambiguous partial
target keys, unexpected values or contradictions refuse. File/get disagreement,
loopback listener, fresh query and process/executable/starttime stability guards
are unchanged. Reports keep runtime precedence, internal consumption measurement
and recovery acceptance unproven; this is a configured-memory precondition.

Three new regressions were RED against0883ac6 and GREEN after correction. Fixtures
cover both permitted forms, a file-only source/quiesce/restore flow, contradictory
reports and file/get values, and unknown/incomplete projections. Native causes,
compatibility and consumption are not established by fixtures. This local change
does not alter bootstrap, historical packets/closures/tar or authorize a new AWS
cycle, VM, installation, publication or merge.

### Native selected-get CLI correction - local, 2026-10-23

The approved `r20261023az5` cycle created all20 resources and completed SQL
bootstrap on both hosts. The current artifact passed its member/hash/mode checks
on both. Source then refused at `get_memory / SELECTED_GET_FORMAT_UNSUPPORTED`
before its DDL, app-secret read, API or backup. No quiesce/restore/RPO/RTO followed.
Normal retirement deleted the owned NAT first, observed native EIP unassociation,
then applied a fresh19-delete full-root plan. Runtime/root disks/ENIs were absent,
terminal state empty and lock absent at01:59:02UTC. The two inline policies and
backend/backup-key edits were reversed/read back at02:00:33; retained originals
and2+2-day rules matched at02:05. This is a successful bounded retirement trial,
not a recovery PASS. Its immutable closure SHA256 is
`6123ba5b7d5e8aad3687d4dcabad510c928fa160dd8b4094afdb5d3721303173`.

The native diagnosis retained a70-byte stdout hash, not raw unknown output. An
offline check downloaded the exact official Microsoft `mssql-server16.0.4305.5-1`
Debian package, verified published size/SHA256
`3fbd4e3d2ad41e9abf9195b22a2dd213632ce4eeac6da3f806bc9d8f7369385a`,
and extracted public configuration source without installation or engine execution.
Its actual `initializeCommandLine`, `getSettings`, `handleGet` and `processCommands`
functions reproduced the captured bytes exactly with synthetic configuration:
`No setting for the given option found in '/var/opt/mssql/mssql.conf'.` plus LF,
SHA256 `da1b908f33cd2edc41fa90195a3ea55188a8ca1bdf2fbb4642fd6ed5823f40f1`.

There were two local contract defects. `get` takes separate section/key arguments;
the old dotted argument was interpreted as a nonexistent section and returned
that message with exit0. Correct calls are `mssql-conf get memory memorylimitmb`
and `mssql-conf get network ipaddress`. The package formatter returns one
`memorylimitmb : 2048` or `ipaddress : 127.0.0.1` line. The helper now uses those
arguments and accepts only the exact selected key, colon and expected numeric
value, with horizontal whitespace. Prior strict scalar/single-field INI forms
remain supported. Error text, wrong keys/values, multiple rows, comments and
canaries still refuse. No fallback to defaults, skipped getter or relaxed
memory/listener/PID/fresh-query/environment guard was added.

The checked-in package-derived fixture records old/correct arguments, output
bytes and provenance. Three new regressions were RED against the old helper;
72 recovery/authorization/runtime tests and27 verifier tests are now GREEN.
The full source adapter and source/quiesce/restore fixture flow use the native
argument/formatter protocol, fresh-query port and file-only memory path. These
are offline fixtures: internal memory consumption/precedence remains unproven,
and the corrected helper still needs native execution. Frozen receipts, the
closed cycle, original artifacts and budgets are unchanged; the old archive is
not qualified for this source change. No AWS call, new tar or redeployment ran
for the fix. The older attempt4 cause remains UNKNOWN.

Primary references: [exact Microsoft package](https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022/pool/main/m/mssql-server/mssql-server_16.0.4305.5-1_amd64.deb),
[official package index](https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022/dists/jammy/main/binary-amd64/Packages.gz)
and [configuration documentation](https://learn.microsoft.com/en-us/sql/linux/configure/mssql-conf?view=sql-server-ver16).
The documentation distinguishes configuration-file inspection from runtime
behavior; the package's actual CLI implementation establishes the selected-get
syntax and formatter used here.

For a subsequent authorized live cycle, the owner now permits ordinary fixes and
retests while test infrastructure remains live within its original budget/window
and protected retirement reserve. An ordinary recoverable refusal need not cause
immediate teardown. Record changed source/hash bindings and reconcile issued or
partial effects before a bounded retry; never blindly bypass STARTED markers.
Denials, uncertain effects and new security/resource/spend scope still require
their applicable disposition. This already-closed cycle is not recreated and
its clock/budget does not reset.

### Official image native qualification checkpoint - 2026-10-23

The corrected selected-get calls subsequently passed against real SQL Server
2022 Express16.0.4305.5 in the official
`mcr.microsoft.com/mssql/server:2022-CU27-GDR1-ubuntu-22.04` amd64 image, pinned to
`sha256:cf8f0ab2ebe61feec2eed2629061a07d247f791c2a8ddda74a4ac9f06a291718`.
Its three CLI/get modules matched the exact Debian package source hashes. The
image omits dpkg metadata; native SELECT established engine version and Express
edition. The old dotted call reproduced the exact70-byte error/hash; the actual
production `Verifier.selected` accepted both native21/22-byte selected lines.

One container ran at a time within3GiB/2CPU, with synthetic stdin-only password,
network none, no published ports, mounts or persistent volumes. SQL's observed
`cap_net_bind_service=ep` file capability required retaining NET_BIND_SERVICE
within the otherwise reduced Docker default capability set. No privileged mode,
SYS_ADMIN, SYS_PTRACE, daemon/builder/toolchain change or AWS call was used.

The unadapted EC2 port refused at service_state because this image has no systemd.
A separately identified direct-launch adapter supplied only the actual owned
ActiveState/MainPID/DropInPaths and a marker after real query readiness. Native
configuration/getter/process/listener observation then passed, with2048 and
loopback1433. The production host precheck still refused at
`fresh_sql_query / FRESH_QUERY_WRONG_PROCESS /65`: native kernel main PID16,
listener PID18, stable executable/start tokens. The SQL-reported PID value was
not retained, so its mismatch cause remains unresolved. No PID/query guard was
relaxed, and container adaptation does not prove EC2 systemd/drop-in/bootstrap.

Normal SIGTERM/wait cleanup removed all owned containers with no OOM. The final
local receipt SHA256 is
`1e4d599e6010cecb6b9f4dc91a6d29297307e02b4db7eac4141d992cf33a2714`.
Getter compatibility is native-proven; the full precheck, memory consumption and
cross-AZ recovery remain unqualified. No new artifact was built/qualified or
published. Resolve the process identity mismatch with bounded native evidence
before the next trial; preserve the closed AWS receipt, originals and budgets.

### Proposed kernel endpoint binding correction - offline, 2026-10-23

The recovery requirement is a fresh authenticated query on the locally configured
SQL listener/process. Numeric equality between SERVERPROPERTY(ProcessID) and a
Linux PID was an unqualified implementation assumption, not an application or
backup/restore requirement. Actual pinned SQL16.0.4305.5 Express returned380 while
the kernel main/listener PIDs were16/18 and their host namespace mappings677/693.
All recorded identities were stable. This disproves that equality in the tested
environment; it does not establish an undocumented SQLPAL translation or prove
that EC2 exhibits the same relationship.

Microsoft's [CONNECTIONPROPERTY contract](https://learn.microsoft.com/en-us/sql/t-sql/functions/connectionproperty-transact-sql?view=sql-server-ver16)
defines the server address and port targeted by that specific TCP connection.
The existing host adapter always launches a new authenticated sqlcmd connection
to tcp:127.0.0.1,1433 with a fixed read-only query. The proposed helper joins that
supported endpoint to kernel observation rather than treating SQL's process
number as a /proc path. SERVERPROPERTY(ProcessID) remains a separate diagnostic.

The proposed before/after snapshots require exactly one loopback1433 listener,
the same socket inode and exactly one descriptor owner in the current SQL
service process tree. MainPID, actual listener PID, sqlservr executable paths and
start ticks must remain stable; config time must also remain unchanged. Another
listener, a shared descriptor, missing/foreign owner, non-loopback endpoint,
new socket inode or restart refuses. The exact2048 environment projection uses
only that kernel listener PID. Reports separate KernelSqlPid/KernelSqlStartTicks,
SqlReportedProcessId and ListenerInode. Old binding shapes cannot satisfy the new
consumer contract. No PID is whitelisted or equated to a parent/child by fiat.

The captured PID regression is RED against1325f6a and GREEN with this proposal.
The PID/query/start values are native observations; fixture socket inode and
other kernel metadata remain explicitly synthetic. Ten added tests cover the
positive case, actual source adapter, wrong endpoints/process ownership,
ambiguous listeners, socket replacement and process restart/executable races.
The focused suites are82 recovery/integration plus27 verifier tests PASS.

This remains a proposed local correction, not native execution of the new
binding, EC2/systemd proof or recovery acceptance. Snapshots provide bounded
before/after observation, not an atomic or continuous process/socket attestation.
They do not establish behavior between observations or after the precheck; those
limits also applied to the earlier identity snapshots. Internal memory
consumption/precedence and RecoveryAcceptance remain false. Original receipts,
artifacts, cloud resources and budgets are untouched. No AWS/container run or
runtime artifact build/publication was performed for this proposal. One focused
native validation of the grounded contract remains before artifact qualification.


### Native kernel endpoint binding validation - 2026-10-23

The six-file endpoint/socket-owner correction above is now integrated following
one focused native test in the existing pinned official SQL16.0.4305.5 Express
image. Actual production host.Port().runtime_precheck passed, with kernel main17,
listener19/start651/inode5428 and separately reported SQL ProcessID372. The real
wrong-port1434 connection refused with fresh_sql_query/COMMAND_EXIT_NONZERO/1.
One owned SIGTERM restart changed main17/start538 to282/start1789 and a fresh
native SELECT proved the new engine ready. The in-flight precheck refused at
memory_environment/READ_FAILED/74 while retaining the old listener identity.

The raw harness incorrectly required this negative to reach the later
runtime_binding_after/PROCESS_IDENTITY_CHANGED check, so its final assertion
failed. The immutable raw receipt SHA256 is
264dcfda975d32d61aa43a723dc00648d5f301b2f78da824ac797a028c5a63eb.
A separate bounded review validated the actual required positive, wrong-endpoint
and restart-refusal evidence; evaluation SHA256 is
c61664a40aeaca1ce7ccf485b8a7bfa6a0dc712528558f19fc4b8b7177030527.
No production condition was changed to alter that outcome and no second
container was run. The extra positive-after-restart stage was not executed and
is not claimed. Normal cleanup removed the container, no OOM/forced PID action.

Only actual owned direct-launch service fields/marker adapt the container's lack
of systemd. SQL/config/getters, executable/start identities, socket inode/owner,
initial2048 environment projection and authenticated queries were native. This
does not qualify EC2 systemd/drop-ins/bootstrap, the native file-only environment
branch, API/backup/restore, memory consumption or cross-AZ recovery. Snapshot
limitations remain; no atomic/continuous attestation is claimed. Originals and
closed AWS receipts/budgets are preserved. No AWS action or budget reset occurred.


### Controlled SQL/API cross-AZ recovery and closure - 2026-10-23

The admitted r20261023az6 trial used a1e6060 and artifact SHA256
2d59ce9834deb84924cb1badfa0b3fdb4be8f7b4f99839a24844b25756a42d9a.
Both actual EC2/systemd native prechecks passed with the file-only memory input
basis, stable kernel listener ownership and separately reported SQL logical PIDs.
Source SSM appeared naturally; the separately approved one-host reboot policy
was never installed and no reboot was executed.

Two ordinary failures were reconciled live, preserving original STARTED markers,
failed receipts and exact backup/source lineage. First, mkdir(parents=True) left
/var/opt/mssql/backup owned by root0700 above mssql-owned staging directories.
The source database/login and one API marker existed, but the backup CLI could
not read its config. Only the new private parent was changed to mssql0700 on the
two owned hosts. The continuation retained the database, repeated no DDL, and
created fresh timed pre/post markers. Second, Ubuntu's Python 3.10 rejected the
actual .NET StartedUtc value 2026-10-23T04:41:29.5627332+00:00. Read-only diagnosis
proved no target database/login or restore file existed. A distinct continuation
checked event ordering at exact 100 ns precision, then adapted timestamp parsing
in memory. Sealed artifact bytes and original timestamps were unchanged.

Native backup checksum and S3 exact-version receipts passed. After source SQL
was confirmed inactive, the other AZ restored that version, passed CHECKDB,
decrypted/read the pre-backup marker, excluded the post-backup marker, and wrote
and read a new API marker. Warm-target RTO was 142.630783 seconds, including the
diagnosis pause; the controlled marker-age upper bound was 20.296562 seconds.
This proves the controlled SQL/API component drill with explicit live repairs,
not the unmodified host workflow, hourly RPO, production traffic, cold-AZ/full
ECS recovery or internal SQL memory consumption/precedence.

Retirement began immediately after proof. The owned NAT was deleted first;
native NAT-ENI absence and EIP unassociation preceded the fresh saved full-root
19-delete destroy. Native resource/root-volume/ENI absence, managed state 0 and
lock absence were confirmed at 04:48:29UTC. Exact backend/KMS originals were
restored and the two temporary inline grants removed/read back at 04:48:54UTC.
No DisassociateAddress retry, DeleteVolume, state surgery, forced PID cleanup,
EKS mutation or new budget was used. Original az5 evidence/state and original
state versions/backups/retention 2+2 days remain preserved. USD 2 is the aggregate
approved envelope, not a measured bill; the conservative combined reserve was
USD 1.95 and no budget/T0 reset occurred. New retained objects expire under the
existing asynchronous lifecycle.

The local correction now explicitly owns the private staging parent before
creating its children and refuses foreign/shared/symlink/existing-trial paths.
Timestamp parsing supports 1-7 fractional digits on Python 3.10, while event-order
comparison retains the seventh digit as integer 100 ns ticks. Duration reporting
uses a microsecond projection; malformed timestamps and reversed submicrosecond
events refuse. Seven captured/POSIX regressions and the affected contract suites
pass: Windows 89 tests (3 POSIX skips), verifier 27 separately, and all 7 focused tests
in existing Ubuntu 24.04. Early combined execution hit sandbox-temp permissions
and the suite's intentional external-process audit hook; final commands used an
owned TEMP and ran verifier separately. No installation/build/daemon change.
The checked-in correction is local-tested; it is not a newly published or native
SQL-qualified artifact. Preserve the original successful repaired trial receipts
instead of retroactively attributing this source to its immutable artifact.

Immutable closure receipt SHA256: `988d7917f9e2bf92129a7cd9ca3aad91b4b01b6591ea42aeb9019b224e5ffdbb`; closed at04:49:25UTC.
Terminal state VersionId: `JrH4aZ1_HeCozCsizjXx4LLcuNA0MWoF`, serial3, managed0.


### New artifact native local backup component - 2026-10-23

The reproducible artifact from 65c7901, SHA256
ece30607405bdaf65ea29d6396591bab7048b72b99e5d75f5cd8ea8c21846d6b,
was streamed into one isolated cached SQL 16.0.4305.5 Express container. All 623
files matched. From absent staging/database state, the unmodified create_staging
helper created the private mssql UID10001 parent/children/config without manual repair.
The exact published CLI ran local backup without --aws and returned LOCAL_VERIFIED;
native checksum verification and backup SHA256 passed. Actual manifest timestamps
2026-10-23T05:08:27.9444697+00:00 and 2026-10-23T05:08:28.1584589+00:00 were accepted
and ordered by the new helper on native Python 3.10.

With the synthetic source database OFFLINE, an explicitly manual native SQL
RESTORE WITH MOVE/CHECKSUM/STOP_ON_ERROR/RECOVERY passed CHECKDB, read the pre-backup
marker, excluded the later marker and wrote/read a new row. This was one SQL
engine and two databases, not a separate host/AZ or the production remote CLI
restore. That command requires exact remote storage; no fake S3/KMS/IMDS service
or encrypted API was introduced. Both unadapted and direct-launch service checks
refused service_state/READ_FAILED/74 in this container. The finer cause was not
captured. No guard was relaxed and the full recovery host flow did not run past
that refusal. EC2 systemd/bootstrap, credentials/remote exact-version restore,
S3/KMS/API and the unchanged full host workflow remain the acceptance gap.

The first local attempt failed in the test harness before any SQL DDL/backup:
Python 3.10 lacks hashlib.file_digest. Its immutable failed receipt is preserved;
the harness used portable streaming SHA256 for one bounded retry. Both containers
were removed through normal same-user SIGTERM, no force/OOM or daemon/security/
network changes. The existing 3 GiB / 2 CPU/network-none/no-mount bounds were retained;
EKS confirmed no WSL work and the window was released at 05:08:32.865015UTC.
No AWS calls, rebuild, new archive, upload, budget reset, push or merge occurred.
The original controlled AWS prepared-target RTO 142.630783 s remains historical
measured evidence, not a local/full-ECS/RPO claim.

Native component assessment SHA256:
0cb0065f6862059d7970bf37efcd207e5c3918b83b50425265e14e01c311e52b.
Raw successful native receipt SHA256:
6e9d0dceaa93c2574b41d34abe4d1aa62644769515cdd17462215de29eff7940.

## Cold recovery preparation — local increment, 2026-10-24

`prepare.py cold-plan` and `cold-review` extend the existing offline preparer; they have no SDK, AWS executor, secret read, apply or activation flag. They reuse the az6 Terraform generator and host timestamp/identity contracts. Existing az6 `render`/`host.py restore` remain historical two-host/cross-AZ tools; **do not pass the new single-host proposal through those old two-host retirement or host restore contracts**. The cold path is locally executable preparation/review, not a completed cloud recovery runner.

From repository root, using installed Python (replace `python` with its existing path if needed):

```text
python -I -B operations/sql-backup/recovery/prepare.py cold-plan --trial r20261024cold --input operations/sql-backup/recovery/fixtures/cold-request.synthetic.json
python -I -B operations/sql-backup/recovery/prepare.py cold-review --trial r20261024cold --input operations/sql-backup/recovery/fixtures/cold-request.synthetic.json --evidence operations/sql-backup/recovery/fixtures/cold-evidence.synthetic.json
python -I -B -m unittest discover -s operations/sql-backup/recovery -p test_cold_path.py -v
```

These checked-in examples are **synthetic**, including AMI, instance IDs, timestamps, manifests, hashes and successful checks. Never deploy them or treat their output as native proof. The response keeps `AllowsCreation=false`, `AllowsActivation=false` and `EvidenceAuthenticated=false` even when metadata is consistent. JSON validation cannot authenticate its own assertions. Replacing parameters/evidence invalidates the request binding and requires another review.

### Mode, backup, target and clock

The request binds Trial, SAME_AZ/CROSS_AZ, source incarnation/account/region, target AZ in that account, exact AMI, artifact digest, recovery request time, review time, maximum backup age and the existing versioned source receipt. SAME_AZ requires the same AZ; CROSS_AZ another one. The proposal removes the second private subnet/route-table/association/route and second instance from az6, retaining one fresh target, private SQL/loopback API, encrypted 30GiB disk, IMDSv2 and the existing network/egress design: **15 Terraform resources proposed**, not a real plan. It does not include creation of the old source, permanent HA SQL, ECS app infrastructure or IAM/backend/KMS overlays.

A selected manifest must belong to the source trial prefix and include immutable manifest/backup versions, native checksum verification metadata, ordered backup timestamps and explicit age bound. The selection uses that specific supplied receipt, not a fabricated search for the latest backup. Original source and new target trial can differ. Actual object/version/hash availability, decryptability, engine compatibility and restore remain the existing backup component's responsibility in a future native run. The 168h historical b2 bound must not become an unnoticed normal freshness policy.

`RecoveryRequestedUtc` precedes fencing and **target creation**, then bootstrap/restore/checks precede deployed API readiness. Cold RTO is request→deployed API readiness, including provision time. Review refuses a prepared target, future/out-of-order events, changed artifact/versions, missing CHECKDB/decrypted marker/read/write, stale final source observation and missing renewed ECS connections/deployed API readiness. The example's 540s is constructed test data, not a measured RTO. RPO is not inferred from manifest age; keep az6's controlled marker qualification separate.

### Fencing recommendation and hard limit

For the next disposable-data trial, recommend **terminate the exact old instance and verify terminal control-plane state**, plus a fresh write attempt against the old endpoint that is unavailable and closure of old application connections, before creating/enabling the target. Termination is irreversible and needs explicit source data/disk disposition in that trial's approval. A mere stopped SQL service, authentication error, failed network probe or unreachable AZ is insufficient. The final receipt must re-observe the same terminated incarnation after API validation and shortly before the decision (local freshness bound 15 minutes). This is evidence freshness, not a short approval cutoff; re-observation is permitted in the future plan rather than re-requesting consent by the minute.

This approach prevents that exact EC2 from resuming SQL, but a positive end-to-end no-write proof still requires authentic control-plane evidence, correctly bound endpoint/generation and known other writers/replicas. Root/SDK assertions in a user-supplied JSON are not proof. During an AZ outage, if termination cannot be confirmed, this path **halts activation**. Do not equate the outage with successful fencing. An independent durable write-authority/fencing-token design could permit another recovery strategy but is an architecture/IAM change, not implemented or silently substituted here.

### Next single trial: grouped prerequisites and retirement

Before live, close these concrete gaps as one reviewable package:

1. Bind a real source/backup/artifact/AMI/target subnet and full saved plan. Source must be disposable synthetic trial data with a valid durable backup before irreversible termination; do not terminate an ordinary database from this template. Existing source manifests/backups/keys and 2+2 retention remain preserved.
2. Adapt and test the old host restore entry point for source/new trial separation, SAME/CROSS mode and authenticated fencing evidence; wire the gate at the write-enable boundary. Add the actual collector/export of source termination/endpoint/connection evidence. No cloud executor or write-enable integration was added in this increment.
3. Bind exact `TerminateInstances` authority for the source, `DescribeInstances` readback, new target create/tag/profile/pass-role/SSM only if that route is proven, network callbacks, encrypted EBS, exact source manifest/backup GetObjectVersion and KMS decrypt, app KMS/secret metadata/value use only on the workload, and isolated backend lock/state permissions. Compare roles/boundaries/bucket/key policies and full create/read/delete callbacks before approval. No final policy hashes or permission installation exist for this proposal yet.
4. Produce a **new** cost estimate/budget for source setup plus one target, 15-resource network including NAT gateway/EIP, disk, S3/KMS/transfer, application readiness and retained storage. Count resource-hour overlap and allow 30min owner LIVE review plus cleanup reserve inside the agreed ceiling. Prior USD2/USD1 cycles are closed. No price/remaining-budget claim is made from absent billing.
5. Prepare target-specific retirement inventory/plan for 15 resources and real implicit IDs, separately from the old source and application ownership. Old `bind-retirement` expects two instances and must refuse this state until adapted explicitly. NAT own delete first, wait/reconcile then fresh complete destroy; no DisassociateAddress retry, state hacks or blind replay. Export source/target/fencing/backup/API timings before deleting synthetic runtime and reversing only this trial's overlays.
6. Announce readiness to Kendall with actual accessible LIVE API/web and honest historical diagrams; reserve the proposed 30min viewing window, then retire on schedule if he does not reply. This does not reactivate the deferred combined observability diagram or authorize new notices.

### Local validation

Seven hermetic tests PASS, covering both modes/15-resource proposal, invalid backup/age/scope/version, wrong account/AZ, stopped/unknown source/auth failure/stale fence, wrong instance/artifact/request binding, prepared target, event ordering and missing end-to-end checks. Existing `test_recovery.py`: **30 PASS**. Real isolated-Python CLI ran successfully on the synthetic fixture; an initial sibling-import failure under `-I` was corrected by temporarily resolving only the reviewed module directory, restoring sys.path afterwards. External socket/subprocess effects are prohibited by the test audit hook. No AWS, host service, SQL, provider init/schema/apply, real backup read or native fencing occurred. az6's 142.630783s and all closed artifacts/receipts remain unchanged.

## Cold host/retirement adaptation — subsequent local increment

The host restore now accepts `--cold-request <request.json>` only with action restore and the existing explicit execute/acknowledge/Linux-root/instance-role/private-path gates. No command was executed natively here. The request must bind the same source record and target AZ; the target checks STS effective role and exact EC2 source/target metadata itself. Source must be **terminated**, same launch generation/AZ; target must be running, newly launched after recovery request, correct AMI/AZ/trial. Denials/unknowns/missing IDs do not retry or fall back to a stopped-service receipt. Fence readbacks occur before restore, login creation, API start and completion; private `fence-N.json` summaries persist before subsequent steps so failure does not erase the observed boundary. This is stronger than a supplied JSON boolean, but still needs native qualification under real policies and assumes the source instance is the only old SQL writer.

The config retains the original source backup prefix while restore targets the new trial database name. Existing CHECKDB/decrypted marker/read/write checks are reused. Cold timing is `RtoColdHostSeconds`, not deployed ECS readiness; full ECS proof remains false. `bind-cold-retirement` now binds the reduced one-instance/two-subnet state and rejects the old two-instance inventory. Full saved plan and native resource-generation checks remain necessary before deletion.

[Concrete next-trial proposal](COLD-TRIAL-PROPOSAL.md) covers30 total source+target creations in two sequential15-object roots, implicit objects, proposedUSD4 incremental envelope, permissions/reversal,6h paid test+90min reserve within24h, viewing window and exact admission blockers. No budget is reset or approved by this document. The isolated topology is not represented as full Fargate/public API recovery.

Local evidence: new synthetic adapter/write-barrier/retirement suite3 PASS, cold-path suite7 PASS and existing recovery suite30 PASS. POSIX host entrypoint suite on Windows:4 SKIP, not native acceptance. All cloud/SQL responses in these tests are doubles, never a claimed real fence or AZ failure. No AWS, provider init, host installation or push occurred.
