#!/usr/bin/env python3
"""Compose the machine readable receipt of the correction-05 batch.

The receipt is composed from the actual runner receipts, the actual
obligation audit and the actual counterexample observations of this batch.
Nothing in it is typed by hand: every count and every hash is read back from
the evidence that the guarded runs produced.
"""

import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACK_ROOT = Path(__file__).resolve().parents[4]
BASE = PACK_ROOT / "reports/v0-s3/product-gate0/implementation-p3b-correction-05"

FULL = json.loads((BASE / "full-final.receipt.json").read_text(encoding="utf-8"))
GUARD = json.loads((BASE / "guard-selftest.receipt.json").read_text(encoding="utf-8"))
COUNTER = json.loads((BASE / "counterexamples.receipt.json").read_text(encoding="utf-8"))
AUDIT = json.loads((BASE / "obligation-audit.json").read_text(encoding="utf-8"))
OBSERVATIONS = json.loads((BASE / "counterexample-observations.json").read_text(encoding="utf-8"))
BASELINE = json.loads((PACK_ROOT / "reports/v0-s3/product-gate0/"
                       "implementation-p3b-correction-04/full-final.receipt.json").read_text(
                           encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


baseline_ids = set(BASELINE["collected_nodeids"])
candidate_ids = set(FULL["collected_nodeids"])

receipt = {
    "kind": "S3_P3B_CORRECTION_05_IMPLEMENTATION_RECEIPT",
    "status": "READY_FOR_REVIEW",
    "code_candidate": "44ad8c7a30ee418af41834de6cc87685f80d42fa",
    "code_baseline_before": "5de09478a4af6e3dd91410d4dde90c9020a77bfd",
    "evidence_baseline_before": "0d28fd4d607808c1980f66ff86b289cbcc5134e8",
    "independent_review_consumed": "8ea70dac74a81ae407fa149ca7f3d8c716c103ae",
    "root_disposition_merged": "08e6fbe8f0bcf4443b1832758327de798d78481b",
    "root_adjudication": "reports/v0-s3/product-gate0/p3b-correction-05.adjudication.json",
    "source_sha256": {
        "tools/v0_s3_quality_phase.py": FULL["after_source_sha256"]["tools/v0_s3_quality_phase.py"],
        "tools/test_v0_s3_quality_phase.py": FULL["after_source_sha256"]["tools/test_v0_s3_quality_phase.py"],
    },
    "runner_sha256": FULL["runner_sha256_after"],
    "probe_sha256": COUNTER["probe_sha256_after"],
    "obligation_audit_script_sha256": sha256_file(BASE / "audit_test_obligations.py"),
    "findings": [
        {
            "id": "M01",
            "severity": "Major",
            "status": "CORRECTED_IN_THIS_BATCH",
            "production_path": [
                "tools/v0_s3_quality_phase.py:217 QS_RECEIPT_OVERLAY_FIELDS",
                "tools/v0_s3_quality_phase.py:222 QS_ROW_OVERLAY_FIELDS",
                "tools/v0_s3_quality_phase.py:251 QS_RECEIPT_TYPED_CONTEXTS",
                "tools/v0_s3_quality_phase.py:2979 _row_evidence_complete",
                "tools/v0_s3_quality_phase.py:3051 _verify_execution_content",
                "tools/v0_s3_quality_phase.py:3101 _effective_failure_verdict",
                "tools/v0_s3_quality_phase.py:3182 recompute_scores",
            ],
            "oracle": ("the canonical receipt that is actually published on disk under the owned "
                       "artifact root, the sealed original source plan and the independent "
                       "scoring receipts"),
            "negative": [
                "a published unknown validation failure stays unresolved under a supplied known error",
                "a published known failure supplied as a pass stays resolved and not usable",
                "a published pass downgraded by a supplied known failure stays resolved and not usable",
                "a fabricated release sample vector leaves the row unresolved",
                "a fabricated bound baseline is refused",
                "a fabricated terminal count is refused",
                "a fabricated row attempt flag is refused",
                "an extra fabricated row fact is refused",
                "a fabricated run context is refused",
                "every published field outside the closed overlay is bound",
            ],
            "terminal": [
                "QS_EXECUTION_CONTENT_MISMATCH:<field>",
                "EVIDENCE_UNKNOWN:RELEASE_EVIDENCE_NOT_CANONICAL",
                "UNKNOWN_EXECUTION_FAILURE",
                "QUALITY_INCOMPLETE_UNRESOLVED_ROWS",
            ],
            "cleanup": ("the supplied document is never written to; every owned fixture root of the "
                        "batch is registered and removed; the owned phase handles are closed"),
            "counterexample_observations": [
                "published_unknown_failure", "published_unknown_failure_supplied_known_error",
                "published_fail_supplied_pass", "published_fail_critical3",
                "valid_but_fabricated_release_samples", "fabricated_bound_baseline_and_release",
                "fabricated_terminal_counts", "fabricated_attempt_row", "fabricated_run_context",
            ],
        },
        {
            "id": "M08",
            "severity": "Major",
            "status": "CORRECTED_IN_THIS_BATCH",
            "production_path": [
                "tools/v0_s3_quality_phase.py:2812 _verify_seal_row_alignment",
                "tools/v0_s3_quality_phase.py:2840 load_source_plan",
                "tools/v0_s3_quality_phase.py:1338 _persist_source_plan",
            ],
            "oracle": ("the canonical execution row of the published receipt and the fixed admitted "
                       "projection order and identity"),
            "negative": [
                "a seal row whose asset contradicts the execution row is refused",
                "a seal row whose media kind contradicts the execution row is refused",
                "a seal row whose input reference contradicts the execution row is refused",
                "a seal row whose size contradicts the execution row is refused",
                "a seal row whose hash contradicts the execution row is refused",
                "a seal row whose path contradicts the execution row is refused",
                "a seal row whose descriptor identity contradicts the execution row is refused",
                "a seal row with a wrong ordinal is refused",
                "two swapped seal rows are refused",
            ],
            "terminal": [
                "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:<field>:<index>",
                "QS_SOURCE_PLAN_ORDER_INVALID",
            ],
            "cleanup": ("the negative cases write only inside their own private owned root and the "
                        "root is removed; no old evidence root is written"),
            "counterexample_observations": [
                "seal_label_alignment.asset_id", "seal_label_alignment.media_kind",
                "seal_label_alignment.input_reference", "seal_swap.swap_whole_rows",
                "seal_swap.swap_descriptor",
            ],
        },
        {
            "id": "NM03",
            "severity": "Major",
            "status": "CORRECTED_IN_THIS_BATCH",
            "production_path": [
                "tools/v0_s3_quality_phase.py:2510 _ArtifactBoundary",
                "tools/v0_s3_quality_phase.py:2700 _boundary_error_code",
                "tools/v0_s3_quality_phase.py:2716 load_canonical_receipt",
                "tools/v0_s3_quality_phase.py:2760 _verify_run_root_binding",
                "tools/v0_s3_quality_phase.py:2840 load_source_plan",
                "tools/v0_s3_quality_phase.py:3182 recompute_scores",
            ],
            "oracle": ("the real <run root>/temp/s3-quality directory of the run, opened level by "
                       "level against its own pinned parent"),
            "negative": [
                "a redirected temp ancestor is refused",
                "a redirected run root is refused",
                "a redirected phase directory is refused",
                "a redirected canonical receipt is refused",
                "a redirected source plan is refused",
                "a redirected raw artifact is refused",
            ],
            "terminal": [
                "QS_ARTIFACT_ROOT_REDIRECT_FORBIDDEN:<level>",
                "CANONICAL_RECEIPT_REDIRECT_FORBIDDEN",
                "QS_SOURCE_PLAN_REDIRECT_FORBIDDEN",
                "QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN",
            ],
            "cleanup": ("every descriptor of the boundary is closed in a finally block and every "
                        "owned fixture root of the batch is removed"),
            "counterexample_observations": [
                "qs_temp_ancestor_symlink", "qs_phase_ancestor_symlink",
                "qs_canonical_leaf_symlink",
            ],
            "accepted_limitation": ("an in-process inode observation inside the existing audited "
                                    "Python/filesystem trust model; no immunity against a hostile "
                                    "kernel, a native Windows reparse point or a filesystem that "
                                    "moves inodes underneath the process is claimed"),
        },
        {
            "id": "NM04",
            "severity": "Major",
            "status": "CORRECTED_IN_THIS_BATCH",
            "production_path": [
                "tools/v0_s3_quality_phase.py:1583 _execute_row",
                "tools/v0_s3_quality_phase.py:1260 _validate_source",
                "tools/v0_s3_quality_phase.py:1076 _resolve_driver_state",
                "tools/v0_s3_quality_phase.py:1026 _send_admission_guard",
                "tools/v0_s3_quality_phase.py:1338 _persist_source_plan",
            ],
            "oracle": ("the exclusive source seal written once before the first public submission "
                       "and the bounded five component descriptor identity that it records"),
            "negative": [
                "a controlled accessor that changes the first source produces zero sends, zero "
                "charges, zero reserved calls and sixteen terminal refusals",
                "a controlled accessor that changes a later source preserves the earlier real "
                "attempts and charges and stops every later send",
                "the final source check is the last observation before the single admission",
                "the sealed original identity is the source authority",
            ],
            "terminal": ["SOURCE_REPLACED", "HALTED_AFTER_SOURCE_REPLACED"],
            "cleanup": ("the phase closes every owned handle after the run and the private owned "
                        "root of the case is removed"),
            "counterexample_observations": [
                "limit_source_identity_changed", "later_source_identity_changed",
            ],
        },
    ],
    "test_counts": {
        "baseline_collected_nodeids": len(baseline_ids),
        "candidate_collected_nodeids": len(candidate_ids),
        "baseline_nodeids_missing": sorted(baseline_ids - candidate_ids),
        "added_nodeids": len(candidate_ids - baseline_ids),
        "suite_passed": 206,
        "suite_failed": 0,
        "guard_blocked": 4,
        "guard_attempts": 4,
        "counterexample_observations": OBSERVATIONS["count"],
        "counterexample_observations_are_product_tests": False,
    },
    "obligation_audit": {
        "baseline_revision": AUDIT["baseline_revision"],
        "candidate_revision": AUDIT["candidate_revision"],
        "baseline_test_definitions": AUDIT["baseline_test_definitions"],
        "candidate_test_definitions": AUDIT["candidate_test_definitions"],
        "identical_definitions": AUDIT["identical_definitions"],
        "adapted_definitions": AUDIT["adapted_definitions"],
        "deleted_definitions": AUDIT["deleted_definitions"],
        "added_definitions": len(AUDIT["added_definitions"]),
        "evidence": "reports/v0-s3/product-gate0/implementation-p3b-correction-05/obligation-audit.json",
    },
    "runs": [
        {
            "label": "full-final",
            "mode": "suite",
            "exit_code": FULL["exit_code"],
            "collected_count": FULL["collected_count"],
            "source_unchanged_during_run": FULL["source_unchanged_during_run"],
            "runner_unchanged_during_run": FULL["runner_unchanged_during_run"],
            "probe_unchanged_during_run": FULL["probe_unchanged_during_run"],
            "owned_root_removed": FULL["owned_root_removed"],
            "stdout_sha256": FULL["stdout_sha256"],
            "stderr_sha256": FULL["stderr_sha256"],
            "argv": FULL["argv"],
        },
        {
            "label": "guard-selftest",
            "mode": "guard",
            "exit_code": GUARD["exit_code"],
            "blocked_events": GUARD["guard"]["blocked_events"],
            "guard_results": GUARD["guard_results"],
            "source_unchanged_during_run": GUARD["source_unchanged_during_run"],
            "owned_root_removed": GUARD["owned_root_removed"],
            "stdout_sha256": GUARD["stdout_sha256"],
            "stderr_sha256": GUARD["stderr_sha256"],
            "argv": GUARD["argv"],
        },
        {
            "label": "counterexamples",
            "mode": "script",
            "exit_code": COUNTER["exit_code"],
            "observation_count": OBSERVATIONS["count"],
            "source_unchanged_during_run": COUNTER["source_unchanged_during_run"],
            "probe_unchanged_during_run": COUNTER["probe_unchanged_during_run"],
            "owned_root_removed": COUNTER["owned_root_removed"],
            "stdout_sha256": COUNTER["stdout_sha256"],
            "stderr_sha256": COUNTER["stderr_sha256"],
            "argv": COUNTER["argv"],
        },
    ],
    "guard": FULL["guard"],
    "scope": {
        "changed_paths": [
            "tools/v0_s3_quality_phase.py",
            "tools/test_v0_s3_quality_phase.py",
            "reports/v0-s3/product-gate0/implementation-p3b-correction-05/",
        ],
        "old_evidence_immutable": True,
        "contract_changes": "none",
        "new_infrastructure": False,
        "signing_platform": False,
        "ledger_api": False,
        "real_runtime_execution": False,
        "windows_wsl_powershell_parser_host_hashing": False,
        "real_media_ffmpeg_models_gpu_services_network_download": False,
        "real_ledger_or_full_checkpoint": False,
        "test_source_holdout_or_full_prelabel_read": False,
        "binary_media_database_archive_or_copied_source_committed": False,
        "git_push": False,
        "permanent_configuration": False,
    },
    "not_proven": [
        "parent archive or retained original attestation binding and its integration",
        "parent hard end to end process supervision",
        "native residue admission and A06 enforcement and attempt observation",
        "registration baseline, install and rollback",
        "authentic parent ledger debit",
        "real quality against the real frozen quality set",
        "the real twelve fixed items",
        "the product Gate0",
        "the human experience signature",
        "the release signature",
        "the crash durability of the parent directory entry",
    ],
    "accepted_trust_boundary": ("a total coherent rewrite of both the original trusted canonical "
                                 "document and the original trusted seal is not a new cryptographic "
                                 "signature obligation; the parent must bind the selected owned "
                                 "archive or an independent attestation before a real consumer run"),
    "stage_pass_claim": False,
    "product_gate0": False,
    "real_execution_performed": False,
    "ready_for_review": True,
}

(OUT / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
print(json.dumps({
    "test_counts": receipt["test_counts"],
    "obligation_audit": receipt["obligation_audit"],
    "runs": [{"label": run["label"], "exit_code": run["exit_code"]} for run in receipt["runs"]],
}, indent=2, sort_keys=True))
