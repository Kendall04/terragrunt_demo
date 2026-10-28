"""Protected image entrypoint. SDK dependencies belong to the approved image.

No credentials are accepted in events/configuration. No dynamic adapter/plugin
selection. Worker runtimes never execute this module.
"""
import base64
from contextlib import nullcontext
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from e1_contract import CONTROLLERS, CORE_BUILD, CORE_FINALIZER, canonical, closed, digest, require, version

_installation = None


def installed(s3, reference):
    """Keep verified files alive for cached Python modules across warm invocations."""
    global _installation
    identity = canonical(reference)
    if _installation is None:
        directory = tempfile.TemporaryDirectory(prefix='e1-installed-')
        try:
            load_bundle(s3, reference, Path(directory.name))
        except Exception:
            directory.cleanup()
            raise
        _installation = identity, directory
    require(_installation[0] == identity)
    return Path(_installation[1].name)


def load_bundle(s3, reference, root):
    closed(reference, ('bucket','key','version_id','sha256','class','consumer'))
    require(reference['key'] == 'bundles/sha256/' + reference['sha256'] + '.json')
    response = s3.get_object(Bucket=reference['bucket'], Key=reference['key'], VersionId=version(reference['version_id']))
    raw = response['Body'].read(1048577)
    require(response.get('VersionId') == reference['version_id'] and digest(raw) == reference['sha256'])
    package = json.loads(raw)
    require(package['class'] == reference['class'] and reference['consumer'] in package['consumers'])
    for name, encoded in package['files'].items():
        parts = name.split('/')
        require(not any(p in ('', '.', '..') or ':' in p or '\\' in p for p in parts))
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(base64.b64decode(encoded, validate=True))
    return package


def config():
    value = json.loads(os.environ['E1_PROTECTED_CONFIGURATION'])
    closed(value, ('binding','account','region','bundle','runtime_image','support_sha256','evidence_bucket','exchange_bucket'))
    require(value['binding'] in CONTROLLERS)
    reference = value['bundle']
    require(reference['class'] + '/' + reference['consumer'] == value['binding'])
    expected = {'build/release': CORE_BUILD, 'qualification-finalizer/qualification': CORE_FINALIZER}
    if value['binding'] in expected:
        require(reference['sha256'] == expected[value['binding']])
    # Runtime source identity is independently pinned in admin configuration.
    files = ('e1_contract.py','exchange.py','publisher.py','workers.py','adapters.py','services.py','runtime.py','worker.py')
    source = canonical({name: digest((Path(__file__).parent / name).read_bytes().replace(b'\r\n', b'\n')) for name in files})
    require(digest(source) == value['support_sha256'])
    return value


def invoke(event):
    import boto3  # supplied by separately approved, immutable runtime image
    from botocore.config import Config
    c = config()
    # SigV4 binds the conditional output header; do not inherit S3 presign defaults.
    s3 = boto3.client('s3', region_name=c['region'], config=Config(signature_version='s3v4'))
    codebuild = boto3.client('codebuild', region_name=c['region'])
    with nullcontext(installed(s3, c['bundle'])) as temp:
        root = Path(temp)
        # Core dependencies are pinned into the protected runtime for gateway /
        # status, and are loaded from their accepted installed packages for build
        # and finalizer. No payload path is added to sys.path.
        sys.path[:0] = [str(root/'scripts/build_supervision'), str(root/'scripts/qualification')]
        from adapters import Store, Control, Records, Manifests, Source, Payload, Images, Exchange, Workers, supervisor, finalizer
        from services import Gateway, Evidence, Qualifications, status, wakeup
        operations = Store(s3, c['evidence_bucket'], 'operations/demo-api/')
        records = Records(Store(s3, c['evidence_bucket'], 'attempts/demo-api/'))
        manifests = Manifests(s3, c['evidence_bucket'])
        if c['binding'] == 'request-gateway/release':
            approvals = Store(s3, c['evidence_bucket'], 'source-approvals/demo-api/')
            def approved(commit):
                return approvals.read(commit + '.json') == canonical({'source_commit': commit, 'repository': 'Kendall04/terragrunt_demo'})
            return Gateway(codebuild, operations, c['account'], c['region'], approved).release(event)
        if c['binding'] == 'status/status-neutral':
            return status(event, operations, records)
        if c['binding'] == 'qualification-finalizer/qualification':
            evidence = Evidence(codebuild, operations, records, manifests)
            qualifications = Qualifications(Store(s3, c['evidence_bucket'], ''))
            record = finalizer.Finalizer(c['account'], c['region'], evidence, qualifications).finalize(
                wakeup(event, operations, c['account'], c['region']))
            public = {'operation_id':record['operation_id'],'state':'SUCCESS',
                      'release_id':record['release_id'],'source_commit':record['source_commit']}
            store = Store(s3,c['evidence_bucket'],'qualifications/demo-api/operations/')
            key = record['operation_id']+'/public.json'
            if store.read(key) is None:store.create(key,canonical(public))
            require(store.read(key)==canonical(public))
            return record
        require(event is None)
        outer = os.environ['CODEBUILD_BUILD_ID']
        from e1_contract import build_id
        build_id(outer, CONTROLLERS['build/release'][0])
        for _ in range(60):
            raw = operations.read('builds/' + outer + '.json')
            if raw is not None:
                break
            time.sleep(1)
        require(raw is not None)
        wake = finalizer.decode(raw)
        closed(wake, ('operation_id',))
        control = Control(operations)
        op = control.operation(wake['operation_id'])
        require(op['build_id'] == outer)
        context = {k: op[k] for k in supervisor.CONTEXT_KEYS}
        context.update(github_run_id='0', github_run_attempt='0',
            created_at=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            controller_image={'owner':'SECURITY_ROOT_OWNED','binding':'build/release',
                              'uri':c['runtime_image'],'approval':'ADMIN_VERIFIED'})
        workers = Workers(codebuild,c['account'],c['region'],'demo-shared-demo-ms',op['operation_id'])
        payload = Payload(Source(),workers,Exchange(s3,c['exchange_bucket'],op['operation_id']))
        registry = c['account'] + '.dkr.ecr.' + c['region'] + '.amazonaws.com'
        images = Images(boto3.client('ecr',region_name=c['region']),payload,registry,'demo-shared-demo-ms')
        result = supervisor.Supervisor(context,control,payload,images,manifests,records).run(wake)
        require(result['schema'] == 'E1_SUPERVISED_RESULT_V1' and result['state'] == 'SUCCEEDED')
        require(all(v == 'PASS' for v in result['checks'].values()))
        return {'state':'SUCCEEDED'}


def handler(event, context):
    try:
        return invoke(event)
    except Exception:
        raise RuntimeError('E1_INTERNAL_RELEASE_FAILED') from None


if __name__ == '__main__':
    try:
        invoke(None)
    except Exception:
        raise SystemExit('E1_INTERNAL_RELEASE_FAILED') from None
