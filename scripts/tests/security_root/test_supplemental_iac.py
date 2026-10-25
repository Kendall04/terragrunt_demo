"""Exact supplemental coverage, never runtime/deployment or AWS authority."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import model
from evaluator import Unsupported

ROOT=Path(__file__).resolve().parents[3]

class SupplementalIacTests(unittest.TestCase):
    def fixture(self):
        tmp=tempfile.TemporaryDirectory(prefix='ecs-iac-catalog-')
        self.addCleanup(tmp.cleanup)
        root=Path(tmp.name)
        for name in model.SUPPLEMENTAL_IAC_FILES|{model.SUPPLEMENTAL_CATALOG,'terraform/live/security/terragrunt.hcl'}:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        return root

    def test_actual_repository_surface_matches_without_adding_target_roots(self):
        doc=model.load_authority(ROOT)
        before=json.dumps(doc['wp6']['approvals'],sort_keys=True)
        generated=model.wiring(doc)
        supplemental=model.reviewed_supplemental_iac(ROOT)
        self.assertEqual(len(supplemental),11)
        self.assertFalse(supplemental&set(generated))
        model.admit_configuration_paths(ROOT,generated)
        self.assertEqual(before,json.dumps(model.load_authority(ROOT)['wp6']['approvals'],sort_keys=True))
        self.assertEqual(doc['wp6']['approvals'],{})

    def test_exact_fixture_passes_and_does_not_grant_execution(self):
        root=self.fixture();model.admit_configuration_paths(root,{})
        catalog=json.loads((root/model.SUPPLEMENTAL_CATALOG).read_text())
        self.assertIs(catalog['execution_authorized'],False)
        self.assertNotIn('CURRENT_APPROVAL',catalog['meaning'])

    def test_new_root_and_nested_auto_tfvars_are_not_admitted_by_directory(self):
        root=self.fixture()
        for name in ('terraform/infra/evil/main.tf','terraform/infra/sentinel-backup/unreviewed.auto.tfvars.json',
                     'operations/integrations/ssm-diagnostic/review/runtime/extra.tf',
                     'terraform/live/sentinel-backup/other.hcl'):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
            with self.subTest(path=name),self.assertRaisesRegex(Unsupported,'unadmitted/missing IaC'):
                model.admit_configuration_paths(root,{})
            path.unlink()

    def test_changed_known_resource_or_provider_checksum_is_rejected(self):
        root=self.fixture()
        for name in ('terraform/infra/sentinel-backup/modules/pipeline/main.tf.json',
                     'operations/sql-backup/recovery/provider.lock.hcl'):
            path=root/name;original=path.read_bytes();path.write_bytes(original+b'\n# unreviewed change\n')
            with self.subTest(path=name),self.assertRaisesRegex(Unsupported,'supplemental source drift'):
                model.reviewed_supplemental_iac(root)
            path.write_bytes(original)

    def test_missing_known_source_fails(self):
        root=self.fixture()
        (root/'terraform/infra/sentinel-backup/modules/observer/main.tf.json').unlink()
        with self.assertRaisesRegex(Unsupported,'supplemental source'):model.reviewed_supplemental_iac(root)

    def test_editing_catalog_cannot_self_approve_or_replace_paths(self):
        root=self.fixture();path=root/model.SUPPLEMENTAL_CATALOG;original=path.read_text()
        for mutate in (lambda c:c.update(execution_authorized=True),
                       lambda c:c['files'].update({'terraform/infra/evil/main.tf':{}}),
                       lambda c:next(iter(c['files'].values())).update(sha256_lf='a'*64)):
            value=json.loads(original);mutate(value);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(Unsupported,'catalog changed'):model.reviewed_supplemental_iac(root)

    def test_hashes_accept_only_crlf_normalization_not_content_changes(self):
        root=self.fixture()
        name='terraform/live/sentinel-backup/terragrunt.hcl'
        path=root/name;path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
        self.assertEqual(len(model.reviewed_supplemental_iac(root)),11)

    def test_symlink_is_rejected_before_following_source_bytes(self):
        root=self.fixture();path=root/'terraform/infra/sentinel-backup/main.tf.json'
        original=path.read_bytes();path.unlink()
        harmless=root/'outside-reference.json';harmless.write_bytes(original)
        try:path.symlink_to(harmless)
        except OSError as error:
            self.fail('Existing environment must support isolated link test: '+str(error.winerror if hasattr(error,'winerror') else error.errno))
        with self.assertRaisesRegex(Unsupported,'linked supplemental'):model.reviewed_supplemental_iac(root)

if __name__=='__main__':unittest.main(verbosity=2)
