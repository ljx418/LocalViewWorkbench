"""The directed composition tests of the S3-P4 production composition 01.

The suite is offline and it creates no operating system child process.

The hard guard is installed *before* the candidate is imported, so neither
the candidate nor a plugin can open a socket, start a host process, fork,
exec, call ``system`` or open a database.  The guard counts every attempt,
so a test can state that the boundary was never crossed.

The composition itself drives the *production* path: the formal controller,
the formal worker entry, the real ``WorkerContext``, the real
``QualityPhase`` with its sixteen rows, the real protocol writer over a
real pipe, the real parent reader, the real canonical receipt, the real
parent original evidence and the real twelve key aggregation.  Only the
native driver construction, the child process and the clock are replaced, and
they are replaced by an explicit in-process seam.

Every receipt of this suite is labelled as an offline synthetic fact.  None
of them is a product pass, a stage pass or a gate.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


# --------------------------------------------------------------------------
# the hard offline guard, installed before any candidate import
# --------------------------------------------------------------------------
class OfflineGuardError(RuntimeError):
    """Raised when a test tries to leave the offline boundary."""


GUARD_ATTEMPTS = []


def _blocked(name):
    def refuse(*args, **kwargs):
        GUARD_ATTEMPTS.append(name)
        raise OfflineGuardError('the offline boundary blocks ' + name)
    return refuse


def _install_guard():
    """Block every way out of the offline boundary.

    The guard is independent of the guard of any other suite: it is
    installed again after the reuse of the shared test data, so the
    candidate import and the composition always run under this guard.
    """
    for name in ('Popen', 'run', 'call', 'check_call', 'check_output'):
        setattr(subprocess, name, _blocked('subprocess.' + name))
    for name in ('system', 'popen', 'fork', 'forkpty'):
        if hasattr(os, name):
            setattr(os, name, _blocked('os.' + name))
    for name in ('execv', 'execve', 'execvp', 'execvpe', 'execl', 'execle',
                 'execlp', 'execlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe'):
        if hasattr(os, name):
            setattr(os, name, _blocked('os.' + name))
    socket.socket.connect = _blocked('socket.connect')
    socket.socket.connect_ex = _blocked('socket.connect_ex')
    socket.socket.bind = _blocked('socket.bind')
    socket.create_connection = _blocked('socket.create_connection')
    socket.getaddrinfo = _blocked('socket.getaddrinfo')
    sqlite3.connect = _blocked('sqlite3.connect')


_install_guard()

import pytest  # noqa: E402  (imported only after the offline guard is active)

from tools import v0_s3_production_controller as controller  # noqa: E402

RUN_ID = 's3-p4-composition-01'
CANDIDATE_SHA = 'a' * 40
AUTHORIZATION_SHA = 'b' * 64
DEPENDENCY_MANIFEST_SCHEMA = 'lvw.s3-dependency-path-manifest/1'
DEPENDENCY_MANIFEST_SCOPE = 'named_files_only_not_a_transitive_seal'
PARENT_PROOF_KIND = 'LVW_PARENT_CAPACITY_PROOF/1'
MAX_PROVIDER_CALLS = 34

_HELPERS = None


def _helpers():
    """The reused test data of the accepted quality phase suite.

    The synthetic driver, the synthetic sources and the projection builder
    of the accepted suite are reused as they are: this suite does not
    build a second copy of them and it does not copy the production phase.
    """
    global _HELPERS
    if _HELPERS is None:
        from tools import test_v0_s3_quality_phase as helpers
        _HELPERS = helpers
        # The reused module installs its own guard; this suite installs its
        # own guard again, so the boundary that counts the attempts is the
        # independent one of this file.
        _install_guard()
    return _HELPERS


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest_of(path):
    return _digest(Path(path).read_bytes())


def _write_json(path, document):
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    path.write_bytes(raw)
    return raw


class Composition:
    """The sealed documents of one offline composition."""

    def __init__(self, root):
        self.root = Path(root)
        self.documents = {}

    def write(self, name, document):
        path = self.root / 'contexts' / (name + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _write_json(path, document)
        self.documents[name] = {'path': str(path), 'sha256': _digest(raw)}
        return path


def _build_composition(tmp_path, *, name='run', driver_failure=None,
                        mutate_worker=None, mutate_projection=None,
                        projection_bytes=None):
    """Build the sealed documents of one composition.

    The sixteen sources, the projection, the source identity, the binding
    and the synthetic driver come from the accepted quality phase suite.
    Everything else - the worker context, the controller context and the
    admission record - is the closed document of this package.
    """
    helpers = _helpers()
    root = tmp_path / name
    for sub in ('input', 'output', 'temp'):
        (root / sub).mkdir(parents=True, exist_ok=True)
    rows = helpers._build_sources(root)
    projection = projection_bytes if projection_bytes is not None else helpers._projection_bytes(rows)
    if mutate_projection is not None:
        projection = mutate_projection(projection)
    projection_path = root / 'temp' / 'projection.json'
    projection_path.write_bytes(projection)
    projection_sha = _digest(projection)

    source_identity = helpers._source_identity()
    source_identity_path = root / 'contexts' / 'source-identity.json'
    source_identity_path.parent.mkdir(parents=True, exist_ok=True)
    source_identity_raw = _write_json(source_identity_path, source_identity)

    now = time.monotonic()
    parent_budget = {
        'kind': PARENT_PROOF_KIND,
        'known': True,
        'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA,
        'authorization_sha256': AUTHORIZATION_SHA,
        'issued_monotonic': float(now),
        'expires_monotonic': float(now) + 3600.0,
        'action_capacity': MAX_PROVIDER_CALLS,
    }
    parent_budget_path = root / 'contexts' / 'parent-budget.json'
    parent_budget_raw = _write_json(parent_budget_path, parent_budget)

    binding = helpers._binding()
    binding_path = root / 'contexts' / 'binding.json'
    binding_raw = _write_json(binding_path, binding)

    workflow_dir = helpers.WORKFLOW_DIR
    manifest = {
        'schema': DEPENDENCY_MANIFEST_SCHEMA,
        'scope': DEPENDENCY_MANIFEST_SCOPE,
        'path': str(workflow_dir),
        'files': [{'path': str(workflow_dir / name), 'sha256': _digest_of(workflow_dir / name)}
                  for name in (helpers.IMAGE_WORKFLOW, helpers.VIDEO_WORKFLOW)],
    }
    manifest_path = root / 'contexts' / 'dependency-manifest.json'
    manifest_raw = _write_json(manifest_path, manifest)

    worker_context = {
        'schema': 'lvw.s3-quality-worker-context/1',
        'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA,
        'authorization_sha256': AUTHORIZATION_SHA,
        'root': str(root),
        'projection_path': str(projection_path),
        'projection_sha256': projection_sha,
        'source_identity_path': str(source_identity_path),
        'source_identity_sha256': _digest(source_identity_raw),
        'parent_budget_path': str(parent_budget_path),
        'parent_budget_sha256': _digest(parent_budget_raw),
        'binding_path': str(binding_path),
        'binding_sha256': _digest(binding_raw),
        'driver': 'fixture',
        'driver_arguments': {
            'powershell': 'C:/offline-boundary/powershell.exe',
            'comfy_main': 'C:/offline-boundary/comfy/main.py',
            'comfy_python': 'C:/offline-boundary/comfy/python.exe',
            'ollama_exe': 'C:/offline-boundary/ollama.exe',
            'ffmpeg_exe': 'C:/offline-boundary/ffmpeg.exe',
            'nvidia_exe': 'C:/offline-boundary/nvidia-smi.exe',
        },
        'dependency_manifest_path': str(manifest_path),
        'dependency_manifest_sha256': _digest(manifest_raw),
        'canonical_receipt_reference': 'temp/s3-quality/qd-receipt.json',
    }
    if mutate_worker is not None:
        worker_context = mutate_worker(worker_context)
    composition = Composition(root)
    worker_context_path = composition.write('worker-context', worker_context)

    admission = {
        'kind': controller.NATIVE_ADMISSION_KIND,
        'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA,
        'authorization_sha256': AUTHORIZATION_SHA,
        'model_digest': 'f' * 64,
        'authority_root': str(root / 'authority'),
        'ledger_path': str(root / 'authority' / 'original.sqlite'),
        'admission_references': {name: {'path': str(root / 'missing' / (name + '.json')),
                                        'sha256': '0' * 64}
                                 for name in controller.ADMISSION_REFERENCE_KEYS},
    }
    admission_path = composition.write('admission', admission)

    controller_context = {
        'schema': controller.CONTROLLER_CONTEXT_SCHEMA,
        'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA,
        'authorization_sha256': AUTHORIZATION_SHA,
        'root': str(root),
        'worker_context': {'path': str(worker_context_path),
                           'sha256': _digest_of(worker_context_path)},
        'admission': {'path': str(admission_path), 'sha256': _digest_of(admission_path)},
        'quality_scores': {'path': None, 'sha256': None},
        'independence': {'path': None, 'sha256': None},
    }
    controller_context_path = composition.write('controller-context', controller_context)

    return {'root': root,
            'rows': rows,
            'projection': projection,
            'worker_context_path': worker_context_path,
            'worker_context_sha256': _digest_of(worker_context_path),
            'controller_context_path': controller_context_path,
            'composition': composition,
            'driver_failure': driver_failure}


def _controller_context(path):
    return controller.ControllerContext.load(path)


def _seam(composition, *, fault='none', on_transition=None):
    helpers = _helpers()
    failure = composition['driver_failure']

    def driver_factory(context):
        return helpers.SyntheticDriver(Path(context.document['root']), failure)

    seam = controller.OfflineCompositionSeam(
        driver_factory=driver_factory,
        context_sha256=composition['worker_context_sha256'],
        fault=fault)
    seam.on_transition = on_transition
    return seam


def _run_composition(composition, *, fault='none', on_transition=None, context_path=None):
    context = _controller_context(context_path or composition['controller_context_path'])
    seam = _seam(composition, fault=fault, on_transition=on_transition)
    instance = controller.ProductionController(context, seam=seam)
    return instance.run(), instance, seam


# --------------------------------------------------------------------------
# A: the formal entry, the finite admission and the default refusal
# --------------------------------------------------------------------------
def test_the_command_line_entry_refuses_an_unknown_argument(tmp_path):
    """A: the argument set of the entry is closed."""
    assert controller.main(['--force']) == controller.EXIT_REFUSED
    assert controller.main([]) == controller.EXIT_REFUSED


def test_the_command_line_entry_refuses_a_missing_context(tmp_path):
    """A: a missing context is refused before anything happens."""
    assert controller.main(['--context', str(tmp_path / 'absent.json')]) \
        == controller.EXIT_REFUSED


def test_the_command_line_entry_refuses_a_wrong_context_seal(tmp_path):
    """A: the seal of the controller context is checked."""
    composition = _build_composition(tmp_path)
    assert controller.main(['--context', str(composition['controller_context_path']),
                            '--context-sha256', '0' * 64]) == controller.EXIT_REFUSED


def test_the_native_path_is_refused_before_any_spawn(tmp_path):
    """A/C01/M02: the native path stops in the precheck with zero spawn.

    There is no accepted native execution backend on this platform, so the
    native path refuses with the stable code
    ``NATIVE_EXECUTION_BACKEND_NOT_READY`` before any spawn and before
    any native driver is constructed.  Nothing is spawned and no artefact
    of the run is written.
    """
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    receipt = controller.ProductionController(context).run()
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['spawn_attempts'] == 0
    assert receipt['refusals'] == ['CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY']
    assert receipt['admission']['accepted'] is False
    assert receipt['admission']['native_execution_backend_ready'] is False
    assert receipt['admission']['primary_reason'] == 'NATIVE_EXECUTION_BACKEND_NOT_READY'
    assert receipt['stage_pass_claim'] is False
    assert receipt['product_gate0'] is False
    # no business artefact of the run was written
    assert not (composition['root'] / 'temp' / 's3-quality').exists()
    assert not (composition['root'] / 'temp' / 's3-production-controller').exists()


def test_the_command_line_entry_of_a_valid_context_refuses_the_native_run(tmp_path, capsys):
    """A: the formal entry is closed and its refusal is machine readable.

    The entry writes its receipt on the standard output and reports the
    refusal with the exit code of a refusal.  There is no switch that
    turns the refusal into an execution.
    """
    composition = _build_composition(tmp_path)
    code = controller.main(['--context', str(composition['controller_context_path']),
                            '--context-sha256',
                            _digest_of(composition['controller_context_path'])])
    assert code == controller.EXIT_REFUSED
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt['kind'] == controller.CONTROLLER_RECEIPT_KIND
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['spawn_attempts'] == 0
    assert receipt['execution_mode'] == 'NATIVE'
    assert receipt['stage_pass_claim'] is False
    assert receipt['product_gate0'] is False
    assert not (composition['root'] / 'temp' / 's3-quality').exists()


def test_a_foreign_candidate_is_refused_before_any_spawn(tmp_path):
    """C01/I03: a worker context of a foreign candidate is refused."""
    composition = _build_composition(
        tmp_path, mutate_worker=lambda document: dict(document, candidate_sha='c' * 40))
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] == ['CONTROLLER_WORKER_CANDIDATE_MISMATCH']
    assert receipt['spawn_attempts'] == 0


def test_a_foreign_authorization_is_refused_before_any_spawn(tmp_path):
    """C01/I04: a worker context of a foreign authorization is refused."""
    composition = _build_composition(
        tmp_path, mutate_worker=lambda document: dict(document, authorization_sha256='d' * 64))
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] == ['CONTROLLER_WORKER_AUTHORIZATION_MISMATCH']
    assert receipt['spawn_attempts'] == 0


def test_a_foreign_root_is_refused_before_any_spawn(tmp_path):
    """C01/I23: a worker context of a foreign root is refused."""
    composition = _build_composition(
        tmp_path, mutate_worker=lambda document: dict(document, root=str(tmp_path / 'elsewhere')))
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] == ['CONTROLLER_WORKER_ROOT_MISMATCH']
    assert receipt['spawn_attempts'] == 0


def test_a_tampered_worker_context_is_refused_before_any_spawn(tmp_path):
    """C01: the seal of the worker context is checked again."""
    composition = _build_composition(tmp_path)
    document = json.loads(Path(composition['worker_context_path']).read_text('utf-8'))
    document['root'] = str(tmp_path / 'elsewhere')
    _write_json(Path(composition['worker_context_path']), document)
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] == ['CONTROLLER_WORKER_CONTEXT_REFUSED:WORKER_FILE_SEAL_MISMATCH']
    assert receipt['spawn_attempts'] == 0


def test_a_projection_that_the_phase_refuses_is_refused_before_any_spawn(tmp_path):
    """C01: the projection is parsed by the owner of the phase."""
    def broken(projection):
        document = json.loads(projection.decode('utf-8'))
        document['samples'][3]['asset_id'] = document['samples'][2]['asset_id']
        return json.dumps(document, ensure_ascii=False, sort_keys=True,
                          indent=2).encode('utf-8')

    composition = _build_composition(tmp_path, mutate_projection=broken)
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'][0].startswith('CONTROLLER_PROJECTION_REJECTED:')
    assert receipt['spawn_attempts'] == 0
    assert not (composition['root'] / 'temp' / 's3-quality').exists()


def test_the_seam_can_not_be_serialised_into_the_context(tmp_path):
    """A: the offline seam is not a document field and not a switch."""
    composition = _build_composition(tmp_path)
    document = json.loads(Path(composition['controller_context_path']).read_text('utf-8'))
    document['seam'] = {'driver': 'fixture'}
    _write_json(Path(composition['controller_context_path']), document)
    with pytest.raises(controller.ControllerError) as error:
        _controller_context(composition['controller_context_path'])
    assert error.value.code == 'CONTROLLER_CONTEXT_KEY_SET_INVALID'


def test_a_boolean_can_not_replace_the_seam(tmp_path):
    """A: the seam is a typed object and never a boolean."""
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    with pytest.raises(controller.ControllerError) as error:
        controller.ProductionController(context, seam=True)
    assert error.value.code == 'CONTROLLER_SEAM_INVALID'


# --------------------------------------------------------------------------
# B: the production composition itself
# --------------------------------------------------------------------------
def test_the_composition_runs_the_real_phase_and_persists_the_summary(tmp_path):
    """C02/I07: the whole production path runs once, in process.

    The controller starts the frozen production command, the formal worker
    entry loads the sealed context, the real quality phase executes the
    sixteen rows, the real protocol writer speaks over a real pipe, the real
    parent reads it, the real canonical receipt is written by the phase, the
    real parent evidence seals it and the real aggregation produces the
    twelve keys.
    """
    composition = _build_composition(tmp_path)
    receipt, instance, seam = _run_composition(composition)

    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    assert receipt['transitions'] == ['PRECHECK', 'PLAN_SEALED', 'WORKER_SUPERVISED',
                                      'ORIGINALS_VERIFIED', 'RECEIPTS_BOUND',
                                      'SUMMARY_PERSISTED']
    assert receipt['spawn_attempts'] == 1
    assert seam.spawns == 1
    assert receipt['execution_mode'] == 'OFFLINE_SYNTHETIC_COMPOSITION'
    assert receipt['real_execution_performed'] is False
    assert receipt['stage_pass_claim'] is False
    assert receipt['product_gate0'] is False

    # the frozen production command is the only command of the run
    command = receipt['command']
    assert command[1:4] == ['-I', '-B', str(PACK_ROOT / 'tools/v0_s3_quality_worker.py')]
    assert command[4] == '--context'
    assert command[5] == str(composition['worker_context_path'])

    # the phase really wrote the canonical receipt into the run root
    canonical_path = composition['root'] / 'temp/s3-quality/qd-receipt.json'
    assert canonical_path.is_file()
    canonical = json.loads(canonical_path.read_text('utf-8'))
    assert canonical['kind'] == 'S3_P3B_QD_EXECUTION_RECEIPT'
    assert len(canonical['rows']) == 16
    assert canonical['test_counts']['fixed'] == 16

    # the parent read the real bytes of the canonical receipt
    evidence = receipt['supervision']
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['terminal_received'] is True
    assert evidence['unknown_outcome'] is False
    assert evidence['row_count'] == 16
    assert len(evidence['row_status']) == 16
    assert set(evidence['row_status'].values()) == {'PASS'}

    # the parent sealed the sixteen row plan before the first send
    assert receipt['plan']['rows'] == 16
    assert len(receipt['plan']['plan_sha256']) == 64

    # the summary was persisted exactly once
    summary_path = composition['root'] / 'temp/s3-production-controller' / \
        ('summary-' + RUN_ID + '.json')
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text('utf-8'))
    assert summary['kind'] == controller.SUMMARY_KIND
    assert summary['key_count'] == 12
    assert summary['stage_pass_claim'] is False
    assert summary['product_gate0'] is False
    assert summary['real_execution_performed'] is False


def test_the_composition_never_leaves_the_offline_boundary(tmp_path):
    """C08/I22: no host process, no socket, no database and no fixture run."""
    composition = _build_composition(tmp_path)
    before = list(GUARD_ATTEMPTS)
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    assert GUARD_ATTEMPTS == before
    # the boundary is still armed after the run
    with pytest.raises(OfflineGuardError):
        subprocess.Popen(['/bin/true'])
    assert GUARD_ATTEMPTS[-1] == 'subprocess.Popen'


def test_the_composition_accepts_the_real_row_and_history_order(tmp_path):
    """C03/I10/I11/I21: the parent accepts the order of the real rows."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition)
    evidence = receipt['supervision']
    assert evidence['protocol_violation'] is None
    assert evidence['message_count'] > 16
    assert sorted(evidence['history_completed_rows']) == sorted(
        row['asset_id'] for row in composition['rows'])
    # every row announced its history wait exactly once and the deadline of
    # a row was fixed at its first announcement
    for asset_id, record in evidence['history_records'].items():
        assert record['first_start'] is not None
        assert record['deadline'] >= record['first_start']
        assert record['completed_at'] is not None
    assert evidence['phase_timeout_seconds'] == 10800
    assert evidence['history_timeout_seconds'] == 600
    assert evidence['child_timeout_seconds'] == 21600


def test_a_repeated_history_announcement_is_refused_and_does_not_extend_a_deadline(tmp_path):
    """C03/I10: a late repeat is refused and never extends the deadline."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition, fault='duplicate_history_start')
    assert receipt['state'] == controller.STATE_UNKNOWN
    evidence = receipt['supervision']
    assert evidence['protocol_violation'] == 'MESSAGE_HISTORY_STARTED_REPEATED'
    assert receipt['summary_persisted'] is False
    # the deadline of the refused row was fixed at its first announcement
    deadlines = evidence['history_deadlines']
    assert len(deadlines) >= 1
    for asset_id, deadline in deadlines.items():
        record = evidence['history_records'][asset_id]
        assert deadline == record['first_start'] + 600


def test_a_worker_that_refuses_never_produces_a_summary(tmp_path):
    """C04/I13: an incomplete run keeps the root and the reservation."""
    composition = _build_composition(tmp_path)
    receipt, _instance, seam = _run_composition(composition, fault='context_seal_mismatch')
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    evidence = receipt['supervision']
    assert evidence['protocol_violation'] == 'WORKER_EXITED_WITHOUT_TERMINAL'
    assert evidence['canonical_receipt_verified'] is False
    assert evidence['unknown_outcome'] is True
    assert evidence['root_retained'] is True
    assert evidence['reservation_retained'] is True
    assert evidence['refund_allowed'] is False
    assert evidence['resend_allowed'] is False
    assert evidence['archive_allowed'] is False
    assert seam.worker_exit_code == 2


def test_a_canonical_receipt_that_changed_is_refused(tmp_path):
    """C04/C05/I16: an original that changed is never consumed."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition, fault='tamper_canonical')
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    assert receipt['supervision']['canonical_receipt_verified'] is False
    # the protocol itself was clean, so the parent does not call the run
    # unknown; it refuses the receipt and keeps the root and the reservation
    assert receipt['supervision']['unknown_outcome'] is False
    assert receipt['supervision']['root_retained'] is True
    assert receipt['supervision']['reservation_retained'] is True


def test_a_removed_canonical_receipt_is_refused(tmp_path):
    """C05: a missing original is never read as an empty result."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition, fault='remove_canonical')
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False


def test_a_terminal_reference_out_of_the_root_is_refused(tmp_path):
    """C05: a terminal reference that leaves the root is refused."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition, fault='bad_terminal_reference')
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    assert receipt['supervision']['canonical_receipt_verified'] is False


def test_a_replaced_root_is_refused_by_the_manifest(tmp_path):
    """C05/I16: the manifest re-checks the root and refuses a replaced one.

    The root of the run is migrated to another directory object while the
    artefacts themselves are still readable.  The parent refuses the
    migration: the sealed root identity is not the identity of the root that
    is opened now.
    """
    composition = _build_composition(tmp_path)

    def replace_root(state, instance):
        if state != controller.STATE_WORKER_SUPERVISED:
            return
        root = composition['root']
        moved = root.with_name(root.name + '-moved')
        os.rename(root, moved)
        root.mkdir(parents=True)
        shutil.copytree(moved / 'temp', root / 'temp')

    receipt, _instance, _seam = _run_composition(composition, on_transition=replace_root)
    assert receipt['state'] != controller.STATE_SUMMARY_PERSISTED
    assert receipt['summary_persisted'] is False
    assert any('S3_SELECTED_ROOT_REPLACED' in reason for reason in receipt['refusals'])


def test_the_recovery_entry_of_an_unknown_outcome_never_replays(tmp_path):
    """C11/I15: the recovery coordinates, it never replays."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition, fault='context_seal_mismatch')
    recovery = receipt['recovery']
    assert recovery['replay_allowed'] is False
    assert recovery['resend_allowed'] is False
    assert recovery['stage_pass_claim'] is False
    # the offline seam creates no child, so there is no custody to recover
    assert recovery['status'] == 'BLOCKED'
    assert recovery['reason'] == 'CUSTODY_EVIDENCE_UNAVAILABLE'


# --------------------------------------------------------------------------
# C: the receipts, the twelve keys and the provenance
# --------------------------------------------------------------------------
def test_the_receipts_of_the_run_are_adapted_from_the_run_facts(tmp_path):
    """C06/I19/I20: the twelve keys come from the real receipts of the run."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    receipts = receipt['receipts']
    # every receipt of the run carries the identity of the run
    for name, document in receipts.items():
        assert document['run_id'] == RUN_ID
        assert document['candidate_sha'] == CANDIDATE_SHA
        assert document['stage_pass_claim'] is False
        assert document['product_gate0'] is False
        assert document['product_pass_claimed'] is False
    # the receipts whose truth belongs to the native or the product side
    # are never a pass
    for name in ('a06_isolation', 'install', 'rollback', 'independent_score',
                 'webp_format', 'cleanup'):
        assert receipts[name]['status'] == 'BLOCKED'
        assert receipts[name]['reason']
    summary = receipt['summary']
    assert summary['key_count'] == 12
    assert summary['pass_count'] == 0
    assert summary['cleanup_proven'] is False
    assert summary['synthetic_fixtures_count_as_product_pass'] is False
    assert summary['offline_receipts_are_not_product_receipts'] is True
    for key in summary['keys'].values():
        assert key['status'] != 'PASS'
        assert key['stage_pass_claim'] is False
        assert key['product_gate0'] is False


def test_the_old_nine_keys_can_never_fill_a_green_key(tmp_path):
    """C06: an old phase fact is not an aggregate receipt."""
    from tools.v0_s3_coordinator import aggregate_twelve_keys
    binding = {'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA}
    old = {'kind': 'S2_PHASE_RECEIPT/1', 'status': 'PASS', 'run_id': RUN_ID,
           'candidate_sha': CANDIDATE_SHA, 'stage_pass_claim': False}
    summary = aggregate_twelve_keys(receipts={'stage_binding': old,
                                              'image_input': old,
                                              'video_input': old,
                                              'output_contract': old,
                                              'manual_export': old,
                                              'no_overwrite': old,
                                              'file_safety': old,
                                              'no_approval_gate': old,
                                              'resource_budget': old,
                                              'cancel_release': old,
                                              'quality_16_rows': old,
                                              'a06_isolation': old,
                                              'install': old,
                                              'rollback': old,
                                              'independent_score': old,
                                              'webp_format': old,
                                              'cleanup': old},
                                   binding=binding)
    assert summary['pass_count'] == 0
    assert summary['old_s2_nine_keys_accepted_as_green'] is False
    for key in summary['keys'].values():
        assert key['status'] in ('NOT_RUN', 'BLOCKED')
        assert any('RECEIPT_KIND_NOT_ACCEPTED' in reason for reason in key['reasons'])


def test_a_foreign_receipt_is_refused_by_the_aggregation(tmp_path):
    """C07/I24: a receipt of another run never fills a key."""
    from tools.v0_s3_coordinator import aggregate_twelve_keys
    binding = {'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA}
    foreign = {'kind': 'lvw.s3-aggregate-receipt/1', 'status': 'PASS',
               'run_id': 'another-run', 'candidate_sha': CANDIDATE_SHA,
               'stage_pass_claim': False}
    summary = aggregate_twelve_keys(receipts={'stage_binding': foreign,
                                              'image_input': foreign,
                                              'video_input': foreign,
                                              'output_contract': foreign,
                                              'no_overwrite': foreign,
                                              'file_safety': foreign,
                                              'resource_budget': foreign,
                                              'quality_16_rows': foreign,
                                              'cleanup': foreign},
                                   binding=binding)
    assert summary['pass_count'] == 0
    for key in summary['keys'].values():
        assert 'BINDING_MISMATCH' in ' '.join(key['reasons'])


def test_the_provenance_of_the_summary_is_one_source_chain(tmp_path):
    """C07/I24: the context, the projection and the originals are one chain."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition)
    provenance = receipt['summary']['provenance']
    assert provenance['projection']['sha256'] == _digest(composition['projection'])
    assert provenance['worker_context']['sha256'] == composition['worker_context_sha256']
    assert provenance['plan']['sha256'] == receipt['plan']['plan_sha256']
    canonical_path = composition['root'] / 'temp/s3-quality/qd-receipt.json'
    assert provenance['canonical']['sha256'] == _digest_of(canonical_path)
    assert provenance['canonical']['bytes'] == canonical_path.stat().st_size
    # the manifest is the consumption boundary of the originals
    assert receipt['manifest']['reverification']['verified'] is True
    assert len(receipt['manifest']['originals']['canonical']) == 1
    assert len(receipt['manifest']['originals']['source_plan']) == 1
    assert len(receipt['manifest']['originals']['raw']) > 0


def test_the_summary_is_never_overwritten(tmp_path):
    """C: the persisted summary is written exactly once."""
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    seam = _seam(composition)
    first = controller.ProductionController(context, seam=seam).run()
    assert first['state'] == controller.STATE_SUMMARY_PERSISTED
    summary_path = composition['root'] / 'temp/s3-production-controller' / \
        ('summary-' + RUN_ID + '.json')
    before = summary_path.read_bytes()
    second = controller.ProductionController(context, seam=_seam(composition)).run()
    assert second['state'] != controller.STATE_SUMMARY_PERSISTED
    assert summary_path.read_bytes() == before


def test_the_independent_score_is_recomputed_by_the_accepted_owner(tmp_path):
    """C06/I20: the controller really calls the accepted QS owner.

    The sealed score documents and the sealed independence evidence of a
    previous run of the same identity are bound into the context.  The
    controller recomputes the score with the accepted owner; it never writes
    a score of its own.  The key of the quality obligation still stays
    blocked, because the cleanup of the product is not proven.
    """
    helpers = _helpers()
    first = _build_composition(tmp_path, name='run-a')
    receipt_a, _instance, _seam = _run_composition(first)
    assert receipt_a['state'] == controller.STATE_SUMMARY_PERSISTED
    canonical = json.loads((first['root'] / 'temp/s3-quality/qd-receipt.json').read_text('utf-8'))

    second = _build_composition(tmp_path, name='run-b')
    scores = helpers._scores(canonical, receipt_a['plan']['projection_sha256'],
                             run_id=RUN_ID)
    independence = helpers._independence(run_id=RUN_ID)
    scores_path = second['root'] / 'contexts' / 'quality-scores.json'
    independence_path = second['root'] / 'contexts' / 'independence.json'
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(scores_path, scores)
    _write_json(independence_path, independence)
    document = json.loads(Path(second['controller_context_path']).read_text('utf-8'))
    document['quality_scores'] = {'path': str(scores_path), 'sha256': _digest_of(scores_path)}
    document['independence'] = {'path': str(independence_path),
                                'sha256': _digest_of(independence_path)}
    _write_json(Path(second['controller_context_path']), document)

    receipt, _instance, _seam = _run_composition(second)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    score_receipt = receipt['receipts']['independent_score']
    assert score_receipt['status'] == 'PASS'
    assert score_receipt['independent'] is True
    assert score_receipt['product_pass_claimed'] is False
    # the quality key is still not green: the product cleanup is not proven
    assert receipt['summary']['pass_count'] == 0
    assert receipt['summary']['keys']['V0-A11']['status'] != 'PASS'
    assert any('CLEANUP_UNPROVEN' in reason
               for reason in receipt['summary']['keys']['V0-A11']['reasons'])


def test_an_independent_score_that_does_not_match_is_refused(tmp_path):
    """C06/I20: a score of another raw artefact never becomes a receipt."""
    helpers = _helpers()
    first = _build_composition(tmp_path, name='run-a')
    receipt_a, _instance, _seam = _run_composition(first)
    assert receipt_a['state'] == controller.STATE_SUMMARY_PERSISTED
    canonical = json.loads((first['root'] / 'temp/s3-quality/qd-receipt.json').read_text('utf-8'))

    second = _build_composition(tmp_path, name='run-b')
    scores = helpers._scores(canonical, receipt_a['plan']['projection_sha256'],
                             run_id=RUN_ID)
    for score in scores:
        score['raw_sha256'] = 'e' * 64
    independence = helpers._independence(run_id=RUN_ID)
    scores_path = second['root'] / 'contexts' / 'quality-scores.json'
    independence_path = second['root'] / 'contexts' / 'independence.json'
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(scores_path, scores)
    _write_json(independence_path, independence)
    document = json.loads(Path(second['controller_context_path']).read_text('utf-8'))
    document['quality_scores'] = {'path': str(scores_path), 'sha256': _digest_of(scores_path)}
    document['independence'] = {'path': str(independence_path),
                                'sha256': _digest_of(independence_path)}
    _write_json(Path(second['controller_context_path']), document)

    receipt, _instance, _seam = _run_composition(second)
    score_receipt = receipt['receipts']['independent_score']
    assert score_receipt['status'] == 'BLOCKED'
    assert score_receipt['independent'] is False
    assert score_receipt['reason'].startswith('INDEPENDENT_SCORE_REFUSED:')
    assert receipt['summary']['pass_count'] == 0


def test_the_clock_of_the_seam_drives_the_deadlines_of_the_parent(tmp_path):
    """C03/I11: the third replacement of the seam is the clock.

    The parent reads its deadlines from the injected clock, so the deadline
    of a row is fixed at its first announcement in that clock domain and
    the frozen budgets themselves are unchanged.
    """
    composition = _build_composition(tmp_path)
    seam = _seam(composition)

    class _FixedClock:
        def __init__(self):
            self.now = 1000.0

        def __call__(self):
            return self.now

    seam.clock = _FixedClock()
    context = _controller_context(composition['controller_context_path'])
    receipt = controller.ProductionController(context, seam=seam).run()
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    evidence = receipt['supervision']
    assert evidence['phase_timeout_seconds'] == 10800
    assert evidence['history_timeout_seconds'] == 600
    assert evidence['child_timeout_seconds'] == 21600
    for record in evidence['history_records'].values():
        assert record['first_start'] == 1000.0
        assert record['deadline'] == 1600.0


def test_the_unproven_receipts_keep_their_reasons_in_the_summary(tmp_path):
    """C06/I20: a missing proof is machine readable in the summary."""
    composition = _build_composition(tmp_path)
    receipt, _instance, _seam = _run_composition(composition)
    summary = receipt['summary']
    assert summary['not_run_count'] + summary['blocked_count'] == 12
    reasons = ' '.join(reason for key in summary['keys'].values() for reason in key['reasons'])
    assert 'CLEANUP_UNPROVEN' in reasons
    assert 'REAL_ISOLATION_UNPROVEN' in reasons
    assert 'INDEPENDENT_SCORE_MISSING' in reasons


def test_the_native_admission_uses_the_accepted_budget_authority(tmp_path):
    """C09/I03/I04: the accepted loader and validator are really used.

    The admission record of this case names a sealed budget binding whose
    authority, shim, protocol source, execution binding and expiry are
    verified by the accepted provider.  The native obligations are still
    missing, so the native run stays refused with zero spawn - and the
    original ledger of the binding is never opened by this controller.
    """
    from tools import test_v0_s3_integration as integration
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import MODEL_DIGEST

    composition = _build_composition(tmp_path)
    authority_root = tmp_path / 'authority'
    binding_reference, authority, _document = integration.synthetic_binding(
        authority_root, run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
        child_sha=AUTHORIZATION_SHA, model_digest=MODEL_DIGEST)
    admission = {
        'kind': controller.NATIVE_ADMISSION_KIND,
        'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA,
        'authorization_sha256': AUTHORIZATION_SHA,
        'model_digest': MODEL_DIGEST,
        'authority_root': str(authority),
        'ledger_path': str(authority / 'original.sqlite'),
        'admission_references': dict(
            {name: {'path': str(tmp_path / 'missing' / (name + '.json')), 'sha256': '0' * 64}
             for name in controller.ADMISSION_REFERENCE_KEYS},
            budget_binding=binding_reference),
    }
    admission_path = composition['composition'].write('admission-complete', admission)
    document = json.loads(Path(composition['controller_context_path']).read_text('utf-8'))
    document['admission'] = {'path': str(admission_path), 'sha256': _digest_of(admission_path)}
    _write_json(Path(composition['controller_context_path']), document)

    ledger = authority / 'original.sqlite'
    before = (ledger.read_bytes(), ledger.stat().st_mtime_ns)
    context = _controller_context(composition['controller_context_path'])
    receipt = controller.ProductionController(context).run()

    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['spawn_attempts'] == 0
    # the accepted budget authority was really verified
    assert 'budget_binding' in receipt['admission']['verified']
    assert receipt['admission']['budget_authority'] == 'S3BudgetBindingProvider'
    assert receipt['admission']['debit_owner'] == 'original_ledger_authority'
    assert receipt['admission']['original_ledger_touched_by_this_controller'] is False
    # the native obligations are still missing
    assert 'native_custody' not in receipt['admission']['verified']
    assert 'gpu_release' not in receipt['admission']['verified']
    assert 'install' not in receipt['admission']['verified']
    assert 'rollback' not in receipt['admission']['verified']
    assert 'grant' not in receipt['admission']['verified']
    assert 'tool_closure' not in receipt['admission']['verified']
    # the original ledger was not read, written or opened
    assert (ledger.read_bytes(), ledger.stat().st_mtime_ns) == before


def test_a_residue_that_is_not_empty_is_never_read_as_an_empty_residue(tmp_path):
    """C10/I17/I18: an unknown residue stays unknown and nothing is deleted.

    The residue accessor of the driver reports a leftover of the video
    snapshot.  The phase refuses the row, the run is not green, the
    observation keeps its own error and the controller deletes nothing.
    """
    composition = _build_composition(tmp_path, driver_failure='residue')
    receipt, _instance, _seam = _run_composition(composition)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    observations = receipt['residue_observations']
    assert observations
    unknown = [item for item in observations if not item['proven_empty']]
    assert unknown
    for item in unknown:
        # the observation keeps its own error; it is never an empty list
        assert isinstance(item['observation'], dict)
        assert item['observation'].get('proven') is not True
    assert receipt['receipts']['cleanup']['reason'].startswith('RESIDUE_NOT_PROVEN_EMPTY:')
    summary = receipt['summary']
    assert summary['pass_count'] == 0
    # the rows that were refused are not counted as executed rows
    assert receipt['receipts']['quality_16_rows']['status'] == 'FAIL'
    assert receipt['receipts']['image_input']['status'] == 'FAIL'
    # the controller deleted nothing of the run root
    assert (composition['root'] / 'temp/s3-quality').is_dir()
    assert (composition['root'] / 'input').is_dir()


# --------------------------------------------------------------------------
# E: the directed correction scope of the production composition correction 01
#
# The scope is one positive example of the whole chain and one negative
# example for every finding of the independent review: M01, M02, M03, M04,
# M05, M06, M07, M08, M09, m01 and m02.  Nothing of the old denominators
# is rerun mechanically here: the scope is the findings themselves.
#
# Every example drives the *formal* command line entry of the controller.
# The offline seam is injected at the Python construction site only, so the
# argument set of the entry stays closed and the entry never learns about
# the seam.
# --------------------------------------------------------------------------
def _formal_main(composition, monkeypatch, *, fault='none', transition=None,
                 factory=None, driver_failure=None, clock=None, holder=None,
                 worker_wait_timeout=5.0):
    """Run the formal command line entry of the controller.

    The entry receives the sealed controller context and its *exact* hash.
    The seam is a Python object that is injected into the construction of
    the controller and that is never an argument, a document field or a
    switch.
    """
    if driver_failure is None:
        driver_failure = composition.get('driver_failure')
    seam = controller.OfflineCompositionSeam(
        driver_factory=factory or (lambda ctx: _helpers().SyntheticDriver(
            Path(ctx.document['root']), driver_failure)),
        context_sha256=composition['worker_context_sha256'],
        fault=fault,
        clock=clock,
        worker_wait_timeout=worker_wait_timeout)
    seam.on_transition = transition
    if holder is not None:
        holder['seam'] = seam
    original = controller.ProductionController

    class Injected(original):
        def __init__(self, context):
            super().__init__(context, seam=seam)

    output = io.StringIO()
    errors = io.StringIO()
    arguments = ['--context', str(composition['controller_context_path']),
                 '--context-sha256', _digest_of(composition['controller_context_path'])]
    with monkeypatch.context() as scope:
        scope.setattr(controller, 'ProductionController', Injected)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = controller.main(arguments)
    receipt = None
    if output.getvalue().strip():
        receipt = json.loads(output.getvalue())
    return code, receipt, seam, errors.getvalue()


def _controller_directory_of(composition):
    return composition['root'] / 'temp' / 's3-production-controller'


# ---- the positive example ------------------------------------------------
def test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary(tmp_path, monkeypatch):
    """C02/I07: the positive example of the whole production chain.

    The formal entry of the controller starts the fixed production command,
    the formal worker entry loads the sealed context, the real quality
    phase executes the sixteen rows, the real protocol writer speaks over a
    real pipe, the real parent reader reads it, the real canonical receipt
    is sealed by the real parent evidence, the receipts are adapted from
    the facts of this run and the summary is persisted inside the bound
    root.
    """
    composition = _build_composition(tmp_path)
    code, receipt, seam, errors = _formal_main(composition, monkeypatch)

    assert code == controller.EXIT_PERSISTED
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    assert receipt['transitions'] == ['PRECHECK', 'PLAN_SEALED', 'WORKER_SUPERVISED',
                                      'ORIGINALS_VERIFIED', 'RECEIPTS_BOUND',
                                      'SUMMARY_PERSISTED']
    assert seam.spawns == 1
    assert receipt['spawn_attempts'] == 1

    # the fixed production command carries the pre-sealed worker hash
    command = receipt['command']
    assert command[1:4] == ['-I', '-B', str(PACK_ROOT / 'tools/v0_s3_quality_worker.py')]
    assert command[4:6] == ['--context', str(composition['worker_context_path'])]
    assert command[6:8] == ['--context-sha256', composition['worker_context_sha256']]

    # the real phase really wrote its canonical receipt
    canonical = json.loads((composition['root'] / 'temp/s3-quality/qd-receipt.json')
                           .read_text('utf-8'))
    assert len(canonical['rows']) == 16
    assert canonical['test_counts']['PASS'] == 16
    assert receipt['supervision']['message_count'] > 16
    assert receipt['supervision']['canonical_receipt_verified'] is True

    # the manifest is the consumption boundary of the originals
    assert receipt['manifest']['reverification']['verified'] is True
    assert receipt['consumption_reverified'] is True

    # the summary and the receipt are written exactly once, inside the root
    directory = _controller_directory_of(composition)
    summary_path = directory / ('summary-' + RUN_ID + '.json')
    receipt_path = directory / ('receipt-' + RUN_ID + '.json')
    assert summary_path.is_file()
    assert receipt_path.is_file()
    summary = json.loads(summary_path.read_text('utf-8'))
    assert summary['kind'] == controller.SUMMARY_KIND
    assert summary['key_count'] == 12
    assert summary['pass_count'] == 0
    assert summary['stage_pass_claim'] is False
    assert summary['product_gate0'] is False
    assert receipt['receipt_persisted'] is True

    # the provenance names the real controller context and the worker context
    provenance = summary['provenance']
    assert provenance['controller_context']['sha256'] == \
        _digest_of(composition['controller_context_path'])
    assert provenance['worker_context']['sha256'] == composition['worker_context_sha256']
    assert provenance['canonical']['sha256'] == \
        receipt['manifest']['originals']['canonical'][0]['sha256']

    # the lifecycle of the worker thread is honest
    lifecycle = receipt['fd_cleanup']['worker_lifecycle']
    assert lifecycle['worker_thread_finished'] is True
    assert lifecycle['worker_thread_retained'] is False
    assert lifecycle['late_write_after_return_is_possible'] is False
    assert receipt['fd_cleanup']['fd_leaked'] == []


# ---- M01: the comparison of a value ---------------------------------------
def test_the_comparison_of_a_value_is_a_comparison_of_the_type_and_the_value(tmp_path):
    """M01: a decoded string is equal to the expected literal.

    The comparison of a *value* was an identity test, so every normally
    decoded document was refused and only a Python literal that happened to
    be the very same object passed.  The comparison is now a comparison of
    the type and of the value, and a boolean proof is still compared with
    its identity.
    """
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    decoded = json.loads(json.dumps({'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
                                     'status': 'PROVEN', 'grant_active': True}))
    reasons = []
    assert controller._bound_receipt(decoded, context, label='grant', reasons=reasons,
                                     required={'status': 'PROVEN', 'grant_active': True}) is True
    assert reasons == []
    # a number is never a boolean proof
    loose = dict(decoded, grant_active=1)
    reasons = []
    assert controller._bound_receipt(loose, context, label='grant', reasons=reasons,
                                     required={'status': 'PROVEN', 'grant_active': True}) is False
    assert reasons == ['grant:PROOF_MISSING:grant_active']
    # a foreign run is still refused
    reasons = []
    assert controller._bound_receipt(dict(decoded, run_id='another-run'), context,
                                     label='grant', reasons=reasons,
                                     required={'status': 'PROVEN'}) is False
    assert reasons == ['grant:BINDING_MISMATCH']


# ---- M02: the missing native execution backend ----------------------------
def test_a_complete_self_written_proof_chain_is_never_an_admission(tmp_path):
    """M02: a self written PROVEN chain never authorises a native execution.

    Every element of the chain is written by this test with the right
    strings and the right booleans.  The admission is refused anyway: the
    trusted native execution backend does not exist on this platform, and
    the report names that as its primary reason.  The budget binding is
    only verified in its shape.
    """
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    document = json.loads((composition['root'] / 'contexts' / 'admission.json')
                          .read_text('utf-8'))
    proof_fields = {'native_custody': ['descendant_handles_closed', 'native_services_stopped'],
                    'gpu_release': ['gpu_released'],
                    'install': ['installed'],
                    'rollback': ['rollback_verified'],
                    'grant': ['grant_active']}
    for name in controller.ADMISSION_REFERENCE_KEYS:
        path = composition['root'] / 'contexts' / ('own-' + name + '.json')
        proof = {'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA, 'status': 'PROVEN'}
        for key in proof_fields.get(name, []):
            proof[key] = True
        if name == 'grant':
            proof.update(expires_at=0, scope='outside-the-authorized-scope', budget=0,
                         authorization_sha256='e' * 64)
        if name == 'tool_closure':
            proof['files'] = [{'path': str(composition['controller_context_path']),
                               'sha256': _digest_of(composition['controller_context_path'])}]
        _write_json(path, proof)
        document['admission_references'][name] = {'path': str(path), 'sha256': _digest_of(path)}
    report = controller.verify_native_admission(context, document)
    assert report['accepted'] is False
    assert report['primary_reason'] == 'NATIVE_EXECUTION_BACKEND_NOT_READY'
    assert report['native_execution_backend_ready'] is False
    assert report['budget_binding_scope'].startswith('SEALED_BINDING_SHAPE_ONLY')
    assert report['original_ledger_touched_by_this_controller'] is False


def test_the_default_entries_refuse_the_native_execution_with_zero_spawn(tmp_path, monkeypatch):
    """M02: the controller and the worker refuse before any spawn.

    The controller refuses with the stable code of the missing backend and
    spawns nothing.  The worker refuses with the very same code and never
    constructs a native driver: the spy of the construction is never
    called.
    """
    from tools import v0_s3_quality_worker as worker
    composition = _build_composition(tmp_path)
    context = _controller_context(composition['controller_context_path'])
    receipt = controller.ProductionController(context).run()
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['spawn_attempts'] == 0
    assert receipt['refusals'] == ['CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY']
    assert receipt['admission']['accepted'] is False

    calls = []

    def deny(worker_context):
        calls.append(worker_context)
        raise AssertionError('the native driver must never be constructed')

    monkeypatch.setattr(worker, 'build_native_driver', deny)
    errors = io.StringIO()
    code = worker.main(['--context', str(composition['worker_context_path']),
                        '--context-sha256', composition['worker_context_sha256']],
                       stream=io.BytesIO(), error_stream=errors)
    assert code == 2
    assert errors.getvalue() == 'S3_WORKER_REFUSED NATIVE_EXECUTION_BACKEND_NOT_READY\n'
    assert calls == []


# ---- M03: the chain of the context hash -----------------------------------
def test_the_command_line_entry_demands_the_exact_controller_context_hash(tmp_path, capsys):
    """M03: the entry never computes the expectation of the seal itself."""
    composition = _build_composition(tmp_path)
    assert controller.main(['--context', str(composition['controller_context_path'])]) \
        == controller.EXIT_REFUSED
    assert 'CONTROLLER_CONTEXT_HASH_ARGUMENT_REQUIRED' in capsys.readouterr().err
    assert controller.main(['--context', str(composition['controller_context_path']),
                            '--context-sha256', 'not-a-digest']) == controller.EXIT_REFUSED
    assert 'CONTROLLER_CONTEXT_HASH_INVALID' in capsys.readouterr().err
    assert controller.main(['--context', str(composition['controller_context_path']),
                            '--context-sha256', '0' * 64]) == controller.EXIT_REFUSED
    assert 'CONTROLLER_CONTEXT_SEAL_MISMATCH' in capsys.readouterr().err


def test_a_worker_context_that_changed_between_the_two_loads_is_refused(tmp_path, monkeypatch):
    """M03: the worker verifies every load against the sealed hash.

    The context is changed between the first load of the seam and the
    second load of the formal worker entry.  The second load refuses, the
    worker never sends a row and the run stays unknown.
    """
    composition = _build_composition(tmp_path)
    original = Path(composition['worker_context_path']).read_bytes()

    def factory(worker_context):
        document = json.loads(original)
        document['driver_arguments']['powershell'] = 'C:/changed-after-the-seal.exe'
        _write_json(Path(composition['worker_context_path']), document)
        return _helpers().SyntheticDriver(Path(worker_context.document['root']))

    code, receipt, seam, errors = _formal_main(composition, monkeypatch, factory=factory)
    assert original != Path(composition['worker_context_path']).read_bytes()
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    assert seam.worker_exit_code == 2
    assert not (_controller_directory_of(composition) / ('summary-' + RUN_ID + '.json')).exists()


# ---- M04: the bounded and safe reads --------------------------------------
def test_the_reads_are_bounded_regular_and_never_follow_a_link(tmp_path, monkeypatch):
    """M04: the bound is applied before the bytes are taken.

    An oversized file is refused without being read, the read loop never
    asks for more than the bound plus one byte, a special file is never
    read as a file and an ancestor that is a link is refused.
    """
    from tools import v0_s3_controller_io as io_module
    limit = io_module.MAX_BOUNDED_BYTES

    exact = tmp_path / 'exact.bin'
    exact.write_bytes(b'a' * limit)
    assert len(io_module.read_bounded_regular(exact)) == limit

    over = tmp_path / 'over.bin'
    over.write_bytes(b'a' * (limit + 1))
    taken = []
    original_read = os.read

    def spy(descriptor, size):
        block = original_read(descriptor, size)
        taken.append(len(block))
        return block

    monkeypatch.setattr(os, 'read', spy)
    with pytest.raises(io_module.ControllerIOError) as error:
        io_module.read_bounded_regular(over)
    assert error.value.code == 'FILE_TOO_LARGE'
    assert sum(taken) <= limit + 1

    # a file whose size lies about itself: the loop stops at the bound
    taken.clear()
    with pytest.raises(io_module.ControllerIOError) as error:
        io_module.read_bounded_regular('/proc/self/status', 16)
    assert error.value.code == 'FILE_TOO_LARGE'
    assert sum(taken) <= 17
    monkeypatch.undo()

    # a fifo and a device are never read as a file
    fifo = tmp_path / 'fifo'
    os.mkfifo(fifo)
    with pytest.raises(io_module.ControllerIOError) as error:
        io_module.read_bounded_regular(fifo)
    assert error.value.code == 'FILE_NOT_A_REGULAR_FILE'
    with pytest.raises(io_module.ControllerIOError) as error:
        io_module.read_bounded_regular('/dev/null')
    assert error.value.code == 'FILE_NOT_A_REGULAR_FILE'

    # an ancestor that is a link is refused
    root = tmp_path / 'root'
    (root / 'real').mkdir(parents=True)
    (root / 'real' / 'artifact.bin').write_bytes(b'x')
    os.symlink(str(root / 'real'), str(root / 'link'))
    with pytest.raises(io_module.ControllerIOError) as error:
        io_module.read_bounded_in_root(root, 'link/artifact.bin')
    assert error.value.code in ('DIRECTORY_UNUSABLE', 'ANCESTOR_NOT_A_DIRECTORY')


# ---- M05: the consumption boundary ----------------------------------------
@pytest.mark.parametrize('target', ['raw', 'canonical', 'root'])
def test_an_original_that_changed_after_the_verification_is_refused(tmp_path, monkeypatch, target):
    """M05: a controlled change after the verification keeps the run unknown.

    The original is changed after the parent verified it.  The consumption
    boundary re-verifies the root, the manifest and the originals, so the
    run stays unknown, no summary is written and no contradictory hash is
    published.
    """
    composition = _build_composition(tmp_path)
    changed = {}

    def fault(state, instance):
        if state != controller.STATE_ORIGINALS_VERIFIED:
            return
        if target == 'root':
            root = composition['root']
            moved = root.with_name(root.name + '-moved')
            os.rename(root, moved)
            os.symlink(str(moved), str(root), target_is_directory=True)
            changed['sealed'] = str(root)
            return
        if target == 'canonical':
            path = composition['root'] / 'temp' / 's3-quality' / 'qd-receipt.json'
        else:
            entry = instance.manifest['originals']['raw'][0]
            path = composition['root'] / entry['reference']
        changed['sealed'] = instance.manifest['originals'][
            'canonical' if target == 'canonical' else 'raw'][0]['sha256']
        path.write_bytes(path.read_bytes() + b' ')
        changed['actual'] = _digest_of(path)

    code, receipt, seam, errors = _formal_main(composition, monkeypatch, transition=fault)
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    assert 'CONTROLLER_ORIGINALS_CHANGED_AT_CONSUMPTION' in receipt['unknown_reason']
    assert not (_controller_directory_of(composition) / ('summary-' + RUN_ID + '.json')).exists()
    assert receipt['root_retained'] is True
    assert receipt['reservation_retained'] is True


# ---- M06: the exclusive summary inside the bound root ----------------------
def test_the_summary_is_never_written_outside_the_bound_root(tmp_path, monkeypatch):
    """M06: the summary stays inside the bound root.

    The directory of the controller is replaced by a link to a directory
    outside of the root.  The exclusive write walks the chain of the
    bound root without following a link, so it refuses and nothing is
    written outside.
    """
    composition = _build_composition(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()

    def fault(state, instance):
        if state != controller.STATE_RECEIPTS_BOUND:
            return
        directory = _controller_directory_of(composition)
        moved = directory.with_name(directory.name + '-moved')
        os.rename(directory, moved)
        os.symlink(str(outside), str(directory), target_is_directory=True)

    code, receipt, seam, errors = _formal_main(composition, monkeypatch, transition=fault)
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['summary_persisted'] is False
    assert 'CONTROLLER_DIRECTORY_UNUSABLE' in receipt['unknown_reason']
    assert list(outside.glob('*.json')) == []
    assert not (_controller_directory_of(composition) / ('summary-' + RUN_ID + '.json')).exists()


# ---- M07: the internal receipts follow the complete obligation -------------
@pytest.mark.parametrize('failure', ['release-unproven', 'residue', 'provider-refusal'])
def test_a_failed_row_never_produces_an_internal_pass(tmp_path, monkeypatch, failure):
    """M07: an inner failure is never hidden by the outer state.

    The receipts of the run are derived from the complete obligation of
    each of them.  A row that failed is not a pass of the output, of the
    budget, of the no-overwrite or of the sixteen rows, and the outer
    status of the run never hides that.
    """
    composition = _build_composition(tmp_path, driver_failure=failure)
    code, receipt, seam, errors = _formal_main(composition, monkeypatch)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    canonical = json.loads((composition['root'] / 'temp/s3-quality/qd-receipt.json')
                           .read_text('utf-8'))
    assert canonical['test_counts']['FAIL'] > 0
    statuses = {name: document['status'] for name, document in receipt['receipts'].items()}
    for name in ('output_contract', 'resource_budget', 'no_overwrite', 'quality_16_rows'):
        assert statuses[name] != 'PASS', name
    assert receipt['summary']['pass_count'] == 0
    # the cleanup of the product is not proven: the root and the reservation stay
    assert receipt['cleanup_proven'] is False
    assert receipt['root_retained'] is True
    assert receipt['reservation_retained'] is True
    assert receipt['refund_allowed'] is False


def test_the_last_row_of_the_run_is_not_hidden_by_the_outer_state(tmp_path, monkeypatch):
    """M07: the failure of the sixteenth row is an inner failure.

    Fifteen rows pass and the sixteenth one fails.  The receipts of the
    run stay failures: the existence of the artefacts and a count that is
    not ``None`` are never a proof.
    """
    composition = _build_composition(tmp_path)

    class LastFailure(_helpers().SyntheticDriver):
        def release_preload(self, binding, worker):
            self.failure = 'release-unproven' if self.submissions == 16 else None
            return super().release_preload(binding, worker)

    code, receipt, seam, errors = _formal_main(
        composition, monkeypatch,
        factory=lambda ctx: LastFailure(Path(ctx.document['root'])))
    canonical = json.loads((composition['root'] / 'temp/s3-quality/qd-receipt.json')
                           .read_text('utf-8'))
    assert canonical['test_counts']['PASS'] == 15
    assert canonical['test_counts']['FAIL'] == 1
    statuses = {name: document['status'] for name, document in receipt['receipts'].items()}
    for name in ('output_contract', 'resource_budget', 'no_overwrite', 'quality_16_rows'):
        assert statuses[name] != 'PASS', name
    assert receipt['summary']['pass_count'] == 0


# ---- M08: an ordinary exception -------------------------------------------
def test_an_ordinary_exception_keeps_a_persisted_unknown_and_cleans_up(tmp_path, monkeypatch):
    """M08: an ordinary exception ends in a persisted unknown.

    The receipt of the unknown run is persisted inside the bound root, the
    descriptors of the run are closed in a bounded way, the partial
    evidence is kept and no summary is written.
    """

    def broken(self):
        raise RuntimeError('independent-exception-probe')

    composition = _build_composition(tmp_path)
    monkeypatch.setattr(controller.ProductionController, '_bind_receipts', broken)
    code, receipt, seam, errors = _formal_main(composition, monkeypatch)
    assert receipt['state'] == controller.STATE_UNKNOWN
    assert receipt['unknown_reason'] == 'CONTROLLER_UNEXPECTED_EXCEPTION:RuntimeError'
    assert receipt['refusals'] == ['CONTROLLER_UNEXPECTED_EXCEPTION:RuntimeError']
    assert receipt['summary_persisted'] is False
    assert receipt['fd_cleanup']['fd_leaked'] == []
    receipt_path = _controller_directory_of(composition) / ('receipt-' + RUN_ID + '.json')
    assert receipt_path.is_file()
    persisted = json.loads(receipt_path.read_text('utf-8'))
    assert persisted['state'] == controller.STATE_UNKNOWN
    assert persisted['unknown_reason'] == 'CONTROLLER_UNEXPECTED_EXCEPTION:RuntimeError'
    assert not (_controller_directory_of(composition) / ('summary-' + RUN_ID + '.json')).exists()


# ---- M09: the execution right of the run -----------------------------------
def test_a_second_run_of_the_same_run_id_is_refused_before_any_send(tmp_path, monkeypatch):
    """M09: the exclusive execution right is taken before the first send.

    The reservation of the first run is kept.  The second run finds it and
    refuses before it sends anything, so the sixteen rows are never run
    twice and the summary of the first run is never replaced.
    """
    composition = _build_composition(tmp_path)
    code, receipt, seam, errors = _formal_main(composition, monkeypatch)
    assert receipt['state'] == controller.STATE_SUMMARY_PERSISTED
    summary_path = _controller_directory_of(composition) / ('summary-' + RUN_ID + '.json')
    before = summary_path.read_bytes()

    code, receipt, seam, errors = _formal_main(composition, monkeypatch)
    assert seam.spawns == 0
    assert receipt['spawn_attempts'] == 0
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] in (['CONTROLLER_RESERVATION_ALREADY_EXISTS'],
                                   ['CONTROLLER_SUMMARY_ALREADY_EXISTS'])
    assert summary_path.read_bytes() == before


def test_a_pre_existing_summary_is_refused_before_any_send(tmp_path, monkeypatch):
    """M09: an existing terminal state of the run is refused."""
    composition = _build_composition(tmp_path)
    directory = _controller_directory_of(composition)
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / ('summary-' + RUN_ID + '.json')
    summary_path.write_bytes(b'prior-summary')

    code, receipt, seam, errors = _formal_main(composition, monkeypatch)
    assert seam.spawns == 0
    assert receipt['spawn_attempts'] == 0
    assert receipt['state'] == controller.STATE_REFUSED
    assert receipt['refusals'] == ['CONTROLLER_SUMMARY_ALREADY_EXISTS']
    assert summary_path.read_bytes() == b'prior-summary'


# ---- m01: the lifecycle of the offline seam --------------------------------
def test_the_cooperative_cancel_stops_the_worker_and_the_thread_is_joined(tmp_path, monkeypatch):
    """m01: the cancel is checked before the next submission.

    The seam requests the cooperative cancel inside the driver.  The next
    controlled call of the phase refuses, the worker stops on its own and
    the thread is joined: the run never claims that nothing can write
    after it returned.
    """
    composition = _build_composition(tmp_path)
    holder = {}

    def factory(worker_context):
        driver = _helpers().SyntheticDriver(Path(worker_context.document['root']))
        original_submit = driver.submit

        def submit(graph):
            result = original_submit(graph)
            holder['seam'].cancel()
            return result

        driver.submit = submit
        return driver

    code, receipt, seam, errors = _formal_main(composition, monkeypatch,
                                                factory=factory, holder=holder)
    lifecycle = receipt['fd_cleanup']['worker_lifecycle']
    assert lifecycle['cooperative_cancel_requested'] is True
    assert lifecycle['worker_thread_finished'] is True
    assert lifecycle['worker_thread_retained'] is False
    assert lifecycle['worker_thread_killable'] is False
    assert lifecycle['late_write_after_return_is_possible'] is False
    assert receipt['fd_cleanup']['fd_leaked'] == []


def test_a_worker_that_does_not_cooperate_is_retained_and_the_run_stays_unknown(
        tmp_path, monkeypatch):
    """m01: a thread that can not be stopped is retained and reported.

    The driver blocks inside its own callback and does not cooperate.  A
    thread of this process can not be killed, so the run stays unknown, the
    thread stays retained and the receipt says that a late write after the
    return of the run is still possible.
    """
    composition = _build_composition(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    baseline = time.monotonic()
    holder = {}

    class Blocking(_helpers().SyntheticDriver):
        def submit(self, graph):
            entered.set()
            release.wait(120)
            return super().submit(graph)

    def factory(worker_context):
        return Blocking(Path(worker_context.document['root']))

    def clock():
        return baseline + 22000 if entered.is_set() else time.monotonic()

    try:
        code, receipt, seam, errors = _formal_main(composition, monkeypatch,
                                                    factory=factory, clock=clock,
                                                    holder=holder,
                                                    worker_wait_timeout=0.5)
        lifecycle = receipt['fd_cleanup']['worker_lifecycle']
        assert receipt['state'] == controller.STATE_UNKNOWN
        assert lifecycle['worker_thread_finished'] is False
        assert lifecycle['worker_thread_retained'] is True
        assert lifecycle['worker_thread_killable'] is False
        assert lifecycle['late_write_after_return_is_possible'] is True
        assert receipt['root_retained'] is True
        assert receipt['reservation_retained'] is True
    finally:
        release.set()
        seam = holder.get('seam')
        if seam is not None:
            seam.release_and_join(15)


# ---- m02: the error stream of the worker -----------------------------------
def test_the_refusal_of_the_worker_keeps_its_code_on_a_text_and_on_a_binary_stream(
        tmp_path, monkeypatch):
    """m02: the exact code of a refusal survives both stream types.

    The stream of the composition is a binary stream.  A refusal that was
    written as text into it became a ``TypeError`` and the code of the
    refusal was lost.  Both stream types carry the very same code now.
    """
    from tools import v0_s3_quality_worker as worker
    composition = _build_composition(tmp_path)
    driver = _helpers().SyntheticDriver(composition['root'])

    text = io.StringIO()
    code = worker.main(['--context', str(composition['worker_context_path']),
                        '--context-sha256', '0' * 64],
                       driver=driver, stream=io.BytesIO(), error_stream=text)
    assert code == 2
    assert text.getvalue() == 'S3_WORKER_REFUSED WORKER_FILE_SEAL_MISMATCH\n'

    binary = io.BytesIO()
    code = worker.main(['--context', str(composition['worker_context_path']),
                        '--context-sha256', '0' * 64],
                       driver=driver, stream=io.BytesIO(), error_stream=binary)
    assert code == 2
    assert binary.getvalue() == b'S3_WORKER_REFUSED WORKER_FILE_SEAL_MISMATCH\n'

    # the default entry refuses the native execution on both stream types
    binary = io.BytesIO()
    code = worker.main(['--context', str(composition['worker_context_path']),
                        '--context-sha256', composition['worker_context_sha256']],
                       stream=io.BytesIO(), error_stream=binary)
    assert code == 2
    assert binary.getvalue() == b'S3_WORKER_REFUSED NATIVE_EXECUTION_BACKEND_NOT_READY\n'
