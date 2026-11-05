"""Read-only recomputation of one terminal failure; no native commands/network."""
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute():
    pack = Path(__file__).resolve().parents[3]
    from tools import v0_s2_stage_checkpoint as cp
    state = cp.STATE_ROOT/'full-oracle-correction-01'
    public_path = pack/'reports/v0-s2/full-oracle-correction-01/receipt.json'
    public = json.loads(public_path.read_bytes())
    assert digest(state/'terminal.json') == public['raw_terminal_sha256']
    terminal = json.loads((state/'terminal.json').read_bytes())
    assert terminal['decision'] == public['decision'] == 'NO_GO'
    assert (state/'lease.closed').read_bytes() == b'1'
    archive = state/'default-raw'
    manifest_path = archive/'ARCHIVE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes())
    assert digest(manifest_path) == terminal['sequence']['default_archive']['manifest_sha256']
    for row in manifest['files']:
        path = archive/row['file']
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
    online = json.loads((archive/'temp/cumulative-phase/online-receipt.json').read_bytes())
    assert online['cases']['V0-A01']['status'] == online['cases']['V0-A03']['status'] == 'PASS'
    phase = json.loads((archive/'temp/public-phase/phase-receipt.json').read_bytes())
    assert phase['cases']['native-decoder']['status'] == 'PASS'
    assert phase['cases']['negative-over-duration']['status'] == 'FAIL'
    history = json.loads((archive/'temp/public-phase/negative-over-duration.history.json').read_bytes())
    record = next(iter(history.values()))
    errors = [json.loads(v['exception_message']) for k, v in record['status']['messages'] if k == 'execution_error']
    assert len(errors) == 1 and errors[0]['code'] == 'SCOPE_FORBIDDEN'
    assert errors[0]['details']['subcode'] == 'NATIVE_BINDING_UNAVAILABLE'
    assert not record['outputs']
    log = (archive/'comfy.log').read_text(errors='replace')
    assert 'FileNotFoundError' in log and 'lvw-native-profile.json' in log
    assert not (archive/'temp/lvw-native-profile.json').exists()
    cleanup = terminal['sequence']['default_cleanup']
    assert cleanup['proven'] and cleanup['final_target_listener_count'] == 0
    assert not cleanup['failures'] and not any(cleanup['http_workers_pending'].values())
    assert all(row['terminal_absent'] and row['unknown_descendants_absent'] for row in cleanup['owned_listener_terminal_states'])
    assert all(row['exited'] and row['native_wrapper_absent'] for row in cleanup['owned_wrapper_terminal_states'])
    assert all(row['proven'] and row['native_worker_absent'] for row in cleanup['sampler_workers'])
    rows = [json.loads(line) for line in (archive/'temp/resource-sampler/resource-trace.jsonl').read_text().splitlines()]
    assert not Path(terminal['runtime_evidence']['default']['owned_run_root']).exists()
    counts = terminal['runtime_counts']['default']
    return {'kind': 'TERMINAL_FAILURE_RECOMPUTATION_NOT_ACCEPTANCE',
        'candidate_sha': terminal['candidate_sha'], 'run_id': terminal['run_id'],
        'public_receipt_sha256': digest(public_path), 'raw_terminal_sha256': digest(state/'terminal.json'),
        'archive_manifest_sha256': digest(manifest_path), 'archive_files_verified': len(manifest['files']),
        'observed_error': errors[0], 'expected_error': {'code': 'MEDIA_LIMIT_EXCEEDED', 'subcode': 'VIDEO_DURATION_LIMIT'},
        'missing_profile_after_startup': True,
        'image_and_four_output_local_facts': 'PASS_NOT_CUMULATIVE_STAGE_PASS',
        'native_decoder_local_fact': 'PASS_NOT_STAGE_PASS',
        'resource_sample_count': len(rows), 'observed_peak_gpu_mib': max(row['gpu_used_mib'] for row in rows),
        'minimum_available_ram_mib': min(row['available_ram_mib'] for row in rows),
        'public_submissions': counts['public_submissions'], 'provider_attempt_upper_bound': counts['provider_attempt_upper_bound'],
        'preloads': counts['preloads'], 'cleanup_proven': True, 'run_root_removed': True,
        'lease_closed': True, 'fixed_case_count': 9, 'stage_pass_claim': False,
        'no_new_service_model_media_gpu_or_browser_actions': True}


if __name__ == '__main__':
    print(json.dumps(recompute(), ensure_ascii=False, indent=2))
