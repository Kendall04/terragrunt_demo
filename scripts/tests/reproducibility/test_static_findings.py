"""Offline scanner-boundary tests: no scanners, subprocess or AWS calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from test_reproducibility import load

CHECK = load('static_findings', '.github/scripts/ci/check-static-findings.py')


class StaticFindingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root / 'terraform/main.tf'
        self.source.parent.mkdir(); self.source.write_text('resource "example" "one" {}\n')
        self.row = {'rule': {'name': 'old-rule', 'severity': 'warning'}, 'message': 'known warning',
                    'range': {'filename': 'terraform/main.tf', 'start': {'line': 1}, 'end': {'line': 1}}}
        self.report = {'issues': [self.row], 'errors': []}
        self.expected = CHECK.identities('tflint', self.report, self.root)
        self.baseline = {'findings': {'tflint': self.expected}}

    def test_known_nonzero_finding_exit_is_observed_not_suppressed(self):
        self.assertEqual(CHECK.inspect('tflint', 2, json.dumps(self.report), self.baseline, self.root), 1)

    def test_add_remove_and_duplicate_each_block(self):
        for rows in ([], [self.row, self.row], [dict(self.row, message='new warning')]):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                CHECK.inspect('tflint', 2 if rows else 0, json.dumps({'issues': rows, 'errors': []}), self.baseline, self.root)

    def test_severity_and_source_changes_block(self):
        changed = copy.deepcopy(self.report); changed['issues'][0]['rule']['severity'] = 'error'
        with self.assertRaises(ValueError): CHECK.inspect('tflint', 2, json.dumps(changed), self.baseline, self.root)
        self.source.write_text('resource "example" "changed" {}\n')
        with self.assertRaises(ValueError): CHECK.inspect('tflint', 2, json.dumps(self.report), self.baseline, self.root)

    def test_execution_errors_malformed_json_and_empty_error_exit_block(self):
        for code, raw in ((1, json.dumps(self.report)), (2, '{}'), (2, 'not-json'),
                          (2, '{"issues":[],"errors":[]}'), (0, '{"issues":[],"errors":["failure"]}')):
            with self.subTest(code=code), self.assertRaises((ValueError, KeyError)):
                CHECK.inspect('tflint', code, raw, self.baseline, self.root)

    def test_windows_linux_paths_normalize_without_accepting_traversal(self):
        row = copy.deepcopy(self.row); row['range']['filename'] = r'C:\checkout\terraform\main.tf'
        self.assertEqual(CHECK.identities('tflint', {'issues': [row], 'errors': []}, self.root), self.expected)
        row['range']['filename'] = '/home/runner/work/repo/terraform/main.tf'
        self.assertEqual(CHECK.identities('tflint', {'issues': [row], 'errors': []}, self.root), self.expected)
        row['range']['filename'] = 'terraform/../outside.tf'
        with self.assertRaises(ValueError): CHECK.identities('tflint', {'issues': [row], 'errors': []}, self.root)

    def test_tfsec_identity_and_multiplicity_are_not_count_only(self):
        row = {'rule_id': 'AVD-example', 'severity': 'HIGH', 'resource': 'example.one', 'description': 'known',
               'location': {'filename': 'terraform/main.tf', 'start_line': 1, 'end_line': 1}}
        report = {'results': [row, row]}; baseline = {'findings': {'tfsec': CHECK.identities('tfsec', report, self.root)}}
        self.assertEqual(CHECK.inspect('tfsec', 1, json.dumps(report), baseline, self.root), 2)
        changed = copy.deepcopy(report); changed['results'][0]['resource'] = 'example.other'
        with self.assertRaises(ValueError): CHECK.inspect('tfsec', 1, json.dumps(changed), baseline, self.root)
