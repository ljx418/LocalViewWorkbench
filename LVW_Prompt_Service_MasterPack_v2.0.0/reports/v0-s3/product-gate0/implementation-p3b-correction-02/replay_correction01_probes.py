"""Replay the correction-01 review's counterexamples against correction 02.

These are *observations*, not passing tests.  Each probe re-runs one published
counterexample of the independent correction-01 review and records what the
corrected implementation actually does now.  A probe that is rejected by a
contract error is an observation of the correction, not a claim that a defect
expectation became a green test.

The probes are adapted to the new strict internal shapes: the typed parent
capacity proof and the per row evidence validation.  The original probe
files, logs and runners are immutable and are only read here.

Everything is synthetic: new generated 4x4 PNGs, small synthetic video
bytes, the real production node classes and the real BridgeOwner behind a
fake native HTTP/provider boundary.  No real media, model, service, GPU,
network, download or ledger is involved, and no process is ever hung.
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
ROOT = Path(tempfile.mkdtemp(prefix="lvw-p3b-correction-02-probes-"))


def record(name, **values):
    RESULTS.append(dict(probe=name, **values))


def attempt(name, action):
    try:
        record(name, outcome=action())
    except Exception as error:  # noqa: BLE001 - the rejection is the observation
        record(name, outcome="REJECTED", error=type(error).__name__,
               detail=str(error)[:200])


def brief(receipt):
    return {key: receipt.get(key) for key in
            ("decision", "public_submissions", "public_submissions_succeeded",
             "provider_calls_reserved", "provider_calls_observed",
             "provider_calls_observed_known", "test_counts", "storage_unproven",
             "cleanup_unproven", "receipt_persisted", "terminal_status",
             "error_code")}


def main():
    # ---- baseline --------------------------------------------------------
    phase, driver, projection = t._prepare(ROOT / "baseline")
    receipt = phase.run()
    record("baseline", **brief(receipt))
    scores = t._scores(receipt, receipt["projection_sha256"])
    artifact_root = phase.directory

    # ---- M01: the persisted receipt states its own final totals -----------
    def persisted_totals():
        stored_path = phase.directory / "qd-receipt.json"
        stored_bytes = stored_path.read_bytes()
        stored = json.loads(stored_bytes.decode("utf-8"))
        files = [path for path in phase.directory.rglob("*") if path.is_file()]
        actual_bytes = sum(path.stat().st_size for path in files)
        return {
            "stored_receipt_bytes": stored.get("receipt_bytes"),
            "actual_receipt_bytes": len(stored_bytes),
            "stored_files_including_receipt": stored.get("artifact_files_including_receipt"),
            "actual_files": len(files),
            "stored_bytes_including_receipt": stored.get("artifact_bytes_including_receipt"),
            "actual_bytes": actual_bytes,
            "agrees": (stored.get("receipt_bytes") == len(stored_bytes)
                       and stored.get("artifact_files_including_receipt") == len(files)
                       and stored.get("artifact_bytes_including_receipt") == actual_bytes),
        }
    attempt("persisted_receipt_totals", persisted_totals)

    # ---- M08: unknown evidence on every row -------------------------------
    for kind in ("PASS_cleanup_unknown", "known_FAIL_storage_unknown",
                 "known_FAIL_source_unknown"):
        def evidence_probe(kind=kind):
            broken = copy.deepcopy(receipt)
            if kind == "PASS_cleanup_unknown":
                broken["rows"][0]["release_evidence"] = None
            else:
                broken["rows"][0]["execution_status"] = "FAIL"
                broken["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
                if "storage" in kind:
                    broken["storage_unproven"] = True
                    broken["rows"][0]["storage_unproven"] = True
                else:
                    broken["rows"][0]["source_evidence"] = None
            result = q.recompute_scores(broken, artifact_root, scores,
                                         independence=t._independence())
            row = result["rows"][0]
            return {"aggregate_pass": result["aggregate_pass"],
                    "row_usable": row["usable"], "row_resolved": row["resolved"],
                    "row_reason": row["reason"]}
        attempt(kind, evidence_probe)

    # ---- M02: a temp ancestor redirect inside a controlled callback --------
    def temp_ancestor():
        local, local_driver, _ = t._prepare(ROOT / "tempancestor")
        once = []

        def replace_temp(action, subject):
            if action == "quality_row_begin" and not once:
                once.append(True)
                (local.root / "temp").rename(local.root / "old-temp")
                (local.root / "temp").symlink_to(local.root / "old-temp",
                                                 target_is_directory=True)

        local.authorize = replace_temp
        result = local.run()
        old = local.root / "old-temp"
        return {"submissions": local_driver.submissions, "decision": result["decision"],
                "files_in_the_old_directory": [str(path.relative_to(old))
                                               for path in old.rglob("*") if path.is_file()],
                "receipt_persisted": result["receipt_persisted"]}
    attempt("temp_ancestor_callback_redirect", temp_ancestor)

    # ---- M02: a deterministic open interposition ----------------------------
    def open_race():
        local, local_driver, _ = t._prepare(ROOT / "openrace")
        foreign = ROOT / "openrace-foreign"
        foreign.mkdir()
        original_open = q.os.open
        swapped = []

        def racing_open(path, flags, *args, **kwargs):
            if str(path) == "rows" and flags & os.O_DIRECTORY and not swapped:
                swapped.append(True)
                (local.directory / "rows").rename(local.directory / "rows-original")
                (local.directory / "rows").symlink_to(foreign, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        q.os.open = racing_open
        try:
            result = local.run()
        finally:
            q.os.open = original_open
        return {"foreign_files": [str(path.relative_to(foreign))
                                  for path in foreign.rglob("*") if path.is_file()],
                "submissions": local_driver.submissions,
                "first_error": result["rows"][0]["error_code"]}
    attempt("artifact_open_ancestor_race", open_race)

    # ---- M02: an initial temp symlink --------------------------------------
    def initial_redirect():
        local, local_driver, _ = t._prepare(ROOT / "initialredirect")
        foreign = ROOT / "initial-foreign"
        foreign.mkdir()
        (local.root / "temp").rmdir()
        (local.root / "temp").symlink_to(foreign, target_is_directory=True)
        result = local.run()
        return {"foreign_entries": [str(path.relative_to(foreign))
                                    for path in foreign.rglob("*")],
                "submissions": local_driver.submissions,
                "error": result.get("error_code")}
    attempt("initial_temp_redirect", initial_redirect)

    # ---- M02: a preexisting phase directory --------------------------------
    def existing_directory():
        local, local_driver, _ = t._prepare(ROOT / "existing")
        (local.directory).mkdir(parents=True, exist_ok=True)
        result = local.run()
        return {**brief(result),
                "files_written_into_the_old_root": sorted(
                    path.name for path in local.directory.iterdir())}
    attempt("existing_directory", existing_directory)

    # ---- NM01: a proof for another identity or a stale proof ---------------
    for name, overrides in (
            ("wrong_identity", {"run_id": "WRONG", "candidate_sha": "0" * 40,
                                "authorization_sha256": "0" * 64}),
            ("stale", {"issued_monotonic": -99999.0, "expires_monotonic": -1.0}),
            ("diminished", {"action_capacity": 10}),
            ("non_finite", {"issued_monotonic": float("nan"), "expires_monotonic": 10.0}),
    ):
        def proof_probe(overrides=overrides):
            local, local_driver, _ = t._prepare(
                ROOT / ("proof-" + name), parent_budget=t._parent_proof(t.FakeClock(), **overrides))
            result = local.run()
            return {"submissions": local_driver.submissions, "decision": result["decision"],
                    "error": result.get("error_code"),
                    "rows": len(result["rows"])}
        attempt("parent_proof_" + name, proof_probe)

    # ---- NM02: a callback that returns only after the phase deadline -------
    def post_return_elapsed():
        local, local_driver, _ = t._prepare(ROOT / "callbackdeadline")
        events = []

        def delayed(action, subject):
            if action == "quality_public_submit":
                local.clock.now += q.PHASE_TIMEOUT_SECONDS + 1
                events.append("callback_returned_after_phase_deadline")

        local.authorize = delayed
        result = local.run()
        return {"events": events, "submissions": local_driver.submissions,
                "error": result["rows"][0]["error_code"],
                "hard_timing_blocker": result.get("hard_timing_blocker"),
                "synchronous_callables_preemptively_bounded":
                    result.get("timing_assurance", {}).get("synchronous_callables_preemptively_bounded")}
    attempt("post_return_elapsed_only", post_return_elapsed)

    # ---- NM02: a decreasing phase clock -------------------------------------
    def decreasing_clock():
        local, local_driver, _ = t._prepare(ROOT / "decreasingclock")
        counter = [0]

        def clock():
            counter[0] += 1
            return 100000.0 - counter[0] * 0.01

        local.clock = clock
        try:
            result = local.run()
            return {"submissions": local_driver.submissions, "decision": result["decision"],
                    "error": result.get("error_code")}
        except Exception as error:  # noqa: BLE001
            return {"rejected": type(error).__name__, "detail": str(error)[:160],
                    "submissions": local_driver.submissions}
    attempt("decreasing_phase_clock", decreasing_clock)

    # ---- M01: the receipt caps, exact and one over --------------------------
    for bound in ("artifact", "total", "files"):
        for over in (0, 1):
            def receipt_cap(bound=bound, over=over):
                local, local_driver, _ = t._prepare(ROOT / ("receipt-" + bound + str(over)))
                local._open_owned_directories()
                try:
                    local._artifact("filler.bin", b"synthetic filler")
                    document = {"synthetic": True, "receipt_persisted": True,
                                "receipt_persistence_error": None,
                                "terminal_status": "TERMINAL_RECEIPT_PERSISTED"}
                    raw, _ = local._serialized_receipt(document)
                    if bound == "artifact":
                        q.MAX_ARTIFACT_BYTES = len(raw) - over
                    elif bound == "total":
                        q.MAX_TOTAL_ARTIFACT_BYTES = local._artifact_bytes + len(raw) - over
                    else:
                        q.MAX_ARTIFACT_FILES = local._artifact_files + 1 - over
                    persisted = local._write_receipt(document)
                    return {"persisted": persisted,
                            "error": document.get("receipt_persistence_error")}
                finally:
                    local._close_owned_directories()
                    if bound == "artifact":
                        q.MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
                    elif bound == "total":
                        q.MAX_TOTAL_ARTIFACT_BYTES = 128 * 1024 * 1024
                    else:
                        q.MAX_ARTIFACT_FILES = 256
            attempt("receipt_" + bound + ("_over" if over else "_exact"), receipt_cap)

    return {
        "kind": "S3_P3B_CORRECTION_02_REPLAYED_CORRECTION01_PROBES",
        "note": ("Observations of the correction-01 review's counterexamples against the "
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
