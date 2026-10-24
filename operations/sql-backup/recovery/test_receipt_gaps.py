"""Synthetic historical-shape receipts; no native observations or approvals."""
import ast
import copy
import io
from contextlib import redirect_stdout
import tempfile
from unittest.mock import patch
import json
from pathlib import Path
import sys
import unittest

import receipt_gaps as g


def audit(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn'):
        raise AssertionError('GAP_PROJECTION_EXTERNAL_EFFECT_FORBIDDEN')
sys.addaudithook(audit)


def fixture():
    source=dict(accountId=g.ACCOUNT,region=g.REGION,instanceId='i-'+'1'*17,availabilityZone='us-east-1a')
    target=dict(source,instanceId='i-'+'2'*17,availabilityZone='us-east-1b')
    runtime=lambda identity:dict(Status='RUNTIME_PRECHECK_INPUTS_BOUND',RuntimePrecheckSatisfied=True,
        HostBinding=copy.deepcopy(identity),Ipv4Loopback1433Only=True)
    before=dict(Status='SOURCE_BACKED_UP',Trial='r20261023az6',Source=source,
        RuntimePrecheck=runtime(source),PreMarkerRequestUtc='2026-10-23T04:41:28.132761Z',
        PreMarkerConfirmedUtc='2026-10-23T04:41:28.419738Z',PostMarkerConfirmedUtc='2026-10-23T04:41:30.387806Z',
        Receipt=dict(ManifestVersion='fixture-manifest-v1',Manifest=dict(NativeChecksumVerified=True,
            BackupVersion='fixture-backup-v1',StartedUtc='2026-10-23T04:41:29.5627332Z',
            CompletedUtc='2026-10-23T04:41:29.831222Z')))
    quiet=dict(Trial=before['Trial'],SourceInstanceId=source['instanceId'],ActiveState='inactive',
        FailureDeclaredUtc='2026-10-23T04:41:48.429323Z',SourceInactiveConfirmedUtc='2026-10-23T04:41:48.633769Z')
    after=dict(Status='TARGET_RECOVERED_REVIEW_EVIDENCE',Trial=before['Trial'],Source=copy.deepcopy(source),
        Target=target,RuntimePrecheck=runtime(target),ManifestVersion='fixture-manifest-v1',BackupVersion='fixture-backup-v1',
        Checkdb='RESTORED_CHECKDB_READABLE',ReadyAndDecryptedMarkersConfirmedUtc='2026-10-23T04:44:11.060106Z')
    records={}
    for name,value,identity in [('source',before,source),('quiesce',quiet,source),('restore',after,target)]:
        records[name]=dict(Trial=before['Trial'],InstanceId=identity['instanceId'],Outcome='HOST_ACTION_COMPLETE',
            SsmStatus='Success',ResponseCode=0,FinishedUtc='2026-10-23T04:44:16.444863Z',
            Result=dict(Status='HOST_ACTION_COMPLETE',Action=name,Receipt=value))
    return records


def encode(records):
    values=copy.deepcopy(records)
    for value in values.values():
        value['Result']['ReceiptSha256']=g.sha(json.dumps(value['Result']['Receipt'],indent=2).encode())
    inputs={name:json.dumps(value,indent=2).encode() for name,value in values.items()}
    return inputs,{name:g.sha(raw) for name,raw in inputs.items()}


class ReceiptGapTests(unittest.TestCase):
    def test_only_six_historical_fields_and_unknown_not_approval(self):
        report=g.project(*encode(fixture()))
        self.assertEqual(len(report['KnownHistoricalFields']),6)
        self.assertEqual(set(report['KnownHistoricalFields'])|set(report['UnknownV2Fields']),set(g.V2_FIELDS))
        self.assertTrue(all(v=='UNKNOWN' for v in report['UnknownV2Fields'].values()))
        for key in ('source_state','source_terminated_at','target_launch_epoch','restore_started_at',
                    'observed_at','secret_key_arn','secret_version_id','endpoint','writer','schema'):
            self.assertEqual(report['UnknownV2Fields'][key],'UNKNOWN')
        for key in ('EvidenceAuthenticated','AllowsCreation','AllowsActivation','AllowsBindingPublication','NativeAcceptanceV2'):
            self.assertIs(report[key],False)
        self.assertNotIn('schema',report);self.assertNotIn('writer',report)

    def test_cli_reads_only_explicit_pinned_inputs_and_prints_gap_report(self):
        inputs,pins=encode(fixture())
        with tempfile.TemporaryDirectory() as directory:
            args=['receipt_gaps.py']
            for name,raw in inputs.items():
                path=Path(directory)/(name+'.json');path.write_bytes(raw)
                args+=['--'+name,str(path),'--'+name+'-sha256',pins[name]]
            output=io.StringIO()
            with patch.object(sys,'argv',args),redirect_stdout(output):g.main()
            report=json.loads(output.getvalue())
            self.assertEqual(report['Status'],'HISTORICAL_GAP_REPORT_NOT_AUTHORITY')
            self.assertEqual(report['InputSha256'],pins)
            self.assertIs(report['AllowsBindingPublication'],False)

    def test_v2_field_list_tracks_existing_validator_not_a_new_schema(self):
        root=Path(__file__).resolve().parents[3]
        tree=ast.parse((root/'scripts/normal_delivery/recovery.py').read_text(encoding='utf-8'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_recovery')
        call=next(n for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                  and n.func.attr=='keys' and isinstance(n.args[0],ast.Name) and n.args[0].id=='e')
        self.assertEqual(g.V2_FIELDS,ast.literal_eval(call.args[1]))

    def test_raw_pin_and_embedded_hash_fail_closed(self):
        raw,pins=encode(fixture());pins['source']='0'*64
        with self.assertRaisesRegex(ValueError,'PIN_MISMATCH'):g.project(raw,pins)
        raw,pins=encode(fixture());body=json.loads(raw['restore']);body['Result']['Receipt']['Checkdb']='CHANGED'
        raw['restore']=g.encoded(body);pins['restore']=g.sha(raw['restore'])
        with self.assertRaisesRegex(ValueError,'EMBEDDED_RECEIPT_HASH'):g.project(raw,pins)

    def test_identity_trial_runtime_and_backup_contradictions(self):
        mutations=[lambda r:r['restore']['Result']['Receipt']['Source'].update(instanceId='i-'+'3'*17),
            lambda r:r['source']['Result']['Receipt']['Source'].update(accountId='000000000000'),
            lambda r:r['restore']['Result']['Receipt']['Target'].update(region='us-west-2'),
            lambda r:r['quiesce']['Result']['Receipt'].update(SourceInstanceId='i-'+'3'*17),
            lambda r:r['restore'].update(InstanceId='i-'+'3'*17),
            lambda r:r['restore']['Result']['Receipt'].update(Trial='r20261023other'),
            lambda r:r['restore']['Result']['Receipt']['RuntimePrecheck']['HostBinding'].update(instanceId='i-'+'3'*17),
            lambda r:r['restore']['Result']['Receipt'].update(ManifestVersion='foreign-version'),
            lambda r:r['restore']['Result']['Receipt'].update(BackupVersion='foreign-version'),
            lambda r:r['restore']['Result']['Receipt'].update(Checkdb='UNKNOWN')]
        for mutate in mutations:
            records=fixture();mutate(records)
            with self.subTest(mutate=mutate),self.assertRaises((ValueError,KeyError)):g.project(*encode(records))

    def test_time_order_preserves_100ns_and_requires_offset(self):
        records=fixture();manifest=records['source']['Result']['Receipt']['Receipt']['Manifest']
        manifest.update(StartedUtc='2026-10-23T04:41:29.5627332Z',CompletedUtc='2026-10-23T04:41:29.5627331Z')
        with self.assertRaisesRegex(ValueError,'TIME_CONTRADICTION'):g.project(*encode(records))
        records=fixture();records['restore']['Result']['Receipt']['ReadyAndDecryptedMarkersConfirmedUtc']='2026-10-23T04:44:11'
        with self.assertRaisesRegex(ValueError,'UTC_OFFSET_REQUIRED'):g.project(*encode(records))

    def test_never_infers_current_state_pending_time_or_claimed_authority(self):
        records=fixture()
        for value in records.values():
            value.update(Approval='APPROVED',NativeAcceptanceV2=True,SecretString='SYNTHETIC_DO_NOT_EXPORT')
            value['Result']['Receipt'].update(source_state='terminated',schema='E1_SQL_RECOVERY_EVIDENCE_V2',
                writer='SECURITY_ADMIN',secret_version_id='a'*32,source_terminated_at=1000)
        records['restore']['Result']['Receipt']['Target'].update(pendingTime='2026-10-23T03:58:15Z')
        report=g.project(*encode(records));text=json.dumps(report)
        self.assertNotIn('SYNTHETIC_DO_NOT_EXPORT',text)
        self.assertNotIn('APPROVED',text);self.assertNotIn('SECURITY_ADMIN',text)
        self.assertEqual(report['UnknownV2Fields']['source_state'],'UNKNOWN')
        self.assertEqual(report['UnknownV2Fields']['target_launch_epoch'],'UNKNOWN')

    def test_size_duplicates_missing_fields_and_incomplete_execution_refuse(self):
        raw,pins=encode(fixture());raw['source']=b' '*(1048577);pins['source']=g.sha(raw['source'])
        with self.assertRaisesRegex(ValueError,'SIZE_INVALID'):g.project(raw,pins)
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_FIELD'):g.parse(b'{"x":1,"x":2}',g.sha(b'{"x":1,"x":2}'))
        for field in ('Outcome','SsmStatus','ResponseCode'):
            records=fixture();records['restore'].pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):g.project(*encode(records))
        records=fixture();records['restore']['ResponseCode']=False
        with self.assertRaises(ValueError):g.project(*encode(records))
        records=fixture();records['source']['Result']['Receipt'].pop('Source')
        with self.assertRaises(KeyError):g.project(*encode(records))


if __name__=='__main__':unittest.main()
