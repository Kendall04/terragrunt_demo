"""Offline ports for production WP3A finalizer tests; no AWS emulation."""
import copy
import json
import unittest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/qualification'))
import finalizer as f

OP='11111111-1111-1111-1111-111111111111'
OTHER='22222222-2222-2222-2222-222222222222'
CANARY='SECRET_CANARY_do_not_disclose'
class Evidence(f.Evidence):
    def __init__(self):
        self.calls=[]
        common=dict(operation_id=OP, project='e1-controller-release',build_id='e1-controller-release:'+OTHER,source_commit='a'*40)
        self.op=dict(schema='E1_RELEASE_OPERATION_V1',writer='RELEASE_GATEWAY',account='111122223333',region='us-east-1',repository='Kendall04/terragrunt_demo',**common)
        checks={k:'PASS' for k in f.REQUIRED_CHECKS}
        self.actual=dict(schema='E1_BUILD_OBSERVATION_V1',state='SUCCEEDED',checks=copy.deepcopy(checks),**common)
        self.candidate=dict(schemaVersion='1.0',app='demo-api',repository=self.op['repository'],gitSha='a'*40,sourceBranch='develop',githubRunId='42',githubRunAttempt='1',createdAt='2026-09-25T00:00:00Z',image=dict(registry='111122223333.dkr.ecr.us-east-1.amazonaws.com',repository='demo-shared-demo-ms',tag='candidate',digest='sha256:'+'b'*64,uri='111122223333.dkr.ecr.us-east-1.amazonaws.com/demo-shared-demo-ms@sha256:'+'b'*64),quality=dict(dotnetTests='passed',dockerBuild='passed',scanStatus='unknown'))
        raw=f.canonical(self.candidate)
        self.ref=dict(bucket='demo-release-artifacts-111122223333',key='releases/demo-api/by-digest/sha256-'+'b'*64+'.json',version_id='returned-manifest-version-A',sha256=f.checksum(raw))
        self.supervised=dict(schema='E1_SUPERVISED_RESULT_V1',state='SUCCEEDED',checks=checks,image_repository='demo-shared-demo-ms',image_digest='sha256:'+'b'*64,runtime_contract=f.RUNTIME,manifest=copy.deepcopy(self.ref),**common)
        for record in (self.actual,self.supervised):
            record.update({k:self.op[k] for k in ('account','region','repository')})
        self.receipt={k:v for k,v in self.ref.items() if k!='sha256'};self.receipt['bytes']=raw
    def operation(self, operation_id):self.calls.append(('operation',operation_id));return copy.deepcopy(self.op)
    def build(self, build_id):self.calls.append(('build',build_id));return copy.deepcopy(self.actual)
    def result(self, operation_id, build_id):self.calls.append(('result',operation_id,build_id));return copy.deepcopy(self.supervised)
    def manifest(self,bucket,key,version_id):self.calls.append(('manifest',bucket,key,version_id));return copy.deepcopy(self.receipt)
class Store(f.Qualifications):
    def __init__(self):self.records={};self.writes=0;self.failure=False;self.noop=False
    def create(self,key,raw):
        if self.failure:raise OSError(CANARY)
        if key in self.records:raise FileExistsError(key)
        if not self.noop:self.records[key]=raw;self.writes+=1
    def read(self,key):return self.records[key]

class Tests(unittest.TestCase):
    def setUp(self):
        self.e=Evidence();self.s=Store();self.core=f.Finalizer('111122223333','us-east-1',self.e,self.s)
    def run_finalizer(self,wakeup=None):return self.core.finalize(wakeup if wakeup is not None else {'operation_id':OP})
    def rejected(self,wakeup=None):
        with self.assertRaises(f.Rejected) as caught:self.run_finalizer(wakeup)
        self.assertNotIn(CANARY,str(caught.exception));self.assertEqual(self.s.records,{})
    def test_positive_closed_contracts(self):
        for kind,v in [('operation',self.e.op),('build',self.e.actual),('result',self.e.supervised)]:self.assertEqual(f.validate(kind,v),v)
        q=self.run_finalizer();self.assertEqual(f.validate('qualification',q),q);self.assertEqual(len(self.s.records),1)
        self.assertIn(('manifest',self.e.ref['bucket'],self.e.ref['key'],self.e.ref['version_id']),self.e.calls)
    def test_exact_retry(self):
        first=self.run_finalizer();self.assertEqual(self.run_finalizer(),first);self.assertEqual(self.s.writes,1)
    def test_conflicting_existing_qualification(self):
        self.run_finalizer();key=next(iter(self.s.records));self.s.records[key]=b'conflicting'
        with self.assertRaises(f.Rejected):self.run_finalizer()
        self.assertEqual(self.s.records[key],b'conflicting')
    def test_write_failure(self):self.s.failure=True;self.rejected()
    def test_noop_write_is_not_success(self):self.s.noop=True;self.rejected()
    def test_notification_without_evidence(self):
        self.e.op={};self.rejected()
    def test_caller_fields(self):
        for k in ('source_commit','image_digest','manifest','checks','project','success','eligibility','build_id','release_id'):
            self.rejected({'operation_id':OP,k:CANARY})
    def test_legacy_defaults_not_qualification(self):
        self.e.supervised['checks']={};self.rejected()
    def test_actual_failure_despite_result_success(self):self.e.actual['state']='FAILED';self.rejected()
    def test_eligibility_separate(self):
        q=self.run_finalizer();record=dict(schema='E1_ELIGIBILITY_V1',writer='SECURITY_ADMIN',release_id=q['release_id'],state='REVOKED',version_id='registry-A')
        self.assertEqual(f.validate_eligibility(record,q['release_id']),record)
        self.assertFalse(hasattr(self.s,'write_eligibility'))
        for writer in ['QUALIFICATION_FINALIZER','BUILD','REQUESTER']:
            with self.assertRaises(f.Rejected):f.validate_eligibility({**record,'writer':writer},q['release_id'])
    def test_qualification_writer_schema(self):
        q=self.run_finalizer()
        for writer in ['BUILD','REQUESTER','DELIVERY','SECURITY_ADMIN']:
            with self.assertRaises(f.Rejected):f.validate('qualification',{**q,'writer':writer})
    def test_secret_port_error(self):
        def fail(_):raise OSError(CANARY)
        self.e.operation=fail;self.rejected()
    def test_secret_unknown_field(self):self.e.supervised['secret']=CANARY;self.rejected()
    def test_candidate_secret_not_copied(self):
        self.e.candidate['image']['tag']=CANARY
        raw=f.canonical(self.e.candidate);self.e.receipt['bytes']=raw;self.e.supervised['manifest']['sha256']=f.checksum(raw)
        q=self.run_finalizer();self.assertNotIn(CANARY,json.dumps(q));self.assertNotIn(CANARY,str(self.s.records))
    def test_duplicate_manifest_json(self):
        raw=self.e.receipt['bytes'].rstrip()[:-1]+b',"app":"demo-api"}'
        self.e.receipt['bytes']=raw;self.e.supervised['manifest']['sha256']=f.checksum(raw);self.rejected()
    def test_candidate_image_substitution(self):
        self.e.candidate['image']['digest']='sha256:'+'c'*64
        raw=f.canonical(self.e.candidate);self.e.receipt['bytes']=raw;self.e.supervised['manifest']['sha256']=f.checksum(raw);self.rejected()
    def test_candidate_source_substitution(self):
        self.e.candidate['gitSha']='b'*40
        raw=f.canonical(self.e.candidate);self.e.receipt['bytes']=raw;self.e.supervised['manifest']['sha256']=f.checksum(raw);self.rejected()
    def test_release_identity_recomputed(self):
        q=self.run_finalizer();identity=q.pop('release_id');self.assertEqual(identity,'sha256-'+f.checksum(f.canonical(q)))
    def test_wrong_port(self):
        with self.assertRaises(f.Rejected):f.Finalizer('111122223333','us-east-1',{},self.s)
    def test_wp2_inactive(self):
        d=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());c=d['controller_compute']
        self.assertEqual(len(c['nodes']),18);self.assertFalse(c['creation_supported']);self.assertFalse(c['operational'])
        self.assertTrue(all(not n['operational'] for n in c['nodes'].values()))
        self.assertEqual(len(d['request_identities']),11)
        for policy in [d['policies']['inert_trust'],d['policies']['inert_permissions'],*c['role_trust'].values()]:self.assertTrue(all(s['Effect']=='Deny' for s in policy['Statement']))
        self.assertEqual(len(d['ownership_closure']['recovery']),8);self.assertTrue(all(not r['operational'] and not r['invocation_enabled'] for r in d['ownership_closure']['recovery'].values()))
        self.assertEqual(d['ownership_closure']['live'],'UNVERIFIED')

# Each mutation runs the real finalizer, not an expected-answer evaluator.
def mutation(path,value,delete=False):
    def test(self):
        obj=getattr(self.e,path[0])
        for key in path[1:-1]:obj=obj[key]
        if delete:del obj[path[-1]]
        else:obj[path[-1]]=value
        self.rejected()
    return test
cases={
 'failed_check':(('supervised','checks','dotnet_test'),'FAIL'),
 'skipped_check':(('supervised','checks','dotnet_test'),'SKIPPED'),
 'unknown_check':(('supervised','checks','dotnet_test'),'UNKNOWN'),
 'null_check':(('supervised','checks','dotnet_test'),None),
 'actual_check':(('actual','checks','probe_capability'),'FAIL'),
 'wrong_project':(('actual','project'),'other'),
 'wrong_build':(('actual','build_id'),'e1-controller-release:'+OP),
 'wrong_operation':(('supervised','operation_id'),OTHER),
 'actual_wrong_operation':(('actual','operation_id'),OTHER),
 'wrong_source':(('actual','source_commit'),'b'*40),
 'result_wrong_source':(('supervised','source_commit'),'b'*40),
 'wrong_digest':(('supervised','image_digest'),'sha256:'+'c'*64),
 'tag_only':(('supervised','image_digest'),'latest'),
 'wrong_version':(('receipt','version_id'),'version-B'),
 'null_version':(('supervised','manifest','version_id'),None),
 'latest_version':(('supervised','manifest','version_id'),'latest'),
 'empty_version':(('supervised','manifest','version_id'),''),
 'wrong_checksum':(('supervised','manifest','sha256'),'0'*64),
 'wrong_runtime':(('supervised','runtime_contract'),'other'),
 'wrong_schema':(('supervised','schema'),'legacy'),
 'result_failed':(('supervised','state'),'FAILED'),
 'wrong_bucket':(('receipt','bucket'),'other'),
 'wrong_key':(('receipt','key'),'other'),
 'orphan_result':(('supervised','build_id'),'e1-controller-release:'+OP),
 'actual_wrong_account':(('actual','account'),'999999999999'),
 'result_wrong_region':(('supervised','region'),'us-west-2'),
 'actual_wrong_repository':(('actual','repository'),'other/repo'),
 'wrong_account':(('op','account'),'999999999999'),
 'wrong_repository':(('op','repository'),'other/repo'),
 'wrong_writer':(('op','writer'),'REQUESTER'),
}
for name,(path,value) in cases.items():setattr(Tests,'test_mutation_'+name,mutation(path,value))
setattr(Tests,'test_missing_check',mutation(('supervised','checks','dotnet_test'),None,True))
