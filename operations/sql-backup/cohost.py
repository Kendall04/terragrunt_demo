#!/usr/bin/env python3
"""SQL-host observer configuration and startup integrity gate. No transport or service control."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import stat
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
    dropin='[Service]\n'+gate+'\n'
    target='[Unit]\nDescription=SQL backup and local observation, external Sentinel required\nWants=sql-backup.timer sql-backup-sentinel-producer.timer\nAfter=network-online.target\n[Install]\nWantedBy=multi-user.target\n'
    return {'etc/systemd/system/sql-backup-sentinel-producer.service':service.encode(),'etc/systemd/system/sql-backup-sentinel-producer.timer':timer.encode(),'etc/systemd/system/sql-backup.service.d/sentinel-integrity.conf':dropin.encode(),'etc/systemd/system/sql-backup.timer.d/sentinel-cohost.conf':b'[Unit]\nPartOf=sql-backup-cohost.target\n','etc/systemd/system/sql-backup-cohost.target':target.encode()}

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
    require(bool(receipt.get('InstalledFiles')),'INSTALLED_INVENTORY_REQUIRED')
    expected=set(receipt['InstalledFiles'])
    required={'opt/terragrunt-demo/sql-backup/'+name for name in FILES if not name.endswith('.in')}
    required|={'opt/terragrunt-demo/sql-backup/bin/SqlBackup','etc/terragrunt-demo/sql-backup/config.json','etc/terragrunt-demo/sql-backup/sentinel.json','etc/systemd/system/sql-backup-sentinel-producer.service','etc/systemd/system/sql-backup-sentinel-producer.timer','etc/systemd/system/sql-backup.service.d/sentinel-integrity.conf','etc/systemd/system/sql-backup.service','etc/systemd/system/sql-backup.timer','etc/systemd/system/sql-backup.timer.d/sentinel-cohost.conf','etc/systemd/system/sql-backup-cohost.target'}
    require(required<=expected,'COHOST_INVENTORY_INCOMPLETE')
    for relative,record in receipt['InstalledFiles'].items():
        p=file(relative)
        require(hashlib.sha256(p.read_bytes()).hexdigest()==record['Sha256'] and stat.S_IMODE(p.stat().st_mode)==record['Mode'],'INSTALLED_FILE_DRIFT')
    config=signals.read(root/str(CONFIG).lstrip('/'));settings=signals.read(root/str(SETTINGS).lstrip('/'));validate(settings,config)
    at=now or dt.datetime.now(dt.timezone.utc)
    require(signals.utc(settings['StartsAt'])<=at<signals.utc(settings['ExpiresAt']),'COHOST_WINDOW_NOT_ACTIVE')
    return {'Status':'VERIFIED_LOCAL_INSTALL','Placement':'SQL_HOST','FailureDomain':'SHARED_WITH_SQL','IndependentS3Observation':False,'ExternalWatchdogRequired':True,'WatchdogSeconds':settings['WatchdogSeconds'],'ExpectedUp':settings['ExpectedUp'],'ServicesStarted':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['verify']);p.parse_args()
    print(json.dumps(verify(),separators=(',',':')))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'Status':'REFUSED','Code':str(e) if isinstance(e,(ValueError,signals.Refused)) else 'COHOST_INTEGRITY_FAILED'}));raise SystemExit(1)
