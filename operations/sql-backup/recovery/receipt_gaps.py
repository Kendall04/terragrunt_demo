#!/usr/bin/env python3
"""Read-only historical gap projection. Never a V2 evidence/approval writer."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare import ACCOUNT, REGION, encoded, require, trial
from host import event_order

# Names from the existing validate_recovery evidence object, not a new contract.
# A drift test compares this list with that original validator's closed tuple.
V2_FIELDS = ('schema','writer','account','region','recovery_id','source_instance_id',
 'source_launch_epoch','source_state','source_terminated_at','target_instance_id',
 'target_launch_epoch','target_state','recovery_requested_at','restore_started_at',
 'restore_completed_at','observed_at','checkdb','endpoint','vpc_id','db_subnet_id',
 'db_security_group_id','task_security_groups','source_fence_sha256','network_sha256',
 'runtime_precheck_sha256','connection_receipt_sha256','restored_schema_sha256',
 'secret_arn','secret_version_id','secret_key_arn')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key,value in pairs:
        require(key not in result, 'DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def parse(raw, expected):
    require(type(raw) is bytes and 0 < len(raw) <= 1048576, 'RECEIPT_SIZE_INVALID')
    require(type(expected) is str and re.fullmatch('[a-f0-9]{64}',expected)
            and sha(raw) == expected, 'RECEIPT_PIN_MISMATCH')
    record = json.loads(raw, object_pairs_hook=unique,
                        parse_constant=lambda _: require(False,'NONFINITE_JSON'))
    require(type(record) is dict and record.get('Outcome') == 'HOST_ACTION_COMPLETE'
            and record.get('SsmStatus') == 'Success' and type(record.get('ResponseCode')) is int
            and record['ResponseCode'] == 0, 'HOST_COMPLETION_NOT_CONFIRMED')
    result = record.get('Result',{})
    require(type(result) is dict and result.get('Status') == 'HOST_ACTION_COMPLETE'
            and type(result.get('Receipt')) is dict, 'HOST_RECEIPT_MISSING')
    # Original host.private_write: indent=2, original key order, no trailing LF.
    # This only checks retained bytes/consistency; neither pin authenticates AWS.
    receipt = result['Receipt']
    require(result.get('ReceiptSha256') == sha(json.dumps(receipt,indent=2).encode()),
            'EMBEDDED_RECEIPT_HASH_MISMATCH')
    require(trial(record.get('Trial')) == receipt.get('Trial'), 'TRIAL_MISMATCH')
    return record, receipt


def project(inputs, pins):
    """Only recognized az6-style receipts; no network, clock or approval input."""
    require(type(inputs) is dict and type(pins) is dict
            and set(inputs) == set(pins) == {'source','quiesce','restore'}, 'EXACT_INPUT_SET_REQUIRED')
    parsed = {name:parse(inputs[name],pins[name]) for name in inputs}
    source_outer,source = parsed['source']; quiet_outer,quiet = parsed['quiesce']; restore_outer,restored = parsed['restore']
    require(source.get('Status') == 'SOURCE_BACKED_UP'
            and restored.get('Status') == 'TARGET_RECOVERED_REVIEW_EVIDENCE'
            and quiet.get('ActiveState') == 'inactive', 'HISTORICAL_ACTION_STATUS_MISMATCH')
    require(source_outer['Result'].get('Action') in ('source','source-resume1')
            and quiet_outer['Result'].get('Action') == 'quiesce'
            and restore_outer['Result'].get('Action') in ('restore','restore-resume1'), 'ACTION_MISMATCH')
    require(source['Trial'] == quiet['Trial'] == restored['Trial'], 'TRIAL_MISMATCH')
    old,new = source['Source'],restored['Target']
    require(all(type(i) is dict and i.get('accountId') == ACCOUNT and i.get('region') == REGION
                and re.fullmatch('i-[a-f0-9]{17}',i.get('instanceId',''))
                and re.fullmatch(REGION+'[a-f]',i.get('availabilityZone',''))
                for i in (old,new)), 'HISTORICAL_IDENTITY_INVALID')
    require(all(restored['Source'].get(k) == old[k] for k in
                ('accountId','region','instanceId','availabilityZone'))
            and old['instanceId'] != new['instanceId']
            and quiet['SourceInstanceId'] == quiet_outer['InstanceId'] == source_outer['InstanceId'] == old['instanceId']
            and restore_outer['InstanceId'] == new['instanceId'], 'HISTORICAL_IDENTITY_CONTRADICTION')
    for receipt,identity in ((source,old),(restored,new)):
        runtime = receipt.get('RuntimePrecheck',{})
        require(runtime.get('Status') == 'RUNTIME_PRECHECK_INPUTS_BOUND'
                and runtime.get('RuntimePrecheckSatisfied') is True
                and type(runtime.get('HostBinding')) is dict
                and all(runtime['HostBinding'].get(k) == identity[k] for k in
                        ('accountId','region','instanceId','availabilityZone')), 'RUNTIME_HOST_CONTRADICTION')
    backup = source['Receipt']; manifest = backup['Manifest']
    require(manifest.get('NativeChecksumVerified') is True
            and all(type(value) is str and bool(value) and value.lower() not in ('null','latest')
                    for value in (backup.get('ManifestVersion'),manifest.get('BackupVersion')))
            and restored.get('ManifestVersion') == backup['ManifestVersion']
            and restored.get('BackupVersion') == manifest['BackupVersion'], 'BACKUP_VERSION_CONTRADICTION')
    ready = restored['ReadyAndDecryptedMarkersConfirmedUtc']
    require(event_order(source['PreMarkerRequestUtc'],source['PreMarkerConfirmedUtc'],
                manifest['StartedUtc'],manifest['CompletedUtc'],source['PostMarkerConfirmedUtc'],
                quiet['FailureDeclaredUtc'],quiet['SourceInactiveConfirmedUtc'],ready,
                restore_outer['FinishedUtc']), 'HISTORICAL_TIME_CONTRADICTION')
    require(restored.get('Checkdb') == 'RESTORED_CHECKDB_READABLE', 'CHECKDB_NOT_CONFIRMED')
    # Exact micro/100ns ordering above; do not manufacture Unix epochs, LaunchTime
    # from IMDS pendingTime, restore start from SSM start, or fencing from cleanup.
    known = dict(account=ACCOUNT,region=REGION,recovery_id=source['Trial'],
                 source_instance_id=old['instanceId'],target_instance_id=new['instanceId'],
                 checkdb=restored['Checkdb'])
    return {'Status':'HISTORICAL_GAP_REPORT_NOT_AUTHORITY','KnownHistoricalFields':known,
        'UnknownV2Fields':{name:'UNKNOWN' for name in V2_FIELDS if name not in known},
        'InputSha256':dict(pins),'EmbeddedReceiptBytesConsistent':True,
        'HistoricalObservations':{'SourceSqlInactiveOnly':True,
            'TargetCreatedFromZero':'UNKNOWN','PreparedTargetReadyUtc':ready,
            'PrivateFargateListener':'UNKNOWN','ConnectionSecretVersion':'UNKNOWN',
            'BackupAndManifestVersionsAgree':True,
            'RuntimePrecheckProjectionSha256':sha(encoded(restored['RuntimePrecheck']))},
        'EvidenceAuthenticated':False,'AllowsCreation':False,'AllowsActivation':False,
        'AllowsBindingPublication':False,'NativeAcceptanceV2':False,
        'Reasons':['Historical quiesce is not EC2 termination or an AZ failure.',
                   'Prepared-target marker time is not total cold-recovery RTO.',
                   'Loopback runtime proof is not private Fargate SQL reachability.',
                   'Backup manifest TextKeyArn is not a connection-version/approved-schema receipt.',
                   'Pins and hashes establish local consistency, not authority or current state.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','quiesce','restore'):
        parser.add_argument('--'+name,type=Path,required=True)
        parser.add_argument('--'+name+'-sha256',required=True)
    args=parser.parse_args()
    inputs={};pins={}
    for name in ('source','quiesce','restore'):
        with getattr(args,name).open('rb') as stream: inputs[name]=stream.read(1048577)
        pins[name]=getattr(args,name+'_sha256')
    print(encoded(project(inputs,pins)).decode(),end='')


if __name__ == '__main__':
    try: main()
    except Exception: raise SystemExit('HISTORICAL_PROJECTION_REFUSED_NO_AUTHORITY') from None
