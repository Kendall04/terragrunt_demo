#!/usr/bin/env python3
"""Local scheduled-job lifecycle. No AWS implementation or credential persistence."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

class Refused(Exception): pass
class Unknown(Refused): pass

def private(path):
    if not path.is_absolute(): raise Refused('ABSOLUTE_PATH_REQUIRED')
    for item in (path,*path.parents):
        if item.is_symlink(): raise Refused('SYMLINK_DENIED')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    if stat.S_IMODE(path.stat().st_mode)&0o077: raise Refused('PRIVATE_DIRECTORY_REQUIRED')

def write(path,value):
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream: json.dump(value,stream)
    os.replace(temporary,path)

def lock(path,wait):
    if path.is_symlink(): raise Refused('SYMLINK_DENIED')
    descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    end=time.monotonic()+wait
    while True:
        try: fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB); return descriptor
        except BlockingIOError:
            if time.monotonic()>=end: os.close(descriptor); raise Refused('JOB_ACTIVE')
            time.sleep(0.05)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','inhibit','resume','status'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--executable',type=Path)
    parser.add_argument('--wait-seconds',type=int,default=30)
    parser.add_argument('--local-sql-self-signed',action='store_true')
    args=parser.parse_args()
    if not 0<=args.wait_seconds<=3600: raise Refused('INVALID_WAIT_BOUND')
    if args.config.stat().st_size>65536: raise Refused('CONFIG_TOO_LARGE')
    options=json.loads(args.config.read_text())
    staging=Path(options['StagingDirectory']); private(staging)
    control=staging/'.service'; private(control)
    owner=control/'owner.json'
    expected={'SchemaVersion':1,'Database':options['Database'],'Bucket':options['Bucket'],'Prefix':options['Prefix'],'StagingDirectory':str(staging)}
    if owner.exists():
        if owner.is_symlink() or json.loads(owner.read_text())!=expected: raise Refused('SERVICE_OWNERSHIP_MISMATCH')
    else: write(owner,expected)
    inhibited=control/'inhibited.json'
    state=control/'last-job.json'
    if args.action=='inhibit':
        write(inhibited,{'Status':'INHIBITED','RequestedUtc':time.time()})
    held=lock(control/'job.lock',args.wait_seconds if args.action=='inhibit' else 0)
    try:
        if args.action=='inhibit':
            previous=json.loads(state.read_text()) if state.exists() else {}
            return {'Status':'INHIBITED_LOCAL_IDLE','RemoteOutcome':previous.get('Status','NOT_OBSERVED'),'SQLQuiescence':'NOT_CERTIFIED'}
        if args.action=='resume':
            if inhibited.is_symlink(): raise Refused('SYMLINK_DENIED')
            inhibited.unlink(missing_ok=True)
            previous=json.loads(state.read_text()) if state.exists() else {}
            write(state,{'Status':'OPERATOR_RESUMED','PreviousOutcome':previous.get('Status'),'Utc':time.time()})
            return {'Status':'RESUMED','RemoteEffects':'NOT_REPLAYED'}
        if args.action=='status':
            return {'Status':'INHIBITED' if inhibited.exists() else 'IDLE','LastJob':json.loads(state.read_text()).get('Status') if state.exists() else None}
        if inhibited.exists(): raise Refused('BACKUP_INHIBITED')
        previous=json.loads(state.read_text()) if state.exists() else {}
        if previous.get('Status') in ('STARTED','UNKNOWN'): raise Refused('PREVIOUS_JOB_REQUIRES_REVIEW')
        if not args.executable or not args.executable.is_absolute() or args.executable.is_symlink() or not args.executable.is_file(): raise Refused('EXECUTABLE_REQUIRED')
        if args.executable.stat().st_mode&0o022: raise Refused('WRITABLE_EXECUTABLE_DENIED')
        credential_dir=Path(os.environ.get('CREDENTIALS_DIRECTORY',''))
        if not credential_dir.is_absolute(): raise Refused('RUNTIME_CREDENTIALS_REQUIRED')
        private(credential_dir)
        child=dict(os.environ)
        for filename,variable in [('backup-connection','SQL_BACKUP_CONNECTION_STRING'),('verify-connection','SQL_VERIFY_CONNECTION_STRING')]:
            path=credential_dir/filename
            if path.is_symlink() or not path.is_file() or path.stat().st_size>8192 or path.stat().st_mode&0o077: raise Refused('PRIVATE_CREDENTIAL_FILE_REQUIRED')
            child[variable]=path.read_text().rstrip('\r\n')
            if not child[variable]: raise Refused('EMPTY_CREDENTIAL')
        write(state,{'Status':'STARTED','Utc':time.time()})
        flags=['--config',str(args.config),'--aws','--ec2-role']
        if args.local_sql_self_signed: flags+=['--local-sql-self-signed']
        seconds=int(options.get('TimeoutSeconds',600))
        if not 10<=seconds<=600: raise Refused('INVALID_JOB_DEADLINE')
        timeout=seconds+30
        try:
            result=subprocess.run([str(args.executable),'backup',*flags],capture_output=True,text=True,env=child,timeout=timeout)
            body=json.loads(result.stdout) if len(result.stdout)<=65536 and result.stdout.strip().startswith('{') else {}
            if body.get('Code')=='DEADLINE_EXCEEDED': raise Unknown('CLIENT_DEADLINE_REMOTE_EFFECTS_NOT_CERTIFIED')
            if result.returncode!=0 or body.get('Status')!='REMOTE_VERIFIED': raise Refused('BACKUP_FAILED_OR_UNCONFIRMED')
            for variable in ('SQL_BACKUP_CONNECTION_STRING','SQL_VERIFY_CONNECTION_STRING'): child.pop(variable,None)
            result=subprocess.run([str(args.executable),'cleanup',*flags],capture_output=True,text=True,env=child,timeout=timeout)
            body=json.loads(result.stdout) if result.returncode==0 and len(result.stdout)<=65536 else {}
            if result.returncode!=0 or body.get('Status')!='LOCAL_CLEANUP_VERIFIED': raise Refused('REMOTE_VERIFIED_CLEANUP_INCOMPLETE')
            outcome={'Status':'REMOTE_VERIFIED_CLEANUP_VERIFIED','Utc':time.time()}
            write(state,outcome); return outcome
        except subprocess.TimeoutExpired:
            write(state,{'Status':'UNKNOWN','Code':'CLIENT_DEADLINE','Utc':time.time()})
            raise Refused('CLIENT_DEADLINE_REMOTE_EFFECTS_NOT_CERTIFIED')
        except Unknown:
            write(state,{'Status':'UNKNOWN','Code':'CLIENT_DEADLINE','Utc':time.time()})
            raise
        except Exception:
            write(state,{'Status':'FAILED_OR_UNCONFIRMED','Utc':time.time()})
            raise
    finally: os.close(held)

if __name__=='__main__':
    try: print(json.dumps(main(),separators=(',',':')))
    except Exception as error:
        print(json.dumps({'Status':'FAILED','Code':str(error) if isinstance(error,Refused) else 'HOST_OPERATION_FAILED'}),file=sys.stderr)
        raise SystemExit(1)
