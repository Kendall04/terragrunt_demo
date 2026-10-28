"""Production-path recovery boundaries, with deterministic persistence attacks."""
import copy
import unittest
from scripts.normal_delivery import authorization as a
from scripts.tests.recovery.fixtures import application, nat, OP, NEXT


class EmergencyTests(unittest.TestCase):
    def test_zero_capacity(self):
        c, r, records, f = application()
        result = c.run(NEXT, b'{}')
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual([t['id'] for t in result['final']['recovered']['targets']], ['target-0', 'target-1'])
        self.assertEqual([x[0] for x in r.calls], ['scale', 'switch', 'candidate', 'schedule'])

    def test_running(self):
        c, r, records, f = application(running=2)
        result = c.run(NEXT, b'{}')
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual([t['id'] for t in result['final']['recovered']['targets']], ['target-0', 'target-1'])
        self.assertEqual([x[0] for x in r.calls], ['switch', 'candidate', 'schedule'])

    def test_prod(self):
        c, r, records, f = application(endpoint='promote-prod')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')

    def test_revoked(self):
        c, r, records, f = application()
        f.e['state'] = 'REVOKED'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_history_required(self):
        for alteration in ('missing', 'FAILURE', 'UNCERTAIN', 'foreign', 'revision'):
            with self.subTest(alteration=alteration):
                c, r, records, f = application()
                key = 'dev/' + OP + '/success'
                receipt = a.decode(records.data[key])
                if alteration == 'missing': del records.data[key]
                else:
                    if alteration == 'foreign': receipt['environment'] = 'prod'
                    elif alteration == 'revision': receipt['registration']['task_definition_arn'] += '9'
                    else: receipt['status'] = alteration
                    records.data[key] = a.canonical(receipt)
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
                self.assertEqual(r.calls, [])

    def test_other_selected_revision(self):
        c, r, records, f = application()
        r.state['services']['blue']['revision'] += '9'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_no_caller_authority(self):
        for field in ('revision', 'image', 'service', 'target', 'release_id', 'color', 'ready', 'history'):
            c, r, records, f = application()
            self.assertEqual(c.run(NEXT, a.canonical({field: 'arbitrary'}))['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_health(self):
        for field, value in (('stable', False), ('pending', 1), ('running', 0), ('targets', [])):
            c, r, records, f = application(running=2)
            r.state['services']['blue'][field] = value
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_foreign_health(self):
        for field in ('revision', 'service', 'target_group', 'operation', 'environment', 'state'):
            c, r, records, f = application(running=2)
            targets = r.observe(NEXT, 1030)['services']['blue']['targets']
            targets[0][field] = 'foreign'
            r.state['services']['blue']['targets'] = targets
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_blank_target_identity(self):
        for running in (0, 2):
            for target_id in ('', ' ', '\t', '\n'):
                with self.subTest(running=running, target_id=repr(target_id)):
                    c, r, records, f = application(running=running)
                    observe = r.observe
                    def malformed(operation, deadline):
                        snapshot = observe(operation, deadline)
                        targets = snapshot['services']['blue']['targets']
                        if targets: targets[0]['id'] = target_id
                        return snapshot
                    r.observe = malformed
                    result = c.run(NEXT, b'{}')
                    self.assertEqual(result['status'], 'FAILURE')
                    self.assertNotIn('switch', [stage for stage, _ in r.calls])
                    self.assertNotEqual(result['status'], 'SUCCESS')

    def test_target_identity_normalization_collision(self):
        for ids in (('target-0', ' target-0 '), ('target-0', 'target-0 '),
                    ('target-0', 'target-0')):
            with self.subTest(ids=ids):
                c, r, records, f = application(running=2)
                targets = r.observe(NEXT, 1030)['services']['blue']['targets']
                for target, target_id in zip(targets, ids): target['id'] = target_id
                r.state['services']['blue']['targets'] = targets
                result = c.run(NEXT, b'{}')
                self.assertEqual(result['status'], 'FAILURE')
                self.assertNotIn('switch', [stage for stage, _ in r.calls])

    def test_revoked_after_scale(self):
        c, r, records, f = application()
        r.hook = lambda stage: f.e.update(state='REVOKED')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual([x[0] for x in r.calls], ['scale'])

    def test_fresh_persistence_guards(self):
        for stage in ('scale', 'switch'):
            for attack in ('route', 'revoked'):
                c, r, records, f = application()
                create = records.create
                def attacked(key, raw):
                    create(key, raw)
                    if key.endswith('/' + stage + '/plan'):
                        if attack == 'route': r.state['normal_targets'] = [r.configuration['colors']['blue']['target_group']]
                        else: f.e.update(state='REVOKED')
                records.create = attacked
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
                self.assertNotIn(stage, [x[0] for x in r.calls])

    def test_ambiguous_retry(self):
        for stage in ('scale', 'switch'):
            c, r, records, f = application()
            r.hidden.add(stage)
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            before = copy.deepcopy(r.calls)
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            self.assertEqual(r.calls, before)
            r.hidden.clear()
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
            self.assertEqual([x[0] for x in r.calls].count(stage), 1)

    def test_corrupt_intent_classification(self):
        for stage in (None, 'scale', 'switch'):
            for damage in (b'{', b'{"corrupt":true}'):
                c, r, records, f = application()
                if stage:
                    r.hidden.add(stage)
                    self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
                else:
                    c.operation = NEXT
                    c.journal.accept(NEXT, {}, c.prepare)
                records.data['dev/recovery/emergency/' + NEXT + '/intent'] = damage
                before = copy.deepcopy(r.calls)
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN' if stage else 'FAILURE')
                self.assertEqual(r.calls, before)

    def test_damaged_effect_reconciles(self):
        c, r, records, f = application()
        r.hidden.add('scale')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        key = 'dev/recovery/emergency/' + NEXT + '/scale/observed'
        records.data[key] = b'{"corrupt":true}'
        r.hidden.clear()
        result = c.run(NEXT, b'{}')
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(records.data[key], b'{"corrupt":true}')
        self.assertEqual(result['effects']['scale']['state'], 'APPLIED')

    def test_absent_no_resend(self):
        c, r, records, f = application()
        r.hidden.add('scale')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        r.hidden.clear(); r.effects.clear()
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(len(r.calls), 1)


class CleanupTests(unittest.TestCase):
    def test_both_active(self):
        c, r, records, f = application('cleanup', running=2)
        r.state['normal_targets'].append(r.configuration['colors']['blue']['target_group'])
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_positive(self):
        c, r, records, f = application('cleanup', running=2)
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
        self.assertEqual(r.calls[0][1]['service'], r.configuration['colors']['blue']['service'])
        self.assertEqual(r.calls[1][1]['Ids'], ['scale-down'])
        self.assertEqual(r.state['services']['green']['desired'], 2)

    def test_already_zero(self):
        c, r, records, f = application('cleanup')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
        self.assertEqual([x[0] for x in r.calls], ['remove_target', 'delete_rule'])

    def test_ambiguous_topology(self):
        for field in ('normal_targets', 'candidate_targets'):
            for value in ([], ['foreign'], ['a', 'b']):
                c, r, records, f = application('cleanup', running=2)
                r.state[field] = value
                self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
                self.assertEqual(r.calls, [])

    def test_active_alive(self):
        for field in ('desired', 'running'):
            c, r, records, f = application('cleanup', running=2)
            r.state['services']['green'][field] = 0
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_foreign_resources(self):
        for field in ('listener', 'rule'):
            c, r, records, f = application('cleanup', running=2)
            r.state[field] = 'foreign'
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])
        c, r, records, f = application('cleanup', running=2)
        r.state['services']['blue']['service'] = 'foreign'
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_no_caller_service(self):
        c, r, records, f = application('cleanup', running=2)
        self.assertEqual(c.run(NEXT, b'{"service":"active"}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_stale_plan(self):
        c, r, records, f = application('cleanup', running=2)
        create = records.create
        def attack(key, raw):
            create(key, raw)
            if key.endswith('/scale_zero/plan'):
                r.state['normal_targets'], r.state['candidate_targets'] = r.state['candidate_targets'], r.state['normal_targets']
        records.create = attack
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_unknown(self):
        c, r, records, f = application('cleanup', running=2)
        r.hidden.add('scale_zero')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        self.assertEqual(len(r.calls), 1)


class NatTests(unittest.TestCase):
    def test_second_az_replacement(self):
        for action in ('assign_eip', 'change_rt', 'disable_sdc'):
            c, r, records = nat(action)
            for source in ('membership', 'observed'):
                m = r.nat_context[source]
                m.update(subnet='subnet-b', az='us-east-1b', asg='nat-b', instance='i-replacement-b',
                         eni='eni-replacement-b', eip='eipalloc-b', route_table='rtb-b')
                m['spec'].update(launch_template='lt-protected-b', tags=dict(Role='nat', Group='b', Az='us-east-1b'))
            r.nat_context['observed']['eni_instance'] = 'i-replacement-b'
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
            self.assertEqual(len(r.calls), 1)

    def test_route_create(self):
        c, r, records = nat('change_rt')
        r.nat_context['route_exists'] = False
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
        self.assertEqual(r.calls[0][1]['action'], 'create_route')

    def test_final_state_required(self):
        c, r, records = nat()
        r.hook = lambda stage: r.nat_context['observed'].update(association_eni='foreign')
        self.assertNotEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')

    def test_fresh_nat_membership(self):
        c, r, records = nat()
        create = records.create
        def attack(key, raw):
            create(key, raw)
            if key.endswith('/plan'): r.nat_context['observed']['instance'] = 'foreign'
        records.create = attack
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_exact_requests(self):
        for action in ('assign_eip', 'change_rt', 'disable_sdc'):
            c, r, records = nat(action)
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
            request = r.calls[0][1]
            m = r.nat_context['membership']
            if action == 'assign_eip': self.assertEqual(request, dict(AllocationId=m['eip'], NetworkInterfaceId=m['eni'], AllowReassociation=True))
            elif action == 'change_rt': self.assertEqual(request, dict(RouteTableId=m['route_table'], DestinationCidrBlock='0.0.0.0/0', NetworkInterfaceId=m['eni'], action='replace_route'))
            else: self.assertEqual(request, dict(InstanceId=m['instance'], SourceDestCheck=dict(Value=False)))

    def test_handlers(self):
        for action in ('assign_eip', 'change_rt', 'disable_sdc'):
            c, r, records = nat(action)
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
            self.assertEqual([x[0] for x in r.calls], [action])

    def test_foreign_membership(self):
        for field in ('environment', 'vpc', 'subnet', 'az', 'asg', 'instance', 'eni', 'eip', 'route_table', 'eni_instance', 'route_vpc', 'eip_environment'):
            c, r, records = nat()
            r.nat_context['observed'][field] = 'foreign'
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE', field)
            self.assertEqual(r.calls, [])

    def test_runtime_identity(self):
        for field in ('ami', 'launch_template', 'launch_template_version', 'user_data_sha256', 'instance_profile', 'role', 'security_groups', 'http_tokens'):
            c, r, records = nat()
            r.nat_context['observed']['spec'][field] = 'foreign'
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE', field)
            self.assertEqual(r.calls, [])

    def test_tag_only(self):
        c, r, records = nat()
        r.nat_context['membership'] = dict(prefix='nat-', tags=dict(Role='nat'))
        self.assertEqual(c.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(r.calls, [])

    def test_no_arbitrary_request(self):
        for action in ('assign_eip', 'change_rt', 'disable_sdc'):
            c, r, records = nat(action)
            self.assertEqual(c.run(NEXT, b'{"InstanceId":"foreign"}')['status'], 'FAILURE')
            self.assertEqual(r.calls, [])

    def test_retry(self):
        for action in ('assign_eip', 'change_rt', 'disable_sdc'):
            c, r, records = nat(action)
            r.hidden.add(action)
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'UNCERTAIN')
            self.assertEqual(len(r.calls), 1)
            r.hidden.clear()
            self.assertEqual(c.run(NEXT, b'{}')['status'], 'SUCCESS')
            self.assertEqual(len(r.calls), 1)
