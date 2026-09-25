"""Disposable in-memory production-source mutations must break acceptance tests."""
import copy
import io
import types
import unittest
import test_finalizer as acceptance

class Sensitivity(unittest.TestCase):
    def detects(self, old, new, test_name):
        original=acceptance.f
        source=original.Path(original.__file__).read_text()
        self.assertIn(old,source)
        mutant=types.ModuleType('disposable_finalizer')
        mutant.__file__=original.__file__
        exec(compile(source.replace(old,new),'<disposable-finalizer-mutation>','exec'),mutant.__dict__)
        acceptance.f=mutant
        try:
            result=unittest.TextTestRunner(stream=io.StringIO()).run(acceptance.Tests(test_name))
            self.assertFalse(result.wasSuccessful(),'production mutation escaped tests')
        finally:acceptance.f=original
    def test_noop_publication_cannot_hide(self):
        self.detects('require(self.qualifications.read(key) == raw)','pass','test_noop_write_is_not_success')
    def test_source_binding_removal_detected(self):
        self.detects("require(record[key] == op[key])","require(key == 'source_commit' or record[key] == op[key])",'test_mutation_wrong_source')
    def test_manifest_version_binding_removal_detected(self):
        self.detects("require(receipt[key] == manifest[key])","require(key == 'version_id' or receipt[key] == manifest[key])",'test_mutation_wrong_version')
    def test_checksum_removal_detected(self):
        self.detects("require(type(receipt['bytes']) is bytes and checksum(receipt['bytes']) == manifest['sha256'])","require(type(receipt['bytes']) is bytes)",'test_mutation_wrong_checksum')
    def test_deny_all_detected(self):
        self.detects("validate('wakeup', wakeup)","require(False)",'test_positive_closed_contracts')
