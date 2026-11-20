"""Sealed two-action / two-generation loaded cleanup and public image UI check."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time
import stat as stat_module
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'lvw/backend')]
import hashlib
from types import ModuleType
AUTHORITY_SHA256 = "677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787"
# Execute precisely the bytes we verified. Normal import may read an existing
# unchecked/timestamp .pyc even under -B; sys.modules is also not an authority.
authority_path = ROOT / "tools/local_program_authority.py"
authority_source = authority_path.read_bytes()
if hashlib.sha256(authority_source).hexdigest() != AUTHORITY_SHA256:
    raise ValueError("TRUSTED_AUTHORITY_DRIFT_BEFORE_IMPORT")
authority = ModuleType("lvw_cleanup_verified_authority")
authority.__file__ = str(authority_path)
exec(compile(authority_source, str(authority_path), "exec"), authority.__dict__)
WRITE_ROOTS = ()
CRITICAL_INPUTS = {'lvw/backend/app/native_private.py', 'lvw/backend/app/native_job.py', 'tools/local_program_authority.py', 'lvw/backend/app/native_runtime.py',
    'lvw/backend/app/resources.py', 'lvw/backend/app/video_kernel.py',
    'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py',
    'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_process.py',
    'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_input.py',
    'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_decoder.py'}


def write_bytes(path, value):
    path = path.absolute()
    if not any(path.is_relative_to(root) for root in WRITE_ROOTS) or path.parent.resolve() != path.parent:
        raise ValueError('OUTPUT_PATH_UNBOUND')
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            current = os.fstat(stream.fileno())
            if not stat_module.S_ISREG(current.st_mode) or current.st_nlink != 1:
                raise ValueError('OUTPUT_FILE_ALIAS')
            stream.truncate(0)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def write(path, value):
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def actual_tools(child):
    value = {'python': str(Path(sys.executable).resolve()), 'chromium': child['chromium_executable'],
             'nvidia-smi': shutil.which('nvidia-smi')}
    if not child['fixture']:
        value['git'] = shutil.which('git')
        value['wslpath'] = shutil.which('wslpath')
        value['ollama'] = '/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe'
        value['powershell'] = shutil.which('powershell.exe') or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    return value


def ledger_row(child):
    if child['budget_ledger'] != str(authority.LEDGER):
        raise ValueError('UNEXPECTED_LEDGER')
    with sqlite3.connect(authority.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM children WHERE run=?', (child['run_id'],)).fetchone()
        if row is None: raise ValueError('NO_RESERVED_CHILD')
        return dict(row)


def verify_candidate_files(root, candidate, entries):
    """Compare manifest AND working bytes to named Git blobs; never relabel dirt."""
    if not re.fullmatch(r'[a-f0-9]{40}', candidate):
        raise ValueError('INVALID_CANDIDATE')
    paths = [entry['path'] for entry in entries]
    if (len(paths) != len(set(paths)) or any(not isinstance(v, str) or '\n' in v
            or Path(v).is_absolute() or '..' in Path(v).parts for v in paths)):
        raise ValueError('INVALID_CANDIDATE_PATHS')
    env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_TERMINAL_PROMPT': '0'}
    prefix = subprocess.run(['git', 'rev-parse', '--show-prefix'], cwd=root, env=env,
                            capture_output=True, check=True, timeout=5).stdout.decode().strip()
    references = ''.join(candidate + ':' + prefix + path + '\n' for path in paths).encode()
    payload = subprocess.run(['git', 'cat-file', '--batch'], input=references, cwd=root, env=env,
                             capture_output=True, check=True, timeout=10).stdout
    offset = 0
    for entry in entries:
        end = payload.index(b'\n', offset)
        header = payload[offset:end].split()
        if len(header) != 3 or header[1] != b'blob': raise ValueError('CANDIDATE_BLOB_MISSING')
        size = int(header[2]); offset = end + 1
        blob = payload[offset:offset+size]; offset += size
        if payload[offset:offset+1] != b'\n': raise ValueError('CANDIDATE_BATCH_MALFORMED')
        offset += 1
        if (hashlib.sha256(blob).hexdigest() != entry['sha256']
                or authority.digest(root / entry['path']) != entry['sha256']):
            raise ValueError('CANDIDATE_WORKTREE_MISMATCH')
    if offset != len(payload): raise ValueError('CANDIDATE_BATCH_TRAILING')


def terminal_sample_ok(sample, baseline):
    return bool(baseline is not None and sample['gpu_used_mib'] < 23552
                and sample['available_ram_mib'] >= 2048
                and sample['gpu_used_mib'] <= baseline['gpu_used_mib'] + 1024)


def reconciled_runtime(runtime, provider):
    return bool((runtime is None or not runtime._owned() and runtime._native is None
                 and runtime._cleanup_pending is None)
                and (provider is None or getattr(provider, '_lease', None) is None))


def validate(child_path, expected_calls=0):
    if child_path.absolute() != child_path.resolve() or child_path.parent.parent != BASE / 'runs':
        raise ValueError('UNEXPECTED_CHILD_PATH')
    child = json.loads(child_path.read_text())
    authority.approved(ROOT)
    if (os.environ.get('LVW_DATA_ROOT') != child['data_root'] or os.environ.get('TMPDIR') != child['private_root']):
        raise ValueError('AMBIENT_ROOT_MISMATCH')
    if (child.get('kind') != 'RESOURCE_CLEANUP_V7_LOADED_CHILD/1'
            or child['program'] != authority.COMPLETE_APPROVAL
            or child['program_sha256'] != authority.digest(ROOT / authority.COMPLETE_APPROVAL)
            or child['expires_at'] <= time.time() or child['fixture'] is not False
            or child['budget'] != {'model_calls': 2, 'provider_calls': 2, 'api_starts': 1, 'ollama_starts': 2, 'headless_browser_starts': 1, 'full_checkpoints': 0}
            or os.environ.get('LVW_AUTHORIZATION_CHILD') != str(child_path)):
        raise ValueError('INVALID_OR_EXPIRED_CHILD')
    row = ledger_row(child)
    if (row['active'] != 1 or row['calls'] != expected_calls or row['cap'] != 2 or row['expires'] <= time.time()
            or row['child_path'] != str(child_path) or row['child_hash'] != authority.digest(child_path)
            or row['bindings_hash'] != authority.digest(Path(row['bindings_path']))):
        raise ValueError('CHILD_SEAL_MISMATCH')
    for item in child['frozen_files']:
        path = ROOT / item['path']
        if not path.resolve().is_relative_to(ROOT) or authority.digest(path) != item['sha256']:
            raise ValueError('SOURCE_DRIFT')
    if not CRITICAL_INPUTS.issubset({item['path'] for item in child['frozen_files']}):
        raise ValueError('TRUSTED_INPUTS_INCOMPLETE')
    if child['harness_sha256'] != authority.digest(Path(__file__)):
        raise ValueError('HARNESS_DRIFT')
    bindings = json.loads(Path(row['bindings_path']).read_text())
    expected_tools = {'python', 'chromium', 'nvidia-smi'} | (set() if child['fixture'] else {'ollama', 'powershell', 'wslpath', 'git'})
    if set(bindings) != expected_tools: raise ValueError('TOOL_BINDINGS_INCOMPLETE')
    for item in bindings.values():
        if authority.digest(Path(item['path'])) != item['sha256']: raise ValueError('TOOL_DRIFT')
    selected = actual_tools(child)
    if any(not selected.get(key) or Path(selected[key]).resolve() != Path(item['path']).resolve()
           for key, item in bindings.items()):
        raise ValueError('ACTUAL_TOOL_MISMATCH')
    private = Path(child['private_root'])
    stat = private.lstat()
    if (private.absolute() != private.resolve() or not private.name.startswith('lvw-cleanup-v4-')
            or [stat.st_dev, stat.st_ino, stat.st_uid] != child['private_identity']
            or stat.st_mode & 0o077 or (private / 'owner-marker.json').read_text() != child['private_marker']
            or Path(child['data_root']) != private / 'data'):
        raise ValueError('PRIVATE_ROOT_IDENTITY_MISMATCH')
    data = Path(child['data_root'])
    data_stat = data.lstat()
    if (data.resolve() != data or not stat_module.S_ISDIR(data_stat.st_mode) or data_stat.st_mode & 0o077
            or [data_stat.st_dev, data_stat.st_ino, data_stat.st_uid] != child['data_identity']):
        raise ValueError('DATA_ROOT_IDENTITY_MISMATCH')
    if not (child_path.parent / 'run.claim').exists() and any(data.iterdir()):
        raise ValueError('DATA_ROOT_NOT_FRESH')
    # Existing descendants must also be private ordinary paths, never symlinks/reparse aliases.
    for descendant in data.rglob('*'):
        info = descendant.lstat()
        if descendant.is_symlink() or info.st_nlink > 1 and not descendant.is_dir():
            raise ValueError('DATA_DESCENDANT_ALIAS')
    if child['samples'] != [{'path': 'reports/unified-media/dev-image.png', 'sha256': authority.digest(ROOT / 'reports/unified-media/dev-image.png')}]:
        raise ValueError('SAMPLE_UNBOUND')
    if child['model_tag'] != 'gemma4:26b' or child['model_digest'] != '5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251':
        raise ValueError('MODEL_UNBOUND')
    verify_candidate_files(ROOT, child['candidate_sha'], child['frozen_files'] + child['samples'])
    return child


def native_terminal(runtime, captured, out, errors):
    """Reconcile EVERY prepared generation, never synthesize expected from terminal."""
    try:
        from app.native_runtime import proof
        history = getattr(runtime, '_native_history', []) if runtime is not None else []
        if len(history) > 2 or len({n['nonce'] for n in history}) != len(history):
            raise ValueError('UNEXPECTED_NATIVE_GENERATIONS')
        observations = []
        known = True
        for native in history:
            record = captured.get(native['nonce'])
            value = proof(native)
            expected = record['identity'] if record else None
            matched = bool(record and expected.get('state') in {'starting', 'listening'}
                and native is record['native'] and value.get('nonce') == native['nonce'] == expected.get('nonce')
                and value.get('state') == 'exited' and value.get('listener_owned') is False
                and type(expected.get('pid')) is int and expected['pid'] > 0
                and type(expected.get('birth_ticks')) is int and expected['birth_ticks'] > 0
                and value.get('pid') == expected['pid'] and value.get('birth_ticks') == expected['birth_ticks']
                and record['wrapper'].returncode == 0)
            observations.append({'proof': value, 'expected': expected, 'matched': matched,
                                 'wrapper_returncode': record['wrapper'].returncode if record else None})
            known = known and matched
        known = known and len(history) == len(captured)
        write(out / 'native-final.json', {'generations': observations, 'matched': known})
        return known, len(history)
    except BaseException as error:
        errors.append({'step': 'native.proof_or_archive', 'error': type(error).__name__})
        return False, None


def finalize_budget(child, result, known, errors, out):
    """Settle only actual bounded debits after proven cleanup; success requires both model actions."""
    result['model_actions'] = None
    try:
        actual = ledger_row(child)['calls']
        if type(actual) is not int or actual < 0: raise ValueError('INVALID_LEDGER_COUNT')
        result['model_actions'] = actual
        if actual > 2 or result['status'] == 'PASS_REAL_LOADED_RESTART_IMAGE' and actual != 2:
            raise ValueError('LOADED_ACTION_COUNT_MISMATCH')
        if known and not errors and result['status'] == 'PASS_REAL_LOADED_RESTART_IMAGE':
            # Full resource/process evidence is synced BEFORE capacity is released.
            write(out / 'receipt.prepared.json', {**result, 'status': 'EVIDENCE_COMPLETE_PENDING_SETTLEMENT',
                  'operation_status': result['status'], 'known_terminal': True,
                  'settlement_expected': {'run_id': child['run_id'], 'actual_model_actions': actual}})
            result['authorization_terminal'] = authority.settle(child['run_id'], actual)
            return True
    except BaseException as error:
        errors.append({'step': 'budget.read_or_settle', 'error': type(error).__name__})
    try:
        authority.close_retaining_reservation(child['run_id'])
        if ledger_row(child)['active'] != 2:
            raise ValueError('RESERVATION_RETAIN_UNPROVEN')
        result['authorization_terminal'] = 'RESERVATION_RETAINED'
    except BaseException as error:
        errors.append({'step': 'budget.retain', 'error': type(error).__name__})
        result['authorization_terminal'] = 'RESERVATION_TERMINAL_UNKNOWN'
    result['status'] = 'FAIL_OR_BLOCKED'
    return False


def finish_receipt(child, result, known, errors, out):
    known = finalize_budget(child, result, known, errors, out)
    if errors: result['status'] = 'FAIL_OR_BLOCKED'
    result['known_terminal'] = known
    try:
        write(out / 'receipt.json', result)
    except BaseException as error:
        result.update(status='FAIL_OR_BLOCKED', known_terminal=False, terminal_error='FINAL_RECEIPT_WRITE_FAILED')
        print(json.dumps({'status': 'TERMINAL_RECEIPT_WRITE_FAILED', 'error': type(error).__name__}))
        return False
    return known and result['status'] == 'PASS_REAL_LOADED_RESTART_IMAGE'


def create_claim(child, out, write_claim=None, close_claim=None):
    """O_EXCL replay refusal is separate; every post-creation failure gets a terminal attempt."""
    descriptor = os.open(out / 'run.claim', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    errors = []
    try:
        body = child['run_id'].encode()
        if (write_claim or os.write)(descriptor, body) != len(body):
            raise OSError('SHORT_CLAIM_WRITE')
    except BaseException as error:
        errors.append({'step': 'claim.write', 'error': type(error).__name__})
    finally:
        try:
            (close_claim or os.close)(descriptor)
        except BaseException as error:
            errors.append({'step': 'claim.close', 'error': type(error).__name__})
    if not errors:
        return True
    result = {'status': 'FAIL_OR_BLOCKED', 'cleanup_errors': errors, 'model_actions': None,
              'product_imported': False, 'native_started': False}
    finalize_budget(child, result, False, errors, out)
    result['known_terminal'] = False
    write(out / 'receipt.json', result)
    return False


async def run(child_path):
    child = validate(child_path)
    global WRITE_ROOTS
    out = child_path.parent
    WRITE_ROOTS = (out, Path(child['private_root']))
    if not create_claim(child, out): return 1
    # The production provider's unchanged budget import resolves to the exact
    # verified authority source, rather than an ambient cache/module substitute.
    sys.modules['tools.local_program_authority'] = authority
    checks, errors, captured = [], [], {}
    result = {'candidate_sha': child['candidate_sha'], 'status': 'NOT_COMPLETED',
              'checks': checks, 'cleanup_errors': errors, 'model_actions': None,
              'scope': 'loaded model close, explicit restart, one real public image analysis'}
    provider = runtime = app = server = task = sock = pw = browser = context = None
    baseline = None
    monitor_task = None
    tearing_down = False
    resource_samples = []
    main_task = asyncio.current_task()

    async def monitor():
        from app import resources
        try:
            while True:
                sample = await resources.snapshot()
                resource_samples.append({'at_monotonic': time.monotonic(), **sample})
                if sample['gpu_used_mib'] >= 23552 or sample['available_ram_mib'] < 2048:
                    raise ValueError('RESOURCE_HARD_LIMIT')
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            errors.append({'step': 'continuous resource monitor', 'error': type(error).__name__})
            if not tearing_down:
                main_task.cancel()

    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        if not value: raise AssertionError(name)

    async def step(name, action, seconds=10):
        try:
            await asyncio.wait_for(action(), seconds)
            return True
        except BaseException as error:
            errors.append({'step': name, 'error': type(error).__name__})
            return False

    def capture(label):
        from app.native_runtime import proof
        native = runtime._native
        value = proof(native)
        check(label + ' independent live owner captured', bool(native and runtime._owned()
            and value.get('state') == 'listening' and value.get('listener_owned') is True
            and type(value.get('pid')) is int and type(value.get('birth_ticks')) is int
            and value['pid'] > 0 and value['birth_ticks'] > 0))
        check(label + ' unique generation', native['nonce'] not in captured)
        captured[native['nonce']] = {'native': native, 'identity': dict(value), 'wrapper': runtime.process}
        write(out / (label + '-start.json'), {'identity': value, 'wrapper_pid': runtime.process.pid})
        return native

    try:
        async with asyncio.timeout(235):
            import httpx
            import uvicorn
            from playwright.async_api import async_playwright
            from app.config import Settings
            from app.main import create_app
            from app.provider import OllamaProvider
            from app.runtime import OllamaRuntime
            from app import resources
            from app.native_runtime import proof
            provider = OllamaProvider('http://127.0.0.1:11434/api/chat', child['model_tag'], 100,
                                      ledger_path=Path(child['data_root']) / 'provider.jsonl')
            runtime = OllamaRuntime(provider, Path(actual_tools(child)['ollama']), Path(child['data_root']))
            observation = await provider.listener_state()
            write(out / 'initial-listener.json', observation)
            check('no external listener before start', observation.get('state') == 'absent')
            baseline = await resources.snapshot()
            write(out / 'preflight.json', baseline)
            check('unchanged GPU and RAM admission', baseline['gpu_free_mib'] >= 19047
                  and baseline['gpu_used_mib'] < 23552 and baseline['available_ram_mib'] >= 2048)
            validate(child_path, 0)
            monitor_task = asyncio.create_task(monitor())
            await runtime.start()
            first = capture('generation-a')
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.get('http://127.0.0.1:11434/api/tags')
                response.raise_for_status()
                tags = response.json()
                write(out / 'model-tags.json', tags)
                target = [v for v in tags['models'] if v.get('name') == child['model_tag']]
                check('installed model digest matches seal', len(target) == 1 and target[0].get('digest') == child['model_digest'])
                check('own fresh service inventory empty', await provider._inventory() == [])
                validate(child_path, 0)
                authority.model_action(child_path)  # Debit BEFORE the only preload send.
                response = await client.post('http://127.0.0.1:11434/api/generate', json={
                    'model': child['model_tag'], 'keep_alive': '5m', 'stream': False, 'options': {'num_ctx': 2048}})
                response.raise_for_status()
                write(out / 'preload-response.json', response.json())
            loaded = await provider._inventory()
            write(out / 'loaded-inventory.json', loaded)
            check('target really resident before cleanup', len(loaded) == 1
                  and loaded[0].get('name') == child['model_tag']
                  and loaded[0].get('digest') == child['model_digest']
                  and type(loaded[0].get('size_vram')) is int and loaded[0]['size_vram'] > 0)
            app = create_app(Settings(data_root=Path(child['data_root']), static_root=ROOT / 'lvw/frontend/dist'), provider, runtime)
            sock = socket.socket(); sock.bind(('127.0.0.1', child['port']))
            server = uvicorn.Server(uvicorn.Config(app, log_level='warning', lifespan='on', timeout_graceful_shutdown=15))
            task = asyncio.create_task(server.serve(sockets=[sock]))
            for _ in range(100):
                if server.started: break
                await asyncio.sleep(.05)
            check('isolated public API started', server.started)
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True, executable_path=child['chromium_executable'])
            context = await browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
            base = f"http://127.0.0.1:{child['port']}"
            external, js_errors = [], []
            async def route(r):
                if not r.request.url.startswith(base + '/'):
                    external.append(r.request.url); await r.abort()
                else: await r.continue_()
            await context.route('**/*', route)
            page = await context.new_page()
            page.on('pageerror', lambda e: js_errors.append(str(e)))
            await page.goto(base, wait_until='networkidle')
            draft = page.locator('#draft-natural-zh')
            original = '人工稿保护验证：资源清理、重启和模型分析不自动改稿。'
            await draft.fill(original)
            validate(child_path, 1)
            async with page.expect_response(lambda r: r.url.endswith('/runtime/resources/cleanup'), timeout=50000) as pending:
                await page.get_by_test_id('resource-cleanup').click()
            response = await pending.value
            body = await response.json(); write(out / 'cleanup-response.json', body)
            verdict = body['data']
            check('loaded public cleanup actually verified', response.status == 200
                  and verdict['status'] == 'released' and verdict['verified'] is True
                  and verdict['inventory_observation'] == {'state': 'complete', 'model_count': 1}
                  and verdict['listener_observation']['state'] == 'absent')
            check('first service exited and no retained cleanup', proof(first).get('state') == 'exited'
                  and runtime._native is None and not runtime._owned() and provider._lease is None
                  and runtime._cleanup_pending is None)
            check('cleanup retained manual draft', await draft.input_value() == original)
            write_bytes(out / 'cleanup-desktop.png', await page.screenshot(full_page=True))
            start = page.get_by_test_id('runtime-start'); await start.wait_for()
            for _ in range(100):
                if await start.is_enabled(): break
                await asyncio.sleep(.05)
            validate(child_path, 1)
            async with page.expect_response(lambda r: r.url.endswith('/runtime/ollama/start'), timeout=45000) as pending:
                await start.click()
            response = await pending.value
            body = await response.json(); write(out / 'restart-response.json', body)
            check('explicit UI restart ready and owned', response.status == 200
                  and body['data']['ollama']['managed'] and body['data']['ollama']['model_ready'])
            capture('generation-b')
            await page.get_by_test_id('image-input').set_input_files(str(ROOT / child['samples'][0]['path']))
            analyze = page.get_by_test_id('analyze')
            for _ in range(100):
                if await analyze.is_enabled(): break
                await asyncio.sleep(.05)
            validate(child_path, 1)
            async with page.expect_response(lambda r: '/api/v1/model-runs/' in r.url, timeout=140000) as pending:
                await analyze.click()
            response = await pending.value
            body = await response.json(); write(out / 'model-run.json', body)
            run = body['data']
            check('real image suggestion returned through public UI', response.status == 200
                  and run['status'] == 'succeeded' and run['input_sha256'] == child['samples'][0]['sha256']
                  and run['parsed_spec'] is not None
                  and run['parsed_spec']['text_zh'].strip() and run['parsed_spec']['text_en'].strip())
            check('analysis leaves manual draft unchanged', await draft.input_value() == original)
            public = await context.request.get(base + '/api/v1/jobs/' + run['job_id'])
            terminal = await public.json(); write(out / 'job-terminal.json', terminal)
            check('job terminal succeeded and physical resource released', terminal['data']['status'] == 'succeeded'
                  and terminal['data']['result_ref'] == run['id'] and terminal['data']['resource_state'] == 'released')
            page.on('dialog', lambda dialog: dialog.accept())
            await page.get_by_role('button', name='采纳到人工稿', exact=True).click()
            check('only explicit adoption changes draft', await draft.input_value() == run['parsed_spec']['text_zh'])
            async with page.expect_download() as download:
                await page.get_by_role('button', name='导出 JSON', exact=True).click()
            downloaded = await (await download.value).path()
            exported = json.loads(Path(downloaded).read_bytes()); write(out / 'export.json', exported)
            check('export source matches actual run', exported['source']['model_run_id'] == run['id']
                  and exported['outputs']['natural_zh'] == run['parsed_spec']['text_zh'])
            write_bytes(out / 'analysis-desktop.png', await page.screenshot(full_page=True))
            await page.set_viewport_size({'width': 390, 'height': 844})
            check('mobile layout contained', await page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            write_bytes(out / 'analysis-mobile.png', await page.screenshot(full_page=True))
            check('no page errors or nonlocal browser requests', not js_errors and not external)
            check('exact two model actions, two native generations', ledger_row(child)['calls'] == 2
                  and len(runtime._native_history) == len(captured) == 2)
            result['status'] = 'PASS_REAL_LOADED_RESTART_IMAGE'
    except BaseException as error:
        result.update(status='FAIL_OR_BLOCKED', error_type=type(error).__name__, error=str(error))
    finally:
        tearing_down = True
        context_closed = context is None or await step('context.close', context.close)
        browser_closed = browser is None or await step('browser.close', browser.close)
        driver_closed = pw is None or await step('playwright.stop', pw.stop)
        if app:
            for job in list(app.state.analysis.jobs.values()):
                if job.status in {'queued', 'preparing', 'running', 'cancelling'}:
                    app.state.analysis.cancel(job.id)
        if server: server.should_exit = True
        async def stop_server(): await task
        api_closed = task is None or await step('api.shutdown', stop_server, 18)
        if runtime: await step('original runtime.close', runtime.close, 15)
        if sock:
            try: sock.close()
            except OSError: errors.append({'step': 'socket.close', 'error': 'OSError'})
        native_exited, generations = native_terminal(runtime, captured, out, errors)
        final_observations = []
        resources_ok = True
        if provider:
            async def final_probe():
                nonlocal resources_ok
                from app import resources
                listener = await provider.listener_state()
                result['final_listener'] = listener
                resources_ok = listener.get('state') == 'absent'
                for _ in range(3):
                    sample = await resources.snapshot(); final_observations.append(sample)
                    resources_ok = resources_ok and terminal_sample_ok(sample, baseline)
                    await asyncio.sleep(.25)
            resources_ok = await step('final resource observations', final_probe, 12) and resources_ok
        if monitor_task:
            monitor_task.cancel()
            try: await monitor_task
            except asyncio.CancelledError: pass
        try: write(out / 'resource-samples.json', resource_samples)
        except BaseException as error: errors.append({'step': 'resource archive', 'error': type(error).__name__})
        result['final_resource_samples'] = final_observations
        known = bool(context_closed and browser_closed and driver_closed and api_closed and native_exited
                     and resources_ok and reconciled_runtime(runtime, provider) and not errors)
        result['cleanup'] = dict(context_closed=context_closed, browser_closed=browser_closed,
            driver_closed=driver_closed, api_closed=api_closed, native_exited=native_exited,
            native_generations=generations, resource_bound_confirmed=resources_ok,
            private_data_retained_for_diagnostics=True, recursive_deletion_performed=False)
        accepted = finish_receipt(child, result, known, errors, out)
        print(json.dumps({'status': result['status'], 'checks': len(checks), 'known_terminal': result['known_terminal'], 'model_actions': result['model_actions']}))
    return 0 if accepted else 1


if __name__ == '__main__':
    try: raise SystemExit(asyncio.run(run(Path(sys.argv[1]).absolute())))
    except (ValueError, FileExistsError) as error:
        print('PRESTART_REFUSED:', type(error).__name__, str(error))
        raise SystemExit(2)
