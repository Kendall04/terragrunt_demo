"""Resolved module directories never hide controls under an unbound root."""
from pathlib import Path
import tempfile
import unittest
from discovery import Discovery

CONTROL = 'resource "aws_iam_role_policy" "unknown" {\n role = var.role\n policy = var.policy\n}\n'


class UnboundSourceCoverage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='e1-unbound-coverage-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def put(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
        return path

    def controls(self, env='dev'):
        return [r for r in Discovery(self.root, env=env).records
                if r.get('declaration', {}).get('type') == 'aws_iam_role_policy']

    def test_unbound_root_keeps_direct_and_transitive_child_unknown(self):
        self.put('trial/main.tf', 'module "child" {\n source = "./modules/child"\n}\n')
        self.put('trial/modules/child/main.tf', CONTROL+'module "nested" {\n source = "./nested"\n}\n')
        self.put('trial/modules/child/nested/main.tf', CONTROL)
        for env in ('dev', 'prod'):
            rows = self.controls(env)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row['admission'], 'UNSUPPORTED_APPLICABLE')
                self.assertEqual(row['applicability']['status'], 'APPLICABLE')
                self.assertEqual(row['affects'], ['*'])

    def test_other_environment_cannot_hide_same_child_called_by_unbound_root(self):
        self.put('shared/main.tf', CONTROL)
        self.put('prod-source/main.tf', 'module "child" {\n source = "../shared"\n}\n')
        self.put('terraform/live/prod/data/terragrunt.hcl', 'terraform {\n source = "../../../../prod-source"\n}\n')
        self.assertEqual(self.controls()[0]['admission'], 'UNSUPPORTED_NOT_APPLICABLE')
        rogue = self.put('trial/main.tf', 'module "same_child" {\n source = "../shared"\n}\n')
        self.assertEqual(self.controls()[0]['admission'], 'UNSUPPORTED_APPLICABLE')
        rogue.unlink()
        self.assertEqual(self.controls()[0]['admission'], 'UNSUPPORTED_NOT_APPLICABLE')

    def test_truly_uninvoked_module_keeps_structural_non_applicability(self):
        self.put('modules/uninvoked/main.tf', CONTROL)
        row = self.controls()[0]
        self.assertEqual(row['admission'], 'UNSUPPORTED_NOT_APPLICABLE')
        self.assertEqual(row['affects'], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
