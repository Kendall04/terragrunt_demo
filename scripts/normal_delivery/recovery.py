"""Opt-in WP4 recovery V2 contract. No SDK, IAM, installer or public entrypoint.

Only protected Facts.environment may supply a V2 binding. JSON hashes and writer
labels do not authenticate its provenance; the existing admin-only/current-read
adapter boundary remains mandatory. Fixtures prove consistency, not native SQL.
"""
import copy
import ipaddress
import json
from pathlib import Path

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.normal_delivery.e3 import Gate

PROFILE = json.loads((a.ROOT / 'ci/authority/recovery-profile-v2.json').read_text(encoding='utf-8'))
PROFILE_SHA256 = 'dff756555488f995b7c8daed1b20735ee904bfb24e91d6849fb32854ee8cd6f2'
V2_BINDING = 'E1_DELIVERY_BINDING_V2'
V2_INTENT = 'E1_AUTHORIZED_RUNTIME_INTENT_V2'
V2_OPERATION = 'E1_DELIVERY_OPERATION_V2'
PROFILE_NAME = 'SQL_RESTORE_NO_MIGRATIONS_V2'


def validate_profile():
    a.require(a.sha(a.canonical(PROFILE)) == PROFILE_SHA256)
    a.require(PROFILE['base_model_sha256'] == a.sha(a.canonical(a.MODEL))
              and PROFILE['base_runtime_contract'] == a.wp3.RUNTIME)


def base_binding(value, endpoint, account, region):
    a.require(type(value) is dict and value.get('schema') == V2_BINDING and 'recovery' in value)
    base = copy.deepcopy(value)
    base.pop('recovery')
    base['schema'] = 'E1_DELIVERY_BINDING_V1'
    return a.binding(base, endpoint, account, region)


def digest(value):
    a.match(r'[a-f0-9]{64}', value)


def epoch(value):
    a.require(type(value) is int and 0 < value < 2**53)


def validate_recovery(value, base, operation, now):
    validate_profile()
    a.require(base['environment'] == 'dev' and base['max_replicas'] <= 2)
    a.require(base['service']['platformVersion'] == '1.4.0')
    r = value['recovery']
    a.keys(r, ('profile', 'model_sha256', 'approval_id', 'writer', 'status',
               'operation_id', 'approved_at', 'expires_at', 'base_binding_sha256',
               'secret_version_id', 'evidence', 'evidence_sha256', 'allowed_releases'))
    a.require(r['profile'] == PROFILE_NAME and r['model_sha256'] == PROFILE_SHA256
              and r['writer'] == 'SECURITY_ADMIN' and r['status'] == 'APPROVED'
              and r['operation_id'] == operation
              and r['base_binding_sha256'] == a.sha(a.canonical(base)))
    d.identity(r['approval_id'])
    for timestamp in (now, r['approved_at'], r['expires_at']): epoch(timestamp)
    a.require(r['approved_at'] <= now < r['expires_at']
              and r['expires_at'] - r['approved_at'] <= PROFILE['maximum_approval_seconds'])
    a.match(r'[A-Za-z0-9-]{32,64}', r['secret_version_id'])
    e = r['evidence']
    a.keys(e, ('schema', 'writer', 'account', 'region', 'recovery_id',
               'source_instance_id', 'source_launch_epoch', 'source_state', 'source_terminated_at',
               'target_instance_id', 'target_launch_epoch', 'target_state', 'recovery_requested_at',
               'restore_started_at', 'restore_completed_at', 'observed_at', 'checkdb',
               'endpoint', 'vpc_id', 'db_subnet_id', 'db_security_group_id', 'task_security_groups',
               'source_fence_sha256', 'network_sha256', 'runtime_precheck_sha256',
               'connection_receipt_sha256', 'restored_schema_sha256',
               'secret_arn', 'secret_version_id', 'secret_key_arn'))
    a.require(e['schema'] == 'E1_SQL_RECOVERY_EVIDENCE_V2' and e['writer'] == 'RECOVERY_VERIFIER'
              and e['account'] == base['account'] and e['region'] == base['region']
              and e['source_state'] == 'terminated' and e['target_state'] == 'running'
              and e['checkdb'] == 'RESTORED_CHECKDB_READABLE')
    a.match(r'r[0-9]{8}[a-z0-9]{1,8}', e['recovery_id'])
    for key in ('source_instance_id', 'target_instance_id'): a.match(r'i-[a-f0-9]{17}', e[key])
    a.require(e['source_instance_id'] != e['target_instance_id'])
    times = [e[key] for key in ('source_launch_epoch', 'recovery_requested_at',
             'target_launch_epoch', 'restore_started_at', 'restore_completed_at', 'observed_at')]
    for timestamp in times + [e['source_terminated_at']]: epoch(timestamp)
    a.require(all(left <= right for left, right in zip(times, times[1:])))
    a.require(e['recovery_requested_at'] <= e['source_terminated_at'] <= e['restore_started_at'])
    a.require(0 <= r['approved_at'] - e['observed_at'] <= PROFILE['maximum_evidence_age_at_approval_seconds'])
    # Fresh at approval; expiry/current protected binding remain checked at every
    # reauthorization. This is not a live host/network observation or a lease.
    address = ipaddress.ip_address(e['endpoint'])
    a.require(address.version == 4 and str(address) == e['endpoint']
              and any(address in ipaddress.ip_network(c) for c in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')))
    for key, prefix in (('vpc_id','vpc'), ('db_subnet_id','subnet'), ('db_security_group_id','sg')):
        a.match(prefix + r'-[a-f0-9]{8,17}', e[key])
    groups = base['service']['networkConfiguration']['awsvpcConfiguration']['securityGroups']
    a.require(type(e['task_security_groups']) is list and len(groups) == 1)
    a.exact(e['task_security_groups'], sorted(groups), 'recovery.task_security_groups')
    a.require(e['db_security_group_id'] not in groups)
    for key in ('source_fence_sha256', 'network_sha256', 'runtime_precheck_sha256',
                'connection_receipt_sha256', 'restored_schema_sha256'): digest(e[key])
    a.require(e['secret_arn'] == base['secret_arn'] and e['secret_key_arn'] == base['kms_key_arn']
              and e['secret_version_id'] == r['secret_version_id']
              and r['evidence_sha256'] == a.sha(a.canonical(e)))
    releases = r['allowed_releases']
    a.require(type(releases) is list and 1 <= len(releases) <= 2)
    for release in releases:
        a.keys(release, ('release_id', 'image_uri', 'qualification_sha256', 'schema_sha256'))
        a.match(r'sha256-[a-f0-9]{64}', release['release_id'])
        a.match(r'[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9._/-]+@sha256:[a-f0-9]{64}', release['image_uri'])
        a.require(release['image_uri'].startswith(base['account']+'.dkr.ecr.'+base['region']+'.amazonaws.com/'))
        digest(release['qualification_sha256'])
        a.require(release['schema_sha256'] == e['restored_schema_sha256'])
    a.require(len({release['release_id'] for release in releases}) == len(releases))
    return copy.deepcopy(value)


def build_runtime(config, uri, replicas):
    base = base_binding(config, 'deploy-dev', config['account'], config['region'])
    task, service = a.runtime(base, uri, replicas)
    task['containerDefinitions'][0]['environment'].append(copy.deepcopy(PROFILE['app_environment_append']))
    task['containerDefinitions'][0]['secrets'][0]['valueFrom'] = base['secret_arn']+':::'+config['recovery']['secret_version_id']
    return task, service


def check_task_model(task, config, uri):
    validate_profile()
    base = base_binding(config, 'deploy-dev', config['account'], config['region'])
    normal = copy.deepcopy(task)
    app = normal['containerDefinitions'][0]
    a.exact(app['environment'][-1], PROFILE['app_environment_append'], 'recovery.migrations')
    app['environment'].pop()
    a.exact(app['secrets'], [{'name':'DB_CONN_STRING','valueFrom':base['secret_arn']+':::'+config['recovery']['secret_version_id']}], 'recovery.secret')
    app['secrets'][0]['valueFrom'] = base['secret_arn']
    a.validate_task_model(normal, base, uri)


class RecoveryAuthorizer(a.Authorizer):
    """Selected only by a separately reviewed protected installer, never a request."""
    intent_schema = V2_INTENT

    def __init__(self, endpoint, account, region, facts, *, operation_id, clock):
        super().__init__(endpoint, account, region, facts)
        a.require(endpoint == 'deploy-dev' and callable(clock))
        d.identity(operation_id)
        self.operation_id, self.clock = operation_id, clock

    def read_binding(self, observed):
        value = a.envelope(observed, 'endpoint', self.endpoint)
        base = base_binding(value, self.endpoint, self.account, self.region)
        return validate_recovery(value, base, self.operation_id, self.clock())

    def build_runtime(self, config, uri, replicas):
        return build_runtime(config, uri, replicas)

    def check_task_model(self, task, config, uri):
        check_task_model(task, config, uri)

    def intent_extension(self, config, q, uri):
        r = config['recovery']
        matches = [item for item in r['allowed_releases'] if item['release_id'] == q['release_id']]
        a.require(len(matches) == 1)
        selected = matches[0]
        a.require(selected['image_uri'] == uri and selected['qualification_sha256'] == a.sha(a.canonical(q)))
        return {'recovery':{'profile':PROFILE_NAME,'model_sha256':PROFILE_SHA256,
                'approval_id':r['approval_id'],'approval_sha256':a.sha(a.canonical(r)),
                'operation_id':self.operation_id,'evidence_sha256':r['evidence_sha256'],
                'restored_schema_sha256':r['evidence']['restored_schema_sha256']}}


class RecoveryDelivery(d.Delivery):
    """Same WP4B state machine/ports/E2/E3, with explicit V2 journal identity."""
    def __init__(self, authorizer, runtime, records, gate):
        a.require(type(authorizer) is RecoveryAuthorizer and isinstance(runtime,d.Runtime)
                  and isinstance(records,d.Records) and type(gate) is Gate)
        self.auth,self.runtime,self.records,self.gate = authorizer,runtime,records,gate
        self.env = 'dev'

    def operation_contract(self):
        return V2_OPERATION,V2_INTENT,super().operation_contract()[2]+('recovery',)

    def retained_operation(self, operation):
        retained = super().retained_operation(operation)
        if retained is None: return None
        try:
            proof = retained['intent']['recovery']
            a.keys(proof, ('profile','model_sha256','approval_id','approval_sha256',
                           'operation_id','evidence_sha256','restored_schema_sha256'))
            a.require(proof['profile'] == PROFILE_NAME and proof['model_sha256'] == PROFILE_SHA256
                      and proof['operation_id'] == operation == self.auth.operation_id)
            d.identity(proof['approval_id'])
            for key in ('approval_sha256','evidence_sha256','restored_schema_sha256'):digest(proof[key])
        except Exception:
            raise d.JournalError(operation+'/intent') from None
        return retained

    def accept(self, operation, raw):
        a.exact(operation,self.auth.operation_id,'recovery.operation')
        return super().accept(operation,raw)
