#!/usr/bin/env bash
set -euo pipefail

# Event SHAs are immutable inputs supplied by ci-cd-safety.yml. Never use a
# moving branch ref or the last commit alone to grant an exemption.
die() { echo "::error::$*" >&2; exit 2; }
for tool in git mktemp rm; do
  command -v "$tool" >/dev/null || die "Missing dependency: $tool"
done
export GIT_NO_REPLACE_OBJECTS=1 GIT_NO_LAZY_FETCH=1
actual="$(git rev-parse --verify HEAD)" || die 'Cannot resolve checkout HEAD'
printf 'checkout actual_sha=%s event_test_sha=%s\n' "$actual" "${GITHUB_SHA:-missing}"
[[ ${GITHUB_SHA:-} =~ ^[0-9a-f]{40}$ && $actual == "$GITHUB_SHA" ]] || die 'Checkout identity mismatch'
base="${SAFETY_BASE_SHA:-}"
head="${SAFETY_HEAD_SHA:-}"
merge_base=''
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

finish() {
  local selection="$1" reason="$2"
  printf 'selection=%s\nreason=%s\nactual_sha=%s\nmerge_base=%s\n' \
    "$selection" "$reason" "$actual" "$merge_base"
  if [[ -n ${GITHUB_OUTPUT:-} ]]; then
    printf 'selection=%s\nreason=%s\nactual_sha=%s\nmerge_base=%s\n' \
      "$selection" "$reason" "$actual" "$merge_base" >> "$GITHUB_OUTPUT"
  fi
  exit 0
}
run() { finish RUN "$1"; }
commit_exists() {
  [[ $1 =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "$1^{commit}" 2>/dev/null
}
shallow="$(git rev-parse --is-shallow-repository)" || run history-check-failed
[[ $shallow == false ]] || run shallow-history
commit_exists "$base" || run unavailable-base
commit_exists "$head" || run unavailable-head

case "${GITHUB_EVENT_NAME:-}" in
  pull_request)
    [[ ${GITHUB_BASE_REF:-} == main || ${GITHUB_BASE_REF:-} == develop ]] || run unexpected-pr-target
    # Only a merge with the exact event base and head is unambiguous. A stale
    # merge, unexpected parent order or missing merge base must run the suite.
    parents="$(git show -s --format=%P "$actual")" || run unavailable-merge-parents
    [[ $parents == "$base $head" ]] || run ambiguous-merge
    merge_base="$(git merge-base --all "$base" "$head")" || run unavailable-merge-base
    [[ $merge_base =~ ^[0-9a-f]{40}$ ]] || run ambiguous-merge-base
    git diff --raw --no-abbrev -z --no-renames --no-ext-diff --no-textconv \
      "$merge_base" "$head" -- > "$work/paths" || run pr-diff-failed
    git diff --raw --no-abbrev -z --no-renames --no-ext-diff --no-textconv \
      "$base" "$actual" -- >> "$work/paths" || run merge-diff-failed
    ;;
  push)
    [[ ${GITHUB_REF:-} == refs/heads/develop ]] || run unexpected-push-target
    [[ $head == "$actual" ]] || die 'Push head differs from tested revision'
    git merge-base --is-ancestor "$base" "$head" || run non-ancestor-push
    git diff --raw --no-abbrev -z --no-renames --no-ext-diff --no-textconv \
      "$base" "$head" -- > "$work/paths" || run push-diff-failed
    ;;
  *) run unsupported-event ;;
esac

count=0
while IFS= read -r -d '' record; do
  IFS= read -r -d '' path || run malformed-path-list
  # Only ordinary non-executable blobs can be exempt. Symlinks, submodules,
  # executable-bit changes and type changes are relevant, including deletions.
  [[ $record =~ ^:(000000|100644)\ (000000|100644)\ [0-9a-f]{40}\ [0-9a-f]{40}\ [AMD]$ ]] || run uncertain-file-type
  [[ $path != *[$'\n\r\t\\']* ]] || run uncertain-path
  case "$path" in AGENTS.md|*/AGENTS.md) run repository-guidance ;; esac
  case "$path" in
    README.md|terraform/docs/*.md|terraform/docs/*.png|demo-api/terragrunt-demo/*.cs|demo-api/terragrunt-demo.Tests/*.cs) ;;
    *) printf 'Relevant path: %q\n' "$path"; run relevant-path ;;
  esac
  count=$((count + 1))
done < "$work/paths"
[[ -z $record ]] || run truncated-path-list
[[ $count -gt 0 ]] || run empty-diff
finish EXEMPT complete-unrelated-diff
