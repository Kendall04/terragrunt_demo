#!/usr/bin/env bash
set -euo pipefail

DIGEST=""
IMAGE_URI=""

usage() {
  cat <<'EOF'
Usage:
  scripts/validate-image-digest.sh --digest sha256:<64 lowercase hex>
  scripts/validate-image-digest.sh --image-uri <registry>/<repo>@sha256:<64 lowercase hex>
  scripts/validate-image-digest.sh --digest sha256:<64 lowercase hex> --image-uri <registry>/<repo>@sha256:<64 lowercase hex>

Validates immutable image digests and image URIs. Tag-only image URIs are rejected.
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --digest)
        DIGEST="${2:-}"
        shift 2
        ;;
      --image-uri)
        IMAGE_URI="${2:-}"
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

validate_digest() {
  local digest="$1"

  if ! [[ "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    die "Invalid image digest. Expected sha256:<64 lowercase hex chars>."
  fi
}

validate_image_uri() {
  local image_uri="$1"
  local uri_digest

  if [[ "$image_uri" != *"@"* ]]; then
    die "Image URI must be digest-based and include @sha256:..."
  fi

  if ! [[ "$image_uri" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]*/[A-Za-z0-9][A-Za-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]]; then
    die "Invalid image URI. Expected <registry>/<repo>@sha256:<64 lowercase hex chars>."
  fi

  uri_digest="${image_uri##*@}"
  validate_digest "$uri_digest"

  if [ -n "$DIGEST" ] && [ "$uri_digest" != "$DIGEST" ]; then
    die "Image URI digest does not match the provided digest."
  fi
}

main() {
  parse_args "$@"

  if [ -z "$DIGEST" ] && [ -z "$IMAGE_URI" ]; then
    die "At least one of --digest or --image-uri is required."
  fi

  if [ -n "$DIGEST" ]; then
    validate_digest "$DIGEST"
  fi

  if [ -n "$IMAGE_URI" ]; then
    validate_image_uri "$IMAGE_URI"
  fi
}

main "$@"
