"""First-session security backend bootstrap; no AWS calls on import.

Only a new project-specific security bucket in the explicitly selected account.
Never adopts an existing bucket, grants IAM, deletes state or changes a profile.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

PROFILE='cnp-cert-dev'
REGION='us-east-1'


def require(ok,message):
    if not ok:raise ValueError(message)


class AWS:
    def __init__(self,account):
        require(bool(re.fullmatch('[0-9]{12}',account)),'verified account ID required')
        self.account=account
        self.env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','TF_','TERRAGRUNT'))}
        self.env.update(AWS_PROFILE=PROFILE,AWS_REGION=REGION,AWS_DEFAULT_REGION=REGION,AWS_EC2_METADATA_DISABLED='true',AWS_MAX_ATTEMPTS='1',AWS_PAGER='')
    def call(self,*args):
        run=subprocess.run(['aws','--profile',PROFILE,'--region',REGION,'--no-cli-pager','--output','json',*args],env=self.env,capture_output=True,text=True,timeout=120)
        require(run.returncode==0,'AWS command failed: '+args[0]+' '+args[1]+'; retain evidence, inspect before any retry')
        return json.loads(run.stdout) if run.stdout.strip() else {}


def policy(bucket,admin):
    resources=['arn:aws:s3:::'+bucket,'arn:aws:s3:::'+bucket+'/*']
    return {'Version':'2012-10-17','Statement':[
        {'Sid':'TLSOnly','Effect':'Deny','Principal':'*','Action':'s3:*','Resource':resources,'Condition':{'Bool':{'aws:SecureTransport':'false'}}},
        {'Sid':'SecurityAdminOnly','Effect':'Deny','Principal':'*','Action':'s3:*','Resource':resources,'Condition':{'ArnNotEquals':{'aws:PrincipalArn':admin}}}]}


def bootstrap(aws,directory,confirmation):
    directory=Path(directory)
    account=aws.account;bucket='terragrunt-demo-security-'+account+'-'+REGION
    require(confirmation=='CREATE SECURITY BACKEND '+account+' '+REGION,'explicit backend creation scope')
    identity=aws.call('sts','get-caller-identity')
    require(identity['Account']==account and bool(re.fullmatch('arn:aws:iam::'+account+':(?:user|role)/[A-Za-z0-9+=,.@_/-]+',identity['Arn'])),'same-account human admin identity required')
    require(bucket not in [b['Name'] for b in aws.call('s3api','list-buckets')['Buckets']],'existing bucket: inspect manually; no adoption or policy overwrite')
    directory.mkdir(parents=True,exist_ok=True)
    attempt=directory/'security-backend-attempt.json'
    with attempt.open('x',encoding='utf-8') as file:json.dump({'bucket':bucket,'account':account,'admin':identity['Arn'],'status':'UNKNOWN_UNTIL_READBACK'},file)
    owner=['--bucket',bucket,'--expected-bucket-owner',account]
    aws.call('s3api','create-bucket','--bucket',bucket,'--object-ownership','BucketOwnerEnforced')
    public={k:True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')}
    aws.call('s3api','put-public-access-block',*owner,'--public-access-block-configuration',json.dumps(public))
    aws.call('s3api','put-bucket-encryption',*owner,'--server-side-encryption-configuration',json.dumps({'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]}))
    aws.call('s3api','put-bucket-versioning',*owner,'--versioning-configuration','Status=Enabled')
    aws.call('s3api','put-bucket-tagging',*owner,'--tagging',json.dumps({'TagSet':[{'Key':'Project','Value':'terragrunt_demo'},{'Key':'Purpose','Value':'security-state'},{'Key':'Environment','Value':'security'}]}))
    expected=policy(bucket,identity['Arn'])
    aws.call('s3api','put-bucket-policy',*owner,'--policy',json.dumps(expected))
    require((aws.call('s3api','get-bucket-location',*owner)['LocationConstraint'] or 'us-east-1')==REGION,'backend region mismatch')
    require(aws.call('s3api','get-public-access-block',*owner)['PublicAccessBlockConfiguration']==public,'backend not private')
    require(aws.call('s3api','get-bucket-versioning',*owner)['Status']=='Enabled','versioning not enabled')
    rules=aws.call('s3api','get-bucket-encryption',*owner)['ServerSideEncryptionConfiguration']['Rules']
    require(len(rules)==1 and rules[0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']=='AES256','encryption mismatch')
    require(aws.call('s3api','get-bucket-ownership-controls',*owner)['OwnershipControls']['Rules']==[{'ObjectOwnership':'BucketOwnerEnforced'}],'bucket ownership mismatch')
    require(json.loads(aws.call('s3api','get-bucket-policy',*owner)['Policy'])==expected,'installed policy mismatch')
    result={'bucket':bucket,'account':account,'region':REGION,'admin':identity['Arn'],'key':'e1/security/terraform.tfstate','lock_key':'e1/security/terraform.tfstate.tflock','locking':'S3_NATIVE_LOCKFILE','configuration_readback':'VERIFIED','terraform_lock_execution':'NOT_YET_TESTED','retained_after_down':True}
    with (directory/'security-backend-verified.json').open('x',encoding='utf-8') as file:json.dump(result,file,indent=2)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account',required=True);parser.add_argument('--evidence-directory',type=Path,required=True);parser.add_argument('--confirm',required=True)
    args=parser.parse_args();print(json.dumps(bootstrap(AWS(args.account),args.evidence_directory,args.confirm),indent=2))


if __name__=='__main__':main()
