"""Deterministic interleavings at installed SDK, E1 journal and WP5 apply boundaries."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import environment_mutation as e
from scripts.normal_delivery import delivery as d
from scripts.tests.delivery.fixtures import setup, OP, NEXT
from scripts.tests.recovery.fixtures import application
from scripts.lifecycle import runtime as life
from scripts.lifecycle.controller import Controller
from test_wp4d import ACCOUNT, REGION, policy, permits
import wp5_iam

ROOT = Path(__file__).resolve().parents[3]
THIRD = "99999999-2222-3333-4444-555555555555"


class Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class S3:
    """Linearizable S3 conditional-write double, separate contender transports."""
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()
        self.barrier = None
        self.fail_read = False
        self.drop_write = False
        self.lost_ack = False
        self.calls = []
        self.version = 0
    def get_object(self, **kw):
        if self.fail_read:
            raise OSError("storage unavailable")
        with self.lock:
            value = self.values.get((kw["Bucket"], kw["Key"]))
            if value is None:
                raise Missing()
            raw, version = value
            result = dict(Body=io.BytesIO(raw), VersionId=str(version),
                          ETag='"'+hashlib.sha256(raw).hexdigest()+'"')
        if self.barrier and kw["Key"].endswith("/application.json") and json.loads(raw)["generation"] == 0:
            self.barrier.wait(timeout=5)
        return result
    def put_object(self, **kw):
        with self.lock:
            self.calls.append(copy.deepcopy(kw))
            if self.drop_write:
                raise TimeoutError()
            key = kw["Bucket"], kw["Key"]
            old = self.values.get(key)
            if kw.get("IfNoneMatch") == "*":
                if old is not None:
                    raise FileExistsError()
            elif "IfMatch" in kw:
                if old is None or kw["IfMatch"] != '"'+hashlib.sha256(old[0]).hexdigest()+'"':
                    raise FileExistsError()
            else:
                raise AssertionError("unconditional write")
            self.version += 1
            self.values[key] = kw["Body"], self.version
        if self.lost_ack:
            raise TimeoutError()
    def seed(self, env="dev", selected="application"):
        store = e.Store(self, "protected-"+env, env, selected)
        store.initialize()
        return store


class Boundary:
    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.resume = threading.Event()
        self.pause = False
    def update_service(self, **kw):
        self.calls.append(("ecs", kw))
        if self.pause:
            self.entered.set()
            assert self.resume.wait(timeout=5)
        return {}
    def modify_listener(self, **kw):
        self.calls.append(("alb", kw))
        return {}
    def describe_services(self, **kw):
        return {"services":[]}
    def put_rule(self, **kw):
        self.calls.append(("rule", kw))
        return {}
    def put_targets(self, **kw):
        self.calls.append(("targets",kw))
        return {"FailedEntryCount":0}


def authority(store, operation=OP, binding="normal-delivery/deploy-dev", request=None, **kw):
    return e.Authority(store,binding,operation,request or {},**kw)


def guarded_delivery(owner, endpoint="deploy-dev", fail=None):
    facts, auth, records, runtime, process, controller, raw = setup(endpoint)
    for stage in d.STAGES:
        original = getattr(runtime,stage)
        setattr(runtime,stage,lambda *args, method=original: owner.call(method,*args))
    if fail:
        runtime.hidden.add(fail)
    return records,runtime,controller,raw


def bootstrap():
    spec=importlib.util.spec_from_file_location("installed",ROOT/"scripts/wp4d/installed.py")
    installed=importlib.util.module_from_spec(spec);spec.loader.exec_module(installed)
    sys.modules["installed"]=installed
    spec=importlib.util.spec_from_file_location("e2_bootstrap",ROOT/"scripts/wp4d/runtime.py")
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


class Arbitration(unittest.TestCase):
    def setUp(self):
        self.s3=S3();self.store=self.s3.seed();self.sdk=Boundary()
    def body(self,owner):
        e.Client(self.sdk,"ecs",owner,deadline=2**62).update_service(cluster="fixed",service="fixed",desiredCount=1)
        return {"status":"SUCCESS"}
    def test_two_simultaneous_installed_mutations_one_environment(self):
        self.s3.barrier=threading.Barrier(2)
        owners=[authority(self.store),authority(e.Store(self.s3,"protected-dev","dev"),NEXT)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda owner:e.execute(owner,self.body),owners))
        self.assertEqual(sorted(x["status"] for x in results),["SUCCESS","UNCERTAIN"])
        self.assertEqual(len(self.sdk.calls),1)
    def test_different_classes_cannot_cross_paused_sdk_boundary(self):
        owner=authority(self.store);self.sdk.pause=True
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(e.execute,owner,self.body)
            self.assertTrue(self.sdk.entered.wait(timeout=5))
            for binding in ("normal-delivery/deploy-dev","emergency-recovery/emergency-dev",
                            "environment-lifecycle/infra-dev"):
                other=authority(self.store,NEXT,binding,layer="apps") if binding.startswith("environment") else authority(self.store,NEXT,binding)
                self.assertEqual(e.execute(other,self.body)["status"],"UNCERTAIN")
            self.sdk.resume.set()
            self.assertEqual(future.result(timeout=5)["status"],"SUCCESS")
        self.assertEqual(len(self.sdk.calls),1)
    def test_dev_prod_independent_boundaries(self):
        dev=authority(self.store).acquire()
        prod=authority(self.s3.seed("prod"),NEXT,"normal-delivery/promote-prod")
        self.assertEqual(e.execute(prod,self.body)["status"],"SUCCESS")
        dev.finish()
    def test_unrelated_sns_and_metadata_domains_independent(self):
        owner=authority(self.store).acquire()
        for selected,op in (("shared",NEXT),("secrets",THIRD)):
            other=authority(self.s3.seed(selected=selected),op,"environment-lifecycle/infra-dev",layer=selected)
            def unrelated(grant):
                grant.call(self.sdk.calls.append,(selected,{}))
                return {"status":"SUCCESS"}
            self.assertEqual(e.execute(other,unrelated)["status"],"SUCCESS")
        owner.finish()
    def test_cross_environment_binding_rejected(self):
        with self.assertRaises(e.CoordinationError):
            authority(self.store,NEXT,"normal-delivery/promote-prod")
    def test_expired_operation_deadline_cannot_take_over_active_owner(self):
        owner=authority(self.store).acquire()
        # E2 accepts no clock or expiration evidence. Even arbitrarily late
        # invocations with the same logical ID cannot steal a live grant.
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
        self.assertEqual(e.execute(authority(self.store,NEXT),self.body)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls,[])
        self.assertEqual(self.store.read()[0]["owner"],owner.owner)
    def test_crash_after_mutation_retains_owner_and_no_resend(self):
        class Crash(BaseException):pass
        owner=authority(self.store)
        def crash(grant):
            self.body(grant)
            raise Crash()
        with self.assertRaises(Crash):e.execute(owner,crash)
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
        self.assertEqual(len(self.sdk.calls),1)
    def test_interruption_before_mutation_also_never_inferrs_termination(self):
        class Cancel(BaseException):pass
        with self.assertRaises(Cancel):
            e.execute(authority(self.store),lambda grant:(_ for _ in ()).throw(Cancel()))
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertEqual(e.execute(authority(self.store,NEXT),self.body)["status"],"UNCERTAIN")
    def test_old_worker_fenced_after_new_generation(self):
        old=authority(self.store).acquire();old.finish()
        new=authority(self.store,NEXT).acquire()
        old.closed=False  # simulate a stale worker that lost release readback
        with self.assertRaises(e.CoordinationError):
            e.Client(self.sdk,"ecs",old,deadline=2**62).update_service(desiredCount=0)
        # Old CAS release cannot overwrite the new active owner.
        with self.assertRaises(e.CoordinationError):old.finish(True)
        self.assertEqual(self.store.read()[0]["owner"],new.owner)
        self.assertEqual(self.sdk.calls,[])
    def test_lost_ack_acquisition_and_release_exact_readback(self):
        self.s3.lost_ack=True
        result=e.execute(authority(self.store),self.body)
        self.assertEqual(result["status"],"SUCCESS")
        self.assertEqual(self.store.read()[0]["state"],"RELEASED")
    def test_failed_cas_never_calls_mutation(self):
        self.s3.drop_write=True
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls,[])
    def test_corrupt_or_missing_head_fails_closed(self):
        for raw in (None,b"{}\n",b"not-json",e.canonical(dict(e.initial("prod","application"))),
                    e.canonical(dict(e.initial("dev","application"),generation=True))):
            if raw is None:self.s3.values.pop((self.store.bucket,self.store.key),None)
            else:self.s3.values[self.store.bucket,self.store.key]=(raw,99)
            self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
            self.assertEqual(self.sdk.calls,[])
    def test_storage_read_error_at_mutation_boundary_fails_closed(self):
        grant=authority(self.store).acquire();self.s3.fail_read=True
        with self.assertRaises(OSError):self.body(grant)
        self.assertEqual(self.sdk.calls,[])
    def test_readonly_sdk_observation_needs_no_grant(self):
        self.assertEqual(e.Client(self.sdk,"ecs",authority(self.store)).describe_services(),{"services":[]})
    def test_terminal_retry_never_reacquires_or_republishes(self):
        owner=authority(self.store)
        self.assertEqual(e.execute(owner,self.body)["status"],"SUCCESS")
        self.assertEqual(e.execute(authority(self.store,NEXT),self.body)["status"],"SUCCESS")
        generation=self.store.read()[0]["generation"]
        self.assertEqual(e.execute(authority(self.store),lambda _:self.fail("resend"))["status"],"SUCCESS")
        self.assertEqual(self.store.read()[0]["generation"],generation)
        self.assertEqual(len(self.sdk.calls),2)
    def test_terminal_changed_request_cannot_claim_success(self):
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"SUCCESS")
        self.assertEqual(e.execute(authority(self.store,request={"replicas":2}),self.body)["status"],"UNCERTAIN")
        self.assertEqual(len(self.sdk.calls),1)
    def test_uncertain_effect_never_releases_or_claims_success(self):
        owner=authority(self.store)
        def body(grant):
            self.body(grant)
            return {"status":"UNCERTAIN"}
        self.assertEqual(e.execute(owner,body)["status"],"UNCERTAIN")
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertIsNone(owner.retained())
    def test_failure_before_effect_releases_and_retains_failure(self):
        self.assertEqual(e.execute(authority(self.store),lambda _:{"status":"FAILURE"})["status"],"FAILURE")
        self.assertEqual(self.store.read()[0]["state"],"RELEASED")
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"FAILURE")
        self.assertEqual(self.sdk.calls,[])
    def test_cleanup_old_generation_after_new_activation_cannot_mutate(self):
        deployed=authority(self.store).acquire()
        proof=deployed.schedule();deployed.finish(True)
        newer=authority(self.store,NEXT).acquire();newer.schedule();newer.finish(True)
        cleanup=authority(self.store,THIRD,"cleanup-recovery/cleanup-dev",cleanup=proof)
        self.assertEqual(e.execute(cleanup,self.body)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls,[])
    def test_cleanup_authority_blocks_new_activation_and_consumes_schedule(self):
        deployed=authority(self.store).acquire();proof=deployed.schedule();deployed.finish(True)
        clean=authority(self.store,NEXT,"cleanup-recovery/cleanup-dev",cleanup=proof).acquire()
        self.assertEqual(e.execute(authority(self.store,THIRD),self.body)["status"],"UNCERTAIN")
        self.assertEqual(self.body(clean)["status"],"SUCCESS");clean.finish(True)
        self.assertIsNone(self.store.read()[0]["schedule"])
    def test_scheduler_emits_native_event_identity_and_exact_generation(self):
        owner=authority(self.store).acquire()
        client=e.Client(self.sdk,"events",owner,deadline=2**62)
        client.put_rule(Name="fixed")
        client.put_targets(Rule="fixed",Targets=[dict(Id="scale-down",Arn="fixed-function")])
        actual=self.sdk.calls[-1][1]["Targets"][0]["InputTransformer"]
        self.assertEqual(actual,e.cleanup_transformer(owner.value["schedule"]))
        self.assertIn('"id":<id>',actual["InputTemplate"])
        self.assertEqual(actual["InputPathsMap"]["resources"],"$.resources")
    def test_real_delivery_journal_positive_and_terminal_retry(self):
        owner=authority(self.store)
        records,runtime,controller,raw=guarded_delivery(owner)
        self.assertEqual(e.execute(owner,lambda _:controller.run(OP,raw))["status"],"SUCCESS")
        calls=len(runtime.calls)
        self.assertEqual(e.execute(authority(self.store),lambda _:controller.run(OP,raw))["status"],"SUCCESS")
        self.assertEqual(len(runtime.calls),calls)
        self.assertEqual([stage for stage,_ in runtime.calls if stage != "e3"],list(d.STAGES))
    def test_real_delivery_retry_reconciles_unknown_without_blind_resend(self):
        owner=authority(self.store)
        records,runtime,controller,raw=guarded_delivery(owner,fail="start")
        self.assertEqual(e.execute(owner,lambda _:controller.run(OP,raw))["status"],"UNCERTAIN")
        calls=len(runtime.calls);runtime.hidden.clear()
        self.assertEqual(e.execute(owner,lambda _:controller.run(OP,raw))["status"],"SUCCESS")
        self.assertEqual(sum(stage=="start" for stage,_ in runtime.calls),1)
        self.assertGreater(len(runtime.calls),calls)
    def test_real_emergency_and_cleanup_journals_have_contended_boundary(self):
        for kind,binding in (("emergency","emergency-recovery/emergency-dev"),
                             ("cleanup","cleanup-recovery/cleanup-dev")):
            s3=S3();store=s3.seed();deployed=authority(store).acquire();proof=deployed.schedule();deployed.finish(True)
            ctrl,runtime,_,_=application(kind,running=2)
            grant=authority(store,NEXT,binding,cleanup=proof if kind=="cleanup" else None)
            original=runtime.mutate
            runtime.mutate=lambda *args:grant.call(original,*args)
            self.assertEqual(e.execute(grant,lambda _:ctrl.run(NEXT,b"{}\n"))["status"],"SUCCESS")
            self.assertTrue(runtime.calls)
    def test_wp5_saved_plan_apply_requires_current_owner(self):
        engine=life.Terraform(".",None,{},None)
        engine._call=lambda args:self.sdk.calls.append(("terraform",args))
        with self.assertRaises(ValueError):engine.call(["apply","wp5.tfplan"])
        owner=authority(self.store,NEXT,"environment-lifecycle/infra-dev",layer="platform").acquire()
        engine.authority=owner;engine.call(["apply","wp5.tfplan"]);owner.finish(True)
        other=authority(self.store,THIRD).acquire()
        with self.assertRaises(e.CoordinationError):engine.call(["apply","wp5.tfplan"])
        self.assertEqual(len(self.sdk.calls),1)
    def test_installed_entrypoint_contention_stops_real_transport_before_sdk(self):
        module=bootstrap()
        from test_wp4d import installed_projection
        doc=json.loads((ROOT/"terraform/infra/security/authority.json").read_text())
        _,_,bindings=installed_projection(doc)
        config=dict(environment="dev",binding="normal-delivery/deploy-dev",account=ACCOUNT,region=REGION,
                    evidence_bucket="protected-dev",admin_bucket="fixed",dev_evidence_bucket="fixed",
                    repository="fixed",resources=bindings["dev"])
        owner=authority(self.store).acquire()
        clients=dict(s3=self.s3,ecs=self.sdk,elbv2=self.sdk,events=self.sdk,ecr=None)
        with patch.object(module,"_wakeup",return_value=(NEXT,{})),patch.object(d.Delivery,"run",side_effect=AssertionError("entered busy controller")):
            self.assertEqual(module._normal(clients,config)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls,[])
    def test_installed_entrypoint_constructs_guarded_transport_and_holds_failure(self):
        module=bootstrap()
        from test_wp4d import installed_projection
        doc=json.loads((ROOT/"terraform/infra/security/authority.json").read_text())
        _,_,bindings=installed_projection(doc)
        config=dict(environment="dev",binding="normal-delivery/deploy-dev",account=ACCOUNT,region=REGION,
                    evidence_bucket="protected-dev",admin_bucket="fixed",dev_evidence_bucket="fixed",
                    repository="fixed",resources=bindings["dev"])
        clients=dict(s3=self.s3,ecs=self.sdk,elbv2=self.sdk,events=self.sdk,ecr=None)
        def run(ctrl,operation,raw):
            ctrl.runtime.remembered=lambda *args:None
            ctrl.runtime.switch("dev/"+operation+"/switch",
                dict(listener=config["resources"]["colors"]["blue"]["listener"],
                     target=config["resources"]["colors"]["blue"]["target_group"]),ctrl.runtime.now()+30)
            return {"status":"UNCERTAIN"}
        # The public immutable status write is existing E1 If-None-Match evidence.
        with patch.object(module,"_wakeup",return_value=(OP,{})),patch.object(d.Delivery,"run",run):
            self.assertEqual(module._normal(clients,config)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls[0][0],"alb")
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")


    def test_terminal_write_failure_retains_authority_and_no_success(self):
        owner=authority(self.store)
        def body(grant):
            self.body(grant)
            self.s3.drop_write=True
            return {"status":"SUCCESS"}
        with self.assertRaises(e.CoordinationError):e.execute(owner,body)
        self.s3.drop_write=False
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertEqual(e.execute(authority(self.store,NEXT),self.body)["status"],"UNCERTAIN")
        self.assertEqual(len(self.sdk.calls),1)

    def test_same_logical_operation_two_invocations_during_mutation(self):
        owner=authority(self.store);self.sdk.pause=True
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(e.execute,owner,self.body)
            self.assertTrue(self.sdk.entered.wait(timeout=5))
            self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
            self.sdk.resume.set()
            self.assertEqual(future.result(timeout=5)["status"],"SUCCESS")
        self.assertEqual(len(self.sdk.calls),1)

    def test_malformed_ownership_headers_cannot_authorize_sdk_call(self):
        original=self.s3.get_object
        for field,replacement in (("ETag",None),("ETag",""),("VersionId","latest"),("VersionId",None)):
            self.s3.get_object=lambda **kw:dict(original(**kw),**{field:replacement})
            self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
            self.assertEqual(self.sdk.calls,[])
        self.s3.get_object=original

    def test_cleanup_retry_after_new_deployment_does_not_enter_old_controller(self):
        deployed=authority(self.store).acquire();proof=deployed.schedule();deployed.finish(True)
        ctrl,runtime,records,_=application("cleanup",running=2)
        old=authority(self.store,NEXT,"cleanup-recovery/cleanup-dev",cleanup=proof)
        # A delayed event reaches the actual E1 cleanup controller only if its
        # admission is still valid; a newer activation invalidates it first.
        newer=authority(self.store,THIRD).acquire()
        newer.schedule();newer.finish(True)
        self.assertEqual(e.execute(old,lambda _:ctrl.run(NEXT,b"{}\\n"))["status"],"UNCERTAIN")
        self.assertEqual(runtime.calls,[])
        self.assertFalse(any("/recovery/cleanup/" in key for key in records.data))

    def test_actual_schedule_readback_rejects_absent_or_wrong_transformer(self):
        from scripts.wp4d.aws_runtime import Delivery
        owner=authority(self.store).acquire();proof=owner.schedule()
        target=dict(Id="scale-down",Arn="fixed")
        class Events:
            def describe_rule(self,**kw):return {"ScheduleExpression":"rate(5 minutes)","State":"ENABLED"}
            def list_targets_by_rule(self,**kw):return {"Targets":[self.target]}
        events=Events();events.target=dict(target)
        runtime=object.__new__(Delivery);runtime.events=e.Client(events,"events",owner)
        schedule=dict(rule="fixed",expression="rate(5 minutes)")
        self.assertFalse(runtime._schedule_matches(schedule,target))
        events.target=e.scheduled_target(runtime.events,target)
        self.assertTrue(runtime._schedule_matches(schedule,target))
        events.target["InputTransformer"]=e.cleanup_transformer(dict(proof,generation=proof["generation"]+1))
        self.assertFalse(runtime._schedule_matches(schedule,target))


    def test_unknown_before_call_also_requires_explicit_reconciliation(self):
        self.assertEqual(e.execute(authority(self.store),lambda _:{"status":"UNCERTAIN"})["status"],"UNCERTAIN")
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertEqual(e.execute(authority(self.store,NEXT),self.body)["status"],"UNCERTAIN")

    def test_wp5_real_journal_unknown_retains_grant_and_retry_never_applies(self):
        from scripts.tests.lifecycle.test_lifecycle import projection,request,Memory,Engine,Checked,plan,DOC
        binding="environment-lifecycle/infra-dev"
        _,_,bindings=projection();protected=bindings[binding]["configuration"]
        value=request(DOC["wp5"]["selected"][binding]["package_sha256"])
        owner=e.Authority(self.store,binding,value["operation_id"],value,layer="platform")
        records=Memory();engine=Engine(plan())
        def apply(*args):
            bridge=life.Terraform(".",None,protected,owner)
            def failed(argv):
                engine.applies+=1
                raise TimeoutError("unknown apply")
            bridge._call=failed
            bridge.call(["apply","wp5.tfplan"])
        engine.apply=apply
        controller=Controller(binding,protected,Checked(),engine,records)
        self.assertEqual(e.execute(owner,lambda _:controller.run(value),"state")["state"],"UNKNOWN")
        self.assertEqual(self.store.read()[0]["state"],"ACTIVE")
        self.assertEqual(controller.run(value)["state"],"UNKNOWN")
        self.assertEqual(engine.applies,1)


    def test_corrupt_terminal_status_cannot_become_success(self):
        owner=authority(self.store)
        self.assertEqual(e.execute(owner,lambda _:{"status":"FAILURE"})["status"],"FAILURE")
        key=(self.store.bucket,owner.terminal_key())
        value=json.loads(self.s3.values[key][0]);value["status"]="SUCCESS"
        self.s3.values[key]=(e.canonical(value),99)
        self.assertEqual(e.execute(authority(self.store),self.body)["status"],"UNCERTAIN")
        self.assertEqual(self.sdk.calls,[])


    def test_storage_read_consuming_deadline_cannot_send_aws_mutation(self):
        owner=authority(self.store).acquire()
        clock=[1000]
        original=self.s3.get_object
        def delayed(**kw):
            value=original(**kw)
            if kw["Key"]==self.store.key:clock[0]=1001
            return value
        self.s3.get_object=delayed
        client=e.Client(self.sdk,"ecs",owner,deadline=1001,clock=lambda:clock[0])
        with self.assertRaises(e.CoordinationError):client.update_service(desiredCount=0)
        self.assertEqual(self.sdk.calls,[])

    def test_unbound_mutation_deadline_fails_closed(self):
        owner=authority(self.store).acquire()
        with self.assertRaises(e.CoordinationError):
            e.Client(self.sdk,"ecs",owner).update_service(desiredCount=0)
        self.assertEqual(self.sdk.calls,[])


    def test_cleanup_rejects_boolean_and_float_generation_evidence(self):
        deployed=authority(self.store).acquire()
        proof=deployed.schedule();deployed.finish(True)
        for malformed in (True,1.0):
            cleanup=authority(self.store,NEXT,"cleanup-recovery/cleanup-dev",
                              cleanup=dict(proof,generation=malformed))
            self.assertEqual(e.execute(cleanup,self.body)["status"],"UNCERTAIN")
            self.assertEqual(self.sdk.calls,[])


class Permissions(unittest.TestCase):
    def test_only_own_controller_coordination_key_and_terminal_are_admitted(self):
        for binding in ("normal-delivery/deploy-dev","emergency-recovery/emergency-dev",
                        "cleanup-recovery/cleanup-dev"):
            p=policy(binding);base=f"arn:aws:s3:::e1-wp4-dev-{ACCOUNT}-{REGION}/arbitration/dev/"
            self.assertTrue(permits(p,"s3:GetObject",base+"application.json"))
            self.assertTrue(permits(p,"s3:PutObject",base+"application.json",{"s3:if-match":"etag"}))
            for context in ({},{"s3:if-none-match":"*"}):
                self.assertFalse(permits(p,"s3:PutObject",base+"application.json",context))
            self.assertFalse(permits(p,"s3:DeleteObject",base+"application.json"))
            self.assertFalse(permits(p,"s3:PutObject",base+"shared.json",{"s3:if-match":"etag"}))
            terminal=base+"terminals/"+binding+"/"+OP+".json"
            self.assertTrue(permits(p,"s3:PutObject",terminal,{"s3:if-none-match":"*"}))
            self.assertFalse(permits(p,"s3:PutObject",terminal,{"s3:if-match":"etag"}))
            self.assertFalse(permits(p,"s3:PutObject",terminal.replace("dev","prod"),{"s3:if-none-match":"*"}))
    def test_gateways_nat_and_public_callers_get_no_coordination_authority(self):
        for binding in ("request-gateway/deploy-dev","nat-recovery/nat-dev/assign_eip",
                        "nat-recovery/nat-dev/change_rt","nat-recovery/nat-dev/disable_sdc"):
            p=policy(binding);key=f"arn:aws:s3:::e1-wp4-dev-{ACCOUNT}-{REGION}/arbitration/dev/application.json"
            for action in ("s3:GetObject","s3:PutObject","s3:DeleteObject"):
                self.assertFalse(permits(p,action,key,{"s3:if-match":"etag"}))
    def test_lifecycle_only_own_heads_and_terminals_no_delivery_evidence(self):
        resources={kind:[] for kind in wp5_iam.INVENTORY}
        p=wp5_iam.policy("environment-lifecycle/infra-dev",ACCOUNT,REGION,resources,"a"*64,"version")
        base=f"arn:aws:s3:::e1-wp4-dev-{ACCOUNT}-{REGION}/"
        for selected in ("application","shared","secrets"):
            self.assertTrue(permits(p,"s3:PutObject",base+"arbitration/dev/"+selected+".json",{"s3:if-match":"etag"}))
        for key in ("delivery/dev/"+OP+"/success","history/blue.json",
                    "arbitration/prod/application.json"):
            self.assertFalse(permits(p,"s3:PutObject",base+key,{"s3:if-match":"etag"}))
