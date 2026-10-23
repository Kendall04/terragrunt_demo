#!/usr/bin/env python3
"""Finite independent backup check + local transition candidates. No notification transport."""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import signals

class Refused(ValueError): pass

def safe_path(path):
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
        raise Refused('SAFE_ABSOLUTE_PATH_REQUIRED')
    return path

def parse_health(body):
    if len(body)>65536: raise Refused('CHECK_OUTPUT_TOO_LARGE')
    def unique(pairs):
        value={}
        for k,v in pairs:
            if k in value: raise Refused('DUPLICATE_CHECK_FIELD')
            value[k]=v
        return value
    try: value=json.loads(body,object_pairs_hook=unique)
    except (ValueError,UnicodeError): raise Refused('INVALID_CHECK_OUTPUT') from None
    if not isinstance(value,dict): raise Refused('INVALID_CHECK_OUTPUT')
    return value

def health(value,observed,exit_code,job=None):
    # Reuse existing exact field/pair/time/exit validation; never copy raw fields.
    valid=signals.render('health',value,observed,exit_code)
    coverage='NOT_PROVIDED'
    if job is not None:
        signals.render('job',job,observed)
        coverage='LOCAL_RECEIPT_ONLY'
        latest=valid['LastSuccessUtc']
        later=latest is None or job['Utc']>signals.utc(latest).timestamp()
        if valid['Status']!='MAINTENANCE' and job['Status']=='FAILED_OR_UNCONFIRMED' and later:
            valid=signals.render('health',{'Status':'FAILED','Code':'LAST_ATTEMPT_FAILED','LastSuccessUtc':latest},observed,1)
    return {k:valid[k] for k in ('Status','Code','Severity','LastSuccessUtc')}|{'ProducerFailureCoverage':coverage}

def transition(current,observed,previous,subject,scope,repeat_seconds):
    now=signals.utc(observed)
    if not isinstance(subject,str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',subject): raise Refused('SUBJECT_REQUIRED')
    if not isinstance(scope,str) or not re.fullmatch('[a-f0-9]{64}',scope): raise Refused('CONFIG_BINDING_REQUIRED')
    if type(repeat_seconds) is not int or not 0<=repeat_seconds<=604800: raise Refused('REMINDER_BOUND_REQUIRED')
    condition=[current['Status'],current['Code']]
    if previous is not None:
        keys={'SchemaVersion','Subject','ConfigSha256','LastObservedUtc','Condition','LastNoticeUtc','IncidentOpen'}
        if set(previous)!=keys or previous['SchemaVersion']!=1 or type(previous['SchemaVersion']) is not int: raise Refused('STATE_SHAPE')
        if previous['Subject']!=subject or previous['ConfigSha256']!=scope: raise Refused('STATE_SCOPE_MISMATCH')
        if signals.utc(previous['LastObservedUtc'])>now: raise Refused('CLOCK_REGRESSION')
        old=previous['Condition'];opened=previous['IncidentOpen'];notice=previous['LastNoticeUtc']
        if type(opened) is not bool or (old is not None and (not isinstance(old,list) or len(old)!=2 or not isinstance(old[0],str) or signals.PAIRS.get(old[0])!=old[1] or old[0]=='MAINTENANCE')): raise Refused('STATE_CONDITION')
        if opened!=(old is not None and old[0]!='HEALTHY'): raise Refused('STATE_INCIDENT')
        if notice is not None and signals.utc(notice)>signals.utc(previous['LastObservedUtc']): raise Refused('STATE_NOTICE_TIME')
        if opened and notice is None: raise Refused('STATE_NOTICE_REQUIRED')
    else: old=None;opened=False;notice=None
    emit=False;reason='UNCHANGED';next_condition=old
    if current['Status']=='MAINTENANCE': reason='MAINTENANCE'
    elif current['Status']=='HEALTHY':
        emit=opened;reason='RECOVERED' if opened else 'BASELINE_HEALTHY' if old is None else 'UNCHANGED'
        opened=False;next_condition=condition
    else:
        if not opened or old!=condition: emit=True;reason='INITIAL_ATTENTION' if old is None else 'CONDITION_CHANGED'
        elif repeat_seconds and (now-signals.utc(notice)).total_seconds()>=repeat_seconds: emit=True;reason='REMINDER_DUE'
        opened=True;next_condition=condition
    if emit: notice=observed
    state={'SchemaVersion':1,'Subject':subject,'ConfigSha256':scope,'LastObservedUtc':observed,'Condition':next_condition,'LastNoticeUtc':notice,'IncidentOpen':opened}
    event={'SchemaVersion':1,'Source':'SqlBackup.Observer','Subject':subject,'ObservedUtc':observed,**current,'Emit':emit,'Reason':reason,'Delivery':'NONE','SentinelIntegrated':False,'RemediationAllowed':False}
    return state,event

@contextmanager
def owner(directory):
    directory=safe_path(directory);directory.mkdir(mode=0o700,exist_ok=True)
    if os.name=='posix' and stat.S_IMODE(directory.stat().st_mode)&0o077: raise Refused('PRIVATE_STATE_DIRECTORY_REQUIRED')
    path=directory/'observer.lock'
    try: descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    except FileExistsError: raise Refused('OBSERVER_ACTIVE_OR_INTERRUPTED') from None
    identity=os.fstat(descriptor)
    try:
        yield directory
    finally:
        os.close(descriptor)
        if path.exists() and not path.is_symlink() and os.path.samestat(identity,path.stat()): path.unlink()
        # Interrupted ownership is never stolen; no PID cleanup or stale-lock takeover.

def save(path,value):
    temporary=path.with_name(path.name+'.pending')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,separators=(',',':'));stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()

def run(args,runner=subprocess.run,clock=lambda:dt.datetime.now(dt.timezone.utc),before_state_save=None):
    config=safe_path(args.config)
    with config.open('rb') as stream: raw=stream.read(65537)
    if len(raw)>65536: raise Refused('CONFIG_TOO_LARGE')
    scope=hashlib.sha256(raw).hexdigest()
    with owner(args.state_directory) as directory:
        state_path=safe_path(directory/'observer-state.json')
        previous=signals.read(state_path) if state_path.exists() else None
        observed=args.observed_at if args.action=='replay' else clock().isoformat()
        transition(health({'Status':'MAINTENANCE','Code':'NOT_EXPECTED_UP'},observed,0),observed,previous,args.subject,scope,args.repeat_after_seconds)
        if args.expected_up=='false': current=health({'Status':'MAINTENANCE','Code':'NOT_EXPECTED_UP'},observed,0)
        elif args.action=='replay':
            job=signals.read(safe_path(args.producer_job_receipt)) if args.producer_job_receipt else None
            current=health(signals.read(safe_path(args.health_receipt)),observed,args.health_exit_code,job)
        else:
            if not args.aws or not args.ec2_role: raise Refused('EXPLICIT_EC2_READ_GATE_REQUIRED')
            if args.executable is None: raise Refused('CHECK_EXECUTABLE_REQUIRED')
            executable=safe_path(args.executable)
            if not executable.is_file(): raise Refused('CHECK_EXECUTABLE_REQUIRED')
            # Pass only process/runtime settings, never copy SQL/AWS credential values.
            allowed=('PATH','SystemRoot','WINDIR','TEMP','TMP','LANG','LC_ALL','DOTNET_ROOT','DOTNET_ROOT_X64')
            env={key:os.environ[key] for key in allowed if key in os.environ}
            env.update(AWS_EC2_METADATA_V1_DISABLED='true',DOTNET_CLI_TELEMETRY_OPTOUT='1')
            # Existing CLI owns its native TimeoutSeconds cancellation. Never call
            # backup/restore/cleanup, retry, acquire SQL credentials or kill a PID.
            try:
                result=runner([str(executable),'check','--config',str(config),'--expected-up','true','--aws','--ec2-role'],capture_output=True,env=env)
                observed=clock().isoformat()
                job=signals.read(safe_path(args.producer_job_receipt)) if args.producer_job_receipt else None
                current=health(parse_health(result.stdout),observed,result.returncode,job)
            except (Refused,signals.Refused,OSError):
                current=health({'Status':'UNKNOWN','Code':'REMOTE_STORAGE_NOT_CHECKED'},observed,1)
        state,event=transition(current,observed,previous,args.subject,scope,args.repeat_after_seconds)
        event['Evaluation']='EXPECTED_UP_FALSE' if args.expected_up=='false' else 'LOCAL_RECEIPT_REPLAY' if args.action=='replay' else 'CHECK_COMMAND_RESULT'
        event['CheckInvoked']=args.action=='run' and args.expected_up=='true'
        if before_state_save is not None: before_state_save(state,event)
        save(state_path,state)
        return event

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['run','replay'])
    for flag in ['config','state-directory']:p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--subject',required=True);p.add_argument('--expected-up',choices=['true','false'],required=True)
    p.add_argument('--repeat-after-seconds',type=int,required=True,help='0 disables repeat reminders; changes/recovery still emit')
    p.add_argument('--executable',type=Path);p.add_argument('--aws',action='store_true');p.add_argument('--ec2-role',action='store_true')
    p.add_argument('--health-receipt',type=Path);p.add_argument('--health-exit-code',type=int);p.add_argument('--observed-at');p.add_argument('--producer-job-receipt',type=Path)
    a=p.parse_args()
    if a.action=='replay' and (a.aws or a.ec2_role or not a.observed_at or not a.health_receipt or a.health_exit_code is None): raise Refused('REPLAY_INPUTS_REQUIRED_NO_CLOUD')
    if a.action=='run' and (a.observed_at or a.health_receipt or a.health_exit_code is not None): raise Refused('LIVE_REPLAY_INPUTS_DENIED')
    event=run(a);print(json.dumps(event,separators=(',',':')))
    return 0 if event['Status'] in ('HEALTHY','MAINTENANCE') else 1

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        # Never echo OS/SDK/JSON errors, arguments, raw child output or secret data.
        print(json.dumps({'Status':'REFUSED','Code':str(error) if isinstance(error,(Refused,signals.Refused)) else 'OBSERVER_REFUSED'}));raise SystemExit(2)
