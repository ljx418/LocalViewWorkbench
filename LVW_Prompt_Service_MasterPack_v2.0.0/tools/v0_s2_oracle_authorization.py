"""One explicitly approved oracle-correction slot; reuse bounded admission.

No new retry, fixture, product rule, evidence reuse or optimization policy.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time

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
    for value in (old,current):
        value.pop('stage_packet_version',None);value.pop('oracle_correction_authorization',None)
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
        auth=cp.repository_json('reports/v0-s2/authorization-'+READY+'.json');report=cp.repository_json(auth['terminal_receipt'])
        if (auth.get('status')!='EXPIRED_RESOURCE_READY' or auth.get('candidate_sha')!=candidate
                or cp.file_hash(cp.ROOT/auth['terminal_receipt'])!=auth.get('terminal_receipt_sha256')
                or report.get('decision')!='RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE' or report.get('sample_count')!=3
                or (cp.STATE_ROOT/READY/'lease.closed').read_bytes()!=b'1'):
            raise EvidenceError('fresh same-candidate oracle resource admission not proven')
    return {'approval':APPROVAL,'approval_sha256':cp.file_hash(cp.ROOT/APPROVAL),'request':REQUEST,
        'request_sha256':REQUEST_SHA,'expires_at':approval['expires_at']}


def prepare(candidate,offline):
    return admission.prepare(candidate,offline,profile=sys.modules[__name__])


def probe():
    return admission.probe(profile=sys.modules[__name__])


def main():
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    ready=commands.add_parser('prepare');ready.add_argument('--candidate',required=True);ready.add_argument('--offline-receipt',required=True)
    commands.add_parser('probe');args=parser.parse_args()
    result=prepare(args.candidate,args.offline_receipt) if args.command=='prepare' else probe()
    print(json.dumps({key:result.get(key) for key in ('run_id','status','decision','error_code')}))
    return int(result.get('decision')=='NO_GO')


if __name__=='__main__':raise SystemExit(main())
