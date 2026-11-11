#!/usr/bin/env python3
"""Validate the approved V1-only S2 -> S3 handoff predicate (ADR-14).

This is a READINESS validator and nothing else.  It proves that the single
approved dependency predicate ``S3-V1-ONLY-S2-HANDOFF-01`` is:

* present and identical in all three authority plans
  (``plans/tasks.json`` -> ``dependency_gate_overrides``,
  ``plans/v1-revised-plan.json`` -> ``v1_only_s2_handoff``,
  ``plans/execution-control.json`` -> ``v1_only_s2_handoff``),
* bound to the exact owner scope approval (``CHANGE-V1-S2-HANDOFF-01``) and to
  the exact immutable request that approval answers,
* bound to the exact frozen machine / independent / human evidence hashes,
* paired with the frozen capability mapping that keeps every retained S3
  quality, install and rollback duty,
* still projecting the historical S2 stage as 7/8 with native human signoff
  PENDING -- in the *declared* predicate snapshot **and** in the *actual* live
  authority ``plans/execution-control.json`` (the ``development_outline``
  entry ``V0-S2`` and the retained ``historical_s2_coordinate`` snapshot).

Deliberately NOT validated (and deliberately not frozen): the mutable *live*
execution coordinates of ``plans/execution-control.json`` (``coordinate`` /
``current_blocking_gate`` / ``updated_at``).  Those may advance.  The document
is read and interpreted, never hash-frozen: the old-S2 *actual* projection is
asserted semantically against the live authority, not against a copied
snapshot or a checksum.

This tool never grants model execution, never grants product Gate0 and never
declares a Stage PASS.

Usage:
    python3 -B tools/verify_s3_handoff.py [--root PACKAGE_ROOT]

Exit code 0 when every check passes, 1 otherwise.  The stdout payload is a
single JSON object.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Frozen owner authority.  These values are copied from the Codex-owned
# authority documents; this tool never regenerates or rewrites them.
# --------------------------------------------------------------------------
PACKET_REL = ".agent-governance/stages/V0-S3"
SPEC_MANIFEST_REL = PACKET_REL + "/spec-manifest.json"
SPEC_MANIFEST_SHA256 = "4e0018e284094172ac8c20bb5002913e200fcf6d5def0a48ec221b1af05c8dc1"
PAYLOAD_MANIFEST_REL = PACKET_REL + "/PAYLOAD_MANIFEST.sha256"
PAYLOAD_MANIFEST_SHA256 = "d167feb76e99dc3d9abcaa9892db6754e19e765a27c967ca8d012629a6e77a78"
SOURCE_FENCE_COUNT = 16
PAYLOAD_FENCE_COUNT = 10

PREDICATE_ID = "S3-V1-ONLY-S2-HANDOFF-01"
CHANGE_ID = "CHANGE-V1-S2-HANDOFF-01"
CONSUMER_STAGE = "V0-S3"
DEPENDENCY_STAGE = "V0-S2"
PURPOSE = "V1_DEVELOPMENT_ONLY"

S2_MACHINE_CANDIDATE = "719c74559393a6489b2f630a1e0d3bc3303eb655"
UM_HUMAN_CANDIDATE = "621b1bf386db71bfe08ca2f533fa8ec396b0504b"

REQUIRED_S2_CASE_IDS = (
    "V0-A01", "V0-A02", "V0-A03", "V0-A04", "V0-A05",
    "V0-A07", "V0-A08", "V0-A09", "V0-A10",
)
REQUIRED_UM_CASE_IDS = (
    "UM-01", "UM-02", "UM-03", "UM-04", "UM-05",
    "UM-06", "UM-07", "UM-08", "UM-09", "UM-10",
)
NEW_S3_CASE_IDS = ("V0-A06", "V0-A11", "V0-A12")
ALL_S3_CASE_IDS = tuple("V0-A%02d" % index for index in range(1, 13))

# The seven proof files bound by the predicate.  Order is irrelevant, the
# mapping is compared as a whole.
PROOF_PINS = {
    "scope_request": {
        "path": "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.request.json",
        "sha256": "8a6032010e7290325341cf7f54c6de25c68412e9bdb651dab1d7bc4803da2e91",
    },
    "scope_approval": {
        "path": "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.approval.json",
        "sha256": "bab47506d5a13657edcabc33644c6b159f2967e696dff4c4c43859d54fbf3057",
    },
    "s2_machine": {
        "path": "reports/v0-s2/full-v0-auto-08/receipt.json",
        "sha256": "53c267a19a60b34b8aa7abc065f696ac8eb46b1549cd66a24135d7b67fb61f96",
    },
    "s2_independent": {
        "path": "reports/v0-s2/full-v0-auto-08/independent-review.json",
        "sha256": "b6e1e8470d9ef12dba40ac0d3a90b0c96ea5f7fcd906f07001118b7370224d1a",
    },
    "unified_human": {
        "path": "reports/unified-media/human-signoff-live15.json",
        "sha256": "fab689dc6563fc343e38b8acb645cee45622bf6216f567e5a32a27bcabf73bc9",
    },
    "unified_coverage": {
        "path": "reports/unified-media/independent-live-15/coverage.json",
        "sha256": "f3e0b494e88a48ce586dc6bab0c96d6fc850d22f5252f4d0859c41e792256b20",
    },
    "capability_map": {
        "path": "reports/v0-s3/handoff-capability-map-01.json",
        "sha256": "d3ece8c2862b779919a57293361d906d6ffa2d6e351224c828311618ec36dd24",
    },
}

# Authority documents that are fenced by the packet manifests but are not
# part of the predicate proof list.
DECISION_PIN = {
    "path": "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.approved-decision.json",
    "sha256": "8e4678ff068a6485f42ca189a161ad67e7ba8bd94f52c8e30418938546e2e528",
}
CHILD_PIN = {
    "path": "reports/v0-s3/preparation-03/asset-inventory-child.json",
    "sha256": "50f3db0b9f9263b268cce15b4b150c1bf972250688725cab003856d08e739c4a",
}
UM_INDEPENDENT_REL = "reports/unified-media/independent-live-15/receipt.json"

PRODUCTION_PINS = {
    "proofs": PROOF_PINS,
    "decision": DECISION_PIN,
    "child": CHILD_PIN,
    "spec_manifest": {"path": SPEC_MANIFEST_REL, "sha256": SPEC_MANIFEST_SHA256},
    "payload_manifest": {"path": PAYLOAD_MANIFEST_REL, "sha256": PAYLOAD_MANIFEST_SHA256},
}

# Predicate fields that must not silently change meaning.
PREDICATE_FLAGS = {
    "gate0_still_required": True,
    "authorizes_old_s2_release": False,
    "may_apply_to_other_dependency_edges": False,
    "product_execution_authorized_by_predicate_alone": False,
}
HISTORICAL_S2_PROJECTION = {
    "completed_substeps": 7,
    "total_substeps": 8,
    "human_signoff": "PENDING",
}

# --------------------------------------------------------------------------
# The ACTUAL old-S2 projection, read live out of ``plans/execution-control.json``.
#
# The owner rule (AGENTS.md rule 24 / ADR-14) preserves the actual historical
# V0-S2 state, not only the declared predicate snapshot.  These constants are
# the *expected* values; the *observed* values are reported next to them and
# are never silently asserted as 7/8.
# --------------------------------------------------------------------------
EXPECTED_S2_COMPLETED_SUBSTEPS = 7
EXPECTED_S2_TOTAL_SUBSTEPS = 8
EXPECTED_S2_HUMAN_SIGNOFF = "PENDING"
EXPECTED_S2_HUMAN_SUBSTEP_NAME = "S2 人工签署与Git同步"

# The retained historical coordinate is a snapshot, not a second live
# coordinate: it must stay exactly as recorded.
EXPECTED_HISTORICAL_S2_COORDINATE = {
    "stage_id": "V0-S2",
    "workpack_id": "WP-S2-06",
    "gate": "GATE5_HUMAN_EXPERIENCE_SIGNOFF",
    "state": "WAIT_HUMAN",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Report:
    """Ordered check ledger with stable diagnostic identifiers."""

    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, identifier: str, passed: bool, detail: str = "") -> bool:
        self.checks.append(
            {"id": identifier, "passed": bool(passed), "detail": str(detail)}
        )
        return bool(passed)

    @property
    def failed(self) -> list[dict]:
        return [item for item in self.checks if not item["passed"]]


def load_json(root: Path, relative: str, report: Report, identifier: str):
    """Read one JSON object, recording a stable diagnostic on any defect."""
    path = root / relative
    if not path.is_file():
        report.add(identifier + ".present", False, "missing file: " + relative)
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.add(identifier + ".readable", False, "%s: %s" % (relative, exc))
        return None
    try:
        data = json.loads(raw)
    except ValueError as exc:
        report.add(
            identifier + ".malformed_json",
            False,
            "malformed JSON in %s: %s" % (relative, exc),
        )
        return None
    if not isinstance(data, dict):
        report.add(
            identifier + ".malformed_container",
            False,
            "top level of %s is not a JSON object" % relative,
        )
        return None
    report.add(identifier + ".readable", True, relative)
    return data


def check_file_hash(root: Path, relative: str, expected: str, report: Report, identifier: str) -> bool:
    path = root / relative
    if not path.is_file():
        report.add(identifier, False, "missing file: " + relative)
        return False
    actual = sha256_file(path)
    return report.add(
        identifier,
        actual == expected,
        "%s expected=%s actual=%s" % (relative, expected, actual),
    )


def check_source_fence(root: Path, pins: dict, report: Report) -> None:
    """The 16 source files and the 10 packet payload files must be frozen."""
    spec_rel = pins["spec_manifest"]["path"]
    payload_rel = pins["payload_manifest"]["path"]
    check_file_hash(root, spec_rel, pins["spec_manifest"]["sha256"], report, "fence.spec_manifest.sha256")
    check_file_hash(
        root, payload_rel, pins["payload_manifest"]["sha256"], report, "fence.payload_manifest.sha256"
    )

    spec = load_json(root, spec_rel, report, "fence.spec_manifest")
    if spec is None:
        return
    files = spec.get("files")
    if not isinstance(files, dict):
        report.add("fence.spec_manifest.container", False, "spec-manifest has no files object")
        return
    report.add(
        "fence.spec_manifest.container",
        True,
        "kind=%s files=%d" % (spec.get("kind"), len(files)),
    )
    report.add(
        "fence.source_file_count",
        len(files) == SOURCE_FENCE_COUNT,
        "expected %d source fence files, found %d" % (SOURCE_FENCE_COUNT, len(files)),
    )
    mismatched = []
    for relative in sorted(files):
        expected = files[relative]
        path = root / relative
        if not path.is_file():
            mismatched.append(relative + " (missing)")
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatched.append("%s (expected %s actual %s)" % (relative, expected, actual))
    report.add(
        "fence.source_files",
        not mismatched,
        "all %d source fence hashes match" % len(files) if not mismatched else "; ".join(mismatched),
    )

    payload_path = root / payload_rel
    if not payload_path.is_file():
        report.add("fence.payload_files", False, "missing payload manifest")
        return
    entries = []
    for line in payload_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            report.add("fence.payload_files", False, "malformed payload manifest line: %r" % line)
            return
        entries.append((name.strip(), digest.strip()))
    report.add(
        "fence.payload_file_count",
        len(entries) == PAYLOAD_FENCE_COUNT,
        "expected %d packet payload files, found %d" % (PAYLOAD_FENCE_COUNT, len(entries)),
    )
    bad = []
    for name, digest in entries:
        target = (root / payload_rel).parent / name
        if not target.is_file():
            bad.append(name + " (missing)")
            continue
        actual = sha256_file(target)
        if actual != digest:
            bad.append("%s (expected %s actual %s)" % (name, digest, actual))
    report.add(
        "fence.payload_files",
        not bad,
        "all %d packet payload hashes match" % len(entries) if not bad else "; ".join(bad),
    )


def extract_predicates(tasks: dict, v1plan: dict, execution: dict, report: Report) -> list:
    """Return the three predicate snapshots, recording diagnostics."""
    found = []

    overrides = tasks.get("dependency_gate_overrides")
    if not isinstance(overrides, list):
        report.add("predicate.tasks.container", False, "dependency_gate_overrides is not a list")
        overrides = []
    else:
        report.add("predicate.tasks.container", True, "entries=%d" % len(overrides))
    matching = [item for item in overrides if isinstance(item, dict) and item.get("id") == PREDICATE_ID]
    report.add(
        "predicate.tasks.occurrence",
        len(matching) == 1,
        "predicate id occurrences in plans/tasks.json: %d" % len(matching),
    )
    others = [item.get("id") for item in overrides if isinstance(item, dict) and item.get("id") != PREDICATE_ID]
    report.add(
        "predicate.tasks.no_unsanctioned_alias",
        not others,
        "no additional dependency-gate aliases" if not others else "unsanctioned aliases: %r" % (others,),
    )
    if matching:
        found.append(("tasks", matching[0]))

    for label, document, key in (
        ("v1plan", v1plan, "v1_only_s2_handoff"),
        ("execution", execution, "v1_only_s2_handoff"),
    ):
        value = document.get(key)
        if not isinstance(value, dict):
            report.add("predicate.%s.container" % label, False, "%s is missing %s" % (label, key))
            continue
        report.add("predicate.%s.container" % label, True, key)
        found.append((label, value))

    for label, value in found:
        report.add(
            "predicate.%s.id" % label,
            value.get("id") == PREDICATE_ID,
            "id=%r" % value.get("id"),
        )
    return found


def check_predicate_shape(predicate: dict, report: Report, label: str, pins: dict) -> None:
    report.add(
        "%s.consumer_stage" % label,
        predicate.get("consumer_stage") == CONSUMER_STAGE,
        "consumer_stage=%r (only %s is eligible)" % (predicate.get("consumer_stage"), CONSUMER_STAGE),
    )
    report.add(
        "%s.dependency_stage" % label,
        predicate.get("dependency_stage") == DEPENDENCY_STAGE,
        "dependency_stage=%r (only %s is eligible)" % (predicate.get("dependency_stage"), DEPENDENCY_STAGE),
    )
    report.add(
        "%s.purpose" % label,
        predicate.get("purpose") == PURPOSE,
        "purpose=%r (only %s is eligible)" % (predicate.get("purpose"), PURPOSE),
    )
    report.add(
        "%s.approved_change" % label,
        predicate.get("approved_change") == CHANGE_ID,
        "approved_change=%r" % predicate.get("approved_change"),
    )
    proofs = predicate.get("proofs")
    report.add(
        "%s.proofs_pinned" % label,
        proofs == pins["proofs"],
        "predicate proof hashes match the frozen owner pins"
        if proofs == pins["proofs"]
        else "predicate proof hashes differ from the frozen owner pins",
    )
    report.add(
        "%s.historical_s2_projection" % label,
        predicate.get("historical_s2_required_state") == HISTORICAL_S2_PROJECTION,
        "historical_s2_required_state=%r (must stay 7/8 with native human PENDING)"
        % (predicate.get("historical_s2_required_state"),),
    )
    report.add(
        "%s.s2_machine_candidate" % label,
        predicate.get("s2_machine_candidate") == S2_MACHINE_CANDIDATE,
        "s2_machine_candidate=%r" % predicate.get("s2_machine_candidate"),
    )
    report.add(
        "%s.unified_human_candidate" % label,
        predicate.get("unified_human_candidate") == UM_HUMAN_CANDIDATE,
        "unified_human_candidate=%r" % predicate.get("unified_human_candidate"),
    )
    report.add(
        "%s.required_s2_case_ids" % label,
        tuple(predicate.get("required_s2_case_ids") or ()) == REQUIRED_S2_CASE_IDS,
        "required_s2_case_ids=%r" % (predicate.get("required_s2_case_ids"),),
    )
    report.add(
        "%s.required_unified_case_ids" % label,
        tuple(predicate.get("required_unified_case_ids") or ()) == REQUIRED_UM_CASE_IDS,
        "required_unified_case_ids=%r" % (predicate.get("required_unified_case_ids"),),
    )
    for flag, expected in PREDICATE_FLAGS.items():
        report.add(
            "%s.flag.%s" % (label, flag),
            predicate.get(flag) == expected,
            "%s=%r (expected %r)" % (flag, predicate.get(flag), expected),
        )


def check_scope_approval(root: Path, pins: dict, report: Report) -> None:
    approval_pin = pins["proofs"]["scope_approval"]
    request_pin = pins["proofs"]["scope_request"]
    check_file_hash(root, approval_pin["path"], approval_pin["sha256"], report, "approval.sha256")
    check_file_hash(root, request_pin["path"], request_pin["sha256"], report, "request.sha256")
    check_file_hash(
        root, pins["decision"]["path"], pins["decision"]["sha256"], report, "decision.sha256"
    )

    approval = load_json(root, approval_pin["path"], report, "approval")
    request = load_json(root, request_pin["path"], report, "request")
    decision = load_json(root, pins["decision"]["path"], report, "decision")
    if approval is None or request is None or decision is None:
        return

    report.add(
        "approval.id",
        approval.get("id") == CHANGE_ID,
        "id=%r (expected %s)" % (approval.get("id"), CHANGE_ID),
    )
    report.add(
        "approval.decision",
        approval.get("decision") == "APPROVED",
        "decision=%r (expected APPROVED)" % approval.get("decision"),
    )
    report.add(
        "approval.scope",
        approval.get("scope") == "V1_DEVELOPMENT_HANDOFF_ONLY",
        "scope=%r" % approval.get("scope"),
    )
    report.add(
        "approval.request_path",
        approval.get("request") == request_pin["path"],
        "request=%r" % approval.get("request"),
    )
    report.add(
        "approval.binds_exact_request",
        approval.get("request_sha256") == request_pin["sha256"],
        "approval.request_sha256=%r (expected %s)" % (approval.get("request_sha256"), request_pin["sha256"]),
    )
    report.add(
        "request.id",
        request.get("id") == CHANGE_ID,
        "id=%r (expected %s)" % (request.get("id"), CHANGE_ID),
    )
    report.add(
        "approval.historical_s2_not_signed",
        approval.get("historical_s2_native_human_approved") is False
        and approval.get("historical_s2_completed_substeps") == 7,
        "historical_s2_native_human_approved=%r completed_substeps=%r (must stay False/7)"
        % (approval.get("historical_s2_native_human_approved"), approval.get("historical_s2_completed_substeps")),
    )
    report.add(
        "approval.no_scope_expansion",
        approval.get("full_v1_approved") is False
        and approval.get("release_approved") is False
        and approval.get("runtime_authority_changed") is False,
        "full_v1_approved=%r release_approved=%r runtime_authority_changed=%r"
        % (
            approval.get("full_v1_approved"),
            approval.get("release_approved"),
            approval.get("runtime_authority_changed"),
        ),
    )
    report.add(
        "decision.applied_to_readiness_only",
        decision.get("decision") == "APPROVED_APPLIED_TO_READINESS_ONLY"
        and decision.get("predicate_id") == PREDICATE_ID
        and decision.get("request_sha256") == request_pin["sha256"]
        and decision.get("product_gate0") is False
        and decision.get("product_runtime_started") is False,
        "decision=%r predicate_id=%r product_gate0=%r product_runtime_started=%r"
        % (
            decision.get("decision"),
            decision.get("predicate_id"),
            decision.get("product_gate0"),
            decision.get("product_runtime_started"),
        ),
    )


def check_s2_machine(root: Path, pins: dict, report: Report) -> None:
    pin = pins["proofs"]["s2_machine"]
    check_file_hash(root, pin["path"], pin["sha256"], report, "evidence.s2_machine.sha256")
    receipt = load_json(root, pin["path"], report, "evidence.s2_machine")
    if receipt is None:
        return
    report.add(
        "evidence.s2_machine.candidate",
        receipt.get("candidate_sha") == S2_MACHINE_CANDIDATE,
        "candidate_sha=%r (expected %s)" % (receipt.get("candidate_sha"), S2_MACHINE_CANDIDATE),
    )
    cases = receipt.get("cases")
    if not isinstance(cases, dict):
        report.add("evidence.s2_machine.cases", False, "receipt has no cases object")
    else:
        report.add(
            "evidence.s2_machine.case_set",
            set(cases) == set(REQUIRED_S2_CASE_IDS),
            "case ids=%r (expected exactly the nine required ids)"
            % sorted(cases),
        )
        report.add(
            "evidence.s2_machine.case_status",
            all(cases.get(case) == "PASS" for case in REQUIRED_S2_CASE_IDS),
            "every required case must be PASS",
        )
    counts = receipt.get("test_counts") if isinstance(receipt.get("test_counts"), dict) else {}
    report.add(
        "evidence.s2_machine.counts",
        counts.get("PASS") == 9
        and counts.get("FAIL") == 0
        and counts.get("BLOCKED") == 0
        and counts.get("NOT_RUN") == 0
        and counts.get("fixed") == 9,
        "test_counts=%r (expected 9 PASS / 0 others)" % (counts,),
    )
    report.add(
        "evidence.s2_machine.no_stage_pass",
        receipt.get("stage_pass_claim") is False,
        "stage_pass_claim=%r" % receipt.get("stage_pass_claim"),
    )


def check_s2_independent(root: Path, pins: dict, report: Report) -> None:
    pin = pins["proofs"]["s2_independent"]
    check_file_hash(root, pin["path"], pin["sha256"], report, "evidence.s2_independent.sha256")
    review = load_json(root, pin["path"], report, "evidence.s2_independent")
    if review is None:
        return
    report.add(
        "evidence.s2_independent.candidate",
        review.get("candidate_sha") == S2_MACHINE_CANDIDATE,
        "candidate_sha=%r (expected %s)" % (review.get("candidate_sha"), S2_MACHINE_CANDIDATE),
    )
    report.add(
        "evidence.s2_independent.nine_of_nine",
        review.get("cumulative_pass") == 9 and review.get("cumulative_fixed_cases") == 9,
        "cumulative_pass=%r cumulative_fixed_cases=%r (expected 9/9)"
        % (review.get("cumulative_pass"), review.get("cumulative_fixed_cases")),
    )
    findings = review.get("findings") if isinstance(review.get("findings"), dict) else {}
    report.add(
        "evidence.s2_independent.no_fatal_or_major",
        findings.get("Fatal") == 0 and findings.get("Major") == 0,
        "findings=%r (Fatal and Major must be 0)" % (findings,),
    )
    report.add(
        "evidence.s2_independent.isolated_read_only",
        review.get("context_isolated") is True and review.get("read_only") is True,
        "context_isolated=%r read_only=%r" % (review.get("context_isolated"), review.get("read_only")),
    )
    report.add(
        "evidence.s2_independent.human_signoff_still_absent",
        review.get("human_signoff") is None,
        "human_signoff=%r (historical S2 native human signature stays absent)" % review.get("human_signoff"),
    )
    report.add(
        "evidence.s2_independent.no_stage_pass",
        review.get("stage_pass_claim") is False,
        "stage_pass_claim=%r" % review.get("stage_pass_claim"),
    )


def check_unified_media(root: Path, pins: dict, report: Report) -> None:
    human_pin = pins["proofs"]["unified_human"]
    coverage_pin = pins["proofs"]["unified_coverage"]
    check_file_hash(root, human_pin["path"], human_pin["sha256"], report, "evidence.um_human.sha256")
    check_file_hash(root, coverage_pin["path"], coverage_pin["sha256"], report, "evidence.um_coverage.sha256")
    signoff = load_json(root, human_pin["path"], report, "evidence.um_human")
    coverage = load_json(root, coverage_pin["path"], report, "evidence.um_coverage")
    if signoff is None or coverage is None:
        return
    report.add(
        "evidence.um_human.approved",
        signoff.get("decision") == "APPROVED" and signoff.get("signer_role") == "project_owner",
        "decision=%r signer_role=%r" % (signoff.get("decision"), signoff.get("signer_role")),
    )
    report.add(
        "evidence.um_human.candidate",
        signoff.get("product_candidate") == UM_HUMAN_CANDIDATE,
        "product_candidate=%r (expected %s)" % (signoff.get("product_candidate"), UM_HUMAN_CANDIDATE),
    )
    report.add(
        "evidence.um_human.slice",
        signoff.get("slice_id") == "UNIFIED_MEDIA_EARLY",
        "slice_id=%r" % signoff.get("slice_id"),
    )
    report.add(
        "evidence.um_coverage.candidate",
        coverage.get("candidate_sha") == UM_HUMAN_CANDIDATE,
        "candidate_sha=%r (expected %s)" % (coverage.get("candidate_sha"), UM_HUMAN_CANDIDATE),
    )
    report.add(
        "evidence.um_coverage.fixed_denominator",
        coverage.get("fixed_denominator") == 10,
        "fixed_denominator=%r (expected 10)" % coverage.get("fixed_denominator"),
    )
    rows = coverage.get("rows")
    if not isinstance(rows, list):
        report.add("evidence.um_coverage.rows", False, "coverage has no rows list")
        return
    by_id = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            by_id[row["id"]] = row
    report.add(
        "evidence.um_coverage.case_set",
        set(by_id) == set(REQUIRED_UM_CASE_IDS),
        "coverage case ids=%r (expected exactly UM-01..UM-10)" % sorted(by_id),
    )
    report.add(
        "evidence.um_coverage.all_pass",
        all(by_id.get(case, {}).get("status") == "PASS" for case in REQUIRED_UM_CASE_IDS),
        "every UM case must be PASS",
    )
    independent = load_json(root, UM_INDEPENDENT_REL, report, "evidence.um_independent")
    if independent is not None:
        report.add(
            "evidence.um_independent.informational",
            independent.get("candidate_sha") == UM_HUMAN_CANDIDATE
            and independent.get("stage_pass_claim") is False,
            "decision=%r candidate_sha=%r"
            % (independent.get("decision"), independent.get("candidate_sha")),
        )


def check_capability_map(root: Path, pins: dict, report: Report) -> None:
    pin = pins["proofs"]["capability_map"]
    check_file_hash(root, pin["path"], pin["sha256"], report, "map.sha256")
    capability = load_json(root, pin["path"], report, "map")
    if capability is None:
        return
    report.add(
        "map.status",
        capability.get("status") == "FROZEN_READINESS_MAPPING_ONLY",
        "status=%r" % capability.get("status"),
    )
    report.add(
        "map.new_s3_cases",
        tuple(capability.get("required_new_s3_cases") or ()) == NEW_S3_CASE_IDS,
        "required_new_s3_cases=%r (install/rollback + image + video quality duties)"
        % (capability.get("required_new_s3_cases"),),
    )
    report.add(
        "map.cumulative_cases",
        tuple(capability.get("all_s3_cumulative_cases") or ()) == ALL_S3_CASE_IDS,
        "all_s3_cumulative_cases=%r (expected the full twelve)" % (capability.get("all_s3_cumulative_cases"),),
    )
    mapping = capability.get("mapping")
    if not isinstance(mapping, list) or not mapping:
        report.add("map.mapping_entries", False, "mapping must be a non-empty list")
    else:
        report.add("map.mapping_entries", True, "capability groups=%d" % len(mapping))
        complete = all(
            isinstance(entry, dict)
            and entry.get("capability")
            and isinstance(entry.get("old_cases"), list)
            and isinstance(entry.get("current_cases"), list)
            and entry.get("scope")
            for entry in mapping
        )
        report.add("map.mapping_entries_wellformed", complete, "each group needs capability/old_cases/current_cases/scope")
    report.add(
        "map.no_inherited_quality",
        capability.get("quality_coverage_inherited") is False
        and capability.get("future_candidate_results_inherited") is False,
        "quality_coverage_inherited=%r future_candidate_results_inherited=%r"
        % (capability.get("quality_coverage_inherited"), capability.get("future_candidate_results_inherited")),
    )
    report.add(
        "map.historical_s2_not_signed",
        capability.get("historical_s2_signed") is False,
        "historical_s2_signed=%r" % capability.get("historical_s2_signed"),
    )
    report.add(
        "map.product_gate0_false",
        capability.get("product_gate0") is False,
        "product_gate0=%r" % capability.get("product_gate0"),
    )


def check_stage_packet(root: Path, pins: dict, report: Report) -> None:
    control = load_json(root, PACKET_REL + "/stage-control.json", report, "packet.stage_control")
    if control is None:
        return
    report.add(
        "packet.stage_control.predicate",
        control.get("dependency_predicate") == PREDICATE_ID,
        "dependency_predicate=%r" % control.get("dependency_predicate"),
    )
    report.add(
        "packet.stage_control.preparation_only",
        control.get("product_execution_authorized") is False
        and control.get("stage_pass_forbidden") is True
        and str(control.get("state", "")).startswith("FROZEN_PREPARATION_ONLY"),
        "state=%r product_execution_authorized=%r stage_pass_forbidden=%r"
        % (control.get("state"), control.get("product_execution_authorized"), control.get("stage_pass_forbidden")),
    )
    workpacks = control.get("workpacks")
    commands = []
    if isinstance(workpacks, list):
        for workpack in workpacks:
            if isinstance(workpack, dict) and isinstance(workpack.get("commands"), list):
                commands.extend(str(item) for item in workpack["commands"])
    report.add(
        "packet.stage_control.commands",
        "python3 -B tools/verify_s3_handoff.py" in commands
        and "python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py -q" in commands,
        "frozen workpack commands: %r" % (commands,),
    )


def _observed_s2_projection(execution: dict) -> dict:
    """Read the observed old-S2 projection without asserting any expected value.

    Every defect fails closed: a missing, duplicated or malformed stage entry
    yields ``None`` for every field, never the declared 7/8 expectation.
    """
    observed = {"completed_substeps": None, "total_substeps": None, "human_signoff": None}
    if not isinstance(execution, dict):
        return observed
    outline = execution.get("development_outline")
    if not isinstance(outline, list):
        return observed
    entries = [
        item
        for item in outline
        if isinstance(item, dict) and item.get("stage_id") == "V0-S2"
    ]
    if len(entries) != 1:
        return observed
    entry = entries[0]
    observed["completed_substeps"] = entry.get("completed_substeps")
    observed["total_substeps"] = entry.get("total_substeps")
    observed["human_signoff"] = entry.get("human_signoff")
    return observed


def check_actual_s2_projection(execution: dict, report: Report) -> dict:
    """Assert the ACTUAL old-S2 projection carried by the live execution authority.

    ``plans/execution-control.json`` is the mutable execution coordinate and is
    therefore never hash-frozen.  It is read and *interpreted*: the live
    ``development_outline`` entry ``V0-S2`` must keep exactly eight substeps of
    which seven are ``DONE`` and exactly one -- the native human step -- stays
    ``PENDING`` with null evidence, the counters must stay integer 7 of 8 and
    the native human signoff must stay ``PENDING``.  The retained
    ``historical_s2_coordinate`` snapshot must stay exactly as recorded.

    The live ``coordinate`` / ``current_blocking_gate`` / ``updated_at`` fields
    are deliberately NOT touched here: they are free to advance.
    """
    execution = execution if isinstance(execution, dict) else {}
    first_check = len(report.checks)
    observed = _observed_s2_projection(execution)

    outline = execution.get("development_outline")
    report.add(
        "actual.outline.container",
        isinstance(outline, list),
        "development_outline is %s (a list of stage objects is required)"
        % type(outline).__name__,
    )
    entries = []
    if isinstance(outline, list):
        entries = [
            item
            for item in outline
            if isinstance(item, dict) and item.get("stage_id") == "V0-S2"
        ]
    report.add(
        "actual.outline.v0_s2_occurrence",
        len(entries) == 1,
        "development_outline entries with stage_id 'V0-S2': %d (exactly one required)"
        % len(entries),
    )
    entry = entries[0] if len(entries) == 1 else {}

    completed = entry.get("completed_substeps")
    report.add(
        "actual.outline.completed_substeps",
        isinstance(completed, int)
        and not isinstance(completed, bool)
        and completed == EXPECTED_S2_COMPLETED_SUBSTEPS,
        "observed completed_substeps=%r (expected integer %d)"
        % (completed, EXPECTED_S2_COMPLETED_SUBSTEPS),
    )
    total = entry.get("total_substeps")
    report.add(
        "actual.outline.total_substeps",
        isinstance(total, int)
        and not isinstance(total, bool)
        and total == EXPECTED_S2_TOTAL_SUBSTEPS,
        "observed total_substeps=%r (expected integer %d)"
        % (total, EXPECTED_S2_TOTAL_SUBSTEPS),
    )
    signoff = entry.get("human_signoff")
    report.add(
        "actual.outline.human_signoff",
        signoff == EXPECTED_S2_HUMAN_SIGNOFF,
        "observed human_signoff=%r (expected %r)" % (signoff, EXPECTED_S2_HUMAN_SIGNOFF),
    )

    substeps = entry.get("substeps")
    report.add(
        "actual.outline.substeps_container",
        isinstance(substeps, list),
        "substeps is %s (a list of substep objects is required)" % type(substeps).__name__,
    )
    substeps = substeps if isinstance(substeps, list) else []
    report.add(
        "actual.outline.substep_count",
        len(substeps) == EXPECTED_S2_TOTAL_SUBSTEPS,
        "substep count=%d (expected exactly %d)" % (len(substeps), EXPECTED_S2_TOTAL_SUBSTEPS),
    )
    statuses = [item.get("status") for item in substeps if isinstance(item, dict)]
    report.add(
        "actual.outline.substep_status_vocabulary",
        len(statuses) == len(substeps)
        and all(status in ("DONE", "PENDING") for status in statuses),
        "substep statuses=%r (only DONE and PENDING are allowed)" % (statuses,),
    )
    done = [item for item in substeps if isinstance(item, dict) and item.get("status") == "DONE"]
    pending = [item for item in substeps if isinstance(item, dict) and item.get("status") == "PENDING"]
    report.add(
        "actual.outline.done_count",
        len(done) == EXPECTED_S2_COMPLETED_SUBSTEPS,
        "DONE substeps=%d (expected exactly %d)" % (len(done), EXPECTED_S2_COMPLETED_SUBSTEPS),
    )
    report.add(
        "actual.outline.pending_count",
        len(pending) == 1,
        "PENDING substeps=%d (expected exactly 1)" % len(pending),
    )
    report.add(
        "actual.outline.done_substep_evidence",
        len(done) == EXPECTED_S2_COMPLETED_SUBSTEPS
        and all(isinstance(item.get("evidence"), str) and item.get("evidence") for item in done),
        "every DONE substep must carry a non-empty evidence path",
    )
    human = [
        item
        for item in substeps
        if isinstance(item, dict) and item.get("name") == EXPECTED_S2_HUMAN_SUBSTEP_NAME
    ]
    report.add(
        "actual.outline.human_substep_present",
        len(human) == 1,
        "substeps named %r: %d (exactly one required)"
        % (EXPECTED_S2_HUMAN_SUBSTEP_NAME, len(human)),
    )
    human_step = human[0] if len(human) == 1 else {}
    report.add(
        "actual.outline.human_substep_pending",
        human_step.get("status") == "PENDING",
        "the native human substep status=%r (expected PENDING)"
        % (human_step.get("status"),),
    )
    report.add(
        "actual.outline.human_substep_evidence_null",
        "evidence" in human_step and human_step.get("evidence") is None,
        "the native human substep evidence=%r (expected null)"
        % (human_step.get("evidence"),),
    )

    coordinate = execution.get("historical_s2_coordinate")
    report.add(
        "actual.historical_s2_coordinate.container",
        isinstance(coordinate, dict),
        "historical_s2_coordinate is %s" % type(coordinate).__name__,
    )
    coordinate = coordinate if isinstance(coordinate, dict) else {}
    for field in sorted(EXPECTED_HISTORICAL_S2_COORDINATE):
        expected = EXPECTED_HISTORICAL_S2_COORDINATE[field]
        report.add(
            "actual.historical_s2_coordinate.%s" % field,
            coordinate.get(field) == expected,
            "%s=%r (the retained historical snapshot must stay %r)"
            % (field, coordinate.get(field), expected),
        )
    report.add(
        "actual.historical_s2_coordinate.exact_keys",
        set(coordinate) == set(EXPECTED_HISTORICAL_S2_COORDINATE),
        "historical_s2_coordinate keys=%r (expected exactly %r)"
        % (sorted(coordinate), sorted(EXPECTED_HISTORICAL_S2_COORDINATE)),
    )

    failed = [item for item in report.checks[first_check:] if not item["passed"]]
    return {
        "projection": observed,
        "coordinate": coordinate if isinstance(execution.get("historical_s2_coordinate"), dict) else None,
        "ok": not failed,
    }


def evaluate(root: Path = None, pins: dict = None) -> dict:
    """Evaluate the handoff predicate under ``root``.

    ``pins`` defaults to the frozen owner pins.  Tests may inject a different
    pin mapping; such a run is explicitly labelled non-authority.
    """
    root = Path(root) if root is not None else ROOT
    pins = pins if pins is not None else PRODUCTION_PINS
    report = Report()

    check_source_fence(root, pins, report)
    check_stage_packet(root, pins, report)

    tasks = load_json(root, "plans/tasks.json", report, "plans.tasks")
    v1plan = load_json(root, "plans/v1-revised-plan.json", report, "plans.v1plan")
    execution = load_json(root, "plans/execution-control.json", report, "plans.execution")
    if tasks is not None and v1plan is not None and execution is not None:
        found = extract_predicates(tasks, v1plan, execution, report)
        if len(found) == 3:
            report.add(
                "predicate.equality",
                found[0][1] == found[1][1] == found[2][1],
                "the predicate snapshot must be identical in tasks.json, v1-revised-plan.json "
                "and execution-control.json",
            )
            for label, predicate in found:
                check_predicate_shape(predicate, report, "predicate." + label, pins)

    check_scope_approval(root, pins, report)
    check_s2_machine(root, pins, report)
    check_s2_independent(root, pins, report)
    check_unified_media(root, pins, report)
    check_capability_map(root, pins, report)

    # The ACTUAL old-S2 projection, read live out of the execution authority.
    actual = check_actual_s2_projection(execution if execution is not None else {}, report)
    observed_projection = actual["projection"]

    failed = report.failed
    canonical = root.resolve() == ROOT.resolve()
    overridden = pins != PRODUCTION_PINS
    if not canonical and overridden:
        authority = "FIXTURE_NON_AUTHORITY_COPY_AND_PIN_OVERRIDE"
    elif not canonical:
        authority = "FIXTURE_NON_AUTHORITY_COPY"
    elif overridden:
        authority = "FIXTURE_NON_AUTHORITY_PIN_OVERRIDE"
    else:
        authority = "AUTHORITATIVE"

    result = {
        "kind": "S3_V1_HANDOFF_READINESS_VALIDATION",
        "scope": "HANDOFF_READINESS_ONLY",
        "authority": authority,
        "evaluated_root_is_canonical": canonical,
        "pins_overridden": overridden,
        "predicate_id": PREDICATE_ID,
        "approved_change": CHANGE_ID,
        "eligible_edge": {
            "consumer_stage": CONSUMER_STAGE,
            "dependency_stage": DEPENDENCY_STAGE,
            "purpose": PURPOSE,
        },
        "historical_s2_projection": dict(observed_projection),
        "historical_s2_declared_expected_state": dict(HISTORICAL_S2_PROJECTION),
        "historical_s2_projection_source": (
            "plans/execution-control.json#/development_outline (stage_id=V0-S2)"
        ),
        "historical_s2_coordinate_observed": actual["coordinate"],
        "product_gate0": False,
        "stage_pass_claim": False,
        "product_execution_authorized": False,
        "authorizes_model_execution": False,
        "authorizes_any_other_stage": False,
        "execution_coordinates_frozen": False,
        "historical_s2_coordinate_snapshot_enforced": True,
        "notes": [
            "HANDOFF_READINESS_ONLY: this validator proves the approved V1-only dependency predicate only.",
            "It never authorises model execution, product Gate0, a Stage PASS or any other dependency edge.",
            "The live old-S2 projection is READ from plans/execution-control.json and asserted semantically; "
            "that document is never hash-frozen and no copied snapshot or checksum stands in for it.",
            "The mutable live coordinate (coordinate / current_blocking_gate / updated_at) stays free to advance.",
            "The retained historical_s2_coordinate snapshot must stay V0-S2 / WP-S2-06 / "
            "GATE5_HUMAN_EXPERIENCE_SIGNOFF / WAIT_HUMAN.",
        ]
        + (
            [
                "Observed historical V0-S2 projection in plans/execution-control.json: "
                "7/8 substeps with native human signoff PENDING."
            ]
            if actual["ok"]
            else [
                "Observed historical V0-S2 projection in plans/execution-control.json does NOT match "
                "the declared expectation; see the failed actual.* checks (no 7/8 is asserted here)."
            ]
        ),
        "summary": {
            "checks": len(report.checks),
            "passed": len(report.checks) - len(failed),
            "failed": len(failed),
        },
        "checks": report.checks,
    }
    result["decision"] = "HANDOFF_READINESS_VERIFIED" if not failed else "HANDOFF_READINESS_REJECTED"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the approved V1-only S2->S3 handoff predicate (readiness only)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="LVW package root to validate (default: the directory holding tools/)",
    )
    args = parser.parse_args(argv)
    result = evaluate(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
    if result["decision"] != "HANDOFF_READINESS_VERIFIED":
        for item in result["checks"]:
            if not item["passed"]:
                print("FAIL %s: %s" % (item["id"], item["detail"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
