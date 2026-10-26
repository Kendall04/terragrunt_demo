"""Prepare exact upstream CLR source plus two explicit consumer extensions; no fetch/build."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();base=Path(__file__).parent
pin=json.loads((base/'upstream.json').read_text());git=lambda *v:subprocess.check_output(['git','-C',str(a.source),*v])
assert git('rev-parse','HEAD').decode().strip()==pin['commit'] and git('remote','get-url','origin').decode().strip()==pin['origin'] and not git('status','--porcelain').strip()
assert not a.output.exists();a.output.mkdir(parents=True);files={};changes={}
for name in git('ls-tree','-r','--name-only',pin['commit']).decode().splitlines():
 if name=='Directory.Build.props' or name.startswith('src/') and (name.endswith(('.cs','.csproj')) or name.endswith('/packages.lock.json')):
  raw=git('show',pin['commit']+':'+name);dest=a.output/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=hashlib.sha256(raw).hexdigest()
for name in ['notice-extension.json','runtime-extension.json']:
 patch=json.loads((base/name).read_text());assert patch['upstreamCommit']==pin['commit'];dest=a.output/patch['file'];raw=dest.read_bytes();assert hashlib.sha256(raw).hexdigest()==patch['baseSha256'];text=raw.decode()
 for replacement in patch['replacements']:assert text.count(replacement['before'])==1;text=text.replace(replacement['before'],replacement['after'])
 dest.write_text(text,encoding='utf-8',newline='\n');changes[patch['file']]=hashlib.sha256(dest.read_bytes()).hexdigest()
(a.output/'ecs-portable-runtime-receipt.json').write_text(json.dumps({'upstreamCommit':pin['commit'],'originalFiles':files,'extendedFiles':changes,'consumerSdk':pin['consumerSdk'],'upstreamGlobalJsonOmittedNotModified':True,'awsCalls':0},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sourceFiles':len(files),'extensions':len(changes),'awsCalls':0}))
