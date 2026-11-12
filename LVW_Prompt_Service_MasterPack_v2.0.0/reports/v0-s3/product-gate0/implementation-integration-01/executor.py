"""The independent finite CPU executor of the S3 integration batch.

This executor is the custody of the finite fixture process plan.  It is
*not* the supervisor that is under test: it is the outer, independent guard
of the process budget, of the source identity and of the wall clock.

Four properties are enforced here and nowhere else:

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
    session admission bound with a cleanup only reserve.  The reaper has its
    own deadline and records the raw exit proof of every child.  An
    uncertain exit keeps the reservation.

G4  The argv, the scenario, the working directory and the bounded context
    document are exactly the sealed plan.  The context document lives in the
    fresh runner owned root; no arbitrary private path is accepted.

The executor never downloads, never opens a socket, never starts a service
and never touches the original product ledger.
"""
import errno
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

COUNTER_SCHEMA = 'lvw.s3-cpu-budget/1'
BINDING_SCHEMA = 'S3_INTEGRATION_MACHINE_BINDING/1'
ROLES = ('implementation', 'independent_review')
CONTEXT_ENVIRONMENT_VARIABLE = 'LVW_S3_FIXTURE_CONTEXT'
GUARD_ROOT_ENVIRONMENT_VARIABLE = 'LVW_S3_GUARD_ROOT'


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
                or not isinstance(document.get('charges'), list)):
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
    def _active(document):
        return sum(1 for record in document['charges'] if record.get('state') == 'STARTED')

    def charge(self, *, role, scenario, argv):
        """Charge one start atomically, before the operating system action."""
        if role not in ROLES:
            raise CpuGateError('CPU_ROLE_INVALID')
        with self._open() as handle:
            document = self._read(handle)
            if document.get('budget_id') != self.budget_id:
                raise CpuGateError('CPU_COUNTER_IDENTITY_MISMATCH')
            limits = self.limits
            if self._active(document) >= limits['max_concurrent']:
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
                'state': 'STARTED',
                'exit_code': None,
                'pid': None,
                'birth': None,
                'finished_wall': None,
                'spent_wall_seconds': None,
            }
            document['charges'].append(record)
            document['starts_total'] += 1
            by_role[role] = by_role.get(role, 0) + 1
            document['starts_by_role'] = by_role
            self._write(handle, document)
            return record['index']

    def finish(self, index, *, state, exit_code, spent, pid=None, birth=None):
        """Close one charge.  A charge is never removed and never refunded."""
        with self._open() as handle:
            document = self._read(handle)
            for record in document['charges']:
                if record.get('index') == index:
                    record['state'] = state
                    record['exit_code'] = exit_code
                    record['pid'] = pid
                    record['birth'] = birth
                    record['finished_wall'] = time.time()
                    record['spent_wall_seconds'] = spent
                    break
            document['spent_wall_seconds'] = round(
                float(document.get('spent_wall_seconds', 0.0)) + float(spent), 3)
            self._write(handle, document)

    def snapshot(self):
        with self._open() as handle:
            document = self._read(handle)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return document


class FiniteCpuExecutor:
    """The outer, independent guard of the finite fixture process plan."""

    def __init__(self, *, binding_path, binding_sha256, counter, role, python, pins,
                 candidate_sha, repository_root, package_root, guard_root, clock=None):
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
        self.session_started = self.clock()
        self.limits = counter.limits
        self.children = []
        self.refusals = []
        self._lock = threading.Lock()
        self._watchdog = None
        self._stop = threading.Event()

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
        elapsed = self.clock() - self.session_started
        if elapsed > self.limits['session_admission_seconds']:
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
            self._pending = getattr(self, '_pending', [])
            self._pending.append(index)
        return True

    # -- the custody of the started children ------------------------------
    def spawn(self, command):
        """Start one child and take the custody of its original handle."""
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   bufsize=0, cwd=str(self.guard_root))
        self.register(process)
        return process

    def register(self, process):
        with self._lock:
            pending = getattr(self, '_pending', [])
            index = pending.pop(0) if pending else None
            self.children.append({'index': index, 'process': process,
                                  'started': self.clock(), 'state': 'STARTED',
                                  'exit_code': None, 'timed_out': False})
        self._ensure_watchdog()
        return index

    def _ensure_watchdog(self):
        if self._watchdog is not None:
            return
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def _watch(self):
        """The independent per child deadline of the executor."""
        limit = self.limits['per_process_seconds']
        while not self._stop.wait(0.02):
            with self._lock:
                children = list(self.children)
            for entry in children:
                if entry['state'] != 'STARTED':
                    continue
                if self.clock() - entry['started'] <= limit:
                    continue
                entry['timed_out'] = True
                process = entry['process']
                try:
                    process.terminate()
                except Exception:  # noqa: BLE001 - the failure stays visible
                    pass
                try:
                    process.wait(timeout=1.0)
                except Exception:  # noqa: BLE001 - the failure stays visible
                    try:
                        process.kill()
                    except Exception:  # noqa: BLE001 - the failure stays visible
                        pass

    def reap(self):
        """The bounded reaper of the executor with its own deadline."""
        deadline = self.session_started + self.limits['session_cleanup_seconds']
        proofs = []
        with self._lock:
            children = list(self.children)
        for entry in children:
            process = entry['process']
            remaining = max(0.0, deadline - self.clock())
            exit_code = None
            proven = False
            try:
                exit_code = process.wait(timeout=min(remaining, 5.0))
                proven = True
            except Exception:  # noqa: BLE001 - the failure stays visible
                exit_code = None
            entry['exit_code'] = exit_code
            spent = round(self.clock() - entry['started'], 3)
            if not proven:
                entry['state'] = 'UNKNOWN'
            elif entry['timed_out']:
                entry['state'] = 'TIMED_OUT'
            else:
                entry['state'] = 'STOPPED'
            proofs.append({'index': entry['index'], 'state': entry['state'],
                           'exit_code': exit_code, 'spent_wall_seconds': spent,
                           'timed_out': entry['timed_out'],
                           'pid': getattr(process, 'pid', None)})
            if entry['index'] is not None:
                try:
                    self.counter.finish(entry['index'], state=entry['state'],
                                        exit_code=exit_code, spent=spent,
                                        pid=getattr(process, 'pid', None))
                except CpuGateError:
                    entry['state'] = 'UNKNOWN'
        self._stop.set()
        return proofs

    def session_evidence(self):
        try:
            counter = self.counter.snapshot()
        except CpuGateError as error:
            counter = {'status': 'UNAVAILABLE', 'code': error.code}
        return {
            'kind': 'lvw.s3-finite-cpu-session/1',
            'role': self.role,
            'binding_path': str(self.binding_path),
            'binding_sha256': self.binding_sha256,
            'candidate_sha': self.candidate_sha,
            'counter_path': str(self.counter.path),
            'counter_budget_id': self.counter.budget_id,
            'starts_total': counter.get('starts_total') if isinstance(counter, dict) else None,
            'starts_by_role': counter.get('starts_by_role') if isinstance(counter, dict) else None,
            'spent_wall_seconds': counter.get('spent_wall_seconds') if isinstance(counter, dict) else None,
            'counter': counter,
            'children': [{'index': entry['index'], 'state': entry['state'],
                          'exit_code': entry['exit_code'],
                          'timed_out': entry['timed_out'],
                          'pid': getattr(entry['process'], 'pid', None)}
                         for entry in self.children],
            'refusals': list(self.refusals),
            'stage_pass_claim': False,
            'product_gate0': False,
        }


def build_executor(*, binding_path, binding_sha256, role, repository_root, package_root,
                   guard_root):
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
        'session_admission_seconds': budget.get('session_admission_seconds'),
        'session_cleanup_seconds': budget.get('session_cleanup_seconds'),
    }
    for key in ('max_total_starts', 'max_concurrent', 'per_process_seconds',
                'session_admission_seconds', 'session_cleanup_seconds'):
        if type(limits[key]) is not int or limits[key] <= 0:
            raise CpuGateError('BINDING_CPU_BUDGET_INVALID:' + key)
    if not isinstance(limits['max_starts_by_role'], dict):
        raise CpuGateError('BINDING_CPU_BUDGET_INVALID:max_starts_by_role')
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
                              guard_root=guard_root)
