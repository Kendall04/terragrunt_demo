"""Offline gh/Sigstore transport fixtures; never mock receipt/discovery logic."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import uuid
from scripts.api_delivery import model as m, receipts as r

PREFIX = 'repos/'+m.REPOSITORY


def origin(sha='2'*40,run=22,attempt=1,event='push',env='dev'):
    return dict(run=run,attempt=attempt,workflow_sha=sha,source_sha=sha,event=event,
                ref='refs/heads/'+('develop' if env == 'dev' else 'main'))


def enrich(value):
    value.setdefault('event_source',value['source'])
    value.setdefault('operation',str(uuid.uuid5(uuid.NAMESPACE_URL,f'{m.REPOSITORY}/{value["environment"]}/{value["run_id"]}')))
    value['manifest_ref']['key']=f'api-delivery/{value["environment"]}/operations/{value["operation"]}/release.json'
    value.setdefault('producer',origin(value['event_source'],value['run_id'],value['run_attempt'],env=value['environment']))
    value.setdefault('request_sha256','a'*64)
    value.setdefault('configuration_ref',dict(bucket='protected-'+value['environment'],key='configuration',version='config-v1',sha256='a'*64))
    value['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in value.items() if k != 'manifest_ref'}))
    return value


class Signatures:
    def __init__(self): self.valid={}; self.responses={}; self.calls=[]

    def sign(self,descriptor,record,pub,recovered=False):
        rule=r.POLICY[descriptor['kind']]
        cert=dict(buildConfigURI=f'https://github.com/{m.REPOSITORY}/{rule["caller"]}@{pub["ref"]}',
            buildConfigDigest=pub['workflow_sha'],buildSignerURI=f'https://github.com/{m.REPOSITORY}/{rule["signer"]}@{pub["ref"]}',
            buildSignerDigest=pub['workflow_sha'],buildTrigger=pub['event'],
            runInvocationURI=f'https://github.com/{m.REPOSITORY}/actions/runs/{pub["run"]}/attempts/{pub["attempt"]}',
            sourceRepositoryIdentifier='1143067989',sourceRepositoryOwnerIdentifier='66651825',
            sourceRepositoryDigest=pub['source_sha'],sourceRepositoryRef=pub['ref'],sourceRepositoryURI='https://github.com/'+m.REPOSITORY,
            issuer='https://token.actions.githubusercontent.com',runnerEnvironment='github-hosted')
        statement=dict(_type='https://in-toto.io/Statement/v1',subject=[dict(name='slot.json',digest={'sha256':m.sha(m.canonical(descriptor))})],
            predicateType=r.POLICY['predicate_type'],predicate=dict(schema='API_SIGNED_RECEIPT_V1',slot=descriptor,
            publisher=pub,record=record,recovered=recovered))
        bundle={'dsseEnvelope':{'payload':base64.b64encode(m.canonical(statement)).decode(),'signatures':[{'sig':'fixture-signature'}]}}
        self.valid[m.sha(m.canonical(bundle))]=dict(verificationResult=dict(statement=copy.deepcopy(statement),signature={'certificate':cert}))
        path=PREFIX+'/attestations/sha256:'+m.sha(m.canonical(descriptor))+'?per_page=100'
        self.responses.setdefault(path,{'attestations':[]})['attestations'].append({'bundle':bundle})
        return bundle,r.compact(descriptor,bundle,pub)

    def verify(self,command):
        self.calls.append(command)
        bundle=json.loads(Path(command[command.index('--bundle')+1]).read_bytes())
        value=self.valid.get(m.sha(m.canonical(bundle)))
        if value is None: raise subprocess.CalledProcessError(1,command)
        return m.canonical([value])

    def deployment(self,record,recovered=False,pub=None):
        enrich(record);pub=pub or record['producer'];bundle,loc=self.sign(r.slot('deployment',record['run_id'],record['environment']),record,pub,recovered)
        original=record['producer'];branch='develop' if record['environment']=='dev' else 'main'
        run=dict(id=original['run'],run_attempt=original['attempt'],repository={'full_name':m.REPOSITORY},head_repository={'full_name':m.REPOSITORY},
            workflow_id=7,path=m.DELIVERY,event=original['event'],head_branch=branch,head_sha=original['source_sha'],status='completed',conclusion='success')
        self.responses.update({PREFIX+'/actions/workflows/api-delivery.yml':{'id':7},
            PREFIX+f'/actions/runs/{original["run"]}/attempts/{original["attempt"]}':run,
            PREFIX+f'/actions/runs/{original["run"]}/attempts/{original["attempt"]}/jobs?per_page=100&page=1':{'jobs':[
                dict(name='delivery / delivery',steps=[dict(name=r.EXECUTE,status='completed',conclusion='success')])]},
            PREFIX+'/actions/workflows/api-delivery.yml/runs?per_page=100&page=1':{'workflow_runs':[run]}})
        return bundle,loc
