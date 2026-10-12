"""E2-R read-only diagnosis, never recovery authorization or mutation authority.

Call only with the protected bucket/environment/domain from installed configuration
and an independently authenticated diagnostic client. No client/credentials are
created here. This module is not an installed controller or a recovery endpoint.
"""
import hashlib

from scripts.environment_mutation import Store, canonical


class _ReadOnly:
    def __init__(self, client):
        self.client = client
        self.version = None

    def get_object(self, **kwargs):
        response = self.client.get_object(**kwargs)
        self.version = response.get("VersionId")
        return response


def inspect_domain(s3, bucket, environment, selected="application"):
    """One current, validated head observation; no termination/effect inference.

    Missing, malformed and unavailable observations return the same fixed blocked
    diagnostic. SDK errors and unvalidated bytes are never copied to the report.
    A valid observation does not prove bucket installation, caller authority,
    executor termination, remote quiescence or deployment consistency.
    """
    reader = _ReadOnly(s3)
    store = Store(reader, bucket, environment, selected)
    report = dict(schema="E2R_DIAGNOSTIC_V1", bucket=bucket, key=store.key,
                  environment=environment, domain=selected,
                  recovery="UNAVAILABLE", termination="UNPROVED", effects="UNRECONCILED")
    try:
        value, etag = store.read()
    except Exception:
        return dict(report, status="E2R_BLOCKED_HEAD_UNPROVED", observation=None)
    return dict(report, status=("E2R_BLOCKED_QUIESCENCE_UNPROVED" if value["state"] == "ACTIVE"
                               else "E2R_RELEASED_OBSERVED"),
                observation=dict(head=value, etag=etag, version_id=reader.version,
                                 sha256=hashlib.sha256(canonical(value)).hexdigest()))
