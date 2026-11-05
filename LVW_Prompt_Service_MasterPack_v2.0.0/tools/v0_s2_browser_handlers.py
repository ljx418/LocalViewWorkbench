"""Real public/native browser evidence callbacks for a sealed Stage parent.

No CLI, authorization creation or service/browser launch. Requires a monitored
NativeRuntime, frozen native profile, original worker identity and parent-bound
authorization/tool/user-root preflight. Synthetic approvals are never supplied
by this module; caller-owned offline phases must return their actual receipts.
"""
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import valid_baseline
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import unquote

from tools.v0_s2_driver import base
from tools.v0_s2_runtime import read_jsonl
from tools.v0_s2_public_phase import encoded, exact_timeline
from tools.v0_s2_browser_evidence import analysis_join, adopted_export_join, document, public_graph
from tools.v0_s2_browser_owner import profile_baseline, verify_owner, verify_driver_listener
from tools.v0_s2_browser_supervisor import ACTIONS
from tools.v0_s2_cancel_phase import CancellationPhase, cancelled_history
from tools.v0_s2_fault_phase import FaultPhase
from tools.v0_s2_cancel_evidence import cancellation_trace, count
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import validate_binding


def default_offline_runner(driver, run_root, *, run_id, binding, fixture, reference, baseline_gpu_mib,
                           nvidia_exe, nvidia_sha256, authorize):
    """Compose the existing real cancellation/fault phases, once, in order.

    Creation performs no target actions. The caller supplies its already bound
    resources and phase budgets; no restart or inference retry is introduced.
    """
    validate_binding(binding, binding['issued_at'])
    if (type(baseline_gpu_mib) is not int or not valid_baseline(baseline_gpu_mib)
            or not re.fullmatch('[a-f0-9]{64}', nvidia_sha256) or not callable(authorize)
            or not isinstance(nvidia_exe, (str, Path)) or not str(nvidia_exe)):
        raise ValueError('INVALID_OFFLINE_RESOURCE_BINDINGS')
    binding = copy.deepcopy(binding); fixture = copy.deepcopy(fixture)
    used = False
    def execute(observe):
        nonlocal used
        if used: raise EvidenceError('browser offline runner is one-shot')
        used = True; observe()
        previous_observer = driver.resource_observer
        def guarded_authorize(action, case):
            observe(); authorize(action, case); observe()
        try:
            driver.resource_observer = observe
            cancellation = CancellationPhase(driver, run_root, run_id=run_id, binding=binding, fixture=fixture,
                reference=reference, authorize=guarded_authorize).run()
            not_run = {'run_id': run_id, 'candidate_sha': binding['candidate_sha'],
                'authorization_sha256': binding['authorization_sha256'], 'decision': 'NOT_RUN', 'stage_pass_claim': False,
                'cases': {name: {'status': 'NOT_RUN'} for name in ('provider-root-stop', 'manual-offline', 'quarantine-entry', 'adopt-denied')}}
            if cancellation.get('decision') != 'CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE':
                return {'cancellation': cancellation, 'fault': not_run}
            observe(); guarded_authorize('start_comfy_only_fault_sampler', 'provider-root-stop')
            driver.prepare_fault_sampler(run_root, nvidia_exe=nvidia_exe, nvidia_sha256=nvidia_sha256)
            driver.resource_observer = observe
            observe()
            fault = FaultPhase(driver, run_root, run_id=run_id, binding=binding, fixture=fixture, reference=reference,
                baseline_gpu_mib=baseline_gpu_mib, authorize=guarded_authorize).run()
            observe()
            return {'cancellation': cancellation, 'fault': fault}
        finally:
            driver.resource_observer = previous_observer
    return execute


class BrowserHandlers:
    def __init__(self, driver, *, config, binding, fixture, worker_birth, temporary_root,
                 authorize, verify_bindings, run_offline):
        if (not callable(getattr(driver, 'resource_observer', None)) or getattr(driver, 'native_audit', False) is not True
                or getattr(driver, 'warm_benchmark', False) is not False
                or any(not callable(f) for f in (authorize, verify_bindings, run_offline))):
            raise ValueError('MONITORED_DEFAULT_RUNTIME_AND_PARENT_BINDINGS_REQUIRED')
        validate_binding(binding, binding['issued_at'])
        if (binding['candidate_sha'] != config['candidate_sha'] or binding['authorization_sha256'] != config['authorization_sha256']
                or fixture['sha256'] != config['sample_sha256'] or fixture['bytes'] != config['sample_bytes']):
            raise ValueError('BROWSER_NATIVE_CONFIG_IDENTITY_MISMATCH')
        self.driver = driver; self.config = copy.deepcopy(config); self.binding = copy.deepcopy(binding)
        self.fixture = copy.deepcopy(fixture); self.worker = copy.deepcopy(worker_birth)
        self.root = Path(config['run_root']); self.temporary = Path(temporary_root)
        if not self.root.is_absolute() or not self.temporary.is_absolute(): raise ValueError('ABSOLUTE_BROWSER_ROOTS_REQUIRED')
        self.authorize = authorize; self.verify = verify_bindings; self.run_offline = run_offline
        self.directory = self.root/'temp/browser-phase/parent-evidence'
        self.ready = False; self.sessions = {}; self.seen = set(); self.completed = set(); self.lock = threading.RLock()
        self.artifacts = []; self.ordinal = 0; self.owner = None; self.offline = None

    def callbacks(self):
        return {action: self._handler(action) for action in ACTIONS}

    def _handler(self, action):
        def execute(payload, observe):
            self.authorize(action, copy.deepcopy(payload)); observe()
            if action != 'preflight' and not self.ready: raise EvidenceError('browser preflight not complete')
            if action != 'preflight': self._lease()
            value = getattr(self, action)(copy.deepcopy(payload), observe)
            observe()
            return value
        return execute

    def artifact(self, name, value):
        raw = value if isinstance(value, bytes) else encoded(value)
        if len(raw) > 24*1024*1024 or not re.fullmatch('[A-Za-z0-9._-]{1,100}', name):
            raise EvidenceError('browser parent artifact bound')
        # Concurrent user-write approvals and offline phases need unique names.
        with self.lock:
            self.ordinal += 1; filename = f'{self.ordinal:04d}-'+name
            with (self.directory/filename).open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            self.artifacts.append({'file': filename, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        return filename

    def plain(self, path, maximum):
        path = Path(path)
        path.relative_to(self.root)
        for p in (path, *path.parents):
            info = p.lstat()
            if p.is_symlink() or getattr(info, 'st_file_attributes', 0)&0x400: raise EvidenceError('browser artifact/source redirect')
            if p == self.root: break
        if path.resolve(strict=True) != path or not path.is_file() or path.stat().st_size > maximum:
            raise EvidenceError('browser artifact/source invalid')
        raw = path.read_bytes()
        if len(raw) > maximum: raise EvidenceError('browser artifact/source grew')
        return raw

    def worker_artifact(self, name):
        if not re.fullmatch('[A-Za-z0-9._-]{1,80}', name): raise EvidenceError('invalid browser artifact name')
        return self.plain(self.root/'temp/browser-phase/evidence'/name, 24*1024*1024)

    def _lease(self):
        if document(self.plain(self.root/'temp/lvw-native-profile.json', 4096)) != self.binding:
            raise EvidenceError('native browser profile changed')

    def _source(self, reference):
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}', reference) or '..' in reference:
            raise EvidenceError('browser reference invalid')
        raw = self.plain(self.root/'input'/reference, 8*1024*1024)
        if len(raw) != self.fixture['bytes'] or hashlib.sha256(raw).hexdigest() != self.fixture['sha256']:
            raise EvidenceError('browser source differs from frozen sample')

    def _roots(self, observe, *, inference=True):
        observe(); comfy = self.driver.owned_listener_birth(8191); observe()
        if hasattr(self, 'comfy') and comfy != self.comfy: raise EvidenceError('browser Comfy owner changed')
        if inference:
            ollama = self.driver.owned_listener_birth(11434); observe()
            if (ollama['pid'], ollama['start_ticks']) != (self.binding['ollama_pid'], self.binding['ollama_start_ticks']):
                raise EvidenceError('browser Ollama root changed')
        return comfy

    def request(self, path, observe):
        observe()
        status, value = self.driver._json_request(base.COMFY_URL+path, timeout=2, observer=observe)
        if status != 200: raise EvidenceError('browser parent public read failed')
        return value

    def journal(self):
        return read_jsonl(self.root/'temp/lvw-native-events.jsonl', limit=8*1024*1024)

    def delta(self, session):
        events = self.journal(); before = session['journal_before']
        if events[:len(before)] != before: raise EvidenceError('browser native prefix replaced')
        delta = events[len(before):]
        if before and delta and delta[0]['monotonic_seconds'] < before[-1]['monotonic_seconds']:
            raise EvidenceError('browser appended stale native run')
        return delta

    def prefix(self):
        value = self.driver.chat_log_snapshot(); count(value); return value

    def preflight(self, payload, observe):
        if self.ready or payload.get('run_root') != str(self.root): raise EvidenceError('browser preflight replay/root')
        proof = self.verify(self.config, 'preflight'); observe()
        if proof.get('owned_run_root') != str(self.root) or self.root.resolve(strict=True) != self.root:
            raise EvidenceError('browser owned root unproven')
        self._lease()
        self.directory.mkdir(exist_ok=False)
        self.artifact('preflight.json', proof); self.ready = True
        return {'owned_run_root': str(self.root)}

    def browser_start(self, payload, observe):
        proof = self.verify(self.config, 'browser_start'); observe()
        if proof.get('owned_run_root') != str(self.root) or proof.get('ephemeral_user_root_verified') is not True:
            raise EvidenceError('browser ephemeral user root/dependencies unproven')
        self.comfy = self._roots(observe)
        if proof.get('comfy_pid') != self.comfy['pid']: raise EvidenceError('browser user root owner mismatch')
        self.before_profiles = profile_baseline(self.temporary)
        self.artifact('launch-bindings.json', {'proof': proof, 'comfy': self.comfy, 'profiles_before': self.before_profiles})
        return {'ephemeral_user_root_verified': True, 'comfy_pid': self.comfy['pid']}

    def browser_owner(self, payload, observe):
        self._roots(observe)
        self.owner = verify_owner(payload, worker_birth=self.worker, browser_executable=self.config['browser_executable'],
            expected_sha256=self.config['browser_executable_sha256'], temporary_root=self.temporary, before_profiles=self.before_profiles)
        if not re.fullmatch('[a-f0-9]{64}', payload.get('driver_endpoint_sha256', '')):
            raise EvidenceError('browser driver endpoint identity absent')
        self.owner['driver_listener'] = verify_driver_listener(self.worker, payload.get('driver_port'))
        self.owner['driver_endpoint_sha256'] = payload['driver_endpoint_sha256']
        self.artifact('independent-browser-owner.json', self.owner)
        return {}

    def upload(self, payload, observe):
        self._roots(observe)
        if payload != {'bytes': self.fixture['bytes'], 'sha256': self.fixture['sha256']}:
            raise EvidenceError('browser upload permission bytes mismatch')
        self._source(Path(self.config['sample_path']).name)
        self.artifact('upload-permission.json', payload)
        return {}

    def case_begin(self, payload, observe):
        case = payload.get('case_id')
        with self.lock:
            if case not in ('complete', 'cancel') or case in self.sessions or (case == 'cancel' and 'complete' not in self.completed):
                raise EvidenceError('browser case sequence invalid')
            upload = document(self.worker_artifact('upload-response.json'))
            if upload.get('sha256') != self.fixture['sha256'] or upload.get('bytes') != self.fixture['bytes']:
                raise EvidenceError('browser actual upload does not match sample')
            reference = upload['video_reference']; self._source(reference); self._roots(observe)
            before = self.prefix(); events = self.journal()
            if ({e['run_token'] for e in events if e['event'] == 'run_started'}
                    != {e['run_token'] for e in events if e['event'] == 'run_finished'}):
                raise EvidenceError('browser previous native run incomplete')
            self.sessions[case] = {'reference': reference, 'before': before, 'journal_before': events, 'graph': None, 'prompt_id': None}
            self.artifact(case+'-before.json', self.sessions[case])
        return {}

    def public_submit(self, payload, observe):
        case = payload['case_id']; session = self.sessions[case]; graph = payload['body']['prompt']
        with self.lock:
            if session['graph'] is not None: raise EvidenceError('browser duplicate submission')
            public_graph(graph, session['reference']); self._source(session['reference']); self._roots(observe)
            ordinal = self.driver.reserve_public_submission()
            session['graph'] = copy.deepcopy(graph)  # Failures consume the global slot.
            self.artifact(case+'-submit-permission.json', {'stage_submission_ordinal': ordinal, 'body': payload['body']})
        return {}

    def case_queued(self, payload, observe):
        with self.lock:
            case = payload['case_id']; session = self.sessions[case]; prompt = payload['prompt_id']
            if (payload['body']['prompt'] != session['graph'] or session['prompt_id'] is not None
                    or not re.fullmatch('[a-fA-F0-9-]{1,80}', prompt) or prompt in self.seen):
                raise EvidenceError('browser actual queue differs from permitted graph')
            self.seen.add(prompt); session['prompt_id'] = prompt
            self.artifact(case+'-actual-queue.json', payload)
        return {}

    def _current(self, session, observe):
        status = self.request('/lvw/v0/video/status', observe); events = self.delta(session)
        starts = [e for e in events if e['event'] == 'run_started']
        if len(starts) > 1: raise EvidenceError('browser unexpected native run')
        if not starts: return status, events, None
        start = starts[0]
        if (start['candidate_sha'] != self.binding['candidate_sha'] or start['authorization_sha256'] != self.binding['authorization_sha256']
                or start['owner_pid'] != self.comfy['pid'] or status.get('run_token') != start['run_token']):
            raise EvidenceError('browser current owner/token unproven')
        return status, events, start['run_token']

    def busy_manual(self, payload, observe):
        session = self.sessions['complete']
        if payload.get('prompt_id') != session['prompt_id']: raise EvidenceError('browser busy prompt mismatch')
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            status, events, token = self._current(session, observe)
            if token:
                if status['status'] not in ('preparing', 'running') or any(e['event'] == 'run_finished' for e in events):
                    raise EvidenceError('browser busy window missed')
                self.artifact('busy-manual-window.json', {'public_status': status, 'native_events': events})
                return {}
            observe(); time.sleep(.05)
        raise EvidenceError('browser busy run not started')

    def cancel_ready(self, payload, observe):
        session = self.sessions['cancel']
        if payload.get('prompt_id') != session['prompt_id']: raise EvidenceError('browser cancel prompt mismatch')
        self._roots(observe)
        status, events, token = self._current(session, observe)
        if token is None: return {'ready': False}
        if status['status'] not in ('preparing', 'running') or any(e['event'] == 'run_finished' for e in events):
            raise EvidenceError('browser cancel window missed')
        sent = [e for e in events if e['event'] == 'provider_request_sent']
        closed = {e['call_index'] for e in events if e['event'] == 'provider_connection_closed'}
        active = [e for e in sent if e['call_index'] not in closed]
        if len(active) > 1: raise EvidenceError('browser overlapping provider windows')
        if not active: return {'ready': False}
        prepared = [e for e in events if e['event'] == 'source_prepared']
        if len(prepared) != 1: raise EvidenceError('browser cancel source missing')
        exact_timeline(prepared[0], self.fixture)
        observe(); response, inventory = self.driver._json_request(base.OLLAMA_URL+'/api/ps', timeout=2, observer=observe)
        models = inventory.get('models')
        if response != 200 or not isinstance(models, list): raise EvidenceError('browser resident inventory invalid')
        if not models: return {'ready': False}
        model = models[0]
        if (len(models) != 1 or model.get('model', model.get('name')) != 'gemma4:26b'
                or model.get('digest') != self.binding['model_digest'] or type(model.get('size_vram')) is not int or model['size_vram'] <= 0):
            raise EvidenceError('browser wrong resident model')
        latest = self.delta(session)
        if any(e['event'] in ('run_finished', 'provider_connection_closed') and
                (e['event'] == 'run_finished' or e['call_index'] == active[0]['call_index']) for e in latest):
            raise EvidenceError('browser provider window ended during inventory')
        session['token'] = token
        self.artifact('cancel-resident-window.json', {'status': status, 'events': latest, 'api_ps': inventory})
        return {'ready': True, 'run_token': token}

    def _terminal(self, session, observe, seconds):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            status, events, token = self._current(session, observe)
            if token and any(e['event'] == 'run_finished' for e in events):
                history = self.request('/history/'+session['prompt_id'], observe)
                if session['prompt_id'] in history and status.get('resource_state') == 'released':
                    return status, events, token, history
            observe(); time.sleep(.2)
        raise EvidenceError('browser terminal proof timeout')

    def case_finished(self, payload, observe):
        case = payload['case_id']; target = 'cancel' if case == 'cancel' else 'complete'; session = self.sessions[target]
        if payload.get('prompt_id') != session['prompt_id'] or case in self.completed:
            raise EvidenceError('browser finished identity/replay')
        self._roots(observe); self._source(session['reference'])
        if case == 'complete':
            if 'analysis_before_adoption' not in self.completed or payload.get('export_file') != 'adopted-export.json':
                raise EvidenceError('browser analysis/export order')
            if payload.get('raw_sha256') != session['analysis']['raw_sha256']: raise EvidenceError('browser raw changed at adoption')
            adopted = document(self.worker_artifact('adoption-response.json'))['result']
            value = adopted_export_join(self.worker_artifact('adopted-export.json'), analysis=session['analysis'],
                adoption_response=self.worker_artifact('adoption-response.json'), expected_draft=adopted['draft'])
            self.artifact('adoption-export-join.json', value); session['export_join'] = value
        elif case in ('analysis_before_adoption', 'cancel'):
            status, events, token, history = self._terminal(session, observe, 35 if case == 'cancel' else 12)
            after = self.prefix(); samples = self.driver._resource_worker.points()
            facts = {'history': history, 'prompt_id': session['prompt_id'], 'graph': session['graph'],
                'reference': session['reference'], 'fixture': self.fixture, 'before': session['before'], 'after': after,
                'events': events, 'binding': self.binding, 'owner_pid': self.comfy['pid'], 'resource_samples': samples}
            self.artifact(target+'-terminal-facts.json', {'public_status': status, **facts})
            if case == 'analysis_before_adoption':
                value = analysis_join(**facts)
                if payload.get('raw_sha256') != value['raw_sha256']: raise EvidenceError('browser visible raw differs from native/public response')
                session['analysis'] = value; session['analysis_facts'] = facts
            else:
                if payload.get('acknowledgement_file') != 'cancel-ack.json' or token != session.get('token'):
                    raise EvidenceError('browser cancel acknowledgement/current token mismatch')
                ack = document(self.worker_artifact('cancel-ack.json'))
                value = cancellation_trace(events, binding=self.binding, token=token, owner_pid=self.comfy['pid'], kind='provider',
                    ack=ack, before=session['before'], after=after, resource_samples=samples)
                value['public_failure'] = cancelled_history(history, session['prompt_id'], session['graph'])
                if status.get('status') != 'cancelled' or status.get('error_code') != 'JOB_CANCELLED' or status.get('cancel_epoch') != 1:
                    raise EvidenceError('browser public cancellation not terminal')
                prepared = [e for e in events if e['event'] == 'source_prepared']
                if len(prepared) != 1: raise EvidenceError('browser cancellation source not unique')
                exact_timeline(prepared[0], self.fixture)
                session['cancel_facts'] = {'events': events, 'binding': self.binding, 'token': token,
                    'owner_pid': self.comfy['pid'], 'kind': 'provider', 'ack': ack, 'before': session['before'],
                    'after': after, 'resource_samples': samples, 'history': history, 'graph': session['graph'], 'prompt_id': session['prompt_id']}
            self.artifact(target+'-joined.json', value)
        else: raise EvidenceError('browser unknown terminal case')
        if list((self.root/'temp').glob('lvw-video-*')) or list((self.root/'input').glob('lvw-upload-*.part')):
            raise EvidenceError('browser decoder/upload snapshot remains')
        self.completed.add(case)
        return {'run_token': session['analysis']['run_token']} if case == 'analysis_before_adoption' else {}

    def user_write(self, payload, observe):
        path = payload.get('pathname', '')
        if not isinstance(path, str): raise EvidenceError('browser ephemeral write path type invalid')
        decoded = unquote(unquote(path))
        if (not isinstance(path, str) or len(path) > 1024 or '..' in decoded or '\\' in decoded or '\0' in decoded
                or '%' in decoded or payload.get('method') not in ('POST', 'PUT', 'DELETE')
                or type(payload.get('bytes')) is not int or not 0 <= payload['bytes'] <= 1024*1024
                or not (decoded == '/settings' or decoded.startswith('/settings/') or decoded.startswith('/userdata/'))):
            raise EvidenceError('browser ephemeral write path/method/body invalid')
        proof = self.verify(self.config, 'user_write'); observe(); self._roots(observe, inference=False)
        if (proof.get('owned_run_root') != str(self.root) or proof.get('ephemeral_user_root_verified') is not True
                or proof.get('comfy_pid') != self.comfy['pid']): raise EvidenceError('browser user write owner/root unproven')
        self.artifact('ephemeral-user-write.json', {'request': payload, 'root_proof': proof})
        return {}

    def offline_op(self, payload, observe):
        if 'cancel' not in self.completed or self.offline is not None or payload != {'require_owned_ollama_stopped': True}:
            raise EvidenceError('browser offline order/permission invalid')
        self._roots(observe); self.offline = {'decision': 'STARTED_NOT_VERIFIED'}
        receipts = self.run_offline(observe); observe()
        expected = {'cancellation': ('CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', {'preparation', 'provider'}),
            'fault': ('FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', {'provider-root-stop', 'manual-offline', 'quarantine-entry', 'adopt-denied'})}
        if set(receipts) != set(expected): raise EvidenceError('browser offline full phase set missing')
        for name, (decision, cases) in expected.items():
            receipt = receipts[name]
            if (receipt.get('decision') != decision or receipt.get('candidate_sha') != self.binding['candidate_sha']
                    or receipt.get('authorization_sha256') != self.binding['authorization_sha256']
                    or receipt.get('run_id') != self.config['run_id']
                    or receipt.get('stage_pass_claim') is not False or set(receipt.get('cases', {})) != cases
                    or any(r.get('status') != 'PASS' for r in receipt['cases'].values())
                    or receipt.get('test_counts') != {'fixed': len(cases), 'PASS': len(cases), 'FAIL': 0, 'NOT_RUN': 0}):
                raise EvidenceError('browser offline phase not independently complete')
        stop = self.driver.listener_terminal_states.get('11434', {})
        if (stop.get('owned_listener_pid') != self.binding['ollama_pid'] or stop.get('terminal_absent') is not True
                or stop.get('lineage_reproven') is not True or stop.get('root_stop', {}).get('original_absent') is not True
                or stop.get('root_stop', {}).get('pid') != self.binding['ollama_pid']
                or stop.get('root_stop', {}).get('state') != 'STOPPED'
                or stop.get('root_stop', {}).get('termination_requested') is not True
                or self.driver._listener_pid_values(11434)):
            raise EvidenceError('browser offline owned Ollama stop not proven')
        self._roots(observe, inference=False)
        self.offline = {'receipts': receipts, 'owned_stop': copy.deepcopy(stop)}
        self.artifact('offline-phase-proofs.json', self.offline)
        return {'owned_ollama_stopped': True, 'comfy_pid': self.comfy['pid']}
