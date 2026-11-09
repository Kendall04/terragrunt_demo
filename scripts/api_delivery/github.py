"""GitHub evidence adapter: signed receipts plus diagnostic-only artifact helpers."""
import hashlib
import io
import json
import subprocess
import time
import zipfile
from .model import REPOSITORY, DELIVERY, PROMOTION, require, release, manifest_reference


class GitHub:
    def verify_signature(self, command):
        return subprocess.check_output(command, timeout=120)

    def get(self, path):
        return json.loads(self.raw(path))

    def raw(self, path):
        root = 'repos/' + REPOSITORY
        require(path == root or path.startswith(root + '/'), 'repository scope')
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
        return self.artifact_id(run, name, item['id'])

    def artifact_id(self, run, name, artifact_id, digest=None):
        result, _ = self.artifact_document(run, name, artifact_id, digest)
        require(result['run_attempt'] == run['run_attempt'], 'stale attempt artifact')
        return result

    def artifact_document(self, run, name, artifact_id, digest=None):
        """Authenticate bytes/producer run; the caller must authenticate the attempt."""
        item = self.get(f'repos/{REPOSITORY}/actions/artifacts/{artifact_id}')
        require(item['id'] == artifact_id and item['name'] == name and not item['expired'] and
                item['workflow_run']['id'] == run['id'], 'artifact producer or identity mismatch')
        repository = self.get(f'repos/{REPOSITORY}')
        require(item['workflow_run']['repository_id'] == repository['id'] and
                item['workflow_run']['head_repository_id'] == repository['id'], 'foreign artifact repository')
        if digest is not None:
            require(item['digest'] == digest, 'linked artifact digest mismatch')
        require(item['size_in_bytes'] <= 1048576, 'oversized evidence')
        raw = self.raw(f'repos/{REPOSITORY}/actions/artifacts/{item["id"]}/zip')
        require('sha256:' + hashlib.sha256(raw).hexdigest() == item['digest'], 'artifact digest mismatch')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            require(archive.namelist() == ['result.json'] and archive.infolist()[0].file_size <= 262144,
                    'unexpected artifact contents')
            result = json.loads(archive.read('result.json'))
        require(result['run_id'] == run['id'], 'artifact run mismatch')
        return result, item

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

    def deployments(self, environment, exclude_run=None, allow_queued=False):
        from . import receipts as r
        branch = 'develop' if environment == 'dev' else 'main'
        for run in self.runs(DELIVERY):
            if run['id'] == exclude_run or run['head_branch'] != branch or run['event'] not in ('push', 'workflow_dispatch'):
                continue
            descriptor = r.slot('deployment',run['id'],environment)
            if not r.bundles(self,descriptor):
                r.proven_no_execution(self,run,allow_queued=allow_queued)
                continue
            record, _ = r.resolve(self,descriptor)
            if record['schema'] != 'API_NO_DEPLOYMENT_V1':
                yield record

    def deployment_receipt(self, record):
        from . import receipts as r
        observed, locator = r.resolve(self,r.slot('deployment',record['run_id'],record['environment']))
        require(observed == record, 'deployment changed during approval')
        return locator

    def require_app_validation(self, sha, branch):
        runs = [r for r in self.runs('ci.yml', branch, sha) if r['head_sha'] == sha and r['event'] == 'push']
        require(bool(runs), 'application validation run missing')
        run = max(runs, key=lambda r:(r['id'], r['run_attempt']))
        self.trusted(run, '.github/workflows/ci.yml', 'push', branch)
        jobs = list(self.pages(f'repos/{REPOSITORY}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs', 'jobs'))
        app = [j for j in jobs if j['name'] == 'App CI / .NET Restore • Build • Test • Docker Validate']
        require(len(app) == 1 and app[0]['conclusion'] == 'success', 'application qualification skipped or unsuccessful')

    def require_merge_policy(self, administrator=False):
        rules = self.get(f'repos/{REPOSITORY}/rules/branches/main')
        methods = [set(r['parameters']['allowed_merge_methods']) for r in rules if r['type'] == 'pull_request']
        require(bool(methods) and set.intersection(*methods) == {'merge'}, 'main must enforce merge-only promotions')
        require(not any(r['type'] in ('required_linear_history', 'merge_queue') for r in rules),
                'main history/queue policy incompatible with two-parent promotion')
        repository = self.get(f'repos/{REPOSITORY}')
        # This optional setting is not exposed to every read-only job token.
        # Effective branch rules above are the runtime contract; installation
        # must additionally check the repository setting with the owner's token.
        if administrator or 'allow_merge_commit' in repository:
            require(repository.get('allow_merge_commit') is True, 'merge commits disabled or not observable')

    def require_promotion_rule(self):
        self.require_merge_policy()
        rules = self.get(f'repos/{REPOSITORY}/rules/branches/main')
        required = [r['parameters'] for r in rules if r['type'] == 'required_status_checks']
        require(any(r['strict_required_status_checks_policy'] and any(
            c['context'] == 'API Promotion Validation' and c.get('integration_id') == 15368
            for c in r['required_status_checks']) for r in required), 'main promotion rule not installed')

    def promotion_artifact(self, locator, completed=True):
        # Kept as the adapter API name for callers; no artifact/ZIP lookup remains.
        from . import receipts as r
        r.locator(locator)
        receipt, _ = r.resolve(self,r.slot('promotion',locator['r'],attempt=locator['a']),locator,completed)
        return receipt

    @staticmethod
    def approval_url(locator):
        return f'https://github.com/{REPOSITORY}/actions/runs/{locator["r"]}/attempts/{locator["a"]}'

    def promotion_receipt(self, pr):
        self.require_promotion_rule()
        require(pr['merged'] and pr['merged_at'], 'merged PR required')
        checks = list(self.pages(f'repos/{REPOSITORY}/commits/{pr["head"]["sha"]}/check-runs?filter=all', 'check_runs'))
        # The latest check completed before the merge is authoritative. Never
        # search older green runs or follow new develop deployments after merge.
        checks = [c for c in checks if c['name'] == 'API Promotion Validation' and c['app']['id'] == 15368 and
                  c['head_sha'] == pr['head']['sha'] and c['started_at'] <= pr['merged_at']]
        require(bool(checks), 'merged PR approval check missing/expired')
        check = max(checks, key=lambda c: c['id'])
        require(check['conclusion'] == 'success' and check['completed_at'] and
                check['completed_at'] <= pr['merged_at'], 'promotion was not approved before merge')
        locator = json.loads(check['external_id'])
        receipt = self.promotion_artifact(locator)
        require(receipt['pr'] == pr['number'] and receipt['head'] == pr['head']['sha'] and receipt['check_id'] == check['id'], 'approval belongs to another PR')
        return receipt, dict(check_id=check['id'], **locator)

    def check(self, head, status, check_id=None, locator=None):
        body = dict(name='API Promotion Validation', head_sha=head,
                    details_url=f'https://github.com/{REPOSITORY}/actions/runs/' + __import__('os').environ['GITHUB_RUN_ID'])
        if status == 'in_progress':
            body['status'] = status
        else:
            body.update(status='completed', conclusion=status)
        if locator is not None:
            body.update(external_id=json.dumps(locator, separators=(',', ':')), details_url=self.approval_url(locator))
        path = f'repos/{REPOSITORY}/check-runs' + ('/' + str(check_id) if check_id else '')
        if check_id: body.pop('head_sha')
        return json.loads(subprocess.check_output(['gh', 'api', '-X', 'PATCH' if check_id else 'POST', path,
                                                   '--input', '-'], input=json.dumps(body).encode(), timeout=60))
