"""The converted negative probes of the audit correction 02.

This script is the starting point of the independent review of the candidate
``74ff021934afef661f8c7e8c1c4f11b26f7c3360`` (``negative_probes.py`` of the
review), with the oracles converted and the four directed production path
cases of the adopted findings added.

The conversion of the oracles is the point of this script.  The old script
reproduced the defects and called the reproduction a success: it asserted
that a copied marker released the slot of a charge, that a stale refusal
released the slot of a charge, that a failed settlement still produced a
proven cleanup, that a registration that raised still promised an installed
guard and that a registration that CPython silently suppressed still
promised an installed guard.  Every one of these oracles is now inverted:
the defect must be *rejected* and it must never be green.  The original
trigger conditions are kept: they are not deleted and they are not weakened.

The boundary of this script is installed before any candidate import.  It
refuses every socket event and every process creation, so no child, no
network and no host process can exist while the probes run.  Only temporary
synthetic counters are written; the real shared counter is never read and
never written.
"""
import sys


# The independent, unconditional boundary of this script.  It is installed
# before any candidate import, so no candidate module can reach the network
# or the operating system.
#
# CPython calls the audit hooks in the order of their addition, so this
# boundary is the *first* hook of the process.  It owns the network events
# and the process events that the guard of the runner does not own.  The
# process creation events are left to the guard of the runner, which is
# installed after this boundary and which refuses every one of them; this
# boundary refuses them too whenever that guard is not installed.
PROCESS_EVENTS = ('subprocess.Popen', 'os.system', 'os.exec', 'os.execv',
                  'os.spawn', 'os.posix_spawn', 'os.fork', 'os.forkpty')


def boundary(event, args):
    if event.startswith('socket.'):
        raise RuntimeError('probe boundary: ' + event)
    if event in PROCESS_EVENTS:
        registry = sys.modules.get('lvw_s3_offline_guard_registry')
        if getattr(registry, 'hook_installed', False):
            # The guard of the runner owns this event and it refuses every
            # process creation before the fork.
            return
        raise RuntimeError('probe boundary: ' + event)


sys.addaudithook(boundary)

import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

OUT = Path(__file__).resolve().parent
PACK = OUT.parents[3]
sys.path.insert(0, str(PACK))
from tools import test_v0_s3_supervisor as t  # noqa: E402

e = t.EXECUTOR_MODULE
r = t.RUNNER_MODULE
results = {}


def build(root):
    """A synthetic counter and a synthetic executor.  Nothing else."""
    counter = t.fake_root_counter(root)
    _, digest, _ = t.fake_root_binding(root, counter_path=counter)
    executor = t.build_test_executor(root, counter_path=counter, binding_digest=digest)
    t.context_inside(root)
    return counter, executor


def drive(root, executor, error, *, finish_error=None, admission=None):
    """Run one start whose operating system action fails with ``error``.

    ``admission`` is the callable that admits the start.  The default is the
    real guard of the runner: the real audit event of the start is raised
    and the real hook of the runner admits it.  The gate of the process
    wide registry carries the synthetic executor of this probe, and it is
    restored in every case.
    """
    command = t.executor_prefix() + ['clean_terminal']

    class FakePopen:
        PIPE = t._subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            if admission is None:
                sys.audit('subprocess.Popen', sys.executable, list(argv), str(root), None)
            else:
                admission(executor, argv, root)
            if finish_error is not None:
                def fail(*args, **kwargs):
                    raise e.CpuGateError(finish_error)
                executor.counter.finish = fail
            raise error

    original = e.subprocess
    e.subprocess = FakePopen
    gate = r.PROCESS_GATE
    original_executor = gate.get('executor')
    gate['executor'] = executor
    caught = None
    try:
        executor.spawn(command)
    except BaseException as error_caught:  # noqa: BLE001 - the probe records it
        caught = error_caught
    finally:
        e.subprocess = original
        gate['executor'] = original_executor
    return caught


def observe(counter, executor):
    """The state of the counter and of the ledger, without a reaper."""
    document = json.loads(counter.read_text())
    return {'charges': len(document['charges']),
            'states': [charge['state'] for charge in document['charges']],
            'settled': [charge['settled'] for charge in document['charges']],
            'occupied': executor.counter._occupied(document),
            'uncertain': executor.uncertain,
            'open_charges': executor.unsettled_charges(),
            'ledger': executor.charge_ledger()}


def state(root, counter, executor, caught=None):
    """The observable state of the executor after one failed start."""
    proofs = executor.reap()
    owned = root / 'owned'
    owned.mkdir()
    outcome = r.finalize_session(executor=executor, owned=owned,
                                 stdout_handle=t.GoodHandle(), stderr_handle=t.GoodHandle(),
                                 saved_out=os.dup(1), saved_err=os.dup(2),
                                 source_hasher=lambda: {})
    document = json.loads(counter.read_text())
    return {'counter_state': document['charges'][0]['state'],
            'counter_settled': document['charges'][0]['settled'],
            'occupied': executor.counter._occupied(document),
            'uncertain': executor.uncertain,
            'open_charges': executor.unsettled_charges(),
            'ledger': executor.charge_ledger(),
            'proofs': proofs,
            'cleanup_proven': outcome['cleanup_proven'],
            'finalizer_exit': outcome['exit_code'],
            'failure_reasons': outcome['failure_reasons'],
            'owned_exists': owned.exists(),
            'caught_type': type(caught).__name__ if caught is not None else None,
            'caught_credential': (getattr(caught, r.REFUSAL_CREDENTIAL, None) is not None
                                  if caught is not None else False)}


# ---------------------------------------------------------------------------
# The four cases of the review, with their oracles converted.
# ---------------------------------------------------------------------------
r.install_offline_guard()

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # 1. marker_only: the control of the review.  An ordinary error with a
    #    wrong nested type was already UNKNOWN and stays UNKNOWN.
    counter, executor = build(root)
    error = RuntimeError('ordinary exception with copied attributes')
    error.lvw_before_fork = True
    error.gate_error = ValueError('wrong nested type')
    caught = drive(root, executor, error)
    results['marker_only'] = state(root, counter, executor, caught)

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # 2. wrong_outer_class: the copied marker and the copied gate error.
    #    OLD ORACLE: REFUSED_BEFORE_FORK (the defect).
    #    NEW ORACLE: the slot is kept and the charge stays open.
    counter, executor = build(root)
    error = RuntimeError('ordinary exception with copied attributes')
    error.lvw_before_fork = True
    error.gate_error = e.CpuGateError('COPIED_GATE_ERROR')
    caught = drive(root, executor, error)
    results['wrong_outer_class'] = state(root, counter, executor, caught)

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # 3. stale_guard_error: a refusal of an earlier action.
    #    OLD ORACLE: REFUSED_BEFORE_FORK (the defect).
    #    NEW ORACLE: the slot is kept and the charge stays open.
    counter, executor = build(root)
    stale = r.OfflineBoundaryViolation('unrelated prior refusal', before_fork=True,
                                       gate_error=e.CpuGateError('OLD_REFUSAL'))
    caught = drive(root, executor, stale)
    results['stale_guard_error'] = state(root, counter, executor, caught)

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # 4. failed_finish: the settlement of the charge that the counter did
    #    not accept.
    #    OLD ORACLE: counter_state PENDING and cleanup_proven True (the
    #    defect: a charge that is still open was presented as a proven
    #    cleanup).
    #    NEW ORACLE: the charge stays open, the finalizer is not zero and
    #    the root is kept.
    counter, executor = build(root)
    error = r.OfflineBoundaryViolation('a refusal of the operating system action',
                                       before_fork=True,
                                       gate_error=e.CpuGateError('REFUSAL'))
    caught = drive(root, executor, error, finish_error='CPU_COUNTER_UNREADABLE')
    results['failed_finish'] = state(root, counter, executor, caught)

# ---------------------------------------------------------------------------
# The four directed production path cases of the adopted findings.
# ---------------------------------------------------------------------------
with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # M1 positive: the real guard of the runner refuses the process
    # creation inside the audit event of this very start.  The refusal
    # carries the one time credential of this action.
    counter, executor = build(root)
    command = t.executor_prefix() + ['clean_terminal']

    class RealGuardPopen:
        PIPE = t._subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(root), None)
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    original = e.subprocess
    e.subprocess = RealGuardPopen
    caught = None
    gate = r.PROCESS_GATE
    original_executor = gate.get('executor')
    gate['executor'] = executor
    try:
        executor.spawn(command)
    except BaseException as error_caught:  # noqa: BLE001 - the probe records it
        caught = error_caught
    finally:
        e.subprocess = original
        gate['executor'] = original_executor
    results['m1_real_guard_positive'] = state(root, counter, executor, caught)

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # M1 negative: the real refusal of an earlier action is replayed.  The
    # credential of that refusal is consumed and its nonce is not the nonce
    # of this action, so nothing is released.
    counter, executor = build(root)
    command = t.executor_prefix() + ['clean_terminal']
    replayed = None

    class RefusingPopen:
        PIPE = t._subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(root), None)
            sys.audit('os.posix_spawn', sys.executable, list(argv), None)

    original = e.subprocess
    e.subprocess = RefusingPopen
    gate = r.PROCESS_GATE
    original_executor = gate.get('executor')
    gate['executor'] = executor
    try:
        executor.spawn(command)
    except BaseException as error_caught:  # noqa: BLE001 - the probe records it
        replayed = error_caught
    finally:
        e.subprocess = original
        gate['executor'] = original_executor
    first = observe(counter, executor)

    class ReplayingPopen:
        PIPE = t._subprocess.PIPE

        @staticmethod
        def Popen(argv, **kwargs):
            sys.audit('subprocess.Popen', sys.executable, list(argv), str(root), None)
            raise replayed

    e.subprocess = ReplayingPopen
    gate['executor'] = executor
    try:
        executor.spawn(command)
    except BaseException:  # noqa: BLE001 - the probe records the state
        pass
    finally:
        e.subprocess = original
        gate['executor'] = original_executor
    results['m1_replay_negative'] = {'first_state': first,
                                     'replayed_credential_present':
                                         getattr(replayed, r.REFUSAL_CREDENTIAL, None) is not None,
                                     'second_state': observe(counter, executor)}

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # M2 positive: a settlement that the counter accepted is a real terminal
    # state of the charge.  The terminal state itself is UNKNOWN, because
    # the refusal of this case was not proven by the guard (M1), and an
    # unknown charge keeps its slot by design.
    counter, executor = build(root)
    error = r.OfflineBoundaryViolation('a refusal of the operating system action',
                                       before_fork=True,
                                       gate_error=e.CpuGateError('REFUSAL'))
    caught = drive(root, executor, error)
    results['m2_persisted_positive'] = state(root, counter, executor, caught)

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # M3 positive: the handshake of the owner proves that the hook of this
    # process is really active.
    registry = r.guard_registry()
    owner = r.install_offline_guard()
    before = registry.handshake_count
    sys.audit(r.GUARD_HANDSHAKE_EVENT, 'owner-of-another-process',
              registry.handshake_token)
    foreign = registry.handshake_count
    r.guard_handshake()
    results['m3_handshake_positive'] = {
        'owner_returned': bool(owner),
        'hook_installed': registry.hook_installed,
        'hook_install_count': registry.hook_install_count,
        'handshake_before': before,
        'handshake_after_foreign': foreign,
        'handshake_after_own': registry.handshake_count,
        'install_error': registry.install_error}

with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
    root = Path(directory)

    # m1 positive and negative: the receipt saves the complete effective
    # command, and the outer invocation of a programmatic call is reported
    # as such and never invented.
    arguments = type('Arguments', (), {
        'mode': 'focused', 'label': 'probe', 'select': 'refusal',
        'modules': 'tools/test_v0_s3_supervisor.py',
        'binding': '/sealed/binding.json', 'binding_sha256': 'a' * 64,
        'role': 'implementation', 'candidate_sha': 'b' * 40})()
    command = r.build_effective_command(arguments, str(OUT))
    invocation = r.invocation_evidence(command)
    results['m1_command_positive'] = {'command': command,
                                       'has_modules': '--modules' in command,
                                       'has_select': '--select' in command,
                                       'has_binding': '--binding' in command,
                                       'has_binding_sha': '--binding-sha256' in command,
                                       'has_role': '--role' in command,
                                       'has_candidate': '--candidate-sha' in command}
    results['m1_invocation_negative'] = {'invocation': invocation,
                                          'kind': invocation.get('kind')}

# ---------------------------------------------------------------------------
# The two installation failures of M3.  The explicit failure is a fault
# injection at the documented API.  The silent suppression uses the real
# ``sys.addaudithook`` and the real behaviour of CPython: an existing audit
# hook that raises on the ``sys.addaudithook`` event makes CPython skip the
# new hook without any error.
# ---------------------------------------------------------------------------
old_registry = sys.modules[r.GUARD_REGISTRY_MODULE]
fresh = r._GuardRegistry()
sys.modules[r.GUARD_REGISTRY_MODULE] = fresh
original_add = sys.addaudithook
calls = []


def failed_add(hook):
    calls.append(hook.__name__)
    raise RuntimeError('hook registration failure')


sys.addaudithook = failed_add
try:
    refusal = None
    try:
        r.install_offline_guard()
    except Exception as error_caught:  # noqa: BLE001 - the probe records it
        refusal = error_caught
    second_refusal = None
    try:
        r.install_offline_guard()
    except Exception as error_caught:  # noqa: BLE001 - the probe records it
        second_refusal = error_caught
    results['m3_registration_failure_negative'] = {
        'api_calls': calls,
        'reported_installed': fresh.hook_installed,
        'reported_count': fresh.hook_install_count,
        'install_error': fresh.install_error,
        'refused': refusal is not None,
        'refused_code': getattr(refusal, 'code', None),
        'second_call_refused': second_refusal is not None}
finally:
    sys.addaudithook = original_add
    sys.modules[r.GUARD_REGISTRY_MODULE] = old_registry


def reject_new_hook(event, args):
    if event == 'sys.addaudithook':
        raise RuntimeError('existing policy rejects additional hooks')


sys.addaudithook(reject_new_hook)
fresh = r._GuardRegistry()
sys.modules[r.GUARD_REGISTRY_MODULE] = fresh
try:
    refusal = None
    try:
        r.install_offline_guard()
    except Exception as error_caught:  # noqa: BLE001 - the probe records it
        refusal = error_caught
    results['m3_silent_rejection_negative'] = {
        'reported_installed': fresh.hook_installed,
        'reported_count': fresh.hook_install_count,
        'install_error': fresh.install_error,
        'refused': refusal is not None,
        'refused_code': getattr(refusal, 'code', None),
        'handshake_seen_by_the_new_registration': fresh.handshake_count}
finally:
    sys.modules[r.GUARD_REGISTRY_MODULE] = old_registry

print(json.dumps(results, indent=2, sort_keys=True))

# ---------------------------------------------------------------------------
# The converted oracles.  The defect of every case must be rejected and it
# must never be green.
# ---------------------------------------------------------------------------
assert results['marker_only']['counter_state'] == 'UNKNOWN'
assert results['marker_only']['occupied'] == 1

assert results['wrong_outer_class']['counter_state'] == 'UNKNOWN', \
    'a copied marker and a copied gate error must not release the slot'
assert results['wrong_outer_class']['occupied'] == 1
assert results['wrong_outer_class']['cleanup_proven'] is False
assert results['wrong_outer_class']['finalizer_exit'] != 0
assert results['wrong_outer_class']['owned_exists'] is True

assert results['stale_guard_error']['counter_state'] == 'UNKNOWN', \
    'a stale refusal must not release the slot'
assert results['stale_guard_error']['occupied'] == 1
assert results['stale_guard_error']['cleanup_proven'] is False
assert results['stale_guard_error']['owned_exists'] is True

assert results['failed_finish']['counter_state'] == 'PENDING', \
    'a charge that was not settled must stay pending'
assert results['failed_finish']['cleanup_proven'] is False, \
    'an open charge must never be presented as a proven cleanup'
assert results['failed_finish']['finalizer_exit'] != 0
assert results['failed_finish']['owned_exists'] is True
assert len(results['failed_finish']['open_charges']) >= 1

assert results['m1_real_guard_positive']['counter_state'] == 'REFUSED_BEFORE_FORK'
assert results['m1_real_guard_positive']['occupied'] == 0
assert results['m1_real_guard_positive']['caught_credential'] is True
assert results['m1_real_guard_positive']['cleanup_proven'] is True

assert results['m1_replay_negative']['second_state']['states'] == \
    ['REFUSED_BEFORE_FORK', 'UNKNOWN'], 'a replayed refusal must release nothing'
assert results['m1_replay_negative']['second_state']['occupied'] == 1
assert results['m1_replay_negative']['replayed_credential_present'] is True

assert results['m2_persisted_positive']['counter_state'] == 'UNKNOWN'
assert results['m2_persisted_positive']['counter_settled'] is True, \
    'a settlement that the counter accepted is a real terminal state'
assert results['m2_persisted_positive']['ledger'][0]['settlement_persisted'] is True
assert results['m2_persisted_positive']['occupied'] == 1, \
    'an unknown charge keeps its slot by design'

assert results['m3_handshake_positive']['owner_returned'] is True
assert results['m3_handshake_positive']['hook_installed'] is True
assert results['m3_handshake_positive']['handshake_after_own'] > \
    results['m3_handshake_positive']['handshake_after_foreign']
assert results['m3_handshake_positive']['handshake_after_foreign'] == \
    results['m3_handshake_positive']['handshake_before'], \
    'a handshake of a foreign owner must never be counted'

assert results['m3_registration_failure_negative']['api_calls'] == ['_audit_hook']
assert results['m3_registration_failure_negative']['refused'] is True
assert results['m3_registration_failure_negative']['reported_installed'] is False
assert results['m3_registration_failure_negative']['reported_count'] == 0
assert results['m3_registration_failure_negative']['second_call_refused'] is True

assert results['m3_silent_rejection_negative']['refused'] is True
assert results['m3_silent_rejection_negative']['reported_installed'] is False
assert results['m3_silent_rejection_negative']['reported_count'] == 0
assert results['m3_silent_rejection_negative']['handshake_seen_by_the_new_registration'] == 0

assert all(results['m1_command_positive'][key] is True
           for key in ('has_modules', 'has_select', 'has_binding', 'has_binding_sha',
                       'has_role', 'has_candidate'))
assert results['m1_invocation_negative']['kind'] in ('programmatic', 'UNKNOWN'), \
    'the outer invocation of a programmatic call must never be invented'

print('CONVERTED_ORACLES_OK')
