"""One explicitly approved readiness/full run after the profile lifecycle fix."""
import argparse
import hashlib
import json
import subprocess
import sys
import time

from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools import v0_s2_resource_admission as admission
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import profile

REQUEST = 'reports/v0-s2/authorization-s2-profile-lifecycle-01.request.json'
REQUEST_SHA = 'd26de57732f99320615d36112fd0c54de27a990d04a2c69bfaf91e23454456da'
APPROVAL = 'reports/v0-s2/authorization-s2-profile-lifecycle-01.approval.json'
BASELINE = '5bb7c14a12ef51d09efe0937e8fe59380fdc6a2c'
SLOT = 'full-profile-lifecycle-correction-01'
READY = 'resource-admission-profile-lifecycle-01'
HARNESS = 'tools/v0_s2_lifecycle_authorization.py'
HISTORICAL = {
    'reports/v0-s2/authorization-s2-policy-correction-01.approval.json',
    'reports/v0-s2/authorization-s2-oracle-correction-01.approval.json',
    'reports/v0-s2/authorization-s2-resource-resume-01.approval.json',
    'reports/v0-s2/authorization-full-oracle-correction-01.json',
}


def packet_scope():
    return dict(approval=APPROVAL, request=REQUEST, slot=SLOT, readiness_slot=READY,
                max_new_readiness=1, max_complete_claims=1, max_rechecks=0)


def readiness_scope():
    from tools import v0_s2_stage_checkpoint as cp
    return cp.repository_json(REQUEST)['readiness_child']


def verify_ready(candidate):
    """Recompute the controlled raw run, never trust a success summary alone."""
    from tools import v0_s2_stage_checkpoint as cp
    from tools.v0_s2_execution_bindings import plain
    directory = cp.STATE_ROOT/READY
    def raw(name, limit=1024*1024):
        path = plain(directory/name)
        if path.stat().st_size > limit: raise EvidenceError('readiness raw artifact too large')
        data = path.read_bytes()
        if len(data) > limit: raise EvidenceError('readiness raw artifact too large')
        return data
    try:
        child = cp.repository_json('reports/v0-s2/authorization-'+READY+'.json')
        receipt = cp.repository_json(child['terminal_receipt'])
        active = json.loads(raw('active-child.json')); terminal_bytes = raw('terminal.json')
        terminal = json.loads(terminal_bytes)
        expected = dict(active, status='EXPIRED_RESOURCE_READY', terminal_receipt=child['terminal_receipt'],
                        terminal_receipt_sha256=cp.file_hash(cp.ROOT/child['terminal_receipt']))
        if (child != expected or active.get('status') != 'ACTIVE_ONE_SHOT'
                or active.get('run_id') != READY or active.get('candidate_sha') != candidate
                or active.get('scope') != readiness_scope()
                or active.get('harness_sha256') != cp.file_hash(cp.ROOT/HARNESS)
                or active.get('program_sha256') != cp.program_authority()
                or active.get('supplemental_authorization', {}).get('approval_sha256') != cp.file_hash(cp.ROOT/APPROVAL)
                or cp.file_hash(cp.ROOT/active['offline_receipt']) != active['offline_receipt_sha256']
                or receipt.get('raw_terminal_sha256') != hashlib.sha256(terminal_bytes).hexdigest()
                or raw('lease.closed', 1) != b'1'):
            raise EvidenceError('readiness raw/active/public/child identity mismatch')
        for result in (terminal, receipt):
            if (result.get('run_id') != READY or result.get('candidate_sha') != candidate
                    or result.get('decision') != 'RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE'
                    or result.get('sample_count') != 3 or result.get('stage_pass_claim') is not False
                    or any(result.get(key) != 0 for key in ('model_calls','service_starts','media_reads','browser_starts','foreign_process_terminations'))):
                raise EvidenceError('readiness terminal incomplete or out of scope')
        commands = terminal['commands']; samples = terminal['samples']
        if (len(commands) != 6 or len(samples) != 3 or terminal['elapsed_seconds'] > 60
                or terminal.get('native_command_upper_bound') != 6 or terminal.get('wsl_commands') != 3):
            raise EvidenceError('readiness fixed command/sample budget changed')
        for index, sample in enumerate(samples):
            if sample['ordinal'] != index+1: raise EvidenceError('readiness sample order changed')
            outputs = []
            for offset, kind in enumerate(('native','wsl')):
                ordinal = index*2+offset+1; command = commands[ordinal-1]
                started = json.loads(raw('command-'+str(ordinal)+'.json'))
                if (command['kind'] != kind or command['exit_code'] != 0
                        or started != {'kind':kind,'argv':command['argv'],'exit_code':None}):
                    raise EvidenceError('readiness original command identity/exit changed')
                for stream in ('stdout','stderr'):
                    data = raw('command-'+str(ordinal)+'.'+stream+'.log', 65536)
                    if hashlib.sha256(data).hexdigest() != command[stream+'_sha256']:
                        raise EvidenceError('readiness original command output changed')
                    if stream == 'stdout': outputs.append(data.decode('utf-8-sig').strip())
            native = json.loads(outputs[0])
            native['gpus'] = [[int(v.strip()) for v in line.split(',')] for line in native['gpu_csv'].splitlines() if line.strip()]
            wsl = [[int(v.strip()) for v in line.split(',')] for line in outputs[1].splitlines() if line.strip()]
            if native != sample['native'] or wsl != sample['wsl'] or admission.oracle(native,wsl) != sample['admission']:
                raise EvidenceError('readiness raw sample/oracle mismatch')
    except (OSError, KeyError, ValueError, TypeError) as error:
        raise EvidenceError('fresh complete raw readiness not proven: '+str(error)) from error


def authority(candidate, *, require_ready):
    from tools import v0_s2_stage_checkpoint as cp
    request = cp.repository_json(REQUEST); grant = cp.repository_json(APPROVAL)
    control = cp.repository_json('plans/execution-control.json')
    if (cp.file_hash(cp.ROOT/REQUEST) != REQUEST_SHA or grant.get('request_sha256') != REQUEST_SHA
            or grant.get('authorization_id') != 'AUTH-V1-S2-PROFILE-LIFECYCLE-01'
            or grant.get('status') != 'ACTIVE' or grant.get('granted_by') != 'project_owner'
            or grant.get('statement') != '批准 AUTH-REQUEST-V1-S2-PROFILE-LIFECYCLE-01'
            or grant.get('scope') != request['policy_exception_requested']
            or not grant['issued_at'] <= time.time() < grant['expires_at']
            or not 0 < grant['expires_at']-grant['issued_at'] <= 21600
            or control.get('profile_lifecycle_authorization') != APPROVAL
            or control.get('external_execution_hold', {}).get('active') is not False):
        raise EvidenceError('WAIT_AUTH: lifecycle permission absent, expired, changed or held')
    cp.program_authority()
    if (request['corrected_candidate'] != BASELINE or request['native_runtime_budget'] != cp.BUDGET
            or request['acceptance_hash'] != cp.ACCEPTANCE or readiness_scope()['resource_policy'] != profile()):
        raise EvidenceError('lifecycle budget, baseline, denominator or profile changed')
    for ref, digest in request['correction_files_sha256'].items():
        if cp.file_hash(cp.ROOT/ref) != digest: raise EvidenceError('approved lifecycle correction changed')
    for ref, key in [(request['offline_receipt'], 'offline_receipt_sha256'),
                     (request['failure_recomputation'], 'failure_recomputation_sha256')]:
        if cp.file_hash(cp.ROOT/ref) != request[key]: raise EvidenceError('approved offline/failure evidence changed')
    for name, digest in request['seed_artifact_sha256'].items():
        if cp.file_hash(cp.ROOT/cp.SEEDS[name]) != digest: raise EvidenceError('bound model/media/SDK seed changed')
    if set(grant.get('historical_records_sha256', {})) != HISTORICAL:
        raise EvidenceError('historical authority set changed')
    for ref, digest in grant['historical_records_sha256'].items():
        if cp.file_hash(cp.ROOT/ref) != digest or cp.repository_json(ref).get('status') != 'EXPIRED_NO_GO':
            raise EvidenceError('historical expired authority changed')
    expected = {'full-checkpoint-01','full-recheck-01','full-supplemental-01','full-resource-ready-01','full-oracle-correction-01'}
    if {r['run_id'] for r in request['prior_consumed_full_runs']} != expected:
        raise EvidenceError('prior full-run denominator changed')
    for row in request['prior_consumed_full_runs']:
        state = cp.STATE_ROOT/row['run_id']
        if (cp.file_hash(cp.ROOT/row['receipt']) != row['receipt_sha256']
                or cp.repository_json(row['receipt']).get('decision') != 'NO_GO'
                or cp.file_hash(state/'terminal.json') != row['raw_terminal_sha256']
                or (state/'lease.closed').read_bytes() != b'1'):
            raise EvidenceError('prior failure identity/closure changed')
    subprocess.run(['git','merge-base','--is-ancestor',BASELINE,candidate],cwd=cp.ROOT,check=True,timeout=30)
    prefix = subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=cp.ROOT,text=True,timeout=30).strip()
    changed = subprocess.check_output(['git','diff','--name-only',BASELINE,candidate],cwd=cp.ROOT,text=True,timeout=30).splitlines()
    spec = '.agent-governance/stages/V0-S2/stage-control.json'
    allowed = {'plans/execution-control.json','MANIFEST.sha256','docs/24_EXECUTION_MASTER_PLAN.md',
        HARNESS,'tools/v0_s2_stage_checkpoint.py','LVW_V0_RuntimePatch/tests/test_s2_lifecycle_authorization.py',
        spec,'.agent-governance/stages/V0-S2/PAYLOAD_MANIFEST.sha256',
        '.agent-governance/stages/V0-S2/07-checkpoint-plan.md'}
    for name in changed:
        if not name.startswith(prefix): raise EvidenceError('lifecycle candidate outside package')
        ref = name[len(prefix):]
        if ref.startswith(('reports/v0-s2/frozen-structural-inputs','reports/v0-s2/fixture-preparation-','reports/v0-s2/authorization-fixtures-')):
            raise EvidenceError('frozen samples changed')
        if ref not in allowed and not ref.startswith('reports/v0-s2/'):
            raise EvidenceError('lifecycle candidate outside authorization wiring: '+ref)
    old = json.loads(subprocess.check_output(['git','show',BASELINE+':'+prefix+spec],cwd=cp.ROOT,timeout=30))
    current = cp.repository_json(spec)
    if current.get('profile_lifecycle_authorization') != packet_scope() or current.get('authorities') != old['authorities']+[APPROVAL]:
        raise EvidenceError('frozen lifecycle authority changed')
    current.pop('profile_lifecycle_authorization'); current['authorities'] = old['authorities']
    current.pop('stage_packet_version'); old.pop('stage_packet_version')
    if current != old: raise EvidenceError('other frozen obligations changed')
    if (cp.STATE_ROOT/SLOT).exists() or (cp.ROOT/'reports/v0-s2'/SLOT).exists():
        raise EvidenceError('lifecycle full slot already claimed')
    if not require_ready and cp.child_path(SLOT).exists(): raise EvidenceError('full slot already prepared')
    if require_ready:
        verify_ready(candidate)
    return {'approval':APPROVAL,'approval_sha256':cp.file_hash(cp.ROOT/APPROVAL),
            'request':REQUEST,'request_sha256':REQUEST_SHA,'expires_at':grant['expires_at']}


def main():
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest='command',required=True)
    ready = commands.add_parser('prepare'); ready.add_argument('--candidate',required=True); ready.add_argument('--offline-receipt',required=True)
    commands.add_parser('probe'); args = parser.parse_args()
    own = sys.modules[__name__]
    value = admission.prepare(args.candidate,args.offline_receipt,profile=own) if args.command == 'prepare' else admission.probe(profile=own)
    print(json.dumps({k:value.get(k) for k in ('run_id','status','decision','error_code')}))
    return int(value.get('decision') == 'NO_GO')


if __name__ == '__main__': raise SystemExit(main())
