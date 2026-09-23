import os
import socket
import subprocess
import unittest
from hermetic import install


class HermeticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Also safe when someone invokes this test module outside run.py.
        install()

    def test_credential_inputs_removed(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "synthetic-canary"
        os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"] = "/synthetic/token"
        os.environ["AWS_CONTAINER_CREDENTIALS_FULL_URI"] = "http://synthetic.invalid"
        os.environ["GITHUB_TOKEN"] = "synthetic-canary"
        os.environ["HTTPS_PROXY"] = "http://synthetic.invalid"
        install()
        for key in ("AWS_ACCESS_KEY_ID", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_CONTAINER_CREDENTIALS_FULL_URI", "GITHUB_TOKEN", "HTTPS_PROXY"):
            self.assertNotIn(key, os.environ)
        self.assertEqual(os.environ["AWS_EC2_METADATA_DISABLED"], "true")
        self.assertEqual(os.environ["AWS_SHARED_CREDENTIALS_FILE"], os.devnull)

    def test_real_aws_and_other_subprocesses_blocked(self):
        for command in (["aws", "sts", "get-caller-identity"], ["terraform", "init"], ["gh", "api", "user"]):
            with self.assertRaisesRegex(PermissionError, "HERMETIC_GUARD"):
                subprocess.run(command, check=True)
        with self.assertRaisesRegex(PermissionError, "HERMETIC_GUARD"):
            os.system("aws sts get-caller-identity")

    def test_network_and_metadata_resolution_blocked(self):
        with self.assertRaisesRegex(PermissionError, "HERMETIC_GUARD"):
            socket.socket()
        with self.assertRaisesRegex(PermissionError, "HERMETIC_GUARD"):
            socket.getaddrinfo("169.254.169.254", 80)
