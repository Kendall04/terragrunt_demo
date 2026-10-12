"""Deterministic provider-free E1 repository acceptance, never live acceptance.

python -I -B scripts/tests/final_acceptance/gate.py --report-dir <outside-repo>
Uses preinstalled Python/Git/Terraform only; no init, AWS, download or deployment.
Each test runner installs its process/socket/credential guard. Terraform checks
use only disposable provider-free locals/variables configurations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SUITES = ('authority', 'security_root', 'control_bundles', 'controller_compute',
          'ownership_publication', 'build_supervision', 'qualification', 'internal_release',
          'normal_delivery', 'delivery', 'recovery', 'wp4d', 'lifecycle', 'workflows', 'final_acceptance')
ADDITIONAL_SUITES = ("mutation", "post_switch", "owner_recovery")
# Every criterion includes positive, negative and actual-source admission evidence;
# WP7 composes the resulting relationships and eliminates historical overlap.
CRITERIA = {
    'AC1': ('authority', 'security_root', 'ownership_publication', 'lifecycle', 'final_acceptance'),
    'AC2': ('authority', 'workflows', 'final_acceptance'),
    'AC3': ('ownership_publication', 'wp4d', 'lifecycle', 'workflows', 'final_acceptance'),
    'AC4': ('normal_delivery', 'delivery', 'wp4d', 'final_acceptance'),
    'AC5': ('normal_delivery', 'delivery', 'wp4d', 'final_acceptance'),
    'AC6': ('build_supervision', 'qualification', 'internal_release', 'delivery', 'final_acceptance'),
    'AC7': ('security_root', 'control_bundles', 'ownership_publication', 'lifecycle', 'final_acceptance'),
    'AC8': ('delivery', 'recovery', 'wp4d', 'lifecycle', 'final_acceptance'),
    'AC9': ('delivery', 'recovery', 'workflows', 'final_acceptance'),
    'AC10': ('workflows', 'final_acceptance'),
    'AC11': ('ownership_publication', 'build_supervision', 'delivery', 'recovery', 'lifecycle', 'workflows', 'final_acceptance'),
    'AC12': ('authority', 'qualification', 'delivery', 'recovery', 'lifecycle', 'workflows', 'final_acceptance'),
    'AC13': ('authority', 'security_root', 'controller_compute', 'internal_release', 'wp4d', 'workflows', 'final_acceptance'),
    'AC14': ('normal_delivery', 'delivery', 'final_acceptance'),
    'AC15': ('ownership_publication', 'delivery', 'lifecycle', 'final_acceptance'),
    'AC16': SUITES + ADDITIONAL_SUITES,
}
CHECKS = (
    ('administrative_handoff', ('python', '-I', '-B', 'scripts/tests/handoff/run.py')),
    ('exact_destroy', ('python', '-I', '-B', 'scripts/tests/exact_destroy/run.py')),
    ('dev_down', ('python', '-I', '-B', 'scripts/tests/dev_down/run.py')),
    ('ephemeral_plan_shape', ('python', '-I', '-B', 'scripts/tests/ephemeral/check_plan_shape.py')),
    ('ephemeral_lifecycle', ('python', '-I', '-B', 'scripts/tests/ephemeral/run.py')),
    ('image_retention', ('python', '-I', '-B', 'scripts/tests/retention/run.py')),
    ('nat_reliability', ('python', '-I', '-B', 'scripts/tests/nat/run.py')),
    ('nat_static', ('python', '-I', '-B', 'scripts/tests/nat/check_static.py')),
    ('generated_security', ('python', '-I', '-B', 'scripts/tests/security_root/render.py')),
    ('generated_workflows', ('python', '-I', '-B', 'scripts/workflow_requests/render.py')),
    ('knowledge', ('python', '-I', '-B', 'scripts/tests/final_acceptance/check_knowledge.py')),
    ('extracted_packages', ('python', '-I', '-B', 'scripts/tests/internal_release/check_packages.py')),
    ('e2_static', ('python', '-I', '-B', 'scripts/tests/mutation/check_static.py')),
    ('wp4d_static', ('python', '-I', '-B', 'scripts/tests/wp4d/check_static.py')),
    ('wp5_static', ('python', '-I', '-B', 'scripts/tests/lifecycle/check_static.py')),
    ('wp6_static', ('python', '-I', '-B', 'scripts/tests/workflows/check_static.py')),
    ('terraform_format', ('terraform', 'fmt', '-check', '-recursive', 'terraform/')),
    ('diff_whitespace', ('git', 'diff', '--check')),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = args.report_dir.resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise SystemExit('Reports must be outside the repository')
    directory.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(
        ('AWS', 'AMAZON', 'BOTO', 'GITHUB', 'GH_', 'AZURE', 'GOOGLE', 'TF_', 'TERRAGRUNT')) and
        'PROXY' not in k.upper() and k.upper() not in ('BASH_ENV', 'ENV', 'PYTHONPATH', 'PYTHONSTARTUP')}
    env.update(AWS_EC2_METADATA_DISABLED='true', AWS_CONFIG_FILE=os.devnull,
               AWS_SHARED_CREDENTIALS_FILE=os.devnull, CHECKPOINT_DISABLE='1',
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0',
               GIT_CONFIG_COUNT='3', GIT_CONFIG_KEY_0='core.autocrlf',
               GIT_CONFIG_VALUE_0='true' if os.name == 'nt' else 'input',
               GIT_CONFIG_KEY_1='safe.directory', GIT_CONFIG_VALUE_1=ROOT.as_posix(),
               GIT_CONFIG_KEY_2='core.fsmonitor', GIT_CONFIG_VALUE_2='false')
    git = shutil.which('git')
    def metadata(*args):
        return subprocess.check_output([git, '-c', 'core.fsmonitor=false', *args], cwd=ROOT, env=env, text=True).strip()
    identity = dict(revision=metadata('rev-parse', 'HEAD'), tree=metadata('rev-parse', 'HEAD^{tree}'),
                    branch=metadata('branch', '--show-current'), status=metadata('status', '--porcelain=v1', '--untracked-files=all'))
    def execute(name, argv):
        argv = [sys.executable if argv[0] == 'python' else shutil.which(argv[0]), *argv[1:]]
        if not argv[0]:
            return name, {'status': 'UNAVAILABLE', 'exit': None}
        log = directory / (name + '.log')
        try:
            with log.open('wb') as stream:
                process = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=2400)
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = -1
        raw = log.read_bytes()
        text = raw.decode('utf-8', errors='replace')
        record = dict(status='PASS' if code == 0 else 'FAIL', exit=code,
                      log_sha256=hashlib.sha256(raw).hexdigest())
        if name in SUITES + ADDITIONAL_SUITES:
            counts = re.findall(r'^Ran (\d+) tests?', text, re.M)
            # unittest prints a test docstring on the following line before its
            # outcome. The method ID still appears once on its own first line.
            ids = re.findall(r'^test\w+ \(([^)]+)\)', text, re.M)
            record.update(executed=int(counts[-1]) if len(counts) == 1 else 0, test_ids=ids)
            if not record['executed'] or len(ids) != record['executed'] or not re.search(r'^OK\s*$', text, re.M):
                record['status'] = 'FAIL'
        print(name + ': ' + record['status'], flush=True)
        return name, record
    records = {}
    # Independent processes retain isolated hermetic guards and disposable files.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(execute, name, ('python', '-I', '-B', f'scripts/tests/{name}/run.py')) for name in SUITES + ADDITIONAL_SUITES]
        for future in as_completed(futures):
            name, record = future.result()
            records[name] = record
    for name, argv in CHECKS:
        name, record = execute(name, argv)
        records[name] = record
    sys.path[:0] = [str(ROOT/'scripts/tests/final_acceptance'), str(ROOT/'scripts/tests/security_root'), str(ROOT/'scripts/tests/authority')]
    from contract import authority_inventory, closed, parse
    from inventory import scan, verify
    errors = verify(ROOT)
    try:
        closed(ROOT)
        parsing = parse(ROOT)
        final_authority = authority_inventory(ROOT)
    except (ValueError, KeyError, OSError) as exc:
        errors.append(str(exc))
        parsing = None
        final_authority = None
    hashes = {name: value['sha256'] for name, value in scan(ROOT).items()}
    for base in ('ci/authority', 'specs/iam-hardening', 'terraform/docs'):
        for path in (ROOT/base).rglob('*'):
            if path.is_file():
                hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    regression = sum(records[k].get('executed', 0) for k in SUITES if k != 'final_acceptance')
    if regression != 959:
        errors.append(f'Accepted regression count changed: {regression} != 959')
    static_good = all(records[n]['status'] == 'PASS' for n, _ in CHECKS)
    criteria = {key: {'status': 'PASS' if static_good and not errors and all(records[n]['status'] == 'PASS' for n in names) else 'FAIL',
                      'evidence_suites': list(names)} for key, names in CRITERIA.items()}
    good = not errors and all(v['status'] == 'PASS' for v in records.values())
    identity['status'] = metadata('status', '--porcelain=v1', '--untracked-files=all')
    report = dict(result='E1_REPOSITORY_ACCEPTANCE_PASS' if good else 'E1_REPOSITORY_ACCEPTANCE_FAIL',
                  identity=identity, evaluated_sha256=hashes, content_digest=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
                  criteria=criteria, checks=records, regression_count=regression, wp7_count=records['final_acceptance'].get('executed', 0),
                  errors=errors, parsing=parsing, final_authority_inventory=final_authority,
                  e2_count=records['mutation'].get('executed', 0),
                  e4_count=records['post_switch'].get('executed', 0),
                  e2r_count=records['owner_recovery'].get('executed', 0),
                  external_prerequisites='UNVERIFIED_NOT_DEPLOYED',
                  native_linux_e3='SEPARATE_EVIDENCE_REQUIRED', activation={'request_identities': '0/11', 'wp4d': '0/16', 'wp5': '0/8'},
                  limitations=['WP1 historical characterization is extractor regression, not final TARGET evidence',
                               'Provider-free Terraform does not validate AWS provider schemas',
                               'Live IAM, installation, resource membership, GitHub governance, E3 and app DB/KMS remain separate evidence'])
    (directory/'acceptance.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(report['result'] + f'; regression={regression}; wp7={report["wp7_count"]}')
    return 0 if good else 1


if __name__ == '__main__':
    raise SystemExit(main())
