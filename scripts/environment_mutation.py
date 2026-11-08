"""E2 protected, non-expiring environment mutation ownership.

One versioned S3 object per conflict domain, initialized by the administrator.
Workers never initialize, delete, expire or take over ACTIVE ownership. Journal
algorithms remain E1's; this adapter surrounds their installed execution boundary.
"""
import copy
import hashlib
import json
import re
import threading
import time
import uuid


class CoordinationError(Exception):
    pass


def require(ok):
    if not ok:
        raise CoordinationError("E2_COORDINATION_UNPROVED")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def identity(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value))
    return value


def domain(binding, layer=None):
    require(type(binding) is str)
    if binding in ("normal-delivery/deploy-dev", "normal-delivery/promote-prod",
                   "emergency-recovery/emergency-dev", "emergency-recovery/emergency-prod",
                   "cleanup-recovery/cleanup-dev", "cleanup-recovery/cleanup-prod"):
        require(layer is None)
        return "application"
    require(binding in tuple("environment-lifecycle/" + name for name in (
        "infra-dev", "infra-prod", "infra-high-risk-dev", "infra-high-risk-prod")))
    require(layer in ("shared", "secrets", "global", "data", "platform", "apps", "edge"))
    # Shared is SNS/alarms only; secrets is a metadata-only consumer root.
    # All other layers share runtime/network/data dependencies.
    return layer if layer in ("shared", "secrets") else "application"


def initial(environment, selected):
    require(environment in ("dev", "prod") and selected in ("application", "shared", "secrets"))
    return dict(schema="E2_MUTATION_V1", environment=environment, domain=selected,
                generation=0, state="RELEASED", owner=None, operation=None,
                binding=None, request_sha256=None, schedule=None)


def validate(value, environment, selected):
    require(type(value) is dict and set(value) == set(initial(environment, selected)))
    require(value["schema"] == "E2_MUTATION_V1" and value["environment"] == environment
            and value["domain"] == selected and type(value["generation"]) is int
            and 0 <= value["generation"] < 2**63 and value["state"] in ("ACTIVE", "RELEASED"))
    if value["generation"] == 0:
        require(value == initial(environment, selected))
    else:
        identity(value["owner"])
        identity(value["operation"])
        require(domain(value["binding"], selected if selected != "application" else
                       ("apps" if value["binding"].startswith("environment-lifecycle/") else None)) == selected)
        require(value["binding"].endswith("-" + environment))
        require(type(value["request_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["request_sha256"]))
    schedule = value["schedule"]
    if schedule is not None:
        require(selected == "application" and type(schedule) is dict and
                set(schedule) == {"environment", "generation", "binding", "operation"})
        require(schedule["environment"] == environment and type(schedule["generation"]) is int
                and 0 < schedule["generation"] <= value["generation"])
        identity(schedule["operation"])
        require(domain(schedule["binding"]) == "application" and
                schedule["binding"].endswith("-" + environment) and
                schedule["binding"].startswith(("normal-delivery/", "emergency-recovery/")))
    return value


class Store:
    """Exact environment/domain CAS; no lists, deletes, renewals or SDK retries."""
    def __init__(self, s3, bucket, environment, selected="application"):
        initial(environment, selected)
        require(type(bucket) is str and bool(bucket))
        self.s3, self.bucket, self.environment, self.selected = s3, bucket, environment, selected
        self.key = "arbitration/" + environment + "/" + selected + ".json"

    def read(self):
        result = self.s3.get_object(Bucket=self.bucket, Key=self.key)
        raw = result["Body"].read(16385)
        require(type(raw) is bytes and 0 < len(raw) <= 16384)
        value = json.loads(raw)
        require(canonical(value) == raw)
        validate(value, self.environment, self.selected)
        require(type(result.get("ETag")) is str and bool(result["ETag"])
                and type(result.get("VersionId")) is str
                and result["VersionId"].lower() not in ("", "null", "latest"))
        return value, result["ETag"]

    def exchange(self, value, etag):
        validate(value, self.environment, self.selected)
        raw = canonical(value)
        try:
            self.s3.put_object(Bucket=self.bucket, Key=self.key, Body=raw,
                ContentType="application/json", **({"IfNoneMatch": "*"} if etag is None else {"IfMatch": etag}))
        except Exception:
            pass  # ACK/error is not proof; a single exact read settles this CAS.
        observed, current_etag = self.read()
        require(observed == value)
        return current_etag

    def initialize(self):
        """Administrator-only installation step, never called by a worker."""
        return self.exchange(initial(self.environment, self.selected), None)


class Authority:
    def __init__(self, store, binding, operation, request, layer=None, cleanup=None):
        require(type(store) is Store and domain(binding, layer) == store.selected
                and binding.endswith("-" + store.environment))
        identity(operation)
        self.store, self.binding, self.operation = store, binding, operation
        self.request_sha256 = hashlib.sha256(canonical(request)).hexdigest()
        self.owner = str(uuid.uuid4())  # invocation identity, never a caller UUID
        self.cleanup = copy.deepcopy(cleanup)
        self.value = None
        self.touched = False
        self.closed = False
        self.mutex = threading.Lock()

    def terminal_key(self):
        return ("arbitration/" + self.store.environment + "/terminals/" +
                self.binding + "/" + self.operation + ".json")

    def retained(self):
        try:
            response = self.store.s3.get_object(Bucket=self.store.bucket, Key=self.terminal_key())
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        raw = response["Body"].read(4097)
        value = json.loads(raw)
        require(len(raw) <= 4096 and canonical(value) == raw and type(value) is dict
                and set(value) == {"environment", "domain", "binding", "operation",
                                  "request_sha256", "generation", "status", "sha256"})
        require(value["sha256"] == hashlib.sha256(canonical(
            {key:item for key,item in value.items() if key != "sha256"})).hexdigest())
        require(value["environment"] == self.store.environment and value["domain"] == self.store.selected
                and value["binding"] == self.binding and value["operation"] == self.operation
                and value["request_sha256"] == self.request_sha256
                and type(value["generation"]) is int and value["generation"] > 0
                and value["status"] in ("SUCCESS", "FAILURE")
                and type(response.get("VersionId")) is str
                and response["VersionId"].lower() not in ("", "null", "latest"))
        return value

    def acquire(self):
        with self.mutex:
            if self.value is not None:
                self._check()
                return self
            require(not self.closed)
            prior, etag = self.store.read()
            require(prior["state"] == "RELEASED")
            # A RELEASED matching operation must already have its terminal.
            require(not (prior["binding"] == self.binding and prior["operation"] == self.operation))
            if self.binding.startswith("cleanup-recovery/"):
                require(self.cleanup is not None and
                        canonical(prior["schedule"]) == canonical(self.cleanup))
            else:
                require(self.cleanup is None)
            require(prior["generation"] < 2**63 - 1)
            value = dict(prior, generation=prior["generation"] + 1, state="ACTIVE",
                         binding=self.binding, operation=self.operation,
                         request_sha256=self.request_sha256, owner=self.owner)
            if not self.binding.startswith("cleanup-recovery/"):
                value["schedule"] = None
            self.store.exchange(value, etag)
            self.value = value
        return self

    def _check(self):
        require(self.value is not None and not self.closed)
        value, etag = self.store.read()
        require(value == self.value and value["state"] == "ACTIVE")
        return etag

    def call(self, function, *args, **kwargs):
        # Local lock only prevents release while THIS invocation's synchronous
        # call runs. Independent invocation arbitration is the durable S3 CAS.
        with self.mutex:
            self._check()
            self.touched = True
            return function(*args, **kwargs)

    def schedule(self):
        with self.mutex:
            etag = self._check()
            require(self.binding.startswith(("normal-delivery/", "emergency-recovery/")))
            proof = {key: self.value[key] for key in ("environment", "generation", "binding", "operation")}
            value = dict(self.value, schedule=proof)
            if value != self.value:
                self.store.exchange(value, etag)
                self.value = value
            return copy.deepcopy(proof)

    def finish(self, successful=False, status=None):
        with self.mutex:
            # Keep ownership after any possibly applied failed/uncertain call.
            # No lease, timeout, SIGTERM handler or finally can release that hold.
            if status in ("UNCERTAIN", "UNKNOWN") or (self.touched and not successful):
                return
            etag = self._check()
            if status in ("SUCCESS", "FAILURE"):
                terminal = {key: self.value[key] for key in
                            ("environment", "domain", "binding", "operation", "request_sha256", "generation")}
                terminal["status"] = status
                terminal["sha256"] = hashlib.sha256(canonical(terminal)).hexdigest()
                try:
                    self.store.s3.put_object(Bucket=self.store.bucket, Key=self.terminal_key(),
                        Body=canonical(terminal), ContentType="application/json", IfNoneMatch="*")
                except Exception:
                    pass
                require(self.retained() == terminal)
            value = dict(self.value, state="RELEASED")
            if self.binding.startswith("cleanup-recovery/") and successful:
                value["schedule"] = None
            self.store.exchange(value, etag)
            self.closed = True


MUTATIONS = {
    "ecs": frozenset(("register_task_definition", "update_service")),
    "elbv2": frozenset(("modify_listener", "modify_rule")),
    "events": frozenset(("put_rule", "put_targets", "remove_targets", "delete_rule")),
}


def cleanup_transformer(proof):
    # Keep the native event identity, while attaching the installed owner's
    # exact schedule generation. A queued event cannot acquire a newer schedule.
    template = '{"source":"aws.events","detail-type":"Scheduled Event","id":<id>,' \
               '"account":<account>,"region":<region>,"resources":<resources>,"e2":' \
               + canonical(proof).decode("ascii").strip() + "}"
    return {"InputPathsMap": {"id": "$.id", "account": "$.account", "region": "$.region",
                             "resources": "$.resources"}, "InputTemplate": template}


def scheduled_target(events, target):
    if not isinstance(events, Client):
        return target  # E1's provider-free domain-port fixtures
    proof = events.authority.value["schedule"]
    require(proof is not None)
    return dict(target, InputTransformer=cleanup_transformer(proof))


class Client:
    """Wrap only existing admitted mutation APIs; observations stay read-only."""
    def __init__(self, client, service, authority, deadline=None, clock=time.time):
        require(service in MUTATIONS and type(authority) is Authority
                and authority.store.selected == "application")
        self.client, self.service, self.authority = client, service, authority
        self.deadline, self.clock = deadline, clock

    def __getattr__(self, name):
        function = getattr(self.client, name)
        if name not in MUTATIONS[self.service]:
            require(name.startswith(("describe_", "list_", "get_")))
            return function
        def invoke(*args, **kwargs):
            if self.service == "events" and name in ("put_rule", "put_targets"):
                proof = self.authority.schedule()
                if name == "put_targets":
                    kwargs = copy.deepcopy(kwargs)
                    require(type(kwargs.get("Targets")) is list and len(kwargs["Targets"]) == 1
                            and kwargs["Targets"][0].get("Id") == "scale-down"
                            and not set(kwargs["Targets"][0]) - {"Id", "Arn"})
                    kwargs["Targets"][0]["InputTransformer"] = cleanup_transformer(proof)
            def send():
                # Validate the immutable E1 deadline after the ownership read.
                require(type(self.deadline) is int and self.clock() < self.deadline)
                return function(*args, **kwargs)
            return self.authority.call(send)
        return invoke


def mutation_deadline(deadline, *clients):
    for client in clients:
        if isinstance(client, Client):
            require(type(deadline) is int)
            client.deadline = deadline


def execute(authority, body, state_key="status"):
    """Bounded one-attempt admission, then E1 execution with truthful outcomes."""
    try:
        terminal = authority.retained()
        if terminal is not None:
            return {state_key: terminal["status"], "operation_id": authority.operation}
        authority.acquire()
    except Exception:
        return {state_key: "UNCERTAIN" if state_key == "status" else "UNKNOWN",
                "reason": "E2 mutation ownership unavailable"}
    try:
        result = body(authority)
        require(type(result) is dict and result.get(state_key) in
                ("SUCCESS", "FAILURE", "UNCERTAIN", "UNKNOWN", "PLANNED"))
        authority.finish(result[state_key] == "SUCCESS", result[state_key])
        return result
    except BaseException:
        # No termination handler/finally can infer safe release. Even an
        # unexpected pre-call exception leaves the admitted invocation ACTIVE.
        raise
