#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SELECTOR="$ROOT/.github/scripts/cd/select-safety-tests.sh"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
# Isolate synthetic commits from runner/user configuration and credentials.
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
export GIT_AUTHOR_NAME=SafetyTest GIT_AUTHOR_EMAIL=safety@example.invalid
export GIT_COMMITTER_NAME=SafetyTest GIT_COMMITTER_EMAIL=safety@example.invalid
export GIT_AUTHOR_DATE='2026-01-01T00:00:00Z' GIT_COMMITTER_DATE='2026-01-01T00:00:00Z'
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
mkdir "$scratch/repo"
cd "$scratch/repo"
git init -q
git config core.autocrlf false
git config core.filemode true
git config commit.gpgsign false
git config advice.detachedHead false
echo seed > seed
git add seed
git commit -qm seed
seed="$(git rev-parse HEAD)"
passed=0

change() {
  mkdir -p "$(dirname "$1")"
  printf '%s\n' "${2:-change}" > "$1"
  git add -- "$1"
  git commit -qm change
}
reset_history() {
  # Only this freshly created disposable repository is ever reset.
  [[ $PWD -ef $scratch/repo && $(git rev-parse --git-dir) == .git ]] || exit 1
  git reset --hard -q "$seed"
  git checkout -q -B scenario "$seed"
}
expect() {
  local label="$1" expected="$2" event="$3" base="$4" head="$5" tested="$6" target="${7:-develop}" status=0
  GITHUB_EVENT_NAME="$event" GITHUB_BASE_REF="$target" GITHUB_REF=refs/heads/develop \
    GITHUB_SHA="$tested" SAFETY_BASE_SHA="$base" SAFETY_HEAD_SHA="$head" \
    GITHUB_OUTPUT="$scratch/outputs" bash "$SELECTOR" > "$scratch/result" 2>&1 || status=$?
  if [[ $expected == FAIL ]]; then
    [[ $status -ne 0 ]] || { echo "FAIL $label: expected nonzero"; exit 1; }
  else
    if [[ $status != 0 ]] || ! grep -Fxq "selection=$expected" "$scratch/result"; then
      echo "FAIL $label: exit=$status expected=$expected"
      cat "$scratch/result"
      exit 1
    fi
  fi
  passed=$((passed + 1))
  printf 'ok %s (exit=%s, expected=%s)\n' "$label" "$status" "$expected"
}
push_expect() {
  local head
  head="$(git rev-parse HEAD)"
  expect "$1" "$2" push "$seed" "$head" "$head"
}

# Expectations deliberately do not import the selector's exemption policy.
relevant=(
  .github/scripts/cd/detect-scope.sh .github/scripts/cd/resolve-terragrunt-layers.sh
  .github/scripts/cd/validate-infra-gate.sh .github/scripts/cd/select-safety-tests.sh
  .github/scripts/cd/tests/test-select-safety-tests.sh .github/scripts/cd/tests/test-safety-workflow.sh
  .github/workflows/ci-cd-safety.yml .github/workflows/cd.yml .github/actions/blue-green/action.yml
  scripts/render-demo-api-taskdef.sh scripts/validate-release-manifest.sh ci/schemas/release-manifest.schema.json
  terraform/live/dev/root.hcl terraform/live/prod/shared/terragrunt.hcl terraform/infra/apps/fargate/main.tf
  demo-api/deploy/task-definition.template.json demo-api/terragrunt-demo/App.csproj
  demo-api/terragrunt-demo.Tests/Tests.csproj demo-api/terragrunt-demo/appsettings.json demo-api/Dockerfile
  .gitattributes .gitmodules AGENTS.md terraform/docs/AGENTS.md terraform/docs/nested/AGENTS.md
  specs/cd-test-enforcement/spec.md unknown/new.file terraform/docs/tool.sh terraform/docs/data.json
  elsewhere/README.md demo-api/other/Program.cs 'scripts/a space.sh' 'scripts/[glob]$.sh'
  $'terraform/docs/new\nline.md' $'terraform/docs/tab\tname.md'
)
find "$ROOT/.github/scripts/cd/tests" -type f -print0 > "$scratch/test-paths"
while IFS= read -r -d '' path; do relevant+=("${path#"$ROOT/"}"); done < "$scratch/test-paths"
for path in "${relevant[@]}"; do
  reset_history
  change "$path"
  push_expect "relevant: $(printf %q "$path")" RUN
done
for path in README.md terraform/docs/guide.md terraform/docs/diagrams/example.png \
  demo-api/terragrunt-demo/Program.cs demo-api/terragrunt-demo.Tests/Tests.cs \
  'demo-api/terragrunt-demo/nested/A space.cs' 'terraform/docs/[literal]$.md'; do
  reset_history
  change "$path"
  push_expect "exempt: $path" EXEMPT
  before="$(git rev-parse HEAD)"
  git rm -q -- "$path"
  git commit -qm deletion
  head="$(git rev-parse HEAD)"
  expect "ordinary deletion: $path" EXEMPT push "$before" "$head" "$head"
done

reset_history
change scripts/relevant.sh
change README.md
push_expect multi-commit-mixed-push RUN
before="$(git rev-parse HEAD)"
mkdir -p terraform/docs
git mv scripts/relevant.sh terraform/docs/moved.md
git commit -qm rename
head="$(git rev-parse HEAD)"
expect relevant-to-exempt-rename RUN push "$before" "$head" "$head"
before="$head"
git mv terraform/docs/moved.md terraform/docs/renamed.md
git commit -qm rename
head="$(git rev-parse HEAD)"
expect exempt-rename EXEMPT push "$before" "$head" "$head"
reset_history
change scripts/delete-me.sh
before="$(git rev-parse HEAD)"
git rm -q scripts/delete-me.sh
git commit -qm delete-relevant
head="$(git rev-parse HEAD)"
expect relevant-deletion RUN push "$before" "$head" "$head"

reset_history
change README.md initial
before="$(git rev-parse HEAD)"
change README.md modified
head="$(git rev-parse HEAD)"
expect unrelated-modification EXEMPT push "$before" "$head" "$head"

reset_history
change README.md
before="$(git rev-parse HEAD)"
blob="$(printf target | git hash-object -w --stdin)"
git update-index --add --cacheinfo "120000,$blob,README.md"
git commit -qm symlink
head="$(git rev-parse HEAD)"
expect type-change RUN push "$before" "$head" "$head"
git checkout -q -- README.md
git rm -q README.md
git commit -qm deletion
expect symlink-deletion RUN push "$head" "$(git rev-parse HEAD)" "$(git rev-parse HEAD)"
reset_history
change README.md
git update-index --chmod=+x README.md
git commit -qm executable
push_expect executable-mode RUN

for target in develop main; do
  for relevance in relevant unrelated; do
    reset_history
    git checkout -q -B pr-head "$seed"
    if [[ $relevance == relevant ]]; then change scripts/earlier.sh; else change terraform/docs/earlier.md; fi
    change demo-api/terragrunt-demo/Latest.cs
    head="$(git rev-parse HEAD)"
    git checkout -q -B pr-base "$seed"
    change terraform/docs/base.md
    base="$(git rev-parse HEAD)"
    git merge --no-ff -qm merge "$head"
    tested="$(git rev-parse HEAD)"
    expected=EXEMPT
    [[ $relevance == unrelated ]] || expected=RUN
    expect "multi-commit divergent PR to $target: $relevance" "$expected" pull_request "$base" "$head" "$tested" "$target"
    expect 'wrong checkout SHA' FAIL pull_request "$base" "$head" "$head" "$target"
    expect 'stale event base' RUN pull_request "$seed" "$head" "$tested" "$target"
    # A merge-resolution change outside the head diff must also run tests.
    echo resolution > merge-only.sh
    git add merge-only.sh
    git commit --amend --no-edit -q
    expect 'merge-tree-only relevance' RUN pull_request "$base" "$head" "$(git rev-parse HEAD)" "$target"
  done
done

reset_history
change README.md
head="$(git rev-parse HEAD)"
missing=1111111111111111111111111111111111111111
zero=0000000000000000000000000000000000000000
expect empty-diff RUN push "$head" "$head" "$head"
expect zero-before RUN push "$zero" "$head" "$head"
expect absent-base RUN push "$missing" "$head" "$head"
expect absent-head RUN push "$seed" "$missing" "$head"
expect malformed-base RUN push not-a-sha "$head" "$head"
expect wrong-push-head FAIL push "$seed" "$seed" "$head"
expect wrong-checkout FAIL push "$seed" "$head" "$seed"
expect unsupported-event RUN workflow_dispatch "$seed" "$head" "$head"
tree="$(git rev-parse HEAD^{tree})"
other="$(printf other | git commit-tree "$tree")"
expect force-push-unrelated-history RUN push "$other" "$head" "$head"
merge="$(printf merge | git commit-tree "$tree" -p "$other" -p "$head")"
git checkout -q --detach "$merge"
expect unavailable-merge-base RUN pull_request "$other" "$head" "$merge"

# Criss-cross ancestry has two equally valid merge bases: no exemption.
a="$(printf a | git commit-tree "$tree" -p "$seed")"
b="$(printf b | git commit-tree "$tree" -p "$seed")"
left="$(printf left | git commit-tree "$tree" -p "$a" -p "$b")"
right="$(printf right | git commit-tree "$tree" -p "$b" -p "$a")"
merge="$(printf merge | git commit-tree "$tree" -p "$left" -p "$right")"
git checkout -q --detach "$merge"
expect ambiguous-merge-bases RUN pull_request "$left" "$right" "$merge"

git clone -q --depth 1 --no-local "file://$scratch/repo" "$scratch/shallow"
cd "$scratch/shallow"
expect shallow-history RUN push "$left" "$merge" "$merge"
cd "$scratch/repo"

# Make actual Git diff failures/truncation observable without mocking selection.
mkdir "$scratch/bin"
export SAFETY_REAL_GIT
SAFETY_REAL_GIT="$(command -v git)"
cat > "$scratch/bin/git" <<'SH'
#!/usr/bin/env bash
if [[ $1 == diff ]]; then
  case "$SAFETY_DIFF_FAULT" in
    failure) exit 1 ;;
    truncated) printf ':100644 100644'; exit 0 ;;
  esac
fi
exec "$SAFETY_REAL_GIT" "$@"
SH
chmod +x "$scratch/bin/git"
for fault in failure truncated; do
  export SAFETY_DIFF_FAULT="$fault"
  PATH="$scratch/bin:$PATH" expect "diff $fault" RUN push "$seed" "$merge" "$merge"
done
printf '%s selector history/category checks passed.\n' "$passed"
