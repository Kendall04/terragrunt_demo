"""Internal gateway, independent finalizer evidence, and sanitized status.

No public HTTP endpoint. AWS clients and configuration come from the protected
runtime, never request JSON. Outer operation binding is gateway-owned.
"""
import json
import re
import uuid
from e1_contract import CONTROLLERS, build_id, canonical, closed, operation_id, require
from adapters import Store, finalizer


class Gateway:
    def __init__(self, codebuild, operations, account, region, approved_source):
        self.codebuild, self.operations = codebuild, operations
        self.account, self.region, self.approved_source = account, region, approved_source
    def release(self, request):
        closed(request, ('source_commit',))
        commit = request['source_commit']
        require(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit))
        # Approval comes from a protected source-governance reader.
        require(self.approved_source(commit) is True)
        identity = str(uuid.uuid4())
        project = CONTROLLERS['build/release'][0]
        intent = {'operation_id': identity, 'source_commit': commit,
                  'project': project, 'repository': 'Kendall04/terragrunt_demo',
                  'account': self.account, 'region': self.region}
        self.operations.create('intents/' + identity + '.json', canonical(intent))
        started = self.codebuild.start_build(projectName=project, idempotencyToken=identity)
        bound = build_id(started['build']['id'], project)
        require(started['build'].get('projectName') == project)
        op = dict(intent, schema='E1_RELEASE_OPERATION_V1', writer='RELEASE_GATEWAY', build_id=bound)
        finalizer.validate('operation', op)
        self.operations.create(identity + '.json', canonical(op))
        self.operations.create('builds/' + bound + '.json', canonical({'operation_id': identity}))
        require(self.operations.read(identity + '.json') == canonical(op))
        return {'operation_id': identity}


class Evidence(finalizer.Evidence):
    def __init__(self, codebuild, operations, records, manifests):
        self.codebuild, self.operations, self.records, self.manifests = codebuild, operations, records, manifests
        self.current = None
    def operation(self, identity):
        self.current = finalizer.validate('operation', finalizer.decode(
            self.operations.read(operation_id(identity) + '.json')))
        require(self.current['operation_id'] == identity)
        return self.current
    def build(self, identity):
        op = self.current
        require(op is not None and op['build_id'] == identity)
        build_id(identity, CONTROLLERS['build/release'][0])
        reverse = finalizer.decode(self.operations.read('builds/' + identity + '.json'))
        require(reverse == {'operation_id': op['operation_id']})
        response = self.codebuild.batch_get_builds(ids=[identity])
        require(not response.get('buildsNotFound') and len(response.get('builds', [])) == 1)
        b = response['builds'][0]
        require(b.get('id') == identity and b.get('projectName') == op['project'])
        require(b.get('buildComplete') is True and b.get('buildStatus') == 'SUCCEEDED')
        phases = b.get('phases', [])
        require(len({p['phaseType'] for p in phases}) == len(phases))
        require(any(p['phaseType'] == 'BUILD' and p.get('phaseStatus') == 'SUCCEEDED' for p in phases))
        require(all(p.get('phaseStatus') == 'SUCCEEDED' for p in phases if p['phaseType'] != 'COMPLETED'))
        # Fixed protected outer BUILD exits zero only after all seven checks and
        # exact persisted supervised result. Never copy checks from result JSON.
        common = {k: op[k] for k in ('operation_id','project','build_id','source_commit','account','region','repository')}
        return dict(common, schema='E1_BUILD_OBSERVATION_V1', state='SUCCEEDED',
                    checks=dict.fromkeys(finalizer.REQUIRED_CHECKS, 'PASS'))
    def result(self, identity, build):
        return finalizer.decode(self.records.read(identity + '/' + build))
    def manifest(self, bucket, key, version_id):
        result = self.manifests.read_exact(bucket, key, version_id)
        return {k: result[k] for k in ('bucket', 'key', 'version_id', 'bytes')}


class Qualifications(finalizer.Qualifications):
    def __init__(self, store):
        self.store = store
    def create(self, key, raw):
        require(re.fullmatch(r'qualifications/demo-api/sha256-[0-9a-f]{64}\.json', key))
        self.store.create(key, raw)
    def read(self, key):
        require(re.fullmatch(r'qualifications/demo-api/sha256-[0-9a-f]{64}\.json', key))
        return self.store.read(key)


def wakeup(event, operations, account, region):
    require(event.get('source') == 'aws.codebuild' and event.get('detail-type') == 'CodeBuild Build State Change')
    require(event.get('account') == account and event.get('region') == region)
    detail = event.get('detail', {})
    project = CONTROLLERS['build/release'][0]
    require(detail.get('project-name') == project and detail.get('build-status') in ('SUCCEEDED','FAILED','STOPPED'))
    arn = detail.get('build-id', '')
    prefix = 'arn:aws:codebuild:' + region + ':' + account + ':build/'
    require(arn.startswith(prefix))
    identity = build_id(arn[len(prefix):], project)
    result = finalizer.decode(operations.read('builds/' + identity + '.json'))
    closed(result, ('operation_id',))
    operation_id(result['operation_id'])
    return result


def status(request, operations, records):
    closed(request, ('operation_id',))
    identity = operation_id(request['operation_id'])
    result = {'operation_id': identity, 'state': 'UNKNOWN'}
    try:
        op = finalizer.validate('operation', finalizer.decode(operations.read(identity + '.json')))
        require(op['operation_id'] == identity)
        raw = records.read(identity + '/' + op['build_id'])
        if raw is None:
            return dict(result, state='INCOMPLETE')
        record = finalizer.decode(raw)
        require(all(record[k] == op[k] for k in ('operation_id','build_id','source_commit','project')))
        if record.get('schema') == 'E1_BUILD_ATTEMPT_TERMINAL_V1':
            from adapters import supervisor
            supervisor.validate_terminal(record)
            return dict(result, state='FAILED')
        finalizer.validate('result', record)
        require(all(record[k] == op[k] for k in ('operation_id','build_id','source_commit','project')))
        # Build completion is informational, never qualification/eligibility.
        return dict(result, state='BUILD_SUCCEEDED' if record['state'] == 'SUCCEEDED' else 'FAILED')
    except Exception:
        return result
