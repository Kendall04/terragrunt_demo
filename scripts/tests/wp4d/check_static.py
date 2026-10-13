"""Evaluate actual WP4D Terraform gates/policies without providers or a backend.

Uses installed Terraform console/validate only in disposable local configuration.
Synthetic installation receipts exercise expressions; they are not AWS evidence.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent/'security_root'), str(HERE.parents[2]),
               str(HERE.parent/'authority')]
from terraform_console import decode as console_json
import wp4d
from test_wp4d import installed_projection, ACCOUNT, REGION


def main():
    terraform = shutil.which('terraform')
    if not terraform:
        raise SystemExit('WP4D_STATIC_TERRAFORM_UNAVAILABLE')
    authority = json.loads((wp4d.ROOT/'terraform/infra/security/authority.json').read_text())
    tf = json.loads((wp4d.ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    locals_ = {key: value for key, value in tf['locals'].items() if key in (
        'wp4d_contract', 'wp4d_candidates', 'wp4d_ready', 'wp4d_active', 'wp4d_policy_templates',
        'wp4d_project_names', 'wp4d_cleanup_names', 'wp4d_config')}
    locals_['evidence_bucket'] = f'e1-evidence-{ACCOUNT}-{REGION}'
    policy = tf['resource']['aws_iam_role_policy']['wp4d']['policy'][2:-1].replace('each.value', 'v').replace('each.key', 'key')
    trust = tf['resource']['aws_iam_role']['wp4d_reserved']['assume_role_policy'][2:-1].replace('each.value', 'v')
    expression = 'jsonencode({active=keys(local.wp4d_active), policies={for key,v in local.wp4d_active:key=>jsondecode(' + policy + ')}, trusts={for key,v in local.wp4d_active:key=>jsondecode(' + trust + ')}, configurations={for key,value in local.wp4d_config:key=>jsondecode(value)}})'
    environment = {k:v for k,v in os.environ.items() if not k.upper().startswith(
        ('AWS', 'AMAZON', 'BOTO', 'TF_', 'TERRAGRUNT')) and 'PROXY' not in k.upper()}
    environment.update(AWS_EC2_METADATA_DISABLED='true', AWS_CONFIG_FILE=os.devnull,
                       AWS_SHARED_CREDENTIALS_FILE=os.devnull, CHECKPOINT_DISABLE='1', TF_IN_AUTOMATION='1')
    installs, images, bindings = installed_projection(authority)
    cases = [('undeployed', {}, {}, {}), ('all-synthetic', installs, images, bindings)]
    missing = copy.deepcopy(installs); missing.pop('cleanup-recovery/cleanup-dev')
    cases.append(('missing-cleanup', missing, images, bindings))
    for field, bad in [('version_id', 'latest'), ('readback', 'UNVERIFIED'), ('sha256', 'f'*64)]:
        wrong = copy.deepcopy(installs)
        for record in wrong.values(): record[field] = bad
        cases.append(('bad-install-'+field, wrong, images, bindings))
    wrong = copy.deepcopy(bindings); del wrong['dev']['nat_slots'][0]['spec']['ami']
    cases.append(('incomplete-launch', installs, images, wrong))
    wrong = copy.deepcopy(bindings); wrong['dev']['colors']['blue']['roles']['task'] = bindings['prod']['colors']['blue']['roles']['task']
    cases.append(('cross-environment-role', installs, images, wrong))
    network = {key:copy.deepcopy(value) for key,value in bindings['dev'].items() if key in wp4d.NAT_ENV_FIELDS}
    network.update(schema='E1_WP4D_PROTECTED_NAT_NETWORK_V1',repository='demo-dev-shared-demo-ms')
    for slot,side in zip(network['nat_slots'],('a','b')):slot['asg']='demo-dev-asg-nat-'+side
    cases.append(('dev-network-bootstrap',installs,images,{'dev':network}))
    wrong=copy.deepcopy(network);wrong['nat_slots'][0]['asg']='foreign-asg'
    cases.append(('dev-network-foreign-asg',installs,images,{'dev':wrong}))
    cases.append(('nat-network-not-prod',installs,images,{'prod':network}))
    with tempfile.TemporaryDirectory(prefix='e1-wp4d-provider-free-') as directory:
        path = Path(directory)/'main.tf.json'
        for name, i, r, b in cases:
            variables = {key:{'type':'any', 'default': value} for key,value in {
                'authority': authority, 'account_id': ACCOUNT, 'region': REGION,
                'wp4d_installations': i, 'wp4d_runtime_approvals': r,
                'wp4d_environment_bindings': b}.items()}
            path.write_text(json.dumps({'variable':variables, 'locals':locals_}), encoding='utf-8')
            result = subprocess.run([terraform, 'console', '-no-color'], input=expression+'\n',
                                    text=True, capture_output=True, cwd=directory, env=environment, timeout=30)
            if result.returncode:
                raise AssertionError(name+': '+result.stderr)
            observed = console_json(result.stdout)
            assert observed['active'] == wp4d.creation_supported(authority, i, r, b, ACCOUNT, REGION), (name,observed['active'],wp4d.creation_supported(authority,i,r,b,ACCOUNT,REGION))
            for binding in observed['active']:
                selected = authority['wp4d']['selected'][binding]
                config=observed['configurations'][binding]
                assert config['binding']==binding and config['nat_slots']==b[config['environment']]['nat_slots']
                if binding.startswith('nat-recovery/nat-dev/'):
                    assert config['resources']=={}
                    assert len('E1_PROTECTED_CONFIGURATION'.encode())+len(json.dumps(config,separators=(',',':'),ensure_ascii=False).encode())<=4096, 'Lambda configuration too large'
                else:assert config['resources']==b[config['environment']]
                env = selected['environment']
                if b[env].get('schema') == 'E1_WP4D_PROTECTED_NAT_NETWORK_V1':
                    resources = {'package_sha256':selected['package_sha256'],'name':selected['name'],
                        'nat_slots':[{**slot,'instance_profile':slot['spec']['instance_profile']} for slot in b[env]['nat_slots']]}
                else:
                    env = selected['environment']; colors = b[env]['colors']
                    cluster = colors['blue']['cluster']
                    resources = {'name': selected['name'], 'project': 'e1-controller-'+binding.split('/')[1],
                        'package_sha256': selected['package_sha256'], 'cluster_arn': cluster,
                        'cluster_name': cluster.split('/')[1], 'listener': colors['blue']['listener'],
                        'candidate_rule': colors['blue']['candidate_rule'], 'repository': b[env]['repository'],
                        'cleanup': {'rule_arn':f'arn:aws:events:{REGION}:{ACCOUNT}:rule/'+b[env]['cleanup']['rule'],
                                    'function_arn':b[env]['cleanup']['function_arn']},
                        'nat_slots': [{**s, 'instance_profile':s['spec']['instance_profile']} for s in b[env]['nat_slots']],
                        'colors': {color:{'service_arn':f'arn:aws:ecs:{REGION}:{ACCOUNT}:service/'+cluster.split('/')[1]+'/'+member['service'],
                                         'target_group':member['target_group'], 'family':f'demo-{env}-app-api-{color}',
                                         'task_role':member['roles']['task'], 'execution_role':member['roles']['execution']}
                                   for color,member in colors.items()}}
                assert observed['policies'][binding] == wp4d.policy(binding, resources, ACCOUNT, REGION, i[binding]['version_id']), binding
                statement = observed['trusts'][binding]['Statement'][0]
                service = 'lambda.amazonaws.com' if selected['engine'] == 'LAMBDA' else 'codebuild.amazonaws.com'
                assert statement['Principal'] == {'Service': service}
                if selected['engine'] == 'CODEBUILD':
                    assert statement['Condition'] == {'StringEquals':{'aws:SourceAccount':ACCOUNT},
                        'ArnEquals':{'aws:SourceArn':f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/'+selected['name']}}
            print(name+': Terraform gate/policy/trust parity PASS ('+str(len(observed['active']))+' synthetic bindings)')
        result = subprocess.run([terraform, 'validate', '-no-color'], cwd=directory, env=environment,
                                text=True, capture_output=True, timeout=30)
        if result.returncode: raise AssertionError(result.stderr)
        print('Disposable provider-free Terraform structure PASS')
        launch = json.loads((wp4d.ROOT/'terraform/modules/target/dev/global/wp5-nat.tf.json').read_text())
        condition=launch['variable']['protected_nat_launch']['validation']['condition']
        for slots,expected in (({},True),({'a':{},'b':{}},True),({'a':{}},False),({'a':{},'prod':{}},False)):
            path.write_text(json.dumps({'variable':{'protected_nat_launch':{'type':'any','default':slots}},
                                       'locals':{'valid':condition}}),encoding='utf-8')
            result=subprocess.run([terraform,'console','-no-color'],input='jsonencode(local.valid)\n',text=True,
                capture_output=True,cwd=directory,env=environment,timeout=30)
            assert result.returncode==0,result.stderr
            assert console_json(result.stdout)==expected,(slots,result.stdout)
        print('Original DEV NAT exact two-slot Terraform validation PASS')
        root=json.loads((wp4d.ROOT/'terraform/infra/security/main.tf.json').read_text())
        names=('dev_nat_launch_inputs','dev_nat_installations','dev_nat_runtime_approvals','dev_nat_network_binding')
        for name in names:
            chosen=root['variable'][name]
            assert chosen['default'] in ({},None)
            good=({'dev/a':{'environment':'dev','account':ACCOUNT,'region':REGION}} if name=='dev_nat_launch_inputs' else
                  {'schema':'E1_WP4D_PROTECTED_NAT_NETWORK_V1','environment':'dev','account':ACCOUNT,'region':REGION} if name=='dev_nat_network_binding' else
                  {'nat-recovery/nat-dev/assign_eip':{}})
            bad=({'prod/a':{'environment':'prod','account':ACCOUNT,'region':REGION}} if name=='dev_nat_launch_inputs' else
                 {'schema':'E1_WP4D_PROTECTED_NAT_NETWORK_V1','environment':'prod','account':ACCOUNT,'region':REGION} if name=='dev_nat_network_binding' else
                 {'nat-recovery/nat-prod/assign_eip':{}})
            for value,expected in ((chosen['default'],True),(good,True),(bad,False)):
                path.write_text(json.dumps({'variable':{'aws_account_id':{'type':'string','default':ACCOUNT},
                    'aws_region':{'type':'string','default':REGION},name:{'type':'any','default':value}},
                    'locals':{'valid':chosen['validation']['condition']}}),encoding='utf-8')
                result=subprocess.run([terraform,'console','-no-color'],input='jsonencode(local.valid)\n',text=True,
                    capture_output=True,cwd=directory,env=environment,timeout=30)
                assert result.returncode==0,result.stderr
                assert console_json(result.stdout)==expected,(name,value,result.stdout)
        print('Security administrator NAT inputs: empty defaults, exact DEV acceptance, PROD rejection PASS')




if __name__ == '__main__':
    main()
