"""Offline Bash fixtures only; no main/bootstrap, Linux install, AWS or network.

Run separately from test_recovery.py, whose audit hook prohibits subprocesses.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

BOOT = Path(__file__).with_name('bootstrap.sh')
BASH = Path(r'C:\Program Files\Git\bin\bash.exe') if os.name == 'nt' else Path(shutil.which('bash') or '/bin/bash')


class BootstrapTests(unittest.TestCase):
    def candidate_fixture(self, changed_package=None, changed_policy=None, installed=False):
        policies = {}
        for package in ('mssql-server', 'mssql-tools18', 'unixodbc-dev'):
            version = {'mssql-server': '16.0.4236.2-2', 'mssql-tools18': '18.5.1.1-1', 'unixodbc-dev': '2.3.11-3'}[package]
            origin = 'https://packages.microsoft.com/ubuntu/22.04/' + ('mssql-server-2022' if package == 'mssql-server' else 'prod')
            policies[package] = (f'{package}:\n  Installed: {version if installed else "(none)"}\n  Candidate: {version}\n'
                                 f'  Version table:\n {"***" if installed else "   "} {version} 500\n'
                                 f'        500 {origin} jammy/main amd64 Packages\n' +
                                 ('        100 /var/lib/dpkg/status\n' if installed else ''))
        if changed_package:
            policies[changed_package] = changed_policy
        cases = '\n'.join(f'{package}) printf %s {shlex.quote(value)} ;;' for package, value in policies.items())
        return self.run_bash('apt-cache() { case "$2" in\n' + cases + '\nesac; }\nrun_stage sql_candidates check_candidates')

    def run_bash(self, body, source=True):
        self.assertTrue(BASH.is_file(), 'Existing Bash required; do not install one for this suite')
        path = str(BOOT.resolve()).replace('\\', '/')
        if os.name == 'nt':
            path = '/' + path[0].lower() + path[2:]
        with tempfile.TemporaryDirectory(prefix='ecs-bootstrap-fixture-') as directory:
            env = {'PATH': str(BASH.parent.parent / 'usr/bin') if os.name == 'nt' else '/usr/bin:/bin',
                   'SystemRoot': os.environ.get('SystemRoot', ''), 'TEMP': directory, 'TMP': directory,
                   'LC_ALL': 'C', 'FIXTURE_DIR': directory.replace('\\', '/')}
            setup = 'set -Eeuo pipefail\n'
            if source:
                setup += 'source "$1"\n'
            # Failing guards: a fixture must explicitly replace any intended stub.
            setup += '\n'.join(f'{name}() {{ echo UNEXPECTED_EXTERNAL_COMMAND >&2; return 99; }}' for name in
                               ('aws', 'apt-get', 'curl', 'gpg', 'timeout', 'systemctl', 'runuser', 'install')) + '\n'
            return subprocess.run([str(BASH), '--noprofile', '--norc', '-c', setup + body, 'fixture', path],
                                  env=env, capture_output=True, text=True, timeout=8)

    def test_original_suppressed_cause_but_returned_apt_exit(self):
        original = '''
trap 'unset SA_PASS SQLCMDPASSWORD; echo RECOVERY_BOOTSTRAP_FAILED' ERR
timeout() { echo 'NO_PUBKEY fixture-public-key'; return 100; }
timeout 600 apt-get update -y >/dev/null 2>&1
'''
        result = self.run_bash(original, source=False)
        self.assertEqual(result.returncode, 100)
        self.assertEqual(result.stdout.strip(), 'RECOVERY_BOOTSTRAP_FAILED')
        self.assertEqual(result.stderr, '')

    def test_source_is_inert(self):
        result = self.run_bash(':')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_failure_categories_hide_raw_output_and_preserve_exit(self):
        for raw, category, code in [
            ('NO_PUBKEY fixture-sensitive-output', 'APT_SIGNATURE', 100),
            ('does not have a Release file', 'APT_RELEASE', 100),
            ('Unable to locate package private-value', 'PACKAGE_CANDIDATE', 100),
            ('unmet dependencies private-value', 'PACKAGE_DEPENDENCY', 100),
            ('Temporary failure resolving private-value', 'DNS', 100),
            ('Certificate verification failed private-value', 'TLS', 100),
            ('Failed to fetch private-value', 'NETWORK', 100),
            ('No space left on device private-value', 'DISK', 1),
            ('EULA private-value', 'EULA', 1),
            ('private-value', 'COMMAND_FAILED', 124),
        ]:
            with self.subTest(category=category):
                result = self.run_bash(f"fail() {{ printf '%s' '{raw}'; return {code}; }}\nrun_stage sql_index fail")
                self.assertEqual(result.returncode, code)
                self.assertIn(f'stage=sql_index exit={code} category={category}', result.stdout)
                self.assertNotIn(raw, result.stdout + result.stderr)
                self.assertNotIn('private-value', result.stdout + result.stderr)

    def test_success_hides_command_output(self):
        result = self.run_bash("ok() { echo private-value >&2; }\nrun_stage sql_packages ok")
        self.assertEqual(result.returncode, 0)
        self.assertIn('RECOVERY_STAGE_OK stage=sql_packages', result.stdout)
        self.assertNotIn('private-value', result.stdout + result.stderr)

    def test_secret_failure_never_classifies_value_and_clears_secrets(self):
        result = self.run_bash('''
SA_PASS=fixture-secret; export SQLCMDPASSWORD=fixture-secret
trap '[[ ! -v SA_PASS && ! -v SQLCMDPASSWORD && ! -v probe ]] && echo CLEARED' EXIT
fail() { echo 'EULA fixture-secret'; echo 'NO_PUBKEY fixture-secret' >&2; return 254; }
secret_stage sa_secret fail
''')
        self.assertEqual(result.returncode, 254)
        self.assertIn('exit=254 category=SECRET_OPERATION_FAILED', result.stdout)
        self.assertIn('CLEARED', result.stdout)
        self.assertNotIn('fixture-secret', result.stdout + result.stderr)
        self.assertNotIn('APT_SIGNATURE', result.stdout)

    def test_unexpected_trap_preserves_code_without_command_text(self):
        result = self.run_bash('''
STAGE=fixture
trap 'stage_fail "$?" UNEXPECTED' ERR
failure() { return 42; }
failure fixture-secret
''')
        self.assertEqual(result.returncode, 42)
        self.assertIn('stage=fixture exit=42 category=UNEXPECTED', result.stdout)
        self.assertNotIn('fixture-secret', result.stdout + result.stderr)

    def test_platform_rejects_root_architecture_or_distribution_mismatch(self):
        for uid, kernel, machine, arch, distro, version, code in [
            ('0', 'Linux', 'x86_64', 'amd64', 'ubuntu', '22.04', 0),
            ('1000', 'Linux', 'x86_64', 'amd64', 'ubuntu', '22.04', 77),
            ('0', 'Darwin', 'x86_64', 'amd64', 'ubuntu', '22.04', 65),
            ('0', 'Linux', 'aarch64', 'arm64', 'ubuntu', '22.04', 65),
            ('0', 'Linux', 'x86_64', 'arm64', 'ubuntu', '22.04', 65),
            ('0', 'Linux', 'x86_64', 'amd64', 'debian', '12', 65),
            ('0', 'Linux', 'x86_64', 'amd64', 'ubuntu', '24.04', 65),
        ]:
            with self.subTest(uid=uid, kernel=kernel, machine=machine, arch=arch, distro=distro, version=version):
                result = self.run_bash(f'''
id() {{ echo {uid}; }}
uname() {{ if [[ "$1" == -s ]]; then echo {kernel}; else echo {machine}; fi; }}
dpkg() {{ echo {arch}; }}
load_os_release() {{ ID={distro}; VERSION_ID={version}; }}
run_stage platform check_platform
''')
                self.assertEqual(result.returncode, code)

    def test_candidate_missing_or_wrong_repository_refuses_before_install(self):
        for candidate, origin, code in [('16.0.1-1', 'https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022', 0),
                                        ('(none)', 'https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022', 65),
                                        ('16.0.1-1', 'https://unrelated.invalid/ubuntu/22.04/prod', 65)]:
            with self.subTest(candidate=candidate, origin=origin):
                policy = f'mssql-server:\n  Installed: (none)\n  Candidate: {candidate}\n  Version table:\n     16.0.1-1 500\n        500 {origin} jammy/main amd64 Packages\n'
                result = self.candidate_fixture('mssql-server', policy)
                self.assertEqual(result.returncode, code)
                self.assertNotIn('UNEXPECTED_EXTERNAL_COMMAND', result.stdout + result.stderr)

    def test_realistic_candidate_and_installed_status_metadata_pass(self):
        for installed in (False, True):
            with self.subTest(installed=installed):
                result = self.candidate_fixture(installed=installed)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_candidate_origin_rejects_lower_microsoft_decoy_and_ambiguity(self):
        allowed = '500 https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy/main amd64 Packages'
        foreign = '500 https://unrelated.invalid/sql jammy/main amd64 Packages'
        cases = {
            'foreign_candidate_lower_microsoft': f'     99.0.0-1 500\n        {foreign}\n     16.0.1-1 500\n        {allowed}\n',
            'candidate_metadata_missing_lower_microsoft': f'     99.0.0-1 500\n     16.0.1-1 500\n        {allowed}\n',
            'two_candidate_origins': f'     99.0.0-1 500\n        {allowed}\n        {foreign}\n',
            'two_candidate_blocks': f'     99.0.0-1 500\n        {allowed}\n     99.0.0-1 500\n        {allowed}\n',
            'duplicate_candidate_origin': f'     99.0.0-1 500\n        {allowed}\n        {allowed}\n',
            'installed_status_without_repository': f' *** 99.0.0-1 100\n        100 /var/lib/dpkg/status\n     16.0.1-1 500\n        {allowed}\n',
            'no_candidate_block': f'     16.0.1-1 500\n        {allowed}\n',
            'wrong_microsoft_product': '     99.0.0-1 500\n        500 https://packages.microsoft.com/ubuntu/22.04/prod jammy/main amd64 Packages\n',
            'wrong_architecture': f'     99.0.0-1 500\n        {allowed.replace("amd64", "arm64")}\n',
            'wrong_distribution': f'     99.0.0-1 500\n        {allowed.replace("jammy/main", "noble/main")}\n',
        }
        for name, table in cases.items():
            with self.subTest(case=name):
                result = self.candidate_fixture('mssql-server', 'mssql-server:\n  Installed: (none)\n  Candidate: 99.0.0-1\n  Version table:\n' + table)
                self.assertEqual(result.returncode, 65, result.stdout + result.stderr)
                self.assertNotIn('unrelated.invalid', result.stdout + result.stderr)

    def test_candidate_metadata_required_for_tools_and_odbc_dependency(self):
        for package in ('mssql-tools18', 'unixodbc-dev'):
            with self.subTest(package=package):
                result = self.candidate_fixture(package, f'{package}:\n  Installed: (none)\n  Candidate: 99.0.0-1\n  Version table:\n     99.0.0-1 500\n        500 https://unrelated.invalid/sql jammy/main amd64 Packages\n     18.5.1.1-1 500\n        500 https://packages.microsoft.com/ubuntu/22.04/prod jammy/main amd64 Packages\n')
                self.assertEqual(result.returncode, 65)

    def test_candidate_table_requires_one_matching_package_header(self):
        table = '     16.0.1-1 500\n        500 https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy/main amd64 Packages\n'
        policies = ['mssql-server:\n  Candidate: 16.0.1-1\n' + table,
                    'unrelated-package:\n  Candidate: 16.0.1-1\n  Version table:\n' + table,
                    'mssql-server:\n  Candidate: 16.0.1-1\n  Version table:\n' + table + '  Version table:\n']
        for policy in policies:
            with self.subTest(policy=policy):
                result = self.candidate_fixture('mssql-server', policy)
                self.assertEqual(result.returncode, 65)

    def test_odbc_candidate_official_jammy_metadata_passes(self):
        for uri, suite in [('http://us-east-1.ec2.archive.ubuntu.com/ubuntu', 'jammy-updates/main'),
                           ('http://archive.ubuntu.com/ubuntu', 'jammy/main'),
                           ('http://security.ubuntu.com/ubuntu', 'jammy-security/main')]:
            with self.subTest(uri=uri):
                result = self.candidate_fixture('unixodbc-dev', f'unixodbc-dev:\n  Installed: (none)\n  Candidate: 2.3.9-5ubuntu0.1\n  Version table:\n     2.3.9-5ubuntu0.1 500\n        500 {uri} {suite} amd64 Packages\n')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_odbc_candidate_can_have_only_recognized_security_and_update_sources(self):
        result = self.candidate_fixture('unixodbc-dev', '''unixodbc-dev:
  Installed: 2.3.9-5ubuntu0.1
  Candidate: 2.3.9-5ubuntu0.1
  Version table:
 *** 2.3.9-5ubuntu0.1 500
        500 http://us-east-1.ec2.archive.ubuntu.com/ubuntu jammy-updates/main amd64 Packages
        500 http://security.ubuntu.com/ubuntu jammy-security/main amd64 Packages
        100 /var/lib/dpkg/status
     2.3.9-5 500
        500 http://archive.ubuntu.com/ubuntu jammy/main amd64 Packages
''')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_repository_unreadable_by_apt_is_a_separate_stage(self):
        result = self.run_bash('''
printf public-key >"$FIXTURE_DIR/key.gpg"
runuser() { [[ "$1 $2 $3 $4 $5" == '-u _apt -- test -r' ]] || return 99; return 13; }
run_stage repository_access check_repository_access "$FIXTURE_DIR/key.gpg"
''')
        self.assertEqual(result.returncode, 13)
        self.assertIn('stage=repository_access exit=13', result.stdout)

    def test_secret_read_exit_and_empty_result_are_distinct_no_value_logged(self):
        for body, code in [('echo fixture-secret; return 254', 254), ('echo None', 65), ('echo fixture-secret', 0)]:
            with self.subTest(code=code):
                result = self.run_bash(f'aws() {{ {body}; }}\nsecret_stage sa_secret read_sa_secret' +
                                       ('\n[[ "$SA_PASS" == fixture-secret ]]' if code == 0 else ''))
                self.assertEqual(result.returncode, code)
                self.assertNotIn('fixture-secret', result.stdout + result.stderr)

    def test_setup_keeps_consent_and_password_in_environment_not_arguments(self):
        result = self.run_bash('''
SA_PASS=fixture-secret
timeout() { [[ "$ACCEPT_EULA" == Y && "$MSSQL_PID" == Express && "$MSSQL_SA_PASSWORD" == fixture-secret && "$*" != *fixture-secret* ]]; }
secret_stage express_setup setup_sql
''')
        self.assertEqual(result.returncode, 0)
        self.assertNotIn('fixture-secret', result.stdout + result.stderr)

    def test_readiness_authorization_denial_does_not_poll_again(self):
        result = self.run_bash('''
SA_PASS=fixture-secret; STAGE=sql_readiness
function /opt/mssql-tools18/bin/sqlcmd { echo 'Login failed 18456 fixture-secret'; return 7; }
sleep() { echo UNEXPECTED_RETRY; return 99; }
wait_sql
''')
        self.assertEqual(result.returncode, 7)
        self.assertIn('category=SQL_AUTHORIZATION_DENIED', result.stdout)
        self.assertNotIn('UNEXPECTED_RETRY', result.stdout)
        self.assertNotIn('fixture-secret', result.stdout + result.stderr)

    def test_public_metadata_permissions_and_secret_boundary_order(self):
        body = BOOT.read_text()
        self.assertIn('chmod 0644 /etc/apt/keyrings/recovery-microsoft.gpg /etc/apt/sources.list.d/recovery-sql.list /etc/apt/sources.list.d/recovery-tools.list', body)
        main = body.split('bootstrap_main() {', 1)[1]
        for stage in ('platform', 'fresh_host', 'repository_access', 'sql_candidates', 'sql_dependencies', 'sql_installation'):
            self.assertLess(main.index('run_stage ' + stage), main.index('secret_stage sa_secret'))
        self.assertNotIn('set -x', body)
        self.assertNotIn('BASH_COMMAND', body)

    def test_readiness_success_and_exhaustion_clear_values_preserve_last_code(self):
        for code in (0, 6):
            with self.subTest(code=code):
                result = self.run_bash(f'''
SA_PASS=fixture-secret; STAGE=sql_readiness
trap '[[ ! -v SA_PASS && ! -v SQLCMDPASSWORD && ! -v probe ]] && echo CLEARED' EXIT
function /opt/mssql-tools18/bin/sqlcmd {{ echo fixture-secret; return {code}; }}
seq() {{ printf '1\\n2\\n'; }}
sleep() {{ :; }}
wait_sql
''')
                self.assertEqual(result.returncode, code)
                self.assertIn('CLEARED', result.stdout)
                self.assertNotIn('fixture-secret', result.stdout + result.stderr)
                if code:
                    self.assertIn('exit=6 category=SQL_NOT_READY', result.stdout)


if __name__ == '__main__':
    unittest.main()
