"""Determinism and isolated extracted gateway/status execution; no AWS/network."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'scripts/tests/security_root'),str(ROOT/'scripts/internal_release')]
import bundles
import internal

CHILD=r'''
import json,sys,types
from pathlib import Path
package,repo,kind=sys.argv[1:]
root=Path(package);repo=Path(repo)
sys.path[:0]=[str(root/'scripts/internal_release'),str(root/'scripts/build_supervision'),str(root/'scripts/qualification'),str(repo/'scripts/tests/internal_release'),str(repo/'scripts/tests/authority'),str(repo/'scripts/tests/security_root')]
from hermetic import install
install()
import test_adapters as fixtures
import runtime
from e1_contract import canonical
assert Path(runtime.__file__).is_relative_to(root)
import adapters
assert Path(adapters.supervisor.__file__).is_relative_to(root)
assert Path(adapters.finalizer.__file__).is_relative_to(root)
s3=fixtures.S3();cb=fixtures.CodeBuild()
raw=(root/'package.json').read_bytes();package=json.loads(raw)
import hashlib,os
digest=hashlib.sha256(raw).hexdigest();key='bundles/sha256/'+digest+'.json'
version=s3.put_object(Bucket='bundles',Key=key,Body=raw,IfNoneMatch='*')['VersionId']
consumer='release' if kind=='request-gateway' else 'status-neutral'
reference=dict(bucket='bundles',key=key,sha256=digest,version_id=version,consumer=consumer,**{'class':kind})
support=hashlib.sha256(canonical({name:hashlib.sha256((root/'scripts/internal_release'/name).read_bytes()).hexdigest() for name in ('e1_contract.py','exchange.py','publisher.py','workers.py','adapters.py','services.py','runtime.py','worker.py')})).hexdigest()
os.environ['E1_PROTECTED_CONFIGURATION']=json.dumps(dict(binding=kind+'/'+consumer,account=fixtures.ACCOUNT,region=fixtures.REGION,bundle=reference,runtime_image=fixtures.REGISTRY+'/runtime@sha256:'+'a'*64,support_sha256=support,evidence_bucket='protected',exchange_bucket='quarantine'))
boto=types.ModuleType('boto3');boto.client=lambda name,**kw:s3 if name=='s3' else cb
config=types.ModuleType('botocore.config')
class Config:
 def __init__(self,**kw):assert kw==dict(signature_version='s3v4')
config.Config=Config
sys.modules['boto3']=boto;sys.modules['botocore']=types.ModuleType('botocore');sys.modules['botocore.config']=config
if kind=='request-gateway':
 adapters.Store(s3,'protected','source-approvals/demo-api/').create('a'*40+'.json',canonical(dict(source_commit='a'*40,repository='Kendall04/terragrunt_demo')))
 result=runtime.handler({'source_commit':'a'*40},None)
 assert set(result)=={'operation_id'} and cb.calls[0]['projectName']=='e1-controller-release'
else:
 result=runtime.handler({'operation_id':fixtures.OP},None)
 assert result==dict(operation_id=fixtures.OP,state='UNKNOWN') and not cb.calls
print(kind+' extracted execution PASS')
'''


def main():
    doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());catalog=doc['control_bundles']
    results={}
    for kind in catalog['classes']:
        first=bundles.artifact(ROOT,catalog,kind);second=bundles.artifact(ROOT,catalog,kind)
        assert first==second
        bundles.verify_artifact(ROOT,catalog,kind,first)
        results[kind]=bundles.digest(first)
        if kind not in ('request-gateway','status'):continue
        with tempfile.TemporaryDirectory(prefix='wp3c-extracted-') as tmp:
            root=Path(tmp);(root/'package.json').write_bytes(first)
            for name,encoded in json.loads(first)['files'].items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(base64.b64decode(encoded))
            (root/'check.py').write_text(CHILD)
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','BOTO','GITHUB','GH_','TF_','TERRAGRUNT'))}
            result=subprocess.run([sys.executable,'-I','-B',str(root/'check.py'),tmp,str(ROOT),kind],capture_output=True,text=True,env=env,timeout=30)
            assert result.returncode==0,result.stdout+result.stderr
            print(result.stdout.strip())
            changed=root/'scripts/internal_release/services.py'
            changed.write_bytes(changed.read_bytes()+b'\n# disposable source identity mutant\n')
            assert bundles.digest(bundles.artifact(root,catalog,kind))!=results[kind]
    assert results['build']=='ef9ce1edd5331ea6dccebfa4ea9783c40650fd6b075e87c2ce0f3c6553701ec4'
    assert results['qualification-finalizer']=='0e34a5cd928e91694083a46aba1291b1526b7c1c47faaed4fe51a4ea60eb8fae'
    baseline=json.loads(subprocess.check_output(['git','show','fcd492da928e2bb9b2fc715a39f1733a7289e13d:terraform/infra/security/authority.json'],cwd=ROOT))
    for kind,identity in results.items():
        if kind not in ('request-gateway','status'):assert identity==baseline['control_bundles']['classes'][kind]['sha256']
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
