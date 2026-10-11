"""Expand retired source text only inside disposable characterization fixtures.

Never use this root for E1 acceptance, Terraform or deployment. WP1's original
positive bypass witnesses remain regression evidence about the pre-E1 model.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import tempfile


@contextmanager
def source_root(root):
    root = Path(root)
    if (root / 'terraform/infra/shared/main.tf').exists():
        yield root
        return
    from inventory import scan
    with tempfile.TemporaryDirectory(prefix='e1-historical-characterization-') as directory:
        target = Path(directory)
        for name in scan(root):
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
