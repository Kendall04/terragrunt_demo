"""Conservative source-coverage admission, separate from semantic evaluation.

All Terraform/Terragrunt and operational sources are registered, not just files
whose names contain IAM. Adding or editing a surface requires inventory review.
Hashes establish review freshness, NOT security or policy semantics.
"""
import json
from pathlib import Path
import re
from source import digest

IGNORED = {".git", ".terraform", ".terragrunt-cache", "__pycache__", "bin", "obj", "node_modules"}
DECLARATION = re.compile(r'(?m)^\s*(resource|data|module)\s+"([^"]+)"(?:\s+"([^"]+)")?\s*\{')
SIGNALS = {
    "credential-acquisition": r"configure-aws-credentials|assume-role|AssumeRole|id-token:",
    "role-input": r"AWS_ROLE_|role-to-assume|role_arn|roleArn|taskRoleArn|executionRoleArn|iam_instance_profile",
    "launch-or-mutation": r"\baws\b|\bboto3\b|terraform|terragrunt|register-task-definition|update-service|modify-listener|put-targets|docker run",
    "executable-dependency": r"source\s*=|user_data|filename\s*=|image\s*=|entryPoint|command|\.sh\b|\.py\b|uses:",
    "security-control": r"permissions_boundary|assume_role_policy|policy\s*=|policy_arn|aws_lambda_permission|aws_kms|aws_iam|aws_.*_policy",
}


def sources(root):
    root = Path(root)
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError("source symlink requires explicit review: " + rel.as_posix())
        if not path.is_file():
            continue
        if rel.parts[0] == "ci" and len(rel.parts) > 1 and rel.parts[1] in ("schemas", "ephemeral") and path.suffix == ".json":
            yield path
            continue
        if rel.as_posix() == "global.json":
            # The host SDK selection is an executed build input, even at root.
            yield path
            continue
        own_contract = rel.parts[:2] == ("ci", "authority") and path.suffix in (".json", ".md") and not path.name.endswith(".tf.json")
        own_test = rel.parts[:3] == ("scripts", "tests", "authority") and path.suffix in (".py", ".md")
        if own_contract or own_test:
            continue
        # Deliberately conservative: unknown files under operational roots are covered too.
        if (rel.parts[0] in ("terraform", ".github", "scripts") and path.suffix not in (".md", ".png")) or \
                (rel.parts[:2] == ("demo-api", "deploy")) or path.name == "Dockerfile":
            yield path
        elif path.suffix in (".tf", ".hcl", ".tfvars", ".ps1", ".sh", ".py", ".yml", ".yaml") or path.name.endswith(".tf.json"):
            yield path


def scan(root):
    root = Path(root)
    found = {}
    for path in sources(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8-sig")
        declarations = [{"kind": m[1], "type": m[2], "name": m[3],
                         "line": text.count("\n", 0, m.start()) + 1} for m in DECLARATION.finditer(text)]
        signals = {name: [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)]
                   for name, pattern in SIGNALS.items()}
        signals = {k: v for k, v in signals.items() if v}
        found[rel] = {"sha256": digest(path), "declarations": declarations, "signals": signals}
    return found


def verify(root):
    expected = json.loads((Path(root) / "ci/authority/source-inventory.json").read_text())["sources"]
    actual = scan(root)
    errors = []
    for path in sorted(set(expected) | set(actual)):
        if path not in expected:
            errors.append("UNMODELED_SOURCE: " + path)
        elif path not in actual:
            errors.append("MISSING_SOURCE: " + path)
        elif any(actual[path][key] != expected[path][key] for key in ("sha256", "declarations", "signals")):
            errors.append("SOURCE_DRIFT_REQUIRES_REVIEW: " + path)
        if path in expected and expected[path].get("semantic_status") not in ("CURRENT_FACT", "UNVERIFIED"):
            errors.append("MISSING_SEMANTIC_DISPOSITION: " + path)
    return errors
