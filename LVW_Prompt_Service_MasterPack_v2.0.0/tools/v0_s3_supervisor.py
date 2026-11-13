"""S3 parent supervision: the bounded protocol, the fixed deadlines and the
parent-held worker handle.

The parent starts the worker from a *sealed* command plan, keeps the original
process handle and the birth identity of that process, and reads a bounded,
identity bound progress protocol from it.  The parent never executes a
callback that the worker sent, never runs a synchronous child observer in
its own loop and never grants a termination right on the basis of a PID that
the worker reported.

The protocol is UTF-8 JSONL with the schema ``lvw.s3-supervision/1``.  A
message has exactly the keys ``schema``, ``run_id``, ``candidate_sha``,
``authorization_sha256``, ``sequence``, ``event`` and ``payload``.  The
sequence is a strictly increasing integer and every identity has to match
the sealed plan of the parent.

The deadlines are fixed: the phase deadline starts when the parent starts
the worker, the history deadline starts at the *first* history wait of that
row, and both are bounded by the remaining child lifetime.  A progress
message can never extend a deadline, swap a sample or create a result.

Everything in this module is an offline, parent side component.  It does not
prove a native Windows service release, a GPU release or an archived run:
those stay with their original owners.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
WORKER_SCRIPT = 'tools/v0_s3_quality_worker.py'
FIXTURE_SCRIPT = 'tools/fixtures/v0_s3_supervisor_fixture.py'

PROTOCOL_SCHEMA = 'lvw.s3-supervision/1'
MESSAGE_KEYS = frozenset({'schema', 'run_id', 'candidate_sha', 'authorization_sha256',
                          'sequence', 'event', 'payload'})
EVENTS = ('STARTED', 'ROW_STARTED', 'HISTORY_WAIT_STARTED', 'ROW_FINISHED', 'PROGRESS',
          'TERMINAL')
ROW_EVENTS = ('ROW_STARTED', 'HISTORY_WAIT_STARTED', 'ROW_FINISHED')

MAX_MESSAGE_BYTES = 32 * 1024
MAX_MESSAGES = 1024
MAX_STREAM_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024

# The stable refusal codes of a child stream that is over its byte budget or
# that cannot be read any more.  The parent revokes its later actions on
# such a stream; it never waits for the phase deadline to expire.
STDOUT_STREAM_LIMIT_EXCEEDED = 'STDOUT_STREAM_LIMIT_EXCEEDED'
STDERR_STREAM_LIMIT_EXCEEDED = 'STDERR_STREAM_LIMIT_EXCEEDED'
STDOUT_STREAM_READ_FAILED = 'STDOUT_STREAM_READ_FAILED'
STDERR_STREAM_READ_FAILED = 'STDERR_STREAM_READ_FAILED'

PHASE_TIMEOUT_SECONDS = 10800
HISTORY_TIMEOUT_SECONDS = 600
CHILD_TIMEOUT_SECONDS = 21600
DEFAULT_GRACE_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 0.05
# The bounded wait for the readers of the worker that was stopped.  The
# readers reach the end of their stream as soon as the worker is gone.
DRAIN_TIMEOUT_SECONDS = 0.5


class SupervisionError(RuntimeError):
    """A refused supervision step with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _strict_pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise SupervisionError('MESSAGE_DUPLICATE_KEY')
        value[key] = item
    return value


def _reject_constant(_value):
    raise SupervisionError('MESSAGE_NONFINITE_NUMBER')


def decode_message(raw):
    """Decode one protocol line with the strict rules of the contract."""
    if not isinstance(raw, (bytes, bytearray)):
        raise SupervisionError('MESSAGE_NOT_BYTES')
    if len(raw) > MAX_MESSAGE_BYTES:
        raise SupervisionError('MESSAGE_TOO_LARGE')
    if not raw.strip():
        raise SupervisionError('MESSAGE_EMPTY')
    try:
        text = bytes(raw).decode('utf-8')
    except UnicodeDecodeError as error:
        raise SupervisionError('MESSAGE_NOT_UTF8') from error
    try:
        value = json.loads(text, object_pairs_hook=_strict_pairs,
                           parse_constant=_reject_constant)
    except SupervisionError:
        raise
    except (ValueError, TypeError) as error:
        raise SupervisionError('MESSAGE_NOT_JSON') from error
    if not isinstance(value, dict):
        raise SupervisionError('MESSAGE_NOT_OBJECT')
    if set(value) != MESSAGE_KEYS:
        raise SupervisionError('MESSAGE_KEY_SET_INVALID')
    if value['schema'] != PROTOCOL_SCHEMA:
        raise SupervisionError('MESSAGE_SCHEMA_INVALID')
    if value['event'] not in EVENTS:
        raise SupervisionError('MESSAGE_EVENT_INVALID')
    if type(value['sequence']) is not int or value['sequence'] < 1:
        raise SupervisionError('MESSAGE_SEQUENCE_INVALID')
    if not isinstance(value['payload'], dict):
        raise SupervisionError('MESSAGE_PAYLOAD_INVALID')
    return value


class SealedPlan:
    """The complete sixteen row plan that the parent seals before it starts.

    The plan is written down before any send is allowed.  A row event that
    does not name a row of this plan is refused; the denominator never
    shrinks.
    """

    def __init__(self, rows):
        if not isinstance(rows, list) or len(rows) != 16:
            raise SupervisionError('PLAN_INCOMPLETE')
        ordinals = set()
        assets = set()
        sealed = []
        for row in rows:
            if not isinstance(row, dict):
                raise SupervisionError('PLAN_ROW_INVALID')
            ordinal = row.get('ordinal')
            asset_id = row.get('asset_id')
            if type(ordinal) is not int or not 1 <= ordinal <= 16 or ordinal in ordinals:
                raise SupervisionError('PLAN_ORDINAL_INVALID')
            if (not isinstance(asset_id, str) or not asset_id
                    or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,31}', asset_id)
                    or asset_id in assets):
                raise SupervisionError('PLAN_ASSET_INVALID')
            if row.get('media_kind') not in ('image', 'video'):
                raise SupervisionError('PLAN_MEDIA_KIND_INVALID')
            ordinals.add(ordinal)
            assets.add(asset_id)
            sealed.append({'ordinal': ordinal, 'asset_id': asset_id,
                           'media_kind': row['media_kind']})
        if len(ordinals) != 16:
            raise SupervisionError('PLAN_INCOMPLETE')
        self.rows = sealed
        self.by_asset = {row['asset_id']: row for row in sealed}
        self.digest = sha256_bytes(canonical_json(sealed).encode('utf-8'))

    def row(self, asset_id):
        row = self.by_asset.get(asset_id)
        if row is None:
            raise SupervisionError('ROW_NOT_IN_PLAN')
        return row


class ProtocolState:
    """The ordered, single source protocol state of one supervised worker."""

    def __init__(self, *, run_id, candidate_sha, authorization_sha256, plan):
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.plan = plan
        self.last_sequence = 0
        self.count = 0
        self.started = False
        self.terminal = None
        self.history_started = {}
        self.row_events = {}
        self.terminal_payload = None

    def accept(self, message):
        """Validate one message against the sealed identities and the plan.

        A refused message does not advance the state: the refusal itself is
        the violation and it revokes every later action.
        """
        if self.count >= MAX_MESSAGES:
            raise SupervisionError('MESSAGE_COUNT_EXCEEDED')
        if message['run_id'] != self.run_id:
            raise SupervisionError('MESSAGE_RUN_ID_MISMATCH')
        if message['candidate_sha'] != self.candidate_sha:
            raise SupervisionError('MESSAGE_CANDIDATE_MISMATCH')
        if message['authorization_sha256'] != self.authorization_sha256:
            raise SupervisionError('MESSAGE_AUTHORIZATION_MISMATCH')
        if message['sequence'] <= self.last_sequence:
            raise SupervisionError('MESSAGE_SEQUENCE_NOT_INCREASING')
        event = message['event']
        payload = message['payload']
        if event == 'STARTED':
            if self.started:
                raise SupervisionError('MESSAGE_STARTED_REPEATED')
        elif event in ROW_EVENTS:
            asset_id = payload.get('asset_id')
            if not isinstance(asset_id, str):
                raise SupervisionError('MESSAGE_ROW_PAYLOAD_INVALID')
            row = self.plan.row(asset_id)
            if payload.get('ordinal') != row['ordinal']:
                raise SupervisionError('MESSAGE_ROW_ORDINAL_MISMATCH')
            if event == 'HISTORY_WAIT_STARTED' and asset_id in self.history_started:
                raise SupervisionError('MESSAGE_HISTORY_STARTED_REPEATED')
        elif event == 'PROGRESS':
            # A progress message carries no result and no deadline.  It may
            # not name a row that is not in the sealed plan.
            asset_id = payload.get('asset_id')
            if asset_id is not None:
                if not isinstance(asset_id, str):
                    raise SupervisionError('MESSAGE_PROGRESS_PAYLOAD_INVALID')
                self.plan.row(asset_id)
        elif event == 'TERMINAL':
            if self.terminal is not None:
                raise SupervisionError('MESSAGE_TERMINAL_REPEATED')
            reference = payload.get('canonical_receipt')
            if not isinstance(reference, dict):
                raise SupervisionError('MESSAGE_TERMINAL_REFERENCE_INVALID')
            if set(reference) != {'reference', 'bytes', 'sha256'}:
                raise SupervisionError('MESSAGE_TERMINAL_REFERENCE_INVALID')
            if not isinstance(reference['reference'], str) or not reference['reference']:
                raise SupervisionError('MESSAGE_TERMINAL_REFERENCE_INVALID')
            if type(reference['bytes']) is not int or reference['bytes'] <= 0:
                raise SupervisionError('MESSAGE_TERMINAL_REFERENCE_INVALID')
            if not re.fullmatch('[0-9a-f]{64}', str(reference['sha256'])):
                raise SupervisionError('MESSAGE_TERMINAL_REFERENCE_INVALID')
            if payload.get('decision') is not None and not isinstance(payload['decision'], str):
                raise SupervisionError('MESSAGE_TERMINAL_DECISION_INVALID')
        else:
            raise SupervisionError('MESSAGE_EVENT_INVALID')
        # The message is accepted: the state advances exactly once.
        self.last_sequence = message['sequence']
        self.count += 1
        if event == 'STARTED':
            self.started = True
        elif event in ROW_EVENTS:
            asset_id = payload['asset_id']
            if event == 'HISTORY_WAIT_STARTED':
                self.history_started[asset_id] = True
            self.row_events.setdefault(asset_id, []).append(event)
        elif event == 'TERMINAL':
            self.terminal = message
            self.terminal_payload = payload
        return message


class _StreamReader(threading.Thread):
    """A bounded background reader of one child stream.

    The thread only reads bytes.  It never calls the worker, never runs an
    observer and never writes.  The parent loop never blocks on the pipe: it
    drains the collected chunks.

    The reader keeps three separate accounts, because they mean different
    things: ``total`` is every byte that the stream delivered, ``received``
    holds those bytes for the evidence and ``chunks`` holds the bytes that
    the parent has not consumed yet.  A consumed buffer is never reported
    as an empty stream.
    """

    def __init__(self, stream, limit):
        super().__init__(daemon=True)
        self.stream = stream
        self.limit = limit
        self.chunks = []
        self.received = []
        self.total = 0
        self.overflow = False
        self.error = None
        self.finished = threading.Event()

    def run(self):
        try:
            descriptor = self.stream.fileno()
            while True:
                block = os.read(descriptor, 65536)
                if not block:
                    break
                before = self.total
                self.total += len(block)
                if self.total > self.limit:
                    # The bytes that are still inside the budget are kept,
                    # the rest of the block is dropped: the retained bytes
                    # never exceed the frozen budget of the stream.
                    allowed = self.limit - before
                    if allowed > 0:
                        self._retain(block[:allowed])
                    self.overflow = True
                    break
                self._retain(block)
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            self.error = type(error).__name__
        finally:
            self.finished.set()

    def _retain(self, block):
        self.chunks.append(block)
        self.received.append(block)

    def take(self):
        chunks = self.chunks
        self.chunks = []
        return b''.join(chunks)

    def raw(self):
        """Every byte that this reader received, consumed or not."""
        return b''.join(self.received)

    def retained(self):
        """The bytes that the parent has not consumed yet."""
        return sum(len(chunk) for chunk in self.chunks)

    def text(self):
        return b''.join(self.chunks).decode('utf-8', 'replace')


class ParentSupervisor:
    """The parent that holds the worker handle and the fixed deadlines.

    The parent starts the worker from a sealed command, keeps the original
    process handle and the birth identity of that process, and reads the
    bounded protocol from it.  When the worker misbehaves, times out or
    loses contact, the parent revokes the later actions, asks for a
    cooperative cancel, terminates *only* the worker handle that it holds
    and records what it could and could not prove.

    The native service cleanup, the GPU release and the archive stay with
    their original owners.  An unknown outcome keeps the original root and
    the reservation: it never archives, never continues to the next phase,
    never refunds and never resends.
    """

    def __init__(self, *, command, run_id, candidate_sha, authorization_sha256, plan,
                 root, phase_timeout=PHASE_TIMEOUT_SECONDS,
                 history_timeout=HISTORY_TIMEOUT_SECONDS, child_timeout=CHILD_TIMEOUT_SECONDS,
                 grace_seconds=DEFAULT_GRACE_SECONDS, clock=None, spawner=None,
                 original_sealer=None):
        if not isinstance(command, list) or not command:
            raise SupervisionError('COMMAND_PLAN_INVALID')
        if not isinstance(plan, SealedPlan):
            raise SupervisionError('PLAN_REQUIRED')
        self.command = list(command)
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.plan = plan
        self.root = Path(root)
        self.phase_timeout = phase_timeout
        self.history_timeout = history_timeout
        self.child_timeout = child_timeout
        self.grace_seconds = grace_seconds
        self.clock = clock or time.monotonic
        self.spawner = spawner or self._spawn
        self.original_sealer = original_sealer
        self.state = ProtocolState(run_id=run_id, candidate_sha=candidate_sha,
                                    authorization_sha256=authorization_sha256, plan=plan)
        self.process = None
        self.birth = None
        self.started_at = None
        self.phase_deadline = None
        self.child_deadline = None
        self.effective_phase_deadline = None
        self.history_deadlines = {}
        self.stdout_reader = None
        self.stderr_reader = None
        self.stdout_buffer = bytearray()
        self.messages = []
        self.violation = None
        self.deadline_exceeded = False
        self.exit_code = None
        self.cleanup = {'requested': False, 'proven_stopped': False, 'exit_code': None}
        self.terminal_receipt = None
        self.receipt_verified = False
        self.row_status = {}
        self.cooperative_cancel = False
        self.notes = []
        self.poll_interval = POLL_INTERVAL_SECONDS

    # -- the frozen command plans -----------------------------------------
    def _spawn(self, command):
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=0)

    def start(self):
        """Start the sealed command and take the original handle."""
        if self.process is not None:
            raise SupervisionError('SUPERVISOR_ALREADY_STARTED')
        self.process = self.spawner(self.command)
        self.started_at = self.clock()
        self.phase_deadline = self.started_at + self.phase_timeout
        self.child_deadline = self.started_at + self.child_timeout
        self.effective_phase_deadline = min(self.phase_deadline, self.child_deadline)
        self.birth = self._birth_identity(self.process)
        stdout = getattr(self.process, 'stdout', None)
        stderr = getattr(self.process, 'stderr', None)
        if stdout is not None:
            self.stdout_reader = _StreamReader(stdout, MAX_STREAM_BYTES)
            self.stdout_reader.start()
        if stderr is not None:
            self.stderr_reader = _StreamReader(stderr, MAX_STREAM_BYTES)
            self.stderr_reader.start()
        return {'pid': getattr(self.process, 'pid', None), 'birth': self.birth,
                'started_at': self.started_at}

    @staticmethod
    def _birth_identity(process):
        """The birth identity of the process handle that the parent holds.

        The identity is read from the handle that this parent created.  It is
        never taken from a value that the worker reported.
        """
        pid = getattr(process, 'pid', None)
        if type(pid) is not int or pid <= 0:
            return None
        try:
            fields = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
            return {'linux_start_ticks': int(fields[19])}
        except (OSError, IndexError, ValueError):
            return None

    # -- the protocol pump -------------------------------------------------
    def _stream_failure(self):
        """The stable refusal code of a stream that failed or overflowed.

        A child stream that is over its frozen byte budget or that cannot be
        read any more is a resource failure of the supervision itself.  The
        parent notices it in the same poll interval as the protocol and
        never waits for the phase deadline to expire.
        """
        if self.stdout_reader is not None:
            if self.stdout_reader.overflow:
                return STDOUT_STREAM_LIMIT_EXCEEDED
            if self.stdout_reader.error is not None:
                return STDOUT_STREAM_READ_FAILED
        if self.stderr_reader is not None:
            if self.stderr_reader.overflow:
                return STDERR_STREAM_LIMIT_EXCEEDED
            if self.stderr_reader.error is not None:
                return STDERR_STREAM_READ_FAILED
        return None

    def _consume_stdout(self):
        if self.stdout_reader is None:
            return
        block = self.stdout_reader.take()
        if not block:
            return
        self.stdout_buffer.extend(block)
        while True:
            index = self.stdout_buffer.find(b'\n')
            if index < 0:
                break
            line = bytes(self.stdout_buffer[:index])
            del self.stdout_buffer[:index + 1]
            if len(line) > MAX_MESSAGE_BYTES:
                raise SupervisionError('MESSAGE_TOO_LARGE')
            message = decode_message(line)
            self.state.accept(message)
            self.messages.append(message)
            if message['event'] == 'HISTORY_WAIT_STARTED':
                self._fix_history_deadline(message['payload']['asset_id'])
            if message['event'] == 'TERMINAL':
                self.terminal_receipt = message['payload']['canonical_receipt']

    def _fix_history_deadline(self, asset_id):
        """Fix the history deadline of one row at its first history wait.

        The deadline is never moved again.  A repeated history start for the
        same row is a protocol violation and is refused by the state.
        """
        if asset_id in self.history_deadlines:
            return
        started = self.clock()
        self.history_deadlines[asset_id] = min(started + self.history_timeout,
                                               self.effective_phase_deadline,
                                               self.child_deadline)

    def _deadline_state(self):
        now = self.clock()
        if now > self.effective_phase_deadline:
            return 'PHASE_DEADLINE_EXCEEDED'
        for asset_id, deadline in self.history_deadlines.items():
            if now > deadline:
                return 'HISTORY_DEADLINE_EXCEEDED:' + asset_id
        return None

    def run(self):
        """Drive the worker to a terminal state or to a refusal."""
        if self.process is None:
            self.start()
        while True:
            # The protocol is consumed first: a frame that was already
            # received is never lost.  A stream failure is checked right
            # after the consumption, so a resource failure revokes the later
            # actions even when a terminal event of the same batch was read.
            try:
                self._consume_stdout()
            except SupervisionError as error:
                self.violation = error.code
                break
            failure = self._stream_failure()
            if failure is not None:
                self.violation = failure
                break
            if self.state.terminal is not None:
                break
            expired = self._deadline_state()
            if expired is not None:
                self.deadline_exceeded = True
                self.violation = expired
                break
            status = self.process.poll()
            if status is not None:
                # The worker left.  Wait for the bounded readers to reach the
                # end of their stream and drain them, so a terminal event
                # that is already in the pipe is not lost.
                for reader in (self.stdout_reader, self.stderr_reader):
                    if reader is not None:
                        reader.finished.wait(timeout=2.0)
                try:
                    self._consume_stdout()
                except SupervisionError as error:
                    self.violation = error.code
                    break
                failure = self._stream_failure()
                if failure is not None:
                    self.violation = failure
                    break
                if self.state.terminal is None:
                    self.violation = 'WORKER_EXITED_WITHOUT_TERMINAL'
                    break
                break
            time.sleep(self.poll_interval)
        self.cleanup = self._terminate_owned_worker()
        self.exit_code = self.process.poll()
        self._drain_streams()
        self._verify_terminal_receipt()
        self._derive_row_status()
        return self.evidence()

    # -- the final drain of the streams -------------------------------------
    def _drain_streams(self):
        """Drain the streams of the worker that was stopped.

        The bytes that were received are never lost: the frames that arrive
        after the last poll are still decoded.  A stream failure that
        arrives with the last bytes of a stream is never hidden by a
        terminal event of the same batch: the outcome is unknown and the
        root and the reservation are retained.
        """
        for reader in (self.stdout_reader, self.stderr_reader):
            if reader is not None:
                reader.finished.wait(timeout=DRAIN_TIMEOUT_SECONDS)
        try:
            self._consume_stdout()
        except SupervisionError as error:
            if self.violation is None:
                self.violation = error.code
        failure = self._stream_failure()
        if failure is not None and self.violation is None:
            self.violation = failure

    # -- the cooperative cancel and the owned termination ------------------
    def _request_cooperative_cancel(self):
        """Close the standard input of the worker as the cooperative cancel.

        The worker sees the end of its input and stops on its own.  This is
        a request, not a proof: the parent still terminates the handle it
        holds afterwards.
        """
        stream = getattr(self.process, 'stdin', None)
        if stream is None:
            return False
        try:
            stream.close()
        except Exception:  # noqa: BLE001 - the request may fail
            return False
        self.cooperative_cancel = True
        return True

    def _terminate_owned_worker(self):
        """Terminate only the worker handle that this parent started.

        No other process is touched.  A PID that the worker reported is
        never used, and no process is selected by a name that was read from
        a file.
        """
        outcome = {'requested': False, 'cooperative_cancel': False,
                   'terminated': False, 'killed': False, 'proven_stopped': False,
                   'exit_code': None, 'pid': getattr(self.process, 'pid', None),
                   'birth': self.birth, 'native_cleanup_proven': False,
                   'native_cleanup_owner': 'original_driver'}
        if self.process is None:
            return outcome
        if self.violation is not None:
            outcome['cooperative_cancel'] = self._request_cooperative_cancel()
        if self.process.poll() is None:
            outcome['requested'] = True
            try:
                self.process.terminate()
                outcome['terminated'] = True
            except Exception:  # noqa: BLE001 - the failure stays visible
                outcome['terminate_failed'] = True
            try:
                self.process.wait(timeout=self.grace_seconds)
            except Exception:  # noqa: BLE001 - a timeout or an error
                try:
                    self.process.kill()
                    outcome['killed'] = True
                except Exception:  # noqa: BLE001 - the failure stays visible
                    outcome['kill_failed'] = True
                try:
                    self.process.wait(timeout=self.grace_seconds)
                except Exception:  # noqa: BLE001 - the failure stays visible
                    outcome['kill_failed'] = True
        outcome['exit_code'] = self.process.poll()
        outcome['proven_stopped'] = outcome['exit_code'] is not None
        return outcome

    # -- the terminal receipt ---------------------------------------------
    def _resolve_reference(self, reference):
        pure = Path(reference)
        if pure.is_absolute() or '..' in pure.parts:
            raise SupervisionError('TERMINAL_REFERENCE_ESCAPES_ROOT')
        return self.root / pure

    def _verify_terminal_receipt(self):
        """Read the actual canonical receipt bytes of the bound root.

        The in-memory claim of the worker is never the result.  The parent
        reads the bytes itself and compares the real length and hash with
        the sealed reference.
        """
        if self.terminal_receipt is None:
            return None
        reference = self.terminal_receipt
        try:
            path = self._resolve_reference(reference['reference'])
            raw = path.read_bytes()
        except (OSError, SupervisionError, ValueError):
            self.receipt_verified = False
            return None
        if len(raw) != reference['bytes'] or sha256_bytes(raw) != reference['sha256']:
            self.receipt_verified = False
            return None
        self.receipt_verified = True
        try:
            document = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            self.receipt_verified = False
            return None
        if not isinstance(document, dict):
            self.receipt_verified = False
            return None
        return document

    def _derive_row_status(self):
        """Derive the sixteen row states from the verified canonical receipt.

        A row that the worker never started is ``BLOCKED``.  A row that was
        started but is not proven by the verified receipt is ``FAIL`` with
        an unknown cause.  The denominator never shrinks.
        """
        document = None
        if self.terminal_receipt is not None:
            try:
                path = self._resolve_reference(self.terminal_receipt['reference'])
                raw = path.read_bytes()
                if (len(raw) == self.terminal_receipt['bytes']
                        and sha256_bytes(raw) == self.terminal_receipt['sha256']):
                    document = json.loads(raw.decode('utf-8'))
            except (OSError, ValueError, UnicodeDecodeError, SupervisionError):
                document = None
        started = set(self.state.row_events)
        proved = {}
        if isinstance(document, dict) and isinstance(document.get('rows'), list):
            for row in document['rows']:
                if isinstance(row, dict) and isinstance(row.get('asset_id'), str):
                    proved[row['asset_id']] = row.get('execution_status')
        for row in self.plan.rows:
            asset_id = row['asset_id']
            if asset_id in proved and proved[asset_id] in ('PASS', 'FAIL', 'BLOCKED'):
                self.row_status[asset_id] = proved[asset_id]
            elif asset_id in started:
                self.row_status[asset_id] = 'FAIL'
            else:
                self.row_status[asset_id] = 'BLOCKED'
        return self.row_status

    # -- the evidence ------------------------------------------------------
    def evidence(self):
        """The parent's own evidence of this supervision."""
        stdout_raw = b''
        stderr_raw = b''
        stdout_bytes = 0
        stderr_bytes = 0
        stdout_retained = len(self.stdout_buffer)
        stderr_retained = 0
        if self.stdout_reader is not None:
            stdout_raw = self.stdout_reader.raw()
            stdout_bytes = self.stdout_reader.total
            stdout_retained += self.stdout_reader.retained()
        if self.stderr_reader is not None:
            stderr_raw = self.stderr_reader.raw()
            stderr_bytes = self.stderr_reader.total
            stderr_retained = self.stderr_reader.retained()
        # A refusal is never a success: a terminal event that was read in the
        # same batch does not turn a protocol violation or a stream failure
        # into a proven outcome.
        unknown = self.violation is not None
        retained = unknown or not self.receipt_verified
        return {
            'kind': 'lvw.s3-supervision-evidence/1',
            'run_id': self.run_id,
            'candidate_sha': self.candidate_sha,
            'authorization_sha256': self.authorization_sha256,
            'plan_sha256': self.plan.digest,
            'row_count': len(self.plan.rows),
            'command': list(self.command),
            'pid': getattr(self.process, 'pid', None),
            'birth': self.birth,
            'exit_code': self.exit_code,
            'message_count': self.state.count,
            'message_limit': MAX_MESSAGES,
            'stream_byte_limit': MAX_STREAM_BYTES,
            'stdout_bytes': stdout_bytes,
            'stderr_bytes': stderr_bytes,
            'stdout_bytes_retained': stdout_retained,
            'stderr_bytes_retained': stderr_retained,
            'stdout_sha256': sha256_bytes(stdout_raw),
            'stderr_sha256': sha256_bytes(stderr_raw),
            'stdout_overflow': bool(self.stdout_reader and self.stdout_reader.overflow),
            'stderr_overflow': bool(self.stderr_reader and self.stderr_reader.overflow),
            'stdout_read_error': (self.stdout_reader.error if self.stdout_reader
                                  is not None else None),
            'stderr_read_error': (self.stderr_reader.error if self.stderr_reader
                                  is not None else None),
            'stream_violation': self._stream_failure(),
            'phase_timeout_seconds': self.phase_timeout,
            'history_timeout_seconds': self.history_timeout,
            'child_timeout_seconds': self.child_timeout,
            'phase_deadline_reached': self.deadline_exceeded,
            'protocol_violation': self.violation,
            'terminal_received': self.state.terminal is not None,
            'canonical_receipt': self.terminal_receipt,
            'canonical_receipt_verified': self.receipt_verified,
            'row_status': dict(self.row_status),
            'cleanup': self.cleanup,
            'cooperative_cancel_requested': self.cooperative_cancel,
            'unknown_outcome': bool(unknown),
            'root_retained': bool(retained),
            'reservation_retained': bool(retained),
            'archive_allowed': not retained,
            'refund_allowed': False,
            'resend_allowed': False,
            'next_phase_allowed': not retained,
            'native_service_cleanup_proven': False,
            'native_gpu_release_proven': False,
            'parent_crash_recovery_proven': False,
            'stage_pass_claim': False,
            'product_gate0': False,
            'real_execution_performed': False,
            'notes': list(self.notes),
        }


FIXTURE_SCENARIOS = (
    'clean_terminal',
    'blocking_callback',
    'blocking_persistence',
    'history_replay',
    'sequence_reversal',
    'duplicate_sequence',
    'oversize_message',
    'foreign_identity',
    'unexpected_field',
    'nonfinite_number',
    'early_exit',
    'message_flood',
    'bad_terminal_reference',
)


def build_production_command(context_path, *, python=None):
    """The frozen production command of the quality worker.

    The production entry starts exactly the fixed quality worker with one
    context document.  A fixture script, a dynamic import or an arbitrary
    argument vector is never a production command.
    """
    script = PACK_ROOT / WORKER_SCRIPT
    if not script.is_file():
        raise SupervisionError('WORKER_SCRIPT_MISSING')
    executable = python or 'python3'
    context = Path(context_path)
    if not context.is_absolute():
        context = PACK_ROOT / context
    return [executable, '-I', '-B', str(script), '--context', str(context)]


def build_fixture_command(scenario, *, python=None, arguments=()):
    """The command of one enumerated fixture scenario.

    This command is only ever used by the bounded offline fixture scenarios.
    It is not a production command and it is not a general execution
    platform: the scenario is one member of a closed enumeration.
    """
    if scenario not in FIXTURE_SCENARIOS:
        raise SupervisionError('FIXTURE_SCENARIO_UNKNOWN')
    script = PACK_ROOT / FIXTURE_SCRIPT
    if not script.is_file():
        raise SupervisionError('FIXTURE_SCRIPT_MISSING')
    executable = python or 'python3'
    command = [executable, '-I', '-S', '-B', str(script), '--scenario', scenario]
    command.extend(str(item) for item in arguments)
    return command


class RecoveryEntry:
    """The recovery entry of a lost or crashed parent.

    The recovery coordinates the cleanup and the existing evidence only.  It
    never replays the inference, it never resends a model action and it
    never terminates a process on the basis of a PID that was read from a
    file.  Without the original custody evidence of the parent it stays
    ``BLOCKED``.
    """

    def __init__(self, *, custody=None):
        self.custody = custody

    def recover(self):
        if not isinstance(self.custody, dict):
            return {'status': 'BLOCKED', 'reason': 'CUSTODY_EVIDENCE_UNAVAILABLE',
                    'replay_allowed': False, 'resend_allowed': False,
                    'stage_pass_claim': False}
        required = ('run_id', 'candidate_sha', 'authorization_sha256', 'pid', 'birth')
        if any(key not in self.custody for key in required):
            return {'status': 'BLOCKED', 'reason': 'CUSTODY_EVIDENCE_INCOMPLETE',
                    'replay_allowed': False, 'resend_allowed': False,
                    'stage_pass_claim': False}
        return {
            'status': 'RECOVERED_FOR_CLEANUP_ONLY',
            'run_id': self.custody['run_id'],
            'candidate_sha': self.custody['candidate_sha'],
            'authorization_sha256': self.custody['authorization_sha256'],
            'pid': self.custody['pid'],
            'birth': self.custody['birth'],
            'replay_allowed': False,
            'resend_allowed': False,
            'refund_allowed': False,
            'archive_allowed': False,
            'cleanup_owner': 'original_driver',
            'native_cleanup_proven': False,
            'stage_pass_claim': False,
            'product_gate0': False,
        }
