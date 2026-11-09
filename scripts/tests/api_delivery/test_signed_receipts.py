"""Integrated signed receipt protocol. Only GitHub/AWS/gh transports are fixtures.

No test needs AWS credentials or a deployed resource. Real E2 terminal/head
serialization, real S3 journal, discovery, signature-policy checks and CLI run.
"""
import base64
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
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.api_delivery import aws, cli, model as m, receipts as r
from scripts.api_delivery.github import GitHub
from scripts import environment_mutation as e2
from test_delivery import record, config, MemoryS3
from test_review_regressions import Rest, PREFIX
from test_release_history import ReleaseWire
from test_followup_regressions import GitHistory, ConfigurationTests
from receipt_fixture import Signatures, enrich, origin


class SignedDiscovery(unittest.TestCase):
    @staticmethod
    def sealed_promotion(event='pull_request_target'):
        # Only gh REST/Sigstore transports are replaced. promotion_receipt,
        # get/raw and recursive receipt resolution remain the real code.
        approval=Rest(event);wire=ReleaseWire()
        wire.responses.update(approval.responses);wire.signatures=approval.signatures
        return wire,approval

    @staticmethod
    def resign_deployment(wire,approval,attempt,conclusion,record=None):
        original=approval.receipt['dev'];pub=origin(original['event_source'],22,attempt)
        wire.signatures.sign(r.slot('deployment',22,'dev'),copy.deepcopy(record or original),pub,recovered=True)
        previous=wire.responses[PREFIX+'/actions/runs/22/attempts/1']
        wire.responses[PREFIX+f'/actions/runs/22/attempts/{attempt}']=dict(previous,run_attempt=attempt,conclusion=conclusion)

    def test_sealed_promotion_keeps_attempt_one_after_failed_and_successful_resigning(self):
        for event in ('pull_request_target','workflow_run'):
            wire,approval=self.sealed_promotion(event)
            expected=copy.deepcopy(approval.receipt)
            with patch('subprocess.check_output',side_effect=wire):
                for attempt in (1,2,3):
                    if attempt>1:self.resign_deployment(wire,approval,attempt,'failure' if attempt==2 else 'success')
                    with self.subTest(event=event,stage=attempt):
                        observed,loc=GitHub().promotion_receipt(approval.pull)
                        self.assertEqual(observed,expected)
                        self.assertEqual(observed['dev_receipt'],expected['dev_receipt'])
                        self.assertEqual(observed['dev_receipt']['a'],1)
                        self.assertEqual(loc,dict(check_id=700,**approval.locator))
                self.assertIn(PREFIX+'/actions/runs/22/attempts/1',wire.calls)
                self.assertNotIn(PREFIX+'/actions/runs/22',wire.calls)
                self.assertFalse(any('/artifacts' in path for path in wire.calls))

    def test_unsealed_discovery_still_needs_valid_reconciliation_of_failed_publication(self):
        wire,approval=self.sealed_promotion()
        self.resign_deployment(wire,approval,2,'failure')
        with patch('subprocess.check_output',side_effect=wire):
            with self.assertRaisesRegex(ValueError,'requires authenticated reconciliation'):
                list(GitHub().deployments('dev'))
            self.resign_deployment(wire,approval,3,'success')
            self.assertEqual(list(GitHub().deployments('dev')),[approval.receipt['dev']])

    def test_sealed_promotion_rejects_selected_identity_failure_and_signed_contradiction(self):
        for fault in ('producer','attempt','selected-failed','signature','failed-contradiction','successful-contradiction'):
            with self.subTest(fault=fault):
                wire,approval=self.sealed_promotion()
                self.resign_deployment(wire,approval,2,'failure')
                self.resign_deployment(wire,approval,3,'success')
                original=wire.responses[PREFIX+'/actions/runs/22/attempts/1']
                if fault=='producer':original['workflow_id']=999
                if fault=='attempt':original['run_attempt']=3
                if fault=='selected-failed':original['conclusion']='failure'
                if fault=='signature':
                    path=PREFIX+'/attestations/sha256:'+approval.receipt['dev_receipt']['s']+'?per_page=100'
                    wire.responses[path]['attestations'][0]['bundle']['dsseEnvelope']['signatures'][0]['sig']='altered'
                if fault.endswith('contradiction'):
                    changed=copy.deepcopy(approval.receipt['dev']);changed['image']=record('c')['image']
                    enrich(changed)
                    self.resign_deployment(wire,approval,2 if fault.startswith('failed') else 3,
                                           'failure' if fault.startswith('failed') else 'success',changed)
                with patch('subprocess.check_output',side_effect=wire):
                    with self.assertRaisesRegex(ValueError,'contradictory' if fault.endswith('contradiction') else '.*'):
                        GitHub().promotion_receipt(approval.pull)

    def test_discovery_needs_no_id_attempt_or_hash_and_never_downloads_ZIP(self):
        wire=ReleaseWire()
        # GitHub has already removed every Actions artifact after rerun.
        for path in list(wire.responses):
            if '/artifacts' in path: del wire.responses[path]
        with patch('subprocess.check_output',side_effect=wire):
            found=list(GitHub().deployments('dev'))
        self.assertEqual([(v['run_id'],v['run_attempt']) for v in found],[(22,1)])
        self.assertFalse(any('/artifacts' in p for p in wire.calls))

    def test_docs_noop_and_missing_publication_are_distinct(self):
        wire=ReleaseWire();path=PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100'
        wire.responses[path]['attestations'].clear();wire.latest.update(run_attempt=1,conclusion='success')
        jobs=wire.responses[PREFIX+'/actions/runs/22/attempts/1/jobs?per_page=100&page=1']
        jobs['jobs']=[dict(name='delivery / scope',conclusion='success',steps=[]),
                      dict(name='delivery / delivery',conclusion='skipped',steps=[])]
        with patch('subprocess.check_output',side_effect=wire):
            self.assertEqual(list(GitHub().deployments('dev')),[])
            jobs['jobs'][1].update(conclusion='failure',steps=[dict(name=r.EXECUTE,status='completed',conclusion='success')])
            with self.assertRaisesRegex(ValueError,'pending'):list(GitHub().deployments('dev'))

    def test_empty_subject_real_404_does_not_turn_denial_into_success(self):
        gh=GitHub();descriptor=r.slot('deployment',22,'dev')
        for status,empty in (('404',True),('403',False),('429',False)):
            error=subprocess.CalledProcessError(1,['gh','api'],output=m.canonical({'status':status}))
            with patch('subprocess.check_output',side_effect=error):
                if empty:self.assertEqual(r.bundles(gh,descriptor),[])
                else:
                    with self.assertRaises(subprocess.CalledProcessError):r.bundles(gh,descriptor)

    def test_other_workflow_cannot_self_claim_authorized_publisher(self):
        wire=ReleaseWire();valid=wire.signatures.valid[m.sha(m.canonical(wire.bundle))]
        valid['verificationResult']['signature']['certificate']['buildSignerURI']='https://github.com/'+m.REPOSITORY+'/.github/workflows/evil.yml@refs/heads/develop'
        with patch('subprocess.check_output',side_effect=wire),self.assertRaisesRegex(ValueError,'untrusted'):
            list(GitHub().deployments('dev'))

    def test_reconciler_signed_attempt_is_real_not_original_impersonation(self):
        wire=ReleaseWire();wire.producer['conclusion']='failure'
        # Publication succeeded but its readback failed. A later recovery can
        # publish exactly the same record under its own attempt, not rewrite 1.
        pub=origin(wire.value['event_source'],22,2)
        wire.signatures.deployment(wire.value,recovered=True,pub=pub)
        wire.latest['conclusion']='success'
        with patch('subprocess.check_output',side_effect=wire):
            value,loc=r.resolve(GitHub(),r.slot('deployment',22,'dev'))
        self.assertEqual((value['producer']['attempt'],loc['a']),(1,2))
        # The recovering job rereads exactly its own published signature while
        # running, even if the older failed publisher is still in the slot.
        wire.latest.update(status='in_progress',conclusion=None)
        wire.responses[PREFIX+'/actions/runs/22']=wire.latest
        with patch('subprocess.check_output',side_effect=wire):
            current,_=r.resolve(GitHub(),r.slot('deployment',22,'dev'),loc,completed=False)
        self.assertEqual(current,value)
        wire.latest.update(status='completed',conclusion='success')
        other=copy.deepcopy(wire.value);other['image']=record('c')['image']
        wire.signatures.deployment(other,recovered=True,pub=pub)
        with patch('subprocess.check_output',side_effect=wire),self.assertRaisesRegex(ValueError,'contradictory'):
            r.resolve(GitHub(),r.slot('deployment',22,'dev'))

    def test_finalizer_rejects_truncated_external_id_before_green(self):
        gh=Rest();gh.producer['status']='in_progress';gh.pull['state']='open';gh.check=Mock()
        gh.responses[PREFIX+'/check-runs/700']=dict(gh.check_record,status='in_progress',external_id='truncated')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'evidence').mkdir()
            (path/'promotion-check.json').write_bytes(m.canonical(dict(id=700,head='2'*40,base='1'*40,pr=42)))
            (path/'evidence/result.json').write_bytes(m.canonical(gh.receipt))
            (path/'evidence/slot.json').write_bytes(m.canonical(r.slot('promotion',80,attempt=2)))
            (path/'bundle').write_bytes(m.canonical(gh.bundle))
            env=dict(RECEIPT_BUNDLE=str(path/'bundle'),GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='2',GITHUB_SHA='1'*40,
                     GITHUB_WORKFLOW_SHA='1'*40,GITHUB_EVENT_NAME='pull_request_target',GITHUB_REF='refs/heads/main')
            before=Path.cwd()
            try:
                os.chdir(path)
                with patch.dict(os.environ,env),self.assertRaises(ValueError):cli.finish_promotion(gh,True)
            finally:os.chdir(before)
        self.assertFalse(any(c.args[1]=='success' for c in gh.check.call_args_list))

    def test_optimized_python_preserves_policy_validation(self):
        code="""import sys
sys.path[:0]=['scripts/tests/api_delivery','.']
from unittest.mock import patch
from test_release_history import ReleaseWire
from scripts.api_delivery.github import GitHub
from scripts.api_delivery import model as m
w=ReleaseWire()
w.signatures.valid[m.sha(m.canonical(w.bundle))]['verificationResult']['signature']['certificate']['sourceRepositoryIdentifier']='wrong'
with patch('subprocess.check_output',side_effect=w):
 try: list(GitHub().deployments('dev'))
 except ValueError: print('REJECTED under -O')
 else: raise SystemExit('UNSAFE')
"""
        out=subprocess.check_output([sys.executable,'-O','-B','-c',code],cwd=ROOT)
        self.assertIn(b'REJECTED under -O',out)

    def test_discovery_and_promotion_follow_real_git_B_C_Bprime_not_tree_only(self):
        with tempfile.TemporaryDirectory() as temp:
            history=GitHistory(temp);base=history.shas['A'];b=history.commit('B','B');history.commit('C','C');bp=history.commit('Bprime','B')
            wire=ReleaseWire();wire.value.update(source=b,event_source=b,application=m.application(history.root,b),producer=origin(b));wire.producer['head_sha']=wire.latest['head_sha']=b;wire.pack()
            pull=Rest().pull;pull.update(state='open',draft=False);pull['head']['sha']=bp;pull['base']['sha']=base
            wire.responses.update({PREFIX+'/pulls/42':pull,PREFIX+'/rules/branches/main':[{'type':'pull_request','parameters':{'allowed_merge_methods':['merge']}}]})
            path=Path(temp);(path/'event').write_bytes(m.canonical({'pull_request':{'number':42}}))
            env=dict(GITHUB_EVENT_PATH=str(path/'event'),GITHUB_EVENT_NAME='pull_request_target',GITHUB_SHA=base,
                     GITHUB_WORKFLOW_SHA=base,GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.PROMOTION+'@refs/heads/main',GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='1')
            previous=Path.cwd()
            try:
                os.chdir(path)
                with patch.dict(os.environ,env),patch.object(cli,'ROOT',path),patch('subprocess.check_output',side_effect=wire),patch.object(GitHub,'check',return_value={'id':700}):
                    with self.assertRaisesRegex(ValueError,'no successful DEV'):cli.promotion(GitHub(),path/'result')
                    newer=enrich(record('d'));newer.update(source=bp,event_source=bp,application=m.application(path,bp),run_id=23,producer=origin(bp,23))
                    newer.pop('operation')
                    sig=Signatures();sig.deployment(newer);wire.signatures.valid.update(sig.valid);wire.responses.update(sig.responses)
                    # New Bprime, different OCI digest, followed by old B.
                    wire.responses[PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1']['workflow_runs'].append(wire.latest)
                    cli.promotion(GitHub(),path/'result')
                result=json.loads((path/'result').read_bytes())
                self.assertEqual((result['dev']['source'],result['dev']['image']),(bp,record('d')['image']))
            finally:os.chdir(previous)


class VersionedS3(MemoryS3):
    """Real journal/E2 wire shapes, isolated buckets and explicit version history."""
    def __init__(self,cfg):super().__init__();self.cfg=cfg;self.versions={};self.markers=[];self.calls=[]
    def put_object(self,**kw):
        key=kw['Key'];self.calls.append(('put',key))
        result=super().put_object(**{k:v for k,v in kw.items() if k in ('Bucket','Key','Body','ContentType','IfNoneMatch','IfMatch')})
        raw,version=self.objects[key];self.versions[(key,str(version))]=(raw,kw)
        return {'VersionId':str(version)}
    def get_object(self,**kw):
        key=kw['Key'];self.calls.append(('get',key,kw.get('VersionId')))
        if 'VersionId' not in kw:return super().get_object(Bucket=kw['Bucket'],Key=key)
        raw,metadata=self.versions[(key,kw['VersionId'])]
        return dict(Body=io.BytesIO(raw),VersionId=kw['VersionId'],ServerSideEncryption='aws:kms',
                    SSEKMSKeyId=self.cfg['evidence_kms_key'],BucketKeyEnabled=False)
    def list_object_versions(self,**kw):
        self.calls.append(('versions',kw['Prefix']))
        return dict(IsTruncated=False,Versions=[{'Key':k,'VersionId':v} for k,v in self.versions if k.startswith(kw['Prefix'])],DeleteMarkers=self.markers)


class RecoveryTests(unittest.TestCase):
    def scenario(self,temp):
        runtime,value,configuration,actual=ConfigurationTests().setup_port()
        cfg=runtime.config;s3=VersionedS3(cfg);store=e2.Store(s3,cfg['evidence_bucket'],'dev');store.initialize()
        request=dict(environment='dev',source=value['source'],event_source=value['source'],application=value['application'],operation='deploy')
        operation=str(uuid.uuid5(uuid.NAMESPACE_URL,m.REPOSITORY+'/dev/22'))
        owner=e2.Authority(store,'normal-delivery/deploy-dev',operation,request);owner.acquire()
        value=enrich(value);value.update(operation=operation,request_sha256=m.sha(e2.canonical(request)))
        value.pop('manifest_ref')
        journal=aws.Runtime(dict(s3=s3,ecs=None,elbv2=None),cfg,owner,operation,temp)
        reference=journal.journal('release',value);owner.finish(True,'SUCCESS')
        # Exactly the crash boundary: no GitHub receipt, no VersionId/hash input.
        wire=ReleaseWire(dict(value,manifest_ref=reference));wire.producer['conclusion']='failure'
        wire.job['steps'][0]['conclusion']='failure' # lost output after E2/S3 success
        wire.responses[PREFIX+'/attestations/sha256:'+wire.locator['s']+'?per_page=100']['attestations'].clear()
        reloaded=e2.Authority(store,'normal-delivery/deploy-dev',operation,request)
        runtime.current_configuration=Mock(return_value=configuration['task'])
        clients=dict(s3=s3,ecs=type('ECS',(),{'describe_task_definition':Mock(return_value={'taskDefinition':actual})})())
        return cfg,s3,store,request,operation,value,reference,wire,reloaded,runtime,clients

    def test_cli_recovery_from_zero_references_actual_E2_S3_and_new_signer_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg,s3,store,request,op,value,ref,wire,owner,runtime,clients=self.scenario(temp)
            path=Path(temp);(path/'request').write_bytes(m.canonical(request));before=copy.deepcopy(s3.objects);s3.calls.clear()
            env=dict(API_CD_ENABLED='true',API_BINDING_REF=json.dumps({'region':cfg['region'],'sha256':'a'*64}),
                GITHUB_EVENT_NAME='push',GITHUB_RUN_ID='22',GITHUB_RUN_ATTEMPT='2',GITHUB_SHA=value['event_source'],
                GITHUB_WORKFLOW_SHA=value['event_source'],GITHUB_REF='refs/heads/develop',GITHUB_OUTPUT=str(path/'out'))
            with patch.dict(os.environ,env),patch('subprocess.check_output',side_effect=wire),patch.object(aws,'clients',return_value=clients),\
                 patch.object(aws,'binding',return_value=cfg),patch.object(aws,'owner',return_value=owner),\
                 patch.object(aws,'Runtime',return_value=runtime),patch.object(aws,'verify_image') as ecr_read,patch.object(aws,'publish') as build:
                cli.execute(GitHub(),path/'request',path/'result.json')
                r.prepare_files(path/'result.json','deployment',True)
            recovered=json.loads((path/'result.json').read_bytes());predicate=json.loads((path/'predicate.json').read_bytes())
            self.assertEqual(recovered['manifest_ref'],ref)
            self.assertEqual((predicate['publisher']['attempt'],predicate['record']['producer']['attempt']),(2,1))
            self.assertTrue(predicate['recovered']);self.assertEqual(s3.objects,before)
            build.assert_not_called();runtime.journal.assert_not_called()
            self.assertFalse(any(c[0]=='put' for c in s3.calls));self.assertEqual(ecr_read.call_count,1)
            self.assertEqual(store.read()[0]['state'],'RELEASED')
            self.assertFalse(any('/attestations/' in p for p in wire.calls))

    def test_noop_SUCCESS_held_displaced_multiple_deleted_wrong_producer_block(self):
        for fault in ('no-release','held','displaced','versions','delete','request','producer','unverified-step','bytes'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                cfg,s3,store,request,op,value,ref,wire,owner,runtime,clients=self.scenario(temp)
                key=ref['key'];version=ref['version']
                if fault=='no-release':del s3.versions[(key,version)]
                if fault in ('held','displaced'):
                    other=e2.Authority(store,'normal-delivery/deploy-dev','22222222-2222-2222-2222-222222222222',{})
                    other.acquire()
                    if fault=='displaced':other.finish(True,'SUCCESS')
                if fault=='versions':s3.versions[(key,'extra')]=s3.versions[(key,version)]
                if fault=='delete':s3.markers=[dict(Key=key,VersionId='deleted')]
                if fault=='producer':wire.producer['head_sha']='9'*40
                if fault=='unverified-step':wire.job['steps'][0]['conclusion']='skipped'
                if fault=='request':
                    changed=dict(value,request_sha256='0'*64);s3.versions[(key,version)]=(m.canonical(changed),{})
                if fault=='bytes':s3.versions[(key,version)]=(m.canonical(value)+b' ',{})
                before=copy.deepcopy(s3.objects);s3.calls.clear()
                with patch.dict(os.environ,GITHUB_RUN_ID='22',GITHUB_RUN_ATTEMPT='2'),patch('subprocess.check_output',side_effect=wire),\
                     patch.object(aws,'publish') as build,patch.object(aws,'Runtime') as rt,patch.object(aws,'verify_image') as er:
                    with self.assertRaises((ValueError,e2.CoordinationError)):
                        aws.recover_release(GitHub(),clients,cfg,owner,op,request)
                build.assert_not_called();rt.assert_not_called();er.assert_not_called()
                self.assertEqual(s3.objects,before);self.assertFalse(any(c[0]=='put' for c in s3.calls))


if __name__=='__main__':unittest.main(verbosity=2)
