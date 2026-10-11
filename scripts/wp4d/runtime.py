"""WP4D fixed entrypoint for admin-installed, digest-pinned controller images.

No event may choose a project, environment, AWS resource, role, package or port.
The selected implementation is fixed by the installed Lambda/CodeBuild config.
"""
import json
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager

from installed import load, require


def configuration():
    value = json.loads(os.environ["E1_PROTECTED_CONFIGURATION"])
    require(type(value) is dict and set(value) == {
        "binding", "account", "region", "environment", "bundle",
        "runtime_image", "project", "evidence_bucket", "dev_evidence_bucket",
        "admin_bucket", "repository", "resources", "nat_slots"})
    require(value["environment"] in ("dev", "prod")
            and re.fullmatch(r"[0-9]{12}", value["account"]) is not None
            and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]", value["region"]) is not None)
    require(value["bundle"]["binding"] == value["binding"])
    return value


@contextmanager
def _installed(s3, config):
    directory = tempfile.TemporaryDirectory(prefix="e1-wp4-installed-")
    try:
        package = load(s3, config["bundle"], directory.name)
        require(package["binding"] == config["binding"]
                and package["environment"] == config["environment"])
        for filename in ("runtime.py", "installed.py"):
            bootstrap = Path(__file__).with_name(filename).read_bytes().replace(b"\r\n", b"\n")
            reviewed = (Path(directory.name) / "scripts" / "wp4d" / filename).read_bytes()
            require(hashlib.sha256(bootstrap).digest() == hashlib.sha256(reviewed).digest())
        # Warm Lambda processes must not retain modules pointing at a deleted
        # extraction, or let the image's source tree shadow installed bytes.
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
        sys.path.insert(0, directory.name)
        yield directory
    finally:
        if directory.name in sys.path:
            sys.path.remove(directory.name)
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
        directory.cleanup()


def _operation_id(event, config, scheduled=False):
    if not scheduled:
        return str(uuid.uuid4())
    require(type(event) is dict and event.get("account") == config["account"]
            and event.get("region") == config["region"])
    identity = event.get("id")
    require(type(identity) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", identity))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, config["binding"] + "/" + identity))


def _clients(config):
    import boto3  # separately approved exact-digest runtime image
    from botocore.config import Config
    region = config["region"]
    # AWS SDK retries must not resend an ambiguously acknowledged mutation
    # underneath WP4B/WP4C's durable attempt/UNKNOWN contract.
    return {name: boto3.client(name, region_name=region,
                               config=Config(connect_timeout=3, read_timeout=5,
                                   retries={"total_max_attempts": 1, "mode": "standard"},
                                   **({"signature_version": "s3v4"} if name == "s3" else {})))
            for name in ("s3", "ecs", "elbv2", "events", "ecr", "ec2", "autoscaling", "codebuild", "iam")}


def _fact_config(config):
    binding = config["binding"]
    endpoint = "deploy-dev" if config["environment"] == "dev" else "promote-prod"
    return {k: config[k] for k in ("account", "region", "environment", "admin_bucket",
                                  "evidence_bucket", "dev_evidence_bucket", "repository")} | {"endpoint": endpoint}


def _wakeup(clients, config):
    from scripts.wp4d.adapters import Objects
    project = config["project"]
    build_id = os.environ["CODEBUILD_BUILD_ID"]
    require(type(project) is str and build_id.startswith(project + ":"))
    gateway = Objects(clients["s3"], config["evidence_bucket"],
                      "gateway/" + config["environment"] + "/" +
                      ("normal" if config["binding"].startswith("normal-delivery/") else "emergency") + "/")
    bridge = None
    end = time.monotonic() + 30
    while bridge is None and time.monotonic() < end:
        bridge = gateway.read("builds/" + build_id + ".json")
        if bridge is None:
            time.sleep(1)
    require(bridge is not None)
    value = json.loads(bridge["bytes"])
    require(type(value) is dict and set(value) == {"operation"})
    operation = value["operation"]
    envelope = gateway.read("operations/" + operation + ".json")
    require(envelope is not None)
    intent = json.loads(envelope["bytes"])
    require(type(intent) is dict and set(intent) == {"operation", "binding", "request"}
            and intent["operation"] == operation)
    gateway_binding = ("request-gateway/" + config["binding"].split("/", 1)[1])
    require(intent["binding"] == gateway_binding)
    return operation, intent["request"]


def _authority(clients, config, operation, request, cleanup=None):
    from scripts.environment_mutation import Store, Authority
    return Authority(Store(clients["s3"], config["evidence_bucket"], config["environment"]),
                     config["binding"], operation, request, cleanup=cleanup)


def _guarded(clients, authority):
    from scripts.environment_mutation import Client
    return dict(clients, **{name: Client(clients[name], name, authority)
                           for name in ("ecs", "elbv2", "events")})


def _normal(clients, config):
    from scripts.environment_mutation import execute
    operation, request = _wakeup(clients, config)
    owner = _authority(clients, config, operation, request)
    result = execute(owner, lambda grant: _normal_owned(
        _guarded(clients, grant), config, operation, request, grant))
    return {"operation": operation, "status": result["status"]}


def _normal_owned(clients, config, operation, request, authority):
    from scripts.normal_delivery import authorization as a
    from scripts.normal_delivery import delivery as d
    from scripts.normal_delivery.e3 import Gate
    from scripts.wp4d.adapters import Facts, Objects, History
    from scripts.wp4d.aws_runtime import Delivery, BoundedProcess
    records = Objects(clients["s3"], config["evidence_bucket"], "delivery/")
    facts = Facts(clients["s3"], clients["ecr"], _fact_config(config))
    endpoint = config["binding"].split("/", 1)[1]
    authorizer = a.Authorizer(endpoint, config["account"], config["region"], facts)
    runtime = Delivery(clients["ecs"], clients["elbv2"], clients["events"],
                       records, config["resources"])
    result = d.Delivery(authorizer, runtime, records, Gate(BoundedProcess())).run(
        operation, a.canonical(request))
    if result["status"] == "SUCCESS":
        authority.call(History(clients["s3"], config["evidence_bucket"],
                config["environment"]).publish, result, records)
        if config["environment"] == "dev":
            activation = d.dev_prerequisite(result)
            publication = Objects(clients["s3"], config["evidence_bucket"], "activations/by-release/")
            key = activation["release_id"] + ".json"
            retained = publication.read(key)
            if retained is None:
                publication.create(key, a.canonical(activation))
                retained = publication.read(key)
            require(retained is not None and retained["bytes"] == a.canonical(activation))
    public = {"operation_id": operation, "state": result["status"], "release_id": None, "source_commit": None}
    key = config["environment"] + "/" + operation + "/public.json"
    try:
        records.create(key, a.canonical(public))
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") != "PreconditionFailed":
            raise
    retained = records.read(key)
    require(retained is not None and retained["bytes"] == a.canonical(public))
    return {"operation": operation, "status": result["status"]}


def _application(clients, config, operation, cleanup=False, evidence=None):
    require(config["binding"] == ("cleanup-recovery/cleanup-" if cleanup else
                                 "emergency-recovery/emergency-") + config["environment"])
    from scripts.environment_mutation import execute
    owner = _authority(clients, config, operation, {}, evidence if cleanup else None)
    result = execute(owner, lambda grant: _application_owned(
        _guarded(clients, grant), config, operation, cleanup))
    return {"operation": operation, "status": result["status"]}


def _application_owned(clients, config, operation, cleanup=False):
    from scripts.normal_delivery import authorization as a
    from scripts.recovery.application import Emergency, Cleanup
    from scripts.wp4d.adapters import Facts, RecoveryObjects, History
    from scripts.wp4d.aws_runtime import Application
    records = RecoveryObjects(clients["s3"], config["evidence_bucket"],
                              config["environment"])
    facts = Facts(clients["s3"], clients["ecr"], _fact_config(config))
    membership = a.envelope(facts.membership(config["environment"]),
                            "environment", config["environment"])
    require(membership["colors"] == config["resources"]["colors"])
    runtime = Application(clients["ecs"], clients["elbv2"], clients["events"],
                          records, config["resources"],
                          History(clients["s3"], config["evidence_bucket"], config["environment"]))
    if cleanup:
        result = Cleanup(config["environment"], records, runtime).run(operation, b"{}\n")
    else:
        auth = a.Authorizer(_fact_config(config)["endpoint"], config["account"], config["region"], facts)
        result = Emergency(auth, records, runtime).run(operation, b"{}\n")
    if not cleanup:
        public = {"operation_id": operation, "state": result["status"], "release_id": None, "source_commit": None}
        key = config["environment"] + "/recovery/emergency/" + operation + "/public.json"
        try:
            records.create(key, a.canonical(public))
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") != "PreconditionFailed":
                raise
        retained = records.read(key)
        require(retained is not None and retained["bytes"] == a.canonical(public))
    return {"operation": operation, "status": result["status"]}


def _nat(clients, config, operation, event):
    from scripts.recovery.nat import Nat as Controller
    from scripts.wp4d.adapters import Objects
    from scripts.wp4d.aws_runtime import Nat as Transport
    from scripts.wp4d.nat_resolver import Resolver
    action = config["binding"].rsplit("/", 1)[1]
    from scripts.nat.reliability import launch_event, verify, checksum
    from scripts.normal_delivery import authorization as a
    asg, instance = launch_event(event, config)
    records = Objects(clients["s3"], config["evidence_bucket"], "recovery/")
    runtime = Transport(clients["ec2"], clients["autoscaling"], clients["iam"], records,
                        Resolver(config["environment"], config["nat_slots"]), action, operation, asg, instance)
    result = Controller(config["environment"], action, records, runtime).run(operation, b"{}\n")
    # A normal return would silently discard FAILURE/UNCERTAIN async events.
    require(result["status"] == "SUCCESS")
    if action == "disable_sdc":
        try:
            readiness = verify(clients["ec2"], lambda: runtime.context(action, runtime.now() + 30), instance)
        except Exception:
            # Persist only a fixed diagnostic code, never console output or SDK errors.
            failure = {"schema": "E13_NAT_READINESS_V1", "event_id": event["id"],
                       "operation": operation, "instance": instance, "observed_at": runtime.now(),
                       "bootstrap_and_network": "UNVERIFIED", "private_subnet_egress": "UNVERIFIED_LIVE_PROOF_REQUIRED"}
            raw = a.canonical(failure)
            key = config["environment"] + "/recovery/" + action + "/" + operation + "/readiness-failures/" + checksum(failure)
            retained = records.read(key)
            if retained is None:
                records.create(key, raw)
            else:
                require(retained["bytes"] == raw)
            raise ValueError("E13_NAT_READINESS_UNVERIFIED") from None
        raw = a.canonical(readiness)
        key = config["environment"] + "/recovery/" + action + "/" + operation + "/readiness/" + checksum(readiness)
        retained = records.read(key)
        if retained is None:
            records.create(key, raw)
        else:
            require(retained["bytes"] == raw)
    return {"operation": operation, "status": "SUCCESS", "forwarding": "LIVE_PROOF_REQUIRED"}


def invoke(event):
    config = configuration()
    clients = _clients(config)
    with _installed(clients["s3"], config):
        binding = config["binding"]
        if binding.startswith("request-gateway/"):
            from scripts.wp4d.adapters import Objects
            from scripts.wp4d.gateway import start
            kind = "emergency" if "emergency-" in binding else "normal"
            operations = Objects(clients["s3"], config["evidence_bucket"],
                                 "gateway/" + config["environment"] + "/" + kind + "/")
            return start(kind, event, config, operations, clients["codebuild"])
        if binding.startswith("normal-delivery/"):
            require(event is None)
            return _normal(clients, config)
        if binding.startswith("emergency-recovery/"):
            require(event is None)
            operation, request = _wakeup(clients, config)
            require(request == {})
            return _application(clients, config, operation)
        if binding.startswith("cleanup-recovery/"):
            require(event.get("source") == "aws.events" and
                    event.get("detail-type") == "Scheduled Event")
            require(event.get("resources") == ["arn:aws:events:" + config["region"] + ":" +
                    config["account"] + ":rule/" + config["resources"]["cleanup"]["rule"]])
            return _application(clients, config, _operation_id(event, config, True), True,
                                event.get("e2"))
        if binding.startswith("nat-recovery/"):
            require(event.get("source") == "aws.autoscaling")
            return _nat(clients, config, _operation_id(event, config, True), event)
        raise ValueError("E1_WP4D_BINDING_REJECTED")


def handler(event, context):
    try:
        return invoke(event)
    except Exception:
        raise RuntimeError("E1_WP4D_CONTROL_FAILED") from None


if __name__ == "__main__":
    try:
        invoke(None)
    except Exception:
        raise SystemExit("E1_WP4D_CONTROL_FAILED") from None
