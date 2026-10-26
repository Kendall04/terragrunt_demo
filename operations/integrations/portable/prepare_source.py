"""Stage reviewed source-only CLR slice from exact Git objects. No fetch, build or scripts."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
pin=json.loads((Path(__file__).parent/'upstream.json').read_text(encoding='utf-8'))
def git(*args):return subprocess.check_output(['git','-C',str(a.source),*args])
assert git('remote','get-url','origin').decode().strip()==pin['origin']
assert git('rev-parse','HEAD').decode().strip()==pin['commit'] and not git('status','--porcelain','--untracked-files=no').strip()
projects={'Sentinel.Core','Sentinel.Application','Sentinel.Ingestion','Sentinel.Observability','Sentinel.Operations','Sentinel.Portable','Sentinel.Persistence.Fakes'}
paths=git('ls-tree','-r','--name-only',pin['commit']).decode().splitlines()
selected=[n for n in paths if n=='Directory.Build.props' or (len(Path(n).parts)>2 and Path(n).parts[:1]==('src',) and Path(n).parts[1] in projects and (n.endswith(('.cs','.csproj')) or n.endswith('/packages.lock.json')))]
assert not a.output.exists(),'OUTPUT_MUST_BE_NEW';a.output.mkdir(parents=True);inventory={}
for n in selected:
 raw=git('show',pin['commit']+':'+n);dest=a.output/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);inventory[n]=hashlib.sha256(raw).hexdigest()
receipt={**pin,'sourceFiles':inventory,'omitted':'upstream global.json; consumer builds under existing ECS SDK10.0.402, without changing upstream or machine pins','dependencySlice':'CORE_ONLY_NO_PACKAGE_REFERENCES_OR_AWS_ADAPTERS','awsCalls':0,'scriptsExecuted':False}
(a.output/'ecs-portable-source-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({'files':len(inventory),'commit':pin['commit'],'prepared':str(a.output)}))
