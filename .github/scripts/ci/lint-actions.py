"""Bridge one documented GitHub feature not parsed by pinned actionlint 1.7.12.

Validate queue:max ourselves in the sole reviewed executor, then lint every
workflow in a temporary copy with only that key omitted. Never filter diagnostics,
disable syntax checks, mutate sources or accept arbitrary new concurrency keys.
Remove this bridge when the pinned upstream release supports concurrency.queue.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate workflow field: ' + key)
        result[key] = value
    return result


def normalize(raw):
    value = json.loads(raw, object_pairs_hook=unique)
    concurrency = value['jobs']['delivery']['concurrency']
    if (concurrency.get('queue') != 'max' or concurrency.get('cancel-in-progress') is not False or
            set(concurrency) != {'group', 'queue', 'cancel-in-progress'}):
        raise ValueError('reviewed executor requires bounded native queue and no cancellation')
    del concurrency['queue']
    return json.dumps(value, indent=2) + '\n'


def main():
    with tempfile.TemporaryDirectory(prefix='actionlint-queue-') as temporary:
        target = Path(temporary)
        shutil.copytree(ROOT/'.github', target/'.github')
        (target/'.git').mkdir()  # Project discovery only; no Git operations.
        executor = target/'.github/workflows/api-execute.yml'
        executor.write_text(normalize(executor.read_text(encoding='utf-8')), encoding='utf-8')
        workflows = sorted(str(p.relative_to(target)) for p in (target/'.github/workflows').iterdir()
                           if p.is_file() and p.suffix in ('.yml', '.yaml'))
        subprocess.run(['actionlint', *workflows], cwd=target, check=True)


if __name__ == '__main__':
    main()
