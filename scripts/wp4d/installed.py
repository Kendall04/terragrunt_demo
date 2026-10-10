"""Exact-version WP4D controller package loading from protected storage."""
import base64
import hashlib
import json
from pathlib import Path


def require(ok):
    if not ok:
        raise ValueError("E1_WP4D_INSTALLATION_REJECTED")


def load(s3, reference, destination):
    """Read only the administrator-published version and verify all bytes first."""
    require(type(reference) is dict and set(reference) ==
            {"bucket", "key", "version_id", "sha256", "binding"})
    digest = reference["sha256"]
    require(type(digest) is str and len(digest) == 64 and
            all(c in "0123456789abcdef" for c in digest))
    require(reference["key"] == "bundles/sha256/" + digest + ".json")
    version = reference["version_id"]
    require(type(version) is str and bool(version) and version == version.strip()
            and version.lower() not in ("null", "latest"))
    response = s3.get_object(Bucket=reference["bucket"], Key=reference["key"], VersionId=version)
    raw = response["Body"].read(1048577)
    require(len(raw) <= 1048576 and response.get("VersionId") == version
            and hashlib.sha256(raw).hexdigest() == digest)
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {"format", "owner", "binding",
            "reservation", "reservation_sha256", "environment", "engine", "files", "entrypoint"})
    require(value["format"] == "E1_WP4D_BUNDLE_JSON_V1" and value["owner"] == "SECURITY_ROOT_OWNED"
            and value["binding"] == reference["binding"]
            and value["entrypoint"] == "scripts/wp4d/runtime.py"
            and type(value["files"]) is dict and bool(value["files"]))
    root = Path(destination).resolve()
    for name, encoded in value["files"].items():
        parts = name.split("/")
        require(type(name) is str and all(part not in ("", ".", "..") and
                ":" not in part and "\\" not in part for part in parts))
        target = root.joinpath(*parts)
        require(root in target.parents)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(base64.b64decode(encoded, validate=True))
    return value
