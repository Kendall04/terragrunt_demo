"""Focused drain regressions composed into the existing WP4D health boundary."""
import copy
import importlib.util
from pathlib import Path
from unittest.mock import patch
from scripts.wp4d.aws_runtime import Application as Base, Observer
from scripts.wp4d.dev_cleanup import application
from scripts.environment_mutation import Authority, CoordinationError


def exercise(test):
    class Records:
        def __init__(self): self.items = {"dev/recovery/cleanup/op/scale_zero/attempt": b"attempt"}
        def read(self, key): return {"bytes": self.items[key]} if key in self.items else None
        def create(self, key, raw):
            if key in self.items: raise FileExistsError(key)
            self.items[key] = raw
    class ECS:
        def __init__(self): self.calls = []
        def update_service(self, **request): self.calls.append(copy.deepcopy(request))
    class ELB:
        def __init__(self, clock, until): self.clock, self.until = clock, until; self.mode = None; self.reads = 0
        def describe_target_health(self, **request):
            self.reads += 1
            if self.mode == "error": raise OSError("read unavailable")
            if self.mode == "missing": return {}
            if self.mode == "transient" and self.reads < 3: raise OSError("eventual read")
            return {"TargetHealthDescriptions": ([{"Target":{"Id":"10.0.1.2","Port":8080},
                    "TargetHealth":{"State":"draining"}}] if self.clock[0] < self.until else [])}
    class Observation:
        def __init__(self, clock, active_until): self.clock, self.active_until = clock, active_until
        def service(self, color):
            active = self.clock[0] < self.active_until
            return ({"desiredCount":0,"runningCount":int(active),"pendingCount":0},
                    [{"lastStatus":"RUNNING"}] if active else [], not active)
    token = "dev/recovery/cleanup/op/scale_zero"
    request = {"cluster":"cluster","service":"blue","desiredCount":0}
    config = {"environment":"dev","colors":{"blue":{"cluster":"cluster","service":"blue","target_group":"tg"}}}
    def setup(active_until=0, target_until=0, mode=None):
        clock = [0];ecs = ECS();elb = ELB(clock,target_until);elb.mode = mode;records = Records()
        port = application(Base)(ecs,elb,None,records,config,None)
        port.now = lambda: clock[0];port.observer = Observation(clock,active_until)
        return port,clock,ecs,elb,records
    for name,active,target,mode,budget,expected in (
            ("blue-active",4,12,None,20,"APPLIED"),
            ("stopped-target-draining",0,8,None,20,"APPLIED"),
            ("no-tasks-no-targets",0,0,None,20,"APPLIED"),
            ("temporary-read-failure",0,8,"transient",20,"APPLIED"),
            ("real-deadline",0,100,None,10,"UNKNOWN"),
            ("read-error-is-not-absence",0,0,"error",8,"UNKNOWN"),
            ("missing-response-is-not-absence",0,0,"missing",8,"UNKNOWN")):
        with test.subTest(cleanup=name):
            port,clock,ecs,elb,records=setup(active,target,mode)
            with patch("scripts.wp4d.dev_cleanup.time.sleep",side_effect=lambda n: clock.__setitem__(0,clock[0]+n)):
                port.mutate("scale_zero",token,request,budget)
                result=port.effect(token, min(30,budget))
            test.assertEqual(result["state"],expected);test.assertEqual(ecs.calls,[request])
            test.assertIn(token+"/ack",records.items)
            if expected=="APPLIED": test.assertGreaterEqual(clock[0],target)
            else: test.assertGreaterEqual(clock[0],budget)
            # Prior FAILURE bytes and attempts are not converted into success.
            records.items["previous/outcome"]=b'{"status":"FAILURE"}\n'
            test.assertEqual(records.items["previous/outcome"],b'{"status":"FAILURE"}\n')
    with test.subTest(cleanup="retry-idempotent-terminal-readback"):
        port,clock,ecs,elb,records=setup(0,100);port.mutate("scale_zero",token,request,10)
        frozen=copy.deepcopy(records.items)
        retry=application(Base)(ecs,elb,None,records,config,None);retry.observer=Observation(clock,0);retry.now=lambda:clock[0]
        with patch("scripts.wp4d.dev_cleanup.time.sleep",side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            test.assertEqual(retry.effect(token,10)["state"],"UNKNOWN")
            elb.until=0
            test.assertEqual(retry.effect(token,20)["state"],"APPLIED")
        test.assertEqual(ecs.calls,[request]);test.assertEqual(records.items,frozen)
    with test.subTest(cleanup="original-failure-condition"):
        port,clock,ecs,elb,records=setup(0,100)
        # The exact pre-fix production Observer rejects STOPPED/absent tasks
        # while their ALB target is still draining; a timeout is not necessary.
        with test.assertRaises(ValueError): Observer(None,elb,config).targets("blue",[])
    with test.subTest(cleanup="CAS-failure-keeps-authority-and-prior-failure"):
        path=Path(__file__).resolve().parents[1]/"mutation/test_mutation.py"
        spec=importlib.util.spec_from_file_location("cleanup_conditional_storage",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class Conditional(module.S3):
            reject=False
            def put_object(self,**kw):
                if self.reject and kw["Key"].endswith("/application.json") and "IfMatch" in kw:
                    raise FileExistsError("CAS rejected")
                return super().put_object(**kw)
        storage=Conditional();store=storage.seed();owner=Authority(store,"normal-delivery/deploy-dev","11111111-2222-3333-4444-555555555555",{})
        owner.acquire();before=store.read();storage.values[("protected-dev","prior/failure")]=(b'{"status":"FAILURE"}\n',"prior-version")
        storage.reject=True
        with test.assertRaises(CoordinationError): owner.finish(True,"SUCCESS")
        test.assertEqual(store.read(),before);test.assertEqual(store.read()[0]["state"],"ACTIVE")
        test.assertEqual(storage.values[("protected-dev","prior/failure")],(b'{"status":"FAILURE"}\n',"prior-version"))
