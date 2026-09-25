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
    NOT state. read_publication must raise KeyError only for an absent key, and fail on
    ambiguous provenance. Class-installation entries may be created only by the
    verified installer; arbitrary caller records cannot enter that namespace.
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


def _installation_context(doc, account, region, controller_class):
    context(account, region)
    c = doc["control_bundles"]
    require(controller_class in c["classes"], "canonical installation class")
    ref = bundles.reference(c, controller_class)
    return {"schema": "E1_CLASS_INSTALLATION_V1", "owner": ownership.OWNER,
        "class": controller_class, "sha256": ref["sha256"],
        "bucket": c["storage"]["bucket_prefix"] + account + "-" + region,
        "key": ref["key"], "authority_digest": ownership.authority_digest(doc["ownership_closure"]),
        "catalog_digest": ownership.digest(c), "installation": "VERIFIED",
        "version_origin": "CONDITIONAL_WRITE_RETURN", "readback": "EXACT_VERSION_BYTES_VERIFIED",
        "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}


def installation_key(doc, account, region, controller_class):
    # Stable lookup detects stale/conflicting installations rather than adopting
    # an existing object or silently switching to a different published version.
    _installation_context(doc, account, region, controller_class)
    return "class-installations/" + account + "/" + region + "/" + controller_class


_ABSENT = object()


def _read_optional(admin, key):
    # Only an explicit missing-key response means absent. Transport/auth errors
    # propagate; they are never a reason to overwrite or reinstall.
    try:
        return admin.read_publication(key)
    except KeyError:
        return _ABSENT


def _validate_installation(doc, account, region, controller_class, evidence):
    fixed = _installation_context(doc, account, region, controller_class)
    require(isinstance(evidence, dict) and set(evidence) == set(fixed) | {"version_id", "installation_id"}, "closed class installation evidence")
    require(all(type(evidence[k]) is type(v) and evidence[k] == v for k, v in fixed.items()), "current canonical installation provenance")
    version = evidence["version_id"]
    require(isinstance(version, str) and 0 < len(version) <= 1024 and version.strip() == version
            and version.lower() not in ("null", "latest") and not any(ord(x) < 32 for x in version), "installed exact VersionId")
    require(evidence["installation_id"] == ownership.digest({k: v for k, v in evidence.items() if k != "installation_id"}), "installation identity mismatch")
    return copy.deepcopy(evidence)


def install_class(root, doc, account, region, controller_class, raw, storage, admin):
    """Install once or reuse evidence read ONLY from the trusted admin channel.

    No evidence document/VersionId is accepted as an argument. The channel must
    protect the class-installations namespace against arbitrary JSON insertion;
    installation_id is a consistency checksum, never an authentication token.
    """
    from model import validate_repository
    require(validate_repository(root) == doc, "admitted authority required")
    require(isinstance(storage, AdminBundleStorage) and isinstance(admin, AdminChannel), "external admin adapters required")
    fixed = _installation_context(doc, account, region, controller_class)
    c = doc["control_bundles"]
    proposal = bundles.installation_proposal(root, c, controller_class, raw)
    lookup = installation_key(doc, account, region, controller_class)
    existing = _read_optional(admin, lookup)
    if existing is not _ABSENT:
        return _validate_installation(doc, account, region, controller_class, existing)
    bucket, key = fixed["bucket"], fixed["key"]
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
    evidence = {**fixed, "version_id": version}
    evidence["installation_id"] = ownership.digest(evidence)
    # Atomic create-only publication: no evidence exists before verification.
    admin.create_publication(lookup, evidence)
    return copy.deepcopy(evidence)


def publish_consumer(root, doc, account, region, controller_class, consumer, admin):
    """Resolve the canonical relation through protected class evidence, not a
    consumer record, requester-supplied installation or arbitrary version selector.
    Class/consumer arguments are administrator operation selectors only.
    """
    from model import validate_repository
    require(validate_repository(root) == doc, "admitted authority required")
    require(isinstance(admin, AdminChannel), "external admin channel required")
    approved = bundles.consumer_reference(doc["control_bundles"], controller_class, consumer)
    evidence = _validate_installation(doc, account, region, controller_class,
        admin.read_publication(installation_key(doc, account, region, controller_class)))
    require(approved["sha256"] == evidence["sha256"] and approved["key"] == evidence["key"], "canonical consumer installation binding")
    publication_key = "installed/" + controller_class + "/" + consumer + "/" + approved["sha256"]
    result = {"schema": "E1_INSTALLED_REFERENCE_V1", "owner": ownership.OWNER,
        "class": controller_class, "consumer": consumer, "sha256": approved["sha256"],
        "bucket": evidence["bucket"], "key": evidence["key"], "version_id": evidence["version_id"], "installation": "VERIFIED",
        "readback": "EXACT_VERSION_BYTES_VERIFIED", "operational": False,
        "executable": False, "authority_digest": evidence["authority_digest"],
        "installation_id": evidence["installation_id"], "catalog_digest": evidence["catalog_digest"],
        "publisher": "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"}
    existing = _read_optional(admin, publication_key)
    if existing is not _ABSENT:
        require(existing == result, "conflicting consumer publication")
        return copy.deepcopy(existing)
    admin.create_publication(publication_key, result)
    return copy.deepcopy(result)


def install_bundle(root, doc, account, region, controller_class, consumer, raw, storage, admin):
    """Convenience admin operation: validate consumer, install class once, publish.
    Existing storage conflicts are never caught/adopted. Reuse requires protected
    evidence from a completed exact-version installation, not object existence.
    """
    bundles.consumer_reference(doc["control_bundles"], controller_class, consumer)
    install_class(root, doc, account, region, controller_class, raw, storage, admin)
    return publish_consumer(root, doc, account, region, controller_class, consumer, admin)
