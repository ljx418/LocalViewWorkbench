"""Real protocol subprocess, synthetic handlers; zero browser/model/service starts."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

from tools.v0_s2_browser_supervisor import ACTIONS, LIMITS, MAX_LINE, Protocol, ProtocolError, Supervisor, strict_json

ROOT = Path(__file__).resolve().parents[2]


def config(root='/synthetic-owned-root'):
    return {'candidate_sha': 'a'*40, 'authorization_sha256': 'b'*64, 'protocol_nonce': 'c'*64,
        'run_root': root, 'expires_at': time.time()+3600}


def packet(p, action, payload=None, **extra):
    return json.dumps({'kind': 'lvw.s2.browser-parent-request/1', 'sequence': p.sequence+1,
        **{key: p.config[key] for key in ('candidate_sha', 'authorization_sha256', 'protocol_nonce')},
        'action': action, 'payload': payload or {}, **extra}).encode()


def exchange(p, action, payload=None, answer=None):
    request = p.reserve(packet(p, action, payload))
    return json.loads(p.complete(request['sequence'], answer or {}))


def bootstrap(p):
    exchange(p, 'preflight', {'run_root': p.config['run_root']}, {'owned_run_root': p.config['run_root']})
    exchange(p, 'browser_start', answer={'comfy_pid': 123, 'ephemeral_user_root_verified': True})
    exchange(p, 'browser_owner')
    exchange(p, 'upload')


class BrowserSupervisorTests(unittest.TestCase):
    def test_exact_identity_sequence_shape_duplicate_and_nonfinite_refused(self):
        for bad in ({'candidate_sha': 'd'*40}, {'protocol_nonce': 'e'*64}, {'authorization_sha256': 'f'*64},
                    {'sequence': True}, {'sequence': 2}, {'action': 'shell'}, {'extra': 1}, {'payload': []}):
            p = Protocol(config())
            with self.subTest(bad=bad), self.assertRaises(ProtocolError):
                value = json.loads(packet(p, 'preflight', {'run_root': p.config['run_root']}))
                value.update(bad); p.reserve(json.dumps(value).encode())
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff', b'['*10000):
            with self.subTest(raw=raw[:20]), self.assertRaises(ProtocolError): strict_json(raw)

    def test_exact_and_one_over_record_limit(self):
        raw = b'{"x":"'+b'x'*(MAX_LINE-8)+b'"}'
        self.assertEqual(MAX_LINE, len(raw)); self.assertIn('x', strict_json(raw))
        with self.assertRaisesRegex(ProtocolError, 'RECORD_LIMIT'): strict_json(raw+b' ')

    def test_preflight_and_owner_must_complete_before_dependent_permission(self):
        p = Protocol(config()); request = p.reserve(packet(p, 'preflight', {'run_root': p.config['run_root']}))
        with self.assertRaisesRegex(ProtocolError, 'PREFLIGHT_NOT_COMPLETE'): p.reserve(packet(p, 'browser_start'))
        with self.assertRaisesRegex(ProtocolError, 'ROOT_UNPROVEN'): p.complete(request['sequence'], {})
        p.complete(request['sequence'], {'owned_run_root': p.config['run_root']})
        request = p.reserve(packet(p, 'browser_start'))
        with self.assertRaisesRegex(ProtocolError, 'EPHEMERAL_USER_ROOT'): p.complete(request['sequence'], {})
        p.complete(request['sequence'], {'comfy_pid': 123, 'ephemeral_user_root_verified': True})
        with self.assertRaisesRegex(ProtocolError, 'OWNER_NOT_COMPLETE'): p.reserve(packet(p, 'upload'))

    def test_submit_consumed_before_callback_no_duplicate_or_old_prompt_join(self):
        p = Protocol(config()); bootstrap(p)
        exchange(p, 'case_begin', {'case_id': 'complete'})
        request = p.reserve(packet(p, 'public_submit', {'case_id': 'complete', 'body': {'prompt': {}}}))
        with self.assertRaisesRegex(ProtocolError, 'SUBMIT_NOT_ARMED'):
            p.reserve(packet(p, 'public_submit', {'case_id': 'complete', 'body': {'prompt': {}}}))
        p.complete(request['sequence'], {})
        exchange(p, 'case_queued', {'case_id': 'complete', 'prompt_id': 'abc'})
        with self.assertRaisesRegex(ProtocolError, 'CURRENT_PROMPT'):
            p.reserve(packet(p, 'case_finished', {'case_id': 'analysis_before_adoption', 'prompt_id': 'def'}))
        exchange(p, 'case_finished', {'case_id': 'analysis_before_adoption', 'prompt_id': 'abc'}, {'run_token': 'actual-handler-token'})
        with self.assertRaisesRegex(ProtocolError, 'DUPLICATE_OR_INVALID'):
            p.reserve(packet(p, 'case_finished', {'case_id': 'analysis_before_adoption', 'prompt_id': 'abc'}))

    def test_failed_permission_stays_consumed_exact_user_write_limit_and_expiry(self):
        p = Protocol(config()); bootstrap(p)
        for _ in range(LIMITS['user_write']): exchange(p, 'user_write')
        with self.assertRaisesRegex(ProtocolError, 'ACTION_LIMIT'): p.reserve(packet(p, 'user_write'))
        self.assertEqual(16, p.used['user_write'])
        p.config['expires_at'] = time.time()-1
        with self.assertRaisesRegex(ProtocolError, 'LEASE_EXPIRED'): p.reserve(packet(p, 'busy_manual'))

    def fixture(self, root, script, *, handlers=None, observer=None, authority=None):
        c = config(str(root)); (root/'temp/browser-phase').mkdir(parents=True)
        fixture = "const {parentBridge}=require('./tools/v0_s2_browser_acceptance.cjs');"+\
            'const c='+json.dumps(c)+';const bridge=parentBridge(c);'+\
            '(async()=>{try{'+script+'}finally{bridge.close();}})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});'
        process = subprocess.Popen(['node', '-e', fixture], cwd=ROOT, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.addCleanup(self.cleanup_process, process)
        def verify(handle, given):
            self.assertIs(handle, process); self.assertEqual(c, given)
            self.assertIsNone(process.poll())
        supervisor = Supervisor(c, handlers=handlers or self.handlers(c),
            authorize_owned_worker=authority or verify, resource_observer=observer or (lambda: None))
        return process, supervisor, root/'temp/browser-phase/parent'

    @staticmethod
    def cleanup_process(process):
        if process.poll() is None:
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed: stream.close()

    @staticmethod
    def handlers(c):
        answers = {'preflight': {'owned_run_root': c['run_root']},
            'browser_start': {'ephemeral_user_root_verified': True, 'comfy_pid': 123},
            'case_finished': {'run_token': 'synthetic-token'}, 'cancel_ready': {'ready': True, 'run_token': 'synthetic-token'},
            'offline_op': {'owned_ollama_stopped': True, 'comfy_pid': 123}}
        return {name: (lambda payload, observe, name=name: copy.deepcopy(answers.get(name, {}))) for name in ACTIONS}

    def test_authority_denial_prevents_log_creation_and_pipe_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def deny(*_): raise ProtocolError('synthetic authorization rejected')
            process, supervisor, logs = self.fixture(root, '', authority=deny)
            with self.assertRaisesRegex(ProtocolError, 'authorization rejected'): supervisor.run(process, logs)
            self.assertFalse(logs.exists())
            with self.assertRaisesRegex(ProtocolError, 'ONE_SHOT'): supervisor.run(process, logs)

    def test_real_node_bridge_zero_exit_without_joins_is_no_go_and_raw_logs_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process, supervisor, logs = self.fixture(root, "await bridge.request('preflight',{run_root:c.run_root});")
            result = supervisor.run(process, logs)
            self.assertEqual('NO_GO', result['decision']); self.assertEqual(0, result['exit_code'])
            self.assertIn('JOINS_MISSING', result['error_code'])
            self.assertEqual(1, result['requests']); self.assertEqual(1, result['replies'])
            self.assertEqual('preflight', json.loads((logs/'worker.stdout.jsonl').read_bytes())['action'])
            self.assertTrue(json.loads((logs/'parent.replies.jsonl').read_bytes())['approved'])
            self.assertFalse(result['stage_pass_claim']); self.assertEqual(3, len(result['artifacts']))

    def test_full_synthetic_handshake_can_only_complete_transport_not_product(self):
        script = """
          await bridge.request('preflight',{run_root:c.run_root});
          await bridge.request('browser_start',{}); await bridge.request('browser_owner',{});
          await bridge.request('upload',{});
          for(const name of ['complete','cancel']) {
            const prompt_id=name==='complete'?'abc':'def';
            await bridge.request('case_begin',{case_id:name});
            await bridge.request('public_submit',{case_id:name,body:{prompt:{}}});
            await bridge.request('case_queued',{case_id:name,prompt_id});
            if(name==='complete') {
              await bridge.request('busy_manual',{prompt_id});
              await bridge.request('case_finished',{case_id:'analysis_before_adoption',prompt_id});
            } else await bridge.request('cancel_ready',{prompt_id});
            await bridge.request('case_finished',{case_id:name,prompt_id});
          }
          await Promise.all([
            bridge.request('offline_op',{require_owned_ollama_stopped:true}),
            bridge.request('user_write',{pathname:'/settings',method:'POST',bytes:2})
          ]);
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); written = threading.Event(); handlers = self.handlers(config(str(root)))
            def offline(payload, observe):
                until = time.monotonic()+2
                while not written.wait(.01):
                    observe()
                    if time.monotonic() >= until: raise ProtocolError('concurrent user-write was blocked')
                return {'owned_ollama_stopped': True, 'comfy_pid': 123}
            def write(payload, observe): written.set(); return {}
            handlers['offline_op'] = offline; handlers['user_write'] = write
            process, supervisor, logs = self.fixture(root, script, handlers=handlers)
            result = supervisor.run(process, logs)
            self.assertEqual('TRANSPORT_COMPLETED_REQUIRES_PRODUCT_ORACLES', result['decision'], result)
            self.assertEqual(0, result['callbacks_pending']); self.assertTrue(result['worker_original_terminal'])
            self.assertEqual(result['requests'], result['replies']); self.assertFalse(result['stage_pass_claim'])

    def test_long_handler_does_not_block_resource_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); observed = []; entered = threading.Event()
            handlers = self.handlers(config(str(root)))
            def owner(payload, observe):
                entered.set()
                for _ in range(6): observe(); time.sleep(.02)
                return {}
            handlers['browser_owner'] = owner
            script = """
              await bridge.request('preflight',{run_root:c.run_root});
              await bridge.request('browser_start',{}); await bridge.request('browser_owner',{});
            """
            process, supervisor, logs = self.fixture(root, script, handlers=handlers, observer=lambda: observed.append(time.monotonic()))
            result = supervisor.run(process, logs)
            self.assertTrue(entered.is_set()); self.assertGreaterEqual(len(observed), 6)
            self.assertEqual('NO_GO', result['decision'])

    def test_resource_abort_closes_parent_pipe_and_cooperating_callback_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); entered = threading.Event(); finished = threading.Event()
            handlers = self.handlers(config(str(root)))
            def owner(payload, observe):
                entered.set()
                try:
                    while True: observe(); time.sleep(.01)
                finally: finished.set()
            handlers['browser_owner'] = owner
            def observe():
                if entered.is_set(): raise ProtocolError('synthetic resource threshold')
            script = "await bridge.request('preflight',{run_root:c.run_root});await bridge.request('browser_start',{});await bridge.request('browser_owner',{});"
            process, supervisor, logs = self.fixture(root, script, handlers=handlers, observer=observe)
            result = supervisor.run(process, logs)
            self.assertEqual('NO_GO', result['decision']); self.assertIn('resource threshold', result['error_code'])
            self.assertTrue(finished.wait(1)); self.assertEqual(0, result['callbacks_pending'])
            process.wait(timeout=3); self.assertNotEqual(0, process.returncode)


if __name__ == '__main__': unittest.main()
