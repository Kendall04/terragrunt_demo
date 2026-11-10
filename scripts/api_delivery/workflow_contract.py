"""Security invariants for four readable workflows, without a duplicate YAML copy."""
import json
from pathlib import Path
from .model import require


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
    require(job['needs']=='scope' and "needs.scope.outputs.deploy == 'true'" in job['if'], 'docs filtered before queue')
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
