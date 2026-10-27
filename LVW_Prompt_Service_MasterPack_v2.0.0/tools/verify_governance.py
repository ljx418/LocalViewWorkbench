#!/usr/bin/env python3
"""Validate agent governance structure and false-green guards, not the product."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / ".agent-governance"
STAGE_DIR = GOV / "stages" / "V0-S0"

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
    "spec_version",
    "acceptance_hash",
    "gate_version",
    "run_id",
    "environment",
    "check_results",
    "test_counts",
    "artifact_refs",
    "risks",
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
        if control.get("authorization_records"):
            errors.append("WAIT_AUTH must not claim active authorization records")
    elif external:
        if state not in {"RUNNING", "CHECKPOINT", "STAGE_BASELINE_COMPLETE", "NO_GO", "BLOCKED", "WAIT_BUDGET"}:
            errors.append("external/private Stage has an invalid post-authorization state")
        records = control.get("authorization_records", [])
        if not records:
            errors.append("post-authorization Stage is missing authorization_records")
        for record in records:
            if not (ROOT / record).is_file():
                errors.append(f"authorization record is missing: {record}")
    if control.get("budgets", {}).get("max_effective_retries_per_probe", 99) > 2:
        errors.append("retry budget exceeds the frozen V0-S0 maximum")
    protected = set(control.get("forbidden_paths", []))
    for required in {"contracts/", "plans/acceptance_cases.json", "plans/release_gates.json"}:
        if required not in protected:
            errors.append(f"protected path missing: {required}")
    return errors


def validate_receipt(receipt: dict, expected_candidate: str | None = None) -> list[str]:
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
    if receipt.get("decision") == "PASS":
        if counts["pass"] != counts["denominator"] or any(counts[name] for name in ("fail", "blocked", "skipped", "not_run")):
            errors.append("PASS contains an incomplete or non-passing fixed denominator")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

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

    execution = load_json(ROOT / "plans" / "execution-control.json")
    check("single_coordinate_stage", execution["coordinate"]["stage_id"] == control["stage_id"])
    check("single_coordinate_state", execution["coordinate"]["state"] == control["state"])
    check("product_status_not_promoted", execution["product_status"] == "NOT_RUN")
    check("packet_reference", (ROOT / execution["stage_packet"]).resolve() == (STAGE_DIR / "stage-control.json").resolve())
    check("manifest_reference", (ROOT / execution["stage_packet_manifest"]).resolve() == (STAGE_DIR / "PAYLOAD_MANIFEST.sha256").resolve())
    case_status = {item["case_id"]: item["status"] for item in cases["cases"]}
    check("fixed_cases_still_not_run", all(case_status[item] == "NOT_RUN" for item in control["fixed_acceptance_ids"]))

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
