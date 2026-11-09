"""Disposable receipt prototype. No AWS SDK, no cloud calls, only fictitious payloads."""
import base64
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

REPO = "Kendall04/terragrunt_demo"
BRANCH = "codex/receipt-attestations-trial-20261109"
TYPE = "https://github.com/Kendall04/terragrunt_demo/receipt-prototype/v1"
OUT = Path("out")

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))

def read(path):
    return json.loads(Path(path).read_bytes())

def api(path, body=None):
    command = ["gh", "api", "-H", "Accept: application/vnd.github+json", "repos/" + REPO + "/" + path]
    if body is not None:
        command += ["--method", "POST", "--input", "-"]
    raw = subprocess.check_output(command, input=canonical(body) if body is not None else None, timeout=90)
    return json.loads(raw)

def context():
    return {"repository": REPO, "workflow_sha": os.environ["GITHUB_WORKFLOW_SHA"],
            "source_sha": os.environ["GITHUB_SHA"], "workflow_ref": os.environ["GITHUB_WORKFLOW_REF"],
            "signer": ".github/workflows/" + os.environ["PROTOTYPE_SIGNER"] + ".yml",
            "run": int(os.environ["GITHUB_RUN_ID"]), "attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "event": os.environ["GITHUB_EVENT_NAME"], "ref": os.environ["GITHUB_REF"]}

def slot(kind, operation):
    return {"schema": "github-receipt-slot-prototype/v1", "repository": REPO,
            "kind": kind, "operation": operation}

def bundles(subject):
    # A single-operation slot, never the latest image or latest release.
    values = []
    for page in range(1, 5):
        path = "attestations/sha256:" + subject + "?per_page=100"
        if page != 1:
            raise ValueError("Cursor pagination requires explicit review for this bounded prototype")
        response = api(path)
        for row in response["attestations"]:
            bundle = row.get("bundle")
            if bundle is None:
                url = row["bundle_url"]
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme != "https" or not parsed.hostname.endswith(".blob.core.windows.net"):
                    raise ValueError("Unexpected attestation bundle host")
                with urllib.request.urlopen(url, timeout=60) as data:
                    raw = data.read(1048577)
                if len(raw) > 1048576:
                    raise ValueError("Oversized bundle")
                bundle = json.loads(raw)
            values.append(bundle)
        if len(response["attestations"]) >= 100:
            raise ValueError("Bounded prototype slot overflow")
        break
    return values

def statement(bundle):
    return json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))

def verify_bundle(bundle, locator, label):
    OUT.mkdir(exist_ok=True)
    subject_path = OUT / (label + "-slot.json")
    bundle_path = OUT / (label + "-bundle.json")
    write(subject_path, locator["slot"])
    write(bundle_path, bundle)
    assert sha(subject_path.read_bytes()) == locator["subject_sha256"]
    authority = locator["authority"]
    signer = REPO + "/" + authority["signer"]
    command = ["gh", "attestation", "verify", str(subject_path), "--bundle", str(bundle_path),
               "--repo", REPO, "--predicate-type", TYPE, "--signer-workflow", signer,
               "--signer-digest", authority["workflow_sha"], "--source-digest", authority["source_sha"],
               "--source-ref", authority["ref"], "--deny-self-hosted-runners", "--format", "json"]
    result = subprocess.run(command, capture_output=True, timeout=120)
    (OUT / (label + "-verify.log")).write_bytes(result.stderr)
    if result.returncode:
        raise ValueError("Cryptographic identity/content verification failed: " + label)
    verified = json.loads(result.stdout)
    write(OUT / (label + "-verified.json"), verified)
    assert len(verified) == 1
    verified_statement = verified[0]["verificationResult"]["statement"]
    cert = verified[0]["verificationResult"]["signature"]["certificate"]
    # Exact signed execution URI/event are checked after inspecting the real
    # verifier schema. Never authenticate these fields only from the predicate.
    write(OUT / (label + "-certificate.json"), cert)
    receipt = verified_statement["predicate"]
    assert receipt["publisher"] == authority, "Publisher mismatch"
    assert receipt["fictitious"] is True
    if locator.get("statement_sha256"):
        assert sha(base64.b64decode(bundle["dsseEnvelope"]["payload"])) == locator["statement_sha256"], "Statement substituted"
    return receipt

def resolve(locator, label):
    matching = []
    errors = []
    for index, bundle in enumerate(bundles(locator["subject_sha256"])):
        try:
            receipt = verify_bundle(bundle, locator, label + "-" + str(index))
            matching.append((receipt, bundle))
        except (ValueError, AssertionError) as error:
            errors.append(str(error))
    if len(matching) != 1:
        raise ValueError("Expected exactly one authenticated sealed receipt: " + str(errors))
    return matching[0]

def prepare(mode):
    OUT.mkdir(exist_ok=True)
    cfg = read("inputs/" + mode + ".json")
    pub = context()
    operation = str(pub["run"])
    descriptor = slot(mode, operation)
    if mode == "dev":
        version = cfg["version"]
        manifest = {"fictitious": True, "environment": "dev", "commit": cfg["source"],
                    "application": cfg["application"], "image": "000000000000.dkr.ecr.us-east-1.amazonaws.com/fictitious@sha256:" + sha(version.encode()),
                    "ecs_revision": "arn:aws:ecs:us-east-1:000000000000:task-definition/fictitious-" + version + ":1",
                    "health": {"per_task_ready": True, "sql_query": True, "kms_roundtrip": True, "client_ready": True},
                    "operation": operation, "producer": pub}
        receipt = dict(manifest, schema="deployment-receipt-prototype/v1", publisher=pub,
                       manifest_ref={"bucket": "fictitious-not-an-aws-resource", "key": "operations/" + operation + "/release.json",
                                     "VersionId": "fictitious-version-" + version, "sha256": sha(canonical(manifest))})
        write(OUT / "fictitious-s3-manifest.json", manifest)
    elif mode == "approval":
        dev, _ = resolve(cfg["dev"], "approved-dev")
        receipt = {"schema": "promotion-receipt-prototype/v1", "fictitious": True,
                   "repository": REPO, "pr": cfg["pr"], "head": cfg["head"], "base": cfg["base"],
                   "application": dev["application"], "image": dev["image"],
                   "dev": cfg["dev"], "manifest_ref": dev["manifest_ref"], "publisher": pub}
        assert cfg["head"] == dev["commit"]
    elif mode == "forgery":
        # Sign a counterfeit with the OTHER workflow's real identity, while its
        # user-controlled claims copy the legitimate producer byte for byte.
        receipt = cfg["receipt"]
        descriptor = cfg["locator"]["slot"]
    else:
        raise ValueError("Unsupported mode")
    write(OUT / "slot.json", descriptor)
    write(OUT / "receipt.json", receipt)
    write(OUT / "authority.json", pub)

def finish(mode):
    bundle = read(os.environ["BUNDLE_PATH"])
    descriptor = read(OUT / "slot.json")
    authority = read(OUT / "authority.json")
    locator = {"v": 1, "slot": descriptor, "subject_sha256": sha(canonical(descriptor)),
               "statement_sha256": sha(base64.b64decode(bundle["dsseEnvelope"]["payload"])),
               "attestation_id": os.environ["ATTESTATION_ID"], "authority": authority}
    write(OUT / "bundle.json", bundle)
    write(OUT / "locator.json", locator)
    if mode != "forgery":
        verify_bundle(bundle, locator, "publisher")
    if mode == "approval":
        # A separate check name on the disposable branch only: no ruleset changes,
        # no real PR and never the production required-check name.
        check = api("check-runs", {"name": "Receipt prototype approval (NOT deployment)",
                    "head_sha": os.environ["GITHUB_SHA"], "status": "completed", "conclusion": "success",
                    "external_id": json.dumps(locator, separators=(",", ":")),
                    "details_url": "https://github.com/" + REPO + "/attestations/" + locator["attestation_id"],
                    "output": {"title": "Fictitious B approval", "summary": "No real PR, image, AWS resource or deployment."}})
        write(OUT / "check.json", check)
    print("RECEIPT_LOCATOR=" + json.dumps(locator, separators=(",", ":")))

if __name__ == "__main__":
    {"prepare": prepare, "finish": finish}[sys.argv[1]](sys.argv[2])

