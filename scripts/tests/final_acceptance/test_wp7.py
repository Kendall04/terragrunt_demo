"""Composed final authority edges and controlled retirement reintroduction."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import contract
import model
import wp4d
import wp5_iam
import wp6
from test_wp4d import fixture, permits
from test_workflows import projection
from scripts.workflow_requests import contract as request

ROOT = Path(__file__).resolve().parents[3]
ACCOUNT = '123456789012'
REGION = 'us-east-1'


class FinalAuthority(unittest.TestCase):
    def fixture(self):
        from inventory import scan
        tmp = tempfile.TemporaryDirectory(prefix='e1-wp7-mutation-')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name in scan(ROOT):
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        shutil.copytree(ROOT / 'ci/authority', root / 'ci/authority', dirs_exist_ok=True)
        return root

    def test_final_actual_source_closure(self):
        self.assertEqual(len(contract.closed(ROOT)['request_identities']), 11)

    def test_retired_sources_are_only_inert_text(self):
        self.assertGreater(len(contract.retirement(ROOT)['retired']), 100)

    def test_packages_and_generated_roots_preserve_accepted_contract(self):
        # Admission reconstructs every protected policy, trust, root and package
        # digest from actual source, not a new WP7 permission manifest.
        doc = model.validate_repository(ROOT)
        self.assertEqual(doc, model.load_authority(ROOT))
        for kind in ('wp4d', 'wp5'):
            self.assertTrue(all(v['package_sha256'] for v in doc[kind]['selected'].values()))

    def test_eleven_request_identities_and_24_compute_bindings_stay_inactive(self):
        doc = contract.closed(ROOT)
        self.assertEqual(doc['wp6']['approvals'], wp6.dev_trial_approvals(doc))
        self.assertEqual(len(doc['wp4d']['selected']) + len(doc['wp5']['selected']), 24)
        self.assertTrue(all(v['stage'] == 'INERT' for v in doc['request_identities'].values()))

    def test_exact_subject_acquisition_matrix_has_positive_diagonal(self):
        subjects = {k: request.subject(k, projection(k)['workflow_commit']) for k in request.IDENTITIES}
        for caller, subject in subjects.items():
            for target in request.IDENTITIES:
                trust = wp6.trust(target, projection(target), ACCOUNT)['Statement'][0]
                conditions = trust['Condition']['StringEquals']
                self.assertEqual(subject == conditions['token.actions.githubusercontent.com:sub'], caller == target)
                self.assertEqual(conditions['token.actions.githubusercontent.com:aud'], 'sts.amazonaws.com')
                self.assertEqual(trust['Principal'], {'Federated': f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com'})

    def test_old_default_subject_and_dev_approval_cannot_acquire_target(self):
        for key in request.IDENTITIES:
            trust = wp6.trust(key, projection(key), ACCOUNT)
            subject = trust['Statement'][0]['Condition']['StringEquals']['token.actions.githubusercontent.com:sub']
            for old in ('repo:Kendall04/terragrunt_demo:environment:dev',
                        'repo:Kendall04/terragrunt_demo:environment:prod',
                        'repo:Kendall04/terragrunt_demo:environment:dev-infra-approval'):
                self.assertNotEqual(subject, old)
            self.assertNotIn('*', json.dumps(trust))

    def test_every_mutation_requester_has_only_own_exact_gateway(self):
        for key in request.IDENTITIES:
            p = wp6.policy(key, projection(key), ACCOUNT, REGION)
            for target in request.IDENTITIES:
                endpoint = f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-gateway-{target}:7'
                self.assertEqual(permits(p, 'lambda:InvokeFunction', endpoint, {'aws:RequestedRegion': REGION}),
                                 key == target and not key.startswith('plan-'))
            for endpoint in (f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-gateway-{key}',
                             f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-gateway-{key}:6'):
                self.assertFalse(permits(p, 'lambda:InvokeFunction', endpoint, {'aws:RequestedRegion': REGION}))

    def test_requesters_cannot_chain_pass_roles_or_mutate_directly(self):
        for key in request.IDENTITIES:
            p = wp6.policy(key, projection(key), ACCOUNT, REGION)
            for action in ('sts:AssumeRole', 'iam:PassRole', 'iam:PutRolePolicy', 'ecs:RegisterTaskDefinition',
                           'ecs:RunTask', 'ecs:UpdateService', 'elasticloadbalancing:ModifyListener',
                           'ec2:RunInstances', 'codebuild:StartBuild', 'lambda:UpdateFunctionCode', 's3:PutObject'):
                self.assertNotIn(action, {a for s in p['Statement'] for a in s['Action']}, (key, action))

    def test_gateway_can_start_only_its_service_specific_project(self):
        for key in ('deploy-dev', 'promote-prod', 'emergency-dev', 'emergency-prod'):
            resources = fixture(request.environment(key))
            resources['project'] = 'e1-controller-' + key
            p = wp4d.policy('request-gateway/' + key, resources, ACCOUNT, REGION, 'synthetic-version')
            for target in ('deploy-dev', 'promote-prod', 'emergency-dev', 'emergency-prod'):
                self.assertEqual(permits(p, 'codebuild:StartBuild', f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-{target}'), key == target)
            self.assertFalse(permits(p, 'iam:PassRole', '*'))

    def test_delivery_passrole_exact_environment_and_service(self):
        for key, env in (('deploy-dev', 'dev'), ('promote-prod', 'prod')):
            p = wp4d.policy('normal-delivery/' + key, fixture(env), ACCOUNT, REGION, 'synthetic-version')
            for e in ('dev', 'prod'):
                for color in ('blue', 'green'):
                    for role in ('task', 'exec'):
                        arn = f'arn:aws:iam::{ACCOUNT}:role/demo-{e}-app-api-{color}-{role}-role'
                        self.assertEqual(permits(p, 'iam:PassRole', arn, {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}), e == env)
                        self.assertFalse(permits(p, 'iam:PassRole', arn, {'iam:PassedToService': 'lambda.amazonaws.com'}))
                        self.assertFalse(permits(p, 'iam:PassRole', arn))

    def test_emergency_cleanup_nat_cannot_publish_or_register(self):
        for binding in wp4d.RESERVED:
            if not binding.startswith(('emergency-recovery/', 'cleanup-recovery/', 'nat-recovery/')):
                continue
            p = wp4d.policy(binding, fixture(wp4d.RESERVED[binding][0]), ACCOUNT, REGION, 'synthetic-version')
            for action in ('iam:PassRole', 'sts:AssumeRole', 'ecs:RegisterTaskDefinition', 'ecs:RunTask',
                           'ecr:PutImage', 'ec2:RunInstances', 'ec2:TerminateInstances', 'iam:PutRolePolicy'):
                self.assertNotIn(action, {a for s in p['Statement'] for a in s['Action']}, (binding, action))
            self.assertFalse(permits(p, 's3:PutObject', f'arn:aws:s3:::demo-release-artifacts-{ACCOUNT}/qualifications/demo-api/fake.json'))

    def test_infra_gateways_are_distinct_from_security_administration(self):
        for key in ('infra-dev', 'infra-prod', 'infra-high-risk-dev', 'infra-high-risk-prod'):
            p = wp5_iam.policy('request-gateway/' + key, ACCOUNT, REGION, {}, 'a'*64, 'synthetic-version')
            self.assertTrue(permits(p, 'codebuild:StartBuild', f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-{key}'))
            for action in ('iam:CreateRole', 'iam:PassRole', 'kms:PutKeyPolicy', 'sts:AssumeRole', 'ecs:UpdateService'):
                self.assertFalse(permits(p, action, '*'))

    def test_all_ordinary_lifecycle_policy_actions_exclude_security_administration(self):
        for env in ('dev', 'prod'):
            resources = {k: [] for k in wp5_iam.INVENTORY}
            for high in ('', 'high-risk-'):
                p = wp5_iam.policy('environment-lifecycle/infra-' + high + env, ACCOUNT, REGION, resources, 'a'*64, 'synthetic-version')
                for statement in p['Statement']:
                    for action in statement['Action']:
                        self.assertFalse(action.startswith(('iam:Create', 'iam:Put', 'iam:Update', 'iam:Delete', 'kms:', 'secretsmanager:Put', 'sts:')))

    def test_prod_authorization_cannot_be_supplied_by_dev_workflow(self):
        for key in ('promote-prod', 'emergency-prod', 'infra-prod', 'infra-high-risk-prod'):
            self.assertEqual(request.source_ref(key), 'refs/heads/main')
            self.assertEqual(request.environment(key), 'prod')
        p = wp4d.policy('normal-delivery/promote-prod', fixture('prod'), ACCOUNT, REGION, 'synthetic-version')
        authority = f'arn:aws:s3:::demo-release-artifacts-{ACCOUNT}/prod-approvals/demo-api/approval.json'
        self.assertTrue(permits(p, 's3:GetObject', authority))
        self.assertFalse(permits(p, 's3:PutObject', authority))

    def test_deny_all_cannot_satisfy_intended_request_path(self):
        key = 'deploy-dev'
        p = wp6.policy(key, projection(key), ACCOUNT, REGION)
        endpoint = projection(key)['endpoint_readback']
        self.assertTrue(permits(p, 'lambda:InvokeFunction', endpoint, {'aws:RequestedRegion': REGION}))
        p['Statement'] = [s for s in p['Statement'] if 'lambda:InvokeFunction' not in s['Action']]
        with self.assertRaises(ValueError):
            contract.require(permits(p, 'lambda:InvokeFunction', endpoint, {'aws:RequestedRegion': REGION}), 'essential gateway grant removed')

    def test_restore_generated_controller_passrole_is_rejected(self):
        root = self.fixture()
        path = root / 'terraform/infra/security/modules/request_identities/main.tf.json'
        doc = json.loads(path.read_text())
        doc['resource']['aws_iam_role_policy']['alternate'] = {'role': 'e1-request-deploy-dev', 'policy': json.dumps({'Statement': [{'Effect': 'Allow', 'Action': 'iam:PassRole', 'Resource': '*'}]})}
        path.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            contract.closed(root)

    def test_restore_old_iam_root_is_rejected(self):
        root = self.fixture()
        name = 'terraform/infra/shared/modules/iam_github/github_delivery_split.tf'
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / ('ci/authority/retired/' + name + '.txt'), path)
        with self.assertRaises(ValueError):
            contract.closed(root)

    def test_restore_action_is_rejected(self):
        root = self.fixture()
        path = root / '.github/actions/aws-oidc/action.yml'
        path.parent.mkdir(parents=True)
        path.write_text('name: restored\nruns: {using: composite, steps: []}\n')
        with self.assertRaises(ValueError):
            contract.retirement(root)

    def test_restore_direct_wrapper_is_rejected(self):
        root = self.fixture()
        (root / 'scripts/deploy.sh').write_text('#!/bin/bash\naws ecs update-service "$@"\n')
        with self.assertRaises(ValueError):
            contract.retirement(root)

    def test_restore_direct_entrypoint_is_rejected(self):
        root = self.fixture()
        path = root / 'scripts/ecs-blue-green-deploy.sh'
        path.write_text(path.read_text().replace('die "E1_LEGACY_PATH_RETIRED: use protected normal delivery or emergency recovery."', 'parse_args "$@"\n  promote_inactive_color'))
        with self.assertRaises(ValueError):
            contract.retirement(root)

    def test_archive_edit_cannot_redefine_accepted_roots(self):
        root = self.fixture()
        path = root / 'ci/authority/retired/terraform/infra/shared/main.tf.txt'
        path.write_text(path.read_text() + '\nresource "aws_iam_role" "alternate" {}\n')
        with self.assertRaises(ValueError):
            contract.retirement(root)

    def test_direct_aws_workflow_restoration_is_rejected(self):
        root = self.fixture()
        (root / '.github/workflows/alternate.yml').write_text('permissions:\n  id-token: write\nsteps:\n  - uses: aws-actions/configure-aws-credentials@v4\n')
        with self.assertRaises(ValueError):
            contract.closed(root)

    def test_inactive_state_is_not_installation_evidence(self):
        root = self.fixture()
        path = root / model.AUTHORITY
        doc = json.loads(path.read_text())
        doc['wp6']['approvals']['deploy-dev'] = {'active': True}
        path.write_text(json.dumps(doc))
        with self.assertRaises((ValueError, KeyError)):
            contract.closed(root)

    def test_actual_python_json_and_generated_yaml_parse(self):
        counts = contract.parse(ROOT)
        self.assertGreater(counts['python'], 0)
        self.assertGreater(counts['json'], 0)
        self.assertGreater(counts['generated_yaml'], 0)
