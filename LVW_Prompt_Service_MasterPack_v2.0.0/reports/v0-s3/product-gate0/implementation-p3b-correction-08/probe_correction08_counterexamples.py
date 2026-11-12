#!/usr/bin/env python3
"""The bounded resource observations of the correction-08 batch.

This probe runs **only** under the inspected guarded runner: the audit hook
is installed before this file is executed, so no socket, no host process and
no download can happen here either.  It drives the *real* owners of the
product - the ``_ArtifactBoundary`` of the scoring entry point and the
public ``recompute_scores`` entry point - after a genuine public-owner run,
and it observes the two resource roots of the independent correction-07
review:

    owner_child_directory_metadata   a child directory is opened and its
                                     first metadata read fails: the opened
                                     descriptor must be owned and closed;
    owner_leaf_metadata              the same for a leaf;
    public_evaluation_metadata       the public scoring entry point fails
                                     the same way and must release every
                                     descriptor it had pinned;
    custody_bound_exact_and_one_over the custody is filled with exactly the
                                     internal bound and the next name must
                                     be refused *before* it is opened;
    custody_bound_cache_hit          a repeated name at the bound reuses
                                     its pinned descriptor;
    failed_admission                 a refused admission gives its slot back
                                     and leaves the registry undamaged.

Every observation is a bounded observation of the current candidate.  A
script exit of 0 means that the observations were captured and that no
observed invariant was violated; it does not turn an observation into a
passing obligation and it is not an additional product test.

The probe owns exactly one temporary root, registers every root that it
creates and removes them all in the ``finally`` block.  It never scans and
never deletes an older root, it never decodes real media, it never starts a
server and it never touches the network.
"""

import errno
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="lvw-c08-observations-"))
RESULTS = []
OWNED = [str(ROOT)]
VIOLATIONS = []


def descriptors():
    """The number of open descriptors of this process."""
    return len(os.listdir("/proc/self/fd"))


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


def fail_the_metadata_of_the_next_open(arm_after_the_boundary=True):
    """Fail the metadata of the next opened descriptor exactly once.

    The fault is injected into the product's own ``os`` module: the
    product code that opens the descriptor is the code that fails.  Nothing
    is repaired afterwards, so a leaked descriptor stays visible in the
    descriptor count.
    """
    state = {"armed": not arm_after_the_boundary, "fired": 0, "descriptor": None}
    original_open = q.os.open
    original_fstat = q.os.fstat
    original_init = q._ArtifactBoundary.__init__

    def hooked_open(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if state["armed"] and state["descriptor"] is None:
            state["descriptor"] = descriptor
        return descriptor

    def hooked_fstat(descriptor):
        if state["fired"] == 0 and state["armed"] and descriptor == state["descriptor"]:
            state["fired"] += 1
            raise OSError(errno.EIO, "injected metadata failure")
        return original_fstat(descriptor)

    def hooked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        state["armed"] = True

    q.os.open = hooked_open
    q.os.fstat = hooked_fstat
    if arm_after_the_boundary:
        q._ArtifactBoundary.__init__ = hooked_init

    def restore():
        q.os.open = original_open
        q.os.fstat = original_fstat
        q._ArtifactBoundary.__init__ = original_init

    return state, restore


def count_opens():
    """Count the real ``os.open`` calls of the product."""
    counter = {"count": 0}
    original_open = q.os.open

    def hooked_open(path, flags, *args, **kwargs):
        counter["count"] += 1
        return original_open(path, flags, *args, **kwargs)

    q.os.open = hooked_open

    def restore():
        q.os.open = original_open

    return counter, restore


def record(name, observation):
    RESULTS.append({"name": name, "observation": observation})


def owner_metadata_observation(name, run, relative):
    """One owner level observation of a metadata failure after the open."""
    before = descriptors()
    state, restore = fail_the_metadata_of_the_next_open()
    boundary = None
    observation = {}
    try:
        boundary = q._ArtifactBoundary(run["artifact_root"])
        during = descriptors()
        refused = None
        try:
            boundary.read(relative, q.MAX_ARTIFACT_BYTES)
        except Exception as error:  # noqa: BLE001 - the refusal is the observation
            refused = type(error).__name__ + ": " + str(error)
        after_read = descriptors()
        custody_entries = boundary._custody.count()
        reserved = boundary._custody.reserved()
        boundary.close()
        after_close = descriptors()
        observation = {
            "relative": relative,
            "refused": refused,
            "hook_fired": state["fired"],
            "descriptors_before": before,
            "descriptors_during": during,
            "descriptors_after_the_refused_read": after_read,
            "descriptors_after_close": after_close,
            "custody_entries": custody_entries,
            "reserved_slots": reserved,
            "the_refused_descriptor_is_closed": after_read == during,
            "the_boundary_releases_everything": after_close <= before,
            "the_custody_is_undamaged": custody_entries == 0 and reserved == 0,
        }
    finally:
        restore()
        if boundary is not None:
            boundary.close()
    record(name, observation)
    if observation.get("hook_fired") != 1:
        VIOLATIONS.append(name + ": the injected fault did not fire exactly once")
    if not observation.get("the_refused_descriptor_is_closed"):
        VIOLATIONS.append(name + ": the refused descriptor was left open")
    if not observation.get("the_boundary_releases_everything"):
        VIOLATIONS.append(name + ": the boundary did not release every descriptor")
    return observation


try:
    # ---- the owner level observations ------------------------------------
    run = prepare("owner_child_directory_metadata")
    owner_metadata_observation(
        "owner_child_directory_metadata", run,
        run["receipt"]["rows"][0]["raw_artifact"])
    run = prepare("owner_leaf_metadata")
    owner_metadata_observation("owner_leaf_metadata", run, q.CANONICAL_RECEIPT_NAME)

    # ---- the public entry point ------------------------------------------
    run = prepare("public_evaluation_metadata")
    before = descriptors()
    state, restore = fail_the_metadata_of_the_next_open()
    refused = None
    try:
        q.recompute_scores(run["receipt"], run["artifact_root"],
                           t._scores(run["receipt"], run["projection_sha256"]),
                           independence=t._independence())
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        refused = type(error).__name__ + ": " + str(error)
    finally:
        restore()
    after = descriptors()
    record("public_evaluation_metadata", {
        "refused": refused,
        "hook_fired": state["fired"],
        "descriptors_before": before,
        "descriptors_after": after,
        "the_public_refusal_releases_everything": after <= before,
    })
    if state["fired"] != 1:
        VIOLATIONS.append("public_evaluation_metadata: the injected fault did not fire exactly once")
    if after > before:
        VIOLATIONS.append("public_evaluation_metadata: the refusing evaluation leaked a descriptor")

    # ---- the internal bound of the custody --------------------------------
    run = prepare("custody_bound")
    root = run["artifact_root"]
    names = []
    for index in range(q._CUSTODY_ENTRY_LIMIT):
        name = "bound-%04d.bin" % index
        (root / name).write_bytes(b"abcd")
        names.append(name)
    excess = "bound-excess.bin"
    (root / excess).write_bytes(b"abcd")
    boundary = q._ArtifactBoundary(root)
    counter, restore_counter = count_opens()
    observation = {}
    try:
        before = descriptors()
        for name in names:
            boundary.read(name, 4)
        at_bound = descriptors()
        opens_at_bound = counter["count"]
        entries_at_bound = boundary._custody.count()
        refused = None
        try:
            boundary.read(excess, 4)
        except Exception as error:  # noqa: BLE001 - the refusal is the observation
            refused = type(error).__name__ + ": " + str(error)
        opens_after_excess = counter["count"]
        after_excess = descriptors()
        verified = True
        try:
            boundary.verify()
        except Exception:  # noqa: BLE001 - the verification is the observation
            verified = False
        boundary.read(names[0], 4)
        opens_after_repeat = counter["count"]
        after_repeat = descriptors()
        observation = {
            "custody_limit": q._CUSTODY_ENTRY_LIMIT,
            "exact_entries": entries_at_bound,
            "opens_for_the_exact_bound": opens_at_bound,
            "refused": refused,
            "extra_opens_for_the_excess": opens_after_excess - opens_at_bound,
            "descriptors_before": before,
            "descriptors_at_the_bound": at_bound,
            "descriptors_after_the_refused_excess": after_excess,
            "descriptors_after_the_repeated_name": after_repeat,
            "opens_after_the_repeated_name": opens_after_repeat,
            "the_earlier_custody_is_still_verifiable": verified,
            "the_excess_is_refused_without_an_open":
                opens_after_excess == opens_at_bound and after_excess == at_bound,
            "the_repeated_name_at_the_bound_opens_nothing":
                opens_after_repeat == opens_at_bound and after_repeat == at_bound,
        }
    finally:
        restore_counter()
        boundary.close()
        for name in names + [excess]:
            (root / name).unlink(missing_ok=True)
    after_close = descriptors()
    observation["descriptors_after_close"] = after_close
    observation["the_close_releases_everything"] = after_close <= observation["descriptors_before"]
    record("custody_bound_exact_and_one_over", observation)
    if observation.get("extra_opens_for_the_excess") != 0:
        VIOLATIONS.append("custody_bound_exact_and_one_over: the excess entry was opened")
    if not observation.get("the_excess_is_refused_without_an_open"):
        VIOLATIONS.append("custody_bound_exact_and_one_over: the refused excess raised the descriptor use")
    if not observation.get("the_repeated_name_at_the_bound_opens_nothing"):
        VIOLATIONS.append("custody_bound_exact_and_one_over: a repeated name at the bound was opened again")
    if not observation.get("the_earlier_custody_is_still_verifiable"):
        VIOLATIONS.append("custody_bound_exact_and_one_over: the earlier custody is no longer verifiable")

    # ---- a refused admission gives its slot back ---------------------------
    run = prepare("failed_admission")
    root = run["artifact_root"]
    (root / "admission-a.bin").write_bytes(b"abcd")
    (root / "admission-b.bin").write_bytes(b"abcd")
    state, restore = fail_the_metadata_of_the_next_open()
    boundary = q._ArtifactBoundary(root)
    observation = {}
    try:
        during = descriptors()
        refused = None
        try:
            boundary.read("admission-a.bin", 4)
        except Exception as error:  # noqa: BLE001 - the refusal is the observation
            refused = type(error).__name__ + ": " + str(error)
        after_read = descriptors()
        entries = boundary._custody.count()
        reserved = boundary._custody.reserved()
        admitted = None
        try:
            admitted = boundary.read("admission-b.bin", 4).decode("ascii")
        except Exception as error:  # noqa: BLE001 - the admission is the observation
            admitted = type(error).__name__ + ": " + str(error)
        entries_after = boundary._custody.count()
        boundary.close()
        observation = {
            "refused": refused,
            "hook_fired": state["fired"],
            "descriptors_during": during,
            "descriptors_after_the_refused_admission": after_read,
            "custody_entries_after_the_refusal": entries,
            "reserved_slots_after_the_refusal": reserved,
            "the_next_name_is_admitted": admitted,
            "custody_entries_after_the_admission": entries_after,
            "the_refused_admission_closed_its_descriptor": after_read == during,
            "the_refused_admission_consumed_no_slot": entries == 0 and reserved == 0,
        }
    finally:
        restore()
        boundary.close()
        (root / "admission-a.bin").unlink(missing_ok=True)
        (root / "admission-b.bin").unlink(missing_ok=True)
    record("failed_admission", observation)
    if not observation.get("the_refused_admission_closed_its_descriptor"):
        VIOLATIONS.append("failed_admission: the refused admission leaked a descriptor")
    if not observation.get("the_refused_admission_consumed_no_slot"):
        VIOLATIONS.append("failed_admission: the refused admission consumed a custody slot")
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

payload = {
    "kind": "S3_P3B_CORRECTION08_BOUNDED_RESOURCE_OBSERVATIONS",
    "note": ("Bounded observations of the current candidate.  They are not "
             "additional product tests and they do not turn an observation "
             "into a passing obligation."),
    "count": len(RESULTS),
    "observations": RESULTS,
    "violations": VIOLATIONS,
    "owned_root": str(ROOT),
    "registered_roots": OWNED,
    "removed": not ROOT.exists(),
    "stage_pass_claim": False,
    "product_gate0": False,
}
(OUT / "counterexample-observations.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
if VIOLATIONS:
    print("VIOLATED INVARIANTS: " + "; ".join(VIOLATIONS))
    raise SystemExit(1)
