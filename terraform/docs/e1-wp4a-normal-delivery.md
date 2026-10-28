# E1 WP4A — closed normal-delivery authorization

WP4A is a repository-level, provider-free authorization contract. It neither
registers a task definition nor changes a service or listener. [E1 spec](../../specs/iam-hardening/spec.md),
[E1 plan](../../specs/iam-hardening/plan.md) and [E3](../../specs/deployment-readiness-promotion/spec.md)
remain authoritative. WP3 production schemas/code remain unchanged.

## Protected reads and caller boundary

The endpoint is installed as `deploy-dev` or `promote-prod`; the caller cannot
choose an environment. Input JSON contains only `release_id`, bounded `replicas`
(1–100, further bounded by installed config), and optional short `reason`.
Unknown/duplicate fields, authority booleans and caller AWS parameters reject.

`scripts/normal_delivery/authorization.py` takes a read-only `Facts` port. Its
production adapter in later WP4B/D **must** authenticate namespaces and storage
versions. Object `writer` and `schema` strings alone are consistency checks:

- Qualification is exact finalizer-owned canonical bytes, keyed by release ID;
  release ID is recomputed from qualification content.
- Manifest is an exact bucket/key/VersionId read with byte checksum, schema,
  source, repository and digest agreement.
- Eligibility is the **current** admin-owned read, not a version chosen by the
  caller or historical record. Its storage VersionId must equal the canonical
  `E1_ELIGIBILITY_V1` content VersionId and state must be `ELIGIBLE`.
- Artifact availability is an exact authoritative repository/digest lookup. A
  mutable tag or arbitrary image URI cannot satisfy it.
- Configuration is a protected endpoint-only current read. It binds account,
  region, color, task/execution role positions, secret ARN, KMS ARN, logs,
  cluster/service, network, target group and routing. Installed bootstrap
  evidence must show count zero and an inert definition without workload roles
  or secrets.
- Prod requires a protected successful dev receipt for the exact release,
  source, image URI, manifest VersionId/checksum, qualification checksum and
  runtime, plus a distinct protected prod approval context. This defines
  internal facts to be produced/authenticated later, not WP6 request acquisition.

The current Fargate skeleton defaults to ECS Exec enabled and uses a bootstrap
definition with workload roles/secrets. An installed binding mirroring that
state is rejected. WP4A does not modify WP5-owned lifecycle to hide this gap.

## Runtime and readback

The executable [closed field model](../../ci/authority/normal-delivery-model.json)
classifies the repository-supported task/container/service vocabulary from
`runtime-fields.json`, the renderer template and service skeleton. It is a
bounded local model, not a claim to reproduce every AWS ECS API version. Unknown
request or nested response fields reject. The model is checked against the
reviewed local field vocabulary; any additional AWS field requires a reviewed
contract update before use.

One deterministic intent contains the exact task definition, intended service
bindings/count, routing IDs and hashes/versions of protected facts. Both app and
probe use the same qualified `repository@sha256:digest`. The app has no command
or entrypoint override; the probe command is exactly `readiness-probe`.
Task/execution roles occupy distinct protected fields. Environment, secret and
awslogs fields come only from installed configuration. ECS Exec is false.

`validate_registration_readback` accepts a normalized authoritative task
registration response, recognizes explicit return-only fields/defaults and
compares every execution field before WP4B may start a candidate. It reports
the exact returned ARN/revision, never a readiness/activation permission.
`validate_readback` additionally compares a normalized service snapshot to
the intended cluster/service/revision/count and closed service settings. The
adapter may normalize only listed harmless response defaults. It must not copy
unknown response fields into another request.

WP4B must bind an accepted registration result to its protected operation,
independently observe the service and run the accepted E3 gate before the normal
listener switch. A WP4A intent or task readback never authorizes activation.

## Acceptance and limits

Run `python -I -B scripts/tests/normal_delivery/run.py`. It uses protected-port
fixtures and the repository's hermetic I/O guard. Positive dev/prod and exact
readback controls, current eligibility, WP3 binding, nested field attacks and
four behavioral field-guard mutants are covered. Fixtures are not live AWS
evidence. IAM, service trust, compute and request identities remain unchanged.

WP4B owns delivery state machine and E3 orchestration; WP4C owns emergency,
cleanup and NAT; WP4D owns exact authority/materialization. WP5 owns lifecycle,
WP6 request cutover, WP7 legacy retirement. Current/live platform gaps remain
unverified as documented in [validation](validation.md).

## V2 correction � independent membership and executable model

V1 remains checkpoint `9cc59275d64ecd675aa7bb5d24e328c761becff7`.
V2 changes only the offline authorization contract, its model and fixtures.

`Facts.membership(environment)` reads a separate CURRENT admin-owned resource
universe. It must not synthesize membership from the configuration being checked.
The existing installed-bundle consumer references do not contain this resource
universe; this port defines its future adapter obligation without live discovery.
The authenticated envelope contains environment, observed storage VersionId and
canonical bytes. The closed record is `E1_ENVIRONMENT_RESOURCES_V1`, writer
`SECURITY_ADMIN`, exact environment/account/region and exactly blue/green maps.
Each map contains exact task/execution roles, secret ARN, KMS key ARN, log group,
cluster, service, subnet set, security-group set, target group, listener and
candidate rule. Semantic positions remain distinct. Network lists are nonempty,
unique and compared as sets by sorting; additional resources are not admitted.
Sharing between colors is allowed where explicitly installed (for example KMS);
cross-environment ownership must be authenticated by the independent admin port.
Names, tags and ARN shapes do not establish membership. The caller has no
membership input. The intent binds membership bytes by hash and storage version;
readback reauthorization re-reads them. Publication/ownership enforcement is
deferred to protected installation, not added as AWS authority here.

The model's `canonical_task` is the executable recursive contract: literal
values define constants, and `$binding` leaves identify exact semantic positions.
One resolver and strict recursive comparator validate both stages. Before
construction, the template must equal the model with empty placeholder values.
After construction, and before emitting an intent, the task must equal that same
model resolved from qualified image identity and validated protected bindings.
Unknown fields, types, list cardinality and absent-by-contract fields reject.
The template cannot change this vocabulary or legitimize itself through readback.
Existing normalized readback comparison remains mandatory and unchanged.

The 20-test suite includes both directions of KMS/subnet/security-group
substitution, malformed/wrong-environment membership, role-position ambiguity,
caller membership injection, 15 incompatible template cases and independent
post-construction corruption. Two additional behavioral guard mutants demonstrate
that bypassing membership or model validation admits the corresponding attack;
unchanged controls reject them and valid dev/prod/readback controls still pass.
All fixtures are synthetic protected-port evidence, not deployed resources.
