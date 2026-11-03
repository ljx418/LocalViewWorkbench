"""One-shot, selected-source directed receipt; never a full/Stage gate."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.v0_s2_seal import seal_candidate

DIRECTORY = Path(__file__).resolve().parent
SELECTED = ['LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge',
    'tools/v0_s2_browser_evidence.py', 'tools/v0_s2_browser_supervisor.py',
    'tools/v0_s2_browser_owner.py', 'tools/v0_s2_browser_acceptance.cjs',
    'tools/v0_s2_browser_policy.cjs', 'tools/v0_s2_browser_policy_test.cjs',
    'tools/v0_s2_seal.py', 'contracts/v0-result.schema.json', 'tools/v0_s2_browser_handlers.py',
    'tools/v0_s2_driver.py', 'tools/v0_s2_runtime.py', 'tools/v0_s2_http.py',
    'tools/v0_s2_cancel_phase.py', 'tools/v0_s2_cancel_evidence.py', 'tools/v0_s2_fault_phase.py',
    'tools/v0_s2_fault_evidence.py', 'tools/v0_s2_public_phase.py', 'tools/v0_s2_measurements.py',
    'tools/v0_s2_checkpoint_oracles.py', 'reports/v0-s1/wp-s1-03-phase-a/live_probe.py',
    'LVW_V0_RuntimePatch/tests/test_s2_driver.py',
    'reports/v0-s2/browser-handlers-directed-01/executor.py'] + [
    'LVW_V0_RuntimePatch/tests/test_s2_browser_'+name+'.py' for name in ('evidence', 'supervisor', 'owner', 'worker', 'handlers')]
CHECKS = [
    ('directed', [sys.executable, '-B', '-m', 'unittest'] + [
        'LVW_V0_RuntimePatch.tests.test_s2_browser_'+name for name in ('evidence', 'supervisor', 'owner', 'worker', 'handlers')] + ['LVW_V0_RuntimePatch.tests.test_s2_driver', '-q']),
    ('browser_syntax', ['node', '--check', 'tools/v0_s2_browser_acceptance.cjs']),
    ('pack', [sys.executable, '-B', 'tools/verify_pack.py', '--schema']),
    ('governance', [sys.executable, '-B', 'tools/verify_governance.py', '--self-test']),
    ('diff', ['git', 'diff', '--check']),
]


if __name__ == '__main__':
    if (DIRECTORY/'receipt.json').exists(): raise SystemExit('ONE_SHOT_RECEIPT_EXISTS')
    candidate = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    harness = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {'kind': 'SELECTED_BROWSER_DIRECTED_CHECKS_NOT_FULL_OR_STAGE_ACCEPTANCE',
        'candidate_sha': candidate, 'harness_sha256': harness, 'decision': 'NO_GO', 'stage_pass_claim': False,
        'binding_scope': 'selected browser execution/test sources, not a transitive dependency closure',
        'service_starts': 0, 'browser_starts': 0, 'provider_calls': 0, 'stage_checkpoint_consumed': False,
        'checks': []}
    try:
        identity = seal_candidate(ROOT, candidate, SELECTED)
        result['identity'] = identity
        for name, command in CHECKS:
            row = {'name': name, 'command': command}; result['checks'].append(row)
            process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            row['exit_code'] = process.returncode
            row['passed'] = process.returncode == 0
            for stream, raw in (('stdout', process.stdout), ('stderr', process.stderr)):
                path = DIRECTORY/(name+'.'+stream+'.log')
                with path.open('xb') as output: output.write(raw)
                row[stream] = {'file': path.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            if name == 'directed':
                summary = process.stderr.decode('utf-8', 'replace')
                counts = re.findall(r'^Ran ([0-9]+) tests? in ', summary, re.M)
                row['tests_executed'] = int(counts[0]) if len(counts) == 1 else None
                row['passed'] &= row['tests_executed'] == 42 and bool(re.search(r'^OK\s*$', summary, re.M))
        if seal_candidate(ROOT, candidate, SELECTED) != identity: raise ValueError('SELECTED_SOURCE_CHANGED')
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != harness: raise ValueError('HARNESS_CHANGED')
        if len(result['checks']) == len(CHECKS) and all(row['passed'] for row in result['checks']):
            result['decision'] = 'DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE'
    except Exception as error:
        result['error_code'] = type(error).__name__+':'+str(error)
    result['counts'] = {'fixed_checks': len(CHECKS), 'PASS': sum(r.get('passed') is True for r in result['checks']),
        'FAIL': sum(r.get('passed') is False for r in result['checks']), 'NOT_RUN': len(CHECKS)-len(result['checks'])}
    with (DIRECTORY/'receipt.json').open('x') as stream: stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('decision', 'candidate_sha', 'counts')}))
    raise SystemExit(0 if result['decision'] == 'DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE' else 1)
