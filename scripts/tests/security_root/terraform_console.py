"""Strict provider-free console JSON readback with known CLI lock status lines.

Terraform console has no -lock=false option. Its Windows local-state release
statuses may precede or follow the result even without a backend/provider. Never
accept warnings, errors, multiple JSON values or arbitrary diagnostic output.
"""
import json

STATUSES = ("Acquiring state lock. This may take a few moments...",
            "Releasing state lock. This may take a few moments...")


def decode(stdout):
    lines = stdout.splitlines()
    if any(lines.count(status) > 1 for status in STATUSES):
        raise ValueError("AMBIGUOUS_TERRAFORM_CONSOLE_STATUS")
    raw = "\n".join(line for line in lines if line not in STATUSES)
    outer = json.loads(raw)
    if type(outer) is not str:
        raise ValueError("TERRAFORM_CONSOLE_JSON_STRING_REQUIRED")
    return json.loads(outer)
