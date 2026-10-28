"""Extract exact BCL enum/record for formatting tests. Does not build/replace an SNS SDK."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=Path(__file__).parent;pin=json.loads((base/'upstream.json').read_text());extension=json.loads((base/'notice-extension.json').read_text())
def git(*args):return subprocess.check_output(['git','-C',str(a.source),*args])
assert git('remote','get-url','origin').decode().strip()==pin['origin'] and git('rev-parse','HEAD').decode().strip()==pin['commit'] and not git('status','--porcelain','--untracked-files=no').strip()
raw=git('show',pin['commit']+':'+extension['file']);assert hashlib.sha256(raw).hexdigest()==extension['baseSha256'];source=raw.decode()
for replacement in extension['replacements']:assert source.count(replacement['before'])==1
body='using Sentinel.Core;\nnamespace Sentinel.Portable.Aws;\n'+source[source.index('public enum NoticeCondition'):source.index('public sealed class Notifications')]
assert not a.output.exists();a.output.mkdir(parents=True);(a.output/'IncidentNoticeContract.cs').write_text(body,encoding='utf-8',newline='\n')
(a.output/'receipt.json').write_text(json.dumps({'upstreamCommit':pin['commit'],'notificationSourceSha256':extension['baseSha256'],'contractSha256':hashlib.sha256(body.encode()).hexdigest(),'fullSnsImplementationExecuted':False,'sdkUsed':False,'extensionContextCount':len(extension['replacements'])},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'contractExtracted':True,'sdkUsed':False,'awsCalls':0}))
