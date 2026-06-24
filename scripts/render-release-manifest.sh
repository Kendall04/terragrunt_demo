#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_NAME="${APP_NAME:-demo-api}"
REPOSITORY="${GITHUB_REPOSITORY:-}"
GIT_SHA="${GITHUB_SHA:-}"
SOURCE_BRANCH="${SOURCE_BRANCH:-}"
GITHUB_RUN_ID_VALUE="${GITHUB_RUN_ID:-}"
GITHUB_RUN_ATTEMPT_VALUE="${GITHUB_RUN_ATTEMPT:-}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
IMAGE_DIGEST="${IMAGE_DIGEST:-}"
DOTNET_TESTS="${DOTNET_TESTS:-passed}"
DOCKER_BUILD="${DOCKER_BUILD:-passed}"
SCAN_STATUS="${SCAN_STATUS:-unknown}"
OUTPUT_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/render-release-manifest.sh --repository OWNER/REPO --git-sha SHA \
    --source-branch BRANCH --github-run-id ID --github-run-attempt N \
    --image-registry REGISTRY --image-repository REPO --image-tag TAG \
    --image-digest sha256:<64 lowercase hex> --output FILE

Optional:
  --app APP                         Default: demo-api
  --dotnet-tests passed|failed|skipped
  --docker-build passed|failed|skipped
  --scan-status passed|failed|skipped|unknown

Environment variables with matching names are also accepted for CI usage.
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --app)
        APP_NAME="${2:-}"
        shift 2
        ;;
      --repository)
        REPOSITORY="${2:-}"
        shift 2
        ;;
      --git-sha)
        GIT_SHA="${2:-}"
        shift 2
        ;;
      --source-branch)
        SOURCE_BRANCH="${2:-}"
        shift 2
        ;;
      --github-run-id)
        GITHUB_RUN_ID_VALUE="${2:-}"
        shift 2
        ;;
      --github-run-attempt)
        GITHUB_RUN_ATTEMPT_VALUE="${2:-}"
        shift 2
        ;;
      --image-registry)
        IMAGE_REGISTRY="${2:-}"
        shift 2
        ;;
      --image-repository)
        IMAGE_REPOSITORY="${2:-}"
        shift 2
        ;;
      --image-tag)
        IMAGE_TAG="${2:-}"
        shift 2
        ;;
      --image-digest)
        IMAGE_DIGEST="${2:-}"
        shift 2
        ;;
      --dotnet-tests)
        DOTNET_TESTS="${2:-}"
        shift 2
        ;;
      --docker-build)
        DOCKER_BUILD="${2:-}"
        shift 2
        ;;
      --scan-status)
        SCAN_STATUS="${2:-}"
        shift 2
        ;;
      --output)
        OUTPUT_FILE="${2:-}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

validate_args() {
  [ "$APP_NAME" = "demo-api" ] || die "--app must be demo-api."
  [ -n "$REPOSITORY" ] || die "--repository is required."
  [[ "$GIT_SHA" =~ ^[A-Fa-f0-9]{7,40}$ ]] || die "--git-sha must be a 7 to 40 character git SHA."
  [ -n "$SOURCE_BRANCH" ] || die "--source-branch is required."
  [[ "$GITHUB_RUN_ID_VALUE" =~ ^[0-9]+$ ]] || die "--github-run-id must be numeric."
  [[ "$GITHUB_RUN_ATTEMPT_VALUE" =~ ^[0-9]+$ ]] || die "--github-run-attempt must be numeric."
  [ -n "$IMAGE_REGISTRY" ] || die "--image-registry is required."
  [ -n "$IMAGE_REPOSITORY" ] || die "--image-repository is required."
  [[ "$IMAGE_TAG" =~ ^[A-Za-z0-9_.-]+$ ]] || die "--image-tag contains unsupported characters."
  [ -n "$OUTPUT_FILE" ] || die "--output is required."

  case "$DOTNET_TESTS" in
    passed|failed|skipped) ;;
    *) die "--dotnet-tests must be passed, failed, or skipped." ;;
  esac

  case "$DOCKER_BUILD" in
    passed|failed|skipped) ;;
    *) die "--docker-build must be passed, failed, or skipped." ;;
  esac

  case "$SCAN_STATUS" in
    passed|failed|skipped|unknown) ;;
    *) die "--scan-status must be passed, failed, skipped, or unknown." ;;
  esac

  "$ROOT_DIR/scripts/validate-image-digest.sh" --digest "$IMAGE_DIGEST"
}

render_manifest() {
  local image_uri
  local created_at
  local output_dir

  image_uri="${IMAGE_REGISTRY}/${IMAGE_REPOSITORY}@${IMAGE_DIGEST}"
  created_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  output_dir="$(dirname "$OUTPUT_FILE")"
  mkdir -p "$output_dir"

  jq -n \
    --arg schema_version "1.0" \
    --arg app "$APP_NAME" \
    --arg repository "$REPOSITORY" \
    --arg git_sha "$GIT_SHA" \
    --arg source_branch "$SOURCE_BRANCH" \
    --arg github_run_id "$GITHUB_RUN_ID_VALUE" \
    --arg github_run_attempt "$GITHUB_RUN_ATTEMPT_VALUE" \
    --arg created_at "$created_at" \
    --arg image_registry "$IMAGE_REGISTRY" \
    --arg image_repository "$IMAGE_REPOSITORY" \
    --arg image_tag "$IMAGE_TAG" \
    --arg image_digest "$IMAGE_DIGEST" \
    --arg image_uri "$image_uri" \
    --arg dotnet_tests "$DOTNET_TESTS" \
    --arg docker_build "$DOCKER_BUILD" \
    --arg scan_status "$SCAN_STATUS" \
    '{
      schemaVersion: $schema_version,
      app: $app,
      repository: $repository,
      gitSha: $git_sha,
      sourceBranch: $source_branch,
      githubRunId: $github_run_id,
      githubRunAttempt: $github_run_attempt,
      createdAt: $created_at,
      image: {
        registry: $image_registry,
        repository: $image_repository,
        tag: $image_tag,
        digest: $image_digest,
        uri: $image_uri
      },
      quality: {
        dotnetTests: $dotnet_tests,
        dockerBuild: $docker_build,
        scanStatus: $scan_status
      }
    }' > "$OUTPUT_FILE"

  "$ROOT_DIR/scripts/validate-release-manifest.sh" "$OUTPUT_FILE"
}

main() {
  parse_args "$@"
  require_command jq
  validate_args
  render_manifest
}

main "$@"
