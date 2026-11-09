"""Historical PRT association: real readers, only gh/crypto transports replaced.

GitHub trial 42574195759/1 retained run.head_sha but updated the nested PR SHA.
No AWS authority, fresh signatures or GitHub mutations are needed for replay.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.api_delivery import cli, model as m, receipts as r
from scripts.api_delivery.github import GitHub
from evaluator_fixture import Rest, PREFIX, Wire


class HistoricalPRTarget(unittest.TestCase):
    def read(self, fixture, completed=True):
        wire=Wire(fixture)
        with patch('subprocess.check_output',side_effect=wire):
            result=GitHub().promotion_artifact(fixture.locator,completed)
        self.assertIn(PREFIX+'/check-runs/700',wire.calls)
        self.assertIn(PREFIX+('/actions/runs/80/attempts/2' if completed else '/actions/runs/80'),wire.calls)
        return result

    def test_nested_SHA_drift_does_not_revoke_exact_historical_approval(self):
        for run_head in ('1'*40,'2'*40):
            f=Rest();f.producer['head_sha']=run_head
            f.producer['pull_requests'][0]['head']['sha']='3'*40
            f.producer['pull_requests'][0]['base']['sha']='4'*40
            with self.subTest(run_head=run_head):self.assertEqual(self.read(f),f.receipt)

    def test_PR_number_branches_and_both_repository_IDs_are_still_required(self):
        for fault in ('number','head-ref','base-ref','head-repo','base-repo','missing-repo','run-head'):
            f=Rest();nested=f.producer['pull_requests'][0]
            if fault=='number':nested['number']=43
            if fault=='head-ref':nested['head']['ref']='feature/foreign'
            if fault=='base-ref':nested['base']['ref']='develop'
            if fault=='head-repo':nested['head']['repo']['id']=99
            if fault=='base-repo':nested['base']['repo']['id']=99
            if fault=='missing-repo':nested['head']['repo'].pop('id')
            if fault=='run-head':f.producer['head_sha']='9'*40
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'PR event identity'):
                self.read(f)

    def test_exact_check_independently_binds_head_even_when_run_reports_base(self):
        for fault in ('id','name','app','head','locator-h','locator-r','locator-a','locator-w','locator-s',
                      'failed','cancelled','in-progress'):
            f=Rest();f.producer['head_sha']=f.receipt['base'];check=f.check_record
            if fault=='id':check['id']=701
            if fault=='name':check['name']='Different validation'
            if fault=='app':check['app']['id']=123
            if fault=='head':check['head_sha']='3'*40
            if fault.startswith('locator-'):
                key=fault[-1];bad=dict(f.locator);bad[key]=999 if key in ('r','a') else '0'*len(bad[key])
                check['external_id']=json.dumps(bad)
            if fault in ('failed','cancelled'):check['conclusion']='failure' if fault=='failed' else 'cancelled'
            if fault=='in-progress':check.update(status='in_progress',conclusion=None)
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'promotion check'):
                self.read(f)

    def test_finalizing_check_is_in_progress_not_yet_successful(self):
        f=Rest();f.producer.update(status='in_progress',conclusion=None)
        f.check_record.update(status='in_progress',conclusion=None)
        self.assertEqual(self.read(f,completed=False),f.receipt)
        f.check_record.update(status='completed',conclusion='success')
        with self.assertRaisesRegex(ValueError,'promotion check'):self.read(f,completed=False)

    def test_run_attempt_certificate_and_sealed_base_remain_authenticated(self):
        for fault in ('attempt','workflow','signed-base'):
            f=Rest()
            if fault=='attempt':f.producer['run_attempt']=3
            if fault=='workflow':f.producer['workflow_id']=9
            if fault=='signed-base':
                verified=f.signatures.valid[m.sha(m.canonical(f.bundle))]['verificationResult']
                verified['signature']['certificate']['sourceRepositoryDigest']='9'*40
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.read(f)

    def test_new_head_and_wrong_merge_parents_cannot_use_historical_approval(self):
        f=Rest();f.producer['pull_requests'][0]['head']['sha']='3'*40
        receipt=self.read(f)
        for fault in ('head','first-parent','second-parent','parent-order'):
            pr=copy.deepcopy(f.pull);parents=[receipt['base'],receipt['head']]
            if fault=='head':pr['head']['sha']='3'*40;parents[1]='3'*40
            if fault=='first-parent':parents[0]='9'*40
            if fault=='second-parent':parents[1]='3'*40
            if fault=='parent-order':parents.reverse()
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'exact merged PR'):
                m.promoted(pr,parents,receipt['application'],receipt)
        self.assertEqual(m.promoted(f.pull,[receipt['base'],receipt['head']],receipt['application'],receipt),receipt['dev'])

    def test_workflow_run_control_still_authenticates_its_DEV_attempt(self):
        f=Rest('workflow_run');wire=Wire(f)
        with patch('subprocess.check_output',side_effect=wire):
            self.assertEqual(GitHub().promotion_artifact(f.locator),f.receipt)
        self.assertIn(PREFIX+'/actions/runs/22/attempts/1',wire.calls)

    def test_issuer_rejects_stale_event_before_creating_a_check(self):
        for fault in ('head','base','head-repo','base-repo','head-ref','base-ref'):
            f=Rest();f.pull.update(state='open',merged=False);event=copy.deepcopy(f.pull)
            if fault in ('head','base'):event[fault]['sha']='9'*40
            if fault in ('head-repo','base-repo'):event[fault.split('-')[0]]['repo']['id']=99
            if fault in ('head-ref','base-ref'):event[fault.split('-')[0]]['ref']='foreign'
            wire=Wire(f)
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);(path/'event').write_bytes(m.canonical({'pull_request':event}))
                env=dict(GITHUB_EVENT_NAME='pull_request_target',GITHUB_EVENT_PATH=str(path/'event'),GITHUB_SHA='1'*40)
                with patch.dict(os.environ,env),patch('subprocess.check_output',side_effect=wire),\
                     patch.object(GitHub,'check') as create, self.subTest(fault=fault):
                    with self.assertRaisesRegex(ValueError,'PR event changed'):
                        cli.promotion(GitHub(),path/'result.json')
                    create.assert_not_called()

    def test_finalizer_never_marks_changed_PR_green(self):
        for fault in ('head','base','head-repo','base-repo','head-ref','base-ref','closed'):
            f=Rest();f.pull.update(state='open',merged=False)
            if fault in ('head','base'):f.pull[fault]['sha']='9'*40
            if fault in ('head-repo','base-repo'):f.pull[fault.split('-')[0]]['repo']['id']=99
            if fault in ('head-ref','base-ref'):f.pull[fault.split('-')[0]]['ref']='foreign'
            if fault=='closed':f.pull['state']='closed'
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);(path/'promotion-check.json').write_bytes(m.canonical(dict(id=700,head='2'*40,base='1'*40,pr=42)))
                before=Path.cwd()
                try:
                    os.chdir(path)
                    with patch.object(f,'check') as check,self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'promotion check failed'):
                        cli.finish_promotion(f,True)
                    self.assertFalse(any(call.args[1]=='success' for call in check.call_args_list))
                finally:os.chdir(before)
