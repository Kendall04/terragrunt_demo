"""Actual generated resource structures and E1/E2/E4 controller traces.

The historical evaluator handles exactly the captured single any/count/expire
rule. It is a deterministic risk witness, not an AWS lifecycle preview.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

import model
import ownership
from scripts.wp4d.adapters import Facts
from scripts.normal_delivery import authorization as a
from scripts.tests.delivery.fixtures import setup, OP, NEXT
from scripts.tests.recovery.fixtures import application
from scripts.tests.post_switch import test_post_switch

ROOT = Path(__file__).resolve().parents[3]
DOC = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
REPOSITORIES = {"dev_repository": "demo-dev-shared-demo-ms",
                "prod_repository": "demo-prod-shared-demo-ms",
                "neutral_repository": "demo-shared-demo-ms"}


class ECR:
    def __init__(self, account, repository, digest):
        self.calls = []
        self.result = {"imageDetails": [dict(registryId=account,
            repositoryName=repository, imageDigest=digest, imageStatus="ACTIVE")]}
        self.error = None

    def describe_images(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return copy.deepcopy(self.result)


def installed(facts, environment="dev"):
    account, region = facts.available["account"], facts.available["region"]
    repository, digest = facts.q["image_repository"], facts.q["image_digest"]
    ecr = ECR(account, repository, digest)
    adapter = Facts(None, ecr, dict(account=account, region=region, environment=environment,
        endpoint="deploy-dev" if environment == "dev" else "promote-prod",
        admin_bucket="protected", evidence_bucket="evidence", dev_evidence_bucket="dev",
        repository=repository))
    facts.artifact = adapter.artifact
    return adapter, ecr


class Retention(unittest.TestCase):
    def test_original_generated_policy_expires_required_sixteenth_image(self):
        captured = json.loads((Path(__file__).parent / "baseline-policy.json").read_text())
        self.assertEqual(captured["revision"], "8ccc7c4edf56467403d6942eb0745f31ba546935")
        self.assertEqual(set(captured["policies"]), set(REPOSITORIES))
        # Oldest D is still deployed in prod, eligible rollback in dev, and
        # referenced by a held operation. S3 digest references do not affect ECR.
        images = [dict(digest="sha256:" + f"{n:064x}", pushed=n, tags=[])
                  for n in range(16)]
        for tags in ([], ["release-old"], ["release-old", "prod-current"]):
            images[0]["tags"] = tags
            for body in captured["policies"].values():
                rule, = json.loads(body["policy"])["rules"]
                self.assertEqual(rule["rulePriority"], 1)
                self.assertEqual(rule["selection"], dict(tagStatus="any",
                    countType="imageCountMoreThan", countNumber=15))
                self.assertEqual(rule["action"], {"type": "expire"})
                expired = sorted(images, key=lambda i: i["pushed"], reverse=True)[15:]
                self.assertEqual([i["digest"] for i in expired], [images[0]["digest"]])

    def test_authoritative_generation_matches_checked_in_terraform(self):
        generated = model.wiring(DOC)[ownership.MODULE]
        self.assertEqual(generated, json.loads((ROOT / ownership.MODULE).read_text()))
        model.validate_repository(ROOT)

    def test_all_three_protected_repositories_have_no_expiration_policy(self):
        resources = json.loads((ROOT / ownership.MODULE).read_text())["resource"]
        self.assertEqual({k: v["name"] for k, v in resources["aws_ecr_repository"].items()},
                         REPOSITORIES)
        self.assertNotIn("aws_ecr_lifecycle_policy", resources)
        self.assertTrue(all(v["image_tag_mutability"] == "IMMUTABLE"
                            for v in resources["aws_ecr_repository"].values()))

    def test_no_other_active_policy_can_select_application_images(self):
        # JSON is the generator's authoritative form. HCL roots are also checked
        # so a second policy resource cannot silently bypass the omission.
        for base in ("terraform/infra/security", "terraform/modules/target", "terraform/live"):
            for path in (ROOT / base).rglob("*"):
                if path.name.endswith(".tf.json"):
                    self.assertNotIn("aws_ecr_lifecycle_policy", json.loads(path.read_text()).get("resource", {}), path)
                elif path.suffix == ".tf":
                    self.assertIsNone(re.search(r'resource\s+"aws_ecr_lifecycle_policy"', path.read_text()), path)

    def test_dev_prod_consume_same_neutral_repository(self):
        consumers = model.wiring(DOC)
        for env in ("dev", "prod"):
            path = f"terraform/modules/target/{env}/shared/main.tf.json"
            self.assertEqual(consumers[path], json.loads((ROOT / path).read_text()))
            self.assertIn("neutral/repository", DOC["ownership_closure"]["consumers"][env + "/shared"])
        dev = setup()[0]
        prod = setup("promote-prod")[0]
        self.assertEqual(dev.q["image_repository"], prod.q["image_repository"])
        self.assertEqual(dev.q["image_digest"], prod.q["image_digest"])

    def test_current_release_keeps_exact_manifest_and_digest(self):
        facts, _, _, _, _, controller, raw = setup()
        _, ecr = installed(facts)
        receipt = controller.run(OP, raw)
        self.assertEqual(receipt["status"], "SUCCESS")
        self.assertEqual(receipt["intent"]["release"], facts.q)
        self.assertEqual(receipt["intent"]["release"]["manifest"], facts.ref)
        self.assertTrue(ecr.calls)

    def rollback(self, endpoint="deploy-dev"):
        *_, records, world, process, core, raw = setup(endpoint)
        self.assertEqual(core.run(OP, raw)["status"], "SUCCESS")
        facts, auth, records, world, process, core, _ = setup(endpoint, records=records)
        _, ecr = installed(facts, a.ENDPOINTS[endpoint])
        return core, world, records, ecr, a.canonical(dict(action="rollback-release", history=OP, replicas=2))

    def test_prior_success_rollback_available_in_both_environments(self):
        for endpoint in ("deploy-dev", "promote-prod"):
            core, world, records, ecr, raw = self.rollback(endpoint)
            self.assertEqual(core.run(NEXT, raw)["status"], "SUCCESS")
            self.assertTrue(ecr.calls)

    def test_missing_image_blocks_rollback_before_mutation(self):
        for endpoint in ("deploy-dev", "promote-prod"):
            core, world, records, ecr, raw = self.rollback(endpoint)
            ecr.result = {"imageDetails": []}
            self.assertEqual(core.run(NEXT, raw)["status"], "FAILURE")
            self.assertEqual(world.calls, [])
            self.assertNotIn(a.ENDPOINTS[endpoint] + "/" + NEXT + "/success", records.data)

    def test_unverifiable_image_blocks_rollback_before_mutation(self):
        for error in (TimeoutError("unavailable"), PermissionError("denied"), ValueError("ImageNotFoundException")):
            core, world, records, ecr, raw = self.rollback()
            ecr.error = error
            self.assertEqual(core.run(NEXT, raw)["status"], "FAILURE")
            self.assertEqual(world.calls, [])

    def test_wrong_response_identity_blocks_rollback(self):
        for field, value in (("registryId", "999999999999"), ("repositoryName", "foreign"),
                             ("imageDigest", "sha256:" + "f" * 64)):
            core, world, records, ecr, raw = self.rollback()
            ecr.result["imageDetails"][0][field] = value
            self.assertEqual(core.run(NEXT, raw)["status"], "FAILURE")
            self.assertEqual(world.calls, [])

    def test_non_active_or_unknown_storage_blocks_rollback(self):
        for status in ("ARCHIVED", "ACTIVATING", "UNKNOWN", None):
            core, world, records, ecr, raw = self.rollback()
            ecr.result["imageDetails"][0]["imageStatus"] = status
            self.assertEqual(core.run(NEXT, raw)["status"], "FAILURE")
            self.assertEqual(world.calls, [])

    def test_lookup_is_bounded_to_installed_account_repository_and_digest(self):
        facts = setup()[0]
        adapter, ecr = installed(facts)
        self.assertEqual(adapter.artifact(facts.q["image_repository"], facts.q["image_digest"]), facts.available)
        self.assertEqual(ecr.calls, [dict(registryId=facts.available["account"],
            repositoryName=facts.q["image_repository"], imageIds=[{"imageDigest": facts.q["image_digest"]}])])
        for repository, digest in (("foreign", facts.q["image_digest"]),
                                   (facts.q["image_repository"], "latest")):
            with self.assertRaises(ValueError): adapter.artifact(repository, digest)
        self.assertEqual(len(ecr.calls), 1)

    def test_malformed_or_ambiguous_availability_fails_closed(self):
        facts = setup()[0]
        adapter, ecr = installed(facts)
        good = copy.deepcopy(ecr.result["imageDetails"][0])
        for result in ({}, {"imageDetails": None}, {"imageDetails": [None]},
                       {"imageDetails": [good, good]}, {"imageDetails": [good], "nextToken": "more"},
                       *[{"imageDetails": [{k: v for k, v in good.items() if k != field}]}
                         for field in good]):
            ecr.result = result
            with self.assertRaises(ValueError): adapter.artifact(facts.q["image_repository"], facts.q["image_digest"])

    def test_emergency_restoration_missing_image_has_no_success(self):
        for endpoint in ("deploy-dev", "promote-prod"):
            core, world, records, facts = application(endpoint=endpoint)
            _, ecr = installed(facts, a.ENDPOINTS[endpoint])
            ecr.result = {"imageDetails": []}
            self.assertEqual(core.run(NEXT, b"{}")["status"], "FAILURE")
            self.assertEqual(world.calls, [])

    def test_active_operation_losing_image_blocks_later_steps(self):
        facts, _, records, world, _, core, raw = setup()
        _, ecr = installed(facts)
        def removed(runtime, stage):
            if stage == "start": ecr.result = {"imageDetails": []}
        world.on_mutation = removed
        self.assertEqual(core.run(OP, raw)["status"], "FAILURE")
        self.assertNotIn("dev/" + OP + "/success", records.data)
        self.assertNotIn("switch", [stage for stage, _ in world.calls])

    def test_protected_configuration_delta_is_only_policy_removal_and_package_hashes(self):
        baseline = json.loads((Path(__file__).parent / "baseline-policy.json").read_text())
        def checksum(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(checksum(json.loads((ROOT / ownership.MODULE).read_text())),
                         baseline["configuration_without_lifecycle_sha256"])
        authority = copy.deepcopy(DOC)
        for item in authority["wp4d"]["selected"].values():
            del item["package_sha256"]
        self.assertEqual(checksum(authority), baseline["authority_without_wp4d_package_hashes_sha256"])

    def test_e4_uncertain_dependency_loss_retains_e2_hold(self):
        case = test_post_switch.Recovery()
        case.configure()
        _, ecr = installed(case.f)
        case.partial()
        ecr.result = {"imageDetails": []}
        calls = copy.deepcopy(case.world.calls)
        self.assertEqual(case.recover()["status"], "UNCERTAIN")
        self.assertEqual(case.world.calls, calls)
        self.assertEqual(case.store.read()[0]["state"], "ACTIVE")
        self.assertNotIn("dev/" + OP + "/success", case.records.data)

    def test_untagged_and_superseded_images_never_become_automatically_disposable(self):
        # No evidence reconciler or tag removal authority exists. Even a revoked
        # release can remain referenced by an UNCERTAIN journal or another env.
        policies = model.wiring(DOC)[ownership.MODULE]["resource"].get("aws_ecr_lifecycle_policy", {})
        self.assertEqual(policies, {})
