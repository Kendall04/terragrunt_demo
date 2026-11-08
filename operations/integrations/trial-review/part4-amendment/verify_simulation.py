"""Validate captured AWS IAM simulation responses offline, without AWS SDK/network."""
from pathlib import Path
import json
ROOT=Path(__file__).parent
RAW=ROOT/'simulation-complete-03'
BUCKET='arn:aws:s3:::ecs-sentinel-r20261023b1-341936017254'
def flatten(response):
    for e in response['EvaluationResults']:
        if e.get('ResourceSpecificResults'):
            for r in e['ResourceSpecificResults']:
                yield e['EvalActionName'],r['EvalResourceName'],r['EvalResourceDecision'],r.get('MissingContextValues',[])
        else:
            yield e['EvalActionName'],e['EvalResourceName'],e['EvalDecision'],e.get('MissingContextValues',[])
def verify():
    checks=[];standalone_contexts=[];excluded=0
    cases=['original-plus-temporary-allow','proposal-alone','proposal-plus-temporary-allow-bucket-matrix','proposal-other-denies-retained']
    proper={
      'iam:CreateRole':'arn:aws:iam::341936017254:role/ecs-sentinel-r20261023b1-ingest-role',
      'iam:PutRolePolicy':'arn:aws:iam::341936017254:role/ecs-sentinel-r20261023b1-ingest-role',
      'iam:AttachRolePolicy':'arn:aws:iam::341936017254:role/ecs-sentinel-r20261023b1-ingest-role',
      's3:PutBucketPolicy':BUCKET,
      'kms:ScheduleKeyDeletion':'arn:aws:kms:us-east-1:341936017254:key/00000000-0000-4000-8000-000000000000',
      'secretsmanager:DeleteSecret':'arn:aws:secretsmanager:us-east-1:341936017254:secret:synthetic-no-secret-value-000000'}
    for name in cases:
        response=json.loads((RAW/(name+'.json')).read_text(encoding='utf-8'))
        assert not response.get('IsTruncated')
        for action,resource,decision,missing in flatten(response):
            if name=='proposal-other-denies-retained' and resource!=proper[action]:
                # Invalid service/resource cross-products are not authority evidence.
                assert decision=='implicitDeny';excluded+=1;continue
            expected=('implicitDeny' if name=='proposal-alone' else
                      'allowed' if name=='proposal-plus-temporary-allow-bucket-matrix' and resource==BUCKET else 'explicitDeny')
            assert decision==expected,(name,action,resource,decision)
            if name=='proposal-alone':
                standalone_contexts=missing
            else: assert not missing,(name,missing)
            checks.append({'Case':name,'Action':action,'Resource':resource,'Decision':decision})
    assert len(checks)==16 and excluded==18
    return {'Status':'PASS_CAPTURED_CUSTOM_SIMULATION_ONLY','PassedApplicableCases':len(checks),
            'ExcludedInvalidActionResourceCrossProducts':excluded,'Cases':checks,
            'StandaloneImplicitDenyMissingUnrelatedAllowContexts':standalone_contexts,
            'Limits':['Four SimulateCustomPolicy calls; source role and attached Part4 unchanged.',
                      'No real DeleteBucket, AssumeRole, IAM mutation or full effective-policy/SCP proof.',
                      'Proposal-alone implicitDeny lists contexts from unchanged other-action allows; no new Allow is proved by exact structural tests.'],
            'ActualDeleteRequests':0,'CloudMutations':0}
if __name__=='__main__':
    result=verify()
    (ROOT/'simulation-summary.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ['Cases','Limits']}))
