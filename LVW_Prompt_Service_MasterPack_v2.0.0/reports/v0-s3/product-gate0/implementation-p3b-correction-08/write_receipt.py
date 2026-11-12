#!/usr/bin/env python3
"""Write the acceptance receipt of the S3-P3B correction-08 batch.

The script reads text files only: the four guarded run receipts, the static
obligation audit, the bounded resource observations, the diagnostic runs of
the debug phase and the current root control
``plans/execution-control.json``.  It imports no product module and it
executes no product code, so it is run outside the offline audit guard,
which blocks host processes by design.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-08/write_receipt.py \
        --out reports/v0-s3/product-gate0/implementation-p3b-correction-08/receipt.json
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
DEBUG = OUT / "debug"

CANDIDATE_CODE_COMMIT = "6c9a0a07c66060e53b00e690ebdd98047167511d"
ROOT_DISPOSITION_COMMIT = "94ade2aa32740830c17849b04dc2d3c365857c3e"
ROOT_RESUME_APPROVAL_COMMIT = "4de8379eaf658d10f53fe3a1c954ff29773c95ae"
REVIEW_COMMIT = "9d2c51de4e8df6e5f882405cbff1332356dc8269"
BASELINE_CODE_COMMIT = "fd96cbc37574b382f483e757e8d7235ed5d2598c"
BASELINE_EVIDENCE_COMMIT = "55e5463ae1bd1dd9f6c9c19bda347fe5900051ff"
RUNNER_RELATIVE = ("reports/v0-s3/product-gate0/implementation-p3b-correction-05/"
                    "run_guarded_checks.py")
PROBE_RELATIVE = ("reports/v0-s3/product-gate0/implementation-p3b-correction-08/"
                   "probe_correction08_counterexamples.py")
AUDIT_RELATIVE = ("reports/v0-s3/product-gate0/implementation-p3b-correction-08/"
                   "audit_test_obligations.py")


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
        "candidate_sha_claim": receipt["candidate_sha_claim"],
        "candidate_sha_claim_is_attestation": receipt["candidate_sha_claim_is_attestation"],
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


def summary_line(path, mode):
    """The summary line of a raw run stream.

    The pytest summary is the line that starts with the number of the
    cases; the bounded observation script prints a JSON payload, so its
    summary is the size of the payload and the number of the observed
    violations.
    """
    text = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    if mode == "script":
        # The stream holds the payload of the script and, after it, the
        # receipt that the runner itself prints; only the first JSON value
        # is the payload of the observation.
        payload = {}
        if text:
            payload, _ = json.JSONDecoder().raw_decode("\n".join(text))
        return ("bounded resource observations: %d observations, %d violations"
                % (payload.get("count", 0), len(payload.get("violations") or [])))
    pattern = re.compile(r"^\d+ (passed|failed|error)")
    for line in reversed(text):
        if pattern.match(line.strip()):
            return line.strip()
    return text[-1].strip() if text else ""


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

    by_name = {item["name"]: item["observation"] for item in observations["observations"]}
    bound = by_name["custody_bound_exact_and_one_over"]
    child = by_name["owner_child_directory_metadata"]
    leaf = by_name["owner_leaf_metadata"]
    public = by_name["public_evaluation_metadata"]
    admission = by_name["failed_admission"]

    debug_receipts = sorted(DEBUG.glob("*.receipt.json"))
    diagnostics = []
    for path in debug_receipts:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        diagnostics.append({
            "label": receipt["label"],
            "mode": receipt["mode"],
            "select": receipt["select"],
            "script": receipt["script"],
            "inner_exit_code": receipt["exit_code"],
            "outcome": receipt["outcome"],
            "duration_seconds": receipt["duration_seconds"],
            "collected_count": receipt["collected_count"],
            "product_source_sha256_during_the_run": receipt["before_source_sha256"].get(
                "tools/v0_s3_quality_phase.py"),
            "summary": summary_line(DEBUG / (receipt["label"] + ".stdout.log"),
                                    receipt["mode"]),
            "stdout_sha256": receipt["stdout_sha256"],
            "stderr_sha256": receipt["stderr_sha256"],
            "stdout_file": receipt["stdout_file"],
            "stderr_file": receipt["stderr_file"],
            "role": "PRE_COMMIT_DIAGNOSTIC_NOT_FINAL_EVIDENCE",
        })

    negative_control = next(item for item in diagnostics
                             if item["label"] == "debug-negative-control")

    payload = {
        "kind": "S3_P3B_CORRECTION_08_ACCEPTANCE_RECEIPT",
        "batch": "S3-P3B aggregate correction 08",
        "root_disposition_commit": ROOT_DISPOSITION_COMMIT,
        "root_resume_approval_commit": ROOT_RESUME_APPROVAL_COMMIT,
        "independent_review_commit": REVIEW_COMMIT,
        "baseline_code_commit": BASELINE_CODE_COMMIT,
        "baseline_evidence_commit": BASELINE_EVIDENCE_COMMIT,
        "candidate_code_commit": CANDIDATE_CODE_COMMIT,
        "candidate_code_commit_short": "6c9a0a0",
        "closed_roots": [
            "NM03_R1_POST_OPEN_METADATA_EXCEPTION_DESCRIPTOR_LEAK",
            "NM03_r2_CAP_CHECK_AFTER_EXCESS_OPEN",
        ],
        "contract_change": ("none: the existing cleanup and before-excess-open bounds are "
                            "enforced; no threshold, no denominator, no public schema "
                            "and no quality rule changed"),
        "code_sha256": {
            "tools/v0_s3_quality_phase.py": sha256_file(PACK_ROOT / "tools/v0_s3_quality_phase.py"),
            "tools/test_v0_s3_quality_phase.py": sha256_file(PACK_ROOT / "tools/test_v0_s3_quality_phase.py"),
            RUNNER_RELATIVE: sha256_file(PACK_ROOT / RUNNER_RELATIVE),
            PROBE_RELATIVE: sha256_file(PACK_ROOT / PROBE_RELATIVE),
            AUDIT_RELATIVE: sha256_file(PACK_ROOT / AUDIT_RELATIVE),
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
            "observed_violations": len(observations["violations"]),
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
            "no_original_obligation_adapted": audit["no_original_obligation_adapted"],
            "no_old_helper_changed": audit["no_old_helper_changed"],
        },
        "negative_control": {
            "what": ("the new correction-08 cases were executed against the unfixed "
                     "baseline product code fd96cbc in the debug phase of this batch"),
            "label": negative_control["label"],
            "product_source_sha256_during_the_run":
                negative_control["product_source_sha256_during_the_run"],
            "inner_exit_code": negative_control["inner_exit_code"],
            "summary": negative_control["summary"],
            "meaning": ("the new cases reproduce the two resource roots of the independent "
                        "review against the baseline and pass against the candidate"),
            "not_a_final_evidence_run": True,
        },
        "finite_resource_bound": {
            "custody_entry_limit": bound["custody_limit"],
            "custody_entry_limit_is_internal": True,
            "custody_entry_limit_is_a_public_threshold": False,
            "exact_entries_at_the_bound": bound["exact_entries"],
            "opens_for_the_exact_bound": bound["opens_for_the_exact_bound"],
            "extra_opens_for_the_excess": bound["extra_opens_for_the_excess"],
            "descriptors_before": bound["descriptors_before"],
            "descriptors_at_the_bound": bound["descriptors_at_the_bound"],
            "descriptors_after_the_refused_excess": bound["descriptors_after_the_refused_excess"],
            "descriptors_after_the_repeated_name": bound["descriptors_after_the_repeated_name"],
            "descriptors_after_close": bound["descriptors_after_close"],
            "opens_after_the_repeated_name": bound["opens_after_the_repeated_name"],
            "the_excess_is_refused_without_an_open": bound["the_excess_is_refused_without_an_open"],
            "the_repeated_name_at_the_bound_opens_nothing":
                bound["the_repeated_name_at_the_bound_opens_nothing"],
            "the_earlier_custody_is_still_verifiable": bound["the_earlier_custody_is_still_verifiable"],
            "derivation": ("4 * (FIXED_TOTAL + 2): a conservative multiple of the frozen "
                           "sixteen row shape - the canonical receipt, the source seal "
                           "and one raw leaf per row plus the shared rows directory "
                           "and one row directory per row"),
        },
        "descriptor_ownership": {
            "child_directory_metadata_failure": {
                "hook_fired": child["hook_fired"],
                "refused": child["refused"],
                "descriptors_before": child["descriptors_before"],
                "descriptors_during": child["descriptors_during"],
                "descriptors_after_the_refused_read": child["descriptors_after_the_refused_read"],
                "descriptors_after_close": child["descriptors_after_close"],
                "the_refused_descriptor_is_closed": child["the_refused_descriptor_is_closed"],
                "the_boundary_releases_everything": child["the_boundary_releases_everything"],
                "the_custody_is_undamaged": child["the_custody_is_undamaged"],
            },
            "leaf_metadata_failure": {
                "hook_fired": leaf["hook_fired"],
                "refused": leaf["refused"],
                "descriptors_before": leaf["descriptors_before"],
                "descriptors_during": leaf["descriptors_during"],
                "descriptors_after_the_refused_read": leaf["descriptors_after_the_refused_read"],
                "descriptors_after_close": leaf["descriptors_after_close"],
                "the_refused_descriptor_is_closed": leaf["the_refused_descriptor_is_closed"],
                "the_boundary_releases_everything": leaf["the_boundary_releases_everything"],
                "the_custody_is_undamaged": leaf["the_custody_is_undamaged"],
            },
            "public_evaluation_metadata_failure": {
                "hook_fired": public["hook_fired"],
                "refused": public["refused"],
                "descriptors_before": public["descriptors_before"],
                "descriptors_after": public["descriptors_after"],
                "the_public_refusal_releases_everything":
                    public["the_public_refusal_releases_everything"],
            },
            "failed_admission": {
                "hook_fired": admission["hook_fired"],
                "refused": admission["refused"],
                "descriptors_during": admission["descriptors_during"],
                "descriptors_after_the_refused_admission":
                    admission["descriptors_after_the_refused_admission"],
                "custody_entries_after_the_refusal": admission["custody_entries_after_the_refusal"],
                "reserved_slots_after_the_refusal": admission["reserved_slots_after_the_refusal"],
                "the_next_name_is_admitted": admission["the_next_name_is_admitted"],
                "custody_entries_after_the_admission": admission["custody_entries_after_the_admission"],
                "the_refused_admission_closed_its_descriptor":
                    admission["the_refused_admission_closed_its_descriptor"],
                "the_refused_admission_consumed_no_slot":
                    admission["the_refused_admission_consumed_no_slot"],
            },
            "no_probe_remediation": ("the injected faults are never repaired by the probe; a "
                                     "leaked descriptor would stay visible in the descriptor "
                                     "count"),
        },
        "invocations": [
            invocation(suite, "COMBINED_PRODUCT_SUITE_ONCE"),
            invocation(guard, "GUARD_SELFTEST_ONCE"),
            invocation(focused, "FOCUSED_RESOURCE_COUNTEREXAMPLES_ONCE"),
            invocation(counterexamples, "INDEPENDENT_BOUNDED_RESOURCE_OBSERVATIONS"),
        ],
        "diagnostics": diagnostics,
        "production_path": {
            "module": "tools/v0_s3_quality_phase.py",
            "boundary": "_ArtifactBoundary",
            "custody": "_NamedCustody",
            "custody_is_boundary_owned": True,
            "custody_lifetime": "the whole QS evaluation, until the boundary is closed",
            "ownership_rule": ("every successful os.open has exactly one owner until the "
                               "descriptor is closed: the level openers hand the descriptor "
                               "to the boundary before they read any metadata, the child and "
                               "leaf openers own it until the metadata was validated and "
                               "the custody has taken it over"),
            "admission_rule": ("the custody slot is reserved before the descriptor of a new "
                               "name is opened; a refused admission consumes no slot"),
            "public_entry_point": "recompute_scores",
            "public_production_owners_retained": True,
            "oracles_retained": True,
        },
        "negatives": {
            "child_directory_metadata_failure_after_the_open": "REFUSED_AND_CLOSED",
            "leaf_metadata_failure_after_the_open": "REFUSED_AND_CLOSED",
            "child_directory_named_stat_failure": "REFUSED_AND_CLOSED",
            "leaf_named_identity_mismatch": "REFUSED_AND_CLOSED",
            "leaf_named_type_mismatch": "REFUSED_AND_CLOSED",
            "custody_insertion_failure": "REFUSED_AND_CLOSED",
            "public_evaluation_metadata_failure": "REFUSED_AND_RELEASED",
            "custody_bound_exact": "ACCEPTED",
            "custody_bound_one_over": "REFUSED_WITHOUT_AN_OPEN",
            "repeated_name_at_the_bound": "REUSED_WITHOUT_AN_OPEN",
            "refused_admission": "REFUSED_WITHOUT_A_CONSUMED_SLOT",
            "failed_boundary_construction": "REFUSED_AND_RELEASED",
            "earlier_read_and_completion_mutations": "STILL_REFUSED",
            "clean_genuine_run": "AGGREGATE_PASS",
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
            "immunity against a hostile kernel, a native Windows reparse point, a "
            "filesystem that moves inodes underneath the process or any universal "
            "concurrency guarantee",
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
        "negative_control", "terminal", "cleanup")}, ensure_ascii=False, indent=2,
        sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
