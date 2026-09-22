"""Linux runner boundary: a private process group, TERM then unconditional KILL.

Output is inherited, never drained through an unbounded communicate(). Cleanup
also runs when the leader exits first, so descendants cannot retain output pipes.
The grace interval is reserved *inside* the supplied remaining attempt budget.
"""
import math
import os
import signal
import subprocess
import sys
import time


def signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        return False


def main():
    budget = float(sys.argv[1])
    if not math.isfinite(budget) or budget <= 0 or os.name != "posix":
        raise ValueError("A positive finite budget and POSIX runner are required")
    deadline = time.monotonic() + budget
    grace = min(1.0, budget / 2)
    interrupted = False

    def cancelled(_signum, _frame):
        nonlocal interrupted
        interrupted = True
        # The enclosing gate budget owns this cancellation. Kill our separate
        # observer group immediately, before that enclosing supervisor escalates.
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, cancelled)
    process = None
    timed_out = False
    forced = False
    descendants = False
    try:
        process = subprocess.Popen(sys.argv[2:], start_new_session=True)
        try:
            process.wait(timeout=max(0, deadline - time.monotonic() - grace))
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if process is not None:
            # Even a successful leader may leave children holding output pipes.
            descendants = signal_group(process.pid, 0)
            if descendants and not interrupted:
                signal_group(process.pid, signal.SIGTERM)
                cleanup_deadline = min(deadline, time.monotonic() + grace)
                try:
                    process.wait(timeout=max(0, cleanup_deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
                # Do not cut descendants' cleanup short just because their
                # parent exited first (including nested observer supervisors).
                time.sleep(max(0, cleanup_deadline - time.monotonic()))
            forced = signal_group(process.pid, signal.SIGKILL)
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                forced = True

    if forced:
        print("External call required forced process-group termination.", file=sys.stderr)
        return 137
    if timed_out:
        print("External call timed out (TERM).", file=sys.stderr)
        return 124
    if descendants:
        print("External call left descendants requiring cleanup.", file=sys.stderr)
        return 125
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


if __name__ == "__main__":
    sys.exit(main())
