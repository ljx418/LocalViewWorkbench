"""Nine-obligation oracle on explicitly synthetic browser/service/model evidence."""
import copy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from LVW_V0_RuntimePatch.tests import test_s2_browser_handlers as wiring
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_workbench import project
from tools.v0_s2_browser_terminal import terminal_join, load_artifacts, CASES, BUDGET, MANUAL
from tools.v0_s2_browser_evidence import digest
from tools.v0_s2_browser_owner import cleanup_witness
from tools.v0_s2_checkpoint_oracles import EvidenceError


def raw(value): return json.dumps(value, ensure_ascii=False).encode()


def fixture(root):
    helper = wiring.BrowserHandlerTests()
    handlers, driver, value, adoption = helper.prepare(root)
    try:
        callbacks, observe = helper.start(handlers)
        graph = helper.complete_analysis(handlers, driver, value, adoption, callbacks, observe)
        helper.cancellation(handlers, driver, value, graph, callbacks, observe)
        def receipt(decision, cases):
            return {'run_id': 'synthetic', 'candidate_sha': handlers.binding['candidate_sha'],
                'authorization_sha256': handlers.binding['authorization_sha256'], 'decision': decision,
                'stage_pass_claim': False, 'cases': {c: {'status': 'PASS'} for c in cases},
                'test_counts': {'fixed': len(cases), 'PASS': len(cases), 'FAIL': 0, 'NOT_RUN': 0}}
        def offline(observe):
            driver.stopped = True
            driver.listener_terminal_states['11434'] = {'owned_listener_pid': 10, 'terminal_absent': True, 'lineage_reproven': True,
                'root_stop': {'pid': 10, 'state': 'STOPPED', 'termination_requested': True, 'original_absent': True}}
            return {'cancellation': receipt('CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', ('preparation', 'provider')),
                'fault': receipt('FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', ('provider-root-stop', 'manual-offline', 'quarantine-entry', 'adopt-denied'))}
        handlers.run_offline = offline
        callbacks['offline_op']({'require_owned_ollama_stopped': True}, observe)
    finally: helper.doCleanups()
    (handlers.temporary/handlers.owner['profile_relative_name']).rmdir()
    cleanup = cleanup_witness(handlers.owner, temporary_root=handlers.temporary)
    session = handlers.sessions['complete']; cancelled = handlers.sessions['cancel']; machine = adoption['result']['draft']
    fields = {**machine, 'tags': ', '.join(machine['tags'])}
    manual = project({'action': 'preview', 'fields': {**MANUAL, 'tags': ', '.join(MANUAL['tags'])}})['result']
    edited = copy.deepcopy(adoption['result']); edited['draft_origin'] = 'edited'
    edited['draft']['natural_zh'] = '人工修改：等待采纳时保留，不被新运行或取消覆盖；请求期间继续编辑'
    held = raw(adoption)
    paths = {'uploads': '/lvw/v0/video/upload', 'public_submissions': '/prompt', 'previews': '/lvw/v0/video/workbench',
        'adoptions': '/lvw/v0/video/workbench', 'cancellations': '/lvw/v0/video/cancel'}
    network = [{'method': 'POST', 'origin': 'http://127.0.0.1:8191', 'scheme': 'http:', 'pathname': path,
        'kind': kind, 'body_sha256': 'a'*64} for kind, path in paths.items() for _ in range(BUDGET[kind])]
    png = BytesIO(); Image.new('RGB', (1, 1)).save(png, format='PNG')
    files = {'manual-initial-export.json': raw(manual), 'busy-manual-export.json': raw(manual),
        'upload-response.json': (handlers.root/'temp/browser-phase/evidence/upload-response.json').read_bytes(),
        'complete-public-queue.json': raw({'case_id': 'complete', 'prompt_id': 'abc', 'body': {'prompt': graph}}),
        'cancel-public-queue.json': raw({'case_id': 'cancel', 'prompt_id': 'def', 'body': {'prompt': graph}}),
        'raw-visible.json': raw({'text': session['analysis']['raw_response'], 'sha256': session['analysis']['raw_sha256']}),
        'adoption-response.json': raw(adoption), 'adopted-export.json': raw(adoption['result']),
        'adopted-fields.json': raw(fields), 'adopted-export.txt': project({'action': 'preview', 'fields': fields})['txt'].encode(),
        'clipboard.txt': project({'action': 'preview', 'fields': fields})['txt'].encode(),
        'clipboard-denial.json': raw({'text': 'LVW controlled clipboard denial', 'fields_after': fields}),
        'held-adoption-original.json': raw({'status': 200, 'raw_utf8': held.decode(), 'sha256': digest(held)}),
        'held-adoption-forwarded.json': raw({'sha256': digest(held), 'bytes': len(held)}),
        'cancel-ack.json': raw(cancelled['cancel_facts']['ack']), 'after-cancel-export.json': raw(edited),
        'offline-export.json': raw(edited), 'node-removal-observation.json': raw({'node_id': 1, 'node_before': True,
            'node_after': False, 'fields_before': 7, 'fields_after': 0}), 'faults.json': b'[]', 'network.json': raw(network),
        'browser-cleanup.json': raw({k: cleanup[k] for k in ('browser_original_absent', 'group_empty', 'profile_absent')}),
        'native-workbench.png': png.getvalue()}
    config = handlers.config
    result = {**{k: config[k] for k in ('candidate_sha', 'authorization_sha256', 'run_id')},
        'decision': 'BROWSER_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', 'stage_pass_claim': False,
        'cases': dict.fromkeys(CASES, 'PASS'), 'counts': {'fixed': 9, 'PASS': 9, 'FAIL': 0, 'NOT_RUN': 0},
        'cleanup': json.loads(files['browser-cleanup.json']), 'budget_used': {**BUDGET, 'user_writes': 0}}
    supervisor = {**{k: config[k] for k in ('candidate_sha', 'authorization_sha256', 'run_id')},
        'decision': 'TRANSPORT_COMPLETED_REQUIRES_PRODUCT_ORACLES', 'exit_code': 0,
        'callbacks_pending': 0, 'worker_original_terminal': True, 'requests': 20, 'replies': 20}
    full = session['analysis_facts']['events']; end = next(i for i, e in enumerate(full) if e['event'] == 'provider_request_sent')
    data = {'config': config, 'result': result, 'artifacts': files, 'supervisor': supervisor,
        'analysis_facts': session['analysis_facts'], 'cancel_facts': cancelled['cancel_facts'],
        'busy_window': {'public_status': {'run_token': session['analysis']['run_token'], 'status': 'running', 'resource_state': 'busy'},
            'native_events': full[:end+1]}, 'offline_proofs': handlers.offline, 'independent_cleanup': cleanup}
    resign(data)
    return data


def resign(data):
    data['result']['artifacts'] = [{'file': name, 'bytes': len(value), 'sha256': digest(value)} for name, value in data['artifacts'].items()]


class BrowserTerminalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.data = fixture(Path(temp.name))

    def test_nine_rows_require_raw_and_native_facts_and_never_sign_stage(self):
        result = terminal_join(**self.data)
        self.assertEqual(9, result['counts']['PASS']); self.assertFalse(result['stage_pass_claim'])
        self.assertIn('human_experience_signoff', result['remaining_obligations'])

    def test_pass_labels_and_exit_zero_cannot_hide_changed_or_missing_facts(self):
        for case in ('old-candidate', 'old-supervisor', 'counter', 'raw', 'clipboard', 'held', 'adopt', 'source',
                     'removal', 'fault', 'origin', 'offline', 'cleanup', 'pending-callback', 'provider', 'busy'):
            d = copy.deepcopy(self.data)
            if case == 'old-candidate': d['result']['candidate_sha'] = '0'*40
            if case == 'old-supervisor': d['supervisor']['authorization_sha256'] = '0'*64
            if case == 'counter': d['result']['budget_used']['public_submissions'] = 1
            if case == 'raw': d['artifacts']['raw-visible.json'] = b'{}'
            if case == 'clipboard': d['artifacts']['clipboard.txt'] += b'changed'
            if case == 'held': d['artifacts']['held-adoption-forwarded.json'] = b'{}'
            if case == 'adopt': d['artifacts']['adopted-export.json'] = b'{}'
            if case == 'source':
                value = json.loads(d['artifacts']['offline-export.json']); value['run_id'] = '2'*32
                d['artifacts']['offline-export.json'] = raw(value)
            if case == 'removal': d['artifacts']['node-removal-observation.json'] = b'{}'
            if case == 'fault': d['artifacts']['faults.json'] = b'[{"code":"PAGE_ERROR"}]'
            if case == 'origin':
                rows = json.loads(d['artifacts']['network.json']); rows[0]['origin'] = 'https://example.org'
                d['artifacts']['network.json'] = raw(rows)
            if case == 'offline': d['offline_proofs']['receipts']['fault']['cases']['adopt-denied']['status'] = 'NOT_RUN'
            if case == 'cleanup': d['independent_cleanup']['profile_absent'] = False
            if case == 'pending-callback': d['supervisor']['callbacks_pending'] = 1
            if case == 'provider': d['analysis_facts']['after']['chat_calls'] -= 1
            if case == 'busy': d['busy_window']['public_status']['run_token'] = 'old'
            resign(d)  # Semantic errors must still fail with consistent hashes.
            with self.subTest(case=case), self.assertRaises(EvidenceError): terminal_join(**d)

    def test_file_inventory_extra_file_digest_change_and_symlink_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name, value in self.data['artifacts'].items(): (directory/name).write_bytes(value)
            (directory/'browser-result.json').write_bytes(raw(self.data['result']))
            self.assertEqual(self.data['artifacts'], load_artifacts(directory, self.data['result']))
            (directory/'unaccounted').touch()
            with self.assertRaises(EvidenceError): load_artifacts(directory, self.data['result'])
            (directory/'unaccounted').unlink()
            path = directory/'clipboard.txt'; path.write_bytes(b'changed')
            with self.assertRaises(EvidenceError): load_artifacts(directory, self.data['result'])
            path.unlink(); path.symlink_to(directory/'adopted-export.txt')
            with self.assertRaises(EvidenceError): load_artifacts(directory, self.data['result'])


if __name__ == '__main__': unittest.main()
