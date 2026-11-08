"""AWS adapter, instantiated only in an admitted push/rollback job.

Bindings are versioned public admin objects; runtime secret values are never read.
All application mutations share the existing E2 application head with lifecycle.
"""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import urllib.parse
import uuid
from scripts import environment_mutation as e2
from scripts.normal_delivery import authorization
from scripts.wp4d.aws_runtime import Observer, json_readback
from .model import canonical, sha, require

ROOT = Path(__file__).resolve().parents[2]


def clients(region):
    import boto3
    from botocore.config import Config
    cfg = Config(connect_timeout=5, read_timeout=15, retries={'total_max_attempts': 1})
    return {name: boto3.client(name, region_name=region, config=cfg)
            for name in ('sts', 's3', 'ecs', 'elbv2', 'ecr')}


def binding(reference, environment, aws):
    require(set(reference) == {'bucket', 'key', 'version', 'sha256', 'account', 'region'}, 'binding reference fields')
    require(reference['version'].lower() not in ('', 'null', 'latest'), 'versioned binding required')
    require(aws['sts'].get_caller_identity()['Account'] == reference['account'], 'AWS account mismatch')
    result = aws['s3'].get_object(Bucket=reference['bucket'], Key=reference['key'], VersionId=reference['version'],
                                  ExpectedBucketOwner=reference['account'])
    raw = result['Body'].read(262145)
    require(len(raw) <= 262144 and sha(raw) == reference['sha256'] and result['VersionId'] == reference['version'],
            'binding provenance mismatch')
    value = json.loads(raw)
    validate_binding(value, environment, reference['account'], reference['region'])
    return value


def validate_binding(value, environment, account, region):
    require(set(value) == {'schema', 'environment', 'account', 'region', 'colors', 'database', 'trust',
                          'secret_version', 'repository', 'evidence_bucket', 'client_url', 'replicas',
                          'drain_seconds', 'compatibility', 'evidence_kms_key', 'binding_kms_key'}, 'closed installation contract')
    require(value['schema'] == 'API_INSTALLATION_V1' and value['environment'] == environment and
            value['account'] == account and value['region'] == region, 'environment binding mismatch')
    require(set(value['colors']) == {'blue', 'green'}, 'two independent color bindings required')
    endpoint = 'deploy-dev' if environment == 'dev' else 'promote-prod'
    for color, item in value['colors'].items():
        authorization.binding(item, endpoint, account, region)
        require(item['color'] == color, 'color identity')
    left, right = value['colors'].values()
    for key in ('listener_arn', 'candidate_rule_arn', 'secret_arn', 'kms_key_arn'):
        require(left[key] == right[key], 'shared color configuration mismatch')
    require(left['service']['cluster'] == right['service']['cluster'], 'cluster mismatch')
    require(type(value['replicas']) is int and 1 <= value['replicas'] <= min(left['max_replicas'], right['max_replicas']), 'replica limit')
    require(type(value['drain_seconds']) is int and 30 <= value['drain_seconds'] <= 300, 'bounded drain')
    require(value['database']['environment'] == environment and value['database']['profile'] == 'validated-v2' and
            value['trust']['environment'] == environment, 'strict environment trust required')
    import re
    require(re.fullmatch('[A-Za-z0-9-]{32,64}', value['secret_version']), 'exact secret version required')
    require(re.fullmatch('[0-9a-f]{64}', value['compatibility']), 'reviewed schema/trust compatibility required')
    for key in ('evidence_kms_key', 'binding_kms_key'):
        require(re.fullmatch(f'arn:aws:kms:{region}:{account}:key/[0-9a-f-]{{36}}', value[key]), 'exact storage CMK required')
    require(re.fullmatch(re.escape(account + '.dkr.ecr.' + region + '.amazonaws.com/') + '[a-z0-9._/-]+', value['repository']), 'same-account approved repository')
    parsed = urllib.parse.urlsplit(value['client_url'])
    require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.query and
            parsed.path in ('', '/') and not parsed.fragment, 'fixed HTTPS client route required')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def task_readback(expected, actual, account, region):
    """Only documented empty/default ECS response fields may be normalized."""
    result = json_readback(copy.deepcopy(actual)); wanted = copy.deepcopy(expected)
    require(result['status'] == 'ACTIVE' and result['revision'] > 0 and
            result['taskDefinitionArn'] == f'arn:aws:ecs:{region}:{account}:task-definition/{expected["family"]}:{result["revision"]}',
            'task identity mismatch')
    for field in authorization.MODEL['task_return_only']:
        if field in result:
            authorization.validate_metadata(field, result.pop(field), account, region)
    authorization.defaults(result, authorization.MODEL['task_defaults'], 'task')
    for container in result['containerDefinitions']:
        original = next(c for c in wanted['containerDefinitions'] if c['name'] == container['name'])
        defaults = dict(authorization.MODEL['container_defaults'], cpu=[0])
        authorization.defaults(container, {k:v for k,v in defaults.items() if k not in original}, 'container')
        for port in container.get('portMappings', []):
            if 'hostPort' in port: require(port.pop('hostPort') == 8080, 'host port mismatch')
    for task in (wanted, result):
        task['containerDefinitions'].sort(key=lambda x:x['name'])
        for c in task['containerDefinitions']:
            for field in ('environment', 'secrets'):
                if field in c: c[field].sort(key=lambda x:x['name'])
    authorization.exact(result, wanted, 'registered-task')


class Runtime:
    def __init__(self, aws, config, owner, operation, directory):
        self.aws, self.config, self.owner, self.operation = aws, config, owner, operation
        self.directory = Path(directory)
        self.replicas = config['replicas']
        self.deadline = time.time() + 1800
        self.sequence = 0
        self.cohort = None
        self.observer = Observer(aws['ecs'], aws['elbv2'], dict(environment=config['environment'], colors={
            color: dict(cluster=b['service']['cluster'], service=b['service']['service'],
                        target_group=b['service']['loadBalancers'][0]['targetGroupArn'],
                        listener=b['listener_arn'], candidate_rule=b['candidate_rule_arn'])
            for color,b in config['colors'].items()}))

    def journal(self, stage, value):
        self.sequence += 1
        key = f'api-delivery/{self.config["environment"]}/operations/{self.operation}/{self.sequence:03}-{stage}.json'
        raw = canonical(value)
        s3 = self.aws['s3']; bucket = self.config['evidence_bucket']
        # Conditional create and exact readback. No overwrite, delete or blind retry.
        s3.put_object(Bucket=bucket, Key=key, Body=raw, IfNoneMatch='*', ContentType='application/json')
        observed = s3.get_object(Bucket=bucket, Key=key)
        require(observed['Body'].read(len(raw) + 1) == raw and observed.get('VersionId') not in (None, 'null') and
                observed.get('ServerSideEncryption') == 'aws:kms' and observed.get('SSEKMSKeyId') == self.config['evidence_kms_key'],
                'journal not persisted with the approved CMK')

    def mutate(self, service, method, **kwargs):
        self.journal('attempt-' + method, kwargs)
        def send():
            require(time.time() < self.deadline, 'operation deadline')
            return getattr(self.aws[service], method)(**kwargs)
        return self.owner.call(send)

    def color(self, color):
        return self.config['colors'][color]

    def target(self, color):
        return self.color(color)['service']['loadBalancers'][0]['targetGroupArn']

    def routes(self):
        def target(arn):
            matches = [c for c in ('blue', 'green') if self.target(c) == arn]
            require(len(matches) == 1, 'route outside environment')
            return matches[0]
        listener, candidate = self.observer.routes()
        return target(listener), target(candidate)

    def service(self, color):
        spec = self.color(color)['service']
        response = self.aws['ecs'].describe_services(cluster=spec['cluster'], services=[spec['service']])
        require(not response.get('failures') and len(response['services']) == 1, 'service missing')
        actual = response['services'][0]
        for key in ('clusterArn', 'launchType', 'networkConfiguration', 'loadBalancers', 'deploymentController'):
            require(actual[key] == spec['cluster' if key == 'clusterArn' else key], 'service binding drift: ' + key)
        require(actual['status'] == 'ACTIVE', 'inactive service')
        return actual

    def snapshot(self):
        routes = self.routes(); active = routes[0]; inactive = 'green' if active == 'blue' else 'blue'
        a = self.service(active); b = self.service(inactive)
        return dict(routes=routes, active=active, inactive=inactive, active_revision=a['taskDefinition'],
                    active_count=a['desiredCount'], inactive_count=max(b['desiredCount'], b['runningCount']),
                    pending=a['pendingCount'] + b['pendingCount'])

    def register(self, color, image):
        cfg = self.config; spec = self.color(color)
        files = {'binding': spec, 'database': cfg['database'], 'trust': cfg['trust']}
        for name, value in files.items():
            (self.directory / (name + '.json')).write_bytes(canonical(value))
        output = self.directory / 'task.json'
        args = ['bash', str(ROOT/'scripts/render-demo-api-taskdef.sh'), '--env', cfg['environment'],
                '--region', cfg['region'], '--account-id', cfg['account'], '--color', color,
                '--image-uri', image, '--db-secret-id', spec['secret_arn'] + ':::' + cfg['secret_version'],
                '--kms-key-id', spec['kms_key_arn'], '--database-config', str(self.directory/'database.json'),
                '--sql-trust-manifest', str(self.directory/'trust.json'), '--environment-binding',
                str(self.directory/'binding.json'), '--output', str(output)]
        subprocess.run(args, check=True, timeout=60)
        task = json.loads(output.read_bytes())
        require(len(task['containerDefinitions']) == 2, 'two-container contract')
        result = self.mutate('ecs', 'register_task_definition', **task)['taskDefinition']
        revision = result['taskDefinitionArn']
        readback = self.aws['ecs'].describe_task_definition(taskDefinition=revision)['taskDefinition']
        task_readback(task, readback, cfg['account'], cfg['region'])
        return revision

    def start(self, color, revision):
        s = self.color(color)['service']; self.started = int(time.time())
        self.mutate('ecs', 'update_service', cluster=s['cluster'], service=s['service'],
                    taskDefinition=revision, desiredCount=self.replicas)

    def ready(self, color, revision, image, active):
        cfg = self.config; spec = self.color(color); service = spec['service']
        args = ['bash', str(ROOT/'scripts/ecs-readiness-gate.sh'), '--use-instance-role']
        values = dict(region=cfg['region'], cluster=service['cluster'], service=service['service'],
                      **{'task-definition-arn': revision, 'image-uri': image,
                         'app-container': service['loadBalancers'][0]['containerName'],
                         'probe-container': service['loadBalancers'][0]['containerName'] + '-readiness-probe',
                         'target-group-arn': self.target(color), 'listener-arn': spec['listener_arn'],
                         'candidate-rule-arn': spec['candidate_rule_arn'], 'active-target-group-arn': self.target(active),
                         'desired-count': self.replicas, 'attempt-start-epoch': self.started,
                         'deadline-epoch': int(self.deadline)})
        for key, value in values.items(): args += ['--' + key, str(value)]
        result = subprocess.run(args, capture_output=True, timeout=max(1, self.deadline-time.time()))
        require(result.returncode == 0, 'per-task SQL/KMS readiness failed')
        self.journal('readiness', dict(transcript_sha256=sha(result.stdout), revision=revision, image=image))
        self.cohort = self.tasks(color, revision, image)

    def tasks(self, color, revision, image=None):
        svc = self.service(color); spec = self.color(color)['service']
        require(svc['taskDefinition'] == revision and svc['runningCount'] == svc['desiredCount'] and
                svc['pendingCount'] == 0, 'service not stable')
        ids = self.aws['ecs'].list_tasks(cluster=spec['cluster'], serviceName=spec['service'], desiredStatus='RUNNING')
        require(not ids.get('nextToken') and len(ids['taskArns']) == self.replicas, 'task cohort cardinality')
        result = self.aws['ecs'].describe_tasks(cluster=spec['cluster'], tasks=ids['taskArns'])
        require(not result.get('failures') and len(result['tasks']) == self.replicas, 'incomplete task readback')
        for task in result['tasks']:
            require(task['taskDefinitionArn'] == revision and task['lastStatus'] == 'RUNNING', 'task revision drift')
            containers = task['containers']; require(len(containers) == 2, 'task container count')
            app = next(c for c in containers if c['name'] == spec['loadBalancers'][0]['containerName'])
            probe = next(c for c in containers if c is not app)
            require(app['lastStatus'] == 'RUNNING' and probe['lastStatus'] == 'STOPPED' and probe['exitCode'] == 0,
                    'task probe not successful')
            if image:
                require(all(c.get('imageDigest') == image.split('@')[1] for c in containers), 'task image drift')
        targets = self.aws['elbv2'].describe_target_health(TargetGroupArn=self.target(color))['TargetHealthDescriptions']
        require(len(targets) == self.replicas and all(t['TargetHealth']['State'] == 'healthy' for t in targets), 'targets not healthy')
        self.observer.targets(color, result['tasks'])  # exact task ENIs, not merely N healthy targets
        return sorted(ids['taskArns'])

    def still_ready(self, color, revision, image):
        require(self.tasks(color, revision, image) == self.cohort, 'task cohort changed')

    def old_ready(self, color, revision, count):
        require(count == self.replicas, 'rollback capacity differs')
        self.tasks(color, revision)

    def listener(self, color):
        self.mutate('elbv2', 'modify_listener', ListenerArn=self.color(color)['listener_arn'],
                    DefaultActions=[{'Type': 'forward', 'TargetGroupArn': self.target(color)}])

    def candidate(self, color):
        self.mutate('elbv2', 'modify_rule', RuleArn=self.color(color)['candidate_rule_arn'],
                    Actions=[{'Type': 'forward', 'TargetGroupArn': self.target(color)}])

    def stop(self, color):
        s = self.color(color)['service']
        self.mutate('ecs', 'update_service', cluster=s['cluster'], service=s['service'], desiredCount=0)
        while time.time() < self.deadline:
            actual = self.service(color)
            if actual['runningCount'] == actual['pendingCount'] == actual['desiredCount'] == 0:
                return
            time.sleep(5)
        raise TimeoutError('drain incomplete')

    def drain_wait(self):
        time.sleep(self.config['drain_seconds'])

    def client_ready(self):
        # /ready executes SQL and KMS round-trip health checks. No production data
        # enumeration or business writes are needed for this deployment gate.
        opener = urllib.request.build_opener(NoRedirect())
        for path in ('/health/live', '/ready'):
            with opener.open(self.config['client_url'].rstrip('/') + path, timeout=15) as response:
                raw = response.read(65537)
                require(response.status == 200 and len(raw) <= 65536, 'client route unhealthy')
                if path == '/ready':
                    value = json.loads(raw)
                    require(value['status'] == 'Healthy' and
                            {v['name'] for v in value['checks']} == {'database', 'kms'} and
                            all(v['status'] == 'Healthy' for v in value['checks']),
                            'SQL/KMS client readiness unproved')


def owner(aws, cfg, operation, request):
    endpoint = 'deploy-dev' if cfg['environment'] == 'dev' else 'promote-prod'
    return e2.Authority(e2.Store(aws['s3'], cfg['evidence_bucket'], cfg['environment']),
                        'normal-delivery/' + endpoint, operation, request)


def publish(aws, config, source, run_id, attempt):
    repository = config['repository']; registry, name = repository.split('/', 1)
    actual = aws['ecr'].describe_repositories(repositoryNames=[name])['repositories']
    require(len(actual) == 1 and actual[0]['repositoryUri'] == repository and actual[0]['imageTagMutability'] == 'IMMUTABLE',
            'immutable approved ECR repository required')
    tag = f'{source}-{run_id}-{attempt}'
    image = repository + ':' + tag
    subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '-f', 'demo-api/Dockerfile', '-t', image, 'demo-api'], check=True)
    inspected = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))
    require(len(inspected) == 1 and inspected[0]['Architecture'] == 'amd64' and inspected[0]['Os'] == 'linux' and
            inspected[0]['Config']['User'] == '1654' and inspected[0]['Config']['Entrypoint'] == ['/app/entrypoint.sh'],
            'built image runtime contract')
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', image, 'readiness-probe', '--check-capability'], check=True)
    auth = aws['ecr'].get_authorization_token()['authorizationData']
    require(len(auth) == 1 and auth[0]['proxyEndpoint'] == 'https://' + registry, 'ECR login scope')
    username, password = base64.b64decode(auth[0]['authorizationToken']).decode().split(':', 1)
    # Ephemeral Docker auth directory; token never enters argv/logs/artifacts.
    with tempfile.TemporaryDirectory() as directory:
        env = dict(os.environ, DOCKER_CONFIG=directory)
        subprocess.run(['docker', 'login', '--username', username, '--password-stdin', registry],
                       input=password.encode(), check=True, env=env, capture_output=True)
        subprocess.run(['docker', 'push', image], check=True, env=env)
    details = aws['ecr'].describe_images(repositoryName=name, imageIds=[{'imageTag': tag}])['imageDetails']
    require(len(details) == 1, 'published digest missing')
    return repository + '@' + details[0]['imageDigest']
