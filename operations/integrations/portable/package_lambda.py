"""Package a reviewed publish directory and exact synthetic config. No publish, SDK install or AWS."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--published',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();R=Path(__file__).resolve().parents[3]
commit=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain']).strip(),'Commit reviewed sources before packaging'
assert not a.output.exists();P=a.published;assert (P/'Ecs.Backup.Portable.Host.dll').is_file();assert not (P/'ecs-package-manifest.json').exists(),'Use a fresh publish directory; preserve previous artifacts'
raw=a.config.read_bytes();config=json.loads(raw);assert config['account']=='341936017254' and config['region']=='us-east-1' and len(config['monitors'])==2
sha=lambda b:hashlib.sha256(b).hexdigest();(P/'sentinel.json').write_bytes(raw)
(P/'ecs-portable.json').write_text(json.dumps({'schemaVersion':1,'upstreamCommit':'b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828','syntheticTrial':True,'configSha256':sha(raw)},indent=2)+'\n',encoding='utf-8')
files={}
for f in sorted(P.iterdir()):
 assert f.is_file() and not f.is_symlink() and f.suffix in ('.dll','.json'),f
 files[f.name]={'sha256':sha(f.read_bytes()),'bytes':f.stat().st_size}
manifest={'schemaVersion':1,'sourceCommit':commit,'upstreamCommit':'b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828','runtime':'dotnet10','distribution':'FRAMEWORK_DEPENDENT_MANAGED','runtimeFactory':'Ecs.Backup.Portable.Host::Ecs.Backup.Portable.Host.Function','configSha256':sha(raw),'syntheticTrial':True,'noticeAttempts':3,'publisherContract':{'transport':'EVENTBRIDGE_REPORT_V1','entryAttempts':20,'perPendingEntryAttempts':3,'copyOnlyPolicy':'FULL_COPY_ONLY_CHECKSUM','includedInLambda':False,'location':'SQL host publisher source-qualified separately; legacy cohost tar unchanged'},'files':files,'executionAuthorized':False}
(P/'ecs-package-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in sorted(P.iterdir()):
  i=zipfile.ZipInfo(f.name,date_time=(2026,1,1,0,0,0));i.external_attr=0o100644<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,f.read_bytes())
receipt={k:manifest[k] for k in ('schemaVersion','sourceCommit','upstreamCommit','runtime','runtimeFactory','configSha256','syntheticTrial','executionAuthorized')};receipt.update(zipSha256=sha(a.output.read_bytes()),zipBytes=a.output.stat().st_size,path=a.output.name,payloadFiles=len(files)+1,includedSqlHostPublisher=False,noticeAttempts=3)
a.output.with_suffix('.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
