"""Explicit one-slot amendment and exact retained-root cleanup, never implicit retry.

No target I/O at import/authority/prepare. The cleanup command claims its own
child before inspecting the adopted root or launching a pinned native helper.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from tools.v0_s2_checkpoint_oracles import EvidenceError

REQUEST = 'reports/v0-s2/authorization-s2-supplemental-01.request.json'
APPROVAL = 'reports/v0-s2/authorization-s2-supplemental-01.approval.json'
REQUEST_SHA = 'f523a7de0949f979eee4884c50e9120f7e8e3095c489a04b6bbcb7967628e957'
SLOT = 'full-supplemental-01'
CLEANUP = 'supplemental-cleanup-01'
HARNESS = 'tools/v0_s2_supplemental.py'
CLEANUP_BUDGET = {'native_commands': 4, 'junction_deletions': 1, 'service_starts': 0, 'model_calls': 0,
    'browser_starts': 0, 'testSource_reads': 0, 'process_terminations': 0}


def authority(candidate, *, require_cleanup):
    from tools import v0_s2_stage_checkpoint as cp
    request = cp.repository_json(REQUEST); approval = cp.repository_json(APPROVAL)
    if (cp.file_hash(cp.ROOT/REQUEST) != REQUEST_SHA or approval.get('request_sha256') != REQUEST_SHA
            or approval.get('status') != 'ACTIVE' or approval.get('granted_by') != 'project_owner'
            or approval.get('authorization_id') != 'AUTH-V1-S2-SUPPLEMENTAL-01'
            or approval.get('grant_statement') != '批准 AUTH-REQUEST-V1-S2-SUPPLEMENTAL-01，按请求文件的完整范围执行，终态后自动过期。'
            or approval.get('additional_complete_native_runs') != 1 or approval.get('additional_full_rechecks') != 0
            or request.get('runtime_budget') != cp.BUDGET or request.get('acceptance_hash') != cp.ACCEPTANCE
            or request.get('forbidden') != cp.FORBIDDEN+['human experience signoff', 'final V1 release signoff', 'V2/V3 execution']):
        raise EvidenceError('supplemental explicit authority is missing, changed or expired')
    cp.program_authority()
    if (cp.file_hash(cp.ROOT/request['offline_receipt']) != request['offline_receipt_sha256']
            or any(cp.file_hash(cp.ROOT/cp.SEEDS[name]) != digest
                for name, digest in request['seed_artifact_sha256'].items())):
        raise EvidenceError('approved baseline or fixed sample/model/SDK seed changed')
    subprocess.run(['git', 'merge-base', '--is-ancestor', request['corrected_candidate'], candidate],
        cwd=cp.ROOT, check=True, timeout=30)
    prefix = subprocess.check_output(['git', 'rev-parse', '--show-prefix'], cwd=cp.ROOT, text=True, timeout=30).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', request['corrected_candidate'], candidate],
        cwd=cp.ROOT, text=True, timeout=30).splitlines()
    allowed = {'tools/v0_s2_stage_checkpoint.py', HARNESS,
        'LVW_V0_RuntimePatch/tests/test_s2_supplemental.py', 'LVW_V0_RuntimePatch/tests/test_s2_stage_checkpoint.py',
        'plans/execution-control.json', 'MANIFEST.sha256'}
    for name in changed:
        if not name.startswith(prefix): raise EvidenceError('supplemental candidate changes outside package')
        relative = name[len(prefix):]
        report_allowed = (relative in (REQUEST, APPROVAL) or relative.startswith(('reports/v0-s2/offline-checkpoint-',
            'reports/v0-s2/supplemental-', 'reports/v0-s2/authorization-supplemental-')))
        if relative not in allowed and not report_allowed and not relative.startswith('.agent-governance/stages/V0-S2/'):
            raise EvidenceError('supplemental descendant changes outside approved transport: '+relative)
    stage_relative = '.agent-governance/stages/V0-S2/stage-control.json'
    old = json.loads(subprocess.check_output(['git', 'show', request['corrected_candidate']+':'+prefix+stage_relative],
        cwd=cp.ROOT, timeout=30))
    current = cp.repository_json(stage_relative)
    if current.get('supplemental_authorization') != {'approval': APPROVAL, 'request': REQUEST,
            'slot': SLOT, 'max_runs': 1, 'max_rechecks': 0}:
        raise EvidenceError('frozen supplemental transport is missing or broadened')
    for value in (old, current):
        value.pop('stage_packet_version', None); value.pop('supplemental_authorization', None)
    if old != current: raise EvidenceError('supplemental amendment changed frozen product obligations')
    for prior in request['prior_failed_runs']:
        report = cp.repository_json(prior['receipt'])
        if cp.file_hash(cp.ROOT/prior['receipt']) != prior['receipt_sha256'] or report.get('decision') != 'NO_GO':
            raise EvidenceError('prior failure changed')
        auth = cp.repository_json('reports/v0-s2/authorization-'+prior['run_id']+'.json')
        if auth.get('status') != 'EXPIRED_NO_GO' or (cp.STATE_ROOT/prior['run_id']/'lease.closed').read_bytes() != b'1':
            raise EvidenceError('prior native attempt not closed')
    if require_cleanup:
        path = cp.ROOT/'reports/v0-s2/authorization-supplemental-cleanup-01.json'
        auth = json.loads(path.read_bytes()); report = cp.repository_json(auth['terminal_receipt'])
        if (auth.get('status') != 'EXPIRED_CLEANUP_PROVEN' or report.get('decision') != 'CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE'
                or report.get('root_absent') is not True or report.get('original_identity_recovered') is not False
                or cp.file_hash(cp.ROOT/auth['terminal_receipt']) != auth.get('terminal_receipt_sha256')
                or auth.get('candidate_sha') != candidate
                or (cp.STATE_ROOT/CLEANUP/'lease.closed').read_bytes() != b'1'):
            raise EvidenceError('supplemental requires proven cleanup on this final candidate')
    return {'approval': APPROVAL, 'approval_sha256': cp.file_hash(cp.ROOT/APPROVAL),
        'request': REQUEST, 'request_sha256': REQUEST_SHA}


def expire(refs, *, decision, terminal):
    from tools import v0_s2_stage_checkpoint as cp
    path = cp.ROOT/refs['approval']
    if cp.file_hash(path) != refs['approval_sha256']: return  # Preserve revocation.
    value = json.loads(path.read_bytes()); value.update(status='EXPIRED_'+decision, terminal=terminal)
    temporary = path.with_suffix('.terminal.tmp'); cp.write_new(temporary, value); os.replace(temporary, path)


def prepare_cleanup(candidate, offline):
    from tools import v0_s2_stage_checkpoint as cp
    refs = authority(candidate, require_cleanup=False)
    identity = cp.source_gate(candidate, offline)
    path = cp.ROOT/'reports/v0-s2/authorization-supplemental-cleanup-01.json'
    if (cp.STATE_ROOT/CLEANUP).exists(): raise EvidenceError('cleanup already claimed; never retry')
    request = cp.repository_json(REQUEST)
    now = time.time()
    value = {'schema_version': 'lvw.cleanup-child/1', 'status': 'ACTIVE_ONE_SHOT', 'run_id': CLEANUP,
        'candidate_sha': candidate, 'payload_sha256': identity['payload_sha256'], 'harness_sha256': cp.file_hash(cp.ROOT/HARNESS),
        'offline_receipt': offline, 'offline_receipt_sha256': cp.file_hash(cp.ROOT/offline),
        'program_sha256': cp.program_authority(), 'supplemental_authorization': refs,
        'scope': request['retained_root_cleanup'], 'issued_at': now, 'expires_at': now+900,
        'budget': dict(CLEANUP_BUDGET), 'stage_pass_claim': False}
    cp.write_new(path, value)
    return value


def retained_expected(cp, original):
    """Repository/recorded bytes only, never reopen testSource or installed code."""
    active = cp.STATE_ROOT/'full-recheck-01/active-child.json'
    if cp.file_hash(active) != original['authorization_sha256']:
        raise EvidenceError('original active child changed')
    prior = json.loads(active.read_bytes())
    offline = cp.repository_json(prior['offline_receipt'])
    if cp.file_hash(cp.ROOT/prior['offline_receipt']) != prior['offline_receipt_sha256']:
        raise EvidenceError('original code binding changed')
    if offline['candidate_sha'] != original['candidate_sha']:
        raise EvidenceError('retained code belongs to a different candidate')
    prefix = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
    expected = {'custom_nodes/lvw_v0_bridge/'+name[len(prefix):]: {'sha256': digest}
        for name, digest in offline['identity']['execution_artifact_sha256'].items() if name.startswith(prefix)}
    seeds = cp.seed_values(); samples = seeds['targets']['samples']
    for kind, suffix in [('image', '.jpg'), ('video', '.mp4')]:
        row = next(row for row in samples if row['suffix'] == suffix)
        expected['input/authorized-'+kind+suffix] = {'sha256': row['sha256'], 'bytes': row['bytes']}
    plan = cp.repository_json('reports/v0-s2/frozen-structural-inputs-02.json')
    for category in ('categories', 'negatives'):
        for row in plan[category].values():
            expected['input/s2-'+Path(row['path']).name] = {'sha256': row['sha256'], 'bytes': row['bytes']}
    row = plan['categories']['static']; expected['outside-input/source.mp4'] = {'sha256': row['sha256'], 'bytes': row['bytes']}
    expected['input/empty.mp4'] = {'sha256': hashlib.sha256(b'').hexdigest(), 'bytes': 0}
    expected['input/oversize.mp4'] = {'bytes': 256*1024**2+1, 'deliberate_oversize_fixture': True}
    if not expected: raise EvidenceError('original file closure empty')
    return expected


def check_retained_tree(archive, root, expected):
    from tools.v0_s2_execution_bindings import hashed_file, stamp
    rows, directories = archive.inventory(root, exclusions=False)
    if set(rows) != set(expected)|{'input/redirect'} or rows['input/redirect'][0] != 'redirect':
        raise EvidenceError('retained root has unknown/missing entries')
    allowed_dirs = {root, root/'input', root/'output', root/'temp', root/'custom_nodes', root/'outside-input'}
    for relative in expected:
        allowed_dirs.update((root/relative).parents)
    if any(path not in allowed_dirs for path in directories): raise EvidenceError('unknown retained directory')
    for name, spec in expected.items():
        kind, path, observed = rows[name]
        if kind != 'file' or ('bytes' in spec and observed[2] != spec['bytes']):
            raise EvidenceError('retained file type/size changed')
        if not spec.get('deliberate_oversize_fixture'):
            digest, _ = hashed_file(path, observed, time.monotonic()+30)
            if digest != spec['sha256'] or stamp(path) != observed: raise EvidenceError('retained file bytes changed')
    return rows


def cleanup():
    from tools import v0_s2_stage_checkpoint as cp
    from tools.v0_s2_stage_archive import OwnedArchive
    from tools.v0_s2_driver import S2SystemDriver
    from tools.v0_s2_execution_bindings import plain
    path = cp.ROOT/'reports/v0-s2/authorization-supplemental-cleanup-01.json'
    raw = path.read_bytes(); auth = json.loads(raw)
    refs = authority(auth['candidate_sha'], require_cleanup=False)
    if (auth.get('schema_version') != 'lvw.cleanup-child/1' or auth.get('run_id') != CLEANUP
            or auth.get('budget') != CLEANUP_BUDGET or auth.get('stage_pass_claim') is not False
            or any(type(v) is not int for v in auth.get('budget', {}).values())
            or not 0 < auth['expires_at']-auth['issued_at'] <= 900
            or auth.get('status') != 'ACTIVE_ONE_SHOT' or refs != auth['supplemental_authorization']
            or auth['scope'] != cp.repository_json(REQUEST)['retained_root_cleanup']
            or auth['harness_sha256'] != cp.file_hash(cp.ROOT/HARNESS)
            or auth['program_sha256'] != cp.program_authority()
            or cp.file_hash(cp.ROOT/auth['offline_receipt']) != auth['offline_receipt_sha256']
            or not auth['issued_at'] <= time.time() < auth['expires_at']
            or cp.source_gate(auth['candidate_sha'], auth['offline_receipt'])['payload_sha256'] != auth['payload_sha256']):
        raise EvidenceError('cleanup child not bound/current')
    directory = cp.STATE_ROOT/CLEANUP; directory.mkdir(exist_ok=False)
    cp.write_new(directory/'active-child.json', auth)
    with (directory/'lease.closed').open('xb') as output: output.write(b'0'); output.flush(); os.fsync(output.fileno())
    result = {'run_id': CLEANUP, 'candidate_sha': auth['candidate_sha'], 'authorization_sha256': hashlib.sha256(raw).hexdigest(),
        'decision': 'NO_GO', 'original_identity_recovered': False, 'explicit_adoption': True,
        'native_commands': 0, 'model_calls': 0, 'service_starts': 0, 'stage_pass_claim': False}
    commands = []
    def guard(action, detail):
        if (path.read_bytes() != raw or cp.file_hash(cp.ROOT/APPROVAL) != refs['approval_sha256']
                or cp.file_hash(cp.ROOT/REQUEST) != REQUEST_SHA or time.time() >= auth['expires_at']):
            raise EvidenceError('cleanup revoked/expired; preserve root')
        root = Path(auth['scope']['wsl_path']); info = root.lstat()
        if (str(info.st_dev), str(info.st_ino)) != (auth['scope']['observed_device'], auth['scope']['observed_inode']):
            raise EvidenceError('adopted root identity changed')
    try:
        guard('before_owned_root_read', None)
        root = plain(Path(auth['scope']['wsl_path']))
        expected_root = cp.STATE_ROOT/'full-recheck-01/lvw-s2-default-ccmmyy5d'
        if root != expected_root: raise EvidenceError('cleanup root outside exact grant')
        old_directory = root.parent
        original = json.loads((old_directory/'terminal.json').read_bytes())
        public = cp.repository_json('reports/v0-s2/full-recheck-01/receipt.json')
        if cp.file_hash(old_directory/'terminal.json') != public['raw_terminal_sha256']:
            raise EvidenceError('old raw terminal changed')
        snapshot = json.loads((old_directory/'installed-bindings.json').read_bytes())
        manifest = hashlib.sha256(json.dumps(snapshot['files'], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        if manifest != original['runtime_evidence']['default']['binding_proof']['manifest_sha256']:
            raise EvidenceError('original installed manifest changed')
        expected_ps = next(row['sha256'] for row in snapshot['files'] if row['alias'] == 'POWERSHELL')
        ps = plain(Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'))
        if cp.file_hash(ps) != expected_ps: raise EvidenceError('cleanup native helper changed')
        driver = S2SystemDriver(SimpleNamespace(run_id=CLEANUP, powershell=str(ps), max_public_submissions=1),
            {'owned_run_root': str(root), 'reparse_fixture_creation_attempted': True})
        deletions = 0
        def native(script):
            nonlocal deletions
            guard('native_cleanup_helper', None)
            if len(commands) >= 4: raise EvidenceError('cleanup native command budget exceeded')
            if cp.file_hash(ps) != expected_ps: raise EvidenceError('cleanup helper bytes changed')
            if script.startswith('[System.IO.Directory]::Delete('):
                if deletions >= 1: raise EvidenceError('cleanup junction deletion budget exceeded')
                deletions += 1
            elif not script.startswith('$item=Get-Item -LiteralPath '):
                raise EvidenceError('unexpected native cleanup command')
            script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"+script
            row = {'argv': [str(ps), '-NoProfile', '-NonInteractive', '-Command', script], 'exit_code': None}
            commands.append(row); cp.write_new(directory/('command-'+str(len(commands))+'.json'), row)
            process = subprocess.run(row['argv'], capture_output=True, timeout=60)
            for label in ('stdout', 'stderr'):
                data = getattr(process, label); (directory/('command-'+str(len(commands))+'.'+label+'.log')).write_bytes(data)
                row[label+'_sha256'] = hashlib.sha256(data).hexdigest()
            row['exit_code'] = process.returncode
            if process.returncode: raise EvidenceError('native cleanup helper failed')
            return process.stdout.decode('utf-8-sig', 'strict').strip()
        driver._powershell = native
        if cp.windows_path(auth['scope']['windows_path']) != root:
            raise EvidenceError('approved native and WSL root spellings disagree')
        def literal_native(value, **kwargs):
            relative = Path(value).relative_to(root)
            if '..' in relative.parts: raise EvidenceError('cleanup conversion escaped root')
            return auth['scope']['windows_path'].rstrip('\\/')+'/'+relative.as_posix()
        driver._windows_path = literal_native
        archive = OwnedArchive(directory, run_id=CLEANUP, candidate_sha=auth['candidate_sha'],
            authorization_sha256=result['authorization_sha256'], authorize=guard)
        # Explicitly adopted CURRENT identity, not register() and not a claim of
        # recovering the missing original empty-root lease.
        info = root.lstat(); archive.leases['default'] = (root, info.st_dev, info.st_ino)
        cp.write_new(directory/'explicit-current-root-adoption.json', {'root': str(root), 'device': str(info.st_dev),
            'inode': str(info.st_ino), 'original_identity_recovered': False, 'approval': refs})
        expected = retained_expected(cp, original); check_retained_tree(archive, root, expected)
        cp.write_new(directory/'retained-file-closure.json', expected)
        guard('before_archive', None)
        failure = json.loads((old_directory/'default-preparation-failure.json').read_bytes())
        if (failure['cleanup'].get('owned_count') != 0 or original['sequence'].get('error_code') != 'StopProbe:REPARSE_NATIVE_IDENTITY_MISMATCH'
                or original['runtime_evidence']['default'].get('preflight') is not None):
            raise EvidenceError('original failure was not pre-service')
        context = SimpleNamespace(root=root, binding={'candidate_sha': auth['candidate_sha'],
            'authorization_sha256': result['authorization_sha256']}, driver=driver)
        driver.listener_proofs = {}; driver.owned = []
        result['archive'] = archive(context, failure['cleanup'])
        result['junction_deletions'] = deletions
        result['root_absent'] = not root.exists()
        if result['archive'].get('proven') is not True or not result['root_absent']: raise EvidenceError('cleanup root not absent')
        result['decision'] = 'CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE'
    except BaseException as error:
        result['error_code'] = type(error).__name__+':'+str(error)
    finally:
        result['native_commands'] = len(commands); result['commands'] = commands
        with (directory/'lease.closed').open('r+b') as output: output.write(b'1'); output.flush(); os.fsync(output.fileno())
        published = False; public_dir = cp.ROOT/'reports/v0-s2'/CLEANUP
        try:
            cp.write_new(directory/'terminal.json', result)
            public_dir.mkdir(exist_ok=False)
            public = cp.base.redact_value(result, {str(cp.ROOT): 'PACK_ROOT', str(cp.STATE_ROOT): 'STATE'})
            public['raw_terminal_sha256'] = cp.file_hash(directory/'terminal.json')
            cp.write_new(public_dir/'receipt.json', public); published = True
        finally:
            auth['status'] = 'EXPIRED_CLEANUP_PROVEN' if published and result['decision'].startswith('CLEANUP_PROVEN') else 'EXPIRED_NO_GO'
            if published:
                auth.update(terminal_receipt=str((public_dir/'receipt.json').relative_to(cp.ROOT)),
                    terminal_receipt_sha256=cp.file_hash(public_dir/'receipt.json'))
            try:
                if path.read_bytes() == raw:
                    temporary = path.with_suffix('.terminal.tmp'); cp.write_new(temporary, auth); os.replace(temporary, path)
            finally:
                if auth['status'] == 'EXPIRED_NO_GO':
                    expire(refs, decision='NO_GO', terminal=auth.get('terminal_receipt', 'STATE/'+CLEANUP+'/terminal.json'))

    return result


def main():
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest='command', required=True)
    ready = commands.add_parser('prepare-cleanup'); ready.add_argument('--candidate', required=True); ready.add_argument('--offline-receipt', required=True)
    commands.add_parser('cleanup')
    args = parser.parse_args()
    result = prepare_cleanup(args.candidate, args.offline_receipt) if args.command == 'prepare-cleanup' else cleanup()
    print(json.dumps({key: result.get(key) for key in ('run_id', 'status', 'decision', 'error_code')}))
    return int(result.get('decision', '').startswith('NO_GO'))


if __name__ == '__main__': raise SystemExit(main())
