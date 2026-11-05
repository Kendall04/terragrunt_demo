"""Low-authority worker helper. Runs only inside subordinate workers.

Possession of its URLs/role and complete modification of this runtime are within
the threat model. This module never loads controller configuration or AWS SDKs.
"""
import base64
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.request


def source_path(name):
    # Deliberately standalone: the low-authority worker imports no controller.
    if type(name) is not str or len(name) > 1024:
        raise ValueError('source path')
    parts = name.split('/')
    projects = ('operations/sql-backup/SqlBackup', 'operations/sql-backup/SqlBackup.Tests')
    directories = ('operations', 'operations/sql-backup', *projects)
    files = ('.gitignore', 'global.json')
    if not (name in files or name in directories or parts[0] == 'demo-api' or
            any(name.startswith(p + '/') and len(parts) == 4 and
                (parts[-1] == 'packages.lock.json' or parts[-1].endswith(('.cs', '.csproj')))
                for p in projects)):
        raise ValueError('source path')
    for part in parts:
        if (not part or part in ('.', '..') or part.endswith(('.', ' ')) or
            any(ord(c) < 32 or c in '\\:<>"|?*' for c in part) or
            part.casefold() in ('bin', 'obj', '.git', 'secrets', '.aws') or
            re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',part,re.I)):
            raise ValueError('source path')
    if parts[-1].casefold().endswith(('.key', '.pfx', '.p12', '.env')):
        raise ValueError('source path')
    return directories, files, projects


def decode_source(raw):
    """Bounded node codec; filesystem writes stay inside a fresh worker root."""
    if type(raw) is not bytes or len(raw) > 96 * 1024 * 1024:
        raise ValueError('source size')
    nodes = json.loads(raw)
    if type(nodes) is not list or not 0 < len(nodes) <= 10000:
        raise ValueError('source nodes')
    names, total, checked = set(), 0, []
    for node in nodes:
        if type(node) is not list or len(node) != 4:
            raise ValueError('source node')
        name, kind, mode, content = node
        directories, files, projects = source_path(name)
        if name.casefold() in names or type(mode) is not int or type(content) is not str:
            raise ValueError('source node')
        names.add(name.casefold())
        data = base64.b64decode(content, validate=True)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError('source size')
        total += len(data)
        if total > 64 * 1024 * 1024:
            raise ValueError('source size')
        if kind == 'directory' and mode == 0 and not data:
            if name in files or any(name.startswith(p + '/') for p in projects):
                raise ValueError('source directory')
        elif kind == 'file' and mode in (0o644, 0o755):
            if name in directories or name == 'demo-api':
                raise ValueError('source file')
        else:
            raise ValueError('source node')
        checked.append((name, kind, mode, data))
    for name, kind, mode, data in checked:
        path = Path(name)
        for parent in (Path('.'), *reversed(path.parents[:-1])):
            info = parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
                raise ValueError('source parent')
        if kind == 'directory':
            path.mkdir(exist_ok=False)
        else:
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(mode)


def main(action):
    if action == 'source':
        url = os.environ['E1_SOURCE_URL']
        if not url.startswith('https://'):
            raise ValueError('source capability')
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read(96 * 1024 * 1024 + 1)
        if len(raw) > 96 * 1024 * 1024:
            raise ValueError('source size')
        decode_source(raw)
    elif action == 'output':
        url = os.environ['E1_OUTPUT_URL']
        if not url.startswith('https://'):
            raise ValueError('output capability')
        raw = Path('/tmp/e1-image.tar').read_bytes()
        if not 0 < len(raw) <= 1024 * 1024 * 1024:
            raise ValueError('archive size')
        request = urllib.request.Request(url, data=raw, method='PUT', headers={'If-None-Match': '*'})
        with urllib.request.urlopen(request, timeout=300) as response:
            if response.status != 200:
                raise ValueError('output upload')
    else:
        raise ValueError('worker action')


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception:
        raise SystemExit('E1_WORKER_FAILED') from None
