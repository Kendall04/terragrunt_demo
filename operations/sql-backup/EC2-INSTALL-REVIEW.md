# EC2 SQL backup installation review - 2026-10-16

Status: PREPARED, NOT AUTHORIZED OR INSTALLED. This is the next ECS-track SQL
backup component, following local service commit b036141. Source preparation,
local fixtures and AWS read-only inventory are authorized. Owner approval of this
concrete scope is required before any runtime apply, IAM/KMS/bucket/network change,
SQL login/credential creation or real host installation. No push/merge is included.

## Current inventory and minimum topology

Windows profile cnp-cert-dev verified account 341936017254, region us-east-1 and
human cnp-cert-admin. Read-only inventory found no EC2 instances, SSM managed
instances, original DEV VPC, ASGs, ECS clusters or S3 VPC endpoint. Only the default
VPC exists; it must not be adopted. There is no SQL host or installed timer.
The retained SQL role/profile and AmazonSSMManagedInstanceCore attachment exist.
Its existing wp2d-dev_sql policy reads the two original DB secrets and decrypts
with the original text key; this preparation changes neither that policy nor trust.

Activate only the original global/data stages needed for this component, through
existing E16 reviewed saved plans and separately administered NAT/E13 setup:
the same two-AZ VPC, four subnets, two original NAT slots/EIPs, internal ALB and
private SQL EC2. Keep SQL on t3a.small/30-GiB encrypted gp3, IMDSv2 required, no
public IP or inbound SSH, no new SQL ingress. Preserve both NAT slots and E13
default-route ownership. Do not create a reduced VPC, public SQL or NAT Gateway.
Platform/apps/edge source remains unchanged; this component needs no Fargate
task/image delivery, API publication or Cognito. This is partial staged runtime
activation, never a claim that complete DEV or the .NET app is qualified.

The SQL name is demo-dev-data-sql-instance. Existing profile is
arn:aws:iam::341936017254:instance-profile/demo-dev-data-sql-ec2-profile and role
arn:aws:iam::341936017254:role/demo-dev-data-sql-ec2-role. No current instance,
subnet, route table, endpoint or SSM command ID can be supplied: they do not exist.
Bind their real readbacks and tags after original plan creation; never reuse old
IDs or authorize an invented saved plan. The observed Canonical Ubuntu 22.04
x86-64 AMI candidate is ami-09db1e291cef3f1ef, owner 099720109477, dated 2026-10-14;
it is a candidate, not an installed or qualified image selection.

## Exact retained storage and security changes to approve together

| Item | Proposed change |
| --- | --- |
| Bucket terragrunt-demo-sql-backup-341936017254-fa48a32dc9 | Reuse; no new bucket |
| Data prefix terragrunt-demo/dev/sql-backups/ec2-20261016/ | New operational scope; no writes into lab-fa48a32dc9/ |
| Backup CMK arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced | Append only producer, artifact-reader and temporary human artifact-publisher use statements |
| Existing text CMK arn:aws:kms:us-east-1:341936017254:key/50d3fe36-8128-4d09-ac13-8f5536a230a7 | Preserve policy and key; no new grant |
| Existing SQL role | New temporary inline policy sql-backup-ec2-20261016; preserve wp2d-dev_sql/trust/SSM attachment |
| Bucket policy | Append exact new-prefix/artifact denies for wrong/missing SSE-KMS key and nonconditional writes; preserve existing TLS and historical-prefix statements |
| Lifecycle | Append ec2-hourly-two-plus-two for new data prefix and ec2-artifact-one-day for exact new artifact key; preserve old lab rule |
| S3 gateway endpoint demo-dev-sql-backup-s3 | One new Gateway endpoint on the two actual original private route tables; no paid interface endpoint |

Producer policy permits only PutObject/GetObject/GetObjectVersion in the new data
prefix and GetObjectVersion for the one digest-addressed installation artifact.
KMS use is restricted through s3.us-east-1.amazonaws.com and the corresponding
S3 encryption contexts; bucket keys stay disabled so those contexts remain exact.
It grants no ListBucket, DeleteObject, state access, PassRole, KMS administration,
new secret access or application text decrypt. The original SQL role already has
SA bootstrap access; this is an existing privilege, not a backup-only host identity.

The artifact key is
terragrunt-demo/dev/sql-backup-artifacts/ec2-20261016/<reviewed-package-sha256>/SqlBackup.tar.
After approval, the human conditionally uploads it with the same CMK, hashes and
records the returned VersionId, performs exact-version readback, then removes the
temporary human key-use statement. On EC2, download only that VersionId, check the
independently reviewed SHA-256, and run the package inspector before installation.
No AWS session, SQL password, .aws directory or Windows CA bundle goes to Linux.

The Gateway endpoint's standard allow policy preserves existing IAM-authorized
S3 traffic, including other original architecture dependencies; it is not an IAM
grant. Its route insertion is limited to the AWS S3 prefix list on the two private
tables, never 0.0.0.0/0 or the E13 NAT routes. STS, SSM and the existing SA-secret
read continue over the original NAT egress. No public/bastion/22/1433 rule is added.
The generated endpoint .tf.json is an administrator review candidate outside the
ordinary/protected Terraform roots. It is not admitted by E1 or authorized for
apply. Either administer this temporary endpoint with exact readback/ownership
evidence after approval, or complete separate source admission before using it
inside Terraform; an inventory refresh is not admission.

## SQL credentials and host changes

`ec2_credentials.py` plans by default and does not call AWS or SQL in plan mode.
Real provisioning requires root, the reviewed approval-file SHA-256 acknowledgement,
the matching package-install receipt/config and the exact instance-role STS
identity. Its AWS subprocess ignores ambient profiles/tokens/files and uses IMDS;
the host enforces IMDSv2. It uses the already permitted SA secret
demo/dev/db/sql-sa-password-30fCjc only in process memory. It never prints child
diagnostics containing SQL input, places passwords in argv, or invokes systemctl.

It creates td_backup_dev in demodb with db_backupoperator and td_verify_dev in
master with CREATE DATABASE. Neither gets sysadmin/dbcreator or source SELECT;
the application login is unchanged. Random passwords are generated on EC2.
Connection files backup-connection and verify-connection persist root:root 0600
under /etc/terragrunt-demo/sql-backup/credentials, directory 0700, on encrypted EBS.
They are plaintext files readable by root, survive reboot, and disappear with the
approved disposable root disk; they are not Secrets Manager secrets. This explicit
lab storage choice avoids two new paid secrets and extra retrieval grants.
systemd LoadCredential copies them into the service's private runtime credentials.
No secret value enters Terraform, SSM command text, evidence or Git. Existing
logins/credentials and uncertain partial provisioning are refused, never silently
adopted/rotated; retain the private receipt and review before repair.

The reviewed package installs root-owned /opt/terragrunt-demo/sql-backup, public
config root:SQL-group 0640, inert units under /etc/systemd/system and SQL-user-owned
0700 /var/opt/mssql/backup/v2. The bootstrap adds root-owned
sql-backup.service.d/credentials.conf plus the credential files/receipt. Python 3,
existing AWS CLI and sqlcmd18, compatible ICU/OpenSSL and systemd are prerequisites;
no permanent .NET SDK is needed. Existing Ubuntu awscli v1/v2 are supported by
the bootstrap commands. All real file/ownership/login/daemon-reload/manual-start/
timer-enable changes are pending this grouped approval.

## Finite qualification and four-hour window

1. Reconcile original E2/E13/lifecycle and actual saved plans before runtime apply.
   Confirm expected DEV tags, approved AMI, encrypted EBS, private addressing,
   instance role and SSM reachability; bind actual VPC/two-private-table IDs.
2. Re-read the retained policies and compare their hashes with the reviewed before
   documents. Install only the named admin overlay and endpoint after approval;
   do not overwrite concurrent edits or edit the original text-key policy.
3. Publish/read back the exact artifact version; remove temporary publisher use.
   Use SSM with public command text only to download/verify/stage it on SQL EC2.
   Install config, provision the two local SQL credentials, validate actual units
   and daemon-reload. Do not start a timer before SQL readiness and manual success.
4. Manually start sql-backup.service once. Require REMOTE_VERIFIED plus cleanup
   success, actual instance-role/account proof and an immutable receipt with both
   S3 VersionIds, native checksum, bytes and SHA-256. Source `.bak` alone fails.
5. Enable/start the hourly timer. Observe two distinct real OnCalendar hourly
   activations and three total commits (one manual plus two timer), recording UTC
   activation timestamps/journal outcomes and exact S3 versions/hash readback.
   Do not replace them with accelerated/manual invocations. At most three
   <=512-MiB backups, about 1.5 GiB plus the artifact, are planned.
6. Stop scheduling after the second timer success or at the four-hour deadline.
   Disable/stop the timer, inhibit the wrapper and wait for the whole job to become
   idle; never kill an active backup or mistake UNKNOWN for remote cancellation.
   Export sanitized receipts/version/hash evidence. No final ceremonial backup is
   required for the owner's empty disposable lab data. No HA, external observer,
   cross-AZ restore or full-app acceptance is added to this session.

The four-hour limit is supervised, not an installed spending cap or automatic
TTL. If bootstrap/readback cannot pass in the window, stop and retain evidence;
do not extend compute, create paid endpoints, broaden policies or loop on minor
warnings. A real role/provider denial or unready SQL is a material failure.

## Cost and retirement package

AWS Pricing GetProducts read-only quotes confirmed us-east-1 Linux shared
t3a.small USD 0.0188/hour and t3.micro USD 0.0104/hour. Four hours of one SQL plus
two original NAT instances is USD 0.1584. The packet includes USD 0.04 for two
public NAT IPv4s, USD 0.122 for internal ALB plus one LCU, USD 0.0276 EBS allowance
(62 GiB gp3/4h; reprice actual saved-plan disks), and USD 0.50 logs/alarms/request
contingency. It also carries the previous retained-component first-month ceiling
USD 1.2574, the existing text-key month USD 1 and three existing secrets USD 1.20.
Conservative first-month planning total: USD 4.3054 before taxes, rounded to USD 5.
No new CMK, bucket, secret, Fargate workload or paid endpoint is proposed.

This uses the previous shared ECS limit of USD 10, not another USD 10 and not a
claim that USD 10 remains. Earlier runtime spend, unrelated EKS costs, billing
delay, taxes or retained resources beyond these assumptions must be reconciled;
price quotes do not prove account charges or remaining budget. Do not silently
increase the ceiling. Rates/assumptions are in approval.json and its source
snapshot; [IPv4/Gateway](https://aws.amazon.com/vpc/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[EBS](https://aws.amazon.com/ebs/pricing/), [KMS](https://aws.amazon.com/kms/pricing/)
and [existing secrets](https://aws.amazon.com/secrets-manager/pricing/) support the
allowances. Both retained CMKs continue their approximate USD-1/month base each;
three existing secrets remain approximately USD 1.20/month plus usage.

After local idleness and evidence export, remove only the owned SQL users/logins,
new credential files/drop-in and named role inline policy; remove the two remaining
new EC2 key-use Sids, preserving current administrator/other statements. Remove
only the owned endpoint by its recorded ID before original global DOWN. Retire
the newly activated global/data runtime using existing supervised E16 plans,
including disposable SQL/EBS, both NAT ASGs/EIPs and internal ALB. This runtime
retirement and synthetic SQL loss belong in the same approval scope. Do not delete
retained bucket, keys, historical versions, existing roles or original secrets.
Keep the new prefix's encryption/conditional denies and agreed 2+2 expiry; artifact
expiry is one day plus noncurrent one day, eventual. Old lab retention is unchanged.

## Reproduce the preparation without installation

Run `ec2_snapshot.py --output <new-external-snapshot.json>` on Windows with the
existing named profile. Its API list is fixed to public metadata/pricing and
contains no GetSecretValue, state download or mutation. Then build the reviewed
Linux package and run `ec2_prepare.py --snapshot <snapshot> --package <tar>
--expected-sha256 <reviewed-hash> --output <new-external-review-directory>`.
The output contains approval/config and exact before/after policy/lifecycle JSON,
hashes and explicit absent-runtime blockers. Optional --network requires a freshly
observed nondefault project VPC and two distinct private table IDs; it does not
claim those IDs or a Terraform root are installed/admitted. Default-VPC adoption,
wrong account/key/package, overwrite and an estimate above USD 5 are refused.

Before any approved credential action, `ec2_credentials.py --approval <approval>
--config <config>` gives a no-access/no-write plan. The --apply and
--confirm-secret-bootstrap <approval-sha256> flags are deliberately not exercised
on a real host in this preparation. They do not independently authorize execution.

The isolated suite covers review preservation/scope, default VPC rejection,
budget re-estimation, fixture provisioning/permissions, failed bootstrap receipt,
wrong-role refusal, SQL input validation and default no-access behavior. The
native SQL permission proof from b036141 remains separate. Live Access Analyzer
checked the proposed identity/bucket/key documents without installing them: zero
errors/security warnings; generic wildcard warnings refer to the intentional
literal '*' in exact s3:if-none-match conditions. Keep StringEquals/StringNotEquals;
StringLike would change that exact conditional-write contract. EC2, native host
bootstrap and the two real timer activations remain unexecuted.
