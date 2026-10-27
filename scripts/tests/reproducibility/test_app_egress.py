import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]

class AppEgressTests(unittest.TestCase):
    def test_dev_and_prod_allow_https_and_exact_sql_destination(self):
        for env in ('dev', 'prod'):
            with self.subTest(env=env):
                text=(ROOT/f'terraform/modules/target/{env}/global/ordinary-security_rules.tf').read_text(encoding='utf-8')
                blocks=dict(re.findall(r'resource "aws_security_group_rule" "([^"]+)" \{(.*?)\n\}',text,re.S))
                outbound=[body for body in blocks.values() if '"egress"' in body and re.search(r'^\s*security_group_id\s*=\s*aws_security_group\.fargate_demo\.id\s*$',body,re.M)]
                self.assertEqual(2,len(outbound))
                internet=blocks['fargate_egress_any']
                self.assertRegex(internet,r'protocol\s*=\s*"tcp"')
                for port in ('from_port','to_port'):
                    self.assertRegex(internet,rf'{port}\s*=\s*443\b')
                    self.assertRegex(blocks['fargate_demo_egress_to_db'],rf'{port}\s*=\s*1433\b')
                self.assertIn('source_security_group_id = aws_security_group.db_instance.id',blocks['fargate_demo_egress_to_db'])
                self.assertNotIn('protocol          = "-1"',internet)
                # This increment must not pretend SQL bootstrapping no longer needs HTTP/NTP/etc.
                self.assertIn('protocol          = "-1"',blocks['db_egress_any'])

if __name__ == '__main__': unittest.main()
