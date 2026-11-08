"""Process-level accidental-I/O guard, not a sandbox for malicious Python code.

The runner loads only checked-in tests, never application/Terraform code. Audit
hooks deny sockets/processes/dynamic-library loads for the lifetime of the run.
"""
import os
import sys

BLOCKED = {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.spawn",
           "ctypes.dlopen", "pty.spawn"}


def install():
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(("AWS", "AMAZON", "BOTO", "GITHUB", "GH_", "AZURE", "GOOGLE", "TF_", "TERRAGRUNT")) or \
                "PROXY" in upper or upper in ("BASH_ENV", "ENV", "PYTHONPATH", "PYTHONSTARTUP"):
            del os.environ[key]
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    os.environ["AWS_CONFIG_FILE"] = os.devnull
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = os.devnull
    os.environ["PATH"] = ""
    def guard(event, args):
        if event.startswith("socket.") or event in BLOCKED:
            raise PermissionError("HERMETIC_GUARD: " + event)
    sys.addaudithook(guard)
