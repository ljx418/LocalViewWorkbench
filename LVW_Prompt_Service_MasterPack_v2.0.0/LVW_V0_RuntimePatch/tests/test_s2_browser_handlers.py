"""Actual callback/oracle path with synthetic service/model data and owned PID fixture."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.v0_s2_browser_handlers import BrowserHandlers, default_offline_runner
from tools.v0_s2_browser_owner import birth, executable
from tools.v0_s2_driver import S2SystemDriver, base
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.tests.test_s2_browser_evidence import facts
from LVW_V0_RuntimePatch.tests.test_s2_cancel_evidence import facts as cancel_facts, prefix


def raw(value): return (json.dumps(value, ensure_ascii=False)+'\n').encode()


class Native(S2SystemDriver):
    def __init__(self, value):
        super().__init__(SimpleNamespace(max_public_submissions=2, run_id='synthetic', powershell='never-run', native_audit=True), {})
        self.resource_observer = lambda: None
        self.value = value; self.calls = 10; self.status = {}; self.http = []; self.stopped = False
        self._resource_worker = SimpleNamespace(points=lambda: copy.deepcopy(self.value['resource_samples']))

    def owned_listener_birth(self, port):
        if port == 8191: return {'pid': os.getpid(), 'start_ticks': 123, 'name': 'python.exe'}
        if self.stopped: raise EvidenceError('synthetic Ollama already stopped')
        return {'pid': 10, 'start_ticks': 100, 'name': 'ollama.exe'}

    def _listener_pid_values(self, port): return [] if self.stopped else [10]
    def chat_log_snapshot(self): return prefix(self.calls)
    def prepare_fault_sampler(self, *args, **kwargs): self.transitioned = True

    def _json_request(self, url, **kwargs):
        self.http.append(url)
        if url.endswith('/lvw/v0/video/status'): return 200, copy.deepcopy(self.status)
        if '/history/' in url: return 200, copy.deepcopy(self.value['history'])
        if url.endswith('/api/ps'):
            return 200, {'models': [{'model': 'gemma4:26b', 'digest': self.value['binding']['model_digest'], 'size_vram': 1}]}
        raise AssertionError('unexpected synthetic endpoint: '+url)


class BrowserHandlerTests(unittest.TestCase):
    def prepare(self, root, authorize=None, offline=None):
        value, adoption = facts(); driver = Native(value)
        for name in ('input', 'temp/browser-phase/evidence', 'profiles'): (root/name).mkdir(parents=True)
        (root/'input/sample.mp4').write_bytes(b'x'*32)
        (root/'input/uploaded.mp4').write_bytes(b'x'*32)
        (root/'temp/lvw-native-profile.json').write_bytes(raw(value['binding']))
        (root/'temp/lvw-native-events.jsonl').touch()
        target = Path(sys.executable).resolve(strict=True)
        c = {'run_id': 'synthetic', 'run_root': str(root), 'candidate_sha': value['binding']['candidate_sha'],
            'authorization_sha256': value['binding']['authorization_sha256'], 'sample_path': str(root/'input/sample.mp4'),
            'sample_sha256': value['fixture']['sha256'], 'sample_bytes': 32, 'browser_executable': str(target),
            'browser_executable_sha256': executable(target)['sha256']}
        proof = {'owned_run_root': str(root), 'ephemeral_user_root_verified': True, 'comfy_pid': os.getpid(), 'scope': 'SYNTHETIC_TEST_ONLY'}
        handlers = BrowserHandlers(driver, config=c, binding=value['binding'], fixture=value['fixture'], worker_birth=birth(os.getpid()),
            temporary_root=root/'profiles', authorize=authorize or (lambda *args: None),
            verify_bindings=lambda *args: copy.deepcopy(proof), run_offline=offline or (lambda observe: {}))
        return handlers, driver, value, adoption

    def journal(self, handlers, events):
        (handlers.root/'temp/lvw-native-events.jsonl').write_bytes(b''.join(raw(e) for e in events))

    def start(self, handlers):
        callbacks = handlers.callbacks(); observe = lambda: None
        callbacks['preflight']({'run_root': str(handlers.root)}, observe)
        callbacks['browser_start']({}, observe)
        profile = handlers.temporary/'playwright_chromiumdev_profile-synthetic'; profile.mkdir()
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)', '--user-data-dir='+str(profile)],
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop, child)
        claim = birth(child.pid); info = profile.lstat()
        claim.update(executable_sha256=handlers.config['browser_executable_sha256'], profile_relative_name=profile.name,
            profile_inode=info.st_ino, profile_device=info.st_dev)
        callbacks['browser_owner'](claim, observe)
        callbacks['upload']({'bytes': 32, 'sha256': handlers.fixture['sha256']}, observe)
        (handlers.root/'temp/browser-phase/evidence/upload-response.json').write_bytes(raw({'video_reference': 'uploaded.mp4',
            'bytes': 32, 'sha256': handlers.fixture['sha256']}))
        return callbacks, observe

    @staticmethod
    def stop(process):
        if process.poll() is None: process.terminate()
        process.wait(timeout=3)

    def complete_analysis(self, handlers, driver, value, adoption, callbacks, observe):
        callbacks['case_begin']({'case_id': 'complete'}, observe)
        graph = copy.deepcopy(value['graph']); graph['1']['inputs']['video_reference'] = 'uploaded.mp4'
        body = {'prompt': graph, 'client_id': 'synthetic-new-session'}
        callbacks['public_submit']({'case_id': 'complete', 'body': body}, observe)
        self.assertEqual(1, driver.submissions)
        callbacks['case_queued']({'case_id': 'complete', 'body': body, 'prompt_id': 'abc'}, observe)
        value['history']['abc']['prompt'][2] = graph
        driver.status = {'run_token': value['events'][0]['run_token'], 'status': 'running', 'resource_state': 'busy'}
        sent_index = next(i for i, e in enumerate(value['events']) if e['event'] == 'provider_request_sent')
        self.journal(handlers, value['events'][:sent_index+1])
        callbacks['busy_manual']({'prompt_id': 'abc'}, observe)
        self.journal(handlers, value['events']); driver.calls = 14
        driver.status.update(status='succeeded', resource_state='released')
        digest = hashlib.sha256(value['history']['abc']['outputs']['1']['text'][0].encode()).hexdigest()
        response = callbacks['case_finished']({'case_id': 'analysis_before_adoption', 'prompt_id': 'abc', 'raw_sha256': digest}, observe)
        self.assertEqual(value['events'][0]['run_token'], response['run_token'])
        evidence = handlers.root/'temp/browser-phase/evidence'
        (evidence/'adoption-response.json').write_bytes(raw(adoption))
        (evidence/'adopted-export.json').write_bytes(raw(adoption['result']))
        callbacks['case_finished']({'case_id': 'complete', 'prompt_id': 'abc', 'raw_sha256': digest, 'export_file': 'adopted-export.json'}, observe)
        return graph

    def cancellation(self, handlers, driver, value, graph, callbacks, observe):
        callbacks['case_begin']({'case_id': 'cancel'}, observe)
        body = {'prompt': graph}
        callbacks['public_submit']({'case_id': 'cancel', 'body': body}, observe)
        callbacks['case_queued']({'case_id': 'cancel', 'body': body, 'prompt_id': 'def'}, observe)
        cancelled = cancel_facts(); events = cancelled['events']; token = '2'*32
        for event in events:
            event.update(run_token=token, run_number=2)
            event['monotonic_seconds'] += 100; event['wall_seconds'] += 100
            if 'observed_monotonic_seconds' in event: event['observed_monotonic_seconds'] += 100
            if event['event'] == 'source_prepared':
                event['source_sha256'] = handlers.fixture['sha256']; event['frames'] = copy.deepcopy(value['events'][1]['frames'])
            for key in ('release', 'resource_release'):
                if key in event:
                    event[key]['started_monotonic_seconds'] += 100
                    event[key]['model_inventory_empty_monotonic'] += 100
        prefix_events = copy.deepcopy(value['events'])
        end = next(i for i, e in enumerate(events) if e['event'] == 'provider_request_sent')
        self.journal(handlers, prefix_events+events[:end+1])
        driver.status = {'run_token': token, 'status': 'running', 'resource_state': 'busy'}
        response = callbacks['cancel_ready']({'prompt_id': 'def'}, observe)
        self.assertTrue(response['ready']); self.assertEqual(token, response['run_token'])
        self.journal(handlers, prefix_events+events); driver.calls = 15
        driver.status.update(status='cancelled', resource_state='released', error_code='JOB_CANCELLED', cancel_epoch=1)
        driver.value['history']['def'] = {'prompt': [0, 'def', graph], 'outputs': {}, 'status': {'status_str': 'error',
            'messages': [['execution_error', {'node_id': '1', 'node_type': 'LVWVideoPromptOwner', 'prompt_id': 'def',
                'exception_message': json.dumps({'code': 'JOB_CANCELLED'})}]]}}
        driver.value['resource_samples'] = [{'monotonic_seconds': i, 'gpu_used_mib': 1124, 'available_ram_mib': 4096} for i in range(111)]
        ack = copy.deepcopy(cancelled['ack']); ack['response']['run_token'] = token
        (handlers.root/'temp/browser-phase/evidence/cancel-ack.json').write_bytes(raw(ack))
        callbacks['case_finished']({'case_id': 'cancel', 'prompt_id': 'def', 'acknowledgement_file': 'cancel-ack.json'}, observe)

    def test_real_handlers_drive_public_native_adoption_cancel_and_ephemeral_write_oracles(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, value, adoption = self.prepare(Path(directory))
            callbacks, observe = self.start(handlers)
            graph = self.complete_analysis(handlers, driver, value, adoption, callbacks, observe)
            self.cancellation(handlers, driver, value, graph, callbacks, observe)
            self.assertEqual({'analysis_before_adoption', 'complete', 'cancel'}, handlers.completed)
            self.assertEqual(2, driver.submissions)
            self.assertTrue(handlers.sessions['cancel']['cancel_facts'])
            callbacks['user_write']({'pathname': '/userdata/workflows/test.json', 'method': 'POST', 'bytes': 2}, observe)
            self.assertTrue(handlers.artifacts)
            self.assertTrue(all('127.0.0.1' in path for path in driver.http))

    def test_denied_authority_or_wrong_profile_prevents_preflight_evidence_writes(self):
        for case in ('authority', 'profile'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                def deny(*_): raise EvidenceError('synthetic authority denial')
                handlers, driver, value, _ = self.prepare(Path(directory), authorize=deny if case == 'authority' else None)
                if case == 'profile': (handlers.root/'temp/lvw-native-profile.json').write_text('{}')
                with self.assertRaises(EvidenceError): handlers.callbacks()['preflight']({'run_root': str(handlers.root)}, lambda: None)
                self.assertFalse(handlers.directory.exists()); self.assertEqual(0, driver.submissions)

    def test_changed_upload_nonpublic_graph_and_duplicate_submission_cannot_send(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, value, _ = self.prepare(Path(directory)); callbacks, observe = self.start(handlers)
            callbacks['case_begin']({'case_id': 'complete'}, observe)
            graph = copy.deepcopy(value['graph']); graph['1']['inputs']['video_reference'] = 'uploaded.mp4'
            bad = copy.deepcopy(graph); bad['1']['class_type'] = 'HiddenInternalOwner'
            with self.assertRaises(EvidenceError): callbacks['public_submit']({'case_id': 'complete', 'body': {'prompt': bad}}, observe)
            self.assertEqual(0, driver.submissions)
            (handlers.root/'input/uploaded.mp4').write_bytes(b'y'*32)
            with self.assertRaises(EvidenceError): callbacks['public_submit']({'case_id': 'complete', 'body': {'prompt': graph}}, observe)
            self.assertEqual(0, driver.submissions)
            (handlers.root/'input/uploaded.mp4').write_bytes(b'x'*32)
            callbacks['public_submit']({'case_id': 'complete', 'body': {'prompt': graph}}, observe)
            with self.assertRaises(EvidenceError): callbacks['public_submit']({'case_id': 'complete', 'body': {'prompt': graph}}, observe)
            self.assertEqual(1, driver.submissions)

    def test_offline_boolean_or_missing_phase_receipts_never_prove_owned_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, value, adoption = self.prepare(Path(directory), offline=lambda observe: {})
            callbacks, observe = self.start(handlers)
            graph = self.complete_analysis(handlers, driver, value, adoption, callbacks, observe)
            self.cancellation(handlers, driver, value, graph, callbacks, observe)
            with self.assertRaisesRegex(EvidenceError, 'phase set missing'):
                callbacks['offline_op']({'require_owned_ollama_stopped': True}, observe)
            self.assertFalse(driver.stopped)

    def test_offline_requires_both_frozen_phases_and_actual_owned_stop_witness(self):
        for stopped in (False, True):
            with self.subTest(stopped=stopped), tempfile.TemporaryDirectory() as directory:
                handlers, driver, value, adoption = self.prepare(Path(directory))
                callbacks, observe = self.start(handlers)
                graph = self.complete_analysis(handlers, driver, value, adoption, callbacks, observe)
                self.cancellation(handlers, driver, value, graph, callbacks, observe)
                def receipt(decision, cases):
                    return {'run_id': 'synthetic', 'candidate_sha': handlers.binding['candidate_sha'],
                        'authorization_sha256': handlers.binding['authorization_sha256'], 'stage_pass_claim': False,
                        'decision': decision, 'cases': {c: {'status': 'PASS'} for c in cases},
                        'test_counts': {'fixed': len(cases), 'PASS': len(cases), 'FAIL': 0, 'NOT_RUN': 0}}
                receipts = {'cancellation': receipt('CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', ('preparation', 'provider')),
                    'fault': receipt('FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', ('provider-root-stop', 'manual-offline', 'quarantine-entry', 'adopt-denied'))}
                def offline(observe):
                    if stopped:
                        driver.stopped = True
                        driver.listener_terminal_states['11434'] = {'owned_listener_pid': 10, 'terminal_absent': True,
                            'lineage_reproven': True, 'root_stop': {'pid': 10, 'state': 'STOPPED', 'termination_requested': True, 'original_absent': True}}
                    return copy.deepcopy(receipts)
                handlers.run_offline = offline
                if stopped:
                    result = callbacks['offline_op']({'require_owned_ollama_stopped': True}, observe)
                    self.assertTrue(result['owned_ollama_stopped']); self.assertEqual(os.getpid(), result['comfy_pid'])
                else:
                    with self.assertRaisesRegex(EvidenceError, 'stop not proven'):
                        callbacks['offline_op']({'require_owned_ollama_stopped': True}, observe)
                with self.assertRaises(EvidenceError): callbacks['offline_op']({'require_owned_ollama_stopped': True}, observe)

    def test_default_offline_factory_does_not_start_fault_after_cancel_failure_or_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, value, _ = self.prepare(Path(directory))
            common = dict(run_id='synthetic', binding=handlers.binding, fixture=handlers.fixture,
                reference='sample.mp4', baseline_gpu_mib=100, nvidia_exe='never-run', nvidia_sha256='0'*64,
                authorize=lambda *args: None)
            execute = default_offline_runner(driver, handlers.root, **common)
            with patch('tools.v0_s2_browser_handlers.CancellationPhase') as cancel, patch('tools.v0_s2_browser_handlers.FaultPhase') as fault:
                cancel.return_value.run.return_value = {'decision': 'NO_GO'}
                result = execute(lambda: None)
                self.assertEqual('NOT_RUN', result['fault']['decision']); fault.assert_not_called()
                self.assertFalse(getattr(driver, 'transitioned', False))
                with self.assertRaises(EvidenceError): execute(lambda: None)

    def test_offline_internal_actions_receive_abort_and_restore_original_resource_observer(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, _, _ = self.prepare(Path(directory)); original = driver.resource_observer
            aborted = [False]; authorized = []
            def observe():
                if aborted[0]: raise EvidenceError('synthetic supervisor abort')
            execute = default_offline_runner(driver, handlers.root, run_id='synthetic', binding=handlers.binding,
                fixture=handlers.fixture, reference='sample.mp4', baseline_gpu_mib=100, nvidia_exe='never-run',
                nvidia_sha256='0'*64, authorize=lambda *args: authorized.append(args))
            with patch('tools.v0_s2_browser_handlers.CancellationPhase') as cancel, patch('tools.v0_s2_browser_handlers.FaultPhase') as fault:
                def inside():
                    self.assertIs(observe, driver.resource_observer)
                    aborted[0] = True
                    cancel.call_args.kwargs['authorize']('public_submit', 'provider')
                cancel.return_value.run.side_effect = inside
                with self.assertRaisesRegex(EvidenceError, 'supervisor abort'): execute(observe)
                fault.assert_not_called()
            self.assertEqual([], authorized); self.assertIs(original, driver.resource_observer)

    def test_double_encoded_traversal_and_unowned_user_root_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            handlers, driver, _, _ = self.prepare(Path(directory)); callbacks, observe = self.start(handlers)
            for path in ('/userdata/%252e%252e/private', '/userdata/%5cprivate', '/userdata/%00', '/foreign/config'):
                with self.subTest(path=path), self.assertRaises(EvidenceError):
                    callbacks['user_write']({'pathname': path, 'method': 'POST', 'bytes': 2}, observe)
            handlers.verify = lambda *args: {'owned_run_root': str(handlers.root), 'comfy_pid': os.getpid()}
            with self.assertRaises(EvidenceError): callbacks['user_write']({'pathname': '/settings', 'method': 'POST', 'bytes': 2}, observe)


if __name__ == '__main__': unittest.main()
