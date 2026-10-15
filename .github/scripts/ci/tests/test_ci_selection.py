"""Exercise real Git events, workflow job conditions and the actual result CLI."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / '.github/scripts/ci/select-checks.py'
spec = importlib.util.spec_from_file_location('ci_selection', SCRIPT)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)
WORKFLOW = json.loads((ROOT / '.github/workflows/ci.yml').read_text())
JOBS = {'acceptance': 'e1-acceptance', 'app': 'app-ci',
        'hygiene': 'repo-hygiene', 'infra': 'infra-static'}


def workflow_jobs(selection, detection='success'):
    """Evaluate the actual supported workflow expressions, refusing other syntax."""
    selected = set()
    for gate, job in JOBS.items():
        expression = WORKFLOW['jobs'][job]['if']
        expected = "${{ always() && !cancelled() && (needs.detect-changes.result != 'success' || needs.detect-changes.outputs." + gate + " != 'false') }}"
        if expression != expected:
            raise AssertionError('Changed/unsupported job condition: ' + job)
        if detection != 'success' or selection.get(gate) is not False:
            selected.add(gate)
    return selected


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e11-ci-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('GIT_', 'AWS', 'GITHUB', 'CI_'))}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME='CI Test', GIT_AUTHOR_EMAIL='ci@example.invalid',
                        GIT_COMMITTER_NAME='CI Test', GIT_COMMITTER_EMAIL='ci@example.invalid')
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'commit.gpgsign', 'false')
        self.write('LICENSE')
        self.commit()

    def git(self, *args):
        result = subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=self.root,
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture\n', encoding='utf-8')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def event(self, base, head=None, **changes):
        actual = self.git('rev-parse', 'HEAD')
        return {'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': actual,
                'GITHUB_REF': 'refs/heads/main', 'CI_BASE_SHA': base,
                'CI_HEAD_SHA': head or actual, **changes}

    def changed(self, name):
        base = self.git('rev-parse', 'HEAD')
        self.write(name)
        self.commit()
        return selector.select(self.root, self.event(base))

    def test_protected_script_selects_acceptance_without_scanners(self):
        self.assertEqual(workflow_jobs(self.changed('scripts/normal_delivery/delivery.py')),
                         {'acceptance', 'hygiene'})

    def test_selector_cli_outputs_feed_actual_job_conditions(self):
        base = self.git('rev-parse', 'HEAD')
        self.write('scripts/recovery/application.py'); self.commit()
        output = self.root / 'github-output'
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT)], cwd=self.root,
                                env=self.env | self.event(base) | {'GITHUB_OUTPUT': str(output)},
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        emitted = dict(line.split('=', 1) for line in output.read_text().splitlines())
        selection = json.loads(emitted['selection'])
        for gate in selector.GATES:
            self.assertEqual(emitted[gate], str(selection[gate]).lower())
        self.assertEqual(workflow_jobs(selection), {'acceptance', 'hygiene'})

    def test_complete_push_keeps_earlier_protected_change(self):
        base = self.git('rev-parse', 'HEAD')
        self.write('scripts/recovery/application.py'); self.commit()
        (self.root / 'LICENSE').write_text('later unrelated change\n'); self.commit()
        self.assertIn('acceptance', workflow_jobs(selector.select(self.root, self.event(base))))

    def test_authority_schema_configuration_and_specs(self):
        for name in ('ci/authority/source-inventory.json', 'ci/schemas/e1-qualification.schema.json',
                     'ci/new-contract/configuration.xyz', 'specs/iam-hardening/spec.md'):
            with self.subTest(name=name):
                self.assertIn('acceptance', workflow_jobs(self.changed(name)))

    def test_generated_target_modules(self):
        for env in ('dev', 'prod'):
            with self.subTest(env=env):
                self.assertEqual(workflow_jobs(self.changed('terraform/modules/target/' + env + '/apps/new.tf')),
                                 {'acceptance', 'hygiene', 'infra'})

    def test_security_root(self):
        self.assertIn('acceptance', workflow_jobs(self.changed('terraform/infra/security/authority.json')))

    def test_application_workflow_selects_its_gate(self):
        self.assertEqual(workflow_jobs(self.changed('.github/workflows/ci-dotnet.yml')),
                         {'acceptance', 'app', 'hygiene'})

    def test_orchestrator_and_unmapped_workflow_select_all(self):
        for name in ('ci.yml', 'future-validation.yml'):
            self.assertEqual(workflow_jobs(self.changed('.github/workflows/' + name)), set(selector.GATES))

    def test_composite_action(self):
        self.assertEqual(workflow_jobs(self.changed('.github/actions/new/action.yml')), set(selector.GATES))

    def test_selector_change_selects_all_affected_jobs(self):
        self.assertEqual(workflow_jobs(self.changed('.github/scripts/ci/select-checks.py')), set(selector.GATES))

    def test_protected_deletion(self):
        name = 'scripts/normal_delivery/deleted.py'
        self.write(name); base = self.commit()
        (self.root / name).unlink(); self.commit()
        self.assertIn('acceptance', workflow_jobs(selector.select(self.root, self.event(base))))

    def test_rename_out_of_protected_tree(self):
        name = 'scripts/normal_delivery/moved.py'
        self.write(name); base = self.commit()
        self.git('mv', name, 'README.md'); self.commit()
        self.assertIn('acceptance', workflow_jobs(selector.select(self.root, self.event(base))))

    def test_rename_into_protected_tree(self):
        base = self.git('rev-parse', 'HEAD')
        (self.root / 'scripts').mkdir()
        self.git('mv', 'LICENSE', 'scripts/new.xyz'); self.commit()
        self.assertIn('acceptance', workflow_jobs(selector.select(self.root, self.event(base))))

    def test_unknown_protected_file(self):
        self.assertIn('acceptance', workflow_jobs(self.changed('scripts/future-handler.xyz')))

    def test_unknown_root_path_selects_all(self):
        self.assertEqual(workflow_jobs(self.changed('future-input.xyz')), set(selector.GATES))

    def test_historical_document_need_not_run_expensive_gates(self):
        self.assertEqual(workflow_jobs(self.changed('terraform/docs/case-study.md')), {'hygiene'})

    def test_application_source_retains_app_gate(self):
        self.assertEqual(workflow_jobs(self.changed('demo-api/terragrunt-demo/Controllers/DemoTextController.cs')), {'app'})

    def test_readiness_helpers_retain_app_and_acceptance(self):
        self.assertEqual(workflow_jobs(self.changed('scripts/ecs-readiness-gate.sh')),
                         {'acceptance', 'app', 'hygiene'})

    def test_missing_base_and_new_branch_select_all(self):
        for base in ('', '0' * 40, 'a' * 40):
            with self.subTest(base=base):
                self.assertEqual(workflow_jobs(selector.select(self.root, self.event(base))), set(selector.GATES))

    def test_shallow_history_selects_all(self):
        actual = self.git('rev-parse', 'HEAD')
        (self.root / '.git/shallow').write_text(actual + '\n')
        self.assertEqual(workflow_jobs(selector.select(self.root, self.event(actual))), set(selector.GATES))

    def test_checkout_identity_mismatch_fails_and_workflow_runs_gates(self):
        with self.assertRaises(ValueError):
            selector.select(self.root, self.event('', GITHUB_SHA='a' * 40))
        self.assertEqual(workflow_jobs({}, 'failure'), set(selector.GATES))

    def test_real_pull_request_merge_selects_protected_head(self):
        base = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-qb', 'feature')
        self.write('scripts/recovery/application.py'); head = self.commit()
        self.git('checkout', '-q', 'main'); self.git('merge', '--no-ff', '-qm', 'merge', head)
        event = self.event(base, head, GITHUB_EVENT_NAME='pull_request', GITHUB_BASE_REF='main')
        self.assertEqual(workflow_jobs(selector.select(self.root, event)), {'acceptance', 'hygiene'})

    def test_ambiguous_pr_and_unsupported_event_select_all(self):
        base = self.git('rev-parse', 'HEAD')
        for event in ('pull_request', 'unknown'):
            self.assertEqual(workflow_jobs(selector.select(self.root, self.event(base, GITHUB_EVENT_NAME=event,
                                                                                           GITHUB_BASE_REF='main'))), set(selector.GATES))

    def test_malformed_and_linked_diff_never_earn_exemption(self):
        for raw in (b'broken', b':120000 120000 ' + b'a' * 40 + b' ' + b'b' * 40 + b' M\0README.md\0',
                    b':100644 100644 ' + b'a' * 40 + b' ' + b'b' * 40 + b' M\0bad\npath\0'):
            with self.assertRaises(selector.Uncertain):
                selector.changed_paths(raw)

    def test_existing_source_inventory_and_approved_contracts_select_acceptance(self):
        paths = json.loads((ROOT / 'ci/authority/source-inventory.json').read_text())['sources']
        paths = set(paths) | set(json.loads((ROOT / 'ci/authority/retirement.json').read_text())['approved_contract_sha256'])
        for name in paths:
            with self.subTest(name=name):
                self.assertIn('acceptance', workflow_jobs(selector.classify([name])))


class WorkflowTests(unittest.TestCase):
    def test_outer_triggers_and_exact_checkout(self):
        events = WORKFLOW['on']
        self.assertEqual(events['push'], {})
        self.assertEqual(events['pull_request']['branches'], ['develop', 'main'])
        self.assertIn('edited', events['pull_request']['types'])
        self.assertFalse(any('paths' in key for key in events['pull_request']))
        checkout = WORKFLOW['jobs']['detect-changes']['steps'][0]
        self.assertEqual(checkout['with'], {'ref': '${{ github.sha }}', 'persist-credentials': False, 'fetch-depth': 0})
        self.assertEqual(WORKFLOW['jobs']['e1-acceptance']['steps'][0]['with'],
                         {'ref': '${{ github.sha }}', 'persist-credentials': False, 'fetch-depth': 0})
        self.assertTrue(all(output == '${{ steps.scope.outputs.' + name + ' }}'
                            for name, output in WORKFLOW['jobs']['detect-changes']['outputs'].items()))

    def verify_cli(self, selection, results, detection='success'):
        job = WORKFLOW['jobs']['validation']
        step = job['steps'][-1]
        self.assertEqual(job['if'], '${{ always() }}')
        self.assertEqual(step['run'], 'python3 -I -B .github/scripts/ci/select-checks.py --verify')
        self.assertEqual(step['env']['CI_SELECTION'], '${{ needs.detect-changes.outputs.selection }}')
        self.assertEqual(step['env']['CI_DETECTION'], '${{ needs.detect-changes.result }}')
        env = dict(os.environ, CI_SELECTION=json.dumps(selection), CI_DETECTION=detection, GITHUB_SHA='a' * 40)
        for gate, target in JOBS.items():
            key = 'CI_RESULT_' + gate.upper()
            self.assertIn(target, job['needs'])
            self.assertEqual(step['env'][key], '${{ needs.' + target + '.result }}')
            env[key] = results[gate]
        return subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), '--verify'], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_failed_skipped_cancelled_or_missing_selected_gate_cannot_pass(self):
        selected = selector.all_gates('fixture') | {'actual_sha': 'a' * 40}
        for gate in selector.GATES:
            for result in ('failure', 'skipped', 'cancelled', '', 'unknown'):
                with self.subTest(gate=gate, result=result):
                    outcomes = dict.fromkeys(selector.GATES, 'success') | {gate: result}
                    self.assertNotEqual(self.verify_cli(selected, outcomes).returncode, 0)

    def test_valid_selection_and_legitimate_skips(self):
        selection = selector.classify(['demo-api/terragrunt-demo/Program.cs']) | {'actual_sha': 'a' * 40}
        outcomes = {g: 'success' if selection[g] else 'skipped' for g in selector.GATES}
        self.assertEqual(self.verify_cli(selection, outcomes).returncode, 0)
        outcomes['acceptance'] = 'success'  # Unexpected execution cannot masquerade as the recorded selection.
        self.assertNotEqual(self.verify_cli(selection, outcomes).returncode, 0)

    def test_failed_detection_or_invalid_selection_cannot_pass(self):
        selected = selector.all_gates('fixture') | {'actual_sha': 'a' * 40}
        outcomes = dict.fromkeys(selector.GATES, 'success')
        for detection in ('failure', 'skipped', ''):
            self.assertNotEqual(self.verify_cli(selected, outcomes, detection).returncode, 0)
        for changed in ({}, {**selected, 'acceptance': 'false'}, {**selected, 'actual_sha': 'b' * 40}):
            self.assertNotEqual(self.verify_cli(changed, outcomes).returncode, 0)

    def test_actual_acceptance_command_failure_is_not_masked(self):
        job = WORKFLOW['jobs']['e1-acceptance']
        step = job['steps'][-1]
        self.assertEqual(step['run'], 'python3 -I -B scripts/tests/final_acceptance/gate.py --report-dir "$RUNNER_TEMP/e1-acceptance"')
        self.assertNotIn('continue-on-error', job)
        self.assertNotIn('continue-on-error', step)
        self.assertNotIn('if', step)
        selected = selector.classify(['scripts/normal_delivery/delivery.py']) | {'actual_sha': 'a' * 40}
        # Execute the actual workflow command/arguments over a failing stand-in,
        # just as the existing CD Safety runner tests use controlled processes.
        with tempfile.TemporaryDirectory(prefix='e11-failed-gate-') as directory:
            gate = Path(directory) / 'scripts/tests/final_acceptance/gate.py'
            gate.parent.mkdir(parents=True)
            gate.write_text('raise SystemExit(7)\n')
            process = subprocess.run([sys.executable, *shlex.split(step['run'])[1:]],
                                     cwd=directory, capture_output=True, timeout=20)
            self.assertEqual(process.returncode, 7)
        outcomes = {'acceptance': 'success' if process.returncode == 0 else 'failure',
                    'hygiene': 'success', 'app': 'skipped', 'infra': 'skipped'}
        self.assertNotEqual(self.verify_cli(selected, outcomes).returncode, 0)

    def test_acceptance_runs_once_and_standalone_static_callers_preserved(self):
        self.assertIs(WORKFLOW['jobs']['infra-static']['with']['run_acceptance'], False)
        static = (ROOT / '.github/workflows/ci-terragrunt.yml').read_text()
        self.assertIn('      run_acceptance:', static)
        self.assertIn('        default: true', static)
        self.assertIn('      - name: Final E1 repository acceptance\n        if: inputs.run_acceptance', static)

    def test_cd_safety_application_readiness_and_shell_helpers_preserved(self):
        self.assertEqual(WORKFLOW['jobs']['app-ci']['uses'], './.github/workflows/ci-dotnet.yml')
        app = (ROOT / '.github/workflows/ci-dotnet.yml').read_text()
        self.assertIn('dotnet test', app)
        self.assertIn('scripts/tests/run-offline-readiness-tests.sh', app)
        safety = (ROOT / '.github/workflows/ci-cd-safety.yml').read_text()
        self.assertIn('branches: [develop, main]', safety)
        self.assertIn('  push:\n    branches: [develop, main]', safety)
        self.assertNotIn('paths:', safety)
        self.assertIn('bash .github/scripts/cd/tests/test-safety-workflow.sh', safety)
        self.assertIn('for suite in detect-scope resolve-terragrunt-layers validate-infra-gate', safety)
        hygiene = (ROOT / '.github/workflows/ci-repo-hygiene.yml').read_text()
        self.assertEqual(hygiene.count('.github/scripts/cd/*.sh .github/scripts/cd/tests/*.sh'), 2)

    def test_validation_jobs_have_no_aws_credentials_or_deployment_permissions(self):
        self.assertEqual(WORKFLOW['permissions'], {'contents': 'read'})
        self.assertNotIn('pull_request_target', WORKFLOW['on'])
        raw = json.dumps(WORKFLOW)
        for forbidden in ('id-token', 'configure-aws-credentials', 'role-to-assume', 'continue-on-error'):
            self.assertNotIn(forbidden, raw)


if __name__ == '__main__':
    unittest.main()
