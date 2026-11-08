import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import original_dev as operator
from scripts.workflow_requests import client,contract as c

ACCOUNT='123456789012';REGION='us-east-1';COMMIT='b'*40
OP='11111111-1111-4111-8111-111111111111'
def request(layer='global'):
    return dict(operation_id=OP,operation='create',layer=layer,revision='a'*64,parameters={})
def configuration(identity):
    return dict(identity=identity,environment=c.environment(identity),account=ACCOUNT,region=REGION,workflow_commit=COMMIT,active=True,governance='ADMIN_VERIFIED_G1_G9',gateway_version='7',plan_binding=None)
def claims(identity):
    return dict(aud=c.AUDIENCE,sub=c.subject(identity,COMMIT),repository=c.REPOSITORY,ref=c.source_ref(identity),event_name='workflow_dispatch',job_workflow_ref=c.workflow(identity)+'@'+COMMIT,sha='a'*40)
class Port:
    def __init__(self,state='SUCCESS'):self.calls=[];self.state=state
    def invoke(self,value):self.calls.append(value);return value['operation_id']
    def status(self,operation):return dict(operation_id=operation,state=self.state,release_id=None,source_commit=None)
class Tests(unittest.TestCase):
    def test_all_original_layers_route_without_replacing_authority(self):
        for layer in operator.lifecycle.LAYERS:
            identity=operator.select('up',json.dumps(request(layer)))
            self.assertEqual(identity,'infra-high-risk-dev' if layer in ('data','apps') else 'infra-dev')
    def test_cli_delegates_exact_request_to_real_existing_execution(self):
        port=Port();identity='infra-dev';config=configuration(identity)
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'request.json';raw=json.dumps(request());file.write_text(raw)
            env=dict(E1_REQUEST_CONFIGURATION=json.dumps(config),ACTIONS_ID_TOKEN_REQUEST_URL='offline',ACTIONS_ID_TOKEN_REQUEST_TOKEN='offline')
            def entry():
                self.assertEqual(os.environ['E1_REQUEST'],raw)
                value=client.execute(identity,os.environ['E1_REQUEST'],config,claims(identity),port)
                self.assertEqual(value['state'],'SUCCESS')
            with patch.dict(os.environ,env,clear=True),patch.object(client,'main',side_effect=entry):
                self.assertEqual(operator.main(['up','--account',ACCOUNT,'--region',REGION,'--request-file',str(file)]),0)
                self.assertNotIn('E1_REQUEST',os.environ)
            self.assertEqual(port.calls,[request()])
    def test_uncertain_result_is_not_success_or_resend(self):
        for state in ('FAILURE','UNKNOWN','UNCERTAIN'):
            port=Port(state)
            with self.assertRaises(ValueError):client.execute('infra-dev',json.dumps(request()),configuration('infra-dev'),claims('infra-dev'),port)
            self.assertEqual(len(port.calls),1)
    def test_down_and_residual_block_before_credentials(self):
        for action in ('down','residual'):
            with patch.object(client,'main',side_effect=AssertionError('no authority')),self.assertRaisesRegex(ValueError,'uninstalled|whole DOWN'):
                operator.main([action,'--account',ACCOUNT,'--region',REGION])
    def test_prod_shared_and_foreign_fields_rejected(self):
        for change in ({'layer':'prod'},{'environment':'prod'},{'backend':'protected'},{'role_arn':'admin'}):
            with self.assertRaises(ValueError):operator.select('up',json.dumps(dict(request(),**change)))
    def test_no_reconcile_or_destroy_under_up(self):
        for operation in ('reconcile','teardown','plan'):
            with self.assertRaises(ValueError):operator.select('up',json.dumps(dict(request(),operation=operation)))
    def test_inactive_configuration_before_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'r.json';file.write_text(json.dumps(request()))
            with patch.dict(os.environ,{'E1_REQUEST_CONFIGURATION':json.dumps(dict(configuration('infra-dev'),active=False))},clear=True),patch.object(client,'main',side_effect=AssertionError('inactive')):
                with self.assertRaises(ValueError):operator.main(['up','--account',ACCOUNT,'--region',REGION,'--request-file',str(file)])
    def test_wrong_account_region_before_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'r.json';file.write_text(json.dumps(request()))
            for account,region in (('999999999999',REGION),(ACCOUNT,'us-west-2')):
                with patch.dict(os.environ,{'E1_REQUEST_CONFIGURATION':json.dumps(configuration('infra-dev'))},clear=True),patch.object(client,'main',side_effect=AssertionError('scope')):
                    with self.assertRaisesRegex(ValueError,'account/region'):operator.main(['up','--account',account,'--region',region,'--request-file',str(file)])
    def test_local_terminal_cannot_supply_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'r.json';file.write_text(json.dumps(request()))
            with patch.dict(os.environ,{'E1_REQUEST_CONFIGURATION':json.dumps(configuration('infra-dev'))},clear=True),self.assertRaisesRegex(ValueError,'entry job'):
                operator.main(['up','--account',ACCOUNT,'--region',REGION,'--request-file',str(file)])
    def test_release_and_digest_delivery_reuse_contracts(self):
        self.assertEqual(operator.select('release',json.dumps(dict(source_commit='a'*40))),'release')
        self.assertEqual(operator.select('deploy',json.dumps(dict(action='deliver',release_id='sha256-'+'a'*64,replicas=1))),'deploy-dev')
        with self.assertRaises(ValueError):operator.select('deploy',json.dumps(dict(action='deliver',release_id='latest',replicas=1)))
    def test_plan_and_preflight_not_full_application_health(self):
        self.assertEqual(operator.select('plan',json.dumps(dict(operation='plan',layer='global'))),'plan-dev')
        self.assertEqual(operator.select('verify-infrastructure',json.dumps(dict(operation='preflight',layer='apps'))),'plan-dev')
    def test_retired_supervised_entry_stops_before_credentials(self):
        with patch.object(client,'main',side_effect=AssertionError('no AWS')),self.assertRaisesRegex(ValueError,'executor retired'):
            operator.main(['dev','apply'])

    def test_original_source_graph_and_no_lab_left(self):
        root=operator.ROOT
        self.assertFalse((root/'scripts/simple_lab.py').exists());self.assertFalse((root/'scripts/lab_resources.py').exists())
        subnets=(root/'terraform/modules/target/dev/global/modules/vpc/subnets.tf').read_text()
        for name in ('public0','public1','private0','private1'):self.assertIn('"'+name+'"',subnets)
        nat=json.loads((root/'terraform/modules/target/dev/global/wp5-nat.tf.json').read_text())
        self.assertEqual(nat['resource']['aws_autoscaling_group']['wp5_nat']['desired_capacity'],1)
        self.assertIn('a',nat['variable']['protected_nat_launch']['validation']['condition'])
