"""Admin-only output publication and exact-version installation orchestration.

Ports are trusted dependencies supplied by separately authenticated bootstrap,
never request parameters. No AWS adapter/credentials/CLI is implemented here.
An implementation of these ports must enforce admin authentication and atomic
create-only publication. A JSON owner field is NOT authentication.
"""
from abc import ABC, abstractmethod
import copy
import re

import bundles
import ownership
from contracts import load_json


def decode_record(raw):
    require(isinstance(raw, bytes) and len(raw) <= 1048576, "record bytes/size")
    return load_json(raw.decode("utf-8"))


class AdminChannel(ABC):
    """External admin-authenticated channel; ordinary consumers get read-only access.

    read_output must return the dedicated protected_output_candidates output,
    NOT state. read_publication must fail on absent/ambiguous provenance.
    """
    @abstractmethod
    def read_output(self):
        raise NotImplementedError

    @abstractmethod
    def create_publication(self, key, value):
        raise NotImplementedError

    @abstractmethod
    def read_publication(self, key):
        raise NotImplementedError


class AdminBundleStorage(ABC):
    """Externally authenticated admin-only, fixed protected bucket adapter.

    Conditional put returns exactly bucket/key/version_id. Exact get returns
    those same identity fields plus bytes. No latest/copy/list fallback.
    """
    @abstractmethod
    def put_if_absent(self, bucket, key, raw, checksum_sha256):
        raise NotImplementedError

    @abstractmethod
    def get_exact(self, bucket, key, version_id):
        raise NotImplementedError


def require(ok, message):
    if not ok:
        raise ValueError("WP2D_PUBLICATION_REJECTED: " + message)


def context(account, region):
    require(isinstance(account, str) and re.fullmatch(r"[0-9]{12}", account), "account")
    require(isinstance(region, str) and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region), "region")


def validate_records(doc, records, account, region):
    c = ownership.validate(doc)
    context(account, region)
    require(isinstance(records, dict), "record map; duplicate keys must be rejected by JSON loader")
    expected = set(c["resources"]) | {"recovery/" + k for k in c["recovery"]}
    require(set(records) == expected, "missing/unknown output records")
    for key, record in records.items():
        require(isinstance(record, dict) and set(record) == {"schema", "owner", "scope", "class", "logical_id", "declaration", "authority_digest", "available", "value", "publication"}, "closed record fields")
        recovery = key.startswith("recovery/")
        item = c["recovery"][key[len("recovery/"):]] if recovery else c["resources"][key]
        fixed = {"schema": c["record_schema"], "owner": ownership.OWNER, "scope": item["scope"],
            "class": "recovery" if recovery else item["kind"], "logical_id": key,
            "declaration": "reservation/" + key if recovery else item["declaration"],
            "authority_digest": ownership.authority_digest(c), "available": not recovery,
            "publication": "ADMIN_OUTPUT_CANDIDATE_NOT_AUTHENTICATED"}
        require(all(type(record[k]) is type(v) and record[k] == v for k, v in fixed.items()), "record identity/scope/availability")
        value = record["value"]
        if recovery:
            require(value is None, "unavailable recovery value")
            continue
        require(isinstance(value, str), "resource value type")
        name = re.escape(item["name"])
        prefix = "arn:aws:"
        pattern = {
            "role": prefix + "iam::" + account + ":role/" + name,
            "profile": prefix + "iam::" + account + ":instance-profile/" + name,
            "key": prefix + "kms:" + region + ":" + account + r":key/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
            "secret": prefix + "secretsmanager:" + region + ":" + account + ":secret:" + name + r"-[A-Za-z0-9]{6}",
            "repository": prefix + "ecr:" + region + ":" + account + ":repository/" + name,
            "bucket": prefix + "s3:::" + name + account,
            "oidc": prefix + "iam::" + account + ":oidc-provider/" + name,
        }[item["kind"]]
        require(re.fullmatch(pattern, value) is not None, "exact supported resource identity")
    return copy.deepcopy(records)


def output_key(doc, account, region):
    return "outputs/" + account + "/" + region + "/" + ownership.authority_digest(ownership.validate(doc))


def publish_outputs(doc, account, region, admin):
    require(isinstance(admin, AdminChannel), "external admin channel required")
    records = validate_records(doc, admin.read_output(), account, region)
    result = {"schema": "E1_OUTPUT_PUBLICATION_V1", "authority_digest": ownership.authority_digest(doc["ownership_closure"]),
        "account": account, "region": region, "records": records, "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}
    admin.create_publication(output_key(doc, account, region), result)
    return copy.deepcopy(result)


def consume(doc, account, region, consumer, protected_reader):
    """Consumer identity is protected configuration, not requester-selected input.

    The read port must address the admin-controlled publication, not an arbitrary
    file/record supplied by the ordinary caller. Exact equality to that publication
    is the provenance boundary for random AWS IDs; ARN grammar alone is insufficient.
    """
    c = ownership.validate(doc)
    require(consumer in c["consumers"], "consumer binding")
    pub = protected_reader.read_publication(output_key(doc, account, region))
    records = validate_publication(doc, pub, account, region)
    return {key: records[key]["value"] for key in c["consumers"][consumer]}


def validate_publication(doc, pub, account, region):
    c = ownership.validate(doc)
    require(isinstance(pub, dict) and set(pub) == {"schema", "authority_digest", "account", "region", "records", "publisher"}, "publication fields")
    require(pub["schema"] == "E1_OUTPUT_PUBLICATION_V1" and pub["authority_digest"] == ownership.authority_digest(c)
            and pub["account"] == account and pub["region"] == region
            and pub["publisher"] == "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP", "publication provenance")
    records = validate_records(doc, pub["records"], account, region)
    return records


def promote_outputs(doc, account, region, admin):
    """Return an admin change candidate, never write the repo or enable compute.

    Separately reviewed administrator source promotion pins the publication for
    Terraform consumers. Ordinary callers cannot provide the publication body.
    """
    require(isinstance(admin, AdminChannel), "external admin channel required")
    pub = admin.read_publication(output_key(doc, account, region))
    validate_publication(doc, pub, account, region)
    result = copy.deepcopy(doc)
    result["ownership_closure"]["publications"][account + "/" + region] = copy.deepcopy(pub)
    ownership.validate_publications(result)
    return result


def validate_consumer_input(doc, account, region, consumer, supplied, protected_reader):
    require(supplied == consume(doc, account, region, consumer, protected_reader), "manual/substituted protected input")
    return copy.deepcopy(supplied)


def install_bundle(root, doc, account, region, controller_class, consumer, raw, storage, admin):
    """No VersionId parameter, no approval flag and no caller-selected bucket/key.

    Authentication of the two injected ports belongs to external bootstrap.
    The production AWS adapters are deliberately absent; fake ports are tests only.
    Publication success is not invocation authorization or executable readiness.
    """
    from model import validate_repository
    require(validate_repository(root) == doc, "admitted authority required")
    context(account, region)
    require(isinstance(storage, AdminBundleStorage) and isinstance(admin, AdminChannel), "external admin adapters required")
    c = doc["control_bundles"]
    approved = bundles.consumer_reference(c, controller_class, consumer)
    proposal = bundles.installation_proposal(root, c, controller_class, raw)
    require(approved["sha256"] == proposal["reference"]["sha256"], "approved class digest")
    bucket = c["storage"]["bucket_prefix"] + account + "-" + region
    key = approved["key"]
    ack = storage.put_if_absent(bucket, key, raw, proposal["checksum_sha256"])
    require(isinstance(ack, dict) and set(ack) == {"bucket", "key", "version_id"}, "write receipt fields")
    version = ack["version_id"]
    require(ack["bucket"] == bucket and ack["key"] == key, "write identity")
    require(isinstance(version, str) and 0 < len(version) <= 1024 and version.strip() == version
            and version.lower() not in ("null", "latest") and not any(ord(x) < 32 for x in version), "returned VersionId")
    readback = storage.get_exact(bucket, key, version)
    require(isinstance(readback, dict) and set(readback) == {"bucket", "key", "version_id", "bytes"}, "readback fields")
    require({k: readback[k] for k in ack} == ack, "exact-version readback identity")
    bundles.verify_artifact(root, c, controller_class, readback["bytes"])
    require(readback["bytes"] == raw, "readback approved bytes")
    publication_key = "installed/" + controller_class + "/" + consumer + "/" + approved["sha256"]
    result = {"schema": "E1_INSTALLED_REFERENCE_V1", "owner": ownership.OWNER,
        "class": controller_class, "consumer": consumer, "sha256": approved["sha256"],
        "bucket": bucket, "key": key, "version_id": version, "installation": "VERIFIED",
        "readback": "EXACT_VERSION_BYTES_VERIFIED", "operational": False,
        "executable": False, "authority_digest": ownership.authority_digest(doc["ownership_closure"]),
        "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}
    admin.create_publication(publication_key, result)
    return copy.deepcopy(result)
