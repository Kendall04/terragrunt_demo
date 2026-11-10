"""AWS adapter, instantiated only in an admitted push/rollback job.

Bindings are versioned public admin objects; runtime secret values are never read.
GitHub environment concurrency serializes jobs; a reviewed administrative handover fences external writers.
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
from scripts.normal_delivery import authorization
from scripts.wp4d.aws_runtime import Observer, json_readback
from .model import canonical, sha, require, manifest_reference, recovery_target

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
                          'drain_seconds', 'compatibility', 'evidence_kms_key', 'binding_kms_key',
                          'native_baseline', 'dev_evidence'}, 'closed installation contract')
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
    if value['native_baseline'] is not None:
        recovery_target(value['native_baseline'], environment, value['compatibility'])
        require(value['native_baseline']['kind'] == 'native-admission', 'bootstrap is not a fabricated automatic release')
    if environment == 'prod':
        evidence = value['dev_evidence']
        require(set(evidence) == {'bucket', 'account', 'region', 'kms_key', 'environment'} and
                evidence['environment'] == 'dev' and evidence['account'] == account and evidence['region'] == region and
                re.fullmatch(f'arn:aws:kms:{region}:{account}:key/[0-9a-f-]{{36}}', evidence['kms_key']),
                'reviewed same-account DEV manifest scope required')
    else:
        require(value['dev_evidence'] is None, 'DEV does not consume cross-environment evidence')
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
            value = result.pop(field)
            if field == 'compatibilities':
                require(type(value) is list and 'FARGATE' in value and len(value) == len(set(value)) and
                        set(value) <= {'EC2', 'FARGATE', 'EXTERNAL', 'MANAGED_INSTANCES'}, 'invalid compatibility metadata')
            elif field == 'requiresAttributes':
                require(type(value) is list and len(value) <= 100 and all(
                    type(a) is dict and set(a) == {'name'} and isinstance(a['name'], str) and
                    0 < len(a['name']) <= 256 and a['name'].startswith(('ecs.', 'com.amazonaws.ecs.')) for a in value),
                    'invalid capability metadata')
            else:
                authorization.validate_metadata(field, value, account, region)
    authorization.defaults(result, authorization.MODEL['task_defaults'], 'task')
    for container in result['containerDefinitions']:
        original = next(c for c in wanted['containerDefinitions'] if c['name'] == container['name'])
        defaults = dict(authorization.MODEL['container_defaults'], cpu=[0], systemControls=[[]])
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
    def __init__(self, aws, config, operation, directory):
        self.aws, self.config, self.operation = aws, config, operation
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
        suffix = 'release.json' if stage == 'release' else f'{self.sequence:03}-{stage}.json'
        key = f'api-delivery/{self.config["environment"]}/operations/{self.operation}/{suffix}'
        raw = canonical(value)
        s3 = self.aws['s3']; bucket = self.config['evidence_bucket']
        # Conditional create and exact readback. No overwrite, delete or blind retry.
        stored = s3.put_object(Bucket=bucket, Key=key, Body=raw, IfNoneMatch='*', ContentType='application/json',
                               ServerSideEncryption='aws:kms', SSEKMSKeyId=self.config['evidence_kms_key'],
                               ExpectedBucketOwner=self.config['account'], BucketKeyEnabled=False)
        require(stored.get('VersionId') not in (None, '', 'null'), 'S3 did not return an immutable version')
        observed = s3.get_object(Bucket=bucket, Key=key, VersionId=stored['VersionId'], ExpectedBucketOwner=self.config['account'])
        require(observed['Body'].read(len(raw) + 1) == raw and observed.get('VersionId') not in (None, 'null') and
                observed.get('ServerSideEncryption') == 'aws:kms' and observed.get('SSEKMSKeyId') == self.config['evidence_kms_key'],
                'journal not persisted with the approved CMK')
        require(observed['VersionId'] == stored['VersionId'], 'journal version readback mismatch')
        return dict(bucket=bucket, key=key, version=stored['VersionId'], sha256=sha(raw))

    def mutate(self, client_name, method, **kwargs):
        self.journal('attempt-' + method, kwargs)
        def send():
            require(time.time() < self.deadline, 'operation deadline')
            return getattr(self.aws[client_name], method)(**kwargs)
        return send()

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

    def render(self, color, image):
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
        return task

    def register(self, color, image):
        cfg = self.config; task = self.render(color, image)
        result = self.mutate('ecs', 'register_task_definition', **task)['taskDefinition']
        revision = result['taskDefinitionArn']
        readback = self.aws['ecs'].describe_task_definition(taskDefinition=revision)['taskDefinition']
        task_readback(task, readback, cfg['account'], cfg['region'])
        self.configuration_ref = self.journal('task-configuration', dict(schema='API_TASK_CONFIGURATION_V1',
            environment=cfg['environment'], color=color, image=image, revision=revision, task=task))
        return revision

    def start(self, color, revision):
        s = self.color(color)['service']; self.started = int(time.time())
        self.mutate('ecs', 'update_service', cluster=s['cluster'], service=s['service'],
                    taskDefinition=revision, desiredCount=self.replicas)

    def ready(self, color, revision, image, active):
        cfg = self.config; spec = self.color(color); service = spec['service']
        # ECS retains the empty previous deployment while the candidate starts.
        # The unchanged gate requires a settled single deployment before it
        # authenticates the cohort and its task-local SQL/KMS probe.
        remaining = self.deadline - time.time()
        require(remaining > 0, 'candidate stabilization deadline')
        self.aws['ecs'].get_waiter('services_stable').wait(
            cluster=service['cluster'], services=[service['service']],
            WaiterConfig={'Delay': 5, 'MaxAttempts': max(1, int(remaining / 5))})
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

    def tasks(self, color, revision, image=None, count=None):
        count = self.replicas if count is None else count
        svc = self.service(color); spec = self.color(color)['service']
        require(svc['taskDefinition'] == revision and svc['runningCount'] == svc['desiredCount'] == count and
                svc['pendingCount'] == 0, 'service not stable')
        ids = self.aws['ecs'].list_tasks(cluster=spec['cluster'], serviceName=spec['service'], desiredStatus='RUNNING')
        require(not ids.get('nextToken') and len(ids['taskArns']) == count, 'task cohort cardinality')
        result = self.aws['ecs'].describe_tasks(cluster=spec['cluster'], tasks=ids['taskArns'])
        require(not result.get('failures') and len(result['tasks']) == count, 'incomplete task readback')
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
        require(len(targets) == count and all(t['TargetHealth']['State'] == 'healthy' for t in targets), 'targets not healthy')
        self.observer.targets(color, result['tasks'])  # exact task ENIs, not merely N healthy targets
        return sorted(ids['taskArns'])

    def still_ready(self, color, revision, image):
        require(self.tasks(color, revision, image) == self.cohort, 'task cohort changed')

    def old_ready(self, color, revision, count):
        require(count > 0, 'no old capacity')
        self.tasks(color, revision, count=count)

    def admit_current(self, history, binding_sha256):
        initial = self.snapshot()
        require(initial['routes'] == (initial['active'], initial['inactive']) and
                initial['inactive_count'] == 0 and initial['pending'] == 0, 'initial service not quiescent')
        if initial['active_count'] == 0:
            require(not history and self.config['native_baseline'] is None, 'empty runtime conflicts with retained identity')
            # desired=0 alone is not proof of an empty environment.
            require(all(self.service(c)['runningCount'] == 0 for c in ('blue', 'green')), 'tasks still draining')
            return None
        cfg = self.config
        if history:
            latest = history[0]
            verify_manifest(self.aws, dict(bucket=cfg['evidence_bucket'], account=cfg['account'], region=cfg['region'],
                                          kms_key=cfg['evidence_kms_key'], environment=cfg['environment']), latest)
            target = dict(schema='API_RECOVERY_TARGET_V1', kind='automatic',
                          **{k:latest[k] for k in ('environment','source','application','image','compatibility','profile','revision','color')},
                          evidence=latest['manifest_ref'], configuration_ref=latest.get('configuration_ref'))
        else:
            target = copy.deepcopy(cfg['native_baseline'])
            require(target is not None, 'native blue requires reviewed baseline before traffic')
            target['evidence'] = dict(binding_sha256=binding_sha256)
        recovery_target(target, cfg['environment'], cfg['compatibility'])
        require(target['revision'] == initial['active_revision'] and target['color'] == initial['active'] and
                target['image'].startswith(cfg['repository'] + '@sha256:'), 'current recovery identity drift')
        verify_image(self.aws, cfg, target['image'])
        # Blue is authenticated against the exact task configuration that was
        # verified for blue, never reconstructed using green's new credentials
        # or trust manifest. The S3 reference is sealed by the release/admission.
        expected = self.current_configuration(target)
        task = self.aws['ecs'].describe_task_definition(taskDefinition=initial['active_revision'])['taskDefinition']
        task_readback(expected, task, cfg['account'], cfg['region'])
        self.tasks(initial['active'], initial['active_revision'], target['image'], count=initial['active_count'])
        self.client_ready()
        # A new admission attests current observations, never a historical CI run.
        self.journal('current-recovery-admission', dict(target=target, count=initial['active_count']))
        return target

    def current_configuration(self, target):
        import re
        cfg = self.config
        reference = manifest_reference(target.get('configuration_ref'))
        require(reference['bucket'] == cfg['evidence_bucket'] and re.fullmatch(
            'api-delivery/' + cfg['environment'] + r'/operations/[0-9a-f-]{36}/[0-9]{3}-task-configuration.json',
            reference['key']), 'historical configuration outside environment')
        response = self.aws['s3'].get_object(Bucket=reference['bucket'], Key=reference['key'],
            VersionId=reference['version'], ExpectedBucketOwner=cfg['account'])
        raw = response['Body'].read(262145)
        require(len(raw) <= 262144 and sha(raw) == reference['sha256'] and
                response['VersionId'] == reference['version'] and response.get('ServerSideEncryption') == 'aws:kms' and
                response.get('SSEKMSKeyId') == cfg['evidence_kms_key'] and not response.get('BucketKeyEnabled', False),
                'historical configuration provenance mismatch')
        value = json.loads(raw)
        require(set(value) == {'schema','environment','color','image','revision','task'} and
                value['schema'] == 'API_TASK_CONFIGURATION_V1' and all(
                    value[k] == target[k] for k in ('environment','color','image','revision')),
                'historical configuration identity mismatch')
        task = value['task']; spec = self.color(target['color'])
        name = spec['service']['loadBalancers'][0]['containerName']
        require(task['family'] == name and task['requiresCompatibilities'] == ['FARGATE'] and
                task['taskRoleArn'] == spec['roles']['task'] and task['executionRoleArn'] == spec['roles']['execution'] and
                len(task['containerDefinitions']) == 2 and
                {c['name'] for c in task['containerDefinitions']} == {name, name+'-readiness-probe'} and
                all(c['image'] == target['image'] for c in task['containerDefinitions']), 'historical task binding mismatch')
        app = next(c for c in task['containerDefinitions'] if c['name'] == name)
        environment = {v['name']:v['value'] for v in app['environment']}
        require(environment.get('Database__SecurityProfile') == 'validated-v2' and
                environment.get('APP_ENV') == cfg['environment'] and
                environment.get('Database__RunMigrationsOnStartup') == 'false', 'historical task is not strict runtime')
        require(re.fullmatch('[0-9a-f]{64}', environment.get('SQL_TRUST_MANIFEST_SHA256', '')) and
                sha(base64.b64decode(environment.get('SQL_TRUST_MANIFEST_B64', ''), validate=True)) ==
                environment['SQL_TRUST_MANIFEST_SHA256'], 'historical trust material differs')
        secrets = app['secrets']
        require(len(secrets) == 1 and secrets[0]['name'] == 'DB_CONN_STRING' and re.fullmatch(
            re.escape(spec['secret_arn']) + r':::[A-Za-z0-9-]{32,64}', secrets[0]['valueFrom']),
            'historical versioned runtime secret differs')
        return task

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
                targets = self.aws['elbv2'].describe_target_health(TargetGroupArn=self.target(color))['TargetHealthDescriptions']
                if not targets:
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


def verify_manifest(aws, scope, record):
    reference = manifest_reference(record['manifest_ref'])
    import re
    require(record['environment'] == scope['environment'] and reference['bucket'] == scope['bucket'] and
            re.fullmatch('api-delivery/' + scope['environment'] + r'/operations/[0-9a-f-]{36}/release.json', reference['key']),
            'manifest outside admitted environment')
    response = aws['s3'].get_object(Bucket=scope['bucket'], Key=reference['key'], VersionId=reference['version'],
                                     ExpectedBucketOwner=scope['account'])
    raw = response['Body'].read(262145)
    require(len(raw) <= 262144 and sha(raw) == reference['sha256'] and response['VersionId'] == reference['version'] and
            response.get('ServerSideEncryption') == 'aws:kms' and response.get('SSEKMSKeyId') == scope['kms_key'] and
            not response.get('BucketKeyEnabled', False),
            'manifest bytes/version/encryption mismatch')
    require(json.loads(raw) == {k:v for k,v in record.items() if k != 'manifest_ref'}, 'GitHub and S3 deployment differ')
    return json.loads(raw)


def verify_image(aws, cfg, image):
    require(image.startswith(cfg['repository'] + '@sha256:'), 'shared ECR repository not admitted')
    digest = image.split('@')[1]; name = cfg['repository'].split('/', 1)[1]
    result = aws['ecr'].batch_get_image(registryId=cfg['account'], repositoryName=name, imageIds=[{'imageDigest': digest}])
    require(not result.get('failures') and len(result['images']) == 1, 'ECR manifest unavailable')
    item = result['images'][0]
    require(item['registryId'] == cfg['account'] and item['repositoryName'] == name and
            item['imageId']['imageDigest'] == digest and 'sha256:' + sha(item['imageManifest'].encode('utf-8')) == digest and
            item['imageManifestMediaType'] in ('application/vnd.oci.image.manifest.v1+json',
                'application/vnd.oci.image.index.v1+json', 'application/vnd.docker.distribution.manifest.v2+json',
                'application/vnd.docker.distribution.manifest.list.v2+json'), 'ECR manifest identity differs')
    return digest


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
