"""Synthetic plan JSON only: never Terraform, AWS, state or a deployment proof."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_native_plan as check

ACCOUNT = '111122223333'
REGION = 'us-east-1'


def row(address='module.vpc.aws_vpc.this', kind='aws_vpc', action='create'):
    attrs = dict(id='OFFLINE', tags={'Project': 'demo', 'Environment': 'dev'})
    return dict(address=address, type=kind, mode='managed', change=dict(actions=[action],
                before=attrs if action != 'create' else None, after=attrs if action != 'delete' else None))


def plan(*rows):
    return dict(format_version='1.2', terraform_version='1.13.4', errored=False,
                applyable=True, complete=True, resource_changes=list(rows or [row()]))


class ReviewTests(unittest.TestCase):
    def review(self, value, **kw):
        args = dict(layer='global', direction='up', account=ACCOUNT, region=REGION)
        args.update(kw)
        return check.review(value, **args)

    def test_network_create_still_requires_human_review(self):
        result = self.review(plan(), network_only=True)
        self.assertEqual(result['status'], 'REVIEW_REQUIRED_NOT_AUTHORIZED')
        self.assertFalse(result['aws_verified'])

    def test_partial_network_destroy_does_not_require_other_layers(self):
        value = plan(row(action='delete'))
        self.assertEqual(self.review(value, direction='down')['resources'], {'aws_vpc:delete': 1})

    def test_all_five_roots_have_native_locked_backends(self):
        for layer in check.LAYERS:
            source = json.loads((check.ROOT/'terraform/modules/target/dev'/layer/'main.tf.json').read_text())
            self.assertEqual(source['terraform']['backend']['s3'], dict(encrypt=True, use_lockfile=True))
            self.assertTrue(check.declarations(layer))
            self.assertIn('5.100.0', (check.ROOT/'terraform/modules/target/dev'/layer/'.terraform.lock.hcl').read_text())
        self.assertFalse((check.ROOT/'terraform/live/dev/global/terragrunt.hcl').exists())

    def test_foreign_address_and_wrong_layer_rejected(self):
        for value, layer in ((plan(row('aws_vpc.eks')), 'global'), (plan(), 'data')):
            with self.assertRaisesRegex(ValueError, 'foreign'):
                self.review(value, layer=layer)

    def test_foreign_project_environment_and_account_rejected(self):
        for key, value in (('Project', 'eks'), ('Environment', 'prod')):
            v = plan();v['resource_changes'][0]['change']['after']['tags'][key] = value
            with self.assertRaisesRegex(ValueError, 'foreign'): self.review(v)
        v = plan();v['resource_changes'][0]['change']['after']['arn'] = 'arn:aws:ec2:us-east-1:999999999999:vpc/vpc-offline'
        with self.assertRaisesRegex(ValueError, 'foreign'): self.review(v)

    def test_foreign_region_rejected(self):
        v = plan();v['resource_changes'][0]['change']['after']['arn'] = f'arn:aws:ec2:us-west-2:{ACCOUNT}:vpc/vpc-offline'
        with self.assertRaisesRegex(ValueError, 'foreign'): self.review(v)

    def test_both_replacement_orders_rejected(self):
        for actions in (['delete', 'create'], ['create', 'delete']):
            v = plan();v['resource_changes'][0]['change']['actions'] = actions
            with self.assertRaisesRegex(ValueError, 'replacement'): self.review(v)

    def test_direction_does_not_silently_allow_destruction_or_creation(self):
        with self.assertRaises(ValueError): self.review(plan(row(action='delete')))
        with self.assertRaises(ValueError): self.review(plan(), direction='down')

    def test_incomplete_errored_deferred_and_wrong_version_rejected(self):
        for field, value in (('complete', False), ('errored', True), ('applyable', False),
                             ('deferred_changes', [{}]), ('terraform_version', '1.15.7')):
            v = plan();v[field] = value
            with self.assertRaises(ValueError): self.review(v)

    def test_drift_duplicate_and_move_rejected(self):
        v = plan();v['resource_drift'] = [row()]
        with self.assertRaises(ValueError): self.review(v)
        with self.assertRaises(ValueError): self.review(plan(row(), row()))
        v = plan();v['resource_changes'][0]['previous_address'] = 'aws_vpc.old'
        with self.assertRaises(ValueError): self.review(v)

    def test_network_bootstrap_rejects_nat_compute(self):
        v = plan(row('aws_autoscaling_group.wp5_nat["a"]', 'aws_autoscaling_group'))
        with self.assertRaisesRegex(ValueError, 'compute'): self.review(v, network_only=True)

    def test_public_alb_rejected(self):
        v = plan(row('module.alb.aws_lb.demo_internal_alb', 'aws_lb'))
        v['resource_changes'][0]['change']['after']['internal'] = False
        with self.assertRaisesRegex(ValueError, 'public'): self.review(v)

    def test_runtime_task_count_is_not_created_by_infrastructure(self):
        names = check.declarations('apps')
        address = next(a for a, t in names.items() if t == 'aws_ecs_service')
        v = plan(row(address, 'aws_ecs_service'));v['resource_changes'][0]['change']['after']['desired_count'] = 1
        with self.assertRaisesRegex(ValueError, 'WP4'): self.review(v, layer='apps')
        v['resource_changes'][0]['change']['after']['desired_count'] = 0
        self.review(v, layer='apps')

    def test_listener_forwarding_update_rejected(self):
        v = plan(row('module.alb.aws_lb_listener.demo_http_listener', 'aws_lb_listener', 'update'))
        change = v['resource_changes'][0]['change']
        change['before']['internal'] = True;change['after'] = copy.deepcopy(change['before'])
        change['before']['default_action'] = ['old'];change['after']['default_action'] = ['new']
        with self.assertRaisesRegex(ValueError, 'ownership'): self.review(v)

    def test_no_apply_option_or_process_authority(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            check.main(['--apply'])
        with patch('subprocess.run', side_effect=AssertionError('process escape')):
            self.review(plan())

    def test_cli_prints_only_counts_and_review_requirement(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'plan.json';v = plan();v['variables'] = {'SECRET_SENTINEL': 'never print'};f.write_text(json.dumps(v))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(check.main(['--plan-json', str(f), '--layer', 'global', '--direction', 'up', '--account', ACCOUNT, '--region', REGION]), 0)
            self.assertNotIn('SECRET_SENTINEL', out.getvalue())
            self.assertIn('REVIEW_REQUIRED', out.getvalue())

    def test_duplicate_json_and_nan_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError): check.decode(raw)

    def test_permission_delta_adds_only_missing_companion_actions(self):
        value = json.loads((check.ROOT/'scripts/native-dev-retirement-permissions.template.json').read_text())
        self.assertEqual(value['status'], 'REVIEW_TEMPLATE_NOT_INSTALLABLE_UNTIL_BOUND')
        rows = value['policy']['Statement']
        self.assertEqual({r['Action'] for r in rows}, {'ec2:DetachInternetGateway', 'ec2:DisassociateRouteTable'})
        for r in rows:
            self.assertEqual(r['Effect'], 'Allow')
            self.assertIn('341936017254', r['Resource'])
            self.assertEqual(r['Condition']['StringEquals']['aws:ResourceTag/Project'], 'demo')
            self.assertEqual(r['Condition']['StringEquals']['aws:ResourceTag/Environment'], 'dev')
            self.assertIn('DateLessThan', r['Condition'])

    def test_mode_spoofing_and_non_object_plan_rejected(self):
        with self.assertRaises(ValueError): self.review([])
        value = plan();value['resource_changes'][0]['mode'] = 'data'
        with self.assertRaises(ValueError): self.review(value)
