#!/usr/bin/env python3
"""Guarded runner for the S3-P3B correction-03 observation probes.

The audit hook is installed **before** any product module or pytest is
imported.  It blocks every network connection and every host process
creation, so the probes cannot leave the offline boundary.  Plugin autoload,
the cache provider and bytecode writing are disabled as well.

The raw stdout and stderr streams and the actual process exit code are
written to disk; nothing is truncated and nothing is reconstructed.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-03/run_guarded_probe.py \
        --script reports/v0-s3/product-gate0/implementation-p3b-correction-03/replay_correction02_probes.py \
        --outdir reports/v0-s3/product-gate0/implementation-p3b-correction-03 \
        --label review-probe-replay
"""

import argparse
import hashlib
import io
import json
import os
import runpy
import sys


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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--candidate-sha", default="")
    arguments = parser.parse_args(argv)

    outdir = os.path.abspath(arguments.outdir)
    os.makedirs(outdir, exist_ok=True)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 0
    previous_out, previous_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_buffer, stderr_buffer
    try:
        runpy.run_path(os.path.abspath(arguments.script), run_name="__main__")
    except SystemExit as error:
        exit_code = int(error.code or 0)
    except BaseException as error:  # noqa: BLE001 - the failure must be recorded
        exit_code = 3
        import traceback
        traceback.print_exc(file=stderr_buffer)
    finally:
        sys.stdout, sys.stderr = previous_out, previous_err
        stdout_path = os.path.join(outdir, arguments.label + ".stdout.log")
        stderr_path = os.path.join(outdir, arguments.label + ".stderr.log")
        with open(stdout_path, "w", encoding="utf-8") as stream:
            stream.write(stdout_buffer.getvalue())
        with open(stderr_path, "w", encoding="utf-8") as stream:
            stream.write(stderr_buffer.getvalue())

    receipt = {
        "kind": "S3_P3B_CORRECTION_03_OBSERVATION_RECEIPT",
        "label": arguments.label,
        "script": os.path.relpath(os.path.abspath(arguments.script), PACK_ROOT),
        "command": [sys.executable, "-B", os.path.abspath(__file__),
                    "--script", arguments.script, "--outdir", arguments.outdir,
                    "--label", arguments.label, "--candidate-sha", arguments.candidate_sha],
        "candidate_sha": arguments.candidate_sha,
        "guard": {
            "installed_before_product_import": True,
            "audit_hook_events": list(BLOCKED_EVENTS),
            "pytest_disable_plugin_autoload": os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"),
            "bytecode_written": False,
            "network": "blocked",
            "host_subprocess": "blocked",
        },
        "exit_code": exit_code,
        "outcome": "PASS" if exit_code == 0 else "FAIL",
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
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
