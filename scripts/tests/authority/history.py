"""Expand retired source text only inside disposable characterization fixtures.

Never use this root for E1 acceptance, Terraform or deployment. WP1's original
positive bypass witnesses remain regression evidence about the pre-E1 model.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


# These exact reviewed sources postdate the pre-E1 characterization.
# Exclude only their authenticated bytes from this disposable historical view;
# CURRENT discovery/inventory still includes them, as do unknown new JSON roots.
NON_BASELINE_REVIEW_INPUTS = {
    # This reviewed probe was added after the retired fixture; it remains in
    # current discovery and the exact supplemental source inventory.
    'operations/integrations/portable/trial/nat-observer.tf':
        'aaa53fe035cf7ecad31766ed30f2d6081c0cf96d44116fc8a745e1b3b30fb780',
    # Current discovery still sees the observer and its unresolved role expansion.
    # It cannot retroactively change the retired pre-E1 fixture.
    'operations/integrations/portable/trial/storage-observer.tf':
        '4b93f2fe36f9ec50c9d7047dc84eae8f7f33004c2f3f9fa445570f236da9aa90',
    'operations/integrations/ssm-diagnostic/review/bootstrap/main.tf.json':
        'edebf25f7532707ab79c99eb36a8c54d679ff2d42244c018ba14ea4b5cde3cd8',
    'operations/integrations/ssm-diagnostic/review/runtime/main.tf.json':
        'b19dd7078b7eda4a821b54fa881dbac2948f3ac3a83ef329c654fb7af80db1af',
}


def historical_inputs(root):
    from inventory import scan
    for name in scan(root):
        if name in NON_BASELINE_REVIEW_INPUTS:
            raw = (Path(root) / name).read_bytes().replace(b'\r\n', b'\n')
            if hashlib.sha256(raw).hexdigest() != NON_BASELINE_REVIEW_INPUTS[name]:
                raise ValueError('Historical review-input drift: ' + name)
            continue
        yield name


@contextmanager
def source_root(root):
    root = Path(root)
    if (root / 'terraform/infra/shared/main.tf').exists():
        yield root
        return
    from inventory import scan
    with tempfile.TemporaryDirectory(prefix='e1-historical-characterization-') as directory:
        target = Path(directory)
        for name in historical_inputs(root):
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, path)
        shutil.copytree(root / 'ci/authority', target / 'ci/authority', dirs_exist_ok=True)
        manifest = json.loads((root / 'ci/authority/target/legacy-sources.json').read_text())
        for name in manifest['sources']:
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / 'ci/authority/retired' / (name + '.txt'), path)
        inventory = json.loads((target / 'ci/authority/source-inventory.json').read_text())
        inventory['sources'] = {name: {**entry, 'semantic_status': 'UNVERIFIED'}
                                for name, entry in scan(target).items()}
        (target / 'ci/authority/source-inventory.json').write_text(json.dumps(inventory))
        yield target
