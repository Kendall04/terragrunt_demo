"""Real bundle loader/factory and state machines, with in-memory AWS ports only."""
import base64
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
from contextlib import contextmanager
import unittest
from unittest.mock import patch

import wp4d

ROOT = Path(__file__).resolve().parents[3]
PROFILE = 'SQL_RESTORE_NO_MIGRATIONS_V2'


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class MemoryS3:
    """Exact versions and conditional create; no SDK or persistent storage."""
    def __init__(self): self.values = {}; self.calls = []
    def get_object(self, **kw):
        self.calls.append(('get', kw))
        if kw['Key'] not in self.values: raise Missing()
        raw, version = self.values[kw['Key']]
        if 'VersionId' in kw and kw['VersionId'] != version: raise Missing()
        return dict(Body=io.BytesIO(raw), VersionId=version, ETag='"'+wp4d.digest(raw)+'"')
    def put_object(self, **kw):
        self.calls.append(('put', kw))
        old = self.values.get(kw['Key'])
        if kw.get('IfNoneMatch') == '*' and old is not None: raise FileExistsError()
        if 'IfMatch' in kw and (old is None or kw['IfMatch'] != '"'+wp4d.digest(old[0])+'"'):
            raise FileExistsError()
        self.values[kw['Key']] = kw['Body'], 'version-'+wp4d.digest(kw['Body'])
        return dict(VersionId=self.values[kw['Key']][1])


def bootstrap():
    def read(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
        return value
    sys.modules['installed'] = read('installed', ROOT/'scripts/wp4d/installed.py')
    return read('fixture_bootstrap', ROOT/'scripts/wp4d/runtime.py')


@contextmanager
def installed_bundle(mutate=None):
    authority = json.loads((ROOT/'terraform/infra/security/authority.json').read_text(encoding='utf-8'))
    binding = 'normal-delivery/deploy-dev'
    package = json.loads(wp4d.artifact(ROOT, authority['control_bundles'], binding))
    if mutate: mutate(package)
    raw = wp4d.canonical(package); digest = wp4d.digest(raw)
    ref = dict(binding=binding, bucket='synthetic-protected', version_id='exact-fixture-version',
               key='bundles/sha256/'+digest+'.json', sha256=digest)
    s3 = MemoryS3(); s3.values[ref['key']] = raw, ref['version_id']
    config = dict(binding=binding, account='111122223333', region='us-east-1', environment='dev',
                  bundle=ref, delivery_contract=PROFILE, evidence_bucket='synthetic-evidence')
    # The production bootstrap intentionally purges all scripts.* warm modules.
    # Preserve the test runner's imports, but verify extracted domain modules.
    with patch.dict(sys.modules), patch.object(sys, 'path', list(sys.path)):
        runtime = bootstrap()
        with runtime._installed(s3, config) as directory:
            from scripts.normal_delivery import authorization as a, delivery as d, recovery as r
            from scripts.recovery import application
            from scripts.wp4d import adapters
            from scripts.wp4d import aws_runtime
            for module in (a, d, r, application, adapters, aws_runtime):
                assert Path(directory.name) in Path(module.__file__).parents, module.__file__
            from scripts.tests.delivery import fixtures as delivery_fixtures
            from scripts.tests.normal_delivery.test_authorization import Fixture
            from scripts.wp4d.dev_delivery_contract import ATTRIBUTES
            original_response = delivery_fixtures.response
            def native_shape(intent):
                observed = original_response(intent)
                observed['taskDefinition']['compatibilities'] = ['EC2','FARGATE','MANAGED_INSTANCES']
                observed['taskDefinition']['requiresAttributes'] = [{'name':v} for v in sorted(ATTRIBUTES)]
                return observed
            # Fixture outputs match the already materialized DEV contract. The
            # extracted validator/normalizer itself is never mocked or relaxed.
            with patch.object(delivery_fixtures, 'response', native_shape), \
                 patch.object(Fixture, 'eligibility_current', eligibility_fixture):
                yield runtime, config, s3, directory
        assert not any(k == 'scripts' or k.startswith('scripts.') for k in sys.modules)
        assert not Path(directory.name).exists()


def eligibility_fixture(self, release_id):
    from scripts.normal_delivery import authorization as a
    record = dict(schema='E1_ELIGIBILITY_DEV_V2', writer='SECURITY_ADMIN',
                  release_id=release_id, state='ELIGIBLE')
    return dict(release_id=release_id, version_id='current-fixture-version', bytes=a.canonical(record))


def fixture(runtime, config, recovery=True):
    from scripts.normal_delivery import authorization as a
    from scripts.tests.normal_delivery.test_recovery_v2 import CurrentFacts, approve
    from scripts.tests.delivery.fixtures import OP, Runtime, ProcessFixture
    from scripts.wp4d.adapters import Objects
    facts = approve(CurrentFacts()) if recovery else CurrentFacts()
    from types import MethodType
    facts.eligibility_current = MethodType(eligibility_fixture, facts)
    auth, controller = runtime._delivery_factory(config, OP, facts)
    if recovery: auth.clock = lambda: 1000
    request = dict(action='deliver', release_id=facts.q['release_id'], replicas=2)
    intent = auth.authorize(a.canonical({k:v for k,v in request.items() if k!='action'}))
    return facts, auth, controller, request, intent, Runtime, ProcessFixture, Objects, OP


class InstalledRecovery(unittest.TestCase):
    def test_exact_loader_versions_bytes_and_bootstrap_pin(self):
        with installed_bundle() as (runtime, c, s3, _):
            from installed import load
            import tempfile
            for field, bad in [('sha256','f'*64), ('version_id','other'), ('version_id','latest')]:
                ref = c['bundle'] | {field:bad}
                with tempfile.TemporaryDirectory() as target, self.assertRaises((ValueError,Missing)):
                    load(s3, ref, target)
            self.assertEqual(s3.calls[0][1]['VersionId'], c['bundle']['version_id'])
        def wrong(p): p['files']['scripts/wp4d/runtime.py']=base64.b64encode(b'wrong').decode()
        with self.assertRaises(ValueError):
            with installed_bundle(wrong): pass

    def test_configuration_v1_default_and_v2_only_protected_dev_normal(self):
        with installed_bundle() as (runtime,c,_,_):
            full = c | {k:'fixture' for k in ('runtime_image','project','dev_evidence_bucket','admin_bucket','repository')}
            full.update(resources={}, nat_slots=[])
            for value in (full, {k:v for k,v in full.items() if k!='delivery_contract'}):
                with patch.dict(runtime.os.environ, {'E1_PROTECTED_CONFIGURATION':json.dumps(value)}):
                    self.assertEqual(runtime.configuration(), value)
            for delta in ({'delivery_contract':'caller-profile'}, {'environment':'prod'},
                          {'binding':'emergency-recovery/emergency-dev'}, {'profile':PROFILE}):
                with patch.dict(runtime.os.environ, {'E1_PROTECTED_CONFIGURATION':json.dumps(full|delta)}), self.assertRaises(ValueError):
                    runtime.configuration()

    def test_factory_explicit_opt_in_and_no_caller_or_v1_fallback(self):
        with installed_bundle() as (runtime,c,_,_):
            from scripts.normal_delivery import authorization as a, delivery as d, recovery as r
            facts,auth,controller,request,intent,*_=fixture(runtime,c)
            self.assertIs(type(auth),r.RecoveryAuthorizer);self.assertIs(controller,r.RecoveryDelivery)
            self.assertEqual(intent['schema'],r.V2_INTENT)
            normal,core=runtime._delivery_factory({k:v for k,v in c.items() if k!='delivery_contract'},auth.operation_id,facts)
            self.assertIs(type(normal),a.Authorizer);self.assertIs(core,d.Delivery)
            with self.assertRaises(ValueError): normal.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))
            for field,value in [('profile',PROFILE),('delivery_contract',PROFILE),('secret_version_id','e'*32)]:
                with self.assertRaises(ValueError): auth.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)|{field:value}))
            foreign,_=runtime._delivery_factory(c,'66666666-2222-3333-4444-555555555555',facts)
            foreign.clock=lambda:1000
            with self.assertRaises(ValueError): foreign.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))

    def test_missing_or_changed_descriptor_refuses_selection(self):
        for mutate in (lambda p:p['files'].pop('ci/authority/recovery-profile-v2.json'),
                       lambda p:p['files'].__setitem__('ci/authority/recovery-profile-v2.json',base64.b64encode(b'{}').decode())):
            with self.assertRaises((ValueError,FileNotFoundError,KeyError)):
                with installed_bundle(mutate) as (runtime,c,_,_): fixture(runtime,c)

    def test_installed_normal_execution_history_public_receipt_and_no_v1_promotion(self):
        with installed_bundle() as (runtime,c,s3,_):
            from scripts.normal_delivery import authorization as a, delivery as d
            from scripts.wp4d import adapters, aws_runtime
            from scripts.environment_mutation import Store, Authority
            facts,auth,controller,request,intent,World,Process,Objects,op=fixture(runtime,c)
            records=Objects(s3,c['evidence_bucket'],'delivery/')
            world=World(intent,records,facts.members['dev']['colors']);process=Process(world)
            owner_store=Store(s3,c['evidence_bucket'],'dev');owner_store.initialize()
            owner=Authority(owner_store,c['binding'],op,request);owner.acquire()
            with patch.object(runtime,'_delivery_factory',return_value=(auth,controller)), \
                 patch.object(adapters,'Facts',return_value=facts), \
                 patch.object(aws_runtime,'Delivery',return_value=world), \
                 patch.object(aws_runtime,'BoundedProcess',return_value=process):
                result=runtime._normal_owned(dict(s3=s3,ecr=None,ecs=None,elbv2=None,events=None),
                        c|dict(admin_bucket='synthetic-admin',dev_evidence_bucket='synthetic-dev',repository='fixture',resources={}),op,request,owner)
            self.assertEqual(result,dict(operation=op,status='SUCCESS'))
            receipt=a.decode(records.read('dev/'+op+'/success')['bytes'])
            self.assertEqual(receipt['intent']['schema'],'E1_AUTHORIZED_RUNTIME_INTENT_V2')
            self.assertEqual(adapters.History(s3,c['evidence_bucket'],'dev').current()['blue'],op)
            self.assertEqual(a.decode(records.read('dev/'+op+'/public.json')['bytes']),
                             dict(operation_id=op,state='SUCCESS',release_id=None,source_commit=None))
            self.assertFalse(any(key.startswith('activations/by-release/') for key in s3.values))
            with self.assertRaises(ValueError):d.dev_prerequisite(receipt)
            forged=copy.deepcopy(receipt);forged['intent']['recovery']['evidence_sha256']='0'*64
            with self.assertRaises(ValueError):adapters.History(s3,c['evidence_bucket'],'dev').publish(forged,records)

    def test_v1_history_emergency_and_inactive_cleanup_still_execute(self):
        with installed_bundle():
            from scripts.tests.recovery.fixtures import application
            from scripts.tests.delivery.fixtures import NEXT
            from scripts.tests.normal_delivery.test_authorization import Fixture
            with patch.object(Fixture, 'eligibility_current', eligibility_fixture):
                for kind in ('emergency','cleanup'):
                    controller,world,records,_=application(kind,running=0 if kind=='emergency' else 1)
                    result=controller.run(NEXT,b'{}\n')
                    self.assertEqual(result['status'],'SUCCESS',result)
                    self.assertTrue(world.calls)

    def test_v2_history_cannot_be_used_by_v1_emergency_cleanup_remains_bounded(self):
        with installed_bundle() as (runtime,c,s3,_):
            from scripts.normal_delivery import authorization as a, delivery as d
            from scripts.normal_delivery.e3 import Gate
            from scripts.recovery.application import Emergency, History
            from scripts.tests.recovery.fixtures import application
            facts,auth,controller,request,intent,World,Process,Objects,op=fixture(runtime,c)
            records=Objects(s3,c['evidence_bucket'],'delivery/');world=World(intent,records,facts.members['dev']['colors'])
            result=controller(auth,world,records,Gate(Process(world))).run(op,a.canonical(request))
            self.assertEqual(result['status'],'SUCCESS')
            with self.assertRaises(ValueError):Emergency(auth,records,None)
            normal=a.Authorizer('deploy-dev',c['account'],c['region'],facts)
            with self.assertRaises(d.JournalError):History(normal,records).success(op)
            from scripts.tests.normal_delivery.test_authorization import Fixture
            with patch.object(Fixture, 'eligibility_current', eligibility_fixture):
                cleanup,target,_,_=application('cleanup',running=1)
            target.configuration['history']['blue']=op
            # Cleanup consumes protected membership/topology, not stale task secrets/history.
            for service in target.state['services'].values():service['task']=copy.deepcopy(intent['task'])
            result=cleanup.run('66666666-2222-3333-4444-555555555555',b'{}\n')
            self.assertEqual(result['status'],'SUCCESS',result)
            self.assertEqual([stage for stage,_ in target.calls],['scale_zero','remove_target','delete_rule'])
            self.assertEqual(target.state['services']['green']['desired'],2)


if __name__ == '__main__': unittest.main()
