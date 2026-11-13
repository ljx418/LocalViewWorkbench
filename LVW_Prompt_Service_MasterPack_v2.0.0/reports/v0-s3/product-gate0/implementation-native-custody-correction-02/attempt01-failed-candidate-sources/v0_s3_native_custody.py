"""Parent-side native custody: the closed launch plan and the bounded session.

This module is the parent internal half of the N1 native custody foundation.
It owns exactly two things.

* The **closed launch plan**.  It is a small, exactly keyed document that
  names the tools of one round, the absolute lease of the round and the
  finite role set.  The plan never carries an argument vector, a shell, a
  script, an environment or a PID.  The command form of a role is frozen in
  the broker and assembled from the already authorised tools; the plan only
  says *which* tools and *which* closed data.

* The **bounded custody session**.  It is the parent side handle of one
  broker process, the private control channel to that broker and the
  absolute deadline of the round.

Three facts are deliberate and they are repeated in every evidence that
this module produces.

* The hash of the plan proves that the plan did not change.  It does not
  prove that a grant is real.  The grant authority of this package is
  ``NOT_VERIFIED`` and this package produces no admission evidence at all.

* The parent never stops a native service by name, by PID or by a record
  that somebody else wrote.  The parent stops only what it created: the
  broker process of this round, through its own original handle and through
  the private channel.  The broker, in turn, stops only what it created:
  the processes of this round, through their own original handles and
  through the job object of this round.

* Nothing here is a proof of a native execution.  The Windows path of this
  package has never run on Windows, so every native claim of its evidence
  stays ``NOT_PROVEN``.

The session owns the resources of one round from the moment they are
created until they are released, and it never leaves a resource of the
round to the garbage collector:

* the plan is validated once, deep copied and presented as a copy, so
  that a caller that changes the presented copy changes nothing of the
  command that the round will really run;

* every failure of the start of the round closes the original handle of
  the broker inside the method that failed, whether the failure was a
  refusal of the broker, a timeout, a parse error, an ordinary exception
  or a cancellation;

* the read side of the private channel has exactly one owner, a bounded
  pump, and the round keeps a status heartbeat alive on its own, so that
  a long round is not stopped for silence and so that a heartbeat never
  extends the absolute deadline of the round.
"""
import copy
import hashlib
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from types import MappingProxyType

PLAN_SCHEMA = 'lvw.s3-native-custody-plan/1'
CHANNEL_SCHEMA = 'lvw.s3-native-custody-channel/1'

# The closed key sets.  A document with one key too many or one key too few
# is refused; a plan is never repaired and never completed.
PLAN_KEYS = frozenset({'schema', 'run_id', 'candidate_sha', 'authorization_sha256',
                       'lease_expires_at', 'max_runtime_seconds', 'roles'})
ROLE_KEYS = frozenset({'role', 'tools', 'data', 'log'})
TOOL_KEYS = frozenset({'path', 'sha256'})

# The finite role set.  COMFY and OLLAMA are required, SAMPLER is optional.
# The order of the roles is fixed: the sampler is created last, because it
# observes the two services that this broker created.
ROLE_ORDER = ('COMFY', 'OLLAMA', 'SAMPLER')
REQUIRED_ROLES = ('COMFY', 'OLLAMA')
ROLE_DATA_KEYS = {
    'COMFY': frozenset({'user_directory'}),
    'OLLAMA': frozenset(),
    'SAMPLER': frozenset({'nvidia_exe', 'nvidia_sha256', 'max_seconds'}),
}
# The number of tools of a role is fixed as well.  The first tool of a role
# is its executable; the second one, where it exists, is the script that the
# executable runs.  A role never grows a third tool by accident.
ROLE_TOOL_COUNTS = {'COMFY': 2, 'OLLAMA': 1, 'SAMPLER': 2}

# The bounded limits of the round.  They are internal limits of this
# foundation and they are not a claim about any native Windows behaviour.
MAX_RUNTIME_SECONDS = 21600
MAX_FRAME_BYTES = 32 * 1024
MAX_FRAMES = 1024
MAX_STREAM_BYTES = 256 * 1024
MAX_NEW_TEXT_BYTES = 8 * 1024 * 1024
MAX_DESCENDANTS = 17
MAX_SAMPLER_SECONDS = 7200

# The bounded waits of the parent side.  The heartbeat keeps a round alive
# while the round runs; it never moves the absolute deadline of the round.
# The cleanup of a stop has its own short budget and never borrows the
# remaining runtime of the round: the stop and the cleanup share ONE
# budget and no layer adds a budget of its own.
CHANNEL_POLL_SECONDS = 0.25
HEARTBEAT_INTERVAL_SECONDS = 60.0
HEARTBEAT_MISSING_SECONDS = 120.0
HEARTBEAT_SLICE_SECONDS = 0.25
STOP_CLEANUP_SECONDS = 5.0
WRITE_BUDGET_SECONDS = 5.0
THREAD_JOIN_SECONDS = 2.0
# The number of the frames of the channel that is reserved for the
# terminal exchange of the round.  The heartbeat may not spend them: a
# round that reached its frame budget fails closed and it never
# reconnects and it never renews its lease.
RESERVED_TERMINAL_FRAMES = 8

# The closed command set of the private channel and the closed reply kinds.
COMMANDS = ('STATUS', 'STOP')
REPLIES = ('READY', 'STATUS', 'STOPPED', 'REFUSED')

# The state machine of one round.  ARMED means that the job object of the
# round exists; RUNNING means that the roles of the round were created,
# assigned to that job and resumed.  UNKNOWN_RETAINED is a terminal state
# that keeps the evidence of what could not be proven.
STATES = ('NEW', 'VALIDATED', 'ARMED', 'RUNNING', 'STOPPING', 'RELEASED',
          'UNKNOWN_RETAINED')

COMMAND_KEYS = frozenset({'schema', 'command', 'run_id', 'candidate_sha',
                          'authorization_sha256', 'nonce', 'sequence'})
REPLY_KEYS = frozenset({'schema', 'kind', 'run_id', 'candidate_sha',
                        'authorization_sha256', 'nonce', 'sequence', 'state', 'detail'})

# The nonce of the private channel.  The parent and the broker agree on
# one closed form: 32 hexadecimal characters.  A nonce identifies the
# channel of one round; it grants no custody over any process.
NONCE_PATTERN = r'[0-9a-f]{32}'
NONCE_BYTES = 16


class CustodyError(RuntimeError):
    """A refused custody step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


# -- the closed plan -------------------------------------------------------

_WINDOWS_ABSOLUTE = re.compile(r'^(?:[A-Za-z]:[\\/]|\\\\)[^\x00]+$')
_LOG_REFERENCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,254}')
_DIRECTORY_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
DIRECTORY_NAME_MAX_LENGTH = 64
# The device names of Windows.  A directory of the round may not carry
# one of them, with or without an extension.
WINDOWS_DEVICE_NAMES = frozenset(
    ['CON', 'PRN', 'AUX', 'NUL']
    + ['COM%d' % index for index in range(1, 10)]
    + ['LPT%d' % index for index in range(1, 10)])


def _require_text(value, pattern, code):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise CustodyError(code)
    return value


def _require_exact_int(value, code, *, minimum=None, maximum=None):
    """An exact integer.

    A boolean is not an integer here and a float is not an integer either:
    ``True`` would silently become ``1`` and ``1.5`` would silently become
    ``1``, and both would hide a malformed plan.
    """
    if type(value) is not int:
        raise CustodyError(code)
    if minimum is not None and value < minimum:
        raise CustodyError(code)
    if maximum is not None and value > maximum:
        raise CustodyError(code)
    return value


def _require_number(value, code):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CustodyError(code)
    if not math.isfinite(value):
        raise CustodyError(code)
    return value


def _windows_parts(path):
    return [part for part in re.split(r'[\\/]+', path) if part not in ('', '.')]


def _require_absolute_windows_path(value, code):
    if not isinstance(value, str) or not _WINDOWS_ABSOLUTE.match(value):
        raise CustodyError(code)
    if '..' in _windows_parts(value):
        raise CustodyError(code)
    if len(value) > 512:
        raise CustodyError(code)
    return value


def _require_log_reference(value):
    """A relative reference of a log of this run, below the run root.

    The reference is judged with the semantics of a **Windows** path and
    not with the semantics of the host that runs the check.  The package
    is validated on a POSIX host and the round runs on Windows, so a check
    that used the rules of the host would accept a reference that the
    broker of the round resolves somewhere else.  ``pathlib`` is not used
    here for the same reason: ``Path('C:/Windows/temp/x.log').is_absolute()``
    is ``False`` on Linux and ``True`` on Windows.

    A reference is refused when it is

    * empty, not a string or longer than the closed limit;
    * absolute in the POSIX sense (``/var/log/comfy.log``);
    * absolute in the Windows sense (``C:/Windows/temp/comfy.log``);
    * relative to a drive (``C:comfy.log``);
    * a UNC reference or a mixed separator reference
      (``\\\\server\\share\\comfy.log``, ``temp\\native\\comfy.log``);
    * an alternate data stream (``temp/native/comfy.log:stream``);
    * a traversal (``../comfy.log``, ``temp/../comfy.log``);
    * a reference with an empty or a dot segment
      (``temp//comfy.log``, ``temp/./comfy.log``).

    A plain relative reference below the run root is accepted.  The
    refusal happens in ``validate_launch_plan``, before any job, any
    process and any log of the round exists, and the broker validates the
    plan again before it consumes it.
    """
    if not isinstance(value, str) or not value or len(value) > 255:
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    # A colon is the separator of a drive and the separator of an
    # alternate data stream.  Both are refused: the reference stays a
    # plain relative name of the run root.
    if ':' in value:
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    # A backslash is a path separator of Windows.  A UNC reference and a
    # reference with a mixed separator are refused with it.
    if '\\' in value:
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    # A leading slash is an absolute reference in POSIX and in Windows.
    if value.startswith('/'):
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    # The closed character set of the reference.
    if not _LOG_REFERENCE.fullmatch(value):
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
    return value


def _require_directory_name(value, code):
    """One controlled directory name and nothing else.

    The name of the user directory of the ComfyUI role is a **single
    segment** below the root of the round.  A prefix match is not a
    match: a name that starts with a legal name and continues with a
    separator would leave the root of the round, and the round would
    then write outside of the root that it sealed.

    The name is therefore refused when it is

    * not a string, empty or longer than 64 characters;
    * not exactly one segment of the closed character set;
    * a traversal (``..``) or a name that ends with a dot, because
      Windows would silently cut that dot and the directory of the plan
      would not be the directory that the round creates;
    * a device name of Windows (``NUL``, ``CON``, ``COM1`` ...), with
      or without an extension.
    """
    if not isinstance(value, str) or not value:
        raise CustodyError(code)
    if len(value) > DIRECTORY_NAME_MAX_LENGTH:
        raise CustodyError(code)
    if not _DIRECTORY_NAME.fullmatch(value):
        raise CustodyError(code)
    if '..' in value:
        raise CustodyError(code)
    if value.endswith('.') or value != value.strip():
        raise CustodyError(code)
    if value.split('.', 1)[0].upper() in WINDOWS_DEVICE_NAMES:
        raise CustodyError(code)
    return value


def _validate_role_data(name, data):
    if name == 'COMFY':
        _require_directory_name(data['user_directory'],
                                'CUSTODY_PLAN_ROLE_DATA_INVALID')
        return
    if name == 'SAMPLER':
        _require_absolute_windows_path(data['nvidia_exe'],
                                       'CUSTODY_PLAN_ROLE_DATA_INVALID')
        _require_text(data['nvidia_sha256'], r'[0-9a-f]{64}',
                      'CUSTODY_PLAN_ROLE_DATA_INVALID')
        _require_exact_int(data['max_seconds'], 'CUSTODY_PLAN_ROLE_DATA_INVALID',
                           minimum=1, maximum=MAX_SAMPLER_SECONDS)


def _freeze(value):
    """A read-only view of one validated document.

    The view is what the command of a role is built from.  A caller that
    holds the view cannot change it, and a caller that holds the
    presented copy of the plan cannot change the view either.
    """
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


class LaunchPlan:
    """The validated and sealed launch plan of one native custody round.

    The plan holds two things that cannot influence each other.

    * The **canonical** document: the validated document itself, deep
      copied once, at the moment of the validation.  Its normalized
      bytes and their digest are the seal of the plan, and the broker
      checks the very same bytes again when it consumes the plan.

    * The **read-only views** of the roles: the commands of the round
      are built from these views and never from a presented copy.

    The sealed form that is handed to a caller is a *copy* of the
    canonical document.  A caller that changes that copy changes
    nothing: the command of the role still comes from the read-only
    view of the canonical document.
    """

    __slots__ = ('run_id', 'candidate_sha', 'authorization_sha256',
                 'lease_expires_at', 'max_runtime_seconds', 'roles',
                 '_canonical')

    def __init__(self, run_id, candidate_sha, authorization_sha256,
                 lease_expires_at, max_runtime_seconds, roles):
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.lease_expires_at = lease_expires_at
        self.max_runtime_seconds = max_runtime_seconds
        self._canonical = {
            'schema': PLAN_SCHEMA,
            'run_id': run_id,
            'candidate_sha': candidate_sha,
            'authorization_sha256': authorization_sha256,
            'lease_expires_at': lease_expires_at,
            'max_runtime_seconds': max_runtime_seconds,
            'roles': [copy.deepcopy(dict(role)) for role in roles],
        }
        self.roles = tuple(_freeze(role) for role in self._canonical['roles'])

    @property
    def sealed(self):
        """A copy of the canonical document of the plan.

        The copy is a copy: a caller that writes into it writes into a
        temporary object and the plan of the round does not change.
        """
        return copy.deepcopy(self._canonical)

    def sealed_bytes(self):
        """The normalized bytes of the seal of the plan.

        The bytes are the one definition of the seal: the parent writes
        them, the parent hashes them and the broker hashes the very same
        bytes when it consumes the plan.
        """
        return json.dumps(self._canonical, ensure_ascii=False, sort_keys=True,
                          indent=2).encode('utf-8')

    def sealed_sha256(self):
        """The digest of the normalized bytes of the seal of the plan."""
        return hashlib.sha256(self.sealed_bytes()).hexdigest()


def validate_launch_plan(plan, *, now=None):
    """Validate one closed launch plan and return its sealed form.

    The plan is never repaired.  A plan that carries an unknown key, an
    unknown role, an arbitrary argument vector, a shell, a script, an
    environment or a PID is refused here, before anything is created.
    """
    if not isinstance(plan, dict):
        raise CustodyError('CUSTODY_PLAN_NOT_OBJECT')
    if set(plan) != PLAN_KEYS:
        raise CustodyError('CUSTODY_PLAN_KEY_SET_INVALID')
    if plan['schema'] != PLAN_SCHEMA:
        raise CustodyError('CUSTODY_PLAN_SCHEMA_INVALID')
    run_id = _require_text(plan['run_id'], r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',
                           'CUSTODY_PLAN_RUN_ID_INVALID')
    candidate_sha = _require_text(plan['candidate_sha'], r'[0-9a-f]{40}',
                                  'CUSTODY_PLAN_CANDIDATE_INVALID')
    authorization_sha256 = _require_text(plan['authorization_sha256'],
                                         r'[0-9a-f]{64}',
                                         'CUSTODY_PLAN_AUTHORIZATION_INVALID')
    wall = time.time() if now is None else _require_number(now, 'CUSTODY_PLAN_LEASE_INVALID')
    lease = _require_number(plan['lease_expires_at'], 'CUSTODY_PLAN_LEASE_INVALID')
    if lease <= wall:
        raise CustodyError('CUSTODY_PLAN_LEASE_EXPIRED')
    runtime = _require_exact_int(plan['max_runtime_seconds'],
                                 'CUSTODY_PLAN_RUNTIME_INVALID',
                                 minimum=1, maximum=MAX_RUNTIME_SECONDS)
    roles = plan['roles']
    if not isinstance(roles, list) or not roles or len(roles) > len(ROLE_ORDER):
        raise CustodyError('CUSTODY_PLAN_ROLES_INVALID')
    sealed_roles = {}
    logs = set()
    for item in roles:
        if not isinstance(item, dict) or set(item) != ROLE_KEYS:
            raise CustodyError('CUSTODY_PLAN_ROLE_INVALID')
        name = item['role']
        if not isinstance(name, str) or name not in ROLE_ORDER or name in sealed_roles:
            raise CustodyError('CUSTODY_PLAN_ROLE_INVALID')
        tools = item['tools']
        if not isinstance(tools, list) or len(tools) != ROLE_TOOL_COUNTS[name]:
            raise CustodyError('CUSTODY_PLAN_TOOL_INVALID')
        sealed_tools = []
        paths = set()
        for tool in tools:
            if not isinstance(tool, dict) or set(tool) != TOOL_KEYS:
                raise CustodyError('CUSTODY_PLAN_TOOL_INVALID')
            path = _require_absolute_windows_path(tool['path'], 'CUSTODY_PLAN_TOOL_INVALID')
            _require_text(tool['sha256'], r'[0-9a-f]{64}', 'CUSTODY_PLAN_TOOL_INVALID')
            if path.casefold() in paths:
                raise CustodyError('CUSTODY_PLAN_TOOL_INVALID')
            paths.add(path.casefold())
            sealed_tools.append({'path': path, 'sha256': tool['sha256']})
        data = item['data']
        if not isinstance(data, dict) or set(data) != ROLE_DATA_KEYS[name]:
            raise CustodyError('CUSTODY_PLAN_ROLE_DATA_INVALID')
        _validate_role_data(name, data)
        log = _require_log_reference(item['log'])
        if log.casefold() in logs:
            raise CustodyError('CUSTODY_PLAN_LOG_INVALID')
        logs.add(log.casefold())
        sealed_roles[name] = {'role': name, 'tools': sealed_tools,
                              'data': dict(data), 'log': log}
    if any(name not in sealed_roles for name in REQUIRED_ROLES):
        raise CustodyError('CUSTODY_PLAN_ROLES_INVALID')
    ordered = [sealed_roles[name] for name in ROLE_ORDER if name in sealed_roles]
    return LaunchPlan(run_id, candidate_sha, authorization_sha256, float(lease),
                      runtime, ordered)


def enforce_child_budget(plan, *, parent_child_remaining_seconds):
    """Bind the runtime of the round to the finite budget of the parent.

    The remaining budget of the parent child is an input of the parent.  It
    is never read from a ledger here and it is never invented: a parent that
    has no remaining budget refuses the round instead of starting one.
    """
    remaining = _require_exact_int(parent_child_remaining_seconds,
                                   'CUSTODY_NO_CHILD_BUDGET_REMAINING', minimum=1)
    if plan.max_runtime_seconds > remaining:
        raise CustodyError('CUSTODY_CHILD_BUDGET_TOO_SMALL')
    return remaining


# -- the private control channel -------------------------------------------

def _strict_pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise CustodyError('CUSTODY_FRAME_INVALID')
        value[key] = item
    return value


def _reject_constant(_value):
    raise CustodyError('CUSTODY_FRAME_INVALID')


def decode_frame(raw, *, limit=MAX_FRAME_BYTES):
    """Decode one frame of the private channel with the strict rules."""
    if not isinstance(raw, (bytes, bytearray)):
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if len(raw) > limit:
        raise CustodyError('CUSTODY_FRAME_TOO_LARGE')
    try:
        text = bytes(raw).decode('utf-8')
    except UnicodeDecodeError as error:
        raise CustodyError('CUSTODY_FRAME_INVALID') from error
    try:
        value = json.loads(text, object_pairs_hook=_strict_pairs,
                           parse_constant=_reject_constant)
    except CustodyError:
        raise
    except (ValueError, TypeError) as error:
        raise CustodyError('CUSTODY_FRAME_INVALID') from error
    if not isinstance(value, dict):
        raise CustodyError('CUSTODY_FRAME_INVALID')
    return value


def encode_command(command, *, run_id, candidate_sha, authorization_sha256,
                   nonce, sequence):
    """Encode one command of the parent for the private channel."""
    if command not in COMMANDS:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    _require_exact_int(sequence, 'CUSTODY_FRAME_SEQUENCE_INVALID', minimum=1)
    frame = {'schema': CHANNEL_SCHEMA, 'command': command, 'run_id': run_id,
             'candidate_sha': candidate_sha,
             'authorization_sha256': authorization_sha256,
             'nonce': nonce, 'sequence': sequence}
    raw = json.dumps(frame, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > MAX_FRAME_BYTES:
        raise CustodyError('CUSTODY_FRAME_TOO_LARGE')
    return raw + b'\n'


def decode_command(raw, *, run_id, candidate_sha, authorization_sha256,
                   nonce, last_sequence):
    """Decode and check one command that the parent sent to the broker."""
    value = decode_frame(raw)
    if set(value) != COMMAND_KEYS:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if value['schema'] != CHANNEL_SCHEMA:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if value['command'] not in COMMANDS:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if (value['run_id'] != run_id or value['candidate_sha'] != candidate_sha
            or value['authorization_sha256'] != authorization_sha256
            or value['nonce'] != nonce):
        raise CustodyError('CUSTODY_FRAME_IDENTITY_MISMATCH')
    sequence = value['sequence']
    if type(sequence) is not int or sequence < 1:
        raise CustodyError('CUSTODY_FRAME_SEQUENCE_INVALID')
    if last_sequence is not None and sequence <= last_sequence:
        raise CustodyError('CUSTODY_FRAME_SEQUENCE_INVALID')
    return value


def decode_reply(raw, *, run_id, candidate_sha, authorization_sha256,
                 nonce, last_sequence):
    """Decode and check one reply that the broker sent to the parent."""
    value = decode_frame(raw)
    if set(value) != REPLY_KEYS:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if value['schema'] != CHANNEL_SCHEMA:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if value['kind'] not in REPLIES:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if (value['run_id'] != run_id or value['candidate_sha'] != candidate_sha
            or value['authorization_sha256'] != authorization_sha256
            or value['nonce'] != nonce):
        raise CustodyError('CUSTODY_FRAME_IDENTITY_MISMATCH')
    sequence = value['sequence']
    if type(sequence) is not int or sequence < 1:
        raise CustodyError('CUSTODY_FRAME_SEQUENCE_INVALID')
    if last_sequence is not None and sequence <= last_sequence:
        raise CustodyError('CUSTODY_FRAME_SEQUENCE_INVALID')
    if value['state'] not in STATES:
        raise CustodyError('CUSTODY_FRAME_INVALID')
    if not isinstance(value['detail'], dict):
        raise CustodyError('CUSTODY_FRAME_INVALID')
    return value


# -- the one reader of the private channel --------------------------------

class _ReplyWaiter:
    """One waiting owner of one kind of reply."""

    __slots__ = ('kinds', 'event', 'reply')

    def __init__(self, kinds):
        self.kinds = kinds
        self.event = threading.Event()
        self.reply = None


class _ChannelPump(threading.Thread):
    """The one reader of the private control channel of one round.

    The pump is the single owner of the read side of the channel.  It is
    one thread, it is joined by the owner of the round and it is never a
    pool of workers.  Its failure is visible: the waiters of the round
    are woken and the round keeps the failure instead of waiting for a
    reply that will never arrive.

    A reply that nobody waits for is kept, but only the last status
    reply is kept: a round that runs for hours would otherwise fill the
    channel with the answers of its own heartbeat.
    """

    def __init__(self, broker, *, decode, clock=None):
        super().__init__(daemon=True, name='lvw-native-custody-channel-pump')
        self._broker = broker
        self._decode = decode
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._waiters = []
        self._pending = []
        self._latest_status = None
        self._error = None
        self._eof = False
        self._frames = 0
        self._stop = threading.Event()
        self._finished = threading.Event()

    # -- the reading ------------------------------------------------------
    def run(self):
        try:
            while not self._stop.is_set():
                raw = self._broker.read(CHANNEL_POLL_SECONDS)
                if raw is None:
                    continue
                if raw == b'':
                    self._eof = True
                    break
                reply = self._decode(raw)
                self._frames += 1
                self._deliver(reply)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._error = error
        finally:
            with self._lock:
                for waiter in self._waiters:
                    waiter.event.set()
                self._waiters = []
            self._finished.set()

    def _deliver(self, reply):
        with self._lock:
            for waiter in list(self._waiters):
                if reply['kind'] in waiter.kinds:
                    waiter.reply = reply
                    waiter.event.set()
                    self._waiters.remove(waiter)
                    return
            if reply['kind'] == 'STATUS':
                # The status of the round is a snapshot, not a queue: only
                # the last one is kept.
                self._latest_status = reply
                return
            if len(self._pending) >= MAX_FRAMES:
                raise CustodyError('CUSTODY_FRAME_COUNT_EXCEEDED')
            self._pending.append(reply)

    # -- the waiting ------------------------------------------------------
    def take(self, kinds, deadline):
        """Wait for one reply of the wanted kinds, bounded by the deadline."""
        waiter = _ReplyWaiter(kinds)
        with self._lock:
            for index, reply in enumerate(self._pending):
                if reply['kind'] in kinds:
                    del self._pending[index]
                    return reply
            if 'STATUS' in kinds and self._latest_status is not None:
                reply = self._latest_status
                self._latest_status = None
                return reply
            if self._error is not None:
                raise self._error
            if self._eof:
                raise CustodyError('CUSTODY_CHANNEL_EOF')
            self._waiters.append(waiter)
        remaining = deadline - self._clock()
        if not waiter.event.wait(max(0.0, remaining)):
            with self._lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
            raise CustodyError('CUSTODY_CHANNEL_TIMEOUT')
        if waiter.reply is not None:
            return waiter.reply
        with self._lock:
            failure = self._error
        if failure is not None:
            raise failure
        raise CustodyError('CUSTODY_CHANNEL_EOF')

    # -- the end ----------------------------------------------------------
    def stop(self):
        """Ask the pump to stop.  The pump is joined by its owner."""
        self._stop.set()

    def join_bounded(self, seconds):
        """Join the pump and report whether it really stopped."""
        self.join(seconds)
        stopped = not self.is_alive()
        return stopped

    @property
    def frames(self):
        return self._frames

    @property
    def error(self):
        return self._error

    @property
    def finished(self):
        return self._finished.is_set()

    @property
    def alive(self):
        return self.is_alive()


# -- the parent side session -----------------------------------------------

class NativeCustodySession:
    """The parent side custody of one native custody round.

    The session owns the validated plan, the original handle of the broker
    process of this round and the private control channel to it.  It never
    stops a native service by name, by PID or by a record of another owner.

    The session is deliberately *not* a service platform.  It launches one
    broker process, it exchanges the closed frames of the private channel
    with it and it closes it again.  It never loads a caller supplied
    module, it never builds an argument vector of its own and it never
    starts a native service itself: the broker is the only creator of the
    processes of a round.

    Every failure of the start of the round ends inside ``start``: the
    original handle of the broker and the private channel are released
    there, and the caller never has to remember to stop a round that never
    started.
    """

    def __init__(self, *, plan, run_root, parent_child_remaining_seconds,
                 launcher=None, clock=None, wall=None, nonce=None):
        self._document = plan
        self._run_root = Path(run_root)
        self._remaining = parent_child_remaining_seconds
        self._launcher = launcher
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        self._nonce = self._resolve_nonce(nonce)
        self.state = 'NEW'
        self.plan = None
        self.broker = None
        self._sequence = 0
        self._broker_sequence = 0
        self._frames_sent = 0
        self._frames_received = 0
        self._deadline_wall = None
        self._deadline_mono = None
        self._stopped = False
        self._failures = []
        self._terminal = None
        self._broker_identity = None
        self._broker_reader_finished = None
        self._pump = None
        self._heartbeat = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_failure = None
        self._last_heartbeat = None
        self._last_alive_wall = None
        self._write_lock = threading.Lock()
        self._close_attempted = False
        self._broker_close_failed = False
        self._cleanup_deadline = None

    # -- the nonce of the round -------------------------------------------
    @staticmethod
    def _resolve_nonce(nonce):
        """The nonce of the private channel of one round.

        The parent and the broker agree on one closed form: 32
        hexadecimal characters.  A nonce that does not have that form is
        refused here, before any directory, before any file and before
        any process.  A nonce identifies the channel of one round and it
        grants no custody over any process.
        """
        if nonce is None:
            return os.urandom(NONCE_BYTES).hex()
        if not isinstance(nonce, str) or not re.fullmatch(NONCE_PATTERN, nonce):
            raise CustodyError('CUSTODY_NONCE_INVALID')
        return nonce

    # -- the deadline ----------------------------------------------------
    def _fix_deadline(self):
        """Fix the absolute deadline of the round, once.

        The deadline is the earlier of the absolute lease of the plan, the
        runtime of the plan and the remaining budget of the parent.  It is
        fixed here, before the broker is launched and before the first
        reply of the round, and it is never moved again: a status request,
        a heartbeat or a stop command may not extend it.
        """
        if self._deadline_wall is not None:
            return self._deadline_wall
        wall_now = self._wall()
        self._deadline_wall = min(self.plan.lease_expires_at,
                                  wall_now + self.plan.max_runtime_seconds,
                                  wall_now + self._remaining)
        self._deadline_mono = self._clock() + max(0.0, self._deadline_wall - wall_now)
        return self._deadline_wall

    def remaining_seconds(self):
        if self._deadline_mono is None:
            return float(self._remaining)
        return max(0.0, self._deadline_mono - self._clock())

    # -- the plan --------------------------------------------------------
    def validate(self):
        """Validate the plan of the round and bind the finite budget."""
        if self.state != 'NEW':
            raise CustodyError('CUSTODY_STATE_INVALID')
        self.plan = validate_launch_plan(self._document, now=self._wall())
        enforce_child_budget(self.plan,
                             parent_child_remaining_seconds=self._remaining)
        self.state = 'VALIDATED'
        return self.plan

    # -- the channel -----------------------------------------------------
    def _send(self, command, *, terminal=False):
        """Send one command of the parent to the broker.

        The write is bounded three times: by the absolute deadline of
        the round, by the remaining time of the round and by a fixed
        short budget of its own.  A broker that never reads can
        therefore never hold the supervisor of the round forever, and
        the failure of the write is a named failure of the round.

        The frame budget of the channel is shared by the frames that the
        parent sends and by the frames that it receives.  The frames of
        the terminal exchange are reserved and the budget is never
        widened and never renewed.
        """
        raw = encode_command(command, run_id=self.plan.run_id,
                             candidate_sha=self.plan.candidate_sha,
                             authorization_sha256=self.plan.authorization_sha256,
                             nonce=self._nonce, sequence=self._sequence + 1)
        with self._write_lock:
            self._check_frame_budget(terminal=terminal)
            self._sequence += 1
            self._frames_sent += 1
            budget = max(0.0, min(self.remaining_seconds(), WRITE_BUDGET_SECONDS))
            deadline = self._clock() + budget
            self._write_to_broker(raw, deadline)

    def _check_frame_budget(self, *, terminal=False):
        """The frame budget of the channel, in both directions.

        The round of six hours with its heartbeat stays inside the
        budget of the channel, and the frames of the terminal exchange
        are reserved.  A round that reached its budget fails closed: it
        never reconnects and it never renews its lease.
        """
        reserved = 0 if terminal else RESERVED_TERMINAL_FRAMES
        if self._frames_sent + self._frames_received + reserved + 1 > MAX_FRAMES:
            raise CustodyError('CUSTODY_FRAME_BUDGET_EXCEEDED')

    def _write_to_broker(self, raw, deadline):
        """Write one frame through the deadline aware interface.

        The handle of the broker has to say that it understands an
        absolute deadline.  A handle that does not say so is **never**
        assumed to be deadline aware: the parent refuses to write into
        it instead of blocking on a write that nobody bounds.
        """
        writer = getattr(self.broker, 'write', None)
        if not callable(writer):
            raise CustodyError('CUSTODY_BROKER_WRITE_INTERFACE_MISSING')
        if getattr(self.broker, 'channel_deadline_aware', False) is not True:
            raise CustodyError('CUSTODY_BROKER_NOT_DEADLINE_AWARE')
        writer(raw, deadline)

    def _bind_deadline(self, deadline):
        """Bind the absolute deadline of the round to the broker handle.

        The deadline may only shorten the deadline that is already
        bound.  A handle that does not offer the interface is left
        alone: the session still bounds its own waits.
        """
        if self.broker is None:
            return
        binder = getattr(self.broker, 'bind_channel_deadline', None)
        if not callable(binder):
            return
        binder(deadline)

    def _read_reply(self, kinds, *, timeout=None):
        """Read the replies of the broker until one of them is wanted.

        The read never blocks the deadline of the round: the transport of
        the channel is bounded and the wait is clipped to the remaining
        deadline of the round.
        """
        if self._heartbeat_failure is not None:
            raise CustodyError(self._heartbeat_failure)
        limit = self.remaining_seconds() if timeout is None else timeout
        limit = max(0.0, min(limit, self.remaining_seconds()))
        deadline = self._clock() + limit
        while True:
            if self._pump is None:
                raise CustodyError('CUSTODY_CHANNEL_CLOSED')
            reply = self._pump.take(kinds, deadline)
            if reply['kind'] in kinds:
                return reply

    def _decode_reply(self, raw):
        """Decode one reply of the broker and check the identity of it."""
        self._frames_received += 1
        if self._frames_received > MAX_FRAMES:
            raise CustodyError('CUSTODY_FRAME_COUNT_EXCEEDED')
        reply = decode_reply(raw, run_id=self.plan.run_id,
                             candidate_sha=self.plan.candidate_sha,
                             authorization_sha256=self.plan.authorization_sha256,
                             nonce=self._nonce,
                             last_sequence=self._broker_sequence)
        self._broker_sequence = reply['sequence']
        # Only a reply that was decoded and that carries the identity of
        # the round refreshes the liveness of the round.
        self._last_alive_wall = self._wall()
        return reply

    # -- the heartbeat ----------------------------------------------------
    def _heartbeat_step(self):
        """One step of the status heartbeat of the round.

        The heartbeat is the explicit owner of the keep alive of the
        round: it sends one status command of the parent every 60
        seconds, so that a long round is not stopped for silence.  It
        never extends the absolute deadline of the round: it is a frame
        of the closed protocol and nothing else.

        The step is a method of its own and it reads the clock of the
        session, so that the whole schedule of a round of six hours can
        be checked with a clock that only moves when the check moves it.
        """
        now = self._clock()
        if self._last_heartbeat is None:
            self._last_heartbeat = now
            return False
        if now - self._last_heartbeat < HEARTBEAT_INTERVAL_SECONDS:
            return False
        self._last_heartbeat = now
        try:
            self._send('STATUS')
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._heartbeat_failure = ('CUSTODY_HEARTBEAT_FAILED:'
                                       + type(error).__name__)
            self._failures.append(self._heartbeat_failure)
            return False
        return True

    def _start_heartbeat(self):
        """Start the status heartbeat of the round.

        There is exactly one heartbeat thread per round and it is joined
        by the owner of the round.  A failure of the heartbeat is a
        named failure of the round: the round becomes unknown and it is
        never stopped silently in the background.
        """
        if self._heartbeat is not None:
            return
        self._heartbeat_stop = threading.Event()

        def beat():
            while not self._heartbeat_stop.wait(HEARTBEAT_SLICE_SECONDS):
                try:
                    self._heartbeat_step()
                except BaseException as error:  # noqa: BLE001 - the failure stays visible
                    self._heartbeat_failure = ('CUSTODY_HEARTBEAT_FAILED:'
                                               + type(error).__name__)
                    self._failures.append(self._heartbeat_failure)
                    return

        self._heartbeat = threading.Thread(target=beat, daemon=True,
                                            name='lvw-native-custody-heartbeat')
        self._heartbeat.start()

    def _stop_background(self):
        """Stop the background threads of the round and join them.

        A thread that does not stop within its bounded join is a fact of
        the round: it is named and the round becomes unknown.  It is
        never left behind and it is never discarded.
        """
        if self._heartbeat is not None:
            self._heartbeat_stop.set()
            self._heartbeat.join(THREAD_JOIN_SECONDS)
            if self._heartbeat.is_alive():
                self._failures.append('CUSTODY_HEARTBEAT_NOT_STOPPED')
                self.state = 'UNKNOWN_RETAINED'
            self._heartbeat = None
        if self._pump is not None:
            self._pump.stop()
            if not self._pump.join_bounded(THREAD_JOIN_SECONDS):
                self._failures.append('CUSTODY_PUMP_NOT_STOPPED')
                self.state = 'UNKNOWN_RETAINED'
            self._pump = None

    # -- the lifecycle ----------------------------------------------------
    def start(self):
        """Start the broker of the round and take the custody of it.

        The parent keeps the *original* handle of the broker.  The identity
        of the broker is therefore read from that handle and never from a
        claim of the broker itself: a child that reports its own pid is a
        claim and not a proof.

        Every failure of this method releases the original handle of the
        broker and the private channel before it leaves the method.  A
        refusal of the broker, a timeout, a parse error, an ordinary
        exception and a cancellation all end the same way: the round is
        closed here and the caller never has to stop a round that never
        started.
        """
        if self.state == 'NEW':
            self.validate()
        if self.state != 'VALIDATED':
            raise CustodyError('CUSTODY_STATE_INVALID')
        self._fix_deadline()
        launcher = self._launcher or _default_launcher
        try:
            self.broker = launcher(self.plan, self._run_root, self._nonce)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self.state = 'UNKNOWN_RETAINED'
            self._failures.append('CUSTODY_BROKER_LAUNCH_FAILED:'
                                   + type(error).__name__)
            raise
        if self.broker is None:
            self.state = 'UNKNOWN_RETAINED'
            self._failures.append('CUSTODY_BROKER_LAUNCH_UNAVAILABLE')
            raise CustodyError('CUSTODY_BROKER_LAUNCH_UNAVAILABLE')
        self._broker_identity = {
            'pid': getattr(self.broker, 'pid', None),
            'executable': getattr(self.broker, 'executable', None),
            'executable_sha256': getattr(self.broker, 'executable_sha256', None),
            'identity_source': 'PARENT_ORIGINAL_HANDLE',
            'reported_by_the_broker': False,
        }
        # The absolute deadline of the round is bound to the handle of
        # the broker before the first frame of the round is read: the
        # channel of the round can never outlive the round.
        try:
            self._bind_deadline(self._deadline_mono)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append(self._failure_code(error))
            self.state = 'UNKNOWN_RETAINED'
            self._close_broker()
            raise
        self._pump = _ChannelPump(self.broker, decode=self._decode_reply,
                                  clock=self._clock)
        self._pump.start()
        self._start_heartbeat()
        try:
            ready = self._read_reply(('READY', 'REFUSED'))
            if ready['kind'] == 'REFUSED':
                self.state = 'UNKNOWN_RETAINED'
                self._failures.append(ready['detail'].get('code', 'BROKER_REFUSED'))
                self._close_broker()
                return self.evidence()
            self.state = ready['state']
            if ready['state'] != 'ARMED':
                raise CustodyError('CUSTODY_STATE_INVALID')
            status = self._read_reply(('STATUS', 'REFUSED'))
            if status['kind'] == 'REFUSED':
                self.state = 'UNKNOWN_RETAINED'
                self._failures.append(status['detail'].get('code', 'BROKER_REFUSED'))
                self._close_broker()
                return self.evidence()
            self.state = status['state']
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append(self._failure_code(error))
            self.state = 'UNKNOWN_RETAINED'
            # The handle of the broker is released even when the exchange
            # of the start failed: the resource of this round is never left
            # open on purpose and the caller never has to stop it later.
            self._close_broker()
            raise
        return self.evidence()

    @staticmethod
    def _failure_code(error):
        """The named code of one failure of the round."""
        code = getattr(error, 'code', None)
        if isinstance(code, str) and code:
            return code
        return 'CUSTODY_SESSION_FAILED:' + type(error).__name__

    def stop(self):
        """Stop the round and close the original handle of the broker.

        The stop is idempotent: a repeated stop does not send a second
        command, does not create anything and does not change the evidence
        of the round.  The closure of the broker happens in a ``finally``,
        so it also happens when the exchange of the stop failed.

        The wait for the answer of the stop has its own short cleanup
        budget.  It never borrows the remaining runtime of the round: a
        round that is stopped does not get a new and unauthorised grace
        period of hours.
        """
        if self._stopped:
            return self.evidence()
        self._stopped = True
        # The stop and the cleanup share ONE budget: the smaller of the
        # fixed cleanup budget of the round and the time that is left.
        # No layer of the cleanup adds a budget of its own and the round
        # never borrows its whole remaining runtime.
        budget = max(0.0, min(STOP_CLEANUP_SECONDS, self.remaining_seconds()))
        cleanup_deadline = self._clock() + budget
        self._cleanup_deadline = cleanup_deadline
        try:
            if self.broker is not None and self.state in ('ARMED', 'RUNNING'):
                self._bind_deadline(cleanup_deadline)
                self._send('STOP', terminal=True)
                reply = self._read_reply(
                    ('STOPPED', 'REFUSED'),
                    timeout=max(0.0, cleanup_deadline - self._clock()))
                self.state = reply['state']
                self._terminal = reply['detail']
                if reply['kind'] == 'REFUSED':
                    self._failures.append(reply['detail'].get('code', 'BROKER_REFUSED'))
            elif self.broker is None:
                self._failures.append('CUSTODY_BROKER_NOT_STARTED')
                self.state = 'UNKNOWN_RETAINED'
        except CustodyError as error:
            self._failures.append(error.code)
            self.state = 'UNKNOWN_RETAINED'
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            # An ordinary failure of the stop is a named failure of the
            # round: the evidence of the round keeps it and the stop
            # does not raise over the evidence.
            self._failures.append(self._failure_code(error))
            self.state = 'UNKNOWN_RETAINED'
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            # A cancellation is cleaned up and it continues to propagate.
            self._failures.append(self._failure_code(error))
            self.state = 'UNKNOWN_RETAINED'
            raise
        finally:
            self._close_broker()
        return self.evidence()

    def _close_broker(self):
        """Close the original handle of the broker, exactly once.

        A handle that could not be closed is *kept*: the reference of the
        original handle stays in the evidence of the round and the round
        stays unknown.  A failed close is never swallowed and never
        replaced by a success.
        """
        if self.broker is None or self._close_attempted:
            return
        broker = self.broker
        self._close_attempted = True
        self._stop_background()
        deadline = self._cleanup_deadline
        if deadline is None:
            deadline = self._clock() + max(
                0.0, min(STOP_CLEANUP_SECONDS, self.remaining_seconds()))
        try:
            self._bind_deadline(deadline)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append(self._failure_code(error))
        try:
            facts = broker.close()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append('CUSTODY_BROKER_CLOSE_FAILED:'
                                   + type(error).__name__)
            self._broker_close_failed = True
            self.state = 'UNKNOWN_RETAINED'
            self._broker_reader_finished = getattr(broker, 'reader_finished', None)
            return
        if isinstance(facts, dict):
            for key, value in sorted(facts.items()):
                if value is False:
                    self._failures.append('CUSTODY_BROKER_CLOSE_INCOMPLETE:' + key)
                    self._broker_close_failed = True
                    self.state = 'UNKNOWN_RETAINED'
        self._broker_reader_finished = getattr(broker, 'reader_finished', None)
        self.broker = None

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        try:
            self.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            self.state = 'UNKNOWN_RETAINED'
        return False

    # -- the evidence ------------------------------------------------------
    def evidence(self):
        """The evidence of the round.

        Every native claim of this evidence is ``NOT_PROVEN``.  This package
        has never executed a Windows service, so it may not claim that a
        service was released, that a GPU was released, that a port was
        released or that a parent crash is survived.
        """
        return {
            'kind': 'lvw.s3-native-custody-evidence/1',
            'state': self.state,
            'run_id': self.plan.run_id if self.plan is not None else None,
            'candidate_sha': self.plan.candidate_sha if self.plan is not None else None,
            'authorization_sha256': (self.plan.authorization_sha256
                                     if self.plan is not None else None),
            'grant_authority': 'NOT_VERIFIED',
            'plan_sha256_proves': 'PLAN_INTEGRITY_ONLY',
            'plan': self.plan.sealed if self.plan is not None else None,
            'plan_sha256': (self.plan.sealed_sha256()
                            if self.plan is not None else None),
            'broker': self._broker_identity,
            'broker_channel_reader_finished': self._broker_reader_finished,
            'broker_retained': self.broker is not None,
            'broker_close_failed': self._broker_close_failed,
            'broker_deadline_aware': (getattr(self.broker, 'channel_deadline_aware', False)
                                      is True),
            'broker_channel_deadline_bound': getattr(self.broker, 'write_deadline', None),
            'channel': {
                'schema': CHANNEL_SCHEMA,
                'nonce': self._nonce,
                'frames_sent': self._frames_sent,
                'frames_received': self._frames_received,
                'last_sequence_sent': self._sequence,
                'last_sequence_received': self._broker_sequence,
                'frame_limit': MAX_FRAMES,
                'frame_bytes_limit': MAX_FRAME_BYTES,
                'private_to_the_parent': True,
                'heartbeat_interval_seconds': HEARTBEAT_INTERVAL_SECONDS,
                'heartbeat_missing_seconds': HEARTBEAT_MISSING_SECONDS,
                'heartbeat_failure': self._heartbeat_failure,
                'last_alive_wall': self._last_alive_wall,
                'frame_budget_total': MAX_FRAMES,
                'frame_budget_reserved_terminal': RESERVED_TERMINAL_FRAMES,
                'stop_cleanup_budget_seconds': STOP_CLEANUP_SECONDS,
            },
            'lease': {
                'lease_expires_at': self.plan.lease_expires_at if self.plan is not None else None,
                'max_runtime_seconds': (self.plan.max_runtime_seconds
                                        if self.plan is not None else None),
                'parent_child_remaining_seconds': self._remaining,
                'effective_deadline_wall': self._deadline_wall,
                'deadline_extended': False,
                'absolute': True,
            },
            'terminal': self._terminal,
            'failures': list(self._failures),
            # The claims that this package does not make.
            'native_execution_proven': False,
            'native_cleanup_proven': False,
            'gpu_released_proven': False,
            'port_released_proven': False,
            'sampler_proven': False,
            'parent_crash_recovery_proven': False,
            'windows_stdin_eof_proven': False,
            'admission_produced': False,
            'stage_pass_claim': False,
            'product_gate0': False,
        }


def _default_launcher(plan, run_root, nonce):
    """The production launcher of the broker of this package.

    The launcher is deliberately inert here.  The broker of this package is
    a Windows process and this package has never started one, so the
    launcher refuses on every platform instead of pretending that a native
    execution exists.  The wiring of the launcher into the parent
    controller is a later owner and it is not enabled by this package.
    """
    from tools.v0_s3_native_broker import launch_broker
    return launch_broker(plan, run_root, nonce)
