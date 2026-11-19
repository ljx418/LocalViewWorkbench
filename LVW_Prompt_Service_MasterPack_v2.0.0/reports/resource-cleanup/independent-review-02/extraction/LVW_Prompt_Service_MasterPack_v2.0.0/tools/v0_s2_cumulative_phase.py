"""Re-execute the five accepted V0-Min obligations on the current candidate.

Online image/views precede the S2 browser/fault phase. Offline manual/state tests
follow its proven owned Ollama stop. No service startup, old authorization or
old PASS is reused; no CLI or Stage verdict is provided.
"""
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import valid_baseline
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time

from tools.v0_s2_driver import ROOT, base
from tools.v0_s2_http import PinnedLoopbackClient
from tools.v0_s2_public_phase import encoded
from tools.v0_s2_cancel_evidence import count
from tools.v0_s2_browser_evidence import result_validator
from tools.v0_s2_measurements import spec_validator
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraft, result_txt

_spec = importlib.util.spec_from_file_location('lvw_s2_historical_graph_helpers', ROOT/'reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py')
legacy = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(legacy)
CASES = ('V0-A01', 'V0-A03', 'V0-A04', 'V0-A05', 'V0-A08')


class CumulativePhase:
    def __init__(self, driver, run_root, *, run_id, binding, image, baseline_gpu_mib, authorize):
        if (not callable(authorize) or not callable(getattr(driver, 'resource_observer', None))
                or getattr(driver, 'warm_benchmark', False) is not False): raise ValueError('monitored default runtime required')
        if (not re.fullmatch('[a-f0-9]{40}', binding['candidate_sha']) or not re.fullmatch('[a-f0-9]{64}', binding['authorization_sha256'])
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}', run_id)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}', image['reference']) or '..' in image['reference']
                or not re.fullmatch('[a-f0-9]{64}', image['sha256']) or type(image['bytes']) is not int
                or not 0 < image['bytes'] <= 20*1024*1024 or type(baseline_gpu_mib) is not int
                or not valid_baseline(baseline_gpu_mib)): raise ValueError('cumulative identity/source invalid')
        self.driver = driver; self.root = Path(run_root).resolve(strict=True); self.run_id = run_id
        self.binding = copy.deepcopy(binding); self.image = copy.deepcopy(image); self.baseline = baseline_gpu_mib
        self.authorize = authorize; self.directory = self.root/'temp/cumulative-phase'
        self.cases = {c: {'status': 'NOT_RUN'} for c in CASES}; self.artifacts = []; self.actions = []; self.traces = []
        self.online_used = self.offline_used = self.online_complete = False; self.seen = set()
        self.raw = self.suggestion = None; self.active = None

    def action(self, name):
        self.authorize(name, self.active); self.driver.resource_observer()
        row = {'ordinal': len(self.actions)+1, 'case_id': self.active, 'action': name}
        with (self.directory/'actions.jsonl').open('ab') as stream:
            stream.write(encoded(row)); stream.flush(); os.fsync(stream.fileno())
        self.actions.append(row)

    def artifact(self, name, value):
        raw = value if isinstance(value, bytes) else encoded(value)
        if len(raw) > 8*1024*1024: raise EvidenceError('cumulative artifact cap')
        with (self.directory/name).open('xb') as stream: stream.write(raw)
        self.artifacts.append({'file': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def plain(self, path):
        path = Path(path); path.relative_to(self.root)
        for ancestor in (path, *path.parents):
            info = ancestor.lstat()
            if ancestor.is_symlink() or getattr(info, 'st_file_attributes', 0)&0x400: raise EvidenceError('cumulative file redirect')
            if ancestor == self.root: break
        if path.resolve(strict=True) != path or not path.is_file() or path.stat().st_size > 20*1024*1024:
            raise EvidenceError('cumulative file invalid')
        return path.read_bytes()

    def provider(self, name):
        self.action('provider_prefix'); value = self.driver.chat_log_snapshot(); count(value)
        self.artifact(name+'.json', value); return value

    def execute(self, graph, *, node='1', error=None):
        self.action('public_submit')
        ordinal = len(self.traces)+1
        trace = {'ordinal': ordinal, 'case_id': self.active, 'graph': copy.deepcopy(graph)}; self.traces.append(trace)
        prompt = self.driver.submit(graph); trace['prompt_id'] = prompt
        if not re.fullmatch('[a-fA-F0-9-]{1,80}', prompt) or prompt in self.seen: raise EvidenceError('cumulative queue ID reused/invalid')
        self.seen.add(prompt); trace['stage_submission_ordinal'] = self.driver.submissions
        deadline = time.monotonic()+(480 if self.active == 'V0-A01' else 30)
        while time.monotonic() < deadline:
            self.action('public_history')
            status, history = self.driver._json_request(base.COMFY_URL+'/history/'+prompt, timeout=2, observer=self.driver.resource_observer)
            if status == 200 and prompt in history: break
            time.sleep(.1)
        else: raise EvidenceError('cumulative history timeout')
        trace['history'] = history; self.artifact(f'trace-{ordinal:02d}.json', trace)
        record = history[prompt]
        if record['prompt'][1] != prompt or record['prompt'][2] != graph: raise EvidenceError('cumulative public graph mismatch')
        if error:
            errors = [v for name, v in record['status']['messages'] if name == 'execution_error']
            if (record.get('outputs') or record['status']['status_str'] != 'error' or len(errors) != 1
                    or str(errors[0]['node_id']) != node or errors[0]['node_type'] != graph[node]['class_type']
                    or errors[0]['prompt_id'] != prompt or json.loads(errors[0]['exception_message'])['code'] != error):
                raise EvidenceError('cumulative exact public failure missing')
            return None
        return base.workflow_oracle(history, prompt, node)

    def manual(self, fields, action, filename):
        return self.execute(legacy.manual_public_graph(fields, action, filename))

    def payload(self, text):
        result = legacy._manual_payload(text); result_validator().validate(result); return result

    def online_cases(self):
        self.active = 'V0-A01'
        raw = self.plain(self.root/'input'/self.image['reference'])
        if len(raw) != self.image['bytes'] or hashlib.sha256(raw).hexdigest() != self.image['sha256']:
            raise EvidenceError('cumulative image changed')
        before = self.provider('online-before')
        graph = json.loads((ROOT/'LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json').read_text())
        graph['1']['inputs']['image_reference'] = self.image['reference']
        graph['3'] = legacy.manual_public_graph({'natural_zh': ['1', 1]}, 'preview_json', 'metadata')['1']
        text = self.execute(graph, node='2'); record = self.traces[-1]['history'][self.traces[-1]['prompt_id']]
        metadata = json.loads(self.payload(record['outputs']['3']['text'])['draft']['natural_zh'])
        witness = base.validate_image_result(text); spec = json.loads(text[1]); spec_validator().validate(spec)
        envelope = json.loads(text[0])
        if envelope.get('model') != base.MODEL or envelope.get('done') is not True: raise EvidenceError('cumulative model response incomplete')
        after = self.provider('image-after')
        if not after['raw_log'].startswith(before['raw_log']) or count(after)-count(before) != 1: raise EvidenceError('cumulative image was cached/extra provider')
        if (metadata['source_sha256'] != self.image['sha256'] or metadata['source_bytes'] != self.image['bytes']
                or max(metadata['output_dimensions']) > 1024 or not re.fullmatch('[a-f0-9]{64}', metadata['output_rgb_sha256'])):
            raise EvidenceError('cumulative controlled image metadata differs')
        self.action('owned_image_release')
        release = self.driver.release_preload({**self.binding, 'baseline_gpu_mib': self.baseline}, self.driver._resource_worker)
        self.artifact('image-release.json', release)
        samples = release.get('gpu_samples', [])
        if (release.get('proven') is not True or release.get('loaded_models') != 0 or not 3 <= len(samples) <= 32
                or release.get('elapsed_seconds', 31) > 30
                or any(s['gpu_used_mib'] > self.baseline+1024 for s in samples[-3:])
                or any(not 1-1e-6 <= b['monotonic_seconds']-a['monotonic_seconds'] <= 1.5 for a, b in zip(samples, samples[1:]))):
            raise EvidenceError('cumulative physical release unproven')
        self.raw, self.suggestion = text
        self.cases[self.active] = {'status': 'PASS', 'source_sha256': self.image['sha256'], 'oracle': witness, 'provider_calls': 1}
        self.active = 'V0-A03'
        fields = {'natural_zh': spec['text_zh'], 'natural_en': spec['text_en'], 'image_prompt': spec['text_en'],
            'video_prompt': spec['text_en'], 'tags': ','.join(spec['tags']), 'negative': spec['negative'], 'edit_instruction': ''}
        texts = [self.manual(fields, a, 's2-a03') for a in ('preview_json', 'export_json', 'export_txt')]
        expected = ManualDraft.from_inputs(**fields)
        if any(self.payload(t)['draft'] != expected.outputs() for t in texts[:2]) or texts[2][1] != result_txt(expected):
            raise EvidenceError('cumulative four outputs/views changed')
        if self.plain(self.root/'output/lvw_manual/s2-a03.json') != texts[1][1].encode() or self.plain(self.root/'output/lvw_manual/s2-a03.txt') != texts[2][1].encode():
            raise EvidenceError('cumulative persisted export differs')
        last = self.provider('online-after')
        # Unload/inventory requests also append Provider logs. Preserve the
        # authenticated prefix and recompute chat counts, rather than requiring
        # byte-identical logs after physical model release.
        if not last['raw_log'].startswith(after['raw_log']) or count(last) != count(after):
            raise EvidenceError('cumulative view switch made provider call or log changed')
        self.cases[self.active] = {'status': 'PASS', 'four_outputs_preserved': True, 'extra_provider_calls': 0}

    def offline_cases(self):
        self.active = 'V0-A04'; before = self.provider('offline-before')
        stop = self.driver.listener_terminal_states.get('11434', {})
        if stop.get('terminal_absent') is not True or stop.get('owned_listener_pid') != self.binding['ollama_pid'] or self.driver._listener_pid_values(11434):
            raise EvidenceError('cumulative offline model stop unproven')
        self.artifact('offline-owned-stop.json', stop)
        fields = {k: v for k, v in legacy._node_inputs('稿'*20_000).items() if k not in ('action', 'filename')}
        outputs = [self.manual(fields, a, 's2-a04') for a in ('preview_json', 'copy_json', 'copy_txt', 'export_json', 'export_txt')]
        expected = ManualDraft.from_inputs(**fields)
        for index in (0, 1, 3):
            if self.payload(outputs[index])['draft'] != expected.outputs(): raise EvidenceError('cumulative exact20k/copy JSON changed')
        for index in (2, 4):
            if outputs[index][1] != result_txt(expected): raise EvidenceError('cumulative copy/TXT changed')
        if self.plain(self.root/'output/lvw_manual/s2-a04.json') != outputs[3][1].encode() or self.plain(self.root/'output/lvw_manual/s2-a04.txt') != outputs[4][1].encode():
            raise EvidenceError('cumulative offline export bytes changed')
        target = self.root/'output/lvw_manual/s2-a04-failure.json'
        self.action('owned_export_replace_fault'); target.mkdir(exist_ok=False)
        self.execute(legacy.manual_public_graph(fields, 'export_json', 's2-a04-failure'), error='DISK_FULL')
        if not target.is_dir() or list(target.parent.glob('.lvw-manual-*.tmp')): raise EvidenceError('cumulative failed export left artifacts')
        self.cases[self.active] = {'status': 'PASS', 'exact_characters': 20_000, 'failed_replace_preserved_target': True,
            'clipboard_scope': 'real public node copy actions; browser clipboard verified separately'}
        self.active = 'V0-A05'; token = self.run_id+'-state'
        chosen = {'natural_zh': 'kept bytes', 'natural_en': '', 'image_prompt': '', 'video_prompt': '', 'tags': [], 'negative': '', 'edit_instruction': ''}
        started = self.execute(legacy.state_public_graph('', 'start_run', token))[0]
        succeeded = self.execute(legacy.state_public_graph(started, 'model_success', token, raw=self.raw, suggestion=self.suggestion))[0]
        adopted = self.execute(legacy.state_public_graph(succeeded, 'adopt', token, draft=json.dumps(chosen)))[0]
        baseline = json.loads(adopted); negatives = []
        for name, action, code, callback, suggestion, error in (
            ('invalid_json', 'model_success', '', token+'-next', '{', 'PARSE_PARTIAL'),
            ('explicit_refusal', 'model_failure', 'MODEL_REFUSAL', token+'-next', '', None),
            ('timeout', 'model_failure', 'MODEL_TIMEOUT', token+'-next', '', None),
            ('oom', 'model_failure', 'GPU_OOM', token+'-next', '', None),
            ('stale_token', 'model_success', '', 'stale', '{}', 'ATTEMPT_STALE')):
            running = self.execute(legacy.state_public_graph(adopted, 'start_run', token+'-next'))[0]
            result = self.execute(legacy.state_public_graph(running, action, callback, raw='safe raw', suggestion=suggestion, error=code), error=error)
            final = json.loads(running if error else result[0])
            if final['draft'] != chosen or final['draft_epoch'] != baseline['draft_epoch'] or final['retry_count'] != 0:
                raise EvidenceError('cumulative failure callback changed draft/retried')
            negatives.append(name)
        self.cases[self.active] = {'status': 'PASS', 'negative_callbacks': negatives, 'scope': 'public state callbacks, not actual Provider failures', 'automatic_retries': 0}
        self.active = 'V0-A08'; empty = dict.fromkeys(fields, '')
        result = self.manual(empty, 'export_json', 's2-a08-empty'); value = self.payload(result)
        if ([value['source_type'], value['run_id'], value['analysis_status'], value['suggestion']] != ['manual', None, 'not_requested', None]
                or any(value['draft'][k] != ([] if k == 'tags' else '') for k in empty)
                or self.plain(self.root/'output/lvw_manual/s2-a08-empty.json') != result[1].encode()):
            raise EvidenceError('cumulative empty/no-model contract changed')
        after = self.provider('offline-after')
        if not after['raw_log'].startswith(before['raw_log']) or count(after) != count(before):
            raise EvidenceError('cumulative offline path invoked model or log changed')
        self.cases[self.active] = {'status': 'PASS', 'manual_contract_preserved': True, 'extra_provider_calls': 0}

    def run(self, segment):
        if (segment not in ('online', 'offline') or getattr(self, segment+'_used')
                or (segment == 'offline' and (not self.online_complete or hasattr(self, 'error')))):
            raise EvidenceError('cumulative segment order/replay')
        setattr(self, segment+'_used', True)
        self.authorize('cumulative_segment_begin', segment)
        if segment == 'online': self.directory.mkdir(exist_ok=False)
        self.active = 'V0-A01' if segment == 'online' else 'V0-A04'
        interrupted = None
        client = PinnedLoopbackClient(base.COMFY_URL); original = self.driver.clients[base.COMFY_URL]
        try:
            proof = client.pin(lambda: self.driver.owned_listener_birth(8191)); self.artifact(segment+'-peer.json', proof)
            if hasattr(self, 'peer') and proof != self.peer: raise EvidenceError('cumulative Comfy root changed between segments')
            self.peer = proof; self.driver.clients[base.COMFY_URL] = client
            (self.online_cases if segment == 'online' else self.offline_cases)()
            if segment == 'online': self.online_complete = True
        except BaseException as error:
            if self.active: self.cases[self.active] = {'status': 'FAIL', 'error': type(error).__name__+':'+str(error)}
            self.error = type(error).__name__+':'+str(error)
            if isinstance(error, (KeyboardInterrupt, SystemExit)): interrupted = error
        finally:
            self.driver.clients[base.COMFY_URL] = original; client.close()
            if client.reap_pending(timeout=2): self.error = 'CUMULATIVE_CONTROL_WORKER_REMAINS'
            result = {'run_id': self.run_id, 'candidate_sha': self.binding['candidate_sha'], 'authorization_sha256': self.binding['authorization_sha256'],
                'kind': 'V0_MIN_CURRENT_CANDIDATE_CUMULATIVE_NOT_STAGE_ACCEPTANCE', 'stage_pass_claim': False,
                'decision': 'NO_GO', 'cases': copy.deepcopy(self.cases), 'public_submissions': len(self.traces),
                'actions': copy.deepcopy(self.actions), 'artifacts': copy.deepcopy(self.artifacts)}
            statuses = [r['status'] for r in self.cases.values()]
            result['test_counts'] = {'fixed': 5, 'PASS': statuses.count('PASS'), 'FAIL': statuses.count('FAIL'), 'NOT_RUN': statuses.count('NOT_RUN')}
            if hasattr(self, 'error'): result['error_code'] = self.error
            elif segment == 'online': result['decision'] = 'ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING'
            elif statuses == ['PASS']*5 and len(self.traces) == 24: result['decision'] = 'CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE'
            self.artifact(segment+'-receipt.json', result)
        if interrupted is not None: raise interrupted
        return result
