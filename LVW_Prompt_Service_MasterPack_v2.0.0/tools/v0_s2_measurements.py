"""Join actual public history, warm events and native samples without retiming.

No target actions occur here. The caller must load fresh, hash-bound artifacts
from one authorized run; these joins do not establish artifact authenticity.
"""
import hashlib
import json
import math
import re
from pathlib import Path
from functools import lru_cache
from jsonschema import Draft202012Validator,ValidationError

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import validate_lineage
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources import validate_snapshot
from tools.v0_s2_checkpoint_oracles import EvidenceError,public_video_oracle


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def stamp(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise EvidenceError('invalid native monotonic observation')
    return value


@lru_cache(maxsize=1)
def spec_validator():
    document=json.loads((Path(__file__).resolve().parents[1]/'contracts/v0-result.schema.json').read_text())
    return Draft202012Validator({**document,'$ref':'#/$defs/PromptSpec'})


def hot_record(*,run_id,sample_run_id,candidate_sha,authorization_sha256,kind,binding,
               history,prompt_id,source_sha256,chat_calls_before,chat_calls_after,
               warm_events,resource_samples,sampler_receipt,started,finished):
    """Full public interval uses one native Python monotonic clock.

    Native clock readings must bracket submit/history in the real runner. Never
    subtract load, cleanup, polling or queue time, nor shift a resource point to
    manufacture coverage. Samples outside this interval remain in raw evidence.
    """
    try:
        if (not re.fullmatch('[0-9a-f]{40}',candidate_sha)
                or not re.fullmatch('[0-9a-f]{64}',authorization_sha256)
                or not re.fullmatch('[0-9a-f]{64}',source_sha256) or kind not in ('image','video')):
            raise ValueError('invalid identity')
        if binding['candidate_sha']!=candidate_sha or binding['authorization_sha256']!=authorization_sha256:
            raise ValueError('binding identity mismatch')
        for value in (run_id,sample_run_id):
            if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}',value):
                raise ValueError('bounded run identity required')
        started=stamp(started);finished=stamp(finished)
        if finished<=started:raise ValueError('empty interval')
        count=1 if kind=='image' else 4
        if (type(chat_calls_before) is not int or type(chat_calls_after) is not int
                or chat_calls_before<0 or chat_calls_after-chat_calls_before!=count):
            raise ValueError('independent provider log count mismatch')
        record=history[prompt_id]
        if kind=='video':
            public_video_oracle(history,prompt_id,source_sha256=source_sha256,expected_model='gemma4:26b',
                chat_calls_before=chat_calls_before,chat_calls_after=chat_calls_after)
            raws=json.loads(record['outputs']['1']['text'][0])['frame_raw_responses']
            spec_validator().validate(json.loads(record['outputs']['1']['text'][1]))
        else:
            submitted=record['prompt'];graph=submitted[2]
            if (record['status']['status_str'] not in ('success','completed') or submitted[1]!=prompt_id
                    or graph['1']['class_type']!='LVWControlledImageInput'
                    or graph['2']['class_type']!='LVWImagePromptBridge' or graph['2']['inputs']['image']!=['1',0]):
                raise ValueError('image public path bypassed')
            text=record['outputs']['2']['text']
            if len(text)!=2:
                raise ValueError('image outputs missing')
            spec_validator().validate(json.loads(text[1]))
            envelope=json.loads(text[0])
            if (envelope.get('model')!='gemma4:26b' or envelope.get('done') is not True
                    or not isinstance(envelope.get('message',{}).get('content'),str)
                    or not envelope['message']['content'].strip()):raise ValueError('image provider response incomplete')
            raws=[text[0]]
        if not isinstance(warm_events,list) or len(warm_events)!=2+2*count:
            raise ValueError('warm trace denominator')
        first,last=warm_events[0],warm_events[-1]
        if (first['event']!='request_started' or first['kind']!=kind or first['expected_calls']!=count
                or type(first['request_number']) is not int or not 1<=first['request_number']<=20
                or last['event']!='request_finished' or last['outcome']!='succeeded'
                or last['restored_unloaded'] is not True):raise ValueError('warm request not successfully restored')
        origin=stamp(first['monotonic_seconds'])-stamp(first['elapsed_seconds'])
        if origin<started:raise ValueError('model trace predates public request')
        previous=None;snapshots=[];owner_pid=None
        for event in warm_events:
            observed=stamp(event['monotonic_seconds']);elapsed=stamp(event['elapsed_seconds'])
            if (event['candidate_sha']!=candidate_sha or event['authorization_sha256']!=authorization_sha256
                    or event['request_number']!=first['request_number'] or not started<=observed<=finished
                    or (previous is not None and observed<=previous)
                    or not math.isclose(observed-origin,elapsed,rel_tol=0,abs_tol=1e-6)):
                raise ValueError('cross-run or fabricated warm timeline')
            previous=observed
        for index in range(count):
            before,after=warm_events[1+2*index:3+2*index]
            if (before['event']!='before_call' or after['event']!='after_call'
                    or type(before['call_index']) is not int or type(after['call_index']) is not int
                    or before['call_index']!=index or after['call_index']!=index
                    or not re.fullmatch('[0-9a-f]{64}',before['request_payload_sha256'])
                    or after['provider_raw_sha256']!=digest(raws[index])):
                raise ValueError('provider raw hash/order mismatch')
            if not stamp(binding['issued_at'])<=stamp(before['wall_seconds'])<stamp(binding['expires_at']):
                raise ValueError('provider call started outside warm lease')
            resource=before['resource_admission'];pid=resource['owner_pid'];pids=resource['compute_pids']
            if owner_pid is not None and owner_pid!=pid:raise ValueError('Comfy owner changed')
            owner_pid=pid
            proof=resource['native_lineage']
            if proof['verified_compute_pids']!=pids:raise ValueError('GPU PID evidence mismatch')
            owned=validate_lineage(proof['snapshot'],binding,pids,pid)
            validate_snapshot(','.join(str(resource[k]) for k in ('gpu_total_mib','gpu_used_mib','gpu_free_mib')),
                '\n'.join(str(p) for p in pids),resource['available_ram_mib'],owner_pid=pid,warm=True,owned_compute_pids=owned)
            snapshots.append({'call_index':index,'elapsed_seconds':before['monotonic_seconds']-started,'api_ps':before['api_ps']})
        for event in (first,last):
            proof=event['root_proof']
            if proof['verified_compute_pids']!=[]:raise ValueError('root proof scope mismatch')
            validate_lineage(proof['snapshot'],binding,[],owner_pid)
        if (sampler_receipt['decision']!='RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'
                or sampler_receipt['owned_gpu_query_exited'] is not True
                or not re.fullmatch('[0-9a-f]{64}',sampler_receipt['nvidia_binary_sha256'])
                or sampler_receipt['nvidia_binary_sha256']!=sampler_receipt['nvidia_binary_sha256_after']
                or sampler_receipt['nvidia_binary_sha256']!=binding['nvidia_smi_sha256']
                or owner_pid not in sampler_receipt['private_process_set']
                or binding['ollama_pid'] not in sampler_receipt['private_process_set']):
            raise ValueError('sampler terminal/identity/process set invalid')
        samples=[];last_time=None;covered=False;phase_peak=0;phase_min_ram=None
        if not isinstance(resource_samples,list) or len(resource_samples)!=sampler_receipt['samples']:
            raise ValueError('resource trace denominator mismatch')
        for index,point in enumerate(resource_samples):
            observed=stamp(point['monotonic_seconds'])
            if point['sample_index']!=index or type(point['sample_index']) is not int or (last_time is not None and observed<=last_time):
                raise ValueError('resource trace order invalid')
            if last_time is not None and observed-last_time>1.5:raise ValueError('resource trace has an acquisition gap')
            last_time=observed
            gpu=stamp(point['gpu_used_mib']);ram=stamp(point['available_ram_mib'])
            if gpu>=23552 or ram<2048:raise ValueError('resource trace violates threshold outside or inside request')
            phase_peak=max(phase_peak,gpu);phase_min_ram=ram if phase_min_ram is None else min(phase_min_ram,ram)
            if set(point['private_bytes'])!={str(pid) for pid in sampler_receipt['private_process_set']}:
                raise ValueError('private process set omitted')
            if any(type(value) is not int or value<0 for value in point['private_bytes'].values()):
                raise ValueError('private bytes invalid')
            if observed>=started and not covered:
                samples.append({'elapsed_seconds':observed-started,'gpu_used_mib':point['gpu_used_mib'],
                                'available_ram_mib':point['available_ram_mib'],'private_bytes':point['private_bytes']})
                if observed>=finished:covered=True
        if not covered:raise ValueError('resource trace ends before public request')
        return {'run_id':run_id,'candidate_sha':candidate_sha,'sample_run_id':sample_run_id,'kind':kind,
            'phase':'hot','duration_seconds':finished-started,'provider_calls':count,'outcome':'succeeded','oom':False,
            'source_sha256':source_sha256,'prompt_id':prompt_id,'warm_model_snapshots':snapshots,'resource_samples':samples,
            'sampler_phase_peak_gpu_mib':phase_peak,'sampler_phase_min_available_ram_mib':phase_min_ram}
    except (KeyError,IndexError,TypeError,ValueError,OverflowError,BridgeError,ValidationError) as error:
        raise EvidenceError('hot measurement join failed: '+type(error).__name__) from error
