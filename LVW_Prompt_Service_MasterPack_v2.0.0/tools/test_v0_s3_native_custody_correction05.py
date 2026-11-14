"""The frozen regressions of the N1 correction 05 of the native custody.

This module carries the **24 frozen oracle groups** of the root package
``reports/v0-s3/product-gate0/native-custody-correction-05`` (the file
``regression-obligations.json``).  The obligations are frozen by the
root and they are not written by the implementer: every group below is
mapped to the production owner that has to carry it and to the test
that drives it.

Every group is written in the same closed form.  The group names

* the **obligation** and the major that it belongs to,
* the **production entry** that has to carry it,
* the **trigger** that the check drives,
* the **oracle** that the product has to satisfy,
* the **negative** case and the exact boundary,
* the **state that the product returned with**, before any salvage of
  the test owner,
* the **salvage** of the test owner, which is explicit, bounded and
  which never changes the fact of the product.

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
  ``BrokerCore``, the production ``BrokerLoop``, the production
  ``BrokerProcess``, the production ``StreamChannel``, the production
  ``_WindowsPipeWorker`` and ``_WindowsPipeEndpoint`` and the
  production ``NativeCustodySession``.  A façade that only returns the
  right story would not prove anything and it is not used for the
  failure paths.

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
import os
import sys
import threading
import time
import unittest.mock
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_native_broker import (  # noqa: E402 - the path is set above
    BrokerCore, BrokerError, BrokerLoop, BrokerProcess, StreamChannel,
    WindowsApi, _WindowsPipeEndpoint, _WindowsPipeWorker,
    _adopt_broker_process, _launcher_custody_items, release_retained_launches,
    role_command)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, CustodyError, MAX_FRAMES, NativeCustodySession,
    RESERVED_TERMINAL_FRAMES, _ChannelPump, validate_launch_plan)
from tools.test_v0_s3_native_custody_regressions import (  # noqa: E402
    ManualClock, RecordingWin32, SyntheticKernel32, make_session,
    m07a_interrupted_launch, plan_document, sealed_plan, synthetic_table)

#: The facts of a close that proves a release.  Every fact is derived
#: from the stand-in that produced it and it is never added by default.
COMPLETE_CLOSE_FACTS = {'channel_closed': True,
                        'process_exited': True,
                        'process_handle_released': True,
                        'channel_reader_finished': True,
                        'read_end_closed': True,
                        'write_end_closed': True,
                        'worker_thread_handle_released': True,
                        'channel_reader_error': None,
                        'channel_retained_workers': 0}


class SteppingClock:
    """A clock that moves by a fixed step on every read.

    A clock that only moves when the check moves it cannot tell an
    atomic publication from a lucky one: two threads that read the
    same value would see the same result with and without a lock.  A
    clock that moves on every read makes the difference visible: the
    value that was published is the value that everybody sees.
    """

    def __init__(self, value=1000.0, step=0.5):
        self.value = float(value)
        self.step = float(step)

    def __call__(self):
        current = self.value
        self.value += self.step
        return current

    def advance(self, seconds):
        self.value += float(seconds)


class _RecordingEvent:
    """An event that records the waits and moves the clock."""

    def __init__(self, clock, waits):
        self._clock = clock
        self._waits = waits
        self._set = False

    def is_set(self):
        return self._set

    def set(self):
        self._set = True

    def wait(self, timeout=None):
        self._waits.append(timeout)
        # The wait consumes the budget of the round: the clock moves.
        self._clock.advance(timeout or 0.0)
        return self._set


class RecordingReader:
    """A stand-in of the reader of a child stream.

    The stand-in records the wait of the reader and the join of the
    reader, and it moves the clock of the round while it waits.  It is
    the **production** ``BrokerCore._close_readers`` that coordinates it.
    """

    def __init__(self, clock, handle, name='lvw-native-custody-stream-fake'):
        self.handle = handle
        self.name = name
        self.error = None
        self.ident = 1
        self.waits = []
        self.joins = []
        self._clock = clock
        self._alive = True
        self.finished = _RecordingEvent(clock, self.waits)

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        self.joins.append(timeout)
        self._alive = False

    def stop(self):
        self._alive = False


# -- N05-R01: the null device is owned from the moment of its creation ----

def test_n05_r01_the_null_device_has_an_owner_from_the_moment_of_its_creation():
    """N05-R01 (M03): the null device keeps its original owner.

    Obligation: the null device of the child has to be owned from the
    moment of its creation.  Entry: ``WindowsApi.create_process_suspended``.
    Trigger: the close of the null device fails.  Oracle: the original
    handle of the null device stays with its owner, the failure keeps
    it recoverable and the other safe cleanups still run.  Negative: a
    null device that was closed with a confirmed close leaves the table.
    Returned state: the failed creation names the null device and the
    table of the façade still holds the original handle.  Salvage: the
    recovery of the owner is explicit and it closes the handle.
    """
    null_handle = 901

    def fail_null_close(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle == null_handle:
            # The close of the null device fails the first time only:
            # a later recovery of the owner may close it.
            attempts = kernel32.__dict__.setdefault('null_close_attempts', {})
            attempts[handle] = attempts.get(handle, 0) + 1
            if attempts[handle] == 1:
                return 0
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'CloseHandle': fail_null_close})
    kernel32.null_handle = null_handle
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    # The failure of the close of the null device is the failure of the
    # creation: it is named and it is not only a message.
    assert info.value.code == 'BROKER_NULL_DEVICE_CLOSE_FAILED'
    assert 'CloseHandle' in (info.value.detail or '')
    # The null device is with its owner and with its **original**
    # reference: the table of the façade is the recovery entry point.
    retained = api.retained_handles()
    kinds = sorted(entry['kind'] for entry in retained)
    assert kinds == ['null_device']
    entry = retained[0]
    assert entry['handle'] == null_handle
    assert entry['owner'] == 'WINDOWS_API'
    # The other safe cleanups of the creation still ran.
    assert 'TerminateProcess' in kernel32.names()
    assert 'WaitForSingleObject' in kernel32.names()
    # The recovery of the owner is explicit and it closes the handle.
    report = api.release_retained()
    assert [item['kind'] for item in report] == ['null_device']
    assert api.retained_handles() == []
    assert null_handle not in kernel32.live


# -- N05-R02: a cancellation never skips the other finalizers ------------

def test_n05_r02_a_cancellation_in_the_cleanup_never_skips_the_other_finalizers():
    """N05-R02 (M03): the finalizers of a creation are independent.

    Obligation: every safe finalizer of a creation runs on its own, the
    primary and the secondary error coexist and the cancellation
    propagates after the cleanup.  Entry:
    ``WindowsApi.create_process_suspended``.  Trigger:
    ``DeleteProcThreadAttributeList`` raises a cancellation.  Oracle:
    the null device was closed, the created process was released and
    the cancellation is named.  Negative: the cancellation never
    replaces the primary error of the creation.  Returned state: the
    cancellation is the error that leaves the method.  Salvage: the
    retained handles of the façade are released by their owner.
    """
    def cancel_delete(kernel32, *args):
        raise KeyboardInterrupt('delete_cancelled')

    kernel32 = SyntheticKernel32(script={'DeleteProcThreadAttributeList': cancel_delete})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(KeyboardInterrupt):
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    # The safe steps of the cleanup ran: the deletion of the attribute
    # list never skipped the close of the null device.
    assert 'CloseHandle' in kernel32.names()
    assert kernel32.null_handle not in kernel32.live
    # The release of the created process ran as well.
    assert 'TerminateProcess' in kernel32.names()
    assert 'WaitForSingleObject' in kernel32.names()
    assert kernel32.process_handle not in kernel32.live
    assert kernel32.thread_handle not in kernel32.live
    # Nothing is left without an owner.
    assert api.retained_handles() == []

    # The primary error of the creation is never replaced by the
    # cancellation of a later finalizer.
    def fail_birth(kernel32, *args):
        return 0

    def cancel_terminate(kernel32, *args):
        raise SystemExit('terminate_cancelled')

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': fail_birth,
                                         'TerminateProcess': cancel_terminate})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    assert info.value.code == 'BROKER_PROCESS_BIRTH_QUERY_FAILED'
    detail = info.value.detail or ''
    assert 'TerminateProcess:CANCELLED' in detail
    # The close of the handles of the process still ran: the
    # cancellation never skipped it.
    assert 'CloseHandle' in kernel32.names()
    assert kernel32.process_handle not in kernel32.live
    assert kernel32.thread_handle not in kernel32.live


# -- N05-R03: the ends of a pipe are owned from their creation ------------

def test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation():
    """N05-R03 (M05): both ends of a pipe have an owner.

    Obligation: the ends of a pipe are registered from the moment of
    their creation, the end whose close failed stays recoverable and the
    end that was closed is closed exactly once.  Entry:
    ``WindowsApi.create_pipe``.  Trigger: the inherit flag of the read
    end could not be cleared.  Oracle: the core never received the
    pair and the round never loses the ownership of the two ends.
    Negative: an end that was closed with a confirmed close leaves the
    table.  Returned state: the refusal names the failure of the
    inherit flag.  Salvage: the recovery of the owner closes the end
    that is still open.
    """
    def create_pipe(kernel32, *args):
        read = kernel32.allocate('pipe_read')
        write = kernel32.allocate('pipe_write')
        kernel32.pipe_read_handle = read
        args[0]._obj.value = read
        args[1]._obj.value = write
        return 1

    def refuse_inherit(kernel32, *args):
        return 0

    def fail_first_read_close(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle == kernel32.pipe_read_handle:
            # The close of the read end fails the first time only: a
            # later recovery of the owner may close it.
            attempts = kernel32.__dict__.setdefault('close_attempts', {})
            attempts[handle] = attempts.get(handle, 0) + 1
            if attempts[handle] == 1:
                return 0
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe,
                                         'SetHandleInformation': refuse_inherit,
                                         'CloseHandle': fail_first_read_close})
    kernel32.next_handle = 700
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_pipe('stdout')
    assert info.value.code == 'BROKER_PIPE_INHERIT_FAILED'
    # The end that was closed with a confirmed close left the table and
    # the end that could not be closed is still with its owner.
    retained = api.retained_handles()
    assert [entry['kind'] for entry in retained] == ['pipe_read']
    # The façade keeps the **original** object of the end: the handle of
    # a pipe is a ``ctypes`` object and that type is not hashable, so
    # the membership is checked with the number that the kernel knows.
    # The production is not changed to make the test easier: the handle
    # stays the object that the façade created.
    retained_handle = retained[0]['handle']
    assert getattr(retained_handle, 'value', retained_handle) == kernel32.pipe_read_handle
    assert getattr(retained_handle, 'value', retained_handle) in kernel32.live
    # The identity of the original end is never replaced by a copy: the
    # façade hands out the very object that it holds.
    assert api.retained_handles()[0]['handle'] is retained_handle
    # The owner of the end is the façade and its recovery is the entry
    # that releases it.
    assert retained[0]['owner'] == 'WINDOWS_API'
    # The recovery of the owner reaches the end that is still open.
    report = api.release_retained()
    assert [item['kind'] for item in report] == ['pipe_read']
    assert api.retained_handles() == []
    assert not kernel32.live


# -- N05-R04: a cancellation in the release of the core -------------------

def test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup(tmp_path):
    """N05-R04 (M06): a cancellation is not an ordinary evidence.

    Obligation: the finalizers of the release of the core run on their
    own and the cancellation propagates after the cleanup.  Entry:
    ``BrokerCore.stop`` and ``BrokerCore._close_handle``.  Trigger: the
    close of one handle raises a cancellation.  Oracle: the later
    finalizers still ran and the cancellation is the error that leaves
    the method.  Negative: an ordinary failure of a close is named and
    it does not stop the release.  Returned state: the cancellation is
    named as a cancellation in the failures of the core.  Salvage: the
    handles that are still open keep their owner.
    """
    class CancellingWin32(RecordingWin32):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.cancelled = False
            self.cancelled_handle = None

        def close_handle(self, handle):
            self.calls.append(('close_handle', handle))
            if (self.cancelled_handle is not None
                    and handle == self.cancelled_handle
                    and not self.cancelled):
                self.cancelled = True
                raise KeyboardInterrupt('close_cancelled')
            super().close_handle(handle)

    win32 = CancellingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    job = core.job
    # The close of the job handle of the round raises a cancellation.
    win32.cancelled_handle = job
    with pytest.raises(KeyboardInterrupt):
        core.stop('STOP')
    # The finalizers that follow the cancellation still ran.
    assert win32.closed, 'the handles that follow the cancellation were not closed'
    assert 'job_process_ids' in win32.names()
    # The cancellation is named as a cancellation and it is not only an
    # ordinary evidence of the round.
    cancellations = [item for item in core.failures if item.get('cancellation')]
    assert cancellations, 'the cancellation was not named'
    assert any(item['stage'] == 'release_job' for item in cancellations)
    # The pending pass of the cleanup closed the job handle for real.
    # The bookkeeping of the core agrees with that fact: a handle that
    # is closed is never named by the job of the round any more.
    assert job not in win32.live, 'the job handle was not really closed'
    assert core.job is None, 'the core names a handle that is closed'
    assert core.job_closed is True
    assert core._pending.pending() == []
    assert not [item for item in core._retained_resources
                if item['handle'] is job], \
        'the core retains a handle that was really closed'

    # -- a close that fails temporarily is retried by the pending pass -----
    class TransientWin32(RecordingWin32):
        """A façade whose first close of every handle fails."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.failed_handles = set()

        def close_handle(self, handle):
            self.calls.append(('close_handle', handle))
            if handle not in self.failed_handles:
                self.failed_handles.add(handle)
                raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            super().close_handle(handle)

    win32 = TransientWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    job = core.job
    # The eligibility of the control handle of a process is a
    # **callable** over the original record and never a frozen copy of
    # the fact: the pending pass asks it at the moment of its close and
    # it reads the current exit fact of the record.  A frozen answer
    # would protect the handle for ever.
    for item in core._pending.pending():
        if item['kind'] == 'process':
            assert callable(item['closeable']), \
                'the close eligibility of the control handle was frozen'
            assert item['closeable']() is False, \
                'the eligibility of a live process is not closeable'
    handles = [record['process_handle'] for record in core.records]
    try:
        core.stop('STOP')
        # The pending pass retried the close and it succeeded: the fact
        # of the close is the fact of the round.
        assert not win32.live, 'the pending pass did not close the handles'
        for handle in handles:
            assert win32.closed.count(handle) == 1, \
                'the control handle of a process was not closed exactly once'
        assert core.job is None
        assert core.job_closed is True
        assert core._pending.pending() == []
        # The records of the round agree with the close of their handles.
        for record in core.records:
            assert record['process_handle'] is None
            assert record['thread_handle'] is None
            assert record['process_handle_closed'] is True
            assert record['thread_handle_closed'] is True
        # Nothing that was really closed is retained any more.
        assert core._retained_resources == []
        assert not [item for item in core._retained_resources
                    if item['handle'] is job]
    finally:
        # The salvage of the test owner: the handles that the product
        # could not close are released by the owner of the façade.
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)

    # -- a close that keeps failing keeps its owner ------------------------
    class PersistentWin32(RecordingWin32):
        """A façade whose close of every handle fails."""

        def close_handle(self, handle):
            self.calls.append(('close_handle', handle))
            raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')

    win32 = PersistentWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    job = core.job
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
        assert retained[0]['code'] == 'BROKER_HANDLE_CLOSE_FAILED'
        # The handle is still pending and it still has its owner.
        pending = [item for item in core._pending.pending()
                   if item['handle'] is job]
        assert pending, 'the handle that could not be closed lost its owner'
        assert pending[0]['owner'] == 'CORE'
    finally:
        # The salvage of the test owner: the handles that the product
        # could not close are released by the owner of the façade.
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N05-R05: one process never skips the others -------------------------

def test_n05_r05_one_process_never_skips_the_wait_of_the_next_one(tmp_path):
    """N05-R05 (M06): the processes of a round are independent.

    Obligation: the wait of one original process never skips the wait
    of the next one and the shared deadline is recomputed before every
    wait.  Entry: ``BrokerCore.stop`` and ``BrokerCore._wait_the_processes``.
    Trigger: the wait of the first process raises an ordinary error.
    Oracle: the later process was waited for and released.  Negative:
    an expired deadline never starts a new wait.  Returned state: the
    failure of the first process is named and the round stays unknown.
    Salvage: the handles of the round are released by their owner.

    RECONCILIATION (N1 correction 11): the old group ended with the
    blanket assertion that **every** handle of the round was closed.
    That assertion contradicted the obligation N10-R01: the control
    handle of a process whose exit was **not** confirmed may not be
    closed, because it is the only handle that may still stop that
    process.  The expectation of the group is therefore **split by the
    actual facts** and it is not weakened:

    * the process whose exit was really confirmed is released and its
      control handle is closed **exactly once**;
    * the process whose wait failed keeps its **original** control
      handle: the handle is still in the record and still in the
      pending table with its owner, it is **not** closed, and the
      round stays ``UNKNOWN_RETAINED``;
    * the later process and the independent handles of the round (the
      thread handles, the pipes and the job) are released and the
      original error of the first wait is preserved;
    * the recovery of the **same** owner succeeds only after an
      explicit **new** proof of the exit, inside the **same** unextended
      cleanup deadline; the deadline of the cleanup is never extended
      and the salvage of the owner of the test is recorded apart and
      it is never a product PASS.
    """
    class FailingWaitWin32(RecordingWin32):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.failed = False

        def wait_process(self, process, timeout_ms):
            self.calls.append(('wait_process', process, timeout_ms))
            if not self.failed:
                self.failed = True
                raise RuntimeError('wait_failed')
            for entry in self.created:
                if entry['handle'] == process:
                    return entry['exited']
            return True

    win32 = FailingWaitWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    first_record = core.records[0]
    second_record = core.records[1]
    unconfirmed = first_record['process_handle']
    confirmed = second_record['process_handle']
    try:
        evidence = core.stop('STOP')
        # The failure of the first wait is named and the group was not
        # interrupted: the second process was waited for as well.
        assert any(item.get('error_type') == 'RuntimeError'
                   for item in core.failures), \
            'the original error of the first wait was lost'
        waited = [call for call in win32.calls if call[0] == 'wait_process']
        assert len(waited) >= 2, 'the wait of the second process never ran'
        assert evidence['state'] == 'UNKNOWN_RETAINED'
        # -- the confirmed exit: the control handle of the second
        #    process is closed exactly once --------------------------
        assert second_record['exited'] is True, \
            'the exit of the second process was not confirmed'
        assert second_record['process_handle_closed'] is True
        assert win32.closed.count(confirmed) == 1, \
            'the control handle of the confirmed process was closed twice'
        assert confirmed not in win32.live
        # -- the unconfirmed exit: the control handle of the first
        #    process keeps its owner and it is NOT closed -----------
        assert first_record['exited'] is False, \
            'the exit of the first process was claimed without a proof'
        assert first_record['process_handle'] is unconfirmed, \
            'the control handle was forgotten while the exit was unknown'
        assert first_record['process_handle_closed'] is False
        assert unconfirmed in win32.live, \
            'the control handle was closed while the exit was unknown'
        pending = [item for item in core._pending.pending()
                   if item['handle'] == unconfirmed]
        assert pending, 'the control handle lost its owner'
        assert pending[0]['kind'] == 'process'
        assert pending[0]['owner'] == 'CORE'
        retained = [item for item in core._retained_resources
                    if item['handle'] is unconfirmed]
        assert retained, 'the control handle was not named'
        assert retained[0]['code'] == 'BROKER_PROCESS_EXIT_NOT_CONFIRMED'
        # -- the independent handles are released --------------------
        for record in core.records:
            assert record['thread_handle_closed'] is True
            assert record['thread_handle'] is None
        assert core.job_closed is True
        assert core.job is None
        # The **only** handle that is still open is the control handle
        # of the process whose exit was never confirmed.
        assert sorted(win32.live) == [unconfirmed], \
            'a handle was closed or kept without the proof of the exit'

        # -- the recovery: the same owner confirms the exit inside the
        #    SAME unextended deadline and the handle is closed once --
        published = core.cleanup_deadline()
        core.stop('STOP')
        assert core.cleanup_deadline() == published, \
            'the cleanup deadline was extended by the recovery'
        assert first_record['exited'] is True, \
            'the recovery did not confirm the exit of the process'
        assert first_record['process_handle_closed'] is True
        assert first_record['process_handle'] is None
        assert win32.closed.count(unconfirmed) == 1, \
            'the control handle was closed twice'
        assert unconfirmed not in win32.live
        assert core._pending.pending() == []
    finally:
        # The salvage of the owner of the test is bounded and it never
        # hides a resource that the product kept.
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N05-R06: a reader that never started is never joined ----------------

def test_n05_r06_a_reader_that_never_started_is_never_joined(tmp_path):
    """N05-R06 (M06): the readers of a round are coordinated one by one.

    Obligation: a reader whose thread never started is not joined, the
    readers are coordinated one after the other and the read end of a
    live reader is never closed under it.  Entry:
    ``BrokerCore._start_reader`` and ``BrokerCore._close_readers``.
    Trigger: the start of the first reader raises before the thread
    exists.  Oracle: the later reader is coordinated and the read end of
    the live reader keeps its owner.  Negative: a reader that never
    started is not a live reader and its handle is closed with a
    confirmed close.  Returned state: the round names the reader that
    was not stopped.  Salvage: the owner of the live reader closes it
    later.
    """
    import tools.v0_s3_native_broker as broker_module

    class FailingReader:
        """A reader whose thread never starts."""

        def __init__(self, win32, handle, *, limit, name):
            self.win32 = win32
            self.handle = handle
            self.limit = limit
            self.observed = 0
            self.kept = 0
            self.overflow = False
            self.error = None
            self.name = name
            self.ident = None
            self.finished = threading.Event()

        def start(self):
            raise RuntimeError('reader_start_failed')

        def is_alive(self):
            return False

        def join(self, timeout=None):
            raise RuntimeError('cannot join thread before it is started')

    original = broker_module._BoundedStreamReader
    broker_module._BoundedStreamReader = FailingReader
    try:
        win32 = RecordingWin32()
        core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
        core.arm()
        record = {'role': 'COMFY', 'pending_handles': []}
        core.readers.append(FailingReader(win32, 0x31, limit=1024, name='never-started'))
        with pytest.raises(RuntimeError):
            core._start_reader(record, 0x32, 'stdout')
        # The reader that never started is not joined: the join of a
        # thread that was not started is an error of the caller.
        core._close_readers()
    finally:
        broker_module._BoundedStreamReader = original
    states = core.reader_states
    assert states, 'the state of the readers was not recorded'
    assert states[0]['started'] is False
    assert states[0]['alive'] is False
    # The handle of a reader that never started is closed with a
    # confirmed close: no thread of the round reads it.
    assert 0x31 in win32.closed
    assert 0x32 in win32.closed


# -- N05-R07: a background start that did not return ---------------------

def test_n05_r07_a_background_start_that_did_not_return_keeps_its_owner(tmp_path):
    """N05-R07 (M07): a start that did not return keeps the thread.

    Obligation: the original owner of a background thread that is
    still starting is always kept, a late thread may only wind up and
    the deadline of the round is never reset.  Entry:
    ``NativeCustodySession._start_background_thread`` and
    ``NativeCustodySession._stop_background``.  Trigger: the start of
    the reader never returns and the cleanup expires.  Oracle: the
    session keeps the reference, the round is unknown and the late
    thread never does business IO.  Negative: the deadline of the
    cleanup is never renewed.  Returned state: the pending start is
    named.  Salvage: the late thread winds up at once.
    """
    class LatePump(_ChannelPump):
        """A pump whose start does not return before it is released."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.entered = threading.Event()
            self.gate = threading.Event()

        def start(self):
            self.entered.set()
            self.gate.wait(10.0)
            super().start()

    class RecordingBroker:
        def __init__(self):
            self.reads = 0

        def read(self, timeout):
            self.reads += 1
            return None

    clock = ManualClock(1000.0)
    session, _holder, clock = make_session(tmp_path, clock=clock)
    broker = RecordingBroker()
    pump = LatePump(broker, decode=lambda raw: raw, clock=clock)
    starter = threading.Thread(target=session._start_background_thread,
                               args=('pump', pump))
    starter.start()
    assert pump.entered.wait(5.0), 'the start of the reader never blocked'
    # The deadline of the cleanup of the round arrives while the start
    # of the reader is still in flight.
    deadline = session._cleanup_deadline_for()
    clock.value += 10.0
    session._stop_background(deadline)
    evidence = session.evidence()
    assert 'CUSTODY_BACKGROUND_START_PENDING' in evidence['failures']
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    # The original owner of the thread is kept: the reference was never
    # dropped and the deadline of the cleanup was never renewed.
    assert session._pump is pump
    assert session._cleanup_deadline_for() == deadline
    # The late thread may only wind up: it never reads the channel.
    pump.gate.set()
    starter.join(5.0)
    for _ in range(100):
        if broker.reads:
            break
        time.sleep(0.01)
    assert broker.reads == 0, 'the late reader did business IO'


# -- N05-R08: a start that raised after the thread really started --------

def test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread(tmp_path):
    """N05-R08 (M07): the real state of a thread decides, not a flag.

    Obligation: a thread that really runs keeps the reference of the
    session even when its start raised.  Entry:
    ``NativeCustodySession._start_background_thread``.  Trigger: the
    start of the thread raises after the thread really started.
    Oracle: the session keeps the live thread and the round is
    unknown.  Negative: a thread that never started is not a live
    thread and its reference is dropped.  Returned state: the failed
    start is named.  Salvage: the owner of the thread stops it inside
    the deadline of the cleanup.
    """
    class StartedThenFailed(threading.Thread):
        """A reader that really starts and whose start then raises.

        The stand-in implements the **whole** interface of the reader of
        the channel: the evidence of the round reads ``error`` and
        ``alive`` and the stop of the round reads ``stop`` and
        ``join``.  A stand-in that does not implement it would hide the
        real facts of the product behind an ``AttributeError`` and the
        production evidence is never weakened to accommodate it.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.gate = threading.Event()
            self.error = None
            self.finished = threading.Event()
            self.joins = []
            self.stops = 0

        def run(self):
            self.gate.wait(5.0)
            self.finished.set()

        def start(self):
            super().start()
            raise RuntimeError('start_failed_after_start')

        @property
        def alive(self):
            return self.is_alive()

        def stop(self):
            self.stops += 1
            self.gate.set()

        def join(self, timeout=None):
            self.joins.append(timeout)
            return super().join(timeout)

        def join_bounded(self, seconds):
            self.join(seconds)
            return not self.is_alive()

    session, _holder, clock = make_session(tmp_path, clock=ManualClock(1000.0))
    thread = StartedThenFailed(daemon=True, name='lvw-native-custody-late')
    try:
        with pytest.raises(RuntimeError):
            session._start_background_thread('pump', thread)
        evidence = session.evidence()
        assert 'CUSTODY_BACKGROUND_START_FAILED:pump' in evidence['failures']
        assert evidence['state'] == 'UNKNOWN_RETAINED'
        # The live thread keeps the reference of the session: the local
        # flag of the start never took it for a thread that never started.
        assert session._pump is thread
        assert thread.is_alive()
        # The reader interface of the stand-in reports the truth of the
        # thread: the evidence reads it and it never claims a fact that
        # the thread does not have.
        assert evidence['pump_alive'] is True
        assert evidence['pump_error'] is None
        assert evidence['background_threads'][0]['alive'] is True
        assert evidence['background_threads'][0]['started'] is True
        # The owner of the thread stops it inside the deadline of the
        # cleanup.
        thread.gate.set()
        session._stop_background(session._cleanup_deadline_for())
        assert session._pump is None
        assert thread.stops == 1
        assert thread.joins, 'the reader was never joined'
    finally:
        # The salvage of the test owner: the thread of the stand-in is
        # released and joined, whatever the checks above did.  The
        # salvage never changes the fact of the product above.
        thread.gate.set()
        thread.join(5.0)


# -- N05-R09: a closer that could not be built or started ----------------

def test_n05_r09_a_closer_that_could_not_start_does_not_latch_the_round(tmp_path):
    """N05-R09 (M07): a closer that fails is named and stays recoverable.

    Obligation: the construction and the start of the closer are named,
    the waiters end and the original broker stays recoverable.  Entry:
    ``NativeCustodySession._start_bounded_close``.  Trigger: the
    construction of the closer raises.  Oracle: the failure is named,
    the round is unknown and the original broker keeps its owner.
    Negative: the latch of the closer is not permanent: a later attempt
    may try again.  Returned state: the state of the close is not
    ``IN_PROGRESS`` for ever.  Salvage: the public stop of the round
    closes the broker.
    """
    class FailingThread:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('closer_construction_failed')

    session, holder, clock = make_session(
        tmp_path, clock=ManualClock(1000.0),
        close_facts=dict(COMPLETE_CLOSE_FACTS))
    session.start()
    peer = holder['peer']
    with unittest.mock.patch('tools.v0_s3_native_custody.threading.Thread',
                              FailingThread):
        assert session._start_bounded_close() is False
    evidence = session.evidence()
    assert any('CUSTODY_CLOSER_START_FAILED' in failure
               for failure in evidence['failures'])
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    # The close never began: the waiters are not latched and the
    # original broker keeps its owner.
    assert evidence['close_state'] != 'IN_PROGRESS'
    assert session.broker is peer
    assert peer.closed == 0
    # The latch of the closer is not permanent: a later attempt may try
    # again and the public stop of the round is the recovery entry.
    assert session._closer_started is False
    session.stop()
    assert peer.closed == 1
    assert session.broker is None


# -- N05-R10: a launch that could not be handed over ---------------------

def test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources(tmp_path):
    """N05-R10 (M07): the launcher keeps the original resources.

    Obligation: the launcher registers the original process, its
    handles, its pipes and its endpoint and it has a finite recovery
    entry point.  Entry: ``_adopt_broker_process`` and
    ``release_retained_launches``.  Trigger: the channel could not be
    built and the termination, the wait and the close of the pipes
    failed.  Oracle: the original objects are with their owner and the
    session that never took over does not lose the ownership.  Negative:
    a pid is never used to find a process again.  Returned state: the
    failure of the adoption is the error that leaves.  Salvage: the
    recovery of the launcher is explicit and it names what it kept.

    CORRECTION 12 (M07-A): a raw stream that the launch could not
    close is owned by the **launch** and the **same** owner retries it.
    A retry that fails keeps the owner of the stream and names the
    failure: a stream is never forgotten without a confirmed close.
    """
    class BrokenProcess:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0
            self.stdin = type('S', (), {'close': self._fail_close})()
            self.stdout = type('S', (), {'close': self._fail_close})()

        def _fail_close(self):
            raise RuntimeError('pipe_close_failed')

        def terminate(self):
            self.terminated += 1
            raise RuntimeError('terminate_failed')

        def wait(self, timeout=None):
            self.waited += 1
            raise RuntimeError('wait_failed')

    process = BrokenProcess()

    def broken_channel():
        raise RuntimeError('channel_construction_failed')

    with pytest.raises(RuntimeError):
        _adopt_broker_process(process, channel_factory=broken_channel,
                              executable='C:/python.exe', executable_sha256='a' * 64)
    # The launcher tried to release the process and it named the
    # failures of every step.
    assert process.terminated == 1
    assert process.waited == 1
    # The original resources are with the table of the launcher and they
    # are the **original** objects: no pid is used to find them again.
    items = _launcher_custody_items()
    kinds = sorted(item['kind'] for item in items)
    assert 'process' in kinds
    assert 'stdin' in kinds
    assert 'stdout' in kinds
    process_entry = [item for item in items if item['kind'] == 'process'][0]
    assert process_entry['resource'] is process
    # The recovery of the launcher is explicit and it is finite.
    report = release_retained_launches()
    assert 'process' in report['retained']
    assert _launcher_custody_items()

    # -- N1 correction 12 (M07-A): a **failed** retry keeps the owner of
    #    the raw stream and names the failure.  A stream is never
    #    forgotten without a confirmed close.
    holder = m07a_interrupted_launch(tmp_path, sealed_plan(), failures=2)
    stdout = holder['stdout']
    aggregate = holder['aggregate'][0] if holder['aggregate'] else None
    assert aggregate is not None, 'the interrupted launch lost its owner'
    release_retained_launches()
    assert stdout.attempts == 1, \
        'the raw stream was not closed by the first release'
    assert stdout.confirmed == 0
    release_retained_launches()
    assert stdout.attempts == 2, \
        'the same owner did not retry the raw stream of the launch'
    assert stdout.confirmed == 0, \
        'the failed retry of the raw stream was read as a close'
    owned = [item for item in _launcher_custody_items()
             if item['kind'] == 'stdout' and item['resource'] is stdout]
    assert owned, 'the failed retry forgot the owner of the raw stream'
    assert [item['name'] for item in aggregate.raw_streams] == ['stdout'], \
        'the launch forgot a raw stream that was never closed'


# -- N05-R11: the shared budget of the startup ---------------------------

def test_n05_r11_no_role_is_created_or_resumed_after_the_deadline(tmp_path):
    """N05-R11 (M08): the startup checks the shared budget.

    Obligation: the action, the creation, the assignment, the resume
    and the start of a reader check the shared cancel and the shared
    deadline before they happen and after they happened.  Entry:
    ``BrokerCore.check_startup_budget`` and ``BrokerCore._launch_role``.
    Trigger: the creation of the role consumes the whole lease.
    Oracle: the process is never assigned and never resumed and the
    late resource is only cleaned up.  Negative: a role that is created
    after the deadline is never resumed and the next role is never
    created.  Returned state: the refusal of the startup is named.
    Salvage: the handles of the late role are released by their owner.

    The correction 08 of the root corrected the **oracle** of the
    second scenario of the group.  The product obligation of the root
    has always been that **every** creation is refused before the
    deadline of the round arrived, and the arm of a round is a creation
    like every other one.  The old group armed the round first and
    refused only the launch, which contradicts that obligation.  The
    group now drives three named scenarios and the arm of an expired
    round is refused **inside** the guard of the refusal, with a stable
    error code and with **nothing** created at all.

    The check of the budget before the creation of the job was **not**
    relaxed: the production keeps its bytes and the refusal of the
    expired arm is the behaviour that the root requires.

    RECONCILIATION (N1 correction 11): the second scenario of the group
    ended with the blanket expectation that **every** handle of the
    round was closed.  The late process of that scenario is a process
    whose exit was never confirmed - the lease of the round had already
    expired when it was created - and the obligation N10-R01 forbids the
    close of the control handle of such a process.  The expectation is
    therefore **split by the actual facts**: the control handle of the
    late process keeps its original reference and its owner, every
    other handle of the round is released, and the recovery of the same
    owner may not confirm the exit any more inside the same unextended
    deadline.  The salvage of the owner of the test is recorded apart
    and it is never a product PASS.
    """
    # SCENARIO ONE: an arm whose deadline is still valid succeeds: the
    # job of the round is created and the round is armed.
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.bind_absolute_deadline(1005.0)
    try:
        core.arm()
        assert 'create_job' in win32.names()
        assert core.job is not None
        assert core.state == 'ARMED'
    finally:
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)

    # SCENARIO TWO: the creation of the role consumes the whole lease
    # of the round: the launch is refused, the process is never
    # assigned and it is never resumed and the late resource is only
    # cleaned up.
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.bind_absolute_deadline(1005.0)
    core.arm()
    original = win32.create_process_suspended

    def slow_create(**kwargs):
        result = original(**kwargs)
        # The creation consumes the whole lease of the round.
        clock.value += 100000.0
        return result

    win32.create_process_suspended = slow_create
    with pytest.raises(BrokerError) as info:
        core.launch()
    assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED'
    # The process was never assigned and it was never resumed.
    assert 'assign_process_to_job' not in win32.names()
    assert 'resume_thread' not in win32.names()
    # The late resource was only cleaned up.
    assert core.state == 'UNKNOWN_RETAINED'

    # RECONCILIATION (N1 correction 11): the late resource is a process
    # whose exit was **never** confirmed: the lease of the round had
    # already expired when it was created, so the bounded wait of the
    # exit never started.  The blanket expectation that every handle of
    # the round is closed contradicted the obligation N10-R01 and it is
    # therefore **split by the actual facts**:
    #
    # * the control handle of the late process keeps its **original**
    #   reference: it is in the record and in the pending table with
    #   its owner and it is **not** closed;
    # * every other handle of the round - the thread handle, the pipes
    #   and the job - is released;
    # * the recovery of the same owner may not confirm the exit any
    #   more, because the **same** unextended deadline of the cleanup
    #   is expired: the handle stays with its owner and the salvage of
    #   the owner of the test is recorded apart.  It is never a product
    #   PASS.
    late_record = core.records[0]
    late = late_record['process_handle']
    assert late is not None, 'the late process never got a control handle'
    assert late_record['exited'] is False, \
        'the exit of the late process was claimed without a proof'
    assert late_record['process_handle_closed'] is False
    assert late in win32.live, \
        'the control handle was closed while the exit was unknown'
    pending = [item for item in core._pending.pending() if item['handle'] == late]
    assert pending, 'the control handle of the late process lost its owner'
    assert pending[0]['kind'] == 'process'
    # Every other handle of the round was released by its owner.
    assert late_record['thread_handle_closed'] is True
    assert late_record['thread_handle'] is None
    assert core.job_closed is True
    assert sorted(win32.live) == [late], \
        'a handle was closed or kept without the proof of the exit'
    # The recovery of the same owner: the deadline is not extended and
    # the exit may not be confirmed any more.
    published = core.cleanup_deadline()
    core.stop('STOP')
    assert core.cleanup_deadline() == published, \
        'the cleanup deadline was extended by the recovery'
    assert late_record['exited'] is False
    assert late_record['process_handle_closed'] is False
    assert late in win32.live
    # The salvage of the owner of the test is bounded and it is recorded
    # apart: it is never a product PASS.
    for handle in list(win32.live):
        RecordingWin32.close_handle(win32, handle)

    # SCENARIO THREE: the arm of a round whose deadline already
    # arrived is refused **before** the job of the round exists.  The
    # arm is inside the guard of the refusal and the error code is
    # stable.
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    run_root = tmp_path / 'expired-arm'
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=run_root,
                      clock=clock)
    core.bind_absolute_deadline(999.0)
    with pytest.raises(BrokerError) as info:
        core.arm()
    assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED'
    # **Nothing** was created: the job, the limits of the job, the
    # pipes, the processes, the assignment and the resume were never
    # called at all.
    for name in ('create_job', 'set_job_kill_on_close', 'create_pipe',
                 'create_process_suspended', 'assign_process_to_job',
                 'resume_thread'):
        assert name not in win32.names(), name
    # The round left no handle behind and it left no output behind.
    assert win32.live == {}
    assert not win32.closed
    assert core.state != 'ARMED'
    assert not (run_root.exists() and any(run_root.rglob('*')))


# -- N05-R12: the one cleanup deadline -----------------------------------

def test_n05_r12_the_cleanup_deadline_is_published_once_and_never_extended(tmp_path):
    """N05-R12 (M08): the cleanup deadline is published atomically.

    Obligation: the first entry of the cleanup publishes one deadline
    and every later caller reuses it.  Entry:
    ``NativeCustodySession._cleanup_deadline_for`` and
    ``BrokerCore.cleanup_deadline``.  Trigger: two callers enter the
    cleanup at the same moment.  Oracle: every caller sees the same
    value.  Negative: the deadline is never extended and never
    replaced.  Returned state: the deadline of the evidence is the
    published one.  Salvage: none is needed: nothing was created.
    """
    clock = SteppingClock(1000.0, step=0.5)
    session, _holder, _clock = make_session(tmp_path, clock=clock)
    values = []
    barrier = threading.Barrier(4)

    def enter():
        barrier.wait()
        values.append(session._cleanup_deadline_for())

    threads = [threading.Thread(target=enter) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert len(values) == 4
    # Every caller saw the very same value: the deadline was published
    # once and it was not generated twice.
    assert len(set(values)) == 1, 'the cleanup deadline was generated twice'
    published = values[0]
    # The deadline is never extended by a caller that came later.
    clock.advance(100.0)
    assert session._cleanup_deadline_for() == published
    assert session.evidence()['cleanup_deadline'] == published

    # The core of the broker publishes its deadline the same way.
    clock = SteppingClock(1000.0, step=0.5)
    core = BrokerCore(win32=RecordingWin32(), plan=sealed_plan(),
                      run_root=tmp_path, clock=clock)
    values = []
    barrier = threading.Barrier(4)

    def enter_core():
        barrier.wait()
        values.append(core.cleanup_deadline())

    threads = [threading.Thread(target=enter_core) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert len(set(values)) == 1, 'the cleanup deadline was generated twice'


# -- N05-R13: the remaining budget is recomputed before every wait -------

def test_n05_r13_the_remaining_budget_is_recomputed_before_every_wait(tmp_path):
    """N05-R13 (M08): no wait ever receives the budget twice.

    Obligation: the remaining budget is recomputed before every wait,
    every join and every cancel.  Entry: ``BrokerCore._close_readers``
    and ``BrokerCore._wait_timeout_ms``.  Trigger: the wait of a reader
    consumes the budget of the round.  Oracle: the join of the reader
    receives the time that is left and not the whole budget again.
    Negative: there is no fixed extra settle.  Returned state: the
    deadlines of the round are the published ones.  Salvage: the
    handle of the reader is released by its owner.
    """
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    # The deadline of the round leaves less than the join cap of the
    # package: the remaining budget is visible in the two waits.
    core.bind_absolute_deadline(1001.5)
    core.arm()
    core.launch()
    reader = RecordingReader(clock, 0x44)
    core.readers.append(reader)
    core._close_readers()
    # The wait of the reader consumed the budget of the round and the
    # join received the time that was left.
    assert reader.waits, 'the reader was never waited for'
    assert reader.joins, 'the reader was never joined'
    assert reader.joins[0] < reader.waits[0], \
        'the join received the budget of the wait again'
    assert reader.joins[0] >= 0.0

    # The waits of the processes receive a decreasing budget: the
    # remaining is recomputed before every one of them.
    clock = SteppingClock(1000.0, step=1.0)
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                      clock=clock)
    core.arm()
    core.launch()
    core.stop('STOP')
    timeouts = [call[2] for call in win32.calls if call[0] == 'wait_process']
    assert timeouts, 'no process was waited for'
    assert timeouts == sorted(timeouts, reverse=True), \
        'the budget of the wait was not recomputed'


# -- N05-R14: an await that is running reads the tightened deadline ------

def test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline():
    """N05-R14 (M08): a running await reads the shared deadline.

    Obligation: an await that is already running reads the deadline
    that was tightened after it began.  Entry:
    ``_WindowsPipeEndpoint._await`` and
    ``_WindowsPipeEndpoint.bind_deadline``.  Trigger: the read carries
    no deadline and the deadline is bound while the read runs.  Oracle:
    the read ends at the tightened deadline and the original worker and
    its handle are kept.  Negative: a cancellation that reports
    ``NOT_FOUND`` and never completes is unknown at the deadline.
    Returned state: the failure is named and the worker is retained.
    Salvage: the owner of the worker stops it.
    """
    entered = threading.Event()
    release = threading.Event()

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            pass

    clock = ManualClock(1000.0)
    # The endpoint is built with its **real** constructor and with the
    # injected primitives of the round: the fixture never bypasses the
    # constructor, so every invariant of the endpoint - the lock of the
    # admission among them - is really initialised and the admission is
    # never a permissive fallback.
    endpoint = _WindowsPipeEndpoint(
        file_object=type('F', (), {'close': lambda self: None})(),
        name='inprocess', api=Api(), clock=clock, handle=702)
    # The request of the group enters **unexpired**: the round has no
    # deadline yet and the admission of the generation is the one of a
    # live round.  The initial expired refusal is the separate
    # obligation N10-R06 and it is not weakened here.
    assert endpoint._effective_deadline() is None, \
        'the request of the group did not enter with a live deadline'

    def action(request):
        entered.set()
        release.wait(5.0)
        return b''

    original = endpoint._read_block
    endpoint._read_block = action

    outcome = {}

    def run_read():
        try:
            endpoint.read(None, None)
        except BrokerError as error:
            outcome['code'] = error.code
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            outcome['code'] = type(error).__name__

    reader = threading.Thread(target=run_read)
    reader.start()
    assert entered.wait(5.0), 'the read never entered the operation'
    # The request was really admitted and it really entered the
    # primitive: the deadline of the round is tightened **after** that
    # fact and never before it.  The initial expired refusal is the
    # separate obligation N10-R06 and it is not weakened here.
    assert endpoint._reader is not None, \
        'the worker of the endpoint was never started'
    assert endpoint._effective_deadline() is None, \
        'the request did not enter with a live deadline'
    # The deadline of the round is tightened while the read is running.
    tightened = clock.value + 0.5
    endpoint.bind_deadline(tightened)
    clock.advance(5.0)
    reader.join(5.0)
    # The tightened deadline is the one that the endpoint uses and the
    # lease of the round is never extended by the tightening.
    assert endpoint._effective_deadline() == tightened, \
        'the lease of the round was extended'
    assert outcome.get('code') in ('BROKER_PIPE_TIMEOUT',
                                    'BROKER_PIPE_CANCEL_NOT_CONFIRMED'), \
        'the running await did not read the tightened deadline'
    # The original worker and its handle are kept: the unknown state of
    # the endpoint has a reachable owner.
    assert endpoint._retained, 'the worker of the endpoint was forgotten'
    worker = endpoint._retained[0]
    assert worker.thread_handle == 701
    assert worker.thread_handle_released is False
    assert endpoint.facts['retained_workers'] == 1
    # The salvage of the test owner: the worker is released.
    release.set()
    worker.join_bounded(5.0)
    endpoint._read_block = original

    # -- N1 correction 12 (M08-C): the wait of the endpoint is cropped
    #    to the time that is really left until the **current** effective
    #    deadline of the round.  The requested value of the wait is the
    #    fact of the test: it is recorded before and after the
    #    tightening.
    requested = []
    original_wait_done = _WindowsPipeWorker.wait_done

    def recording_wait_done(self, generation, timeout):
        requested.append(timeout)
        return original_wait_done(self, generation, timeout)

    clock = ManualClock(1000.0)

    class WaitApi:
        def duplicate_current_thread_handle(self):
            return 711

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            return b''

    endpoint = _WindowsPipeEndpoint(
        file_object=type('F', (), {'close': lambda self: None})(),
        name='inprocess-wait', api=WaitApi(), clock=clock, handle=712)
    waiting = threading.Event()

    def blocking_action(request):
        waiting.wait(10.0)
        return b''

    endpoint._read_block = blocking_action
    holder = {}

    def run_read():
        try:
            endpoint.read(clock.value + 10.0, None)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            holder['error'] = error

    reader = threading.Thread(target=run_read)
    with unittest.mock.patch.object(_WindowsPipeWorker, 'wait_done',
                                    recording_wait_done):
        reader.start()
        try:
            deadline = time.monotonic() + 10.0
            while not requested and time.monotonic() < deadline:
                time.sleep(0.005)
            assert requested, 'the endpoint never waited for its worker'
            # The deadline of the round is tightened while the read runs
            # and the next wait receives the time that is really left.
            endpoint.bind_deadline(clock.value + 0.01)
            deadline = time.monotonic() + 10.0
            while min(requested) > 0.01 + 1e-9 and time.monotonic() < deadline:
                time.sleep(0.005)
            waiting.set()
            reader.join(10.0)
            assert not reader.is_alive(), 'the read of the round was left behind'
            facts = {'requested': list(requested)}
            assert max(requested) <= 0.05 + 1e-9, \
                'the wait of the endpoint exceeded the poll cap of the package'
            assert min(requested) <= 0.01 + 1e-9, \
                'the wait of the endpoint was not cropped to the remaining'
        finally:
            waiting.set()
            reader.join(10.0)
            endpoint.close()

    # -- N1 correction 12 (M08-C): the put of the reader of the channel
    #    is cropped to the time that is really left.  There is no
    #    positive floor beyond the remaining of the round.
    class SlowReader:
        """A read end that delivers one frame and then waits."""

        def __init__(self):
            self.blocks = [b'one\n']
            self.released = threading.Event()

        def read(self, deadline=None, cancel=None):
            if self.blocks:
                return self.blocks.pop(0)
            if not self.released.is_set():
                self.released.wait(10.0)
                return b'two\n'
            return b''

        def close(self):
            return {'closed': True, 'retained_workers': 0,
                    'worker_thread_handle_released': True}

    class BlockWriter:
        def write(self, raw, deadline=None, cancel=None):
            return len(raw)

        def close(self):
            return {'closed': True, 'retained_workers': 0,
                    'worker_thread_handle_released': True}

    clock = ManualClock(1000.0)
    channel = StreamChannel(None, None, read_endpoint=SlowReader(),
                             write_endpoint=BlockWriter(), clock=clock,
                             max_frames=2)
    puts = []
    original_put = channel._queue.put

    def recording_put(item, timeout=None):
        puts.append(timeout)
        return original_put(item, timeout=timeout)

    channel._queue.put = recording_put
    channel.bind_deadline(clock.value + 10.0)
    try:
        deadline = time.monotonic() + 10.0
        while not puts and time.monotonic() < deadline:
            time.sleep(0.005)
        assert puts, 'the reader of the channel never put a frame'
        assert puts[0] == pytest.approx(0.5), \
            'the put of the reader did not use the wait of the package'
        # The deadline of the round is tightened while the reader waits
        # for its next frame.
        channel.bind_deadline(clock.value + 0.02)
        channel._reader.released.set()
        deadline = time.monotonic() + 10.0
        while len(puts) < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(puts) >= 2, 'the reader of the channel never put a frame'
        assert min(puts) <= 0.02 + 1e-9, \
            'the put of the reader was not cropped to the remaining'
        assert max(puts) <= 0.5 + 1e-9
    finally:
        channel._reader.released.set()
        channel.close()


# -- N05-R15: the worker coordinates by generation ------------------------

def test_n05_r15_the_worker_coordinates_by_generation_and_keeps_its_handle():
    """N05-R15 (M08): the worker of an endpoint coordinates by request.

    Obligation: the submission and the cancellation of a worker are
    coordinated by the same generation, a done of an older generation
    is never the done of this one and a handle that could not be closed
    keeps its owner.  Entry: ``_WindowsPipeWorker.submit``,
    ``_WindowsPipeWorker.request_cancel`` and
    ``_WindowsPipeWorker.release_thread_handle``.  Trigger: a
    cancellation that arrives while a request is queued.  Oracle: the
    request that is submitted after the cancellation is refused and the
    handle of the thread is kept.  Negative: a request that does not
    fit into the queue is refused with a named error.  Returned state:
    the state of the worker names the cancellation.  Salvage: the owner
    of the worker releases it.
    """
    entered = []
    release = threading.Event()

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')

    def action(request):
        entered.append(request)
        release.wait(5.0)
        return b''

    worker = _WindowsPipeWorker(Api(), 702, kind='read', action=action,
                                name='n05-r15-worker')
    worker.start()
    worker.wait_ready(2.0)
    generation = worker.submit(b'first')
    for _ in range(100):
        if entered:
            break
        time.sleep(0.02)
    assert entered == [b'first']
    worker.submit(b'second')
    # The cancellation stops the worker from accepting a new task.
    state = worker.request_cancel(time.monotonic() + 0.2)
    assert state == 'NOT_FOUND'
    with pytest.raises(BrokerError) as info:
        worker.submit(b'third')
    assert info.value.code == 'BROKER_WORKER_CANCELLED'
    # The completion of an older generation is never the completion of a
    # newer one.
    assert worker.wait_done(generation + 1, 0.05) is False
    # The handle of the thread could not be closed: the original owner
    # keeps it.
    assert worker.release_thread_handle() is False
    assert worker.thread_handle == 701
    assert worker.thread_handle_released is False
    # The salvage of the test owner: the worker ends and its handle is
    # released.
    release.set()
    worker.stop_accepting()
    worker.join_bounded(5.0)
    assert not worker.is_alive()


# -- N05-R16: the unknown state is latched atomically -------------------

def test_n05_r16_the_unknown_state_is_latched_atomically(tmp_path):
    """N05-R16 (M08): the unknown state is a one way latch.

    Obligation: the latch of the unknown state and the application of a
    state share one owner, so that a late reply never overwrites the
    unknown state of the round.  Entry:
    ``NativeCustodySession._apply_state`` and
    ``NativeCustodySession._latch_unknown_state``.  Trigger: a reply
    that passes the check at the same moment as the failure of the
    background.  Oracle: the round stays unknown.  Negative: a status
    is never sent after the stop of the round.  Returned state: the
    late state is named and ignored.  Salvage: the close of the round
    is bounded and it ends.
    """
    for _ in range(50):
        session, holder, clock = make_session(tmp_path, clock=ManualClock(1000.0))
        session.start()
        barrier = threading.Barrier(2)
        outcome = {}

        def late_reply():
            barrier.wait()
            outcome['applied'] = session._apply_state('RUNNING')

        worker = threading.Thread(target=late_reply)
        worker.start()
        barrier.wait()
        session._latch_unknown_state()
        worker.join(5.0)
        # The unknown state of the round was never overwritten.
        assert session.state == 'UNKNOWN_RETAINED'
        if outcome.get('applied') is False:
            assert any('CUSTODY_LATE_STATE_IGNORED' in failure
                       for failure in session.evidence()['failures'])
        # A status is never sent after the stop of the round.
        session._stopping = True
        sent = len(holder['peer'].outbound)
        session._last_heartbeat = clock.value - 61.0
        assert session._heartbeat_step() is False
        assert len(holder['peer'].outbound) == sent
        session._stopping = False
        session.stop()


# -- N05-R17: one owner of the frame budget ------------------------------

def test_n05_r17_the_frame_budget_has_one_owner_in_both_directions(tmp_path):
    """N05-R17 (M08): the frame budget is one atomic owner.

    Obligation: the check and the commit of the frame budget are one
    atomic step in both directions.  Entry:
    ``NativeCustodySession._reserve_frame``.  Trigger: two directions
    check the budget at the same moment.  Oracle: only one of them
    takes the last frame of the budget.  Negative: the total of the two
    directions never exceeds the limit.  Returned state: the refused
    direction is named.  Salvage: nothing was created.
    """
    session, _holder, _clock = make_session(tmp_path)
    session.start()
    # Exactly one frame of the budget is left for the two directions.
    session._frames_sent = MAX_FRAMES - RESERVED_TERMINAL_FRAMES - 1
    session._frames_received = 0
    outcomes = []
    barrier = threading.Barrier(2)

    def reserve(received):
        barrier.wait()
        try:
            session._reserve_frame(received=received)
            outcomes.append('accepted')
        except CustodyError as error:
            outcomes.append(error.code)

    threads = [threading.Thread(target=reserve, args=(index == 1,))
               for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert sorted(outcomes) == ['CUSTODY_FRAME_BUDGET_EXCEEDED', 'accepted'], \
        'the two directions took the last frame of the budget together'
    assert session._frames_sent + session._frames_received <= MAX_FRAMES
    session.stop()


# -- N05-R18: the terminal exchange consumes its reservation -------------

def test_n05_r18_the_terminal_exchange_consumes_its_reservation(tmp_path):
    """N05-R18 (M08): the terminal frames are inside the budget.

    Obligation: the frames of the terminal exchange consume the
    reservation that was kept for them and they are never refused
    because of it.  Entry: ``NativeCustodySession._reserve_frame`` and
    ``BrokerLoop._check_frame_budget``.  Trigger: the budget is nearly
    exhausted.  Oracle: the terminal frame is accepted and the
    non-terminal frame is refused.  Negative: a non-terminal frame
    never borrows the reservation.  Returned state: the refusal is
    named and the round fails closed.  Salvage: nothing was created.
    """
    session, _holder, _clock = make_session(tmp_path)
    session.start()
    # The total is at the limit of the non-terminal frames: only the
    # reservation of the terminal exchange is left.
    session._frames_sent = MAX_FRAMES - RESERVED_TERMINAL_FRAMES
    session._frames_received = 0
    # The terminal frame consumes the reservation: it is legal.
    session._reserve_frame(terminal=True)
    # A non-terminal frame never borrows the reservation.
    with pytest.raises(CustodyError) as info:
        session._reserve_frame()
    assert info.value.code == 'CUSTODY_FRAME_BUDGET_EXCEEDED'
    session.stop()

    # The broker of the round applies the same rule to the frame that
    # it receives.
    plan = sealed_plan()
    core = BrokerCore(win32=RecordingWin32(), plan=plan, run_root=tmp_path)
    loop = BrokerLoop(core=core, transport=object(), plan=plan, nonce='a' * 32)
    loop._frames = MAX_FRAMES - RESERVED_TERMINAL_FRAMES
    loop._sent_frames = 0
    loop._check_frame_budget(0)
    with pytest.raises(BrokerError) as info:
        loop._check_frame_budget(RESERVED_TERMINAL_FRAMES)
    assert info.value.code == 'BROKER_FRAME_BUDGET_EXCEEDED'


# -- N05-R19: the unconfirmed items are coordinated again ---------------

def test_n05_r19_the_unconfirmed_items_are_coordinated_again(tmp_path):
    """N05-R19 (M09): the attempt that ended is not a release.

    Obligation: the items that a close did not confirm are coordinated
    again inside the original deadline and the confirmed items are never
    closed twice.  Entry: ``NativeCustodySession.stop`` and
    ``NativeCustodySession._recover_close``.  Trigger: the close of the
    peer fails and the condition of the round recovers.  Oracle: the
    peer is coordinated again through the public stop and the deadline
    of the cleanup is not reset.  Negative: a recovery that arrives
    after the deadline keeps the resources with their owner.  Returned
    state: the state of the close is published.  Salvage: the owner of
    the peer releases it.
    """
    session, holder, clock = make_session(
        tmp_path, close_facts=dict(COMPLETE_CLOSE_FACTS,
                                   process_handle_released=False))
    session.start()
    peer = holder['peer']
    deadline = session._cleanup_deadline_for()
    first = session.stop()
    assert first['state'] == 'UNKNOWN_RETAINED'
    assert peer.closed == 1
    assert session.broker is peer
    # The condition of the round recovered.
    peer.close_facts = dict(COMPLETE_CLOSE_FACTS)
    second = session.stop()
    assert peer.closed == 2, 'the peer was never coordinated again'
    assert session.broker is None
    assert second['broker_retained'] is False
    # The deadline of the cleanup was never reset.
    assert session._cleanup_deadline_for() == deadline
    assert second['cleanup_deadline'] == deadline

    # A recovery that arrives after the deadline keeps the resources of
    # the round with their owner.
    session, holder, clock = make_session(
        tmp_path, close_facts=dict(COMPLETE_CLOSE_FACTS,
                                   process_handle_released=False))
    session.start()
    peer = holder['peer']
    session.stop()
    clock.value += 1000.0
    session.stop()
    assert session.broker is peer
    assert 'CUSTODY_CLOSE_RECOVERY_EXPIRED' in session.evidence()['failures']


# -- N05-R20: the closed fact is committed when it is confirmed ----------

def test_n05_r20_the_closed_fact_is_committed_only_when_it_is_confirmed():
    """N05-R20 (M09): a close is committed when it really happened.

    Obligation: the fact that an endpoint is closed is committed only
    when the close was confirmed, a failed close is recoverable and the
    close of an endpoint that is closed stays idempotent.  Entry:
    ``_WindowsPipeEndpoint.close`` and ``_PosixPipeEndpoint.close``.
    Trigger: the close of the file of the endpoint fails.  Oracle: the
    endpoint may try the close again and the fact becomes true when it
    is confirmed.  Negative: a proven close is never turned into a
    missing one and the descriptor is never closed twice.  Returned
    state: the facts of the close name the failure.  Salvage: the owner
    of the endpoint closes it later.
    """
    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            pass

    class BrokenFile:
        def __init__(self):
            self.attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise OSError('close_failed')

    clock = ManualClock(1000.0)
    # The endpoint is built with its **real** constructor and with the
    # injected primitives of the round: the fixture never bypasses the
    # constructor and every invariant of the endpoint is really
    # initialised.
    endpoint = _WindowsPipeEndpoint(file_object=BrokenFile(),
                                    name='inprocess', api=Api(),
                                    clock=clock, handle=702)
    facts = endpoint.close()
    # The close was not confirmed: the fact is not committed and the
    # endpoint may try it again.
    assert facts['closed'] is False
    assert facts['error_type'] == 'OSError'
    assert endpoint._closed is False
    facts = endpoint.close()
    assert facts['closed'] is True
    assert endpoint._closed is True
    # A close of an endpoint that is closed is idempotent and it keeps
    # the fact that it is closed.
    again = endpoint.close()
    assert again['closed'] is True
    assert again['already_closed'] is True
    assert endpoint._file.attempts == 2, 'the file was closed a third time'


# -- N05-R21: the endpoint is the only owner of the files ----------------

def test_n05_r21_the_endpoint_is_the_only_owner_of_the_files_of_the_channel():
    """N05-R21 (M09): the broker never closes the files of the endpoint.

    Obligation: the endpoint is the only owner of the files of the
    channel and the broker process never closes them by itself.  Entry:
    ``BrokerProcess.close``.  Trigger: the read end of the channel
    could not be closed and a worker of the endpoint is still alive.
    Oracle: the broker process did not close the standard output and
    the standard input by itself.  Negative: a live worker keeps the
    file and the round stays unknown.  Returned state: the facts of the
    close name the end that is still open.  Salvage: the owner of the
    channel closes it later.
    """
    closed = []

    class Channel:
        reader_finished = False

        def __init__(self):
            self.closes = 0

        def bind_deadline(self, deadline):
            self.deadline = deadline

        def close(self):
            self.closes += 1
            return {'write_end_closed': True, 'read_end_closed': False,
                    'reader_finished': False, 'reader_error': None,
                    'write_retained_workers': 0, 'read_retained_workers': 1,
                    'worker_thread_handle_released': False}

    class Process:
        pid = 1
        returncode = None

        def __init__(self):
            self.stdin = type('S', (), {'close': lambda self: closed.append('stdin')})()
            self.stdout = type('S', (), {'close': lambda self: closed.append('stdout')})()

        def wait(self, timeout=None):
            raise TimeoutError('still running')

        def terminate(self):
            closed.append('terminate')

    channel = Channel()
    broker = BrokerProcess(Process(), 'x', 'a' * 64, channel)
    broker.write_deadline = 1005.0
    facts = broker.close()
    # The endpoint is the only owner of the files: the broker process
    # never closed the standard input and the standard output by
    # itself.
    assert 'stdin' not in closed
    assert 'stdout' not in closed
    assert facts['channel_closed'] is True
    assert facts['read_end_closed'] is False
    assert facts['stdout_closed'] is False
    assert facts['channel_retained_workers'] == 1
    assert facts['worker_thread_handle_released'] is False
    assert facts['process_exited'] is False
    # The channel was closed by its owner and the end that is still
    # open keeps its owner.
    assert channel.closes == 1


# -- N05-R22: the strict facts of the close -----------------------------

def test_n05_r22_the_strict_facts_of_the_close_are_required(tmp_path):
    """N05-R22 (M09): three facts are not a release.

    Obligation: the parent refuses a close that does not report the
    facts of the reader, of the endpoints and of the workers.  Entry:
    ``NativeCustodySession._perform_close``.  Trigger: the close of the
    peer reports the three old facts only.  Oracle: the original broker
    is kept and the missing facts are named.  Negative: a close that
    reports every fact releases the broker.  Returned state: the round
    is unknown and the broker is retained.  Salvage: the public stop of
    the round coordinates the peer again.
    """
    session, holder, _clock = make_session(
        tmp_path, close_facts={'channel_closed': True, 'process_exited': True,
                               'process_handle_released': True})
    session.start()
    peer = holder['peer']
    evidence = session.stop()
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    assert session.broker is peer
    assert evidence['broker_retained'] is True
    failures = [failure for failure in evidence['failures']
                if failure.startswith('CUSTODY_BROKER_CLOSE_INCOMPLETE')]
    assert failures, 'the missing facts were not named'
    # The facts that the parent requires are named in the evidence.
    required = evidence['broker_close_facts_required']
    for key in ('channel_reader_finished', 'read_end_closed',
                'write_end_closed', 'worker_thread_handle_released'):
        assert key in required
    # A close that reports every fact releases the broker.
    session, holder, _clock = make_session(
        tmp_path, close_facts=dict(COMPLETE_CLOSE_FACTS))
    session.start()
    evidence = session.stop()
    assert session.broker is None
    assert evidence['broker_retained'] is False


# -- N05-R23: the end of the attempt and the end of the closer ----------

def test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts(tmp_path):
    """N05-R23 (M09): the attempt and the thread are two facts.

    Obligation: the end of the attempt of the close and the end of the
    thread that performs it are two different facts.  Entry:
    ``NativeCustodySession._await_close`` and
    ``NativeCustodySession._closer_main``.  Trigger: the closer is
    still alive when the attempt of the close ended.  Oracle: the
    waiter waits for the closer inside the same deadline and the
    evidence carries both facts.  Negative: the round never joins
    itself and never forms a cycle of waits.  Returned state: the
    closer that is still alive is named.  Salvage: the closer ends and
    the round is closed.
    """
    session, holder, clock = make_session(tmp_path, clock=ManualClock(1000.0))
    session.start()
    entered = threading.Event()
    release = threading.Event()
    original_finish = session._finish_close

    def slow_finish():
        # The end of the attempt is published and the closer stays
        # alive for a while.
        original_finish()
        entered.set()
        release.wait(5.0)

    session._finish_close = slow_finish
    try:
        assert session._start_bounded_close() is True
        assert entered.wait(5.0), 'the closer never ended its attempt'
        evidence = session.evidence()
        assert evidence['close_finished'] is True
        assert evidence['closer_alive'] is True
        assert evidence['closer_exited'] is False
        # The waiter waits for the closer inside the same deadline and it
        # never forms a cycle of waits.
        outcome = {}

        def waiter():
            outcome['result'] = session._await_close()

        thread = threading.Thread(target=waiter)
        thread.start()
        thread.join(0.2)
        assert thread.is_alive(), 'the waiter returned before the closer ended'
        # The deadline of the cleanup arrives while the closer is alive.
        clock.value += 100.0
        thread.join(5.0)
        assert not thread.is_alive()
        assert outcome.get('result') is False
        assert 'CUSTODY_CLOSER_NOT_FINISHED' in session.evidence()['failures']
        assert session.evidence()['state'] == 'UNKNOWN_RETAINED'
        # The closer is still named by the round: it keeps its owner.
        assert session.evidence()['closer_alive'] is True
    finally:
        # The salvage of the test owner: the closer ends and it is
        # joined.  The salvage never changes the fact of the product
        # above.
        release.set()
        closer = session._closer
        if closer is not None:
            closer.join(5.0)

    # -- the waiter that arrives before the end of the attempt -------------
    session, holder, clock = make_session(tmp_path, clock=ManualClock(1000.0))
    session.start()
    entered = threading.Event()
    release = threading.Event()
    original_finish = session._finish_close

    def slow_attempt():
        # The attempt of the close is still in flight and the closer
        # stays alive inside it.
        entered.set()
        release.wait(5.0)
        original_finish()

    session._finish_close = slow_attempt
    try:
        assert session._start_bounded_close() is True
        assert entered.wait(5.0), 'the closer never began its attempt'
        outcome = {}

        def waiter():
            outcome['result'] = session._await_close()

        thread = threading.Thread(target=waiter)
        thread.start()
        thread.join(0.2)
        assert thread.is_alive(), 'the waiter returned before the attempt ended'
        # The attempt ends: the waiter still waits for the **real** exit
        # of the closer and it confirms it.
        release.set()
        thread.join(5.0)
        assert not thread.is_alive()
        assert outcome.get('result') is True
        assert not session._closer.is_alive()
        assert session.evidence()['closer_exited'] is True
    finally:
        release.set()
        closer = session._closer
        if closer is not None:
            closer.join(5.0)

    # -- the close of the calling thread has no closer of its own ----------
    session, holder, clock = make_session(tmp_path, clock=ManualClock(1000.0))
    session.start()
    # The close is performed by the calling thread itself: there is no
    # closer thread and no cleanup in flight, so the confirmation is
    # immediate.
    assert session._close_broker() == 'PERFORMED'
    assert session._closer is None
    assert session._await_close() is True


# -- N05-R24: the closed items and the frozen groups are kept ------------

def test_n05_r24_the_closed_items_and_the_frozen_groups_are_kept(tmp_path):
    """N05-R24 (compatibility): the closed items did not regress.

    Obligation: the closed items of the earlier rounds still hold, the
    frozen groups of the package are still there and the native claims
    stay ``NOT_PROVEN``.  Entry: the validators of the plan, the
    declarations of the Windows primitives and the command of the
    sampler.  Trigger: the closed refusals are driven one after the
    other.  Oracle: every refusal still happens and the positive cases
    are not migrated.  Negative: a plan with an extra key is still
    refused.  Returned state: the refusals carry their own codes.
    Salvage: nothing was created.
    """
    import tools.test_v0_s3_native_custody_regressions as regressions

    # The sixteen frozen groups of the correction 03 are still there.
    frozen = [name for name in dir(regressions)
              if name.startswith('test_n03_r')]
    assert len(frozen) == 16, 'a frozen group of the package was lost'

    # M01: the closed key set of the plan.
    document = plan_document()
    document['extra'] = 'x'
    with pytest.raises(CustodyError) as info:
        validate_launch_plan(document)
    assert info.value.code == 'CUSTODY_PLAN_KEY_SET_INVALID'

    # M04: the job query is unknown when a fact does not agree.
    def refuse_query(kernel32, *args):
        return 0

    kernel32 = SyntheticKernel32(script={'QueryInformationJobObject': refuse_query})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.job_process_ids(0x99)
    assert info.value.code == 'BROKER_JOB_QUERY_UNKNOWN'

    # M10: the sampler receives the private pids as separate arguments.
    role = {'role': 'SAMPLER',
            'tools': [{'path': 'C:/ComfyUI-aki-v2/python/python.exe', 'sha256': 'c' * 64},
                      {'path': 'C:/lvw/tools/v0_s2_native_sampler.py', 'sha256': '1' * 64}],
            'data': {'nvidia_exe': 'C:/Windows/System32/nvidia-smi.exe',
                     'nvidia_sha256': '2' * 64, 'max_seconds': 600},
            'log': 'temp/native/sampler.log'}
    arguments = role_command(role, '/tmp/none', [4001, 4002])['arguments']
    index = arguments.index('--private-pids')
    assert arguments[index + 1] == '4001'
    assert arguments[index + 2] == '4002'

    # M11: the default launcher refuses with its own code.
    from tools.v0_s3_native_broker import launch_broker
    if os.name != 'nt':
        with pytest.raises(BrokerError) as info:
            launch_broker(None, '/tmp/never', 'a' * 32)
        assert info.value.code == 'BROKER_PLATFORM_UNSUPPORTED'

    # The native claims of the package are not proven.
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    evidence = core.stop('STOP')
    assert evidence['native_execution_proven'] is False
    assert evidence['native_cleanup_proven'] is False
    assert evidence['stage_pass_claim'] is False
    assert evidence['product_gate0'] is False
    assert evidence['grant_authority'] == 'NOT_VERIFIED'
    assert not win32.live
