"""Safe holds and counterexamples to head-only administrative recovery.

Illegal releases occur ONLY in the in-memory S3 double to demonstrate why they
must not become a production API. Events control ordering; no timeout is evidence.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch

from scripts import environment_mutation as e
from scripts.owner_recovery import inspect_domain
from scripts.lifecycle import runtime as life
from scripts.tests.mutation.test_mutation import (
    S3, Boundary, authority, guarded_delivery, OP, NEXT, THIRD)


class Interrupted(BaseException):
    pass


class OwnerRecovery(unittest.TestCase):
    def setUp(self):
        self.s3 = S3()
        self.store = self.s3.seed()
        self.sdk = Boundary()

    def send(self, grant):
        e.Client(self.sdk, "ecs", grant, deadline=2**62).update_service(desiredCount=1)
        return {"status": "SUCCESS"}

    def blocked(self, operation=NEXT, binding="normal-delivery/deploy-dev", **kwargs):
        before = copy.deepcopy(self.store.read()[0])
        calls = copy.deepcopy(self.sdk.calls)
        writes = len(self.s3.calls)
        result = e.execute(authority(self.store, operation, binding, **kwargs),
                           lambda _: self.fail("blocked invocation entered controller"))
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(self.store.read()[0], before)
        self.assertEqual(self.sdk.calls, calls)
        self.assertEqual(len(self.s3.calls), writes)

    def test_interrupted_before_first_effect_blocks_all_application_contenders(self):
        owner = authority(self.store)
        def interrupt(_):
            raise Interrupted()
        with self.assertRaises(Interrupted):
            e.execute(owner, interrupt)
        self.assertFalse(owner.touched)
        self.assertEqual(self.store.read()[0]["state"], "ACTIVE")
        self.blocked(OP)
        self.blocked()
        self.blocked(binding="emergency-recovery/emergency-dev")
        self.blocked(binding="cleanup-recovery/cleanup-dev")
        self.blocked(binding="environment-lifecycle/infra-dev", layer="apps")
        self.assertIsNone(owner.retained())

    def test_process_exit_after_effect_does_not_settle_remote_outcome(self):
        owner = authority(self.store)
        def interrupt(grant):
            self.send(grant)
            raise Interrupted()
        with self.assertRaises(Interrupted):
            e.execute(owner, interrupt)
        self.assertEqual(len(self.sdk.calls), 1)
        self.assertIsNone(owner.retained())
        self.blocked(OP)
        self.blocked()

    def test_real_delivery_reconciled_effects_do_not_let_new_invocation_borrow_owner(self):
        owner = authority(self.store)
        records, runtime, controller, raw = guarded_delivery(owner, fail="start")
        self.assertEqual(e.execute(owner, lambda _: controller.run(OP, raw))["status"], "UNCERTAIN")
        calls, journal = copy.deepcopy(runtime.calls), copy.deepcopy(records.data)
        runtime.hidden.clear()  # Effect attribution becomes available, no termination proof.
        result = e.execute(authority(self.store), lambda _: controller.run(OP, raw))
        self.assertEqual(result["status"], "UNCERTAIN")
        self.assertEqual(runtime.calls, calls)
        self.assertEqual(records.data, journal)
        self.assertEqual(self.store.read()[0]["owner"], owner.owner)

    def test_elapsed_deadline_blocks_old_send_and_never_releases_hold(self):
        owner = authority(self.store).acquire()
        client = e.Client(self.sdk, "ecs", owner, deadline=100, clock=lambda: 10**12)
        with self.assertRaises(e.CoordinationError):
            client.update_service(desiredCount=0)
        self.assertEqual(self.sdk.calls, [])
        self.blocked(OP)
        self.blocked()

    def test_uncertain_failure_retains_hold_even_if_local_call_returned(self):
        owner = authority(self.store)
        def fail(grant):
            self.send(grant)
            return {"status": "FAILURE"}
        self.assertEqual(e.execute(owner, fail)["status"], "FAILURE")
        self.assertIsNone(owner.retained())
        self.blocked()

    def test_terminal_before_failed_release_is_historical_not_available_ownership(self):
        owner = authority(self.store)
        put = self.s3.put_object
        def fail_release(**kwargs):
            if kwargs["Key"] == self.store.key and b'"state":"RELEASED"' in kwargs["Body"]:
                raise TimeoutError()
            return put(**kwargs)
        with patch.object(self.s3, "put_object", side_effect=fail_release):
            with self.assertRaises(e.CoordinationError):
                e.execute(owner, self.send)
        self.assertEqual(owner.retained()["status"], "SUCCESS")
        before = copy.deepcopy(self.store.read()[0])
        self.assertEqual(e.execute(authority(self.store), lambda _: self.fail("resend"))["status"], "SUCCESS")
        self.assertEqual(self.store.read()[0], before)
        self.assertEqual(before["state"], "ACTIVE")
        self.blocked()

    def test_unknown_and_corrupt_storage_cannot_establish_recovery(self):
        authority(self.store).acquire()
        self.s3.fail_read = True
        self.assertEqual(e.execute(authority(self.store), self.send)["status"], "UNCERTAIN")
        self.s3.fail_read = False
        self.s3.values[(self.store.bucket, self.store.key)] = (b"{}\n", 100)
        self.assertEqual(e.execute(authority(self.store), self.send)["status"], "UNCERTAIN")
        self.assertEqual(self.sdk.calls, [])

    def test_stale_worker_cannot_send_schedule_release_or_apply_after_legal_new_owner(self):
        old = authority(self.store).acquire()
        old.finish(False, "FAILURE")  # Proven pre-call failure, existing safe path.
        new = authority(self.store, NEXT).acquire()
        old.closed = False  # Stale memory lost release acknowledgement.
        engine = life.Terraform(".", None, {}, None)
        engine.authority = old
        engine._call = lambda _: self.fail("stale provider apply")
        for action in (lambda: self.send(old), old.schedule,
                       lambda: old.finish(True, "SUCCESS"),
                       lambda: engine.call(["apply", "wp5.tfplan"])):
            with self.assertRaises(e.CoordinationError):
                action()
        self.assertEqual(self.store.read()[0]["owner"], new.owner)
        self.assertEqual(self.sdk.calls, [])

    def test_lost_release_ack_is_settled_only_by_exact_readback(self):
        owner = authority(self.store).acquire()
        self.s3.lost_ack = True
        owner.finish(False, "FAILURE")
        self.assertEqual(self.store.read()[0]["state"], "RELEASED")
        self.assertEqual(e.execute(authority(self.store, NEXT), self.send)["status"], "SUCCESS")

    def test_hold_is_scoped_to_environment_and_conflict_domain(self):
        owner = authority(self.store).acquire()
        prod = authority(self.s3.seed("prod"), NEXT, "normal-delivery/promote-prod")
        self.assertEqual(e.execute(prod, self.send)["status"], "SUCCESS")
        shared = authority(self.s3.seed(selected="shared"), THIRD,
                           "environment-lifecycle/infra-dev", layer="shared")
        self.assertEqual(e.execute(shared, lambda _: {"status": "FAILURE"})["status"], "FAILURE")
        self.assertEqual(self.store.read()[0]["owner"], owner.owner)

    def test_e4_partial_switch_keeps_uncertain_result_and_original_owner(self):
        owner = authority(self.store)
        records, runtime, controller, raw = guarded_delivery(owner)
        records.fail = "/switch/observed"
        self.assertEqual(e.execute(owner, lambda _: controller.run(OP, raw))["status"], "UNCERTAIN")
        records.fail = None
        calls = copy.deepcopy(runtime.calls)
        journal = copy.deepcopy(records.data)
        replacement = authority(self.store)
        self.assertEqual(e.execute(replacement, lambda grant: controller.recover_post_switch(
            OP, raw, grant))["status"], "UNCERTAIN")
        self.assertEqual(runtime.calls, calls)
        self.assertEqual(records.data, journal)
        self.assertEqual([stage for stage, _ in calls][-1], "switch")
        self.assertEqual(self.store.read()[0]["owner"], owner.owner)

    def test_counterexample_head_cas_cannot_revoke_send_after_last_check(self):
        old = authority(self.store).acquire()
        checked, resume = threading.Event(), threading.Event()
        check = old._check
        def paused_check():
            etag = check()
            checked.set()
            if not resume.wait(timeout=5):
                raise AssertionError("test barrier did not resume")
            return etag
        with patch.object(old, "_check", side_effect=paused_check), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.send, old)
            try:
                self.assertTrue(checked.wait(timeout=5))
                self.assertFalse(old.touched)  # Even this snapshot cannot prove quiescence.
                self.assertEqual(self.sdk.calls, [])
                self.blocked()
                value, etag = self.store.read()
                # DELIBERATELY UNSAFE, in-memory counterexample only.
                self.store.exchange(dict(value, state="RELEASED"), etag)
                new = authority(self.store, NEXT).acquire()
                self.assertEqual(self.send(new)["status"], "SUCCESS")
            finally:
                resume.set()
            self.assertEqual(future.result(timeout=5)["status"], "SUCCESS")
        self.assertEqual(len(self.sdk.calls), 2)  # Old send AFTER new owner acquired.
        self.assertEqual(self.store.read()[0]["owner"], new.owner)
        with self.assertRaises(e.CoordinationError):
            old.finish(True, "SUCCESS")

    def test_paused_worker_before_check_rejects_changed_generation_on_resume(self):
        old = authority(self.store).acquire()
        entered, resume = threading.Event(), threading.Event()
        check = old._check
        def before_check():
            entered.set()
            if not resume.wait(timeout=5):
                raise AssertionError("test barrier did not resume")
            return check()
        with patch.object(old, "_check", side_effect=before_check), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.send, old)
            try:
                self.assertTrue(entered.wait(timeout=5))
                value, etag = self.store.read()
                # Synthetic head change ONLY; this does not prove safe recovery.
                self.store.exchange(dict(value, state="RELEASED"), etag)
                new = authority(self.store, NEXT).acquire()
            finally:
                resume.set()
            with self.assertRaises(e.CoordinationError):
                future.result(timeout=5)
        self.assertEqual(self.sdk.calls, [])
        self.assertEqual(self.store.read()[0]["owner"], new.owner)

    def test_delayed_cleanup_callback_cannot_use_superseded_schedule(self):
        deployed = authority(self.store).acquire()
        proof = deployed.schedule()
        deployed.finish(True, "SUCCESS")
        newer = authority(self.store, NEXT).acquire()
        newer.schedule()
        newer.finish(True, "SUCCESS")
        writes = len(self.s3.calls)
        old_callback = authority(self.store, THIRD, "cleanup-recovery/cleanup-dev", cleanup=proof)
        self.assertEqual(e.execute(old_callback, self.send)["status"], "UNCERTAIN")
        self.assertEqual(self.sdk.calls, [])
        self.assertEqual(len(self.s3.calls), writes)

    def test_counterexample_head_cas_cannot_cancel_inflight_remote_effect(self):
        old = authority(self.store).acquire()
        entered, resume, effects = threading.Event(), threading.Event(), []
        def remote_effect():
            entered.set()
            if not resume.wait(timeout=5):
                raise AssertionError("test barrier did not resume")
            effects.append("old-completed")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(old.call, remote_effect)
            try:
                self.assertTrue(entered.wait(timeout=5))
                self.blocked()
                value, etag = self.store.read()
                # DELIBERATELY UNSAFE, in-memory counterexample only.
                self.store.exchange(dict(value, state="RELEASED"), etag)
                new = authority(self.store, NEXT).acquire()
                new.call(effects.append, "new-completed")
            finally:
                resume.set()
            future.result(timeout=5)
        self.assertEqual(effects, ["new-completed", "old-completed"])
        self.assertEqual(self.store.read()[0]["owner"], new.owner)


class Diagnostic(unittest.TestCase):
    def setUp(self):
        self.s3 = S3()
        self.store = self.s3.seed()

    def inspect(self, environment="dev", selected="application"):
        return inspect_domain(self.s3, "protected-" + environment, environment, selected)

    def test_active_snapshot_binds_exact_head_version_hash_and_owner_without_writes(self):
        owner = authority(self.store).acquire()
        writes = copy.deepcopy(self.s3.calls)
        report = self.inspect()
        observed = report["observation"]
        self.assertEqual(report["status"], "E2R_BLOCKED_QUIESCENCE_UNPROVED")
        self.assertEqual(observed["head"], owner.value)
        self.assertEqual(observed["version_id"], str(self.s3.version))
        self.assertEqual(observed["etag"], self.store.read()[1])
        self.assertEqual(observed["sha256"], observed["etag"].strip('"'))
        self.assertEqual(report["termination"], "UNPROVED")
        self.assertEqual(report["effects"], "UNRECONCILED")
        self.assertEqual(self.s3.calls, writes)

    def test_released_observation_does_not_claim_recovered_or_successful_deployment(self):
        report = self.inspect()
        self.assertEqual(report["status"], "E2R_RELEASED_OBSERVED")
        self.assertEqual(report["recovery"], "UNAVAILABLE")
        self.assertEqual(report["effects"], "UNRECONCILED")
        self.assertEqual(report["observation"]["head"]["generation"], 0)

    def test_missing_corrupt_contradictory_or_unavailable_evidence_stays_blocked(self):
        for raw in (None, b"bad bytes", b"{}\n", e.canonical(e.initial("prod", "application")),
                    e.canonical(dict(e.initial("dev", "application"), generation=True))):
            if raw is None:
                self.s3.values.clear()
            else:
                self.s3.values[(self.store.bucket, self.store.key)] = (raw, 100)
            result = self.inspect()
            self.assertEqual(result["status"], "E2R_BLOCKED_HEAD_UNPROVED")
            self.assertIsNone(result["observation"])
        self.s3.fail_read = True
        self.assertIsNone(self.inspect()["observation"])
        self.assertEqual(len(self.s3.calls), 1)  # Only installation seed.

    def test_transport_headers_and_noncanonical_bytes_are_not_audit_evidence(self):
        get = self.s3.get_object
        for field, value in (("ETag", ""), ("VersionId", "latest"), ("VersionId", None)):
            with patch.object(self.s3, "get_object", side_effect=lambda **kw: dict(get(**kw), **{field: value})):
                self.assertIsNone(self.inspect()["observation"])
        raw, version = self.s3.values[(self.store.bucket, self.store.key)]
        self.s3.values[(self.store.bucket, self.store.key)] = (raw + b" ", version)
        self.assertIsNone(self.inspect()["observation"])

    def test_competing_and_repeated_administrative_diagnostics_cannot_release(self):
        owner = authority(self.store).acquire()
        writes = copy.deepcopy(self.s3.calls)
        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(pool.map(lambda _: self.inspect(), range(2)))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(self.inspect(), reports[0])
        self.assertEqual(self.store.read()[0], owner.value)
        self.assertEqual(self.s3.calls, writes)
        self.assertTrue(all(report["recovery"] == "UNAVAILABLE" for report in reports))

    def test_operator_assertions_are_not_accepted_as_recovery_evidence(self):
        owner = authority(self.store).acquire()
        for claim in (dict(admin=True), dict(terminated=True), dict(force=True),
                      dict(expected_generation=owner.value["generation"])):
            with self.assertRaises(TypeError):
                inspect_domain(self.s3, "protected-dev", "dev", **claim)
        self.assertEqual(self.store.read()[0], owner.value)

    def test_environment_domain_mismatch_cannot_relabel_an_observed_head(self):
        authority(self.store).acquire()
        self.assertIsNone(self.inspect("prod")["observation"])
        self.assertIsNone(self.inspect(selected="shared")["observation"])
        raw, version = self.s3.values[(self.store.bucket, self.store.key)]
        self.s3.values[("protected-prod", "arbitration/prod/application.json")] = (raw, version)
        self.assertIsNone(self.inspect("prod")["observation"])
        self.assertEqual(self.store.read()[0]["state"], "ACTIVE")

    def test_diagnostic_snapshot_never_authorizes_later_generation(self):
        owner = authority(self.store).acquire()
        snapshot = self.inspect()
        owner.finish(False, "FAILURE")
        newer = authority(self.store, NEXT).acquire()
        current = self.inspect()
        self.assertNotEqual(snapshot["observation"], current["observation"])
        self.assertEqual(snapshot["recovery"], current["recovery"])
        self.assertEqual(self.store.read()[0], newer.value)
