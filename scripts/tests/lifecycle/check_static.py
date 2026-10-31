"""Evaluate actual WP5 Terraform gates/policies/trust without init/providers."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'security_root'),str(HERE.parent/'authority'),str(HERE.parents[2]),str(HERE.parent/'wp4d')]
from terraform_console import decode as console_json
import wp5
import wp5_iam
from test_lifecycle import DOC,ACCOUNT,REGION,projection

def main():
    terraform=shutil.which('terraform')
    if not terraform:raise SystemExit('WP5_TERRAFORM_STATIC_UNAVAILABLE')
    tf=json.loads((wp5.ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    locals_={k:v for k,v in tf['locals'].items() if k.startswith('wp5_')}
    locals_.update(wp4d_active={},wp3_active={},wp3_build_trust={},wp3_trust={})
    policy='jsonencode(local.wp5_policies[key])'
    trust=tf['resource']['aws_iam_role']['execution']['assume_role_policy'][2:-1].replace('each.value','v').replace('each.key','key')
    expression='jsonencode({active=keys(local.wp5_active),chunks=local.wp5_chunks,policies={for key,v in local.wp5_active:key=>jsondecode('+policy+')},trusts={for key,v in local.wp5_active:key=>jsondecode('+trust+')}})'
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','BOTO','TF_','TERRAGRUNT')) and 'PROXY' not in k.upper()}
    env.update(AWS_EC2_METADATA_DISABLED='true',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,CHECKPOINT_DISABLE='1',TF_IN_AUTOMATION='1')
    i,r,b=projection();cases=[('undeployed',{},{},{}),('all-synthetic',i,r,b)]
    missing=copy.deepcopy(i);missing.pop('environment-lifecycle/infra-dev');cases.append(('missing-controller',missing,r,b))
    for field,value in (('version_id','latest'),('readback','UNVERIFIED'),('sha256','f'*64)):
        bad=copy.deepcopy(i)
        for item in bad.values():item[field]=value
        cases.append(('bad-install-'+field,bad,r,b))
    bad=copy.deepcopy(b)
    for item in bad.values():item['configuration']['active_contracts']=[]
    cases.append(('revoked-contract',i,r,bad))
    bad=copy.deepcopy(b)
    for item in bad.values():item['configuration']['layers']['global']['backend']['key']='attacker'
    cases.append(('wrong-backend',i,r,bad))
    with tempfile.TemporaryDirectory(prefix='e1-wp5-static-') as directory:
        path=Path(directory)/'main.tf.json'
        for name,install,image,binding in cases:
            variables={k:{'type':'any','default':v} for k,v in dict(authority=DOC,account_id=ACCOUNT,region=REGION,
                dev_cicd_installation_only=False,
                wp5_installations=install,wp5_runtime_approvals=image,wp5_environment_bindings=binding).items()}
            path.write_text(json.dumps(dict(variable=variables,locals=locals_)),encoding='utf-8')
            result=subprocess.run([terraform,'console','-no-color'],input=expression+'\n',capture_output=True,text=True,cwd=directory,env=env,timeout=30)
            if result.returncode:raise AssertionError(name+': '+result.stderr)
            try:actual=console_json(result.stdout)
            except json.JSONDecodeError:
                raise AssertionError((name,result.stdout[:300],result.stderr[-3000:]))
            assert all(len(chunk['policy'])<=6144 for chunk in actual['chunks'].values()),'IAM managed policy size'
            assert all(sum(chunk['role']==v['role'] for chunk in actual['chunks'].values())<=10 for v in DOC['wp5']['selected'].values()),'IAM attachment ceiling'
            assert actual['active']==wp5.creation_supported(DOC,install,image,binding,ACCOUNT,REGION),(name,actual['active'])
            for key in actual['active']:
                members=copy.deepcopy(binding[key]['resources']);members['_sql_launch']=binding[key]['sql_launch']
                expected=wp5_iam.policy(key,ACCOUNT,REGION,members,DOC['wp5']['selected'][key]['package_sha256'],install[key]['version_id'])
                if actual['policies'][key]!=expected:
                    missing=[s for s in expected['Statement'] if s not in actual['policies'][key]['Statement']]
                    extra=[s for s in actual['policies'][key]['Statement'] if s not in expected['Statement']]
                    raise AssertionError((name,key,'policy parity',missing,extra))
                statement=actual['trusts'][key]['Statement'][0]
                assert statement['Principal']=={'Service':'lambda.amazonaws.com' if key.startswith('request-gateway/') else 'codebuild.amazonaws.com'}
                assert 'Federated' not in statement['Principal']
            print(name+': actual Terraform gate/policy/trust PASS ('+str(len(actual['active']))+' synthetic bindings)')
        result=subprocess.run([terraform,'validate','-no-color'],capture_output=True,text=True,cwd=directory,env=env,timeout=30)
        if result.returncode:raise AssertionError(result.stderr)
        print('Disposable provider-free Terraform structure PASS')

if __name__=='__main__':main()
