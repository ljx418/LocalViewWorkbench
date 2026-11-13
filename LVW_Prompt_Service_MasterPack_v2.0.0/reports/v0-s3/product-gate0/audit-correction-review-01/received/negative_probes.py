"""Read-only candidate diagnostics; synthetic counters only; no subprocess/network."""
import sys

# Install an independent, unconditional boundary before any candidate import.
def boundary(event, args):
    if event.startswith('socket.') or event in (
        'subprocess.Popen', 'os.system', 'os.exec', 'os.spawn',
        'os.posix_spawn', 'os.fork', 'os.forkpty'):
        raise RuntimeError('independent diagnostic boundary: ' + event)

sys.addaudithook(boundary)
import importlib.util
import json
import os
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACK = OUT.parents[3]
sys.path.insert(0, str(PACK))
from tools import test_v0_s3_supervisor as t

e = t.EXECUTOR_MODULE
r = t.RUNNER_MODULE
results = {}

def probe(kind):
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=OUT) as directory:
        root = Path(directory)
        counter = t.fake_root_counter(root)
        _, digest, _ = t.fake_root_binding(root, counter_path=counter)
        executor = t.build_test_executor(root, counter_path=counter, binding_digest=digest)
        t.context_inside(root)
        command = t.executor_prefix() + ['clean_terminal']
        error = RuntimeError('ordinary exception with copied attributes')
        error.lvw_before_fork = True
        error.gate_error = e.CpuGateError('COPIED_GATE_ERROR')
        if kind == 'marker_only':
            error.gate_error = ValueError('wrong nested type')
        if kind == 'stale_guard_error':
            error = r.OfflineBoundaryViolation('unrelated prior refusal', before_fork=True,
                gate_error=e.CpuGateError('OLD_REFUSAL'))
        if kind == 'failed_finish':
            error = r.OfflineBoundaryViolation('synthetic refusal', before_fork=True,
                gate_error=e.CpuGateError('REFUSAL'))

        class FakePopen:
            PIPE = t._subprocess.PIPE

            @staticmethod
            def Popen(argv, **kwargs):
                executor.admit((sys.executable, list(argv), str(root), None))
                if kind == 'failed_finish':
                    def fail(*args, **kwargs):
                        raise e.CpuGateError('CPU_COUNTER_UNREADABLE')
                    executor.counter.finish = fail
                raise error

        original = e.subprocess
        e.subprocess = FakePopen
        try:
            try:
                executor.spawn(command)
            except BaseException as caught:
                assert caught is error
        finally:
            e.subprocess = original
        proofs = executor.reap()
        owned = root / 'owned'
        owned.mkdir()
        outcome = r.finalize_session(executor=executor, owned=owned,
            stdout_handle=t.GoodHandle(), stderr_handle=t.GoodHandle(),
            saved_out=os.dup(1), saved_err=os.dup(2), source_hasher=lambda: {})
        doc = json.loads(counter.read_text())
        return {'counter_state': doc['charges'][0]['state'],
            'occupied': executor.counter._occupied(doc), 'uncertain': executor.uncertain,
            'open_charges': executor.unsettled_charges(), 'ledger': executor.charge_ledger(),
            'proofs': proofs, 'cleanup_proven': outcome['cleanup_proven'],
            'finalizer_exit': outcome['exit_code'], 'owned_exists': owned.exists()}

for kind in ['marker_only', 'wrong_outer_class', 'stale_guard_error', 'failed_finish']:
    results[kind] = probe(kind)

# Fault injection at the documented hook registration API.  The outer boundary
# remains installed, and no blocked event is exercised with a weakened guard.
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
    try:
        r.install_offline_guard()
    except RuntimeError:
        pass
    second_return = r.install_offline_guard()
    results['installation_failure'] = {'api_calls': calls,
        'reported_installed': fresh.hook_installed, 'reported_count': fresh.hook_install_count,
        'retry_return': second_return}
finally:
    sys.addaudithook = original_add
    sys.modules[r.GUARD_REGISTRY_MODULE] = old_registry

# CPython also silently suppresses addaudithook when an existing audit hook
# raises RuntimeError.  Exercise the real API, still behind our outer boundary.
def reject_new_hook(event, args):
    if event == 'sys.addaudithook':
        raise RuntimeError('existing policy rejects additional hooks')
sys.addaudithook(reject_new_hook)
fresh = r._GuardRegistry()
sys.modules[r.GUARD_REGISTRY_MODULE] = fresh
seen = []
original_hook = r._audit_hook
def observed_hook(event, args):
    if event == 'lvw.independent.install.probe':
        seen.append(event)
    return original_hook(event, args)
r._audit_hook = observed_hook
try:
    owner = r.install_offline_guard()
    sys.audit('lvw.independent.install.probe')
    results['real_api_silent_rejection'] = {'reported_installed': fresh.hook_installed,
        'reported_count': fresh.hook_install_count, 'owner_returned': bool(owner),
        'probe_seen': seen}
finally:
    r._audit_hook = original_hook
    sys.modules[r.GUARD_REGISTRY_MODULE] = old_registry

print(json.dumps(results, indent=2, sort_keys=True))
assert results['marker_only']['counter_state'] == 'UNKNOWN'
assert results['wrong_outer_class']['counter_state'] == 'REFUSED_BEFORE_FORK'
assert results['stale_guard_error']['counter_state'] == 'REFUSED_BEFORE_FORK'
assert results['failed_finish']['counter_state'] == 'PENDING'
assert results['failed_finish']['cleanup_proven'] is True
assert results['installation_failure']['api_calls'] == ['_audit_hook']
