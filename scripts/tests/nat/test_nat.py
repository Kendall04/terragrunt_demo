"""Actual NAT controllers, generated authority, launch bytes and read-only evidence."""
import base64
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import model
from terraform_console import decode as console_json
import wp4d
import wp5
from test_wp4d import ACCOUNT, REGION, installed_projection, policy, permits
from scripts.nat import reliability as n
from scripts.wp4d.nat_resolver import Resolver
from scripts.wp4d.aws_runtime import Nat

ROOT = Path(__file__).resolve().parents[3]
DOC = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
UUID = "11111111-1111-4111-8111-111111111111"


def bootstrap():
    spec = importlib.util.spec_from_file_location("installed", ROOT / "scripts/wp4d/installed.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sys.modules["installed"] = module
    spec = importlib.util.spec_from_file_location("e13_bootstrap", ROOT / "scripts/wp4d/runtime.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def fixture(env="dev"):
    slots = installed_projection(DOC)[2][env]["nat_slots"]
    data = (ROOT / "scripts/nat/user_data.sh").read_bytes().replace(b"\r\n", b"\n")
    for slot in slots:
        slot["spec"]["user_data_sha256"] = hashlib.sha256(data).hexdigest()
    config = {"environment": env, "account": ACCOUNT, "region": REGION, "nat_slots": slots,
              "evidence_bucket": f"e1-wp4-{env}-{ACCOUNT}-{REGION}"}
    event = {"id": UUID, "account": ACCOUNT, "region": REGION, "source": "aws.autoscaling",
             "detail-type": "EC2 Instance Launch Successful", "time": datetime.now(timezone.utc).isoformat(),
             "detail": {"AutoScalingGroupName": slots[0]["asg"], "EC2InstanceId": "i-00000001"}}
    return slots, data, config, event


class Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class S3:
    def __init__(self): self.values = {}
    def get_object(self, Bucket, Key):
        if Key not in self.values: raise Missing()
        return {"VersionId": "OFFLINE_ONLY", "Body": io.BytesIO(self.values[Key])}
    def put_object(self, Bucket, Key, Body, **kwargs):
        assert kwargs["IfNoneMatch"] == "*" and Key not in self.values
        self.values[Key] = Body


class AWS:
    """SDK-shaped doubles; every mutation is visible, no credentials available."""
    def __init__(self, env="dev"):
        self.slots, self.data, self.config, self.event = fixture(env)
        self.eip = [None, "eni-00000002"]; self.route = [None, "eni-00000002"]
        self.sdc = [True, False]; self.calls = []; self.console = "good"; self.route_state = "active"
        self.foreign = None; self.stamp = int(time.time()) - 1
    def slot(self, value): return self.slots[int(value[-1])-1]
    def describe_auto_scaling_groups(self, AutoScalingGroupNames):
        s = self.slot(AutoScalingGroupNames[0]); i = int(s["asg"][-1])
        return {"AutoScalingGroups": [{"AutoScalingGroupName": s["asg"], "VPCZoneIdentifier": s["subnet"],
            "Instances": [{"InstanceId": f"i-{i:08x}", "LifecycleState": "InService", "HealthStatus": "Healthy",
                "LaunchTemplate": {"LaunchTemplateId": s["spec"]["launch_template"], "Version": str(s["spec"]["launch_template_version"])}}]}]}
    def describe_instances(self, InstanceIds):
        identity = InstanceIds[0]; s = self.slot(identity); spec = s["spec"]; i = int(identity[-1])
        value = {"InstanceId": identity, "State": {"Name": "running"}, "LaunchTime": datetime.fromtimestamp(self.stamp-10, timezone.utc),
            "VpcId": s["vpc"], "SubnetId": s["subnet"], "Placement": {"AvailabilityZone": s["az"]},
            "ImageId": spec["ami"], "InstanceType": spec["instance_type"], "IamInstanceProfile": {"Arn": spec["instance_profile"]},
            "MetadataOptions": {"HttpTokens": "required"}, "Tags": [{"Key": k, "Value": v} for k,v in spec["tags"].items()],
            "SecurityGroups": [{"GroupId": group} for group in spec["security_groups"]], "NetworkInterfaces": [{"NetworkInterfaceId": f"eni-{i:08x}"}]}
        if self.foreign in ("VpcId", "SubnetId", "ImageId", "InstanceType"): value[self.foreign] = "foreign"
        if self.foreign == "az": value["Placement"]["AvailabilityZone"] = "foreign"
        return {"Reservations": [{"Instances": [value]}]}
    def get_instance_profile(self, InstanceProfileName):
        spec = self.slots[0]["spec"]
        return {"InstanceProfile": {"Arn": spec["instance_profile"], "Roles": [{"Arn": spec["role"]}]}}
    def describe_network_interfaces(self, NetworkInterfaceIds):
        identity = NetworkInterfaceIds[0]; s = self.slot(identity); i = int(identity[-1])
        return {"NetworkInterfaces": [{"NetworkInterfaceId": identity, "VpcId": s["vpc"], "SubnetId": s["subnet"],
            "AvailabilityZone": s["az"], "Attachment": {"InstanceId": f"i-{i:08x}", "DeleteOnTermination": True}}]}
    def describe_launch_template_versions(self, LaunchTemplateId, Versions):
        spec = self.slot(LaunchTemplateId)["spec"]
        return {"LaunchTemplateVersions": [{"VersionNumber": spec["launch_template_version"], "LaunchTemplateData": {
            "ImageId": spec["ami"], "InstanceType": "t3.micro", "UserData": base64.b64encode(self.data).decode(),
            "IamInstanceProfile": {"Name": spec["instance_profile"].rsplit("/",1)[1]}, "MetadataOptions": {"HttpTokens": "required"},
            "NetworkInterfaces": [{"AssociatePublicIpAddress": True, "DeleteOnTermination": True, "Groups": spec["security_groups"]}]}}]}
    def describe_instance_attribute(self, InstanceId, Attribute):
        if Attribute == "userData": return {"InstanceId": InstanceId, "UserData": {"Value": base64.b64encode(self.data).decode()}}
        return {"InstanceId": InstanceId, "SourceDestCheck": {"Value": self.sdc[int(InstanceId[-1])-1]}}
    def describe_addresses(self, AllocationIds):
        s = self.slot(AllocationIds[0]); i = int(AllocationIds[0][-1])-1
        return {"Addresses": [{"AllocationId": s["eip"], "Tags": [{"Key":"Environment","Value":s["environment"]}], "NetworkInterfaceId": self.eip[i]}]}
    def describe_route_tables(self, RouteTableIds):
        s = self.slot(RouteTableIds[0]); i = int(RouteTableIds[0][-1])-1
        return {"RouteTables": [{"RouteTableId": s["route_table"], "VpcId": s["vpc"], "Routes": [] if self.route[i] is None else [
            {"DestinationCidrBlock":"0.0.0.0/0","NetworkInterfaceId":self.route[i],"State":self.route_state}]}]}
    def get_console_output(self, InstanceId, Latest):
        assert Latest is True
        raw = f"E13_NAT_BOOTSTRAP_V1 {InstanceId} {self.stamp} CONFIGURED\n"
        if self.console == "missing": raw = "EC2 is healthy\n"
        if self.console == "foreign": raw = raw.replace(InstanceId, "i-ffffffff")
        if self.console == "failed": raw += "E13_NAT_BOOTSTRAP_FAILED\n"
        if self.console == "duplicate": raw += raw
        if self.console == "encoded": raw = base64.b64encode(raw.encode()).decode()
        if self.console == "corrupt": raw = "\ufffd" + raw
        stamp = self.stamp-100 if self.console == "stale" else self.stamp
        return {"InstanceId":InstanceId,"Output":raw,"Timestamp":datetime.fromtimestamp(stamp,timezone.utc)}
    def associate_address(self, **kw):
        self.calls.append(("assign_eip", kw)); self.eip[int(kw["AllocationId"][-1])-1] = kw["NetworkInterfaceId"]
    def create_route(self, **kw):
        self.calls.append(("change_rt", kw)); self.route[int(kw["RouteTableId"][-1])-1] = kw["NetworkInterfaceId"]
    replace_route = create_route
    def modify_instance_attribute(self, **kw):
        self.calls.append(("disable_sdc",kw)); self.sdc[int(kw["InstanceId"][-1])-1] = kw["SourceDestCheck"]["Value"]
    def state(self): return Resolver(self.config["environment"], self.slots).observe(self,self,self,"disable_sdc",int(time.time()),self.slots[0]["asg"])
    def ready(self): self.eip[0] = "eni-00000001"; self.route[0] = "eni-00000001"; self.sdc[0] = False


class Events(unittest.TestCase):
    def test_missing_and_corrupt_event_identity_rejects(self):
        _, _, config, event = fixture()
        self.assertEqual(n.launch_event(event, config), (config["nat_slots"][0]["asg"], "i-00000001"))
        for key in ("id", "account", "region", "source", "detail-type", "detail", "time"):
            for value in (None, {}, "foreign"):
                wrong = copy.deepcopy(event); wrong[key] = value
                with self.subTest(key=key,value=value), self.assertRaises((ValueError,TypeError)): n.launch_event(wrong,config)
    def test_wrong_asg_instance_and_environment_rejects(self):
        _, _, config, event = fixture()
        for field,value in (("AutoScalingGroupName","foreign"),("EC2InstanceId","i-bad"),("EC2InstanceId",None)):
            wrong = copy.deepcopy(event); wrong["detail"][field] = value
            with self.assertRaises(ValueError): n.launch_event(wrong,config)
        with self.assertRaises(ValueError): n.launch_event(event,fixture("prod")[2])
    def test_stale_future_and_timezone_free_events_are_rejected(self):
        _, _, config, event = fixture()
        for stamp in ("2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "2026-10-11T00:00:00", "invalid"):
            event["time"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError): n.launch_event(event, config)
    def test_same_event_has_stable_distinct_handler_operations(self):
        with patch.dict(sys.modules):
            runtime = bootstrap(); config = fixture()[2]; event = fixture()[3]
            operations = []
            for action in ("assign_eip","change_rt","disable_sdc"):
                config["binding"] = "nat-recovery/nat-dev/"+action
                operation = runtime._operation_id(event, config, True)
                self.assertEqual(operation,runtime._operation_id(copy.deepcopy(event),config,True));operations.append(operation)
            self.assertEqual(len(set(operations)),3)


class Readiness(unittest.TestCase):
    def setUp(self): self.aws = AWS(); self.aws.ready()
    def test_positive_bootstrap_is_not_forwarded_egress_proof(self):
        evidence=n.assess(self.aws,self.aws.state(),int(time.time()))
        self.assertEqual(evidence["bootstrap"],"CONFIGURED_AT_LAUNCH")
        self.assertEqual(evidence["private_subnet_egress"],"UNVERIFIED_LIVE_PROOF_REQUIRED")
        self.assertNotIn("Output",json.dumps(evidence))
    def test_ec2_health_without_bootstrap_is_rejected(self):
        for value in ("missing","failed","foreign","duplicate","stale","encoded","corrupt"):
            self.aws.console=value
            with self.subTest(value=value),self.assertRaises(ValueError):n.assess(self.aws,self.aws.state(),int(time.time()))
    def test_route_eip_source_destination_prerequisites(self):
        for field,value in (("association_eni",None),("default_route_eni",None),("source_dest_check",True)):
            state=self.aws.state();state["observed"][field]=value
            with self.assertRaises(ValueError):n.assess(self.aws,state,int(time.time()))
        state=self.aws.state();state["route_exists"]=False
        with self.assertRaises(ValueError):n.assess(self.aws,state,int(time.time()))
    def test_blackhole_is_not_ready(self):
        self.aws.route_state="blackhole"
        with self.assertRaises(ValueError):n.assess(self.aws,self.aws.state(),int(time.time()))
    def test_bounded_missing_evidence_never_mutates(self):
        self.aws.console="missing"; sleeps=[]; reads=[]
        def resolve():reads.append(1);return self.aws.state()
        with self.assertRaisesRegex(ValueError,"READINESS_UNVERIFIED"):
            n.verify(self.aws,resolve,"i-00000001",pause=sleeps.append)
        self.assertEqual(len(reads),12);self.assertEqual(sleeps,[10]*11);self.assertEqual(self.aws.calls,[])
    def test_delayed_prerequisites_can_complete_bounded_verification(self):
        self.aws.eip[0]=None;sleeps=[]
        def pause(seconds):sleeps.append(seconds);self.aws.eip[0]="eni-00000001"
        self.assertEqual(n.verify(self.aws,self.aws.state,"i-00000001",pause=pause)["network_prerequisites"],"VERIFIED")
        self.assertEqual(sleeps,[10]);self.assertEqual(self.aws.calls,[])
    def test_late_observation_cannot_become_success(self):
        clock=[1000]
        def resolve():
            clock[0]=1121
            return self.aws.state()
        sleeps=[]
        with self.assertRaisesRegex(ValueError,"READINESS_UNVERIFIED"):
            n.verify(self.aws,resolve,"i-00000001",now=lambda:clock[0],pause=sleeps.append)
        self.assertEqual(sleeps,[])
    def test_replaced_instance_rejects_event(self):
        with self.assertRaises(ValueError):n.verify(self.aws,self.aws.state,"i-ffffffff",pause=lambda _:None)
    def test_wrong_vpc_subnet_az_and_launch_reject_before_mutation(self):
        for field in ("VpcId","SubnetId","az","ImageId","InstanceType"):
            self.aws.foreign=field
            with self.subTest(field=field),self.assertRaises(ValueError):self.aws.state()
        self.assertEqual(self.aws.calls,[])


class Runtime(unittest.TestCase):
    def test_real_three_handler_replacement_and_retry_no_resend(self):
        for env in ("dev","prod"):
            with self.subTest(env=env),patch.dict(sys.modules):
                runtime=bootstrap();aws=AWS(env);store=S3();clients={"ec2":aws,"autoscaling":aws,"iam":aws,"s3":store}
                for action in ("assign_eip","change_rt","disable_sdc"):
                    aws.config["binding"]="nat-recovery/nat-"+env+"/"+action
                    operation=runtime._operation_id(aws.event,aws.config,True)
                    self.assertEqual(runtime._nat(clients,aws.config,operation,aws.event)["status"],"SUCCESS")
                    self.assertEqual(runtime._nat(clients,aws.config,operation,aws.event)["status"],"SUCCESS")
                self.assertEqual([kind for kind,_ in aws.calls],["assign_eip","change_rt","disable_sdc"])
                readiness=[json.loads(raw) for key,raw in store.values.items() if "/readiness/" in key]
                self.assertTrue(readiness);self.assertEqual(readiness[0]["private_subnet_egress"],"UNVERIFIED_LIVE_PROOF_REQUIRED")
    def test_approved_new_ami_version_recovers_with_fixed_configuration(self):
        with patch.dict(sys.modules):
            runtime=bootstrap();aws=AWS();store=S3()
            aws.slots[0]["spec"].update(ami="ami-abcdef12",launch_template_version=4)
            for action in ("assign_eip","change_rt","disable_sdc"):
                aws.config["binding"]="nat-recovery/nat-dev/"+action
                operation=runtime._operation_id(aws.event,aws.config,True)
                self.assertEqual(runtime._nat({"ec2":aws,"autoscaling":aws,"iam":aws,"s3":store},aws.config,operation,aws.event)["status"],"SUCCESS")
            self.assertEqual(len(aws.calls),3)
    def test_failed_controller_becomes_async_failure(self):
        from scripts.recovery.nat import Nat as Controller
        for status in ("FAILURE","UNCERTAIN"):
            with patch.dict(sys.modules),patch.object(Controller,"run",return_value={"status":status}):
                runtime=bootstrap();aws=AWS();aws.config["binding"]="nat-recovery/nat-dev/assign_eip"
                with self.assertRaises(ValueError):runtime._nat({"ec2":aws,"autoscaling":aws,"iam":aws,"s3":S3()},aws.config,UUID,aws.event)
                self.assertEqual(aws.calls,[])
    def test_unverified_forwarding_fails_with_fixed_retained_diagnostic(self):
        with patch.dict(sys.modules),patch.object(n,"verify",side_effect=ValueError("sensitive SDK text")):
            runtime=bootstrap();aws=AWS();aws.ready();store=S3();aws.config["binding"]="nat-recovery/nat-dev/disable_sdc"
            with self.assertRaisesRegex(ValueError,"E13_NAT_READINESS_UNVERIFIED"):
                runtime._nat({"ec2":aws,"autoscaling":aws,"iam":aws,"s3":store},aws.config,UUID,aws.event)
            failures=[json.loads(raw) for key,raw in store.values.items() if "/readiness-failures/" in key]
            self.assertEqual(failures[0]["bootstrap_and_network"],"UNVERIFIED")
            self.assertNotIn("sensitive",str(store.values))
    def test_stale_launch_event_cannot_mutate_current_replacement(self):
        with patch.dict(sys.modules):
            runtime=bootstrap();aws=AWS();aws.config["binding"]="nat-recovery/nat-dev/assign_eip"
            aws.event["detail"]["EC2InstanceId"]="i-ffffffff"
            with self.assertRaises(ValueError):runtime._nat({"ec2":aws,"autoscaling":aws,"iam":aws,"s3":S3()},aws.config,UUID,aws.event)
            self.assertEqual(aws.calls,[])
    def test_handler_does_not_leak_exception_details(self):
        with patch.dict(sys.modules):
            runtime=bootstrap()
            with patch.object(runtime,"invoke",side_effect=ValueError("credential-value")):
                with self.assertRaisesRegex(RuntimeError,"^E1_WP4D_CONTROL_FAILED$") as error:runtime.handler({},None)
                self.assertTrue(error.exception.__suppress_context__)


class Administrator(unittest.TestCase):
    def setUp(self):
        self.old={k:v for k,v in fixture()[0][0].items() if k not in ("account","region")}
        self.candidate=copy.deepcopy(self.old);self.candidate["spec"].update(ami="ami-abcdef12",launch_template_version=4)
        self.value={"old":self.old,"candidate":self.candidate,"approval":{"environment":"dev","asg":self.old["asg"],
            "old_sha256":n.checksum(self.old),"candidate_sha256":n.checksum(self.candidate),"source_commit":"b"*40,
            "maintenance":"ADMIN_APPROVED_SINGLE_AZ_OUTAGE"},"readback":"EXACT_LAUNCH_VERSIONS_AND_NETWORK_VERIFIED"}
        value=self.value
        class Channel(n.ReplacementAdmin):
            def observe(self,environment,asg):return copy.deepcopy(value)
        self.channel=Channel()
    def test_exact_approved_replacement(self):
        result=n.replacement(self.channel,"dev",self.old["asg"])
        self.assertEqual(result["candidate"]["spec"]["ami"],"ami-abcdef12")
    def test_arbitrary_caller_and_wrong_environment_denied(self):
        for channel,env,asg in ((self.value,"dev",self.old["asg"]),(self.channel,"prod",self.old["asg"]),(self.channel,"dev","foreign")):
            with self.assertRaises(ValueError):n.replacement(channel,env,asg)
    def test_every_approval_field_is_required(self):
        for key in list(self.value["approval"]):
            old=self.value["approval"].pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])
            self.value["approval"][key]=old
        self.value["readback"]="UNVERIFIED"
        with self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])
    def test_version_and_ami_are_exact_not_floating(self):
        for key,value in (("launch_template_version","$Latest"),("launch_template_version",True),("launch_template_version",3),
                          ("launch_template_version",4.5),("ami","latest")):
            old=self.candidate["spec"][key];self.candidate["spec"][key]=value
            self.value["approval"]["candidate_sha256"]=n.checksum(self.candidate)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])
            self.candidate["spec"][key]=old
    def test_network_and_immutable_launch_controls_cannot_change(self):
        for key in ("vpc","subnet","az","asg","eip","route_table"):
            old=self.candidate[key];self.candidate[key]="foreign"
            self.value["approval"]["candidate_sha256"]=n.checksum(self.candidate)
            with self.subTest(key=key),self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])
            self.candidate[key]=old
        for key in set(self.candidate["spec"])-{"ami","launch_template_version"}:
            old=self.candidate["spec"][key];self.candidate["spec"][key]="foreign"
            self.value["approval"]["candidate_sha256"]=n.checksum(self.candidate)
            with self.subTest(key=key),self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])
            self.candidate["spec"][key]=old
    def test_approved_metadata_cannot_enroll_foreign_profile_or_role(self):
        self.old["spec"]["instance_profile"]="arn:aws:iam::123456789012:instance-profile/demo-prod-nat-instance-profile"
        self.candidate["spec"]["instance_profile"]=self.old["spec"]["instance_profile"]
        self.value["approval"]["old_sha256"]=n.checksum(self.old)
        self.value["approval"]["candidate_sha256"]=n.checksum(self.candidate)
        with self.assertRaises(ValueError): n.replacement(self.channel,"dev",self.old["asg"])
    def test_candidate_cannot_substitute_approval_digest(self):
        self.candidate["spec"]["ami"]="ami-ffffffff"
        with self.assertRaises(ValueError):n.replacement(self.channel,"dev",self.old["asg"])


class Generated(unittest.TestCase):
    def setUp(self):self.tf=model.wiring(DOC)["terraform/infra/security/modules/controller_compute/main.tf.json"]
    def test_runbook_links_resolve_and_live_egress_remains_explicit(self):
        path=ROOT/"terraform/docs/e13-nat-reliability.md"
        text=path.read_text()
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)",text):
            target=target.split("#",1)[0]
            if not target or re.match(r"[a-zA-Z]+:",target):continue
            self.assertTrue((path.parent/target).resolve().exists(),target)
        self.assertIn("UNVERIFIED_LIVE_PROOF_REQUIRED",text)
        self.assertIn("no live port or",text)
    def test_authoritative_generator_matches_checked_in_sources(self):model.validate_repository(ROOT)
    def test_both_failure_stages_have_bounded_retry_and_exact_version(self):
        resources=self.tf["resource"];target=resources["aws_cloudwatch_event_target"]["wp4d_nat"]
        self.assertEqual(target["retry_policy"],{"maximum_event_age_in_seconds":900,"maximum_retry_attempts":3})
        self.assertEqual(target["dead_letter_config"]["arn"],"${aws_sqs_queue.nat_delivery_failed[each.value.environment].arn}")
        invocation=resources["aws_lambda_function_event_invoke_config"]["wp4d_nat"]
        self.assertEqual(invocation["maximum_event_age_in_seconds"],900);self.assertEqual(invocation["maximum_retry_attempts"],1)
        self.assertEqual(invocation["qualifier"],"${aws_lambda_function.wp4d[each.key].version}")
        self.assertIn("nat_execution_failed",invocation["destination_config"]["on_failure"]["destination"])
        self.assertNotIn("aws_lambda_event_source_mapping",resources)
    def test_failed_messages_retained_encrypted_and_no_automatic_consumer(self):
        for queue in self.tf["resource"]["aws_sqs_queue"].values():
            self.assertEqual(queue["message_retention_seconds"],1209600);self.assertTrue(queue["sqs_managed_sse_enabled"])
            self.assertEqual(queue["for_each"],"${local.wp4d_nat_events}");self.assertTrue(queue["lifecycle"]["prevent_destroy"])
        policy_text=self.tf["resource"]["aws_sqs_queue_policy"]["nat_failures"]["policy"]
        self.assertIn('"aws:SourceArn"=aws_cloudwatch_event_rule.wp4d_nat[each.value.environment].arn',policy_text)
        self.assertIn('"aws:SourceAccount"=var.account_id',policy_text);self.assertIn("OnlyAdminDrain",policy_text)
    def test_alerts_cover_backlog_and_failure_to_retain(self):
        alarms=self.tf["resource"]["aws_cloudwatch_metric_alarm"]
        self.assertEqual(alarms["nat_failure_queue"]["dimensions"],{"QueueName":"${each.value.name}"})
        self.assertEqual(alarms["nat_failure_queue"]["treat_missing_data"],"missing")
        self.assertEqual(alarms["nat_async_delivery"]["metric_name"],"DestinationDeliveryFailures")
        self.assertEqual(alarms["nat_event_dlq_delivery"]["metric_name"],"InvocationsFailedToBeSentToDlq")
        self.assertTrue(all("alerts" in alarm["alarm_actions"][0] for alarm in alarms.values()))
    def test_failure_payload_projection_has_no_caller_configuration(self):
        transformer=self.tf["resource"]["aws_cloudwatch_event_target"]["wp4d_nat"]["input_transformer"]
        self.assertEqual(set(transformer["input_paths"]),{"id","account","region","time","asg","instance"})
        self.assertNotIn("userData",str(transformer));self.assertNotIn("credentials",str(transformer))
    def test_failure_destination_permissions_are_environment_specific(self):
        for env in ("dev","prod"):
            for action in ("assign_eip","change_rt","disable_sdc"):
                p=policy("nat-recovery/nat-"+env+"/"+action)
                queue=f"arn:aws:sqs:{REGION}:{ACCOUNT}:e1-wp4-{env}-nat-execution-failed"
                self.assertTrue(permits(p,"sqs:SendMessage",queue))
                for foreign in (queue.replace(env,"prod" if env=="dev" else "dev"),queue.replace("execution","delivery"),queue+"foreign"):
                    self.assertFalse(permits(p,"sqs:SendMessage",foreign))
                for verb in ("sqs:ReceiveMessage","sqs:DeleteMessage","ssm:SendCommand","ec2:RunInstances","ec2:CreateLaunchTemplateVersion","iam:PassRole"):
                    self.assertFalse(permits(p,verb,queue))
    def test_only_disable_sdc_can_read_bounded_console_evidence(self):
        resource=f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-00000001"
        context={"aws:ResourceTag/Environment":"dev","aws:ResourceTag/Role":"nat"}
        for action in ("assign_eip","change_rt","disable_sdc"):
            p=policy("nat-recovery/nat-dev/"+action)
            self.assertEqual(permits(p,"ec2:GetConsoleOutput",resource,context),action=="disable_sdc")
            self.assertFalse(permits(p,"ec2:GetConsoleOutput",resource,{**context,"aws:ResourceTag/Environment":"prod"}))
    def test_original_action_responsibilities_remain_disjoint(self):
        verbs={"assign_eip":{"ec2:AssociateAddress"},"change_rt":{"ec2:CreateRoute","ec2:ReplaceRoute"},"disable_sdc":{"ec2:ModifyInstanceAttribute"}}
        for action,expected in verbs.items():
            statements=policy("nat-recovery/nat-dev/"+action)["Statement"]
            mutations={verb for statement in statements for verb in statement["Action"] if verb.startswith("ec2:") and not verb.startswith(("ec2:Describe","ec2:Get"))}
            self.assertEqual(mutations,expected)
    def test_fixed_userdata_and_numeric_template_ownership(self):
        foundations=wp5.foundations();lt=foundations["resource"]["aws_launch_template"]["nat"]
        self.assertEqual(foundations["locals"]["nat_userdata"],(ROOT/"scripts/nat/user_data.sh").read_text())
        self.assertEqual(lt["image_id"],"${each.value.ami}");self.assertEqual(lt["lifecycle"],{"prevent_destroy":True})
        self.assertNotIn("aws_ami",foundations.get("data",{}))
        for env in ("dev","prod"):
            root=json.loads((ROOT/f"terraform/modules/target/{env}/global/wp5-nat.tf.json").read_text())
            asg=root["resource"]["aws_autoscaling_group"]["wp5_nat"]
            self.assertEqual(asg["launch_template"]["version"],"${tostring(each.value.version)}")
            self.assertNotIn("instance_refresh",asg)
    def test_pinned_packages_include_exact_new_sources(self):
        for binding in wp4d.RESERVED:
            files=wp4d.package_sources(binding)
            self.assertIn("scripts/nat/reliability.py",files)
        for binding in wp5.BINDINGS:
            files=wp5.package_files(ROOT,DOC,binding)
            self.assertEqual(files["scripts/nat/user_data.sh"],(ROOT/"scripts/nat/user_data.sh").read_bytes().replace(b"\r\n",b"\n"))


class ConsoleReadback(unittest.TestCase):
    def test_json_with_one_fixed_lock_release_status_is_supported(self):
        raw=json.dumps(json.dumps({"gate":"exact"}))
        status="Releasing state lock. This may take a few moments..."
        acquire="Acquiring state lock. This may take a few moments..."
        for output in (raw,raw+"\n"+status,status+"\n"+raw,acquire+"\n"+raw,acquire+"\n"+raw+"\n"+status):
            self.assertEqual(console_json(output),{"gate":"exact"})
    def test_warning_extra_json_or_duplicate_status_is_rejected(self):
        raw=json.dumps(json.dumps({"gate":"exact"}))
        status="Releasing state lock. This may take a few moments..."
        for output in ("Warning: unknown\n"+raw,raw+"\n{}",raw+"\n"+status+"\n"+status,"Error: bad"):
            with self.subTest(output=output),self.assertRaises(ValueError):console_json(output)
    def test_unencoded_scalar_and_invalid_nested_json_are_rejected(self):
        for output in ('{}','true','123',json.dumps('invalid')):
            with self.assertRaises(ValueError):console_json(output)
