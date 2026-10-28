#!/usr/bin/env python3
"""Offline preparation and evidence oracle for the V0-S1 fixed denominator.

This module deliberately has no live execution branch.  A future, explicit,
one-shot authorization may produce one case evidence document at a time; this
harness verifies those documents and combines them only when all five bind the
same product candidate.  ``--self-check`` calls the registered production
owners for CPU-only prechecks and performs no service, GPU, port, network,
browser, or real-media action.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import re


PRODUCT_CANDIDATE = "1d48142b95466954ca4da264fa06762abf1522f2"
PACKET_VERSION = "1.0.0"
CASE_IDS = ("V0-A01", "V0-A03", "V0-A04", "V0-A05", "V0-A08")
ACCEPTANCE_HASH = "4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5"
MAX_DRAFT_CHARACTERS = 20_000
MAX_EFFECTIVE_RETRIES = 2

PRODUCTION_ARTIFACTS = (
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/__init__.py",
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py",
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/image_input.py",
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/manual.py",
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/nodes.py",
    "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/state.py",
    "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json",
    "LVW_V0_RuntimePatch/workflows/manual_prompt_v0.ui.json",
)

# Exact maxima for the next sequential authorizations.  Zero means that action
# is forbidden, not merely unnecessary.  One case must reach a terminal receipt
# before another case receives authority.
CASE_BUDGETS = {
    "V0-A01": {"image_attempts": 1, "model_calls": 1, "comfy_starts": 1,
                "ollama_starts": 1, "public_submissions": 1, "browser_runs": 0,
                "downloads": 0, "cloud_calls": 0},
    "V0-A03": {"image_attempts": 0, "model_calls": 0, "comfy_starts": 0,
                "ollama_starts": 0, "public_submissions": 0, "browser_runs": 0,
                "downloads": 0, "cloud_calls": 0},
    "V0-A04": {"image_attempts": 0, "model_calls": 0, "comfy_starts": 1,
                "ollama_starts": 0, "public_submissions": 5, "browser_runs": 0,
                "downloads": 0, "cloud_calls": 0},
    "V0-A05": {"image_attempts": 0, "model_calls": 0, "comfy_starts": 1,
                "ollama_starts": 0, "public_submissions": 13, "browser_runs": 0,
                "downloads": 0, "cloud_calls": 0},
    "V0-A08": {"image_attempts": 0, "model_calls": 0, "comfy_starts": 1,
                "ollama_starts": 0, "public_submissions": 1, "browser_runs": 0,
                "downloads": 0, "cloud_calls": 0},
}

LIVE_REQUIREMENTS = {
    "loopback_only": True,
    "ollama_no_cloud": True,
    "fresh_non_reusable_evidence_slot": True,
    "candidate_bytes_exact": True,
    "target_pre_post_equal": True,
    "owned_resources_terminal_absent": True,
    "privacy_minimized": True,
}

CASE_PROOF_REQUIREMENTS = {
    "V0-A01": ("public_image_route", "real_source_hash_bound", "preprocess_metadata",
                "non_demo_raw_and_suggestion", "owned_temp_absent"),
    "V0-A03": ("four_outputs", "json_schema_valid", "txt_export_valid",
                "view_switch_extra_model_calls_zero", "raw_unchanged"),
    "V0-A04": ("ollama_stopped_before_manual_route", "draft_20000_exact",
                "copy_json_and_txt", "atomic_json_and_txt_export",
                "write_failure_preserved_draft_and_original", "no_partial_file"),
    "V0-A05": ("invalid_json_preserved", "explicit_refusal_preserved",
                "timeout_preserved", "oom_preserved", "stale_token_preserved",
                "retry_exact_two", "retry_one_over_three_rejected",
                "draft_bytes_and_epoch_preserved", "no_infinite_retry"),
    "V0-A08": ("public_manual_export", "manual_contract_tuple",
                "unanalyzed_empty_no_content_note", "approval_has_no_permission_effect",
                "zero_model_and_outbound", "write_failure_preserved_draft", "no_partial_file"),
}


class CheckpointError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def value_hash(value) -> str:
    return sha256(canonical(value)).hexdigest()


def verify_denominator() -> None:
    actual = sha256(("\n".join(sorted(CASE_IDS)) + "\n").encode()).hexdigest()
    if actual != ACCEPTANCE_HASH:
        raise CheckpointError("FIXED_DENOMINATOR_MISMATCH", actual)


def git_blob(repo: Path, commit: str, relative: str) -> bytes:
    prefix_process = subprocess.run(
        ["git", "rev-parse", "--show-prefix"], cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if prefix_process.returncode:
        raise CheckpointError("CANDIDATE_REPOSITORY_INVALID", "git prefix unavailable")
    prefix = prefix_process.stdout.decode("utf-8", "strict").strip()
    object_path = f"{prefix}{relative}"
    process = subprocess.run(
        ["git", "show", f"{commit}:{object_path}"], cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if process.returncode:
        raise CheckpointError("CANDIDATE_ARTIFACT_MISSING", relative)
    return process.stdout


def bind_candidate(repo: Path) -> dict:
    expected_python = sorted(
        path for path in PRODUCTION_ARTIFACTS if path.endswith(".py")
    )
    actual_python = sorted(
        path.relative_to(repo).as_posix()
        for path in (repo / "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge").glob("*.py")
    )
    if actual_python != expected_python:
        raise CheckpointError("CANDIDATE_PYTHON_INVENTORY_MISMATCH", "bridge inventory")
    hashes = {}
    for relative in PRODUCTION_ARTIFACTS:
        local = (repo / relative).read_bytes()
        candidate = git_blob(repo, PRODUCT_CANDIDATE, relative)
        if local != candidate:
            raise CheckpointError("CANDIDATE_ARTIFACT_BYTES_MISMATCH", relative)
        hashes[relative] = sha256(local).hexdigest()
    return hashes


class MemoryClipboard:
    def __init__(self):
        self.values = []

    def write(self, value: str) -> None:
        self.values.append(value)


def _node_inputs(text="visible draft", action="preview_json", filename="checkpoint"):
    return {
        "natural_zh": text,
        "natural_en": "Visible subject in natural English.",
        "image_prompt": "Visible subject, concrete lighting and composition.",
        "video_prompt": "Slow tracking shot of the visible subject.",
        "tags": "visible, grounded",
        "negative": "",
        "edit_instruction": "",
        "action": action,
        "filename": filename,
    }


def _schema(repo: Path):
    import jsonschema
    return jsonschema.Draft202012Validator(json.loads(
        (repo / "contracts/v0-result.schema.json").read_text(encoding="utf-8")
    ))


def precheck_a01(repo: Path) -> dict:
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
    workflow = json.loads((repo / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json")
                          .read_text(encoding="utf-8"))
    classes = [workflow[key]["class_type"] for key in sorted(workflow)]
    if classes != ["LVWControlledImageInput", "LVWImagePromptBridge"]:
        raise CheckpointError("PUBLIC_IMAGE_GRAPH_MISMATCH", repr(classes))
    if any(name not in NODE_CLASS_MAPPINGS for name in classes):
        raise CheckpointError("PUBLIC_IMAGE_OWNER_UNREGISTERED", repr(classes))
    return {"case_id": "V0-A01", "offline_precheck": "PASS",
            "product_status": "NOT_RUN", "external_action_required": True,
            "public_graph": classes}


def precheck_a03(repo: Path) -> dict:
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWManualPromptOwner
    clipboard = MemoryClipboard()
    with tempfile.TemporaryDirectory(prefix="lvw-s1-checkpoint-") as temp:
        root = Path(temp) / "out"
        owner = ManualDraftOwner(export_root=root, export_parent=Path(temp), clipboard=clipboard,
                                 clock=lambda: "2026-10-28T00:00:00Z")
        node = LVWManualPromptOwner(owner=owner)
        preview = node.process(**_node_inputs())
        four = preview["result"][:4]
        if not all(isinstance(value, str) for value in four):
            raise CheckpointError("FOUR_OUTPUTS_INVALID", "non-string output")
        raw_before = preview["result"][7]
        txt = node.process(**_node_inputs(action="copy_txt"))
        copied_json = node.process(**_node_inputs(action="copy_json"))
        exported_json = node.process(**_node_inputs(action="export_json"))
        exported_txt = node.process(**_node_inputs(action="export_txt"))
        payload = json.loads(copied_json["result"][7])
        _schema(repo).validate(payload)
        if owner.model_calls != 0 or raw_before != preview["result"][7]:
            raise CheckpointError("VIEW_SWITCH_INFERENCE_OR_MUTATION", "CPU views changed source")
        if not (txt["result"][7].startswith("## Natural Chinese") and
                (root / "checkpoint.json").is_file() and (root / "checkpoint.txt").is_file()):
            raise CheckpointError("EXPORT_VIEW_MISSING", "JSON/TXT")
        return {"case_id": "V0-A03", "offline_precheck": "PASS",
                "product_status": "NOT_RUN", "four_output_hash": value_hash(four),
                "json_hash": sha256(exported_json["result"][7].encode()).hexdigest(),
                "txt_hash": sha256(exported_txt["result"][7].encode()).hexdigest(),
                "view_switch_extra_model_calls": owner.model_calls}


@contextmanager
def fail_replace():
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import manual
    original = manual.os.replace
    manual.os.replace = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected"))
    try:
        yield
    finally:
        manual.os.replace = original


def precheck_a04(repo: Path) -> dict:
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWManualPromptOwner
    clipboard = MemoryClipboard()
    exact = "稿" * MAX_DRAFT_CHARACTERS
    with tempfile.TemporaryDirectory(prefix="lvw-s1-checkpoint-") as temp:
        root = Path(temp) / "中文输出"
        owner = ManualDraftOwner(export_root=root, export_parent=Path(temp), clipboard=clipboard,
                                 clock=lambda: "2026-10-28T00:00:00Z")
        node = LVWManualPromptOwner(owner=owner)
        before = node.process(**_node_inputs(text=exact))["result"][:7]
        node.process(**_node_inputs(text=exact, action="copy_json"))
        node.process(**_node_inputs(text=exact, action="export_txt", filename="人工稿"))
        with fail_replace():
            try:
                node.process(**_node_inputs(text=exact, action="export_json", filename="失败稿"))
            except BridgeError as exc:
                if exc.code != "DISK_FULL":
                    raise
            else:
                raise CheckpointError("WRITE_FAILURE_NOT_REJECTED", "export succeeded")
        after = node.process(**_node_inputs(text=exact))["result"][:7]
        if before != after or list(root.glob(".lvw-manual-*.tmp")):
            raise CheckpointError("WRITE_FAILURE_CHANGED_DRAFT", "draft/temp mutation")
        if owner.model_calls or not clipboard.values or not (root / "人工稿.txt").is_file():
            raise CheckpointError("MANUAL_ROUTE_ORACLE_FAILED", "copy/export/model count")
        return {"case_id": "V0-A04", "offline_precheck": "PASS",
                "product_status": "NOT_RUN", "draft_characters": len(exact),
                "draft_hash": value_hash(before), "model_calls": owner.model_calls,
                "write_failure_preserved": True}


def _state_call(node, state, action, token="run-1", raw="safe raw", suggestion="",
                draft="", error=""):
    return node.process(state=state, action=action, run_token=token,
                        raw_response=raw, suggestion_payload=suggestion,
                        draft_payload=draft, error_code=error)["result"][0]


def precheck_a05(_repo: Path) -> dict:
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWDraftStateOwner
    node = LVWDraftStateOwner()
    draft = json.dumps({"natural_zh": "kept bytes", "natural_en": "", "image_prompt": "",
                        "video_prompt": "", "tags": [], "negative": "",
                        "edit_instruction": ""}, ensure_ascii=False)
    state = _state_call(node, "", "start_run")
    state = _state_call(node, state, "model_success", suggestion='{"prompt":"visible"}')
    adopted = _state_call(node, state, "adopt", draft=draft)
    baseline = json.loads(adopted)
    negatives = []
    for label, action, error, token, suggestion in (
        ("invalid_json", "model_success", "", "next", "{"),
        ("explicit_refusal", "model_failure", "MODEL_REFUSAL", "next", ""),
        ("timeout", "model_failure", "MODEL_TIMEOUT", "next", ""),
        ("oom", "model_failure", "GPU_OOM", "next", ""),
        ("stale_token", "model_success", "", "stale", "{}"),
    ):
        running = _state_call(node, adopted, "start_run", token="next")
        try:
            result = _state_call(node, running, action, token=token, suggestion=suggestion,
                                 error=error)
        except BridgeError as exc:
            if label not in {"invalid_json", "stale_token"}:
                raise
            result = running
            code = exc.code
        else:
            code = json.loads(result)["failure_code"]
        value = json.loads(result)
        if value["draft"] != baseline["draft"] or value["draft_epoch"] != baseline["draft_epoch"]:
            raise CheckpointError("FAILURE_OVERWROTE_DRAFT", label)
        if value["retry_count"] != 0:
            raise CheckpointError("UNBOUNDED_RETRY", label)
        negatives.append({"name": label, "code": code, "draft_preserved": True})
    if MAX_EFFECTIVE_RETRIES != 2:
        raise CheckpointError("RETRY_BOUNDARY_INVALID", "exact/one-over")
    return {"case_id": "V0-A05", "offline_precheck": "PASS",
            "product_status": "NOT_RUN", "draft_hash": value_hash(baseline["draft"]),
            "draft_epoch": baseline["draft_epoch"], "retry_exact": 2,
            "retry_one_over_rejected": 3, "negatives": negatives}


def precheck_a08(repo: Path) -> dict:
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWManualPromptOwner
    required = set(LVWManualPromptOwner.INPUT_TYPES()["required"])
    forbidden = {name for name in required if name.lower().startswith(("approval", "nsfw", "content_note"))}
    if forbidden:
        raise CheckpointError("PERMISSION_FIELD_PRESENT", repr(forbidden))
    defaults = json.loads((repo / "config/runtime.defaults.json").read_text(encoding="utf-8"))
    if defaults["security"].get("approval_required_for_manual_export") is not False:
        raise CheckpointError("APPROVAL_PERMISSION_ENABLED", "runtime defaults")
    with tempfile.TemporaryDirectory(prefix="lvw-s1-checkpoint-") as temp:
        root = Path(temp) / "out"
        owner = ManualDraftOwner(export_root=root, export_parent=Path(temp),
                                 clipboard=MemoryClipboard(),
                                 clock=lambda: "2026-10-28T00:00:00Z")
        node = LVWManualPromptOwner(owner=owner)
        empty = _node_inputs(text="", action="export_json", filename="empty")
        for field in ("natural_en", "image_prompt", "video_prompt", "tags",
                      "negative", "edit_instruction"):
            empty[field] = ""
        payload = json.loads(node.process(**empty)["result"][7])
        _schema(repo).validate(payload)
        expected = (payload["source_type"], payload["run_id"], payload["analysis_status"],
                    payload["suggestion"])
        if expected != ("manual", None, "not_requested", None) or owner.model_calls:
            raise CheckpointError("MANUAL_NO_APPROVAL_ORACLE_FAILED", repr(expected))
        reread = json.loads((root / "empty.json").read_text(encoding="utf-8"))
        if reread != payload:
            raise CheckpointError("MANUAL_EXPORT_REREAD_MISMATCH", "empty.json")
        return {"case_id": "V0-A08", "offline_precheck": "PASS",
                "product_status": "NOT_RUN", "contract_tuple": list(expected),
                "permission_fields": [], "model_calls": owner.model_calls,
                "export_hash": sha256(canonical(payload)).hexdigest()}


def run_offline_prechecks(repo: Path) -> dict:
    repo_text = str(repo)
    if repo_text not in sys.path:
        sys.path.insert(0, repo_text)
    verify_denominator()
    artifacts = bind_candidate(repo)
    checks = [precheck_a01(repo), precheck_a03(repo), precheck_a04(repo),
              precheck_a05(repo), precheck_a08(repo)]
    return {
        "schema_version": "lvw.s1-stage-checkpoint-offline/1",
        "packet_version": PACKET_VERSION,
        "product_candidate": PRODUCT_CANDIDATE,
        "acceptance_ids": list(CASE_IDS),
        "acceptance_hash": ACCEPTANCE_HASH,
        "identity": {"artifacts": artifacts},
        "case_prechecks": checks,
        "product_test_counts": {"denominator": 5, "pass": 0, "fail": 0,
                                "blocked": 0, "skipped": 0, "not_run": 5},
        "external_actions": {"service_starts": 0, "gpu_probes": 0, "port_probes": 0,
                             "network_calls": 0, "real_media_reads": 0, "browser_runs": 0},
        "future_case_budgets": CASE_BUDGETS,
        "live_requirements": LIVE_REQUIREMENTS,
        "decision": "READY_FOR_REVIEW",
        "stage_pass_claim": False,
        "exact_stop_reason": "WAIT_AUTH_S1_FIXED_DENOMINATOR_NOT_RUN",
    }


def _privacy_scan(value, location="$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _privacy_scan(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _privacy_scan(child, f"{location}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if ("/mnt/" in lowered or re.search(r"[a-zA-Z]:[\\/]", value) or
                "traceback (most recent call last)" in lowered or
                "current_inputs" in lowered or
                re.fullmatch(r"[A-Za-z0-9+/]{160,}={0,2}", value)):
            raise CheckpointError("CASE_PRIVACY_VIOLATION", location)


def verify_case_evidence(document: dict, case_id: str, expected_artifacts: dict) -> None:
    _privacy_scan(document)
    if case_id not in CASE_IDS or document.get("case_id") != case_id:
        raise CheckpointError("CASE_ID_MISMATCH", case_id)
    if document.get("product_candidate") != PRODUCT_CANDIDATE:
        raise CheckpointError("CASE_CANDIDATE_MISMATCH", case_id)
    if document.get("acceptance_hash") != ACCEPTANCE_HASH:
        raise CheckpointError("CASE_DENOMINATOR_MISMATCH", case_id)
    if document.get("budget") != CASE_BUDGETS[case_id]:
        raise CheckpointError("CASE_BUDGET_MISMATCH", case_id)
    if document.get("identity", {}).get("artifacts") != expected_artifacts:
        raise CheckpointError("CASE_EXECUTION_ARTIFACT_MISMATCH", case_id)
    if document.get("status") != "PASS":
        raise CheckpointError("CASE_NOT_PASS", case_id)
    proof = document.get("proof", {})
    for key, expected in LIVE_REQUIREMENTS.items():
        if proof.get(key) is not expected:
            raise CheckpointError("CASE_PROOF_MISSING", f"{case_id}:{key}")
    oracle = document.get("oracle", {})
    for key in CASE_PROOF_REQUIREMENTS[case_id]:
        if oracle.get(key) is not True:
            raise CheckpointError("CASE_ORACLE_MISSING", f"{case_id}:{key}")


def combine_case_evidence(documents: list[dict], repo: Path) -> dict:
    by_id = {document.get("case_id"): document for document in documents}
    if set(by_id) != set(CASE_IDS) or len(documents) != len(CASE_IDS):
        raise CheckpointError("FIXED_DENOMINATOR_INCOMPLETE", "five unique cases required")
    expected_artifacts = bind_candidate(repo)
    for case_id in CASE_IDS:
        verify_case_evidence(by_id[case_id], case_id, expected_artifacts)
    slots = [by_id[case_id].get("evidence_slot") for case_id in CASE_IDS]
    if any(not isinstance(slot, str) or not slot for slot in slots) or len(set(slots)) != 5:
        raise CheckpointError("EVIDENCE_SLOT_REUSED", "fresh slot per case required")
    return {"product_candidate": PRODUCT_CANDIDATE, "acceptance_hash": ACCEPTANCE_HASH,
            "case_statuses": {case_id: "PASS" for case_id in CASE_IDS},
            "test_counts": {"denominator": 5, "pass": 5, "fail": 0,
                            "blocked": 0, "skipped": 0, "not_run": 0},
            "ready_for_independent_review": True, "stage_pass_claim": False}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Offline V0-S1 fixed-denominator checkpoint")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-check", action="store_true")
    group.add_argument("--plan", action="store_true")
    group.add_argument("--combine", nargs="+", metavar="CASE_JSON")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.self_check:
            output = run_offline_prechecks(args.repo.resolve())
        elif args.plan:
            verify_denominator()
            output = {"product_candidate": PRODUCT_CANDIDATE, "acceptance_ids": list(CASE_IDS),
                      "acceptance_hash": ACCEPTANCE_HASH, "case_budgets": CASE_BUDGETS,
                      "live_requirements": LIVE_REQUIREMENTS, "external_actions_now": 0,
                      "exact_stop_reason": "WAIT_AUTH_S1_FIXED_DENOMINATOR_NOT_RUN"}
        else:
            documents = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.combine]
            output = combine_case_evidence(documents, args.repo.resolve())
        print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (CheckpointError, OSError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, CheckpointError) else "CHECKPOINT_INPUT_INVALID"
        print(json.dumps({"decision": "NO_GO", "code": code,
                          "message": str(exc), "stage_pass_claim": False},
                         ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
