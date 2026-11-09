"""Review regressions against real readers/executor, with REST/AWS wire fixtures.

No AWS calls, keys or deployed identifiers. These are protocol tests, not cloud
qualification. In particular REST head_sha is deliberately the PR head.
"""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.api_delivery import model as m, cli, aws, permissions, workflow_contract
from scripts.api_delivery.github import GitHub
from scripts.api_delivery.executor import deploy, DeliveryFailure
from scripts import environment_mutation as e2
from test_delivery import config, record, pr, Port, MemoryS3, authorization_task, ACCOUNT, REGION
from test_provenance import run

PREFIX = 'repos/' + m.REPOSITORY


def failure(code):
    error = RuntimeError(code)
    error.response = {'Error': {'Code': code}}
    return error


class Rest(GitHub):
    """Only transport is doubled. No mocked artifact/receipt/provenance methods."""
    def __init__(self, event='pull_request_target', letter='b', source='2', oci=None):
        self.calls = []; self.responses = {}; self.binary = {}
        pull = pr(); pull.update(state='closed', draft=False, merged_at='2026-11-08T20:10:00Z', merge_commit_sha='4'*40)
        pull['head']['sha'] = source*40
        dev = record(letter, source=source)
        if oci is not None:
            dev['image']=config()['repository']+'@sha256:'+m.sha(oci.encode())
            dev['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in dev.items() if k!='manifest_ref'}))
        receipt = dict(m.approval(pull, letter*64, dev), run_id=80, run_attempt=2,
                       execution=dict(event=event, workflow_sha='1'*40,
                       workflow_ref=m.REPOSITORY+'/'+m.PROMOTION+'@refs/heads/main'))
        producer = dict(run(m.PROMOTION,event,'develop',source*40),id=80,run_attempt=2,
                        pull_requests=[copy.deepcopy(pull)])
        if event == 'workflow_run':
            producer.update(head_sha='1'*40,head_branch='main',pull_requests=[])
            receipt['execution']['trigger'] = dict(id=22,attempt=1,sha=source*40)
            self.responses[PREFIX+'/actions/runs/22/attempts/1'] = run(sha=source*40)
            self.responses[PREFIX+'/actions/workflows/api-delivery.yml'] = {'id':7}
        self.pull, self.receipt, self.producer = pull, receipt, producer
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z: z.writestr('result.json',m.canonical(receipt))
        raw = stream.getvalue(); digest = 'sha256:'+m.sha(raw)
        self.locator = dict(v=1,artifact=901,run=80,attempt=2,digest=digest)
        self.check_record = dict(id=700,name='API Promotion Validation',app={'id':15368},head_sha=source*40,
            status='completed',conclusion='success',started_at='2026-11-08T20:00:00Z',completed_at='2026-11-08T20:01:00Z',
            external_id=json.dumps(self.locator),details_url=self.approval_url(self.locator))
        self.metadata = dict(id=901,name='promotion-record-2',expired=False,size_in_bytes=len(raw),digest=digest,
                             workflow_run=dict(id=80,repository_id=99,head_repository_id=99,head_sha=producer['head_sha']))
        self.responses.update({PREFIX:dict(id=99,allow_merge_commit=True),
            PREFIX+'/rules/branches/main':[permissions.PROMOTION_RULE,{'type':'pull_request','parameters':{'allowed_merge_methods':['merge']}}],
            PREFIX+'/actions/workflows/api-promotion.yml':{'id':7},
            PREFIX+'/actions/runs/80':producer,PREFIX+'/actions/runs/80/attempts/2':producer,
            PREFIX+'/actions/artifacts/901':self.metadata,
            PREFIX+'/commits/'+source*40+'/check-runs?filter=all&per_page=100&page=1':{'check_runs':[self.check_record]},
            PREFIX+'/commits/'+'4'*40+'/pulls':[pull], PREFIX+'/pulls/42':pull})
        self.binary[PREFIX+'/actions/artifacts/901/zip'] = raw

    def get(self,path):
        self.calls.append(path)
        if path not in self.responses: raise AssertionError('unexpected REST lookup: '+path)
        return copy.deepcopy(self.responses[path])

    def raw(self,path):
        self.calls.append(path)
        return self.binary[path]


class DirectReceiptTests(unittest.TestCase):
    def test_real_reader_handles_PRtarget_head_and_workflow_run_separately(self):
        for event in ('pull_request_target','workflow_run'):
            gh=Rest(event)
            result,locator=gh.promotion_receipt(gh.pull)
            self.assertEqual(result,gh.receipt)
            self.assertEqual(locator['artifact'],901)
            self.assertFalse(any('/workflows/' in p and '/runs' in p for p in gh.calls))
            if event=='pull_request_target': self.assertNotEqual(gh.producer['head_sha'],result['base'])
            else:
                gh.producer.update(head_sha='2'*40,head_branch='develop')
                self.assertEqual(gh.promotion_receipt(gh.pull)[0],gh.receipt)

    def test_B_healthy_before_PR_C_after_merge_real_REST_reader_and_CLI_keep_B(self):
        gh=Rest(); gh.wait_checks=Mock()
        # The transport contains only B's directly linked artifact. Any scan for
        # latest DEV/C or for all promotion runs is an unexpected REST lookup.
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); (path/'event').write_text(json.dumps({'before':'1'*40}))
            env=dict(GITHUB_EVENT_PATH=str(path/'event'),GITHUB_EVENT_NAME='push',GITHUB_REF_NAME='main',
                     GITHUB_SHA='4'*40,GITHUB_REPOSITORY=m.REPOSITORY,
                     GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/main',GITHUB_OUTPUT=str(path/'outputs'))
            with patch.dict(os.environ,env),patch.object(m,'application',side_effect=['b'*64,'a'*64]),\
                 patch.object(m,'git',return_value=('1'*40+' '+'2'*40).encode()):
                cli.prepare(gh,path/'request.json')
            selected=json.loads((path/'request.json').read_bytes())
        self.assertEqual(selected['approved']['image'],record()['image'])
        self.assertEqual(selected['source'],'4'*40)
        self.assertEqual(selected['approved']['source'],'2'*40)
        self.assertEqual(selected['approval']['artifact'],901)

    def test_C_before_merge_invalidates_old_check_and_requires_new_receipt(self):
        gh=Rest(); changed=copy.deepcopy(gh.pull); changed['head']['sha']='3'*40
        gh.responses[PREFIX+'/commits/'+'3'*40+'/check-runs?filter=all&per_page=100&page=1']={'check_runs':[gh.check_record]}
        with self.assertRaisesRegex(ValueError,'missing'): gh.promotion_receipt(changed)
        with self.assertRaises(ValueError): m.promoted(changed,['1'*40,'3'*40],'c'*64,gh.receipt)
        revalidated=Rest(letter='c',source='3')
        receipt,_=revalidated.promotion_receipt(revalidated.pull)
        self.assertEqual(m.promoted(revalidated.pull,['1'*40,'3'*40],'c'*64,receipt)['image'],record('c',source='3')['image'])

    def test_expiry_wrong_attempt_producer_digest_PR_and_postmerge_approval_block(self):
        for defect in ('expired','attempt','workflow','event','digest','archive','foreign','pr','after-merge','failed-check','base'):
            gh=Rest()
            if defect=='expired': gh.metadata['expired']=True
            if defect=='attempt': gh.producer['run_attempt']=3
            if defect=='workflow': gh.producer['workflow_id']=900
            if defect=='event': gh.producer['event']='pull_request'
            if defect=='digest': gh.metadata['digest']='sha256:'+'0'*64
            if defect=='archive': gh.binary[PREFIX+'/actions/artifacts/901/zip']+=b'tampered'
            if defect=='foreign': gh.metadata['workflow_run']['head_repository_id']=100
            if defect=='pr': gh.pull['number']=43
            if defect=='after-merge': gh.check_record['completed_at']='2026-11-08T20:11:00Z'
            if defect=='failed-check': gh.check_record['conclusion']='failure'
            if defect=='base': gh.producer['pull_requests'][0]['base']['sha']='9'*40
            with self.subTest(defect=defect),self.assertRaises(ValueError): gh.promotion_receipt(gh.pull)

    def test_green_is_not_written_until_the_exact_uploaded_artifact_is_retrievable(self):
        for missing in (False,True):
            gh=Rest(); gh.producer['status']='in_progress';gh.pull['state']='open';gh.check=Mock()
            if missing: gh.metadata['expired']=True
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp); (path/'evidence').mkdir()
                (path/'promotion-check.json').write_text(json.dumps(dict(id=700,head='2'*40,base='1'*40,pr=42)))
                (path/'evidence/result.json').write_bytes(m.canonical(gh.receipt))
                env=dict(PROMOTION_ARTIFACT_ID='901',PROMOTION_ARTIFACT_DIGEST=gh.locator['digest'][7:],GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='2')
                previous=Path.cwd()
                try:
                    os.chdir(path)
                    with patch.dict(os.environ,env):
                        if missing:
                            with self.assertRaises(ValueError):cli.finish_promotion(gh,True)
                        else:cli.finish_promotion(gh,True)
                finally:os.chdir(previous)
            self.assertEqual(gh.check.call_args.args[1],'failure' if missing else 'success')
            if not missing:self.assertEqual(gh.check.call_args.kwargs['locator'],gh.locator)

    def test_merge_only_preflight_and_declaration_preserve_other_PR_controls(self):
        gh=Rest(); rules=gh.responses[PREFIX+'/rules/branches/main']
        rules[1]['parameters'].update(required_approving_review_count=0,require_last_push_approval=False,
                                      allowed_merge_methods=['merge','squash','rebase'])
        with self.assertRaisesRegex(ValueError,'merge-only'):gh.require_merge_policy()
        overlay=permissions.merge_only_rule(rules[1]);self.assertEqual(overlay['parameters']['required_approving_review_count'],0)
        rules.append(overlay);gh.require_promotion_rule()
        gh.responses[PREFIX]['allow_merge_commit']=False
        with self.assertRaisesRegex(ValueError,'disabled'):gh.require_merge_policy()


class ObjectS3:
    def __init__(self, value, scope): self.value=value;self.scope=scope;self.requests=[];self.raw=m.canonical({k:v for k,v in value.items() if k!='manifest_ref'})
    def get_object(self,**kwargs):
        self.requests.append(kwargs)
        return dict(Body=io.BytesIO(self.raw),VersionId=self.value['manifest_ref']['version'],ServerSideEncryption='aws:kms',
                    SSEKMSKeyId=self.scope['kms_key'],BucketKeyEnabled=False)


class StorageTests(unittest.TestCase):
    def test_exact_S3_version_and_bytes_then_exact_OCI_manifest(self):
        dev=record();scope=config('prod')['dev_evidence'];s3=ObjectS3(dev,scope)
        self.assertEqual(aws.verify_manifest({'s3':s3},scope,dev)['image'],dev['image'])
        self.assertEqual(s3.requests[0]['VersionId'],'s3-version-B')
        self.assertEqual(s3.requests[0]['ExpectedBucketOwner'],ACCOUNT)
        for defect in ('bytes','version','scope','KMS','denied'):
            s3=ObjectS3(dev,scope);bad=copy.deepcopy(dev)
            if defect=='bytes':s3.raw+=b' '
            if defect=='version':bad['manifest_ref']['version']='another-version'
            if defect=='scope':bad['manifest_ref']['key']=bad['manifest_ref']['key'].replace('/dev/','/prod/')
            if defect=='KMS':s3.scope=dict(scope,kms_key='wrong')
            if defect=='denied':s3.get_object=Mock(side_effect=failure('AccessDenied'))
            with self.subTest(defect=defect),self.assertRaises((ValueError,RuntimeError)):
                aws.verify_manifest({'s3':s3},scope,bad)
        raw='{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json"}'
        image=config()['repository']+'@sha256:'+m.sha(raw.encode())
        item=dict(registryId=ACCOUNT,repositoryName='api',imageId={'imageDigest':image.split('@')[1]},imageManifest=raw,
                  imageManifestMediaType='application/vnd.oci.image.manifest.v1+json')
        ecr=SimpleNamespace(batch_get_image=Mock(return_value={'images':[item]}))
        self.assertEqual(aws.verify_image({'ecr':ecr},config(),image),image.split('@')[1])
        item['imageManifest']+=' '
        with self.assertRaisesRegex(ValueError,'identity'):aws.verify_image({'ecr':ecr},config(),image)

    def test_journal_returns_PUT_version_not_an_unversioned_read(self):
        port=aws.Runtime.__new__(aws.Runtime);port.config=config();port.operation='1'*36;port.sequence=0
        raw=m.canonical({'immutable':'manifest'})
        s3=SimpleNamespace(put_object=Mock(return_value={'VersionId':'PUT-v1'}),get_object=Mock(return_value=dict(
            Body=io.BytesIO(raw),VersionId='PUT-v1',ServerSideEncryption='aws:kms',SSEKMSKeyId=config()['evidence_kms_key'])))
        port.aws={'s3':s3};ref=port.journal('release',{'immutable':'manifest'})
        self.assertEqual(ref['version'],'PUT-v1');self.assertEqual(ref['sha256'],m.sha(raw))
        self.assertEqual(s3.get_object.call_args.kwargs['VersionId'],'PUT-v1')
        self.assertEqual(s3.put_object.call_args.kwargs['IfNoneMatch'],'*')

    def test_E2_absence_denial_and_existing_terminal_use_real_Authority(self):
        class S3(MemoryS3):
            denied=False;list_denied=False
            def list_objects_v2(self,**kw):
                if self.list_denied:raise failure('AccessDenied')
                self.assertion=kw
                return {'Contents':[{'Key':k} for k in sorted(self.objects) if k.startswith(kw['Prefix'])][:kw['MaxKeys']]}
            def get_object(self,**kw):
                if self.denied or kw['Key'] not in self.objects:raise failure('AccessDenied')
                return super().get_object(**kw)
        s3=S3();cfg=config();e2.Store(s3,cfg['evidence_bucket'],'dev').initialize()
        authority=aws.owner({'s3':s3},cfg,'11111111-1111-1111-1111-111111111111',{})
        self.assertIsNone(authority.retained()) # Get on a missing key would return 403.
        self.assertEqual(s3.assertion['MaxKeys'],1)
        s3.list_denied=True
        with self.assertRaisesRegex(RuntimeError,'AccessDenied'):authority.retained()
        s3.list_denied=False;authority.acquire();authority.finish(True,'SUCCESS')
        self.assertEqual(authority.retained()['status'],'SUCCESS')
        s3.denied=True
        with self.assertRaisesRegex(RuntimeError,'AccessDenied'):authority.retained()

    def test_IAM_matches_S3_protocol_ECS_table_and_PROD_manifest_scope(self):
        p=permissions.definitions(config('prod'),f'arn:aws:iam::{ACCOUNT}:role/api-delivery-prod',dict(bucket='config',key='prod',version='v'))
        statements=p['permissions']['Statement']
        find=lambda action:[s for s in statements if action in s['Action']]
        self.assertEqual(find('ecs:DescribeTaskDefinition')[0]['Resource'],['*'])
        self.assertTrue(all(':task-definition/demo-prod-app-api-' in r for r in find('ecs:RegisterTaskDefinition')[0]['Resource']))
        listing=find('s3:ListBucket')[0]
        self.assertEqual(listing['Condition']['NumericEquals'],{'s3:max-keys':1})
        self.assertIn('arbitration/prod/terminals/normal-delivery/promote-prod/',listing['Condition']['StringLike']['s3:prefix'])
        dev_reads=[s for s in find('s3:GetObjectVersion') if 'protected-dev' in str(s)]
        self.assertEqual(dev_reads[0]['Resource'],['arn:aws:s3:::protected-dev/api-delivery/dev/operations/*/release.json'])
        self.assertFalse(any('protected-dev' in str(s) for s in find('s3:GetObject')))


class OrderingTests(unittest.TestCase):
    def test_A_running_B_pending_docs_C_never_enters_environment_slot(self):
        # Real Git source identity + real classification, with GitHub's documented
        # single-pending replacement semantics. No assertion of an actual cloud run.
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'demo-api').mkdir()
            def git(*args):return m.git(path,*args).decode().strip()
            git('init');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            (path/'demo-api/Dockerfile').write_text('FROM scratch\n');git('add','.');git('commit','-m','A');a=git('rev-parse','HEAD')
            (path/'demo-api/app.cs').write_text('B');git('add','.');git('commit','-m','B');b=git('rev-parse','HEAD')
            (path/'README.md').write_text('C documentation');git('add','.');git('commit','-m','C docs');c=git('rev-parse','HEAD')
            pending=None; builds=[]
            for before,after in ((a,b),(b,c)):
                event=path/'event.json';event.write_text(json.dumps({'before':before}));out=path/(after+'.outputs')
                with patch.dict(os.environ,dict(GITHUB_EVENT_NAME='push',GITHUB_EVENT_PATH=str(event),GITHUB_SHA=after,GITHUB_OUTPUT=str(out))),patch.object(cli,'ROOT',path):
                    cli.classify()
                if 'deploy=true' in out.read_text():pending=after
            self.assertEqual(pending,b);builds.append(pending);self.assertEqual(builds,[b])
            self.assertEqual(m.application(path,b),m.application(path,c))
        jobs=workflow_contract.EXPECTED['api-execute.yml']['jobs']
        self.assertNotIn('concurrency',jobs['scope']);self.assertEqual(jobs['delivery']['needs'],'scope')
        self.assertIn("needs.scope.outputs.deploy == 'true'",jobs['delivery']['if'])
        ci=json.loads((ROOT/'.github/workflows/ci.yml').read_bytes())
        self.assertIn('github.sha',ci['concurrency']['group'])
        self.assertIn("github.event_name == 'push'",ci['concurrency']['group'])

    def test_old_B_retry_after_C_is_checked_under_E2_and_never_builds(self):
        cfg=config();s3=MemoryS3();store=e2.Store(s3,cfg['evidence_bucket'],'dev');store.initialize()
        owner=e2.Authority(store,'normal-delivery/deploy-dev','11111111-1111-1111-1111-111111111111',{})
        class Facts:
            def get(self,path):
                if '/workflows/' in path:return {'state':'disabled_manually'}
                if '/git/ref/' in path:
                    assert store.read()[0]['state']=='ACTIVE'
                    return {'object':{'sha':'3'*40}}
                raise AssertionError(path)
            def deployments(self,*args):raise AssertionError('superseded run must not reach deployment')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);request=dict(environment='dev',source='2'*40,event_source='2'*40,application='b'*64,operation='deploy')
            (path/'request').write_bytes(m.canonical(request))
            env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':REGION,'sha256':'a'*64}),
                     GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='22',GITHUB_RUN_ATTEMPT='2',GITHUB_OUTPUT=str(path/'outputs'))
            with patch.dict(os.environ,env),patch.object(aws,'clients',return_value={}),patch.object(aws,'binding',return_value=cfg),\
                 patch.object(aws,'owner',return_value=owner),patch.object(aws,'Runtime') as runtime,patch.object(aws,'publish') as publish,\
                 patch.object(m,'git',return_value=b''),patch.object(m,'application',return_value='c'*64):
                cli.execute(Facts(),path/'request',path/'result')
            self.assertFalse((path/'result').exists());self.assertIn('deployed=false',(path/'outputs').read_text())
            publish.assert_not_called();runtime.return_value.admit_current.assert_not_called()
        self.assertEqual(store.read()[0]['state'],'RELEASED')


class RuntimeTests(unittest.TestCase):
    def real_old_runtime(self):
        cfg=config();port=aws.Runtime.__new__(aws.Runtime);port.config=cfg;port.replicas=2
        port.color=lambda c:cfg['colors'][c];port.target=lambda c:'target-'+c
        port.service=lambda c:dict(taskDefinition='old',runningCount=1,desiredCount=1,pendingCount=0)
        name=cfg['colors']['blue']['service']['loadBalancers'][0]['containerName']
        task=dict(taskArn='task-old',taskDefinitionArn='old',lastStatus='RUNNING',containers=[
            dict(name=name,lastStatus='RUNNING'),dict(name=name+'-readiness-probe',lastStatus='STOPPED',exitCode=0)])
        ecs=SimpleNamespace(list_tasks=Mock(return_value={'taskArns':['task-old']}),describe_tasks=Mock(return_value={'tasks':[task]}))
        lb=SimpleNamespace(describe_target_health=Mock(return_value={'TargetHealthDescriptions':[{'TargetHealth':{'State':'healthy'}}]}))
        port.aws=dict(ecs=ecs,elbv2=lb);port.observer=SimpleNamespace(targets=Mock())
        return port

    def test_blue_one_green_two_compensates_with_real_old_capacity_validator(self):
        for fault in ('candidate-before-blue','candidate-after-blue','listener-after-green'):
            port=Port(fault);port.replicas=2
            def start(color,revision):port.counts[color]=2;port.revisions[color]=revision
            port.start=start;real=self.real_old_runtime();port.old_ready=real.old_ready
            with self.subTest(fault=fault),self.assertRaisesRegex(DeliveryFailure,'RESTORED_HOLD_RETAINED'):deploy(port,record()['image'])
            self.assertEqual(port.routes,('blue','green'));self.assertEqual(port.counts,{'blue':1,'green':2})
            self.assertNotIn('stop-before-blue',port.calls)

    def test_lost_compensation_ACK_is_resolved_by_both_route_readbacks(self):
        port=Port('candidate-before-blue');original=port.listener
        def lost(color):
            original(color)
            if color=='blue':raise TimeoutError('applied, response lost')
        port.listener=lost
        with self.assertRaisesRegex(DeliveryFailure,'RESTORED_HOLD_RETAINED'):deploy(port,record()['image'])
        self.assertEqual(port.routes,('blue','green'));self.assertEqual(port.counts,{'blue':1,'green':1})

    def test_real_ECS_metadata_does_not_loosen_requested_fields(self):
        expected=authorization_task(config()['colors']['green']);actual=copy.deepcopy(expected)
        actual.update(taskDefinitionArn=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{expected["family"]}:2',revision=2,status='ACTIVE',
                      compatibilities=['EC2','FARGATE'],requiresAttributes=[{'name':'ecs.capability.execution-role-ecr-pull'},
                      {'name':'com.amazonaws.ecs.capability.docker-remote-api.1.25'}])
        aws.task_readback(expected,actual,ACCOUNT,REGION)
        for mutate in (lambda x:x.update(requiresCompatibilities=['EC2']),lambda x:x.update(taskRoleArn='other'),
                       lambda x:x['containerDefinitions'][0].update(image='changed'),
                       lambda x:x['containerDefinitions'][0].update(secrets=[{'name':'SQL','valueFrom':'foreign'}])):
            bad=copy.deepcopy(actual);mutate(bad)
            with self.assertRaises(ValueError):aws.task_readback(expected,bad,ACCOUNT,REGION)

    def test_native_admission_missing_or_mismatched_blocks_before_register(self):
        cfg=config();port=aws.Runtime.__new__(aws.Runtime);port.config=cfg
        target=dict(schema='API_RECOVERY_TARGET_V1',kind='native-admission',**{k:record()[k] for k in
                    ('environment','source','application','image','compatibility','profile','revision','color')})
        initial=dict(routes=('blue','green'),active='blue',inactive='green',active_revision=target['revision'],active_count=1,inactive_count=0,pending=0)
        port.snapshot=lambda:initial;port.journal=Mock();port.client_ready=Mock();port.tasks=Mock()
        expected=authorization_task(cfg['colors']['blue']);actual=dict(copy.deepcopy(expected),revision=2,status='ACTIVE',taskDefinitionArn=target['revision'])
        port.current_configuration=Mock(return_value=expected);port.aws={'ecs':SimpleNamespace(describe_task_definition=Mock(return_value={'taskDefinition':actual}))}
        with self.assertRaisesRegex(ValueError,'baseline'):port.admit_current([], 'a'*64)
        cfg['native_baseline']=target
        with patch.object(aws,'verify_image'):
            admitted=port.admit_current([], 'a'*64)
            self.assertEqual(admitted['kind'],'native-admission');self.assertNotIn('run_id',admitted)
            self.assertEqual(m.recovery_target(admitted,'dev','f'*64),admitted)
            port.tasks.assert_called_with('blue',target['revision'],target['image'],count=1)
            initial['active_revision']='foreign'
            with self.assertRaisesRegex(ValueError,'identity drift'):port.admit_current([], 'a'*64)
        initial['active_count']=0;port.service=lambda c:{'runningCount':0}
        with self.assertRaisesRegex(ValueError,'empty runtime'):port.admit_current([], 'a'*64)
        cfg['native_baseline']=None;self.assertIsNone(port.admit_current([], 'a'*64))


class ExecutionChainTests(unittest.TestCase):
    def test_PROD_execute_binds_main_approval_S3_and_ECR_before_ECS(self):
        raw='{"schemaVersion":2,"mediaType":"application/vnd.oci.image.manifest.v1+json"}'
        for defect in (None,'S3','ECR'):
            gh=Rest(oci=raw);receipt,locator=gh.promotion_receipt(gh.pull)
            request=dict(environment='prod',source='4'*40,event_source='4'*40,application='b'*64,operation='deploy',
                         approved=receipt['dev'],promotion=receipt,approval=locator)
            cfg=config('prod');s3=ObjectS3(receipt['dev'],cfg['dev_evidence'])
            if defect=='S3':s3.raw+=b'tampered'
            image=receipt['dev']['image']
            item=dict(registryId=ACCOUNT,repositoryName='api',imageId={'imageDigest':image.split('@')[1]},
                      imageManifest=raw+(' ' if defect=='ECR' else ''),imageManifestMediaType='application/vnd.oci.image.manifest.v1+json')
            clients=dict(s3=s3,ecr=SimpleNamespace(batch_get_image=Mock(return_value={'images':[item]})))
            gh.responses[PREFIX+'/git/ref/heads/main']={'object':{'sha':'4'*40}}
            for name in ('cd.yml','cd-terragrunt.yml'):gh.responses[PREFIX+'/actions/workflows/'+name]={'state':'disabled_manually'}
            gh.deployments=lambda env:iter([])
            storage=MemoryS3();store=e2.Store(storage,'coordination','prod');store.initialize()
            owner=e2.Authority(store,'normal-delivery/promote-prod','11111111-1111-1111-1111-111111111111',request)
            port=Port();port.counts['blue']=0;port.admit_current=Mock(return_value=None)
            journal=port.journal
            def archive(stage,value):
                journal(stage,value)
                return dict(bucket='protected-prod',key='api-delivery/prod/operations/example/release.json',version='PROD-v1',sha256=m.sha(m.canonical(value)))
            port.journal=archive
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);(path/'request').write_bytes(m.canonical(request))
                env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':REGION,'sha256':'a'*64}),
                         GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='100',GITHUB_RUN_ATTEMPT='1',GITHUB_OUTPUT=str(path/'outputs'))
                with patch.dict(os.environ,env),patch.object(aws,'clients',return_value=clients),patch.object(aws,'binding',return_value=cfg),\
                     patch.object(aws,'owner',return_value=owner),patch.object(aws,'Runtime',return_value=port),\
                     patch.object(m,'git',return_value=b''),patch.object(m,'application',return_value='b'*64),patch.object(aws,'publish') as publish:
                    if defect:
                        with self.assertRaises(ValueError):cli.execute(gh,path/'request',path/'result')
                        self.assertNotIn('register',port.calls);port.admit_current.assert_not_called()
                    else:
                        cli.execute(gh,path/'request',path/'result')
                        result=json.loads((path/'result').read_bytes())
                        self.assertEqual(result['source'],'4'*40)
                        self.assertEqual(result['image'],image);self.assertEqual(result['approval'],locator)
                        self.assertEqual(result['manifest_ref']['version'],'PROD-v1')
                    publish.assert_not_called()
            self.assertEqual(store.read()[0]['state'],'RELEASED')

    def test_first_manual_rollback_uses_explicit_native_admission_not_fake_CI(self):
        native=dict(schema='API_RECOVERY_TARGET_V1',kind='native-admission',evidence={'binding_sha256':'a'*64},
                    **{k:record('a',source='1')[k] for k in ('environment','source','application','image','compatibility','profile','revision','color')})
        current=record();current['previous']=native
        active=dict(native,kind='automatic',image=current['image'],source=current['source'],application=current['application'])
        gh=SimpleNamespace(get=lambda p:{'state':'disabled_manually'},deployments=lambda env:iter([current]))
        request=dict(environment='dev',source='4'*40,event_source='4'*40,application='b'*64,operation='rollback')
        store=e2.Store(MemoryS3(),'coordination','dev');store.initialize()
        owner=e2.Authority(store,'normal-delivery/deploy-dev','11111111-1111-1111-1111-111111111111',request)
        port=Port();port.admit_current=Mock(return_value=active);port.journal=Mock(return_value={'version':'new'})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'request').write_bytes(m.canonical(request))
            env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':REGION,'sha256':'a'*64}),
                     GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ID='100',GITHUB_RUN_ATTEMPT='1',GITHUB_OUTPUT=str(path/'outputs'))
            with patch.dict(os.environ,env),patch.object(aws,'clients',return_value={}),patch.object(aws,'binding',return_value=config()),\
                 patch.object(aws,'owner',return_value=owner),patch.object(aws,'Runtime',return_value=port),\
                 patch.object(aws,'verify_image') as image,patch.object(aws,'publish') as publish:
                cli.execute(gh,path/'request',path/'result')
            result=json.loads((path/'result').read_bytes())
        self.assertEqual(result['source'],'1'*40);self.assertEqual(result['event_source'],'4'*40)
        self.assertEqual(result['image'],native['image']);self.assertNotIn('run_id',native)
        image.assert_called_once_with({},config(),native['image']);publish.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
