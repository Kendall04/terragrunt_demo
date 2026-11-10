"""Security invariants for four readable workflows, without a duplicate YAML copy."""
import json
from pathlib import Path
from .model import require

WORKFLOWS = frozenset(name + '.yml' for name in ('api-delivery','api-execute','api-promotion','api-evaluate'))
GATE = "${{ (github.ref_name == 'develop' && vars.API_DEV_DELIVERY_ENABLED == 'true') || (github.ref_name == 'main' && vars.API_PROD_DELIVERY_ENABLED == 'true') }}"
ENVIRONMENT = "${{ github.event_name == 'workflow_dispatch' && format('api-{0}', github.event.inputs.environment) || (github.ref_name == 'develop' && 'api-dev' || 'api-prod') }}"
CHECKOUT = {'uses':'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803',
            'with':{'ref':'${{ github.sha }}','fetch-depth':0,'persist-credentials':False}}


def executable_steps(job, expected):
    # Names are editorial, but commands, conditions, IDs, actions and arguments
    # are the authority surface. Extra steps/env/working-directory are rejected.
    actual = [{k:v for k,v in step.items() if k != 'name'} for step in job['steps']]
    require(actual == expected, 'unexpected executable workflow surface')


def validate(root):
    folder=Path(root)/'.github/workflows'
    files={n:json.loads((folder/(n+'.yml')).read_text()) for n in ('api-delivery','api-execute','api-promotion','api-evaluate')}
    caller=files['api-delivery']; worker=files['api-execute']; evaluator=files['api-evaluate']['jobs']['promotion']
    require(caller['on']['push']['branches']==['develop','main'], 'protected push branches')
    gate=caller['jobs']['delivery']['if']
    require('API_DEV_DELIVERY_ENABLED' in gate and 'API_PROD_DELIVERY_ENABLED' in gate and 'API_DELIVERY_ENABLED' not in gate, 'independent activation')
    require(caller['jobs']['delivery']['uses']=='./.github/workflows/api-execute.yml','one executor')
    job=worker['jobs']['delivery']
    require(job['concurrency']==dict(group="e1-application-delivery-${{ github.event_name == 'workflow_dispatch' && github.event.inputs.environment || (github.ref_name == 'develop' && 'dev' || 'prod') }}", **{'cancel-in-progress':False,'queue':'max'}), 'serialized non-cancelling environment queue')
    require(job['needs']=='scope' and job['if']=="${{ needs.scope.outputs.deploy == 'true' }}", 'docs filtered before queue')
    require(job['permissions']==dict(contents='read',actions='read',**{'pull-requests':'read','id-token':'write','deployments':'write'}), 'delivery permissions')
    require(evaluator['permissions']==dict(contents='read',actions='read',**{'pull-requests':'read','checks':'write','deployments':'read'}), 'evaluator has no AWS/signing authority')
    require('environment' not in evaluator and len(evaluator['steps'])==2,'trusted evaluator isolation')
    checkout=evaluator['steps'][0]
    require(checkout['uses']=='actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803' and
            checkout['with']['ref']=='${{ github.sha }}' and checkout['with']['persist-credentials'] is False, 'trusted base checkout')
    require(evaluator['steps'][1]['run']=='python3 -B -m scripts.api_delivery.cli promotion','reviewed evaluator')
    steps=job['steps']; names=[s['name'] for s in steps]
    require(names.index('Wait for exact-SHA CI') < names.index('Acquire environment-only deployment identity') < names.index('Execute release or reconcile'), 'CI before AWS')
    require('API_HANDOVER_REF' in job['env'], 'writer transition required')
    for value in files.values():
        require('actions/attest@' not in json.dumps(value),'retired signing path')
        require(set(value)=={'name','on','permissions','jobs'} and value['permissions']=={'contents':'read'}, 'workflow authority surface')
    require(set(caller['jobs'])=={'delivery'} and set(worker['jobs'])=={'scope','delivery'} and
            set(files['api-evaluate']['jobs'])=={'promotion'} and set(files['api-promotion']['jobs'])=={'promotion'}, 'unexpected writer job')
    require(gate == GATE and worker['jobs']['scope']['if'] == GATE, 'activation binding')
    require(job['environment'] == ENVIRONMENT, 'environment identity')
    require(set(caller['jobs']['delivery'])=={'if','uses','permissions'} and
            caller['jobs']['delivery']['permissions']==job['permissions'], 'caller authority')
    promotion=files['api-promotion']['jobs']['promotion']
    require(set(promotion)=={'if','uses','permissions'} and promotion['uses']=='./.github/workflows/api-evaluate.yml' and
            promotion['permissions']==evaluator['permissions'], 'evaluator caller authority')
    require(files['api-evaluate']['on']==worker['on']=={'workflow_call':{}}, 'reusable workflows only')
    require(set(caller['on'])=={'push','workflow_dispatch'} and set(caller['on']['push'])=={'branches'}, 'delivery events')
    inputs=caller['on']['workflow_dispatch']['inputs']
    require(set(inputs)=={'environment','operation'} and inputs['environment']['options']==['dev','prod'] and
            inputs['operation']['options']==['rollback','reconcile'] and all(v['required'] and v['type']=='choice' for v in inputs.values()), 'manual recovery only')
    require(set(files['api-promotion']['on'])=={'pull_request_target','workflow_run'} and
            files['api-promotion']['on']['pull_request_target']['branches']==['main'] and
            files['api-promotion']['on']['workflow_run']=={'workflows':['API automatic delivery'],'types':['completed'],'branches':['develop']}, 'trusted promotion events')
    require(job['env']==dict(GH_TOKEN='${{ github.token }}',API_BINDING_REF='${{ vars.API_BINDING_REF }}',
            AWS_EC2_METADATA_DISABLED='true',API_ENV_ENABLED=GATE,API_HANDOVER_REF='${{ vars.API_HANDOVER_REF }}'), 'executor environment')
    scope=worker['jobs']['scope']
    require(scope['env']=={'API_ENV_ENABLED':GATE} and scope['permissions']=={'contents':'read'} and
            scope['outputs']=={'deploy':'${{ steps.scope.outputs.deploy }}'}, 'scope isolation')
    require(evaluator['env']=={'GH_TOKEN':'${{ github.token }}'}, 'evaluator environment')
    for item, keys in [(job,{'if','runs-on','timeout-minutes','environment','concurrency','permissions','env','steps','needs'}),
                       (scope,{'if','runs-on','permissions','timeout-minutes','outputs','steps','env'}),
                       (evaluator,{'runs-on','timeout-minutes','env','steps','permissions'})]:
        require(set(item)==keys and item['runs-on']=='ubuntu-latest', 'unreviewed execution context')
    executable_steps(scope,[CHECKOUT,{'id':'scope','run':'python3 -B -m scripts.api_delivery.cli scope'}])
    executable_steps(evaluator,[CHECKOUT,{'run':'python3 -B -m scripts.api_delivery.cli promotion'}])
    executable_steps(job,[CHECKOUT,
        {'run':'python3 -B -m scripts.api_delivery.cli preflight'},
        {'run':'python3 -m pip install --require-hashes -r scripts/wp4d/requirements-codebuild.lock\naws configure set cli_timestamp_format iso8601'},
        {'uses':'aws-actions/configure-aws-credentials@61815dcd50bd041e203e49132bacad1fd04d2708','with':{
            'role-to-assume':'${{ vars.API_DELIVERY_ROLE_ARN }}','aws-region':'${{ vars.API_REGION }}',
            'allowed-account-ids':'${{ vars.API_ACCOUNT_ID }}','role-session-name':'api-${{ github.run_id }}-${{ github.run_attempt }}',
            'role-duration-seconds':3600,'unset-current-credentials':True}},
        {'id':'execute','run':'python3 -B -m scripts.api_delivery.cli execute'},
        {'if':"steps.execute.outputs.publish == 'true'",'run':'python3 -B -m scripts.api_delivery.cli publish'},
        {'if':"always() && hashFiles('evidence/result.json') != ''",'uses':'actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',
         'with':{'name':'release-diagnostics-${{ github.run_attempt }}','path':'evidence/result.json'}}])
