"""Versioned operational record, not a distributed lease or mutation authority.

GitHub concurrency and externally fenced writers are prerequisites. A failed
operation is reconciled explicitly against current ECS, without borrowing E2.
"""
import json
from . import model as m


class State:
    def __init__(self, clients, config):
        self.s3 = clients['s3']; self.cfg = config
        self.key = f'api-delivery/{config["environment"]}/state.json'
        self.etag = None

    def read(self):
        # Installation creates this small state alongside the native baseline.
        # Missing/denied storage is never treated as an empty environment.
        response = self.s3.get_object(Bucket=self.cfg['evidence_bucket'], Key=self.key, ExpectedBucketOwner=self.cfg['account'])
        raw = response['Body'].read(262145)
        value = json.loads(raw)
        m.require(len(raw) <= 262144 and value['schema'] == 'API_STATE_V2' and
                  value['environment'] == self.cfg['environment'] and
                  response.get('VersionId') not in (None, 'null') and
                  value['phase'] in ('HEALTHY','DEPLOYING','RECONCILE'), 'operational state invalid')
        self.etag = response['ETag']
        return value

    def write(self, value):
        m.require(self.etag is not None, 'read state before write')
        raw = m.canonical(value)
        response = self.s3.put_object(Bucket=self.cfg['evidence_bucket'], Key=self.key, Body=raw, ContentType='application/json',
            IfMatch=self.etag, ServerSideEncryption='aws:kms', SSEKMSKeyId=self.cfg['evidence_kms_key'], BucketKeyEnabled=False)
        observed = self.read()
        m.require(observed == value and response.get('VersionId') not in (None, 'null'), 'state write requires reconciliation')


def handover(clients, config, reference, binding_hash):
    """A real administrator publishes this only after external writers are fenced.

    Reading an approved record is not a way to release the retained E2 head.
    No job can publish/change this record or its IAM/environment binding.
    """
    m.manifest_reference(reference)
    m.require(reference['bucket'] == config['evidence_bucket'] and
              reference['key'].startswith(f'api-delivery/{config["environment"]}/handover/'), 'handover scope')
    response = clients['s3'].get_object(Bucket=reference['bucket'], Key=reference['key'], VersionId=reference['version'], ExpectedBucketOwner=config['account'])
    raw = response['Body'].read(262145); value = json.loads(raw)
    m.require(len(raw) <= 262144 and m.sha(raw) == reference['sha256'] and response['VersionId'] == reference['version'] and
              value['schema'] == 'API_HANDOVER_V2' and value['status'] == 'APPROVED' and
              value['environment'] == config['environment'] and value['binding_sha256'] == binding_hash and
              value['external_writers_fenced'] is True and value['pending_effects_settled'] is True and
              all(value.get(k) for k in ('administrator','writer_controls','execution_termination','settled_effects')),
              'reviewed writer handover missing')
    if value.get('legacy_head'):
        legacy = value['legacy_head']
        m.require(legacy['key'] == f'arbitration/{config["environment"]}/application.json', 'legacy head scope')
        current = clients['s3'].get_object(Bucket=config['evidence_bucket'], Key=legacy['key'], ExpectedBucketOwner=config['account'])
        m.require(current['VersionId'] == legacy['version'] and current['ETag'] == legacy['etag'] and
                  m.sha(current['Body'].read(16385)) == legacy['sha256'], 'retired controller state changed; stop')
    return value
