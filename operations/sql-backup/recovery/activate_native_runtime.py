#!/usr/bin/env python3
"""Activate only a verified restored DEV database using the existing SQL handoff.

Positional arguments: private request path, sql-principals.sh path, its LF SHA256.
The request is metadata, never an authorization or a credential. Run on the new
host only after native_step restore succeeded. This wrapper preserves grants,
uses validated SQL TLS and reads credentials in memory through the SQL role.
"""

def require(condition, code):
    if not condition:
        raise ValueError(code)


def main():
    import os,sys,json,pathlib,subprocess,hashlib,resource,re
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.umask(0o077)
    request=json.loads(pathlib.Path(sys.argv[1]).read_text())
    require(re.fullmatch('v2-[a-z0-9-]{1,40}', request['trial']), 'HANDOFF_PRECONDITION_FAILED')
    sys.path.insert(0,'/run/'+request['trial']+'-restore')
    from native_host import Sql,SNAPSHOT,check_data,identity,validate,SA
    validate(request)
    identity(request);sql=Sql(request['instanceId']);before=sql.query(SNAPSHOT);check_data(before,request)
    require(before['runtimeDisabled'] is True and before['otherSessions']==0 and before['accessMode']=='READ_WRITE', 'HANDOFF_PRECONDITION_FAILED')
    permissions=sql.query("""SELECT
     (SELECT COUNT(*) FROM sys.database_role_members WHERE member_principal_id=USER_ID('recovery_app')) AS databaseRoles,
     (SELECT COUNT(*) FROM sys.server_role_members WHERE member_principal_id=SUSER_ID('recovery_app')) AS serverRoles,
     (SELECT COUNT(*) FROM sys.server_permissions WHERE grantee_principal_id=SUSER_ID('recovery_app') AND permission_name<>'CONNECT SQL') AS elevatedServerGrants,
     CASE WHEN EXISTS(SELECT 1 FROM sys.databases WHERE name=DB_NAME() AND owner_sid=SUSER_SID('recovery_app')) THEN 1 ELSE 0 END AS ownsDatabase,
     JSON_QUERY((SELECT p.state,p.permission_name,OBJECT_SCHEMA_NAME(p.major_id) AS schemaName,OBJECT_NAME(p.major_id) AS objectName,p.class,p.minor_id FROM sys.database_permissions p WHERE p.grantee_principal_id=USER_ID('recovery_app') ORDER BY p.permission_name,p.major_id FOR JSON PATH,INCLUDE_NULL_VALUES)) AS grants
     FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;""",database='demodb')
    require(all(permissions[k]==0 for k in ['databaseRoles','serverRoles','elevatedServerGrants','ownsDatabase']), 'HANDOFF_PRECONDITION_FAILED')
    expected={('DemoTexts','SELECT'),('DemoTexts','INSERT'),('__EFMigrationsHistory','SELECT')}
    observed=set()
    for g in permissions['grants']:
     if g['class']==0 and g['permission_name']=='CONNECT' and g['state']=='G':continue
     require(g['class']==1 and g['schemaName']=='dbo' and g['state']=='G' and g['minor_id']==0, 'HANDOFF_PRECONDITION_FAILED')
     observed.add((g['objectName'],g['permission_name']))
    require(observed==expected, 'HANDOFF_PRECONDITION_FAILED')
    helper=pathlib.Path(sys.argv[2]);require(hashlib.sha256(helper.read_bytes()).hexdigest()==sys.argv[3], 'HANDOFF_PRECONDITION_FAILED')
    command="""set +x
    set -eu
    source "$1"
    APP_DB=demodb
    APP_USER=recovery_app
    MIGRATION_USER=recovery_migrator
    sql_principals_execute() {
     /opt/mssql-tools18/bin/sqlcmd -S tcp:127.0.0.1,1433 -N -F sql.demo.internal -U sa -d demodb -b -x -l 15 -t 30 >/dev/null 2>&1
    }
    sql_principals_activate_runtime --ack-reviewed-sql-privilege-change
    """
    env=dict(os.environ,SQLCMDPASSWORD=sql.password(SA))
    try:
     result=subprocess.run(['bash','-c',command,'recovery-handoff',str(helper)],env=env,capture_output=True,timeout=90)
     require(result.returncode==0, 'HANDOFF_FAILED_OR_UNCERTAIN')
    finally:env.pop('SQLCMDPASSWORD',None)
    after=sql.query(SNAPSHOT);check_data(after,request);require(after['runtimeDisabled'] is False and after['otherSessions']==0, 'HANDOFF_PRECONDITION_FAILED')
    state=sql.query("SELECT is_disabled AS disabled FROM sys.sql_logins WHERE name='recovery_migrator' FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;");require(state['disabled'] is True, 'HANDOFF_PRECONDITION_FAILED')
    effective=sql.query("""SELECT ORIGINAL_LOGIN() AS loginName,DB_NAME() AS databaseName,
     HAS_PERMS_BY_NAME('dbo.DemoTexts','OBJECT','SELECT') AS canSelect,
     HAS_PERMS_BY_NAME('dbo.DemoTexts','OBJECT','INSERT') AS canInsert,
     HAS_PERMS_BY_NAME('dbo.DemoTexts','OBJECT','UPDATE') AS canUpdate,
     HAS_PERMS_BY_NAME('dbo.DemoTexts','OBJECT','DELETE') AS canDelete,
     HAS_PERMS_BY_NAME('dbo.DemoTexts','OBJECT','ALTER') AS canAlter,
     HAS_PERMS_BY_NAME('dbo.__EFMigrationsHistory','OBJECT','SELECT') AS canReadMigrationMetadata,
     HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL') AS databaseControl,
     HAS_PERMS_BY_NAME(NULL,NULL,'CONTROL SERVER') AS serverControl,
     IS_ROLEMEMBER('db_owner') AS dbOwner,IS_ROLEMEMBER('db_ddladmin') AS ddlAdmin,
     (SELECT COUNT_BIG(*) FROM dbo.DemoTexts) AS rows,
     (SELECT COUNT(*) FROM dbo.__EFMigrationsHistory) AS migrations
     FOR JSON PATH,WITHOUT_ARRAY_WRAPPER,INCLUDE_NULL_VALUES;""",database='demodb',runtime=True)
    require(effective['loginName']=='recovery_app' and effective['databaseName']=='demodb', 'HANDOFF_PRECONDITION_FAILED')
    require(all(effective[k]==1 for k in ['canSelect','canInsert','canReadMigrationMetadata']), 'HANDOFF_PRECONDITION_FAILED')
    require(all(effective[k]==0 for k in ['canUpdate','canDelete','canAlter','databaseControl','serverControl','dbOwner','ddlAdmin']), 'HANDOFF_PRECONDITION_FAILED')
    require(effective['rows']==request['expectedRows'] and effective['migrations']==2, 'HANDOFF_PRECONDITION_FAILED')
    print(json.dumps({'status':'HANDOFF_STRICT_RUNTIME_READ_PASS','grantsPreserved':permissions,'effective':effective,'dataHash':after['dataHash'],'migratorDisabled':True,'newApplicationWrites':0}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("HANDOFF_FAILED_OR_UNCERTAIN; reconcile before any retry")
        raise SystemExit(1)
