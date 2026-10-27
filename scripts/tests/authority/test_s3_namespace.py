"""Typed S3 identity proofs: namespace isolation is source-derived, never a skip."""
from pathlib import Path
import tempfile
import unittest
from current_controls import symbolic_string, disjoint_s3
from discovery import Discovery

ROOT=Path(__file__).resolve().parents[3]
LEGACY='arn:aws:s3:::demo-release-artifacts-111122223333/deployments/prod/fixture.json'


class S3NamespaceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='e1-s3-binding-');self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.source=(ROOT/'operations/integrations/portable/trial/runtime/main.tf').read_text()

    def discover(self,text):
        (self.root/'main.tf').write_text(text,encoding='utf-8')
        return Discovery(self.root,names=('demo-dev-shared-github-dev-deploy',))

    def query(self,d,resource=LEGACY):
        return d.taints('github','api:s3',action='s3:PutObject',resource=resource)

    def test_actual_bucket_policy_arn_binding_proves_only_disjoint_targets(self):
        d=self.discover(self.source)
        policy=next(x for x in d.records if x['declaration']['type']=='aws_s3_bucket_policy')
        b=policy['s3_target_binding']
        self.assertEqual(b['bucketDeclaration'],'aws_s3_bucket.archive')
        self.assertEqual(b['arnReference'],'aws_s3_bucket.archive.arn')
        self.assertEqual(b['resourceReferencesChecked'],2)
        self.assertEqual(b['patterns'],['snt-*-*-*'])
        self.assertEqual(policy['admission'],'UNSUPPORTED_APPLICABLE')
        self.assertEqual(self.query(d),[])
        self.assertEqual(len(self.query(d,'arn:aws:s3:::snt-example-111122223333-us-east-1/key')),1)

    def test_removed_namespace_or_colliding_literal_restores_unknown(self):
        for changed in (self.source.replace('"snt-${lower(local.name)}-', '"${lower(local.name)}-'),
                        self.source.replace('"snt-${lower(local.name)}-${local.config.account}-${local.config.region}"',
                                            '"demo-release-artifacts-111122223333"')):
            with self.subTest(changed=changed[:50]):self.assertTrue(self.query(self.discover(changed)))

    def test_foreign_or_variable_policy_resources_cannot_inherit_bucket_proof(self):
        marker='Resource = [aws_s3_bucket.archive.arn, "${aws_s3_bucket.archive.arn}/*"]'
        self.assertIn(marker,self.source)
        for target in ('var.foreign','[aws_s3_bucket.other.arn]','["arn:aws:s3:::foreign/*"]'):
            with self.subTest(target=target):
                d=self.discover(self.source.replace(marker,'Resource = '+target));self.assertTrue(self.query(d))

    def test_missing_duplicate_or_foreign_bucket_identity_stays_unknown(self):
        for changed in (self.source.replace('bucket = aws_s3_bucket.archive.id','bucket = var.foreign_bucket'),
                        self.source.replace('bucket = aws_s3_bucket.archive.id','bucket = aws_s3_bucket.missing.id'),
                        self.source+'\nresource "aws_s3_bucket" "archive" {\n bucket="other"\n}\n'):
            with self.subTest(changed=changed[-70:]):self.assertTrue(self.query(self.discover(changed)))

    def test_hook_or_uninspected_attribute_cannot_be_scoped_away(self):
        marker='  force_destroy = false'
        for injected in ('\n  uninspected_control = var.value',
                         '\n  provisioner "local-exec" {\n    command="unexecuted"\n  }'):
            with self.subTest(injected=injected):
                self.assertTrue(self.query(self.discover(self.source.replace(marker,marker+injected))))

    def test_same_target_missing_transport_context_never_becomes_a_grant(self):
        d=self.discover(self.source)
        self.assertTrue(self.query(d,'arn:aws:s3:::snt-demo-111122223333-us-east-1/key'))
        self.assertTrue(d.taints('api:s3',action='s3:GetObject'))
        self.assertTrue(self.query(d,'arn:aws:s3:::*/*'))

    def test_extra_cross_service_deny_remains_relevant(self):
        changed=self.source.replace('Action = "s3:*"','Action = ["s3:*", "iam:PassRole"]')
        d=self.discover(changed)
        self.assertTrue(d.taints('api:iam',action='iam:PassRole',resource='arn:aws:iam::111122223333:role/known'))

    def test_symbolic_templates_do_not_evaluate_arbitrary_or_cyclic_expressions(self):
        values={('d','x'):'local.x'}
        self.assertEqual(symbolic_string('local.x',values,'d'),'*')
        for expr in ('"snt-${arbitrary()}"','"snt-$${var.x}"','"%{ if var.x }snt-%{ endif }"'):
            self.assertEqual(symbolic_string(expr,{},'d'),'*')
        self.assertEqual(symbolic_string('"snt-${lower(var.x)}-${local.config.account}-${local.config.region}"',{},'d'),'snt-*-*-*')
        self.assertFalse(disjoint_s3({'patterns':['*']},LEGACY))
        self.assertFalse(disjoint_s3({'patterns':['snt-*']},'arn:aws:s3:::*/*'))

    def test_future_source_contract_requires_name_validation_without_fallback(self):
        self.assertRegex(self.source,r'archive_bucket_name\s*=\s*"snt-')
        self.assertIn('bucket        = local.archive_bucket_name',self.source)
        self.assertIn('length(local.archive_bucket_name) <= 63',self.source)
        self.assertIn('^snt-[a-z0-9][a-z0-9-]*[a-z0-9]$',self.source)
        for suffix in ('-s3alias','--ol-s3','--x-s3','--table-s3','-an'):
            self.assertIn('"'+suffix+'"',self.source)
        self.assertIn('force_destroy = false',self.source)


if __name__=='__main__':unittest.main(verbosity=2)
