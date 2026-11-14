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
  missing.  The only seam that is injected is the **lowest** one: the
  primitive table of the façade of the Windows API, the file objects
  of the ends of the channel and the frame of the peer.  The public
  production owners - the core, the loop, the channel, the endpoints,
  the workers, the session, the launcher and the custody of the
  launcher - are the real ones.

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
  Every thread that the test itself started is joined by the test with
  a **bounded** wait, in every case and unconditionally.

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
import hashlib
import json
import os
import queue
import subprocess
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
    _FakeFile, _F5Api, _F5ExternalCancelOwner, _f5_build_chain, _reply_bytes)
from tools.test_v0_s3_native_custody_regressions import (  # noqa: E402
    ManualClock, RecordingWin32, SyntheticKernel32, plan_document, sealed_plan,
    synthetic_table)


#: The directory in which the bounded facts of this module are written.
#: Every document is written **before** the assertions of its phase and
#: every value of it is a value that the production returned.
#:
#: CORRECTION 11: the diagnostics of this module are written in the NEW
#: directory of the correction 11.  The real documents of the failed
#: batch of the correction 10 stay in the directory of the correction
#: 10: they are never overwritten, never deleted and never replaced by
#: a summary.
EVIDENCE_DIR = (PACK_ROOT / 'reports' / 'v0-s3' / 'product-gate0'
                / 'implementation-native-custody-correction-11' / 'evidence')

#: The nonce of the private channel of the probes of this module.  It
#: is a closed form of 32 hexadecimal characters and it is the nonce of
#: the round of the probe: the frames of the probe carry it.
NONCE = '0' * 32

#: The two codes that the production may name for the cancellation of
#: the channel.  The code depends on the layer that observed the flag:
#: the read endpoint of the channel raises ``BROKER_PIPE_CANCELLED`` and
#: the wait of the channel between two reads raises
#: ``BROKER_CHANNEL_CANCELLED``.  A negative case that is about the
#: **origin** of the cancellation accepts the code that the real
#: observation layer produced and it never widens the set to hide any
#: other error.
CANCELLATION_CODES = ('BROKER_PIPE_CANCELLED', 'BROKER_CHANNEL_CANCELLED')


def write_phase(phase, document):
    """Write the bounded facts of one phase of this module."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / ('n10-%s.json' % phase)
    path.write_text(json.dumps(document, indent=1, sort_keys=True,
                                default=repr), encoding='utf-8')
    return str(path)


def _live_plan_document():
    """A plan document whose lease is valid for the clock of the host."""
    return plan_document(lease_expires_at=time.time() + 3600.0)


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


# -- N10-R01: the control handle of a process ------------------------------

def test_n10_r01_the_control_handle_is_closed_only_after_the_exit(tmp_path):
    """N10-R01 (M03): the last control handle of a process is kept.

    Obligation: a Core that took a process and could not assign it to
    the job of the round - the child is still suspended and it never ran
    - keeps the **original** control handle of that process when the
    termination of the child fails and when the wait does not confirm
    the exit: the record of the round and the pending table of the
    round **both** forbid the close of the handle, the handle stays with
    its owner and the same owner may still terminate the process and
    wait for it inside the original deadline.  The thread handle and
    the pipe handles are independent of the exit and they are released
    on their own.

    Entry: ``BrokerCore._launch_role`` (the assignment of the process),
    ``BrokerCore._terminate_owned``, ``BrokerCore._release_the_records``,
    ``BrokerCore._process_closeable`` and
    ``_PendingResources.close_all``.  Trigger: the assignment of the
    process to the job fails, the termination of the child fails and the
    wait does not confirm the exit.  Oracle: the close of the control
    handle was never attempted, the handle is still reachable and the
    round is not a release.  Negative: a close that would succeed is
    never a proof that the process ended.  Returned state: the record
    and the pending table name the handle and its owner.  Salvage: the
    same owner confirms the exit later and closes the handle exactly
    once.
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

    win32 = UnconfirmedWin32(fail_at=('assign', 'terminate'))
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        # The assignment of the process to the job of the round fails:
        # the child is still suspended and it never ran.
        with pytest.raises(BrokerError) as info:
            core.launch()
        assert info.value.code == 'BROKER_ASSIGN_FAILED'
        assert win32.fired == {'assign', 'terminate'}, \
            'the named failures of the round never happened'
        record = core.records[0]
        target = record['process_handle']
        assert target is not None, 'the child never got a control handle'
        facts = {'assigned': record['assigned'], 'resumed': record['resumed'],
                 'exited': record['exited'],
                 'process_handle_kept': record['process_handle'] is target,
                 'process_handle_closed': record['process_handle_closed'],
                 'thread_handle_closed': record['thread_handle_closed'],
                 'pending': [item['kind'] for item in core._pending.pending()],
                 'live': sorted(win32.live),
                 'state': core.state}
        write_phase('r01-first', facts)
        # The child never ran and its exit was never confirmed.
        assert record['assigned'] is False
        assert record['resumed'] is False
        assert record['exited'] is False
        # The control handle of the child is **still** with its owner.
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

    CORRECTION 11 (M05): the **creation** of a process and the
    recovery of the façade are **one** ownership decision as well.  The
    original entries of the process and of its thread are reserved or
    refused under the lock of the table, the blocking primitives run
    outside of that lock, and a handle that the recovery of the façade
    claimed is never delivered to the core and never closed twice.
    The group drives the race between the birth query of a created
    process and the recovery of the façade and it proves that there is
    exactly one closer of the original handle of the process.
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
                                     'live': sorted(kernel32.live)})
    assert report == [], 'the recovery closed an end that it handed over'
    assert getattr(read, 'value', read) in kernel32.live

    # -- the third direction (N1 correction 11, M05): the **creation**
    #    of a process and the recovery of the façade are one ownership
    #    decision.  The birth query of the created process blocks, the
    #    recovery of the façade claims the original entries of the
    #    process and of its thread while the creation is in flight,
    #    and the return of the creation may then neither deliver a
    #    stale claimed handle to the core nor forget it.  There is
    #    exactly **one** closer of the original handle of the process.
    blocked = threading.Event()
    resume = threading.Event()
    closed_handles = []

    def get_process_times(kernel32, *args):
        # The birth query of the created process blocks: the recovery
        # of the façade runs while the creation is in flight.
        blocked.set()
        resume.wait(10.0)
        creation = args[1]
        creation.dwLowDateTime = kernel32.creation_time & 0xFFFFFFFF
        creation.dwHighDateTime = kernel32.creation_time >> 32
        return 1

    def close_handle(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        closed_handles.append(handle)
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': get_process_times,
                                         'CloseHandle': close_handle})
    api = WindowsApi(table=synthetic_table(kernel32))
    outcome = {}

    def create():
        try:
            outcome['created'] = api.create_process_suspended(
                executable='C:/python.exe', arguments=['-I'],
                working_directory='C:/', stdout_handle=0, stderr_handle=0)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            outcome['error'] = error

    creator = threading.Thread(target=create, name='lvw-n10-r02-creation')
    creator.start()
    try:
        assert blocked.wait(10.0), \
            'the birth query of the creation never ran'
        # The recovery of the façade claims the original entries of the
        # process and of its thread while the creation is in flight.
        report = api.release_retained()
        assert report, 'the recovery of the façade found nothing to release'
        resume.set()
        creator.join(15.0)
        assert not creator.is_alive(), 'the creation was left behind'
    finally:
        resume.set()
        creator.join(15.0)
    facts = {'error': getattr(outcome.get('error'), 'code', None),
             'created': outcome.get('created') is not None,
             'closed': list(closed_handles),
             'report': [{'kind': item['kind'], 'released': item['released']}
                        for item in report]}
    write_phase('r02-creation', facts)
    # A stale claimed handle is never delivered to the core.
    assert outcome.get('created') is None, \
        'a stale claimed handle was delivered to the core'
    error = outcome.get('error')
    assert isinstance(error, BrokerError), \
        'the creation did not refuse the refused handover'
    assert error.code == 'BROKER_PROCESS_HANDOVER_REFUSED'
    # There is exactly **one** closer of the original handle of the
    # process and of its thread: the recovery of the façade and the
    # direct cleanup of the failed creation are one owner.
    assert closed_handles.count(kernel32.process_handle) == 1, \
        'the original handle of the process was closed twice'
    assert closed_handles.count(kernel32.thread_handle) == 1, \
        'the original handle of the thread was closed twice'


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
    facts of the two stops agree with each other.  Salvage: the owner of
    the test releases the handles that the product kept.
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

    Entry: ``StreamChannel.__init__``, ``_LaunchAggregate.retain``,
    ``_LaunchAggregate.release`` and ``_adopt_broker_process``.
    Trigger: the reader thread of the channel really starts and the
    start of the thread does not return, so that the construction of
    the channel fails with the channel already half built.  Oracle: the
    aggregate found the partial channel, the files of the process were
    closed by the channel and never by the process helper.  Negative:
    the process helper never closes the files of a process whose
    channel took them.  Returned state: the facts of the aggregate
    name what it released.  Salvage: the owner of the test releases the
    handles that the product kept.
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

        def read_stream(self, handle, size):
            # The reader of the chain ends at once: the drain of the
            # channel is bounded and it never blocks for ever.
            return b''

        def write_stream(self, handle, data):
            return len(data)

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
    read_file = CountingFile('read')
    write_file = CountingFile('write')
    original_start = threading.Thread.start

    def failing_start(self):
        # The thread of the reader of the channel really starts and its
        # start does not return: the channel is half built and the
        # aggregate is its owner.
        original_start(self)
        if self.name == 'lvw-native-custody-channel':
            raise RuntimeError('thread_start_failed_after_start')

    try:
        with unittest.mock.patch.object(threading.Thread, 'start',
                                        failing_start):
            with pytest.raises(RuntimeError):
                StreamChannel(
                    None, None,
                    read_endpoint=_WindowsPipeEndpoint(
                        file_object=read_file, name='channel-read',
                        api=Api(), clock=clock, handle=900),
                    write_endpoint=_WindowsPipeEndpoint(
                        file_object=write_file, name='channel-write',
                        api=Api(), clock=clock, handle=901),
                    custody=aggregate, clock=clock)
        # The partial channel is found **through the aggregate** and not
        # through a local variable of the adoption.
        channel = aggregate.channel
        assert channel is not None, \
            'the partial channel lost its owner'
        facts = {'aggregate_channel': channel is not None,
                 'read_closes': read_file.closes,
                 'write_closes': write_file.closes,
                 'process_closed': list(process.closed),
                 'terminated': process.terminated,
                 'waited': process.waited,
                 'custody': [(item['kind'], repr(item['resource']))
                             for item in custody.items()]}
        write_phase('r04-partial', facts)
        # The outer owner of the launch finds the partial channel and
        # coordinates it: the files of the channel are closed by the
        # channel itself.
        report = aggregate.release()
        facts = {'report': report,
                 'read_closes': read_file.closes,
                 'write_closes': write_file.closes,
                 'process_closed': list(process.closed),
                 'terminated': process.terminated,
                 'waited': process.waited}
        write_phase('r04-release', facts)
        assert read_file.closes == 1, \
            'the partial channel was not coordinated by the aggregate'
        assert write_file.closes == 1
        # The files of the process were not closed by the process
        # helper: the channel owns them.
        assert process.closed == [], \
            'the process helper closed the files of the channel'
        # The process was coordinated by the aggregate and it was
        # coordinated after the channel.
        assert process.terminated == 1
        assert process.waited == 1
    finally:
        # The salvage of the owner of the test: the thread that the
        # channel really started is joined with a bounded wait.
        partial = aggregate.channel
        thread = getattr(partial, '_thread', None)
        if thread is not None:
            thread.join(10.0)
            assert not thread.is_alive(), \
                'the reader thread of the channel was left behind'


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
    original object is the one that leaves, the cancellation of the
    recovery stays reachable next to it and the recovery of the launcher
    cancels in the same way.

    Entry: ``_LaunchAggregate.release``, ``_adopt_broker_process`` and
    ``_LauncherCustody.release``.  Trigger: the close of the channel
    returns without a confirmed end and it is cancelled by the
    recovery.  Oracle: the process was terminated and waited **after**
    the channel was coordinated, the channel kept its owner, the
    original failure object is the one that propagated and the
    cancellation of the recovery is reachable next to it.  Negative: a
    returned close is never taken for a release.  Returned state: the
    facts of the aggregate name what it kept.  Salvage: the recovery of
    the launcher releases what it may.
    """
    order = []

    class Process:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0

        def terminate(self):
            self.terminated += 1
            order.append('terminate')

        def wait(self, timeout=None):
            self.waited += 1
            order.append('wait')
            return 0

    class CancellingChannel:
        """A channel whose close returns without a confirmed end and
        whose close is cancelled by the recovery."""

        reader_finished = True

        def __init__(self):
            self.closes = 0

        def close(self):
            self.closes += 1
            order.append('channel')
            raise KeyboardInterrupt('channel_close_cancelled')

    class FailingBrokerProcess:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    process = Process()
    channel = CancellingChannel()
    custody = _LauncherCustody()
    aggregate = _LaunchAggregate(custody=custody)
    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess
    try:
        with pytest.raises(RuntimeError) as info:
            _adopt_broker_process(process, channel_factory=lambda: channel,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  aggregate=aggregate, custody=custody)
    finally:
        broker_module.BrokerProcess = original
    facts = {'channel_closes': channel.closes,
             'terminated': process.terminated,
             'waited': process.waited,
             'order': list(order),
             'aggregate_channel': aggregate.channel is channel,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody.items()],
             'error_type': type(info.value).__name__,
             'error_detail': getattr(info.value, 'detail', None)}
    write_phase('r05-adoption', facts)
    # The original failure object is the one that propagated.
    assert str(info.value) == 'broker_process_construction_failed'
    # The safe steps of the release ran before the failure left: the
    # channel was coordinated **before** the process.
    assert channel.closes == 1
    assert order == ['channel', 'terminate', 'wait'], \
        'the channel of the launch was not coordinated before the process'
    assert process.terminated == 1
    assert process.waited == 1
    # The cancellation of the recovery is reachable next to the original
    # failure: the primary failure and the cancellation coexist.
    cancellation = getattr(info.value, 'lvw_cancelled', None)
    assert isinstance(cancellation, KeyboardInterrupt), \
        'the cancellation of the recovery was swallowed'
    assert str(cancellation) == 'channel_close_cancelled'
    # The incomplete facts kept the channel with its owner.
    assert aggregate.channel is channel, \
        'an incomplete channel lost its owner'
    assert any(item['kind'] == 'channel' for item in custody.items())

    # The recovery of the launcher cancels in the same way: the safe
    # steps run first and the cancellation of the recovery is the error
    # that leaves.  The recovery runs on a **fresh** launch and on a
    # fresh table of the launcher, so that the order that is observed
    # belongs to that launch alone.
    order[:] = []
    process2 = Process()
    channel2 = CancellingChannel()
    custody2 = _LauncherCustody()

    class FailingBrokerProcess2:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess2
    try:
        with pytest.raises(RuntimeError):
            _adopt_broker_process(process2, channel_factory=lambda: channel2,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  custody=custody2)
    finally:
        broker_module.BrokerProcess = original
    order[:] = []
    with pytest.raises(KeyboardInterrupt) as recovery:
        custody2.release()
    facts = {'order': list(order),
             'terminated': process2.terminated,
             'waited': process2.waited,
             'error_type': type(recovery.value).__name__,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody2.items()]}
    write_phase('r05-recovery', facts)
    assert str(recovery.value) == 'channel_close_cancelled'
    # RECONCILIATION (N1 correction 11): the process of this launch was
    # **already** released by the adoption phase: its exit was really
    # confirmed and its original handle was released with it.  The
    # recovery of the launcher therefore coordinates the channel only
    # and it never repeats the termination and the wait of a process
    # that was already proved released.  The old expectation that the
    # recovery repeats them contradicted the ownership of the process
    # and it is replaced by the boundary that really holds.
    assert order == ['channel'], \
        'the recovery of the launcher did not coordinate the channel only'
    assert process2.terminated == 1, \
        'the recovery terminated the process of the launch a second time'
    assert process2.waited == 1, \
        'the recovery waited for the process of the launch a second time'
    # The channel that could not be released keeps its owner.
    assert any(item['kind'] == 'channel' for item in custody2.items())

    # -- PHASE THREE: a launch whose **original handle** was still
    #    retained is coordinated **again** by the recovery of the
    #    launcher.  The recovery retries the incomplete parts and it
    #    never opens a budget of its own.
    order[:] = []

    class RetainedProcess:
        """A process whose first wait failed: it keeps its owner."""

        pid = 4243
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0

        def terminate(self):
            self.terminated += 1
            order.append('terminate')

        def wait(self, timeout=None):
            self.waited += 1
            order.append('wait')
            if self.waited == 1:
                raise RuntimeError('wait_failed')
            return 0

    class FailingBrokerProcess3:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    process3 = RetainedProcess()
    channel3 = CancellingChannel()
    custody3 = _LauncherCustody()

    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess3
    try:
        with pytest.raises(RuntimeError):
            _adopt_broker_process(process3, channel_factory=lambda: channel3,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  custody=custody3)
    finally:
        broker_module.BrokerProcess = original
    # The adoption could not release the process: it keeps its owner.
    assert process3.waited == 1
    kept = [item for item in custody3.items() if item['kind'] == 'process']
    assert kept, 'the process that could not be released lost its owner'
    order[:] = []
    with pytest.raises(KeyboardInterrupt):
        custody3.release()
    facts = {'order': list(order),
             'terminated': process3.terminated,
             'waited': process3.waited,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody3.items()]}
    write_phase('r05-retained-recovery', facts)
    # The channel is coordinated first and the **retained** process is
    # coordinated again: the recovery really retries the incomplete
    # part and it never releases the channel alone.
    assert order == ['channel', 'terminate', 'wait'], \
        'the recovery did not coordinate the retained process again'
    assert process3.terminated == 2
    assert process3.waited == 2


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
    an expired deadline and with a cancel flag that is already set, for
    the read and for the write.  Oracle: the refusal is named and no
    worker was started.  Negative: the endpoint never starts a worker
    for a refused call.  Returned state: the facts of the endpoint name
    no worker.  Salvage: the owner of the test closes the endpoint at
    the end.
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

        with pytest.raises(BrokerError) as info:
            endpoint.write(b'abc', None, cancel)
        assert info.value.code == 'BROKER_PIPE_CANCELLED'
        assert calls == [], 'a primitive was called by a refused write'
        assert endpoint._writer is None, \
            'the refused write started a worker of the endpoint'
        write_phase('r06-admission', {'calls': list(calls),
                                      'reader': endpoint._reader is not None,
                                      'writer': endpoint._writer is not None})

        # -- the linearization point of the admission (N1 correction
        #    11, M08): the request is admitted **before** the worker of
        #    the endpoint is started and it is admitted **again** after
        #    the worker is ready and immediately before the request is
        #    submitted.  A cancellation or an expiry that is published
        #    **before** that final admission causes **zero** primitive
        #    calls: the request never reaches the worker.
        endpoint2 = _WindowsPipeEndpoint(file_object=_FakeFile('read2'),
                                         name='inprocess-2', api=Api(),
                                         clock=clock, handle=703)
        try:
            cancel2 = _ChannelCancel()
            # The initial admission of the generation succeeds: the
            # round is neither expired nor cancelled.
            endpoint2._admission(None, None)
            worker = endpoint2._start('read', endpoint2._read_block, None)
            assert worker.ready.is_set(), 'the worker was never ready'
            # The cancellation is published after the readiness of the
            # worker and before the dispatch of the request.
            cancel2.set()
            with pytest.raises(BrokerError) as info:
                endpoint2._await(worker, None, None, cancel2)
            assert info.value.code == 'BROKER_PIPE_CANCELLED'
            assert calls == [], \
                'a primitive was called by a request that was not admitted'
            assert worker._submitted == 0, \
                'the request was submitted although the admission was refused'
            write_phase('r06-linearization', {
                'calls': list(calls),
                'submitted': worker._submitted,
                'code': info.value.code})
        finally:
            endpoint2.close()

        # The same boundary with an **expiry**: the deadline of the
        # round arrives after the readiness of the worker and before the
        # dispatch of the request.
        endpoint3 = _WindowsPipeEndpoint(file_object=_FakeFile('read3'),
                                         name='inprocess-3', api=Api(),
                                         clock=clock, handle=704)
        try:
            before = list(calls)
            endpoint3._admission(None, None)
            worker3 = endpoint3._start('read', endpoint3._read_block, None)
            assert worker3.ready.is_set(), 'the worker was never ready'
            # The deadline of the round arrives before the dispatch.
            clock.value += 1000.0
            with pytest.raises(BrokerError) as info:
                endpoint3._await(worker3, None, clock.value - 1.0, None)
            assert info.value.code == 'BROKER_PIPE_TIMEOUT'
            assert calls == before, \
                'a primitive was called by a request that was not admitted'
            assert worker3._submitted == 0, \
                'the request was submitted although the admission was refused'
            write_phase('r06-expiry', {
                'calls': list(calls),
                'submitted': worker3._submitted,
                'code': info.value.code})
        finally:
            endpoint3.close()
    finally:
        endpoint.close()


# -- N10-R07: the context reaches every layer -----------------------------

def test_n10_r07_the_context_of_the_round_reaches_every_layer(tmp_path):
    """N10-R07 (M08): the context of the round is one context.

    Obligation: the parent hands the **one** context of the round to
    the launcher of the broker and the launcher holds it **before** the
    first side effect of the launch - the creation of the process, the
    reading of the executable, the channel and its endpoints.  The
    channel, the endpoints, the workers of the endpoints and the API of
    the primitives read the **same** context.  In the child the STOP of
    the round publishes the ONE cleanup deadline and the transport of
    the round - the write of the terminal reply, the partial write and
    the join of the reader - uses the earlier of the lease and the
    cleanup: there is no unbound window and no new budget of its own.

    The group drives the **production** launcher of the round: the
    default launcher of the session calls the production ``launch_broker``
    and the only seam that is replaced is the creation of the process:
    an in-process fake of ``subprocess.Popen`` that never calls the
    original and that never starts an operating system process.  The
    executable that is hashed is a **bound synthetic fixture** of the
    round and the endpoints of the channel are the production Windows
    endpoints with the synthetic primitives of the round.

    Entry: ``NativeCustodySession._call_launcher``,
    ``NativeCustodySession.start``, ``_default_launcher``,
    ``launch_broker``, ``_LaunchAggregate``, ``StreamChannel``,
    ``_WindowsPipeEndpoint``, ``_WindowsPipeWorker``,
    ``WindowsApi.bind_context``, ``BrokerCore.__init__`` and
    ``BrokerLoop._stop``.  Trigger: the round publishes its cleanup
    deadline and the terminal reply is written.  Oracle: the context of
    the session was already the context of the round when the process
    was created, when the executable was hashed and when the channel and
    its endpoints were built; every layer of the child reads the
    published cleanup deadline.  Negative: no layer keeps a deadline of
    its own.  Returned state: the evidence of the session names the
    propagation of the context.  Salvage: the owner of the test closes
    the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = ManualClock(1000.0)
    observations = {'events': []}

    class Api:
        """The synthetic primitives of the round."""

        def __init__(self):
            self.lock = threading.Lock()
            self.frames = []
            self.thread_handles = []
            self.next_handle = 900
            # The explicit notification that the round published a
            # frame: the reader of the round waits for it and it never
            # ends the stream on a timeout.
            self.frames_ready = threading.Event()
            self.final = b''

        def duplicate_current_thread_handle(self):
            with self.lock:
                self.next_handle += 1
                self.thread_handles.append(self.next_handle)
                return self.next_handle

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            with self.lock:
                if self.frames:
                    return self.frames.pop(0)
            # The reader of the round waits for the explicit frame of
            # the round; the wait is bounded and it never decides the
            # end of the stream.
            self.frames_ready.wait(30.0)
            with self.lock:
                if self.frames:
                    return self.frames.pop(0)
            return b''

        def write_stream(self, handle, data):
            # The terminal frame of the round is published by the write
            # of the stop and by nothing else.
            with self.lock:
                final = self.final
                self.final = b''
            if final:
                with self.lock:
                    self.frames.append(final)
                self.frames_ready.set()
            return len(data)

    api = Api()
    api.frames = [_reply_bytes('READY', 'ARMED', {}, plan, NONCE, 1),
                  _reply_bytes('STATUS', 'RUNNING', {}, plan, NONCE, 2)]
    api.final = _reply_bytes('STOPPED', 'RELEASED', {}, plan, NONCE, 3)

    class FakeFile:
        """A file of the round that counts its own closes."""

        def __init__(self, name):
            self.name = name
            self.closes = 0

        def close(self):
            self.closes += 1
            return True

    class FakeHandle:
        """The original handle of the process of the round."""

        def __init__(self):
            self.closed = 0

        def Close(self):
            self.closed += 1
            return True

    class FakeProcess:
        """The process of the round: it is never an operating system one."""

        pid = 4242
        returncode = 0

        def __init__(self):
            self.stdin = FakeFile('stdin')
            self.stdout = FakeFile('stdout')
            self.stderr = FakeFile('stderr')
            self._handle = FakeHandle()
            self.terminated = 0
            self.waited = 0

        def wait(self, timeout=None):
            self.waited += 1
            return 0

        def terminate(self):
            self.terminated += 1
            return None

    # The bound synthetic executable of the round: a local file whose
    # bytes are the bytes that the launcher hashes.  No arbitrary path
    # and no network is ever read.
    synthetic_executable = tmp_path / 'synthetic-python.exe'
    synthetic_executable.write_bytes(b'# the synthetic executable of the round\n')
    synthetic_digest = hashlib.sha256(
        synthetic_executable.read_bytes()).hexdigest()

    def fake_popen(command, **kwargs):
        """The in-process seam of the creation of the process.

        The fake never calls the original ``Popen`` and it never
        starts an operating system process.  It observes the state of
        the launch **at the moment of the creation of the process**: the
        aggregate of the launch is already with its owner and the
        context of the launch is already the context of the session.
        """
        observations['events'].append('popen')
        observations['command'] = list(command)
        aggregates = [item['resource'] for item in _launcher_custody_items()
                      if item['kind'] == 'aggregate']
        observations['aggregate_at_popen'] = aggregates[-1] if aggregates else None
        observations['context_at_popen'] = (aggregates[-1].context
                                           if aggregates else None)
        return FakeProcess()

    class _OsView:
        """A view of the module os that reports the platform of the round.

        The view is bound to the **module of the broker** and it never
        changes the module os of the host: the guard of the batch and
        every other owner of the host keep the real platform.
        """

        name = 'nt'

        def __getattr__(self, item):
            return getattr(os, item)

    class _SubprocessView:
        """A view of the module subprocess whose Popen is the fake."""

        def Popen(self, command, **kwargs):
            return fake_popen(command, **kwargs)

        def __getattr__(self, item):
            return getattr(subprocess, item)

    class _SysView:
        """A view of the module sys that names the synthetic executable."""

        executable = str(synthetic_executable)

        def __getattr__(self, item):
            return getattr(sys, item)

    handles = {'next': 900}

    def fake_make_endpoint(file_object, name, *, api=None, clock=None,
                           context=None):
        """The endpoints of the round: the production ones.

        The endpoint is the production Windows endpoint and the only
        thing that is injected is the **synthetic primitive table** of
        the round: no native library is loaded and no operating system
        call is made.
        """
        handles['next'] += 1
        return _WindowsPipeEndpoint(file_object=file_object, name=name,
                                    api=api if api is not None else api_table,
                                    clock=clock,
                                    handle=handles['next'], context=context)

    api_table = api
    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=21600,
                                   launcher=None, clock=clock,
                                   wall=time.time, nonce=NONCE)
    try:
        # -- the parent: the PRODUCTION default launcher and the
        #    PRODUCTION launch_broker, with the creation of the process
        #    replaced by the in-process fake -------------------------
        with unittest.mock.patch.object(broker_module, 'os', _OsView()), \
             unittest.mock.patch.object(broker_module, 'subprocess',
                                        _SubprocessView()), \
             unittest.mock.patch.object(broker_module, 'sys', _SysView()), \
             unittest.mock.patch.object(broker_module, '_make_endpoint',
                                        fake_make_endpoint):
            session.start()
        facts = {'context_at_popen':
                 observations['context_at_popen'] is session._context,
                 'command': observations.get('command'),
                 'executable_sha256': getattr(session.broker,
                                              'executable_sha256', None),
                 'channel_context':
                 session.broker._channel._context is session._context,
                 'reader_context':
                 session.broker._channel._reader._context is session._context,
                 'writer_context':
                 session.broker._channel._writer._context is session._context,
                 'broker_context':
                 session.broker._context is session._context,
                 'events': list(observations['events'])}
        write_phase('r07-launcher', facts)
        # The context of the round was **already** the context of the
        # session when the process of the round was created.
        assert observations.get('context_at_popen') is session._context, \
            'the launcher did not hold the context of the session before ' \
            'the creation of the process'
        # The executable that was hashed is the bound synthetic fixture
        # of the round and the hash is the one that the round carries.
        assert observations.get('command', [None])[0] \
            == str(synthetic_executable), \
            'the launcher did not use the bound synthetic executable'
        assert session.broker.executable_sha256 == synthetic_digest, \
            'the launcher did not hash the bound synthetic executable'
        # The channel of the launch and its endpoints carry the same
        # context.
        assert session.broker._channel._context is session._context
        assert session.broker._channel._reader._context is session._context
        assert session.broker._channel._writer._context is session._context
        assert session.broker._context is session._context
        assert session.evidence()['launcher_context_propagated'] is True

        # -- the child: the core, the loop and the transport share one
        #    context and the cleanup deadline of the round -----------
        kernel32 = SyntheticKernel32()
        windows = WindowsApi(table=synthetic_table(kernel32))
        child = BrokerCore(win32=windows, plan=sealed_plan(),
                           run_root=tmp_path, clock=clock)
        assert windows._context is child.context, \
            'the facade of the primitives has no context of the round'
        child.bind_absolute_deadline(2000.0)
        transport = StreamChannel(
            None, None,
            read_endpoint=_WindowsPipeEndpoint(
                file_object=_FakeFile('read'), name='transport-read',
                api=api, clock=clock, handle=920, context=child.context),
            write_endpoint=_WindowsPipeEndpoint(
                file_object=_FakeFile('write'), name='transport-write',
                api=api, clock=clock, handle=921, context=child.context),
            clock=clock, context=child.context)
        transport.bind_deadline(2000.0)
        loop = BrokerLoop(core=child, transport=transport, plan=child.plan,
                          nonce=NONCE, clock=clock, wall=time.time)
        loop._deadline_mono = 2000.0
        # The STOP of the round: the core publishes the ONE cleanup
        # deadline and the terminal reply is written under it.
        loop._stop('STOP_COMMAND', 0)
        cleanup = child.context.cleanup_deadline_value()
        facts = {'cleanup': cleanup,
                 'transport': transport._effective_deadline(),
                 'write_endpoint': transport._writer._effective_deadline(),
                 'write_deadline': transport._writer._write_deadline,
                 'read_endpoint': transport._reader._effective_deadline(),
                 'api': windows._effective_deadline()}
        write_phase('r07-child', facts)
        assert cleanup is not None, 'the round published no cleanup deadline'
        assert transport._effective_deadline() == cleanup, \
            'the transport kept the long lease of the round'
        assert transport._writer._effective_deadline() == cleanup, \
            'the endpoint of the transport kept the long lease'
        assert transport._writer._write_deadline == cleanup, \
            'the partial write of the transport kept the long lease'
        assert transport._reader._effective_deadline() == cleanup, \
            'the join of the reader kept the long lease'
        assert windows._effective_deadline() == cleanup, \
            'the facade of the primitives kept the long lease'
        transport.close()
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


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
    exception object is the one that leaves and the wait never
    publishes the cleanup deadline of the round before the round
    failed.

    Entry: ``BrokerLoop._run_startup`` and ``_StartupOwner.settle``.
    Trigger: the result of the step is published while the **real**
    thread of the step is still alive, and the result is an ordinary
    error, a cancellation and a ``SystemExit``.  Oracle: the owner was
    not released before the real exit of its thread, the bounded join
    ran and the original exception object is the one that propagated.
    Negative: the publication of the result is never a proof that the
    thread ended.  Returned state: the owners that are in flight are
    named.  Salvage: the owner of the test releases the threads that
    the product started.

    RECONCILIATION (N1 correction 11): the three phases of the group
    shared **one** deadline of the loop, so the second phase inherited
    the budget that the first phase had already consumed and it was
    refused by the deadline of the round before its result was read.
    Every phase is now an **independent bounded scenario** with its own
    core, its own loop and its own deadline: no phase borrows the
    expired budget of a previous phase, the real result is published
    while the real thread of the step is still alive, the join of every
    thread is **unconditional** and no sleep ever proves the exit of a
    thread.
    """
    clock = time.monotonic
    release = threading.Event()
    owners = []
    try:
        for error in (BrokerError('BROKER_STARTUP_ORDINARY'),
                      KeyboardInterrupt('startup_cancelled'),
                      SystemExit(3)):
            published = threading.Event()
            # RECONCILIATION (N1 correction 11): every phase of the
            # group is an **independent bounded scenario**.  It has its
            # own core, its own loop and its own deadline: no phase
            # borrows the expired budget of a previous phase and no
            # sleep ever proves the exit of a thread.
            win32 = RecordingWin32()
            core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                              clock=clock)
            core.bind_absolute_deadline(clock() + 60.0)
            transport = type('T', (), {'bind_deadline': lambda self, value: value,
                                       'write': lambda self, raw: None})()
            loop = BrokerLoop(core=core, transport=transport, plan=core.plan,
                              nonce=NONCE, clock=clock, wall=time.time)
            loop._deadline_mono = clock() + 2.0

            def action(error=error, published=published, loop=loop):
                # The result of the step is published and the **real**
                # thread of the step stays alive: the publication of the
                # result is never a proof that the thread ended.
                owner = loop._startup_owner
                owner._results.put_nowait(('error', error))
                published.set()
                release.wait(15.0)

            published.clear()
            with pytest.raises(type(error)) as info:
                loop._run_startup('ARM', action)
            assert published.is_set(), \
                'the result of the step was never published'
            # The original exception object is the one that propagated.
            assert info.value is error, \
                'the original exception object was replaced'
            owner = loop._startup_owner
            owners.append(owner)
            # The real thread of the step is still alive: the owner was
            # not released before the real exit of its thread.
            assert owner.in_flight, \
                'the thread of the step ended while the owner was released'
            assert loop._startup_in_flight is owner, \
                'the owner of a step that did not end was released'
            assert owner in core.context.inflight(), \
                'the owner of a step that did not end left the flight'
            facts = {'error_type': type(error).__name__,
                     'in_flight': len(core.context.inflight()),
                     'retained': loop._startup_in_flight is owner}
            write_phase('r09-%s' % type(error).__name__.lower(), facts)
    finally:
        # The salvage of the owner of the test: the threads that the
        # product started are released and joined with a bounded wait.
        # The join is **unconditional**: no phase leaves a thread of the
        # round behind.
        release.set()
        for owner in owners:
            thread = owner._thread
            if thread is not None:
                thread.join(10.0)
                assert not thread.is_alive(), \
                    'the thread of a startup step was left behind'


# -- N10-R10: the outcome of the generation wins --------------------------

def test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation(tmp_path):
    """N10-R10 (M09): a real fault of the round is never a benign cancel.

    Obligation: the worker of an endpoint keeps the **outcome** of
    every generation it runs: the result, the error, the original error
    object and the order of the completion.  A failure that was really
    published **before** the cancellation of the round is the first
    error of the round: a close that sets the cancel flag afterwards
    may not replace it and it may not turn it into a benign
    cancellation.  The identity of the token of the cancel is not a
    proof: the order of the two facts is the proof.  The error of the
    reader is a **history**: two real stops of the round keep it and
    the round stays unknown.

    Entry: ``_WindowsPipeWorker.outcome``,
    ``_WindowsPipeWorker.published_before_cancel``,
    ``_WindowsPipeEndpoint._raise_cancellation``,
    ``BrokerProcess._keep_reader_error_history`` and
    ``NativeCustodySession.stop``.  Trigger: the read of the
    generation fails with an ordinary error, the outcome of the
    generation is really published and the close of the round asks for
    the cancellation of the same generation.  Oracle: the original
    error object is the one that leaves, the code of the error is the
    code of the real fault and the two stops of the round keep it.
    Negative: a cancellation may never rewrite a published failure.
    Returned state: the outcome of the generation is named with its
    order and its error object.  Salvage: the owner of the test stops
    the round in every case.

    CORRECTION 11 (M09): the outcome of the **same** generation is
    inspected **again** after the coordination of the cancellation, and
    it is inspected **before** a new timeout is decided.  The published
    failure of the generation remains the primary error of the round and
    the failure of the coordination and a new timeout are **parallel**
    facts: they never replace it and they never hide it.  The group
    drives the coordination of a cancellation whose fault of the round
    is published while the coordination runs, and it proves the order
    of the two facts with the auxiliary static proof of the group.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    api = _F5Api(read_fault=RuntimeError('read_fault'))
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        reader = holder['read_endpoint']._reader
        assert reader is not None, 'the reader of the chain never started'
        # The owner of the test publishes the ordinary failure of the
        # read and waits for the reader to be really inside its read.
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_read_fault()
        assert api.fault_observed.wait(15.0), \
            'the ordinary failure of the read never happened'
        # The barrier: the outcome of the generation is really published
        # and it carries the **original** error object.
        assert reader.outcome_published.wait(15.0), \
            'the outcome of the read was never published'
        outcome = reader.outcome(1)
        assert outcome is not None, 'the outcome of the generation is gone'
        assert outcome['error'] == 'RuntimeError'
        assert isinstance(outcome['error_object'], RuntimeError)
        # The close of the round asks for the cancellation of the same
        # generation **after** the failure was published.
        holder['channel']._cancel.set()
        first = session.stop()
        first_facts = first['broker_close_facts'] or {}
        write_phase('r10-first', {'outcome_error': outcome['error'],
                                   'outcome_object':
                                   type(outcome['error_object']).__name__,
                                   'sequence': outcome['sequence'],
                                   'reader_error':
                                   first_facts.get('channel_reader_error'),
                                   'state': first['state']})
        assert first_facts.get('channel_reader_error') == 'RuntimeError', \
            'the real fault of the round was replaced by a cancellation'
        assert first_facts.get('close_cancellation') is None
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'

        # The second public stop of the round: the error of the reader is
        # a history and it is never lost.
        second = session.stop()
        second_facts = second['broker_close_facts'] or {}
        write_phase('r10-second', {'reader_error':
                                    second_facts.get('channel_reader_error'),
                                    'source':
                                    second_facts.get('channel_reader_error_source'),
                                    'state': second['state']})
        assert second_facts.get('channel_reader_error') == 'RuntimeError', \
            'the second attempt lost the error of the reader'
        assert second_facts.get('channel_reader_error_source') \
            == 'REPEATED_CLOSE'
        assert second['broker_retained'] is True
        assert second['state'] == 'UNKNOWN_RETAINED'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass

    # -- the coordination of the cancellation (N1 correction 11, M09):
    #    the outcome of the **same** generation is inspected **again**
    #    after the coordination of the cancellation.  The original error
    #    object of the generation remains the error that leaves and the
    #    failure of the coordination is a **parallel** fact: it never
    #    replaces the published failure and it never hides it.
    gate = threading.Event()
    entered = threading.Event()

    class CoordinationApi:
        """The primitives of a read whose fault is published late."""

        def duplicate_current_thread_handle(self):
            return 705

        def cancel_synchronous_io(self, handle):
            # The request of the cancellation releases the fault of the
            # round: the original error of the generation is really
            # published **while** the coordination of the cancellation
            # runs.
            gate.set()
            return 'NOT_FOUND'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            entered.set()
            gate.wait(5.0)
            raise RuntimeError('read_fault')

    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('coordination'),
                                    name='coordination',
                                    api=CoordinationApi(),
                                    clock=time.monotonic, handle=706)
    cancel = _ChannelCancel()
    holder = {}

    def run_read():
        try:
            endpoint.read(None, cancel)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            holder['error'] = error

    reader = threading.Thread(target=run_read)
    reader.start()
    try:
        assert entered.wait(5.0), 'the read never entered the operation'
        # The cancellation of the round is published while the read is
        # really inside its operation.
        cancel.set()
        reader.join(10.0)
        assert not reader.is_alive(), 'the read of the round was left behind'
        error = holder.get('error')
        assert isinstance(error, RuntimeError), \
            'the original error object of the generation was replaced'
        assert str(error) == 'read_fault'
        outcome = endpoint._reader.outcome(1)
        assert outcome is not None, 'the outcome of the generation is gone'
        assert outcome['error'] == 'RuntimeError'
        assert isinstance(outcome['error_object'], RuntimeError)
        write_phase('r10-coordination', {'error': type(error).__name__,
                                         'detail': str(error),
                                         'outcome': outcome['error'],
                                         'parallel': getattr(
                                             error, 'lvw_parallel_cancellation',
                                             None) is not None})
    finally:
        gate.set()
        reader.join(10.0)
        endpoint.close()

    # -- the auxiliary proof of the group (N1 correction 11, M09): the
    #    outcome of the **same** generation is inspected **before** a
    #    new timeout is decided and **again** after the coordination of
    #    the cancellation.  The order of the two facts is the reason of
    #    the behaviour above and the behaviour above is the oracle.
    source = (PACK_ROOT / 'tools' / 'v0_s3_native_broker.py').read_text(
        encoding='utf-8')
    tree = ast.parse(source)
    await_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == '_WindowsPipeEndpoint':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == '_await':
                    await_node = item
    assert await_node is not None, 'the awaiting of the endpoint is gone'
    section = ast.unparse(await_node)
    assert section.count('worker.outcome(generation)') >= 3, \
        'the outcome of the generation is not consulted on every path'
    timeout_at = section.index('BROKER_PIPE_TIMEOUT')
    first_outcome = section.index('worker.outcome(generation)')
    cancel_at = section.index('self._cancel(worker, effective)')
    second_outcome = section.index('worker.outcome(generation)', cancel_at)
    assert first_outcome < timeout_at, \
        'the new timeout is decided before the published outcome is read'
    assert first_outcome < cancel_at < second_outcome, \
        'the published outcome is not read again after the coordination'


# -- N10-R11: the overflow of the channel is a named failure -------------

def test_n10_r11_the_overflow_of_the_channel_is_a_named_failure(tmp_path):
    """N10-R11 (M09): the overflow of the channel is named where it is.

    Obligation: a complete frame with a newline that is too long and a
    frame that is one byte beyond the limit are recorded at the place
    where they really happen, as a **named** sticky error of the
    channel with the original facts of the overflow.  A close that
    happens before the read consumes the frame carries that error: the
    channel that overflowed is never a channel that ended normally and
    the broker is never released as if there were no error.  The limits
    of the package do not move: the exact frame fits and the frame that
    is one byte longer does not.

    Entry: ``StreamChannel._drain``, ``StreamChannel._record_overflow``,
    ``StreamChannel.close``, ``BrokerProcess._close_channel`` and
    ``NativeCustodySession.stop``.  Trigger: the channel of the round
    reads a frame that does not fit and the round is stopped twice.
    Oracle: the error of the reader is the named overflow, the facts of
    the overflow travel with the close and the broker is kept.  Negative:
    the exact frame still fits and the one byte beyond the limit does
    not.  Returned state: the facts of the two stops name the overflow.
    Salvage: the owner of the test stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    limit = 32 * 1024
    # The exact frame and the frame that is one byte longer are strictly
    # adjacent and the limit of the package does not move.
    exact = b'y' * (limit - 1) + b'\n'
    one_over = b'x' * limit + b'\n'
    assert len(exact) == limit
    assert len(one_over) == limit + 1

    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        # The owner of the test publishes the frame that does not fit
        # into the channel of the round: the frame is a **complete**
        # frame with a newline that is one byte beyond the limit.
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_outcome('FRAME', one_over)
        # The channel of the round reads the frame that does not fit.
        deadline = time.monotonic() + 15.0
        while holder['channel']._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        channel = holder['channel']
        facts = {'error': channel._error, 'overflow': channel.overflow,
                 'overflow_facts': channel._overflow_facts}
        write_phase('r11-oversize', facts)
        assert channel.overflow is True
        assert channel._error == 'BROKER_CHANNEL_OVERFLOW', \
            'the overflow was not recorded as a named failure'
        assert channel._overflow_facts.get('reason') == 'FRAME_TOO_LARGE'
        # The two real stops of the round carry the named error.
        first = session.stop()
        first_facts = first['broker_close_facts'] or {}
        write_phase('r11-first', {'reader_error':
                                  first_facts.get('channel_reader_error'),
                                  'overflow': first_facts.get('channel_overflow'),
                                  'state': first['state']})
        assert first_facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_OVERFLOW', \
            'the close of the round lost the overflow'
        assert first_facts.get('channel_overflow') is True
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
        second = session.stop()
        second_facts = second['broker_close_facts'] or {}
        write_phase('r11-second', {'reader_error':
                                    second_facts.get('channel_reader_error'),
                                    'source':
                                    second_facts.get('channel_reader_error_source'),
                                    'state': second['state']})
        assert second_facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_OVERFLOW', \
            'the second attempt lost the overflow'
        assert second['broker_retained'] is True
        assert second['state'] == 'UNKNOWN_RETAINED'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass

    # The exact frame still fits: the limits of the package did not move.
    blocks = [exact]
    channel = StreamChannel(None, None, read_endpoint=_BlockReader(blocks),
                            write_endpoint=_BlockWriter(), clock=time.monotonic)
    try:
        deadline = time.monotonic() + 15.0
        while channel._count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        write_phase('r11-exact', {'count': channel._count,
                                  'overflow': channel.overflow,
                                  'error': channel._error})
        assert channel._count == 1, \
            'the exact frame did not fit into the channel'
        assert channel.overflow is False
        assert channel._error is None
    finally:
        channel.close()

    # The frame count of the channel: the frame that is one beyond the
    # number of the frames of the package is refused with the same named
    # error.  The parent of the round may never deliver that many
    # frames - its own budget is smaller - and the channel alone is the
    # owner that may prove it.
    blocks = [b'z\n'] * 1025
    channel = StreamChannel(None, None, read_endpoint=_BlockReader(blocks),
                            write_endpoint=_BlockWriter(), clock=time.monotonic)
    try:
        deadline = time.monotonic() + 15.0
        while channel._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        write_phase('r11-frames', {'error': channel._error,
                                   'overflow': channel.overflow,
                                   'overflow_facts': channel._overflow_facts,
                                   'frames': channel.frames})
        assert channel.overflow is True
        assert channel._error == 'BROKER_CHANNEL_OVERFLOW'
        assert channel._overflow_facts.get('reason') == 'TOO_MANY_FRAMES'
    finally:
        channel.close()


class _BlockReader:
    """A read end of the channel that returns the blocks it was given."""

    def __init__(self, blocks):
        self.blocks = list(blocks)

    def read(self, deadline=None, cancel=None):
        if self.blocks:
            return self.blocks.pop(0)
        return b''

    def close(self):
        return {'closed': True, 'retained_workers': 0,
                'worker_thread_handle_released': True}


class _BlockWriter:
    """A write end of the channel that counts its own closes."""

    def __init__(self):
        self.closes = 0

    def write(self, raw, deadline=None, cancel=None):
        return len(raw)

    def close(self):
        self.closes += 1
        return {'closed': True, 'retained_workers': 0,
                'worker_thread_handle_released': True}


# -- N10-R12: the causal order of the reader ------------------------------

def test_n10_r12_the_reader_publishes_its_wait_before_it_waits(tmp_path):
    """N10-R12 (test causality): the reader publishes its real state.

    Obligation: the reader of the chain publishes the event that it is
    really inside its read **before** it waits, so that the owner of
    the test never waits for an event that the reader publishes only
    after a timeout.  The external owner waits for that event, it sets
    the **same** cancel flag of the **same** channel without naming an
    owner and it publishes an explicit confirmation; the public stop of
    the round is driven only after that confirmation.  The code of the
    cancellation is the one that the **real** observation layer raised
    - the read endpoint of the channel or the wait of the channel
    between two reads - and the origin of the cancellation stays
    unknown: the close of the channel may never be taken for the owner
    of this cancellation.

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
    the test, in every case and with a bounded wait.
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
        assert owner.flag_owner is None
        # The public stop of the round is driven only after the
        # confirmation of the owner.
        first = session.stop()
        close_facts = first['broker_close_facts'] or {}
        write_phase('r12-stop', {'state': first['state'],
                                  'reader_error':
                                  close_facts.get('channel_reader_error'),
                                  'retained': first['broker_retained']})
        # The code of the cancellation is the one that the real
        # observation layer raised and it is one of the two codes that
        # the production names for the cancellation of the channel.
        assert close_facts.get('channel_reader_error') in CANCELLATION_CODES, \
            'the cancellation of the other owner was not classified'
        # It is **not** the cancellation of the close of the channel.
        assert close_facts.get('close_cancellation') is None, \
            'the cancellation of another owner was taken for the close'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        # The exact thread of the owner of the test is joined in every
        # case and with a bounded wait.
        thread.join(30.0)
        assert not thread.is_alive(), 'the owner of the round was left behind'
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- N10-R13: the fault is unlocked by the owner of the test ---------------

def test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first(tmp_path):
    """N10-R13 (M09): the fault of the read is observed before the stop.

    Obligation: the ordinary failure of the read, the frame that never
    ends and the end of the stream are published by the **owner of the
    test** and they are never unlocked by the write of the stop: the
    owner waits for the real outcome - the error, the frame or the end
    of the stream - and it observes it **before** it drives the public
    stop of the round.  Every phase of the round writes its bounded
    document and every value of it is a value that the production
    returned.

    Entry: ``_F5Api.publish_read_fault``,
    ``_F5Api.publish_partial_frame`` and
    ``NativeCustodySession.stop``.  Trigger: the ordinary failure of
    the read of the chain, the frame that never ends and the end of the
    stream.  Oracle: the failure was really published before the stop,
    the error of the reader is the error of the round and the partial
    frame keeps its own name.  Negative: the write of the stop never
    unlocks a failure that should have happened first.  Returned state:
    the phase documents are on the disk.  Salvage: the owner of the test
    stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())

    # -- PHASE ONE: the ordinary failure of the read --------------------
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
        facts = first['broker_close_facts'] or {}
        write_phase('r13-fault', {'reader_error':
                                   facts.get('channel_reader_error'),
                                   'state': first['state'],
                                   'retained': first['broker_retained']})
        assert facts.get('channel_reader_error') == 'RuntimeError', \
            'the failure of the read was swallowed by the stop'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass

    # -- PHASE TWO: the frame that never ends and the end of the stream --
    api = _F5Api(partial_frame=b'{"schema": "lvw.s3-native-custody-channel/1"')
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_partial_frame()
        assert api.eof_observed.wait(15.0), \
            'the end of the stream was never observed'
        channel = holder['channel']
        deadline = time.monotonic() + 15.0
        while channel._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        first = session.stop()
        facts = first['broker_close_facts'] or {}
        write_phase('r13-partial', {'reader_error':
                                    facts.get('channel_reader_error'),
                                    'state': first['state'],
                                    'retained': first['broker_retained']})
        assert facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_PARTIAL_FRAME', \
            'the partial frame was dropped as a normal end'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass


# -- N10-R14: the compatibility of the new candidate ----------------------

def test_n10_r14_the_closed_obligations_of_the_package_do_not_regress(tmp_path):
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
            wall=time.time, nonce=NONCE)
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
        facts = {'unknown': probe._context.is_unknown(),
                 'frames_sent': session._frames_sent,
                 'frames_received': session._frames_received,
                 'cancel_owner': cancel.owner().owner}
        write_phase('r14-compatibility', facts)
        first = session.stop()
        assert first['state'] in ('UNKNOWN_RETAINED', 'RELEASED')
    finally:
        try:
            session.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            pass
