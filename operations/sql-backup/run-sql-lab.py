"""Isolated SQL Express test. Requires explicit EULA acceptance; never uses AWS.

Creates/removes only UUID-labelled Docker resources owned by this invocation.
Credentials are random process environment values, never argv/files/output.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import uuid

TERMS = 'https://www.microsoft.com/content/dam/microsoft/usetm/documents/sql-server/sql-server-2022-developer-express-evaluation/retail-packaged/SQLServer2022_SQLServer2022DeveloperExpressEvaluation_English.pdf'
SQL_IMAGE = 'mcr.microsoft.com/mssql/server@sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89'
SDK_IMAGE = 'mcr.microsoft.com/dotnet/sdk:10.0.402@sha256:3a48280a9a7c6276c3eeaba1efa6a08820f18c84fb9e6274c187719ecfaf9fbc'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accept-sql-eula', action='store_true')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    if not args.accept_sql_eula:
        parser.error('Explicit Microsoft SQL Server 2022 Express EULA acceptance is required')
    if shutil.disk_usage('/').free < 3 * 1024**3:
        raise SystemExit('Insufficient space: leave at least 3 GiB before creating the lab')
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
    if available < 4 * 1024**3:
        raise SystemExit('Insufficient available memory for the isolated lab')
    source = args.source.resolve(strict=True); results = args.results.resolve(strict=True)
    cache = (source.parent / 'temp/terragrunt-demo-dotnet10').resolve(strict=True)
    assert (source / 'operations/sql-backup/SqlBackup.Tests/SqlBackup.Tests.csproj').is_file()
    identity = uuid.uuid4().hex
    label = 'com.terragrunt-demo.sql-backup-lab=' + identity
    container, volume, runner = ('terragrunt-demo-sql-lab-' + identity[:12], 'terragrunt-demo-sql-data-' + identity[:12], 'terragrunt-demo-sql-test-' + identity[:12])
    report = {'EulaAccepted': True, 'AcceptedUtc': datetime.now(timezone.utc).isoformat(), 'Terms': TERMS, 'TermsDate': '2022-10-21', 'EditionRequested': 'Express', 'Image': SQL_IMAGE,
              'Network': 'none; runner shares only SQL network namespace', 'PublishedPorts': [], 'SqlContainer': container, 'DataVolume': volume, 'CleanupVerified': False}
    report['CliAssemblySha256'] = hashlib.sha256((source / 'operations/sql-backup/SqlBackup/bin/Release/net10.0/SqlBackup.dll').read_bytes()).hexdigest()
    report['TestAssemblySha256'] = hashlib.sha256((source / 'operations/sql-backup/SqlBackup.Tests/bin/Release/net10.0/SqlBackup.Tests.dll').read_bytes()).hexdigest()
    created_container = created_volume = False
    def docker(*command, **kwargs):
        return subprocess.run(['docker', *command], text=True, capture_output=True, **kwargs)
    def required(*command, **kwargs):
        result = docker(*command, **kwargs)
        if result.returncode:
            raise RuntimeError('Docker operation failed: ' + command[0] + '; inspect local lab log')
        return result.stdout
    try:
        for kind, name in (('container', container), ('container', runner), ('volume', volume)):
            assert docker(kind, 'inspect', name).returncode != 0, 'Unexpected pre-existing resource'
        required('image', 'inspect', SQL_IMAGE)
        required('volume', 'create', '--label', label, volume); created_volume = True
        sql_env = dict(os.environ, MSSQL_SA_PASSWORD='Synthetic!' + secrets.token_hex(24))
        required('run', '-d', '--name', container, '--label', label, '--network', 'none', '--memory', '3g',
                 '-e', 'ACCEPT_EULA=Y', '-e', 'MSSQL_PID=Express', '-e', 'MSSQL_SA_PASSWORD', '-e', 'MSSQL_MEMORY_LIMIT_MB=1024',
                 '--mount', f'type=volume,source={volume},target=/var/opt/mssql', SQL_IMAGE, env=sql_env)
        created_container = True
        ready = False
        for _ in range(90):
            logs = required('logs', container)
            if 'SQL Server is now ready for client connections' in logs:
                ready = True; break
            time.sleep(2)
        (results / 'sql-startup.log').write_text(required('logs', container))
        if not ready:
            raise RuntimeError('Isolated SQL Express did not become ready')
        assert required('exec', container, 'id', '-u').strip() == '10001', 'Unexpected SQL OS identity'
        sql_gid = required('exec', container, 'id', '-g').strip()
        assert sql_gid.isdecimal(), 'Unexpected SQL OS group'
        # Only inside our new labelled volume: provision a private directory owned
        # by the same UID as SQL and the test process. No host/shared permissions.
        required('exec', '--user', '0', container, 'install', '-d', '-m', '0700', '-o', '10001', '-g', sql_gid, '/var/opt/mssql/v2-lab')
        print('ISOLATED_SQL_EXPRESS_READY; EULA accepted; no published ports', flush=True)
        connection = f'Server=127.0.0.1,1433;User ID=sa;Password={sql_env["MSSQL_SA_PASSWORD"]};Encrypt=True;TrustServerCertificate=True;Connect Timeout=10'
        test_env = dict(os.environ, SQL_BACKUP_INTEGRATION_CONNECTION=connection)
        run = docker('run', '--rm', '--name', runner, '--label', label, '--user', '10001:' + sql_gid, '--network', 'container:' + container,
                     '--volumes-from', container, '--mount', f'type=bind,source={source},target=/src,readonly',
                     '--mount', f'type=bind,source={results},target=/work', '-w', '/src',
                     '--mount', f'type=bind,source={cache},target=/cache,readonly',
                     '-e', 'SQL_BACKUP_INTEGRATION_CONNECTION', '-e', 'SQL_BACKUP_INTEGRATION_STAGING=/var/opt/mssql/v2-lab',
                     '-e', 'NUGET_PACKAGES=/cache/nuget', '-e', 'DOTNET_CLI_HOME=/tmp/dotnet-home',
                     '-e', 'DOTNET_CLI_TELEMETRY_OPTOUT=1', '-e', 'AWS_EC2_METADATA_DISABLED=true', SDK_IMAGE,
                     # Invoke the already-built test assembly directly: no SDK first-use
                     # migration under the SQL UID and no writes to the source/cache.
                     'dotnet', '/usr/share/dotnet/sdk/10.0.402/vstest.console.dll',
                     '/src/operations/sql-backup/SqlBackup.Tests/bin/Release/net10.0/SqlBackup.Tests.dll',
                     '/TestCaseFilter:FullyQualifiedName~SqlExpressIntegrationTests', '/Logger:trx', '/ResultsDirectory:/work/SqlTestResults', env=test_env)
        (results / 'sql-integration.log').write_text(run.stdout + run.stderr)
        report['TestExitCode'] = run.returncode
        print(run.stdout + run.stderr, flush=True)
        if run.returncode:
            raise RuntimeError('Native SQL integration failed; resources will be retired')
    finally:
        # Validate our unique ownership labels before removing only our resources.
        for name in (runner, container):
            existing = docker('container', 'inspect', name)
            if existing.returncode == 0:
                metadata = json.loads(existing.stdout)[0]
                assert metadata['Config']['Labels'].get('com.terragrunt-demo.sql-backup-lab') == identity
                required('rm', '-f', name)
        if created_volume:
            metadata = json.loads(required('volume', 'inspect', volume))[0]
            assert metadata['Labels'].get('com.terragrunt-demo.sql-backup-lab') == identity
            required('volume', 'rm', volume)
        report['CleanupVerified'] = all(docker(kind, 'inspect', name).returncode != 0 for kind, name in (('container', runner), ('container', container), ('volume', volume)))
        report['FreeBytesAfterCleanup'] = shutil.disk_usage('/').free
        (results / 'sql-lab-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    main()
