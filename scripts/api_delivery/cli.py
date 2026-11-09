"""CLI used only by the three reviewed GitHub workflows; no manual image input."""
import argparse
import json
import itertools
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from . import model as m
from .github import GitHub
from . import receipts

ROOT = Path(__file__).resolve().parents[2]


def event():
    return json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(m.canonical(value))


def outputs(**values):
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        for key, value in values.items():
            stream.write(f'{key}={value}\n')


def run_metadata():
    return dict(run_id=int(os.environ['GITHUB_RUN_ID']), run_attempt=int(os.environ['GITHUB_RUN_ATTEMPT']))


def classify():
    """No AWS authority and no environment concurrency slot for docs-only runs."""
    name = os.environ['GITHUB_EVENT_NAME']; ev = event()
    if name == 'workflow_dispatch':
        outputs(deploy='true')
        return
    m.require(name == 'push' and not ev.get('forced') and not ev.get('deleted') and ev['before'] != '0'*40,
              'ordinary existing-branch push required')
    changed = m.application(ROOT, ev['before']) != m.application(ROOT, os.environ['GITHUB_SHA'])
    outputs(deploy='true' if changed else 'false')


def promotion(gh, output):
    ev = event()
    if os.environ['GITHUB_EVENT_NAME'] == 'pull_request_target':
        number = ev['pull_request']['number']
    else:
        trigger = ev['workflow_run']
        gh.trusted(trigger, m.DELIVERY, 'push', 'develop')
        prs = gh.get(f'repos/{m.REPOSITORY}/pulls?state=open&base=main&head=Kendall04:develop')
        if not prs:
            return
        m.require(len(prs) == 1, 'ambiguous promotion PR')
        number = prs[0]['number']
    pr = gh.get(f'repos/{m.REPOSITORY}/pulls/{number}')
    head, base = pr['head']['sha'], pr['base']['sha']
    check = gh.check(head, 'in_progress')
    write('promotion-check.json', dict(id=check['id'], head=head, pr=number, base=base))
    m.eligible_pr(pr)
    gh.require_merge_policy()
    m.require(pr['state'] == 'open' and not pr['draft'], 'open non-draft PR required')
    m.require(os.environ['GITHUB_SHA'] == base, 'rerun promotion against current main')
    # Fetch objects only. Never checkout, import or execute PR code.
    m.git(ROOT, 'fetch', '--no-tags', 'origin', head, base)
    m.git(ROOT, 'merge-base', '--is-ancestor', base, head)
    app = m.application(ROOT, head)
    if app == m.application(ROOT, base):
        result = dict(schema='API_PROMOTION_V1', repository=m.REPOSITORY, pr=number, head=head,
                      base=base, application=app, deployment=False)
    else:
        dev = next((r for r in gh.deployments('dev') if r['application'] == app and
                    m.same_application_lineage(ROOT, r['source'], head, app)), None)
        m.require(dev is not None, 'exact application has no successful DEV deployment')
        m.git(ROOT, 'merge-base', '--is-ancestor', dev['source'], head)
        result = m.approval(pr, app, dev)
        result['dev_receipt'] = gh.deployment_receipt(dev)
    current = gh.get(f'repos/{m.REPOSITORY}/pulls/{number}')
    m.require(current['head']['sha'] == head and current['base']['sha'] == base, 'PR changed during validation')
    execution = dict(event=os.environ['GITHUB_EVENT_NAME'], workflow_ref=os.environ['GITHUB_WORKFLOW_REF'],
                     workflow_sha=os.environ['GITHUB_WORKFLOW_SHA'])
    if execution['event'] == 'workflow_run':
        execution['trigger'] = dict(id=ev['workflow_run']['id'], attempt=ev['workflow_run']['run_attempt'],
                                    sha=ev['workflow_run']['head_sha'])
    write(output, dict(result, execution=execution, check_id=check['id'], **run_metadata()))


def finish_promotion(gh, success):
    path = Path('promotion-check.json')
    if not path.exists():
        return
    check = json.loads(path.read_bytes())
    current = gh.get(f'repos/{m.REPOSITORY}/pulls/{check["pr"]}')
    success = success and current['state'] == 'open' and current['head']['sha'] == check['head'] and current['base']['sha'] == check['base']
    locator = None
    if success:
        try:
            bundle = json.loads(Path(os.environ['RECEIPT_BUNDLE']).read_bytes())
            descriptor = json.loads(Path('evidence/slot.json').read_bytes())
            locator = receipts.compact(descriptor,bundle,receipts.publisher())
            # GitHub may truncate external_id. Read it back before success; the
            # source of approval is the published attestation, never this file.
            gh.check(check['head'], 'in_progress',check['id'],locator=locator)
            observed = gh.get(f'repos/{m.REPOSITORY}/check-runs/{check["id"]}')
            m.require(observed['head_sha'] == check['head'] and observed['app']['id'] == 15368 and
                      observed['status'] == 'in_progress' and json.loads(observed['external_id']) == locator,
                      'compact check locator readback differs')
            receipt = gh.promotion_artifact(locator, completed=False)
            m.require(receipt == json.loads(Path('evidence/result.json').read_bytes()) and
                      receipt['check_id'] == check['id'], 'published receipt differs')
            gh.require_merge_policy()
        except Exception:
            gh.check(check['head'], 'failure', check['id'])
            raise
    gh.check(check['head'], 'success' if success else 'failure', check['id'], locator=locator if success else None)
    m.require(success, 'promotion check failed')


def prepare(gh, output):
    ev = event(); name = os.environ['GITHUB_EVENT_NAME']; branch = os.environ['GITHUB_REF_NAME']
    m.require(branch in ('develop', 'main'), 'protected branch required')
    m.require(os.environ['GITHUB_WORKFLOW_REF'] == m.REPOSITORY + '/' + m.DELIVERY + '@refs/heads/' + branch,
              'only the automatic delivery caller may execute')
    env = 'dev' if branch == 'develop' else 'prod'; source = os.environ['GITHUB_SHA']
    m.require(os.environ['GITHUB_REPOSITORY'] == m.REPOSITORY, 'repository mismatch')
    gh.wait_checks(source, branch)
    app = m.application(ROOT, source)
    request = dict(environment=env, source=source, event_source=source, application=app, operation='deploy')
    if name == 'workflow_dispatch':
        env = ev['inputs']['environment']
        m.require(env in ('dev', 'prod') and branch == ('develop' if env == 'dev' else 'main'), 'rollback branch/environment mismatch')
        request.update(environment=env, operation='rollback')
    else:
        m.require(name == 'push' and not ev.get('deleted') and not ev.get('forced'), 'ordinary push required')
        before = ev['before']
        m.require(before != '0' * 40, 'branch creation is not a release')
        if m.application(ROOT, before) == app:
            outputs(deploy='false', environment=env)
            return
        if env == 'dev':
            gh.require_app_validation(source, branch)
        if env == 'prod':
            prs = gh.get(f'repos/{m.REPOSITORY}/commits/{source}/pulls')
            prs = [p for p in prs if p['merge_commit_sha'] == source and p['base']['ref'] == 'main']
            m.require(len(prs) == 1, 'one merged promotion PR required')
            pr = gh.get(f'repos/{m.REPOSITORY}/pulls/{prs[0]["number"]}')
            parents = m.git(ROOT, 'show', '-s', '--format=%P', source).decode().strip().split()
            receipt, locator = gh.promotion_receipt(pr)
            approved = m.promoted(pr, parents, app, receipt)
            m.require(approved is not None, 'app mutation without deployment approval')
            request.update(approved=approved, promotion=receipt, approval=locator)
    write(output, request)
    outputs(deploy='true', environment=env)


def superseded(request, output):
    write(output,dict(schema='API_NO_DEPLOYMENT_V1',reason='superseded',environment=request['environment'],
                      event_source=request['event_source'],**run_metadata()))
    outputs(deployed='false', receipt='true', reason='superseded')


def execute(gh, request_path, output):
    from . import aws
    from .executor import deploy
    from scripts import environment_mutation as e2
    request = json.loads(Path(request_path).read_bytes()); env = request['environment']
    m.require(os.environ.get('API_CD_ENABLED') == 'true', 'activation not installed')
    reference = json.loads(os.environ['API_BINDING_REF'])
    clients = aws.clients(reference['region']); cfg = aws.binding(reference, env, clients)
    # Before credentials can mutate anything, the runtime verifies all retired
    # automatic entrypoints are still disabled/fail-closed. Settings are not edited.
    for workflow in ('cd.yml', 'cd-terragrunt.yml'):
        settings = gh.get(f'repos/{m.REPOSITORY}/actions/workflows/{workflow}')
        m.require(settings['state'] == 'disabled_manually', 'historical delivery workflow enabled')
    m.require(os.environ.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch'), 'PR receives no AWS authority')
    if env == 'prod' and request['operation'] == 'deploy':
        gh.require_promotion_rule()
    operation = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{m.REPOSITORY}/{env}/{os.environ["GITHUB_RUN_ID"]}'))
    owner = aws.owner(clients, cfg, operation, request)
    terminal = owner.retained()
    if terminal is not None:
        # Publication-only recovery, before acquire/build/ECR/ECS. A SUCCESS
        # terminal with no real release is not sufficient evidence.
        recovered = aws.recover_release(gh, clients, cfg, owner, operation, request)
        if recovered['schema'] == 'API_SUPERSEDED_DECISION_V1':
            superseded(request, output)
            return
        write(output,recovered)
        outputs(deployed='true',recovered='true')
        return
    # Resolve missing publication BEFORE taking E2. Otherwise this read-only
    # failure displaces B's released head and consumes C's operation as FAILURE,
    # preventing either rerun from recovering. Immutable evidence is still
    # admitted against current ECS/configuration under E2 below.
    eligible = request['operation'] != 'deploy' or current_request(gh, request)
    if not eligible:
        # A stale request needs no mutation authority. Acquiring just to record
        # a no-op would displace B's released head while B awaits publication.
        # Do not bless a retained/uncertain owner or an operation missing its
        # own terminal. This read-only disposition creates no E2 terminal.
        head, _ = owner.store.read()
        m.require(head['state'] == 'RELEASED' and head['operation'] != operation,
                  'superseded request cannot settle retained or incomplete ownership')
        superseded(request, output)
        return
    history = list(itertools.islice(gh.deployments(
        env, exclude_run=int(os.environ['GITHUB_RUN_ID']), allow_queued=True), 1))
    owner.acquire()
    with tempfile.TemporaryDirectory() as directory:
        port = aws.Runtime(clients, cfg, owner, operation, directory)
        try:
            # Checked under E2, before build, registration or traffic. A rerun of
            # an old source cannot roll back a newer branch application. A docs
            # descendant with identical application identity does not obsolete B.
            if request['operation'] == 'deploy' and not current_request(gh, request):
                # Positive, immutable evidence BEFORE settling E2. SUCCESS or
                # absence of a healthy release alone cannot recover an omission.
                m.require(not owner.touched, 'superseded after possible effects')
                port.journal('release',dict(schema='API_SUPERSEDED_DECISION_V1',reason='superseded',
                    phase='before-application-effects',environment=env,operation=operation,
                    request_sha256=owner.request_sha256,event_source=request['event_source'],
                    generation=owner.value['generation'],producer=receipts.publisher(),**run_metadata()))
                owner.finish(True, 'SUCCESS')
                superseded(request, output)
                return
            image = None
            if env == 'prod' and request['operation'] == 'deploy':
                # Recheck exact GitHub approval and exact DEV S3 version using the
                # destination role, never latest DEV or an unversioned S3 key.
                receipt = gh.promotion_artifact({k:v for k,v in request['approval'].items() if k != 'check_id'})
                m.require(receipt == request['promotion'], 'approval changed before execution')
                aws.verify_manifest(clients, cfg['dev_evidence'], request['approved'])
                image = m.release(request['approved'], 'dev')['image']
                aws.verify_image(clients, cfg, image)
            # Admission needs the current release only; rollback is sealed in
            # its previous field. Do not read unrelated expired older artifacts.
            previous = port.admit_current(history, reference['sha256'])
            if request['operation'] == 'rollback':
                m.require(history and previous is not None, 'verified current release required')
                chosen = m.recovery_target(history[0].get('previous'), env, cfg['compatibility'])
                m.require(chosen['image'] != previous['image'], 'no distinct previous recovery target')
                image = chosen['image']
                request.update(source=chosen['source'], application=chosen['application'])
            if image is None:
                # ECR writes also occur while holding application ownership.
                image = owner.call(aws.publish, clients, cfg, request['source'],
                                   os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'])
            aws.verify_image(clients, cfg, image)
            result = deploy(port, image)
            record = dict(schema='API_RELEASE_V1', repository=m.REPOSITORY, environment=env, status='HEALTHY',
                          source=request['source'], application=request['application'], image=image,
                          profile='validated-v2', compatibility=cfg['compatibility'], operation=operation,
                          binding_sha256=reference['sha256'], event_source=request['event_source'], previous=previous,
                          configuration_ref=port.configuration_ref,
                          approval=request.get('approval'), producer=receipts.publisher(),
                          request_sha256=owner.request_sha256, **result, **run_metadata())
            m.release(record, env)
            record['manifest_ref'] = port.journal('release', record)
            owner.finish(True, 'SUCCESS')
            write(output, record)
            outputs(deployed='true')
        except BaseException:
            # No force unlock or deadline-based release. Before/after route state
            # remains in AWS + immutable attempts for reconciliation.
            owner.finish(False, 'UNCERTAIN' if owner.touched else 'FAILURE')
            raise


def current_request(gh, request):
    branch = 'develop' if request['environment'] == 'dev' else 'main'
    tip = gh.get(f'repos/{m.REPOSITORY}/git/ref/heads/{branch}')['object']['sha']
    m.git(ROOT, 'fetch', '--no-tags', 'origin', tip)
    m.git(ROOT, 'merge-base', '--is-ancestor', request['event_source'], tip)
    return m.same_application_lineage(ROOT, request['event_source'], tip, request['application'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('classify', 'prepare', 'promotion', 'finish-promotion', 'execute', 'receipt-files', 'verify-receipt'))
    parser.add_argument('--input', default='request.json')
    parser.add_argument('--output', default='evidence/result.json')
    parser.add_argument('--success', action='store_true')
    parser.add_argument('--kind', choices=('deployment','promotion'))
    parser.add_argument('--recovered', action='store_true')
    args = parser.parse_args(); gh = GitHub()
    if args.operation == 'classify': classify()
    elif args.operation == 'prepare': prepare(gh, args.output)
    elif args.operation == 'promotion': promotion(gh, args.output)
    elif args.operation == 'finish-promotion': finish_promotion(gh, args.success)
    elif args.operation == 'receipt-files': receipts.prepare_files(args.input,args.kind,args.recovered)
    elif args.operation == 'verify-receipt':
        descriptor = json.loads(Path('evidence/slot.json').read_bytes())
        bundle = json.loads(Path(os.environ['RECEIPT_BUNDLE']).read_bytes())
        sealed = receipts.compact(descriptor,bundle,receipts.publisher())
        record, _ = receipts.resolve(gh,descriptor,sealed,completed=False)
        m.require(record == json.loads(Path(args.input).read_bytes()), 'published deployment differs')
    else: execute(gh, args.input, args.output)


if __name__ == '__main__':
    main()
