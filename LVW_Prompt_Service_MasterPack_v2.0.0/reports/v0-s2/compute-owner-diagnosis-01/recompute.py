"""Recompute terminal facts only; never query current GPU/processes/services."""
import hashlib
import json
from pathlib import Path


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute():
    from tools import v0_s2_stage_checkpoint as cp
    state=cp.STATE_ROOT/'full-profile-lifecycle-correction-01'
    public_path=cp.ROOT/'reports/v0-s2/full-profile-lifecycle-correction-01/receipt.json'
    public=json.loads(public_path.read_bytes());terminal=json.loads((state/'terminal.json').read_bytes())
    assert public['decision']==terminal['decision']=='NO_GO'
    assert public['raw_terminal_sha256']==digest(state/'terminal.json')
    assert (state/'lease.closed').read_bytes()==b'1'
    raw=state/'default-raw';manifest_path=raw/'ARCHIVE_MANIFEST.json';manifest=json.loads(manifest_path.read_bytes())
    assert digest(manifest_path)==terminal['sequence']['default_archive']['manifest_sha256']
    for row in manifest['files']:
        p=raw/row['file'];assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256']
    public_phase=json.loads((raw/'temp/public-phase/phase-receipt.json').read_bytes())
    assert public_phase['test_counts']=={'fixed':15,'PASS':11,'FAIL':1,'NOT_RUN':3}
    assert public_phase['cases']['category-static']['status']=='FAIL'
    history=json.loads((raw/'temp/public-phase/category-static.history.json').read_bytes())
    record=next(iter(history.values()));assert not record['outputs']
    error=[json.loads(p['exception_message']) for name,p in record['status']['messages'] if name=='execution_error']
    assert len(error)==1 and error[0]['code']=='RESOURCE_BUSY'
    assert error[0]['details']['subcode']=='RESOURCE_PREFLIGHT_UNPROVEN'
    log=(raw/'comfy.log').read_text(errors='replace');assert 'GPU_FOREIGN_COMPUTE_PROCESS' in log
    events=[json.loads(s) for s in (raw/'temp/lvw-native-events.jsonl').read_text().splitlines() if s.strip()]
    final=events[-1];assert final['event']=='run_finished' and final['error_code']=='RESOURCE_BUSY'
    assert final['provider_attempts']==0 and final['result_published'] is False and final['resource_state']=='released'
    samples=[json.loads(s) for s in (raw/'temp/resource-sampler/resource-trace.jsonl').read_text().splitlines() if s.strip()]
    cleanup=terminal['sequence']['default_cleanup']
    assert cleanup['proven'] and cleanup['final_target_listener_count']==0 and not cleanup['failures']
    assert not any(cleanup['http_workers_pending'].values())
    assert all(v['terminal_absent'] and v['unknown_descendants_absent'] for v in cleanup['owned_listener_terminal_states'])
    assert all(v['exited'] and v['native_wrapper_absent'] for v in cleanup['owned_wrapper_terminal_states'])
    assert all(v['proven'] and v['native_worker_absent'] for v in cleanup['sampler_workers'])
    root=terminal['runtime_evidence']['default']['owned_run_root'];assert not Path(root).exists()
    counts=terminal['runtime_counts']['default'];assert counts['provider_attempts_in_native_events']==0
    for ref in ['reports/v0-s2/authorization-s2-profile-lifecycle-01.approval.json',
                'reports/v0-s2/authorization-full-profile-lifecycle-correction-01.json']:
        assert cp.repository_json(ref)['status']=='EXPIRED_NO_GO'
    return {'kind':'TERMINAL_COMPUTE_OWNER_DIAGNOSIS_NOT_ACCEPTANCE',
        'run_id':terminal['run_id'],'candidate_sha':terminal['candidate_sha'],
        'public_receipt_sha256':digest(public_path),'raw_terminal_sha256':digest(state/'terminal.json'),
        'archive_manifest_sha256':digest(manifest_path),'archive_files_verified':len(manifest['files']),
        'archive_bytes_verified':sum(r['bytes'] for r in manifest['files']),
        'public_phase_counts':public_phase['test_counts'],'fixed_stage_cumulative_counts':terminal['test_counts'],
        'public_error':error[0],'nested_production_subcode':'GPU_FOREIGN_COMPUTE_PROCESS',
        'rejected_compute_pid_list_recorded':False,'actual_foreign_or_owned_identity_proven':False,
        'resource_samples':len(samples),'observed_peak_gpu_mib':max(s['gpu_used_mib'] for s in samples),
        'minimum_available_ram_mib':min(s['available_ram_mib'] for s in samples),
        'physical_vram_shortage_proven':False,'public_submissions':counts['public_submissions'],
        'provider_attempt_upper_bound':counts['provider_attempt_upper_bound'],'video_provider_attempts':0,
        'cleanup_proven':True,'run_root_removed':True,'lease_closed':True,'authorization_expired':True,
        'stage_pass_claim':False,'new_native_actions':0}


if __name__=='__main__': print(json.dumps(recompute(),ensure_ascii=False,indent=2))
