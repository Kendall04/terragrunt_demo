"""Offline receipt and component binding regressions, no AWS or delivery."""
from pathlib import Path
import json
import tempfile
import tarfile
import io
import unittest
import signals
import local_release as release

NOW='2026-10-23T08:00:00Z'

class SignalTests(unittest.TestCase):
    def test_existing_health_states_and_nonzero_codes(self):
        for status,code in signals.PAIRS.items():
            value={'Status':status,'Code':code,'LastSuccessUtc':'2026-10-23T04:41:29.5627332+00:00' if status in ('HEALTHY','STALE') else None}
            result=signals.render('health',value,NOW,0 if status in ('HEALTHY','MAINTENANCE') else 1)
            self.assertEqual(result['Code'],code);self.assertEqual(result['Delivery'],'NONE');self.assertFalse(result['SentinelIntegrated']);self.assertFalse(result['RemediationAllowed'])
            if status in ('FAILED','MISSING','STALE'):self.assertEqual(result['Severity'],'ATTENTION')

    def test_unknown_future_wrong_exit_or_private_fields_never_emit_healthy(self):
        cases=[({'Status':'HEALTHY','Code':'RECENT_REMOTE_COMMIT'},0),({'Status':'HEALTHY','Code':'RECENT_REMOTE_COMMIT','LastSuccessUtc':'2026-10-24T00:00:00Z'},0),({'Status':'MISSING','Code':'NO_REMOTE_COMMIT'},0),({'Status':'FAILED','Code':'LAST_ATTEMPT_FAILED','Password':'never-output'},1),({'Status':'OTHER','Code':'arbitrary'},1)]
        for value,exitcode in cases:
            with self.subTest(value=value),self.assertRaises(signals.Refused):signals.render('health',value,NOW,exitcode)

    def test_service_started_unknown_resume_are_not_success(self):
        for status in ('STARTED','UNKNOWN','OPERATOR_RESUMED'):
            self.assertEqual(signals.render('job',{'Status':status,'Utc':1},NOW)['Severity'],'UNKNOWN')
        self.assertEqual(signals.render('job',{'Status':'FAILED_OR_UNCONFIRMED','Utc':1},NOW)['Severity'],'ATTENTION')
        self.assertEqual(signals.render('job',{'Status':'REMOTE_VERIFIED_CLEANUP_VERIFIED','Utc':1},NOW)['Severity'],'OK')

    def test_duplicate_oversize_and_unknown_job_code_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'receipt.json';path.write_text('{"Status":"UNKNOWN","Status":"HEALTHY"}')
            with self.assertRaises(signals.Refused):signals.read(path)
            path.write_bytes(b' '*65537)
            with self.assertRaisesRegex(signals.Refused,'RECEIPT_TOO_LARGE'):signals.read(path)
        with self.assertRaises(signals.Refused):signals.render('job',{'Status':'UNKNOWN','Utc':1,'Code':'private message'},NOW)

class ReleaseTests(unittest.TestCase):
    def test_archive_cannot_substitute_old_source_or_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);commit,digest=self.make(directory);component=release.verify(directory,digest,commit)
            for case in ('matching','old-source','old-dll'):
                value={'SourceCommit':commit,'Files':{'backup/'+name:row.copy() for name,row in component['Files'].items()}}
                if case=='old-source':value['SourceCommit']='b'*40
                if case=='old-dll':value['Files']['backup/SqlBackup.dll']['Sha256']='0'*64
                path=directory/(case+'.tar');body=json.dumps(value).encode()
                with tarfile.open(path,'w') as stream:
                    entry=tarfile.TarInfo('bundle-manifest.json');entry.size=len(body);stream.addfile(entry,io.BytesIO(body))
                if case=='matching':self.assertEqual(release.verify_bundle(path,release.sha(path),component),component)
                else:
                    with self.assertRaisesRegex(release.Refused,'BUNDLE_COMPONENT_MISMATCH'):release.verify_bundle(path,release.sha(path),component)

    def make(self,directory):
        (directory/'SqlBackup').write_bytes(b'\x7fELF\x02'+b'\0'*13+b'\x3e\x00')
        (directory/'SqlBackup.dll').write_bytes(b'synthetic-component-not-executed')
        (directory/'SqlBackup.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{'includedFrameworks':[{'name':'Microsoft.NETCore.App','version':'10.0.13'}]}}))
        commit='a'*40;identity={'Component':'SqlBackup','SourceCommit':commit,'InformationalVersion':'1.0.0+'+commit}
        manifest=release.create(directory,identity,commit);path=directory/'local-component-manifest.json';path.write_text(json.dumps(manifest));return commit,release.sha(path)

    def test_exact_inventory_and_expected_revision_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);commit,digest=self.make(directory);self.assertEqual(release.verify(directory,digest,commit)['SourceCommit'],commit)

    def test_old_manifest_or_revision_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);commit,digest=self.make(directory)
            with self.assertRaisesRegex(release.Refused,'MANIFEST_HASH_MISMATCH'):release.verify(directory,'0'*64,commit)
            with self.assertRaisesRegex(release.Refused,'COMPONENT_REVISION_MISMATCH'):release.verify(directory,digest,'b'*40)

    def test_old_binary_substitution_and_extra_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);commit,digest=self.make(directory);(directory/'SqlBackup.dll').write_bytes(b'old-binary')
            with self.assertRaisesRegex(release.Refused,'COMPONENT_CONTENT_CHANGED'):release.verify(directory,digest,commit)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);commit,digest=self.make(directory);(directory/'extra').write_text('unreviewed')
            with self.assertRaisesRegex(release.Refused,'COMPONENT_CONTENT_CHANGED'):release.verify(directory,digest,commit)

    def test_unbound_identity_or_wrong_runtime_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);self.make(directory)
            with self.assertRaises(release.Refused):release.create(directory,{'Component':'SqlBackup','SourceCommit':'UNBOUND'},'a'*40)
            (directory/'SqlBackup.runtimeconfig.json').write_text('{"runtimeOptions":{}}')
            with self.assertRaisesRegex(release.Refused,'SELF_CONTAINED_RUNTIME_REQUIRED'):release.create(directory,{'Component':'SqlBackup','SourceCommit':'a'*40,'InformationalVersion':'1.0.0+'+'a'*40},'a'*40)

if __name__=='__main__':unittest.main()
