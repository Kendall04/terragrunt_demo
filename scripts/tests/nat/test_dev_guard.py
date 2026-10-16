"""Deterministic production-package reproduction of the DEV SDC/EIP guard race."""
import base64
import copy
import json
from pathlib import Path
import unittest

import wp4d
from scripts.tests.recovery.fixtures import nat, NEXT

ROOT = Path(__file__).resolve().parents[3]
DOC = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
FIELDS = {'assign_eip': 'association_eni', 'change_rt': 'default_route_eni',
          'disable_sdc': 'source_dest_check'}


def installed(action):
    binding = 'nat-recovery/nat-dev/' + action
    package = json.loads(wp4d.artifact(ROOT, DOC['control_bundles'], binding))
    namespace = {}
    exec(compile(base64.b64decode(package['files']['scripts/recovery/nat.py']),
                 'installed-dev-nat.py', 'exec'), namespace)
    old, runtime, records = nat(action)
    return namespace['Nat']('dev', action, records, runtime), runtime, records


def on_persistence(records, suffix, change):
    create = records.create
    def persist(key, raw):
        create(key, raw)
        if key.endswith(suffix):
            change()
    records.create = persist


class DevGuard(unittest.TestCase):
    def test_actual_old_guard_rejects_other_duty_after_attempt(self):
        controller, runtime, records = nat('disable_sdc')
        on_persistence(records, '/attempt', lambda:
            runtime.nat_context['observed'].update(association_eni='eni-member'))
        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'FAILURE')
        self.assertEqual(runtime.calls, [])
        self.assertTrue(any(k.endswith('/attempt') for k in records.data))
        self.assertFalse(any(k.endswith('/ack') for k in records.data))

    def test_emitted_dev_packages_allow_independent_duty_progress(self):
        for action, own_field in FIELDS.items():
            for other_field in set(FIELDS.values()) - {own_field}:
                for boundary in ('/plan', '/attempt'):
                    with self.subTest(action=action, other=other_field, boundary=boundary):
                        controller, runtime, records = installed(action)
                        value = False if other_field == 'source_dest_check' else 'eni-member'
                        on_persistence(records, boundary, lambda field=other_field, v=value:
                            runtime.nat_context['observed'].update({field: v}))
                        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'SUCCESS')
                        self.assertEqual([s for s, _ in runtime.calls], [action])

    def test_owned_state_route_existence_and_membership_still_reject(self):
        for action, field in FIELDS.items():
            for attack in ('owned_state', 'membership', 'route_existence'):
                if attack == 'route_existence' and action != 'change_rt':
                    continue
                for boundary in ('/plan', '/attempt'):
                    with self.subTest(action=action, attack=attack, boundary=boundary):
                        controller, runtime, records = installed(action)
                        def change():
                            if attack == 'owned_state':
                                runtime.nat_context['observed'][field] = (
                                    False if field == 'source_dest_check' else 'eni-foreign')
                            elif attack == 'route_existence':
                                runtime.nat_context['route_exists'] = False
                            else:
                                runtime.nat_context['membership']['instance'] = 'i-foreign'
                                runtime.nat_context['observed'].update(
                                    instance='i-foreign', eni_instance='i-foreign')
                        on_persistence(records, boundary, change)
                        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'FAILURE')
                        self.assertEqual(runtime.calls, [])

    def test_unknown_effect_retry_does_not_dispatch_again_or_rewrite_failure(self):
        controller, runtime, records = installed('disable_sdc')
        runtime.hidden.add('disable_sdc')
        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        retained = copy.deepcopy(records.data)
        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'UNCERTAIN')
        self.assertEqual(len(runtime.calls), 1)
        for key, raw in retained.items():
            self.assertEqual(records.data[key], raw)
        runtime.hidden.clear()
        self.assertEqual(controller.run(NEXT, b'{}')['status'], 'SUCCESS')
        self.assertEqual(len(runtime.calls), 1)

    def test_guard_is_selected_only_in_dev_nat_packages(self):
        for binding in wp4d.RESERVED:
            package = json.loads(wp4d.artifact(ROOT, DOC['control_bundles'], binding))
            files = package['files']
            selected = binding.startswith('nat-recovery/nat-dev/')
            self.assertEqual('scripts/wp4d/dev_nat_guard.py' in files, selected)
            source = base64.b64decode(files['scripts/recovery/nat.py'])
            self.assertEqual(b'Nat = _dev_nat_guard(Nat)' in source, selected)
            if not selected:
                self.assertEqual(source, (ROOT / 'scripts/recovery/nat.py').read_bytes().replace(b'\r\n', b'\n'))
