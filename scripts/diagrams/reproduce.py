"""Reproduce frozen Archify artifacts using a supplied, authenticated local tool.

No tool install/download, no AWS, no Git writes. Existing source/expected hashes
must match before rendering. A changed candidate requires a fresh reviewed receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tool-zip', type=Path, required=True)
    parser.add_argument('--tool-root', type=Path, required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/interactive/GENERATION-V2.json').read_text(encoding='utf-8'))
    if digest(args.tool_zip.read_bytes()) != manifest['tool']['zip_sha256']:
        raise SystemExit('Official tool ZIP identity mismatch')
    with zipfile.ZipFile(args.tool_zip) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            parts = Path(entry.filename).parts
            if '..' in parts or parts[0] != 'archify':
                raise SystemExit('Unexpected tool archive path')
            local = args.tool_root.joinpath(*parts[1:])
            if not local.is_file() or digest(local.read_bytes()) != digest(archive.read(entry)):
                raise SystemExit('Extracted official tool changed: ' + entry.filename)
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    results = []
    for item in manifest['diagrams']:
        if digest((ROOT / item['source']).read_bytes()) != item['sourceSha256']:
            raise SystemExit('Source changed: new review required for ' + item['id'])
        output_dir = args.evidence_dir / item['id']
        command = [args.node, str(args.tool_root / 'bin/archify.mjs'), 'finalize', item['type'],
                   item['source'], item['output'], '--repo-root', str(ROOT), '--quality', 'showcase',
                   '--out-dir', str(output_dir), '--json']
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
        (args.evidence_dir / (item['id'] + '.stdout.json')).write_bytes(result.stdout)
        (args.evidence_dir / (item['id'] + '.stderr.txt')).write_bytes(result.stderr)
        if result.returncode:
            raise SystemExit('Archify failed: inspect ' + str(output_dir))
        receipt = json.loads((output_dir / (item['id'] + '.finalize-summary.json')).read_text(encoding='utf-8'))
        actual = digest((ROOT / item['output']).read_bytes())
        if not receipt['ok'] or actual != item['htmlSha256']:
            raise SystemExit('Artifact is not byte-reproducible: ' + item['id'])
        results.append({'id': item['id'], 'htmlSha256': actual, 'gates': receipt['gates'], 'byteIdentical': True})
        print(item['id'] + ' byte-identical PASS', flush=True)
    (args.evidence_dir / 'REPRODUCTION.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
