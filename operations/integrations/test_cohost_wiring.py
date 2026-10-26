"""Source-backed bootstrap/schedule contracts. No Terraform init, providers, AWS or services."""
import ast
import base64
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
class CohostWiring(unittest.TestCase):
    def test_real_target_null_opt_in_preserves_original_template_and_no_new_resources(self):
        main=(ROOT/'terraform/modules/target/dev/data/ordinary-main.tf').read_text()
        locals_=(ROOT/'terraform/modules/target/dev/data/ordinary-locals.tf').read_text()
        variables=(ROOT/'terraform/modules/target/dev/data/ordinary-variables.tf').read_text()
        self.assertIn('var.sql_backup_cohost == null ? local.sql_base_user_data',main)
        self.assertIn('cohost-bootstrap.sh.tftpl',main);self.assertIn('base64encode(jsonencode(var.sql_backup_cohost))',main)
        for key in ['AWS_REGION','APP_DB','APP_USER','SA_SECRET_ARN','APP_SECRET_ARN']:self.assertIn(key,locals_)
        self.assertIn('enable_after_native_gates = optional(bool, false)',variables)
        self.assertIn('length(base64encode(jsonencode(var.sql_backup_cohost))) <= 4096',variables)
        self.assertNotIn('remote-exec',main);self.assertNotIn('provisioner',main)
        self.assertEqual(main.count('resource "aws_instance"'),1)
    def test_real_external_rule_lambda_and_watchdog_configuration_are_connected(self):
        root=json.loads((ROOT/'terraform/infra/sentinel-backup/main.tf.json').read_text())
        module=json.loads((ROOT/'terraform/infra/sentinel-backup/modules/pipeline/main.tf.json').read_text());r=module['resource']
        self.assertEqual(root['module']['pipeline']['dispatch_schedule_enabled'],'${var.dispatch_schedule_enabled}')
        self.assertEqual(r['aws_cloudwatch_event_target']['dispatch']['arn'],'${aws_lambda_function.dispatch.arn}')
        self.assertEqual(r['aws_lambda_function']['dispatch']['handler'],'Ecs.Backup.Managed::Ecs.Backup.Managed.DispatchFunction::Reconcile')
        env=r['aws_lambda_function']['dispatch']['environment']['variables']
        self.assertEqual(env['SENTINEL_WATCHDOG_SECONDS'],'${tostring(var.config.watchdog_seconds)}')
        self.assertEqual(env['SENTINEL_OBSERVER_EXPECTED_UP'],'${tostring(var.config.observer_expected_up)}')
        code=(ROOT/'operations/integrations/Ecs.Backup.Managed/Functions.cs').read_text()
        self.assertIn('BackupObserverWatchdog.Evaluate(',code)
        self.assertIn('var.config.sender_role_arn',r['aws_sqs_queue_policy']['ingestion']['policy'])
        self.assertTrue(r['aws_sqs_queue']['ingestion']['sqs_managed_sse_enabled'])
        addresses=sum(len(items) for items in r.values());self.assertEqual(addresses,29)
    def test_bootstrap_python_compiles_and_excludes_denied_transports_and_profile_fallback(self):
        template=(ROOT/'terraform/infra/data/cohost-bootstrap.sh.tftpl').read_text()
        inline=template.split("<<'SQL_BACKUP_COHOST_BOOTSTRAP'\n",1)[1].split('\nSQL_BACKUP_COHOST_BOOTSTRAP',1)[0]
        ast.parse(inline.replace('${cohost_config}',base64.b64encode(b'{}').decode()))
        for required in ['--version-id','--expected-bucket-owner','PACKAGE_SHA_MISMATCH','SAFE_PACKAGE_MEMBERS_REQUIRED','package.install(','cohost.verify()','cohost.activate(apply=True,confirmation=sha)','enable_after_native_gates']:
            self.assertIn(required,template)
        for forbidden in ['send-command','start-session','ssh ','--profile','set -x','SQLCMDPASSWORD','secretsmanager get-secret-value']:
            self.assertNotIn(forbidden,template)
        self.assertLess(template.index("if v['enable_after_native_gates']"),template.index('cohost.activate(apply=True,confirmation=sha)'))
if __name__=='__main__':unittest.main(verbosity=2)
