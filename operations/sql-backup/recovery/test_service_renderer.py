"""Real Bash argument validation only. No jq substitute or task materialization."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import prepare

ROOT = Path(__file__).resolve().parents[3]
BASH = '/bin/bash'


def audit(event, args):
    if event.startswith('socket.'):
        raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')
    if event == 'subprocess.Popen' and args[0] != BASH:
        raise AssertionError('ONLY_REVIEWED_BASH_VALIDATION_ALLOWED')


sys.addaudithook(audit)


class ServiceRendererTests(unittest.TestCase):
    def run_validation(self, updates=None, recovery=True, source_only=False):
        image = prepare.ACCOUNT + '.dkr.ecr.' + prepare.REGION + '.amazonaws.com/demo@sha256:' + 'e' * 64
        values = {'--env':'dev', '--region':prepare.REGION, '--account-id':prepare.ACCOUNT,
                  '--color':'green', '--image-uri':image,
                  '--db-secret-id':f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/connection-fixture:::' + 'd' * 32,
                  '--kms-key-id':prepare.TEXT_KEY,
                  '--template':str(ROOT / 'demo-api/deploy/task-definition.template.json'),
                  '--output':'candidate.review.json'}
        values.update(updates or {})
        args = [item for pair in values.items() for item in pair]
        if recovery:
            args.append('--recovery')
        # Normalize only this temporary source copy; preserve the original checkout.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'renderer.sh'
            source.write_text((ROOT / 'scripts/render-demo-api-taskdef.sh').read_text(encoding='utf-8'), encoding='utf-8')
            program = 'source "$1"; shift; '
            program += 'printf LOADED' if source_only else 'parse_args "$@"; validate_args; printf VALIDATED'
            env = {'PATH':'/usr/bin:/bin', 'HOME':tmp, 'LANG':'C.UTF-8',
                   'BASH_ENV':'', 'ENV':'', 'AWS_EC2_METADATA_DISABLED':'true',
                   'AWS_CONFIG_FILE':'/dev/null', 'AWS_SHARED_CREDENTIALS_FILE':'/dev/null'}
            result = subprocess.run([BASH, '--noprofile', '--norc', '-c', program,
                                     'validation-only', str(source), *args],
                                    env=env, cwd=tmp, text=True, capture_output=True, timeout=10)
            self.assertFalse((Path(tmp) / 'candidate.review.json').exists())
            return result

    def test_actual_recovery_arguments_validate_without_rendering(self):
        result = self.run_validation()
        self.assertEqual((result.returncode, result.stdout), (0, 'VALIDATED'), result.stderr)

    def test_recovery_rejects_unpinned_or_foreign_secret_image_key_and_prod(self):
        secret = f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/connection-fixture'
        for updates in ({'--db-secret-id':secret}, {'--db-secret-id':secret + '::AWSCURRENT:'},
                        {'--db-secret-id':secret.replace(prepare.ACCOUNT, '000000000000') + ':::' + 'd' * 32},
                        {'--kms-key-id':'alias/dev-kms-service'},
                        {'--kms-key-id':prepare.BACKUP_KEY.replace(prepare.REGION, 'us-west-2')},
                        {'--image-uri':'000000000000.dkr.ecr.us-east-1.amazonaws.com/demo@sha256:' + 'e' * 64},
                        {'--env':'prod'}):
            with self.subTest(updates=updates):
                self.assertNotEqual(self.run_validation(updates).returncode, 0)

    def test_normal_profile_still_allows_existing_unversioned_secret_and_default_key(self):
        result = self.run_validation({'--db-secret-id':f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/connection-fixture', '--kms-key-id':''}, recovery=False)
        self.assertEqual((result.returncode, result.stdout), (0, 'VALIDATED'), result.stderr)

    def test_source_is_inert_and_full_script_is_valid_bash(self):
        result = self.run_validation(source_only=True)
        self.assertEqual((result.returncode, result.stdout), (0, 'LOADED'), result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'renderer.sh'
            path.write_text((ROOT / 'scripts/render-demo-api-taskdef.sh').read_text(encoding='utf-8'), encoding='utf-8')
            result = subprocess.run([BASH, '-n', str(path)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
