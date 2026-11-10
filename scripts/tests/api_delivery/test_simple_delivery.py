"""Critical behaviors through production adapters; no AWS mutation in tests."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_delivery import ROOT, config, record, pr, Port, authorization_task, ACCOUNT, REGION
from scripts.api_delivery import aws, cli, model as m, workflow_contract
from scripts.api_delivery.github import GitHub, PREFIX, BOT
from scripts.api_delivery.executor import deploy, DeliveryFailure
from scripts.api_delivery.state import State, handover


class Wire:
    """Replace only gh transport. Real get/run/release/approval consume REST."""
    def __init__(self):
        self.rows={};self.seen=[]
    def __call__(self,args,**kwargs):
        path=args[4];self.seen.append(path)
        return m.canonical(self.rows[path])
    def release(self, ident=81, value=None, attempt=1):
        value=value or record(); value['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in value.items() if k!='manifest_ref'}))
        publisher=dict(run=22,attempt=attempt,sha='2'*40)
        self.rows[f'{PREFIX}/deployments/{ident}']=dict(id=ident,task='api-release',environment='api-dev',creator={'login':BOT},sha=value['source'],
            payload=dict(schema='API_INDEX_V2',publisher=publisher,release=value))
        self.rows[f'{PREFIX}/actions/workflows/api-delivery.yml']=dict(id=7)
        self.rows[f'{PREFIX}/actions/runs/22/attempts/{attempt}']=dict(id=22,run_attempt=attempt,repository={'full_name':m.REPOSITORY},head_repository={'full_name':m.REPOSITORY},
            workflow_id=7,path=m.DELIVERY,event='push',head_branch='develop',head_sha='2'*40)
        self.rows[f'{PREFIX}/actions/runs/22/attempts/{attempt}/jobs?per_page=100&page=1']={'jobs':[{'steps':[{'name':'Execute release or reconcile','conclusion':'success'}]}]}
        self.rows[f'{PREFIX}/deployments/{ident}/statuses?per_page=100&page=1']=[dict(state='success',creator={'login':BOT},log_url=f'https://github.com/{m.REPOSITORY}/actions/runs/22/attempts/{attempt}')]
        return value
    def approval(self):
        value=self.release();pull=pr();pull['merged_at']='2026-11-09T22:00:00Z'
        self.rows[PREFIX+'/rules/branches/main']=[dict(type='pull_request',parameters={'allowed_merge_methods':['merge']}),
            dict(type='required_status_checks',parameters=dict(strict_required_status_checks_policy=True,required_status_checks=[dict(context='API Promotion Validation',integration_id=15368)]))]
        loc=dict(v=2,pr=42,base='1'*40,app='b'*64,release=81,run=80,attempt=1)
        self.check=dict(id=90,name='API Promotion Validation',app={'id':15368},head_sha='2'*40,started_at='2026-11-09T21:00:00Z',completed_at='2026-11-09T21:01:00Z',
            conclusion='success',external_id=json.dumps(loc),details_url=f'https://github.com/{m.REPOSITORY}/actions/runs/80/attempts/1')
        self.rows[f'{PREFIX}/commits/{"2"*40}/check-runs?filter=all&per_page=100&page=1']={'check_runs':[self.check]}
        self.rows[f'{PREFIX}/actions/workflows/api-promotion.yml']=dict(id=8)
        self.rows[f'{PREFIX}/actions/runs/80/attempts/1']=dict(id=80,run_attempt=1,repository={'full_name':m.REPOSITORY},head_repository={'full_name':m.REPOSITORY},
            workflow_id=8,path=m.PROMOTION,event='pull_request_target',head_sha='1'*40)
        return pull,value


class ReleaseTests(unittest.TestCase):
    def test_B_pinned_C_published_after_merge_PROD_still_reads_B(self):
        wire=Wire(); pull,b=wire.approval(); wire.release(82,record('c',source='3'))
        # The C fixture reuses a producer for brevity; it must never be read.
        with patch('subprocess.check_output',side_effect=wire):
            got,approval=GitHub().approval(pull,['1'*40,'2'*40],'b'*64)
        self.assertEqual(got['image'],b['image']);self.assertEqual(approval['release'],81)
        self.assertNotIn(PREFIX+'/deployments/82',wire.seen)

    def test_rerun_does_not_erase_original_publisher(self):
        wire=Wire(); b=wire.release(attempt=1)
        wire.rows[PREFIX+'/actions/runs/22']=dict(run_attempt=2,conclusion='failure')
        with patch('subprocess.check_output',side_effect=wire):self.assertEqual(GitHub().release(81),b)
        self.assertNotIn(PREFIX+'/actions/runs/22',wire.seen)
        self.assertFalse(any('/artifacts' in x or '/attestations' in x for x in wire.seen))

    def test_changed_check_producer_head_or_digest_is_rejected(self):
        for change in ('app','head','base','after-merge','workflow','payload','failed-execute'):
            wire=Wire();pull,_=wire.approval();parents=['1'*40,'2'*40]
            if change=='app':wire.check['app']['id']=123
            if change=='head':wire.check['head_sha']='3'*40
            if change=='base':parents[0]='3'*40
            if change=='after-merge':wire.check['completed_at']='2026-11-10T00:00:00Z'
            if change=='workflow':wire.rows[PREFIX+'/actions/runs/80/attempts/1']['path']='.github/workflows/evil.yml'
            if change=='payload':wire.rows[PREFIX+'/deployments/81']['payload']['release']['image']=record('c')['image']
            if change=='failed-execute':wire.rows[PREFIX+'/actions/runs/22/attempts/1/jobs?per_page=100&page=1']['jobs'][0]['steps'][0]['conclusion']='failure'
            with self.subTest(change=change),patch('subprocess.check_output',side_effect=wire),self.assertRaises(ValueError):
                GitHub().approval(pull,parents,'b'*64)

    def test_repository_scope_rejects_prefix_lookalikes(self):
        with patch('subprocess.check_output',return_value=b'{}') as transport:
            GitHub().get(PREFIX); GitHub().get(PREFIX+'/deployments/1')
            with self.assertRaises(ValueError):GitHub().get(PREFIX+'-evil/deployments/1')
            self.assertEqual(transport.call_count,2)

    def test_docs_descendant_and_B_C_Bprime_use_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args): return m.git(tmp,*args).decode().strip()
            git('init');git('config','user.email','test@example.invalid');git('config','user.name','Test')
            p=Path(tmp);(p/'demo-api').mkdir();(p/'demo-api/Dockerfile').write_text('FROM scratch\n')
            git('add','.');git('commit','-m','B');b=git('rev-parse','HEAD');identity=m.application(tmp,b)
            (p/'README.md').write_text('docs');git('add','.');git('commit','-m','docs');docs=git('rev-parse','HEAD')
            self.assertTrue(m.same_application_lineage(tmp,b,docs,identity))
            (p/'demo-api/app').write_text('C');git('add','.');git('commit','-m','C')
            (p/'demo-api/app').unlink();git('add','.');git('commit','-m','Bprime');bp=git('rev-parse','HEAD')
            self.assertEqual(m.application(tmp,bp),identity)
            self.assertFalse(m.same_application_lineage(tmp,b,bp,identity))


class RuntimeTests(unittest.TestCase):
    def test_metadata_and_UpdateService_keyword_remain_valid(self):
        expected=authorization_task(config()['colors']['blue']);actual=copy.deepcopy(expected)
        actual.update(taskDefinitionArn=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{expected["family"]}:2',revision=2,status='ACTIVE',
            compatibilities=['EC2','FARGATE','MANAGED_INSTANCES'],requiresAttributes=[{'name':'ecs.capability.execution-role-ecr-pull'}])
        for c in actual['containerDefinitions']:c['systemControls']=[]
        aws.task_readback(expected,actual,ACCOUNT,REGION)
        for compat in (['EC2'],['FARGATE','FARGATE'],['FARGATE','UNKNOWN']):
            bad=copy.deepcopy(actual);bad['compatibilities']=compat
            with self.assertRaises(ValueError):aws.task_readback(expected,bad,ACCOUNT,REGION)
        calls=[]
        class ECS:
            def update_service(self,**kw):calls.append(kw)
        port=aws.Runtime({'ecs':ECS(),'elbv2':object()},config(),'operation',Path('.'))
        port.journal=lambda stage,value:calls.append(stage)
        port.start('blue','revision')
        self.assertEqual(calls[0],'attempt-update_service')
        self.assertEqual(calls[1],dict(cluster=config()['colors']['blue']['service']['cluster'],service=config()['colors']['blue']['service']['service'],taskDefinition='revision',desiredCount=1))

    def test_SQL_loss_after_wait_preserves_blue_one_green_two(self):
        p=Port();p.replicas=2
        def start(color,revision):p.counts[color]=2;p.revisions[color]=revision
        p.start=start
        def wait():p.fail='client-green'
        p.drain_wait=wait
        with self.assertRaises(DeliveryFailure):deploy(p,record()['image'])
        self.assertEqual(p.routes,('blue','green'));self.assertEqual(p.counts,{'blue':1,'green':2})
        self.assertNotIn('stop-before-blue',p.calls)

    def test_workflow_security_invariants_and_substitutions(self):
        workflow_contract.validate(ROOT)
        for change in ('cancel','aws-on-pr','checkout','global','extra-step','extra-job','env-injection','scope-bypass'):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)/'.github/workflows';folder.mkdir(parents=True)
                for p in (ROOT/'.github/workflows').glob('api-*.yml'):shutil.copy(p,folder/p.name)
                name='api-execute.yml' if change in ('cancel','scope-bypass') else 'api-delivery.yml' if change=='global' else 'api-evaluate.yml'
                path=folder/name;value=json.loads(path.read_text())
                if change=='cancel':value['jobs']['delivery']['concurrency']['cancel-in-progress']=True
                if change=='aws-on-pr':value['jobs']['promotion']['permissions']['id-token']='write'
                if change=='checkout':value['jobs']['promotion']['steps'][0]['with']['ref']='${{ github.event.pull_request.head.sha }}'
                if change=='global':value['jobs']['delivery']['if']="vars.API_DELIVERY_ENABLED == 'true'"
                if change=='extra-step':value['jobs']['promotion']['steps'].append({'run':'aws ecs update-service'})
                if change=='extra-job':value['jobs']['other']={'runs-on':'ubuntu-latest','steps':[{'run':'false'}]}
                if change=='env-injection':value['jobs']['promotion']['env']['BASH_ENV']='untrusted.sh'
                if change=='scope-bypass':value['jobs']['delivery']['if']="${{ true || needs.scope.outputs.deploy == 'true' }}"
                path.write_text(json.dumps(value))
                with self.subTest(change=change),self.assertRaises(ValueError):workflow_contract.validate(tmp)


if __name__=='__main__':unittest.main()
