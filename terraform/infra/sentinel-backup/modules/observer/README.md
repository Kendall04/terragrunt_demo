# Optional observer host â€” local preparation only

This module is opt-in (default OFF). It installs nothing on the laptop and creates
nothing until a separately admitted plan/apply. Lambda artifact bcac19f is unchanged.

## Why EC2 rather than WSL

| Criterion | Existing WSL with a limited session | Proposed EC2 |
| --- | --- | --- |
| Same checker/publisher identity contract | No: S3Store requires InstanceProfile credentials and exact role; publisher supports EC2 only | Yes, dedicated instance profile |
| Independent periodic observer while laptop sleeps/disconnects | No | Yes, installed systemd timer |
| Actual SSM command/retirement proof | No | Yes, own Command document |
| Credential transfer | Would require a NEW reviewed session-delivery/credential path | IMDSv2; no copied credentials |
| What is already locally proven | POSIX tests, native checker build-info and receipt replay | Module/provider/mock plans; native EC2 still unproven |

Do not impersonate an instance profile in WSL or copy Windows credentials. WSL remains
useful for local code tests; it is not equivalent acceptance. A Lambda rewrite of the
checker/publisher credential/process contract is unnecessary for this increment.

## Implemented ownership and inventory

14 new Terraform addresses, single observer module: VPC/IGW/subnet/route table/route/
association/SG7; boundary/role/inline/profile4; instance1; versioned host-code object1;
restricted SSM Command document1. Base pipeline26, scheduled pipeline29, full43.
Only the distribution object is added to the pipeline's existing versioned bucket;
that module continues to own the bucket/policy. No second bucket, CloudFormation,
NAT, SQL, new CMK, business API, persistent CA or EKS dependency.

Indirect dependencies: root EBS, primary ENI/public IPv4 and default VPC objects;
SSM service metadata persists according to AWS behavior. Inventory them separately.
Do not call DeregisterManagedInstance for EC2 i-* IDs: the documented API accepts
activation-managed mi-* / eks_c:* identities, not these EC2 nodes. Wait/read back the
native terminated host/volume/ENI and report any stale SSM row honestly, not as a
billable instance or a deleted row. No DeleteVolume/PID force cleanup workaround.

Official AL2023 standard x86 AMI is pinned by ID (no latest lookup in Terraform),
owner amazon/name/architecture/EBS/HVM/available filters. AL2023 ships AWS CLI v2 and
Python3, and official standard AMIs have SSM; bootstrap checks them, never installs
or upgrades packages. Canonical root KMS ARN must resolve to KeyManager AWS; this
avoids inheriting an unknown account-default customer CMK. Neither new identity has
been read from AWS yet. Data-source reads are mandatory future plan checks.

t3.micro STANDARD avoids surplus CPU charges, encrypted8GiB gp3 deletes on termination,
IMDSv2/hop1, no keypair/ingress, one ephemeral public IPv4. HTTPS egress0.0.0.0/0 can
reach the Internet, not only AWS; DNS uses VPC resolver. This is an explicit risk and
cost tradeoff versus NAT/endpoints, not a private-only host. SSM runs root controls.

## Immutable distribution and runtime

observer_host.py build first verifies every original b2bf8d8 component byte against
its previously qualified manifest; excludes symbols only, keeps checker dependencies
and self-contained10.0.13 runtime. Adds the actual observer/publisher and bounded host
control. No SDK rebuild/download, SQL server or credentials. Gzip/tar entries use
fixed metadata, strict inventory/hash/path/symlink/size checks. One compressed bundle
is sufficient; the old301MB recovery tar is neither copied nor reused as qualification.

Terraform owns its content-addressed object/version/hash and EC2 userdata. Bootstrap
fetches ONLY that version using IMDS-role AWS CLI, verifies the archive before executing
the installer, installs dedicated user/private state and verifies native build-info.
No raw CLI stderr, password/token, shell tracing or credential file is logged/copied.
The timer is installed INERT. Operator starts it only after native SNS confirmation.
Changing userdata intentionally replaces this disposable host; no ignore_changes or
competing code updater exists. Runtime start/stop/mode is operator-owned, not Terraform.

SSM document accepts only status/evidence/start/stop/once/healthy/missing/stale/fail;
there is no arbitrary shell parameter or Session Manager shell grant. Each observation
mode has its own durable local spool/state. A mode switch stops the timer, waits for
known-idle own service/cgroup and refuses ANY pending delivery; no discard/force kill.
It runs the real checker without publishing first and refuses a mismatched status.
healthy reads original manifests with explicit test max age; stale uses1h, missing
uses a distinct empty own prefix, fail writes a clearly synthetic local attempt in
own state only. Original S3 objects/config/backups are never changed by host controls.
No branch asserts SQL restore or fabricates NativeChecksumVerified/date/version fields.
The evidence action exports own state/spool hashes and attempt counts, not raw payload,
not a drain certificate. Pending synthetic payload retirement requires explicit consent.

## Permissions, admission and retirement

Boundary equals host inline policy: exact ingress SendMessage; immutable code-version
GetObjectVersion; prefix-restricted original ListBucket and manifest-only Get/GetVersion;
one existing backup-key Decrypt via S3/object context (no text-key decrypt); own Command
document Get/Describe. SSM heartbeat is restricted to own Trial-tagged EC2; ssmmessages
channel APIs require regional Resource* and expiry. No EC2/NAT/IAM/SNS/Dynamo/secret
actions. Bucket policy denies this role ALL other resources and ALL actions except
GetObjectVersion on the one distribution object. No list/latest/mutation exception.
These are source contracts, not a native IAM simulation or promise of current access.

READONLY-PREFLIGHT.json identifies new coordinated reads; required-capabilities.json
lists lifecycle action/target contracts. Compare them with actual operator policies to
grant only the missing delta. Do not attach a broad duplicate Allow, widen a Deny after
failure or switch principals. Admin prepares/reverses reviewed scope; intended operator
executes the same saved plan. IAM management of own3 role/boundary documents is an
access capability to disclose; resource-name scope alone does not freeze policy content.
PassRole is only own2 Lambda roles to Lambda and observer role to EC2. No CF role.

No new USD allowance/recipient is assumed. Proposed full trial remains newUSD2,
target2h/ceiling24h and cleanup reserve; two notices, max3 attempts each, <=20 external
observations, original2+2days unchanged. A NEW SNS subscription needs owner confirmation.
Use a single continuous incident for watchdog/negative modes, then real later healthy
checks for recovery. Active unsupported probes stay Pending without a provider;
obsolete closed-episode work may CAS-cancel. Report each status; never claim historical
outbox drainage or fabricate a successful read-probe.

Stop timer, verify service idle; disable rule/mapping, export native incident/outbox/
archive/cursor evidence and host hashes. Review saved destroy with same backend lineage.
Export/delete ONLY owned code/archive versions; no force_destroy. Remove host, wait for
embedded disk/ENI/IP release; Terraform removes network, document, roles/profile/boundaries,
Lambdas/mapping/topic/queues/logs/table/bucket as admitted. Restore separately reviewed
operator/backend/KMS/original-bucket exceptions and policy contents/version history.
Keep terminal state and both native/local evidence. Any residual SSM metadata is explicit.

## Actual qualification / limits

Windows and existing WSL: archive/source/scope/state/control tests PASS. Native checker
build-info under WSL with invariant-globalization matches b2bf8d8; this is not AL2023
execution or authenticated S3 proof. Terraform6.27 schema validate and two native
mock-provider plans PASS, including opt-out and host distribution deny contracts.
Mock fixture text is explicitly NOT a deployable ZIP/tar. No backend initialized,
AWS calls, role assumption, credential transfer, installed timer, email, remote CI/push.
Still required: coordinated AMI/EBS/source retention/policy reads, actual saved plan,
effective create/delete access, native AL2023 bootstrap/SSM/checker/SQS and final teardown.

Official sources:
- https://docs.aws.amazon.com/linux/al2023/ug/awscli2.html
- https://docs.aws.amazon.com/linux/al2023/ug/python.html
- https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html
- https://docs.aws.amazon.com/service-authorization/latest/reference/list_ssm.html
- https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-setting-up.html
- https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_DeregisterManagedInstance.html
