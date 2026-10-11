"""WP6 extends the existing eleven inert reservations, never compute trust."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.workflow_requests import contract as c
import wp5_iam

SOURCES=('ci/authority/governance.json','scripts/workflow_requests/contract.py','scripts/workflow_requests/client.py','scripts/workflow_requests/render.py',
    '.github/workflows/cd-scope.yml','scripts/lifecycle/contract.py','scripts/wp4d/gateway.py',
    'scripts/normal_delivery/delivery.py','scripts/normal_delivery/authorization.py')+tuple(
    '.github/workflows/'+c.CONTEXTS[k]+'.yml' for k in c.IDENTITIES)

def contract(root,doc):
    return {'schema':'E1_WP6_PROTECTED_REQUESTS_V1','owner':'SECURITY_ROOT_OWNED',
        'repository':c.REPOSITORY,'audience':c.AUDIENCE,
        'selected':{k:{'name':doc['request_identities'][k]['name'],'environment':c.environment(k),
            'context':c.CONTEXTS[k],'workflow':c.workflow(k),'ref':c.source_ref(k),
            'kind':'PLAN_READ_ONLY' if k.startswith('plan-') else 'GATEWAY_REQUEST',
            'gateway':None if k.startswith('plan-') else doc['controller_compute']['nodes']['request-gateway/'+k]['name'],
            'human_approval':k=='promote-prod' or 'high-risk' in k or k.startswith('emergency-')}
            for k in c.IDENTITIES},
        'source_sha256':{p:hashlib.sha256((Path(root)/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in SOURCES},
        'approvals':{},'live':'UNVERIFIED_NOT_DEPLOYED','legacy_retirement':'WP7'}

def validate(root,doc):
    expected=contract(root,doc)
    records=doc['wp6'].get('approvals')
    c.require(type(records) is dict and set(records)<=set(c.IDENTITIES))
    expected['approvals']=records
    if doc['wp6']!=expected:raise ValueError('WP6_SOURCE_ADMISSION_FAILURE')
    for key,v in records.items():
        c.require(ready(key,v,v['account'],v['region'],None if key.startswith('plan-') else v['endpoint_readback'],expected['source_sha256']))

valid_plan_resources=c.valid_plan_resources

def ready(key,record,account,region,endpoint,source):
    try:
        c.closed(record,('identity','environment','account','region','workflow_commit','active','governance','gateway_version','plan_binding','source_sha256','endpoint_readback'))
        c.require(record['source_sha256']==source and record['identity']==key and record['environment']==c.environment(key))
        c.subject(key,record['workflow_commit']);c.require(record['active'] is True and record['governance']=='ADMIN_VERIFIED_G1_G9')
        c.require(record['account']==account and record['region']==region)
        if key.startswith('plan-'):
            c.validate_plan_binding(key,record)
            c.require(endpoint is None and record['gateway_version'] is None and record['endpoint_readback']=='ADMIN_VERIFIED_PLAN_READ_ONLY')
        else:
            c.require(record['plan_binding'] is None and record['endpoint_readback']==endpoint and endpoint is not None)
            c.require(endpoint==f'arn:aws:lambda:{region}:{account}:function:e1-gateway-{key}:{record["gateway_version"]}')
            c.match('[1-9][0-9]*',record['gateway_version'])
        c.require(len(c.canonical(policy(key,record,account,region)))<=10240)
        return True
    except Exception:return False

class RequestAdminChannel:
    """Separately authenticated operator port, never a workflow transport.

    observe reads the immutable Git commit's actual source bytes, current GitHub
    governance and installed qualified endpoint. There is no live implementation
    or default observation here; provider-free doubles are only synthetic tests.
    """
    def observe(self,identity):raise NotImplementedError

def approve(root,doc,identity,admin):
    c.require(isinstance(admin,RequestAdminChannel) and identity in c.IDENTITIES)
    observed=admin.observe(identity)
    c.closed(observed,('record','governance_verifications','complete'))
    c.require(observed['complete'] is True)
    facts=observed['governance_verifications']
    c.closed(facts,tuple('G'+str(i) for i in range(1,10)))
    c.require(all(value=='VERIFIED' for value in facts.values()))
    value=observed['record']
    # The port supplies genuine source/endpoint readbacks. Approval does not
    # install compute, create evidence, write GitHub settings or update Terraform.
    c.require(ready(identity,value,value['account'],value['region'],None if identity.startswith('plan-') else value['endpoint_readback'],contract(root,doc)['source_sha256']))
    return json.loads(json.dumps(value))

def trust(key,record,account):
    return {'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{
        'Federated':f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'},
        'Action':'sts:AssumeRoleWithWebIdentity','Condition':{'StringEquals':{
            'token.actions.githubusercontent.com:aud':c.AUDIENCE,
            'token.actions.githubusercontent.com:sub':c.subject(key,record['workflow_commit'])}}}]}

def policy(key,record,account,region):
    statements=[]
    def allow(actions,resources,condition=None):
        if not resources:return
        value={'Effect':'Allow','Action':list(actions),'Resource':resources}
        if condition:value['Condition']=condition
        statements.append(value)
    env=c.environment(key)
    if not key.startswith('plan-'):
        allow(['lambda:InvokeFunction'],[f'arn:aws:lambda:{region}:{account}:function:e1-gateway-{key}:{record["gateway_version"]}'],
              {'StringEquals':{'aws:RequestedRegion':region}})
        bucket,path=c.status_location(key,account,region,'00000000-0000-0000-0000-000000000000')
        allow(['s3:GetObject'],['arn:aws:s3:::'+bucket+'/'+path.replace('00000000-0000-0000-0000-000000000000','*')])
    else:
        p=record['plan_binding']['resources'];regional={'StringEquals':{'aws:RequestedRegion':region}}
        for service,actions in wp5_iam.READS.items():allow([service+':'+a for a in actions],['*'],regional)
        allow(['ecs:DescribeClusters','ecs:ListTagsForResource'],[p['cluster']]);allow(['ecs:DescribeServices','ecs:ListTagsForResource'],p['services'])
        allow(['ecs:DescribeTaskDefinition'],['*'],regional)
        allow(['ecs:ListTagsForResource'],[f'arn:aws:ecs:{region}:{account}:task-definition/demo-{env}-app-api-{color}:*' for color in ('blue','green')])
        allow(['ec2:DescribeLaunchTemplates'],['*'],regional)
        allow(['iam:GetRole'],p['roles']);allow(['iam:GetRole'],[f'arn:aws:iam::{account}:role/demo-{env}-vpc-flow-logs-role'])
        allow(['iam:GetInstanceProfile'],[f'arn:aws:iam::{account}:instance-profile/demo-{env}-{name}' for name in ('data-sql-ec2-profile','nat-instance-profile')])
        allow(['lambda:GetFunctionConfiguration'],[p['cleanup_function']])
        for kind,(service,actions) in c.PLAN_READS.items():allow([service+':'+a for a in actions],p['skeleton'][kind])
        for layer in record['plan_binding']['layers'].values():
            b=layer['backend'];allow(['s3:GetObject'],['arn:aws:s3:::'+b['bucket']+'/'+b['key']])
        allow(['s3:ListBucket'],[f'arn:aws:s3:::e1-lifecycle-{env}-{account}-{region}'],{'StringEquals':{'s3:prefix':[f'e1/lifecycle/{env}/{name}/terraform.tfstate' for name in record['plan_binding']['layers']]}})
    return {'Version':'2012-10-17','Statement':statements}

def templates(doc):
    trusts={};policies={}
    for key in c.IDENTITIES:
        record={'workflow_commit':'a'*40,'gateway_version':'WP6_VERSION'}
        if key.startswith('plan-'):
            resources={name: 'WP6_'+name for name in ('cluster','cleanup_function')}
            resources.update(services=['WP6_services'],roles=['WP6_roles'],skeleton={kind:['WP6_'+kind] for kind in c.PLAN_READS})
            record['plan_binding']={'resources':resources,'layers':{layer:{'backend':{'bucket':'e1-lifecycle-'+c.environment(key)+'-WP6_ACCOUNT-WP6_REGION','key':'e1/lifecycle/'+c.environment(key)+'/'+layer+'/terraform.tfstate'}} for layer in ('shared','secrets','global','data','platform','apps','edge')}}
        trusts[key]=json.dumps(trust(key,record,'WP6_ACCOUNT'),separators=(',',':')).replace('a'*40,'WP6_COMMIT')
        policies[key]=json.dumps(policy(key,record,'WP6_ACCOUNT','WP6_REGION'),separators=(',',':'))
    return trusts,policies


def extend(root,child,compute,foundations,doc):
    ex=lambda s:'${'+s+'}'
    compute['output']['wp6_endpoints']={'value':ex('merge({for key,v in aws_lambda_function.wp3:key=>v.qualified_arn if startswith(key,"request-gateway/")},{for key,v in aws_lambda_function.wp4d:key=>v.qualified_arn if startswith(key,"request-gateway/")},{for key,v in aws_lambda_function.wp5:key=>v.qualified_arn if startswith(key,"request-gateway/")})')}
    root['module']['request_identities'].update(account_id=ex('var.aws_account_id'),region=ex('var.aws_region'),endpoints=ex('module.controller_compute.wp6_endpoints'))
    root['output']['wp6']={'value':ex('module.request_identities.wp6')}
    child['variable'].update(account_id={'type':'string'},region={'type':'string'},endpoints={'type':'map(string)'})
    local=child.setdefault('locals',{})
    local['wp6_records']=ex('var.authority.wp6.approvals')
    local['wp6_selected']=ex('var.authority.wp6.selected')
    # Match the administrator's exact Python-admitted record a second time. Only
    # selected, checked-in source records are usable; callers have no module port.
    local['wp6_admitted']={key:v for key,v in doc['wp6']['approvals'].items() if ready(key,v,v['account'],v['region'],None if key.startswith('plan-') else v['endpoint_readback'],doc['wp6']['source_sha256'])}
    conditions=['v==local.wp6_admitted[key]','v.identity==key','v.environment==local.wp6_selected[key].environment','v.account==var.account_id',
        'v.region==var.region','v.active==true','v.governance=="ADMIN_VERIFIED_G1_G9"',
        'can(regex("^[0-9a-f]{40}$",v.workflow_commit))','v.workflow_commit!="0000000000000000000000000000000000000000"',
        'v.source_sha256==var.authority.wp6.source_sha256','length(keys(v))==11']
    ordinary='v.plan_binding==null && can(regex("^[1-9][0-9]*$",v.gateway_version)) && v.endpoint_readback==try(var.endpoints["request-gateway/${key}"],null) && v.endpoint_readback=="arn:aws:lambda:${var.region}:${var.account_id}:function:${local.wp6_selected[key].gateway}:${v.gateway_version}"'
    plan='v.gateway_version==null && v.endpoint_readback=="ADMIN_VERIFIED_PLAN_READ_ONLY" && v.plan_binding.source_commit==v.workflow_commit && v.plan_binding.readback=="ADMIN_VERIFIED_NONSECRET_STATE_AND_EXACT_BINDINGS"'
    conditions.append('(startswith(key,"plan-") ? ('+plan+') : ('+ordinary+'))')
    local['wp6_active']=ex('{for key,v in local.wp6_records:key=>v if try(contains(keys(local.wp6_selected),key) && '+' && '.join(conditions)+',false)}')
    trusts,policies=templates(doc)
    local['wp6_trust_templates']=trusts;local['wp6_policy_templates']=policies
    trustexpr='local.wp6_trust_templates[key]'
    for token,value in [('WP6_ACCOUNT','var.account_id'),('WP6_COMMIT','v.workflow_commit')]:trustexpr='replace('+trustexpr+','+json.dumps(token)+','+value+')'
    local['wp6_trusts']=ex('{for key,v in local.wp6_active:key=>jsondecode('+trustexpr+')}')
    policyexpr='local.wp6_policy_templates[key]'
    for token,value in [('WP6_ACCOUNT','var.account_id'),('WP6_REGION','var.region'),('WP6_VERSION','coalesce(v.gateway_version,"INACTIVE")')]:policyexpr='replace('+policyexpr+','+json.dumps(token)+','+value+')'
    for field in ('cluster','cleanup_function'):
        policyexpr='replace('+policyexpr+','+json.dumps(json.dumps('WP6_'+field))+',jsonencode(try(v.plan_binding.resources.'+field+',"INACTIVE")))'
    for field in ('services','roles'):
        policyexpr='replace('+policyexpr+','+json.dumps(json.dumps(['WP6_'+field],separators=(',',':')))+',jsonencode(try(v.plan_binding.resources.'+field+',[])))'
    for kind in c.PLAN_READS:policyexpr='replace('+policyexpr+','+json.dumps(json.dumps(['WP6_'+kind],separators=(',',':')))+',jsonencode(try(v.plan_binding.resources.skeleton.'+kind+',[])))'
    local['wp6_policy_raw']=ex('{for key,v in local.wp6_active:key=>jsondecode('+policyexpr+')}')
    local['wp6_policies']=ex('{for key,v in local.wp6_policy_raw:key=>{Version=v.Version,Statement=[for s in v.Statement:s if length(s.Resource)>0]}}')
    child['resource']['aws_iam_role']['request']['assume_role_policy']=ex('contains(keys(local.wp6_active),each.key) ? jsonencode(local.wp6_trusts[each.key]) : jsonencode(var.authority.policies.inert_trust)')
    child['resource']['aws_iam_role']['request']['description']='Protected WP6 request reservation; inactive until exact approval/installation/governance gates.'
    child['resource']['aws_iam_role_policy']['inert']['for_each']=ex('{for key,v in var.authority.request_identities:key=>v if !contains(keys(local.wp6_active),key)}')
    child['resource']['aws_iam_role_policy']['wp6']={'for_each':ex('local.wp6_active'),'name':'wp6-request-only','role':ex('aws_iam_role.request[each.key].id'),'policy':ex('jsonencode(local.wp6_policies[each.key])'),'lifecycle':{'precondition':{'condition':ex('length(jsonencode(local.wp6_policies[each.key]))<=10240'),'error_message':'Exact read/request inventory exceeds the IAM inline ceiling; keep this identity inactive.'}}}
    child['output']['wp6']={'value':ex('{active=keys(local.wp6_active),reserved=keys(var.authority.request_identities),live="UNVERIFIED"}')}
    # IAM grants public reads only. Resource policies additionally forbid every
    # request principal's writes and internal object reads, including admin state.
    readers=compute['locals']['wp4d_bucket_readers']
    compute['locals']['wp4d_bucket_readers']=readers.replace('[var.admin_arn]', '[var.admin_arn,"arn:aws:iam::${var.account_id}:role/e1-request-${env == "dev" ? "deploy-dev" : "promote-prod"}","arn:aws:iam::${var.account_id}:role/e1-request-emergency-${env}"]')
    wp4=compute['resource']['aws_s3_bucket_policy']['wp4d']
    extra=',{Sid="ExternalOnlyPublic",Effect="Deny",Principal="*",Action=["s3:GetObject","s3:GetObjectVersion"],NotResource=["${aws_s3_bucket.wp4d[each.key].arn}/delivery/${each.key}/*/public.json","${aws_s3_bucket.wp4d[each.key].arn}/recovery/${each.key}/recovery/emergency/*/public.json"],Condition={ArnLike={"aws:PrincipalArn"="arn:aws:iam::${var.account_id}:role/e1-request-*"}}}'
    wp4['policy']=wp4['policy'].replace('}] })','}'+extra+'] })')
    state=foundations['resource']['aws_s3_bucket_policy']['state']
    state['policy']=state['policy'].replace('[var.admin_arn]', '[var.admin_arn,"arn:aws:iam::${var.account_id}:role/e1-request-plan-${each.key}","arn:aws:iam::${var.account_id}:role/e1-request-infra-${each.key}","arn:aws:iam::${var.account_id}:role/e1-request-infra-high-risk-${each.key}"]')
    extra=',{Sid="ExternalNoWrite",Effect="Deny",Principal="*",NotAction=["s3:GetObject","s3:ListBucket"],Resource=[each.value.arn,"${each.value.arn}/*"],Condition={ArnLike={"aws:PrincipalArn"="arn:aws:iam::${var.account_id}:role/e1-request-*"}}},{Sid="ExternalOnlyOwnPublic",Effect="Deny",Principal="*",Action="s3:GetObject",NotResource=["${each.value.arn}/operations/environment-lifecycle/infra-${each.key}/*/public.json","${each.value.arn}/operations/environment-lifecycle/infra-high-risk-${each.key}/*/public.json"],Condition={ArnEquals={"aws:PrincipalArn"=["arn:aws:iam::${var.account_id}:role/e1-request-infra-${each.key}","arn:aws:iam::${var.account_id}:role/e1-request-infra-high-risk-${each.key}"]}}},{Sid="PlanOnlyOwnState",Effect="Deny",Principal="*",Action="s3:GetObject",NotResource=[for layer in ["shared","secrets","global","data","platform","apps","edge"]:"${each.value.arn}/e1/lifecycle/${each.key}/${layer}/terraform.tfstate"],Condition={ArnEquals={"aws:PrincipalArn"="arn:aws:iam::${var.account_id}:role/e1-request-plan-${each.key}"}}}'
    state['policy']=state['policy'].replace('}]})','}'+extra+']})')
    evidence=json.loads(compute['resource']['aws_s3_bucket_policy']['evidence']['policy'])
    evidence['Statement']+= [
        {'Sid':'ExternalNoWrite','Effect':'Deny','Principal':'*','NotAction':['s3:GetObject'],'Resource':['arn:aws:s3:::${local.evidence_bucket}','arn:aws:s3:::${local.evidence_bucket}/*'],'Condition':{'ArnLike':{'aws:PrincipalArn':'arn:aws:iam::${var.account_id}:role/e1-request-*'}}},
        {'Sid':'ExternalOnlyPublic','Effect':'Deny','Principal':'*','Action':['s3:GetObject'],'NotResource':['arn:aws:s3:::${local.evidence_bucket}/qualifications/demo-api/operations/*/public.json'],'Condition':{'ArnLike':{'aws:PrincipalArn':'arn:aws:iam::${var.account_id}:role/e1-request-*'}}}]
    compute['resource']['aws_s3_bucket_policy']['evidence']['policy']=json.dumps(evidence)
    return child
