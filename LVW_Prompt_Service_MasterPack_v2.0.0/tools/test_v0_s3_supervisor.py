"""The offline supervision obligations of the S3-P4-OFFLINE workpack.

Section B: the bounded protocol, the sealed sixteen row plan, the fixed
deadlines, the parent held worker handle, the terminal receipt verification,
the quality worker entry and the recovery entry.

The process bearing scenarios are gated: they run only when the root machine
binding of the finite fixture process plan is present and says that the
execution is permitted.  Without that binding they are skipped, and the
zero process part of this module stays complete.
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess as _subprocess
import sys
import time
from pathlib import Path

import pytest

# The original Popen of this interpreter is kept before the accepted P3B
# harness is imported.  That harness installs its own blocking monkeypatch at
# import time; restoring the original keeps the inspected runner's audit hook
# the only process gate of this batch.
_ORIGINAL_POPEN = _subprocess.Popen

from tools import test_v0_s3_quality_phase as _p3b  # noqa: E402

_subprocess.Popen = _ORIGINAL_POPEN

from tools.v0_s3_quality_worker import (  # noqa: E402
    WorkerContext, WorkerError, run_worker)
from tools.v0_s3_supervisor import (  # noqa: E402
    CHILD_TIMEOUT_SECONDS, EVENTS, FIXTURE_SCENARIOS, HISTORY_TIMEOUT_SECONDS,
    MAX_MESSAGE_BYTES, MAX_MESSAGES, MESSAGE_KEYS, PHASE_TIMEOUT_SECONDS,
    PROTOCOL_SCHEMA, ParentSupervisor, ProtocolState, RecoveryEntry, SealedPlan,
    SupervisionError, build_fixture_command, build_production_command, decode_message)

PACK_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACK_ROOT.parent
RUN_ID = 'synthetic-quality-run'
CANDIDATE_SHA = 'a' * 40
AUTHORIZATION_SHA = 'b' * 64
EXECUTOR_RELATIVE = ('reports/v0-s3/product-gate0/implementation-integration-01/'
                     'executor.py')


def load_executor_module():
    """Load the independent finite CPU executor of the new report subtree."""
    path = PACK_ROOT / EXECUTOR_RELATIVE
    spec = importlib.util.spec_from_file_location('lvw_s3_finite_cpu_executor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXECUTOR_MODULE = load_executor_module()


def bound_executor():
    """The executor instance that the guarded runner installed, if any."""
    module = sys.modules.get('lvw_s3_finite_cpu_executor')
    if module is None:
        return None
    return getattr(module, 'EXECUTOR', None)


def sixteen_rows():
    return [{'ordinal': index + 1, 'asset_id': 'SYN-%02d' % (index + 1),
             'media_kind': 'image' if index < 10 else 'video'} for index in range(16)]


def message(event, payload, *, sequence=1, run_id=RUN_ID, candidate=CANDIDATE_SHA,
            authorization=AUTHORIZATION_SHA, **extra):
    value = {'schema': PROTOCOL_SCHEMA, 'run_id': run_id, 'candidate_sha': candidate,
             'authorization_sha256': authorization, 'sequence': sequence, 'event': event,
             'payload': payload}
    value.update(extra)
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def plan():
    return SealedPlan(sixteen_rows())


# ------------------------------------------------------------------ protocol
def test_the_message_key_set_is_closed():
    """I12: a message with an extra or a missing key is refused."""
    value = message('STARTED', {})
    value['unexpected'] = True
    with pytest.raises(SupervisionError) as error:
        decode_message(encoded(value))
    assert error.value.code == 'MESSAGE_KEY_SET_INVALID'
    value = message('STARTED', {})
    del value['sequence']
    with pytest.raises(SupervisionError) as error:
        decode_message(encoded(value))
    assert error.value.code == 'MESSAGE_KEY_SET_INVALID'


def test_the_schema_and_the_event_are_validated():
    """I12: a foreign schema or an unknown event is refused."""
    value = message('STARTED', {})
    value['schema'] = 'lvw.s3-supervision/2'
    with pytest.raises(SupervisionError) as error:
        decode_message(encoded(value))
    assert error.value.code == 'MESSAGE_SCHEMA_INVALID'
    value = message('STARTED', {})
    value['event'] = 'SOMETHING'
    with pytest.raises(SupervisionError) as error:
        decode_message(encoded(value))
    assert error.value.code == 'MESSAGE_EVENT_INVALID'


def test_an_oversize_message_is_refused():
    """I12: a message above the bound is refused."""
    value = message('PROGRESS', {'filler': 'x' * (MAX_MESSAGE_BYTES + 10)})
    with pytest.raises(SupervisionError) as error:
        decode_message(encoded(value))
    assert error.value.code == 'MESSAGE_TOO_LARGE'


def test_a_nonfinite_number_is_refused():
    """I12: a nonfinite number in the protocol is refused."""
    raw = (b'{"schema":"' + PROTOCOL_SCHEMA.encode('utf-8') + b'","run_id":"x",'
           b'"candidate_sha":"y","authorization_sha256":"z","sequence":1,'
           b'"event":"STARTED","payload":{"value":NaN}}')
    with pytest.raises(SupervisionError) as error:
        decode_message(raw)
    assert error.value.code == 'MESSAGE_NONFINITE_NUMBER'


def test_a_duplicate_key_is_refused():
    """I12: a duplicate JSON key is refused."""
    raw = (b'{"schema":"' + PROTOCOL_SCHEMA.encode('utf-8') + b'","run_id":"x",'
           b'"run_id":"y","candidate_sha":"y","authorization_sha256":"z",'
           b'"sequence":1,"event":"STARTED","payload":{}}')
    with pytest.raises(SupervisionError) as error:
        decode_message(raw)
    assert error.value.code == 'MESSAGE_DUPLICATE_KEY'


def test_the_sequence_must_strictly_increase():
    """I12: a repeated or a reversed sequence is refused."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    state.accept(decode_message(encoded(message('STARTED', {}, sequence=2))))
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('PROGRESS', {}, sequence=2))))
    assert error.value.code == 'MESSAGE_SEQUENCE_NOT_INCREASING'


def test_a_foreign_identity_is_refused():
    """I12: a message of another run, candidate or child is refused."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('STARTED', {}, run_id='other'))))
    assert error.value.code == 'MESSAGE_RUN_ID_MISMATCH'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('STARTED', {}, candidate='c' * 40))))
    assert error.value.code == 'MESSAGE_CANDIDATE_MISMATCH'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('STARTED', {}, authorization='d' * 64))))
    assert error.value.code == 'MESSAGE_AUTHORIZATION_MISMATCH'


def test_the_message_count_is_capped():
    """I12: the message count is bounded."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    state.accept(decode_message(encoded(message('STARTED', {}, sequence=1))))
    state.count = MAX_MESSAGES
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('PROGRESS', {}, sequence=2))))
    assert error.value.code == 'MESSAGE_COUNT_EXCEEDED'


def test_a_row_event_must_name_a_plan_row():
    """I12: a row event of a row outside the sealed plan is refused."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message(
            'ROW_STARTED', {'asset_id': 'unknown', 'ordinal': 1}))))
    assert error.value.code == 'ROW_NOT_IN_PLAN'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message(
            'ROW_STARTED', {'asset_id': 'SYN-01', 'ordinal': 2}))))
    assert error.value.code == 'MESSAGE_ROW_ORDINAL_MISMATCH'


def test_a_repeated_history_start_is_refused():
    """I10/I12: the history start of a row happens exactly once."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    payload = {'asset_id': 'SYN-01', 'ordinal': 1}
    state.accept(decode_message(encoded(message('HISTORY_WAIT_STARTED', payload, sequence=1))))
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('HISTORY_WAIT_STARTED', payload, sequence=2))))
    assert error.value.code == 'MESSAGE_HISTORY_STARTED_REPEATED'


def test_the_terminal_reference_is_validated():
    """I12: a terminal event carries only a bounded reference."""
    state = ProtocolState(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
                          authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('TERMINAL', {'canonical_receipt': {}}))))
    assert error.value.code == 'MESSAGE_TERMINAL_REFERENCE_INVALID'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message(
            'TERMINAL', {'canonical_receipt': {'reference': 'a', 'bytes': 1,
                                               'sha256': 'z' * 64}}))))
    assert error.value.code == 'MESSAGE_TERMINAL_REFERENCE_INVALID'


# ---------------------------------------------------------------------- plan
def test_the_plan_requires_the_complete_sixteen_rows():
    """I12: the parent records the complete sixteen row plan before it sends."""
    with pytest.raises(SupervisionError) as error:
        SealedPlan(sixteen_rows()[:15])
    assert error.value.code == 'PLAN_INCOMPLETE'
    with pytest.raises(SupervisionError) as error:
        SealedPlan(sixteen_rows() + [dict(sixteen_rows()[0], ordinal=17)])
    assert error.value.code == 'PLAN_INCOMPLETE'
    duplicated = sixteen_rows()
    duplicated[3] = dict(duplicated[3], ordinal=2)
    with pytest.raises(SupervisionError) as error:
        SealedPlan(duplicated)
    assert error.value.code == 'PLAN_ORDINAL_INVALID'
    sealed = plan()
    assert len(sealed.rows) == 16
    assert len(sealed.digest) == 64


# ----------------------------------------------------------------- deadlines
class SteppingClock:
    """A deterministic monotonic clock of the offline tests."""

    def __init__(self, step=1.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        value = self.now
        self.now += self.step
        return value


class FakeProcess:
    """A fake child process with real pipes and no real process."""

    def __init__(self, pid=4242):
        self.out_read, self.out_write = os.pipe()
        self.err_read, self.err_write = os.pipe()
        self.in_read, self.in_write = os.pipe()
        self.stdout = os.fdopen(self.out_read, 'rb')
        self.stderr = os.fdopen(self.err_read, 'rb')
        self.stdin = os.fdopen(self.in_write, 'wb')
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False

    def emit(self, value):
        os.write(self.out_write, encoded(value) + b'\n')

    def emit_raw(self, raw):
        os.write(self.out_write, raw)

    def close_stdout(self):
        os.close(self.out_write)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def make_supervisor(tmp_path, *, process, clock=None, **kwargs):
    arguments = dict(command=['python3', '-B', 'worker.py'], run_id=RUN_ID,
                     candidate_sha=CANDIDATE_SHA, authorization_sha256=AUTHORIZATION_SHA,
                     plan=plan(), root=tmp_path)
    arguments.update(kwargs)
    supervisor = ParentSupervisor(clock=clock or SteppingClock(), **arguments)
    supervisor.spawner = lambda command: process
    supervisor.poll_interval = 0.001
    return supervisor


def test_the_production_defaults_are_the_frozen_ones():
    """I11: the production defaults stay 10800 / 600 / 21600."""
    assert PHASE_TIMEOUT_SECONDS == 10800
    assert HISTORY_TIMEOUT_SECONDS == 600
    assert CHILD_TIMEOUT_SECONDS == 21600
    supervisor = make_supervisor(Path('/tmp'), process=FakeProcess())
    assert supervisor.phase_timeout == 10800
    assert supervisor.history_timeout == 600
    assert supervisor.child_timeout == 21600


def test_the_phase_deadline_is_fixed_from_the_start(tmp_path):
    """I11: the phase deadline starts when the parent starts the worker."""
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock,
                                  phase_timeout=100, child_timeout=1000)
    supervisor.start()
    assert supervisor.phase_deadline == 100
    assert supervisor.child_deadline == 1000
    assert supervisor.effective_phase_deadline == 100


def test_the_earlier_child_deadline_wins(tmp_path):
    """I11: the effective deadline is the earlier of the phase and the child."""
    clock = SteppingClock(step=0.0)
    supervisor = make_supervisor(tmp_path, process=FakeProcess(), clock=clock,
                                 phase_timeout=1000, child_timeout=100)
    supervisor.start()
    assert supervisor.effective_phase_deadline == 100


def test_the_history_deadline_is_fixed_at_the_first_history_wait(tmp_path):
    """I10: the history deadline is fixed once and never extended."""
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock,
                                 phase_timeout=1000, history_timeout=600,
                                 child_timeout=21600)
    supervisor.start()
    supervisor._fix_history_deadline('SYN-01')
    first = supervisor.history_deadlines['SYN-01']
    assert first == 600
    clock.now = 100.0
    supervisor._fix_history_deadline('SYN-01')
    assert supervisor.history_deadlines['SYN-01'] == first


def test_an_expired_history_deadline_is_detected(tmp_path):
    """I10: a history wait beyond its fixed deadline is a refusal."""
    clock = SteppingClock(step=0.0)
    supervisor = make_supervisor(tmp_path, process=FakeProcess(), clock=clock,
                                 phase_timeout=1000, history_timeout=600)
    supervisor.start()
    supervisor._fix_history_deadline('SYN-01')
    clock.now = 700.0
    assert supervisor._deadline_state() == 'HISTORY_DEADLINE_EXCEEDED:SYN-01'
    clock.now = 2000.0
    assert supervisor._deadline_state() == 'PHASE_DEADLINE_EXCEEDED'


# ---------------------------------------------------------- the parent hold
def test_the_parent_terminates_only_the_handle_it_holds(tmp_path):
    """I08/I24: the parent stops the worker that it started itself."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process)
    supervisor.start()
    evidence = supervisor.run()
    assert process.terminated is True
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['cleanup']['exit_code'] == -15
    assert evidence['cleanup']['native_cleanup_proven'] is False
    assert evidence['native_service_cleanup_proven'] is False


def test_an_unknown_outcome_retains_the_root_and_the_reservation(tmp_path):
    """I14: an unknown outcome keeps the root and the reservation."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process)
    supervisor.start()
    supervisor.violation = 'WORKER_EXITED_WITHOUT_TERMINAL'
    evidence = supervisor.run()
    assert evidence['unknown_outcome'] is True
    assert evidence['root_retained'] is True
    assert evidence['reservation_retained'] is True
    assert evidence['archive_allowed'] is False
    assert evidence['refund_allowed'] is False
    assert evidence['resend_allowed'] is False
    assert evidence['next_phase_allowed'] is False


def test_the_row_denominator_never_shrinks(tmp_path):
    """I13: the sixteen rows stay, unstarted ones are BLOCKED."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process)
    supervisor.start()
    supervisor.violation = 'WORKER_EXITED_WITHOUT_TERMINAL'
    evidence = supervisor.run()
    assert len(evidence['row_status']) == 16
    assert set(evidence['row_status'].values()) == {'BLOCKED'}


def test_a_started_row_without_a_verified_receipt_is_a_failure(tmp_path):
    """I13: a started row that is not proven by the receipt is a failure."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process)
    supervisor.start()
    supervisor.state.row_events['SYN-01'] = ['ROW_STARTED']
    supervisor.violation = 'WORKER_EXITED_WITHOUT_TERMINAL'
    evidence = supervisor.run()
    assert evidence['row_status']['SYN-01'] == 'FAIL'
    assert evidence['row_status']['SYN-02'] == 'BLOCKED'


def test_the_parent_reads_the_real_canonical_receipt_bytes(tmp_path):
    """I16/I24: the parent reads the actual bytes of the canonical receipt."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    payload = json.dumps({'rows': [{'asset_id': 'SYN-01', 'execution_status': 'PASS'}]}).encode()
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(payload)
    process = FakeProcess()
    process.emit(message('STARTED', {}, sequence=1))
    process.emit(message('TERMINAL', {'canonical_receipt': {
        'reference': 'temp/s3-quality/qd-receipt.json', 'bytes': len(payload),
        'sha256': hashlib.sha256(payload).hexdigest()}}, sequence=2))
    process.close_stdout()
    process.returncode = 0
    supervisor = make_supervisor(tmp_path, process=process, root=root)
    evidence = supervisor.run()
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['row_status']['SYN-01'] == 'PASS'
    assert evidence['row_status']['SYN-02'] == 'BLOCKED'
    assert evidence['cleanup']['proven_stopped'] is True


def test_a_wrong_terminal_hash_is_not_verified(tmp_path):
    """I24: a canonical receipt whose bytes do not match is not accepted."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(b'{"rows": []}')
    process = FakeProcess()
    process.emit(message('STARTED', {}, sequence=1))
    process.emit(message('TERMINAL', {'canonical_receipt': {
        'reference': 'temp/s3-quality/qd-receipt.json', 'bytes': 12,
        'sha256': '0' * 64}}, sequence=2))
    process.close_stdout()
    process.returncode = 0
    supervisor = make_supervisor(tmp_path, process=process, root=root)
    evidence = supervisor.run()
    assert evidence['canonical_receipt_verified'] is False
    assert evidence['root_retained'] is True


def test_a_terminal_reference_outside_the_root_is_refused(tmp_path):
    """I24: a terminal reference that escapes the root is refused."""
    root = tmp_path / 'run'
    root.mkdir()
    process = FakeProcess()
    process.emit(message('STARTED', {}, sequence=1))
    process.emit(message('TERMINAL', {'canonical_receipt': {
        'reference': '../outside.json', 'bytes': 12, 'sha256': '0' * 64}}, sequence=2))
    process.close_stdout()
    process.returncode = 0
    supervisor = make_supervisor(tmp_path, process=process, root=root)
    evidence = supervisor.run()
    assert evidence['canonical_receipt_verified'] is False


# ------------------------------------------------------------------ recovery
def test_a_recovery_without_custody_is_blocked():
    """I15: without the original custody evidence the recovery is blocked."""
    evidence = RecoveryEntry().recover()
    assert evidence['status'] == 'BLOCKED'
    assert evidence['replay_allowed'] is False
    assert evidence['resend_allowed'] is False


def test_a_recovery_never_replays_and_never_resends():
    """I15: the recovery coordinates the cleanup and the existing evidence."""
    custody = {'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
               'authorization_sha256': AUTHORIZATION_SHA, 'pid': 4242,
               'birth': {'linux_start_ticks': 99}}
    evidence = RecoveryEntry(custody=custody).recover()
    assert evidence['status'] == 'RECOVERED_FOR_CLEANUP_ONLY'
    assert evidence['replay_allowed'] is False
    assert evidence['resend_allowed'] is False
    assert evidence['refund_allowed'] is False
    assert evidence['native_cleanup_proven'] is False


def test_a_recovery_does_not_trust_a_pid_from_a_file(tmp_path):
    """I15: the recovery never selects a process by a self reported PID."""
    marker = tmp_path / 'worker.pid'
    marker.write_text('31337')
    evidence = RecoveryEntry().recover()
    assert evidence['status'] == 'BLOCKED'
    assert 'pid' not in evidence


# ------------------------------------------------------------- worker entry
def dependency_manifest():
    """The explicit manifest of the existing dependency paths.

    The manifest names the exact existing directory and the exact files.  No
    dependency is downloaded and no environment variable is trusted.
    """
    import importlib.util
    spec = importlib.util.find_spec('PIL')
    package = Path(spec.origin).parent
    names = ['__init__.py', '_version.py', 'Image.py', 'PngImagePlugin.py',
             '_imaging.cpython-312-x86_64-linux-gnu.so']
    files = []
    for name in names:
        path = package / name
        if not path.is_file():
            continue
        files.append({'path': str(path),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'schema': 'lvw.s3-dependency-path-manifest/1',
            'scope': 'named_files_only_not_a_transitive_seal',
            'transitive_seal_complete': False,
            'path': str(package.parent), 'files': files}


def build_worker_context(tmp_path, root, *, clock):
    """The sealed data context of one supervised quality run."""

    for name in ('input', 'output', 'temp'):
        (root / name).mkdir(parents=True, exist_ok=True)
    rows = _p3b._build_sources(root)
    projection = _p3b._projection_bytes(rows)
    projection_path = tmp_path / 'projection.json'
    projection_path.write_bytes(projection)
    source_identity = _p3b._source_identity()
    source_path = tmp_path / 'source-identity.json'
    source_path.write_text(json.dumps(source_identity))
    proof = _p3b._parent_proof(clock)
    budget_path = tmp_path / 'parent-budget.json'
    budget_path.write_text(json.dumps(proof))
    binding = _p3b._binding()
    binding_path = tmp_path / 'binding.json'
    binding_path.write_text(json.dumps(binding))
    manifest_path = tmp_path / 'dependency-manifest.json'
    manifest_path.write_text(json.dumps(dependency_manifest()))
    document = {
        'schema': 'lvw.s3-quality-worker-context/1', 'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA, 'authorization_sha256': AUTHORIZATION_SHA,
        'root': str(root), 'projection_path': str(projection_path),
        'projection_sha256': hashlib.sha256(projection).hexdigest(),
        'source_identity_path': str(source_path),
        'source_identity_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'parent_budget_path': str(budget_path),
        'parent_budget_sha256': hashlib.sha256(budget_path.read_bytes()).hexdigest(),
        'binding_path': str(binding_path),
        'binding_sha256': hashlib.sha256(binding_path.read_bytes()).hexdigest(),
        'dependency_manifest_path': str(manifest_path),
        'dependency_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'driver': 'fixture',
        'driver_arguments': {key: '/tmp/' + key for key in
                             ('powershell', 'comfy_main', 'comfy_python', 'ollama_exe',
                              'ffmpeg_exe', 'nvidia_exe')},
        'canonical_receipt_reference': 'temp/s3-quality/qd-receipt.json',
    }
    context_path = tmp_path / 'context.json'
    context_path.write_text(json.dumps(document))
    return context_path, rows


def test_the_worker_really_invokes_the_quality_phase(tmp_path):
    """I07: the worker entry really invokes the accepted quality phase."""
    root = tmp_path / 'run'
    clock = _p3b.FakeClock(step=0.0)
    context_path, rows = build_worker_context(tmp_path, root, clock=clock)
    context = WorkerContext.load(context_path)
    events = []

    def emit(event, payload):
        events.append((event, payload))

    driver = _p3b.SyntheticDriver(root, None)
    receipt = run_worker(context, driver=driver, emit=emit, clock=clock, sleep=clock.sleep)
    names = [name for name, _ in events]
    assert names[0] == 'STARTED'
    assert names[-1] == 'TERMINAL'
    assert names.count('ROW_STARTED') == 16
    assert names.count('ROW_FINISHED') == 16
    assert names.count('HISTORY_WAIT_STARTED') == 16
    assert receipt['fixed_denominator'] == {'images': 10, 'videos': 6, 'total': 16}
    canonical = root / 'temp/s3-quality/qd-receipt.json'
    assert canonical.is_file()
    terminal = events[-1][1]['canonical_receipt']
    assert terminal['reference'] == 'temp/s3-quality/qd-receipt.json'
    assert terminal['bytes'] == canonical.stat().st_size
    assert terminal['sha256'] == hashlib.sha256(canonical.read_bytes()).hexdigest()
    assert receipt['stage_pass_claim'] is False


def test_the_history_wait_is_announced_before_the_row_finishes(tmp_path):
    """I10: the history start is announced before the row finishes."""
    root = tmp_path / 'run'
    clock = _p3b.FakeClock(step=0.0)
    context_path, rows = build_worker_context(tmp_path, root, clock=clock)
    context = WorkerContext.load(context_path)
    events = []
    driver = _p3b.SyntheticDriver(root, None)
    run_worker(context, driver=driver, emit=lambda event, payload: events.append(event),
               clock=clock, sleep=clock.sleep)
    first = events.index('HISTORY_WAIT_STARTED')
    assert events.index('ROW_STARTED') < first
    assert events.index('ROW_FINISHED') > first


def test_a_context_with_a_wrong_seal_is_refused(tmp_path):
    """I23: a context file whose seal does not match is refused."""
    root = tmp_path / 'run'
    clock = _p3b.FakeClock(step=0.0)
    context_path, rows = build_worker_context(tmp_path, root, clock=clock)
    context_path.write_text(context_path.read_text() + ' ')
    with pytest.raises(WorkerError) as error:
        WorkerContext.load(context_path, expected_sha256='0' * 64)
    assert error.value.code == 'WORKER_FILE_SEAL_MISMATCH'


def test_a_context_with_an_unknown_key_is_refused(tmp_path):
    """I23: a context with an extra key is refused."""
    root = tmp_path / 'run'
    clock = _p3b.FakeClock(step=0.0)
    context_path, rows = build_worker_context(tmp_path, root, clock=clock)
    document = json.loads(context_path.read_text())
    document['unexpected'] = True
    context_path.write_text(json.dumps(document))
    with pytest.raises(WorkerError) as error:
        WorkerContext.load(context_path)
    assert error.value.code == 'WORKER_CONTEXT_KEY_SET_INVALID'


# -------------------------------------------------- the frozen command plans
def test_the_production_command_is_the_fixed_worker():
    """I23: the production entry starts exactly the fixed quality worker."""
    command = build_production_command('/tmp/context.json')
    assert command[1:4] == ['-I', '-B', str(PACK_ROOT / 'tools/v0_s3_quality_worker.py')]
    assert command[-2:] == ['--context', '/tmp/context.json']
    assert 'fixture' not in ' '.join(command)


def test_the_fixture_command_is_one_enumerated_scenario():
    """I23: the fixture command is one member of a closed enumeration."""
    for scenario in FIXTURE_SCENARIOS:
        command = build_fixture_command(scenario)
        assert command[1:5] == ['-I', '-S', '-B', str(PACK_ROOT /
                                                     'tools/fixtures/v0_s3_supervisor_fixture.py')]
        assert command[5] == '--scenario'
        assert command[6] == scenario
    with pytest.raises(SupervisionError) as error:
        build_fixture_command('not-a-scenario')
    assert error.value.code == 'FIXTURE_SCENARIO_UNKNOWN'


# ------------------------------------------- the gated fixture process tests
def machine_binding():
    """The root machine binding of the finite fixture process plan."""
    path = os.environ.get('LVW_S3_MACHINE_BINDING')
    if not path:
        return None
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get('kind') != 'S3_INTEGRATION_MACHINE_BINDING/1':
        return None
    if document.get('execution_permitted') is not True:
        return None
    return document


MACHINE_BINDING = machine_binding()
requires_machine_gate = pytest.mark.skipif(
    MACHINE_BINDING is None,
    reason='the finite fixture process machine gate is not bound by the root')


def fixture_context(guard_root, root, rows):
    """The bounded context document of one fixture scenario.

    The document lives in the fresh runner owned root.  No arbitrary private
    path is accepted by the executor.
    """
    document = {'run_id': RUN_ID, 'candidate_sha': CANDIDATE_SHA,
                'authorization_sha256': AUTHORIZATION_SHA, 'root': str(root),
                'terminal_reference': 'temp/s3-quality/qd-receipt.json',
                'plan': rows}
    path = Path(guard_root) / 'fixture-context.json'
    path.write_text(json.dumps(document))
    return path


def run_fixture(tmp_path, scenario, *, rows=None, root=None, phase_seconds=1.0,
                grace_seconds=0.25):
    """Run one enumerated fixture scenario under the real parent.

    The executor of the guarded runner owns the start: it charges the shared
    counter before the operating system action, it holds the original child
    handle and it enforces the independent per child deadline.  The parent
    supervisor under test never starts a process itself.
    """
    rows = rows if rows is not None else sixteen_rows()
    root = root if root is not None else (tmp_path / 'run')
    (root / 'temp/s3-quality').mkdir(parents=True, exist_ok=True)
    guard_root = os.environ.get('LVW_S3_GUARD_ROOT')
    if not guard_root:
        raise AssertionError('the guarded runner did not publish its owned root')
    executor = bound_executor()
    if executor is None:
        raise AssertionError('the guarded runner did not publish its executor')
    context = fixture_context(guard_root, root, rows)
    os.environ['LVW_S3_FIXTURE_CONTEXT'] = str(context)
    command = build_fixture_command(scenario,
                                    python=MACHINE_BINDING['python']['path'])
    supervisor = ParentSupervisor(command=command, run_id=RUN_ID,
                                  candidate_sha=CANDIDATE_SHA,
                                  authorization_sha256=AUTHORIZATION_SHA,
                                  plan=plan(), root=root,
                                  phase_timeout=phase_seconds,
                                  child_timeout=phase_seconds * 2,
                                  grace_seconds=grace_seconds)
    supervisor.spawner = executor.spawn
    try:
        return supervisor.run()
    finally:
        os.environ.pop('LVW_S3_FIXTURE_CONTEXT', None)


@requires_machine_gate
def test_the_fixture_clean_terminal_is_verified_by_the_parent(tmp_path):
    """I07/I24: the real fixture process ends with a verified terminal."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    payload = json.dumps({'rows': [{'asset_id': 'SYN-01', 'execution_status': 'PASS'}]}).encode()
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(payload)
    evidence = run_fixture(tmp_path, 'clean_terminal', root=root)
    assert evidence['terminal_received'] is True
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['row_status']['SYN-01'] == 'PASS'
    assert evidence['cleanup']['proven_stopped'] is True


@requires_machine_gate
def test_a_blocking_callback_is_actually_stopped(tmp_path):
    """I08: a blocked callback is stopped by the parent, not by a timeout text."""
    evidence = run_fixture(tmp_path, 'blocking_callback')
    assert evidence['protocol_violation'] == 'PHASE_DEADLINE_EXCEEDED'
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['cleanup']['exit_code'] is not None
    assert evidence['root_retained'] is True
    assert evidence['resend_allowed'] is False


@requires_machine_gate
def test_a_blocking_persistence_is_actually_stopped(tmp_path):
    """I09: a blocked persistence is stopped by the parent."""
    evidence = run_fixture(tmp_path, 'blocking_persistence')
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


@requires_machine_gate
@pytest.mark.parametrize('scenario,code', [
    ('history_replay', 'MESSAGE_HISTORY_STARTED_REPEATED'),
    ('sequence_reversal', 'MESSAGE_SEQUENCE_NOT_INCREASING'),
    ('duplicate_sequence', 'MESSAGE_SEQUENCE_NOT_INCREASING'),
    ('oversize_message', 'MESSAGE_TOO_LARGE'),
    ('foreign_identity', 'MESSAGE_RUN_ID_MISMATCH'),
    ('unexpected_field', 'MESSAGE_KEY_SET_INVALID'),
    ('nonfinite_number', 'MESSAGE_NONFINITE_NUMBER'),
    ('early_exit', 'WORKER_EXITED_WITHOUT_TERMINAL'),
    ('message_flood', 'MESSAGE_COUNT_EXCEEDED'),
])
def test_a_protocol_violation_is_refused(tmp_path, scenario, code):
    """I12/I13: every protocol violation is a stable refusal."""
    evidence = run_fixture(tmp_path, scenario)
    assert evidence['protocol_violation'] == code
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


@requires_machine_gate
def test_a_bad_terminal_reference_is_refused(tmp_path):
    """I24: a terminal reference outside the bound root is refused."""
    evidence = run_fixture(tmp_path, 'bad_terminal_reference')
    assert evidence['canonical_receipt_verified'] is False
    assert evidence['root_retained'] is True


# ------------------------------------- the finite CPU executor, zero process
def fake_root_binding(tmp_path, *, counter_path, budget_id='budget-under-test',
                      limits=None, pins=None, candidate_sha=None, python=None):
    """A sealed binding that the root would issue, built for the unit tests."""
    limits = limits or {'max_total_starts': 24,
                        'max_starts_by_role': {'implementation': 16,
                                               'independent_review': 8},
                        'max_concurrent': 2, 'per_process_seconds': 10,
                        'shared_pool_seconds': 180,
                        'session_wall_cap_seconds': 60,
                        'cleanup_reserve_seconds': 30,
                        'per_child_termination_margin_seconds': 2,
                        'per_child_kill_seconds': 1}
    supervisor = PACK_ROOT / 'tools/v0_s3_supervisor.py'
    binding = {
        'kind': 'S3_INTEGRATION_MACHINE_BINDING/1',
        'execution_permitted': True,
        'candidate_sha': candidate_sha or EXECUTOR_MODULE.resolve_head_commit(REPOSITORY_ROOT),
        'python': python or {'path': sys.executable,
                             'sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()},
        'argv_prefix': [sys.executable, '-I', '-S', '-B',
                        str(PACK_ROOT / 'tools/fixtures/v0_s3_supervisor_fixture.py'),
                        '--scenario'],
        'allowed_scenarios': ['clean_terminal'],
        'source_pins': pins if pins is not None else {
            'tools/v0_s3_supervisor.py':
                hashlib.sha256(supervisor.read_bytes()).hexdigest()},
        'cpu_budget': dict({'counter_path': str(counter_path), 'budget_id': budget_id},
                           **limits),
    }
    path = tmp_path / 'binding.json'
    path.write_text(json.dumps(binding, sort_keys=True))
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), binding


def fake_root_counter(tmp_path, *, budget_id='budget-under-test', starts_total=0,
                      by_role=None, charges=None, active=True, name='counter.json',
                      reserved_wall_seconds=0.0):
    """The counter that the root creates.  The executor never creates it."""
    document = {'kind': 'lvw.s3-cpu-budget/1', 'budget_id': budget_id,
                'starts_total': starts_total,
                'starts_by_role': by_role if by_role is not None
                else {'implementation': 0, 'independent_review': 0},
                'spent_wall_seconds': 0.0,
                'reserved_wall_seconds': reserved_wall_seconds,
                'active': active, 'charges': charges if charges is not None else [],
                'sessions': []}
    path = tmp_path / name
    path.write_text(json.dumps(document, sort_keys=True))
    return path


def build_test_executor(tmp_path, *, counter_path, binding_digest, role='implementation',
                        session_id=None, clock=None):
    return EXECUTOR_MODULE.build_executor(
        binding_path=str(tmp_path / 'binding.json'), binding_sha256=binding_digest,
        role=role, repository_root=REPOSITORY_ROOT, package_root=PACK_ROOT,
        guard_root=tmp_path, clock=clock, session_id=session_id)


def executor_prefix():
    return [sys.executable, '-I', '-S', '-B',
            str(PACK_ROOT / 'tools/fixtures/v0_s3_supervisor_fixture.py'), '--scenario']


def context_inside(tmp_path):
    path = tmp_path / 'fixture-context.json'
    path.write_text(json.dumps({'run_id': RUN_ID}))
    os.environ['LVW_S3_FIXTURE_CONTEXT'] = str(path)
    return path


def test_the_executor_refuses_a_missing_counter(tmp_path):
    """G1: a missing counter is a refusal, never an empty budget."""
    counter = tmp_path / 'missing-counter.json'
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_COUNTER_MISSING'
    assert not counter.exists()


def test_the_executor_refuses_a_binding_digest_drift(tmp_path):
    """G2: the issuer proof is the path and the digest of the root binding."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    # The root supplies the digest out of band; a drifted document is not
    # issuer proof even when it has the right kind.
    executor = build_test_executor(tmp_path, counter_path=counter,
                                   binding_digest='0' * 64)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'BINDING_DIGEST_DRIFT'
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_executor_refuses_a_source_pin_drift_before_the_charge(tmp_path):
    """G2: a drifted source pin refuses the start before the OS action."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter,
                                         pins={'tools/v0_s3_supervisor.py': '0' * 64})
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code.startswith('PIN_DRIFT')
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_executor_refuses_a_candidate_drift(tmp_path):
    """G2: the actual candidate is verified before every spawn."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter,
                                         candidate_sha='1' * 40)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code in ('BINDING_CANDIDATE_MISMATCH', 'CANDIDATE_DRIFT')
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_executor_refuses_an_inactive_or_foreign_counter(tmp_path):
    """G1: an inactive counter and a foreign budget identity are refused."""
    counter = fake_root_counter(tmp_path, active=False)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_COUNTER_INACTIVE'

    counter = fake_root_counter(tmp_path, budget_id='other-budget')
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_COUNTER_IDENTITY_MISMATCH'


def test_the_executor_refuses_an_exhausted_total_or_role_budget(tmp_path):
    """G1: the shared total and the role budget are enforced."""
    counter = fake_root_counter(tmp_path, starts_total=24,
                                by_role={'implementation': 16, 'independent_review': 8})
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_TOTAL_BUDGET_EXCEEDED'

    counter = fake_root_counter(tmp_path, starts_total=16,
                                by_role={'implementation': 16, 'independent_review': 0})
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_ROLE_BUDGET_EXCEEDED'


def test_the_executor_refuses_beyond_the_concurrency_limit(tmp_path):
    """G3: the concurrency bound is enforced by the shared counter."""
    charges = [{'index': index, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'started_wall': 0.0, 'state': 'STARTED', 'exit_code': None,
                'pid': None, 'birth': None, 'finished_wall': None,
                'spent_wall_seconds': None} for index in range(2)]
    counter = fake_root_counter(tmp_path, starts_total=2,
                                by_role={'implementation': 2, 'independent_review': 0},
                                charges=charges)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_CONCURRENCY_LIMIT'


def test_the_charge_is_written_before_the_start_and_is_never_removed(tmp_path):
    """G1: the charge happens before the start and is never refunded."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert document['starts_by_role']['implementation'] == 1
    assert len(document['charges']) == 1
    # The charge is pending before the operating system action and it only
    # becomes started when the original handle has been taken.
    assert document['charges'][0]['state'] == 'PENDING'
    executor.counter.mark_started(0, pid=os.getpid(), birth={'linux_start_ticks': 1})
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'STARTED'
    executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 2
    assert len(document['charges']) == 2


def test_the_executor_refuses_a_context_outside_the_guard_root(tmp_path, monkeypatch):
    """G4: the bounded context document lives in the runner owned root."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    outside = tmp_path.parent / 'outside-context.json'
    outside.write_text(json.dumps({'run_id': RUN_ID}))
    monkeypatch.setenv('LVW_S3_FIXTURE_CONTEXT', str(outside))
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'FIXTURE_CONTEXT_OUTSIDE_GUARD_ROOT'
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_executor_refuses_a_closed_admission_window(tmp_path):
    """G3: the admission window is derived from the shared remaining pool."""
    counter = fake_root_counter(tmp_path, reserved_wall_seconds=179.0)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    # A fresh invocation of the executor starts its own clock at zero, but
    # the shared pool is nearly exhausted: the start is refused before the
    # operating system action.
    executor.clock = lambda: 0.0
    executor.reserve_session()
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'SESSION_ADMISSION_WINDOW_CLOSED'
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_shared_wall_pool_refuses_an_exhausted_pool(tmp_path):
    """G1: the shared wall pool is shared across invocations and rebinds."""
    counter = fake_root_counter(tmp_path, reserved_wall_seconds=180.0)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.reserve_session()
    assert error.value.code == 'SHARED_WALL_POOL_EXHAUSTED'


def test_the_session_reservation_is_atomic_and_idempotent(tmp_path):
    """G1: one session never reserves the shared pool twice."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    first = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                session_id='session-fixed')
    record = first.reserve_session()
    assert record['reserved_wall_seconds'] == 60
    document = json.loads(counter.read_text())
    assert document['reserved_wall_seconds'] == 60
    # the same runtime owner is idempotent and never rebases the window
    again = first.reserve_session()
    assert again['reserved_wall_seconds'] == 60
    assert again['admission_deadline_wall'] == record['admission_deadline_wall']
    document = json.loads(counter.read_text())
    assert document['reserved_wall_seconds'] == 60
    assert len(document['sessions']) == 1
    # a reconstructed executor may not acquire a fresh window
    second = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                 session_id='session-fixed')
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        second.reserve_session()
    assert error.value.code == 'CPU_SESSION_OWNER_MISMATCH'


def test_the_session_settlement_is_exactly_once_and_accounts_the_actual_wall(tmp_path):
    """G1: the session is settled once and the actual wall is accounted once."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    executor.reserve_session()
    executor.session_started = 0.0
    executor.clock = lambda: 9.0
    spent = executor.settle_session()
    assert spent == 9.0
    assert executor.settle_session() is None
    document = json.loads(counter.read_text())
    assert document['sessions'][0]['state'] == 'SETTLED'
    assert document['sessions'][0]['spent_wall_seconds'] == 9.0
    assert document['spent_wall_seconds'] == 9.0


def test_an_unknown_charge_keeps_its_concurrency_slot(tmp_path):
    """G2: an unresolved start stays occupied and blocks a new admission."""
    charges = [{'index': 0, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'started_wall': 0.0, 'state': 'UNKNOWN', 'exit_code': None,
                'pid': None, 'birth': None, 'finished_wall': None,
                'spent_wall_seconds': None, 'settled': True},
               {'index': 1, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'started_wall': 0.0, 'state': 'STARTED', 'exit_code': None,
                'pid': None, 'birth': None, 'finished_wall': None,
                'spent_wall_seconds': None, 'settled': False}]
    counter = fake_root_counter(tmp_path, starts_total=2,
                                by_role={'implementation': 2, 'independent_review': 0},
                                charges=charges)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    # The unknown charge still holds its slot: an unresolved start is never
    # released by a late settlement.
    assert executor.counter._occupied(json.loads(counter.read_text())) == 2
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'CPU_CONCURRENCY_LIMIT'


def test_a_repeated_settlement_can_neither_free_an_unknown_nor_double_charge(tmp_path):
    """G2: the settlement of a charge happens exactly once."""
    charges = [{'index': 0, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'started_wall': 0.0, 'state': 'STARTED', 'exit_code': None,
                'pid': None, 'birth': None, 'finished_wall': None,
                'spent_wall_seconds': None, 'settled': False}]
    counter = fake_root_counter(tmp_path, starts_total=1,
                                by_role={'implementation': 1, 'independent_review': 0},
                                charges=charges)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    assert executor.counter.finish(0, state='UNKNOWN', exit_code=None, spent=1.0) is True
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'UNKNOWN'
    # the child keeps its own observed lifetime; the global wall is the
    # session wall and is accounted by the settlement of the session
    assert document['charges'][0]['observed_lifetime_seconds'] == 1.0
    assert document['spent_wall_seconds'] == 0.0
    assert executor.counter.finish(0, state='STOPPED', exit_code=0, spent=1.0) is False
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'UNKNOWN'
    assert document['spent_wall_seconds'] == 0.0


def test_the_custody_carries_the_birth_of_the_held_handle(tmp_path):
    """G5: the completion proof carries the birth of the process it holds."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)

    class FakeProcess:
        pid = os.getpid()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    process = FakeProcess()
    executor.register(process)
    entry = executor.children[0]
    assert entry['state'] == 'STARTED'
    assert entry['pid'] == os.getpid()
    assert entry['birth'] is not None
    assert 'linux_start_ticks' in entry['birth']
    assert entry['birth'] == EXECUTOR_MODULE.process_birth(os.getpid())


def test_the_bounded_termination_starts_before_the_per_child_deadline(tmp_path):
    """G5: the bounded termination starts early enough for the whole budget."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = type('Clock', (), {'now': 0.0, '__call__': lambda self: self.now})()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class FakeProcess:
        pid = os.getpid()

        def __init__(self):
            self.terminated = False
            self.killed = False

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    process = FakeProcess()
    executor.register(process)
    entry = executor.children[0]
    clock.now = 9.0  # past the margin of the ten second per child budget
    deadline = time.monotonic() + 3.0
    while not entry['timed_out'] and time.monotonic() < deadline:
        time.sleep(0.02)
    assert entry['timed_out'] is True
    assert process.terminated is True
    executor.revoke_admissions()
    executor.reap()


def test_the_revoked_or_uncertain_session_refuses_a_new_start(tmp_path):
    """G3/G5: a revoked or uncertain session admits nothing further."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    executor.reserve_session()
    executor.revoke_admissions()
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'SESSION_ADMISSIONS_REVOKED'
    executor.revoked = False
    executor.uncertain = True
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'SESSION_UNCERTAIN_CUSTODY'


def test_the_executor_refuses_an_argv_outside_the_plan(tmp_path):
    """G4: only the frozen prefix plus one enumerated scenario is admitted."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['not-a-scenario'], None, None))
    assert error.value.code == 'SCENARIO_NOT_IN_PLAN'
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal', 'extra'],
                        None, None))
    assert error.value.code == 'ARGV_DIFFERS_FROM_PLAN'
    assert json.loads(counter.read_text())['starts_total'] == 0


def test_the_executor_refuses_a_non_inherited_environment(tmp_path):
    """G4: the plan requires the inherited environment of the runner."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None,
                        {'PATH': '/usr/bin'}))
    assert error.value.code == 'SPAWN_ENVIRONMENT_NOT_INHERITED'


def test_the_executor_refuses_a_cwd_outside_the_guard_root(tmp_path):
    """G4: the working directory stays inside the runner owned root."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'],
                        str(tmp_path.parent), None))
    assert error.value.code == 'SPAWN_CWD_OUTSIDE_GUARD_ROOT'


def test_the_executor_refuses_an_unknown_role(tmp_path):
    """G1: only the two sealed roles may charge the shared counter."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                            role='other')
    assert error.value.code == 'CPU_ROLE_INVALID'


# ---------------------------- the lifecycle corrections of the second review
def load_runner_module():
    """Load the guarded runner of the new report subtree."""
    path = PACK_ROOT / ('reports/v0-s3/product-gate0/implementation-integration-01/'
                        'run_guarded_checks.py')
    spec = importlib.util.spec_from_file_location('lvw_s3_guarded_runner', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER_MODULE = load_runner_module()


def fake_clock():
    return type('Clock', (), {'now': 0.0, '__call__': lambda self: self.now})()


def test_the_sixty_slice_gives_thirty_admission_and_thirty_cleanup(tmp_path):
    """A: the window is bounded by the actual reserved slice."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock, session_id='session-slice')
    record = executor.reserve_session()
    assert record['reserved_wall_seconds'] == 60
    assert record['admission_seconds'] == 30
    assert record['cleanup_seconds'] == 60
    assert abs(executor.admission_deadline - 30.0) < 0.5
    assert abs(executor.cleanup_deadline - 60.0) < 0.5
    context_inside(tmp_path)
    # inside the admission window the start is admitted
    clock.now = 29.0
    executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    # one over the admission boundary the start is refused
    clock.now = 30.5
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    assert error.value.code == 'SESSION_ADMISSION_WINDOW_CLOSED'


def test_a_second_executor_cannot_reset_the_window_of_the_same_session(tmp_path):
    """A: a reconstructed executor may not acquire a fresh wall window."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    first = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                session_id='session-owner')
    record = first.reserve_session()
    assert record['owner_id'] == first.owner_id
    second = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                 session_id='session-owner')
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        second.reserve_session()
    assert error.value.code == 'CPU_SESSION_OWNER_MISMATCH'
    # the same owner is idempotent and never rebases its deadline
    again = first.reserve_session()
    assert again['admission_deadline_wall'] == record['admission_deadline_wall']
    assert first.admission_deadline == first.admission_deadline


def test_the_global_wall_is_the_session_wall_and_not_the_child_sum(tmp_path):
    """A: the global actual wall is accounted once per session."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    first = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                session_id='session-one')
    second = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                 session_id='session-two')
    first.reserve_session()
    second.reserve_session()
    context_inside(tmp_path)
    first.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    first.counter.finish(0, state='STOPPED', exit_code=0, spent=7.5)
    document = json.loads(counter.read_text())
    # the child keeps its own observed lifetime and the global wall is untouched
    assert document['charges'][0]['observed_lifetime_seconds'] == 7.5
    assert document['spent_wall_seconds'] == 0.0
    first.session_started = 0.0
    first.clock = lambda: 12.0
    first.settle_session()
    second.session_started = 0.0
    second.clock = lambda: 20.0
    second.settle_session()
    document = json.loads(counter.read_text())
    assert document['spent_wall_seconds'] == 32.0
    # a repeated settlement is idempotent
    assert first.settle_session() is None
    document = json.loads(counter.read_text())
    assert document['spent_wall_seconds'] == 32.0


def test_the_finalizer_stops_a_live_child_that_is_still_young(tmp_path):
    """B: the finalizer stops a live original handle at once."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class LiveProcess:
        pid = os.getpid()

        def __init__(self):
            self.terminated = False
            self.killed = False
            self.waited = 0

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waited += 1
            if not self.terminated and not self.killed:
                raise AssertionError('the child was waited for without a stop')
            return 0

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

    process = LiveProcess()
    executor.register(process)
    entry = executor.children[0]
    clock.now = 1.0  # the child is one second old, far below the watchdog
    proofs = executor.reap()
    assert process.terminated is True
    assert entry['state'] == 'STOPPED'
    assert proofs[0]['proven'] is True


def test_a_failing_finalizer_cannot_skip_the_reaper_or_yield_pass(tmp_path):
    """C: a failing stream, hash or removal never bypasses the reaper."""
    class FaultyExecutor:
        def __init__(self):
            self.revoked = False
            self.reaped = False

        def revoke_admissions(self):
            self.revoked = True

        def reap(self):
            self.reaped = True
            return [{'proven': True, 'exit_code': 0}]

        def session_evidence(self):
            return {'kind': 'lvw.s3-finite-cpu-session/1', 'status': 'OK'}

    class FaultyHandle:
        def flush(self):
            raise OSError('injected flush failure')

        def close(self):
            raise OSError('injected close failure')

    owned = tmp_path / 'owned'
    owned.mkdir()
    executor = FaultyExecutor()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=FaultyHandle(),
        stderr_handle=FaultyHandle(), saved_out=-1, saved_err=-1, exit_code=0,
        source_hasher=lambda: (_ for _ in ()).throw(OSError('injected hash failure')),
        remover=lambda path: (_ for _ in ()).throw(OSError('injected removal failure')))
    assert executor.revoked is True
    assert executor.reaped is True
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    reasons = outcome['failure_reasons']
    for prefix in ('STDOUT_HANDLE_FLUSH_FAILED', 'STDOUT_RESTORE_FAILED',
                   'SOURCE_HASH_FAILED'):
        assert any(reason.startswith(prefix) for reason in reasons), prefix
    # the root is retained: an uncertain cleanup never deletes it
    assert any(reason.startswith('OWNED_ROOT_RETAINED') for reason in reasons)
    assert owned.exists()


def test_a_failing_root_removal_cannot_yield_pass(tmp_path):
    """C: a failing removal of the owned root is never a pass."""
    class EmptyExecutor:
        def revoke_admissions(self):
            return None

        def reap(self):
            return []

        def session_evidence(self):
            return {'kind': 'lvw.s3-finite-cpu-session/1', 'status': 'OK'}

    class GoodHandle:
        def flush(self):
            return None

        def close(self):
            return None

    owned = tmp_path / 'owned'
    owned.mkdir()
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    outcome = RUNNER_MODULE.finalize_session(
        executor=EmptyExecutor(), owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=saved_out, saved_err=saved_err, exit_code=0,
        source_hasher=lambda: {},
        remover=lambda path: (_ for _ in ()).throw(OSError('injected removal failure')))
    reasons = outcome['failure_reasons']
    assert any(reason.startswith('ROOT_REMOVAL_FAILED') for reason in reasons)
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert owned.exists()


def test_a_successful_finalizer_removes_the_root_and_keeps_the_proof(tmp_path):
    """C: a proven cleanup removes the owned root and stays a pass."""
    class EmptyExecutor:
        def __init__(self):
            self.reaped = False

        def revoke_admissions(self):
            return None

        def reap(self):
            self.reaped = True
            return []

        def session_evidence(self):
            return {'kind': 'lvw.s3-finite-cpu-session/1', 'status': 'OK'}

    class GoodHandle:
        def flush(self):
            return None

        def close(self):
            return None

    owned = tmp_path / 'owned'
    owned.mkdir()
    executor = EmptyExecutor()
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=saved_out, saved_err=saved_err, exit_code=0,
        source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    assert executor.reaped is True
    assert outcome['cleanup_proven'] is True
    assert outcome['exit_code'] == 0
    assert not owned.exists()
