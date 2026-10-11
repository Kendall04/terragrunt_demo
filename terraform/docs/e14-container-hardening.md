# E14-A application container contract

E14-A is bounded to application base identities, non-root execution and offline
Dockerfile validation. It does not complete the broader B14/E14 toolchain initiative.

## Current contract

The [Dockerfile](../../demo-api/Dockerfile) retains its runtime/build/final stages,
Release default, framework-dependent publish to `/app/publish`, final `/app` work
directory and `dotnet terragrunt-demo.dll` entrypoint. Both runtime stages explicitly
use `USER $APP_UID`, supplied as UID 1654 by the verified .NET 8 image. The build
stage retains its original build identity; it is not the deployed runtime stage.
No package installation, chmod/chown layer or privileged runtime operation is added.

The bases are pinned to the **linux/amd64 child manifests**, matching the existing
[ECS template](../../demo-api/deploy/task-definition.template.json)'s Linux/X86_64
Fargate contract. The same image/entrypoint/user runs the essential API and the
non-essential `readiness-probe` command. Neither container overrides the image user.
HTTP remains `ASPNETCORE_URLS=http://+:8080`, `EXPOSE 8080` and ECS TCP port 8080;
the probe still calls `http://127.0.0.1:8080/ready`. This pin deliberately targets
x86-64; ARM64 builds are outside this contract.

The published files remain root-owned through Docker COPY's default ownership.
The inspected application reads its binaries/configuration, logs to stdout/stderr
and performs network DB/KMS operations; it does not write application files or
require root. Standard publish output is expected to be readable by UID 1654.
The selected base's configuration/history reports the `app` account/group and
`/home/app` creation. `/tmp` and the app home remain available for normal runtime
temporary files. Linux permissions and execution must still be checked with a
real container; source inspection and Windows startup do not prove them.

`APP_ENV` still does not select ASP.NET's environment. No Dockerfile setting changes
`ASPNETCORE_ENVIRONMENT`, secret injection, credential-chain behavior or the default
startup migrations. Normal startup requires care: migrations remain enabled and
can modify the configured database. The local smoke recipe below disables them.

## Verified image identities

On 2026-10-11, installed Docker Buildx 0.37.1 queried public Microsoft Container
Registry with `imagetools inspect`. Each 8.0 index listed the selected linux/amd64
manifest; digest-qualified manifest and `.Image` reads confirmed OS/architecture,
.NET/ASP.NET 8.0.31, SDK 8.0.425, `APP_UID=1654` and base HTTP port 8080.
The index, manifest and config digests are recorded in
[base-image evidence](../../demo-api/container-base-images.json).

| Stage | Immutable linux/amd64 manifest |
| --- | --- |
| Runtime | `mcr.microsoft.com/dotnet/aspnet:8.0@sha256:9a432d3500734557e5fecea0336bf274c85de15aa55505a2dafe06e44f0cd024` |
| SDK | `mcr.microsoft.com/dotnet/sdk:8.0@sha256:e1d5584f7c7f45439449054292acadf4f71730034507186497bab3d539a5a9b7` |

These fix the base contents, including OS layers. They do not establish bit-for-bit
application build reproducibility: NuGet/transitive resolution, SDK selection in
host CI, actions/tools and incomplete infrastructure locks remain separate work.

## Intentional update procedure

Using an existing Docker/Buildx installation, inspect both approved .NET 8 tags:

```bash
docker buildx imagetools inspect mcr.microsoft.com/dotnet/aspnet:8.0
docker buildx imagetools inspect mcr.microsoft.com/dotnet/sdk:8.0
```

Select each linux/amd64 child digest from the response. Inspect each resulting
`tag@sha256:...` reference with `imagetools inspect --raw` for its config digest
and `imagetools inspect --format '{{json .Image}}'` for OS/architecture, runtime/SDK
versions and APP_UID. Check the runtime account/history; do not reuse a digest
from another platform or invent one when the registry is unavailable. Review the
patch change, update both FROM references and the evidence file, then refresh only
the Dockerfile entry in the source inventory through the existing scanner.
Run the application tests and Linux smoke checks before accepting the update.
Pinning means security/OS patches require this deliberate refresh.

## Focused validation and evidence boundary

[Container contract tests](../../demo-api/terragrunt-demo.Tests/ContainerContractTests.cs)
run through the existing .NET test entry point. Their 21 cases cover pinned base
references, explicit runtime identities (including root/UID reset mutations),
HTTP 8080, multi-stage publish/entrypoint behavior, packaged probe compatibility
and ECS inheritance without execution overrides. The bounded Dockerfile grammar
rejects added instructions, so deliberate pipeline changes require test review.
The tests use checked-in evidence and make no registry, DB or AWS requests.

```bash
dotnet restore demo-api/terragrunt-demo.sln
dotnet build demo-api/terragrunt-demo.sln --configuration Release --no-restore
dotnet test demo-api/terragrunt-demo.sln --configuration Release --no-build
```

Candidate local evidence: restore succeeded; build had zero warnings/errors; all
61 tests passed. Framework-dependent publish succeeded, the published probe's
`--check-capability` succeeded and Production startup returned HTTP 200/Healthy
from `/health` on loopback port 8080. That startup used the installed Windows .NET
8 runtime with migrations disabled, scrubbed credentials, metadata disabled and a
synthetic unused DB connection; no readiness/text/dependency route was invoked.
It is application/output evidence, not Linux container execution evidence.

Docker CLI 29.8.1 was installed, but neither default nor Docker Desktop Linux
engine pipe was available. No container image build/start or Linux filesystem
permission test was executed, and no tooling was installed or daemon started.
There was no AWS access, deployment, fetch, push or PR.

With a running Linux Docker engine, the following local Bash recipe validates the
remaining permissions, runtime identity, packaged probe and HTTP startup. The
application container has no external network, credentials, volumes or privilege;
it calls only liveness, never DB/KMS readiness. Build still downloads bases/NuGet
and writes Docker caches, as described in [validation](validation.md).

```bash
set -euo pipefail
docker build --platform linux/amd64 -t e14-api-local -f demo-api/Dockerfile demo-api
test "$(docker image inspect e14-api-local --format '{{.Config.User}}')" = 1654
docker run --rm --network none --entrypoint /bin/sh e14-api-local -c \
  'test "$(id -u)" = 1654 && test "$(id -g)" = 1654 && test -x /app && test -r /app/terragrunt-demo.dll && test -r /app/appsettings.json && test ! -w /app && test -w /tmp && test -w /home/app'
test "$(docker run --rm --network none e14-api-local readiness-probe --check-capability)" = readiness-probe-capability=available
cid=$(docker run -d --network none \
  -e ASPNETCORE_ENVIRONMENT=Production -e Database__RunMigrationsOnStartup=false \
  -e AWS_EC2_METADATA_DISABLED=true -e AWS_REGION=us-east-1 \
  -e 'DB_CONN_STRING=Server=127.0.0.1;Database=e14_unused;User Id=unused;Password=synthetic-unused;TrustServerCertificate=true;' \
  e14-api-local)
trap 'docker rm -f "$cid" >/dev/null' EXIT
# Base image includes bash. Bound the loop and each HTTP read.
docker exec "$cid" bash -c '
  for attempt in {1..20}; do
    if (exec 3<>/dev/tcp/127.0.0.1/8080) 2>/dev/null; then
      exec 3<>/dev/tcp/127.0.0.1/8080
      printf "GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n" >&3
      IFS= read -r -t 2 status <&3
      [[ "$status" == *"200 OK"* ]] && exit 0
    fi
    sleep 1
  done
  exit 1'
```

No live ECS/Fargate compatibility or deployment evidence is claimed. Current
configuration compatibility is checked; real container and AWS execution remain
unverified. Agent 2's pagination files/test project are untouched. Architecture,
validation and backlog documentation overlap with Agents 1/2; combine the distinct
E14 paragraphs/row change during integration, and preserve each agent's source
inventory entries. No other branch was edited.
