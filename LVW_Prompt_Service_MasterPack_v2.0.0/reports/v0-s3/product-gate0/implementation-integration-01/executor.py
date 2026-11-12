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
TERMINAL_STATES = ('STOPPED', 'TIMED_OUT', 'UNKNOWN')


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
        return True

    # -- G5: the custody of the started children --------------------------
    def spawn(self, command):
        """Start one child and take the custody of its original handle.

        The custody is taken immediately.  A failure of the registration or
        of the watchdog setup never loses the handle: the child is still
        stopped by this executor and the cleanup still runs.
        """
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   bufsize=0, cwd=str(self.guard_root))
        entry = self._take_custody(process)
        try:
            self._ensure_watchdog()
        except BaseException:
            # The watchdog could not be armed.  The handle is still owned.
            self._stop_child(entry)
            raise
        return process

    def _take_custody(self, process):
        pid = getattr(process, 'pid', None)
        entry = {'index': None, 'process': process, 'pid': pid,
                 'birth': process_birth(pid), 'started': self.clock(),
                 'state': 'STARTED', 'exit_code': None, 'timed_out': False,
                 'proven': False}
        with self._lock:
            index = self._pending.pop(0) if self._pending else None
            entry['index'] = index
            self.children.append(entry)
        if index is not None:
            try:
                self.counter.mark_started(index, pid=pid, birth=entry['birth'])
            except CpuGateError:
                entry['state'] = 'UNKNOWN'
                self.uncertain = True
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
        child budget, the cleanup included, stays inside the seal.
        """
        limit = float(self.limits['per_process_seconds'])
        margin = float(self.limits['per_child_termination_margin_seconds'])
        stop_at = max(0.0, limit - margin)
        while not self._stop.wait(0.02):
            with self._lock:
                children = list(self.children)
            for entry in children:
                if entry['state'] != 'STARTED':
                    continue
                if self.clock() - entry['started'] <= stop_at:
                    continue
                entry['timed_out'] = True
                self._stop_child(entry)

    def _stop_child(self, entry, session_deadline=None):
        """Stop one owned child with a bounded cleanup.

        The termination and the waits are clipped to the remaining per child
        budget *and* to the remaining session deadline.  The child is
        stopped here, not only by the watchdog: a young child must not
        survive the finalizer.
        """
        process = entry['process']
        budget = float(self.limits['per_child_kill_seconds'])
        if session_deadline is not None:
            budget = max(0.0, min(budget, session_deadline - self.clock()))
        try:
            process.terminate()
        except Exception:  # noqa: BLE001 - the failure stays visible
            pass
        try:
            process.wait(timeout=budget)
        except Exception:  # noqa: BLE001 - the failure stays visible
            try:
                process.kill()
            except Exception:  # noqa: BLE001 - the failure stays visible
                pass
            try:
                process.wait(timeout=budget)
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
            remaining = max(0.0, deadline - self.clock())
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
                           'birth': entry['birth'], 'proven': proven})
            if entry['index'] is not None:
                try:
                    self.counter.finish(entry['index'], state=entry['state'],
                                        exit_code=exit_code, spent=spent,
                                        pid=entry['pid'], birth=entry['birth'])
                except CpuGateError:
                    entry['state'] = 'UNKNOWN'
                    self.uncertain = True
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
        try:
            settled = self.counter.settle_session(self.session_id, spent=spent)
        except CpuGateError:
            return None
        return spent if settled else None

    def session_evidence(self):
        try:
            counter = self.counter.snapshot()
        except CpuGateError as error:
            counter = {'status': 'UNAVAILABLE', 'code': error.code}
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
    }
    for key in ('max_total_starts', 'max_concurrent', 'per_process_seconds',
                'shared_pool_seconds', 'session_wall_cap_seconds',
                'cleanup_reserve_seconds', 'per_child_termination_margin_seconds',
                'per_child_kill_seconds'):
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
