#!/bin/bash
# Public user-data only. Sourceable helpers permit offline fixtures; main is Linux-only.
set +x

stage_fail() {
  local rc="$1" category="$2"
  trap - ERR
  unset SA_PASS SQLCMDPASSWORD probe
  printf 'RECOVERY_STAGE_FAILED stage=%s exit=%s category=%s\n' "$STAGE" "$rc" "$category"
  exit "$rc"
}

classify_output() {
  case "$1" in
    *NO_PUBKEY*|*'not signed'*|*'signatures couldn'* ) echo APT_SIGNATURE ;;
    *'Release file'*|*'Release does not have'* ) echo APT_RELEASE ;;
    *'Unable to locate package'*|*'no installation candidate'* ) echo PACKAGE_CANDIDATE ;;
    *'unmet dependencies'*|*'held broken packages'*|*'Unable to correct problems'* ) echo PACKAGE_DEPENDENCY ;;
    *'Could not resolve'*|*'Temporary failure resolving'* ) echo DNS ;;
    *'certificate verification failed'*|*'Certificate verification failed'* ) echo TLS ;;
    *'Failed to fetch'*|*'Could not connect'*|*'Connection timed out'* ) echo NETWORK ;;
    *'No space left on device'* ) echo DISK ;;
    *EULA* ) echo EULA ;;
    * ) echo COMMAND_FAILED ;;
  esac
}

run_stage() {
  STAGE="$1"; shift
  [[ "$STAGE" =~ ^[a-z0-9_]+$ ]] || exit 64
  printf 'RECOVERY_STAGE_START stage=%s\n' "$STAGE"
  local output rc category
  if output=$("$@" 2>&1); then
    unset output
    printf 'RECOVERY_STAGE_OK stage=%s\n' "$STAGE"
  else
    rc=$?; category=$(classify_output "$output"); unset output
    stage_fail "$rc" "$category"
  fi
}

secret_stage() {
  STAGE="$1"; shift
  [[ "$STAGE" =~ ^[a-z0-9_]+$ ]] || exit 64
  printf 'RECOVERY_STAGE_START stage=%s\n' "$STAGE"
  local rc
  if "$@" >/dev/null 2>&1; then
    printf 'RECOVERY_STAGE_OK stage=%s\n' "$STAGE"
  else
    rc=$?; stage_fail "$rc" SECRET_OPERATION_FAILED
  fi
}

load_os_release() { . /etc/os-release; }

check_platform() {
  [[ $(id -u) == 0 ]] || return 77
  [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || return 65
  [[ $(dpkg --print-architecture) == amd64 ]] || return 65
  load_os_release || return $?
  [[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 ]] || return 65
}

check_fresh_host() {
  local command
  for command in timeout apt-get apt-cache dpkg-query systemctl runuser getent; do
    command -v "$command" >/dev/null || return 69
  done
  [[ -d /run/systemd/system ]] || return 69
  systemctl show --property=Version --value >/dev/null || return $?
  getent passwd _apt >/dev/null || return 69
  [[ ! -e /opt/mssql/bin/sqlservr && ! -e /var/opt/mssql/mssql.conf ]] || return 73
}

configure_repositories() {
  install -d -m 0755 /etc/apt/keyrings || return $?
  curl --max-time 30 -fsSL https://packages.microsoft.com/keys/microsoft.asc |
    gpg --batch --dearmor -o /etc/apt/keyrings/recovery-microsoft.gpg || return $?
  printf '%s\n' 'deb [arch=amd64 signed-by=/etc/apt/keyrings/recovery-microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy main' >/etc/apt/sources.list.d/recovery-sql.list || return $?
  printf '%s\n' 'deb [arch=amd64 signed-by=/etc/apt/keyrings/recovery-microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main' >/etc/apt/sources.list.d/recovery-tools.list || return $?
  # These are public trust metadata. The log and secret handling retain umask 077.
  chmod 0644 /etc/apt/keyrings/recovery-microsoft.gpg /etc/apt/sources.list.d/recovery-sql.list /etc/apt/sources.list.d/recovery-tools.list
}

check_repository_access() {
  local file
  for file in "$@"; do
    [[ -s "$file" && ! -L "$file" ]] || return 65
    runuser -u _apt -- test -r "$file" || return $?
  done
}

check_candidates() {
  local package policy candidate rc
  for package in mssql-server mssql-tools18 unixodbc-dev; do
    if policy=$(apt-cache policy "$package" 2>&1); then :; else rc=$?; return "$rc"; fi
    candidate=$(printf '%s\n' "$policy" | awk '/^[[:space:]]*Candidate:/ {print $2}')
    [[ "$candidate" =~ ^[0-9][A-Za-z0-9.+:~_-]*$ ]] || return 65
    # Bind repository rows to this exact candidate block, not any older version.
    # dpkg status is installation metadata, never repository provenance.
    if printf '%s\n' "$policy" | awk -v package="$package" -v candidate="$candidate" '
      function allowed(uri, suite, arch, kind) {
        sub(/\/$/, "", uri)
        if (arch != "amd64" || kind != "Packages") return 0
        if (package == "mssql-server")
          return uri == "https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022" && suite == "jammy/main"
        if (uri == "https://packages.microsoft.com/ubuntu/22.04/prod" && suite == "jammy/main") return 1
        if (package != "unixodbc-dev") return 0
        return uri ~ /^https?:\/\/(archive\.ubuntu\.com|security\.ubuntu\.com|us-east-1\.ec2\.archive\.ubuntu\.com)\/ubuntu$/ && suite ~ /^jammy(-updates|-security)?\/main$/
      }
      $0 == package ":" { headers++; next }
      $1 == "Version" && $2 == "table:" && NF == 2 { tables++; active = 0; next }
      tables == 1 && $1 == "***" && NF == 3 && $3 ~ /^[0-9]+$/ {
        active = ($2 == candidate); if (active) blocks++; next
      }
      tables == 1 && NF == 2 && $2 ~ /^[0-9]+$/ {
        active = ($1 == candidate); if (active) blocks++; next
      }
      active && NF {
        if (NF == 2 && $1 ~ /^[0-9]+$/ && $2 == "/var/lib/dpkg/status") { status++; next }
        if ($1 ~ /^[0-9]+$/) {
          sources++
          if (NF != 5 || !allowed($2, $3, $4, $5) || seen[$2 FS $3 FS $4 FS $5]++) bad = 1
          next
        }
        bad = 1
      }
      END { exit (headers == 1 && tables == 1 && blocks == 1 && sources >= 1 && status <= 1 && !bad ? 0 : 65) }
    '; then :; else rc=$?; return "$rc"; fi
  done
}

install_sql_packages() {
  ACCEPT_EULA=Y timeout 900 apt-get install -y mssql-server mssql-tools18 unixodbc-dev
}

check_sql_installation() {
  [[ -x /opt/mssql/bin/sqlservr && -x /opt/mssql-tools18/bin/sqlcmd ]] || return 69
  local package status rc
  for package in mssql-server mssql-tools18 msodbcsql18; do
    if status=$(dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null); then :; else rc=$?; return "$rc"; fi
    [[ "$status" == installed ]] || return 69
  done
  systemctl cat mssql-server >/dev/null
}

read_sa_secret() {
  local rc
  if SA_PASS=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-sa-password-30fCjc --query SecretString --output text 2>/dev/null); then :; else rc=$?; return "$rc"; fi
  [[ -n "$SA_PASS" && "$SA_PASS" != None ]] || return 65
}

setup_sql() { ACCEPT_EULA=Y MSSQL_PID=Express MSSQL_SA_PASSWORD="$SA_PASS" timeout 180 /opt/mssql/bin/mssql-conf -n setup; }

wait_sql() {
  local attempt rc=1
  export SQLCMDPASSWORD="$SA_PASS"
  for attempt in $(seq 1 90); do
    if probe=$(/opt/mssql-tools18/bin/sqlcmd -S 127.0.0.1 -C -U sa -l 3 -b -Q 'SELECT 1' 2>&1); then
      unset probe SA_PASS SQLCMDPASSWORD; return 0
    else rc=$?; fi
    case "$probe" in
      *18456*|*'Login failed'*|*'permission was denied'*|*'Error: 229'*)
        unset probe SA_PASS SQLCMDPASSWORD
        stage_fail "$rc" SQL_AUTHORIZATION_DENIED ;;
    esac
    unset probe
    sleep 2
  done
  unset SA_PASS SQLCMDPASSWORD
  stage_fail "$rc" SQL_NOT_READY
}

bootstrap_main() {
  set +x
  set -Eeuo pipefail
  umask 077
  unset SA_PASS SQLCMDPASSWORD probe
  exec >/var/log/ecs-recovery-bootstrap.log 2>&1
  chmod 0600 /var/log/ecs-recovery-bootstrap.log
  export DEBIAN_FRONTEND=noninteractive LC_ALL=C
  STAGE=initialization
  trap 'stage_fail "$?" UNEXPECTED' ERR
  run_stage platform check_platform
  run_stage fresh_host check_fresh_host
  run_stage base_index timeout 600 apt-get update -y
  run_stage base_packages timeout 600 apt-get install -y curl ca-certificates gnupg awscli
  run_stage repositories configure_repositories
  run_stage repository_access check_repository_access /etc/apt/keyrings/recovery-microsoft.gpg /etc/apt/sources.list.d/recovery-sql.list /etc/apt/sources.list.d/recovery-tools.list
  run_stage sql_index timeout 600 apt-get update -y
  run_stage sql_candidates check_candidates
  run_stage sql_dependencies timeout 60 apt-get -s install mssql-server mssql-tools18 unixodbc-dev
  run_stage sql_packages install_sql_packages
  run_stage sql_installation check_sql_installation
  # Only EC2 reads values. Secret stages never classify or print command output.
  secret_stage sa_secret read_sa_secret
  secret_stage express_setup setup_sql
  secret_stage sql_start systemctl start mssql-server
  secret_stage sql_memory /opt/mssql/bin/mssql-conf set memory.memorylimitmb 2048
  secret_stage sql_loopback /opt/mssql/bin/mssql-conf set network.ipaddress 127.0.0.1
  secret_stage sql_restart systemctl restart mssql-server
  STAGE=sql_readiness
  echo RECOVERY_STAGE_START stage=sql_readiness
  wait_sql
  run_stage sql_active systemctl is-active --quiet mssql-server
  echo RECOVERY_SQL_ENGINE_READY
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then bootstrap_main; fi
