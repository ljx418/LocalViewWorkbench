#!/usr/bin/env python3
"""The guarded runner of the S3-P4-OFFLINE integration batch.

The ``sys.addaudithook`` guard is installed **before** pytest, before any
plugin and before any product or test module is imported, so neither the
pytest startup, nor a plugin, nor a product import can open a socket, bind
a socket, resolve a name or start a host process.  Plugin autoload, the
cache provider and bytecode writing are disabled as well.

This runner lives in the new report subtree of this batch.  The original
P3B runner and the original P3B guard are unchanged.

The runner is the only executable that touches the product code of this
batch.  It never pipes a test stream, never masks an exit code and never
reconstructs a log: the raw stdout and stderr bytes are captured at the file
descriptor level and the true process exit code is written next to them.

Two modes exist:

``--mode guard``    the guard selftest.  It starts no process at all.
``--mode suite``    the committed integration suite of this batch.

The finite fixture process plan of the machine gate is *not* enabled by this
file.  It becomes active only when the root supplies a machine binding with
``--binding``; without that binding the guard blocks every process event.
The whitelist is read from the root binding and is never a monkeypatch of the
candidate code.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py \
        --mode suite --label integration-suite \
        --outdir reports/v0-s3/product-gate0/implementation-integration-01
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

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

SOURCE_FILES = (
    "tools/v0_s2_stage_runtime.py",
    "tools/v0_s2_runtime.py",
    "tools/v0_s3_quality_phase.py",
    "tools/v0_s3_coordinator.py",
    "tools/v0_s3_supervisor.py",
    "tools/v0_s3_quality_worker.py",
    "tools/test_v0_s3_integration.py",
    "tools/test_v0_s3_supervisor.py",
    "tools/fixtures/v0_s3_supervisor_fixture.py",
)
TEST_MODULES = (
    "tools/test_v0_s3_integration.py",
    "tools/test_v0_s3_supervisor.py",
)
RUNNER_RELATIVE = ("reports/v0-s3/product-gate0/implementation-integration-01/"
                    "run_guarded_checks.py")

# The machine gate is closed until the root supplies a binding.  The state is
# module level, because the audit hook has to see it.
PROCESS_GATE = {"binding": None, "starts": 0, "limit": 0, "allowed": []}


def _audit_hook(event, arguments):
    if event == "subprocess.Popen" and PROCESS_GATE["binding"] is not None:
        _gate_subprocess(arguments)
        return
    if event in BLOCKED_EVENTS:
        raise OfflineBoundaryViolation(
            "offline boundary violation: " + event + " " + repr(arguments))


def _gate_subprocess(arguments):
    """Allow exactly one bound fixture start of the root machine binding.

    The binding is a document of the root, not of the candidate.  The
    candidate cannot widen it: the argv has to be the frozen prefix plus one
    enumerated scenario, the count has to stay inside the shared budget and
    every other process event stays blocked.
    """
    binding = PROCESS_GATE["binding"]
    if PROCESS_GATE["starts"] >= PROCESS_GATE["limit"]:
        raise OfflineBoundaryViolation("fixture process budget exhausted")
    argv = list(arguments[1]) if len(arguments) > 1 and arguments[1] else []
    executable = arguments[0] if arguments else None
    prefix = list(binding.get("argv_prefix", []))
    scenarios = binding.get("allowed_scenarios", [])
    if not prefix or len(argv) != len(prefix) + 1:
        raise OfflineBoundaryViolation("fixture process is not in the machine binding")
    if argv[:len(prefix)] != prefix:
        raise OfflineBoundaryViolation("fixture process argv differs from the machine binding")
    if argv[len(prefix)] not in scenarios:
        raise OfflineBoundaryViolation("fixture scenario is not in the machine binding")
    if executable is not None and str(executable) != prefix[0]:
        raise OfflineBoundaryViolation("fixture executable is not the bound python")
    PROCESS_GATE["starts"] += 1
    return


sys.addaudithook(_audit_hook)

os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ.pop("PYTHONPYCACHEPREFIX", None)
sys.dont_write_bytecode = True


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


def imported_module_evidence():
    evidence = {}
    for name in ("tools.v0_s3_coordinator", "tools.v0_s3_supervisor",
                 "tools.v0_s3_quality_worker", "tools.v0_s3_quality_phase",
                 "tools.v0_s2_runtime", "tools.v0_s2_stage_runtime",
                 "tools.test_v0_s3_integration", "tools.test_v0_s3_supervisor"):
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


def load_machine_binding(path):
    """Read the root machine binding of the finite fixture process plan.

    Only a sealed binding of the root opens the gate.  A proposal of this
    batch is not a binding: its kind and its execution permission say so,
    and the runner refuses it.
    """
    if not path:
        return None
    binding_path = Path(path)
    if not binding_path.is_absolute():
        binding_path = PACK_ROOT / binding_path
    document = json.loads(binding_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SystemExit("machine binding is not an object")
    if document.get("kind") != "S3_INTEGRATION_MACHINE_BINDING/1":
        raise SystemExit("machine binding is not a sealed root binding")
    if document.get("execution_permitted") is not True:
        raise SystemExit("machine binding does not permit the fixture execution")
    limit = document.get("total_starts")
    if type(limit) is not int or limit < 0:
        raise SystemExit("machine binding has no finite start budget")
    executable = document.get("python", {}).get("path")
    if not isinstance(executable, str) or not executable:
        raise SystemExit("machine binding has no bound python")
    actual = sha256_file(executable)
    if actual != document["python"].get("sha256"):
        raise SystemExit("machine binding python digest drift")
    prefix = document.get("argv_prefix")
    scenarios = document.get("allowed_scenarios")
    if (not isinstance(prefix, list) or not prefix
            or not isinstance(scenarios, list) or not scenarios
            or any(not isinstance(item, str) or not item for item in scenarios)):
        raise SystemExit("machine binding command plan is malformed")
    if prefix[0] != executable:
        raise SystemExit("machine binding argv prefix is not the bound python")
    PROCESS_GATE["binding"] = document
    PROCESS_GATE["limit"] = limit
    PROCESS_GATE["allowed"] = scenarios
    return document


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["suite", "focused", "guard"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--select", default=None)
    parser.add_argument("--binding", default=None,
                        help="the root machine binding of the finite fixture plan")
    parser.add_argument("--modules", default=None,
                        help="a comma separated list of test modules of this pack")
    parser.add_argument("--candidate-sha", default="",
                        help="recorded as a claim only, never as an attestation")
    arguments = parser.parse_args(argv)

    binding = load_machine_binding(arguments.binding)
    if arguments.modules:
        test_modules = [item for item in arguments.modules.split(',') if item]
    else:
        test_modules = list(TEST_MODULES)

    outdir = Path(arguments.outdir)
    if not outdir.is_absolute():
        outdir = PACK_ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=True)
    stdout_path = outdir / (arguments.label + ".stdout.log")
    stderr_path = outdir / (arguments.label + ".stderr.log")

    before = source_hashes()
    runner_before = runner_hash()
    owned = Path(tempfile.mkdtemp(prefix="lvw-s3-integration-"))
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
        else:
            import pytest

            class Collection:
                def pytest_collection_finish(self, session):
                    collected.extend(item.nodeid for item in session.items)

            argv_pytest = list(test_modules) + ["-q", "-p", "no:cacheprovider",
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
        "kind": "S3_P4_OFFLINE_INTEGRATION_GUARDED_CHECK_RECEIPT",
        "label": arguments.label,
        "mode": arguments.mode,
        "select": arguments.select,
        "argv": list(sys.argv),
        "command": [sys.executable, "-B", str(Path(__file__).resolve()),
                    "--mode", arguments.mode, "--label", arguments.label,
                    "--outdir", str(outdir)],
        "candidate_sha_claim": arguments.candidate_sha,
        "candidate_sha_claim_is_attestation": False,
        "machine_binding": arguments.binding,
        "machine_binding_present": binding is not None,
        "fixture_process_starts": PROCESS_GATE["starts"],
        "fixture_process_limit": PROCESS_GATE["limit"],
        "before_source_sha256": before,
        "after_source_sha256": after,
        "source_unchanged_during_run": before == after,
        "runner_sha256_before": runner_before,
        "runner_sha256_after": runner_hash(),
        "runner_unchanged_during_run": runner_before == runner_hash(),
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
            "host_subprocess": "blocked" if binding is None else "bound_fixture_plan_only",
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
