#!/usr/bin/env python3
"""Deterministic artifact build/inspection only; no publish, extraction or execution."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

from prepare import require


def digest(body):
    return hashlib.sha256(body).hexdigest()


BUNDLE_CONTRACT = 'RECOVERY_HOST_WITH_SERVICE_VALIDATORS_V2'
SERVICE_SUPPORT = (
    'scripts/workflow_requests/contract.py',
    'scripts/wp4d/gateway.py',
    'scripts/normal_delivery/delivery.py',
    'scripts/normal_delivery/model_consistency.py',
    'scripts/normal_delivery/e3.py',
    'scripts/normal_delivery/authorization.py',
    'scripts/qualification/finalizer.py',
    'ci/authority/normal-delivery-model.json',
    'ci/schemas/e1-qualification.schema.json',
    'demo-api/deploy/task-definition.template.json',
)


def runtime_sources():
    """Closed source-only dependency set; never includes approvals/credentials."""
    base = Path(__file__).resolve().parent
    root = base.parents[2]
    paths = {name: base / name for name in ('host.py', 'prepare.py', 'verify_effective.py', 'bootstrap.sh')}
    paths.update({name: root / name for name in SERVICE_SUPPORT})
    require(all(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents))
                for path in paths.values()), 'BUNDLE_RUNTIME_SOURCE_UNAVAILABLE')
    return {name: path.read_bytes() for name, path in paths.items()}


def inspect(path, expected, source_commit=None):
    require(path.stat().st_size <= 536870912 and digest(path.read_bytes()) == expected, 'BUNDLE_HASH_MISMATCH')
    found = {}
    total = 0
    with tarfile.open(path, 'r:') as archive:
        for item in archive:
            name = PurePosixPath(item.name)
            require(item.isfile() and not name.is_absolute() and '..' not in name.parts and str(name) == item.name and item.name not in found, 'UNSAFE_BUNDLE')
            require(item.mode in (0o644, 0o755) and item.size <= 536870912, 'BUNDLE_MODE_OR_SIZE')
            total += item.size
            require(total <= 500000000 and len(found) < 2000 and item.type in (tarfile.REGTYPE, tarfile.AREGTYPE), 'BUNDLE_EXPANSION_BOUND')
            found[item.name] = archive.extractfile(item).read()
    manifest = json.loads(found.pop('bundle-manifest.json'))
    require(set(found) == set(manifest['Files']), 'BUNDLE_INVENTORY_MISMATCH')
    require(manifest['Status'] == 'LOCAL_ARTIFACT_NOT_DEPLOYED' and manifest['Runtime'] == '10.0.13', 'BUNDLE_CONTRACT')
    for name, body in found.items():
        require(digest(body) == manifest['Files'][name]['Sha256'], 'BUNDLE_CONTENT_CHANGED')
    if source_commit is not None:
        require(manifest.get('SourceCommit') == source_commit, 'BUNDLE_SOURCE_COMMIT_MISMATCH')
        require(manifest.get('BundleContract') == BUNDLE_CONTRACT, 'BUNDLE_CURRENT_SOURCE_MISMATCH')
        sources = runtime_sources()
        nonbinary = {name for name in found if not name.startswith(('api/', 'backup/'))}
        require(nonbinary == set(sources) and all(
            found[name].replace(b'\r\n', b'\n') == body.replace(b'\r\n', b'\n')
            for name, body in sources.items()), 'BUNDLE_CURRENT_SOURCE_MISMATCH')
    return manifest


def build(api, backup, output, commit):
    import re
    require(re.fullmatch('[0-9a-f]{40}', commit), 'SOURCE_COMMIT_REQUIRED')
    require(not output.exists(), 'OUTPUT_EXISTS')
    files = {}
    for label, directory, executable in [('api', api, 'terragrunt-demo'), ('backup', backup, 'SqlBackup')]:
        require(directory.is_dir() and not any(p.is_symlink() for p in (directory, *directory.parents)), 'SAFE_PUBLISH_DIRECTORY_REQUIRED')
        require((directory / executable).is_file() and (directory / 'libcoreclr.so').is_file(), 'LINUX_SELF_CONTAINED_REQUIRED')
        runtime = json.loads((directory / (executable + '.runtimeconfig.json')).read_text())['runtimeOptions']
        frameworks = runtime.get('includedFrameworks', [])
        require(any(f.get('name') == 'Microsoft.NETCore.App' and f.get('version') == '10.0.13' for f in frameworks), 'PINNED_RUNTIME_REQUIRED')
        if label == 'api':
            require(any(f.get('name') == 'Microsoft.AspNetCore.App' and f.get('version') == '10.0.13' for f in frameworks), 'PINNED_WEB_RUNTIME_REQUIRED')
        for path in sorted(directory.rglob('*')):
            require(not path.is_symlink(), 'BUNDLE_SYMLINK_DENIED')
            if path.is_file():
                name = label + '/' + path.relative_to(directory).as_posix()
                files[name] = (path.read_bytes(), 0o755 if path.name == executable or path.suffix == '.so' else 0o644)
    for name, body in runtime_sources().items():
        files[name] = (body, 0o644)
    require(sum(len(body) for body, _ in files.values()) <= 500000000, 'BUNDLE_TOO_LARGE')
    manifest = {'Status': 'LOCAL_ARTIFACT_NOT_DEPLOYED', 'SourceCommit': commit, 'Runtime': '10.0.13',
                'BundleContract': BUNDLE_CONTRACT,
                'Files': {name: {'Sha256': digest(body), 'Bytes': len(body), 'Mode': mode} for name, (body, mode) in files.items()}}
    files['bundle-manifest.json'] = ((json.dumps(manifest, sort_keys=True) + '\n').encode(), 0o644)
    with tarfile.open(output, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, (body, mode) in sorted(files.items()):
            item = tarfile.TarInfo(name)
            item.size, item.mode, item.mtime, item.uid, item.gid = len(body), mode, 0, 0, 0
            archive.addfile(item, io.BytesIO(body))
    return {'Status': 'LOCAL_BUNDLE', 'Sha256': digest(output.read_bytes()), 'Files': len(manifest['Files']), 'CloudExecuted': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['build', 'inspect'])
    p.add_argument('--api', type=Path)
    p.add_argument('--backup', type=Path)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--commit')
    p.add_argument('--sha256')
    a = p.parse_args()
    try:
        print(json.dumps(build(a.api, a.backup, a.archive, a.commit) if a.action == 'build' else inspect(a.archive, a.sha256, source_commit=a.commit), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(json.dumps({'Status': 'REFUSED', 'Code': str(e) if type(e) is ValueError else type(e).__name__}))
        raise SystemExit(1)
