#!/usr/bin/env bash
# Sourceable bootstrap/adoption primitives only. Sourcing does not connect or apply.
# Future execution requires admitted deployment/host control; an acknowledgement is not authority.

sql_principals_validate() {
  [[ "$APP_DB" =~ ^[A-Za-z_][A-Za-z0-9_]{0,63}$ &&
     "$APP_USER" =~ ^[A-Za-z_][A-Za-z0-9_]{0,63}$ &&
     "$MIGRATION_USER" =~ ^[A-Za-z_][A-Za-z0-9_]{0,63}$ ]] || return 64
  local runtime_lower="${APP_USER,,}" migration_lower="${MIGRATION_USER,,}" database_lower="${APP_DB,,}"
  [[ "$runtime_lower" != sa && "$migration_lower" != sa && "$runtime_lower" != "$migration_lower" ]] || return 64
  case "$database_lower" in master|model|msdb|tempdb) return 64 ;; esac
}

sql_principals_is_root() { [[ "$EUID" == 0 ]]; }

sql_principals_execute() {
  # SQLCMDPASSWORD is supplied to the existing admin process, never an argv password.
  # -x prevents sqlcmd variable expansion inside supplied password values.
  [[ -n "${SQLCMDPASSWORD:-}" ]] || return 64
  command sqlcmd -S tcp:127.0.0.1,1433 -C -U SA -d "$APP_DB" -b -x -l 15 -t 30 >/dev/null 2>&1
}

sql_principals_gate() {
  [[ "${1:-}" == --ack-reviewed-sql-privilege-change ]] &&
    sql_principals_validate && sql_principals_is_root && [[ -n "${SQLCMDPASSWORD:-}" ]]
}

sql_principals_prepare() {
  set +x
  sql_principals_gate "${1:-}" || return 64
  [[ -n "${APP_PASS:-}" && -n "${MIGRATION_PASS:-}" &&
     "$APP_PASS" != *$'\n'* && "$APP_PASS" != *$'\r'* &&
     "$MIGRATION_PASS" != *$'\n'* && "$MIGRATION_PASS" != *$'\r'* ]] || return 64
  local runtime_password="${APP_PASS//\'/\'\'}" migration_password="${MIGRATION_PASS//\'/\'\'}"
  # No automatic retry or password rotation. Execute only after the application is
  # quiesced by its admitted owner. The SQL observation below is not fencing proof.
  if sql_principals_execute <<SQL
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_ID(N'$APP_DB') IS NULL THROW 51000, 'DATABASE_MUST_EXIST', 1;
IF EXISTS (SELECT 1 FROM sys.dm_exec_sessions WHERE is_user_process = 1
  AND login_name IN (N'$APP_USER', N'$MIGRATION_USER'))
  THROW 51000, 'APPLICATION_SESSIONS_MUST_BE_QUIESCED', 1;
IF EXISTS (SELECT 1 FROM sys.databases WHERE name=N'$APP_DB'
  AND owner_sid IN (SUSER_SID(N'$APP_USER'), SUSER_SID(N'$MIGRATION_USER')))
  THROW 51000, 'APPLICATION_LOGIN_MUST_NOT_OWN_DATABASE', 1;
BEGIN TRANSACTION;
IF SUSER_ID(N'$APP_USER') IS NULL
  CREATE LOGIN [$APP_USER] WITH PASSWORD=N'$runtime_password', CHECK_POLICY=ON;
IF SUSER_ID(N'$MIGRATION_USER') IS NULL
  CREATE LOGIN [$MIGRATION_USER] WITH PASSWORD=N'$migration_password', CHECK_POLICY=ON;
ALTER LOGIN [$APP_USER] DISABLE;
IF USER_ID(N'$APP_USER') IS NULL CREATE USER [$APP_USER] FOR LOGIN [$APP_USER];
IF USER_ID(N'$MIGRATION_USER') IS NULL CREATE USER [$MIGRATION_USER] FOR LOGIN [$MIGRATION_USER];
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name=N'$APP_USER'
  AND sid<>SUSER_SID(N'$APP_USER')) OR EXISTS (SELECT 1 FROM sys.database_principals
  WHERE name=N'$MIGRATION_USER' AND sid<>SUSER_SID(N'$MIGRATION_USER'))
  THROW 51000, 'DATABASE_LOGIN_BINDING_MISMATCH', 1;
IF EXISTS (SELECT 1 FROM sys.server_role_members WHERE member_principal_id
  IN (SUSER_ID(N'$APP_USER'), SUSER_ID(N'$MIGRATION_USER')))
  THROW 51000, 'APPLICATION_SERVER_ROLE_FORBIDDEN', 1;
IF EXISTS (SELECT 1 FROM sys.server_permissions WHERE grantee_principal_id
  IN (SUSER_ID(N'$APP_USER'), SUSER_ID(N'$MIGRATION_USER')) AND permission_name<>'CONNECT SQL')
  THROW 51000, 'APPLICATION_SERVER_PERMISSION_FORBIDDEN', 1;
IF EXISTS (SELECT 1 FROM sys.schemas WHERE principal_id=USER_ID(N'$APP_USER')) OR
  EXISTS (SELECT 1 FROM sys.objects WHERE principal_id=USER_ID(N'$APP_USER'))
  THROW 51000, 'RUNTIME_MUST_NOT_OWN_SECURABLES', 1;
IF COALESCE(IS_ROLEMEMBER(N'db_owner',N'$APP_USER'),-1) NOT IN (0,1)
  THROW 51000, 'RUNTIME_ROLE_EVIDENCE_UNKNOWN', 1;
IF IS_ROLEMEMBER(N'db_owner',N'$APP_USER')=1 ALTER ROLE db_owner DROP MEMBER [$APP_USER];
IF EXISTS (SELECT 1 FROM sys.database_role_members WHERE member_principal_id=USER_ID(N'$APP_USER'))
  THROW 51000, 'UNREVIEWED_RUNTIME_ROLE', 1;
IF EXISTS (SELECT 1 FROM sys.database_permissions WHERE grantee_principal_id=USER_ID(N'$APP_USER')
  AND NOT ((class=0 AND permission_name='CONNECT' AND state='G') OR
    (class=1 AND major_id=OBJECT_ID(N'dbo.DemoTexts') AND minor_id=0
     AND permission_name IN ('SELECT','INSERT') AND state='G')))
  THROW 51000, 'UNREVIEWED_RUNTIME_PERMISSION', 1;
IF EXISTS (SELECT 1 FROM sys.database_role_members membership JOIN sys.database_principals role
  ON role.principal_id=membership.role_principal_id WHERE membership.member_principal_id=USER_ID(N'$MIGRATION_USER')
  AND role.name<>'db_ddladmin') THROW 51000, 'UNREVIEWED_MIGRATION_ROLE', 1;
IF COALESCE(IS_ROLEMEMBER(N'db_ddladmin',N'$MIGRATION_USER'),-1) NOT IN (0,1)
  THROW 51000, 'MIGRATION_ROLE_EVIDENCE_UNKNOWN', 1;
IF IS_ROLEMEMBER(N'db_ddladmin',N'$MIGRATION_USER')=0 ALTER ROLE db_ddladmin ADD MEMBER [$MIGRATION_USER];
GRANT SELECT, INSERT, DELETE ON SCHEMA::dbo TO [$MIGRATION_USER];
ALTER LOGIN [$MIGRATION_USER] ENABLE;
COMMIT TRANSACTION;
SQL
  then :; else
    printf '%s\n' SQL_PRINCIPALS_PREPARE_FAILED_OUTCOME_REQUIRES_READBACK >&2
    return 65
  fi
}

sql_principals_activate_runtime() {
  set +x
  sql_principals_gate "${1:-}" || return 64
  if sql_principals_execute <<SQL
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name=N'$APP_USER' AND is_disabled=1)
  THROW 51000, 'RUNTIME_MUST_REMAIN_DISABLED_UNTIL_ADOPTION', 1;
IF EXISTS (SELECT 1 FROM sys.dm_exec_sessions WHERE is_user_process=1
  AND login_name IN (N'$APP_USER',N'$MIGRATION_USER'))
  THROW 51000, 'APPLICATION_SESSIONS_MUST_BE_QUIESCED', 1;
IF OBJECT_ID(N'dbo.__EFMigrationsHistory') IS NULL OR OBJECT_ID(N'dbo.DemoTexts') IS NULL
  THROW 51000, 'SCHEMA_MIGRATION_REQUIRED', 1;
IF (SELECT COUNT(*) FROM dbo.__EFMigrationsHistory)<>2 OR
  NOT EXISTS (SELECT 1 FROM dbo.__EFMigrationsHistory WHERE MigrationId=N'20251123201248_InitialMigration') OR
  NOT EXISTS (SELECT 1 FROM dbo.__EFMigrationsHistory WHERE MigrationId=N'20260305033500_ExpandCipherTextColumn') OR
  COALESCE(COL_LENGTH(N'dbo.DemoTexts', N'Text'),0)<>-1
  THROW 51000, 'REVIEWED_SCHEMA_REQUIRED', 1;
IF COALESCE(IS_ROLEMEMBER(N'db_owner',N'$APP_USER'),-1)<>0 OR
  EXISTS (SELECT 1 FROM sys.database_role_members WHERE member_principal_id=USER_ID(N'$APP_USER'))
  THROW 51000, 'RUNTIME_ROLE_NOT_MINIMAL', 1;
BEGIN TRANSACTION;
GRANT SELECT, INSERT ON OBJECT::dbo.DemoTexts TO [$APP_USER];
ALTER LOGIN [$MIGRATION_USER] DISABLE;
ALTER LOGIN [$APP_USER] ENABLE;
COMMIT TRANSACTION;
SQL
  then :; else
    printf '%s\n' SQL_PRINCIPALS_ACTIVATE_FAILED_OUTCOME_REQUIRES_READBACK >&2
    return 65
  fi
}
