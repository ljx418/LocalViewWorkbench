#!/usr/bin/env python3
"""The guarded runner of the S3-P4-OFFLINE integration batch.

The ``sys.addaudithook`` guard is installed **before** pytest, before any
plugin and before any product or test module is imported, so neither the
pytest startup, nor a plugin, nor a product import can open a socket, bind
a socket, resolve a name or start a host process.  Plugin autoload, the
cache provider and bytecode writing are disabled as well.

The guard has **one owner per process**.  It is installed by the production
bootstrap of this module, in the ``__main__`` guard, before pytest and
before any candidate import.  A plain import of this module - the module
alias that the tests use in order to call ``finalize_session`` and the other
helpers - never installs a hook and never owns a second gate: the alias
shares the registry, the gate and the owner of the production entry.  Two
guards in one process would be two gates, and the second one would veto
every admitted start of the first one.

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

GUARD_REGISTRY_MODULE = 'lvw_s3_offline_guard_registry'
# The contract of the executor: an exception that carries this attribute was
# raised by the guard inside the audit event of a process start.  That audit
# event is raised before the operating system action, so such a refusal is a
# proven position before the fork.
BEFORE_FORK_MARKER = 'lvw_before_fork'


def _violation_class():
    """Build the one violation class of this process.

    The class belongs to the process wide guard registry, so the production
    entry and every module alias of this file share the very same class: an
    alias can never raise a class that the production entry does not catch.
    """

    class OfflineBoundaryViolation(RuntimeError):
        """Raised when the offline boundary would be crossed."""

        def __init__(self, message, *, before_fork=False, code=None, gate_error=None):
            super().__init__(message)
            setattr(self, BEFORE_FORK_MARKER, bool(before_fork))
            self.before_fork = bool(before_fork)
            self.code = code
            self.gate_error = gate_error

    return OfflineBoundaryViolation


class _GuardRegistry:
    """The single, process wide owner of the offline guard.

    The registry holds the one gate of this process.  The production entry
    and every module alias of this file share it, so a second import never
    installs a second hook and never closes the gate of the production entry.
    """

    def __init__(self):
        self.owner_id = None
        self.hook_installed = False
        self.hook_install_count = 0
        self.install_attempts = 0
        self.installed_by = None
        self.installed_at = None
        self.violation_class = _violation_class()
        self.process_gate = {"executor": None, "starts": 0, "limit": 0, "allowed": []}
        self.refusals = []


def _guard_registry():
    """The registry of this process.  It is created once and then shared."""
    registry = sys.modules.get(GUARD_REGISTRY_MODULE)
    if registry is None:
        registry = _GuardRegistry()
        sys.modules[GUARD_REGISTRY_MODULE] = registry
    return registry


def guard_registry():
    """The public accessor of the one guard registry of this process."""
    return _guard_registry()


GUARD_REGISTRY = _guard_registry()
OfflineBoundaryViolation = GUARD_REGISTRY.violation_class
PROCESS_GATE = GUARD_REGISTRY.process_gate

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
# wall clock; the audit hook only asks it for an admission.  The gate itself
# belongs to the process wide guard registry, never to a module instance.


def finalize_session(*, executor, owned, stdout_handle, stderr_handle, saved_out,
                     saved_err, exit_code=0, failure_reasons=None, source_hasher=None,
                     remover=None, anchor_path=None):
    """The mandatory outer finalizer of the runner.

    The order is fixed and every step is guarded on its own:

    1. revoke the admissions of the session;
    2. restore the streams and close the log handles;
    3. reap and prove every owned child;
    4. hash the sources again;
    5. remove the owned root only after a proven cleanup, and verify the
       removal instead of ignoring a failure.

    The nested ``finally`` guarantees that the process reaper runs even when
    the restoration of a stream fails.  Any ordinary I/O failure of the
    finalizer keeps the root and the reservations and cannot retain exit 0.
    """
    failure_reasons = list(failure_reasons or [])
    cleanup_proven = True
    session_evidence = None
    session_spent = None
    notes = []
    proofs = []
    source_hasher = source_hasher or source_hashes
    remover = remover or shutil.rmtree

    def record(code, error=None):
        failure_reasons.append(code + (':' + type(error).__name__ if error else ''))

    try:
        try:
            if executor is not None:
                try:
                    executor.revoke_admissions()
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('ADMISSION_REVOKE_FAILED', error)
            steps = (
                ('STDOUT_FLUSH_FAILED', lambda: sys.stdout.flush()),
                ('STDERR_FLUSH_FAILED', lambda: sys.stderr.flush()),
                ('STDOUT_RESTORE_FAILED', lambda: os.dup2(saved_out, 1)),
                ('STDERR_RESTORE_FAILED', lambda: os.dup2(saved_err, 2)),
                ('STDOUT_CLOSE_FAILED', lambda: os.close(saved_out)),
                ('STDERR_CLOSE_FAILED', lambda: os.close(saved_err)),
                ('STDOUT_HANDLE_FLUSH_FAILED', lambda: stdout_handle.flush()),
                ('STDERR_HANDLE_FLUSH_FAILED', lambda: stderr_handle.flush()),
                ('STDOUT_HANDLE_CLOSE_FAILED', lambda: stdout_handle.close()),
                ('STDERR_HANDLE_CLOSE_FAILED', lambda: stderr_handle.close()),
            )
            for code, step in steps:
                try:
                    step()
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record(code, error)
        finally:
            if executor is not None:
                try:
                    proofs = executor.reap()
                    if any(not proof.get('proven') for proof in proofs):
                        cleanup_proven = False
                        record('CHILD_EXIT_UNPROVEN')
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('REAP_FAILED', error)
                # A charge that was admitted but never settled is not a proven
                # cleanup.  The run may not claim that everything was cleaned
                # up while a charge of this session is still open.
                unsettled = getattr(executor, 'unsettled_charges', None)
                if callable(unsettled):
                    try:
                        open_charges = unsettled()
                    except Exception as error:  # noqa: BLE001 - stays visible
                        cleanup_proven = False
                        record('CHARGE_LEDGER_FAILED', error)
                    else:
                        if open_charges:
                            cleanup_proven = False
                            record('UNSETTLED_CHARGE')
            after = None
            try:
                after = source_hasher()
            except Exception as error:  # noqa: BLE001 - the failure stays visible
                after = None
                cleanup_proven = False
                record('SOURCE_HASH_FAILED', error)
            if cleanup_proven:
                try:
                    remover(owned)
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('ROOT_REMOVAL_FAILED', error)
                else:
                    if Path(owned).exists():
                        cleanup_proven = False
                        record('ROOT_REMOVAL_INCOMPLETE')
            else:
                record('OWNED_ROOT_RETAINED')
            # The control anchor of the session exists from here on and is
            # removed only after a successful settlement.  It is the
            # diagnostic marker that a failed settlement leaves behind.
            anchor = None
            if anchor_path is not None:
                anchor = Path(anchor_path)
                try:
                    anchor.parent.mkdir(parents=True, exist_ok=True)
                    anchor.write_text(json.dumps({'kind': 'lvw.s3-settlement-anchor/1',
                                                  'session': getattr(executor, 'session_id', None),
                                                  'root': str(owned),
                                                  'stage_pass_claim': False},
                                                 sort_keys=True) + '\n', encoding='utf-8')
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('ANCHOR_WRITE_FAILED', error)
            # The settlement is the last accounting step: it happens after the
            # hash and the removal, so the global actual wall of the run
            # includes the whole cleanup work.
            if executor is not None:
                try:
                    spent = executor.settle_session()
                    if spent is None:
                        notes.append('SESSION_SETTLEMENT_ALREADY_APPLIED')
                    else:
                        session_spent = spent
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('SESSION_SETTLEMENT_FAILED', error)
                try:
                    # The evidence is captured after the settlement.
                    session_evidence = executor.session_evidence()
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    cleanup_proven = False
                    record('SESSION_EVIDENCE_FAILED', error)
                    session_evidence = {'kind': 'lvw.s3-finite-cpu-session/1',
                                         'status': 'EVIDENCE_FAILED',
                                         'error_type': type(error).__name__,
                                         'stage_pass_claim': False}
            if anchor is not None and anchor.exists() and not failure_reasons:
                try:
                    anchor.unlink()
                except Exception as error:  # noqa: BLE001 - the failure stays visible
                    record('ANCHOR_REMOVAL_FAILED', error)
    finally:
        if failure_reasons and exit_code == 0:
            exit_code = 4
    return {'exit_code': exit_code, 'cleanup_proven': cleanup_proven,
            'failure_reasons': sorted(set(failure_reasons)),
            'after_source_sha256': after, 'proofs': proofs,
            'session_evidence': session_evidence, 'session_spent': session_spent,
            'notes': sorted(set(notes))}


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
    """The one audit hook of this process.

    The hook reads the gate of the process wide registry, never a module
    local gate, so the production entry and a module alias of this file can
    never veto each other.
    """
    registry = _guard_registry()
    gate = registry.process_gate
    violation = registry.violation_class
    if event == "subprocess.Popen" and gate["executor"] is not None:
        try:
            gate["executor"].admit(arguments)
        except Exception as error:  # noqa: BLE001 - the refusal is the guard
            code = getattr(error, 'code', type(error).__name__)
            registry.refusals.append(code)
            # The audit event of a process start is raised before the
            # operating system action.  A refusal that is raised here is
            # therefore a proven position before the fork, and the executor
            # may settle the charge of this start as "not created".
            raise violation("finite cpu gate refused: " + str(code),
                            before_fork=True, code=code, gate_error=error)
        gate["starts"] += 1
        return
    if event in BLOCKED_EVENTS:
        raise violation(
            "offline boundary violation: " + event + " " + repr(arguments))


def install_offline_guard():
    """Install the global offline guard of this process, exactly once.

    The production bootstrap of this module calls it before pytest and before
    any candidate import.  The call is idempotent: a second import of this
    module - the module alias that the tests use - never installs a second
    hook and never owns a second gate.  The returned value is the owner of
    the one guard of this process; every call returns the same owner.
    """
    registry = _guard_registry()
    registry.install_attempts += 1
    if registry.hook_installed:
        return registry.owner_id
    registry.owner_id = 'owner-' + hashlib.sha256(
        str(Path(__file__).resolve()).encode('utf-8')).hexdigest()[:32]
    registry.hook_installed = True
    registry.hook_install_count += 1
    registry.installed_by = Path(__file__).resolve().name
    registry.installed_at = time.time()
    sys.addaudithook(_audit_hook)
    return registry.owner_id

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


def process_accounting(registry, session_evidence):
    """The process accounting of the run.

    Two numbers are different and are reported as two numbers: an *admitted
    attempt* is an admission that the audit hook granted, and a *proven child
    handle* is a child whose original handle the executor obtained and whose
    exit it proved.  A run in which every admission was refused never has a
    child, and it never presents its refusals as a proven cleanup.

    The legacy field ``fixture_process_starts`` keeps its value and its
    meaning: it counts the admitted attempts of the audit hook.  The
    semantics are stated next to it, so that the field is never read as a
    number of successful process starts.
    """
    gate = registry.process_gate
    evidence = session_evidence if isinstance(session_evidence, dict) else {}
    admitted = evidence.get('admitted_attempts')
    if not isinstance(admitted, int):
        admitted = int(gate.get('starts', 0))
    proven = evidence.get('proven_child_handles')
    if not isinstance(proven, int):
        proven = 0
    obtained = evidence.get('child_handles_obtained')
    if not isinstance(obtained, int):
        obtained = proven
    without_handle = evidence.get('charges_without_handle')
    if not isinstance(without_handle, list):
        without_handle = []
    return {
        "fixture_process_starts": admitted,
        "fixture_process_starts_semantics": (
            "the number of admitted audit hook attempts; it is NOT a number of "
            "created or successful process starts"),
        "admitted_attempts": admitted,
        "proven_child_handles": proven,
        "child_handles_obtained": obtained,
        "charges_without_handle": without_handle,
        "admission_refusals": {"count": len(registry.refusals),
                               "codes": list(registry.refusals)},
    }


def main(argv=None):
    # The guard of this process is installed before pytest and before any
    # candidate import, whatever the entry point is.  The installation is
    # idempotent: the production bootstrap of this module has already
    # installed it, and this call returns the owner of that one guard.
    install_offline_guard()
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
        # The mandatory outer finalizer.  It is exception safe: the process
        # reaper always runs, even when the restoration of the streams or the
        # removal of the root fails, and a failed finalization can never
        # retain exit 0.
        outcome = finalize_session(executor=executor, owned=owned,
                                  stdout_handle=stdout_handle, stderr_handle=stderr_handle,
                                  saved_out=saved_out, saved_err=saved_err,
                                  exit_code=exit_code, failure_reasons=failure_reasons,
                                  anchor_path=outdir / (arguments.label + '.settlement-anchor.json'))
        exit_code = outcome['exit_code']
        cleanup_proven = outcome['cleanup_proven']
        failure_reasons = outcome['failure_reasons']
        after = outcome['after_source_sha256']
        session_evidence = outcome['session_evidence']
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
        **process_accounting(GUARD_REGISTRY, session_evidence),
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
            "owner_id": GUARD_REGISTRY.owner_id,
            "hook_install_count": GUARD_REGISTRY.hook_install_count,
            "install_attempts": GUARD_REGISTRY.install_attempts,
            "installed_by": GUARD_REGISTRY.installed_by,
            "single_owner_gate": True,
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
    # The production bootstrap of this runner.  The global offline guard is
    # installed here, before pytest and before any candidate import.  The
    # installation is idempotent and it has exactly one owner per process:
    # a module alias of this file never installs a second hook.
    install_offline_guard()
    sys.exit(main())
