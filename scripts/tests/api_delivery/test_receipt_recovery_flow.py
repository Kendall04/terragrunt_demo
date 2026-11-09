"""Receipt outages must not consume the next deployment's E2 operation.

Real CLI, receipt reader, E2 store, S3 journal/admission and blue/green executor;
only external service/build/signature transports use offline fixtures.
"""
import copy
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.api_delivery import aws, cli, model as m, receipts as r
from scripts.api_delivery.github import GitHub
from scripts import environment_mutation as e2
from test_delivery import Port, record
import test_followup_regressions as followup
from test_release_history import ReleaseWire, PREFIX
from test_signed_receipts import VersionedS3
from receipt_fixture import enrich, origin

PREPARE = 'Require exact-SHA CI and resolve immutable promotion'
CREDENTIALS = 'Acquire environment-only deployment identity'


def step(name, conclusion):
    return dict(name=name, status='completed', conclusion=conclusion)


class Flow:
    """Begin at B's real journal/E2 commit boundary, before receipt publication."""
    def __init__(self, directory):
        self.root = Path(directory); self.git = followup.GitHistory(directory)
        b = self.git.commit('B', 'B')
        admission, value, configuration, actual = followup.ConfigurationTests().setup_port()
        self.cfg = admission.config
        value.update(source=b, event_source=b, application=m.application(directory, b))
        enrich(value)
        self.requests = {22: dict(environment='dev', source=b, event_source=b,
                                 application=value['application'], operation='deploy')}
        self.s3 = VersionedS3(self.cfg)
        self.store = e2.Store(self.s3, self.cfg['evidence_bucket'], 'dev'); self.store.initialize()
        initial = self.owner(22); initial.acquire()
        writer = aws.Runtime(dict(s3=self.s3, ecs=None, elbv2=None), self.cfg, initial,
                             initial.operation, directory)
        value['configuration_ref'] = writer.journal('task-configuration', configuration)
        value.update(request_sha256=initial.request_sha256)
        value.pop('manifest_ref')
        value['manifest_ref'] = writer.journal('release', value)
        initial.finish(True, 'SUCCESS')
        self.wire = ReleaseWire(value); self.wire.latest['run_attempt'] = 1
        self.wire.producer['conclusion'] = self.wire.latest['conclusion'] = 'failure'
        self.wire.responses[self.slot_path(22)]['attestations'].clear()
        self.wire.job['steps'] = [step(CREDENTIALS, 'success'), step(r.EXECUTE, 'success'), step(r.SIGN, 'failure')]
        self.port = Port(); self.port.config = self.cfg
        self.port.revisions['blue'] = value['revision']
        self.clients = dict(s3=self.s3, elbv2=None, ecs=type('ECS', (), {
            'describe_task_definition': Mock(return_value={'taskDefinition':actual})})())
        admission.aws = self.clients; admission.snapshot = self.port.snapshot
        admission.client_ready = self.port.client_ready
        self.port.admit_current = admission.admit_current
        self.port.current_configuration = admission.current_configuration
        self.port.tasks = admission.tasks
        self.port.configuration_ref = value['configuration_ref']
        self.effects = dict(build=0, ecr_write=0)
        self.port.register = self.register
        self.Runtime = aws.Runtime

    @staticmethod
    def slot_path(run):
        return PREFIX+'/attestations/sha256:'+m.sha(m.canonical(r.slot('deployment',run,'dev')))+'?per_page=100'

    def owner(self, run):
        operation = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{m.REPOSITORY}/dev/{run}'))
        return e2.Authority(self.store, 'normal-delivery/deploy-dev', operation, self.requests[run])

    def add_run(self, number, status='in_progress', conclusion=None, source=None):
        run = dict(self.wire.producer, id=number, run_attempt=1, status=status, conclusion=conclusion,
                   head_sha=source or self.wire.producer['head_sha'])
        self.wire.responses[PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1']['workflow_runs'].insert(0,run)
        self.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/1'] = run
        self.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/1/jobs?per_page=100&page=1'] = {'jobs':[]}
        self.wire.responses[self.slot_path(number)] = {'attestations':[]}
        return run

    def c(self, number=23):
        c = self.git.commit('C', 'C')
        self.requests[number] = dict(self.requests[22], source=c, event_source=c, application=m.application(self.root,c))
        self.wire.responses[PREFIX+'/git/ref/heads/develop'] = {'object':{'sha':c}}
        return self.add_run(number,source=c)

    def register(self, color, image):
        self.port.mark('register')
        revision=self.wire.value['revision'].replace('blue:2',color+':3')
        candidate=dict(self.wire.value,color=color,image=image,revision=revision)
        configuration,_=followup.configuration_fixture(self.cfg,candidate)
        for container in configuration['task']['containerDefinitions']:container['image']=image
        self.port.configuration_ref=self.port.journal('task-configuration',configuration)
        return revision

    def publish(self, *args):
        self.effects['build'] += 1; self.effects['ecr_write'] += 1
        return getattr(self, 'publish_image', record('c')['image'])

    def counters(self):
        return dict(self.effects, ecs=sum(self.port.calls.count(k) for k in ('register','start','stop-before-blue','stop-before-green')))

    def execute(self, run, attempt):
        folder=self.root/f'{run}-{attempt}'; folder.mkdir()
        request=self.requests[run]; (folder/'request').write_bytes(m.canonical(request))
        owner=self.owner(run)
        writer=self.Runtime(self.clients,self.cfg,owner,owner.operation,folder)
        self.port.journal=writer.journal
        env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':self.cfg['region'],'sha256':'a'*64}),
                 GITHUB_EVENT_NAME='push',GITHUB_RUN_ID=str(run),GITHUB_RUN_ATTEMPT=str(attempt),
                 GITHUB_SHA=request['source'],GITHUB_WORKFLOW_SHA=request['source'],GITHUB_REF='refs/heads/develop',
                 GITHUB_OUTPUT=str(folder/'outputs'))
        with patch.dict(os.environ,env),patch.object(cli,'ROOT',self.root),patch('subprocess.check_output',side_effect=self.wire),\
             patch.object(aws,'clients',return_value=self.clients),patch.object(aws,'binding',return_value=self.cfg),\
             patch.object(aws,'owner',return_value=owner),patch.object(aws,'Runtime',return_value=self.port),\
             patch.object(aws,'publish',side_effect=self.publish),patch.object(aws,'verify_image'):
            cli.execute(GitHub(),folder/'request',folder/'result')
        return json.loads((folder/'result').read_bytes())

    def sign_recovery(self, value):
        pub=origin(value['event_source'],22,2)
        _,locator=self.wire.signatures.sign(r.slot('deployment',22,'dev'),value,pub,recovered=True)
        self.wire.responses[self.slot_path(22)]=self.wire.signatures.responses[self.slot_path(22)]
        reconciler=dict(self.wire.producer,run_attempt=2,conclusion='success')
        self.wire.responses[PREFIX+'/actions/runs/22/attempts/2']=reconciler
        self.wire.latest.update(run_attempt=2,conclusion='success')
        with patch('subprocess.check_output',side_effect=self.wire):
            resolved,_=r.resolve(GitHub(),r.slot('deployment',22,'dev'),locator)
        return resolved


class ReceiptRecoveryFlow(unittest.TestCase):
    def test_B_unsigned_C_superseded_B_reconciles_D_deploys_once(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp); bhead=copy.deepcopy(f.store.read()); c=f.c()
            d=f.git.commit('D','D'); f.requests[24]=dict(f.requests[23],source=d,event_source=d,
                                                      application=m.application(f.root,d))
            f.wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':d}}
            later=f.add_run(24,'queued',source=d)
            skipped=f.execute(23,1)
            self.assertEqual(skipped['reason'],'superseded')
            self.assertEqual(f.store.read(),bhead)
            self.assertIsNone(f.owner(23).retained())
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            # Complete the real signed no-deployment path; D must skip C's
            # authenticated result, never wait for a release C cannot produce.
            c.update(status='completed',conclusion='success')
            f.wire.responses[PREFIX+'/actions/runs/23/attempts/1/jobs?per_page=100&page=1']={'jobs':[
                dict(name='delivery / delivery',steps=[step(r.EXECUTE,'success'),step(r.SIGN,'success')])]}
            descriptor=r.slot('deployment',23,'dev')
            _,locator=f.wire.signatures.sign(descriptor,skipped,origin(c['head_sha'],23,1))
            f.wire.responses[f.slot_path(23)]=f.wire.signatures.responses[f.slot_path(23)]
            with patch('subprocess.check_output',side_effect=f.wire):
                self.assertEqual(r.resolve(GitHub(),descriptor,locator)[0],skipped)
            # D waits only for B, without consuming either operation. B's
            # publication recovery does not consult queued/failed successors.
            with self.assertRaises(ValueError):f.execute(24,1)
            self.assertEqual(f.store.read(),bhead)
            self.assertIsNone(f.owner(24).retained())
            later.update(status='completed',conclusion='failure')
            f.sign_recovery(f.execute(22,2))
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            self.assertEqual(f.store.read(),bhead)
            f.publish_image=record('d')['image']
            result=f.execute(24,2)
            self.assertEqual((result['source'],result['image']),(d,record('d')['image']))
            self.assertEqual(result['previous']['evidence'],f.wire.value['manifest_ref'])
            self.assertEqual(f.port.calls.count('register'),1)
            self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))
            head=f.store.read()[0]
            self.assertEqual((head['state'],head['generation'],head['operation']),('RELEASED',2,f.owner(24).operation))
            self.assertEqual(f.owner(24).retained()['status'],'SUCCESS')
            self.assertIsNone(f.owner(23).retained())
            self.assertEqual(f.port.revisions[f.port.routes[0]],result['revision'])
            self.assertEqual(f.port.counts,dict(blue=0,green=1))
            print('SUPERSEDED_RECEIPT_FLOW '+json.dumps(dict(
                C=dict(build=0,ecr_write=0,ecs=0),B_reconciliation=dict(build=0,ecr_write=0,ecs=0),
                D=f.counters(),E2=dict(state=head['state'],generation=head['generation'],operation=head['operation'],
                                     run=24,terminal='SUCCESS'),served_source=d,served_revision=result['revision'],
                served_image=result['image'],replicas=f.port.counts),sort_keys=True))

    def test_superseded_path_preserves_held_uncertain_and_active_drift_blocks(self):
        for fault in ('held','uncertain','revision'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);f.c();d=f.git.commit('D','D')
                f.wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':d}}
                if fault=='revision':f.port.revisions['blue']='unexpected'
                else:
                    f.requests[25]=f.requests[22];other=f.owner(25);other.acquire()
                    if fault=='uncertain':other.call(lambda:None);other.finish(False,'UNCERTAIN')
                head=copy.deepcopy(f.store.read())
                if fault=='revision':
                    self.assertEqual(f.execute(23,1)['reason'],'superseded')
                else:
                    with self.assertRaises((ValueError,e2.CoordinationError)):f.execute(23,1)
                with self.assertRaises((ValueError,e2.CoordinationError)):f.execute(22,2)
                self.assertEqual(f.store.read(),head)
                self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))

    def test_source_becoming_stale_after_preflight_is_still_checked_under_E2(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp);f.sign_recovery(f.execute(22,2));f.c()
            current=cli.current_request;states=[]
            def advance(gh,request):
                states.append(f.store.read()[0]['state'])
                if states[-1]=='ACTIVE':
                    d=f.git.commit('D','D')
                    f.wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':d}}
                return current(gh,request)
            with patch.object(cli,'current_request',side_effect=advance):result=f.execute(23,1)
            self.assertEqual(states,['RELEASED','ACTIVE'])
            self.assertEqual(result['reason'],'superseded')
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            self.assertEqual(f.port.revisions['blue'],f.wire.value['revision'])

    def test_docs_scope_in_progress_without_delivery_steps_allows_C(self):
        for fault in ('none','prior-effects','scope-conclusion','delivery-steps','delivery-running','dependency','caller'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);f.sign_recovery(f.execute(22,2));f.c()
                docs=f.git.commit('docs-after-C')
                f.wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':docs}}
                later=f.add_run(24,'in_progress',source=docs)
                jobs=[dict(name='delivery / scope',status='in_progress',conclusion=None,
                           steps=[dict(name='Exclude docs before environment concurrency',status='in_progress',conclusion=None)]),
                      dict(name='delivery / delivery',status='queued',conclusion=None,steps=[])]
                workflow=json.loads((ROOT/'.github/workflows/api-execute.yml').read_bytes())
                self.assertEqual(workflow['jobs']['delivery']['needs'],'scope')
                content_path=PREFIX+'/contents/.github/workflows/api-execute.yml?ref='+docs
                if fault=='dependency':workflow['jobs']['delivery'].pop('needs')
                raw=m.canonical(workflow)
                f.wire.responses[content_path]=dict(type='file',path='.github/workflows/api-execute.yml',
                    encoding='base64',size=len(raw),content=base64.b64encode(raw).decode())
                caller=json.loads((ROOT/'.github/workflows/api-delivery.yml').read_bytes())
                if fault=='caller':caller['jobs']['delivery']['uses']='./.github/workflows/other.yml'
                raw=m.canonical(caller)
                f.wire.responses[PREFIX+'/contents/.github/workflows/api-delivery.yml?ref='+docs]=dict(
                    type='file',path='.github/workflows/api-delivery.yml',encoding='base64',size=len(raw),
                    content=base64.b64encode(raw).decode())
                if fault=='scope-conclusion':jobs[0]['conclusion']='success'
                if fault=='delivery-steps':jobs[1]['steps']=[step(CREDENTIALS,'success')]
                if fault=='delivery-running':jobs[1]['status']='in_progress'
                attempt=1
                if fault=='prior-effects':
                    first=dict(later,status='completed',conclusion='failure')
                    f.wire.responses[PREFIX+'/actions/runs/24/attempts/1']=first
                    f.wire.responses[PREFIX+'/actions/runs/24/attempts/1/jobs?per_page=100&page=1']={'jobs':[
                        dict(name='delivery / delivery',status='completed',conclusion='failure',
                             steps=[step(CREDENTIALS,'success'),step(r.EXECUTE,'failure')])]}
                    attempt=2;later['run_attempt']=2
                    f.wire.responses[PREFIX+'/actions/runs/24/attempts/2']=later
                f.wire.responses[f'{PREFIX}/actions/runs/24/attempts/{attempt}/jobs?per_page=100&page=1']={'jobs':jobs}
                head=copy.deepcopy(f.store.read())
                if fault=='none':
                    result=f.execute(23,1)
                    self.assertEqual(result['source'],f.requests[23]['source'])
                    self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))
                    self.assertIn(content_path,f.wire.calls)
                else:
                    with self.assertRaises(ValueError):f.execute(23,1)
                    self.assertEqual(f.store.read(),head)
                    self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))

    def test_B_publication_failure_C_arrives_B_reconciles_C_retries_once(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp); bhead=copy.deepcopy(f.store.read()); c=f.c()
            with self.assertRaises(ValueError): f.execute(23,1)
            # Before the fix C leaves FAILURE/gen2, so B cannot reconcile gen1.
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            self.assertEqual(f.store.read(),bhead)
            self.assertIsNone(f.owner(23).retained())
            c.update(status='completed',conclusion='failure')
            f.wire.responses[PREFIX+'/actions/runs/23/attempts/1/jobs?per_page=100&page=1']={'jobs':[
                dict(name='delivery / delivery',steps=[step(CREDENTIALS,'success'),step(r.EXECUTE,'failure')])]}
            recovered=f.execute(22,2)
            self.assertEqual(f.store.read(),bhead)
            self.assertEqual(f.sign_recovery(recovered),f.wire.value)
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            f.wire.responses[PREFIX+'/actions/runs/23/attempts/1']=copy.deepcopy(c)
            c.update(run_attempt=2,status='in_progress',conclusion=None)
            result=f.execute(23,2)
            self.assertEqual(result['previous']['evidence'],f.wire.value['manifest_ref'])
            self.assertEqual(result['image'],record('c')['image'])
            self.assertEqual(f.port.calls.count('register'),1)
            self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))
            self.assertEqual(f.port.revisions[f.port.routes[0]],result['revision'])
            self.assertEqual(f.port.counts,dict(blue=0,green=1))
            head=f.store.read()[0]
            self.assertEqual((head['state'],head['generation'],head['operation']),('RELEASED',2,f.owner(23).operation))
            self.assertEqual(f.owner(23).retained()['status'],'SUCCESS')
            self.assertEqual(f.owner(22).retained()['status'],'SUCCESS')
            print('RECEIPT_RECOVERY_FLOW '+json.dumps(dict(
                B_reconciliation=dict(build=0,ecr_write=0,ecs=0),C_retry=f.counters(),
                E2=dict(state=head['state'],generation=head['generation'],terminal='SUCCESS'),
                served_revision=result['revision'],replicas=f.port.counts),sort_keys=True))

    def test_later_queued_run_is_not_prior_missing_publication(self):
        for status in ('queued','in_progress'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp); f.sign_recovery(f.execute(22,2)); f.c()
                f.add_run(24,status)
                if status=='in_progress':
                    f.wire.responses[PREFIX+'/actions/runs/24/attempts/1/jobs?per_page=100&page=1']={'jobs':[
                        dict(name='delivery / scope',status='completed',conclusion='success',steps=[]),
                        dict(name='delivery / delivery',status='queued',conclusion=None,steps=[])]}
                result=f.execute(23,1)
                self.assertEqual(result['image'],record('c')['image'])
                self.assertIn(PREFIX+'/actions/runs/24/attempts/1/jobs?per_page=100&page=1',f.wire.calls)
                self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))

    def test_cancelled_after_successful_execute_reconciles_without_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp); f.wire.producer['conclusion']='cancelled'
            original=copy.deepcopy(f.store.read())
            value=f.execute(22,2)
            self.assertEqual(f.sign_recovery(value),f.wire.value)
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            self.assertEqual(f.store.read(),original)

    def test_cancelled_uncertain_or_changed_active_revision_stays_blocked(self):
        for fault in ('execute-cancelled','execute-failed','held','revision','no-release'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);f.wire.producer['conclusion']='cancelled'
                if fault.startswith('execute-'):f.wire.job['steps'][1]['conclusion']=fault.split('-')[1]
                if fault=='held':
                    f.requests[24]=f.requests[22]; other=f.owner(24);other.acquire();other.call(lambda:None);other.finish(False,'UNCERTAIN')
                if fault=='revision':f.port.revisions['blue']='unexpected'
                if fault=='no-release':
                    ref=f.wire.value['manifest_ref'];del f.s3.versions[(ref['key'],ref['version'])]
                original=copy.deepcopy(f.store.read())
                with self.assertRaises((ValueError,e2.CoordinationError)):f.execute(22,2)
                self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0));self.assertEqual(f.store.read(),original)


class PreAuthorityFailure(unittest.TestCase):
    @staticmethod
    def attempt(f, number, attempt=1):
        row=f.add_run(number,'completed','failure') if attempt==1 else dict(f.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/1'],run_attempt=attempt)
        f.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/{attempt}']=row
        jobs=[dict(name='delivery / scope',status='completed',conclusion='success',steps=[]),
              dict(name='delivery / delivery',status='completed',conclusion='failure',steps=[
                  step('Checkout trusted event revision','success'),step(PREPARE,'failure'),
                  step(CREDENTIALS,'skipped'),step(r.EXECUTE,'skipped')])]
        f.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/{attempt}/jobs?per_page=100&page=1']={'jobs':jobs}
        return row,jobs[1]

    def test_prepare_failure_before_credentials_followed_by_good_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp);f.sign_recovery(f.execute(22,2))
            bad=f.git.commit('bad-CI','unqualified')
            original,_=self.attempt(f,23);original['head_sha']=bad
            ci_run=dict(original,id=81,path='.github/workflows/ci.yml',workflow_id=8)
            f.wire.responses[PREFIX+'/actions/workflows/ci.yml']={'id':8}
            f.wire.responses[PREFIX+'/actions/workflows/ci.yml/runs?branch=develop&head_sha='+bad+'&per_page=100&page=1']={'workflow_runs':[ci_run]}
            event=f.root/'event.json';event.write_bytes(m.canonical({'before':f.requests[22]['source']}))
            env=dict(GITHUB_EVENT_PATH=str(event),GITHUB_EVENT_NAME='push',GITHUB_SHA=bad,GITHUB_REF_NAME='develop',
                     GITHUB_REPOSITORY=m.REPOSITORY,GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/develop')
            with patch.dict(os.environ,env),patch.object(cli,'ROOT',f.root),patch('subprocess.check_output',side_effect=f.wire),\
                 self.assertRaisesRegex(ValueError,'untrusted workflow result'):
                cli.prepare(GitHub(),f.root/'failed-request')
            self.assertFalse((f.root/'failed-request').exists())
            self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
            workflow=json.loads((ROOT/'.github/workflows/api-execute.yml').read_bytes())['jobs']['delivery']['steps']
            for name in (CREDENTIALS,r.EXECUTE):
                self.assertEqual(next(s for s in workflow if s['name']==name)['if'],"steps.prepare.outputs.deploy == 'true'")
            f.c(24)
            result=f.execute(24,1)
            self.assertEqual(result['image'],record('c')['image']);self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))
            self.assertIn(PREFIX+'/actions/runs/23/attempts/1/jobs?per_page=100&page=1',f.wire.calls)

    def test_every_attempt_must_prove_no_authority_and_complete_evidence(self):
        for fault in ('safe','credentials','execute','missing-credentials','missing-prepare','duplicate','attempt','source','pending','job-status'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);first,job=self.attempt(f,21);latest,_=self.attempt(f,21,2)
                # The last attempt is safe; the preceding one must not disappear.
                f.wire.responses[PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1']['workflow_runs'][0]=latest
                if fault=='credentials':job['steps'][2]['conclusion']='success'
                if fault=='execute':job['steps'][3]['conclusion']='failure'
                if fault=='missing-credentials':job['steps'].pop(2)
                if fault=='missing-prepare':job['steps'].pop(1)
                if fault=='duplicate':job['steps'].append(step(CREDENTIALS,'skipped'))
                if fault=='attempt':first['run_attempt']=7
                if fault=='source':first['head_sha']='f'*40
                if fault=='pending':first['status']='in_progress'
                if fault=='job-status':job['status']='in_progress'
                with patch('subprocess.check_output',side_effect=f.wire):
                    if fault=='safe':r.proven_no_execution(GitHub(),latest)
                    else:
                        with self.assertRaises(ValueError):r.proven_no_execution(GitHub(),latest)

    def test_queued_retry_does_not_hide_a_prior_attempt_with_possible_effects(self):
        for safe in (True,False):
            with self.subTest(safe=safe),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);first,job=self.attempt(f,21);latest,_=self.attempt(f,21,2)
                latest.update(status='queued',conclusion=None)
                f.wire.responses[PREFIX+'/actions/runs/21/attempts/2/jobs?per_page=100&page=1']={'jobs':[]}
                if not safe:job['steps'][2]['conclusion']='success'
                with patch('subprocess.check_output',side_effect=f.wire):
                    # Promotion stays conservative; only the executor can pass
                    # a queued run after proving all attempts lack authority.
                    with self.assertRaises(ValueError):r.proven_no_execution(GitHub(),latest)
                    if safe:r.proven_no_execution(GitHub(),latest,allow_queued=True)
                    else:
                        with self.assertRaises(ValueError):r.proven_no_execution(GitHub(),latest,allow_queued=True)


if __name__=='__main__':unittest.main(verbosity=2)
