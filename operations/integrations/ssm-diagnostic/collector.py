#!/usr/bin/env python3
"""Bounded, allowlisted SSM evidence. Default invocation never executes AWS."""
import argparse,datetime as dt,hashlib,json,os,re,stat,subprocess,time
from pathlib import Path
BASE=Path('/opt/terragrunt-demo/ssm-diagnostic')
LOGS=('/var/log/amazon/ssm/amazon-ssm-agent.log','/var/log/amazon/ssm/errors.log')
CODES=('AccessDenied','AccessDeniedException','InvalidDocument','InvalidInstanceId','ExpiredToken','UnauthorizedOperation','TargetNotConnected','ThrottlingException','RequestError','RequestCanceled','NoCredentialProviders')
ACTIONS=('GetDocument','DescribeDocument','UpdateInstanceInformation','CreateControlChannel','OpenControlChannel','CreateDataChannel','OpenDataChannel','SendCommand')
UUID=r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
def need(ok,code):
    if not ok:raise ValueError(code)
def now():return dt.datetime.now(dt.timezone.utc)
def environment():
    return {'PATH':'/usr/bin:/bin:/usr/local/bin','LANG':'C.UTF-8','AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null','AWS_EC2_METADATA_V1_DISABLED':'true','AWS_MAX_ATTEMPTS':'1','AWS_PAGER':'','AWS_DEFAULT_REGION':'us-east-1'}
def validate(c):
    need(set(c)=={'run','account','region','expires_at','log_group','role','source_sha256'},'CONFIG_SHAPE')
    need(c['run']=='ecs-sentinel-ssmdiag-r20261024d1' and c['account']=='341936017254' and c['region']=='us-east-1','SCOPE')
    need(c['role']==c['run']+'-node' and c['log_group']=='/ecs/ssm-diagnostic/'+c['run'],'SCOPE')
    need(re.fullmatch('[a-f0-9]{64}',c['source_sha256']) is not None,'SOURCE_HASH')
    end=dt.datetime.fromisoformat(c['expires_at'].replace('Z','+00:00'));need(end.tzinfo is not None,'EXPIRY');return end

def sanitize(data):
    """Never export arbitrary strings, matched payload values or complete input lines."""
    need(isinstance(data,bytes) and len(data)<=65536,'INPUT_BOUND')
    rows=[]
    for line in data.decode('utf-8','replace').splitlines()[-128:]:
        codes=[v for v in CODES if re.search(r'\b'+v+r'\b',line)]
        actions=[v for v in ACTIONS if re.search(r'\b'+v+r'\b',line)]
        if not codes and not actions:continue
        rows.append({'lineSha256':hashlib.sha256(line.encode()).hexdigest(),'codes':codes,'actions':actions,
          'commandIds':sorted(set(re.findall(r'(?i)\bcommand(?:id)?[ =:\[\]"\-]+('+UUID+r')\b',line)))[:4],
          'requestIds':sorted(set(re.findall(r'(?i)\brequest(?:id)?[ =:\[\]"\-]+('+UUID+r')\b',line)))[:4]})
        if len(rows)==32:break
    return rows

def tail(path):
    # Fixed files only; reject symlink parents as well as final entry. No /proc/env.
    need(str(path) in LOGS,'LOG_PATH')
    if any(p.is_symlink() for p in (Path(path),*Path(path).parents)):raise ValueError('SYMLINK')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode),'REGULAR_LOG_REQUIRED')
        os.lseek(fd,max(0,s.st_size-65536),os.SEEK_SET);return os.read(fd,65536)
    finally:os.close(fd)

def validate_record(c,r):
    validate(c)
    keys={'schemaVersion','diagnosticOnly','run','account','region','nodeRole','instanceId','atUtc','sequence','agentService','agentVersion','logs','rawLogsExported','sourceSha256'}
    need(set(r)==keys and r['schemaVersion']==1 and r['diagnosticOnly'] is True and r['rawLogsExported'] is False,'EXPORT_RECORD')
    need(all(r[k]==c[k] for k in ['run','account','region']) and r['nodeRole']==c['role'] and r['sourceSha256']==c['source_sha256'],'EXPORT_SCOPE')
    need(re.fullmatch('i-[a-f0-9]{17}',r['instanceId']) and type(r['sequence']) is int and 0<=r['sequence']<120,'EXPORT_ID')
    need(dt.datetime.fromisoformat(r['atUtc']).tzinfo is not None,'EXPORT_TIME')
    states={'active','inactive','failed','activating','deactivating','running','dead','exited','success','exit-code','timeout','signal','start-limit-hit'}
    need(set(r['agentService'])<={'ActiveState','SubState','Result'} and all(v in states for v in r['agentService'].values()),'EXPORT_SERVICE')
    need(r['agentVersion'] is None or re.fullmatch(r'[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,6}\.[0-9]{1,3}',r['agentVersion']),'EXPORT_VERSION')
    need(len(r['logs'])==2,'EXPORT_LOGS')
    for index,log in enumerate(r['logs']):
        need(set(log)=={'source','status','rows'} and log['source']==index and log['status'] in ['READ','UNAVAILABLE'] and len(log['rows'])<=32,'EXPORT_LOG')
        for row in log['rows']:
            need(set(row)=={'lineSha256','codes','actions','commandIds','requestIds'} and re.fullmatch('[a-f0-9]{64}',row['lineSha256']),'EXPORT_ROW')
            need(set(row['codes'])<=set(CODES) and set(row['actions'])<=set(ACTIONS),'EXPORT_ENUM')
            need(all(len(row[k])<=4 and all(re.fullmatch(UUID,v) for v in row[k]) for k in ['commandIds','requestIds']),'EXPORT_CORRELATION')

class Native:
    def command(self,args):
        return subprocess.run(args,capture_output=True,env=environment(),timeout=20,check=False)
    def logs(self,path):return tail(path)
    def identity(self):
        r=self.command(['/usr/bin/aws','sts','get-caller-identity','--region','us-east-1','--output','json','--cli-connect-timeout','3','--cli-read-timeout','5'])
        need(r.returncode==0 and len(r.stdout)<8192,'IDENTITY_UNCONFIRMED')
        return json.loads(r.stdout)
    def put(self,c,record):
        validate_record(c,record)
        # Only this sanitized record reaches AWS CLI. No response/stderr is exported.
        body={'logGroupName':c['log_group'],'logStreamName':'boot','logEvents':[{'timestamp':int(now().timestamp()*1000),'message':json.dumps(record,sort_keys=True,separators=(',',':'))}]}
        need(len(json.dumps(body).encode())<32768,'EXPORT_BOUND')
        path=BASE/'export.json'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(body,f)
            r=self.command(['/usr/bin/aws','logs','put-log-events','--region',c['region'],'--cli-input-json','file://'+str(path),'--output','json','--cli-connect-timeout','3','--cli-read-timeout','5'])
            need(r.returncode==0 and len(r.stdout)<8192,'EXPORT_UNCONFIRMED_NO_RETRY')
            response=json.loads(r.stdout or b'{}');need(not response.get('rejectedLogEventsInfo') and not response.get('rejectedEntityInfo'),'EXPORT_REJECTED_NO_RETRY')
        finally:path.unlink()

def snapshot(port,c,sequence):
    validate(c);identity=port.identity()
    need(identity.get('Account')==c['account'] and re.fullmatch(re.escape('arn:aws:sts::'+c['account']+':assumed-role/'+c['role']+'/')+'i-[a-f0-9]{17}',identity.get('Arn','')),'NODE_IDENTITY')
    r=port.command(['/usr/bin/systemctl','show','amazon-ssm-agent.service','-p','ActiveState','-p','SubState','-p','Result'])
    fields={}
    if len(r.stdout)<4096:
        for line in r.stdout.decode('utf-8','replace').splitlines():
            key,sep,value=line.partition('=')
            if sep and key in ('ActiveState','SubState','Result') and value in ('active','inactive','failed','activating','deactivating','running','dead','exited','success','exit-code','timeout','signal','start-limit-hit'):fields[key]=value
    version=port.command(['/usr/bin/amazon-ssm-agent','-version'])
    versions=re.findall(r'\b[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,6}\.[0-9]{1,3}\b',version.stdout.decode('utf-8','replace')[:256])
    logs=[]
    for index,path in enumerate(LOGS):
        try:rows=sanitize(port.logs(path));logs.append({'source':index,'status':'READ','rows':rows})
        except (OSError,ValueError):logs.append({'source':index,'status':'UNAVAILABLE','rows':[]})
    return {'schemaVersion':1,'diagnosticOnly':True,'run':c['run'],'account':c['account'],'region':c['region'],'nodeRole':c['role'],
      'instanceId':identity['Arn'].rsplit('/',1)[1],'atUtc':now().isoformat(),'sequence':sequence,'agentService':fields,
      'agentVersion':versions[0] if versions else None,'logs':logs,'rawLogsExported':False,'sourceSha256':c['source_sha256']}

def execute(c,port=None,sleeper=time.sleep,clock=now):
    end=validate(c);need(os.geteuid()==0,'ROOT_REQUIRED');port=port or Native()
    need(clock()<end and end-clock()<=dt.timedelta(hours=24),'EXPIRED_OR_EXCESS_WINDOW')
    need(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==c['source_sha256'],'COLLECTOR_CHANGED')
    r=port.command(['/usr/bin/aws','logs','create-log-stream','--log-group-name',c['log_group'],'--log-stream-name','boot','--region',c['region'],'--cli-connect-timeout','3','--cli-read-timeout','5'])
    need(r.returncode==0,'NEW_STREAM_REQUIRED_NO_RETRY')
    published=0
    for sequence in range(120):
        if clock()>=end:return
        record=snapshot(port,c,sequence)
        published+=len(json.dumps(record).encode())+26
        need(published<=2*1024*1024,"TOTAL_EXPORT_BOUND")
        port.put(c,record)
        if sequence<119:sleeper(60)
    # <=120 events/2h. No command executor, daemon, timer or implicit retry.

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print(json.dumps({'status':'DESIGN_ONLY','awsExecuted':False}));return
    path=BASE/'collector-config.json';need(not path.is_symlink(),'CONFIG_PATH')
    execute(json.loads(path.read_text(encoding='utf-8')))
if __name__=='__main__':main()
