"""Derive fresh finite S2 checkpoints without another human GPU approval."""
import argparse
import re
import time

from tools import v0_verification_authority as program


def is_slot(slot):return isinstance(slot,str) and re.fullmatch('full-v0-auto-[0-9]{2}',slot) is not None


def require_closed_runs():
    from tools import v0_s2_stage_checkpoint as cp
    roots=[*cp.STATE_ROOT.glob('full-*'),*cp.STATE_ROOT.glob('browser-component-*')]
    for root in roots:
        if root.is_symlink() or root.resolve(strict=True)!=root:raise ValueError('runtime registry redirect forbidden')
        if root.is_dir():
            marker=root/'lease.closed'
            if not marker.is_file() or marker.read_bytes()!=b'1':
                raise ValueError('another complete verification is active, unclosed or incomplete')
            if root.name.startswith('browser-component-'):
                from tools.v0_s2_component_clearance import require_clearance
                require_clearance(root)


def approval_path(slot):
    if not is_slot(slot):raise ValueError('automatic verification slot invalid')
    return 'reports/v0-s2/authorization-'+slot+'.approval.json'


def authority(slot,candidate):
    from tools import v0_s2_stage_checkpoint as cp
    parent=cp.repository_json(program.PROGRAM);program.validate(parent,'V0-S2')
    control=cp.repository_json('plans/execution-control.json');path=approval_path(slot)
    child=cp.repository_json(path)
    require_closed_runs()
    if (control.get('v0_verification_program')!=program.PROGRAM or control.get('external_execution_hold',{}).get('active') is not False
            or child.get('status')!='ACTIVE_ONE_SHOT' or child.get('candidate_sha')!=candidate or child.get('run_id')!=slot
            or child.get('program_sha256')!=cp.file_hash(cp.ROOT/program.PROGRAM)
            or child.get('budget')!=cp.BUDGET or parent.get('default_full_s2_run_budget')!=cp.BUDGET
            or child.get('acceptance_hash')!=cp.ACCEPTANCE
            or child.get('harness_sha256')!=cp.file_hash(cp.ROOT/cp.HARNESS)
            or child.get('stage_packet_sha256')!=cp.file_hash(cp.ROOT/'.agent-governance/stages/V0-S2/stage-control.json')
            or not child['issued_at']<=time.time()<child['expires_at'] or not 0<child['expires_at']-child['issued_at']<=21600
            or (cp.STATE_ROOT/slot).exists() or (cp.ROOT/'reports/v0-s2'/slot).exists()):
        raise ValueError('automatic finite verification authority invalid, changed, held or claimed')
    return {'approval':path,'approval_sha256':cp.file_hash(cp.ROOT/path),'request':program.PROGRAM,
            'request_sha256':cp.file_hash(cp.ROOT/program.PROGRAM),'expires_at':child['expires_at']}


def prepare(slot,candidate,offline):
    from tools import v0_s2_stage_checkpoint as cp
    parent=cp.repository_json(program.PROGRAM);program.validate(parent,'V0-S2')
    if parent.get('default_full_s2_run_budget')!=cp.BUDGET:raise ValueError('fixed verification budget changed')
    path=cp.ROOT/approval_path(slot)
    if path.exists() or cp.child_path(slot).exists() or (cp.STATE_ROOT/slot).exists():raise ValueError('fresh unique slot required')
    identity=cp.source_gate(candidate,offline)
    child=program.child(parent,stage='V0-S2',run_id=slot,candidate=candidate,harness_sha256=cp.file_hash(cp.ROOT/cp.HARNESS),
        program_sha256=cp.file_hash(cp.ROOT/program.PROGRAM),budget=cp.BUDGET,max_seconds=cp.BUDGET['max_seconds'])
    child.update(acceptance_hash=cp.ACCEPTANCE,source_payload_sha256=identity['payload_sha256'],
        offline_receipt=offline,offline_receipt_sha256=cp.file_hash(cp.ROOT/offline),
        stage_packet_sha256=cp.file_hash(cp.ROOT/'.agent-governance/stages/V0-S2/stage-control.json'))
    cp.write_new(path,child)
    return cp.prepare(slot,candidate,offline)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--slot',required=True);parser.add_argument('--candidate',required=True)
    parser.add_argument('--offline-receipt',required=True);args=parser.parse_args()
    value=prepare(args.slot,args.candidate,args.offline_receipt)
    print(value['run_id'],value['status'])
