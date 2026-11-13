"""The independent finite CPU executor of the S3 integration batch.

This executor is the custody of the finite fixture process plan.  It is
*not* the supervisor that is under test: it is the outer, independent guard
of the process budget, of the source identity and of the wall clock.

Five properties are enforced here and nowhere else:

G1  The shared budget is a **root created external counter**.  The executor
    never creates it, never resets it and never treats a missing counter as
    zero.  Every actual start is charged **atomically before** the operating
    system action, under an exclusive file lock.  A charge is never removed:
    a failed or an unknown start keeps its reservation.

G2  Before every spawn the executor verifies the exact root binding path and
    digest, the actual candidate, every source/runner/supervisor/fixture
    pin and the bound Python.  Any drift refuses the start *before* the
    operating system action.  A document of the same kind that the root did
    not seal is not issuer proof.

G3  The executor holds the original child handles and enforces the
    concurrency bound, an independent per child deadline and the cumulative
    session wall.  The wall is **shared across invocations**: a session
    reserves its slice of the shared pool atomically and the admission and
    the cleanup deadlines are derived from the shared remaining pool with
    the last reserve cleanup only.  The reaper has its own deadline and
    records the raw exit proof of every child.  An uncertain exit keeps the
    reservation and keeps the slot occupied.

G4  The argv, the scenario, the working directory and the bounded context
    document are exactly the sealed plan.  The context document lives in the
    fresh runner owned root; no arbitrary private path is accepted.

G5  The custody of a child is taken **immediately** after the operating
    system action and survives a failure of the registration or of the
    watchdog setup.  The bounded termination starts early enough that the
    whole per child budget, cleanup included, stays inside the seal.  The
    completion proof carries the birth that was read from the held handle.

The executor never downloads, never opens a socket, never starts a service
and never touches the original product ledger.

Two rules of the accounting are absolute.  A concurrency slot is released
only by a refusal that the guard itself proved inside the audit event of
*this* start: the guard mints a one time credential that is bound to this
executor, to this charge, to this thread and to this action, and only that
credential is consumed.  A copied marker, a copied gate error and a
replayed old refusal keep the charge open.  And a settlement that the
counter did not accept is never a terminal state: the charge stays pending,
the session stays uncertain, the finalizer keeps the root and its exit code
is not zero.

A third rule completes them.  A slot is also released when the **original
handle** of a child proves that the child exited and when the shared counter
**persists** the terminal state of that charge.  A sequential run admits its
next start long before the final reap, so a child that has already exited
would otherwise keep its slot and refuse the next start although it is gone.
The reconciliation that does this runs **before** an admission, it looks
only at the children that this executor owns, it never revokes the
admissions, never stops the watchdog, never takes a new custody and never
refunds anything.  A live child, an unproven child and a settlement that
the counter did not accept keep their slot.

A fourth rule closes it.  The reconciliation is a bounded work, but it is
not a free one: when it cannot prove the terminal state of a child that has
already exited, the slot of that child is kept, the session becomes
uncertain and the **current admission fails closed**.  No new charge is
taken while a settlement of this session is unproven, and the refusal is
reported explicitly instead of hiding behind the concurrency limit of a
full counter.  The window is re-checked after the reconciliation against
the *original* deadline, which is never rebased.

And a fifth rule makes the repeated settlement strict.  The shared counter
is the only proof of a terminal state, and the proof has to carry the
identity of the charge: the same budget and counter, the same charge
index, the same admission, the same original handle (pid and birth), the
same exit code and the matching terminal state.  A record of another
index, another handle, another exit code, an ``UNKNOWN`` state or a local
marker that the counter does not confirm is never an idempotent success.
"""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

COUNTER_SCHEMA = 'lvw.s3-cpu-budget/1'
BINDING_SCHEMA = 'S3_INTEGRATION_MACHINE_BINDING/1'
ROLES = ('implementation', 'independent_review')
CONTEXT_ENVIRONMENT_VARIABLE = 'LVW_S3_FIXTURE_CONTEXT'
GUARD_ROOT_ENVIRONMENT_VARIABLE = 'LVW_S3_GUARD_ROOT'
# The states of a charge that still occupy the concurrency slot.  An
# unresolved start is never released by a late or a repeated settlement.
OCCUPIED_STATES = ('PENDING', 'STARTED', 'UNKNOWN')
# The state of a charge whose start was refused inside the audit event of a
# process start.  That event is raised before the operating system action,
# so the refusal is a proven before fork position: the child was not created
# and the concurrency slot of the charge is released.  The charge itself is
# never removed, never refunded and never reset.
REFUSED_BEFORE_FORK = 'REFUSED_BEFORE_FORK'
TERMINAL_STATES = ('STOPPED', 'TIMED_OUT', 'UNKNOWN', REFUSED_BEFORE_FORK)
# The contract of the guard: an exception that carries this attribute was
# raised by the guard inside the audit event of a process start.  The marker
# alone proves nothing: an exception that only *claims* the marker is never
# trusted with the release of a concurrency slot.
BEFORE_FORK_MARKER = 'lvw_before_fork'
# The contract of a *proven* refusal.  The guard mints a credential inside
# the audit event of one process start and binds it to the executor, to the
# charge, to the thread and to the action of that start.  Only the live
# credential of the current action is consumed; a copied marker, a copied
# gate error and a replayed old refusal are all UNKNOWN.
REFUSAL_CREDENTIAL = 'lvw_refusal_credential'
# The terminal states that may *prove* an idempotent settlement.  ``UNKNOWN``
# is never one of them: an unresolved exit is not a proven terminal state
# and it never releases a slot.
PROVEN_TERMINAL_STATES = ('STOPPED', 'TIMED_OUT')


def persisted_terminal_matches(persisted, *, index, role, scenario, argv,
                               pid, birth, exit_code, state):
    """Whether the persisted record proves exactly this terminal state.

    This is the one rule of an idempotent settlement and it is shared by
    the reconciliation and by the final reaper.  The rule is strict on
    purpose: a persisted record proves the terminal state of this charge
    only when it carries

    * the same counter and the same budget (the caller reads the record
      from the bound counter and the counter verifies its own identity),
    * the same charge index,
    * the same admission: the same role, the same scenario and the same
      argv of the charge that this executor took,
    * the same **original handle**: the same pid and the same birth,
    * the same exit code, and
    * the matching terminal state, ``STOPPED`` or ``TIMED_OUT``.

    A record of another index, another handle, another exit code, an
    ``UNKNOWN`` state, or a state that only shares the *name* of a
    terminal state is never an idempotent success.  The second value of the
    result is the machine readable reason of a mismatch.
    """
    if not isinstance(persisted, dict):
        return False, 'NOT_A_CHARGE_RECORD'
    if persisted.get('index') != index:
        return False, 'FOREIGN_CHARGE_INDEX'
    if persisted.get('role') != role:
        return False, 'ROLE_MISMATCH'
    if persisted.get('scenario') != scenario:
        return False, 'ADMISSION_MISMATCH'
    if list(persisted.get('argv') or []) != list(argv or []):
        return False, 'ADMISSION_MISMATCH'
    if persisted.get('settled') is not True:
        return False, 'NOT_SETTLED'
    if state not in PROVEN_TERMINAL_STATES:
        return False, 'STATE_NOT_PROVABLE'
    if persisted.get('state') != state:
        return False, 'STATE_MISMATCH'
    if exit_code is None or persisted.get('exit_code') != exit_code:
        return False, 'EXIT_CODE_MISMATCH'
    if persisted.get('pid') != pid:
        return False, 'PID_MISMATCH'
    if persisted.get('birth') != birth:
        return False, 'BIRTH_MISMATCH'
    return True, None


class CpuGateError(RuntimeError):
    """A refused finite CPU operation with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


class RefusalCredential:
    """The one time evidence of a refusal that the guard itself produced.

    The credential is minted by the guard inside the audit event of a
    process start, in the thread of that start.  It is bound to the
    executor that took the charge, to the index of that charge, to the
    thread of the action and to the nonce of the action.  The first
    settlement that consumes it marks it as consumed, so a replayed
    exception never releases a second slot.
    """

    __slots__ = ('executor_id', 'charge_index', 'thread_id', 'action_nonce', 'code',
                 'consumed')

    def __init__(self, *, executor_id, charge_index, thread_id, action_nonce, code):
        self.executor_id = executor_id
        self.charge_index = charge_index
        self.thread_id = thread_id
        self.action_nonce = action_nonce
        self.code = code
        self.consumed = False

    def describe(self):
        return {'executor_id': self.executor_id, 'charge_index': self.charge_index,
                'thread_id': self.thread_id, 'action_nonce': self.action_nonce,
                'code': self.code, 'consumed': self.consumed}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def refusal_credential_of(error):
    """The credential that the guard attached to an error, if there is one.

    Only the *shape* of the credential is checked here.  Whether the
    credential belongs to the current executor, to the current charge, to
    the current thread and to the current action is decided by the
    executor that owns the charge.
    """
    credential = getattr(error, REFUSAL_CREDENTIAL, None)
    if credential is None:
        return None
    if getattr(credential, 'consumed', True) is not False:
        return None
    for field in ('executor_id', 'charge_index', 'thread_id', 'action_nonce', 'code'):
        if not hasattr(credential, field):
            return None
    return credential


def process_birth(pid):
    """Read the birth identity of a process that this executor holds.

    The identity is read from the operating system for the process that the
    executor itself started.  It is never taken from a value that the child
    reported about itself.
    """
    if type(pid) is not int or pid <= 0:
        return None
    try:
        fields = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
        return {'linux_start_ticks': int(fields[19])}
    except (OSError, IndexError, ValueError):
        return None


def _packed_ref(gitdir, ref):
    packed = gitdir / 'packed-refs'
    if not packed.is_file():
        raise CpuGateError('GIT_HEAD_UNRESOLVED')
    for line in packed.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#') or line.startswith('^'):
            continue
        parts = line.split(' ', 1)
        if len(parts) == 2 and parts[1].strip() == ref:
            return parts[0].strip()
    raise CpuGateError('GIT_HEAD_UNRESOLVED')


def resolve_head_commit(repository_root):
    """Read the actual candidate commit without starting a host process."""
    dotgit = Path(repository_root) / '.git'
    if dotgit.is_file():
        text = dotgit.read_text(encoding='utf-8').strip()
        if not text.startswith('gitdir:'):
            raise CpuGateError('GIT_METADATA_UNAVAILABLE')
        gitdir = Path(text.split(':', 1)[1].strip())
        if not gitdir.is_absolute():
            gitdir = (Path(repository_root) / gitdir).resolve()
    elif dotgit.is_dir():
        gitdir = dotgit
    else:
        raise CpuGateError('GIT_METADATA_UNAVAILABLE')
    # A linked worktree keeps its own HEAD, but the branch that it points at
    # lives in the common directory of the repository.
    common = gitdir
    common_file = gitdir / 'commondir'
    if common_file.is_file():
        try:
            raw = common_file.read_text(encoding='utf-8').strip()
        except OSError as error:
            raise CpuGateError('GIT_METADATA_UNAVAILABLE') from error
        common = Path(raw)
        if not common.is_absolute():
            common = (gitdir / common).resolve()
    try:
        head = (gitdir / 'HEAD').read_text(encoding='utf-8').strip()
    except OSError as error:
        raise CpuGateError('GIT_METADATA_UNAVAILABLE') from error
    if head.startswith('ref:'):
        ref = head.split(':', 1)[1].strip()
        ref_path = common / ref
        if ref_path.is_file():
            sha = ref_path.read_text(encoding='utf-8').strip()
        else:
            sha = _packed_ref(common, ref)
    else:
        sha = head
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise CpuGateError('GIT_HEAD_UNRESOLVED')
    return sha


class SharedCounter:
    """The root created shared budget counter.

    The counter is never created here and never reset here.  A missing
    counter is a refusal, not an empty budget.
    """

    def __init__(self, path, *, budget_id, limits):
        self.path = Path(path)
        self.budget_id = budget_id
        self.limits = limits

    def _open(self):
        if not self.path.is_file():
            raise CpuGateError('CPU_COUNTER_MISSING')
        try:
            handle = open(self.path, 'r+', encoding='utf-8')
        except OSError as error:
            raise CpuGateError('CPU_COUNTER_UNREADABLE') from error
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    @staticmethod
    def _read(handle):
        handle.seek(0)
        raw = handle.read()
        try:
            document = json.loads(raw)
        except ValueError as error:
            raise CpuGateError('CPU_COUNTER_INVALID') from error
        if not isinstance(document, dict):
            raise CpuGateError('CPU_COUNTER_INVALID')
        if document.get('kind') != COUNTER_SCHEMA:
            raise CpuGateError('CPU_COUNTER_SCHEMA_INVALID')
        if document.get('active') is not True:
            raise CpuGateError('CPU_COUNTER_INACTIVE')
        if (type(document.get('starts_total')) is not int
                or not isinstance(document.get('starts_by_role'), dict)
                or not isinstance(document.get('charges'), list)
                or not isinstance(document.get('sessions'), list)
                or type(document.get('reserved_wall_seconds')) not in (int, float)
                or type(document.get('spent_wall_seconds')) not in (int, float)):
            raise CpuGateError('CPU_COUNTER_INVALID')
        return document

    @staticmethod
    def _write(handle, document):
        raw = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        handle.seek(0)
        handle.truncate()
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())

    @staticmethod
    def _occupied(document):
        """The number of charges that still hold a concurrency slot.

        A pending, a started and an unknown charge all occupy a slot: an
        unresolved start is never released by a late or a repeated
        settlement.
        """
        return sum(1 for record in document['charges']
                   if record.get('state') in OCCUPIED_STATES)

    def charge(self, *, role, scenario, argv):
        """Charge one start atomically, before the operating system action."""
        if role not in ROLES:
            raise CpuGateError('CPU_ROLE_INVALID')
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            limits = self.limits
            if self._occupied(document) >= limits['max_concurrent']:
                raise CpuGateError('CPU_CONCURRENCY_LIMIT')
            if document['starts_total'] >= limits['max_total_starts']:
                raise CpuGateError('CPU_TOTAL_BUDGET_EXCEEDED')
            by_role = document['starts_by_role']
            if by_role.get(role, 0) >= limits['max_starts_by_role'].get(role, 0):
                raise CpuGateError('CPU_ROLE_BUDGET_EXCEEDED')
            record = {
                'index': len(document['charges']),
                'role': role,
                'scenario': scenario,
                'argv': list(argv),
                'started_wall': time.time(),
                'state': 'PENDING',
                'exit_code': None,
                'pid': None,
                'birth': None,
                'finished_wall': None,
                'observed_lifetime_seconds': None,
                'settled': False,
            }
            document['charges'].append(record)
            document['starts_total'] += 1
            by_role[role] = by_role.get(role, 0) + 1
            document['starts_by_role'] = by_role
            self._write(handle, document)
            return record['index']

    def mark_started(self, index, *, pid, birth):
        """Record the original handle of a charged start."""
        with self._open() as handle:
            document = self._read(handle)
            for record in document['charges']:
                if record.get('index') == index:
                    record['state'] = 'STARTED'
                    record['pid'] = pid
                    record['birth'] = birth
                    break
            self._write(handle, document)

    def finish(self, index, *, state, exit_code, spent, pid=None, birth=None):
        """Settle one charge exactly once.

        A charge is never removed and never refunded.  A repeated settlement
        of the same charge does nothing: it can neither free an unknown
        charge nor charge the budget twice.
        """
        if state not in TERMINAL_STATES:
            raise CpuGateError('CPU_CHARGE_STATE_INVALID')
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            settled = False
            for record in document['charges']:
                if record.get('index') != index:
                    continue
                if record.get('settled') is True:
                    settled = False
                    break
                record['state'] = state
                record['exit_code'] = exit_code
                record['pid'] = pid if pid is not None else record.get('pid')
                record['birth'] = birth if birth is not None else record.get('birth')
                record['finished_wall'] = time.time()
                # The child keeps its own observed lifetime.  The global
                # actual wall of the package is accounted once by the
                # settlement of the session, never by the sum of the child
                # ages.
                record['observed_lifetime_seconds'] = spent
                record['settled'] = True
                settled = True
                break
            self._write(handle, document)
            return settled

    def charge_state(self, index):
        """The read-only record of one charge of this counter.

        The record is never created and never changed here: it is the view
        that tells an idempotent settlement apart from a failed one.  The
        identity of the budget is verified here as well: a record of
        another budget is never read as the record of this counter.
        """
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            for record in document['charges']:
                if record.get('index') == index:
                    return dict(record)
            return None

    def reserve_session(self, session_id, *, owner_id, role, seconds):
        """Reserve this session's slice of the shared wall pool.

        The reservation is atomic and idempotent for the *same* runtime
        owner: the persisted start and the persisted deadlines are returned
        unchanged.  A different runtime owner that reuses the same session
        id is refused: a reconstructed executor may never acquire a fresh
        wall window.

        The window is bounded by the **actual reserved slice**, not by the
        remaining pool: a reservation of 60 seconds gives at most 30 seconds
        of admission and 30 seconds of cleanup.  The reservation is never
        refunded, so a session that dies still holds its slice.
        """
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            for record in document['sessions']:
                if record.get('session_id') != session_id:
                    continue
                if record.get('owner_id') != owner_id:
                    raise CpuGateError('CPU_SESSION_OWNER_MISMATCH')
                return dict(record)
            remaining = round(self.limits['shared_pool_seconds']
                              - float(document['reserved_wall_seconds']), 3)
            if remaining <= 0:
                raise CpuGateError('SHARED_WALL_POOL_EXHAUSTED')
            reservation = round(min(remaining, float(seconds)), 3)
            span = reservation
            admission = round(max(0.0, span - float(self.limits['cleanup_reserve_seconds'])), 3)
            now = time.time()
            record = {'session_id': session_id, 'owner_id': owner_id, 'role': role,
                      'reserved_wall_seconds': reservation,
                      'remaining_before_seconds': remaining,
                      'admission_seconds': admission,
                      'cleanup_seconds': span,
                      'reserved_at_wall': now,
                      'admission_deadline_wall': round(now + admission, 3),
                      'cleanup_deadline_wall': round(now + span, 3),
                      'started_wall': now, 'state': 'ACTIVE',
                      'spent_wall_seconds': None}
            document['sessions'].append(record)
            document['reserved_wall_seconds'] = round(
                float(document['reserved_wall_seconds']) + reservation, 3)
            self._write(handle, document)
            return dict(record)

    def settle_session(self, session_id, *, spent):
        """Settle this session exactly once and account its actual wall."""
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            for record in document['sessions']:
                if record.get('session_id') != session_id:
                    continue
                if record.get('state') == 'SETTLED':
                    return False
                record['state'] = 'SETTLED'
                record['spent_wall_seconds'] = round(float(spent), 3)
                record['finished_wall'] = time.time()
                # The global actual session wall is accounted exactly once.
                document['spent_wall_seconds'] = round(
                    float(document.get('spent_wall_seconds', 0.0)) + float(spent), 3)
                self._write(handle, document)
                return True
            raise CpuGateError('CPU_SESSION_UNKNOWN')

    def snapshot(self):
        with self._open() as handle:
            document = self._read(handle)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return document


class FiniteCpuExecutor:
    """The outer, independent guard of the finite fixture process plan."""

    def __init__(self, *, binding_path, binding_sha256, counter, role, python, pins,
                 candidate_sha, repository_root, package_root, guard_root, clock=None,
                 session_id=None):
        self.binding_path = Path(binding_path)
        self.binding_sha256 = binding_sha256
        self.counter = counter
        self.role = role
        self.python = python
        self.pins = pins
        self.candidate_sha = candidate_sha
        self.repository_root = Path(repository_root)
        self.package_root = Path(package_root)
        self.guard_root = Path(guard_root)
        self.clock = clock or time.monotonic
        self.session_id = session_id or ('session-' + uuid.uuid4().hex)
        self.owner_id = 'owner-' + uuid.uuid4().hex
        # The identity of this executor.  A refusal credential is bound to
        # it, so a credential of another executor is never consumed here.
        self.executor_id = 'executor-' + uuid.uuid4().hex
        self.session_started = self.clock()
        self.limits = counter.limits
        self.children = []
        self.refusals = []
        self.reservation = None
        self.reserved_at = None
        self.admission_deadline = None
        self.cleanup_deadline = None
        self.revoked = False
        self.uncertain = False
        self._lock = threading.Lock()
        self._watchdog = None
        self._stop = threading.Event()
        self._pending = []
        # The ledger of the charges of this executor.  It is the own record
        # of this instance: it knows every charge it took, whether that
        # charge ever produced a handle and how it ended.  A charge is never
        # removed from it and never refunded.
        self._charges = {}
        # The admission of the current thread.  The audit event of a process
        # start is raised in the thread that called the start, so the token
        # binds the charge to the operating system action of that thread.
        # The *action* is the scope of one start: it carries a nonce that no
        # other action of this executor can present.
        self._local = threading.local()
        self._local.action = None

    # -- the shared wall of this session ----------------------------------
    def reserve_session(self):
        """Reserve the slice of the shared wall pool of this session.

        The admission and the cleanup deadlines are derived from the shared
        remaining pool with the last reserve cleanup only.  A shared pool
        that is nearly exhausted refuses the session before any operating
        system action, even when the local clock of this executor starts at
        zero.
        """
        if self.reservation is not None:
            # The same runtime owner is idempotent: the persisted window is
            # returned unchanged and the deadlines are never rebased.
            return self.reservation
        record = self.counter.reserve_session(
            self.session_id, owner_id=self.owner_id, role=self.role,
            seconds=self.limits['session_wall_cap_seconds'])
        self.reservation = record
        # The persisted wall deadlines of the shared counter are the
        # authority.  They are converted once, into the local monotonic
        # clock of this process, and they are never recomputed.
        now_wall = time.time()
        now_mono = self.clock()
        self.reserved_at = now_mono
        self.admission_deadline = now_mono + max(
            0.0, float(record['admission_deadline_wall']) - now_wall)
        self.cleanup_deadline = now_mono + max(
            0.0, float(record['cleanup_deadline_wall']) - now_wall)
        return record

    # -- G2: the identity of everything that is about to run --------------
    def verify_identity(self):
        """Verify the sealed binding, the candidate and every pin.

        Any drift refuses the start before the operating system action.
        """
        if not self.binding_path.is_absolute():
            raise CpuGateError('BINDING_PATH_NOT_ABSOLUTE')
        if not self.binding_path.is_file():
            raise CpuGateError('BINDING_MISSING')
        actual_binding = sha256_file(self.binding_path)
        if actual_binding != self.binding_sha256:
            raise CpuGateError('BINDING_DIGEST_DRIFT')
        try:
            document = json.loads(self.binding_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise CpuGateError('BINDING_INVALID') from error
        if not isinstance(document, dict) or document.get('kind') != BINDING_SCHEMA:
            raise CpuGateError('BINDING_SCHEMA_INVALID')
        if document.get('execution_permitted') is not True:
            raise CpuGateError('BINDING_EXECUTION_NOT_PERMITTED')
        if document.get('candidate_sha') != self.candidate_sha:
            raise CpuGateError('BINDING_CANDIDATE_MISMATCH')
        head = resolve_head_commit(self.repository_root)
        if head != self.candidate_sha:
            raise CpuGateError('CANDIDATE_DRIFT')
        for relative, expected in sorted(self.pins.items()):
            path = self.package_root / relative
            if not path.is_file():
                raise CpuGateError('PIN_FILE_MISSING:' + relative)
            if sha256_file(path) != expected:
                raise CpuGateError('PIN_DRIFT:' + relative)
        python = self.python
        if not Path(python['path']).is_file():
            raise CpuGateError('PYTHON_MISSING')
        if sha256_file(python['path']) != python['sha256']:
            raise CpuGateError('PYTHON_DIGEST_DRIFT')
        return document

    # -- G4: the exact plan of one start ----------------------------------
    def _binding_plan(self):
        with open(self.binding_path, 'r', encoding='utf-8') as stream:
            return json.load(stream)

    def _scenario_of(self, argv):
        plan = self._binding_plan()
        prefix = list(plan.get('argv_prefix', []))
        if len(argv) != len(prefix) + 1 or argv[:len(prefix)] != prefix:
            raise CpuGateError('ARGV_DIFFERS_FROM_PLAN')
        scenario = argv[len(prefix)]
        if scenario not in plan.get('allowed_scenarios', []):
            raise CpuGateError('SCENARIO_NOT_IN_PLAN')
        return scenario

    def _check_context(self):
        """The bounded context document lives in the fresh runner owned root."""
        raw = os.environ.get(CONTEXT_ENVIRONMENT_VARIABLE)
        if not raw:
            raise CpuGateError('FIXTURE_CONTEXT_MISSING')
        path = Path(raw)
        if not path.is_absolute():
            raise CpuGateError('FIXTURE_CONTEXT_NOT_ABSOLUTE')
        try:
            path.resolve().relative_to(self.guard_root.resolve())
        except ValueError as error:
            raise CpuGateError('FIXTURE_CONTEXT_OUTSIDE_GUARD_ROOT') from error
        if not path.is_file() or path.stat().st_size > 64 * 1024:
            raise CpuGateError('FIXTURE_CONTEXT_INVALID')
        return path

    def _check_session(self):
        """The shared wall of this session, before the operating system action."""
        if self.revoked:
            raise CpuGateError('SESSION_ADMISSIONS_REVOKED')
        if self.uncertain:
            raise CpuGateError('SESSION_UNCERTAIN_CUSTODY')
        if self.reservation is None:
            # The slice of the shared pool is taken when the session first
            # asks for an admission.  A pool that is exhausted refuses here,
            # before the operating system action.
            self.reserve_session()
        if self.clock() >= self.admission_deadline:
            raise CpuGateError('SESSION_ADMISSION_WINDOW_CLOSED')

    # -- the admission that the audit hook calls --------------------------
    def admit(self, arguments):
        """Admit one process start.  This runs before the fork."""
        try:
            self.verify_identity()
            argv = list(arguments[1]) if len(arguments) > 1 and arguments[1] else []
            executable = arguments[0] if arguments else None
            cwd = arguments[2] if len(arguments) > 2 else None
            env = arguments[3] if len(arguments) > 3 else None
            if env is not None:
                raise CpuGateError('SPAWN_ENVIRONMENT_NOT_INHERITED')
            plan = self._binding_plan()
            prefix = list(plan.get('argv_prefix', []))
            if executable is not None and str(executable) != prefix[0]:
                raise CpuGateError('EXECUTABLE_NOT_THE_BOUND_PYTHON')
            scenario = self._scenario_of(argv)
            self._check_context()
            self._check_session()
            if cwd is not None:
                try:
                    Path(cwd).resolve().relative_to(self.guard_root.resolve())
                except ValueError as error:
                    raise CpuGateError('SPAWN_CWD_OUTSIDE_GUARD_ROOT') from error
            # The children that already exited release their slot before
            # this admission: a sequential run is never refused by the
            # ghosts of its own previous children.
            reconciliation = self.reconcile_exited_children()
            if reconciliation['failures']:
                # The reconciliation could not prove the terminal state of
                # every child that already exited.  The slots of those
                # charges are kept, the session becomes uncertain and this
                # admission fails closed: no new charge is taken while a
                # settlement of this session is unproven.  The failure is
                # reported explicitly instead of being hidden behind the
                # concurrency limit of a full counter.
                detail = ','.join(sorted({str(item.get('settlement_error'))
                                           for item in reconciliation['failures']}))
                raise CpuGateError('CPU_RECONCILIATION_UNSETTLED', detail=detail)
            # The reconciliation is bounded, but it is not free: the window
            # and the uncertainty are re-checked *after* it, against the
            # original deadline.  The deadline is never rebased and a
            # reconciliation that crossed it refuses this admission.
            self._check_session()
            index = self.counter.charge(role=self.role, scenario=scenario, argv=argv)
        except CpuGateError as error:
            self.refusals.append(error.code)
            raise
        with self._lock:
            self._pending.append(index)
            self._charges[index] = {
                'index': index, 'scenario': scenario, 'argv': list(argv),
                'admitted_wall': time.time(), 'handle_obtained': False,
                'handle_proven': None, 'outcome': 'ADMITTED',
                'refusal_code': None, 'created': None,
                'settlement_persisted': None, 'settlement_error': None,
            }
        # The token binds this charge to the operating system action of this
        # thread.  The guard of the runner asks for the admission from inside
        # the audit event of the start, in the very same thread.  The nonce of
        # the current action is part of the token: a refusal of another
        # action can never present it.
        action = getattr(self._local, 'action', None)
        self._local.admission = {'index': index, 'scenario': scenario,
                                 'nonce': action.get('nonce') if action else None}
        return True

    # -- the refusal credential of the guard --------------------------------
    def mint_refusal_credential(self, code):
        """Mint the one time credential of a refusal of this action.

        The guard calls this inside the audit event of a process start, in
        the thread of that start.  A credential exists only when this
        executor admitted a start in this very action: a refusal without a
        live admission has no charge to settle and mints nothing.
        """
        token = getattr(self._local, 'admission', None)
        action = getattr(self._local, 'action', None)
        if token is None or action is None:
            return None
        nonce = token.get('nonce')
        if nonce is None or nonce != action.get('nonce'):
            return None
        return RefusalCredential(executor_id=self.executor_id,
                                 charge_index=token['index'],
                                 thread_id=threading.get_ident(),
                                 action_nonce=nonce, code=code)

    def _verify_refusal_credential(self, error, token):
        """Whether the error carries the live credential of this action.

        The credential must belong to this executor, to this charge, to this
        thread and to this action, and it must not have been consumed
        already.  A copied marker, a copied gate error and a replayed old
        refusal are all rejected here and stay UNKNOWN.
        """
        credential = refusal_credential_of(error)
        if credential is None:
            return None
        action = getattr(self._local, 'action', None)
        if action is None or token is None:
            return None
        if credential.executor_id != self.executor_id:
            return None
        if credential.thread_id != threading.get_ident():
            return None
        if credential.action_nonce != action.get('nonce'):
            return None
        if credential.charge_index != token.get('index'):
            return None
        if token.get('nonce') != action.get('nonce'):
            return None
        credential.consumed = True
        return credential

    # -- G5: the custody of the started children --------------------------
    def spawn(self, command):
        """Start one child and take the custody of its original handle.

        The custody is taken immediately.  A failure of the registration or
        of the watchdog setup never loses the handle: the child is still
        stopped by this executor and the cleanup still runs.

        A failure of the operating system action itself never leaves a
        charge without a terminal state.  The charge was taken before the
        action, so it is settled here: either as a refusal that the guard
        proved before the fork, or as an unknown custody that keeps its
        slot, its reservation and the owned root.
        """
        # The scope of this action.  The nonce of the action is what a
        # refusal credential of this action has to present.
        action = {'nonce': uuid.uuid4().hex}
        self._local.action = action
        self._local.admission = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       bufsize=0, cwd=str(self.guard_root))
        except BaseException as error:  # noqa: BLE001 - the state stays visible
            self._settle_without_handle(error)
            raise
        token = getattr(self._local, 'admission', None)
        self._local.admission = None
        self._local.action = None
        entry = self._take_custody(process, token)
        try:
            self._ensure_watchdog()
        except BaseException:
            # The watchdog could not be armed.  The handle is still owned.
            self._stop_child(entry)
            raise
        return process

    def _settle_without_handle(self, error):
        """Settle the charge of a start that never produced a handle.

        The charge was taken before the operating system action, so it is
        never removed and never refunded.  Two terminal states are possible:

        ``REFUSED_BEFORE_FORK``
            The guard refused inside the audit event of the start and
            proved it with the one time credential of this very action.
            That event is raised before the fork, so the child was not
            created.  The concurrency slot of the charge is released and
            the root may be removed.

        ``UNKNOWN``
            Every other failure of the operating system action may have had
            side effects.  The charge keeps its slot, the session becomes
            uncertain and the owned root is kept.

        A settlement that the counter did not accept changes neither of
        them: the charge stays in the pending set, it is not written as a
        terminal state and the session stays uncertain.  The reaper settles
        it again and the finalizer keeps the root.
        """
        token = getattr(self._local, 'admission', None)
        self._local.admission = None
        if token is None:
            # No admission was charged for this action: nothing is settled.
            self._local.action = None
            return None
        index = token['index']
        credential = self._verify_refusal_credential(error, token)
        self._local.action = None
        if credential is not None:
            state = REFUSED_BEFORE_FORK
            created = False
            code = credential.code
            spent = 0.0
        else:
            state = 'UNKNOWN'
            created = None
            code = getattr(getattr(error, 'gate_error', None), 'code', None)
            if code is None:
                code = getattr(error, 'code', type(error).__name__)
            spent = None
            # The custody of a possible child is unknown: the session may
            # not admit another start and the root may not be removed.
            self.uncertain = True
        persisted = False
        settlement_error = None
        try:
            persisted = self.counter.finish(index, state=state, exit_code=None,
                                            spent=spent, pid=None,
                                            birth=None) is True
        except CpuGateError as failure:
            settlement_error = failure.code
        if not persisted:
            # The terminal state was not persisted.  The charge is not
            # removed from the pending set, it is not written as a settled
            # terminal state and the session stays uncertain.
            self.uncertain = True
            state = 'UNKNOWN'
            created = None
            code = settlement_error or code
        else:
            with self._lock:
                if index in self._pending:
                    self._pending.remove(index)
        with self._lock:
            record = self._charges.get(index)
            if record is not None:
                record['outcome'] = state
                record['created'] = created
                record['refusal_code'] = code
                record['settlement_persisted'] = persisted
                record['settlement_error'] = settlement_error
        return state

    def _take_custody(self, process, token=None):
        pid = getattr(process, 'pid', None)
        entry = {'index': None, 'process': process, 'pid': pid,
                 'birth': process_birth(pid), 'started': self.clock(),
                 'state': 'STARTED', 'exit_code': None, 'timed_out': False,
                 'proven': False, 'settlement_persisted': False,
                 'stop_attempts': 0, 'last_stop_attempt': None}
        with self._lock:
            index = None
            if token is not None:
                index = token['index']
                if index in self._pending:
                    self._pending.remove(index)
            elif self._pending:
                index = self._pending.pop(0)
            entry['index'] = index
            self.children.append(entry)
        if index is not None:
            try:
                self.counter.mark_started(index, pid=pid, birth=entry['birth'])
            except CpuGateError:
                entry['state'] = 'UNKNOWN'
                self.uncertain = True
            with self._lock:
                record = self._charges.get(index)
                if record is not None:
                    record['handle_obtained'] = True
                    record['outcome'] = 'HANDLE'
        return entry

    def register(self, process):
        """Take the custody of a child that was started elsewhere."""
        entry = self._take_custody(process)
        self._ensure_watchdog()
        return entry

    # -- the bounded reconciliation of the children that already exited ----
    def _persisted_terminal_proof(self, index, entry, exit_code, state):
        """The strict proof that the counter persists this terminal state.

        The proof is read from the bound shared counter and it is matched
        with the one strict rule of this module.  A counter that cannot be
        read is never an absent record: it is a failure, and a failure
        never releases a slot.
        """
        with self._lock:
            record = self._charges.get(index)
        if record is None:
            return False, 'NO_LOCAL_ADMISSION'
        try:
            persisted = self.counter.charge_state(index)
        except CpuGateError as error:
            return False, error.code
        except OSError:
            return False, 'CPU_COUNTER_IO_ERROR'
        if persisted is None:
            return False, 'NO_PERSISTED_RECORD'
        return persisted_terminal_matches(
            persisted, index=index, role=self.role,
            scenario=record.get('scenario'), argv=record.get('argv'),
            pid=entry.get('pid'), birth=entry.get('birth'),
            exit_code=exit_code, state=state)

    def reconcile_exited_children(self):
        """Release the slot of a child whose original handle proves its exit.

        The final reaper of the executor is the *last* accounting of the
        children.  A sequential run admits its next start long before that
        final reap: a child that has already exited keeps its charge in the
        ``STARTED`` state and keeps its concurrency slot, so the third
        sequential start would be refused by the shared counter although the
        first two children are gone.

        This reconciliation runs before an admission and it never replaces
        the final reap:

        * it looks only at the children that **this** executor owns,
        * it releases a slot only when the **original handle** proves that
          the child exited and when the shared counter **persists** the
          terminal state of that charge, with the exact identity of that
          charge (see ``persisted_terminal_matches``),
        * a live child, an unproven child, a conflicting persisted record
          and a settlement that the counter did not accept keep their slot,
        * the cumulative starts, the charges and the evidence of the
          original run are never removed, never refunded and never reset,
        * it never revokes the admissions, never stops the watchdog and
          never takes a new custody.

        The result is explicit: the entries that were released and the
        entries whose settlement could not be proven.  A failure is never
        hidden and it never releases anything.

        The reconciliation is bounded: it inspects the owned children of
        this executor once and it never waits for anything.
        """
        released = []
        failures = []
        with self._lock:
            children = list(self.children)
        for entry in children:
            index = entry.get('index')
            if index is None:
                continue
            if entry.get('state') != 'STARTED':
                # Only a child that this executor still holds open is a
                # candidate.  A settled child and an unknown child keep
                # their slot.
                continue
            if entry.get('settlement_persisted') is True:
                continue
            process = entry.get('process')
            if process is None:
                continue
            try:
                exit_code = process.poll()
            except Exception:  # noqa: BLE001 - the failure stays visible
                # The exit of this child cannot be observed: the slot is
                # kept and nothing is claimed about the child.
                exit_code = None
            if exit_code is None:
                # The child is still alive: it keeps its slot.
                continue
            state = 'TIMED_OUT' if entry.get('timed_out') else 'STOPPED'
            spent = round(self.clock() - entry['started'], 3)
            persisted = False
            settlement_error = None
            reason = None
            # The persisted proof comes first: the local marker of a former
            # reconciliation is never a proof by itself, and a record that
            # conflicts with this charge is never an idempotent success.
            proof, reason = self._persisted_terminal_proof(index, entry, exit_code, state)
            if proof:
                # The counter already persists exactly this terminal state.
                # The settlement is idempotent: the finished_wall of the
                # charge is never written a second time.
                persisted = True
            elif reason in ('NO_PERSISTED_RECORD', 'NOT_SETTLED'):
                # The charge is not settled yet: the settlement is attempted.
                try:
                    persisted = self.counter.finish(index, state=state, exit_code=exit_code,
                                                    spent=spent, pid=entry.get('pid'),
                                                    birth=entry.get('birth')) is True
                except CpuGateError as failure:
                    settlement_error = failure.code
                except OSError:
                    # An ordinary I/O failure of the counter is a failure of
                    # the settlement, never an absent proof.
                    settlement_error = 'CPU_COUNTER_IO_ERROR'
                if not persisted and settlement_error is None:
                    # The counter may have accepted the settlement of this
                    # very charge: only the strict proof decides.
                    proof, reason = self._persisted_terminal_proof(
                        index, entry, exit_code, state)
                    persisted = proof
                    if not proof:
                        settlement_error = reason
            else:
                # A conflict: the persisted state is not the terminal state
                # of this charge.  Nothing is released and the conflict is
                # reported.
                settlement_error = reason
            if not persisted:
                # Nothing is released: the charge keeps its slot, the
                # settlement of this session is uncertain and the finalizer
                # keeps the owned root.
                self.uncertain = True
                with self._lock:
                    record = self._charges.get(index)
                    if record is not None:
                        record['settlement_persisted'] = False
                        record['settlement_error'] = settlement_error
                        record['outcome'] = 'UNKNOWN'
                failures.append({'index': index, 'state': state,
                                 'exit_code': exit_code,
                                 'settlement_error': settlement_error,
                                 'reason': reason})
                continue
            entry['exit_code'] = exit_code
            entry['state'] = state
            entry['proven'] = True
            entry['settlement_persisted'] = True
            with self._lock:
                record = self._charges.get(index)
                if record is not None:
                    record['handle_proven'] = True
                    record['settlement_persisted'] = True
                    record['settlement_error'] = None
            released.append({'index': index, 'state': state, 'exit_code': exit_code,
                             'spent_wall_seconds': spent})
        return {'released': released, 'failures': failures}

    def _ensure_watchdog(self):
        if self._watchdog is not None:
            return
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def _watch(self):
        """The independent per child deadline of the executor.

        The bounded termination starts early enough that the whole per
        child budget, the cleanup included, stays inside the seal.  An
        *unknown* live handle stays eligible for this bounded safety
        action: it keeps its occupied charge and its root and it blocks the
        admission, but it is never left without the only remaining safety.

        The action is bounded and never a busy loop: at most one attempt per
        backoff window and never more than the declared maximum of attempts.
        """
        limit = float(self.limits['per_process_seconds'])
        margin = float(self.limits['per_child_termination_margin_seconds'])
        backoff = float(self.limits['per_child_kill_seconds'])
        maximum = int(self.limits['per_child_stop_attempts'])
        while not self._stop.wait(0.02):
            with self._lock:
                children = list(self.children)
            now = self.clock()
            for entry in children:
                if entry['state'] not in ('STARTED', 'UNKNOWN'):
                    continue
                if entry.get('proven') is True:
                    continue
                stop_deadline = self._stop_deadline(entry, self.cleanup_deadline)
                if now < stop_deadline - margin:
                    continue
                if entry.get('stop_attempts', 0) >= maximum:
                    continue
                last = entry.get('last_stop_attempt')
                if last is not None and now - last < backoff:
                    continue
                entry['stop_attempts'] = entry.get('stop_attempts', 0) + 1
                entry['last_stop_attempt'] = now
                entry['timed_out'] = True
                self._stop_child(entry, self.cleanup_deadline)

    def _stop_deadline(self, entry, session_deadline=None):
        """The one absolute deadline of the stop of one child.

        It is the earlier of the per child budget and the session cleanup
        deadline.  Every wait of the stop is clipped to it.
        """
        deadline = entry['started'] + float(self.limits['per_process_seconds'])
        if session_deadline is not None:
            deadline = min(deadline, session_deadline)
        return deadline

    def _wait_budget(self, stop_deadline):
        """The remaining time of the stop, recomputed before every wait."""
        remaining = max(0.0, stop_deadline - self.clock())
        return min(float(self.limits['per_child_kill_seconds']), remaining)

    def _stop_child(self, entry, session_deadline=None):
        """Stop one owned child with a bounded cleanup.

        There is exactly one absolute stop deadline and the remaining time is
        recomputed before every wait, the post kill wait included.  The
        total stop therefore never exceeds the per child budget.
        """
        process = entry['process']
        stop_deadline = self._stop_deadline(entry, session_deadline)
        try:
            process.terminate()
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass
        try:
            process.wait(timeout=self._wait_budget(stop_deadline))
        except Exception:  # noqa: BLE001 - the failure stays visible
            try:
                process.kill()
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
            try:
                process.wait(timeout=self._wait_budget(stop_deadline))
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass

    def revoke_admissions(self):
        """Stop every further admission of this session."""
        self.revoked = True

    def reap(self):
        """The bounded reaper of the executor with its own deadline.

        The finalizer revokes the admissions and stops every live original
        handle first.  Only a child whose exit is proven is closed; an
        unproven child keeps its occupied slot, keeps the root and keeps
        the watchdog armed, because the watchdog is the only remaining
        safety of a child that did not stop.
        """
        self.revoke_admissions()
        deadline = self.cleanup_deadline if self.cleanup_deadline is not None \
            else self.session_started + float(self.limits['shared_pool_seconds'])
        proofs = []
        with self._lock:
            children = list(self.children)
        for entry in children:
            process = entry['process']
            try:
                live = process.poll() is None
            except Exception:  # noqa: BLE001 - the failure stays visible
                live = True
            if live:
                # The live original handle is stopped here.  The finalizer
                # never waits for a young child to reach the watchdog.
                self._stop_child(entry, deadline)
            # The final proof wait uses the *same* absolute child deadline as
            # the stop.  The lifetime observation of a child therefore never
            # reaches beyond the per child budget, not even when the stop and
            # the proof wait both time out.
            stop_deadline = self._stop_deadline(entry, deadline)
            remaining = max(0.0, stop_deadline - self.clock())
            exit_code = None
            proven = False
            try:
                exit_code = process.wait(timeout=min(remaining, 5.0))
                proven = exit_code is not None
            except Exception:  # noqa: BLE001 - the failure stays visible
                exit_code = None
            entry['exit_code'] = exit_code
            spent = round(self.clock() - entry['started'], 3)
            if not proven:
                entry['state'] = 'UNKNOWN'
                self.uncertain = True
            elif entry['timed_out']:
                entry['state'] = 'TIMED_OUT'
            else:
                entry['state'] = 'STOPPED'
            entry['proven'] = proven
            # The settlement of the charge is the last accounting step of
            # this child.  A settlement that the counter did not accept
            # leaves the charge open: the proof of the exit may never be
            # presented as a proven cleanup.
            persisted = True
            settlement_error = None
            if entry['index'] is not None:
                proof = False
                reason = None
                if entry['state'] in PROVEN_TERMINAL_STATES:
                    proof, reason = self._persisted_terminal_proof(
                        entry['index'], entry, exit_code, entry['state'])
                if proof:
                    # The terminal state of this child is already persisted
                    # with the exact identity of this charge: the finalizer
                    # never settles it a second time and never rewrites its
                    # finished_wall.
                    persisted = True
                elif entry.get('settlement_persisted') is True:
                    # The local marker claims a settlement that the shared
                    # counter does not prove.  The counter is the authority:
                    # the charge stays open and the cleanup stays uncertain.
                    persisted = False
                    settlement_error = reason or 'PERSISTED_STATE_NOT_PROVEN'
                else:
                    try:
                        persisted = self.counter.finish(
                            entry['index'], state=entry['state'], exit_code=exit_code,
                            spent=spent, pid=entry['pid'], birth=entry['birth']) is True
                    except CpuGateError as failure:
                        persisted = False
                        settlement_error = failure.code
                    except OSError:
                        persisted = False
                        settlement_error = 'CPU_COUNTER_IO_ERROR'
                    if (not persisted and settlement_error is None
                            and entry['state'] in PROVEN_TERMINAL_STATES):
                        # The counter may already hold this terminal state:
                        # only the strict proof decides whether the repeated
                        # settlement is idempotent.  An ``UNKNOWN`` record or
                        # a record of another charge is never a success.
                        proof, reason = self._persisted_terminal_proof(
                            entry['index'], entry, exit_code, entry['state'])
                        persisted = proof
                        if not proof:
                            settlement_error = reason
                if not persisted:
                    entry['state'] = 'UNKNOWN'
                    self.uncertain = True
                with self._lock:
                    record = self._charges.get(entry['index'])
                    if record is not None:
                        record['handle_proven'] = proven
                        record['settlement_persisted'] = persisted
                        record['settlement_error'] = settlement_error
                        if not proven or not persisted:
                            record['outcome'] = 'UNKNOWN'
            proofs.append({'index': entry['index'], 'state': entry['state'],
                           'exit_code': exit_code, 'spent_wall_seconds': spent,
                           'timed_out': entry['timed_out'], 'pid': entry['pid'],
                           'birth': entry['birth'], 'proven': proven,
                           'persisted': persisted,
                           'settlement_error': settlement_error,
                           'handle_obtained': True})
        # Every admission that never produced a handle is settled here.  The
        # charge was taken before the operating system action, so it is never
        # removed and never refunded: an unknown custody keeps its slot and
        # keeps the root, because a child may exist without a handle.
        with self._lock:
            leftover = list(self._pending)
            self._pending.clear()
        for index in leftover:
            persisted = False
            settlement_error = None
            try:
                persisted = self.counter.finish(index, state='UNKNOWN', exit_code=None,
                                               spent=None) is True
            except CpuGateError as failure:
                settlement_error = failure.code
            self.uncertain = True
            with self._lock:
                record = self._charges.get(index)
                if record is not None:
                    record['outcome'] = 'UNKNOWN'
                    record['created'] = None
                    record['settlement_persisted'] = persisted
                    record['settlement_error'] = settlement_error
            proofs.append({'index': index, 'state': 'UNKNOWN', 'exit_code': None,
                           'spent_wall_seconds': None, 'timed_out': False,
                           'pid': None, 'birth': None, 'proven': False,
                           'persisted': persisted,
                           'settlement_error': settlement_error,
                           'handle_obtained': False,
                           'reason': 'ADMITTED_WITHOUT_HANDLE'})
        if all(proof['proven'] for proof in proofs):
            # Every child is proven gone: the watchdog may be disarmed.
            self._stop.set()
        else:
            # An unproven child keeps the watchdog armed: it is the only
            # remaining safety and the session stays uncertain.
            self.uncertain = True
        return proofs

    def settle_session(self):
        """Account the actual wall of this session, cleanup included."""
        spent = round(self.clock() - self.session_started, 3)
        # An ordinary failure of the settlement is visible: it is never
        # swallowed into a silent success.
        settled = self.counter.settle_session(self.session_id, spent=spent)
        return spent if settled else None

    def unsettled_charges(self):
        """The charges of this executor that no proof has settled.

        A charge that was admitted but never produced a handle, a charge
        whose exit was never proven and a charge whose settlement was not
        persisted are unsettled: they keep their concurrency slot and they
        keep the owned root.  The finalizer may not report a proven cleanup
        while such a charge exists.
        """
        unsettled = []
        with self._lock:
            records = list(self._charges.values())
        for record in records:
            open_charge = (record['outcome'] in ('ADMITTED', 'UNKNOWN')
                           or (record['handle_obtained']
                               and record['handle_proven'] is not True)
                           or record.get('settlement_persisted') is False)
            if open_charge:
                unsettled.append({'index': record['index'],
                                  'scenario': record['scenario'],
                                  'outcome': record['outcome'],
                                  'handle_obtained': record['handle_obtained'],
                                  'handle_proven': record['handle_proven'],
                                  'settlement_persisted': record.get('settlement_persisted'),
                                  'settlement_error': record.get('settlement_error'),
                                  'refusal_code': record['refusal_code']})
        return unsettled

    def charge_ledger(self):
        """The ledger of the charges of this executor.

        Every charge that this executor took is in the ledger, whatever
        ended it.  A charge is never removed from it, never refunded and
        never reset.
        """
        with self._lock:
            records = list(self._charges.values())
        return [dict(record) for record in records]

    def session_evidence(self):
        try:
            counter = self.counter.snapshot()
        except CpuGateError as error:
            counter = {'status': 'UNAVAILABLE', 'code': error.code}
        ledger = self.charge_ledger()
        obtained = sum(1 for record in ledger if record['handle_obtained'])
        proven = sum(1 for record in ledger
                     if record['handle_obtained'] and record['handle_proven'] is True)
        without_handle = [{'index': record['index'],
                           'scenario': record['scenario'],
                           'outcome': record['outcome'],
                           'refusal_code': record['refusal_code'],
                           'settlement_persisted': record.get('settlement_persisted')}
                          for record in ledger if not record['handle_obtained']]
        settlement_failures = [{'index': record['index'],
                                'outcome': record['outcome'],
                                'settlement_error': record.get('settlement_error')}
                               for record in ledger
                               if record.get('settlement_persisted') is False]
        return {
            'kind': 'lvw.s3-finite-cpu-session/1',
            'role': self.role,
            'session_id': self.session_id,
            'binding_path': str(self.binding_path),
            'binding_sha256': self.binding_sha256,
            'candidate_sha': self.candidate_sha,
            'counter_path': str(self.counter.path),
            'counter_budget_id': self.counter.budget_id,
            'reservation': self.reservation,
            'admission_deadline': self.admission_deadline,
            'cleanup_deadline': self.cleanup_deadline,
            'starts_total': counter.get('starts_total') if isinstance(counter, dict) else None,
            'starts_by_role': counter.get('starts_by_role') if isinstance(counter, dict) else None,
            'reserved_wall_seconds': counter.get('reserved_wall_seconds') if isinstance(counter, dict) else None,
            'spent_wall_seconds': counter.get('spent_wall_seconds') if isinstance(counter, dict) else None,
            'counter': counter,
            # The admitted attempts and the proven child handles are two
            # different numbers and are reported as two different numbers.
            'admitted_attempts': len(ledger),
            'child_handles_obtained': obtained,
            'proven_child_handles': proven,
            'charges_without_handle': without_handle,
            'settlement_failures': settlement_failures,
            'charge_ledger': ledger,
            'children': [{'index': entry['index'], 'state': entry['state'],
                          'exit_code': entry['exit_code'],
                          'timed_out': entry['timed_out'],
                          'proven': entry['proven'],
                          'pid': entry['pid'], 'birth': entry['birth']}
                         for entry in self.children],
            'refusals': list(self.refusals),
            'uncertain': self.uncertain,
            'admissions_revoked': self.revoked,
            'stage_pass_claim': False,
            'product_gate0': False,
        }


def build_executor(*, binding_path, binding_sha256, role, repository_root, package_root,
                   guard_root, clock=None, session_id=None):
    """Build the executor from the sealed root binding."""
    if role not in ROLES:
        raise CpuGateError('CPU_ROLE_INVALID')
    binding_path = Path(binding_path)
    if not binding_path.is_absolute():
        raise CpuGateError('BINDING_PATH_NOT_ABSOLUTE')
    document = json.loads(binding_path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('kind') != BINDING_SCHEMA:
        raise CpuGateError('BINDING_SCHEMA_INVALID')
    budget = document.get('cpu_budget')
    if not isinstance(budget, dict):
        raise CpuGateError('BINDING_CPU_BUDGET_MISSING')
    limits = {
        'max_total_starts': budget.get('max_total_starts'),
        'max_starts_by_role': budget.get('max_starts_by_role'),
        'max_concurrent': budget.get('max_concurrent'),
        'per_process_seconds': budget.get('per_process_seconds'),
        'shared_pool_seconds': budget.get('shared_pool_seconds'),
        'session_wall_cap_seconds': budget.get('session_wall_cap_seconds'),
        'cleanup_reserve_seconds': budget.get('cleanup_reserve_seconds'),
        'per_child_termination_margin_seconds': budget.get(
            'per_child_termination_margin_seconds'),
        'per_child_kill_seconds': budget.get('per_child_kill_seconds'),
        'per_child_stop_attempts': budget.get('per_child_stop_attempts'),
    }
    for key in ('max_total_starts', 'max_concurrent', 'per_process_seconds',
                'shared_pool_seconds', 'session_wall_cap_seconds',
                'cleanup_reserve_seconds', 'per_child_termination_margin_seconds',
                'per_child_kill_seconds', 'per_child_stop_attempts'):
        if type(limits[key]) is not int or limits[key] <= 0:
            raise CpuGateError('BINDING_CPU_BUDGET_INVALID:' + key)
    if not isinstance(limits['max_starts_by_role'], dict):
        raise CpuGateError('BINDING_CPU_BUDGET_INVALID:max_starts_by_role')
    if limits['cleanup_reserve_seconds'] >= limits['shared_pool_seconds']:
        raise CpuGateError('BINDING_CPU_BUDGET_INVALID:cleanup_reserve_seconds')
    if limits['per_child_termination_margin_seconds'] >= limits['per_process_seconds']:
        raise CpuGateError('BINDING_CPU_BUDGET_INVALID:per_child_termination_margin_seconds')
    counter = SharedCounter(budget.get('counter_path'), budget_id=budget.get('budget_id'),
                            limits=limits)
    pins = document.get('source_pins')
    if not isinstance(pins, dict) or not pins:
        raise CpuGateError('BINDING_SOURCE_PINS_MISSING')
    python = document.get('python')
    if not isinstance(python, dict) or 'path' not in python or 'sha256' not in python:
        raise CpuGateError('BINDING_PYTHON_MISSING')
    return FiniteCpuExecutor(binding_path=binding_path, binding_sha256=binding_sha256,
                              counter=counter, role=role, python=python, pins=pins,
                              candidate_sha=document.get('candidate_sha'),
                              repository_root=repository_root, package_root=package_root,
                              guard_root=guard_root, clock=clock, session_id=session_id)
