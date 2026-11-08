"""Evaluate actual generated DEV handoff/SNS expressions, no provider/init."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(HERE.parent/'security_root'),str(ROOT)]
from terraform_console import decode
ACCOUNT='111122223333';REGION='us-east-1';ADMIN='arn:aws:iam::'+ACCOUNT+':role/SeparateAdmin';OP='arn:aws:iam::'+ACCOUNT+':role/DemoDevOperator'

def console(expression,environment,operator,wp4=False):
    expression=expression[2:-1].replace('each.value.arn','local.bucket_arn').replace('each.key','local.environment')
    expression=expression.replace('aws_s3_bucket.wp4d[local.environment].arn','local.bucket_arn')
    locals_value=dict(environment=environment,bucket_arn=f'arn:aws:s3:::e1-lifecycle-{environment}-{ACCOUNT}-{REGION}')
    if wp4:
        source=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())['locals']
        locals_value.update({k:source[k] for k in ('wp4d_bucket_readers','wp4d_bucket_writers','e2_lifecycle_writers')})
        locals_value['wp4d_active']={}
    variables={name:dict(type='any',default=value) for name,value in dict(account_id=ACCOUNT,region=REGION,admin_arn=ADMIN,dev_operator_arn=operator).items()}
    with tempfile.TemporaryDirectory(prefix='native-backend-static-') as directory:
        Path(directory,'main.tf.json').write_text(json.dumps(dict(variable=variables,locals=locals_value)),encoding='utf-8')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','TF_','TERRAGRUNT')) and 'PROXY' not in k.upper()}
        env.update(AWS_EC2_METADATA_DISABLED='true',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,CHECKPOINT_DISABLE='1')
        run=subprocess.run(['terraform','console','-no-color'],input='jsonencode(jsondecode('+expression+'))\n',text=True,capture_output=True,cwd=directory,env=env,timeout=30)
        assert run.returncode==0,run.stderr
        return decode(run.stdout)

new=json.loads((ROOT/'terraform/infra/security/modules/lifecycle_foundations/main.tf.json').read_text())['resource']['aws_s3_bucket_policy']['state']['policy']
old=json.loads(subprocess.check_output(['git','show','98fa727032b8837198f8b07e5a09a086359db182:terraform/infra/security/modules/lifecycle_foundations/main.tf.json'],cwd=ROOT))['resource']['aws_s3_bucket_policy']['state']['policy']
for env in ('dev','prod'):
    baseline=console(old,env,None)
    assert console(new,env,None)==baseline,'null mode must preserve authority'
    if env=='prod':assert console(new,env,OP)==baseline,'PROD changed with DEV operator'
policy=console(new,'dev',OP);rows={r['Sid']:r for r in policy['Statement']}
writer=rows['E16ExclusiveDevRuntimeWriter'];assert len(writer['Resource'])==10
assert all('/dev/' in r and not any(x in r for x in ('/shared/','/secrets/','/prod/','/security/')) for r in writer['Resource'])
assert writer['Condition']['ArnNotEquals']['aws:PrincipalArn']==OP
assert rows['E16RuntimeLockDelete']['Resource']==[r for r in writer['Resource'] if r.endswith('.tflock')]
assert rows['E16NoOtherDevObjects']['NotResource']==writer['Resource']
assert rows['E16RetainStateObjects']['Effect']=='Deny'
assert rows['E16RetainStateObjects']['Resource']==[r for r in writer['Resource'] if not r.endswith('.tflock')]
assert rows['E16NoBackendAdministration']['Effect']=='Deny'
assert 's3:DeleteObjectVersion' not in rows['E16NoBackendAdministration']['NotAction']
assert 's3:PutBucketPolicy' not in rows['E16NoBackendAdministration']['NotAction']
# Real Terraform interpolation verifies unchanged PROD alert name.
root=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
for label,env_expr in (('nat_failure_queue','each.value.environment'),('nat_async_delivery','local.wp4d_active[each.key].environment'),('nat_event_dlq_delivery','each.key')):
    expression=root['resource']['aws_cloudwatch_metric_alarm'][label]['alarm_actions'][0]
    for env in ('dev','prod'):
        replaced=expression[2:-1].replace(env_expr,json.dumps(env))
        # Wrap the native string as JSON, using the same provider-free console.
        result=console('${jsonencode('+replaced+')}',env,None)
        assert result==f'arn:aws:sns:{REGION}:{ACCOUNT}:demo-{env}'+('-shared' if env=='dev' else '')+'-alerts',result
print('Native operator actual Terraform policy: null unchanged, PROD unchanged, exclusive 5-state/lock scope; DEV SNS matches shared root PASS')

# Evaluate the complete generated protected-evidence policy, including WP6
# extensions. Nullable selection and PROD must preserve all earlier statements.
observed=root['resource']['aws_s3_bucket_policy']['wp4d']['policy']
previous=json.loads(subprocess.check_output(['git','show','98fa727032b8837198f8b07e5a09a086359db182:terraform/infra/security/modules/controller_compute/main.tf.json'],cwd=ROOT))['resource']['aws_s3_bucket_policy']['wp4d']['policy']
for env in ('dev','prod'):
    baseline=console(previous,env,None,wp4=True)
    assert console(observed,env,None,wp4=True)==baseline,'evidence null policy changed'
    if env=='prod':assert console(observed,env,OP,wp4=True)==baseline,'PROD evidence changed'
observations={r['Sid']:r for r in console(observed,'dev',OP,wp4=True)['Statement']}
assert 'ExternalOnlyPublic' in observations and 'E2ConditionalUpdates' in observations
assert observations['E16ObservationObjects']['Action']==['s3:GetObject','s3:GetObjectVersion']
assert len(observations['E16ObservationObjects']['Resource'])==4
assert observations['E16ObservationOnly']['NotResource']==observations['E16ObservationObjects']['Resource']
assert OP not in observations['Writers']['Condition']['ArnNotEquals']['aws:PrincipalArn']
assert OP in observations['Readers']['Condition']['ArnNotEquals']['aws:PrincipalArn']
print('Native operator actual protected E2/E13 read-only policy: old/null/PROD preserved; no write authority PASS')
