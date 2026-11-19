"""Sealed zero-model UI check. Explicitly does not certify loaded-model reanalysis."""
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

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'lvw/backend')]
from tools import local_program_authority as authority


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ledger_row(child):
    if child['budget_ledger'] != str(authority.LEDGER):
        raise ValueError('UNEXPECTED_LEDGER')
    with sqlite3.connect(authority.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT * FROM children WHERE run=?', (child['run_id'],)).fetchone()
        if row is None: raise ValueError('NO_RESERVED_CHILD')
        return dict(row)


def validate(child_path):
    if child_path.absolute() != child_path.resolve() or child_path.parent.parent != BASE / 'runs':
        raise ValueError('UNEXPECTED_CHILD_PATH')
    child = json.loads(child_path.read_text())
    authority.approved(ROOT)
    if (child.get('kind') != 'RESOURCE_CLEANUP_V2_CHILD/1'
            or child['program'] != authority.COMPLETE_APPROVAL
            or child['program_sha256'] != authority.digest(ROOT / authority.COMPLETE_APPROVAL)
            or child['expires_at'] <= time.time() or child['fixture'] not in (True, False)
            or child['budget']['model_calls'] != 0 or child['budget']['provider_calls'] != 0
            or os.environ.get('LVW_AUTHORIZATION_CHILD') != str(child_path)):
        raise ValueError('INVALID_OR_EXPIRED_CHILD')
    row = ledger_row(child)
    if (row['active'] != 1 or row['calls'] != 0 or row['expires'] <= time.time()
            or row['child_path'] != str(child_path) or row['child_hash'] != authority.digest(child_path)
            or row['bindings_hash'] != authority.digest(Path(row['bindings_path']))):
        raise ValueError('CHILD_SEAL_MISMATCH')
    for item in child['frozen_files']:
        path = ROOT / item['path']
        if not path.resolve().is_relative_to(ROOT) or authority.digest(path) != item['sha256']:
            raise ValueError('SOURCE_DRIFT')
    if child['harness_sha256'] != authority.digest(Path(__file__)):
        raise ValueError('HARNESS_DRIFT')
    bindings = json.loads(Path(row['bindings_path']).read_text())
    expected_tools = {'python', 'chromium', 'nvidia-smi'} | (set() if child['fixture'] else {'ollama'})
    if set(bindings) != expected_tools: raise ValueError('TOOL_BINDINGS_INCOMPLETE')
    for item in bindings.values():
        if authority.digest(Path(item['path'])) != item['sha256']: raise ValueError('TOOL_DRIFT')
    private = Path(child['private_root'])
    stat = private.lstat()
    if (private.absolute() != private.resolve() or not private.name.startswith('lvw-cleanup-v2-')
            or [stat.st_dev, stat.st_ino, stat.st_uid] != child['private_identity']
            or stat.st_mode & 0o077 or (private / 'owner-marker.json').read_text() != child['private_marker']
            or Path(child['data_root']) != private / 'data'):
        raise ValueError('PRIVATE_ROOT_IDENTITY_MISMATCH')
    return child


async def run(child_path):
    # Atomic claim rejects replay before importing a product module or starting any process.
    child = validate(child_path)
    out = child_path.parent
    descriptor = os.open(out / 'run.claim', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(descriptor, child['run_id'].encode()); os.close(descriptor)
    fixture = child['fixture']
    checks, cleanup_errors = [], []
    result = {'candidate_sha': child['candidate_sha'], 'fixture': fixture, 'checks': checks,
              'status': 'NOT_COMPLETED', 'real_loaded_model_release_and_reanalysis': 'BLOCKED_NOT_EXECUTED',
              'cleanup_errors': cleanup_errors, 'model_actions': 0}
    provider = None; runtime = None; app = None
    server = task = sock = browser = context = pw = native = None
    native_identity = {}

    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
        if not passed: raise AssertionError(name)

    async def step(name, action, seconds=12):
        try:
            await asyncio.wait_for(action(), timeout=seconds)
            return True
        except BaseException as error:
            cleanup_errors.append({'step': name, 'error': type(error).__name__})
            return False

    try:
        async with asyncio.timeout(210):
            from app.config import Settings
            from app.main import create_app
            from app.provider import OllamaProvider
            from app.runtime import OllamaRuntime
            from app.native_runtime import proof
            from fastapi.responses import JSONResponse
            from playwright.async_api import async_playwright
            import uvicorn
            data = Path(child['data_root'])
            if fixture:
                from types import SimpleNamespace
                class FixtureProvider:
                    model = 'gemma4:26b'
                    _lease = None
                    _sent = False
                    online = True
                    rows = [{'name': model, 'model': model, 'digest': 'a' * 64, 'size_vram': 0}]
                    async def _inventory(self):
                        if not self.online: raise OSError('fixture service stopped')
                        return self.rows
                    async def readiness(self):
                        return dict(ready=self.online, model=self.model, reason=None if self.online else 'OLLAMA_UNAVAILABLE', loaded=self.online)
                provider = FixtureProvider()
                runtime = OllamaRuntime(provider, None, data)
                data.mkdir(parents=True, exist_ok=True)
                native = dict(owner=data / 'native-owner.json', stop=data / 'stop', nonce='fixture')
                native_identity = dict(nonce='fixture', pid=987, birth_ticks=12345, state='listening', listener_owned=True)
                write(native['owner'], native_identity)
                class OriginalHandle:
                    pid = 321
                    returncode = None
                    async def wait(self):
                        if native['stop'].read_text() != native['nonce']: raise ValueError('wrong nonce')
                        self.returncode = 0
                        provider.online = False
                        provider.rows = []
                        write(native['owner'], {**native_identity, 'state': 'exited', 'listener_owned': False})
                        return 0
                runtime._native = native
                runtime.process = OriginalHandle()
                # Deliberately named fixture telemetry, not real GPU evidence.
                import app.resource_cleanup as cleanup_owner
                async def fixture_sample():
                    return dict(gpu_used_mib=0, gpu_free_mib=24564, gpu_total_mib=24564, available_ram_mib=8000)
                cleanup_owner.resources.snapshot = fixture_sample
            else:
                provider = OllamaProvider('http://127.0.0.1:11434/api/chat', 'gemma4:26b', 15)
                exe = Path('/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe')
                runtime = OllamaRuntime(provider, exe, data)
                if (await provider.readiness())['reason'] == 'OLLAMA_UNAVAILABLE':
                    validate(child_path)
                    await runtime.start()
                native = runtime._native
                native_identity = proof(native)
                write(out / 'initial-runtime.json', await runtime.status())
            app = create_app(Settings(data_root=data, static_root=ROOT / 'lvw/frontend/dist'), provider, runtime)
            app.state.status_failure = False
            @app.middleware('http')
            async def injected_status_error(request, call_next):
                if fixture and app.state.status_failure and request.url.path == '/api/v1/runtime/status':
                    return JSONResponse(status_code=503, content={'error': {'code': 'FIXTURE_STATUS_DOWN'}})
                return await call_next(request)
            sock = socket.socket()
            sock.bind(('127.0.0.1', child['port']))
            server = uvicorn.Server(uvicorn.Config(app, log_level='warning', lifespan='on'))
            task = asyncio.create_task(server.serve(sockets=[sock]))
            for _ in range(100):
                if server.started: break
                await asyncio.sleep(0.05)
            check('isolated API started', server.started)
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True, executable_path=child['chromium_executable'])
            context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
            base = f"http://127.0.0.1:{child['port']}"
            external, js_errors = [], []
            async def route(r):
                if not r.request.url.startswith(base + '/'):
                    external.append(r.request.url); await r.abort()
                else: await r.continue_()
            await context.route('**/*', route)
            page = await context.new_page()
            page.on('pageerror', lambda error: js_errors.append(str(error)))
            await page.goto(base, wait_until='networkidle')
            draft = page.locator('#draft-natural-zh')
            await draft.fill('人工稿必须保留：清理不自动改稿。')
            button = page.get_by_test_id('resource-cleanup')
            validate(child_path)
            async with page.expect_response(lambda r: r.url.endswith('/runtime/resources/cleanup')) as response:
                await button.click()
                check('control disabled during action', await button.is_disabled())
            body = await (await response.value).json()
            write(out / 'cleanup-response.json', body)
            verdict = body['data']
            check('public response explicitly scoped', verdict['verification_scope'] == 'original_service_exit_and_resource_bound')
            check('fixture original-handle cleanup' if fixture else 'real local maintenance verdict recorded',
                  verdict['status'] == 'released' if fixture else verdict['status'] in {'noop', 'released', 'blocked', 'unknown'})
            await page.get_by_test_id('cleanup-result').get_by_text('清理前：', exact=False).wait_for()
            check('manual draft retained', await draft.input_value() == '人工稿必须保留：清理不自动改稿。')
            if fixture:
                app.state.analysis._controller_busy = True
                await button.click()
                await page.get_by_text('资源清理未完成：', exact=False).wait_for()
                app.state.analysis._controller_busy = False
                app.state.status_failure = True
                await page.get_by_role('button', name='再次检查服务').click()
                await page.get_by_text('服务状态检查失败', exact=False).wait_for()
                check('cleanup failure not overwritten by recheck failure', 'RESOURCE_BUSY' in await page.get_by_test_id('cleanup-result').inner_text())
                app.state.status_failure = False
                await page.get_by_role('button', name='再次检查服务').click()
                await page.get_by_text('服务状态检查失败', exact=False).wait_for(state='hidden')
                check('successful refresh clears only refresh error', 'RESOURCE_BUSY' in await page.get_by_test_id('cleanup-result').inner_text())
            await page.screenshot(path=str(out / 'desktop.png'), full_page=True)
            await page.set_viewport_size({'width': 390, 'height': 844})
            check('mobile layout contained', await page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            await page.screenshot(path=str(out / 'mobile.png'), full_page=True)
            check('no JS errors or outside browser requests', not js_errors and not external)
            result['status'] = 'PASS_FIXTURE_ONLY' if fixture else 'REAL_ZERO_MODEL_OBSERVATION_ONLY'
    except BaseException as error:
        result.update(status='FAIL_OR_BLOCKED', error_type=type(error).__name__, error=str(error))
    finally:
        context_closed = context is None or await step('context.close', context.close)
        browser_closed = browser is None or await step('browser.close', browser.close)
        driver_closed = pw is None or await step('playwright.stop', pw.stop)
        if server: server.should_exit = True
        async def stop_server(): await task
        api_closed = task is None or await step('api.shutdown', stop_server, 15)
        if runtime:
            await step('original runtime.close', runtime.close, 15)
        if sock:
            try: sock.close()
            except OSError: cleanup_errors.append({'step': 'socket.close', 'error': 'OSError'})
        exit_proof = proof(native) if native else {}
        native_exited = (native is None or (exit_proof.get('state') == 'exited'
            and exit_proof.get('pid') == native_identity.get('pid')
            and exit_proof.get('birth_ticks') == native_identity.get('birth_ticks')
            and exit_proof.get('listener_owned') is False))
        if native: write(out / 'native-final.json', exit_proof)
        known = bool(context_closed and browser_closed and driver_closed and api_closed and native_exited
                     and (runtime is None or (not runtime._owned() and runtime._native is None)) and not cleanup_errors)
        result['cleanup'] = dict(context_closed=context_closed, browser_closed=browser_closed,
            driver_closed=driver_closed, api_closed=api_closed, native_exited=native_exited,
            private_data_retained_for_diagnostics=True, recursive_deletion_performed=False,
            original_runtime_remaining=bool(runtime and (runtime._owned() or runtime._native is not None)))
        try:
            # Trust budget debits, not attempted-call log lines.
            actual = ledger_row(child)['calls']
            result['model_actions'] = actual
            if known and actual == 0:
                result['authorization_terminal'] = authority.settle(child['run_id'], actual)
            else:
                authority.close_retaining_reservation(child['run_id'])
                result['authorization_terminal'] = 'UNKNOWN_OR_UNEXPECTED_CALLS_RESERVATION_RETAINED'
        except BaseException as error:
            cleanup_errors.append({'step': 'budget.terminal', 'error': type(error).__name__})
            try: authority.close_retaining_reservation(child['run_id'])
            except BaseException: pass
            known = False
        if cleanup_errors: result['status'] = 'FAIL_OR_BLOCKED'
        result['known_terminal'] = known
        write(out / 'receipt.json', result)
        print(json.dumps({'status': result['status'], 'checks': len(checks), 'known_terminal': known, 'model_actions': result['model_actions']}))
    return 0 if known and result['status'] in {'PASS_FIXTURE_ONLY', 'REAL_ZERO_MODEL_OBSERVATION_ONLY'} else 1


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(run(Path(sys.argv[1]).absolute())))
    except (ValueError, FileExistsError) as error:
        print('PRESTART_REFUSED:', type(error).__name__, str(error))
        raise SystemExit(2)
