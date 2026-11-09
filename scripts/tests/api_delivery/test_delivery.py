"""Offline acceptance: real coordinator/algorithms, deterministic service ports."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.api_delivery import model as m, cli, aws, permissions, workflow_contract
from scripts.api_delivery.executor import deploy, DeliveryFailure
from scripts.api_delivery.github import GitHub
from scripts.tests.normal_delivery.test_authorization import make_binding, ACCOUNT, REGION
from scripts import environment_mutation as e2


def record(letter='b', env='dev', source='2'):
    value = dict(schema='API_RELEASE_V1', repository=m.REPOSITORY, status='HEALTHY', environment=env,
                source=source*40, application=letter*64, image=ACCOUNT+'.dkr.ecr.us-east-1.amazonaws.com/api@sha256:'+letter*64,
                compatibility='f'*64, profile='validated-v2', per_task_ready=True, client_ready=True, run_id=22, run_attempt=1,
                revision=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/demo-{env}-app-api-blue:2',color='blue')
    value['manifest_ref'] = dict(bucket='protected-'+env, key='api-delivery/'+env+'/operations/11111111-1111-1111-1111-111111111111/release.json',
                                version='s3-version-B',sha256=m.sha(m.canonical(value)))
    return value


def pr():
    return dict(number=42, merged=True, head=dict(ref='develop', sha='2'*40, repo={'full_name': m.REPOSITORY}),
                base=dict(ref='main', sha='1'*40, repo={'full_name': m.REPOSITORY}))


def config(env='dev'):
    return dict(schema='API_INSTALLATION_V1', environment=env, account=ACCOUNT, region=REGION,
                colors={c: make_binding(env, c) for c in ('blue', 'green')},
                database={'environment': env, 'profile': 'validated-v2'}, trust={'environment': env},
                secret_version='a'*32, repository=ACCOUNT+'.dkr.ecr.us-east-1.amazonaws.com/api',
                evidence_bucket='protected-'+env, client_url='https://example.test', replicas=1,
                drain_seconds=30, compatibility='f'*64,
                evidence_kms_key=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/11111111-1111-1111-1111-111111111111',
                binding_kms_key=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/22222222-2222-2222-2222-222222222222',
                native_baseline=None, dev_evidence=None if env=='dev' else dict(bucket='protected-dev',account=ACCOUNT,
                region=REGION,environment='dev',kms_key=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/11111111-1111-1111-1111-111111111111'))


class PromotionTests(unittest.TestCase):
    def test_B_approval_survives_C_in_DEV_and_distinct_merge_SHA(self):
        pull = pr(); approved = m.approval(pull, 'b'*64, record())
        # DEV C is deliberately a newer successful deployment. PROD receives no
        # latest-develop argument: it can only consume the sealed B receipt.
        latest_dev = record('c', source='3')
        merge_sha = '4'*40
        result = m.promoted(pull, ['1'*40, '2'*40], 'b'*64, approved)
        self.assertNotEqual(merge_sha, result['source'])
        self.assertNotEqual(result['image'], latest_dev['image'])
        self.assertEqual(result['image'], record()['image'])

    def test_changed_PR_head_base_or_content_invalidates_B(self):
        receipt = m.approval(pr(), 'b'*64, record())
        for change in ('head', 'base', 'application', 'number', 'squash'):
            pull = pr(); parents = ['1'*40, '2'*40]; app = 'b'*64
            if change == 'head': pull['head']['sha'] = '3'*40
            if change == 'base': parents[0] = '3'*40
            if change == 'application': app = 'c'*64
            if change == 'number': pull['number'] = 43
            if change == 'squash': parents.pop()
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.promoted(pull, parents, app, receipt)

    def test_foreign_branch_fork_pending_failed_or_legacy_rejected(self):
        for change in ('branch', 'fork', 'pending', 'failed', 'profile', 'readiness', 'version'):
            pull = pr(); dev = record()
            if change == 'branch': pull['head']['ref'] = 'feature/backdoor'
            if change == 'fork': pull['head']['repo']['full_name'] = 'other/terragrunt_demo'
            if change in ('pending', 'failed'): dev['status'] = change.upper()
            if change == 'profile': dev['profile'] = 'legacy-v1'
            if change == 'readiness': dev['per_task_ready'] = False
            if change == 'version': dev['application'] = 'c'*64
            with self.subTest(change=change), self.assertRaises(ValueError): m.approval(pull, 'b'*64, dev)

    def test_rollback_is_environment_and_compatibility_scoped(self):
        current, previous = record('c'), record()
        self.assertEqual(m.rollback(current, previous, 'dev', 'f'*64), previous)
        for env, key in [('prod', 'f'*64), ('dev', 'e'*64)]:
            with self.assertRaises(ValueError): m.rollback(current, previous, env, key)
        with self.assertRaises(ValueError): m.rollback(current, current, 'dev', 'f'*64)

    def test_git_application_identity_ignores_docs_preserves_merge_content(self):
        with tempfile.TemporaryDirectory() as temp:
            def git(*args): return m.git(temp, *args).decode().strip()
            git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
            path = Path(temp); (path/'demo-api').mkdir()
            (path/'demo-api/Dockerfile').write_text('FROM scratch\n')
            git('add','.'); git('commit','-m','app'); first=git('rev-parse','HEAD')
            (path/'README.md').write_text('docs'); git('add','.'); git('commit','-m','docs'); second=git('rev-parse','HEAD')
            self.assertEqual(m.application(temp, first), m.application(temp, second))
            (path/'demo-api/runtime.cs').write_text('new app'); git('add','.'); git('commit','-m','change')
            self.assertNotEqual(m.application(temp, first), m.application(temp, git('rev-parse','HEAD')))


class Port:
    replicas = 1
    def __init__(self, fail=None):
        self.routes = ('blue', 'green'); self.counts = {'blue':1,'green':0}
        self.configuration_ref = dict(bucket='fixture',key='configuration',version='configuration-v1',sha256='a'*64)
        self.calls=[]; self.fail=fail; self.revisions={'blue':'old','green':'empty'}
    def mark(self, name):
        self.calls.append(name)
        if self.fail == name: raise TimeoutError(name)
    def snapshot(self):
        self.mark('snapshot'); active=self.routes[0]; inactive='green' if active=='blue' else 'blue'
        return dict(routes=self.routes, active=active, inactive=inactive, active_revision=self.revisions[active],
                    active_count=self.counts[active], inactive_count=self.counts[inactive], pending=0)
    def register(self,color,image): self.mark('register'); return 'new'
    def start(self,color,revision): self.mark('start'); self.counts[color]=1; self.revisions[color]=revision
    def ready(self,*args): self.mark('ready')
    def listener(self,color):
        self.mark('listener-before-'+color); self.routes=(color,self.routes[1]); self.mark('listener-after-'+color)
    def candidate(self,color):
        self.mark('candidate-before-'+color); self.routes=(self.routes[0],color); self.mark('candidate-after-'+color)
    def client_ready(self):
        self.mark('client-'+self.routes[0])
    def drain_wait(self): self.mark('drain-wait')
    def still_ready(self,*args): self.mark('still-ready')
    def old_ready(self,*args): self.mark('old-ready')
    def journal(self,stage,value): self.mark(stage)
    def stop(self,color): self.mark('stop-before-'+color); self.counts[color]=0; self.mark('stop-after-'+color)


class ExecutorTests(unittest.TestCase):
    def test_same_executor_dev_prod_and_rollback(self):
        for environment in ('dev','prod'):
            for action in ('deploy','rollback'):
                with self.subTest(environment=environment, action=action):
                    p=Port(); result=deploy(p,record()['image'])
                    self.assertEqual(result['color'],'green'); self.assertEqual(p.counts,dict(blue=0,green=1))
                    self.assertEqual(p.routes,('green','blue'))
                    self.assertLess(p.calls.index('still-ready'),p.calls.index('stop-before-blue'))

    def test_pre_switch_failures_never_move_traffic_or_drain(self):
        for failure in ('register','start','ready'):
            p=Port(failure)
            with self.subTest(failure=failure), self.assertRaises(DeliveryFailure): deploy(p,record()['image'])
            self.assertEqual(p.routes,('blue','green')); self.assertEqual(p.counts['blue'],1)
            self.assertNotIn('stop-before-blue',p.calls)

    def test_listener_changed_candidate_write_failed_restores_both_routes(self):
        for failure in ('listener-after-green','candidate-before-blue','candidate-after-blue','client-green','healthy-before-drain'):
            p=Port(failure)
            with self.subTest(failure=failure), self.assertRaisesRegex(DeliveryFailure,'RESTORED_HOLD_RETAINED'):
                deploy(p,record()['image'])
            self.assertEqual(p.routes,('blue','green'))
            self.assertEqual(p.counts,dict(blue=1,green=1))
            self.assertIn('old-ready',p.calls); self.assertIn('traffic-restored',p.calls)
            self.assertNotIn('stop-before-blue',p.calls)

    def test_unknown_foreign_route_cannot_be_overwritten(self):
        p=Port('candidate-before-blue')
        def snapshot():
            if 'candidate-before-blue' in p.calls: p.routes=('foreign','green')
            return Port.snapshot(p)
        p.snapshot=snapshot
        with self.assertRaisesRegex(DeliveryFailure,'RECONCILIATION_REQUIRED'): deploy(p,record()['image'])
        self.assertNotIn('listener-before-blue',p.calls)

    def test_post_drain_failure_keeps_new_color_and_never_switches_back(self):
        for failure in ('stop-before-blue','stop-after-blue'):
            p=Port(failure)
            with self.assertRaisesRegex(DeliveryFailure,'POST_DRAIN'): deploy(p,record()['image'])
            self.assertEqual(p.routes,('green','blue')); self.assertEqual(p.counts['green'],1)
            self.assertNotIn('listener-before-blue',p.calls)

    def test_routing_drift_after_delay_blocks_drain(self):
        p=Port()
        def changed(): p.routes=('green','foreign')
        p.drain_wait=changed
        with self.assertRaises(DeliveryFailure): deploy(p,record()['image'])
        self.assertNotIn('stop-before-blue',p.calls)


class BoundaryTests(unittest.TestCase):
    def test_task_readback_normalizes_only_reviewed_ECS_defaults(self):
        cfg=make_binding('dev','green')
        expected=authorization_task(cfg)
        actual=copy.deepcopy(expected)
        actual.update(taskDefinitionArn=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{expected["family"]}:2',
                      revision=2,status='ACTIVE',volumes=[],placementConstraints=[])
        for c in actual['containerDefinitions']:
            c.update(cpu=0,mountPoints=[],volumesFrom=[])
        actual['containerDefinitions'][0]['portMappings'][0]['hostPort']=8080
        aws.task_readback(expected,actual,ACCOUNT,REGION)
        for key,value in [('privileged',True),('user','root'),('entryPoint',['sh']),('dependsOn',[{'containerName':'init','condition':'SUCCESS'}])]:
            bad=copy.deepcopy(actual);bad['containerDefinitions'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):aws.task_readback(expected,bad,ACCOUNT,REGION)

    def test_two_color_binding_fixtures_and_both_cross_environment_rejections(self):
        for env in ('dev','prod'):
            cfg=config(env); aws.validate_binding(cfg,env,ACCOUNT,REGION)
            cfg['colors']['green']=make_binding('prod' if env=='dev' else 'dev','green')
            with self.assertRaises(ValueError): aws.validate_binding(cfg,env,ACCOUNT,REGION)

    def test_ordinary_binding_rejects_legacy_and_unversioned_secret(self):
        for field,value in [('secret_version','latest'),('database',{'environment':'dev','profile':'legacy-v1'})]:
            cfg=config(); cfg[field]=value
            with self.assertRaises(ValueError): aws.validate_binding(cfg,'dev',ACCOUNT,REGION)

    def test_IAM_separates_oidc_environment_AND_branch_and_prod_cannot_publish(self):
        for env in ('dev','prod'):
            result=permissions.definitions(config(env),f'arn:aws:iam::{ACCOUNT}:role/api-delivery-{env}',
                                           dict(bucket='public-config',key=env+'.json',version='exact-version'))
            subject=result['trust']['Statement'][0]['Condition']['StringEquals']['token.actions.githubusercontent.com:sub']
            self.assertIn('environment:api-'+env,subject)
            self.assertIn('job_workflow_ref:'+m.REPOSITORY+'/.github/workflows/api-execute.yml@refs/heads/'+('develop' if env=='dev' else 'main'),subject)
            actions={a for s in result['permissions']['Statement'] for a in s['Action']}
            self.assertEqual('ecr:PutImage' in actions, env=='dev')
            self.assertNotIn('secretsmanager:GetSecretValue', actions)
        self.assertNotIn('iam:PutRolePolicy', actions)

    def test_fixed_client_route_requires_real_database_AND_KMS_health(self):
        class Response:
            status=200
            def __init__(self,value):self.value=value
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,bound):return json.dumps(self.value).encode()
        class Opener:
            def __init__(self,value):self.value=value;self.urls=[]
            def open(self,url,timeout):self.urls.append(url);return Response(self.value)
        port=aws.Runtime.__new__(aws.Runtime);port.config={'client_url':'https://example.test'}
        good={'status':'Healthy','checks':[{'name':'database','status':'Healthy'},{'name':'kms','status':'Healthy'}]}
        for value,accepted in [(good,True),({'status':'Healthy','checks':[]},False),
                               ({'status':'Healthy','checks':[{'name':'database','status':'Healthy'}]},False),
                               ({'status':'Unhealthy','checks':good['checks']},False)]:
            opener=Opener(value)
            with patch('scripts.api_delivery.aws.urllib.request.build_opener',return_value=opener):
                if accepted:port.client_ready()
                else:
                    with self.assertRaises(ValueError):port.client_ready()
            self.assertEqual(opener.urls,['https://example.test/health/live','https://example.test/ready'])

    def test_workflows_closed_and_PR_signing_has_no_AWS_authority(self):
        workflow_contract.validate(ROOT)
        promo=workflow_contract.EXPECTED['api-promotion.yml']
        self.assertNotIn('id-token',promo['permissions'])
        evaluate=workflow_contract.EXPECTED['api-evaluate.yml']['jobs']['promotion']
        self.assertEqual(evaluate['permissions']['id-token'],'write')
        self.assertEqual(evaluate['permissions']['attestations'],'write')
        self.assertNotIn('environment',evaluate)
        self.assertNotIn('configure-aws-credentials',json.dumps(evaluate))
        self.assertEqual(evaluate['steps'][0]['with']['ref'],'${{ github.sha }}')
        self.assertEqual(promo['jobs']['promotion']['uses'],'./.github/workflows/api-evaluate.yml')
        caller=workflow_contract.EXPECTED['api-delivery.yml']
        self.assertNotIn('pull_request',caller['on']);self.assertNotIn('pull_request_target',caller['on'])
        self.assertEqual(caller['jobs']['delivery']['uses'],'./.github/workflows/api-execute.yml')
        self.assertEqual(set(caller['on']['workflow_dispatch']['inputs']),{'environment'})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'.github/workflows';path.mkdir(parents=True)
            for name,value in workflow_contract.EXPECTED.items(): (path/name).write_text(json.dumps(value))
            altered=copy.deepcopy(caller); altered['on']['pull_request']={}
            (path/'api-delivery.yml').write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'WORKFLOW_DRIFT'):workflow_contract.validate(temp)

    def test_preserved_historical_callers_remain_inert(self):
        from scripts.workflow_requests import render
        original=render.callers({})
        for name in ('cd.yml','cd-demo-api.yml','deploy-dev.yml','promote-prod.yml','rollback-manifest.yml'):
            self.assertEqual(json.loads((ROOT/'.github/workflows'/name).read_bytes()),original[name])


class MemoryS3:
    def __init__(self): self.objects={};self.generation=0
    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            error=RuntimeError();error.response={'Error':{'Code':'NoSuchKey'}};raise error
        raw,version=self.objects[Key]
        return dict(Body=io.BytesIO(raw),VersionId=str(version),ETag=str(version))
    def put_object(self, Bucket,Key,Body,ContentType,**conditions):
        if 'IfMatch' in conditions:
            if Key not in self.objects or str(self.objects[Key][1])!=conditions['IfMatch']:raise RuntimeError('CAS')
        elif Key in self.objects:raise RuntimeError('exists')
        self.generation+=1;self.objects[Key]=(Body,self.generation)


def authorization_task(cfg):
    from scripts.normal_delivery import authorization as a
    task,_=a.runtime(cfg,record()['image'],1)
    return task


class ExclusionTests(unittest.TestCase):
    def test_existing_E2_fences_delivery_rollback_and_lifecycle_without_expiry(self):
        s3=MemoryS3();store=e2.Store(s3,'fixture','dev');store.initialize()
        first=e2.Authority(store,'normal-delivery/deploy-dev','11111111-1111-1111-1111-111111111111',{})
        first.acquire();first.call(lambda:None)
        first.finish(False,'UNCERTAIN')
        for binding,layer in [('normal-delivery/deploy-dev',None),('environment-lifecycle/infra-dev','apps')]:
            other=e2.Authority(store,binding,'22222222-2222-2222-2222-222222222222',{},layer=layer)
            with self.assertRaises(e2.CoordinationError):other.acquire()
        self.assertEqual(store.read()[0]['state'],'ACTIVE')


if __name__=='__main__':unittest.main(verbosity=2)
