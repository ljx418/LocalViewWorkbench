#!/usr/bin/env python3
"""Tests for tools/verify_s3_handoff.py (V0-S3 preparation, ADR-14).

Every negative test builds a *synthetic* package tree under pytest's
``tmp_path`` by copying the frozen authority files and then mutating only that
copy.  The canonical plans, packets and evidence in this repository are never
written to.

The positive test runs against the real repository tree and asserts the real
owner proof, so a broken authority file is a test failure, not a silent pass.

Run: python3 -B -m pytest tools/test_verify_s3_handoff.py -q
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_s3_handoff as checker  # noqa: E402

PACKET_REL = ".agent-governance/stages/V0-S3"
APPROVAL_REL = "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.approval.json"
REQUEST_REL = "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.request.json"
S2_MACHINE_REL = "reports/v0-s2/full-v0-auto-08/receipt.json"
UM_COVERAGE_REL = "reports/unified-media/independent-live-15/coverage.json"
CAPABILITY_MAP_REL = "reports/v0-s3/handoff-capability-map-01.json"
EXECUTION_REL = "plans/execution-control.json"
TASKS_REL = "plans/tasks.json"
V1PLAN_REL = "plans/v1-revised-plan.json"


def authority_files() -> list:
    """Every file the checker reads, derived from the frozen packet manifests."""
    files = set(json.loads((ROOT / PACKET_REL / "spec-manifest.json").read_text(encoding="utf-8"))["files"])
    for line in (ROOT / PACKET_REL / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            files.add(PACKET_REL + "/" + line.split("  ", 1)[1].strip())
    files.add(EXECUTION_REL)
    files.add(PACKET_REL + "/PAYLOAD_MANIFEST.sha256")
    files.add("reports/unified-media/independent-live-15/receipt.json")
    return sorted(files)


AUTHORITY_FILES = authority_files()


def build_tree(root: Path) -> Path:
    """Copy the frozen authority files into a synthetic package tree."""
    for relative in AUTHORITY_FILES:
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def read_json(root: Path, relative: str):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload) -> None:
    (root / relative).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def failed_ids(result: dict) -> set:
    return {item["id"] for item in result["checks"] if not item["passed"]}


def evaluate_tree(root: Path) -> dict:
    return checker.evaluate(root)


# --------------------------------------------------------------------------
# positive owner proof
# --------------------------------------------------------------------------


def test_real_repository_authority_verifies():
    result = checker.evaluate(ROOT)
    assert result["decision"] == "HANDOFF_READINESS_VERIFIED", failed_ids(result)
    assert result["summary"]["failed"] == 0
    assert result["summary"]["checks"] > 50
    assert result["authority"] == "AUTHORITATIVE"


def test_report_states_readiness_only_and_never_a_stage_pass():
    result = checker.evaluate(ROOT)
    assert result["scope"] == "HANDOFF_READINESS_ONLY"
    assert result["product_gate0"] is False
    assert result["stage_pass_claim"] is False
    assert result["product_execution_authorized"] is False
    assert result["authorizes_model_execution"] is False
    assert result["authorizes_any_other_stage"] is False
    assert result["historical_s2_projection"] == {
        "completed_substeps": 7,
        "total_substeps": 8,
        "human_signoff": "PENDING",
    }


def test_public_cli_exits_zero_and_emits_one_json_object():
    process = subprocess.run(
        [sys.executable, "-B", "tools/verify_s3_handoff.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["decision"] == "HANDOFF_READINESS_VERIFIED"
    assert payload["scope"] == "HANDOFF_READINESS_ONLY"
    assert payload["product_gate0"] is False


def test_synthetic_copy_of_the_authority_verifies_and_is_labelled(tmp_path):
    tree = build_tree(tmp_path / "package")
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_VERIFIED", failed_ids(result)
    assert result["authority"] == "FIXTURE_NON_AUTHORITY_COPY"


# --------------------------------------------------------------------------
# the predicate itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "V1_FULL_ACCEPTANCE"),
        ("consumer_stage", "V0-S2"),
        ("dependency_stage", "R1"),
        ("id", "ANY_STAGE_HANDOFF"),
    ],
)
def test_wrong_purpose_consumer_dependency_or_alias_is_rejected(tmp_path, field, value):
    tree = build_tree(tmp_path / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0][field] = value
        else:
            payload["v1_only_s2_handoff"][field] = value
        write_json(tree, relative, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    identifiers = failed_ids(result)
    assert any(identifier.endswith("." + field) for identifier in identifiers), identifiers


def test_an_extra_generic_alias_entry_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, TASKS_REL)
    alias = dict(payload["dependency_gate_overrides"][0])
    alias["id"] = "GENERIC_V1_HANDOFF"
    payload["dependency_gate_overrides"].append(alias)
    write_json(tree, TASKS_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "predicate.tasks.no_unsanctioned_alias" in failed_ids(result)


def test_predicate_must_be_identical_in_all_three_plans(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, EXECUTION_REL)
    payload["v1_only_s2_handoff"]["s2_machine_candidate"] = "0" * 40
    write_json(tree, EXECUTION_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "predicate.equality" in failed_ids(result)


def test_a_shrunk_case_list_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["required_s2_case_ids"].remove("V0-A07")
        else:
            payload["v1_only_s2_handoff"]["required_s2_case_ids"].remove("V0-A07")
        write_json(tree, relative, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert any(identifier.endswith(".required_s2_case_ids") for identifier in failed_ids(result))


def test_fake_old_s2_signoff_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["historical_s2_required_state"] = {
                "completed_substeps": 8,
                "total_substeps": 8,
                "human_signoff": "SIGNED",
            }
        else:
            payload["v1_only_s2_handoff"]["historical_s2_required_state"] = {
                "completed_substeps": 8,
                "total_substeps": 8,
                "human_signoff": "SIGNED",
            }
        write_json(tree, relative, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert any(
        identifier.endswith(".historical_s2_projection") for identifier in failed_ids(result)
    )


def test_approval_claiming_an_old_s2_signature_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, APPROVAL_REL)
    payload["historical_s2_native_human_approved"] = True
    payload["historical_s2_completed_substeps"] = 8
    write_json(tree, APPROVAL_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "approval.historical_s2_not_signed" in failed_ids(result)


def test_approval_that_does_not_bind_the_exact_request_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, APPROVAL_REL)
    payload["request_sha256"] = "0" * 64
    write_json(tree, APPROVAL_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "approval.binds_exact_request" in failed_ids(result)


def test_a_missing_capability_map_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    (tree / CAPABILITY_MAP_REL).unlink()
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    identifiers = failed_ids(result)
    assert "map.sha256" in identifiers
    assert "map.present" in identifiers


def test_a_wrong_machine_candidate_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, S2_MACHINE_REL)
    payload["candidate_sha"] = "0" * 40
    write_json(tree, S2_MACHINE_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "evidence.s2_machine.candidate" in failed_ids(result)


def test_a_non_pass_machine_case_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, S2_MACHINE_REL)
    payload["cases"]["V0-A03"] = "SKIPPED"
    write_json(tree, S2_MACHINE_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "evidence.s2_machine.case_status" in failed_ids(result)


def test_a_missing_um_case_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, UM_COVERAGE_REL)
    payload["rows"] = [row for row in payload["rows"] if row.get("id") != "UM-05"]
    write_json(tree, UM_COVERAGE_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    identifiers = failed_ids(result)
    assert "evidence.um_coverage.case_set" in identifiers
    assert "evidence.um_coverage.all_pass" in identifiers


def test_malformed_json_in_a_plan_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    (tree / TASKS_REL).write_text("{ this is not json", encoding="utf-8")
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "plans.tasks.malformed_json" in failed_ids(result)


def test_a_malformed_payload_manifest_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    (tree / PACKET_REL / "PAYLOAD_MANIFEST.sha256").write_text("garbage\n", encoding="utf-8")
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "fence.payload_files" in failed_ids(result)


def test_a_missing_approval_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    (tree / APPROVAL_REL).unlink()
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "approval.present" in failed_ids(result)


def test_a_tampered_source_fence_file_is_rejected(tmp_path):
    tree = build_tree(tmp_path / "package")
    target = tree / "docs/24_EXECUTION_MASTER_PLAN.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"
    assert "fence.source_files" in failed_ids(result)


# --------------------------------------------------------------------------
# what must NOT be frozen
# --------------------------------------------------------------------------


def test_execution_coordinates_may_advance(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, EXECUTION_REL)
    payload["coordinate"] = {
        "stage_id": "R1",
        "workpack_id": "WP-R1-U3",
        "gate": "S3_GATE0_INPUTS_AND_EXECUTION_PACKET_READINESS",
        "state": "ADVANCED",
    }
    payload["current_blocking_gate"] = "SOMETHING_ELSE"
    payload["updated_at"] = "2026-12-31"
    write_json(tree, EXECUTION_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_VERIFIED", failed_ids(result)
    assert result["execution_coordinates_frozen"] is False


def test_the_historical_s2_coordinate_state_is_not_required_to_stay_wait_human(tmp_path):
    tree = build_tree(tmp_path / "package")
    payload = read_json(tree, EXECUTION_REL)
    payload["historical_s2_coordinate"]["state"] = "ADVANCED_BY_OWNER"
    write_json(tree, EXECUTION_REL, payload)
    result = evaluate_tree(tree)
    assert result["decision"] == "HANDOFF_READINESS_VERIFIED", failed_ids(result)


def test_pin_override_is_labelled_non_authority(tmp_path):
    tree = build_tree(tmp_path / "package")
    pins = json.loads(json.dumps(checker.PRODUCTION_PINS))
    pins["proofs"]["scope_approval"]["sha256"] = "0" * 64
    result = checker.evaluate(tree, pins=pins)
    assert result["authority"] == "FIXTURE_NON_AUTHORITY_COPY_AND_PIN_OVERRIDE"
    assert result["pins_overridden"] is True
    assert result["decision"] == "HANDOFF_READINESS_REJECTED"


def test_proof_pins_match_the_predicate_in_the_real_plans():
    tasks = read_json(ROOT, TASKS_REL)
    predicate = tasks["dependency_gate_overrides"][0]
    assert predicate["proofs"] == checker.PROOF_PINS
    assert predicate["id"] == checker.PREDICATE_ID
    assert predicate["purpose"] == checker.PURPOSE
    assert predicate["consumer_stage"] == checker.CONSUMER_STAGE
    assert predicate["dependency_stage"] == checker.DEPENDENCY_STAGE
    for entry in checker.PROOF_PINS.values():
        actual = hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
        assert actual == entry["sha256"], entry["path"]
