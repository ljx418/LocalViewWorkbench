"""Deterministic Stage-S2 evidence oracles; never starts a target runtime."""
from math import ceil, isfinite

STAGE_IDS = ("V0-A02", "V0-A07", "V0-A09", "V0-A10")
VIDEO_CATEGORIES = ("static", "tracking", "fast-cut", "vfr")


class EvidenceError(ValueError):
    pass


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
