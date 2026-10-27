"""Three metadata-only E16 inputs; synthetic state port, no AWS/Terraform."""
import copy
import unittest
from unittest.mock import Mock
import test_practical as fixture
from scripts import practical_dev as p

class DataInputTests(unittest.TestCase):
    setUp=fixture.Tests.setUp
    def metadata(self,updates):
        self.session.config['variables']['data']=copy.deepcopy(updates)
        self.session.state=Mock(return_value={'outputs':{'private_subnet_ids':['subnet-'+'a'*17,'subnet-'+'b'*17],'db_instance_sg_id':'sg-'+'c'*17}})
        self.fake.calls.clear()
        return self.session.variables('data')
    def cohost(self):
        # Actual account-specific contract; all versions/IDs below are SYNTHETIC.
        self.session.account='341936017254'
        sha='a'*64;run='ecs-sentinel-e16-fixture'
        return {'artifact':{'Bucket':'terragrunt-demo-sql-backup-341936017254-fa48a32dc9',
          'Key':'terragrunt-demo/dev/sql-backup-artifacts/'+run+'/'+sha+'/SqlBackup.tar',
          'VersionId':'SYNTHETIC_VERSION_NOT_ADMITTED','Sha256':sha,'BucketKeyEnabled':False},
          'backup':{'Database':'demodb','StagingDirectory':'/var/opt/mssql/backup/e16-fixture',
          'RestoreDirectory':'/var/opt/mssql/backup/e16-fixture-restores','Bucket':'terragrunt-demo-sql-backup-341936017254-fa48a32dc9',
          'Prefix':'terragrunt-demo/dev/sql-backups/ec2-20261016/e16-fixture',
          'BackupKeyArn':'arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced',
          'TextKeyArn':'arn:aws:kms:us-east-1:341936017254:key/50d3fe36-8128-4d09-ac13-8f5536a230a7',
          'ExpectedEc2RoleName':'demo-dev-data-sql-ec2-role','MaxBackupBytes':536870912,'FreeReserveBytes':268435456,
          'TimeoutSeconds':600,'ProposedIntervalHours':1,'ProposedRetentionDays':2,'ProposedMaxAgeHours':2,'RetainLocalVerifiedBackups':2},
          'sentinel':{'SchemaVersion':1,'Placement':'SQL_HOST','Account':'341936017254','Region':'us-east-1',
          'RunId':run,'Subject':'e16-fixture','StartsAt':'2026-10-27T00:00:00Z','ExpiresAt':'2026-10-28T00:00:00Z',
          'CadenceSeconds':300,'ReminderSeconds':0,'PublishAttempts':3,'WatchdogSeconds':1200,'ExpectedUp':True,
          'Portable':{'SchemaVersion':1,'ContractSha256':'b'*64}}}
    def test_explicit_nulls_and_legacy_defaults_are_preserved_without_operations(self):
        values=dict(sql_database_security=None,sql_backup_cohost=None,recovery_target_subnet_id=None)
        result=self.metadata(values)
        self.assertTrue(all(result[k] is None for k in values));self.assertEqual(self.fake.calls,[])
        self.assertNotIn('sql_database_security',self.metadata({}))
    def test_strict_identity_reference_and_observed_subnet_roundtrip_without_override(self):
        security={'migration_user':'fixture_migrator','migration_secret_arn':f'arn:aws:secretsmanager:{self.session.region}:{self.session.account}:secret:demo/dev/db/sql-migrator-password-AbCdEf'}
        values=dict(sql_database_security=security,recovery_target_subnet_id='subnet-'+'b'*17)
        result=self.metadata(values)
        for k,v in values.items():self.assertEqual(result[k],v)
        self.assertEqual(result['db_instance_sg_id'],'sg-'+'c'*17);self.assertEqual(self.fake.calls,[])
        with self.assertRaisesRegex(ValueError,'observed original global'):self.metadata(dict(values,recovery_target_subnet_id='subnet-'+'d'*17))
    def test_security_values_wrong_scope_sa_shared_identity_extra_keys_and_commands_are_rejected(self):
        security={'migration_user':'fixture_migrator','migration_secret_arn':f'arn:aws:secretsmanager:{self.session.region}:{self.session.account}:secret:demo/dev/db/sql-migrator-password-AbCdEf'}
        for mutate in (lambda x:x.update(migration_user='sa'),lambda x:x.update(migration_user='fargate_user'),
                       lambda x:x.update(migration_secret_arn='SYNTHETIC_PASSWORD_NOT_AN_ARN'),
                       lambda x:x.update(migration_secret_arn=x['migration_secret_arn'].replace('us-east-1','us-east-2')),
                       lambda x:x.update(migration_secret_arn=x['migration_secret_arn'].replace(self.session.account,'999999999999')),
                       lambda x:x.update(password='SYNTHETIC_VALUE'),lambda x:x.update(command=['not-admitted'])):
            v=copy.deepcopy(security);mutate(v)
            with self.assertRaises(ValueError):self.metadata({'sql_database_security':v})
            self.session.state.assert_not_called();self.assertEqual(self.fake.calls,[])
        for key in ('private_subnet_ids','db_instance_sg_id','protected_inputs','user_data','iam_instance_profile'):
            with self.assertRaises(ValueError):self.metadata({key:'caller override'})
            self.session.state.assert_not_called()
    def test_cohost_public_metadata_roundtrips_with_timers_disabled_and_no_policy_defaults_changed(self):
        cohost=self.cohost();before=copy.deepcopy(cohost)
        result=self.metadata({'sql_backup_cohost':cohost})
        self.assertEqual(result['sql_backup_cohost'],before);self.assertEqual(self.fake.calls,[])
        self.assertNotIn('enable_after_native_gates',cohost)
    def test_cohost_activation_unknown_fields_foreign_artifact_keys_paths_and_values_are_rejected(self):
        original=self.cohost()
        for mutate in (lambda x:x.update(enable_after_native_gates=True),lambda x:x.update(enable_producer_after_native_gates=True),
                       lambda x:x.update(command=['start']),lambda x:x['backup'].update(ConnectionString='SYNTHETIC_SECRET'),
                       lambda x:x['artifact'].update(VersionId='latest'),lambda x:x['artifact'].update(Key='other/artifact'),
                       lambda x:x['artifact'].update(BucketKeyEnabled=True),lambda x:x['backup'].update(TextKeyArn=x['backup']['BackupKeyArn']),
                       lambda x:x['backup'].update(StagingDirectory='/etc/unrelated'),lambda x:x['sentinel'].update(Account='999999999999'),
                       lambda x:x['sentinel'].update(PublishAttempts=4),lambda x:x['sentinel'].update(ExpiresAt='2026-11-01T00:00:00Z'),
                       lambda x:x['sentinel']['Portable'].update(Token='SYNTHETIC_SECRET')):
            v=copy.deepcopy(original);mutate(v)
            with self.assertRaises(ValueError):self.metadata({'sql_backup_cohost':v})
            self.session.state.assert_not_called();self.assertEqual(self.fake.calls,[])
    def test_subnet_type_wildcard_and_non_data_root_pass_through_fail_closed(self):
        for subnet in ('subnet-*','subnet-foreign',1,True):
            with self.assertRaises(ValueError):self.metadata({'recovery_target_subnet_id':subnet})
            self.session.state.assert_not_called()
        self.session.config['variables']['global']={'sql_database_security':None}
        with self.assertRaisesRegex(ValueError,'dependency overrides'):self.session.variables('global')
