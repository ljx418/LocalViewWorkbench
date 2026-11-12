#!/usr/bin/env python3
"""Guarded offline runner for the S3-P3B quality acceptance checks.

The audit hook below is installed **before** pytest is imported, so the guard
covers plugin import and collection as well as the test bodies.  It blocks
every network connection and every host process creation; the offline quality
tests need none of them, so a blocked event is a genuine boundary violation
and not a tolerated side effect.

The runner writes the raw stdout and stderr streams and the actual pytest
exit code to disk.  It never truncates a stream and never reports a success
that did not happen.  The process exit code is the pytest exit code.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py \
        --outdir reports/v0-s3/product-gate0/implementation-p3b \
        --label qd-directed --select "tools/test_v0_s3_quality_phase.py::QualityExecution"
"""

import argparse
import hashlib
import io
import json
import os
import sys

# --------------------------------------------------------------------------
# The guard is installed before pytest and before any project import.
# --------------------------------------------------------------------------
class OfflineBoundaryViolation(RuntimeError):
    """Raised when the offline boundary would be crossed."""


BLOCKED_EVENTS = (
    "socket.connect",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.spawn",
    "os.posix_spawn",
    "os.fork",
    "os.forkpty",
)


def _audit_hook(event, arguments):
    if event in BLOCKED_EVENTS:
        raise OfflineBoundaryViolation(
            "offline boundary violation: " + event + " " + repr(arguments))


sys.addaudithook(_audit_hook)

os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ.pop("PYTHONPYCACHEPREFIX", None)

PACK_ROOT = __file__.split(os.sep + "reports" + os.sep)[0]
if PACK_ROOT and PACK_ROOT not in sys.path:
    sys.path.insert(0, PACK_ROOT)


def sha256_file(path):
    with open(path, "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def guard_selftest(outdir, label, candidate_sha):
    """Prove that the audit hook really blocks the offline boundary.

    A guard that is never exercised is decoration.  This mode attempts one
    loopback connect, one host child process and one shell call and records
    the actual outcome of each attempt.
    """
    import socket
    import subprocess

    outcomes = {}

    def attempt(name, action):
        try:
            action()
            outcomes[name] = "NOT_BLOCKED"
        except OfflineBoundaryViolation as error:
            outcomes[name] = "BLOCKED"
            outcomes[name + "_detail"] = str(error)
        except Exception as error:  # noqa: BLE001 - the real outcome is recorded
            outcomes[name] = "OTHER:" + type(error).__name__

    def connect():
        handle = socket.socket()
        try:
            handle.connect(("127.0.0.1", 9))
        finally:
            handle.close()

    attempt("socket_connect", connect)
    attempt("socket_bind", lambda: socket.socket().bind(("127.0.0.1", 0)))
    attempt("subprocess_popen", lambda: subprocess.Popen(["/bin/true"]).wait())
    attempt("os_system", lambda: os.system("true"))

    blocked = all(outcomes.get(name) == "BLOCKED" for name in
                  ("socket_connect", "socket_bind", "subprocess_popen", "os_system"))
    receipt = {
        "kind": "S3_P3B_OFFLINE_GUARD_SELFTEST",
        "label": label,
        "candidate_sha": candidate_sha,
        "installed_before_pytest_import": True,
        "audit_hook_events": list(BLOCKED_EVENTS),
        "outcomes": outcomes,
        "guard_effective": blocked,
        "stage_pass_claim": False,
        "product_gate0": False,
        "real_execution_performed": False,
    }
    path = os.path.join(outdir, label + ".guard-selftest.json")
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0 if blocked else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--testpath", default="tools/test_v0_s3_quality_phase.py")
    parser.add_argument("--select", default="")
    parser.add_argument("--guard-selftest", action="store_true")
    arguments = parser.parse_args(argv)

    outdir = os.path.abspath(arguments.outdir)
    os.makedirs(outdir, exist_ok=True)

    if arguments.guard_selftest:
        return guard_selftest(outdir, arguments.label, arguments.candidate_sha)

    import pytest  # imported only after the audit hook is active

    command = [sys.executable, "-B", os.path.abspath(__file__),
               "--outdir", arguments.outdir, "--label", arguments.label,
               "--candidate-sha", arguments.candidate_sha,
               "--testpath", arguments.testpath, "--select", arguments.select]
    pytest_arguments = [arguments.testpath, "-q", "-p", "no:cacheprovider",
                         "--no-header", "-rN"]
    if arguments.select:
        pytest_arguments += ["-k", arguments.select]

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = None
    outcome = "UNKNOWN"
    try:
        previous_out, previous_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout_buffer, stderr_buffer
        try:
            exit_code = int(pytest.main(pytest_arguments))
            outcome = "PASS" if exit_code == 0 else "FAIL"
        except BaseException as error:  # noqa: BLE001 - the failure must be recorded
            exit_code = 3
            outcome = "ERROR"
            traceback_text = io.StringIO()
            import traceback
            traceback.print_exc(file=traceback_text)
            stderr_buffer.write(traceback_text.getvalue())
        finally:
            sys.stdout, sys.stderr = previous_out, previous_err
    finally:
        stdout_path = os.path.join(outdir, arguments.label + ".stdout.log")
        stderr_path = os.path.join(outdir, arguments.label + ".stderr.log")
        with open(stdout_path, "w", encoding="utf-8") as stream:
            stream.write(stdout_buffer.getvalue())
        with open(stderr_path, "w", encoding="utf-8") as stream:
            stream.write(stderr_buffer.getvalue())

    receipt = {
        "kind": "S3_P3B_OFFLINE_CHECK_RECEIPT",
        "label": arguments.label,
        "command": command,
        "pytest_arguments": pytest_arguments,
        "candidate_sha": arguments.candidate_sha,
        "guard": {
            "installed_before_pytest_import": True,
            "audit_hook_events": list(BLOCKED_EVENTS),
            "pytest_disable_plugin_autoload": os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"),
            "bytecode_written": False,
            "cache_provider": "disabled",
            "network": "blocked",
            "host_subprocess": "blocked",
        },
        "exit_code": exit_code,
        "outcome": outcome,
        "stdout_file": os.path.relpath(stdout_path, PACK_ROOT),
        "stderr_file": os.path.relpath(stderr_path, PACK_ROOT),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "stdout_bytes": os.path.getsize(stdout_path),
        "stderr_bytes": os.path.getsize(stderr_path),
        "stage_pass_claim": False,
        "product_gate0": False,
        "real_execution_performed": False,
    }
    receipt_path = os.path.join(outdir, arguments.label + ".receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0 if exit_code == 0 else (exit_code if isinstance(exit_code, int) and exit_code > 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
