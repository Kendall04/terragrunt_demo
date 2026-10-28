"""Low-authority worker helper. Runs only inside subordinate workers.

Possession of its URLs/role and complete modification of this runtime are within
the threat model. This module never loads controller configuration or AWS SDKs.
"""
import base64
import json
import os
from pathlib import Path
import sys
import urllib.request


def main(action):
    if action == 'source':
        url = os.environ['E1_SOURCE_URL']
        if not url.startswith('https://'):
            raise ValueError('source capability')
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read(96 * 1024 * 1024 + 1)
        if len(raw) > 96 * 1024 * 1024:
            raise ValueError('source size')
        nodes = json.loads(raw)
        for name, kind, mode, content in nodes:
            parts = name.split('/')
            if parts[0] != 'demo-api' or any(p in ('', '.', '..') or '\\' in p or ':' in p for p in parts):
                raise ValueError('source path')
            path = Path(name)
            if kind == 'directory':
                path.mkdir(exist_ok=False)
            elif kind == 'file' and mode in (0o644, 0o755):
                with path.open('xb') as stream:
                    stream.write(base64.b64decode(content, validate=True))
                path.chmod(mode)
            else:
                raise ValueError('source node')
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
