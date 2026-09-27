"""Hermetic WP4A production-contract tests. Facts are protected-port fixtures."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.normal_delivery import authorization as a
from scripts.qualification import finalizer as f

ACCOUNT = '111122223333'
REGION = 'us-east-1'
DIGEST = 'sha256:' + 'b' * 64
REPOSITORY = 'demo-shared-demo-ms'
URI = ACCOUNT + '.dkr.ecr.' + REGION + '.amazonaws.com/' + REPOSITORY + '@' + DIGEST
SOURCE = 'a' * 40


def make_binding(env, color='blue'):
    family = 'demo-' + env + '-app-api-' + color
    role = 'arn:aws:iam::' + ACCOUNT + ':role/' + family
    elb = 'arn:aws:elasticloadbalancing:' + REGION + ':' + ACCOUNT + ':'
    return dict(schema='E1_DELIVERY_BINDING_V1', environment=env, color=color,
                account=ACCOUNT, region=REGION, runtime_contract=f.RUNTIME,
                max_replicas=3, roles=dict(task=role + '-task-role', execution=role + '-exec-role'),
                secret_arn='arn:aws:secretsmanager:' + REGION + ':' + ACCOUNT
                + ':secret:demo/' + env + '/app/db-connection-string-ABC123',
                kms_key_arn='arn:aws:kms:' + REGION + ':' + ACCOUNT
                + ':key/12345678-1234-1234-1234-123456789abc',
                log_group='/aws/ecs/' + family,
                listener_arn=elb + 'listener/app/demo-' + env + '-alb/abcdef/012345',
                candidate_rule_arn=elb + 'listener-rule/app/demo-' + env + '-alb/abcdef/012345/789abc',
                service=dict(cluster='arn:aws:ecs:' + REGION + ':' + ACCOUNT + ':cluster/demo-' + env + '-cluster',
                             service=family + '-svc', enableExecuteCommand=False, launchType='FARGATE',
                             schedulingStrategy='REPLICA', propagateTags='SERVICE',
                             deploymentController={'type': 'ECS'},
                             deploymentConfiguration={'minimumHealthyPercent': 100, 'maximumPercent': 200},
                             capacityProviderStrategy=[], healthCheckGracePeriodSeconds=0,
                             enableECSManagedTags=False, platformVersion='1.4.0',
                             networkConfiguration={'awsvpcConfiguration': {
                                 'subnets': ['subnet-12345678', 'subnet-abcdef12'],
                                 'securityGroups': ['sg-12345678'], 'assignPublicIp': 'DISABLED'}},
                             loadBalancers=[{'targetGroupArn': elb + 'targetgroup/demo-' + env + '-' + color
                                             + '/0123456789abcdef', 'containerName': family, 'containerPort': 8080}]),
                bootstrap={'desiredCount': 0, 'taskDefinition': {
                    'family': family, 'networkMode': 'awsvpc', 'requiresCompatibilities': ['FARGATE'],
                    'cpu': '256', 'memory': '512', 'containerDefinitions': [
                        {'name': family, 'image': 'public.ecr.aws/docker/library/nginx:stable', 'essential': True}]}})


class Fixture(a.Facts):
    def __init__(self):
        self.calls = []
        manifest = dict(schemaVersion='1.0', app='demo-api', repository='Kendall04/terragrunt_demo',
                        gitSha=SOURCE, sourceBranch='develop', githubRunId='42', githubRunAttempt='1',
                        createdAt='2026-09-25T00:00:00Z', image=dict(
                            registry=ACCOUNT + '.dkr.ecr.' + REGION + '.amazonaws.com',
                            repository=REPOSITORY, tag='candidate', digest=DIGEST, uri=URI),
                        quality=dict(dotnetTests='passed', dockerBuild='passed', scanStatus='unknown'))
        self.manifest_bytes = f.canonical(manifest)
        self.ref = dict(bucket='demo-release-artifacts-' + ACCOUNT,
                        key='releases/demo-api/by-digest/sha256-' + DIGEST[7:] + '.json',
                        version_id='manifest-version-A', sha256=f.checksum(self.manifest_bytes))
        q = dict(schema='E1_QUALIFICATION_V1', writer='QUALIFICATION_FINALIZER', account=ACCOUNT,
                 region=REGION, repository='Kendall04/terragrunt_demo',
                 operation_id='11111111-1111-1111-1111-111111111111', project='e1-controller-release',
                 build_id='e1-controller-release:22222222-2222-2222-2222-222222222222',
                 source_commit=SOURCE, checks={name: 'PASS' for name in f.REQUIRED_CHECKS},
                 image_repository=REPOSITORY, image_digest=DIGEST, runtime_contract=f.RUNTIME,
                 manifest=self.ref)
        q['release_id'] = 'sha256-' + f.checksum(f.canonical(q))
        self.q = q
        self.q_raw = f.canonical(q)
        self.e = dict(schema='E1_ELIGIBILITY_V1', writer='SECURITY_ADMIN', release_id=q['release_id'],
                      state='ELIGIBLE', version_id='eligibility-version-A')
        self.e_env = lambda: dict(release_id=q['release_id'], version_id=self.e['version_id'], bytes=f.canonical(self.e))
        self.bindings = {key: make_binding(env) for key, env in a.ENDPOINTS.items()}
        self.receipt = self.protected('E1_DEV_ACTIVATION_RECEIPT_V1', 'NORMAL_DELIVERY_DEV', outcome='ACTIVATED')
        self.approval = self.protected('E1_PROD_APPROVAL_CONTEXT_V1', 'PROTECTED_PROD_APPROVAL', consumer='promote-prod')
        self.available = dict(account=ACCOUNT, region=REGION, repository=REPOSITORY, digest=DIGEST, available=True)

    def protected(self, schema, writer, **extra):
        record = dict(schema=schema, writer=writer, release_id=self.q['release_id'],
                      source_commit=SOURCE, image_uri=URI, runtime_contract=f.RUNTIME,
                      manifest_version_id=self.ref['version_id'], manifest_sha256=self.ref['sha256'],
                      qualification_sha256=f.checksum(f.canonical(self.q)),
                      account=ACCOUNT, region=REGION, **extra)
        return dict(release_id=self.q['release_id'], version_id=schema + '-version-A', bytes=f.canonical(record))

    def qualification(self, release_id):
        self.calls.append(('qualification', release_id)); return self.q_raw

    def manifest(self, bucket, key, version_id):
        self.calls.append(('manifest', bucket, key, version_id))
        return dict(bucket=self.ref['bucket'], key=self.ref['key'], version_id=self.ref['version_id'],
                    bytes=self.manifest_bytes)

    def eligibility_current(self, release_id):
        self.calls.append(('eligibility_current', release_id)); return self.e_env()

    def environment(self, endpoint):
        self.calls.append(('environment', endpoint))
        return dict(endpoint=endpoint, version_id='binding-' + endpoint, bytes=f.canonical(self.bindings[endpoint]))

    def artifact(self, repository, digest):
        self.calls.append(('artifact', repository, digest)); return copy.deepcopy(self.available)

    def promotion(self, release_id):
        self.calls.append(('promotion', release_id))
        return dict(dev_receipt=copy.deepcopy(self.receipt), prod_approval=copy.deepcopy(self.approval))


def response(intent):
    task = copy.deepcopy(intent['task'])
    family = task['family']
    task.update(taskDefinitionArn='arn:aws:ecs:' + REGION + ':' + ACCOUNT
                + ':task-definition/' + family + ':17', revision=17, status='ACTIVE',
                registeredAt='2026-09-25T00:00:00Z', compatibilities=['FARGATE'],
                requiresAttributes=[], deregisteredAt=None)
    task['volumes'] = []
    task['containerDefinitions'][0]['mountPoints'] = []
    task['containerDefinitions'][0]['portMappings'][0]['hostPort'] = 8080
    task['containerDefinitions'][1]['environment'] = []
    task['containerDefinitions'][1]['portMappings'] = []
    service = copy.deepcopy(intent['service'])
    service['taskDefinition'] = task['taskDefinitionArn']
    return dict(taskDefinition=task, service=service)


class Tests(unittest.TestCase):
    def setUp(self):
        self.facts = Fixture()
        self.core = a.Authorizer('deploy-dev', ACCOUNT, REGION, self.facts)
        self.raw = a.canonical({'release_id': self.facts.q['release_id'], 'replicas': 2})

    def intent(self): return self.core.authorize(self.raw)

    def reject(self, *, raw=None, core=None):
        with self.assertRaises(a.Rejected) as caught:
            (core or self.core).authorize(raw if raw is not None else self.raw)
        self.assertEqual(str(caught.exception), 'E1_NORMAL_DELIVERY_REJECTED')

    def test_positive_dev_and_exact_wp3_bindings(self):
        intent = self.intent()
        self.assertEqual(intent, self.intent())
        self.assertEqual(intent['task']['containerDefinitions'][0]['image'], URI)
        self.assertEqual(intent['task']['containerDefinitions'][1]['image'], URI)
        self.assertEqual(intent['eligibility']['version_id'], 'eligibility-version-A')
        self.assertEqual(intent['service']['desiredCount'], 2)
        self.assertIn(('artifact', REPOSITORY, DIGEST), self.facts.calls)

    def test_positive_prod_same_artifact_distinct_binding(self):
        dev = self.intent()
        prod = a.Authorizer('promote-prod', ACCOUNT, REGION, self.facts).authorize(self.raw)
        self.assertEqual(dev['task']['containerDefinitions'][0]['image'], prod['task']['containerDefinitions'][0]['image'])
        self.assertNotEqual(dev['task']['taskRoleArn'], prod['task']['taskRoleArn'])
        self.assertNotEqual(dev['service']['cluster'], prod['service']['cluster'])
        self.assertIsNotNone(prod['promotion'])

    def test_positive_normalized_readback(self):
        intent = self.intent()
        result = self.core.validate_readback(intent, a.canonical(response(intent)))
        self.assertEqual(result['revision'], 17)
        self.assertEqual(result['intent_sha256'], intent['intent_sha256'])
        registered = self.core.validate_registration_readback(intent, a.canonical(response(intent)['taskDefinition']))
        self.assertEqual(registered, result)

    def test_request_rejects_authority_fields_and_duplicates(self):
        for field in ('image', 'taskRoleArn', 'executionRoleArn', 'service', 'cluster', 'environment',
                      'approved', 'ready', 'qualified', 'taskDefinition', 'runtimePlatform', 'secret_arn'):
            with self.subTest(field=field): self.reject(raw=a.canonical({'release_id': self.facts.q['release_id'], 'replicas': 2, field: 'x'}))
        self.reject(raw=b'{"release_id":"' + self.facts.q['release_id'].encode() + b'","replicas":2,"replicas":3}')
        for replicas in (0, 101, True, '2'):
            with self.subTest(replicas=replicas):
                self.reject(raw=a.canonical({'release_id': self.facts.q['release_id'], 'replicas': replicas}))

    def test_qualification_and_manifest_negative(self):
        for mutate in (lambda: setattr(self.facts, 'q_raw', b'{}'),
                       lambda: setattr(self.facts, 'q_raw', f.canonical({**self.facts.q, 'source_commit': 'c' * 40})),
                       lambda: setattr(self.facts, 'manifest_bytes', b'{}'),
                       lambda: setattr(self.facts, 'manifest_bytes', self.facts.manifest_bytes.replace(DIGEST.encode(), b'sha256:' + b'c'*64))):
            with self.subTest(mutate=mutate):
                self.setUp(); mutate(); self.reject()
        self.reject(raw=a.canonical({'release_id': 'sha256-' + '0'*64, 'replicas': 1}))
        self.setUp(); self.facts.q['image_digest'] = 'latest'
        self.facts.q_raw = f.canonical(self.facts.q)
        self.reject()

    def test_eligibility_currentness(self):
        self.facts.e['state'] = 'REVOKED'; self.reject()
        self.setUp(); self.facts.e['version_id'] = 'old'; self.facts.e_env = lambda: dict(
            release_id=self.facts.q['release_id'], version_id='current', bytes=f.canonical(self.facts.e)); self.reject()
        self.setUp(); self.facts.e['release_id'] = 'sha256-' + '0'*64; self.reject()
        self.setUp(); self.facts.e_env = lambda: None; self.reject()

    def test_artifact_exactness(self):
        for field, value in [('repository', 'other'), ('digest', 'sha256:'+'c'*64), ('available', False)]:
            with self.subTest(field=field):
                self.setUp(); self.facts.available[field] = value; self.reject()

    def test_binding_cross_environment_and_current_gaps(self):
        self.facts.bindings['deploy-dev'] = make_binding('prod'); self.reject()
        self.setUp(); self.facts.bindings['deploy-dev']['service']['enableExecuteCommand'] = True; self.reject()
        self.setUp(); self.facts.bindings['deploy-dev']['service']['platformVersion'] = 'LATEST'; self.reject()
        self.setUp(); self.facts.bindings['deploy-dev']['bootstrap']['taskDefinition']['taskRoleArn'] = 'arn:aws:iam::'+ACCOUNT+':role/workload'; self.reject()
        self.setUp(); self.facts.bindings['deploy-dev']['bootstrap']['taskDefinition']['containerDefinitions'][0]['secrets'] = [{'name':'DB_CONN_STRING','valueFrom':'x'}]; self.reject()

    def test_prod_protected_prerequisites(self):
        prod = a.Authorizer('promote-prod', ACCOUNT, REGION, self.facts)
        self.facts.receipt['bytes'] = b'{}'; self.reject(core=prod)
        self.setUp(); prod = a.Authorizer('promote-prod', ACCOUNT, REGION, self.facts)
        self.facts.approval['version_id'] = 'latest'; self.reject(core=prod)

    def test_nested_readback_mutation_matrix(self):
        intent = self.intent()
        base = response(intent)
        paths = [
            ('taskDefinition', 'family'), ('taskDefinition', 'networkMode'),
            ('taskDefinition', 'requiresCompatibilities'), ('taskDefinition', 'cpu'),
            ('taskDefinition', 'memory'), ('taskDefinition', 'taskRoleArn'),
            ('taskDefinition', 'executionRoleArn'), ('taskDefinition', 'runtimePlatform', 'cpuArchitecture'),
            ('taskDefinition', 'runtimePlatform', 'operatingSystemFamily'),
            ('taskDefinition', 'containerDefinitions', 0, 'image'),
            ('taskDefinition', 'containerDefinitions', 0, 'essential'),
            ('taskDefinition', 'containerDefinitions', 0, 'portMappings', 0, 'containerPort'),
            ('taskDefinition', 'containerDefinitions', 0, 'environment', 0, 'value'),
            ('taskDefinition', 'containerDefinitions', 0, 'secrets', 0, 'valueFrom'),
            ('taskDefinition', 'containerDefinitions', 0, 'logConfiguration', 'options', 'awslogs-group'),
            ('taskDefinition', 'containerDefinitions', 1, 'command', 0),
            ('taskDefinition', 'containerDefinitions', 1, 'essential'),
            ('taskDefinition', 'containerDefinitions', 1, 'image'),
            ('service', 'cluster'), ('service', 'service'), ('service', 'enableExecuteCommand'),
            ('service', 'platformVersion'),
            ('service', 'networkConfiguration', 'awsvpcConfiguration', 'securityGroups', 0),
            ('service', 'networkConfiguration', 'awsvpcConfiguration', 'subnets', 0),
            ('service', 'loadBalancers', 0, 'targetGroupArn'),
            ('service', 'deploymentConfiguration', 'maximumPercent'),
            ('service', 'desiredCount')]
        for path in paths:
            with self.subTest(path=path):
                changed = copy.deepcopy(base)
                node = changed
                for key in path[:-1]: node = node[key]
                node[path[-1]] = 'MUTATED' if type(node[path[-1]]) is str else 999
                with self.assertRaises(a.Rejected): self.core.validate_readback(intent, a.canonical(changed))
        self.assertEqual(len(paths), 27)

    def test_every_canonical_runtime_leaf_is_closed(self):
        """Enumerate all populated nested task/service scalar fields, not examples."""
        intent = self.intent()
        base = response(intent)
        paths = []
        def visit(value, path):
            if type(value) is dict:
                for key, child in value.items(): visit(child, path + (key,))
            elif type(value) is list:
                for index, child in enumerate(value): visit(child, path + (index,))
            elif value is not None:
                paths.append(path)
        visit(intent['task'], ('taskDefinition',))
        visit(intent['service'], ('service',))
        self.assertEqual(len(paths), 56)
        for path in paths:
            with self.subTest(path=path):
                changed = copy.deepcopy(base)
                node = changed
                for key in path[:-1]: node = node[key]
                previous = node[path[-1]]
                if type(previous) is bool: replacement = not previous
                elif type(previous) is int: replacement = previous + 1
                else: replacement = previous + 'X'
                node[path[-1]] = replacement
                with self.assertRaises(a.Rejected):
                    self.core.validate_readback(intent, a.canonical(changed))

    def test_unknown_and_missing_nested_fields(self):
        intent = self.intent()
        for alter in (lambda v: v['taskDefinition']['containerDefinitions'][0].update(privileged=True),
                      lambda v: v['taskDefinition']['containerDefinitions'][0].update(newApiFeature='x'),
                      lambda v: v['taskDefinition']['containerDefinitions'][0].update(entryPoint=['sh']),
                      lambda v: v['taskDefinition']['containerDefinitions'][0].pop('secrets'),
                      lambda v: v['taskDefinition']['containerDefinitions'].append(copy.deepcopy(v['taskDefinition']['containerDefinitions'][1])),
                      lambda v: v['service'].update(forceNewDeployment=True),
                      lambda v: v['service']['networkConfiguration']['awsvpcConfiguration'].update(extra='x'),
                      lambda v: v['taskDefinition'].update(ephemeralStorage={'sizeInGiB': 21})):
            with self.subTest(alter=alter):
                changed = response(intent); alter(changed)
                with self.assertRaises(a.Rejected): self.core.validate_readback(intent, a.canonical(changed))

    def test_readback_identity_and_fresh_fact_change(self):
        intent = self.intent()
        changed = response(intent); changed['taskDefinition']['revision'] = 18
        with self.assertRaises(a.Rejected): self.core.validate_readback(intent, a.canonical(changed))
        self.facts.e['state'] = 'REVOKED'
        with self.assertRaises(a.Rejected): self.core.validate_readback(intent, a.canonical(response(intent)))

    def test_model_vocabulary_closure(self):
        vocabulary = set(json.loads((ROOT/'ci/authority/runtime-vocabulary.json').read_text())['fields'])
        reviewed = set(json.loads((ROOT/'ci/authority/runtime-fields.json').read_text())['fields'])
        model = a.MODEL
        covered = ({'task.'+x for x in model['task_required']} | {'task.'+x for x in model['task_defaults']}
                   | {'task.'+x for x in model['forbidden_task']}
                   | {'container.'+x for x in model['container_required']['app']}
                   | {'container.'+x for x in model['container_required']['probe']}
                   | {'container.'+x for x in model['container_defaults']}
                   | {'container.'+x for x in model['forbidden_container']}
                   | {'service.'+x for x in model['service_ownership']}
                   | {'service.'+x for x in model['forbidden_service']}
                   | {'response.'+x for x in model['task_return_only']})
        self.assertEqual(vocabulary, covered)
        self.assertEqual(reviewed, vocabulary)
        self.assertEqual(set(model['service_required']) | {'desiredCount'},
                         set(model['service_ownership']) - {'taskDefinition'})
        self.assertEqual(set(a.TEMPLATE), set(model['task_required']))
        self.assertEqual(set(a.TEMPLATE['containerDefinitions'][0]), set(model['container_required']['app']))
        self.assertEqual(set(a.TEMPLATE['containerDefinitions'][1]), set(model['container_required']['probe']))

    def test_behavioral_mutants_remove_single_field_guard(self):
        """Four valid behavioral mutants; no syntax/import/setup detection counted."""
        intent = self.intent()
        original = a.exact
        cases = [
            (('taskDefinition', 'cpu'), 'task.cpu'),
            (('taskDefinition', 'containerDefinitions', 0, 'environment', 0, 'value'),
             'task.containerDefinitions[].environment[].value'),
            (('taskDefinition', 'containerDefinitions', 0, 'logConfiguration', 'options', 'awslogs-group'),
             'task.containerDefinitions[].logConfiguration.options.awslogs-group'),
            (('service', 'platformVersion'), 'service.platformVersion')]
        for path, target in cases:
            with self.subTest(target=target):
                changed = response(intent)
                node = changed
                for key in path[:-1]: node = node[key]
                node[path[-1]] = 'MUTATED'
                with self.assertRaises(a.Rejected):
                    self.core.validate_readback(intent, a.canonical(changed))
                def mutant(actual, expected, current):
                    if current == target: return None
                    return original(actual, expected, current)
                with patch.object(a, 'exact', mutant):
                    accepted = self.core.validate_readback(intent, a.canonical(changed))
                    self.assertEqual(accepted['revision'], 17)


if __name__ == '__main__': unittest.main()
