"""Replay the independent review's counterexamples against the corrected phase.

These are *observations*, not passing tests.  Each probe re-runs one published
counterexample of the independent review and records what the corrected
implementation actually does now.  A probe that is rejected by a contract
error is an observation of the correction, not a claim that a defect
expectation became a green test.

Every probe is synthetic: new generated 4x4 PNGs, small synthetic video
bytes, the real production node classes and the real BridgeOwner behind a
fake native HTTP/provider boundary.  No real media, model, service, GPU,
network, download or ledger is involved.
"""

import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from tools import test_v0_s3_quality_phase as t          # noqa: E402
from tools import v0_s3_quality_phase as q                # noqa: E402

RESULTS = []
ROOT = Path(tempfile.mkdtemp(prefix="lvw-p3b-correction-01-probes-"))


def record(name, **values):
    RESULTS.append(dict(probe=name, **values))


def attempt(name, action):
    """Run one probe action and record its actual outcome."""
    try:
        outcome = action()
        record(name, outcome=outcome)
    except Exception as error:  # noqa: BLE001 - the rejection is the observation
        record(name, outcome="REJECTED", error=type(error).__name__,
               detail=str(error)[:200])


def brief(receipt):
    return {key: receipt.get(key) for key in
            ("decision", "public_submissions", "public_submissions_succeeded",
             "provider_calls_reserved", "provider_calls_observed",
             "provider_calls_observed_known", "test_counts", "storage_unproven",
             "cleanup_unproven", "receipt_persisted", "terminal_status")}


def main():
    # ---- baseline ------------------------------------------------------
    phase, driver, projection = t._prepare(ROOT / "baseline")
    receipt = phase.run()
    record("baseline", **brief(receipt))
    scores = t._scores(receipt, receipt["projection_sha256"])
    artifact_root = phase.directory

    # ---- M06: a cross paired reviewer and session ------------------------
    def cross_pair():
        independence = t._independence(reviewers=[
            {"reviewer_id": "A", "session_id": "SA", "role": "INDEPENDENT_REVIEWER"},
            {"reviewer_id": "B", "session_id": "SB", "role": "INDEPENDENT_REVIEWER"}])
        crossed = copy.deepcopy(scores)
        for score in crossed:
            score.update(reviewer_id="A", session_id="SB")
        result = q.recompute_scores(receipt, artifact_root, crossed, independence=independence)
        return {"aggregate_pass": result["aggregate_pass"]}
    attempt("cross_paired_reviewer_session", cross_pair)

    # ---- M07: a wrong execution raw length ------------------------------
    def wrong_length():
        broken = copy.deepcopy(receipt)
        broken["rows"][0]["raw_bytes"] += 123
        result = q.recompute_scores(broken, artifact_root, scores, independence=t._independence())
        return {"aggregate_pass": result["aggregate_pass"]}
    attempt("execution_raw_length_mismatch", wrong_length)

    # ---- M08: a failed row with critical evidence -----------------------
    def failed_with_critical():
        broken = copy.deepcopy(receipt)
        broken["rows"][0]["execution_status"] = "FAIL"
        broken["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
        scored = copy.deepcopy(scores)
        scored[0]["critical_hallucinations"] = 3
        result = q.recompute_scores(broken, artifact_root, scored, independence=t._independence())
        return {"aggregate_pass": result["aggregate_pass"],
                "total_critical": result["thresholds"]["total_critical_hallucinations"],
                "row_quality_status": result["rows"][0]["quality_status"],
                "row_usable": result["rows"][0]["usable"],
                "row_resolved": result["rows"][0]["resolved"]}
    attempt("failed_row_critical_evidence", failed_with_critical)

    # ---- M08: a known failed row with zero critical ----------------------
    def failed_zero_critical():
        broken = copy.deepcopy(receipt)
        broken["rows"][0]["execution_status"] = "FAIL"
        broken["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
        scored = copy.deepcopy(scores)
        scored[0]["critical_hallucinations"] = 0
        result = q.recompute_scores(broken, artifact_root, scored, independence=t._independence())
        return {"aggregate_pass": result["aggregate_pass"],
                "images_usable": result["thresholds"]["images_usable"],
                "videos_usable": result["thresholds"]["videos_usable"],
                "total_critical": result["thresholds"]["total_critical_hallucinations"],
                "row_resolved": result["rows"][0]["resolved"],
                "row_usable": result["rows"][0]["usable"]}
    attempt("known_failed_independently_scored", failed_zero_critical)

    # ---- M01: a raw persistence failure ---------------------------------
    def raw_failure():
        local, local_driver, _ = t._prepare(ROOT / "writefail")
        original = local._artifact

        def failing(relative, raw):
            if relative.endswith("/raw.txt"):
                raise q.QualityContractError("ARTIFACT_WRITE_FAILED:" + relative)
            return original(relative, raw)

        local._artifact = failing
        result = local.run()
        return {**brief(result),
                "first_error": result["rows"][0]["error_code"],
                "raw_preserved": [row.get("raw_preserved") for row in result["rows"]]}
    attempt("raw_persistence_failure", raw_failure)

    # ---- M03: a source replaced inside the authorize callback -----------
    def source_mutation():
        local, local_driver, _ = t._prepare(ROOT / "sourcecallback")
        sent = []

        def authorize(action, asset):
            if action == "quality_public_submit" and not sent:
                target = local.root / "input" / "synthetic-image-00.png"
                target.write_bytes(t._tiny_png(9))

        def submit(graph):
            sent.append(graph)
            return local_driver.submit(graph)

        local.authorize = authorize
        local_driver.submit = submit
        result = local.run()
        return {**brief(result), "first_error": result["rows"][0]["error_code"], "sent": len(sent)}
    attempt("source_mutation_in_authorize", source_mutation)

    # ---- M05: a submit that fails after the reservation ------------------
    def failed_submit():
        local, local_driver, _ = t._prepare(ROOT / "submitfailure")

        def failing(graph):
            local_driver.submissions += 1
            raise RuntimeError("synthetic transport failure after reservation")

        local_driver.submit = failing
        result = local.run()
        return {**brief(result), "driver_attempts": local_driver.submissions}
    attempt("failed_submit_counter", failed_submit)

    # ---- M04: an ordinary residue exception -----------------------------
    def residue_exception():
        local, local_driver, _ = t._prepare(ROOT / "residueexception")

        def failing():
            raise OSError("synthetic inaccessible snapshot root")

        local_driver.video_snapshot_residue = failing
        result = local.run()
        return {**brief(result), "row_count": len(result["rows"]),
                "cleanup_diagnostics": result["rows"][0]["cleanup_diagnostics"]}
    attempt("residue_exception", residue_exception)

    # ---- M01: the terminal receipt against the total byte cap -----------
    def receipt_total_cap():
        local, local_driver, _ = t._prepare(ROOT / "receipttotal")
        local.directory.mkdir(parents=True, exist_ok=True)
        info = local.directory.lstat()
        local._phase_identity = [info.st_dev, info.st_ino]
        local._artifact_bytes = q.MAX_TOTAL_ARTIFACT_BYTES
        persisted = local._write_receipt({"synthetic": True})
        return {"persisted": persisted, "cap": q.MAX_TOTAL_ARTIFACT_BYTES,
                "accounted": local._artifact_bytes}
    attempt("receipt_total_cap", receipt_total_cap)

    # ---- M02: an artifact ancestor redirect -----------------------------
    def ancestor_redirect():
        local, local_driver, _ = t._prepare(ROOT / "ancestorredirect")
        local.directory.mkdir(parents=True, exist_ok=True)
        info = local.directory.lstat()
        local._phase_identity = [info.st_dev, info.st_ino]
        outside = ROOT / "redirect-target"
        outside.mkdir(exist_ok=True)
        (local.directory / "rows").symlink_to(outside, target_is_directory=True)
        try:
            local._artifact("rows/asset/raw.txt", b"synthetic")
            return {"escaped": (outside / "asset" / "raw.txt").exists()}
        except Exception as error:  # noqa: BLE001
            return {"escaped": (outside / "asset" / "raw.txt").exists(),
                    "rejected": type(error).__name__, "detail": str(error)[:120]}
    attempt("artifact_ancestor_redirect", ancestor_redirect)

    # ---- m01: a non finite release evidence -----------------------------
    def nonfinite_release():
        local, local_driver, _ = t._prepare(ROOT / "nanrelease", failure="release-nan")
        try:
            evidence = local._release_evidence({"asset_id": "probe"})
            return {"accepted": evidence["proven"]}
        except Exception as error:  # noqa: BLE001
            return {"rejected": type(error).__name__, "detail": str(error)[:120]}
    attempt("nonfinite_release", nonfinite_release)

    # ---- M02: a preexisting phase directory ------------------------------
    def existing_directory():
        local, local_driver, _ = t._prepare(ROOT / "existing")
        local.directory.mkdir(parents=True, exist_ok=True)
        result = local.run()
        return {**brief(result),
                "files_written_into_the_old_root": sorted(
                    path.name for path in local.directory.iterdir())}
    attempt("existing_directory", existing_directory)

    return {
        "kind": "S3_P3B_CORRECTION_01_REPLAYED_REVIEW_PROBES",
        "note": ("Observations of the independent review's counterexamples against the "
                 "corrected implementation. A rejected probe is the observation of the "
                 "correction, not a passing test."),
        "results": RESULTS,
        "owned_fixture_root": str(ROOT),
        "own_fixture_cleanup": True,
        "real_execution": False,
        "real_media": False,
        "network": False,
    }


if __name__ == "__main__":
    document = main()
    shutil.rmtree(ROOT, ignore_errors=True)
    print(json.dumps(document, ensure_ascii=False, indent=2))
