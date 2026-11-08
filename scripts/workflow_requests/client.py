"""Pinned entry process: bounded requests, short-lived OIDC, sanitized completion.

No AWS call on import. CLI diagnostics never include payloads, JWTs, credentials,
Terraform output, storage bytes or provider errors. No mutation retries/fallback.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.workflow_requests import contract as c

def configuration(identity,raw):
    value=c.decode(raw,65536)
    c.closed(value,('identity','environment','account','region','workflow_commit','active','governance','gateway_version','plan_binding'))
    c.require(value['identity']==identity and value['environment']==c.environment(identity))
    c.match('[0-9]{12}',value['account']);c.match('[a-z]{2}(?:-[a-z]+)+-[0-9]',value['region'])
    c.subject(identity,value['workflow_commit'])
    c.require(value['active'] is True and value['governance']=='ADMIN_VERIFIED_G1_G9')
    if identity.startswith('plan-'):
        c.require(value['gateway_version'] is None)
        validate_plan_binding(identity,value)
    else:c.match('[1-9][0-9]*',value['gateway_version']);c.require(value['plan_binding'] is None)
    return value

validate_plan_binding=c.validate_plan_binding

class AWS:
    def __init__(self,config):
        self.config=config
        self.env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','TF_','TERRAGRUNT','GIT_','GH_','LD_','DYLD_')) and k not in ('BASH_ENV','ENV')}
        self.env.update(AWS_REGION=config['region'],AWS_DEFAULT_REGION=config['region'],AWS_EC2_METADATA_DISABLED='true',
            AWS_MAX_ATTEMPTS='1',AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,AWS_PAGER='')
    def call(self,service,action,args):
        run=subprocess.run(['aws',service,action,'--region',self.config['region'],'--output','json',*args],
            env=self.env,stdin=subprocess.DEVNULL,capture_output=True,timeout=45)
        c.require(run.returncode==0 and len(run.stdout)<=1048576)
        return json.loads(run.stdout)
    def acquire(self,token):
        role='arn:aws:iam::'+self.config['account']+':role/e1-request-'+self.config['identity']
        response=self.call('sts','assume-role-with-web-identity',['--role-arn',role,'--role-session-name','e1-request',
            '--web-identity-token',token,'--duration-seconds','900'])
        creds=response['Credentials']
        self.env.update(AWS_ACCESS_KEY_ID=creds['AccessKeyId'],AWS_SECRET_ACCESS_KEY=creds['SecretAccessKey'],AWS_SESSION_TOKEN=creds['SessionToken'])
        observed=self.call('sts','get-caller-identity',[])
        c.require(observed['Account']==self.config['account'] and observed['Arn'].startswith(
            'arn:aws:sts::'+self.config['account']+':assumed-role/e1-request-'+self.config['identity']+'/'))
    def invoke(self,request):
        identity=self.config['identity']
        endpoint=f'arn:aws:lambda:{self.config["region"]}:{self.config["account"]}:function:e1-gateway-{identity}:{self.config["gateway_version"]}'
        with tempfile.TemporaryDirectory(prefix='e1-request-') as directory:
            payload=Path(directory)/'request.json';payload.write_bytes(c.canonical(request))
            output=Path(directory)/'response.json'
            result=self.call('lambda','invoke',['--function-name',endpoint,'--invocation-type','RequestResponse',
                '--payload','fileb://'+str(payload),str(output)])
            c.require(result.get('StatusCode')==200 and 'FunctionError' not in result)
            value=c.decode(output.read_text())
            operation=value.get('operation_id',value.get('operation'))
            c.match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',operation)
            if identity!='release':c.require(operation==request['operation_id'])
            return operation
    def status(self,operation):
        bucket,key=c.status_location(self.config['identity'],self.config['account'],self.config['region'],operation)
        with tempfile.TemporaryDirectory(prefix='e1-result-') as directory:
            output=Path(directory)/'public.json'
            try:self.call('s3api','get-object',['--bucket',bucket,'--key',key,str(output)])
            except Exception:return None # Absence/transient error never proves success.
            return c.result(self.config['identity'],operation,c.decode(output.read_text()))
    def preflight(self):
        p=self.config['plan_binding']['resources']
        for action,args in [('describe-clusters',['--clusters',p['cluster']]),('describe-services',['--cluster',p['cluster'],'--services',*p['services']])]:
            response=self.call('ecs',action,args);c.require(not response.get('failures'))
            field='clusters' if action=='describe-clusters' else 'services'
            c.require(len(response[field])==(1 if field=='clusters' else 2))
            if field=='clusters':c.require(response[field][0]['clusterArn']==p['cluster'])
            else:c.require({s['serviceArn'] for s in response[field]}==set(p['services']) and all(s['clusterArn']==p['cluster'] for s in response[field]))
        for action,key,arg in [('describe-listeners','listener','--listener-arns'),('describe-rules','rule','--rule-arns'),('describe-target-groups','targets','--target-group-arns')]:
            response=self.call('elbv2',action,[arg,*([p[key]] if type(p[key]) is str else p[key])])
            collection,field={'listener':('Listeners','ListenerArn'),'rule':('Rules','RuleArn'),'targets':('TargetGroups','TargetGroupArn')}[key]
            expected=[p[key]] if type(p[key]) is str else p[key]
            c.require(len(response[collection])==len(expected) and {v[field] for v in response[collection]}==set(expected))
        # Configuration metadata suffices; do not acquire a code download URL.
        response=self.call('lambda','get-function-configuration',['--function-name',p['cleanup_function']])
        c.require(response['FunctionArn']==p['cleanup_function'])
        for role in p['roles']:
            c.require(self.call('iam','get-role',['--role-name',role.rsplit('/',1)[1]])['Role']['Arn']==role)
        return {'state':'SUCCESS'}
    def plan(self,layer):
        p=self.config['plan_binding']['layers'][layer]
        directory=Path(__file__).resolve().parents[2]/p['root']
        version=subprocess.run(['terraform','version','-json'],env=self.env,capture_output=True,timeout=15)
        c.require(version.returncode==0 and json.loads(version.stdout)['terraform_version']=='1.13.4')
        with tempfile.TemporaryDirectory(prefix='e1-plan-') as tmp:
            variables=Path(tmp)/'variables.json';variables.write_bytes(c.canonical(p['variables']))
            out=Path(tmp)/'plan'
            for args in [['init','-input=false','-lockfile=readonly',*['-backend-config='+k+'='+v for k,v in p['backend'].items()]],
                         ['plan','-input=false','-lock=false','-out='+str(out),'-var-file='+str(variables)]]:
                run=subprocess.run(['terraform',*args],cwd=directory,env=self.env,stdin=subprocess.DEVNULL,capture_output=True,timeout=600)
                c.require(run.returncode==0)
            run=subprocess.run(['terraform','show','-json',str(out)],cwd=directory,env=self.env,capture_output=True,timeout=45)
            c.require(run.returncode==0 and len(run.stdout)<=16777216)
            plan=json.loads(run.stdout);c.require(not plan.get('errored') and not plan.get('deferred_changes'))
            return {'state':'PLANNED','source_commit':self.config['workflow_commit'],
                'changes':len([x for x in plan.get('resource_changes',[]) if x['change']['actions']!=['no-op']])}

def execute(identity,raw,config,claims,aws,deadline=1800):
    value=c.request(identity,raw)
    c.context(identity,claims,config)
    if identity=='release':c.require(value['source_commit']==claims['sha'])
    if identity.startswith('plan-'):
        return aws.preflight() if value['operation']=='preflight' else aws.plan(value['layer'])
    operation=aws.invoke(value) # Exactly once. A missing ACK cannot be retried here.
    end=time.monotonic()+deadline
    while time.monotonic()<end:
        result=aws.status(operation)
        if result is not None:
            c.require(result['state'] in ('SUCCESS','PLANNED'))
            if identity=='release':c.require(result['source_commit']==value['source_commit'])
            return result
        time.sleep(5)
    raise RuntimeError('E1_REQUEST_COMPLETION_UNVERIFIED')

def main():
    identity=sys.argv[1];config=configuration(identity,os.environ['E1_REQUEST_CONFIGURATION'])
    # Input validation and missing installation/governance fail before OIDC request.
    raw=os.environ['E1_REQUEST'];c.request(identity,raw)
    endpoint=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    req=urllib.request.Request(endpoint+('&' if '?' in endpoint else '?')+'audience='+c.AUDIENCE,
        headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urllib.request.urlopen(req,timeout=10) as response:token=json.loads(response.read(32769))['value']
    claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
    c.context(identity,claims,config)
    aws=AWS(config);aws.acquire(token)
    value=execute(identity,raw,config,claims,aws)
    # Only sanitized IDs/counts/status are printed or exported.
    print(json.dumps(value,sort_keys=True))
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:
            for key in ('operation_id','release_id','state'):
                if value.get(key) is not None:stream.write(key+'='+value[key]+'\n')

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('E1_PROTECTED_WORKFLOW_FAILED') from None
