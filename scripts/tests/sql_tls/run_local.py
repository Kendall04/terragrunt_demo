"""Opt-in SQL 2022 integration. Local Docker only; disposable identities/data.

Runs the real API image ENTRYPOINT and SqlClient admission query. No AWS calls,
ports, real secrets, shared Docker volumes, or readiness/KMS success claims.
Requires an already built image ID and SQL image; never pulls/builds implicitly.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
SQL_IMAGE = 'mcr.microsoft.com/mssql/server@sha256:cf8f0ab2ebe61feec2eed2629061a07d247f791c2a8ddda74a4ac9f06a291718'
HOST = 'sql.demo.internal'  # Same SAN in BOTH disposable issuers, not production identity.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', required=True, help='Exact local sha256 image ID')
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', a.image):
        p.error('An immutable local image ID is required')
    output = a.output.resolve()
    if output == ROOT or ROOT in output.parents:
        p.error('Evidence must be outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    docker = ['docker']
    if os.name == 'nt': docker += ['--host', 'npipe:////./pipe/docker_engine']
    openssl = shutil.which('openssl')
    if not openssl: p.error('OpenSSL executable required')

    def run(command, *, stdin=None, check=True, timeout=120):
        result = subprocess.run(command, input=stdin, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=timeout)
        if check and result.returncode:
            # Never include argv, environment, stdin or server logs in errors.
            raise RuntimeError('Local command failed: ' + Path(command[0]).name)
        return result

    def d(*args, **kw): return run(docker + list(args), **kw)
    image_metadata = json.loads(d('image', 'inspect', a.image).stdout)[0]
    if image_metadata['Config']['User'] != '1654' or image_metadata['Config']['Entrypoint'] != ['/app/entrypoint.sh']:
        p.error('Expected common nonroot image ENTRYPOINT')
    deps = json.loads(d('run', '--rm', '--pull', 'never', '--network', 'none', '--entrypoint', 'cat',
                       a.image, '/app/terragrunt-demo.deps.json').stdout)
    if 'Microsoft.Data.SqlClient/6.1.7' not in deps['libraries']:
        p.error('SqlClient version mismatch in image')
    cleanliness = d('run', '--rm', '--pull', 'never', '--network', 'none', '--entrypoint', '/bin/sh', a.image,
                    '-c', 'test ! -e /usr/local/share/ca-certificates/ecs-sql-lab.crt && test ! -e /app/deploy/trust/sql.demo.internal.crt && test -s /etc/ssl/certs/ca-certificates.crt')
    d('image', 'inspect', SQL_IMAGE)
    prefix = 'ecs-tls-' + uuid.uuid4().hex[:10]
    network = prefix + '-net'
    containers = set()
    results = []
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        d('network', 'create', '--internal', '--label', 'ecs-sql-tls-disposable=true', network)
        with tempfile.TemporaryDirectory(prefix=prefix) as temp:
            work = Path(temp)
            roots = {}
            for env in ('dev', 'prod'):
                folder = work / env; folder.mkdir()
                run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                     '-days', '2', '-subj', '/CN=Disposable-' + env + '-TLS-test-root',
                     '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
                     '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
                     '-keyout', str(folder/'ca.key'), '-out', str(folder/'ca.crt')])
                run([openssl, 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-sha256',
                     '-subj', '/CN=' + HOST, '-keyout', str(folder/'server.key'),
                     '-out', str(folder/'server.csr')])
                (folder/'extensions').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:'+HOST+'\n')
                run([openssl, 'x509', '-req', '-in', str(folder/'server.csr'),
                     '-CA', str(folder/'ca.crt'), '-CAkey', str(folder/'ca.key'),
                     '-set_serial', '0x'+secrets.token_hex(16), '-days', '1', '-sha256',
                     '-extfile', str(folder/'extensions'), '-out', str(folder/'server.crt')])
                run([openssl, 'x509', '-in', str(folder/'ca.crt'), '-outform', 'DER', '-out', str(folder/'ca.der')])
                raw = (folder/'ca.der').read_bytes()
                roots[env] = dict(kind='ca', sha256=hashlib.sha256(raw).hexdigest(), der_base64=base64.b64encode(raw).decode())
                (folder/'mssql.conf').write_text('[network]\ntlscert = /var/opt/mssql/server.crt\ntlskey = /var/opt/mssql/server.key\ntlsprotocols = 1.2\nforceencryption = 1\n')

            password = 'Local!' + secrets.token_hex(16)
            sa = 'Local!' + secrets.token_hex(16)
            sqlenv = work/'sql.env'
            sqlenv.write_text('ACCEPT_EULA=Y\nMSSQL_PID=Express\nMSSQL_MEMORY_LIMIT_MB=1024\nMSSQL_SA_PASSWORD='+sa+'\n')

            def manifest(env):
                return dict(schema='SQL_TLS_TRUST_V1', environment=env, version='disposable-v1', hostname=HOST, anchors=[roots[env].copy()])

            def test(name, env, expected, *, edit=None, trust_edit=None, profile='validated-v2', hostname=HOST, bridge=False, command=()):
                trust = manifest(env)
                trust['hostname'] = hostname
                if bridge:
                    pub = ROOT/'demo-api/deploy/trust/sql.demo.internal.crt'
                    der = work/'historical.der'
                    run([openssl, 'x509', '-in', str(pub), '-outform', 'DER', '-out', str(der)])
                    raw = der.read_bytes()
                    trust['anchors'].append(dict(kind='dev-leaf-transition', sha256=hashlib.sha256(raw).hexdigest(), der_base64=base64.b64encode(raw).decode()))
                    now = dt.datetime.now(dt.timezone.utc)
                    stamp = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
                    trust['transition'] = dict(not_before=stamp(now-dt.timedelta(minutes=1)), not_after=stamp(now+dt.timedelta(minutes=30)))
                if trust_edit: trust_edit(trust)
                raw = json.dumps(trust, separators=(',', ':')).encode()
                settings = {
                    'APP_ENV': env, 'AWS_REGION': 'us-east-1', 'AWS_EC2_METADATA_DISABLED': 'true',
                    'Database__SecurityProfile': profile, 'Database__RunMigrationsOnStartup': 'false',
                    'Database__ExpectedSqlEndpoint': 'tcp:sql-server,1433',
                    'Database__ExpectedDatabase': 'demodb', 'Database__ExpectedRuntimeUser': 'app_runtime',
                    'Database__ExpectedCertificateHostName': hostname,
                    'DB_CONN_STRING': 'Server=tcp:sql-server,1433;Database=demodb;User Id=app_runtime;Password='+password+';Encrypt=True;TrustServerCertificate=False;HostNameInCertificate='+hostname+';Pooling=False;Connect Timeout=5;ConnectRetryCount=0',
                    'SQL_TRUST_MANIFEST_B64': base64.b64encode(raw).decode(),
                    'SQL_TRUST_MANIFEST_SHA256': hashlib.sha256(raw).hexdigest()
                }
                if edit: edit(settings)
                envfile = work/(name+'.env')
                envfile.write_text('\n'.join(k+'='+v for k,v in settings.items())+'\n')
                container = prefix+'-'+name; containers.add(container)
                d('run', '-d', '--pull', 'never', '--name', container, '--network', network,
                  '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--env-file', str(envfile), a.image, *command)
                until = time.monotonic()+35
                logs = ''
                while time.monotonic() < until:
                    captured = d('logs', container)
                    logs = captured.stdout + captured.stderr
                    if expected in logs: break
                    if d('inspect', container, '--format', '{{.State.Running}}').stdout.strip() == 'false': break
                    time.sleep(.25)
                # The process can exit between a log read and inspect; collect its
                # final stderr before classifying a refusal or timed shutdown.
                captured = d('logs', container)
                logs = captured.stdout + captured.stderr
                forbidden = [password, sa, 'BEGIN PRIVATE KEY']
                if any(x in logs for x in forbidden): raise RuntimeError('Sensitive output suppressed')
                (output/(name+'.log')).write_text(logs)
                image = d('inspect', container, '--format', '{{.Image}}').stdout.strip()
                passed = expected in logs and image == a.image
                if expected not in ('DATABASE_RUNTIME_ADMITTED', 'SQL_TRUST_TRANSITION_EXPIRED'):
                    passed = passed and 'DATABASE_RUNTIME_ADMITTED' not in logs and 'Now listening on' not in logs
                if expected == 'SQL_TRUST_TRANSITION_EXPIRED':
                    passed = passed and 'DATABASE_RUNTIME_ADMITTED' in logs
                    d('wait', container, timeout=10)
                if expected == 'DATABASE_TLS_HANDSHAKE_REFUSED':
                    passed = passed and 'System.Security.Authentication.AuthenticationException' in logs
                results.append(dict(case=name, environment=env, expected=expected, passed=passed,
                                    image=image, fresh_process=True, pooling=False,
                                    server_issuer=issuer, hostname=hostname,
                                    trust_roots=[x['sha256'] for x in trust['anchors']],
                                    log_sha256=hashlib.sha256(logs.encode()).hexdigest(),
                                    timestamp=dt.datetime.now(dt.timezone.utc).isoformat()))
                print(name + ': ' + ('PASS' if passed else 'FAIL'), flush=True)
                d('rm', '-f', '-v', container); containers.remove(container)

            for issuer in ('prod', 'dev'):
                folder = work/issuer; server = prefix+'-sql'; containers.add(server)
                mounts=[]
                for filename in ('server.crt','server.key','mssql.conf'):
                    mounts += ['--mount', 'type=bind,source='+str(folder/filename)+',target=/input/'+filename+',readonly']
                d('run', '-d', '--pull', 'never', '--name', server, '--network', network,
                  '--network-alias', 'sql-server', '--hostname', HOST, '--memory', '4g',
                  '--env-file', str(sqlenv), '--tmpfs', '/var/opt/mssql:uid=10001,gid=0,mode=0700,size=2g',
                  *mounts, '--entrypoint', '/bin/bash', SQL_IMAGE, '-c',
                  'umask 077; cp /input/server.crt /input/server.key /input/mssql.conf /var/opt/mssql/; chmod 600 /var/opt/mssql/server.key; exec /opt/mssql/bin/sqlservr')
                sqlcmd = ['exec','-i',server,'/bin/bash','-c',
                          'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -l 3']
                until=time.monotonic()+100
                while True:
                    r=d(*sqlcmd,stdin='SELECT 1;\nGO\n',check=False)
                    if r.returncode == 0: break
                    if time.monotonic()>until: raise RuntimeError('Local SQL Server did not become available')
                    time.sleep(1)
                seed = "CREATE DATABASE demodb;\nGO\nCREATE LOGIN app_runtime WITH PASSWORD='"+password+"';\nGO\nUSE demodb;\nCREATE USER app_runtime FOR LOGIN app_runtime;\nCREATE TABLE dbo.DemoTexts (Id int IDENTITY PRIMARY KEY, Text nvarchar(max) NOT NULL, CreatedAt datetime2 NOT NULL);\nGRANT SELECT, INSERT ON OBJECT::dbo.DemoTexts TO app_runtime;\nGO\n"
                d(*sqlcmd,stdin=seed)
                version=d(*sqlcmd,stdin="SELECT SERVERPROPERTY('ProductVersion'), SERVERPROPERTY('Edition');\nGO\n").stdout
                (output/('sql-'+issuer+'-version.txt')).write_text(version)
                test(issuer+'_accepts_own',issuer,'DATABASE_RUNTIME_ADMITTED')
                opposite='dev' if issuer=='prod' else 'prod'
                test(opposite+'_rejects_'+issuer,opposite,'DATABASE_TLS_HANDSHAKE_REFUSED')
                if issuer=='prod':
                    test('wrong_hostname','prod','DATABASE_TLS_HANDSHAKE_REFUSED',hostname='wrong.example.test')
                    test('missing_manifest','prod','SQL_TRUST_MANIFEST_REQUIRED',edit=lambda x:x.pop('SQL_TRUST_MANIFEST_B64'))
                    test('altered_manifest','prod','SQL_TRUST_MANIFEST_HASH_REFUSED',edit=lambda x:x.update(SQL_TRUST_MANIFEST_SHA256='0'*64))
                    test('missing_profile','prod','DATABASE_VALIDATED_PROFILE_REQUIRED',edit=lambda x:x.pop('Database__SecurityProfile'))
                    test('legacy_profile','prod','DATABASE_VALIDATED_PROFILE_REQUIRED',profile='legacy-v1')
                    test('prod_rejects_bridge','prod','SQL_TRUST_SCHEMA_REFUSED',bridge=True)
                    test('anchor_bytes_changed','prod','SQL_TRUST_ANCHOR_HASH_REFUSED',trust_edit=lambda x:x['anchors'][0].update(sha256='0'*64))
                    test('runtime_with_migration_credential','prod','DATABASE_RUNTIME_HAS_MIGRATION_CREDENTIAL',edit=lambda x:x.update(DB_MIGRATION_CONN_STRING=x['DB_CONN_STRING']))
                    test('migrator_requires_confirmation','prod','SQL_TRUST_COMMAND_REFUSED',command=('database-migrate',))
                    test('migrator_no_runtime_fallback','prod','DATABASE_MIGRATION_REFUSED_OR_FAILED',command=('database-migrate','--confirm-schema-change'))
                    test('migrator_rejects_runtime_identity','prod','DATABASE_MIGRATION_REFUSED_OR_FAILED',command=('database-migrate','--confirm-schema-change'),edit=lambda x:x.update(DB_MIGRATION_CONN_STRING=x['DB_CONN_STRING']))
                else:
                    test('dev_bridge_accepts','dev','DATABASE_RUNTIME_ADMITTED',bridge=True)
                    test('bridge_expired','dev','SQL_TRUST_TRANSITION_REFUSED',bridge=True,trust_edit=lambda x:x['transition'].update(not_after='2026-01-01T00:00:00Z'))
                    test('bridge_too_long','dev','SQL_TRUST_TRANSITION_REFUSED',bridge=True,trust_edit=lambda x:x['transition'].update(not_before='2026-10-01T00:00:00Z'))
                    def replace_leaf(trust):
                        fake = roots['prod'].copy(); fake['kind']='dev-leaf-transition'; trust['anchors'][1]=fake
                    test('bridge_wrong_pin','dev','SQL_TRUST_LEAF_PIN_REFUSED',bridge=True,trust_edit=replace_leaf)
                    test('bridge_running_expiry','dev','SQL_TRUST_TRANSITION_EXPIRED',bridge=True,
                         trust_edit=lambda x:x['transition'].update(not_after=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=8)).strftime('%Y-%m-%dT%H:%M:%SZ')))
                d('rm','-f','-v',server);containers.remove(server)

            capability=d('run','--rm','--pull','never','--network','none',a.image,'readiness-probe','--check-capability').stdout.strip()
            results.append(dict(case='probe_capability_without_trust_or_secrets',passed=capability=='readiness-probe-capability=available',image=a.image))
            unavailable=d('run','--rm','--pull','never','--network','none',
                          '-e','READINESS_PROBE_TIMEOUT_SECONDS=1','-e','READINESS_PROBE_REQUEST_TIMEOUT_SECONDS=1',
                          '-e','READINESS_PROBE_INTERVAL_SECONDS=1',a.image,'readiness-probe',check=False)
            results.append(dict(case='probe_loopback_unavailable_without_sql_configuration',
                                passed=unavailable.returncode == 1 and 'SQL_TRUST_' not in unavailable.stderr,
                                image=a.image))
    finally:
        for container in containers: d('rm','-f','-v',container,check=False)
        d('network','rm',network,check=False)
        report=dict(started_utc=started, ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(), image=a.image,
                    sql_image=SQL_IMAGE, tests=results, sqlclient='6.1.7',
                    image_user=image_metadata['Config']['User'], image_entrypoint=image_metadata['Config']['Entrypoint'],
                    public_linux_roots_preserved=cleanliness.returncode == 0, laboratory_certificate_in_image=False,
                    proof='Real API ENTRYPOINT and SQL runtime permission SELECT; not SslStream simulation',
                    not_proven=['Fargate','KMS','AWS IAM','production PKI','server certificate rotation or rollback'])
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    if not results or not all(x['passed'] for x in results): raise SystemExit(1)


if __name__ == '__main__': main()
