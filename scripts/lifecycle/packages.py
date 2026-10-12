"""Deterministic WP5 packages and exact-version installation readback."""
import base64
import json
from pathlib import Path

from . import contract as c


def verify(s3, reference, destination):
    c.keys(reference, ('bucket', 'key', 'version_id', 'sha256', 'binding', 'source_commit'), 'package reference')
    c.require(reference['key'] == 'bundles/sha256/' + reference['sha256'] + '.json', 'content-addressed key')
    version = reference['version_id']
    c.require(type(version) is str and version.strip() == version and version.lower() not in ('', 'null', 'latest'), 'exact version')
    response = s3.get_object(Bucket=reference['bucket'], Key=reference['key'], VersionId=version)
    raw = response['Body'].read(16777217)
    c.require(len(raw) <= 16777216 and response.get('VersionId') == version and c.digest(raw) == reference['sha256'], 'exact readback bytes')
    package = json.loads(raw)
    c.keys(package, ('schema', 'binding', 'reservation', 'files'), 'closed package')
    c.require(package['schema'] == 'E1_WP5_PACKAGE_V1' and package['binding'] == reference['binding'], 'package binding')
    root = Path(destination).resolve()
    c.require(type(package['files']) is dict and bool(package['files']), 'package files')
    for name, encoded in package['files'].items():
        c.require(type(name) is str and all(part not in ('', '.', '..') and ':' not in part and '\\' not in part for part in name.split('/')), 'package path')
        target = root.joinpath(*name.split('/'))
        c.require(root in target.parents, 'package containment')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:stream.write(base64.b64decode(encoded, validate=True))
    # Privileged bootstrap must itself be the exact code inside the verified
    # package. An image with unrelated entrypoint bytes cannot borrow its hash.
    for name in ('contract.py', 'controller.py', 'packages.py', 'runtime.py', 'dev_down.py', 'exact_destroy.py', 'handoff.py', 'ecs_quiescence.py', 'quiescence.py', 'operational.py'):
        source = Path(__file__).with_name(name).read_bytes().replace(b'\r\n', b'\n')
        c.require((root/'scripts/lifecycle'/name).read_bytes() == source, 'installed bootstrap byte identity')
    source = Path(__file__).parents[1]/'environment_mutation.py'
    c.require((root/'scripts/environment_mutation.py').read_bytes() ==
              source.read_bytes().replace(b'\r\n',b'\n'), 'installed arbitration byte identity')
    for name in ('scripts/nat/quiescence.py', 'scripts/recovery/nat.py',
                 'scripts/recovery/journal.py', 'scripts/recovery/ports.py',
                 'scripts/wp4d/nat_resolver.py', 'scripts/normal_delivery/authorization.py',
                 'scripts/normal_delivery/delivery.py', 'scripts/normal_delivery/e3.py',
                 'scripts/normal_delivery/model_consistency.py', 'scripts/qualification/finalizer.py',
                 'ci/authority/normal-delivery-model.json', 'ci/schemas/release-manifest.schema.json',
                 'ci/schemas/e1-qualification.schema.json', 'demo-api/deploy/task-definition.template.json'):
        source = Path(__file__).resolve().parents[2] / name
        c.require((root/name).read_bytes() == source.read_bytes().replace(b'\r\n', b'\n'),
                  'installed combined dependency byte identity')
    return reference
