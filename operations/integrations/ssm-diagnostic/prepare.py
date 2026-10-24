#!/usr/bin/env python3
"""Single offline diagnostic packet renderer. No deployment/execution command."""
import argparse,base64,copy,gzip,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
A='341936017254';REG='us-east-1';RUN='ecs-sentinel-ssmdiag-r20261024d1'
OP=f'arn:aws:iam::{A}:role/TerragruntDemoDevOperator';ROLE=f'arn:aws:iam::{A}:role/{RUN}-node';BOUND=f'arn:aws:iam::{A}:policy/{RUN}-node-boundary'
PROFILE=f'arn:aws:iam::{A}:instance-profile/{RUN}-node';DOC=f'arn:aws:ssm:{REG}:{A}:document/{RUN}-observer-control'
GROUP='/ecs/ssm-diagnostic/'+RUN;LOG=f'arn:aws:logs:{REG}:{A}:log-group:{GROUP}'
AMI='ami-0d6e34c14757a048b';EBS=f'arn:aws:kms:{REG}:{A}:key/585f0833-6a1c-465d-ab40-a6c8278cae39'
BUCKET=f'e1-lifecycle-dev-{A}-{REG}';KEY=f'ssm-diagnostic/{RUN}/runtime/terraform.tfstate';EXP='${var.expires_at}'
TAGS={'Project':'EcsBackupSentinel','Environment':'Sandbox','Owner':'Kendall04','Trial':RUN,'Purpose':'SsmDiagnosticOnly'}
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def allow(actions,resources,condition=None):return {'Effect':'Allow','Action':actions,'Resource':resources,**({'Condition':condition} if condition else {})}
def cond(region=True):return {**({'StringEquals':{'aws:RequestedRegion':REG}} if region else {}),'DateLessThan':{'aws:CurrentTime':EXP}}
def policy(st):return {'Version':'2012-10-17','Statement':st}
def node_policy():
    c=cond();tag=cond();tag['StringEquals']['ssm:resourceTag/Trial']=RUN
    return policy([allow(['sts:GetCallerIdentity'],['*'],c),allow(['ssmmessages:'+s for s in ['CreateControlChannel','CreateDataChannel','OpenControlChannel','OpenDataChannel']],['*'],c),allow(['ssm:GetDocument','ssm:DescribeDocument'],[DOC],c),allow(['ssm:UpdateInstanceInformation'],[f'arn:aws:ec2:{REG}:{A}:instance/*'],tag),allow(['logs:CreateLogStream','logs:PutLogEvents'],[LOG+':log-stream:*'],c),allow(['logs:CreateLogGroup','logs:DescribeLogStreams'],[LOG,LOG+':*'],c),allow(['logs:DescribeLogGroups'],['*'],c)])
def operator_policy(instance='__VERIFIED_INSTANCE_ID__'):
    if instance!='__VERIFIED_INSTANCE_ID__' and not re.fullmatch('i-[0-9a-f]{17}',instance):raise ValueError('INSTANCE_ID')
    ar=lambda t:f'arn:aws:ec2:{REG}:{A}:{t}/*';st=[]
    creates={'CreateVpc':'vpc','CreateSubnet':'subnet','CreateSecurityGroup':'security-group','CreateInternetGateway':'internet-gateway','CreateRouteTable':'route-table'}
    c=cond();c['StringEquals']['aws:RequestTag/Trial']=RUN;st.append(allow(['ec2:'+a for a in creates],[ar(t) for t in creates.values()],c))
    c=cond();c['StringEquals']['aws:ResourceTag/Trial']=RUN;st.append(allow(['ec2:CreateSubnet','ec2:CreateSecurityGroup','ec2:CreateRouteTable'],[ar('vpc')],c))
    st.append(allow(['ec2:'+s for s in ['ModifyVpcAttribute','DeleteVpc','ModifySubnetAttribute','DeleteSubnet','AttachInternetGateway','DetachInternetGateway','DeleteInternetGateway','DeleteRouteTable','AssociateRouteTable','DisassociateRouteTable','CreateRoute','DeleteRoute','ReplaceRoute','DeleteSecurityGroup','AuthorizeSecurityGroupEgress','RevokeSecurityGroupEgress','CreateTags','DeleteTags','TerminateInstances','ModifyInstanceCreditSpecification']], [ar(t) for t in ['vpc','subnet','internet-gateway','route-table','security-group','instance','volume','network-interface']],c))
    c=cond();c['StringEquals'].update({'aws:RequestTag/Trial':RUN,'ec2:CreateAction':[*creates,'RunInstances']});st.append(allow(['ec2:CreateTags'],[ar(t) for t in ['vpc','subnet','internet-gateway','route-table','security-group','instance','volume','network-interface']],c))
    st.append(allow(['ec2:RunInstances'],[f'arn:aws:ec2:{REG}::image/{AMI}',ar('volume'),ar('network-interface')],cond()))
    c=cond();c['StringEquals']['aws:ResourceTag/Trial']=RUN;st.append(allow(['ec2:RunInstances'],[ar('subnet'),ar('security-group')],c))
    c=cond();c['StringEquals'].update({'aws:RequestTag/Trial':RUN,'ec2:InstanceType':'t3.micro','ec2:MetadataHttpTokens':'required'});c['ArnEquals']={'ec2:InstanceProfile':PROFILE};st.append(allow(['ec2:RunInstances'],[ar('instance')],c))
    c=cond(False);c['StringEquals']={'iam:PassedToService':'ec2.amazonaws.com'};st.append(allow(['iam:PassRole'],[ROLE],c))
    st.append(allow(['iam:GetRole','iam:ListInstanceProfilesForRole'],[ROLE],cond(False)));st.append(allow(['iam:GetInstanceProfile'],[PROFILE],cond(False)))
    reads=['DescribeVpcs','DescribeVpcAttribute','DescribeSubnets','DescribeSecurityGroups','DescribeSecurityGroupRules','DescribeInternetGateways','DescribeRouteTables','DescribeInstances','DescribeInstanceStatus','DescribeInstanceAttribute','DescribeInstanceCreditSpecifications','DescribeNetworkInterfaces','DescribeVolumes','DescribeImages','DescribeTags','DescribeAccountAttributes','DescribeAvailabilityZones']
    st.append(allow(['ec2:'+s for s in reads]+['ssm:GetCommandInvocation','ssm:ListCommands','ssm:ListCommandInvocations','ssm:DescribeInstanceInformation','logs:DescribeLogGroups','cloudtrail:LookupEvents'],['*'],cond()))
    st.append(allow(['ssm:'+s for s in ['CreateDocument','GetDocument','DescribeDocument','DescribeDocumentPermission','ListDocumentVersions','DeleteDocument','AddTagsToResource','RemoveTagsFromResource','ListTagsForResource']],[DOC],cond()))
    for via in ('false','true'):
        c=cond(via=='false');c['Bool']={'aws:ViaAWSService':via};st.append(allow(['ssm:SendCommand'],[DOC],c));t=copy.deepcopy(c)
        if via=='false':t['StringEquals']['ssm:resourceTag/Trial']=RUN
        st.append(allow(['ssm:SendCommand'],[f'arn:aws:ec2:{REG}:{A}:instance/{instance}'],t))
    st.append(allow(['ec2:GetConsoleOutput'],[f'arn:aws:ec2:{REG}:{A}:instance/{instance}'],cond()))
    st.append(allow(['logs:'+s for s in ['CreateLogGroup','PutRetentionPolicy','DeleteRetentionPolicy','DeleteLogGroup','ListTagsForResource','TagResource','UntagResource','DescribeLogStreams','GetLogEvents','FilterLogEvents']],[LOG,LOG+':*'],cond()))
    sb='arn:aws:s3:::'+BUCKET;st.append(allow(['s3:GetObject','s3:PutObject'],[sb+'/'+KEY,sb+'/'+KEY+'.tflock'],cond()));st.append(allow(['s3:DeleteObject'],[sb+'/'+KEY+'.tflock'],cond()))
    c=cond();c['StringLike']={'s3:prefix':[KEY+'*',f'ssm-diagnostic/{RUN}/runtime/workspaces/*']};st.append(allow(['s3:ListBucket'],[sb],c));st.append(allow(['s3:GetBucketLocation','s3:GetBucketVersioning','s3:GetEncryptionConfiguration'],[sb],cond()));st.append(allow(['kms:DescribeKey'],[EBS],cond()))
    return policy(st)
def document():return {'schemaVersion':'2.2','description':'New bounded SSM diagnostic, status only; no backup acceptance','parameters':{'Action':{'type':'String','default':'status','allowedValues':['status'],'allowedPattern':'^status$'}},'mainSteps':[{'action':'aws:runShellScript','name':'ObserverControl','inputs':{'timeoutSeconds':'30','runCommand':['/usr/bin/python3 -I -B /opt/terragrunt-demo/ssm-diagnostic/harness.py --action status']}}]}
def config():return {'terraform':{'required_version':'= 1.13.4','backend':{'s3':{}},'required_providers':{'aws':{'source':'hashicorp/aws','version':'= 6.27.0'}}},'provider':{'aws':{'region':REG,'allowed_account_ids':[A]}},'variable':{'expires_at':{'type':'string','description':'Reviewed admission T0+24h UTC, identical both states; no default','validation':[{'condition':'${can(formatdate("YYYY",var.expires_at)) && can(regex("Z$",var.expires_at))}','error_message':'Absolute UTC expiry required.'}]}}}
def backend(root):return {'bucket':BUCKET,'key':f'ssm-diagnostic/{RUN}/{root}/terraform.tfstate','region':REG,'encrypt':True,'use_lockfile':True,'workspace_key_prefix':f'ssm-diagnostic/{RUN}/{root}/workspaces'}
def bootstrap():
    x=config();x['resource']={'aws_iam_policy':{'boundary':{'name':RUN+'-node-boundary','policy':json.dumps(node_policy()),'tags':TAGS}},'aws_iam_role':{'node':{'name':RUN+'-node','assume_role_policy':json.dumps(policy([{'Effect':'Allow','Principal':{'Service':'ec2.amazonaws.com'},'Action':'sts:AssumeRole'}])),'permissions_boundary':'${aws_iam_policy.boundary.arn}','tags':TAGS}},'aws_iam_instance_profile':{'node':{'name':RUN+'-node','role':'${aws_iam_role.node.name}','tags':TAGS}},'aws_iam_role_policy':{'node':{'name':'SsmDiagnosticOnly','role':'${aws_iam_role.node.id}','policy':json.dumps(node_policy())}}};return x

def observer_source():
    import ast
    original=(HERE.parent/'observer_host.py').read_text(encoding='utf-8')
    tree=ast.parse(original)
    names={'BASE','STATE','MODES','UNIT','Refused','need','environment','validate','safe','host','system','service_busy','control'}
    selected=[]
    for node in tree.body:
        name=getattr(node,'name',None)
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name):name=node.targets[0].id
        if name in names:selected.append(ast.get_source_segment(original,node))
    if len(selected)!=len(names):raise ValueError('OBSERVER_STATUS_SOURCE_CHANGED')
    return ('# Exact status dependency subset from observer_host.py; no checker or installer.\nimport os,json,re,subprocess,datetime as dt\nfrom pathlib import Path\n'+'\n\n'.join(selected)+'\n').encode()

def boot_script():
    blobs={n:base64.b64encode((HERE/n).read_bytes().replace(b'\r\n',b'\n')).decode() for n in ['collector.py','harness.py']};original=observer_source();blobs['observer_host.py']=base64.b64encode(original).decode()
    cfg={'run':RUN,'account':A,'region':REG,'expires_at':None,'log_group':GROUP,'role':RUN+'-node','source_sha256':sha((HERE/'collector.py').read_bytes().replace(b'\r\n',b'\n'))}
    host={'account':A,'region':REG,'run_id':RUN,'subject':'diagnostic-only','bucket':'diagnostic-no-bucket','prefix':'unused/original','missing_prefix':'sentinel-observer/'+RUN+'/unused','backup_key_arn':f'arn:aws:kms:{REG}:{A}:key/00000000-0000-0000-0000-000000000001','text_key_arn':f'arn:aws:kms:{REG}:{A}:key/00000000-0000-0000-0000-000000000002','database':'diagnostic_only','max_age_hours':1,'expires_at':None,'cadence_seconds':60,'publish_attempts':1,'aws_cli':'/usr/bin/aws','uid':0}
    text='''#!/bin/bash
set -euo pipefail
umask 077
/usr/bin/python3 -I -B - <<'PY'
import base64,hashlib,json,os,pathlib,subprocess
binding=json.loads(base64.b64decode('${binding_base64}',validate=True))
base=pathlib.Path('/opt/terragrunt-demo/ssm-diagnostic')
base.mkdir(parents=True,mode=0o700,exist_ok=False)
'''
    text+='files='+repr(blobs)+'\n';text+='''for name,data in files.items():
    raw=base64.b64decode(data,validate=True)
    with (base/name).open('xb') as f:f.write(raw)
    os.chmod(base/name,0o600)
'''
    text+='cfg='+repr(cfg)+'\n'+'host='+repr(host)+'\n';text+="cfg['expires_at']=host['expires_at']=binding['expires_at']\n";text+='hc='+repr({'observerSha256':sha(original)})+'\n'
    text+='''for name,value in [('collector-config.json',cfg),('host.json',host),('harness-config.json',hc)]:
    with (base/name).open('x',encoding='utf-8') as f:json.dump(value,f)
    os.chmod(base/name,0o600)
(base/'state').mkdir(mode=0o700)
(base/'state/mode.json').write_text('{"mode":"missing"}',encoding='utf-8')
for executable in ['/usr/bin/aws','/usr/bin/amazon-ssm-agent','/usr/bin/systemctl','/usr/bin/python3','/usr/bin/systemd-run']:
    if not os.path.isfile(executable):raise SystemExit('AMI_TOOL_MISSING_NO_INSTALL')
env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
# No status invocation at boot. New command evidence must come from the owned document.
r=subprocess.run(['/usr/bin/systemd-run','--unit=ecs-ssmdiag-collector','--property=RuntimeMaxSec=7500','--property=UMask=0077','--property=SendSIGKILL=no','/usr/bin/python3','-I','-B',str(base/'collector.py'),'--execute'],env=env)
if r.returncode:raise SystemExit('COLLECTOR_START_UNCONFIRMED')
PY
'''
    if len(gzip.compress(text.encode(),mtime=0))>16384:raise ValueError('EC2_USER_DATA_BOUND')
    return text

def runtime():
    x=config();r={};x['resource']=r
    def add(t,n,v):r.setdefault(t,{})[n]=v|({'tags':TAGS} if t in ['aws_vpc','aws_subnet','aws_internet_gateway','aws_route_table','aws_security_group','aws_instance','aws_cloudwatch_log_group','aws_ssm_document'] else {})
    add('aws_vpc','diag',{'cidr_block':'10.249.0.0/24','enable_dns_support':True,'enable_dns_hostnames':True});add('aws_internet_gateway','diag',{'vpc_id':'${aws_vpc.diag.id}'})
    add('aws_subnet','diag',{'vpc_id':'${aws_vpc.diag.id}','cidr_block':'10.249.0.0/28','availability_zone':'us-east-1a','map_public_ip_on_launch':False});add('aws_route_table','diag',{'vpc_id':'${aws_vpc.diag.id}'})
    add('aws_route_table_association','diag',{'subnet_id':'${aws_subnet.diag.id}','route_table_id':'${aws_route_table.diag.id}'});add('aws_route','internet',{'route_table_id':'${aws_route_table.diag.id}','destination_cidr_block':'0.0.0.0/0','gateway_id':'${aws_internet_gateway.diag.id}'})
    add('aws_security_group','diag',{'name':RUN,'description':'Diagnostic HTTPS egress only; no ingress','vpc_id':'${aws_vpc.diag.id}','ingress':[],'egress':[{'from_port':443,'to_port':443,'protocol':'tcp','cidr_blocks':['0.0.0.0/0'],'ipv6_cidr_blocks':[],'prefix_list_ids':[],'security_groups':[],'self':False,'description':'AWS HTTPS endpoints by intended clients'}]})
    add('aws_cloudwatch_log_group','diag',{'name':GROUP,'retention_in_days':1,'log_group_class':'STANDARD','skip_destroy':False});add('aws_ssm_document','control',{'name':RUN+'-observer-control','document_type':'Command','document_format':'JSON','content':canonical(document())})
    add('aws_instance','node',{'ami':AMI,'instance_type':'t3.micro','subnet_id':'${aws_subnet.diag.id}','vpc_security_group_ids':['${aws_security_group.diag.id}'],'associate_public_ip_address':True,'iam_instance_profile':RUN+'-node','monitoring':False,'credit_specification':{'cpu_credits':'standard'},'metadata_options':{'http_endpoint':'enabled','http_tokens':'required','http_put_response_hop_limit':1,'instance_metadata_tags':'disabled'},'root_block_device':{'encrypted':True,'kms_key_id':EBS,'volume_type':'gp3','volume_size':8,'iops':3000,'throughput':125,'delete_on_termination':True,'tags':TAGS},'user_data_replace_on_change':True,'user_data_base64':'${base64gzip(templatefile("${path.module}/bootstrap.sh.tftpl",{binding_base64=base64encode(jsonencode({expires_at=var.expires_at}))}))}','depends_on':['aws_route.internet','aws_route_table_association.diag','aws_cloudwatch_log_group.diag','aws_ssm_document.control']})
    x['output']={'instance_id':{'value':'${aws_instance.node.id}'},'document_name':{'value':'${aws_ssm_document.control.name}'},'log_group':{'value':'${aws_cloudwatch_log_group.diag.name}'}};return x

def amend_backend(original):
    x=copy.deepcopy(original);sb='arn:aws:s3:::'+BUCKET;objs=[sb+'/'+KEY,sb+'/'+KEY+'.tflock'];found=set()
    for s in x['Statement']:
        if s.get('Sid')=='E16NoOtherDevObjects':s['NotResource']+=objs;found.add(s['Sid'])
        if s.get('Sid')=='E16RetainStateObjects':s['Resource'].append(objs[0]);found.add(s['Sid'])
    if found!={'E16NoOtherDevObjects','E16RetainStateObjects'}:raise ValueError('BASELINE_CHANGED')
    for sid,actions,res,extra in [('DiagStateReadWrite',['s3:GetObject','s3:PutObject'],objs,{}),('DiagLockDelete',['s3:DeleteObject'],[objs[1]],{}),('DiagList',['s3:ListBucket'],[sb],{'StringLike':{'s3:prefix':[KEY+'*',f'ssm-diagnostic/{RUN}/runtime/workspaces/*']}})]:x['Statement'].append({'Sid':sid,'Effect':'Allow','Principal':{'AWS':OP},'Action':actions,'Resource':res,'Condition':cond(False)|extra})
    return x

def build(output,baselines):
    if output.exists():raise ValueError('OUTPUT_MUST_BE_NEW')
    output.mkdir(parents=True)
    def save(name,value):
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n' if not isinstance(value,str) else value,encoding='utf-8')
    for k in ['part4','part7','backend']:save('originals/'+k+'.json',baselines[k])
    for name,x in [('bootstrap',bootstrap()),('runtime',runtime())]:
        save(name+'/main.tf.json',x);save(name+'/backend.s3.json',backend(name));save(name+'/.terraform.lock.hcl',(ROOT/'terraform/infra/sentinel-backup/.terraform.lock.hcl').read_text())
    save('runtime/bootstrap.sh.tftpl',boot_script());save('access/operator-template.NOT-INSTALLABLE.json',operator_policy());save('access/backend-template.NOT-INSTALLABLE.json',amend_backend(baselines['backend']));save('document.json',document());save('access/node-runtime.json',node_policy());save('send-command.template.NOT-EXECUTED.json',{'DocumentName':RUN+'-observer-control','DocumentVersion':'1','DocumentHash':'__NATIVE_DOCUMENT_HASH_SHA256__','DocumentHashType':'Sha256','InstanceIds':['__VERIFIED_INSTANCE_ID__'],'Parameters':{'Action':['status']},'TimeoutSeconds':60,'CloudWatchOutputConfig':{'CloudWatchLogGroupName':GROUP,'CloudWatchOutputEnabled':True},'MaxConcurrency':'1','MaxErrors':'0'})
    admin_actions=['CreatePolicy','GetPolicy','GetPolicyVersion','ListPolicyVersions','DeletePolicy','TagPolicy','UntagPolicy','ListPolicyTags','CreateRole','GetRole','DeleteRole','TagRole','UntagRole','ListRoleTags','ListRolePolicies','ListAttachedRolePolicies','ListInstanceProfilesForRole','PutRolePolicy','GetRolePolicy','DeleteRolePolicy','PutRolePermissionsBoundary','DeleteRolePermissionsBoundary','CreateInstanceProfile','GetInstanceProfile','DeleteInstanceProfile','AddRoleToInstanceProfile','RemoveRoleFromInstanceProfile','TagInstanceProfile','UntagInstanceProfile','ListInstanceProfileTags']
    save('access/admin-required-scope.json',policy([allow(['iam:'+a for a in admin_actions],[ROLE,BOUND,PROFILE],cond(False)),allow(['iam:PutRolePolicy','iam:GetRolePolicy','iam:DeleteRolePolicy','iam:ListRolePolicies'],[OP],cond(False)),allow(['iam:PassRole'],[ROLE],cond(False)|{'StringEquals':{'iam:PassedToService':'ec2.amazonaws.com'}}),allow(['s3:GetBucketPolicy','s3:PutBucketPolicy','s3:GetBucketLocation','s3:GetBucketVersioning','s3:GetEncryptionConfiguration'],['arn:aws:s3:::'+BUCKET],cond(False)),allow(['s3:GetObject','s3:PutObject'],['arn:aws:s3:::'+BUCKET+'/'+f'ssm-diagnostic/{RUN}/bootstrap/terraform.tfstate','arn:aws:s3:::'+BUCKET+'/'+f'ssm-diagnostic/{RUN}/bootstrap/terraform.tfstate.tflock'],cond(False)),allow(['s3:DeleteObject'],['arn:aws:s3:::'+BUCKET+'/'+f'ssm-diagnostic/{RUN}/bootstrap/terraform.tfstate.tflock'],cond(False)),allow(['s3:ListBucket'],['arn:aws:s3:::'+BUCKET],cond(False)|{'StringLike':{'s3:prefix':[f'ssm-diagnostic/{RUN}/bootstrap/*']}})]))
    total=round(5.5*(0.05+0.005+8*0.10/720)+0.65,6)
    save('cost.json',{'Status':'PROPOSED_NEW_BUDGET_NOT_APPROVED','UsdCeiling':1,'BaseRates':{'Ec2LinuxT3MicroPerHour':0.0104,'PublicIpv4PerHour':0.005,'Gp3GbMonthIllustrativeUpper':0.10},'ConservativeEc2PerHour':0.05,'PaidHoursIncludingCleanupReserve':5.5,'ComputeIpv4DiskConservativeUsd':round(total-0.65,6),'LogsStorageExportReserveUsd':0.15,'TransferReserveUsd':0.05,'BackendRequestsStatePreservationReserveUsd':0.05,'UncertaintyReserveUsd':0.40,'TotalConservativeUsd':total,'ObjectiveHours':2,'StopTestsByPaidHour':4,'CleanupReserveHours':1.5,'AbsoluteCeilingHours':24,'NoFreeTierCreditOrAutomaticCap':True,'LogBytesHardLimit':2097152,'NoSnapshotsNatSqlSnsCustomMetricsOrLogInsights':True,'Sources':['https://aws.amazon.com/ec2/instance-types/t3/','https://aws.amazon.com/vpc/pricing/','https://aws.amazon.com/ebs/pricing/','https://aws.amazon.com/cloudwatch/pricing/','https://aws.amazon.com/systems-manager/pricing/']})
    inventory=[{'Owner':owner,'Address':t+'.'+n} for owner,x in [('cnp-cert-admin',bootstrap()),('TerragruntDemoDevOperator',runtime())] for t,rs in x['resource'].items() for n in rs]
    save('inventory.json',{'Classification':'EXPECTED_CONTRACT_NOT_NATIVE_SAVED_PLAN','PrimaryResources':inventory,'Count':len(inventory),'Implicit':['root volume','primary ENI','temporary public IPv4','VPC default route table/security group/network ACL'],'AccessDeltas':['temporary operator inline SsmDiagnosticr20261024d1','exact runtime backend state/lock exception'],'Part4AndPart7':'UNCHANGED','BackupKmsOrBucketChanges':False,'SessionManagerEnabled':False})
    manifest={'Status':'LOCAL_REVIEW_PACKET_NOT_APPROVED','Run':RUN,'CloudExecuted':False,'RequiresAdmissionReadbacksAndActualSavedPlans':True,'DocumentCanonicalSha256':sha(canonical(document()).encode()),'ObserverOriginalLfSha256':sha((HERE.parent/'observer_host.py').read_bytes().replace(b'\r\n',b'\n')),'ObserverSubsetSha256':sha(observer_source()),'CompressedUserDataBytes':len(gzip.compress(boot_script().encode(),mtime=0)),'OperatorTemplateChars':len(canonical(operator_policy())),'OriginalCanonicalSha256':{k:sha(canonical(v).encode()) for k,v in baselines.items()},'FilesSha256Lf':{p.relative_to(output).as_posix():sha(p.read_bytes().replace(b'\r\n',b'\n')) for p in output.rglob('*') if p.is_file()}}
    if manifest['OperatorTemplateChars']>10240:raise ValueError('OPERATOR_INLINE_QUOTA')
    save('manifest.json',manifest);return manifest

def bind_instance(value,expiry):
    keys={'Account','Region','InstanceId','ImageId','State','Trial','ProfileArn','LaunchTime','ObservedUtc'}
    if set(value)!=keys or value['Account']!=A or value['Region']!=REG or value['ImageId']!=AMI or value['State']!='running' or value['Trial']!=RUN or value['ProfileArn']!=PROFILE:raise ValueError('INSTANCE_BINDING')
    import datetime as dt
    parse=lambda v:dt.datetime.fromisoformat(v.replace('Z','+00:00'));launch,observed,end=map(parse,[value['LaunchTime'],value['ObservedUtc'],expiry])
    if not all(x.tzinfo for x in [launch,observed,end]) or not launch<=observed<end or end-launch>dt.timedelta(hours=24):raise ValueError('INSTANCE_WINDOW')
    return {'Status':'BOUND_POLICY_REQUIRES_NATIVE_REVIEW','EvidenceAuthenticated':False,'Policy':json.loads(json.dumps(operator_policy(value['InstanceId'])).replace(EXP,expiry))}
def review_saved_plan(plan,root,phase,registry=None):
    """Small trial-only change guard, not a general executor or authorization proof."""
    if root not in ('bootstrap','runtime') or phase not in ('create','delete'):raise ValueError('PLAN_SCOPE')
    x=bootstrap() if root=='bootstrap' else runtime()
    expected={t+'.'+n for t,rs in x['resource'].items() for n in rs}
    changes=[v for v in plan.get('resource_changes',[]) if v.get('mode','managed')=='managed']
    addresses=[v['address'] for v in changes]
    if len(addresses)!=len(set(addresses)) or not changes or not set(addresses)<=expected:raise ValueError('FOREIGN_OR_EMPTY_PLAN')
    if phase=='create' and set(addresses)!=expected:raise ValueError('INCOMPLETE_CREATE')
    for v in changes:
        if v['change']['actions']!=['create' if phase=='create' else 'delete']:raise ValueError('REPLACEMENT_OR_UPDATE_REFUSED')
        if phase=='delete':
            if not registry or v['address'] not in registry or v['change']['before'].get('id')!=registry[v['address']]:raise ValueError('GENERATION_CHANGED')
    return {'Status':'DIAGNOSTIC_PLAN_SCOPE_ONLY','Count':len(changes),'AllowsExecution':False,'EvidenceAuthenticated':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);a=p.parse_args();originals={k:json.loads((a.baseline/(k+'.json')).read_text(encoding='utf-8')) for k in ['part4','part7','backend']};print(json.dumps(build(a.output,originals),indent=2))
