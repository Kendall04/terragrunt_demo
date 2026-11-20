# Validation and command effects

[CI coverage](../../docs/CI-CD-REVIEW.md) · [Demonstrated results](../../docs/RESULTS.md)

CI is the reproducible source of selected checks. Historical local test counts
are not today's coverage, and offline PASS does not prove AWS installation,
permissions, SQL restore or deployment. Commands below use existing tools from
the repository root; a command listing is not authorization to install tools or
change infrastructure.

## Command effect classification

| Command family | Effects |
| --- | --- |
| `git diff`, `git status`, file/link review | Local inspection; Git fetch/push separately uses the remote. |
| `terraform fmt -check`, `terragrunt hcl format --check`, lint | Check-only with existing tools; initialization/downloads are separate. |
| Python/Node contract tests | Temporary local files/processes; transport doubles are not AWS evidence. |
| `dotnet restore/build/test` | Package network/cache and bin/obj/test outputs; opt-in integration tests may contact configured services. |
| Docker build or SQL/TLS experiment | Images, caches and isolated containers; not read-only. |
| Terraform/Terragrunt `init`, `validate`, `plan` | Can generate files, read remote state, invoke providers and contact AWS. Plan is not an offline synonym. |
| Runtime start / readiness | Can connect to SQL and KMS. `/ready` checks DB/migrations and KMS Encrypt; a configured local start is not automatically isolated. |
| Deploy, reconcile, rollback, apply, secret publication | AWS mutations or evidence writes; follow the owning runbook and explicit scope. |
| Destroy, retention admission, restore-hold creation | Destruction, version-tag changes or new object copies respectively; none is routine CI. |

Secret values must stay out of state, argv, logs and public test artifacts.
A helper's `--dry-run` semantics must be checked individually. State audits
may download private state; they are cloud-connected, not ordinary offline tests.

## Focused offline checks

```sh
# Required documentation links and immutable approved contracts
python3 -I -B scripts/tests/final_acceptance/check_knowledge.py

# Real selectors with synthetic Git histories and result enforcement
python3 -I -B -m unittest discover -s .github/scripts/ci/tests -v

# Automatic delivery, GitHub/S3 transport contracts and failure handling
python3 -I -B -m unittest discover -s scripts/tests/api_delivery -v

# SQL recovery/storage Python suites, no real SQL or AWS
python3 -I -B scripts/tests/run_recovery_ci.py

# Portfolio, isolation and Archify provenance; no external browser/network
node --test portfolio/test-contract.mjs
node --test scripts/diagrams/test-diagrams.mjs
```

Readiness Bash fixtures run in a scrubbed environment through
`scripts/tests/run-offline-readiness-tests.sh` with a fake AWS executable.
[Repo Hygiene](../../.github/workflows/ci-repo-hygiene.yml) also runs backup observer
and local-signal helpers, reproducibility, hosting contracts, Actionlint,
ShellCheck and formatting. Retained observer tests do not install Sentinel.

The [E1 gate](e1-final-acceptance.md) requires the pinned Terraform tool and its
complete hermetic suite:

```sh
python3 -I -B scripts/tests/final_acceptance/gate.py --report-dir <new-temporary-directory>
```

Do not regenerate authority hashes or relax tests to bypass a failed source
check. `ci/authority/retired/` and the approved IAM contracts are test inputs.

## Application and database tests

Use the SDK in [global.json](../../global.json) and locked NuGet dependencies.
The exact build/test and Docker commands live in [App CI](../../.github/workflows/ci-dotnet.yml).
Build/test create local output; restores can require network access.

```sh
dotnet restore demo-api/terragrunt-demo.sln --locked-mode
dotnet test demo-api/terragrunt-demo.sln --no-restore
```

API tests cover input size/pagination, encryption/repository paths, strict
configuration and readiness with explicit doubles. A green liveness endpoint
alone proves neither SQL identity nor KMS availability. The opt-in
[real SQL environment-trust experiment](../../demo-api/deploy/sql-trust/README.md)
uses disposable SQL/CA credentials, the real image entrypoint and new physical
SqlClient connections. It is distinct from both unit tests and AWS qualification.
No database migration or restore is implicit in CI.

## Infrastructure and security

[Static IaC CI](../../.github/workflows/ci-terragrunt.yml) uses pinned tools and
existing scanner baselines. [E14-B](e14b-toolchain-reproducibility.md) records their
provenance and update boundaries. Scanner warnings require interpretation;
known findings are not removed by updating documentation. Remote plans have
separate read-only entrypoints and authority; this guide does not invoke them.

## Browser and diagram validation

[Frontend instructions](../../portfolio/product/README.md#pruebas) use existing
Chrome/Playwright. The local runner isolates DEMO and explicit HTTP doubles;
[the current atlas](../../docs/interactive/CURRENT-INDEX.md) provides authenticated
Archify generation and reproducibility commands. Do not regenerate historical
outputs or alter hashes just to pass a gate. AWS browser tests perform real API
operations and require explicit authorization; the historical proof remains in
[the UI validation record](../../docs/RESULTS.md).

## Evidence boundaries

Real automatic DEV delivery, CA-only TLS, native backups and SAME/CROSS-AZ
restoration have separate [dated evidence](../../docs/RESULTS.md).
PROD deployment, uninterrupted monitoring, PITR and abrupt-disaster zero RPO
are not demonstrated. The earlier validation chronology is recoverable at
[the pre-consolidation revision](https://github.com/Kendall04/terragrunt_demo/blob/1a39c46cc02f262c04f438207647acc1282393a0/terraform/docs/validation.md);
it is not a current task list or permission to replay old experiments.
