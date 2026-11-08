"""WP3A closed qualification logic. No AWS adapter, execution or IAM authority.

Ports/configuration are protected dependencies, never requester inputs. JSON
provenance fields are consistency constraints, not authentication. Adapters must
protect writer namespaces and return independently observed facts.
"""
from abc import ABC, abstractmethod
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'ci/schemas/e1-qualification.schema.json'
CONTRACT = json.loads(SCHEMA.read_text(encoding='utf-8'))['$defs']
REQUIRED_CHECKS = tuple(CONTRACT['checks']['required'])
RUNTIME = CONTRACT['result']['properties']['runtime_contract']['const']

class Rejected(ValueError):
    """Public diagnostics intentionally contain no input or transport details."""

def require(ok):
    if not ok:
        raise Rejected('E1_QUALIFICATION_REJECTED')

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')

def checksum(raw):
    return hashlib.sha256(raw).hexdigest()

def decode(raw):
    require(type(raw) is bytes and len(raw) <= 1048576)
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out)
            out[k] = v
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False))

def _validate(value, schema, definitions):
    if '$ref' in schema:
        return _validate(value, definitions[schema['$ref'].split('/')[-1]], definitions)
    if 'const' in schema: require(type(value) is type(schema['const']) and value == schema['const'])
    if 'enum' in schema: require(value in schema['enum'])
    kind = schema.get('type')
    if kind == 'object':
        require(type(value) is dict)
        require(set(schema.get('required', [])) <= set(value))
        require(not schema.get('additionalProperties') and set(value) <= set(schema['properties']))
        for k, v in value.items(): _validate(v, schema['properties'][k], definitions)
    elif kind == 'string':
        require(type(value) is str and len(value) <= schema.get('maxLength', 4096))
        require(len(value) >= schema.get('minLength', 0))
        if 'pattern' in schema: require(re.fullmatch(schema['pattern'], value) is not None)
    elif kind == 'integer': require(type(value) is int)

def validate(kind, value):
    definitions = CONTRACT
    _validate(value, definitions[kind], definitions)
    return copy.deepcopy(value)

class Evidence(ABC):
    """Authenticated protected reads. No method accepts evidence from a wakeup.

    Operation IDs are gateway-generated. The operation/build association is
    create-only and owned by the protected dispatcher, with reverse binding in
    the independent build observation. Results are supervisor-only, never
    application-writable. Manifest reads return exact requested version + bytes.
    """
    @abstractmethod
    def operation(self, operation_id): raise NotImplementedError
    @abstractmethod
    def build(self, build_id): raise NotImplementedError
    @abstractmethod
    def result(self, operation_id, build_id): raise NotImplementedError
    @abstractmethod
    def manifest(self, bucket, key, version_id): raise NotImplementedError

class Qualifications(ABC):
    """Finalizer-only namespace; atomic conditional create; exact bytes reads.

    create raises FileExistsError on conflict, other failures are not absence.
    No update/delete/eligibility-write operation. Deployment adapter authenticates
    the finalizer independently; subclassing or a writer string is not authority.
    """
    @abstractmethod
    def create(self, key, raw): raise NotImplementedError
    @abstractmethod
    def read(self, key): raise NotImplementedError

class Finalizer:
    def __init__(self, account, region, evidence, qualifications):
        require(re.fullmatch(r'[0-9]{12}', account) is not None)
        require(re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]', region) is not None)
        require(isinstance(evidence, Evidence) and isinstance(qualifications, Qualifications))
        # Derive protected names from the accepted canonical authority, never a
        # caller project, bucket, repository, runtime or installation selector.
        authority = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
        self.project = authority['controller_compute']['nodes']['build/release']['name']
        resources = authority['ownership_closure']['resources']
        self.repository = resources['neutral/repository']['name']
        self.bucket = resources['neutral/artifacts']['name'] + account
        self.account, self.region = account, region
        self.evidence, self.qualifications = evidence, qualifications

    def finalize(self, wakeup):
        try:
            return self._finalize(wakeup)
        except Exception:
            # Never propagate SDK/port errors or record values to public errors.
            raise Rejected('E1_QUALIFICATION_REJECTED') from None

    def _finalize(self, wakeup):
        validate('wakeup', wakeup)
        op = validate('operation', self.evidence.operation(wakeup['operation_id']))
        require(op['operation_id'] == wakeup['operation_id'])
        require(op['project'] == self.project and op['account'] == self.account and op['region'] == self.region)
        require(op['build_id'].startswith(self.project + ':'))
        build = validate('build', self.evidence.build(op['build_id']))
        result = validate('result', self.evidence.result(op['operation_id'], op['build_id']))
        for record in (build, result):
            for key in ('operation_id', 'build_id', 'project', 'source_commit', 'account', 'region', 'repository'):
                require(record[key] == op[key])
            require(record['state'] == 'SUCCEEDED')
            require(all(record['checks'][k] == 'PASS' for k in REQUIRED_CHECKS))
        require(result['checks'] == build['checks'])
        require(result['image_repository'] == self.repository)
        manifest = result['manifest']
        require(manifest['bucket'] == self.bucket)
        expected_key = 'releases/demo-api/by-digest/sha256-' + result['image_digest'][7:] + '.json'
        require(manifest['key'] == expected_key)
        receipt = self.evidence.manifest(manifest['bucket'], manifest['key'], manifest['version_id'])
        require(type(receipt) is dict and set(receipt) == {'bucket', 'key', 'version_id', 'bytes'})
        for key in ('bucket', 'key', 'version_id'): require(receipt[key] == manifest[key])
        require(type(receipt['bytes']) is bytes and checksum(receipt['bytes']) == manifest['sha256'])
        candidate = decode(receipt['bytes'])
        legacy = json.loads((ROOT / 'ci/schemas/release-manifest.schema.json').read_text())
        _validate(candidate, legacy, {})
        require(candidate['repository'] == op['repository'] and candidate['gitSha'] == op['source_commit'])
        require(candidate['sourceBranch'] == 'develop')
        registry = self.account + '.dkr.ecr.' + self.region + '.amazonaws.com'
        require(candidate['image']['registry'] == registry)
        require(candidate['image']['repository'] == self.repository)
        require(candidate['image']['digest'] == result['image_digest'])
        require(candidate['image']['uri'] == registry + '/' + self.repository + '@' + result['image_digest'])
        # Legacy quality never supplies missing supervised/authoritative checks.
        require(candidate['quality']['dotnetTests'] == candidate['quality']['dockerBuild'] == 'passed')
        record = {'schema': 'E1_QUALIFICATION_V1', 'writer': 'QUALIFICATION_FINALIZER',
                  'account': self.account, 'region': self.region, 'repository': op['repository'],
                  'source_commit': op['source_commit'], 'operation_id': op['operation_id'],
                  'project': op['project'], 'build_id': op['build_id'],
                  'image_repository': self.repository, 'image_digest': result['image_digest'],
                  'runtime_contract': RUNTIME, 'checks': result['checks'], 'manifest': manifest}
        record['release_id'] = 'sha256-' + checksum(canonical(record))
        validate('qualification', record)
        raw = canonical(record)
        key = 'qualifications/demo-api/' + record['release_id'] + '.json'
        try:
            self.qualifications.create(key, raw)
        except FileExistsError:
            pass
        # Also confirms successful persistence; a no-op write is not success.
        require(self.qualifications.read(key) == raw)
        return copy.deepcopy(record)

def validate_eligibility(record, release_id):
    """Schema consistency only, not authentication/currentness or delivery approval.

    Future consumer obtains the CURRENT admin-controlled registry through a
    trusted read adapter. Caller-authored JSON or an old version is not authority.
    This function neither publishes eligibility nor authorizes execution.
    """
    try:
        validate('eligibility', record)
        require(record['release_id'] == release_id)
        return copy.deepcopy(record)
    except Exception:
        raise Rejected('E1_ELIGIBILITY_REJECTED') from None
