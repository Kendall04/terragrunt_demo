"""E15-S supervised isolated lab preparation. No network/process/execution port.

E1 closes all installable IaC roots. This helper prepares an inert single-state
composition for separate owner admission; it cannot activate or bypass WP5.
"""
import argparse
import copy
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[1]
BLOCKERS = ['LAB_ADMIN_STATE_AND_IAM_ADMISSION_REQUIRED', 'LIVE_IDENTITY_AND_OWNERSHIP_UNVERIFIED',
            'LIVE_BUILD_DEPLOY_READINESS_AND_RESIDUAL_VALIDATION_REQUIRED']
FIELDS = ('schema','environment','lab_id','account','region','az','operator_cidr','sql_ami',
          'ssh_key_name','sql_profile','execution_role','task_role','kms_key','sa_secret',
          'app_secret','connection_secret','image')
# These AWS resources have no independent tag surface. Attribute them through
# exact parent IDs in the same local state, never invented tags or name prefixes.
UNTAGGED = {
    'aws_route.egress': dict(route_table_id='aws_route_table.lab',gateway_id='aws_internet_gateway.lab'),
    'aws_route_table_association.lab': dict(route_table_id='aws_route_table.lab',subnet_id='aws_subnet.lab'),
    'aws_security_group_rule.sql_egress': dict(security_group_id='aws_security_group.sql'),
    'aws_security_group_rule.app_egress': dict(security_group_id='aws_security_group.app'),
    'aws_security_group_rule.sql_from_app': dict(security_group_id='aws_security_group.sql',source_security_group_id='aws_security_group.app'),
    'aws_security_group_rule.operator_ssh': dict(security_group_id='aws_security_group.sql'),
    'aws_security_group_rule.app_tunnel': dict(security_group_id='aws_security_group.app',source_security_group_id='aws_security_group.sql'),
}


def require(ok, reason):
    if not ok: raise ValueError('E15S_LAB_REJECTED: '+reason)


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def decode(raw):
    require(type(raw) is bytes and len(raw)<=4194304, 'bounded JSON')
    def pairs(items):
        value={}
        for k,v in items:
            require(k not in value,'duplicate key');value[k]=v
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:require(False,'finite JSON'))


def select(value):
    require(type(value) is dict and set(value)==set(FIELDS), 'closed metadata-only configuration')
    require(value['schema']=='E15S_LAB_DRAFT_V1' and value['environment']=='lab', 'lab only; DEV/PROD/shared rejected')
    identity=str(uuid.UUID(value['lab_id']));require(identity==value['lab_id'],'canonical lab UUID')
    account,region=value['account'],value['region']
    require(type(account) is str and re.fullmatch('[0-9]{12}',account),'exact account')
    require(type(region) is str and re.fullmatch('[a-z]{2}(?:-[a-z]+)+-[0-9]',region),'exact region')
    require(type(value['az']) is str and re.fullmatch(re.escape(region)+'[a-z]',value['az']),'explicit single AZ')
    network=ipaddress.ip_network(value['operator_cidr'],strict=True)
    require(network.version==4 and network.prefixlen==32 and not network.is_unspecified and
            not network.network_address.is_multicast and not network.network_address.is_loopback,
            'one operator IPv4 address, never public CIDR range')
    require(re.fullmatch('ami-[0-9a-f]{17}',value['sql_ami']), 'explicit Ubuntu 22.04 amd64 AMI; no latest lookup')
    name='demo-lab-'+identity.replace('-','')
    require(value['ssh_key_name']==name+'-ssh','lab-only preinstalled SSH public-key identity')
    for field,suffix,kind in (('sql_profile','sql','instance-profile'),('execution_role','execution','role'),('task_role','task','role')):
        require(value[field]==f'arn:aws:iam::{account}:{kind}/{name}-{suffix}', 'exact lab role/profile; no protected identities')
    require(re.fullmatch(re.escape(f'arn:aws:kms:{region}:{account}:key/')+'[0-9a-f-]{36}',value['kms_key']), 'lab KMS key metadata')
    for field,label in (('sa_secret','sql-sa-password'),('app_secret','sql-app-password'),('connection_secret','db-connection-string')):
        require(re.fullmatch(re.escape(f'arn:aws:secretsmanager:{region}:{account}:secret:demo/lab/{identity}/{label}-')+'[A-Za-z0-9]{6}',value[field]),'lab-only secret metadata')
    require(re.fullmatch(re.escape(f'{account}.dkr.ecr.{region}.amazonaws.com/{name}@sha256:')+'[0-9a-f]{64}',value['image']), 'dedicated ECR immutable image; no protected WP3 repository')
    return dict(environment='lab',lab_id=identity,account=account,region=region,name=name,
        configuration_sha256=sha(canonical(value)),workspace='default',
        backend=dict(bucket=f'terragrunt-demo-lab-state-{account}-{region}',key=f'labs/{identity}/terraform.tfstate',region=region,use_lockfile=True))


def inventory(config):
    selected=select(config)
    return dict(deleted=['VPC/subnet/IGW/routes/security groups','Fargate service/task definitions/cluster',
        'SQL EC2 and encrypted root EBS (delete_on_termination)','lab application log group'],
        retained=['dedicated lab state bucket/versions/lock evidence','dedicated ECR image bytes (no GC decision)',
        'lab-only IAM roles/profile and SSH public key','lab-only KMS key until separately scheduled deletion',
        'lab-only secret metadata/values until separate administrative cleanup'],
        excluded=['protected DEV/PROD WP5 state and resources','neutral E1/WP3/WP4 control resources','shared infrastructure'],
        unknown_until_aws=['orphan tasks/ENIs/EBS/snapshots/public IPv4','failed or pending deletion','unexpected lab-owned resources'],
        cost_dimensions=['Fargate CPU/memory','SQL EC2/EBS/CPU credits','two in-use public IPv4 addresses',
                         'transfer/log ingestion','retained ECR/S3/secret/KMS storage and requests'],
        account=selected['account'],region=selected['region'],zero_cost_claim=False)


def composition(config):
    """Inert draft, not an admitted operational Terraform root.

    Terraform owns all lab runtime fields in this separate proposed state; no
    WP4/WP5 scripts, remote-state dependencies, NAT or automation installed.
    """
    s=select(config);name=s['name']
    tags=dict(Project='terragrunt-demo-lab',Environment='lab',LabId=s['lab_id'],ManagedBy='Terraform')
    resources={};add=lambda kind,label,value:resources.setdefault(kind,{}).update({label:value})
    add('terraform_data','installation_required',dict(lifecycle=dict(precondition=[dict(condition='${terraform.workspace == "default" && false}',
        error_message='E15S draft only: isolated backend/IAM/source admission and genuine readbacks are not installed.')])) )
    add('aws_vpc','lab',dict(cidr_block='10.77.0.0/16',enable_dns_support=True,enable_dns_hostnames=True,tags=dict(tags,Name=name)))
    add('aws_subnet','lab',dict(vpc_id='${aws_vpc.lab.id}',cidr_block='10.77.1.0/24',availability_zone=config['az'],
        map_public_ip_on_launch=False,tags=dict(tags,Name=name+'-public-egress')))
    add('aws_internet_gateway','lab',dict(vpc_id='${aws_vpc.lab.id}',tags=tags))
    add('aws_route_table','lab',dict(vpc_id='${aws_vpc.lab.id}',tags=tags))
    add('aws_route','egress',dict(route_table_id='${aws_route_table.lab.id}',destination_cidr_block='0.0.0.0/0',gateway_id='${aws_internet_gateway.lab.id}'))
    add('aws_route_table_association','lab',dict(subnet_id='${aws_subnet.lab.id}',route_table_id='${aws_route_table.lab.id}'))
    for duty in ('sql','app'):
        add('aws_security_group',duty,dict(name=name+'-'+duty,description='Isolated disposable lab '+duty,
            vpc_id='${aws_vpc.lab.id}',tags=tags))
        add('aws_security_group_rule',duty+'_egress',dict(type='egress',from_port=0,to_port=0,protocol='-1',
            cidr_blocks=['0.0.0.0/0'],security_group_id='${aws_security_group.'+duty+'.id}',description='AWS and package endpoints over public egress; no NAT'))
    add('aws_security_group_rule','sql_from_app',dict(type='ingress',from_port=1433,to_port=1433,protocol='tcp',
        source_security_group_id='${aws_security_group.app.id}',security_group_id='${aws_security_group.sql.id}',description='SQL only from lab task'))
    add('aws_security_group_rule','operator_ssh',dict(type='ingress',from_port=22,to_port=22,protocol='tcp',
        cidr_blocks=[config['operator_cidr']],security_group_id='${aws_security_group.sql.id}',description='Operator SSH tunnel only'))
    add('aws_security_group_rule','app_tunnel',dict(type='ingress',from_port=8080,to_port=8080,protocol='tcp',
        source_security_group_id='${aws_security_group.sql.id}',security_group_id='${aws_security_group.app.id}',description='API via authenticated SSH tunnel from SQL host'))
    # Reuse accepted SQL bootstrap bytes with metadata substitutions only.
    sql=(ROOT/'terraform/infra/data/user_data.sh').read_text(encoding='utf-8-sig').replace('\r\n','\n')
    for key,value in dict(AWS_REGION=config['region'],APP_DB='LabDemo',APP_USER='lab_app',SA_SECRET_ARN=config['sa_secret'],APP_SECRET_ARN=config['app_secret']).items():
        sql=sql.replace('${'+key+'}',value)
    sql=sql.replace('$${','${')  # Terraform-template escaping is unnecessary in literal API user_data.
    # Escape Terraform's JSON interpolation without changing shell expansion.
    sql=sql.replace('${','$${')
    add('aws_instance','sql',dict(ami=config['sql_ami'],instance_type='t3a.medium',subnet_id='${aws_subnet.lab.id}',
        vpc_security_group_ids=['${aws_security_group.sql.id}'],associate_public_ip_address=True,key_name=config['ssh_key_name'],
        iam_instance_profile=config['sql_profile'].split('/')[-1],metadata_options=dict(http_tokens='required',http_endpoint='enabled'),
        credit_specification=dict(cpu_credits='standard'),user_data=sql,
        root_block_device=dict(volume_type='gp3',volume_size=20,encrypted=True,delete_on_termination=True,tags=tags),
        tags=dict(tags,Name=name+'-sql'),depends_on=['aws_route.egress','aws_route_table_association.lab']))
    add('aws_cloudwatch_log_group','app',dict(name='/demo/lab/'+s['lab_id']+'/app',retention_in_days=1,tags=tags))
    add('aws_ecs_cluster','lab',dict(name=name,setting=[dict(name='containerInsights',value='disabled')],tags=tags))
    task=decode((ROOT/'demo-api/deploy/task-definition.template.json').read_bytes())
    task.update(family=name,executionRoleArn=config['execution_role'],taskRoleArn=config['task_role'])
    for index,container in enumerate(task['containerDefinitions']):
        container.update(name='app' if index==0 else 'ready',image=config['image'])
        container['logConfiguration']['options'].update({'awslogs-group':'${aws_cloudwatch_log_group.app.name}',
            'awslogs-region':s['region'],'awslogs-stream-prefix':'lab'})
    app=task['containerDefinitions'][0]
    for item in app['environment']:
        item['value']={'AWS_REGION':s['region'],'APP_ENV':'lab','DEPLOYMENT':'single','KMS_KEY_ID':config['kms_key']}[item['name']]
    app['environment'].append(dict(name='ASPNETCORE_ENVIRONMENT',value='Production'))
    app['secrets'][0]['valueFrom']=config['connection_secret']
    add('aws_ecs_task_definition','app',dict(family=name,network_mode='awsvpc',requires_compatibilities=['FARGATE'],
        cpu=task['cpu'],memory=task['memory'],execution_role_arn=config['execution_role'],task_role_arn=config['task_role'],
        runtime_platform=dict(cpu_architecture='X86_64',operating_system_family='LINUX'),
        container_definitions=json.dumps(task['containerDefinitions'],separators=(',',':')),tags=tags))
    add('aws_ecs_service','app',dict(name=name,cluster='${aws_ecs_cluster.lab.id}',task_definition='${aws_ecs_task_definition.app.arn}',
        desired_count=0,launch_type='FARGATE',platform_version='1.4.0',
        deployment_minimum_healthy_percent=0,deployment_maximum_percent=100,
        deployment_circuit_breaker=dict(enable=True,rollback=False),propagate_tags='SERVICE',tags=tags,
        network_configuration=dict(subnets=['${aws_subnet.lab.id}'],security_groups=['${aws_security_group.app.id}'],assign_public_ip=True),
        depends_on=['aws_instance.sql','aws_route.egress','aws_route_table_association.lab']))
    return dict(terraform=dict(required_version='= 1.13.4',required_providers=dict(aws=dict(source='hashicorp/aws',version='= 5.100.0')),
        backend=dict(s3=s['backend'])),provider=dict(aws=dict(region=s['region'],allowed_account_ids=[s['account']],default_tags=dict(tags=tags))),
        resource=resources,output=dict(sql_private_ip=dict(value='${aws_instance.sql.private_ip}'),
        sql_tunnel_host=dict(value='${aws_instance.sql.public_ip}'),cluster=dict(value='${aws_ecs_cluster.lab.name}')))


def ownership(snapshot, selected):
    """Structural local review only. Live origin/authenticity remains unproved."""
    require(type(snapshot) is dict and set(snapshot)=={'lineage','serial','backend','workspace','resources'},'closed state identity')
    require(type(snapshot['serial']) is int and snapshot['serial']>=0,'state serial')
    require(str(uuid.UUID(snapshot['lineage']))==snapshot['lineage'],'state lineage')
    require(snapshot['backend']==selected['backend'] and snapshot['workspace']=='default','exact isolated backend; never WP5')
    require(type(snapshot['resources']) is list,'complete local state resource inventory')
    expected=set(composition_address_names());seen=set()
    for row in snapshot['resources']:
        require(type(row) is dict and set(row)=={'address','id','tags'},'resource identity')
        require(row['address'] in expected and row['address'] not in seen,'closed lab-owned addresses; no module/import/controller')
        seen.add(row['address'])
        require(type(row['id']) is str and bool(row['id']),'resource ID')
        if row['address'] in UNTAGGED or row['address']=='terraform_data.installation_required':
            require(row['tags']=={},'untaggable resources have no fabricated tag evidence')
        else:
            require(all(row['tags'].get(k)==v for k,v in dict(Environment='lab',Project='terragrunt-demo-lab',LabId=selected['lab_id'],ManagedBy='Terraform').items()),'lab attribution; fresh AWS verification still required')
    return seen


def composition_address_names():
    # Matches only this draft graph; never arbitrary Terraform selectors.
    return ['terraform_data.installation_required']+[kind+'.'+label for kind,labels in {
        'aws_vpc':['lab'],'aws_subnet':['lab'],'aws_internet_gateway':['lab'],'aws_route_table':['lab'],'aws_route':['egress'],
        'aws_route_table_association':['lab'],'aws_security_group':['sql','app'],
        'aws_security_group_rule':['sql_egress','app_egress','sql_from_app','operator_ssh','app_tunnel'],
        'aws_instance':['sql'],'aws_cloudwatch_log_group':['app'],'aws_ecs_cluster':['lab'],
        'aws_ecs_task_definition':['app'],'aws_ecs_service':['app']}.items() for label in labels]


def review(config,binary,plan,context,state):
    selected=select(config);owned=ownership(state,selected)
    require(type(binary) is bytes and 0<len(binary)<=16777216,'bounded saved binary plan')
    require(type(context) is dict and set(context)=={'configuration_sha256','binary_sha256','json_sha256','state_sha256'},'closed local plan context')
    require(context==dict(configuration_sha256=selected['configuration_sha256'],binary_sha256=sha(binary),
        json_sha256=sha(canonical(plan)),state_sha256=sha(canonical(state))), 'exact supplied plan/context/state binding')
    require(type(plan) is dict and plan.get('format_version')=='1.2' and plan.get('errored') is False and
            plan.get('complete') is True and plan.get('applyable') is True and plan.get('deferred_changes',[])==[], 'complete applicable supplied plan')
    changes=plan.get('resource_changes');require(type(changes) is list and bool(changes),'nonempty exact destroy changes')
    addresses=[]
    for item in changes:
        require(item.get('mode')=='managed' and item.get('address') in owned and 'deposed' not in item,'no foreign/import/deposed object')
        require(item.get('change',{}).get('actions')==['delete'],'destroy only; no create/update/read/no-op')
        before=item['change'].get('before');require(type(before) is dict,'attributable prior resource')
        retained=next(row for row in state['resources'] if row['address']==item['address'])
        require(before.get('id')==retained['id'],'same state resource ID')
        if item['address'] in UNTAGGED:
            require(not before.get('tags'),'no fabricated route/association/rule tags')
            ids={row['address']:row['id'] for row in state['resources']}
            for field,parent in UNTAGGED[item['address']].items():
                require(parent in ids and before.get(field)==ids[parent],'untaggable object belongs to exact tagged lab parent')
        elif item['address']!='terraform_data.installation_required':
            require(before.get('tags')==retained['tags'],'same lab ownership tags')
        addresses.append(item['address'])
    require(len(set(addresses))==len(addresses) and set(addresses)==owned,'every state resource accounted; no filtering')
    return dict(binary_sha256=sha(binary),configuration_sha256=selected['configuration_sha256'],
        state_lineage=state['lineage'],state_serial=state['serial'],addresses=sorted(addresses),
        destroy_confirmation='DESTROY LAB '+selected['account']+' '+selected['region']+' '+selected['lab_id']+' '+sha(binary),
        sql_confirmation='PERMANENTLY LOSE LAB SQL '+selected['lab_id']+' '+sha(binary),
        provenance='UNTRUSTED_LOCAL_INPUTS_NOT_INSTALLED_APPROVAL',execution_authorized=False)


def report(action,config,notes=None,reviewed=None,confirm=None,sql_confirm=None):
    selected=select(config)
    require(action in ('status','up','verify','down','residual'),'closed lab command')
    value=dict(schema='E15S_LAB_REPORT_V1',action=action,scope=selected,classification='PARTIALLY_READY',
        execution_authorized=False,aws_verified=False,blockers=BLOCKERS,resources=inventory(config),
        up_order=['review isolated single-state plan (tasks=0)','provision SQL/network/cluster after future admission',
                  'administrator seed lab-only secret values outside state','build/test/publish dedicated immutable app image',
                  'review separate same-state task_count=1 plan','verify exact task /ready, SQL and KMS through operator tunnel'],
        down_order=['review same-state saved destroy plan','confirm destruction','independently confirm SQL loss',
                    'future admitted apply of the SAME saved plan','inspect task/instance termination and state','AWS residual inventory'],
        failure='STOP; preserve state and saved plan/logs privately; no blind retry; resources may still be billable',
        clean='not implemented: retained administrative dependencies and orphan checks require authorized AWS evidence')
    if action=='up':
        expected='PREPARE LAB '+selected['account']+' '+selected['region']+' '+selected['lab_id']
        require(confirm==expected,'explicit infrastructure preparation confirmation: '+expected)
        value['stage']='LOCAL_DRAFT_PREPARED_NOT_PROVISIONED'
    if action=='down':
        require(type(reviewed) is dict and reviewed.get('configuration_sha256') == selected['configuration_sha256'] and
                reviewed.get('execution_authorized') is False and reviewed.get('provenance') ==
                'UNTRUSTED_LOCAL_INPUTS_NOT_INSTALLED_APPROVAL','same lab/config supplied plan review required')
        require(confirm==reviewed['destroy_confirmation'],'exact destruction confirmation')
        require(sql_confirm==reviewed['sql_confirmation'],'independent irreversible SQL data loss confirmation')
        value['review']=reviewed;value['stage']='LOCAL_DESTROY_REVIEWED_NOT_EXECUTED'
    if action in ('verify','residual'):
        if notes is None:value['observations']='MISSING_UNKNOWN_POTENTIAL_COSTS'
        else:
            require(type(notes) is dict and set(notes)=={'scope','stage','resources','app_readiness'},'closed local operator notes')
            require(notes['scope']==selected,'no foreign notes')
            require(notes['stage'] in ('UP','DOWN','FAILED','UNKNOWN'),'honest stage')
            require(type(notes['resources']) is dict and bool(notes['resources']) and
                    all(v in ('PRESENT','ABSENT','UNKNOWN','RETAINED') for v in notes['resources'].values()),'explicit residuals')
            require(notes['app_readiness'] in ('OBSERVED_READY','FAILED','NOT_CHECKED'),'no synthetic readiness')
            value['observations']=dict(copy.deepcopy(notes),provenance='UNTRUSTED_LOCAL_NOTES',
                                      possible_charges=True)
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','up','verify','down','residual'))
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--output',type=Path,help='up only: new local inert draft directory, outside the repository')
    parser.add_argument('--notes',type=Path)
    parser.add_argument('--binary',type=Path);parser.add_argument('--plan-json',type=Path)
    parser.add_argument('--plan-context',type=Path);parser.add_argument('--state-notes',type=Path)
    parser.add_argument('--confirm');parser.add_argument('--confirm-sql-loss')
    args=parser.parse_args(argv);config=decode(args.config.read_bytes())
    reviewed=None
    if args.action=='down':
        require(all((args.binary,args.plan_json,args.plan_context,args.state_notes)),'binary/JSON/context/state inventory required')
        require(args.binary.is_file() and not args.binary.is_symlink() and args.binary.stat().st_size<=16777216,'bounded private plan')
        reviewed=review(config,args.binary.read_bytes(),decode(args.plan_json.read_bytes()),
                        decode(args.plan_context.read_bytes()),decode(args.state_notes.read_bytes()))
    else:require(not any((args.binary,args.plan_json,args.plan_context,args.state_notes,args.confirm_sql_loss)),'destroy arguments only for down')
    value=report(args.action,config,decode(args.notes.read_bytes()) if args.notes else None,reviewed,args.confirm,args.confirm_sql_loss)
    if args.output is not None:
        require(args.action=='up','draft output only during up preparation')
        output=args.output.resolve()
        require(output!=ROOT and ROOT not in output.parents and not output.exists(),'new output outside protected repository')
        output.mkdir(parents=True)
        (output/'lab.draft.json').write_bytes(canonical(composition(config)))
        (output/'review.json').write_bytes(canonical(value))
        value['draft']=str(output/'lab.draft.json')
    print(json.dumps(value,indent=2));return 0
