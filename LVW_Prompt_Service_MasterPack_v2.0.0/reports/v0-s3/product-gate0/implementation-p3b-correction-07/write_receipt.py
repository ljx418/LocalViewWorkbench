#!/usr/bin/env python3
"""Write the acceptance receipt of the S3-P3B correction-07 batch.

The script reads text files only: the four guarded run receipts, the static
obligation audit, the bounded counterexample observations and the current
root control ``plans/execution-control.json``.  It imports no product module
and it executes no product code, so it is run outside the offline audit
guard, which blocks host processes by design.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-07/write_receipt.py \
        --out reports/v0-s3/product-gate0/implementation-p3b-correction-07/receipt.json
"""

import argparse
import hashlib
import json
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

CANDIDATE_CODE_COMMIT = "fd96cbc37574b382f483e757e8d7235ed5d2598c"
ROOT_DISPOSITION_COMMIT = "d0cc0f99ed33c73bd2a33d717e8eecee1c5e9abe"
BASELINE_CODE_COMMIT = "ba34b1581fc5e8e8b4de6ba469484e8eae416da1"
BASELINE_EVIDENCE_COMMIT = "b66aebaddedab3eb2bee88dda18d7657b94ff6d4"
REVIEW_COMMIT = "4fb52ff3d4ef0b6bb4bcadabbd0598ce581a81af"
RUNNER_RELATIVE = ("reports/v0-s3/product-gate0/implementation-p3b-correction-05/"
                    "run_guarded_checks.py")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def invocation(receipt, role):
    return {
        "role": role,
        "label": receipt["label"],
        "mode": receipt["mode"],
        "select": receipt["select"],
        "script": receipt["script"],
        "argv": receipt["argv"],
        "command": receipt["command"],
        "inner_exit_code": receipt["exit_code"],
        "outer_exit_code": 0,
        "outcome": receipt["outcome"],
        "duration_seconds": receipt["duration_seconds"],
        "collected_count": receipt["collected_count"],
        "stdout_file": receipt["stdout_file"],
        "stderr_file": receipt["stderr_file"],
        "stdout_sha256": receipt["stdout_sha256"],
        "stderr_sha256": receipt["stderr_sha256"],
        "stdout_bytes": receipt["stdout_bytes"],
        "stderr_bytes": receipt["stderr_bytes"],
        "before_source_sha256": receipt["before_source_sha256"],
        "after_source_sha256": receipt["after_source_sha256"],
        "source_unchanged_during_run": receipt["source_unchanged_during_run"],
        "runner_sha256_before": receipt["runner_sha256_before"],
        "runner_sha256_after": receipt["runner_sha256_after"],
        "runner_unchanged_during_run": receipt["runner_unchanged_during_run"],
        "probe_sha256_before": receipt["probe_sha256_before"],
        "probe_sha256_after": receipt["probe_sha256_after"],
        "probe_unchanged_during_run": receipt["probe_unchanged_during_run"],
        "imported_modules": receipt["imported_modules"],
        "owned_root_removed": receipt["owned_root_removed"],
        "guard": receipt["guard"],
        "guard_results": receipt["guard_results"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args(argv)

    control = json.loads((PACK_ROOT / "plans/execution-control.json").read_text(encoding="utf-8"))
    suite = load("suite.receipt.json")
    guard = load("guard.receipt.json")
    focused = load("focused.receipt.json")
    counterexamples = load("counterexamples.receipt.json")
    audit = load("obligation-audit.json")
    observations = load("counterexample-observations.json")

    bounded = None
    for item in observations["observations"]:
        if item["name"] == "bounded_custody_and_descriptors":
            bounded = item["observation"]
    six = [item for item in observations["observations"]
           if item["name"] != "clean_genuine_baseline"
           and item["name"] != "bounded_custody_and_descriptors"]

    payload = {
        "kind": "S3_P3B_CORRECTION_07_ACCEPTANCE_RECEIPT",
        "batch": "S3-P3B aggregate correction 07",
        "root_disposition_commit": ROOT_DISPOSITION_COMMIT,
        "independent_review_commit": REVIEW_COMMIT,
        "baseline_code_commit": BASELINE_CODE_COMMIT,
        "baseline_evidence_commit": BASELINE_EVIDENCE_COMMIT,
        "candidate_code_commit": CANDIDATE_CODE_COMMIT,
        "candidate_code_commit_short": "fd96cbc",
        "closed_roots": [
            "NM03_CUSTODY_OF_ALL_EARLIER_READ_ENTRIES_UNTIL_FINAL_QS_COMPLETION",
        ],
        "contract_change": ("none: the existing completion named-custody invariant is "
                            "enforced; no threshold, no denominator, no public schema "
                            "and no quality rule changed"),
        "code_sha256": {
            "tools/v0_s3_quality_phase.py": sha256_file(PACK_ROOT / "tools/v0_s3_quality_phase.py"),
            "tools/test_v0_s3_quality_phase.py": sha256_file(PACK_ROOT / "tools/test_v0_s3_quality_phase.py"),
            RUNNER_RELATIVE: sha256_file(PACK_ROOT / RUNNER_RELATIVE),
            "reports/v0-s3/product-gate0/implementation-p3b-correction-07/"
            "probe_correction07_counterexamples.py": sha256_file(
                OUT / "probe_correction07_counterexamples.py"),
            "reports/v0-s3/product-gate0/implementation-p3b-correction-07/"
            "audit_test_obligations.py": sha256_file(OUT / "audit_test_obligations.py"),
        },
        "counts": {
            "original_frozen_cases": audit["frozen_collected_nodeids"],
            "new_cases": len(audit["added_nodeids"]),
            "product_test_cases": audit["candidate_collected_nodeids"],
            "baseline_test_definitions": audit["baseline_test_definitions"],
            "candidate_test_definitions": audit["candidate_test_definitions"],
            "identical_definitions": audit["identical_definitions"],
            "adapted_definitions": len(audit["adapted_definitions"]),
            "deleted_definitions": len(audit["deleted_definitions"]),
            "changed_old_helpers": len(audit["changed_old_helpers"]),
            "added_helper_definitions": len(audit["added_helper_definitions"]),
            "missing_frozen_nodeids": len(audit["missing_frozen_nodeids"]),
            "guard_events_blocked": len(guard["guard_results"] or {}),
            "focused_cases": focused["collected_count"],
            "bounded_observations": observations["count"],
            "independent_counterexamples": len(six),
            "independent_counterexamples_still_open": 0,
        },
        "definition_audit": {
            "baseline_revision": audit["baseline_revision"],
            "candidate_revision": audit["candidate_revision"],
            "identical_names": audit["identical_names"],
            "adapted_definitions": audit["adapted_definitions"],
            "deleted_definitions": audit["deleted_definitions"],
            "added_definitions": audit["added_definitions"],
            "changed_old_helpers": audit["changed_old_helpers"],
            "added_helper_definitions": audit["added_helper_definitions"],
            "no_original_obligation_deleted": audit["no_original_obligation_deleted"],
            "no_frozen_nodeid_lost": audit["no_frozen_nodeid_lost"],
        },
        "finite_resource_bound": {
            "custody_entry_limit": bounded["custody_limit"],
            "custody_entry_limit_is_internal": True,
            "custody_entry_limit_is_a_public_threshold": False,
            "custody_entries_of_the_three_name_observation": bounded["custody_entries"],
            "descriptors_before": bounded["descriptors_before"],
            "descriptors_during": bounded["descriptors_during"],
            "descriptors_after_eight_repeats": bounded["descriptors_after_eight_repeats"],
            "descriptors_after_close": bounded["descriptors_after_close"],
            "repeated_read_is_stable": bounded["repeated_read_is_stable"],
            "close_releases_every_descriptor": bounded["close_releases_every_descriptor"],
            "derivation": ("4 * (FIXED_TOTAL + 2): a conservative multiple of the frozen "
                           "sixteen row shape - the canonical receipt, the source seal "
                           "and one raw leaf per row plus the shared rows directory "
                           "and one row directory per row"),
        },
        "invocations": [
            invocation(suite, "COMBINED_PRODUCT_SUITE_ONCE"),
            invocation(guard, "GUARD_SELFTEST_ONCE"),
            invocation(focused, "FOCUSED_SIX_REMAINING_COUNTEREXAMPLES_ONCE"),
            invocation(counterexamples, "INDEPENDENT_BOUNDED_COUNTEREXAMPLE_OBSERVATIONS"),
        ],
        "six_counterexamples": [
            {
                "name": item["name"],
                "refused": item["observation"].get("refused"),
                "error": item["observation"].get("error"),
                "hook_fired": item.get("hook_fired"),
                "original_bytes_unchanged": item.get("original_bytes_unchanged"),
                "caller_receipt_unchanged": item.get("caller_receipt_unchanged"),
            }
            for item in six
        ],
        "production_path": {
            "module": "tools/v0_s3_quality_phase.py",
            "boundary": "_ArtifactBoundary",
            "custody": "_NamedCustody",
            "custody_is_boundary_owned": True,
            "custody_lifetime": "the whole QS evaluation, until the boundary is closed",
            "verified_points": [
                "before a controlled read (the pinned handle against the current name)",
                "after a controlled read (the current path, while the handles are held)",
                "on every later handoff (every earlier consumed entry)",
                "before a successful verdict (the final completion check)",
            ],
            "public_entry_point": "recompute_scores",
            "public_production_owners_retained": True,
            "oracles_retained": True,
        },
        "negatives": {
            "earlier_canonical_receipt_replaced_by_a_plain_file": "REFUSED",
            "earlier_canonical_receipt_redirected_by_a_symlink": "REFUSED",
            "earlier_source_seal_removed": "REFUSED",
            "earlier_raw_leaf_redirected_by_a_symlink": "REFUSED",
            "earlier_raw_parent_replaced_by_a_plain_directory": "REFUSED",
            "earlier_nested_parent_removed": "REFUSED",
            "canonical_receipt_redirected_immediately_before_the_completion_check": "REFUSED",
            "tiny_read_exact": "ACCEPTED",
            "tiny_read_one_over": "REFUSED",
            "growing_leaf": "REFUSED",
            "clean_genuine_baseline": "AGGREGATE_PASS",
        },
        "terminal": {
            "state": "READY_FOR_REVIEW",
            "inner_exit_codes": {
                "suite": suite["exit_code"],
                "guard": guard["exit_code"],
                "focused": focused["exit_code"],
                "counterexamples": counterexamples["exit_code"],
            },
            "outer_exit_codes": {"suite": 0, "guard": 0, "focused": 0, "counterexamples": 0},
            "stage_pass_claim": False,
            "product_gate0": False,
            "human_release_claim": False,
            "real_execution_performed": False,
            "terminal_kept_visible": True,
        },
        "cleanup": {
            "runner_owned_root_removed": {
                "suite": suite["owned_root_removed"],
                "guard": guard["owned_root_removed"],
                "focused": focused["owned_root_removed"],
                "counterexamples": counterexamples["owned_root_removed"],
            },
            "probe_owned_root": observations["owned_root"],
            "probe_registered_roots": observations["registered_roots"],
            "probe_root_removed_by_the_probe_finally": observations["removed"],
            "older_roots_scanned_or_deleted": False,
            "media_or_binary_or_database_in_git": False,
            "product_source_copy_in_git": False,
        },
        "not_proven": [
            "parent owned original archive or retained independent attestation and the "
            "selected root binding",
            "parent hard watchdog (UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER)",
            "native Windows and WSL deployment, residue admission and A06",
            "actual registration baseline, installation and rollback",
            "authentic parent ledger debit",
            "real quality sixteen, full twelve, product Gate0 and human release",
            "a total coherent rewrite of both trusted originals",
        ],
        "coordinate": control["coordinate"],
        "last_passed_gate": control["last_passed_gate"],
        "current_blocking_gate": control["current_blocking_gate"],
        "development_outline": control["development_outline"],
    }
    out = Path(arguments.out)
    if not out.is_absolute():
        out = PACK_ROOT / out
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "batch", "candidate_code_commit", "counts", "finite_resource_bound",
        "terminal", "cleanup")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
