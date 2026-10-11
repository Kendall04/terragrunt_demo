"""Synthetic records prove repository semantics, never GitHub/AWS installation."""
import ast
import copy
import json
import base64
import io
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import wp6
import model
from test_wp4d import permits
from scripts.workflow_requests import contract as c, client, render

ROOT=Path(__file__).resolve().parents[3]
DOC=json.loads((ROOT/model.AUTHORITY).read_text())
ACCOUNT='123456789012';REGION='us-east-1';COMMIT='b'*40
OP='11111111-1111-4111-8111-111111111111'

def projection(key):
    env=c.environment(key)
    record=dict(identity=key,environment=env,account=ACCOUNT,region=REGION,workflow_commit=COMMIT,
        active=True,governance='ADMIN_VERIFIED_G1_G9',gateway_version='7',plan_binding=None,
        source_sha256=DOC['wp6']['source_sha256'],endpoint_readback=f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-gateway-{key}:7')
    if key.startswith('plan-'):
        cluster=f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-{env}-platform-main-cluster'
        record.update(gateway_version=None,endpoint_readback='ADMIN_VERIFIED_PLAN_READ_ONLY',plan_binding=dict(source_commit=COMMIT,
            readback='ADMIN_VERIFIED_NONSECRET_STATE_AND_EXACT_BINDINGS',layers={layer:dict(root=f'terraform/modules/target/{env}/{layer}',
                backend=dict(bucket=f'e1-lifecycle-{env}-{ACCOUNT}-{REGION}',region=REGION,key=f'e1/lifecycle/{env}/{layer}/terraform.tfstate'),
                variables=dict(account_id=ACCOUNT,region=REGION)) for layer in ('shared','secrets','global','data','platform','apps','edge')},
            resources=dict(cluster=cluster,services=[f'arn:aws:ecs:{REGION}:{ACCOUNT}:service/{cluster.split("/")[-1]}/demo-{env}-app-api-{color}-svc' for color in ('blue','green')],
                roles=[f'arn:aws:iam::{ACCOUNT}:role/demo-{env}-app-api-{color}-{role}-role' for color in ('blue','green') for role in ('task','exec')],
                cleanup_function=f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-cleanup-recovery-cleanup-{env}:7',
                listener=f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:listener/app/demo-{env}-internal-alb/abc/def',
                rule=f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:listener-rule/app/demo-{env}-internal-alb/abc/def/ghi',
                targets=[f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:targetgroup/demo-{env}-{color}/abc123' for color in ('blue','green')],
                skeleton={kind:[] for kind in c.PLAN_READS})))
    return record

def config(key):return {k:v for k,v in projection(key).items() if k not in ('source_sha256','endpoint_readback')}

def claims(key):
    return dict(aud=c.AUDIENCE,sub=c.subject(key,COMMIT),repository=c.REPOSITORY,ref=c.source_ref(key),
        event_name='workflow_dispatch',job_workflow_ref=c.workflow(key)+'@'+COMMIT,sha='a'*40)

def request(key):
    if key=='release':return {'source_commit':'a'*40}
    if key.startswith('plan-'):return {'operation':'plan','layer':'global'}
    if key.startswith('infra-'):return {'operation_id':OP,'operation':'reconcile','layer':'data' if 'high-risk' in key else 'global','revision':'a'*64,'parameters':{}}
    if key.startswith('emergency-'):return {}
    return {'action':'deliver','release_id':'sha256-'+'a'*64,'replicas':1}

class FakeAWS:
    def __init__(self,key,state='SUCCESS'):self.key=key;self.state=state;self.invocations=[]
    def invoke(self,value):self.invocations.append(value);return value.get('operation_id',OP)
    def status(self,op):return dict(operation_id=op,state=self.state,release_id='sha256-'+'a'*64 if self.key=='release' else None,source_commit='a'*40 if self.key=='release' else None)
    def plan(self,layer):return {'state':'PLANNED'}
    def preflight(self):return {'state':'SUCCESS'}

class Workflows(unittest.TestCase):
    def reject(self,fn,*args):
        with self.assertRaises((ValueError,KeyError,TypeError,RuntimeError)):fn(*args)
    def test_registry_eleven_reserved_inactive(self):
        self.assertEqual(set(DOC['wp6']['selected']),set(c.IDENTITIES));self.assertEqual(DOC['wp6']['approvals'],{})
        self.assertTrue(all(v['stage']=='INERT' and v['oidc_expectation']['commit'] is None for v in DOC['request_identities'].values()))
    def test_wp4d_wp5_remain_uninstalled(self):
        self.assertEqual(len(DOC['wp4d']['selected']),16);self.assertEqual(len(DOC['wp5']['selected']),8)
        for key in ('wp4d','wp5','internal_release'):
            self.assertEqual(DOC[key]['installations'],{});self.assertEqual(DOC[key]['runtime_approvals'],{})
    def test_source_identity_admission(self):wp6.validate(ROOT,DOC)
    def test_source_identity_drift_rejected(self):
        bad=copy.deepcopy(DOC);bad['wp6']['source_sha256']['scripts/workflow_requests/client.py']='f'*64
        self.reject(wp6.validate,ROOT,bad)
    def test_config_missing_before_token(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('token must not be acquired')):
            self.reject(client.configuration,'deploy-dev','{}')
    def test_immutable_subject_has_no_default_fallback(self):
        s=c.subject('deploy-dev',COMMIT);self.assertEqual(s,'repo:'+c.REPOSITORY+':environment:e1-dev-deploy:job_workflow_ref:'+c.workflow('deploy-dev')+'@'+COMMIT)
        for sha in ('main','develop','0'*40,'${SHA}','b'*39):self.reject(c.subject,'deploy-dev',sha)
    def test_role_templates_have_no_security_admin_or_role_chaining(self):
        for key in c.IDENTITIES:
            p=wp6.policy(key,projection(key),ACCOUNT,REGION)
            actions={a for s in p['Statement'] for a in s['Action']}
            self.assertFalse(actions & {'iam:PassRole','sts:AssumeRole','codebuild:StartBuild','lambda:UpdateFunctionCode','iam:CreateRole','s3:PutObject','secretsmanager:GetSecretValue','kms:Decrypt'})
            self.assertFalse(any('*' in a for a in actions))
    def test_gateway_region_and_exact_version(self):
        for key in c.IDENTITIES:
            if key.startswith('plan-'):continue
            p=wp6.policy(key,projection(key),ACCOUNT,REGION);arn=projection(key)['endpoint_readback']
            self.assertTrue(permits(p,'lambda:InvokeFunction',arn,{'aws:RequestedRegion':REGION}))
            for bad in (arn.rsplit(':',1)[0],arn.rsplit(':',1)[0]+':8',arn.replace('e1-gateway-','e1-controller-')):
                self.assertFalse(permits(p,'lambda:InvokeFunction',bad,{'aws:RequestedRegion':REGION}))
            self.assertFalse(permits(p,'lambda:InvokeFunction',arn,{'aws:RequestedRegion':'eu-west-1'}))
    def test_no_direct_controller_finalizer_cleanup_nat_invocation(self):
        p=wp6.policy('deploy-dev',projection('deploy-dev'),ACCOUNT,REGION)
        for name in ('e1-controller-deploy-dev','e1-qualification-finalizer','e1-cleanup-recovery-cleanup-dev','e1-nat-nat-dev-assign_eip'):
            self.assertFalse(permits(p,'lambda:InvokeFunction',f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:{name}:7',{'aws:RequestedRegion':REGION}))
    def test_public_evidence_only(self):
        for key in c.IDENTITIES:
            if key.startswith('plan-'):continue
            p=wp6.policy(key,projection(key),ACCOUNT,REGION);bucket,path=c.status_location(key,ACCOUNT,REGION,OP);arn='arn:aws:s3:::'+bucket+'/'+path
            self.assertTrue(permits(p,'s3:GetObject',arn))
            for name in ('intent','completed','receipt','candidate','outcome'):
                self.assertFalse(permits(p,'s3:GetObject',arn.replace('public.json',name+'.json')))
            self.assertFalse(permits(p,'s3:PutObject',arn));self.assertFalse(permits(p,'s3:GetObjectVersion',arn))
    def test_plan_own_state_read_never_security_state(self):
        for env in ('dev','prod'):
            p=wp6.policy('plan-'+env,projection('plan-'+env),ACCOUNT,REGION)
            arn=f'arn:aws:s3:::e1-lifecycle-{env}-{ACCOUNT}-{REGION}/e1/lifecycle/{env}/apps/terraform.tfstate'
            self.assertTrue(permits(p,'s3:GetObject',arn));self.assertFalse(permits(p,'s3:PutObject',arn))
            self.assertFalse(permits(p,'s3:GetObject',arn.replace(env,'prod' if env=='dev' else 'dev')))
            self.assertFalse(permits(p,'s3:GetObject','arn:aws:s3:::security-state/e1/security/terraform.tfstate'))
            self.assertFalse(permits(p,'lambda:InvokeFunction',projection('deploy-dev')['endpoint_readback'],{'aws:RequestedRegion':REGION}))
    def test_read_only_region_wide_metadata_limitation(self):
        p=wp6.policy('plan-dev',projection('plan-dev'),ACCOUNT,REGION)
        self.assertTrue(permits(p,'ec2:DescribeVpcs','*',{'aws:RequestedRegion':REGION}))
        self.assertFalse(permits(p,'ec2:DescribeVpcs','*',{'aws:RequestedRegion':'eu-west-1'}))
        self.assertFalse(permits(p,'ec2:CreateVpc','*',{'aws:RequestedRegion':REGION}))
    def test_plan_service_and_role_metadata_exact(self):
        p=wp6.policy('plan-dev',projection('plan-dev'),ACCOUNT,REGION);r=projection('plan-dev')['plan_binding']['resources']
        self.assertTrue(permits(p,'ecs:DescribeServices',r['services'][0]));self.assertFalse(permits(p,'ecs:DescribeServices',r['services'][0].replace('demo-dev','demo-prod')))
        self.assertTrue(permits(p,'iam:GetRole',r['roles'][0]));self.assertFalse(permits(p,'iam:GetRole',f'arn:aws:iam::{ACCOUNT}:role/e1-controller-deploy-dev-exec'))
    def test_production_is_independent(self):
        dev=wp6.policy('deploy-dev',projection('deploy-dev'),ACCOUNT,REGION);prod=projection('promote-prod')['endpoint_readback']
        self.assertFalse(permits(dev,'lambda:InvokeFunction',prod,{'aws:RequestedRegion':REGION}))
        self.reject(c.context,'promote-prod',claims('deploy-dev'),config('promote-prod'))
        self.reject(c.request,'promote-prod',json.dumps(request('promote-prod')|{'allow_no_dev_record':True}))
    def test_unknown_parameters_duplicate_keys_and_oversize_rejected(self):
        for key in c.IDENTITIES:
            for field in ('role','environment','principal','approved','mode','source','image','service','task_definition','routing','account','gateway','buildspecOverride'):
                self.reject(c.request,key,json.dumps(request(key)|{field:'attacker'}))
        self.reject(c.request,'release','{"source_commit":"'+('a'*40)+'","source_commit":"'+('b'*40)+'"}')
        self.reject(c.request,'emergency-dev',' '*4097);self.reject(c.decode,'NaN')
    def test_normal_requires_qualified_id_and_bounded_replicas(self):
        for release in ('main','sha256:deadbeef','docker:latest',None):self.reject(c.request,'deploy-dev',json.dumps(request('deploy-dev')|{'release_id':release}))
        for count in (0,101,True,'1',1.5):self.reject(c.request,'deploy-dev',json.dumps(request('deploy-dev')|{'replicas':count}))
    def test_rollback_uses_only_protected_history_selector(self):
        value=c.request('deploy-dev',json.dumps(dict(action='rollback-release',history=OP,replicas=1)),OP)
        self.assertEqual(json.loads(value['body'])['history'],OP)
        self.reject(c.request,'deploy-dev',json.dumps(dict(action='rollback-release',history='s3://attacker/data',replicas=1)))
    def test_emergency_has_no_content_selector(self):
        for key in ('emergency-dev','emergency-prod'):
            self.assertEqual(json.loads(c.request(key,'{}',OP)['body']),{})
            for field in ('release_id','color','replicas','task_definition'):self.reject(c.request,key,json.dumps({field:'blue'}))
    def test_lifecycle_approval_id_preserved(self):
        value=request('infra-high-risk-dev');self.assertEqual(c.request('infra-high-risk-dev',json.dumps(value))['operation_id'],OP)
        for layer in ('shared','global','edge'):self.reject(c.request,'infra-high-risk-dev',json.dumps(value|{'layer':layer}))
        self.reject(c.request,'infra-dev',json.dumps(request('infra-dev')|{'layer':'data'}))
        self.reject(c.request,'infra-dev',json.dumps(request('infra-dev')|{'operation':'teardown'}))
    def test_full_teardown_retains_wp5_approved_path(self):
        for env in ('dev','prod'):
            key='infra-high-risk-'+env
            self.assertEqual(c.request(key,json.dumps(request(key)|{'operation':'teardown','layer':'edge'}))['operation'],'teardown')
    def test_sanitized_success_required_not_build_ack(self):
        for state in ('FAILURE','UNKNOWN','UNCERTAIN','BUILD_SUCCEEDED','STARTED'):
            self.reject(client.execute,'deploy-dev',json.dumps(request('deploy-dev')),config('deploy-dev'),claims('deploy-dev'),FakeAWS('deploy-dev',state))
    def test_release_requires_finalizer_and_exact_source(self):
        bad=FakeAWS('release');bad.status=lambda op:dict(operation_id=op,state='SUCCESS',release_id='sha256-'+'a'*64,source_commit='f'*40)
        self.reject(client.execute,'release',json.dumps(request('release')),config('release'),claims('release'),bad)
        self.reject(client.execute,'release',json.dumps({'source_commit':'f'*40}),config('release'),claims('release'),FakeAWS('release'))
    def test_result_cannot_replace_operation_or_return_secret_fields(self):
        value=FakeAWS('deploy-dev').status(OP)
        for bad in (dict(value,operation_id='00000000-0000-4000-8000-000000000000'),dict(value,credentials='secret'),dict(value,release_id='attacker')):
            self.reject(c.result,'deploy-dev',OP,bad)
    def test_timeout_is_not_success_and_does_not_retry(self):
        aws=FakeAWS('deploy-dev')
        self.reject(lambda:client.execute('deploy-dev',json.dumps(request('deploy-dev')),config('deploy-dev'),claims('deploy-dev'),aws,deadline=0))
        self.assertEqual(len(aws.invocations),1)
    def test_workflows_and_pins_are_deterministic(self):
        first=render.render(ROOT,{})
        self.assertEqual(first,render.render(ROOT,{}))
        for name,text in first.items():self.assertEqual((ROOT/name).read_text(),text)
        positive=render.call('deploy-dev','{}',{'deploy-dev':projection('deploy-dev')})
        self.assertEqual(positive['uses'],c.workflow('deploy-dev')+'@'+COMMIT)
        self.assertNotIn('secrets',positive)
    def test_entry_hardcodes_environment_identity_and_code_source(self):
        for key in c.IDENTITIES:
            w=render.entry(key);job=w['jobs']['request']
            self.assertEqual(job['environment'],c.CONTEXTS[key]);self.assertEqual(job['env']['E1_IDENTITY'],key)
            self.assertEqual(set(w['on']['workflow_call']['inputs']),{'request'})
            self.assertEqual(job['steps'][1]['with']['ref'],'${{ steps.installation.outputs.commit }}')
            self.assertFalse(job['steps'][1]['with']['persist-credentials'])
            self.assertTrue(job['steps'][-1]['run'].endswith(' '+key))
    def test_inline_python_and_yaml_json_parse(self):
        for text in render.render(ROOT,{}).values():
            doc=json.loads(text)
            for job in doc['jobs'].values():
                for step in job.get('steps',[]):
                    run=step.get('run','')
                    if "<<'PY'\n" in run:ast.parse(run.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0])
    def test_no_legacy_workflow_credential_or_mutation_overlap(self):
        for path in (ROOT/'.github/workflows').glob('*.yml'):
            text=path.read_text()
            self.assertNotIn('AWS_ROLE_',text);self.assertNotIn('./.github/actions/aws-oidc',text)
            for mutation in ('aws ecs update-service','aws ecs register-task-definition','aws elbv2 modify','terragrunt apply','aws ecr get-login-password'):
                self.assertNotIn(mutation,text)
        self.assertNotIn('id-token: write',(ROOT/'.github/workflows/ci.yml').read_text())
    def test_legacy_terraform_is_explicit_wp7_debt(self):self.assertEqual(DOC['wp6']['legacy_retirement'],'WP7')
    def test_bootstrap_missing_governance_denies_before_oidc(self):
        run=render.entry('deploy-dev')['jobs']['request']['steps'][0]['run']
        code=run.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        for value in ({},config('deploy-dev')|{'active':False},config('deploy-dev')|{'governance':'UNVERIFIED'}):
            with patch.dict(os.environ,{'E1_REQUEST_CONFIGURATION':json.dumps(value)},clear=True),patch('urllib.request.urlopen') as http:
                with self.assertRaises(SystemExit):exec(compile(code,'protected-entry','exec'),{})
                http.assert_not_called()
    def test_bootstrap_token_binds_checkout_before_credentials(self):
        run=render.entry('deploy-dev')['jobs']['request']['steps'][0]['run'];code=run.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'output'
            env=dict(E1_REQUEST_CONFIGURATION=json.dumps(config('deploy-dev')),GITHUB_REPOSITORY=c.REPOSITORY,
                GITHUB_REF=c.source_ref('deploy-dev'),GITHUB_EVENT_NAME='workflow_dispatch',ACTIONS_ID_TOKEN_REQUEST_URL='https://fixture.invalid/token',
                ACTIONS_ID_TOKEN_REQUEST_TOKEN='OFFLINE_FIXTURE_NOT_A_TOKEN',GITHUB_OUTPUT=str(path))
            for changed in (False,True):
                issued=claims('deploy-dev')
                if changed:issued['job_workflow_ref']=c.workflow('deploy-dev')+'@'+'f'*40
                encoded=base64.urlsafe_b64encode(c.canonical(issued)).decode().rstrip('=')
                response=io.BytesIO(json.dumps({'value':'offline.'+encoded+'.offline'}).encode())
                with patch.dict(os.environ,env,clear=True),patch('urllib.request.urlopen',return_value=response):
                    if changed:
                        with self.assertRaises(SystemExit):exec(compile(code,'protected-entry','exec'),{})
                    else:exec(compile(code,'protected-entry','exec'),{})
            self.assertEqual(path.read_text(),'commit='+COMMIT+'\n')
    def test_pr_target_also_rejected_before_credential_use(self):
        for key in c.IDENTITIES:self.reject(c.context,key,claims(key)|{'event_name':'pull_request_target'},config(key))
    def test_plan_binding_substitution_rejected(self):
        for env in ('dev','prod'):
            key='plan-'+env
            for field in ('cluster','services','roles','listener','rule','targets','cleanup_function'):
                value=config(key);p=value['plan_binding']['resources']
                p[field]=[v.replace('demo-'+env,'demo-other') for v in p[field]] if isinstance(p[field],list) else p[field].replace('demo-'+env,'demo-other').replace('cleanup-'+env,'cleanup-other')
                self.reject(client.configuration,key,json.dumps(value))
            value=config(key);value['plan_binding']['layers']['shared']['variables']['secret_value']='forbidden'
            self.reject(client.configuration,key,json.dumps(value))
    def test_plan_metadata_does_not_download_function_code(self):
        p=wp6.policy('plan-dev',projection('plan-dev'),ACCOUNT,REGION);arn=projection('plan-dev')['plan_binding']['resources']['cleanup_function']
        self.assertTrue(permits(p,'lambda:GetFunctionConfiguration',arn));self.assertFalse(permits(p,'lambda:GetFunction',arn))
    def test_high_risk_selectors_keep_branch_and_environment_grouped(self):
        for key,job in render.callers({k:projection(k) for k in c.IDENTITIES})['cd-terragrunt.yml']['jobs'].items():
            self.assertIn("github.ref == '"+c.source_ref(key)+"' && (",job['if'])
            self.assertIn("inputs.environment == '"+c.environment(key)+"'",job['if'])
    def test_admin_approval_requires_authenticated_complete_observation(self):
        observation=dict(record=projection('deploy-dev'),governance_verifications={'G'+str(i):'VERIFIED' for i in range(1,10)},complete=True)
        class Admin(wp6.RequestAdminChannel):
            def observe(self,identity):return observation
        self.reject(wp6.approve,ROOT,DOC,'deploy-dev',observation)
        self.assertEqual(wp6.approve(ROOT,DOC,'deploy-dev',Admin()),projection('deploy-dev'))
        observation['complete']=False;self.reject(wp6.approve,ROOT,DOC,'deploy-dev',Admin())
    def test_configured_flags_do_not_prove_external_governance(self):
        observation=dict(record=projection('deploy-dev'),governance_verifications={'G'+str(i):'VERIFIED' for i in range(1,10)},complete=True)
        class Admin(wp6.RequestAdminChannel):
            def observe(self,identity):return observation
        for gate in observation['governance_verifications']:
            observation['governance_verifications'][gate]='UNVERIFIED'
            self.reject(wp6.approve,ROOT,DOC,'deploy-dev',Admin())
            observation['governance_verifications'][gate]='VERIFIED'
        observation['record']['source_sha256']={}
        self.reject(wp6.approve,ROOT,DOC,'deploy-dev',Admin())

    def test_cd_preserves_safe_then_high_risk_order(self):
        jobs=render.callers({k:projection(k) for k in c.IDENTITIES})['cd.yml']['jobs']
        for env in ('dev','prod'):
            order=[env+'-'+layer for layer in ('shared','secrets','global','platform','edge','data','apps')]
            for index,name in enumerate(order):self.assertTrue(set(order[:index])<=set(jobs[name]['needs']))
    def test_oversized_exact_inventory_keeps_plan_identity_inactive(self):
        value=projection('plan-dev')
        value['plan_binding']['resources']['skeleton']['aws_sns_topic']=[f'arn:aws:sns:{REGION}:{ACCOUNT}:demo-dev-'+('a'*100)+str(i) for i in range(100)]
        self.assertTrue(c.valid_plan_resources(value['plan_binding']['resources'],'dev',ACCOUNT,REGION))
        self.assertFalse(wp6.ready('plan-dev',value,ACCOUNT,REGION,None,DOC['wp6']['source_sha256']))

def add_cases():
    # Each responsibility's positive acquisition, operation and inactive gate is
    # counted independently, making all eleven trust/capability pairings visible.
    for key in c.IDENTITIES:
        def positive(self,key=key):
            self.assertEqual(c.context(key,claims(key),config(key))['identity'],key)
            p=projection(key);self.assertTrue(wp6.ready(key,p,ACCOUNT,REGION,None if key.startswith('plan-') else p['endpoint_readback'],DOC['wp6']['source_sha256']))
            result=client.execute(key,json.dumps(request(key)),config(key),claims(key),FakeAWS(key))
            self.assertIn(result['state'],('SUCCESS','PLANNED'))
            trust=wp6.trust(key,p,ACCOUNT)['Statement'][0]
            self.assertEqual(trust['Principal'],{'Federated':f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com'})
            self.assertEqual(trust['Condition']['StringEquals']['token.actions.githubusercontent.com:sub'],c.subject(key,COMMIT))
        def negative(self,key=key):
            for field,value in [('aud','attacker'),('sub','repo:'+c.REPOSITORY+':environment:'+c.CONTEXTS[key]),('repository','fork/terragrunt_demo'),('ref','refs/heads/untrusted'),('event_name','pull_request'),('job_workflow_ref',c.workflow(key)+'@main')]:
                self.reject(c.context,key,claims(key)|{field:value},config(key))
            for field,value in [('active',False),('governance','UNVERIFIED'),('workflow_commit','main'),('source_sha256',{}),('account','999999999999'),('environment','attacker')]:
                p=projection(key);p[field]=value
                self.assertFalse(wp6.ready(key,p,ACCOUNT,REGION,None if key.startswith('plan-') else projection(key)['endpoint_readback'],DOC['wp6']['source_sha256']))
        setattr(Workflows,'test_positive_'+key.replace('-','_'),positive)
        setattr(Workflows,'test_negative_'+key.replace('-','_'),negative)
add_cases()
