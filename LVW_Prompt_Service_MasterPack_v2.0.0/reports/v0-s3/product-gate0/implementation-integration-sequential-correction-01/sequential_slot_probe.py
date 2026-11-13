#!/usr/bin/env python3
"""Zero process probe of the sequential concurrency slot of the finite CPU executor.

The probe drives the **real** executor API of the S3-P4 batch against a
synthetic temporary counter and fake child handles.  It starts no process, it
opens no socket, it never reads and never writes the root counter of the
batch and it never touches the fixture of the batch.

The independent boundary of this probe is installed **before** the first
candidate import.  The offline guard of the candidate runner is installed
right after that boundary and before the executor module is imported, so no
candidate code of this batch ever runs outside a guarded process.

The probe exists because the finding of the root about the sequential reuse
of the concurrency slot has to be *confirmed* and not assumed: the same
probe is run against the baseline executor of the candidate 7ed2116 and
against the corrected executor, and the two receipts are compared.

Usage::

    python3 -B sequential_slot_probe.py --executor <executor.py> --out <receipt.json>
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

DENIED_EVENTS = ('subprocess.Popen', 'os.system', 'os.exec', 'os.spawn',
                 'os.posix_spawn', 'os.fork', 'os.forkpty')


def find_pack_root(start):
    """The package root is the directory that holds ``tools`` and ``reports``."""
    for candidate in [start] + list(start.parents):
        if (candidate / 'tools').is_dir() and (candidate / 'reports').is_dir():
            return candidate
    raise SystemExit('PACK_ROOT_NOT_FOUND')


def find_repository_root(start):
    """The repository root is the directory that holds the git metadata."""
    for candidate in [start] + list(start.parents):
        if (candidate / '.git').exists():
            return candidate
    raise SystemExit('REPOSITORY_ROOT_NOT_FOUND')


PACK_ROOT = find_pack_root(Path(__file__).resolve().parent)
REPOSITORY_ROOT = find_repository_root(PACK_ROOT)
RUNNER_RELATIVE = ('reports/v0-s3/product-gate0/implementation-integration-01/'
                    'run_guarded_checks.py')


def install_independent_boundary():
    """Deny every process and every network event of this process.

    The boundary is the first thing that this process does: it is installed
    before the first candidate import, so no candidate code of this batch can
    open a socket or start a host process.
    """
    denials = []

    def hook(event, arguments):
        if event.startswith('socket.') and event != 'socket.__new__':
            denials.append(event)
            raise RuntimeError('PROBE_BOUNDARY_DENIAL:' + event)
        if event in DENIED_EVENTS:
            denials.append(event)
            raise RuntimeError('PROBE_BOUNDARY_DENIAL:' + event)

    sys.addaudithook(hook)
    return denials


class FakeChild:
    """A fake child handle: no process, only the four calls of a handle.

    The handle is the *original* handle of the child from the point of view
    of the executor.  ``poll`` reports the exit of the child when it is set
    and it reports ``None`` while the child is alive.
    """

    def __init__(self, pid=4242):
        self.pid = pid
        self.returncode = None
        self.terminated = False
        self.killed = False
        self.waits = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.waits += 1
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


class UnprovableChild(FakeChild):
    """A handle whose exit can never be proven by a poll."""

    def poll(self):
        raise OSError('the exit of this child cannot be observed')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_synthetic(module, workdir, *, max_concurrent=2, budget_id='probe-budget'):
    """A synthetic counter and a synthetic binding in a temporary directory."""
    counter_path = workdir / 'counter.json'
    counter_path.write_text(json.dumps({
        'kind': 'lvw.s3-cpu-budget/1', 'budget_id': budget_id,
        'starts_total': 0,
        'starts_by_role': {'implementation': 0, 'independent_review': 0},
        'spent_wall_seconds': 0.0, 'reserved_wall_seconds': 0.0,
        'active': True, 'charges': [], 'sessions': []}, sort_keys=True))
    fixture = PACK_ROOT / 'tools/fixtures/v0_s3_supervisor_fixture.py'
    prefix = [sys.executable, '-I', '-S', '-B', str(fixture), '--scenario']
    supervisor = PACK_ROOT / 'tools/v0_s3_supervisor.py'
    binding = {
        'kind': 'S3_INTEGRATION_MACHINE_BINDING/1',
        'execution_permitted': True,
        'candidate_sha': module.resolve_head_commit(REPOSITORY_ROOT),
        'python': {'path': sys.executable,
                   'sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()},
        'argv_prefix': prefix,
        'allowed_scenarios': ['clean_terminal'],
        'source_pins': {'tools/v0_s3_supervisor.py':
                        hashlib.sha256(supervisor.read_bytes()).hexdigest()},
        'cpu_budget': {
            'counter_path': str(counter_path), 'budget_id': budget_id,
            'max_total_starts': 24,
            'max_starts_by_role': {'implementation': 16, 'independent_review': 8},
            'max_concurrent': max_concurrent, 'per_process_seconds': 10,
            'shared_pool_seconds': 180, 'session_wall_cap_seconds': 60,
            'cleanup_reserve_seconds': 30,
            'per_child_termination_margin_seconds': 2,
            'per_child_kill_seconds': 1, 'per_child_stop_attempts': 3}}
    binding_path = workdir / 'binding.json'
    binding_path.write_text(json.dumps(binding, sort_keys=True))
    digest = hashlib.sha256(binding_path.read_bytes()).hexdigest()
    return counter_path, binding_path, digest, prefix


def build_executor(module, workdir, **kwargs):
    """The real executor of the batch, bound to a synthetic counter."""
    counter_path, binding_path, digest, prefix = build_synthetic(module, workdir, **kwargs)
    context = workdir / 'fixture-context.json'
    context.write_text(json.dumps({'run_id': 'probe'}))
    os.environ['LVW_S3_FIXTURE_CONTEXT'] = str(context)
    executor = module.build_executor(
        binding_path=str(binding_path), binding_sha256=digest,
        role='implementation', repository_root=REPOSITORY_ROOT,
        package_root=PACK_ROOT, guard_root=workdir,
        session_id='session-sequential-probe')
    return executor, counter_path, prefix


def admit(executor, module, prefix, scenario='clean_terminal'):
    """One admission of the real API.  The refusal is the observation."""
    argv = list(prefix) + [scenario]
    try:
        executor.admit((prefix[0], argv, None, None))
    except module.CpuGateError as error:
        return {'accepted': False, 'code': error.code}
    return {'accepted': True, 'code': None}


def occupancy(module, counter_path):
    document = json.loads(counter_path.read_text())
    return module.SharedCounter._occupied(document)


def counter_view(module, counter_path):
    document = json.loads(counter_path.read_text())
    return {'starts_total': document['starts_total'],
            'starts_by_role': document['starts_by_role'],
            'occupied': module.SharedCounter._occupied(document),
            'charges': [{'index': record.get('index'),
                         'scenario': record.get('scenario'),
                         'state': record.get('state'),
                         'settled': record.get('settled'),
                         'exit_code': record.get('exit_code'),
                         'observed_lifetime_seconds': record.get('observed_lifetime_seconds')}
                        for record in document['charges']]}


def sequence_two_exited_then_third(module):
    """Two children that already exited, then the third admission."""
    with tempfile.TemporaryDirectory(prefix='probe-two-exited-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        first = FakeChild()
        admit(executor, module, prefix)
        executor.register(first)
        second = FakeChild()
        admit(executor, module, prefix)
        executor.register(second)
        # Both children are gone: their original handles report the exit.
        first.returncode = 0
        second.returncode = 0
        third = admit(executor, module, prefix)
        return {'name': 'two_exited_then_third',
                'third_admission': third,
                'counter': counter_view(module, counter_path)}


def sequence_two_live_then_one_released(module):
    """Two children that are still alive, then one of them is released."""
    with tempfile.TemporaryDirectory(prefix='probe-two-live-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        first = FakeChild()
        admit(executor, module, prefix)
        executor.register(first)
        second = FakeChild()
        admit(executor, module, prefix)
        executor.register(second)
        third = admit(executor, module, prefix)
        # Exactly one of the two live children is gone.
        first.returncode = 0
        fourth = admit(executor, module, prefix)
        fifth = admit(executor, module, prefix)
        return {'name': 'two_live_then_one_released',
                'third_admission_while_two_live': third,
                'fourth_admission_after_one_release': fourth,
                'fifth_admission_after_one_release': fifth,
                'counter': counter_view(module, counter_path)}


def sequence_thirteen_sequential(module):
    """Thirteen sequential children: the peak occupancy stays bounded."""
    with tempfile.TemporaryDirectory(prefix='probe-thirteen-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        peak = 0
        refusals = []
        accepted = 0
        for position in range(13):
            result = admit(executor, module, prefix)
            if not result['accepted']:
                refusals.append({'position': position, 'code': result['code']})
                break
            accepted += 1
            child = FakeChild()
            executor.register(child)
            # The child of this position is gone before the next admission.
            child.returncode = 0
            peak = max(peak, occupancy(module, counter_path))
        return {'name': 'thirteen_sequential',
                'accepted_admissions': accepted,
                'peak_occupied': peak,
                'refusals': refusals,
                'counter': counter_view(module, counter_path)}


def sequence_unprovable_exit_keeps_the_slot(module):
    """A child whose exit can never be proven keeps its concurrency slot."""
    with tempfile.TemporaryDirectory(prefix='probe-unprovable-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        # The first child can never prove its exit: it holds its slot.
        admit(executor, module, prefix)
        executor.register(UnprovableChild())
        # The second child exited: it may release its slot.
        admit(executor, module, prefix)
        second = FakeChild()
        executor.register(second)
        second.returncode = 0
        third = admit(executor, module, prefix)
        fourth = admit(executor, module, prefix)
        document = json.loads(counter_path.read_text())
        return {'name': 'unprovable_exit_keeps_the_slot',
                'third_admission': third,
                'fourth_admission': fourth,
                'unprovable_charge_settled': document['charges'][0].get('settled'),
                'unprovable_charge_state': document['charges'][0].get('state'),
                'counter': counter_view(module, counter_path)}


def sequence_unpersisted_settlement_keeps_the_slot(module):
    """A settlement that the counter does not accept keeps the slot."""
    with tempfile.TemporaryDirectory(prefix='probe-unpersisted-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        child = FakeChild()
        admit(executor, module, prefix)
        executor.register(child)
        child.returncode = 0
        original = executor.counter.finish

        def refuse(index, **keywords):
            return False

        executor.counter.finish = refuse
        second = admit(executor, module, prefix)
        third = admit(executor, module, prefix)
        executor.counter.finish = original
        document = json.loads(counter_path.read_text())
        return {'name': 'unpersisted_settlement_keeps_the_slot',
                'second_admission': second,
                'third_admission': third,
                'charge_settled': document['charges'][0].get('settled'),
                'charge_state': document['charges'][0].get('state'),
                'counter': counter_view(module, counter_path)}


def sequence_finalizer_is_idempotent(module):
    """The finalizer never double settles a child that is already settled."""
    with tempfile.TemporaryDirectory(prefix='probe-finalizer-') as name:
        workdir = Path(name)
        executor, counter_path, prefix = build_executor(module, workdir)
        first = FakeChild()
        admit(executor, module, prefix)
        executor.register(first)
        first.returncode = 0
        second = admit(executor, module, prefix)
        if second['accepted']:
            follower = FakeChild()
            executor.register(follower)
            follower.returncode = 0
        before = json.loads(counter_path.read_text())['charges']
        executor.reap()
        after = json.loads(counter_path.read_text())['charges']
        unsettled = executor.unsettled_charges()
        return {'name': 'finalizer_is_idempotent',
                'second_admission': second,
                'charge_before_reap': before,
                'charge_after_reap': after,
                'uncertain_after_reap': executor.uncertain,
                'unsettled_after_reap': unsettled,
                'settlement_failures': executor.session_evidence()['settlement_failures']}


SEQUENCES = (sequence_two_exited_then_third,
             sequence_two_live_then_one_released,
             sequence_thirteen_sequential,
             sequence_unprovable_exit_keeps_the_slot,
             sequence_unpersisted_settlement_keeps_the_slot,
             sequence_finalizer_is_idempotent)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--executor', required=True,
                        help='the executor.py that this probe drives')
    parser.add_argument('--out', required=True,
                        help='the receipt of this probe')
    parser.add_argument('--label', default='sequential-slot-probe')
    arguments = parser.parse_args(argv)

    denials = install_independent_boundary()
    # The offline guard of the candidate runner is installed before the
    # executor module is imported: no candidate code of this batch runs
    # outside the guarded process.
    runner = load_module(PACK_ROOT / RUNNER_RELATIVE, 'lvw_s3_guarded_runner_probe')
    guard_owner = runner.install_offline_guard()
    executor_path = Path(arguments.executor).resolve()
    module = load_module(executor_path, 'lvw_s3_finite_cpu_executor_probe')

    results = []
    for sequence in SEQUENCES:
        try:
            results.append(sequence(module))
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            results.append({'name': sequence.__name__, 'error': repr(error)})

    receipt = {
        'kind': 'LVW_S3_SEQUENTIAL_SLOT_ZERO_PROCESS_PROBE/1',
        'label': arguments.label,
        'executor_path': str(executor_path),
        'executor_sha256': hashlib.sha256(executor_path.read_bytes()).hexdigest(),
        'repository_root': str(REPOSITORY_ROOT),
        'package_root': str(PACK_ROOT),
        'candidate_sha': module.resolve_head_commit(REPOSITORY_ROOT),
        'offline_guard_owner': guard_owner,
        'offline_guard_installed': bool(guard_owner),
        'boundary_denials': denials,
        'real_process_started': False,
        'root_counter_touched': False,
        'sequences': results}
    out = Path(arguments.out)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    sys.stdout.write(json.dumps({'label': arguments.label,
                                 'executor_sha256': receipt['executor_sha256'],
                                 'sequences': [item.get('name') for item in results]},
                                indent=2) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
