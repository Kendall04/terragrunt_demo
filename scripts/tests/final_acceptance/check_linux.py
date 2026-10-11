"""Optional existing Linux host checks, no installation or AWS.

Checks native YAML parsing and normalized disposable Bash syntax. A missing YAML
parser is unavailable, never a successful skip. Native E3 has its own entry point.
"""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def main():
    import yaml
    count = 0
    for path in (ROOT/'.github').rglob('*'):
        if path.suffix in ('.yml', '.yaml'):
            documents = list(yaml.safe_load_all(path.read_text(encoding='utf-8')))
            assert len(documents) == 1 and isinstance(documents[0], dict), path
            count += 1
    syntax = 0
    with tempfile.TemporaryDirectory(prefix='e1-bash-syntax-') as directory:
        for base in ('scripts', '.github/scripts'):
            for path in (ROOT/base).rglob('*.sh'):
                temporary = Path(directory)/'script.sh'
                temporary.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
                run = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-n', str(temporary)], capture_output=True)
                assert run.returncode == 0, (path, run.stderr)
                syntax += 1
    print(json.dumps({'yaml': count, 'bash_syntax': syntax, 'result': 'PASS', 'yaml_parser': yaml.__version__}))


if __name__ == '__main__':
    main()
