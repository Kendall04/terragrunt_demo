"""Explicit lifecycle action inventory; protected code completes API limits.

No action wildcard grants. Existing-resource writes use published exact ARNs.
Create-time generated IDs use typed ARNs and supported request conditions;
immutable source and controller-owned state enforce graph membership.
"""
import re


def valid_sql(launch,account,region):
    return (type(launch) is dict and set(launch)=={'image','subnet','security_group','instance_type'} and
            all(type(value) is str for value in launch.values()) and
            bool(re.fullmatch(f'arn:aws:ec2:{re.escape(region)}::image/ami-[0-9a-f]{{8,17}}',launch['image'])) and
            bool(re.fullmatch(f'arn:aws:ec2:{re.escape(region)}:{account}:subnet/subnet-[0-9a-f]{{8,17}}',launch['subnet'])) and
            bool(re.fullmatch(f'arn:aws:ec2:{re.escape(region)}:{account}:security-group/sg-[0-9a-f]{{8,17}}',launch['security_group'])) and
            launch['instance_type']=='t3a.small')


def valid_resources(resources,account,region,environment=None):
    if type(resources) is not dict or set(resources)!=set(INVENTORY):return False
    return all(type(arns) is list and all(type(arn) is str and '*' not in arn and '?' not in arn and
        (f':{region}:{account}:' in arn or arn.startswith(f'arn:aws:apigateway:{region}::')) and
        arn.startswith('arn:aws:'+INVENTORY[kind][0]+':') and
        (not environment or ('demo-prod-' not in arn if environment=='dev' else 'demo-dev-' not in arn))
        for arn in arns) for kind,arns in resources.items())

READS = {
 'ec2': ('DescribeAvailabilityZones','DescribeVpcs','DescribeVpcAttribute','DescribeSubnets','DescribeSecurityGroups','DescribeSecurityGroupRules','DescribeRouteTables','DescribeInternetGateways','DescribeAddresses','DescribeFlowLogs','DescribeInstances','DescribeInstanceAttribute','DescribeVolumes','DescribeVolumesModifications','DescribeLaunchTemplateVersions','DescribeImages','DescribeTags'),
 'elasticloadbalancing': ('DescribeLoadBalancers','DescribeLoadBalancerAttributes','DescribeListeners','DescribeRules','DescribeTargetGroups','DescribeTargetGroupAttributes','DescribeTags'),
 'autoscaling': ('DescribeAutoScalingGroups','DescribeScalingActivities','DescribeTags'),
 'logs': ('DescribeLogGroups',),
 'ecs': ('ListAccountSettings',),
}
# type: service, create actions, existing mutation actions, typed create ARN.
INVENTORY = {
 'aws_vpc':('ec2',('CreateVpc',),('ModifyVpcAttribute','DeleteVpc'),'vpc'),
 'aws_subnet':('ec2',('CreateSubnet',),('ModifySubnetAttribute','DeleteSubnet'),'subnet'),
 'aws_security_group':('ec2',('CreateSecurityGroup',),('DeleteSecurityGroup',),'security-group'),
 'aws_security_group_rule':('ec2',(),('AuthorizeSecurityGroupIngress','RevokeSecurityGroupIngress','AuthorizeSecurityGroupEgress','RevokeSecurityGroupEgress'),'security-group'),
 'aws_internet_gateway':('ec2',('CreateInternetGateway',),('AttachInternetGateway','DetachInternetGateway','DeleteInternetGateway'),'internet-gateway'),
 'aws_route_table':('ec2',('CreateRouteTable',),('DeleteRouteTable',),'route-table'),
 'aws_route':('ec2',(),('CreateRoute','ReplaceRoute','DeleteRoute'),'route-table'),
 'aws_route_table_association':('ec2',(),('AssociateRouteTable','DisassociateRouteTable','ReplaceRouteTableAssociation'),'route-table'),
 'aws_eip':('ec2',('AllocateAddress',),('ReleaseAddress',),'elastic-ip'),
 'aws_flow_log':('ec2',('CreateFlowLogs',),('DeleteFlowLogs',),'vpc-flow-log'),
 'aws_lb':('elasticloadbalancing',('CreateLoadBalancer',),('ModifyLoadBalancerAttributes','SetSecurityGroups','SetSubnets','DeleteLoadBalancer'),'loadbalancer/app'),
 'aws_lb_target_group':('elasticloadbalancing',('CreateTargetGroup',),('ModifyTargetGroup','ModifyTargetGroupAttributes','DeleteTargetGroup'),'targetgroup'),
 'aws_lb_listener':('elasticloadbalancing',('CreateListener',),('ModifyListener','DeleteListener'),'listener/app'),
 'aws_lb_listener_rule':('elasticloadbalancing',('CreateRule',),('ModifyRule','DeleteRule','SetRulePriorities'),'listener-rule/app'),
 'aws_autoscaling_group':('autoscaling',('CreateAutoScalingGroup',),('UpdateAutoScalingGroup','DeleteAutoScalingGroup'),'autoScalingGroup'),
 'aws_ecs_cluster':('ecs',('CreateCluster',),('DescribeClusters','UpdateCluster','UpdateClusterSettings','DeleteCluster','ListTagsForResource'),'cluster'),
 'aws_ecs_service':('ecs',('CreateService',),('DescribeServices','UpdateService','DeleteService','ListTagsForResource'),'service'),
 'aws_ecs_task_definition':('ecs',('RegisterTaskDefinition',),('DescribeTaskDefinition','DeregisterTaskDefinition','ListTagsForResource'),'task-definition'),
 'aws_instance':('ec2',('RunInstances',),('ModifyInstanceAttribute','TerminateInstances'),'instance'),
 'aws_cloudwatch_metric_alarm':('cloudwatch',('PutMetricAlarm',),('DescribeAlarms','PutMetricAlarm','DeleteAlarms','ListTagsForResource'),'alarm'),
 'aws_cloudwatch_log_group':('logs',('CreateLogGroup',),('PutRetentionPolicy','DeleteLogGroup','ListTagsForResource'),'log-group'),
 'aws_sns_topic':('sns',('CreateTopic',),('GetTopicAttributes','SetTopicAttributes','DeleteTopic','ListTagsForResource'),'topic'),
 'aws_sns_topic_subscription':('sns',(),('Subscribe','Unsubscribe','GetSubscriptionAttributes','SetSubscriptionAttributes','ListSubscriptionsByTopic'),'topic'),
 'aws_apigatewayv2_api':('apigateway',('POST',),('GET','PATCH','DELETE'),'/apis'),
 'aws_apigatewayv2_vpc_link':('apigateway',('POST',),('GET','PATCH','DELETE'),'/vpclinks'),
 'aws_apigatewayv2_integration':('apigateway',('POST',),('GET','PATCH','DELETE'),'/apis'),
 'aws_apigatewayv2_route':('apigateway',('POST',),('GET','PATCH','DELETE'),'/apis'),
 'aws_apigatewayv2_stage':('apigateway',('POST',),('GET','PATCH','DELETE'),'/apis'),
}


def policy(binding, account, region, resources, package, version):
    env=binding.rsplit('-',1)[1]
    high_risk='/infra-high-risk-' in binding
    role_name='e1-controller-'+binding.split('/')[1]
    bucket=f'e1-lifecycle-{env}-{account}-{region}'
    statements=[]
    def allow(actions, arns, conditions=None):
        if not actions or not arns:return
        statement={'Effect':'Allow','Action':sorted(set(actions)),'Resource':sorted(set(arns))}
        if conditions:statement['Condition']=conditions
        statements.append(statement)
    if binding.startswith('request-gateway/'):
        allow(['codebuild:StartBuild'],[f'arn:aws:codebuild:{region}:{account}:project/{role_name}'])
    else:
        for service,actions in READS.items():
            allow([service+':'+action for action in actions],['*'],{'StringEquals':{'aws:RequestedRegion':region}})
        for kind, members in resources.items():
            if kind not in INVENTORY:continue
            if not high_risk and kind in ('aws_instance','aws_ecs_service','aws_ecs_task_definition'):continue
            service,create,mutate,resource_type=INVENTORY[kind]
            # Exact existing resources supplied only by protected binding/state.
            if kind=='aws_instance':
                # User-data/profile/network mutations have no generic grant.
                mutate=tuple(action for action in mutate if action!='ModifyInstanceAttribute')
            allow([service+':'+action for action in mutate],members)
            if service=='logs':allow([service+':'+action for action in mutate],[arn+':*' for arn in members])
            if not create:continue
            if service=='apigateway':
                # POST collection endpoints for the two roots; child collections
                # need exact protected API IDs and are not wildcarded.
                create_arns=[f'arn:aws:apigateway:{region}::{resource_type}'] if kind in ('aws_apigatewayv2_api','aws_apigatewayv2_vpc_link') else members
            elif service=='sns':create_arns=[f'arn:aws:sns:{region}:{account}:demo-{env}-shared-alerts']
            elif service=='ecs':
                create_arns=[f'arn:aws:ecs:{region}:{account}:cluster/demo-{env}-platform-main-cluster'] if kind=='aws_ecs_cluster' else [f'arn:aws:ecs:{region}:{account}:task-definition/demo-{env}-app-api-{color}:*' for color in ('blue','green')]
                if kind=='aws_ecs_service':create_arns=[f'arn:aws:ecs:{region}:{account}:service/demo-{env}-platform-main-cluster/demo-{env}-app-api-{color}-svc' for color in ('blue','green')]
            elif service=='autoscaling':create_arns=[f'arn:aws:autoscaling:{region}:{account}:autoScalingGroup:*:autoScalingGroupName/demo-{env}-asg-nat-{az}' for az in ('a','b')]
            elif service=='cloudwatch':create_arns=[f'arn:aws:cloudwatch:{region}:{account}:alarm:demo-{env}-*']
            elif service=='logs':create_arns=members
            else:create_arns=[f'arn:aws:{service}:{region}:{account}:{resource_type}/*']
            if kind=='aws_flow_log':create_arns=resources.get('aws_vpc',[])
            if kind=='aws_lb_listener':create_arns=resources.get('aws_lb',[])
            if kind=='aws_lb_listener_rule':create_arns=resources.get('aws_lb_listener',[])
            if kind=='aws_instance':
                # RunInstances authorizes multiple resource types separately.
                # A protected launch tuple is indispensable, including profile.
                sql=resources.get('_sql_launch')
                if not sql:continue
                allow(['ec2:RunInstances'],[sql['image'],sql['subnet'],sql['security_group']])
                allow(['ec2:RunInstances'],[f'arn:aws:ec2:{region}:{account}:instance/*'],
                      {'StringEquals':{'aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo',
                                       'ec2:InstanceType':sql['instance_type'],'ec2:MetadataHttpTokens':'required'},
                       'ArnEquals':{'ec2:InstanceProfile':f'arn:aws:iam::{account}:instance-profile/demo-{env}-data-sql-ec2-profile'}})
                allow(['ec2:RunInstances'],[f'arn:aws:ec2:{region}:{account}:volume/*'],{'Bool':{'ec2:Encrypted':'true'}})
                allow(['ec2:RunInstances'],[f'arn:aws:ec2:{region}:{account}:network-interface/*'],
                      {'ArnEquals':{'ec2:Subnet':sql['subnet']},'Bool':{'ec2:AssociatePublicIpAddress':'false'}})
                allow(['ec2:CreateTags'],[f'arn:aws:ec2:{region}:{account}:instance/*',f'arn:aws:ec2:{region}:{account}:volume/*'],
                      {'StringEquals':{'ec2:CreateAction':'RunInstances','aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}})
                continue
            # RequestTag is supported on taggable create resources. API child
            # collections are exact-ID-only and do not take tagging parameters.
            condition=None if (service=='apigateway' and kind not in ('aws_apigatewayv2_api','aws_apigatewayv2_vpc_link')) or kind in ('aws_lb_listener','aws_lb_listener_rule','aws_flow_log') else {'StringEquals':{'aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}}
            if kind=='aws_autoscaling_group':
                condition={'StringEquals':{'aws:RequestTag/Environment':env},
                           'Bool':{'autoscaling:LaunchTemplateVersionSpecified':'true'},
                           'NumericEquals':{'autoscaling:MinSize':'1','autoscaling:MaxSize':'1'}}
            allow([service+':'+action for action in create],create_arns,condition)
            if service in ('cloudwatch','sns','logs'):
                allow([service+':TagResource'],create_arns,{'StringEquals':{'aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}})
            if service=='ecs':
                allow(['ecs:TagResource'],create_arns,{'StringEquals':{'ecs:CreateAction':list(create),
                    'aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}})
            if service=='autoscaling':
                allow(['autoscaling:CreateOrUpdateTags'],create_arns,{'StringEquals':{'aws:RequestTag/Environment':env}})
            if kind=='aws_cloudwatch_log_group':allow(['logs:CreateLogGroup'],[arn+':*' for arn in create_arns],condition)
            if service=='ec2' and kind not in ('aws_flow_log','aws_instance'):
                allow(['ec2:CreateTags'],create_arns,{'StringEquals':{'ec2:CreateAction':list(create),
                    'aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}})
            if service=='elasticloadbalancing':
                allow(['elasticloadbalancing:AddTags'],[f'arn:aws:elasticloadbalancing:{region}:{account}:{resource_type}/demo-{env}-*'],
                      {'StringEquals':{'elasticloadbalancing:CreateAction':list(create)}})
        # Multi-resource parent authorizations are separate from generated
        # child request tags, which are absent on parent evaluations.
        allow(['ec2:CreateSubnet','ec2:CreateRouteTable','ec2:CreateSecurityGroup','ec2:AttachInternetGateway','ec2:DetachInternetGateway'],resources.get('aws_vpc',[]))
        allow(['ec2:AssociateRouteTable','ec2:DisassociateRouteTable','ec2:ReplaceRouteTableAssociation'],resources.get('aws_subnet',[]))
        allow(['ecs:ListTasks'],['*'],{'ArnEquals':{'ecs:cluster':f'arn:aws:ecs:{region}:{account}:cluster/demo-{env}-platform-main-cluster'}})
        allow(['ec2:CreateTags'],[f'arn:aws:ec2:{region}:{account}:vpc-flow-log/*'],{'StringEquals':{
            'ec2:CreateAction':'CreateFlowLogs','aws:RequestTag/Environment':env,'aws:RequestTag/Project':'demo'}})
        # Newly generated IDs inside the immutable create graph cannot be
        # enumerated beforehand. These bootstrap dependencies are typed and
        # tagged; existing-ID plan membership remains mandatory before mutation.
        # The execution role is never exposed to callers and cannot change tags.
        tagged={'StringEquals':{'aws:ResourceTag/Environment':env,'aws:ResourceTag/Project':'demo'}}
        for kind,actions in {
            'vpc':('CreateSubnet','CreateRouteTable','CreateSecurityGroup','ModifyVpcAttribute','AttachInternetGateway','CreateFlowLogs'),
            'subnet':('ModifySubnetAttribute','AssociateRouteTable'),
            'security-group':('AuthorizeSecurityGroupIngress','AuthorizeSecurityGroupEgress'),
            'internet-gateway':('AttachInternetGateway',),
            'route-table':('AssociateRouteTable','CreateRoute'),
        }.items():allow(['ec2:'+action for action in actions],[f'arn:aws:ec2:{region}:{account}:{kind}/*'],tagged)
        alb=f'arn:aws:elasticloadbalancing:{region}:{account}:loadbalancer/app/demo-{env}-internal-alb/*'
        listener=f'arn:aws:elasticloadbalancing:{region}:{account}:listener/app/demo-{env}-internal-alb/*'
        allow(['elasticloadbalancing:CreateListener'],[alb],{'StringEquals':{'elasticloadbalancing:ListenerProtocol':'HTTP'}})
        allow(['elasticloadbalancing:CreateRule'],[listener])
        allow(['elasticloadbalancing:ModifyLoadBalancerAttributes'],[alb],tagged)
        allow(['elasticloadbalancing:ModifyTargetGroupAttributes'],[f'arn:aws:elasticloadbalancing:{region}:{account}:targetgroup/demo-{env}-{color}/*' for color in ('blue','green')],tagged)
        # Only the installed child collections; no authorizers, domains, IAM
        # credentials or caller-defined integration source.
        for child in ('integrations','routes','stages'):
            allow(['apigateway:POST'],[f'arn:aws:apigateway:{region}::/apis/*/{child}'],tagged)
            allow(['apigateway:GET'],[f'arn:aws:apigateway:{region}::/apis/*/{child}/*'],tagged)
        allow(['apigateway:GET'],[f'arn:aws:apigateway:{region}::/apis/*',f'arn:aws:apigateway:{region}::/vpclinks/*'],tagged)
        flow=f'arn:aws:iam::{account}:role/demo-{env}-vpc-flow-logs-role'
        allow(['iam:PassRole'],[flow],{'StringEquals':{'iam:PassedToService':'vpc-flow-logs.amazonaws.com'}})
        if high_risk:
            allow(['iam:PassRole'],[f'arn:aws:iam::{account}:role/demo-{env}-data-sql-ec2-role'],
                  {'StringEquals':{'iam:PassedToService':'ec2.amazonaws.com'}})
        allow(['iam:PassRole'],[f'arn:aws:iam::{account}:role/demo-{env}-nat-role'],
              {'StringEquals':{'iam:PassedToService':'ec2.amazonaws.com'}})
        allow(['iam:GetInstanceProfile'],[f'arn:aws:iam::{account}:instance-profile/demo-{env}-nat-instance-profile']+
              ([f'arn:aws:iam::{account}:instance-profile/demo-{env}-data-sql-ec2-profile'] if high_risk else []))
        layers=('shared','secrets','global','data','platform','apps','edge') if high_risk else ('shared','secrets','global','platform','edge')
        state=[f'e1/lifecycle/{env}/{layer}/terraform.tfstate' for layer in layers]
        allow(['s3:GetObject','s3:PutObject'],[f'arn:aws:s3:::{bucket}/{key}' for key in state])
        allow(['s3:GetObject','s3:PutObject','s3:DeleteObject'],[f'arn:aws:s3:::{bucket}/{key}.tflock' for key in state])
        allow(['s3:ListBucket'],[f'arn:aws:s3:::{bucket}'],{'StringLike':{'s3:prefix':[f'e1/lifecycle/{env}/{layer}/*' for layer in layers]}})
    allow(['s3:GetObjectVersion'],[f'arn:aws:s3:::e1-control-bundles-{account}-{region}/bundles/sha256/{package}.json'],
          {'StringEquals':{'s3:VersionId':version}})
    # Binding/admin approval reads; never permission to install/change them.
    configs=[binding]+(['environment-lifecycle/'+binding.split('/')[1]] if binding.startswith('request-gateway/') else [])
    allow(['s3:GetObject'],[f'arn:aws:s3:::demo-release-artifacts-{account}/lifecycle/{name}/current.json' for name in configs])
    own='operations/'+binding+'/'
    allow(['s3:GetObject'],[f'arn:aws:s3:::{bucket}/{own}*'])
    allow(['s3:PutObject'],[f'arn:aws:s3:::{bucket}/{own}*'],{'StringEquals':{'s3:if-none-match':'*'}})
    requests='requests/'+binding.split('/')[1]+'/'
    allow(['s3:GetObject'],[f'arn:aws:s3:::{bucket}/{requests}*'])
    if binding.startswith('request-gateway/'):
        allow(['s3:PutObject'],[f'arn:aws:s3:::{bucket}/{requests}*'],{'StringEquals':{'s3:if-none-match':'*'}})
    prefix='/aws/lambda/' if binding.startswith('request-gateway/') else '/aws/codebuild/'
    name=('e1-gateway-' if binding.startswith('request-gateway/') else 'e1-controller-')+binding.split('/')[1]
    allow(['logs:CreateLogStream','logs:PutLogEvents'],[f'arn:aws:logs:{region}:{account}:log-group:{prefix}{name}:log-stream:*'])
    return {'Version':'2012-10-17','Statement':statements}
