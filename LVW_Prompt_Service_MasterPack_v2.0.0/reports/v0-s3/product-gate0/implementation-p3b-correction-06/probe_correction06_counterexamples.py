#!/usr/bin/env python3
"""The remaining independent counterexamples of the correction-05 review.

This probe runs **only** under the guarded runner: the audit hook is
installed before this file is executed, so no socket, no host process and no
download can happen here either.  It drives the *public* quality scoring
entry point of the product with a genuine public-owner run and replays the
counterexamples that the correction-05 independent review reported as open
(M01 typed facts and extra facts, NM03 named hierarchy during a read).

Every observation is a bounded observation of the current candidate.  A
script exit of 0 means that the observations were captured; it does not turn
a reproduced defect into a passing obligation.

The probe owns exactly one temporary root, registers it and removes it in
the ``finally`` block.  It never scans and never deletes an older root, it
never decodes real media, it never starts a server and it never touches the
network.
"""

import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="lvw-c06-focused-"))
RESULTS = []
OWNED = []


def prepare(name):
    """A genuine public-owner run in a private root of this probe."""
    root = ROOT / name
    OWNED.append(str(root))
    phase, driver, projection = t._prepare(root, clock=t.FakeClock(step=0.0))
    receipt = phase.run()
    return {
        "phase": phase,
        "driver": driver,
        "receipt": receipt,
        "artifact_root": phase.directory,
        "root": phase.root,
        "projection": projection,
        "projection_sha256": hashlib.sha256(projection).hexdigest(),
    }


def observe(name, receipt, run, scores=None, **extra):
    """Drive the public scoring entry point and record the observation."""
    if scores is None:
        scores = t._scores(receipt, run["projection_sha256"])
    try:
        value = q.recompute_scores(receipt, run["artifact_root"], scores,
                                   independence=t._independence())
        row = value["rows"][0]
        observation = {
            "refused": False,
            "aggregate_pass": value["aggregate_pass"],
            "all_rows_resolved": value["all_rows_resolved"],
            "decision": value["decision"],
            "images_usable": value["thresholds"]["images_usable"],
            "videos_usable": value["thresholds"]["videos_usable"],
            "total_critical": value["thresholds"]["total_critical_hallucinations"],
            "row0_usable": row["usable"],
            "row0_resolved": row["resolved"],
            "row0_reason": row["reason"],
            "row0_evidence_reason": row.get("evidence_reason"),
        }
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        observation = {
            "refused": True,
            "error": type(error).__name__ + ": " + str(error),
        }
    RESULTS.append({"name": name, "observation": observation, **extra})


def hook_read(inode, action):
    """Fire ``action`` exactly once, during the read of the given inode."""
    original = q.os.read
    state = {"fired": 0}

    def hooked(descriptor, count):
        value = original(descriptor, count)
        if not state["fired"]:
            try:
                info = os.fstat(descriptor)
            except OSError:
                return value
            if info.st_ino == inode:
                state["fired"] += 1
                action()
        return value

    q.os.read = hooked
    return original, state


def redirect_directory(path):
    """Rename the directory and replace the entry with a symlink to it."""
    retained = path.with_name(path.name + "-retained")
    path.rename(retained)
    path.symlink_to(retained, target_is_directory=True)
    return retained


def replace_directory(path):
    """Rename the directory and put a different plain directory in its place."""
    retained = path.with_name(path.name + "-retained")
    path.rename(retained)
    path.mkdir()
    return retained


def redirect_file(path):
    """Rename the file and replace the entry with a symlink to it."""
    retained = path.with_name(path.name + "-retained")
    path.rename(retained)
    path.symlink_to(retained)
    return retained


def main():
    # ------------------------------------------------------------------
    # the honest baseline: the aggregate of a genuine run still passes
    # ------------------------------------------------------------------
    base = prepare("baseline")
    observe("honest_baseline", base["receipt"], base)

    # ------------------------------------------------------------------
    # M01: the typed actual facts and the closed key sets
    # ------------------------------------------------------------------
    def identity_to_bool(document):
        identity = list(document["rows"][0]["source_evidence"]["identity"])
        identity[0] = True
        document["rows"][0]["source_evidence"]["identity"] = identity

    mutations = [
        ("attempt_true_to_int1",
         lambda document: document["rows"][0].update(public_submission_attempted=1)),
        ("attempt_true_to_float",
         lambda document: document["rows"][0].update(public_submission_attempted=1.0)),
        ("counter_one_to_bool",
         lambda document: document["rows"][0].update(provider_calls=True)),
        ("counter_one_to_float",
         lambda document: document["rows"][0].update(provider_calls=1.0)),
        ("nested_identity_int_to_bool", identity_to_bool),
        ("nested_counter_int_to_bool",
         lambda document: document["rows"][0]["release_evidence"]["gpu_samples"][0].update(
             gpu_used_mib=True)),
        ("source_extra_fact",
         lambda document: document["rows"][0]["source_evidence"].update(
             independent_added_fact="fabricated")),
        ("release_extra_fact",
         lambda document: document["rows"][0]["release_evidence"].update(
             independent_added_fact="fabricated")),
        ("gpu_sample_extra_fact",
         lambda document: document["rows"][0]["release_evidence"]["gpu_samples"][0].update(
             independent_added_fact="fabricated")),
        ("receipt_extra_fact",
         lambda document: document.update(independent_added_fact="fabricated")),
        ("row_extra_fact",
         lambda document: document["rows"][0].update(independent_added_fact="fabricated")),
    ]
    for name, mutate in mutations:
        document = copy.deepcopy(base["receipt"])
        mutate(document)
        observe(name, document, base,
                canonical_unchanged=json.loads(
                    (base["artifact_root"] / q.CANONICAL_RECEIPT_NAME).read_bytes()) == base["receipt"])

    # The seal only: the ordinal of the seal row is typed wrongly while the
    # seal hash, the seal length and every execution row stay consistent.
    for name, value in (("seal_only_ordinal_true", True), ("seal_only_ordinal_float", 1.0)):
        run = prepare("seal-" + name)

        def contradict(document, value=value):
            document["rows"][0]["ordinal"] = value

        published = t._rewrite_seal(run, contradict)
        observe(name, copy.deepcopy(published), run,
                execution_rows_unchanged=published["rows"] == base["receipt"]["rows"])

    # The monotone known failure handling and the independently scored
    # critical evidence stay visible under the typed binding.
    document = copy.deepcopy(base["receipt"])
    document["rows"][0].update(execution_status="FAIL",
                               error_code="PUBLIC_EXECUTION_NOT_SUCCESSFUL")
    scores = t._scores(base["receipt"], base["projection_sha256"])
    scores[0]["critical_hallucinations"] = 3
    observe("known_overlay_with_critical_three", document, base, scores=scores)

    # ------------------------------------------------------------------
    # NM03: the named hierarchy during a bounded read
    # ------------------------------------------------------------------
    for level in ("run_root", "temp", "phase", "raw_parent"):
        run = prepare("race-" + level)
        receipt = run["receipt"]
        if level == "run_root":
            target = run["root"]
            trigger = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
        elif level == "temp":
            target = run["root"] / "temp"
            trigger = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
        elif level == "phase":
            target = run["artifact_root"]
            trigger = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
        else:
            target = (run["artifact_root"] / receipt["rows"][0]["raw_artifact"]).parent
            trigger = run["artifact_root"] / receipt["rows"][0]["raw_artifact"]
        before = trigger.read_bytes()
        original, state = hook_read(os.stat(trigger).st_ino,
                                    lambda: redirect_directory(target))
        try:
            observe("redirect_during_read_" + level, receipt, run,
                    trigger="the first bounded read of the named artifact")
        finally:
            q.os.read = original
        RESULTS[-1]["hook_fired"] = state["fired"]
        RESULTS[-1]["entry_is_symlink_at_return"] = target.is_symlink()
        RESULTS[-1]["original_bytes_unchanged"] = trigger.read_bytes() == before

    # A renamed ancestor that is replaced by a *different plain directory*
    # is refused as well, and so is a missing named entry.
    run = prepare("race-plain-directory")
    trigger = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
    before = trigger.read_bytes()
    original, state = hook_read(os.stat(trigger).st_ino,
                                lambda: replace_directory(run["root"]))
    try:
        observe("rename_to_another_plain_directory_during_read", run["receipt"], run)
    finally:
        q.os.read = original
    RESULTS[-1]["hook_fired"] = state["fired"]
    retained = run["root"].with_name(run["root"].name + "-retained")
    RESULTS[-1]["original_bytes_unchanged"] = (
        (retained / "temp" / "s3-quality" / q.CANONICAL_RECEIPT_NAME).read_bytes() == before)

    run = prepare("race-missing-entry")
    trigger = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
    original, state = hook_read(os.stat(trigger).st_ino,
                                lambda: trigger.rename(trigger.with_name(trigger.name + "-retained")))
    try:
        observe("missing_named_entry_during_read", run["receipt"], run)
    finally:
        q.os.read = original
    RESULTS[-1]["hook_fired"] = state["fired"]

    run = prepare("race-leaf-file")
    trigger = run["artifact_root"] / run["receipt"]["rows"][0]["raw_artifact"]
    before = trigger.read_bytes()
    original, state = hook_read(os.stat(trigger).st_ino, lambda: redirect_file(trigger))
    try:
        observe("redirected_raw_leaf_during_read", run["receipt"], run)
    finally:
        q.os.read = original
    RESULTS[-1]["hook_fired"] = state["fired"]
    RESULTS[-1]["original_bytes_unchanged"] = trigger.read_bytes() == before

    payload = {
        "kind": "S3_P3B_CORRECTION_06_FOCUSED_COUNTEREXAMPLE_OBSERVATIONS",
        "observations": RESULTS,
        "count": len(RESULTS),
        "owned_root": str(ROOT),
        "registered_roots": list(OWNED),
        "real_execution_performed": False,
        "stage_pass_claim": False,
        "product_gate0": False,
    }
    (OUT / "focused-observations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)
    raise SystemExit(code)
