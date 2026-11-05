"""Trusted controller-side CodeBuild transport; never locally runs a payload."""
import time
import json
from e1_contract import (WORKERS, WORKER_ROLE, build_id, closed, image_uri, observe, operation_id,
                         require, STANDARD_RECIPE, DEV_SQL_LAB_RECIPE, worker_buildspec)


class Workers:
    def __init__(self, codebuild, account, region, repository, attempt, sleep=time.sleep,
                 recipe=STANDARD_RECIPE, selectable=False, dotnet_image=None):
        require(recipe in (STANDARD_RECIPE, DEV_SQL_LAB_RECIPE))
        require(type(selectable) is bool)
        self.recipe = recipe
        self.selectable = selectable or recipe == DEV_SQL_LAB_RECIPE
        if recipe == DEV_SQL_LAB_RECIPE:
            image_uri(dotnet_image, account, region, 'e1-payload-dotnet')
        else:
            require(dotnet_image is None)
        self.dotnet_image = dotnet_image
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
            if kind == 'image' and self.selectable:
                request['environmentVariablesOverride'].append(
                    {'name':'E1_BUILD_RECIPE','value':self.recipe,'type':'PLAINTEXT'})
            if kind == 'dotnet' and self.dotnet_image is not None:
                request['imageOverride'] = self.dotnet_image
                request['imagePullCredentialsTypeOverride'] = 'CODEBUILD'
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
                if kind == 'dotnet' and self.dotnet_image is not None:
                    environment = b.get('environment', {})
                    require(environment.get('image') == self.dotnet_image
                            and environment.get('privilegedMode') is False
                            and b.get('serviceRole') == 'arn:aws:iam::'+self.account+':role/'+WORKER_ROLE)
                if kind == 'image' and self.selectable:
                    # Authoritative AWS build metadata, not worker stdout. An old
                    # shared buildspec must never silently build the default recipe.
                    require(json.loads(b.get('source', {}).get('buildspec', 'null')) ==
                            worker_buildspec('image', selectable=True))
                    variables = b.get('environment', {}).get('environmentVariables', [])
                    selected = [v for v in variables if v.get('name') == 'E1_BUILD_RECIPE']
                    require(selected == [{'name':'E1_BUILD_RECIPE','value':self.recipe,'type':'PLAINTEXT'}])
                return identity, response
            self.sleep(5)
        raise TimeoutError('E1_WORKER_TIMEOUT')

    def stage(self, run, kind, stage):
        return observe(run[1], run[0], WORKERS[kind], stage)
