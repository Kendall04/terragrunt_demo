import copy
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import time
import wp5
from scripts import practical_dev as p,original_dev
from scripts.lifecycle import contract as c
from scripts import environment_mutation as e

ACCOUNT='111122223333';REGION='us-east-1';REV='a'*40
CONFIG=dict(schema='E16_SUPERVISED_DEV_V1',environment='dev',account=ACCOUNT,region=REGION,profile='offline-fixture',
 operator_arn='arn:aws:iam::'+ACCOUNT+':role/DemoDevOperator',source_commit=REV,
 variables={'global':{'protected_nat_launch':{'a':{'id':'lt-00000001','version':1,'subnet':'subnet-a','recovery':'ADMIN_VERIFIED_ALL_THREE_HANDLERS_AND_EXACT_MEMBERSHIP'},'b':{'id':'lt-00000002','version':1,'subnet':'subnet-b','recovery':'ADMIN_VERIFIED_ALL_THREE_HANDLERS_AND_EXACT_MEMBERSHIP'}}},'data':{'protected_sql_ami':'ami-00000001'}})

class Fake:
    def __init__(self):
        self.calls=[];self.states={};self.outputs={};self.serial=0;self.plans={};self.wrong=False;self.exclusive=True;self.active=False
        self.busy=False;self.fail=False;self.partial=False;self.asg_busy=False;self.ecs_busy=False;self.metrics=True;self.unknown=False;self.tamper_tags=False
        self.inhibited=True;self.verify_mode=False;self.ready=True
    def rows(self,layer,network=False):
        types={'global':[('module.vpc.aws_vpc.this','aws_vpc')]+([] if network else [('aws_autoscaling_group.wp5_nat["a"]','aws_autoscaling_group'),('aws_autoscaling_group.wp5_nat["b"]','aws_autoscaling_group')]),
            'data':[('aws_instance.db','aws_instance')],'platform':[('module.ecs_cluster.aws_ecs_cluster.this','aws_ecs_cluster')],
            'apps':[('module.demo_api_blue.aws_ecs_service.this','aws_ecs_service'),('module.demo_api_green.aws_ecs_service.this','aws_ecs_service')],
            'edge':[('module.apigateway.aws_apigatewayv2_api.http','aws_apigatewayv2_api')]}
        return [dict(address=a,mode='managed',type=t,values=dict(id=layer+'-'+str(i),tags=dict(Environment='dev',Project='demo'),**({'desired_count':0} if t=='aws_ecs_service' else {}))) for i,(a,t) in enumerate(types[layer])]
    def out(self,layer):
        return {'global':dict(private_subnet_ids=['subnet-a','subnet-b'],db_instance_sg_id='sg-db',demo_sg_id='sg-app',vpc_link_sg_id='sg-link',alb_listener_arn='arn:listener',demo_blue_tg_arn='arn:tg:blue',demo_green_tg_arn='arn:tg:green',vpc_id='vpc-own',nat_eip_allocation_ids={'a':'eipalloc-a','b':'eipalloc-b'}),
            'data':dict(instance_id='i-sql',db_private_ip='10.0.100.5'), 'platform':dict(cluster_name='demo-dev-platform-main-cluster',cluster_arn='arn:cluster'),
            'apps':{},'edge':dict(api_id='apiown',api_endpoint='https://apiown.execute-api.us-east-1.amazonaws.com',vpc_link_id='link-own')}[layer]
    def run(self,args,cwd=None,data=None):
        self.calls.append(list(args))
        if args[:2]==['git','rev-parse']:return REV.encode()
        if args[:2]==['git','status']:return b''
        if args[:2]==['git','ls-files']:return '\n'.join(f.relative_to(Path(cwd)).as_posix() for f in Path(cwd).rglob('*') if f.is_file()).encode()
        if args[:2]==['terraform','version']:return c.canonical(dict(terraform_version='1.13.4'))
        if args[0]=='terraform':
            root=Path(args[1].split('=',1)[1]);layer=root.name;action=args[2]
            if action=='init':
                path=root/'.terraform';path.mkdir(exist_ok=True)
                path.joinpath('terraform.tfstate').write_bytes(c.canonical(dict(backend=dict(type='s3',config=dict(bucket=f'e1-lifecycle-dev-{ACCOUNT}-{REGION}',key=f'e1/lifecycle/dev/{layer}/terraform.tfstate',workspace_key_prefix=f'e1/lifecycle/dev/{layer}/terraform.tfstate/workspaces',region=REGION,encrypt=True,use_lockfile=True)))))
                return b'initialized'
            if action=='workspace':return b'default'
            if action=='state':
                return c.canonical(dict(version=4,lineage='11111111-1111-4111-8111-111111111111',serial=self.serial,outputs={k:dict(value=v) for k,v in self.out(layer).items()},resources=self.states[layer]))
            if action=='show':
                if args[-1]=='-json':return c.canonical(dict(values=dict(root_module=dict(resources=self.states[layer]))))
                value=self.plans[args[-1]]
                return c.canonical(value) if '-json' in args else b'REAL_BINARY_PREVIEW_FROM_TERRAFORM_FAKE'
            if action=='plan':
                file=Path(next(v.split('=',1)[1] for v in args if v.startswith('-out=')));down='-destroy' in args
                vars=json.loads((root/'e16.auto.tfvars.json').read_text());network=layer=='global' and not vars['protected_nat_launch']
                future=[] if down else self.rows(layer,network)
                prior={r['address']:r for r in self.states.get(layer,[])}
                changes=[dict(address=r['address'],mode='managed',type=r['type'],change=dict(actions=['delete'] if down else (['no-op'] if r['address'] in prior else ['create']),before=prior.get(r['address'],{}).get('values'),after=None if down else r['values'])) for r in (self.states[layer] if down else future)]
                value=dict(format_version='1.2',resource_changes=changes,network=network,layer=layer,down=down)
                file.write_bytes(c.canonical(value));self.plans[str(file)]=value;return b'plan'
            if action=='apply':
                value=self.plans[args[-1]]
                self.states[layer]=[] if value['down'] else self.rows(layer,value['network']);self.serial+=1
                if self.fail:raise p.Failure(1,b'lost response after state changed')
                if self.partial:self.states[layer]=self.states[layer][:1]
                return b'applied'
            raise AssertionError(args)
        if args[0]=='curl':
            if args[-1].endswith('/ready'):return c.canonical(dict(status='Healthy' if self.ready else 'Unhealthy',checks=[dict(name=n,status='Healthy') for n in ('database','kms')]))
            if '--request' in args:self.marker=json.loads(data)['text'];return c.canonical(dict(id=1,text=self.marker))
            return c.canonical([dict(id=1,text=self.marker)])
        assert args[0]=='aws',args
        index=args.index('--output')+2;service,action=args[index:index+2];rest=args[index+2:]
        bucket=f'e1-lifecycle-dev-{ACCOUNT}-{REGION}'
        if action=='get-caller-identity':value=dict(Account='999999999999' if self.wrong else ACCOUNT,Arn=f'arn:aws:sts::{ACCOUNT}:assumed-role/DemoDevOperator/test')
        elif action=='get-bucket-location':value=dict(LocationConstraint=None)
        elif action=='get-bucket-versioning':value=dict(Status='Enabled')
        elif action=='get-public-access-block':value=dict(PublicAccessBlockConfiguration=dict(BlockPublicAcls=True,IgnorePublicAcls=True,BlockPublicPolicy=True,RestrictPublicBuckets=True))
        elif action=='get-bucket-encryption':value=dict(ServerSideEncryptionConfiguration=dict(Rules=[dict(ApplyServerSideEncryptionByDefault=dict(SSEAlgorithm='AES256'))]))
        elif action=='get-bucket-policy':
            keys=[f'arn:aws:s3:::{bucket}/e1/lifecycle/dev/{l}/terraform.tfstate'+suffix for l in p.UP for suffix in ('','.tflock')]
            statements=[dict(Effect='Deny',Condition=dict(Bool={'aws:SecureTransport':'false'}))]
            if self.exclusive:statements += [dict(Sid='E16ExclusiveDevRuntimeWriter',Effect='Deny',Principal='*',Action=['s3:PutObject','s3:DeleteObject'],Resource=keys,Condition=dict(ArnNotEquals={'aws:PrincipalArn':CONFIG['operator_arn']}))]
            value=dict(Policy=json.dumps(dict(Statement=statements)))
        elif action=='get-object':
            key=rest[rest.index('--key')+1];target=Path(rest[-1])
            if key=='arbitration/dev/application.json':
                head=e.initial('dev','application')
                if self.active:head.update(generation=1,state='ACTIVE',owner='11111111-1111-4111-8111-111111111111',operation='11111111-1111-4111-8111-111111111111',binding='environment-lifecycle/infra-dev',request_sha256='a'*64)
                target.write_bytes(e.canonical(head))
            else:
                from scripts.normal_delivery import authorization as a
                planned=dict(token='dev/recovery/change_rt/op/change_rt',request={'RouteTableId':'rtb-own'},operation_sha256='a'*64)
                if key.endswith('/plan'):value=planned
                elif key.endswith('/attempt'):value=dict(token=planned['token'],plan_sha256=a.sha(a.canonical(planned)))
                else:value=dict(token=planned['token'],request_sha256=a.sha(a.canonical(planned['request'])),state='UNKNOWN' if self.unknown else 'APPLIED',result=planned['request'])
                target.write_bytes(c.canonical(value))
            value=dict(VersionId='offline-version')
        elif action=='list-functions':value=dict(Functions=[dict(FunctionName='e1-nat-recovery-nat-dev-change-rt',FunctionArn=f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-nat-recovery-nat-dev-change-rt')])
        elif action=='list-versions-by-function':value=dict(Versions=[dict(Timeout=60,Version='1')])
        elif action=='list-projects':value=dict(projects=['e1-controller-'+n for n in p.BINDINGS])
        elif action=='list-builds-for-project':value=dict(ids=['build-one'] if self.busy else [])
        elif action=='batch-get-builds':value=dict(builds=[dict(buildInProgress=True,buildStatus='IN_PROGRESS')],buildsNotFound=[])
        elif action=='list-objects-v2':
            prefix=rest[rest.index('--prefix')+1]
            if prefix.startswith('e1/'):
                layer=prefix.split('/')[3];value=dict(Contents=[dict(Key=prefix)] if layer in self.states else [],IsTruncated=False)
            else:value=dict(Contents=[dict(Key='recovery/dev/recovery/change_rt/op/change_rt/attempt'),dict(Key='recovery/dev/recovery/change_rt/op/change_rt/observed'),dict(Key='recovery/dev/recovery/change_rt/op/change_rt/plan')] if self.unknown else [],IsTruncated=False)
        elif action=='get-resources':value=dict(ResourceTagMappingList=[])
        elif action=='describe-secret':value=dict(VersionIdsToStages={'version':['AWSCURRENT']})
        elif action=='get-queue-url':value=dict(QueueUrl='https://sqs.us-east-1.amazonaws.com/'+ACCOUNT+'/own')
        elif action=='get-queue-attributes':value=dict(Attributes={k:'0' for k in ('ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed')})
        elif action=='describe-rule':value=dict(State='DISABLED' if self.inhibited else 'ENABLED')
        elif action=='get-function-concurrency':value=dict(ReservedConcurrentExecutions=0 if self.inhibited else 1)
        elif action=='get-function-configuration':value=dict(Timeout=60)
        elif action in ('disable-rule','put-function-concurrency','suspend-processes','update-auto-scaling-group','update-service'):value={}
        elif action=='describe-auto-scaling-groups':
            if not any(r['type']=='aws_autoscaling_group' for r in self.states.get('global',[])):return c.canonical(dict(AutoScalingGroups=[]))
            value=dict(AutoScalingGroups=[dict(AutoScalingGroupName='demo-dev-asg-nat-'+v,Instances=[dict(InstanceId='i-nat',HealthStatus='Healthy',LifecycleState='InService')] if self.verify_mode else [],MinSize=0,MaxSize=0,DesiredCapacity=0,SuspendedProcesses=[dict(ProcessName=n) for n in p.PROCESSES]) for v in ('a','b')])
        elif action=='describe-scaling-activities':value=dict(Activities=[dict(StatusCode='InProgress')] if self.asg_busy else [])
        elif action in ('describe-lifecycle-hooks','describe-warm-pool','describe-scheduled-actions','describe-policies'):
            value={dict(zip(('describe-lifecycle-hooks','describe-warm-pool','describe-scheduled-actions','describe-policies'),('LifecycleHooks','Instances','ScheduledUpdateGroupActions','ScalingPolicies')))[action]:[]}
        elif action=='describe-services':value=dict(services=[dict(desiredCount=1 if self.verify_mode else 0,runningCount=1 if self.ecs_busy or self.verify_mode else 0,pendingCount=0) for _ in range(2)],failures=[])
        elif action=='list-tasks':value=dict(taskArns=['task-one'] if self.verify_mode else [])
        elif action=='describe-tasks':value=dict(failures=[],tasks=[dict(lastStatus='RUNNING',taskDefinitionArn=f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/demo-dev-app-api-blue:1',group='service:demo-dev-app-api-blue-svc',containers=[dict(name=getattr(self,'probe_name','demo-dev-app-api-blue-readiness-probe'),exitCode=0),dict(name='demo-dev-app-api-blue',lastStatus='RUNNING')])])
        elif action=='get-api':value=dict(ApiId='apiown',ApiEndpoint='https://apiown.execute-api.us-east-1.amazonaws.com')
        elif action=='get-vpc-link':value=dict(VpcLinkStatus='AVAILABLE')
        elif action=='describe-route-tables':value=dict(RouteTables=[dict(Routes=[dict(DestinationCidrBlock='0.0.0.0/0',NetworkInterfaceId='eni-nat',State='active')])])
        elif action=='describe-instance-attribute':value=dict(SourceDestCheck=dict(Value=False))
        elif action=='get-metric-statistics':value=dict(Datapoints=[dict(Maximum=0,Timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))] if self.metrics else [])
        elif action=='describe-instances':value=dict(Reservations=[dict(Instances=[dict(InstanceId='i-sql' if 'i-sql' in rest else 'i-nat',State=dict(Name='running'),PrivateIpAddress='10.0.100.5',VpcId='vpc-own',NetworkInterfaces=[dict(NetworkInterfaceId='eni-nat')])])] if self.verify_mode else [])
        elif action=='describe-volumes':value=dict(Volumes=[])
        elif action=='describe-addresses':value=dict(Addresses=[dict(NetworkInterfaceId='eni-nat',InstanceId='i-nat')] if self.verify_mode else [])
        elif action=='describe-network-interfaces':value=dict(NetworkInterfaces=[])
        else:raise AssertionError((service,action,rest))
        return c.canonical(value)

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);base=Path(self.temp.name)
        source=base/'source';shutil.copytree(p.ROOT/'terraform/modules/target/dev',source/'terraform/modules/target/dev')
        auth=source/'terraform/infra/security/authority.json';auth.parent.mkdir(parents=True)
        doc=json.loads((p.ROOT/'terraform/infra/security/authority.json').read_text());records={}
        for key in {k for values in doc['ownership_closure']['consumers'].values() for k in values}:records[key]=dict(available=True,value='arn:offline:'+key)
        doc['ownership_closure']['publications'][ACCOUNT+'/'+REGION]=dict(records=records);auth.write_text(json.dumps(doc))
        user=source/'terraform/infra/data/user_data.sh';user.parent.mkdir(parents=True);user.write_bytes((p.ROOT/'terraform/infra/data/user_data.sh').read_bytes())
        self.patch=patch.object(p,'ROOT',source);self.patch.start();self.addCleanup(self.patch.stop)
        self.config=copy.deepcopy(CONFIG);self.fake=Fake();self.session=p.Session(self.config,base/'session',self.fake);self.session.initialize()
    def apply(self,down=False,network=False):
        review=self.session.prepare(down,network);result=self.session.apply(review['plan_id'],review['confirmation'],review['sql_confirmation']);return result
    def all_up(self):
        for _ in p.UP:self.apply()
    def shutdown(self):
        self.session.save(self.session.directory/'shutdown-readback.json',dict(config_sha256=p.sha(c.canonical(self.config)),prior_instances={'demo-dev-asg-nat-a':[],'demo-dev-asg-nat-b':[]},at=int(time.time())-600,timeouts={'e1-nat-recovery-nat-dev-change-rt':60},reviewed=True))
    def test_dev_only_scope(self):
        for field,value in (('environment','prod'),('environment','shared'),('operator_arn','arn:aws:iam::'+ACCOUNT+':role/e1-controller-infra-dev')):
            with self.assertRaises(ValueError):p.Session(dict(self.config,**{field:value}),self.session.directory,self.fake)
    def test_wrong_identity_before_plan(self):
        self.fake.wrong=True
        with self.assertRaisesRegex(ValueError,'account'):self.session.prepare()
    def test_exclusive_handoff_not_claimed_from_configuration(self):
        self.fake.exclusive=False
        with self.assertRaisesRegex(ValueError,'transfer'):self.session.prepare()
    def test_original_backend_and_locking(self):
        file=self.session.root('global')/'.terraform/terraform.tfstate';value=json.loads(file.read_text());value['backend']['config']['key']='e1/lifecycle/prod/global/terraform.tfstate';file.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'state/locking'):self.session.prepare()
    def test_e2_active_owner_rejected(self):
        self.fake.active=True
        with self.assertRaisesRegex(ValueError,'E2'):self.session.prepare()
    def test_controller_active_rejected(self):
        self.fake.busy=True
        with self.assertRaisesRegex(ValueError,'active ECS'):self.session.prepare()
    def test_real_plan_preview_and_exact_binary(self):
        review=self.session.prepare();self.assertIn('REAL_BINARY',review['preview']);self.session.apply(review['plan_id'],review['confirmation'])
        applied=[a for a in self.fake.calls if a[0]=='terraform' and a[2]=='apply'];plans=[a for a in self.fake.calls if a[0]=='terraform' and a[2]=='plan']
        self.assertEqual(len(plans),1);self.assertTrue(applied[0][-1].endswith('/saved.tfplan') or applied[0][-1].endswith('\\saved.tfplan'));self.assertNotIn('-auto-approve',applied[0])
    def test_full_original_up_order(self):
        result=[self.apply()['layer'] for _ in p.UP];self.assertEqual(result,list(p.UP));self.assertEqual(set(self.fake.states),set(p.UP))
    def test_network_stage_does_not_claim_nat_ready(self):
        result=self.apply(network=True);self.assertEqual(result['phase'],'NETWORK_ONLY_ADMIN_NAT_INSTALL_NEXT');self.assertFalse((self.session.directory/'up-global-reconciled.json').exists())
        self.assertEqual(self.session.prepare()['layer'],'global')
    def test_reconciled_partial_network_can_prepare_fresh_bootstrap_plan(self):
        self.fake.states['global']=self.fake.rows('global',network=True)
        result=self.session.prepare(network_only=True)
        self.assertEqual(result['layer'],'global');self.assertEqual(result['phase'],'REVIEW_REQUIRED_NOT_EXECUTED')
        calls=[v for v in self.fake.calls if 'describe-auto-scaling-groups' in v]
        self.assertTrue(calls)
    def test_network_bootstrap_rejects_already_created_nat_asgs(self):
        self.fake.states['global']=self.fake.rows('global')
        with self.assertRaisesRegex(ValueError,'NAT ASGs'):self.session.prepare(network_only=True)
    def test_provider_cache_is_not_treated_as_executable_root_source(self):
        cache=self.session.root('platform')/'.terraform/providers/registry.terraform.io/hashicorp/aws/5.100.0/linux_amd64'
        cache.mkdir(parents=True);(cache/'cache-only.tf').write_text('provider cache is not root source')
        self.session.source()
        extra=self.session.root('platform')/'extra.tf';extra.write_text('resource "aws_vpc" "foreign" {}')
        with self.assertRaisesRegex(ValueError,'extra nested'):self.session.source()
    def test_saved_binary_mismatch(self):
        review=self.session.prepare();(self.session.directory/'plans'/review['plan_id']/'saved.tfplan').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'binary'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_stale_state(self):
        self.apply();review=self.session.prepare();self.fake.states['data']=[];self.fake.serial+=1
        with self.assertRaisesRegex(ValueError,'stale'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_reordered_state_checks_preserve_exact_plan_execution(self):
        self.apply(network=True)
        original=self.fake.run
        count=0
        def run(args,cwd=None,data=None):
            nonlocal count
            raw=original(args,cwd,data)
            if args[0]=='terraform' and args[2]=='state':
                value=json.loads(raw);count+=1
                checks=[dict(config_addr=n,object_kind='var',status='pass',objects=[dict(object_addr=n,status='pass')]) for n in ('var.a','var.b')]
                value['check_results']=checks if count%2 else list(reversed(checks))
                return json.dumps(value,indent=count%2+1).encode()
            return raw
        self.fake.run=run
        review=self.session.prepare(network_only=True)
        self.session.apply(review['plan_id'],review['confirmation'])
        self.assertTrue((self.session.directory/'plans'/review['plan_id']/'completed.json').exists())
    def test_same_serial_changed_state_still_rejects_saved_plan(self):
        self.apply(network=True);review=self.session.prepare(network_only=True)
        self.fake.states=copy.deepcopy(self.fake.states)
        self.fake.states['global'][0]['values']['id']='different-vpc-at-same-serial'
        with self.assertRaisesRegex(ValueError,'stale'):self.session.apply(review['plan_id'],review['confirmation'])
        self.assertFalse((self.session.directory/'plans'/review['plan_id']/'attempt.json').exists())
    def test_check_status_and_ordered_resource_values_are_not_ignored(self):
        value=dict(check_results=[dict(config_addr='var.a',status='pass',objects=None)],resources=[dict(values=['first','second'])])
        digest=p.state_digest(json.dumps(value).encode())
        value['check_results'][0]['status']='fail';self.assertNotEqual(digest,p.state_digest(json.dumps(value).encode()))
        value['check_results'][0]['status']='pass';value['resources'][0]['values'].reverse()
        self.assertNotEqual(digest,p.state_digest(json.dumps(value).encode()))
    def test_independent_confirmation(self):
        review=self.session.prepare()
        with self.assertRaisesRegex(ValueError,'confirmation'):self.session.apply(review['plan_id'],'yes')
    def test_partial_up_stops_and_reports_recovery(self):
        review=self.session.prepare();self.fake.fail=True
        with self.assertRaisesRegex(ValueError,'possible running'):self.session.apply(review['plan_id'],review['confirmation'])
        self.fake.fail=False
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.session.prepare()
        self.assertFalse((self.session.directory/'up-global-reconciled.json').exists())
    def test_partial_down_blocks_next_stage(self):
        self.all_up();self.shutdown();review=self.session.prepare(True);self.fake.fail=True
        with self.assertRaises(p.Failure):self.session.apply(review['plan_id'],review['confirmation'])
        self.fake.fail=False
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.session.prepare(True)
    def test_destroy_preview_before_inhibition_never_dispatches_mutation(self):
        self.all_up();self.fake.inhibited=False
        review=self.session.prepare(True)
        self.assertEqual(review['layer'],'edge');self.assertEqual(review['phase'],'REVIEW_REQUIRED_NOT_EXECUTED')
        self.assertFalse((self.session.directory/'shutdown-readback.json').exists())
        count=sum(a[0]=='terraform' and a[2]=='apply' for a in self.fake.calls)
        with self.assertRaisesRegex(ValueError,'inhibited'):self.session.apply(review['plan_id'],review['confirmation'])
        self.assertEqual(sum(a[0]=='terraform' and a[2]=='apply' for a in self.fake.calls),count)
        self.assertFalse((self.session.directory/'plans'/review['plan_id']/'attempt.json').exists())
    def test_later_layer_preview_is_not_out_of_order_authority(self):
        self.all_up();self.shutdown()
        review=self.session.prepare(True,down_layer='global');self.assertEqual(review['layer'],'global')
        with self.assertRaisesRegex(ValueError,'dependency order'):self.session.apply(review['plan_id'],review['confirmation'])
        for bad in ('prod','shared','security'):
            with self.assertRaisesRegex(ValueError,'original DEV'):self.session.prepare(True,down_layer=bad)
        with self.assertRaisesRegex(ValueError,'original DEV'):self.session.prepare(False,down_layer='global')
    def test_full_down_order_retains_backend_shared(self):
        self.all_up();self.shutdown();results=[self.apply(True)['layer'] for _ in p.DOWN];self.assertEqual(results,list(p.DOWN))
        self.assertFalse(any('delete-bucket' in a for a in self.fake.calls));self.assertNotIn('shared',self.fake.states)
    def test_sql_loss_is_independent(self):
        self.all_up();self.shutdown();self.apply(True);self.apply(True);self.apply(True);review=self.session.prepare(True)
        self.assertEqual(review['layer'],'data')
        with self.assertRaisesRegex(ValueError,'SQL'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_known_nat_effect_unknown_blocks(self):
        self.all_up();self.shutdown();self.fake.unknown=True
        review=self.session.prepare(True)
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_canonical_e13_absent_and_attributable_applied_before_destroy(self):
        self.all_up();self.shutdown();self.fake.unknown=True
        original=self.session.object
        def read(key):
            value=original(key)
            if key.endswith('/observed'):
                value.update(state='ABSENT',request_sha256=None,result=None)
            return value
        self.session.object=read
        # Same terminal representation accepted by the production E13 journal.
        from scripts.normal_delivery.delivery import Delivery
        value=read('recovery/dev/recovery/change_rt/op/change_rt/observed')
        Delivery.check_effect(None,value,value['token'],{'RouteTableId':'rtb-own'})
        self.assertEqual(self.apply(True)['layer'],'edge')
        def applied(key):
            value=original(key)
            if key.endswith('/observed'):value['state']='APPLIED'
            return value
        self.session.object=applied
        self.assertEqual(self.apply(True)['layer'],'apps')

    def test_noncanonical_or_foreign_e13_effect_never_dispatches_destroy(self):
        self.all_up();self.shutdown();self.fake.unknown=True
        original=self.session.object;review=self.session.prepare(True)
        changes=[dict(state='UNKNOWN',request_sha256=None,result=None),
                 dict(state='ABSENT'),dict(state='ABSENT',request_sha256=None),
                 dict(state='ABSENT',result=None),dict(state='ABSENT',request_sha256=None,result=None,token='foreign'),
                 dict(state='APPLIED',request_sha256='0'*64),dict(state='APPLIED',result={'RouteTableId':'foreign'})]
        count=sum(a[0]=='terraform' and a[2]=='apply' for a in self.fake.calls)
        for fields in changes:
            with self.subTest(fields=fields):
                def read(key):
                    value=original(key)
                    if key.endswith('/observed'):value.update(fields)
                    return value
                self.session.object=read
                with self.assertRaisesRegex(ValueError,'E13'):
                    self.session.apply(review['plan_id'],review['confirmation'])
                self.assertFalse((self.session.directory/'plans'/review['plan_id']/'attempt.json').exists())
        self.assertEqual(sum(a[0]=='terraform' and a[2]=='apply' for a in self.fake.calls),count)

    def test_asg_replacement_blocks(self):
        self.all_up();self.shutdown();self.fake.asg_busy=True
        review=self.session.prepare(True)
        with self.assertRaisesRegex(ValueError,'replacement'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_ecs_activity_blocks(self):
        self.all_up();self.shutdown();self.fake.ecs_busy=True
        review=self.session.prepare(True)
        with self.assertRaisesRegex(ValueError,'drained'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_metric_absence_is_not_zero(self):
        self.all_up();self.shutdown();self.fake.metrics=False
        review=self.session.prepare(True)
        with self.assertRaisesRegex(ValueError,'metric absence'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_controller_reactivation_blocks(self):
        self.all_up();self.shutdown();self.fake.inhibited=False
        review=self.session.prepare(True)
        with self.assertRaisesRegex(ValueError,'inhibited'):self.session.apply(review['plan_id'],review['confirmation'])
    def test_foreign_state_address(self):
        self.apply();self.fake.states['global'][0]['address']='aws_vpc.foreign'
        with self.assertRaisesRegex(ValueError,'foreign'):self.session.status()
    def test_extra_nested_root_rejected(self):
        (self.session.root('global')/'modules/vpc/evil.tf').write_text('resource "aws_vpc" "evil" {}')
        with self.assertRaisesRegex(ValueError,'extra'):self.session.prepare()
    def test_no_foreign_dependency_override(self):
        self.session.config['variables']['data']['private_subnet_ids']=['subnet-prod']
        with self.assertRaisesRegex(ValueError,'overrides'):self.session.variables('data')
    def test_residual_is_not_zero_bill_or_synthetic_proof(self):
        self.all_up();result=self.session.residual();self.assertFalse(result['zero_cost_claim']);self.assertFalse(result['aws_verified']);self.assertTrue(result['unverified']);self.assertIn('ECR/evidence',result['retained'])
    def test_inhibition_is_not_finality_and_no_resend(self):
        result=self.session.inhibit('INHIBIT DEV '+ACCOUNT+' '+REGION);self.assertIn('RECONCILE',result['stage'])
        with self.assertRaisesRegex(ValueError,'retry'):self.session.inhibit('INHIBIT DEV '+ACCOUNT+' '+REGION)
    def test_production_cli_uses_same_session(self):
        config=self.session.directory.parent/'config.json';config.write_text(json.dumps(self.config))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(p.main(['status','--config',str(config),'--directory',str(self.session.directory)],self.fake),0)
        self.assertFalse(json.loads(out.getvalue())['aws_verified'])
    def test_static_handoff_default_inert_and_exact_runtime_paths(self):
        value=wp5.foundations();self.assertIsNone(value['variable']['dev_operator_arn']['default'])
        expression=value['resource']['aws_s3_bucket_policy']['state']['policy']
        self.assertIn('E16ExclusiveDevRuntimeWriter',expression);self.assertIn('E16NoOtherDevObjects',expression)
        self.assertIn('each.key=="dev" && var.dev_operator_arn!=null',expression)
        self.assertNotIn('force-unlock',Path(p.__file__).read_text())

    def test_wrong_region_backend(self):
        foreign=p.Session(dict(self.config,region='us-west-2'),self.session.directory.parent/'foreign',self.fake)
        with self.assertRaisesRegex(ValueError,'region'):foreign.initialize()
    def test_failed_readback_cannot_complete_inhibition(self):
        self.all_up();self.shutdown();self.fake.metrics=False
        with self.assertRaises(ValueError):self.session.review_inhibition('REVIEW SUPERVISED DEV INHIBITION '+ACCOUNT+' '+REGION)
        self.assertFalse(json.loads((self.session.directory/'shutdown-readback.json').read_text())['reviewed'])

    def test_actual_verify_requires_gateway_sql_kms_readbacks(self):
        self.all_up();self.fake.verify_mode=True
        result=self.session.verify();self.assertEqual(result['stage'],'OBSERVED_GATEWAY_APPLICATION_ROUNDTRIP');self.assertFalse(result['aws_verified'])
        self.fake.ready=False
        with self.assertRaisesRegex(ValueError,'readiness'):self.session.verify()
    def test_stage_input_change_requires_new_binary_review(self):
        self.apply(network=True)
        self.session.config['variables']['global']['protected_nat_launch']['a']['id']='lt-00000003'
        review=self.session.prepare();self.assertEqual(review['layer'],'global')
        self.session.config['variables']['global']['protected_nat_launch']['a']['version']=2
        with self.assertRaisesRegex(ValueError,'confirmation/config'):self.session.apply(review['plan_id'],review['confirmation'])

    def test_verify_rejects_wrong_probe_name(self):
        self.all_up();self.fake.verify_mode=True;self.fake.probe_name='ready'
        with self.assertRaisesRegex(ValueError,'per-task readiness'):self.session.verify()
    def test_failure_context_does_not_expose_stderr(self):
        error=p.Failure(1,b'sensitive mock stderr','data:terraform apply')
        self.assertIn('data:terraform apply',str(error));self.assertNotIn('sensitive',str(error))

    def test_backend_workspace_listing_stays_in_runtime_prefix(self):
        init=[call for call in self.fake.calls if call[0]=='terraform' and 'init' in call]
        self.assertEqual(len(init),5)
        for call,layer in zip(init,p.UP):
            self.assertIn('-backend-config=workspace_key_prefix=e1/lifecycle/dev/'+layer+'/terraform.tfstate/workspaces',call)
        path=self.session.root('global')/'.terraform/terraform.tfstate'
        value=json.loads(path.read_text());value['backend']['config']['workspace_key_prefix']='env:';path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'exact original state'):self.session.state('global')
