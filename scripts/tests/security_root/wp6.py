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

# Observed state serial 66 and the authenticated reconciliation plan. These are
# not recovered G1-G9 approvals. A separate new owner decision is mandatory.
PRESERVED_WP6 = {
    'release': {'workflow_commit':'f0ba8ad1d6528d362693c8de932f935c8084529d','gateway_version':'2','plan_binding':None},
    'deploy-dev': {'workflow_commit':'f0ba8ad1d6528d362693c8de932f935c8084529d','gateway_version':'3','plan_binding':None}}
PRESERVED_WP6_SHA256 = {
    'release':'c29297b10233a1b63a672cb71399709bc9adc6ee89287554bc95607add7137a4',
    'deploy-dev':'fc2bbc86193e79b16b0137af9408f9ae88445bdd9e418f5e4111071d2c1436ce'}

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

def dev_trial_approvals(doc):
    """Only the owner's two exact trial entries may leave repository inactivity.

    This validates source records; it is never live governance or installation
    evidence. approve() still requires the independently authenticated G1-G9 port.
    """
    records=doc['wp6']['approvals']
    c.require(type(records) is dict and set(records)<= {'release','deploy-dev'})
    for key,value in records.items():
        c.require(doc['wp6']['selected'][key]['ref']=='refs/heads/codex/final-github-actions-cicd')
        c.require(value['account']=='341936017254' and value['region']=='us-east-1')
        c.require(ready(key,value,'341936017254','us-east-1',value['endpoint_readback'],doc['wp6']['source_sha256']))
    return records


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
    root['variable']['wp6_preservation_approval_sha256']={'type':'string','default':None,'nullable':True,
        'validation':{'condition':ex('var.wp6_preservation_approval_sha256==null ? true : can(regex("^[0-9a-f]{64}$",var.wp6_preservation_approval_sha256))'),
        'error_message':'Separate new owner approval of the complete preservation document is required; a hex value alone is not approval.'}}
    root['locals']['wp6_preservation_records']=PRESERVED_WP6
    compute['output']['wp6_endpoints']={'value':ex('merge({for key,v in aws_lambda_function.wp3:key=>v.qualified_arn if startswith(key,"request-gateway/")},{for key,v in aws_lambda_function.wp4d:key=>v.qualified_arn if startswith(key,"request-gateway/")},{for key,v in aws_lambda_function.wp5:key=>v.qualified_arn if startswith(key,"request-gateway/")})')}
    # Request activation is a later installation stage. Read the exact already
    # installed numeric version independently, rather than depending on the
    # entire compute collection (which can include unrelated existing NAT).
    root.setdefault('data',{})['aws_lambda_function']={'request_gateway':{
        'for_each':ex('merge({for key,v in local.authority.wp6.approvals:key=>v if !startswith(key,"plan-")},jsondecode(var.wp6_preservation_approval_sha256==null ? "{}" : jsonencode(local.wp6_preservation_records)))'),
        'function_name':ex('"e1-gateway-${each.key}"'),
        'qualifier':ex('each.value.gateway_version')}}
    root['module']['request_identities'].update(account_id=ex('var.aws_account_id'),region=ex('var.aws_region'),
        endpoints=ex('{for key,v in data.aws_lambda_function.request_gateway:"request-gateway/${key}"=>v.qualified_arn}'),
        wp6_preservation_approval_sha256=ex('var.wp6_preservation_approval_sha256'),
        wp6_preservation_required=ex('var.dev_cicd_installation_only && var.wp3_preservation_approval_sha256!=null'),
        wp6_preservation_readbacks=ex('{for key,v in data.aws_lambda_function.request_gateway:key=>{function_name=v.function_name,qualified_arn=v.qualified_arn,role=v.role,image_uri=v.image_uri,configuration=v.environment[0].variables.E1_PROTECTED_CONFIGURATION}}'))
    root['output']['wp6']={'value':ex('module.request_identities.wp6')}
    child['variable'].update(account_id={'type':'string'},region={'type':'string'},endpoints={'type':'map(string)'})
    child['variable'].update(wp6_preservation_approval_sha256={'type':'string','default':None},
        wp6_preservation_required={'type':'bool','default':False},wp6_preservation_readbacks={'type':'any','default':{}})
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
    local['wp6_normal_active']=ex('{for key,v in local.wp6_records:key=>v if try(contains(keys(local.wp6_selected),key) && '+' && '.join(conditions)+',false)}')
    local['wp6_preservation_records']=PRESERVED_WP6
    local['wp6_preservation_fingerprints']=PRESERVED_WP6_SHA256
    local['wp6_preservation_trust_templates']={k:json.dumps(trust(k,v,'WP6_ACCOUNT'),separators=(',',':')) for k,v in PRESERVED_WP6.items()}
    local['wp6_preservation_policy_templates']={k:json.dumps(policy(k,v,'WP6_ACCOUNT','WP6_REGION'),separators=(',',':')) for k,v in PRESERVED_WP6.items()}
    local['wp6_preservation_identities']=ex('{for key,v in local.wp6_preservation_records:key=>{identity=key,role_address="module.request_identities.aws_iam_role.request[\\"${key}\\"]",policy_address="module.request_identities.aws_iam_role_policy.wp6[\\"${key}\\"]",role_name=var.authority.request_identities[key].name,role_arn="arn:aws:iam::${var.account_id}:role/${var.authority.request_identities[key].name}",trust=jsondecode(replace(local.wp6_preservation_trust_templates[key],"WP6_ACCOUNT",var.account_id)),policy=jsondecode(replace(replace(local.wp6_preservation_policy_templates[key],"WP6_ACCOUNT",var.account_id),"WP6_REGION",var.region)),gateway=try(var.wp6_preservation_readbacks[key],null)}}')
    local['wp6_preserved']=ex('{for key,v in local.wp6_preservation_records:key=>v if try(var.dev_cicd_installation_only && can(regex("^[0-9a-f]{64}$",var.wp6_preservation_approval_sha256)) && sha256(jsonencode(local.wp6_preservation_identities[key]))==local.wp6_preservation_fingerprints[key],false)}')
    local['wp6_preservation_complete']=ex('var.wp6_preservation_approval_sha256==null ? !var.wp6_preservation_required : var.dev_cicd_installation_only && length(local.wp6_preserved)==2 && length(local.wp6_normal_active)==0')
    local['wp6_active']=ex('merge(local.wp6_normal_active,local.wp6_preserved)')
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
    child['output']['wp6']={'value':ex('{active=keys(local.wp6_active),preserved=keys(local.wp6_preserved),reserved=keys(var.authority.request_identities),live="UNVERIFIED"}'),
        'precondition':{'condition':ex('local.wp6_preservation_complete'),
            'error_message':'Approve observed WP6 preservation separately: both exact readbacks are required; partial preservation or overlap with normal activation is rejected.'}}
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
    if 'Statement=concat(' in state['policy']:
        state['policy']=state['policy'].replace('}}}],jsondecode(', '}}}'+extra+'],jsondecode(')
    else:
        state['policy']=state['policy'].replace('}]})','}'+extra+']})')
    evidence=json.loads(compute['resource']['aws_s3_bucket_policy']['evidence']['policy'])
    evidence['Statement']+= [
        {'Sid':'ExternalNoWrite','Effect':'Deny','Principal':'*','NotAction':['s3:GetObject'],'Resource':['arn:aws:s3:::${local.evidence_bucket}','arn:aws:s3:::${local.evidence_bucket}/*'],'Condition':{'ArnLike':{'aws:PrincipalArn':'arn:aws:iam::${var.account_id}:role/e1-request-*'}}},
        {'Sid':'ExternalOnlyPublic','Effect':'Deny','Principal':'*','Action':['s3:GetObject'],'NotResource':['arn:aws:s3:::${local.evidence_bucket}/qualifications/demo-api/operations/*/public.json'],'Condition':{'ArnLike':{'aws:PrincipalArn':'arn:aws:iam::${var.account_id}:role/e1-request-*'}}}]
    compute['resource']['aws_s3_bucket_policy']['evidence']['policy']=json.dumps(evidence)
    return child
