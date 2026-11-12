"""Replay the correction-02 review's counterexamples against correction 03.

These are *observations*, not passing tests.  Each probe re-runs one published
counterexample of the independent correction-02 review and records what the
corrected implementation actually does now.  A probe that is rejected by a
contract error is an observation of the correction, not a claim that a defect
expectation became a green test.

The probes are adapted to the corrected architecture: the terminal receipt is
now staged, fsynced and only then published, the evidence validators are
complete and typed, and the send boundary has a final local admission guard.
The original probe files, logs and runners are immutable and are only read
here.

Everything is synthetic: new generated 4x4 PNGs, small synthetic video bytes,
the real production node classes and the real BridgeOwner behind a fake native
HTTP/provider boundary.  No real media, model, service, GPU, network, download
or ledger is involved, and no process is ever hung.
"""

import copy
import json
import os
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
ROOT = Path(tempfile.mkdtemp(prefix="lvw-p3b-correction-03-probes-"))


def record(name, **values):
    RESULTS.append(dict(probe=name, **values))


def attempt(name, action):
    try:
        record(name, outcome=action())
    except Exception as error:  # noqa: BLE001 - the rejection is the observation
        record(name, outcome="REJECTED", error=type(error).__name__,
               detail=str(error)[:200])


def main():
    # ---- baseline --------------------------------------------------------
    phase, driver, projection = t._prepare(ROOT / "baseline")
    receipt = phase.run()
    record("baseline", decision=receipt["decision"],
           public_submissions=receipt["public_submissions"],
           provider_calls_reserved=receipt["provider_calls_reserved"],
           provider_calls_observed=receipt["provider_calls_observed"],
           receipt_persisted=receipt["receipt_persisted"],
           terminal_status=receipt["terminal_status"],
           test_counts=receipt["test_counts"])
    scores = t._scores(receipt, receipt["projection_sha256"])
    artifact_root = phase.directory

    # ---- M01: the persisted receipt states its own final totals -----------
    def persisted_totals():
        stored_bytes = (phase.directory / q.CANONICAL_RECEIPT_NAME).read_bytes()
        stored = json.loads(stored_bytes.decode("utf-8"))
        files = [path for path in phase.directory.rglob("*") if path.is_file()]
        actual_bytes = sum(path.stat().st_size for path in files)
        staged = phase.directory / q.STAGED_RECEIPT_NAME
        return {"stored_receipt_bytes": stored.get("receipt_bytes"),
                "actual_receipt_bytes": len(stored_bytes),
                "stored_files_including_receipt": stored.get("artifact_files_including_receipt"),
                "actual_files": len(files),
                "stored_bytes_including_receipt": stored.get("artifact_bytes_including_receipt"),
                "actual_bytes": actual_bytes,
                "staging_retained": staged.exists(),
                "shares_one_inode": staged.stat().st_ino
                == (phase.directory / q.CANONICAL_RECEIPT_NAME).stat().st_ino,
                "agrees": (stored.get("receipt_bytes") == len(stored_bytes)
                           and stored.get("artifact_files_including_receipt") == len(files)
                           and stored.get("artifact_bytes_including_receipt") == actual_bytes)}
    attempt("persisted_receipt_totals", persisted_totals)

    # ---- M01: a staging failure leaves no authoritative receipt ------------
    def staging_failure():
        local, local_driver, _ = t._prepare(ROOT / "staging-failure")
        original_open = q.os.open
        original_fsync = q.os.fsync
        staged = []

        def opening(path, flags, *args, **kwargs):
            descriptor = original_open(path, flags, *args, **kwargs)
            if str(path) == q.STAGED_RECEIPT_NAME:
                staged.append(descriptor)
            return descriptor

        def failing_fsync(descriptor):
            if staged and descriptor == staged[-1]:
                raise OSError("independent injected staging fsync failure")
            return original_fsync(descriptor)

        q.os.open = opening
        q.os.fsync = failing_fsync
        try:
            result = local.run()
        finally:
            q.os.open = original_open
            q.os.fsync = original_fsync
        canonical = local.directory / q.CANONICAL_RECEIPT_NAME
        staged_path = local.directory / q.STAGED_RECEIPT_NAME
        return {"canonical_exists": canonical.exists(),
                "staging_retained": staged_path.exists(),
                "returned": {key: result.get(key) for key in
                             ("decision", "receipt_persisted", "terminal_status",
                              "storage_unproven", "error_code")},
                "submissions": local_driver.submissions}
    attempt("actual_run_staging_fsync_failure", staging_failure)

    # ---- M08: the unknown evidence probes ----------------------------------
    for name in ("storage_flag_missing", "storage_flag_null", "cleanup_flag_missing",
                 "source_identity_missing", "source_path_foreign", "release_details_missing"):
        def evidence_probe(name=name):
            broken = copy.deepcopy(receipt)
            row = broken["rows"][0]
            if name == "storage_flag_missing":
                broken.pop("storage_unproven")
            elif name == "storage_flag_null":
                broken["storage_unproven"] = None
            elif name == "cleanup_flag_missing":
                broken.pop("cleanup_unproven")
            elif name == "source_identity_missing":
                row["source_evidence"].pop("identity")
            elif name == "source_path_foreign":
                row["source_evidence"]["path"] = "/foreign/not-the-bound-input"
            else:
                row["release_evidence"] = {"proven": True, "model_inventory_empty": True}
            result = q.recompute_scores(broken, artifact_root, scores,
                                        independence=t._independence())
            return {"aggregate_pass": result["aggregate_pass"],
                    "row_usable": result["rows"][0]["usable"],
                    "row_resolved": result["rows"][0]["resolved"],
                    "row_reason": result["rows"][0]["reason"]}
        attempt(name, evidence_probe)

    # ---- M08: a complete known failure stays resolved but not usable -------
    def known_failed_critical():
        broken = copy.deepcopy(receipt)
        broken["rows"][0]["execution_status"] = "FAIL"
        broken["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
        scored = copy.deepcopy(scores)
        scored[0]["critical_hallucinations"] = 3
        result = q.recompute_scores(broken, artifact_root, scored,
                                    independence=t._independence())
        return {"aggregate_pass": result["aggregate_pass"],
                "row_quality_status": result["rows"][0]["quality_status"],
                "row_usable": result["rows"][0]["usable"],
                "row_resolved": result["rows"][0]["resolved"],
                "row_critical": result["rows"][0]["critical_hallucinations"],
                "total_critical": result["thresholds"]["total_critical_hallucinations"]}
    attempt("known_failed_critical3", known_failed_critical)

    # ---- NM01: the proof expires or is diminished at the send boundary ------
    for name in ("proof_expires_before_first_send", "proof_diminishes_before_first_send"):
        def proof_probe(name=name):
            local, local_driver, _ = t._prepare(ROOT / name)
            if name == "proof_expires_before_first_send":
                local.parent_budget["expires_monotonic"] = 2.0

            def authorize(action, subject):
                if action == "quality_public_submit":
                    if name == "proof_expires_before_first_send":
                        local.clock.now = 2.0
                    else:
                        local.parent_budget["action_capacity"] = 0

            local.authorize = authorize
            result = local.run()
            return {"submissions": local_driver.submissions, "decision": result["decision"],
                    "error": result.get("error_code"), "rows": len(result["rows"]),
                    "counts": result["test_counts"]}
        attempt(name, proof_probe)

    # ---- NM02: the cooperative phase deadline before the send --------------
    def cooperative_deadline():
        local, local_driver, _ = t._prepare(ROOT / "phase-deadline")
        local.parent_budget["expires_monotonic"] = 20000.0
        load = local._load_workflows

        def load_near_deadline():
            result = load()
            local.clock.now = 10799.0
            return result

        local._load_workflows = load_near_deadline
        events = []

        def authorize(action, subject):
            if action == "quality_public_submit":
                local.clock.now += 2.0
                events.append({"action": action, "returned_at": local.clock.now,
                               "phase_deadline": local._phase_deadline})

        local.authorize = authorize
        result = local.run()
        return {"events": events, "submissions": local_driver.submissions,
                "first_error": result["rows"][0]["error_code"],
                "decision": result["decision"], "counts": result["test_counts"],
                "hard_timing_blocker": result["hard_timing_blocker"]}
    attempt("cooperative_phase_deadline_before_send", cooperative_deadline)

    # ---- NM02: a non finite or boolean clock -------------------------------
    for name, value in (("nonfinite", float("nan")), ("boolean", True)):
        def clock_probe(value=value):
            local, local_driver, _ = t._prepare(ROOT / ("clock-" + name))
            local.clock = lambda: value
            result = local.run()
            return {"submissions": local_driver.submissions, "rows": len(result["rows"]),
                    "error": result.get("error_code")}
        attempt("clock_" + name, clock_probe)

    # ---- M01: the real caps, exact and one over ----------------------------
    for bound in ("artifact", "total", "files"):
        for over in (0, 1):
            def receipt_cap(bound=bound, over=over):
                local, local_driver, _ = t._prepare(ROOT / ("actual-cap-" + bound + str(over)))
                local._open_owned_directories()
                try:
                    document = q.receipt_document(
                        {"synthetic": True, "receipt_persisted": True,
                         "receipt_persistence_error": None,
                         "terminal_status": "TERMINAL_RECEIPT_PERSISTED"})
                    if bound == "artifact":
                        q.MAX_ARTIFACT_BYTES = q.MAX_ARTIFACT_BYTES + over
                    elif bound == "total":
                        q.MAX_TOTAL_ARTIFACT_BYTES = q.MAX_TOTAL_ARTIFACT_BYTES + over
                    else:
                        q.MAX_ARTIFACT_FILES = q.MAX_ARTIFACT_FILES + over
                    raw, _ = local._serialized_receipt(document)
                    if bound == "artifact":
                        q.MAX_ARTIFACT_BYTES = len(raw) - over
                    elif bound == "total":
                        q.MAX_TOTAL_ARTIFACT_BYTES = local._artifact_bytes + 2 * len(raw) - over
                    else:
                        q.MAX_ARTIFACT_FILES = local._artifact_files + 2 - over
                    persisted = local._write_receipt(document)
                    return {"persisted": persisted,
                            "error": document.get("receipt_persistence_error"),
                            "limits": [q.MAX_ARTIFACT_BYTES, q.MAX_TOTAL_ARTIFACT_BYTES,
                                       q.MAX_ARTIFACT_FILES]}
                finally:
                    local._close_owned_directories()
                    q.MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
                    q.MAX_TOTAL_ARTIFACT_BYTES = 128 * 1024 * 1024
                    q.MAX_ARTIFACT_FILES = 256
            attempt("actual_" + bound + ("_over" if over else "_exact"), receipt_cap)

    # ---- M01: a replay cannot overwrite the retained evidence ---------------
    def receipt_replay():
        local, local_driver, _ = t._prepare(ROOT / "receipt-replay")
        local._open_owned_directories()
        try:
            document = q.receipt_document({"synthetic": True})
            first = local._write_receipt(document)
            staged = local.directory / q.STAGED_RECEIPT_NAME
            before = staged.read_bytes() if staged.exists() else b""
            second = local._write_receipt({"synthetic": True, "another": True})
            after = staged.read_bytes() if staged.exists() else b""
            return {"first_persisted": first, "replay_persisted": second,
                    "replay_error": document.get("receipt_persistence_error"),
                    "original_bytes_unchanged": before == after}
        finally:
            local._close_owned_directories()
    attempt("receipt_replay_cannot_overwrite", receipt_replay)

    return {
        "kind": "S3_P3B_CORRECTION_03_REPLAYED_CORRECTION02_PROBES",
        "note": ("Observations of the correction-02 review's counterexamples against the "
                 "corrected implementation. A rejected probe is the observation of the "
                 "correction, not a passing test. The original probe files are immutable "
                 "and were only read."),
        "results": RESULTS,
        "owned_fixture_root": str(ROOT),
        "own_fixture_cleanup": True,
        "real_execution": False,
        "real_media": False,
        "network": False,
        "hung_process": False,
    }


if __name__ == "__main__":
    document = main()
    shutil.rmtree(ROOT, ignore_errors=True)
    print(json.dumps(document, ensure_ascii=False, indent=2))
