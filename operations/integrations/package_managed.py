"""Create one small deterministic local Lambda ZIP from an allowlisted publish output. Never uploads."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path

def digest(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--publish',type=Path,required=True);p.add_argument('--staged-source',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--source-commit',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 actual=subprocess.check_output(['git','-C',str(a.repo),'rev-parse','HEAD'],text=True).strip()
 if actual!=a.source_commit:raise SystemExit('SOURCE_COMMIT_MISMATCH')
 if a.output.exists() or a.output.with_suffix('.manifest.json').exists():raise SystemExit('OUTPUT_MUST_BE_NEW')
 receipt=json.loads((a.staged_source/'ecs-source-receipt.json').read_text(encoding='utf-8'))
 for name,expected in receipt['originalFiles'].items():
  expected=receipt['patchedSha256'] if name==receipt['patchedFile'] else expected
  if digest((a.staged_source/name).read_bytes())!=expected:raise SystemExit('STAGED_SOURCE_CHANGED: '+name)
 files=sorted(x for x in a.publish.iterdir() if x.is_file());payload={}
 allowed=re.compile(r'(?:Ecs\.Backup\.(?:Managed|Sentinel)|Sentinel\.[A-Za-z0-9.]+|AWSSDK\.[A-Za-z0-9.]+|Amazon\.Lambda\.[A-Za-z0-9.]+)\.dll$|Ecs\.Backup\.Managed\.(?:deps|runtimeconfig)\.json$')
 for path in files:
  if not allowed.fullmatch(path.name):raise SystemExit('UNINTENDED_PUBLISH_FILE: '+path.name)
  data=path.read_bytes()
  if re.search(rb'(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])',data):raise SystemExit('ACCESS_KEY_PATTERN: '+path.name)
  for encoding in ['utf-8','utf-16-le']:
   text=data.decode(encoding,errors='ignore')
   if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{40,}',text):raise SystemExit('PRIVATE_KEY_PATTERN: '+path.name)
  if path.suffix=='.json':
   def walk(x):
    if isinstance(x,dict):
     for k,v in x.items():
      if k.casefold() in {'password','secretaccesskey','aws_access_key_id','aws_secret_access_key','access_token','client_secret','privatekey'} and v:raise SystemExit('CREDENTIAL_JSON_FIELD')
      walk(v)
    elif isinstance(x,list):
     for v in x:walk(v)
   walk(json.loads(data))
  payload[path.name]=data
 if not {'Ecs.Backup.Managed.dll','Ecs.Backup.Managed.deps.json','Ecs.Backup.Managed.runtimeconfig.json'}<=payload.keys():raise SystemExit('MISSING_LAMBDA_ENTRY_FILES')
 lock=a.repo/'operations/integrations/Ecs.Backup.Managed/packages.lock.json'
 metadata={'integrationContractVersion':'ecs-backup-managed-v3','capabilities':['durable-cursor-v1','observer-watchdog-v1'],'supportedModes':['synthetic-trial','observer-check'],'dispatchHandlers':['Handler','Reconcile'],'schemaVersion':1,'sourceCommit':actual,'upstreamCommit':receipt['upstreamCommit'],'sourceExtensionSha256':receipt['extensionSha256'],
  'managedLockSha256':digest(lock.read_bytes().replace(b'\r\n',b'\n')),'entries':{k:{'sha256':digest(v),'bytes':len(v)} for k,v in payload.items()},
  'runtime':'framework-dependent .NET10; no native Lambda execution claimed','handlerAssembly':'Ecs.Backup.Managed','awsCalls':0,'secretsScan':'publish allowlist + credential-shaped patterns, no findings; not a universal secret detector'}
 payload['ecs-managed-build.json']=(json.dumps(metadata,indent=2)+'\n').encode()
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(payload.items()):
   info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.create_system=3;info.external_attr=0o644<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data,compresslevel=9)
 if a.output.stat().st_size>20*1024*1024:raise SystemExit('PACKAGE_SIZE_EXCEEDS_SMALL_TRIAL_LIMIT')
 manifest={**metadata,'zipSha256':digest(a.output.read_bytes()),'zipBytes':a.output.stat().st_size,'zipMembers':len(payload),'cloudObjectKey':'packages/'+digest(a.output.read_bytes())+'.zip','uploaded':False}
 a.output.with_suffix('.manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode());print(json.dumps({k:manifest[k] for k in ['zipSha256','zipBytes','zipMembers','cloudObjectKey','uploaded']}))
if __name__=='__main__':main()
