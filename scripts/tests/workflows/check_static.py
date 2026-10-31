"""Evaluate actual WP6 generated Terraform; no providers/backend/init/AWS."""
import copy
import fnmatch
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'security_root'),str(HERE.parent/'authority'),str(HERE.parents[2]),str(HERE.parent/'wp4d')]
import model
from terraform_console import decode as console_json
import wp6
from test_workflows import DOC,ROOT,ACCOUNT,REGION,projection

def denied(policy,action,resource,principal):
    def matches(patterns,value):
        if isinstance(patterns,str):patterns=[patterns]
        return any(fnmatch.fnmatchcase(value,p) for p in patterns)
    facts={'aws:PrincipalArn':principal,'aws:SecureTransport':'true'}
    for s in policy['Statement']:
        if s['Effect']!='Deny':continue
        if matches(s.get('Action',s.get('NotAction')),action)==('NotAction' in s):continue
        if matches(s.get('Resource',s.get('NotResource')),resource)==('NotResource' in s):continue
        conditions=[]
        for operator,fields in s.get('Condition',{}).items():
            for key,expected in fields.items():
                value=facts.get(key)
                if operator in ('ArnLike','StringLike'):conditions.append(value is not None and matches(expected,value))
                elif operator in ('ArnNotEquals','StringNotEquals'):conditions.append(not matches(expected,value or ''))
                elif operator in ('ArnEquals','StringEquals','Bool'):conditions.append(matches(expected,value or ''))
                else:raise AssertionError('unsupported resource condition '+operator)
        if all(conditions):return True
    return False

def main():
    terraform=shutil.which('terraform')
    if not terraform:raise SystemExit('WP6_TERRAFORM_STATIC_UNAVAILABLE')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','BOTO','TF_','TERRAGRUNT')) and 'PROXY' not in k.upper()}
    env.update(AWS_EC2_METADATA_DISABLED='true',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,CHECKPOINT_DISABLE='1',TF_IN_AUTOMATION='1')
    synthetic=copy.deepcopy(DOC);synthetic['wp6']['approvals']={k:projection(k) for k in wp6.c.IDENTITIES}
    endpoints={'request-gateway/'+k:v['endpoint_readback'] for k,v in synthetic['wp6']['approvals'].items() if not k.startswith('plan-')}
    target='terraform/infra/security/modules/request_identities/main.tf.json'
    inactive=copy.deepcopy(DOC);inactive['wp6']['approvals']={}
    cases=[('undeployed',inactive,{},None),('all-synthetic',synthetic,endpoints,None),('missing-installed-endpoints',synthetic,{},None)]
    for field,value in [('active',False),('governance','UNVERIFIED'),('workflow_commit','main'),('environment','attacker'),('source_sha256',{}),('gateway_version','$LATEST')]:
        mutant=copy.deepcopy(synthetic)
        for v in mutant['wp6']['approvals'].values():v[field]=value
        cases.append(('mutated-'+field,synthetic,endpoints,mutant))
    bad=copy.deepcopy(synthetic)
    for k,v in bad['wp6']['approvals'].items():
        if k.startswith('plan-'):v['plan_binding']['layers']['shared']['backend']['key']='e1/security/terraform.tfstate'
    cases.append(('caller-replaced-protected-state',synthetic,endpoints,bad))
    expression='jsonencode({active=keys(local.wp6_active),policies=local.wp6_policies,trusts=local.wp6_trusts})'
    with tempfile.TemporaryDirectory(prefix='e1-wp6-static-') as directory:
        for name,admitted,observed,mutant in cases:
            # Use the actual generator, including Python source admission; then
            # attempt unadmitted caller/module substitutions against its locals.
            generated=model.wiring(admitted)[target]
            # Normal activation uses the generated module's inactive preservation
            # defaults. The separate closed-preservation fixture tests new inputs.
            defaults={k:v['default'] for k,v in generated['variable'].items() if 'default' in v}
            variables={k:{'type':'any','default':v} for k,v in dict(defaults,
                authority=mutant or admitted,account_id=ACCOUNT,region=REGION,endpoints=observed).items()}
            path=Path(directory)/'main.tf.json';path.write_text(json.dumps(dict(variable=variables,locals=generated['locals'])))
            result=subprocess.run([terraform,'console','-no-color'],input=expression+'\n',capture_output=True,text=True,cwd=directory,env=env,timeout=30)
            if result.returncode:raise AssertionError(name+': '+result.stderr)
            actual=console_json(result.stdout)
            records=(mutant or admitted)['wp6']['approvals']
            expected=sorted(k for k,v in records.items() if v==admitted['wp6']['approvals'].get(k) and wp6.ready(k,v,ACCOUNT,REGION,None if k.startswith('plan-') else observed.get('request-gateway/'+k),DOC['wp6']['source_sha256']))
            assert actual['active']==expected,(name,actual['active'],expected)
            for key in expected:
                assert actual['trusts'][key]==wp6.trust(key,records[key],ACCOUNT)
                assert actual['policies'][key]==wp6.policy(key,records[key],ACCOUNT,REGION),(name,key,'policy parity')
                assert len(json.dumps(actual['policies'][key],separators=(',',':')))<=10240,'inline IAM ceiling'
            print(name+': actual Terraform gate/policy/trust PASS ('+str(len(expected))+' synthetic identities)')
        result=subprocess.run([terraform,'validate','-no-color'],capture_output=True,text=True,cwd=directory,env=env,timeout=30)
        assert result.returncode==0,result.stderr
        print('Disposable provider-free Terraform structure PASS')
        full=model.wiring(DOC);compute=full['terraform/infra/security/modules/controller_compute/main.tf.json']
        foundation=full['terraform/infra/security/modules/lifecycle_foundations/main.tf.json']
        wp4=compute['resource']['aws_s3_bucket_policy']['wp4d']['policy']
        wp4=wp4.replace('aws_s3_bucket.wp4d[each.key].arn','var.bucket').replace('each.key','var.environment')
        state=foundation['resource']['aws_s3_bucket_policy']['state']['policy']
        state=state.replace('each.value.arn','var.state_bucket').replace('each.key','var.environment')
        for environment in ('dev','prod'):
            bucket=f'arn:aws:s3:::e1-wp4-{environment}-{ACCOUNT}-{REGION}'
            sb=f'arn:aws:s3:::e1-lifecycle-{environment}-{ACCOUNT}-{REGION}'
            variables={k:{'default':v} for k,v in dict(account_id=ACCOUNT,region=REGION,admin_arn=f'arn:aws:iam::{ACCOUNT}:role/security-admin',environment=environment,bucket=bucket,state_bucket=sb,dev_operator_arn=None).items()}
            locals_={name:value for name,value in compute['locals'].items() if name in ('wp4d_bucket_readers','wp4d_bucket_writers','e2_lifecycle_writers','evidence_bucket')}
            locals_.update(wp4d_active={},wp4=wp4,state=state,evidence=compute['resource']['aws_s3_bucket_policy']['evidence']['policy'])
            path.write_text(json.dumps(dict(variable=variables,locals=locals_)))
            expression='jsonencode({wp4=jsondecode(local.wp4),state=jsondecode(local.state),evidence=jsondecode(local.evidence)})'
            # wp4/state already jsonencode strings; decode only the final outputs.
            result=subprocess.run([terraform,'console','-no-color'],input=expression+'\n',capture_output=True,text=True,cwd=directory,env=env,timeout=30)
            assert result.returncode==0,result.stderr
            policies=console_json(result.stdout)
            delivery='deploy-dev' if environment=='dev' else 'promote-prod'
            for identity in (delivery,'emergency-'+environment):
                role=f'arn:aws:iam::{ACCOUNT}:role/e1-request-{identity}'
                prefix='delivery/'+environment+'/' if identity==delivery else 'recovery/'+environment+'/recovery/emergency/'
                public=bucket+'/'+prefix+'11111111-1111-4111-8111-111111111111/public.json'
                assert not denied(policies['wp4'],'s3:GetObject',public,role)
                assert denied(policies['wp4'],'s3:GetObject',public.replace('public.json','receipt.json'),role)
                assert denied(policies['wp4'],'s3:PutObject',public,role)
            for identity in ('infra-'+environment,'infra-high-risk-'+environment):
                role=f'arn:aws:iam::{ACCOUNT}:role/e1-request-{identity}'
                public=sb+'/operations/environment-lifecycle/'+identity+'/11111111-1111-4111-8111-111111111111/public.json'
                assert not denied(policies['state'],'s3:GetObject',public,role)
                assert denied(policies['state'],'s3:GetObject',public.replace('public.json','completed.json'),role)
                assert denied(policies['state'],'s3:PutObject',public,role)
            role=f'arn:aws:iam::{ACCOUNT}:role/e1-request-plan-{environment}'
            ownstate=sb+f'/e1/lifecycle/{environment}/apps/terraform.tfstate'
            assert not denied(policies['state'],'s3:GetObject',ownstate,role)
            assert denied(policies['state'],'s3:PutObject',ownstate,role)
            assert denied(policies['state'],'s3:GetObject',sb+'/requests/infra-'+environment+'/internal.json',role)
            role=f'arn:aws:iam::{ACCOUNT}:role/e1-request-release'
            public=f'arn:aws:s3:::demo-release-artifacts-{ACCOUNT}/qualifications/demo-api/operations/11111111-1111-4111-8111-111111111111/public.json'
            assert not denied(policies['evidence'],'s3:GetObject',public,role)
            assert denied(policies['evidence'],'s3:GetObject',public.replace('public.json','internal.json'),role)
            assert denied(policies['evidence'],'s3:PutObject',public,role)
            print(environment+': actual protected bucket public/read/write isolation PASS')

if __name__=='__main__':main()
