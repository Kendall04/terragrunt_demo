"""Idempotent omission receipts and positive under-E2 recovery (offline ports)."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.api_delivery import cli, model as m, receipts as r
from scripts.api_delivery.github import GitHub
from scripts import environment_mutation as e2
from test_receipt_recovery_flow import Flow, step, PREFIX
from test_delivery import record
from receipt_fixture import origin, enrich


def finish(f, number, attempt, outcome='success', execute='success', signed='success'):
    runs=f.wire.responses[PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1']['workflow_runs']
    latest=next(row for row in runs if row['id']==number)
    current=dict(latest,run_attempt=attempt,status='completed',conclusion=outcome)
    latest.update(current)
    f.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/{attempt}']=copy.deepcopy(current)
    f.wire.responses[f'{PREFIX}/actions/runs/{number}/attempts/{attempt}/jobs?per_page=100&page=1']={'jobs':[
        dict(name='delivery / delivery',status='completed',conclusion=outcome,
             steps=[step(r.EXECUTE,execute),step(r.SIGN,signed)])]}


def sign(f, value, outcome='success'):
    number,attempt=value['run_id'],value['run_attempt']
    finish(f,number,attempt,outcome)
    descriptor=r.slot('deployment',number,'dev')
    bundle,locator=f.wire.signatures.sign(descriptor,value,origin(value['event_source'],number,attempt))
    f.wire.responses[f.slot_path(number)]=f.wire.signatures.responses[f.slot_path(number)]
    return bundle,locator


def advance(f):
    d=f.git.commit('D','D')
    f.requests[24]=dict(f.requests[23],source=d,event_source=d,application=m.application(f.root,d))
    f.wire.responses[PREFIX+'/git/ref/heads/develop']={'object':{'sha':d}}
    f.add_run(24,'queued',source=d)
    return d


class SupersededRetries(unittest.TestCase):
    def verify_D(self,f,generation):
        self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))
        f.publish_image=record('d')['image']
        value=f.execute(24,1)
        self.assertEqual(value['source'],f.requests[24]['source'])
        self.assertEqual(value['image'],record('d')['image'])
        self.assertEqual(f.counters(),dict(build=1,ecr_write=1,ecs=3))
        self.assertEqual(f.port.calls.count('register'),1)
        head=f.store.read()[0]
        self.assertEqual((head['state'],head['operation'],head['generation']),('RELEASED',f.owner(24).operation,generation))
        self.assertEqual(f.owner(24).retained()['status'],'SUCCESS')
        self.assertEqual(f.port.revisions[f.port.routes[0]],value['revision'])
        self.assertEqual(f.port.counts,dict(blue=0,green=1))
        print('SUPERSEDED_RETRY '+json.dumps(dict(E2=head,served_revision=value['revision'],
            B_reconciliation=dict(build=0,ecr_write=0,ecs=0),C_total=dict(build=0,ecr_write=0,ecs=0),D=f.counters()),sort_keys=True))

    def test_before_E2_two_signed_attempts_preserve_B_recovery_and_D_once(self):
        for outcome in ('success','failure'):
            with self.subTest(first_publisher=outcome),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);head=copy.deepcopy(f.store.read());f.c();advance(f)
                first=f.execute(23,1);_,one=sign(f,first,outcome)
                second=f.execute(23,2);_,two=sign(f,second)
                with patch('subprocess.check_output',side_effect=f.wire):
                    value,_=r.resolve(GitHub(),r.slot('deployment',23,'dev'))
                    self.assertEqual(value['reason'],'superseded')
                    for receipt in (one,two):
                        selected,_=r.resolve(GitHub(),r.slot('deployment',23,'dev'),receipt)
                        self.assertEqual(selected['run_attempt'],receipt['a'])
                    # The finalizer also sees the earlier failed/successful
                    # signature while authenticating its own in-progress run.
                    current=dict(f.wire.responses[PREFIX+'/actions/runs/23/attempts/2'],status='in_progress',conclusion=None)
                    f.wire.responses[PREFIX+'/actions/runs/23']=current
                    self.assertEqual(r.resolve(GitHub(),r.slot('deployment',23,'dev'),two,completed=False)[0],second)
                for attempt in (1,2):
                    self.assertIn(f'{PREFIX}/actions/runs/23/attempts/{attempt}',f.wire.calls)
                    self.assertIn(f'{PREFIX}/actions/runs/23/attempts/{attempt}/jobs?per_page=100&page=1',f.wire.calls)
                self.assertEqual(f.store.read(),head)
                self.assertIsNone(f.owner(23).retained())
                f.sign_recovery(f.execute(22,2))
                self.assertEqual(f.store.read(),head)
                self.verify_D(f,2)

    def under_E2(self,f):
        f.sign_recovery(f.execute(22,2));f.c()
        current=cli.current_request
        def move(gh,request):
            if f.store.read()[0]['state']=='ACTIVE':advance(f)
            return current(gh,request)
        with patch.object(cli,'current_request',side_effect=move):value=f.execute(23,1)
        finish(f,23,1,'failure',signed='failure')
        return value

    def test_under_E2_omission_recovers_positive_decision_before_first_signature(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Flow(temp);first=self.under_E2(f);head=copy.deepcopy(f.store.read())
            self.assertEqual(first['reason'],'superseded')
            self.assertEqual(f.owner(23).retained()['status'],'SUCCESS')
            self.assertEqual(f.wire.responses[f.slot_path(23)]['attestations'],[])
            key=f'api-delivery/dev/operations/{f.owner(23).operation}/release.json'
            versions=[(version,item) for version,item in f.s3.versions.items() if version[0]==key]
            self.assertEqual(len(versions),1)
            (key,version),(raw,_)=versions[0]
            decision=json.loads(raw)
            self.assertEqual(decision['schema'],'API_SUPERSEDED_DECISION_V1')
            self.assertEqual(decision['phase'],'before-application-effects')
            self.assertEqual((decision['producer']['run'],decision['producer']['attempt']),(23,1))
            f.s3.calls.clear();original=copy.deepcopy(f.s3.objects)
            recovered=f.execute(23,2)
            self.assertEqual(recovered['reason'],'superseded')
            self.assertEqual(f.store.read(),head)
            self.assertEqual(f.s3.objects,original)
            self.assertFalse(any(call[0]=='put' for call in f.s3.calls))
            self.assertIn(('get',key,version),f.s3.calls)
            _,locator=sign(f,recovered)
            with patch('subprocess.check_output',side_effect=f.wire):
                self.assertEqual(r.resolve(GitHub(),r.slot('deployment',23,'dev'),locator)[0],recovered)
            self.verify_D(f,3)

    def test_conflicting_or_foreign_omission_receipts_never_authorize_history(self):
        for fault in ('foreign','attempt','execute','sign','contradiction','deployment'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);f.c();advance(f);value=f.execute(23,1)
                bundle,locator=sign(f,value)
                if fault=='foreign':
                    f.wire.signatures.valid[m.sha(m.canonical(bundle))]['verificationResult']['signature']['certificate']['buildSignerURI']='https://github.com/other/repo/evil.yml'
                if fault=='attempt':f.wire.responses[PREFIX+'/actions/runs/23/attempts/1']['run_attempt']=9
                if fault in ('execute','sign'):
                    jobs=f.wire.responses[PREFIX+'/actions/runs/23/attempts/1/jobs?per_page=100&page=1']['jobs']
                    jobs[0]['steps'][0 if fault=='execute' else 1]['conclusion']='failure'
                if fault=='contradiction':
                    other=dict(value,event_source='f'*40)
                    sign(f,other)
                if fault=='deployment':
                    release=record('c');release.update(run_id=23,source=value['event_source'],event_source=value['event_source'])
                    release.pop('producer',None);release.pop('operation',None);enrich(release)
                    f.wire.signatures.sign(r.slot('deployment',23,'dev'),release,origin(value['event_source'],23,1))
                with patch('subprocess.check_output',side_effect=f.wire):
                    for sealed in (None,locator):
                        with self.assertRaises(ValueError):r.resolve(GitHub(),r.slot('deployment',23,'dev'),sealed)
                self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))

    def test_under_E2_missing_contradictory_foreign_or_uncertain_decision_blocks(self):
        for fault in ('absent','producer','content','held','uncertain','execute','versions','delete','generation','phase'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=Flow(temp);self.under_E2(f)
                key=f'api-delivery/dev/operations/{f.owner(23).operation}/release.json'
                if fault=='absent':
                    for version in list(f.s3.versions):
                        if version[0]==key:del f.s3.versions[version]
                if fault=='producer':f.wire.responses[PREFIX+'/actions/runs/23/attempts/1']['workflow_id']=999
                if fault=='execute':
                    f.wire.responses[PREFIX+'/actions/runs/23/attempts/1/jobs?per_page=100&page=1']['jobs'][0]['steps'][0]['conclusion']='failure'
                if fault=='delete':f.s3.markers=[dict(Key=key,VersionId='deleted')]
                if fault=='versions':
                    original=next(item for version,item in f.s3.versions.items() if version[0]==key)
                    f.s3.versions[(key,'extra')]=original
                if fault in ('content','generation','phase'):
                    for version,item in f.s3.versions.items():
                        if version[0]==key:
                            # Preserve transport encoding and encryption, change the authenticated decision.
                            value=json.loads(item[0])
                            field,changed={'content':('request_sha256','0'*64),'generation':('generation',99),
                                           'phase':('phase','after-effects')}[fault]
                            value[field]=changed
                            f.s3.versions[version]=(m.canonical(value),item[1])
                if fault in ('held','uncertain'):
                    f.requests[25]=f.requests[23];owner=f.owner(25);owner.acquire()
                    if fault=='uncertain':owner.call(lambda:None);owner.finish(False,'UNCERTAIN')
                head=copy.deepcopy(f.store.read())
                with self.assertRaises((ValueError,e2.CoordinationError)):f.execute(23,2)
                self.assertEqual(f.store.read(),head)
                self.assertEqual(f.counters(),dict(build=0,ecr_write=0,ecs=0))


if __name__=='__main__':unittest.main(verbosity=2)
