"""Production admission, outputs and installer with narrow admin test adapters."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import bundles
import compute
import ownership as own
import publication as pub
from model import SUPPORT_FILES
from model import AUTHORITY, LEGACY, configuration_paths, validate_repository, wiring

ROOT = Path(__file__).resolve().parents[3]
ACCOUNT = "111122223333"
REGION = "us-east-1"


class Admin(pub.AdminChannel):
    def __init__(self, records=None):
        self.records = records
        self.publications = {}

    def read_output(self):
        if self.records is None:
            raise OSError("no protected output")
        return copy.deepcopy(self.records)

    def create_publication(self, key, value):
        if key in self.publications:
            raise FileExistsError(key)
        self.publications[key] = copy.deepcopy(value)

    def read_publication(self, key):
        return copy.deepcopy(self.publications[key])


class Storage(pub.AdminBundleStorage):
    def __init__(self, mode="ok"):
        self.mode = mode
        self.calls = []
        self.objects = {}

    def put_if_absent(self, bucket, key, raw, checksum_sha256):
        self.calls.append(("put", bucket, key, checksum_sha256))
        if self.mode == "write-failure":
            raise OSError("write failed")
        if (bucket, key) in self.objects or self.mode == "conflict":
            raise FileExistsError(key)
        version = {"null-version": None, "empty-version": "", "latest-version": "latest", "literal-null": "null"}.get(self.mode, "returned-version-A")
        self.objects[bucket, key] = (version, raw)
        return {"bucket": bucket, "key": "wrong" if self.mode == "write-key" else key, "version_id": version}

    def get_exact(self, bucket, key, version_id):
        self.calls.append(("get", bucket, key, version_id))
        if self.mode in ("read-failure", "missing-object"):
            raise OSError("read failed")
        version, raw = self.objects[bucket, key]
        assert version == version_id
        return {"bucket": bucket, "key": "wrong" if self.mode == "read-key" else key,
            "version_id": "version-B" if self.mode == "wrong-version" else version_id,
            "bytes": raw + b"wrong" if self.mode == "wrong-bytes" else raw}


def output_fixture(doc):
    records = copy.deepcopy(own.wiring(doc)["output"]["protected_output_candidates"]["value"])
    for i, (key, item) in enumerate(doc["ownership_closure"]["resources"].items()):
        name = item["name"]
        values = {"role": f"arn:aws:iam::{ACCOUNT}:role/{name}",
            "profile": f"arn:aws:iam::{ACCOUNT}:instance-profile/{name}",
            "key": f"arn:aws:kms:{REGION}:{ACCOUNT}:key/00000000-0000-0000-0000-{i:012x}",
            "secret": f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:{name}-Ab1234",
            "repository": f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{name}",
            "bucket": f"arn:aws:s3:::{name}{ACCOUNT}", "oidc": f"arn:aws:iam::{ACCOUNT}:oidc-provider/{name}"}
        records[key]["value"] = values[item["kind"]]
    return records


class ClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = validate_repository(ROOT)

    def fixture(self):
        tmp = tempfile.TemporaryDirectory(prefix="wp2d-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for path in configuration_paths(ROOT) | set(SUPPORT_FILES) | {AUTHORITY, LEGACY, bundles.SOURCE, "terraform/infra/security/README.md"}:
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, dest)
        return root

    def mutate(self, change):
        root = self.fixture()
        d = copy.deepcopy(self.doc)
        change(d)
        (root / AUTHORITY).write_text(json.dumps(d))
        with self.assertRaises((ValueError, TypeError, KeyError)):
            validate_repository(root)

    def install(self, storage=None, admin=None, name="build", consumer="release", raw=None):
        storage, admin = storage or Storage(), admin or Admin()
        raw = raw if raw is not None else bundles.artifact(ROOT, self.doc["control_bundles"], name)
        return pub.install_bundle(ROOT, self.doc, ACCOUNT, REGION, name, consumer, raw, storage, admin), storage, admin

    def test_01_real_neutral_declarations(self):
        tf = wiring(self.doc)[own.MODULE]
        self.assertEqual(len(tf["resource"]["aws_iam_role"]), 18)
        self.assertEqual(len(tf["resource"]["aws_iam_instance_profile"]), 4)
        self.assertEqual(len(tf["resource"]["aws_kms_key"]), 2)
        self.assertEqual(len(tf["resource"]["aws_secretsmanager_secret"]), 6)
        self.assertEqual(len(tf["resource"]["aws_ecr_repository"]), 3)
        self.assertEqual(len(tf["resource"]["aws_iam_openid_connect_provider"]), 1)

    def test_02_exactly_one_target_owner(self):
        c = self.doc["ownership_closure"]
        declarations = [r["declaration"] for r in c["resources"].values()]
        self.assertEqual(len(declarations), len(set(declarations)))
        self.assertTrue(all(r["owner"] == own.OWNER for r in c["resources"].values()))
        for path, tf in wiring(self.doc).items():
            if path.startswith("terraform/modules/target/") and not isinstance(tf, str):
                self.assertEqual(set(tf["resource"]), {"terraform_data"})

    def test_03_current_is_excluded_not_second_owner(self):
        legacy = json.loads((ROOT / LEGACY).read_text())
        self.assertEqual(legacy["classification"], "TRANSITIONAL_LEGACY_NOT_TARGET_ACCEPTED")
        for source in ("terraform/infra/apps/fargate/lambda_scale_down.tf", "terraform/infra/global/modules/nat/events_nat.tf"):
            self.assertIn(source, legacy["sources"])
        self.mutate(lambda d: d["ownership_closure"].update(legacy="TARGET_ORDINARY_OWNED"))

    def test_04_consumer_bindings_no_default_ids(self):
        for tf in own.consumer_wiring(self.doc).values():
            self.assertNotIn("default", tf["variable"]["protected_inputs"])
            self.assertIn("var.protected_inputs == tomap(local.expected)", tf["resource"]["terraform_data"]["protected_input"]["lifecycle"]["precondition"]["condition"])
            self.assertNotIn("terraform_remote_state", json.dumps(tf))

    def test_05_publication_positive_all_consumers(self):
        admin = Admin(output_fixture(self.doc))
        published = pub.publish_outputs(self.doc, ACCOUNT, REGION, admin)
        promoted = pub.promote_outputs(self.doc, ACCOUNT, REGION, admin)
        own.validate_publications(promoted)
        self.assertEqual(len(published["records"]), 43)
        for consumer in self.doc["ownership_closure"]["consumers"]:
            values = pub.consume(self.doc, ACCOUNT, REGION, consumer, admin)
            self.assertEqual(values, pub.validate_consumer_input(self.doc, ACCOUNT, REGION, consumer, values, admin))

    def test_06_records_wrong_scope_class_owner_identity(self):
        for field, value in (("scope", "prod"), ("class", "key"), ("owner", "ORDINARY_LIFECYCLE_OWNED"), ("logical_id", "prod/sql"), ("declaration", "ordinary/sql"), ("schema", "unknown"), ("authority_digest", "a" * 64)):
            records = output_fixture(self.doc)
            records["dev/sql"][field] = value
            with self.assertRaises(ValueError):
                pub.publish_outputs(self.doc, ACCOUNT, REGION, Admin(records))

    def test_07_records_malformed_extra_duplicate(self):
        for change in (lambda r: r["dev/sql"].update(value="not-an-arn"), lambda r: r["dev/sql"].update(secret="canary"), lambda r: r.update(extra=r["dev/sql"]), lambda r: r.pop("dev/sql")):
            records = output_fixture(self.doc)
            change(records)
            with self.assertRaises(ValueError):
                pub.validate_records(self.doc, records, ACCOUNT, REGION)
        with self.assertRaises(ValueError):
            pub.decode_record(b'{"x":1,"x":2}')

    def test_08_manual_arn_and_random_uuid_substitution(self):
        admin = Admin(output_fixture(self.doc))
        pub.publish_outputs(self.doc, ACCOUNT, REGION, admin)
        original = pub.consume(self.doc, ACCOUNT, REGION, "dev/data", admin)
        for key in original:
            values = dict(original)
            values[key] += "alternate"
            with self.assertRaises(ValueError):
                pub.validate_consumer_input(self.doc, ACCOUNT, REGION, "dev/data", values, admin)

    def test_09_missing_publication_fails(self):
        with self.assertRaises(KeyError):
            pub.consume(self.doc, ACCOUNT, REGION, "dev/data", Admin())
        with self.assertRaises(ValueError):
            pub.publish_outputs(self.doc, ACCOUNT, REGION, "ordinary-lifecycle")

    def test_10_recovery_records_unavailable(self):
        records = output_fixture(self.doc)
        for key in list(records):
            if not key.startswith("recovery/"):
                continue
            self.assertIsNone(records[key]["value"])
            bad = copy.deepcopy(records)
            bad[key].update(available=True, value="arn:aws:lambda:us-east-1:111122223333:function:fake")
            with self.assertRaises(ValueError):
                pub.validate_records(self.doc, bad, ACCOUNT, REGION)

    def test_11_dependency_writers(self):
        c = self.doc["ownership_closure"]
        self.assertEqual(set(c["dependencies"]), set(c["resources"]) | {"recovery/" + k for k in c["recovery"]})
        for key in c["dependencies"]:
            self.mutate(lambda d, key=key: d["ownership_closure"]["dependencies"][key].update(writer="HIGH_RISK_LIFECYCLE_OWNED"))

    def test_12_recovery_disabled_states(self):
        for key in self.doc["ownership_closure"]["recovery"]:
            for field in ("operational", "available", "events_enabled", "invocation_enabled"):
                self.mutate(lambda d, key=key, field=field: d["ownership_closure"]["recovery"][key].update({field: True}))

    def test_13_launch_config_override(self):
        for env in ("dev", "prod"):
            self.mutate(lambda d, env=env: d["ownership_closure"]["recovery"][env + "/nat-launch"].update(user_data="ordinary script"))

    def test_14_recovery_concrete_roles_inert(self):
        tf = own.wiring(self.doc)
        for env in ("dev", "prod"):
            for key in (env + "_cleanup", env + "_nat_recovery"):
                trust = json.loads(tf["resource"]["aws_iam_role"][key]["assume_role_policy"])
                policy = json.loads(tf["resource"]["aws_iam_role_policy"][key]["policy"])
                self.assertTrue(all(s["Effect"] == "Deny" for s in trust["Statement"]))
                self.assertEqual(policy["Statement"], [{"Effect": "Deny", "Action": "*", "Resource": "*"}])

    def test_15_no_recovery_compute_events_permissions(self):
        tf = own.wiring(self.doc)
        self.assertFalse(any(t.startswith(("aws_lambda", "aws_codebuild", "aws_cloudwatch_event", "aws_launch_template")) for t in tf["resource"]))

    def test_16_install_positive_returned_version(self):
        result, storage, admin = self.install()
        self.assertEqual(result["version_id"], "returned-version-A")
        self.assertEqual(storage.calls[1], ("get", result["bucket"], result["key"], result["version_id"]))
        self.assertEqual(list(admin.publications.values()), [result])
        self.assertFalse(result["operational"])
        self.assertFalse(result["executable"])

    def test_17_write_failures_publish_nothing(self):
        for mode in ("write-failure", "conflict", "write-key"):
            admin = Admin()
            with self.assertRaises((ValueError, OSError)):
                self.install(Storage(mode), admin)
            self.assertEqual(admin.publications, {})

    def test_18_version_null_empty_latest_rejected(self):
        for mode in ("null-version", "empty-version", "latest-version", "literal-null"):
            admin = Admin()
            with self.assertRaises(ValueError):
                self.install(Storage(mode), admin)
            self.assertEqual(admin.publications, {})

    def test_19_exact_read_identity_mandatory(self):
        for mode in ("wrong-version", "read-key"):
            admin = Admin()
            with self.assertRaises(ValueError):
                self.install(Storage(mode), admin)
            self.assertEqual(admin.publications, {})

    def test_20_failed_readback_publishes_nothing(self):
        for mode in ("read-failure", "missing-object", "wrong-bytes"):
            admin = Admin()
            with self.assertRaises((ValueError, OSError)):
                self.install(Storage(mode), admin)
            self.assertEqual(admin.publications, {})

    def test_21_wrong_class_consumer_digest(self):
        storage, admin = Storage(), Admin()
        for name, consumer, raw in (("build", "deploy-dev", None), ("normal-delivery", "deploy-dev", bundles.artifact(ROOT, self.doc["control_bundles"], "build")), ("build", "release", b"fake")):
            with self.assertRaises((ValueError, KeyError)):
                self.install(storage, admin, name, consumer, raw)
        self.assertEqual(storage.calls, [])
        self.assertEqual(admin.publications, {})

    def test_22_no_caller_version_parameter(self):
        import inspect
        params = inspect.signature(pub.install_bundle).parameters
        self.assertNotIn("version_id", params)
        self.assertNotIn("approved", params)
        self.assertNotIn("key", params)

    def test_23_install_does_not_activate_or_mutate(self):
        before = copy.deepcopy(self.doc)
        self.install()
        self.assertEqual(self.doc, before)
        self.assertFalse(self.doc["controller_compute"]["operational"])
        self.assertFalse(self.doc["controller_compute"]["creation_supported"])
        for key in self.doc["controller_compute"]["nodes"]:
            self.assertFalse(compute.activation_status(ROOT, self.doc, key)["operational"])
        self.mutate(lambda d: d["controller_compute"].update(operational=True))

    def test_24_recovery_bundles_still_reservations(self):
        for name in ("cleanup-recovery", "nat-recovery"):
            self.assertFalse(self.doc["control_bundles"]["classes"][name]["operational"])
            key = next(k for k in self.doc["control_bundles"]["consumer_references"] if k.startswith(name + "/"))
            self.mutate(lambda d, key=key: d["control_bundles"]["consumer_references"][key].update(version_id="fake", installation="VERIFIED", operational=True))

    def test_25_requests_and_compute_roles_preserved(self):
        self.assertEqual(len(self.doc["request_identities"]), 11)
        self.assertEqual(len(self.doc["controller_compute"]["nodes"]), 18)
        self.assertEqual(self.doc["policies"]["inert_permissions"]["Statement"], [{"Effect": "Deny", "Action": "*", "Resource": "*"}])
        for trust in self.doc["controller_compute"]["role_trust"].values():
            self.assertTrue(all(s["Effect"] == "Deny" for s in trust["Statement"]))

    def test_26_out_of_model_surfaces(self):
        for prefix in ("terraform/modules/target/dev/data", "terraform/modules/target/prod/global", "terraform/infra/security"):
            for typ in ("aws_iam_role", "aws_kms_key", "aws_s3_bucket", "aws_lambda_function", "aws_lambda_permission", "aws_launch_template"):
                root = self.fixture()
                path = root / prefix / "alternate.tf.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"resource": {typ: {"alternate": {}}}}))
                with self.assertRaises(ValueError):
                    validate_repository(root)

    def test_27_target_recovery_grants_rejected(self):
        for action in ("lambda:InvokeFunction", "ecs:UpdateService", "ec2:ReplaceRoute", "iam:PassRole"):
            root = self.fixture()
            path = root / own.MODULE
            tf = json.loads(path.read_text())
            tf["resource"]["aws_iam_role_policy"]["dev_nat_recovery"]["policy"] = json.dumps({"Statement": [{"Effect": "Allow", "Action": action, "Resource": "*"}]})
            path.write_text(json.dumps(tf))
            with self.assertRaises(ValueError):
                validate_repository(root)

    def test_28_remote_state_and_alternate_publication_rejected(self):
        for change in (lambda t: t.update(data={"terraform_remote_state": {"security": {"backend": "s3"}}}),
                       lambda t: t["locals"].update(authority='${jsondecode(file("caller.json"))}'),
                       lambda t: t["variable"]["protected_inputs"].update(default={"dev/sql": "manual"})):
            root = self.fixture()
            path = root / "terraform/modules/target/dev/data/main.tf.json"
            tf = json.loads(path.read_text())
            change(tf)
            path.write_text(json.dumps(tf))
            with self.assertRaises(ValueError):
                validate_repository(root)

    def test_29_registry_is_empty_not_live_claim(self):
        c = self.doc["ownership_closure"]
        self.assertEqual(c["publications"], {})
        self.assertEqual(c["live"], "UNVERIFIED")
        self.assertEqual(c["state_migration"], "NOT_PERFORMED")
        self.mutate(lambda d: d["ownership_closure"].update(live="VERIFIED"))

    def test_30_changed_source_role_or_ownership_rejected(self):
        for field, value in (("owner", "ORDINARY_LIFECYCLE_OWNED"), ("mode", "RECOVERY_ACTIVE"), ("name", "alternate"), ("source", "ordinary.tf")):
            self.mutate(lambda d, field=field, value=value: d["ownership_closure"]["resources"]["dev/nat-recovery"].update({field: value}))

    def test_31_actual_ordinary_resources_use_protected_bindings(self):
        generated = wiring(self.doc)
        for env in ("dev", "prod"):
            data = generated[f"terraform/modules/target/{env}/data/ordinary-main.tf"]
            self.assertIn('resource "aws_instance" "db"', data)
            self.assertIn(f'local.expected["{env}/sql-profile"]', data)
            self.assertIn(f'local.expected["{env}/sa"]', data)
            vpc = generated[f"terraform/modules/target/{env}/global/modules/vpc/vpc.tf"]
            self.assertIn("iam_role_arn         = var.protected_flow_role", vpc)
            for path, text in generated.items():
                if path.startswith(f"terraform/modules/target/{env}/") and isinstance(text, str):
                    for prefix in ('resource "aws_iam_', 'resource "aws_kms_', 'resource "aws_ecr_', 'resource "aws_s3_', 'resource "aws_secretsmanager_', 'resource "aws_lambda_', 'resource "aws_launch_template"'):
                        self.assertNotIn(prefix, text)

    def test_32_bootstrap_no_workload_roles_or_secrets(self):
        generated = wiring(self.doc)
        for env in ("dev", "prod"):
            task = generated[f"terraform/modules/target/{env}/apps/modules/ecs_service/taskdef.tf"]
            self.assertNotIn("task_role_arn", task)
            self.assertNotIn("execution_role_arn", task)
            caller = generated[f"terraform/modules/target/{env}/apps/ordinary-demo.tf"]
            self.assertNotIn("DB_CONN_STRING", caller)
            self.assertEqual(caller.count("desired_count = 0"), 2)
            self.assertEqual(caller.count("secrets = {}"), 2)

    def test_33_recovery_install_still_dormant(self):
        for name, consumer in (("cleanup-recovery", "cleanup-dev"), ("nat-recovery", "nat-prod")):
            result, _, _ = self.install(name=name, consumer=consumer)
            self.assertFalse(result["operational"])
            self.assertFalse(result["executable"])
            self.assertTrue(all(not r["operational"] for r in self.doc["ownership_closure"]["recovery"].values()))

    def test_34_source_dependency_mutation_rejected(self):
        root = self.fixture()
        path = root / "terraform/infra/data/user_data.sh"
        path.write_text("caller-controlled script")
        with self.assertRaisesRegex(ValueError, "protected source dependency drift"):
            validate_repository(root)

    def test_35_no_ordinary_publication_file(self):
        root = self.fixture()
        (root / "terraform/modules/target/dev/data/records.json").write_text('{"available":true}')
        with self.assertRaisesRegex(ValueError, "unadmitted protected-root file"):
            validate_repository(root)


if __name__ == "__main__":
    unittest.main()
