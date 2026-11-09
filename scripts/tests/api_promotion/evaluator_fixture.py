"""Promotion-only transport fixtures extracted from reviewed develop tests.

Record, PR, run, Rest and Wire retain their reviewed behavior; AWS executor/config
fixtures are replaced by the sole repository string and synthetic rule they use.
This file never mocks the production reader or signature-policy comparisons.
"""
import copy
import io
import json
from types import SimpleNamespace
import zipfile
from scripts.api_delivery import model as m, receipts as r
from scripts.api_delivery.github import GitHub
from receipt_fixture import Signatures, enrich, origin

ACCOUNT='123456789012'
REGION='us-east-1'
PREFIX='repos/'+m.REPOSITORY
permissions=SimpleNamespace(PROMOTION_RULE={
    'type':'required_status_checks',
    'parameters':{'strict_required_status_checks_policy':True,
                  'required_status_checks':[{'context':'API Promotion Validation','integration_id':15368}]}})
def config():
    return {'repository':ACCOUNT+'.dkr.ecr.us-east-1.amazonaws.com/api'}

def record(letter='b', env='dev', source='2'):
    value = dict(schema='API_RELEASE_V1', repository=m.REPOSITORY, status='HEALTHY', environment=env,
                source=source*40, application=letter*64, image=ACCOUNT+'.dkr.ecr.us-east-1.amazonaws.com/api@sha256:'+letter*64,
                compatibility='f'*64, profile='validated-v2', per_task_ready=True, client_ready=True, run_id=22, run_attempt=1,
                revision=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/demo-{env}-app-api-blue:2',color='blue')
    value['manifest_ref'] = dict(bucket='protected-'+env, key='api-delivery/'+env+'/operations/11111111-1111-1111-1111-111111111111/release.json',
                                version='s3-version-B',sha256=m.sha(m.canonical(value)))
    return value


def pr():
    return dict(number=42, merged=True, head=dict(ref='develop', sha='2'*40, repo={'full_name': m.REPOSITORY,'id':1143067989}),
                base=dict(ref='main', sha='1'*40, repo={'full_name': m.REPOSITORY,'id':1143067989}))


def run(workflow=m.DELIVERY, event='push', branch='develop', sha='2'*40):
    return dict(id=22,run_attempt=1,repository={'full_name':m.REPOSITORY},head_repository={'full_name':m.REPOSITORY},
                workflow_id=7,path=workflow,event=event,head_branch=branch,head_sha=sha,
                status='completed',conclusion='success')


class Rest(GitHub):
    """Only transport is doubled. No mocked artifact/receipt/provenance methods."""
    def __init__(self, event='pull_request_target', letter='b', source='2', oci=None):
        self.calls = []; self.responses = {}; self.binary = {}; self.signatures = Signatures()
        pull = pr(); pull.update(state='closed', draft=False, merged_at='2026-11-08T20:10:00Z', merge_commit_sha='4'*40)
        pull['head']['sha'] = source*40
        dev = record(letter, source=source)
        if oci is not None:
            dev['image']=config()['repository']+'@sha256:'+m.sha(oci.encode())
            dev['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in dev.items() if k!='manifest_ref'}))
        dev_bundle, dev_locator = self.signatures.deployment(dev)
        receipt = dict(m.approval(pull, letter*64, dev), run_id=80, run_attempt=2, check_id=700, dev_receipt=dev_locator,
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
        self.bundle,self.locator = self.signatures.sign(r.slot('promotion',80,attempt=2),receipt,origin('1'*40,80,2,event,'prod'))
        self.responses.update(self.signatures.responses)
        self.check_record = dict(id=700,name='API Promotion Validation',app={'id':15368},head_sha=source*40,
            status='completed',conclusion='success',started_at='2026-11-08T20:00:00Z',completed_at='2026-11-08T20:01:00Z',
            external_id=json.dumps(self.locator),details_url=self.approval_url(self.locator))
        self.metadata = dict(id=901,name='promotion-record-2',expired=False,size_in_bytes=len(raw),digest=digest,
                             workflow_run=dict(id=80,repository_id=99,head_repository_id=99,head_sha=producer['head_sha']))
        self.responses.update({PREFIX:dict(id=99,allow_merge_commit=True),
            PREFIX+'/rules/branches/main':[permissions.PROMOTION_RULE,{'type':'pull_request','parameters':{'allowed_merge_methods':['merge']}}],
            PREFIX+'/actions/workflows/api-promotion.yml':{'id':7},
            PREFIX+'/actions/runs/80':producer,PREFIX+'/actions/runs/80/attempts/2':producer,
            PREFIX+'/check-runs/700':self.check_record,
            PREFIX+'/actions/artifacts/901':self.metadata,
            PREFIX+'/commits/'+source*40+'/check-runs?filter=all&per_page=100&page=1':{'check_runs':[self.check_record]},
            PREFIX+'/commits/'+'4'*40+'/pulls':[pull], PREFIX+'/pulls/42':pull})
        self.binary[PREFIX+'/actions/artifacts/901/zip'] = raw

    def verify_signature(self,command): return self.signatures.verify(command)

    def get(self,path):
        self.calls.append(path)
        if path not in self.responses: raise AssertionError('unexpected REST lookup: '+path)
        return copy.deepcopy(self.responses[path])

    def raw(self,path):
        self.calls.append(path)
        return self.binary[path]


class Wire:
    """Only gh's external process is replaced; GitHub.get/raw remain real."""
    def __init__(self, fixture):
        self.fixture, self.calls = fixture, []
        fixture.responses[PREFIX+'/actions/runs/80/attempts/2'] = copy.deepcopy(fixture.producer)

    def __call__(self, argv, **kwargs):
        if argv[:2] == ['gh','attestation']: return self.fixture.signatures.verify(argv)
        if argv[:2] != ['gh', 'api']: raise AssertionError(argv)
        path = argv[-1]
        self.calls.append(path)
        if path in self.fixture.binary:
            return self.fixture.binary[path]
        if path in self.fixture.responses:
            return m.canonical(self.fixture.responses[path])
        raise AssertionError('Unexpected wire request: ' + path)
