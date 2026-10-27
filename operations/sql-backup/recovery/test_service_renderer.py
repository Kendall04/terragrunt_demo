"""Real offline Bash/jq rendering and review. Synthetic metadata; no AWS or SQL."""
from pathlib import Path
import json
import shutil
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
        raise AssertionError('ONLY_REVIEWED_BASH_RENDERER_ALLOWED')


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

    def materialize(self, value, recovery=True, overrides=None, alter_template=None):
        jq = shutil.which('jq')
        self.assertIsNotNone(jq, 'Real jq required in process PATH; no substitute or automatic install')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root/'scripts/render-demo-api-taskdef.sh';script.parent.mkdir()
            script.write_text((ROOT/'scripts/render-demo-api-taskdef.sh').read_text(encoding='utf-8'),encoding='utf-8')
            template = root/'demo-api/deploy/task-definition.template.json';template.parent.mkdir(parents=True)
            body = json.loads((ROOT/'demo-api/deploy/task-definition.template.json').read_text(encoding='utf-8'))
            if alter_template:alter_template(body)
            template.write_text(json.dumps(body),encoding='utf-8')
            deny = root/'deny';deny.mkdir();marker = root/'aws-forbidden'
            aws = deny/'aws';aws.write_text('#!/bin/sh\nprintf forbidden > "'+str(marker)+'"\nexit 97\n',encoding='utf-8');aws.chmod(0o700)
            out = root/'candidate.json'
            args = prepare.service_plan(value)['RendererArguments'][2:]
            if '--database-security-plan' in args:
                security_plan=root/'service-security.json';security_plan.write_text(json.dumps(value))
                args[args.index('--database-security-plan')+1]=str(security_plan)
            if not recovery:
                args.remove('--recovery')
                index=args.index('--kms-key-id');del args[index:index+2]
                args[args.index('--db-secret-id')+1] = value['Connection']['SecretArn']
            for key,new in (overrides or {}).items():args[args.index(key)+1] = new
            args[args.index('--output')+1] = str(out)
            env = {'PATH':str(deny)+':'+str(Path(jq).parent)+':/usr/bin:/bin',
                   'HOME':tmp,'LANG':'C.UTF-8','BASH_ENV':'','ENV':'',
                   'AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null',
                   'AWS_EC2_METADATA_DISABLED':'true'}
            result = subprocess.run([BASH,'--noprofile','--norc',str(script),*args],
                                    cwd=tmp,env=env,text=True,capture_output=True,timeout=10)
            self.assertFalse(marker.exists(),'Renderer escaped to AWS')
            payload = out.read_bytes() if out.exists() else None
            return result,payload

    def real_fixture(self, color='green'):
        value = json.loads((Path(__file__).parent/'fixtures/service-cutover.synthetic.json').read_text(encoding='utf-8'))
        if color == 'blue':
            d=value['Delivery'];d['active_color']='green';d['candidate_color']='blue'
            d['active_target_arn'],d['candidate_target_arn'] = d['candidate_target_arn'],d['active_target_arn']
        return value

    def test_real_jq_materializes_both_recovery_colors_and_full_artifact_review(self):
        for color in ('blue','green'):
            value = self.real_fixture(color)
            result,payload=self.materialize(value)
            self.assertEqual(result.returncode,0,result.stderr)
            candidate=json.loads(payload)
            report=prepare.service_taskdef(value,candidate)
            self.assertEqual(report['Status'],'OFFLINE_RECOVERY_TASKDEF_REVIEW_PASS')
            self.assertFalse(report['AllowsActivation']);self.assertFalse(report['PublicApiRecoveryProven'])
            env={e['name']:e['value'] for e in candidate['containerDefinitions'][0]['environment']}
            self.assertEqual(env['Database__RunMigrationsOnStartup'],'false')
            self.assertNotIn('environment',candidate['containerDefinitions'][1])
            self.assertNotIn('secrets',candidate['containerDefinitions'][1])

    def test_real_strict_renderer_binds_all_api_security_fields_and_refuses_drift(self):
        value=self.real_fixture()
        value['DatabaseSecurity']={'Profile':'validated-v2','RuntimeUser':'recovery_app',
            'MigrationUser':'recovery_migrator','MigrationSecretArn':f'arn:aws:secretsmanager:{prepare.REGION}:{prepare.ACCOUNT}:secret:demo/dev/db/sql-migrator-password-AbCdEf',
            'CertificateHostName':'sql.demo.internal'}
        value['ColdReceipt'].update(DatabaseSecurity=value['DatabaseSecurity'],PrincipalAdoption='RUNTIME_MINIMAL_MIGRATOR_DISABLED')
        result,payload=self.materialize(value)
        self.assertEqual(result.returncode,0,result.stderr)
        task=json.loads(payload);prepare.service_taskdef(value,task)
        env={e['name']:e['value'] for e in task['containerDefinitions'][0]['environment']}
        self.assertEqual(env['Database__SecurityProfile'],'validated-v2')
        self.assertEqual(env['Database__ExpectedSqlEndpoint'],'tcp:10.77.1.8,1433')
        self.assertEqual(env['Database__ExpectedCertificateHostName'],'sql.demo.internal')
        self.assertNotIn('DB_MIGRATION_CONN_STRING',env)
        self.assertNotIn('MigrationSecretArn',str(task))
        self.assertNotIn('environment',task['containerDefinitions'][1])
        for key,bad in (('Database__SecurityProfile','legacy-v1'),('Database__ExpectedSqlEndpoint','tcp:10.0.0.1,1433'),
                        ('Database__ExpectedCertificateHostName','wrong.invalid')):
            altered=json.loads(payload)
            next(e for e in altered['containerDefinitions'][0]['environment'] if e['name']==key)['value']=bad
            with self.assertRaises(ValueError):prepare.service_taskdef(value,altered)

    def test_real_normal_render_preserves_unversioned_secret_and_migration_defaults(self):
        value=self.real_fixture();result,payload=self.materialize(value,recovery=False)
        self.assertEqual(result.returncode,0,result.stderr)
        candidate=json.loads(payload);app=candidate['containerDefinitions'][0]
        env={e['name']:e['value'] for e in app['environment']}
        self.assertNotIn('Database__RunMigrationsOnStartup',env)
        self.assertEqual(env['KMS_KEY_ID'],'alias/dev-kms-service')
        self.assertEqual(app['secrets'][0]['valueFrom'],value['Connection']['SecretArn'])
        with self.assertRaises(ValueError):prepare.service_taskdef(value,candidate)

    def test_real_renderer_refuses_bad_recovery_inputs_before_creating_output(self):
        value=self.real_fixture()
        for bad in ({'--db-secret-id':value['Connection']['SecretArn']},
                    {'--image-uri':value['Release']['image_uri'].replace(prepare.ACCOUNT,'000000000000')},
                    {'--kms-key-id':'alias/dev-kms-service'}):
            result,payload=self.materialize(value,overrides=bad)
            self.assertNotEqual(result.returncode,0)
            self.assertIsNone(payload)

    def test_actual_rendered_template_drift_and_probe_injection_fail_review(self):
        value=self.real_fixture()
        for mutate in (lambda x:x['containerDefinitions'][1].update(essential=True),
                       lambda x:x['containerDefinitions'][0].update(command=['unreviewed']),
                       lambda x:x['containerDefinitions'][0]['environment'].append({'name':'DB_CONN_STRING','value':'SYNTHETIC_PRIVATE'})):
            result,payload=self.materialize(value,alter_template=mutate)
            self.assertEqual(result.returncode,0,result.stderr)
            with self.assertRaisesRegex(ValueError,'RECOVERY_TASKDEF_NOT_EXACT_REVIEWED_PROJECTION'):
                prepare.service_taskdef(value,json.loads(payload))

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
