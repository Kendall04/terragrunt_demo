"""SQL adoption composition using Bash plus a substituted SQL port. Never SQL/AWS."""
import base64
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / 'terraform/infra/data/sql-principals.sh'
BASH = Path(r'C:\Program Files\Git\bin\bash.exe') if os.name == 'nt' else Path(shutil.which('bash') or '/bin/bash')

class SqlPrincipalsTests(unittest.TestCase):
    def run_fixture(self, body):
        self.assertTrue(BASH.is_file(), 'Use existing Bash only; no installs')
        path = HELPER.resolve().as_posix()
        if os.name == 'nt': path = '/' + path[0].lower() + path[2:]
        with tempfile.TemporaryDirectory(prefix='ecs-principals-') as directory:
            fixture = Path(directory)
            env={'PATH':str(BASH.parent.parent/'usr/bin') if os.name=='nt' else '/usr/bin:/bin',
                 'SystemRoot':os.environ.get('SystemRoot',''), 'TEMP':directory,'TMP':directory,
                 'LC_ALL':'C', 'FIXTURE_DIR':fixture.as_posix()}
            script=r"""
set -euo pipefail
source "$1"
APP_DB=demodb; APP_USER=fargate_user; MIGRATION_USER=demo_migrator
APP_PASS="fixture-'quoted"; MIGRATION_PASS='fixture-$(must_not_run)'
SQLCMDPASSWORD=fixture-admin
sql_principals_is_root() { return 0; }
# Substituted port captures synthetic SQL in private fixture only.
sql_principals_execute() { cat > "$FIXTURE_DIR/statement"; }
aws() { echo UNEXPECTED_AWS >&2; return 98; }
sqlcmd() { echo UNEXPECTED_SQL >&2; return 98; }
"""
            result=subprocess.run([str(BASH),'--noprofile','--norc','-c',script+body,'fixture',path],
                                  env=env,capture_output=True,text=True,timeout=10)
            sql=(fixture/'statement').read_text(encoding='utf-8') if (fixture/'statement').exists() else ''
            return result,sql

    def test_source_is_inert(self):
        result,sql=self.run_fixture('true')
        self.assertEqual((0,'','', ''),(result.returncode,result.stdout,result.stderr,sql))

    def test_prepare_separates_roles_disables_runtime_and_never_rotates_existing_password(self):
        result,sql=self.run_fixture('sql_principals_prepare --ack-reviewed-sql-privilege-change')
        self.assertEqual((0,'',''),(result.returncode,result.stdout,result.stderr))
        self.assertIn("PASSWORD=N'fixture-''quoted'",sql)
        self.assertIn("PASSWORD=N'fixture-$(must_not_run)'",sql)
        self.assertIn("IF SUSER_ID(N'fargate_user') IS NULL",sql)
        self.assertIn('ALTER LOGIN [fargate_user] DISABLE',sql)
        self.assertLess(sql.index('DISABLE'),sql.index('ALTER ROLE db_owner DROP MEMBER'))
        self.assertNotIn('db_owner ADD MEMBER',sql)
        self.assertNotIn('ALTER LOGIN [fargate_user] WITH PASSWORD',sql)
        self.assertIn('GRANT SELECT, INSERT, DELETE ON SCHEMA::dbo TO [demo_migrator]',sql)
        self.assertNotIn('GRANT SELECT, INSERT ON OBJECT::dbo.DemoTexts TO [fargate_user]',sql)
        self.assertIn('APPLICATION_SESSIONS_MUST_BE_QUIESCED',sql)
        self.assertIn('APPLICATION_SERVER_PERMISSION_FORBIDDEN',sql)
        self.assertIn('DATABASE_LOGIN_BINDING_MISMATCH',sql)
        self.assertIn('UNREVIEWED_RUNTIME_ROLE',sql)

    def test_activate_requires_exact_migrations_before_permissions_and_disables_migrator_first(self):
        result,sql=self.run_fixture('sql_principals_activate_runtime --ack-reviewed-sql-privilege-change')
        self.assertEqual((0,'',''),(result.returncode,result.stdout,result.stderr))
        self.assertIn('20251123201248_InitialMigration',sql)
        self.assertIn('20260305033500_ExpandCipherTextColumn',sql)
        self.assertIn("COALESCE(COL_LENGTH(N'dbo.DemoTexts', N'Text'),0)<>-1",sql)
        self.assertLess(sql.index('REVIEWED_SCHEMA_REQUIRED'),sql.index('GRANT SELECT'))
        self.assertLess(sql.index('ALTER LOGIN [demo_migrator] DISABLE'),sql.index('ALTER LOGIN [fargate_user] ENABLE'))
        self.assertNotIn('CREATE LOGIN',sql)
        self.assertNotIn('UPDATE ON',sql)
        self.assertNotIn('DELETE ON',sql)

    def test_gate_and_bad_inputs_never_reach_port(self):
        for setup in ('APP_USER=SA','MIGRATION_USER=FARGATE_USER','APP_DB=master',
                      "APP_USER='unsafe;name'",'SQLCMDPASSWORD=',"APP_PASS=$'bad\\nsecret'",
                      'sql_principals_is_root() { return 1; }'):
            with self.subTest(setup=setup):
                result,sql=self.run_fixture(setup+'\nsql_principals_prepare --ack-reviewed-sql-privilege-change')
                self.assertNotEqual(0,result.returncode)
                self.assertEqual('',sql)
        for name in ('sql_principals_prepare','sql_principals_activate_runtime'):
            result,sql=self.run_fixture(name)
            self.assertNotEqual(0,result.returncode)
            self.assertEqual('',sql)

    def test_failure_reports_uncertain_outcome_without_leaking_sql_or_password(self):
        for name in ('sql_principals_prepare','sql_principals_activate_runtime'):
            result,_=self.run_fixture('sql_principals_execute() { cat >/dev/null; return 1; }\n'+name+' --ack-reviewed-sql-privilege-change')
            self.assertEqual(65,result.returncode)
            self.assertEqual('',result.stdout)
            self.assertIn('OUTCOME_REQUIRES_READBACK',result.stderr)
            self.assertNotIn('fixture-',result.stderr)

    def test_fixed_adapter_has_no_password_argv_and_only_loopback(self):
        source=HELPER.read_text(encoding='utf-8')
        adapter=source[source.index('sql_principals_execute()'):source.index('sql_principals_gate()')]
        self.assertIn('command sqlcmd -S tcp:127.0.0.1,1433 -C -U SA',adapter)
        self.assertIn('-b -x -l 15 -t 30',adapter)
        self.assertNotIn(' -P ',adapter)
        self.assertIn('>/dev/null 2>&1',adapter)

    def test_deterministic_public_payload_matches_source(self):
        raw=HELPER.read_bytes()
        compressed=base64.b64decode(HELPER.with_name('sql-principals.sh.gz.b64').read_text().strip(),validate=True)
        self.assertEqual(raw,gzip.decompress(compressed))
        # Header timestamp is fixed; compressor/zlib versions need not emit identical streams.
        self.assertEqual(bytes(4),compressed[4:8])
        self.assertLess(len(compressed),3000)

    def test_both_module_paths_wire_opt_in_references_and_byte_guard(self):
        template=(ROOT/'terraform/infra/data/user_data.sh').read_text(encoding='utf-8')
        self.assertIn("== '${SQL_PRINCIPAL_SHA256}'",template)
        self.assertIn("sha256sum | cut -d' ' -f1",template)
        self.assertIn('SQLCMDPASSWORD="$SA_PASS" sql_principals_prepare',template)
        self.assertIn('if [ "$SQL_SECURITY_PROFILE" = validated-v2 ]',template)
        self.assertNotIn('sql_principals_activate_runtime --ack',template)
        for env in ('dev','prod'):
            with self.subTest(env=env):
                directory=ROOT/f'terraform/modules/target/{env}/data'
                variables=(directory/'ordinary-variables.tf').read_text(encoding='utf-8')
                locals_=(directory/'ordinary-locals.tf').read_text(encoding='utf-8')
                main=(directory/'ordinary-main.tf').read_text(encoding='utf-8')
                self.assertIn('variable "sql_database_security"',variables)
                self.assertIn(f'secret:demo/{env}/db/sql-migrator-password-',variables)
                self.assertIn('var.sql_database_security == null ? "legacy-v1" : "validated-v2"',locals_)
                self.assertIn('filesha256(',locals_)
                self.assertIn('local.sql_full_user_data',main)
                self.assertIn('<= 21844',main)
                self.assertIn('validated-v2 requires the reviewed connection secret',(directory/'ordinary-outputs.tf').read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
