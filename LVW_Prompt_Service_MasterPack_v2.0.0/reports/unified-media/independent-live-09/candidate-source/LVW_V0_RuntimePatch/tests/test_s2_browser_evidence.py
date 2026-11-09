"""Production public adapter/audit/project with synthetic model/GPU facts only."""
import copy
import hashlib
import json
import os
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import prompt_spec
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_api import LVWVideoPromptOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import NativeAudit
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_workbench import project
from LVW_V0_RuntimePatch.tests.test_s2_native_evidence import binding
from LVW_V0_RuntimePatch.tests.test_s2_cancel_evidence import prefix
from tools.v0_s2_browser_evidence import analysis_join, adopted_export_join, document, public_graph
from tools.v0_s2_checkpoint_oracles import EvidenceError


def facts(huge=False, release_duration=3.35):
    b = {**binding(), 'expires_at': 1200}; clock = [0]; events = []; factor = 9007199254740993 if huge else 1
    frames = [{'index': i, 'pts': p*factor, 'time_base_num': 1, 'time_base_den': factor,
        'time_seconds': p, 'sha256': str(i)*64} for i, p in enumerate((1, 3, 5, 7))]
    fixture = {'sha256': hashlib.sha256(b'x'*32).hexdigest(), 'bytes': 32, 'expected_sample_pts': [f['pts'] for f in frames],
        'oracle': {'time_base': '1/'+str(factor)}}
    proof = {'verified_compute_pids': [], 'snapshot': {'listener_pid': 10, 'listener_address': '127.0.0.1',
        'listener_port': 11434, 'processes': [{'pid': 10, 'parent_pid': 1, 'start_ticks': 100, 'name': 'ollama.exe'}]}}
    audit = NativeAudit(b, sink=events.append, check_root=lambda: copy.deepcopy(proof),
        clock=lambda: clock[0], wall=lambda: 1000+clock[0])
    token = '1'*32; audit.start(token)
    clock[0] = 1; audit.event(token, 'source_prepared', source_sha256=fixture['sha256'], frames=frames)
    clock[0] = 2; audit.event(token, 'gpu_admission_started')
    clock[0] = 3; audit.event(token, 'gpu_admission_completed', snapshot={'gpu_used_mib': 100})
    raws = []
    for index in range(4):
        base = index*(release_duration+10)
        clock[0] = base+4; audit.before_provider(token, {'model': 'gemma4:26b'}, 120)
        clock[0] = base+4.1; audit.verify_provider_owner(token)
        clock[0] = base+4.2; audit.event(token, 'provider_request_sent', call_index=index)
        raw = json.dumps({'model': 'gemma4:26b', 'done': True, 'message': {'content': 'synthetic red shape '+str(index)}})
        raws.append(raw)
        clock[0] = base+5; audit.event(token, 'provider_response', call_index=index, raw_sha256=hashlib.sha256(raw.encode()).hexdigest())
        clock[0] = base+5.1; audit.event(token, 'provider_connection_closed', call_index=index)
        clock[0] = base+5.2; audit.before_control(token)
        clock[0] = base+5.3; audit.event(token, 'unload_acknowledged', call_index=index, response={'done': True})
        clock[0] = base+5.4; audit.event(token, 'model_inventory_empty', call_index=index,
            observed_monotonic_seconds=clock[0], api_ps={'models': []})
        release = {'state': 'released', 'loaded_models': 0, 'baseline_gpu_mib': 100,
            'model_inventory_empty_monotonic': base+5.4, 'started_monotonic_seconds': base+5.15,
            'elapsed_seconds': release_duration, 'gpu_samples': [
                {'elapsed_seconds': release_duration-2+i, 'gpu_used_mib': 1124} for i in range(3)]}
        clock[0] = base+5.15+release_duration
        audit.event(token, 'physical_release', call_index=index, release=copy.deepcopy(release))
    clock[0] += 1
    audit.finish(token, status='succeeded', resource_state='released', error_code=None,
        cancel_epoch=0, cancel_accepted_at=None, release=copy.deepcopy(release))
    source = {'id': 'video_'+fixture['sha256'][:32], 'sha256': fixture['sha256'], 'kind': 'video',
        'display_name': 'Local video', 'bytes': fixture['bytes'], 'width': 1, 'height': 1,
        'duration_seconds': 8, 'source_root_id': None, 'relative_path': None, 'availability': 'available',
        'frames': [{'index': f['index'], 'target_seconds': f['time_seconds'], 'source_pts': f['pts'],
            'time_base_num': f['time_base_num'], 'time_base_den': f['time_base_den'], 'sha256': f['sha256'],
            'time_basis': 'decoded_pts'} for f in frames]}
    native = {'raw_response': json.dumps({'frame_raw_responses': raws}),
        'suggestion': json.dumps(prompt_spec(mode='realistic', observations=['red shape'], inferences=[],
            unknowns=[], creative_prompt='red shape', tags=['red'])), 'source_sha256': fixture['sha256'],
        'frames': frames, 'run_token': token, 'cancel_epoch': 0, 'resource_release': release,
        'source': source, 'model_tag': 'gemma4:26b'}
    class Owner:
        def run(self, *args, **kwargs): return copy.deepcopy(native)
        def completed_result(self, token): return copy.deepcopy(native)
    value = LVWVideoPromptOwner(owner=Owner()).analyze('synthetic.mp4')
    graph = {'1': {'class_type': 'LVWVideoPromptOwner', 'inputs': {'video_reference': 'synthetic.mp4',
        'model': 'gemma4:26b', 'mode': 'realistic', 'user_instruction': '', 'timeout_seconds': 120}}}
    history = {'abc': {'prompt': [0, 'abc', graph], 'status': {'status_str': 'success'}, 'outputs': {'1': value['ui']}}}
    samples = [{'monotonic_seconds': i, 'gpu_used_mib': 1124, 'available_ram_mib': 4096} for i in range(int(clock[0])+2)]
    adoption = project({'action': 'adopt', 'run_token': token}, Owner())
    return {'history': history, 'prompt_id': 'abc', 'graph': graph, 'reference': 'synthetic.mp4', 'fixture': fixture,
        'before': prefix(10), 'after': prefix(14), 'events': events, 'binding': b,
        'owner_pid': os.getpid(), 'resource_samples': samples}, adoption


def raw(value): return json.dumps(value, ensure_ascii=False).encode()


class BrowserEvidenceTests(unittest.TestCase):
    def test_public_native_four_frame_join_and_actual_project_export(self):
        value, adoption = facts(); joined = analysis_join(**value)
        self.assertEqual('PUBLIC_NATIVE_ANALYSIS_JOIN_NOT_STAGE_ACCEPTANCE', joined['kind'])
        self.assertFalse(joined['stage_pass_claim']); self.assertEqual(4, joined['provider_log_calls'])
        self.assertIn('independent_frame_decode', joined['remaining_obligations'])
        result = adopted_export_join(raw(adoption['result']), analysis=joined, adoption_response=raw(adoption),
            expected_draft=adoption['result']['draft'])
        self.assertFalse(result['stage_pass_claim'])
        self.assertEqual(joined['run_token'], result['run_token'])

    def test_edited_export_keeps_original_snapshot_and_large_pts_are_exact(self):
        value, adoption = facts(huge=True); joined = analysis_join(**value)
        edited = copy.deepcopy(adoption['result']); edited['draft_origin'] = 'edited'
        edited['draft']['natural_zh'] = '人工编辑；取消和离线之后仍保留'
        result = adopted_export_join(raw(edited), analysis=joined, adoption_response=raw(adoption),
            expected_draft=edited['draft'], edited=True)
        self.assertEqual('edited', result['draft_origin'])
        self.assertEqual(9007199254740993, document(raw(edited))['source']['frames'][0]['source_pts'])
        edited['source']['frames'][0]['source_pts'] = 9007199254740992
        with self.assertRaises(EvidenceError): adopted_export_join(raw(edited), analysis=joined,
            adoption_response=raw(adoption), expected_draft=edited['draft'], edited=True)

    def test_old_source_graph_cached_provider_and_native_raw_forgery_fail(self):
        for case in ('old-auth', 'wrong-owner', 'wrong-source', 'source-frame', 'pts', 'public-owner', 'history-graph',
                     'cached', 'log-replaced', 'provider-raw', 'missing-event', 'extra-event', 'unknown-event',
                     'missing-proof', 'wrong-root', 'false-success', 'expired-work', 'missing-persistence'):
            value, _ = facts(); events = value['events']
            def select(name): return next(e for e in events if e['event'] == name)
            if case == 'old-auth': events[0]['authorization_sha256'] = '0'*64
            if case == 'wrong-owner': value['owner_pid'] += 1
            if case == 'wrong-source': select('source_prepared')['source_sha256'] = '0'*64
            if case == 'source-frame': select('source_prepared')['frames'][0]['sha256'] = 'f'*64
            if case == 'pts': value['fixture']['expected_sample_pts'][0] = 2
            if case == 'public-owner': value['graph']['1']['class_type'] = 'InternalMock'
            if case == 'history-graph':
                value['history']['abc']['prompt'][2] = copy.deepcopy(value['graph'])
                value['history']['abc']['prompt'][2]['1']['inputs']['mode'] = 'documentary'
            if case == 'cached': value['after'] = prefix(10)
            if case == 'log-replaced': value['after'] = prefix(4)
            if case == 'provider-raw': select('provider_response')['raw_sha256'] = '0'*64
            if case == 'missing-event': events.remove(select('provider_owner_verified'))
            if case == 'extra-event': events.insert(5, copy.deepcopy(events[5]))
            if case == 'unknown-event': select('gpu_admission_started')['event'] = 'fake_green'
            if case == 'missing-proof': select('provider_attempt').pop('root_proof')
            if case == 'wrong-root': select('provider_owner_verified')['root_proof']['snapshot']['processes'][0]['start_ticks'] = 99
            if case == 'false-success': events[-1]['result_published'] = False
            if case == 'expired-work': select('provider_request_sent')['wall_seconds'] = value['binding']['expires_at']
            if case == 'missing-persistence': events.pop()
            with self.subTest(case=case), self.assertRaises(EvidenceError): analysis_join(**value)

    def test_release_exact_budget_and_one_over_and_sampler_disagreement(self):
        value, _ = facts(release_duration=30)
        value['binding']['expires_at'] = 1200
        analysis_join(**value)
        value, _ = facts(release_duration=30.0001); value['binding']['expires_at'] = 1200
        with self.assertRaises(EvidenceError): analysis_join(**value)
        for case in ('socket-only', 'gpu-over', 'two-samples', 'independent-over', 'cadence', 'RAM', 'empty-inventory'):
            value, _ = facts()
            def select(name): return next(e for e in value['events'] if e['event'] == name)
            if case == 'socket-only': value['events'].remove(select('physical_release'))
            if case == 'gpu-over': select('physical_release')['release']['gpu_samples'][-1]['gpu_used_mib'] = 1125
            if case == 'two-samples': select('physical_release')['release']['gpu_samples'].pop()
            if case == 'independent-over': value['resource_samples'][7]['gpu_used_mib'] = 1125
            if case == 'cadence': value['resource_samples'][7]['monotonic_seconds'] = 6.9
            if case == 'RAM': value['resource_samples'][0]['available_ram_mib'] = 2047
            if case == 'empty-inventory': select('model_inventory_empty')['api_ps']['models'] = [{}]
            with self.subTest(case=case), self.assertRaises(EvidenceError): analysis_join(**value)

    def test_modified_adoption_export_raw_source_draft_or_old_token_never_pass(self):
        value, adoption = facts(); joined = analysis_join(**value)
        for case in ('source', 'raw', 'suggestion', 'token', 'model', 'draft', 'origin', 'old-adoption'):
            exported = copy.deepcopy(adoption['result']); response = copy.deepcopy(adoption)
            if case == 'source': exported['source']['sha256'] = '0'*64
            if case == 'raw': exported['raw_response'] = 'old model result'
            if case == 'suggestion': exported['suggestion']['text_en'] = 'replaced'
            if case == 'token': exported['run_id'] = '2'*32
            if case == 'model': exported['model_tag'] = 'other'
            if case == 'draft': exported['draft']['natural_en'] = 'changed'
            if case == 'origin': exported['draft_origin'] = 'manual'
            if case == 'old-adoption': response['result']['run_id'] = '2'*32
            with self.subTest(case=case), self.assertRaises(EvidenceError):
                adopted_export_join(raw(exported), analysis=joined, adoption_response=raw(response),
                    expected_draft=adoption['result']['draft'])

    def test_duplicate_nonfinite_or_ambiguous_json_and_nonpublic_graph_are_refused(self):
        for text in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff'):
            with self.subTest(text=text), self.assertRaises(EvidenceError): document(text)
        value, _ = facts(); graph = copy.deepcopy(value['graph'])
        graph['1']['_meta'] = {'title': 'Visible Comfy node title'}; public_graph(graph, 'synthetic.mp4')
        graph['1']['inputs']['timeout_seconds'] = 121
        with self.assertRaises(EvidenceError): public_graph(graph, 'synthetic.mp4')

    def test_internally_consistent_wrong_adoption_cannot_validate_itself(self):
        value, adoption = facts(); joined = analysis_join(**value)
        for case in ('source-type', 'analysis-state', 'model-digest', 'machine-draft'):
            changed = copy.deepcopy(adoption)
            if case == 'source-type': changed['result']['source_type'] = 'manual'
            if case == 'analysis-state': changed['result']['analysis_status'] = 'failed'
            if case == 'model-digest': changed['result']['model_digest'] = '0'*64
            if case == 'machine-draft': changed['result']['draft']['natural_en'] = 'invented translation'
            with self.subTest(case=case), self.assertRaises(EvidenceError):
                adopted_export_join(raw(changed['result']), analysis=joined, adoption_response=raw(changed),
                    expected_draft=changed['result']['draft'])


if __name__ == '__main__': unittest.main()
