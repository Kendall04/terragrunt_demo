"""Read-only GitHub evidence adapter: exact workflow/run/attempt and immutable artifact."""
import hashlib
import io
import json
import subprocess
import time
import zipfile
from .model import REPOSITORY, DELIVERY, PROMOTION, require, release


class GitHub:
    def get(self, path):
        return json.loads(self.raw(path))

    def raw(self, path):
        require(path.startswith('repos/' + REPOSITORY + '/'), 'repository scope')
        return subprocess.check_output(['gh', 'api', '-H', 'Accept: application/vnd.github+json', path], timeout=90)

    def pages(self, path, key):
        separator = '&' if '?' in path else '?'
        for page in range(1, 21):
            value = self.get(path + separator + 'per_page=100&page=' + str(page))
            rows = value[key] if key else value
            yield from rows
            if len(rows) < 100:
                return
        raise ValueError('GitHub evidence pagination bound exceeded')

    def runs(self, workflow, branch=None, sha=None):
        query = []
        if branch: query.append('branch=' + branch)
        if sha: query.append('head_sha=' + sha)
        suffix = '?' + '&'.join(query) if query else ''
        return self.pages(f'repos/{REPOSITORY}/actions/workflows/{workflow.split("/")[-1]}/runs' + suffix, 'workflow_runs')

    def trusted(self, run, workflow, event, branch):
        expected = self.get(f'repos/{REPOSITORY}/actions/workflows/{workflow.split("/")[-1]}')
        require(run['repository']['full_name'] == REPOSITORY and
                run['head_repository']['full_name'] == REPOSITORY and
                run['workflow_id'] == expected['id'] and run['path'] == workflow and
                run['event'] == event and (branch is None or run['head_branch'] == branch) and
                run['status'] == 'completed' and run['conclusion'] == 'success', 'untrusted workflow result')

    def artifact(self, run, name):
        artifacts = list(self.pages(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/artifacts', 'artifacts'))
        found = [x for x in artifacts if x['name'] == name and not x['expired']]
        require(len(found) == 1, 'unique retained artifact required')
        item = found[0]
        require(item['size_in_bytes'] <= 1048576, 'oversized evidence')
        raw = self.raw(f'repos/{REPOSITORY}/actions/artifacts/{item["id"]}/zip')
        require('sha256:' + hashlib.sha256(raw).hexdigest() == item['digest'], 'artifact digest mismatch')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            require(archive.namelist() == ['result.json'] and archive.infolist()[0].file_size <= 262144,
                    'unexpected artifact contents')
            result = json.loads(archive.read('result.json'))
        require(result['run_id'] == run['id'] and result['run_attempt'] == run['run_attempt'], 'stale attempt artifact')
        return result

    def wait_checks(self, sha, branch, timeout=3600):
        expected = {'ci.yml': 'CI Push Validation', 'ci-cd-safety.yml': 'CD Safety Push Validation'}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            complete = True
            for workflow, check in expected.items():
                runs = [r for r in self.runs(workflow, branch, sha) if r['head_sha'] == sha and r['event'] == 'push']
                if not runs:
                    complete = False
                    continue
                run = max(runs, key=lambda x: (x['id'], x['run_attempt']))
                if run['status'] != 'completed':
                    complete = False
                    continue
                self.trusted(run, '.github/workflows/' + workflow, 'push', branch)
                jobs = list(self.pages(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs', 'jobs'))
                require(len([j for j in jobs if j['name'] == check and j['conclusion'] == 'success']) == 1,
                        'required exact-SHA validation failed/cancelled/missing')
            if complete:
                return
            time.sleep(20)
        raise ValueError('exact-SHA validations did not finish')

    def deployments(self, environment):
        branch = 'develop' if environment == 'dev' else 'main'
        for run in self.runs(DELIVERY):
            if run['head_branch'] != branch or run['event'] not in ('push', 'workflow_dispatch') or run['conclusion'] != 'success':
                continue
            self.trusted(run, DELIVERY, run['event'], branch)
            # No-op runs intentionally have no release artifact.
            names = self.get(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/artifacts')['artifacts']
            if not any(a['name'] == 'release-record' and not a['expired'] for a in names):
                continue
            record = self.artifact(run, 'release-record')
            if record['environment'] == environment:
                require(record['source'] == run['head_sha'] or run['event'] == 'workflow_dispatch' or environment == 'prod',
                        'DEV source is not the built push')
                yield release(record, environment)

    def require_app_validation(self, sha, branch):
        runs = [r for r in self.runs('ci.yml', branch, sha) if r['head_sha'] == sha and r['event'] == 'push']
        require(bool(runs), 'application validation run missing')
        run = max(runs, key=lambda r:(r['id'], r['run_attempt']))
        self.trusted(run, '.github/workflows/ci.yml', 'push', branch)
        jobs = list(self.pages(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs', 'jobs'))
        app = [j for j in jobs if j['name'] == 'App CI / .NET Restore • Build • Test • Docker Validate']
        require(len(app) == 1 and app[0]['conclusion'] == 'success', 'application qualification skipped or unsuccessful')

    def promotion_receipts(self):
        for run in self.runs(PROMOTION):
            if run['conclusion'] != 'success' or run['event'] not in ('pull_request_target', 'workflow_run'):
                continue
            # pull_request_target executes base/main code, never the PR checkout.
            self.trusted(run, PROMOTION, run['event'], None)
            artifacts = self.get(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/artifacts')['artifacts']
            if any(a['name'] == 'promotion-record' and not a['expired'] for a in artifacts):
                record = self.artifact(run, 'promotion-record')
                require(run['head_sha'] == record['base'], 'gate did not run reviewed base code')
                yield record

    def require_promotion_check(self, receipt):
        rules = self.get(f'repos/{REPOSITORY}/rules/branches/main')
        required = [r['parameters'] for r in rules if r['type'] == 'required_status_checks']
        require(any(r['strict_required_status_checks_policy'] and any(
            c['context'] == 'API Promotion Validation' and c.get('integration_id') == 15368
            for c in r['required_status_checks']) for r in required), 'main promotion rule not installed')
        checks = list(self.pages(f'repos/{REPOSITORY}/commits/{receipt["head"]}/check-runs', 'check_runs'))
        url = f'https://github.com/{REPOSITORY}/actions/runs/{receipt["run_id"]}'
        require(any(c['name'] == 'API Promotion Validation' and c['app']['id'] == 15368 and
                    c['head_sha'] == receipt['head'] and c['conclusion'] == 'success' and c['details_url'] == url
                    for c in checks), 'exact receipt was not approved by the required check')

    def check(self, head, status, check_id=None):
        body = dict(name='API Promotion Validation', head_sha=head,
                    details_url=f'https://github.com/{REPOSITORY}/actions/runs/' + __import__('os').environ['GITHUB_RUN_ID'])
        if status == 'in_progress':
            body['status'] = status
        else:
            body.update(status='completed', conclusion=status)
        path = f'repos/{REPOSITORY}/check-runs' + ('/' + str(check_id) if check_id else '')
        if check_id: body.pop('head_sha')
        return json.loads(subprocess.check_output(['gh', 'api', '-X', 'PATCH' if check_id else 'POST', path,
                                                   '--input', '-'], input=json.dumps(body).encode(), timeout=60))
