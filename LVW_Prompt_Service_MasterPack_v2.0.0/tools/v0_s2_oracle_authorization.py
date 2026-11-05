"""One explicitly approved oracle-correction slot; reuse bounded admission.

No new retry, fixture, product rule, evidence reuse or optimization policy.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from types import SimpleNamespace

from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools import v0_s2_resource_admission as admission

REQUEST='reports/v0-s2/authorization-s2-oracle-correction-01.request.json'
APPROVAL='reports/v0-s2/authorization-s2-oracle-correction-01.approval.json'
REQUEST_SHA='8cea679b8d0f85f2fdfb205c36a26564d5d390df337b062acab36244c3693725'
DOC_REVISION='d26f8ffc72022214f00658382d75adde0d55387a'
SLOT='full-oracle-correction-01'
READY='resource-admission-oracle-correction-01'
HARNESS='tools/v0_s2_oracle_authorization.py'
RESUME='解除本次文档审阅暂停，按现行门禁继续；docs/25 中未批准的优化暂不实施。'

RESUME_REQUEST='reports/v0-s2/authorization-s2-resource-resume-01.request.json'
RESUME_APPROVAL='reports/v0-s2/authorization-s2-resource-resume-01.approval.json'
RESUME_SHA='63ba7a898498778e272efa57231abeb57d27f2191fa2eb05fc60632775f01ae0'
RESUME_READY='resource-admission-oracle-resume-01'
RESUME_STATEMENT='已释放 GPU，并批准现有 AUTH-REQUEST-V1-S2-RESOURCE-RESUME-01，恢复有限准入及原未使用的完整验收槽位，不增加完整运行次数。'


def authority(candidate,*,require_ready):
    from tools import v0_s2_stage_checkpoint as cp
    request=cp.repository_json(REQUEST); approval=cp.repository_json(APPROVAL)
    coordinate=cp.repository_json('plans/execution-control.json')
    if (cp.file_hash(cp.ROOT/REQUEST)!=REQUEST_SHA or approval.get('request_sha256')!=REQUEST_SHA
            or approval.get('status')!='ACTIVE' or approval.get('granted_by')!='project_owner'
            or approval.get('authorization_id')!='AUTH-V1-S2-ORACLE-CORRECTION-01'
            or approval.get('statement')!='我给予上述授权。' or approval.get('resume_statement')!=RESUME
            or approval.get('runtime_execution_allowed_now') is not True
            or approval.get('complete_runs_approved')!=1 or approval.get('additional_full_rechecks')!=0
            or not approval['issued_at']<=time.time()<approval['expires_at']
            or not 0<approval['expires_at']-approval['issued_at']<=21600
            or coordinate.get('external_execution_hold',{}).get('active') is not False
            or request.get('native_runtime_budget')!=cp.BUDGET or request.get('acceptance_hash')!=cp.ACCEPTANCE
            or request.get('policy_exception_requested')!={'additional_complete_native_runs':1,'additional_full_rechecks':0,
                'planned_run_id':SLOT,'expires_at_terminal_or_revocation':True,'total_wall_seconds_max':21600}
            or request.get('readiness_child',{}).get('planned_run_id')!=READY):
        raise EvidenceError('oracle-correction authority missing, held, expired or broadened')
    return scope_checks(candidate,require_ready,request,approval,sys.modules[__name__])


def scope_checks(candidate,require_ready,request,approval,profile):
    from tools import v0_s2_stage_checkpoint as cp
    cp.program_authority()
    if cp.file_hash(cp.ROOT/request['offline_receipt'])!=request['offline_receipt_sha256']:
        raise EvidenceError('approved offline baseline changed')
    for name,digest in request['seed_artifact_sha256'].items():
        if cp.file_hash(cp.ROOT/cp.SEEDS[name])!=digest:raise EvidenceError('fixed model/sample/SDK binding changed')
    # The owner separately requested and then accepted this exact documentation
    # revision. Do not treat arbitrary later documentation changes as permitted.
    for older,newer in ((request['corrected_candidate'],DOC_REVISION),(DOC_REVISION,candidate)):
        subprocess.run(['git','merge-base','--is-ancestor',older,newer],cwd=cp.ROOT,check=True,timeout=30)
    prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=cp.ROOT,text=True,timeout=30).strip()
    names=subprocess.check_output(['git','diff','--name-only',DOC_REVISION,candidate],cwd=cp.ROOT,text=True,timeout=30).splitlines()
    allowed={'tools/v0_s2_stage_checkpoint.py','tools/v0_s2_resource_admission.py',HARNESS,
        'LVW_V0_RuntimePatch/tests/test_s2_oracle_authorization.py','LVW_V0_RuntimePatch/tests/test_s2_resource_admission.py',
        'LVW_V0_RuntimePatch/tests/test_s2_resource_resume.py',
        'plans/execution-control.json','MANIFEST.sha256'}
    for name in names:
        if not name.startswith(prefix):raise EvidenceError('oracle candidate outside package')
        relative=name[len(prefix):]
        if relative.startswith(('reports/v0-s2/frozen-structural-inputs','reports/v0-s2/fixture-preparation-',
                'reports/v0-s2/authorization-fixtures-')):
            raise EvidenceError('fixed structural media changed')
        if relative not in allowed and not relative.startswith(('reports/v0-s2/','.agent-governance/stages/V0-S2/')):
            raise EvidenceError('candidate outside approved authorization transport: '+relative)
    spec='.agent-governance/stages/V0-S2/stage-control.json'
    old=json.loads(subprocess.check_output(['git','show',DOC_REVISION+':'+prefix+spec],cwd=cp.ROOT,timeout=30))
    current=cp.repository_json(spec)
    if current.get('oracle_correction_authorization')!={'approval':APPROVAL,'request':REQUEST,'slot':SLOT,'max_runs':1,'max_rechecks':0}:
        raise EvidenceError('frozen oracle-correction scope missing/broadened')
    resumed=profile.READY==RESUME_READY
    if resumed and current.get('resource_resume_authorization')!={'approval':RESUME_APPROVAL,'request':RESUME_REQUEST,
            'slot':SLOT,'readiness_slot':RESUME_READY,'max_new_readiness':1,'max_complete_claims':1,'max_extra_complete_runs':0,'max_rechecks':0}:
        raise EvidenceError('frozen resource-resume scope missing/broadened')
    for value in (old,current):
        value.pop('stage_packet_version',None);value.pop('oracle_correction_authorization',None)
        if resumed:value.pop('resource_resume_authorization',None)
    if old!=current:raise EvidenceError('frozen obligations changed')
    for prior in request['prior_failed_runs']:
        report=cp.repository_json(prior['receipt'])
        if cp.file_hash(cp.ROOT/prior['receipt'])!=prior['receipt_sha256'] or report.get('decision')!='NO_GO':
            raise EvidenceError('prior failure changed')
        if (cp.STATE_ROOT/prior['run_id']/'lease.closed').read_bytes()!=b'1':raise EvidenceError('prior run not terminal')
    cleanup=request['existing_cleanup']
    if (cp.file_hash(cp.ROOT/cleanup['receipt'])!=cleanup['receipt_sha256']
            or cp.repository_json(cleanup['receipt']).get('decision')!='CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE'
            or cp.file_hash(cp.ROOT/cleanup['resource_ready_fact_receipt'])!=cleanup['resource_ready_fact_sha256']):
        raise EvidenceError('prior cleanup evidence changed')
    facts=cp.repository_json(cleanup['resource_ready_fact_receipt'])
    directory=cp.STATE_ROOT/'full-resource-ready-01'
    if (cp.file_hash(directory/'terminal.json')!=facts['raw_terminal_sha256']
            or cp.file_hash(directory/'default-raw/ARCHIVE_MANIFEST.json')!=facts['archive_manifest_sha256']
            or facts.get('owned_cleanup_proven') is not True or facts.get('runtime_root_absent') is not True):
        raise EvidenceError('latest failed-run cleanup/terminal binding changed')
    lease=json.loads((directory/'default-root-lease.json').read_bytes())
    terminal=json.loads((directory/'terminal.json').read_bytes())
    from pathlib import Path
    if (Path(lease['root']).parent!=directory or lease.get('run_id')!=facts.get('run_id')
            or lease.get('candidate_sha')!=facts.get('candidate_sha')
            or terminal['runtime_evidence']['default']['owned_run_root']!=lease['root']
            or Path(lease['root']).exists()):
        raise EvidenceError('prior runtime root unexpectedly present or lease changed')
    if require_ready:
        auth=cp.repository_json('reports/v0-s2/authorization-'+profile.READY+'.json');report=cp.repository_json(auth['terminal_receipt'])
        if (auth.get('status')!='EXPIRED_RESOURCE_READY' or auth.get('candidate_sha')!=candidate
                or cp.file_hash(cp.ROOT/auth['terminal_receipt'])!=auth.get('terminal_receipt_sha256')
                or report.get('decision')!='RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE' or report.get('sample_count')!=3
                or (cp.STATE_ROOT/profile.READY/'lease.closed').read_bytes()!=b'1'):
            raise EvidenceError('fresh same-candidate oracle resource admission not proven')
    return {'approval':profile.APPROVAL,'approval_sha256':cp.file_hash(cp.ROOT/profile.APPROVAL),'request':profile.REQUEST,
        'request_sha256':profile.REQUEST_SHA,'expires_at':approval['expires_at']}


def prepare(candidate,offline):
    return admission.prepare(candidate,offline,profile=sys.modules[__name__])


def probe():
    return admission.probe(profile=sys.modules[__name__])


def resource_resume_profile():
    return SimpleNamespace(REQUEST=RESUME_REQUEST,APPROVAL=RESUME_APPROVAL,REQUEST_SHA=RESUME_SHA,
        READY=RESUME_READY,SLOT=SLOT,HARNESS=HARNESS,SCOPE_KEY='readiness_scope',authority=resume_authority)


def resume_authority(candidate,*,require_ready):
    from tools import v0_s2_stage_checkpoint as cp
    request=cp.repository_json(RESUME_REQUEST);approval=cp.repository_json(RESUME_APPROVAL)
    coordinate=cp.repository_json('plans/execution-control.json')
    amendment={'additional_resource_admission_children':1,'planned_readiness_run_id':RESUME_READY,
        'additional_complete_native_runs':0,'restore_original_unclaimed_complete_slot':SLOT,
        'maximum_complete_claims_for_original_slot':1,'additional_full_rechecks':0,'max_total_wall_seconds':21600,
        'expires_at_terminal_or_revocation':True}
    if (cp.file_hash(cp.ROOT/RESUME_REQUEST)!=RESUME_SHA or approval.get('request_sha256')!=RESUME_SHA
            or approval.get('status')!='ACTIVE' or approval.get('authorization_id')!='AUTH-V1-S2-RESOURCE-RESUME-01'
            or approval.get('granted_by')!='project_owner' or approval.get('statement')!=RESUME_STATEMENT
            or approval.get('amendment')!=amendment or request.get('amendment_requested')!=amendment
            or not approval['issued_at']<=time.time()<approval['expires_at']
            or not 0<approval['expires_at']-approval['issued_at']<=21600
            or coordinate.get('resource_resume_authorization')!=RESUME_APPROVAL
            or coordinate.get('external_execution_hold',{}).get('active') is not False
            or request.get('native_runtime_budget')!=cp.BUDGET or request.get('acceptance_hash')!=cp.ACCEPTANCE
            or request.get('original_approved_request')!=REQUEST or request.get('original_approved_request_sha256')!=REQUEST_SHA
            or cp.file_hash(cp.ROOT/REQUEST)!=REQUEST_SHA):
        raise EvidenceError('resource-resume approval missing, expired, held or broadened')
    original=cp.repository_json(REQUEST);previous=cp.repository_json(APPROVAL)
    if previous.get('status')!='EXPIRED_NO_GO' or cp.file_hash(cp.ROOT/APPROVAL)!=approval.get('previous_grant_sha256'):
        raise EvidenceError('original expired grant must remain immutable')
    expected_scope=dict(original['readiness_child']);expected_scope['planned_run_id']=RESUME_READY
    if request.get('readiness_scope')!=expected_scope:raise EvidenceError('readiness scope changed')
    if cp.file_hash(cp.ROOT/request['offline_receipt'])!=request['offline_receipt_sha256']:
        raise EvidenceError('resource-resume baseline changed')
    cp.program_authority()
    subprocess.run(['git','merge-base','--is-ancestor',request['corrected_candidate'],candidate],cwd=cp.ROOT,check=True,timeout=30)
    prior=request['prior_resource_failure'];report=cp.repository_json(prior['receipt'])
    child=cp.repository_json('reports/v0-s2/authorization-'+READY+'.json')
    if (prior.get('run_id')!=READY or cp.file_hash(cp.ROOT/prior['receipt'])!=prior['receipt_sha256']
            or report.get('decision')!='NO_GO' or any(report.get(k)!=0 for k in ('model_calls','service_starts','media_reads','browser_starts'))
            or child.get('status')!='EXPIRED_NO_GO' or child.get('candidate_sha')!=request['corrected_candidate']
            or child.get('terminal_receipt')!=prior['receipt'] or child.get('terminal_receipt_sha256')!=prior['receipt_sha256']
            or (cp.STATE_ROOT/READY/'lease.closed').read_bytes()!=b'1'
            or cp.file_hash(cp.STATE_ROOT/READY/'terminal.json')!=report['raw_terminal_sha256']):
        raise EvidenceError('closed original readiness failure changed')
    if ((cp.STATE_ROOT/SLOT).exists() or (cp.ROOT/'reports/v0-s2'/SLOT).exists()
            or (not require_ready and cp.child_path(SLOT).exists())):
        raise EvidenceError('original complete slot already prepared/claimed; no new complete attempt allowed')
    return scope_checks(candidate,require_ready,original,approval,resource_resume_profile())


def prepare_resume(candidate,offline):
    return admission.prepare(candidate,offline,profile=resource_resume_profile())


def probe_resume():
    return admission.probe(profile=resource_resume_profile())


def main():
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','prepare-resume'):
        ready=commands.add_parser(name);ready.add_argument('--candidate',required=True);ready.add_argument('--offline-receipt',required=True)
    commands.add_parser('probe');commands.add_parser('probe-resume');args=parser.parse_args()
    if args.command in ('prepare','prepare-resume'):
        result=(prepare_resume if args.command=='prepare-resume' else prepare)(args.candidate,args.offline_receipt)
    else:result=(probe_resume if args.command=='probe-resume' else probe)()
    print(json.dumps({key:result.get(key) for key in ('run_id','status','decision','error_code')}))
    return int(result.get('decision')=='NO_GO')


if __name__=='__main__':raise SystemExit(main())
