"""LOCAL REVIEW CANDIDATE. Do not execute E16 until the tool rejection is reviewed.

Default: describe only. A review digest binds this wrapper and both existing E16
source files. The execution flag checks reviewed bytes, not permission: it does
not clear the prior rejection or authorize apply, deletion or a different route.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO=Path(r'C:\CodexDrop\terragrunt_demo')
PREVIOUS=Path(r'C:\CodexDrop\temp\terragrunt-demo-sql-ec2-live-20261016')
ACTIONS=('init','bootstrap-network-plan')
STEPS={'source':'SOURCE_METADATA','init':'E16_INIT','bootstrap-network-plan':'E16_NETWORK_PLAN'}
SAFE_STEPS=set(STEPS.values())|{'LOCAL_PREPARATION','E16_PRECONDITION','AWS_METADATA','TERRAFORM_PREPARATION'}|{
    layer+'_TERRAFORM_'+action for layer in ('GLOBAL','DATA','PLATFORM','APPS','EDGE') for action in ('INIT','WORKSPACE','STATE','SHOW','PLAN')}

class StepFailure(Exception):
    def __init__(self,step,code):
        self.step=step if step in SAFE_STEPS else 'LOCAL_PREPARATION'
        self.code=code if type(code) is int else 1

def failure_metadata(error):
    return {'Status':'FAILED','Step':error.step if isinstance(error,StepFailure) else 'LOCAL_PREPARATION',
            'ExitCode':error.code if isinstance(error,StepFailure) else 1}

def review():
    paths={'wrapper':Path(__file__),'entry':REPO/'scripts/original_dev.py','implementation':REPO/'scripts/practical_dev.py'}
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
    digest=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'Status':'LOCAL_REVIEW_ONLY','ReviewSha256':digest,'SourceSha256':hashes,
            'CanonicalEntry':'scripts/original_dev.py dev','Actions':list(ACTIONS),'RequiredFlag':'--discard-diagnostics',
            'RemoteState':'internal E16/Terraform consumption only after human/tool review',
            'ChildStderr':'DEVNULL in wrapper and native E16 Process; no raw stderr file',
            'ReturnedOutput':'fixed metadata summary only; no state/preview/before/after/confirmations',
            'PlanArtifacts':'existing private E16 binary/preview/review artifacts; never copied or printed by wrapper',
            'ApplyAuthorized':False,'ExecutionAuthorizedByThisFile':False,'RetryAfterSecondRejection':False}

def checked(command,action):
    result=subprocess.run(command,cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=1200)
    if result.returncode:
        step=STEPS.get(action,'LOCAL_PREPARATION');code=result.returncode
        if action in ACTIONS:
            try:
                safe=json.loads(result.stdout)
                if safe.get('Step') in SAFE_STEPS and type(safe.get('ExitCode')) is int:step,code=safe['Step'],safe['ExitCode']
            except (ValueError,UnicodeError,AttributeError):pass
        raise StepFailure(step,code)
    if action in ACTIONS:print(json.dumps({'Step':STEPS[action],'ExitCode':0}),flush=True)
    return result.stdout

def execute_after_review(root,review_digest):
    if review_digest!=review()['ReviewSha256']: raise ValueError('REVIEWED_SOURCE_BYTES_REQUIRED')
    if root.exists() or not root.is_absolute() or REPO==root or REPO in root.parents: raise ValueError('NEW_EXTERNAL_SESSION_REQUIRED')
    commit=checked(['git','rev-parse','HEAD'],'source').decode('ascii').strip()
    if checked(['git','status','--porcelain'],'source').strip(): raise ValueError('CLEAN_REVIEWED_SOURCE_REQUIRED')
    config=json.loads((PREVIOUS/'config.json').read_text(encoding='utf-8'));config['source_commit']=commit
    root.mkdir(parents=True)
    (root/'config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    (root/'operator-profile.config').write_bytes((PREVIOUS/'operator-profile.config').read_bytes())
    arguments=['--config',str(root/'config.json'),'--directory',str(root/'session'),
               '--aws-config-file',str(root/'operator-profile.config'),'--discard-diagnostics']
    result=None
    for action in ACTIONS:
        raw=checked([sys.executable,'-I','-B','scripts/original_dev.py','dev',action,*arguments],action)
        try: result=json.loads(raw)
        except (ValueError,UnicodeError): raise ValueError('SUPPORTED_E16_METADATA_RESPONSE_REQUIRED') from None
    allowed=('stage','aws_verified','plan_id','layer','phase','change_summary')
    summary={key:result[key] for key in allowed if key in result}
    summary.update(Status='PLAN_ONLY_NOT_APPLIED',Utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   SourceCommit=commit,ReviewSha256=review_digest,Applied=False,RuntimeCreated=False,
                   BillingStartUtc=None,DeadlineUtc=None,RawDiagnosticsSaved=False)
    (root/'plan-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-after-human-review',action='store_true')
    parser.add_argument('--review-sha256');parser.add_argument('--evidence-root',type=Path)
    args=parser.parse_args()
    if not args.execute_after_human_review: return review()
    if not args.evidence_root or not args.review_sha256: raise ValueError('HUMAN_REVIEW_AND_NEW_EVIDENCE_ROOT_REQUIRED')
    return execute_after_review(args.evidence_root,args.review_sha256)

if __name__=='__main__':
    try: print(json.dumps(main(),indent=2))
    except Exception as error:
        print(json.dumps(failure_metadata(error)))
        raise SystemExit(1)
