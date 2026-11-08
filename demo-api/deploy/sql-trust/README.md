# Common image: environment-supplied SQL trust

The ordinary API requires `validated-v2`. The common `demo-api/Dockerfile`
contains no laboratory SQL certificate. Its entrypoint prepares public trust as
UID 1654, then replaces itself with the API process. No third ECS container,
init dependency, download, root privilege or system trust-store write is required.

The packaged `readiness-probe` command, including `--check-capability`, bypasses
SQL configuration entirely. It still calls loopback `/ready`; only the API
connects to SQL. `database-migrate --confirm-schema-change` uses the same trust
bootstrap but requires its separate `DB_MIGRATION_CONN_STRING`. It starts neither
HTTP nor KMS and never falls back to runtime credentials.

## Public configuration contract

The renderer accepts `--database-config` and `--sql-trust-manifest` for **ordinary
DEV or PROD**, independently of `--recovery`. An identity file has exactly:

```json
{
  "schema": "SQL_RUNTIME_IDENTITY_V1",
  "environment": "dev",
  "profile": "validated-v2",
  "endpoint": "tcp:sql.example.test,1433",
  "database": "demodb",
  "runtime_user": "app_runtime",
  "certificate_hostname": "sql.example.test"
}
```

These are illustrative identities, not deployed DEV/PROD configuration. A trust
manifest has exactly the following fields (one to three public anchors):

```json
{
  "schema": "SQL_TLS_TRUST_V1",
  "environment": "dev",
  "version": "reviewed-trust-v1",
  "hostname": "sql.example.test",
  "anchors": [{
    "kind": "ca",
    "sha256": "<SHA256 of the exact DER certificate>",
    "der_base64": "<base64 of that public DER certificate>"
  }]
}
```

The renderer puts the exact manifest bytes in `SQL_TRUST_MANIFEST_B64` and their
SHA256 in `SQL_TRUST_MANIFEST_SHA256`, only on the API container. The entrypoint
checks both, rejects duplicate/unknown fields, verifies each DER digest, X.509
encoding, validity, CA/keyCertSign and self-signature. It requires the manifest
hostname and environment to match the deployment configuration. The application
separately validates endpoint, database, runtime identity and explicit
`Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=...` before its
real read-only permission query and before accepting HTTP traffic.

Example **local rendering only**, using separately reviewed public files:

```sh
scripts/render-demo-api-taskdef.sh --env dev --region us-east-1 \
  --account-id "$ACCOUNT" --color green --image-uri "$IMAGE_BY_DIGEST" \
  --db-secret-id "$VERSIONED_RUNTIME_SECRET_ARN" --kms-key-id "$KMS_KEY_ARN" \
  --environment-binding /private/authenticated-current-environment-binding.json \
  --database-config /private/reviewed-identity.json \
  --sql-trust-manifest /private/reviewed-public-trust.json --output /tmp/task.json
```

There are still exactly two containers, the same image on both, empty
`dependsOn`, and no SQL environment variables/secrets on the probe. Ordinary
configuration requires an exact Secrets Manager version reference and key ARN.
It also requires an independent current administrative `E1_DELIVERY_BINDING_V1`
readback via `--environment-binding`, validated with the existing
`scripts/normal_delivery/authorization.py` contract. The unversioned secret ARN
must equal that binding's `secret_arn`, including its exact generated suffix,
destination environment, account and region; the candidate retains its explicit
version selector. Neither a DEV ARN in PROD nor another same-env ARN is admitted.
The binding must come from the protected administrative configuration, not from
`--db-secret-id` or the public database identity document. This offline renderer
cannot authenticate a file's transport: a caller able to replace the binding can
change authority. Admission/provenance remains the administrative owner's job.
No real PROD binding is supplied here; without its authenticated publication,
ordinary PROD rendering remains blocked. Test fixtures are not deployment approval.
The historical `--recovery` plan format remains available for historical images;
it does not supply the new common image's required manifest and cannot bypass
its startup checks. Existing pipelines are unchanged and need a later explicit
integration of the new ordinary inputs.

## Trust boundary and provenance

The process-specific bundle combines Linux's public HTTPS roots with only the
environment's supplied private roots. `SSL_CERT_FILE`, an empty root-owned
`SSL_CERT_DIR`, and a new private HOME are set **before the API .NET process**.
Files are private to UID 1654 in ephemeral `/tmp`; `/app` and the system bundle
remain root-owned. No root count is part of the contract.

This preserves the public-root basis for AWS HTTPS. It proves environment
separation when the approved PROD configuration excludes DEV roots; it does
**not** promise that only the private PROD CA can authenticate SQL. A publicly
trusted, otherwise valid certificate for the expected hostname is also trusted.
Real Fargate/KMS connectivity remains a separate acceptance test.

Hashes detect corruption/substitution against the admitted configuration; they
are **not signatures or independent approval**. Someone who can replace both
manifest and hash can change trust. The future deployment owner must admit the
version/hash and environment binding, restrict task-definition registration and
deployment inputs, and preserve the exact public manifest with rollback evidence.
DEV operators must not have authority to modify PROD trust or sign with its CA.
No issuer key, connection value, AWS credential or real CA is created here.

## Bounded DEV bridge (prepared, not installed)

Only DEV may add `kind: "dev-leaf-transition"` with the exact public leaf DER
SHA256 `206095fa0ba9e17a84c80eff5021db93d05e2dc377e982a64d517696ed21a1e7`.
It must retain `CA:FALSE`, validate for `sql.demo.internal`, and accompany at
least one valid root CA. A manifest `transition` object is then required with
UTC `not_before` and `not_after` in `yyyy-MM-ddTHH:mm:ssZ` format. Maximum window:
seven days, never beyond the leaf expiry `2026-12-04T20:09:56Z`. PROD rejects
this schema. The API refuses admission after expiry and stops a running bridge
at its deadline; middleware rejects new HTTP requests during shutdown.

Future supervised transition, **not executed by these changes**:

1. Prepare bridge B's immutable image, public DEV manifest (old leaf + new DEV
   root), exact identity and runtime secret version. Verify B against the old SQL
   certificate with fresh connections and actual readiness/KMS before promotion.
2. Keep B as the known revision and preserve its complete task/config identity.
   Prepare a separately reviewed SQL rotation/rollback procedure; the original
   installer rejects existing TLS directories and is not a rotation tool.
3. Rotate SQL's certificate in a controlled window. **Before testing/promoting a
   later green**, open new physical SQL connections from B against the new leaf
   and check readiness/KMS. Only then is B eligible for rollback after rotation.
4. If later green fails, return to that exact B revision + manifest + secret
   version, whose ability to connect to the new server was measured. The original
   blue trusting only the old leaf is not a valid rollback target. If B cannot
   validate the rotated server, stop promotion and use the prepared server
   certificate rollback, not a TLS bypass.
5. Remove the old leaf via a new manifest after the rollback observation period;
   do not retain B as eligible after its deadline. Leaf renewal under the same
   CA needs no image rebuild. CA rotation uses a bounded overlap of reviewed
   roots, new connections, and removal of the old root through new task config.

Deterministic bootstrap tests admit the exact public bridge material one second
before the fixed deadline and reject it at/after the deadline and in PROD. They
do not use its real private key or prove B against the active AWS SQL instance.

## Reproduce the opt-in real SQL test

Requires a local Docker Linux/amd64 engine, Python and OpenSSL. It never starts
AWS clients or publishes ports. Build/pull are explicit operations:

```sh
docker build --platform linux/amd64 -t ecs-api:trust-test -f demo-api/Dockerfile demo-api
docker pull mcr.microsoft.com/mssql/server@sha256:cf8f0ab2ebe61feec2eed2629061a07d247f791c2a8ddda74a4ac9f06a291718
python scripts/tests/sql_tls/run_local.py \
  --image "$(docker image inspect ecs-api:trust-test --format '{{.Id}}')" \
  --output /tmp/ecs-sql-tls-evidence
```

SQL Express runs on disposable tmpfs with two test issuers, each issuing the
**same hostname**, identical synthetic login/password and schema. Each API case
uses the real ENTRYPOINT, a fresh container and `Pooling=False`. Positive cases
execute the actual permission SELECT using SqlClient 6.1.7. Negative issuer/name
cases require its inner `AuthenticationException`, not a generic connection error.
The positive migrator case invokes the real entrypoint with
`database-migrate --confirm-schema-change`, a separate synthetic login/password
and no runtime connection variable. Exit zero plus exactly the two expected EF
history rows, `Text=nvarchar(max)` and zero data rows verify the schema effect.
The administrator's local `sqlcmd -C` is confined to synthetic fixture setup;
it does not establish API TLS acceptance. Test containers, network, passwords
and disposable private keys are removed on completion. No backup/recovery or
business data operation occurs. Evidence contains only public hashes/statuses.

The wall-clock SQL matrix does not expect the historical bridge to remain valid.
`scripts/tests/sql_tls/test_bootstrap.py` uses disposable external PATH shims for
the date, certificate verification time, UID and .NET boundary; it proves shell
admission only. The xUnit lifetime tests use a test-only `TimeProvider`. These
controls are outside the Docker context/artifact and cannot enable a production
clock override. Ordinary C has no transition deadline and remains covered by
real SQL positives as well as deterministic before/at/after-boundary tests.

The historical SQL-Lab Dockerfile, public leaf and E1 recipe hash remain unchanged.
Tests verify that frozen identity independently of the common Dockerfile, while
mutation tests still reject changed trust pins, bypasses and weakened runtime
instructions. Local results are in [LOCAL-VALIDATION.json](LOCAL-VALIDATION.json).
The follow-up findings, regression results and final image identity are in
[REVIEW-VALIDATION.json](REVIEW-VALIDATION.json). xUnit checks historical recipe
bytes inside the restricted E1 projection; the repository-level Python adapter
test owns the comparison with `e1_contract.py`, which is intentionally not
distributed to the .NET worker.
