"""Offline ECS trial CloudFormation/policy renderer. No AWS SDK, CLI or network calls."""
import argparse,copy,hashlib,json,re,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
# SNS resource policies accept this service-specific action set, not arbitrary IAM actions.
# https://docs.aws.amazon.com/sns/latest/dg/sns-access-policy-language-api-permissions-reference.html
SNS_TOPIC_POLICY_ACTIONS=['sns:AddPermission', 'sns:DeleteTopic', 'sns:GetDataProtectionPolicy', 'sns:GetTopicAttributes', 'sns:ListSubscriptionsByTopic', 'sns:ListTagsForResource', 'sns:Publish', 'sns:PutDataProtectionPolicy', 'sns:RemovePermission', 'sns:SetTopicAttributes', 'sns:Subscribe']
ref=lambda n:{'Ref':n}
get=lambda n:{'Fn::GetAtt':[n,'Arn']}
policy=lambda statements:{'Version':'2012-10-17','Statement':statements}
def allow(actions,resources,condition=None):
 s={'Effect':'Allow','Action':actions,'Resource':resources}
 if condition:s['Condition']=condition
 return s
def build(scope,source,package_sha=None):
 run=scope['runId'];account=scope['account'];region=scope['region'];b=scope['bindings'];names=scope['resourceNames']
 if not re.fullmatch(r'ecs-sentinel-[a-z0-9-]{1,24}',run) or not re.fullmatch(r'\d{12}',account) or not re.fullmatch(r'[a-z]{2}-[a-z]+-\d',region):raise ValueError('Invalid trial identity')
 operator=f'arn:aws:iam::{account}:role/TerragruntDemoDevOperator'
 arn=lambda svc,tail:f'arn:aws:{svc}:{region}:{account}:{tail}'
 role=lambda suffix:f'arn:aws:iam::{account}:role/{run}-{suffix}'
 boundary=lambda suffix:f'arn:aws:iam::{account}:policy/{run}-{suffix}-boundary'
 table=arn('dynamodb','table/'+run);bucket='arn:aws:s3:::'+b['archiveBucket'];topic=arn('sns',run+'-notices');queues=[b['queueArn'],arn('sqs',run+'-dlq')]
 funcs=[arn('lambda','function:'+run+'-'+x) for x in ['ingest','dispatch']]
 logs=[arn('logs','log-group:/aws/lambda/'+run+'-'+x) for x in ['ingest','dispatch']]
 ns={'ForAllValues:StringEquals':{'dynamodb:LeadingKeys':[b['dynamoNamespace']]},'Null':{'dynamodb:LeadingKeys':'false'}}
 ddb=allow(['dynamodb:GetItem','dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:DeleteItem','dynamodb:ConditionCheckItem'],table,ns)
 runtime={
  'ingest':policy([ddb,allow(['sqs:ReceiveMessage','sqs:DeleteMessage','sqs:GetQueueAttributes'],queues[0]),allow(['logs:CreateLogStream','logs:PutLogEvents'],logs[0]+':log-stream:*')]),
  'dispatch':policy([ddb,allow(['s3:GetObject','s3:PutObject'],bucket+'/'+b['archivePrefix']+'/*'),allow(['sns:Publish'],topic),allow(['logs:CreateLogStream','logs:PutLogEvents'],logs[1]+':log-stream:*')])}
 tags=[{'Key':k,'Value':v} for k,v in {'Project':'EcsBackupSentinel','Environment':'Sandbox','Owner':'Kendall04','RunId':run,'Purpose':'SyntheticSignalTrial'}.items()]
 # Reuse the original reviewed table/index and private archive definitions, not a parallel store.
 original=json.loads((source/'tools/aws-sandbox/cloudformation.json').read_text(encoding='utf-8'))['Resources']
 resources={n:copy.deepcopy(original[n]) for n in ['Sentinel','Archive']}
 resources['Sentinel']['Properties'].update(TableName=run,Tags=tags)
 resources['Archive']['Properties'].update(BucketName=b['archiveBucket'],Tags=tags,VersioningConfiguration={'Status':'Enabled'})
 for name in ['Sentinel','Archive']:resources[name].update(DeletionPolicy='Retain',UpdateReplacePolicy='Retain')
 params={
  'NotificationEmail':{'Type':'String','AllowedPattern':r'[^\s@]+@[^\s@]+\.[^\s@]+','NoEcho':True,'Description':'Owner supplied/consented email; confirmation is performed by the owner.'},
  'SenderLabel':{'Type':'String','AllowedPattern':r'[a-zA-Z0-9 ._-]{1,40}','Description':'Subject/body label; SNS controls the actual From address.'},
  'NotificationMode':{'Type':'String','AllowedValues':['EscalationOnly','EscalationAndRecovery']},
  'Owner':{'Type':'String','AllowedPattern':r'[a-zA-Z0-9._-]{1,64}'},
  'StartsAt':{'Type':'String','AllowedPattern':r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'},
  'ExpiresAt':{'Type':'String','AllowedPattern':r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'},
  'DeployRuntime':{'Type':'String','AllowedValues':['false','true'],'Default':'false','Description':'Base stack first; runtime only after immutable package upload/version receipt.'},
  'PackageKey':{'Type':'String','AllowedPattern':r'packages/[a-f0-9]{64}\.zip'},
  'PackageVersion':{'Type':'String','MinLength':1},
  'LogRetentionDays':{'Type':'Number','AllowedValues':[1,3,5,7,14,30]},
  'QueueRetentionSeconds':{'Type':'Number','MinValue':60,'MaxValue':1209600},
  'DlqRetentionSeconds':{'Type':'Number','MinValue':60,'MaxValue':1209600}}
 for name in ['EvidenceSeconds','BudgetSeconds','CheckSeconds','HoldSeconds','DedupSeconds','SignalAgeSeconds','AuditSeconds','EffectSeconds']:
  params[name]={'Type':'Number','MinValue':0 if name=='HoldSeconds' else 1,'MaxValue':2592000}
 bound={'Fn::And':[{'Fn::Equals':[ref('AWS::AccountId'),account]},{'Fn::Equals':[ref('AWS::Region'),region]}]}
 if package_sha is not None:
  if not re.fullmatch(r'[a-f0-9]{64}',package_sha):raise ValueError('Invalid package SHA256')
  params['PackageKey'].update(AllowedValues=['packages/'+package_sha+'.zip'],Default='packages/'+package_sha+'.zip')
 params['PackageVersion']['Default']='BASE_ONLY_UNPUBLISHED'
 conditions={'BoundEnvironment':bound,'WithRuntime':{'Fn::And':[{'Condition':'BoundEnvironment'},{'Fn::Equals':[ref('DeployRuntime'),'true']}]}}
 env={'SENTINEL_MODE':'synthetic-trial','SENTINEL_RUN_ID':run,'SENTINEL_ACCOUNT':account,'SENTINEL_REGION':region,'SENTINEL_PROJECT':b['project'],
  'SENTINEL_CONSUMER':b['consumer'],'SENTINEL_SUBJECT':b['subject'],'SENTINEL_SERVICE':b['correlationKey']['service'],'SENTINEL_SCOPE':b['correlationKey']['scope'],
  'SENTINEL_FAILURE_SIGNATURE':b['correlationKey']['failureSignature'],'SENTINEL_QUEUE_ARN':b['queueArn'],'SENTINEL_TABLE':run,'SENTINEL_BUCKET':b['archiveBucket'],
  'SENTINEL_NAMESPACE':b['dynamoNamespace'],'SENTINEL_ARCHIVE_PREFIX':b['archivePrefix'],'SENTINEL_TOPIC_ARN':topic}
 for name,key in {'Owner':'OWNER','EvidenceSeconds':'EVIDENCE_SECONDS','BudgetSeconds':'BUDGET_SECONDS','CheckSeconds':'CHECK_SECONDS','HoldSeconds':'HOLD_SECONDS',
  'DedupSeconds':'DEDUP_SECONDS','SignalAgeSeconds':'SIGNAL_AGE_SECONDS','AuditSeconds':'AUDIT_SECONDS','EffectSeconds':'EFFECT_SECONDS','SenderLabel':'SENDER_LABEL',
  'NotificationMode':'NOTIFICATION_MODE','StartsAt':'STARTS_AT','ExpiresAt':'EXPIRES_AT'}.items():env['SENTINEL_'+key]=ref(name)
 resources['ArchivePolicy']={'Type':'AWS::S3::BucketPolicy','Properties':{'Bucket':ref('Archive'),'PolicyDocument':policy([
  {'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[bucket,bucket+'/*'],'Condition':{'Bool':{'aws:SecureTransport':'false','aws:PrincipalIsAWSService':'false'}}},
  {'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[bucket,bucket+'/*'],'Condition':{'ArnNotEquals':{'aws:PrincipalArn':[operator,role('cfn'),role('dispatch-role')]},'Bool':{'aws:PrincipalIsAWSService':'false'}}}])}}
 resources['Dlq']={'Type':'AWS::SQS::Queue','Properties':{'QueueName':run+'-dlq','MessageRetentionPeriod':ref('DlqRetentionSeconds'),'SqsManagedSseEnabled':True,'Tags':tags,
  'RedriveAllowPolicy':{'redrivePermission':'byQueue','sourceQueueArns':[queues[0]]}}}
 resources['Queue']={'Type':'AWS::SQS::Queue','Properties':{'QueueName':run+'-ingestion','VisibilityTimeout':90,'ReceiveMessageWaitTimeSeconds':20,
  'MessageRetentionPeriod':ref('QueueRetentionSeconds'),'SqsManagedSseEnabled':True,'Tags':tags,'RedrivePolicy':{'deadLetterTargetArn':get('Dlq'),'maxReceiveCount':5}}}
 resources['QueuePolicy']={'Type':'AWS::SQS::QueuePolicy','Properties':{'Queues':[ref('Queue'),ref('Dlq')],'PolicyDocument':policy([
  {'Effect':'Deny','Principal':'*','Action':'sqs:*','Resource':queues,'Condition':{'Bool':{'aws:SecureTransport':'false','aws:PrincipalIsAWSService':'false'}}},
  {'Effect':'Deny','Principal':'*','Action':'sqs:*','Resource':queues,'Condition':{'ArnNotEquals':{'aws:PrincipalArn':[operator,role('cfn'),role('ingest-role')]},'Bool':{'aws:PrincipalIsAWSService':'false'}}},
  {'Effect':'Deny','Principal':'*','Action':'sqs:SendMessage','Resource':queues[0],'Condition':{'ArnNotEquals':{'aws:PrincipalArn':operator}}}])}}
 # SQS requires exactly one Resource per statement. Preserve the same two
 # queue attachments and exact Deny semantics, with no extra logical resource.
 original_statements=resources['QueuePolicy']['Properties']['PolicyDocument']['Statement']
 expanded=[]
 for statement in original_statements:
  for resource in statement['Resource'] if isinstance(statement['Resource'],list) else [statement['Resource']]:
   expanded.append(dict(copy.deepcopy(statement),Resource=resource))
 resources['QueuePolicy']['Properties']['PolicyDocument']['Statement']=expanded
 for component in ['ingest','dispatch']:
  cap=component.capitalize()
  resources[cap+'Logs']={'Type':'AWS::Logs::LogGroup','Properties':{'LogGroupName':'/aws/lambda/'+run+'-'+component,'RetentionInDays':ref('LogRetentionDays'),'Tags':tags}}
  resources[cap+'Role']={'Type':'AWS::IAM::Role','Properties':{'RoleName':run+'-'+component+'-role','PermissionsBoundary':boundary(component),
   'AssumeRolePolicyDocument':policy([{'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]),'Tags':tags,
   'Policies':[{'PolicyName':'BackupTrialRuntime','PolicyDocument':runtime[component]}]}}
  resources[cap+'Function']={'Type':'AWS::Lambda::Function','Condition':'WithRuntime','DependsOn':[cap+'Logs','ArchivePolicy','QueuePolicy'],
   'Properties':{'FunctionName':run+'-'+component,'Role':get(cap+'Role'),'Runtime':'dotnet10','Handler':'Ecs.Backup.Managed::Ecs.Backup.Managed.'+cap+'Function::Handler',
    'MemorySize':512,'Timeout':15,'Architectures':['x86_64'],'ReservedConcurrentExecutions':2 if component=='ingest' else 1,
    'Code':{'S3Bucket':ref('Archive'),'S3Key':ref('PackageKey'),'S3ObjectVersion':ref('PackageVersion')},'Environment':{'Variables':env},'Tags':tags}}
 resources['Mapping']={'Type':'AWS::Lambda::EventSourceMapping','Condition':'WithRuntime','DependsOn':['IngestFunction','QueuePolicy'],
  'Properties':{'EventSourceArn':get('Queue'),'FunctionName':get('IngestFunction'),'BatchSize':5,'FunctionResponseTypes':['ReportBatchItemFailures'],
   'ScalingConfig':{'MaximumConcurrency':2},'Enabled':False,'Tags':tags}}
 resources['Topic']={'Type':'AWS::SNS::Topic','Properties':{'TopicName':run+'-notices','Tags':tags}}
 resources['TopicPolicy']={'Type':'AWS::SNS::TopicPolicy','Properties':{'Topics':[ref('Topic')],'PolicyDocument':dict(policy([
  {'Sid':'OnlyDispatchMayPublish','Effect':'Deny','Principal':'*','Action':'sns:Publish','Resource':topic,'Condition':{'ArnNotEquals':{'aws:PrincipalArn':role('dispatch-role')}}},
  {'Sid':'RequireTlsForSupportedTopicActions','Effect':'Deny','Principal':'*','Action':SNS_TOPIC_POLICY_ACTIONS,'Resource':topic,'Condition':{'Bool':{'aws:SecureTransport':'false','aws:PrincipalIsAWSService':'false'}}}]),Id=run+'-topic-policy')}}
 resources['Subscription']={'Type':'AWS::SNS::Subscription','Properties':{'TopicArn':ref('Topic'),'Protocol':'email','Endpoint':ref('NotificationEmail')}}
 # Confirmation is created only after all other base resources/policies pass.
 resources['Subscription']['DependsOn']=[n for n in resources if n not in ['Subscription','IngestFunction','DispatchFunction','Mapping']]
 for resource in resources.values():resource.setdefault('Condition','BoundEnvironment')
 main={'AWSTemplateFormatVersion':'2010-09-09','Description':'ECS synthetic backup signal trial; offline reviewed, no deployment authorized','Parameters':params,'Conditions':conditions,
  'Rules':{'RuntimePackagePublished':{'RuleCondition':{'Fn::Equals':[ref('DeployRuntime'),'true']},'Assertions':[{'Assert':{'Fn::Not':[{'Fn::Equals':[ref('PackageVersion'),'BASE_ONLY_UNPUBLISHED']}]},'AssertDescription':'Runtime requires the actual recorded version of the immutable published package.'}]}},'Resources':resources,'Outputs':{'Table':{'Value':run,'Condition':'BoundEnvironment'},'Bucket':{'Value':ref('Archive'),'Condition':'BoundEnvironment'},
   'QueueUrl':{'Value':ref('Queue'),'Condition':'BoundEnvironment'},'MappingId':{'Value':ref('Mapping'),'Condition':'WithRuntime'},'Topic':{'Value':ref('Topic'),'Condition':'BoundEnvironment'}}}
 # Exact CF execution privileges, including rollback/delete. Role cannot alter its boundaries or own policy.
 regional={'StringEquals':{'aws:RequestedRegion':region}}
 cfn=[allow(['logs:DescribeLogGroups'],'*',regional),allow(['dynamodb:CreateTable','dynamodb:DescribeTable','dynamodb:DeleteTable','dynamodb:TagResource','dynamodb:UntagResource','dynamodb:ListTagsOfResource'],table,regional),
  allow(['s3:CreateBucket','s3:DeleteBucket','s3:GetBucketLocation','s3:GetBucketAcl','s3:GetBucketPolicy','s3:PutBucketPolicy','s3:DeleteBucketPolicy','s3:GetBucketTagging','s3:PutBucketTagging',
   's3:GetBucketVersioning','s3:PutBucketVersioning','s3:GetEncryptionConfiguration','s3:PutEncryptionConfiguration','s3:GetBucketPublicAccessBlock','s3:PutBucketPublicAccessBlock',
   's3:GetBucketOwnershipControls','s3:PutBucketOwnershipControls','s3:ListBucket','s3:ListBucketVersions'],bucket),
  allow(['s3:GetObject','s3:GetObjectVersion'],bucket+'/packages/*'),
  allow(['sqs:CreateQueue','sqs:GetQueueUrl','sqs:GetQueueAttributes','sqs:SetQueueAttributes','sqs:DeleteQueue','sqs:TagQueue','sqs:UntagQueue','sqs:ListQueueTags'],queues,regional),
  allow(['logs:CreateLogGroup','logs:DeleteLogGroup','logs:DescribeLogStreams','logs:PutRetentionPolicy','logs:DeleteRetentionPolicy','logs:TagResource','logs:UntagResource','logs:ListTagsForResource'],logs+[x+':*' for x in logs],regional),
  allow(['lambda:CreateFunction','lambda:GetFunction','lambda:GetFunctionConfiguration','lambda:DeleteFunction','lambda:TagResource','lambda:UntagResource',
   'lambda:ListTags','lambda:UpdateFunctionCode','lambda:UpdateFunctionConfiguration','lambda:PutFunctionConcurrency','lambda:GetFunctionConcurrency','lambda:DeleteFunctionConcurrency'],funcs,regional),
  allow(['lambda:CreateEventSourceMapping'],'*',{'ArnEquals':{'lambda:FunctionArn':funcs[0]},**regional}),
  allow(['lambda:TagResource'],arn('lambda','event-source-mapping:*'),{'StringEquals':{'aws:RequestTag/RunId':run,'aws:RequestedRegion':region},'ForAllValues:StringLike':{'aws:TagKeys':[t['Key'] for t in tags]+['aws:cloudformation:*']}}),
  allow(['lambda:GetEventSourceMapping','lambda:UpdateEventSourceMapping','lambda:DeleteEventSourceMapping'],arn('lambda','event-source-mapping:*'),{'ArnEquals':{'lambda:FunctionArn':funcs[0]},**regional}),
  allow(['sns:CreateTopic','sns:GetTopicAttributes','sns:SetTopicAttributes','sns:DeleteTopic','sns:TagResource','sns:UntagResource','sns:ListTagsForResource','sns:ListSubscriptionsByTopic','sns:GetSubscriptionAttributes','sns:Unsubscribe'],topic,regional),
  allow(['sns:Subscribe'],topic,{'StringEquals':{'sns:Protocol':'email','sns:Endpoint':ref('NotificationEmail'),'aws:RequestedRegion':region}})]
 for component in ['ingest','dispatch']:
  rr=role(component+'-role');cfn += [allow(['iam:CreateRole','iam:PutRolePermissionsBoundary'],rr,{'StringEquals':{'iam:PermissionsBoundary':boundary(component)}}),
   allow(['iam:GetRole','iam:TagRole','iam:UntagRole','iam:ListRolePolicies','iam:ListAttachedRolePolicies','iam:ListInstanceProfilesForRole','iam:GetRolePolicy','iam:PutRolePolicy','iam:DeleteRolePolicy','iam:DeleteRole'],rr),
   allow(['iam:PassRole'],rr,{'StringEquals':{'iam:PassedToService':'lambda.amazonaws.com'}})]
 boot={'AWSTemplateFormatVersion':'2010-09-09','Description':'Temporary bounded ECS trial CF execution role and immutable runtime boundaries; offline only',
  'Parameters':{'NotificationEmail':copy.deepcopy(params['NotificationEmail'])},'Conditions':{'BoundEnvironment':bound},'Resources':{}}
 for component in ['ingest','dispatch']:
  boot['Resources'][component.capitalize()+'Boundary']={'Type':'AWS::IAM::ManagedPolicy','Condition':'BoundEnvironment','Properties':{'ManagedPolicyName':run+'-'+component+'-boundary','PolicyDocument':runtime[component]}}
 boot['Resources']['ExecutionRole']={'Type':'AWS::IAM::Role','Condition':'BoundEnvironment','Properties':{'RoleName':run+'-cfn','Tags':tags,
  'AssumeRolePolicyDocument':policy([{'Effect':'Allow','Principal':{'Service':'cloudformation.amazonaws.com'},'Action':'sts:AssumeRole'}]),
  'Policies':[{'PolicyName':'CreateAndRetireOwnTrial','PolicyDocument':policy(cfn)}]}}
 stack=arn('cloudformation','stack/'+run+'/*');bootstrapStack=arn('cloudformation','stack/'+run+'-bootstrap/*')
 common=['cloudformation:CreateStack','cloudformation:DescribeStacks','cloudformation:DescribeStackEvents','cloudformation:DescribeStackResource','cloudformation:ListStackResources','cloudformation:GetTemplate','cloudformation:DeleteStack','cloudformation:CreateChangeSet','cloudformation:DescribeChangeSet','cloudformation:ExecuteChangeSet','cloudformation:DeleteChangeSet','cloudformation:TagResource','cloudformation:UntagResource']
 operatorPolicy=policy([allow(common,[stack,arn('cloudformation','changeSet/'+run+'-*/*')],regional),allow(['iam:PassRole'],role('cfn'),{'StringEquals':{'iam:PassedToService':'cloudformation.amazonaws.com'}}),
  allow(['sqs:SendMessage','sqs:ReceiveMessage','sqs:DeleteMessage','sqs:GetQueueAttributes'],queues,regional),
  allow(['lambda:InvokeFunction'],funcs[1],regional),allow(['lambda:GetFunction','lambda:GetFunctionConfiguration'],funcs,regional),
  allow(['lambda:GetEventSourceMapping','lambda:UpdateEventSourceMapping'],arn('lambda','event-source-mapping:*'),{'ArnEquals':{'lambda:FunctionArn':funcs[0]},**regional}),
  allow(['dynamodb:DescribeTable','dynamodb:DeleteTable'],table,regional),allow(['dynamodb:GetItem'],table,ns),allow(['dynamodb:Query'],[table]+[table+'/index/'+x for x in ['Due','Active','Cleanup']],ns),
  allow(['s3:ListBucket','s3:ListBucketVersions','s3:GetBucketLocation','s3:DeleteBucket'],bucket),allow(['s3:PutObject','s3:GetObject','s3:GetObjectVersion','s3:DeleteObject','s3:DeleteObjectVersion'],[bucket+'/packages/*',bucket+'/'+b['archivePrefix']+'/*']),
  allow(['logs:DescribeLogStreams','logs:GetLogEvents'],logs+[x+':*' for x in logs],regional),allow(['sns:GetTopicAttributes','sns:ListSubscriptionsByTopic','sns:GetSubscriptionAttributes'],topic,regional)])
 adminPolicy=policy([allow(common,[bootstrapStack,arn('cloudformation','changeSet/'+run+'-bootstrap-*/*')],regional),
  allow(['iam:CreateRole','iam:GetRole','iam:TagRole','iam:UntagRole','iam:ListRolePolicies','iam:ListAttachedRolePolicies','iam:ListInstanceProfilesForRole','iam:GetRolePolicy','iam:PutRolePolicy','iam:DeleteRolePolicy','iam:DeleteRole'],role('cfn')),
  allow(['iam:CreatePolicy','iam:GetPolicy','iam:GetPolicyVersion','iam:ListPolicyVersions','iam:ListEntitiesForPolicy','iam:DeletePolicy'],[boundary('ingest'),boundary('dispatch')]),
  allow(['iam:GetRole','iam:GetRolePolicy','iam:PutRolePolicy','iam:DeleteRolePolicy'],operator)])
 decisions={k:None for k in params if k!='DeployRuntime'};decisions['DeployRuntime']='false';decisions['PackageVersion']='BASE_ONLY_UNPUBLISHED'
 if package_sha is not None:decisions['PackageKey']='packages/'+package_sha+'.zip'
 return {'trial-template.json':main,'bootstrap-template.json':boot,'operator-temporary-policy.json':operatorPolicy,'bootstrap-admin-scope.json':adminPolicy,
  'runtime-policies.json':runtime,'required-decisions.json':decisions,'scope-summary.json':{'status':'OFFLINE_REVIEW_NOT_AUTHORIZED','runId':run,'account':account,'region':region,
   'operator':operator,'mainResources':len(resources),'bootstrapResources':3,'resourceTypes':sorted({x['Type'] for x in resources.values()}),
   'newStacks':[run,run+'-bootstrap'],'noCloudCalls':True,'retainedAfterMainStackDelete':['Sentinel','Archive'],
   'wildcardException':'CreateEventSourceMapping lacks resource scoping: exact function ARN/region. DescribeLogGroups is regional metadata-only and lacks resource scoping for CF provider reads. Mapping UUID operations remain function-bound; run-tag writes only.',
   'permissionBoundary':'CF role cannot edit its own policy or the two runtime boundaries; runtime IAM and NAT capabilities absent.'}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--scope',type=Path,default=HERE/'OPERATIONAL-SCOPE-PROPOSAL.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--package-sha256');a=p.parse_args()
 subprocess.run([sys.executable,'-I','-B',str(HERE/'verify_sources.py'),'--sentinel-root',str(a.upstream)],check=True)
 if a.output.exists():raise SystemExit('OUTPUT_MUST_BE_NEW')
 products=build(json.loads(a.scope.read_text(encoding='utf-8')),a.upstream,a.package_sha256);a.output.mkdir(parents=True)
 for name,data in products.items():(a.output/name).write_bytes((json.dumps(data,indent=2)+'\n').encode())
 print(json.dumps({'outputs':len(products),'mainResources':16,'bootstrapResources':3,'awsCalls':0}))
if __name__=='__main__':main()
