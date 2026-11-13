"""The offline validation of the N1 parent owned native custody.

The validation of this package is *offline*.  It never starts a process,
it never opens a socket, it never touches a database and it never reads
the original budget ledger or the original shared counter.  The only
native capability that is exercised here is an **in-process façade** of the
Windows primitives: a typed object with the same methods as the
production façade, which records the calls in their order and can fail at
one named call.

**The boundary of this module is not installed here.**  The guard of the
process lives in ``reports/v0-s3/product-gate0/implementation-native-custody-01/guard.py``
and the run lives in the ``runner.py`` of the same directory.  The guard
is installed by that runner *before* pytest, before any plugin and before
any import of a candidate module, so the refusal of the operating system
events happens inside the event itself and before the action.  A plain
``pytest tools/test_v0_s3_native_custody.py`` is **not** an authorised
entry of this package: the plan of the batch names the runner and only
the runner.

This module has no entry point of its own.  It has no ``--run`` mode, it
has no counter snapshot and it has no exemption of its own: the original
shared counter is observed once before and once after the batch by the
outer runner, and it is never written, never refunded and never revived.
"""
import hashlib
import json
import os
import queue
import sys
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools.v0_s3_native_broker import (  # noqa: E402 - the path is set above
    BrokerCore, BrokerError, BrokerLoop, CreatedProcess, WindowsApi, role_command)
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_SCHEMA, CustodyError, MAX_FRAME_BYTES, MAX_FRAMES, NativeCustodySession,
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
                   'WindowsApi.create_job -> tools/v0_s3_native_broker.py:341'),
    'job_limit': ('BROKER_JOB_LIMIT_FAILED',
                  'WindowsApi.set_job_kill_on_close -> tools/v0_s3_native_broker.py:357'),
    'terminate_job': ('BROKER_TERMINATE_FAILED',
                      'WindowsApi.terminate_job -> tools/v0_s3_native_broker.py:363'),
    'query_job': ('BROKER_JOB_QUERY_UNKNOWN',
                  'WindowsApi.job_process_ids -> tools/v0_s3_native_broker.py:387'),
    'create': ('BROKER_PROCESS_CREATE_FAILED',
               'WindowsApi.create_process_suspended -> tools/v0_s3_native_broker.py:451'),
    'assign': ('BROKER_ASSIGN_FAILED',
               'WindowsApi.assign_process_to_job -> tools/v0_s3_native_broker.py:477'),
    'resume': ('BROKER_RESUME_FAILED',
               'WindowsApi.resume_thread -> tools/v0_s3_native_broker.py:484'),
    'terminate': ('BROKER_TERMINATE_FAILED',
                  'WindowsApi.terminate_process -> tools/v0_s3_native_broker.py:490'),
    'close': ('BROKER_HANDLE_CLOSE_FAILED',
              'WindowsApi.close_handle -> tools/v0_s3_native_broker.py:511'),
    'pipe': ('BROKER_PIPE_FAILED',
             'WindowsApi.create_pipe -> tools/v0_s3_native_broker.py:524'),
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
        self._next_handle = 100
        self._next_pid = 4000

    # -- helpers -----------------------------------------------------------
    def _handle(self):
        self._next_handle += 1
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

    The transport is a pair of queues.  It never opens a pipe, a socket or
    a file and it never starts a process.
    """

    def __init__(self):
        self.inbound = queue.Queue()
        self.outbound = []
        self.closed = False
        self.eof = False

    def read(self, timeout):
        try:
            return self.inbound.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return b'' if self.eof else None

    def write(self, raw):
        self.outbound.append(raw)

    def close(self):
        self.closed = True


class FakeBrokerProcess:
    """The in-process stand-in of the original handle of the broker.

    The stand-in speaks the closed frame protocol of the private channel.
    It is not a simulation of a Windows process: it is a queue of frames,
    and the assertions of this package are made on the frames themselves.
    """

    def __init__(self, plan, nonce, kinds=('READY', 'STATUS', 'STOPPED')):
        self.plan = plan
        self.nonce = nonce
        self.pid = 4242
        self.executable = 'C:/Windows/py.exe'
        self.executable_sha256 = 'f' * 64
        self.inbound = queue.Queue()
        self.outbound = []
        self.closed = False
        self.close_count = 0
        states = {'READY': 'ARMED', 'STATUS': 'RUNNING', 'STOPPED': 'RELEASED'}
        for index, kind in enumerate(kinds, start=1):
            self.inbound.put(_reply_frame(kind, states[kind], {}, plan, nonce, index))

    def write(self, raw):
        self.outbound.append(raw)

    def read(self, timeout):
        try:
            return self.inbound.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return None

    def close(self):
        self.closed = True
        self.close_count += 1


class Clock:
    """A clock that only moves when the test moves it."""

    def __init__(self, value):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


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
    second = core.stop('STOP')
    assert list(win32.terminated) == terminated
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


def test_the_sampler_is_created_last_with_the_pids_of_the_services(tmp_path):
    document = plan_document()
    document['roles'].append(sampler_role())
    plan = validate_launch_plan(document)
    command = role_command(plan.roles[2], tmp_path, [11, 22])
    assert command['arguments'][0] == '-I'
    assert '--execute-sampler' in command['arguments']
    assert command['arguments'][command['arguments'].index('--private-pids') + 1] == '11 22'
    assert command['executable'] == 'C:/ComfyUI-aki-v2/python/python.exe'


# -- the broker loop --------------------------------------------------------

def _loop(tmp_path, *, channel, document=None, max_frames=MAX_FRAMES, now=None):
    plan = validate_launch_plan(document or plan_document(), now=now)
    core = BrokerCore(win32=FakeWin32(), plan=plan, run_root=tmp_path)
    loop = BrokerLoop(core=core, transport=channel, plan=plan, nonce='a' * 32,
                      max_frames=max_frames)
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
    channel.eof = True
    loop, core = _loop(tmp_path, channel=channel, document=document, now=1000.0)
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


# -- the parent session -----------------------------------------------------

def _session(tmp_path, *, document=None, remaining=600, wall=None, clock=None):
    document = document or plan_document()
    state = {'nonce': None}

    def launcher(plan, run_root, nonce):
        state['nonce'] = nonce
        return FakeBrokerProcess(plan, nonce)

    return NativeCustodySession(plan=document, run_root=tmp_path,
                                 parent_child_remaining_seconds=remaining,
                                 launcher=launcher, clock=clock, wall=wall), state


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
