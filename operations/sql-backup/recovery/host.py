#!/usr/bin/env python3
"""One synthetic source/restore drill on a bound Linux EC2 host; default is plan-only.

No timer, lifecycle scheduler, cloud resource creation or automatic replay.
SQL/SDK output is captured and replaced with fixed error codes on failure.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import urllib.request
import urllib.error

import verify_effective as runtime_verify

from prepare import ACCOUNT, REGION, BUCKET, BASE, BACKUP_KEY, TEXT_KEY, ROLE_NAME, SA_SECRET, APP_SECRET, require, trial


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    # .NET round-trip timestamps may have seven fractional digits. Python3.10
    # accepts at most six; durations project below one microsecond while ordering
    # below retains the original seventh digit instead of silently losing it.
    require(isinstance(value, str), 'INVALID_TIMESTAMP')
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,7}))?(Z|[+-]\d{2}:\d{2})?', value)
    require(match is not None, 'INVALID_TIMESTAMP')
    require(match[3] is not None, 'UTC_OFFSET_REQUIRED')
    fraction = match[2] or ''
    projected = match[1] + ('.' + fraction[:6] if fraction else '') + match[3]
    return dt.datetime.fromisoformat(projected.replace('Z', '+00:00'))


def timestamp_ticks(value):
    parsed = timestamp(value).astimezone(dt.timezone.utc)
    delta = parsed - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    fraction = re.search(r'\.(\d{1,7})', value)
    last = int(fraction[1][6]) if fraction and len(fraction[1]) == 7 else 0
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 10 + last


def event_order(*values):
    ticks = [timestamp_ticks(value) for value in values]
    return all(left <= right for left, right in zip(ticks, ticks[1:]))


def create_staging(name, user):
    directories = [Path(options(name)[field]) for field in ('StagingDirectory', 'RestoreDirectory')]
    parent = directories[0].parent
    require(parent.is_absolute(), 'SAFE_ABSOLUTE_PATH_REQUIRED')
    require(all(directory.parent == parent for directory in directories), 'STAGING_PARENT_MISMATCH')
    require(not any(path.is_symlink() for path in (parent, *parent.parents)), 'SAFE_ABSOLUTE_PATH_REQUIRED')
    require(all(not directory.exists() and not directory.is_symlink() for directory in directories), 'EXISTING_STAGING_REQUIRES_REVIEW')
    if not parent.exists():
        # Never leave a root0700 intermediate directory above mssql-owned children.
        parent.mkdir(mode=0o700)
        os.chown(parent, user.pw_uid, user.pw_gid)
    stat = parent.stat()
    require(parent.is_dir() and stat.st_uid == user.pw_uid and stat.st_gid == user.pw_gid
            and stat.st_mode & 0o777 == 0o700, 'PRIVATE_SQL_STAGING_PARENT_REQUIRED')
    for directory in directories:
        directory.mkdir(mode=0o700)
        os.chown(directory, user.pw_uid, user.pw_gid)
    return directories[0] / 'backup-config.json'


def bind_identity(identity, expected_instance, expected_az):
    require(isinstance(expected_instance, str) and re.fullmatch('i-[0-9a-f]{17}', expected_instance), 'EXPECTED_INSTANCE_REQUIRED')
    require(isinstance(expected_az, str) and re.fullmatch('us-east-1[a-f]', expected_az), 'EXPECTED_AZ_REQUIRED')
    require(identity['accountId'] == ACCOUNT and identity['region'] == REGION
            and identity['instanceId'] == expected_instance and identity['availabilityZone'] == expected_az,
            'WRONG_ACCOUNT_REGION_OR_HOST')


def private_write(path, value):
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'SAFE_ABSOLUTE_PATH_REQUIRED')
    require(path.parent.is_dir() and path.parent.stat().st_mode & 0o077 == 0, 'PRIVATE_DIRECTORY_REQUIRED')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2)


def options(name):
    trial(name)
    return {'Database': 'recoverydb', 'StagingDirectory': '/var/opt/mssql/backup/' + name,
            'RestoreDirectory': '/var/opt/mssql/backup/' + name + '-restores', 'Bucket': BUCKET,
            'Prefix': BASE + '/' + name, 'BackupKeyArn': BACKUP_KEY, 'TextKeyArn': TEXT_KEY,
            'ExpectedEc2RoleName': ROLE_NAME, 'MaxBackupBytes': 536870912, 'FreeReserveBytes': 268435456,
            'TimeoutSeconds': 600, 'ProposedIntervalHours': 1, 'ProposedRetentionDays': 2,
            'ProposedMaxAgeHours': 2, 'RetainLocalVerifiedBackups': 2}


def connection(user, password, database, endpoint='127.0.0.1'):
    # SqlClient quote escapes semicolons, braces and embedded double quotes.
    require(isinstance(password, str) and password and '\n' not in password and '\r' not in password, 'INVALID_CREDENTIAL')
    runtime_verify.checked_endpoint(endpoint)
    quoted = '"' + password.replace('"', '""') + '"'
    return f'Server={endpoint};Database={database};User Id={user};Password={quoted};Encrypt=True;TrustServerCertificate=True;'


class Port:
    def run(self, command, env=None, body=None, timeout=630):
        try:
            result = subprocess.run(command, input=body, env=env, capture_output=True, text=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('CHILD_OUTCOME_UNKNOWN') from None
        require(result.returncode == 0, 'CHILD_FAILED_REVIEW_BEFORE_RETRY')
        return result.stdout

    def identity(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        token = opener.open(urllib.request.Request('http://169.254.169.254/latest/api/token',
            data=b'', method='PUT', headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'}), timeout=3).read().decode()
        return json.loads(opener.open(urllib.request.Request('http://169.254.169.254/latest/dynamic/instance-identity/document',
            headers={'X-aws-ec2-metadata-token': token}), timeout=3).read())

    def runtime_precheck(self, password, expected_ip='127.0.0.1'):
        runtime_verify.checked_endpoint(expected_ip)
        def fresh_query():
            env = dict(os.environ, SQLCMDPASSWORD=password)
            try:
                return subprocess.run(['/opt/mssql-tools18/bin/sqlcmd', '-S', 'tcp:' + expected_ip + ',1433', '-C', '-U', 'sa', '-d', 'master', '-l', '5', '-b', '-h', '-1', '-W'],
                    env=env, input='SET NOCOUNT ON; SET XACT_ABORT ON;\n' + runtime_verify.FRESH_QUERY,
                    capture_output=True, text=True, check=False, timeout=15)
            finally:
                env.pop('SQLCMDPASSWORD', None)
        return runtime_verify.assess_runtime(runtime_verify.LocalPort(), fresh_query, expected_ip)

    def confirm_cold_fence(self, request, target_identity):
        """Native reads only, never terminate or assume a different role. No retries."""
        source = request['SourceRecord']['Source']
        caller = json.loads(self.run(['aws', 'sts', 'get-caller-identity', '--output', 'json'], timeout=20))
        require(caller['Account'] == ACCOUNT and
                caller['Arn'].startswith(f'arn:aws:sts::{ACCOUNT}:assumed-role/{ROLE_NAME}/'),
                'FENCE_READER_IDENTITY_MISMATCH')
        document = json.loads(self.run(['aws', 'ec2', 'describe-instances', '--region', REGION,
                   '--instance-ids', source['instanceId'], target_identity['instanceId'], '--output', 'json'], timeout=20))
        reservations = document.get('Reservations', [])
        require(reservations and all(r.get('OwnerId') == ACCOUNT for r in reservations), 'FENCE_ACCOUNT_MISMATCH')
        instances = [i for r in reservations for i in r.get('Instances', [])]
        require(len(instances) == 2 and len({i['InstanceId'] for i in instances}) == 2, 'FENCE_INVENTORY_INCOMPLETE')
        items = {i['InstanceId']: i for i in instances}
        old, new = items[source['instanceId']], items[target_identity['instanceId']]
        require(old['State']['Name'] == 'terminated', 'SOURCE_TERMINATION_NOT_CONFIRMED')
        require(timestamp(old['LaunchTime']) == timestamp(request['SourceLaunchUtc'])
                and old['Placement']['AvailabilityZone'] == source['availabilityZone'], 'SOURCE_GENERATION_MISMATCH')
        tags = {t['Key']: t['Value'] for t in new.get('Tags', [])}
        require(new['State']['Name'] == 'running' and tags.get('Trial') == request['Trial']
                and new['Placement']['AvailabilityZone'] == request['TargetAz']
                and new['ImageId'] == request['SqlAmiId'], 'TARGET_GENERATION_MISMATCH')
        require(event_order(request['RecoveryRequestedUtc'], new['LaunchTime'], utc()), 'PREPARED_TARGET_FORBIDDEN')
        receipt = {'Status': 'EXACT_SOURCE_TERMINATED', 'Source': source, 'Target': target_identity,
                'SourceLaunchUtc': old['LaunchTime'], 'TargetLaunchUtc': new['LaunchTime'],
                'ObservedUtc': utc(), 'ControlPlaneSha256': hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest(),
                'Basis': 'Native STS and EC2 reads under the instance role; not an AZ-outage guarantee.'}
        if hasattr(self, 'record_fence'):
            self.record_fence(receipt)
        return receipt

    def application_network(self, value, identity):
        """Exact future native reads; no SG/IAM/config mutation or alternate role."""
        from prepare import PROFILE, service_plan
        service_plan(value)
        source, target = value['ColdReceipt']['Source'], value['ColdReceipt']['Target']
        net, fence = value['Network'], value['ColdReceipt']['ColdFence']
        require(all(identity[k] == target[k] for k in ('accountId','region','instanceId','availabilityZone')), 'LISTENER_TARGET_IDENTITY_MISMATCH')
        caller = json.loads(self.run(['aws','sts','get-caller-identity','--output','json'],timeout=20))
        require(caller['Account'] == ACCOUNT and caller['Arn'] == f'arn:aws:sts::{ACCOUNT}:assumed-role/{ROLE_NAME}/' + identity['instanceId'], 'LISTENER_ROLE_IDENTITY_MISMATCH')
        doc = json.loads(self.run(['aws','ec2','describe-instances','--region',REGION,'--instance-ids',source['instanceId'],identity['instanceId'],'--output','json'],timeout=20))
        reservations = doc.get('Reservations',[])
        require(reservations and all(r.get('OwnerId') == ACCOUNT for r in reservations), 'LISTENER_INSTANCE_ACCOUNT_MISMATCH')
        rows = [i for r in reservations for i in r.get('Instances',[])]
        require(len(rows) == 2 and {i['InstanceId'] for i in rows} == {source['instanceId'],target['instanceId']}, 'LISTENER_INSTANCE_INVENTORY_MISMATCH')
        by_id = {i['InstanceId']:i for i in rows};old,node = by_id[source['instanceId']],by_id[target['instanceId']]
        require(old['State']['Name'] == 'terminated' and old['Placement']['AvailabilityZone'] == source['availabilityZone']
                and timestamp(old['LaunchTime']) == timestamp(fence['SourceLaunchUtc']), 'LISTENER_SOURCE_FENCE_UNCERTAIN')
        require(node['State']['Name'] == 'running' and node['Placement']['AvailabilityZone'] == target['availabilityZone']
                and timestamp(node['LaunchTime']) == timestamp(fence['TargetLaunchUtc']), 'LISTENER_TARGET_GENERATION_MISMATCH')
        require(node.get('VpcId') == net['AppVpcId'] and node.get('PrivateIpAddress') == net['DbPrivateIp']
                and not node.get('PublicIpAddress') and node.get('IamInstanceProfile',{}).get('Arn') == PROFILE
                and {t['Key']:t['Value'] for t in node.get('Tags',[])}.get('Trial') == value['Trial'], 'LISTENER_NATIVE_NETWORK_MISMATCH')
        require([g['GroupId'] for g in node.get('SecurityGroups',[])] == [net['DbSgId']], 'LISTENER_EXTRA_SECURITY_GROUP')
        interfaces = node.get('NetworkInterfaces',[])
        require(len(interfaces) == 1 and interfaces[0].get('PrivateIpAddress') == net['DbPrivateIp']
                and interfaces[0].get('VpcId') == net['DbVpcId'] and interfaces[0].get('SubnetId') == node.get('SubnetId')
                and [g['GroupId'] for g in interfaces[0].get('Groups',[])] == [net['DbSgId']]
                and not interfaces[0].get('Association') and not interfaces[0].get('Ipv6Addresses')
                and [a['PrivateIpAddress'] for a in interfaces[0].get('PrivateIpAddresses',[])] == [net['DbPrivateIp']]
                and not any(a.get('Association') for a in interfaces[0].get('PrivateIpAddresses',[])), 'LISTENER_INTERFACE_SCOPE_MISMATCH')
        subnets = json.loads(self.run(['aws','ec2','describe-subnets','--region',REGION,'--subnet-ids',node['SubnetId'],'--output','json'],timeout=20))['Subnets']
        require(len(subnets) == 1 and subnets[0].get('SubnetId') == node['SubnetId']
                and subnets[0].get('OwnerId') == ACCOUNT and subnets[0].get('VpcId') == net['AppVpcId']
                and subnets[0].get('CidrBlock') == net['DbSubnetCidr'] and subnets[0].get('MapPublicIpOnLaunch') is False, 'LISTENER_SUBNET_MISMATCH')
        groups = json.loads(self.run(['aws','ec2','describe-security-groups','--region',REGION,'--group-ids',net['DbSgId'],net['TaskSgId'],'--output','json'],timeout=20))['SecurityGroups']
        require(len(groups) == 2 and {g['GroupId'] for g in groups} == {net['DbSgId'],net['TaskSgId']}
                and all(g.get('OwnerId') == ACCOUNT and g.get('VpcId') == net['AppVpcId'] for g in groups), 'LISTENER_SECURITY_GROUP_OWNER_MISMATCH')
        ingress = next(g for g in groups if g['GroupId'] == net['DbSgId'])['IpPermissions']
        require(len(ingress) == 1, 'LISTENER_SQL_INGRESS_MISMATCH')
        rule = ingress[0];pairs = rule.get('UserIdGroupPairs',[])
        require(rule.get('IpProtocol') == 'tcp' and rule.get('FromPort') == rule.get('ToPort') == 1433
                and not any(rule.get(k) for k in ('IpRanges','Ipv6Ranges','PrefixListIds'))
                and len(pairs) == 1 and pairs[0].get('GroupId') == net['TaskSgId']
                and pairs[0].get('UserId') == ACCOUNT, 'LISTENER_SQL_INGRESS_MISMATCH')
        return {'SourceInstanceId':source['instanceId'],'SourceLaunchUtc':fence['SourceLaunchUtc'],
                'SourceState':'terminated','TargetInstanceId':identity['instanceId'],'TargetLaunchUtc':fence['TargetLaunchUtc'],
                'VpcId':node['VpcId'],'SubnetId':node['SubnetId'],'PrivateIp':node['PrivateIpAddress'],
                'DbSgId':net['DbSgId'],'TaskSgId':net['TaskSgId'], 'SingleTaskSgSql1433IngressOnly':True}

    def secret(self, arn):
        value = self.run(['aws', 'secretsmanager', 'get-secret-value', '--region', REGION, '--secret-id', arn,
                          '--query', 'SecretString', '--output', 'text'], timeout=20).rstrip('\n')
        require(value and value != 'None', 'SECRET_UNAVAILABLE')
        return value

    def connection_aws(self, *arguments):
        # Deliberately no profiles, caller tokens, AWS SDK retries or raw output.
        env={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
             'HOME':'/nonexistent','AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null',
             'AWS_REGION':REGION,'AWS_DEFAULT_REGION':REGION,'AWS_EC2_METADATA_V1_DISABLED':'true',
             'AWS_MAX_ATTEMPTS':'1','AWS_PAGER':''}
        return json.loads(self.run(['aws','--region',REGION,'--output','json',*arguments],env=env,timeout=30))

    def put_connection_version(self, arn, version, stage, value, directory):
        # Value exists only in this root-private EC2 file, never argv/stdout/state.
        path=directory/('connection-value-'+version+'.json')
        private_write(path, {'SecretId':arn,'ClientRequestToken':version,
                             'VersionStages':[stage],'SecretString':value})
        try:
            return self.connection_aws('secretsmanager','put-secret-value','--cli-input-json','file://'+str(path))
        finally:
            path.unlink()  # only the file just created; unknown mutation is not retried

    def sql(self, password, statement):
        env = dict(os.environ, SQLCMDPASSWORD=password)
        return self.run(['/opt/mssql-tools18/bin/sqlcmd', '-S', '127.0.0.1', '-C', '-U', 'sa', '-l', '5', '-b', '-h', '-1', '-W'],
                        env, 'SET NOCOUNT ON; SET XACT_ABORT ON;\n' + statement, timeout=610)

    @contextmanager
    def api(self, executable, password, database, migrate):
        env = dict(os.environ, DB_CONN_STRING=connection('recovery_app', password, database),
                   KMS_KEY_ID=TEXT_KEY, AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION,
                   ASPNETCORE_ENVIRONMENT='Production', ASPNETCORE_URLS='http://127.0.0.1:5088',
                   Database__RunMigrationsOnStartup=str(migrate).lower())
        process = subprocess.Popen(['runuser', '-u', 'mssql', '--', str(executable)], env=env,
                                   start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for attempt in range(45):
                require(process.poll() is None, 'API_START_FAILED')
                try:
                    if self.http('GET', '/health')['status'] == 'Healthy':
                        break
                except urllib.error.HTTPError:
                    raise ValueError('API_LIVENESS_FAILED_REVIEW') from None
                except (urllib.error.URLError, TimeoutError, KeyError):
                    pass
                time.sleep(2)
            else:
                raise ValueError('API_READINESS_DEADLINE')
            # Dependency readiness is one-shot: never poll a KMS/SQL denial.
            try:
                require(self.http('GET', '/ready')['status'] == 'Healthy', 'API_DEPENDENCIES_NOT_READY')
            except (urllib.error.URLError, TimeoutError, KeyError):
                raise ValueError('API_DEPENDENCY_FAILURE_REVIEW') from None
            yield
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if process.poll() is None:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)

    def http(self, method, route, body=None):
        request = urllib.request.Request('http://127.0.0.1:5088' + route,
            data=None if body is None else json.dumps(body).encode(), method=method,
            headers={'Content-Type': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            return json.loads(response.read(65537))

    def backup(self, executable, config, password, restore=None):
        env = dict(os.environ)
        for key in ('SQL_BACKUP_CONNECTION_STRING', 'SQL_VERIFY_CONNECTION_STRING', 'SQL_RESTORE_CONNECTION_STRING'):
            env[key] = connection('sa', password, 'master')
        command = ['runuser', '-u', 'mssql', '--', str(executable), 'restore' if restore else 'backup', '--config', str(config), '--aws', '--ec2-role', '--local-sql-self-signed']
        if restore:
            command += ['--manifest-key', restore['Receipt']['ManifestKey'], '--manifest-version', restore['Receipt']['ManifestVersion'],
                        '--target', 'recoverydb_restore_' + restore['Trial']]
        return json.loads(self.run(command, env))



class RuntimePrecheckFailure(ValueError):
    def __init__(self, report):
        super().__init__()
        fallback = runtime_verify.failure('runtime_gate', runtime_verify.Problem('RUNTIME_PRECHECK_INCOMPLETE'))
        if isinstance(report, dict) and report.get('Status') == 'REFUSED' and type(report.get('ExitCode')) is int:
            stage, code = report.get('Stage'), report.get('Code')
            if isinstance(stage, str) and stage in runtime_verify.STAGES and isinstance(code, str) and code in runtime_verify.CODES:
                allowed_exit = {'READ_FAILED':74, 'READ_COMMAND_TIMEOUT':124, 'ENVIRONMENT_UNSUPPORTED':69}.get(code, 65)
                safe = runtime_verify.failure(stage, runtime_verify.Problem(code, report.get('CommandExitCode')))
                if code != 'COMMAND_EXIT_NONZERO': safe['ExitCode'] = allowed_exit
                if safe['ExitCode'] == report.get('ExitCode'): fallback = safe
        self.report = fallback


def checked_runtime(port, identity, password, expected_ip='127.0.0.1'):
    binding = {k: identity[k] for k in ('accountId','region','instanceId','availabilityZone')}
    bind_identity(binding, binding['instanceId'], binding['availabilityZone'])
    report = port.runtime_precheck(password) if expected_ip == '127.0.0.1' else port.runtime_precheck(password, expected_ip=expected_ip)
    try: runtime_verify.require_runtime_precheck(report, expected_ip)
    except runtime_verify.Problem: raise RuntimePrecheckFailure(report) from None
    return dict(report, HostBinding=binding)


def check_source_runtime(source_record):
    report = source_record.get('RuntimePrecheck')
    try: runtime_verify.require_runtime_precheck(report)
    except runtime_verify.Problem: raise RuntimePrecheckFailure(report) from None
    source = {k: source_record['Source'][k] for k in ('accountId','region','instanceId','availabilityZone')}
    require(report.get('HostBinding') == source, 'SOURCE_RUNTIME_BINDING_MISMATCH')




def check_application_network(port, value, identity):
    from prepare import application_listener_plan
    plan = application_listener_plan(value)
    return {'Status':'APPLICATION_NETWORK_OBSERVATION_ONLY','Trial':value['Trial'],
            'ServiceInputSha256':plan['ServiceInputSha256'],
            'NetworkBinding':port.application_network(value,identity),'ObservedUtc':utc(),
            'AllowsHostChanges':False,'AllowsActivation':False,'FullEcsRecoveryProven':False}


def check_application_listener(port, value, identity):
    """Read-only post-transition qualification, never a listener activation command."""
    from prepare import application_listener_plan
    plan = application_listener_plan(value)
    before = port.application_network(value, identity)
    runtime = checked_runtime(port, identity, port.secret(SA_SECRET), plan['ProposedEndpoint'])
    after = port.application_network(value, identity)
    require(after == before, 'LISTENER_NETWORK_CHANGED_DURING_OBSERVATION')
    return {'Status':'APPLICATION_LISTENER_OBSERVATION_ONLY','Trial':value['Trial'],
            'ServiceInputSha256':plan['ServiceInputSha256'],'NetworkBinding':after,
            'RuntimePrecheck':runtime,'ObservedUtc':utc(),'AllowsActivation':False,
            'PublicApiRecoveryProven':False,'FullEcsRecoveryProven':False}


def write_connection_version(port, value, identity, directory, approved_sha256):
    """Future explicit host action; hash acknowledgement is not owner authority.

    Uses the existing listener/fence validators and fresh native reads. Metadata
    never activates ECS. CLI main records STARTED before this mutating action.
    """
    from prepare import service_plan, encoded
    service_plan(value)
    expected=hashlib.sha256(encoded(value)).hexdigest()
    require(isinstance(approved_sha256,str) and re.fullmatch('[a-f0-9]{64}',approved_sha256)
            and approved_sha256==expected,'EXACT_CONNECTION_WRITE_ACK_REQUIRED')
    age=(timestamp(utc())-timestamp(value['ReviewedUtc'])).total_seconds()
    require(0<=age<=600,'FRESH_CONNECTION_REVIEW_REQUIRED')
    target=value['ColdReceipt']['Target']
    require(all(identity[k]==target[k] for k in ('accountId','region','instanceId','availabilityZone')),
            'CONNECTION_TARGET_IDENTITY_MISMATCH')
    before=check_application_listener(port,value,identity)
    conn=value['Connection'];arn=conn['SecretArn'];version=conn['VersionId']
    stage='ecs-recovery-'+value['Trial']
    metadata=port.connection_aws('secretsmanager','describe-secret','--secret-id',arn)
    require(metadata.get('ARN')==arn and metadata.get('KmsKeyId')==conn['SecretKeyArn']
            and not metadata.get('DeletedDate'),'CONNECTION_SECRET_METADATA_MISMATCH')
    stages=metadata.get('VersionIdsToStages')
    require(type(stages) is dict and len([v for v,labels in stages.items() if 'AWSCURRENT' in labels])==1
            and version not in stages and all(stage not in labels for labels in stages.values()),
            'CONNECTION_VERSION_OR_STAGE_REQUIRES_REVIEW')
    password=port.secret(APP_SECRET)
    secret=connection('recovery_app',password,conn['Database'],endpoint=conn['Endpoint'])
    try:
        result=port.put_connection_version(arn,version,stage,secret,directory)
    finally:
        password=secret=None
    require(result.get('ARN')==arn and result.get('VersionId')==version and result.get('VersionStages')==[stage],
            'CONNECTION_PUT_RESULT_UNKNOWN')
    after=port.connection_aws('secretsmanager','describe-secret','--secret-id',arn)
    require(after.get('ARN')==arn and after.get('KmsKeyId')==conn['SecretKeyArn']
            and not after.get('DeletedDate') and after.get('VersionIdsToStages')==dict(stages,**{version:[stage]}),
            'CONNECTION_STAGES_CHANGED_OR_UNKNOWN')
    final=check_application_listener(port,value,identity)
    require(before['NetworkBinding']==final['NetworkBinding'],'CONNECTION_NETWORK_CHANGED')
    receipt={'Status':'CONNECTION_VERSION_WRITTEN_METADATA_VERIFIED','Trial':value['Trial'],
             'ServiceInputSha256':expected,'Target':target,'SecretArn':arn,
             'VersionId':version,'CustomStage':stage,'SecretKeyArn':conn['SecretKeyArn'],
             'Endpoint':conn['Endpoint'],'Database':conn['Database'],'ObservedUtc':utc(),
             'OriginalStagesPreserved':True,'PlaintextExported':False,'AllowsActivation':False,
             'OwnerAuthorityEstablishedByAcknowledgement':False,'FullEcsRecoveryProven':False}
    return dict(receipt,ConnectionReceiptSha256=hashlib.sha256(encoded(receipt)).hexdigest())


def source(port, name, config, backup, api, identity):
    sa = port.secret(SA_SECRET)
    runtime = checked_runtime(port, identity, sa)
    app = port.secret(APP_SECRET)
    escaped = app.replace("'", "''")
    port.sql(sa, f"IF DB_ID(N'recoverydb') IS NOT NULL OR SUSER_ID(N'recovery_app') IS NOT NULL THROW 51000,'Existing source',1;\nGO\nCREATE DATABASE recoverydb;\nGO\nCREATE LOGIN recovery_app WITH PASSWORD=N'{escaped}';\nGO\nUSE recoverydb; CREATE USER recovery_app FOR LOGIN recovery_app; ALTER ROLE db_owner ADD MEMBER recovery_app;")
    before, after = name + '-before', name + '-after'
    with port.api(api, app, 'recoverydb', True):
        requested = utc()
        pre = port.http('POST', '/text', {'text': before})
        committed = utc()
        require(pre['text'] == before and isinstance(pre['id'], int), 'SOURCE_MARKER_NOT_CONFIRMED')
        result = port.backup(backup, config, sa)
        require(result['Status'] == 'REMOTE_VERIFIED', 'BACKUP_NOT_VERIFIED')
        receipt = result['Receipt']
        require(receipt['Manifest']['NativeChecksumVerified'] and receipt['ManifestKey'].startswith(BASE + '/' + name + '/runs/'), 'BACKUP_SCOPE_MISMATCH')
        require(bool(receipt['ManifestVersion']) and bool(receipt['Manifest']['BackupVersion']), 'BACKUP_VERSION_MISSING')
        post = port.http('POST', '/text', {'text': after})
        require(post['text'] == after, 'POST_BACKUP_MARKER_NOT_CONFIRMED')
    # No application process survives this action. SQL stays UP until explicit quiesce.
    return {'Status': 'SOURCE_BACKED_UP', 'Trial': name, 'Source': identity, 'RuntimePrecheck': runtime, 'PreMarker': before,
            'PreMarkerId': pre['id'], 'PreMarkerRequestUtc': requested, 'PreMarkerConfirmedUtc': committed, 'PostMarker': after,
            'PostMarkerConfirmedUtc': utc(), 'Receipt': receipt, 'CompletedUtc': utc()}


def quiesce(port, source_record, identity):
    check_source_runtime(source_record)
    require(source_record['Source']['instanceId'] == identity['instanceId'], 'WRONG_SOURCE_HOST')
    start = utc()
    port.run(['systemctl', 'stop', 'mssql-server'], timeout=60)
    # systemctl returns 3 for inactive, so inspect the text without treating exit 3 as failure.
    active = port.run(['systemctl', 'show', 'mssql-server', '--property=ActiveState', '--value'], timeout=10).strip()
    require(active == 'inactive', 'SOURCE_NOT_QUIESCENT')
    return {'Trial': source_record['Trial'], 'SourceInstanceId': identity['instanceId'],
            'FailureDeclaredUtc': start, 'SourceInactiveConfirmedUtc': utc(), 'ActiveState': active}


def restore(port, name, config, backup, api, identity, source_record, failure, cold_request=None):
    check_source_runtime(source_record)
    fence = None
    m = source_record['Receipt']['Manifest']
    if cold_request is None:
        require(source_record['Status'] == 'SOURCE_BACKED_UP' and source_record['Trial'] == name == failure['Trial'], 'WRONG_TRIAL')
        require(source_record['Source']['instanceId'] != identity['instanceId'] and source_record['Source']['availabilityZone'] != identity['availabilityZone'], 'CROSS_AZ_REQUIRED')
        require(failure['SourceInstanceId'] == source_record['Source']['instanceId'] and failure['ActiveState'] == 'inactive', 'SOURCE_QUIESCENCE_REQUIRED')
        require(source_record['Receipt']['ManifestKey'].startswith(BASE + '/' + name + '/runs/'), 'MANIFEST_OUTSIDE_TRIAL')
        require(event_order(source_record['PreMarkerRequestUtc'], source_record['PreMarkerConfirmedUtc'], m['StartedUtc'], m['CompletedUtc'], source_record['PostMarkerConfirmedUtc'], failure['FailureDeclaredUtc'], failure['SourceInactiveConfirmedUtc'], utc()), 'INVALID_EVENT_ORDER')
    else:
        from prepare import cold_path
        require(cold_request['Trial'] == name and cold_request['SourceRecord'] == source_record, 'COLD_REQUEST_SOURCE_MISMATCH')
        require(source_record['Source']['instanceId'] != identity['instanceId'], 'FRESH_TARGET_REQUIRED')
        require(identity['availabilityZone'] == cold_request['TargetAz'], 'WRONG_TARGET_AZ')
        cold_path(dict(cold_request, NowUtc=utc()))
        fence = port.confirm_cold_fence(cold_request, identity)
        failure = {'FailureDeclaredUtc': cold_request['RecoveryRequestedUtc']}

    sa = port.secret(SA_SECRET)
    runtime = checked_runtime(port, identity, sa)
    app = port.secret(APP_SECRET)
    target = 'recoverydb_restore_' + name
    restore_record = dict(source_record, Trial=name) if cold_request is not None else source_record
    result = port.backup(backup, config, sa, restore_record)
    require(result['Status'] == 'RESTORED_CHECKDB_READABLE' and result['Rows'] >= 1, 'RESTORE_NOT_VERIFIED')
    escaped = app.replace("'", "''")
    if cold_request is not None:
        fence = port.confirm_cold_fence(cold_request, identity)
    port.sql(sa, f"IF SUSER_ID(N'recovery_app') IS NOT NULL THROW 51000,'Existing target login',1; CREATE LOGIN recovery_app WITH PASSWORD=N'{escaped}'; USE [{target}]; ALTER USER recovery_app WITH LOGIN=recovery_app;")
    if cold_request is not None:
        fence = port.confirm_cold_fence(cold_request, identity)
    with port.api(api, app, target, False):
        rows = port.http('GET', '/text?page=1&pageSize=100')
        require(any(r['id'] == source_record['PreMarkerId'] and r['text'] == source_record['PreMarker'] for r in rows), 'RECOVERED_MARKER_MISSING')
        require(not any(r['text'] == source_record['PostMarker'] for r in rows), 'UNEXPECTED_POST_BACKUP_MARKER')
        probe = name + '-restored-write'
        require(port.http('POST', '/text', {'text': probe})['text'] == probe, 'RESTORED_WRITE_FAILED')
        require(any(r['text'] == probe for r in port.http('GET', '/text?page=1&pageSize=100')), 'RESTORED_READ_FAILED')
        ready = utc()
    if cold_request is not None:
        fence = port.confirm_cold_fence(cold_request, identity)
    return {'ColdFence': fence, 'RecoveryMode': cold_request['Mode'] if cold_request else 'CROSS_AZ_PREPARED',
            'RtoColdHostSeconds': (timestamp(ready) - timestamp(cold_request['RecoveryRequestedUtc'])).total_seconds() if cold_request else None,
            'DeployedEcsApiProven': False, 'Status': 'TARGET_RECOVERED_REVIEW_EVIDENCE', 'Trial': name, 'Source': source_record['Source'], 'Target': identity,
            'ManifestVersion': source_record['Receipt']['ManifestVersion'], 'BackupVersion': m['BackupVersion'],
            'Checkdb': result['Status'], 'RuntimePrecheck': runtime, 'ReadyAndDecryptedMarkersConfirmedUtc': ready,
            'RtoWarmTargetSeconds': (timestamp(ready) - timestamp(failure['FailureDeclaredUtc'])).total_seconds() if cold_request is None else None,
            'ControlledMarkerAgeUpperBoundSeconds': (timestamp(failure['FailureDeclaredUtc']) - timestamp(source_record['PreMarkerRequestUtc'])).total_seconds(),
            'RpoQualification': 'Controlled synthetic marker observation only; not hourly RPO or production workload proof.',
            'FullEcsRecoveryProven': False, 'CloudLifecycleClosed': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['source', 'quiesce', 'restore', 'listener-network-check', 'listener-check', 'connection-version'])
    p.add_argument('--trial', required=True)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--failure', type=Path)
    p.add_argument('--cold-request', type=Path)
    p.add_argument('--listener-plan', type=Path)
    p.add_argument('--connection-write-approved-sha256')
    p.add_argument('--backup', type=Path)
    p.add_argument('--api', type=Path)
    p.add_argument('--backup-sha256')
    p.add_argument('--api-sha256')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--acknowledge')
    p.add_argument('--expected-instance-id')
    p.add_argument('--expected-az')
    a = p.parse_args()
    trial(a.trial)
    require(a.listener_plan is None or a.action in ('listener-network-check','listener-check','connection-version'), 'LISTENER_PLAN_ACTION_MISMATCH')
    if not a.execute:
        print(json.dumps({'Status': 'HOST_PLAN_ONLY', 'Action': a.action, 'AllowsCreation': False, 'ReadsSecrets': False}))
        return
    require(a.acknowledge == a.trial and os.name == 'posix' and os.geteuid() == 0, 'EXPLICIT_APPROVED_LINUX_ROOT_REQUIRED')
    require(not any(k in os.environ for k in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_PROFILE', 'AWS_WEB_IDENTITY_TOKEN_FILE')), 'INSTANCE_ROLE_ONLY')
    os.environ.update(AWS_CONFIG_FILE='/dev/null', AWS_SHARED_CREDENTIALS_FILE='/dev/null', AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION)
    require(a.directory.is_absolute() and a.directory.is_dir() and a.directory.stat().st_mode & 0o077 == 0 and not any(p.is_symlink() for p in (a.directory, *a.directory.parents)), 'PRIVATE_DIRECTORY_REQUIRED')
    output = a.directory / (a.action + '-receipt.json')
    require(not output.exists() and not output.with_suffix('.started').exists(), 'PREVIOUS_ACTION_REQUIRES_REVIEW')
    # Durable local STARTED marker remains on failure/unknown; never blind replay.
    private_write(output.with_suffix('.started'), {'Trial': a.trial, 'Action': a.action, 'Utc': utc()})
    port = Port()
    fence_index = [0]
    def record_fence(receipt):
        private_write(a.directory / ('fence-' + str(fence_index[0]) + '.json'), receipt)
        fence_index[0] += 1
    port.record_fence = record_fence
    identity = port.identity()
    bind_identity(identity, a.expected_instance_id, a.expected_az)
    if a.action in ('listener-network-check','listener-check','connection-version'):
        require(a.listener_plan is not None, 'EXPLICIT_LISTENER_PLAN_REQUIRED')
        value = json.loads(a.listener_plan.read_text(encoding='utf-8'))
        require(value['Trial'] == a.trial, 'WRONG_TRIAL')
        if a.action=='connection-version':
            result=write_connection_version(port,value,identity,a.directory,a.connection_write_approved_sha256)
        else:
            result = check_application_network(port,value,identity) if a.action == 'listener-network-check' else check_application_listener(port, value, identity)
    elif a.action == 'quiesce':
        source_record = json.loads(a.source.read_text())
        require(source_record['Trial'] == a.trial, 'WRONG_TRIAL')
        result = quiesce(port, source_record, identity)
    else:
        for executable, expected in [(a.backup, a.backup_sha256), (a.api, a.api_sha256)]:
            require(executable is not None and executable.is_absolute() and executable.is_file()
                    and not any(p.is_symlink() or p.stat().st_mode & 0o022 for p in (executable, *executable.parents)), 'REVIEWED_EXECUTABLE_REQUIRED')
            require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected) and hashlib.sha256(executable.read_bytes()).hexdigest() == expected, 'EXECUTABLE_HASH_MISMATCH')
        import pwd
        user = pwd.getpwnam('mssql')
        config = create_staging(a.trial, user)
        cold_request = json.loads(a.cold_request.read_text()) if a.cold_request else None
        require(cold_request is None or a.action == 'restore', 'COLD_RESTORE_ONLY')
        cfg = options(a.trial)
        if cold_request is not None:
            cfg['Prefix'] = options(cold_request['SourceRecord']['Trial'])['Prefix']
        private_write(config, cfg)
        os.chown(config, user.pw_uid, user.pw_gid)
        if a.action == 'source':
            result = source(port, a.trial, config, a.backup, a.api, identity)
        else:
            result = restore(port, a.trial, config, a.backup, a.api, identity, json.loads(a.source.read_text()), json.loads(a.failure.read_text()) if a.failure else None, cold_request)
    private_write(output, result)
    print(json.dumps({'Status': result['Status'] if 'Status' in result else 'SOURCE_QUIESCENT', 'Receipt': str(output)}))


if __name__ == '__main__':
    try:
        main()
    except RuntimePrecheckFailure as e:
        print(json.dumps(e.report)); raise SystemExit(e.report['ExitCode'])
    except Exception as e:
        print(json.dumps({'Status': 'FAILED_OR_UNKNOWN_REVIEW_BEFORE_RETRY', 'Code': str(e) if type(e) is ValueError and re.fullmatch('[A-Z_]+', str(e)) else type(e).__name__}))
        raise SystemExit(1)
