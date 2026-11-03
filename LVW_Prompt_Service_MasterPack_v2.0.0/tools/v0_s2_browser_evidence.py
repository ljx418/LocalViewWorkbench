"""Join public production history, native journal and actual adopted exports.

Pure oracles: no browser/provider calls or authorizations. The parent must load
hash-bound artifacts from the same fresh run. These checks cannot establish
artifact authenticity, independent decoding or final Stage acceptance alone.
"""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
import re

from jsonschema import Draft202012Validator, ValidationError

from tools.v0_s2_checkpoint_oracles import EvidenceError, public_video_oracle, number
from tools.v0_s2_cancel_evidence import count
from tools.v0_s2_measurements import spec_validator
from tools.v0_s2_public_phase import exact_timeline
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import validate_lineage
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import validate_binding


def digest(raw): return hashlib.sha256(raw).hexdigest()


def document(raw):
    """Keep arbitrary-size PTS integers exact; reject ambiguous JSON evidence."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate evidence key')
            result[key] = value
        return result
    def invalid(_): raise ValueError('nonfinite evidence')
    def floating(text):
        value = float(text)
        if not math.isfinite(value): raise ValueError('nonfinite evidence')
        return value
    try:
        if not isinstance(raw, bytes) or len(raw) > 24*1024*1024: raise ValueError('bounded evidence bytes required')
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=floating)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise EvidenceError('invalid evidence JSON') from error


def public_graph(graph, reference):
    try:
        node = graph['1']
        if (set(graph) != {'1'} or set(node)-{'class_type', 'inputs', '_meta'}
                or node['class_type'] != 'LVWVideoPromptOwner' or node['inputs'] != {
                    'video_reference': reference, 'model': 'gemma4:26b', 'mode': 'realistic',
                    'user_instruction': '', 'timeout_seconds': 120}): raise ValueError()
        if '_meta' in node and (not isinstance(node['_meta'], dict) or set(node['_meta']) != {'title'}
                or not isinstance(node['_meta']['title'], str) or len(node['_meta']['title']) > 256): raise ValueError()
        if not isinstance(reference, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}', reference) or '..' in reference:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceError('browser graph bypasses frozen public owner/inputs') from error


def release_join(events, index, *, baseline, resource_samples):
    """Independent empty inventory plus 3x1Hz GPU evidence for one call."""
    def one(name):
        values = [e for e in events if e['event'] == name and e.get('call_index') == index]
        if len(values) != 1: raise ValueError('release event denominator')
        return values[0]
    closed, unloaded, empty, physical = map(one, ('provider_connection_closed', 'unload_acknowledged',
        'model_inventory_empty', 'physical_release'))
    release = physical['release']
    started = number(release['started_monotonic_seconds'], 'release start')
    finished = number(physical['monotonic_seconds'], 'physical release')
    observed = number(empty['observed_monotonic_seconds'], 'empty inventory')
    if (release['state'] != 'released' or release['loaded_models'] != 0 or release['baseline_gpu_mib'] != baseline
            or release['model_inventory_empty_monotonic'] != observed or empty['api_ps'].get('models') != []
            or unloaded['response'].get('done') is not True
            or not closed['monotonic_seconds'] <= started <= unloaded['monotonic_seconds'] <= observed
            <= empty['monotonic_seconds'] <= finished
            or abs(started+number(release['elapsed_seconds'], 'release duration')-finished) > 1e-6
            or number(release['elapsed_seconds'], 'release duration') > 30): raise ValueError('physical release origin/budget')
    controls = [e for e in events if e['event'] == 'release_owner_verified'
        and closed['monotonic_seconds'] <= e['monotonic_seconds'] <= unloaded['monotonic_seconds']]
    if not controls: raise ValueError('unload owner not verified')
    points = release['gpu_samples']
    if not isinstance(points, list) or not 3 <= len(points) <= 31: raise ValueError('release samples missing')
    previous = None
    for point in points:
        elapsed = number(point['elapsed_seconds'], 'GPU sample time')
        if (type(point['gpu_used_mib']) is not int or point['gpu_used_mib'] < 0 or elapsed > finished-started+1e-6
                or (previous is not None and elapsed-previous < 1-1e-6)): raise ValueError('GPU sample cadence')
        previous = elapsed
    if abs(started+previous-finished) > 1e-6 or any(p['gpu_used_mib'] > baseline+1024 for p in points[-3:]):
        raise ValueError('GPU stability not proven')
    stable = [p for p in resource_samples if started+points[-3]['elapsed_seconds'] <= p['monotonic_seconds'] <= finished]
    if len(stable) < 2 or any(p['gpu_used_mib'] > baseline+1024 for p in stable):
        raise ValueError('independent sampler disagrees with release')
    return release


def analysis_join(*, history, prompt_id, graph, reference, fixture, before, after,
                  events, binding, owner_pid, resource_samples):
    try:
        validate_binding(binding, binding['issued_at'])
        public_graph(graph, reference)
        before_calls, after_calls = count(before), count(after)
        if not after['raw_log'].startswith(before['raw_log']): raise ValueError('provider log replaced')
        result = public_video_oracle(history, prompt_id, source_sha256=fixture['sha256'], expected_model='gemma4:26b',
            chat_calls_before=before_calls, chat_calls_after=after_calls)
        record = history[prompt_id]
        if record['prompt'][2] != graph: raise ValueError('public submitted graph mismatch')
        raw, suggestion, metadata = record['outputs']['1']['text']
        meta, spec = json.loads(metadata), json.loads(suggestion)
        spec_validator().validate(spec)
        timeline = exact_timeline(meta, fixture)
        token, frames = result['run_token'], result['frames']
        expected_frames = [{'index': f['index'], 'target_seconds': f['time_seconds'], 'source_pts': f['pts'],
            'time_base_num': f['time_base_num'], 'time_base_den': f['time_base_den'], 'sha256': f['sha256'],
            'time_basis': 'decoded_pts'} for f in frames]
        if (meta['source']['sha256'] != fixture['sha256'] or meta['source']['bytes'] != fixture['bytes']
                or meta['source']['kind'] != 'video' or meta['source']['frames'] != expected_frames):
            raise ValueError('public source differs from sampled metadata')
        if type(owner_pid) is not int or owner_pid <= 0 or not isinstance(events, list) or not 3 <= len(events) <= 1024:
            raise ValueError('native run missing')
        allowed = {'run_started', 'source_prepared', 'gpu_admission_started', 'gpu_admission_completed',
            'provider_attempt', 'provider_owner_verified', 'provider_request_sent', 'provider_response',
            'provider_connection_closed', 'release_owner_verified', 'unload_acknowledged', 'model_inventory_empty',
            'physical_release', 'run_finished'}
        previous = None
        for event in events:
            stamp = number(event['monotonic_seconds'], 'native time'); number(event['wall_seconds'], 'native wall')
            if (event['event'] not in allowed or event['candidate_sha'] != binding['candidate_sha']
                    or event['authorization_sha256'] != binding['authorization_sha256'] or event['run_token'] != token
                    or type(event['owner_pid']) is not int or event['owner_pid'] != owner_pid
                    or type(event['run_number']) is not int or not 1 <= event['run_number'] <= binding['max_runs']
                    or event['run_number'] != events[0]['run_number'] or (previous is not None and stamp < previous)):
                raise ValueError('native identity/order mismatch')
            if event['event'] in ('run_started', 'provider_attempt', 'provider_owner_verified', 'provider_request_sent'):
                if not binding['issued_at'] <= event['wall_seconds'] < binding['expires_at']: raise ValueError('expired new work')
            if event['event'] in ('provider_attempt', 'provider_owner_verified', 'release_owner_verified'):
                proof = event['root_proof']
                if proof['verified_compute_pids'] != []: raise ValueError('wrong root proof scope')
                validate_lineage(proof['snapshot'], binding, [], owner_pid)
            previous = stamp
        names = [e['event'] for e in events]
        for name in ('run_started', 'run_finished', 'source_prepared', 'gpu_admission_started', 'gpu_admission_completed'):
            if names.count(name) != 1: raise ValueError('native lifecycle denominator')
        if names[0] != 'run_started' or names[-1] != 'run_finished': raise ValueError('native terminal missing')
        source = next(e for e in events if e['event'] == 'source_prepared')
        admission = next(e for e in events if e['event'] == 'gpu_admission_completed')
        admission_start = next(e for e in events if e['event'] == 'gpu_admission_started')
        if not source['monotonic_seconds'] <= admission_start['monotonic_seconds'] <= admission['monotonic_seconds']:
            raise ValueError('native preparation/admission order')
        if source['source_sha256'] != fixture['sha256'] or source['frames'] != frames: raise ValueError('native frame source mismatch')
        baseline = admission['snapshot']['gpu_used_mib']
        if type(baseline) is not int or not 0 <= baseline <= 4096: raise ValueError('cold baseline invalid')
        previous = None
        for point in resource_samples:
            stamp = number(point['monotonic_seconds'], 'independent sample')
            if (previous is not None and not 1-1e-6 <= stamp-previous <= 1.5
                    or type(point['gpu_used_mib']) is not int or not 0 <= point['gpu_used_mib'] < 23552
                    or number(point['available_ram_mib'], 'RAM') < 2048): raise ValueError('independent trace invalid')
            previous = stamp
        raws = json.loads(raw)['frame_raw_responses']
        last_release = None
        prior_release_time = admission['monotonic_seconds']
        for index in range(4):
            selected = {}
            for name in ('provider_attempt', 'provider_owner_verified', 'provider_request_sent', 'provider_response',
                         'provider_connection_closed', 'physical_release'):
                rows = [e for e in events if e['event'] == name and e.get('call_index') == index]
                if len(rows) != 1: raise ValueError('native per-frame denominator')
                selected[name] = rows[0]
            times = [prior_release_time]+[selected[name]['monotonic_seconds'] for name in selected]
            if times != sorted(times): raise ValueError('native provider/release order')
            if not re.fullmatch('[a-f0-9]{64}', selected['provider_attempt']['payload_sha256']): raise ValueError('request hash missing')
            if selected['provider_response']['raw_sha256'] != digest(raws[index].encode()): raise ValueError('provider response differs from public raw')
            last_release = release_join(events, index, baseline=baseline, resource_samples=resource_samples)
            prior_release_time = selected['physical_release']['monotonic_seconds']
        for name in ('provider_attempt', 'provider_owner_verified', 'provider_request_sent', 'provider_response',
                     'provider_connection_closed', 'unload_acknowledged', 'model_inventory_empty', 'physical_release'):
            if names.count(name) != 4: raise ValueError('extra provider/release event')
        terminal = events[-1]
        if (terminal['status'] != 'succeeded' or terminal['resource_state'] != 'released' or terminal['error_code'] is not None
                or terminal['cancel_epoch'] != 0 or type(terminal['cancel_epoch']) is not int
                or terminal['provider_attempts'] != 4 or terminal['result_published'] is not True
                or terminal['resource_release'] != last_release or meta['resource_release'] != last_release):
            raise ValueError('success not persistently terminal/released')
        result.update(kind='PUBLIC_NATIVE_ANALYSIS_JOIN_NOT_STAGE_ACCEPTANCE', frozen_timeline=timeline,
            model_digest=binding['model_digest'], source=meta['source'], suggestion=spec,
            raw_response=raw, candidate_sha=binding['candidate_sha'], authorization_sha256=binding['authorization_sha256'],
            remaining_obligations=['independent_frame_decode', 'browser_actions_and_exports', 'full_sampler_and_cleanup', 'independent_review'])
        return result
    except (KeyError, TypeError, ValueError, IndexError, BridgeError, ValidationError) as error:
        raise EvidenceError('browser analysis evidence join failed: '+str(error)) from error


@lru_cache(maxsize=1)
def result_validator():
    schema = json.loads((Path(__file__).resolve().parents[1]/'contracts/v0-result.schema.json').read_text())
    return Draft202012Validator(schema)


def adopted_export_join(raw, *, analysis, adoption_response, expected_draft, edited=False):
    """Actual browser download must preserve the actual public adoption result."""
    try:
        result = document(raw); result_validator().validate(result)
        adopted = document(adoption_response)['result']; result_validator().validate(adopted)
        if (analysis['kind'] != 'PUBLIC_NATIVE_ANALYSIS_JOIN_NOT_STAGE_ACCEPTANCE'
                or adopted['run_id'] != analysis['run_token'] or adopted['source'] != analysis['source']
                or adopted['raw_response'] != analysis['raw_response'] or adopted['suggestion'] != analysis['suggestion']
                or adopted['model_tag'] != 'gemma4:26b' or adopted['draft_origin'] != 'model_adopted'):
            raise ValueError('adoption differs from public analysis')
        for key in adopted:
            if key not in ('draft', 'draft_origin') and result[key] != adopted[key]: raise ValueError('export provenance changed: '+key)
        if result['draft'] != expected_draft or result['draft_origin'] != ('edited' if edited else 'model_adopted'):
            raise ValueError('manual draft/origin changed')
        if not edited and result['draft'] != adopted['draft']: raise ValueError('unmodified adopted draft differs')
        return {'kind': 'ADOPTED_EXPORT_JOIN_NOT_STAGE_ACCEPTANCE', 'run_token': result['run_id'],
            'source_sha256': result['source']['sha256'], 'artifact_sha256': digest(raw),
            'adoption_response_sha256': digest(adoption_response), 'draft_origin': result['draft_origin'], 'stage_pass_claim': False}
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        raise EvidenceError('browser export evidence join failed: '+str(error)) from error
