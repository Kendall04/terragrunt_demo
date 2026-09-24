"""Run WP1 offline characterization, never target E1 acceptance.

Usage: python -I -B scripts/tests/authority/run.py [--report PATH]
Requires only Python >=3.10 and Git for fixed read-only revision metadata.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    git = shutil.which("git")
    if not git:
        raise SystemExit("Git required for exact offline revision identity")
    # Only fixed local Git reads precede the process guard. Do not run user aliases,
    # hooks, credential helpers, remote commands, checkout, Terraform or AWS here.
    env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    def metadata(*argv):
        return subprocess.check_output([git, "-c", "safe.directory=" + ROOT.as_posix(),
                                        "-c", "core.fsmonitor=false", "--no-pager", *argv],
                                       cwd=ROOT, env=env, text=True).strip()
    identity = {"revision": metadata("rev-parse", "HEAD"), "committed_tree": metadata("rev-parse", "HEAD^{tree}"),
                "status": metadata("status", "--porcelain=v1", "--untracked-files=all")}
    from hermetic import install
    # Load stdlib socket before the audit hook so guard tests can call its API.
    import socket  # noqa: F401
    install()
    from inventory import scan, verify
    from graph import baseline
    from source import semantic_inventory
    from evaluator import Unsupported
    files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in scan(ROOT)}
    for directory in (ROOT / "ci/authority", HERE):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("specs/iam-hardening/spec.md", "specs/iam-hardening/plan.md"):
        files[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    errors = verify(ROOT)
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py")
    class Recorded(unittest.TextTestResult):
        def startTest(self, test):
            executed.append(test.id())
            super().startTest(test)
    executed = []
    result = unittest.TextTestRunner(verbosity=2, resultclass=Recorded).run(suite)
    chains = []
    if not errors:
        for environment in ("dev", "prod"):
            try:
                chains.extend(baseline(ROOT, (environment,)))
            except Unsupported as exc:
                # One invalid environment must not erase valid evidence for the
                # other. The package still fails characterization visibly.
                errors.append(environment + ": " + str(exc))
                chains.append({"environment": environment, "classification": "UNVERIFIED",
                               "reason_codes": ["SOURCE_BINDING_UNKNOWN"], "error": str(exc),
                               "states": {}, "outcomes": {}})
    good = result.wasSuccessful() and not result.skipped and result.testsRun > 0 and not errors
    report = {
        "result": "WP1_CHARACTERIZATION_PASS" if good else "WP1_CHARACTERIZATION_FAIL",
        "e1_acceptance": "NOT_EVALUATED_NOT_SECURE",
        "identity": identity, "evaluated_file_sha256": files,
        "evaluated_content_digest": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "scope": "repository-model reachability with fixed synthetic inputs; not executed exploits",
        "executed_tests": executed, "counts": {"executed": result.testsRun, "failures": len(result.failures),
                                                 "errors": len(result.errors), "skipped": len(result.skipped)},
        "test_modules": {module: {"executed": sum(x.split(".")[0] == module for x in executed),
            "failures": sum(t.id().split(".")[0] == module for t, _ in result.failures),
            "errors": sum(t.id().split(".")[0] == module for t, _ in result.errors),
            "skipped": sum(t.id().split(".")[0] == module for t, _ in result.skipped)}
            for module in sorted({x.split(".")[0] for x in executed})},
        "inventory_errors": errors, "baseline": chains,
        "semantic_source_admission": semantic_inventory(ROOT),
        "external_prerequisites": "UNVERIFIED",
        "hermetic": "credential environment scrubbed; AWS files disabled; PATH empty; process/socket/dlopen audit guard active",
        "limitations": ["process-level accidental-I/O guard, not malicious-code sandbox", "only admitted policy/API semantics evaluated",
                        "inventoried UNVERIFIED surfaces and managed-policy contents remain UNKNOWN", "no target controller or cloud configuration exists"]}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("result", "e1_acceptance", "identity", "evaluated_content_digest", "counts", "inventory_errors")}, indent=2))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
