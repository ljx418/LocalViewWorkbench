"""Current public nodes and real CPU exports/state, synthetic service/model/GPU."""
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from tools.v0_s2_cumulative_phase import CumulativePhase, CASES
from tools.v0_s2_driver import base
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import nodes
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.image_input import ControlledImageOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.tests.test_s2_cancel_evidence import prefix


class Transport:
    endpoint = 'http://127.0.0.1:11434/api/chat'
    def __init__(self): self.calls = 0
    def chat(self, payload, timeout_seconds):
        self.calls += 1
        return json.dumps({'model': base.MODEL, 'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps({
            'observations': ['red rectangle'], 'inferences': [], 'unknowns': [], 'prompt': 'a red rectangle', 'tags': ['red']})}})
    def cleanup(self, *args): pass


class Native:
    warm_benchmark = False
    def __init__(self, root, failure=None):
        self.root = root; self.failure = failure; self.submissions = 0; self.history = {}; self.stopped = False
        self.resource_observer = lambda: None; self.clients = {base.COMFY_URL: object()}; self.listener_terminal_states = {}
        self._resource_worker = object(); self.transport = Transport()
        clipboard = SimpleNamespace(write=lambda value: None)
        self.manual = nodes.LVWManualPromptOwner(owner=ManualDraftOwner(export_root=root/'output/lvw_manual',
            export_parent=root/'output', clipboard=clipboard))
        self.image = nodes.LVWControlledImageInput(owner=ControlledImageOwner(root/'input'))
        self.bridge = nodes.LVWImagePromptBridge(transport=self.transport, encoder=lambda frame: 'synthetic-encoded-image')
    def owned_listener_birth(self, port): return {'pid': 99 if self.failure == 'root' else 20, 'start_ticks': 100}
    def chat_log_snapshot(self):
        value = prefix(self.transport.calls+(1 if self.failure == 'extra-call' and self.submissions > 1 else 0))
        if self.failure in ('status-logs', 'changed-prefix', 'forged-count'):
            raw = value['raw_log']
            # Synthetic control traffic, mirroring the real unload/inventory
            # append observed in full-resource-ready-01; no model is invoked.
            if self.submissions:
                raw += '[GIN] POST "/api/generate"\n[GIN] GET "/api/ps"\n'
            if self.submissions > 1:
                raw += '[GIN] GET "/api/ps"\n'
                if self.failure == 'changed-prefix': raw = 'rewritten\n'+raw
            value.update(raw_log=raw, source_log_bytes=len(raw.encode()),
                source_log_sha256=hashlib.sha256(raw.encode()).hexdigest())
            if self.failure == 'forged-count' and self.submissions > 1: value['chat_calls'] += 1
        return value
    def release_preload(self, binding, worker):
        return {'proven': True, 'loaded_models': 0, 'elapsed_seconds': 3,
            'gpu_samples': [{'monotonic_seconds': i, 'gpu_used_mib': 1124} for i in range(3)]}
    def _listener_pid_values(self, port): return [] if self.stopped else [10]
    def stop_fixture(self):
        self.stopped = True; self.listener_terminal_states['11434'] = {'terminal_absent': True, 'owned_listener_pid': 10}
    def submit(self, graph):
        self.submissions += 1; prompt = f'{self.submissions:032x}'
        if self.failure == 'interrupt': raise KeyboardInterrupt()
        produced = {}; outputs = {}; status = {'status_str': 'success', 'messages': []}
        try:
            for name in sorted(graph, key=int):
                definition = graph[name]; inputs = copy.deepcopy(definition['inputs'])
                for key, value in list(inputs.items()):
                    if isinstance(value, list) and len(value) == 2: inputs[key] = produced[value[0]][value[1]]
                kind = definition['class_type']
                if kind == 'LVWControlledImageInput': result = self.image.load(**inputs)
                elif kind == 'LVWImagePromptBridge': result = self.bridge.analyze(**inputs)
                elif kind == 'LVWManualPromptOwner': result = self.manual.process(**inputs)
                elif kind == 'LVWDraftStateOwner': result = nodes.LVWDraftStateOwner().process(**inputs)
                else: raise AssertionError(kind)
                if isinstance(result, dict): outputs[name] = result['ui']; produced[name] = result['result']
                else: produced[name] = result
        except BridgeError as error:
            status = {'status_str': 'error', 'messages': [['execution_error', {'prompt_id': prompt, 'node_id': name,
                'node_type': kind, 'exception_message': json.dumps({'code': error.code})}]]}; outputs = {}
        history_graph = {} if self.failure == 'history' else copy.deepcopy(graph)
        self.history[prompt] = {'prompt': [0, prompt, history_graph], 'outputs': outputs, 'status': status}
        if self.failure == 'export-bytes' and '1' in graph and graph['1']['inputs'].get('action') == 'export_json':
            target = self.root/'output/lvw_manual'/('s2-a03.json')
            target.write_text('{}')
        return prompt
    def _json_request(self, url, **kwargs): return 200, copy.deepcopy(self.history)


class CumulativeTests(unittest.TestCase):
    def setUp(self):
        class Pin:
            def __init__(self, *args): pass
            def pin(self, prove): return prove()
            def close(self): pass
            def reap_pending(self, **kwargs): return 0
        patcher = patch('tools.v0_s2_cumulative_phase.PinnedLoopbackClient', Pin); patcher.start(); self.addCleanup(patcher.stop)
    def prepare(self, root, failure=None, authorize=None):
        for path in ('input', 'output', 'temp'): (root/path).mkdir()
        content = BytesIO(); Image.new('RGB', (8, 4), 'red').save(content, format='PNG')
        data = content.getvalue(); (root/'input/sample.png').write_bytes(data)
        driver = Native(root, failure)
        phase = CumulativePhase(driver, root, run_id='synthetic', binding={'candidate_sha': 'a'*40,
            'authorization_sha256': 'b'*64, 'ollama_pid': 10, 'ollama_start_ticks': 100},
            image={'reference': 'sample.png', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)},
            baseline_gpu_mib=100, authorize=authorize or (lambda *args: None))
        return phase, driver

    def test_twenty_four_public_submissions_close_five_cases_with_one_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            phase, driver = self.prepare(Path(directory)); original = driver.clients[base.COMFY_URL]
            online = phase.run('online')
            self.assertEqual('ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING', online['decision'], online)
            self.assertEqual(4, driver.submissions); self.assertEqual(1, driver.transport.calls)
            driver.stop_fixture(); result = phase.run('offline')
            self.assertEqual('CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', result['decision'], result)
            self.assertEqual({'fixed': 5, 'PASS': 5, 'FAIL': 0, 'NOT_RUN': 0}, result['test_counts'])
            self.assertEqual(24, driver.submissions); self.assertEqual(1, driver.transport.calls)
            self.assertIs(original, driver.clients[base.COMFY_URL]); self.assertFalse(result['stage_pass_claim'])
            self.assertEqual(list(CASES), list(result['cases']))
            self.assertIn('not actual Provider failures', result['cases']['V0-A05']['scope'])
            with self.assertRaises(EvidenceError): phase.run('offline')

    def test_wrong_history_export_and_extra_model_call_keep_full_denominator_no_go(self):
        for failure in ('history', 'export-bytes', 'extra-call', 'changed-prefix', 'forged-count'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                phase, driver = self.prepare(Path(directory), failure)
                result = phase.run('online'); self.assertEqual('NO_GO', result['decision'])
                self.assertEqual(5, len(result['cases'])); self.assertEqual(1, result['test_counts']['FAIL'])
                self.assertLessEqual(driver.submissions, 4)
                with self.assertRaises(EvidenceError): phase.run('offline')

    def test_unload_and_inventory_log_growth_preserves_one_visual_call_and_all_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            phase, driver = self.prepare(Path(directory), 'status-logs')
            online = phase.run('online')
            self.assertEqual('ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING', online['decision'], online)
            before = json.loads((phase.directory/'image-after.json').read_text())
            after = json.loads((phase.directory/'online-after.json').read_text())
            self.assertNotEqual(before, after)
            self.assertTrue(after['raw_log'].startswith(before['raw_log']))
            self.assertEqual(1, before['chat_calls']); self.assertEqual(1, after['chat_calls'])
            driver.stop_fixture(); result = phase.run('offline')
            self.assertEqual('CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', result['decision'], result)
            self.assertEqual(1, driver.transport.calls); self.assertEqual(24, driver.submissions)

    def test_offline_appends_allow_status_but_reject_chat_and_rewritten_prefix(self):
        for change in ('status', 'chat', 'rewrite'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                phase, driver = self.prepare(Path(directory))
                self.assertEqual('ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING', phase.run('online')['decision'])
                driver.stop_fixture(); snapshot = driver.chat_log_snapshot
                def appended():
                    value = snapshot()
                    if driver.submissions > 4:
                        raw = value['raw_log']+('[GIN] POST "/api/chat"\n' if change == 'chat' else '[GIN] GET "/api/ps"\n')
                        if change == 'rewrite': raw = 'replacement\n'+raw
                        value.update(raw_log=raw, source_log_bytes=len(raw.encode()),
                            source_log_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                            chat_calls=value['chat_calls']+(change == 'chat'))
                    return value
                driver.chat_log_snapshot = appended
                result = phase.run('offline')
                if change == 'status':
                    self.assertEqual('CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', result['decision'], result)
                else:
                    self.assertEqual('NO_GO', result['decision'])
                    self.assertEqual('FAIL', result['cases']['V0-A08']['status'])
                    self.assertEqual(5, result['test_counts']['fixed'])

    def test_offline_requires_actual_stop_and_original_peer_before_more_submissions(self):
        for failure in ('stop', 'peer'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                phase, driver = self.prepare(Path(directory)); self.assertEqual('ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING', phase.run('online')['decision'])
                if failure == 'peer': driver.stop_fixture(); driver.failure = 'root'
                result = phase.run('offline')
                self.assertEqual('NO_GO', result['decision']); self.assertEqual(4, driver.submissions)
                self.assertEqual('PASS', result['cases']['V0-A03']['status'])

    def test_source_denial_and_interrupt_never_become_pass(self):
        for failure in ('source', 'authorization', 'interrupt'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                phase, driver = self.prepare(Path(directory), 'interrupt' if failure == 'interrupt' else None)
                if failure == 'source': (phase.root/'input/sample.png').write_bytes(b'changed')
                if failure == 'authorization': phase.authorize = lambda *args: (_ for _ in ()).throw(EvidenceError('denied'))
                if failure == 'interrupt':
                    with self.assertRaises(KeyboardInterrupt): phase.run('online')
                    result = json.loads((phase.directory/'online-receipt.json').read_text()); self.assertEqual('NO_GO', result['decision'])
                elif failure == 'authorization':
                    with self.assertRaises(EvidenceError): phase.run('online')
                    self.assertFalse(phase.directory.exists())
                else: self.assertEqual('NO_GO', phase.run('online')['decision'])
