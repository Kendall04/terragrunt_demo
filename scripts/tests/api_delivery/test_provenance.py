"""GitHub transport and actual CLI orchestration with offline API responses."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.api_delivery import model as m, cli
from scripts.api_delivery.github import GitHub
from test_delivery import record, pr


def run(workflow=m.DELIVERY, event='push', branch='develop', sha='2'*40):
    return dict(id=22,run_attempt=1,repository={'full_name':m.REPOSITORY},head_repository={'full_name':m.REPOSITORY},
                workflow_id=7,path=workflow,event=event,head_branch=branch,head_sha=sha,
                status='completed',conclusion='success')


class GitHubTests(unittest.TestCase):
    def test_release_requires_actual_App_CI_not_a_skipped_job(self):
        gh=GitHub();gh.runs=lambda *args:iter([run(workflow='.github/workflows/ci.yml')]);gh.get=lambda p:{'id':7}
        name='App CI / .NET Restore • Build • Test • Docker Validate'
        for status in ('skipped','failure','cancelled',None):
            gh.pages=lambda *args:iter([{'name':name,'conclusion':status}])
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'qualification'):
                gh.require_app_validation('2'*40,'develop')
        gh.pages=lambda *args:iter([{'name':name,'conclusion':'success'}])
        gh.require_app_validation('2'*40,'develop')
    def test_forged_failed_canceled_foreign_workflow_and_fork_rejected(self):
        gh=GitHub();gh.get=lambda p:{'id':7}
        gh.trusted(run(),m.DELIVERY,'push','develop')
        for field,value in [('conclusion','cancelled'),('conclusion','failure'),('workflow_id',99),
                            ('path','.github/workflows/fake.yml'),('head_branch','feature/fake'),
                            ('event','pull_request'),('head_repository',{'full_name':'other/repo'})]:
            candidate=run();candidate[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                gh.trusted(candidate,m.DELIVERY,'push','develop')

    def test_zip_digest_and_attempt_are_mandatory(self):
        raw_record=record()
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('result.json',json.dumps(raw_record))
        raw=stream.getvalue()
        metadata=dict(name='release-record',expired=False,id=9,size_in_bytes=len(raw),digest='sha256:'+hashlib.sha256(raw).hexdigest(),
                      workflow_run={'id':22,'repository_id':99,'head_repository_id':99})
        gh=GitHub();gh.pages=lambda *args:iter([metadata]);gh.raw=lambda p:raw
        gh.get=lambda p: metadata if '/artifacts/' in p else {'id':99}
        self.assertEqual(gh.artifact(run(),'release-record'),raw_record)
        with self.assertRaises(ValueError):gh.artifact(dict(run(),run_attempt=2),'release-record')
        metadata['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):gh.artifact(run(),'release-record')

    def test_latest_failed_rerun_cannot_fall_back_to_older_green(self):
        gh=GitHub();older=run(workflow='.github/workflows/ci.yml')
        newer=dict(older,id=23,conclusion='cancelled')
        gh.runs=lambda *args:iter([newer,older]);gh.get=lambda p:{'id':7}
        with self.assertRaisesRegex(ValueError,'untrusted'):gh.wait_checks('2'*40,'develop',1)

    def test_success_without_aggregator_and_wrong_SHA_not_sufficient(self):
        gh=GitHub();gh.runs=lambda *args:iter([run(workflow='.github/workflows/ci.yml')])
        gh.get=lambda p:{'id':7};gh.pages=lambda *args:iter([{'name':'CI Validation','conclusion':'success'}])
        with self.assertRaisesRegex(ValueError,'exact-SHA'):gh.wait_checks('2'*40,'develop',1)

    def test_pending_checks_timeout_and_no_mutation(self):
        gh=GitHub();gh.runs=lambda *args:iter([])
        with patch('scripts.api_delivery.github.time.monotonic',side_effect=[0,0,2]),patch('scripts.api_delivery.github.time.sleep'):
            with self.assertRaisesRegex(ValueError,'did not finish'):gh.wait_checks('2'*40,'develop',1)


class CliTests(unittest.TestCase):
    def test_PROD_CLI_uses_PR_B_receipt_after_DEV_C_and_never_builds(self):
        pull=pr();receipt=m.approval(pull,'b'*64,record())
        class Facts:
            def wait_checks(self,sha,branch):
                assert sha=='4'*40 and branch=='main'
            def get(self,path):
                if '/commits/' in path:return [dict(pull,merge_commit_sha='4'*40)]
                return pull
            def promotion_receipt(self, pull):return receipt,dict(artifact=9)
            def deployments(self,env):
                raise AssertionError('PROD must never resolve latest DEV')
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/'event.json';event.write_text(json.dumps({'before':'1'*40}))
            output=Path(tmp)/'request.json';env=dict(GITHUB_EVENT_PATH=str(event),GITHUB_EVENT_NAME='push',
                GITHUB_REF_NAME='main',GITHUB_SHA='4'*40,GITHUB_REPOSITORY=m.REPOSITORY,
                GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/main',GITHUB_OUTPUT=str(Path(tmp)/'outputs'))
            def app(root,sha):return 'a'*64 if sha=='1'*40 else 'b'*64
            with patch.dict(os.environ,env),patch.object(m,'application',side_effect=app),patch.object(m,'git',return_value=('1'*40+' '+'2'*40).encode()):
                cli.prepare(Facts(),output)
            selected=json.loads(output.read_bytes())
            self.assertEqual(selected['approved']['image'],record()['image'])
            self.assertEqual(selected['source'],'4'*40)
            self.assertEqual(selected['approved']['source'],'2'*40)

    def test_docs_only_push_is_true_noop_even_without_prod_binding(self):
        class Facts:
            def wait_checks(self,*args):pass
            def get(self,*args):raise AssertionError('No artifact or AWS lookup for docs')
        for branch in ('develop','main'):
            with tempfile.TemporaryDirectory() as tmp:
                event=Path(tmp)/'event';event.write_text(json.dumps({'before':'1'*40}))
                out=Path(tmp)/'request.json';env=dict(GITHUB_EVENT_PATH=str(event),GITHUB_EVENT_NAME='push',
                    GITHUB_REF_NAME=branch,GITHUB_SHA='2'*40,GITHUB_REPOSITORY=m.REPOSITORY,
                    GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/'+branch,GITHUB_OUTPUT=str(Path(tmp)/'outputs'))
                with patch.dict(os.environ,env),patch.object(m,'application',return_value='a'*64):cli.prepare(Facts(),out)
                self.assertFalse(out.exists());self.assertIn('deploy=false',(Path(tmp)/'outputs').read_text())

    def test_expired_or_missing_approval_blocks_PROD_no_latest_fallback(self):
        pull=pr()
        class Facts:
            def wait_checks(self,*args):pass
            def get(self,path):return [dict(pull,merge_commit_sha='4'*40)] if '/commits/' in path else pull
            def promotion_receipt(self, pull):raise ValueError('missing/expired')
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/'event';event.write_text(json.dumps({'before':'1'*40}))
            env=dict(GITHUB_EVENT_PATH=str(event),GITHUB_EVENT_NAME='push',GITHUB_REF_NAME='main',GITHUB_SHA='4'*40,
                     GITHUB_REPOSITORY=m.REPOSITORY,GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/main')
            with patch.dict(os.environ,env),patch.object(m,'application',side_effect=['b'*64,'a'*64]),patch.object(m,'git',return_value=('1'*40+' '+'2'*40).encode()):
                with self.assertRaisesRegex(ValueError,'missing/expired'):cli.prepare(Facts(),Path(tmp)/'out')

if __name__=='__main__':unittest.main(verbosity=2)
