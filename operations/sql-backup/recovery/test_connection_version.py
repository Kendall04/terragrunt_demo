"""Real local writer/CLI/file behavior with synthetic transport; no AWS or SQL."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

import host
import prepare
from test_service_plan import fixture

class ConnectionVersionTests(unittest.TestCase):
    def setUp(self):
        self.value=fixture()
        self.value['DatabaseSecurity']={'Profile':'validated-v2','RuntimeUser':'recovery_app','MigrationUser':'recovery_migrator',
            'MigrationSecretArn':f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/sql-migrator-password-AbCdEf',
            'CertificateHostName':'sql.demo.internal'}
        self.value['ColdReceipt'].update(DatabaseSecurity=self.value['DatabaseSecurity'],PrincipalAdoption='RUNTIME_MINIMAL_MIGRATOR_DISABLED')
        self.value['ColdReceipt']['ColdFence']['SourceLaunchUtc']='2026-10-24T18:00:00Z'
        self.now='2026-10-24T19:10:01Z'
        self.identity=self.value['ColdReceipt']['Target']
        self.conn=self.value['Connection'];self.stage='ecs-recovery-'+self.value['Trial']
        self.before={'ARN':self.conn['SecretArn'],'KmsKeyId':self.conn['SecretKeyArn'],
                     'VersionIdsToStages':{'a'*32:['AWSCURRENT'],'b'*32:['AWSPREVIOUS']}}
        self.after=copy.deepcopy(self.before)
        self.after['VersionIdsToStages'][self.conn['VersionId']]=[self.stage]
        self.port=host.Port()
        self.port.secret=Mock(return_value='SYNTHETIC;password"quoted')
        self.commands=[]
        self.private_values=[]
        self.put_error=False
        def run(command,env=None,**kwargs):
            self.commands.append(command)
            self.assertEqual(env['AWS_MAX_ATTEMPTS'],'1')
            self.assertNotIn('AWS_PROFILE',env)
            self.assertNotIn('AWS_ACCESS_KEY_ID',env)
            if 'describe-secret' in command:
                count=sum('describe-secret' in x for x in self.commands)
                return json.dumps(self.before if count==1 else self.after)
            self.assertIn('put-secret-value',command)
            path=Path(command[-1].removeprefix('file://'))
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            payload=json.loads(path.read_text())
            self.private_values.append(payload)
            self.assertNotIn('SYNTHETIC',str(command))
            if self.put_error:raise ValueError('CHILD_FAILED_REVIEW_BEFORE_RETRY')
            return json.dumps({'ARN':self.conn['SecretArn'],'VersionId':self.conn['VersionId'],
                               'VersionStages':[self.stage]})
        self.port.run=Mock(side_effect=run)
        self.listener=patch.object(host,'check_application_listener',return_value={'NetworkBinding':{'NativeFixtureOnly':True}})
        self.listener.start();self.addCleanup(self.listener.stop)
        self.clock=patch.object(host,'utc',side_effect=lambda:self.now)
        self.clock.start();self.addCleanup(self.clock.stop)
        self.temp=tempfile.TemporaryDirectory(prefix='ecs-connection-local-')
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.directory.chmod(0o700)

    def call(self,value=None,identity=None,ack=None):
        v=value or self.value
        digest=hashlib.sha256(prepare.encoded(v)).hexdigest()
        return host.write_connection_version(self.port,v,identity or self.identity,self.directory,
                                             digest if ack is None else ack)

    def test_actual_private_file_write_is_metadata_only_and_preserves_original_stages(self):
        result=self.call()
        self.assertEqual(result['Status'],'CONNECTION_VERSION_WRITTEN_METADATA_VERIFIED')
        self.assertFalse(result['AllowsActivation'])
        self.assertFalse(result['OwnerAuthorityEstablishedByAcknowledgement'])
        self.assertTrue(result['OriginalStagesPreserved'])
        self.assertNotIn('SYNTHETIC',json.dumps(result))
        self.assertEqual(list(self.directory.iterdir()),[])
        payload=self.private_values[0]
        self.assertEqual(payload['VersionStages'],[self.stage])
        self.assertEqual(payload['ClientRequestToken'],self.conn['VersionId'])
        self.assertIn('Server=tcp:10.77.1.8,1433;',payload['SecretString'])
        self.assertIn('Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.demo.internal;',payload['SecretString'])
        self.assertNotIn('recovery_migrator',payload['SecretString'])
        self.assertIn('Password="SYNTHETIC;password""quoted";',payload['SecretString'])
        self.assertEqual(sum('put-secret-value' in c for c in self.commands),1)
        self.assertNotIn('update-secret-version-stage',str(self.commands))

    def test_missing_or_wrong_ack_cannot_read_secrets_or_write(self):
        for ack in ('','f'*64):
            with self.assertRaisesRegex(ValueError,'ACK_REQUIRED'):self.call(ack=ack)
        self.assertEqual(self.commands,[]);self.port.secret.assert_not_called()

    def test_historical_review_hash_is_not_current_authority(self):
        self.now='2026-10-25T19:10:01Z'
        with self.assertRaisesRegex(ValueError,'FRESH_CONNECTION'):self.call()
        self.assertEqual(self.commands,[]);self.port.secret.assert_not_called()

    def test_future_review_and_foreign_target_are_refused_before_writes(self):
        self.now='2026-10-24T19:09:59Z'
        with self.assertRaisesRegex(ValueError,'FRESH_CONNECTION'):self.call()
        self.now='2026-10-24T19:10:01Z'
        with self.assertRaisesRegex(ValueError,'TARGET_IDENTITY'):self.call(identity=dict(self.identity,instanceId='i-'+'9'*17))
        self.assertEqual(self.commands,[])

    def test_foreign_secret_version_override_listener_and_extra_authority_fail_closed(self):
        for change in (
            lambda v:v['Connection'].update(SecretArn=prepare.APP_SECRET),
            lambda v:v['Connection'].update(VersionId='latest'),
            lambda v:v['Connection'].update(SecretKeyArn=prepare.BACKUP_KEY),
            lambda v:v['Network'].update(SqlBoundAddresses=['0.0.0.0']),
            lambda v:v.update(OwnerApproved=True)):
            value=copy.deepcopy(self.value);change(value)
            with self.assertRaises(ValueError):self.call(value=value)
        self.assertEqual(self.commands,[]);self.port.secret.assert_not_called()

    def test_readback_metadata_must_match_exact_secret_key_and_existing_current(self):
        original=copy.deepcopy(self.before)
        for change in (
            lambda m:m.update(ARN=prepare.APP_SECRET),
            lambda m:m.update(KmsKeyId=prepare.BACKUP_KEY),
            lambda m:m.update(DeletedDate='pending'),
            lambda m:m.update(VersionIdsToStages={}),
            lambda m:m['VersionIdsToStages'].update({self.conn['VersionId']:[self.stage]}),
            lambda m:m['VersionIdsToStages']['a'*32].append(self.stage)):
            self.commands.clear();self.before=copy.deepcopy(original);change(self.before)
            with self.assertRaises(ValueError):self.call()
            self.assertEqual(len(self.commands),1)
        self.port.secret.assert_not_called()

    def test_put_denial_is_once_private_file_removed_and_no_followup_or_fallback(self):
        self.put_error=True
        with self.assertRaisesRegex(ValueError,'CHILD_FAILED'):self.call()
        self.assertEqual(len(self.commands),2)
        self.assertEqual(sum('put-secret-value' in c for c in self.commands),1)
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_concurrent_stage_change_after_put_is_unknown_not_compensated(self):
        self.after['VersionIdsToStages']['a'*32]=['AWSPREVIOUS']
        with self.assertRaisesRegex(ValueError,'STAGES_CHANGED_OR_UNKNOWN'):self.call()
        self.assertEqual(sum('put-secret-value' in c for c in self.commands),1)
        self.assertNotIn('update-secret',str(self.commands))

    def test_default_cli_is_plan_only_even_for_new_action(self):
        output=io.StringIO()
        with patch('sys.argv',['host.py','connection-version','--trial',self.value['Trial'],
                               '--directory',str(self.directory)]),patch.object(host,'Port') as port,redirect_stdout(output):
            host.main()
        self.assertEqual(json.loads(output.getvalue())['Status'],'HOST_PLAN_ONLY')
        port.assert_not_called();self.assertEqual(list(self.directory.iterdir()),[])

    def test_cli_started_marker_blocks_replay_after_unknown(self):
        plan=self.directory/'plan.json';plan.write_text(json.dumps(self.value))
        argv=['host.py','connection-version','--trial',self.value['Trial'],'--directory',str(self.directory),
              '--execute','--acknowledge',self.value['Trial'],'--listener-plan',str(plan),
              '--expected-instance-id',self.identity['instanceId'],'--expected-az',self.identity['availabilityZone']]
        self.port.identity=Mock(return_value=self.identity)
        with patch('sys.argv',argv),patch.object(host.os,'geteuid',return_value=0),patch.object(host,'Port',return_value=self.port),patch.object(host,'write_connection_version',side_effect=ValueError('OUTCOME_UNKNOWN')) as writer:
            with self.assertRaisesRegex(ValueError,'OUTCOME_UNKNOWN'):host.main()
            with self.assertRaisesRegex(ValueError,'PREVIOUS_ACTION'):host.main()
        self.assertEqual(writer.call_count,1)
        self.assertTrue((self.directory/'connection-version-receipt.started').is_file())

if __name__=='__main__':unittest.main(verbosity=2)
