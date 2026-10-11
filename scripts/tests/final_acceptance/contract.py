"""WP7 final operational source closure; historical text grants no authority."""
import ast
import hashlib
import json
from pathlib import Path
import re


def require(value, reason):
    if not value:
        raise ValueError('E1_FINAL_ACCEPTANCE: ' + reason)


def retirement(root):
    root = Path(root)
    catalog = json.loads((root / 'ci/authority/retirement.json').read_text())
    legacy = json.loads((root / 'ci/authority/target/legacy-sources.json').read_text())
    require(catalog['schema'] == 'E1_WP7_RETIREMENT_V1', 'retirement schema')
    require(set(legacy['sources']) <= set(catalog['retired']), 'complete legacy accounting')
    for name, record in catalog['retired'].items():
        require(record['archive'] == 'ci/authority/retired/' + name + '.txt', 'inert archive path')
        raw = (root / record['archive']).read_bytes().replace(b'\r\n', b'\n')
        require(hashlib.sha256(raw).hexdigest() == record['sha256'], 'retired source drift: ' + name)
        if name not in ('scripts/bootstrap.sh', 'scripts/deploy.sh'):
            require(not (root / name).exists(), 'retired executable/configuration restored: ' + name)
        if name in legacy['sources']:
            require(record['sha256'] == legacy['sources'][name], 'immutable historical digest')
    for path in (root / 'ci/authority/retired').rglob('*'):
        require(not path.is_symlink(), 'linked retired source')
        if path.is_file():
            require(path.suffix == '.txt' and path.relative_to(root).as_posix() in
                    {v['archive'] for v in catalog['retired'].values()}, 'executable or unaccounted archive')
    for name in ('scripts/bootstrap.sh', 'scripts/deploy.sh'):
        text = (root / name).read_text()
        require('E1_LEGACY_PATH_RETIRED' in text and 'exit 1' in text, 'wrapper rejection')
        require(not re.search(r'\b(aws|terraform|terragrunt|exec|source)\b', text), 'wrapper mutation/fallback')
    text = (root / 'scripts/ecs-blue-green-deploy.sh').read_text()
    body = text.split('main() {', 1)[1].split('\n}', 1)[0]
    require(body.strip() == 'die "E1_LEGACY_PATH_RETIRED: use protected normal delivery or emergency recovery."',
            'standalone direct delivery restored')
    require(not list((root / '.github/actions').rglob('action.yml')), 'old action path')
    return catalog


def closed(root):
    import model
    from scripts.workflow_requests import render
    doc = model.validate_repository(root)
    retirement(root)
    for name, expected in render.render(root, doc['wp6']['approvals']).items():
        require((Path(root) / name).read_text() == expected, 'workflow invocation drift: ' + name)
    generated = set(render.render(root, doc['wp6']['approvals']))
    for path in (Path(root) / '.github/workflows').glob('*.yml'):
        if path.relative_to(root).as_posix() in generated:
            json.loads(path.read_text()) # Generated YAML is the JSON subset.
            continue
        text = path.read_text()
        require(not re.search(r'configure-aws-credentials|AWS_ROLE_|role-to-assume|id-token:\s*write|uses:\s*\./\.github/actions/aws-oidc|secrets:\s*inherit', text),
                'unprotected workflow acquisition: ' + path.name)
        commands = '\n'.join(line for line in text.splitlines() if '--generate-cli-skeleton' not in line)
        require(not re.search(r'\baws\s+(ecs|elbv2|ec2|iam|sts|lambda|codebuild)\s+', commands),
                'unprotected workflow API mutation/acquisition: ' + path.name)
    require(doc['wp6']['approvals'] == {}, 'external activation introduced')
    for kind, count in (('wp4d', 16), ('wp5', 8)):
        require(len(doc[kind]['selected']) == count, 'compute reservation count')
        for field in ('installations', 'runtime_approvals', 'environment_bindings'):
            require(doc[kind][field] == {}, 'compute activation introduced: ' + kind)
    return doc


def authority_inventory(root):
    """Complete final generated roots and protected JSON authority declarations.

    These are source contracts, including inactive expressions, not materialized
    AWS policy/readback evidence. No additional authority is authored here.
    """
    import model
    doc = model.validate_repository(root)
    generated = model.wiring(doc)
    declarations = {}
    for name, configuration in generated.items():
        if not isinstance(configuration, dict):
            continue
        for kind, entries in configuration.get('resource', {}).items():
            if kind.startswith(('aws_iam_', 'aws_kms_', 'aws_secretsmanager_')) or kind.endswith('_policy') or kind == 'aws_lambda_permission':
                for label, value in entries.items():
                    declarations[name + '#' + kind + '.' + label] = value
    return dict(classification='CLOSED_FINAL_TARGET_SOURCE_MODEL_NOT_LIVE_READBACK',
                request_identities=doc['request_identities'], ownership=doc['ownership'],
                protected_declarations=declarations,
                generated_root_sha256={name: hashlib.sha256((Path(root)/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                       for name in sorted(generated)},
                wp4d_bindings=doc['wp4d']['selected'], wp5_bindings=doc['wp5']['selected'],
                source_admission='model.validate_repository exact wiring plus immutable retired data and package admission')


def parse(root):
    """Parse all operational Python/JSON plus generated YAML, without execution."""
    from inventory import scan
    counts = dict(python=0, json=0, generated_yaml=0)
    names = set(scan(root))
    for directory in ('scripts/tests/authority', 'ci/authority'):
        names.update(p.relative_to(root).as_posix() for p in (Path(root)/directory).rglob('*')
                     if p.is_file() and p.suffix in ('.py', '.json'))
    for name in sorted(names):
        path = Path(root) / name
        text = path.read_text(encoding='utf-8-sig')
        if path.suffix == '.py':
            ast.parse(text, filename=name)
            counts['python'] += 1
        elif path.suffix == '.json':
            json.loads(text)
            counts['json'] += 1
        elif path.suffix in ('.yml', '.yaml') and text.lstrip().startswith('{'):
            json.loads(text)
            counts['generated_yaml'] += 1
    return counts
