"""Install reviewed Linux/amd64 CI tools; checksum before unpacking or use.

Network/download/write entry point for CI only. Import and --check are offline.
No sudo, provider initialization, AWS, package manager or tool execution.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile
import zipfile

MANIFEST = Path(__file__).with_name('toolchain.json')
REPOSITORIES = {'terragrunt': 'gruntwork-io/terragrunt', 'tflint': 'terraform-linters/tflint',
                'tfsec': 'aquasecurity/tfsec', 'actionlint': 'rhysd/actionlint',
                'shellcheck': 'koalaman/shellcheck'}


def identity(name, version):
    """Supported artifact/checksum relationship, permitting reviewed versions."""
    if name == 'terraform':
        base = f'https://releases.hashicorp.com/terraform/{version}/'
        return (base + f'terraform_{version}_linux_amd64.zip',
                base + f'terraform_{version}_SHA256SUMS', 'zip', 'terraform', 'UPSTREAM_CHECKSUM_MANIFEST')
    base = f'https://github.com/{REPOSITORIES[name]}/releases/download/v{version}/'
    archive, checksum, format_, member = {
        'terragrunt': ('terragrunt_linux_amd64', 'SHA256SUMS', 'binary', None),
        'tflint': ('tflint_linux_amd64.zip', 'checksums.txt', 'zip', 'tflint'),
        'tfsec': (f'tfsec_{version}_linux_amd64.tar.gz', f'tfsec_{version}_checksums.txt', 'tar.gz', 'tfsec'),
        'actionlint': (f'actionlint_{version}_linux_amd64.tar.gz', f'actionlint_{version}_checksums.txt', 'tar.gz', 'actionlint'),
        'shellcheck': (f'shellcheck-v{version}.linux.x86_64.tar.gz', None, 'tar.gz', f'shellcheck-v{version}/shellcheck')
    }[name]
    evidence = base + checksum if checksum else f'https://api.github.com/repos/{REPOSITORIES[name]}/releases/tags/v{version}'
    method = 'UPSTREAM_CHECKSUM_MANIFEST' if checksum else 'UPSTREAM_RELEASE_ASSET_DIGEST'
    return base + archive, evidence, format_, member, method


def validate(doc):
    if doc['schema'] != 'E14B_CI_TOOLCHAIN_V1' or doc['platform'] != 'linux_amd64':
        raise ValueError('Unsupported toolchain schema/platform')
    if set(doc['tools']) != set(REPOSITORIES) | {'terraform'}:
        raise ValueError('Explicit reviewed tool set required')
    for name, item in doc['tools'].items():
        if not re.fullmatch(r'[a-z]+', name) or not re.fullmatch(r'\d+\.\d+\.\d+', item['version']):
            raise ValueError('Exact tool name/version required')
        if not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or item['sha256'] == '0' * 64:
            raise ValueError('Reviewed SHA-256 required')
        if item['verification'] not in ('UPSTREAM_CHECKSUM_MANIFEST', 'UPSTREAM_RELEASE_ASSET_DIGEST'):
            raise ValueError('Unverified download cannot be installed')
        for key in ('url', 'evidence_url'):
            version = item['version']
            prefixes = (f'https://releases.hashicorp.com/terraform/{version}/',) if name == 'terraform' else (
                f'https://github.com/{REPOSITORIES[name]}/releases/download/v{version}/',
                f'https://api.github.com/repos/{REPOSITORIES[name]}/releases/tags/v{version}')
            if not item[key].startswith(prefixes):
                raise ValueError('Official HTTPS source required')
            if item['version'] not in item[key] or '/latest' in item[key]:
                raise ValueError('Version-bound upstream URL required')
        if item['format'] not in ('binary', 'zip', 'tar.gz'):
            raise ValueError('Unsupported artifact format')
        if item['format'] != 'binary' and not item.get('member'):
            raise ValueError('Exact archive member required')
        if tuple(item.get(key) for key in ('url', 'evidence_url', 'format', 'member', 'verification')) != identity(name, item['version']):
            raise ValueError('Supported artifact/checksum/member relationship required')
    for reference, tag in doc['actions'].items():
        if not re.fullmatch(r'[\w-]+/[\w-]+@[0-9a-f]{40}', reference) or not re.fullmatch(r'v\d+(\.\d+){0,2}', tag):
            raise ValueError('Verified immutable action identity required')
    for reference, item in doc['deferred_actions'].items():
        if item['status'] != 'MUTABLE_REFERENCE_RETAINED' or reference in doc['actions']:
            raise ValueError('Deferred reference cannot be marked verified')
    return doc


def verified_binary(raw, item):
    """No archive bytes are interpreted until their repository pin matches."""
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('Upstream artifact checksum mismatch')
    if item['format'] == 'binary':
        return raw
    if item['format'] == 'zip':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.namelist().count(item['member']) != 1:
                raise ValueError('Unique archive member required')
            return archive.read(item['member'])
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        if archive.getnames().count(item['member']) != 1:
            raise ValueError('Unique archive member required')
        member = archive.getmember(item['member'])
        if not member.isfile():
            raise ValueError('Archive member must be a regular file')
        return archive.extractfile(member).read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tools', nargs='*')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    doc = validate(json.loads(MANIFEST.read_text()))
    if args.check:
        print('E14-B exact versions and version-bound checksum provenance PASS')
        return
    if not args.tools or any(name not in doc['tools'] for name in args.tools):
        raise ValueError('Choose only manifest tools')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        raise ValueError('Supported installer host is Linux/amd64')
    destination = Path(os.environ['RUNNER_TEMP']).resolve() / 'e14-tools' / 'bin'
    if '\n' in str(destination) or '\r' in str(destination):
        raise ValueError('Invalid runner path')
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='e14-download-', dir=os.environ['RUNNER_TEMP']) as tmp:
        for name in args.tools:
            item = doc['tools'][name]
            artifact = Path(tmp) / 'artifact'
            subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                            '--proto', '=https', '--proto-redir', '=https', '--retry', '3',
                            '--connect-timeout', '20', '--max-time', '300',
                            item['url'], '--output', str(artifact)], check=True)
            binary = verified_binary(artifact.read_bytes(), item)
            target = destination / name
            target.write_bytes(binary)
            target.chmod(0o755)
            print(f"Installed {name} {item['version']} with reviewed SHA-256")
    with open(os.environ['GITHUB_PATH'], 'a') as stream:
        stream.write(str(destination) + '\n')


if __name__ == '__main__':
    main()
