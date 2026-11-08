# WP4 CodeBuild image: built and locally qualified

The normal delivery engine is CodeBuild. Its existing protected buildspec runs
`python3 /opt/e1/scripts/wp4d/runtime.py`; Lambda instead uses the separate
`Controller.Dockerfile`/`runtime.handler` bootstrap at `/var/task`. This recipe
does not pretend the Lambda Dockerfile supplies a CodeBuild environment.

## Concrete locked inputs and result

- Base: `docker.io/library/python@sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850`,
  linux/amd64, observed Python **3.13.17**, 44,199,179 compressed layer bytes.
- Thirteen official PyPI wheels, **20,930,576 bytes**, verified against PyPI's
  SHA256 metadata; existing jq **1.8.2** and its previously verified hash.
- Image-only AWS CLI **1.42.76**, Boto3/botocore **1.40.76**, s3transfer **0.14.0**.
  This aligns CLI and SDK requirements without changing host Boto3 1.40.0 or any
  global toolchain setting. Exact transitive versions/URLs/hashes are in the lock.
- Bootstrap bytes come from `29120514c64f7c7b36b680e7251da96b19d849e2` and match
  the unchanged exact DEV bundle `dc91ab31610de2b050ee077f3c55b6e29ffd06da1065609840c04d2ca90e9406`.
- Local tag: `ecs-wp4-codebuild:5fe2809-local`; manifest
  **`sha256:48b67dff2fb9b936975b73adfb15957522519f49928f9a34f68a5182a10fbba8`**;
  config **`sha256:c5869d49e9731dd03701b73f21f0d94cd105542ba64dadfdc8879df706af5a83`**.
  Local image size **271,431,922 bytes**; layers stay in the existing Docker cache,
  with no image tar/export or registry push.

The Lambda base is also known historically, not guessed:
`public.ecr.aws/lambda/python@sha256:c05509c1a303e7ca10acc26782f530ff1a8573411132e2a67c1924d687a65a96`
from `terraform/docs/first-real-dev-deployment.md` and `.github/workflows/ci-dotnet.yml`.
That source records historical Lambda image digest
`sha256:1f55128f3203d38f452405d9625011573865ac71710635eecd21ea17304162c4`.
It is not proof of a current AWS installation or a new V2 Lambda build. Only the
needed CodeBuild candidate was built here; engines/approvals remain separate.

## Reproduce locally without dependency installation or network in RUN

Use `prepare_image_context.py` with the already populated shared wheel cache and
verified jq. It verifies all inputs before writing, normalizes source text to LF,
refuses existing/repository outputs and links cached wheels when possible. It
does not execute Docker, fetch dependencies, read credentials or install anything.

```text
python -I -B scripts/wp4d/prepare_image_context.py --wheels WHEEL_CACHE --jq VERIFIED_JQ --output NEW_CONTEXT_OUTSIDE_REPO
docker buildx build --platform linux/amd64 --network=none --pull=false --provenance=false --sbom=false --load --build-arg SOURCE_DATE_EPOCH=1792885786 --metadata-file BUILD_METADATA.json --tag ecs-wp4-codebuild:5fe2809-local NEW_CONTEXT_OUTSIDE_REPO
```

The fixed base must already be in the builder's local cache. Initial base/wheel
acquisition used official public registries/PyPI and retained metadata/hashes;
the Docker RUN steps used `--network=none`, offline `--require-hashes` installation
and `pip check`. No apt, global install, new builder or daemon configuration was
used. Shared wheel bytes are retained once; contexts link them rather than
duplicating large archives. The source lock is an input inventory, not authority.

The first experimental context had CRLF in `requirements.lock`; the versioned
preparer emits LF. That real COPY-input difference produced a different digest
(`74151211...891f4795`) and is preserved with its context/logs. The canonical LF
context was then repeated **identically** and both builds returned `48b67dff...`;
descriptor, tag, source-date epoch and input hashes agree. This proves the local
cache replay with pinned inputs, not an independent uncached rebuild on another
builder. The observed builder is BuildKit v0.34.0 / Dockerfile frontend 1.28.0.

## Qualification and deployment boundary

**44 PASS, zero skips**, inside the actual image with network disabled, UID65534,
read-only root/source mounts, capabilities dropped and 768MiB/1CPU limits. Seven
cases loaded the actual image bootstrap from `/opt/e1`, and a real Boto3 client
loaded the version-pinned bundle with Stubber responses. Other runtime/fact/E3
ports remain doubles. AWS CLI/jq versions and installed dependency consistency
were observed. The disposable container exited normally and was removed.

No private AWS request, SQL execution, ECR publication, service installation or
runtime/IAM approval happened. The image is a concrete local build candidate,
not a deployed controller. ECR URI/versioned installation receipt, current
protected configuration/membership/effective permissions and native recovery
acceptance must be admitted together before installation. The public request
still cannot choose image, profile, role, endpoint or secret version.

The next gate is the **native execution/admission**, not another local image
design: resolve SSM's demonstrated asynchronous denial without an alternate
principal/document workaround, verify current metadata, admit the complete
platform plan/budget/retirement and capture the listed fresh recovery fields.
The prior budgets remain closed.

Sources: [CodeBuild image repositories](https://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref.html),
[Docker Official Python packaging](https://github.com/docker-library/python),
[AWS CLI Python support](https://docs.aws.amazon.com/cli/v1/userguide/install-virtualenv.html),
[BuildKit reproducibility boundaries](https://github.com/moby/buildkit/blob/master/docs/build-repro.md).
