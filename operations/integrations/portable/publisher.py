"""Bounded portable publication. One atomic journal, no implicit retry or authentication."""
import datetime as dt
import hashlib,json,os,re,stat,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bridge
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sql-backup'))
import observer,signals

class Refused(ValueError):pass
def require(v,code):
 if not v:raise Refused(code)
def encode(v):return json.dumps(v,separators=(',',':'),sort_keys=True)
def digest(v):return hashlib.sha256(encode(v).encode()).hexdigest()
def commit(path,value):
 observer.save(path,value)
 if os.name=='posix':
  fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
def scope(config,manifest,subject,expires_at):
 bridge.binding(config,manifest)
 require(re.fullmatch('[a-z][a-z0-9-]{0,29}',manifest['deployment']) is not None,'EXACT_BUS_REQUIRED')
 require(subject==config['subject'],'EXACT_SUBJECT_REQUIRED')
 signals.utc(expires_at)
 return digest({'Config':config,'Manifest':manifest,'Subject':subject,'ExpiresAt':expires_at,'Limit':20,'PerEntry':3,'Transport':'EVENTBRIDGE_REPORT_V1'})
def validate_entry(entry,config,manifest):
 require(set(entry)=={'EventBusName','Source','DetailType','Detail'},'EXACT_ENTRY_REQUIRED')
 require(entry['EventBusName']==manifest['deployment'] and entry['Source']=='sentinel.report.'+config['producer'] and entry['DetailType']=='Sentinel Observation v1','ENTRY_TARGET_DRIFT')
 report=bridge.read_unique(entry['Detail']);require(set(report)==set('schemaVersion monitor producer id resource generation observedAt dataAt verdict assurance runId detail backupType'.split()),'EXACT_REPORT_REQUIRED')
 m=next((m for m in manifest['monitors'] if m['id']==report['monitor']),None);require(m is not None,'REPORT_SCOPE_DRIFT')
 require(report['schemaVersion']==1 and report['producer']==config['producer'] and report['resource']==m['resource'] and report['generation']==m['generation'],'REPORT_BINDING_DRIFT')
 require(report['verdict'] in ('Pass','Unknown') and report['assurance'] in ('Reported','Artifact'),'REPORT_ASSURANCE_DRIFT')
 require(report['backupType']==('full' if m['kind']=='sql-backup' else None),'REPORT_TYPE_DRIFT')
 require(re.fullmatch('[a-f0-9]{64}',report['id']) is not None and re.fullmatch('[a-f0-9]{64}',report['runId']) is not None,'REPORT_ID_REQUIRED')
 require(signals.utc(report['dataAt'])<=signals.utc(report['observedAt']),'REPORT_TIME_DRIFT')
 return report['id']
def journal(path,binding,config,manifest):
 if not path.exists():return {'SchemaVersion':1,'ScopeSha256':binding,'Limit':20,'PerEntry':3,'Entries':[]}
 j=signals.read(path)
 require(set(j)=={'SchemaVersion','ScopeSha256','Limit','PerEntry','Entries'} and type(j['SchemaVersion']) is int and j['SchemaVersion']==1 and j['ScopeSha256']==binding and j['Limit']==20 and j['PerEntry']==3,'JOURNAL_SCOPE_MISMATCH')
 require(isinstance(j['Entries'],list) and len(j['Entries'])<=20,'JOURNAL_BOUND')
 ids=[];attempts=0
 for e in j['Entries']:
  require(set(e)=={'Entry','Sha256','Id','Attempts','Status','EventId'},'JOURNAL_ENTRY_SHAPE')
  require(e['Id']==validate_entry(e['Entry'],config,manifest) and digest(e['Entry'])==e['Sha256'],'JOURNAL_PAYLOAD_DRIFT')
  require(type(e['Attempts']) is int and 0<=e['Attempts']<=3 and e['Status'] in ('PENDING','ACCEPTED','BLOCKED'),'JOURNAL_ATTEMPTS')
  require((e['Status']=='ACCEPTED' and e['Attempts']>0 and isinstance(e['EventId'],str) and re.fullmatch('[A-Za-z0-9-]{1,128}',e['EventId']) is not None) or (e['Status']!='ACCEPTED' and e['EventId'] is None),'JOURNAL_ACCEPTANCE')
  ids.append(e['Id']);attempts+=e['Attempts']
 require(len(set(ids))==len(ids) and attempts<=20,'JOURNAL_BUDGET_OR_ID_COLLISION')
 return j
def denied(code):return bool(re.search('AccessDenied|Unauthorized|NotAuthorized|UnrecognizedClient|InvalidClientToken',code))
def send(entries,args,runner):
 executable=observer.safe_path(args.aws_cli)
 require(executable.is_file() and args.aws and args.ec2_role,'EXPLICIT_EC2_PUBLISH_GATE_REQUIRED')
 env={k:os.environ[k] for k in ('PATH','SystemRoot','WINDIR','LANG','LC_ALL') if k in os.environ}
 env.update(AWS_EC2_METADATA_V1_DISABLED='true',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,AWS_MAX_ATTEMPTS='1',AWS_PAGER='')
 try:
  response=runner([str(executable),'events','put-events','--region',args.region,'--entries',encode(entries),'--output','json','--cli-connect-timeout','5','--cli-read-timeout','10'],capture_output=True,env=env)
 except (OSError,subprocess.TimeoutExpired):return None
 if response.returncode!=0:
  if re.search(rb'\((?:AccessDenied[^)]*|Unauthorized[^)]*|NotAuthorized[^)]*|UnrecognizedClientException|InvalidClientTokenId)\)',response.stderr or b''):return ['BLOCKED']*len(entries)
  return None
 try:
  value=bridge.read_unique(response.stdout.decode('utf-8') if isinstance(response.stdout,bytes) else response.stdout)
  require(set(value)=={'FailedEntryCount','Entries'} and type(value['FailedEntryCount']) is int and len(value['Entries'])==len(entries),'PUT_RESPONSE_SHAPE')
  outcomes=[];failed=0
  for row in value['Entries']:
   if set(row)=={'EventId'} and isinstance(row['EventId'],str) and re.fullmatch('[A-Za-z0-9-]{1,128}',row['EventId']):outcomes.append(row['EventId']);continue
   require(set(row)<= {'ErrorCode','ErrorMessage'} and isinstance(row.get('ErrorCode'),str) and re.fullmatch('[A-Za-z0-9]{1,128}',row['ErrorCode']) is not None,'PUT_ENTRY_RESULT')
   failed+=1;code=row['ErrorCode'];outcomes.append('BLOCKED' if denied(code) or code in ('MalformedDetail','MalformedDetailException','InvalidArgument','InvalidArgumentException') else None)
  require(failed==value['FailedEntryCount'],'PUT_FAILED_COUNT_MISMATCH');return outcomes
 except (ValueError,KeyError,TypeError,UnicodeError,AttributeError):return None

def run(args,config,manifest,runner=subprocess.run,clock=lambda:dt.datetime.now(dt.timezone.utc),observe=None):
 """Old pending entries always precede collection. EventBridge itself does not promise order."""
 require(args.action=='run' and args.aws and args.ec2_role and getattr(args,'portable',False) is True,'EXPLICIT_PORTABLE_OPT_IN_REQUIRED')
 require(args.account==manifest['account'] and args.region==manifest['region'],'EXACT_ACCOUNT_REGION_REQUIRED')
 require(clock()<signals.utc(args.expires_at),'PUBLISH_WINDOW_EXPIRED')
 binding=scope(config,manifest,args.subject,args.expires_at)
 backup=observer.safe_path(args.config);raw=backup.read_bytes();require(len(raw)<=65536,'CONFIG_TOO_LARGE')
 binding=digest([binding,hashlib.sha256(raw).hexdigest()])
 root=observer.safe_path(args.state_directory);root.mkdir(mode=0o700,exist_ok=True)
 if os.name=='posix':require(not stat.S_IMODE(root.stat().st_mode)&0o077,'PRIVATE_STATE_DIRECTORY_REQUIRED')
 with observer.owner(root/'portable-delivery') as directory:
  path=directory/'journal.json';j=journal(path,binding,config,manifest)
  pending=[e for e in j['Entries'] if e['Status']!='ACCEPTED']
  require(not any(e['Status']=='BLOCKED' for e in pending),'PUBLISH_BLOCKED_REQUIRES_REVIEW')
  require(not any(e['Attempts']>=3 for e in pending),'PER_ENTRY_ATTEMPTS_EXHAUSTED')
  # Refuse even a new collection once the global cap has been spent.
  require(sum(e['Attempts'] for e in j['Entries'])<20,'TOTAL_ENTRY_ATTEMPTS_EXHAUSTED')
  if not pending:
   def stage(state,event):
    entries=bridge.project(encode(event),config,manifest,clock().isoformat(),'check-result')
    for entry in entries:
     ident=validate_entry(entry,config,manifest);old=next((e for e in j['Entries'] if e['Id']==ident),None)
     if old is not None:require(old['Sha256']==digest(entry),'REPORT_ID_COLLISION');continue
     require(len(j['Entries'])<20,'TOTAL_JOURNAL_BOUND');j['Entries'].append({'Entry':entry,'Sha256':digest(entry),'Id':ident,'Attempts':0,'Status':'PENDING','EventId':None})
    if entries:commit(path,j)
   if observe is None:observer.run(args,runner=runner,clock=clock,before_state_save=stage)
   else:stage(None,observe()) # Explicit local collector port for tests; never selected by CLI.
   pending=[e for e in j['Entries'] if e['Status']!='ACCEPTED']
  if not pending:return {'Status':'NO_PENDING','Acceptance':'NONE','CloudHealthProven':False}
  remaining=20-sum(e['Attempts'] for e in j['Entries']);batch=pending[:remaining]
  # One journal update debits global/per-entry attempts before any transport, including crash/unknown.
  for e in batch:e['Attempts']+=1
  commit(path,j)
  outcomes=send([e['Entry'] for e in batch],args,runner)
  if outcomes is not None:
   for e,outcome in zip(batch,outcomes):
    if outcome=='BLOCKED':e['Status']='BLOCKED'
    elif outcome is not None:e['Status']='ACCEPTED';e['EventId']=outcome
   commit(path,j)
  accepted=sum(e['Status']=='ACCEPTED' for e in j['Entries']);pending=[e for e in j['Entries'] if e['Status']!='ACCEPTED']
  return {'Status':'BLOCKED' if any(e['Status']=='BLOCKED' for e in pending) else 'PENDING' if pending else 'ACCEPTED','Attempts':sum(e['Attempts'] for e in j['Entries']),'AcceptedEntries':accepted,'PendingEntries':len(pending),'Acceptance':'EVENTBRIDGE_ONLY_NOT_SENTINEL_OR_EMAIL','MayDuplicateOnRetry':outcomes is None,'CloudHealthProven':False}
