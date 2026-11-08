"""Provider-free Terraform console fixtures; no init, provider or backend block."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]


def main():
    authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
    module=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    local=module['locals'];local.pop('wp3_role_arns')
    # Evaluate the actual generated role-policy expression in both branches.
    trust=module['resource']['aws_iam_role']['execution']['assume_role_policy'][2:-1]
    local['evaluated_trust']='${{ for key, node in local.nodes : key => '+trust.replace('each.key','key').replace('each.value','node')+' }}'
    variables=module['variable']
    for name,value in dict(authority=authority,account_id='111122223333',region='us-east-1',admin_arn='arn:aws:iam::111122223333:role/SecurityAdmin').items():
        variables[name]['default']=value
    contract=authority['internal_release'];installs={};runtimes={}
    for binding,v in contract['selected'].items():
        cls,consumer=binding.split('/')
        installs[binding]=dict(authority['control_bundles']['consumer_references'][binding],
            version_id='fixture-version',installation='VERIFIED',readback='EXACT_VERSION_BYTES_VERIFIED',
            version_origin='CONDITIONAL_WRITE_RETURN',publisher='SECURITY_ADMIN_EXTERNAL_BOOTSTRAP',
            configuration=contract['support_sha256'],bucket='e1-control-bundles-111122223333-us-east-1')
        suffix='build' if binding=='build/release' else binding.replace('/','-')
        runtimes[binding]=dict(owner='SECURITY_ROOT_OWNED',approval='ADMIN_VERIFIED',binding=binding,
            support_sha256=contract['support_sha256'],uri='111122223333.dkr.ecr.us-east-1.amazonaws.com/e1-controller-'+suffix+'@sha256:'+'a'*64)
    for key,v in contract['workers'].items():
        runtimes['payload/'+key]=dict(owner='SECURITY_ROOT_OWNED',approval='ADMIN_VERIFIED',binding='payload/'+key,
            role=v['role'],support_sha256=contract['support_sha256'],uri='111122223333.dkr.ecr.us-east-1.amazonaws.com/e1-payload-'+key+'@sha256:'+'b'*64)
    expression='jsonencode({ controllers = keys(local.wp3_active), workers = keys(local.payloads), skeleton = length(local.nodes), gateway_instances = keys(local.gateways), project_instances = keys(local.projects), trust = local.evaluated_trust })'
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','TF_','TERRAGRUNT','BOTO','AMAZON'))}
    with tempfile.TemporaryDirectory(prefix='e1-wp3c-console-') as tmp:
        path=Path(tmp);(path/'main.tf.json').write_text(json.dumps({'variable':variables,'locals':local},indent=2))
        def evaluate(i,r):
            (path/'fixture.tfvars.json').write_text(json.dumps(dict(installations=i,runtime_approvals=r)))
            result=subprocess.run(['terraform','-chdir='+tmp,'console','-no-color','-var-file=fixture.tfvars.json'],input=expression+'\n',text=True,capture_output=True,env=env,timeout=30)
            if result.returncode or 'Error:' in result.stderr:raise AssertionError(result.stderr)
            return json.loads(json.loads(result.stdout))
        canonical=evaluate({},{});inert_trust=canonical.pop('trust')
        assert all(json.loads(v)['Statement'][0]['Effect']=='Deny' for v in inert_trust.values())
        assert canonical==dict(controllers=[],workers=[],skeleton=18,gateway_instances=[],project_instances=[])
        positive=evaluate(installs,runtimes)
        active_trust=positive.pop('trust')
        assert {k for k,v in active_trust.items() if json.loads(v)['Statement'][0]['Effect']=='Allow'}=={'build/release','request-gateway/release'}
        assert positive['controllers']==sorted(contract['selected']) and positive['workers']==['dotnet','image','probe']
        count=2
        for binding in installs:
            for key,bad in [('class','status'),('consumer','wrong'),('sha256','0'*64),('key','bundles/latest.json'),('version_id',None),('version_id','latest'),('version_id',' padded '),('readback','UNVERIFIED'),('configuration','0'*64),('publisher','REQUESTER')]:
                mutant=copy.deepcopy(installs);mutant[binding][key]=bad
                # A status class mutation must actually change status as well.
                if key=='class' and installs[binding][key]==bad:mutant[binding][key]='build'
                result=evaluate(mutant,runtimes);assert binding not in result['controllers'],(binding,key,result);count+=1
        for binding in runtimes:
            mutant=copy.deepcopy(runtimes);mutant[binding]['uri']=mutant[binding]['uri'].split('@')[0]+':latest'
            result=evaluate(installs,mutant)
            if binding.startswith('payload/'):
                assert 'build/release' not in result['controllers'] and not result['workers']
            else:assert binding not in result['controllers']
            count+=1
        print(json.dumps(dict(checks=count,canonical=canonical,fixture=positive,providers='NOT_INITIALIZED',live='UNVERIFIED_NOT_DEPLOYED'),indent=2))


if __name__=='__main__':main()
