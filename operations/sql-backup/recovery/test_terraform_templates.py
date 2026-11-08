"""Actual Terraform 1.13.4 core evaluation, offline, with no providers/backend/AWS.

Run separately from the recovery unit suite's subprocess-denying audit hook.
Temporary JSON/output plans are small and removed; nothing is applied.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import prepare


class TerraformTemplateTests(unittest.TestCase):
    def evaluate(self, values):
        terraform = shutil.which('terraform')
        self.assertIsNotNone(terraform, 'Use existing Terraform only; no install')
        env = {k: v for k, v in os.environ.items() if not k.startswith(('AWS_', 'TF_'))}
        env.update(AWS_CONFIG_FILE=os.devnull, AWS_SHARED_CREDENTIALS_FILE=os.devnull,
                   AWS_EC2_METADATA_DISABLED='true', CHECKPOINT_DISABLE='1', TF_IN_AUTOMATION='1')
        with tempfile.TemporaryDirectory(prefix='ecs-tf-template-') as directory:
            root = Path(directory)
            config = {'terraform': {'required_version': '= 1.13.4'},
                      'output': {name: {'value': value} for name, value in values.items()}}
            (root / 'main.tf.json').write_text(json.dumps(config), encoding='utf-8')
            env['TF_DATA_DIR'] = str(root / '.terraform')
            args = [terraform, '-chdir=' + directory]
            result = subprocess.run(args + ['plan', '-refresh=false', '-input=false', '-lock=false',
                                             '-no-color', '-out=output.tfplan'], env=env,
                                    capture_output=True, text=True, timeout=20)
            if result.returncode:
                return result.returncode, '\n'.join(line for line in (result.stdout + result.stderr).splitlines() if line.startswith('Error:')), None
            shown = subprocess.run(args + ['show', '-json', 'output.tfplan'], env=env,
                                   capture_output=True, text=True, timeout=10, check=True)
            data = json.loads(shown.stdout)
            return 0, '', {name: v['value'] for name, v in data['planned_values']['outputs'].items()}

    def test_raw_bash_interpolation_reproduces_real_terraform_failure(self):
        code, diagnostic, _ = self.evaluate({'raw': "echo '${db:Status-Status}'\n"})
        self.assertNotEqual(code, 0)
        self.assertIn('Extra characters after interpolation expression', diagnostic)

    def test_both_hosts_evaluate_to_exact_original_bootstrap_bytes(self):
        original = Path(__file__).with_name('bootstrap.sh').read_bytes()
        root, _ = prepare.render('r20261021az1', original.decode('utf-8'))
        code, diagnostic, values = self.evaluate({label: root['resource']['aws_instance'][label]['user_data'] for label in ('a', 'b')})
        self.assertEqual(code, 0, diagnostic)
        for label in ('a', 'b'):
            self.assertEqual(values[label].encode('utf-8'), original)
            self.assertEqual(hashlib.sha256(values[label].encode()).hexdigest(), hashlib.sha256(original).hexdigest())

    def test_literal_dollar_percent_braces_are_preserved_without_extra_layer(self):
        # These are raw Bash bytes, including sequences already resembling HCL escapes.
        cases = ["${name}\n", "${db:Status-Status}\n${BASH_SOURCE[0]}\n",
                 "$${name}\n$$${name}\n", "%{ if ignored }literal%{ endif }\n",
                 "%%{ literal }\n%%%{ literal }\n", "printf '%s' '$x %% ${x}'\r\n"]
        encoded = {}
        for i, original in enumerate(cases):
            root, _ = prepare.render('r20261021az1', original)
            for label in ('a', 'b'):
                encoded[f'case{i}_{label}'] = root['resource']['aws_instance'][label]['user_data']
        code, diagnostic, values = self.evaluate(encoded)
        self.assertEqual(code, 0, diagnostic)
        for i, original in enumerate(cases):
            for label in ('a', 'b'):
                self.assertEqual(values[f'case{i}_{label}'].encode(), original.encode())


if __name__ == '__main__':
    unittest.main()
