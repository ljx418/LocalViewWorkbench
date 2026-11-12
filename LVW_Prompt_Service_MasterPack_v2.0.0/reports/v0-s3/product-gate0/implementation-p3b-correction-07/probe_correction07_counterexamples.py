#!/usr/bin/env python3
"""The six independent earlier-read counterexamples of the correction-06 review.

This probe runs **only** under the inspected guarded runner: the audit hook
is installed before this file is executed, so no socket, no host process and
no download can happen here either.  It drives the *public* quality scoring
entry point of the product with a genuine public-owner run and replays the
six counterexamples that the independent correction-06 review reported as
still open:

    after_canonical_read_symlink     a symlink replaces the canonical receipt
                                     during the source seal read;
    after_canonical_read_plain       a plain file with the very same bytes
                                     replaces the canonical receipt during the
                                     first raw read;
    after_seal_read_missing          the source seal disappears during the
                                     first raw read;
    after_raw_read_leaf_symlink      a symlink replaces the first raw leaf
                                     during the second raw read;
    after_raw_read_parent_plain      a different plain directory replaces the
                                     parent of the first raw leaf during the
                                     second raw read;
    completion_canonical_leaf_redirect
                                     the canonical receipt is redirected
                                     immediately before the final completion
                                     check.

Every observation is a bounded observation of the current candidate.  A
script exit of 0 means that the observations were captured; it does not turn
a reproduced defect into a passing obligation and it is not an additional
product test.

The probe owns exactly one temporary root, registers it and removes it in the
``finally`` block.  It never scans and never deletes an older root, it never
decodes real media, it never starts a server and it never touches the
network.
"""

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="lvw-c07-counterexamples-"))
RESULTS = []
OWNED = [str(ROOT)]


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


def observe(name, run, **extra):
    """Drive the public scoring entry point and record the observation."""
    receipt = run["receipt"]
    scores = t._scores(receipt, run["projection_sha256"])
    try:
        value = q.recompute_scores(receipt, run["artifact_root"], scores,
                                   independence=t._independence())
        observation = {
            "refused": False,
            "aggregate_pass": value["aggregate_pass"],
            "all_rows_resolved": value["all_rows_resolved"],
            "decision": value["decision"],
            "images_usable": value["thresholds"]["images_usable"],
            "videos_usable": value["thresholds"]["videos_usable"],
            "total_critical": value["thresholds"]["total_critical_hallucinations"],
        }
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        observation = {
            "refused": True,
            "error": type(error).__name__ + ": " + str(error),
        }
    RESULTS.append({"name": name, "observation": observation, **extra})
    return observation


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


def hook_completion(action):
    """Fire ``action`` exactly once, immediately before the completion check."""
    original = q._ArtifactBoundary.verify
    state = {"fired": 0}

    def hooked(self):
        if not state["fired"] and sys._getframe(1).f_code.co_name == "recompute_scores":
            state["fired"] += 1
            action()
        return original(self)

    q._ArtifactBoundary.verify = hooked
    return original, state


def change(target, mode):
    """Rename ``target`` and put the requested replacement at its name."""
    retained = target.with_name(target.name + "-retained")
    target.rename(retained)
    if mode == "symlink":
        target.symlink_to(retained, target_is_directory=retained.is_dir())
    elif mode == "plain":
        if retained.is_dir():
            target.mkdir()
        else:
            target.write_bytes(retained.read_bytes())
    elif mode != "missing":
        raise ValueError("unknown mutation mode: " + str(mode))
    return retained


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore(target, retained, mode):
    """Restore the own fixture of this probe; never touch an older root."""
    if mode != "missing":
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    retained.rename(target)


try:
    # ---- the clean honest baseline -------------------------------------
    base = prepare("baseline")
    baseline = observe("clean_genuine_baseline", base)
    RESULTS[-1]["submissions"] = base["driver"].submissions
    RESULTS[-1]["provider_calls_reserved"] = base["receipt"]["provider_calls_reserved"]

    # ---- the six independent earlier-read counterexamples ---------------
    for name, trigger_kind, target_kind, mode in [
        ("after_canonical_read_symlink", "seal", "canonical", "symlink"),
        ("after_canonical_read_plain", "raw0", "canonical", "plain"),
        ("after_seal_read_missing", "raw0", "seal", "missing"),
        ("after_raw_read_leaf_symlink", "raw1", "raw0", "symlink"),
        ("after_raw_read_parent_plain", "raw1", "raw_parent", "plain"),
    ]:
        run = prepare(name)
        receipt = run["receipt"]
        paths = {
            "canonical": run["artifact_root"] / q.CANONICAL_RECEIPT_NAME,
            "seal": run["artifact_root"] / receipt["source_plan"]["path"],
            "raw0": run["artifact_root"] / receipt["rows"][0]["raw_artifact"],
            "raw1": run["artifact_root"] / receipt["rows"][1]["raw_artifact"],
        }
        paths["raw_parent"] = paths["raw0"].parent
        trigger = paths[trigger_kind]
        target = paths[target_kind]
        before = {key: digest(paths[key]) for key in ("canonical", "seal", "raw0")}
        receipt_before = copy.deepcopy(receipt)
        original, state = hook_read(trigger.stat().st_ino,
                                    lambda: change(target, mode))
        try:
            observe(name, run, trigger_kind=trigger_kind, target_kind=target_kind,
                   mutation=mode)
        finally:
            q.os.read = original
        retained = target.with_name(target.name + "-retained")
        if target_kind in before and retained.is_file():
            unchanged = digest(retained) == before[target_kind]
        elif target_kind == "raw_parent":
            # The mutated target is the parent directory of the first raw
            # leaf: the genuine leaf bytes are kept inside the retained
            # directory.
            unchanged = digest(retained / paths["raw0"].name) == before["raw0"]
        else:
            unchanged = None
        RESULTS[-1].update(
            hook_fired=state["fired"],
            entry_is_symlink_at_return=target.is_symlink(),
            entry_exists_at_return=target.exists(),
            before_sha256=before,
            original_bytes_unchanged=unchanged,
            caller_receipt_unchanged=(receipt == receipt_before),
        )
        restore(target, retained, mode)

    # ---- the companion: the redirect right before the completion check --
    run = prepare("completion_canonical_leaf_redirect")
    receipt = run["receipt"]
    canonical = run["artifact_root"] / q.CANONICAL_RECEIPT_NAME
    before = digest(canonical)
    receipt_before = copy.deepcopy(receipt)
    original, state = hook_completion(lambda: change(canonical, "symlink"))
    try:
        observe("completion_canonical_leaf_redirect", run)
    finally:
        q._ArtifactBoundary.verify = original
    retained = canonical.with_name(canonical.name + "-retained")
    RESULTS[-1].update(
        hook_fired=state["fired"],
        entry_is_symlink_at_return=canonical.is_symlink(),
        before_sha256=before,
        original_bytes_unchanged=digest(retained) == before,
        caller_receipt_unchanged=(receipt == receipt_before),
    )
    restore(canonical, retained, "symlink")

    # ---- the bounded descriptor observations ----------------------------
    run = prepare("descriptors")
    count = lambda: len(os.listdir("/proc/self/fd"))
    before = count()
    boundary = q._ArtifactBoundary(run["artifact_root"])
    names = [q.CANONICAL_RECEIPT_NAME,
             run["receipt"]["source_plan"]["path"],
             run["receipt"]["rows"][0]["raw_artifact"]]
    first = [boundary.read(name, q.MAX_ARTIFACT_BYTES) for name in names]
    entries = boundary._custody.count()
    during = count()
    for _ in range(8):
        again = [boundary.read(name, q.MAX_ARTIFACT_BYTES) for name in names]
        assert again == first, "a repeated read returned different bytes"
    after_repeat = count()
    boundary.close()
    after_close = count()
    RESULTS.append({
        "name": "bounded_custody_and_descriptors",
        "observation": {
            "refused": False,
            "custody_entries": entries,
            "custody_limit": q._CUSTODY_ENTRY_LIMIT,
            "descriptors_before": before,
            "descriptors_during": during,
            "descriptors_after_eight_repeats": after_repeat,
            "descriptors_after_close": after_close,
            "repeated_read_is_stable": during == after_repeat,
            "close_releases_every_descriptor": after_close <= before,
        },
    })
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

payload = {
    "kind": "S3_P3B_CORRECTION07_BOUNDED_COUNTEREXAMPLE_OBSERVATIONS",
    "note": ("Bounded observations of the current candidate.  They are not "
             "additional product tests and they do not turn a reproduced "
             "defect into a passing obligation."),
    "count": len(RESULTS),
    "observations": RESULTS,
    "owned_root": str(ROOT),
    "registered_roots": OWNED,
    "removed": not ROOT.exists(),
}
(OUT / "counterexample-observations.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
