# Evidence Notes

**CURRENT CONTRACT:** these are synthetic contract examples, not evidence that
tests, releases, deployment or rollback succeeded. No infrastructure is deployed
as of owner reconciliation on 2026-09-18. No historical-state cleanup is pending.
Future evidence must bind claims to the exact source/artifact and verified result;
see [delivery](../deployment.md) and [decisions](../decisions-and-limitations.md).
Do not infer verification from the quality fields in example JSON.

The architecture PNG is an illustrative older view, not a placement guarantee.
The CD pipeline PNG is HISTORICAL / SUPERSEDED and must not guide operations.

This folder contains redacted examples of operational evidence for the demo.

The JSON examples use synthetic account IDs, ARNs, S3 bucket names, image URIs,
run IDs, and digests. They are intended to show the shape of the release audit
trail without exposing real infrastructure identifiers.

For a public portfolio version, add a real GitHub Actions screenshot here after
redacting:

- AWS account IDs
- backend bucket names and object keys
- listener, target group, task definition, and IAM role ARNs
- full image URIs and ECR registry IDs
- secret names, secret ARNs, and environment-specific values

Recommended screenshot:

```text
terraform/docs/evidence/github-actions-cd.png
```

Capture the workflow graph or job summary for a successful app release or
manifest rollback run. Do not add a fabricated screenshot.
