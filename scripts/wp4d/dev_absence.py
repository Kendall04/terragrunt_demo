"""Bounded CURRENT absence observation for the three DEV delivery roles only.

A 403 is never absence. Only an independently authorized, complete exact-prefix
listing can raise FileNotFoundError. No writes, retries or ownership decisions.
"""
import re


PREFIXES = ("gateway/dev/normal/", "delivery/dev/", "history/",
            "activations/by-release/", "recovery/dev/recovery/cleanup/",
            "arbitration/dev/terminals/normal-delivery/deploy-dev/",
            "arbitration/dev/terminals/cleanup-recovery/cleanup-dev/")


def get_object(s3, **request):
    try:
        return s3.get_object(**request)
    except Exception as original:
        code = getattr(original, "response", {}).get("Error", {}).get("Code")
        bucket, key = request.get("Bucket"), request.get("Key")
        if (code not in ("AccessDenied", "403") or set(request) != {"Bucket", "Key"}
                or type(bucket) is not str or re.fullmatch(
                    r"e1-wp4-dev-[0-9]{12}-[a-z]{2}(?:-[a-z]+)+-[0-9]", bucket) is None
                or type(key) is not str or not key.startswith(PREFIXES)):
            raise
        listed = s3.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=2)
        if (listed.get("IsTruncated") is not False or listed.get("Prefix") != key
                or type(listed.get("Contents", [])) is not list):
            raise original
        contents = listed.get("Contents", [])
        if not all(type(v) is dict and type(v.get("Key")) is str and v["Key"].startswith(key)
                   for v in contents):
            raise original
        if any(v["Key"] == key for v in contents):
            raise original
        # This local exception represents the authentic listing observation;
        # it is not a fabricated AWS error response or a terminal effect record.
        raise FileNotFoundError("DEV_CURRENT_ABSENCE_VERIFIED_BY_EXACT_LISTING") from None
