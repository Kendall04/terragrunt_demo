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

Generated `security-additions.json` proposes exact new trial-prefix object access,
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
   broadly installed operator policy is supplied or certified by this local packet.
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
