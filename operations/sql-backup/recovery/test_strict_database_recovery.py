"""Strict recovery composition with synthetic ports only; no SQL, AWS or processes."""
import copy
import json
import tempfile
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import Mock, patch
import unittest
import host
import prepare
from test_recovery import FakePort, IDENTITY, TARGET, NAME
from test_service_plan import fixture


def security():
    return dict(Profile='validated-v2',RuntimeUser='recovery_app',MigrationUser='recovery_migrator',
        MigrationSecretArn=f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/sql-migrator-password-AbCdEf',
        CertificateHostName='sql.demo.internal')


class StrictFake(FakePort):
    def __init__(self):
        super().__init__();self.database_security=security();self.phases=[]
    def secret(self,arn):
        return 'fixture-migrator-only' if arn==self.database_security['MigrationSecretArn'] else 'fixture-runtime-admin'
    def principals(self,phase,database,*passwords):self.phases.append((phase,database))
    def migrate(self,exe,password,database):self.phases.append(('migrate',database))
    @contextmanager
    def api(self,exe,password,database,migrate):
        self.phases.append(('api',database,migrate));yield


class StrictDatabaseRecoveryTests(unittest.TestCase):
    def test_connection_enforces_tls_name_and_quoted_password_without_pin_or_fallback(self):
        c=host.connection('recovery_app','fixture;"quoted','recoverydb_restore_'+NAME,'10.77.1.8',security=security())
        self.assertIn('Server=tcp:10.77.1.8,1433;',c)
        self.assertIn('Password="fixture;""quoted";',c)
        self.assertIn('Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.demo.internal;',c)
        self.assertNotIn(';ServerCertificate=',c)
        for x in ({},dict(security(),Profile='legacy-v1'),dict(security(),CertificateHostName='*.demo.internal')):
            with self.assertRaises(ValueError):host.connection('recovery_app','fixture','recoverydb',security=x)
        with self.assertRaises(ValueError):host.connection('sa','fixture','recoverydb',security=security())
        with self.assertRaisesRegex(ValueError,'LOOPBACK_ONLY'):host.connection('recovery_app','fixture','recoverydb','10.77.1.8')
        self.assertIn('TrustServerCertificate=True;',host.connection('recovery_app','fixture','recoverydb'))

    def test_migrator_environment_is_separate_and_runtime_cannot_inherit_credential(self):
        with patch.dict(host.os.environ,{'DB_CONN_STRING':'forbidden','DB_MIGRATION_CONN_STRING':'forbidden',
                                       'Database__SecurityProfile':'legacy-v1','AWS_ACCESS_KEY_ID':'forbidden'}):
            env=host.database_process_environment(security(),'recoverydb')
        self.assertNotIn('DB_CONN_STRING',env);self.assertNotIn('DB_MIGRATION_CONN_STRING',env)
        self.assertNotIn('AWS_ACCESS_KEY_ID',env)
        self.assertEqual(env['Database__SecurityProfile'],'validated-v2')
        self.assertEqual(env['Database__RunMigrationsOnStartup'],'false')
        p=host.Port();p.configure_security(security());captured=[]
        p.run=Mock(side_effect=lambda *args,**kw:captured.append(dict(kw['env'])) or 'DATABASE_MIGRATION_COMPLETED\n')
        p.migrate(Path('/reviewed/api'),'fixture-migrator','recoverydb')
        args=p.run.call_args
        self.assertEqual(args.args[0][-2:],['database-migrate','--confirm-schema-change'])
        self.assertIn('User Id=recovery_migrator;',captured[0]['DB_MIGRATION_CONN_STRING'])
        self.assertIn('TrustServerCertificate=False;',captured[0]['DB_MIGRATION_CONN_STRING'])
        self.assertNotIn('KMS_KEY_ID',captured[0])
        self.assertNotIn('DB_CONN_STRING',args.kwargs['env'])
        self.assertNotIn('DB_MIGRATION_CONN_STRING',args.kwargs['env'])  # removed in finally
        self.assertNotIn('-C',p.sql_tls_args())
        self.assertEqual(p.sql_tls_args(),['-N','-F','sql.demo.internal'])
        p.run.reset_mock()
        with self.assertRaisesRegex(ValueError,'RUNTIME_MIGRATION'):
            with p.api(Path('/reviewed/api'),'fixture','recoverydb',True):pass
        p.run.assert_not_called()

    def test_actual_helper_adapter_uses_bound_public_source_and_validated_admin_tls(self):
        helper=Path(__file__).resolve().parents[3]/'terraform/infra/data/sql-principals.sh'
        p=host.Port();p.configure_security(security());calls=[]
        p.run=Mock(side_effect=lambda command,**kw:calls.append((command,dict(kw['env']))))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'sql-principals.sh').write_bytes(helper.read_bytes())
            with patch.object(host,'__file__',str(root/'host.py')):
                p.principals('prepare','recoverydb','fixture-admin','fixture-runtime','fixture-migrator')
                command,env=calls[0]
                self.assertEqual(command[:3],['/bin/bash','--noprofile','--norc'])
                self.assertIn('-N -F "$CERTIFICATE_HOSTNAME"',command[4]);self.assertNotIn(' -C ',command[4])
                self.assertIn('sql_principals_prepare --ack-reviewed-sql-privilege-change',command[4])
                self.assertEqual(env['APP_USER'],'recovery_app');self.assertEqual(env['MIGRATION_USER'],'recovery_migrator')
                self.assertNotIn('fixture-admin',str(command));self.assertNotIn('fixture-migrator',str(command))
                (root/'sql-principals.sh').write_text('tampered')
                with self.assertRaisesRegex(ValueError,'REVIEWED_PRINCIPAL_HELPER'):p.principals('prepare','recoverydb','fixture')
        self.assertEqual(p.run.call_count,1)

    def test_source_and_restore_adopt_minimal_runtime_only_after_migrator(self):
        p=StrictFake();src=host.source(p,NAME,Path('/fixture/config'),Path('/fixture/backup'),Path('/fixture/api'),IDENTITY)
        self.assertEqual(p.phases[:4],[('prepare','recoverydb'),('migrate','recoverydb'),('activate_runtime','recoverydb'),('api','recoverydb',False)])
        self.assertFalse(any('db_owner ADD MEMBER' in c for c in p.commands if isinstance(c,str)))
        self.assertEqual(src['DatabaseSecurity'],security())
        failure=host.quiesce(p,src,IDENTITY)
        result=host.restore(p,NAME,Path('/fixture/config'),Path('/fixture/backup'),Path('/fixture/api'),TARGET,src,failure)
        db='recoverydb_restore_'+NAME
        self.assertEqual(p.phases[-4:],[('prepare',db),('migrate',db),('activate_runtime',db),('api',db,False)])
        self.assertEqual(result['PrincipalAdoption'],'RUNTIME_MINIMAL_MIGRATOR_DISABLED')
        self.assertEqual(result['DatabaseSecurity'],security());self.assertFalse(result['FullEcsRecoveryProven'])
        self.assertTrue(any('ALTER USER recovery_migrator WITH LOGIN=recovery_migrator' in c for c in p.commands if isinstance(c,str)))

    def test_failed_migration_never_activates_runtime_or_launches_api(self):
        p=StrictFake();p.migrate=Mock(side_effect=ValueError('DATABASE_MIGRATION_RESULT_UNKNOWN'))
        with self.assertRaisesRegex(ValueError,'MIGRATION_RESULT_UNKNOWN'):
            host.source(p,NAME,Path('/fixture/config'),Path('/fixture/backup'),Path('/fixture/api'),IDENTITY)
        self.assertEqual(p.phases,[('prepare','recoverydb')]);self.assertEqual(p.migrate.call_count,1)

    def test_strict_restore_cannot_relabel_legacy_source_receipt(self):
        p=FakePort();src=host.source(p,NAME,None,None,None,IDENTITY)
        strict=StrictFake()
        with self.assertRaisesRegex(ValueError,'SECURITY_MISMATCH'):
            host.restore(strict,NAME,None,None,None,TARGET,src,{})
        self.assertEqual(strict.commands,[]);self.assertEqual(strict.phases,[])

    def test_service_contract_binds_adoption_and_all_runtime_fields(self):
        v=fixture();v['DatabaseSecurity']=security()
        with self.assertRaisesRegex(ValueError,'PRINCIPAL_RECEIPT'):prepare.service_plan(v)
        v['ColdReceipt'].update(DatabaseSecurity=security(),PrincipalAdoption='RUNTIME_MINIMAL_MIGRATOR_DISABLED')
        plan=prepare.service_plan(v)
        env={e['name']:e['value'] for e in plan['ProposedTaskEnvironmentAppend']}
        self.assertEqual(env['Database__ExpectedSqlEndpoint'],'tcp:10.77.1.8,1433')
        self.assertEqual(env['Database__ExpectedRuntimeUser'],'recovery_app')
        self.assertNotIn('MigrationSecretArn',json.dumps(plan['ProposedTaskEnvironmentAppend']))
        for change in (lambda x:x['DatabaseSecurity'].update(Profile='legacy-v1'),
                       lambda x:x['DatabaseSecurity'].update(MigrationSecretArn=prepare.APP_SECRET),
                       lambda x:x['DatabaseSecurity'].update(RuntimeUser='sa'),
                       lambda x:x['ColdReceipt'].update(PrincipalAdoption='LEGACY_DB_OWNER')):
            x=copy.deepcopy(v);change(x)
            with self.assertRaises(ValueError):prepare.service_plan(x)

if __name__=='__main__':unittest.main()
