"""Adapt only synthetic parts of independent-01 scripts; never open old previews."""
import hashlib
import json
import pathlib
import sys
import tempfile
import time
import os

P = pathlib.Path(__file__).resolve().parents[6]
sys.path.insert(0, str(P / 'tools'))
import s3_sample_preparation as s
import test_s3_sample_preparation as t

result = {'scope': 'synthetic only; no old preview or original source access', 'cases': {}}
with tempfile.TemporaryDirectory(prefix='s3-correction-proof-') as tmp:
    base = pathlib.Path(tmp)
    package = t.correction_package(base / 'source-change')
    source = package.source / 'a.jpg'
    source.write_bytes(source.read_bytes() + b'changed')
    receipt = t.correction_run(package)
    result['cases']['size_change'] = {
        'decision': receipt['decision'], 'hash_calls': receipt['budget']['source_files_hashed'],
        'image_decodes': receipt['budget']['image_decode_calls'],
        'statuses': [x['status'] for x in receipt['candidates']], 'cleanup': receipt['cleanup']}
    assert receipt['decision'] == 'SOURCE_CHANGED_TERMINAL'
    assert receipt['budget']['source_files_hashed'] == receipt['budget']['image_decode_calls'] == 0
    tick = [0.0]
    adapter = t.ControlledAdapter(tick, probe_advance=1201)
    receipt = t.correction_run(t.correction_package(base / 'deadline', video=True), adapter, tick)
    result['cases']['deadline'] = {'decision': receipt['decision'], 'calls': adapter.calls,
        'wall_seconds_used': receipt['budget']['wall_seconds_used'], 'cleanup': receipt['cleanup']}
    assert receipt['decision'] == 'BUDGET_EXHAUSTED' and adapter.calls == ['probe']
    adapter = t.ControlledAdapter(padding=100000)
    receipt = t.correction_run(t.correction_package(base / 'output', video=True), adapter, output=100000)
    result['cases']['output'] = {'decision': receipt['decision'], 'calls': adapter.calls,
        'budget': receipt['budget'], 'cleanup': receipt['cleanup']}
    assert receipt['decision'] == 'PREPARATION_FAILED_OUTPUT_BUDGET_EXCEEDED'
    assert adapter.calls == ['probe', 'frame']
    # Real owned CPU timeout, no decoder or model, then kill(0) absence check.
    budget = s.OutputAccountant(limit=100, deadline=time.monotonic() + .08)
    try:
        budget.render(lambda: time.sleep(30), base / 'never-created')
    except s.BudgetStop:
        pass
    event = budget.processes[0]
    assert event['reaped'] and event['exitcode'] < 0
    try:
        os.kill(event['pid'], 0)
        raise AssertionError('owned process remains')
    except ProcessLookupError:
        event['pid_absent_measured'] = True
    result['owned_timeout'] = event
    result['temporary_tree_before_cleanup'] = {
        'entries': len(list(base.rglob('*'))),
        'bytes': sum(p.stat().st_size for p in base.rglob('*') if p.is_file())}
result['temporary_root_absent_measured'] = not base.exists()
assert result['temporary_root_absent_measured']
result['historical_data_deleted'] = 0
print(json.dumps(result, indent=2))
