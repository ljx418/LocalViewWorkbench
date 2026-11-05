"""Counterfactual draft-policy replay. Reads controlled historical evidence only.

Never queries a GPU, calls a model, modifies old evidence, or authorizes a run.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
STATE=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/V0-S2'
HARD_PEAK=23552
RESERVE=512  # Proposed minimum free reserve; pending approval, not an active gate.

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def classify(samples,additional):
    all_rows=[]
    for sample in samples:
        native=sample['native']['gpus'];wsl=sample['wsl']
        if len(native)!=1 or len(wsl)!=1 or native[0][:2]!=wsl[0][:2]:return 'WOULD_DENY_DEVICE_OR_TELEMETRY'
        for row in (native[0],wsl[0]):
            if (len(row)!=4 or any(type(x) is not int or x<0 for x in row)
                    or row[1]<=0 or row[2]+row[3]>row[1]):return 'WOULD_DENY_DEVICE_OR_TELEMETRY'
            all_rows.append(row)
        if sample['native']['ram_available_mib']<2048 or sample['native']['target_listener_count'] or sample['native']['target_process_count']:
            return 'WOULD_DENY_RAM_OR_TARGET_OWNERSHIP'
    worst_used=max(r[2] for r in all_rows);least_free=min(r[3] for r in all_rows)
    if least_free<additional+RESERVE or worst_used+additional>=HARD_PEAK:return 'WOULD_DENY_HEADROOM'
    return 'WOULD_ADMIT_MONITORED_ATTEMPT'

def main():
    full=STATE/'full-resource-ready-01';public=ROOT/'reports/v0-s2/full-resource-ready-01/receipt.json'
    assert sha(full/'terminal.json')==json.loads(public.read_text())['raw_terminal_sha256']
    terminal=json.loads((full/'terminal.json').read_text())
    manifest_path=full/'default-raw/ARCHIVE_MANIFEST.json';manifest=json.loads(manifest_path.read_text())
    trace_path=full/'default-raw/temp/resource-sampler/resource-trace.jsonl'
    entry=next(r for r in manifest['files'] if r['file']=='temp/resource-sampler/resource-trace.jsonl')
    assert sha(trace_path)==entry['sha256']
    points=[json.loads(line) for line in trace_path.read_text().splitlines()]
    baseline=terminal['runtime_evidence']['default']['preflight']['max_used_mib']
    peak=max(x['gpu_used_mib'] for x in points);additional=peak-baseline
    assert additional>0
    report={'kind':'COUNTERFACTUAL_PROPOSED_POLICY_NOT_PRODUCT_ACCEPTANCE','stage_pass_claim':False,
        'production_policy_changed':False,'new_gpu_queries':0,'new_model_calls':0,
        'model':terminal['runtime_evidence']['default']['model'],
        'source_terminal_sha256':sha(full/'terminal.json'),'source_archive_manifest_sha256':sha(manifest_path),
        'source_resource_trace_sha256':sha(trace_path),'resource_samples':len(points),
        'historical_pre_service_used_mib':baseline,'historical_total_peak_mib':peak,'observed_increment_mib':additional,
        'proposed_free_reserve_mib':RESERVE,'proposed_required_free_mib':additional+RESERVE,
        'unchanged_hard_peak_mib_exclusive':HARD_PEAK,'replays':[],
        'limitations':['One successful image analysis is a measured baseline, not a proven worst-case video bound.',
            'Admission means permission for a monitored attempt, not guaranteed OOM-free completion.',
            'Numerical profile and resource method remain proposed until owner approval; no old NO_GO is rewritten.']}
    expected=['WOULD_DENY_HEADROOM','WOULD_ADMIT_MONITORED_ATTEMPT','WOULD_ADMIT_MONITORED_ATTEMPT']
    for run,want in zip(['resource-admission-oracle-correction-01','resource-admission-oracle-resume-01','resource-admission-01'],expected):
        path=ROOT/'reports/v0-s2'/run/'receipt.json';data=json.loads(path.read_text());raw=STATE/run/'terminal.json'
        assert sha(raw)==data['raw_terminal_sha256']
        samples=data['samples'];rows=[row for s in samples for row in (s['native']['gpus'][0],s['wsl'][0])]
        decision=classify(samples,additional);assert decision==want
        report['replays'].append({'run_id':run,'original_decision':data['decision'],'original_receipt_sha256':sha(path),
            'worst_used_mib':max(x[2] for x in rows),'least_free_mib':min(x[3] for x in rows),
            'observed_reserved_mib':[x[1]-x[2]-x[3] for x in rows],
            'projected_total_used_mib':max(x[2] for x in rows)+additional,'draft_decision':decision})
    def sample(used,free):
        row=[0,24564,used,free]
        return [{'native':{'gpus':[row],'ram_available_mib':2048,'target_listener_count':0,'target_process_count':0},'wsl':[row.copy()]}]
    controls=[('exact_free',sample(4000,additional+RESERVE),'WOULD_ADMIT_MONITORED_ATTEMPT'),
        ('one_below_free',sample(4000,additional+RESERVE-1),'WOULD_DENY_HEADROOM'),
        ('exact_hard_peak',sample(HARD_PEAK-additional,additional+RESERVE),'WOULD_DENY_HEADROOM'),
        ('one_below_hard_peak',sample(HARD_PEAK-additional-1,additional+RESERVE),'WOULD_ADMIT_MONITORED_ATTEMPT'),
        ('invalid_telemetry',sample(4000,24565),'WOULD_DENY_DEVICE_OR_TELEMETRY')]
    report['draft_boundary_checks']=[]
    for name,data,want in controls:
        actual=classify(data,additional);assert actual==want
        report['draft_boundary_checks'].append({'name':name,'expected':want,'actual':actual})
    sys.path.insert(0,str(ROOT))
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources import validate_snapshot
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
    try:
        validate_snapshot('24564,4520,19619\n','',8913,owner_pid=1)
    except BridgeError as error:
        report['current_production_cpu_replay']=json.loads(str(error))
    else:raise AssertionError('Expected current sum-gap rejection was not reproduced')
    report['decision']='DRAFT_REPLAY_MATCHES_EXPECTATIONS_NOT_STAGE_ACCEPTANCE'
    (Path(__file__).parent/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('observed_increment_mib','proposed_required_free_mib','replays','decision')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
