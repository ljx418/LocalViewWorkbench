"""The offline supervision obligations of the S3-P4-OFFLINE workpack.

Section B: the bounded protocol, the sealed sixteen row plan, the fixed
deadlines, the parent held worker handle, the terminal receipt verification,
the quality worker entry and the recovery entry.

The process bearing scenarios are gated: they run only when the root machine
binding of the finite fixture process plan is present and says that the
execution is permitted.  Without that binding they are skipped, and the
zero process part of this module stays complete.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess as _subprocess
import sys
import threading
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
    CHILD_TIMEOUT_SECONDS, DRAIN_TIMEOUT_SECONDS, EVENTS, FIXTURE_SCENARIOS,
    HISTORY_TIMEOUT_SECONDS, MAX_MESSAGE_BYTES, MAX_MESSAGES, MAX_STREAM_BYTES,
    MESSAGE_INCOMPLETE_FRAME, MESSAGE_KEYS, PHASE_TIMEOUT_SECONDS, PROTOCOL_SCHEMA,
    STDERR_STREAM_DRAIN_INCOMPLETE, STDERR_STREAM_LIMIT_EXCEEDED,
    STDERR_STREAM_READ_FAILED, STDOUT_STREAM_DRAIN_INCOMPLETE,
    STDOUT_STREAM_LIMIT_EXCEEDED, STDOUT_STREAM_READ_FAILED, ParentSupervisor,
    ProtocolState, RecoveryEntry, SealedPlan, SupervisionError,
    _StreamReader, build_fixture_command, build_production_command, decode_message)

PACK_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACK_ROOT.parent
RUN_ID = 'synthetic-quality-run'
CANDIDATE_SHA = 'a' * 40
AUTHORIZATION_SHA = 'b' * 64
# The short synthetic run identity of the message count negative case.  The
# wire of that case has to stay inside the frozen byte budget of a stream,
# so the count - and not the byte budget - is the reason of its refusal.
# The identity is bound by the parent context and by the child messages in
# the very same way as every other identity; the candidate and the
# authorization keep their full length.
FLOOD_RUN_ID = 'syn1'
EXECUTOR_RELATIVE = ('reports/v0-s3/product-gate0/implementation-integration-01/'
                     'executor.py')


def _context_digest(context_path):
    """The sealed digest of a worker context document.

    The worker never computes the expectation of the seal of its own
    context: every load of a context is verified against a hash that the
    caller sealed before the run.
    """
    return hashlib.sha256(Path(context_path).read_bytes()).hexdigest()


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
        if self.out_write is None:
            return
        os.close(self.out_write)
        self.out_write = None

    def close_streams(self):
        """Close the write ends of the fake child.

        A child that is gone closes its own ends of the pipes.  The fake
        holds those ends, so the fake closes them when the child is gone.
        Without that the readers of the parent would never see the end of
        their stream and the parent would refuse a run that is really over.
        """
        for name in ('out_write', 'err_write', 'in_write'):
            descriptor = getattr(self, name, None)
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError:
                pass
            setattr(self, name, None)

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


# ------------------------------------------------- H: the history lifetime
def row_event(event, asset_id, ordinal, sequence):
    """One row event of the protocol, with its own sequence."""
    return message(event, {'asset_id': asset_id, 'ordinal': ordinal}, sequence=sequence)


def consume_until(supervisor, sequence, *, timeout=5.0):
    """Consume the protocol until the state has the given sequence."""
    end = time.monotonic() + timeout
    while supervisor.state.last_sequence < sequence and time.monotonic() < end:
        supervisor._consume_stdout()
        time.sleep(0.001)
    assert supervisor.state.last_sequence == sequence


def test_a_finished_row_does_not_constrain_the_later_rows(tmp_path):
    """H: a history deadline only constrains the wait of its own row.

    The first row started its history wait at zero and finished at ten, so
    its deadline of six hundred is in the past when the second row starts
    its own wait at five hundred.  The finished row does not interrupt the
    second row.
    """
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock,
                                  phase_timeout=100000, history_timeout=600,
                                  child_timeout=100000)
    supervisor.start()
    clock.now = 0.0
    process.emit(row_event('ROW_STARTED', 'SYN-01', 1, 1))
    process.emit(row_event('HISTORY_WAIT_STARTED', 'SYN-01', 1, 2))
    consume_until(supervisor, 2)
    assert supervisor.history_deadlines['SYN-01'] == 600
    clock.now = 10.0
    process.emit(row_event('ROW_FINISHED', 'SYN-01', 1, 3))
    consume_until(supervisor, 3)
    assert supervisor.history_completed == {'SYN-01'}
    clock.now = 500.0
    process.emit(row_event('ROW_STARTED', 'SYN-02', 2, 4))
    process.emit(row_event('HISTORY_WAIT_STARTED', 'SYN-02', 2, 5))
    consume_until(supervisor, 5)
    assert supervisor.history_deadlines['SYN-02'] == 1100
    # the deadline of the finished row is in the past and does not stop the
    # run of the second row
    for moment in (600.0, 601.0, 1099.0, 1100.0):
        clock.now = moment
        assert supervisor._deadline_state() is None


def test_the_history_deadline_of_the_active_row_is_exact_and_one_over(tmp_path):
    """H: the deadline of the active row is exact and one over is a refusal."""
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock,
                                  phase_timeout=100000, history_timeout=600,
                                  child_timeout=100000)
    supervisor.start()
    supervisor._fix_history_deadline('SYN-01')
    clock.now = 600.0
    assert supervisor._deadline_state() is None
    clock.now = 600.001
    assert supervisor._deadline_state() == 'HISTORY_DEADLINE_EXCEEDED:SYN-01'


def test_the_phase_and_the_child_deadline_stay_exact_and_one_over(tmp_path):
    """H: the phase and the child deadline are exact and one over refuses."""
    clock = SteppingClock(step=0.0)
    supervisor = make_supervisor(tmp_path, process=FakeProcess(), clock=clock,
                                 phase_timeout=1000, history_timeout=600,
                                 child_timeout=2000)
    supervisor.start()
    clock.now = 1000.0
    assert supervisor._deadline_state() is None
    clock.now = 1000.001
    assert supervisor._deadline_state() == 'PHASE_DEADLINE_EXCEEDED'
    clock = SteppingClock(step=0.0)
    supervisor = make_supervisor(tmp_path, process=FakeProcess(), clock=clock,
                                 phase_timeout=1000, history_timeout=600,
                                 child_timeout=100)
    supervisor.start()
    clock.now = 100.0
    assert supervisor._deadline_state() is None
    clock.now = 100.001
    assert supervisor._deadline_state() == 'PHASE_DEADLINE_EXCEEDED'


def test_the_history_audit_is_kept_and_a_row_is_not_reopened(tmp_path):
    """H: the audit of a finished row stays and the row is not reopened."""
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock,
                                  phase_timeout=100000, history_timeout=600,
                                  child_timeout=100000)
    supervisor.start()
    supervisor._fix_history_deadline('SYN-01')
    clock.now = 10.0
    supervisor._close_history_deadline('SYN-01')
    # the first start, the fixed deadline and the completion stay in the audit
    assert supervisor.history_deadlines['SYN-01'] == 600
    record = supervisor.history_records['SYN-01']
    assert record['first_start'] == 0.0
    assert record['deadline'] == 600
    assert record['completed_at'] == 10.0
    # the audit is not deleted to make a repeated start acceptable
    state = supervisor.state
    payload = {'asset_id': 'SYN-01', 'ordinal': 1}
    state.accept(decode_message(encoded(message('ROW_STARTED', payload, sequence=1))))
    state.accept(decode_message(encoded(message('HISTORY_WAIT_STARTED', payload,
                                                 sequence=2))))
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('ROW_STARTED', payload, sequence=3))))
    assert error.value.code == 'MESSAGE_ROW_STARTED_REPEATED'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('HISTORY_WAIT_STARTED', payload,
                                                     sequence=4))))
    assert error.value.code == 'MESSAGE_HISTORY_STARTED_REPEATED'
    state.accept(decode_message(encoded(message('ROW_FINISHED', payload, sequence=5))))
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('ROW_STARTED', payload, sequence=6))))
    assert error.value.code == 'MESSAGE_ROW_REOPENED'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('ROW_FINISHED', payload, sequence=7))))
    assert error.value.code == 'MESSAGE_ROW_FINISHED_REPEATED'
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(encoded(message('HISTORY_WAIT_STARTED', payload,
                                                     sequence=8))))
    assert error.value.code == 'MESSAGE_ROW_REOPENED'
    # the audit of the row is still there
    assert supervisor.history_records['SYN-01']['deadline'] == 600


def test_a_finished_row_does_not_stop_the_run(tmp_path):
    """H: the run of the later rows is not interrupted by a finished row."""
    root = tmp_path / 'run'
    root.mkdir()
    payload = b'{"rows": []}'
    (root / 'canonical.json').write_bytes(payload)
    clock = SteppingClock(step=0.0)
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=clock, root=root,
                                  phase_timeout=100000, history_timeout=600,
                                  child_timeout=100000)
    supervisor.start()
    written = 0
    clock.now = 0.0
    for value in (row_event('ROW_STARTED', 'SYN-01', 1, 1),
                  row_event('HISTORY_WAIT_STARTED', 'SYN-01', 1, 2)):
        process.emit(value)
        written += len(encoded(value)) + 1
    consume_until(supervisor, 2)
    clock.now = 10.0
    process.emit(row_event('ROW_FINISHED', 'SYN-01', 1, 3))
    written += len(encoded(row_event('ROW_FINISHED', 'SYN-01', 1, 3))) + 1
    consume_until(supervisor, 3)
    clock.now = 500.0
    for value in (row_event('ROW_STARTED', 'SYN-02', 2, 4),
                  row_event('HISTORY_WAIT_STARTED', 'SYN-02', 2, 5)):
        process.emit(value)
        written += len(encoded(value)) + 1
    consume_until(supervisor, 5)
    terminal = canonical_terminal(root, sequence=6)
    os.write(process.out_write, terminal)
    assert wait_for_the_reader(supervisor.stdout_reader, written + len(terminal))
    process.close_streams()
    process.returncode = 0
    clock.now = 601.0
    evidence = supervisor.run()
    # the deadline of the finished row did not interrupt the run
    assert evidence['protocol_violation'] is None
    assert evidence['unknown_outcome'] is False
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['history_completed_rows'] == ['SYN-01']
    assert evidence['history_deadlines'] == {'SYN-01': 600, 'SYN-02': 1100}
    assert evidence['history_records']['SYN-01']['completed_at'] == 10.0


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
    process.close_streams()
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
    process.close_streams()
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
    process.close_streams()
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
    context = WorkerContext.load(context_path, expected_sha256=_context_digest(context_path))
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
    context = WorkerContext.load(context_path, expected_sha256=_context_digest(context_path))
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
        WorkerContext.load(context_path, expected_sha256=_context_digest(context_path))
    assert error.value.code == 'WORKER_CONTEXT_KEY_SET_INVALID'


# -------------------------------------------------- the frozen command plans
def test_the_production_command_is_the_fixed_worker():
    """I23: the production entry starts exactly the fixed quality worker."""
    command = build_production_command('/tmp/context.json', context_sha256='a' * 64)
    assert command[1:4] == ['-I', '-B', str(PACK_ROOT / 'tools/v0_s3_quality_worker.py')]
    assert command[4:6] == ['--context', '/tmp/context.json']
    assert 'fixture' not in ' '.join(command)


def test_the_production_command_carries_the_pre_sealed_context_hash():
    """M03: the fixed command hands the sealed hash down to the worker.

    The worker never recomputes the expectation of the seal of its own
    context: the command carries the hash that the caller sealed, and the
    worker verifies every load against it.  The hash is the only internal
    argument that the command adds.
    """
    command = build_production_command('/tmp/context.json', context_sha256='b' * 64)
    assert command[-2:] == ['--context-sha256', 'b' * 64]
    assert command.count('--context-sha256') == 1
    with pytest.raises(SupervisionError) as error:
        build_production_command('/tmp/context.json')
    assert error.value.code == 'WORKER_CONTEXT_HASH_REQUIRED'
    with pytest.raises(SupervisionError) as error:
        build_production_command('/tmp/context.json', context_sha256='not-a-digest')
    assert error.value.code == 'WORKER_CONTEXT_HASH_INVALID'


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


def fixture_context(guard_root, root, rows, run_id=RUN_ID):
    """The bounded context document of one fixture scenario.

    The document lives in the fresh runner owned root.  No arbitrary private
    path is accepted by the executor.
    """
    document = {'run_id': run_id, 'candidate_sha': CANDIDATE_SHA,
                'authorization_sha256': AUTHORIZATION_SHA, 'root': str(root),
                'terminal_reference': 'temp/s3-quality/qd-receipt.json',
                'plan': rows}
    path = Path(guard_root) / 'fixture-context.json'
    path.write_text(json.dumps(document))
    return path


def run_fixture(tmp_path, scenario, *, rows=None, root=None, phase_seconds=1.0,
                grace_seconds=0.25, run_id=RUN_ID):
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
    context = fixture_context(guard_root, root, rows, run_id=run_id)
    os.environ['LVW_S3_FIXTURE_CONTEXT'] = str(context)
    command = build_fixture_command(scenario,
                                    python=MACHINE_BINDING['python']['path'])
    supervisor = ParentSupervisor(command=command, run_id=run_id,
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
    # The message count negative case carries its own short synthetic run
    # identity, so that its wire fits into the frozen byte budget of a
    # stream.  The identity is bound by the parent and by the child.
    run_id = FLOOD_RUN_ID if scenario == 'message_flood' else RUN_ID
    evidence = run_fixture(tmp_path, scenario, run_id=run_id)
    assert evidence['protocol_violation'] == code
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


@requires_machine_gate
def test_a_bad_terminal_reference_is_refused(tmp_path):
    """I24: a terminal reference outside the bound root is refused."""
    evidence = run_fixture(tmp_path, 'bad_terminal_reference')
    assert evidence['canonical_receipt_verified'] is False
    assert evidence['root_retained'] is True


# --------------------------------- the zero process correction of the streams
# The correction of the two refused scenarios of the finite fixture run is
# checked here without any process at all: the real writer of the fixture and
# the real scenario functions build the wire, and the real protocol state and
# the real parent supervisor read it.  No fixture process is started, no
# socket is opened, no model, no GPU, no service and no ledger is touched.
FIXTURE_PATH = PACK_ROOT / 'tools/fixtures/v0_s3_supervisor_fixture.py'


def load_fixture_module():
    """Load the fixture entry as a module, without its boundary guard.

    The import of the fixture never registers the audit hook of the child:
    the hook is installed by the ``__main__`` entry of the fixture only.
    Importing the fixture in this process therefore never closes the process
    gate of this process.
    """
    spec = importlib.util.spec_from_file_location('lvw_s3_supervisor_fixture_module',
                                                  FIXTURE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = load_fixture_module()


class CapturedStdout:
    """A stdout replacement that keeps the exact bytes of the fixture."""

    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        return None

    def write(self, text):
        return self.buffer.write(text.encode('utf-8'))


def fixture_values(*, run_id=RUN_ID, root=''):
    """The context values of one fixture scenario."""
    return {'run_id': run_id, 'candidate_sha': CANDIDATE_SHA,
            'authorization_sha256': AUTHORIZATION_SHA, 'root': root,
            'terminal_reference': 'temp/s3-quality/qd-receipt.json',
            'plan': []}


def run_fixture_scenario(monkeypatch, scenario, values, rows=None):
    """Run one enumerated scenario of the fixture and keep its wire bytes.

    No process is started.  The writer of the fixture writes into a captured
    standard output, so the wire of the scenario is the real wire of the
    scenario.
    """
    captured = CapturedStdout()
    monkeypatch.setattr(sys, 'stdout', captured)
    writer = FIXTURE.Writer(values)
    handler = FIXTURE.SCENARIO_FUNCTIONS[scenario]
    handler(writer, values, rows if rows is not None else values.get('plan') or [])
    return captured.buffer.getvalue()


class UnreadableStream:
    """A child stream that cannot be read at all."""

    def __init__(self, error=None):
        self.error = error or OSError('the child stream cannot be read')

    def fileno(self):
        raise self.error


class UnreadableProcess:
    """A fake child whose streams cannot be read.  No process is started."""

    def __init__(self, *, stdout=None, stderr=None, pid=4343):
        self.stdout = stdout
        self.stderr = stderr
        self.stdin = None
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False

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


def test_the_fixture_import_installs_no_process_guard():
    """The fixture module never closes the process gate of the parent."""
    assert FIXTURE.BOUNDARY_GUARD_INSTALLED is False
    # The audit event of a process start must not be refused by the fixture.
    # The outer guard of a gated batch refuses the event first; a refusal of
    # the fixture would be the bug that this test protects against.
    try:
        sys.audit('subprocess.Popen', sys.executable,
                  [sys.executable, '-c', 'pass'], str(PACK_ROOT), None)
    except FIXTURE.FixtureBoundaryViolation:
        pytest.fail('the fixture installed its process guard in the parent process')
    except Exception:  # noqa: BLE001 - the outer guard of a gated batch
        pass


def test_the_fixture_guard_refuses_the_blocked_events():
    """The guard of the child entry refuses the network and the descendants."""
    with pytest.raises(FIXTURE.FixtureBoundaryViolation):
        FIXTURE._audit_hook('os.fork', ())
    with pytest.raises(FIXTURE.FixtureBoundaryViolation):
        FIXTURE._audit_hook('subprocess.Popen', ('/bin/true',))
    with pytest.raises(FIXTURE.FixtureBoundaryViolation):
        FIXTURE._audit_hook('socket.connect', ('127.0.0.1', 80))
    # an event outside of the boundary is not refused
    assert FIXTURE._audit_hook('open', ('/dev/null', 'rb')) is None


def test_the_product_import_of_the_fixture_needs_the_guard(monkeypatch):
    """The fixture refuses to import the product without its guard."""
    module = load_fixture_module()
    monkeypatch.setattr(module, '__name__', '__main__')
    monkeypatch.setattr(module, '_PRODUCT', None)
    with pytest.raises(SystemExit) as error:
        module.product()
    assert str(error.value) == 'FIXTURE_GUARD_MISSING'


def test_the_child_entry_installs_the_guard_before_the_product():
    """The ``__main__`` entry of the fixture installs the guard first."""
    source = FIXTURE_PATH.read_text(encoding='utf-8')
    marker = "if __name__ == '__main__':"
    assert marker in source
    calls = []
    namespace = {'__name__': '__main__', 'sys': sys,
                 'install_boundary_guard': lambda: calls.append('guard'),
                 'main': lambda: calls.append('main')}
    with pytest.raises(SystemExit):
        exec(compile(source[source.index(marker):], str(FIXTURE_PATH), 'exec'),
             namespace)
    assert calls == ['guard', 'main']


def test_the_nonfinite_frame_is_complete_and_is_refused(monkeypatch):
    """The NaN negative case is a complete frame that the parser refuses."""
    raw = run_fixture_scenario(monkeypatch, 'nonfinite_number', fixture_values(),
                               sixteen_rows())
    # the frame is complete: exactly one terminated JSONL line
    assert raw.endswith(b'\n')
    lines = raw.split(b'\n')
    assert lines[-1] == b''
    assert len(lines) == 2
    frame = lines[0]
    document = json.loads(frame.decode('utf-8'))
    assert set(document) == set(MESSAGE_KEYS)
    assert document['event'] == 'STARTED'
    assert document['run_id'] == RUN_ID
    assert document['candidate_sha'] == CANDIDATE_SHA
    assert document['authorization_sha256'] == AUTHORIZATION_SHA
    assert math.isnan(document['payload']['value'])
    # the product parser refuses the NaN of that complete frame
    with pytest.raises(SupervisionError) as error:
        decode_message(frame)
    assert error.value.code == 'MESSAGE_NONFINITE_NUMBER'


def test_the_parent_refuses_the_nonfinite_frame_on_a_real_pipe(tmp_path, monkeypatch):
    """The real read path of the parent refuses the complete NaN frame."""
    raw = run_fixture_scenario(monkeypatch, 'nonfinite_number', fixture_values(),
                               sixteen_rows())
    process = FakeProcess()
    process.emit_raw(raw)
    process.close_streams()
    process.returncode = 0
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic)
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == 'MESSAGE_NONFINITE_NUMBER'
    assert evidence['message_count'] == 0
    assert evidence['stdout_overflow'] is False
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


def test_the_message_count_negative_case_fits_the_frozen_byte_caps(monkeypatch):
    """The flood negative case is exactly one message too many and it fits."""
    raw = run_fixture_scenario(monkeypatch, 'message_flood',
                               fixture_values(run_id=FLOOD_RUN_ID), sixteen_rows())
    frames = [line for line in raw.split(b'\n') if line]
    # the real numbers of the wire, computed from the real bytes
    assert len(frames) == MAX_MESSAGES + 1
    longest = max(len(frame) + 1 for frame in frames)
    total = len(raw)
    assert longest <= MAX_MESSAGE_BYTES
    assert total <= MAX_STREAM_BYTES
    # every frame is closed and carries the bound identity
    for index, frame in enumerate(frames):
        document = json.loads(frame.decode('utf-8'))
        assert document['run_id'] == FLOOD_RUN_ID
        assert document['candidate_sha'] == CANDIDATE_SHA
        assert document['authorization_sha256'] == AUTHORIZATION_SHA
        assert document['sequence'] == index + 1
        assert set(document) == set(MESSAGE_KEYS)
    # the exact limit is legal, the one over is refused by the count
    state = ProtocolState(run_id=FLOOD_RUN_ID, candidate_sha=CANDIDATE_SHA,
                           authorization_sha256=AUTHORIZATION_SHA, plan=plan())
    for frame in frames[:MAX_MESSAGES]:
        state.accept(decode_message(frame))
    assert state.count == MAX_MESSAGES
    with pytest.raises(SupervisionError) as error:
        state.accept(decode_message(frames[MAX_MESSAGES]))
    assert error.value.code == 'MESSAGE_COUNT_EXCEEDED'
    # the byte budget did not come first
    assert total <= MAX_STREAM_BYTES


def test_the_parent_accepts_exactly_the_message_limit(tmp_path, monkeypatch):
    """Exactly 1024 messages are legal and the verified terminal still holds."""
    raw = run_fixture_scenario(monkeypatch, 'message_flood',
                               fixture_values(run_id=FLOOD_RUN_ID), sixteen_rows())
    frames = [line for line in raw.split(b'\n') if line]
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    payload = json.dumps({'rows': [{'asset_id': 'SYN-01',
                                    'execution_status': 'PASS'}]}).encode()
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(payload)
    terminal = encoded(message('TERMINAL',
                                {'canonical_receipt': {
                                    'reference': 'temp/s3-quality/qd-receipt.json',
                                    'bytes': len(payload),
                                    'sha256': hashlib.sha256(payload).hexdigest()},
                                 'decision': 'FIXTURE_TERMINAL'},
                                sequence=MAX_MESSAGES,
                                run_id=FLOOD_RUN_ID)) + b'\n'
    exact = b'\n'.join(frames[:MAX_MESSAGES - 1]) + b'\n' + terminal
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 run_id=FLOOD_RUN_ID, root=root)
    # the reader of the parent has to run before the wire is written: the
    # wire is larger than the buffer of a pipe
    supervisor.start()
    process.emit_raw(exact)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['message_count'] == MAX_MESSAGES
    assert evidence['protocol_violation'] is None
    assert evidence['terminal_received'] is True
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['root_retained'] is False


def test_the_parent_refuses_the_one_over_message_count(tmp_path, monkeypatch):
    """The parent refuses the one over message count on a real pipe."""
    raw = run_fixture_scenario(monkeypatch, 'message_flood',
                               fixture_values(run_id=FLOOD_RUN_ID), sixteen_rows())
    process = FakeProcess()

    def deliver():
        try:
            os.write(process.out_write, raw)
        except OSError:  # noqa: BLE001 - the pipe may be closed
            pass
        try:
            os.close(process.out_write)
        except OSError:  # noqa: BLE001 - the pipe may be closed
            pass

    thread = threading.Thread(target=deliver, daemon=True)
    thread.start()
    # the error stream of the fake child ends with the child
    os.close(process.err_write)
    process.err_write = None
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 run_id=FLOOD_RUN_ID)
    evidence = supervisor.run()
    thread.join(timeout=5.0)
    assert evidence['protocol_violation'] == 'MESSAGE_COUNT_EXCEEDED'
    assert evidence['message_count'] == MAX_MESSAGES
    # the byte budget of the stream did not come first
    assert evidence['stdout_overflow'] is False
    assert evidence['stdout_bytes'] <= MAX_STREAM_BYTES
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


def test_the_stdout_stream_at_the_exact_cap_is_not_refused(tmp_path):
    """The exact byte budget of a stream is not a refusal."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic)
    supervisor.start()
    process.emit_raw(b'x' * MAX_STREAM_BYTES)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['stdout_overflow'] is False
    assert evidence['stdout_bytes'] == MAX_STREAM_BYTES
    assert evidence['protocol_violation'] != STDOUT_STREAM_LIMIT_EXCEEDED


def test_the_parent_refuses_an_overlong_stdout_stream(tmp_path):
    """One byte over the budget of the stream is a stable refusal."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    process.emit_raw(b'x' * (MAX_STREAM_BYTES + 1))
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDOUT_STREAM_LIMIT_EXCEEDED
    assert evidence['stdout_overflow'] is True
    assert evidence['stream_violation'] == STDOUT_STREAM_LIMIT_EXCEEDED
    # the retained bytes never exceed the frozen budget of the stream
    assert evidence['stdout_bytes_retained'] <= MAX_STREAM_BYTES
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True
    assert evidence['archive_allowed'] is False


def test_the_stderr_stream_at_the_exact_cap_is_not_refused(tmp_path):
    """The exact byte budget of the error stream is not a refusal."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic)
    supervisor.start()
    os.write(process.err_write, b'y' * MAX_STREAM_BYTES)
    os.close(process.err_write)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['stderr_overflow'] is False
    assert evidence['stderr_bytes'] == MAX_STREAM_BYTES
    assert evidence['protocol_violation'] != STDERR_STREAM_LIMIT_EXCEEDED


def test_the_parent_refuses_an_overlong_stderr_stream(tmp_path):
    """One byte over the budget of the error stream is a stable refusal."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    os.write(process.err_write, b'y' * (MAX_STREAM_BYTES + 1))
    os.close(process.err_write)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDERR_STREAM_LIMIT_EXCEEDED
    assert evidence['stderr_overflow'] is True
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


def test_the_parent_refuses_a_failing_stdout_reader(tmp_path):
    """A stream that cannot be read is a stable refusal."""
    process = UnreadableProcess(stdout=UnreadableStream())
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDOUT_STREAM_READ_FAILED
    assert evidence['stdout_read_error'] == 'OSError'
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


def test_the_parent_refuses_a_failing_stderr_reader(tmp_path):
    """An error stream that cannot be read is a stable refusal."""
    process = UnreadableProcess(stderr=UnreadableStream())
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDERR_STREAM_READ_FAILED
    assert evidence['stderr_read_error'] == 'OSError'
    assert evidence['cleanup']['proven_stopped'] is True
    assert evidence['root_retained'] is True


def test_a_terminal_with_a_stream_overflow_is_not_a_success(tmp_path):
    """A terminal of the same batch never hides a stream failure."""
    root = tmp_path / 'run'
    (root / 'temp/s3-quality').mkdir(parents=True)
    payload = json.dumps({'rows': [{'asset_id': 'SYN-01',
                                    'execution_status': 'PASS'}]}).encode()
    (root / 'temp/s3-quality/qd-receipt.json').write_bytes(payload)
    terminal = encoded(message('TERMINAL',
                                {'canonical_receipt': {
                                    'reference': 'temp/s3-quality/qd-receipt.json',
                                    'bytes': len(payload),
                                    'sha256': hashlib.sha256(payload).hexdigest()},
                                 'decision': 'FIXTURE_TERMINAL'})) + b'\n'
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    process.emit_raw(terminal)
    process.emit_raw(b'x' * (MAX_STREAM_BYTES + 1))
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDOUT_STREAM_LIMIT_EXCEEDED
    assert evidence['terminal_received'] is True
    assert evidence['unknown_outcome'] is True
    assert evidence['root_retained'] is True
    assert evidence['reservation_retained'] is True
    assert evidence['archive_allowed'] is False
    assert evidence['next_phase_allowed'] is False
    assert evidence['cleanup']['proven_stopped'] is True


def test_the_blocking_partial_frame_stays_incomplete(tmp_path, monkeypatch):
    """The deliberately incomplete frame of the persistence case is kept."""
    raw = run_fixture_scenario(monkeypatch, 'blocking_persistence', fixture_values(),
                               sixteen_rows())
    assert not raw.endswith(b'\n')
    assert b'"run_id":"' in raw
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=0.3)
    supervisor.start()
    process.emit_raw(raw)
    evidence = supervisor.run()
    # only the closed frame of the scenario is a message; the partial frame
    # is never decoded and never completed
    assert evidence['message_count'] == 1
    assert evidence['protocol_violation'] == 'PHASE_DEADLINE_EXCEEDED'
    assert evidence['stdout_overflow'] is False
    assert evidence['stdout_bytes_retained'] > 0
    assert evidence['cleanup']['proven_stopped'] is True


def test_the_frozen_caps_of_the_protocol_are_unchanged():
    """The message and the stream caps of the contract are not relaxed."""
    assert MAX_MESSAGES == 1024
    assert MAX_MESSAGE_BYTES == 32 * 1024
    assert MAX_STREAM_BYTES == 256 * 1024
    assert STDOUT_STREAM_LIMIT_EXCEEDED == 'STDOUT_STREAM_LIMIT_EXCEEDED'
    assert STDERR_STREAM_LIMIT_EXCEEDED == 'STDERR_STREAM_LIMIT_EXCEEDED'
    assert STDOUT_STREAM_READ_FAILED == 'STDOUT_STREAM_READ_FAILED'
    assert STDERR_STREAM_READ_FAILED == 'STDERR_STREAM_READ_FAILED'
    # the new internal codes of the drain and of the trailing frame
    assert STDOUT_STREAM_DRAIN_INCOMPLETE == 'STDOUT_STREAM_DRAIN_INCOMPLETE'
    assert STDERR_STREAM_DRAIN_INCOMPLETE == 'STDERR_STREAM_DRAIN_INCOMPLETE'
    assert MESSAGE_INCOMPLETE_FRAME == 'MESSAGE_INCOMPLETE_FRAME'
    # the shared budget of the drain is the one of the last round
    assert DRAIN_TIMEOUT_SECONDS == 0.5
    # the public protocol of the contract is unchanged
    assert EVENTS == ('STARTED', 'ROW_STARTED', 'HISTORY_WAIT_STARTED',
                      'ROW_FINISHED', 'PROGRESS', 'TERMINAL')
    assert MESSAGE_KEYS == frozenset({'schema', 'run_id', 'candidate_sha',
                                       'authorization_sha256', 'sequence', 'event',
                                       'payload'})
    assert len(FIXTURE_SCENARIOS) == 13


# -------------------------- the second correction of the streams, zero process
# The three findings of the independent review are checked here without any
# process: real pipes, real threads, the real reader and the real parent.
# No fixture process is started, no socket is opened, no model, no GPU, no
# service and no ledger is touched.
class HeldPipeProcess:
    """A fake child that is gone but whose pipes are still held open.

    No process is started.  The write ends of the pipes stay open, so the
    readers of the parent never see the end of their stream.  The exit of
    the handle says nothing about the end of the streams.
    """

    def __init__(self, pid=4343, stderr_factory=None):
        self.out_read, self.out_write = os.pipe()
        self.err_read, self.err_write = os.pipe()
        self.stdout = os.fdopen(self.out_read, 'rb', buffering=0)
        self.stderr = (stderr_factory(self.err_read) if stderr_factory is not None
                       else os.fdopen(self.err_read, 'rb', buffering=0))
        self.stdin = None
        self.pid = pid
        self.returncode = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        raise AssertionError('a child that is gone must not be terminated')

    def kill(self):
        raise AssertionError('no other handle may be killed')

    def release(self):
        """Close the write ends, so the readers of the parent can end."""
        for name in ('out_write', 'err_write'):
            descriptor = getattr(self, name, None)
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError:  # noqa: BLE001 - the pipe may be closed
                pass
            setattr(self, name, None)


class LateFailingStream:
    """A stream that can be read once and that fails on the next read."""

    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.calls = 0

    def fileno(self):
        self.calls += 1
        if self.calls == 1:
            return self.descriptor
        raise OSError('the child stream can not be read any more')


def canonical_terminal(root, *, run_id=RUN_ID, sequence=1):
    """A legal terminal frame that names a real canonical receipt."""
    payload = b'{"rows": []}'
    (root / 'canonical.json').write_bytes(payload)
    return encoded(message('TERMINAL',
                            {'canonical_receipt': {
                                'reference': 'canonical.json',
                                'bytes': len(payload),
                                'sha256': hashlib.sha256(payload).hexdigest()}},
                            sequence=sequence, run_id=run_id)) + b'\n'


def wait_for_the_reader(reader, wanted, *, timeout=5.0):
    """Wait until the reader has taken the bytes that the test wrote."""
    end = time.monotonic() + timeout
    while reader.total < wanted and time.monotonic() < end:
        time.sleep(0.001)
    return reader.total >= wanted


def test_the_drain_without_a_proven_end_of_the_stream_is_not_archived(tmp_path):
    """M1: an unproven end of the streams is never an archiveable success."""
    root = tmp_path / 'run'
    root.mkdir()
    process = HeldPipeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    terminal = canonical_terminal(root)
    os.write(process.out_write, terminal)
    assert wait_for_the_reader(supervisor.stdout_reader, len(terminal))
    try:
        evidence = supervisor.run()
        # the readers are still active: they are not stopped and not faked
        stdout_active = supervisor.stdout_reader.finished.is_set() is False
        stderr_active = supervisor.stderr_reader.finished.is_set() is False
    finally:
        process.release()
    # the terminal and the canonical receipt are there and both are legal
    assert evidence['terminal_received'] is True
    assert evidence['canonical_receipt_verified'] is True
    # the end of the streams is not proven
    assert evidence['drain_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
    assert evidence['stdout_drain_complete'] is False
    assert evidence['stderr_drain_complete'] is False
    assert evidence['protocol_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
    assert evidence['unknown_outcome'] is True
    assert evidence['root_retained'] is True
    assert evidence['reservation_retained'] is True
    assert evidence['archive_allowed'] is False
    assert evidence['next_phase_allowed'] is False
    assert evidence['refund_allowed'] is False
    assert evidence['resend_allowed'] is False
    # the exit of the handle is not the end of the stream
    assert evidence['cleanup']['proven_stopped'] is True
    assert stdout_active is True
    assert stderr_active is True


def test_the_drain_uses_one_shared_bounded_deadline(tmp_path):
    """M1: the two readers share one budget, they do not get one each."""
    root = tmp_path / 'run'
    root.mkdir()
    process = HeldPipeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    os.write(process.out_write, canonical_terminal(root))
    try:
        start = time.monotonic()
        evidence = supervisor.run()
        elapsed = time.monotonic() - start
    finally:
        process.release()
    # one budget for the two readers and not one budget for each of them
    assert elapsed < 2 * DRAIN_TIMEOUT_SECONDS
    assert evidence['drain_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
    assert evidence['archive_allowed'] is False


def test_the_drain_never_waits_beyond_the_child_deadline(tmp_path):
    """M1: a run without any remaining time waits no fixed extra time."""
    root = tmp_path / 'run'
    root.mkdir()
    process = HeldPipeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root, phase_timeout=0.05, child_timeout=0.10)
    supervisor.start()
    terminal = canonical_terminal(root)
    os.write(process.out_write, terminal)
    assert wait_for_the_reader(supervisor.stdout_reader, len(terminal))
    try:
        start = time.monotonic()
        evidence = supervisor.run()
        elapsed = time.monotonic() - start
    finally:
        process.release()
    # the drain stopped at the deadline of the run and did not add a wait
    assert elapsed < 0.10
    assert evidence['terminal_received'] is True
    assert evidence['drain_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
    assert evidence['archive_allowed'] is False


def test_a_late_overflow_after_the_terminal_is_not_a_success(tmp_path):
    """M1: a failure that arrives after the run never keeps an archive."""
    root = tmp_path / 'run'
    root.mkdir()
    process = HeldPipeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    terminal = canonical_terminal(root)
    os.write(process.out_write, terminal)
    assert wait_for_the_reader(supervisor.stdout_reader, len(terminal))
    try:
        evidence = supervisor.run()
        # the run already refused, the late failure can not change that
        assert evidence['archive_allowed'] is False
        assert evidence['root_retained'] is True
        assert evidence['drain_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
        assert evidence['stderr_overflow'] is False

        def deliver():
            try:
                os.write(process.err_write, b'l' * (MAX_STREAM_BYTES + 1))
            except OSError:  # noqa: BLE001 - the pipe may be closed
                pass

        thread = threading.Thread(target=deliver, daemon=True)
        thread.start()
        assert supervisor.stderr_reader.finished.wait(10)
        thread.join(10)
    finally:
        process.release()
    # the late overflow is a real failure of the stream
    assert supervisor.stderr_reader.overflow is True
    assert supervisor._stream_failure() == STDERR_STREAM_LIMIT_EXCEEDED
    # and the returned evidence never claimed a success
    assert evidence['archive_allowed'] is False


def test_a_late_read_error_is_not_hidden_by_the_terminal(tmp_path):
    """M1: a read error stays the primary reason, the drain is recorded."""
    root = tmp_path / 'run'
    root.mkdir()
    process = HeldPipeProcess(stderr_factory=LateFailingStream)
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    terminal = canonical_terminal(root)
    os.write(process.err_write, b'partial')
    os.write(process.out_write, terminal)
    assert wait_for_the_reader(supervisor.stdout_reader, len(terminal))
    try:
        evidence = supervisor.run()
    finally:
        process.release()
    # the read error of the stream is the primary reason of the refusal
    assert evidence['stderr_read_error'] == 'OSError'
    assert evidence['protocol_violation'] == STDERR_STREAM_READ_FAILED
    # the drain that was not complete is recorded on its own
    assert evidence['drain_violation'] == STDOUT_STREAM_DRAIN_INCOMPLETE
    assert evidence['archive_allowed'] is False
    assert evidence['root_retained'] is True


def test_a_trailing_partial_frame_after_the_terminal_is_refused(tmp_path):
    """M1: a stream that ends in the middle of a frame is not a success."""
    root = tmp_path / 'run'
    root.mkdir()
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    process.emit_raw(canonical_terminal(root))
    process.emit_raw(b'{"schema":"lvw.s3')  # the frame is never closed
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['terminal_received'] is True
    assert evidence['canonical_receipt_verified'] is True
    # the end of the stream is proven, the frame is not closed
    assert evidence['stdout_drain_complete'] is True
    assert evidence['stderr_drain_complete'] is True
    assert evidence['drain_violation'] is None
    assert evidence['incomplete_frame'] is True
    assert evidence['protocol_violation'] == MESSAGE_INCOMPLETE_FRAME
    assert evidence['archive_allowed'] is False
    assert evidence['root_retained'] is True
    assert evidence['unknown_outcome'] is True


def test_a_normal_bounded_run_with_a_proven_end_of_the_streams_succeeds(tmp_path):
    """M1: a run whose streams really end is a success and it is archived."""
    root = tmp_path / 'run'
    root.mkdir()
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 root=root)
    supervisor.start()
    process.emit_raw(canonical_terminal(root))
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] is None
    assert evidence['drain_violation'] is None
    assert evidence['stdout_drain_complete'] is True
    assert evidence['stderr_drain_complete'] is True
    assert evidence['canonical_receipt_verified'] is True
    assert evidence['message_count'] == 1
    assert evidence['root_retained'] is False
    assert evidence['archive_allowed'] is True
    assert evidence['next_phase_allowed'] is True


def test_the_hash_scope_of_an_overlong_stream_is_honest(tmp_path):
    """m1: the digest of an overlong stream covers the prefix and says so."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    payload = b'x' * (MAX_STREAM_BYTES + 1)
    process.emit_raw(payload)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDOUT_STREAM_LIMIT_EXCEEDED
    assert evidence['stdout_overflow'] is True
    # the digest covers the prefix that is still inside the budget
    assert evidence['stdout_hash_scope'] == 'prefix_within_budget'
    assert evidence['stdout_hashed_bytes'] == MAX_STREAM_BYTES
    assert evidence['stdout_total_observed'] == MAX_STREAM_BYTES + 1
    assert evidence['stdout_bytes'] == MAX_STREAM_BYTES + 1
    # the digest is the digest of that prefix and can be recomputed
    assert evidence['stdout_sha256'] == hashlib.sha256(b'x' * MAX_STREAM_BYTES).hexdigest()
    # the digest is never the digest of the whole stream
    assert evidence['stdout_sha256'] != hashlib.sha256(payload).hexdigest()
    # the digest is recomputable from the raw bytes that the reader kept
    assert evidence['stdout_sha256'] == hashlib.sha256(
        supervisor.stdout_reader.raw()).hexdigest()
    # a stream that stayed inside its budget is the digest of everything
    assert evidence['stderr_hash_scope'] == 'all_observed'
    assert evidence['stderr_hashed_bytes'] == evidence['stderr_total_observed']


def test_the_hash_scope_of_the_error_stream_is_honest(tmp_path):
    """m1: the digest of an overlong error stream covers the prefix."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    payload = b'y' * (MAX_STREAM_BYTES + 1)
    os.write(process.err_write, payload)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['protocol_violation'] == STDERR_STREAM_LIMIT_EXCEEDED
    assert evidence['stderr_overflow'] is True
    assert evidence['stderr_hash_scope'] == 'prefix_within_budget'
    assert evidence['stderr_hashed_bytes'] == MAX_STREAM_BYTES
    assert evidence['stderr_total_observed'] == MAX_STREAM_BYTES + 1
    assert evidence['stderr_sha256'] == hashlib.sha256(b'y' * MAX_STREAM_BYTES).hexdigest()
    assert evidence['stderr_sha256'] != hashlib.sha256(payload).hexdigest()


def test_the_hash_of_an_exact_stream_covers_everything_it_delivered(tmp_path):
    """m1: a stream inside its budget is digested in full."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic,
                                 phase_timeout=5.0)
    supervisor.start()
    stdout_payload = b'x' * MAX_STREAM_BYTES
    stderr_payload = b'y' * MAX_STREAM_BYTES
    process.emit_raw(stdout_payload)
    os.write(process.err_write, stderr_payload)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['stdout_overflow'] is False
    assert evidence['stderr_overflow'] is False
    assert evidence['stdout_hash_scope'] == 'all_observed'
    assert evidence['stderr_hash_scope'] == 'all_observed'
    assert evidence['stdout_hashed_bytes'] == MAX_STREAM_BYTES
    assert evidence['stdout_total_observed'] == MAX_STREAM_BYTES
    assert evidence['stderr_hashed_bytes'] == MAX_STREAM_BYTES
    assert evidence['stderr_total_observed'] == MAX_STREAM_BYTES
    assert evidence['stdout_sha256'] == hashlib.sha256(stdout_payload).hexdigest()
    assert evidence['stderr_sha256'] == hashlib.sha256(stderr_payload).hexdigest()
    # the digests are recomputable from the raw bytes of the readers
    assert evidence['stdout_sha256'] == hashlib.sha256(
        supervisor.stdout_reader.raw()).hexdigest()
    assert evidence['stderr_sha256'] == hashlib.sha256(
        supervisor.stderr_reader.raw()).hexdigest()


def test_the_raw_digest_survives_the_consumption(tmp_path):
    """m1: the digest of a stream does not change when the parent consumes."""
    process = FakeProcess()
    supervisor = make_supervisor(tmp_path, process=process, clock=time.monotonic)
    supervisor.start()
    payload = encoded(message('STARTED', {})) + b'\n'
    process.emit_raw(payload)
    assert wait_for_the_reader(supervisor.stdout_reader, len(payload))
    before = supervisor.stdout_reader.raw()
    digest_before = hashlib.sha256(before).hexdigest()
    supervisor._consume_stdout()
    after = supervisor.stdout_reader.raw()
    assert after == before
    assert hashlib.sha256(after).hexdigest() == digest_before
    # the bytes are consumed, the stream is not empty
    assert supervisor.stdout_reader.retained() == 0
    assert len(after) == len(payload)
    process.close_streams()
    process.returncode = 0
    evidence = supervisor.run()
    assert evidence['stdout_sha256'] == digest_before
    assert evidence['stdout_hashed_bytes'] == len(payload)
    assert evidence['stdout_total_observed'] == len(payload)
    assert evidence['stdout_hash_scope'] == 'all_observed'
    assert evidence['stdout_bytes'] == len(payload)


def test_the_controlled_handoff_keeps_the_frame(tmp_path):
    """M2: a frame that is appended while the parent takes is not lost.

    The interleaving is the one of the independent review: the reader is
    paused inside the handoff, the parent takes the pending bytes at that
    moment and the reader continues afterwards.  The frame has to reach the
    protocol state of the parent.
    """
    import dis
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = _StreamReader(stream, MAX_STREAM_BYTES)
    code = _StreamReader._retain.__code__
    target = next(instruction.offset for instruction in dis.get_instructions(code)
                  if instruction.opname == 'CALL')
    paused = threading.Event()
    release = threading.Event()

    def instruction(code_object, offset):
        if offset == target:
            paused.set()
            release.wait(5)

    sys.monitoring.use_tool_id(5, 'lvw-s3-handoff')
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION, instruction)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)
    try:
        worker = threading.Thread(target=reader.run, daemon=True)
        worker.start()
        raw = encoded(message('STARTED', {})) + b'\n'
        os.write(writer_fd, raw)
        assert paused.wait(5) is True
        parent = make_supervisor(tmp_path, process=FakeProcess(), clock=time.monotonic)
        parent.stdout_reader = reader
        # the parent takes the pending bytes while the reader is in the
        # middle of the handoff
        parent._consume_stdout()
        release.set()
        worker.join(5)
        # the frame has to reach the protocol state of the parent
        parent._consume_stdout()
        assert parent.state.count == 1
        assert parent.messages[0]['event'] == 'STARTED'
        assert len(reader.raw()) == len(raw)
    finally:
        sys.monitoring.set_local_events(5, code, 0)
        sys.monitoring.free_tool_id(5)
        release.set()
        os.close(writer_fd)
        stream.close()


# --------------------------------------- S: the published state of a reader
def assert_consistent_snapshot(snapshot, raw):
    """A snapshot is one moment: its accounts belong to each other."""
    assert snapshot['hashed_bytes'] == snapshot['kept_bytes']
    assert snapshot['total_observed'] >= snapshot['kept_bytes']
    assert snapshot['sha256'] == hashlib.sha256(
        raw[:snapshot['hashed_bytes']]).hexdigest()
    if snapshot['overflow']:
        assert snapshot['hash_scope'] == 'prefix_within_budget'
    elif snapshot['complete']:
        assert snapshot['hash_scope'] == 'all_observed'
    else:
        assert snapshot['hash_scope'] == 'observed_prefix'


def test_an_unfinished_stream_is_only_an_observed_prefix(tmp_path):
    """S: a stream that did not end is never reported as the whole stream."""
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = _StreamReader(stream, MAX_STREAM_BYTES)
    worker = threading.Thread(target=reader.run, daemon=True)
    worker.start()
    try:
        empty = reader.snapshot()
        assert empty['total_observed'] == 0
        assert empty['hashed_bytes'] == 0
        assert empty['complete'] is False
        # an empty stream that did not end is not the whole stream
        assert empty['hash_scope'] == 'observed_prefix'
        os.write(writer_fd, b'later')
        assert wait_for_the_reader(reader, 5)
        partial = reader.snapshot()
        assert partial['total_observed'] == 5
        assert partial['hashed_bytes'] == 5
        assert partial['complete'] is False
        # the hashed bytes and the observed bytes are equal and it is still
        # only the observed prefix
        assert partial['hash_scope'] == 'observed_prefix'
        assert_consistent_snapshot(partial, reader.raw())
        os.close(writer_fd)
        worker.join(5)
        final = reader.snapshot()
        assert final['complete'] is True
        assert final['hash_scope'] == 'all_observed'
        assert_consistent_snapshot(final, reader.raw())
    finally:
        stream.close()


def test_the_snapshot_never_mixes_two_moments(tmp_path):
    """S: a snapshot is not the state of one step and of another step.

    The interleaving is the one of the independent review: the snapshot is
    paused after it read the published state, the reader publishes the
    bytes and the end of the stream in the meantime and the snapshot
    returns afterwards.  The snapshot that is returned is one moment and it
    never claims that a stream ended while its digest is empty.
    """
    import dis
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = _StreamReader(stream, MAX_STREAM_BYTES)
    code = _StreamReader.snapshot.__code__
    target = next(instruction.offset for instruction in dis.get_instructions(code)
                  if instruction.opname == 'STORE_SUBSCR')
    paused = threading.Event()
    release = threading.Event()

    def instruction(code_object, offset):
        if offset == target:
            paused.set()
            release.wait(5)

    sys.monitoring.use_tool_id(5, 'lvw-s3-snapshot')
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION, instruction)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)
    try:
        worker = threading.Thread(target=reader.run, daemon=True)
        worker.start()
        box = {}
        snapshotter = threading.Thread(target=lambda: box.update(reader.snapshot()))
        snapshotter.start()
        assert paused.wait(5) is True
        # the reader publishes the bytes and the end of the stream while the
        # snapshot is paused
        os.write(writer_fd, b'hello')
        os.close(writer_fd)
        worker.join(5)
        assert reader.finished.is_set()
        release.set()
        snapshotter.join(5)
        # the returned snapshot is one moment and it is not the mixed state
        # of the old publication
        assert_consistent_snapshot(box, reader.raw())
        assert not (box['complete'] and box['hashed_bytes'] != box['total_observed'])
        assert not (box['hashed_bytes'] == 5 and box['total_observed'] == 0)
        # the state after the publication is complete and consistent
        final = reader.snapshot()
        assert final['complete'] is True
        assert final['total_observed'] == 5
        assert final['hashed_bytes'] == 5
        assert final['hash_scope'] == 'all_observed'
        assert final['sha256'] == hashlib.sha256(b'hello').hexdigest()
        assert_consistent_snapshot(final, reader.raw())
    finally:
        sys.monitoring.set_local_events(5, code, 0)
        sys.monitoring.free_tool_id(5)
        release.set()
        stream.close()


def test_the_reader_publishes_the_bytes_and_the_total_together(tmp_path):
    """S: the observed bytes and the kept bytes are one publication.

    The reader is paused after it read the bytes of the stream and before
    it publishes them.  A snapshot of that moment is the older, complete
    state of the reader and never a state in which the bytes are hashed but
    the total of the stream is still the old one.
    """
    import dis
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = _StreamReader(stream, MAX_STREAM_BYTES)
    code = _StreamReader.run.__code__
    targets = [instruction.offset for instruction in dis.get_instructions(code)
               if instruction.opname == 'LOAD_ATTR' and instruction.argval == '_retain']
    assert targets, 'the reader has no publication point'
    target = targets[-1]
    paused = threading.Event()
    release = threading.Event()

    def instruction(code_object, offset):
        if offset == target:
            paused.set()
            release.wait(5)

    sys.monitoring.use_tool_id(5, 'lvw-s3-publication')
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION, instruction)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)
    try:
        worker = threading.Thread(target=reader.run, daemon=True)
        worker.start()
        os.write(writer_fd, b'world')
        assert paused.wait(5) is True
        snapshot = reader.snapshot()
        release.set()
        os.close(writer_fd)
        worker.join(5)
        # the mixed state of the old publication is gone
        assert not (snapshot['hashed_bytes'] == 5 and snapshot['total_observed'] == 0)
        assert snapshot['hashed_bytes'] == snapshot['total_observed']
        assert_consistent_snapshot(snapshot, reader.raw())
        final = reader.snapshot()
        assert final['total_observed'] == 5
        assert final['hashed_bytes'] == 5
        assert final['complete'] is True
        assert final['hash_scope'] == 'all_observed'
        assert final['sha256'] == hashlib.sha256(b'world').hexdigest()
    finally:
        sys.monitoring.set_local_events(5, code, 0)
        sys.monitoring.free_tool_id(5)
        release.set()
        stream.close()


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
                        'per_child_kill_seconds': 1,
                        'per_child_stop_attempts': 3}
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

        def settle_session(self):
            return 1.0

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

        def settle_session(self):
            return 1.0

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

        def settle_session(self):
            return 1.0

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


# ------------------------- the lifecycle corrections of the third review
class GoodHandle:
    def flush(self):
        return None

    def close(self):
        return None


def test_the_stop_never_exceeds_the_absolute_child_deadline(tmp_path):
    """CPU-TERMINATION-DEADLINE: one absolute stop deadline."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class AdvancingProcess:
        pid = os.getpid()

        def __init__(self):
            self.waits = []

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits.append(timeout)
            self.clock.now += timeout if timeout else 0.0
            raise TimeoutError('injected timeout')

        def terminate(self):
            return None

        def kill(self):
            return None

    process = AdvancingProcess()
    process.clock = clock
    executor.register(process)
    entry = executor.children[0]
    clock.now = 9.5
    executor._stop_child(entry, session_deadline=clock.now + 100.0)
    # the stop never passes the ten second child deadline, not even with two
    # timeout waits
    assert clock.now <= 10.0 + 0.001
    assert process.waits[0] <= 0.5 + 0.001
    assert process.waits[1] <= 0.001
    assert len(process.waits) == 2


def test_the_stop_is_clipped_to_the_session_deadline(tmp_path):
    """CPU-TERMINATION-DEADLINE: the session deadline clips the stop."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class AdvancingProcess:
        pid = os.getpid()

        def __init__(self):
            self.waits = []

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits.append(timeout)
            self.clock.now += timeout if timeout else 0.0
            raise TimeoutError('injected timeout')

        def terminate(self):
            return None

        def kill(self):
            return None

    process = AdvancingProcess()
    process.clock = clock
    executor.register(process)
    entry = executor.children[0]
    clock.now = 9.0
    executor._stop_child(entry, session_deadline=9.4)
    assert clock.now <= 9.4 + 0.001
    assert process.waits[1] <= 0.001


def test_the_watchdog_still_acts_on_an_unknown_live_handle(tmp_path):
    """CPU-UNKNOWN-WATCHDOG: an unknown handle keeps the bounded safety."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class FailingProcess:
        pid = os.getpid()
        attempts = 0

        def poll(self):
            return None

        def wait(self, timeout=None):
            raise TimeoutError('the child never exits')

        def terminate(self):
            FailingProcess.attempts += 1
            raise OSError('injected terminate failure')

        def kill(self):
            FailingProcess.attempts += 1
            raise OSError('injected kill failure')

    process = FailingProcess()
    executor.register(process)
    entry = executor.children[0]
    clock.now = 9.0
    proofs = executor.reap()
    # the initial stop failed: the child stays unknown and unproven
    assert entry['state'] == 'UNKNOWN'
    assert proofs[0]['proven'] is False
    assert executor.uncertain is True
    # the watchdog still performs the bounded safety action on the unknown
    # original handle
    clock.now = 9.5
    deadline = time.monotonic() + 3.0
    while entry.get('stop_attempts', 0) == 0 and time.monotonic() < deadline:
        time.sleep(0.02)
    assert entry.get('stop_attempts', 0) >= 1
    # the action is bounded and never a busy loop
    time.sleep(0.25)
    assert entry['stop_attempts'] <= 3
    executor.revoke_admissions()


def test_the_finalization_settles_the_session_through_the_real_path(tmp_path):
    """CPU-SETTLEMENT-NOT-WIRED: the real finalization settles the session."""
    charges = [{'index': 0, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'started_wall': 0.0, 'state': 'UNKNOWN', 'exit_code': None,
                'pid': None, 'birth': None, 'finished_wall': None,
                'observed_lifetime_seconds': None, 'settled': True}]
    counter = fake_root_counter(tmp_path, starts_total=1,
                                by_role={'implementation': 1, 'independent_review': 0},
                                charges=charges)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    executor.reserve_session()
    clock.now = 12.0
    owned = tmp_path / 'owned'
    owned.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    document = json.loads(counter.read_text())
    assert document['sessions'][0]['state'] == 'SETTLED'
    assert document['spent_wall_seconds'] == 12.0
    assert outcome['session_spent'] == 12.0
    assert outcome['cleanup_proven'] is True
    assert outcome['exit_code'] == 0
    # the evidence is captured after the settlement
    assert outcome['session_evidence']['counter']['sessions'][0]['state'] == 'SETTLED'
    # the unknown custody stays explicit and the charge is never released
    assert document['charges'][0]['state'] == 'UNKNOWN'
    assert executor.counter._occupied(document) == 1


def test_a_failing_settlement_keeps_the_root_and_a_nonzero_receipt(tmp_path):
    """CPU-SETTLEMENT-NOT-WIRED: an ordinary settlement failure is not a pass."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    executor.reserve_session()
    clock.now = 5.0
    # the counter becomes unusable for the settlement
    counter.unlink()
    counter.mkdir()
    owned = tmp_path / 'owned'
    owned.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert any(reason.startswith('SESSION_SETTLEMENT_FAILED')
               for reason in outcome['failure_reasons'])
    # The removal of the owned root happens before the settlement, so the
    # diagnostic marker of a failed settlement is the control anchor, not the
    # removed temporary root.
    anchor = tmp_path / 'anchor.json'
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {},
        remover=lambda path: shutil.rmtree(path), anchor_path=anchor)
    assert outcome['exit_code'] != 0
    assert anchor.exists()


# ------------------------- the lifecycle corrections of the fourth review
def test_the_reap_final_wait_never_passes_the_child_deadline(tmp_path):
    """CPU-REAP-FINAL-WAIT: the proof wait uses the same absolute deadline."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)

    class UnprovableProcess:
        pid = os.getpid()

        def __init__(self):
            self.waits = []

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits.append(timeout)
            self.clock.now += timeout if timeout else 0.0
            raise TimeoutError('the child never exits')

        def terminate(self):
            return None

        def kill(self):
            return None

    process = UnprovableProcess()
    process.clock = clock
    executor.register(process)
    entry = executor.children[0]
    clock.now = 9.5
    proofs = executor.reap()
    # the last wait is clipped to the absolute child deadline
    assert clock.now <= 10.0 + 0.001
    assert process.waits[-1] <= 0.5 + 0.001
    # the child stays unknown and unproven, and it keeps its slot
    assert entry['state'] == 'UNKNOWN'
    assert proofs[0]['proven'] is False
    assert executor.uncertain is True
    assert executor.counter._occupied(json.loads(counter.read_text())) == 0


def test_the_reap_final_wait_is_clipped_to_the_session_deadline(tmp_path):
    """CPU-REAP-FINAL-WAIT: the session deadline clips the proof wait."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    executor.reserve_session()

    class UnprovableProcess:
        pid = os.getpid()

        def __init__(self):
            self.waits = []

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits.append(timeout)
            self.clock.now += timeout if timeout else 0.0
            raise TimeoutError('the child never exits')

        def terminate(self):
            return None

        def kill(self):
            return None

    process = UnprovableProcess()
    process.clock = clock
    executor.register(process)
    executor.cleanup_deadline = 9.4
    clock.now = 9.0
    executor.reap()
    assert clock.now <= 9.4 + 0.001
    assert process.waits[-1] <= 0.4 + 0.001


def test_the_whole_terminal_path_is_bounded_and_accounted(tmp_path):
    """The full path revoke, stop, proof wait, hash, remove, settle, evidence."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    executor.reserve_session()

    class UnprovableProcess:
        pid = os.getpid()

        def __init__(self):
            self.waits = []

        def poll(self):
            return None

        def wait(self, timeout=None):
            self.waits.append(timeout)
            self.clock.now += timeout if timeout else 0.0
            raise TimeoutError('the child never exits')

        def terminate(self):
            return None

        def kill(self):
            return None

    process = UnprovableProcess()
    process.clock = clock
    executor.register(process)
    owned = tmp_path / 'owned'
    owned.mkdir()
    anchor = tmp_path / 'anchor.json'

    def hasher():
        clock.now += 4.0
        return {'after': 'hash'}

    def remover(path):
        clock.now += 3.0
        shutil.rmtree(path)

    clock.now = 9.0
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=hasher, remover=remover, anchor_path=anchor)
    # the proof wait never passes the absolute child deadline
    assert clock.now <= 10.0 + 4.0 + 3.0 + 0.001
    assert process.waits[-1] <= 1.0 + 0.001
    # the unknown custody stays explicit and the charge is never released
    assert executor.children[0]['state'] == 'UNKNOWN'
    document = json.loads(counter.read_text())
    # the global actual wall includes the hash and the removal work
    assert document['sessions'][0]['state'] == 'SETTLED'
    assert document['spent_wall_seconds'] >= 7.0
    assert outcome['session_spent'] >= 7.0
    # the evidence was captured after the settlement
    assert outcome['session_evidence']['counter']['sessions'][0]['state'] == 'SETTLED'
    # an unproven child means no proven cleanup and a nonzero receipt
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0


def test_a_failed_settlement_keeps_the_anchor_and_the_evidence(tmp_path):
    """CPU-SETTLE-BEFORE-CLEANUP: a failed settlement keeps a diagnostic marker."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    executor.reserve_session()
    owned = tmp_path / 'owned'
    owned.mkdir()
    anchor = tmp_path / 'anchor.json'
    counter.unlink()
    counter.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {},
        remover=lambda path: shutil.rmtree(path), anchor_path=anchor)
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert any(reason.startswith('SESSION_SETTLEMENT_FAILED')
               for reason in outcome['failure_reasons'])
    # the diagnostic anchor survives the failed settlement
    assert anchor.exists()
    assert 'lvw.s3-settlement-anchor/1' in anchor.read_text()


# ------------------------- the audit correction of the fifth review
# The root cause of the failed finite fixture run of the audit correction:
# the runner installed its audit hook at the import of the module, so the
# module alias that this file loads installed a *second* hook with a second,
# closed gate.  The second hook vetoed every start that the first hook had
# already admitted and charged: the charges stayed PENDING without a handle,
# the concurrency slots stayed occupied and every later start was refused.
# The correction installs the one guard of the process in the production
# bootstrap, and it settles every charge whose start never produced a handle.
RUNNER_RELATIVE = ('reports/v0-s3/product-gate0/implementation-integration-01/'
                    'run_guarded_checks.py')


def load_runner_alias(name):
    """Load the guarded runner of this report subtree under another name."""
    path = PACK_ROOT / RUNNER_RELATIVE
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProbeReached(Exception):
    """The sentinel of the zero process probe of the audit event."""


def test_the_module_alias_shares_the_one_guard_and_never_installs_a_second_hook():
    """AUDIT-CORRECTION: an import of the runner installs no second guard."""
    registry = RUNNER_MODULE.guard_registry()
    owner = RUNNER_MODULE.install_offline_guard()
    assert registry.hook_installed is True
    assert registry.hook_install_count == 1
    before = registry.hook_install_count
    alias = load_runner_alias('lvw_s3_guarded_runner_alias')
    # the alias import did not install a second hook of its own
    assert registry.hook_install_count == before
    # the alias shares the one gate, the one registry and the one owner
    assert alias.PROCESS_GATE is RUNNER_MODULE.PROCESS_GATE
    assert alias.guard_registry() is registry
    assert alias.OfflineBoundaryViolation is RUNNER_MODULE.OfflineBoundaryViolation
    # the installation stays idempotent for the alias as well
    assert alias.install_offline_guard() == owner
    assert registry.hook_install_count == before
    assert registry.owner_id == owner


def test_the_production_entry_owns_the_guard_and_the_alias_shares_its_owner():
    """AUDIT-CORRECTION: the production entry owns the one guard."""
    registry = RUNNER_MODULE.guard_registry()
    main_module = sys.modules.get('__main__')
    runner_path = (PACK_ROOT / RUNNER_RELATIVE).resolve()
    entry_path = getattr(main_module, '__file__', None)
    if not entry_path or Path(entry_path).resolve() != runner_path:
        pytest.skip('this process is not the production entry of the runner')
    # the production bootstrap installed the one guard of this process
    assert registry.hook_installed is True
    assert registry.hook_install_count == 1
    assert registry.installed_by == 'run_guarded_checks.py'
    # the production entry and the module alias share the one owner
    assert main_module.PROCESS_GATE is RUNNER_MODULE.PROCESS_GATE
    assert main_module.guard_registry() is registry
    assert main_module.install_offline_guard() == registry.owner_id
    assert registry.hook_install_count == 1


def test_the_single_guard_admits_a_start_once_and_is_never_vetoed_twice(monkeypatch):
    """AUDIT-CORRECTION: one guard, one gate, one admission.

    The probe raises the audit event of a process start by hand.  It never
    reaches an operating system action, so no child is ever created, and the
    guard of this process is observed exactly as it is in the real chain.
    """
    registry = RUNNER_MODULE.guard_registry()
    RUNNER_MODULE.install_offline_guard()
    gate = RUNNER_MODULE.PROCESS_GATE
    admitted = []

    class RecordingExecutor:
        def admit(self, arguments):
            admitted.append(arguments)
            return True

    def fake_popen(command, **kwargs):
        # the real start raises this audit event before the fork; the probe
        # raises it by hand and never reaches an operating system action
        sys.audit('subprocess.Popen', kwargs.get('executable') or command[0],
                  list(command), kwargs.get('cwd'), kwargs.get('env'))
        raise ProbeReached()

    original_executor = gate.get('executor')
    original_starts = gate.get('starts')
    gate['executor'] = RecordingExecutor()
    gate['starts'] = 0
    monkeypatch.setattr(_subprocess, 'Popen', fake_popen)
    try:
        with pytest.raises(ProbeReached):
            _subprocess.Popen(['/bin/true'])
    finally:
        gate['executor'] = original_executor
        gate['starts'] = original_starts
    # the one guard admitted the start exactly once and never vetoed it
    assert len(admitted) == 1
    assert admitted[0][0] == '/bin/true'


def test_the_offline_boundary_still_blocks_a_process_and_a_socket():
    """AUDIT-CORRECTION: the zero process boundary is still a real guard."""
    import socket
    RUNNER_MODULE.install_offline_guard()
    # the process boundary: the audit event of a start is refused before the
    # fork, so no child is created
    with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation):
        sys.audit('subprocess.Popen', '/bin/true', ['/bin/true'], None, None)
    # the network boundary: the name resolution is refused before any query
    with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation):
        socket.gethostbyname('localhost')


@contextlib.contextmanager
def guard_gate(executor):
    """The gate of this process, with the synthetic executor of a test.

    The gate belongs to the process wide registry, so the production entry
    and this alias share it.  The exchange is restored in every case: a test
    never leaves a gate behind.
    """
    gate = RUNNER_MODULE.PROCESS_GATE
    original_executor = gate.get('executor')
    original_starts = gate.get('starts')
    gate['executor'] = executor
    gate['starts'] = 0
    try:
        yield gate
    finally:
        gate['executor'] = original_executor
        gate['starts'] = original_starts


def test_a_refused_start_that_never_forked_is_settled_and_frees_its_slot(tmp_path,
                                                                         monkeypatch):
    """AUDIT-CORRECTION: a proven before fork refusal is never a pending charge."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class RefusingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real guard of this process admits the start and the
            # executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # and the real guard refuses the process creation inside the
            # audit event: the child is never created
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', RefusingSubprocess)
    with guard_gate(executor):
        with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation):
            executor.spawn(command)
    document = json.loads(counter.read_text())
    # the charge has a terminal state and is never removed nor refunded
    assert len(document['charges']) == 1
    assert document['charges'][0]['state'] == 'REFUSED_BEFORE_FORK'
    assert document['charges'][0]['settled'] is True
    assert document['charges'][0]['pid'] is None
    assert document['starts_total'] == 1
    # the concurrency slot of a proven refusal is released
    assert executor.counter._occupied(document) == 0
    assert executor.uncertain is False
    assert executor.unsettled_charges() == []
    # a new legitimate admission is not blocked by a wrong pending charge
    executor.admit((sys.executable, command, str(tmp_path), None))
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 2
    assert len(document['charges']) == 2


def test_an_unknown_start_keeps_its_charge_its_slot_and_the_root(tmp_path, monkeypatch):
    """AUDIT-CORRECTION: an ordinary failure of the start keeps the custody."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class FailingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the guard admitted the start and charged it
            executor.admit((sys.executable, list(argv), str(tmp_path), None))
            # and the operating system action failed after the admission: the
            # child may exist, the custody is unknown
            raise OSError('the operating system action failed after the admission')

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', FailingSubprocess)
    with pytest.raises(OSError):
        executor.spawn(command)
    document = json.loads(counter.read_text())
    # the charge is settled as unknown and keeps its slot
    assert document['charges'][0]['state'] == 'UNKNOWN'
    assert document['charges'][0]['settled'] is True
    assert document['starts_total'] == 1
    assert executor.counter._occupied(document) == 1
    assert executor.uncertain is True
    unsettled = executor.unsettled_charges()
    assert len(unsettled) == 1
    assert unsettled[0]['outcome'] == 'UNKNOWN'
    # the session refuses a new admission while the custody is unknown
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        executor.admit((sys.executable, command, str(tmp_path), None))
    assert error.value.code == 'SESSION_UNCERTAIN_CUSTODY'


def test_the_finalizer_never_claims_a_proven_cleanup_with_an_open_charge(tmp_path):
    """AUDIT-CORRECTION: an open charge is never a proven cleanup."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    # an admitted start that never produced a handle
    executor.admit((sys.executable, executor_prefix() + ['clean_terminal'], None, None))
    owned = tmp_path / 'owned'
    owned.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert any(reason.startswith('UNSETTLED_CHARGE')
               for reason in outcome['failure_reasons'])
    # the root is retained and the charge stays visible in the counter
    assert owned.exists()
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'UNKNOWN'
    assert document['starts_total'] == 1
    assert executor.counter._occupied(document) == 1


def test_the_machine_accounting_separates_the_admissions_from_the_created_handles(
        tmp_path, monkeypatch):
    """AUDIT-CORRECTION: the receipt never counts an admission as a child."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class RefusingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real guard of this process admits the start and the
            # executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # and the real guard refuses the process creation inside the
            # audit event: the child is never created
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', RefusingSubprocess)
    with guard_gate(executor):
        with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation):
            executor.spawn(command)
    evidence = executor.session_evidence()
    accounting = RUNNER_MODULE.process_accounting(RUNNER_MODULE.guard_registry(),
                                                   evidence)
    # one admission, no child: the two numbers are never the same number
    assert accounting['admitted_attempts'] == 1
    assert accounting['child_handles_obtained'] == 0
    assert accounting['proven_child_handles'] == 0
    # the legacy field keeps its value and states its own meaning
    assert accounting['fixture_process_starts'] == 1
    assert 'NOT a number of created' in accounting['fixture_process_starts_semantics']
    # the refused charge is visible with its own terminal state
    assert accounting['charges_without_handle'][0]['outcome'] == 'REFUSED_BEFORE_FORK'


# ------------------------- the audit correction of the sixth review
# The independent review of the candidate 74ff021934afef661f8c7e8c1c4f11b26f7c3360
# found four defects and the root adopted all of them:
#
#   M1  the before fork release trusted a marker and a copied gate error, so
#       a fabricated error and a replayed old refusal released the slot of a
#       charge that was never refused;
#   M2  a settlement that the counter did not accept was still written as a
#       local terminal state, so the finalizer claimed a proven cleanup of a
#       charge that was still open;
#   M3  the registration of the guard was promised before it happened, so a
#       registration that CPython silently suppressed still ran the tests;
#   m1  the receipt saved a base command that did not reproduce the run.
#
# The tests below are the directed cases of those four defects.  Every
# positive case goes through the real guard of this process: the refusal is
# produced by the real hook, never by an exception that a test builds by
# hand.


class SettledChild:
    """A child handle that reports a proven exit without a real process."""

    pid = None

    def __init__(self):
        self.waits = 0
        self.stopped = False

    def poll(self):
        return 0

    def wait(self, timeout=None):
        self.waits += 1
        return 0

    def terminate(self):
        self.stopped = True
        return None

    def kill(self):
        self.stopped = True
        return None


def test_the_real_guard_refusal_releases_the_slot_of_its_own_charge(tmp_path,
                                                                   monkeypatch):
    """M1: the real guard proves its own refusal and only that one."""
    RUNNER_MODULE.install_offline_guard()
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class RealGuardSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real audit event of the start: the real guard of this
            # process admits it and the executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # the real audit event of the process creation: the real guard
            # refuses it, so the child is never created.  No operating system
            # action is reached at all.
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', RealGuardSubprocess)
    with guard_gate(executor):
        with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation) as caught:
            executor.spawn(command)
    violation = caught.value
    # the refusal of the real guard carries its one time credential
    credential = getattr(violation, RUNNER_MODULE.REFUSAL_CREDENTIAL, None)
    assert credential is not None
    assert credential.executor_id == executor.executor_id
    assert credential.charge_index == 0
    assert credential.consumed is True
    document = json.loads(counter.read_text())
    assert len(document['charges']) == 1
    assert document['charges'][0]['state'] == 'REFUSED_BEFORE_FORK'
    assert document['charges'][0]['settled'] is True
    assert document['charges'][0]['pid'] is None
    # the slot of the charge of this very action is released
    assert executor.counter._occupied(document) == 0
    assert executor.uncertain is False
    assert executor.unsettled_charges() == []
    assert executor.charge_ledger()[0]['settlement_persisted'] is True


def test_a_copied_marker_and_a_copied_gate_error_release_nothing(tmp_path,
                                                                  monkeypatch):
    """M1: an exception that only claims a refusal releases nothing."""
    RUNNER_MODULE.install_offline_guard()
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    fabricated = RuntimeError('an ordinary exception with copied attributes')
    fabricated.lvw_before_fork = True
    fabricated.gate_error = EXECUTOR_MODULE.CpuGateError('COPIED_GATE_ERROR')

    class CopyingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real guard admits the start and the executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # the failure that follows only *claims* a before fork refusal
            raise fabricated

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', CopyingSubprocess)
    with guard_gate(executor):
        with pytest.raises(RuntimeError):
            executor.spawn(command)
    document = json.loads(counter.read_text())
    # the charge stays open: it keeps its slot and its reservation
    assert document['charges'][0]['state'] == 'UNKNOWN'
    assert document['charges'][0]['settled'] is True
    assert executor.counter._occupied(document) == 1
    assert executor.uncertain is True
    unsettled = executor.unsettled_charges()
    assert len(unsettled) == 1
    assert unsettled[0]['outcome'] == 'UNKNOWN'
    # the claim of the exception was never taken for a proof
    assert getattr(fabricated, RUNNER_MODULE.REFUSAL_CREDENTIAL, None) is None


def test_a_replayed_real_guard_refusal_releases_nothing(tmp_path, monkeypatch):
    """M1: a real refusal of an earlier action never releases a later slot."""
    RUNNER_MODULE.install_offline_guard()
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class RefusingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', RefusingSubprocess)
    with guard_gate(executor):
        with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation) as caught:
            executor.spawn(command)
    replayed = caught.value

    class ReplayingSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # a new start of a new action: the real guard admits it and the
            # executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # and the refusal of the *earlier* action is replayed
            raise replayed

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', ReplayingSubprocess)
    with guard_gate(executor):
        with pytest.raises(RUNNER_MODULE.OfflineBoundaryViolation):
            executor.spawn(command)
    document = json.loads(counter.read_text())
    assert len(document['charges']) == 2
    # the first charge was really refused and was released
    assert document['charges'][0]['state'] == 'REFUSED_BEFORE_FORK'
    # the replayed refusal releases nothing: the second charge stays open
    assert document['charges'][1]['state'] == 'UNKNOWN'
    assert executor.counter._occupied(document) == 1
    assert executor.uncertain is True
    unsettled = executor.unsettled_charges()
    assert len(unsettled) == 1
    assert unsettled[0]['index'] == 1


def test_a_charge_whose_settlement_failed_stays_open_and_keeps_the_root(tmp_path,
                                                                       monkeypatch):
    """M2: a settlement that the counter refused is not a terminal state."""
    RUNNER_MODULE.install_offline_guard()
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']

    class FailingFinishSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real guard admits the start and the executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # the counter becomes unreadable: the settlement of the charge
            # cannot be persisted
            def refuse(*args, **kwargs):
                raise EXECUTOR_MODULE.CpuGateError('CPU_COUNTER_UNREADABLE')
            executor.counter.finish = refuse
            # and the operating system action fails after the admission
            raise OSError('the operating system action failed after the admission')

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', FailingFinishSubprocess)
    with guard_gate(executor):
        with pytest.raises(OSError):
            executor.spawn(command)
    document = json.loads(counter.read_text())
    # the charge was never persisted as a terminal state: it stays pending
    assert document['charges'][0]['state'] == 'PENDING'
    assert document['charges'][0]['settled'] is False
    # the local ledger does not claim a persisted terminal state
    ledger = executor.charge_ledger()
    assert ledger[0]['outcome'] == 'UNKNOWN'
    assert ledger[0]['settlement_persisted'] is False
    assert ledger[0]['settlement_error'] == 'CPU_COUNTER_UNREADABLE'
    # the charge keeps its slot and the session stays uncertain
    assert executor.counter._occupied(document) == 1
    assert executor.uncertain is True
    unsettled = executor.unsettled_charges()
    assert len(unsettled) == 1
    assert unsettled[0]['settlement_persisted'] is False
    # the finalizer keeps the root and does not claim a proven cleanup
    owned = tmp_path / 'owned'
    owned.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert owned.exists()


def test_the_proof_of_a_child_is_never_written_before_its_settlement(tmp_path,
                                                                     monkeypatch):
    """M2: a proven exit with a failed settlement is not a proven cleanup."""
    RUNNER_MODULE.install_offline_guard()
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    command = executor_prefix() + ['clean_terminal']
    child = SettledChild()

    class HandledSubprocess:
        PIPE = _subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            # the real guard admits the start and the executor charges it
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(tmp_path), None)
            # the handle of the child is taken by the executor
            return child

    monkeypatch.setattr(EXECUTOR_MODULE, 'subprocess', HandledSubprocess)
    with guard_gate(executor):
        process = executor.spawn(command)
        assert process is child
        # the counter becomes unreadable before the settlement of the child
        def refuse(*args, **kwargs):
            raise EXECUTOR_MODULE.CpuGateError('CPU_COUNTER_UNREADABLE')
        executor.counter.finish = refuse
        proofs = executor.reap()
    assert len(proofs) == 1
    # the exit of the child was proven, the settlement of its charge was not
    assert proofs[0]['proven'] is True
    assert proofs[0]['persisted'] is False
    assert proofs[0]['settlement_error'] == 'CPU_COUNTER_UNREADABLE'
    # the charge stays open and the session stays uncertain
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    assert executor.counter._occupied(document) == 1
    assert executor.uncertain is True
    unsettled = executor.unsettled_charges()
    assert len(unsettled) == 1
    assert unsettled[0]['settlement_persisted'] is False
    # the finalizer keeps the root and does not claim a proven cleanup
    owned = tmp_path / 'owned'
    owned.mkdir()
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {}, remover=lambda path: shutil.rmtree(path))
    assert outcome['cleanup_proven'] is False
    assert outcome['exit_code'] != 0
    assert any(reason.startswith('CHARGE_SETTLEMENT_FAILED')
               for reason in outcome['failure_reasons'])
    assert owned.exists()


def test_the_guard_installation_is_proved_by_an_owner_bound_handshake():
    """M3: the guard is only promised after its own handshake answered."""
    registry = RUNNER_MODULE.guard_registry()
    owner = RUNNER_MODULE.install_offline_guard()
    assert registry.hook_installed is True
    assert registry.hook_install_count == 1
    assert registry.install_error is None
    # the handshake of this owner was really seen by the hook of this process
    assert registry.handshake_count > 0
    before = registry.handshake_count
    # a handshake of a foreign owner is never counted
    sys.audit(RUNNER_MODULE.GUARD_HANDSHAKE_EVENT, 'owner-of-another-process',
              registry.handshake_token)
    assert registry.handshake_count == before
    # the handshake of this owner is counted
    assert RUNNER_MODULE.guard_handshake() is True
    assert registry.handshake_count == before + 1


def test_a_refused_guard_installation_fails_closed_and_keeps_the_evidence(monkeypatch,
                                                                        tmp_path):
    """M3: a registration that raised never claims an installed guard."""
    fresh = RUNNER_MODULE._GuardRegistry()
    monkeypatch.setitem(sys.modules, RUNNER_MODULE.GUARD_REGISTRY_MODULE, fresh)
    calls = []

    def refuse(hook):
        calls.append(hook.__name__)
        raise RuntimeError('hook registration failure')

    monkeypatch.setattr(sys, 'addaudithook', refuse)
    with pytest.raises(RUNNER_MODULE.GuardInstallationError) as error:
        RUNNER_MODULE.install_offline_guard()
    assert error.value.code == 'GUARD_REGISTRATION_FAILED'
    # the registration was attempted once and nothing was promised
    assert calls == ['_audit_hook']
    assert fresh.hook_installed is False
    assert fresh.hook_install_count == 0
    assert fresh.install_error is not None
    # a later call does not succeed on the word of an unconfirmed flag
    with pytest.raises(RUNNER_MODULE.GuardInstallationError):
        RUNNER_MODULE.install_offline_guard()
    assert fresh.hook_installed is False
    assert fresh.hook_install_count == 0
    # the evidence of the refusal is written and the exit code is not zero
    outdir = tmp_path / 'out'
    outdir.mkdir()
    arguments = type('Arguments', (), {'mode': 'focused', 'label': 'refused-install',
                                       'outdir': str(outdir)})()
    code = RUNNER_MODULE.guard_install_failure(outdir, arguments, error.value)
    assert code != 0
    receipt = json.loads((outdir / 'refused-install.receipt.json').read_text())
    assert receipt['guard_installed'] is False
    assert receipt['outcome'] == 'FAIL'
    assert receipt['pytest_imported'] is False
    assert receipt['candidate_imported'] is False
    assert receipt['stage_pass_claim'] is False
    assert receipt['product_gate0'] is False


def test_the_receipt_saves_the_complete_effective_command():
    """m1: the receipt reproduces the run, including every control argument."""
    arguments = type('Arguments', (), {
        'mode': 'focused', 'label': 'complete-command', 'select': 'refusal or guard',
        'modules': 'tools/test_v0_s3_supervisor.py',
        'binding': '/sealed/binding.json',
        'binding_sha256': 'a' * 64, 'role': 'implementation',
        'candidate_sha': 'b' * 40})()
    command = RUNNER_MODULE.build_effective_command(arguments, '/out/dir')
    assert command[0] == sys.executable
    assert command[1] == '-B'
    assert command[2].endswith('run_guarded_checks.py')
    assert command[3:] == ['--mode', 'focused', '--label', 'complete-command',
                           '--outdir', '/out/dir',
                           '--select', 'refusal or guard',
                           '--modules', 'tools/test_v0_s3_supervisor.py',
                           '--binding', '/sealed/binding.json',
                           '--binding-sha256', 'a' * 64,
                           '--role', 'implementation',
                           '--candidate-sha', 'b' * 40]
    # the invocation of this process is reported, never guessed
    invocation = RUNNER_MODULE.invocation_evidence(command)
    assert invocation['kind'] in ('process', 'programmatic', 'UNKNOWN')
    if invocation['kind'] == 'UNKNOWN':
        assert invocation['outer_argv'] is None
    else:
        assert isinstance(invocation['outer_argv'], list)


# ------------------- the sequential reuse of the concurrency slot (G3)
class FakeChildHandle:
    """A fake child handle: no process, only the four calls of a handle.

    The handle is the *original* handle of the child from the point of view
    of the executor.  ``poll`` reports the exit of the child when it is set
    and it reports ``None`` while the child is alive.  A handle whose exit
    can never be observed refuses to answer at all.
    """

    def __init__(self, pid=4242, *, exit_code=None, provable=True):
        self.pid = pid
        self.returncode = exit_code
        self.provable = provable
        self.terminated = False
        self.killed = False

    def poll(self):
        if not self.provable:
            raise OSError('the exit of this child cannot be observed')
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def admit_one(executor):
    """One admitted start of the real executor API."""
    prefix = executor_prefix()
    argv = list(prefix) + ['clean_terminal']
    executor.admit((prefix[0], argv, None, None))


def admit_and_register(executor, child):
    """One admitted start with the custody of a fake child handle."""
    admit_one(executor)
    executor.register(child)
    return executor.children[-1]


def finalize_with(executor, tmp_path):
    """The outer finalizer of the runner, on a synthetic owned root.

    The finalizer is the real one of the accepted runner: it reaps the
    children, it settles the charges and it removes the owned root only
    after a proven cleanup.
    """
    owned = tmp_path / 'owned'
    owned.mkdir(exist_ok=True)
    outcome = RUNNER_MODULE.finalize_session(
        executor=executor, owned=owned, stdout_handle=GoodHandle(),
        stderr_handle=GoodHandle(), saved_out=os.dup(1), saved_err=os.dup(2),
        exit_code=0, source_hasher=lambda: {})
    return {'exit_code': outcome['exit_code'],
            'cleanup_proven': outcome['cleanup_proven'],
            'root_retained': owned.exists(),
            'failure_reasons': outcome['failure_reasons'],
            'proofs': outcome['proofs']}


def test_two_exited_children_release_their_slot_for_the_next_admission(tmp_path):
    """G3: a child that already exited never refuses the next sequential start.

    The sequential run admits its next start long before the final reap.
    A child whose original handle proves its exit keeps its charge in the
    ``STARTED`` state until the final accounting, so it used to hold its
    concurrency slot against the ghosts of its own previous children.
    """
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    first = FakeChildHandle()
    admit_and_register(executor, first)
    second = FakeChildHandle()
    admit_and_register(executor, second)
    # Both original handles report the exit of their child.
    first.returncode = 0
    second.returncode = 0
    admit_one(executor)
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 3
    assert document['charges'][0]['state'] == 'STOPPED'
    assert document['charges'][0]['settled'] is True
    assert document['charges'][1]['state'] == 'STOPPED'
    assert document['charges'][1]['settled'] is True
    assert document['charges'][2]['state'] == 'PENDING'


def test_thirteen_sequential_children_stay_inside_the_concurrency_bound(tmp_path):
    """G3: thirteen sequential children never exceed the concurrency bound."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    peak = 0
    for _ in range(13):
        child = FakeChildHandle()
        admit_and_register(executor, child)
        # The child of this position is gone before the next admission.
        child.returncode = 0
        document = json.loads(counter.read_text())
        peak = max(peak, EXECUTOR_MODULE.SharedCounter._occupied(document))
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 13
    assert len(document['charges']) == 13
    assert peak <= 2
    # Every child but the last one is settled and keeps its own evidence.
    assert [charge['state'] for charge in document['charges'][:-1]] == ['STOPPED'] * 12
    assert all(charge['settled'] is True for charge in document['charges'][:-1])
    assert document['charges'][-1]['state'] == 'STARTED'


def test_two_live_children_refuse_the_next_start_and_release_one_slot(tmp_path):
    """G3: a live child keeps its slot and only one slot is released."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    first = FakeChildHandle()
    admit_and_register(executor, first)
    second = FakeChildHandle()
    admit_and_register(executor, second)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_CONCURRENCY_LIMIT'
    # Exactly one of the two live children is gone.
    first.returncode = 0
    admit_one(executor)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_CONCURRENCY_LIMIT'
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 3
    assert document['charges'][0]['state'] == 'STOPPED'
    assert document['charges'][1]['state'] == 'STARTED'
    assert document['charges'][1]['settled'] is False


def test_an_unprovable_exit_keeps_its_concurrency_slot(tmp_path):
    """G3: a child whose exit can never be proven keeps its slot."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    unprovable = FakeChildHandle(provable=False)
    admit_and_register(executor, unprovable)
    exited = FakeChildHandle()
    admit_and_register(executor, exited)
    exited.returncode = 0
    # The exited child released its slot, the unprovable one did not.
    admit_one(executor)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_CONCURRENCY_LIMIT'
    document = json.loads(counter.read_text())
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    assert document['charges'][1]['state'] == 'STOPPED'


def test_a_settlement_that_the_counter_refuses_keeps_its_concurrency_slot(tmp_path,
                                                                         monkeypatch):
    """G3: a refused settlement releases nothing and fails the admission closed.

    The counter refuses the settlement of a child that has already exited.
    The slot of that child is kept, the session becomes uncertain and the
    next admission fails closed: no new charge is taken, even though the
    counter still has a free slot.  The refusal is explicit and it is not
    the concurrency limit of a full counter.
    """
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0
    monkeypatch.setattr(executor.counter, 'finish', lambda index, **keywords: False)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    document = json.loads(counter.read_text())
    # No new charge: a failed settlement never opens a new start.
    assert document['starts_total'] == 1
    assert len(document['charges']) == 1
    # The slot of the refused settlement is kept.
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    occupied = EXECUTOR_MODULE.SharedCounter._occupied(document)
    assert occupied == 1
    # The counter is not full: the refusal is not the concurrency limit.
    assert occupied < 2
    # The session is uncertain, so the next admission is refused as well.
    assert executor.uncertain is True
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as second:
        admit_one(executor)
    assert second.value.code == 'SESSION_UNCERTAIN_CUSTODY'
    assert json.loads(counter.read_text())['starts_total'] == 1
    # The finalizer keeps the owned root and its exit code is not zero.
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0
    assert 'CHARGE_SETTLEMENT_FAILED' in final['failure_reasons']


def test_a_settlement_gate_error_keeps_the_slot_and_fails_the_admission_closed(tmp_path,
                                                                              monkeypatch):
    """G3: a gate error of the settlement is a failure, never a release."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0

    def refuse(index, **keywords):
        raise EXECUTOR_MODULE.CpuGateError('CPU_CHARGE_STATE_INVALID')

    monkeypatch.setattr(executor.counter, 'finish', refuse)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'CPU_CHARGE_STATE_INVALID' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_a_settlement_io_error_keeps_the_slot_and_fails_the_admission_closed(tmp_path,
                                                                             monkeypatch):
    """G3: an ordinary I/O failure of the settlement is a failure too."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0

    def refuse(index, **keywords):
        raise OSError('the counter could not be written')

    monkeypatch.setattr(executor.counter, 'finish', refuse)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'CPU_COUNTER_IO_ERROR' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_an_unreadable_terminal_state_keeps_the_slot_and_fails_the_admission_closed(
        tmp_path, monkeypatch):
    """G3: a terminal state that cannot be read is never a release."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0

    def refuse(index):
        raise EXECUTOR_MODULE.CpuGateError('CPU_COUNTER_UNREADABLE')

    monkeypatch.setattr(executor.counter, 'charge_state', refuse)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'CPU_COUNTER_UNREADABLE' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert document['charges'][0]['state'] == 'STARTED'
    assert document['charges'][0]['settled'] is False
    assert executor.uncertain is True


def test_a_foreign_exit_code_keeps_the_slot_of_its_charge(tmp_path):
    """G3: a persisted exit code of another run is not an idempotent proof."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    entry = executor.children[-1]
    child.returncode = 0
    # The counter holds a terminal state of this index, but the exit code
    # belongs to another run.
    executor.counter.finish(0, state='STOPPED', exit_code=77, spent=1.0,
                            pid=entry['pid'], birth=entry['birth'])
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'EXIT_CODE_MISMATCH' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_a_foreign_handle_keeps_the_slot_of_its_charge(tmp_path):
    """G3: a persisted handle of another identity is not an idempotent proof."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0
    executor.counter.finish(0, state='STOPPED', exit_code=child.returncode, spent=1.0,
                            pid=999999, birth={'linux_start_ticks': 1})
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'PID_MISMATCH' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_a_foreign_charge_index_keeps_the_slot_of_its_charge(tmp_path, monkeypatch):
    """G3: a persisted record of another index is not an idempotent proof."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0

    def foreign(index):
        return {'index': 53, 'role': 'implementation', 'scenario': 'clean_terminal',
                'argv': [], 'settled': True, 'state': 'STOPPED', 'exit_code': 77,
                'pid': 999999, 'birth': {'foreign': 'session'}}

    monkeypatch.setattr(executor.counter, 'charge_state', foreign)
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'FOREIGN_CHARGE_INDEX' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_an_unknown_terminal_state_keeps_the_slot_of_its_charge(tmp_path):
    """G3: an UNKNOWN record is never an idempotent proof."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    entry = executor.children[-1]
    child.returncode = 0
    executor.counter.finish(0, state='UNKNOWN', exit_code=None, spent=None,
                            pid=entry['pid'], birth=entry['birth'])
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'CPU_RECONCILIATION_UNSETTLED'
    assert 'STATE_MISMATCH' in (error.value.detail or '')
    document = json.loads(counter.read_text())
    assert document['starts_total'] == 1
    assert executor.uncertain is True
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0


def test_a_local_settlement_marker_keeps_the_slot_and_the_root(tmp_path):
    """G3: the local marker never replaces the persisted proof.

    The counter is made to disagree with the local marker after a
    successful reconciliation.  The shared counter is the authority: the
    charge stays open, the finalizer keeps the root and the reaper never
    rewrites the record to fake a cleanup.
    """
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0
    outcome = executor.reconcile_exited_children()
    assert outcome['failures'] == []
    assert len(outcome['released']) == 1
    document = json.loads(counter.read_text())
    assert document['charges'][0]['settled'] is True
    # The counter diverges from the local marker of the executor.
    document['charges'][0].update(state='STARTED', settled=False, finished_wall=None)
    counter.write_text(json.dumps(document, sort_keys=True))
    final = finalize_with(executor, tmp_path)
    assert final['cleanup_proven'] is False
    assert final['root_retained'] is True
    assert final['exit_code'] != 0
    after = json.loads(counter.read_text())
    # The reaper never repaired the divergence to fake a proven cleanup.
    assert after['charges'][0]['settled'] is False
    assert after['charges'][0]['state'] == 'STARTED'


def test_the_finalizer_never_settles_a_settled_child_twice(tmp_path):
    """G3: the finalizer is idempotent for a child that is already settled."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    first = FakeChildHandle()
    admit_and_register(executor, first)
    first.returncode = 0
    second = FakeChildHandle()
    admit_and_register(executor, second)
    second.returncode = 0
    before = json.loads(counter.read_text())['charges'][0]
    assert before['settled'] is True
    executor.reap()
    after = json.loads(counter.read_text())['charges'][0]
    # The terminal state of the first child is not written a second time.
    assert after['finished_wall'] == before['finished_wall']
    assert after['observed_lifetime_seconds'] == before['observed_lifetime_seconds']
    assert after['settled'] is True
    # The cleanup is not faked and the session is not uncertain.
    assert executor.uncertain is False
    assert executor.unsettled_charges() == []
    assert executor.session_evidence()['settlement_failures'] == []


def test_the_reconciliation_keeps_the_window_the_source_and_the_single_owner(tmp_path):
    """G2/G3: the reconciliation releases a slot and changes nothing else."""
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest)
    context_inside(tmp_path)
    executor.reserve_session()
    admission_deadline = executor.admission_deadline
    cleanup_deadline = executor.cleanup_deadline
    registry = RUNNER_MODULE._guard_registry()
    owners_before = registry.hook_install_count
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0
    released = executor.reconcile_exited_children()
    assert released['failures'] == []
    assert len(released['released']) == 1
    assert released['released'][0]['state'] == 'STOPPED'
    # The window of the session is never rebased.
    assert executor.admission_deadline == admission_deadline
    assert executor.cleanup_deadline == cleanup_deadline
    # The admissions are never revoked by the reconciliation.
    assert executor.revoked is False
    # The identity of the candidate and of every source pin is still proven.
    assert executor.verify_identity()['candidate_sha'] == executor.candidate_sha
    # The audit guard of this process still has exactly one owner.
    assert registry.hook_install_count == owners_before
    assert registry.hook_install_count <= 1


def test_a_reconciliation_that_crosses_the_admission_window_refuses_the_start(tmp_path):
    """G3: a reconciliation that crosses the window refuses this start.

    The reconciliation is bounded, but it is not free: its own I/O spends
    the wall of the session.  When it crosses the fixed admission deadline,
    the start that follows it is refused before the new charge is taken and
    the deadline is never rebased.
    """
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    context_inside(tmp_path)
    child = FakeChildHandle()
    admit_and_register(executor, child)
    child.returncode = 0
    deadline = executor.admission_deadline
    # The reconciliation spends the rest of the window.
    original_finish = executor.counter.finish

    def slow_finish(index, **keywords):
        result = original_finish(index, **keywords)
        clock.now = deadline + 0.001
        return result

    executor.counter.finish = slow_finish
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'SESSION_ADMISSION_WINDOW_CLOSED'
    # No new charge: the start that crossed the window never happened.
    assert json.loads(counter.read_text())['starts_total'] == 1
    # The deadline of the session is never rebased by the reconciliation.
    assert executor.admission_deadline == deadline
    assert executor.cleanup_deadline is not None


def test_the_admission_window_boundary_after_a_reconciliation_is_exact(tmp_path):
    """G3: the boundary of the window is exact, one over included.

    The check of the window is not only the one of the beginning of the
    admission: it is repeated after the reconciliation, and it refuses the
    start exactly on the deadline and one second over it.
    """
    counter = fake_root_counter(tmp_path)
    path, digest, _ = fake_root_binding(tmp_path, counter_path=counter)
    clock = fake_clock()
    executor = build_test_executor(tmp_path, counter_path=counter, binding_digest=digest,
                                   clock=clock)
    context_inside(tmp_path)
    admit_one(executor)
    deadline = executor.admission_deadline
    # One second before the deadline the start is admitted.
    clock.now = deadline - 0.001
    admit_one(executor)
    assert json.loads(counter.read_text())['starts_total'] == 2
    # Exactly on the deadline the start is refused.
    clock.now = deadline
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'SESSION_ADMISSION_WINDOW_CLOSED'
    # One second over the deadline the start is refused as well.
    clock.now = deadline + 1.0
    with pytest.raises(EXECUTOR_MODULE.CpuGateError) as error:
        admit_one(executor)
    assert error.value.code == 'SESSION_ADMISSION_WINDOW_CLOSED'
    assert json.loads(counter.read_text())['starts_total'] == 2
    assert executor.admission_deadline == deadline
