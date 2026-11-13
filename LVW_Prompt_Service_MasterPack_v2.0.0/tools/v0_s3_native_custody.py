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

The close of the round is coordinated by **one** owner and **one**
absolute deadline.

* the first caller of the close owns it and every other caller waits
  for the close that is in flight inside that very deadline, so that a
  caller never returns a success before the cleanup could finish;

* the end of the attempt of the close is published in a ``finally`` and
  the state of the close is explicit: ``NOT_STARTED``, ``IN_PROGRESS``
  or ``FINISHED``.  ``FINISHED`` means that the attempt ended and it
  never means that the resources of the round are released: only the
  facts of the close prove that;

* no background thread of the round starts after the close began: the
  permission to start one is closed before the close takes its snapshot
  of the threads, and the stop event of the heartbeat is never rebuilt.
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

# The facts that the close of the broker has to report before the
# parent may forget the original reference of the broker.  Every one of
# them has to be present in the facts of the close and it has to be
# exactly ``True``.  A missing fact, a ``None``, a ``False`` and an
# unknown value are all unknown: the original broker is kept and the
# round stays unknown.
#
# The list is **strict**.  The channel, the process and its original
# handle are not enough: the reader of the channel has to have really
# stopped without an error, the two ends of the channel have to be
# closed and the original handles of the workers of the endpoints have
# to be released.  A close that proves only three facts does not prove
# that the resources of the round are released.
REQUIRED_CLOSE_FACTS = ('channel_closed', 'process_exited',
                        'process_handle_released', 'channel_reader_finished',
                        'read_end_closed', 'write_end_closed',
                        'worker_thread_handle_released')
# The facts of the close that have to be present and that have to be
# zero.  A missing fact is a missing fact and not a zero.
REQUIRED_CLOSE_ZERO_FACTS = ('channel_retained_workers',)
# The facts of the reader of the channel.  They are facts of the close
# and not of the round: they are checked when they are present.
READER_CLOSE_FACTS = ('channel_reader_finished', 'reader_finished')

# The three states of the close of one round.  NOT_STARTED is the state
# of a round whose close never began.  IN_PROGRESS is the state of a
# close that is running right now.  FINISHED is the state of a close
# whose **attempt** ended: it never means that the resources of the
# round are released, only the facts of the close prove that.
CLOSE_STATES = ('NOT_STARTED', 'IN_PROGRESS', 'FINISHED')

# The slice of the wait of a competitor of the close.  The wait is
# sliced so that the shared deadline of the cleanup is honoured by the
# clock of the round and not only by the clock of the host: a clock
# that the round controls can make the deadline arrive at once.
CLOSE_WAIT_SLICE_SECONDS = 0.05


class CustodyError(RuntimeError):
    """A refused custody step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


# -- the one context of a round ---------------------------------------------

class _CustodyContext:
    """The ONE finite startup and cleanup context of one round.

    The context holds the four things that every layer of the round has
    to share and that may never be copied from one layer into the next
    one.

    * The **clock** of the round, so that every deadline of the round is
      expressed in one domain.

    * The **absolute deadline** of the round.  It is fixed once and it
      may only be shortened.

    * The **one cleanup deadline**.  It is published **once**, by the
      first caller that enters the cleanup, and every later caller
      reuses that very value.  The publication is one atomic step under
      the lock of the context: two callers that entered the cleanup at
      the same moment always see the same number and the deadline is
      never generated twice.

    * The three **one way latches** of the round: the cancel, the stop
      and the unknown.  A latch that was set is never cleared, and a
      late event may never overwrite the unknown of the round.

    The session, the send of the round, the stop of the background
    threads and the close of the broker all hold this **one object**.
    A layer that only copied the number of a deadline would be a layer
    with a deadline of its own.
    """

    def __init__(self, *, clock=None, wall=None):
        self.clock = clock or time.monotonic
        self.wall = wall or time.time
        self._lock = threading.RLock()
        self._absolute_deadline = None
        self._cleanup_deadline = None
        # The one way latches of the round.
        self.cancel = threading.Event()
        self.stopping = threading.Event()
        self.unknown = threading.Event()

    # -- the deadlines ----------------------------------------------------
    def bind_absolute_deadline(self, deadline):
        """Bind the absolute deadline of the round.  It may only shorten."""
        if deadline is None:
            return self._absolute_deadline
        with self._lock:
            if self._absolute_deadline is None or deadline < self._absolute_deadline:
                self._absolute_deadline = deadline
            return self._absolute_deadline

    @property
    def absolute_deadline(self):
        with self._lock:
            return self._absolute_deadline

    def cleanup_deadline_value(self):
        """The published cleanup deadline, or ``None`` before the first."""
        with self._lock:
            return self._cleanup_deadline

    def publish_cleanup_deadline(self, value):
        """Publish the ONE cleanup deadline of the round, atomically.

        The first caller publishes the value and every later caller
        receives the very same value.  A later caller may never extend
        the deadline of the cleanup and it may never replace it.
        """
        with self._lock:
            if self._cleanup_deadline is None:
                self._cleanup_deadline = value
            return self._cleanup_deadline

    def remaining_cleanup(self):
        """The seconds that are left until the cleanup deadline.

        The value is recomputed on every call: a wait that already
        consumed part of the budget never receives the whole budget
        again.
        """
        with self._lock:
            value = self._cleanup_deadline
        if value is None:
            return 0.0
        return max(0.0, value - self.clock())

    # -- the one way latches ----------------------------------------------
    def request_cancel(self):
        """Ask for the cancellation of the round.  One way."""
        self.cancel.set()

    def request_stop(self):
        """Ask for the stop of the round.  One way."""
        self.stopping.set()

    def latch_unknown(self):
        """Latch the unknown state of the round.  One way."""
        if self.unknown.is_set():
            return False
        self.unknown.set()
        return True

    def is_unknown(self):
        """Whether the unknown state of the round was latched."""
        return self.unknown.is_set()


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

    def __init__(self, broker, *, decode, clock=None, on_error=None):
        super().__init__(daemon=True, name='lvw-native-custody-channel-pump')
        self._broker = broker
        self._decode = decode
        self._clock = clock or time.monotonic
        # The owner of the round is told about a failure of the pump.
        # A pump that died is not a silent event: the round latches its
        # unknown state and closes itself in a bounded way.
        self._on_error = on_error
        self._lock = threading.Lock()
        self._waiters = []
        self._pending = []
        self._latest_status = None
        self._error = None
        self._eof = False
        self._frames = 0
        # The name of the cancel flag is not ``_stop``: the base class of
        # the thread uses that name for its own method and a shadow of it
        # would break the join of the thread.
        self._stop_event = threading.Event()
        self._finished = threading.Event()

    # -- the reading ------------------------------------------------------
    def run(self):
        try:
            while not self._stop_event.is_set():
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
            if self._on_error is not None:
                try:
                    self._on_error(error)
                except BaseException:  # noqa: BLE001 - the failure stays visible
                    pass
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
        self._stop_event.set()

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
        self._broker_close_facts = None
        self._pump = None
        # The failure that the reader of the channel really saw.  It is
        # kept with the round, because the reader may be gone when the
        # owner of the round reads the first reply: a cancellation that
        # the reader saw is the failure of the round and it continues to
        # propagate.
        self._pump_error = None
        self._heartbeat = None
        # The stop event of the heartbeat is created **once**, here, and
        # it is never rebuilt: a rebuilt event would let a heartbeat
        # that starts after the stop of the round wait for a stop that
        # will never come.
        self._heartbeat_stop = threading.Event()
        self._heartbeat_failure = None
        self._last_heartbeat = None
        self._last_alive_wall = None
        self._write_lock = threading.Lock()
        # The one owner of the frame budget of the round.  The frames
        # that the parent sends and the frames that it receives share
        # this one lock, so that the check and the commit of the budget
        # are one atomic step in both directions.
        self._budget_lock = threading.Lock()
        # The one owner of the state of the round.  The latch of the
        # unknown state and the application of a state are one atomic
        # step: a late reply never turns an unknown round into a
        # running one.
        self._state_lock = threading.RLock()
        self._unknown_latched = False
        self._close_lock = threading.Lock()
        self._broker_close_failed = False
        self._cleanup_deadline = None
        # The ONE context of the round.  Every layer of the session
        # holds this very object: the send, the stop of the background
        # threads, the close of the broker and the recovery of the close
        # share one deadline, one cancel and one unknown.
        self._context = _CustodyContext(clock=self._clock, wall=self._wall)
        # -- the coordination of the close ----------------------------------
        # One session keeps ONE cleanup owner and ONE absolute cleanup
        # deadline.  The state of the close is explicit: a competitor
        # never assumes that a close in progress is a close that is
        # finished and it waits inside the same absolute deadline.
        self._close_state = 'NOT_STARTED'
        self._close_done = threading.Event()
        self._close_owner = None
        self._close_waiters = 0
        self._close_waiter_arrived = threading.Event()
        # The event of the **real** end of the closer.  The end of the
        # attempt of the close and the end of the thread that performs
        # it are two different facts.
        self._closer_exited = threading.Event()
        # -- the latch of the background of the round ------------------------
        # The permission to start a background thread is closed before
        # the close takes its snapshot of the threads, so that a thread
        # that starts after the close began is refused and never leaks.
        self._background_lock = threading.Lock()
        self._background_cv = threading.Condition(self._background_lock)
        self._background_open = True
        self._background_starting = 0
        # The state of every background thread of the round.  The state
        # tells whether the start of the thread returned, whether it
        # failed and whether the thread really runs: a thread whose
        # start did not return keeps its owner and it is never taken for
        # a thread that ended.
        self._background_threads = {}
        # The flag of the stop of the round.  A stop blocks every later
        # heartbeat: the heartbeat of a round that is stopping must not
        # write into a channel that is being closed.
        self._stopping = False
        # The latch of the bounded close that a failure of the
        # background threads started.  The close runs in its own thread:
        # a thread never joins itself.
        self._closer_started = False
        self._closer = None

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
        # The context of the round carries the same absolute deadline:
        # every layer of the round reads it there and it is never
        # copied into a deadline of its own.
        self._context.bind_absolute_deadline(self._deadline_mono)
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

        The sequence of a frame is chosen **inside** the write lock and
        the frame is encoded there as well.  The parent, the heartbeat
        and the stop of the round share ONE sequence owner: two frames
        with the same sequence can never be built and no frame is ever
        built outside of the lock.

        A round that is stopping sends no further frame: the stop
        blocks the heartbeat that would follow it.
        """
        with self._write_lock:
            if self._stopping and not terminal:
                return False
            self._reserve_frame(terminal=terminal)
            self._sequence += 1
            raw = encode_command(command, run_id=self.plan.run_id,
                                 candidate_sha=self.plan.candidate_sha,
                                 authorization_sha256=self.plan.authorization_sha256,
                                 nonce=self._nonce, sequence=self._sequence)
            budget = max(0.0, min(self.remaining_seconds(), WRITE_BUDGET_SECONDS))
            # The write of the round never outlives the shared cleanup
            # deadline of the round: a stop that is in flight does not
            # give the write a budget of its own.
            cleanup = self._context.cleanup_deadline_value()
            if cleanup is not None:
                budget = min(budget, max(0.0, cleanup - self._clock()))
            deadline = self._clock() + budget
            self._write_to_broker(raw, deadline)
            return True

    def _reserve_frame(self, *, terminal=False, received=False):
        """One atomic check and commit of the shared frame budget.

        The frames that the parent sends and the frames that it receives
        share **one** counter and one owner.  The check and the commit
        are one atomic step under the lock of the budget: two
        directions that check the budget at the same moment may never
        take the last frame of the budget together.

        The reservation of the terminal exchange is **consumed** by the
        terminal frame itself: a frame of the terminal exchange is
        never refused because of the reservation that was kept for it.
        A frame that is not terminal never borrows the reservation and
        it fails closed when the total does not fit.
        """
        with self._budget_lock:
            reserved = 0 if terminal else RESERVED_TERMINAL_FRAMES
            if self._frames_sent + self._frames_received + reserved + 1 > MAX_FRAMES:
                raise CustodyError('CUSTODY_FRAME_BUDGET_EXCEEDED')
            if received:
                self._frames_received += 1
            else:
                self._frames_sent += 1
            return True

    def _check_frame_budget(self, *, terminal=False):
        """The frame budget of the channel, in both directions.

        The round of six hours with its heartbeat stays inside the
        budget of the channel, and the frames of the terminal exchange
        are reserved.  A round that reached its budget fails closed: it
        never reconnects and it never renews its lease.

        The budget is the **total** of the frames that the parent sent
        and of the frames that it received.  One direction is never a
        substitute for the total: a reply is refused before it is
        accepted when the total does not fit.
        """
        with self._budget_lock:
            reserved = 0 if terminal else RESERVED_TERMINAL_FRAMES
            if self._frames_sent + self._frames_received + reserved + 1 > MAX_FRAMES:
                raise CustodyError('CUSTODY_FRAME_BUDGET_EXCEEDED')
            return True

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
            pump = self._pump
            if pump is None:
                # The reader of the channel is gone.  A cancellation that
                # the reader saw is the failure of the round and it
                # continues to propagate; an ordinary failure of the
                # reader is already named in the failures of the round.
                if isinstance(self._pump_error, (KeyboardInterrupt, SystemExit)):
                    raise self._pump_error
                raise CustodyError('CUSTODY_CHANNEL_CLOSED')
            reply = pump.take(kinds, deadline)
            if reply['kind'] in kinds:
                return reply

    def _decode_reply(self, raw):
        """Decode one reply of the broker and check the identity of it."""
        reply = decode_reply(raw, run_id=self.plan.run_id,
                             candidate_sha=self.plan.candidate_sha,
                             authorization_sha256=self.plan.authorization_sha256,
                             nonce=self._nonce,
                             last_sequence=self._broker_sequence)
        # The budget of the channel is the total of both directions.  A
        # reply that does not fit into the total is refused before it
        # is accepted and before it is counted.  The reply of the
        # terminal exchange consumes the reservation that was kept for
        # it: it is never refused because of its own reservation.
        terminal = reply['kind'] in ('STOPPED', 'REFUSED')
        self._reserve_frame(terminal=terminal, received=True)
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

        The heartbeat is never sent **after** the absolute deadline of
        the round arrived and it is never sent after the round started
        to stop.

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
        if self._stopping:
            # A round that is stopping sends no further heartbeat.
            return False
        if self._deadline_mono is not None and now >= self._deadline_mono:
            # The absolute lease of the round arrived: the heartbeat is
            # not sent any more and it never extends the lease.
            return False
        self._last_heartbeat = now
        try:
            sent = self._send('STATUS')
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._heartbeat_failure = ('CUSTODY_HEARTBEAT_FAILED:'
                                       + type(error).__name__)
            self._latch_background_failure(self._heartbeat_failure)
            return False
        return bool(sent)

    def _start_heartbeat(self):
        """Start the status heartbeat of the round.

        There is exactly one heartbeat thread per round and it is joined
        by the owner of the round.  A failure of the heartbeat is a
        named failure of the round: the round becomes unknown and it is
        never stopped silently in the background.

        The stop event of the heartbeat is created **once**, in the
        constructor of the session, and it is never rebuilt.  A rebuilt
        event would let a heartbeat that starts after the stop of the
        round wait for a stop that will never come.
        """
        if self._heartbeat is not None:
            # There is exactly one heartbeat per round.
            return True
        if self._heartbeat_stop.is_set():
            # The round is already stopping: a heartbeat that starts
            # now would be a heartbeat that nobody stops any more.
            self._failures.append('CUSTODY_HEARTBEAT_NOT_STARTED')
            return False

        def beat():
            while not self._heartbeat_stop.wait(HEARTBEAT_SLICE_SECONDS):
                try:
                    self._heartbeat_step()
                except BaseException as error:  # noqa: BLE001 - the failure stays visible
                    self._heartbeat_failure = ('CUSTODY_HEARTBEAT_FAILED:'
                                               + type(error).__name__)
                    self._latch_background_failure(self._heartbeat_failure)
                    return

        thread = threading.Thread(target=beat, daemon=True,
                                  name='lvw-native-custody-heartbeat')
        return self._start_background_thread('heartbeat', thread)

    def _start_background_thread(self, kind, thread):
        """Start one background thread of the round under the latch.

        The registration of the thread, the permission to start it and
        the count of the threads that are in the middle of their start
        are **one** atomic step under the lock of the background of the
        round.  A thread that is registered may be started and a thread
        that may not be started any more is never registered.

        The close of the round closes the permission **before** it takes
        its snapshot of the threads, so a thread that is started after
        the close began is either refused or stopped by the very close
        that refused it.

        The state of the thread is recorded **while** it is started:

        * ``STARTING``  the start of the thread did not return yet.  The
          thread keeps its owner and it may only clean up: it is never
          taken for a thread that ended.
        * ``RUNNING``   the thread started and it runs.
        * ``FAILED``    the start of the thread raised.  The record says
          whether the thread really runs anyway: a thread that runs
          keeps the reference of the session and the round becomes
          unknown, and a thread that never started is not a thread of
          the round.
        """
        with self._background_lock:
            if not self._background_open:
                self._failures.append('CUSTODY_BACKGROUND_START_REFUSED:' + kind)
                return False
            record = {'kind': kind, 'thread': thread, 'state': 'STARTING',
                      'started': False, 'error': None}
            self._background_threads[kind] = record
            setattr(self, '_' + kind, thread)
            self._background_starting += 1
        try:
            thread.start()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            alive = bool(getattr(thread, 'is_alive', lambda: False)())
            ident = getattr(thread, 'ident', None)
            with self._background_lock:
                record['error'] = error
                record['state'] = 'FAILED'
                record['started'] = bool(alive or ident is not None)
                self._background_starting -= 1
                self._background_cv.notify_all()
            if record['started']:
                # The thread really runs: it keeps the reference of the
                # session and the round becomes unknown.  A thread that
                # runs is never taken for a thread that never started.
                self._failures.append('CUSTODY_BACKGROUND_START_FAILED:' + kind)
                self._latch_unknown_state()
            else:
                # The thread never started: its reference is dropped and
                # its failure stays visible.
                with self._background_lock:
                    if getattr(self, '_' + kind) is thread:
                        setattr(self, '_' + kind, None)
            raise
        with self._background_lock:
            record['state'] = 'RUNNING'
            record['started'] = True
            self._background_starting -= 1
            self._background_cv.notify_all()
        return True

    def _latch_unknown_state(self):
        """Latch the unknown state of the round.  One way.

        The latch and the application of a state share **one** lock: a
        reply that arrives late and the failure of a background thread
        may never both believe that they are the first one.  The first
        one latches the unknown state and every later one is refused.
        """
        with self._state_lock:
            first = not self._unknown_latched
            self._unknown_latched = True
            self._context.latch_unknown()
            self.state = 'UNKNOWN_RETAINED'
        return first

    def _latch_background_failure(self, code):
        """Latch the unknown state of the round after a background failure.

        A failure of the heartbeat or of the pump is not a string that
        is appended to a list and nothing else.  The round becomes
        unknown and a **bounded** close is started.  The close runs in
        its own thread: a thread never joins itself.
        """
        if code not in self._failures:
            self._failures.append(code)
        self._latch_unknown_state()
        self._start_bounded_close()

    def _apply_state(self, state):
        """Apply the state of the round, never overwriting an unknown one.

        A reply that arrives late - after the pump failed and after the
        round latched its unknown state - never turns an unknown round
        into a running one.  The late reply stays visible in the
        evidence of the round.

        The check and the application are **one** atomic step under the
        lock of the state of the round: a reply that passed the check
        and a failure that latches the unknown state may never both
        believe that they are the first one.
        """
        with self._state_lock:
            if self._unknown_latched and state != 'UNKNOWN_RETAINED':
                self._failures.append('CUSTODY_LATE_STATE_IGNORED:' + state)
                return False
            self.state = state
            return True

    def _start_bounded_close(self):
        """Start the bounded close of the round, once, in its own thread.

        The close runs in its own thread because a thread never joins
        itself: the pump and the heartbeat of the round report their
        failure to the round and the round closes in a thread of its
        own.  The callbacks of the pump and of the heartbeat never wait
        for that close, so a closer that joins the pump can never wait
        for the pump in turn.

        A closer that could not be **built** and a closer that could not
        be **started** must not leave the round in ``IN_PROGRESS`` for
        ever: the waiters are woken, the failure is named and the round
        stays unknown.  The original broker of the round keeps its
        owner, so that the public stop of the round may coordinate it
        again.
        """
        with self._close_lock:
            if self._closer_started:
                return False
            self._closer_started = True
        try:
            thread = threading.Thread(target=self._closer_main, daemon=True,
                                      name='lvw-native-custody-closer')
            self._closer = thread
            thread.start()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append('CUSTODY_CLOSER_START_FAILED:'
                                   + type(error).__name__)
            self._latch_unknown_state()
            with self._close_lock:
                # The latch of the closer is not permanent: a later
                # attempt may try again and the public stop of the round
                # is the recovery entry of the resources.
                self._closer_started = False
                unpublished = (self._close_state == 'IN_PROGRESS'
                               and self._close_owner is None)
                if unpublished:
                    self._close_state = 'FINISHED'
            if unpublished:
                self._close_done.set()
            return False
        return True

    def _closer_main(self):
        """The body of the closer of the round.

        The end of the **attempt** of the close and the end of the
        **thread** that performs it are two different facts: the
        evidence of the round carries both of them.
        """
        try:
            self._close_broker()
        finally:
            self._closer_exited.set()

    def _on_pump_error(self, error):
        """The reader of the channel failed: the round latches its state.

        The failure that the reader really saw is kept with the round
        and its own code stays visible: the failure of the reader never
        replaces the failure that the reader really saw.
        """
        self._pump_error = error
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            code = 'CUSTODY_PUMP_CANCELLED:' + type(error).__name__
        else:
            code = 'CUSTODY_PUMP_FAILED:' + type(error).__name__
        original = getattr(error, 'code', None)
        if isinstance(original, str) and original and original not in self._failures:
            self._failures.append(original)
        self._latch_background_failure(code)

    def _stop_background(self, deadline=None):
        """Stop the background threads of the round and join them.

        A thread that does not stop within the shared cleanup deadline
        is a fact of the round: it is named and the round becomes
        unknown.  It is never left behind and it is never discarded, and
        its reference is kept so that the owner of the round can try it
        again.  A thread that really stopped is not kept any more.

        The latch of the background is closed **before** the snapshot of
        the threads is taken.  A thread that is started after this
        point is refused, and a thread that is in the middle of its own
        start is finished before the snapshot is taken: the close of
        the round never leaves behind a thread that it did not know
        about.

        The close never joins the thread that runs it: a thread that
        joins itself is refused by the product and not by the caller.
        """
        if deadline is None:
            deadline = self._cleanup_deadline_for()
        # The stop of the round blocks every later heartbeat, also when
        # the close was started by a failure and not by the caller.
        self._stopping = True
        self._context.request_stop()
        self._heartbeat_stop.set()
        current = threading.current_thread()
        with self._background_cv:
            self._background_open = False
            while self._background_starting > 0:
                remaining = max(0.0, deadline - self._clock())
                if remaining <= 0.0:
                    self._failures.append('CUSTODY_BACKGROUND_START_PENDING')
                    break
                self._background_cv.wait(remaining)
            heartbeat = self._heartbeat
            pump = self._pump
            records = dict(self._background_threads)
        if heartbeat is not None:
            record = records.get('heartbeat')
            if record is not None and record['state'] == 'STARTING':
                # The start of this thread did not return: the thread
                # may still come up.  It keeps its owner, it is never
                # joined and it may only clean up.  A thread whose start
                # did not return is never taken for a thread that ended.
                self._failures.append('CUSTODY_BACKGROUND_START_PENDING:heartbeat')
                self._latch_unknown_state()
            else:
                if heartbeat is not current and heartbeat.ident is not None:
                    heartbeat.join(self._cleanup_remaining(deadline))
                if heartbeat.is_alive():
                    self._failures.append('CUSTODY_HEARTBEAT_NOT_STOPPED')
                    self._latch_unknown_state()
                else:
                    self._heartbeat = None
        if pump is not None:
            pump.stop()
            record = records.get('pump')
            if record is not None and record['state'] == 'STARTING':
                # The start of the reader did not return: the thread may
                # still come up.  It keeps its owner and it is never
                # joined: a thread that was not started is not joinable.
                self._failures.append('CUSTODY_BACKGROUND_START_PENDING:pump')
                self._latch_unknown_state()
            elif pump is current:
                # The close never joins the thread that runs it: a pump
                # that is the current thread stays alive and keeps its
                # reference with its owner.
                self._failures.append('CUSTODY_PUMP_NOT_STOPPED')
                self._latch_unknown_state()
            elif pump.ident is None and not pump.is_alive():
                # The reader never started: it is not a thread of the
                # round and it is never joined.
                self._failures.append('CUSTODY_PUMP_NOT_STARTED')
                self._pump = None
            elif not pump.join_bounded(self._cleanup_remaining(deadline)):
                self._failures.append('CUSTODY_PUMP_NOT_STOPPED')
                self._latch_unknown_state()
            else:
                self._pump = None

    def _cleanup_remaining(self, deadline=None):
        """The seconds that are left until the deadline of the cleanup.

        The name of this helper is **not** ``_remaining``: the session
        owns ``_remaining`` as the remaining budget of the parent child
        and an instance attribute of the same name would shadow this
        method.  A shadowed helper is a ``TypeError`` in every close
        path of the round.
        """
        if deadline is None:
            return THREAD_JOIN_SECONDS
        return max(0.0, deadline - self._clock())

    def _cleanup_deadline_for(self):
        """The ONE absolute deadline of the cleanup of the round.

        The deadline is generated at the first stop or at the first
        failure of the cleanup.  It is the earlier of the absolute
        deadline of the round and the fixed cleanup budget of the round
        and it is the same value in every layer of the cleanup: the
        send, the stop of the background threads, the close of the
        broker, the close of the channel and the close of the endpoints
        all use this very value.

        The generation is **one atomic step** under the lock of the
        context of the round.  Two callers that entered the cleanup at
        the same moment therefore see the very same value: the
        deadline is never generated twice and it is never extended by a
        caller that came later.
        """
        published = self._context.cleanup_deadline_value()
        if published is not None:
            self._cleanup_deadline = published
            return published
        budget = max(0.0, min(STOP_CLEANUP_SECONDS, self.remaining_seconds()))
        value = self._clock() + budget
        if self._deadline_mono is not None:
            value = min(value, self._deadline_mono)
        published = self._context.publish_cleanup_deadline(value)
        self._cleanup_deadline = published
        return published

    # -- the lifecycle ----------------------------------------------------
    def start(self):
        """Start the broker of the round and take the custody of it.

        The parent keeps the *original* handle of the broker.  The identity
        of the broker is therefore read from that handle and never from a
        claim of the broker itself: a child that reports its own pid is a
        claim and not a proof.

        The **whole** lifecycle of the start is protected: the launcher,
        the reading of the identity of the broker, the construction and
        the start of the pump and the start of the heartbeat are all
        inside one guard.  Every failure of this method releases the
        original handle of the broker and the private channel before it
        leaves the method: the caller never has to stop a round that
        never started.

        A refusal of the launcher, a timeout, a parse error and an
        ordinary exception end the same way: the round is closed here
        and it ends in a **structured** terminal state that carries the
        named code of the failure.  The code of the original error is
        kept: a refusal of the broker is never replaced by a generic
        error of the parent.  A cancellation is cleaned up and it
        continues to propagate.
        """
        if self.state == 'NEW':
            self.validate()
        if self.state != 'VALIDATED':
            raise CustodyError('CUSTODY_STATE_INVALID')
        self._fix_deadline()
        launcher = self._launcher or _default_launcher
        try:
            try:
                self.broker = launcher(self.plan, self._run_root, self._nonce)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as error:  # noqa: BLE001 - the failure stays visible
                # The refusal of the launcher is a structured refusal of
                # the round.  The code of the original error is kept and
                # the error is not raised as it is.
                self._latch_unknown_state()
                self._failures.append(self._launch_failure_code(error))
                return self.evidence()
            if self.broker is None:
                self._latch_unknown_state()
                self._failures.append('CUSTODY_BROKER_LAUNCH_UNAVAILABLE')
                return self.evidence()
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
                self._latch_unknown_state()
                self._close_broker()
                raise
            pump = _ChannelPump(self.broker, decode=self._decode_reply,
                                clock=self._clock,
                                on_error=self._on_pump_error)
            # The start of the background of the round is refused when
            # the close of the round began already.  The start does not
            # raise on that refusal: it continues to the exchange of the
            # start, and the failure that leaves this method is the
            # failure of the reader of the channel - a cancellation
            # among them.
            self._start_background_thread('pump', pump)
            self._start_heartbeat()
            ready = self._read_reply(('READY', 'REFUSED'))
            if ready['kind'] == 'REFUSED':
                self._latch_unknown_state()
                self._failures.append(ready['detail'].get('code', 'BROKER_REFUSED'))
                self._close_broker()
                return self.evidence()
            self._apply_state(ready['state'])
            if ready['state'] != 'ARMED':
                raise CustodyError('CUSTODY_STATE_INVALID')
            status = self._read_reply(('STATUS', 'REFUSED'))
            if status['kind'] == 'REFUSED':
                self._latch_unknown_state()
                self._failures.append(status['detail'].get('code', 'BROKER_REFUSED'))
                self._close_broker()
                return self.evidence()
            self._apply_state(status['state'])
        except (KeyboardInterrupt, SystemExit):
            # A cancellation is cleaned up and it continues to propagate.
            self._failures.append('CUSTODY_SESSION_CANCELLED')
            self._latch_unknown_state()
            self._close_broker()
            raise
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            # An ordinary failure of the start is a structured terminal
            # state of the round.  The handle of the broker is released
            # even when the exchange of the start failed: the resource of
            # this round is never left open on purpose and the caller
            # never has to stop it later.
            code = self._failure_code(error)
            if code not in self._failures:
                self._failures.append(code)
            self._latch_unknown_state()
            self._close_broker()
            return self.evidence()
        return self.evidence()

    @staticmethod
    def _launch_failure_code(error):
        """The named code of a refusal of the launcher.

        The code of the original error is kept.  A refusal of the
        broker that names its own code - the unsupported platform of the
        broker for instance - is never replaced by a generic code of the
        parent.
        """
        code = getattr(error, 'code', None)
        if isinstance(code, str) and code:
            return code
        return 'CUSTODY_BROKER_LAUNCH_FAILED:' + type(error).__name__

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

        The stop and the cleanup share **one** absolute deadline: the
        earlier of the absolute deadline of the round and the fixed
        cleanup budget of the round.  That one value is used by the send
        of the stop, by the stop of the background threads, by the close
        of the broker, by the close of the channel and by the close of
        the endpoints of the channel.  No layer of the cleanup adds a
        budget of its own and a round that is stopped does not get a new
        and unauthorised grace period of hours.

        The stop blocks the heartbeat that would follow it.

        A repeated stop does not send a second command and it does not
        close a second time.  It waits for the close that is in flight
        inside the same absolute deadline of the cleanup, so that it
        never returns a success before the cleanup could finish.
        """
        if self._stopped:
            # A repeated stop sends no second command and it closes no
            # second time.  It waits for the close that is in flight and
            # it coordinates the items that a previous attempt did not
            # confirm, inside the **original** deadline of the cleanup.
            self._close_broker()
            self._await_close()
            return self.evidence()
        self._stopped = True
        self._stopping = True
        self._context.request_stop()
        cleanup_deadline = self._cleanup_deadline_for()
        try:
            if self.broker is not None and self.state in ('ARMED', 'RUNNING'):
                self._bind_deadline(cleanup_deadline)
                self._send('STOP', terminal=True)
                reply = self._read_reply(
                    ('STOPPED', 'REFUSED'),
                    timeout=max(0.0, cleanup_deadline - self._clock()))
                self._apply_state(reply['state'])
                self._terminal = reply['detail']
                if reply['kind'] == 'REFUSED':
                    self._failures.append(reply['detail'].get('code', 'BROKER_REFUSED'))
            elif self.broker is None:
                self._failures.append('CUSTODY_BROKER_NOT_STARTED')
                self._latch_unknown_state()
        except CustodyError as error:
            self._failures.append(error.code)
            self._latch_unknown_state()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            # An ordinary failure of the stop is a named failure of the
            # round: the evidence of the round keeps it and the stop
            # does not raise over the evidence.
            self._failures.append(self._failure_code(error))
            self._latch_unknown_state()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            # A cancellation is cleaned up and it continues to propagate.
            self._failures.append(self._failure_code(error))
            self._latch_unknown_state()
            raise
        finally:
            self._close_broker()
        return self.evidence()

    def _close_broker(self):
        """Close the original handle of the broker, exactly once.

        One session keeps ONE cleanup owner and ONE absolute cleanup
        deadline.  The first caller becomes the owner of the close and
        it performs it; every other caller is a competitor and it waits
        for the close that is in flight **inside the same absolute
        deadline** of the cleanup.  A competitor never assumes that a
        close in progress is a close that is finished and it never
        renews the deadline of the cleanup.

        The owner publishes the end of its attempt in a ``finally``: a
        success, an ordinary exception, a cancellation and a
        ``SystemExit`` all wake the waiters.  A waiter never holds the
        lock of the owner while it waits and the owner never waits for
        itself.

        A handle that could not be closed is *kept*: the reference of the
        original handle stays in the evidence of the round and the round
        stays unknown.  A failed close is never swallowed and never
        replaced by a success.
        """
        deadline = self._cleanup_deadline_for()
        with self._close_lock:
            state = self._close_state
            if state == 'NOT_STARTED':
                if self.broker is None:
                    # Nothing was acquired: there is nothing to close
                    # and no owner of the close is claimed.
                    return
                self._close_state = 'IN_PROGRESS'
                self._close_owner = threading.current_thread()
                owner = True
            else:
                owner = False
        if owner:
            try:
                self._perform_close(deadline)
            finally:
                # The end of the attempt is published on every path: a
                # success, an ordinary exception, a cancellation and a
                # SystemExit all wake the waiters.
                self._finish_close()
            return
        if state == 'FINISHED':
            # The attempt that was in flight ended.  An attempt that
            # ended is **not** a release: the items that were not
            # confirmed may be coordinated again by the same owner,
            # inside the **original** deadline of the cleanup.
            self._recover_close(deadline)
            return
        if self._close_owner is threading.current_thread():
            # The owner of the close never waits for itself.
            return
        self._await_close()

    def _recover_close(self, deadline):
        """Coordinate the items that a previous attempt did not confirm.

        The recovery is the **public** entry of the round: it calls the
        product entry of the handle of the broker and it never calls a
        method of a stand-in.  The original deadline of the cleanup is
        never renewed: a recovery that arrives after it keeps the
        resources of the round with their owner and the round stays
        unknown.
        """
        if self.broker is None:
            # Everything that the round owned was released: there is
            # nothing left to coordinate.
            return
        if max(0.0, deadline - self._clock()) <= 0.0:
            self._failures.append('CUSTODY_CLOSE_RECOVERY_EXPIRED')
            self._latch_unknown_state()
            return
        with self._close_lock:
            if self._close_state == 'IN_PROGRESS':
                # Another owner is closing the round right now.
                return
            self._close_state = 'IN_PROGRESS'
            self._close_owner = threading.current_thread()
        try:
            self._perform_close(deadline)
        finally:
            self._finish_close()

    def _perform_close(self, deadline):
        """The close of the original handle of the broker, by its owner.

        The steps of the close are independent of each other: a failure
        of one of them never skips the ones that are safe to run.

        The release of the reference needs the **facts** of the close:
        the channel, the process and its original handle and the reader
        of the channel have to be closed and the reader has to have
        stopped without an error.  A missing fact, a ``None``, a
        ``False``, an unknown value and an exception are all unknown: the
        original broker is kept and the round stays unknown.
        """
        try:
            self._stop_background(deadline)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            # The background threads of the round could not be stopped.
            # The close of the original handle of the broker still runs:
            # the steps of the close are independent of each other.
            self._failures.append('CUSTODY_BACKGROUND_STOP_FAILED:'
                                   + type(error).__name__)
            self._latch_unknown_state()
        try:
            self._bind_deadline(deadline)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append(self._failure_code(error))
        broker = self.broker
        if broker is None:
            return
        try:
            facts = broker.close()
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append('CUSTODY_BROKER_CLOSE_FAILED:'
                                   + type(error).__name__)
            self._broker_close_failed = True
            self._latch_unknown_state()
            self._broker_reader_finished = getattr(broker, 'reader_finished', None)
            return
        self._broker_reader_finished = getattr(broker, 'reader_finished', None)
        self._broker_close_facts = facts if isinstance(facts, dict) else None
        if not isinstance(facts, dict):
            # A close that returned no facts at all is not a proof.
            self._failures.append('CUSTODY_BROKER_CLOSE_INCOMPLETE:facts')
            self._broker_close_failed = True
            self._latch_unknown_state()
            return
        incomplete = []
        for key in REQUIRED_CLOSE_FACTS:
            if key not in facts or facts[key] is not True:
                incomplete.append(key)
        for key in REQUIRED_CLOSE_ZERO_FACTS:
            if key not in facts or facts[key] != 0:
                incomplete.append(key)
        for key in READER_CLOSE_FACTS:
            if key in facts and facts[key] is not True:
                incomplete.append(key)
        if getattr(broker, 'reader_finished', None) is not True:
            # The reader of the channel has to have really stopped.
            # A missing fact and an unknown fact are both unknown.
            incomplete.append('reader_finished')
        if facts.get('channel_reader_error'):
            incomplete.append('channel_reader_error')
        if facts.get('channel_retained_workers'):
            incomplete.append('channel_retained_workers')
        if incomplete:
            for key in incomplete:
                self._failures.append('CUSTODY_BROKER_CLOSE_INCOMPLETE:' + key)
            self._broker_close_failed = True
            self._latch_unknown_state()
            # The original broker is kept: the reference of the
            # resource of the round is never dropped and the round
            # never claims a release that it cannot prove.
            return
        self.broker = None

    def _finish_close(self):
        """Publish the end of the attempt of the close of the round.

        FINISHED means that the attempt ended and it never means that
        the resources of the round are released: only the facts of the
        close prove that.
        """
        with self._close_lock:
            self._close_state = 'FINISHED'
        self._close_done.set()

    def _await_close(self):
        """Wait for the close that is in flight, inside the shared deadline.

        The wait never holds the lock of the owner: the owner may need
        it while it stops the background threads of the round.  The
        arrival of a waiter is published, so that the round and its
        evidence can see that a competitor waits for the close that it
        owns.
        """
        with self._close_lock:
            if self._close_state != 'IN_PROGRESS':
                return True
            if self._close_owner is threading.current_thread():
                # The owner of the close never waits for itself.
                return True
            self._close_waiters += 1
        self._close_waiter_arrived.set()
        try:
            deadline = self._cleanup_deadline_for()
            while True:
                remaining = max(0.0, deadline - self._clock())
                if remaining <= 0.0:
                    # The shared deadline of the cleanup arrived.  The
                    # deadline is never renewed and the original
                    # resources of the round are kept.
                    self._failures.append('CUSTODY_CLOSE_NOT_FINISHED')
                    self._latch_unknown_state()
                    return False
                if self._close_done.wait(min(remaining, CLOSE_WAIT_SLICE_SECONDS)):
                    # The end of the attempt of the close is published.
                    # The end of the **thread** that performed it is a
                    # second fact: the waiter waits for it inside the
                    # same deadline and the evidence names the closer
                    # that is still alive.
                    while True:
                        remaining = max(0.0, deadline - self._clock())
                        if remaining <= 0.0:
                            self._failures.append('CUSTODY_CLOSER_NOT_FINISHED')
                            self._latch_unknown_state()
                            return False
                        if self._closer is None:
                            # The close was performed by the caller
                            # itself: there is no thread of its own.
                            return True
                        if self._closer_exited.wait(min(remaining,
                                                        CLOSE_WAIT_SLICE_SECONDS)):
                            return True
        finally:
            with self._close_lock:
                self._close_waiters -= 1

    def __enter__(self):
        return self

    def __exit__(self, _kind, _value, _traceback):
        try:
            self.stop()
        except Exception:  # noqa: BLE001 - the evidence keeps the failure
            self._latch_unknown_state()
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
            'broker_close_facts': self._broker_close_facts,
            'broker_close_facts_required': list(REQUIRED_CLOSE_FACTS),
            'pump_error': (repr(self._pump.error)
                           if self._pump is not None and self._pump.error is not None
                           else None),
            'heartbeat_alive': bool(self._heartbeat is not None
                                    and self._heartbeat.is_alive()),
            'pump_alive': bool(self._pump is not None and self._pump.alive),
            # The coordination of the close of the round.  ``FINISHED``
            # means that the attempt of the close ended and it never
            # means that the resources of the round are released: only
            # the facts of the close prove that.
            'close_state': self._close_state,
            'close_finished': self._close_done.is_set(),
            'close_waiters': self._close_waiters,
            'closer_alive': bool(self._closer is not None and self._closer.is_alive()),
            'closer_exited': self._closer_exited.is_set(),
            'background_open': self._background_open,
            # The state of every background thread of the round.  The
            # state tells whether the start of the thread returned and
            # whether the thread really runs: a thread whose start did
            # not return is never taken for a thread that ended.
            'background_threads': [{'kind': record['kind'],
                                    'state': record['state'],
                                    'started': record['started'],
                                    'alive': bool(record['thread'].is_alive()),
                                    'error_type': (type(record['error']).__name__
                                                   if record['error'] is not None
                                                   else None)}
                                   for record in self._background_threads.values()],
            'cleanup_deadline': self._cleanup_deadline,
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
