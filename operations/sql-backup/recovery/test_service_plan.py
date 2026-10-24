"""Offline proposed service cutover metadata; fixtures are NOT authenticated facts."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import tempfile
import prepare


def deny_external(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn'):
        raise AssertionError('OFFLINE_SERVICE_PLAN_EXTERNAL_EFFECT_DENIED')
sys.addaudithook(deny_external)


def fixture():
    name='r20261024c1t'
    origin={'accountId':prepare.ACCOUNT,'region':prepare.REGION,'instanceId':'i-'+'1'*17,'availabilityZone':'us-east-1a'}
    target=dict(origin,instanceId='i-'+'2'*17,availabilityZone='us-east-1b')
    base=f'arn:aws:elasticloadbalancing:{prepare.REGION}:{prepare.ACCOUNT}:'
    return {'Trial':name,'ColdReceipt':{'Trial':name,'Status':'TARGET_RECOVERED_REVIEW_EVIDENCE','Checkdb':'RESTORED_CHECKDB_READABLE',
        'Source':origin,'Target':target,'ReadyAndDecryptedMarkersConfirmedUtc':'2026-10-24T19:08:00Z',
        'ColdFence':{'Status':'EXACT_SOURCE_TERMINATED','Source':copy.deepcopy(origin),'Target':copy.deepcopy(target),
            'ControlPlaneSha256':'c'*64,'TargetLaunchUtc':'2026-10-24T19:02:00Z','ObservedUtc':'2026-10-24T19:09:00Z'}},
      'RecoveryRequestedUtc':'2026-10-24T19:00:00Z','ReviewedUtc':'2026-10-24T19:10:00Z',
      'Network':{'AppVpcId':'vpc-'+'a'*17,'DbVpcId':'vpc-'+'a'*17,'DbInstanceId':target['instanceId'],
        'DbPrivateIp':'10.77.1.8','DbSubnetCidr':'10.77.1.0/24','DbSgId':'sg-'+'b'*17,'TaskSgId':'sg-'+'c'*17,
        'DbIngress':[{'Protocol':'tcp','FromPort':1433,'ToPort':1433,'SourceSecurityGroupId':'sg-'+'c'*17}],
        'SqlBoundAddresses':['10.77.1.8'],'HasPublicIpv4':False},
      'Connection':{'SecretArn':f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/app-connection-fixture',
        'VersionId':'d'*32,'Endpoint':'10.77.1.8','Database':'recoverydb_restore_'+name,
        'TextKeyArn':prepare.TEXT_KEY,'BackupKeyArn':prepare.BACKUP_KEY,'SecretKeyArn':prepare.TEXT_KEY},
      'Release':{'release_id':'sha256-'+'e'*64,'image_uri':f'{prepare.ACCOUNT}.dkr.ecr.{prepare.REGION}.amazonaws.com/demo-shared-demo-ms@sha256:'+'e'*64,
        'schema_sha256':'f'*64,'restored_schema_sha256':'f'*64,'rollback_schema_sha256':'f'*64,
        'rollback_history':'11111111-1111-4111-8111-111111111111'},
      'Delivery':{'operation_id':'22222222-2222-4222-8222-222222222222','rollback_operation_id':'33333333-3333-4333-8333-333333333333',
        'active_color':'blue','candidate_color':'green','replicas':1,
        'listener_arn':base+'listener/app/demo-dev-internal-alb/aaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbb',
        'rule_arn':base+'listener-rule/app/demo-dev-internal-alb/aaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbb/cccccccccccccccc',
        'active_target_arn':base+'targetgroup/demo-dev-blue/aaaaaaaaaaaaaaaa',
        'candidate_target_arn':base+'targetgroup/demo-dev-green/bbbbbbbbbbbbbbbb'},
      'PublicApiId':'abc123def4','PublicUrl':f'https://abc123def4.execute-api.{prepare.REGION}.amazonaws.com'}


def synthetic_taskdef(value):
    """Synthetic review fixture, never labelled as renderer output or native ECS."""
    color = value['Delivery']['candidate_color']
    name = 'demo-dev-app-api-' + color
    x = json.loads((Path(__file__).resolve().parents[3] / 'demo-api/deploy/task-definition.template.json').read_text(encoding='utf-8'))
    x.update(family=name,executionRoleArn=f'arn:aws:iam::{prepare.ACCOUNT}:role/{name}-exec-role',
             taskRoleArn=f'arn:aws:iam::{prepare.ACCOUNT}:role/{name}-task-role')
    for index,c in enumerate(x['containerDefinitions']):
        c['name'] = name + ('-readiness-probe' if index else '')
        c['image'] = value['Release']['image_uri']
        c['logConfiguration']['options'] = {'awslogs-group':'/aws/ecs/' + name,
            'awslogs-region':prepare.REGION,'awslogs-stream-prefix':c['name']}
    x['containerDefinitions'][0]['environment'] = [
        {'name':'AWS_REGION','value':prepare.REGION},{'name':'APP_ENV','value':'dev'},
        {'name':'DEPLOYMENT','value':color},{'name':'KMS_KEY_ID','value':prepare.TEXT_KEY},
        {'name':'Database__RunMigrationsOnStartup','value':'false'}]
    x['containerDefinitions'][0]['secrets'][0]['valueFrom'] = value['Connection']['SecretArn'] + ':::' + value['Connection']['VersionId']
    return x


class ServicePlanTests(unittest.TestCase):
    def test_real_gateway_validator_and_renderer_arguments_without_authority(self):
        v=fixture();result=prepare.service_plan(v)
        self.assertEqual(json.loads(result['GatewayRequest']['body'])['action'],'deliver')
        self.assertEqual(json.loads(result['RollbackRequest']['body'])['action'],'rollback-release')
        self.assertIn('scripts/render-demo-api-taskdef.sh',result['RendererArguments'])
        self.assertEqual(result['ConnectionMetadata']['SecretReference'],v['Connection']['SecretArn']+':::'+'d'*32)
        self.assertFalse(result['AllowsActivation']);self.assertFalse(result['EvidenceAuthenticated'])
        self.assertFalse(result['FullEcsRecoveryProven']);self.assertFalse(result['TaskTemplateAutomaticallyChanged'])
        self.assertFalse(result['PublicChecks']['BeforeTrafficSwitch'])
        self.assertTrue(result['PublicChecks']['BeforeMarkingReady'])
        self.assertTrue(any('migrations' in x for x in result['BlockingLiveGates']))

    def test_taskdef_review_binds_profile_image_roles_secret_and_inert_cli(self):
        v=fixture();candidate=synthetic_taskdef(v)
        result=prepare.service_taskdef(v,candidate)
        self.assertFalse(result['AllowsActivation']);self.assertFalse(result['EvidenceAuthenticated'])
        self.assertFalse(result['PublicApiRecoveryProven']);self.assertTrue(result['RequiresNewTasks'])
        self.assertEqual(result['Status'],'OFFLINE_RECOVERY_TASKDEF_REVIEW_PASS')
        plan=prepare.service_plan(v)
        self.assertIn('--recovery',plan['RendererArguments'])
        self.assertTrue(plan['RecoveryProfileEnforcedByRenderer'])
        self.assertEqual([r['Method'] for r in plan['PublicChecks']['Requests']],['GET','GET','POST','GET'])
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/'input.json';inp.write_text(json.dumps(v),encoding='utf-8')
            task=Path(d)/'task.json';task.write_text(json.dumps(candidate),encoding='utf-8')
            with patch.object(sys,'argv',['prepare.py','service-taskdef','--trial',v['Trial'],'--input',str(inp),'--evidence',str(task)]),redirect_stdout(io.StringIO()) as out:
                prepare.main()
            self.assertEqual(json.loads(out.getvalue())['TaskDefinitionSha256'],result['TaskDefinitionSha256'])

    def test_taskdef_review_rejects_migrations_secret_drift_probe_privileges_or_command_override(self):
        v=fixture()
        for change in (
            lambda x:x['containerDefinitions'][0]['environment'][-1].update(value='true'),
            lambda x:x['containerDefinitions'][0]['environment'].pop(),
            lambda x:x['containerDefinitions'][0]['secrets'][0].update(valueFrom=v['Connection']['SecretArn']),
            lambda x:x['containerDefinitions'][0]['secrets'][0].update(valueFrom=v['Connection']['SecretArn']+':::'+'e'*32),
            lambda x:x.update(taskRoleArn=x['executionRoleArn']),
            lambda x:x['containerDefinitions'][1].update(essential=True),
            lambda x:x['containerDefinitions'][1].update(environment=[{'name':'DB_CONN_STRING','value':'SYNTHETIC_PRIVATE'}]),
            lambda x:x['containerDefinitions'][1].update(image='unrelated:latest'),
            lambda x:x['containerDefinitions'][0].update(command=['unexpected']),
            lambda x:x['containerDefinitions'][0]['environment'].append({'name':'DB_CONN_STRING','value':'SYNTHETIC_PRIVATE'})):
            candidate=synthetic_taskdef(v);change(candidate)
            with self.assertRaisesRegex(ValueError,'RECOVERY_TASKDEF_NOT_EXACT_REVIEWED_PROJECTION'):
                prepare.service_taskdef(v,candidate)

    def test_unfenced_wrong_source_stale_and_prepared_receipts_refuse(self):
        for change in (
            lambda v:v['ColdReceipt'].update(ColdFence=None),
            lambda v:v['ColdReceipt']['ColdFence'].update(Status='SOURCE_QUIESCENT'),
            lambda v:v['ColdReceipt']['ColdFence']['Source'].update(instanceId='i-'+'9'*17),
            lambda v:v.update(ReviewedUtc='2026-10-24T19:30:00Z'),
            lambda v:v['ColdReceipt']['ColdFence'].update(TargetLaunchUtc='2026-10-24T18:00:00Z')):
            v=fixture();change(v)
            with self.assertRaises(ValueError):prepare.service_plan(v)

    def test_foreign_endpoint_vpc_instance_listener_and_ingress_refuse(self):
        for change in (
            lambda v:v['Connection'].update(Endpoint='10.77.1.99'),
            lambda v:v['Network'].update(DbVpcId='vpc-'+'d'*17),
            lambda v:v['Network'].update(DbInstanceId='i-'+'9'*17),
            lambda v:v['Network'].update(SqlBoundAddresses=['0.0.0.0']),
            lambda v:v['Network'].update(HasPublicIpv4=True),
            lambda v:v['Network'].update(DbPrivateIp='169.254.169.254',DbSubnetCidr='169.254.0.0/16'),
            lambda v:v['Network'].update(DbSubnetCidr='0.0.0.0/0'),
            lambda v:v['Network'].update(DbIngress=[{'Protocol':'tcp','FromPort':1433,'ToPort':1433,'CidrIp':'0.0.0.0/0'}])):
            v=fixture();change(v)
            with self.assertRaises(ValueError):prepare.service_plan(v)

    def test_rollback_schema_image_secret_or_key_mismatch_refuse(self):
        for change in (
            lambda v:v['Release'].update(rollback_schema_sha256='a'*64),
            lambda v:v['Release'].update(schema_sha256='a'*64),
            lambda v:v['Release'].update(image_uri=v['Release']['image_uri'].split('@')[0]+':latest'),
            lambda v:v['Connection'].update(SecretArn=prepare.SA_SECRET),
            lambda v:v['Connection'].update(Password='SYNTHETIC_SHOULD_NOT_BE_ALLOWED'),
            lambda v:v['Connection'].update(TextKeyArn=prepare.BACKUP_KEY),
            lambda v:v['Connection'].update(SecretKeyArn=prepare.BACKUP_KEY),
            lambda v:v['Connection'].update(VersionId='AWSCURRENT')):
            v=fixture();change(v)
            with self.assertRaises(ValueError):prepare.service_plan(v)

    def test_foreign_routing_or_public_host_and_invalid_gateway_payload_refuse(self):
        for change in (
            lambda v:v.update(PublicUrl='https://unrelated.example.invalid'),
            lambda v:v['Delivery'].update(candidate_color='blue'),
            lambda v:v['Delivery'].update(rollback_operation_id=v['Delivery']['operation_id']),
            lambda v:v['Delivery'].update(operation_id='not-an-operation'),
            lambda v:v['Delivery'].update(listener_arn=v['Delivery']['listener_arn'].replace(prepare.ACCOUNT,'000000000000')),
            lambda v:v['Release'].update(rollback_history='not-an-operation')):
            v=fixture();change(v)
            with self.assertRaises(ValueError):prepare.service_plan(v)

    def test_cli_offline_does_not_enter_terraform_renderer_or_add_secret_values(self):
        v=fixture()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'input.json';path.write_text(json.dumps(v),encoding='utf-8')
            with patch.object(sys,'argv',['prepare.py','service-plan','--trial',v['Trial'],'--input',str(path)]), \
                 patch.object(prepare,'render',side_effect=AssertionError('WRONG_RENDER_PATH')),redirect_stdout(io.StringIO()) as output:
                prepare.main()
            result=json.loads(output.getvalue())
            self.assertEqual(result['Status'],'SERVICE_CUTOVER_DRY_PLAN')
            self.assertNotIn('Password',output.getvalue());self.assertNotIn('ConnectionString=',output.getvalue())


if __name__=='__main__':unittest.main()
