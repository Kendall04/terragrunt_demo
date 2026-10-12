"""WP5 reviewed lifecycle configuration/package and selective compute admission."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
from abc import ABC, abstractmethod

import bundles
import ordinary
import ownership
import wp5_iam
import retired

ROOT = Path(__file__).resolve().parents[3]
OWNER = 'SECURITY_ROOT_OWNED'
LAYERS = ('shared', 'secrets', 'global', 'data', 'platform', 'apps', 'edge')
BINDINGS = tuple(kind + '/' + consumer for consumer in
                 ('infra-dev', 'infra-prod', 'infra-high-risk-dev', 'infra-high-risk-prod')
                 for kind in ('request-gateway', 'environment-lifecycle'))
SOURCES = ('scripts/lifecycle/contract.py', 'scripts/lifecycle/controller.py',
           'scripts/lifecycle/packages.py', 'scripts/lifecycle/runtime.py',
           'scripts/lifecycle/dev_down.py', 'scripts/lifecycle/exact_destroy.py', 'scripts/lifecycle/handoff.py',
           'scripts/nat/user_data.sh', 'scripts/environment_mutation.py',
           'scripts/lifecycle/ecs_quiescence.py', 'scripts/lifecycle/quiescence.py',
           'scripts/nat/quiescence.py', 'scripts/recovery/nat.py',
           'scripts/recovery/journal.py', 'scripts/recovery/ports.py',
           'scripts/wp4d/nat_resolver.py', 'scripts/normal_delivery/authorization.py',
           'scripts/normal_delivery/delivery.py', 'scripts/normal_delivery/e3.py',
           'scripts/normal_delivery/model_consistency.py', 'scripts/qualification/finalizer.py',
           'ci/authority/normal-delivery-model.json', 'ci/schemas/release-manifest.schema.json',
           'ci/schemas/e1-qualification.schema.json', 'demo-api/deploy/task-definition.template.json')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')


def sha(raw):return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def require(ok, reason):
    if not ok:raise ValueError('WP5_SOURCE_ADMISSION_FAILURE: ' + reason)


def configuration(doc):
    """Extend the exact WP2 extraction; never copy legacy IAM/recovery controls."""
    result = {}
    for env in ('dev', 'prod'):
        for layer in ('platform', 'edge'):
            base = ROOT/'terraform/infra'/layer
            for relative, path in retired.sources(ROOT, 'terraform/infra/'+layer):
                text = path.read_text(encoding='utf-8')
                text = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))+'\n'
                text = text.replace('var.env', '"'+env+'"').replace('var.project', '"demo"')
                text = text.replace('${"demo"}', 'demo').replace('${"'+env+'"}', env)
                if relative == 'variables.tf':
                    text = ordinary.select(text, lambda h:not h.startswith(('variable "env"', 'variable "project"')))
                name = ('ordinary-'+relative) if '/' not in relative else relative
                result['terraform/modules/target/'+env+'/'+layer+'/'+name] = text
            result['terraform/modules/target/'+env+'/'+layer+'/main.tf.json'] = {
                'terraform': {'backend': {'s3': {'encrypt': True, 'use_lockfile': True}}},
                'provider': {'aws': {'region':'${var.region}', 'allowed_account_ids':['${var.account_id}']}},
                'variable': {'account_id':{'type':'string','nullable':False},'region':{'type':'string','nullable':False}}}
        # Reuse actual reviewed provider checksums. No downloaded/generated lock.
        lock = retired.source(ROOT, 'terraform/live/dev/shared/.terraform.lock.hcl').read_text()
        for layer in LAYERS:
            result[f'terraform/modules/target/{env}/{layer}/.terraform.lock.hcl'] = lock
    return result


def target_overlay(wiring):
    for env in ('dev', 'prod'):
        root = f'terraform/modules/target/{env}/'
        # Floating AMI/user input is not an installed SQL security binding.
        name = root+'data/ordinary-main.tf'
        text = ordinary.select(wiring[name], lambda h:not h.startswith('data "aws_ami"'))
        wiring[name] = text.replace('data.aws_ami.ubuntu_2204.id', 'var.protected_sql_ami')
        wiring[root+'data/ordinary-variables.tf'] += '\nvariable "protected_sql_ami" { type = string }\n'
        # The old archive provider served the removed Lambda ownership. The
        # protected lifecycle bundle has no caller ZIP/package compilation.
        wiring[root+'apps/ordinary-versions.tf']=re.sub(r'^\s*archive = .*\n','',wiring[root+'apps/ordinary-versions.tf'],flags=re.M).replace('aws     =', 'aws =')
        # NAT launch templates and handlers are security installations. The
        # lifecycle root receives immutable template IDs/versions only.
        wiring[root+'global/wp5-nat.tf.json'] = {
            'variable': {'protected_nat_launch': {'type': 'map(object({ id = string, version = number, subnet = string, recovery = string }))', 'default': {},
                'validation':{'condition':'${length(var.protected_nat_launch) == 0 || sort(keys(var.protected_nat_launch)) == ["a", "b"]}',
                    'error_message':'Only the exact two protected NAT slots are admitted.'}}},
            'resource': {
                'aws_eip': {'wp5_nat': {'for_each': '${toset(["a", "b"])}', 'domain':'vpc',
                    'tags': {'Project':'demo','Environment':env,'Name':'${"demo-'+env+'-nat-eip-${each.key}"}'}}},
                'aws_autoscaling_group': {'wp5_nat': {'for_each':'${var.protected_nat_launch}',
                    'name':'${"demo-'+env+'-asg-nat-${each.key}"}', 'min_size':1,'max_size':1,'desired_capacity':1,
                    'vpc_zone_identifier':['${each.value.subnet}'],
                    'enabled_metrics':['GroupDesiredCapacity','GroupInServiceInstances'],
                    'metrics_granularity':'1Minute',
                    'launch_template':{'id':'${each.value.id}','version':'${tostring(each.value.version)}'},
                    'tag':[{'key':'Environment','value':env,'propagate_at_launch':True},
                           {'key':'Group','value':'${each.key}','propagate_at_launch':True},
                           {'key':'Role','value':'nat','propagate_at_launch':True}],
                    'lifecycle':{'precondition':{'condition':'${each.value.recovery == "ADMIN_VERIFIED_ALL_THREE_HANDLERS_AND_EXACT_MEMBERSHIP" && each.value.version > 0 && floor(each.value.version) == each.value.version && can(regex("^lt-[0-9a-f]{8,17}$", each.value.id))}',
                        'error_message':'Exact administrator-installed NAT launch identity required.'}}}}}}
        nat=wiring[root+'global/wp5-nat.tf.json']
        nat['output']={'nat_eip_allocation_ids':{'value':'${{for key,v in aws_eip.wp5_nat:key=>v.allocation_id}}'},
            'nat_asg_names':{'value':'${{for key,v in aws_autoscaling_group.wp5_nat:key=>v.name}}'}}
        alarms=retired.source(ROOT, 'terraform/infra/global/modules/nat/alarms_nat.tf').read_text(encoding='utf-8')
        alarms='\n'.join(line for line in alarms.splitlines() if not line.lstrip().startswith('#'))+'\n'
        alarms=alarms.replace('var.name','local.name').replace('var.tags','local.tags')
        for side in ('a','b'):
            block=ordinary.select(alarms,lambda header:header.startswith('resource "aws_cloudwatch_metric_alarm" "nat_'+side+'_'))
            block=block.replace('var.enable_alarms ? 1 : 0','contains(keys(var.protected_nat_launch), "'+side+'") ? 1 : 0')
            block=block.replace('aws_autoscaling_group.nat_'+side+'.name','aws_autoscaling_group.wp5_nat["'+side+'"].name')
            wiring[root+'global/wp5-nat-alarms-'+side+'.tf']=block
        # E7 corrects active TARGET output only; frozen retired text stays inert.
        ecs = root+'apps/modules/ecs_service/alarm_ecs_service.tf'
        wiring[ecs] = wiring[ecs].replace('"AWS/ECS"', '"ECS/ContainerInsights"')
        wiring[ecs] = wiring[ecs].replace('m_desired - m_running',
            'IF((FILL(m_desired, -1) >= 0) AND (FILL(m_running, -1) >= 0), m_desired - m_running)')
        for side in ('a', 'b'):
            name = root+'global/wp5-nat-alarms-'+side+'.tf'
            wiring[name] = wiring[name].replace('desired - inservice',
                'IF((FILL(desired, -1) >= 0) AND (FILL(inservice, -1) >= 0), desired - inservice)')
        # Gauge absence is unknown, including intentionally inactive colors.
        # Sparse ALB 5xx events keep notBreaching; latency has no such evidence.
        for name in (ecs, root+'data/ordinary-main.tf',
                     root+'global/wp5-nat-alarms-a.tf', root+'global/wp5-nat-alarms-b.tf'):
            wiring[name] = wiring[name].replace('"notBreaching"', '"missing"')
        name = root+'global/modules/alb/alarms_tg.tf'
        starts = list(ordinary.BLOCK.finditer(wiring[name]))
        blocks = []
        for index, match in enumerate(starts):
            block = wiring[name][match.start():starts[index+1].start() if index+1<len(starts) else len(wiring[name])]
            if match.group().endswith('_latency" {'):
                block = block.replace('"notBreaching"', '"missing"')
            blocks.append(block)
        wiring[name] = ''.join(blocks)
        # Keep zero-count, role-free bootstrap and delivery-owned ignore_changes.
        for layer in LAYERS:
            name = root+layer+'/main.tf.json'
            if name in wiring:
                wiring[name].setdefault('terraform', {})['backend'] = {'s3':{'encrypt':True,'use_lockfile':True}}


def package_files(root, doc, binding):
    env = binding.rsplit('-',1)[1]
    wiring = {**ordinary.wiring(doc), **ownership.consumer_wiring(doc), **configuration(doc)}
    for e in ('dev','prod'):
        name=f'terraform/modules/target/{e}/global/modules/alb/target_group.tf'
        for color in ('blue','green'):
            wiring[name]=wiring[name].replace('${var.name}-'+color+'-tg', 'demo-'+e+'-'+color)
    target_overlay(wiring)
    files = {name: (value.encode('utf-8') if isinstance(value,str) else canonical(value))
             for name,value in wiring.items() if name.startswith('terraform/modules/target/'+env+'/')}
    # Only protected publication data is needed by the immutable consumers;
    # exclude package digests/install maps, avoiding self-referential identities.
    files['terraform/infra/security/authority.json'] = canonical({'ownership_closure':doc['ownership_closure']})
    for name in SOURCES+('terraform/infra/data/user_data.sh',):
        files[name]=(Path(root)/name).read_bytes().replace(b'\r\n',b'\n')
    return files


def artifact(root, doc, binding):
    require(binding in BINDINGS, 'WP2 reserved lifecycle binding')
    return canonical({'schema':'E1_WP5_PACKAGE_V1','binding':binding,
        'reservation':doc['control_bundles']['consumer_references'][binding],
        'files':{name:base64.b64encode(raw).decode('ascii') for name,raw in sorted(package_files(root,doc,binding).items())}})


def contract(root, doc):
    nodes=doc['controller_compute']['nodes']
    return {'schema':'E1_WP5_LIFECYCLE_V1','owner':OWNER,
        'selected':{binding:{'name':nodes[binding]['name'],'role':nodes[binding]['role_name'],
                            'environment':binding.rsplit('-',1)[1],'engine':nodes[binding]['engine'],
                            'required_inputs':required_inputs(root,doc,binding),
                            'package_sha256':sha(artifact(root,doc,binding))} for binding in BINDINGS},
        'installations':{},'runtime_approvals':{},'environment_bindings':{},
        'active_contracts':{},'nat_launch_inputs':{},'external_invocation':[], 'live':'UNVERIFIED_NOT_DEPLOYED'}


def validate(root,doc):
    require(doc.get('wp5')==contract(root,doc),'package/installation/active-contract drift')


def install(root,doc,binding,account,region,admin,source_commit):
    """Authenticated admin port; VersionId comes solely from storage response."""
    from publication import AdminBundleStorage
    require(isinstance(admin,AdminBundleStorage),'separately authenticated admin storage port')
    require(bool(re.fullmatch('[0-9]{12}',account)) and bool(re.fullmatch('[a-z]{2}(-[a-z]+)+-[0-9]+',region)),'account/region')
    require(bool(re.fullmatch('[0-9a-f]{40}',source_commit)),'reviewed source commit')
    raw=artifact(root,doc,binding); digest=sha(raw)
    require(digest==doc['wp5']['selected'][binding]['package_sha256'],'admitted exact source')
    bucket=f'e1-control-bundles-{account}-{region}'; key='bundles/sha256/'+digest+'.json'
    returned=admin.put_if_absent(bucket,key,raw,digest)
    require(type(returned) is dict and set(returned)=={'bucket','key','version_id'} and returned['bucket']==bucket and returned['key']==key,'returned installation identity')
    version=returned['version_id']
    require(type(version) is str and version.strip()==version and version.lower() not in ('','null','latest'),'returned exact VersionId')
    read=admin.get_exact(bucket,key,version)
    require(read=={**returned,'bytes':raw},'exact version byte readback')
    return {**returned,'sha256':digest,'binding':binding,'source_commit':source_commit,
            'readback':'EXACT_VERSION_BYTES_VERIFIED'}


class LifecycleAdminChannel(ABC):
    """Separately authenticated admin publication, never a runtime dependency.

    observe must independently verify exact environment membership, skeleton
    IDs, installation/image approvals, bootstrap and operator approvals. Caller
    claims/tags alone are insufficient. No live AWS adapter is implemented here.
    """
    @abstractmethod
    def observe(self,binding):raise NotImplementedError
    @abstractmethod
    def write_current(self,bucket,key,raw):raise NotImplementedError
    @abstractmethod
    def read_exact(self,bucket,key,version):raise NotImplementedError


def publish(doc,binding,installation,runtime,account,region,admin):
    require(isinstance(admin,LifecycleAdminChannel),'separately authenticated lifecycle admin channel')
    observed=admin.observe(binding)
    require(type(observed) is dict and set(observed)=={'complete','configuration','resources','sql_launch'} and
            observed['complete'] is True,'complete authoritative environment observation')
    selected=doc['wp5']['selected'][binding]
    require(ready(binding,selected,installation,runtime,observed['configuration'],account,region) and
            wp5_iam.valid_resources(observed['resources'],account,region,selected['environment']) and
            ('/infra-high-risk-' not in binding or wp5_iam.valid_sql(observed['sql_launch'],account,region)),
            'complete installation/approved image/protected binding prerequisites')
    bucket='demo-release-artifacts-'+account;key='lifecycle/'+binding+'/current.json'
    raw=canonical(observed['configuration']);receipt=admin.write_current(bucket,key,raw)
    require(type(receipt) is dict and set(receipt)=={'bucket','key','version_id'} and receipt['bucket']==bucket and
            receipt['key']==key and type(receipt['version_id']) is str and receipt['version_id'].strip()==receipt['version_id'] and
            receipt['version_id'].lower() not in ('','null','latest'),'returned exact configuration version')
    require(admin.read_exact(bucket,key,receipt['version_id'])=={**receipt,'bytes':raw},'exact protected configuration readback')
    return {**receipt,'sha256':sha(raw),'binding':binding,'verification':'EXACT_VERSION_BYTES_VERIFIED'}


def ready(binding,selected,installation,runtime,protected,account,region):
    """Class prerequisites; registry is admin source, not caller assertions."""
    try:
        from scripts.lifecycle import contract as c
        c.keys(installation, ('bucket','key','version_id','sha256','binding','source_commit','readback'), 'verified installation')
        c.require(installation['binding']==binding and installation['sha256']==selected['package_sha256'] and
                  installation['bucket']==f'e1-control-bundles-{account}-{region}' and installation['readback']=='EXACT_VERSION_BYTES_VERIFIED','installation provenance')
        c.require(installation['key']=='bundles/sha256/'+installation['sha256']+'.json' and
                  installation['version_id'].lower() not in ('','null','latest') and bool(re.fullmatch('[0-9a-f]{40}',installation['source_commit'])),'exact install')
        c.keys(runtime, ('uri','package_sha256','source_commit','tools'), 'runtime approval')
        c.require(runtime['package_sha256']==selected['package_sha256'] and runtime['source_commit']==installation['source_commit'] and
                  bool(re.fullmatch(account+r'\.dkr\.ecr\.'+re.escape(region)+r'\.amazonaws\.com/e1-wp5-'+binding.replace('/','-')+r'@sha256:[0-9a-f]{64}',runtime['uri'])),'immutable runtime')
        c.require(runtime['tools']=={'terraform':'1.13.4','providers':'LOCKED_READONLY_MIRROR','python':'PROTECTED_IMAGE'},'installed tools')
        c.require(protected['binding']==binding and protected['environment']==selected['environment'] and
                  selected['package_sha256'] in protected['active_contracts'],'active protected binding')
        c.require(set(protected['layers'])==set(LAYERS),'all original layers')
        c.require(protected['account']==account and protected['region']==region and
                  protected['bootstrap'].get('state_store')=='ADMIN_VERIFIED_READY' and
                  protected['bootstrap'].get('configuration_publication')=='ADMIN_VERIFIED_READY' and
                  protected['bootstrap'].get('service_linked_roles')=='ADMIN_VERIFIED_READY','live bootstrap prerequisites')
        reference={key:installation[key] for key in ('bucket','key','version_id','sha256','binding','source_commit')}
        c.require(protected['installations'].get(selected['package_sha256'])==reference,'current installation binding')
        for name,layer in protected['layers'].items():
            c.keys(layer,('root','variables','addresses','membership','backend'),'layer shape')
            c.require(layer['root']==f'terraform/modules/target/{selected["environment"]}/{name}' and
                      layer['backend']=={'bucket':f'e1-lifecycle-{selected["environment"]}-{account}-{region}',
                      'region':region,'key':f'e1/lifecycle/{selected["environment"]}/{name}/terraform.tfstate'} and
                      layer['variables'].get('account_id')==account and layer['variables'].get('region')==region,'protected roots/backends/providers')
            c.require(set(selected['required_inputs'][name])<=set(layer['variables']) and
                      all(layer['variables'][key] is not None for key in selected['required_inputs'][name]),'complete installed root inputs')
        return True
    except (ValueError,KeyError,TypeError,AttributeError):return False


def required_inputs(root,doc,binding):
    """Derive required root variables from the exact installed extraction."""
    files=package_files(root,doc,binding);env=binding.rsplit('-',1)[1];result={name:set() for name in LAYERS}
    for name,raw in files.items():
        path=Path(name)
        if path.parent.as_posix() not in {f'terraform/modules/target/{env}/{layer}' for layer in LAYERS}:continue
        layer=path.parent.name
        if name.endswith('.tf.json'):
            result[layer].update(k for k,v in json.loads(raw).get('variable',{}).items() if 'default' not in v)
        elif name.endswith('.tf'):
            text=raw.decode('utf-8');starts=list(ordinary.BLOCK.finditer(text))
            for index,match in enumerate(starts):
                variable=re.match(r'variable "([^"]+)"',match.group())
                block=text[match.start():starts[index+1].start() if index+1<len(starts) else len(text)]
                if variable and not re.search(r'\bdefault\s*=',block):result[layer].add(variable[1])
    return {name:sorted(value) for name,value in result.items()}


def creation_supported(doc, installations, runtimes, bindings, account, region):
    accepted={key for key,v in doc['wp5']['selected'].items() if ready(key,v,
        installations.get(key),runtimes.get(key),bindings.get(key,{}).get('configuration'),account,region)
        and wp5_iam.valid_resources(bindings.get(key,{}).get('resources'),account,region,v['environment'])
        and ('/infra-high-risk-' not in key or wp5_iam.valid_sql(bindings.get(key,{}).get('sql_launch'),account,region))}
    return sorted(key for key in accepted if not key.startswith('request-gateway/') or
                  'environment-lifecycle/'+key.split('/')[1] in accepted)


def extend(tf):
    """Use the eight accepted WP2 reservations; no external request activation."""
    ex=lambda source:'${'+source+'}'
    for name in ('installations','runtime_approvals','environment_bindings'):
        tf['variable']['wp5_'+name]={'type':'any','default':{}}
    local=tf['locals'];resources=tf['resource']
    local['wp5_contract']=ex('var.authority.wp5')
    local['wp5_candidates']=ex('{for key,v in local.wp5_contract.selected:key=>merge(v,{install=try(var.wp5_installations[key],null),runtime=try(var.wp5_runtime_approvals[key],null),binding=try(var.wp5_environment_bindings[key],null)})}')
    checks=[
        'sort(keys(v.install))==sort(["bucket","key","version_id","sha256","binding","source_commit","readback"])',
        'sort(keys(v.runtime))==sort(["uri","package_sha256","source_commit","tools"])',
        'sort(keys(v.binding.configuration))==sort(["binding","environment","account","region","active_contracts","installations","layers","bootstrap","operation_approvals","teardown_approvals"])',
        'v.install.binding==key','v.install.sha256==v.package_sha256',
        'v.install.bucket=="e1-control-bundles-${var.account_id}-${var.region}"',
        'v.install.key=="bundles/sha256/${v.package_sha256}.json"',
        'v.install.version_id!=null','length(trimspace(v.install.version_id))>0',
        'v.install.version_id==trimspace(v.install.version_id)',
        '!contains(["null","latest"],lower(v.install.version_id))',
        'v.install.readback=="EXACT_VERSION_BYTES_VERIFIED"',
        'can(regex("^[0-9a-f]{40}$",v.install.source_commit))',
        'v.runtime.package_sha256==v.package_sha256','v.runtime.source_commit==v.install.source_commit',
        'can(regex("^${var.account_id}[.]dkr[.]ecr[.]${var.region}[.]amazonaws[.]com/e1-wp5-${replace(key,"/","-")}@sha256:[0-9a-f]{64}$",v.runtime.uri))',
        'v.runtime.tools=={terraform="1.13.4",providers="LOCKED_READONLY_MIRROR",python="PROTECTED_IMAGE"}',
        'v.binding.configuration.binding==key','v.binding.configuration.environment==v.environment',
        'v.binding.configuration.account==var.account_id','v.binding.configuration.region==var.region',
        'contains(v.binding.configuration.active_contracts,v.package_sha256)',
        'v.binding.configuration.bootstrap.state_store=="ADMIN_VERIFIED_READY"',
        'v.binding.configuration.bootstrap.configuration_publication=="ADMIN_VERIFIED_READY"',
        'v.binding.configuration.bootstrap.service_linked_roles=="ADMIN_VERIFIED_READY"',
        'v.binding.configuration.installations[v.package_sha256]=={binding=key,bucket=v.install.bucket,key=v.install.key,version_id=v.install.version_id,sha256=v.package_sha256,source_commit=v.install.source_commit}',
        'sort(keys(v.binding.configuration.layers))==sort('+json.dumps(LAYERS)+')',
        'alltrue([for name,layer in v.binding.configuration.layers:layer.root=="terraform/modules/target/${v.environment}/${name}" && layer.backend=={bucket="e1-lifecycle-${v.environment}-${var.account_id}-${var.region}",key="e1/lifecycle/${v.environment}/${name}/terraform.tfstate",region=var.region} && layer.variables.account_id==var.account_id && layer.variables.region==var.region])',
        'alltrue([for name,layer in v.binding.configuration.layers:alltrue([for input in v.required_inputs[name]:contains(keys(layer.variables),input) && try(layer.variables[input]!=null,false)])])',
        'alltrue([for name,layer in v.binding.configuration.layers:sort(keys(layer))==sort(["root","variables","addresses","membership","backend"])])',
        'sort(keys(v.binding.resources))==sort('+json.dumps(sorted(wp5_iam.INVENTORY))+')',
        'alltrue(flatten([for kind,arns in v.binding.resources:[for arn in arns:startswith(arn,"arn:aws:") && !strcontains(arn,"*") && !strcontains(arn,"?") && (strcontains(arn,":${var.region}:${var.account_id}:") || startswith(arn,"arn:aws:apigateway:${var.region}::"))]]))',
        'alltrue(flatten([for kind,arns in v.binding.resources:[for arn in arns:!strcontains(arn,v.environment=="dev"?"demo-prod-":"demo-dev-")]]))',
        '(!strcontains(key,"/infra-high-risk-") || try(sort(keys(v.binding.sql_launch))==sort(["image","subnet","security_group","instance_type"]) && v.binding.sql_launch.instance_type=="t3a.small" && can(regex("^arn:aws:ec2:${var.region}::image/ami-[0-9a-f]{8,17}$",v.binding.sql_launch.image)) && can(regex("^arn:aws:ec2:${var.region}:${var.account_id}:subnet/subnet-[0-9a-f]{8,17}$",v.binding.sql_launch.subnet)) && can(regex("^arn:aws:ec2:${var.region}:${var.account_id}:security-group/sg-[0-9a-f]{8,17}$",v.binding.sql_launch.security_group)),false))',
    ]
    local['wp5_ready']=ex('{for key,v in local.wp5_candidates:key=>v if try('+' && '.join(checks)+',false)}')
    local['wp5_active']=ex('{for key,v in local.wp5_ready:key=>v if !startswith(key,"request-gateway/") || contains(keys(local.wp5_ready),"environment-lifecycle/${split("/",key)[1]}")}')
    local['wp5_gateways']=ex('{for k,v in local.wp5_active:k=>v if v.engine=="LAMBDA"}')
    local['wp5_projects']=ex('{for k,v in local.wp5_active:k=>v if v.engine=="CODEBUILD"}')
    templates={}
    for key in BINDINGS:
        members={kind:['WP5_'+kind] for kind in wp5_iam.INVENTORY}
        members['_sql_launch']={'image':'WP5_SQL_IMAGE','subnet':'WP5_SQL_SUBNET','security_group':'WP5_SQL_SG','instance_type':'WP5_SQL_TYPE'}
        templates[key]=json.dumps(wp5_iam.policy(key,'WP5_ACCOUNT','WP5_REGION',members,'WP5_PACKAGE','WP5_VERSION'),separators=(',',':'),sort_keys=True)
    local['wp5_policy_templates']=templates
    expression='local.wp5_policy_templates[each.key]'
    for token,value in (('WP5_ACCOUNT','var.account_id'),('WP5_REGION','var.region'),('WP5_PACKAGE','each.value.package_sha256')):
        expression='replace('+expression+','+json.dumps(token)+','+value+')'
    expression='replace('+expression+',"\\\"WP5_VERSION\\\"",jsonencode(each.value.install.version_id))'
    for kind in wp5_iam.INVENTORY:
        expression='replace('+expression+','+json.dumps(json.dumps(['WP5_'+kind],separators=(',',':')))+',jsonencode(each.value.binding.resources.'+kind+'))'
        expression='replace('+expression+','+json.dumps(json.dumps(['WP5_'+kind+':*'],separators=(',',':')))+',jsonencode([for arn in each.value.binding.resources.'+kind+':"${arn}:*"]))'
    for token,field in (('WP5_SQL_IMAGE','image'),('WP5_SQL_SUBNET','subnet'),('WP5_SQL_SG','security_group'),('WP5_SQL_TYPE','instance_type')):
        expression='replace('+expression+','+json.dumps(json.dumps(token))+',jsonencode(try(each.value.binding.sql_launch.'+field+',"UNAVAILABLE")))'
    local['wp5_config']=ex('{for key,v in local.wp5_active:key=>jsonencode({binding=key,account=var.account_id,region=var.region,package={binding=key,bucket=v.install.bucket,key=v.install.key,sha256=v.package_sha256,version_id=v.install.version_id,source_commit=v.install.source_commit}})}')
    trust='jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Action="sts:AssumeRole",Principal={Service=each.value.engine=="LAMBDA"?"lambda.amazonaws.com":"codebuild.amazonaws.com"},Condition=each.value.engine=="CODEBUILD"?{StringEquals={"aws:SourceAccount"=var.account_id},ArnEquals={"aws:SourceArn"="arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}"}}:{}}]})'
    old=resources['aws_iam_role']['execution']
    old['assume_role_policy']=ex('contains(keys(local.wp5_active),each.key)?'+trust+':('+old['assume_role_policy'][2:-1]+')')
    old['description']=ex('contains(keys(local.wp5_active),each.key)?"WP5 protected lifecycle execution":('+old['description'][2:-1]+')')
    resources['aws_iam_role_policy']['inert']['for_each']=ex('{for k,v in local.nodes:k=>v if !contains(keys(local.wp3_active),k) && !contains(keys(local.wp4d_active),k) && !contains(keys(local.wp5_active),k)}')
    # Admin-owned customer-managed policies avoid the aggregate inline ceiling.
    policy_expression='jsonencode({Version="2012-10-17",Statement=[for s in jsondecode('+expression+').Statement:merge(s,{Resource=sort(s.Resource)}) if length(s.Resource)>0]})'
    local['wp5_policies']=ex('{for key,v in local.wp5_active:key=>jsondecode('+policy_expression.replace('each.value','v').replace('each.key','key')+')}')
    local['wp5_chunks']=ex('{for pair in flatten([for key,v in local.wp5_projects:[for index in range(min(8,length(local.wp5_policies[key].Statement))):{key="${key}/${index}",role=v.role,name="wp5-${split("/",key)[1]}-${index}",policy=jsonencode({Version="2012-10-17",Statement=[for position in range(index*ceil(length(local.wp5_policies[key].Statement)/8),min((index+1)*ceil(length(local.wp5_policies[key].Statement)/8),length(local.wp5_policies[key].Statement))):local.wp5_policies[key].Statement[position]]})}]]):pair.key=>pair}')
    resources['aws_iam_role_policy']['wp5']={'for_each':ex('local.wp5_gateways'),'name':'wp5-protected-lifecycle',
        'role':ex('each.value.role'),'policy':ex('jsonencode(local.wp5_policies[each.key])')}
    resources.setdefault('aws_iam_policy',{})['wp5']={'for_each':ex('local.wp5_chunks'),'name':ex('each.value.name'),
        'policy':ex('each.value.policy'),'lifecycle':{'precondition':{'condition':ex('length(each.value.policy)<=6144'),
        'error_message':'Exact lifecycle bindings exceed the IAM managed policy ceiling; remain inactive.'}}}
    resources.setdefault('aws_iam_role_policy_attachment',{})['wp5']={'for_each':ex('local.wp5_chunks'),
        'role':ex('each.value.role'),'policy_arn':ex('aws_iam_policy.wp5[each.key].arn')}
    resources['aws_iam_role_policy']['wp5_peer']={'for_each':ex('local.wp5_gateways'),'name':'wp5-exact-controller-package',
        'role':ex('each.value.role'),'policy':ex('jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Action=["s3:GetObjectVersion"],Resource=["arn:aws:s3:::e1-control-bundles-${var.account_id}-${var.region}/bundles/sha256/${local.wp5_active["environment-lifecycle/${split("/",each.key)[1]}"].package_sha256}.json"],Condition={StringEquals={"s3:VersionId"=local.wp5_active["environment-lifecycle/${split("/",each.key)[1]}"].install.version_id}}}]})')}
    repositories={key:{'name':doc_name,'engine':('LAMBDA' if key.startswith('request-gateway/') else 'CODEBUILD')}
        for key in BINDINGS for doc_name in ['e1-'+('gateway-' if key.startswith('request-gateway/') else 'controller-')+key.split('/')[1]]}
    local['wp5_repositories']=repositories
    resources['aws_ecr_repository']['wp5']={'for_each':ex('local.wp5_repositories'),'name':ex('"e1-wp5-${replace(each.key,"/","-")}"'),
        'image_tag_mutability':'IMMUTABLE','image_scanning_configuration':{'scan_on_push':True}}
    resources['aws_ecr_repository_policy']['wp5']={'for_each':ex('local.wp5_repositories'),'repository':ex('aws_ecr_repository.wp5[each.key].name'),
        'policy':ex('jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service=each.value.engine=="LAMBDA"?"lambda.amazonaws.com":"codebuild.amazonaws.com"},Action=["ecr:BatchGetImage","ecr:GetDownloadUrlForLayer","ecr:BatchCheckLayerAvailability"],Condition={StringEquals={"aws:SourceAccount"=var.account_id},ArnEquals={"aws:SourceArn"=each.value.engine=="LAMBDA"?"arn:aws:lambda:${var.region}:${var.account_id}:function:${each.value.name}":"arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}"}}}]})')}
    resources['aws_cloudwatch_log_group']['wp5']={'for_each':ex('local.wp5_active'),
        'name':ex('"/aws/${each.value.engine=="LAMBDA"?"lambda":"codebuild"}/${each.value.name}"'),'retention_in_days':14}
    resources['aws_lambda_function']['wp5']={'for_each':ex('local.wp5_gateways'),'function_name':ex('each.value.name'),
        'role':ex('aws_iam_role.execution[each.key].arn'),'package_type':'Image','image_uri':ex('each.value.runtime.uri'),
        'publish':True,'timeout':120,'memory_size':256,'reserved_concurrent_executions':1,
        'image_config':{'command':['scripts.lifecycle.runtime.handler']},
        'environment':{'variables':{'E1_WP5_CONFIGURATION':ex('local.wp5_config[each.key]')}},
        'depends_on':['aws_iam_role_policy.wp5','aws_iam_role_policy.wp5_peer','aws_cloudwatch_log_group.wp5']}
    resources['aws_codebuild_project']['wp5']={'for_each':ex('local.wp5_projects'),'name':ex('each.value.name'),
        'service_role':ex('aws_iam_role.execution[each.key].arn'),'build_timeout':30,
        'source':{'type':'NO_SOURCE','buildspec':json.dumps({'version':'0.2','phases':{'build':{'commands':['/opt/e1/bin/python -I -B -m scripts.lifecycle.runtime']}}})},
        'artifacts':{'type':'NO_ARTIFACTS'},'cache':{'type':'NO_CACHE'},
        'environment':{'type':'LINUX_CONTAINER','compute_type':'BUILD_GENERAL1_SMALL','image':ex('each.value.runtime.uri'),
            'image_pull_credentials_type':'CODEBUILD','privileged_mode':False,
            'environment_variable':[{'name':'E1_WP5_CONFIGURATION','type':'PLAINTEXT','value':ex('local.wp5_config[each.key]')}]},
        'logs_config':{'cloudwatch_logs':{'status':'DISABLED'},'s3_logs':{'status':'DISABLED'}},
        'depends_on':['aws_iam_role_policy_attachment.wp5','aws_cloudwatch_log_group.wp5']}
    tf['output']['wp5']={'value':{'active_bindings':ex('keys(local.wp5_active)'),
        'bundle_readers':ex('{for k,v in local.wp5_active:k=>"arn:aws:iam::${var.account_id}:role/${v.role}"}'),
        'external_invocations':[],'live':'UNVERIFIED_NOT_DEPLOYED'}}
    return tf


def foundations():
    """Admin-owned nonsensitive lifecycle state, never ordinary bucket control."""
    ex=lambda source:'${'+source+'}'
    userdata=(ROOT/'scripts/nat/user_data.sh').read_text(encoding='utf-8')
    tf={'terraform':{'required_providers':{'aws':{'source':'hashicorp/aws','version':'~> 5.50'}}},
        'variable':{'account_id':{'type':'string'},'region':{'type':'string'},'admin_arn':{'type':'string'},
            'nat_launch_inputs':{'type':'any','default':{}}},
        'locals':{'nat_userdata':userdata,'nat_ready':ex('{for key,v in var.nat_launch_inputs:key=>v if try(contains(["dev/a","dev/b","prod/a","prod/b"],key) && v.installation=="ADMIN_VERIFIED_NETWORK_BINDING" && v.environment==split("/",key)[0] && v.account==var.account_id && v.region==var.region && can(regex("^ami-[0-9a-f]{8,17}$",v.ami)) && can(regex("^subnet-[0-9a-f]{8,17}$",v.subnet)) && can(regex("^sg-[0-9a-f]{8,17}$",v.security_group)),false)}')},
        'resource':{
            'aws_s3_bucket':{'state':{'for_each':ex('toset(["dev","prod"])'),'bucket':ex('"e1-lifecycle-${each.key}-${var.account_id}-${var.region}"'),'force_destroy':False}},
            'aws_s3_bucket_versioning':{'state':{'for_each':ex('aws_s3_bucket.state'),'bucket':ex('each.value.id'),'versioning_configuration':{'status':'Enabled'}}},
            'aws_s3_bucket_server_side_encryption_configuration':{'state':{'for_each':ex('aws_s3_bucket.state'),'bucket':ex('each.value.id'),
                'rule':{'apply_server_side_encryption_by_default':{'sse_algorithm':'AES256'}}}},
            'aws_s3_bucket_public_access_block':{'state':{'for_each':ex('aws_s3_bucket.state'),'bucket':ex('each.value.id'),
                **{key:True for key in ('block_public_acls','block_public_policy','ignore_public_acls','restrict_public_buckets')}}},
            'aws_s3_bucket_policy':{'state':{'for_each':ex('aws_s3_bucket.state'),'bucket':ex('each.value.id'),
                'policy':ex('jsonencode({Version="2012-10-17",Statement=[{Sid="TLSOnly",Effect="Deny",Principal="*",Action="s3:*",Resource=[each.value.arn,"${each.value.arn}/*"],Condition={Bool={"aws:SecureTransport"="false"}}},{Sid="OnlyOwnEnvironmentAndAdmin",Effect="Deny",Principal="*",Action="s3:*",Resource=[each.value.arn,"${each.value.arn}/*"],Condition={ArnNotEquals={"aws:PrincipalArn"=concat([var.admin_arn],[for name in ["e1-gateway-infra-${each.key}","e1-gateway-infra-high-risk-${each.key}","e1-controller-infra-${each.key}","e1-controller-infra-high-risk-${each.key}"]:"arn:aws:iam::${var.account_id}:role/${name}-exec"])}}}]})')}}},
        'output':{'state_buckets':{'value':ex('{for key,v in aws_s3_bucket.state:key=>v.id}')},'live':{'value':'UNVERIFIED_NOT_DEPLOYED'}}}
    tf['resource']['aws_launch_template']={'nat':{'for_each':ex('local.nat_ready'),
        'name':ex('"demo-${each.value.environment}-lt-nat-${split("/",each.key)[1]}"'),
        'image_id':ex('each.value.ami'),'instance_type':'t3.micro','user_data':ex('base64encode(local.nat_userdata)'),
        'iam_instance_profile':{'name':ex('"demo-${each.value.environment}-nat-instance-profile"')},
        'network_interfaces':{'subnet_id':ex('each.value.subnet'),'security_groups':[ex('each.value.security_group')],
            'associate_public_ip_address':True,'delete_on_termination':True},
        'metadata_options':{'http_tokens':'required'},
        'tag_specifications':{'resource_type':'instance','tags':{'Environment':ex('each.value.environment'),
            'Role':'nat','Group':ex('split("/",each.key)[1]'),'Az':ex('each.value.az'),'Project':'demo'}},
        'tags':{'E1Owner':'SECURITY_ROOT_OWNED','Environment':ex('each.value.environment')},
        'lifecycle':{'prevent_destroy':True}}}
    tf['output']['nat_installation_candidates']={'value':ex('{for key,v in aws_launch_template.nat:key=>{id=v.id,version=v.latest_version,user_data_sha256=sha256(local.nat_userdata),verification="UNVERIFIED_REQUIRES_EXACT_LIVE_READBACK"}}')}
    return tf
