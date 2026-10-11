"""Closed WP6 caller contracts; identity comes from installed entry/IAM, not JSON."""
import json
import re
import uuid

REPOSITORY = 'Kendall04/terragrunt_demo'
AUDIENCE = 'sts.amazonaws.com'
IDENTITIES = ('plan-dev','plan-prod','infra-dev','infra-prod','infra-high-risk-dev',
              'infra-high-risk-prod','release','deploy-dev','promote-prod','emergency-dev','emergency-prod')
CONTEXTS = {k:'e1-'+{'deploy-dev':'dev-deploy','promote-prod':'prod-promote',
    'emergency-dev':'dev-emergency','emergency-prod':'prod-emergency'}.get(k,k) for k in IDENTITIES}

def require(ok):
    if not ok:raise ValueError('E1_WORKFLOW_REQUEST_REJECTED')

def closed(value, keys):require(type(value) is dict and set(value)==set(keys))

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def decode(raw,limit=4096):
    require(type(raw) is str and 0<len(raw.encode())<=limit)
    def pairs(items):
        value={}
        for k,v in items:require(k not in value);value[k]=v
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:require(False))

def match(pattern,value):require(type(value) is str and re.fullmatch(pattern,value) is not None)

def environment(identity):return 'neutral' if identity=='release' else identity.rsplit('-',1)[1]

def source_ref(identity):return 'refs/heads/main' if environment(identity)=='prod' else 'refs/heads/develop'

def workflow(identity):return REPOSITORY+'/.github/workflows/'+CONTEXTS[identity]+'.yml'

def subject(identity,commit):
    require(identity in IDENTITIES);match('[0-9a-f]{40}',commit);require(commit!='0'*40)
    # GitHub escapes colons inside claim values, not the separators.
    enc=lambda v:v.replace(':','%3A')
    return 'repo:'+enc(REPOSITORY)+':environment:'+enc(CONTEXTS[identity])+':job_workflow_ref:'+enc(workflow(identity)+'@'+commit)

def context(identity,claims,configuration):
    """JWT decode is diagnostic preflight only; STS verifies signature/aud/sub."""
    require(identity in IDENTITIES)
    require(configuration['identity']==identity and configuration['environment']==environment(identity))
    match('[0-9]{12}',configuration['account']);match('[a-z]{2}(?:-[a-z]+)+-[0-9]',configuration['region'])
    require(configuration['governance']=='ADMIN_VERIFIED_G1_G9' and configuration['active'] is True)
    require(claims['aud']==AUDIENCE and claims['sub']==subject(identity,configuration['workflow_commit']))
    require(claims['repository']==REPOSITORY and claims['ref']==source_ref(identity))
    require(claims['event_name'] in ('push','workflow_dispatch','workflow_call'))
    require(claims['job_workflow_ref']==workflow(identity)+'@'+configuration['workflow_commit'])
    match('[0-9a-f]{40}',claims['sha'])
    return configuration

def request(identity,raw,operation_id=None):
    require(identity in IDENTITIES);value=decode(raw)
    if identity=='release':
        closed(value,('source_commit',));match('[0-9a-f]{40}',value['source_commit']);return value
    if identity.startswith('plan-'):
        closed(value,('operation','layer'));require(value['operation'] in ('plan','preflight'))
        require(value['layer'] in ('shared','secrets','global','data','platform','apps','edge'));return value
    operation_id=operation_id or str(uuid.uuid4())
    match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',operation_id)
    if identity.startswith('infra-'):
        closed(value,('operation_id','operation','layer','revision','parameters'))
        from scripts.lifecycle.contract import request as accepted
        event=value
        accepted('environment-lifecycle/'+identity,event)
        # High-risk public path is disjoint for reconciliation; full teardown
        # remains independently approved and may select every installed layer.
        if 'high-risk' in identity and value['operation']!='teardown':require(value['layer'] in ('data','apps'))
        return event
    if identity.startswith('emergency-'):closed(value,())
    else:
        from scripts.wp4d.gateway import request as accepted
        accepted('normal',{'operation_id':operation_id,'body':canonical(value).decode()})
        if 'reason' in value:match('[A-Za-z0-9 .,_:/()-]{1,256}',value['reason'])
    return {'operation_id':operation_id,'body':canonical(value).decode()}

def result(identity,operation,value):
    """Only controller/finalizer-written sanitized results can complete a job."""
    closed(value,('operation_id','state','release_id','source_commit'))
    require(value['operation_id']==operation)
    require(value['state'] in ('SUCCESS','PLANNED','FAILURE','UNKNOWN','UNCERTAIN'))
    if identity=='release':
        require(value['state']=='SUCCESS');match('sha256-[0-9a-f]{64}',value['release_id']);match('[0-9a-f]{40}',value['source_commit'])
    else:require(value['release_id'] is None and value['source_commit'] is None)
    return value

def status_location(identity,account,region,operation):
    match('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',operation)
    env=environment(identity)
    if identity=='release':return 'demo-release-artifacts-'+account,'qualifications/demo-api/operations/'+operation+'/public.json'
    if identity.startswith('infra-'):
        return f'e1-lifecycle-{env}-{account}-{region}','operations/environment-lifecycle/'+identity+'/'+operation+'/public.json'
    kind='recovery/'+env+'/recovery/emergency/' if identity.startswith('emergency-') else 'delivery/'+env+'/'
    return f'e1-wp4-{env}-{account}-{region}',kind+operation+'/public.json'


def valid_plan_resources(p,env,account,region):
    try:
        closed(p,('cluster','services','roles','cleanup_function','listener','rule','targets','skeleton'))
        prefix=f'arn:aws:ecs:{region}:{account}:'
        match(re.escape(prefix)+f'cluster/demo-{env}-platform-main-cluster',p['cluster'])
        cluster=p['cluster'].split('/')[-1]
        require(p['services']==[prefix+f'service/{cluster}/demo-{env}-app-api-{color}-svc' for color in ('blue','green')])
        require(p['roles']==[f'arn:aws:iam::{account}:role/demo-{env}-app-api-{color}-{role}-role' for color in ('blue','green') for role in ('task','exec')])
        match(re.escape(f'arn:aws:lambda:{region}:{account}:function:e1-cleanup-recovery-cleanup-{env}:')+'[1-9][0-9]*',p['cleanup_function'])
        for key,kind in (('listener','listener'),('rule','listener-rule')):
            match(re.escape(f'arn:aws:elasticloadbalancing:{region}:{account}:{kind}/app/demo-{env}-internal-alb/')+'[A-Za-z0-9/]+',p[key])
        require(type(p['targets']) is list and len(p['targets'])==2)
        for color,arn in zip(('blue','green'),p['targets']):
            match(re.escape(f'arn:aws:elasticloadbalancing:{region}:{account}:targetgroup/demo-{env}-{color}/')+'[a-z0-9]+',arn)
        require(type(p['skeleton']) is dict and set(p['skeleton'])==set(PLAN_READS))
        for kind,arns in p['skeleton'].items():
            require(type(arns) is list and len(arns)<=100)
            for arn in arns:
                require(type(arn) is str and '*' not in arn and '?' not in arn and
                    (f':{region}:{account}:' in arn or arn.startswith(f'arn:aws:apigateway:{region}::/')) and
                    arn.startswith('arn:aws:'+PLAN_READS[kind][0]+':') and
                    ('demo-prod-' not in arn if env=='dev' else 'demo-dev-' not in arn))
        return True
    except (ValueError,KeyError,TypeError):return False

# Resource-capable nonsecret reads beyond the region-wide Describe inventory.
PLAN_READS={
 'aws_cloudwatch_metric_alarm':('cloudwatch',('DescribeAlarms','ListTagsForResource')),
 'aws_cloudwatch_log_group':('logs',('ListTagsForResource',)),
 'aws_sns_topic':('sns',('GetTopicAttributes','ListTagsForResource','ListSubscriptionsByTopic')),
 'aws_sns_topic_subscription':('sns',('GetSubscriptionAttributes',)),
 'aws_apigatewayv2_api':('apigateway',('GET',)),
 'aws_apigatewayv2_vpc_link':('apigateway',('GET',)),
 'aws_apigatewayv2_integration':('apigateway',('GET',)),
 'aws_apigatewayv2_route':('apigateway',('GET',)),
 'aws_apigatewayv2_stage':('apigateway',('GET',)),
}

def validate_plan_binding(identity,config):
    p=config['plan_binding'];env=environment(identity)
    closed(p,('source_commit','readback','layers','resources'))
    require(p['source_commit']==config['workflow_commit'] and p['readback']=='ADMIN_VERIFIED_NONSECRET_STATE_AND_EXACT_BINDINGS')
    require(type(p['layers']) is dict and set(p['layers'])=={'shared','secrets','global','data','platform','apps','edge'})
    for layer,value in p['layers'].items():
        closed(value,('root','backend','variables'))
        require(value['root']==f'terraform/modules/target/{env}/{layer}')
        require(value['backend']=={'bucket':f'e1-lifecycle-{env}-{config["account"]}-{config["region"]}',
            'region':config['region'],'key':f'e1/lifecycle/{env}/{layer}/terraform.tfstate'})
        require(type(value['variables']) is dict and value['variables']['account_id']==config['account'] and value['variables']['region']==config['region'])
        require(not any('password' in k.lower() or k.lower() in ('connection_string','secret_value') for k in value['variables']))
    require(valid_plan_resources(p['resources'],env,config['account'],config['region']))
    return p
