#!/usr/bin/env python3
"""Offline verifier and sealer for the WP-S0-04 rerun evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
MANIFEST = HERE / "artifact-manifest.json"
SELF_CHECK = HERE / "offline-self-check.json"
RECEIPT = PROJECT / "reports/v0-s0/implementation-receipt-rerun-02.json"
RUN_ID = "v0-s0-rerun-20261027-02"
CANDIDATE = "95be0cd82c5500b0a71e3597f5188b147f11e75f"
ZERO_COMMIT = "0" * 40


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resource_summary(name: str):
    rows = [json.loads(line) for line in (HERE / name).read_text().splitlines() if line]
    gpu = [int(row["gpu_memory_mib"].split(",")[0]) for row in rows if row["gpu_query_exit_code"] == 0]
    ram = [row["host_mem_available_mib"] for row in rows if row["host_mem_available_mib"] is not None]
    return {"samples": len(rows), "gpu_memory_mib_min": min(gpu), "gpu_memory_mib_peak": max(gpu),
            "host_mem_available_mib_min": min(ram), "host_mem_available_mib_max": max(ram)}


def sanitize_startup_logs():
    """Redact target-configured drive paths without reading those targets."""
    drive_path = re.compile(r"[A-Za-z]:\\[^\s\"']+")
    for path in HERE.glob("*.log"):
        text = path.read_text(encoding="utf-8", errors="replace")
        redacted = drive_path.sub("ABSOLUTE_PATH_REDACTED", text)
        if redacted != text:
            path.write_text(redacted, encoding="utf-8")


def evaluate():
    summary = load("probe-summary.json")
    tags = load("ollama-tags-raw.json")
    events = load("command-events.json")
    cleanup = load("cleanup.json")
    config = load("config-integrity.json")
    registry = load("comfy-object-info-raw.json")
    checks = {
        "run_id": summary.get("run_id") == RUN_ID,
        "candidate_sha": summary.get("candidate_sha") == CANDIDATE,
        "attempt_budget": summary.get("attempts") == {"image": 1, "video": 1},
        "image_json_schema": all(x.get("json_parse") and x.get("schema_valid") for x in summary["results"]["image"]),
        "video_json_schema": all(x.get("json_parse") and x.get("schema_valid") for x in summary["results"]["video"]),
        "product_cases_not_run": set(summary["product_acceptance"].values()) == {"NOT_RUN"},
        "separate_paths_no_false_e2e": summary["production_path"] == {
            "comfy_registry_probe": "SEPARATE_PUBLIC_REGISTRY_OBSERVATION",
            "ollama_direct_probe": "SEPARATE_DIRECT_LOCAL_MODEL_CALL",
            "connected_public_entry": False,
            "conclusion": "NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL",
        },
        "registry_nodes_present": all(x in registry for x in ("ImageCaptionNode", "VideoCaptionNode")),
        "registry_has_no_ollama_option": all(
            not any("ollama" in str(option).lower()
                    for option in registry[node]["input"]["required"]["vlm_service"][1]["options"])
            for node in ("ImageCaptionNode", "VideoCaptionNode")
        ),
        "model_digest": any(x.get("digest") == "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"
                            and x.get("name") == "gemma4:26b" for x in tags.get("models", [])),
        "pa_llm_failure_raw": load("pa-models-list-llm-raw.json") == {"success": False, "error": "name 'ModelListService' is not defined"},
        "pa_vision_failure_raw": load("pa-models-list-vision-raw.json") == {"success": False, "error": "name 'ModelListService' is not defined"},
        "config_unchanged": config.get("unchanged") is True,
        "temp_removed": cleanup[-1].get("run_temp_removed") is True,
        "final_listeners_empty": any(item.get("final_listeners") == [] for item in cleanup),
        "post_attempt_ps_empty": all(load(name).get("models") == [] for name in (
            "ollama-image-attempt-1-ps-t0.json", "ollama-image-attempt-1-ps-t5.json",
            "ollama-video-attempt-1-ps-t0.json", "ollama-video-attempt-1-ps-t5.json")),
        "http_events_have_status": all("http_status" in event for event in events if event["logical_command"][:1] == ["HTTP"]),
        "sample_hashes_match_first_run": load("sample-hashes.json")["image"]["sha256"] == "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
            and load("sample-hashes.json")["video"]["sha256"] == "694a50bfb871faed6540a577b25c8a61e629035062a23f982099a6911ff22152",
        "four_frame_hashes": len(load("frame-hashes.json")) == 4 and len({x["sha256"] for x in load("frame-hashes.json")}) == 4,
        "startup_failures_retained": all((HERE / f"harness-failure-{i:02d}-harness-error.json").is_file() for i in (1, 2)),
    }
    text_files = [p for p in HERE.iterdir() if p.is_file() and p.suffix != ".py" and p.name != MANIFEST.name]
    private_hits = []
    for path in text_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"/mnt/[a-z]/[^\s\"']+", text) or re.search(r"[A-Za-z]:\\(?:Users|mnt|ComfyUI)[^\s\"']*", text):
            private_hits.append(path.name)
    checks["no_unredacted_absolute_private_paths"] = not private_hits
    return checks, private_hits


def write_outputs():
    sanitize_startup_logs()
    checks, private_hits = evaluate()
    self_check = {
        "schema_version": "lvw.offline-self-check/1", "run_id": RUN_ID,
        "checks": checks, "all_passed": all(checks.values()),
        "private_path_hit_files": private_hits,
        "resources": {"image": resource_summary("resources-image-1.jsonl"),
                      "video": resource_summary("resources-video-1.jsonl")},
    }
    SELF_CHECK.write_text(json.dumps(self_check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not self_check["all_passed"]:
        raise SystemExit("offline evidence checks failed")
    artifacts = []
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.name != MANIFEST.name:
            artifacts.append({"path": f"reports/v0-s0/rerun-02/{path.name}", "bytes": path.stat().st_size,
                              "sha256": digest(path)})
    manifest = {"schema_version": "lvw.artifact-manifest/1", "run_id": RUN_ID,
                "excludes": ["reports/v0-s0/rerun-02/artifact-manifest.json"], "artifacts": artifacts}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rerun_files = [item["path"] for item in artifacts] + ["reports/v0-s0/rerun-02/artifact-manifest.json"]
    receipt = {
        "schema_version": "lvw.implementation-receipt/1",
        "project_id": "lvw-prompt-service", "stage_id": "V0-S0", "workpack_id": "WP-S0-04",
        "run_id": RUN_ID, "candidate_sha": CANDIDATE,
        "implementation_owner_role": "codex_isolated_implementer",
        "implementation_session": "/root/s0_rerun_implementer",
        "authorization_ref": "reports/v0-s0/authorization-rerun-02.json",
        "evidence_commit": ZERO_COMMIT,
        "evidence_commit_status": "PENDING_ROOT_SEALING; placeholder must be replaced only by root gate owner after evidence commit",
        "changed_files": rerun_files + ["reports/v0-s0/implementation-receipt-rerun-02.json"],
        "contract_changes": [], "target_configuration_changes": [],
        "commands": [
            {"logical_command": "python3 -B reports/v0-s0/rerun-02/probe.py --comfy-root COMFY_ROOT --test-source TEST_SOURCE --comfy-python COMFY_PYTHON --ollama-exe OLLAMA_EXE", "exit_codes": [1, 1, 0],
             "note": "Two pre-model harness/startup failures retained; final execution succeeded."},
            {"logical_command": "python3 -B reports/v0-s0/rerun-02/seal.py", "exit_code": 0},
            {"logical_command": "python3 -B reports/v0-s0/rerun-02/seal.py --verify", "exit_code": 0, "status": "to_be_confirmed_by_post_write_check"},
        ],
        "effective_attempts": {"image": 1, "video": 1, "limit_each": 2, "correction_retries_used": 0},
        "probe_results": {
            "image": "HTTP_200_JSON_PARSE_AND_SCHEMA_PASS",
            "video": "HTTP_200_JSON_PARSE_AND_SCHEMA_PASS",
            "prompt_assistant_models_list_llm": "HTTP_500_MODELLISTSERVICE_NAMEERROR",
            "prompt_assistant_models_list_vision": "HTTP_500_MODELLISTSERVICE_NAMEERROR",
            "connected_public_entry": "NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL",
        },
        "production_path": {
            "comfy_registry": "observed separately through public /object_info",
            "ollama_model": "called separately through local /api/chat",
            "end_to_end_claim": False,
            "exact_stop_reason": "NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL",
        },
        "model": {"tag": "gemma4:26b", "digest": "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"},
        "product_acceptance": {x: "NOT_RUN" for x in ("V0-A01", "V0-A02", "V0-A09", "V0-A10")},
        "private_external_actions": {"cloud_or_paid_provider_calls": 0, "downloads_or_upgrades": 0,
                                     "visible_browser_runs": 0, "authorized_media_files_read": 2,
                                     "effective_local_model_calls": 2, "run_owned_services_started": 2},
        "cleanup": {"owned_services_stopped": True, "ports_8188_11434_empty": True,
                    "temporary_frames_removed": 4, "post_attempt_api_ps_empty": True},
        "resource_summary": self_check["resources"],
        "risks": [
            "No connected public Comfy/Prompt Assistant entry exposes the verified local Ollama model; direct Ollama feasibility cannot be promoted to E2E PASS.",
            "Prompt Assistant models/list remains broken for both llm and vision with ModelListService undefined.",
            "Comfy portable Python requires -s to avoid incompatible user-site pydantic shadowing; no package or configuration was changed.",
            "Peak observed GPU memory was close to device capacity; these samples are a baseline, not V0-A09 performance acceptance.",
            "A historical missing deepseek-r1 cache blob remains visible in Ollama startup logs and was not repaired or deleted.",
        ],
        "decision": "NO_GO",
        "stage_pass_claim": False,
        "next_owner": "codex_isolated_reviewer",
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failures = []
    listed = set()
    for item in manifest["artifacts"]:
        path = PROJECT / item["path"]
        listed.add(path.resolve())
        if not path.is_file() or digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            failures.append(item["path"])
    expected = {p.resolve() for p in HERE.iterdir() if p.is_file() and p.name != MANIFEST.name}
    if listed != expected:
        failures.append("manifest_coverage_mismatch")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt["candidate_sha"] != CANDIDATE or receipt["decision"] not in {"READY_FOR_REVIEW", "NO_GO", "BLOCKED"}:
        failures.append("receipt_contract")
    if receipt["evidence_commit"] != ZERO_COMMIT or not receipt["evidence_commit_status"].startswith("PENDING_ROOT_SEALING"):
        failures.append("evidence_commit_placeholder")
    checks, _ = evaluate()
    if not all(checks.values()):
        failures.append("offline_evidence_checks")
    print(json.dumps({"manifest_artifacts": len(listed), "failures": failures,
                      "receipt_json": True, "all_json_files_parse": all_json_parse()}, ensure_ascii=False))
    return 1 if failures else 0


def all_json_parse() -> bool:
    paths = list(HERE.glob("*.json")) + [RECEIPT]
    try:
        for path in paths:
            json.loads(path.read_text(encoding="utf-8"))
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        return verify()
    write_outputs()
    return 0


if __name__ == "__main__":
    sys.exit(main())
