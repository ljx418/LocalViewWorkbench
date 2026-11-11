#!/usr/bin/env python3
"""Negative tests for tools/verify_v1_plan.py.

Every test builds a *synthetic* package tree under pytest's tmp_path and mutates
only that copy. The canonical plans, packets and manifests in this repository
are never written to.

The synthetic tree mirrors the *actual* parent spec layout: the authority spec
manifest does not list the D0 stage control, and the D0 stage packet is fenced
by its own payload manifest instead.

Run: python3 -B -m pytest tools/test_verify_v1_plan.py -q
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "verify_v1_plan.py"
sys.path.insert(0, str(ROOT / "tools"))

import verify_v1_plan as checker  # noqa: E402

LEGACY_V1 = (
    ["A%02d" % i for i in range(1, 13)]
    + ["F%02d" % i for i in range(1, 6)]
    + ["Q01"]
    + ["X%02d" % i for i in range(1, 4)]
)
LEGACY_V2_EXTRA = ["A%02d" % i for i in range(13, 18)] + ["F06"] + ["X%02d" % i for i in range(4, 7)]
LEGACY_V3_EXTRA = ["A%02d" % i for i in range(18, 23)] + ["F07"] + ["X%02d" % i for i in range(7, 10)]
MS = checker.MS_CASE_IDS

GATES_V1 = LEGACY_V1 + MS
GATES_V2 = LEGACY_V1 + LEGACY_V2_EXTRA + MS
GATES_V3 = LEGACY_V1 + LEGACY_V2_EXTRA + LEGACY_V3_EXTRA + MS

APPROVAL_REL = "reports/v1-redesign/product-change-approval.json"
BASELINE_REL = "reports/v1-redesign/legacy-gates-before-change.json"
D0_DIR = ".agent-governance/stages/V1-D0"
R1_DIR = ".agent-governance/stages/R1"
D0_MANIFEST_REL = D0_DIR + "/PAYLOAD_MANIFEST.sha256"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema_def(required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {field: {"type": "string"} for field in required},
        "required": list(required),
        "additionalProperties": False,
    }


def d0_stage_control() -> dict:
    return {
        "schema_version": "lvw.stage-control/1",
        "stage_id": "V1-D0",
        "status": "FROZEN_OFFLINE_TOOL_SCOPE_ONLY_PRODUCT_GATE0_NOT_READY",
        "product_execution_authorized": False,
        "roles": {
            "gate_owner": "Codex",
            "implementation_owner": "ClaudeCode-D0-Implement",
            "independent_reviewer": "ClaudeCode-D0-Review",
        },
        "workpacks": [
            {
                "id": "D0-B-IMPL",
                "allowed_files": list(checker.FROZEN_D0_ALLOWED_FILES),
                "commands": list(checker.FROZEN_D0_COMMANDS),
                "outputs": ["implementation receipt", "raw commands", "test exit codes", "risks"],
            },
            {
                "id": "D0-B-REVIEW",
                "allowed_files": list(checker.FROZEN_D0_REVIEW_ALLOWED_FILES),
                "depends_on": ["D0-A-DESIGN-DRAFT"],
                "outputs": ["read-only design review", "Fatal/Major/Minor list"],
            },
        ],
        "forbidden_write_paths": list(checker.FROZEN_D0_FORBIDDEN_PATHS),
        "model_gpu_runtime_budget": 0,
        "product_full_checkpoints": 0,
        "stage_pass_forbidden": True,
    }


def regenerate_d0_manifest(root: Path) -> str:
    """Rewrite the D0 payload manifest over the frozen packet inventory."""
    packet = root / D0_DIR
    lines = []
    for name in checker.FROZEN_D0_PACKET_FILES:
        lines.append("%s  %s\n" % (sha256(packet / name), name))
    manifest = packet / "PAYLOAD_MANIFEST.sha256"
    manifest.write_text("".join(lines), encoding="utf-8")
    return sha256(manifest)


def build_fixture(root: Path) -> dict:
    """Write a minimal but complete synthetic package tree."""
    # --- release gates and the pre-amendment baseline ------------------------
    write_json(root / "plans/release_gates.json", {
        "schema_version": "lvw.release-gates/1",
        "gates": {
            "V1": {"required_cases": list(GATES_V1)},
            "V2": {"required_cases": list(GATES_V2)},
            "V3": {"required_cases": list(GATES_V3)},
        },
        "states": ["NOT_RUN", "PASS", "FAIL", "BLOCKED"],
    })
    write_json(root / BASELINE_REL, {
        "kind": "PRE_AMENDMENT_CASE_SETS",
        "required_cases": {
            "V1": list(LEGACY_V1),
            "V2": LEGACY_V1 + LEGACY_V2_EXTRA,
            "V3": LEGACY_V1 + LEGACY_V2_EXTRA + LEGACY_V3_EXTRA,
        },
        "canonical_contract_hashes": {},
        "old_R1_packet_manifest_sha256": "",
    })

    # --- candidate contract and candidate DTO schema -------------------------
    write_json(root / "plans/v1-multishot-contract.json", {
        "schema_version": "lvw.multishot-contract-candidate/1",
        "status": "DESIGN_REVIEW_NOT_ACTIVE_OPENAPI",
        "entities": {
            "SceneRevision": {"required": ["id", "media_ref_id", "source_sha256"]},
            "AnalysisBinding": {"required": ["shot_id", "scene_revision_id"]},
            "ShotEvidence": {
                "required": ["frame_refs", "characters", "scene", "actions", "unknowns"],
                "character_fields": ["local_actor_id", "visible_appearance", "evidence_frame_indices"],
                "action_fields": ["actor_ref", "description", "domain", "evidence_frame_indices"],
            },
            "ParentJob": {"required": ["id", "planned_child_ids", "total"]},
        },
    })
    write_json(root / "contracts/v1-multishot.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:lvw:v1-multishot:design-candidate:1",
        "title": "V1 multi-shot candidate DTOs",
        "$defs": {
            "SceneRevision": schema_def(["id", "media_ref_id", "source_sha256"]),
            "AnalysisBinding": schema_def(["shot_id", "scene_revision_id"]),
            "ShotEvidence": schema_def(["frame_refs", "characters", "scene", "actions", "unknowns"]),
            "Character": schema_def(["local_actor_id", "visible_appearance", "evidence_frame_indices"]),
            "Action": schema_def(["actor_ref", "description", "domain", "evidence_frame_indices"]),
            "BatchChildrenResponse": schema_def(["parent_job_id", "total", "children"]),
        },
    })

    # --- acceptance cases ----------------------------------------------------
    cases = []
    for case_id in ["Q01"] + MS:
        tokens = checker.FROZEN_QUALITY_TOKENS.get(case_id, ())
        assertions = ["阈值断言 %s" % token for token in tokens] or ["无固定阈值"]
        cases.append({"case_id": case_id, "version": "V1", "status": "NOT_RUN", "assertions": assertions})
    write_json(root / "plans/acceptance_cases.json", {
        "schema_version": "lvw.acceptance-cases/2.0",
        "cases": cases,
    })

    # --- requirements and task graph -----------------------------------------
    write_json(root / "plans/requirements.json", {
        "requirements": [{
            "requirement_id": "R22",
            "title": "V1短视频多镜头",
            "stages": ["V1-M1", "R2"],
            "acceptance_ids": list(MS),
            "status": "NOT_RUN",
        }],
    })
    write_json(root / "plans/tasks.json", {
        "stages": [
            {"stage_id": "R1a", "version": "V1", "depends_on": [], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": []},
            {"stage_id": "V0-S3", "version": "V0.2", "depends_on": [], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": []},
            {"stage_id": "R1", "version": "V1", "depends_on": ["R1a", "V0-S3"], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": GATES_V1[:16]},
            {"stage_id": "V1-M1", "version": "V1", "depends_on": ["R1"], "status": "NOT_RUN",
             "requirements": ["R22"], "work_on_cases": list(MS)},
            {"stage_id": "R2", "version": "V1", "depends_on": ["R1", "V1-M1"], "status": "NOT_RUN",
             "requirements": ["R22"], "work_on_cases": list(GATES_V1)},
        ],
    })

    # --- root plan -----------------------------------------------------------
    write_json(root / "plans/v1-revised-plan.json", {
        "schema_version": "lvw.v1-plan/1",
        "approval": APPROVAL_REL,
        "status": "DESIGN_REVIEW_REQUIRED",
        "roles": {
            "architect_gate_owner": "Codex",
            "implementer": "Orca visible ClaudeCode worker",
            "local_validation": "same implementer plus deterministic executor, not independent",
            "independent_reviewer": "separate context/workspace, read-only candidate",
            "human": "actual experience and release signatures",
        },
        "product_current_coordinate_source": "plans/execution-control.json",
        "parallel_preparation": {
            "id": "V1-D0",
            "workpacks": [
                "D0-A architecture/contracts/acceptance design",
                "D0-B deterministic plan checker and independent design review",
            ],
            "product_edits_allowed": False,
        },
        "stages": [
            {"id": "R1", "depends_on": ["R1a", "V0-S3"], "workpacks": ["R1-A"], "completed": 0, "total": 4},
            {"id": "V1-M1", "depends_on": ["R1"], "workpacks": ["M1-A", "M1-B", "M1-C"], "completed": 0, "total": 3},
            {"id": "R2", "depends_on": ["R1", "V1-M1"], "workpacks": ["R2-A", "R2-D"], "completed": 0, "total": 4},
        ],
        "legacy_v0_obligations_retained": True,
        "old_slice_human_signoff_waived": False,
        "limits": {key: value for key, (value, _kind) in checker.FROZEN_LIMITS.items()},
        "v1_required_cases": list(GATES_V1),
        "supplement_case_ids": list(MS),
        "contract_candidate": "plans/v1-multishot-contract.json",
        "acceptance_design": "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md",
        "global_authority": checker.FROZEN_GLOBAL_AUTHORITY,
        "budget_reset": False,
        "authorization_accounting": {
            "design_stage": "V1-M1",
            "authority_stage": "R2",
            "scope_record": APPROVAL_REL,
            "policy": "M1 is approved V1/R2 early substage; finite receipt binds both identities and scope hash.",
        },
    })

    # --- approval, execution control, D0 stage packet ------------------------
    write_json(root / APPROVAL_REL, {
        "kind": "APPROVED_PRODUCT_SCOPE_AND_DEVELOPMENT_ROLE_CHANGE",
        "id": "CHANGE-V1-MULTISHOT-01",
        "decision": "APPROVED_BY_PROJECT_OWNER",
        "human_acceptance_of_621b1bf": False,
        "release_approved": False,
    })
    write_json(root / "plans/execution-control.json", {
        "schema_version": "lvw.execution-control/1",
        "coordinate": {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "UNIFIED_MEDIA", "state": "WAIT_HUMAN"},
        "forbidden_claims": ["V1_ACCEPTED", "PRODUCTION_RELEASED"],
    })
    packet = root / D0_DIR
    packet.mkdir(parents=True, exist_ok=True)
    for name in checker.FROZEN_D0_PACKET_FILES:
        if name.endswith(".md"):
            (packet / name).write_text("# %s\n\nsynthetic packet file for the D0 checker tests\n" % name, encoding="utf-8")
    write_json(packet / "stage-control.json", d0_stage_control())

    # --- canonical contracts and the protected old R1 packet -----------------
    for rel, body in (
        ("contracts/openapi.json", {"openapi": "3.1.0"}),
        ("contracts/lvw.schema.json", {"type": "object"}),
        ("contracts/storage.sql", "-- baseline DDL\n"),
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body) + "\n" if isinstance(body, dict) else body, encoding="utf-8")

    r1_file = root / R1_DIR / "stage-control.json"
    r1_file.parent.mkdir(parents=True, exist_ok=True)
    r1_file.write_text(json.dumps({"stage_id": "R1", "frozen": True}) + "\n", encoding="utf-8")
    (root / R1_DIR / "PAYLOAD_MANIFEST.sha256").write_text(
        "%s  stage-control.json\n" % sha256(r1_file), encoding="utf-8")

    baseline = json.loads((root / BASELINE_REL).read_text(encoding="utf-8"))
    baseline["canonical_contract_hashes"] = {
        "contracts/openapi.json": sha256(root / "contracts/openapi.json"),
        "contracts/lvw.schema.json": sha256(root / "contracts/lvw.schema.json"),
        "contracts/storage.sql": sha256(root / "contracts/storage.sql"),
    }
    baseline["old_R1_packet_manifest_sha256"] = sha256(root / R1_DIR / "PAYLOAD_MANIFEST.sha256")
    write_json(root / BASELINE_REL, baseline)

    # Actual parent layout: the authority spec manifest does *not* list the D0
    # stage control or the D0 payload manifest; the D0 packet manifest fences
    # that control plane instead.
    fenced = [
        "plans/v1-revised-plan.json",
        "plans/release_gates.json",
        "plans/acceptance_cases.json",
        "plans/requirements.json",
        "plans/tasks.json",
        "plans/v1-multishot-contract.json",
        "plans/execution-control.json",
        "contracts/v1-multishot.schema.json",
        "contracts/openapi.json",
        "contracts/lvw.schema.json",
        "contracts/storage.sql",
        APPROVAL_REL,
        BASELINE_REL,
        R1_DIR + "/PAYLOAD_MANIFEST.sha256",
        R1_DIR + "/stage-control.json",
    ]
    write_json(root / D0_DIR / "spec-manifest.json", {
        "kind": "D0_REVIEWED_INPUT_CANDIDATE_HASH_FENCE_NOT_PRODUCT_GATE0",
        "files": {rel: sha256(root / rel) for rel in fenced},
    })
    return {"d0_manifest_sha256": regenerate_d0_manifest(root)}


def run_checker(root: Path, pin: str | None = None, extra: list[str] | None = None):
    command = [sys.executable, "-B", str(CHECKER), "--root", str(root)]
    if pin is not None:
        command += ["--d0-packet-manifest-sha256", pin]
    command += list(extra or [])
    return subprocess.run(command, capture_output=True, text=True)


def load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def save(root: Path, rel: str, payload) -> None:
    write_json(root / rel, payload)


def refresh_fences(package: dict, rels=()) -> None:
    """Re-freeze the authority spec manifest and the D0 payload manifest.

    Used only after mutations that are *not* the subject of the test, so the
    tree stays consistent and the asserted finding stays specific.
    """
    root = package["root"]
    spec_path = root / D0_DIR / "spec-manifest.json"
    spec = load(root, D0_DIR + "/spec-manifest.json")
    for rel in rels:
        spec["files"][rel] = sha256(root / rel)
    write_json(spec_path, spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(root)


@pytest.fixture()
def package(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    state = build_fixture(root)
    state["root"] = root
    return state


def expect_failure(result, code: str):
    assert result.returncode != 0, "checker exited 0 for a faulty package:\n%s" % result.stdout
    assert code in result.stdout, "expected %s in output:\n%s" % (code, result.stdout)


def run_package(package: dict, extra=None):
    return run_checker(package["root"], package["d0_manifest_sha256"], extra)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_valid_package_exits_zero(package):
    result = run_package(package)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_checker_is_read_only(package):
    root = package["root"]
    before = {p: sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    assert run_package(package).returncode == 0
    after = {p: sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    assert before == after


def test_canonical_package_validates_read_only():
    """The canonical package must satisfy the checker; the run must not write anything."""
    watched = [
        "plans/v1-revised-plan.json",
        "plans/release_gates.json",
        "plans/acceptance_cases.json",
        "plans/requirements.json",
        "plans/tasks.json",
        "plans/v1-multishot-contract.json",
        "plans/execution-control.json",
        "contracts/v1-multishot.schema.json",
        "contracts/openapi.json",
        "contracts/lvw.schema.json",
        "contracts/storage.sql",
        D0_DIR + "/stage-control.json",
        D0_DIR + "/spec-manifest.json",
        D0_DIR + "/PAYLOAD_MANIFEST.sha256",
        APPROVAL_REL,
        R1_DIR + "/PAYLOAD_MANIFEST.sha256",
    ]
    before = {rel: sha256(ROOT / rel) for rel in watched}
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER)], capture_output=True, text=True, cwd=str(ROOT)
    )
    after = {rel: sha256(ROOT / rel) for rel in watched}
    assert before == after, "the checker modified a canonical file"
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


# ---------------------------------------------------------------------------
# Major D0-CODE-M01: empty control lists must never bypass a check
# ---------------------------------------------------------------------------


def test_empty_allowed_files_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ALLOWED_FILES")


def test_empty_commands_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["commands"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_COMMANDS")


def test_empty_forbidden_write_paths_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["forbidden_write_paths"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_FORBIDDEN_PATHS")


def test_empty_review_allowed_files_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-REVIEW":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_REVIEW_FILES")


def test_missing_workpack_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["workpacks"] = [w for w in control["workpacks"] if w["id"] != "D0-B-IMPL"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_WORKPACK")


def test_nonzero_d0_budget_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["model_gpu_runtime_budget"] = 8
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_BUDGET")


# ---------------------------------------------------------------------------
# Major D0-CODE-M01: the D0 control plane must be fenced even though the
# authority spec manifest does not list it
# ---------------------------------------------------------------------------


def test_actual_style_layout_without_stage_control_fence_detects_drift(package):
    """The spec manifest does not list the D0 stage control; the packet manifest must catch drift."""
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    result = run_package(package)
    expect_failure(result, "E_D0_PACKET_DRIFT")
    expect_failure(result, "E_OWNERSHIP_ALLOWED_FILES")


def test_d0_packet_control_drift_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["stage_pass_forbidden"] = False
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_D0_PACKET_DRIFT")


def test_d0_packet_manifest_missing_entry_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    kept = [line for line in manifest.read_text(encoding="utf-8").splitlines() if not line.endswith("  stage-control.json")]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")
    result = run_package(package)
    expect_failure(result, "E_D0_PACKET_MANIFEST_MISSING_ENTRY")
    expect_failure(result, "E_D0_CONTROL_UNBOUND")


def test_d0_packet_manifest_extra_entry_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "%s  extra-notebook.md\n" % ("0" * 64), encoding="utf-8"
    )
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_EXTRA_ENTRY")


def test_d0_packet_manifest_missing_file_is_rejected(package):
    (package["root"] / D0_DIR / "07-checkpoint-plan.md").unlink()
    expect_failure(run_package(package), "E_D0_PACKET_FILE_MISSING")


def test_d0_packet_manifest_missing_is_rejected(package):
    (package["root"] / D0_MANIFEST_REL).unlink()
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_MISSING")


def test_d0_packet_manifest_regenerated_to_hide_drift_is_rejected(package):
    """Editing the control and re-signing the manifest must still fail the source-control pin."""
    root = package["root"]
    control = load(root, D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(root, D0_DIR + "/stage-control.json", control)
    regenerate_d0_manifest(root)  # attacker re-signs the packet manifest
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_PINNED")


def test_d0_packet_unlisted_file_is_rejected(package):
    (package["root"] / D0_DIR / "08-extra-note.md").write_text("uncontrolled\n", encoding="utf-8")
    expect_failure(run_package(package), "E_D0_PACKET_UNLISTED_FILE")


def test_d0_packet_manifest_not_bound_to_spec_manifest_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    kept = [line for line in manifest.read_text(encoding="utf-8").splitlines() if not line.endswith("  spec-manifest.json")]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_D0_CONTROL_UNBOUND")


def test_stage_control_must_be_the_packet_bound_file(package):
    root = package["root"]
    stray = root / "reports" / "v1-redesign" / "stage-control-copy.json"
    write_json(stray, load(root, D0_DIR + "/stage-control.json"))
    result = run_package(package, ["--stage-control", "reports/v1-redesign/stage-control-copy.json"])
    expect_failure(result, "E_OWNERSHIP_CONTROL_PATH")


# ---------------------------------------------------------------------------
# Denominators and case identity
# ---------------------------------------------------------------------------


def test_shrunk_v1_denominator_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"] = gates["gates"]["V1"]["required_cases"][:-1]
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_DENOM_V1_COUNT")


def test_dropped_legacy_case_breaks_the_prefix(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].remove("A05")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_LEGACY_PREFIX_V1")


def test_duplicate_ms_case_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].append("MS02")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


def test_duplicate_ms_case_definition_is_rejected(package):
    cases = load(package["root"], "plans/acceptance_cases.json")
    cases["cases"].append(dict(cases["cases"][1], case_id="MS03"))
    save(package["root"], "plans/acceptance_cases.json", cases)
    refresh_fences(package, ["plans/acceptance_cases.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


def test_plan_must_match_the_release_gate_denominator(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["v1_required_cases"] = plan["v1_required_cases"][:-1]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_PLAN_V1_CASE_SET")


def test_r22_coverage_gap_is_rejected(package):
    requirements = load(package["root"], "plans/requirements.json")
    requirements["requirements"][0]["acceptance_ids"] = [c for c in MS if c != "MS08"]
    save(package["root"], "plans/requirements.json", requirements)
    refresh_fences(package, ["plans/requirements.json"])
    expect_failure(run_package(package), "E_R22_ACCEPTANCE")


def test_missing_ms_case_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].remove("MS08")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_MS_MISSING")


def test_plan_duplicate_ms_case_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["v1_required_cases"].append("MS04")
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------


def test_dag_cycle_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][0]["depends_on"] = ["R1a", "V0-S3", "V1-M1"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DAG_CYCLE")


def test_missing_m1_dependency_on_r1_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][1]["depends_on"] = []
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DEP_M1_R1")


def test_missing_r2_dependency_on_m1_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][2]["depends_on"] = ["R1"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DEP_R2_M1")


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


def test_relaxed_resource_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["gpu_used_mib_exclusive"] = 40960
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_LOOSED")


def test_lowered_ram_floor_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["ram_available_mib_min"] = 512
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_LOOSED")


def test_dropped_fixed_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    del plan["limits"]["shots"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_MISSING")


def test_quality_threshold_drift_is_rejected(package):
    cases = load(package["root"], "plans/acceptance_cases.json")
    for case in cases["cases"]:
        if case["case_id"] == "MS04":
            case["assertions"] = ["阈值断言 总可用>=9/18", "阈值断言 总>=4可用"]
    save(package["root"], "plans/acceptance_cases.json", cases)
    refresh_fences(package, ["plans/acceptance_cases.json"])
    expect_failure(run_package(package), "E_QUALITY_DRIFT")


# ---------------------------------------------------------------------------
# Ownership, human signature, authorization
# ---------------------------------------------------------------------------


def test_write_path_ownership_violation_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = list(checker.FROZEN_D0_ALLOWED_FILES) + ["lvw/"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ALLOWED_FILES")


def test_unseparated_roles_are_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["roles"]["independent_reviewer"] = control["roles"]["implementation_owner"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ROLE")


def test_false_human_signature_in_plan_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["human_signoff"] = {"decision": "APPROVED", "signer": "project-owner"}
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_HUMAN_APPROVAL_CLAIM")


def test_false_human_acceptance_in_approval_is_rejected(package):
    approval = load(package["root"], APPROVAL_REL)
    approval["human_acceptance_of_621b1bf"] = True
    save(package["root"], APPROVAL_REL, approval)
    refresh_fences(package, [APPROVAL_REL])
    expect_failure(run_package(package), "E_HUMAN_APPROVAL_CLAIM")


def test_invented_completion_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][1]["completed"] = 3
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_COMPLETED_CLAIM")


def test_forbidden_release_claim_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["status"] = "V1_ACCEPTED"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_PLAN_STATUS_INVALID")


def test_budget_reset_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["budget_reset"] = True
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_BUDGET_RESET")


def test_unauthorized_stage_alias_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["authorization_accounting"]["design_stage"] = "V2"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_STAGE_ALIAS")


def test_authority_stage_alias_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["authorization_accounting"]["authority_stage"] = "V3"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_STAGE_ALIAS")


def test_scope_hash_drift_is_rejected(package):
    approval = load(package["root"], APPROVAL_REL)
    approval["note"] = "scope file changed after the fence was frozen"
    save(package["root"], APPROVAL_REL, approval)
    result = run_package(package)
    expect_failure(result, "E_SPEC_FENCE_DRIFT")
    expect_failure(result, "E_SCOPE_HASH_DRIFT")


# ---------------------------------------------------------------------------
# Protected artefacts
# ---------------------------------------------------------------------------


def test_canonical_contract_drift_is_rejected(package):
    path = package["root"] / "contracts/openapi.json"
    path.write_text(json.dumps({"openapi": "3.1.0", "changed": True}) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_CONTRACT_DRIFT")


def test_old_r1_packet_drift_is_rejected(package):
    path = package["root"] / R1_DIR / "stage-control.json"
    path.write_text(json.dumps({"stage_id": "R1", "frozen": False}) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_R1_FILE_DRIFT")


def test_spec_fence_drift_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["next_action"] = "changed without re-freezing the authority manifest"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    expect_failure(run_package(package), "E_SPEC_FENCE_DRIFT")


# ---------------------------------------------------------------------------
# Candidate contract and schema
# ---------------------------------------------------------------------------


def test_contract_schema_mismatch_is_rejected(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["entities"]["SceneRevision"]["required"] = ["id", "media_ref_id"]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_CONTRACT_SCHEMA_MISMATCH")


def test_schema_without_closed_dtos_is_rejected(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["SceneRevision"]["additionalProperties"] = True
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_SCHEMA_DTO")


def test_missing_input_exits_nonzero_without_verdict(package):
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER), "--root", str(package["root"]), "--plan", "plans/missing.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "INPUT_ERROR" in result.stderr
    assert "RESULT: PASS" not in result.stdout
