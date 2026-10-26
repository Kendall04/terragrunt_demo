#!/usr/bin/env python3
"""SQL-host observer configuration and startup integrity gate. No transport or service control."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import signals

FILES=('cohost.py','observer.py','sentinel_publish.py','signals.py','sql-backup-sentinel-producer.service.in','sql-backup-sentinel-producer.timer.in')
KEYS=set('SchemaVersion Placement Account Region RunId Subject StartsAt ExpiresAt CadenceSeconds ReminderSeconds PublishAttempts WatchdogSeconds ExpectedUp'.split())
ROOT=Path('/opt/terragrunt-demo/sql-backup')
CONFIG=Path('/etc/terragrunt-demo/sql-backup/config.json')
SETTINGS=Path('/etc/terragrunt-demo/sql-backup/sentinel.json')

def require(condition,code):
    if not condition:raise ValueError(code)

def validate(value,backup):
    require(set(value)==KEYS and type(value['SchemaVersion']) is int and value['SchemaVersion']==1 and value['Placement']=='SQL_HOST','EXACT_COHOST_CONFIG_REQUIRED')
    require(value['Account']=='341936017254' and value['Region']=='us-east-1','EXACT_ACCOUNT_REGION_REQUIRED')
    require(re.fullmatch(r'ecs-sentinel-[a-z0-9-]{1,24}',value['RunId']) is not None and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',value['Subject']) is not None,'EXACT_SENTINEL_SUBJECT_REQUIRED')
    require(type(value['ExpectedUp']) is bool,'EXPLICIT_EXPECTED_UP_REQUIRED')
    for key,lo,hi in [('CadenceSeconds',60,3600),('ReminderSeconds',0,604800),('PublishAttempts',1,3),('WatchdogSeconds',1,86400)]:
        require(type(value[key]) is int and lo<=value[key]<=hi,'BOUNDED_COHOST_POLICY_REQUIRED')
    # Includes native check timeout660, queue120 and next-tick jitter60.
    require(value['WatchdogSeconds']>value['CadenceSeconds']+840,'WATCHDOG_MUST_ALLOW_CHECK_AND_DELIVERY')
    start,end=signals.utc(value['StartsAt']),signals.utc(value['ExpiresAt'])
    require(dt.timedelta(0)<end-start<=dt.timedelta(hours=24),'FINITE_COHOST_WINDOW_REQUIRED')
    require(re.fullmatch(r'[A-Za-z0-9+=,.@_-]{1,64}',backup.get('ExpectedEc2RoleName','')) is not None,'SQL_ROLE_BINDING_REQUIRED')
    require(re.fullmatch(r'/[A-Za-z0-9/_-]+',backup.get('StagingDirectory','')) is not None and '..' not in Path(backup['StagingDirectory']).parts,'LOCAL_PRODUCER_STAGING_REQUIRED')
    return value

def external_binding(value,backup):
    validate(value,backup)
    return {'mode':'observer-check','run_id':value['RunId'],'subject':value['Subject'],'starts_at':value['StartsAt'],'expires_at':value['ExpiresAt'],'watchdog_seconds':value['WatchdogSeconds'],'observer_expected_up':value['ExpectedUp'],'sender_role_arn':'arn:aws:iam::'+value['Account']+':role/'+backup['ExpectedEc2RoleName']}


def integration(value,backup,inputs,artifact):
    """Pure projection to the existing TF config/schedule and SQL role; no API calls."""
    import copy
    import ec2_prepare as original
    validate(value,backup)
    require(backup['Bucket']==original.BUCKET and backup['BackupKeyArn']==original.KEY and backup['TextKeyArn']==original.TEXT_KEY and backup['ExpectedEc2RoleName']==original.ROLE.rsplit('/',1)[1],'EXISTING_SQL_STORAGE_ROLE_REQUIRED')
    require(backup['Prefix']==original.PREFIX+'/'+value['RunId'].removeprefix('ecs-sentinel-')+'t','EXACT_TARGET_BACKUP_PREFIX_REQUIRED')
    require(set(artifact)=={'Bucket','Key','VersionId','Sha256','BucketKeyEnabled'},'EXACT_ARTIFACT_DESCRIPTOR_REQUIRED')
    require(artifact['Bucket']==backup['Bucket'] and artifact['BucketKeyEnabled'] is False,'EXACT_ARTIFACT_BUCKET_CONTEXT_REQUIRED')
    require(re.fullmatch('[a-f0-9]{64}',artifact['Sha256']) is not None,'ARTIFACT_HASH_REQUIRED')
    expected='terragrunt-demo/dev/sql-backup-artifacts/'+value['RunId']+'/'+artifact['Sha256']+'/SqlBackup.tar'
    require(artifact['Key']==expected and re.fullmatch(r'[A-Za-z0-9+/=._-]{1,256}',artifact['VersionId']) is not None and artifact['VersionId']!='null','IMMUTABLE_ARTIFACT_REQUIRED')
    require(set(inputs)<= {'config','enable_observer','enable_ingestion','enable_dispatch_schedule','dispatch_schedule_enabled','dispatch_schedule_expression','allow_data_retirement','observer'} and 'config' in inputs,'EXISTING_SENTINEL_INPUTS_REQUIRED')
    require(inputs['config'].get('account')==value['Account'] and inputs['config'].get('region')==value['Region'],'EXACT_SENTINEL_ACCOUNT_REGION_REQUIRED')
    result=copy.deepcopy(inputs);binding=external_binding(value,backup)
    require(all(result['config'].get(k)==v for k,v in binding.items()),'WATCHDOG_AND_SQL_BINDING_MISMATCH')
    require(inputs.get('enable_observer',False) is False and inputs.get('observer') is None,'DEDICATED_OBSERVER_FORBIDDEN')
    require(inputs.get('allow_data_retirement',False) is False,'DATA_RETIREMENT_NOT_ADMITTED')
    staged=result|{'enable_observer':False,'enable_ingestion':False,'enable_dispatch_schedule':True,'dispatch_schedule_enabled':False,'dispatch_schedule_expression':'rate(1 minute)'}
    active=copy.deepcopy(staged);active.update(enable_ingestion=True,dispatch_schedule_enabled=True)
    queue='arn:aws:sqs:'+value['Region']+':'+value['Account']+':'+value['RunId']+'-ingestion'
    object_arn='arn:aws:s3:::'+artifact['Bucket']+'/'+artifact['Key']
    condition={'DateGreaterThanEquals':{'aws:CurrentTime':value['StartsAt']},'DateLessThan':{'aws:CurrentTime':value['ExpiresAt']}}
    send={'Version':'2012-10-17','Statement':[{'Sid':'SqlCohostSendOnly','Effect':'Allow','Action':'sqs:SendMessage','Resource':queue,'Condition':condition|{'StringEquals':{'aws:RequestedRegion':value['Region']}}}]}
    read={'Version':'2012-10-17','Statement':[{'Sid':'SqlCohostExactArtifactVersion','Effect':'Allow','Action':'s3:GetObjectVersion','Resource':object_arn,'Condition':condition|{'StringEquals':{'s3:VersionId':artifact['VersionId']}}},{'Sid':'SqlCohostArtifactDecryptViaS3','Effect':'Allow','Action':'kms:Decrypt','Resource':backup['BackupKeyArn'],'Condition':condition|{'StringEquals':{'kms:ViaService':'s3.'+value['Region']+'.amazonaws.com','kms:EncryptionContext:aws:s3:arn':object_arn}}}]}
    return {'StagedSentinelInputs':staged,'ActivationSentinelInputs':active,'SqlRoleArn':binding['sender_role_arn'],'SqlRoleSqsDelta':send,'SqlRoleArtifactDelta':read,'SqlTargetInput':{'sql_backup_cohost':{'artifact':artifact,'backup':backup,'sentinel':value,'enable_after_native_gates':False,'enable_producer_after_native_gates':False}},'ExecutionAuthorized':False,'AdditionalCloudAddresses':0,'ActivationRequires':['FRESH_CYCLE_APPROVAL','NATIVE_SUBSCRIPTION_CONFIRMED','NATIVE_SENTINEL_RUNTIME_AND_WATCHDOG_READBACK','POST_RESTORE_CREDENTIAL_BOOTSTRAP_COMPLETED'],'ObserverActivationRequires':['FRESH_CYCLE_APPROVAL','NATIVE_SUBSCRIPTION_CONFIRMED','NATIVE_SENTINEL_RUNTIME_AND_WATCHDOG_READBACK'],'ProducerActivationRequires':['FRESH_CYCLE_APPROVAL','POST_RESTORE_CREDENTIAL_BOOTSTRAP_COMPLETED'],'Artifact':artifact}


def render(value,backup,user,templates):
    validate(value,backup)
    require(re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',user) is not None,'SAFE_SERVICE_USER_REQUIRED')
    mapping={'OBSERVER_USER':user,'OBSERVER_CONFIG':str(CONFIG),'BACKUP_EXECUTABLE':str(ROOT/'bin/SqlBackup'),'AWS_CLI':'/usr/bin/aws','OBSERVER_SUBJECT':value['Subject'],'EXPECTED_UP':str(value['ExpectedUp']).lower(),'REMINDER_SECONDS':str(value['ReminderSeconds']),'AWS_ACCOUNT':value['Account'],'AWS_REGION':value['Region'],'SENTINEL_RUN_ID':value['RunId'],'PUBLISH_ATTEMPTS':str(value['PublishAttempts']),'SENTINEL_EXPIRES_AT':value['ExpiresAt']}
    service=templates['sql-backup-sentinel-producer.service.in'].decode()
    for key,item in mapping.items():service=service.replace('@'+key+'@',item)
    require('@' not in service,'UNRESOLVED_COHOST_PLACEHOLDER')
    gate=f'ExecStartPre=/usr/bin/python3 -I -B {ROOT}/cohost.py verify'
    service=service.replace('Type=oneshot','Type=oneshot\n'+gate)
    service=service.replace(' --aws --ec2-role',' --total-publish-attempts 20 --producer-job-receipt '+backup['StagingDirectory']+'/.service/last-job.json --aws --ec2-role')
    timer=f'[Unit]\nPartOf=sql-backup-cohost.target\nDescription=SQL-host backup observation; external watchdog covers telemetry loss\n[Timer]\nOnBootSec=90\nOnUnitActiveSec={value["CadenceSeconds"]}\nUnit=sql-backup-sentinel-producer.service\n[Install]\nWantedBy=timers.target\n'
    dropin='[Service]\n'+gate+'-producer\n'
    target='[Unit]\nDescription=SQL-host observation only, external Sentinel required\nWants=sql-backup-sentinel-producer.timer\nAfter=network-online.target\n[Install]\nWantedBy=multi-user.target\n'
    producer_target='[Unit]\nDescription=SQL backup producer after admitted credential handoff\nWants=sql-backup.timer\nAfter=network-online.target\n[Install]\nWantedBy=multi-user.target\n'
    return {'etc/systemd/system/sql-backup-sentinel-producer.service':service.encode(),'etc/systemd/system/sql-backup-sentinel-producer.timer':timer.encode(),'etc/systemd/system/sql-backup.service.d/sentinel-integrity.conf':dropin.encode(),'etc/systemd/system/sql-backup.timer.d/sentinel-cohost.conf':b'[Unit]\nPartOf=sql-backup-producer.target\n','etc/systemd/system/sql-backup-cohost.target':target.encode(),'etc/systemd/system/sql-backup-producer.target':producer_target.encode()}

def verify(root=Path('/'),now=None):
    # Trusted root-owned receipt is local integrity, not remote attestation.
    def file(relative):
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,'RECEIPT_PATH_REQUIRED')
        p=root/relative
        require(not any(x.is_symlink() for x in (p,*p.parents)) and p.is_file(),'INSTALLED_FILE_REQUIRED')
        require(p.stat().st_uid==os.geteuid() if root!=Path('/') else p.stat().st_uid==0,'ROOT_OWNED_INSTALL_REQUIRED')
        require(not p.stat().st_mode&0o022,'WRITABLE_INSTALL_DENIED')
        return p
    with file('opt/terragrunt-demo/sql-backup/install-receipt.json').open('rb') as stream:raw=stream.read(1048577)
    require(len(raw)<=1048576,'INSTALL_RECEIPT_TOO_LARGE')
    def unique(pairs):
        v={}
        for k,item in pairs:
            require(k not in v,'DUPLICATE_INSTALL_FIELD');v[k]=item
        return v
    receipt=json.loads(raw,object_pairs_hook=unique)
    require(receipt.get('ObserverPlacement')=='SQL_HOST','COHOST_INSTALL_REQUIRED')
    require(receipt.get('ActivationContract')=='COHOST_OBSERVER_PRODUCER_SPLIT_V1','SPLIT_ACTIVATION_INSTALL_REQUIRED')
    require(bool(receipt.get('InstalledFiles')),'INSTALLED_INVENTORY_REQUIRED')
    expected=set(receipt['InstalledFiles'])
    required={'opt/terragrunt-demo/sql-backup/'+name for name in FILES if not name.endswith('.in')}
    required|={'opt/terragrunt-demo/sql-backup/bin/SqlBackup','etc/terragrunt-demo/sql-backup/config.json','etc/terragrunt-demo/sql-backup/sentinel.json','etc/systemd/system/sql-backup-sentinel-producer.service','etc/systemd/system/sql-backup-sentinel-producer.timer','etc/systemd/system/sql-backup.service.d/sentinel-integrity.conf','etc/systemd/system/sql-backup.service','etc/systemd/system/sql-backup.timer','etc/systemd/system/sql-backup.timer.d/sentinel-cohost.conf','etc/systemd/system/sql-backup-cohost.target','etc/systemd/system/sql-backup-producer.target'}
    require(required<=expected,'COHOST_INVENTORY_INCOMPLETE')
    for relative,record in receipt['InstalledFiles'].items():
        p=file(relative)
        require(hashlib.sha256(p.read_bytes()).hexdigest()==record['Sha256'] and stat.S_IMODE(p.stat().st_mode)==record['Mode'],'INSTALLED_FILE_DRIFT')
    config=signals.read(root/str(CONFIG).lstrip('/'));settings=signals.read(root/str(SETTINGS).lstrip('/'));validate(settings,config)
    at=now or dt.datetime.now(dt.timezone.utc)
    require(signals.utc(settings['StartsAt'])<=at<signals.utc(settings['ExpiresAt']),'COHOST_WINDOW_NOT_ACTIVE')
    return {'Status':'VERIFIED_LOCAL_INSTALL','Placement':'SQL_HOST','FailureDomain':'SHARED_WITH_SQL','IndependentS3Observation':False,'ExternalWatchdogRequired':True,'WatchdogSeconds':settings['WatchdogSeconds'],'ExpectedUp':settings['ExpectedUp'],'ServicesStarted':False}


def producer_ready(root=Path('/'),now=None):
    """Root-side producer gate; observer never reads SQL credential material."""
    verify(root,now)
    config=signals.read(root/str(CONFIG).lstrip('/'))
    directory=root/'etc/terragrunt-demo/sql-backup/credentials'
    require(not any(p.is_symlink() for p in (directory,*directory.parents)) and directory.is_dir(),'POST_RESTORE_CREDENTIALS_REQUIRED')
    require(stat.S_IMODE(directory.stat().st_mode)==0o700,'PRIVATE_CREDENTIAL_MATERIAL_REQUIRED')
    for name in ('bootstrap-receipt.json','backup-connection','verify-connection'):
        p=directory/name
        require(p.is_file() and not p.is_symlink() and p.stat().st_uid==os.geteuid() and stat.S_IMODE(p.stat().st_mode)==0o600,'PRIVATE_CREDENTIAL_MATERIAL_REQUIRED')
    completed=signals.read(directory/'bootstrap-receipt.json')
    require(completed.get('Status')=='PROVISIONED_NOT_STARTED' and completed.get('Database')==config['Database'],'POST_RESTORE_CREDENTIALS_REQUIRED')
    dropin=root/'etc/systemd/system/sql-backup.service.d'
    require({p.name for p in dropin.iterdir()}<={'sentinel-integrity.conf','credentials.conf'},'FOREIGN_CREDENTIAL_DROPIN')
    credentials=dropin/'credentials.conf'
    require(credentials.is_file() and not credentials.is_symlink(),'PRODUCER_CREDENTIAL_DROPIN_REQUIRED')
    require(credentials.stat().st_uid==os.geteuid() and stat.S_IMODE(credentials.stat().st_mode)==0o644,'CREDENTIAL_DROPIN_DRIFT')
    expected_credentials='[Service]\nLoadCredential=\nLoadCredential=backup-connection:/etc/terragrunt-demo/sql-backup/credentials/backup-connection\nLoadCredential=verify-connection:/etc/terragrunt-demo/sql-backup/credentials/verify-connection\n'
    require(credentials.read_text()==expected_credentials,'CREDENTIAL_DROPIN_DRIFT')
    return {'Status':'VERIFIED_PRODUCER_HANDOFF','Database':config['Database'],'BackupSuccess':False}

def activate(root=Path('/'),apply=False,confirmation=None,system=subprocess.run,now=None,component='observer'):
    """Independent opt-ins. Hash acknowledgement is not owner/native admission."""
    require(component in ('observer','producer','both'),'EXPLICIT_COMPONENT_REQUIRED')
    verify(root,now)
    if component in ('producer','both'):producer_ready(root,now)
    install=root/'opt/terragrunt-demo/sql-backup/install-receipt.json'
    with install.open('rb') as stream:raw=stream.read(1048577)
    require(len(raw)<=1048576,'INSTALL_RECEIPT_TOO_LARGE');sha=json.loads(raw)['PackageSha256']
    actions=[['/usr/bin/systemctl','daemon-reload']]
    if component in ('observer','both'):actions.append(['/usr/bin/systemctl','enable','--now','sql-backup-cohost.target'])
    if component in ('producer','both'):actions.append(['/usr/bin/systemctl','enable','--now','sql-backup-producer.target'])
    result={'Status':'ACTIVATION_PLAN','Component':component,'PackageSha256':sha,'Actions':actions,'ServicesStarted':False,'NativeAcceptance':False,'ExternalReadiness':'REQUIRES_SEPARATE_NATIVE_ADMISSION'}
    if not apply:return result
    require(confirmation==sha and os.geteuid()==0,'EXPLICIT_ROOT_ACTIVATION_REQUIRED')
    require(root==Path('/') or system is not subprocess.run,'FIXTURE_REQUIRES_DOUBLE_PORT')
    for action in actions:
        try:response=system(action,capture_output=True,timeout=30,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/nonexistent','LANG':'C'})
        except (OSError,subprocess.TimeoutExpired):raise ValueError('ACTIVATION_UNCERTAIN_NO_RETRY') from None
        require(response.returncode==0,'ACTIVATION_FAILED_RECONCILE_NO_RETRY')
    return result|{'Status':'ACTIVATION_REQUEST_ACCEPTED','ServicesStarted':True,'NativeAcceptance':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['verify','verify-producer','activate']);p.add_argument('--component',choices=['observer','producer','both'],default='observer');p.add_argument('--apply',action='store_true');p.add_argument('--confirm-root-activation');args=p.parse_args()
    require(args.action=='activate' or not (args.apply or args.confirm_root_activation),'VERIFY_IS_READ_ONLY')
    print(json.dumps(verify() if args.action=='verify' else producer_ready() if args.action=='verify-producer' else activate(apply=args.apply,confirmation=args.confirm_root_activation,component=args.component),separators=(',',':')))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'Status':'REFUSED','Code':str(e) if isinstance(e,(ValueError,signals.Refused)) else 'COHOST_INTEGRITY_FAILED'}));raise SystemExit(1)
