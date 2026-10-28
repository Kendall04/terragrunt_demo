"""AWS-backed ports for the unchanged WP3B core and WP3A finalizer.

Clients are injected by the protected runtime; tests inject SDK response fixtures.
No application subprocess, Docker endpoint or worker credentials enter this process.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import urllib.parse

ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT / 'scripts/build_supervision'), str(ROOT / 'scripts/qualification')])
import supervisor
import finalizer
from e1_contract import build_id, canonical, digest, operation_id, require, version
from exchange import Exchange
from workers import Workers
import publisher


def error_code(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code')


class Store:
    def __init__(self, s3, bucket, prefix):
        self.client, self.bucket, self.prefix = s3, bucket, prefix

    def key(self, key):
        require(type(key) is str and len(key) <= 1024 and '..' not in key
                and not key.startswith('/') and '\\' not in key)
        return self.prefix + key

    def create(self, key, raw):
        require(type(raw) is bytes and len(raw) <= 1048576)
        try:
            response = self.client.put_object(Bucket=self.bucket, Key=self.key(key),
                Body=raw, IfNoneMatch='*', ChecksumSHA256=base64.b64encode(bytes.fromhex(digest(raw))).decode())
        except Exception as exc:
            if error_code(exc) == 'PreconditionFailed':
                raise FileExistsError() from None
            raise
        return version(response.get('VersionId'))

    def read(self, key):
        exact_key = self.key(key)
        # Without ListBucket S3 reports AccessDenied for absent keys. A bounded
        # exact-prefix lookup distinguishes absence without treating denial as
        # absence or granting whole-bucket enumeration.
        listing = self.client.list_objects_v2(Bucket=self.bucket, Prefix=exact_key, MaxKeys=1)
        entries = listing.get('Contents', [])
        require(type(entries) is list and len(entries) <= 1)
        if not entries or entries[0].get('Key') != exact_key:
            return None
        try:
            value = self.client.get_object(Bucket=self.bucket, Key=exact_key)
        except Exception as exc:
            if error_code(exc) == 'NoSuchKey':
                return None
            raise
        version(value.get('VersionId'))
        raw = value['Body'].read(1048577)
        require(len(raw) <= 1048576)
        return raw


class Records(supervisor.Records):
    def __init__(self, store):
        self.store = store
    def create(self, attempt, raw):
        self.store.create(attempt + '.json', raw)
    def read(self, attempt):
        return self.store.read(attempt + '.json')


class Control(supervisor.Control):
    def __init__(self, store):
        self.store = store
    def operation(self, identity):
        return finalizer.validate('operation', finalizer.decode(
            self.store.read(operation_id(identity) + '.json')))


class Manifests(supervisor.Manifests):
    def __init__(self, s3, bucket):
        self.s3, self.bucket = s3, bucket
        self.store = Store(s3, bucket, '')
    def create(self, attempt, bucket, key, raw):
        require(bucket == self.bucket and key.startswith('releases/demo-api/by-digest/sha256-'))
        try:
            exact = self.store.create(key, raw)
        except FileExistsError:
            head = self.s3.head_object(Bucket=bucket, Key=key)
            exact = version(head.get('VersionId'))
            require(self.read_exact(bucket, key, exact)['bytes'] == raw)
        return {'bucket': bucket, 'key': key, 'version_id': exact}
    def read_exact(self, bucket, key, version_id):
        require(bucket == self.bucket and key.startswith('releases/demo-api/by-digest/sha256-'))
        exact = version(version_id)
        response = self.s3.get_object(Bucket=bucket, Key=key, VersionId=exact)
        raw = response['Body'].read(1048577)
        require(response.get('VersionId') == exact and len(raw) <= 1048576)
        return {'bucket': bucket, 'key': key, 'version_id': exact, 'bytes': raw, 'sha256': digest(raw)}


class Source:
    """Public TLS source, with exact commit/tree and verified Git blob identities.

    Only commit/tree metadata uses the rate-limited REST API. File bytes come
    from the same repository's immutable raw commit paths and must hash to the
    selected tree's blob SHA. No hooks, archive extraction or application runs.
    Transport/rate failures stop acquisition; no tag/latest or retry fallback.
    """
    def __init__(self, fetch=None, fetch_blob=None):
        self.fetch = fetch or self._fetch
        self.fetch_blob = fetch_blob or self._fetch_blob
    @staticmethod
    def _fetch(path):
        request = urllib.request.Request('https://api.github.com/repos/Kendall04/terragrunt_demo/' + path,
                                         headers={'User-Agent': 'e1-protected-source', 'Accept': 'application/vnd.github+json'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read(24 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            status = error.code if type(error.code) is int and 100 <= error.code <= 599 else 0
            print(json.dumps({'diagnostic': 'E1_SOURCE_HTTP_FAILURE', 'transport': 'metadata',
                              'status': status}), file=sys.stderr)
            raise
        require(len(raw) <= 24 * 1024 * 1024)
        return json.loads(raw)
    @staticmethod
    def _fetch_blob(commit, name):
        # acquire() validates the commit and portable path before this read.
        url = ('https://raw.githubusercontent.com/Kendall04/terragrunt_demo/'
               + commit + '/' + urllib.parse.quote(name, safe='/'))
        request = urllib.request.Request(url, headers={'User-Agent': 'e1-protected-source'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            status = error.code if type(error.code) is int and 100 <= error.code <= 599 else 0
            print(json.dumps({'diagnostic': 'E1_SOURCE_HTTP_FAILURE', 'transport': 'raw-blob',
                              'status': status}), file=sys.stderr)
            raise
        require(len(raw) <= 16 * 1024 * 1024)
        return raw
    def acquire(self, repository, commit, workspace):
        require(repository == 'Kendall04/terragrunt_demo')
        import re
        require(re.fullmatch('[0-9a-f]{40}', commit) is not None)
        obj = self.fetch('git/commits/' + commit)
        require(obj['sha'] == commit)
        tree = self.fetch('git/trees/' + obj['tree']['sha'] + '?recursive=1')
        require(tree['sha'] == obj['tree']['sha'] and tree.get('truncated') is False)
        total = 0
        for entry in sorted(tree['tree'], key=lambda x: x['path']):
            name = entry['path']
            if not name.startswith('demo-api/'):
                continue
            supervisor.source_path(name)
            require(entry['type'] in ('blob', 'tree'))
            if entry['type'] == 'tree':
                continue
            require(entry['mode'] in ('100644', '100755'))
            raw = self.fetch_blob(commit, name)
            require(type(raw) is bytes and len(raw) <= 16 * 1024 * 1024)
            require(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['sha'])
            total += len(raw)
            require(total <= 64 * 1024 * 1024)
            path = Path(workspace) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)
            path.chmod(int(entry['mode'][-3:], 8))
        return {'repository': repository, 'commit': commit, 'workspace': workspace}


class Payload(supervisor.Payload):
    def __init__(self, source, workers, exchange):
        self.source, self.workers, self.exchange = source, workers, exchange
        self.dotnet = self.probes = None
        self.selected = {}
    def acquire(self, repository, commit, workspace):
        return self.source.acquire(repository, commit, workspace)
    def execute(self, stage, argv, workspace, env, image):
        if stage in supervisor.COMMANDS:
            require(argv == supervisor.COMMANDS[stage] and image is None)
            if self.dotnet is None:
                require(stage == 'dotnet_restore')
                source = self.exchange.source(supervisor.source_tree(workspace), 'dotnet')
                self.dotnet = self.workers.run('dotnet', {'SOURCE_URL': source})
            return self.workers.stage(self.dotnet, 'dotnet', stage)
        require(stage in ('probe_capability', 'probe_no_server'))
        if self.probes is None:
            require(stage == 'probe_capability')
            self.probes = self.workers.run('probe', image=image)
        return self.workers.stage(self.probes, 'probe', stage)
    def image_build(self, image_context, context, dockerfile, env):
        require(context == image_context + '/demo-api' and dockerfile == context + '/Dockerfile')
        source = self.exchange.source(supervisor.source_tree(image_context), 'image')
        run = self.workers.run('image', {'SOURCE_URL': source, 'OUTPUT_URL': self.exchange.output()})
        outcome = self.workers.stage(run, 'image', 'image_build')
        require(run[1]['builds'][0]['buildStatus'] == 'SUCCEEDED')
        require(outcome['state'] == 'COMPLETED' and outcome['exit_code'] == 0)
        selected = self.exchange.selected_output()
        publisher.oci(selected['bytes'])
        handle = selected['sha256']
        self.selected[handle] = selected
        return {'outcome': outcome, 'handle': handle}


class Images(supervisor.Images):
    def __init__(self, ecr, payload, registry, repository):
        self.ecr, self.payload, self.registry, self.repository = ecr, payload, registry, repository
    def publish(self, attempt, handle, registry, repository):
        require(registry == self.registry and repository == self.repository)
        raw = self.payload.selected[handle]['bytes']
        require(digest(raw) == handle)
        identity = publisher.publish(self.ecr, repository, raw)
        return {'attempt': attempt, 'handle': handle, 'registry': registry,
                'repository': repository, 'digest': identity}
