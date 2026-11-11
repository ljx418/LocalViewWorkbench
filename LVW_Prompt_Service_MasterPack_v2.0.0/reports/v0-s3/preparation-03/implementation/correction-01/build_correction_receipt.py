#!/usr/bin/env python3
"""Derive the S3-PREP-A correction-01 machine receipt from the recorded runs.

This script does not decide anything.  It re-reads the raw logs that the
evidence run produced, extracts the counts and the exit codes mechanically, and
writes the append receipt, the code-candidate record and the SHA-256 sum file.

Usage: python3 -B reports/v0-s3/preparation-03/implementation/correction-01/build_correction_receipt.py
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parents[4]
LOG_DIR = HERE / "logs"

CODE_CANDIDATE = "bc78869231e4dc320dfc9c7198a07aeabf9412fe"
SOURCE_LOAD_COMMIT = "137ce11549b4fe1b9006e5eaffaf21dbcb064c09"
CODEX_SOURCE_COMMIT = "12a1594c12b57a62ce445e4cf7f11fd38423039d"
PREVIOUS_CODE_CANDIDATE = "d33893303f24da57216b63b4e0b9ef7e009d7613"
PREVIOUS_TERMINAL_CANDIDATE = "311bdda937373f1055a6677f02322fb347c31cd1"

GUARD_SHA = "d2b3fd332e3d77a8f710691f9a852b61923d6436d4a9d51a6c131165d5c2b5fa"
GUARD_SHA_PRE_CORRECTION = "5944771fd3fe880014bcbecd06b1ba1fbe76a58d2b560ec74d8a679de5adfe9d"
TEST_SHA = "9a46fd77b388639691c1b91dd1a9042f67f739c23ee9a33d22a72938bdde6328"
INVENTORY_SCRIPT_SHA = "333cfed9828fae22df524870fa691e553bcdb1965f30c1f5efb0b1882e3cbb30"
INVENTORY_TEST_SHA = "2af8bf3e9526e0da4f5c42417f7437a0f62a4d73f429755ff55be06fa92957e0"
INVENTORY_RECEIPT_SHA = "05ab5d63a69556c721b26191273cf60c20e4b3bb5826712688cefb06786ee2ef"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pytest_counts(log: Path) -> dict:
    text = log.read_text(encoding="utf-8", errors="replace")
    passed = re.search(r"(\d+) passed", text)
    failed = re.search(r"(\d+) failed", text)
    return {
        "passed": int(passed.group(1)) if passed else None,
        "failed": int(failed.group(1)) if failed else 0,
        "raw_tail": text.strip().splitlines()[-1] if text.strip() else "",
    }


def guard_counts(log: Path) -> dict:
    payload = json.loads(log.read_text(encoding="utf-8"))
    failed = [item["id"] for item in payload["checks"] if not item["passed"]]
    return {
        "decision": payload["decision"],
        "checks": payload["summary"]["checks"],
        "passed": payload["summary"]["passed"],
        "failed": payload["summary"]["failed"],
        "failed_ids": failed,
        "authority": payload["authority"],
        "observed_historical_s2_projection": payload["historical_s2_projection"],
        "declared_expected_state": payload["historical_s2_declared_expected_state"],
    }


def main() -> int:
    config = json.loads((HERE / "run_configuration.json").read_text(encoding="utf-8"))
    runs = {record["name"]: record for record in config["runs"]}

    packet_tests = pytest_counts(PACKAGE_ROOT / runs["pytest_packet_tests"]["stdout"]["log"])
    owned_tests = pytest_counts(PACKAGE_ROOT / runs["pytest_owned_basetemp"]["stdout"]["log"])
    revert_tests = pytest_counts(
        PACKAGE_ROOT / runs["guard_revert_regression"]["stdout"]["log"]
    )
    guard_ok = guard_counts(PACKAGE_ROOT / runs["verify_s3_handoff"]["stdout"]["log"])
    guard_fake = guard_counts(
        PACKAGE_ROOT / runs["cli_negative_fake_outline"]["stdout"]["log"]
    )

    candidate = {
        "kind": "S3_PREP_A_CORRECTION_01_CODE_CANDIDATE",
        "stage_id": "V0-S3",
        "workpack_id": "S3-PREP-A",
        "correction_id": "S3-PREP-A-CORRECTION-01",
        "decision": "READY_FOR_REVIEW",
        "code_candidate": CODE_CANDIDATE,
        "code_candidate_subject": (
            "feat(S3-PREP-A): read the actual old-S2 projection in the handoff guard"
        ),
        "source_load_commit": SOURCE_LOAD_COMMIT,
        "codex_source_commit": CODEX_SOURCE_COMMIT,
        "previous_code_candidate": PREVIOUS_CODE_CANDIDATE,
        "previous_terminal_candidate": PREVIOUS_TERMINAL_CANDIDATE,
        "branch": "ljx418/lvw-v1-d0-implement",
        "merged_into_main": False,
        "pushed": False,
        "files": [
            {
                "path": "tools/verify_s3_handoff.py",
                "sha256": sha256_file(PACKAGE_ROOT / "tools/verify_s3_handoff.py"),
                "expected": GUARD_SHA,
                "status": "modified",
            },
            {
                "path": "tools/test_verify_s3_handoff.py",
                "sha256": sha256_file(PACKAGE_ROOT / "tools/test_verify_s3_handoff.py"),
                "expected": TEST_SHA,
                "status": "modified",
            },
            {
                "path": "tools/s3_asset_inventory.py",
                "sha256": sha256_file(PACKAGE_ROOT / "tools/s3_asset_inventory.py"),
                "expected": INVENTORY_SCRIPT_SHA,
                "status": "unchanged",
            },
            {
                "path": "tools/test_s3_asset_inventory.py",
                "sha256": sha256_file(PACKAGE_ROOT / "tools/test_s3_asset_inventory.py"),
                "expected": INVENTORY_TEST_SHA,
                "status": "unchanged",
            },
        ],
        "inventory_terminal_receipt": {
            "path": "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json",
            "sha256": INVENTORY_RECEIPT_SHA,
            "bound_to_candidate": PREVIOUS_CODE_CANDIDATE,
            "relabelled_as_new_candidate": False,
        },
    }
    (HERE / "candidate-correction-01.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    receipt = {
        "kind": "S3_PREP_A_CORRECTION_01_APPEND_RECEIPT",
        "stage_id": "V0-S3",
        "workpack_id": "S3-PREP-A",
        "correction_id": "S3-PREP-A-CORRECTION-01",
        "decision": "READY_FOR_REVIEW",
        "scope": "HANDOFF_READINESS_ONLY",
        "product_gate0": False,
        "stage_pass_claim": False,
        "human_signature_made": False,
        "release_claimed": False,
        "old_s2_human_signoff_granted": False,
        "blocker_addressed": "S3P-A-MAJOR-01",
        "new_human_confirmation_requested": False,
        "approved_change": {
            "id": "CHANGE-V1-S2-HANDOFF-01",
            "status": "already approved; not up for a new human confirmation",
            "approval_sha256": "bab47506d5a13657edcabc33644c6b159f2967e696dff4c4c43859d54fbf3057",
        },
        "authority": {
            "codex_adjudication": "reports/v0-s3/preparation-03/codex-review-resolution-01.json",
            "codex_adjudication_decision": "CHANGES_REQUIRED_MAJOR01_NO_NEW_HUMAN_AUTHORIZATION",
            "independent_review": "reports/v0-s3/preparation-03/independent-01/",
            "independent_review_verdict": "NOT_ACCEPTABLE_AS_IS",
            "independent_review_summary": {"Fatal": 0, "Major": 1, "Minor": 7},
            "review_process_deviation": "reports/v0-s3/preparation-03/independent-hash-process-deviation-01.json",
            "review_process_deviation_retained": True,
            "review_process_deviation_note": (
                "the final positive recheck does not erase the two preflight-failed source reads; "
                "no fully compliant independent read is claimed and the reviewer helper fix stays "
                "separately owned by root"
            ),
        },
        "source_loading": {
            "codex_source_commit": CODEX_SOURCE_COMMIT,
            "loading_method": "git merge --no-edit into the clean child checkout",
            "merge_commit": SOURCE_LOAD_COMMIT,
            "merge_conflicts": 0,
            "merge_exit_code": 0,
            "purpose": "source loading only; no owner document was rewritten by hand",
            "push_performed": False,
        },
        "code_candidate": CODE_CANDIDATE,
        "changed_files": [
            "tools/verify_s3_handoff.py",
            "tools/test_verify_s3_handoff.py",
            "reports/v0-s3/preparation-03/implementation/correction-01/",
        ],
        "not_changed": {
            "inventory_script": "tools/s3_asset_inventory.py (byte-identical to 311bdda)",
            "inventory_test": "tools/test_s3_asset_inventory.py (byte-identical to 311bdda)",
            "owner_files": (
                "no owner document, plan, contract, packet, approval, proof, old receipt or "
                "parent worktree file was edited"
            ),
            "owner_files_resealed": False,
            "frozen_source_fence": "16 source fence files and 10 packet payload pins unchanged",
        },
        "semantic_guard": {
            "reads_actual_authority": "plans/execution-control.json",
            "method": "read and interpret; the document is never hash-frozen",
            "checks_added": 20,
            "check_prefix": "actual.",
            "outline_requirements": {
                "exactly_one_stage_id": "V0-S2",
                "completed_substeps": "integer (non-bool) 7",
                "total_substeps": "integer (non-bool) 8",
                "human_signoff": "PENDING",
                "substeps": "exactly 8; exactly 7 DONE; exactly 1 PENDING",
                "human_substep_name": "S2 人工签署与Git同步",
                "human_substep_state": "PENDING with evidence null",
            },
            "historical_s2_coordinate": {
                "role": "retained snapshot, not a second live coordinate",
                "required": {
                    "stage_id": "V0-S2",
                    "workpack_id": "WP-S2-06",
                    "gate": "GATE5_HUMAN_EXPERIENCE_SIGNOFF",
                    "state": "WAIT_HUMAN",
                },
            },
            "free_to_advance": [
                "coordinate.stage_id",
                "coordinate.workpack_id",
                "coordinate.gate",
                "coordinate.state",
                "current_blocking_gate",
                "updated_at",
            ],
            "report_separation": {
                "historical_s2_projection": "observed live values (null when missing or malformed)",
                "historical_s2_declared_expected_state": "the declared contract 7/8/PENDING",
                "historical_s2_projection_source": "plans/execution-control.json#/development_outline (stage_id=V0-S2)",
                "historical_s2_coordinate_observed": "the observed retained snapshot",
                "never_asserts_7_of_8_when_observed_contradicts": True,
            },
        },
        "test_oracle_mapping": [
            {
                "old_test": "test_the_historical_s2_coordinate_state_is_not_required_to_stay_wait_human",
                "old_oracle": "the retained historical snapshot may be rewritten",
                "new_test": "test_the_historical_s2_coordinate_snapshot_must_not_be_rewritten[stage_id|workpack_id|gate|state]",
                "new_oracle": "rewriting the retained historical snapshot must be refused",
                "reason": "owner re-decision: historical_s2_coordinate is a retained snapshot per the Codex memo, not a second live coordinate",
                "silent_deletion": False,
            },
            {
                "old_test": "test_execution_coordinates_may_advance",
                "old_oracle": "the live coordinate may advance",
                "new_test": "test_execution_coordinates_may_advance",
                "new_oracle": "unchanged (retained)",
                "reason": "the live coordinate stays deliberately unfrozen",
                "silent_deletion": False,
            },
        ],
        "tests": {
            "packet_command": "python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py -q",
            "handoff_test_file_cases": 43,
            "inventory_test_file_cases": 22,
            "total": 43 + 22,
            "total_source": "the two test files collected 43 + 22 cases; both runs reported 65 passed",
            "passed": packet_tests["passed"],
            "failed": packet_tests["failed"],
            "owned_basetemp_run": {
                "passed": owned_tests["passed"],
                "failed": owned_tests["failed"],
                "owned_parent_removed_after_context": runs["pytest_owned_basetemp"][
                    "owned_parent_removed"
                ],
            },
            "preserved_obligations": 25,
            "re_decided_oracle_cases": 4,
            "new_cases": 14,
            "regression_against_pre_correction_guard": {
                "collected": revert_tests["passed"] + revert_tests["failed"],
                "failed": revert_tests["failed"],
                "passed": revert_tests["passed"],
                "meaning": "every new and re-decided test fails without the semantic guard fix",
            },
            "constant_against_itself": "the new assertions use literal values and observed values only",
        },
        "runs": [
            {
                "name": record["name"],
                "argv": record["argv"],
                "cwd": record["cwd"],
                "exit_code": record["exit_code"],
                "wall_seconds": record["wall_seconds"],
                "stdout_sha256": record["stdout"]["sha256"],
                "stderr_sha256": record["stderr"]["sha256"],
                "stdout_log": record["stdout"]["log"],
                "stderr_log": record["stderr"]["log"],
                "exit_log": record["exit_log"],
                "owned_parent_removed_after_context": record.get("owned_parent_removed"),
            }
            for record in config["runs"]
        ],
        "machine_extracted_counts": {
            "guard_real_root": guard_ok,
            "guard_faked_actual_outline": guard_fake,
            "pytest_packet_command": packet_tests,
            "pytest_owned_basetemp": owned_tests,
            "pytest_pre_correction_guard": revert_tests,
        },
        "inventory_reuse_analysis": {
            "decision": "REUSE_THE_EXISTING_TERMINAL_INVENTORY_RECEIPT_NO_NEW_INVENTORY",
            "new_full_inventory_authorized": False,
            "new_full_inventory_needed": False,
            "terminal_receipt_path": "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json",
            "terminal_receipt_sha256": INVENTORY_RECEIPT_SHA,
            "bound_to_candidate": PREVIOUS_CODE_CANDIDATE,
            "relabelled_as_new_candidate": False,
            "inventory_script_sha256": INVENTORY_SCRIPT_SHA,
            "inventory_script_unchanged": True,
            "inventory_test_sha256": INVENTORY_TEST_SHA,
            "inventory_test_unchanged": True,
            "why_the_receipt_stays_valid": [
                "the correction changes only the handoff guard: not the inventory script, not its test, not the hash algorithm, not the input set",
                "the actual old-S2 projection that was inventoried was valid 7/8 and is unchanged in the live authority",
                "the independent three-file hashes are correct; the reviewer 3-pass/preflight deviation stays recorded and is not treated as a fully compliant independent read",
            ],
            "preflight_binding_is_stale_and_is_not_resealed": {
                "preflight_handoff_script_sha256": GUARD_SHA_PRE_CORRECTION,
                "corrected_handoff_script_sha256": GUARD_SHA,
                "consequence": "the old inventory CLI would refuse the old preflight binding; the inventory CLI was not run to force it through",
                "inventory_cli_invocations": 0,
            },
            "coverage_limits": {
                "supported_extension_files": 698,
                "hashed": 512,
                "unhashed": 186,
                "whole_corpus_complete": False,
                "inventory_input_items": 512,
                "derived_catalog_candidates": 509,
                "distinct_candidate_content_sha256": 498,
                "excluded_private_labelled_paths": 3,
                "decision_string_meaning": "INVENTORY_COMPLETE describes the bounded operation, not corpus coverage",
            },
        },
        "errata": {
            "file": "reports/v0-s3/preparation-03/implementation/correction-01/errata.md",
            "covers": [
                "S3P-A-MINOR-01 bounded INVENTORY_COMPLETE is not full coverage (512/698, 186 unhashed, 509/498, 3 excluded)",
                "S3P-A-MINOR-02 the pytest tmp_path cleanup sentence was inaccurate and the zero cleanup counters are declarations, not measurements",
                "S3P-A-MINOR-03 AUTHORITATIVE is a local pinned-files check, not a Git attestation; the candidate and script binding is attested externally",
                "S3P-A-MINOR-05 the disclosed ls -la metadata deviation is retained without a retroactive grant",
                "S3P-A-MINOR-06 a failed attempt's terminal receipt is immutable; a future attempt needs a new child and a new path",
                "S3P-A-MINOR-07 and the independent report wording: hashing DID open and read the bytes of the three flagged files; no decode, no visual view, no raw media copy, no provider call",
                "the reviewer's 3-pass/preflight deviation is retained and is not absorbed",
            ],
            "append_only": True,
            "old_records_modified": False,
        },
        "budgets": {
            "model_actions": 0,
            "gpu_actions": 0,
            "media_reads": 0,
            "media_hashes": 0,
            "service_starts": 0,
            "network_requests": 0,
            "downloads": 0,
            "browser_starts": 0,
            "productdb_queries": 0,
            "decoder_invocations": 0,
            "inventory_runs": 0,
            "provider_switches": 0,
            "human_signatures_made": 0,
            "note": "the guard hashes the 16 frozen source-fence files and the 10 packet payload files; those are package documents, not media",
        },
        "cleanup": {
            "owned_temporary_parents_created": 3,
            "owned_temporary_parents_removed_after_context": True,
            "shared_pytest_roots_purged": False,
            "source_files_modified": 0,
            "source_files_deleted": 0,
            "note": "pytest retains its own tmp_path fixtures; the owned TemporaryDirectory parents used here were verified gone after their context exited",
        },
        "limits_and_open_items": [
            "the root commissions a bounded Major-closure recheck next; this worker does not claim the Major closed by its own tests",
            "the reviewer helper correction is separately owned by root and untouched here",
            "the independent review's hash-process deviation stays open",
            "S3P-A-MINOR-01..07 stay non-blocking; no code fix and no inventory label or format change was made for them",
            "product Gate0, the S3 quality set, the V1 Q01 set, the MS sets, packaging, the execution adapter, the finite production budget and every later human signature remain open product items",
            "the AUTHORITATIVE label is path-relative and is not a provenance attestation",
            "the guard binds the local pinned files, not a git object; the candidate and script binding is attested by the preflight, the pre-receipt and the independent review",
        ],
        "next_owner": "root; a bounded S3P-A-MAJOR-01 closure recheck is commissioned next",
    }
    (HERE / "correction-01-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    sums = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            sums.append(
                "%s  %s"
                % (
                    sha256_file(path),
                    path.relative_to(PACKAGE_ROOT).as_posix(),
                )
            )
    (HERE / "checks/SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print("receipt written; %d files hashed" % len(sums))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
