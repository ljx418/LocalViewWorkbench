"""Derive CPU counts and rejection causes from frozen machine artifacts.

PLAN RUNNER GUARD OUTER NEW_OUTPUT. No candidate import or test execution.
This receipt never grants a checkpoint, Stage, N2 or human acceptance.
"""
import collections
import datetime
import hashlib
import json
import sys
from pathlib import Path

plan_path, runner_path, guard_path, outer_path, output = map(Path, sys.argv[1:])
inputs = {}
values = []
for path in (plan_path, runner_path, guard_path, outer_path):
    data = path.read_bytes()
    values.append(json.loads(data))
    inputs[str(path)] = hashlib.sha256(data).hexdigest()
plan, runner, guard, outer = values
selected = plan['nodeids']
reports = runner['reports']
calls = [r for r in reports if r['when'] == 'call']
call_ids = [r['nodeid'] for r in calls]
counts = collections.Counter(call_ids)
by_node = collections.defaultdict(list)
for report in reports:
    by_node[report['nodeid']].append(report)


def group(nodes):
    result = dict(fixed=len(nodes), selected=0, call_records=0, PASS=0, FAIL=0,
                  SKIPPED=0, NOT_RUN=0, AMBIGUOUS=0, not_selected=0)
    for node in nodes:
        if node not in selected:
            result['not_selected'] += 1
            result['NOT_RUN'] += 1
            continue
        result['selected'] += 1
        records = by_node[node]
        actual = [r for r in records if r['when'] == 'call']
        result['call_records'] += len(actual)
        if len(actual) > 1:
            state = 'AMBIGUOUS'
        elif any(r['outcome'] == 'failed' for r in records):
            state = 'FAIL'
        elif any(r['outcome'] == 'skipped' for r in records):
            state = 'SKIPPED'
        elif len(actual) == 1 and actual[0]['outcome'] == 'passed':
            state = 'PASS'
        elif not actual:
            state = 'NOT_RUN'
        else:
            state = 'AMBIGUOUS'
        result[state] += 1
    return result


issues = []
if len(selected) != len(set(selected)):
    issues.append('PLAN_DUPLICATE_NODES')
if not set(selected).issubset(set(plan['full189_nodeids'] + plan['supplemental_nodeids'])):
    issues.append('SELECTED_OUTSIDE_FROZEN_FIXED_AND_SUPPLEMENTAL')
if runner.get('selected') != selected or runner.get('collected') != selected:
    issues.append('SELECTION_OR_COLLECTION_MISMATCH')
if call_ids != selected:
    issues.append('CALL_ORDER_MISSING_OR_DUPLICATED')
if any(r['outcome'] != 'passed' for r in reports) or runner.get('pytest_exit') != 0:
    issues.append('ACTUAL_CHECKS_NOT_ALL_PASSED')
if guard.get('runtime_denials') != []:
    issues.append('GUARD_LEDGER_NONEMPTY_MISSING_OR_INVALID')
if runner.get('cleanup_proven_for_batch') is not True:
    issues.append('CLEANUP_NOT_PROVEN')
if guard.get('preload_window_final_state') != 'CLOSED':
    issues.append('PRELOAD_NOT_CLOSED')
if outer.get('plan_sha256') != inputs[str(plan_path)]:
    issues.append('OUTER_PLAN_BINDING_MISMATCH')
if outer.get('guard_sha256') != inputs[str(guard_path)]:
    issues.append('OUTER_GUARD_BINDING_MISMATCH')
if outer.get('runner_sha256') is not None and outer['runner_sha256'] != inputs[str(runner_path)]:
    issues.append('OUTER_RUNNER_BINDING_MISMATCH')
outer_errors = outer.get('errors')
if not isinstance(outer_errors, list):
    issues.append('OUTER_ERRORS_MISSING_OR_INVALID')
if outer.get('accepted_cpu_feedback') is not True or outer_errors:
    issues.append('OUTER_REJECTED_OR_UNCONFIRMED')

receipt = {
    'kind': 'DERIVED_MACHINE_CPU_FEEDBACK_NOT_EXECUTION_OR_EXIT_PROOF',
    'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'candidate_sha': plan['candidate_sha'],
    'spec_version': plan.get('spec_version'),
    'stage': plan.get('stage'),
    'workpack': plan.get('workpack'),
    'run_directory': plan['report_dir'],
    'plan_sha256': inputs[str(plan_path)],
    'input_sha256': inputs,
    'selected_count': len(selected),
    'collected_count': len(runner.get('collected', [])),
    'call_records': len(calls),
    'unique_calls': len(counts),
    'unexpected_calls': [n for n in counts if n not in selected],
    'duplicate_calls': [n for n, count in counts.items() if count > 1],
    'selected_without_call': [n for n in selected if n not in counts],
    'fixed_original': group(plan['full189_nodeids']),
    'supplemental': group(plan['supplemental_nodeids']),
    'failed_reports': [r for r in reports if r['outcome'] == 'failed'],
    'guard_runtime_denial_count': (len(guard['runtime_denials'])
                                   if isinstance(guard.get('runtime_denials'), list) else None),
    'outer_reported_errors': outer_errors,
    'deterministic_findings': issues,
    'accepted_selected_feedback': not issues,
    'acceptance_scope': 'EXACT_SELECTED_NODES_ONLY',
    'component_checkpoint_claim': False,
    'stage_pass_claim': False,
    'human_signoff_claim': False,
    'product29_claim': False,
    'limitations': 'Derived counts/causes from these inputs; does not independently prove command execution, environment, source preflight or historical ownership.',
}
with output.open('x', encoding='utf-8') as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({k: receipt[k] for k in ['selected_count', 'call_records',
                                        'fixed_original', 'supplemental',
                                        'outer_reported_errors', 'accepted_selected_feedback']}))
