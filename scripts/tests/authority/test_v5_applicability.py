"""V4-04: reachability alone cannot turn inert output metadata into a control."""
import json
import unittest

from graph import baseline
from source import Adapter
import test_v3


class SourceApplicabilityV5Tests(unittest.TestCase):
    fixture = test_v3.SourceAdmissionTests.fixture
    acknowledge = test_v3.SourceAdmissionTests.acknowledge
    directory = "terraform/infra/shared/modules/v5_metadata"

    def put(self, root, name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        self.acknowledge(root)
        return path

    def invoke(self, root):
        self.put(root, "terraform/infra/shared/v5_metadata.tf",
                 'module "v5_metadata" {\n source = "./modules/v5_metadata"\n}\n')

    def current(self, root):
        return next(record for record in baseline(root) if record["environment"] == "dev")

    def test_invoked_inert_json_and_native_output_preserve_witnesses(self):
        for filename, content in (("metadata.tf.json", {"output": {"review_note_no_consumers": {"value": "inert literal"}}}),
                                  ("metadata.tf", 'output "review_note_no_consumers" {\n value = "inert literal"\n}\n')):
            with self.subTest(filename=filename):
                root = self.fixture()
                self.put(root, self.directory + "/" + filename, content)
                self.invoke(root)
                record = self.current(root)
                for node in ("delivery:runtime", "acquire:github_dev_deploy", "infra:stronger-workload-compute"):
                    self.assertEqual(record["states"][node], "ALLOW", node)
                discovery = next(item for item in Adapter(root, "dev").discovery().records
                                 if item["source"] == self.directory + "/" + filename)
                self.assertEqual(discovery["admission"], "NON_SECURITY_RELEVANT")
                self.assertEqual(discovery["applicability"]["status"], "APPLICABLE")
                if filename.endswith("json"):
                    self.assertEqual(discovery["consumer_relationships"], [])
                    self.assertEqual(discovery["security_relevance"], "INERT_LITERAL_OUTPUT")

    def test_invoked_json_iam_and_security_module_input_remain_unknown(self):
        variants = ({"resource": {"aws_iam_role_policy": {"control": {"role": "demo-dev-github-deploy", "policy": "opaque"}}}},
                    {"module": {"security": {"source": "../iam_github", "github_owner": "other-owner"}}})
        for document in variants:
            with self.subTest(document=document):
                root = self.fixture()
                self.put(root, self.directory + "/authority.tf.json", document)
                self.invoke(root)
                self.assertEqual(self.current(root)["states"]["delivery:runtime"], "UNKNOWN")

    def test_uninvoked_json_iam_remains_nonapplicable(self):
        root = self.fixture()
        name = self.directory + "/authority.tf.json"
        self.put(root, name, {"resource": {"aws_iam_role_policy": {"control": {"role": "opaque"}}}})
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "ALLOW")
        record = next(item for item in Adapter(root, "dev").discovery().records if item["source"] == name)
        self.assertEqual(record["admission"], "UNSUPPORTED_NOT_APPLICABLE")

    def test_literal_output_consumed_by_security_relationship_is_not_inert(self):
        root = self.fixture()
        name = self.directory + "/metadata.tf.json"
        self.put(root, name, {"output": {"role_name": {"value": "demo-dev-github-deploy"}}})
        self.invoke(root)
        self.put(root, "terraform/infra/shared/v5_consumer.tf",
                 'resource "aws_iam_role_policy" "control" {\n role = module.v5_metadata.role_name\n policy = "opaque"\n}\n')
        discovery = next(item for item in Adapter(root, "dev").discovery().records if item["source"] == name)
        self.assertEqual(discovery["admission"], "UNSUPPORTED_APPLICABLE")
        self.assertTrue(discovery["consumer_relationships"])
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "UNKNOWN")

    def test_another_output_consumer_does_not_taint_unused_literal(self):
        root = self.fixture()
        name = self.directory + "/metadata.tf.json"
        self.put(root, name, {"output": {"unused_note": {"value": {"nested": [True, None, 7, "literal"]}}}})
        self.put(root, self.directory + "/other.tf", 'output "other_note" {\n value = "other"\n}\n')
        self.invoke(root)
        self.put(root, "terraform/infra/shared/v5_consumer.tf", 'output "review_note" {\n value = module.v5_metadata.other_note\n}\n')
        discovery = next(item for item in Adapter(root, "dev").discovery().records if item["source"] == name)
        self.assertEqual(discovery["admission"], "NON_SECURITY_RELEVANT")
        self.assertEqual(self.current(root)["states"]["delivery:runtime"], "ALLOW")

    def test_overrides_duplicate_names_and_dynamic_values_are_not_inert(self):
        for variant in ("override", "duplicate", "expression"):
            with self.subTest(variant=variant):
                root = self.fixture()
                name = self.directory + ("/review_override.tf.json" if variant == "override" else "/metadata.tf.json")
                value = "${aws_iam_role.opaque.arn}" if variant == "expression" else "literal"
                self.put(root, name, {"output": {"role_name": {"value": value}}})
                if variant == "duplicate":
                    self.put(root, self.directory + "/other.tf", 'output "role_name" {\n value = "other"\n}\n')
                self.invoke(root)
                self.assertEqual(self.current(root)["states"]["delivery:runtime"], "UNKNOWN")

    def test_whole_module_consumer_cannot_hide_output_relationship(self):
        root = self.fixture()
        name = self.directory + "/metadata.tf.json"
        self.put(root, name, {"output": {"role_name": {"value": "role"}}})
        self.invoke(root)
        self.put(root, "terraform/infra/shared/v5_consumer.tf", 'locals {\n selected = module.v5_metadata[local.choice]\n}\n')
        discovery = next(item for item in Adapter(root, "dev").discovery().records if item["source"] == name)
        self.assertEqual(discovery["admission"], "UNSUPPORTED_APPLICABLE")

    def test_malformed_json_cannot_receive_inert_output_exemption(self):
        variants = (
            '{"output":{"note":{"value":"${unknown.expression}","value":"literal"}}}',
            '{"output":{"note":{"value":"${unknown.expression}"}},"output":{"note":{"value":"literal"}}}',
            '{"output":{"note":{"value":NaN}}}',
            '{"output":{"note":{"value":Infinity}}}',
            '{"output":{"note":{"value":1e999}}}',
        )
        for document in variants:
            with self.subTest(document=document):
                root = self.fixture()
                name = self.directory + "/metadata.tf.json"
                self.put(root, name, document)
                self.invoke(root)
                discovery = next(item for item in Adapter(root, "dev").discovery().records
                                 if item["source"] == name)
                self.assertEqual(discovery["admission"], "UNSUPPORTED_APPLICABLE")
                self.assertEqual(self.current(root)["states"]["delivery:runtime"], "UNKNOWN")
