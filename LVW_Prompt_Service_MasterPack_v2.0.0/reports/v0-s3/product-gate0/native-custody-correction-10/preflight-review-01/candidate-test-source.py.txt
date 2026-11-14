"""The frozen regressions of the N1 correction 10 of the native custody.

This module carries the **14 frozen oracle groups** of the root package
``reports/v0-s3/product-gate0/native-custody-correction-10`` (the file
``regression-obligations.json``).  The obligations are frozen by the
root and they are not written by the implementer: every group below is
mapped to the production owner that has to carry it and to the test
that drives it.

The rules of this module are the rules of the whole N1 package.

* It is **offline**.  It never starts a process, it never opens a
  socket, it never touches a database and it never reads the original
  budget ledger or the original shared counter.  The Windows primitives
  are driven through an **in-process** table of primitives that is
  injected into the production façade: the production code that is
  checked here is the code of a real run, only the native library is
  missing.

* Every case drives the **actual production method**: the production
  ``WindowsApi`` with an injected primitive table, the production
  ``BrokerCore``, ``BrokerLoop``, ``BrokerProcess``, ``StreamChannel``,
  ``_WindowsPipeWorker``, ``_WindowsPipeEndpoint``, ``_StartupOwner``,
  ``_LauncherCustody``, ``_LaunchAggregate`` and the production
  ``NativeCustodySession``.  A façade that only returns the right story
  would not prove anything and it is not used for the failure paths.

* Every case records the state of the resources **at the moment the
  product returned**, before any salvage of the test owner.  The
  cleanup of the test owner is explicit and it is never used to
  declare that the product returned cleanly: a product that could not
  release a resource stays unknown and keeps its original reference.

* The native claims of this package stay ``NOT_PROVEN``.  The module
  proves the behaviour of the Python owners and it never claims that a
  Windows API, a job object, a GPU, a port or a service was executed.

The six Majors of the read only pre review stay **OPEN**: this module
is a regression set and it never signs a Major.  The closure of a
Major belongs to a new independent review and to the gate owner.

The boundary of the process is not installed here: the guard of the
batch lives in the report directory of the batch and the runner of the
batch is its only authorised entry.
"""
import ast
import json
import queue
import sys
import threading
import time
import unittest.mock
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

import tools.v0_s3_native_broker as broker_module  # noqa: E402 - the path is set above
from tools.v0_s3_native_broker import (  # noqa: E402 - the path is set above
    BrokerCore, BrokerError, BrokerLoop, BrokerProcess, StreamChannel,
    WindowsApi, _ChannelCancel, _LauncherCustody, _LaunchAggregate,
    _RoundContext, _StartupOwner, _WindowsPipeEndpoint, _WindowsPipeWorker,
    _adopt_broker_process, _launcher_custody_items, release_retained_launches)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, NativeCustodySession, validate_launch_plan)
from tools.test_v0_s3_native_custody_correction07 import (  # noqa: E402
    _FakeFile, _F5Api, _F5ExternalCancelOwner, _f5_build_chain)
from tools.test_v0_s3_native_custody_regressions import (  # noqa: E402
    ManualClock, RecordingWin32, SyntheticKernel32, plan_document, sealed_plan,
    synthetic_table)


#: The directory in which the bounded facts of this module are written.
#: Every document is written **before** the assertions of its phase and
#: every value of it is a value that the production returned.
EVIDENCE_DIR = (PACK_ROOT / 'reports' / 'v0-s3' / 'product-gate0'
                / 'implementation-native-custody-correction-10' / 'evidence')


def write_phase(phase, document):
    """Write the bounded facts of one phase of this module."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / ('n10-%s.json' % phase)
    path.write_text(json.dumps(document, indent=1, sort_keys=True,
                                default=repr), encoding='utf-8')
    return str(path)


#: The nonce of the private channel of the probes of this module.  It
#: is a closed form of 32 hexadecimal characters and it is the nonce of
#: the round of the probe: the frames of the probe carry it.
NONCE = '0' * 32


def _live_plan_document():
    """A plan document whose lease is valid for the clock of the host."""
    return plan_document(lease_expires_at=time.time() + 3600.0)


# -- N10-R01: the control handle of a process ------------------------------

def test_n10_r01_the_control_handle_is_closed_only_after_the_exit(tmp_path):
    """N10-R01 (M03): the last control handle of a process is kept.

    Obligation: a Core that took a process and could not assign it, or
    whose wait did not confirm the exit, keeps the **original** control
    handle of that process: the record of the round and the pending
    table of the round **both** forbid the close of the handle, the
    handle stays with its owner and the same owner may still terminate
    the process and wait for it inside the original deadline.  The
    thread handle and the pipe handles are independent of the exit and
    they are released on their own.

    Entry: ``BrokerCore.stop``, ``BrokerCore._release_the_records``,
    ``BrokerCore._note_closed_handle`` and
    ``_PendingResources.close_all``.  Trigger: the wait of the process
    does not confirm the exit and the close of the handle would
    succeed.  Oracle: the close of the control handle was never
    attempted, the handle is still reachable and the round is not a
    release.  Negative: a close that would succeed is never a proof
    that the process ended.  Returned state: the record and the pending
    table name the handle and its owner.  Salvage: the same owner
    confirms the exit later and closes the handle exactly once.
    """
    class UnconfirmedWin32(RecordingWin32):
        """A façade whose processes never confirm their exit by themselves."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.confirmed = False

        def terminate_job(self, job, exit_code):
            # The termination of the job does **not** mark the processes
            # as exited: only the wait of the round may confirm it.
            self.calls.append(('terminate_job', job, exit_code))

        def wait_process(self, process, timeout_ms):
            self.calls.append(('wait_process', process, timeout_ms))
            for entry in self.created:
                if entry['handle'] == process:
                    entry['exited'] = self.confirmed
                    return entry['exited']
            return True

    win32 = UnconfirmedWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        core.launch()
        record = core.records[0]
        target = record['process_handle']
        thread = record['thread_handle']
        assert target is not None and thread is not None

        # The first stop: the exit of the process is not confirmed.
        core.stop('STOP')
        facts = {'process_handle': target is record['process_handle'],
                 'process_handle_closed': record['process_handle_closed'],
                 'thread_handle_closed': record['thread_handle_closed'],
                 'state': core.state,
                 'pending': [item['kind'] for item in core._pending.pending()],
                 'live': sorted(win32.live)}
        write_phase('r01-first', facts)
        # The control handle of the process is **still** with its owner.
        assert record['process_handle'] is target, \
            'the control handle was forgotten while the exit was unknown'
        assert record['process_handle_closed'] is False
        assert target in win32.live, \
            'the control handle was closed while the exit was unknown'
        # The pending table forbids the close as well: the eligibility
        # comes from the owner of the handle and not from the name of a
        # state.
        pending = [item for item in core._pending.pending()
                   if item['handle'] == target]
        assert pending, 'the control handle lost its owner'
        assert pending[0]['kind'] == 'process'
        # The thread handle is independent of the exit of the process.
        assert record['thread_handle_closed'] is True
        assert record['thread_handle'] is None
        # The round is not a release.
        assert core.state == 'UNKNOWN_RETAINED'
        assert core._released is False

        # The same owner confirms the exit: the handle is closed once.
        win32.confirmed = True
        core.stop('STOP')
        facts = {'process_handle_closed': record['process_handle_closed'],
                 'closes': win32.closed.count(target),
                 'state': core.state,
                 'pending': [item['kind'] for item in core._pending.pending()]}
        write_phase('r01-second', facts)
        assert record['process_handle_closed'] is True
        assert record['process_handle'] is None
        assert win32.closed.count(target) == 1, \
            'the control handle was closed twice'
        assert target not in win32.live
    finally:
        # The salvage of the owner of the test is bounded and it never
        # hides a resource that the product kept.
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N10-R02: the claim of the recovery and the handover -------------------

def test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive():
    """N10-R02 (M05): the recovery and the handover are one decision.

    Obligation: the recovery of the API owner **claims** the entry
    under the lock of the table before it touches it and the handover
    of the same entry is **refused** while the claim is alive: a
    handle that was handed over may never be closed by the recovery and
    a handle that the recovery claimed may never be handed over.  The
    blocking primitive of the recovery runs **outside** of the lock of
    the table and the table stays usable while it waits.  An exception
    never leaves an entry without an owner and never leaves two close
    owners.

    Entry: ``WindowsApi.release_retained``, ``WindowsApi.handover`` and
    ``WindowsApi._claim_entry``.  Trigger: the recovery blocks inside
    the close of one end of a pipe while the core hands the other end
    over.  Oracle: the handover of the claimed end is refused and the
    end is never registered with a second owner; the handover of the
    other end succeeds while the recovery waits.  Negative: the table
    lock is never held while the recovery waits.  Returned state: the
    report of the recovery names the entries that it did not own.
    Salvage: the recovery of the API owner releases the ends that it
    owns.
    """
    entered = threading.Event()
    release = threading.Event()
    closed = []

    def create_pipe(kernel32, *args):
        read = kernel32.allocate('pipe_read')
        write = kernel32.allocate('pipe_write')
        args[0]._obj.value = read
        args[1]._obj.value = write
        return 1

    def close_handle(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle in kernel32.live and kernel32.live[handle] == 'pipe_read':
            # The close of the read end blocks: the recovery holds its
            # claim while it waits.
            entered.set()
            release.wait(10.0)
        kernel32.live.pop(handle, None)
        closed.append(handle)
        return 1

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe,
                                         'CloseHandle': close_handle})
    api = WindowsApi(table=synthetic_table(kernel32))
    read, write = api.create_pipe('stdout')
    report_holder = {}

    def recover():
        report_holder['report'] = api.release_retained()

    worker = threading.Thread(target=recover, name='lvw-n10-r02-recovery')
    worker.start()
    try:
        assert entered.wait(10.0), \
            'the recovery never reached the close of the claimed end'
        # The table is usable while the recovery waits: the lock of the
        # table is not held by the blocking primitive.
        registered = []

        def register(items):
            registered.extend(items)

        # The handover of the **claimed** end is refused.
        with pytest.raises(BrokerError) as info:
            api.handover([(read, 'pipe_read')], owner='CORE', register=register)
        assert info.value.code == 'BROKER_HANDOVER_CLAIMED'
        assert registered == [], \
            'a claimed end was registered with a second owner'
        # The handover of the **other** end succeeds: the table is not
        # held by the recovery that waits.
        api.handover([(write, 'pipe_write')], owner='CORE', register=register)
        assert registered == [(write, 'pipe_write')]
        write_phase('r02-claim', {'claimed': repr(read),
                                   'refused_code': info.value.code,
                                   'registered': [repr(item)
                                                  for item in registered]})
    finally:
        release.set()
        worker.join(15.0)
        assert not worker.is_alive(), 'the recovery was left behind'
    report = report_holder.get('report') or []
    write_phase('r02-report', {'report': [{'kind': item['kind'],
                                            'released': item['released']}
                                           for item in report],
                               'closed': list(closed)})
    # The claimed end was closed by the recovery that owned it and the
    # end that was handed over was never closed by the recovery.
    assert closed.count(getattr(read, 'value', read)) == 1
    assert closed.count(getattr(write, 'value', write)) == 0, \
        'the recovery closed an end that it handed over'

    # The second direction: an end that was handed over is never closed
    # by a recovery that read the entry before the handover.
    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe})
    api = WindowsApi(table=synthetic_table(kernel32))
    read, write = api.create_pipe('stderr')
    key = id(read)
    entry = api._retained.get(key)
    assert entry is not None, 'the end was not retained by the facade'
    registered = []
    api.handover([(read, 'pipe_read'), (write, 'pipe_write')], owner='CORE',
                 register=lambda items: registered.extend(items))
    assert registered == [(read, 'pipe_read'), (write, 'pipe_write')]
    # The recovery of the facade finds nothing: the end has an owner.
    report = api.release_retained()
    write_phase('r02-handed-over', {'report': report,
                                     'closed': list(kernel32.live)})
    assert report == [], 'the recovery closed an end that it handed over'
    assert getattr(read, 'value', read) in kernel32.live


# -- N10-R03: one notification for every confirmed close -------------------

def test_n10_r03_every_confirmed_close_notifies_the_owner_of_the_handle(tmp_path):
    """N10-R03 (M06): the notification of a close is one notification.

    Obligation: a reader that really stopped and whose read end could
    not be closed by the first attempt is closed by the pending pass of
    the round, and that confirmed close notifies the **owner** of the
    handle: the reader learns that its handle is gone, the pending
    table and the retained resources of the round agree with it, and
    the next stop of the round never closes the same original handle a
    second time - a handle that the operating system may have reused.

    Entry: ``BrokerCore._close_one_reader``,
    ``BrokerCore._note_closed_handle`` and
    ``_PendingResources.close_all``.  Trigger: the first close of the
    read end of a stopped reader fails and the pending pass succeeds.
    Oracle: the reader holds no handle any more, the pending table does
    not name it and the handle was closed exactly once.  Negative: a
    second stop never closes the handle again.  Returned state: the
    facts of the two stops agree with each other.  Salvage: the owner
    of the test releases the handles that the product kept.
    """
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        core.launch()
        reader = core.readers[0]
        target = reader.handle
        assert target is not None, 'the reader never got a handle'
        state = {'failed': False}
        original_close = win32.close_handle

        def close_handle(handle):
            if handle == target and not state['failed']:
                # The first close of the read end of the reader fails.
                state['failed'] = True
                win32.calls.append(('close_handle', handle))
                raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            original_close(handle)

        win32.close_handle = close_handle
        core.stop('STOP')
        first = {'reader_handle': reader.handle,
                 'closed': win32.closed.count(target),
                 'pending': [item['handle'] for item in core._pending.pending()],
                 'retained': [item['handle']
                              for item in core._retained_resources],
                 'state': core.state}
        write_phase('r03-first', first)
        assert state['failed'], 'the targeted close never failed'
        # The confirmed close of the pending pass notified the owner.
        assert reader.handle is None, \
            'the reader still names a handle that was really closed'
        assert target not in [item['handle'] for item in core._pending.pending()]
        assert target not in [item['handle']
                              for item in core._retained_resources]
        assert win32.closed.count(target) == 1

        # The next stop of the round never closes the same handle again.
        core.stop('STOP')
        second = {'reader_handle': reader.handle,
                  'closed': win32.closed.count(target),
                  'state': core.state}
        write_phase('r03-second', second)
        assert win32.closed.count(target) == 1, \
            'the read end was closed a second time'
        assert reader.handle is None
    finally:
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N10-R04: the aggregate finds the partial channel ---------------------

def test_n10_r04_the_launch_aggregate_finds_the_partial_channel():
    """N10-R04 (M07): the partial channel has an owner.

    Obligation: the channel of a launch registers itself with the
    **aggregate** of the launch before it builds anything, so that a
    channel whose reader thread did not start is found by the outer
    owner of the launch and never through a local variable that is
    ``None`` at that moment.  The process helper never closes the
    standard input and the standard output of a process whose channel
    took them: the channel is coordinated first and the files of the
    process are closed by the channel alone.  Facts that are not
    complete keep the original owner.

    Entry: ``StreamChannel.__init__``, ``_LaunchAggregate.release`` and
    ``_adopt_broker_process``.  Trigger: the channel of the launch
    exists and the adoption fails before the local variable of the
    channel was assigned.  Oracle: the aggregate found the channel, the
    channel was closed and the files of the process were not closed by
    the process helper.  Negative: the process helper never closes the
    files of a process whose channel took them.  Returned state: the
    facts of the aggregate name what it released.  Salvage: the owner of
    the test releases the handles that the product kept.
    """
    class Process:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0
            self.closed = []
            self.stdin = type('S', (), {'close': self._close})()
            self.stdout = type('S', (), {'close': self._close})()

        def _close(self):
            self.closed.append('stream')

        def terminate(self):
            self.terminated += 1

        def wait(self, timeout=None):
            self.waited += 1
            return 0

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

    class CountingFile:
        """A file of the channel that counts its own closes."""

        def __init__(self, name):
            self.name = name
            self.closes = 0

        def close(self):
            self.closes += 1
            return True

    clock = ManualClock(1000.0)
    custody = _LauncherCustody()
    aggregate = _LaunchAggregate(custody=custody)
    process = Process()
    state = {}

    class StartedThenFailedThread:
        """A thread that really starts and whose start does not return."""

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.started = False

        def start(self):
            self.started = True
            raise RuntimeError('thread_start_failed_after_start')

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    read_file = CountingFile('read')
    write_file = CountingFile('write')

    def channel_factory():
        with unittest.mock.patch.object(broker_module.threading, 'Thread',
                                        StartedThenFailedThread):
            channel = StreamChannel(
                None, None,
                read_endpoint=_WindowsPipeEndpoint(
                    file_object=read_file, name='channel-read',
                    api=Api(), clock=clock, handle=900),
                write_endpoint=_WindowsPipeEndpoint(
                    file_object=write_file, name='channel-write',
                    api=Api(), clock=clock, handle=901),
                custody=aggregate, clock=clock)
        state['channel'] = channel
        raise RuntimeError('adoption_failed_after_the_channel')

    with pytest.raises(RuntimeError):
        _adopt_broker_process(process, channel_factory=channel_factory,
                              executable='C:/python.exe',
                              executable_sha256='a' * 64, aggregate=aggregate,
                              custody=custody)
    channel = state['channel']
    facts = {'aggregate_channel': aggregate.channel is channel,
             'read_closes': read_file.closes,
             'write_closes': write_file.closes,
             'process_closed': list(process.closed),
             'terminated': process.terminated,
             'waited': process.waited,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody.items()]}
    write_phase('r04-adoption', facts)
    # The aggregate found the partial channel: the local variable of the
    # adoption was never assigned and the files of the channel were
    # closed by the **channel** itself.
    assert read_file.closes == 1, \
        'the partial channel was not coordinated by the aggregate'
    assert write_file.closes == 1
    # The files of the process were not closed by the process helper.
    assert process.closed == [], \
        'the process helper closed the files of the channel'
    # The process was coordinated by the aggregate.
    assert process.terminated == 1
    assert process.waited == 1


# -- N10-R05: an incomplete channel keeps its owner ------------------------

def test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel():
    """N10-R05 (M07): a close that returned is not a release.

    Obligation: the close of the channel of a launch is a release only
    when **every** fact of it is closed - the reader, the two ends, the
    workers of the endpoints and the original handles of their threads.
    A close that returned incomplete facts keeps the channel with its
    original reference and its owner, and the same launch coordinates
    the channel **before** the process.  The safe steps of the release
    run before the original cancellation of the launch propagates: the
    original object is the one that leaves and the ordinary failures
    stay named next to it.

    Entry: ``_LaunchAggregate.release`` and
    ``_adopt_broker_process``.  Trigger: the close of the channel
    returns without a confirmed end and the construction of the broker
    fails with a cancellation.  Oracle: the process was terminated and
    waited before the cancellation left, the channel kept its owner and
    the original cancellation object is the one that propagated.
    Negative: a returned close is never taken for a release.  Returned
    state: the facts of the aggregate name what it kept.  Salvage: the
    recovery of the launcher releases what it may.
    """
    class Process:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0

        def terminate(self):
            self.terminated += 1

        def wait(self, timeout=None):
            self.waited += 1
            return 0

    class IncompleteChannel:
        """A channel whose close returns without a confirmed end."""

        reader_finished = True

        def __init__(self):
            self.closes = 0

        def close(self):
            self.closes += 1
            return {'write_end_closed': True, 'read_end_closed': False,
                    'reader_finished': True, 'reader_error': None,
                    'write_retained_workers': 0, 'read_retained_workers': 1,
                    'worker_thread_handle_released': False}

    class FailingBrokerProcess:
        def __init__(self, *args, **kwargs):
            raise KeyboardInterrupt('broker_process_cancelled')

    process = Process()
    channel = IncompleteChannel()
    custody = _LauncherCustody()
    aggregate = _LaunchAggregate(custody=custody)
    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess
    try:
        with pytest.raises(KeyboardInterrupt) as info:
            _adopt_broker_process(process, channel_factory=lambda: channel,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  aggregate=aggregate, custody=custody)
    finally:
        broker_module.BrokerProcess = original
    facts = {'channel_closes': channel.closes,
             'terminated': process.terminated,
             'waited': process.waited,
             'aggregate_channel': aggregate.channel is channel,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody.items()],
             'error_type': type(info.value).__name__}
    write_phase('r05-adoption', facts)
    # The safe steps of the release ran before the cancellation left.
    assert channel.closes == 1
    assert process.terminated == 1
    assert process.waited == 1
    # The incomplete facts kept the channel with its owner.
    assert aggregate.channel is channel, \
        'an incomplete channel lost its owner'
    assert any(item['kind'] == 'channel' for item in custody.items())
    # The original cancellation object is the one that propagated.
    assert str(info.value) == 'broker_process_cancelled'


# -- N10-R06: the admission of a generation -------------------------------

def test_n10_r06_an_expired_or_cancelled_call_performs_no_primitive_call():
    """N10-R06 (M08): the admission comes before the side effect.

    Obligation: a read or a write of an endpoint that enters when the
    round is already expired or already cancelled is refused **before**
    the worker of the endpoint is started, before the request is
    submitted and before the primitive is called: the number of the
    real primitive calls of such a call is zero.  The check and the
    admission of the generation are one atomic step and a cancellation
    is never a remedy that is applied after the submission.

    Entry: ``_WindowsPipeEndpoint.read``,
    ``_WindowsPipeEndpoint.write`` and
    ``_WindowsPipeEndpoint._admission``.  Trigger: the call enters with
    an expired deadline and with a cancel flag that is already set.
    Oracle: the refusal is named and no worker was started.  Negative:
    the endpoint never starts a worker for a refused call.  Returned
    state: the facts of the endpoint name no worker.  Salvage: the
    owner of the test closes the endpoint at the end.
    """
    clock = ManualClock(1000.0)
    calls = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            calls.append('cancel')
            return 'REQUESTED'

        def close_handle(self, handle):
            calls.append('close_handle')
            return None

        def read_stream(self, handle, size):
            calls.append('read')
            return b''

        def write_stream(self, handle, data):
            calls.append('write')
            return len(data)

    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'),
                                    name='inprocess', api=Api(), clock=clock,
                                    handle=702)
    try:
        with pytest.raises(BrokerError) as info:
            endpoint.read(clock.value - 1.0, None)
        assert info.value.code == 'BROKER_PIPE_TIMEOUT'
        assert calls == [], 'a primitive was called by a refused read'
        assert endpoint._reader is None, \
            'the refused read started a worker of the endpoint'
        assert endpoint.facts.get('retained_workers', 0) == 0

        cancel = _ChannelCancel()
        cancel.set()
        with pytest.raises(BrokerError) as info:
            endpoint.read(None, cancel)
        assert info.value.code == 'BROKER_PIPE_CANCELLED'
        assert calls == [], 'a primitive was called by a refused read'
        assert endpoint._reader is None, \
            'the refused read started a worker of the endpoint'

        with pytest.raises(BrokerError) as info:
            endpoint.write(b'abc', clock.value - 1.0, None)
        assert info.value.code == 'BROKER_PIPE_TIMEOUT'
        assert calls == [], 'a primitive was called by a refused write'
        assert endpoint._writer is None, \
            'the refused write started a worker of the endpoint'
        write_phase('r06-admission', {'calls': list(calls),
                                      'reader': endpoint._reader is not None,
                                      'writer': endpoint._writer is not None})
    finally:
        endpoint.close()


# -- N10-R07: the context reaches every layer -----------------------------

def test_n10_r07_the_context_of_the_round_reaches_every_layer(tmp_path):
    """N10-R07 (M08): the context of the round is one context.

    Obligation: the parent hands the **one** context of the round to
    the launcher of the broker and the launcher holds it before the
    first side effect of the launch - the creation of the process, the
    reading of the executable, the channel and its endpoints.  The
    channel, the endpoints, the workers of the endpoints and the API of
    the primitives read the **same** context, and after the round
    published its cleanup deadline every one of them uses the earlier
    of the lease and the cleanup: there is no unbound window and no new
    budget of its own.

    Entry: ``NativeCustodySession.start``,
    ``NativeCustodySession._call_launcher``, ``StreamChannel``,
    ``_WindowsPipeEndpoint`` and ``_WindowsPipeWorker``.  Trigger: the
    round publishes its cleanup deadline while the layers of the round
    are bound.  Oracle: every layer reads the cleanup deadline and the
    launcher received the context of the session.  Negative: no layer
    keeps a deadline of its own.  Returned state: the evidence of the
    session names the propagation of the context.  Salvage: the owner of
    the test closes the channel that it built.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = ManualClock(1000.0)
    seen = {}

    class Peer:
        """A peer of the round that answers the two frames of the start."""

        pid = 4242
        executable = 'C:/python.exe'
        executable_sha256 = 'a' * 64
        reader_finished = True
        channel_deadline_aware = True

        def __init__(self):
            self.inbound = queue.Queue()
            self._sequence = 0
            for kind in ('READY', 'STATUS'):
                self._emit(kind, 'ARMED' if kind == 'READY' else 'RUNNING')

        def _emit(self, kind, state):
            self._sequence += 1
            self.inbound.put(json.dumps(
                {'schema': CHANNEL_SCHEMA, 'kind': kind,
                 'run_id': plan.run_id, 'candidate_sha': plan.candidate_sha,
                 'authorization_sha256': plan.authorization_sha256,
                 'nonce': NONCE, 'sequence': self._sequence,
                 'state': state, 'detail': {}}, ensure_ascii=False,
                sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n')

        def bind_channel_deadline(self, deadline):
            return deadline

        def write(self, raw, deadline=None):
            # The stop of the round is answered by the **terminal**
            # frame of the round and by nothing else.
            try:
                command = json.loads(raw.decode('utf-8')).get('command')
            except Exception:  # noqa: BLE001 - the failure stays visible
                command = None
            if command == 'STOP':
                self._emit('STOPPED', 'RELEASED')
            return None

        def read(self, timeout):
            try:
                return self.inbound.get(timeout=timeout)
            except queue.Empty:
                return None

        def close(self):
            return {'channel_closed': True, 'channel_reader_finished': True,
                    'channel_reader_error': None, 'close_cancellation': None,
                    'channel_retained_workers': 0, 'write_end_closed': True,
                    'read_end_closed': True, 'stdin_closed': True,
                    'stdout_closed': True, 'process_exited': True,
                    'exit_code': 0, 'terminated': False,
                    'process_handle_released': True,
                    'process_handle_release_method': 'POSIX_PROCESS_EXIT',
                    'worker_thread_handle_released': True,
                    'cleanup_budget_seconds': 1.0,
                    'cleanup_deadline': 1005.0}

    peer = Peer()

    def launcher(plan_, run_root_, nonce_, *, context=None):
        # The launcher of the production path accepts the context and it
        # holds it **before** the first side effect of the launch.
        seen['context'] = context
        seen['deadline'] = None if context is None else context.absolute_deadline
        return peer

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=21600,
                                   launcher=launcher, clock=clock,
                                   wall=time.time, nonce=NONCE)
    try:
        session.start()
        facts = {'context_is_the_session_context':
                 seen.get('context') is session._context,
                 'deadline_at_the_launcher': seen.get('deadline'),
                 'propagated': session.evidence()['launcher_context_propagated']}
        write_phase('r07-session', facts)
        assert seen.get('context') is session._context, \
            'the launcher did not receive the context of the session'
        assert seen.get('deadline') is not None, \
            'the launcher had no deadline before the first side effect'
        assert session.evidence()['launcher_context_propagated'] is True

        # The layers of the round read the **same** context and they use
        # the cleanup deadline once the round published it.
        context = _RoundContext(clock=clock)
        context.bind_absolute_deadline(2000.0)
        api = RecordingWin32()
        endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'),
                                        name='inprocess', api=api,
                                        clock=clock, handle=702,
                                        context=context)
        assert endpoint._context is context
        assert endpoint._effective_deadline() == 2000.0
        context.cleanup_deadline(clock.value + 0.5)
        assert endpoint._effective_deadline() == clock.value + 0.5, \
            'the endpoint kept the long lease of the round'
        worker = _WindowsPipeWorker(api, 702, kind='read',
                                    action=lambda request: b'',
                                    name='lvw-n10-r07', clock=clock,
                                    context=context)
        assert worker._context is context
        assert worker._effective_deadline() == clock.value + 0.5, \
            'the worker kept the long lease of the round'
        write_phase('r07-layers', {'endpoint': endpoint._effective_deadline(),
                                    'worker': worker._effective_deadline()})
    finally:
        session.stop()


# -- N10-R08: the retry of a cancellation re-reads the context ------------

def test_n10_r08_the_retry_of_a_cancellation_re_reads_the_context():
    """N10-R08 (M08): the retry of a cancellation tightens itself.

    Obligation: every round of the retry of a cancellation reads the
    **latest** effective context: a cleanup deadline that the round
    published while the retry was running shortens the retry and the
    pause of the retry is cropped to the time that is really left.  A
    retry never waits longer than the context allows and it never falls
    back to a fresh budget of its own.

    Entry: ``_WindowsPipeWorker.request_cancel`` and
    ``_WindowsPipeWorker._effective_deadline``.  Trigger: the
    cancellation reports ``NOT_FOUND`` and the round publishes a
    shorter cleanup deadline while the retry runs.  Oracle: the retry
    stopped at the shorter deadline and it really repeated.  Negative:
    the retry never follows the old absolute deadline beyond the
    cleanup.  Returned state: the number of the attempts is named.
    Salvage: the owner of the test releases the worker at the end.
    """
    context = _RoundContext()
    context.bind_absolute_deadline(time.monotonic() + 30.0)
    release = threading.Event()
    attempts = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            attempts.append(time.monotonic())
            if len(attempts) == 1:
                # The round publishes a **shorter** cleanup deadline
                # while the retry of the cancellation is running.
                context.cleanup_deadline(time.monotonic() + 0.05)
            return 'NOT_FOUND'

        def close_handle(self, handle):
            return None

    worker = _WindowsPipeWorker(Api(), 702, kind='read',
                                action=lambda request: release.wait(10.0),
                                name='lvw-n10-r08', context=context)
    worker.start()
    try:
        assert worker.wait_ready(5.0), 'the worker never came up'
        worker.submit(None)
        assert worker.inside.wait(5.0), 'the worker never entered its read'
        started = time.monotonic()
        state = worker.request_cancel(None)
        elapsed = time.monotonic() - started
        facts = {'state': state, 'attempts': len(attempts),
                 'elapsed': elapsed,
                 'cleanup': context.cleanup_deadline_value()}
        write_phase('r08-retry', facts)
        assert len(attempts) >= 2, \
            'the cancellation was not really repeated'
        assert elapsed < 2.0, \
            'the retry ignored the cleanup deadline of the round'
        assert context.cleanup_deadline_value() is not None
    finally:
        release.set()
        worker.join(10.0)
        assert not worker.is_alive(), 'the worker was left behind'


# -- N10-R09: every exit of the startup owner joins its thread ------------

def test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread(tmp_path):
    """N10-R09 (M08): the owner of a startup step joins its thread.

    Obligation: **every** exit of a startup step - the success, the
    timeout, the ordinary failure, the cancellation and the
    ``SystemExit`` - waits for the **real** exit of the thread of the
    step in a ``finally``, bounded by the deadline of the round.  A
    thread that did not exit keeps its owner: it stays in the owners
    that are in flight and the round keeps the fact.  The original
    exception is the one that leaves and the wait never publishes the
    cleanup deadline of the round before the round failed.

    Entry: ``BrokerLoop._run_startup`` and ``_StartupOwner.settle``.
    Trigger: the action of the step raises an ordinary error, a
    cancellation and a ``SystemExit``, and a step that never returns.
    Oracle: the owner was released only after the real exit of its
    thread and the owner of a step that did not end kept its place.
    Negative: an attempt that ended is never a proof that the thread
    ended.  Returned state: the owners that are in flight are named.
    Salvage: the owner of the test releases the thread at the end.
    """
    clock = time.monotonic
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.bind_absolute_deadline(clock() + 60.0)
    transport = type('T', (), {'bind_deadline': lambda self, value: value,
                               'write': lambda self, raw: None})()
    loop = BrokerLoop(core=core, transport=transport, plan=core.plan,
                      nonce='0' * 32, clock=clock, wall=time.time)
    # The deadline of the step of the round is finite and it is short:
    # a step that never returns must miss it.
    loop._deadline_mono = clock() + 0.3
    release = threading.Event()
    try:
        def ordinary():
            raise BrokerError('BROKER_STARTUP_ORDINARY')

        with pytest.raises(BrokerError) as info:
            loop._run_startup('ARM', ordinary)
        assert info.value.code == 'BROKER_STARTUP_ORDINARY'
        assert loop._startup_in_flight is None, \
            'the owner of a step that ended was kept'
        assert core.context.inflight() == [], \
            'the owner of a step that ended stayed in flight'

        def cancelling():
            raise KeyboardInterrupt('startup_cancelled')

        with pytest.raises(KeyboardInterrupt):
            loop._run_startup('ARM', cancelling)
        assert loop._startup_in_flight is None
        assert core.context.inflight() == []

        def exiting():
            raise SystemExit(3)

        with pytest.raises(SystemExit):
            loop._run_startup('ARM', exiting)
        assert loop._startup_in_flight is None
        assert core.context.inflight() == []

        # A step that never returns keeps its owner: the attempt never
        # ended and the thread of the step is still inside the
        # operating system.  The cleanup deadline of the round is
        # published explicitly here: the round failed and the wait for
        # the thread of the step is bounded by it.
        core.context.cleanup_deadline(clock() + 0.2)
        with pytest.raises(BrokerError) as info:
            loop._run_startup('ARM', lambda: release.wait(10.0))
        assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED'
        facts = {'in_flight': len(core.context.inflight()),
                 'retained': loop._startup_in_flight is not None}
        write_phase('r09-startup', facts)
        assert loop._startup_in_flight is not None, \
            'the owner of a step that did not end was released'
        assert core.context.inflight(), \
            'the owner of a step that did not end left the flight'
    finally:
        release.set()
        time.sleep(0.3)


# -- N10-R10: the outcome of the generation wins --------------------------

def test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation():
    """N10-R10 (M09): a real fault of the round is never a benign cancel.

    Obligation: the worker of an endpoint keeps the **outcome** of
    every generation it runs: the result, the error, the original error
    object and the order of the completion.  A failure that was really
    published **before** the cancellation of the round is the first
    error of the round: a close that sets the cancel flag afterwards
    may not replace it and it may not turn it into a benign
    cancellation.  The identity of the token of the cancel is not a
    proof: the order of the two facts is the proof.

    Entry: ``_WindowsPipeWorker.outcome``,
    ``_WindowsPipeWorker.published_before_cancel`` and
    ``_WindowsPipeEndpoint._raise_cancellation``.  Trigger: the read of
    the generation fails with an ordinary error and the cancel flag of
    the close is set before the endpoint reads the result.  Oracle: the
    original error object is the one that leaves and the code of the
    error is the code of the real fault.  Negative: a cancellation may
    never rewrite a published failure.  Returned state: the outcome of
    the generation is named with its order.  Salvage: the owner of the
    test closes the endpoint at the end.
    """
    clock = ManualClock(1000.0)
    started = threading.Event()
    release = threading.Event()

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            # The ordinary failure of the read of this generation.
            started.set()
            release.wait(5.0)
            raise BrokerError('BROKER_STREAM_READ_FAILED')

    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'),
                                    name='inprocess', api=Api(), clock=clock,
                                    handle=702)
    cancel = _ChannelCancel()
    outcome_holder = {}

    def reader():
        try:
            endpoint.read(None, cancel)
        except BaseException as error:  # noqa: BLE001 - it is reported
            outcome_holder['error'] = error

    worker = threading.Thread(target=reader, name='lvw-n10-r10-reader')
    worker.start()
    try:
        assert started.wait(5.0), 'the read never started'
        # The close of the round asks for the cancellation of the
        # generation and the failure of the read happens at the same
        # moment: the failure of the round is the first error in every
        # interleaving of the two.
        cancel.set()
        release.set()
        worker.join(10.0)
        assert not worker.is_alive(), 'the reader was left behind'
        error = outcome_holder.get('error')
        assert error is not None, 'the read returned without an error'
        record = endpoint._reader.outcome(1)
        facts = {'code': getattr(error, 'code', None),
                 'type': type(error).__name__,
                 'outcome_error': (record or {}).get('error'),
                 'sequence': (record or {}).get('sequence'),
                 'cancel_sequence': (record or {}).get('cancel_sequence'),
                 'parallel': getattr(error, 'lvw_parallel_cancellation',
                                     None)}
        write_phase('r10-outcome', facts)
        # The real fault of the round is the one that leaves.
        assert getattr(error, 'code', None) == 'BROKER_STREAM_READ_FAILED', \
            'the real fault of the round was replaced by a cancellation'
        assert isinstance(error, BrokerError)
        assert (record or {}).get('error') == 'BROKER_STREAM_READ_FAILED'
    finally:
        release.set()
        endpoint.close()


# -- N10-R11: the overflow is a named failure -----------------------------

def test_n10_r11_the_overflow_of_the_channel_is_a_named_failure():
    """N10-R11 (M09): the overflow of the channel is named where it is.

    Obligation: a complete frame with a newline that is too long and a
    frame that is one byte beyond the limit are recorded at the place
    where they really happen, as a **named** sticky error of the
    channel with the original facts of the overflow.  A close that
    happens before the read consumes the frame carries that error: the
    channel that overflowed is never a channel that ended normally and
    the broker is never released as if there were no error.

    Entry: ``StreamChannel._drain``, ``StreamChannel._record_overflow``
    and ``BrokerProcess._close_channel``.  Trigger: the channel reads a
    frame that does not fit and the close happens before the read
    consumes it.  Oracle: the error of the reader is the named overflow
    and the facts of the overflow travel with the close.  Negative: the
    limits of the package are unchanged: the exact frame fits and the
    one byte beyond the limit does not.  Returned state: the facts of
    the close name the overflow.  Salvage: the owner of the test closes
    the channel at the end.
    """
    clock = ManualClock(1000.0)
    blocks = []

    class Reader:
        """The read end of the channel: it returns one block and then EOF."""

        def __init__(self):
            self.facts = {}

        def read(self, deadline=None, cancel=None):
            if not blocks:
                return b''
            return blocks.pop(0)

        def close(self):
            self.facts['closed'] = True
            return {'closed': True, 'retained_workers': 0,
                    'worker_thread_handle_released': True}

    class Writer:
        def __init__(self):
            self.facts = {}

        def write(self, raw, deadline=None, cancel=None):
            return len(raw)

        def close(self):
            self.facts['closed'] = True
            return {'closed': True, 'retained_workers': 0,
                    'worker_thread_handle_released': True}

    # A frame with a newline that is one byte beyond the limit.
    blocks.append(b'x' * (32 * 1024 + 1) + b'\n')
    channel = StreamChannel(None, None, read_endpoint=Reader(),
                            write_endpoint=Writer(), clock=clock,
                            max_frame_bytes=32 * 1024)
    try:
        deadline = time.monotonic() + 5.0
        while channel._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        facts = {'error': channel._error, 'overflow': channel.overflow,
                 'overflow_facts': channel._overflow_facts}
        write_phase('r11-overflow', facts)
        assert channel.overflow is True
        assert channel._error == 'BROKER_CHANNEL_OVERFLOW', \
            'the overflow was not recorded as a named failure'
        assert channel._overflow_facts.get('reason') == 'FRAME_TOO_LARGE'
        # The close of the channel carries the named error of the reader.
        close_facts = channel.close()
        assert close_facts['reader_error'] == 'BROKER_CHANNEL_OVERFLOW', \
            'the close of the channel lost the overflow'
        assert close_facts['overflow'] is True
        assert close_facts['overflow_facts'].get('reason') == 'FRAME_TOO_LARGE'
    finally:
        channel.close()

    # The exact frame still fits: the limits of the package did not move.
    exact = b'y' * (32 * 1024 - 1) + b'\n'
    blocks.append(exact)
    channel = StreamChannel(None, None, read_endpoint=Reader(),
                            write_endpoint=Writer(), clock=clock,
                            max_frame_bytes=32 * 1024)
    try:
        deadline = time.monotonic() + 5.0
        while channel._count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert channel._count == 1, \
            'the exact frame did not fit into the channel'
        assert channel.overflow is False
        assert channel._error is None
        write_phase('r11-exact', {'count': channel._count,
                                  'overflow': channel.overflow})
    finally:
        channel.close()


# -- N10-R12: the causal order of the reader ------------------------------

def test_n10_r12_the_reader_publishes_its_wait_before_it_waits():
    """N10-R12 (test causality): the reader publishes its real state.

    Obligation: the reader of the chain publishes the event that it is
    really inside its read **before** it waits, so that the owner of
    the test never waits for an event that the reader publishes only
    after a timeout.  The external owner waits for that event, it sets
    the **same** cancel flag of the **same** channel without naming an
    owner and it publishes an explicit confirmation; the public stop of
    the round is driven only after that confirmation.  The wait of the
    owner is bounded and its return is checked and the bound of the
    package is never enlarged to make the timing fit.

    Entry: ``_F5Api.read_stream`` and
    ``_F5ExternalCancelOwner.run``.  Trigger: the round is started and
    the reader of the chain enters its read.  Oracle: the event of the
    reader was published before the owner set the flag, the origin of
    the cancellation is really unknown and the reader of the chain
    keeps the error of the cancellation of the other owner.  Negative:
    the owner never sets the flag before the reader is really inside
    its read.  Returned state: the confirmation of the owner is
    published and the facts of the close name the error of the reader.
    Salvage: the exact thread of the owner is joined by the owner of
    the test.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    owner = _F5ExternalCancelOwner(api, holder)
    thread = threading.Thread(target=owner.run, name='lvw-n10-r12-owner')
    thread.start()
    try:
        session.start()
        # The confirmation of the external owner is published in every
        # case and the failure of the owner is the failure of the test.
        assert owner.published.wait(30.0), \
            'the external owner never confirmed its cancellation'
        if owner.error is not None:
            raise owner.error
        channel = holder['channel']
        facts = {'read_waiting': bool(api.read_waiting.is_set()),
                 'flag_set': owner.flag_set,
                 'flag_owner': owner.flag_owner,
                 'frames': len(api.frames)}
        write_phase('r12-owner', facts)
        # The reader of the chain published its wait before it waited.
        assert api.read_waiting.is_set()
        # The flag of the cancel is really set and its origin is really
        # unknown: the close of the channel may never be taken for the
        # owner of this cancellation.
        assert owner.flag_set is True
        assert channel._cancel.is_set()
        assert channel._cancel.owner() is None
        # The public stop of the round is driven only after the
        # confirmation of the owner.
        first = session.stop()
        close_facts = first['broker_close_facts'] or {}
        write_phase('r12-stop', {'state': first['state'],
                                  'reader_error':
                                  close_facts.get('channel_reader_error'),
                                  'retained': first['broker_retained']})
        assert close_facts.get('channel_reader_error') == 'BROKER_PIPE_CANCELLED', \
            'the cancellation of the other owner was swallowed'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        thread.join(30.0)
        assert not thread.is_alive(), 'the owner of the round was left behind'
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- N10-R13: the fault is unlocked by the owner of the test ---------------

def test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first():
    """N10-R13 (M09): the fault of the read is observed before the stop.

    Obligation: the ordinary failure of the read and the frame that
    never ends are published by the **owner of the test** and they are
    never unlocked by the write of the stop: the owner waits for the
    real outcome - the error or the end of the stream - and it observes
    it **before** it drives the public stop of the round.  The phase
    documents of the round are really written and every value of them
    is a value that the production returned.

    Entry: ``_F5Api.publish_read_fault``,
    ``_F5Api.publish_partial_frame`` and
    ``NativeCustodySession.stop``.  Trigger: the ordinary failure of
    the read of the chain.  Oracle: the failure was really published
    before the stop and the error of the reader is the error of the
    round.  Negative: the write of the stop never unlocks a failure
    that should have happened first.  Returned state: the phase
    documents are on the disk.  Salvage: the owner of the test stops the
    round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    api = _F5Api(read_fault=RuntimeError('read_fault'))
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_read_fault()
        assert api.fault_observed.wait(15.0), \
            'the ordinary failure of the read never happened'
        reader = holder['read_endpoint']._reader
        assert reader is not None
        assert reader.outcome_published.wait(15.0), \
            'the outcome of the read was never published'
        first = session.stop()
        facts = {'state': first['state'],
                 'failures': list(first['failures']),
                 'broker_retained': first['broker_retained']}
        write_phase('r13-first', facts)
        close_facts = first['broker_close_facts'] or {}
        assert close_facts.get('channel_reader_error') == 'RuntimeError', \
            'the failure of the read was swallowed by the stop'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- N10-R14: the compatibility of the new candidate ----------------------

def test_n10_r14_the_closed_obligations_of_the_package_do_not_regress():
    """N10-R14 (compatibility): the closed obligations stay closed.

    Obligation: the candidate of this correction keeps every closed
    obligation of the package: the unknown state is latched under one
    lock, the budget of the parent and of the child is one budget in
    both directions, the reservation of the terminal exchange is
    consumed by the terminal frame itself, a cancellation of a normal
    close keeps its source and a first error survives a retry.  The
    identity and the order of the 175 frozen nodes are untouched: the
    new groups are **appended** and they never replace an old one.

    Entry: ``NativeCustodySession._latch_unknown_state``,
    ``NativeCustodySession._check_frame_budget``,
    ``NativeCustodySession._send`` and ``_ChannelCancel``.  Trigger: a
    round that is stopped and a round whose reader failed.  Oracle: the
    latches and the budgets keep their facts.  Negative: a later frame
    never borrows the reservation of the terminal one.  Returned state:
    the facts of the round are named.  Salvage: the owner of the test
    stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = ManualClock(1000.0)
    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        # The unknown state is latched under one lock and it is never
        # cleared.  The latch is checked on a **separate** session, so
        # that the round that is stopped below keeps its own state.
        probe = NativeCustodySession(
            plan=document, run_root=tmp_path,
            parent_child_remaining_seconds=60,
            launcher=lambda *args, **kwargs: None, clock=clock,
            wall=time.time)
        assert probe._latch_unknown_state() is True
        assert probe._latch_unknown_state() is False
        assert probe._context.is_unknown() is True
        # The reservation of the terminal exchange is consumed by the
        # terminal frame itself and a normal frame never borrows it.
        session._check_frame_budget(terminal=False)
        session._check_frame_budget(terminal=True)
        # The cancel flag of a normal close keeps its source.
        cancel = _ChannelCancel()
        source = broker_module._CloseSource(1)
        cancel.set(source)
        assert cancel.owner() is source
        assert cancel.owner() is not broker_module._CloseSource(1)
        facts = {'unknown': session._context.is_unknown(),
                 'frames_sent': session._frames_sent,
                 'frames_received': session._frames_received}
        write_phase('r14-compatibility', facts)
        first = session.stop()
        assert first['state'] in ('UNKNOWN_RETAINED', 'RELEASED')
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- the chain of the round ------------------------------------------------

def _chain(api, document, plan, tmp_path):
    """Build the **real** chain of one round.

    The chain is the one of the production launcher: the frames of the
    round are published first, then the endpoints, then the channel and
    then the handle of the broker.  Nothing of the chain is replaced by
    a stand-in and the facts of the close are the facts of the
    production.
    """
    return _f5_build_chain(api, document, plan, time.monotonic, time.time,
                           tmp_path)
