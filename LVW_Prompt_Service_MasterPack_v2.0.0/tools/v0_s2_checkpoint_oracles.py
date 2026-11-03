"""Deterministic Stage-S2 evidence oracles; never starts a target runtime."""
from math import ceil, isfinite
from fractions import Fraction
import hashlib
import json
import re

STAGE_IDS = ("V0-A02", "V0-A07", "V0-A09", "V0-A10")
VIDEO_CATEGORIES = ("static", "tracking", "fast-cut", "vfr")


class EvidenceError(ValueError):
    pass


def public_video_oracle(history, prompt_id, *, source_sha256, expected_model, chat_calls_before, chat_calls_after):
    """Validate public Comfy history plus independently counted Ollama log calls.

    Raw-array length alone cannot prove that four provider calls happened.
    Frame bytes still require independent decoder recomputation during review.
    """
    try:
        record=history[prompt_id]
        if record['status']['status_str'] not in {'success','completed'}:
            raise ValueError('unsuccessful public execution')
        submitted=record['prompt']
        if submitted[1]!=prompt_id or submitted[2]['1']['class_type']!='LVWVideoPromptOwner':
            raise ValueError('wrong public owner')
        text=record['outputs']['1']['text']
        if len(text)!=3 or not all(isinstance(item,str) for item in text):
            raise ValueError('missing UI evidence')
        raw,suggestion,metadata=(json.loads(item) for item in text)
        if set(raw)!={'frame_raw_responses'} or len(raw['frame_raw_responses'])!=4:
            raise ValueError('raw frame denominator')
        for item in raw['frame_raw_responses']:
            envelope=json.loads(item)
            if (envelope.get('model')!=expected_model or envelope.get('done') is not True
                    or not isinstance(envelope.get('message',{}).get('content'),str)
                    or not envelope['message']['content'].strip()):
                raise ValueError('model response incomplete')
        if (type(chat_calls_before) is not int or type(chat_calls_after) is not int
                or chat_calls_before<0 or chat_calls_after-chat_calls_before!=4):
            raise ValueError('provider log denominator')
        if (not re.fullmatch('[0-9a-f]{64}',source_sha256) or metadata['source_sha256']!=source_sha256
                or not re.fullmatch('[0-9a-f]{32}',metadata['run_token'])
                or metadata['cancel_epoch']!=0 or type(metadata['cancel_epoch']) is not int):
            raise ValueError('source/run identity')
        if suggestion.get('schema_version')!='lvw.prompt/1' or not suggestion['domains']['observation']:
            raise ValueError('suggestion missing observation')
        frames=metadata['frames']
        if len(frames)!=4:raise ValueError('frame denominator')
        previous=None;origin=None;basis=None
        for index,frame in enumerate(frames):
            if frame['index']!=index or type(frame['index']) is not int:
                raise ValueError('frame index')
            if any(type(frame[key]) is not int for key in ('pts','time_base_num','time_base_den')):
                raise ValueError('timestamp type')
            if min(frame['time_base_num'],frame['time_base_den'])<=0:raise ValueError('timebase')
            current_basis=Fraction(frame['time_base_num'],frame['time_base_den'])
            seconds=number(frame['time_seconds'],'frame seconds')
            current_origin=frame['pts']*current_basis-Fraction(str(seconds))
            if (previous is not None and frame['pts']<=previous) or (basis is not None and current_basis!=basis):
                raise ValueError('nonmonotonic/mixed frame timeline')
            if origin is not None and abs(float(current_origin-origin))>1e-9:
                raise ValueError('inconsistent timestamp origin')
            if not re.fullmatch('[0-9a-f]{64}',frame['sha256']):raise ValueError('frame hash missing')
            previous=frame['pts'];origin=current_origin;basis=current_basis
        return {'source_sha256':source_sha256,'frames':frames,'run_token':metadata['run_token'],
                'provider_log_calls':4,'raw_sha256':hashlib.sha256(text[0].encode()).hexdigest(),
                'suggestion_sha256':hashlib.sha256(text[1].encode()).hexdigest(),'stage_pass_claim':False}
    except (KeyError,IndexError,TypeError,ValueError,ZeroDivisionError,OverflowError,AttributeError) as exc:
        raise EvidenceError('public video evidence invalid: '+type(exc).__name__) from exc


def number(value, label):
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise EvidenceError(label + ": invalid observation")
    return value


def performance_oracle(records, *, run_id, candidate_sha):
    """Fixed 10+10 hot denominator, fresh unique sample runs, nearest-rank P95.

    Cold loading must be recorded separately and is never silently excluded from
    this list after a slow run. This oracle receives only the frozen hot phase.
    """
    if not isinstance(records, list) or len(records) != 20:
        raise EvidenceError("performance denominator must be exactly 20")
    seen = set(); durations = {"image":[], "video":[]}
    peak_gpu = 0; min_ram = float("inf")
    for record in records:
        if record.get("run_id") != run_id or record.get("candidate_sha") != candidate_sha:
            raise EvidenceError("cross-run/candidate evidence")
        identity = record.get("sample_run_id")
        if not isinstance(identity,str) or not identity or identity in seen:
            raise EvidenceError("missing/duplicate performance run")
        seen.add(identity)
        kind = record.get("kind")
        if kind not in durations or record.get("phase") != "hot":
            raise EvidenceError("unfrozen performance phase")
        if record.get("outcome") != "succeeded" or record.get("oom") is not False:
            raise EvidenceError("failed/unknown/OOM run cannot be excluded")
        if type(record.get("provider_calls")) is not int or record.get("provider_calls") != (1 if kind == "image" else 4):
            raise EvidenceError("provider denominator mismatch")
        duration = number(record.get("duration_seconds"), "duration")
        if duration == 0:
            raise EvidenceError("zero-duration model run")
        samples = record.get("resource_samples")
        if not isinstance(samples,list) or len(samples) < 2:
            raise EvidenceError("resource sampling missing")
        previous = None
        for sample in samples:
            elapsed = number(sample.get("elapsed_seconds"), "sample time")
            gpu = number(sample.get("gpu_used_mib"), "GPU")
            ram = number(sample.get("available_ram_mib"), "RAM")
            if gpu >= 23552 or ram < 2048:
                raise EvidenceError("resource threshold exceeded")
            if previous is not None and (elapsed <= previous or elapsed - previous > 1.5):
                raise EvidenceError("resource trace gap or nonmonotonic time")
            previous = elapsed
            peak_gpu = max(peak_gpu,gpu); min_ram = min(min_ram,ram)
        if samples[0]["elapsed_seconds"] > .5 or previous < duration or previous - duration > 1.5:
            raise EvidenceError("resource trace does not cover actual run")
        durations[kind].append(duration)
    result = {}
    for kind,limit in (("image",180),("video",300)):
        values = sorted(durations[kind])
        if len(values) != 10:
            raise EvidenceError("each media kind requires ten hot runs")
        p95 = values[ceil(.95 * len(values)) - 1]
        if p95 > limit:
            raise EvidenceError(kind + " P95 exceeds frozen threshold")
        result[kind] = {"count":len(values),"p95_seconds":p95,"limit_seconds":limit}
    return {"performance":result,"peak_gpu_mib":peak_gpu,"minimum_available_ram_mib":min_ram,
            "stage_pass_claim":False}


def cancellation_oracle(record):
    accepted = number(record.get("ack_seconds"), "cancel acknowledgement")
    stopped = number(record.get("actual_stop_seconds"), "actual stop")
    released = number(record.get("release_seconds"), "resource release")
    if accepted > 1 or released < stopped or released - stopped > 30:
        raise EvidenceError("cancel/release timing threshold failed")
    for key in ("late_result_discarded","draft_unchanged","owned_connection_only","ports_and_temp_clean"):
        if record.get(key) is not True:
            raise EvidenceError(key + ": missing positive proof")
    if type(record.get("non_owned_terminations")) is not int or record.get("non_owned_terminations") != 0:
        raise EvidenceError("non-owned termination or unknown count")
    return {"ack_seconds":accepted,"release_after_stop_seconds":released-stopped,"stage_pass_claim":False}
