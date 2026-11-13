"""The frozen regressions of the N1 correction 07 of the native custody.

This module carries the **18 frozen oracle groups** of the root package
``reports/v0-s3/product-gate0/native-custody-correction-07`` (the file
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
  ``_LauncherCustody`` and the production ``NativeCustodySession``.  A
  façade that only returns the right story would not prove anything and
  it is not used for the failure paths.

* Every case records the state of the resources **at the moment the
  product returned**, before any salvage of the test owner.  The
  cleanup of the test owner is explicit and it is never used to
  declare that the product returned cleanly: a product that could not
  release a resource stays unknown and keeps its original reference.

* The native claims of this package stay ``NOT_PROVEN``.  The module
  proves the behaviour of the Python owners and it never claims that a
  Windows API, a job object, a GPU, a port or a service was executed.

The boundary of the process is not installed here: the guard of the
batch lives in the report directory of the batch and the runner of the
batch is its only authorised entry.
"""
import ast
import json
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
    WindowsApi, _LauncherCustody, _RoundContext, _StartupOwner,
    _WindowsPipeEndpoint, _WindowsPipeWorker, _adopt_broker_process,
    _launcher_custody_items, release_retained_launches)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, NativeCustodySession, validate_launch_plan)
from tools.test_v0_s3_native_custody_correction05 import (  # noqa: E402
    COMPLETE_CLOSE_FACTS)
from tools.test_v0_s3_native_custody_regressions import (  # noqa: E402
    ManualClock, RecordingWin32, SyntheticKernel32, make_session, plan_document,
    sealed_plan, synthetic_table)


# -- the helpers of the groups ---------------------------------------------

def _live_plan_document():
    """A plan document whose lease is valid for the clock of the host."""
    return plan_document(lease_expires_at=time.time() + 3600.0)


def _reply_bytes(kind, state, detail, plan, nonce, sequence):
    """One frame of the closed protocol of the private channel."""
    return json.dumps(
        {'schema': CHANNEL_SCHEMA, 'kind': kind, 'run_id': plan.run_id,
         'candidate_sha': plan.candidate_sha,
         'authorization_sha256': plan.authorization_sha256,
         'nonce': nonce, 'sequence': sequence, 'state': state,
         'detail': detail},
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n'


class _FakeFile:
    """A file of the private channel that only records its close."""

    def __init__(self, name='file'):
        self.name = name
        self.closes = 0

    def close(self):
        self.closes += 1
        return True


class _CancellingEvent:
    """An event whose wait is cancelled."""

    def __init__(self):
        self._set = False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout=None):
        raise KeyboardInterrupt('reader_wait_cancelled')


# -- N07-R01: the control handle of an unconfirmed process is kept ---------

def test_n07_r01_the_control_handle_of_an_unconfirmed_process_is_kept():
    """N07-R01 (M03): the last control handle of a process is kept.

    Obligation: an original process whose exit was not confirmed keeps
    its control handle and the recovery entry of the API owner; the
    thread handle is handled on its own and the primary error and the
    secondary errors coexist.  Entry:
    ``WindowsApi.create_process_suspended``.  Trigger: the birth query
    fails, the termination of the process fails, the wait of the release
    times out and the close of the handle would succeed.  Oracle: the
    control handle of the process is still with its owner, the thread
    handle was closed, the primary error is the birth query and the
    secondary errors are named.  Negative: a close that succeeds is
    never a proof that the process ended.  Returned state: the retained
    handles of the façade name the process and only the process.
    Salvage: the recovery of the owner is explicit and it keeps the
    handle as long as the exit is not confirmed.
    """
    def fail_birth(kernel32, *args):
        return 0

    def refuse_terminate(kernel32, *args):
        return 0

    def timeout_wait(kernel32, *args):
        return 258  # WAIT_TIMEOUT

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': fail_birth,
                                         'TerminateProcess': refuse_terminate,
                                         'WaitForSingleObject': timeout_wait})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    # The primary error of the creation is the error that leaves and the
    # secondary errors of the release are named next to it.
    assert info.value.code == 'BROKER_PROCESS_BIRTH_QUERY_FAILED'
    detail = info.value.detail or ''
    assert 'TerminateProcess' in detail
    assert 'WaitForSingleObject:exit_not_confirmed' in detail
    assert 'process_control_handle_retained:exit_not_confirmed' in detail
    # The control handle of the process is with its owner: the process
    # may still be alive and the handle is the only thing that may stop
    # it.  The thread handle is independent of the exit and it was
    # closed on its own.
    retained = api.retained_handles()
    assert [entry['kind'] for entry in retained] == ['process']
    assert retained[0]['owner'] == 'WINDOWS_API'
    assert getattr(retained[0]['handle'], 'value', retained[0]['handle']) \
        == kernel32.process_handle
    assert kernel32.process_handle in kernel32.live
    assert kernel32.thread_handle not in kernel32.live
    # The recovery of the owner never closes the control handle of a
    # process whose exit was not confirmed.
    report = api.release_retained()
    assert [item['kind'] for item in report] == ['process']
    assert report[0]['released'] is False
    assert kernel32.process_handle in kernel32.live
    assert api.retained_handles(), 'the control handle was forgotten'


# -- N07-R02: the recovery keeps the handle until the exit is confirmed ---

def test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed():
    """N07-R02 (M03): the second recovery releases the confirmed handle.

    Obligation: the first coordination of a process whose exit was not
    confirmed keeps its control handle; a later coordination that
    confirms the exit closes it and forgets it; the recovery never opens
    a new budget and a cancellation is uploaded after every safe step.
    Entry: ``WindowsApi.release_retained`` and
    ``WindowsApi.create_process_suspended``.  Trigger: the wait of the
    release times out and the process really ends later.  Oracle: the
    first report names the handle as unreleased, the second report names
    it as released and the table of the façade is empty.  Negative: the
    deadline of the recovery is published once and it is never renewed.
    Returned state: the report of the recovery names the failures of
    every step.  Salvage: the salvage is the second coordination of the
    owner and it is explicit.
    """
    state = {'exited': False}

    def fail_birth(kernel32, *args):
        return 0

    def timeout_wait(kernel32, *args):
        return 0 if state['exited'] else 258

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': fail_birth,
                                         'WaitForSingleObject': timeout_wait})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError):
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    assert [entry['kind'] for entry in api.retained_handles()] == ['process']
    # The first coordination keeps the control handle: the exit was not
    # confirmed and the process may still be alive.
    report = api.release_retained()
    assert [item['kind'] for item in report] == ['process']
    assert report[0]['released'] is False
    assert 'WaitForSingleObject:exit_not_confirmed' in report[0]['failures']
    assert kernel32.process_handle in kernel32.live
    # The process really ends later, inside the original deadline.
    state['exited'] = True
    report = api.release_retained()
    assert [item['kind'] for item in report] == ['process']
    assert report[0]['released'] is True
    assert api.retained_handles() == []
    assert kernel32.process_handle not in kernel32.live

    # The cancellation of the recovery is uploaded after every safe step
    # and it never hides the primary error of the creation.
    def cancel_terminate(kernel32, *args):
        raise KeyboardInterrupt('terminate_cancelled')

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': fail_birth,
                                         'TerminateProcess': cancel_terminate,
                                         'WaitForSingleObject': timeout_wait})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    assert info.value.code == 'BROKER_PROCESS_BIRTH_QUERY_FAILED'
    assert isinstance(info.value.lvw_cancelled, KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        api.release_retained()
    assert api.retained_handles(), 'the control handle was forgotten'


# -- N07-R03: a pipe that was handed over has exactly one owner -----------

def test_n07_r03_a_pipe_that_was_handed_over_has_exactly_one_owner(tmp_path):
    """N07-R03 (M05): the handover of a pipe has one owner.

    Obligation: the ends of a pipe that were created are handed over to
    the core and to its readers in one provable step; the API owner
    never closes an end that it handed over and the tables of the two
    owners agree.  Entry: ``WindowsApi.create_pipe``,
    ``WindowsApi.handover`` and ``BrokerCore._launch_role``.  Trigger: a
    successful creation of the two pipes of a role.  Oracle: the façade
    does not name the ends any more, the core names them with their
    reader as the owner and the recovery of the façade is empty.
    Negative: the recovery of the façade never closes an end that a live
    reader reads from.  Returned state: the table of the façade is
    empty and the table of the core names the ends.  Salvage: the core
    releases its own ends.
    """
    def create_pipe(kernel32, *args):
        read = kernel32.allocate('pipe_read')
        write = kernel32.allocate('pipe_write')
        args[0]._obj.value = read
        args[1]._obj.value = write
        return 1

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe})
    api = WindowsApi(table=synthetic_table(kernel32))
    core = BrokerCore(win32=api, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        core.launch()
        # The façade does not name the ends of the pipes any more: the
        # core and its readers are their only owner.
        kinds = sorted(entry['kind'] for entry in api.retained_handles())
        assert kinds == [], 'the facade still names a handed over handle'
        assert api.handovers(), 'the handover was not recorded'
        # The table of the core names the read ends with their reader as
        # the owner and the owner is an object and not a name.
        readers = [item for item in core._pending.pending()
                   if item['owner'] == 'READER']
        assert readers, 'the readers do not own their read end'
        for item in readers:
            assert item['owner_ref'] is not None
        # The recovery of the façade never closes an end that the core
        # owns: it has nothing to release.
        report = api.release_retained()
        assert report == []
        assert api.retained_handles() == []
    finally:
        core.stop('STOP')


# -- N07-R04: the ends of a pipe are cleaned up independently -------------

def test_n07_r04_the_ends_of_a_pipe_are_cleaned_up_independently():
    """N07-R04 (M05): the cleanup of the ends of a pipe is independent.

    Obligation: the two ends of a pipe are closed on their own when the
    inherit flag could not be cleared; a cancellation of the inherit
    flag and a cancellation of the close of one end never skip the close
    of the other end; the end that could not be closed keeps its owner
    and the cancellation propagates with the primary error next to it.
    Entry: ``WindowsApi.create_pipe``.  Trigger: the inherit flag of the
    read end raises a cancellation and the close of the read end raises
    a cancellation.  Oracle: the safe close of both ends ran, the
    cancellation is the error that leaves and the primary error stays
    reachable.  Negative: a cancellation never becomes a string and it
    never hides the error that caused the pipe.  Returned state: the
    table of the façade names the end that is still open.  Salvage: the
    recovery of the owner closes the end that is still open.
    """
    def create_pipe(kernel32, *args):
        read = kernel32.allocate('pipe_read')
        write = kernel32.allocate('pipe_write')
        kernel32.pipe_read_handle = read
        kernel32.pipe_write_handle = write
        args[0]._obj.value = read
        args[1]._obj.value = write
        return 1

    def cancel_inherit(kernel32, *args):
        raise KeyboardInterrupt('inherit_cancelled')

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe,
                                         'SetHandleInformation': cancel_inherit})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(KeyboardInterrupt) as info:
        api.create_pipe('stdout')
    # The cancellation is the error that leaves and it is not a string.
    assert isinstance(info.value, KeyboardInterrupt)
    # The safe close of both ends ran before the cancellation left.
    assert 'CloseHandle' in kernel32.names()
    assert not kernel32.live
    assert api.retained_handles() == []

    def refuse_inherit(kernel32, *args):
        return 0

    def cancel_read_close(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle == kernel32.pipe_read_handle:
            raise KeyboardInterrupt('read_close_cancelled')
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe,
                                         'SetHandleInformation': refuse_inherit,
                                         'CloseHandle': cancel_read_close})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(KeyboardInterrupt) as info:
        api.create_pipe('stdout')
    # The write end was closed even though the close of the read end was
    # cancelled.
    assert kernel32.pipe_write_handle not in kernel32.live
    # The end that could not be closed keeps its original reference with
    # the façade.
    retained = api.retained_handles()
    assert [entry['kind'] for entry in retained] == ['pipe_read']
    assert retained[0]['owner'] == 'WINDOWS_API'
    # The primary error and the cancellation coexist: the cancellation is
    # not a BrokerError and the primary error stays reachable.
    assert isinstance(info.value, KeyboardInterrupt)
    assert isinstance(info.value.lvw_primary, BrokerError)
    assert info.value.lvw_primary.code == 'BROKER_PIPE_INHERIT_FAILED'


# -- N07-R05: the read end of a live reader is never closed ---------------

def test_n07_r05_the_read_end_of_a_live_reader_is_never_closed(tmp_path):
    """N07-R05 (M06): the read end of a live reader is protected.

    Obligation: the read end of every reader is protected by its owner
    in every branch of the coordination - a cancellation of the wait, a
    cancellation of the join and an ordinary failure of the
    coordination; the readers that follow are still coordinated and the
    pending pass refuses to close an end whose owner is still using it.
    Entry: ``BrokerCore._close_readers``, ``BrokerCore._close_one_reader``
    and ``BrokerCore._close_pending``.  Trigger: the wait of a live
    reader is cancelled and the coordination of another reader fails.
    Oracle: the read ends of the live readers are not closed, the other
    reader was cleaned up and the pending pass names the end that it
    refused to close.  Negative: the pending pass never closes an end
    under a live owner.  Returned state: the states of the readers and
    the failures of the core name every reader.  Salvage: the owner of
    the live reader releases it later.
    """
    class LiveReader:
        """A reader that is alive and whose wait is cancelled."""

        def __init__(self, handle, name):
            self.handle = handle
            self.name = name
            self.error = None
            self.ident = 1
            self.finished = _CancellingEvent()

        def is_alive(self):
            return True

        def join(self, timeout=None):
            raise KeyboardInterrupt('reader_join_cancelled')

        def stop(self):
            return None

    class DeadReader:
        """A reader that really stopped."""

        def __init__(self, handle, name):
            self.handle = handle
            self.name = name
            self.error = None
            self.ident = 1
            self.finished = threading.Event()
            self.finished.set()

        def is_alive(self):
            return False

        def join(self, timeout=None):
            return None

        def stop(self):
            return None

    class UnansweringReader:
        """A reader that cannot say whether it is alive."""

        def __init__(self, handle, name):
            self.handle = handle
            self.name = name
            self.error = None
            self.ident = 1
            self.finished = threading.Event()

        def is_alive(self):
            raise RuntimeError('alive_unknown')

        def join(self, timeout=None):
            raise RuntimeError('alive_unknown')

        def stop(self):
            return None

    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    # The three read ends are handles of the round: the façade of the
    # primitives owns them until they are closed.
    for handle in (0x51, 0x52, 0x53):
        win32.live[handle] = 'pipe_read'
    dead = DeadReader(0x52, 'dead-reader')
    live = LiveReader(0x51, 'live-reader')
    blind = UnansweringReader(0x53, 'blind-reader')
    for reader, handle in ((dead, 0x52), (live, 0x51), (blind, 0x53)):
        core.readers.append(reader)
        core._pending.add(handle, 'pipe_read', role='COMFY')
        core._pending.transfer(handle, 'READER', owner_ref=reader)
    with pytest.raises(KeyboardInterrupt):
        core._close_readers()
    # The read end of the live reader was not closed and the reader that
    # really stopped was cleaned up.
    assert 0x51 not in win32.closed
    assert 0x51 in win32.live
    assert 0x52 in win32.closed
    names = [state['name'] for state in core.reader_states]
    assert 'dead-reader' in names
    assert 'live-reader' in names
    # The pending pass refuses to close the end whose owner cannot say
    # that it stopped: the guard is the fact of the owner.
    core._close_pending()
    assert 0x53 not in win32.closed
    assert 0x53 in win32.live
    assert any(item.get('code') == 'BROKER_PENDING_HANDLE_IN_USE'
               for item in core.failures)


# -- N07-R06: the cancellation of a wait reaches the top ------------------

def test_n07_r06_the_cancellation_of_a_wait_reaches_the_top(tmp_path):
    """N07-R06 (M06): a cancellation of a wait is never swallowed.

    Obligation: a cancellation of the wait of a process and a
    cancellation of the reading of its exit code are propagated to the
    caller of the stop; the processes that follow are still coordinated.
    Entry: ``BrokerCore.stop``, ``BrokerCore._wait_the_processes`` and
    ``BrokerCore._wait_one_process``.  Trigger: the wait of the first
    process raises a cancellation and the exit code of the second raises
    a cancellation.  Oracle: the cancellation is the error that leaves
    the stop and it is named as a cancellation.  Negative: the
    cancellation never becomes an ordinary evidence of the round.
    Returned state: the failures of the core name the cancellation and
    the later processes were waited for.  Salvage: the handles of the
    round are released by their owner.
    """
    class CancellingWaitWin32(RecordingWin32):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.cancelled = False

        def wait_process(self, process, timeout_ms):
            self.calls.append(('wait_process', process, timeout_ms))
            if not self.cancelled:
                self.cancelled = True
                raise KeyboardInterrupt('wait_cancelled')
            for entry in self.created:
                if entry['handle'] == process:
                    return entry['exited']
            return True

    win32 = CancellingWaitWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    with pytest.raises(KeyboardInterrupt):
        core.stop('STOP')
    cancellations = [item for item in core.failures if item.get('cancellation')]
    assert cancellations, 'the cancellation was not named'
    assert any(item['stage'] == 'wait' for item in cancellations)
    # The processes that follow the cancelled one were still waited for.
    waited = [call for call in win32.calls if call[0] == 'wait_process']
    assert len(waited) >= 2, 'the wait of the next process never ran'

    class CancellingExitWin32(RecordingWin32):
        def exit_code(self, process):
            self.calls.append(('exit_code', process))
            raise SystemExit('exit_cancelled')

    win32 = CancellingExitWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    with pytest.raises(SystemExit):
        core.stop('STOP')
    cancellations = [item for item in core.failures if item.get('cancellation')]
    assert cancellations, 'the cancellation of the exit code was not named'
    assert any(item['stage'] == 'exit_code' for item in cancellations)


# -- N07-R07: the recovery of a record synchronises the tables ------------

def test_n07_r07_the_recovery_of_a_record_synchronises_the_tables(tmp_path):
    """N07-R07 (M06): the recovery of a handle updates every table.

    Obligation: the close of a handle that could not be closed keeps its
    owner and its name; the recovery that closes it really updates the
    pending table, the record of the round and the retained resources of
    the round.  Entry: ``BrokerCore.stop`` and ``BrokerCore._close_handle``.
    Trigger: the close of the job handle of the round fails twice.
    Oracle: the second stop closes the handle, the record and the
    retained resources of the round agree with the fact of the close and
    the handle was closed exactly once.  Negative: a handle that was
    really closed is never named as a resource any more and it is never
    closed twice.  Returned state: the tables of the core are empty.
    Salvage: the handles that are still open are released by the owner
    of the façade.
    """
    class SlowWin32(RecordingWin32):
        """A façade whose close of the job handle fails twice."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.attempts = {}

        def close_handle(self, handle):
            self.calls.append(('close_handle', handle))
            if handle == getattr(self, 'job_handle', None):
                count = self.attempts.get(handle, 0)
                if count < 2:
                    self.attempts[handle] = count + 1
                    raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            super().close_handle(handle)

    win32 = SlowWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    job = core.job
    win32.job_handle = job
    try:
        core.stop('STOP')
        # The handle that could not be closed keeps its owner and it is
        # named: it is never replaced by a copy of an error message.
        assert core.job is job
        assert job in win32.live
        retained = [item for item in core._retained_resources
                    if item['handle'] is job]
        assert retained, 'the handle that could not be closed was not named'
        assert retained[0]['owner'] == 'CORE_RETAINED'
        pending = [item for item in core._pending.pending()
                   if item['handle'] == job]
        assert pending, 'the handle that could not be closed lost its owner'
        # The second stop coordinates the handle again and every table of
        # the core agrees with the fact of the close.
        core.stop('STOP')
        assert core.job is None
        assert core.job_closed is True
        assert core._pending.pending() == []
        assert core._retained_resources == []
        assert job not in win32.live
        for record in core.records:
            assert record['process_handle'] is None
            assert record['thread_handle'] is None
            assert record['process_handle_closed'] is True
            assert record['thread_handle_closed'] is True
        # The handle was closed exactly once.
        assert len(win32.closed) == len(set(win32.closed)), \
            'a handle was closed twice'
    finally:
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N07-R08: the endpoint owns its worker before the start ---------------

def test_n07_r08_the_endpoint_owns_its_worker_before_the_start():
    """N07-R08 (M07): the endpoint owns the worker from its creation.

    Obligation: a worker of an endpoint is owned by the endpoint before
    its thread starts; a start that did not return keeps its owner and
    the close of the endpoint never closes the file under a worker that
    is starting or that is inside its operation.  Entry:
    ``_WindowsPipeEndpoint._start`` and ``_WindowsPipeEndpoint.close``.
    Trigger: the start of the worker raises before the thread exists and
    a start that raises after the thread really started.  Oracle: the
    endpoint names the worker in both cases and the file is closed only
    after the worker really stopped.  Negative: the handle of the
    thread of the worker is closed before the file.  Returned state: the
    facts of the endpoint name the retained worker.  Salvage: the owner
    of the worker stops it later.
    """
    order = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            order.append('thread')

    clock = ManualClock(1000.0)
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'), name='inprocess',
                                    api=Api(), clock=clock, handle=702)
    endpoint._file.close = lambda: order.append('file')

    class NeverStartedWorker(broker_module._WindowsPipeWorker):
        def start(self):
            raise RuntimeError('worker_start_failed')

    original = broker_module._WindowsPipeWorker
    broker_module._WindowsPipeWorker = NeverStartedWorker
    try:
        with pytest.raises(RuntimeError):
            endpoint.read(None, None)
        # The endpoint is the owner of the worker from the moment of its
        # creation: the start that did not return never lost it.
        assert endpoint._reader is not None
        assert endpoint._reader in endpoint._retained
        assert endpoint.facts['retained_workers'] == 1
        # The close of the endpoint never closes the file under a worker
        # that never came up.
        facts = endpoint.close()
        assert facts['closed'] is False
        assert 'file' not in order
    finally:
        broker_module._WindowsPipeWorker = original

    order = []
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'), name='inprocess',
                                    api=Api(), clock=clock, handle=702)
    endpoint._file.close = lambda: order.append('file')

    class StartedThenFailedWorker(broker_module._WindowsPipeWorker):
        def start(self):
            super().start()
            raise RuntimeError('worker_start_failed_after_start')

    original = broker_module._WindowsPipeWorker
    broker_module._WindowsPipeWorker = StartedThenFailedWorker
    try:
        with pytest.raises(RuntimeError):
            endpoint.read(None, None)
        assert endpoint._reader is not None
        assert endpoint.facts['retained_workers'] == 1
        # The close of the endpoint sees the worker that is alive: the
        # handle of its thread is closed before the file.
        facts = endpoint.close()
        assert facts['closed'] is True
        assert order == ['thread', 'file'], \
            'the file was closed before the worker really stopped'
    finally:
        broker_module._WindowsPipeWorker = original


# -- N07-R09: the launcher keeps the owner of the process and the channel --

def test_n07_r09_the_launcher_keeps_the_owner_of_the_process_and_the_channel():
    """N07-R09 (M07): the launcher owns the process and the channel.

    Obligation: the original process of the round is registered with the
    launcher from the moment of its creation; a channel that exists and
    that could not be handed over is closed by the launcher through the
    channel and never by closing the standard input and the standard
    output of the process by itself; a resource that could not be
    released keeps its original reference.  Entry:
    ``_adopt_broker_process``, ``_LauncherCustody`` and
    ``release_retained_launches``.  Trigger: the construction of the
    handle of the broker fails and the termination of the process fails.
    Oracle: the channel was closed, the files of the process were not
    closed by the launcher and the process keeps its owner.  Negative: a
    pid is never used to find a process again and the table of the
    launcher never names the same resource twice.  Returned state: the
    table of the launcher names the process.  Salvage: the recovery of
    the launcher is explicit and it names what it kept.
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
            raise RuntimeError('terminate_failed')

        def wait(self, timeout=None):
            self.waited += 1
            raise RuntimeError('wait_failed')

    class Channel:
        reader_finished = True

        def __init__(self):
            self.closes = 0

        def bind_deadline(self, deadline):
            self.deadline = deadline

        def close(self):
            self.closes += 1
            return {'write_end_closed': True, 'read_end_closed': True,
                    'reader_finished': True, 'reader_error': None,
                    'write_retained_workers': 0, 'read_retained_workers': 0,
                    'worker_thread_handle_released': True}

    process = Process()
    channel = Channel()

    class FailingBrokerProcess:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess
    try:
        with pytest.raises(RuntimeError):
            _adopt_broker_process(process, channel_factory=lambda: channel,
                                  executable='C:/python.exe', executable_sha256='a' * 64)
    finally:
        broker_module.BrokerProcess = original
    # The channel is the owner of the files: the launcher closed it and it
    # never closed the standard input and the standard output itself.
    assert channel.closes == 1
    assert process.closed == [], 'the launcher closed the files of the channel'
    assert process.terminated == 1
    assert process.waited == 1
    # The process that could not be released keeps its original reference
    # with the launcher.
    kept = [item for item in _launcher_custody_items() if item['kind'] == 'process']
    assert kept, 'the process lost its owner'
    assert any(item['resource'] is process for item in kept)

    # The table of the launcher never names the same resource twice and
    # the handover removes the resource from it.
    custody = _LauncherCustody()
    custody.retain('process', process, 'first')
    custody.retain('process', process, 'second')
    assert len(custody.items()) == 1
    custody.forget(process)
    assert custody.items() == []
    # The recovery of the launcher names the resources that it kept.
    custody.retain('process', process, 'kept')
    report = custody.release()
    assert report['retained'] == ['process']
    # The public recovery entry of the launcher of the package is the
    # same finite entry and it never loses the original reference.
    public = release_retained_launches()
    assert 'process' in public['retained']


# -- N07-R10: a closer whose start did not return is unknown --------------

def test_n07_r10_a_closer_whose_start_did_not_return_is_unknown(tmp_path):
    """N07-R10 (M07): a start that did not return is unknown.

    Obligation: a closer whose start did not return is **unknown** and
    not a thread that ended; the original owner of the closer is kept and
    the round stays unknown; a later attempt may try again.  Entry:
    ``NativeCustodySession._start_bounded_close`` and
    ``NativeCustodySession._await_closer_exit``.  Trigger: the start of
    the closer raises before the thread exists.  Oracle: the failure is
    named, the state of the start is ``STARTING`` and the wait for the
    closer reports that the state is unknown.  Negative: a join that
    raises because the thread was never started is never read as the end
    of the closer.  Returned state: the evidence names the unknown
    closer.  Salvage: a later attempt of the close is still possible.
    """
    session, _holder, _clock = make_session(tmp_path)
    session.start()

    class NeverStartedThread:
        def __init__(self, *args, **kwargs):
            self.ident = None
            self.daemon = True

        def start(self):
            raise RuntimeError('closer_start_failed')

        def is_alive(self):
            return False

        def join(self, timeout=None):
            raise RuntimeError('cannot join thread before it is started')

    with unittest.mock.patch('tools.v0_s3_native_custody.threading.Thread',
                              NeverStartedThread):
        assert session._start_bounded_close() is False
    evidence = session.evidence()
    assert any('CUSTODY_CLOSER_START_FAILED' in failure
               for failure in evidence['failures'])
    assert evidence['closer_start_state'] == 'STARTING'
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    # The original owner of the closer is kept: the reference was never
    # dropped and the closer is never taken for a thread that ended.
    assert session._closer is not None
    assert session._closer in session._closer_threads
    # The wait for the closer reports that the state is unknown and it
    # never claims that the closer ended.
    assert session._await_close() is False
    assert 'CUSTODY_CLOSER_START_UNKNOWN' in session.evidence()['failures']
    assert session.evidence()['state'] == 'UNKNOWN_RETAINED'
    # The latch of the closer is not permanent: a later attempt may try
    # again and the public stop of the round is the recovery entry.
    assert session._closer_started is False
    session.stop()
    assert session.evidence()['state'] == 'UNKNOWN_RETAINED'


# -- N07-R11: the cancellation and the operation are one atomic step ------

def test_n07_r11_the_cancellation_of_a_worker_is_repeated_and_bounded():
    """N07-R11 (M08): the cancellation of a worker is really repeated.

    Obligation: the cancellation of the operation of a worker is
    repeated while the operation is in flight and it is never released
    by the stop event that the cancellation set itself; the completion of
    an older generation is never the completion of this one; a request
    that waits for the worker is never performed after the cancellation.
    Entry: ``_WindowsPipeWorker.request_cancel``,
    ``_WindowsPipeWorker.submit`` and ``_WindowsPipeWorker.run``.
    Trigger: the cancellation of the operating system reports that the
    operation was not found.  Oracle: the request was really repeated
    and the queued request was never performed.  Negative: the retry
    never waits on the stop event of the worker and it never uses the
    done of an older generation.  Returned state: the state of the
    worker names the cancellation.  Salvage: the owner of the worker
    releases it.
    """
    entered = []
    release = threading.Event()

    class Api:
        def __init__(self):
            self.cancels = []

        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            self.cancels.append(handle)
            return 'NOT_FOUND'

        def close_handle(self, handle):
            return None

    api = Api()

    def action(request):
        entered.append(request)
        release.wait(5.0)
        return b''

    worker = _WindowsPipeWorker(api, 702, kind='read', action=action,
                                name='n07-r11-worker')
    worker.start()
    try:
        worker.wait_ready(2.0)
        generation = worker.submit(b'first')
        for _ in range(200):
            if entered:
                break
            time.sleep(0.01)
        assert entered == [b'first']
        # The second request waits for the worker while the first
        # operation is in flight.
        worker.submit(b'second')
        # The cancellation is requested while the first operation runs.
        state = worker.request_cancel(time.monotonic() + 0.3)
        assert state == 'NOT_FOUND'
        # The request was really repeated: the cancellation was not sent
        # once and dropped.
        assert len(api.cancels) >= 2, 'the cancellation was sent once only'
        # The completion of an older generation is never the completion of
        # this one.
        assert worker.wait_done(generation + 1, 0.05) is False
        # The first operation ends and the queued request is never
        # performed: the cancellation and the intent to enter the
        # operation are one atomic step.
        release.set()
        for _ in range(200):
            if worker.wait_done(generation + 1, 0.02):
                break
            time.sleep(0.01)
        assert entered == [b'first'], 'a request was performed after the cancel'
    finally:
        release.set()
        worker.stop_accepting()
        worker.join_bounded(5.0)
        assert not worker.is_alive()

    # The check of the cancellation and the publication of the intent to
    # enter the operation are **one** critical section of the worker.
    # The interleaving between them is therefore impossible and not
    # improbable: the lock of the worker is what forbids it.
    source = (PACK_ROOT / 'tools/v0_s3_native_broker.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    run = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == '_WindowsPipeWorker':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == 'run':
                    run = item
    assert run is not None, 'the worker of the endpoint is gone'
    critical = None
    for node in ast.walk(run):
        if isinstance(node, ast.With):
            for entry in node.items:
                expression = entry.context_expr
                if (isinstance(expression, ast.Attribute)
                        and expression.attr == '_condition'):
                    critical = node
    assert critical is not None, 'the worker does not take its lock any more'
    section = ast.unparse(critical)
    assert 'self._cancelled' in section
    assert "self.state = 'IN_IO'" in section
    assert 'self.inside.set()' in section


# -- N07-R12: every segment of a partial write reads the latest deadline --

def test_n07_r12_every_segment_of_a_partial_write_reads_the_latest_deadline():
    """N07-R12 (M08): the deadline of a partial write is never a copy.

    Obligation: every segment of a partial write reads the latest
    effective deadline of the round; a deadline that was shortened
    while the write was running ends the write and no further segment
    is written.  Entry: ``_WindowsPipeEndpoint._write_block`` and
    ``_WindowsPipeEndpoint._current_write_deadline``.  Trigger: the
    deadline of the round is shortened after the first segment.  Oracle:
    the write ends with a timeout and only the first segment was
    written.  Negative: the copy of the deadline of the first segment
    never lets a further segment through.  Returned state: the write
    fails with a named error.  Salvage: the owner of the endpoint
    closes it.
    """
    writes = []
    clock = ManualClock(1000.0)
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('write'), name='inprocess',
                                    api=None, clock=clock, handle=702)

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def write_stream(self, handle, data):
            writes.append(bytes(data))
            if len(writes) == 1:
                # The deadline of the round is shortened while the write
                # is running and the clock passes it.
                endpoint.bind_deadline(clock.value + 0.5)
                clock.value += 10.0
            return 1

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

    endpoint._api = Api()
    try:
        with pytest.raises(BrokerError) as info:
            endpoint.write(b'abcdef', clock.value + 100.0)
        assert info.value.code == 'BROKER_PIPE_TIMEOUT'
        assert len(writes) == 1, 'a segment was written after the deadline'
    finally:
        endpoint.close()


# -- N07-R13: every side effect checks the shared context -----------------

def test_n07_r13_every_side_effect_checks_the_shared_context(tmp_path):
    """N07-R13 (M08): the budget of the round is one budget.

    Obligation: every side effect of the startup checks the shared
    context before it happens and after it happened; a request that is
    already expired is refused before it is submitted and a pipe that
    would be created after the deadline is never created; the endpoint
    reads the absolute deadline of the round from the context; the
    recovery of the launcher uses the remaining budget and never a fixed
    number of seconds.  Entry: ``BrokerCore.arm``,
    ``BrokerCore._launch_role``, ``_WindowsPipeEndpoint._effective_deadline``
    and ``_terminate_and_close_process``.  Trigger: the deadline of the
    round arrives before the arm and before the launch.  Oracle: nothing
    was created and the endpoint reads the deadline of the context.
    Negative: an expired deadline never starts a new wait.  Returned
    state: the refusal is named.  Salvage: the resources of the round
    are released by their owner.
    """
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.arm()
    core.bind_absolute_deadline(1000.0)
    with pytest.raises(BrokerError) as info:
        core.launch()
    assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED'
    assert 'create_pipe' not in win32.names()
    assert 'create_process_suspended' not in win32.names()

    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.bind_absolute_deadline(999.0)
    with pytest.raises(BrokerError) as info:
        core.arm()
    assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED'
    assert 'create_job' not in win32.names()

    # The endpoint reads the absolute deadline of the round from the
    # context of the round and it never keeps a deadline of its own.
    clock = ManualClock(1000.0)
    context = _RoundContext(clock=clock)
    context.bind_absolute_deadline(1000.0)
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'), name='inprocess',
                                    api=None, clock=clock, handle=702, context=context)
    assert endpoint._effective_deadline(None) == 1000.0
    assert endpoint._effective_deadline(2000.0) == 1000.0

    # The recovery of the launcher uses the remaining budget of the round
    # and never a fixed number of seconds.
    class WaitingProcess:
        pid = 1
        returncode = None

        def __init__(self):
            self.timeouts = []
            self.terminated = 0

        def terminate(self):
            self.terminated += 1

        def wait(self, timeout=None):
            self.timeouts.append(timeout)
            return 0

    process = WaitingProcess()
    custody = _LauncherCustody()
    custody.retain('process', process, 'test')
    report = custody.release(deadline=time.monotonic() + 1.5)
    assert report['released'] == ['process']
    assert 0 < process.timeouts[0] <= 1.5, \
        'the recovery opened a budget of its own'


# -- N07-R14: the startup owner releases its owner after the real exit -----

def test_n07_r14_the_startup_owner_releases_its_owner_after_the_real_exit(tmp_path):
    """N07-R14 (M08): the attempt of a step is not the exit of its thread.

    Obligation: the end of the attempt of a startup step and the end of
    the thread that performs it are two different facts; the owner of the
    step is released only after a bounded join of the real thread; a
    thread that did not exit keeps its owner and the round never gets a
    new budget.  Entry: ``_StartupOwner.settle`` and
    ``BrokerLoop._run_startup``.  Trigger: the action of the step ends
    and the thread of the step needs one more tick to leave.  Oracle: the
    settle reports that the thread did not exit and the owner of the step
    is not released.  Negative: the event of the attempt never releases
    the owner.  Returned state: the round names the step that is still
    in flight.  Salvage: the thread of the step ends and it may be
    released.
    """
    class SlowThreadOwner(_StartupOwner):
        """A startup owner whose thread needs one more tick to leave."""

        gate = threading.Event()

        def _run(self, action):
            super()._run(action)
            self.gate.wait(5.0)

    SlowThreadOwner.gate = threading.Event()
    owner = SlowThreadOwner(name='arm', clock=time.monotonic,
                             deadline=time.monotonic() + 10.0)
    owner.start(lambda: 'done')
    try:
        assert owner.await_result() == 'done'
        # The attempt of the step ended but the thread of the step is
        # still inside it.
        assert owner._finished.is_set()
        assert owner.settle(0.2) is False, \
            'the event of the attempt was read as the exit of the thread'
        assert owner.in_flight is True
        SlowThreadOwner.gate.set()
        assert owner.settle(5.0) is True
        assert owner.in_flight is False
    finally:
        SlowThreadOwner.gate.set()

    # The loop releases the owner of a step only after the real exit of
    # its thread and it never publishes the cleanup deadline of the round
    # for a step that did not fail.
    core = BrokerCore(win32=RecordingWin32(), plan=sealed_plan(),
                      run_root=tmp_path)
    loop = BrokerLoop(core=core, transport=object(), plan=sealed_plan(),
                      nonce='a' * 32)
    loop._deadline_mono = time.monotonic() + 30.0
    SlowThreadOwner.gate = threading.Event()
    original = broker_module._StartupOwner
    broker_module._StartupOwner = SlowThreadOwner
    try:
        loop._run_startup('ARM', lambda: None)
        assert loop._startup_in_flight is not None, \
            'the owner of the step was released before the real exit'
        assert any(item.get('code') == 'BROKER_STARTUP_IN_FLIGHT_RETAINED'
                   for item in core.failures)
        assert loop.context.inflight(), 'the owner of the step was released'
        assert core.context.cleanup_deadline_value() is None, \
            'the startup published the cleanup deadline of the round'
    finally:
        broker_module._StartupOwner = original
        SlowThreadOwner.gate.set()
        for pending in loop.context.inflight():
            pending.settle(5.0)


# -- N07-R15: the real chain is coordinated again by the same owner -------

def test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner(tmp_path):
    """N07-R15 (M09): the real chain of the round is coordinated again.

    Obligation: a call that returned is not a release: the real chain
    ``Session`` -> ``BrokerProcess`` -> ``StreamChannel`` -> ``Windows
    endpoint`` -> worker is coordinated again by the same owner when the
    first attempt did not confirm every item of it; the confirmed items
    are never closed twice.  Entry: ``NativeCustodySession.stop``,
    ``BrokerProcess.close`` and ``StreamChannel.close``.  Trigger: the
    original handle of the thread of a worker of an endpoint cannot be
    closed by the first attempt.  Oracle: the channel was closed twice,
    the handle of the thread was closed by the second attempt and the
    broker was released.  Negative: the high level never skips an
    unfinished item of the low level because a close returned.  Returned
    state: the evidence of the round names the incomplete facts of the
    first attempt.  Salvage: the second public stop of the round is the
    recovery entry.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = time.monotonic
    wall = time.time

    class Api:
        def __init__(self):
            self.lock = threading.Lock()
            self.frames = []
            self.final = b''
            self.wake = threading.Event()
            self.closed = []
            self.close_failures = 2
            self.next_handle = 700

        def duplicate_current_thread_handle(self):
            self.next_handle += 1
            return self.next_handle

        def cancel_synchronous_io(self, handle):
            self.wake.set()
            return 'REQUESTED'

        def close_handle(self, handle):
            if self.close_failures > 0:
                self.close_failures -= 1
                raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            self.closed.append(handle)

        def read_stream(self, handle, size):
            with self.lock:
                if self.frames:
                    return self.frames.pop(0)
            self.wake.wait(10.0)
            with self.lock:
                if self.final:
                    frame = self.final
                    self.final = b''
                    return frame
            return b''

        def write_stream(self, handle, data):
            self.wake.set()
            return len(data)

    api = Api()

    class Process:
        pid = 4242
        returncode = 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            return None

    read_endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'), name='channel-read',
                                          api=api, clock=clock, handle=900)
    write_endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('write'), name='channel-write',
                                           api=api, clock=clock, handle=901)
    channel = StreamChannel(None, None, read_endpoint=read_endpoint,
                             write_endpoint=write_endpoint, clock=clock)
    channel_closes = []
    original_close = channel.close

    def counting_close():
        channel_closes.append(1)
        return original_close()

    channel.close = counting_close
    broker = BrokerProcess(Process(), 'C:/python.exe', 'a' * 64, channel)

    def launcher(plan_document_, run_root, nonce):
        api.final = _reply_bytes('STOPPED', 'RELEASED', {}, plan, nonce, 3)
        api.frames = [_reply_bytes('READY', 'ARMED', {}, plan, nonce, 1),
                      _reply_bytes('STATUS', 'RUNNING', {}, plan, nonce, 2)]
        return broker

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=21600,
                                   launcher=launcher, clock=clock, wall=wall)
    try:
        session.start()
        assert session.broker is broker
        first = session.stop()
        # The first attempt did not confirm every item of the chain: the
        # original handle of the thread of the worker of the endpoint
        # could not be closed.
        assert session.broker is broker, 'the broker was released without a proof'
        assert first['broker_retained'] is True
        incomplete = [failure for failure in first['failures']
                      if failure.startswith('CUSTODY_BROKER_CLOSE_INCOMPLETE')]
        assert incomplete, 'the incomplete facts were not named'
        assert len(channel_closes) == 1
        # The second public stop coordinates the items that the first
        # attempt did not confirm.
        second = session.stop()
        assert len(channel_closes) == 2, \
            'the high level skipped the unfinished item of the low level'
        assert session.broker is None
        assert second['broker_retained'] is False
        assert api.closed, 'the handle of the thread of the worker was never closed'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- N07-R16: the endpoint recomputes the state of its workers ------------

def test_n07_r16_the_endpoint_recomputes_the_state_of_its_workers():
    """N07-R16 (M09): the state of the workers of an endpoint is real.

    Obligation: the endpoint recomputes the live and the retained state
    of its workers on every close; a worker that really ended and whose
    handle of its thread was released is not retained any more; a worker
    whose handle could not be closed is retained and it may be released
    by a later close; a closed file never locks the recovery of the
    handle of a thread.  Entry: ``_WindowsPipeEndpoint.close`` and
    ``_WindowsPipeWorker.release_thread_handle``.  Trigger: the close of
    the handle of the thread of the worker fails twice.  Oracle: the
    first close keeps the worker, the second close releases it and the
    facts are recomputed and not copied.  Negative: the retained list
    never names the same worker twice.  Returned state: the facts of the
    endpoint name the state of the workers.  Salvage: the second close
    of the owner releases the handle.
    """
    closed = []
    failures = {'left': 2}

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def write_stream(self, handle, data):
            return len(data)

        def close_handle(self, handle):
            if failures['left'] > 0:
                failures['left'] -= 1
                raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            closed.append(handle)

    clock = ManualClock(1000.0)
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('write'), name='inprocess',
                                    api=Api(), clock=clock, handle=702)
    endpoint.write(b'x', clock.value + 5.0)
    assert endpoint._writer is not None
    first = endpoint.close()
    # The handle of the thread of the worker could not be closed: the
    # worker is retained and the file is closed all the same.
    assert first['closed'] is True
    assert first['retained_workers'] == 1
    assert first['worker_thread_handle_released'] is False
    assert len(endpoint._retained) == 1
    # The second close recomputes the state of the workers: the handle of
    # the thread of the worker is released now and the worker is not
    # retained any more.
    second = endpoint.close()
    assert second['retained_workers'] == 0
    assert second['worker_thread_handle_released'] is True
    assert endpoint._retained == []
    assert closed == [701]


# -- N07-R17: the second generation of the close has its own event --------

def test_n07_r17_the_second_generation_of_the_close_has_its_own_event(tmp_path):
    """N07-R17 (M09): every attempt of the close owns its own event.

    Obligation: the attempt of the close that is running now owns its
    own event and its own generation; the end of an older attempt never
    releases a waiter of the attempt that is running now; the waiter
    never holds the lock while it waits and the deadline of the cleanup
    is never reset.  Entry: ``NativeCustodySession._recover_close`` and
    ``NativeCustodySession._await_close``.  Trigger: the first attempt
    did not confirm the release and the recovery of the second
    generation is in flight when a competitor arrives.  Oracle: the
    competitor waits for the second generation and it is released by the
    end of that generation.  Negative: the old event never releases the
    waiter of the new generation.  Returned state: the generation of the
    close is named in the evidence.  Salvage: the release of the second
    attempt ends the wait.
    """
    session, holder, clock = make_session(
        tmp_path, close_facts=dict(COMPLETE_CLOSE_FACTS,
                                   process_handle_released=False))
    session.start()
    peer = holder['peer']
    deadline = session._cleanup_deadline_for()
    session.stop()
    assert session.broker is peer
    # The condition of the round recovered and the recovery of the second
    # generation is in flight.
    entered = threading.Event()
    release = threading.Event()

    def blocking_close():
        entered.set()
        release.wait(5.0)
        return dict(COMPLETE_CLOSE_FACTS)

    peer.close = blocking_close
    recovery = threading.Thread(target=session.stop)
    recovery.start()
    try:
        assert entered.wait(5.0), 'the recovery never reached the close'
        outcome = {}

        def competitor():
            outcome['result'] = session._await_close()

        waiter = threading.Thread(target=competitor)
        waiter.start()
        waiter.join(0.3)
        assert waiter.is_alive(), \
            'the end of the older attempt released the waiter of the new one'
        release.set()
        waiter.join(5.0)
        assert not waiter.is_alive()
        assert outcome.get('result') is True
    finally:
        release.set()
        recovery.join(5.0)
    # The second generation published its own event and the deadline of
    # the cleanup was never reset.
    assert session._close_generation == 1
    assert session._cleanup_deadline_for() == deadline
    assert session.broker is None


# -- N07-R18: the first public stop waits for the real closer -------------

def test_n07_r18_the_first_public_stop_waits_for_the_real_closer(tmp_path):
    """N07-R18 (M09): the public stop coordinates the real closer.

    Obligation: every exit of the public stop of the round - the normal
    one, the cancelled one and the ordinary failure - coordinates the
    current owner of the close and the **real** closer; the end of the
    attempt of the close is never the end of the thread that performs
    it; a closer that is still alive when the deadline arrives keeps its
    owner and the round stays unknown.  Entry:
    ``NativeCustodySession.stop`` and
    ``NativeCustodySession._await_closer_exit``.  Trigger: the closer
    published the end of its attempt and it is still alive when the
    first public stop arrives.  Oracle: the public stop waits for the
    real exit of the closer.  Negative: only a helper or a repeated
    stop never proves the coordination of the closer.  Returned state:
    the evidence of the round names both facts.  Salvage: the closer
    ends and the round is closed.
    """
    session, _holder, _clock = make_session(tmp_path, clock=time.monotonic,
                                            wall=time.time)
    session.start()
    entered = threading.Event()
    release = threading.Event()
    original_finish = session._finish_close

    def slow_finish():
        original_finish()
        entered.set()
        release.wait(5.0)

    session._finish_close = slow_finish
    try:
        assert session._start_bounded_close() is True
        assert entered.wait(5.0), 'the closer never ended its attempt'
        evidence = session.evidence()
        assert evidence['close_state'] == 'FINISHED'
        assert evidence['closer_alive'] is True
        assert evidence['closer_exited'] is False
        outcome = {}

        def stopper():
            outcome['evidence'] = session.stop()

        def release_later():
            time.sleep(0.5)
            release.set()

        threading.Thread(target=release_later, daemon=True).start()
        thread = threading.Thread(target=stopper)
        thread.start()
        thread.join(0.2)
        assert thread.is_alive(), \
            'the public stop returned before the real closer ended'
        thread.join(10.0)
        assert not thread.is_alive()
        final = outcome.get('evidence')
        assert final is not None
        assert final['closer_alive'] is False
        assert final['closer_exited'] is True
    finally:
        release.set()
        closer = session._closer
        if closer is not None:
            closer.join(5.0)
