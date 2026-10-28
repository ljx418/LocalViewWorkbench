#!/usr/bin/env python3
"""Validate agent governance structure and false-green guards, not the product."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / ".agent-governance"
STAGE_DIR = GOV / "stages" / "V0-S0"
NEXT_STAGE_DIR = GOV / "stages" / "V0-S1"

REQUIRED_PACKET_FILES = {
    "00-coordinate.md",
    "01-scope-and-non-goals.md",
    "02-architecture-and-ownership.md",
    "03-workpack-plan.md",
    "04-acceptance-matrix.md",
    "05-risk-and-authorization-register.md",
    "06-implementation-prompt.md",
    "07-checkpoint-plan.md",
    "stage-control.json",
    "PAYLOAD_MANIFEST.sha256",
}
REQUIRED_RECEIPT_FIELDS = {
    "project_id",
    "stage_id",
    "workpack_id",
    "candidate_sha",
    "evidence_commit",
    "spec_version",
    "acceptance_hash",
    "gate_version",
    "run_id",
    "environment",
    "check_results",
    "test_counts",
    "artifact_refs",
    "risks",
    "implementation_owner_role",
    "implementation_session",
    "decision",
}
COUNT_FIELDS = {"denominator", "pass", "fail", "blocked", "skipped", "not_run"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest_ids(ids: list[str]) -> str:
    payload = "\n".join(sorted(ids)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def product_control_digest() -> str:
    digest = hashlib.sha256()
    for name in ("plans/tasks.json", "plans/acceptance_cases.json", "plans/release_gates.json"):
        digest.update(name.encode("utf-8") + b"\0" + (ROOT / name).read_bytes() + b"\0")
    return digest.hexdigest()


def validate_stage(control: dict, tasks: dict, cases: dict) -> list[str]:
    errors: list[str] = []
    stage = next((item for item in tasks["stages"] if item["stage_id"] == control.get("stage_id")), None)
    if not stage:
        return ["stage_id is absent from plans/tasks.json"]
    fixed = control.get("fixed_acceptance_ids", [])
    if fixed != stage["work_on_cases"]:
        errors.append("fixed denominator differs from plans/tasks.json work_on_cases")
    known_cases = {item["case_id"] for item in cases["cases"]}
    if not fixed or not set(fixed) <= known_cases:
        errors.append("fixed denominator is empty or references unknown cases")
    if control.get("acceptance_hash") != digest_ids(fixed):
        errors.append("acceptance_hash does not bind the fixed denominator")

    roles = control.get("roles", {})
    gate_owner = roles.get("gate_owner")
    reviewer = roles.get("independent_reviewer")
    implementers = set(roles.get("implementation_owners", []))
    if not gate_owner or not reviewer or not implementers:
        errors.append("gate owner, independent reviewer and implementation owner are required")
    if gate_owner == reviewer or gate_owner in implementers or reviewer in implementers:
        errors.append("architecture, implementation and independent review roles are not separated")

    workpacks = control.get("workpacks", [])
    ids = [item.get("id") for item in workpacks]
    if not workpacks or None in ids or len(ids) != len(set(ids)):
        errors.append("workpack IDs must be present and unique")
    known = set(ids)
    done: set[str] = set()
    for _ in range(len(workpacks) + 1):
        for item in workpacks:
            if set(item.get("depends_on", [])) <= done:
                done.add(item["id"])
    if done != known:
        errors.append("workpack dependencies are missing or cyclic")
    for item in workpacks:
        if not item.get("owner") or not item.get("allowed_paths") or not item.get("commands") or not item.get("output"):
            errors.append(f"{item.get('id')}: incomplete owner/scope/command/output")
    external = any(item.get("risk") == "external_private" for item in workpacks)
    state = control.get("state")
    if external and state == "WAIT_AUTH":
        if not control.get("required_authorization") or control.get("next_owner") != "project_owner":
            errors.append("WAIT_AUTH must identify the required authorization and human owner")
        request_ref = control.get("authorization_request")
        if request_ref:
            request_path = ROOT / request_ref
            if not request_path.is_file():
                errors.append("authorization request file is missing")
            else:
                request = load_json(request_path)
                if (request.get("status") != "PENDING_PROJECT_OWNER_APPROVAL"
                        or request.get("is_authorization") is not False
                        or request.get("does_not_authorize_execution") is not True
                        or request.get("stage_id") != control.get("stage_id")):
                    errors.append("WAIT_AUTH request is not a fail-closed pending request")
        for record in control.get("authorization_records", []):
            if not (ROOT / record).is_file():
                errors.append(f"historical authorization record is missing: {record}")
    elif external and control.get("authorization_scope") == "OFFLINE_REPOSITORY_ONLY":
        if control.get("external_authorization") != "WAIT_AUTH_BEFORE_WP-S1-03":
            errors.append("offline-only Stage must keep external workpack at WAIT_AUTH")
    elif external:
        if control.get("authorization_scope") not in {
            "WP-S1-03_ONE_SHOT_LIVE", "WP-S1-04_CHECKPOINT_ONE_SHOT_LIVE"
        }:
            errors.append("post-authorization Stage has an unknown authorization scope")
        if state not in {"FROZEN_READY_OFFLINE", "RUNNING", "CHECKPOINT", "STAGE_BASELINE_COMPLETE", "NO_GO", "BLOCKED", "WAIT_BUDGET", "PASS"}:
            errors.append("external/private Stage has an invalid post-authorization state")
        records = control.get("authorization_records", [])
        if not records:
            errors.append("post-authorization Stage is missing authorization_records")
        for record in records:
            if not (ROOT / record).is_file():
                errors.append(f"authorization record is missing: {record}")
    budgets = control.get("budgets", {})
    retry_budget = budgets.get("max_effective_retries_per_probe", budgets.get("max_effective_retries_per_external_case"))
    if not isinstance(retry_budget, int) or retry_budget > 2:
        errors.append("retry budget is missing or exceeds the frozen maximum")
    protected = set(control.get("forbidden_paths", []))
    for required in {"contracts/", "plans/acceptance_cases.json", "plans/release_gates.json"}:
        if required not in protected:
            errors.append(f"protected path missing: {required}")
    return errors


def validate_receipt(
    receipt: dict,
    expected_candidate: str | None = None,
    control: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_RECEIPT_FIELDS - set(receipt)
    if missing:
        errors.append("receipt fields missing: " + ",".join(sorted(missing)))
        return errors
    counts = receipt.get("test_counts", {})
    if COUNT_FIELDS - set(counts):
        errors.append("receipt test_counts are incomplete")
        return errors
    if expected_candidate and receipt.get("candidate_sha") != expected_candidate:
        errors.append("receipt evidence belongs to a different candidate")
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("candidate_sha", ""))):
        errors.append("receipt candidate_sha is not a full Git commit ID")
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("evidence_commit", ""))):
        errors.append("receipt evidence_commit is not a full Git commit ID")
    if control:
        if receipt.get("acceptance_hash") != control.get("acceptance_hash"):
            errors.append("receipt acceptance_hash differs from the frozen Stage denominator")
        if counts.get("denominator") != len(control.get("fixed_acceptance_ids", [])):
            errors.append("receipt denominator count differs from the frozen Stage denominator")
        owner = receipt.get("implementation_owner_role")
        roles = control.get("roles", {})
        if owner not in set(roles.get("implementation_owners", [])):
            errors.append("actual implementation owner is not an authorized implementation owner")
        if owner in {roles.get("gate_owner"), roles.get("independent_reviewer")}:
            errors.append("actual implementation owner collides with gate or review owner")
    if receipt.get("decision") == "PASS":
        if counts["pass"] != counts["denominator"] or any(counts[name] for name in ("fail", "blocked", "skipped", "not_run")):
            errors.append("PASS contains an incomplete or non-passing fixed denominator")
    return errors


def validate_evidence_manifest(path: Path, expected_candidate: str) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return ["evidence manifest is missing"]
    manifest = load_json(path)
    manifest_candidate = manifest.get("candidate_commit")
    if manifest_candidate is not None and manifest_candidate != expected_candidate:
        errors.append("evidence manifest belongs to a different candidate")
    summary_ref: str | None = None
    for artifact in manifest.get("artifacts", []):
        relative = artifact.get("path")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            errors.append("evidence manifest contains an unsafe artifact path")
            continue
        target = ROOT / relative
        actual = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        if actual != artifact.get("sha256"):
            errors.append(f"evidence hash mismatch: {relative}")
        if Path(relative).name == "probe-summary.json":
            summary_ref = relative
    if not manifest.get("artifacts"):
        errors.append("evidence manifest contains no artifacts")
    if manifest_candidate is None:
        if not summary_ref:
            errors.append("evidence manifest has neither candidate_commit nor a probe summary")
        else:
            summary = load_json(ROOT / summary_ref)
            if summary.get("candidate_sha") != expected_candidate:
                errors.append("manifest-bound probe summary belongs to a different candidate")
    return errors


def verify_manifest() -> list[str]:
    errors: list[str] = []
    manifest = STAGE_DIR / "PAYLOAD_MANIFEST.sha256"
    if not manifest.is_file():
        return ["Stage Packet manifest is missing"]
    listed: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            errors.append("invalid Stage manifest line")
            continue
        listed.add(name)
        path = STAGE_DIR / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"Stage manifest mismatch: {name}")
    expected = REQUIRED_PACKET_FILES - {"PAYLOAD_MANIFEST.sha256"}
    if listed != expected:
        errors.append("Stage manifest inventory differs from the frozen packet")
    return errors


def verify_prepared_stage(tasks: dict, cases: dict) -> list[str]:
    errors: list[str] = []
    if not NEXT_STAGE_DIR.is_dir():
        return ["prepared V0-S1 packet is missing"]
    inventory = {path.name for path in NEXT_STAGE_DIR.iterdir() if path.is_file()}
    if inventory != REQUIRED_PACKET_FILES:
        errors.append("prepared V0-S1 packet inventory differs from the standard packet")
    manifest = NEXT_STAGE_DIR / "PAYLOAD_MANIFEST.sha256"
    listed: set[str] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines() if manifest.is_file() else []:
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            errors.append("prepared V0-S1 manifest line is invalid")
            continue
        listed.add(name)
        path = NEXT_STAGE_DIR / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"prepared V0-S1 manifest mismatch: {name}")
    if listed != REQUIRED_PACKET_FILES - {"PAYLOAD_MANIFEST.sha256"}:
        errors.append("prepared V0-S1 manifest inventory is incomplete")
    control = load_json(NEXT_STAGE_DIR / "stage-control.json")
    planned = next(item for item in tasks["stages"] if item["stage_id"] == "V0-S1")
    known = {item["case_id"] for item in cases["cases"]}
    fixed = control.get("fixed_acceptance_ids", [])
    if fixed != planned["work_on_cases"] or not set(fixed) <= known:
        errors.append("prepared V0-S1 denominator differs from plans/tasks.json")
    if control.get("acceptance_hash") != digest_ids(fixed):
        errors.append("prepared V0-S1 acceptance hash is invalid")
    packet_status = control.get("packet_status")
    if packet_status == "DRAFT_NOT_FROZEN":
        if control.get("execution_authorized") is not False or control.get("state") != "BLOCKED_BY_DEPENDENCY":
            errors.append("draft V0-S1 packet must remain non-executable")
    elif packet_status == "FROZEN":
        baseline = control.get("baseline", {})
        bound_commits = [
            baseline.get("git_commit"),
            baseline.get("prepared_against_commit"),
            baseline.get("product_bridge_candidate"),
            baseline.get("harness_candidate"),
            baseline.get("s0_evidence_commit"),
            baseline.get("s0_independent_review_commit"),
        ]
        for commit in bound_commits:
            if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                errors.append("frozen V0-S1 packet has an invalid bound commit")
                continue
            exists = subprocess.run(
                ["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            if exists.returncode != 0:
                errors.append(f"frozen V0-S1 bound commit is missing: {commit}")
        if (
            control.get("execution_authorized") is not True
            or control.get("authorization_scope") != "OFFLINE_REPOSITORY_ONLY"
            or control.get("external_authorization") != "WAIT_AUTH_BEFORE_WP-S1-03"
            or control.get("state") != "FROZEN_READY_OFFLINE"
        ):
            errors.append("frozen V0-S1 packet must authorize offline work only")
    else:
        errors.append("prepared V0-S1 packet status is invalid")
    if control.get("dependencies") != ["V0-S0:STAGE_BASELINE_COMPLETE"]:
        errors.append("prepared V0-S1 packet does not preserve the S0 dependency")
    return errors


def run_self_tests(control: dict, tasks: dict, cases: dict) -> list[dict]:
    results: list[dict] = []

    reduced = copy.deepcopy(control)
    reduced["fixed_acceptance_ids"].pop()
    results.append({"name": "reject_reduced_denominator", "passed": bool(validate_stage(reduced, tasks, cases))})

    collision = copy.deepcopy(control)
    collision["roles"]["independent_reviewer"] = collision["roles"]["implementation_owners"][0]
    results.append({"name": "reject_role_collision", "passed": bool(validate_stage(collision, tasks, cases))})

    unauthorized = copy.deepcopy(control)
    unauthorized["state"] = "RUNNING"
    unauthorized["authorization_records"] = []
    results.append({"name": "reject_unauthorized_external_run", "passed": bool(validate_stage(unauthorized, tasks, cases))})

    base_receipt = load_json(GOV / "templates" / "implementation-receipt.json")
    base_receipt.update({"candidate_sha": "candidate-new", "decision": "PASS"})
    base_receipt["test_counts"] = {"denominator": 4, "pass": 3, "fail": 0, "blocked": 0, "skipped": 1, "not_run": 0}
    results.append({"name": "reject_skipped_as_pass", "passed": bool(validate_receipt(base_receipt, "candidate-new"))})

    old_evidence = copy.deepcopy(base_receipt)
    old_evidence["decision"] = "READY_FOR_REVIEW"
    results.append({"name": "reject_old_candidate_evidence", "passed": bool(validate_receipt(old_evidence, "candidate-newer"))})
    return results


def main_v0_s1(args: argparse.Namespace, execution: dict) -> int:
    checks: list[dict] = []

    def check(name: str, condition: bool, detail: str = ""):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    stage_dir = GOV / "stages" / "V0-S1"
    packet_files = {path.name for path in stage_dir.iterdir()} if stage_dir.is_dir() else set()
    check("stage_packet_inventory", packet_files == REQUIRED_PACKET_FILES)
    control = load_json(stage_dir / "stage-control.json")
    tasks = load_json(ROOT / "plans" / "tasks.json")
    cases = load_json(ROOT / "plans" / "acceptance_cases.json")
    stage_errors = validate_stage(control, tasks, cases)
    check("stage_control", not stage_errors, "; ".join(stage_errors))

    listed: set[str] = set()
    manifest_errors: list[str] = []
    manifest = stage_dir / "PAYLOAD_MANIFEST.sha256"
    for line in manifest.read_text(encoding="utf-8").splitlines() if manifest.is_file() else []:
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            manifest_errors.append("invalid manifest line")
            continue
        listed.add(name)
        path = stage_dir / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            manifest_errors.append(name)
    check(
        "stage_manifest",
        not manifest_errors and listed == REQUIRED_PACKET_FILES - {"PAYLOAD_MANIFEST.sha256"},
        ", ".join(manifest_errors),
    )
    check("packet_frozen", control.get("packet_status") == "FROZEN")
    authorization_records = control.get("authorization_records", [])
    record_values = [load_json(ROOT / item) for item in authorization_records if (ROOT / item).is_file()]
    record_statuses = {item.get("status") for item in record_values}
    live_scopes = {"WP-S1-03_ONE_SHOT_LIVE", "WP-S1-04_CHECKPOINT_ONE_SHOT_LIVE"}
    checkpoint_waiting = (
        control.get("authorization_scope") == "WP-S1-04_CHECKPOINT_ONE_SHOT_LIVE"
        and control.get("external_authorization") == "WAIT_AUTH_REQUEST_V0_S1_WP_S1_04_CHECKPOINT_01"
        and control.get("state") == "WAIT_AUTH"
    )
    live_authorized = (
        control.get("authorization_scope") in live_scopes
        and isinstance(control.get("external_authorization"), str)
        and control.get("external_authorization", "").startswith("AUTH-V0-S1-")
        and bool(authorization_records)
        and control.get("state") == "RUNNING"
        and "GRANTED_ONCE" in record_statuses
    )
    live_terminal = (
        control.get("authorization_scope") in live_scopes
        and control.get("state") in {"CHECKPOINT", "NO_GO", "BLOCKED", "STAGE_BASELINE_COMPLETE", "PASS"}
        and bool(authorization_records)
        and bool(record_statuses)
        and all(str(status).startswith("EXPIRED_") for status in record_statuses)
    )
    offline_waiting = (
        control.get("authorization_scope") == "OFFLINE_REPOSITORY_ONLY"
        and control.get("external_authorization") == "WAIT_AUTH_BEFORE_WP-S1-03"
    )
    check("authorization_scope_valid", control.get("execution_authorized") is True
          and (offline_waiting or checkpoint_waiting or live_authorized or live_terminal))
    check("external_authorization_state", offline_waiting or checkpoint_waiting or live_authorized or live_terminal)
    check("baseline_product_control_fingerprint", control.get("baseline", {}).get("product_control_sha256") == product_control_digest())

    bound_commits = [
        control.get("baseline", {}).get(name)
        for name in ("git_commit", "prepared_against_commit", "product_bridge_candidate", "harness_candidate", "s0_evidence_commit", "s0_independent_review_commit")
    ]
    commit_errors: list[str] = []
    for commit in bound_commits:
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            commit_errors.append(str(commit))
            continue
        exists = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True, check=False)
        if exists.returncode != 0:
            commit_errors.append(commit)
    check("bound_commits_exist", not commit_errors, ", ".join(commit_errors))

    check("single_coordinate_stage", execution.get("coordinate", {}).get("stage_id") == "V0-S1")
    check("single_coordinate_state", execution.get("coordinate", {}).get("state") == control.get("state"))
    workpack_ids = {item.get("id") for item in control.get("workpacks", [])}
    current_workpack = execution.get("coordinate", {}).get("workpack_id")
    check("coordinate_workpack", current_workpack in workpack_ids, str(current_workpack))
    stage_pass = control.get("state") == "PASS"
    if stage_pass:
        check("product_status_pass", execution.get("product_status") == "PASS")
        acceptance_ref = execution.get("product_acceptance")
        acceptance_path = ROOT / str(acceptance_ref or "")
        check("v0_min_acceptance_exists", bool(acceptance_ref) and acceptance_path.is_file())
        acceptance = load_json(acceptance_path) if acceptance_path.is_file() else {}
        expected_ids = control.get("fixed_acceptance_ids", [])
        accepted_cases = acceptance.get("cases", [])
        accepted_ids = [item.get("case_id") for item in accepted_cases]
        candidate = acceptance.get("product_candidate")
        run_id = acceptance.get("run_id")
        check("v0_min_acceptance_decision", acceptance.get("decision") == "V0_MIN_ACCEPTED")
        check("v0_min_acceptance_denominator", accepted_ids == expected_ids
              and acceptance.get("fixed_denominator") == expected_ids
              and acceptance.get("acceptance_hash") == control.get("acceptance_hash"))
        check("v0_min_acceptance_case_binding", bool(candidate) and bool(run_id)
              and all(item.get("status") == "PASS"
                      and item.get("candidate_sha") == candidate
                      and item.get("run_id") == run_id
                      and item.get("observed") for item in accepted_cases))
        evidence_valid = True
        for item in acceptance.get("evidence", []):
            try:
                evidence_path = (ROOT / item["path"]).resolve()
                evidence_valid = (evidence_valid
                                  and evidence_path.is_relative_to(ROOT.resolve())
                                  and evidence_path.is_file()
                                  and hashlib.sha256(evidence_path.read_bytes()).hexdigest() == item["sha256"])
            except (KeyError, OSError, TypeError):
                evidence_valid = False
        check("v0_min_acceptance_evidence_binding", len(acceptance.get("evidence", [])) >= 5 and evidence_valid)
        signoff_ref = execution.get("human_signoff")
        signoff_path = ROOT / str(signoff_ref or "")
        signoff = load_json(signoff_path) if signoff_path.is_file() else {}
        check("v0_min_human_signoff", signoff.get("decision") == "APPROVED"
              and signoff.get("scope") == "V0-Min_PRODUCT_ACCEPTANCE"
              and signoff.get("product_candidate") == candidate
              and signoff.get("external_action_authorized") is False)
        check("v0_min_not_release_approval", acceptance.get("release_approved") is False
              and {"V0.1", "V0.2", "V0 legacy alias", "production release"}
              <= set(acceptance.get("not_approved", [])))
    else:
        check("product_status_not_promoted", execution.get("product_status") == "NOT_RUN")
    fixed_status = {item["case_id"]: item["status"] for item in cases["cases"]}
    check("plan_case_baseline_unchanged", all(fixed_status[item] == "NOT_RUN" for item in control.get("fixed_acceptance_ids", [])))
    check("packet_reference", (ROOT / execution.get("stage_packet", "")).resolve() == (stage_dir / "stage-control.json").resolve())
    check("manifest_reference", (ROOT / execution.get("stage_packet_manifest", "")).resolve() == manifest.resolve())

    offline_workpacks = {"WP-S1-00", "WP-S1-01", "WP-S1-02"}
    if current_workpack in offline_workpacks:
        check("offline_workpack_has_no_live_grant", control.get("external_authorization") == "WAIT_AUTH_BEFORE_WP-S1-03")
    elif current_workpack == "WP-S1-03":
        check("live_workpack_requires_authorization_record", bool(control.get("authorization_records")))

    registry = load_json(GOV / "project-registry.json")
    project = next((item for item in registry.get("projects", []) if item.get("project_id") == control.get("project_id")), None)
    check("project_registry_entry", bool(project))
    if project:
        check("project_registry_coordinate", project.get("current_stage") == "V0-S1" and project.get("state") == control.get("state"))

    if args.self_test:
        reduced = copy.deepcopy(control)
        reduced["fixed_acceptance_ids"].pop()
        check("reject_reduced_denominator", bool(validate_stage(reduced, tasks, cases)), "negative mutation must be rejected")
        collision = copy.deepcopy(control)
        collision["roles"]["independent_reviewer"] = collision["roles"]["implementation_owners"][0]
        check("reject_role_collision", bool(validate_stage(collision, tasks, cases)), "negative mutation must be rejected")
        broadened = copy.deepcopy(control)
        broadened["state"] = "RUNNING"
        broadened["authorization_scope"] = "OFFLINE_AND_LIVE"
        check("reject_unknown_authorization_scope", bool(validate_stage(broadened, tasks, cases)),
              "negative mutation must be rejected")

    result = {
        "kind": "GOVERNANCE_VALIDATION_NOT_PRODUCT_ACCEPTANCE",
        "project_id": control.get("project_id"),
        "stage_id": "V0-S1",
        "passed": sum(item["passed"] for item in checks),
        "failed": sum(not item["passed"] for item in checks),
        "product_tests_executed": False,
        "target_runtime_touched": False,
        "checks": checks,
    }
    if args.write_report:
        (ROOT / "reports" / "governance-validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False, indent=2))
    for item in checks:
        if not item["passed"]:
            print("FAIL", item)
    return 1 if result["failed"] else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    execution = load_json(ROOT / "plans" / "execution-control.json")
    if execution.get("coordinate", {}).get("stage_id") == "V0-S1":
        return main_v0_s1(args, execution)

    checks: list[dict] = []

    def check(name: str, condition: bool, detail: str = ""):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})

    packet_files = {path.name for path in STAGE_DIR.iterdir()} if STAGE_DIR.is_dir() else set()
    check("stage_packet_inventory", packet_files == REQUIRED_PACKET_FILES, str(sorted(REQUIRED_PACKET_FILES - packet_files)))
    control = load_json(STAGE_DIR / "stage-control.json")
    tasks = load_json(ROOT / "plans" / "tasks.json")
    cases = load_json(ROOT / "plans" / "acceptance_cases.json")
    for error in validate_stage(control, tasks, cases):
        check("stage_control", False, error)
    if not validate_stage(control, tasks, cases):
        check("stage_control", True)

    control_hash = product_control_digest()
    check("baseline_product_control_fingerprint", control["baseline"]["product_control_sha256"] == control_hash, control_hash)
    for authority in control["authorities"]:
        check("authority:" + authority, (ROOT / authority).is_file())
    for error in verify_manifest():
        check("stage_manifest", False, error)
    if not verify_manifest():
        check("stage_manifest", True)
    for error in verify_prepared_stage(tasks, cases):
        check("prepared_stage", False, error)
    if not verify_prepared_stage(tasks, cases):
        check("prepared_stage", True)

    execution = load_json(ROOT / "plans" / "execution-control.json")
    check("single_coordinate_stage", execution["coordinate"]["stage_id"] == control["stage_id"])
    check("single_coordinate_state", execution["coordinate"]["state"] == control["state"])
    check("product_status_not_promoted", execution["product_status"] == "NOT_RUN")
    check("packet_reference", (ROOT / execution["stage_packet"]).resolve() == (STAGE_DIR / "stage-control.json").resolve())
    check("manifest_reference", (ROOT / execution["stage_packet_manifest"]).resolve() == (STAGE_DIR / "PAYLOAD_MANIFEST.sha256").resolve())
    case_status = {item["case_id"]: item["status"] for item in cases["cases"]}
    check("fixed_cases_still_not_run", all(case_status[item] == "NOT_RUN" for item in control["fixed_acceptance_ids"]))

    actual_receipt_path = ROOT / "reports" / "v0-s0" / "implementation-receipt-rerun-02.json"
    live_receipt_path = ROOT / "reports" / "v0-s0" / "rerun-02" / "probe-summary.json"
    check("actual_implementation_receipt_exists", actual_receipt_path.is_file())
    check("actual_live_receipt_exists", live_receipt_path.is_file())
    if actual_receipt_path.is_file() and live_receipt_path.is_file():
        actual_receipt = load_json(actual_receipt_path)
        live_receipt = load_json(live_receipt_path)
        expected_candidate = live_receipt.get("candidate_sha")
        for error in validate_receipt(actual_receipt, expected_candidate, control):
            check("actual_implementation_receipt", False, error)
        if not validate_receipt(actual_receipt, expected_candidate, control):
            check("actual_implementation_receipt", True)

        retry = actual_receipt.get("effective_attempts", {})
        retry_limit = control.get("budgets", {}).get("max_effective_retries_per_probe")
        check(
            "actual_retry_budget",
            retry_limit is not None
            and retry.get("image", retry_limit + 1) <= retry_limit
            and retry.get("video", retry_limit + 1) <= retry_limit
            and retry.get("correction_retries_used", retry_limit + 1) <= retry_limit,
            json.dumps(retry, ensure_ascii=False),
        )
        check(
            "actual_product_denominator_not_promoted",
            all(live_receipt.get("product_acceptance", {}).get(item) == "NOT_RUN" for item in control["fixed_acceptance_ids"]),
        )
        raw_refs = actual_receipt.get("raw_artifact_refs", [])
        check(
            "actual_raw_evidence_refs",
            bool(raw_refs) and all((ROOT / item).is_file() for item in raw_refs),
            "raw command/HTTP/resource/cleanup artifacts are required",
        )
        production_path = actual_receipt.get("production_path", {})
        path_status = actual_receipt.get("production_path_status") or production_path.get("exact_stop_reason")
        trace_refs = actual_receipt.get("public_end_to_end_trace_refs", [])
        check(
            "actual_public_entry_disposition",
            bool(trace_refs)
            or (
                path_status == "NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL"
                and production_path.get("end_to_end_claim") is False
                and actual_receipt.get("decision") == "NO_GO"
                and actual_receipt.get("stage_pass_claim") is False
            ),
            str(path_status),
        )

        evidence_manifest = ROOT / "reports" / "v0-s0" / "rerun-02" / "artifact-manifest.json"
        for error in validate_evidence_manifest(evidence_manifest, expected_candidate):
            check("actual_evidence_manifest", False, error)
        if not validate_evidence_manifest(evidence_manifest, expected_candidate):
            check("actual_evidence_manifest", True)

        git_root = ROOT.parent
        for field in ("candidate_sha", "evidence_commit"):
            commit_id = actual_receipt.get(field, "")
            resolved = subprocess.run(
                ["git", "-C", str(git_root), "cat-file", "-e", f"{commit_id}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            check(f"actual_git_commit:{field}", resolved.returncode == 0, commit_id)

        evidence_commit = actual_receipt.get("evidence_commit", "")
        changed = subprocess.run(
            ["git", "-C", str(git_root), "show", "--name-only", "--format=", evidence_commit],
            capture_output=True,
            text=True,
            check=False,
        )
        prefix = ROOT.name + "/"
        actual_changed = {
            line[len(prefix):]
            for line in changed.stdout.splitlines()
            if line.startswith(prefix)
        }
        check(
            "actual_changed_files_receipt",
            changed.returncode == 0 and set(actual_receipt.get("changed_files", [])) == actual_changed,
            "declared=" + json.dumps(sorted(actual_receipt.get("changed_files", [])))
            + "; actual=" + json.dumps(sorted(actual_changed)),
        )

    independent_review = ROOT / "reports" / "v0-s0" / "independent-review-rerun-02.md"
    check("independent_review_exists", independent_review.is_file())
    if independent_review.is_file():
        review_text = independent_review.read_text(encoding="utf-8")
        major_match = re.search(r"Major \*\*(\d+)\*\*", review_text)
        major_count = int(major_match.group(1)) if major_match else None
        check("independent_major_count_parseable", major_count is not None)
        correction16_review = ROOT / "reports" / "v0-s0" / "independent-review-correction-16.md"
        correction16_text = correction16_review.read_text(encoding="utf-8") if correction16_review.is_file() else ""
        correction16_major_match = re.search(r"Major\s+\**(\d+)", correction16_text)
        correction16_major_count = int(correction16_major_match.group(1)) if correction16_major_match else None
        check("correction16_independent_review_zero_major", correction16_major_count == 0)
        check(
            "independent_majors_block_exit",
            major_count == 0
            or control.get("state") == execution["coordinate"]["state"] in {"BLOCKED", "NO_GO"}
            or (
                control.get("state") == execution["coordinate"]["state"] == "STAGE_BASELINE_COMPLETE"
                and execution.get("last_passed_gate", {}).get("id") == "V0_S0_STAGE_BASELINE_COMPLETE"
                and correction16_major_count == 0
            )
            or (
                control.get("state") == execution["coordinate"]["state"] == "RUNNING"
                and execution["coordinate"].get("workpack_id")
                in {"WP-S0-06", "WP-S0-07", "WP-S0-08", "WP-S0-10", "WP-S0-12", "WP-S0-14", "WP-S0-15", "WP-S0-16", "WP-S0-17", "WP-S0-18", "WP-S0-19", "WP-S0-20", "WP-S0-21", "WP-S0-22", "WP-S0-23", "WP-S0-24", "WP-S0-26", "WP-S0-27", "WP-S0-29", "WP-S0-31", "WP-S0-32", "WP-S0-34", "WP-S0-35", "WP-S0-37", "WP-S0-38", "WP-S0-40", "WP-S0-41", "WP-S0-43", "WP-S0-44", "WP-S0-46"}
                and execution.get("last_passed_gate", {}).get("id")
                in {
                    "WP_S0_05_INDEPENDENT_REVIEW_COMPLETE",
                    "WP_S0_07_OFFLINE_CANDIDATE_SEALED",
                    "WP_S0_08_NETWORK_STOP_EVIDENCE_SEALED",
                    "WP_S0_10_NO_CLOUD_GATE_PASS_COMFY_PATH_BLOCKED",
                    "WP_S0_12_IMAGE_PUBLIC_PATH_PASS_VIDEO_ORACLE_STOP",
                    "WP_S0_15_OFFLINE_CANDIDATE_SEALED",
                    "WP_S0_17_INDEPENDENT_NO_GO_REVIEW_COMPLETE",
                    "WP_S0_19_HARNESS_CANDIDATE_SEALED",
                    "WP_S0_21_INDEPENDENT_BLOCK_REVIEW_COMPLETE",
                    "WP_S0_23_CORRECTION_08_OFFLINE_HARNESS_SEALED",
                    "WP_S0_25_INDEPENDENT_REVIEW_COMPLETE",
                    "WP_S0_28_CORRECTION_09_INDEPENDENT_REVIEW_COMPLETE",
                    "WP_S0_30_INDEPENDENT_RESOURCE_STOP_REVIEW_COMPLETE",
                    "WP_S0_33_INDEPENDENT_MAJOR_REVIEW_COMPLETE",
                    "WP_S0_36_INDEPENDENT_MAJOR_REVIEW_COMPLETE",
                    "WP_S0_39_INDEPENDENT_MAJOR_REVIEW_COMPLETE",
                    "WP_S0_42_INDEPENDENT_MAJOR_REVIEW_COMPLETE",
                    "WP_S0_45_INDEPENDENT_REVIEW_COMPLETE",
                }
            )
            or (
                control.get("state") == execution["coordinate"]["state"] == "WAIT_AUTH"
                and (
                    (execution["coordinate"].get("workpack_id") == "WP-S0-24"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_23_CORRECTION_08_OFFLINE_HARNESS_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-29"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_28_CORRECTION_09_INDEPENDENT_REVIEW_COMPLETE")
                )
            )
            or (
                control.get("state") == execution["coordinate"]["state"] == "CHECKPOINT"
                and (
                    (execution["coordinate"].get("workpack_id") == "WP-S0-25"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_24_TERMINAL_EVIDENCE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-30"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_29_TERMINAL_EVIDENCE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-33"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_32_OFFLINE_CANDIDATE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-36"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_35_OFFLINE_CANDIDATE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-39"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_38_OFFLINE_CANDIDATE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-42"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_41_OFFLINE_CANDIDATE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-45"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_44_OFFLINE_CANDIDATE_SEALED")
                    or
                    (execution["coordinate"].get("workpack_id") == "WP-S0-47"
                     and execution.get("last_passed_gate", {}).get("id")
                     == "WP_S0_46_TERMINAL_EVIDENCE_SEALED")
                )
            ),
            f"major_count={major_count}",
        )
        check(
            "checkpoint_coordinate",
            (
                execution["coordinate"].get("workpack_id") == "WP-S0-47"
                and execution["coordinate"].get("gate") == "GATE5_INDEPENDENT_EXIT"
                and execution["coordinate"].get("state") == "STAGE_BASELINE_COMPLETE"
            )
            or (
                execution["coordinate"].get("workpack_id") in {"WP-S0-30", "WP-S0-45"}
                and execution["coordinate"].get("gate") == "GATE4_REAL_ACCEPTANCE"
                and execution["coordinate"].get("state") == "BLOCKED"
            )
            or (
                execution["coordinate"].get("workpack_id") == "WP-S0-05"
                and execution["coordinate"].get("gate") == "GATE3_CHECKPOINT"
            )
            or (
                execution["coordinate"].get("workpack_id")
                in {"WP-S0-06", "WP-S0-07", "WP-S0-08", "WP-S0-10", "WP-S0-12", "WP-S0-14", "WP-S0-15", "WP-S0-16", "WP-S0-18", "WP-S0-19", "WP-S0-20", "WP-S0-22", "WP-S0-23", "WP-S0-24", "WP-S0-26", "WP-S0-27", "WP-S0-29", "WP-S0-31", "WP-S0-32", "WP-S0-34", "WP-S0-35", "WP-S0-37", "WP-S0-38", "WP-S0-40", "WP-S0-41", "WP-S0-43", "WP-S0-44", "WP-S0-46"}
                and execution["coordinate"].get("gate") in {"GATE1_IMPLEMENTATION", "GATE2_WORKPACK", "GATE4_REAL_ACCEPTANCE"}
            )
            or (
                execution["coordinate"].get("workpack_id") in {"WP-S0-11", "WP-S0-13", "WP-S0-17", "WP-S0-21", "WP-S0-25", "WP-S0-28", "WP-S0-30", "WP-S0-33", "WP-S0-36", "WP-S0-39", "WP-S0-42", "WP-S0-45", "WP-S0-47"}
                and execution["coordinate"].get("gate") == "GATE3_CHECKPOINT"
            ),
        )

    registry = load_json(GOV / "project-registry.json")
    project = next((item for item in registry.get("projects", []) if item.get("project_id") == control["project_id"]), None)
    check("project_registry_entry", bool(project))
    if project:
        check("project_registry_coordinate", project["current_stage"] == control["stage_id"] and project["state"] == control["state"])
        check("unborn_repo_has_no_parallel_writes", control["baseline"]["git_commit"] != "UNBORN_WORKTREE" or project["write_slots"] == 0)

    receipt_template = load_json(GOV / "templates" / "implementation-receipt.json")
    check("receipt_template_fields", not (REQUIRED_RECEIPT_FIELDS - set(receipt_template)))
    check("receipt_count_fields", not (COUNT_FIELDS - set(receipt_template["test_counts"])))
    metrics_template = load_json(GOV / "templates" / "metrics-record.json")
    check("cost_and_rework_metrics", all(name in metrics_template for name in ("provider_model", "retry_cost", "review_cost", "human_minutes", "first_acceptance_pass", "independent_defects")))
    check("runtime_state_ignored", all((GOV / "runtime" / name / ".gitkeep").is_file() for name in ("task-queue", "receipts", "metrics")))

    if args.self_test:
        checks.extend({"check": item["name"], "passed": item["passed"], "detail": "negative mutation must be rejected"} for item in run_self_tests(control, tasks, cases))

    live_probe_receipt = ROOT / "reports" / "v0-s0" / "live-probe-receipt.json"
    result = {
        "kind": "GOVERNANCE_VALIDATION_NOT_PRODUCT_ACCEPTANCE",
        "project_id": "lvw-prompt-service",
        "stage_id": "V0-S0",
        "passed": sum(item["passed"] for item in checks),
        "failed": sum(not item["passed"] for item in checks),
        "product_tests_executed": False,
        "target_runtime_touched": live_probe_receipt.is_file(),
        "checks": checks,
    }
    if args.write_report:
        (ROOT / "reports" / "governance-validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False, indent=2))
    for item in checks:
        if not item["passed"]:
            print("FAIL", item)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
