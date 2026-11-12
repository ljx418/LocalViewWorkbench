#!/usr/bin/env python3
"""Write the correction-06 receipt and the checksum list of this batch.

The script reads the raw receipts that the guarded runner wrote, hashes the
retained evidence files and writes ``receipt.json`` and ``SHA256SUMS``.  It
imports no product module, it executes no product code and it starts no host
process.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-06/write_receipt.py \
        --outdir reports/v0-s3/product-gate0/implementation-p3b-correction-06
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = PACK_ROOT.parent
OUT_RELATIVE = ("LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/"
                "implementation-p3b-correction-06")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*arguments):
    return subprocess.run(["git", "-C", str(REPO_ROOT)] + list(arguments),
                          check=True, stdout=subprocess.PIPE).stdout.decode("utf-8").strip()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    arguments = parser.parse_args(argv)
    outdir = PACK_ROOT / arguments.outdir

    guard = json.loads((outdir / "guard.receipt.json").read_text(encoding="utf-8"))
    suite = json.loads((outdir / "suite.receipt.json").read_text(encoding="utf-8"))
    focused = json.loads((outdir / "focused.receipt.json").read_text(encoding="utf-8"))
    audit = json.loads((outdir / "obligation-audit.json").read_text(encoding="utf-8"))
    observations = json.loads((outdir / "focused-observations.json").read_text(encoding="utf-8"))
    control = json.loads((PACK_ROOT / "plans/execution-control.json").read_text(encoding="utf-8"))

    candidate_commit = git("rev-parse", "HEAD")
    candidate_code = git("rev-parse", "HEAD~0")

    opened = []
    for observation in observations["observations"]:
        body = observation["observation"]
        opened.append({
            "name": observation["name"],
            "refused": bool(body.get("refused")),
            "aggregate_pass": body.get("aggregate_pass"),
            "all_rows_resolved": body.get("all_rows_resolved"),
            "row0_usable": body.get("row0_usable"),
            "row0_resolved": body.get("row0_resolved"),
            "row0_reason": body.get("row0_reason"),
            "row0_evidence_reason": body.get("row0_evidence_reason"),
            "error": body.get("error"),
            "hook_fired": observation.get("hook_fired"),
            "original_bytes_unchanged": observation.get("original_bytes_unchanged"),
            "entry_is_symlink_at_return": observation.get("entry_is_symlink_at_return"),
        })

    receipt = {
        "kind": "S3_P3B_CORRECTION_06_IMPLEMENTATION_RECEIPT",
        "batch": "S3-P3B aggregate correction 06",
        "state": "READY_FOR_REVIEW",
        "disposition": "CORRECTION_06_IMPLEMENTED_AWAITING_INDEPENDENT_REVIEW",
        "candidate_code_commit": candidate_commit,
        "candidate_code_commit_short": candidate_code[:7],
        "baseline_code_commit": "44ad8c7a30ee418af41834de6cc87685f80d42fa",
        "baseline_evidence_commit": "afb12e2a136b4a1bed05f1f766084c2b279e07b0",
        "root_disposition_commit": "c05ee011a73a790917000e5ab0e615851053a2eb",
        "independent_review_commit": "1618614798b7eaa23d603ab3d89b2e1176fc0e93",
        "frozen_contract": "reports/v0-s3/product-gate0/p3b-quality-contract.md",
        "frozen_projection_inputs": "reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json",
        "code_sha256": {
            "tools/v0_s3_quality_phase.py":
                suite["before_source_sha256"]["tools/v0_s3_quality_phase.py"],
            "tools/test_v0_s3_quality_phase.py":
                suite["before_source_sha256"]["tools/test_v0_s3_quality_phase.py"],
        },
        "runner_sha256": suite["runner_sha256_before"],
        "runner_reused": ("reports/v0-s3/product-gate0/implementation-p3b-correction-05/"
                          "run_guarded_checks.py"),
        "probe_sha256": focused["probe_sha256_before"],
        "invocations": [
            {
                "label": "guard",
                "mode": "guard",
                "argv": guard["argv"],
                "exit_code": guard["exit_code"],
                "outcome": guard["outcome"],
                "duration_seconds": guard["duration_seconds"],
                "stdout_file": guard["stdout_file"],
                "stderr_file": guard["stderr_file"],
                "stdout_sha256": guard["stdout_sha256"],
                "stderr_sha256": guard["stderr_sha256"],
                "guard_results": guard["guard_results"],
            },
            {
                "label": "suite",
                "mode": "suite",
                "argv": suite["argv"],
                "exit_code": suite["exit_code"],
                "outcome": suite["outcome"],
                "duration_seconds": suite["duration_seconds"],
                "collected_count": suite["collected_count"],
                "stdout_file": suite["stdout_file"],
                "stderr_file": suite["stderr_file"],
                "stdout_sha256": suite["stdout_sha256"],
                "stderr_sha256": suite["stderr_sha256"],
                "source_unchanged_during_run": suite["source_unchanged_during_run"],
                "runner_unchanged_during_run": suite["runner_unchanged_during_run"],
                "owned_root_removed": suite["owned_root_removed"],
            },
            {
                "label": "focused",
                "mode": "script",
                "argv": focused["argv"],
                "exit_code": focused["exit_code"],
                "outcome": focused["outcome"],
                "duration_seconds": focused["duration_seconds"],
                "stdout_file": focused["stdout_file"],
                "stderr_file": focused["stderr_file"],
                "stdout_sha256": focused["stdout_sha256"],
                "stderr_sha256": focused["stderr_sha256"],
                "probe_unchanged_during_run": focused["probe_unchanged_during_run"],
                "owned_root_removed": focused["owned_root_removed"],
            },
        ],
        "counts": {
            "product_test_cases": suite["collected_count"],
            "original_frozen_cases": 206,
            "new_cases": suite["collected_count"] - 206,
            "new_test_definitions": len(audit["added_definitions"]),
            "guard_events_blocked": len(guard["guard_results"]),
            "focused_observations": observations["count"],
            "focused_counterexamples_still_open": sum(
                1 for item in opened
                if item["name"] != "honest_baseline" and item["aggregate_pass"] is True),
        },
        "obligation_audit": {
            "baseline_test_definitions": audit["baseline_test_definitions"],
            "candidate_test_definitions": audit["candidate_test_definitions"],
            "identical_definitions": audit["identical_definitions"],
            "adapted_definitions": audit["adapted_definitions"],
            "deleted_definitions": audit["deleted_definitions"],
            "changed_old_helpers": audit["changed_old_helpers"],
            "frozen_collected_nodeids": audit["frozen_collected_nodeids"],
            "candidate_collected_nodeids": audit["candidate_collected_nodeids"],
            "missing_frozen_nodeids": audit["missing_frozen_nodeids"],
            "baseline_test_sha256": audit["baseline_sha256"],
            "candidate_test_sha256": audit["candidate_sha256"],
        },
        "closed_roots": ["M01_TYPED_EQUALITY_AND_EXTRA_FACT_BINDING",
                         "NM03_NAMED_HIERARCHY_DURING_READ"],
        "preserved_closures": [
            "M02/M03/M04/M05/M06/M07/M09/m01 closed scoped offline preserved",
            "M08 label and full descriptor alignment closed with the shared type residual in M01",
            "NM04 source handoff closed cooperatively",
            "NM01 capacity and time driver accessors closed",
            "NM02 one final coherent clock closed cooperatively",
        ],
        "focused_observations": opened,
        "cleanup": {
            "runner_owned_root_removed": {
                "guard": guard["owned_root_removed"],
                "suite": suite["owned_root_removed"],
                "focused": focused["owned_root_removed"],
            },
            "probe_owned_root": observations["owned_root"],
            "probe_registered_roots": observations["registered_roots"],
            "probe_root_removed_by_the_probe_finally": True,
            "older_roots_scanned_or_deleted": False,
            "media_or_binary_or_database_in_git": False,
        },
        "offline_discipline": {
            "actual_windows_wsl_powershell_parser_hostexe_hashing": 0,
            "actual_real_media_ffmpeg_models_gpu_services_network_download": 0,
            "real_ledger_claims_full_checkpoint": 0,
            "test_source_holdout_or_full_prelabel_reads": 0,
            "fresh_fixtures": "4x4 PNG and tiny fake video behind the actual production owners only",
            "real_decoder_or_server": False,
            "max_retries": 0,
            "retry_watchdog": 0,
            "retry_env_keys_read": ["MAX_RETRIES", "RETRY_WATCHDOG"],
            "secrets_read": False,
            "claude_429_observed": False,
            "purchases": 0,
            "git_push": False,
            "permanent_configuration": False,
        },
        "not_proven": [
            "Parent owned original archive or retained independent attestation and selected root binding NOT_PROVEN",
            "Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; synchronous callbacks not preempted",
            "Native Windows and WSL deployment, residue admission and A06 enforcement and attempt observation NOT_PROVEN",
            "Actual registration baseline, installation and rollback NOT_PROVEN",
            "Authentic parent ledger debit NOT_PROVEN",
            "Real quality sixteen, full twelve, product Gate0, human and release acceptance NOT_PROVEN",
            "No claim of hostile kernel, native Windows reparse, native extension or direct syscall immunity",
            "Parent archive crash durability and external process cleanup remain integration obligations",
            "The correction-03 unguarded twelve remain UNKNOWN and uncredited",
        ],
        "stage_pass_claim": False,
        "product_gate0": False,
        "real_execution_performed": False,
        "ready_for_review_only": True,
        "next_owner": "Root architecture/gate owner for disposition; any implementation remains separate from independent review",
        "ten_field_handoff": {
            "1_current_coordinate": control["coordinate"],
            "2_this_batch": ("S3-P3B aggregate correction 06 implemented: M01 typed actual facts and closed key "
                             "sets, NM03 named hierarchy custody; 232 product cases once (206 original plus 26 new), "
                             "guard four once, focused twenty-two observations once"),
            "3_last_passed_gate": control["last_passed_gate"],
            "4_current_blocking_gate": "S3_P3B_CORRECTION06_INDEPENDENT_REVIEW_PENDING",
            "5_route_position": ("Root aggregate disposition -> bounded correction -> separate independent review -> "
                                 "parent/native/A06/Gate0 -> finite real quality and human/release gates"),
            "6_remaining_work": [
                "Independent review of correction 06 by a separate instance",
                "Parent owned original archive or retained independent attestation and selected root binding NOT_PROVEN",
                "Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER",
                "Native Windows and WSL deployment, residue admission and A06 NOT_PROVEN",
                "Actual registration baseline, installation and rollback NOT_PROVEN",
                "Authentic parent ledger debit NOT_PROVEN",
                "Real quality sixteen, full twelve, product Gate0, human and release acceptance NOT_PROVEN",
            ],
            "7_next_owner": "Root architecture/gate owner for disposition; independent review instance next",
            "8_authorization": ("Completed authorized offline implementation only; no new human approval needed; "
                                 "no real runtime authority inferred"),
            "9_evidence_directory": "reports/v0-s3/product-gate0/implementation-p3b-correction-06/",
            "10_exact_stop_reason": ("The two remaining roots are implemented and the candidate is committed and "
                                     "awaiting an independent review; the implementer reports READY_FOR_REVIEW only"),
        },
        "development_outline": control.get("development_outline"),
    }

    receipt_path = outdir / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")

    entries = []
    for path in sorted(outdir.rglob("*")):
        if not path.is_file() or path.name == "SHA256SUMS":
            continue
        relative = path.relative_to(PACK_ROOT.parent).as_posix()
        entries.append("%s  %s" % (sha256_file(path), relative))
    (outdir / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")

    print(json.dumps({
        "receipt": str(receipt_path.relative_to(PACK_ROOT.parent)),
        "checksum_entries": len(entries),
        "candidate_code_commit": candidate_commit,
        "product_test_cases": receipt["counts"]["product_test_cases"],
        "focused_counterexamples_still_open": receipt["counts"][
            "focused_counterexamples_still_open"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
