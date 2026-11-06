"""Recovery retention is a DEV opt-in, never a state address migration."""
import json
from pathlib import Path
import unittest
import model


class RecoveryDiskTests(unittest.TestCase):
    def test_source_root_can_be_preserved_without_changing_resource_identity(self):
        root = Path(__file__).resolve().parents[3]
        files = model.wiring(json.loads((root/'terraform/infra/security/authority.json').read_text()))
        dev = files['terraform/modules/target/dev/data/ordinary-main.tf']
        prod = files['terraform/modules/target/prod/data/ordinary-main.tf']
        self.assertIn('delete_on_termination = !var.recovery_preserve_root_volume', dev)
        self.assertEqual(1, dev.count('resource "aws_instance" "db"'))
        self.assertNotIn('create_before_destroy', dev)
        self.assertNotIn('recovery_preserve_root_volume', prod)
        var = files['terraform/modules/target/dev/data/ordinary-variables.tf'].split(
            'variable "recovery_preserve_root_volume"', 1)[1]
        self.assertIn('default     = false', var)
        self.assertIn('nullable    = false', var)
