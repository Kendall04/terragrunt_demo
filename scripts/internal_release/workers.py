"""Trusted controller-side CodeBuild transport; never locally runs a payload."""
import time
from e1_contract import WORKERS, build_id, closed, image_uri, observe, operation_id, require


class Workers:
    def __init__(self, codebuild, account, region, repository, attempt, sleep=time.sleep):
        self.client = codebuild
        self.account, self.region, self.repository = account, region, repository
        self.attempt, self.sleep = operation_id(attempt), sleep
        self.started = {}

    def request(self, kind, capabilities=None, image=None):
        require(kind in WORKERS and kind not in self.started)
        request = {'projectName': WORKERS[kind], 'idempotencyToken': self.attempt + '-' + kind}
        if kind == 'probe':
            require(capabilities is None)
            request['imageOverride'] = image_uri(image, self.account, self.region, self.repository)
            request['imagePullCredentialsTypeOverride'] = 'CODEBUILD'
        else:
            closed(capabilities, ('SOURCE_URL',) if kind == 'dotnet' else ('SOURCE_URL', 'OUTPUT_URL'))
            require(image is None)
            require(all(type(v) is str and v.startswith('https://') and len(v) <= 16384
                        for v in capabilities.values()))
            request['environmentVariablesOverride'] = [
                {'name': 'E1_' + k, 'value': v, 'type': 'PLAINTEXT'}
                for k, v in sorted(capabilities.items())]
        return request

    def run(self, kind, capabilities=None, image=None):
        request = self.request(kind, capabilities, image)
        response = self.client.start_build(**request)
        identity = build_id(response['build']['id'], WORKERS[kind])
        require(response['build'].get('projectName') == WORKERS[kind])
        self.started[kind] = identity
        for _ in range(180):
            response = self.client.batch_get_builds(ids=[identity])
            require(not response.get('buildsNotFound') and len(response.get('builds', [])) == 1)
            b = response['builds'][0]
            require(b.get('id') == identity and b.get('projectName') == WORKERS[kind])
            if b.get('buildComplete') is True:
                return identity, response
            self.sleep(5)
        raise TimeoutError('E1_WORKER_TIMEOUT')

    def stage(self, run, kind, stage):
        return observe(run[1], run[0], WORKERS[kind], stage)
