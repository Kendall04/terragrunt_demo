"""Production entrypoint, package closure and effective multi-resource checks."""
import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import wp4d
from publication import AdminBundleStorage
from test_wp4d import ROOT, ACCOUNT, REGION, policy, permits, fixture, installed_projection
from scripts.wp4d import adapters
from scripts.wp4d.aws_runtime import Observer, Application, Nat
from scripts.normal_delivery import authorization as a, delivery as d
from scripts.recovery.application import Cleanup, Emergency


class Completion(unittest.TestCase):
    def test_sdk_clients_never_retry_ambiguous_mutations(self):
        received = []
        def config(**kw): return kw
        def client(name, **kw): received.append((name, kw)); return name
        with patch.dict(sys.modules, {'boto3': SimpleNamespace(client=client),
                                     'botocore.config': SimpleNamespace(Config=config)}):
            spec = importlib.util.spec_from_file_location('installed', ROOT/'scripts/wp4d/installed.py')
            installed = importlib.util.module_from_spec(spec); spec.loader.exec_module(installed)
            sys.modules['installed'] = installed
            spec = importlib.util.spec_from_file_location('bootstrap', ROOT/'scripts/wp4d/runtime.py')
            runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
            clients = runtime._clients({'region':REGION})
        self.assertEqual(len(received), len(clients))
        for name, kwargs in received:
            self.assertEqual(kwargs['config']['retries']['total_max_attempts'], 1)
            self.assertEqual(kwargs['region_name'], REGION)
            self.assertEqual(kwargs['config']['read_timeout'], 5)

    def test_schedule_requires_all_exact_targets_and_nonempty_context(self):
        p = policy('normal-delivery/deploy-dev'); r = fixture('dev')
        target, rule = r['cleanup']['function_arn'], r['cleanup']['rule_arn']
        self.assertTrue(permits(p, 'events:PutTargets', rule, {'events:TargetArn':[target]}))
        for context in ({}, {'events:TargetArn':[]}, {'events:TargetArn':[target, target+'-foreign']}):
            self.assertFalse(permits(p, 'events:PutTargets', rule, context))

    def test_gateway_matrix_cannot_start_other_controllers(self):
        suffixes = ('deploy-dev', 'promote-prod', 'emergency-dev', 'emergency-prod')
        for source in suffixes:
            for destination in suffixes:
                self.assertEqual(permits(policy('request-gateway/'+source), 'codebuild:StartBuild',
                    f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-'+destination),
                    source == destination)

    def test_evidence_put_requires_conditional_creation(self):
        for binding, (env, _) in wp4d.RESERVED.items():
            p = policy(binding)
            for statement in p['Statement']:
                if statement['Action'] == ['s3:PutObject'] and statement.get('Condition') == {'StringEquals': {'s3:if-none-match': '*'}}:
                    resource = statement['Resource'][0].replace('*', 'immutable.json')
                    self.assertTrue(permits(p, 's3:PutObject', resource, {'s3:if-none-match':'*'}))
                    self.assertFalse(permits(p, 's3:PutObject', resource))
                    self.assertFalse(permits(p, 's3:PutObject', resource, {'s3:if-none-match':'other'}))

    def test_every_package_contains_its_transitive_script_imports(self):
        for binding in wp4d.RESERVED:
            files = set(wp4d.package_sources(binding))
            for name in files:
                if not name.endswith('.py'):
                    continue
                for node in ast.walk(ast.parse((ROOT / name).read_text())):
                    if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('scripts.'):
                        path = node.module.replace('.', '/')
                        if path + '.py' in files:
                            continue
                        for alias in node.names:
                            self.assertIn(path + '/' + alias.name + '.py', files, (binding, name))

        # Test the actual extracted modules, including their import order.
        import base64
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        for selected in ('normal-delivery/deploy-dev','cleanup-recovery/cleanup-dev'):
            with tempfile.TemporaryDirectory() as directory:
                package=json.loads(wp4d.artifact(ROOT,authority['control_bundles'],selected))
                for name,encoded in package['files'].items():
                    destination=Path(directory)/name;destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes(base64.b64decode(encoded))
                code = r"""
import sys,copy
sys.path.insert(0,sys.argv[1])
from scripts.normal_delivery import authorization as a
from scripts.wp4d import dev_delivery_contract as dev
from scripts.wp4d.aws_runtime import Observer
assert Observer.__module__=='scripts.wp4d.dev_delivery_contract'
release='sha256-'+'a'*64
record={'schema':'E1_ELIGIBILITY_DEV_V2','writer':'SECURITY_ADMIN','release_id':release,'state':'ELIGIBLE'}
def envelope(body=record,version='returned-current-S3-version'):
 return {'release_id':release,'version_id':version,'bytes':a.canonical(body)}
assert a._dev_eligibility(envelope(),release,'deploy-dev')==record
for value,endpoint in [(envelope(),'promote-prod'),(envelope(version='latest'),'deploy-dev'),
 (envelope(record|{'state':'REVOKED'}),'deploy-dev'),(envelope(record|{'version_id':'invented'}),'deploy-dev'),
 (envelope(record|{'writer':'WORKFLOW'}),'deploy-dev'),(envelope(record|{'release_id':'sha256-'+'b'*64}),'deploy-dev')]:
 try:a._dev_eligibility(value,release,endpoint)
 except ValueError:pass
 else:raise AssertionError('Invalid eligibility accepted')
base={'minimumHealthyPercent':100,'maximumPercent':200}
observed=base|{'deploymentCircuitBreaker':{'enable':False,'rollback':False},'strategy':'ROLLING','bakeTimeInMinutes':0}
assert dev.deployment(observed)==base and 'strategy' in observed
for field,value in [('strategy','BLUE_GREEN'),('deploymentCircuitBreaker',{'enable':True,'rollback':False}),
 ('bakeTimeInMinutes',False),('bakeTimeInMinutes',1),('unknown',0)]:
 try:dev.deployment(observed|{field:value})
 except ValueError:pass
 else:raise AssertionError('Active/unknown ECS configuration accepted')
class Base:
 config={'environment':'dev'}
 def service(self,color):return {'deploymentConfiguration':copy.deepcopy(observed),'platformVersion':'LATEST'},[],True
service,_,stable=dev.observer(Base)().service('green')
assert service['platformVersion']=='LATEST' and stable
print('EXTRACTED_DEV_CONTRACT_PASS')
"""
                saved={k:v for k,v in sys.modules.items() if k=='scripts' or k.startswith('scripts.')}
                try:
                    for key in saved:sys.modules.pop(key,None)
                    with patch.object(sys,'argv',['extracted-test',directory]), patch.object(sys,'path',list(sys.path)):
                        exec(compile(code,'extracted-dev-contract','exec'),{})
                finally:
                    for key in list(sys.modules):
                        if key=='scripts' or key.startswith('scripts.'):sys.modules.pop(key,None)
                    sys.modules.update(saved)

    def test_installation_receipt_requires_returned_identity_and_exact_readback(self):
        authority = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
        class Storage(AdminBundleStorage):
            bad = None
            def put_if_absent(self, bucket, key, raw, checksum_sha256):
                self.raw = raw
                self.identity = dict(bucket=bucket, key=key, version_id='returned-version')
                return {**self.identity, 'version_id': 'latest'} if self.bad == 'version' else self.identity
            def get_exact(self, bucket, key, version_id):
                return {**self.identity, 'bytes': self.raw + (b'!' if self.bad == 'bytes' else b'')}
        store = Storage()
        receipt = wp4d.install(ROOT, authority, 'cleanup-recovery/cleanup-dev', ACCOUNT, REGION, store)
        self.assertEqual(receipt['version_id'], 'returned-version')
        for failure in ('version', 'bytes'):
            store.bad = failure
            with self.assertRaises(ValueError):
                wp4d.install(ROOT, authority, 'cleanup-recovery/cleanup-dev', ACCOUNT, REGION, store)

    def test_missing_or_substituted_prerequisites_never_activate_compute(self):
        authority = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
        installs, images, bindings = installed_projection(authority)
        evaluate = lambda i, r, b: wp4d.creation_supported(authority, i, r, b, ACCOUNT, REGION)
        for field, replacement in [('version_id', None), ('readback', 'UNVERIFIED'),
                                   ('sha256', 'f'*64), ('binding', 'foreign')]:
            wrong = copy.deepcopy(installs)
            for key in wrong: wrong[key][field] = replacement
            self.assertEqual(evaluate(wrong, images, bindings), [])
        for remove in ('ami', 'user_data_sha256', 'role'):
            wrong = copy.deepcopy(bindings)
            del wrong['dev']['nat_slots'][0]['spec'][remove]
            self.assertTrue(all('dev' not in k for k in evaluate(installs, images, wrong)))
        wrong = copy.deepcopy(bindings)
        del wrong['dev']['colors']['blue']['secret_arn']
        self.assertTrue(all('dev' not in k for k in evaluate(installs, images, wrong)))
        self.assertEqual(evaluate(installs, {}, bindings), [])
        del installs['cleanup-recovery/cleanup-dev']
        self.assertTrue(all('dev' not in k or k.startswith('nat-recovery/')
                            for k in evaluate(installs, images, bindings)))

    def test_passrole_all_four_pairs_and_absent_condition(self):
        for env, suffix in [('dev', 'deploy-dev'), ('prod', 'promote-prod')]:
            p, resources = policy('normal-delivery/' + suffix), fixture(env)
            for color in ('blue', 'green'):
                for field in ('task_role', 'execution_role'):
                    role = resources['colors'][color][field]
                    self.assertTrue(permits(p, 'iam:PassRole', role,
                                           {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}))
                    self.assertFalse(permits(p, 'iam:PassRole', role))
                    self.assertFalse(permits(p, 'iam:PassRole', role.replace(ACCOUNT, '999999999999'),
                                            {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}))

    def test_nat_eip_and_eni_must_both_be_authorized(self):
        p = policy('nat-recovery/nat-dev/assign_eip')
        eip = f'arn:aws:ec2:{REGION}:{ACCOUNT}:elastic-ip/eipalloc-1'
        eni = f'arn:aws:ec2:{REGION}:{ACCOUNT}:network-interface/eni-replacement'
        subnet = f'arn:aws:ec2:{REGION}:{ACCOUNT}:subnet/subnet-1'
        call = lambda address, interface, context: all(
            permits(p, 'ec2:AssociateAddress', resource, context) for resource in (address, interface))
        self.assertTrue(call(eip, eni, {'ec2:Subnet': subnet}))
        self.assertFalse(call(eip + 'foreign', eni, {'ec2:Subnet': subnet}))
        self.assertFalse(call(eip, eni, {'ec2:Subnet': subnet + 'foreign'}))
        self.assertFalse(call(eip, eni, {}))
        self.assertFalse(call(eip, eni.replace(ACCOUNT, '999999999999'), {'ec2:Subnet': subnet}))

    def test_disable_sdc_attribute_and_environment_are_required(self):
        p = policy('nat-recovery/nat-dev/disable_sdc')
        instance = f'arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-replacement'
        context = {'ec2:Attribute': 'SourceDestCheck', 'aws:ResourceTag/Environment': 'dev',
                   'aws:ResourceTag/Role': 'nat'}
        self.assertTrue(permits(p, 'ec2:ModifyInstanceAttribute', instance, context))
        self.assertFalse(permits(p, 'ec2:ModifyInstanceAttribute', instance, {**context,'ec2:Attribute':'sourceDestCheck'}))
        prod=policy('nat-recovery/nat-prod/disable_sdc')
        prod_statement=next(s for s in prod['Statement'] if s['Action']==['ec2:ModifyInstanceAttribute'])
        self.assertEqual(prod_statement['Condition']['StringEquals']['ec2:Attribute'],'sourceDestCheck')
        for field, bad in [('ec2:Attribute', 'userData'), ('aws:ResourceTag/Environment', 'prod'),
                           ('aws:ResourceTag/Role', 'app')]:
            self.assertFalse(permits(p, 'ec2:ModifyInstanceAttribute', instance, {**context, field: bad}))
        for field in context:
            self.assertFalse(permits(p, 'ec2:ModifyInstanceAttribute', instance,
                                    {k:v for k,v in context.items() if k != field}))

    def test_evidence_and_installation_access_is_class_owned(self):
        for duty in ('assign_eip','change_rt','disable_sdc'):
            p = policy('nat-recovery/nat-dev/'+duty)
            bucket = f'arn:aws:s3:::e1-wp4-dev-{ACCOUNT}-{REGION}'
            self.assertTrue(permits(p,'s3:ListBucket',bucket,{'s3:prefix':'recovery/dev/recovery/'+duty+'/op/intent'}))
            for prefix in ('arbitration/dev/', 'recovery/prod/recovery/'+duty+'/', 'delivery/dev/', 'recovery/dev/recovery/foreign/'):
                self.assertFalse(permits(p,'s3:ListBucket',bucket,{'s3:prefix':prefix}))
            self.assertFalse(permits(p,'s3:ListBucket',bucket,{}))
            self.assertFalse(permits(policy('nat-recovery/nat-prod/'+duty),'s3:ListBucket',bucket,{'s3:prefix':'recovery/dev/recovery/'+duty+'/'}))
        for binding, (env, _) in wp4d.RESERVED.items():
            p = policy(binding)
            foreign = 'prod' if env == 'dev' else 'dev'
            for prefix in ('delivery', 'recovery', 'gateway', 'history', 'activations'):
                self.assertFalse(permits(p, 's3:PutObject',
                    f'arn:aws:s3:::e1-wp4-{foreign}-{ACCOUNT}-{REGION}/{prefix}/x',
                    {'s3:if-none-match': '*'}))
            package = f'arn:aws:s3:::e1-control-bundles-{ACCOUNT}-{REGION}/bundles/sha256/' + 'a'*64 + '.json'
            self.assertTrue(permits(p, 's3:GetObjectVersion', package, {'s3:VersionId': 'version-1'}))
            self.assertFalse(permits(p, 's3:GetObjectVersion', package, {'s3:VersionId': 'other'}))
            self.assertFalse(permits(p, 's3:GetObject', package))
            for action in ('s3:PutObject', 'sts:AssumeRole', 'iam:PutRolePolicy', 'ecr:PutImage'):
                self.assertFalse(permits(p, action, package, {'s3:if-none-match': '*'}))

    def test_entrypoints_construct_real_storage_and_runtime_ports(self):
        # Load exactly the image bootstrap. It has no boto dependency at import.
        with patch.dict(sys.modules):
            spec = importlib.util.spec_from_file_location('installed', ROOT/'scripts/wp4d/installed.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            sys.modules['installed'] = module
            spec = importlib.util.spec_from_file_location('wp4d_bootstrap', ROOT/'scripts/wp4d/runtime.py')
            runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
            _, _, bindings = installed_projection(json.loads((ROOT/'terraform/infra/security/authority.json').read_text()))
            resources = bindings['dev']
            config = {k: 'protected' for k in ('account', 'region', 'environment', 'admin_bucket',
                       'evidence_bucket', 'dev_evidence_bucket', 'repository', 'binding')}
            config.update(environment='dev', account=ACCOUNT, region=REGION, resources=resources)
            spec_store = importlib.util.spec_from_file_location('e2_test_storage', ROOT/'scripts/tests/mutation/test_mutation.py')
            storage_module = importlib.util.module_from_spec(spec_store); spec_store.loader.exec_module(storage_module)
            store = storage_module.S3()
            from scripts.environment_mutation import Store, Authority
            owner_store = Store(store, config['evidence_bucket'], 'dev')
            owner_store.initialize()
            operation = '11111111-2222-3333-4444-555555555555'
            clients = dict.fromkeys(('ecs', 'elbv2', 'events', 's3', 'ecr'))
            clients['s3'] = store
            with patch.object(runtime, '_wakeup', return_value=(operation, {})), \
                    patch.object(d.Delivery, 'run', return_value={'status': 'FAILURE'}):
                config['binding'] = 'normal-delivery/deploy-dev'
                self.assertEqual(runtime._normal(clients, config)['status'], 'FAILURE')
            with patch.object(adapters.Facts, 'membership', return_value={
                    'environment': 'dev', 'version_id': 'exact', 'bytes': a.canonical({'colors': resources['colors']})}), \
                    patch.object(Cleanup, 'run', return_value={'status': 'FAILURE'}), \
                    patch.object(Emergency, 'run', return_value={'status': 'FAILURE'}):
                config['binding'] = 'cleanup-recovery/cleanup-dev'
                self.assertEqual(runtime._application(clients, config, operation, True)['status'], 'UNCERTAIN')
                config['binding'] = 'emergency-recovery/emergency-dev'
                self.assertEqual(runtime._application(clients, config, operation)['status'], 'FAILURE')
            public = {key:raw for (bucket,key),(raw,version) in store.values.items() if key.endswith('/public.json')}
            self.assertEqual(set(public),{'delivery/dev/'+operation+'/public.json',
                                         'recovery/dev/recovery/emergency/'+operation+'/public.json'})
            for raw in public.values():
                self.assertEqual(json.loads(raw),{'operation_id':operation,'state':'FAILURE','release_id':None,'source_commit':None})

    def test_warm_bootstrap_reloads_only_verified_package_modules(self):
        authority = json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        binding = 'request-gateway/deploy-dev'
        raw = wp4d.artifact(ROOT, authority['control_bundles'], binding)
        reference = dict(binding=binding, bucket='protected', version_id='exact',
                         key='bundles/sha256/'+wp4d.digest(raw)+'.json', sha256=wp4d.digest(raw))
        class Store:
            def get_object(self, **kw): return {'Body':io.BytesIO(raw), 'VersionId':'exact'}
        with patch.dict(sys.modules):
            spec = importlib.util.spec_from_file_location('installed', ROOT/'scripts/wp4d/installed.py')
            installed = importlib.util.module_from_spec(spec); spec.loader.exec_module(installed)
            sys.modules['installed'] = installed
            spec = importlib.util.spec_from_file_location('bootstrap', ROOT/'scripts/wp4d/runtime.py')
            runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
            for _ in range(2):
                with runtime._installed(Store(), dict(bundle=reference, binding=binding, environment='dev')) as directory:
                    from scripts.normal_delivery import authorization as installed_auth
                    self.assertEqual(installed_auth.ROOT, Path(directory.name))
                self.assertFalse(any(k == 'scripts' or k.startswith('scripts.') for k in sys.modules))

    def test_observer_rejects_mixed_deployments_and_foreign_task_target_mapping(self):
        resources = installed_projection(json.loads((ROOT/'terraform/infra/security/authority.json').read_text()))[2]['dev']
        member = resources['colors']['blue']
        revision = f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/demo-dev-app-api-blue:1'
        task = dict(taskArn='exact-task', clusterArn=member['cluster'], group='service:'+member['service'],
                    taskDefinitionArn=revision, lastStatus='RUNNING')
        service = dict(clusterArn=member['cluster'], serviceName=member['service'], status='ACTIVE',
                       taskDefinition=revision, desiredCount=1, runningCount=1, pendingCount=0,
                       deployments=[dict(taskDefinition=revision, status='PRIMARY', rolloutState='COMPLETED')],
                       loadBalancers=[dict(targetGroupArn=member['target_group'], containerName='demo-dev-app-api-blue', containerPort=8080)])
        class ECS:
            def describe_services(self, **kw): return {'services': [service]}
            def list_tasks(self, **kw): return {'taskArns': ['exact-task']}
            def describe_tasks(self, **kw): return {'tasks': [task]}
        observer = Observer(ECS(), None, resources)
        self.assertTrue(observer.service('blue')[2])
        for mutate in (lambda: service['deployments'].append(copy.deepcopy(service['deployments'][0])),
                       lambda: task.update(taskDefinitionArn=revision+'9'),
                       lambda: service['loadBalancers'][0].update(targetGroupArn='foreign')):
            old_service, old_task = copy.deepcopy(service), copy.deepcopy(task)
            mutate()
            with self.assertRaises(ValueError): observer.service('blue')
            service.clear(); service.update(old_service); task.clear(); task.update(old_task)
