#!/usr/bin/env python3
"""Host steps for the native DEV owner. Never provisions, terminates or switches ECS.

The operator must separately authorize interruption, quiesce ECS, retain the source
disk, and prove EC2 termination before dispatching restore to the new instance.
Requests/receipts contain metadata only. A receipt hash is not authorization.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ACCOUNT = '341936017254'
REGION = 'us-east-1'
SA = f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/dev/db/sql-sa-password-30fCjc'
APP = f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/dev/db/sql-app-password-2Shh56'
MIGRATIONS = ['20251123201248_InitialMigration', '20260305033500_ExpandCipherTextColumn']


def require(condition, code):
    if not condition:
        raise ValueError(code)


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    # SQL package timestamps use seven fractional digits; Ubuntu Python 3.10
    # accepts six. Durations here are measured to microseconds, never rounded up.
    return dt.datetime.fromisoformat(re.sub(r'(\.\d{6})\d(?=Z|[+-])', r'\1', value).replace('Z', '+00:00'))


def validate(request, inspect=False):
    required = {'trial', 'instanceId', 'sourceInstanceId', 'sourceLaunchTime', 'targetAz',
                'expiresAt', 'sourceFence', 'backupReceipt', 'expectedRows', 'expectedDataHash'}
    require(set(request) == required, 'REQUEST_FIELDS')
    require(re.fullmatch('v2-[a-z0-9-]{1,40}', request['trial']), 'TRIAL_ID')
    require(all(re.fullmatch('i-[0-9a-f]{17}', request[k]) for k in ('instanceId', 'sourceInstanceId')), 'INSTANCE_ID')
    require(re.fullmatch('us-east-1[a-f]', request['targetAz']), 'AZ')
    require(dt.datetime.now(dt.timezone.utc) < timestamp(request['expiresAt']), 'WINDOW_EXPIRED')
    if inspect and request['expectedRows'] is None and request['expectedDataHash'] is None:
        return  # Read-only discovery has no fabricated data baseline.
    require(type(request['expectedRows']) is int and request['expectedRows'] >= 0 and
            re.fullmatch('[A-Fa-f0-9]{64}', request['expectedDataHash']), 'DATA_BASELINE')


def identity(request):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = opener.open(urllib.request.Request('http://169.254.169.254/latest/api/token', data=b'',
        method='PUT', headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'}), timeout=3).read().decode()
    doc = json.loads(opener.open(urllib.request.Request('http://169.254.169.254/latest/dynamic/instance-identity/document',
        headers={'X-aws-ec2-metadata-token': token}), timeout=3).read())
    require(doc['accountId'] == ACCOUNT and doc['region'] == REGION and
            doc['instanceId'] == request['instanceId'] and doc['availabilityZone'] == request['targetAz'], 'WRONG_HOST')
    return doc


def run(argv, *, data=None, env=None, timeout=660, **process_identity):
    result = subprocess.run(argv, input=data, env=env, capture_output=True, text=True,
                            timeout=timeout, **process_identity)
    if result.returncode != 0 and argv[0].endswith('/sqlcmd'):
        numbers = re.findall(r'\bMsg (\d{1,6})\b', result.stdout + result.stderr)
        require(not numbers, 'SQLCMD_ERROR_NUMBERS_' + '_'.join(numbers[:8]))
    require(result.returncode == 0, 'CHILD_FAILED_RECONCILE_BEFORE_RETRY')
    return result.stdout


class Sql:
    def __init__(self, instance):
        from botocore.session import Session
        from botocore.config import Config
        session = Session()
        config = Config(retries={'total_max_attempts': 1}, connect_timeout=8, read_timeout=30)
        caller = session.create_client('sts', region_name=REGION, config=config).get_caller_identity()
        require(caller['Arn'] == f'arn:aws:sts::{ACCOUNT}:assumed-role/demo-dev-data-sql-ec2-role/{instance}', 'WRONG_ROLE')
        self.sm = session.create_client('secretsmanager', region_name=REGION, config=config)

    def password(self, secret):
        require(secret in (SA, APP), 'SECRET_SCOPE')
        return self.sm.get_secret_value(SecretId=secret)['SecretString']

    def query(self, sql, database='master', runtime=False):
        require(database in ('master', 'demodb'), 'DATABASE_SCOPE')
        env = dict(os.environ, SQLCMDPASSWORD=self.password(APP if runtime else SA))
        try:
            output = run(['/opt/mssql-tools18/bin/sqlcmd', '-S', 'tcp:127.0.0.1,1433',
                '-N', '-F', 'sql.demo.internal', '-U', 'recovery_app' if runtime else 'sa',
                '-d', database, '-b', '-x', '-m', '11', '-h', '-1', '-w', '65535', '-y', '8000',
                '-l', '15', '-t', '180'], data='SET NOCOUNT ON; SET XACT_ABORT ON;\n' + sql,
                env=env, timeout=210)
        finally:
            env.pop('SQLCMDPASSWORD', None)
        return json.loads(''.join(output.splitlines()).strip())


SNAPSHOT = """
SELECT CONVERT(int,SERVERPROPERTY('EngineEdition')) AS edition,
 CONVERT(varchar(30),DATABASEPROPERTYEX('demodb','Updateability')) AS accessMode,
 (SELECT COUNT_BIG(*) FROM demodb.dbo.DemoTexts) AS rows,
 CONVERT(varchar(64),HASHBYTES('SHA2_256',(SELECT Id,Text,CreatedAt FROM demodb.dbo.DemoTexts ORDER BY Id FOR JSON PATH)),2) AS dataHash,
 JSON_QUERY((SELECT MigrationId FROM demodb.dbo.__EFMigrationsHistory ORDER BY MigrationId FOR JSON PATH)) AS migrations,
 (SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process=1 AND session_id<>@@SPID
   AND (database_id=DB_ID('demodb') OR login_name IN ('recovery_app','recovery_migrator'))) AS otherSessions,
 (SELECT is_disabled FROM sys.sql_logins WHERE name='recovery_app') AS runtimeDisabled
 FOR JSON PATH,WITHOUT_ARRAY_WRAPPER,INCLUDE_NULL_VALUES;
"""


def check_data(observed, request):
    require(observed['edition'] == 4 and observed['rows'] == request['expectedRows'] and
            observed['dataHash'].lower() == request['expectedDataHash'].lower() and
            [x['MigrationId'] for x in observed['migrations']] == MIGRATIONS, 'RESTORED_DATA_MISMATCH')


def restore_identity(directory):
    # SQL Server opens the downloaded backup and creates MDF/LDF itself. The
    # portable restore must therefore own its private files as the SQL service
    # user, not root. Keep the SA credential in the child environment only.
    import stat
    require(directory == Path('/var/opt/mssql/backup/v2-restores'), 'RESTORE_DIRECTORY_SCOPE')
    require(not any(p.is_symlink() for p in (directory, *directory.parents)), 'RESTORE_DIRECTORY_LINK')
    import pwd as unix_accounts
    who = unix_accounts.getpwnam('mssql')
    require(who.pw_uid != 0 and who.pw_gid != 0, 'SQL_SERVICE_IDENTITY')
    if not directory.exists():
        directory.mkdir(mode=0o700)
        os.chown(directory, who.pw_uid, who.pw_gid)
    observed = directory.stat()
    require(stat.S_ISDIR(observed.st_mode) and observed.st_uid == who.pw_uid and
            observed.st_gid == who.pw_gid and stat.S_IMODE(observed.st_mode) == 0o700,
            'EXISTING_RESTORE_DIRECTORY_REQUIRES_RECONCILIATION')
    return {'user': who.pw_uid, 'group': who.pw_gid, 'extra_groups': [], 'umask': 0o077}


def fence(sql, request):
    require(request['instanceId'] == request['sourceInstanceId'], 'SOURCE_HOST_REQUIRED')
    before = sql.query(SNAPSHOT)
    check_data(before, request)
    require(before['otherSessions'] == 0 and before['accessMode'] == 'READ_WRITE', 'SOURCE_NOT_QUIESCED')
    # A running Type=oneshot backup is "activating", not "active". Reject both
    # and every other transitional state before stopping its timer or fencing SQL.
    require(run(['systemctl', 'show', 'sql-backup.service', '--property=ActiveState', '--value']).strip() in ('inactive', 'failed'),
            'BACKUP_IN_PROGRESS')
    run(['systemctl', 'stop', 'sql-backup.timer'])
    # The timer may have fired between the first read and StopUnit. Stopping a
    # timer does not stop a service it already launched; recheck before SQL DDL.
    require(run(['systemctl', 'show', 'sql-backup.service', '--property=ActiveState', '--value']).strip() in ('inactive', 'failed'),
            'BACKUP_IN_PROGRESS')
    sql.query("ALTER LOGIN [recovery_app] DISABLE; ALTER LOGIN [recovery_migrator] DISABLE; "
              "ALTER DATABASE [demodb] SET READ_ONLY WITH NO_WAIT; SELECT 1 AS fenced FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;")
    after = sql.query(SNAPSHOT)
    check_data(after, request)
    require(after['runtimeDisabled'] is True and after['accessMode'] == 'READ_ONLY' and after['otherSessions'] == 0,
            'SOURCE_FENCE_UNCONFIRMED')
    # Produce the final restore point only after writers are positively excluded.
    started = stamp()
    run(['systemctl', 'start', 'sql-backup.service'])
    job = json.loads(Path('/var/opt/mssql/backup/v2/.service/last-job.json').read_text())
    require(job['Status'] == 'REMOTE_VERIFIED_CLEANUP_VERIFIED', 'FINAL_BACKUP_FAILED')
    receipt = json.loads(Path('/var/opt/mssql/backup/v2/last-success.json').read_text())
    require(timestamp(receipt['Manifest']['StartedUtc']) >= timestamp(started), 'OLD_BACKUP')
    return {'sourceFence': after, 'backupReceipt': receipt, 'fencedAt': started,
            'scope': 'SQL write fence; EC2 termination still required before restore'}


def restore(sql, request):
    require(request['instanceId'] != request['sourceInstanceId'], 'NEW_HOST_REQUIRED')
    proof = request['sourceFence']
    require(proof['ec2State'] == 'terminated' and proof['instanceId'] == request['sourceInstanceId'] and
            proof['launchTime'] == request['sourceLaunchTime'] and proof['retainedVolumeVerified'] is True,
            'POSITIVE_SOURCE_FENCE_REQUIRED')
    before = sql.query("SELECT (SELECT COUNT(*) FROM demodb.sys.tables WHERE is_ms_shipped=0) AS tables,"
        "(SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process=1 AND session_id<>@@SPID "
        "AND login_name IN ('recovery_app','recovery_migrator')) AS sessions,"
        "(SELECT is_disabled FROM sys.sql_logins WHERE name='recovery_app') AS disabled "
        "FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;")
    require(before == {'tables': 0, 'sessions': 0, 'disabled': True}, 'FRESH_DISABLED_TARGET_REQUIRED')
    target = 'demodb_restore_' + request['trial'].replace('-', '_')
    config = Path('/etc/terragrunt-demo/sql-backup/config.json')
    process_identity = restore_identity(Path(json.loads(config.read_text())['RestoreDirectory']))
    connection = 'Server=tcp:127.0.0.1,1433;Database=master;User Id=sa;Password="' + sql.password(SA).replace('"', '""') + '";Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.demo.internal;'
    env = dict(os.environ, SQL_RESTORE_CONNECTION_STRING=connection, AWS_EC2_METADATA_V1_DISABLED='true')
    connection = None
    receipt = request['backupReceipt']
    try:
        result = json.loads(run(['/opt/terragrunt-demo/sql-backup/bin/SqlBackup', 'restore', '--config', str(config),
            '--aws', '--ec2-role', '--manifest-key', receipt['ManifestKey'], '--manifest-version', receipt['ManifestVersion'],
            '--target', target], env=env, **process_identity))
    finally:
        env.pop('SQL_RESTORE_CONNECTION_STRING', None)
    require(result['Status'] == 'RESTORED_CHECKDB_READABLE' and result['Rows'] == request['expectedRows'], 'RESTORE_UNCONFIRMED')
    with (Path('/var/opt/mssql/backup/recovery-receipts') /
          (request['trial'] + '-native-restore.result.json')).open('x') as stream:
        json.dump({'completedAt': stamp(), 'restore': result,
                   'manifestVersion': receipt['ManifestVersion'], 'target': target}, stream)
    # Preserve the fresh empty bootstrap database, too. Never DROP or WITH REPLACE.
    # The final backup inherits the source READ_ONLY fence. Make only the restored
    # copy writable before renaming; application logins are still disabled.
    empty = 'demodb_bootstrap_' + request['trial'].replace('-', '_')
    sql.query(f"IF DB_ID(N'{empty}') IS NOT NULL THROW 51000,'EMPTY_TARGET_EXISTS',1; "
        f"ALTER DATABASE [{target}] SET READ_WRITE WITH NO_WAIT; "
        f"ALTER DATABASE [demodb] MODIFY NAME=[{empty}]; ALTER DATABASE [{target}] MODIFY NAME=[demodb]; "
        "SELECT 1 AS renamed FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;")
    sql.query("ALTER USER [recovery_app] WITH LOGIN=[recovery_app]; "
        "ALTER USER [recovery_migrator] WITH LOGIN=[recovery_migrator]; "
        "ALTER USER [td_backup_dev] WITH LOGIN=[td_backup_dev]; "
        "ALTER LOGIN [recovery_migrator] DISABLE; "
        "SELECT 1 AS remapped FOR JSON PATH,WITHOUT_ARRAY_WRAPPER;", database='demodb')
    after = sql.query(SNAPSHOT)
    check_data(after, request)
    require(after['runtimeDisabled'] is True, 'RUNTIME_PREMATURELY_ENABLED')
    return {'restore': result, 'data': after, 'emptyBootstrapDatabaseRetained': empty,
            'runtime': 'DISABLED_PENDING_HANDOFF'}


def main():
    import resource
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect', 'fence', 'restore'])
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    require(os.geteuid() == 0, 'ROOT_REQUIRED')
    request = json.loads(Path(args.request).read_text())
    validate(request, inspect=args.action == 'inspect')
    identity(request)
    sql = Sql(request['instanceId'])
    if args.action == 'inspect':
        print(json.dumps(sql.query(SNAPSHOT)))
        return
    directory = Path('/var/opt/mssql/backup/recovery-receipts')
    directory.mkdir(mode=0o700, exist_ok=True)
    intent = directory / (request['trial'] + '-' + args.action + '.intent.json')
    with intent.open('x') as stream:
        json.dump({'utc': stamp(), 'requestSha256': hashlib.sha256(Path(args.request).read_bytes()).hexdigest()}, stream)
    result = fence(sql, request) if args.action == 'fence' else restore(sql, request)
    result.update(completedAt=stamp(), instanceId=request['instanceId'], trial=request['trial'])
    with intent.with_name(intent.name.replace('.intent.', '.result.')).open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) and re.fullmatch(r'SQLCMD_ERROR_NUMBERS_[0-9_]+', str(error)) else None
        print('NATIVE_RECOVERY_FAILED_OR_UNCERTAIN; inspect metadata before any further mutation' +
              (('; ' + code) if code else ''))
        raise SystemExit(1)
