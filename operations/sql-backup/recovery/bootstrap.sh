#!/bin/bash
# Public user-data only. No application DB, API or timer is created here.
set -euo pipefail
umask 077
exec >/var/log/ecs-recovery-bootstrap.log 2>&1
export DEBIAN_FRONTEND=noninteractive
trap 'unset SA_PASS SQLCMDPASSWORD; echo RECOVERY_BOOTSTRAP_FAILED' ERR
timeout 600 apt-get update -y >/dev/null 2>&1
timeout 600 apt-get install -y curl ca-certificates gnupg awscli >/dev/null 2>&1
install -d -m 0755 /etc/apt/keyrings
curl --max-time 30 -fsSL https://packages.microsoft.com/keys/microsoft.asc |
  gpg --dearmor -o /etc/apt/keyrings/recovery-microsoft.gpg
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/recovery-microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy main' >/etc/apt/sources.list.d/recovery-sql.list
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/recovery-microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main' >/etc/apt/sources.list.d/recovery-tools.list
timeout 600 apt-get update -y >/dev/null 2>&1
ACCEPT_EULA=Y timeout 900 apt-get install -y mssql-server mssql-tools18 unixodbc-dev >/dev/null 2>&1
# Future authorized runtime read; never print the value or SDK diagnostics.
SA_PASS=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-sa-password-30fCjc --query SecretString --output text 2>/dev/null)
test -n "$SA_PASS" && test "$SA_PASS" != None
ACCEPT_EULA=Y MSSQL_PID=Express MSSQL_SA_PASSWORD="$SA_PASS" timeout 180 /opt/mssql/bin/mssql-conf -n setup >/dev/null 2>&1
systemctl start mssql-server
/opt/mssql/bin/mssql-conf set memory.memorylimitmb 2048 >/dev/null 2>&1
/opt/mssql/bin/mssql-conf set network.ipaddress 127.0.0.1 >/dev/null 2>&1
systemctl restart mssql-server
export SQLCMDPASSWORD="$SA_PASS"
ready=0
for attempt in $(seq 1 90); do
  if probe=$(/opt/mssql-tools18/bin/sqlcmd -S 127.0.0.1 -C -U sa -l 3 -b -Q 'SELECT 1' 2>&1); then
    ready=1
    break
  fi
  if printf '%s' "$probe" | grep -Eq '18456|Login failed|permission was denied|Error: 229'; then
    unset probe SA_PASS SQLCMDPASSWORD
    echo RECOVERY_SQL_AUTHORIZATION_DENIED
    exit 1
  fi
  sleep 2
done
unset probe SA_PASS SQLCMDPASSWORD
test "$ready" = 1
echo RECOVERY_SQL_ENGINE_READY
