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
# raised by the guard inside the audit event of a process start.
BEFORE_FORK_MARKER = 'lvw_before_fork'


class CpuGateError(RuntimeError):
    """A refused finite CPU operation with a stable, machine readable code."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def is_proven_before_fork_refusal(error):
    """Whether an error is a trusted refusal that happened before the fork.

    The refusal must carry the executor's own gate error: an exception that
    merely claims to be a refusal is not trusted.  The audit event of a
    process start is raised before the operating system action, so a refusal
    that the guard raised inside that event is a proven before fork position.
    """
    if getattr(error, BEFORE_FORK_MARKER, False) is not True:
        return False
    return isinstance(getattr(error, 'gate_error', None), CpuGateError)


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
        self._local = threading.local()

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
            }
        # The token binds this charge to the operating system action of this
        # thread.  The guard of the runner asks for the admission from inside
        # the audit event of the start, in the very same thread.
        self._local.admission = {'index': index, 'scenario': scenario}
        return True

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
            The guard refused inside the audit event of the start.  That
            event is raised before the fork, so the child was not created.
            The concurrency slot of the charge is released and the root may
            be removed.

        ``UNKNOWN``
            Every other failure of the operating system action may have had
            side effects.  The charge keeps its slot, the session becomes
            uncertain and the owned root is kept.
        """
        token = getattr(self._local, 'admission', None)
        self._local.admission = None
        if token is None:
            # No admission was charged for this action: nothing is settled.
            return None
        index = token['index']
        with self._lock:
            if index in self._pending:
                self._pending.remove(index)
        if is_proven_before_fork_refusal(error):
            state = REFUSED_BEFORE_FORK
            created = False
            code = getattr(getattr(error, 'gate_error', None), 'code', None)
            spent = 0.0
        else:
            state = 'UNKNOWN'
            created = None
            code = getattr(error, 'code', type(error).__name__)
            spent = None
            # The custody of a possible child is unknown: the session may
            # not admit another start and the root may not be removed.
            self.uncertain = True
        try:
            self.counter.finish(index, state=state, exit_code=None, spent=spent,
                                pid=None, birth=None)
        except CpuGateError:
            self.uncertain = True
        with self._lock:
            record = self._charges.get(index)
            if record is not None:
                record['outcome'] = state
                record['created'] = created
                record['refusal_code'] = code
        return state

    def _take_custody(self, process, token=None):
        pid = getattr(process, 'pid', None)
        entry = {'index': None, 'process': process, 'pid': pid,
                 'birth': process_birth(pid), 'started': self.clock(),
                 'state': 'STARTED', 'exit_code': None, 'timed_out': False,
                 'proven': False, 'stop_attempts': 0, 'last_stop_attempt': None}
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
            proofs.append({'index': entry['index'], 'state': entry['state'],
                           'exit_code': exit_code, 'spent_wall_seconds': spent,
                           'timed_out': entry['timed_out'], 'pid': entry['pid'],
                           'birth': entry['birth'], 'proven': proven,
                           'handle_obtained': True})
            if entry['index'] is not None:
                try:
                    self.counter.finish(entry['index'], state=entry['state'],
                                        exit_code=exit_code, spent=spent,
                                        pid=entry['pid'], birth=entry['birth'])
                except CpuGateError:
                    entry['state'] = 'UNKNOWN'
                    self.uncertain = True
                with self._lock:
                    record = self._charges.get(entry['index'])
                    if record is not None:
                        record['handle_proven'] = proven
                        if not proven:
                            record['outcome'] = 'UNKNOWN'
        # Every admission that never produced a handle is settled here.  The
        # charge was taken before the operating system action, so it is never
        # removed and never refunded: an unknown custody keeps its slot and
        # keeps the root, because a child may exist without a handle.
        with self._lock:
            leftover = list(self._pending)
            self._pending.clear()
        for index in leftover:
            try:
                self.counter.finish(index, state='UNKNOWN', exit_code=None, spent=None)
            except CpuGateError:
                pass
            self.uncertain = True
            with self._lock:
                record = self._charges.get(index)
                if record is not None:
                    record['outcome'] = 'UNKNOWN'
                    record['created'] = None
            proofs.append({'index': index, 'state': 'UNKNOWN', 'exit_code': None,
                           'spent_wall_seconds': None, 'timed_out': False,
                           'pid': None, 'birth': None, 'proven': False,
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

        A charge that was admitted but never produced a handle, and a charge
        whose exit was never proven, are unsettled: they keep their
        concurrency slot and they keep the owned root.  The finalizer may
        not report a proven cleanup while such a charge exists.
        """
        unsettled = []
        with self._lock:
            records = list(self._charges.values())
        for record in records:
            open_charge = (record['outcome'] in ('ADMITTED', 'UNKNOWN')
                           or (record['handle_obtained']
                               and record['handle_proven'] is not True))
            if open_charge:
                unsettled.append({'index': record['index'],
                                  'scenario': record['scenario'],
                                  'outcome': record['outcome'],
                                  'handle_obtained': record['handle_obtained'],
                                  'handle_proven': record['handle_proven'],
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
                           'refusal_code': record['refusal_code']}
                          for record in ledger if not record['handle_obtained']]
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
