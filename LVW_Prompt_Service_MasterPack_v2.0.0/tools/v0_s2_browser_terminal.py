"""Recompute nine browser obligations from bound files and native parent facts.

No launch, network, authorization or Stage verdict. Authentic collection,
original process cleanup and the complete sampler remain parent obligations.
"""
import copy
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image

from tools.v0_s2_browser_evidence import analysis_join, adopted_export_join, document, digest, public_graph
from tools.v0_s2_cancel_phase import cancelled_history
from tools.v0_s2_cancel_evidence import cancellation_trace
from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools.v0_s2_public_phase import exact_timeline
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraft, result_txt

CASES = ('manual-initial', 'upload', 'native-analysis', 'busy-manual', 'explicit-adoption', 'exports-clipboard',
    'late-adoption-new-run-cancel', 'offline-manual', 'node-removal')
BUDGET = {'browser_starts': 1, 'uploads': 1, 'public_submissions': 2, 'previews': 8, 'adoptions': 2,
    'cancellations': 1, 'held_responses': 1, 'downloads': 6, 'user_writes': 16}
MANUAL = {'natural_zh': '浏览器人工稿：保留蓝色陶瓷杯', 'natural_en': 'Human draft: blue ceramic cup',
    'image_prompt': 'a blue ceramic cup', 'video_prompt': 'static camera, ceramic cup',
    'tags': ['人工', 'local'], 'negative': 'blur', 'edit_instruction': '保留构图'}


def load_artifacts(directory, result):
    """Verify the complete declared file inventory, rejecting redirects/extra files."""
    directory = Path(directory)
    if directory.resolve(strict=True) != directory: raise EvidenceError('browser evidence root redirect')
    rows = result.get('artifacts', [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 64: raise EvidenceError('browser artifact inventory bound')
    loaded = {}; total = 0
    for row in rows:
        name = row['file']
        if (not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9._-]{1,80}', name)
                or name in loaded or name == 'browser-result.json'): raise EvidenceError('browser duplicate/unsafe artifact')
        path = directory/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 24*1024*1024:
            raise EvidenceError('browser artifact type/size')
        raw = path.read_bytes(); total += len(raw)
        if (total > 128*1024*1024 or type(row['bytes']) is not int or row['bytes'] != len(raw)
                or row['sha256'] != digest(raw)): raise EvidenceError('browser artifact digest/denominator')
        loaded[name] = raw
    if {p.name for p in directory.iterdir()} != set(loaded)|{'browser-result.json'}:
        raise EvidenceError('browser unaccounted evidence file')
    return loaded


def terminal_join(*, config, result, artifacts, supervisor, analysis_facts, cancel_facts,
                  busy_window, offline_proofs, independent_cleanup):
    try:
        for record in (result, supervisor):
            if any(record.get(key) != config[key] for key in ('candidate_sha', 'authorization_sha256', 'run_id')):
                raise ValueError('browser cross candidate/child/run')
        if (result.get('decision') != 'BROWSER_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE' or result.get('stage_pass_claim') is not False
                or result.get('cases') != dict.fromkeys(CASES, 'PASS')
                or result.get('counts') != {'fixed': 9, 'PASS': 9, 'FAIL': 0, 'NOT_RUN': 0}
                or supervisor.get('decision') != 'TRANSPORT_COMPLETED_REQUIRES_PRODUCT_ORACLES'
                or supervisor.get('exit_code') != 0 or supervisor.get('callbacks_pending') != 0
                or supervisor.get('worker_original_terminal') is not True or supervisor['requests'] != supervisor['replies']):
            raise ValueError('browser/transport incomplete')
        inventory = result['artifacts']
        if (not 1 <= len(inventory) <= 64 or len(inventory) != len(artifacts)
                or len({r['file'] for r in inventory}) != len(inventory)
                or sum(len(r) for r in artifacts.values()) > 128*1024*1024):
            raise ValueError('browser evidence denominator')
        for row in inventory:
            raw = artifacts[row['file']]
            if len(raw) > 24*1024*1024 or type(row['bytes']) is not int or row['bytes'] != len(raw) or row['sha256'] != digest(raw):
                raise ValueError('browser changed evidence bytes')
        def obj(name): return document(artifacts[name])
        if obj('faults.json') != []: raise ValueError('browser route/page fault')
        for cleanup in (result['cleanup'], obj('browser-cleanup.json'), independent_cleanup):
            if any(cleanup.get(k) is not True for k in ('browser_original_absent', 'group_empty', 'profile_absent')):
                raise ValueError('browser cleanup unproven')
        if independent_cleanup.get('decision') != 'BROWSER_CLEANUP_PROVEN': raise ValueError('independent cleanup absent')
        used = result['budget_used']
        if (set(used) != set(BUDGET) or any(type(v) is not int or not 0 <= v <= BUDGET[k] for k, v in used.items())
                or any(used[k] != maximum for k, maximum in BUDGET.items() if k != 'user_writes')):
            raise ValueError('browser fixed budget denominator')
        counted = dict.fromkeys(('uploads', 'public_submissions', 'previews', 'adoptions', 'cancellations', 'user_writes'), 0)
        network = obj('network.json')
        if not isinstance(network, list) or len(network) > 8192: raise ValueError('browser network ledger bound')
        for request in network:
            kind, path, method = request['kind'], request['pathname'], request['method']
            memory = kind == 'read' and path == 'memory-image' and method == 'GET' and (
                (request['scheme'], request['origin']) in (('data:', 'null'), ('blob:', 'http://127.0.0.1:8191')))
            if not memory and (request['scheme'], request['origin']) != ('http:', 'http://127.0.0.1:8191'):
                raise ValueError('browser foreign origin/scheme')
            if kind == 'read':
                if method not in ('GET', 'HEAD'): raise ValueError('browser hidden mutation')
                continue
            if kind not in counted or (not re.fullmatch('[a-f0-9]{64}', request['body_sha256'] or '')
                    and not (kind == 'user_writes' and request['body_sha256'] is None)):
                raise ValueError('browser unrecognized mutation/body')
            expected = {'uploads': '/lvw/v0/video/upload', 'public_submissions': '/prompt',
                'previews': '/lvw/v0/video/workbench', 'adoptions': '/lvw/v0/video/workbench',
                'cancellations': '/lvw/v0/video/cancel'}
            if kind == 'user_writes':
                if method not in ('POST', 'PUT', 'DELETE') or not (path == '/settings' or path.startswith(('/settings/', '/userdata/'))):
                    raise ValueError('browser foreign user write')
            elif method != 'POST' or path != expected[kind]: raise ValueError('browser mutation path mismatch')
            counted[kind] += 1
        if any(counted[k] != used[k] for k in counted): raise ValueError('browser network/counter mismatch')
        analysis = analysis_join(**analysis_facts)
        if (analysis['candidate_sha'] != config['candidate_sha'] or analysis['authorization_sha256'] != config['authorization_sha256']
                or analysis['source']['sha256'] != config['sample_sha256']): raise ValueError('browser analysis identity mismatch')
        for name in ('manual-initial-export.json', 'busy-manual-export.json'):
            initial = obj(name)
            if initial['draft'] != MANUAL or initial['draft_origin'] != 'manual' or initial['source_type'] != 'manual':
                raise ValueError('browser initial/busy draft changed')
            if any(initial[k] is not None for k in ('run_id', 'source', 'raw_response', 'suggestion')):
                raise ValueError('browser manual draft acquired model provenance')
        window = busy_window['public_status']; prefix = busy_window['native_events']
        if (window.get('run_token') != analysis['run_token'] or window.get('status') not in ('preparing', 'running')
                or window.get('resource_state') != 'busy'
                or not prefix or analysis_facts['events'][:len(prefix)] != prefix or any(e['event'] == 'run_finished' for e in prefix)):
            raise ValueError('browser busy export not in current run')
        upload = obj('upload-response.json')
        if upload['sha256'] != config['sample_sha256'] or upload['bytes'] != config['sample_bytes']: raise ValueError('browser upload identity')
        for case, facts in (('complete', analysis_facts), ('cancel', cancel_facts)):
            queued = obj(case+'-public-queue.json')
            if queued['case_id'] != case or queued['prompt_id'] != facts['prompt_id'] or queued['body']['prompt'] != facts['graph']:
                raise ValueError('browser queue differs from native/public history')
            public_graph(facts['graph'], upload['video_reference'])
        visible = obj('raw-visible.json')
        if visible != {'text': analysis['raw_response'], 'sha256': analysis['raw_sha256']}: raise ValueError('browser visible raw changed')
        adoption = artifacts['adoption-response.json']; machine = obj('adoption-response.json')['result']['draft']
        export = adopted_export_join(artifacts['adopted-export.json'], analysis=analysis, adoption_response=adoption, expected_draft=machine)
        fields = {**machine, 'tags': ', '.join(machine['tags'])}
        if obj('adopted-fields.json') != fields: raise ValueError('browser adopted fields not displayed')
        expected_txt = result_txt(ManualDraft.from_inputs(**fields)).encode()
        if artifacts['adopted-export.txt'] != expected_txt or artifacts['clipboard.txt'] != expected_txt:
            raise ValueError('browser actual TXT/clipboard differs from draft')
        denial = obj('clipboard-denial.json')
        if denial['fields_after'] != fields or 'LVW controlled clipboard denial' not in denial['text']:
            raise ValueError('browser clipboard failure overwrote draft/unobserved')
        held, forwarded = obj('held-adoption-original.json'), obj('held-adoption-forwarded.json')
        held_bytes = held['raw_utf8'].encode()
        if (held['status'] != 200 or held['sha256'] != digest(held_bytes)
                or forwarded != {'sha256': digest(held_bytes), 'bytes': len(held_bytes)}): raise ValueError('held response replaced/not actual bytes')
        adopted_export_join(json.dumps(document(held_bytes)['result'], ensure_ascii=False).encode(), analysis=analysis,
            adoption_response=held_bytes, expected_draft=machine)
        if (cancel_facts['binding'] != analysis_facts['binding'] or cancel_facts['owner_pid'] != analysis_facts['owner_pid']
                or cancel_facts['token'] == analysis['run_token'] or cancel_facts['ack'] != obj('cancel-ack.json')):
            raise ValueError('browser cancel/current run mismatch')
        cancelled = cancellation_trace(**{k: cancel_facts[k] for k in ('events', 'binding', 'token', 'owner_pid', 'kind', 'ack', 'before', 'after', 'resource_samples')})
        cancelled_history(cancel_facts['history'], cancel_facts['prompt_id'], cancel_facts['graph'])
        prepared = [e for e in cancel_facts['events'] if e['event'] == 'source_prepared']
        if len(prepared) != 1: raise ValueError('browser cancelled source denominator')
        exact_timeline(prepared[0], analysis_facts['fixture'])
        edited = copy.deepcopy(machine)
        edited['natural_zh'] = '人工修改：等待采纳时保留，不被新运行或取消覆盖；请求期间继续编辑'
        for name in ('after-cancel-export.json', 'offline-export.json'):
            adopted_export_join(artifacts[name], analysis=analysis, adoption_response=adoption, expected_draft=edited, edited=True)
        expected_phases = {'cancellation': ('CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', {'preparation', 'provider'}),
            'fault': ('FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', {'provider-root-stop', 'manual-offline', 'quarantine-entry', 'adopt-denied'})}
        if set(offline_proofs.get('receipts', {})) != set(expected_phases): raise ValueError('browser offline phase set missing')
        for name, (decision, cases) in expected_phases.items():
            receipt = offline_proofs['receipts'][name]
            if (receipt.get('decision') != decision or receipt.get('stage_pass_claim') is not False
                    or any(receipt.get(k) != config[k] for k in ('candidate_sha', 'authorization_sha256', 'run_id'))
                    or set(receipt.get('cases', {})) != cases or any(r.get('status') != 'PASS' for r in receipt['cases'].values())
                    or receipt.get('test_counts') != {'fixed': len(cases), 'PASS': len(cases), 'FAIL': 0, 'NOT_RUN': 0}):
                raise ValueError('browser offline incomplete/misbound phase')
        stop = offline_proofs['owned_stop']; root = stop['root_stop']
        if (stop.get('terminal_absent') is not True or stop.get('lineage_reproven') is not True
                or stop.get('owned_listener_pid') != analysis_facts['binding']['ollama_pid']
                or root.get('pid') != analysis_facts['binding']['ollama_pid'] or root.get('state') != 'STOPPED'
                or root.get('termination_requested') is not True or root.get('original_absent') is not True):
            raise ValueError('browser offline parent stop proof missing')
        removal = obj('node-removal-observation.json')
        if removal != {'node_id': 1, 'node_before': True, 'node_after': False, 'fields_before': 7, 'fields_after': 0}:
            raise ValueError('browser node removal not observed')
        with Image.open(BytesIO(artifacts['native-workbench.png'])) as picture:
            if picture.format != 'PNG' or picture.width*picture.height > 32_000_000: raise ValueError('browser screenshot invalid')
            picture.verify()
        return {'kind': 'NINE_BROWSER_OBLIGATIONS_JOINED_NOT_STAGE_ACCEPTANCE', 'stage_pass_claim': False,
            'candidate_sha': config['candidate_sha'], 'authorization_sha256': config['authorization_sha256'], 'run_id': config['run_id'],
            'cases': dict.fromkeys(CASES, 'PASS'), 'counts': {'fixed': 9, 'PASS': 9, 'FAIL': 0, 'NOT_RUN': 0},
            'analysis_token': analysis['run_token'], 'cancel_token': cancel_facts['token'], 'export': export,
            'cancel_feedback_seconds': cancelled['cancel_feedback_seconds'],
            'remaining_obligations': ['full_native_source_and_sampler_checks', 'independent_frame_decode', 'independent_review', 'human_experience_signoff']}
    except (KeyError, IndexError, TypeError, ValueError, OSError, SyntaxError) as error:
        raise EvidenceError('browser terminal join failed: '+str(error)) from error
