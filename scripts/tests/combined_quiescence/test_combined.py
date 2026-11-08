"""Actual shared E2, WP5, E15-D and two protocols with deterministic faults."""
import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import environment_mutation as e
from scripts.lifecycle import contract as c, runtime, quiescence as combined, ecs_quiescence as ecs, handoff
from scripts.lifecycle.controller import Controller
from scripts.nat import quiescence as nat
from scripts.tests.nat_quiescence import test_quiescence as nf
from scripts.tests.nat import test_nat
import test_ecs_quiescence as ef
import test_handoff as hf
import test_dev_down as df
from test_lifecycle import ACCOUNT, REGION, Checked, Memory, Engine, DOC
import wp5
import wp5_iam
from inventory import verify

ROOT = Path(__file__).resolve().parents[3]


def prepared(stage='global', env='dev'):
    binding, protected, value, plan = df.fixture(stage, env)
    cluster = f'arn:aws:ecs:{REGION}:{ACCOUNT}:cluster/demo-{env}-platform-main-cluster'
    apps = protected['layers']['apps'];apps['variables']['cluster_arn'] = cluster
    # Keep the selected synthetic destroy plan valid when apps is the stage.
    for color in ('blue', 'green'):
        address = 'module.api_' + color + '.aws_ecs_service.this'
        apps['addresses'][address] = 'aws_ecs_service'
        apps['membership'][address] = cluster.replace(':cluster/', ':service/') + '/demo-' + env + '-app-api-' + color + '-svc'
    config = test_nat.AWS().config
    if stage == 'global':
        members = protected['layers']['global']['membership']
        for index, identity in enumerate(sorted({s[k] for s in config['nat_slots']
                                                for k in ('vpc', 'subnet', 'asg', 'eip', 'route_table')})):
            members['nat-' + str(index)] = identity
            protected['layers']['global']['addresses']['nat-' + str(index)] = 'aws_vpc'
    return binding, protected, value, plan


class Combined(unittest.TestCase):
    def build(self, stage='global', boundary=None):
        self.binding, self.p, self.v, self.plan = prepared(stage)
        self.s3 = hf.SDK();self.store = e.Store(self.s3, f'e1-wp4-dev-{ACCOUNT}-{REGION}', 'dev')
        self.store.initialize();self.owner = e.Authority(self.store, self.binding, self.v['operation_id'], self.v, layer=stage)
        self.owner.acquire();self.now = 1000
        selected = ecs.scope(self.v, self.p)
        self.aws = ef.ECS(selected);self.boundary = boundary or ef.Closure()
        self.eq = ecs.Quiescence(self.v, self.p, self.owner, ecs.ECS(self.aws, selected),
            ecs.Journal(handoff.Storage(self.s3, ACCOUNT), selected), self.boundary, lambda:self.now)
        self.records = runtime.Records(self.s3, selected['backend']['bucket'], 'operations/' + self.binding + '/')
        self.config = test_nat.AWS().config;self.observation = nf.Observations(self.config)
        self.nq = nat.Quiescence(self.owner, self.v, self.p, self.config, self.records,
                                 self.observation, now=lambda:self.now) if stage == 'global' else combined.InstalledNAT()
        self.guard = combined.Guard(self.v, self.p, self.owner, self.eq, self.records, self.nq, lambda:self.now)
        return self.guard

    def denied(self, phase='pre-dispatch'):
        with self.assertRaises(ValueError):self.guard.require(self.v['layer'], phase)
        self.assertEqual(self.store.read()[0], self.owner.value)
        self.assertEqual(self.owner.value['state'], 'ACTIVE')

    def reports(self):
        prefix = self.records.prefix + self.guard.key + '/observations/'
        return [json.loads(raw) for (bucket, key), (raw, _) in self.s3.values.items()
                if bucket == self.records.bucket and key.startswith(prefix)]

    def test_shared_exact_operation_and_owner(self):
        self.build();self.denied();report = self.reports()[-1]
        self.assertEqual(self.eq.owner, self.nq.owner);self.assertEqual(self.guard.owner, self.owner.value)
        self.assertEqual(self.eq.selected['operation_id'], self.nq.scope['operation_id'])
        self.assertEqual(report['scope']['request_sha256'], self.owner.request_sha256)
        self.assertFalse(report['execution_authorized']);self.assertFalse(report['aws_verified'])

    def test_stage_order_registered_and_no_later_stage_reuse(self):
        self.build('edge');self.denied()
        self.assertEqual(self.records.read(self.guard.key)['order'], ['edge','apps','platform','data','global'])
        with self.assertRaises(ValueError):self.guard.require('apps', 'pre-dispatch')
        self.assertEqual(self.records.read(self.guard.key)['stage_index'], 0)

    def test_ecs_quiet_nat_unsettled_blocks_network(self):
        self.build();self.observation.value['effects'] = [dict(token='dev/recovery/assign_eip/late',action='assign_eip',state='UNSETTLED')]
        self.denied();self.assertEqual(self.guard.receipt['state'], 'QUIET')
        self.assertEqual(self.records.read(self.nq.key)['state'], 'UNKNOWN')
        self.assertIn('NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_UNPROVED', self.reports()[-1]['blockers'])

    def test_nat_drained_ecs_unsettled_blocks(self):
        self.build();self.aws.drain_effect = False;self.denied()
        self.assertIsNone(self.guard.receipt)
        self.assertIn('ECS_CURRENT_CLOSURE_OR_QUIETNESS_UNPROVED', self.reports()[-1]['blockers'])
        self.assertEqual(self.records.read(self.nq.key)['state'], 'UNKNOWN')

    def test_both_local_fixtures_never_install_aws_authority(self):
        self.build();self.denied()
        self.assertEqual(self.reports()[-1]['state'], 'UNKNOWN')
        self.assertIn('WHOLE_DOWN_OWNER_AND_ORDERED_STAGE_HANDOFF_UNINSTALLED', self.reports()[-1]['blockers'])

    def test_original_owner_generation_required(self):
        self.build();head = copy.deepcopy(self.owner.value);head['generation'] += 1
        # Deliberately invalid in-memory head, never an administrative pathway.
        self.s3.replace_fixture(self.store.bucket, self.store.key, e.canonical(head))
        with self.assertRaises(e.CoordinationError):self.guard.require('global', 'pre-dispatch')
        self.assertEqual(self.aws.calls, [])

    def test_different_request_digest_rejected(self):
        self.build();bad = copy.deepcopy(self.v);bad['layer'] = 'edge'
        with self.assertRaises(ValueError):combined.Guard(bad, self.p, self.owner, self.eq, self.records, self.nq, lambda:1000)

    def test_different_nat_protocol_owner_rejected(self):
        self.build();self.nq.owner = dict(self.nq.owner, generation=99)
        with self.assertRaises(ValueError):combined.Guard(self.v, self.p, self.owner, self.eq, self.records, self.nq, lambda:1000)

    def test_ecs_evidence_refreshed_at_each_boundary(self):
        self.build('edge');self.denied();first = self.guard.receipt['sample'];self.denied()
        self.assertGreater(self.guard.receipt['sample'], first);self.assertEqual(len(self.aws.calls), 2)

    def test_stale_ecs_receipt_blocks_next_boundary(self):
        self.build('apps');self.denied();self.now += 31;self.denied('post-readback')
        self.assertIn('ECS_CURRENT_CLOSURE_OR_QUIETNESS_UNPROVED', self.reports()[-1]['blockers'])

    def test_stale_nat_diagnostic_cannot_authorize_network(self):
        self.build();self.denied();self.now += 31;self.denied()
        self.assertIn('NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_UNPROVED', self.reports()[-1]['blockers'])

    def test_new_pending_task_invalidates_prior_quietness(self):
        self.build('apps');self.denied();next(iter(self.aws.tasks.values())).update(lastStatus='PENDING', desiredStatus='RUNNING')
        self.denied('post-readback');self.assertIn('ECS_CURRENT_CLOSURE_OR_QUIETNESS_UNPROVED', self.reports()[-1]['blockers'])

    def test_controller_reactivation_invalidates_quietness(self):
        self.build('edge');self.denied();self.boundary.closed = False;self.denied('post-readback')
        self.assertIn('ECS_CURRENT_CLOSURE_OR_QUIETNESS_UNPROVED', self.reports()[-1]['blockers'])

    def test_previously_dispatched_ecs_effect_cannot_be_revoked(self):
        self.build('edge');self.boundary.pending = True;self.denied()
        self.assertEqual(self.aws.calls, []);self.assertIsNone(self.guard.receipt)

    def test_nat_event_after_request_retains_unknown(self):
        self.build();self.nq.request()
        self.observation.hook = lambda:self.observation.value['effects'].append(dict(
            token='dev/recovery/change_rt/late',action='change_rt',state='UNKNOWN'))
        self.denied();self.assertEqual(self.records.read(self.nq.key)['state'], 'UNKNOWN')
        self.assertIn('PRIOR_EFFECT_UNSETTLED', self.nq.inspect()['blockers'])

    def test_interrupted_owner_blocks_new_invocation(self):
        self.build();replacement = e.Authority(self.store, self.binding, self.v['operation_id'], self.v, layer='global')
        result = e.execute(replacement, lambda _:self.fail('replacement entered'), state_key='state')
        self.assertEqual(result['state'], 'UNKNOWN');self.assertEqual(self.store.read()[0], self.owner.value)

    def test_e4_uncertain_owner_blocks_conflicting_teardown(self):
        self.build();self.owner.finish(False, 'UNCERTAIN')
        contender = e.Authority(self.store, self.binding, df.NEXT, dict(self.v,operation_id=df.NEXT), layer='global')
        result = e.execute(contender, lambda _:self.fail('uncertain owner replaced'), state_key='state')
        self.assertEqual(result['state'], 'UNKNOWN');self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')

    def test_lost_ecs_response_never_redispatches_attempted_color(self):
        self.build('apps');self.aws.fail = 'ambiguous-after';self.denied();self.denied()
        services = [x['service'] for x in self.aws.calls]
        self.assertEqual(len(services), len(set(services)));self.assertLessEqual(len(services), 2)

    def test_repeated_guard_request_retains_unknown_and_no_redrain(self):
        self.build();self.denied();intent = self.records.read(self.guard.key);self.denied()
        self.assertEqual(intent, self.records.read(self.guard.key));self.assertEqual(len(self.aws.calls), 2)
        self.assertTrue(all(x['state'] == 'UNKNOWN' for x in self.reports()))

    def test_cluster_deletion_needs_explicit_handoff(self):
        self.build('platform');self.denied('post-readback')
        self.assertIn('ECS_CLUSTER_DELETION_EVIDENCE_HANDOFF_UNINSTALLED', self.reports()[-1]['blockers'])

    def test_data_and_global_need_cluster_handoff(self):
        for stage in ('data', 'global'):
            self.build(stage);self.denied()
            self.assertIn('ECS_CLUSTER_DELETION_EVIDENCE_HANDOFF_UNINSTALLED', self.reports()[-1]['blockers'])

    def test_prod_and_shared_isolation(self):
        self.build()
        for stage, env in (('global','prod'),('shared','dev'),('secrets','dev')):
            _,p,v,_ = prepared(stage, env)
            with self.assertRaises(ValueError):combined.Guard(v,p,self.owner,self.eq,self.records,self.nq,lambda:1000)

    def test_foreign_records_denied(self):
        self.build();records = runtime.Records(self.s3, 'foreign', self.records.prefix)
        with self.assertRaises(ValueError):combined.Guard(self.v,self.p,self.owner,self.eq,records,self.nq,lambda:1000)

    def test_combined_lost_journal_ack_uses_exact_readback(self):
        self.build();self.s3.write_fault = ('after', self.records.prefix + self.guard.key + '/intent.json')
        self.denied();self.assertEqual(self.records.read(self.guard.key)['state'], 'UNKNOWN')

    def test_combined_missing_journal_never_enters_adapter(self):
        self.build();self.s3.write_fault = ('before', self.records.prefix + self.guard.key + '/intent.json')
        self.denied();self.assertEqual(self.aws.calls, []);self.assertIsNone(self.records.read(self.guard.key))

    def test_exact_stage_and_phase_closed(self):
        self.build()
        for stage,phase in (('shared','pre-dispatch'),('global','caller-approved'),('edge','post-readback')):
            with self.assertRaises(ValueError):self.guard.require(stage,phase)
        self.assertEqual(self.aws.calls, [])

    def test_protected_source_default_denies_without_nat_instantiation(self):
        self.build();self.guard.nat = combined.InstalledNAT();self.denied()
        self.assertFalse(self.reports()[-1]['aws_verified'])
        self.assertEqual(self.records.read(self.guard.key)['state'], 'UNKNOWN')

    def test_no_guard_finishes_e2_after_local_quietness(self):
        self.build()
        self.denied();self.assertEqual(self.store.read()[0]['state'], 'ACTIVE')

    def installed_case(self):
        case = hf.Case();self.addCleanup(case.doCleanups)
        with patch('test_exact_destroy.fixture', side_effect=prepared):case.setup_handoff('global')
        selected = ecs.scope(case.v,case.p);case.engine.ecs = ef.ECS(selected)
        return case

    def test_actual_e15d_valid_approval_cannot_bypass_combined_guard(self):
        case = self.installed_case();case.load();case.denied(case.dispatch)
        guard = case.engine.down_quiescence
        self.assertIs(type(guard), combined.Guard);self.assertIs(type(guard.ecs), ecs.Quiescence)
        self.assertIs(type(guard.nat), combined.InstalledNAT)
        self.assertIsNone(case.journal.read('decision'));self.assertIsNone(case.journal.read('attempt'))
        self.assertEqual(case.head.read()[0]['state'], 'ACTIVE');self.assertEqual(case.engine.ecs.calls, [])

    def test_actual_runtime_controller_repetition_does_not_reapply(self):
        case = self.installed_case();case.engine.prepare = lambda *args:None
        records = runtime.Records(case.sdk, case.backend['bucket'], 'operations/' + case.binding + '/')
        controller = Controller(case.binding,case.p,Checked(),case.engine,records)
        with patch.object(runtime.subprocess,'run') as process:
            first = controller.run(case.v);second = controller.run(case.v)
        self.assertEqual(first, second);self.assertEqual(first['state'], 'UNKNOWN');process.assert_not_called()
        self.assertEqual(case.head.read()[0]['state'], 'ACTIVE')

    def test_partial_terraform_verify_cannot_report_success(self):
        case = self.installed_case();case.load()
        bad = dict(format_version='1.2',complete=True,errored=False,planned_values=dict(root_module=dict(resources=[dict(mode='managed')])))
        case.engine.call = lambda args:c.canonical(bad)
        with self.assertRaises(ValueError):case.engine.verify('a'*64,case.engine.layer,'teardown')
        self.assertEqual(case.head.read()[0]['state'], 'ACTIVE')

    def test_empty_state_still_requires_post_readback_guard(self):
        case = self.installed_case();case.load()
        empty = dict(format_version='1.2',complete=True,errored=False,planned_values=dict(root_module={}))
        case.engine.call = lambda args:c.canonical(empty)
        with self.assertRaises(ValueError):case.engine.verify('a'*64,case.engine.layer,'teardown')
        self.assertEqual(case.engine.down_quiescence.records.read(case.engine.down_quiescence.key)['state'], 'UNKNOWN')

    def test_dev_sql_confirmations_preserved(self):
        _,p,v,_ = prepared('data');record = df.install_consent(v,p)
        df.down.check_data_consent(v,p,1000)
        for field in ('destroy_ack','sql_loss_ack'):
            p['teardown_approvals']['dev-sql-loss/'+v['operation_id']] = dict(record, **{field:''})
            with self.assertRaises(ValueError):df.down.check_data_consent(v,p,1000)

    def test_package_inventory_and_acceptance_registration(self):
        self.assertEqual(verify(ROOT), [])
        for binding in wp5.BINDINGS:
            raw = wp5.artifact(ROOT,DOC,binding)
            self.assertEqual(c.digest(raw), DOC['wp5']['selected'][binding]['package_sha256'])
            files = json.loads(raw)['files']
            for name in ('scripts/lifecycle/quiescence.py','scripts/lifecycle/ecs_quiescence.py','scripts/nat/quiescence.py'):
                self.assertEqual(base64.b64decode(files[name]), (ROOT/name).read_bytes().replace(b'\r\n',b'\n'))
        gate = (ROOT/'scripts/tests/final_acceptance/gate.py').read_text()
        for suite in ('combined_quiescence','ecs_quiescence','nat_quiescence'):
            self.assertIn('scripts/tests/'+suite+'/run.py', gate)

    def test_no_iam_or_activation_expansion(self):
        for field in ('installations','runtime_approvals','environment_bindings','active_contracts'):
            self.assertEqual(DOC['wp5'][field], {})
        actions = json.dumps(wp5_iam.policy(ecs.BINDING,ACCOUNT,REGION,{},'a'*64,'version'))
        self.assertNotIn('ecs:DescribeTasks', actions)
        self.assertNotIn('lambda:PutFunctionConcurrency', actions)
        self.assertNotIn('events:DisableRule', actions)

    def test_no_alternate_terraform_execution_path(self):
        source = (ROOT/'scripts/lifecycle/quiescence.py').read_text()
        for token in ('subprocess.', 'boto3', 'authority.finish(', 'authority.acquire(', 'time.sleep('):
            self.assertNotIn(token, source)
        factory = combined.installed
        with self.assertRaises(ValueError):factory(SimpleNamespace(), {}, None, None, lambda:1000)

    def test_current_runtime_configuration_cannot_reuse_guard(self):
        case = self.installed_case();case.load();case.denied(case.dispatch)
        case.engine.request = dict(case.engine.request, layer='edge')
        with self.assertRaises(ValueError):case.engine.require_combined_quiescence('pre-dispatch')
        self.assertEqual(case.head.read()[0]['state'], 'ACTIVE')

    def test_corrupted_combined_package_bytes_rejected(self):
        from scripts.lifecycle import packages
        binding = 'environment-lifecycle/infra-high-risk-dev'
        raw = wp5.artifact(ROOT, DOC, binding);value = json.loads(raw)
        value['files']['scripts/lifecycle/quiescence.py'] = base64.b64encode(b'changed bootstrap').decode()
        corrupt = c.canonical(value);digest = c.digest(corrupt)
        s3 = hf.SDK();bucket = 'protected-fixture';key = 'bundles/sha256/'+digest+'.json'
        response = s3.seed_object(bucket,key,corrupt)
        reference = dict(bucket=bucket,key=key,sha256=digest,version_id=response['VersionId'],binding=binding,source_commit='b'*40)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            packages.verify(s3,reference,directory)

    def test_original_owner_lost_during_nat_observation_no_permission(self):
        self.build()
        def changed():
            head = copy.deepcopy(self.owner.value);head['generation'] += 1
            self.s3.replace_fixture(self.store.bucket,self.store.key,e.canonical(head))
        self.observation.hook = changed
        with self.assertRaises(e.CoordinationError):self.guard.require('global','pre-dispatch')
        self.assertEqual(self.records.read(self.nq.key)['state'],'UNKNOWN')
        self.assertTrue(all(x['state']=='UNKNOWN' for x in self.reports()))
