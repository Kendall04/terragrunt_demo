"""Installed WP5 runtime. No caller code, CLI arguments or build overrides.

Imported by approved images only. Tests replace ports; this module never starts
Terraform merely on import. Live provider/installation behavior is unverified.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from scripts.lifecycle import contract as c
from scripts.lifecycle import packages
from scripts.lifecycle.controller import Controller
from scripts.lifecycle.dev_down import check_data_consent
from scripts.lifecycle.exact_destroy import Execution as ExactDestroyExecution
from scripts.environment_mutation import Store, Authority, execute as arbitrate, domain

def teardown_readback(readback):
    """Require a complete refreshed values tree with no managed resources.

    A no-op refresh alone can describe remaining infrastructure. This is state/
    provider readback evidence, not an account-wide orphan inventory.
    """
    c.require(type(readback) is dict and type(readback.get('planned_values')) is dict,
            'teardown refreshed values required')
    values = readback['planned_values']
    c.require(type(values.get('root_module')) is dict, 'teardown root values required')
    def empty(module, depth=0):
        c.require(type(module) is dict and depth < 64, 'bounded teardown values tree')
        c.require(set(module) <= {'address', 'resources', 'child_modules'}, 'known values module')
        resources, children = module.get('resources', []), module.get('child_modules', [])
        c.require(type(resources) is list and type(children) is list, 'complete values collections')
        for resource in resources:
            c.require(type(resource) is dict and resource.get('mode') == 'data',
                    'managed resource remains after teardown')
        for child in children:
            empty(child, depth + 1)
    empty(values['root_module'])


class Records:
    def __init__(self, s3, bucket, prefix):self.s3,self.bucket,self.prefix=s3,bucket,prefix
    def get(self, key):
        try:
            result=self.s3.get_object(Bucket=self.bucket,Key=self.prefix+key+'.json')
            return json.loads(result['Body'].read(1048577))
        except Exception as exc:
            if getattr(exc,'response',{}).get('Error',{}).get('Code') in ('NoSuchKey','404'):return None
            raise
    def put(self, key, value):
        self.s3.put_object(Bucket=self.bucket,Key=self.prefix+key+'.json',
            Body=c.canonical(value),IfNoneMatch='*',ContentType='application/json')
    def read(self,key):return self.get(key+'/completed') or self.get(key+'/intent')
    def create(self,key,value):self.put(key+'/intent',value)
    def complete(self,key,value):self.put(key+'/completed',value)


class Packages:
    def __init__(self,s3,root):self.s3,self.root=s3,root
    def verify(self,reference):return packages.verify(self.s3,reference,self.root)


class Terraform:
    def __init__(self,root,ecs,protected,authority=None,request=None,exact_destroy=None):
        self.root,self.ecs,self.protected=Path(root),ecs,protected
        self.authority=authority
        self.exact_destroy=exact_destroy
        self.request=json.loads(c.canonical(request)) if request is not None else None
    def prepare(self,reference,layer,parameters):
        self.directory=self.root/layer['root'];self.layer=layer
        c.require(self.directory.is_relative_to(self.root) and self.directory.is_dir(),'installed working directory')
        c.require(not set(parameters)-set(layer['variables']),'installed parameter declaration')
        variables={**layer['variables'],**parameters}
        c.require(not any('password' in k.lower() or k.lower() in ('secret_value','connection_string') for k in variables),'no secret values in Terraform')
        (self.directory/'wp5.auto.tfvars.json').write_bytes(c.canonical(variables))
        self.environment={k:v for k,v in os.environ.items() if not k.startswith(('TF_','TERRAGRUNT','GIT_','GH_','LD_','DYLD_')) and k not in ('BASH_ENV','ENV','AWS_PROFILE','AWS_DEFAULT_PROFILE','AWS_SHARED_CREDENTIALS_FILE','AWS_CONFIG_FILE')}
        self.reference = json.loads(c.canonical(reference))
        self.environment.update(TF_WORKSPACE='default',TF_IN_AUTOMATION='1',TF_INPUT='0',TF_CLI_CONFIG_FILE=str(self.root/'terraformrc'),CHECKPOINT_DISABLE='1')
        (self.root/'terraformrc').write_text('provider_installation { filesystem_mirror { path = "/opt/e1/provider-mirror" } }\n')
        self.call(['init','-input=false','-lockfile=readonly',
                   *['-backend-config='+key+'='+value for key,value in layer['backend'].items()]])
    def call(self,args):
        if args[:1] == ['apply']:
            c.require(type(self.authority) is Authority, 'E2 mutation authority required')
            return self.authority.call(self._call,args)
        return self._call(args)
    def _call(self,args):
        if args[:1] == ['apply'] and getattr(self, 'destroy', False):
            self.check_destroy_seal()
            c.quiescent(self.observe(self.protected['environment']), self.protected['environment'])
            if self.protected['environment'] == 'dev' and self.layer['root'] == 'terraform/modules/target/dev/data':
                c.require(type(self.request) is dict and self.request.get('layer') == 'data'
                          and self.request.get('operation') == 'teardown'
                          and self.layer == self.protected['layers']['data'], 'exact DEV data request at dispatch')
                check_data_consent(self.request, self.protected, int(time.time()))
            if self.protected['environment'] == 'dev':
                c.require(type(self.exact_destroy) is ExactDestroyExecution, 'protected exact destroy approval handoff not installed')
                self.exact_destroy.before_dispatch(self)
        result=subprocess.run(['/opt/e1/bin/terraform',*args],cwd=self.directory,env=self.environment,
                              stdin=subprocess.DEVNULL,capture_output=True,timeout=900)
        c.require(result.returncode==0,'Terraform command failed; output withheld')
        c.require(len(result.stdout)<=16777216,'bounded Terraform output')
        return result.stdout
    def destroy_context(self):
        variables = self.directory / 'wp5.auto.tfvars.json'
        c.require(not variables.is_symlink() and variables.is_file(), 'exact variables file')
        c.require(self.environment.get('TF_WORKSPACE') == 'default', 'fixed workspace')
        workspace = self.directory / '.terraform' / 'environment'
        c.require(not workspace.exists() or (not workspace.is_symlink() and workspace.is_file()
                  and workspace.read_text().strip() == 'default'), 'no alternate workspace')
        return c.digest(c.canonical(dict(reference=self.reference, layer=self.layer,
            configuration=self.protected, variables_sha256=c.digest(variables.read_bytes()), workspace='default')))

    def binary_plan_digest(self):
        path = self.directory / 'wp5.tfplan'
        c.require(not path.is_symlink() and path.is_file() and 0 < path.stat().st_size <= 16777216,
                  'bounded regular saved plan')
        raw = path.read_bytes()
        c.require(0 < len(raw) <= 16777216, 'bounded saved plan bytes')
        return c.digest(raw)

    def check_destroy_seal(self):
        c.require(getattr(self, 'destroy_seal', None) is not None, 'saved destroy seal required')
        c.require(self.binary_plan_digest() == self.destroy_seal['binary_sha256']
                  and self.destroy_context() == self.destroy_seal['context_sha256'],
                  'saved binary or prepared context changed')

    def plan(self,destroy=False):
        self.destroy = destroy
        self.destroy_seal = None
        if destroy and self.protected['environment'] == 'dev' and self.exact_destroy is not None:
            c.require(type(self.exact_destroy) is ExactDestroyExecution, 'installed exact approval executor')
            return self.exact_destroy.load(self)
        self.call(['plan','-input=false','-out=wp5.tfplan',*(['-destroy'] if destroy else [])])
        before = self.binary_plan_digest() if destroy else None
        plan = json.loads(self.call(['show','-json','wp5.tfplan']))
        if destroy:
            c.require(before == self.binary_plan_digest(), 'binary changed during JSON inspection')
            self.destroy_seal = dict(binary_sha256=before, json_sha256=c.digest(c.canonical(plan)),
                                     context_sha256=self.destroy_context())
        return plan
    def observe(self,environment):
        cluster=self.protected['layers']['apps']['variables']['cluster_arn']
        names=['demo-'+environment+'-app-api-'+color+'-svc' for color in ('blue','green')]
        clusters=self.ecs.describe_clusters(clusters=[cluster])
        if not clusters.get('clusters'):
            c.require(clusters.get('failures')==[{'arn':cluster,'reason':'MISSING'}],'authoritative exact cluster absence')
            return {'environment':environment,'services':{name:{'absence':'EXACT_ECS_MISSING'} for name in names},'tasks':[],'complete':True}
        c.require(not clusters.get('failures') and len(clusters['clusters'])==1 and
                  clusters['clusters'][0]['clusterArn']==cluster,'exact live cluster')
        response=self.ecs.describe_services(cluster=cluster,services=names)
        services={}
        for failure in response.get('failures',[]):
            name=failure.get('arn','').rsplit('/',1)[-1]
            c.require(failure.get('reason')=='MISSING' and name in names and name not in services,'exact missing service observation')
            services[name]={'absence':'EXACT_ECS_MISSING'}
        for service in response['services']:
            c.require(service['clusterArn']==cluster and service['serviceName'] in names and service['serviceName'] not in services,'live service identity')
            services[service['serviceName']]={field:service[source] for field,source in
                                           (('desired','desiredCount'),('running','runningCount'),('pending','pendingCount'))}
        c.require(set(services)==set(names),'complete exact service observations')
        tasks=[]
        for status in ('RUNNING','PENDING'):
            next_token=None
            for _ in range(100):
                page=self.ecs.list_tasks(cluster=cluster,desiredStatus=status,**({'nextToken':next_token} if next_token else {}))
                tasks.extend(page['taskArns']);next_token=page.get('nextToken')
                if not next_token:break
            c.require(not next_token,'complete bounded live task listing')
        return {'environment':environment,'services':services,'tasks':tasks,'complete':True}
    def apply(self,plan_hash):
        # Both JSON semantics and exact binary/prepared context must survive.
        # This same-invocation seal is not an administrator review handoff.
        if getattr(self, 'destroy', False):
            self.check_destroy_seal()
            c.require(plan_hash == self.destroy_seal['json_sha256'], 'exact selected JSON plan')
        c.require(c.digest(c.canonical(json.loads(self.call(['show','-json','wp5.tfplan']))))==plan_hash,'saved plan changed')
        if getattr(self, 'destroy', False):
            self.check_destroy_seal()
            c.quiescent(self.observe(self.protected['environment']), self.protected['environment'])
        self.call(['apply','-input=false','wp5.tfplan'])
    def verify(self,plan_hash,layer,operation):
        self.call(['plan','-refresh-only','-input=false','-out=wp5-readback.tfplan'])
        readback=json.loads(self.call(['show','-json','wp5-readback.tfplan']))
        if operation == 'teardown':
            # Terraform 1.13.4 omits resource_changes for a genuinely empty
            # refresh-only plan. Complete empty values, not that optional field,
            # establish state absence; partial/nonempty readback fails closed.
            if not (readback.get('format_version') == '1.2'
                    and readback.get('complete') is True and readback.get('errored') is False
                    and not readback.get('resource_drift') and not readback.get('deferred_changes')):
                return False
            teardown_readback(readback)
            changes = readback.get('resource_changes', [])
            c.require(type(changes) is list and all(type(x) is dict and x.get('mode') == 'data'
                and x.get('change', {}).get('actions') == ['no-op'] for x in changes),
                'teardown readback contradictory changes')
            c.quiescent(self.observe(self.protected['environment']), self.protected['environment'])
            return True
        return (readback.get('format_version') == '1.2' and not readback.get('errored') and
                'resource_changes' in readback and not readback.get('resource_drift') and
                not readback.get('deferred_changes') and
                all(x['change']['actions']==['no-op'] for x in readback['resource_changes']))



def clients(region):
    import boto3
    from botocore.config import Config
    return {name:boto3.client(name,region_name=region,config=Config(connect_timeout=3,read_timeout=5,
        retries={'total_max_attempts':1},**({'signature_version':'s3v4'} if name=='s3' else {})))
        for name in ('s3','codebuild','ecs')}


def execute(event, configuration, clients_):
    c.keys(configuration,('binding','account','region','package'),'installed bootstrap configuration')
    binding=configuration['binding'];environment=binding.rsplit('-',1)[1]
    def read_configuration(selected):
        response=clients_['s3'].get_object(Bucket='demo-release-artifacts-'+configuration['account'],
            Key='lifecycle/'+selected+'/current.json')
        raw=response['Body'].read(1048577)
        c.require(len(raw)<=1048576,'bounded protected configuration')
        value=json.loads(raw)
        c.require(value['binding']==selected and value['environment']==environment and
                  value['account']==configuration['account'] and value['region']==configuration['region'],'current protected binding')
        return value
    protected=read_configuration(binding)
    reference=configuration['package']
    c.require(reference['binding']==binding and reference['sha256'] in protected['active_contracts'] and
              protected['installations'].get(reference['sha256'])==reference,'current bootstrap installation required')
    bucket=f'e1-lifecycle-{environment}-{configuration["account"]}-{configuration["region"]}'
    suffix=binding.split('/')[1]
    requests=Records(clients_['s3'],bucket,'requests/'+suffix+'/')
    if binding.startswith('request-gateway/'):
        downstream='environment-lifecycle/'+suffix
        target=read_configuration(downstream)
        value=c.request(downstream,event)
        # Read back both exact package versions before any privileged invocation.
        with tempfile.TemporaryDirectory(prefix='wp5-gateway-') as directory:
            packages.verify(clients_['s3'],reference,Path(directory)/'gateway')
            installed=packages.verify(clients_['s3'],target['installations'].get(value['revision']),Path(directory)/'controller')
            c.authorize(downstream,value,target,installed)
        if requests.get(value['operation_id']+'/request') is not None:
            return {'operation_id':value['operation_id'],'state':'UNKNOWN'}
        requests.put(value['operation_id']+'/request',value)
        build=clients_['codebuild'].start_build(projectName='e1-controller-'+suffix)['build']
        c.require(build['projectName']=='e1-controller-'+suffix,'exact start acknowledgement')
        requests.put('builds/'+c.digest(build['id'].encode('utf-8')),{'operation_id':value['operation_id']})
        return {'operation_id':value['operation_id'],'state':'STARTED'}
    c.require(event is None,'CodeBuild has no caller payload')
    build_id=os.environ['CODEBUILD_BUILD_ID']
    c.require(build_id.startswith('e1-controller-'+suffix+':'),'fixed project build ID')
    request=None
    for _ in range(100):
        mapping=requests.get('builds/'+c.digest(build_id.encode('utf-8')))
        if mapping is not None:
            request=requests.get(mapping['operation_id']+'/request');break
        time.sleep(.25)
    c.require(request is not None,'protected build-to-operation mapping')
    with tempfile.TemporaryDirectory(prefix='wp5-') as directory:
        package=Packages(clients_['s3'],directory)
        records=Records(clients_['s3'],bucket,'operations/'+binding+'/')
        def run_owned(owner=None):
            engine=Terraform(directory,clients_['ecs'],protected,owner,request=request)
            return Controller(binding,protected,package,engine,records).run(request)
        value=c.request(binding,request)
        retained=records.read(value['operation_id'])
        if retained is not None:
            c.require(retained['request_sha256']==c.digest(c.canonical(value)), 'retry changed request')
            result=retained
        elif value['operation']=='plan':
            result=run_owned()
        else:
            coordination_bucket=f'e1-wp4-{environment}-{configuration["account"]}-{configuration["region"]}'
            owner=Authority(Store(clients_['s3'],coordination_bucket,environment,domain(binding,value['layer'])),
                            binding,value['operation_id'],value,layer=value['layer'])
            result=arbitrate(owner,run_owned,state_key='state')
        public={'operation_id':request['operation_id'],'state':result['state'],'release_id':None,'source_commit':None}
        key=request['operation_id']+'/public'
        try:records.put(key,public)
        except Exception as error:
            if getattr(error,'response',{}).get('Error',{}).get('Code')!='PreconditionFailed':raise
        c.require(records.get(key)==public,'exact public completion persistence')
        return result


def handler(event,context):
    configuration=json.loads(os.environ['E1_WP5_CONFIGURATION'])
    return execute(event,configuration,clients(configuration['region']))


if __name__=='__main__':handler(None,None)
