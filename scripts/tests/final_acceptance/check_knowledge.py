"""Current KDD links, immutable approved contracts and truthful status checks."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS = ('terraform/docs/original-full-lifecycle.md', 'README.md', 'AGENTS.md', 'terraform/AGENTS.md', 'terraform/infra/security/README.md',
             'terraform/docs/architecture.md', 'terraform/docs/deployment.md', 'terraform/docs/bootstrap.md',
             'terraform/docs/secrets-strategy.md', 'terraform/docs/decisions-and-limitations.md',
             'terraform/docs/validation.md', 'terraform/docs/e2-environment-mutation.md',
             'terraform/docs/e4-post-switch-recovery.md',
             'terraform/docs/e8-rollback-image-retention.md',
             'terraform/docs/e15-ephemeral-lifecycle.md',
             'terraform/docs/e15b-dev-down.md',
             'terraform/docs/e15c-exact-destroy-approval.md',
             'terraform/docs/e15d-administrative-handoff.md',
             'terraform/docs/e15e-ecs-quiescence.md',
             'terraform/docs/e15f-nat-quiescence.md',
             'terraform/docs/e15ef-combined-quiescence.md',
             'terraform/docs/e15g-operational-teardown.md',
             'terraform/docs/e15h-nat-trusted-closure.md',
             'terraform/docs/e2r-owner-recovery.md',
             'terraform/docs/e13-nat-reliability.md', 'terraform/docs/e14b-toolchain-reproducibility.md', 'terraform/docs/e1-final-acceptance.md')


def check(root):
    root = Path(root)
    errors = []
    for name in DOCUMENTS:
        path = root/name
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            target = target.split('#', 1)[0]
            if not target or re.match(r'[a-zA-Z]+:', target):
                continue
            resolved = (path.parent/target).resolve()
            if not resolved.exists():
                errors.append(name + ': missing local link ' + target)
    manifest = json.loads((root/'ci/authority/retirement.json').read_text())
    for name, digest in manifest['approved_contract_sha256'].items():
        if hashlib.sha256((root/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() != digest:
            errors.append('approved contract changed: ' + name)
    for name in ('architecture', 'deployment', 'bootstrap', 'secrets-strategy'):
        if 'e1-final-acceptance.md' not in (root/f'terraform/docs/{name}.md').read_text(encoding='utf-8'):
            errors.append('KDD final contract missing: ' + name)
    return errors


if __name__ == '__main__':
    errors = check(ROOT)
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Current KDD links and immutable approved E1 contracts PASS')
