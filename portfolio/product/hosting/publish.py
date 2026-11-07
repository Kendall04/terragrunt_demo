"""Explicit, owner-authorized static hosting operations. No automatic retries or plan upgrades.

Requires existing boto3 and AWS profile; never installs dependencies or downloads code.
Use only after reviewing template/package hashes and obtaining publication authorization.
"""
import argparse
import base64
import datetime
import hashlib
import json
import pathlib
import re
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

STACK = "ecs-v2-portfolio-demo"
ACCOUNT = "341936017254"
BUCKET = "ecs-v2-portfolio-341936017254-us-east-1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["create", "status", "upload", "enable", "verify"])
    p.add_argument("--profile", required=True)
    p.add_argument("--template", type=pathlib.Path, required=True)
    p.add_argument("--template-sha256", required=True)
    p.add_argument("--package", type=pathlib.Path, required=True)
    p.add_argument("--receipt", type=pathlib.Path, required=True)
    p.add_argument("--pricing-model-root", type=pathlib.Path)
    p.add_argument("--pricing-mode", choices=["free", "pay-as-you-go"], default="free")
    args = p.parse_args()
    assert not args.receipt.exists(), "Never overwrite a receipt"
    raw = args.template.read_bytes()
    assert digest(raw) == args.template_sha256
    template = json.loads(raw)
    if args.pricing_mode == "free":
        assert template["Resources"]["FreeSubscription"]["Properties"]["PlanTier"] == "FREE"
    else:
        assert "FreeSubscription" not in template["Resources"] and "WebACL" not in template["Resources"]
        assert "WebACLId" not in template["Resources"]["Distribution"]["Properties"]["DistributionConfig"]
    root = args.package.resolve()
    manifest_bytes = (root / "MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest["edition"] == "demo" and manifest["awsProxy"] is False
    assert manifest["awsCredentials"] is False
    seal = digest(json.dumps(manifest["files"], separators=(",", ":"), ensure_ascii=False).encode())
    assert seal == manifest["contentSHA256"]
    files = []
    for entry in manifest["files"]:
        name = entry["path"]
        assert re.fullmatch(r"(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_.-]+", name)
        source = root / name
        assert not source.is_symlink() and source.resolve().is_relative_to(root)
        data = source.read_bytes()
        assert digest(data) == entry["sha256"] and len(data) == entry["bytes"]
        files.append((name, data))
    assert dict(files)["assets/config.mjs"] == b'export const edition="demo";'
    files.append(("MANIFEST.json", manifest_bytes))
    s = boto3.Session(profile_name=args.profile, region_name="us-east-1")
    if args.pricing_model_root:
        s._session.get_component("data_loader").search_paths.insert(0, str(args.pricing_model_root.resolve()))
    config = Config(retries={"max_attempts": 0}, connect_timeout=10, read_timeout=30)
    identity = s.client("sts", config=config).get_caller_identity()
    assert identity["Account"] == ACCOUNT
    assert identity["Arn"] == f"arn:aws:iam::{ACCOUNT}:user/cnp-cert-admin"
    cf = s.client("cloudformation", config=config)
    receipt = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "action": args.action,
               "account": ACCOUNT, "templateSHA256": digest(raw), "release": seal, "pricingMode": args.pricing_mode}
    try:
        if args.action == "create":
            try:
                cf.describe_stacks(StackName=STACK)
                raise RuntimeError("Stack exists; refuse adoption or duplicate create")
            except ClientError as e:
                assert e.response["Error"]["Code"] == "ValidationError" and "does not exist" in e.response["Error"]["Message"]
            receipt["result"] = cf.create_stack(StackName=STACK, TemplateBody=raw.decode(),
                Parameters=[{"ParameterKey": "Release", "ParameterValue": seal}, {"ParameterKey": "Enabled", "ParameterValue": "false"}],
                OnFailure="ROLLBACK", TimeoutInMinutes=30, ClientRequestToken="ecs-portfolio-" + str(uuid.uuid4()),
                Tags=[{"Key": "Project", "Value": "ecs-v2-portfolio"}, {"Key": "Owner", "Value": "Kendall"}])
        else:
            stack = cf.describe_stacks(StackName=STACK)["Stacks"][0]
            receipt["stackStatus"] = stack["StackStatus"]
            receipt["outputs"] = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
            if args.action == "status":
                receipt["events"] = [{k: e.get(k) for k in ["Timestamp", "LogicalResourceId", "ResourceStatus", "ResourceStatusReason"]}
                    for e in cf.describe_stack_events(StackName=STACK)["StackEvents"][:15]]
            else:
                assert stack["StackStatus"] in ["CREATE_COMPLETE", "UPDATE_COMPLETE"]
                installed = cf.get_template(StackName=STACK, TemplateStage="Original")["TemplateBody"]
                if isinstance(installed, str): installed = json.loads(installed)
                assert installed == template, "Installed template differs"
                outputs = receipt["outputs"]
                assert outputs["Bucket"] == BUCKET and outputs["Release"] == seal
                if args.pricing_mode == "free":
                    ppm = s.client("pricing-plan-manager", config=config, endpoint_url="https://pricingplanmanager.us-east-1.api.aws")
                    subscription = ppm.get_subscription(arn=outputs["Subscription"])["subscription"]
                    receipt["subscription"] = subscription
                    assert subscription["status"] == "ACTIVE" and subscription["planTier"] == "FREE"
                    assert not subscription.get("scheduledChange")
                else:
                    assert "Subscription" not in outputs
                s3 = s.client("s3", config=config)
                receipt["objects"] = []
                for name, data in files:
                    key = f"releases/{seal}/{name}"
                    checksum = base64.b64encode(hashlib.sha256(data).digest()).decode()
                    try:
                        head = s3.head_object(Bucket=BUCKET, Key=key, ChecksumMode="ENABLED")
                    except ClientError as e:
                        if e.response["Error"]["Code"] != "404" or args.action != "upload": raise
                        ext = pathlib.Path(name).suffix
                        mime = {".html": "text/html; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                                ".ttf": "font/ttf", ".txt": "text/plain; charset=utf-8", ".json": "application/json"}[ext]
                        s3.put_object(Bucket=BUCKET, Key=key, Body=data, IfNoneMatch="*", ChecksumSHA256=checksum,
                                      ContentType=mime, CacheControl="public, max-age=60", ServerSideEncryption="AES256")
                        head = s3.head_object(Bucket=BUCKET, Key=key, ChecksumMode="ENABLED")
                    assert head.get("ChecksumSHA256") == checksum and head["ContentLength"] == len(data)
                    assert head["ServerSideEncryption"] == "AES256"
                    receipt["objects"].append({"key": key, "sha256": digest(data), "versionId": head["VersionId"]})
                if args.action == "enable":
                    params = {x["ParameterKey"]: x["ParameterValue"] for x in stack["Parameters"]}
                    assert params["Enabled"] == "false", "Already enabled; refuse duplicate update"
                    receipt["result"] = cf.update_stack(StackName=STACK, UsePreviousTemplate=True,
                        Parameters=[{"ParameterKey": "Release", "UsePreviousValue": True}, {"ParameterKey": "Enabled", "ParameterValue": "true"}],
                        ClientRequestToken="ecs-portfolio-enable-" + str(uuid.uuid4()))
                if args.action == "verify":
                    receipt["publicAccessBlock"] = s3.get_public_access_block(Bucket=BUCKET)["PublicAccessBlockConfiguration"]
                    assert all(receipt["publicAccessBlock"].values())
                    receipt["bucketPolicy"] = json.loads(s3.get_bucket_policy(Bucket=BUCKET)["Policy"])
                    receipt["distribution"] = s.client("cloudfront", config=config).get_distribution(Id=outputs["DistributionId"])["Distribution"]
                    dist = receipt["distribution"]
                    assert dist["Status"] == "Deployed" and dist["DistributionConfig"]["Enabled"]
                    assert dist["DistributionConfig"]["Origins"]["Quantity"] == 1
        receipt["resultStatus"] = "PASS"
    except Exception as e:
        receipt["resultStatus"] = "FAILED_OR_UNCERTAIN"
        receipt["error"] = str(e)
        raise
    finally:
        args.receipt.write_text(json.dumps(receipt, indent=2, default=str), encoding="utf8")
        print(json.dumps({k: receipt.get(k) for k in ["action", "resultStatus", "stackStatus", "outputs", "error"]}))


if __name__ == "__main__":
    main()
