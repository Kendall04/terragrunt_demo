"""Fixed WP6 workflows. JSON is a YAML subset; no template evaluation.

Canonical approvals are empty. Installed immutable pins can only come from the
security-admin-owned registry. No symbolic fallback or guessed pin is emitted.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.workflow_requests import contract as c

CHECKOUT='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'
TERRAFORM='hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd'
INPUT={'request':{'type':'string','required':True,'description':'Closed operation JSON; never AWS resource or credential inputs.'}}
ORDER=('shared','secrets','global','platform','edge','data','apps')
OUTPUTS={name:{'value':'${{ jobs.request.outputs.'+name+' }}'} for name in ('operation_id','release_id','state')}

def entry(identity):
    # Environment variables become available only in the protected job. This
    # bootstrap is stdlib-only and executes before any OIDC token acquisition when prerequisites are missing; a GitHub
    # token then binds the immutable checkout before any AWS credential exists.
    bootstrap=r"""python3 -I -B - <<'PY'
import base64,json,os,re,urllib.request
try:
    raw=os.environ['E1_REQUEST_CONFIGURATION']
    assert len(raw.encode())<=65536
    v=json.loads(raw)
    assert v['active'] is True and v['governance']=='ADMIN_VERIFIED_G1_G9'
    assert v['identity']=='EXPECTED_IDENTITY' and os.environ['GITHUB_REPOSITORY']=='Kendall04/terragrunt_demo'
    assert os.environ['GITHUB_REF']=='EXPECTED_REF'
    assert os.environ['GITHUB_EVENT_NAME'] in ('push','workflow_dispatch','workflow_call')
    assert re.fullmatch('[0-9a-f]{40}',v['workflow_commit']) and v['workflow_commit']!='0'*40
    endpoint=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    req=urllib.request.Request(endpoint+('&' if '?' in endpoint else '?')+'audience=sts.amazonaws.com',headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urllib.request.urlopen(req,timeout=10) as response:token=json.loads(response.read(32769))['value']
    claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
    expected='Kendall04/terragrunt_demo/.github/workflows/EXPECTED_CONTEXT.yml@'+v['workflow_commit']
    assert claims['aud']=='sts.amazonaws.com' and claims['job_workflow_ref']==expected
    assert claims['sub']=='repo:Kendall04/terragrunt_demo:environment:EXPECTED_CONTEXT:job_workflow_ref:'+expected
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('commit='+v['workflow_commit']+'\n')
except Exception:raise SystemExit('E1_INSTALLATION_OR_GOVERNANCE_MISSING') from None
PY""".replace("EXPECTED_IDENTITY",identity).replace("EXPECTED_REF",c.source_ref(identity)).replace("EXPECTED_CONTEXT",c.CONTEXTS[identity])
    steps=[{'name':'Require protected installation and governance','id':'installation','shell':'bash','run':bootstrap},
        {'name':'Checkout only approved controller source','uses':CHECKOUT,'with':{
            'repository':c.REPOSITORY,'ref':'${{ steps.installation.outputs.commit }}','persist-credentials':False}},
        {'name':'Verify checkout identity','shell':'bash','env':{'EXPECTED_COMMIT':'${{ steps.installation.outputs.commit }}'},
            'run':'test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"'}]
    if identity.startswith('plan-'):steps.append({'uses':TERRAFORM,'with':{'terraform_version':'1.13.4','terraform_wrapper':False}})
    steps.append({'name':'Closed protected request and observed completion','id':'request','shell':'bash',
        'run':'python3 -I -B scripts/workflow_requests/client.py '+identity})
    return {'name':'E1 protected '+identity,'on':{'workflow_call':{'inputs':INPUT,'outputs':OUTPUTS}},
        'permissions':{'contents':'read','id-token':'write'},'jobs':{'request':{
            'runs-on':'ubuntu-latest','timeout-minutes':40,'environment':c.CONTEXTS[identity],
            'outputs':{k:'${{ steps.request.outputs.'+k+' }}' for k in OUTPUTS},
            'env':{'E1_IDENTITY':identity,'E1_REQUEST_CONFIGURATION':'${{ vars.E1_REQUEST_CONFIGURATION }}','E1_REQUEST':'${{ inputs.request }}'},
            'steps':steps}}}

def call(identity,request,approvals,**options):
    if identity not in approvals:
        return dict({'runs-on':'ubuntu-latest','permissions':{},'steps':[{'run':
            'echo "::error::E1 '+identity+' is inactive: no verified immutable workflow pin, installation and governance binding."; exit 1'}]},**options)
    c.subject(identity,approvals[identity]['workflow_commit'])
    return dict({'uses':c.workflow(identity)+'@'+approvals[identity]['workflow_commit'],
        'permissions':{'contents':'read','id-token':'write'},'with':{'request':request}},**options)

def dump_request(value):return json.dumps(value,separators=(',',':'))

def callers(approvals):
    result={}
    def workflow(name,inputs,jobs,triggers=None):
        return {'name':name,'on':triggers or {'workflow_dispatch':{'inputs':inputs},'workflow_call':{'inputs':inputs}},
            'permissions':{'contents':'read'},'concurrency':{'group':'e1-'+name.replace(' ','-')+'-${{ github.ref }}','cancel-in-progress':False},'jobs':jobs}
    # Public application requests preserve artifact identity and report only the
    # independently qualified release, never CodeBuild's transport success.
    result['release-build.yml']=workflow('Release Build',{}, {'release':call('release',dump_request({'source_commit':'${{ github.sha }}'}),approvals,
        **{'if':"${{ github.ref == '"+c.source_ref('release')+"' }}"})})
    delivery={'release_id':{'type':'string','required':True},'replicas':{'type':'number','default':1,'required':False}}
    deliver=dump_request({'action':'deliver','release_id':'${{ inputs.release_id }}','replicas':'REPLICAS'})
    deliver=deliver.replace('"REPLICAS"','${{ inputs.replicas }}')
    result['deploy-dev.yml']=workflow('Deploy Dev',delivery,{'deploy':call('deploy-dev',deliver,approvals,**{'if':"${{ github.ref == '"+c.source_ref('deploy-dev')+"' }}"})})
    result['promote-prod.yml']=workflow('Promote Prod',delivery,{'promote':call('promote-prod',deliver,approvals,**{'if':"${{ github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch' }}"})})
    envinput={'environment':{'type':'string','required':True,'description':'dev or prod; selects disjoint fixed entry jobs.'}}
    rollback=dict(envinput,history={'type':'string','required':True},replicas=delivery['replicas'])
    payload=dump_request({'action':'rollback-release','history':'${{ inputs.history }}','replicas':'REPLICAS'}).replace('"REPLICAS"','${{ inputs.replicas }}')
    result['rollback-manifest.yml']=workflow('Rollback Manifest',rollback,{env:call(identity,payload,approvals,**{'if':"${{ inputs.environment == '"+env+"' && github.ref == 'refs/heads/"+('main' if env=='prod' else 'develop')+"' && github.event_name == 'workflow_dispatch' }}"}) for env,identity in [('dev','deploy-dev'),('prod','promote-prod')]})
    result['cd-rollback.yml']=workflow('Emergency Recovery',envinput,{env:call('emergency-'+env,'{}',approvals,**{'if':"${{ inputs.environment == '"+env+"' && github.ref == 'refs/heads/"+('main' if env=='prod' else 'develop')+"' && github.event_name == 'workflow_dispatch' }}"}) for env in ('dev','prod')})
    lifecycle=dict(envinput,request=INPUT['request'])
    jobs={}
    for identity in ('infra-dev','infra-prod','infra-high-risk-dev','infra-high-risk-prod'):
        selected="(contains(fromJSON('[\"data\",\"apps\"]'),fromJSON(inputs.request).layer) || fromJSON(inputs.request).operation == 'teardown')" if 'high-risk' in identity else "(!contains(fromJSON('[\"data\",\"apps\"]'),fromJSON(inputs.request).layer) && fromJSON(inputs.request).operation != 'teardown')"
        jobs[identity]=call(identity,'${{ inputs.request }}',approvals,**{'if':"${{ inputs.environment == '"+c.environment(identity)+"' && github.ref == '"+c.source_ref(identity)+"' && "+selected+" }}"})
    result['cd-terragrunt.yml']=workflow('Protected Environment Lifecycle',lifecycle,jobs)
    # Independent production path takes a previously qualified ID; there is no
    # build-on-main, dev-success-to-prod credential inheritance or override flag.
    result['cd-demo-api.yml']=workflow('Application CD',{}, {
        'infra-ready':call('plan-dev',dump_request({'operation':'preflight','layer':'apps'}),approvals,**{'if':"${{ github.ref == 'refs/heads/develop' }}"}),
        'release':call('release',dump_request({'source_commit':'${{ github.sha }}'}),approvals,needs=['infra-ready']),
        'deploy':call('deploy-dev',dump_request({'action':'deliver','release_id':'${{ needs.release.outputs.release_id }}','replicas':1}),approvals,needs=['release'])})
    planinputs=dict(envinput,request=INPUT['request'])
    result['ci-terragrunt-plan.yml']=workflow('Protected Read Only Plan',planinputs,{env:call('plan-'+env,'${{ inputs.request }}',approvals,**{'if':"${{ inputs.environment == '"+env+"' && github.ref == '"+c.source_ref('plan-'+env)+"' && github.event_name != 'pull_request' }}"}) for env in ('dev','prod')})
    result['ci-terragrunt-manual.yml']=workflow('Manual Read Only Plan',planinputs,{'plan':{'uses':'./.github/workflows/ci-terragrunt-plan.yml','permissions':{'contents':'read','id-token':'write'},'with':{'environment':'${{ inputs.environment }}','request':'${{ inputs.request }}'}}},triggers={'workflow_dispatch':{'inputs':planinputs}})
    jobs={'scope':{'uses':'./.github/workflows/cd-scope.yml','permissions':{'contents':'read','pull-requests':'read'}}}
    # Preserve the accepted safe sequence first, then approved data/apps.
    # Preparing an ID conveys no authority. High-risk administration approves the
    # exact emitted request independently before releasing its environment gate.
    prepare=r"""python3 -I -B - <<'PY'
import json,os,uuid
safe=os.environ['SAFE'].splitlines();high=os.environ['HIGH'].splitlines()
assert set(safe)<=set(('shared','secrets','global','platform','edge'))
assert set(high)<=set(('data','apps/fargate','apps'))
with open(os.environ['GITHUB_OUTPUT'],'a') as f:
    for layer in ('shared','secrets','global','data','platform','apps','edge'):
        revision=os.environ['HIGH_REVISION'] if layer in ('data','apps') else os.environ['REVISION']
        value={'operation_id':str(uuid.uuid4()),'operation':'reconcile','layer':layer,'revision':revision,'parameters':{}}
        f.write(layer+'='+json.dumps(value,separators=(',',':'))+'\n')
        if layer in high or (layer=='apps' and 'apps/fargate' in high):print(json.dumps(value,separators=(',',':')))
PY"""
    for env in ('dev','prod'):
        branch='main' if env=='prod' else 'develop'
        name='prepare-'+env
        jobs[name]={'needs':['scope'],'if':"${{ github.ref == 'refs/heads/"+branch+"' && needs.scope.outputs.critical_manual_only_changed != 'true' && needs.scope.outputs.unmapped_high_risk_paths == '' }}",'runs-on':'ubuntu-latest','permissions':{},
            'outputs':{k:'${{ steps.requests.outputs.'+k+' }}' for k in ('shared','secrets','global','data','platform','apps','edge')},
            'steps':[{'id':'requests','shell':'bash','env':{'SAFE':'${{ needs.scope.outputs.safe_layers }}','HIGH':'${{ needs.scope.outputs.high_risk_layers }}','REVISION':'${{ vars.E1_INFRA_'+env.upper()+'_REVISION }}','HIGH_REVISION':'${{ vars.E1_INFRA_HIGH_RISK_'+env.upper()+'_REVISION }}'},'run':prepare}]}
        previous=[]
        for layer in ORDER:
            key=env+'-'+layer;high=layer in ('data','apps');identity=('infra-high-risk-' if high else 'infra-')+env
            selector='high_risk_layers' if high else 'safe_layers'
            guards=["github.ref == 'refs/heads/"+branch+"'", "needs['"+name+"'].result == 'success'", "contains(needs.scope.outputs."+selector+", '"+layer+"')"]
            guards+= ["(needs['"+prior+"'].result == 'success' || needs['"+prior+"'].result == 'skipped')" for prior in previous]
            jobs[key]=call(identity,"${{ needs['"+name+"'].outputs."+layer+" }}",approvals,needs=['scope',name,*previous],**{'if':'${{ always() && '+' && '.join(guards)+' }}'})
            previous.append(key)
    devinfra=['dev-'+layer for layer in ORDER]
    jobs['infra-ready']=call('plan-dev',dump_request({'operation':'preflight','layer':'apps'}),approvals,needs=['scope','prepare-dev',*devinfra],**{'if':"${{ always() && github.ref == 'refs/heads/develop' && needs['prepare-dev'].result == 'success' && needs.scope.outputs.app_changed == 'true' && "+' && '.join("(needs['"+name+"'].result == 'success' || needs['"+name+"'].result == 'skipped')" for name in devinfra)+" }}"})
    jobs['release']=call('release',dump_request({'source_commit':'${{ github.sha }}'}),approvals,needs=['infra-ready'])
    jobs['deploy']=call('deploy-dev',dump_request({'action':'deliver','release_id':'${{ needs.release.outputs.release_id }}','replicas':1}),approvals,needs=['release'])
    jobs['critical-blocked']={'needs':['scope'],'if':"${{ needs.scope.outputs.critical_manual_only_changed == 'true' || needs.scope.outputs.unmapped_high_risk_paths != '' }}",'runs-on':'ubuntu-latest','permissions':{},'steps':[{'run':'echo "::error::Critical or unmapped infrastructure requires the protected manual lifecycle path; application delivery blocked."; exit 1'}]}
    jobs['prod-notice']={'needs':['scope'],'if':"${{ github.ref == 'refs/heads/main' && needs.scope.outputs.app_changed == 'true' }}",'runs-on':'ubuntu-latest','permissions':{},'steps':[{'run':'echo "Production promotion requires the separate manual promote-prod request with the exact qualified release ID." >> "$GITHUB_STEP_SUMMARY"'}]}
    result['cd.yml']=workflow('CD Orchestrator',{},jobs,triggers={'push':{'branches':['develop','main'],'paths':['terraform/**','demo-api/**','scripts/**','.github/**','ci/**']}})
    return result

def render(root,approvals):
    result={'.github/workflows/'+c.CONTEXTS[k]+'.yml':entry(k) for k in c.IDENTITIES}
    result.update({'.github/workflows/'+name:value for name,value in callers(approvals).items()})
    return {name:json.dumps(value,indent=2)+'\n' for name,value in result.items()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args()
    doc=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
    for name,text in render(ROOT,doc.get('wp6',{}).get('approvals',{})).items():
        path=ROOT/name
        if args.write:path.write_text(text,encoding='utf-8',newline='\n')
        elif path.read_text()!=text:raise SystemExit('WP6_WORKFLOW_DRIFT: '+name)
    print('WP6 fixed YAML workflows PASS; installation/governance UNVERIFIED')

if __name__=='__main__':main()
