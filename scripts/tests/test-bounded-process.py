"""Real Linux process-group fixtures; no AWS or network."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

BOUNDARY = Path(__file__).resolve().parents[1] / "bounded-process.py"


def fixture(mode, directory):
    directory = Path(directory)
    label = mode if mode in ("child", "grandchild") else "leader"
    if mode in ("resistant", "child", "grandchild", "tree"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (directory / label).write_text(str(os.getpid()))
    if mode in ("orphan", "tree", "child"):
        descendant = "grandchild" if mode == "child" else "child"
        subprocess.Popen([sys.executable, __file__, "--fixture", descendant, str(directory)])
        # The marker proves SIG_IGN was installed before the parent can exit.
        while not (directory / "grandchild").exists() and mode != "child":
            time.sleep(0.01)
        if mode == "orphan":
            return
    if mode == "nested":
        subprocess.run([sys.executable, str(BOUNDARY), "10", sys.executable,
                        __file__, "--fixture", "child", str(directory)], check=False)
        return
    time.sleep(60)


@unittest.skipUnless(sys.platform == "linux", "requires Linux process-group semantics")
class HardBoundsTests(unittest.TestCase):
    def run_fixture(self, mode, expected):
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            try:
                result = subprocess.run(
                    [sys.executable, str(BOUNDARY), "2", sys.executable,
                     __file__, "--fixture", mode, directory],
                    capture_output=True, text=True, timeout=5,
                )
                self.assertLess(time.monotonic() - started, 4)
                self.assertIn(result.returncode, expected, result.stderr)
                self.assertTrue("timed out (TERM)" in result.stderr or
                                "forced process-group termination" in result.stderr, result.stderr)
                if mode in ("orphan", "tree", "nested"):
                    self.assertTrue((Path(directory) / "grandchild").exists())
                for path in Path(directory).iterdir():
                    proc = Path("/proc") / path.read_text() / "stat"
                    # Zombies awaiting PID 1 cannot execute or retain output.
                    until = time.monotonic() + 0.5
                    while proc.exists() and proc.read_text().split(") ")[1][0] != "Z" and time.monotonic() < until:
                        time.sleep(0.01)
                    self.assertTrue(not proc.exists() or proc.read_text().split(") ")[1][0] == "Z", path.name)
            finally:
                for path in Path(directory).iterdir():
                    try:
                        os.kill(int(path.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_cooperative_timeout(self):
        self.run_fixture("cooperative", (124,))

    def test_term_resistant(self):
        self.run_fixture("resistant", (137,))

    def test_orphan_holding_output_pipe(self):
        self.run_fixture("orphan", (137,))

    def test_surviving_child_and_grandchild(self):
        self.run_fixture("tree", (137,))

    def test_outer_budget_cleans_nested_observer_group(self):
        self.run_fixture("nested", (124, 137))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fixture":
        fixture(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
