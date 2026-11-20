"""Current KDD links, immutable approved contracts and truthful status checks."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
# Approved IAM contracts and two authenticated diagram inputs retain dated links.
# Their hashes are still checked below; they are not reader-facing navigation.
IMMUTABLE_LINK_CONTEXT = {
    'specs/iam-hardening/spec.md', 'specs/iam-hardening/plan.md',
    'docs/V2-RECOVERY-SECURITY-20261105.md', 'docs/V2-TRUST-AND-THREATS.md',
}



def check(root):
    root = Path(root)
    errors = []
    provenance = json.loads((root/'docs/interactive/TRACEABILITY-CURRENT.json').read_text())
    frozen = {name: digest for name, digest in provenance['filesLfSha256'].items() if name.endswith('.md')}
    for name, digest in frozen.items():
        raw = (root/name).read_bytes().replace(b'\r\n', b'\n')
        if hashlib.sha256(raw).hexdigest() != digest:
            errors.append('diagram evidence changed: ' + name)
    documents = sorted(p.relative_to(root).as_posix() for p in root.rglob('*.md')
                       if not any(part in ('.git', '.terraform', 'node_modules', 'bin', 'obj') for part in p.relative_to(root).parts))
    for name in documents:
        if name in IMMUTABLE_LINK_CONTEXT:
            # Citations in authenticated dated documents resolve at their recorded Git revision.
            continue
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
