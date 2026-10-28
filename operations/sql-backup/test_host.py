"""Isolated process/package fixtures. No AWS, host service manager or real credentials."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sql_backup_package',BASE/'package.py'); package=importlib.util.module_from_spec(spec); spec.loader.exec_module(package)

class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sql-backup-host-'); self.root=Path(self.temp.name)
        self.staging=self.root/'staging'; self.credentials=self.root/'credentials'; self.credentials.mkdir(mode=0o700)
        for name in ('backup-connection','verify-connection'):
            path=self.credentials/name; path.write_text('SECRET-SENTINEL'); path.chmod(0o400)
        self.config=self.root/'config.json'; self.value={'Database':'DemoDb','Bucket':'synthetic-fixture','Prefix':'terragrunt-demo/dev/sql-backups/fixture','StagingDirectory':str(self.staging),'RestoreDirectory':str(self.root/'restores'),'ExpectedEc2RoleName':'fixture-role','TimeoutSeconds':10}
        self.config.write_text(json.dumps(self.value)); self.trace=self.root/'trace.jsonl'
        self.exe=self.root/'SqlBackup'; self.exe.write_text('''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
action=sys.argv[1]
with open(os.environ['FAKE_TRACE'],'a') as f: f.write(json.dumps({'action':action,'sql_env':'SQL_BACKUP_CONNECTION_STRING' in os.environ,'time':time.monotonic()})+'\\n')
if action=='backup':
 Path(os.environ['ENTERED']).touch()
 if os.environ.get('MODE')=='wait':
  while not Path(os.environ['RELEASE']).exists(): time.sleep(.02)
 if os.environ.get('MODE') in ('failure','sql-not-ready','no-space'):
  print('SECRET-SENTINEL',file=sys.stderr); print('SECRET-SENTINEL'); sys.exit(7)
 print(json.dumps({'Status':'REMOTE_VERIFIED'}))
else: print(json.dumps({'Status':'LOCAL_CLEANUP_VERIFIED'}))
'''); self.exe.chmod(0o755)
        self.env=dict(os.environ,CREDENTIALS_DIRECTORY=str(self.credentials),FAKE_TRACE=str(self.trace),ENTERED=str(self.root/'entered'),RELEASE=str(self.root/'release'))
    def tearDown(self): self.temp.cleanup()
    def command(self,action,extra=()): return [sys.executable,str(BASE/'host.py'),action,'--config',str(self.config),'--executable',str(self.exe),*extra]
    def call(self,action,mode='success',extra=()): return subprocess.run(self.command(action,extra),capture_output=True,text=True,env=dict(self.env,MODE=mode),timeout=15)
    def records(self): return [json.loads(x) for x in self.trace.read_text().splitlines()]

    def test_two_accelerated_activations_and_transient_sql_credentials(self):
        for _ in range(2):
            result=self.call('run'); self.assertEqual(0,result.returncode,result.stderr); time.sleep(.1)
        self.assertEqual(['backup','cleanup','backup','cleanup'],[x['action'] for x in self.records()])
        self.assertEqual([True,False,True,False],[x['sql_env'] for x in self.records()])
        self.assertNotIn('SECRET-SENTINEL',(self.staging/'.service/last-job.json').read_text())
        self.assertEqual(0o700,(self.staging/'.service').stat().st_mode&0o777)
        self.assertEqual(0o600,(self.staging/'.service/last-job.json').stat().st_mode&0o777)

    def test_concurrency_inhibition_wait_and_explicit_resume(self):
        running=subprocess.Popen(self.command('run'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(self.env,MODE='wait'))
        try:
            for _ in range(100):
                if (self.root/'entered').exists(): break
                time.sleep(.02)
            else: self.fail('fixture did not enter')
            other=self.call('run'); self.assertNotEqual(0,other.returncode); self.assertIn('JOB_ACTIVE',other.stderr)
            inhibited=self.call('inhibit',extra=('--wait-seconds','0')); self.assertNotEqual(0,inhibited.returncode)
            self.assertTrue((self.staging/'.service/inhibited.json').exists())
            (self.root/'release').touch(); out,err=running.communicate(timeout=10); self.assertEqual(0,running.returncode,err)
            self.assertEqual(0,self.call('inhibit').returncode)
            blocked=self.call('run'); self.assertIn('BACKUP_INHIBITED',blocked.stderr)
            self.assertEqual(0,self.call('resume').returncode); self.assertEqual(0,self.call('run').returncode)
        finally:
            (self.root/'release').touch()
            if running.poll() is None: running.communicate(timeout=10)

    def test_failure_startup_without_sql_and_no_space_never_cleanup_or_echo_secrets(self):
        for mode in ('failure','sql-not-ready','no-space'):
            result=self.call('run',mode); self.assertNotEqual(0,result.returncode)
            self.assertNotIn('SECRET-SENTINEL',result.stdout+result.stderr)
        self.assertEqual(['backup']*3,[x['action'] for x in self.records()])

    def test_permissions_and_symlink_rejection(self):
        path=self.credentials/'backup-connection'; path.chmod(0o644)
        self.assertIn('PRIVATE_CREDENTIAL_FILE_REQUIRED',self.call('run').stderr)
        path.chmod(0o400); self.exe.chmod(0o777)
        self.assertIn('WRITABLE_EXECUTABLE_DENIED',self.call('run').stderr)
        self.exe.chmod(0o755)
        # No data is moved/deleted through the link.
        outside=self.root/'outside'; outside.mkdir(mode=0o700); self.staging.rmdir() if self.staging.exists() and not list(self.staging.iterdir()) else None
        linked=self.root/'linked'; linked.symlink_to(outside,target_is_directory=True)
        self.value['StagingDirectory']=str(linked); self.config.write_text(json.dumps(self.value))
        self.assertIn('SYMLINK_DENIED',self.call('run').stderr)
    def test_deadline_or_interrupted_job_requires_explicit_resume(self):
        module_spec=importlib.util.spec_from_file_location('sql_backup_host',BASE/'host.py'); host=importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(host)
        with mock.patch.object(sys,'argv',self.command('run')[1:]),mock.patch.dict(os.environ,self.env),mock.patch.object(host.subprocess,'run',side_effect=subprocess.TimeoutExpired('fixture',10)):
            with self.assertRaisesRegex(host.Refused,'CLIENT_DEADLINE'): host.main()
        self.assertEqual('UNKNOWN',json.loads((self.staging/'.service/last-job.json').read_text())['Status'])
        self.assertIn('PREVIOUS_JOB_REQUIRES_REVIEW',self.call('run').stderr)
        self.assertEqual(0,self.call('resume').returncode); self.assertEqual(0,self.call('run').returncode)

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sql-backup-package-'); self.root=Path(self.temp.name); self.publish=self.root/'publish'; self.publish.mkdir()
        for name in package.REQUIRED: (self.publish/name).write_bytes(b'isolated-package-fixture')
        (self.publish/'SqlBackup.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'includedFrameworks':[{'name':'Microsoft.NETCore.App','version':'10.0.13'}]}}))
        self.archive=self.root/'package.tar'; result=package.build(self.publish,self.archive,'a'*40); self.sha=result['Sha256']
        self.fixture=self.root/'system'; self.fixture.mkdir()
        self.config=self.root/'config.json'; self.config.write_text(json.dumps({'Database':'DemoDb','Bucket':'synthetic-fixture','Prefix':'fixture/backups','StagingDirectory':'/var/opt/mssql/backup/v2','RestoreDirectory':'/var/opt/mssql/backup/restores','ExpectedEc2RoleName':'fixture-role','BackupKeyArn':'arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000001','TextKeyArn':'arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000002'}))
        self.user=pwd.getpwuid(os.getuid()).pw_name
    def tearDown(self): self.temp.cleanup()
    def install(self,apply=True,root=None): return package.install(self.archive,self.sha,self.config,root or self.fixture,self.user,apply,None)
    def test_deterministic_package_plan_inert_install_and_idempotence(self):
        second=self.root/'same.tar'; self.assertEqual(self.sha,package.build(self.publish,second,'a'*40)['Sha256'])
        self.assertEqual('INSTALL_PLAN',self.install(False)['Status']); self.assertFalse((self.fixture/'opt').exists())
        self.assertEqual('STAGED_NOT_ENABLED',self.install()['Status']); self.assertEqual('ALREADY_INSTALLED',self.install()['Status'])
        self.assertFalse((self.fixture/'etc/systemd/system/timers.target.wants').exists())
        self.assertFalse((self.fixture/'run/sql-backup-credentials').exists())
        self.assertEqual(0o700,(self.fixture/'var/opt/mssql/backup/v2').stat().st_mode&0o777)
        self.assertEqual(0o640,(self.fixture/'etc/terragrunt-demo/sql-backup/config.json').stat().st_mode&0o777)
    def binary_publication(self):
        import local_release
        (self.publish/'SqlBackup.pdb').write_bytes(b'SYNTHETIC_SYMBOL_ONLY')
        original={'SchemaVersion':1,'Component':'SqlBackup','SourceCommit':'b'*40,'Runtime':'10.0.13','Rid':'linux-x64','SelfContained':True,'BuildIdentity':{'Component':'SqlBackup','SourceCommit':'b'*40,'InformationalVersion':'1.0.0+'+'b'*40},'Files':local_release.inventory(self.publish),'DeploymentAuthorized':False,'Uploaded':False}
        raw=json.dumps(original,sort_keys=True).encode();(self.publish/'local-component-manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    def test_distinct_binary_lineage_and_symbols_are_bound_without_claiming_new_compile(self):
        sha=self.binary_publication();archive=self.root/'cohost-binary.tar'
        result=package.build(self.publish,archive,'a'*40,True,sha,'b'*40)
        manifest,files=package.inspect(archive,result['Sha256'])
        self.assertEqual((manifest['SourceCommit'],manifest['BinaryComponent']['SourceCommit']),('a'*40,'b'*40))
        self.assertEqual(manifest['BinaryComponent']['ExcludedSymbols'],['SqlBackup.pdb'])
        self.assertNotIn('bin/SqlBackup.pdb',files);self.assertIn('cohost.py',files)
    def test_wrong_binary_manifest_or_source_refuses_before_output(self):
        sha=self.binary_publication()
        for expected,commit in [('0'*64,'b'*40),(sha,'c'*40)]:
            archive=self.root/'refused.tar'
            with self.assertRaises(ValueError):package.build(self.publish,archive,'a'*40,True,expected,commit)
            self.assertFalse(archive.exists())
    def test_binary_content_drift_refuses_before_output(self):
        sha=self.binary_publication();(self.publish/'SqlBackup').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'COMPONENT_CONTENT_CHANGED'):package.build(self.publish,self.root/'refused.tar','a'*40,True,sha,'b'*40)
        self.assertFalse((self.root/'refused.tar').exists())
    def test_outer_rehash_cannot_substitute_binary_identity(self):
        sha=self.binary_publication();archive=self.root/'bound.tar'
        result=package.build(self.publish,archive,'a'*40,True,sha,'b'*40)
        with tarfile.open(archive,'r:') as t:members={x.name:(t.extractfile(x).read(),x.mode) for x in t}
        manifest=json.loads(members['manifest.json'][0]);manifest['BinaryComponent']['SourceCommit']='c'*40
        members['manifest.json']=(json.dumps(manifest).encode(),0o644)
        changed=self.root/'changed.tar'
        with tarfile.open(changed,'w') as t:
            for name,(raw,mode) in members.items():
                info=tarfile.TarInfo(name);info.size=len(raw);info.mode=mode;t.addfile(info,io.BytesIO(raw))
        with self.assertRaisesRegex(ValueError,'BINARY_COMPONENT_IDENTITY_MISMATCH'):package.inspect(changed,hashlib.sha256(changed.read_bytes()).hexdigest())
    def test_host_install_needs_explicit_confirmation(self):
        with self.assertRaisesRegex(ValueError,'HOST_INSTALL_CONFIRMATION'): self.install(root=Path('/'))
    def test_existing_foreign_staging_is_not_adopted_or_deleted(self):
        target=self.fixture/'var/opt/mssql/backup/v2'; target.mkdir(parents=True); marker=target/'foreign'; marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError,'UNMANAGED_STAGING'): self.install()
        self.assertEqual('preserve',marker.read_text()); self.assertFalse((self.fixture/'opt').exists())
    def test_digest_drift_and_archive_traversal_are_rejected_before_install(self):
        with self.assertRaisesRegex(ValueError,'PACKAGE_HASH'): package.inspect(self.archive,'0'*64)
        with tarfile.open(self.archive,'a') as archive:
            info=tarfile.TarInfo('../escape'); info.size=1; archive.addfile(info,io.BytesIO(b'x'))
        self.sha=hashlib.sha256(self.archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'UNSAFE_PACKAGE'): self.install()
        self.assertFalse((self.root/'escape').exists())
    def test_installed_drift_refuses_overwrite(self):
        self.install(); path=self.fixture/'opt/terragrunt-demo/sql-backup/host.py'; path.write_text('foreign edit')
        with self.assertRaisesRegex(ValueError,'INSTALLED_FILE_DRIFT'): self.install()
        self.assertEqual('foreign edit',path.read_text())
    def test_staging_permission_drift_refuses_idempotent_install(self):
        self.install(); (self.fixture/'var/opt/mssql/backup/v2').chmod(0o777)
        with self.assertRaisesRegex(ValueError,'STAGING_PERMISSION_DRIFT'): self.install()
    def test_unprivileged_service_can_write_only_staging_not_installed_binary(self):
        if os.geteuid()!=0: self.skipTest('root only inside isolated container')
        identity=pwd.getpwnam('nobody'); self.user=identity.pw_name; self.root.chmod(0o755)
        self.install()
        executable=self.fixture/'opt/terragrunt-demo/sql-backup/bin/SqlBackup'
        staging=self.fixture/'var/opt/mssql/backup/v2'
        def drop():
            os.setgroups([]); os.setgid(identity.pw_gid); os.setuid(identity.pw_uid)
        code="from pathlib import Path; import sys; p=Path(sys.argv[1]); failed=False\ntry: p.open('ab')\nexcept PermissionError: failed=True\nassert failed; Path(sys.argv[2],'own-file').write_text('synthetic')"
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(executable),str(staging)],capture_output=True,text=True,preexec_fn=drop)
        self.assertEqual(0,result.returncode,result.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
