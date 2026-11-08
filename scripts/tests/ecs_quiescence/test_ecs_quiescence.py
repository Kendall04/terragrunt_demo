"""Actual SDK/journal/E2 behavior with controlled faults and barriers; no sleeps."""
import copy
import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from scripts.lifecycle import ecs_quiescence as q, contract as c, handoff as h, runtime
from scripts import environment_mutation as e
from test_dev_down import fixture, UUID, NEXT
from test_lifecycle import ACCOUNT, REGION
from test_handoff import SDK, Case as HandoffCase
from test_wp4d import permits
import wp5_iam

ROOT = Path(__file__).resolve().parents[3]


class ECS:
    def __init__(self, selected):
        self.cluster = selected['cluster'];self.calls = [];self.reads = []
        self.fail = None;self.drain_effect = True;self.hook = None;self.page = None
        self.services = {}
        self.tasks = {}
        for service in selected['services']:
            revision = f'arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/' + service.rsplit('/', 1)[1][:-4] + ':2'
            self.services[service] = dict(serviceArn=service, clusterArn=self.cluster,
                serviceName=service.rsplit('/', 1)[1], status='ACTIVE', launchType='FARGATE',
                schedulingStrategy='REPLICA', deploymentController={'type': 'ECS'},
                taskDefinition=revision, desiredCount=1, runningCount=1, pendingCount=0,
                deployments=[dict(id='ecs-svc/' + service[-9:], status='PRIMARY', rolloutState='COMPLETED',
                    taskDefinition=revision, desiredCount=1, runningCount=1, pendingCount=0)])
            arn = self.cluster.replace(':cluster/', ':task/') + '/' + service.split('-')[-2]
            self.tasks[arn] = dict(taskArn=arn, clusterArn=self.cluster,
                group='service:' + service.rsplit('/', 1)[1], lastStatus='RUNNING', desiredStatus='RUNNING')

    def describe_clusters(self, **kw):
        self.reads.append(('clusters', kw))
        if self.fail == 'read':raise OSError('readback unavailable')
        return dict(clusters=[dict(clusterArn=self.cluster, status='ACTIVE')], failures=[])

    def describe_services(self, **kw):
        self.reads.append(('services', kw))
        response = dict(services=copy.deepcopy(list(self.services.values())), failures=[])
        if self.hook:self.hook(response)
        return response

    def list_tasks(self, **kw):
        self.reads.append(('list', kw))
        assert kw['desiredStatus'] == 'RUNNING'
        if self.page is not None:return copy.deepcopy(self.page)
        return dict(taskArns=[arn for arn, task in self.tasks.items() if task['desiredStatus'] == 'RUNNING'])

    def describe_tasks(self, **kw):
        self.reads.append(('tasks', kw))
        tasks = [copy.deepcopy(self.tasks[arn]) for arn in kw['tasks'] if arn in self.tasks]
        return dict(tasks=tasks, failures=[])

    def update_service(self, **kw):
        self.calls.append(kw)
        if self.fail == 'ambiguous-before':raise TimeoutError('unknown API result')
        if self.drain_effect:
            self.zero(kw['service'])
        if self.fail == 'ambiguous-after':raise TimeoutError('lost acknowledgement')
        return {}  # ACK itself proves nothing.

    def zero(self, service):
        svc = self.services[service]
        for key in ('desiredCount', 'runningCount', 'pendingCount'):
            svc[key] = 0
            for deployment in svc['deployments']:deployment[key] = 0
        for task in self.tasks.values():
            if task['group'] == 'service:' + svc['serviceName']:
                task.update(lastStatus='STOPPED', desiredStatus='STOPPED')


class Closure(q.ProtectedBoundary):
    """Synthetic internal domain port. Does NOT prove installation or AWS closure."""
    def __init__(self):self.closed = True;self.pending = False;self.sources = q.SOURCES.copy();self.hook = None
    def require(self, selected, owner, attempts):
        if self.hook:self.hook()
        if not self.closed or self.pending:raise ValueError('controller or dispatched effect unsettled')
        return dict(scope_sha256=selected['scope_sha256'], owner=copy.deepcopy(owner), sources=self.sources.copy())


class Protocol(unittest.TestCase):
    def setUp(self):
        _, self.protected, self.value, _ = fixture('apps')
        cluster = f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-dev-platform-main-cluster'
        apps = self.protected['layers']['apps'];apps['variables']['cluster_arn'] = cluster
        apps['addresses'] = {};apps['membership'] = {}
        for color in ('blue', 'green'):
            address = 'module.api_' + color + '.aws_ecs_service.this'
            apps['addresses'][address] = 'aws_ecs_service'
            apps['membership'][address] = cluster.replace(':cluster/', ':service/') + '/demo-dev-app-api-' + color + '-svc'
        self.selected = q.scope(self.value, self.protected)
        self.s3 = SDK()
        self.store = e.Store(self.s3, f'e1-wp4-dev-{ACCOUNT}-{REGION}', 'dev');self.store.initialize()
        self.owner = e.Authority(self.store, q.BINDING, UUID, self.value, layer='apps');self.owner.acquire()
        self.aws = ECS(self.selected);self.boundary = Closure();self.now = 1000
        self.journal = q.Journal(h.Storage(self.s3, ACCOUNT), self.selected)
        self.protocol = self.make()

    def make(self, boundary=None):
        return q.Quiescence(self.value, self.protected, self.owner, q.ECS(self.aws, self.selected),
                            self.journal, boundary or self.boundary, lambda: self.now)

    def changed(self, key, value):
        record = self.journal.read(key);record.update(value)
        self.s3.replace_fixture(self.journal.bucket, self.journal.key(key), c.canonical(record))

    def assert_held(self):
        self.assertEqual(self.store.read()[0], self.owner.value)
        self.assertEqual(self.owner.value['state'], 'ACTIVE')

    def test_exact_dev_identity_members_and_operation(self):
        receipt = self.protocol.begin()
        self.assertEqual(receipt['state'], 'QUIET');self.assertFalse(receipt['execution_authorized'])
        intent = self.journal.read('intent')
        self.assertEqual(intent['scope'], self.selected);self.assertEqual(intent['owner'], self.owner.value)
        self.assertEqual([x['service'] for x in self.aws.calls], self.selected['services'])
        self.assertTrue(all(set(x) == {'cluster', 'service', 'desiredCount'} and x['desiredCount'] == 0 for x in self.aws.calls))
        self.assert_held()

    def test_prod_shared_secrets_and_other_application_reject(self):
        for env, layer in (('prod', 'apps'), ('dev', 'shared'), ('dev', 'secrets')):
            _, protected, value, _ = fixture(layer, env)
            with self.assertRaises(ValueError):q.scope(value, protected)
        self.protected['layers']['apps']['root'] = 'terraform/modules/target/other/apps'
        with self.assertRaises(ValueError):q.scope(self.value, self.protected)

    def test_foreign_cluster_service_extra_or_missing_members_reject(self):
        for fault in ('cluster', 'foreign', 'extra', 'missing'):
            protected = copy.deepcopy(self.protected);apps = protected['layers']['apps']
            if fault == 'cluster':apps['variables']['cluster_arn'] = self.selected['cluster'].replace('dev', 'prod')
            elif fault == 'foreign':apps['membership'][next(iter(apps['membership']))] = 'prod'
            elif fault == 'extra':apps['addresses']['extra'] = 'aws_ecs_service';apps['membership']['extra'] = self.selected['services'][0]
            else:apps['addresses'].pop(next(iter(apps['addresses'])))
            with self.assertRaises(ValueError):q.scope(self.value, protected)

    def test_unapproved_lifecycle_request_rejects(self):
        self.protected['operation_approvals'] = {}
        with self.assertRaises(ValueError):self.make()

    def test_individual_task_stop_cannot_quiesce_positive_service(self):
        for task in self.aws.tasks.values():task.update(desiredStatus='STOPPED', lastStatus='STOPPED')
        with self.assertRaises(ValueError):q.quiet(q.ECS(self.aws, self.selected).observe())

    def test_drain_requested_but_no_effect_stays_unknown(self):
        self.aws.drain_effect = False
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN')
        self.assertEqual(len(self.aws.calls), 2);self.assert_held()

    def test_running_after_desired_zero_fails(self):
        def hook(response):response['services'][0]['runningCount'] = 1
        self.aws.hook = hook
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assert_held()

    def test_pending_and_stopping_tasks_fail_until_actually_stopped(self):
        self.aws.drain_effect = False
        self.protocol.run()
        for state in ('PENDING', 'PROVISIONING', 'STOPPING', 'DEPROVISIONING', 'RUNNING'):
            for service in self.selected['services']:self.aws.zero(service)
            task = next(iter(self.aws.tasks.values()));task.update(lastStatus=state, desiredStatus='STOPPED')
            with self.assertRaises(ValueError):self.protocol.check()
        for service in self.selected['services']:self.aws.zero(service)
        self.assertEqual(self.protocol.check()['state'], 'QUIET')

    def test_pending_desired_running_is_listed_and_blocks(self):
        self.protocol.begin();task = next(iter(self.aws.tasks.values()))
        task.update(lastStatus='PENDING', desiredStatus='RUNNING')
        with self.assertRaises(ValueError):self.protocol.check()
        self.assertTrue(all(args['desiredStatus'] == 'RUNNING' for method, args in self.aws.reads if method == 'list'))

    def test_service_replacement_capacity_and_old_deployments_block(self):
        self.protocol.begin()
        service = next(iter(self.aws.services.values()))
        deployment = copy.deepcopy(service['deployments'][0]);deployment['id'] += '-old'
        service['deployments'].append(deployment)
        with self.assertRaises(ValueError):self.protocol.check()

    def test_external_codedeploy_daemon_or_non_fargate_controller_rejects_before_drain(self):
        for field, value in (('deploymentController', {'type': 'CODE_DEPLOY'}),
                             ('deploymentController', {'type': 'EXTERNAL'}),
                             ('schedulingStrategy', 'DAEMON'), ('launchType', 'EC2'), ('taskSets', [{}])):
            saved = copy.deepcopy(self.aws.services)
            next(iter(self.aws.services.values()))[field] = value
            self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(self.aws.calls, [])
            self.aws.services = saved

    def test_deployment_just_before_quiescence_not_assumed_cancelled(self):
        service = next(iter(self.aws.services.values()));service['deployments'][0]['rolloutState'] = 'IN_PROGRESS'
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN')
        service['deployments'][0]['rolloutState'] = 'COMPLETED'
        self.assertEqual(self.protocol.check()['state'], 'QUIET');self.assertEqual(len(self.aws.calls), 2)

    def test_new_normal_emergency_cleanup_and_infra_operations_cannot_bypass_hold(self):
        self.protocol.begin()
        for binding in ('normal-delivery/deploy-dev', 'emergency-recovery/emergency-dev',
                        'cleanup-recovery/cleanup-dev', 'environment-lifecycle/infra-dev'):
            peer = e.Authority(self.store, binding, NEXT, {}, layer='global' if binding.startswith('environment') else None)
            result = e.execute(peer, lambda owner: self.fail('competing operation dispatched'))
            self.assertEqual(result['status'], 'UNCERTAIN')
        self.assert_held()

    def test_native_scaling_or_start_scheduler_invalidation_fails_closed(self):
        receipt = self.protocol.begin()
        for source in ('NO_NATIVE_SCALING_OR_START_SCHEDULERS', 'CLEANUP_E2_FENCED', 'E2_AUTHORIZED_WRITERS'):
            self.boundary.sources = [s for s in q.SOURCES if s != source]
            with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'apps')
        self.assert_held()

    def test_verified_terminal_tasks_include_initial_exact_cohort(self):
        self.protocol.begin();sample = self.journal.read('sample-0')
        self.assertEqual(set(sample['observation']['tasks']), set(self.journal.read('intent')['baseline']['tasks']))
        self.assertTrue(all(t['lastStatus'] == t['desiredStatus'] == 'STOPPED' for t in sample['observation']['tasks'].values()))

    def test_missing_previously_seen_task_is_not_terminal_proof(self):
        self.protocol.begin();self.aws.tasks.pop(next(iter(self.aws.tasks)))
        with self.assertRaises(ValueError):self.protocol.check()

    def test_new_task_restart_is_retained_and_must_later_stop(self):
        receipt = self.protocol.begin()
        task = copy.deepcopy(next(iter(self.aws.tasks.values())));task.update(taskArn=task['taskArn'] + '-restart',
                                                                            lastStatus='RUNNING', desiredStatus='RUNNING')
        self.aws.tasks[task['taskArn']] = task
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'data')
        task.update(lastStatus='STOPPED', desiredStatus='STOPPED')
        self.assertEqual(self.protocol.check()['state'], 'QUIET')
        self.assertIn(task['taskArn'], self.journal.read('sample-2')['observation']['tasks'])

    def test_receipt_freshness_expiry_and_clock_regression(self):
        receipt = self.protocol.begin()
        for now in (999, 1030, 1300):
            self.now = now
            with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'global')
        self.assert_held()

    def test_stale_incomplete_or_too_slow_readback_rejects(self):
        self.protocol.begin()
        self.aws.hook = lambda response: response['services'].pop()
        with self.assertRaises(ValueError):self.protocol.check()
        self.aws.hook = lambda response: setattr(self, 'now', self.now + q.FRESH_SECONDS)
        with self.assertRaises(ValueError):self.protocol.check()

    def test_missing_corrupt_and_forged_evidence_rejects(self):
        with self.assertRaises(ValueError):self.protocol.require_quiet({}, 'apps')
        receipt = self.protocol.begin()
        for value in ({'schema': 'wrong'}, {'owner': dict(self.owner.value, generation=99)},
                      {'observation': dict(services={}, tasks={}, live=[])}):
            prior = self.journal.read('sample-0');self.changed('sample-0', value)
            with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'apps')
            self.s3.replace_fixture(self.journal.bucket, self.journal.key('sample-0'), c.canonical(prior))
        self.s3.replace_fixture(self.journal.bucket, self.journal.key('sample-0'), b'not-json')
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'apps')

    def test_generation_or_owner_mismatch_rejects(self):
        receipt = self.protocol.begin()
        head, etag = self.store.read();self.store.exchange(dict(head, generation=head['generation'] + 1), etag)
        with self.assertRaises(e.CoordinationError):self.protocol.require_quiet(receipt, 'apps')

    def test_interrupted_owner_cannot_be_replaced_or_released(self):
        self.aws.fail = 'ambiguous-after';self.assertEqual(self.protocol.run()['state'], 'UNKNOWN')
        self.owner.finish(status='UNKNOWN');self.assert_held()
        peer = e.Authority(self.store, q.BINDING, UUID, self.value, layer='apps')
        with self.assertRaises(e.CoordinationError):peer.acquire()

    def test_e4_uncertain_owner_blocks_admission_without_new_generation(self):
        other_s3 = SDK();store = e.Store(other_s3, f'e1-wp4-dev-{ACCOUNT}-{REGION}', 'dev');store.initialize()
        delivery = e.Authority(store, 'normal-delivery/deploy-dev', NEXT, {});delivery.acquire()
        delivery.call(lambda: None);delivery.finish(status='UNCERTAIN')
        peer = e.Authority(store, q.BINDING, UUID, self.value, layer='apps')
        result = e.execute(peer, lambda owner: self.fail('quiescence admitted'), state_key='state')
        self.assertEqual(result['state'], 'UNKNOWN');self.assertEqual(store.read()[0]['generation'], 1)

    def test_late_old_mutation_blocked_until_settled_and_read_again(self):
        receipt = self.protocol.begin();self.boundary.pending = True
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'platform')
        next(iter(self.aws.services.values()))['desiredCount'] = 1
        self.boundary.pending = False
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'platform')
        self.assert_held()

    def test_readback_failure_after_send_preserves_intent_attempt_and_owner(self):
        original = self.aws.update_service
        def send(**kw):original(**kw);self.aws.fail = 'read'
        self.aws.update_service = send
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN')
        self.assertIsNotNone(self.journal.read('blue-attempt'));self.assertIsNotNone(self.journal.read('intent'))
        self.assert_held()

    def test_ambiguous_api_result_no_blind_resubmission(self):
        for fault in ('ambiguous-before', 'ambiguous-after'):
            with self.subTest(fault=fault):
                self.setUp();self.aws.fail = fault
                self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(len(self.aws.calls), 1)
                self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(len(self.aws.calls), 2)
                if fault == 'ambiguous-after':
                    # Only the synthetic settlement port authorizes reobservation;
                    # no second send for either ambiguous service is made.
                    self.assertEqual(self.protocol.run()['state'], 'QUIET')
                    self.assertEqual(len(self.aws.calls), 2);self.assert_held()
                    continue
                self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(len(self.aws.calls), 2)
                self.assert_held()

    def test_crash_after_attempt_before_send_burns_service_send(self):
        key = self.journal.key('blue-attempt')
        self.s3.write_fault = ('after', key)
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(self.aws.calls, [])
        self.s3.write_fault = None
        self.assertEqual(self.make().run()['state'], 'UNKNOWN')
        self.assertEqual([x['service'] for x in self.aws.calls], [self.selected['services'][1]])
        self.assert_held()

    def test_crash_between_drain_and_readback_reobserves_without_resend(self):
        original = self.aws.update_service
        def crash(**kw):
            original(**kw)
            if kw['service'] == self.selected['services'][1]:raise KeyboardInterrupt('executor interrupted')
        self.aws.update_service = crash
        with self.assertRaises(KeyboardInterrupt):self.protocol.begin()
        self.assertIsNone(self.journal.read('sample-0'));self.assert_held()
        self.aws.update_service = original;calls = copy.deepcopy(self.aws.calls)
        self.assertEqual(self.make().begin()['state'], 'QUIET');self.assertEqual(self.aws.calls, calls)

    def test_duplicate_same_operation_is_not_another_drain(self):
        self.protocol.begin();self.protocol.begin()
        self.assertEqual(len(self.aws.calls), 2);self.assert_held()

    def test_two_simultaneous_attempts_only_one_drain_per_service(self):
        barrier = threading.Barrier(2);original = self.journal.read
        def read(stage):
            result = original(stage)
            if stage == 'intent' and result is None:barrier.wait(timeout=5)
            return result
        with patch.object(self.journal, 'read', read), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.make().run(), range(2)))
        self.assertEqual(sorted(r['state'] for r in results), ['QUIET', 'UNKNOWN'])
        self.assertEqual(len(self.aws.calls), 2);self.assert_held()

    def test_teardown_cannot_begin_without_quietness_or_with_wrong_stage(self):
        with self.assertRaises(ValueError):self.protocol.require_quiet({}, 'apps')
        receipt = self.protocol.begin()
        for stage in ('shared', 'secrets', 'security', 'prod', 'terraform apply'):
            with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, stage)

    def test_quietness_invalidated_before_stage_completion_is_not_success(self):
        receipt = self.protocol.begin();self.protocol.require_quiet(receipt, 'apps')
        next(iter(self.aws.services.values()))['desiredCount'] = 1
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'apps')
        self.assert_held()

    def test_evidence_window_or_readback_limit_never_releases_hold(self):
        self.protocol.begin()
        for _ in range(q.MAX_SAMPLES - 1):self.protocol.check()
        with self.assertRaises(ValueError):self.protocol.check()
        self.assert_held()

    def test_missing_or_repeating_pagination_fails_closed(self):
        for page in ({}, {'taskArns': [], 'nextToken': 'again'}):
            self.aws.page = page
            self.assertEqual(self.protocol.run()['state'], 'UNKNOWN')
        self.assertEqual(self.aws.calls, [])

    def test_standalone_foreign_or_missing_task_description_rejects(self):
        task = next(iter(self.aws.tasks.values()))
        for key, value in (('group', 'standalone'), ('clusterArn', 'prod'), ('taskArn', 'foreign')):
            old = task[key];task[key] = value
            self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');task[key] = old
        self.assertEqual(self.aws.calls, [])

    def test_exact_missing_service_with_stopped_cohort_is_supported(self):
        self.protocol.begin();services = self.selected['services']
        self.aws.describe_services = lambda **kw: dict(services=[], failures=[dict(arn=s, reason='MISSING') for s in services])
        self.assertEqual(self.protocol.check()['state'], 'QUIET')

    def test_absent_cluster_does_not_fabricate_terminal_task_proof(self):
        self.protocol.begin()
        self.aws.describe_clusters = lambda **kw: dict(clusters=[], failures=[dict(arn=self.selected['cluster'], reason='MISSING')])
        with self.assertRaises(ValueError):self.protocol.check()

    def test_default_uninstalled_boundary_never_drains_or_accepts_flags(self):
        for flag in (True, {'installed': True, 'ready': True}):
            with self.assertRaises(ValueError):self.make(flag)
        result = self.make(q.ProtectedBoundary()).run()
        self.assertEqual(result['state'], 'BLOCKED');self.assertEqual(self.aws.calls, [])

    def test_missing_permissions_are_a_readback_failure_not_optimistic_success(self):
        self.aws.fail = 'read'
        result = self.protocol.run();self.assertEqual(result['state'], 'UNKNOWN')
        self.assertFalse(result['execution_authorized']);self.assertEqual(self.aws.calls, [])

    def test_no_iam_expansion_and_exact_existing_stopping_authority(self):
        resources = {kind: [] for kind in wp5_iam.INVENTORY};resources['aws_ecs_service'] = self.selected['services']
        policy = wp5_iam.policy(q.BINDING, ACCOUNT, REGION, resources, 'a' * 64, 'fixture-version')
        for service in self.selected['services']:
            self.assertTrue(permits(policy, 'ecs:UpdateService', service))
            self.assertFalse(permits(policy, 'ecs:UpdateService', service.replace('dev', 'prod')))
        for action in ('ecs:StopTask', 'ecs:RunTask', 'ecs:StartTask', 'ecs:DescribeTasks', 'iam:PutRolePolicy'):
            self.assertFalse(permits(policy, action, self.selected['cluster'].replace(':cluster/', ':task/') + '/blue'))

    def test_no_apply_or_owner_release_interface_and_no_down_success(self):
        receipt = self.protocol.begin()
        self.assertEqual(receipt['down_state'], 'UNKNOWN');self.assertFalse(hasattr(self.protocol, 'apply'))
        self.assertFalse(hasattr(self.protocol, 'finish'));self.assert_held()
        with patch.object(runtime.subprocess, 'run') as process:
            channel = object.__new__(h.Handoff)
            channel.scope = lambda *args: self.selected;channel.session = lambda *args: None
            with self.assertRaises(ValueError):channel.require_down_quiescence(self.value, self.protected, self.owner)
            process.assert_not_called()

    def test_adapter_requires_original_owner_and_concrete_closure_at_dispatch(self):
        adapter = q.ECS(self.aws, self.selected)
        with self.assertRaises(ValueError):adapter.drain(self.selected['services'][0], None,
            self.boundary, [], 1100, lambda: 1000)
        with self.assertRaises(q.Blocked):adapter.drain(self.selected['services'][0], self.owner,
            q.ProtectedBoundary(), [], 1100, lambda: 1000)
        self.assertEqual(self.aws.calls, []);self.assert_held()

    def test_real_sdk_datetime_deployment_metadata_is_normalized_before_journaling(self):
        for service in self.aws.services.values():
            service['deployments'][0].update(createdAt=datetime.datetime(2026, 10, 12),
                                             updatedAt=datetime.datetime(2026, 10, 12))
        self.assertEqual(self.protocol.begin()['state'], 'QUIET')
        deployment = next(iter(self.journal.read('intent')['baseline']['services'].values()))['deployments'][0]
        self.assertEqual(set(deployment), set(q.DEPLOYMENT_FIELDS))

    def test_incomplete_deployment_or_cross_color_revision_blocks_before_drain(self):
        for fault in ('missing', 'bool-count', 'foreign-family', 'unknown-state'):
            saved = copy.deepcopy(self.aws.services);service = next(iter(self.aws.services.values()))
            if fault == 'missing':service['deployments'][0].pop('rolloutState')
            elif fault == 'bool-count':service['deployments'][0]['desiredCount'] = True
            elif fault == 'foreign-family':service['taskDefinition'] = service['taskDefinition'].replace('dev', 'prod')
            else:service['deployments'][0]['rolloutState'] = 'UNKNOWN'
            self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assertEqual(self.aws.calls, [])
            self.aws.services = saved

    def test_publication_delay_or_owner_invalidation_cannot_return_quiet(self):
        def publication(args):
            if args['Key'].endswith('sample-0.json'):self.now += q.FRESH_SECONDS
        self.s3.before = publication
        self.assertEqual(self.protocol.run()['state'], 'UNKNOWN');self.assert_held()

    def test_native_capacity_change_between_stage_gates_invalidates_quietness(self):
        receipt = self.protocol.begin();entered = threading.Event();resume = threading.Event()
        def late_effect():
            entered.set();self.assertTrue(resume.wait(timeout=5))
            next(iter(self.aws.services.values()))['desiredCount'] = 1
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(late_effect)
            self.assertTrue(entered.wait(timeout=5))
            self.protocol.require_quiet(receipt, 'edge')
            resume.set();future.result(timeout=5)
        with self.assertRaises(ValueError):self.protocol.require_quiet(receipt, 'edge')
        self.assert_held()

    def test_late_checked_delivery_call_not_cancelled_by_head_generation(self):
        sdk = SDK();store = e.Store(sdk, f'e1-wp4-dev-{ACCOUNT}-{REGION}', 'dev');store.initialize()
        old = e.Authority(store, 'normal-delivery/deploy-dev', NEXT, {});old.acquire()
        entered = threading.Event();resume = threading.Event();effects = []
        def issued():
            entered.set();self.assertTrue(resume.wait(timeout=5));effects.append('old ECS effect completed')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(old.call, issued);self.assertTrue(entered.wait(timeout=5))
            head, etag = store.read()
            # Deliberately unsafe fixture head change, never a recovery API.
            store.exchange(dict(head, generation=head['generation'] + 1), etag)
            resume.set();future.result(timeout=5)
        self.assertEqual(effects, ['old ECS effect completed'])
        with self.assertRaises(e.CoordinationError):old._check()


class ConcreteBoundary(HandoffCase):
    def test_synthetic_e15d_installation_does_not_install_ecs_closure(self):
        self.setup_handoff(publish=False, approve=False)
        apps = self.p['layers']['apps'];cluster = f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-dev-platform-main-cluster'
        apps['variables']['cluster_arn'] = cluster;apps['addresses'] = {};apps['membership'] = {}
        for color in ('blue', 'green'):
            apps['addresses'][color] = 'aws_ecs_service'
            apps['membership'][color] = cluster.replace(':cluster/', ':service/') + '/demo-dev-app-api-' + color + '-svc'
        channel = h.Handoff(self.sdk, self.executor_sts, self.p, self.v, self.engine)
        selected = q.scope(self.v, self.p)
        boundary = q.HandoffBoundary(channel)
        with self.assertRaises(q.Blocked):boundary.require(selected, {}, [])
        self.assertGreater(self.executor_sts.calls, 0)

    def test_fake_channel_cannot_install_quiescence(self):
        with self.assertRaises(ValueError):q.HandoffBoundary({'authenticated': True})
