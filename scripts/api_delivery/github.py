"""Durable GitHub deployment index; S3 remains the deployment authority.

Protected workflows publish task=api-release. PROD verifies exact S3 bytes
with its own role. No artifacts, attestations or historical attempt enumeration.
"""
import json
import os
import subprocess
import time
from . import model as m

PREFIX = 'repos/' + m.REPOSITORY
BOT = 'github-actions[bot]'
CHECK = 'API Promotion Validation'


class GitHub:
    def request(self, path, method='GET', body=None):
        m.require(path == PREFIX or path.startswith(PREFIX + '/'), 'repository scope')
        args = ['gh', 'api', '-X', method, path]
        if body is not None: args += ['--input', '-']
        raw = subprocess.check_output(args, input=None if body is None else m.canonical(body), timeout=90)
        return json.loads(raw) if raw.strip() else None

    def get(self, path):
        return self.request(path)

    def pages(self, path, key=None):
        for page in range(1, 21):
            value = self.get(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            rows = value[key] if key else value
            yield from rows
            if len(rows) < 100: return
        raise ValueError('GitHub pagination bound exceeded')

    def run(self, run_id, attempt, workflow, events, branch=None):
        run = self.get(f'{PREFIX}/actions/runs/{run_id}/attempts/{attempt}')
        expected = self.get(f'{PREFIX}/actions/workflows/{workflow}')
        m.require(run['id'] == run_id and run['run_attempt'] == attempt and
                  run['repository']['full_name'] == m.REPOSITORY and run['head_repository']['full_name'] == m.REPOSITORY and
                  run['workflow_id'] == expected['id'] and run['path'] == '.github/workflows/' + workflow and
                  run['event'] in events and (branch is None or run['head_branch'] == branch), 'unexpected producer')
        return run

    def wait_checks(self, sha, branch, timeout=3600):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            complete = True
            for workflow, check in [('ci.yml', 'CI Push Validation'), ('ci-cd-safety.yml', 'CD Safety Push Validation')]:
                runs = list(self.pages(f'{PREFIX}/actions/workflows/{workflow}/runs?head_sha={sha}&branch={branch}&event=push', 'workflow_runs'))
                if not runs:
                    complete = False; continue
                latest = max(runs, key=lambda r:(r['id'], r['run_attempt']))
                if latest['status'] != 'completed':
                    complete = False; continue
                run = self.run(latest['id'], latest['run_attempt'], workflow, ('push',), branch)
                jobs = list(self.pages(f'{PREFIX}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs', 'jobs'))
                m.require(run['head_sha'] == sha and run['conclusion'] == 'success' and
                          any(j['name'] == check and j['conclusion'] == 'success' for j in jobs), 'exact-SHA CI failed')
            if complete: return
            time.sleep(20)
        raise ValueError('CI did not finish')

    def release(self, deployment_id, environment='dev'):
        item = self.get(f'{PREFIX}/deployments/{int(deployment_id)}')
        m.require(item['id'] == deployment_id and item['task'] == 'api-release' and
                  item['environment'] == 'api-' + environment and item['creator']['login'] == BOT, 'unexpected deployment index')
        envelope = item['payload']; record = m.release(envelope['release'], environment)
        m.require(item['sha'] == record['source'] and envelope['schema'] == 'API_INDEX_V2', 'release source differs')
        ref = m.manifest_reference(record['manifest_ref'])
        m.require(ref['sha256'] == m.sha(m.canonical({k:v for k,v in record.items() if k != 'manifest_ref'})), 'release bytes differ')
        producer = envelope['publisher']; branch = 'develop' if environment == 'dev' else 'main'
        run = self.run(producer['run'], producer['attempt'], 'api-delivery.yml', ('push', 'workflow_dispatch'), branch)
        m.require(run['head_sha'] == producer['sha'], 'publisher source differs')
        jobs = self.pages(f'{PREFIX}/actions/runs/{run["id"]}/attempts/{producer["attempt"]}/jobs', 'jobs')
        m.require(any(s['name'] == 'Execute release or reconcile' and s['conclusion'] == 'success'
                      for j in jobs for s in j.get('steps', [])), 'release execution did not succeed')
        url = f'https://github.com/{m.REPOSITORY}/actions/runs/{producer["run"]}/attempts/{producer["attempt"]}'
        statuses = self.pages(f'{PREFIX}/deployments/{deployment_id}/statuses')
        m.require(any(s['state'] == 'success' and s['creator']['login'] == BOT and s['log_url'] == url for s in statuses), 'healthy status missing')
        return record

    def releases(self, environment='dev'):
        for item in self.pages(f'{PREFIX}/deployments?task=api-release&environment=api-{environment}'):
            statuses = list(self.pages(f'{PREFIX}/deployments/{item["id"]}/statuses'))
            if any(s['state'] == 'success' for s in statuses):
                yield item['id'], self.release(item['id'], environment)

    def publish(self, record):
        m.release(record)
        publisher = dict(run=int(os.environ['GITHUB_RUN_ID']), attempt=int(os.environ['GITHUB_RUN_ATTEMPT']), sha=os.environ['GITHUB_SHA'])
        envelope = dict(schema='API_INDEX_V2', publisher=publisher, release=record)
        item = self.request(PREFIX + '/deployments', 'POST', dict(ref=record['source'], task='api-release',
            environment='api-' + record['environment'], auto_merge=False, required_contexts=[], payload=envelope,
            transient_environment=False, production_environment=record['environment'] == 'prod', description='Healthy API release; versioned S3 manifest'))
        self.request(f'{PREFIX}/deployments/{item["id"]}/statuses', 'POST', dict(state='success', auto_inactive=False,
            log_url=f'https://github.com/{m.REPOSITORY}/actions/runs/{publisher["run"]}/attempts/{publisher["attempt"]}'))
        m.require(self.release(item['id'], record['environment']) == record, 'index readback differs')
        return item['id']

    def require_promotion_rule(self):
        rules = self.get(PREFIX + '/rules/branches/main')
        methods = [set(r['parameters']['allowed_merge_methods']) for r in rules if r['type'] == 'pull_request']
        m.require(methods and set.intersection(*methods) == {'merge'}, 'main must require merge commits')
        m.require(any(r['type'] == 'required_status_checks' and r['parameters']['strict_required_status_checks_policy'] and
                      any(c['context'] == CHECK and c.get('integration_id') == 15368 for c in r['parameters']['required_status_checks'])
                      for r in rules), 'main promotion check not installed')

    def check(self, head, conclusion=None, check_id=None, locator=None):
        run = int(os.environ['GITHUB_RUN_ID']); attempt = int(os.environ['GITHUB_RUN_ATTEMPT'])
        body = dict(name=CHECK, details_url=f'https://github.com/{m.REPOSITORY}/actions/runs/{run}/attempts/{attempt}')
        if check_id is None: body['head_sha'] = head
        body.update(dict(status='completed', conclusion=conclusion) if conclusion else dict(status='in_progress'))
        if locator is not None: body['external_id'] = json.dumps(locator, separators=(',', ':'))
        return self.request(PREFIX + '/check-runs' + (f'/{check_id}' if check_id else ''), 'PATCH' if check_id else 'POST', body)

    def approval(self, pr, parents, application):
        self.require_promotion_rule(); m.eligible_pr(pr)
        m.require(pr['merged'] and len(parents) == 2 and parents[1] == pr['head']['sha'], 'two-parent promotion required')
        checks = [c for c in self.pages(f'{PREFIX}/commits/{parents[1]}/check-runs?filter=all', 'check_runs')
                  if c['name'] == CHECK and c['app']['id'] == 15368 and c['head_sha'] == parents[1] and c['started_at'] <= pr['merged_at']]
        m.require(checks, 'promotion check missing'); check = max(checks, key=lambda c:c['id'])
        m.require(check['conclusion'] == 'success' and check['completed_at'] <= pr['merged_at'], 'approval not successful before merge')
        loc = json.loads(check['external_id'])
        m.require(loc['v'] == 2 and loc['pr'] == pr['number'] and loc['base'] == parents[0] and loc['app'] == application, 'approval changed')
        # GitHub can rewrite details_url. The exact producer is part of the
        # check's read-back external_id, not inferred from a presentation URL.
        m.require(type(loc['run']) is int and loc['run'] > 0 and type(loc['attempt']) is int and loc['attempt'] > 0, 'check producer')
        run = self.run(loc['run'], loc['attempt'], 'api-promotion.yml', ('pull_request_target', 'workflow_run'))
        m.require(run['head_sha'] in parents, 'check source differs from approved PR')
        record = self.release(loc['release']) if loc['release'] else None
        if record: m.require(record['application'] == application, 'approved release changed')
        return record, dict(check=check['id'], **loc)
