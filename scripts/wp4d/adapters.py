"""Protected storage and WP4A fact adapters for WP4D compute.

The installed configuration fixes bucket and namespace ownership. Observations
come from independently authenticated AWS reads, never from request JSON.
"""
import re

from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d


def _require(ok):
    if not ok:
        raise ValueError("E1_WP4D_ADAPTER_REJECTED")


def _missing(error):
    code = getattr(error, "response", {}).get("Error", {}).get("Code")
    return code in ("NoSuchKey", "NoSuchVersion", "404")


class Objects(d.Records):
    """Create-only and exact-read records in one installed, class-owned prefix."""
    def __init__(self, s3, bucket, prefix):
        _require(type(bucket) is str and bool(bucket) and type(prefix) is str
                 and re.fullmatch(r"[a-z0-9/-]+/", prefix) is not None)
        self.s3, self.bucket, self.prefix = s3, bucket, prefix

    def _key(self, key):
        _require(type(key) is str and re.fullmatch(r"[A-Za-z0-9._/:-]{1,512}", key) is not None
                 and all(part not in ("", ".", "..") for part in key.split("/")))
        return self.prefix + key

    def read(self, key):
        try:
            value = self.s3.get_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as error:
            if _missing(error):
                return None
            raise
        raw = value["Body"].read(1048577)
        _require(len(raw) <= 1048576 and type(value.get("VersionId")) is str)
        return {"version_id": value["VersionId"], "bytes": raw}

    def create(self, key, raw):
        _require(type(raw) is bytes and 0 < len(raw) <= 1048576)
        self.s3.put_object(Bucket=self.bucket, Key=self._key(key), Body=raw,
                           IfNoneMatch="*", ContentType="application/json")


class RecoveryObjects(d.Records):
    """Keep recovery journals separate from immutable WP4B success evidence."""
    def __init__(self, s3, bucket, environment):
        _require(environment in ("dev", "prod"))
        self.environment = environment
        self.recovery = Objects(s3, bucket, "recovery/")
        self.delivery = Objects(s3, bucket, "delivery/")

    def _store(self, key):
        _require(type(key) is str and key.startswith(self.environment + "/"))
        return (self.recovery if key.startswith(self.environment + "/recovery/")
                else self.delivery)

    def read(self, key):
        return self._store(key).read(key)

    def create(self, key, raw):
        _require(self._store(key) is self.recovery)
        self.recovery.create(key, raw)


class Facts(a.Facts):
    """Current protected S3 records and exact repository digest observations."""
    def __init__(self, s3, ecr, config):
        _require(type(config) is dict and set(config) ==
                 {"account", "region", "environment", "endpoint", "admin_bucket",
                  "evidence_bucket", "dev_evidence_bucket", "repository"})
        self.s3, self.ecr, self.c = s3, ecr, config

    def _get(self, bucket, key, version=None):
        args = {"Bucket": bucket, "Key": key}
        if version is not None:
            a.version(version)
            args["VersionId"] = version
        result = self.s3.get_object(**args)
        raw = result["Body"].read(1048577)
        _require(len(raw) <= 1048576 and type(result.get("VersionId")) is str)
        if version is not None:
            _require(result["VersionId"] == version)
        return {"version_id": result["VersionId"], "bytes": raw}

    def qualification(self, release_id):
        a.match(r"sha256-[0-9a-f]{64}", release_id)
        return self._get(self.c["admin_bucket"],
                         "qualifications/demo-api/" + release_id + ".json")["bytes"]

    def manifest(self, bucket, key, version_id):
        _require(bucket == self.c["admin_bucket"])
        a.match(r"releases/demo-api/by-digest/sha256-[0-9a-f]{64}\.json", key)
        value = self._get(bucket, key, version_id)
        return {"bucket": bucket, "key": key, **value}

    def eligibility_current(self, release_id):
        a.match(r"sha256-[0-9a-f]{64}", release_id)
        return {"release_id": release_id, **self._get(
            self.c["admin_bucket"], "eligibility/demo-api/" + release_id + ".json")}

    def environment(self, endpoint):
        _require(endpoint == self.c["endpoint"])
        return {"endpoint": endpoint, **self._get(
            self.c["admin_bucket"], "bindings/" + endpoint + ".json")}

    def membership(self, environment):
        _require(environment == self.c["environment"])
        return {"environment": environment, **self._get(
            self.c["admin_bucket"], "membership/" + environment + ".json")}

    def artifact(self, repository, digest):
        _require(repository == self.c["repository"])
        a.match(r"sha256:[0-9a-f]{64}", digest)
        result = self.ecr.describe_images(repositoryName=repository,
                                          imageIds=[{"imageDigest": digest}])
        details = result.get("imageDetails", [])
        _require(type(details) is list and len(details) == 1
                 and details[0].get("imageDigest") == digest)
        return {"account": self.c["account"], "region": self.c["region"],
                "repository": repository, "digest": digest, "available": True}

    def promotion(self, release_id):
        _require(self.c["environment"] == "prod")
        a.match(r"sha256-[0-9a-f]{64}", release_id)
        dev = self._get(self.c["dev_evidence_bucket"],
                        "activations/by-release/" + release_id + ".json")
        approved = self._get(self.c["admin_bucket"],
                             "prod-approvals/demo-api/" + release_id + ".json")
        return {"dev_receipt": {"release_id": release_id, **dev},
                "prod_approval": {"release_id": release_id, **approved}}


class History:
    """Controller-owned color index, validated again by WP4C receipt closure."""
    def __init__(self, s3, bucket, environment):
        _require(environment in ("dev", "prod"))
        self.s3, self.bucket, self.environment = s3, bucket, environment

    def current(self):
        result = {}
        for color in ("blue", "green"):
            try:
                response = self.s3.get_object(Bucket=self.bucket,
                                              Key="history/" + color + ".json")
            except Exception as error:
                if _missing(error):
                    result[color] = None
                    continue
                raise
            value = a.decode(response["Body"].read(4097))
            a.keys(value, ("environment", "color", "operation"))
            _require(value["environment"] == self.environment and value["color"] == color)
            d.identity(value["operation"])
            result[color] = value["operation"]
        return result

    def publish(self, receipt, records):
        """Only a locally authenticated successful WP4B receipt may advance index."""
        _require(receipt["schema"] == "E1_DELIVERY_RECEIPT_V1"
                 and receipt["status"] == "SUCCESS"
                 and receipt["environment"] == self.environment)
        operation = d.identity(receipt["operation_id"])
        observed = records.read(self.environment + "/" + operation + "/success")
        _require(observed is not None and a.decode(observed["bytes"]) == receipt)
        color = receipt["intent"]["color"]
        _require(color in ("blue", "green"))
        raw = a.canonical({"environment": self.environment, "color": color,
                           "operation": operation})
        self.s3.put_object(Bucket=self.bucket, Key="history/" + color + ".json",
                           Body=raw, ContentType="application/json")
        response = self.s3.get_object(Bucket=self.bucket, Key="history/" + color + ".json")
        _require(response["Body"].read(4097) == raw)
