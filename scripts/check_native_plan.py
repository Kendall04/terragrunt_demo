"""Optional offline review of native DEV plan JSON. No executor or approval authority.

Terraform owns planning, locking and apply. This reads original declarations and
the private output of `terraform show -json`; it never executes a process, reads
credentials, writes a receipt or authorizes apply. Inspect AWS IDs/state separately.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.lifecycle.contract import PROTECTED_TYPES, RUNTIME_FIELDS, EXECUTION_FIELDS

LAYERS = ('global', 'data', 'platform', 'apps', 'edge')


def require(ok, reason):
    if not ok:
        raise ValueError('NATIVE_PLAN_REJECTED: ' + reason)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'nonfinite JSON'))


def declarations(layer):
    require(layer in LAYERS, 'original DEV runtime root only')
    base = ROOT/'terraform/modules/target/dev'/layer
    found = {}

    def walk(directory, prefix=''):
        require(directory.resolve().is_relative_to(base.resolve()), 'foreign module source')
        for file in sorted(directory.glob('*.tf*')):
            if file.name.endswith('.tf.json'):
                value = decode(file.read_bytes())
                for mode in ('resource', 'data'):
                    for kind, names in value.get(mode, {}).items():
                        for name in names:
                            found[prefix+('data.' if mode == 'data' else '')+kind+'.'+name] = kind
                modules = [(name, attrs['source']) for name, attrs in value.get('module', {}).items()]
            elif file.suffix == '.tf':
                text = file.read_text(encoding='utf-8')
                for mode, kind, name in re.findall(r'^\s*(resource|data)\s+"([^"]+)"\s+"([^"]+)"', text, re.M):
                    found[prefix+('data.' if mode == 'data' else '')+kind+'.'+name] = kind
                modules = re.findall(r'module\s+"([^"]+)"\s*\{\s*source\s*=\s*"([^"]+)"', text)
            else:
                continue
            for name, source in modules:
                require(source.startswith('./modules/'), 'original local modules only')
                walk(directory/source, prefix+'module.'+name+'.')
    walk(base)
    return found


def review(plan, layer, direction, account, region, network_only=False):
    require(type(plan) is dict, 'plan object required')
    require(layer in LAYERS and direction in ('up', 'down'), 'layer/direction')
    require(bool(re.fullmatch(r'[0-9]{12}', account)) and bool(re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]', region)), 'explicit account/region')
    require(not network_only or (layer == 'global' and direction == 'up'), 'network bootstrap scope')
    require(plan.get('format_version') == '1.2' and plan.get('terraform_version') == '1.13.4', 'reviewed Terraform/plan format')
    require(plan.get('errored') is False and plan.get('applyable') is True and plan.get('complete') is True and not plan.get('deferred_changes'), 'complete applicable native plan required')
    require(not plan.get('resource_drift'), 'drift requires separate reconciliation')
    expected = declarations(layer)
    counts = Counter()
    seen = set()
    changes = plan.get('resource_changes')
    require(type(changes) is list and bool(changes), 'resource changes required')
    for row in changes:
        address, kind = row['address'], row['type']
        normal = re.sub(r'\[[^\]]*\]', '', address)
        require(address not in seen and expected.get(normal) == kind and not row.get('previous_address'), 'foreign/duplicate/moved address')
        require(('.data.' in '.'+normal) == (row.get('mode') == 'data'), 'resource mode/address mismatch')
        seen.add(address)
        actions = row['change']['actions']
        if row.get('mode') == 'data':
            require('.data.' in '.'+normal and actions in (['read'], ['no-op']), 'data read only')
            continue
        require(row.get('mode') == 'managed' and not kind.startswith(PROTECTED_TYPES), 'protected resource')
        require(actions in ((['create'], ['update'], ['no-op']) if direction == 'up' else (['delete'], ['no-op'])), 'replacement or action outside reviewed direction')
        require(not network_only or kind not in ('aws_autoscaling_group', 'aws_instance'), 'compute in network bootstrap')
        for attrs in (row['change'].get('before'), row['change'].get('after')):
            if attrs is None:
                continue
            require(type(attrs) is dict, 'resource value object required')
            tags = attrs.get('tags_all') or attrs.get('tags')
            if tags:
                require(tags.get('Environment') == 'dev' and tags.get('Project') == 'demo', 'foreign project/environment')
            if kind == 'aws_autoscaling_group':
                tags = {v['key']: v['value'] for v in attrs.get('tag', [])}
                require(tags.get('Environment') == 'dev' and tags.get('Project', 'demo') == 'demo', 'foreign ASG')
                require(address.endswith(('["a"]', '["b"]')), 'foreign NAT slot')
            arn = attrs.get('arn')
            if arn:
                fields = arn.split(':', 5)
                require(len(fields) == 6 and fields[0] == 'arn' and fields[3] == region and fields[4] == account, 'foreign resource ARN')
            if kind == 'aws_lb':
                require(attrs.get('internal') is True, 'public load balancer')
        before, after = row['change'].get('before'), row['change'].get('after')
        if actions == ['create'] and kind == 'aws_ecs_service':
            require(after.get('desired_count') == 0, 'WP4 owns task count')
        if actions == ['update']:
            require(before is not None and after is not None, 'update shape')
            for field in RUNTIME_FIELDS.get(kind, ()) + EXECUTION_FIELDS.get(kind, ()):
                require(before.get(field) == after.get(field), 'delivery/launch field ownership')
        counts[kind+':'+','.join(actions)] += 1
    return dict(status='REVIEW_REQUIRED_NOT_AUTHORIZED', resources=dict(sorted(counts.items())),
                aws_verified=False, limitation='Verify native state, IDs, dependencies, IAM, source and binary hash; obtain explicit owner approval. This tool cannot authorize or execute apply.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-json', type=Path, required=True)
    parser.add_argument('--layer', choices=LAYERS, required=True)
    parser.add_argument('--direction', choices=('up', 'down'), required=True)
    parser.add_argument('--account', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--network-only', action='store_true')
    args = parser.parse_args(argv)
    value = review(decode(args.plan_json.read_bytes()), args.layer, args.direction,
                   args.account, args.region, args.network_only)
    print(json.dumps(value))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        raise SystemExit('NATIVE_PLAN_REJECTED: preserve private diagnostics; no execution authorized') from None
