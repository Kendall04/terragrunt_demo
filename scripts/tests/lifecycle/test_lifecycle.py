"""Actual lifecycle ports and action/resource/condition checks; no live evidence."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import wp5
import wp5_iam as iam
from test_wp4d import permits
from scripts.lifecycle import contract as c, packages, runtime
from scripts.lifecycle.controller import Controller

ROOT=Path(__file__).resolve().parents[3]
ACCOUNT='123456789012'
REGION='us-east-1'
UUID='11111111-1111-4111-8111-111111111111'
DOC=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())

def request(revision='a'*64,layer='platform',operation='create'):
    return dict(operation_id=UUID,operation=operation,layer=layer,revision=revision,parameters={})

def projection():
    installations={};images={};bindings={}
    for key,selected in DOC['wp5']['selected'].items():
        env=selected['environment'];sha=selected['package_sha256']
        reference=dict(binding=key,bucket=f'e1-control-bundles-{ACCOUNT}-{REGION}',key='bundles/sha256/'+sha+'.json',
            version_id='SYNTHETIC_OFFLINE_VERSION',sha256=sha,source_commit='b'*40)
        installations[key]={**reference,'readback':'EXACT_VERSION_BYTES_VERIFIED'}
        images[key]=dict(uri=f'{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/e1-wp5-'+key.replace('/','-')+'@sha256:'+'c'*64,
            package_sha256=sha,source_commit='b'*40,tools=dict(terraform='1.13.4',providers='LOCKED_READONLY_MIRROR',python='PROTECTED_IMAGE'))
        layers={name:dict(root=f'terraform/modules/target/{env}/{name}',variables=dict(account_id=ACCOUNT,region=REGION),
            addresses={},membership={},backend=dict(bucket=f'e1-lifecycle-{env}-{ACCOUNT}-{REGION}',key=f'e1/lifecycle/{env}/{name}/terraform.tfstate',region=REGION)) for name in wp5.LAYERS}
        for name,inputs in selected['required_inputs'].items():
            for field in inputs:layers[name]['variables'].setdefault(field,'SYNTHETIC_OFFLINE_BINDING')
        resources={kind:[] for kind in iam.INVENTORY}
        resources['aws_ecs_cluster']=[f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-{env}-platform-main-cluster']
        layers['platform']['addresses']={'module.ecs_cluster.aws_ecs_cluster.this':'aws_ecs_cluster'}
        configuration=dict(binding=key,environment=env,account=ACCOUNT,region=REGION,active_contracts=[sha],installations={sha:reference},
            layers=layers,bootstrap=dict(state_store='ADMIN_VERIFIED_READY',configuration_publication='ADMIN_VERIFIED_READY',service_linked_roles='ADMIN_VERIFIED_READY',sql_passwords='ADMIN_VERIFIED_READY',connection_string='ADMIN_VERIFIED_READY'),operation_approvals={},teardown_approvals={})
        bindings[key]=dict(configuration=configuration,resources=resources,sql_launch=dict(
            image=f'arn:aws:ec2:{REGION}::image/ami-12345678',subnet=f'arn:aws:ec2:{REGION}:{ACCOUNT}:subnet/subnet-12345678',
            security_group=f'arn:aws:ec2:{REGION}:{ACCOUNT}:security-group/sg-12345678',instance_type='t3a.small'))
    return installations,images,bindings

def plan(kind='aws_ecs_cluster',action='create',before=None,after=None,address='module.ecs_cluster.aws_ecs_cluster.this'):
    return dict(format_version='1.2',applyable=True,errored=False,resource_changes=[dict(address=address,type=kind,mode='managed',
        change=dict(actions=[action],before=before,after=after if after is not None else {},after_unknown={},before_sensitive={},after_sensitive={}))])

def quiescent(env='dev'):
    return dict(environment=env,complete=True,tasks=[],services={f'demo-{env}-app-api-{color}-svc':dict(desired=0,running=0,pending=0) for color in ('blue','green')})

class Memory:
    def __init__(self):self.values={}
    def read(self,k):return self.values.get(k)
    def create(self,k,v):
        c.require(k not in self.values,'conditional intent');self.values[k]=v
    def complete(self,k,v):self.values[k]=v

class Engine:
    def __init__(self,p):self.p=p;self.applies=0
    def prepare(self,*args):pass
    def plan(self,**kwargs):return self.p
    def observe(self,env):return quiescent(env)
    def apply(self,*args):self.applies+=1
    def verify(self,*args):return True

class Checked:
    def verify(self,reference):return reference

class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.i,self.r,self.b=projection();self.key='environment-lifecycle/infra-dev'
        self.protected=self.b[self.key]['configuration'];self.sha=DOC['wp5']['selected'][self.key]['package_sha256']
        self.value=request(self.sha);self.layer=self.protected['layers']['platform']
    def reject(self,fn,*args):
        with self.assertRaises(ValueError):fn(*args)
    def test_authorized_dev_prod_operations(self):
        for key in ('environment-lifecycle/infra-dev','environment-lifecycle/infra-prod'):
            p=self.b[key]['configuration'];v=request(DOC['wp5']['selected'][key]['package_sha256'])
            self.assertEqual(c.authorize(key,v,p,p['installations'][v['revision']])[0],v)
    def test_closed_payload(self):
        for field in ('root','backend','role','terraform','command','source','environment','buildspecOverride'):
            self.reject(c.request,self.key,{**self.value,field:'attacker'})
    def test_ordinary_cannot_select_high_risk_or_teardown(self):
        for layer in ('data','apps'):self.reject(c.request,self.key,{**self.value,'layer':layer})
        self.reject(c.request,self.key,{**self.value,'operation':'teardown'})
    def test_routine_parameter_types(self):
        key='environment-lifecycle/infra-high-risk-dev'
        self.assertEqual(c.request(key,request(self.sha,'data')|{'parameters':{'enable_alarms':False}})['parameters'],{'enable_alarms':False})
        for value in (0,'false',None):self.reject(c.request,key,request(self.sha,'data')|{'parameters':{'enable_alarms':value}})
    def test_active_revision_required(self):
        self.protected['active_contracts']=[]
        self.reject(c.authorize,self.key,self.value,self.protected,self.i[self.key])
    def test_missing_installation_denies(self):
        self.protected['installations']={}
        self.reject(c.authorize,self.key,self.value,self.protected,{})
    def test_exact_version_denies_null_latest(self):
        for version in ('','null','latest',' version '):
            p=copy.deepcopy(self.protected);ref=p['installations'][self.sha];ref['version_id']=version
            self.reject(c.authorize,self.key,self.value,p,ref)
    def test_wrong_environment_and_provider_denies(self):
        for change in (lambda p:p.update(environment='prod'),lambda p:p['layers']['platform']['variables'].update(account_id='999999999999')):
            p=copy.deepcopy(self.protected);change(p);self.reject(c.authorize,self.key,self.value,p,p['installations'][self.sha])
    def test_replacement_backend_denies(self):
        for field in ('bucket','key','region'):
            p=copy.deepcopy(self.protected);p['layers']['platform']['backend'][field]='attacker'
            self.reject(c.authorize,self.key,self.value,p,p['installations'][self.sha])
    def test_operator_approval_required(self):
        key='environment-lifecycle/infra-high-risk-dev';p=self.b[key]['configuration'];v=request(DOC['wp5']['selected'][key]['package_sha256'],'data')
        self.reject(c.authorize,key,v,p,p['installations'][v['revision']])
        p['operation_approvals'][UUID]=dict(request_sha256=c.digest(c.canonical(v)),environment='dev')
        self.assertEqual(c.authorize(key,v,p,p['installations'][v['revision']])[0],v)
    def test_secret_bootstrap_missing_denies(self):
        key='environment-lifecycle/infra-high-risk-dev';p=self.b[key]['configuration'];v=request(DOC['wp5']['selected'][key]['package_sha256'],'data')
        p['bootstrap'].pop('sql_passwords');self.reject(c.authorize,key,v,p,p['installations'][v['revision']])
    def test_positive_plan_and_recorded_retry(self):
        records=Memory();engine=Engine(plan());ctrl=Controller(self.key,self.protected,Checked(),engine,records)
        self.assertEqual(ctrl.run(self.value)['state'],'SUCCESS');self.assertEqual(ctrl.run(self.value)['state'],'SUCCESS')
        self.assertEqual(engine.applies,1)
        self.reject(ctrl.run,{**self.value,'operation':'plan'})
    def test_lost_ack_retained_unknown(self):
        records=Memory();engine=Engine(plan());engine.apply=lambda *args:(_ for _ in ()).throw(RuntimeError())
        ctrl=Controller(self.key,self.protected,Checked(),engine,records)
        self.assertEqual(ctrl.run(self.value)['state'],'UNKNOWN');self.assertEqual(ctrl.run(self.value)['state'],'UNKNOWN')
    def test_readback_failure_retained_unknown(self):
        engine=Engine(plan());engine.verify=lambda *args:(_ for _ in ()).throw(RuntimeError())
        self.assertEqual(Controller(self.key,self.protected,Checked(),engine,Memory()).run(self.value)['state'],'UNKNOWN')
    def test_plan_only_no_apply(self):
        engine=Engine(plan());v={**self.value,'operation':'plan'}
        self.assertEqual(Controller(self.key,self.protected,Checked(),engine,Memory()).run(v)['state'],'PLANNED');self.assertEqual(engine.applies,0)
    def test_drift_unknown_address_protected_type_rejected(self):
        for bad in (plan(address='attacker'),{**plan(),'resource_drift':[{}]}, {**plan(),'deferred_changes':[{}]}):
            self.reject(c.validate_plan,self.value,self.layer,bad)
        layer={**self.layer,'addresses':{'attacker':'aws_iam_role'}}
        self.reject(c.validate_plan,self.value,layer,plan('aws_iam_role',address='attacker'))
    def test_membership_and_authorizing_tags(self):
        address=next(iter(self.layer['addresses']));self.layer['membership']={address:'id-owned'}
        v={**self.value,'operation':'reconcile'}
        self.assertIsInstance(c.validate_plan(v,self.layer,plan(action='update',before={'id':'id-owned','tags':{}},after={'id':'id-owned','tags':{}})),str)
        self.reject(c.validate_plan,v,self.layer,plan(action='update',before={'id':'other'},after={}))
        self.reject(c.validate_plan,v,self.layer,plan(action='update',before={'id':'id-owned','tags':{}},after={'tags':{'Environment':'prod'}}))
    def test_replacement_requires_separate_teardown(self):
        p=plan();p['resource_changes'][0]['change']['actions']=['delete','create']
        self.reject(c.validate_plan,{**self.value,'operation':'reconcile'},self.layer,p)
    def test_service_bootstrap_zero_no_exec_fargate(self):
        layer={**self.layer,'addresses':{'service':'aws_ecs_service'}}
        after={'desired_count':0,'enable_execute_command':False,'launch_type':'FARGATE'}
        self.assertIsInstance(c.validate_plan(self.value,layer,plan('aws_ecs_service',after=after,address='service')),str)
        for field,bad in (('desired_count',1),('enable_execute_command',True),('launch_type','EC2')):
            self.reject(c.validate_plan,self.value,layer,plan('aws_ecs_service',after={**after,field:bad},address='service'))
    def test_no_runtime_service_redefinition(self):
        layer={**self.layer,'addresses':{'service':'aws_ecs_service'},'membership':{'service':'id'}}
        before={'id':'id','desired_count':3,'task_definition':'successful','cluster':'owned','tags':{}}
        for field in c.RUNTIME_FIELDS['aws_ecs_service']+c.EXECUTION_FIELDS['aws_ecs_service']:
            self.reject(c.validate_plan,{**self.value,'operation':'reconcile'},layer,plan('aws_ecs_service','update',before,{**before,field:'changed'},'service'))
    def test_bootstrap_definition_role_and_secret_free(self):
        layer={**self.layer,'addresses':{'td':'aws_ecs_task_definition'}}
        after={'container_definitions':'[{"name":"bootstrap","secrets":[]}]'}
        self.assertIsInstance(c.validate_plan(self.value,layer,plan('aws_ecs_task_definition',after=after,address='td')),str)
        for changed in ({**after,'task_role_arn':'role'},{**after,'execution_role_arn':'role'}, {'container_definitions':'[{"secrets":[{}]}]'}):
            self.reject(c.validate_plan,self.value,layer,plan('aws_ecs_task_definition',after=changed,address='td'))
    def test_quiescence_complete_exact_services(self):
        c.quiescent(quiescent(),'dev')
        for changed in ({**quiescent(),'complete':False},{**quiescent(),'services':{}},{**quiescent(),'tasks':['pending']},{**quiescent(),'environment':'prod'}):self.reject(c.quiescent,changed,'dev')
    def test_nonzero_blocks_teardown(self):
        q=quiescent();next(iter(q['services'].values()))['running']=1
        self.reject(c.validate_plan,{**self.value,'operation':'teardown'},self.layer,dict(format_version='1.2',resource_changes=[]),q,'dev')
    def test_all_compute_missing_prerequisites_inactive(self):
        self.assertEqual(wp5.creation_supported(DOC,{},{},{},ACCOUNT,REGION),[])
        self.assertEqual(len(wp5.creation_supported(DOC,self.i,self.r,self.b,ACCOUNT,REGION)),8)
    def test_installation_and_active_gate_negatives(self):
        for field,bad in (('version_id','latest'),('readback','UNVERIFIED'),('sha256','f'*64)):
            i=copy.deepcopy(self.i)
            for v in i.values():v[field]=bad
            self.assertEqual(wp5.creation_supported(DOC,i,self.r,self.b,ACCOUNT,REGION),[])
        b=copy.deepcopy(self.b)
        for v in b.values():v['configuration']['active_contracts']=[]
        self.assertEqual(wp5.creation_supported(DOC,self.i,self.r,b,ACCOUNT,REGION),[])
    def test_gateway_requires_own_controller(self):
        self.i.pop(self.key)
        active=wp5.creation_supported(DOC,self.i,self.r,self.b,ACCOUNT,REGION)
        self.assertNotIn('request-gateway/infra-dev',active);self.assertEqual(len(active),6)
    def test_packages_deterministic_complete_layers(self):
        for key in wp5.BINDINGS:
            raw=wp5.artifact(ROOT,DOC,key);self.assertEqual(raw,wp5.artifact(ROOT,DOC,key))
            self.assertEqual(c.digest(raw),DOC['wp5']['selected'][key]['package_sha256'])
            files=json.loads(raw)['files'];env=key.rsplit('-',1)[1]
            for layer in wp5.LAYERS:self.assertIn(f'terraform/modules/target/{env}/{layer}/.terraform.lock.hcl',files)
            self.assertIn('terraform/infra/data/user_data.sh',files)
    def test_exact_readback_version_bytes(self):
        raw=wp5.artifact(ROOT,DOC,self.key);ref=self.protected['installations'][self.sha]
        class S3:
            def get_object(self,**kwargs):
                self.args=kwargs;return {'VersionId':ref['version_id'],'Body':io.BytesIO(raw)}
        s3=S3()
        with tempfile.TemporaryDirectory() as directory:self.assertEqual(packages.verify(s3,ref,directory),ref)
        self.assertEqual(s3.args['VersionId'],ref['version_id'])
    def test_wrong_package_readback_rejected(self):
        ref=self.protected['installations'][self.sha]
        for raw,version in ((b'{}',ref['version_id']),(wp5.artifact(ROOT,DOC,self.key),'different')):
            class S3:
                def get_object(self,**kwargs):return {'VersionId':version,'Body':io.BytesIO(raw)}
            with tempfile.TemporaryDirectory() as directory:self.reject(packages.verify,S3(),ref,directory)
    def test_external_requests_remain_inert_and_wp4d_empty(self):
        self.assertEqual(len(DOC['request_identities']),11)
        self.assertTrue(all(v['stage']=='INERT' for v in DOC['request_identities'].values()))
        for key in ('installations','runtime_approvals','environment_bindings'):self.assertEqual(DOC['wp4d'][key],{})
    def test_expected_delivery_drift_preserved(self):
        layer={**self.layer,'addresses':{'service':'aws_ecs_service'},'membership':{'service':'id'}}
        drift=plan('aws_ecs_service','update',{'id':'id','desired_count':0,'task_definition':'bootstrap'},
            {'id':'id','desired_count':3,'task_definition':'successful'},'service')['resource_changes'][0]
        unchanged=plan('aws_ecs_service','no-op',drift['change']['after'],drift['change']['after'],'service')
        unchanged['resource_drift']=[drift];unchanged['applyable']=False
        self.assertIsInstance(c.validate_plan({**self.value,'operation':'reconcile'},layer,unchanged),str)
        drift['change']['after']['cluster']='unrelated'
        self.reject(c.validate_plan,{**self.value,'operation':'reconcile'},layer,unchanged)
    def test_teardown_after_exact_live_absence(self):
        q=quiescent();q['services']={name:{'absence':'EXACT_ECS_MISSING'} for name in q['services']}
        c.quiescent(q,'dev')
        q['services'][next(iter(q['services']))]={'absence':'CLAIMED'};self.reject(c.quiescent,q,'dev')
    def test_live_adapter_exact_cluster_absence(self):
        cluster=f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-dev-platform-main-cluster'
        self.protected['layers']['apps']['variables']['cluster_arn']=cluster
        class ECS:
            def describe_clusters(self,clusters):return {'clusters':[],'failures':[{'arn':clusters[0],'reason':'MISSING'}]}
        observation=runtime.Terraform(ROOT,ECS(),self.protected).observe('dev')
        c.quiescent(observation,'dev')
        class Wrong:
            def describe_clusters(self,clusters):return {'clusters':[],'failures':[{'arn':cluster.replace('dev','prod'),'reason':'MISSING'}]}
        self.reject(runtime.Terraform(ROOT,Wrong(),self.protected).observe,'dev')
    def test_missing_required_root_inputs_denies(self):
        b=copy.deepcopy(self.b)
        for value in b.values():value['configuration']['layers']['global']['variables'].pop('alerts_topic_arn')
        self.assertEqual(wp5.creation_supported(DOC,self.i,self.r,b,ACCOUNT,REGION),[])
    def test_admin_install_receipt_origin_and_readback(self):
        from publication import AdminBundleStorage
        class Storage(AdminBundleStorage):
            def put_if_absent(self,bucket,key,raw,checksum):
                self.raw=raw;return dict(bucket=bucket,key=key,version_id='SYNTHETIC_STORAGE_RETURN')
            def get_exact(self,bucket,key,version_id):return dict(bucket=bucket,key=key,version_id=version_id,bytes=self.raw)
        receipt=wp5.install(ROOT,DOC,self.key,ACCOUNT,REGION,Storage(),'b'*40)
        self.assertEqual(receipt['version_id'],'SYNTHETIC_STORAGE_RETURN');self.assertEqual(receipt['readback'],'EXACT_VERSION_BYTES_VERIFIED')
        class Bad(Storage):
            def get_exact(self,*args):return {}
        self.reject(wp5.install,ROOT,DOC,self.key,ACCOUNT,REGION,Bad(),'b'*40)
    def test_admin_publication_required_and_exact_readback(self):
        observed={**self.b[self.key],'complete':True}
        class Channel(wp5.LifecycleAdminChannel):
            def observe(self,binding):return observed
            def write_current(self,bucket,key,raw):self.raw=raw;return dict(bucket=bucket,key=key,version_id='SYNTHETIC_RETURN')
            def read_exact(self,bucket,key,version):return dict(bucket=bucket,key=key,version_id=version,bytes=self.raw)
        receipt=wp5.publish(DOC,self.key,self.i[self.key],self.r[self.key],ACCOUNT,REGION,Channel())
        self.assertEqual(receipt['verification'],'EXACT_VERSION_BYTES_VERIFIED')
        observed['complete']=False;self.reject(wp5.publish,DOC,self.key,self.i[self.key],self.r[self.key],ACCOUNT,REGION,Channel())
    def test_gateway_exact_request_start_and_revocation(self):
        key='request-gateway/infra-dev';config=dict(binding=key,account=ACCOUNT,region=REGION,
            package=self.b[key]['configuration']['installations'][DOC['wp5']['selected'][key]['package_sha256']])
        class S3:
            def __init__(port):port.objects={};port.calls=[]
            def get_object(port,**kwargs):
                port.calls.append(kwargs)
                path=kwargs['Key']
                if path.startswith('lifecycle/'):
                    binding=path[len('lifecycle/'):].removesuffix('/current.json')
                    return {'Body':io.BytesIO(c.canonical(self.b[binding]['configuration']))}
                if path.startswith('bundles/'):
                    binding=next(k for k,v in DOC['wp5']['selected'].items() if path.endswith(v['package_sha256']+'.json'))
                    return {'VersionId':kwargs['VersionId'],'Body':io.BytesIO(wp5.artifact(ROOT,DOC,binding))}
                if path not in port.objects:
                    exc=RuntimeError();exc.response={'Error':{'Code':'NoSuchKey'}};raise exc
                return {'Body':io.BytesIO(port.objects[path])}
            def put_object(port,**kwargs):
                self.assertEqual(kwargs['IfNoneMatch'],'*');self.assertNotIn(kwargs['Key'],port.objects);port.objects[kwargs['Key']]=kwargs['Body']
        class CodeBuild:
            def start_build(port,**kwargs):port.args=kwargs;return {'build':{'projectName':kwargs['projectName'],'id':kwargs['projectName']+':id'}}
        s3=S3();cb=CodeBuild()
        self.assertEqual(runtime.execute(self.value,config,dict(s3=s3,codebuild=cb))['state'],'STARTED')
        self.assertEqual(cb.args,{'projectName':'e1-controller-infra-dev'})
        self.b[key]['configuration']['active_contracts']=[]
        self.reject(runtime.execute,self.value,config,dict(s3=s3,codebuild=cb))

class Authority(unittest.TestCase):
    def setUp(self):
        self.i,self.r,self.b=projection();self.key='environment-lifecycle/infra-dev'
        self.resources=self.b[self.key]['resources']
    def policy(self,key=None,resources=None):
        return iam.policy(key or self.key,ACCOUNT,REGION,resources or self.resources,'a'*64,'SYNTHETIC_VERSION')
    def test_exact_environment_cluster_positive_negative(self):
        p=self.policy();dev=self.resources['aws_ecs_cluster'][0]
        self.assertTrue(permits(p,'ecs:DeleteCluster',dev));self.assertFalse(permits(p,'ecs:DeleteCluster',dev.replace('demo-dev','demo-prod')))
        self.assertTrue(permits(p,'ecs:CreateCluster',dev,{'aws:RequestTag/Environment':'dev','aws:RequestTag/Project':'demo'}))
        self.assertFalse(permits(p,'ecs:CreateCluster',dev,{'aws:RequestTag/Environment':'prod','aws:RequestTag/Project':'demo'}))
    def test_passrole_exact_roles_and_service(self):
        p=self.policy();role=f'arn:aws:iam::{ACCOUNT}:role/demo-dev-vpc-flow-logs-role'
        self.assertTrue(permits(p,'iam:PassRole',role,{'iam:PassedToService':'vpc-flow-logs.amazonaws.com'}))
        for bad in ('ecs-tasks.amazonaws.com','ec2.amazonaws.com'):self.assertFalse(permits(p,'iam:PassRole',role,{'iam:PassedToService':bad}))
        self.assertFalse(permits(p,'iam:PassRole',role.replace('dev','prod'),{'iam:PassedToService':'vpc-flow-logs.amazonaws.com'}))
    def test_security_and_delivery_admin_absent(self):
        for key in wp5.BINDINGS:
            p=self.policy(key)
            for action in ('iam:PutRolePolicy','iam:UpdateAssumeRolePolicy','iam:CreateRole','sts:AssumeRole','lambda:UpdateFunctionCode','codebuild:UpdateProject','s3:PutBucketPolicy','ecr:PutImage','secretsmanager:GetSecretValue','kms:Decrypt','ssm:SendCommand','ec2:CreateLaunchTemplateVersion','ecs:ExecuteCommand','ecs:RunTask'):
                self.assertFalse(permits(p,action,'*'),(key,action))
    def test_state_and_lock_exact_no_state_delete(self):
        p=self.policy();base=f'arn:aws:s3:::e1-lifecycle-dev-{ACCOUNT}-{REGION}/e1/lifecycle/dev/platform/terraform.tfstate'
        self.assertTrue(permits(p,'s3:PutObject',base));self.assertTrue(permits(p,'s3:DeleteObject',base+'.tflock'))
        self.assertFalse(permits(p,'s3:DeleteObject',base));self.assertFalse(permits(p,'s3:PutObject',base.replace('/platform/','/apps/')))
        self.assertFalse(permits(p,'s3:PutObject',base.replace('dev','prod')))
    def test_protected_config_read_only(self):
        p=self.policy();arn=f'arn:aws:s3:::demo-release-artifacts-{ACCOUNT}/lifecycle/{self.key}/current.json'
        self.assertTrue(permits(p,'s3:GetObject',arn));self.assertFalse(permits(p,'s3:PutObject',arn))
        self.assertFalse(permits(p,'s3:GetObject',arn.replace('infra-dev','infra-prod')))
    def test_gateway_only_exact_start_no_skeleton_mutation(self):
        p=self.policy('request-gateway/infra-dev');arn=f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-infra-dev'
        self.assertTrue(permits(p,'codebuild:StartBuild',arn));self.assertFalse(permits(p,'codebuild:StartBuild',arn.replace('dev','prod')))
        self.assertFalse(permits(p,'ecs:DeleteCluster',self.resources['aws_ecs_cluster'][0]))
    def test_request_store_only_gateway_conditional(self):
        arn=f'arn:aws:s3:::e1-lifecycle-dev-{ACCOUNT}-{REGION}/requests/infra-dev/{UUID}/request.json'
        self.assertTrue(permits(self.policy('request-gateway/infra-dev'),'s3:PutObject',arn,{'s3:if-none-match':'*'}))
        self.assertFalse(permits(self.policy('request-gateway/infra-dev'),'s3:PutObject',arn))
        self.assertFalse(permits(self.policy(),'s3:PutObject',arn,{'s3:if-none-match':'*'}))
    def test_sql_launch_multiresource_tuple_and_ordinary_denial(self):
        key='environment-lifecycle/infra-high-risk-dev';resources=copy.deepcopy(self.resources)
        resources['aws_instance']=[f'arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-12345678'];resources['_sql_launch']=self.b[key]['sql_launch']
        p=self.policy(key,resources);sql=resources['_sql_launch']
        for field in ('image','subnet','security_group'):self.assertTrue(permits(p,'ec2:RunInstances',sql[field]))
        context={'aws:RequestTag/Environment':'dev','aws:RequestTag/Project':'demo','ec2:InstanceType':'t3a.small','ec2:MetadataHttpTokens':'required',
                 'ec2:InstanceProfile':f'arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile'}
        self.assertTrue(permits(p,'ec2:RunInstances',resources['aws_instance'][0],context))
        self.assertFalse(permits(p,'ec2:RunInstances',resources['aws_instance'][0],{**context,'ec2:InstanceProfile':f'arn:aws:iam::{ACCOUNT}:instance-profile/unrelated'}))
        self.assertTrue(permits(p,'ec2:RunInstances',f'arn:aws:ec2:{REGION}:{ACCOUNT}:volume/vol-12345678',{'ec2:Encrypted':'true'}))
        self.assertTrue(permits(p,'ec2:RunInstances',f'arn:aws:ec2:{REGION}:{ACCOUNT}:network-interface/eni-12345678',{'ec2:Subnet':sql['subnet'],'ec2:AssociatePublicIpAddress':'false'}))
        self.assertFalse(permits(self.policy(resources=resources),'ec2:RunInstances',resources['aws_instance'][0],context))
    def test_resource_input_cross_account_environment_rejected(self):
        for bad in ('arn:aws:ecs:us-east-1:999999999999:cluster/demo-dev-platform-main-cluster',f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-prod-platform-main-cluster'):
            resources=copy.deepcopy(self.resources);resources['aws_ecs_cluster']=[bad]
            self.assertFalse(iam.valid_resources(resources,ACCOUNT,REGION,'dev'))
    def test_package_get_exact_version_condition(self):
        p=self.policy();arn=f'arn:aws:s3:::e1-control-bundles-{ACCOUNT}-{REGION}/bundles/sha256/'+('a'*64)+'.json'
        self.assertTrue(permits(p,'s3:GetObjectVersion',arn,{'s3:VersionId':'SYNTHETIC_VERSION'}))
        self.assertFalse(permits(p,'s3:GetObjectVersion',arn,{'s3:VersionId':'latest'}));self.assertFalse(permits(p,'s3:PutObject',arn))
    def test_create_parent_dependencies_and_tag_mutation_denial(self):
        p=self.policy();vpc=f'arn:aws:ec2:{REGION}:{ACCOUNT}:vpc/vpc-12345678'
        facts={'aws:ResourceTag/Environment':'dev','aws:ResourceTag/Project':'demo'}
        self.assertTrue(permits(p,'ec2:CreateSubnet',vpc,facts));self.assertFalse(permits(p,'ec2:CreateSubnet',vpc,{**facts,'aws:ResourceTag/Environment':'prod'}))
        subnet=f'arn:aws:ec2:{REGION}:{ACCOUNT}:subnet/subnet-12345678'
        create={'aws:RequestTag/Environment':'dev','aws:RequestTag/Project':'demo'}
        self.assertTrue(permits(p,'ec2:CreateSubnet',subnet,create))
        self.assertTrue(permits(p,'ec2:CreateTags',subnet,{**create,'ec2:CreateAction':'CreateSubnet'}))
        self.assertFalse(permits(p,'ec2:CreateTags',subnet,create))
    def test_high_risk_sql_binding_prerequisite_denies(self):
        b=copy.deepcopy(self.b)
        for value in b.values():value['sql_launch']['security_group']=value['sql_launch']['security_group'].replace(ACCOUNT,'999999999999')
        active=wp5.creation_supported(DOC,self.i,self.r,b,ACCOUNT,REGION)
        self.assertEqual(len(active),4);self.assertFalse(any('high-risk' in key for key in active))
