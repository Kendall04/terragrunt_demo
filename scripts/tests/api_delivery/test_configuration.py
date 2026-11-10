"""Preserved configuration/queue regressions, independent of retired receipts."""
import base64
import copy
import importlib.util
import io
import json
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from test_delivery import ROOT, config, record, authorization_task, ACCOUNT, REGION
from scripts.api_delivery import aws, model as m

class ObjectS3:
    def __init__(self,record,scope):self.record,self.scope=record,scope
    def get_object(self,**kw):
        if kw['VersionId'] != self.record['manifest_ref']['version']:raise ValueError('version differs')
        return dict(Body=io.BytesIO(m.canonical({k:v for k,v in self.record.items() if k!='manifest_ref'})),
            VersionId=kw['VersionId'],ServerSideEncryption='aws:kms',SSEKMSKeyId=self.scope['kms_key'],BucketKeyEnabled=False)

def configuration_fixture(cfg, deployment):
    task=authorization_task(cfg['colors'][deployment['color']])
    app=next(c for c in task['containerDefinitions'] if c['essential'])
    app['secrets'][0]['valueFrom']=cfg['colors'][deployment['color']]['secret_arn']+':::'+cfg['secret_version']
    trust=m.canonical({'fixture':'v1'})
    app['environment'] += [{'name':'Database__SecurityProfile','value':'validated-v2'},
                           {'name':'Database__RunMigrationsOnStartup','value':'false'},
                           {'name':'SQL_TRUST_MANIFEST_B64','value':base64.b64encode(trust).decode()},
                           {'name':'SQL_TRUST_MANIFEST_SHA256','value':m.sha(trust)}]
    value=dict(schema='API_TASK_CONFIGURATION_V1',environment=cfg['environment'],color=deployment['color'],
               image=deployment['image'],revision=deployment['revision'],task=task)
    ref=dict(bucket=cfg['evidence_bucket'],key=deployment['manifest_ref']['key'].replace('release.json','002-task-configuration.json'),
             version='configuration-v1',sha256=m.sha(m.canonical(value)))
    return value,ref


class ConfigurationTests(unittest.TestCase):
    def setup_port(self):
        old=config();latest=record();value,ref=configuration_fixture(old,latest)
        latest['configuration_ref']=ref
        latest['manifest_ref']['sha256']=m.sha(m.canonical({k:v for k,v in latest.items() if k!='manifest_ref'}))
        new=copy.deepcopy(old);new['secret_version']='b'*32;new['trust']['fixture_revision']='v2'
        port=aws.Runtime.__new__(aws.Runtime);port.config=new
        initial=dict(routes=('blue','green'),active='blue',inactive='green',active_revision=latest['revision'],
                     active_count=1,inactive_count=0,pending=0)
        port.snapshot=lambda:initial;port.journal=Mock();port.client_ready=Mock();port.tasks=Mock()
        v2=copy.deepcopy(value['task']);app=next(c for c in v2['containerDefinitions'] if c['essential'])
        app['secrets'][0]['valueFrom']=new['colors']['blue']['secret_arn']+':::'+new['secret_version']
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']='b'*64
        port.render=Mock(return_value=v2)
        actual=dict(copy.deepcopy(value['task']),revision=2,status='ACTIVE',taskDefinitionArn=latest['revision'])
        scope=dict(bucket=old['evidence_bucket'],account=ACCOUNT,region=REGION,kms_key=old['evidence_kms_key'],environment='dev')
        manifests=ObjectS3(latest,scope)
        def get_object(**kw):
            if kw['Key']==ref['key']:
                self.assertEqual(kw['VersionId'],ref['version'])
                return dict(Body=io.BytesIO(m.canonical(value)),VersionId=ref['version'],ServerSideEncryption='aws:kms',
                            SSEKMSKeyId=scope['kms_key'],BucketKeyEnabled=False)
            return manifests.get_object(**kw)
        port.aws={'ecs':SimpleNamespace(describe_task_definition=Mock(return_value={'taskDefinition':actual})),
                  's3':SimpleNamespace(get_object=Mock(side_effect=get_object))}
        return port,latest,value,actual

    def test_active_v1_is_admitted_from_immutable_evidence_when_candidate_uses_v2(self):
        port,latest,old,actual=self.setup_port()
        with patch.object(aws,'verify_image'):
            target=port.admit_current([latest],'b'*64)
        self.assertEqual(target['configuration_ref'],latest['configuration_ref'])
        port.render.assert_not_called()
        port.client_ready.assert_called_once()
        self.assertEqual(port.config['secret_version'],'b'*32)
        self.assertTrue(next(c for c in actual['containerDefinitions'] if c['essential'])['secrets'][0]['valueFrom'].endswith('a'*32))

    def test_real_active_drift_missing_evidence_or_lost_compatibility_is_rejected(self):
        for fault in ('secret','trust','image','missing','hash','version','compatibility','health'):
            port,latest,value,actual=self.setup_port()
            app=next(c for c in actual['containerDefinitions'] if c['essential'])
            if fault=='secret':app['secrets'][0]['valueFrom']=app['secrets'][0]['valueFrom'][:-32]+'c'*32
            if fault=='trust':next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']='0'*64
            if fault=='image':app['image']='substituted'
            if fault=='missing':latest.pop('configuration_ref')
            if fault=='hash':value['task']['cpu']='999'
            if fault=='version':
                original=port.aws['s3'].get_object.side_effect
                def wrong_version(**kw):
                    response=original(**kw)
                    if 'task-configuration' in kw['Key']:response['VersionId']='other-version'
                    return response
                port.aws['s3'].get_object.side_effect=wrong_version
            if fault=='compatibility':port.config['compatibility']='0'*64
            if fault=='health':port.client_ready.side_effect=ValueError('old credentials or CA no longer work')
            # Keep the release authentically consistent with its fixture record.
            if fault=='missing':
                with patch.object(aws,'verify_manifest'),patch.object(aws,'verify_image'):
                    with self.assertRaises(ValueError):port.admit_current([latest],'b'*64)
            else:
                with patch.object(aws,'verify_image'):
                    with self.subTest(fault=fault),self.assertRaises(ValueError):port.admit_current([latest],'b'*64)
            port.journal.assert_not_called()

    def test_native_baseline_requires_exact_configuration_and_current_health(self):
        port,latest,value,_=self.setup_port()
        target=dict(schema='API_RECOVERY_TARGET_V1',kind='native-admission',configuration_ref=latest['configuration_ref'],
                    **{k:latest[k] for k in ('environment','source','application','image','compatibility','profile','revision','color')})
        port.config['native_baseline']=target
        with patch.object(aws,'verify_image'):
            self.assertEqual(port.admit_current([],'b'*64)['configuration_ref'],latest['configuration_ref'])
            target.pop('configuration_ref')
            with self.assertRaises(ValueError):port.admit_current([],'b'*64)

    def test_register_archives_candidate_v2_not_historical_v1(self):
        port,latest,value,_=self.setup_port()
        with patch.object(aws,'verify_image'):
            port.admit_current([latest],'b'*64)
        port.journal.reset_mock()
        revision=latest['revision'].replace('-blue:2','-green:3')
        candidate=dict(latest,color='green',revision=revision)
        candidate_value,_=configuration_fixture(port.config,candidate)
        new_task=candidate_value['task'];port.render.return_value=new_task
        app=next(c for c in new_task['containerDefinitions'] if c['essential'])
        trust=m.canonical({'fixture':'v2'})
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_B64')['value']=base64.b64encode(trust).decode()
        next(e for e in app['environment'] if e['name']=='SQL_TRUST_MANIFEST_SHA256')['value']=m.sha(trust)
        observed=dict(copy.deepcopy(new_task),taskDefinitionArn=revision,status='ACTIVE',revision=3)
        port.aws['ecs'].describe_task_definition.return_value={'taskDefinition':observed}
        port.mutate=Mock(return_value={'taskDefinition':observed})
        port.journal.return_value=dict(latest['configuration_ref'],version='configuration-v2')
        self.assertEqual(port.register('green',latest['image']),revision)
        stage,saved=port.journal.call_args.args
        self.assertEqual(stage,'task-configuration');self.assertEqual(saved['task'],new_task)
        self.assertEqual(saved['color'],'green');self.assertEqual(saved['revision'],revision)
        self.assertEqual(port.configuration_ref['version'],'configuration-v2')
        self.assertTrue(next(c for c in saved['task']['containerDefinitions'] if c['essential'])['secrets'][0]['valueFrom'].endswith('b'*32))


class QueueLintTests(unittest.TestCase):
    def test_narrow_queue_bridge_preserves_all_other_workflow_fields(self):
        spec=importlib.util.spec_from_file_location('lint_actions',ROOT/'.github/scripts/ci/lint-actions.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        original=json.loads((ROOT/'.github/workflows/api-execute.yml').read_bytes())
        normalized=json.loads(module.normalize(json.dumps(original)))
        expected=copy.deepcopy(original);del expected['jobs']['delivery']['concurrency']['queue']
        self.assertEqual(normalized,expected)
        for change in ({'queue':'single'},{'queue':True},{'cancel-in-progress':True},{'unexpected':False}):
            invalid=copy.deepcopy(original);invalid['jobs']['delivery']['concurrency'].update(change)
            with self.assertRaises(ValueError):module.normalize(json.dumps(invalid))
        bad=copy.deepcopy(original);bad['jobs']['delivery']['steps'][0]['uses']='not-a-valid-action'
        self.assertEqual(json.loads(module.normalize(json.dumps(bad)))['jobs']['delivery']['steps'][0]['uses'],'not-a-valid-action')
        with self.assertRaisesRegex(ValueError,'duplicate'):module.normalize('{"jobs":{},"jobs":{}}')
