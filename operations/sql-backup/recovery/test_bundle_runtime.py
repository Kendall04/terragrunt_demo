"""Extracted runtime checks in a new isolated Python; no checkout, SDK or AWS."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import bundle

ROOT = Path(__file__).resolve().parents[3]
CHILD = r"""
import sys,json
sys.path.insert(0,sys.argv[1])
def deny(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn'):
        raise AssertionError('PACKAGED_RUNTIME_EXTERNAL_EFFECT_FORBIDDEN')
sys.addaudithook(deny)
import prepare,host
value=json.loads(sys.argv[2])
result=prepare.application_listener_plan(value)
assert result['AllowsActivation'] is False and result['AllowsHostChanges'] is False
assert host.check_api_recovery.__module__=='host'
assert all(not p.startswith(sys.argv[3]) for p in sys.path if p)
print(json.dumps({'Status':'PACKAGED_SERVICE_PLAN_PASS','CloudExecuted':False}))
"""

class PackagedRuntimeTests(unittest.TestCase):
    def archive(self, root):
        for name,exe in (('api','terragrunt-demo'),('backup','SqlBackup')):
            directory=root/name;directory.mkdir()
            (directory/exe).write_bytes(b'ELF-fixture-never-executed')
            (directory/'libcoreclr.so').write_bytes(b'fixture-never-loaded')
            frameworks=[{'name':'Microsoft.NETCore.App','version':'10.0.13'}]
            if name=='api':frameworks.append({'name':'Microsoft.AspNetCore.App','version':'10.0.13'})
            (directory/(exe+'.runtimeconfig.json')).write_text(json.dumps({'runtimeOptions':{'includedFrameworks':frameworks}}))
        archive=root/'runtime.tar'
        result=bundle.build(root/'api',root/'backup',archive,'a'*40)
        return archive,result

    def test_extracted_service_plan_without_checkout_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive,result=self.archive(root)
            manifest=bundle.inspect(archive,result['Sha256'])
            extracted=root/'extracted';extracted.mkdir()
            with tarfile.open(archive) as tar:
                for name in manifest['Files']:
                    path=extracted/name;path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(tar.extractfile(name).read())
            value=json.loads((ROOT/'operations/sql-backup/recovery/fixtures/service-cutover.synthetic.json').read_text())
            env={k:v for k,v in os.environ.items() if k in ('SystemRoot','WINDIR','TEMP','TMP','PATH')}
            env.update(AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,AWS_EC2_METADATA_DISABLED='true')
            result=subprocess.run([sys.executable,'-I','-B','-c',CHILD,str(extracted),json.dumps(value),str(ROOT)],
                                  cwd=root,env=env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['Status'],'PACKAGED_SERVICE_PLAN_PASS')

    def test_current_inspection_rejects_old_source_and_changed_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive,result=self.archive(root)
            manifest=bundle.inspect(archive,result['Sha256'],source_commit='a'*40)
            self.assertEqual(manifest['BundleContract'],'RECOVERY_HOST_WITH_SERVICE_VALIDATORS_V2')
            with self.assertRaisesRegex(ValueError,'BUNDLE_SOURCE_COMMIT_MISMATCH'):
                bundle.inspect(archive,result['Sha256'],source_commit='b'*40)
            # Attacker updates its own internal hash: exact current helper bytes still must match.
            with tarfile.open(archive) as tar:
                bodies={i.name:tar.extractfile(i).read() for i in tar}
            bodies['host.py']+=b'\n# unexpected helper change\n'
            metadata=json.loads(bodies['bundle-manifest.json'])
            metadata['Files']['host.py']['Sha256']=hashlib.sha256(bodies['host.py']).hexdigest()
            bodies['bundle-manifest.json']=(json.dumps(metadata)+'\n').encode()
            changed=root/'changed.tar'
            with tarfile.open(changed,'w') as tar:
                for name,body in bodies.items():
                    item=tarfile.TarInfo(name);item.mode=0o644;item.size=len(body)
                    tar.addfile(item,io.BytesIO(body))
            with self.assertRaisesRegex(ValueError,'BUNDLE_CURRENT_SOURCE_MISMATCH'):
                bundle.inspect(changed,hashlib.sha256(changed.read_bytes()).hexdigest(),source_commit='a'*40)

    def test_missing_support_is_rejected_even_with_a_self_consistent_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive,result=self.archive(root)
            with tarfile.open(archive) as tar:bodies={i.name:tar.extractfile(i).read() for i in tar}
            missing='scripts/qualification/finalizer.py'
            bodies.pop(missing)
            metadata=json.loads(bodies['bundle-manifest.json']);metadata['Files'].pop(missing)
            bodies['bundle-manifest.json']=(json.dumps(metadata)+'\n').encode()
            broken=root/'broken.tar'
            with tarfile.open(broken,'w') as tar:
                for name,body in bodies.items():
                    item=tarfile.TarInfo(name);item.mode=0o644;item.size=len(body)
                    tar.addfile(item,io.BytesIO(body))
            with self.assertRaisesRegex(ValueError,'BUNDLE_CURRENT_SOURCE_MISMATCH'):
                bundle.inspect(broken,hashlib.sha256(broken.read_bytes()).hexdigest(),source_commit='a'*40)

if __name__=='__main__':unittest.main()
