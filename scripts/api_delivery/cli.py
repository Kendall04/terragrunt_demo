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
        dev = next((r for r in gh.deployments('dev') if r['application'] == app), None)
        m.require(dev is not None, 'exact application has no successful DEV deployment')
        m.git(ROOT, 'merge-base', '--is-ancestor', dev['source'], head)
        result = m.approval(pr, app, dev)
    current = gh.get(f'repos/{m.REPOSITORY}/pulls/{number}')
    m.require(current['head']['sha'] == head and current['base']['sha'] == base, 'PR changed during validation')
    write(output, dict(result, **run_metadata()))


def finish_promotion(gh, success):
    path = Path('promotion-check.json')
    if not path.exists():
        return
    check = json.loads(path.read_bytes())
    current = gh.get(f'repos/{m.REPOSITORY}/pulls/{check["pr"]}')
    success = success and current['head']['sha'] == check['head'] and current['base']['sha'] == check['base']
    gh.check(check['head'], 'success' if success else 'failure', check['id'])
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
    request = dict(environment=env, source=source, application=app, operation='deploy')
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
        if env == 'prod':
            prs = gh.get(f'repos/{m.REPOSITORY}/commits/{source}/pulls')
            prs = [p for p in prs if p['merge_commit_sha'] == source and p['base']['ref'] == 'main']
            m.require(len(prs) == 1, 'one merged promotion PR required')
            pr = gh.get(f'repos/{m.REPOSITORY}/pulls/{prs[0]["number"]}')
            parents = m.git(ROOT, 'show', '-s', '--format=%P', source).decode().strip().split()
            receipt = next((r for r in gh.promotion_receipts() if r['pr'] == pr['number'] and
                            r['head'] == pr['head']['sha'] and r['base'] == parents[0]), None)
            m.require(receipt is not None, 'retained approval for merged PR missing/expired')
            approved = m.promoted(pr, parents, app, receipt)
            m.require(approved is not None, 'app mutation without deployment approval')
            gh.require_promotion_check(receipt)
            request.update(approved=approved, promotion=receipt)
    write(output, request)
    outputs(deploy='true', environment=env)


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
    history = list(itertools.islice(gh.deployments(env), 30))
    if request['operation'] == 'rollback':
        m.require(len(history) >= 2, 'two retained healthy deployments required')
        previous = next((r for r in history[1:] if r['image'] != history[0]['image'] and
                         r['compatibility'] == cfg['compatibility']), None)
        m.require(previous is not None, 'no compatible previous healthy release')
        chosen = m.rollback(history[0], previous, env, cfg['compatibility'])
        image = chosen['image']
        request.update(source=chosen['source'], application=chosen['application'])
    elif env == 'prod':
        image = m.release(request['approved'], 'dev')['image']
    else:
        image = None
    operation = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{m.REPOSITORY}/{env}/{os.environ["GITHUB_RUN_ID"]}'))
    owner = aws.owner(clients, cfg, operation, request)
    m.require(owner.retained() is None, 'operation already completed; rerun must not redeploy')
    owner.acquire()
    with tempfile.TemporaryDirectory() as directory:
        port = aws.Runtime(clients, cfg, owner, operation, directory)
        try:
            if image is None:
                # ECR writes also occur while holding application ownership.
                image = owner.call(aws.publish, clients, cfg, request['source'],
                                   os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'])
            m.require(image.startswith(cfg['repository'] + '@sha256:'), 'image repository not admitted')
            name = cfg['repository'].split('/', 1)[1]
            images = clients['ecr'].describe_images(repositoryName=name, imageIds=[{'imageDigest': image.split('@')[1]}])['imageDetails']
            m.require(len(images) == 1 and images[0]['imageDigest'] == image.split('@')[1], 'ECR digest readback')
            if request['operation'] == 'rollback':
                live = port.snapshot()
                task = clients['ecs'].describe_task_definition(taskDefinition=live['active_revision'])['taskDefinition']
                m.require(all(c['image'] == history[0]['image'] for c in task['containerDefinitions']), 'current runtime not latest healthy history')
            result = deploy(port, image)
            record = dict(schema='API_RELEASE_V1', repository=m.REPOSITORY, environment=env, status='HEALTHY',
                          source=request['source'], application=request['application'], image=image,
                          profile='validated-v2', compatibility=cfg['compatibility'], operation=operation,
                          binding_sha256=reference['sha256'], **result, **run_metadata())
            m.release(record, env)
            port.journal('release', record)
            owner.finish(True, 'SUCCESS')
            write(output, record)
        except BaseException:
            # No force unlock or deadline-based release. Before/after route state
            # remains in AWS + immutable attempts for reconciliation.
            owner.finish(False, 'UNCERTAIN')
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('prepare', 'promotion', 'finish-promotion', 'execute'))
    parser.add_argument('--input', default='request.json')
    parser.add_argument('--output', default='evidence/result.json')
    parser.add_argument('--success', action='store_true')
    args = parser.parse_args(); gh = GitHub()
    if args.operation == 'prepare': prepare(gh, args.output)
    elif args.operation == 'promotion': promotion(gh, args.output)
    elif args.operation == 'finish-promotion': finish_promotion(gh, args.success)
    else: execute(gh, args.input, args.output)


if __name__ == '__main__':
    main()
