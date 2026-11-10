"""Real CLI/state transitions with deterministic AWS transports and service port."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from test_delivery import config, record, Port
from scripts.api_delivery import aws, cli, model as m
from scripts.api_delivery.state import State, handover


class S3:
    def __init__(self):self.values={};self.versions={};self.counter=0;self.calls=[]
    def put_object(self,Bucket,Key,Body,**kw):
        self.calls.append(('put',Key))
        if 'IfMatch' in kw and (Key not in self.values or self.values[Key][1]!=kw['IfMatch']):raise ValueError('CAS conflict')
        if kw.get('IfNoneMatch')=='*' and Key in self.values:raise ValueError('already exists')
        self.counter+=1;version=str(self.counter);self.values[Key]=(Body,version);self.versions[(Key,version)]=(Body,kw)
        return {'VersionId':version}
    def get_object(self,Bucket,Key,VersionId=None,**kw):
        self.calls.append(('get',Key))
        version=VersionId or self.values[Key][1];raw,meta=self.versions[(Key,version)]
        return dict(Body=io.BytesIO(raw),ETag=version,VersionId=version,ServerSideEncryption=meta.get('ServerSideEncryption','aws:kms'),
                    SSEKMSKeyId=meta.get('SSEKMSKeyId',config()['evidence_kms_key']))


class Environment:
    def __init__(self,env='dev'):
        self.cfg=config(env);self.s3=S3();self.clients={'s3':self.s3};self.store=State(self.clients,self.cfg)
        self.s3.put_object(Bucket='fixture',Key=self.store.key,Body=m.canonical(dict(schema='API_STATE_V2',environment=env,phase='HEALTHY',current=None,github_id=None)))
        self.counts=dict(build=0,ecr=0,ecs=0);self.port=Port();self.port.replicas=1;self.port.sequence=0
        self.port.aws=self.clients;self.port.config=self.cfg
        baseline=dict(schema='API_RECOVERY_TARGET_V1',kind='native-admission',environment='dev',source='1'*40,application='a'*64,
            image=record('a')['image'],profile='validated-v2',compatibility=self.cfg['compatibility'],revision='old',color='blue')
        self.port.admit_current=lambda history,binding: baseline if not history else dict(baseline,kind='automatic',**{k:history[0][k] for k in ('source','application','image','revision','color')})
        original_register=self.port.register
        def register(color,image):self.counts['ecs']+=1;return original_register(color,image)
        self.register=register
        self.port.register=register
        self.port.journal=self.journal
        self.req=dict(environment=env,source='2'*40,event_source='2'*40,application='b'*64,action='deploy',run_id=22,run_attempt=1)
        self.eligible=True
    def journal(self,stage,value):
        self.port.sequence+=1
        key=f'api-delivery/{self.cfg["environment"]}/operations/{self.port.operation}/'+('release.json' if stage=='release' else f'{self.port.sequence:03}-{stage}.json')
        raw=m.canonical(value);out=self.s3.put_object(Bucket=self.cfg['evidence_bucket'],Key=key,Body=raw,IfNoneMatch='*')
        return dict(bucket=self.cfg['evidence_bucket'],key=key,version=out['VersionId'],sha256=m.sha(raw))
    def factory(self,clients,cfg,operation,directory):
        # Each production invocation constructs a new Runtime. Retain only the
        # simulated remote topology, never a previous invocation's wrapper.
        self.port.operation=operation;self.port.register=self.register
        return self.port
    def publish_image(self,*args):self.counts['build']+=1;self.counts['ecr']+=1;return record()['image']
    def execute(self,output,github=None):
        with ExitStack() as stack:
            for target,value in [('request',lambda:copy.deepcopy(self.req)),('current',lambda *a:self.eligible)]:stack.enter_context(patch.object(cli,target,value))
            stack.enter_context(patch.dict('os.environ',API_BINDING_REF=json.dumps(dict(region='us-east-1',sha256='f'*64)),API_HANDOVER_REF='{}'))
            stack.enter_context(patch.object(aws,'clients',return_value=self.clients));stack.enter_context(patch.object(aws,'binding',return_value=self.cfg))
            stack.enter_context(patch('scripts.api_delivery.state.handover',return_value={}))
            stack.enter_context(patch.object(aws,'Runtime',self.factory));stack.enter_context(patch.object(aws,'publish',self.publish_image))
            stack.enter_context(patch.object(aws,'verify_image',return_value='digest'))
            class GH:
                def wait_checks(self,*args):pass
                def get(self,path):return {'state':'disabled_manually'}
            cli.execute(github or GH(),output)


class OperationsTests(unittest.TestCase):
    def test_reconciliation_requires_both_settled_routes_before_recording_candidate(self):
        from test_configuration import ConfigurationTests
        for routes,accepted in [(('blue','green'),True),(('blue','blue'),False)]:
            port,release,configuration,actual=ConfigurationTests().setup_port()
            original_snapshot=port.snapshot()
            port.snapshot=lambda:dict(original_snapshot,routes=routes)
            state=dict(candidate={k:release[k] for k in ('color','revision','configuration_ref')},
                image=release['image'],request=dict(source=release['source'],event_source=release['source'],application=release['application'],run_id=22,run_attempt=1),
                previous=None,operation='original-operation')
            with patch.object(aws,'verify_image') as image:
                if accepted:
                    result=cli.reconcile(port,state,port.config)
                    self.assertEqual(result['image'],release['image']);self.assertEqual(result['run_id'],22)
                    port.client_ready.assert_called_once();image.assert_called_once()
                    port.journal.assert_called_once()
                else:
                    with self.assertRaisesRegex(ValueError,'transition not settled'):cli.reconcile(port,state,port.config)
                    port.client_ready.assert_not_called();port.journal.assert_not_called();image.assert_not_called()

    def test_PROD_executes_B_pinned_check_index_S3_chain_without_build_when_C_exists(self):
        from test_simple_delivery import Wire
        from scripts.api_delivery.github import GitHub, PREFIX
        f=Environment('prod');wire=Wire();pull,b=wire.approval()
        raw=m.canonical({k:v for k,v in b.items() if k!='manifest_ref'})
        b['manifest_ref']['version']=f.s3.put_object(Bucket='protected-dev',Key=b['manifest_ref']['key'],Body=raw)['VersionId']
        wire.release(82,record('c',source='3'))
        f.req.update(source='4'*40,event_source='4'*40,run_id=90)
        wire.rows[PREFIX+'/commits/'+f.req['source']+'/pulls']=[dict(number=42,merge_commit_sha=f.req['source'],base={'ref':'main'})]
        wire.rows[PREFIX+'/pulls/42']=pull
        for name in ('cd.yml','cd-terragrunt.yml'):wire.rows[PREFIX+'/actions/workflows/'+name]={'state':'disabled_manually'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(GitHub,'wait_checks'),patch.object(m,'git',return_value=('1'*40+' '+'2'*40).encode()),patch('subprocess.check_output',side_effect=wire):
            path=Path(tmp)/'result';f.execute(path,GitHub());result=json.loads(path.read_bytes())
        self.assertEqual(result['image'],b['image']);self.assertEqual(result['source'],'4'*40)
        self.assertEqual(result['approval']['release'],81);self.assertEqual(f.counts,dict(build=0,ecr=0,ecs=1))
        self.assertNotIn(PREFIX+'/deployments/82',wire.seen)
        self.assertIn(('get',b['manifest_ref']['key']),f.s3.calls)

    def test_B_success_index_failure_retry_never_rebuilds_or_deploys(self):
        f=Environment()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.json';f.execute(path);original=path.read_bytes();counts=dict(f.counts)
            # S3 healthy, GitHub index still absent. Same run, a later attempt.
            f.req['run_attempt']=2;f.execute(path)
            self.assertEqual(path.read_bytes(),original);self.assertEqual(f.counts,counts)
            self.assertEqual(counts,dict(build=1,ecr=1,ecs=1));self.assertEqual(f.store.read()['phase'],'HEALTHY')

    def test_new_C_blocks_until_B_publication_reconciled(self):
        f=Environment()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result';f.execute(path);f.req.update(run_id=23,source='3'*40,event_source='3'*40,application='c'*64)
            with self.assertRaisesRegex(ValueError,'publish previous'):f.execute(path)
            self.assertEqual(f.counts,dict(build=1,ecr=1,ecs=1))
            f.req['action']='reconcile';f.execute(path)
            state=f.store.read();state['github_id']=81;f.store.write(state)
            f.req['action']='deploy';f.execute(path)
            self.assertEqual(f.counts,dict(build=2,ecr=2,ecs=2));self.assertEqual(f.store.read()['current']['source'],'3'*40)

    def test_old_retry_cannot_displace_current_release(self):
        f=Environment();f.eligible=False
        with tempfile.TemporaryDirectory() as tmp:f.execute(Path(tmp)/'result')
        self.assertEqual(f.counts,dict(build=0,ecr=0,ecs=0))

    def test_failure_stops_following_jobs_and_reconcile_is_explicit(self):
        f=Environment();f.port.fail='register'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result'
            with self.assertRaises(Exception):f.execute(path)
            self.assertEqual(f.store.read()['phase'],'RECONCILE');counts=dict(f.counts)
            with self.assertRaisesRegex(ValueError,'previous operation unfinished'):f.execute(path)
            self.assertEqual(f.counts,counts)
            f.port.fail=None;f.req['action']='reconcile';f.execute(path)
            self.assertEqual(f.counts,counts);self.assertEqual(f.store.read()['phase'],'HEALTHY')

    def test_handover_absent_and_changed_legacy_head_cannot_authorize(self):
        f=Environment();cfg=f.cfg;binding='f'*64
        value=dict(schema='API_HANDOVER_V2',status='APPROVED',environment='dev',binding_sha256=binding,external_writers_fenced=True,pending_effects_settled=True,
            administrator='fixture-admin',writer_controls=['explicit deny'],execution_termination=['fixture'],settled_effects=['fixture'],
            legacy_head=dict(key='arbitration/dev/application.json',version='1',etag='1',sha256='a'*64))
        raw=m.canonical(value);key='api-delivery/dev/handover/test.json';response=f.s3.put_object(Bucket='protected-dev',Key=key,Body=raw)
        reference=dict(bucket='protected-dev',key=key,version=response['VersionId'],sha256=m.sha(raw))
        f.s3.put_object(Bucket='protected-dev',Key='arbitration/dev/application.json',Body=b'{"state":"ACTIVE"}')
        start=len(f.s3.calls)
        with self.assertRaisesRegex(ValueError,'retired controller state changed'):handover(f.clients,cfg,reference,binding)
        with self.assertRaises(ValueError):handover(f.clients,cfg,{},binding)
        self.assertFalse(any(call[0]=='put' for call in f.s3.calls[start:]))

    def test_S3_manifest_tampering_stops_before_any_service_call(self):
        f=Environment();value=record();raw=m.canonical({k:v for k,v in value.items() if k!='manifest_ref'})
        ref=value['manifest_ref'];response=f.s3.put_object(Bucket=ref['bucket'],Key=ref['key'],Body=raw+b' ',SSEKMSKeyId=f.cfg['evidence_kms_key'])
        ref['version']=response['VersionId'];scope=dict(bucket=ref['bucket'],account=f.cfg['account'],region=f.cfg['region'],kms_key=f.cfg['evidence_kms_key'],environment='dev')
        with self.assertRaisesRegex(ValueError,'manifest bytes'):aws.verify_manifest(f.clients,scope,value)
        self.assertEqual(f.counts,dict(build=0,ecr=0,ecs=0))


if __name__=='__main__':unittest.main()
