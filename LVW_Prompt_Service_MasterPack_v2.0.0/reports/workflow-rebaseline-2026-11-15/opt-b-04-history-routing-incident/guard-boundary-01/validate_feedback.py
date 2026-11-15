"""Trusted outer result gate. Run after the guarded child has terminated.

Inputs: frozen plan, guard receipt, runner receipt, NEW outer decision path.
No candidate import; never treats product/Stage acceptance as established.
"""
import hashlib
import json
import sys
from pathlib import Path

errors = []
decision = {'kind': 'CPU_FEEDBACK_VALIDATION_NOT_PRODUCT_ACCEPTANCE',
            'stage_pass_claim': False, 'accepted_cpu_feedback': False}
plan_path, guard_path, runner_path, output = map(Path, sys.argv[1:])
if output.exists():
    raise RuntimeError('OUTER_DECISION_ALREADY_EXISTS')
try:
    plan = json.loads(plan_path.read_text())
    guard = json.loads(guard_path.read_text())
    decision['plan_sha256'] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    decision['guard_sha256'] = hashlib.sha256(guard_path.read_bytes()).hexdigest()
    # Do not consult success claims before applying this independent hard veto.
    denials = guard.get('runtime_denials')
    if not isinstance(denials, list):
        raise RuntimeError('GUARD_DENIAL_LEDGER_MISSING_OR_INVALID')
    if denials:
        raise RuntimeError('GUARD_RUNTIME_DENIALS_NONEMPTY')
    if guard.get('clean_runtime_denial_ledger') is not True:
        errors.append('GUARD_CLEAN_LEDGER_NOT_TRUE')
    expected_denials = {'subprocess.Popen', 'socket.__new__', 'os.fork', 'os.exec',
                       'os.system', 'sqlite3.connect', 'ctypes.dlopen', 'ctypes.dlsym'}
    if set(guard.get('selftest_denials', [])) != expected_denials:
        errors.append('GUARD_SELFTEST_SET_MISMATCH')
    if guard.get('preload_window_final_state') != 'CLOSED' or guard.get('preload_events') != [
            {'event': 'ctypes.dlopen', 'name': None}]:
        errors.append('PRELOAD_NOT_EXACTLY_ONCE_AND_CLOSED')
    if Path(guard.get('write_root', '')).resolve() != Path(plan['report_dir']).resolve():
        errors.append('WRITE_ROOT_MISMATCH')
    runner = json.loads(runner_path.read_text())
    decision['runner_sha256'] = hashlib.sha256(runner_path.read_bytes()).hexdigest()
    selected = plan['nodeids']
    if runner.get('selected') != selected or runner.get('collected') != selected:
        errors.append('FIXED_NODE_ORDER_MISMATCH')
    reports = runner.get('reports', [])
    calls = [r for r in reports if r.get('when') == 'call']
    if [r.get('nodeid') for r in calls] != selected:
        errors.append('REQUIRED_CALLS_MISSING_DUPLICATED_OR_REORDERED')
    failures = [r for r in reports if r.get('outcome') != 'passed']
    if failures or runner.get('pytest_exit') != 0:
        errors.append('ACTUAL_CHECKS_NOT_ALL_PASSED')
    if runner.get('cleanup_proven_for_batch') is not True:
        errors.append('BATCH_CLEANUP_NOT_PROVEN')
    original = plan['full189_nodeids']
    supplemental = plan['supplemental_nodeids']
    decision['groups'] = {label: {
        'required': len(nodes),
        'passed': sum(r.get('outcome') == 'passed' and r.get('nodeid') in nodes for r in calls),
    } for label, nodes in [('original189', original), ('supplemental', supplemental)]}
    decision['accepted_cpu_feedback'] = not errors
except Exception as error:
    errors.append(str(error))
finally:
    decision['errors'] = errors
    output.write_text(json.dumps(decision, indent=2) + '\n')
    print(json.dumps(decision))
raise SystemExit(0 if decision['accepted_cpu_feedback'] else 1)
