"""Run pinned static scanners and reject any change to reviewed historical debt.

No suppression, soft-fail or baseline-update mode. Raw reports stay outside Git.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
import re
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / '.github/scripts/ci/static-findings.json'
COMMANDS = {'tflint': ['tflint', '--recursive', '--format=json'],
            'tfsec': ['tfsec', '--no-color', '--format', 'json', '--minimum-severity=MEDIUM', '.']}


def identities(tool, document, root=ROOT):
    if tool == 'tflint':
        if document.get('errors') != []: raise ValueError('TFLint scanner errors')
        rows = document['issues']
    else:
        rows = document['results']
    if not isinstance(rows, list): raise ValueError('Invalid scanner report')
    result = []
    for row in rows:
        loc = row['range'] if tool == 'tflint' else row['location']
        name = loc['filename'].replace('\\', '/')
        if '/terraform/' in name: name = 'terraform/' + name.split('/terraform/', 1)[1]
        name = name.removeprefix('./')
        if not name.startswith('terraform/') or '..' in name.split('/'):
            raise ValueError('Finding outside Terraform source')
        start = loc['start']['line'] if tool == 'tflint' else loc['start_line']
        end = loc['end']['line'] if tool == 'tflint' else loc['end_line']
        source = (Path(root) / name).read_text(encoding='utf-8-sig').splitlines()
        if not 1 <= start <= end <= len(source): raise ValueError('Invalid source range')
        snippet = '\n'.join(line.strip() for line in source[start - 1:end]).encode()
        result.append(dict(rule=row['rule']['name'] if tool == 'tflint' else row['rule_id'],
            severity=row['rule']['severity'].upper() if tool == 'tflint' else row['severity'],
            file=name, resource='' if tool == 'tflint' else row['resource'],
            message=row['message'] if tool == 'tflint' else row['description'],
            source_sha256=hashlib.sha256(snippet).hexdigest()))
    return sorted(result, key=lambda value: json.dumps(value, sort_keys=True))


def compare(expected, actual):
    counts = lambda rows: Counter(json.dumps(v, sort_keys=True) for v in rows)
    before, after = counts(expected), counts(actual)
    return dict(added=sum((after - before).values()), removed=sum((before - after).values()))


def inspect(tool, code, raw, baseline, root=ROOT):
    if code not in ({0, 2} if tool == 'tflint' else {0, 1}):
        raise ValueError('Static scanner execution failed')
    actual = identities(tool, json.loads(raw), root)
    # A nonzero finding exit without findings cannot be accepted as success.
    if code and not actual: raise ValueError('Unexplained nonzero scanner exit')
    delta = compare(baseline['findings'][tool], actual)
    if any(delta.values()): raise ValueError(tool + ' historical finding drift: ' + str(delta))
    return len(actual)



def failure_diagnostics(tool, result):
    # Scanners inspect public source, not credentials. Export a bounded diagnostic
    # on failure; retain the complete original reports only in RUNNER_TEMP.
    text = (result.stderr + b'\n' + result.stdout).decode('utf-8', 'replace')
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
                  '[REDACTED_PRIVATE_KEY]', text, flags=re.S)
    text = re.sub(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', '[REDACTED_ACCESS_KEY]', text)
    text = re.sub(r'(?i)(aws_secret_access_key|aws_session_token|authorization|password)\s*[:=]\s*[^\r\n]+',
                  r'\1=[REDACTED]', text)
    return f'{tool} failed with exit {result.returncode}; full reports retained in RUNNER_TEMP\n' + text[:4096]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', choices=tuple(COMMANDS)); args = parser.parse_args(argv)
    baseline = json.loads(BASELINE.read_text())
    pins = json.loads((ROOT / '.github/scripts/ci/toolchain.json').read_text())['tools']
    if baseline['tool_versions'][args.tool] != pins[args.tool]['version']:
        raise ValueError('Scanner pin changed; review the baseline separately')
    result = subprocess.run(COMMANDS[args.tool], cwd=ROOT, capture_output=True, timeout=600)
    directory = Path(os.environ['RUNNER_TEMP']).resolve()
    if directory == ROOT or ROOT in directory.parents: raise ValueError('External report directory required')
    (directory / (args.tool + '-raw-findings.json')).write_bytes(result.stdout)
    (directory / (args.tool + '-scanner-stderr.log')).write_bytes(result.stderr)
    try:
        count = inspect(args.tool, result.returncode, result.stdout, baseline)
    except (ValueError, KeyError):
        print(failure_diagnostics(args.tool, result), file=sys.stderr)
        raise
    message = f'{args.tool}: {count} reviewed historical findings; identity/multiplicity/source unchanged; no suppressions'
    print(message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream: stream.write(message + '\n')


if __name__ == '__main__': main()
