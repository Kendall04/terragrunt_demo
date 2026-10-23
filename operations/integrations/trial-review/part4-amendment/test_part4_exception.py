import unittest, json, hashlib
from copy import deepcopy
from pathlib import Path
from fnmatch import fnmatchcase
from part4_exception import propose, BUCKET_ARN, EXPECTED_DENY

ROOT = Path(__file__).parent
ORIGINAL_SHA = '2dee64162063bf48daa6be793a92399fd8383104cd102078ae4bd7427a7876e2'
def load(name): return json.loads((ROOT / name).read_text(encoding='utf-8'))
def denied(policy, action, resource):
    """Only the two unconditional deny shapes under test; not a general IAM engine."""
    for s in policy['Statement']:
        if s['Effect'] != 'Deny': continue
        assert 'Condition' not in s
        if not any(fnmatchcase(action.lower(), a.lower()) for a in s['Action']): continue
        if 'Resource' in s and any(fnmatchcase(resource, r) for r in s['Resource']): return True
        if 'NotResource' in s and not any(fnmatchcase(resource, r) for r in s['NotResource']): return True
    return False

class ScopeTests(unittest.TestCase):
    def setUp(self): self.original=load('part4-original.json'); self.proposal=propose(self.original)
    def test_captured_canonical_hash(self):
        self.assertEqual(hashlib.sha256(json.dumps(self.original,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),ORIGINAL_SHA)
    def test_saved_proposal_is_reproducible(self): self.assertEqual(self.proposal,load('part4-proposed.json'))
    def test_original_is_not_mutated(self):
        before=deepcopy(self.original); propose(self.original); self.assertEqual(self.original,before)
    def test_all_other_statements_exact(self):
        self.assertEqual([s for s in self.original['Statement'] if s!=EXPECTED_DENY],
                         [s for s in self.proposal['Statement'] if s['Effect']!='Deny'])
    def test_remaining_deny_exact(self):
        remaining=deepcopy(EXPECTED_DENY);remaining['Action'].remove('s3:DeleteBucket')
        self.assertIn(remaining,self.proposal['Statement'])
    def test_exception_has_only_exact_bucket_and_action(self):
        s=next(s for s in self.proposal['Statement'] if 'NotResource' in s)
        self.assertEqual(s,{'Sid':'DenyDeleteBucketExceptEcsSentinelR20261023b1','Effect':'Deny','Action':['s3:DeleteBucket'],'NotResource':[BUCKET_ARN]})
    def test_target_was_denied_and_only_deny_is_removed(self):
        self.assertTrue(denied(self.original,'s3:DeleteBucket',BUCKET_ARN));self.assertFalse(denied(self.proposal,'s3:DeleteBucket',BUCKET_ARN))
    def test_no_allow_added_or_changed(self):
        self.assertEqual([s for s in self.original['Statement'] if s['Effect']=='Allow'],[s for s in self.proposal['Statement'] if s['Effect']=='Allow'])
    def test_other_buckets_remain_denied(self):
        for r in [BUCKET_ARN+'-other',BUCKET_ARN.replace('b1-','b2-'),BUCKET_ARN.replace('341936017254','111111111111'),
                  'arn:aws:s3:::e1-lifecycle-dev-341936017254-us-east-1','arn:aws:s3:::e1-wp4-dev-341936017254-us-east-1',
                  'arn:aws:s3:::unrelated-bucket',BUCKET_ARN+'/object',BUCKET_ARN.upper()]:
            with self.subTest(r=r): self.assertTrue(denied(self.proposal,'s3:DeleteBucket',r))
    def test_other_deny_actions_unchanged_for_all_resources(self):
        for a in EXPECTED_DENY['Action']:
            if a=='s3:DeleteBucket': continue
            for r in [BUCKET_ARN,BUCKET_ARN+'/object','*','arn:aws:iam::341936017254:role/ecs-sentinel-r20261023b1-ingest-role']:
                with self.subTest(a=a,r=r):self.assertTrue(denied(self.proposal,a,r))
    def test_upstream_shape_changes_fail_closed(self):
        for key,value in [('Condition',{'Bool':{'aws:SecureTransport':'false'}}),('Resource',[BUCKET_ARN]),('Action',['s3:DeleteBucket']),('Sid','new')]:
            p=deepcopy(self.original);next(s for s in p['Statement'] if s['Effect']=='Deny')[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):propose(p)
    def test_duplicate_or_absent_deny_fail_closed(self):
        for statements in [self.original['Statement']+[deepcopy(EXPECTED_DENY)],[s for s in self.original['Statement'] if s!=EXPECTED_DENY]]:
            p=deepcopy(self.original);p['Statement']=statements
            with self.assertRaises(ValueError):propose(p)
    def test_sid_collision_fails_closed(self):
        p=deepcopy(self.original);p['Statement'][0]['Sid']='DenyDeleteBucketExceptEcsSentinelR20261023b1'
        with self.assertRaises(ValueError):propose(p)
    def test_history_v1_preserved_by_hash(self):
        receipt=load('historical-capture-receipt.json')
        self.assertEqual(hashlib.sha256((ROOT/'part4-historical-v1.json').read_bytes()).hexdigest(),receipt['FileSha256'])
    def test_rollback_baseline_is_still_default_v5(self):
        r=load('capture-receipt.json');self.assertEqual(r['PolicyMetadata']['DefaultVersionId'],'v5')
        self.assertEqual([v['VersionId'] for v in r['Versions']['Versions']],['v5','v4','v3','v2','v1'])
        self.assertEqual([x['RoleName'] for x in r['Entities']['PolicyRoles']],['TerragruntDemoDevOperator'])
        self.assertEqual(r['Entities']['PolicyUsers'],[]);self.assertEqual(r['Entities']['PolicyGroups'],[])

if __name__=='__main__':unittest.main(verbosity=2)
