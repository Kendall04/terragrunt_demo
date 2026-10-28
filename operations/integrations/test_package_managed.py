"""Package boundary tests with synthetic bytes only; no build, git mutation or network."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import package_managed as package

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.pub=self.root/'publish';self.pub.mkdir();self.stage=self.root/'stage';self.stage.mkdir()
        self.repo=self.root/'repo';(self.repo/'operations/integrations/Ecs.Backup.Managed').mkdir(parents=True)
        (self.repo/'operations/integrations/Ecs.Backup.Managed/packages.lock.json').write_text('{}')
        self.commit='a'*40;self.output=self.root/'result.zip'
        self.receipt={'originalFiles':{},'patchedFile':'unused.cs','patchedSha256':'b'*64,'upstreamCommit':'c'*40,'extensionSha256':'d'*64}
        (self.stage/'ecs-source-receipt.json').write_text(json.dumps(self.receipt))
        for name,data in {'Ecs.Backup.Managed.dll':b'OFFLINE_SYNTHETIC_TEST_BYTES','Ecs.Backup.Managed.deps.json':b'{}','Ecs.Backup.Managed.runtimeconfig.json':b'{}'}.items():(self.pub/name).write_bytes(data)
    def tearDown(self):self.temp.cleanup()
    def run_package(self):
        args=['package','--publish',str(self.pub),'--staged-source',str(self.stage),'--repo',str(self.repo),'--source-commit',self.commit,'--output',str(self.output)]
        with patch.object(sys,'argv',args),patch.object(package.subprocess,'check_output',return_value=self.commit),contextlib.redirect_stdout(io.StringIO()):package.main()
    def test_output_allowlist_and_v3_metadata(self):
        self.run_package();m=json.loads(self.output.with_suffix('.manifest.json').read_text())
        self.assertEqual(m['zipSha256'],hashlib.sha256(self.output.read_bytes()).hexdigest());self.assertFalse(m['uploaded'])
        self.assertEqual(m['integrationContractVersion'],'ecs-backup-managed-v3');self.assertIn('observer-check',m['supportedModes'])
        with zipfile.ZipFile(self.output) as z:self.assertEqual(set(z.namelist()),{'Ecs.Backup.Managed.dll','Ecs.Backup.Managed.deps.json','Ecs.Backup.Managed.runtimeconfig.json','ecs-managed-build.json'})
    def test_main_pdb_still_rejected(self):
        (self.pub/'Ecs.Backup.Managed.pdb').write_bytes(b'private debug')
        with self.assertRaisesRegex(SystemExit,'UNINTENDED_PUBLISH_FILE'):self.run_package()
        self.assertFalse(self.output.exists())
    def test_transitive_pdb_still_rejected(self):
        (self.pub/'Sentinel.Core.pdb').write_bytes(b'private debug')
        with self.assertRaisesRegex(SystemExit,'UNINTENDED_PUBLISH_FILE'):self.run_package()
        self.assertFalse(self.output.exists())
    def test_unrelated_binary_rejected(self):
        (self.pub/'Unknown.dll').write_bytes(b'unknown')
        with self.assertRaisesRegex(SystemExit,'UNINTENDED_PUBLISH_FILE'):self.run_package()
    def test_missing_entry_rejected(self):
        (self.pub/'Ecs.Backup.Managed.runtimeconfig.json').unlink()
        with self.assertRaisesRegex(SystemExit,'MISSING_LAMBDA_ENTRY_FILES'):self.run_package()
    def test_staged_source_hash_mismatch_rejected(self):
        (self.stage/'source.cs').write_text('changed');self.receipt['originalFiles']={'source.cs':'0'*64};(self.stage/'ecs-source-receipt.json').write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(SystemExit,'STAGED_SOURCE_CHANGED'):self.run_package()
    def test_wrong_commit_rejected(self):
        with patch.object(package.subprocess,'check_output',return_value='e'*40),patch.object(sys,'argv',['package','--publish',str(self.pub),'--staged-source',str(self.stage),'--repo',str(self.repo),'--source-commit',self.commit,'--output',str(self.output)]):
            with self.assertRaisesRegex(SystemExit,'SOURCE_COMMIT_MISMATCH'):package.main()

if __name__=='__main__':unittest.main()
