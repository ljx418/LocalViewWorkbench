"""The offline validation of the N1 parent owned native custody.

The validation of this package is *offline*.  It never starts a process,
it never opens a socket, it never touches a database and it never reads
the original budget ledger or the original shared counter.  The only
native capability that is exercised here is an **in-process façade** of the
Windows primitives: a typed object with the same methods as the
production façade, which records the calls in their order and can fail at
one named call.

**The boundary of this module is not installed here.**  The guard of the
process lives in the report directory of this batch and the run lives in
the ``runner.py`` of the same directory.  The guard is installed by that
runner *before* pytest, before any plugin and before any import of a
candidate module, so the refusal of the operating system events happens
inside the event itself and before the action.  A plain
``pytest tools/test_v0_s3_native_custody.py`` is **not** an authorised
entry of this package: the plan of the batch names the runner and only
the runner.

This module has no entry point of its own.  It has no ``--run`` mode, it
has no counter snapshot and it has no exemption of its own: the original
shared counter is observed once before and once after the batch by the
outer runner, and it is never written, never refunded and never revived.

The declaration of the Windows primitives is checked through the **real
production declaration builder** with an injected primitive table.  The
builder is the one of ``tools/v0_s3_native_broker.py`` and it is the one
that a real run uses; only the native library is missing.  The ``ctypes``
module itself is loaded by the trusted runner in the one finite window
that the plan of the batch names, before this module is imported.
"""
import ctypes
import hashlib
import json
import os
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
    BrokerCore, BrokerError, BrokerLoop, CreatedProcess, WindowsApi,
    _declare_windows_primitives, _PosixPipeEndpoint, _windows_api_types,
    build_broker_command, role_command)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, CustodyError, HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_MISSING_SECONDS, MAX_FRAME_BYTES, MAX_FRAMES, NativeCustodySession,
    decode_command, decode_frame, decode_reply, encode_command, enforce_child_budget,
    validate_launch_plan)


# -- the in-process façades ------------------------------------------------

# The stable broker codes of the production Windows façade.  Every entry
# names the production position that raises the code, so that the mapping
# of the façade is proved against the production source and not against a
# wish of the test.  The production file is not changed by this package,
# so the positions below are the positions of the candidate.
FAKE_FAILURE_CODES = {
    'create_job': ('BROKER_JOB_CREATE_FAILED',
                   'WindowsApi.create_job -> tools/v0_s3_native_broker.py'),
    'job_limit': ('BROKER_JOB_LIMIT_FAILED',
                  'WindowsApi.set_job_kill_on_close -> tools/v0_s3_native_broker.py'),
    'terminate_job': ('BROKER_TERMINATE_FAILED',
                      'WindowsApi.terminate_job -> tools/v0_s3_native_broker.py'),
    'query_job': ('BROKER_JOB_QUERY_UNKNOWN',
                  'WindowsApi.job_process_ids -> tools/v0_s3_native_broker.py'),
    'create': ('BROKER_PROCESS_CREATE_FAILED',
               'WindowsApi.create_process_suspended -> tools/v0_s3_native_broker.py'),
    'assign': ('BROKER_ASSIGN_FAILED',
               'WindowsApi.assign_process_to_job -> tools/v0_s3_native_broker.py'),
    'resume': ('BROKER_RESUME_FAILED',
               'WindowsApi.resume_thread -> tools/v0_s3_native_broker.py'),
    'terminate': ('BROKER_TERMINATE_FAILED',
                  'WindowsApi.terminate_process -> tools/v0_s3_native_broker.py'),
    'close': ('BROKER_HANDLE_CLOSE_FAILED',
              'WindowsApi.close_handle -> tools/v0_s3_native_broker.py'),
    'pipe': ('BROKER_PIPE_FAILED',
             'WindowsApi.create_pipe -> tools/v0_s3_native_broker.py'),
}


def _failure_points(value):
    """The failure points that a façade was asked to fail at.

    An unknown failure point is refused here and not ignored: a façade
    that cannot fail where it was told to fail would report a success
    that never happened.
    """
    if value is None:
        return frozenset()
    names = (value,) if isinstance(value, str) else tuple(value)
    unknown = sorted(set(names) - set(FAKE_FAILURE_CODES))
    if unknown:
        raise BrokerError('BROKER_FAKE_FAILURE_POINT_UNKNOWN', ','.join(unknown))
    return frozenset(names)


class FakeWin32:
    """The in-process façade of the Windows primitives.

    The façade has the same methods as the production façade.  It records
    the calls in their order, it can fail at one named call and it never
    creates a process, never opens a socket and never touches a file: it
    is a pure in-process object, and the assertions of this package are
    made on its record, not on a claim of the implementation.

    A failure of the façade raises the **stable broker code of the
    production façade** at that position, never a code of the test: the
    broker reacts to its own codes, and a façade that raised a foreign
    code would drive a branch that the production source does not have.
    """

    def __init__(self, *, fail_at=None, job_process_ids=None, stream_payload=None):
        self.fail_at = fail_at
        self.failures_requested = _failure_points(fail_at)
        self.failure_fired = False
        self.calls = []
        self.closed = []
        self.terminated = []
        self.assigned = []
        self.resumed = []
        self.created = []
        self.inherited = []
        self._job_ids = list(job_process_ids) if job_process_ids is not None else []
        self._stream_payload = dict(stream_payload or {})
        self._streams = {}
        self.allocated = []
        self._next_handle = 100
        self._next_pid = 4000

    # -- helpers -----------------------------------------------------------
    def _handle(self):
        self._next_handle += 1
        self.allocated.append(self._next_handle)
        return self._next_handle

    def _fail(self, name):
        """Fail at one named call with the code of the production source.

        The failure point is recorded: a test that asked for a failure
        can prove that the failure really happened and did not pass
        because the point was never reached.
        """
        if name in self.failures_requested:
            self.failure_fired = True
            code, _position = FAKE_FAILURE_CODES[name]
            raise BrokerError(code, 'FAKE_FAILURE_AT_' + name.upper())

    def names(self):
        return [call[0] for call in self.calls]

    # -- the job -----------------------------------------------------------
    def create_job(self):
        # The handle that the façade really allocates is the handle that
        # the record carries: the job handle of the round is never a
        # guess and never a placeholder.
        handle = self._handle()
        self.calls.append(('create_job', handle))
        self._fail('create_job')
        return handle

    def set_job_kill_on_close(self, job):
        self.calls.append(('set_job_kill_on_close', job))
        self._fail('job_limit')

    def terminate_job(self, job, exit_code):
        self.calls.append(('terminate_job', job, exit_code))
        self._fail('terminate_job')
        for entry in self.created:
            entry['exited'] = True

    def job_process_ids(self, job):
        self.calls.append(('job_process_ids', job))
        self._fail('query_job')
        if len(self._job_ids) > 17:
            raise BrokerError('BROKER_DESCENDANT_LIMIT', 'count=%d' % len(self._job_ids))
        return list(self._job_ids)

    # -- the processes -----------------------------------------------------
    def create_process_suspended(self, *, executable, arguments, working_directory,
                                  stdout_handle, stderr_handle, environment=None):
        self.calls.append(('create_process_suspended', executable, tuple(arguments)))
        self._fail('create')
        self._next_pid += 1
        entry = {'pid': self._next_pid, 'exited': False, 'handle': self._handle(),
                 'thread': self._handle()}
        self.created.append(entry)
        self.inherited.append((stdout_handle, stderr_handle))
        return CreatedProcess(entry['handle'], entry['thread'], entry['pid'],
                              creation_time=17000000000000000)

    def assign_process_to_job(self, job, process):
        self.calls.append(('assign_process_to_job', job, process))
        self._fail('assign')
        self.assigned.append((job, process))

    def resume_thread(self, thread):
        self.calls.append(('resume_thread', thread))
        self._fail('resume')
        self.resumed.append(thread)

    def terminate_process(self, process, exit_code):
        self.calls.append(('terminate_process', process, exit_code))
        self._fail('terminate')
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
        self._fail('close')
        self.closed.append(handle)

    # -- the pipes ---------------------------------------------------------
    def create_pipe(self, name):
        self.calls.append(('create_pipe', name))
        self._fail('pipe')
        read = self._handle()
        write = self._handle()
        self._streams[read] = name
        self._streams[write] = name + '-write'
        return read, write

    def read_stream(self, handle, size):
        payload = self._stream_payload.get(self._streams.get(handle, ''), b'')
        if not payload:
            return b''
        self._stream_payload[self._streams.get(handle, '')] = b''
        return payload

    def write_stream(self, handle, data):
        self.calls.append(('write_stream', handle, len(data)))


class MemoryChannel:
    """The in-process transport of the private control channel.

    The transport is a pair of queues.  It never opens a pipe, a socket
    or a file and it never starts a process.
    """

    def __init__(self):
        self.inbound = queue.Queue()
        self.outbound = []
        self.closed = False
        self.eof = False
        self.bound_deadline = None

    def bind_deadline(self, deadline):
        self.bound_deadline = deadline

    def read(self, timeout):
        try:
            return self.inbound.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return b'' if self.eof else None

    def write(self, raw):
        self.outbound.append(raw)

    def close(self):
        self.closed = True
        return {'write_end_closed': True, 'read_end_closed': True,
                'reader_finished': True}


class FakeBrokerProcess:
    """The in-process stand-in of the original handle of the broker.

    The stand-in speaks the closed frame protocol of the private channel
    and it understands the **deadline aware** interface of the
    production handle: it binds an absolute deadline and every write
    carries one.  A stand-in that did not understand the deadline would
    not be a stand-in of the production handle.
    """

    channel_deadline_aware = True

    def __init__(self, plan, nonce, kinds=('READY', 'STATUS', 'STOPPED'),
                 write_fails=False, read_raises=None, raw_frames=None):
        self.plan = plan
        self.nonce = nonce
        self.pid = 4242
        self.executable = 'C:/Windows/py.exe'
        self.executable_sha256 = 'f' * 64
        self.inbound = queue.Queue()
        self.outbound = []
        self.closed = False
        self.close_count = 0
        self.read_raises = read_raises
        self.write_fails = write_fails
        self.raw_frames = list(raw_frames or [])
        self.bound_deadline = None
        self.write_deadlines = []
        states = {'READY': 'ARMED', 'STATUS': 'RUNNING', 'STOPPED': 'RELEASED',
                  'REFUSED': 'UNKNOWN_RETAINED'}
        for index, kind in enumerate(kinds, start=1):
            self.inbound.put(_reply_frame(kind, states[kind], {}, plan, nonce, index))
        for raw in self.raw_frames:
            self.inbound.put(raw)

    def bind_channel_deadline(self, deadline):
        if self.bound_deadline is not None and deadline > self.bound_deadline:
            raise BrokerError('BROKER_DEADLINE_EXTENDED')
        self.bound_deadline = deadline
        return deadline

    def write(self, raw, deadline=None):
        self.write_deadlines.append(deadline)
        if self.write_fails:
            raise BrokerError('BROKER_PIPE_WRITE_FAILED')
        self.outbound.append(raw)

    def read(self, timeout):
        if self.read_raises is not None:
            raise self.read_raises
        try:
            return self.inbound.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return None

    def close(self):
        self.closed = True
        self.close_count += 1
        return {'channel_closed': True, 'process_exited': True,
                'process_handle_released': True}


class Clock:
    """A clock that only moves when the test moves it."""

    def __init__(self, value, step=0.0):
        self.value = float(value)
        self.step = float(step)

    def __call__(self):
        current = self.value
        if self.step:
            self.value += self.step
        return current

    def advance(self, seconds):
        self.value += float(seconds)


# -- the recording primitive table -----------------------------------------

class RecordingPrimitive:
    """One primitive of a table that records its declaration.

    The primitive is never called: a call would be a native call and
    this package never makes one.  It only carries the declaration that
    the production code applied to it.
    """

    def __init__(self, name):
        self.name = name
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        raise BrokerError('BROKER_PRIMITIVE_NOT_CALLED', self.name)


class RecordingTable:
    """A primitive table that records the declaration of every primitive.

    The table is injected into the **production** declaration builder,
    so the declarations that are checked here are the declarations that a
    real run uses.
    """

    def __init__(self):
        self.primitives = {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        primitive = self.primitives.get(name)
        if primitive is None:
            primitive = RecordingPrimitive(name)
            self.primitives[name] = primitive
        return primitive

    def names(self):
        return sorted(self.primitives)


# -- the helpers of the tests ----------------------------------------------

def plan_document(**overrides):
    """A valid closed plan document."""
    document = {
        'schema': 'lvw.s3-native-custody-plan/1',
        'run_id': 'native-custody-01',
        'candidate_sha': 'a' * 40,
        'authorization_sha256': 'b' * 64,
        'lease_expires_at': time.time() + 3600.0,
        'max_runtime_seconds': 600,
        'roles': [
            {'role': 'COMFY',
             'tools': [{'path': 'C:/ComfyUI-aki-v2/python/python.exe', 'sha256': 'c' * 64},
                       {'path': 'C:/ComfyUI-aki-v2/ComfyUI/main.py', 'sha256': 'd' * 64}],
             'data': {'user_directory': 'user'},
             'log': 'temp/native/comfy.log'},
            {'role': 'OLLAMA',
             'tools': [{'path': 'C:/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe',
                        'sha256': 'e' * 64}],
             'data': {},
             'log': 'temp/native/ollama.log'},
        ],
    }
    document.update(overrides)
    return document


def sampler_role():
    return {'role': 'SAMPLER',
            'tools': [{'path': 'C:/ComfyUI-aki-v2/python/python.exe', 'sha256': 'c' * 64},
                      {'path': 'C:/lvw/tools/v0_s2_native_sampler.py', 'sha256': '1' * 64}],
            'data': {'nvidia_exe': 'C:/Windows/System32/nvidia-smi.exe',
                     'nvidia_sha256': '2' * 64,
                     'max_seconds': 600},
            'log': 'temp/native/sampler.log'}


def _reply_frame(kind, state, detail, plan, nonce, sequence):
    return json.dumps({'schema': CHANNEL_SCHEMA, 'kind': kind, 'run_id': plan.run_id,
                       'candidate_sha': plan.candidate_sha,
                       'authorization_sha256': plan.authorization_sha256,
                       'nonce': nonce, 'sequence': sequence, 'state': state,
                       'detail': detail},
                      ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8') + b'\n'


def _core(tmp_path, *, win32=None, document=None):
    plan = validate_launch_plan(document or plan_document())
    return BrokerCore(win32=win32 or FakeWin32(), plan=plan, run_root=tmp_path)


# -- the plan ---------------------------------------------------------------

def test_a_valid_plan_is_accepted_and_closed():
    plan = validate_launch_plan(plan_document())
    assert plan.run_id == 'native-custody-01'
    assert [role['role'] for role in plan.roles] == ['COMFY', 'OLLAMA']
    assert plan.sealed['schema'] == 'lvw.s3-native-custody-plan/1'
    assert set(plan.sealed) == {'schema', 'run_id', 'candidate_sha',
                                'authorization_sha256', 'lease_expires_at',
                                'max_runtime_seconds', 'roles'}


def test_a_bool_runtime_is_refused():
    document = plan_document()
    document['max_runtime_seconds'] = True
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_RUNTIME_INVALID'
    else:
        raise AssertionError('a boolean runtime was accepted')


def test_a_float_runtime_is_refused():
    document = plan_document()
    document['max_runtime_seconds'] = 600.0
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_RUNTIME_INVALID'
    else:
        raise AssertionError('a float runtime was accepted')


def test_a_nonfinite_lease_is_refused():
    document = plan_document()
    document['lease_expires_at'] = float('inf')
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LEASE_INVALID'
    else:
        raise AssertionError('a nonfinite lease was accepted')


def test_an_expired_lease_is_refused():
    document = plan_document(lease_expires_at=time.time() - 1.0)
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LEASE_EXPIRED'
    else:
        raise AssertionError('an expired lease was accepted')


def test_a_runtime_above_the_hard_cap_is_refused():
    document = plan_document(max_runtime_seconds=21601)
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_RUNTIME_INVALID'
    else:
        raise AssertionError('a runtime above the hard cap was accepted')
    assert validate_launch_plan(plan_document(max_runtime_seconds=21600))


def test_an_unknown_role_is_refused():
    document = plan_document()
    document['roles'][0]['role'] = 'WORKER'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLE_INVALID'
    else:
        raise AssertionError('an unknown role was accepted')


def test_a_missing_required_role_is_refused():
    document = plan_document()
    document['roles'] = [document['roles'][0]]
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLES_INVALID'
    else:
        raise AssertionError('a plan without Ollama was accepted')


def test_a_duplicate_role_is_refused():
    document = plan_document()
    document['roles'].append(dict(document['roles'][0]))
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLE_INVALID'
    else:
        raise AssertionError('a duplicated role was accepted')


def test_an_extra_plan_key_is_refused():
    document = plan_document()
    document['environment'] = {'PATH': 'x'}
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_KEY_SET_INVALID'
    else:
        raise AssertionError('a plan with an extra key was accepted')


def test_an_arbitrary_argv_key_is_refused():
    document = plan_document()
    document['roles'][0]['argv'] = ['C:/Windows/System32/cmd.exe', '/c', 'whoami']
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLE_INVALID'
    else:
        raise AssertionError('a role with an argv key was accepted')


def test_a_shell_key_in_a_role_is_refused():
    document = plan_document()
    document['roles'][0]['data'] = {'shell': 'whoami'}
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLE_DATA_INVALID'
    else:
        raise AssertionError('a role with a shell key was accepted')


def test_a_relative_tool_path_is_refused():
    document = plan_document()
    document['roles'][0]['tools'][0]['path'] = 'python.exe'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_TOOL_INVALID'
    else:
        raise AssertionError('a relative tool path was accepted')


def test_an_escaping_tool_path_is_refused():
    document = plan_document()
    document['roles'][0]['tools'][0]['path'] = 'C:/Windows/../../etc/passwd'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_TOOL_INVALID'
    else:
        raise AssertionError('an escaping tool path was accepted')


def test_a_tool_digest_is_refused():
    document = plan_document()
    document['roles'][0]['tools'][0]['sha256'] = 'NOT-A-DIGEST'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_TOOL_INVALID'
    else:
        raise AssertionError('a malformed tool digest was accepted')


def test_an_escaping_log_reference_is_refused():
    document = plan_document()
    document['roles'][0]['log'] = '../../etc/passwd'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    else:
        raise AssertionError('an escaping log reference was accepted')


def test_an_absolute_log_reference_is_refused():
    document = plan_document()
    document['roles'][0]['log'] = 'C:/Windows/temp/comfy.log'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    else:
        raise AssertionError('an absolute log reference was accepted')


def test_a_drive_relative_log_reference_is_refused():
    document = plan_document()
    document['roles'][0]['log'] = 'C:comfy.log'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    else:
        raise AssertionError('a drive relative log reference was accepted')


def test_an_alternate_data_stream_log_reference_is_refused():
    document = plan_document()
    document['roles'][0]['log'] = 'temp/native/comfy.log:stream'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    else:
        raise AssertionError('an alternate data stream log reference was accepted')


def test_a_unc_or_backslash_log_reference_is_refused():
    for reference in ('\\\\server\\share\\comfy.log', 'temp\\native\\comfy.log'):
        document = plan_document()
        document['roles'][0]['log'] = reference
        try:
            validate_launch_plan(document)
        except CustodyError as error:
            assert error.code == 'CUSTODY_PLAN_LOG_INVALID', reference
        else:
            raise AssertionError('a UNC log reference was accepted: ' + reference)


def test_a_posix_absolute_log_reference_is_refused():
    document = plan_document()
    document['roles'][0]['log'] = '/var/log/comfy.log'
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    else:
        raise AssertionError('a POSIX absolute log reference was accepted')


def test_a_legal_relative_log_reference_is_accepted():
    for reference in ('comfy.log', 'temp/native/comfy.log', 'temp/native/sub/comfy.log'):
        document = plan_document()
        document['roles'][0]['log'] = reference
        plan = validate_launch_plan(document)
        assert plan.roles[0]['log'] == reference


def test_an_illegal_log_reference_creates_nothing(tmp_path):
    # The oracle of this check is the façade of the round: it records
    # every call of the broker, so it shows that the refusal happened
    # before the job, before the process and before any log of the round.
    win32 = FakeWin32()
    document = plan_document()
    document['roles'][0]['log'] = 'C:/Windows/temp/comfy.log'
    refused = False
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        refused = True
        assert error.code == 'CUSTODY_PLAN_LOG_INVALID'
    assert refused is True
    # Zero call, zero job and zero process of the round.
    assert win32.calls == []
    assert win32.created == []
    # Zero log: the run root holds nothing at all and the reference that
    # points outside of it was not written next to the sources either.
    assert list(tmp_path.rglob('*')) == []
    assert not (Path.cwd() / 'C:').exists()
    assert not (Path.cwd() / 'comfy.log').exists()


def test_the_broker_validates_the_plan_before_it_consumes_it():
    # The broker consumes a plan only after it validated it itself, with
    # the same closed rules: the validation of the parent is not the only
    # boundary of the round.
    source = (PACK_ROOT / 'tools/v0_s3_native_broker.py').read_text(encoding='utf-8')
    validation = source.index('validate_launch_plan(document, now=time.time())')
    creation = source.index('core = BrokerCore(win32=win32, plan=plan')
    assert validation < creation
    assert 'from tools.v0_s3_native_custody import' in source
    assert 'validate_launch_plan' in source.split('def main(')[0]


def test_a_role_data_key_is_refused():
    document = plan_document()
    document['roles'][0]['data'] = {'user_directory': 'user', 'eval': 'x'}
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        assert error.code == 'CUSTODY_PLAN_ROLE_DATA_INVALID'
    else:
        raise AssertionError('a role with an extra data key was accepted')


def test_no_remaining_child_budget_is_refused():
    plan = validate_launch_plan(plan_document())
    try:
        enforce_child_budget(plan, parent_child_remaining_seconds=0)
    except CustodyError as error:
        assert error.code == 'CUSTODY_NO_CHILD_BUDGET_REMAINING'
    else:
        raise AssertionError('a round without a remaining budget was accepted')


def test_a_runtime_above_the_child_budget_is_refused():
    plan = validate_launch_plan(plan_document(max_runtime_seconds=600))
    try:
        enforce_child_budget(plan, parent_child_remaining_seconds=599)
    except CustodyError as error:
        assert error.code == 'CUSTODY_CHILD_BUDGET_TOO_SMALL'
    else:
        raise AssertionError('a runtime above the remaining budget was accepted')
    assert enforce_child_budget(plan, parent_child_remaining_seconds=600) == 600


# -- M01: the user directory is one closed segment --------------------------

def test_the_user_directory_is_one_closed_segment():
    refused = []
    for name in ('safe/../../outside', 'safe\\..\\outside', 'a/b', 'a\\b', 'a:b',
                 '..', '.', 'NUL', 'nul', 'CON', 'com1', 'con.txt', 'LPT9',
                 '', 'a' * 65, ' user', 'user ', 'user.', 'a..b'):
        document = plan_document()
        document['roles'][0]['data']['user_directory'] = name
        try:
            validate_launch_plan(document)
        except CustodyError as error:
            assert error.code == 'CUSTODY_PLAN_ROLE_DATA_INVALID', name
            refused.append(name)
        else:
            raise AssertionError('an illegal user directory was accepted: ' + repr(name))
    assert len(refused) == 19


def test_the_legal_user_directory_is_accepted():
    for name in ('user', 'User', 'user_1', 'user-1', 'a' * 64):
        document = plan_document()
        document['roles'][0]['data']['user_directory'] = name
        plan = validate_launch_plan(document)
        assert plan.roles[0]['data']['user_directory'] == name


def test_the_user_directory_refusal_creates_nothing(tmp_path):
    # The oracle is the façade of the round and the run root: the
    # refusal happens before the job, before the process and before any
    # directory of the round exists.
    win32 = FakeWin32()
    document = plan_document()
    document['roles'][0]['data']['user_directory'] = 'safe/../../outside'
    refused = False
    try:
        validate_launch_plan(document)
    except CustodyError as error:
        refused = True
        assert error.code == 'CUSTODY_PLAN_ROLE_DATA_INVALID'
    assert refused is True
    assert win32.calls == []
    assert win32.created == []
    assert list(tmp_path.rglob('*')) == []


# -- m01: the sealed plan is a copy and the seal is one definition --------

def test_the_presented_seal_cannot_change_the_command_of_a_role():
    plan = validate_launch_plan(plan_document())
    plan.sealed['roles'][0]['tools'][0]['path'] = 'C:/foreign.exe'
    plan.sealed['roles'][0]['data']['user_directory'] = 'foreign'
    command = role_command(plan.roles[0], '/tmp/round', [])
    assert command['executable'] == 'C:/ComfyUI-aki-v2/python/python.exe'
    assert '--user-directory' in command['arguments']
    assert command['arguments'][command['arguments'].index('--user-directory') + 1] \
        == os.path.join('/tmp/round', 'user')


def test_the_roles_of_the_plan_cannot_be_changed_by_the_caller():
    plan = validate_launch_plan(plan_document())
    try:
        plan.roles[0]['tools'][0]['path'] = 'C:/foreign.exe'
    except TypeError:
        pass
    else:
        raise AssertionError('the roles of the plan were writable')
    command = role_command(plan.roles[0], '/tmp/round', [])
    assert command['executable'] == 'C:/ComfyUI-aki-v2/python/python.exe'


def test_the_seal_bytes_and_the_digest_are_one_definition():
    plan = validate_launch_plan(plan_document())
    raw = plan.sealed_bytes()
    assert hashlib.sha256(raw).hexdigest() == plan.sealed_sha256()
    assert json.loads(raw.decode('utf-8')) == plan.sealed
    # The seal of the plan is stable: it is the snapshot of the
    # validation and it does not change with the presented copy.
    plan.sealed['roles'][0]['log'] = 'foreign.log'
    assert plan.sealed_sha256() == hashlib.sha256(raw).hexdigest()


# -- M11: the nonce of the round -------------------------------------------

def test_the_default_nonce_is_the_closed_form():
    session = NativeCustodySession(plan=plan_document(), run_root='/tmp/round',
                                   parent_child_remaining_seconds=60)
    assert len(session.evidence()['channel']['nonce']) == 32
    assert all(character in '0123456789abcdef'
               for character in session.evidence()['channel']['nonce'])


def test_an_illegal_nonce_is_refused_before_anything_exists(tmp_path):
    refused = False
    try:
        NativeCustodySession(plan=plan_document(), run_root=tmp_path,
                             parent_child_remaining_seconds=60,
                             nonce='custody-' + 'a' * 32)
    except CustodyError as error:
        refused = True
        assert error.code == 'CUSTODY_NONCE_INVALID'
    assert refused is True
    assert list(tmp_path.rglob('*')) == []


def test_the_broker_command_refuses_an_illegal_nonce():
    for nonce in ('custody-' + 'a' * 32, 'A' * 32, 'a' * 31, 'a' * 33, ''):
        try:
            build_broker_command(plan_path='C:/round/plan.json',
                                 plan_sha256='b' * 64,
                                 run_root='C:/round', nonce=nonce)
        except BrokerError as error:
            assert error.code == 'BROKER_NONCE_INVALID', nonce
        else:
            raise AssertionError('an illegal nonce was accepted: ' + repr(nonce))


def test_the_broker_command_keeps_the_fixed_private_parameter():
    command = build_broker_command(plan_path='C:/round/plan.json',
                                    plan_sha256='b' * 64,
                                    run_root='C:/round', nonce='a' * 32)
    # The command is fixed: the interpreter, the isolated flags, this
    # broker and the four private parameters of the round.  There is no
    # argument vector of a caller and no dynamic import.
    assert command[1:3] == ['-I', '-B']
    assert command[3].endswith('v0_s3_native_broker.py')
    assert command[4:] == ['--plan', 'C:/round/plan.json',
                           '--plan-sha256', 'b' * 64,
                           '--run-root', 'C:/round',
                           '--nonce', 'a' * 32]


def test_the_launcher_refuses_before_it_creates_a_directory(tmp_path):
    from tools.v0_s3_native_broker import launch_broker
    try:
        launch_broker(None, tmp_path, 'not-a-nonce')
    except BrokerError as error:
        assert error.code in ('BROKER_PLATFORM_UNSUPPORTED', 'BROKER_NONCE_INVALID')
    else:
        raise AssertionError('the broker was launched with an illegal nonce')
    # Nothing of the round exists: no directory and no plan document.
    assert list(tmp_path.rglob('*')) == []


# -- the private control channel -------------------------------------------

def test_a_foreign_nonce_is_refused():
    plan = validate_launch_plan(plan_document())
    raw = encode_command('STATUS', run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                          authorization_sha256=plan.authorization_sha256,
                          nonce='a' * 32, sequence=1)
    try:
        decode_command(raw, run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                       authorization_sha256=plan.authorization_sha256,
                       nonce='b' * 32, last_sequence=None)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_IDENTITY_MISMATCH'
    else:
        raise AssertionError('a foreign nonce was accepted')


def test_a_repeated_sequence_is_refused():
    plan = validate_launch_plan(plan_document())
    raw = encode_command('STATUS', run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                          authorization_sha256=plan.authorization_sha256,
                          nonce='a' * 32, sequence=2)
    try:
        decode_command(raw, run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                       authorization_sha256=plan.authorization_sha256,
                       nonce='a' * 32, last_sequence=2)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_SEQUENCE_INVALID'
    else:
        raise AssertionError('a repeated sequence was accepted')


def test_an_extra_key_in_a_command_is_refused():
    plan = validate_launch_plan(plan_document())
    frame = {'schema': CHANNEL_SCHEMA, 'command': 'STATUS', 'run_id': plan.run_id,
             'candidate_sha': plan.candidate_sha,
             'authorization_sha256': plan.authorization_sha256,
             'nonce': 'a' * 32, 'sequence': 1, 'pid': 4242}
    raw = json.dumps(frame, sort_keys=True, separators=(',', ':')).encode('utf-8')
    try:
        decode_command(raw, run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                       authorization_sha256=plan.authorization_sha256,
                       nonce='a' * 32, last_sequence=None)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_INVALID'
    else:
        raise AssertionError('a command with an extra key was accepted')


def test_a_frame_at_the_limit_is_accepted_and_one_over_is_refused():
    prefix = b'{"x":"'
    suffix = b'"}'
    exact = prefix + b'a' * (MAX_FRAME_BYTES - len(prefix) - len(suffix)) + suffix
    assert len(exact) == MAX_FRAME_BYTES
    assert isinstance(decode_frame(exact), dict)
    over = prefix + b'a' * (MAX_FRAME_BYTES + 1 - len(prefix) - len(suffix)) + suffix
    assert len(over) == MAX_FRAME_BYTES + 1
    try:
        decode_frame(over)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_TOO_LARGE'
    else:
        raise AssertionError('an oversize frame was accepted')


def test_an_oversize_command_is_refused():
    plan = validate_launch_plan(plan_document())
    try:
        encode_command('STATUS', run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                       authorization_sha256=plan.authorization_sha256,
                       nonce='a' * (MAX_FRAME_BYTES + 16), sequence=1)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_TOO_LARGE'
    else:
        raise AssertionError('an oversize command was encoded')


def test_a_reply_with_a_foreign_identity_is_refused():
    plan = validate_launch_plan(plan_document())
    raw = _reply_frame('STATUS', 'RUNNING', {}, plan, 'b' * 32, 1)
    try:
        decode_reply(raw, run_id=plan.run_id, candidate_sha=plan.candidate_sha,
                     authorization_sha256=plan.authorization_sha256,
                     nonce='a' * 32, last_sequence=None)
    except CustodyError as error:
        assert error.code == 'CUSTODY_FRAME_IDENTITY_MISMATCH'
    else:
        raise AssertionError('a reply with a foreign nonce was accepted')


# -- the broker core --------------------------------------------------------

def test_the_success_path_is_suspend_assign_resume(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    names = win32.names()
    assert names.count('create_process_suspended') == 2
    assert names.count('assign_process_to_job') == 2
    assert names.count('resume_thread') == 2
    first = names.index('create_process_suspended')
    assert names.index('assign_process_to_job') > first
    assert names.index('resume_thread') > names.index('assign_process_to_job')
    assert core.state == 'RUNNING'
    assert all(record['assigned'] and record['resumed'] for record in core.records)
    assert core.job_kill_on_close is True


def test_the_child_inherits_only_its_own_streams(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    # The job handle is never offered to a child and the two write ends
    # are the only handles that a child may inherit.
    job = [call[1] for call in win32.calls if call[0] == 'create_job'][0]
    for stdout_handle, stderr_handle in win32.inherited:
        assert job not in (stdout_handle, stderr_handle)
    assert len(win32.inherited) == 2


def test_a_create_failure_creates_nothing(tmp_path):
    win32 = FakeWin32(fail_at='create')
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_PROCESS_CREATE_FAILED'
    else:
        raise AssertionError('a failed creation did not refuse')
    assert win32.failure_fired is True
    assert win32.names().count('create_process_suspended') == 1
    assert core.state == 'UNKNOWN_RETAINED'
    assert core.records[0]['created'] is False


def test_an_assign_failure_stops_only_the_new_suspended_process(tmp_path):
    win32 = FakeWin32(fail_at='assign')
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_ASSIGN_FAILED'
    else:
        raise AssertionError('a failed assignment did not refuse')
    assert win32.failure_fired is True
    # Exactly one creation, no retry without the job.
    assert win32.names().count('create_process_suspended') == 1
    assert win32.names().count('assign_process_to_job') == 1
    # The suspended process was stopped through its own handle.
    assert len(win32.terminated) == 1
    assert win32.terminated[0] == win32.created[0]['handle']
    # The process never ran.
    assert win32.resumed == []
    assert core.state == 'UNKNOWN_RETAINED'
    assert core.records[0]['resumed'] is False


def test_a_resume_failure_keeps_the_round_unknown(tmp_path):
    win32 = FakeWin32(fail_at='resume')
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_RESUME_FAILED'
    else:
        raise AssertionError('a failed resume did not refuse')
    assert win32.failure_fired is True
    assert win32.names().count('create_process_suspended') == 1
    assert win32.names().count('resume_thread') == 1
    assert core.state == 'UNKNOWN_RETAINED'


def test_a_job_creation_failure_creates_nothing(tmp_path):
    win32 = FakeWin32(fail_at='create_job')
    core = _core(tmp_path, win32=win32)
    try:
        core.arm()
    except BrokerError as error:
        assert error.code == 'BROKER_JOB_CREATE_FAILED'
    else:
        raise AssertionError('a failed job creation did not refuse')
    assert win32.failure_fired is True
    assert core.state == 'UNKNOWN_RETAINED'
    assert core.failures == [{'stage': 'create_job', 'code': 'BROKER_JOB_CREATE_FAILED'}]
    # Nothing of the round exists: no process and no other handle.
    assert win32.created == []
    assert win32.closed == []


def test_a_job_limit_failure_closes_the_job_handle(tmp_path):
    win32 = FakeWin32(fail_at='job_limit')
    core = _core(tmp_path, win32=win32)
    try:
        core.arm()
    except BrokerError as error:
        assert error.code == 'BROKER_JOB_LIMIT_FAILED'
    else:
        raise AssertionError('a failed job limit did not refuse')
    assert win32.failure_fired is True
    assert core.state == 'UNKNOWN_RETAINED'
    # The job of the round is closed again and it is not left open.
    job = [call[1] for call in win32.calls if call[0] == 'create_job'][0]
    assert job in win32.closed
    assert win32.created == []


def test_a_pipe_failure_creates_nothing(tmp_path):
    win32 = FakeWin32(fail_at='pipe')
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_PIPE_FAILED'
    else:
        raise AssertionError('a failed pipe did not refuse')
    assert win32.failure_fired is True
    assert core.state == 'UNKNOWN_RETAINED'
    # The process of the role was never created.
    assert win32.created == []
    assert core.records[0]['created'] is False


def test_a_failed_termination_stays_visible(tmp_path):
    # The termination of the owned process fails as well.  The failure of
    # the termination is never reported as a successful stop.
    win32 = FakeWin32(fail_at=('assign', 'terminate'))
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_ASSIGN_FAILED'
    else:
        raise AssertionError('a failed assignment did not refuse')
    assert win32.failure_fired is True
    assert core.state == 'UNKNOWN_RETAINED'
    # The process was not stopped and the failure is on the record.
    assert win32.terminated == []
    assert core.records[0]['terminated'] is False
    assert {'stage': 'terminate', 'reason': 'ASSIGN_FAILED',
            'code': 'BROKER_TERMINATE_FAILED'} in core.failures


def test_a_job_termination_failure_is_not_a_release(tmp_path):
    win32 = FakeWin32(fail_at='terminate_job')
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    assert win32.failure_fired is True
    # The job of the round was not terminated and the round is not a
    # release: the failure of the termination is on the record.
    assert core.job_terminated is False
    assert core.state == 'UNKNOWN_RETAINED'
    assert {'stage': 'terminate_job',
            'code': 'BROKER_TERMINATE_FAILED'} in core.failures


def test_an_unknown_failure_point_is_refused():
    try:
        FakeWin32(fail_at='not_a_real_call')
    except BrokerError as error:
        assert error.code == 'BROKER_FAKE_FAILURE_POINT_UNKNOWN'
    else:
        raise AssertionError('an unknown failure point was accepted')


def test_a_foreign_process_is_never_stopped(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    owned = [entry['handle'] for entry in win32.created]
    assert set(win32.terminated) <= set(owned)
    # The façade of this package has no pid based stop at all: a record of
    # another owner can therefore never reach the operating system.
    assert not hasattr(win32, 'terminate_by_pid')
    assert not hasattr(win32, 'terminate_named')
    assert [record['pid'] for record in core.records] == [entry['pid']
                                                          for entry in win32.created]


def test_a_partial_role_failure_stops_the_earlier_roles(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    calls = {'count': 0}
    original = win32.create_process_suspended

    def failing(**kwargs):
        calls['count'] += 1
        if calls['count'] == 2:
            raise BrokerError('BROKER_PROCESS_CREATE_FAILED')
        return original(**kwargs)

    win32.create_process_suspended = failing
    try:
        core.launch()
    except BrokerError as error:
        assert error.code == 'BROKER_PROCESS_CREATE_FAILED'
    else:
        raise AssertionError('a partial launch did not refuse')
    assert core.state == 'UNKNOWN_RETAINED'
    # The job of the round was stopped, so the first role could not survive.
    assert 'terminate_job' in win32.names()
    assert len(core.records) == 2
    assert core.records[0]['created'] is True
    assert core.records[1]['created'] is False


def test_an_unknown_job_query_is_not_zero(tmp_path):
    win32 = FakeWin32(fail_at='query_job')
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    assert win32.failure_fired is True
    assert core.job_active_known is False
    assert core.job_active is None
    assert core.state == 'UNKNOWN_RETAINED'
    # The query of the job failed with the code of the production source.
    assert {'stage': 'query_job', 'code': 'BROKER_JOB_QUERY_UNKNOWN'} in core.failures


def test_an_over_limit_job_query_is_not_zero(tmp_path):
    win32 = FakeWin32(job_process_ids=list(range(18)))
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    assert core.job_active_known is False
    assert core.job_active is None
    assert core.state == 'UNKNOWN_RETAINED'


def test_a_close_failure_keeps_the_round_unknown(tmp_path):
    win32 = FakeWin32(fail_at='close')
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    assert win32.failure_fired is True
    assert core.job_closed is False
    assert core.state == 'UNKNOWN_RETAINED'
    assert any(item['stage'] == 'close_handle' for item in core.failures)
    # The close of a handle failed with the code of the production source.
    assert any(item['stage'] == 'close_handle'
               and item['code'] == 'BROKER_HANDLE_CLOSE_FAILED'
               for item in core.failures)


def test_a_stop_is_idempotent(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    first = core.stop('STOP')
    terminated = list(win32.terminated)
    closed = list(win32.closed)
    second = core.stop('STOP')
    assert list(win32.terminated) == terminated
    assert list(win32.closed) == closed
    assert second['state'] == first['state']
    assert core.state == 'RELEASED'
    assert core.job_active_known is True and core.job_active == 0


def test_the_job_is_closed_with_kill_on_close(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    job = [call[1] for call in win32.calls if call[0] == 'create_job'][0]
    assert job in win32.closed
    assert core.job_closed is True
    assert core.evidence()['job']['kill_on_job_close'] is True
    assert core.evidence()['job']['breakaway_allowed'] is False


# -- M10: the fixed command of the sampler ----------------------------------

def test_the_sampler_is_created_last_with_the_pids_of_the_services(tmp_path):
    document = plan_document()
    document['roles'].append(sampler_role())
    plan = validate_launch_plan(document)
    command = role_command(plan.roles[2], tmp_path, [11, 22])
    assert command['arguments'][0] == '-I'
    assert '--execute-sampler' in command['arguments']
    index = command['arguments'].index('--private-pids')
    # The parser of the sampler is ``type=int, nargs='+'``: every pid is
    # its own argument and never one argument with a space in it.
    assert command['arguments'][index + 1] == '11'
    assert command['arguments'][index + 2] == '22'
    assert command['arguments'][index + 3] == '--max-seconds'
    assert '11 22' not in command['arguments']
    assert command['executable'] == 'C:/ComfyUI-aki-v2/python/python.exe'


def test_the_sampler_command_matches_the_parser_of_the_sampler():
    # The oracle is the parser of the production sampler: the arguments
    # of the broker have to be the arguments that it parses.
    source = (PACK_ROOT / 'tools/v0_s2_native_sampler.py').read_text(encoding='utf-8')
    assert "'--private-pids',type=int,nargs='+'" in source


# -- M05: the pending resources of the round -------------------------------

def test_every_created_handle_enters_the_pending_table(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    pending = core._pending.pending()
    # The job of the round entered the table in the moment of its
    # creation and the core is its owner.
    assert [item['kind'] for item in pending] == ['job']
    assert pending[0]['owner'] == 'CORE'
    core.launch()
    pending = core._pending.pending()
    kinds = [item['kind'] for item in pending]
    owners = sorted(set(item['owner'] for item in pending))
    # Every resource of the round that is not closed yet is named: the
    # job, the original handles of the processes and the read ends that
    # the readers own.  The write ends went to the child and they are
    # not pending any more.
    assert kinds.count('job') == 1
    assert kinds.count('process') == 2
    assert kinds.count('thread') == 2
    assert kinds.count('pipe_read') == 4
    assert 'pipe_write' not in kinds
    assert owners == ['CORE', 'READER']
    core.stop('STOP')
    # Nothing of the round is left: every handle was closed and it left
    # the table.
    assert core._pending.pending() == []


def test_an_assign_failure_closes_the_read_ends_of_the_role(tmp_path):
    win32 = FakeWin32(fail_at='assign')
    core = _core(tmp_path, win32=win32)
    core.arm()
    try:
        core.launch()
    except BrokerError:
        pass
    else:
        raise AssertionError('a failed assignment did not refuse')
    # Every handle of this round was closed: the read ends of the role
    # are closed as well and they are not left to the collector.
    assert win32.closed
    assert core._pending.pending() == []
    assert core.evidence()['pending_resources'] == []


def test_a_handle_of_another_owner_is_never_touched(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    closed = set(win32.closed)
    # Only the handles that the façade of the round allocated were
    # closed: a handle of another owner was never touched.
    assert closed <= set(win32.allocated)
    job = [call[1] for call in win32.calls if call[0] == 'create_job'][0]
    assert job in closed


# -- M06: the cleanup of the round does not depend on the diagnosis --------

def test_a_cancellation_during_the_launch_releases_the_round(tmp_path):
    win32 = FakeWin32()
    original = win32.assign_process_to_job

    def cancelling(job, process):
        original(job, process)
        raise KeyboardInterrupt('synthetic cancellation')

    win32.assign_process_to_job = cancelling
    core = _core(tmp_path, win32=win32)
    core.arm()
    caught = None
    try:
        core.launch()
    except BaseException as error:
        caught = type(error).__name__
    # The cancellation continues to propagate after the cleanup.
    assert caught == 'KeyboardInterrupt'
    assert core.state == 'UNKNOWN_RETAINED'
    # Every handle of the round was closed before the failure left.
    assert core._pending.pending() == []
    assert win32.closed


def test_a_diagnostic_failure_does_not_block_the_cleanup(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()

    def broken():
        raise RuntimeError('synthetic diagnostic failure')

    core._collect_stream_counts = broken
    caught = None
    try:
        core.stop('STOP')
    except RuntimeError:
        caught = 'RuntimeError'
    # The first failure is not swallowed and the cleanup still happened.
    assert caught == 'RuntimeError'
    assert core._pending.pending() == []
    assert win32.closed


def test_a_write_failure_of_the_first_reply_releases_the_round(tmp_path):
    win32 = FakeWin32()
    plan = validate_launch_plan(plan_document())
    core = BrokerCore(win32=win32, plan=plan, run_root=tmp_path)

    class Broken:
        def write(self, raw):
            raise BrokenPipeError('synthetic writer failure')

    loop = BrokerLoop(core=core, transport=Broken(), plan=plan, nonce='a' * 32,
                      wall=lambda: 1000.0)
    caught = None
    try:
        loop.run()
    except BrokenPipeError:
        caught = 'BrokenPipeError'
    assert caught == 'BrokenPipeError'
    # The job of the round was released even though the first reply of
    # the round could not be written.
    assert core.state == 'UNKNOWN_RETAINED'
    assert win32.closed
    assert core._pending.pending() == []


# -- M09: a release needs the facts and not only the absence of a failure --

def test_a_release_needs_the_readers_to_be_joined(tmp_path):
    win32 = FakeWin32()
    release = threading.Event()
    original = win32.read_stream

    def blocking_read(handle, size):
        # The first reader of the round stays inside its read: it is a
        # reader that did not stop.
        if handle == 102:
            release.wait(20.0)
            return b''
        return original(handle, size)

    win32.read_stream = blocking_read
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    # A reader that is still alive is a fact of the round: the round is
    # not a release and the read end is not closed under the reader.
    assert core.state == 'UNKNOWN_RETAINED'
    assert any(item['stage'] == 'reader_not_stopped' for item in core.failures)
    assert any(state['alive'] for state in core.reader_states)
    # The reader is released before the check ends: no thread of the
    # round is left behind.
    release.set()
    for reader in core.readers:
        reader.join(5.0)
    assert not any(reader.is_alive() for reader in core.readers)


def test_a_read_error_is_not_the_end_of_a_stream(tmp_path):
    win32 = FakeWin32()

    def failing(handle, size):
        raise BrokerError('BROKER_STREAM_READ_FAILED', 'last_error=5')

    # The read of the children fails from the first read: the failure is
    # installed before the readers of the round start.
    win32.read_stream = failing
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    # The read error is a named error of the round and the round is not
    # a release.
    assert any(state['error'] == 'BROKER_STREAM_READ_FAILED'
               for state in core.reader_states)
    assert core.state == 'UNKNOWN_RETAINED'


def test_a_repeated_stop_does_not_close_twice(tmp_path):
    win32 = FakeWin32()
    core = _core(tmp_path, win32=win32)
    core.arm()
    core.launch()
    core.stop('STOP')
    closed = list(win32.closed)
    core.stop('STOP')
    assert list(win32.closed) == closed


# -- the broker loop --------------------------------------------------------

def _loop(tmp_path, *, channel, document=None, max_frames=MAX_FRAMES, now=None,
          clock=None):
    plan = validate_launch_plan(document or plan_document(), now=now)
    core = BrokerCore(win32=FakeWin32(), plan=plan, run_root=tmp_path)
    loop = BrokerLoop(core=core, transport=channel, plan=plan, nonce='a' * 32,
                      max_frames=max_frames, clock=clock,
                      wall=(lambda: now) if now is not None else None)
    return loop, core


def test_a_stop_command_answers_once(tmp_path):
    plan = validate_launch_plan(plan_document())
    channel = MemoryChannel()
    channel.inbound.put(encode_command('STOP', run_id=plan.run_id,
                                        candidate_sha=plan.candidate_sha,
                                        authorization_sha256=plan.authorization_sha256,
                                        nonce='a' * 32, sequence=1))
    loop, core = _loop(tmp_path, channel=channel)
    assert loop.run() == 0
    kinds = [json.loads(raw)['kind'] for raw in channel.outbound]
    assert kinds == ['READY', 'STATUS', 'STOPPED']
    assert core.stop_reason == 'STOP_COMMAND'
    assert core.state == 'RELEASED'


def test_a_status_command_is_answered(tmp_path):
    plan = validate_launch_plan(plan_document())
    channel = MemoryChannel()
    channel.inbound.put(encode_command('STATUS', run_id=plan.run_id,
                                        candidate_sha=plan.candidate_sha,
                                        authorization_sha256=plan.authorization_sha256,
                                        nonce='a' * 32, sequence=1))
    channel.inbound.put(encode_command('STOP', run_id=plan.run_id,
                                        candidate_sha=plan.candidate_sha,
                                        authorization_sha256=plan.authorization_sha256,
                                        nonce='a' * 32, sequence=2))
    loop, core = _loop(tmp_path, channel=channel)
    assert loop.run() == 0
    kinds = [json.loads(raw)['kind'] for raw in channel.outbound]
    assert kinds == ['READY', 'STATUS', 'STATUS', 'STOPPED']


def test_a_channel_eof_stops_the_round(tmp_path):
    channel = MemoryChannel()
    channel.eof = True
    loop, core = _loop(tmp_path, channel=channel)
    assert loop.run() == 4
    assert core.stop_reason == 'CHANNEL_EOF'
    assert core.state == 'UNKNOWN_RETAINED'


def test_the_absolute_lease_stops_the_round(tmp_path):
    document = plan_document(lease_expires_at=1001.0, max_runtime_seconds=600)
    channel = MemoryChannel()
    # The clock of the loop moves on its own, so that the whole schedule
    # of the round is checked without a long sleep.
    clock = Clock(0.0, step=0.6)
    loop, core = _loop(tmp_path, channel=channel, document=document, now=1000.0,
                       clock=clock)
    assert loop.run() == 4
    assert core.stop_reason == 'LEASE_EXPIRED'
    assert core.state == 'UNKNOWN_RETAINED'


def test_a_foreign_command_stops_the_round(tmp_path):
    plan = validate_launch_plan(plan_document())
    channel = MemoryChannel()
    channel.inbound.put(encode_command('STOP', run_id=plan.run_id,
                                        candidate_sha=plan.candidate_sha,
                                        authorization_sha256=plan.authorization_sha256,
                                        nonce='b' * 32, sequence=1))
    loop, core = _loop(tmp_path, channel=channel)
    assert loop.run() == 4
    assert core.stop_reason == 'CHANNEL_REFUSED'
    assert core.state == 'UNKNOWN_RETAINED'


def test_the_frame_count_limit_is_enforced(tmp_path):
    plan = validate_launch_plan(plan_document())
    channel = MemoryChannel()
    for sequence in range(1, 4):
        channel.inbound.put(encode_command('STATUS', run_id=plan.run_id,
                                            candidate_sha=plan.candidate_sha,
                                            authorization_sha256=plan.authorization_sha256,
                                            nonce='a' * 32, sequence=sequence))
    loop, core = _loop(tmp_path, channel=channel, max_frames=2)
    assert loop.run() == 4
    assert core.stop_reason == 'FRAME_COUNT_EXCEEDED'


def test_the_deadline_of_the_round_is_frozen_before_the_job(tmp_path):
    plan = validate_launch_plan(plan_document())
    channel = MemoryChannel()
    channel.eof = True
    loop, core = _loop(tmp_path, channel=channel)
    loop.run()
    # The deadline of the round was fixed before the job of the round
    # existed and it is the earlier of the lease and the runtime.
    assert loop._deadline_wall is not None
    assert loop._deadline_wall <= plan.lease_expires_at
    assert loop._deadline_mono is not None


# -- the parent session -----------------------------------------------------

def _session(tmp_path, *, document=None, remaining=600, wall=None, clock=None,
             kinds=('READY', 'STATUS', 'STOPPED'), write_fails=False,
             read_raises=None):
    document = document or plan_document()
    state = {'nonce': None, 'peer': None}

    def launcher(plan, run_root, nonce):
        state['nonce'] = nonce
        peer = FakeBrokerProcess(plan, nonce, kinds=kinds,
                                 write_fails=write_fails, read_raises=read_raises)
        state['peer'] = peer
        return peer

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=remaining,
                                   launcher=launcher, clock=clock, wall=wall)
    return session, state


def test_the_session_refuses_a_plan_without_a_remaining_budget(tmp_path):
    session, _ = _session(tmp_path, remaining=0)
    try:
        session.start()
    except CustodyError as error:
        assert error.code == 'CUSTODY_NO_CHILD_BUDGET_REMAINING'
    else:
        raise AssertionError('a session without a remaining budget was started')
    assert session.state == 'NEW'


def test_the_session_holds_the_original_broker_handle(tmp_path):
    session, state = _session(tmp_path)
    evidence = session.start()
    assert evidence['state'] == 'RUNNING'
    assert evidence['broker']['pid'] == 4242
    assert evidence['broker']['identity_source'] == 'PARENT_ORIGINAL_HANDLE'
    assert evidence['broker']['reported_by_the_broker'] is False
    assert evidence['channel']['nonce'] == state['nonce']
    session.stop()
    assert session.broker is None


def test_the_session_does_not_extend_the_deadline(tmp_path):
    wall = Clock(1000.0)
    clock = Clock(0.0)
    document = plan_document(lease_expires_at=4600.0, max_runtime_seconds=600)
    session, _ = _session(tmp_path, document=document, remaining=600,
                          wall=wall, clock=clock)
    session.start()
    first = session.evidence()['lease']['effective_deadline_wall']
    assert first == 1600.0
    wall.advance(300.0)
    clock.advance(300.0)
    session.stop()
    assert session.evidence()['lease']['effective_deadline_wall'] == first
    assert session.evidence()['lease']['deadline_extended'] is False


def test_a_repeated_stop_is_idempotent(tmp_path):
    session, _ = _session(tmp_path)
    session.start()
    broker = session.broker
    first = session.stop()
    sent = list(broker.outbound)
    second = session.stop()
    assert first['state'] == second['state']
    assert first['channel']['frames_sent'] == second['channel']['frames_sent']
    # The start of the round does not send a command of its own: the
    # broker sends its STATUS and the parent reads it.  The only frame of
    # the parent is therefore the one STOP command.
    assert len(sent) == 1
    command = json.loads(sent[0])
    assert command['command'] == 'STOP'
    assert command['sequence'] == 1
    assert first['channel']['last_sequence_sent'] == 1
    # The repeated stop sends no further frame and does not repeat the
    # sequence of the first one.
    assert list(broker.outbound) == sent
    assert second['channel']['last_sequence_sent'] == 1
    assert second['channel']['frames_sent'] == 1
    # The original handle of the broker is closed exactly once.
    assert broker.close_count == 1


def test_the_evidence_keeps_every_native_claim_not_proven(tmp_path):
    session, _ = _session(tmp_path)
    session.start()
    evidence = session.stop()
    assert evidence['grant_authority'] == 'NOT_VERIFIED'
    assert evidence['plan_sha256_proves'] == 'PLAN_INTEGRITY_ONLY'
    assert evidence['admission_produced'] is False
    assert evidence['native_execution_proven'] is False
    assert evidence['native_cleanup_proven'] is False
    assert evidence['gpu_released_proven'] is False
    assert evidence['port_released_proven'] is False
    assert evidence['sampler_proven'] is False
    assert evidence['parent_crash_recovery_proven'] is False
    assert evidence['windows_stdin_eof_proven'] is False
    assert evidence['stage_pass_claim'] is False
    assert evidence['product_gate0'] is False


def test_the_broker_launch_is_refused_off_windows():
    from tools.v0_s3_native_broker import launch_broker
    if os.name == 'nt':
        return
    try:
        launch_broker(None, '/tmp/never', 'a' * 32)
    except BrokerError as error:
        assert error.code == 'BROKER_PLATFORM_UNSUPPORTED'
    else:
        raise AssertionError('the broker was launched on an unsupported platform')


def test_the_windows_facade_is_not_loaded_off_windows():
    if os.name == 'nt':
        return
    try:
        WindowsApi()
    except BrokerError as error:
        assert error.code == 'BROKER_PLATFORM_UNSUPPORTED'
    else:
        raise AssertionError('the Windows table was loaded off Windows')


# -- M07: the parent closes the broker on every failure of the start -------

def test_the_session_closes_the_broker_on_a_refusal(tmp_path):
    # A refusal of the broker ends the round inside the start: the
    # original handle of the broker is released there and the caller
    # never has to stop a round that never started.
    session, state = _session(tmp_path, kinds=('REFUSED',))
    evidence = session.start()
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    assert state['peer'].close_count == 1
    assert session.broker is None
    assert any('BROKER_' in failure or 'REFUSED' in failure
               for failure in evidence['failures'])


def test_the_session_closes_the_broker_on_a_cancellation(tmp_path):
    session, state = _session(tmp_path, read_raises=KeyboardInterrupt())
    caught = None
    try:
        session.start()
    except BaseException as error:
        caught = type(error).__name__
    # The cancellation continues to propagate and the original handle of
    # the broker is released inside the start.
    assert caught == 'KeyboardInterrupt'
    assert state['peer'].close_count == 1
    assert session.state == 'UNKNOWN_RETAINED'


def test_the_session_closes_the_broker_on_a_parse_error(tmp_path):
    # A frame that is not a frame at all is a parse error of the channel:
    # the original handle of the broker is released there as well.
    document = plan_document()
    state = {'peer': None}

    def launcher(plan, run_root, nonce):
        peer = FakeBrokerProcess(plan, nonce, kinds=(),
                                 raw_frames=[b'not a frame\n'])
        state['peer'] = peer
        return peer

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=600,
                                   launcher=launcher, wall=lambda: 1000.0)
    # An ordinary failure of the start is a **structured** terminal state
    # of the round: the named code of the failure is kept, the original
    # handle of the broker is released there and the round stays
    # unknown.  Only a cancellation continues to propagate.
    evidence = session.start()
    assert evidence['state'] == 'UNKNOWN_RETAINED'
    assert 'CUSTODY_FRAME_INVALID' in evidence['failures']
    assert 'CUSTODY_PUMP_FAILED:CustodyError' in evidence['failures']
    assert state['peer'].close_count == 1
    assert session.state == 'UNKNOWN_RETAINED'


def test_the_session_refuses_a_peer_that_is_not_deadline_aware(tmp_path):
    class NotDeadlineAware(FakeBrokerProcess):
        channel_deadline_aware = False

    document = plan_document()
    state = {'peer': None}

    def launcher(plan, run_root, nonce):
        peer = NotDeadlineAware(plan, nonce)
        state['peer'] = peer
        return peer

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=600,
                                   launcher=launcher, wall=lambda: 1000.0)
    session.start()
    # The unknown handle is never assumed to be deadline aware: the
    # parent refuses to write into it.
    caught = None
    try:
        session.stop()
    except BaseException as error:
        caught = type(error).__name__
    assert caught is None
    assert any('CUSTODY_BROKER_NOT_DEADLINE_AWARE' in failure
               for failure in session.evidence()['failures'])
    assert state['peer'].close_count == 1
    assert state['peer'].outbound == []


# -- M08: the deadline aware transport, the heartbeat and the budgets ------

def test_the_stop_uses_one_shared_cleanup_budget(tmp_path):
    session, state = _session(tmp_path)
    session.start()
    broker = state['peer']
    session.stop()
    # Every write of the stop carries a deadline that is inside the
    # cleanup budget of the round and it never borrows the runtime.
    assert broker.write_deadlines
    for deadline in broker.write_deadlines:
        assert deadline is not None
    assert broker.bound_deadline is not None
    assert session.evidence()['channel']['stop_cleanup_budget_seconds'] == 5.0


def test_the_heartbeat_keeps_a_long_round_alive(tmp_path):
    # The oracle is the clock of the session: the whole schedule of a
    # round of six hours is checked without a long sleep.
    clock = Clock(0.0, step=0.0)
    document = plan_document(lease_expires_at=1000.0 + 21600.0,
                             max_runtime_seconds=21600)
    session, state = _session(tmp_path, document=document, remaining=21600,
                              clock=clock, wall=lambda: 1000.0)
    session.start()
    peer = state['peer']
    # The background heartbeat of the session is stopped, so that the
    # schedule of the round is driven by this check and by nothing else.
    session._heartbeat_stop.set()
    session._heartbeat.join(5.0)
    beats = 0
    for step in range(0, 21601, 30):
        clock.value = float(step)
        if session._heartbeat_step():
            beats += 1
    # One heartbeat every 60 seconds over the six hours of the round.
    # The beat at the expiry instant is not sent: the absolute lease of
    # the round is over at that moment and a heartbeat may never be sent
    # after it.
    assert beats == 359
    assert len(peer.outbound) == 359
    # The frames of the round stay inside the budget of the channel and
    # the frames of the terminal exchange are reserved.
    evidence = session.evidence()
    assert evidence['channel']['frames_sent'] + evidence['channel']['frames_received'] \
        <= MAX_FRAMES
    session.stop()


def test_the_heartbeat_does_not_extend_the_absolute_deadline(tmp_path):
    clock = Clock(0.0, step=0.0)
    document = plan_document(lease_expires_at=1000.0 + 600.0,
                             max_runtime_seconds=600)
    session, state = _session(tmp_path, document=document, remaining=600,
                              clock=clock, wall=lambda: 1000.0)
    session.start()
    first = session.evidence()['lease']['effective_deadline_wall']
    for step in range(0, 600, 30):
        clock.value = float(step)
        session._heartbeat_step()
    assert session.evidence()['lease']['effective_deadline_wall'] == first
    assert session.evidence()['lease']['deadline_extended'] is False
    session.stop()


def test_a_heartbeat_failure_is_a_named_failure_of_the_round(tmp_path):
    clock = Clock(0.0, step=0.0)
    session, state = _session(tmp_path, write_fails=True, clock=clock)
    session.start()
    # The first step only arms the heartbeat of the round.
    assert session._heartbeat_step() is False
    # The second step is due and the write of the heartbeat fails: the
    # failure is named and the round is not stopped silently.
    clock.value = HEARTBEAT_INTERVAL_SECONDS + 1.0
    assert session._heartbeat_step() is False
    assert any('CUSTODY_HEARTBEAT_FAILED' in failure
               for failure in session.evidence()['failures'])
    session.stop()


def test_the_frame_budget_fails_closed(tmp_path):
    session, state = _session(tmp_path)
    session.start()
    session._frames_received = MAX_FRAMES
    caught = None
    try:
        session._send('STATUS')
    except CustodyError as error:
        caught = error.code
    assert caught == 'CUSTODY_FRAME_BUDGET_EXCEEDED'
    session.stop()


def test_the_heartbeat_period_and_the_missing_window_are_the_closed_ones():
    assert HEARTBEAT_INTERVAL_SECONDS == 60.0
    assert HEARTBEAT_MISSING_SECONDS == 120.0


# -- M02 and M03: the declaration of the Windows primitives ----------------

class CtypesProxy:
    """The ctypes module with a last error that the check controls.

    The proxy forwards every name to the real module and it answers the
    last error itself, so that the production code of the façade reads
    the value that the check prepared.  The production code is not
    changed for the check: it asks the module of the table.
    """

    def __init__(self, module):
        self._module = module
        self.last_error = 0

    def __getattr__(self, name):
        return getattr(self._module, name)

    def get_last_error(self):
        return self.last_error


class FakeKernel32:
    """A primitive table that answers the calls of the production façade.

    The table is injected into the **production** façade, so the code
    that is checked here is the code of a real run: the arguments, the
    structures, the sizes and the order of the calls are the production
    ones.  The table never touches the operating system.
    """

    def __init__(self, *, create_process=True, last_error=5, job_ids=None):
        self.calls = []
        self.create_process = create_process
        self.last_error = last_error
        self.job_ids = list(job_ids or [])
        self.next_handle = 0x1000
        self.closed = []
        self.startup = None
        self.handle_list = None
        self.null_handle = None
        self.null_attributes = None
        self.process_handle = 0x900
        self.thread_handle = 0x901
        self.creation_time = 0x0000_0000_0000_1234

    def _handle(self):
        self.next_handle += 0x10
        return self.next_handle

    # -- the primitives of the creation -----------------------------------
    def CreateFileW(self, name, access, share, security, creation, flags,
                    template):
        self.calls.append(('CreateFileW', name, access))
        self.null_attributes = security._obj if security is not None else None
        self.null_handle = self._handle()
        return self.null_handle

    def InitializeProcThreadAttributeList(self, attribute_list, count, flags,
                                          size):
        self.calls.append(('InitializeProcThreadAttributeList', attribute_list))
        if attribute_list is None:
            size._obj.value = 256
            return 0
        return 1

    def UpdateProcThreadAttribute(self, attribute_list, flags, attribute,
                                  value, size, previous, return_value):
        self.calls.append(('UpdateProcThreadAttribute', attribute, size))
        self.handle_list = list(value)
        return 1

    def DeleteProcThreadAttributeList(self, attribute_list):
        self.calls.append(('DeleteProcThreadAttributeList',))

    def CreateProcessW(self, application, command_line, process_attributes,
                       thread_attributes, inherit_handles, flags, environment,
                       current_directory, startup_info, process_information):
        self.calls.append(('CreateProcessW', flags, inherit_handles))
        self.startup = startup_info._obj
        self.flags = flags
        self.inherit_handles = inherit_handles
        information = process_information._obj
        information.hProcess = self.process_handle
        information.hThread = self.thread_handle
        information.dwProcessId = 4242
        information.dwThreadId = 4243
        if not self.create_process:
            self.last_error = 1234
            if getattr(self, 'ctypes_proxy', None) is not None:
                self.ctypes_proxy.last_error = self.last_error
            return 0
        return 1

    def GetProcessTimes(self, process, creation, exit_time, kernel_time,
                        user_time):
        self.calls.append(('GetProcessTimes',))
        creation._obj.dwLowDateTime = self.creation_time & 0xFFFFFFFF
        creation._obj.dwHighDateTime = self.creation_time >> 32
        return 1

    def CloseHandle(self, handle):
        self.calls.append(('CloseHandle', handle))
        self.closed.append(handle)
        return 1

    def TerminateProcess(self, process, exit_code):
        self.calls.append(('TerminateProcess', process))
        return 1

    def WaitForSingleObject(self, handle, timeout):
        self.calls.append(('WaitForSingleObject', handle, timeout))
        return 0

    # -- the primitive of the job -----------------------------------------
    def QueryInformationJobObject(self, job, info_class, buffer, size,
                                   returned):
        self.calls.append(('QueryInformationJobObject', info_class, size))
        pointer_size = ctypes.sizeof(ctypes.c_size_t)
        # The buffer of the round holds at most eighteen ids: a job with
        # more ids reports all of them in the counts and only the ids
        # that fit are written into the buffer.
        written = min(len(self.job_ids), 18)
        for index, pid in enumerate(self.job_ids[:written]):
            ctypes.memmove(ctypes.byref(buffer, 8 + index * pointer_size),
                           bytes(ctypes.c_size_t(pid)), pointer_size)
        ctypes.memmove(ctypes.byref(buffer, 0),
                       bytes(ctypes.c_uint32(len(self.job_ids))), 4)
        ctypes.memmove(ctypes.byref(buffer, 4),
                       bytes(ctypes.c_uint32(len(self.job_ids))), 4)
        if returned is not None:
            returned._obj.value = 8 + written * pointer_size
        return 1


def _declared_table(kernel32=None):
    """The production table with an injected primitive table."""
    from tools.v0_s3_native_broker import _WindowsApiTable
    types = _windows_api_types()
    proxy = CtypesProxy(ctypes)
    types = dict(types)
    types['ctypes'] = proxy
    if kernel32 is None:
        kernel32 = FakeKernel32()
    kernel32.ctypes_proxy = proxy
    table = _WindowsApiTable(kernel32=kernel32, types=types)
    return table, proxy


def test_the_windows_types_use_the_windows_widths():
    types = _windows_api_types()
    # The fixed width types of Windows are 32 bit and 16 bit and they do
    # not depend on the size of a long of the host.
    assert ctypes.sizeof(types['DWORD']) == 4
    assert ctypes.sizeof(types['BOOL']) == 4
    assert ctypes.sizeof(types['WORD']) == 2
    assert ctypes.sizeof(types['UINT']) == 4
    # A handle and a size have the width of a pointer.
    assert ctypes.sizeof(types['HANDLE']) == ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(types['SIZE_T']) == ctypes.sizeof(ctypes.c_size_t)
    assert ctypes.sizeof(types['ULONG_PTR']) == ctypes.sizeof(ctypes.c_size_t)
    # The width of a long of the host is never used for a Windows value.
    assert ctypes.sizeof(types['BOOL']) != ctypes.sizeof(ctypes.c_long) \
        or ctypes.sizeof(ctypes.c_long) == 4


def test_every_primitive_of_the_broker_has_a_declared_prototype():
    table = RecordingTable()
    _declare_windows_primitives(table, _windows_api_types())
    for name in ('CreateJobObjectW', 'SetInformationJobObject', 'CreateProcessW',
                 'AssignProcessToJobObject', 'ResumeThread', 'TerminateProcess',
                 'TerminateJobObject', 'WaitForSingleObject', 'GetExitCodeProcess',
                 'GetProcessTimes', 'QueryInformationJobObject', 'CloseHandle',
                 'CreatePipe', 'ReadFile', 'WriteFile', 'SetHandleInformation',
                 'CreateFileW', 'InitializeProcThreadAttributeList',
                 'UpdateProcThreadAttribute', 'DeleteProcThreadAttributeList',
                 'CancelSynchronousIo', 'DuplicateHandle', 'GetCurrentThread',
                 'GetCurrentProcess'):
        primitive = table.primitives[name]
        assert primitive.argtypes is not None, name
        if name != 'DeleteProcThreadAttributeList':
            assert primitive.restype is not None, name


def test_the_prototypes_use_the_windows_widths():
    table = RecordingTable()
    types = _windows_api_types()
    _declare_windows_primitives(table, types)
    handle = types['HANDLE']
    dword = types['DWORD']
    size_t = types['SIZE_T']
    # A handle is a handle and never a plain integer.
    assert table.primitives['CloseHandle'].argtypes == [handle]
    assert table.primitives['AssignProcessToJobObject'].argtypes == [handle, handle]
    # A count that Windows defines as 32 bit is a DWORD.
    assert table.primitives['GetExitCodeProcess'].argtypes == [handle,
                                                               ctypes.POINTER(dword)]
    assert table.primitives['WaitForSingleObject'].argtypes == [handle, dword]
    # A size is a SIZE_T and a boolean is a BOOL.
    assert table.primitives['UpdateProcThreadAttribute'].argtypes[2] == size_t
    assert table.primitives['UpdateProcThreadAttribute'].argtypes[4] == size_t
    assert table.primitives['CreateProcessW'].restype is types['BOOL']
    # The birth query takes four file times and not four plain integers.
    assert table.primitives['GetProcessTimes'].argtypes[1] == ctypes.POINTER(
        types['FILETIME'])
    assert len(table.primitives['GetProcessTimes'].argtypes) == 5
    # The security attributes of a handle are a pointer to the structure.
    assert table.primitives['CreatePipe'].argtypes[2] == ctypes.POINTER(
        types['SECURITY_ATTRIBUTES'])


def test_the_start_up_information_of_the_extended_structure_is_bigger():
    types = _windows_api_types()
    extended = types['STARTUPINFOEXW']
    plain = types['STARTUPINFOW']
    # The attribute list follows the start up information inside the
    # extended structure, so the size of the start up information is the
    # size of the whole structure when the extended flag is set.
    assert ctypes.sizeof(extended) > ctypes.sizeof(plain)
    assert extended.StartupInfo.offset == 0
    assert extended.lpAttributeList.offset == ctypes.sizeof(plain)


def test_the_process_id_list_of_a_job_is_an_inline_array():
    types = _windows_api_types()
    structure = types['JOBOBJECT_BASIC_PROCESS_ID_LIST']
    # Two counts of 32 bit and an inline array of ULONG_PTR: the first
    # process id is written at the offset of the array and it is never
    # behind a pointer that would have to be dereferenced.
    assert structure.NumberOfAssignedProcesses.offset == 0
    assert structure.NumberOfProcessIdsInList.offset == 4
    assert structure.ProcessIdList.offset == 8
    assert structure.ProcessIdList.size == ctypes.sizeof(types['ULONG_PTR'])


def test_the_child_is_created_with_the_extended_start_up_information():
    kernel32 = FakeKernel32()
    table, _proxy = _declared_table(kernel32)
    api = WindowsApi(table=table)
    created = api.create_process_suspended(
        executable='C:/tools/python.exe', arguments=['-s'],
        working_directory='C:/round', stdout_handle=0x21, stderr_handle=0x22,
        environment=None)
    assert created.process == kernel32.process_handle
    assert created.thread == kernel32.thread_handle
    assert created.pid == 4242
    assert created.creation_time == kernel32.creation_time
    # The size of the start up information is the size of the whole
    # extended structure and not the size of the plain one.
    assert kernel32.startup.cb == ctypes.sizeof(table.types['STARTUPINFOEXW'])
    assert kernel32.flags & api.EXTENDED_STARTUPINFO_PRESENT
    assert kernel32.flags & api.CREATE_SUSPENDED
    assert kernel32.inherit_handles is True
    # The handle list is the exact white list of the round: the write
    # end of the output, the write end of the error and the null device.
    assert kernel32.handle_list == [0x21, 0x22, kernel32.null_handle]
    # The null device was created as an inheritable handle and it was
    # closed again after the creation.
    assert kernel32.null_attributes is not None
    assert kernel32.null_attributes.bInheritHandle == 1
    assert kernel32.null_handle in kernel32.closed


def test_the_last_error_is_named_before_the_cleanup():
    kernel32 = FakeKernel32(create_process=False, last_error=1234)
    table, proxy = _declared_table(kernel32)
    proxy.last_error = 1234
    api = WindowsApi(table=table)
    with pytest.raises(BrokerError) as info:
        api.create_process_suspended(
            executable='C:/tools/python.exe', arguments=['-s'],
            working_directory='C:/round', stdout_handle=0x21,
            stderr_handle=0x22, environment=None)
    assert info.value.code == 'BROKER_PROCESS_CREATE_FAILED'
    # The last error of the failure was read before the cleanup began.
    assert 'last_error=1234' in info.value.detail
    # The null device was closed after the failure was named.
    assert kernel32.null_handle in kernel32.closed


def test_the_invalid_handle_value_has_the_width_of_a_pointer():
    table, _proxy = _declared_table()
    api = WindowsApi(table=table)
    assert api.invalid_handle_value == ctypes.c_void_p(-1).value
    assert api.invalid_handle_value == 2 ** (8 * ctypes.sizeof(ctypes.c_void_p)) - 1


def test_the_job_process_ids_are_read_from_the_inline_array():
    kernel32 = FakeKernel32(job_ids=[111, 222])
    table, _proxy = _declared_table(kernel32)
    api = WindowsApi(table=table)
    assert api.job_process_ids(0x99) == [111, 222]


def test_a_truncated_job_process_id_list_is_unknown():
    kernel32 = FakeKernel32(job_ids=[111])
    table, _proxy = _declared_table(kernel32)
    api = WindowsApi(table=table)

    def truncating(job, info_class, buffer, size, returned):
        # The buffer was too small: the job holds more processes than the
        # list that was returned.
        ctypes.memmove(ctypes.byref(buffer, 0), bytes(ctypes.c_uint32(5)), 4)
        ctypes.memmove(ctypes.byref(buffer, 4), bytes(ctypes.c_uint32(1)), 4)
        returned._obj.value = 16
        return 1

    kernel32.QueryInformationJobObject = truncating
    with pytest.raises(BrokerError) as info:
        api.job_process_ids(0x99)
    assert info.value.code == 'BROKER_JOB_QUERY_TRUNCATED'


def test_a_job_process_id_list_over_the_cap_is_unknown():
    kernel32 = FakeKernel32(job_ids=list(range(40)))
    table, _proxy = _declared_table(kernel32)
    api = WindowsApi(table=table)
    with pytest.raises(BrokerError) as info:
        api.job_process_ids(0x99)
    assert info.value.code == 'BROKER_DESCENDANT_LIMIT'


# -- M08: the deadline aware transport of the private channel --------------

class FakeFileObject:
    """A file object of the private pipe with an own descriptor."""

    def __init__(self, descriptor=7):
        self.descriptor = descriptor
        self.closed = False

    def fileno(self):
        return self.descriptor

    def close(self):
        self.closed = True


class FakeSyscalls:
    """The synthetic system calls of the private pipe.

    The table records the calls of the production endpoint and it
    answers with the scripted answers of the check.  It never touches
    the operating system and it never opens a descriptor.
    """

    def __init__(self, *, reads=None, writes=None, ready=True):
        self.calls = []
        self.reads = list(reads or [])
        self.writes = list(writes or [])
        self.ready = ready
        self.closed = []

    def fileno(self, file_object):
        return file_object.fileno()

    def set_blocking(self, descriptor, blocking):
        self.calls.append(('set_blocking', descriptor, blocking))

    def poll(self, descriptor, mask, timeout):
        self.calls.append(('poll', descriptor, mask, timeout))
        return self.ready

    def read(self, descriptor, size):
        self.calls.append(('read', descriptor, size))
        if self.reads:
            return self.reads.pop(0)
        return b''

    def write(self, descriptor, data):
        self.calls.append(('write', descriptor, bytes(data)))
        if self.writes:
            return self.writes.pop(0)
        return len(data)

    def close(self, file_object):
        self.calls.append(('close', file_object))
        self.closed.append(file_object)


def test_the_pipe_is_non_blocking_and_never_waits_for_the_lock():
    calls = FakeSyscalls(reads=[b'frame\n'])
    file_object = FakeFileObject()
    endpoint = _PosixPipeEndpoint(file_object, name='read', syscalls=calls,
                                  clock=Clock(0.0))
    assert endpoint.read(None, None) == b'frame\n'
    # The descriptor of the owner was set to non blocking exactly once.
    assert calls.calls[0] == ('set_blocking', 7, False)
    assert [call[0] for call in calls.calls].count('set_blocking') == 1


def test_the_pipe_read_is_bounded_by_the_deadline():
    calls = FakeSyscalls(ready=False)
    endpoint = _PosixPipeEndpoint(FakeFileObject(), name='read', syscalls=calls,
                                  clock=Clock(0.0, step=1.0))
    with pytest.raises(BrokerError) as info:
        endpoint.read(2.0, None)
    assert info.value.code == 'BROKER_PIPE_TIMEOUT'
    # The pipe was polled in slices of at most 50 milliseconds, so the
    # deadline was observed even while the peer was silent.
    polls = [call for call in calls.calls if call[0] == 'poll']
    assert polls
    assert all(call[3] <= 0.05 for call in polls)


def test_the_pipe_read_observes_the_cancel_flag():
    calls = FakeSyscalls(ready=False)
    cancel = threading.Event()
    cancel.set()
    endpoint = _PosixPipeEndpoint(FakeFileObject(), name='read', syscalls=calls,
                                  clock=Clock(0.0))
    with pytest.raises(BrokerError) as info:
        endpoint.read(None, cancel)
    assert info.value.code == 'BROKER_PIPE_CANCELLED'


def test_the_pipe_reports_the_end_of_the_stream():
    calls = FakeSyscalls(reads=[b''])
    endpoint = _PosixPipeEndpoint(FakeFileObject(), name='read', syscalls=calls,
                                  clock=Clock(0.0))
    assert endpoint.read(None, None) == b''


def test_the_pipe_write_retries_a_partial_write():
    calls = FakeSyscalls(writes=[2, 3])
    endpoint = _PosixPipeEndpoint(FakeFileObject(), name='write', syscalls=calls,
                                  clock=Clock(0.0))
    assert endpoint.write(b'abcde', None, None) == 5
    writes = [call for call in calls.calls if call[0] == 'write']
    assert writes[0][2] == b'abcde'
    assert writes[1][2] == b'cde'


def test_the_pipe_write_is_bounded_by_the_deadline():
    calls = FakeSyscalls(ready=False)
    endpoint = _PosixPipeEndpoint(FakeFileObject(), name='write', syscalls=calls,
                                  clock=Clock(0.0, step=1.0))
    with pytest.raises(BrokerError) as info:
        endpoint.write(b'frame\n', 2.0, None)
    assert info.value.code == 'BROKER_PIPE_TIMEOUT'


def test_the_pipe_closes_only_its_own_descriptor():
    calls = FakeSyscalls()
    file_object = FakeFileObject()
    endpoint = _PosixPipeEndpoint(file_object, name='read', syscalls=calls,
                                  clock=Clock(0.0))
    endpoint.close()
    assert calls.closed == [file_object]
    # A second close does not close the descriptor a second time.
    facts = endpoint.close()
    assert facts['already_closed'] is True
    assert calls.closed == [file_object]


# -- the owners that this package does not change ---------------------------

OLD_OWNERS = {
    'tools/v0_s3_production_controller.py':
        'a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38',
    'tools/v0_s3_quality_worker.py':
        'e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592',
    'tools/v0_s3_quality_phase.py':
        '90552ea113ccf53a2a1cedff3e3f399642ad932bf0f71bb1f9a57e1adb6e8789',
    'tools/v0_s3_supervisor.py':
        '7d210429e70761cea633e8f2e64d8a1f01709930068a21de5cbc3c5a519ce6d8',
    'tools/v0_s3_coordinator.py':
        '14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c',
    'tools/v0_s2_runtime.py':
        'a97ea20d02ed80ab4f99f133dd8162331ddba34662bfdcca637fcade40b4dbd2',
    'tools/v0_s2_driver.py':
        '72883e2fa0c252aef7655708f40ada88a755978d71f632043c8203b53b42afed',
    'tools/v0_s3_budget_authority.py':
        '80908669be48bbb8db5b9fd5271719a9c927918a52eb6565d152b471423ad1b7',
    'tools/local_program_authority.py':
        '677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787',
    'lvw/backend/app/native_runtime.py':
        '16bf3e6396f9548312f92007eebbda55a448f0bdc6bab4a10afd71179b231a85',
}


def test_the_old_owners_are_unchanged():
    for relative, digest in sorted(OLD_OWNERS.items()):
        path = PACK_ROOT / relative
        assert path.is_file(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, relative


def test_the_old_refusal_points_are_still_declared():
    controller = (PACK_ROOT / 'tools/v0_s3_production_controller.py').read_text(
        encoding='utf-8')
    worker = (PACK_ROOT / 'tools/v0_s3_quality_worker.py').read_text(encoding='utf-8')
    supervisor = (PACK_ROOT / 'tools/v0_s3_supervisor.py').read_text(encoding='utf-8')
    assert 'NATIVE_EXECUTION_BACKEND_NOT_READY' in controller
    assert 'NATIVE_EXECUTION_BACKEND_NOT_READY' in worker
    assert "'native_service_cleanup_proven': False" in supervisor
    assert "'native_gpu_release_proven': False" in supervisor
    assert "'parent_crash_recovery_proven': False" in supervisor
