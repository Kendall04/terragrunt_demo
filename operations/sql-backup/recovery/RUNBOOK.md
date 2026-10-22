# V2 SQL/API cross-AZ recovery packet

Status: **LOCAL PREPARATION ONLY**. V1 delivery remains accepted. The October 21
manual/two-hourly backup acceptance is historical PASS; no recovery or cloud
lifecycle PASS follows from these files, generated JSON or offline fixtures.

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
