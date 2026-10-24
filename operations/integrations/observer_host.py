#!/usr/bin/env python3
"""Finite observer-only bundle and host control. Build/inspect never contact AWS."""
import argparse
import base64
import datetime as dt
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile

BASE=Path('/opt/terragrunt-demo/observer')
STATE=Path('/var/lib/terragrunt-demo-backup-observer')
MODES={'healthy','missing','stale','fail'}
UNIT='sql-backup-sentinel-producer'
class Refused(ValueError): pass
def need(ok,code):
    if not ok: raise Refused(code)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def safe(path):
    p=Path(path);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'SAFE_PATH_REQUIRED');return p
def environment():
    e={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','SystemRoot') if k in os.environ}
    e.update(AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,AWS_EC2_METADATA_V1_DISABLED='true',AWS_MAX_ATTEMPTS='1',AWS_PAGER='',DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1',DOTNET_CLI_TELEMETRY_OPTOUT='1')
    return e
def build(component,manifest_sha,commit,output):
    component=safe(component);need(sha(component/'local-component-manifest.json')==manifest_sha,'COMPONENT_MANIFEST_HASH')
    m=json.loads((component/'local-component-manifest.json').read_text());need(m['Component']=='SqlBackup' and m['Runtime']=='10.0.13' and m['Rid']=='linux-x64' and m['SelfContained'] and re.fullmatch('[a-f0-9]{40}',commit),'COMPONENT_BINDING')
    actual={p.relative_to(component).as_posix() for p in component.rglob('*') if p.is_file() and p.name!='local-component-manifest.json'}
    need(actual==set(m['Files']),'COMPONENT_INVENTORY')
    files={}
    for name,row in m['Files'].items():
        p=safe(component/name);need(p.is_file() and sha(p)==row['Sha256'] and p.stat().st_size==row['Bytes'],'COMPONENT_CONTENT_CHANGED')
        if not name.endswith('.pdb'):files['checker/'+name]=p
    here=Path(__file__).resolve().parent
    for name in ('observer.py','signals.py','sentinel_publish.py'):files[name]=here.parent/'sql-backup'/name
    files['observer_host.py']=Path(__file__).resolve()
    need(not output.exists() and not output.with_suffix('.manifest.json').exists(),'OUTPUT_MUST_BE_NEW')
    records={n:{'sha256':sha(p),'bytes':p.stat().st_size,'mode':0o755 if n=='checker/SqlBackup' or p.suffix=='.so' else 0o644} for n,p in files.items()}
    need(sum(v['bytes'] for v in records.values())<512*1024*1024 and len(records)<2000,'BUNDLE_BOUND')
    meta={'schemaVersion':1,'contract':'ecs-observer-host-v2','capabilities':['bounded-sqs-attempts-v1'],'sourceCommit':commit,'componentSourceCommit':m['SourceCommit'],'componentManifestSha256':manifest_sha,'runtime':'10.0.13','rid':'linux-x64','excludedSymbols':sorted(n for n in m['Files'] if n.endswith('.pdb')),'files':records,'containsSqlServer':False,'containsCredentials':False,'awsCalls':0}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz,tarfile.open(fileobj=gz,mode='w',format=tarfile.USTAR_FORMAT) as t:
        for name in sorted([*files,'bundle-manifest.json']):
            data=json.dumps(meta,sort_keys=True,separators=(',',':')).encode() if name=='bundle-manifest.json' else None
            row=records.get(name);info=tarfile.TarInfo(name);info.size=len(data) if data is not None else row['bytes'];info.mode=0o644 if row is None else row['mode'];info.mtime=0;info.uid=info.gid=0
            if data is not None:t.addfile(info,io.BytesIO(data))
            else:
                with files[name].open('rb') as body:t.addfile(info,body)
    need(output.stat().st_size<=128*1024*1024,'COMPRESSED_BUNDLE_BOUND')
    result={**meta,'bundleSha256':sha(output),'bundleBytes':output.stat().st_size,'objectKey':'observer-packages/'+sha(output)+'.tar.gz','uploaded':False}
    output.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
def inspect(archive,expected):
    need(re.fullmatch('[a-f0-9]{64}',expected) and sha(archive)==expected,'BUNDLE_HASH')
    with tarfile.open(archive,'r:gz') as t:
        members={};total=0
        for item in t:
            p=PurePosixPath(item.name)
            need(item.isfile() and not p.is_absolute() and '..' not in p.parts and p.as_posix()==item.name and re.fullmatch('[A-Za-z0-9._/-]+',item.name) and item.name not in members,'UNSAFE_MEMBER')
            total+=item.size;need(total<=512*1024*1024 and len(members)<2000,'BUNDLE_BOUND');members[item.name]=item
        need('bundle-manifest.json' in members and members['bundle-manifest.json'].size<1048576,'BUNDLE_MANIFEST')
        m=json.load(t.extractfile(members['bundle-manifest.json']));need(m['contract']=='ecs-observer-host-v2' and set(members)==set(m['files'])|{'bundle-manifest.json'},'BUNDLE_INVENTORY')
        for name,row in m['files'].items():
            item=members[name];need(item.size==row['bytes'] and item.mode==row['mode'] and row['mode'] in (0o644,0o755),'MEMBER_SHAPE')
            h=hashlib.sha256()
            with t.extractfile(item) as f:
                for b in iter(lambda:f.read(1048576),b''):h.update(b)
            need(h.hexdigest()==row['sha256'],'MEMBER_HASH')
        need({'checker/SqlBackup','observer.py','signals.py','sentinel_publish.py','observer_host.py'}<=set(m['files']),'REQUIRED_FILES')
        need(not any(n.endswith('.pdb') for n in m['files']),'SYMBOL_FORBIDDEN')
        return m
def validate(c):
    keys={'account','region','run_id','subject','bucket','prefix','missing_prefix','backup_key_arn','text_key_arn','database','max_age_hours','expires_at','cadence_seconds','publish_attempts'}
    need(set(c)==keys and c['account']=='341936017254' and c['region']=='us-east-1','HOST_SCOPE')
    need(re.fullmatch('ecs-sentinel-[a-z0-9-]{1,24}',c['run_id']) and re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',c['subject']),'HOST_BINDING')
    need(re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',c['bucket']) and '..' not in c['bucket'],'BUCKET')
    for k in ('prefix','missing_prefix'):need(re.fullmatch('[a-z0-9][a-z0-9/_-]{1,120}',c[k]) and '//' not in c[k] and '..' not in c[k],'PREFIX')
    need(c['prefix']!=c['missing_prefix'] and c['missing_prefix'].startswith('sentinel-observer/'+c['run_id']+'/'),'ISOLATED_MISSING_PREFIX')
    for k in ('backup_key_arn','text_key_arn'):need(re.fullmatch('arn:aws:kms:us-east-1:341936017254:key/[a-f0-9-]{36}',c[k]),'EXACT_KMS_METADATA')
    need(re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',c['database']) and c['database'].lower() not in ('master','model','msdb','tempdb'),'DATABASE')
    need(type(c['max_age_hours']) is int and 1<=c['max_age_hours']<=168 and type(c['cadence_seconds']) is int and 60<=c['cadence_seconds']<=3600 and type(c['publish_attempts']) is int and 1<=c['publish_attempts']<=3,'BOUNDS')
    need(c['expires_at'].endswith('Z'),'UTC_EXPIRY');dt.datetime.fromisoformat(c['expires_at'].replace('Z','+00:00'));return c
def options(c,mode):
    validate(c);need(mode in MODES,'MODE');root=STATE/mode/'checker'
    return {'Database':c['database'],'StagingDirectory':root.as_posix(),'RestoreDirectory':(root/'unused-restores').as_posix(),'Bucket':c['bucket'],'Prefix':c['missing_prefix'] if mode=='missing' else c['prefix'],'BackupKeyArn':c['backup_key_arn'],'TextKeyArn':c['text_key_arn'],'ExpectedEc2RoleName':c['run_id']+'-observer','TimeoutSeconds':30,'ProposedMaxAgeHours':1 if mode=='stale' else c['max_age_hours']}
def unit(c):
    validate(c)
    return '\n'.join(['[Unit]','Description=Finite backup observer and SQS publisher','After=network-online.target','Wants=network-online.target','[Service]','Type=oneshot','User=ecs-observer','UMask=0077','NoNewPrivileges=true','ProtectSystem=strict','ProtectHome=true','PrivateTmp=true','StateDirectory=terragrunt-demo-backup-observer','StateDirectoryMode=0700','ExecStart=/usr/bin/python3 -I -B '+(BASE/'observer_host.py').as_posix()+' tick','TimeoutStartSec=90','KillSignal=SIGTERM','SendSIGKILL=no','Restart=no',''])
def timer(c):
    validate(c);return '[Unit]\nDescription=Finite independent backup observation\n[Timer]\nOnBootSec=60\nOnUnitActiveSec='+str(c['cadence_seconds'])+'\nUnit='+UNIT+'.service\n[Install]\nWantedBy=timers.target\n'
def write(path,value,uid=None):
    safe(path);tmp=path.with_name(path.name+'.new');need(not tmp.exists(),'INTERRUPTED_WRITE')
    with tmp.open('x',encoding='utf-8') as f:json.dump(value,f,separators=(',',':'));f.write('\n');f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o600)
    if uid is not None:os.chown(tmp,uid,uid)
    os.replace(tmp,path)
def system(action,target=None):return subprocess.run(['/usr/bin/systemctl',action]+([target] if target else []),capture_output=True,env=environment()).returncode
def service_busy():
    args=['/usr/bin/systemctl','show',UNIT+'.service','-p','ActiveState','-p','MainPID','-p','ControlPID','-p','ControlGroup','-p','TasksCurrent']
    result=subprocess.run(args,capture_output=True,env=environment())
    if result.returncode!=0:return True
    value=dict(line.split('=',1) for line in result.stdout.decode('utf-8').splitlines() if '=' in line)
    return not(value.get('ActiveState') in ('inactive','failed') and value.get('MainPID')=='0' and value.get('ControlPID')=='0' and (value.get('TasksCurrent')=='0' or value.get('ControlGroup')==''))
def install(archive,expected,c):
    import pwd
    validate(c);need(os.geteuid()==0 and not BASE.exists(),'FRESH_ROOT_INSTALL_REQUIRED');m=inspect(archive,expected)
    cli=Path(os.path.realpath(shutil.which('aws') or '/missing'));need(cli.is_file() and str(cli).startswith(('/usr/bin/','/usr/lib/','/usr/local/')),'AMI_AWSCLI_REQUIRED')
    need(subprocess.run([str(cli),'--version'],capture_output=True,env=environment()).returncode==0,'AMI_CLI_UNUSABLE')
    need(system('is-active','amazon-ssm-agent.service')==0,'AMI_SSM_REQUIRED')
    need(subprocess.run(['/usr/sbin/useradd','--system','--user-group','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','ecs-observer'],capture_output=True).returncode==0,'FRESH_OBSERVER_USER_REQUIRED')
    identity=pwd.getpwnam('ecs-observer');BASE.mkdir(parents=True,mode=0o755)
    with tarfile.open(archive,'r:gz') as t:
        for name,row in m['files'].items():
            out=safe(BASE/name);out.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
            with t.extractfile(name) as src,out.open('xb') as dest:shutil.copyfileobj(src,dest,1048576)
            os.chmod(out,row['mode'])
    native=subprocess.run([str(BASE/'checker/SqlBackup'),'build-info'],capture_output=True,env=environment(),timeout=30)
    need(native.returncode==0 and json.loads(native.stdout).get('SourceCommit')==m['componentSourceCommit'],'NATIVE_CHECKER_IDENTITY_UNCONFIRMED')
    STATE.mkdir(mode=0o700,parents=True);os.chown(STATE,identity.pw_uid,identity.pw_gid)
    for mode in sorted(MODES):
        root=STATE/mode;root.mkdir(mode=0o700);(root/'checker').mkdir(mode=0o700)
        for path in (root,root/'checker'):os.chown(path,identity.pw_uid,identity.pw_gid)
        write(BASE/(mode+'.json'),options(c,mode));os.chmod(BASE/(mode+'.json'),0o644)
    write(BASE/'host.json',c|{'aws_cli':str(cli),'uid':identity.pw_uid})
    os.chmod(BASE/'host.json',0o644);write(STATE/'mode.json',{'mode':'healthy'},identity.pw_uid)
    for suffix,body in [('service',unit(c)),('timer',timer(c))]:
        path=Path('/etc/systemd/system')/(UNIT+'.'+suffix);path.write_text(body);os.chmod(path,0o644)
    need(system('daemon-reload')==0,'SYSTEMD_RELOAD')
    result={'status':'INSTALLED_TIMER_INERT','bundleSha256':expected,'sourceCommit':m['sourceCommit'],'componentSourceCommit':m['componentSourceCommit'],'awsCliResolved':str(cli),'credentialsCopied':False,'timerStarted':False}
    write(BASE/'install-receipt.json',result);return result
def host():
    c=json.loads(safe(BASE/'host.json').read_text());extra={k:c.pop(k) for k in ('aws_cli','uid')};validate(c);return c,extra
def consume_send_slot(run_id):
    import sys
    here=Path(__file__).resolve().parent
    sys.path.insert(0,str(here if (here/'observer.py').is_file() else here.parent/'sql-backup'));import observer
    with observer.owner(STATE/'send-budget') as directory:
        path=directory/'budget.json'
        value=json.loads(path.read_text()) if path.exists() else {'SchemaVersion':1,'RunId':run_id,'SlotsConsumed':0,'Maximum':20}
        need(set(value)=={'SchemaVersion','RunId','SlotsConsumed','Maximum'} and value['SchemaVersion']==1 and value['RunId']==run_id and value['Maximum']==20 and type(value['SlotsConsumed']) is int and 0<=value['SlotsConsumed']<=20,'SEND_BUDGET_SCOPE')
        if value['SlotsConsumed']==20:return False
        # Reserve BEFORE the child may send. A crash consumes the slot conservatively.
        observer.save(path,value|{'SlotsConsumed':value['SlotsConsumed']+1});return True
def tick():
    c,extra=host();mode=json.loads(safe(STATE/'mode.json').read_text())['mode'];need(mode in MODES,'MODE')
    if not consume_send_slot(c['run_id']):
        print(json.dumps({'status':'TRIAL_SEND_BUDGET_EXHAUSTED','maximumSqsAttempts':20}));return 2
    return subprocess.run(['/usr/bin/python3','-I','-B',str(BASE/'sentinel_publish.py'),'--config',str(BASE/(mode+'.json')),'--executable',str(BASE/'checker/SqlBackup'),'--aws-cli',extra['aws_cli'],'--state-directory',str(STATE/mode),'--subject',c['subject'],'--expected-up','true','--repeat-after-seconds','0','--account',c['account'],'--region',c['region'],'--run-id',c['run_id'],'--publish-attempts',str(c['publish_attempts']),'--expires-at',c['expires_at'],'--aws','--ec2-role'],env=environment()).returncode
def can_change(active,pending):need(not active and not pending,'ACTIVE_OR_PENDING_DELIVERY_NO_MODE_CHANGE')
def evidence():
    rows=[]
    for mode in sorted(MODES):
        for relative in ['observer-state.json','delivery/pending.json','delivery/last-enqueued.json']:
            path=safe(STATE/mode/relative)
            if path.is_file():
                need(path.stat().st_size<=65536,'EVIDENCE_BOUND')
                body=path.read_bytes();value=json.loads(body)
                rows.append({'mode':mode,'file':relative,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'pending':relative=='delivery/pending.json','attempts':value.get('Attempts') if type(value.get('Attempts')) is int else None})
    budget=safe(STATE/'send-budget/budget.json')
    if budget.is_file():rows.append({'file':'send-budget/budget.json','sha256':sha(budget),'bytes':budget.stat().st_size,'pending':False,'slotsConsumed':json.loads(budget.read_text())['SlotsConsumed']})
    return {'status':'LOCAL_DELIVERY_EVIDENCE_HASHES','files':rows,'payloadExported':False,'drained':False}
def control(action):
    c,extra=host();need(action in MODES|{'status','evidence','start','stop','once'},'ACTION')
    if action=='evidence':return evidence()
    if action=='status':return {'status':'OBSERVED','timerActive':system('is-active',UNIT+'.timer')==0,'serviceActiveOrUncertain':service_busy(),'mode':json.loads((STATE/'mode.json').read_text())['mode'],'timerStartedByTerraform':False}
    need(os.geteuid()==0,'ROOT_CONTROL_REQUIRED')
    need(action=='stop' or dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(c['expires_at'].replace('Z','+00:00')),'EXPIRED')
    if action in ('start','stop','once'):
        need(action!='start' or dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(c['expires_at'].replace('Z','+00:00')),'EXPIRED')
        need(system('start' if action in ('start','once') else 'stop',UNIT+('.service' if action=='once' else '.timer'))==0,'SYSTEMD_ACTION_UNCONFIRMED');return {'status':'SYSTEMD_ACCEPTED_NOT_BACKUP_PROOF','action':action}
    need(system('stop',UNIT+'.timer')==0,'TIMER_STOP_UNCONFIRMED')
    can_change(service_busy(),any((STATE/m/'delivery/pending.json').exists() for m in MODES))
    import sys
    sys.path.insert(0,str(BASE));import observer
    failed=STATE/'fail/checker/last-attempt.json'
    if action=='fail' and not failed.exists():write(failed,{'Id':'0'*32,'Stage':'FAILED','Utc':dt.datetime.now(dt.timezone.utc).isoformat(),'Code':'SYNTHETIC_OBSERVER_TEST'},extra['uid'])
    response=subprocess.run([str(BASE/'checker/SqlBackup'),'check','--config',str(BASE/(action+'.json')),'--expected-up','true','--aws','--ec2-role'],capture_output=True,env=environment())
    observed=dt.datetime.now(dt.timezone.utc).isoformat();health=observer.health(observer.parse_health(response.stdout),observed,response.returncode)
    need(health['Status']=={'healthy':'HEALTHY','missing':'MISSING','stale':'STALE','fail':'FAILED'}[action],'ACTUAL_CHECK_DID_NOT_MATCH_REQUESTED_MODE')
    write(STATE/'mode.json',{'mode':action},extra['uid']);return {'status':'MODE_SELECTED_TIMER_STOPPED','mode':action,'checkStatus':health['Status'],'syntheticAttempt':action=='fail','delivery':'NONE'}
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build');b.add_argument('--component',type=Path,required=True);b.add_argument('--component-manifest-sha',required=True);b.add_argument('--source-commit',required=True);b.add_argument('--output',type=Path,required=True)
    for action in ('inspect','install'):
        a=sub.add_parser(action);a.add_argument('--archive',type=Path,required=True);a.add_argument('--sha256',required=True)
        if action=='install':a.add_argument('--config-base64',required=True)
    sub.add_parser('tick');a=sub.add_parser('control');a.add_argument('--action',dest='control_action',required=True,choices=sorted(MODES|{'status','evidence','start','stop','once'}));a=p.parse_args()
    if a.action=='build':
        repository=Path(__file__).resolve().parents[2]
        actual=subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True).strip()
        need(actual==a.source_commit,'SOURCE_COMMIT_MISMATCH')
        need(subprocess.run(['git','-C',str(repository),'diff','--quiet','HEAD','--','operations/integrations/observer_host.py','operations/sql-backup/observer.py','operations/sql-backup/signals.py','operations/sql-backup/sentinel_publish.py']).returncode==0,'SOURCE_TREE_CHANGED')
        component=json.loads((a.component/'local-component-manifest.json').read_text())
        need(subprocess.run(['git','-C',str(repository),'diff','--quiet',component['SourceCommit'],'HEAD','--','operations/sql-backup/SqlBackup']).returncode==0,'CHECKER_SOURCE_CHANGED_SINCE_QUALIFICATION')
        result=build(a.component,a.component_manifest_sha,a.source_commit,a.output);print(json.dumps({k:result[k] for k in ('bundleSha256','bundleBytes','sourceCommit','componentSourceCommit','uploaded')}))
    elif a.action=='inspect':m=inspect(a.archive,a.sha256);print(json.dumps({'status':'INSPECTED','files':len(m['files']),'sourceCommit':m['sourceCommit']}))
    elif a.action=='install':print(json.dumps(install(a.archive,a.sha256,json.loads(base64.b64decode(a.config_base64,validate=True)))))
    elif a.action=='tick':return tick()
    else:print(json.dumps(control(a.control_action)))
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print(json.dumps({'status':'REFUSED','code':str(e) if isinstance(e,Refused) else 'OBSERVER_HOST_FAILED'}));raise SystemExit(2)
