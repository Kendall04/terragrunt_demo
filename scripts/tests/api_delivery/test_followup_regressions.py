"""Second review: exercise real transports, Git ancestry and application health.

All IDs, certificates/configuration and service transports below are fixtures.
No GitHub writes or AWS calls occur in these tests.
"""
import copy
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.api_delivery import aws, cli, model as m, workflow_contract
from scripts.api_delivery.github import GitHub
from scripts.api_delivery.executor import deploy, DeliveryFailure
from test_delivery import config, record, Port, authorization_task, ACCOUNT, REGION, MemoryS3
from test_review_regressions import Rest, PREFIX, ObjectS3
from receipt_fixture import origin
from scripts.api_delivery import receipts as r
import test_review_regressions as review
from scripts import environment_mutation as e2


class Wire:
    """Only gh's external process is replaced; GitHub.get/raw remain real."""
    def __init__(self, fixture):
        self.fixture, self.calls = fixture, []
        fixture.responses[PREFIX+'/actions/runs/80/attempts/2'] = copy.deepcopy(fixture.producer)

    def __call__(self, argv, **kwargs):
        if argv[:2] == ['gh','attestation']: return self.fixture.signatures.verify(argv)
        assert argv[:2] == ['gh', 'api'], argv
        path = argv[-1]
        self.calls.append(path)
        if path in self.fixture.binary:
            return self.fixture.binary[path]
        if path in self.fixture.responses:
            return m.canonical(self.fixture.responses[path])
        raise AssertionError('Unexpected wire request: ' + path)


class GitHubTransportTests(unittest.TestCase):
    def test_repository_root_and_subpaths_use_real_get_raw(self):
        f=Rest(); wire=Wire(f); gh=GitHub()
        with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
            self.assertEqual(gh.get(PREFIX)['id'],99)
            gh.require_merge_policy()
            self.assertEqual(gh.artifact_id(f.producer,'promotion-record-2',901),f.receipt)
            for bad in (PREFIX+'-other', PREFIX+'-other/actions', 'repos/other/terragrunt_demo',
                        'repos/other/terragrunt_demo/actions', 'https://example.test/'+PREFIX):
                with self.subTest(path=bad), self.assertRaisesRegex(ValueError,'repository scope'):
                    gh.get(bad)
        self.assertIn(PREFIX,wire.calls)
        self.assertIn(PREFIX+'/actions/artifacts/901/zip',wire.calls)

    def test_completed_approval_uses_attempt_2_even_when_latest_attempt_is_3(self):
        for event in ('pull_request_target','workflow_run'):
            f=Rest(event); wire=Wire(f)
            f.producer.update(run_attempt=3,status='in_progress',conclusion=None)
            with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
                receipt,locator=GitHub().promotion_receipt(f.pull)
            self.assertEqual((locator['r'],locator['a']),(80,2))
            self.assertEqual(receipt['dev']['image'],record()['image'])
            self.assertIn(PREFIX+'/actions/runs/80/attempts/2',wire.calls)
            self.assertNotIn(PREFIX+'/actions/runs/80',wire.calls)
            self.assertIn(PREFIX+'/attestations/sha256:'+f.locator['s']+'?per_page=100',wire.calls)

    def test_missing_repository_setting_is_optional_for_job_but_required_for_admin(self):
        f=Rest();del f.responses[PREFIX]['allow_merge_commit'];wire=Wire(f)
        with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
            GitHub().require_merge_policy()
            with self.assertRaisesRegex(ValueError,'not observable'):
                GitHub().require_merge_policy(administrator=True)
            f.responses[PREFIX]['allow_merge_commit']=False
            with self.assertRaisesRegex(ValueError,'disabled'):GitHub().require_merge_policy()
            f.responses[PREFIX]['allow_merge_commit']=True
            GitHub().require_merge_policy(administrator=True)
            f.responses[PREFIX+'/rules/branches/main'][1]['parameters']['allowed_merge_methods'].append('squash')
            with self.assertRaisesRegex(ValueError,'merge-only'):GitHub().require_merge_policy()

    def test_sealed_attempt_refuses_substitution_expiry_wrong_attempt_and_producer(self):
        for fault in ('substitute','expired','other-attempt','other-run','other-workflow','other-repo','zip-bytes'):
            f=Rest();wire=Wire(f)
            if fault=='substitute':f.check_record['external_id']=json.dumps(dict(f.locator,h='0'*64))
            if fault=='expired':f.responses[PREFIX+'/attestations/sha256:'+f.locator['s']+'?per_page=100']['attestations'].clear()
            if fault=='other-run':wire.fixture.responses[PREFIX+'/actions/runs/80/attempts/2']['id']=81
            if fault=='other-workflow':wire.fixture.responses[PREFIX+'/actions/runs/80/attempts/2']['workflow_id']=900
            if fault=='other-repo':wire.fixture.responses[PREFIX+'/actions/runs/80/attempts/2']['head_repository']['full_name']='other/repo'
            if fault=='zip-bytes':f.bundle['dsseEnvelope']['signatures'][0]['sig']='altered'
            if fault=='other-attempt':f.check_record['external_id']=json.dumps(dict(f.locator,a=3))
            with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
                with self.subTest(fault=fault),self.assertRaises(ValueError):GitHub().promotion_receipt(f.pull)

    def test_later_green_run_does_not_replace_check_that_authorized_merge(self):
        f=Rest();wire=Wire(f)
        other=dict(f.check_record,id=701,started_at='2026-11-08T20:11:00Z',completed_at='2026-11-08T20:12:00Z',
                   external_id=json.dumps(dict(f.locator,r=81)))
        f.responses[PREFIX+'/commits/'+'2'*40+'/check-runs?filter=all&per_page=100&page=1']['check_runs'].append(other)
        with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
            receipt,locator=GitHub().promotion_receipt(f.pull)
        self.assertEqual((locator['check_id'],locator['r'],locator['a']),(700,80,2))
        self.assertEqual(receipt,f.receipt)
        self.assertFalse(any('/81' in p or '/902' in p for p in wire.calls))

    def test_finalizer_authenticates_current_in_progress_attempt_not_completed_endpoint(self):
        f=Rest();wire=Wire(f);f.producer['status']='in_progress';f.producer['conclusion']=None
        f.check_record.update(status='in_progress',conclusion=None)
        with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=wire):
            self.assertEqual(GitHub().promotion_artifact(f.locator,completed=False),f.receipt)
            f.producer['run_attempt']=3
            with self.assertRaisesRegex(ValueError,'attempt'):GitHub().promotion_artifact(f.locator,completed=False)
        self.assertNotIn(PREFIX+'/actions/runs/80/attempts/2',wire.calls)


class GitHistory:
    def __init__(self, directory):
        self.root=Path(directory); self.shas={}
        self.git('init','-q');self.git('config','user.name','Fixture')
        self.git('config','user.email','fixture@example.invalid')
        (self.root/'demo-api').mkdir()
        (self.root/'demo-api/Dockerfile').write_text('FROM scratch\n')
        self.commit('A','A')
        self.git('remote','add','origin',str(self.root))

    def git(self,*args):
        return m.git(self.root,*args).decode().strip()

    def commit(self,name,app=None):
        if app is not None: (self.root/'demo-api/app.cs').write_text(app)
        else: (self.root/'README.md').write_text(name)
        self.git('add','.');self.git('commit','-qm',name)
        self.shas[name]=self.git('rev-parse','HEAD')
        return self.shas[name]

    def current(self,source,tip,environment='dev'):
        request=dict(environment=environment,event_source=source,source=source,
                     application=m.application(self.root,source),operation='deploy')
        gh=SimpleNamespace(get=lambda path:{'object':{'sha':tip}})
        with patch.object(cli,'ROOT',self.root):
            return cli.current_request(gh,request)


class FreshnessTests(unittest.TestCase):
    def test_real_git_docs_descendant_differs_from_B_C_revert_Bprime(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=GitHistory(tmp);b=h.commit('B','B');docs=h.commit('docs')
            self.assertTrue(h.current(b,docs))
            h.commit('C','C');bp=h.commit('B-prime','B')
            self.assertEqual(m.application(h.root,b),m.application(h.root,bp))
            self.assertFalse(h.current(b,bp))
            self.assertTrue(h.current(bp,h.commit('docs-after-revert')))

    def test_native_queue_does_not_displace_C_with_old_B_retry(self):
        concurrency=json.loads((ROOT/'.github/workflows/api-execute.yml').read_bytes())['jobs']['delivery']['concurrency']
        self.assertFalse(concurrency['cancel-in-progress'])
        # GitHub's documented queue semantics. The workflow must explicitly opt in.
        pending=[]
        for event in ('C','B-retry'):
            if concurrency.get('queue','single') == 'single': pending=[]
            pending.append(event)
        self.assertEqual(pending,['C','B-retry'])

    def test_promotion_evaluator_cannot_reuse_B_receipt_for_revert_Bprime(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=GitHistory(tmp);base=h.shas['A'];b=h.commit('B','B');h.commit('C','C');bp=h.commit('B-prime','B')
            app=m.application(h.root,bp);f=Rest();pull=f.pull
            pull.update(state='open',merged=False);pull['head']['sha']=bp;pull['base']['sha']=base
            old=record('b');old.update(source=b,application=app)
            new=record('d');new.update(source=bp,application=app)
            gh=SimpleNamespace(get=lambda p:pull,check=Mock(return_value={'id':700}),require_merge_policy=Mock(),deployment_receipt=lambda record:{'fixture':record['source']})
            (h.root/'event').write_bytes(m.canonical({'pull_request':copy.deepcopy(pull)}))
            env=dict(GITHUB_EVENT_PATH=str(h.root/'event'),GITHUB_EVENT_NAME='pull_request_target',GITHUB_SHA=base,
                     GITHUB_WORKFLOW_SHA=base,GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.PROMOTION+'@refs/heads/main',
                     GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='2')
            previous=Path.cwd()
            try:
                os.chdir(h.root)
                with patch.dict(os.environ,env),patch.object(cli,'ROOT',h.root):
                    gh.deployments=lambda env, **kwargs:iter([old])
                    with self.assertRaisesRegex(ValueError,'no successful DEV'):cli.promotion(gh,h.root/'result')
                    gh.deployments=lambda env, **kwargs:iter([old,new])
                    cli.promotion(gh,h.root/'result')
            finally:os.chdir(previous)
            receipt=json.loads((h.root/'result').read_bytes())
            self.assertEqual(receipt['dev']['source'],bp)
            self.assertEqual(receipt['dev']['image'],record('d')['image'])

    def execute_fixture(self, h, request, gh, store, run_id, image):
        cfg=config(request['environment']);port=Port();port.counts['blue']=0
        port.admit_current=Mock(return_value=None)
        port.journal=Mock(return_value=dict(bucket='fixture',key='release.json',version='v1',sha256='a'*64))
        owner=e2.Authority(store,'normal-delivery/'+('deploy-dev' if cfg['environment']=='dev' else 'promote-prod'),
                           str(uuid.uuid5(uuid.NAMESPACE_URL,str(run_id))),request)
        path=h.root/('execution-'+str(run_id));path.mkdir()
        (path/'request').write_bytes(m.canonical(request))
        env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':REGION,'sha256':'a'*64}),
                 GITHUB_SHA='2'*40,GITHUB_WORKFLOW_SHA='2'*40,GITHUB_REF='refs/heads/develop',GITHUB_EVENT_NAME='push',GITHUB_RUN_ID=str(run_id),GITHUB_RUN_ATTEMPT='2',GITHUB_OUTPUT=str(path/'outputs'))
        with patch.dict(os.environ,env),patch.object(cli,'ROOT',h.root),patch.object(aws,'clients',return_value={}),\
             patch.object(aws,'binding',return_value=cfg),patch.object(aws,'owner',return_value=owner),\
             patch.object(aws,'Runtime',return_value=port),patch.object(aws,'publish',return_value=image) as build,\
             patch.object(aws,'verify_image'),patch.object(aws,'verify_manifest'):
            cli.execute(gh,path/'request',path/'result')
        result=json.loads((path/'result').read_bytes()) if (path/'result').exists() else None
        if result and result['schema']=='API_NO_DEPLOYMENT_V1': result=None
        return result,port,build

    def test_A_running_C_pending_old_B_retry_C_deploys_once_under_real_E2(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=GitHistory(tmp);b=h.commit('B','B');c=h.commit('C','C')
            store=e2.Store(MemoryS3(),'coordination','dev');store.initialize()
            active=e2.Authority(store,'normal-delivery/deploy-dev','11111111-1111-1111-1111-111111111111',{})
            active.acquire()  # A already passed its freshness check and is deploying.
            concurrency=workflow_contract.EXPECTED['api-execute.yml']['jobs']['delivery']['concurrency']
            pending=[]
            for source in (c,b):
                if concurrency.get('queue','single')=='single':pending=[]
                pending.append(source)
            active.finish(True,'SUCCESS')
            freshness_states=[]
            def get(path):
                if '/workflows/' in path:return {'state':'disabled_manually'}
                freshness_states.append(store.read()[0]['state'])
                return {'object':{'sha':c}}
            gh=SimpleNamespace(get=get,deployments=lambda env, **kwargs:iter([]))
            deployed=[];registrations=0
            for index,source in enumerate(pending):
                request=dict(environment='dev',source=source,event_source=source,
                             application=m.application(h.root,source),operation='deploy')
                result,port,build=self.execute_fixture(h,request,gh,store,100+index,record('c')['image'])
                registrations+=port.calls.count('register')
                if result:deployed.append(result['source']);self.assertEqual(build.call_count,1)
                else:build.assert_not_called();self.assertNotIn('register',port.calls)
            self.assertEqual(deployed,[c]);self.assertEqual(registrations,1)
            # Current C is checked under E2; stale B exits without acquiring.
            self.assertEqual(freshness_states,['RELEASED','ACTIVE','RELEASED'])
            self.assertEqual(store.read()[0]['state'],'RELEASED')

    def test_real_merge_B_C_Bprime_distinct_receipts_old_B_cannot_replace_Bprime(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=GitHistory(tmp);h.git('branch','-M','main');h.git('switch','-qc','develop')
            def merge(name,contents):
                base=h.git('rev-parse','main');h.git('switch','-q','develop')
                h.git('merge','--no-ff','-qm','sync-'+name,'main')
                head=h.commit(name,contents);h.git('switch','-q','main')
                h.git('merge','--no-ff','-qm','promote-'+name,'develop')
                return base,head,h.git('rev-parse','HEAD')
            first=merge('B','B');merge('C','C');last=merge('B-prime','B')
            app=m.application(h.root,last[2]);self.assertEqual(app,m.application(h.root,first[2]))
            store=e2.Store(MemoryS3(),'coordination','prod');store.initialize()
            results=[];real_output=subprocess.check_output
            # New B-prime is deployed first; old B then retries its pre-E2 failure.
            for index,(identities,digest) in enumerate(((last,'d'),(first,'b'))):
                base,head,merged=identities
                f=Rest(letter=digest);f.pull.update(number=43-index,merge_commit_sha=merged)
                f.pull['head']['sha']=head;f.pull['base']['sha']=base
                dev=record(digest);dev.update(source=head,application=app)
                dev['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in dev.items() if k!='manifest_ref'}))
                dev['run_id']=100+index
                _,dev_locator=f.signatures.deployment(dev)
                receipt=dict(m.approval(f.pull,app,dev),run_id=81-index,run_attempt=2,check_id=700,dev_receipt=dev_locator,
                             execution=dict(event='pull_request_target',workflow_sha=base,
                             workflow_ref=m.REPOSITORY+'/'+m.PROMOTION+'@refs/heads/main'))
                producer=dict(f.producer,id=81-index,head_sha=head,pull_requests=[copy.deepcopy(f.pull)])
                _,locator=f.signatures.sign(r.slot('promotion',81-index,attempt=2),receipt,origin(base,81-index,2,'pull_request_target','prod'))
                check=dict(f.check_record,head_sha=head,external_id=json.dumps(locator),details_url=GitHub.approval_url(locator))
                f.responses.update(f.signatures.responses)
                f.responses.update({PREFIX+'/actions/runs/'+str(locator['r'])+'/attempts/2':producer,
                    PREFIX+'/check-runs/700':check,
                    PREFIX+'/commits/'+head+'/check-runs?filter=all&per_page=100&page=1':{'check_runs':[check]},
                    PREFIX+'/git/ref/heads/main':{'object':{'sha':last[2]}}})
                for workflow in ('cd.yml','cd-terragrunt.yml'):f.responses[PREFIX+'/actions/workflows/'+workflow]={'state':'disabled_manually'}
                wire=Wire(f)
                # Wire's default run-80 snapshot is only relevant to the base fixture.
                f.responses[PREFIX+'/actions/runs/'+str(locator['r'])+'/attempts/2']=producer
                def transport(argv,**kw):
                    return wire(argv,**kw) if argv[0]=='gh' else real_output(argv,**kw)
                gh=GitHub();gh.deployments=lambda env, **kwargs:iter([])
                with patch('scripts.api_delivery.github.subprocess.check_output',side_effect=transport):
                    approved,link=gh.promotion_receipt(f.pull)
                    parents=h.git('show','-s','--format=%P',merged).split()
                    dev=m.promoted(f.pull,parents,app,approved)
                    request=dict(environment='prod',source=merged,event_source=merged,application=app,operation='deploy',
                                 approved=dev,promotion=approved,approval=link)
                    result,port,build=self.execute_fixture(h,request,gh,store,200+index,dev['image'])
                build.assert_not_called()
                if result:
                    results.append(result);self.assertEqual(port.calls.count('register'),1)
                else:self.assertNotIn('register',port.calls)
            self.assertEqual(len(results),1);self.assertEqual(results[0]['source'],last[2])
            self.assertEqual(results[0]['image'],record('d')['image'])
            self.assertEqual((results[0]['approval']['r'],results[0]['approval']['a']),(81,2))


class DrainHealthTests(unittest.TestCase):
    def test_green_loses_SQL_or_KMS_during_delay_blue_remains_available(self):
        for dependency in ('database','kms'):
            p=Port();p.replicas=2;p.waited=False
            def start(color,revision): p.counts[color]=2;p.revisions[color]=revision
            p.start=start
            p.drain_wait=lambda:setattr(p,'waited',True)
            p.old_ready=review.RuntimeTests().real_old_runtime().old_ready
            real=aws.Runtime.__new__(aws.Runtime);real.config=config()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self,limit):
                    unhealthy=p.waited and p.routes[0]=='green'
                    return m.canonical(dict(status='Unhealthy' if unhealthy else 'Healthy',checks=[
                        dict(name=d,status='Unhealthy' if unhealthy and d==dependency else 'Healthy')
                        for d in ('database','kms')]))
            opener=SimpleNamespace(open=Mock(side_effect=lambda *a,**k:Response()))
            p.client_ready=real.client_ready
            with patch('scripts.api_delivery.aws.urllib.request.build_opener',return_value=opener):
                with self.subTest(dependency=dependency),self.assertRaisesRegex(DeliveryFailure,'RESTORED_HOLD_RETAINED'):
                    deploy(p,record()['image'])
            self.assertEqual(p.routes,('blue','green'))
            self.assertEqual(p.counts,dict(blue=1,green=2))
            self.assertNotIn('stop-before-blue',p.calls)
            self.assertTrue(any(c.args[0].endswith('/ready') for c in opener.open.call_args_list))


def configuration_fixture(cfg, deployment):
    task=authorization_task(cfg['colors'][deployment['color']])
    app=next(c for c in task['containerDefinitions'] if c['essential'])
    app['secrets'][0]['valueFrom']=cfg['colors'][deployment['color']]['secret_arn']+':::'+cfg['secret_version']
    trust=m.canonical({'fixture':'v1'})
    app['environment'] += [{'name':'Database__SecurityProfile','value':'validated-v2'},
                           {'name':'Database__RunMigrationsOnStartup','value':'false'},
                           {'name':'SQL_TRUST_MANIFEST_B64','value':base64.b64encode(trust).decode()},
                           {'name':'SQL_TRUST_MANIFEST_SHA256','value':m.sha(trust)}]
    value=dict(schema='API_TASK_CONFIGURATION_V1',environment=cfg['environment'],color=deployment['color'],
               image=deployment['image'],revision=deployment['revision'],task=task)
    ref=dict(bucket=cfg['evidence_bucket'],key=deployment['manifest_ref']['key'].replace('release.json','002-task-configuration.json'),
             version='configuration-v1',sha256=m.sha(m.canonical(value)))
    return value,ref


class ConfigurationTests(unittest.TestCase):
    def setup_port(self):
        old=config();latest=record();value,ref=configuration_fixture(old,latest)
        latest['configuration_ref']=ref
        latest['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in latest.items() if k!='manifest_ref'}))
        new=copy.deepcopy(old);new['secret_version']='b'*32;new['trust']['fixture_revision']='v2'
        port=aws.Runtime.__new__(aws.Runtime);port.config=new
        initial=dict(routes=('blue','green'),active='blue',inactive='green',active_revision=latest['revision'],
                     active_count=1,inactive_count=0,pending=0)
        port.snapshot=lambda:initial;port.journal=Mock();port.client_ready=Mock();port.tasks=Mock()
        v2=copy.deepcopy(value['task']);app=next(c for c in v2['containerDefinitions'] if c['essential'])
        app['secrets'][0]['valueFrom']=new['colors']['blue']['secret_arn']+':::'+new['secret_version']
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']='b'*64
        port.render=Mock(return_value=v2)
        actual=dict(copy.deepcopy(value['task']),revision=2,status='ACTIVE',taskDefinitionArn=latest['revision'])
        scope=dict(bucket=old['evidence_bucket'],account=ACCOUNT,region=REGION,kms_key=old['evidence_kms_key'],environment='dev')
        manifests=ObjectS3(latest,scope)
        def get_object(**kw):
            if kw['Key']==ref['key']:
                self.assertEqual(kw['VersionId'],ref['version'])
                return dict(Body=io.BytesIO(m.canonical(value)),VersionId=ref['version'],ServerSideEncryption='aws:kms',
                            SSEKMSKeyId=scope['kms_key'],BucketKeyEnabled=False)
            return manifests.get_object(**kw)
        port.aws={'ecs':SimpleNamespace(describe_task_definition=Mock(return_value={'taskDefinition':actual})),
                  's3':SimpleNamespace(get_object=Mock(side_effect=get_object))}
        return port,latest,value,actual

    def test_active_v1_is_admitted_from_immutable_evidence_when_candidate_uses_v2(self):
        port,latest,old,actual=self.setup_port()
        with patch.object(aws,'verify_image'):
            target=port.admit_current([latest],'b'*64)
        self.assertEqual(target['configuration_ref'],latest['configuration_ref'])
        port.render.assert_not_called()
        port.client_ready.assert_called_once()
        self.assertEqual(port.config['secret_version'],'b'*32)
        self.assertTrue(next(c for c in actual['containerDefinitions'] if c['essential'])['secrets'][0]['valueFrom'].endswith('a'*32))

    def test_real_active_drift_missing_evidence_or_lost_compatibility_is_rejected(self):
        for fault in ('secret','trust','image','missing','hash','version','compatibility','health'):
            port,latest,value,actual=self.setup_port()
            app=next(c for c in actual['containerDefinitions'] if c['essential'])
            if fault=='secret':app['secrets'][0]['valueFrom']=app['secrets'][0]['valueFrom'][:-32]+'c'*32
            if fault=='trust':next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']='0'*64
            if fault=='image':app['image']='substituted'
            if fault=='missing':latest.pop('configuration_ref')
            if fault=='hash':value['task']['cpu']='999'
            if fault=='version':
                original=port.aws['s3'].get_object.side_effect
                def wrong_version(**kw):
                    response=original(**kw)
                    if 'task-configuration' in kw['Key']:response['VersionId']='other-version'
                    return response
                port.aws['s3'].get_object.side_effect=wrong_version
            if fault=='compatibility':port.config['compatibility']='0'*64
            if fault=='health':port.client_ready.side_effect=ValueError('old credentials or CA no longer work')
            # Keep the release authentically consistent with its fixture record.
            if fault=='missing':
                with patch.object(aws,'verify_manifest'),patch.object(aws,'verify_image'):
                    with self.assertRaises(ValueError):port.admit_current([latest],'b'*64)
            else:
                with patch.object(aws,'verify_image'):
                    with self.subTest(fault=fault),self.assertRaises(ValueError):port.admit_current([latest],'b'*64)
            port.journal.assert_not_called()

    def test_native_baseline_requires_exact_configuration_and_current_health(self):
        port,latest,value,_=self.setup_port()
        target=dict(schema='API_RECOVERY_TARGET_V1',kind='native-admission',configuration_ref=latest['configuration_ref'],
                    **{k:latest[k] for k in ('environment','source','application','image','compatibility','profile','revision','color')})
        port.config['native_baseline']=target
        with patch.object(aws,'verify_image'):
            self.assertEqual(port.admit_current([],'b'*64)['configuration_ref'],latest['configuration_ref'])
            target.pop('configuration_ref')
            with self.assertRaises(ValueError):port.admit_current([],'b'*64)

    def test_register_archives_candidate_v2_not_historical_v1(self):
        port,latest,value,_=self.setup_port()
        with patch.object(aws,'verify_image'):
            port.admit_current([latest],'b'*64)
        port.journal.reset_mock()
        revision=latest['revision'].replace('-blue:2','-green:3')
        candidate=dict(latest,color='green',revision=revision)
        candidate_value,_=configuration_fixture(port.config,candidate)
        new_task=candidate_value['task'];port.render.return_value=new_task
        app=next(c for c in new_task['containerDefinitions'] if c['essential'])
        trust=m.canonical({'fixture':'v2'})
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_B64')['value']=base64.b64encode(trust).decode()
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']=m.sha(trust)
        observed=dict(copy.deepcopy(new_task),taskDefinitionArn=revision,status='ACTIVE',revision=3)
        port.aws['ecs'].describe_task_definition.return_value={'taskDefinition':observed}
        port.mutate=Mock(return_value={'taskDefinition':observed})
        port.journal.return_value=dict(latest['configuration_ref'],version='configuration-v2')
        self.assertEqual(port.register('green',latest['image']),revision)
        stage,saved=port.journal.call_args.args
        self.assertEqual(stage,'task-configuration');self.assertEqual(saved['task'],new_task)
        self.assertEqual(saved['color'],'green');self.assertEqual(saved['revision'],revision)
        self.assertEqual(port.configuration_ref['version'],'configuration-v2')
        self.assertTrue(next(c for c in saved['task']['containerDefinitions'] if c['essential'])['secrets'][0]['valueFrom'].endswith('b'*32))


class QueueLintTests(unittest.TestCase):
    def test_narrow_queue_bridge_preserves_all_other_workflow_fields(self):
        spec=importlib.util.spec_from_file_location('lint_actions',ROOT/'.github/scripts/ci/lint-actions.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original=json.loads((ROOT/'.github/workflows/api-execute.yml').read_bytes())
        normalized=json.loads(module.normalize(json.dumps(original)))
        expected=copy.deepcopy(original);del expected['jobs']['delivery']['concurrency']['queue']
        self.assertEqual(normalized,expected)
        for change in ({'queue':'single'},{'queue':True},{'cancel-in-progress':True},{'unexpected':False}):
            invalid=copy.deepcopy(original);invalid['jobs']['delivery']['concurrency'].update(change)
            with self.assertRaises(ValueError):module.normalize(json.dumps(invalid))
        bad=copy.deepcopy(original);bad['jobs']['delivery']['steps'][0]['uses']='not-a-valid-action'
        self.assertEqual(json.loads(module.normalize(json.dumps(bad)))['jobs']['delivery']['steps'][0]['uses'],'not-a-valid-action')
        with self.assertRaisesRegex(ValueError,'duplicate'):module.normalize('{"jobs":{},"jobs":{}}')


if __name__=='__main__':
    unittest.main(verbosity=2)
