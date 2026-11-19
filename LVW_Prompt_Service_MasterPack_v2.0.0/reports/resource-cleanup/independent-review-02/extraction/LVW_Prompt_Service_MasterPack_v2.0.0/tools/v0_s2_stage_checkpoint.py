"""One-shot full S2 checkpoint under AUTH-PROGRAM-V1-LOCAL-01.

`prepare` reads repository evidence only and creates a finite child. `execute`
claims that child before any installed-code/sample query, binds actual bytes,
and runs the public/native/default/warm sequence. Terminal evidence never grants
Stage PASS, independent review, human signature or another attempt.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time

from tools.v0_s2_bindings import ROOT, SOURCE, TARGETS, file_hash
from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools.v0_s2_execution_bindings import ExecutionBindings, Tree, plain, hashed_file, stamp
from tools.v0_s2_stage_inputs import load_fixture_set, read_bound
from tools.v0_s2_stage_runtime import StageRuntimeFactory, TOOL_KEYS
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_stage_sequence import StageSequence
from tools.v0_s2_runtime import read_jsonl
from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_driver import base

from tools import v0_s2_supplemental as supplemental
from tools import v0_s2_resource_admission as resource_admission
from tools import v0_s2_oracle_authorization as oracle_authorization
from tools import v0_s2_policy_authorization as policy_authorization
from tools import v0_s2_lifecycle_authorization as lifecycle_authorization
from tools import v0_s2_automatic_verification as automatic_verification

HARNESS = 'tools/v0_s2_stage_checkpoint.py'
PROGRAM = 'reports/authorization-program-v1-local-01.json'
PROGRAM_ID = 'AUTH-PROGRAM-V1-LOCAL-01'
ACCEPTANCE = '32a72139e0c12e0e6d040274024b53bb2dba2f2864b68b840aa215cf739a2a7f'
STATE_ROOT = ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/V0-S2'
GLOBAL_NODE_ROOT = Path('/home/administrator/.npm-global/lib/node_modules')
BROWSER_CACHE_ROOT = Path('/home/administrator/.cache/ms-playwright')
SEEDS = {'targets': 'reports/v0-s2/binding-inventory-06/receipt.json',
    'frontend': 'reports/v0-s2/frontend-bindings-02/receipt.json',
    'packages': 'reports/v0-s2/native-decoder-packages-01/receipt.json',
    'model': 'reports/r1a/authorization-wp-r1a-04-live-08.json'}
SOURCE_PAYLOAD = ['tools', 'LVW_V0_RuntimePatch', 'contracts', 'config',
    'reports/v0-s2/browser-draft-oracle-correction-01/initial-manual-export.json',
    '.agent-governance/stages/V0-S2', 'plans/acceptance_cases.json', 'plans/release_gates.json',
    'reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py', 'reports/v0-s1/wp-s1-03-phase-a/live_probe.py',
    'reports/v0-s2/frozen-structural-inputs-02.json', 'reports/v0-s2/fixture-preparation-02',
    'reports/v0-s2/authorization-fixtures-02.json', 'reports/v0-s2/offline-checkpoint-10/receipt.json',
    PROGRAM, supplemental.REQUEST, supplemental.APPROVAL, resource_admission.REQUEST, resource_admission.APPROVAL, oracle_authorization.REQUEST, oracle_authorization.APPROVAL, oracle_authorization.RESUME_REQUEST, oracle_authorization.RESUME_APPROVAL, policy_authorization.REQUEST, policy_authorization.DECISION, policy_authorization.APPROVAL, lifecycle_authorization.REQUEST, lifecycle_authorization.APPROVAL, 'reports/authorization-program-v0-local-verification-01.json', 'reports/v0-s2/wddm-shared-capacity-decision-01.md', 'reports/v0-s2/response-bounds-correction-01/failed-response.json', *SEEDS.values()]
BUDGET = {'stage_checkpoints': 1, 'public_submissions': 65, 'default_public_submissions': 45,
    'warm_public_submissions': 20, 'provider_calls': 83, 'comfy_starts': 2, 'ollama_starts': 2,
    'browser_starts': 1, 'warm_preloads': 20, 'loopback_requests_per_runtime': 8192,
    'metadata_commands': 2, 'native_clock_reads_per_runtime': 128, 'resource_sampler_workers': 3,
    'resource_sampler_max_seconds': 7200, 'frame_decoder_processes': 80, 'metadata_probe_processes': 24,
    'installed_files_per_snapshot': 100000, 'installed_bytes_per_snapshot': 32*1024**3,
    'installed_full_snapshots': 5, 'sample_files': 2, 'sample_bytes': 276*1024**2,
    'downloads': 0, 'cloud_calls': 0, 'paid_calls': 0, 'max_seconds': 21600}
RESERVED = frozenset(('archive_owned_terminal_root', 'remove_owned_terminal_reparse_fixture'))
FORBIDDEN = ['non-loopback', 'cloud', 'paid-service', 'download', 'private-media', 'cookie',
    'existing-browser-profile', 'visible-browser-automation', 'permanent-configuration', 'non-owned-termination', 'remote-push', 'release']


def canonical(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def write_new(path, value):
    with Path(path).open('xb') as output: output.write(canonical(value)); output.flush(); os.fsync(output.fileno())


def repository_json(relative, *, limit=8*1024**2):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative: raise EvidenceError('repository evidence path invalid')
    target = plain(ROOT/path)
    if target.stat().st_size > limit: raise EvidenceError('repository evidence size limit')
    return json.loads(target.read_bytes())


def seed_values():
    values = {name: repository_json(path) for name, path in SEEDS.items()}
    front = values['frontend']
    if front.get('decision') != 'INSTALLED_BINDINGS_COLLECTED_NOT_NATIVE_ACCEPTANCE':
        raise EvidenceError('historical frontend identity observation missing')
    if values['model'].get('model') != base.MODEL or not re.fullmatch('[a-f0-9]{64}', values['model'].get('model_digest', '')):
        raise EvidenceError('historical exact model identity missing')
    # The target inventory's historical NO_GO is not acceptance evidence. Only
    # its observed bytes are used as expected identities for fresh verification.
    return values


def source_gate(candidate, offline_relative):
    if not re.fullmatch(r'reports/v0-s2/offline-checkpoint-[0-9]{2}/receipt[.]json', offline_relative):
        raise EvidenceError('full offline receipt path invalid')
    identity = seal_candidate(ROOT, candidate, SOURCE_PAYLOAD)
    receipt = repository_json(offline_relative)
    expected_names = ['v0_subtree', 'native_ui_module', 'pack_contracts', 'governance', 'whitespace']
    checks = receipt.get('check_results', [])
    if (receipt.get('schema_version') != 'lvw.s2.offline-checkpoint/1'
            or receipt.get('decision') != 'OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE'
            or receipt.get('stage_pass_claim') is not False or receipt.get('acceptance_hash') != ACCEPTANCE
            or receipt.get('preflight_status') != 'PASS' or receipt.get('live_stage_checkpoint_consumed') is not False
            or [row.get('name') for row in checks] != expected_names
            or any(row.get('passed') is not True or type(row.get('exit_code')) is not int or row['exit_code'] != 0 for row in checks)
            or type(checks[0].get('unit_tests_executed')) is not int or checks[0]['unit_tests_executed'] < 368):
        raise EvidenceError('fresh complete offline checks are not proven')
    for row in checks:
        for stream in ('stdout', 'stderr'):
            raw = read_bound(row[stream+'_artifact'], row[stream+'_artifact_sha256'], limit=8*1024**2)
            if row['name'] == 'v0_subtree' and stream == 'stderr':
                text = raw.decode('utf-8', 'strict'); counts = re.findall(r'^Ran ([0-9]+) tests? in ', text, re.M)
                if counts != [str(row['unit_tests_executed'])] or not re.search(r'^OK\s*$', text, re.M):
                    raise EvidenceError('offline raw unit execution summary differs')
    for path, digest in identity['execution_artifact_sha256'].items():
        if receipt['identity']['execution_artifact_sha256'].get(path) != digest:
            raise EvidenceError('current execution payload is not covered by full offline gate: '+path)
    if receipt['identity']['candidate_sha'] != receipt['candidate_sha']:
        raise EvidenceError('offline candidate identity inconsistent')
    return identity


def program_authority():
    program = repository_json(PROGRAM)
    coordinate = repository_json('plans/execution-control.json')
    if (program.get('status') != 'ACTIVE' or program.get('authorization_id') != PROGRAM_ID
            or coordinate.get('coordinate', {}).get('stage_id') != 'V0-S2'
            or coordinate.get('external_execution_hold', {}).get('active') is True
            or 'V0-S2' not in program.get('stages', [])
            or program.get('child_authorization_policy', {}).get('stage_checkpoint_limit') != 1
            or program['child_authorization_policy'].get('corrected_candidate_full_recheck_limit') != 1):
        raise EvidenceError('WAIT_AUTH: Mother program is not active with frozen Stage limits')
    return file_hash(ROOT/PROGRAM)


def child_path(slot):
    if not automatic_verification.is_slot(slot) and slot not in ('full-checkpoint-01', 'full-recheck-01', supplemental.SLOT, resource_admission.SLOT, oracle_authorization.SLOT, lifecycle_authorization.SLOT): raise EvidenceError('WAIT_AUTH: no further Stage slot')
    return ROOT/'reports/v0-s2'/('authorization-'+slot+'.json')


@contextmanager
def slot_guard(slot):
    """Serialize grant replacement and atomic claim; kernel releases on exit."""
    child_path(slot)
    control = STATE_ROOT/'.control'; control.mkdir(parents=True, exist_ok=True); plain(control)
    descriptor = os.open(control/(slot+'.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try: fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error: raise EvidenceError('slot grant/claim operation already active') from error
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN); os.close(descriptor)


@contextmanager
def complete_admission_guard():
    """Serialize admission across every complete slot, including legacy slots."""
    control=STATE_ROOT/'.control';control.mkdir(parents=True,exist_ok=True);plain(control)
    descriptor=os.open(control/'full-stage-admission.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise EvidenceError('another complete admission is active') from error
        yield
    finally:
        fcntl.flock(descriptor,fcntl.LOCK_UN);os.close(descriptor)


def claim_run(slot,auth,raw):
    with complete_admission_guard(),slot_guard(slot):
        automatic_verification.require_closed_runs()
        if child_path(slot).read_bytes()!=raw:raise EvidenceError('grant changed before atomic claim')
        directory=STATE_ROOT/slot;directory.mkdir(exist_ok=False)
        write_new(directory/'active-child.json',auth)
        with (directory/'lease.closed').open('xb') as output:output.write(b'0');output.flush();os.fsync(output.fileno())
        return directory


def slot_authority(slot, candidate):
    child_path(slot)
    if automatic_verification.is_slot(slot):
        return automatic_verification.authority(slot, candidate)
    if slot == lifecycle_authorization.SLOT:
        return lifecycle_authorization.authority(candidate, require_ready=True)
    if slot == oracle_authorization.SLOT:
        if ((ROOT/'plans/execution-control.json').exists()
                and repository_json('plans/execution-control.json').get('policy_correction_authorization') == policy_authorization.APPROVAL):
            return policy_authorization.authority(candidate, require_ready=True)
        if ((ROOT/'plans/execution-control.json').exists()
                and repository_json('plans/execution-control.json').get('resource_resume_authorization') == oracle_authorization.RESUME_APPROVAL):
            return oracle_authorization.resume_authority(candidate, require_ready=True)
        return oracle_authorization.authority(candidate, require_ready=True)
    if slot == resource_admission.SLOT:
        return resource_admission.authority(candidate, require_ready=True)
    if slot == supplemental.SLOT:
        return supplemental.authority(candidate, require_cleanup=True)
    if slot == 'full-checkpoint-01':
        if child_path('full-recheck-01').exists(): raise EvidenceError('Stage attempt order invalid')
        return
    previous = repository_json('reports/v0-s2/authorization-full-checkpoint-01.json')
    if (previous.get('status') != 'EXPIRED_NO_GO' or previous.get('candidate_sha') == candidate
            or previous.get('terminal_receipt') != 'reports/v0-s2/full-checkpoint-01/receipt.json'):
        raise EvidenceError('corrected recheck requires a terminal failed different candidate')
    receipt = repository_json(previous['terminal_receipt'])
    if (file_hash(ROOT/previous['terminal_receipt']) != previous.get('terminal_receipt_sha256')
            or receipt.get('decision') != 'NO_GO' or receipt.get('stage_checkpoint_consumed') is not True
            or receipt.get('candidate_sha') != previous['candidate_sha']):
        raise EvidenceError('initial terminal failure evidence is incomplete')
    subprocess.run(['git', 'merge-base', '--is-ancestor', previous['candidate_sha'], candidate], cwd=ROOT, check=True, timeout=30)


def prepare(slot, candidate, offline_relative, *, replace_unclaimed=False):
    path = child_path(slot)
    previous_raw = path.read_bytes() if path.exists() else None
    if (STATE_ROOT/slot).exists() or (ROOT/'reports/v0-s2'/slot).exists():
        raise EvidenceError('claimed/terminal slot can never be replaced or restarted')
    if previous_raw is not None:
        previous = json.loads(previous_raw)
        if (not replace_unclaimed or previous.get('status') != 'ACTIVE_ONE_SHOT' or previous.get('run_id') != slot
                or previous.get('source_program_authorization') != PROGRAM_ID or previous.get('budget') != BUDGET
                or previous.get('candidate_sha') == candidate):
            raise EvidenceError('unclaimed replacement needs explicit flag and corrected source')
        subprocess.run(['git', 'merge-base', '--is-ancestor', previous['candidate_sha'], candidate], cwd=ROOT, check=True, timeout=30)
    elif replace_unclaimed: raise EvidenceError('no unclaimed grant exists to replace')
    additional_authority = slot_authority(slot, candidate)
    program_sha = program_authority(); identity = source_gate(candidate, offline_relative); seeds = seed_values()
    now = time.time()
    auth = {'schema_version': 'lvw.program-child-authorization/1', 'authorization_id': 'AUTH-V0-S2-'+slot.upper()+'-'+secrets.token_hex(8),
        'project_id': 'lvw-prompt-service', 'issued_by': 'codex_gate_owner',
        'source_program_authorization': PROGRAM_ID, 'program_sha256': program_sha,
        'stage_id': 'V0-S2', 'workpack_id': 'WP-S2-05', 'scope': 'COMPLETE_FIXED_NATIVE_STAGE_CHECKPOINT',
        'status': 'ACTIVE_ONE_SHOT', 'run_id': slot, 'candidate_sha': candidate,
        'harness_sha256': file_hash(ROOT/HARNESS), 'payload_sha256': identity['payload_sha256'],
        'offline_receipt': offline_relative, 'offline_receipt_sha256': file_hash(ROOT/offline_relative),
        'acceptance_hash': ACCEPTANCE, 'issued_at': now, 'expires_at': now+BUDGET['max_seconds'],
        'budget': dict(BUDGET), 'ports': [8191, 11434], 'endpoints': [base.COMFY_URL, base.OLLAMA_URL],
        'driver_port_policy': 'one fresh worker-owned literal 127.0.0.1 listener, proven before connect',
        'state_root': str(STATE_ROOT), 'samples': seeds['targets']['samples'],
        'installed_roots': {'global_node': str(GLOBAL_NODE_ROOT), 'browser_cache': str(BROWSER_CACHE_ROOT),
            **{name: str(value.parent) for name, value in TARGETS.items()}},
        'model': {'name': base.MODEL, 'digest': seeds['model']['model_digest']},
        'seed_sha256': {name: file_hash(ROOT/relative) for name, relative in SEEDS.items()},
        'process_policy': 'two original native Ollama/Comfy lineages, three owned resource workers, one original Node/headless lineage; declared CPU FFmpeg/PyAV children; bounded read-only metadata helpers',
        'cleanup_policy': 'reprove original owned births; reserved terminal cleanup/archive even after expiry; never terminate foreign or reused PIDs; preserve uncertain roots; expire this child after terminal receipt',
        'forbidden': list(FORBIDDEN),
        'stage_pass_claim': False, 'external_cost': 0}
    if additional_authority and 'expires_at' in additional_authority:
        auth['expires_at'] = min(auth['expires_at'], additional_authority['expires_at'])
    auth['supplemental_authorization'] = additional_authority
    auth['previous_unclaimed_authorization_sha256'] = hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None
    if previous_raw is None: write_new(path, auth)
    else:
        with slot_guard(slot):
            if ((STATE_ROOT/slot).exists() or (ROOT/'reports/v0-s2'/slot).exists() or path.read_bytes() != previous_raw):
                raise EvidenceError('grant changed or claim began; replacement refused')
            history = ROOT/'reports/v0-s2/unclaimed-authorizations'; history.mkdir(exist_ok=True)
            digest = hashlib.sha256(previous_raw).hexdigest(); old = history/(slot+'-'+digest+'.json')
            with old.open('xb') as output: output.write(previous_raw); output.flush(); os.fsync(output.fileno())
            write_new(history/(slot+'-'+digest+'.superseded.json'), {
                'kind': 'UNCLAIMED_SOURCE_GRANT_SUPERSESSION_NOT_EXECUTION', 'stage_checkpoint_consumed': False,
                'status': 'EXPIRED_UNCLAIMED_SOURCE_SUPERSEDED',
                'old_authorization_sha256': digest, 'new_authorization_sha256': hashlib.sha256(canonical(auth)).hexdigest(),
                'old_candidate_sha': previous['candidate_sha'], 'new_candidate_sha': candidate,
                'old_grant_is_authorization': False, 'reason': 'offline source correction before any claim/target query'})
            temporary = path.with_suffix('.replacement.tmp'); write_new(temporary, auth); os.replace(temporary, path)
    return auth


class ChildLease:
    def __init__(self, path, raw):
        self.path = path; self.raw = raw; self.auth = json.loads(raw); self.lock = threading.Lock()
        self.actions = 0; self.directory = None; self.closed = False

    def authorize(self, action, detail):
        with self.lock:
            # Cleanup is reserved for the originally claimed root, not a fresh
            # service/model operation. Do not prevent cleanup after revocation.
            if action not in RESERVED:
                if (self.closed or (self.directory is not None and (self.directory/'lease.closed').read_bytes() != b'0')
                        or self.path.read_bytes() != self.raw or file_hash(ROOT/PROGRAM) != self.auth['program_sha256']
                        or repository_json('plans/execution-control.json').get('coordinate', {}).get('stage_id') != 'V0-S2'
                        or repository_json('plans/execution-control.json').get('external_execution_hold', {}).get('active') is True
                        or not self.auth['issued_at'] <= time.time() < self.auth['expires_at']):
                    raise EvidenceError('child changed, revoked or expired; new work denied')
            if action not in RESERVED and self.auth.get('supplemental_authorization'):
                refs = self.auth['supplemental_authorization']
                if (time.time() >= refs.get('expires_at', self.auth['expires_at'])
                        or file_hash(ROOT/refs['approval']) != refs['approval_sha256']
                        or file_hash(ROOT/refs['request']) != refs['request_sha256']):
                    raise EvidenceError('supplemental authority revoked or changed')
            self.actions += 1
            if self.actions > 100000 and action not in RESERVED: raise EvidenceError('parent action budget exhausted')
            if self.directory is not None:
                row = {'ordinal': self.actions, 'action': action, 'detail_sha256': hashlib.sha256(canonical(detail)).hexdigest(),
                    'reserved_cleanup': action in RESERVED, 'wall_seconds': time.time()}
                with (self.directory/'parent-actions.jsonl').open('ab') as output:
                    output.write(canonical(row)); output.flush()

    def close(self):
        with self.lock:
            self.closed = True
            # This byte was allocated before any target query. Terminal expiry
            # does not depend on allocating a larger receipt on a full disk.
            with (self.directory/'lease.closed').open('r+b') as output:
                output.seek(0); output.write(b'1'); output.flush(); os.fsync(output.fileno())


def windows_path(value):
    normalized = str(value).replace('\\', '/')
    match = re.fullmatch(r'([A-Za-z]):/(.+)', normalized)
    if not match or '..' in Path(match[2]).parts: raise EvidenceError('native metadata path invalid')
    return Path('/mnt/'+match[1].lower())/match[2]


def resolve_installed(lease, seeds):
    """No imports of installed Python/SDK, only two declared metadata commands."""
    lease.authorize('resolve_declared_installed_tools', None)
    node = plain(Path(shutil.which('node') or '').resolve(strict=True))
    commands = seeds['frontend']['metadata_commands']
    if (file_hash(node) != commands[1]['executable_sha256']
            or hashlib.sha256((str(GLOBAL_NODE_ROOT)+'\n').encode()).hexdigest() != commands[0]['stdout_original_sha256']):
        raise EvidenceError('installed Node or frozen global-root observation changed')
    # Pin the path actually observed in frontend-bindings-02; npm's executable
    # location is not its configured global prefix. Do not read private npmrc.
    global_root = plain(GLOBAL_NODE_ROOT)
    env = {'PATH': str(node.parent)+':/usr/bin:/bin', 'LANG': 'C.UTF-8', 'NO_PROXY': '127.0.0.1,localhost',
        'NODE_PATH': str(global_root), 'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1'}
    script = "const p=require('path');const entry=require.resolve(process.env.NODE_PATH+'/playwright');console.log(JSON.stringify({entry,core:require.resolve('playwright-core/package.json',{paths:[p.dirname(entry)]})}));"
    metadata = []
    def query(argv, *, environment=None):
        lease.authorize('installed_metadata_command', len(metadata)+1)
        if len(metadata) >= BUDGET['metadata_commands']: raise EvidenceError('metadata command budget exceeded')
        row = {'argv': argv, 'executable_sha256': file_hash(Path(argv[0])), 'ordinal': len(metadata)+1}; metadata.append(row)
        label = 'metadata-'+str(row['ordinal']).zfill(2)
        write_new(lease.directory/(label+'.command.json'), row)
        try:
            process = subprocess.run(argv, capture_output=True, timeout=30, env=environment)
            stdout, stderr = process.stdout, process.stderr
            row.update(exit_code=process.returncode, command_terminal=True)
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            row.update(exit_code=124, command_terminal=False, error_code='METADATA_TIMEOUT_NATIVE_CLEANUP_NOT_ASSUMED')
        for stream, data in (('stdout', stdout), ('stderr', stderr)):
            row[stream+'_sha256'] = hashlib.sha256(data).hexdigest()
            row[stream+'_bytes'] = len(data)
            if len(data) <= 65536:
                row[stream+'_file'] = label+'.'+stream+'.log'
                with (lease.directory/row[stream+'_file']).open('xb') as output: output.write(data)
            else: row[stream+'_oversize_not_retained'] = True
        write_new(lease.directory/(label+'.result.json'), row)
        if row['exit_code']: raise EvidenceError('installed metadata command failed/timeout')
        if max(len(stdout), len(stderr)) > 65536: raise EvidenceError('metadata output limit')
        return stdout.decode('utf-8-sig', 'strict').strip()
    modules = json.loads(query([str(node), '-e', script], environment=env))
    entry = plain(Path(modules['entry'])); core = plain(Path(modules['core']).parent); playwright = entry.parent
    if not playwright.is_relative_to(global_root) or not core.is_relative_to(global_root):
        raise EvidenceError('installed SDK is outside declared global root')
    powershell = plain(Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'))
    with powershell.open('rb') as stream:
        if stream.read(2) != b'MZ': raise EvidenceError('native PowerShell executable invalid')
    command = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';[ordered]@{nvidia=(Get-Command nvidia-smi -CommandType Application -ErrorAction Stop).Source;ollama_key_present=(Test-Path -LiteralPath ($env:USERPROFILE+'/.ollama/id_ed25519'))}|ConvertTo-Json -Compress"
    native = json.loads(query([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command]))
    if native.get('ollama_key_present') is not True: raise EvidenceError('Ollama startup would create permanent key configuration')
    nvidia = plain(windows_path(native['nvidia']))
    if nvidia.name.lower() != 'nvidia-smi.exe': raise EvidenceError('native telemetry executable name invalid')
    binary_rows = [row for row in seeds['frontend']['browser_binaries']
        if row['alias'].startswith('BROWSER_CACHE/chromium-') and row['alias'].endswith('/chrome')]
    if len(binary_rows) != 1: raise EvidenceError('frozen full Chromium binary is ambiguous')
    browser = plain(BROWSER_CACHE_ROOT/binary_rows[0]['alias'].removeprefix('BROWSER_CACHE/'))
    paths = {'comfy_main': TARGETS['COMFY_MAIN'], 'comfy_python': TARGETS['COMFY_PYTHON'],
        'ollama_exe': TARGETS['OLLAMA_EXE'], 'ffmpeg_exe': TARGETS['COMFY_PYTHON'].parent/'Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe',
        'powershell': powershell, 'node_executable': node, 'nvidia_exe': nvidia,
        'playwright_module': entry, 'browser_executable': browser}
    for path in paths.values(): plain(path)
    trees = {'COMFY_ROOT': Tree(paths['comfy_main'].parent, ('.git', '.github', 'models', 'input', 'output', 'temp', 'user', 'custom_nodes', '.venv', 'venv')),
        'COMFY_PYTHON_HOME': Tree(paths['comfy_python'].parent), 'OLLAMA_HOME': Tree(paths['ollama_exe'].parent),
        'PLAYWRIGHT': Tree(playwright, ('node_modules',)), 'PLAYWRIGHT_CORE': Tree(core), 'BROWSER_TREE': Tree(browser.parent)}
    files = {key.upper(): value for key, value in paths.items()}
    files['WSL_NVIDIA'] = plain(Path(shutil.which('nvidia-smi') or '').resolve(strict=True))
    return paths, trees, files, metadata


def verify_observations(snapshot, seeds):
    observed = {row['alias']: (row['sha256'], row['bytes']) for row in snapshot['files']}
    for alias, field in (('COMFY_MAIN', 'COMFY_MAIN'), ('COMFY_PYTHON', 'COMFY_PYTHON'), ('OLLAMA_EXE', 'OLLAMA_EXE')):
        row = seeds['targets']['executables'][field]
        if observed.get(alias) != (row['sha256'], row['bytes']): raise EvidenceError('actual target identity differs: '+alias)
    for row in seeds['packages']['native_decoder_packages']['files']+seeds['frontend']['sdk']['files']:
        if observed.get(row['alias']) != (row['sha256'], row['bytes']): raise EvidenceError('installed package/SDK identity differs: '+row['alias'])
    for row in seeds['frontend']['frontend']['files']:
        if row['status'] != 'HASHED': continue
        alias = row['alias'].replace('FRONTEND_PACKAGE/', 'COMFY_PYTHON_HOME/Lib/site-packages/comfyui_frontend_package/static/', 1)
        alias = alias.replace('COMFY_WEB/', 'COMFY_ROOT/web/', 1)
        if observed.get(alias) != (row['sha256'], row['bytes']): raise EvidenceError('installed frontend identity differs: '+row['alias'])
    expected_browser = next(row for row in seeds['frontend']['browser_binaries'] if row['alias'].startswith('BROWSER_CACHE/chromium-'))
    if observed.get('BROWSER_EXECUTABLE') != (expected_browser['sha256'], expected_browser['bytes']):
        raise EvidenceError('actual installed browser differs')


def actual_samples(expected):
    candidates = []; root = plain(SOURCE)
    for visited, path in enumerate(root.rglob('*')):
        if visited >= 4096: raise EvidenceError('fixed sample catalog budget exceeded')
        if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.mp4', '.mov'}: candidates.append(path)
    result = {}
    for kind, suffixes in (('image', {'.png', '.jpg', '.jpeg', '.webp'}), ('video', {'.mp4', '.mov'})):
        matching = sorted(path for path in candidates if path.suffix.lower() in suffixes)
        if not matching: raise EvidenceError('fixed sample missing')
        path = plain(matching[0]); path.relative_to(root)
        row = next(row for row in expected if row['suffix'] == path.suffix.lower())
        before = stamp(path)
        if before[2] != row['bytes'] or not 0 < before[2] <= (20 if kind == 'image' else 256)*1024**2:
            raise EvidenceError('fixed sample size differs; no replacement')
        digest, _ = hashed_file(path, before, time.monotonic()+30)
        if digest != row['sha256']: raise EvidenceError('fixed sample hash differs; no replacement')
        result[kind] = {'path': str(path), 'sha256': digest, 'bytes': before[2]}
    return result


def validate_child(auth, path):
    if (path != child_path(auth.get('run_id')) or auth.get('status') != 'ACTIVE_ONE_SHOT'
            or auth.get('schema_version') != 'lvw.program-child-authorization/1'
            or not re.fullmatch(re.escape('AUTH-V0-S2-'+auth['run_id'].upper())+r'-[a-f0-9]{16}', auth.get('authorization_id', ''))
            or auth.get('project_id') != 'lvw-prompt-service' or auth.get('issued_by') != 'codex_gate_owner'
            or auth.get('scope') != 'COMPLETE_FIXED_NATIVE_STAGE_CHECKPOINT' or auth.get('budget') != BUDGET
            or any(type(value) is not int for value in auth['budget'].values())
            or auth.get('forbidden') != FORBIDDEN or auth.get('stage_pass_claim') is not False or auth.get('external_cost') != 0
            or auth.get('source_program_authorization') != PROGRAM_ID or auth.get('program_sha256') != program_authority()
            or auth.get('stage_id') != 'V0-S2' or auth.get('workpack_id') != 'WP-S2-05'
            or auth.get('acceptance_hash') != ACCEPTANCE or auth.get('state_root') != str(STATE_ROOT)
            or auth.get('installed_roots') != {'global_node': str(GLOBAL_NODE_ROOT), 'browser_cache': str(BROWSER_CACHE_ROOT),
                **{name: str(value.parent) for name, value in TARGETS.items()}}
            or auth.get('ports') != [8191, 11434] or auth.get('endpoints') != [base.COMFY_URL, base.OLLAMA_URL]
            or auth.get('harness_sha256') != file_hash(ROOT/HARNESS)
            or type(auth.get('issued_at')) not in (int, float) or type(auth.get('expires_at')) not in (int, float)
            or not 0 < auth['expires_at']-auth['issued_at'] <= BUDGET['max_seconds']
            or not auth['issued_at'] <= time.time() < auth['expires_at']):
        raise EvidenceError('child authority/identity/budget invalid')
    stage = repository_json('.agent-governance/stages/V0-S2/stage-control.json')
    if (stage.get('authorization_scope') != 'PROGRAM_CHILD_REQUIRED' or stage.get('execution_authorized') is not True
            or stage.get('program_authorization') != PROGRAM or stage.get('acceptance_hash') != ACCEPTANCE):
        raise EvidenceError('frozen Stage does not permit program-child execution')
    if slot_authority(auth['run_id'], auth['candidate_sha']) != auth.get('supplemental_authorization'):
        raise EvidenceError('supplemental child authority binding differs')
    seeds = seed_values()
    if (auth.get('samples') != seeds['targets']['samples']
            or auth.get('model') != {'name': base.MODEL, 'digest': seeds['model']['model_digest']}
            or auth.get('seed_sha256') != {name: file_hash(ROOT/relative) for name, relative in SEEDS.items()}
            or auth.get('offline_receipt_sha256') != file_hash(ROOT/auth['offline_receipt'])):
        raise EvidenceError('child sample/model/provenance changed')
    identity = source_gate(auth['candidate_sha'], auth['offline_receipt'])
    if identity['payload_sha256'] != auth.get('payload_sha256'): raise EvidenceError('child execution source changed')
    return identity, seeds


def terminal_counts(context):
    warm = context.driver.warm_benchmark
    path = context.root/('temp/lvw-warm-events.jsonl' if warm else 'temp/lvw-native-events.jsonl')
    events = read_jsonl(path, limit=16*1024**2)
    if path.exists() and path.stat().st_size:
        with path.open('rb') as stream:
            stream.seek(-1, 2)
            if stream.read(1) != b'\n': raise EvidenceError('terminal native event log is incomplete')
    attempts = [value for value in events if value.get('event') == ('before_call' if warm else 'provider_attempt')]
    identities = [(value.get('request_number' if warm else 'run_token'), value.get('call_index')) for value in attempts]
    if len(set(identities)) != len(identities): raise EvidenceError('provider attempt event identity duplicated')
    bound = len(attempts)+(0 if warm or not context.driver.submissions else 1)
    if bound > (50 if warm else 33): raise EvidenceError('fixed provider attempt budget exceeded')
    return {'public_submissions': context.driver.submissions, 'preloads': context.driver.preloads,
        'provider_attempts_in_native_events': len(attempts), 'provider_attempt_upper_bound': bound,
        'legacy_image_attempt_upper_bound': 0 if warm else int(bool(context.driver.submissions)),
        'event_file_sha256': file_hash(path) if path.exists() else None,
        'request_ledger': context.driver.request_ledger, 'owned_service_count': len(context.driver.owned)}


def execute(slot):
    path = child_path(slot); raw = path.read_bytes(); auth = json.loads(raw)
    identity, seeds = validate_child(auth, path)  # Repository-only; no target access.
    if (ROOT/'reports/v0-s2'/slot).exists(): raise EvidenceError('terminal evidence slot already exists')
    # Atomic claim is outside the candidate tree and cannot be reset by a code
    # commit. An existing claim is a stopped/ongoing attempt, never a retry.
    directory=claim_run(slot,auth,raw)
    lease = ChildLease(path, raw); lease.directory = directory
    from tools.v0_s2_browser_owner import birth
    write_new(directory/'claim-process.json', {'parent_birth': birth(os.getpid()), 'candidate_sha': auth['candidate_sha'],
        'authorization_sha256': hashlib.sha256(raw).hexdigest(), 'harness_sha256': auth['harness_sha256']})
    result = {'kind': 'FULL_NATIVE_S2_CHECKPOINT_REQUIRES_INDEPENDENT_REVIEW', 'run_id': slot,
        'candidate_sha': auth['candidate_sha'], 'authorization_sha256': hashlib.sha256(raw).hexdigest(),
        'decision': 'NO_GO', 'stage_pass_claim': False, 'stage_checkpoint_consumed': True, 'state_root_alias': 'STATE/'+slot,
        'cases': dict.fromkeys(('V0-A01', 'V0-A02', 'V0-A03', 'V0-A04', 'V0-A05', 'V0-A07', 'V0-A08', 'V0-A09', 'V0-A10'), 'NOT_RUN')}
    factory = bindings = None; interrupted = None
    try:
        paths, trees, files, metadata = resolve_installed(lease, seeds)
        write_new(directory/'metadata.json', metadata)
        def binding_observation(value):
            # Controlled state only: aliases/counters, never media/model content.
            temporary = directory/'binding-progress.tmp'
            write_new(temporary, value); os.replace(temporary, directory/'binding-progress.json')
            result['installed_binding_progress'] = value
        bindings = ExecutionBindings(trees=trees, files=files, authorize=lease.authorize, observe=binding_observation)
        snapshot = bindings.capture(); verify_observations(snapshot, seeds); write_new(directory/'installed-bindings.json', snapshot)
        observed = {row['alias']: row['sha256'] for row in snapshot['files']}
        if (len(metadata) != 2 or metadata[0]['executable_sha256'] != observed['NODE_EXECUTABLE']
                or metadata[1]['executable_sha256'] != observed['POWERSHELL']):
            raise EvidenceError('queried and captured metadata tools differ')
        samples = actual_samples(auth['samples']); write_new(directory/'sample-bindings.json', samples)
        frozen = repository_json('reports/v0-s2/frozen-structural-inputs-02.json')
        plan = load_fixture_set(**frozen['binding_inputs'])
        if {key: value for key, value in frozen.items() if key != 'binding_inputs'} != plan:
            raise EvidenceError('frozen structural input plan changed')
        digests = {key: next(row['sha256'] for row in snapshot['files'] if row['alias'] == key.upper()) for key in TOOL_KEYS}
        rehashes = [1]
        def complete():
            lease.authorize('complete_execution_reverification', rehashes[0])
            if rehashes[0] >= BUDGET['installed_full_snapshots']: raise EvidenceError('full binding snapshot budget exceeded')
            rehashes[0] += 1
            if seal_candidate(ROOT, auth['candidate_sha'], SOURCE_PAYLOAD) != identity: raise EvidenceError('execution source drift')
            proof = bindings.verify()
            result_proof = {**proof, 'candidate_sha': auth['candidate_sha'],
                'tool_bindings': {key: {'path': str(value), 'sha256': digests[key]} for key, value in paths.items()}}
            write_new(directory/('reverification-'+str(rehashes[0]).zfill(2)+'.json'),
                {**result_proof, 'source_payload_sha256': identity['payload_sha256'], 'wall_seconds': time.time()})
            return result_proof
        archive = OwnedArchive(directory, run_id=slot, candidate_sha=auth['candidate_sha'],
            authorization_sha256=result['authorization_sha256'], authorize=lease.authorize)
        factory = StageRuntimeFactory(directory=directory, run_id=slot, candidate_sha=auth['candidate_sha'],
            authorization_sha256=result['authorization_sha256'], paths=paths, tool_sha256=digests,
            source_identity=identity, samples=samples, fixture_plan=plan, model_digest=auth['model']['digest'], archive=archive,
            authorize=lease.authorize, verify_complete=complete,
            guard_critical=lambda: bindings.guard([key.upper() for key in sorted(TOOL_KEYS)]))
        def prepared(method):
            value = method(); original = value.driver.resource_observer
            def observe(): lease.authorize('resource_and_authorization_guard', None); return original()
            value.driver.resource_observer = observe
            return value
        counts = {}; result['runtime_counts'] = counts
        def record_archive(context, cleanup):
            label = 'warm' if context.driver.warm_benchmark else 'default'
            try: facts = terminal_counts(context)
            except Exception as error: facts = {'counter_error': type(error).__name__+':'+str(error)}
            counts[label] = facts
            write_new(context.root/'temp/runtime-terminal-counts.json', facts)
            proof = archive(context, cleanup)
            if facts.get('counter_error'): raise EvidenceError('raw counter validation failed; evidence archived')
            return proof
        sequence = StageSequence(run_id=slot, candidate_sha=auth['candidate_sha'], authorization_sha256=result['authorization_sha256'],
            prepare_default=lambda: prepared(factory.prepare_default), prepare_warm=lambda: prepared(factory.prepare_warm),
            archive=record_archive, authorize=lease.authorize)
        result['sequence'] = sequence.run()
        result['runtime_evidence'] = factory.evidence
        if result['sequence']['decision'] != 'MACHINE_SEQUENCE_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF':
            result['error_code'] = result['sequence'].get('error_code', 'STAGE_SEQUENCE_INCOMPLETE')
        if result['sequence']['decision'] == 'MACHINE_SEQUENCE_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF':
            if (set(counts) != {'default', 'warm'} or counts['default'].get('public_submissions') != 45
                    or counts['warm'].get('public_submissions') != 20 or counts['warm'].get('preloads') != 20
                    or counts['warm'].get('provider_attempts_in_native_events') != 50
                    or sum(row.get('provider_attempt_upper_bound', BUDGET['provider_calls']+1) for row in counts.values()) > BUDGET['provider_calls']):
                raise EvidenceError('complete sequence raw budget counters are missing/inconsistent')
            complete(); result['cases'] = result['sequence']['cases']
            result['decision'] = 'MACHINE_CHECKPOINT_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF'
        result['full_binding_snapshots'] = rehashes[0]
    except BaseException as error:
        result['error_code'] = type(error).__name__+':'+str(error)
        if isinstance(error, (KeyboardInterrupt, SystemExit)): interrupted = error
    finally:
        if factory is not None: result['runtime_evidence'] = factory.evidence
        try: lease.close()
        except OSError as error:
            result['lease_close_error'] = type(error).__name__; result['decision'] = 'NO_GO'
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        result['authorization_actions'] = lease.actions
        result['case_status_scope'] = 'complete machine obligations; incomplete raw phase facts remain separately retained'
        result['test_counts'] = {'fixed': 9, **{status: list(result['cases'].values()).count(status) for status in ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN')}}
        published = False
        try:
            write_new(directory/'terminal.json', result)
            aliases = {str(ROOT): 'PACK_ROOT', str(STATE_ROOT): 'STATE', str(SOURCE): 'TEST_SOURCE'}
            public = {key: value for key, value in result.items() if key not in ('sequence', 'runtime_evidence', 'runtime_counts')}
            if 'sequence' in result:
                public['phase_decisions'] = {name: {'decision': row.get('decision'), 'test_counts': row.get('test_counts')}
                    for name, row in result['sequence']['phases'].items()}
                public['performance'] = result['sequence']['phases'].get('warm', {}).get('performance')
                public['archive_manifests'] = {name: result['sequence'][name+'_archive'] for name in ('default', 'warm')
                    if name+'_archive' in result['sequence']}
            public['raw_terminal_sha256'] = file_hash(directory/'terminal.json')
            public['raw_evidence_requires_controlled_review'] = True
            public_directory = ROOT/'reports/v0-s2'/slot; public_directory.mkdir(exist_ok=False)
            write_new(public_directory/'receipt.json', base.redact_value(public, aliases)); published = True
        finally:
            auth['status'] = 'EXPIRED_MACHINE_CHECKPOINT_COMPLETE' if published and result['decision'].startswith('MACHINE_CHECKPOINT_COMPLETE') else 'EXPIRED_NO_GO'
            if published:
                auth['terminal_receipt'] = str((public_directory/'receipt.json').relative_to(ROOT))
                auth['terminal_receipt_sha256'] = file_hash(public_directory/'receipt.json')
            # Never overwrite a revocation discovered during reserved cleanup.
            if path.read_bytes() == raw:
                temporary = path.with_suffix('.terminal.tmp'); write_new(temporary, auth); os.replace(temporary, path)
            else: write_new(directory/'child-expired-with-external-record-change.json', {'status': auth['status'], 'original_child_sha256': result['authorization_sha256']})
            if auth.get('supplemental_authorization'):
                supplemental.expire(auth['supplemental_authorization'], decision=('MACHINE_CHECKPOINT_COMPLETE'
                    if result['decision'].startswith('MACHINE_CHECKPOINT_COMPLETE') else 'NO_GO'),
                    terminal=auth.get('terminal_receipt', 'STATE/'+slot+'/terminal.json'))
    if interrupted is not None: raise interrupted
    return result


def main():
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest='command', required=True)
    ready = commands.add_parser('prepare'); ready.add_argument('--slot', required=True)
    ready.add_argument('--candidate', required=True); ready.add_argument('--offline-receipt', required=True)
    ready.add_argument('--replace-unclaimed', action='store_true')
    run = commands.add_parser('execute'); run.add_argument('--slot', required=True)
    run.add_argument('--execute-native-checkpoint', action='store_true', required=True)
    args = parser.parse_args()
    if args.command == 'prepare': value = prepare(args.slot, args.candidate, args.offline_receipt, replace_unclaimed=args.replace_unclaimed)
    else: value = execute(args.slot)
    print(json.dumps({key: value.get(key) for key in ('run_id', 'candidate_sha', 'status', 'decision', 'error_code')}))
    return 0 if args.command == 'prepare' or value['decision'].startswith('MACHINE_CHECKPOINT_COMPLETE') else 1


if __name__ == '__main__': raise SystemExit(main())
