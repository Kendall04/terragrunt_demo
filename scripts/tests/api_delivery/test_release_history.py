"""Retained successful deployments survive failed reruns (offline REST/AWS).

GitHub get/raw/discovery/ZIP verification, CLI, E2 and active admission are real.
Only external transports and deployment service effects are fixtures; no AWS calls.
"""
import copy
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
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.api_delivery import aws, cli, model as m
from scripts.api_delivery.github import GitHub
from scripts import environment_mutation as e2
from test_delivery import config, record, pr, MemoryS3, Port, REGION
from test_provenance import run
from receipt_fixture import Signatures, enrich
from scripts.api_delivery import receipts as r
from test_review_regressions import ObjectS3
import test_followup_regressions as followup

PREFIX = 'repos/' + m.REPOSITORY
EXECUTE = 'Build once in DEV or deploy approved digest in PROD'
UPLOAD = 'Retain authenticated successful deployment'


class ReleaseWire:
    """Replace only gh's subprocess; real Git commands still run."""
    def __init__(self, value=None, conclusion='failure'):
        self.value = copy.deepcopy(value or record())
        enrich(self.value)
        self.value['manifest_ref']['sha256'] = m.sha(m.canonical(
            {k:v for k,v in self.value.items() if k != 'manifest_ref'}))
        branch = 'develop' if self.value['environment'] == 'dev' else 'main'
        self.producer = run(branch=branch, sha=self.value['event_source'])
        self.latest = dict(self.producer, run_attempt=2, conclusion=conclusion)
        self.calls = []
        self.external = subprocess.check_output
        self.metadata = dict(id=901, name='release-record', expired=False,
            workflow_run=dict(id=22, repository_id=99, head_repository_id=99,
                              head_sha=self.producer['head_sha']),
            created_at='2026-11-08T20:01:01.123Z')
        self.job = dict(id=700, run_id=22, head_sha=self.producer['head_sha'],
            status='completed', conclusion='success', steps=[
                dict(name=EXECUTE, status='completed', conclusion='success',
                     started_at='2026-11-08T20:00:00Z', completed_at='2026-11-08T20:01:00Z'),
                dict(name=UPLOAD, status='completed', conclusion='success',
                     started_at='2026-11-08T20:01:01Z', completed_at='2026-11-08T20:01:02Z')])
        self.responses = {PREFIX: {'id':99},
            PREFIX+'/actions/workflows/api-delivery.yml': {'id':7},
            PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1': {'workflow_runs':[self.latest]},
            PREFIX+'/actions/runs/22/attempts/1': self.producer,
            PREFIX+'/actions/runs/22/attempts/2': self.latest,
            PREFIX+'/actions/runs/22/attempts/1/jobs?per_page=100&page=1': {'jobs':[self.job]},
            PREFIX+'/actions/runs/22/artifacts?per_page=100&page=1': {'artifacts':[self.metadata]},
            PREFIX+'/actions/runs/22/artifacts': {'artifacts':[self.metadata]},
            PREFIX+'/actions/artifacts/901': self.metadata}
        for name in ('cd.yml','cd-terragrunt.yml'):
            self.responses[PREFIX+'/actions/workflows/'+name] = {'state':'disabled_manually'}
        self.pack()

    def pack(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('result.json', m.canonical(self.value))
        self.raw = stream.getvalue()
        self.signatures=Signatures()
        self.bundle,self.locator=self.signatures.deployment(self.value)
        self.responses.update({k:v for k,v in self.signatures.responses.items() if '/attestations/' in k})
        self.metadata.update(size_in_bytes=len(self.raw), digest='sha256:'+m.sha(self.raw))

    def __call__(self, argv, **kwargs):
        if argv[0] != 'gh': return self.external(argv, **kwargs)
        if argv[:2] == ['gh','attestation']: return self.signatures.verify(argv)
        path = argv[-1]; self.calls.append(path)
        if path == PREFIX+'/actions/artifacts/901/zip': return self.raw
        if path in self.responses: return m.canonical(self.responses[path])
        raise AssertionError('Unexpected REST request: '+path)


class ReleaseHistoryTests(unittest.TestCase):
    def test_failed_or_cancelled_rerun_keeps_original_producer_and_artifact(self):
        for outcome in ('failure', 'cancelled'):
            wire = ReleaseWire(conclusion=outcome)
            with self.subTest(outcome=outcome), patch('subprocess.check_output', side_effect=wire):
                found = list(GitHub().deployments('dev'))
            self.assertEqual(found, [wire.value])
            self.assertEqual((found[0]['run_id'],found[0]['run_attempt']), (22,1))
            self.assertIn(PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100', wire.calls)
            self.assertIn(PREFIX+'/actions/runs/22/attempts/1', wire.calls)
            self.assertNotIn(PREFIX+'/actions/runs/22/attempts/2', wire.calls)

    def test_bad_artifact_or_insufficient_producer_evidence_blocks_not_falls_back(self):
        faults = ('deleted','other-run','foreign-repo','workflow','producer-failed','branch','event',
                  'source','attempt','signature','missing-execution','failed-execution','contradiction','manifest-ref','private-field')
        for fault in faults:
            wire = ReleaseWire()
            if fault == 'deleted': wire.responses[PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100']['attestations'].clear()
            if fault == 'other-run': wire.producer['id'] = 23
            if fault == 'foreign-repo': wire.producer['head_repository']['full_name'] = 'other/repo'
            if fault == 'workflow': wire.producer['workflow_id'] = 8
            if fault == 'producer-failed': wire.producer['conclusion'] = 'failure'
            if fault == 'branch': wire.producer['head_branch'] = 'main'
            if fault == 'event': wire.producer['event'] = 'pull_request'
            if fault == 'source': wire.value['source'] = '9'*40; wire.pack()
            if fault == 'attempt': wire.value['run_attempt'] = 2; wire.pack()
            if fault == 'signature': wire.bundle['dsseEnvelope']['signatures'][0]['sig']='altered'
            if fault == 'missing-execution': wire.job['steps'].pop(0)
            if fault == 'failed-execution': wire.job['steps'][0]['conclusion']='failure'
            if fault == 'contradiction':
                other=copy.deepcopy(wire.value);other['image']=record('c')['image']
                wire.signatures.deployment(other)
            if fault == 'manifest-ref': wire.value['manifest_ref']['version'] = 'latest'; wire.pack()
            if fault == 'private-field': wire.value['password'] = 'not-a-real-secret'; wire.pack()
            with self.subTest(fault=fault), patch('subprocess.check_output', side_effect=wire):
                with self.assertRaises(ValueError): list(GitHub().deployments('dev'))

    def test_missing_publication_is_not_a_noop_and_dispatch_keeps_identity(self):
        wire=ReleaseWire()
        wire.responses[PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100']['attestations'].clear()
        with patch('subprocess.check_output',side_effect=wire), self.assertRaises(ValueError):
            list(GitHub().deployments('dev'))
        wire=ReleaseWire(record(env='prod'))
        wire.producer['event']=wire.latest['event']=wire.value['producer']['event']='workflow_dispatch'
        wire.value['source']='9'*40;wire.pack()
        with patch('subprocess.check_output',side_effect=wire):
            self.assertEqual(list(GitHub().deployments('prod')),[wire.value])

    def test_promotion_remains_evaluable_after_failed_or_cancelled_rerun(self):
        for outcome in ('failure','cancelled'):
            with tempfile.TemporaryDirectory() as tmp:
                h=followup.GitHistory(tmp); base=h.shas['A']; b=h.commit('B','B')
                value=record(); value.update(source=b,application=m.application(h.root,b))
                wire=ReleaseWire(value,outcome); pull=pr()
                pull.update(state='open',draft=False); pull['head']['sha']=b; pull['base']['sha']=base
                wire.responses.update({PREFIX+'/pulls/42':pull,
                    PREFIX+'/rules/branches/main':[{'type':'pull_request','parameters':{'allowed_merge_methods':['merge']}}]})
                (h.root/'event').write_bytes(m.canonical({'pull_request':{'number':42}}))
                env=dict(GITHUB_EVENT_PATH=str(h.root/'event'),GITHUB_EVENT_NAME='pull_request_target',
                    GITHUB_SHA=base,GITHUB_WORKFLOW_SHA=base,GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='1',
                    GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.PROMOTION+'@refs/heads/main')
                previous=Path.cwd()
                try:
                    os.chdir(h.root)
                    # Check creation is the only write; all reads use real get/raw.
                    with patch.dict(os.environ,env), patch.object(cli,'ROOT',h.root), \
                         patch('subprocess.check_output',side_effect=wire), \
                         patch.object(GitHub,'check',return_value={'id':700}):
                        cli.promotion(GitHub(),h.root/'approval.json')
                finally: os.chdir(previous)
                approved=json.loads((h.root/'approval.json').read_bytes())['dev']
                self.assertEqual(approved,wire.value)
                self.assertEqual((approved['run_id'],approved['run_attempt']), (22,1))

    def scenario(self, tmp, outcome):
        h=followup.GitHistory(tmp); b=h.commit('B','B')
        admission,original,configuration,actual=followup.ConfigurationTests().setup_port()
        request=dict(environment='dev',source=b,event_source=b,application=m.application(h.root,b),operation='deploy')
        original.update(source=b,event_source=b,application=request['application'])
        wire=ReleaseWire(original,outcome); original=wire.value
        scope=dict(bucket=admission.config['evidence_bucket'],account=admission.config['account'],region=REGION,
                   kms_key=admission.config['evidence_kms_key'],environment='dev')
        manifest=ObjectS3(original,scope)
        old_get=admission.aws['s3'].get_object
        def get_object(**kw):
            if kw['Key'] == original['manifest_ref']['key']: return manifest.get_object(**kw)
            return old_get(**kw)
        admission.aws['s3'].get_object=Mock(side_effect=get_object)
        store=e2.Store(MemoryS3(),'coordination','dev'); store.initialize()
        def owner(run_id, req):
            operation=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{m.REPOSITORY}/dev/{run_id}'))
            return e2.Authority(store,'normal-delivery/deploy-dev',operation,req)
        completed=owner(22,request); completed.acquire(); completed.finish(True,'SUCCESS')
        self.assertEqual(completed.retained()['status'],'SUCCESS')
        port=Port();port.revisions['blue']=original['revision']
        port.admit_current=admission.admit_current
        port.journal=Mock(return_value=original['manifest_ref'])
        build,ecr=Mock(return_value=record('c')['image']),Mock()
        def execute(run_id, req, attempt):
            folder=h.root/str(run_id);folder.mkdir(exist_ok=True)
            (folder/'request').write_bytes(m.canonical(req))
            env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':REGION,'sha256':'a'*64}),
                GITHUB_SHA=req['event_source'],GITHUB_WORKFLOW_SHA=req['event_source'],GITHUB_REF='refs/heads/develop',GITHUB_EVENT_NAME='push',GITHUB_RUN_ID=str(run_id),GITHUB_RUN_ATTEMPT=str(attempt),
                GITHUB_OUTPUT=str(folder/'outputs'))
            with patch.dict(os.environ,env),patch.object(cli,'ROOT',h.root), \
                 patch('subprocess.check_output',side_effect=wire),patch.object(aws,'clients',return_value={}), \
                 patch.object(aws,'binding',return_value=admission.config), \
                 patch.object(aws,'owner',return_value=owner(run_id,req)), \
                 patch.object(aws,'Runtime',return_value=port),patch.object(aws,'publish',build), \
                 patch.object(aws,'verify_image',ecr):
                cli.execute(GitHub(),folder/'request',folder/'result')
            return json.loads((folder/'result').read_bytes())
        return h,request,wire,admission,actual,manifest,store,owner,port,build,ecr,execute

    def test_B_attempt1_retry_mutates_zero_C_admits_original_B_and_deploys(self):
        for outcome in ('failure','cancelled'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                h,request,wire,admission,actual,manifest,store,owner,port,build,ecr,execute=self.scenario(tmp,outcome)
                # E2's immutable terminal exists before retry; no effect can repeat.
                if outcome == 'failure':
                    with patch.object(aws,'recover_release',side_effect=ValueError('publication requires exact S3 recovery')), self.assertRaisesRegex(ValueError,'publication requires'):
                        execute(22,request,2)
                else:
                    # Cancellation before ownership/mutation, with the original
                    # terminal retained. It must not mask that completed release.
                    with patch.object(e2.Authority,'retained',side_effect=KeyboardInterrupt('cancelled')), \
                         self.assertRaises(KeyboardInterrupt):
                        execute(22,request,2)
                self.assertEqual((build.call_count,ecr.call_count,len(port.calls)),(0,0,0))
                self.assertEqual(port.counts,{'blue':1,'green':0})
                self.assertEqual(owner(22,request).retained()['status'],'SUCCESS')
                c=h.commit('C','C')
                wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':c}}
                req=dict(request,source=c,event_source=c,application=m.application(h.root,c))
                result=execute(23,req,1)
                self.assertEqual(result['previous']['evidence'],wire.value['manifest_ref'])
                self.assertEqual(result['previous']['revision'],wire.value['revision'])
                self.assertEqual(result['image'],record('c')['image'])
                self.assertEqual(port.calls.count('register'),1)
                self.assertEqual(port.routes,('green','blue'))
                self.assertEqual(manifest.requests[0]['VersionId'],'s3-version-B')
                self.assertIn(PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100',wire.calls)
                self.assertEqual(store.read()[0]['state'],'RELEASED')

    def test_uncertain_later_effect_or_active_drift_blocks_C_before_build(self):
        for fault in ('uncertain','revision','manifest-bytes','manifest-version'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                h,request,wire,admission,actual,manifest,store,owner,port,build,ecr,execute=self.scenario(tmp,'failure')
                if fault == 'uncertain':
                    blocked=owner(24,request);blocked.acquire();blocked.call(lambda:None);blocked.finish(False,'UNCERTAIN')
                if fault == 'revision': admission.snapshot()['active_revision']='arn:aws:ecs:unexpected'
                if fault == 'manifest-bytes': manifest.raw+=b'changed'
                if fault == 'manifest-version': manifest.value=copy.deepcopy(manifest.value);manifest.value['manifest_ref']['version']='other'
                c=h.commit('C','C');wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':c}}
                req=dict(request,source=c,event_source=c,application=m.application(h.root,c))
                with self.assertRaises((ValueError,e2.CoordinationError)):execute(23,req,1)
                build.assert_not_called();self.assertNotIn('register',port.calls)
                self.assertEqual(port.counts,{'blue':1,'green':0})

    @staticmethod
    def add_expired_older_run(wire):
        older=dict(wire.producer,id=21,head_sha='1'*40)
        expired=dict(wire.metadata,id=900,expired=True,
                     workflow_run=dict(id=21,repository_id=99,head_repository_id=99,head_sha='1'*40))
        wire.responses[PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1']['workflow_runs'].append(older)
        wire.responses[PREFIX+'/actions/runs/21/artifacts?per_page=100&page=1']={'artifacts':[expired]}
        wire.responses[PREFIX+'/actions/artifacts/900']=expired

    def test_C_consumes_current_B_only_without_reading_older_expired_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            h,request,wire,admission,actual,manifest,store,owner,port,build,ecr,execute=self.scenario(tmp,'failure')
            self.add_expired_older_run(wire)
            c=h.commit('C','C');wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':c}}
            req=dict(request,source=c,event_source=c,application=m.application(h.root,c))
            try:
                result=execute(23,req,1)
            except ValueError as error:
                raise AssertionError('C rejected valid current B; REST calls: '+repr(wire.calls)) from error
            self.assertEqual(result['previous']['evidence'],wire.value['manifest_ref'])
            self.assertEqual(result['previous']['revision'],wire.value['revision'])
            self.assertEqual(manifest.requests[0]['VersionId'],'s3-version-B')
            self.assertEqual(port.calls.count('register'),1);build.assert_called_once()
            self.assertEqual(port.routes,('green','blue'))
            self.assertEqual(store.read()[0]['state'],'RELEASED')
            self.assertIn(PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100',wire.calls)
            self.assertFalse(any('/runs/21/' in p or '/artifacts/900' in p for p in wire.calls))

    def test_corrupt_current_B_blocks_C_before_build_without_falling_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            h,request,wire,admission,actual,manifest,store,owner,port,build,ecr,execute=self.scenario(tmp,'failure')
            self.add_expired_older_run(wire);wire.bundle['dsseEnvelope']['signatures'][0]['sig']='altered'
            c=h.commit('C','C');wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':c}}
            req=dict(request,source=c,event_source=c,application=m.application(h.root,c))
            with self.assertRaisesRegex(ValueError,'missing/untrusted'):execute(23,req,1)
            build.assert_not_called();ecr.assert_not_called()
            self.assertEqual(port.calls,[]);self.assertEqual(port.counts,{'blue':1,'green':0})
            self.assertIn(PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100',wire.calls)
            self.assertFalse(any('/runs/21/' in p or '/artifacts/900' in p for p in wire.calls))


if __name__ == '__main__': unittest.main(verbosity=2)
