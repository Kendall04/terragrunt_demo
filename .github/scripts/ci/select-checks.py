"""Provider-free CI selection from complete event history, plus result enforcement.

Like CD Safety, exemption needs exact checkout identity and complete history.
Renames are inspected as deletion + addition. Uncertainty selects every gate.
This selects validation only; it never selects deployment or acquires credentials.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

GATES = ('acceptance', 'app', 'hygiene', 'infra')
KNOWLEDGE = {'README.md', 'AGENTS.md', 'terraform/AGENTS.md',
             'terraform/infra/security/README.md'}
HISTORICAL = {'terraform/docs/case-study.md', 'terraform/docs/interview-guide.md',
              'terraform/docs/ci-cd-target-architecture.md'}
READINESS = {'scripts/ecs-readiness-gate.sh', 'scripts/ecs-blue-green-deploy.sh',
             'scripts/aws-response-boundary.sh', 'scripts/bounded-process.py',
             'scripts/render-demo-api-taskdef.sh', 'scripts/validate-demo-api-taskdef.sh'}


class Uncertain(Exception):
    pass


def all_gates(reason):
    return dict.fromkeys(GATES, True) | {'reason': reason}


def classify(paths):
    result = dict.fromkeys(GATES, False)
    if not paths:
        return all_gates('empty-diff')
    for path in paths:
        p = Path(path)
        if path in KNOWLEDGE or p.name == 'AGENTS.md':
            result.update(acceptance=True, hygiene=True)
        elif path in HISTORICAL or path.startswith('terraform/docs/') and p.suffix == '.png':
            result['hygiene'] = True
        elif path.startswith('terraform/docs/'):
            result.update(acceptance=True, hygiene=True)
        elif path.startswith('terraform/'):
            result.update(acceptance=True, hygiene=True, infra=True)
        elif path.startswith('scripts/'):
            result.update(acceptance=True, hygiene=True)
            if path in READINESS or path.startswith('scripts/tests/') and (
                    p.suffix == '.sh' or p.name in ('fake-readiness-aws', 'test-bounded-process.py')):
                result['app'] = True
        elif path.startswith(('ci/', 'specs/')):
            result.update(acceptance=True, hygiene=True)
        elif path.startswith('operations/sql-backup/'):
            result.update(acceptance=True, app=True, hygiene=True)
            if p.suffix in ('.tf', '.hcl') or path.endswith('.tf.json'):
                result['infra'] = True
        elif path.startswith('demo-api/'):
            result['app'] = True
            if path.startswith('demo-api/deploy/') or p.name in ('Dockerfile', '.dockerignore'):
                result.update(acceptance=True, hygiene=True)
        elif path.startswith('.github/workflows/'):
            result.update(acceptance=True, hygiene=True)
            if p.name == 'ci-dotnet.yml':
                result['app'] = True
            elif p.name in ('ci-terragrunt.yml', 'ci-terragrunt-manual.yml'):
                result['infra'] = True
            elif p.name != 'ci-cd-safety.yml' and p.name != 'ci-repo-hygiene.yml' and not (
                    p.name.startswith(('e1-', 'cd-', 'deploy-', 'promote-', 'rollback-', 'release-'))
                    or p.name in ('cd.yml', 'ci-terragrunt-plan.yml')):
                # Orchestration and new/unmapped workflow behavior affect all jobs.
                return all_gates('unmapped-or-orchestration-workflow')
        elif path.startswith('.github/scripts/ci/'):
            return all_gates('ci-selector-or-enforcement')
        elif path.startswith('.github/actions/'):
            return all_gates('composite-action')
        elif path.startswith('.github/'):
            result.update(acceptance=True, hygiene=True)
        elif path == 'LICENSE':
            pass
        else:
            return all_gates('unmapped-path')
    return result | {'reason': 'complete-path-classification'}


def changed_paths(raw):
    """Strict NUL raw-diff decoding; type/mode uncertainty cannot earn exemption."""
    fields = raw.split(b'\0')
    if not fields or fields[-1] != b'' or (len(fields) - 1) % 2:
        raise Uncertain('malformed-diff')
    paths = []
    for i in range(0, len(fields) - 1, 2):
        record = fields[i].decode('ascii')
        match = re.fullmatch(r':(000000|100644|100755) (000000|100644|100755) '
                             r'[0-9a-f]{40} [0-9a-f]{40} ([AMD])', record)
        if not match:
            raise Uncertain('uncertain-file-type')
        path = fields[i + 1].decode('utf-8')
        if not path or path.startswith('/') or any(x in path for x in ('\\', '\n', '\r', '\t')) or '..' in path.split('/'):
            raise Uncertain('uncertain-path')
        # Executable docs, type changes and executable-bit changes need all checks.
        if match[1] != match[2] and '000000' not in (match[1], match[2]) or (
                '100755' in (match[1], match[2]) and Path(path).suffix in ('.md', '.png')):
            raise Uncertain('uncertain-file-mode')
        paths.append(path)
    return paths


def select(root, event):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')

    def git(*args):
        result = subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=root,
                                env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
        if result.returncode or len(result.stdout) > 4194304:
            raise Uncertain('unavailable-history')
        return result.stdout

    actual = git('rev-parse', '--verify', 'HEAD').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', event.get('GITHUB_SHA', '')) or actual != event['GITHUB_SHA']:
        raise ValueError('CI_CHECKOUT_IDENTITY_MISMATCH')
    try:
        if git('rev-parse', '--is-shallow-repository').strip() != b'false':
            raise Uncertain('shallow-history')
        base, head = event.get('CI_BASE_SHA', ''), event.get('CI_HEAD_SHA', '')
        for sha in (base, head):
            if not re.fullmatch('[0-9a-f]{40}', sha) or sha == '0' * 40:
                raise Uncertain('unavailable-event-commit')
            git('cat-file', '-e', sha + '^{commit}')
        diff = ('diff', '--raw', '--no-abbrev', '-z', '--no-renames', '--no-ext-diff', '--no-textconv')
        if event.get('GITHUB_EVENT_NAME') == 'pull_request':
            if event.get('GITHUB_BASE_REF') not in ('develop', 'main'):
                raise Uncertain('unexpected-pr-target')
            if git('show', '-s', '--format=%P', actual).decode().strip() != base + ' ' + head:
                raise Uncertain('ambiguous-merge')
            ancestor = git('merge-base', '--all', base, head).decode().strip()
            if not re.fullmatch('[0-9a-f]{40}', ancestor):
                raise Uncertain('ambiguous-merge-base')
            paths = changed_paths(git(*diff, ancestor, head, '--'))
            paths += changed_paths(git(*diff, base, actual, '--'))
        elif event.get('GITHUB_EVENT_NAME') == 'push':
            if head != actual or not event.get('GITHUB_REF', '').startswith('refs/heads/'):
                raise Uncertain('unexpected-push-identity')
            git('merge-base', '--is-ancestor', base, head)
            paths = changed_paths(git(*diff, base, head, '--'))
        else:
            raise Uncertain('unsupported-event')
        result = classify(paths)
    except (Uncertain, UnicodeError, subprocess.TimeoutExpired) as exc:
        result = all_gates(str(exc) if isinstance(exc, Uncertain) else 'history-decoding-or-timeout')
    return result | {'actual_sha': actual}


def enforce(selection, results, detection, expected_sha):
    if detection != 'success' or set(selection) != set(GATES) | {'reason', 'actual_sha'}:
        raise ValueError('CI_SELECTION_NOT_EXECUTED_SUCCESSFULLY')
    if not selection['reason'] or selection['actual_sha'] != expected_sha:
        raise ValueError('CI_SELECTION_IDENTITY_MISSING')
    for gate in GATES:
        if type(selection[gate]) is not bool:
            raise ValueError('CI_SELECTION_INVALID')
        expected = 'success' if selection[gate] else 'skipped'
        if results.get(gate) != expected:
            raise ValueError('CI_REQUIRED_RESULT_MISSING_OR_FAILED: ' + gate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        selection = json.loads(os.environ['CI_SELECTION'])
        enforce(selection, {gate: os.environ.get('CI_RESULT_' + gate.upper()) for gate in GATES},
                os.environ.get('CI_DETECTION'), os.environ['GITHUB_SHA'])
        print('CI_VALIDATION_PASS: required jobs executed; unselected jobs skipped')
        return
    result = select(Path.cwd(), os.environ)
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':'))
    print(encoded)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for gate in GATES:
                stream.write(gate + '=' + str(result[gate]).lower() + '\n')
            stream.write('selection=' + encoded + '\n')


if __name__ == '__main__':
    main()
