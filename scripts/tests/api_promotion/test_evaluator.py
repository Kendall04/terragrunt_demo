"""Evaluator bootstrap boundaries; real receipt/REST logic, offline transports."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.api_delivery import cli, model as m, receipts as r, workflow_contract
from scripts.api_delivery.github import GitHub
from evaluator_fixture import Rest, Wire, PREFIX
spec=importlib.util.spec_from_file_location('bootstrap_e1_contract',ROOT/'scripts/tests/final_acceptance/contract.py')
e1=importlib.util.module_from_spec(spec)
spec.loader.exec_module(e1)


class EvaluatorBoundaries(unittest.TestCase):
    def test_substituted_certificate_workflow_SHA_ref_run_and_repository_rejected(self):
        changes={'buildConfigURI':'https://github.com/'+m.REPOSITORY+'/.github/workflows/evil.yml@refs/heads/main',
                 'buildSignerURI':'https://github.com/'+m.REPOSITORY+'/.github/workflows/evil.yml@refs/heads/main',
                 'buildConfigDigest':'9'*40,'buildSignerDigest':'9'*40,'sourceRepositoryDigest':'9'*40,
                 'sourceRepositoryRef':'refs/heads/develop','sourceRepositoryIdentifier':'99',
                 'sourceRepositoryOwnerIdentifier':'99','buildTrigger':'push',
                 'runInvocationURI':'https://github.com/'+m.REPOSITORY+'/actions/runs/80/attempts/3',
                 'issuer':'https://example.invalid','runnerEnvironment':'self-hosted'}
        for field,value in changes.items():
            f=Rest()
            f.signatures.valid[m.sha(m.canonical(f.bundle))]['verificationResult']['signature']['certificate'][field]=value
            with self.subTest(field=field),patch('subprocess.check_output',side_effect=Wire(f)):
                with self.assertRaisesRegex(ValueError,'signed workflow identity'):
                    r.cryptographic_verify(GitHub(),f.bundle,r.slot('promotion',80,attempt=2),
                                           json.loads(r.payload(f.bundle))['predicate']['publisher'])
                with self.assertRaisesRegex(ValueError,'missing/untrusted'):
                    GitHub().promotion_artifact(f.locator)

    def test_altered_statement_signature_and_localizer_are_rejected(self):
        for fault in ('statement','signature','locator','missing'):
            f=Rest()
            if fault=='statement':f.bundle['dsseEnvelope']['payload']='e30='
            if fault=='signature':f.bundle['dsseEnvelope']['signatures'][0]['sig']='altered'
            if fault=='locator':f.locator=dict(f.locator,h='9'*64)
            if fault=='missing':
                f.responses[PREFIX+'/attestations/sha256:'+f.locator['s']+'?per_page=100']['attestations'].clear()
            with self.subTest(fault=fault),patch('subprocess.check_output',side_effect=Wire(f)):
                with self.assertRaises((ValueError,subprocess.CalledProcessError)):
                    GitHub().promotion_artifact(f.locator)

    def test_sealed_attempt_survives_later_running_attempt(self):
        for event in ('pull_request_target','workflow_run'):
            f=Rest(event);wire=Wire(f)
            f.producer.update(run_attempt=3,status='in_progress',conclusion=None)
            with patch('subprocess.check_output',side_effect=wire):
                record,locator=GitHub().promotion_receipt(f.pull)
            self.assertEqual(record,f.receipt)
            self.assertEqual((locator['r'],locator['a']),(80,2))
            self.assertIn(PREFIX+'/actions/runs/80/attempts/2',wire.calls)
            self.assertNotIn(PREFIX+'/actions/runs/80',wire.calls)
            self.assertFalse(any('/artifacts/' in path for path in wire.calls))

    def test_previous_check_must_be_successful_before_merge(self):
        for fault in ('failure','cancelled','after-merge','wrong-head'):
            f=Rest()
            if fault in ('failure','cancelled'):f.check_record['conclusion']=fault
            if fault=='after-merge':f.check_record['completed_at']='2026-11-08T20:11:00Z'
            if fault=='wrong-head':f.check_record['head_sha']='9'*40
            with self.subTest(fault=fault),patch('subprocess.check_output',side_effect=Wire(f)):
                with self.assertRaises(ValueError):GitHub().promotion_receipt(f.pull)

    def test_PROD_keeps_approved_B_when_DEV_has_advanced_to_C(self):
        f=Rest();wire=Wire(f);f.pull.update(merge_commit_sha='4'*40)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'event').write_bytes(m.canonical({'before':'1'*40}))
            env=dict(GITHUB_EVENT_NAME='push',GITHUB_REF_NAME='main',GITHUB_EVENT_PATH=str(path/'event'),
                     GITHUB_SHA='4'*40,GITHUB_REPOSITORY=m.REPOSITORY,GITHUB_OUTPUT=str(path/'outputs'),
                     GITHUB_WORKFLOW_REF=m.REPOSITORY+'/'+m.DELIVERY+'@refs/heads/main')
            gh=GitHub()
            with patch.dict(os.environ,env),patch('subprocess.check_output',side_effect=wire),\
                 patch.object(gh,'wait_checks'),patch.object(m,'application',side_effect=['b'*64,'a'*64]),\
                 patch.object(m,'git',return_value=('1'*40+' '+'2'*40).encode()):
                cli.prepare(gh,path/'request')
            request=json.loads((path/'request').read_bytes())
        self.assertEqual(request['approved']['image'],f.receipt['dev']['image'])
        self.assertEqual(request['approval']['a'],2)
        self.assertFalse(any('/workflows/api-delivery.yml/runs' in p for p in wire.calls))

    def test_pending_publication_cannot_be_treated_as_omitted_deployment(self):
        f=Rest();dev=f.receipt['dev']
        descriptor=r.slot('deployment',22,'dev')
        f.responses[PREFIX+'/attestations/sha256:'+m.sha(m.canonical(descriptor))+'?per_page=100']['attestations'].clear()
        f.responses[PREFIX+'/actions/runs/22']=f.responses[PREFIX+'/actions/runs/22/attempts/1']
        f.responses[PREFIX+'/actions/runs/22/attempts/1/jobs?per_page=100&page=1']['jobs'][0]['conclusion']='success'
        with patch('subprocess.check_output',side_effect=Wire(f)):
            with self.assertRaisesRegex(ValueError,'pending'):
                list(GitHub().deployments('dev'))

    def test_finalizer_reads_published_attestation_and_exact_locator_before_green(self):
        for tamper in (False,True):
            f=Rest();f.producer.update(status='in_progress',conclusion=None);f.pull.update(state='open',merged=False)
            f.check_record.update(status='in_progress',conclusion=None);wire=Wire(f);writes=[]
            def transport(argv,**kwargs):
                if argv[:4]==['gh','api','-X','PATCH']:
                    self.assertEqual(argv[4],PREFIX+'/check-runs/700')
                    body=json.loads(kwargs['input']);writes.append(copy.deepcopy(body))
                    f.check_record.update(body)
                    if tamper and body.get('status')=='in_progress':f.check_record['external_id']='truncated'
                    return m.canonical(f.check_record)
                return wire(argv,**kwargs)
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);(path/'evidence').mkdir()
                (path/'promotion-check.json').write_bytes(m.canonical(dict(id=700,head='2'*40,base='1'*40,pr=42)))
                (path/'evidence/result.json').write_bytes(m.canonical(f.receipt))
                (path/'evidence/slot.json').write_bytes(m.canonical(r.slot('promotion',80,attempt=2)))
                (path/'bundle.json').write_bytes(m.canonical(f.bundle))
                env=dict(GITHUB_RUN_ID='80',GITHUB_RUN_ATTEMPT='2',GITHUB_SHA='1'*40,GITHUB_WORKFLOW_SHA='1'*40,
                         GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='pull_request_target',RECEIPT_BUNDLE=str(path/'bundle.json'))
                before=Path.cwd()
                try:
                    os.chdir(path)
                    with patch.dict(os.environ,env),patch('subprocess.check_output',side_effect=transport),self.subTest(tamper=tamper):
                        if tamper:
                            with self.assertRaises(ValueError):cli.finish_promotion(GitHub(),True)
                        else:cli.finish_promotion(GitHub(),True)
                finally:os.chdir(before)
            self.assertEqual(writes[-1]['conclusion'],'failure' if tamper else 'success')
            if not tamper:
                self.assertIn(PREFIX+'/attestations/sha256:'+f.locator['s']+'?per_page=100',wire.calls)

    def test_E1_admits_only_exact_promotion_workflows(self):
        self.assertEqual(e1.promotion_workflows(ROOT),{'api-promotion.yml','api-evaluate.yml'})
        self.assertEqual(set(workflow_contract.EXPECTED),{'api-promotion.yml','api-evaluate.yml','api-delivery.yml','api-execute.yml'})
        for name in ('api-promotion.yml','api-evaluate.yml'):
            for fault in ('permissions','environment','action','checkout','AWS'):
                with tempfile.TemporaryDirectory() as tmp:
                    target=Path(tmp);folder=target/'.github/workflows';folder.mkdir(parents=True)
                    for admitted in ('api-promotion.yml','api-evaluate.yml'):
                        (folder/admitted).write_bytes((ROOT/'.github/workflows'/admitted).read_bytes())
                    doc=json.loads((folder/name).read_bytes());job=doc['jobs']['promotion']
                    if fault=='permissions':job['permissions']['contents']='write'
                    if fault=='environment':job['environment']='api-prod'
                    if fault=='AWS':job['env']={'AWS_ROLE_ARN':'fixture'}
                    if fault=='action':job['uses']='./.github/workflows/unreviewed.yml'
                    if fault=='checkout':job['steps']=[{'uses':'actions/checkout@unreviewed','with':{'ref':'\x24{{ github.event.pull_request.head.sha }}'}}]
                    (folder/name).write_bytes(m.canonical(doc))
                    with self.subTest(workflow=name,fault=fault),self.assertRaisesRegex(ValueError,'workflow invocation drift'):
                        e1.promotion_workflows(target)

    def test_main_policy_is_fail_closed_until_merge_only_is_installed(self):
        f=Rest();wire=Wire(f)
        f.responses[PREFIX+'/rules/branches/main'][1]['parameters']['allowed_merge_methods']=['merge','squash','rebase']
        with patch('subprocess.check_output',side_effect=wire):
            with self.assertRaisesRegex(ValueError,'merge-only'):GitHub().require_merge_policy()
