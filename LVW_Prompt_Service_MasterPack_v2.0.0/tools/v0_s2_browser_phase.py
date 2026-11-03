"""One browser component of a complete child-authorized S2 Stage run.

No CLI or authorization creation. The full parent owns native services, frozen
preflight/dependencies, phase budgets, archival and final Stage cleanup/review.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

from tools.v0_s2_driver import ROOT
from tools.v0_s2_public_phase import encoded
from tools.v0_s2_browser_evidence import document
from tools.v0_s2_browser_handlers import BrowserHandlers
from tools.v0_s2_browser_owner import birth, executable, cleanup_witness
from tools.v0_s2_browser_supervisor import Supervisor
from tools.v0_s2_browser_terminal import load_artifacts, terminal_join
from tools.v0_s2_checkpoint_oracles import EvidenceError


def run_browser_phase(driver, *, config, binding, fixture, node_executable, node_sha256,
                      authorize_launch, authorize_action, verify_bindings, run_offline):
    if any(not callable(f) for f in (authorize_launch, authorize_action, verify_bindings, run_offline)):
        raise ValueError('SEALED_PARENT_BINDINGS_REQUIRED')
    config = copy.deepcopy(config)
    # Must validate ACTIVE Mother/child, complete source/dependency/offline gate,
    # exact tool/sample/port/process/budget bindings BEFORE reads or writes here.
    proof = authorize_launch(copy.deepcopy(config))
    if (proof.get('owned_run_root') != config['run_root'] or proof.get('candidate_sha') != config['candidate_sha']
            or proof.get('authorization_sha256') != config['authorization_sha256'] or proof.get('node_sha256') != node_sha256):
        raise EvidenceError('browser launch authority identities unproven')
    root = Path(config['run_root'])
    if root.resolve(strict=True) != root: raise EvidenceError('browser launch root not canonical')
    node = Path(node_executable)
    if node.resolve(strict=True) != node or executable(node)['sha256'] != node_sha256:
        raise EvidenceError('browser Node executable mismatch')
    for key, path in (('harness_sha256', ROOT/'tools/v0_s2_browser_acceptance.cjs'),
                      ('policy_sha256', ROOT/'tools/v0_s2_browser_policy.cjs'),
                      ('ui_workflow_sha256', ROOT/'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != config[key]: raise EvidenceError('browser frozen launch source mismatch')
    directory = root/'temp/browser-phase'; directory.mkdir(exist_ok=False)
    temporary = root/'temp/browser-os'; temporary.mkdir(exist_ok=False)
    cfg_path = directory/'config.json'; cfg_raw = encoded(config)
    if len(cfg_raw) > 65536: raise EvidenceError('browser config limit')
    with cfg_path.open('xb') as output: output.write(cfg_raw)
    result = {'kind': 'BROWSER_PHASE_COORDINATOR_NOT_STAGE_ACCEPTANCE', 'decision': 'NO_GO', 'stage_pass_claim': False,
        **{k: config[k] for k in ('candidate_sha', 'authorization_sha256', 'run_id')},
        'parent_cleanup_required': True, 'node_started': False, 'callbacks_pending': 0}
    process = supervisor = handlers = None
    try:
        authorize_action('browser_worker_start', {'config_sha256': hashlib.sha256(cfg_raw).hexdigest()})
        # No inherited Node injection/proxy/display/provider environment. A fresh
        # private temp/cache/config root is used, never an existing browser profile.
        env = {'PATH': str(node.parent)+':/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC',
            'TMPDIR': str(temporary), 'TMP': str(temporary), 'TEMP': str(temporary),
            'XDG_CONFIG_HOME': str(temporary/'config'), 'XDG_CACHE_HOME': str(temporary/'cache'),
            'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD': '1', 'NO_PROXY': '127.0.0.1,localhost'}
        command = [str(node), str(ROOT/'tools/v0_s2_browser_acceptance.cjs'), '--config', str(cfg_path)]
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0, start_new_session=True, env=env)
        result['node_started'] = True
        original = birth(process.pid)
        def verify_worker(handle, current_config):
            authorize_action('browser_worker_identity', {'pid': process.pid})
            actual = birth(process.pid)
            if (handle is not process or current_config != config or process.poll() is not None
                    or actual['parent'] != os.getpid() or actual['group'] != process.pid or actual['session'] != process.pid
                    or any(actual[k] != original[k] for k in ('pid', 'parent', 'group', 'session', 'start_ticks'))
                    or Path(f'/proc/{process.pid}/exe').resolve(strict=True) != node
                    or executable(f'/proc/{process.pid}/exe', kernel=True)['sha256'] != node_sha256
                    or Path(f'/proc/{process.pid}/cmdline').read_bytes().rstrip(b'\0').split(b'\0') != [os.fsencode(v) for v in command]
                    or cfg_path.read_bytes() != cfg_raw): raise EvidenceError('browser original worker unproven')
        handlers = BrowserHandlers(driver, config=config, binding=binding, fixture=fixture, worker_birth=original,
            temporary_root=temporary, authorize=authorize_action, verify_bindings=verify_bindings, run_offline=run_offline)
        supervisor = Supervisor(config, handlers=handlers.callbacks(), authorize_owned_worker=verify_worker,
            resource_observer=driver.resource_observer)
        transport = supervisor.run(process, directory/'parent'); result['transport'] = transport
        if transport['decision'] != 'TRANSPORT_COMPLETED_REQUIRES_PRODUCT_ORACLES': raise EvidenceError('browser transport failed')
        if handlers.owner is None: raise EvidenceError('browser original owner absent')
        cleanup = cleanup_witness(handlers.owner, temporary_root=temporary); result['independent_cleanup'] = cleanup
        evidence = directory/'evidence'
        worker = document(handlers.plain(evidence/'browser-result.json', 1024*1024))
        files = load_artifacts(evidence, worker)
        window_files = [r for r in handlers.artifacts if r['file'].endswith('-busy-manual-window.json')]
        if len(window_files) != 1: raise EvidenceError('browser busy observation not unique')
        busy = document(handlers.plain(handlers.directory/window_files[0]['file'], 24*1024*1024))
        joined = terminal_join(config=config, result=worker, artifacts=files, supervisor=transport,
            analysis_facts=handlers.sessions['complete']['analysis_facts'], cancel_facts=handlers.sessions['cancel']['cancel_facts'],
            busy_window=busy, offline_proofs=handlers.offline, independent_cleanup=cleanup)
        result.update(decision='BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE', oracle=joined)
    except Exception as error:
        result['error_code'] = type(error).__name__+':'+str(error)
    finally:
        errors = []
        if process is not None:
            try:
                if process.stdin and not process.stdin.closed: process.stdin.close()
                try: process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    # Only the original unreaped Popen child, never a claimed PID/group.
                    process.kill(); process.wait(timeout=5); result['owned_node_forced_stop'] = True
            except Exception as error: errors.append('node:'+type(error).__name__)
            result['node_original_terminal'] = process.poll() is not None
            result['node_exit_code'] = process.returncode
            for label, stream in (('stdout', process.stdout), ('stderr', process.stderr)):
                if (stream and not stream.closed and process.poll() is not None
                        and not (directory/'parent'/('worker.'+label+('.jsonl' if label == 'stdout' else '.log'))).exists()):
                    try:
                        value = stream.read(2*1024*1024+1)
                        if value is None: value = b''
                        if len(value) > 2*1024*1024: errors.append(label+':CAPTURE_LIMIT'); value = value[:2*1024*1024]
                        with (directory/('unobserved-worker.'+label+'.log')).open('xb') as output: output.write(value)
                    except Exception as error: errors.append(label+':'+type(error).__name__)
                if stream and not stream.closed: stream.close()
        if supervisor is not None:
            supervisor.abort.set()
            try: result['callbacks_pending'] = supervisor.drain_callbacks()
            except Exception as error: errors.append('callbacks:'+type(error).__name__); result['callbacks_pending'] = -1
        result['browser_cleanup_proven'] = process is None or (supervisor is not None and 'browser_start' not in supervisor.protocol.completed)
        if handlers is not None:
            result['parent_artifacts'] = copy.deepcopy(handlers.artifacts)
            if handlers.owner is not None:
                try:
                    result['independent_cleanup'] = cleanup_witness(handlers.owner, temporary_root=temporary)
                    result['browser_cleanup_proven'] = result['independent_cleanup']['decision'] == 'BROWSER_CLEANUP_PROVEN'
                except Exception as error: errors.append('browser:'+type(error).__name__)
        if errors: result['cleanup_errors'] = errors
        if (errors or not result['browser_cleanup_proven'] or result['callbacks_pending']
                or (process is not None and process.returncode != 0)): result['decision'] = 'NO_GO'
        with (directory/'phase-receipt.json').open('x') as output:
            output.write(json.dumps(result, indent=2)+'\n')
    return result
