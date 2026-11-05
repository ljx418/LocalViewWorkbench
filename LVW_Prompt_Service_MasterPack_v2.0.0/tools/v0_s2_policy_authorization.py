"""Approved GPU policy correction plus one new admission/original unused slot."""
import argparse
import json
import subprocess
import sys
import time

from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools import v0_s2_resource_admission as admission
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import profile

REQUEST='reports/v0-s2/change-request-gpu-admission-01.json'
REQUEST_SHA='5093b44c4a15622471cef068042b113fddfd76167bc308f8402457a56011ecda'
DECISION='reports/v0-s2/change-decision-gpu-admission-01.json'
APPROVAL='reports/v0-s2/authorization-s2-policy-correction-01.approval.json'
BASELINE='8e7e06df0f84a7db1d52cb922b25184a03b28fa2'
SLOT='full-oracle-correction-01'
READY='resource-admission-policy-correction-01'
HARNESS='tools/v0_s2_policy_authorization.py'
ORIGINAL='reports/v0-s2/authorization-s2-oracle-correction-01.request.json'


def readiness_scope():
    from tools import v0_s2_stage_checkpoint as cp
    scope=dict(cp.repository_json(ORIGINAL)['readiness_child'])
    scope.pop('gpu_used_mib_max');scope.update(planned_run_id=READY,resource_policy=profile())
    return scope


def authority(candidate,*,require_ready):
    from tools import v0_s2_stage_checkpoint as cp
    request=cp.repository_json(REQUEST);grant=cp.repository_json(APPROVAL);decision=cp.repository_json(DECISION)
    control=cp.repository_json('plans/execution-control.json')
    if (cp.file_hash(cp.ROOT/REQUEST)!=REQUEST_SHA or grant.get('request_sha256')!=REQUEST_SHA
            or grant.get('status')!='ACTIVE' or grant.get('granted_by')!='project_owner'
            or grant.get('statement')!='批准继续进行' or grant.get('authorization_id')!='AUTH-V1-S2-GPU-POLICY-CORRECTION-01'
            or grant.get('execution_amendment')!=request['execution_amendment_requested']
            or not grant['issued_at']<=time.time()<grant['expires_at'] or not 0<grant['expires_at']-grant['issued_at']<=21600
            or grant.get('baseline_commit')!=BASELINE or grant.get('decision_sha256')!=cp.file_hash(cp.ROOT/DECISION)
            or decision.get('decision')!='APPROVED_BY_PROJECT_OWNER' or decision.get('request_sha256')!=REQUEST_SHA
            or decision.get('approved_parts')!=['proposed_resolution','execution_amendment_requested']
            or control.get('policy_correction_authorization')!=APPROVAL
            or control.get('external_execution_hold',{}).get('active') is not False):
        raise EvidenceError('policy-correction authority missing, expired, changed or held')
    cp.program_authority()
    amendment=request['execution_amendment_requested']
    expected={'approve_only_after_policy_offline_gate':True,'additional_finite_readiness_children':1,
        'planned_readiness_run_id':READY,'restore_unclaimed_complete_slot':SLOT,'maximum_total_claims_for_original_complete_slot':1,
        'additional_complete_native_runs':0,'additional_full_rechecks':0,'max_total_wall_seconds':21600,
        'keep_all_original_native_action_budgets':True,'expire_at_readiness_failure_or_complete_terminal_or_revocation':True,
        'new_candidate_and_child_bindings_required':True}
    if amendment!=expected:raise EvidenceError('approved finite amendment changed')
    cold=request['proposed_resolution']['cold_admission'];p=profile()
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core
    if (p['num_ctx']!=core.MAX_NUM_CTX or p['num_ctx']>cold['num_ctx']
            or p['num_predict']!=core.MAX_NUM_PREDICT or decision.get('effective_calibrated_num_ctx')!=p['num_ctx']
            or p['version']!=request['proposed_resolution']['policy_version'] or p['model_digest']!=cold['model']['digest']
            or any(p[k]!=cold[k] for k in ('max_parallel','image_long_edge','video_frame_long_edge','observed_increment_mib','minimum_free_reserve_mib','required_free_mib'))
            or p['hard_peak_mib_exclusive']!=cold['require_projected_total_used_mib_less_than']
            or cp.file_hash(cp.ROOT/request['evidence'])!=request['evidence_sha256']):
        raise EvidenceError('approved shared policy/profile evidence changed')
    original=cp.repository_json(ORIGINAL)
    if original['native_runtime_budget']!=cp.BUDGET or original['acceptance_hash']!=cp.ACCEPTANCE:
        raise EvidenceError('original runtime budget/denominator changed')
    for name,digest in original['seed_artifact_sha256'].items():
        if cp.file_hash(cp.ROOT/cp.SEEDS[name])!=digest:raise EvidenceError('model/media/SDK seed changed')
    subprocess.run(['git','merge-base','--is-ancestor',BASELINE,candidate],cwd=cp.ROOT,check=True,timeout=30)
    prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=cp.ROOT,text=True,timeout=30).strip()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE,candidate],cwd=cp.ROOT,text=True,timeout=30).splitlines()
    owners={'resource_policy.py','video_resources.py','video_transport.py','benchmark.py'}
    tools={'v0_s2_policy_authorization.py','v0_s2_stage_checkpoint.py','v0_s2_resource_admission.py','v0_s2_runtime.py',
        'v0_s2_stage_runtime.py','v0_s2_cumulative_phase.py','v0_s2_cancel_evidence.py','v0_s2_browser_evidence.py',
        'v0_s2_browser_handlers.py','v0_s2_measurements.py','v0_s2_fault_phase.py','v0_s2_fault_evidence.py'}
    for name in changed:
        if not name.startswith(prefix):raise EvidenceError('candidate outside package')
        relative=name[len(prefix):]
        if relative.startswith(('reports/v0-s2/frozen-structural-inputs','reports/v0-s2/fixture-preparation-','reports/v0-s2/authorization-fixtures-')):
            raise EvidenceError('fixed structural samples changed')
        allowed=(relative in {'plans/execution-control.json','MANIFEST.sha256','docs/24_EXECUTION_MASTER_PLAN.md','docs/25_PLAN_OPTIMIZATION_PROPOSAL.md'}
            or relative.startswith(('reports/v0-s2/','.agent-governance/stages/V0-S2/','LVW_V0_RuntimePatch/tests/'))
            or relative in {'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'+x for x in owners}
            or relative in {'tools/'+x for x in tools})
        if not allowed:raise EvidenceError('candidate outside approved resource correction: '+relative)
    spec='.agent-governance/stages/V0-S2/stage-control.json';current=cp.repository_json(spec)
    old=json.loads(subprocess.check_output(['git','show',BASELINE+':'+prefix+spec],cwd=cp.ROOT,timeout=30))
    expected_stage={'approval':APPROVAL,'request':REQUEST,'slot':SLOT,'readiness_slot':READY,'max_new_readiness':1,'max_complete_claims':1,'max_extra_complete_runs':0,'max_rechecks':0}
    if current.get('policy_correction_authorization')!=expected_stage or current.get('gpu_admission_policy')!=p:
        raise EvidenceError('frozen approved policy authorization missing/broadened')
    if current.get('authorities')!=old['authorities']+[DECISION]:raise EvidenceError('unapproved authority change')
    current['authorities']=old['authorities']
    for doc in (current,old):
        for key in ('stage_packet_version','gpu_admission_policy','policy_correction_authorization'):doc.pop(key,None)
    if current!=old:raise EvidenceError('other frozen obligations changed')
    required={'full-checkpoint-01','full-recheck-01','full-supplemental-01','full-resource-ready-01','resource-admission-oracle-correction-01','resource-admission-oracle-resume-01'}
    if {r['run_id'] for r in grant['prior_failures']}!=required:raise EvidenceError('prior failure denominator changed')
    for row in grant['prior_failures']:
        terminal=cp.repository_json(row['receipt']);state=cp.STATE_ROOT/row['run_id']
        if (cp.file_hash(cp.ROOT/row['receipt'])!=row['receipt_sha256'] or terminal.get('decision')!='NO_GO'
                or cp.file_hash(state/'terminal.json')!=row['raw_terminal_sha256']
                or (state/'lease.closed').read_bytes()!=b'1'):raise EvidenceError('prior failure/closure changed')
    if set(grant['prior_expired_grants'])!={'reports/v0-s2/authorization-s2-oracle-correction-01.approval.json',
            'reports/v0-s2/authorization-s2-resource-resume-01.approval.json'}:raise EvidenceError('old grant denominator changed')
    for ref,digest in grant['prior_expired_grants'].items():
        if cp.file_hash(cp.ROOT/ref)!=digest or cp.repository_json(ref).get('status')!='EXPIRED_NO_GO':
            raise EvidenceError('expired old grant changed')
    if ((cp.STATE_ROOT/SLOT).exists() or (cp.ROOT/'reports/v0-s2'/SLOT).exists()
            or (not require_ready and cp.child_path(SLOT).exists())):
        raise EvidenceError('original full slot already prepared/claimed')
    if require_ready:
        child=cp.repository_json('reports/v0-s2/authorization-'+READY+'.json');receipt=cp.repository_json(child['terminal_receipt'])
        if (child.get('status')!='EXPIRED_RESOURCE_READY' or child.get('candidate_sha')!=candidate
                or cp.file_hash(cp.ROOT/child['terminal_receipt'])!=child.get('terminal_receipt_sha256')
                or receipt.get('decision')!='RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE' or receipt.get('sample_count')!=3
                or child.get('scope')!=readiness_scope() or (cp.STATE_ROOT/READY/'lease.closed').read_bytes()!=b'1'):
            raise EvidenceError('new same-candidate policy readiness not proven')
    return {'approval':APPROVAL,'approval_sha256':cp.file_hash(cp.ROOT/APPROVAL),'request':REQUEST,'request_sha256':REQUEST_SHA,'expires_at':grant['expires_at']}


def prepare(candidate,offline):return admission.prepare(candidate,offline,profile=sys.modules[__name__])
def probe():return admission.probe(profile=sys.modules[__name__])


def main():
    parser=argparse.ArgumentParser();cmd=parser.add_subparsers(dest='command',required=True)
    p=cmd.add_parser('prepare');p.add_argument('--candidate',required=True);p.add_argument('--offline-receipt',required=True)
    cmd.add_parser('probe');a=parser.parse_args();v=prepare(a.candidate,a.offline_receipt) if a.command=='prepare' else probe()
    print(json.dumps({k:v.get(k) for k in ('run_id','status','decision','error_code')}));return int(v.get('decision')=='NO_GO')

if __name__=='__main__':raise SystemExit(main())
