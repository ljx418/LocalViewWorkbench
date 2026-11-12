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
import importlib.util
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
REPOSITORY_ROOT = PACK_ROOT.parent
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
    "reports/v0-s3/product-gate0/implementation-integration-01/executor.py",
)
TEST_MODULES = (
    "tools/test_v0_s3_integration.py",
    "tools/test_v0_s3_supervisor.py",
)
RUNNER_RELATIVE = ("reports/v0-s3/product-gate0/implementation-integration-01/"
                    "run_guarded_checks.py")
EXECUTOR_RELATIVE = ("reports/v0-s3/product-gate0/implementation-integration-01/"
                      "executor.py")

# The machine gate is closed until the root supplies a sealed binding.  The
# independent executor owns the shared budget, the source identity and the
# wall clock; the audit hook only asks it for an admission.
PROCESS_GATE = {"executor": None, "starts": 0, "limit": 0, "allowed": []}


def session_identity(role, label, candidate_sha):
    """A stable session identity: the same session never reserves twice."""
    raw = ('%s|%s|%s' % (role, label, candidate_sha)).encode('utf-8')
    return 'session-' + hashlib.sha256(raw).hexdigest()[:32]


def _load_executor_module():
    """Load the independent executor of this report subtree."""
    path = PACK_ROOT / EXECUTOR_RELATIVE
    spec = importlib.util.spec_from_file_location("lvw_s3_finite_cpu_executor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _audit_hook(event, arguments):
    if event == "subprocess.Popen" and PROCESS_GATE["executor"] is not None:
        try:
            PROCESS_GATE["executor"].admit(arguments)
        except Exception as error:  # noqa: BLE001 - the refusal is the guard
            code = getattr(error, 'code', type(error).__name__)
            raise OfflineBoundaryViolation("finite cpu gate refused: " + str(code))
        PROCESS_GATE["starts"] += 1
        return
    if event in BLOCKED_EVENTS:
        raise OfflineBoundaryViolation(
            "offline boundary violation: " + event + " " + repr(arguments))


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


def load_machine_binding(path, expected_sha256):
    """Read the sealed root binding of the finite fixture process plan.

    The issuer proof is the absolute path *and* the digest that the root
    supplied out of band.  A document of the same kind that the root did not
    seal is not issuer proof: it is refused.
    """
    if not path:
        return None
    binding_path = Path(path)
    if not binding_path.is_absolute():
        raise SystemExit("machine binding path must be absolute")
    if not expected_sha256:
        raise SystemExit("machine binding needs the root supplied digest")
    if not binding_path.is_file():
        raise SystemExit("machine binding file is missing")
    actual = sha256_file(binding_path)
    if actual != expected_sha256:
        raise SystemExit("machine binding digest drift")
    document = json.loads(binding_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise SystemExit("machine binding is not an object")
    if document.get("kind") != "S3_INTEGRATION_MACHINE_BINDING/1":
        raise SystemExit("machine binding is not a sealed root binding")
    if document.get("execution_permitted") is not True:
        raise SystemExit("machine binding does not permit the fixture execution")
    return document


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["suite", "focused", "guard"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--select", default=None)
    parser.add_argument("--binding", default=None,
                        help="the absolute path of the sealed root machine binding")
    parser.add_argument("--binding-sha256", default=None,
                        help="the digest of the sealed root binding, supplied by the root")
    parser.add_argument("--role", default=None,
                        choices=["implementation", "independent_review"],
                        help="the role of this session in the shared budget")
    parser.add_argument("--modules", default=None,
                        help="a comma separated list of test modules of this pack")
    parser.add_argument("--candidate-sha", default="",
                        help="recorded as a claim only, never as an attestation")
    arguments = parser.parse_args(argv)

    binding = load_machine_binding(arguments.binding, arguments.binding_sha256)
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

    owned = Path(tempfile.mkdtemp(prefix="lvw-s3-integration-"))
    os.environ["TMPDIR"] = str(owned)
    tempfile.tempdir = str(owned)
    # The fresh runner owned root is the only place where the bounded
    # context document of a fixture scenario may live.
    os.environ["LVW_S3_GUARD_ROOT"] = str(owned)

    executor = None
    executor_module = _load_executor_module()
    started = time.time()
    exit_code = 0
    collected = []
    guard_results = None
    before = None
    after = None
    runner_before = None
    session_evidence = None
    cleanup_proven = True
    failure_reasons = []
    stdout_handle = open(stdout_path, "wb")
    stderr_handle = open(stderr_path, "wb")
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    os.dup2(stdout_handle.fileno(), 1)
    os.dup2(stderr_handle.fileno(), 2)
    try:
        before = source_hashes()
        runner_before = runner_hash()
        if binding is not None:
            if not arguments.role:
                raise SystemExit("the machine gate needs the role of this session")
            executor = executor_module.build_executor(
                binding_path=arguments.binding, binding_sha256=arguments.binding_sha256,
                role=arguments.role, repository_root=REPOSITORY_ROOT,
                package_root=PACK_ROOT, guard_root=owned,
                session_id=session_identity(arguments.role, arguments.label,
                                            binding.get('candidate_sha')))
            sys.modules.setdefault('lvw_s3_finite_cpu_executor', executor_module)
            executor_module.EXECUTOR = executor
            os.environ['LVW_S3_MACHINE_BINDING'] = str(arguments.binding)
            PROCESS_GATE["executor"] = executor
            PROCESS_GATE["limit"] = executor.limits['max_total_starts']
            PROCESS_GATE["allowed"] = list(binding.get("allowed_scenarios", []))
            # The slice of the shared wall pool is reserved before the first
            # child.  A nearly exhausted pool refuses the session here, before
            # any operating system action.
            executor.reserve_session()
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
        # The mandatory outer finalizer.  The order is fixed: revoke the
        # admissions, restore the streams, reap and prove every owned child,
        # then hash the sources again, and only a proven cleanup deletes the
        # owned root.  An uncertain child keeps its root and its reservation.
        if executor is not None:
            try:
                executor.revoke_admissions()
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                cleanup_proven = False
                failure_reasons.append('ADMISSION_REVOKE_FAILED:' + type(error).__name__)
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        stdout_handle.close()
        stderr_handle.close()
        if executor is not None:
            try:
                proofs = executor.reap()
                executor.settle_session()
                session_evidence = executor.session_evidence()
                if any(not proof.get('proven') for proof in proofs):
                    cleanup_proven = False
                    failure_reasons.append('CHILD_EXIT_UNPROVEN')
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                cleanup_proven = False
                failure_reasons.append('REAP_FAILED:' + type(error).__name__)
                session_evidence = {'kind': 'lvw.s3-finite-cpu-session/1',
                                     'status': 'REAP_FAILED',
                                     'error_type': type(error).__name__,
                                     'stage_pass_claim': False}
        try:
            after = source_hashes()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            after = None
            cleanup_proven = False
            failure_reasons.append('SOURCE_HASH_FAILED:' + type(error).__name__)
        if cleanup_proven:
            shutil.rmtree(owned, ignore_errors=True)
        else:
            failure_reasons.append('OWNED_ROOT_RETAINED')
        if failure_reasons and exit_code == 0:
            exit_code = 4
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
        "machine_binding_sha256": arguments.binding_sha256,
        "machine_binding_present": binding is not None,
        "session_role": arguments.role,
        "fixture_process_starts": PROCESS_GATE["starts"],
        "fixture_process_limit": PROCESS_GATE["limit"],
        "executor_session": session_evidence,
        "guard_root": str(owned),
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
        "cleanup_proven": cleanup_proven,
        "failure_reasons": sorted(set(failure_reasons)),
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
