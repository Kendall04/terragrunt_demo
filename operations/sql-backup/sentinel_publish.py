#!/usr/bin/env python3
"""Finite EC2-role SQS delivery with one durable pending observation; never installs or authenticates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import observer
import signals

class Refused(ValueError): pass

def binding(args):
    if not re.fullmatch(r'[0-9]{12}',args.account) or not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]',args.region) or not re.fullmatch(r'ecs-sentinel-[a-z0-9-]{1,24}',args.run_id):
        raise Refused('EXACT_QUEUE_BINDING_REQUIRED')
    return f'https://sqs.{args.region}.amazonaws.com/{args.account}/{args.run_id}-ingestion'

def send(args,payload,runner=subprocess.run):
    executable=observer.safe_path(args.aws_cli)
    if not executable.is_file() or not args.aws or not args.ec2_role: raise Refused('EXPLICIT_EC2_PUBLISH_GATE_REQUIRED')
    # No profile, custom endpoint, inherited AWS credentials or CLI config paths.
    env={k:os.environ[k] for k in ('PATH','SystemRoot','WINDIR','LANG','LC_ALL') if k in os.environ}
    env.update(AWS_EC2_METADATA_V1_DISABLED='true',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,AWS_MAX_ATTEMPTS='1',AWS_PAGER='')
    try:
        response=runner([str(executable),'sqs','send-message','--region',args.region,'--queue-url',binding(args),'--message-body',payload,'--output','json','--no-cli-pager','--cli-connect-timeout','5','--cli-read-timeout','10'],capture_output=True,env=env)
        if response.returncode!=0:
            # Classify only well-known CLI error codes; never echo stderr/provider details.
            if re.search(rb'\((?:AccessDenied(?:Exception)?|UnauthorizedOperation|UnrecognizedClientException|InvalidClientTokenId)\)',response.stderr or b''):
                raise Refused('PUBLISH_ACCESS_DENIED_NO_AUTOMATIC_RETRY')
            return None
        parsed=observer.parse_health(response.stdout)
        mid=parsed.get('MessageId')
        return mid if isinstance(mid,str) and re.fullmatch(r'[a-zA-Z0-9-]{1,128}',mid) else None
    except (OSError,observer.Refused):return None

def run(args,runner=subprocess.run,clock=lambda:__import__('datetime').datetime.now(__import__('datetime').timezone.utc)):
    queue=binding(args)
    if args.action!='run' or not args.aws or not args.ec2_role:raise Refused('LIVE_CHECK_ONLY')
    if type(args.publish_attempts) is not int or not 1<=args.publish_attempts<=3:raise Refused('EXPLICIT_PUBLISH_ATTEMPT_BOUND_REQUIRED')
    if clock()>=signals.utc(args.expires_at):raise Refused('PUBLISH_WINDOW_EXPIRED')
    config=observer.safe_path(args.config);raw=config.read_bytes()
    if len(raw)>65536:raise Refused('CONFIG_TOO_LARGE')
    scope=hashlib.sha256(raw).hexdigest()
    state_root=observer.safe_path(args.state_directory);state_root.mkdir(mode=0o700,exist_ok=True)
    if os.name=='posix' and stat.S_IMODE(state_root.stat().st_mode)&0o077:raise Refused('PRIVATE_STATE_DIRECTORY_REQUIRED')
    with observer.owner(state_root/'delivery') as directory:
        pending=directory/'pending.json'
        def flush():
            item=signals.read(pending)
            if set(item)!={'SchemaVersion','Subject','ConfigSha256','QueueUrl','Payload','PayloadSha256','Attempts','Blocked'} or item['SchemaVersion']!=1 or item['Subject']!=args.subject or item['ConfigSha256']!=scope or item['QueueUrl']!=queue:
                raise Refused('PENDING_SCOPE_MISMATCH')
            payload=item['Payload']
            if not isinstance(payload,str) or len(payload.encode())>65536 or hashlib.sha256(payload.encode()).hexdigest()!=item['PayloadSha256']:
                raise Refused('PENDING_PAYLOAD_MISMATCH')
            if item['Blocked'] is not None:raise Refused('PUBLISH_BLOCKED_REQUIRES_REVIEW')
            if type(item['Attempts']) is not int or not 0<=item['Attempts']<args.publish_attempts:raise Refused('PUBLISH_ATTEMPT_BUDGET_EXHAUSTED')
            item['Attempts']+=1;observer.save(pending,item)
            try:result=send(args,payload,runner)
            except Refused:
                item['Blocked']='ACCESS_OR_SCOPE_REFUSED';observer.save(pending,item);raise
            if result is None:return {'Status':'PENDING','Code':'SQS_ACCEPTANCE_UNCONFIRMED','MayDuplicateOnRetry':True}
            # Preserve acceptance before deleting pending. A crash may redeliver the identical payload.
            observer.save(directory/'last-enqueued.json',{'SchemaVersion':1,'PayloadSha256':item['PayloadSha256'],'MessageId':result,'Acceptance':'SQS_ONLY_NOT_SENTINEL_OR_EMAIL'})
            pending.unlink()
            return {'Status':'ENQUEUED','Code':'SQS_ACCEPTED','MessageId':result,'Acceptance':'SQS_ONLY_NOT_SENTINEL_OR_EMAIL'}
        if pending.exists():return flush() # Drain before newer observation; no overwrite/unbounded spool.
        def persist(state,event):
            if event['Status']=='MAINTENANCE':return
            payload=json.dumps(event,separators=(',',':'),sort_keys=True)
            observer.save(pending,{'SchemaVersion':1,'Subject':args.subject,'ConfigSha256':scope,'QueueUrl':queue,'Payload':payload,'PayloadSha256':hashlib.sha256(payload.encode()).hexdigest(),'Attempts':0,'Blocked':None})
        observer.run(args,runner=runner,clock=clock,before_state_save=persist)
        return flush() if pending.exists() else {'Status':'SUPPRESSED','Code':'MAINTENANCE_NO_PUBLISH'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['config','state-directory','executable','aws-cli']:p.add_argument('--'+flag,type=Path,required=True)
    for flag in ['subject','account','region','run-id']:p.add_argument('--'+flag,required=True)
    p.add_argument('--expected-up',choices=['true','false'],required=True)
    p.add_argument('--repeat-after-seconds',type=int,required=True)
    p.add_argument('--producer-job-receipt',type=Path)
    p.add_argument('--publish-attempts',type=int,required=True);p.add_argument('--expires-at',required=True)
    p.add_argument('--aws',action='store_true');p.add_argument('--ec2-role',action='store_true')
    a=p.parse_args();a.action='run';a.observed_at=None;a.health_receipt=None;a.health_exit_code=None
    result=run(a);print(json.dumps(result,separators=(',',':')));return 1 if result['Status']=='PENDING' else 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        print(json.dumps({'Status':'REFUSED','Code':str(e) if isinstance(e,(Refused,observer.Refused,signals.Refused)) else 'PUBLISHER_REFUSED'}));raise SystemExit(2)
