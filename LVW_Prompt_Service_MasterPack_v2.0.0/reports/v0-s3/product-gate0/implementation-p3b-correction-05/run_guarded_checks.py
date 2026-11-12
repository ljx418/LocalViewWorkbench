#!/usr/bin/env python3
"""Guarded runner for the S3-P3B aggregate correction-05 checks.

The ``sys.addaudithook`` guard is installed **before** pytest, before any
plugin and before any product or test module is imported, so neither the
pytest CLI startup nor a plugin nor a product import can open a socket, bind
a socket, resolve a name or start a host process.  Plugin autoload, the
cache provider and bytecode writing are disabled as well.

The runner is the only executable that touches the product code in this
batch.  It never pipes a test stream, never masks an exit code and never
reconstructs a log: the raw stdout and stderr bytes are captured at the file
descriptor level and the true process exit code is written next to them.

Every invocation pins the hash of the runner itself, of the probe script and
of every bound source file *before and after* the run, records the actual
imported module paths and hashes, the raw stream hashes and sizes, the exact
argv, the true exit code and the removal of the owned temporary fixture root.

A ``--candidate-sha`` argument is recorded as a claim only; it is never
accepted as a source attestation.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py \
        --mode suite --label full-final --outdir reports/v0-s3/product-gate0/implementation-p3b-correction-05

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py \
        --mode script --label counterexamples --script reports/v0-s3/product-gate0/implementation-p3b-correction-05/probe_correction05_counterexamples.py
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path


class OfflineBoundaryViolation(RuntimeError):
    """Raised when the offline boundary would be crossed."""


BLOCKED_EVENTS = (
    "socket.connect",
    "socket.connect_ex",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyaddr",
    "socket.getnameinfo",
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


# The guard is installed before pytest and before any project import.
sys.addaudithook(_audit_hook)

os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ.pop("PYTHONPYCACHEPREFIX", None)
sys.dont_write_bytecode = True

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

SOURCE_FILES = (
    "tools/v0_s3_quality_phase.py",
    "tools/test_v0_s3_quality_phase.py",
)
TEST_MODULE = "tools/test_v0_s3_quality_phase.py"
RUNNER_RELATIVE = "reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes():
    return {relative: sha256_file(PACK_ROOT / relative) for relative in SOURCE_FILES}


def runner_hash():
    return sha256_file(Path(__file__).resolve())


def probe_hash(script):
    if not script:
        return None
    path = Path(script)
    if not path.is_absolute():
        path = PACK_ROOT / script
    if not path.is_file():
        return None
    return sha256_file(path)


def imported_module_evidence():
    """The path and the hash of the module that was really imported."""
    evidence = {}
    for name in ("tools.v0_s3_quality_phase", "tools.test_v0_s3_quality_phase",
                 "test_v0_s3_quality_phase"):
        module = sys.modules.get(name)
        if module is None:
            continue
        location = getattr(module, "__file__", None)
        record = {"module": name, "path": location}
        if location and Path(location).is_file():
            record["sha256"] = sha256_file(Path(location))
        evidence[name] = record
    return evidence


def run_guard_selftest():
    """Four audit events, blocked before any product code exists."""
    import socket
    import subprocess
    results = {}

    def attempt(name, function):
        try:
            function()
            results[name] = "NOT_BLOCKED"
        except OfflineBoundaryViolation as error:
            results[name] = str(error)

    def connect():
        with socket.socket() as handle:
            handle.connect(("127.0.0.1", 9))

    def bind():
        with socket.socket() as handle:
            handle.bind(("127.0.0.1", 0))

    attempt("connect", connect)
    attempt("bind", bind)
    attempt("Popen", lambda: subprocess.Popen(["/bin/true"]))
    attempt("system", lambda: os.system("true"))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True,
                        choices=["suite", "focused", "guard", "script"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--select", default=None,
                        help="a -k expression for the focused mode")
    parser.add_argument("--script", default=None,
                        help="a python file for the script mode")
    parser.add_argument("--candidate-sha", default="",
                        help="recorded as a claim only, never as an attestation")
    arguments = parser.parse_args(argv)

    outdir = Path(arguments.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    stdout_path = outdir / (arguments.label + ".stdout.log")
    stderr_path = outdir / (arguments.label + ".stderr.log")

    before = source_hashes()
    runner_before = runner_hash()
    probe_before = probe_hash(arguments.script)
    owned = Path(tempfile.mkdtemp(prefix="lvw-c05-" + arguments.label + "-"))
    os.environ["TMPDIR"] = str(owned)
    tempfile.tempdir = str(owned)

    started = time.time()
    exit_code = 0
    collected = []
    guard_results = None
    stdout_handle = open(stdout_path, "wb")
    stderr_handle = open(stderr_path, "wb")
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    os.dup2(stdout_handle.fileno(), 1)
    os.dup2(stderr_handle.fileno(), 2)
    try:
        if arguments.mode == "guard":
            guard_results = run_guard_selftest()
            sys.stdout.write(json.dumps(guard_results, indent=2, sort_keys=True) + "\n")
            sys.stdout.flush()
            exit_code = 0 if len(guard_results) == 4 and all(
                value != "NOT_BLOCKED" for value in guard_results.values()) else 1
        elif arguments.mode == "script":
            import runpy
            runpy.run_path(str(Path(arguments.script).resolve()), run_name="__main__")
        else:
            import pytest

            class Collection:
                def pytest_collection_finish(self, session):
                    collected.extend(item.nodeid for item in session.items)

            argv_pytest = [TEST_MODULE, "-q", "-p", "no:cacheprovider",
                           "--no-header", "-rN",
                           "--basetemp", str(owned / "pytest")]
            if arguments.mode == "focused":
                if not arguments.select:
                    raise SystemExit("the focused mode requires --select")
                argv_pytest += ["-k", arguments.select]
            exit_code = int(pytest.main(argv_pytest, plugins=[Collection()]))
    except SystemExit as error:
        exit_code = int(error.code or 0)
    except BaseException:  # noqa: BLE001 - the failure must be recorded
        exit_code = 3
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        stdout_handle.close()
        stderr_handle.close()
        shutil.rmtree(owned, ignore_errors=True)

    after = source_hashes()
    receipt = {
        "kind": "S3_P3B_CORRECTION_05_GUARDED_CHECK_RECEIPT",
        "label": arguments.label,
        "mode": arguments.mode,
        "select": arguments.select,
        "script": arguments.script,
        "argv": list(sys.argv),
        "command": [sys.executable, "-B", str(Path(__file__).resolve()),
                    "--mode", arguments.mode, "--label", arguments.label,
                    "--outdir", str(outdir)],
        "candidate_sha_claim": arguments.candidate_sha,
        "candidate_sha_claim_is_attestation": False,
        "before_source_sha256": before,
        "after_source_sha256": after,
        "source_unchanged_during_run": before == after,
        "runner_sha256_before": runner_before,
        "runner_sha256_after": runner_hash(),
        "runner_unchanged_during_run": runner_before == runner_hash(),
        "probe_sha256_before": probe_before,
        "probe_sha256_after": probe_hash(arguments.script),
        "probe_unchanged_during_run": probe_before == probe_hash(arguments.script),
        "imported_modules": imported_module_evidence(),
        "collected_nodeids": collected,
        "collected_count": len(collected),
        "guard_results": guard_results,
        "guard": {
            "audit_hook_installed_before_pytest": True,
            "audit_hook_installed_before_product_import": True,
            "blocked_events": list(BLOCKED_EVENTS),
            "pytest_disable_plugin_autoload": os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"),
            "cacheprovider": "disabled",
            "bytecode_written": False,
            "network": "blocked",
            "host_subprocess": "blocked",
        },
        "owned_root_removed": not owned.exists(),
        "duration_seconds": round(time.time() - started, 3),
        "exit_code": exit_code,
        "outcome": "PASS" if exit_code == 0 else "FAIL",
        "stdout_file": str(stdout_path.relative_to(PACK_ROOT)),
        "stderr_file": str(stderr_path.relative_to(PACK_ROOT)),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "stdout_bytes": stdout_path.stat().st_size,
        "stderr_bytes": stderr_path.stat().st_size,
        "stage_pass_claim": False,
        "product_gate0": False,
        "real_execution_performed": False,
    }
    receipt_path = outdir / (arguments.label + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
    sys.stdout.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
