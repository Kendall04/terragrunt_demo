"""E16 supervised original DEV sessions. No cloud calls on import.

One local human session, existing roots/state/locks, one reviewed binary per
layer. A future exclusive state-writer handoff is mandatory; never changes IAM.
Advanced WP5 remains a distinct, mutually exclusive mode. No E2 writes/takeover.
"""
import argparse
import configparser
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import subprocess
import time
import uuid
from scripts.lifecycle import contract as c
from scripts import environment_mutation as e

ROOT=Path(__file__).resolve().parents[1]
UP=('global','data','platform','apps','edge')
DOWN=tuple(reversed(UP))
BINDINGS=('infra-dev','infra-high-risk-dev','deploy-dev','emergency-dev')
DUTIES=('assign_eip','change_rt','disable_sdc')
PROCESSES=('Launch','AlarmNotification','AZRebalance','ReplaceUnhealthy','ScheduledActions','InstanceRefresh')


def require(ok,reason):
    if not ok:raise ValueError('E16_DEV_BLOCKED: '+reason)


def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate JSON key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:require(False,'nonfinite JSON'))


def sha(raw):return hashlib.sha256(raw).hexdigest()


def state_digest(raw):
    # Terraform state pull iterates check-result maps in non-deterministic order.
    # Retain every check/result and all resource data; normalize only that order
    # and JSON object key order. Serial/lineage are still checked independently.
    value=decode(raw)
    checks=value.get('check_results')
    if checks is not None:
        require(type(checks) is list,'state check results format')
        for check in checks:
            require(type(check) is dict and isinstance(check.get('config_addr'),str),'state check identity')
            objects=check.get('objects')
            if objects is not None:
                require(type(objects) is list and all(type(o) is dict and isinstance(o.get('object_addr'),str) for o in objects),'state check objects')
                check['objects']=sorted(objects,key=lambda o:o['object_addr'])
        value['check_results']=sorted(checks,key=lambda check:check['config_addr'])
    return sha(c.canonical(value))


class Failure(ValueError):
    def __init__(self,code,stderr,stage='unspecified'):
        self.stage=stage
        super().__init__('stage '+stage+' failed (exit '+str(code)+'); preserve state/plan; use status and residual; possible running EC2/Fargate/ALB/EBS/IPv4 charges')
        self.code,self.stderr=code,stderr


class Process:
    def __init__(self,config,aws_config_file=None,terraform_wsl_bin=None,terraform_plugin_cache=None):
        self.config=config;self.aws_config_file=None;self.terraform_wsl_bin=terraform_wsl_bin;self.paths={};self.terraform_plugin_cache=None
        if terraform_plugin_cache:
            cache=Path(terraform_plugin_cache).resolve()
            require(terraform_wsl_bin is not None and cache.is_dir() and not cache.is_symlink() and cache!=ROOT and ROOT not in cache.parents,
                'existing external provider cache only; readonly locks still verify providers')
            self.terraform_plugin_cache=cache
        if aws_config_file:
            path=Path(aws_config_file).resolve();parsed=configparser.ConfigParser(interpolation=None);parsed.read(path)
            name='profile '+config['profile']
            require(parsed.sections()==[name] and set(parsed[name])=={'region','source_profile','role_arn','role_session_name','duration_seconds','ca_bundle'},'public same-profile role configuration only; no embedded credentials/process')
            require(parsed[name]['region']==config['region'] and parsed[name]['source_profile']==config['profile'] and parsed[name]['role_arn']==config['operator_arn'] and parsed[name]['duration_seconds']=='3600','exact existing operator role/profile/region')
            self.aws_config_file=path
        if terraform_wsl_bin:
            require(os.name=='nt' and self.aws_config_file is not None,'local Windows WSL requires explicit same-profile configuration')
            import zipfile
            archive=Path(terraform_wsl_bin).resolve().with_name('terraform-linux.zip')
            pin=decode((ROOT/'.github/scripts/ci/toolchain.json').read_bytes())['tools']['terraform']
            require(sha(archive.read_bytes())==pin['sha256'],'reviewed Terraform distribution')
            with zipfile.ZipFile(archive) as bundle:require(bundle.read('terraform')==Path(terraform_wsl_bin).read_bytes(),'exact pinned Terraform binary')

    def wsl_path(self,path):
        key=Path(path).resolve().as_posix()
        if key in self.paths:return self.paths[key]
        value=subprocess.run(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(path).resolve().as_posix()],capture_output=True,check=True).stdout.decode().strip()
        require(value.startswith('/mnt/'),'observed local Windows mount required');self.paths[key]=value;return value

    def wsl_command(self,args,cwd):
        config=configparser.ConfigParser(interpolation=None);config.read(self.aws_config_file)
        cert=config['profile '+self.config['profile']]['ca_bundle']
        mapped=[]
        for arg in args[1:]:
            key,sep,value=arg.partition('=')
            if sep and Path(value).is_absolute():arg=key+'='+self.wsl_path(value)
            elif Path(arg).is_absolute():arg=self.wsl_path(arg)
            mapped.append(arg)
        prefix=['wsl','-d','Ubuntu','--exec','env','-i','PATH=/usr/bin:/bin','HOME='+self.wsl_path(Path.home()),
            'CHECKPOINT_DISABLE=1','TF_IN_AUTOMATION=1','AWS_PROFILE='+self.config['profile'],'AWS_REGION='+self.config['region'],
            'AWS_DEFAULT_REGION='+self.config['region'],'AWS_MAX_ATTEMPTS=1','AWS_EC2_METADATA_DISABLED=true',
            'AWS_CONFIG_FILE='+self.wsl_path(self.aws_config_file),'AWS_SHARED_CREDENTIALS_FILE='+self.wsl_path(Path.home()/'.aws/credentials'),
            'AWS_CA_BUNDLE='+self.wsl_path(cert),self.wsl_path(self.terraform_wsl_bin)]
        if self.terraform_plugin_cache:prefix.insert(-1,'TF_PLUGIN_CACHE_DIR='+self.wsl_path(self.terraform_plugin_cache))
        return prefix+mapped
    def run(self,args,cwd=None,data=None):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','TF_','TERRAGRUNT'))}
        env.update(AWS_PROFILE=self.config['profile'],AWS_REGION=self.config['region'],AWS_DEFAULT_REGION=self.config['region'],
            AWS_MAX_ATTEMPTS='1',AWS_EC2_METADATA_DISABLED='true',AWS_PAGER='',TF_IN_AUTOMATION='1',CHECKPOINT_DISABLE='1')
        if self.aws_config_file:env['AWS_CONFIG_FILE']=str(self.aws_config_file)
        original=args
        if args[0]=='terraform' and self.terraform_wsl_bin:args=self.wsl_command(args,cwd)
        stage=(Path(cwd).name+':terraform '+original[2]) if original[0]=='terraform' and cwd else ('AWS '+args[8]+' '+args[9] if args[0]=='aws' else Path(args[0]).name)
        try:result=subprocess.run(args,cwd=cwd,input=data,env=env,capture_output=True,timeout=1800)
        except subprocess.TimeoutExpired:raise Failure(-1,b'timeout; remote effect unknown',stage) from None
        if result.returncode:raise Failure(result.returncode,result.stderr,stage)
        return result.stdout


class Session:
    def __init__(self,config,directory,process=None):
        c.keys(config,('schema','environment','account','region','profile','operator_arn','source_commit','variables'),'E16 config')
        require(config['schema']=='E16_SUPERVISED_DEV_V1' and config['environment']=='dev','DEV only, no shared/PROD mode')
        require(bool(re.fullmatch('[0-9]{12}',config['account'])) and bool(re.fullmatch('[a-z]{2}(?:-[a-z]+)+-[0-9]',config['region'])),'explicit account/region')
        require(bool(config['profile']) and bool(re.fullmatch('arn:aws:iam::'+config['account']+':role/[A-Za-z0-9+=,.@_-]+',config['operator_arn'])),'existing explicit human role, no admin fallback')
        require(not any(word in config['operator_arn'].lower() for word in ('e1-','prod','shared','admin')),'no protected/admin role borrowed')
        require(bool(re.fullmatch('[0-9a-f]{40}',config['source_commit'])),'exact reviewed source')
        require(set(config['variables'])<=set(UP),'runtime DEV roots only, shared/secrets installed separately')
        self.config=copy.deepcopy(config);self.directory=Path(directory).resolve();self.process=process or Process(config)
        require(self.directory!=ROOT and ROOT not in self.directory.parents and not Path(directory).is_symlink(),'private external session directory')
        self.account,self.region=config['account'],config['region']
        self.bucket=f'e1-lifecycle-dev-{self.account}-{self.region}'
        self.coordination=f'e1-wp4-dev-{self.account}-{self.region}'

    def aws(self,service,action,*args):
        raw=self.process.run(['aws','--profile',self.config['profile'],'--region',self.region,'--no-cli-pager','--output','json',service,action,*args])
        return decode(raw) if raw.strip() else {}

    def identity(self):
        result=self.aws('sts','get-caller-identity')
        require(result['Account']==self.account and result['Arn'].startswith(f'arn:aws:sts::{self.account}:assumed-role/'+self.config['operator_arn'].rsplit('/',1)[1]+'/'),'wrong human account/session')
        require(self.process.run(['git','rev-parse','HEAD'],cwd=ROOT).strip().decode()==self.config['source_commit'],'reviewed source commit changed')
        require(not self.process.run(['git','status','--porcelain=v1'],cwd=ROOT).strip(),'checkout must be clean')
        require(decode(self.process.run(['terraform','version','-json']))['terraform_version']=='1.13.4','reviewed Terraform version')

    def save(self,file,value):
        file=Path(file);file.parent.mkdir(parents=True,exist_ok=True)
        with file.open('xb') as stream:stream.write(c.canonical(value))
        file.chmod(0o600)

    def backend(self):
        owner=['--bucket',self.bucket,'--expected-bucket-owner',self.account]
        require((self.aws('s3api','get-bucket-location',*owner)['LocationConstraint'] or 'us-east-1')==self.region,'backend region')
        require(self.aws('s3api','get-bucket-versioning',*owner)['Status']=='Enabled','retain state versions')
        controls=self.aws('s3api','get-public-access-block',*owner)['PublicAccessBlockConfiguration']
        require(set(controls)=={'BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets'} and all(v is True for v in controls.values()),'private backend')
        encryption=self.aws('s3api','get-bucket-encryption',*owner)['ServerSideEncryptionConfiguration']['Rules']
        require(len(encryption)==1 and encryption[0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']=='AES256','retained backend encryption')
        policy=decode(self.aws('s3api','get-bucket-policy',*owner)['Policy'])
        keys=[f'arn:aws:s3:::{self.bucket}/e1/lifecycle/dev/{layer}/terraform.tfstate'+suffix for layer in UP for suffix in ('','.tflock')]
        # Administrative migration must install this exact deny, in addition to
        # preserving TLS/privacy and all existing shared/security protection.
        deny=dict(Sid='E16ExclusiveDevRuntimeWriter',Effect='Deny',Principal='*',Action=['s3:PutObject','s3:DeleteObject'],Resource=keys,
            Condition=dict(ArnNotEquals={'aws:PrincipalArn':self.config['operator_arn']}))
        require(any(item==deny for item in policy['Statement']),'exclusive DEV state-writer transfer not installed; no competing WP5 authority')
        require(any(item.get('Effect')=='Deny' and item.get('Condition',{}).get('Bool',{}).get('aws:SecureTransport')=='false' for item in policy['Statement']),'backend TLS deny retained')

    def object(self,key):
        with tempfile.TemporaryDirectory(prefix='e16-read-') as tmp:
            target=Path(tmp)/'read.json'
            result=self.aws('s3api','get-object','--bucket',self.coordination,'--key',key,'--expected-bucket-owner',self.account,str(target))
            require(result.get('VersionId') not in (None,'','null','latest'),'versioned protected readback')
            return decode(target.read_bytes())

    def functions(self):
        response=self.aws('lambda','list-functions')
        require(not response.get('NextMarker'),'incomplete callable function inventory')
        exact={f'e1-nat-recovery-nat-dev-{d.replace("_","-")}' for d in DUTIES}|{'e1-gateway-'+v for v in BINDINGS}|{'e1-cleanup-recovery-cleanup-dev'}
        found={v['FunctionName']:v for v in response['Functions'] if v['FunctionName'] in exact}
        require(all(v['FunctionArn']==f'arn:aws:lambda:{self.region}:{self.account}:function:{name}' for name,v in found.items()),'exact DEV callable ARNs')
        return found

    def idle(self):
        head=self.object('arbitration/dev/application.json');e.validate(head,'dev','application')
        require(head['state']=='RELEASED' and head['schedule'] is None,'E2 active/interrupted owner or cleanup schedule; do not seize/release')
        # Absent protected compute need not be installed for E16. Enumerated API
        # absence, unlike an AccessDenied, proves that named project is not active.
        functions=self.functions()
        for binding in ('infra-dev','infra-high-risk-dev'):
            name='e1-gateway-'+binding
            if name in functions:
                require(self.aws('lambda','get-function-concurrency','--function-name',name).get('ReservedConcurrentExecutions')==0,'WP5 gateway must be administratively inhibited before exclusive transfer')
        projects=self.aws('codebuild','list-projects')
        require(not projects.get('nextToken'),'incomplete controller project inventory')
        for project in ['e1-controller-'+name for name in BINDINGS if 'e1-controller-'+name in projects['projects']]:
            listed=self.aws('codebuild','list-builds-for-project','--project-name',project,'--sort-order','DESCENDING')
            require(not listed.get('nextToken'),'incomplete build inventory')
            if listed['ids']:
                observed=self.aws('codebuild','batch-get-builds','--ids',*listed['ids'])
                require(not observed.get('buildsNotFound') and len(observed['builds'])==len(listed['ids']),'complete build observation')
                require(all(not b['buildInProgress'] and b['buildStatus'] in ('SUCCEEDED','FAILED','STOPPED','TIMED_OUT','FAULT') for b in observed['builds']),'active ECS/lifecycle controller')

    def root(self,layer):
        require(layer in UP,'original runtime DEV root only')
        return self.directory/'terraform/modules/target/dev'/layer

    def tf(self,layer,*args):
        return self.process.run(['terraform','-chdir='+str(self.root(layer)),*args],cwd=self.root(layer))

    def source(self):
        marker=decode((self.directory/'session.json').read_bytes())
        require({k:v for k,v in marker['config'].items() if k!='variables'}=={k:v for k,v in self.config.items() if k!='variables'},'same DEV identity/source/backend; stage variables separately reviewed')
        for name,digest in marker['sources'].items():
            require(sha((ROOT/name).read_bytes())==digest and sha((self.directory/name).read_bytes())==digest,'source changed; no executable/root substitution')
        known=set(marker['sources'])
        for f in (self.directory/'terraform/modules/target/dev').rglob('*'):
            if any(part in ('.terraform','.terragrunt-cache') for part in f.relative_to(self.directory).parts):continue
            if f.is_file() and (f.suffix in ('.tf','.hcl') or f.name.endswith('.tf.json')):
                require(not f.is_symlink() and (f.relative_to(self.directory).as_posix() in known or f.name=='e16.auto.tfvars.json'),'extra nested executable Terraform source')
        for layer in UP:
            permitted={Path(n).name for n in marker['sources'] if Path(n).parent.as_posix()=='terraform/modules/target/dev/'+layer}
            require(all(f.name in permitted or f.name=='e16.auto.tfvars.json' for f in self.root(layer).glob('*.tf*')),'extra Terraform sources/imports forbidden')
        return marker

    def initialize(self):
        self.identity();self.backend();self.idle()
        require(not self.directory.exists(),'new session directory, no adoption')
        files={}
        tracked={v for v in self.process.run(['git','ls-files'],cwd=ROOT).decode().splitlines()}
        for base in ('terraform/modules/target/dev','terraform/infra/security/authority.json','terraform/infra/data/user_data.sh'):
            path=ROOT/base
            for file in ([path] if path.is_file() else path.rglob('*')):
                if file.is_file():
                    require(not file.is_symlink() and not any(p in ('.terraform','.terragrunt-cache') for p in file.parts),'clean tracked root')
                    name=file.relative_to(ROOT).as_posix();require(name in tracked,'only tracked original source inputs copied');target=self.directory/name;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(file.read_bytes());files[name]=sha(file.read_bytes())
        self.save(self.directory/'session.json',dict(config=self.config,sources=files))
        for layer in UP:
            self.tf(layer,'init','-input=false','-lockfile=readonly','-backend-config=bucket='+self.bucket,'-backend-config=region='+self.region,
                '-backend-config=key=e1/lifecycle/dev/'+layer+'/terraform.tfstate',
                '-backend-config=workspace_key_prefix=e1/lifecycle/dev/'+layer+'/terraform.tfstate/workspaces')
        return dict(stage='INITIALIZED_ORIGINAL_ROOTS',aws_verified=type(self.process) is Process)

    def initialized(self,layer):
        value=decode((self.root(layer)/'.terraform/terraform.tfstate').read_bytes())['backend']
        require(value['type']=='s3' and value['config']['bucket']==self.bucket and value['config']['key']==f'e1/lifecycle/dev/{layer}/terraform.tfstate'
            and value['config'].get('workspace_key_prefix')==f'e1/lifecycle/dev/{layer}/terraform.tfstate/workspaces'
            and value['config']['region']==self.region and value['config']['encrypt'] is True and value['config']['use_lockfile'] is True,'exact original state/locking')
        require(self.tf(layer,'workspace','show').strip()==b'default','no alternate workspace')

    def addresses(self,layer):
        result={}
        def walk(directory,prefix=''):
            for file in directory.glob('*.tf*'):
                if file.name.endswith('.tf.json'):
                    value=decode(file.read_bytes())
                    for kind,nodes in value.get('resource',{}).items():
                        for name in nodes:result[prefix+kind+'.'+name]=kind
                elif file.suffix=='.tf':
                    text=file.read_text()
                    for kind,name in re.findall(r'^resource\s+"([^"]+)"\s+"([^"]+)"',text,re.M):result[prefix+kind+'.'+name]=kind
                    for name,source in re.findall(r'module\s+"([^"]+)"\s*\{\s*source\s*=\s*"([^"]+)"',text):
                        require(source.startswith('./modules/'),'local original modules only')
                        walk(directory/source,prefix+'module.'+name+'.')
        walk(self.root(layer))
        return result

    def address(self,layer,row):
        normal=re.sub(r'\[[^\]]*\]','',row['address'])
        require(self.addresses(layer).get(normal)==row['type'],'foreign state/plan address outside original root')

    def state(self,layer):
        self.initialized(layer)
        # Missing exact key establishes fresh state; permission failure never does.
        listed=self.aws('s3api','list-objects-v2','--bucket',self.bucket,'--prefix',f'e1/lifecycle/dev/{layer}/terraform.tfstate','--expected-bucket-owner',self.account)
        require(not listed.get('IsTruncated'),'complete exact state lookup')
        if not any(x['Key']==f'e1/lifecycle/dev/{layer}/terraform.tfstate' for x in listed.get('Contents',[])):
            return dict(lineage=None,serial=None,sha256=None,rows=[],outputs={})
        raw=self.tf(layer,'state','pull');value=decode(raw)
        require(value['version']==4 and type(value['serial']) is int and bool(value['lineage']),'state format')
        rows=[]
        def visit(module):
            for resource in module.get('resources',[]):
                if resource['mode']=='managed':rows.append(resource)
            for child in module.get('child_modules',[]):visit(child)
        shown=decode(self.tf(layer,'show','-json'));visit(shown.get('values',{}).get('root_module',{}))
        for row in rows:
            self.address(layer,row)
            kind=row['type'];attrs=row['values']
            require(not kind.startswith(c.PROTECTED_TYPES),'state contains security-root ownership')
            if kind!='terraform_data':
                tags=attrs.get('tags_all') or attrs.get('tags')
                if kind=='aws_autoscaling_group':tags={v['key']:v['value'] for v in attrs.get('tag',[])}
                if tags:require(tags.get('Environment')=='dev' and (kind=='aws_autoscaling_group' or tags.get('Project')=='demo'),'foreign state ownership')
                require('prod' not in str(attrs.get('arn','')) and 'shared' not in str(attrs.get('arn','')),'foreign/protected resource')
        arns=[r['values']['arn'] for r in rows if r['values'].get('arn') and (r['values'].get('tags_all') or r['values'].get('tags'))]
        if arns:
            response=self.aws('resourcegroupstaggingapi','get-resources','--resource-arn-list',*arns)
            observed={i['ResourceARN']:{v['Key']:v['Value'] for v in i['Tags']} for i in response['ResourceTagMappingList']}
            require(set(observed)==set(arns) and all(t.get('Environment')=='dev' and t.get('Project')=='demo' for t in observed.values()),'independent owner tags missing/foreign')
        return dict(lineage=value['lineage'],serial=value['serial'],sha256=state_digest(raw),rows=rows,outputs={k:v['value'] for k,v in value.get('outputs',{}).items()})

    def variables(self,layer):
        # Existing admin-promoted source publication supplies only security-owned
        # references; network/service IDs are resolved after their actual creation.
        authority=decode((ROOT/'terraform/infra/security/authority.json').read_bytes())
        publication=authority['ownership_closure']['publications'].get(self.account+'/'+self.region)
        require(publication is not None,'security outputs must first be administrator-promoted; no invented ARN/ID')
        required=authority['ownership_closure']['consumers'].get('dev/'+layer,[])
        protected={k:publication['records'][k]['value'] for k in required if publication['records'][k]['available']}
        require(set(protected)==set(required),'security references incomplete')
        allowed={'global':{'protected_nat_launch'},'data':{'protected_sql_ami','app_db','app_user','enable_alarms','instance_type','volume_size_gb','cpu_credits'},'platform':set(),'apps':set(),'edge':{'cors_allowed_origins'}}
        require(set(self.config['variables'].get(layer,{}))<=allowed[layer],'only original nonsecret configuration inputs; dependency overrides rejected')
        value=dict(self.config['variables'].get(layer,{}),account_id=self.account,region=self.region)
        if required:value['protected_inputs']=protected
        require(not any('password' in k.lower() or k in ('secret_value','connection_string') for k in value),'secret-free Terraform')
        shared=publication['records'].get('dev/kms')
        require(shared and shared['available'],'actual KMS publication')
        if layer!='platform':value['alerts_topic_arn']=f'arn:aws:sns:{self.region}:{self.account}:demo-dev-shared-alerts'
        if layer in ('data','apps','edge'):
            global_=self.state('global')['outputs']
            value['private_subnet_ids']=global_['private_subnet_ids']
            if layer=='data':value['db_instance_sg_id']=global_['db_instance_sg_id']
            elif layer=='edge':value.update(alb_listener_arn=global_['alb_listener_arn'],vpc_link_sg_id=global_['vpc_link_sg_id'])
            else:
                value.update({k:global_[k] for k in ('alb_listener_arn','demo_sg_id','demo_blue_tg_arn','demo_green_tg_arn')})
                value.update({k:self.state('platform')['outputs'][k] for k in ('cluster_arn','cluster_name')})
        return value

    def bootstrap_status(self):
        result=self.status()
        state=self.state('global')
        selected={r['address']:dict(type=r['type'],id=r['values'].get('id'),arn=r['values'].get('arn')) for r in state['rows']}
        result.update(stage='ACTUAL_NETWORK_IDS_FOR_EXISTING_ADMIN_NAT_INSTALL',network_ids=selected,
            next='existing security admin installs exact launch templates and E13 bindings, using these actual IDs; update protected_nat_launch then review global up-plan')
        return result

    def sql_secrets_ready(self,variables):
        for key in ('dev/sa','dev/db-user'):
            value=self.aws('secretsmanager','describe-secret','--secret-id',variables['protected_inputs'][key])
            require('DeletedDate' not in value and any('AWSCURRENT' in stages for stages in value.get('VersionIdsToStages',{}).values()),'SQL password bootstrap metadata not ready')

    def unresolved(self):
        for file in (self.directory/'plans').glob('*/attempt.json'):
            require((file.parent/'completed.json').exists(),'prior partial/ambiguous apply; reconcile and review a new session before proceeding')

    def check_plan(self,layer,plan,state,down):
        require(plan.get('format_version')=='1.2' and not plan.get('errored') and not plan.get('deferred_changes'),'actual complete plan')
        changes=plan.get('resource_changes');require(type(changes) is list,'real resource preview')
        prior={r['address']:r for r in state['rows']};seen=set()
        for row in changes:
            if row.get('mode')=='data':continue
            self.address(layer,row)
            address,kind=row['address'],row['type'];change=row['change']
            require(address not in seen and not kind.startswith(c.PROTECTED_TYPES),'no duplicate/security-root mutation');seen.add(address)
            actions=change['actions'];require(actions in (['delete'],['no-op']) if down else actions in (['create'],['update'],['no-op']),'no hidden replacement/new destroy resource')
            before,after=change.get('before'),change.get('after')
            if before is not None:
                require(address in prior and prior[address]['values']['id']==before['id'],'state exact resource identity')
                for name in c.RUNTIME_FIELDS.get(kind,())+c.EXECUTION_FIELDS.get(kind,()):
                    if actions==['update']:require(before.get(name)==after.get(name),'deployment/execution field ownership preserved')
            tags=(after or before or {}).get('tags_all') or (after or before or {}).get('tags')
            if tags:require(tags.get('Environment')=='dev' and tags.get('Project')=='demo','foreign preview tags')
            if kind=='aws_ecs_service' and actions==['create']:require(after['desired_count']==0,'WP4 owns workload count')
        if down:require({r['address'] for r in state['rows']}<=seen,'complete next-layer teardown')
        return changes

    def prepare(self,down=False,network_only=False,down_layer=None):
        require(down_layer is None or (down and down_layer in DOWN),'preview layer must be an original DEV DOWN layer')
        self.identity();self.source();self.backend();self.idle();self.unresolved()
        states={layer:self.state(layer) for layer in UP}
        if down:
            remaining=[l for l in DOWN if states[l]['rows']];require(remaining,'no runtime state; run residual')
            layer=down_layer or remaining[0];require(layer in remaining,'requested layer has no runtime state')
            # Preview is read-only and must precede destructive human approval.
            # apply() still enforces reverse order and the complete live shutdown guard.
        else:
            remaining=[l for l in UP if not (self.directory/('up-'+l+'-reconciled.json')).exists()];require(remaining,'infrastructure states present; verify, then use WP3/WP4 deployment');layer=remaining[0]
        if down:
            # Reuse exactly the variables of the already-created layer; prior
            # dependencies may already be gone in the reverse order.
            variables_file=self.root(layer)/'e16.auto.tfvars.json'
            require(variables_file.exists(),'after interrupted session, reconstruct exact original variables before DOWN; use retained plan/session inputs')
            variables=decode(variables_file.read_bytes())
        else:variables=self.variables(layer)
        if network_only:
            require(layer=='global' and not down and not any(row['type']=='aws_autoscaling_group' for row in states['global']['rows']),
                'network bootstrap only before original NAT ASGs; partial owned network must be reconciled')
            groups=self.aws('autoscaling','describe-auto-scaling-groups','--auto-scaling-group-names','demo-dev-asg-nat-a','demo-dev-asg-nat-b')
            require(not groups.get('NextToken') and groups['AutoScalingGroups']==[], 'existing or untracked NAT ASG blocks network bootstrap')
            variables['protected_nat_launch']={}
        elif layer=='global' and not down:require(set(variables.get('protected_nat_launch',{}))=={'a','b'},'after network bootstrap, install/read back both original NAT launch versions then configure them')
        if layer=='data' and not down:self.sql_secrets_ready(variables)
        if layer=='apps' and not down:
            secret=self.aws('secretsmanager','describe-secret','--secret-id',variables['protected_inputs']['dev/connection'])
            require(any('AWSCURRENT' in stages for stages in secret.get('VersionIdsToStages',{}).values()),'connection string must be seeded outside Terraform after SQL creation')
        file=self.root(layer)/'e16.auto.tfvars.json';file.write_bytes(c.canonical(variables));file.chmod(0o600)
        plan_id=str(uuid.uuid4());folder=self.directory/'plans'/plan_id;folder.mkdir(parents=True)
        binary=folder/'saved.tfplan';args=['plan','-input=false','-out='+str(binary)]
        if down:args+=['-destroy']
        self.tf(layer,*args)
        raw=self.tf(layer,'show','-json',str(binary));plan=decode(raw)
        changes=self.check_plan(layer,plan,states[layer],down)
        (folder/'preview.json').write_bytes(raw);(folder/'preview.txt').write_bytes(self.tf(layer,'show','-no-color',str(binary)))
        review=dict(layer=layer,down=down,network_only=network_only,config_sha256=sha(c.canonical(self.config)),binary_sha256=sha(binary.read_bytes()),preview_sha256=sha(raw),
            variables_sha256=sha(file.read_bytes()),state={k:states[layer][k] for k in ('lineage','serial','sha256')})
        self.save(folder/'review.json',review)
        return dict(plan_id=plan_id,layer=layer,preview=(folder/'preview.txt').read_text(),confirmation=self.confirmation(review),
            sql_confirmation='PERMANENTLY LOSE DEV SQL '+review['binary_sha256'] if down and layer=='data' else None,phase='REVIEW_REQUIRED_NOT_EXECUTED')

    def confirmation(self,review):return ('DESTROY' if review['down'] else 'APPLY')+' DEV '+self.account+' '+self.region+' '+review['layer']+' '+review['binary_sha256']

    def apply(self,plan_id,confirmation,sql_confirmation=None):
        require(str(uuid.UUID(plan_id))==plan_id,'exact canonical plan ID')
        self.identity();self.source();self.backend();self.idle();self.unresolved()
        folder=self.directory/'plans'/plan_id;review=decode((folder/'review.json').read_bytes());layer=review['layer'];binary=folder/'saved.tfplan'
        require(review['config_sha256']==sha(c.canonical(self.config)) and confirmation==self.confirmation(review),'exact human plan confirmation/config')
        if review['down'] and layer=='data':require(sql_confirmation=='PERMANENTLY LOSE DEV SQL '+review['binary_sha256'],'independent SQL data-loss confirmation')
        require(review['binary_sha256']==sha(binary.read_bytes()) and review['preview_sha256']==sha(self.tf(layer,'show','-json',str(binary))), 'reviewed binary/preview changed')
        state=self.state(layer);require(review['state']=={k:state[k] for k in ('lineage','serial','sha256')},'stale plan/state; review a new plan')
        require(review['variables_sha256']==sha((self.root(layer)/'e16.auto.tfvars.json').read_bytes()),'variables changed')
        states={l:self.state(l) for l in UP}
        next_layer=next((l for l in (DOWN if review['down'] else UP) if (bool(states[l]['rows']) if review['down'] else not (self.directory/('up-'+l+'-reconciled.json')).exists())),None)
        require(next_layer==layer,'dependency order changed')
        self.check_plan(layer,decode(self.tf(layer,'show','-json',str(binary))),state,review['down'])
        if review['down']:self.shutdown_observation()
        self.save(folder/'inventory.json',state)
        self.save(folder/'attempt.json',dict(state='UNKNOWN',plan_sha256=review['binary_sha256']))
        self.tf(layer,'apply','-input=false',str(binary))
        after=self.state(layer)
        require(not review['down'] or not after['rows'],'partial destroy; billable resources remain')
        require(review['down'] or bool(after['rows']),'apply has no observed managed state')
        if not review['down']:
            expected={r['address'] for r in decode(self.tf(layer,'show','-json',str(binary)))['resource_changes'] if r.get('mode')!='data'}
            require(expected=={r['address'] for r in after['rows']},'partial apply/state address readback')
            if not review['network_only'] and not (self.directory/('up-'+layer+'-reconciled.json')).exists():
                self.save(self.directory/('up-'+layer+'-reconciled.json'),dict(state_sha256=after['sha256']))
        self.save(folder/'completed.json',dict(state='STATE_RECONCILED',sha256=after['sha256']))
        return dict(layer=layer,phase='NETWORK_ONLY_ADMIN_NAT_INSTALL_NEXT' if review['network_only'] else 'STATE_RECONCILED_NOT_FUNCTIONAL_HEALTH',next_action='down-plan' if review['down'] else 'up-plan',possible_charges=True)

    def shutdown_observation(self):
        self.idle()
        rule=self.aws('events','describe-rule','--name','e1-wp4-dev-nat-launch');require(rule['State']=='DISABLED','NAT recovery rule not inhibited')
        functions=self.functions()
        for name in functions:
            require(self.aws('lambda','get-function-concurrency','--function-name',name).get('ReservedConcurrentExecutions')==0,'NAT/deployment invocation not inhibited')
        # A snapshot cannot certify all issued effects. Existing journal attempts
        # must be reconciled independently; incomplete read/UNKNOWN always blocks.
        listed=self.aws('s3api','list-objects-v2','--bucket',self.coordination,'--prefix','recovery/dev/recovery/')
        require(not listed.get('IsTruncated'),'incomplete E13 attempt inventory')
        keys={item['Key'] for item in listed.get('Contents',[])}
        for key in keys:
            if key.endswith('/attempt') or key.endswith('/attempt.json'):
                base=key.rsplit('/',1)[0]
                observations=[k for k in keys if k.startswith(base+'/') and (k.endswith('/observed.json') or k.endswith('/reconciled.json') or k.endswith('/observed') or k.endswith('/reconciled'))]
                require(observations,'known dispatched NAT effect without terminal readback; manual reconciliation')
                from scripts.normal_delivery import authorization as a
                attempt=self.object(key)
                planned=base+'/plan'+('.json' if key.endswith('.json') else '')
                require(planned in keys,'E13 missing exact dispatch plan')
                plan=self.object(planned)
                require(attempt==dict(token=plan['token'],plan_sha256=a.sha(a.canonical(plan))),'E13 attempt/plan mismatch')
                for k in observations:
                    effect=self.object(k)
                    require(set(effect)=={'token','request_sha256','state','result'} and effect['token']==plan['token'] and effect['request_sha256']==a.sha(a.canonical(plan['request'])),'E13 attributable effect mismatch')
                    require(effect['state'] in ('APPLIED','ABSENT') and (effect['state']!='APPLIED' or effect['result']==plan['request']),'E13 UNKNOWN/ambiguous effect')
        if any(name.startswith('e1-nat-recovery-nat-dev-') for name in functions):
            for kind in ('delivery','execution'):
                queue=self.aws('sqs','get-queue-url','--queue-name','e1-wp4-dev-nat-'+kind+'-failed','--queue-owner-aws-account-id',self.account)
                attributes=self.aws('sqs','get-queue-attributes','--queue-url',queue['QueueUrl'],'--attribute-names','ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed')['Attributes']
                require(all(int(attributes[k])==0 for k in ('ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed')),'known NAT failure messages remain; independent manual effect reconciliation required')
            # Empty approximate counts never establish total drain/finality.

        require((self.directory/'shutdown-readback.json').exists(),'run inhibit and independently reconcile existing Lambda executions/effects first')
        proof=decode((self.directory/'shutdown-readback.json').read_bytes())
        require(proof['config_sha256']==sha(c.canonical(self.config)),'same inhibition session')
        groups=self.aws('autoscaling','describe-auto-scaling-groups','--auto-scaling-group-names','demo-dev-asg-nat-a','demo-dev-asg-nat-b')['AutoScalingGroups']
        require({g['AutoScalingGroupName'] for g in groups}==set(proof['prior_instances']),'ASG inventory changed or missing')
        for group in groups:
            require(group['AutoScalingGroupName'] in ('demo-dev-asg-nat-a','demo-dev-asg-nat-b'),'foreign ASG')
            require(set(PROCESSES)<={v['ProcessName'] for v in group['SuspendedProcesses']} and 'Terminate' not in {v['ProcessName'] for v in group['SuspendedProcesses']},'native processes not inhibited')
            require(not group['Instances'] and all(group[k]==0 for k in ('MinSize','MaxSize','DesiredCapacity')),'native ASG members/capacity remain')
            for action,field in (('describe-lifecycle-hooks','LifecycleHooks'),('describe-warm-pool','Instances'),('describe-scheduled-actions','ScheduledUpdateGroupActions'),('describe-policies','ScalingPolicies')):
                observed=self.aws('autoscaling',action,'--auto-scaling-group-name',group['AutoScalingGroupName'])
                require(not observed.get('NextToken') and not observed[field],'unexpected native controller/warm pool/hook; manual reconciliation')
            activities=self.aws('autoscaling','describe-scaling-activities','--auto-scaling-group-name',group['AutoScalingGroupName'])
            require(not activities.get('NextToken') and all(v['StatusCode'] in ('Successful','Failed','Cancelled') and v.get('EndTime') for v in activities['Activities']),'ASG replacement active/ambiguous')
        require(set(proof['prior_instances'])<= {'demo-dev-asg-nat-a','demo-dev-asg-nat-b'},'prior NAT identities before capacity mutation')
        previous=sorted({i for ids in proof['prior_instances'].values() for i in ids})
        if previous:
            old=self.aws('ec2','describe-instances','--instance-ids',*previous)
            observed={i['InstanceId']:i for r in old['Reservations'] for i in r['Instances']}
            require(set(observed)==set(previous) and all(i['State']['Name']=='terminated' for i in observed.values()),'prior NAT termination unverified')
        cluster=self.state('platform')['outputs'].get('cluster_name')
        if cluster:
            services=self.aws('ecs','describe-services','--cluster',cluster,'--services','demo-dev-app-api-blue-svc','demo-dev-app-api-green-svc')
            if self.state('apps')['rows']:
                require(not services.get('failures') and len(services['services'])==2,'exact ECS readback')
            else:require(all(v.get('reason')=='MISSING' for v in services.get('failures',[])),'ECS removal ambiguous')
            require(all(all(v[k]==0 for k in ('desiredCount','runningCount','pendingCount')) for v in services['services']),'ECS not drained')
            tasks=self.aws('ecs','list-tasks','--cluster',cluster,'--desired-status','RUNNING')
            require(not tasks.get('nextToken') and not tasks['taskArns'],'live/pending tasks remain')
        require(set(functions)==set(proof['timeouts']),'callable controllers changed after inhibition; do not reuse closure')
        # The owner accepts supervised observation, not an invocation-cancellation
        # guarantee. Require the API-completed inhibition interval, configured
        # maximum function duration and observed execution data; no empty metric
        # response is treated as zero and no timeout alone establishes finality.
        require(proof.get('reviewed') is True,'explicit supervised inhibition review required')
        for name in proof['timeouts']:
            require(time.time() >= proof['at']+proof['timeouts'][name],'previous Lambda can still be running within configured timeout')
            start=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(proof['at']))
            stop=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            metrics=self.aws('cloudwatch','get-metric-statistics','--namespace','AWS/Lambda','--metric-name','ConcurrentExecutions','--dimensions','Name=FunctionName,Value='+name,
                '--start-time',start,'--end-time',stop,'--period','60','--statistics','Maximum')
            from datetime import datetime,timezone
            points=[v for v in metrics['Datapoints'] if datetime.fromisoformat(v['Timestamp'].replace('Z','+00:00')).timestamp()>=proof['at']+proof['timeouts'][name]]
            require(points and all(v['Maximum']==0 for v in points) and max(datetime.fromisoformat(v['Timestamp'].replace('Z','+00:00')).timestamp() for v in points)>=time.time()-180,'Lambda activity positive/stale or metric absence; manual reconciliation')
        return dict(model='SUPERVISED_BOUNDED_OBSERVATIONS',executor_finality='NOT_CERTIFIED',unobservable_late_effect_risk='RETAINED',aws_verified=type(self.process) is Process)

    def inhibit(self,confirmation):
        self.identity();self.source();self.backend();self.idle()
        require(confirmation=='INHIBIT DEV '+self.account+' '+self.region,'explicit administrative inhibition confirmation')
        file=self.directory/'shutdown-attempt.json';require(not file.exists(),'prior inhibition ambiguous; never blind retry')
        prior=self.aws('autoscaling','describe-auto-scaling-groups','--auto-scaling-group-names','demo-dev-asg-nat-a','demo-dev-asg-nat-b')['AutoScalingGroups']
        require(len(prior)<=2 and {g['AutoScalingGroupName'] for g in prior}<= {'demo-dev-asg-nat-a','demo-dev-asg-nat-b'},'exact existing ASGs before inhibition')
        previous={g['AutoScalingGroupName']:[i['InstanceId'] for i in g['Instances']] for g in prior}
        self.save(file,dict(state='UNKNOWN',config_sha256=sha(c.canonical(self.config)),prior_instances=previous))
        self.aws('events','disable-rule','--name','e1-wp4-dev-nat-launch')
        timeouts={}
        names=sorted(self.functions())
        for name in names:
            versions=self.aws('lambda','list-versions-by-function','--function-name',name)
            require(not versions.get('NextMarker') and bool(versions['Versions']),'complete published version timeout inventory')
            timeouts[name]=max(v['Timeout'] for v in versions['Versions'])
            self.aws('lambda','put-function-concurrency','--function-name',name,'--reserved-concurrent-executions','0')
        self.idle()
        cluster=self.state('platform')['outputs'].get('cluster_name')
        if cluster:
            for color in ('blue','green'):self.aws('ecs','update-service','--cluster',cluster,'--service','demo-dev-app-api-'+color+'-svc','--desired-count','0')
        for name in sorted(previous):
            self.aws('autoscaling','suspend-processes','--auto-scaling-group-name',name,'--scaling-processes',*PROCESSES)
            self.aws('autoscaling','update-auto-scaling-group','--auto-scaling-group-name',name,'--min-size','0','--max-size','0','--desired-capacity','0')
        self.save(self.directory/'shutdown-readback.json',dict(config_sha256=sha(c.canonical(self.config)),state='INHIBITION_REQUESTED_FINALITY_UNVERIFIED',prior_instances=previous,timeouts=timeouts,at=int(time.time()),reviewed=False))
        return dict(stage='INHIBITION_REQUESTED_RECONCILE_BEFORE_DOWN',possible_charges=True)

    def review_inhibition(self,confirmation):
        self.identity();self.source();self.backend();self.idle()
        require(confirmation=='REVIEW SUPERVISED DEV INHIBITION '+self.account+' '+self.region,'explicit bounded-observation shutdown decision; no finality certificate')
        file=self.directory/'shutdown-readback.json';value=decode(file.read_bytes())
        require(value['config_sha256']==sha(c.canonical(self.config)),'same session')
        value['reviewed']=True
        file.write_bytes(c.canonical(value));file.chmod(0o600)
        try:return self.shutdown_observation()
        except Exception:
            value['reviewed']=False;file.write_bytes(c.canonical(value));raise

    def status(self):
        self.identity();self.source();self.backend()
        states={l:self.state(l) for l in UP}
        return dict(layers={l:[dict(address=r['address'],id=r['values'].get('id')) for r in s['rows']] for l,s in states.items()},
            aws_verified=type(self.process) is Process,functional_health='UNVERIFIED',possible_charges=True)

    def residual(self):
        result=self.status()
        tags=self.aws('resourcegroupstaggingapi','get-resources','--tag-filters','Key=Environment,Values=dev','Key=Project,Values=demo')
        require(not tags.get('PaginationToken'),'incomplete resource inventory')
        observed={};remaining=[];known=[]
        for file in (self.directory/'plans').glob('*/inventory.json'):
            known+=decode(file.read_bytes())['rows']
        for action,field in (('describe-instances','Reservations'),('describe-volumes','Volumes'),('describe-addresses','Addresses'),('describe-network-interfaces','NetworkInterfaces')):
            value=self.aws('ec2',action,'--filters','Name=tag:Environment,Values=dev','Name=tag:Project,Values=demo')
            require(not value.get('NextToken'),'incomplete EC2 residual inventory');observed[field]=value[field]
            if field=='Reservations':
                remaining += [i['InstanceId'] for r in value[field] for i in r['Instances'] if i['State']['Name']!='terminated']
            else:remaining += [v.get('VolumeId') or v.get('AllocationId') or v.get('NetworkInterfaceId') for v in value[field]]
        # Fargate/VPC Link ENIs need parent-scoped reads; inherited tags are not
        # guaranteed. Inventories were saved before dispatch, even on lost ACK.
        vpcs={r['values']['id'] for r in known if r['type']=='aws_vpc'}
        for vpc in vpcs:
            interfaces=self.aws('ec2','describe-network-interfaces','--filters','Name=vpc-id,Values='+vpc)
            require(not interfaces.get('NextToken'),'incomplete parent ENI inventory')
            remaining += [v['NetworkInterfaceId'] for v in interfaces['NetworkInterfaces']]
        expected={r['values'].get('arn') for layer in UP for r in self.state(layer)['rows']}
        # Protected/reference resources may be deliberately retained with dev
        # naming. Do not propose their deletion from an Environment tag alone.
        authority=decode((ROOT/'terraform/infra/security/authority.json').read_bytes())
        publication=authority['ownership_closure']['publications'].get(self.account+'/'+self.region,{})
        retained_arns={v['value'] for v in publication.get('records',{}).values() if v.get('available')}
        categories=[]
        for item in tags['ResourceTagMappingList']:
            arn=item['ResourceARN']
            categories.append(dict(arn=arn,disposition='RETAINED_PROTECTED' if arn in retained_arns else 'MANAGED_RUNTIME_PRESENT' if arn in expected else 'UNEXPECTED_OR_UNVERIFIED_SURVIVOR'))
        result.update(observed=observed,tagged=categories,present_billable=sorted(set(remaining)),
            retained=['shared','secrets','security-root','backend/versions/locking','ECR/evidence'],
            state='PARTIAL_OR_RETAINED_RESOURCES_REQUIRE_REVIEW' if remaining or any(v['disposition']=='UNEXPECTED_OR_UNVERIFIED_SURVIVOR' for v in categories) else 'NO_RUNTIME_OBSERVED_IN_BOUNDED_INVENTORY',
            zero_cost_claim=False,unverified=['untagged resources outside recorded VPCs','pending KMS/secret deletion','historical images/log storage','independent service deletion where tags are unsupported'])
        return result

    def verify(self):
        result=self.status();out=self.state('edge')['outputs'];api=out['api_id']
        gateway=self.aws('apigatewayv2','get-api','--api-id',api);require(gateway['ApiId']==api and gateway['ApiEndpoint']==out['api_endpoint'] and re.fullmatch(r'https://[a-z0-9]+\.execute-api\.'+re.escape(self.region)+r'\.amazonaws\.com',gateway['ApiEndpoint']),'actual API endpoint')
        link=self.aws('apigatewayv2','get-vpc-link','--vpc-link-id',out['vpc_link_id']);require(link['VpcLinkStatus']=='AVAILABLE','VPC Link readiness')
        services=self.aws('ecs','describe-services','--cluster','demo-dev-platform-main-cluster','--services','demo-dev-app-api-blue-svc','demo-dev-app-api-green-svc')
        require(not services.get('failures') and len(services['services'])==2,'exact original services')
        require(sum(s['runningCount'] for s in services['services'])>=1 and all(s['runningCount']==s['desiredCount'] and s['pendingCount']==0 for s in services['services']),'ECS steady state')
        groups=self.aws('autoscaling','describe-auto-scaling-groups','--auto-scaling-group-names','demo-dev-asg-nat-a','demo-dev-asg-nat-b')['AutoScalingGroups']
        require(len(groups)==2 and all(len(g['Instances'])==1 and g['Instances'][0]['HealthStatus']=='Healthy' and g['Instances'][0]['LifecycleState']=='InService' for g in groups),'both NAT instance slots')
        data=self.state('data');require(data['rows'],'SQL state present')
        instance=self.aws('ec2','describe-instances','--instance-ids',data['outputs']['instance_id'])['Reservations']
        require(len(instance)==1 and len(instance[0]['Instances'])==1 and instance[0]['Instances'][0]['State']['Name']=='running' and instance[0]['Instances'][0]['PrivateIpAddress']==data['outputs']['db_private_ip'],'SQL actual running identity/IP')
        tasklist=self.aws('ecs','list-tasks','--cluster','demo-dev-platform-main-cluster','--desired-status','RUNNING')
        require(not tasklist.get('nextToken') and bool(tasklist['taskArns']),'actual bounded ECS tasks')
        tasks=self.aws('ecs','describe-tasks','--cluster','demo-dev-platform-main-cluster','--tasks',*tasklist['taskArns'])
        require(not tasks.get('failures') and len(tasks['tasks'])==len(tasklist['taskArns']),'exact task readback')
        for task in tasks['tasks']:
            definition=task['taskDefinitionArn'];family=definition.rsplit('/',1)[1].rsplit(':',1)[0]
            require(definition.startswith(f'arn:aws:ecs:{self.region}:{self.account}:task-definition/') and family in ('demo-dev-app-api-blue','demo-dev-app-api-green') and task['group']=='service:'+family+'-svc','exact original task family/service')
            probe=[v for v in task['containers'] if v['name']==family+'-readiness-probe'];app=[v for v in task['containers'] if v['name']==family]
            require(len(task['containers'])==2,'exact original application/probe container set')
            require(task['lastStatus']=='RUNNING' and len(probe)==1 and probe[0].get('exitCode')==0 and len(app)==1 and app[0]['lastStatus']=='RUNNING','actual per-task readiness contract')
        global_state=self.state('global')
        tables=self.aws('ec2','describe-route-tables','--filters','Name=vpc-id,Values='+global_state['outputs']['vpc_id'])['RouteTables']
        network=[]
        for group in groups:
            identity=group['Instances'][0]['InstanceId']
            value=self.aws('ec2','describe-instance-attribute','--instance-id',identity,'--attribute','sourceDestCheck')
            require(value['SourceDestCheck']['Value'] is False,'NAT SDC readback')
            details=self.aws('ec2','describe-instances','--instance-ids',identity)['Reservations']
            require(len(details)==1 and len(details[0]['Instances'])==1,'exact NAT instance')
            inst=details[0]['Instances'][0];require(inst['VpcId']==global_state['outputs']['vpc_id'] and inst['State']['Name']=='running','NAT VPC/state')
            enis={v['NetworkInterfaceId'] for v in inst['NetworkInterfaces']}
            require(any(r.get('DestinationCidrBlock')=='0.0.0.0/0' and r.get('NetworkInterfaceId') in enis and r['State']=='active' for table in tables for r in table['Routes']),'NAT private default route readback')
            addresses=self.aws('ec2','describe-addresses','--allocation-ids',*global_state['outputs']['nat_eip_allocation_ids'].values())['Addresses']
            require(any(v.get('NetworkInterfaceId') in enis and v.get('InstanceId')==identity for v in addresses),'NAT EIP association')
            network.append(identity)
        ready=decode(self.process.run(['curl','--fail','--max-time','15',gateway['ApiEndpoint']+'/ready']))
        require(ready['status']=='Healthy' and {v['name']:v['status'] for v in ready['checks']}=={'database':'Healthy','kms':'Healthy'},'application SQL/KMS readiness via Gateway/ALB')
        marker='e16-smoke-'+str(uuid.uuid4())
        created=decode(self.process.run(['curl','--fail','--max-time','15','--request','POST','--header','Content-Type: application/json','--data-binary','@-',gateway['ApiEndpoint']+'/text'],data=c.canonical(dict(text=marker))))
        rows=decode(self.process.run(['curl','--fail','--max-time','15',gateway['ApiEndpoint']+'/text?page=1&pageSize=100']))
        require(created['text']==marker and any(v['id']==created['id'] and v['text']==marker for v in rows),'actual SQL insert/read and KMS encrypt/decrypt roundtrip')
        result.update(stage='OBSERVED_GATEWAY_APPLICATION_ROUNDTRIP',endpoint=gateway['ApiEndpoint'],unverified=['both private-subnet packet forwarding','SSM/bootstrap marker'])
        return result


def main(argv=None,process=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','status','bootstrap-status','bootstrap-network-plan','up-plan','apply','down-plan','inhibit','review-inhibition','verify','residual'))
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--layer',choices=DOWN,help='review an existing DEV layer before shutdown; apply still enforces reverse order')
    parser.add_argument('--plan-id');parser.add_argument('--confirm');parser.add_argument('--confirm-sql-loss')
    parser.add_argument('--aws-config-file',type=Path);parser.add_argument('--terraform-wsl-bin',type=Path);parser.add_argument('--terraform-plugin-cache',type=Path)
    args=parser.parse_args(argv);require(args.layer is None or args.action=='down-plan','--layer is only a DOWN preview selector');config=decode(args.config.read_bytes())
    session=Session(config,args.directory,process or Process(config,args.aws_config_file,args.terraform_wsl_bin,args.terraform_plugin_cache))
    if args.action=='init':result=session.initialize()
    elif args.action=='bootstrap-status':result=session.bootstrap_status()
    elif args.action=='up-plan':result=session.prepare()
    elif args.action=='bootstrap-network-plan':result=session.prepare(network_only=True)
    elif args.action=='down-plan':result=session.prepare(True,down_layer=args.layer)
    elif args.action=='apply':result=session.apply(args.plan_id,args.confirm,args.confirm_sql_loss)
    elif args.action=='inhibit':result=session.inhibit(args.confirm)
    elif args.action=='review-inhibition':result=session.review_inhibition(args.confirm)
    else:result=getattr(session,args.action)()
    print(json.dumps(result,indent=2));return 0
