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
"""
import json
import math
import os
import re
import time
from pathlib import Path

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


def _validate_role_data(name, data):
    if name == 'COMFY':
        if not isinstance(data['user_directory'], str) \
                or not _DIRECTORY_NAME.match(data['user_directory']):
            raise CustodyError('CUSTODY_PLAN_ROLE_DATA_INVALID')
        return
    if name == 'SAMPLER':
        _require_absolute_windows_path(data['nvidia_exe'],
                                       'CUSTODY_PLAN_ROLE_DATA_INVALID')
        _require_text(data['nvidia_sha256'], r'[0-9a-f]{64}',
                      'CUSTODY_PLAN_ROLE_DATA_INVALID')
        _require_exact_int(data['max_seconds'], 'CUSTODY_PLAN_ROLE_DATA_INVALID',
                           minimum=1, maximum=MAX_SAMPLER_SECONDS)


class LaunchPlan:
    """The validated and sealed launch plan of one native custody round."""

    __slots__ = ('run_id', 'candidate_sha', 'authorization_sha256',
                 'lease_expires_at', 'max_runtime_seconds', 'roles', 'sealed')

    def __init__(self, run_id, candidate_sha, authorization_sha256,
                 lease_expires_at, max_runtime_seconds, roles):
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.lease_expires_at = lease_expires_at
        self.max_runtime_seconds = max_runtime_seconds
        self.roles = tuple(roles)
        self.sealed = {
            'schema': PLAN_SCHEMA,
            'run_id': run_id,
            'candidate_sha': candidate_sha,
            'authorization_sha256': authorization_sha256,
            'lease_expires_at': lease_expires_at,
            'max_runtime_seconds': max_runtime_seconds,
            'roles': [dict(role) for role in self.roles],
        }


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
    """

    def __init__(self, *, plan, run_root, parent_child_remaining_seconds,
                 launcher=None, clock=None, wall=None, nonce=None):
        self._document = plan
        self._run_root = Path(run_root)
        self._remaining = parent_child_remaining_seconds
        self._launcher = launcher
        self._clock = clock or time.monotonic
        self._wall = wall or time.time
        self._nonce = nonce or ('custody-' + os.urandom(16).hex())
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

    # -- the deadline ----------------------------------------------------
    def _fix_deadline(self):
        """Fix the absolute deadline of the round, once.

        The deadline is the earlier of the absolute lease of the plan, the
        runtime of the plan and the remaining budget of the parent.  It is
        fixed here and it is never moved again: a status request, a
        heartbeat or a stop command may not extend it.
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
    def _send(self, command):
        raw = encode_command(command, run_id=self.plan.run_id,
                             candidate_sha=self.plan.candidate_sha,
                             authorization_sha256=self.plan.authorization_sha256,
                             nonce=self._nonce, sequence=self._sequence + 1)
        self._sequence += 1
        self._frames_sent += 1
        if self._frames_sent > MAX_FRAMES:
            raise CustodyError('CUSTODY_FRAME_COUNT_EXCEEDED')
        self.broker.write(raw)

    def _read_reply(self, kinds, *, timeout=None):
        """Read the replies of the broker until one of them is wanted.

        The read never blocks the deadline of the round: the transport of
        the channel is bounded and the wait is clipped to the remaining
        deadline of the round.
        """
        limit = self.remaining_seconds() if timeout is None else timeout
        deadline = self._clock() + max(0.0, limit)
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise CustodyError('CUSTODY_CHANNEL_TIMEOUT')
            raw = self.broker.read(min(remaining, 0.5))
            if raw is None:
                continue
            if raw == b'':
                raise CustodyError('CUSTODY_CHANNEL_EOF')
            self._frames_received += 1
            if self._frames_received > MAX_FRAMES:
                raise CustodyError('CUSTODY_FRAME_COUNT_EXCEEDED')
            reply = decode_reply(raw, run_id=self.plan.run_id,
                                 candidate_sha=self.plan.candidate_sha,
                                 authorization_sha256=self.plan.authorization_sha256,
                                 nonce=self._nonce,
                                 last_sequence=self._broker_sequence)
            self._broker_sequence = reply['sequence']
            if reply['kind'] in kinds:
                return reply

    # -- the lifecycle ----------------------------------------------------
    def start(self):
        """Start the broker of the round and take the custody of it.

        The parent keeps the *original* handle of the broker.  The identity
        of the broker is therefore read from that handle and never from a
        claim of the broker itself: a child that reports its own pid is a
        claim and not a proof.
        """
        if self.state == 'NEW':
            self.validate()
        if self.state != 'VALIDATED':
            raise CustodyError('CUSTODY_STATE_INVALID')
        self._fix_deadline()
        launcher = self._launcher or _default_launcher
        try:
            self.broker = launcher(self.plan, self._run_root, self._nonce)
        except CustodyError:
            self.state = 'UNKNOWN_RETAINED'
            raise
        if self.broker is None:
            self.state = 'UNKNOWN_RETAINED'
            raise CustodyError('CUSTODY_BROKER_LAUNCH_UNAVAILABLE')
        self._broker_identity = {
            'pid': getattr(self.broker, 'pid', None),
            'executable': getattr(self.broker, 'executable', None),
            'executable_sha256': getattr(self.broker, 'executable_sha256', None),
            'identity_source': 'PARENT_ORIGINAL_HANDLE',
            'reported_by_the_broker': False,
        }
        try:
            ready = self._read_reply(('READY', 'REFUSED'))
            if ready['kind'] == 'REFUSED':
                self.state = 'UNKNOWN_RETAINED'
                self._failures.append(ready['detail'].get('code', 'BROKER_REFUSED'))
                return self.evidence()
            self.state = ready['state']
            if ready['state'] != 'ARMED':
                raise CustodyError('CUSTODY_STATE_INVALID')
            status = self._read_reply(('STATUS', 'REFUSED'))
            if status['kind'] == 'REFUSED':
                self.state = 'UNKNOWN_RETAINED'
                self._failures.append(status['detail'].get('code', 'BROKER_REFUSED'))
                return self.evidence()
            self.state = status['state']
        except CustodyError as error:
            self._failures.append(error.code)
            self.state = 'UNKNOWN_RETAINED'
            # The handle of the broker is released even when the exchange
            # of the start failed: the resource of this round is never left
            # open on purpose.
            self._close_broker()
            raise
        return self.evidence()

    def stop(self):
        """Stop the round and close the original handle of the broker.

        The stop is idempotent: a repeated stop does not send a second
        command, does not create anything and does not change the evidence
        of the round.  The closure of the broker happens in a ``finally``,
        so it also happens when the exchange of the stop failed.
        """
        if self._stopped:
            return self.evidence()
        self._stopped = True
        try:
            if self.broker is not None and self.state in ('ARMED', 'RUNNING'):
                self._send('STOP')
                reply = self._read_reply(('STOPPED', 'REFUSED'))
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
        finally:
            self._close_broker()
        return self.evidence()

    def _close_broker(self):
        """Close the original handle of the broker, exactly once."""
        if self.broker is None:
            return
        broker = self.broker
        try:
            broker.close()
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self._failures.append('CUSTODY_BROKER_CLOSE_FAILED:' + type(error).__name__)
        finally:
            # Whether the reader of the private channel really stopped is a
            # fact of this round and it is kept visible: a daemon thread
            # that is still alive is not a finished thread.
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
            'broker': self._broker_identity,
            'broker_channel_reader_finished': self._broker_reader_finished,
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
