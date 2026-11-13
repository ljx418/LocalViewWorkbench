"""The frozen regressions of the N1 correction 03 of the native custody.

This module carries the **16 frozen oracle groups** of the root package
``reports/v0-s3/product-gate0/native-custody-correction-03`` (the file
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
  ``BrokerCore``, the production ``BrokerLoop``, the production
  ``StreamChannel``, the production ``_WindowsPipeWorker`` and
  ``_WindowsPipeEndpoint`` and the production
  ``NativeCustodySession``.  A façade that only returns the right
  story would not prove anything and it is not used for the failure
  paths.

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
import ctypes
import json
import queue
import sys
import threading
import time
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_native_broker import (  # noqa: E402 - the path is set above
    BrokerCore, BrokerError, BrokerLoop, BrokerProcess, CreatedProcess,
    StreamChannel, WindowsApi, _WindowsPipeEndpoint, _WindowsPipeWorker,
    _adopt_broker_process, _declare_windows_primitives, _windows_api_types)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, CustodyError, MAX_FRAME_BYTES, NativeCustodySession,
    validate_launch_plan)

# The plan schema of the package.  It is written out here instead of
# being imported so that the plan of the check does not depend on the
# internal name of the constant.
PLAN_SCHEMA = 'lvw.s3-native-custody-plan/1'


# -- the plan of the check --------------------------------------------------

def plan_document(**overrides):
    """A valid closed plan document with a valid lease."""
    document = {
        'schema': PLAN_SCHEMA,
        'run_id': 'n1-correction-03',
        'candidate_sha': 'a' * 40,
        'authorization_sha256': 'b' * 64,
        'lease_expires_at': 100000.0,
        'max_runtime_seconds': 21600,
        'roles': [
            {'role': 'COMFY',
             'tools': [{'path': 'C:/ComfyUI-aki-v2/python/python.exe', 'sha256': 'c' * 64},
                       {'path': 'C:/ComfyUI-aki-v2/ComfyUI/main.py', 'sha256': 'd' * 64}],
             'data': {'user_directory': 'user'},
             'log': 'temp/native/comfy.log'},
            {'role': 'OLLAMA',
             'tools': [{'path': 'C:/Program Files/Ollama/ollama.exe', 'sha256': 'e' * 64}],
             'data': {},
             'log': 'temp/native/ollama.log'},
        ],
    }
    document.update(overrides)
    return document


def sealed_plan(document=None):
    """The sealed plan of the check."""
    return validate_launch_plan(document or plan_document(), now=1000.0)


# -- the synthetic primitive table of the Windows façade ---------------------

class _Primitive:
    """One primitive of a synthetic table.

    The primitive carries the declaration that the production builder
    applied to it and it forwards the call to the table.  It never
    touches the operating system.
    """

    def __init__(self, name, table):
        self.name = name
        self._table = table
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self._table.call(self.name, *args)


class SyntheticKernel32:
    """A primitive table that answers the calls of the production façade.

    The table allocates integer handles and it records every call in its
    order.  A named behaviour may be replaced by a script, so that one
    exact failure of one exact primitive can be driven.  The handles are
    plain integers: they never reach the kernel and the table owns
    every one of them.
    """

    def __init__(self, *, script=None):
        self.calls = []
        self.live = {}
        self.script = dict(script or {})
        self.next_handle = 500
        self.process_handle = 502
        self.thread_handle = 503
        self.null_handle = 501
        self.creation_time = 0x0000_0000_0000_1234
        self.pid = 4242

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        primitives = self.__dict__.setdefault('primitives', {})
        if name not in primitives:
            primitives[name] = _Primitive(name, self)
        return primitives[name]

    def allocate(self, kind):
        self.next_handle += 1
        self.live[self.next_handle] = kind
        return self.next_handle

    def call(self, name, *args):
        self.calls.append(name)
        handler = self.script.get(name)
        if handler is not None:
            return handler(self, *args)
        return self._default(name, *args)

    def _default(self, name, *args):
        if name == 'CreateFileW':
            handle = self.null_handle
            self.live[handle] = 'null'
            return handle
        if name == 'InitializeProcThreadAttributeList':
            if args[0] is None:
                args[3]._obj.value = 256
                return 0
            return 1
        if name == 'UpdateProcThreadAttribute':
            return 1
        if name == 'DeleteProcThreadAttributeList':
            return None
        if name == 'CreateProcessW':
            information = args[9]._obj
            information.hProcess = self.process_handle
            information.hThread = self.thread_handle
            information.dwProcessId = self.pid
            self.live[self.process_handle] = 'process'
            self.live[self.thread_handle] = 'thread'
            return 1
        if name == 'GetProcessTimes':
            creation = args[1]._obj
            creation.dwLowDateTime = self.creation_time & 0xFFFFFFFF
            creation.dwHighDateTime = self.creation_time >> 32
            return 1
        if name == 'CloseHandle':
            handle = getattr(args[0], 'value', args[0])
            self.live.pop(handle, None)
            return 1
        if name == 'TerminateProcess':
            return 1
        if name == 'WaitForSingleObject':
            return 0
        if name == 'QueryInformationJobObject':
            return self._query_job(args)
        return 1

    def _query_job(self, args):
        """The default answer of the job query: an empty job."""
        buffer = args[2]
        size = args[3]
        returned = args[4]
        ctypes.memmove(ctypes.byref(buffer, 0), bytes(ctypes.c_uint32(0)), 4)
        ctypes.memmove(ctypes.byref(buffer, 4), bytes(ctypes.c_uint32(0)), 4)
        if returned is not None:
            returned._obj.value = 8
        return 1

    def names(self):
        return list(self.calls)


def synthetic_table(kernel32):
    """The production primitive table with an injected kernel32."""
    types = _windows_api_types()
    _declare_windows_primitives(kernel32, types)
    from tools.v0_s3_native_broker import _WindowsApiTable
    return _WindowsApiTable(kernel32=kernel32, types=types)


# -- the recording façade of the broker core --------------------------------

class RecordingWin32:
    """The in-process façade of the Windows primitives of the core.

    The façade has the same methods as the production façade, it records
    the calls in their order and it can fail at one named call with the
    **stable broker code of the production façade**.  It allocates
    integer handles and it owns every one of them: a handle that is not
    closed is still in ``live`` and it is a resource of the round.
    """

    def __init__(self, *, fail_at=None, job_process_ids=None, reader_gate=None):
        self.fail_at = fail_at
        self.job_ids = list(job_process_ids or [])
        self.reader_gate = reader_gate
        self.calls = []
        self.live = {}
        self.closed = []
        self.terminated = []
        self.assigned = []
        self.resumed = []
        self.created = []
        self.next_handle = 100
        self.next_pid = 4000
        self.failure_fired = False

    def _handle(self):
        self.next_handle += 1
        self.live[self.next_handle] = 'handle'
        return self.next_handle

    def _fail(self, name, error):
        self.failure_fired = True
        raise error

    def names(self):
        return [call[0] for call in self.calls]

    # -- the job -----------------------------------------------------------
    def create_job(self):
        handle = self._handle()
        self.calls.append(('create_job', handle))
        return handle

    def set_job_kill_on_close(self, job):
        self.calls.append(('set_job_kill_on_close', job))
        if self.fail_at == 'job_limit':
            self._fail('job_limit', BrokerError('BROKER_JOB_LIMIT_FAILED'))

    def terminate_job(self, job, exit_code):
        self.calls.append(('terminate_job', job, exit_code))
        if self.fail_at == 'terminate_job_ordinary':
            # An **ordinary** failure of the termination of the job.  The
            # core has to keep the primary error and it still has to run
            # every later cleanup.
            self._fail('terminate_job_ordinary', RuntimeError('ordinary_terminate_job'))
        if self.fail_at == 'terminate_job':
            self._fail('terminate_job', BrokerError('BROKER_TERMINATE_FAILED'))
        for entry in self.created:
            entry['exited'] = True

    def job_process_ids(self, job):
        self.calls.append(('job_process_ids', job))
        if self.fail_at == 'query_job':
            self._fail('query_job', BrokerError('BROKER_JOB_QUERY_UNKNOWN'))
        return list(self.job_ids)

    # -- the processes -----------------------------------------------------
    def create_process_suspended(self, *, executable, arguments, working_directory,
                                  stdout_handle, stderr_handle, environment=None):
        self.calls.append(('create_process_suspended', executable))
        if self.fail_at == 'create':
            self._fail('create', BrokerError('BROKER_PROCESS_CREATE_FAILED'))
        self.next_pid += 1
        entry = {'pid': self.next_pid, 'exited': False, 'handle': self._handle(),
                 'thread': self._handle()}
        self.created.append(entry)
        return CreatedProcess(entry['handle'], entry['thread'], entry['pid'],
                              creation_time=17000000000000000)

    def assign_process_to_job(self, job, process):
        self.calls.append(('assign_process_to_job', job, process))
        if self.fail_at == 'assign':
            self._fail('assign', BrokerError('BROKER_ASSIGN_FAILED'))
        self.assigned.append((job, process))

    def resume_thread(self, thread):
        self.calls.append(('resume_thread', thread))
        if self.fail_at == 'resume':
            self._fail('resume', BrokerError('BROKER_RESUME_FAILED'))
        self.resumed.append(thread)

    def terminate_process(self, process, exit_code):
        self.calls.append(('terminate_process', process, exit_code))
        if self.fail_at == 'terminate':
            self._fail('terminate', BrokerError('BROKER_TERMINATE_FAILED'))
        self.terminated.append(process)
        for entry in self.created:
            if entry['handle'] == process:
                entry['exited'] = True

    def wait_process(self, process, timeout_ms):
        self.calls.append(('wait_process', process, timeout_ms))
        for entry in self.created:
            if entry['handle'] == process:
                return entry['exited']
        return True

    def exit_code(self, process):
        self.calls.append(('exit_code', process))
        return 0

    def close_handle(self, handle):
        self.calls.append(('close_handle', handle))
        if self.fail_at == 'close':
            self._fail('close', BrokerError('BROKER_HANDLE_CLOSE_FAILED'))
        self.closed.append(handle)
        if handle in self.live:
            del self.live[handle]

    # -- the pipes ---------------------------------------------------------
    def create_pipe(self, name):
        self.calls.append(('create_pipe', name))
        read = self._handle()
        write = self._handle()
        return read, write

    def read_stream(self, handle, size):
        # Only the first reader of the round stays inside its read: the
        # other readers end at once and their handles are closed.
        self._reader_calls = getattr(self, '_reader_calls', 0) + 1
        if self.reader_gate is not None and self._reader_calls == 1:
            self.reader_gate.wait(10.0)
        return b''

    def write_stream(self, handle, data):
        self.calls.append(('write_stream', handle, len(data)))
        return len(data)


# -- the peer of the parent session -----------------------------------------

class RecordingPeer:
    """The in-process stand-in of the original handle of the broker.

    The stand-in speaks the closed frame protocol of the private channel
    and it understands the **deadline aware** interface of the
    production handle.  The facts of its close are scripted: a close
    that returns nothing or a false fact is a fact of the round and not
    a proof of a release.
    """

    channel_deadline_aware = True

    def __init__(self, plan, nonce, *, kinds=('READY', 'STATUS'), close_facts=None,
                 write_error=None):
        self.plan = plan
        self.nonce = nonce
        self.pid = 4242
        self.executable = 'C:/Windows/py.exe'
        self.executable_sha256 = 'f' * 64
        self.inbound = queue.Queue()
        self.outbound = []
        self.closed = 0
        self.close_facts = close_facts
        self.write_error = write_error
        self.bound_deadline = None
        self.write_deadlines = []
        self.reader_finished = True
        self._sequence = 0
        for kind in kinds:
            self.emit(kind)

    def emit(self, kind):
        self._sequence += 1
        states = {'READY': 'ARMED', 'STATUS': 'RUNNING',
                  'STOPPED': 'RELEASED', 'REFUSED': 'UNKNOWN_RETAINED'}
        self.inbound.put(json.dumps(
            {'schema': CHANNEL_SCHEMA, 'kind': kind, 'run_id': self.plan.run_id,
             'candidate_sha': self.plan.candidate_sha,
             'authorization_sha256': self.plan.authorization_sha256,
             'nonce': self.nonce, 'sequence': self._sequence,
             'state': states[kind], 'detail': {}},
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8') + b'\n')

    def bind_channel_deadline(self, deadline):
        if self.bound_deadline is not None and deadline > self.bound_deadline:
            raise BrokerError('BROKER_DEADLINE_EXTENDED')
        self.bound_deadline = deadline
        return deadline

    def write(self, raw, deadline=None):
        self.write_deadlines.append(deadline)
        if self.write_error is not None:
            raise self.write_error
        self.outbound.append(json.loads(raw))
        if json.loads(raw)['command'] == 'STOP':
            self.emit('STOPPED')

    def read(self, timeout):
        try:
            return self.inbound.get(timeout=min(timeout, 0.05))
        except queue.Empty:
            return None

    def close(self):
        self.closed += 1
        return self.close_facts


class ManualClock:
    """A clock that only moves when the check moves it."""

    def __init__(self, value=1000.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


def make_session(tmp_path, *, peer=None, plan=None, clock=None, wall=None,
                 kinds=('READY', 'STATUS'), close_facts=None, write_error=None):
    """One parent session with an in-process peer."""
    clock = clock or ManualClock()
    wall = wall or (lambda: 1000.0)
    holder = {'peer': None}

    def launcher(plan_document_, run_root, nonce):
        holder['peer'] = peer or RecordingPeer(
            plan_document_, nonce, kinds=kinds, close_facts=close_facts,
            write_error=write_error)
        return holder['peer']

    document = plan or plan_document()
    session = NativeCustodySession(plan=document, run_root=tmp_path / 'round',
                                   parent_child_remaining_seconds=21600,
                                   launcher=launcher, clock=clock, wall=wall)
    return session, holder, clock


# -- N03-R01: the original handles of a failed creation stay with the owner -

def test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api():
    """N03-R01 (M03): the API owner keeps the handles and the errors.

    The birth query of a created process fails, the wait of the release
    times out and both closes fail.  The production API owner keeps the
    original process and thread references, the primary error and the
    cleanup errors are named, the round is not a release and the owner
    alone may recover the handles later.
    """
    def fail_birth(kernel32, *args):
        return 0

    def timeout_wait(kernel32, *args):
        return 258  # WAIT_TIMEOUT

    def fail_close(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle in (kernel32.process_handle, kernel32.thread_handle):
            # The first close of every handle fails.  A later recovery
            # of the owner may close it.
            attempts = kernel32.__dict__.setdefault('close_attempts', {})
            attempts[handle] = attempts.get(handle, 0) + 1
            if attempts[handle] == 1:
                return 0
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': fail_birth,
                                         'WaitForSingleObject': timeout_wait,
                                         'CloseHandle': fail_close})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    # The primary error of the creation is the error that leaves the
    # method and the cleanup errors are named next to it.
    assert info.value.code == 'BROKER_PROCESS_BIRTH_QUERY_FAILED'
    detail = info.value.detail or ''
    assert 'cleanup=' in detail
    assert 'WaitForSingleObject:exit_not_confirmed' in detail
    assert 'CloseHandle' in detail
    # The original references of the process and of the thread are with
    # their owner: they are not only an integer in a local list.
    retained = api.retained_handles()
    kinds = sorted(entry['kind'] for entry in retained)
    assert kinds == ['process', 'thread']
    handles = {entry['handle'] for entry in retained}
    assert kernel32.process_handle in handles
    assert kernel32.thread_handle in handles
    # The null device of the child was closed: the cleanup of the
    # creation is independent of the failure of the birth query.
    assert kernel32.null_handle not in kernel32.live
    # The recovery of the owner is explicit and it is possible later.
    report = api.release_retained()
    assert len(report) == 2
    assert all(entry['released'] for entry in report)
    assert api.retained_handles() == []


def test_n03_r02_a_failed_cleanup_of_the_creation_still_releases_everything():
    """N03-R02 (M03): the cleanups of a creation are independent.

    The deletion of the attribute list raises an ordinary exception
    after a successful creation.  The close of the null device and the
    release of the created process still happen, the first error is
    kept and no original handle is left without an owner.
    """
    def fail_delete(kernel32, *args):
        raise RuntimeError('delete_after_creation')

    kernel32 = SyntheticKernel32(script={'DeleteProcThreadAttributeList': fail_delete})
    api = WindowsApi(table=synthetic_table(kernel32))
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(executable='C:/tools/python.exe', arguments=['-s'],
                                     working_directory='C:/round', stdout_handle=0x21,
                                     stderr_handle=0x22, environment=None)
    assert info.value.code == 'BROKER_ATTRIBUTE_LIST_CLEANUP_FAILED'
    assert 'DeleteProcThreadAttributeList' in (info.value.detail or '')
    # The null device was closed even though the deletion of the
    # attribute list failed before it.
    assert 'CloseHandle' in kernel32.names()
    assert kernel32.null_handle not in kernel32.live
    # The created process was released through its own original handle.
    assert 'TerminateProcess' in kernel32.names()
    assert 'WaitForSingleObject' in kernel32.names()
    assert kernel32.process_handle not in kernel32.live
    assert kernel32.thread_handle not in kernel32.live
    # Nothing is left without an owner.
    assert api.retained_handles() == []


def test_n03_r03_the_job_query_is_unknown_whenever_a_fact_does_not_agree():
    """N03-R03 (M04): the length, the two counts and the cap must agree.

    A returned length of zero, a reversed pair of counts, a length that
    is larger than the buffer, a list over the cap and a truncated list
    are all unknown.  A complete buffer and a legal empty job with a
    complete header are accepted.
    """
    def query(assigned, listed, length):
        def handler(kernel32, *args):
            buffer = args[2]
            returned = args[4]
            payload = (assigned.to_bytes(4, 'little') + listed.to_bytes(4, 'little')
                       + b''.join(pid.to_bytes(8, 'little')
                                  for pid in range(111, 111 + listed)))
            ctypes.memmove(args[2], payload, min(len(payload), args[3]))
            returned._obj.value = length
            return 1
        return handler

    cases = [(2, 2, 24, True), (2, 1, 16, False), (0, 1, 16, False),
             (0, 0, 0, False), (1, 1, 0, False), (18, 18, 152, False),
             (1, 1, 999, False), (0, 0, 8, True)]
    for assigned, listed, length, accepted in cases:
        kernel32 = SyntheticKernel32(script={
            'QueryInformationJobObject': query(assigned, listed, length)})
        api = WindowsApi(table=synthetic_table(kernel32))
        if accepted:
            identifiers = api.job_process_ids(0x99)
            assert len(identifiers) == listed
            assert identifiers == list(range(111, 111 + listed))
        else:
            with pytest.raises(BrokerError):
                api.job_process_ids(0x99)


def test_n03_r04_a_job_that_could_not_be_closed_keeps_its_original_handle(tmp_path):
    """N03-R04 (M05): the job handle is never forgotten by a failed close.

    The limit of the job fails and the close of the job fails as well.
    The core keeps the original job handle, the pending table keeps it
    and the evidence names it.  Nothing is taken and nothing is set to
    ``None``.
    """
    win32 = RecordingWin32(fail_at='close')
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    job = None
    with pytest.raises(BrokerError):
        core.arm()
    job = core.job
    # The original job handle is still with its owner.
    assert job is not None
    assert job in win32.live
    pending = core._pending.pending()
    assert [item['handle'] for item in pending] == [job]
    retained = core.evidence()['retained_resources']
    assert [item['kind'] for item in retained] == ['job']
    # The round is not a release.
    assert core.state == 'UNKNOWN_RETAINED'
    # The close of the job was really attempted.
    assert 'close_handle' in win32.names()


def test_n03_r05_the_stop_runs_every_cleanup_after_an_ordinary_failure(tmp_path):
    """N03-R05 (M06): the cleanups of the stop are independent.

    The termination of the job fails with an ordinary exception.  Every
    later cleanup still runs, the original exception is the one that
    leaves the method, the round stays unknown and the latch of a
    finished release is not set, so that the same owner may try the rest
    again.  A failure of the diagnosis that comes first is never
    replaced by the failure of a later cleanup.
    """
    win32 = RecordingWin32(fail_at='terminate_job_ordinary')
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    with pytest.raises(RuntimeError) as info:
        core.stop('STOP')
    # The original exception of the round is the one that leaves.
    assert 'ordinary_terminate_job' in str(info.value)
    # The later cleanups ran even though the termination of the job
    # failed with an ordinary exception.
    assert 'job_process_ids' in win32.names()
    assert 'close_handle' in win32.names()
    assert win32.closed, 'the original handles of the round were not closed'
    # The round is unknown and the latch of a finished release is not
    # set: a repeated stop may try the rest again.
    assert core.state == 'UNKNOWN_RETAINED'
    assert core._released is False
    with pytest.raises(RuntimeError):
        core.stop('STOP')
    assert core.state == 'UNKNOWN_RETAINED'

    # A failure of the diagnosis is the primary failure of the round and
    # it is not replaced by the failure of the cleanup that follows it.
    win32 = RecordingWin32(fail_at='terminate_job_ordinary')
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    core._collect_stream_counts = lambda: (_ for _ in ()).throw(RuntimeError('diagnosis'))
    with pytest.raises(RuntimeError) as info:
        core.stop('STOP')
    assert 'diagnosis' in str(info.value)
    assert 'job_process_ids' in win32.names()
    assert win32.closed
    assert core.state == 'UNKNOWN_RETAINED'


def test_n03_r06_the_start_cleans_up_everything_that_it_acquired(tmp_path):
    """N03-R06 (M07): the whole lifecycle of the start is protected.

    A failure of the start of the heartbeat, a cancellation and a
    channel that could not be built after the process was started all
    end with the original resources owned and cleaned up, and a
    cancellation continues to propagate.
    """
    # -- the heartbeat thread does not start --------------------------------
    session, holder, _clock = make_session(tmp_path)
    session._start_heartbeat = lambda: (_ for _ in ()).throw(
        RuntimeError('thread_start_failed'))
    evidence = session.start()
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    assert holder['peer'].closed == 1
    assert holder['peer'] is session.broker or session.broker is None

    # -- a cancellation of the read continues to propagate ------------------
    session, holder, _clock = make_session(tmp_path)

    def cancelling_read(timeout):
        raise KeyboardInterrupt('cancel')

    def launcher(plan_document_, run_root, nonce):
        peer = RecordingPeer(plan_document_, nonce)
        peer.read = cancelling_read
        holder['peer'] = peer
        return peer

    session._launcher = launcher
    with pytest.raises(KeyboardInterrupt):
        session.start()
    assert session.state == 'UNKNOWN_RETAINED'
    assert holder['peer'].closed == 1

    # -- a channel that could not be built owns the process ---------------
    class FakeProcess:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = False
            self.waited = 0
            self.stdin = type('S', (), {'close': lambda self: None})()
            self.stdout = type('S', (), {'close': lambda self: None})()

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.waited += 1
            return 0

    process = FakeProcess()

    def broken_channel():
        raise RuntimeError('channel_construction_failed')

    with pytest.raises(RuntimeError):
        _adopt_broker_process(process, channel_factory=broken_channel,
                              executable='C:/python.exe', executable_sha256='a' * 64)
    # The launcher owned the original process and it released it before
    # the failure left: the process was terminated and its pipes closed.
    assert process.terminated is True
    assert process.waited == 1


def test_n03_r07_the_startup_is_bounded_by_the_absolute_deadline(tmp_path):
    """N03-R07 (M08): no role is created after the deadline of the round.

    The arm of the round consumes the absolute lease and returns after
    it.  No process is created, no thread is resumed and no successful
    status is written.  The owner of the round answers with a bounded
    unknown and a startup that is still in flight keeps its owner.
    """
    clock = ManualClock(1000.0)
    win32 = RecordingWin32()
    plan = sealed_plan()
    core = BrokerCore(win32=win32, plan=plan, run_root=tmp_path, clock=clock)

    class Transport:
        def __init__(self):
            self.writes = []

        def bind_deadline(self, deadline):
            self.deadline = deadline

        def write(self, raw):
            self.writes.append(json.loads(raw))

        def read(self, timeout):
            return b''

    original = win32.create_job

    def slow_job():
        # The arm of the round consumes the whole lease of the round.
        handle = original()
        clock.value += 100000.0
        return handle

    win32.create_job = slow_job
    transport = Transport()
    loop = BrokerLoop(core=core, transport=transport, plan=plan, nonce='a' * 32,
                      clock=clock, wall=lambda: 1000.0)
    exit_code = loop.run()
    assert exit_code == 3
    # No role of the round was created and none was resumed.
    assert 'create_process_suspended' not in win32.names()
    assert 'resume_thread' not in win32.names()
    # The round is unknown and its resources were released.
    assert core.state == 'UNKNOWN_RETAINED'
    assert not win32.live
    # The reply of the round is a refusal and never a successful status.
    kinds = [frame['kind'] for frame in transport.writes]
    assert kinds == ['REFUSED']
    assert transport.writes[0]['detail']['code'] == 'BROKER_STARTUP_DEADLINE_EXCEEDED'


def test_n03_r08_the_cleanup_of_the_broker_uses_one_absolute_deadline():
    """N03-R08 (M08): every nested wait uses the same absolute deadline.

    The close of the channel consumes four seconds of the shared five
    seconds and the two waits of the process time out.  The clock never
    passes the deadline and no wait starts with a fresh timeout.
    """
    clock = ManualClock(1000.0)
    calls = []

    class Channel:
        reader_finished = True

        def bind_deadline(self, deadline):
            calls.append(('bind', deadline))

        def close(self):
            calls.append(('channel', clock.value))
            clock.value += 4
            return {'write_end_closed': True, 'read_end_closed': True,
                    'reader_finished': True}

    class Process:
        pid = 1
        returncode = None
        stdin = type('S', (), {'close': lambda self: None})()
        stdout = type('S', (), {'close': lambda self: None})()

        def wait(self, timeout=None):
            calls.append(('wait', clock.value, timeout))
            clock.value += timeout
            raise TimeoutError('still running')

        def terminate(self):
            calls.append(('terminate', clock.value))

    broker = BrokerProcess(Process(), 'x', 'a' * 64, Channel(), clock=clock)
    broker.write_deadline = 1005.0
    facts = broker.close()
    # The clock never passed the shared deadline.
    assert clock.value <= 1005.0
    # The second wait got the time that was left and not the whole
    # budget again.
    waits = [call for call in calls if call[0] == 'wait']
    assert waits[0][2] == 1.0
    assert waits[1][2] == 0.0
    assert facts['process_exited'] is False
    assert facts['cleanup_deadline'] == 1005.0


def test_n03_r09_a_partial_windows_write_is_never_a_success():
    """N03-R09 (M08/M09): the write is complete and the handle is closed.

    Windows writes one byte of six.  The endpoint writes the whole
    block, the worker is stopped and joined and the duplicated handle
    of its thread is closed by its only owner.  A worker that stays
    alive keeps the file: the file is never closed under it.
    """
    writes = []
    closed = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def write_stream(self, handle, data):
            writes.append(bytes(data))
            return 1

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            closed.append(handle)

    endpoint = _WindowsPipeEndpoint.__new__(_WindowsPipeEndpoint)
    endpoint._api = Api()
    endpoint._file = type('F', (), {'close': lambda self: closed.append('file')})()
    endpoint._name = 'inprocess'
    endpoint._handle = 702
    endpoint._clock = time.monotonic
    endpoint._reader = None
    endpoint._writer = None
    endpoint._closed = False
    endpoint._retained = []
    endpoint.facts = {}
    written = endpoint.write(b'abcdef', time.monotonic() + 5.0)
    assert written == 6
    assert writes == [b'abcdef', b'bcdef', b'cdef', b'def', b'ef', b'f']
    facts = endpoint.close()
    assert facts['closed'] is True
    # The handle of the thread of the worker was closed by its only
    # owner and the file was closed after the worker stopped.
    assert 701 in closed
    assert 'file' in closed
    assert facts['retained_workers'] == 0


def test_n03_r10_the_cancellation_of_a_worker_stops_it_from_entering_io():
    """N03-R10 (M08): the cancellation is bounded and it prevents the I/O.

    A cancellation that reports that the operation was not found is
    repeated, bounded by the shared deadline, and a request that is
    still queued when the cancellation arrives is never performed.  A
    worker whose thread handle could not be created and a worker that
    is still inside an older operation both refuse the request with a
    named error, and no wait is unbounded.
    """
    entered = []
    release = threading.Event()

    def action(request):
        entered.append(request)
        release.wait(5.0)
        return b''

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            pass

    worker = _WindowsPipeWorker(Api(), 702, kind='read', action=action,
                                name='n03-r10-worker')
    worker.start()
    worker.wait_ready(2.0)
    worker.submit(b'first')
    for _ in range(100):
        if entered:
            break
        time.sleep(0.02)
    assert entered == [b'first']
    # The second request waits for the worker.
    worker.submit(b'second')
    # The cancellation of the worker that is inside its operation is
    # bounded: it is repeated until the deadline of the round arrives.
    started = time.monotonic()
    state = worker.request_cancel(time.monotonic() + 0.2)
    assert state == 'NOT_FOUND'
    assert time.monotonic() - started < 3.0
    # The request that was still queued is never performed: the
    # cancellation reached the worker before the operation started.
    release.set()
    worker.wait_done(2, 3.0)
    assert entered == [b'first'], 'the worker entered the operation after the cancellation'
    worker.stop_accepting()
    worker.join_bounded(2.0)

    # A worker whose thread handle could not be created refuses the
    # request with a named error.
    class BrokenApi:
        def duplicate_current_thread_handle(self):
            raise BrokerError('BROKER_THREAD_HANDLE_FAILED')

    broken = _WindowsPipeWorker(BrokenApi(), 703, kind='read',
                                action=lambda request: b'', name='n03-r10-broken')
    broken.start()
    broken.wait_ready(2.0)
    with pytest.raises(BrokerError) as info:
        broken.submit(None)
    assert info.value.code in ('BROKER_WORKER_NOT_READY', 'BROKER_WORKER_NOT_ALIVE')
    broken.join(2.0)

    # A worker that is still inside an older operation refuses the
    # request with a named error and never blocks without a bound.
    class SlowApi:
        def duplicate_current_thread_handle(self):
            return 704

        def cancel_synchronous_io(self, handle):
            return 'NOT_FOUND'

        def close_handle(self, handle):
            pass

    release = threading.Event()
    entered = []
    slow = _WindowsPipeWorker(SlowApi(), 705, kind='write',
                              action=lambda request: (entered.append(request),
                                                     release.wait(5.0)),
                              name='n03-r10-slow')
    slow.start()
    slow.wait_ready(2.0)
    slow.submit(b'first')
    for _ in range(100):
        if entered:
            break
        time.sleep(0.02)
    assert entered == [b'first']
    # The queue of the worker holds exactly one request.
    slow.submit(b'second')
    with pytest.raises(BrokerError) as info:
        slow.submit(b'third')
    assert info.value.code == 'BROKER_WORKER_QUEUE_FULL'
    release.set()
    slow.stop_accepting()
    slow.join_bounded(2.0)


def test_n03_r11_a_failure_of_the_background_latches_the_unknown_state(tmp_path):
    """N03-R11 (M08): the heartbeat and the pump latch and close.

    A heartbeat that cannot write and a pump that failed both latch the
    unknown state of the round and they start a bounded close that never
    joins itself.  A heartbeat is never sent after the absolute deadline
    of the round arrived and the stop of the round blocks the heartbeat
    that would follow it.
    """
    # -- the heartbeat cannot write ---------------------------------------
    session, holder, clock = make_session(
        tmp_path,
        write_error=BrokerError('BROKER_PIPE_WRITE_FAILED'))
    session.start()
    session._last_heartbeat = clock.value - 61.0
    assert session._heartbeat_step() is False
    assert session.state == 'UNKNOWN_RETAINED'
    assert any('CUSTODY_HEARTBEAT_FAILED' in failure
               for failure in session.evidence()['failures'])
    # The bounded close ran and it closed the peer exactly once.
    for _ in range(50):
        if holder['peer'].closed:
            break
        time.sleep(0.02)
    assert holder['peer'].closed == 1
    session.stop()

    # -- the heartbeat is not sent after the deadline ----------------------
    clock = ManualClock(1000.0)
    session, holder, clock = make_session(tmp_path, clock=clock)
    session.start()
    deadline = session._deadline_mono
    session._last_heartbeat = clock.value - 61.0
    clock.value = deadline + 1.0
    sent = len(holder['peer'].outbound)
    assert session._heartbeat_step() is False
    assert len(holder['peer'].outbound) == sent
    session.stop()

    # -- the stop blocks the heartbeat that would follow it ---------------
    clock = ManualClock(1000.0)
    session, holder, clock = make_session(tmp_path, clock=clock)
    session.start()
    session._stopping = True
    session._last_heartbeat = clock.value - 61.0
    sent = len(holder['peer'].outbound)
    assert session._heartbeat_step() is False
    assert len(holder['peer'].outbound) == sent
    session._stopping = False
    session.stop()


def test_n03_r12_the_frame_budget_is_the_total_of_both_directions(tmp_path):
    """N03-R12 (M08): the budget of the channel is a total.

    The frames that the parent sent and the frames that it received
    share one budget of 1024 frames, the frames of the terminal exchange
    are reserved, and the frame that does not fit is refused before it
    is sent and before it is accepted.
    """
    clock = ManualClock(1000.0)
    session, holder, clock = make_session(tmp_path, clock=clock)
    session.start()
    plan = session.plan
    # The total of the two directions is exactly at the limit: the frame
    # of the terminal exchange still fits.
    session._frames_sent = 500
    session._frames_received = 516
    session._sequence = 500
    reply = json.dumps(
        {'schema': CHANNEL_SCHEMA, 'kind': 'STATUS', 'run_id': plan.run_id,
         'candidate_sha': plan.candidate_sha,
         'authorization_sha256': plan.authorization_sha256,
         'nonce': session._nonce, 'sequence': session._broker_sequence + 1,
         'state': 'RUNNING', 'detail': {}}, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')
    # 500 + 516 + 8 (reserved) + 1 (the frame) is 1025: one over.
    with pytest.raises(CustodyError) as info:
        session._decode_reply(reply)
    assert info.value.code == 'CUSTODY_FRAME_BUDGET_EXCEEDED'
    # The refused reply was not accepted and it was not counted.
    assert session._frames_received == 516
    # The same total refuses a send as well.
    session._frames_sent = 500
    session._frames_received = 516
    with pytest.raises(CustodyError) as info:
        session._send('STATUS')
    assert info.value.code == 'CUSTODY_FRAME_BUDGET_EXCEEDED'
    assert session._frames_sent == 500
    # One frame below the limit is accepted.
    session._frames_sent = 500
    session._frames_received = 515
    assert session._decode_reply(reply)['kind'] == 'STATUS'
    assert session._frames_received == 516
    session.stop()


def test_n03_r13_the_buffer_of_the_channel_is_bounded_and_a_partial_frame_is_named():
    """N03-R13 (M08): the buffer is bounded and a partial frame is named.

    Two large blocks without a newline overflow the buffer of the
    channel at once: the buffer keeps at most one byte beyond the limit
    and the overflow is refused.  A stream that ends in the middle of a
    frame is a named failure and it is never dropped silently.
    """
    class Endpoint:
        def __init__(self, blocks):
            self.blocks = list(blocks)
            self.closed = False

        def read(self, deadline=None, cancel=None):
            if self.blocks:
                return self.blocks.pop(0)
            return b''

        def write(self, data, deadline=None, cancel=None):
            return len(data)

        def close(self):
            self.closed = True
            return {'closed': True}

    channel = StreamChannel(None, None, read_endpoint=Endpoint([b'x' * (32 * 1024 * 2),
                                                                b'y' * (32 * 1024)]),
                            write_endpoint=Endpoint([]))
    channel._thread.join(2.0)
    # The buffer of the channel is bounded and the overflow is refused.
    assert len(channel._buffer) <= MAX_FRAME_BYTES + 1
    assert channel.overflow is True
    with pytest.raises(BrokerError) as info:
        channel.read(0)
    assert info.value.code == 'BROKER_CHANNEL_OVERFLOW'
    channel.close()

    # A stream that ends in the middle of a frame is a named failure.
    channel = StreamChannel(None, None, read_endpoint=Endpoint([b'partial']),
                            write_endpoint=Endpoint([]))
    channel._thread.join(2.0)
    with pytest.raises(BrokerError) as info:
        channel.read(0.1)
    assert info.value.code == 'BROKER_CHANNEL_PARTIAL_FRAME'
    channel.close()


def test_n03_r14_a_close_without_facts_keeps_the_original_broker(tmp_path):
    """N03-R14 (M09): a release needs the facts of the close.

    A close that returns nothing and a close that reports a false fact
    keep the original broker and its reference: the round is unknown
    and the reference is never dropped.  An endpoint whose close failed
    is not marked as closed irreversibly.
    """
    for facts in (None, {'channel_closed': False, 'process_exited': True,
                         'process_handle_released': True},
                  {'channel_closed': True, 'process_exited': False,
                   'process_handle_released': True},
                  {'channel_closed': True, 'process_exited': True}):
        session, holder, _clock = make_session(tmp_path, close_facts=facts)
        session.start()
        peer = holder['peer']
        evidence = session.stop()
        assert evidence['state'] == 'UNKNOWN_RETAINED'
        # The original broker is kept: the reference of the resource of
        # the round is never dropped.
        assert session.broker is peer
        assert evidence['broker_retained'] is True
        assert peer.closed == 1

    # A close with every fact is a release.
    session, holder, _clock = make_session(
        tmp_path,
        close_facts={'channel_closed': True, 'process_exited': True,
                     'process_handle_released': True})
    session.start()
    evidence = session.stop()
    assert session.broker is None
    assert evidence['broker_retained'] is False

    # An endpoint whose close failed is not closed irreversibly.
    class BrokenSyscalls:
        def __init__(self):
            self.closed = []

        def fileno(self, file_object):
            return file_object.fileno()

        def set_blocking(self, descriptor, blocking):
            pass

        def close(self, file_object):
            raise OSError('close_failed')

    from tools.v0_s3_native_broker import _PosixPipeEndpoint
    file_object = type('F', (), {'fileno': lambda self: 7, 'close': lambda self: None})()
    endpoint = _PosixPipeEndpoint(file_object, name='read', syscalls=BrokenSyscalls(),
                                  clock=ManualClock())
    result = endpoint.close()
    assert result['closed'] is False
    assert result['error_type'] == 'OSError'
    # The endpoint may try the close again: it was not closed.
    assert endpoint.facts.get('already_closed') is None


def test_n03_r15_the_default_launcher_refuses_with_its_own_code(tmp_path):
    """N03-R15 (M11): the refusal of the launcher keeps its own code.

    The default launcher reaches the broker of the package, which
    refuses on a platform that is not Windows.  The refusal is a
    structured terminal state that carries the original code, it is not
    raised as a generic error of the parent, and nothing was created
    before the refusal.
    """
    run_root = tmp_path / 'n03-r15-round'
    document = plan_document(lease_expires_at=100000.0)
    session = NativeCustodySession(plan=document, run_root=run_root,
                                   parent_child_remaining_seconds=21600,
                                   wall=lambda: 1000.0)
    evidence = session.start()
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    assert 'BROKER_PLATFORM_UNSUPPORTED' in evidence['failures']
    assert evidence['broker'] is None
    # Nothing was created before the refusal of the launcher.
    assert not run_root.exists()


def test_n03_r16_the_positive_lifecycle_still_closes_everything(tmp_path):
    """N03-R16 (all): the closed items did not regress.

    A complete round releases every handle that it created, a reader
    that is still alive keeps its handle and may be released later by
    its owner, the closed items of the earlier rounds still hold and
    the native claims of the package stay ``NOT_PROVEN``.
    """
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    evidence = core.stop('STOP')
    assert evidence['state'] == 'RELEASED'
    assert not win32.live
    assert core._pending.pending() == []
    # The native claims of the package are not proven.
    assert evidence['native_execution_proven'] is False
    assert evidence['native_cleanup_proven'] is False
    assert evidence['stage_pass_claim'] is False
    assert evidence['product_gate0'] is False

    # -- a reader that is still alive keeps its handle ---------------------
    gate = threading.Event()
    win32 = RecordingWin32(reader_gate=gate)
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    core.arm()
    core.launch()
    core.stop('STOP')
    alive = [reader for reader in core.readers if reader.is_alive()]
    assert alive, 'the reader of the round did not stay alive'
    retained = {reader.handle for reader in alive}
    assert retained.issubset(set(win32.live))
    assert core.state == 'UNKNOWN_RETAINED'
    assert any(item['stage'] == 'reader_not_stopped' for item in core.failures)
    # The owner of the reader releases it and the handle is closed.
    gate.set()
    for reader in core.readers:
        reader.join(5.0)
    core._close_readers()
    assert not win32.live

    # -- the closed items of the earlier rounds ----------------------------
    # M01: the user directory is one closed segment.
    for bad in ('safe/../../outside', '..', 'NUL', 'a' * 65, ' user', 'user.'):
        document = plan_document()
        document['roles'][0]['data']['user_directory'] = bad
        with pytest.raises(CustodyError):
            validate_launch_plan(document, now=1000.0)
    # m01: the presented seal cannot change the command of a role.
    plan = sealed_plan()
    before = plan.sealed_sha256()
    presented = plan.sealed
    presented['roles'][0]['tools'][0]['path'] = 'C:/foreign.exe'
    assert plan.sealed_sha256() == before
    # M02: the declaration of the primitives is built without a library.
    types = _windows_api_types()
    assert ctypes.sizeof(types['DWORD']) == 4
    assert ctypes.sizeof(types['BOOL']) == 4
    assert types['JOBOBJECT_BASIC_PROCESS_ID_LIST'].ProcessIdList.offset == 8
    # M10: the private pids of the sampler are separate arguments.
    from tools.v0_s3_native_broker import role_command
    role = {'role': 'SAMPLER',
            'tools': [{'path': 'C:/python.exe', 'sha256': 'a' * 64},
                      {'path': 'C:/sampler.py', 'sha256': 'b' * 64}],
            'data': {'nvidia_exe': 'C:/nvidia.exe', 'nvidia_sha256': 'c' * 64,
                     'max_seconds': 60},
            'log': 'temp/native/sampler.log'}
    arguments = role_command(role, '/tmp/none', [4001, 4002])['arguments']
    index = arguments.index('--private-pids')
    assert arguments[index + 1] == '4001'
    assert arguments[index + 2] == '4002'
