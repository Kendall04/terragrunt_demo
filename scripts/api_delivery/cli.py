"""Four workflow commands: scope, execute, publish, promotion.

Normal delivery never asks an operator to select a commit or digest. Rollback
and reconciliation are explicit environment operations in the same job queue.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import tempfile
import uuid
from . import model as m
from .github import GitHub, PREFIX

ROOT = Path(__file__).resolve().parents[2]


def event():
    return json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())


def outputs(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for key, value in values.items(): stream.write(f'{key}={value}\n')


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(m.canonical(value))


def request():
    branch = os.environ['GITHUB_REF_NAME']; source = os.environ['GITHUB_SHA']; ev = event()
    m.require(os.environ['GITHUB_REPOSITORY'] == m.REPOSITORY and branch in ('develop','main'), 'protected source required')
    env = 'dev' if branch == 'develop' else 'prod'
    m.require(os.environ.get('API_ENV_ENABLED') == 'true', 'environment delivery disabled')
    m.require(os.environ['GITHUB_WORKFLOW_REF'] == m.REPOSITORY + '/' + m.DELIVERY + '@refs/heads/' + branch, 'delivery caller')
    action = 'deploy'
    if os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch':
        m.require(ev['inputs']['environment'] == env, 'environment/branch mismatch')
        action = ev['inputs']['operation']
        m.require(action in ('rollback','reconcile'), 'unsupported manual operation')
    else:
        m.require(os.environ['GITHUB_EVENT_NAME'] == 'push' and not ev.get('forced') and not ev.get('deleted'), 'ordinary merge push required')
    return dict(environment=env, source=source, event_source=source, application=m.application(ROOT, source), action=action,
                run_id=int(os.environ['GITHUB_RUN_ID']), run_attempt=int(os.environ['GITHUB_RUN_ATTEMPT']))


def scope():
    req = request(); ev = event()
    changed = req['action'] != 'deploy' or m.application(ROOT, ev['before']) != req['application']
    outputs(deploy=str(changed).lower())


def current(gh, req):
    branch = 'develop' if req['environment'] == 'dev' else 'main'
    tip = gh.get(PREFIX + '/git/ref/heads/' + branch)['object']['sha']
    m.git(ROOT, 'fetch', '--no-tags', 'origin', tip)
    return m.same_application_lineage(ROOT, req['event_source'], tip, m.application(ROOT, req['event_source']))


def record(req, cfg, result, image, previous, configuration, operation):
    value = dict(schema='API_RELEASE_V1',repository=m.REPOSITORY,environment=cfg['environment'],status='HEALTHY',
        source=req['source'],event_source=req['event_source'],application=req['application'],image=image,
        profile='validated-v2',compatibility=cfg['compatibility'],previous=previous,configuration_ref=configuration,
        operation=operation,run_id=req['run_id'],run_attempt=req['run_attempt'],approval=req.get('approval'),
        verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),**result)
    return m.release(value)


def reconcile(port, state, cfg):
    """No ECS/ALB mutation. Accept only a completely observed settled topology."""
    candidate = state.get('candidate'); snap = port.snapshot()
    if candidate and snap['active_revision'] == candidate['revision']:
        other = 'green' if candidate['color'] == 'blue' else 'blue'
        m.require(snap['routes'] == (candidate['color'], other) and snap['active'] == candidate['color'] and snap['inactive_count'] == snap['pending'] == 0 and
                  snap['active_count'] == cfg['replicas'], 'candidate transition not settled')
        # Verify exact registered configuration, real cohort and SQL/KMS now.
        target = dict(schema='API_RECOVERY_TARGET_V1',kind='automatic',environment=cfg['environment'],
            source=state['request']['source'],application=state['request']['application'],image=state['image'],
            profile='validated-v2',compatibility=cfg['compatibility'],**candidate)
        expected = port.current_configuration(target)
        from . import aws
        aws.verify_image(port.aws,cfg,state['image'])
        actual = port.aws['ecs'].describe_task_definition(taskDefinition=candidate['revision'])['taskDefinition']
        aws.task_readback(expected, actual, cfg['account'], cfg['region'])
        port.tasks(candidate['color'],candidate['revision'],state['image']); port.client_ready()
        value = record(state['request'],cfg,dict(color=candidate['color'],revision=candidate['revision'],per_task_ready=True,client_ready=True),
                       state['image'],state['previous'],candidate['configuration_ref'],state['operation'])
        # Reconciliation has its own journal; never overwrite a prior attempt.
        value['manifest_ref'] = port.journal('release',value)
        return value
    port.admit_current([state['current']] if state.get('current') else [], state['binding_sha256'])
    return state.get('current')


def execute(gh, output):
    from . import aws
    from .state import State, handover
    from .executor import deploy
    req = request(); env = req['environment']; branch = 'develop' if env == 'dev' else 'main'
    gh.wait_checks(req['event_source'], branch)
    for name in ('cd.yml','cd-terragrunt.yml'):
        m.require(gh.get(PREFIX+'/actions/workflows/'+name)['state'] == 'disabled_manually', 'historical writer enabled')
    reference=json.loads(os.environ['API_BINDING_REF']); clients=aws.clients(reference['region'])
    cfg=aws.binding(reference,env,clients)
    handover(clients,cfg,json.loads(os.environ['API_HANDOVER_REF']),reference['sha256'])
    store=State(clients,cfg); state=store.read()
    operation=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{m.REPOSITORY}/{env}/{req["run_id"]}/{req["run_attempt"]}'))
    with tempfile.TemporaryDirectory() as directory:
        port=aws.Runtime(clients,cfg,operation,directory)
        if req['action'] == 'reconcile':
            value=reconcile(port,state,cfg)
            state.update(phase='HEALTHY',current=value,github_id=None if value != state.get('current') else state.get('github_id'),candidate=None)
            store.write(state)
            if value: write(output,value); outputs(publish='true')
            return
        m.require(state['phase'] == 'HEALTHY', 'previous operation unfinished; run explicit reconcile')
        # Re-publish the completed operation before considering newer source. No
        # build/ECR/ECS call repeats after a failed GitHub publication.
        if state.get('current') and not state.get('github_id'):
            m.require(state['current']['run_id'] == req['run_id'], 'publish previous release using reconcile before delivery')
            port.admit_current([state['current']],reference['sha256'])
            write(output,state['current']); outputs(publish='true'); return
        if req['action'] == 'deploy' and not current(gh,req):
            outputs(publish='false',reason='superseded'); return
        if req['action'] == 'deploy' and state.get('current') and state['current']['run_id'] == req['run_id']:
            outputs(publish='false',reason='already-deployed'); return
        previous=port.admit_current([state['current']] if state.get('current') else [],reference['sha256'])
        image=None
        if req['action'] == 'rollback':
            m.require(state.get('current'), 'current release missing')
            chosen=m.recovery_target(state['current'].get('previous'),env,cfg['compatibility'])
            m.require(chosen['image'] != state['current']['image'], 'no distinct compatible previous version')
            req.update(source=chosen['source'],application=chosen['application']); image=chosen['image']
        elif env == 'prod':
            prs=gh.get(f'{PREFIX}/commits/{req["source"]}/pulls')
            prs=[p for p in prs if p['merge_commit_sha']==req['source'] and p['base']['ref']=='main']
            m.require(len(prs)==1,'one merged promotion PR required')
            pr=gh.get(f'{PREFIX}/pulls/{prs[0]["number"]}')
            parents=m.git(ROOT,'show','-s','--format=%P',req['source']).decode().split()
            approved,req['approval']=gh.approval(pr,parents,req['application'])
            m.require(approved is not None,'application change requires DEV release')
            aws.verify_manifest(clients,cfg['dev_evidence'],approved); image=approved['image']
        if image: aws.verify_image(clients,cfg,image)
        state.update(phase='DEPLOYING',operation=operation,request=req,previous=previous,candidate=None,
                     image=image,binding_sha256=reference['sha256'])
        store.write(state)
        original_register=port.register
        def register(color, uri):
            revision=original_register(color,uri)
            state['candidate']=dict(color=color,revision=revision,configuration_ref=port.configuration_ref)
            store.write(state)
            return revision
        port.register=register
        try:
            if image is None:
                image=aws.publish(clients,cfg,req['source'],str(req['run_id']),str(req['run_attempt']))
            aws.verify_image(clients,cfg,image); state['image']=image; store.write(state)
            value=record(req,cfg,deploy(port,image),image,previous,port.configuration_ref,operation)
            value['manifest_ref']=port.journal('release',value)
            state.update(phase='HEALTHY',current=value,github_id=None,candidate=None)
            store.write(state); write(output,value); outputs(publish='true')
        except BaseException:
            state['phase']='RECONCILE'
            store.write(state)
            raise


def publish(gh, path):
    from . import aws
    from .state import State
    value=json.loads(Path(path).read_bytes()); reference=json.loads(os.environ['API_BINDING_REF'])
    clients=aws.clients(reference['region']); cfg=aws.binding(reference,value['environment'],clients)
    store=State(clients,cfg); state=store.read()
    m.require(state['phase']=='HEALTHY' and state['current']==value,'publication differs from current healthy release')
    aws.verify_manifest(clients,dict(bucket=cfg['evidence_bucket'],account=cfg['account'],region=cfg['region'],
                                    kms_key=cfg['evidence_kms_key'],environment=cfg['environment']),value)
    state['github_id']=gh.publish(value); store.write(state)


def promotion(gh):
    ev=event(); name=os.environ['GITHUB_EVENT_NAME']
    if name=='pull_request_target': numbers=[ev['pull_request']['number']]
    else:
        m.require(name=='workflow_run' and ev['workflow_run']['event']=='push','promotion event')
        numbers=[p['number'] for p in gh.pages(PREFIX+'/pulls?state=open&base=main') if p['head']['ref']=='develop']
    for number in numbers:
        pr=gh.get(f'{PREFIX}/pulls/{number}'); head=pr['head']['sha']; base=pr['base']['sha']
        check=gh.check(head)
        try:
            gh.require_promotion_rule(); m.eligible_pr(pr)
            m.require(pr['state']=='open' and m.git(ROOT,'rev-parse','HEAD').decode().strip()==base,'trusted base checkout required')
            if name=='pull_request_target':
                m.require((ev['pull_request']['head']['sha'],ev['pull_request']['base']['sha'])==(head,base),'event is stale')
            m.git(ROOT,'fetch','--no-tags','origin',head)
            app=m.application(ROOT,head); release_id=0
            if app != m.application(ROOT,base):
                for ident, value in gh.releases():
                    if value['application']==app and m.same_application_lineage(ROOT,value['source'],head,app):
                        release_id=ident; break
                m.require(release_id,'this application version has no healthy DEV release')
            locator=dict(v=2,pr=number,base=base,app=app,release=release_id,
                         run=int(os.environ['GITHUB_RUN_ID']),attempt=int(os.environ['GITHUB_RUN_ATTEMPT']))
            gh.check(head,check_id=check['id'],locator=locator)
            observed=gh.get(f'{PREFIX}/check-runs/{check["id"]}')
            m.require(observed['head_sha']==head and observed['app']['id']==15368 and
                      observed['name']=='API Promotion Validation' and json.loads(observed['external_id'])==locator,'check locator readback')
            if release_id: gh.release(release_id)
            fresh=gh.get(f'{PREFIX}/pulls/{number}')
            m.require(fresh['state']=='open' and (fresh['head']['sha'],fresh['base']['sha'])==(head,base),'PR changed during evaluation')
            gh.check(head,'success',check['id'],locator)
        except Exception:
            gh.check(head,'failure',check['id']); raise


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=('scope','preflight','execute','publish','promotion'))
    parser.add_argument('--file',default='evidence/result.json'); args=parser.parse_args(); gh=GitHub()
    if args.command=='scope': scope()
    elif args.command=='preflight':
        req=request(); gh.wait_checks(req['source'],'develop' if req['environment']=='dev' else 'main')
    elif args.command=='execute': execute(gh,args.file)
    elif args.command=='publish': publish(gh,args.file)
    else: promotion(gh)


if __name__=='__main__': main()
