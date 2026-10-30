"""Native provider provenance is retained; historical fixtures cannot erase current unknowns."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import history
import model
import retired
import wp5
from discovery import Discovery

ROOT=Path(__file__).resolve().parents[3]


class OriginAndHistoricalTests(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='ecs-historical-origin-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        for name in history.NON_BASELINE_REVIEW_INPUTS:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,path)
        directory=root/'ci/authority/target';directory.mkdir(parents=True)
        (directory/'legacy-sources.json').write_text(json.dumps({'sources':{}}))
        (root/'ci/authority/source-inventory.json').write_text(json.dumps({'sources':{}}))
        return root

    def test_windows_origin_matches_all_five_existing_runtime_locks(self):
        receipt=json.loads((ROOT/'operations/sql-backup/recovery/provider-origin-verification.json').read_text())
        self.assertEqual(receipt['status'],'OFFICIAL_SIGNED_ZIP_AND_H1_VERIFIED')
        self.assertEqual(receipt['archiveSha256'],'9f8b909d3ec50ade83c8062290378b1ec553edef6a447c56dadc01a99f4eaa93')
        self.assertEqual(receipt['fingerprint'],'C874011F0AB405110D02105534365D9472D7468F')
        self.assertFalse(receipt['providerExecuted']);self.assertFalse(receipt['providerInstalled'])
        selected=wp5.dev_runtime_lock(ROOT)
        self.assertIn(receipt['packageH1'],selected)
        for layer in ('global','data','platform','apps','edge'):
            path=ROOT/f'terraform/modules/target/dev/{layer}/.terraform.lock.hcl'
            self.assertEqual(path.read_text(),selected)
        generated=wp5.configuration({})
        for layer in ('global','data','platform','apps','edge'):
            self.assertEqual(generated[f'terraform/modules/target/dev/{layer}/.terraform.lock.hcl'],selected)
        self.assertNotEqual(generated['terraform/modules/target/dev/shared/.terraform.lock.hcl'],selected)
        self.assertNotIn(receipt['packageH1'],generated['terraform/modules/target/prod/global/.terraform.lock.hcl'])
        security=model.security_provider_lock(ROOT)
        historical=retired.source(ROOT,'terraform/live/dev/shared/.terraform.lock.hcl').read_text().split(
            'provider "registry.terraform.io/hashicorp/tls"',1)[0].rstrip()+'\n'
        added='    "'+receipt['packageH1']+'",\n'
        self.assertEqual(security.count(added),1)
        self.assertEqual(security.replace(added,''),historical)
        self.assertIn('version     = "5.100.0"',security)
        self.assertIn('constraints = "~> 5.50"',security)
        self.assertEqual((ROOT/'terraform/infra/security/.terraform.lock.hcl').read_text(),security)
        self.assertEqual(model.wiring(model.load_authority(ROOT))['terraform/infra/security/.terraform.lock.hcl'],security)

    def test_revalidated_bootstrap_still_rejects_future_payload_drift(self):
        from test_wp2a import FoundationTests
        from model import validate_repository
        fixture=FoundationTests();self.addCleanup(fixture.doCleanups)
        root=fixture.fixture();path=root/'terraform/infra/data/user_data.sh'
        path.write_text(path.read_text()+'\n# future unreviewed payload\n')
        with self.assertRaisesRegex(ValueError,'WP5_SOURCE_ADMISSION_FAILURE: package/installation/active-contract drift'):
            validate_repository(root)

    def test_changed_provider_bytes_cannot_redefine_generator_expectations(self):
        root=self.fixture();path=root/wp5.DEV_RUNTIME_LOCK;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/wp5.DEV_RUNTIME_LOCK,path)
        self.assertEqual(wp5.dev_runtime_lock(root),wp5.dev_runtime_lock(ROOT))
        path.write_text(path.read_text().replace('H3mU/7UR','X3mU/7UR'))
        with self.assertRaisesRegex(ValueError,'provider lock drift'):wp5.dev_runtime_lock(root)
        historical=root/'historical.lock.hcl'
        original=retired.source(ROOT,'terraform/live/dev/shared/.terraform.lock.hcl').read_text()
        for altered in (original.replace('edXOJWE4','XdXOJWE4'),original.replace('  hashes = [','  hashes = [\n    "h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs=",')):
            historical.write_text(altered)
            with patch.object(model.retired,'source',return_value=historical):
                with self.assertRaisesRegex(ValueError,'historical security provider lock drift'):
                    model.security_provider_lock(ROOT)

    def test_only_exact_postbaseline_snapshots_leave_historical_view(self):
        root=self.fixture()
        # Current discovery is unchanged: the preserved snapshots remain unknown.
        current=Discovery(root,env='dev')
        for name in history.NON_BASELINE_REVIEW_INPUTS:
            self.assertTrue(any(r['source']==name and r['admission']=='UNSUPPORTED_APPLICABLE' for r in current.records))
        with history.source_root(root) as historical:
            for name in history.NON_BASELINE_REVIEW_INPUTS:self.assertFalse((historical/name).exists())
        for name in history.NON_BASELINE_REVIEW_INPUTS:self.assertTrue((root/name).is_file())

    def test_unknown_json_beside_snapshot_remains_in_historical_discovery(self):
        root=self.fixture();path=root/'operations/integrations/ssm-diagnostic/review/runtime/extra.tf.json'
        path.write_text('{"resource":{"aws_iam_policy":{"unreviewed":{}}}}')
        with history.source_root(root) as historical:
            self.assertTrue((historical/path.relative_to(root)).is_file())
            found=Discovery(historical,env='dev')
            self.assertTrue(any(r['source']==path.relative_to(root).as_posix() and
                                r['admission']=='UNSUPPORTED_APPLICABLE' for r in found.records))

    def test_changed_known_snapshot_cannot_be_silently_omitted(self):
        root=self.fixture();path=root/next(iter(history.NON_BASELINE_REVIEW_INPUTS))
        path.write_text(path.read_text()+'\n ')
        with self.assertRaisesRegex(ValueError,'Historical review-input drift'):
            with history.source_root(root):self.fail('Drift admitted')

    def test_historical_exclusions_are_not_a_directory_or_current_catalog_rule(self):
        self.assertEqual(len(history.NON_BASELINE_REVIEW_INPUTS),2)
        for name,digest in history.NON_BASELINE_REVIEW_INPUTS.items():
            self.assertTrue(name.endswith('/main.tf.json'))
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest)
        root=self.fixture();unrelated=root/'new-root/main.tf.json';unrelated.parent.mkdir();unrelated.write_text('{}')
        self.assertIn('new-root/main.tf.json',set(history.historical_inputs(root)))


if __name__=='__main__':unittest.main(verbosity=2)
