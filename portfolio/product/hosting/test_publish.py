"""Offline content-update boundary; no SDK import, AWS calls or uploads."""
import copy
import unittest

from publish import require_content_update


class ContentUpdate(unittest.TestCase):
    def setUp(self):
        self.original = {"Resources": {
            "Routes": {"Properties": {"FunctionCode": "old routes", "Name": "routes"}},
            "Headers": {"Properties": {"FunctionCode": "old headers", "Name": "headers"}},
            "Bucket": {"Properties": {"PublicAccessBlock": True}},
            "Distribution": {"Properties": {"Origin": "private-S3"}},
        }}

    def test_function_content_only_and_no_input_mutation(self):
        proposed = copy.deepcopy(self.original)
        proposed["Resources"]["Routes"]["Properties"]["FunctionCode"] = "new allowlist"
        require_content_update(self.original, proposed)
        self.assertEqual(self.original["Resources"]["Routes"]["Properties"]["FunctionCode"], "old routes")

    def test_resource_security_origin_and_identity_changes_are_rejected(self):
        for resource, field, value in (
            ("Bucket", "PublicAccessBlock", False),
            ("Distribution", "Origin", "API-Gateway"),
            ("Routes", "Name", "foreign-function"),
            ("Headers", "FunctionCode", "weakened CSP"),
        ):
            proposed = copy.deepcopy(self.original)
            proposed["Resources"][resource]["Properties"][field] = value
            with self.subTest(resource=resource), self.assertRaises(ValueError):
                require_content_update(self.original, proposed)
