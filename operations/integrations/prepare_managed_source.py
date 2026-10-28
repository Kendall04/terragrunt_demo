"""Stage pinned tracked Sentinel source + one explicit Lambda ingress extension. No fetch/build."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=Path(__file__).parent
subprocess.run([sys.executable,'-I','-B',str(base/'verify_sources.py'),'--sentinel-root',str(a.source)],check=True)
if a.output.exists():raise SystemExit('OUTPUT_MUST_BE_NEW')
files=subprocess.check_output(['git','-C',str(a.source),'ls-files'],text=True).splitlines()
selected=[x for x in files if x.startswith(('src/','tests/Sentinel.Adapters.Tests/')) or x in ('Directory.Build.props','global.json','NuGet.Config')]
a.output.mkdir(parents=True)
sha=lambda b:hashlib.sha256(b).hexdigest()
original={}
for x in selected:
 data=subprocess.check_output(['git','-C',str(a.source),'show','HEAD:'+x]);dest=a.output/x;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);original[x]=sha(data)
patch=json.loads((base/'managed-source-extension.json').read_text(encoding='utf-8'))
path=a.output/patch['file'];data=path.read_text(encoding='utf-8');assert sha(data.encode())==patch['baseSha256']
for change in patch['replacements']:
 if data.count(change['before'])!=1:raise SystemExit('PATCH_CONTEXT_MISMATCH')
 data=data.replace(change['before'],change['after'])
path.write_bytes(data.encode());receipt={'upstreamCommit':patch['upstreamCommit'],'extensionSha256':sha((base/'managed-source-extension.json').read_bytes()),'patchedFile':patch['file'],'patchedSha256':sha(path.read_bytes()),'originalFiles':original,'networkCalls':0}
(a.output/'ecs-source-receipt.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
print(json.dumps({'stagedFiles':len(selected),'patchedFile':patch['file'],'patchedSha256':receipt['patchedSha256']}))
