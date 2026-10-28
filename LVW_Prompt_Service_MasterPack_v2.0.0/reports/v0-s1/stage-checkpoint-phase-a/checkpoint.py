#!/usr/bin/env python3
"""Identity-bound producer and verifier for the V0-S1 fixed denominator.

Live execution is default-denied and exists only for a future committed request
plus one-shot authorization.  Offline self-checks call registered production
owners with synthetic fixtures and perform no service, GPU, port, network,
browser, or real-media action.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import re


PRODUCT_CANDIDATE = "1d48142b95466954ca4da264fa06762abf1522f2"
PACKET_VERSION = "1.0.0"
CASE_IDS = ("V0-A01", "V0-A03", "V0-A04", "V0-A05", "V0-A08")
ACCEPTANCE_HASH = "4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5"
MAX_DRAFT_CHARACTERS = 20_000
PLANNED_PUBLIC_SUBMISSIONS = 24
MAX_PUBLIC_SUBMISSIONS = 26
AUTHORIZED_RUN_ID = "v0-s1-stage-checkpoint-live-01"
AUTHORIZED_EVIDENCE_RELATIVE = "reports/v0-s1/stage-checkpoint-live-01"
AUTHORIZED_SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
AUTHORIZED_MODEL_DIGEST = "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"
LIFECYCLE_RELATIVE = "reports/v0-s1/wp-s1-03-phase-a/live_probe.py"
AUTHORIZED_COMFY_MAIN = "C:/ComfyUI-aki-v2/ComfyUI/main.py"
AUTHORIZED_COMFY_PYTHON = "C:/ComfyUI-aki-v2/python/python.exe"
AUTHORIZED_OLLAMA_EXE_ALIAS = "OLLAMA_EXE"
AUTHORIZED_OLLAMA_EXE_BASENAME = "ollama.exe"
AUTHORIZED_OLLAMA_EXE_SHA256 = "d15adaa9cc617da2c44142f36a36de19c76887ec342e4338f37e67fd730a1ced"
AUTHORIZED_POWERSHELL = "powershell.exe"
AUTHORIZED_TEMP_PARENT = "C:/Temp"
AUTHORIZED_COMFY_URL = "http://127.0.0.1:8191"
AUTHORIZED_OLLAMA_URL = "http://127.0.0.1:11434"
AUTH_STAGE_ID = "V0-S1"
AUTH_WORKPACK_ID = "WP-S1-04-CHECKPOINT-LIVE"
AUTH_EXPIRY = ("one terminal V0-S1 fixed-denominator checkpoint receipt is generated, "
               "the single effective image attempt is consumed, or any mandatory stop occurs")

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

ONE_SHOT_BUDGET = {"image_attempts": 1, "model_calls": 1, "comfy_starts": 1,
                   "ollama_starts": 1, "planned_public_submissions": PLANNED_PUBLIC_SUBMISSIONS,
                   "max_public_submissions": MAX_PUBLIC_SUBMISSIONS, "browser_runs": 0,
                   "downloads": 0, "cloud_calls": 0, "external_cost": 0}

LIVE_REQUIREMENTS = {
    "loopback_only": True,
    "ollama_no_cloud": True,
    "fresh_non_reusable_evidence_slot": True,
    "candidate_bytes_exact": True,
    "target_pre_post_equal": True,
    "owned_resources_terminal_absent": True,
    "privacy_minimized": True,
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
    return {"case_id": "V0-A05", "offline_precheck": "PASS",
            "product_status": "NOT_RUN", "draft_hash": value_hash(baseline["draft"]),
            "draft_epoch": baseline["draft_epoch"], "automatic_retry_count": 0,
            "negatives": negatives}


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
        "future_one_shot_budget": ONE_SHOT_BUDGET,
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
        if ("/mnt/" in lowered or re.search(r"(?<![A-Za-z0-9_])[a-zA-Z]:[\\/]", value) or
                "traceback (most recent call last)" in lowered or
                "current_inputs" in lowered or
                re.fullmatch(r"[A-Za-z0-9+/]{160,}={0,2}", value)):
            raise CheckpointError("CASE_PRIVACY_VIOLATION", location)


def service_log_facts(ollama_text: str, comfy_text: str) -> dict:
    """Reduce volatile service logs to non-reversible counters in memory."""
    combined=f"{ollama_text}\n{comfy_text}"
    lowered=combined.lower()
    traceback_count=lowered.count("traceback (most recent call last)")
    current_inputs_count=lowered.count("current_inputs")
    secret_assignment_count=len(re.findall(
        r"(?i)(?:authorization|bearer|token|password|api[_-]?key)\s*[:=]\s*[^\s,;]+",combined))
    long_base64_count=len(re.findall(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{160,}={0,2}(?![A-Za-z0-9+/])",combined))
    private_windows_path_count=len(re.findall(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]",combined))
    private_wsl_path_count=len(re.findall(r"(?<![A-Za-z0-9_])/mnt/[A-Za-z]/",combined,re.I))
    rejected=traceback_count+current_inputs_count+secret_assignment_count+long_base64_count
    ollama_lines=ollama_text.splitlines()
    return {
        "ollama_http_200": {
            "chat":sum(' | 200 |' in line and '"/api/chat"' in line for line in ollama_lines),
            "generate":sum(' | 200 |' in line and '"/api/generate"' in line for line in ollama_lines),
            "ps":sum(' | 200 |' in line and '"/api/ps"' in line for line in ollama_lines),
        },
        "comfy_got_prompt_count":sum("got prompt" in line.lower() for line in comfy_text.splitlines()),
        "ollama_no_cloud_marker_count":ollama_text.count("OLLAMA_NO_CLOUD=true"),
        "loopback_marker_count":combined.count("127.0.0.1")+combined.count("::1"),
        "traceback_count":traceback_count,
        "current_inputs_count":current_inputs_count,
        "secret_assignment_count":secret_assignment_count,
        "long_base64_count":long_base64_count,
        "private_windows_path_count":private_windows_path_count,
        "private_wsl_path_count":private_wsl_path_count,
        "rejected_diagnostic_count":rejected,
    }


def _load_proven_lifecycle(repo: Path):
    path = repo / LIFECYCLE_RELATIVE
    spec = importlib.util.spec_from_file_location("lvw_s1_proven_live_lifecycle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized_windows_path(value: str) -> str:
    path = str(value).replace("\\", "/")
    match = re.fullmatch(r"/mnt/([a-zA-Z])/(.+)", path)
    if match:
        path = f"{match.group(1).upper()}:/{match.group(2)}"
    return re.sub(r"/+", "/", path).rstrip("/")


def target_bindings() -> dict:
    return {
        "comfy_main": AUTHORIZED_COMFY_MAIN,
        "comfy_python": AUTHORIZED_COMFY_PYTHON,
        "ollama_exe_alias": AUTHORIZED_OLLAMA_EXE_ALIAS,
        "ollama_exe_basename": AUTHORIZED_OLLAMA_EXE_BASENAME,
        "ollama_exe_sha256": AUTHORIZED_OLLAMA_EXE_SHA256,
        "powershell": AUTHORIZED_POWERSHELL,
        "temp_parent": AUTHORIZED_TEMP_PARENT,
        "comfy_url": AUTHORIZED_COMFY_URL,
        "ollama_url": AUTHORIZED_OLLAMA_URL,
    }


def _git_path(repo: Path, relative: str) -> str:
    process = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=repo,
                             capture_output=True, text=True, encoding="utf-8", errors="strict")
    if process.returncode:
        raise CheckpointError("GIT_PREFIX_UNAVAILABLE", relative)
    return process.stdout.strip() + relative


def _commit_blob(repo: Path, commit: str, relative: str) -> bytes:
    process = subprocess.run(["git", "show", f"{commit}:{_git_path(repo, relative)}"], cwd=repo,
                             capture_output=True)
    if process.returncode:
        raise CheckpointError("BOUND_BLOB_MISSING", relative)
    return process.stdout


def file_sha256(path: Path) -> str:
    digest=sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_ollama_executable(value: str) -> dict:
    supplied=Path(value)
    if supplied.is_symlink():
        raise CheckpointError("AUTHORIZED_OLLAMA_EXECUTABLE_INVALID","symlink")
    try:
        resolved=supplied.resolve(strict=True)
    except OSError as exc:
        raise CheckpointError("AUTHORIZED_OLLAMA_EXECUTABLE_INVALID","missing") from exc
    if (not resolved.is_file() or resolved.is_symlink()
            or not resolved.as_posix().casefold().startswith("/mnt/c/")
            or resolved.name.casefold()!=AUTHORIZED_OLLAMA_EXE_BASENAME):
        raise CheckpointError("AUTHORIZED_OLLAMA_EXECUTABLE_INVALID","type/mount/basename")
    digest=file_sha256(resolved)
    if digest!=AUTHORIZED_OLLAMA_EXE_SHA256:
        raise CheckpointError("AUTHORIZED_OLLAMA_EXECUTABLE_HASH_MISMATCH",AUTHORIZED_OLLAMA_EXE_ALIAS)
    return {"alias":AUTHORIZED_OLLAMA_EXE_ALIAS,"basename":AUTHORIZED_OLLAMA_EXE_BASENAME,
            "sha256":digest}


def validate_target_args(args) -> dict:
    actual = {
        "comfy_main": normalized_windows_path(args.comfy_main),
        "comfy_python": normalized_windows_path(args.comfy_python),
        "powershell": args.powershell,
        "temp_parent": normalized_windows_path(args.temp_parent),
        "comfy_url": args.comfy_url,
        "ollama_url": args.ollama_url,
    }
    expected = {key:value for key,value in target_bindings().items() if not key.startswith("ollama_exe_")}
    for key, value in expected.items():
        if not isinstance(actual.get(key), str) or actual[key].casefold() != value.casefold():
            raise CheckpointError("AUTHORIZED_TARGET_ARGUMENT_MISMATCH", key)
    return validate_ollama_executable(args.ollama_exe)


def validate_authority_documents(request: dict, authorization: dict, *, expected: dict,
                                 request_hash: str, authorization_id: str) -> None:
    for name, document in (("request", request), ("authorization", authorization)):
        for key, value in expected.items():
            if document.get(key) != value:
                raise CheckpointError("AUTHORITY_BINDING_MISMATCH", f"{name}:{key}")
    request_id = request.get("request_id")
    if (request.get("schema_version") != "lvw.authorization-request/1"
            or request.get("status") != "PENDING_PROJECT_OWNER_APPROVAL"
            or request.get("is_authorization") is not False
            or request.get("does_not_authorize_execution") is not True
            or request.get("project_id") != "lvw-prompt-service"
            or request.get("stage_id") != AUTH_STAGE_ID
            or request.get("workpack_id") != AUTH_WORKPACK_ID
            or request.get("does_not_authorize_stage_pass") is not True
            or not isinstance(request_id, str) or not request_id):
        raise CheckpointError("AUTHORIZATION_REQUEST_SEMANTICS_INVALID", "request")
    if (authorization.get("schema_version") != "lvw.authorization/1"
            or authorization.get("status") != "GRANTED_ONCE"
            or authorization.get("project_id") != "lvw-prompt-service"
            or authorization.get("authorization_id") != authorization_id
            or authorization.get("request_id") != request_id
            or authorization.get("request_sha256") != request_hash
            or authorization.get("stage_id") != AUTH_STAGE_ID
            or authorization.get("workpack_id") != AUTH_WORKPACK_ID
            or authorization.get("expires_when") != AUTH_EXPIRY
            or authorization.get("does_not_authorize_stage_pass") is not True):
        raise CheckpointError("AUTHORIZATION_NOT_GRANTED_ONCE_OR_BOUND", "authorization")


def validate_authority(args, repo: Path) -> dict:
    """Bind a future formal request+authorization before any external action."""
    validate_target_args(args)
    resolved_records = []
    for path in (Path(args.request_record), Path(args.authorization_record)):
        try:
            relative = path.resolve(strict=True).relative_to(repo)
        except (OSError, ValueError) as exc:
            raise CheckpointError("AUTHORITY_RECORD_OUTSIDE_REPO", path.name) from exc
        if not relative.as_posix().startswith("reports/v0-s1/"):
            raise CheckpointError("AUTHORITY_RECORD_OUTSIDE_ALLOWED_PATH", path.name)
        resolved_records.append(path.resolve(strict=True))
    request_path, authorization_path = resolved_records
    request_bytes = request_path.read_bytes()
    authorization_bytes = authorization_path.read_bytes()
    request_hash, authorization_hash = sha256(request_bytes).hexdigest(), sha256(authorization_bytes).hexdigest()
    if request_hash != args.request_sha256 or authorization_hash != args.authorization_sha256:
        raise CheckpointError("AUTHORITY_RECORD_HASH_MISMATCH", "request/authorization")
    request = json.loads(request_bytes)
    authorization = json.loads(authorization_bytes)
    expected = {
        "product_candidate": PRODUCT_CANDIDATE,
        "harness_candidate": args.harness_candidate,
        "harness_sha256": args.harness_sha256,
        "lifecycle_relative": LIFECYCLE_RELATIVE,
        "lifecycle_sha256": args.lifecycle_sha256,
        "run_id": AUTHORIZED_RUN_ID,
        "evidence_relative": AUTHORIZED_EVIDENCE_RELATIVE,
        "sample_sha256": AUTHORIZED_SAMPLE_SHA256,
        "model_digest": AUTHORIZED_MODEL_DIGEST,
        "budget": ONE_SHOT_BUDGET,
        "acceptance_hash": ACCEPTANCE_HASH,
        "target_bindings": target_bindings(),
    }
    validate_authority_documents(request, authorization, expected=expected,
                                 request_hash=request_hash, authorization_id=args.authorization_id)
    if not re.fullmatch(r"[a-f0-9]{40}", args.authorization_commit):
        raise CheckpointError("AUTHORIZATION_COMMIT_INVALID", "authorization_commit")
    for path, local in ((request_path, request_bytes), (authorization_path, authorization_bytes)):
        relative = path.resolve().relative_to(repo).as_posix()
        if _commit_blob(repo, args.authorization_commit, relative) != local:
            raise CheckpointError("AUTHORITY_COMMIT_BLOB_MISMATCH", relative)
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", args.harness_candidate,
                               args.authorization_commit], cwd=repo)
    if ancestor.returncode:
        raise CheckpointError("AUTHORIZATION_NOT_DESCENDANT_OF_HARNESS", "ancestry")
    return {"authorization_id": args.authorization_id, "request_sha256": request_hash,
            "authorization_sha256": authorization_hash, "authorization_commit": args.authorization_commit,
            "request_relative": Path(args.request_record).resolve().relative_to(repo).as_posix(),
            "authorization_relative": Path(args.authorization_record).resolve().relative_to(repo).as_posix()}


def validate_live_identity(args, repo: Path) -> dict:
    artifacts = bind_candidate(repo)
    if args.product_candidate != PRODUCT_CANDIDATE:
        raise CheckpointError("PRODUCT_CANDIDATE_MISMATCH", args.product_candidate)
    harness_relative = Path(__file__).resolve().relative_to(repo).as_posix()
    blob = _commit_blob(repo, args.harness_candidate, harness_relative)
    local = Path(__file__).read_bytes()
    if sha256(blob).hexdigest() != args.harness_sha256 or sha256(local).hexdigest() != args.harness_sha256:
        raise CheckpointError("HARNESS_IDENTITY_MISMATCH", harness_relative)
    lifecycle_path = repo / LIFECYCLE_RELATIVE
    lifecycle_local = lifecycle_path.read_bytes()
    lifecycle_blob = _commit_blob(repo, args.harness_candidate, LIFECYCLE_RELATIVE)
    if (sha256(lifecycle_local).hexdigest() != args.lifecycle_sha256
            or sha256(lifecycle_blob).hexdigest() != args.lifecycle_sha256):
        raise CheckpointError("LIFECYCLE_IDENTITY_MISMATCH", LIFECYCLE_RELATIVE)
    allowed = {harness_relative, "LVW_V0_RuntimePatch/tests/test_s1_stage_checkpoint.py",
               "reports/v0-s1/implementation-receipt-stage-checkpoint-offline.json"}
    changed = subprocess.run(["git", "diff", "--name-only", f"14cdcffb6a34a4330012591652e7f85d20da2b7c..{args.harness_candidate}"],
                             cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="strict")
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=repo, capture_output=True,
                            text=True, encoding="utf-8", errors="strict").stdout.strip()
    changed_files = {path[len(prefix):] if prefix and path.startswith(prefix) else path
                     for path in changed.stdout.splitlines() if path}
    if changed.returncode or not changed_files.issubset(allowed):
        raise CheckpointError("HARNESS_CANDIDATE_SCOPE_MISMATCH", "changed files")
    return {"product_candidate": PRODUCT_CANDIDATE, "product_artifact_sha256": artifacts,
            "harness_candidate": args.harness_candidate, "harness_sha256": args.harness_sha256,
            "lifecycle_relative": LIFECYCLE_RELATIVE, "lifecycle_sha256": args.lifecycle_sha256}


def validate_live_paths(args, repo: Path, *, reserve: bool) -> dict:
    evidence = Path(args.evidence_root)
    expected = repo / AUTHORIZED_EVIDENCE_RELATIVE
    if evidence.resolve(strict=False) != expected or args.run_id != AUTHORIZED_RUN_ID:
        raise CheckpointError("RUN_OR_EVIDENCE_BINDING_MISMATCH", "run/evidence")
    ollama_identity=validate_target_args(args)
    temp_parent = Path(args.temp_parent)
    resolved = temp_parent.resolve(strict=True)
    if (not temp_parent.is_dir() or temp_parent.is_symlink() or repo == resolved
            or repo in resolved.parents or not resolved.as_posix().casefold().startswith("/mnt/c/")):
        raise CheckpointError("RUN_TEMP_PARENT_FORBIDDEN", "temp parent")
    if reserve:
        try:
            evidence.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise CheckpointError("EVIDENCE_ROOT_ALREADY_EXISTS", evidence.name) from exc
    elif not evidence.is_dir():
        raise CheckpointError("EVIDENCE_ROOT_NOT_RESERVED", evidence.name)
    return {"run_id": AUTHORIZED_RUN_ID, "evidence_relative": AUTHORIZED_EVIDENCE_RELATIVE,
            "target_bindings_sha256": value_hash(target_bindings()),
            "ollama_executable_identity": ollama_identity,
            "target_aliases": ["COMFY_ROOT/main.py", "COMFY_PYTHON", "OLLAMA_EXE", "RUN_TEMP_PARENT"]}


def manual_public_graph(values: dict, action: str, filename: str) -> dict:
    inputs = {key: values.get(key, "") for key in
              ("natural_zh", "natural_en", "image_prompt", "video_prompt", "tags", "negative", "edit_instruction")}
    inputs.update(action=action, filename=filename)
    return {"1": {"class_type": "LVWManualPromptOwner", "inputs": inputs}}


def state_public_graph(state: str, action: str, token: str, *, raw="", suggestion="", draft="", error="") -> dict:
    return {"1": {"class_type": "LVWDraftStateOwner", "inputs": {
        "state": state, "action": action, "run_token": token, "raw_response": raw,
        "suggestion_payload": suggestion, "draft_payload": draft, "error_code": error}}}


def _error_facts(history: dict, prompt_id: str) -> list[dict]:
    record = history.get(prompt_id, {})
    facts = []
    for item in record.get("status", {}).get("messages", []):
        if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)):
            continue
        fact = {"event": item[0]}
        payload = item[1]
        for key in ("node_id", "node_type"):
            if isinstance(payload.get(key), str):
                fact[key] = payload[key]
        try:
            error = json.loads(payload.get("exception_message", ""))
        except (TypeError, json.JSONDecodeError):
            error = {}
        if isinstance(error, dict):
            fact["code"] = error.get("code")
            fact["subcode"] = (error.get("details") or {}).get("subcode")
        facts.append(fact)
    return facts


def _success_trace(lifecycle, driver, graph: dict, node="1") -> tuple[dict, list[str]]:
    prompt_id = driver.submit(graph)
    history = driver.history(prompt_id)
    text = lifecycle.workflow_oracle(history, prompt_id, node)
    trace = {"prompt_id": prompt_id, "submission_sequence": driver.submissions,
             "graph_sha256": value_hash(graph),
             "class_types": sorted(value["class_type"] for value in graph.values()),
             "history_ui_text": text}
    return trace, text


def _failure_trace(driver, graph: dict, expected_code: str) -> dict:
    prompt_id = driver.submit(graph)
    history = driver.history(prompt_id)
    facts = _error_facts(history, prompt_id)
    if expected_code not in {fact.get("code") for fact in facts}:
        raise CheckpointError("PUBLIC_FAILURE_CODE_MISSING", expected_code)
    return {"prompt_id": prompt_id, "submission_sequence": driver.submissions,
            "graph_sha256": value_hash(graph), "error_facts": facts}


def _manual_payload(text: list[str]) -> dict:
    if len(text) != 2:
        raise CheckpointError("MANUAL_HISTORY_OUTPUT_INVALID", "UI text length")
    try:
        return json.loads(text[1])
    except json.JSONDecodeError as exc:
        raise CheckpointError("MANUAL_JSON_INVALID", "history payload") from exc


class CheckpointDriver:
    """Adapter over the proven live-06 SystemDriver with the checkpoint budget."""
    def __new__(cls, lifecycle, args, evidence):
        class Driver(lifecycle.SystemDriver):
            def submit(self, graph):
                if self.submissions >= MAX_PUBLIC_SUBMISSIONS:
                    raise lifecycle.StopProbe("PUBLIC_API_SUBMISSION_BUDGET_EXCEEDED")
                self.submissions += 1
                status, value = self._json_request(
                    lifecycle.COMFY_URL + "/prompt",
                    payload={"prompt": graph, "client_id": self.args.run_id})
                if status != 200 or not isinstance(value.get("prompt_id"), str):
                    raise lifecycle.StopProbe("PUBLIC_PROMPT_SUBMISSION_FAILED")
                return value["prompt_id"]
        return Driver(args, evidence)


def execute_live(args, *, driver_factory=CheckpointDriver) -> tuple[int, dict]:
    repo = Path(args.repo).resolve(strict=True)
    lifecycle = None
    result = {"schema_version": "lvw.s1-stage-checkpoint-live/1", "decision": "BLOCKED",
              "exact_stop_reason": None, "stage_pass_claim": False, "run_id": args.run_id,
              "acceptance_hash": ACCEPTANCE_HASH, "product_acceptance": {key: "NOT_RUN" for key in CASE_IDS},
              "budget": ONE_SHOT_BUDGET, "observed": {"image_attempts": 0, "model_calls": 0,
              "comfy_starts": 0, "ollama_starts": 0, "public_submissions": 0},
              "identity": {}, "authority": {}, "case_facts": {}, "cleanup": {"proven": False}}
    base = driver = before = None
    try:
        result["authority"] = validate_authority(args, repo)
        result["identity"] = validate_live_identity(args, repo)
        result["bindings"] = validate_live_paths(args, repo, reserve=False)
        lifecycle = _load_proven_lifecycle(repo)
        if (lifecycle.COMFY_URL != AUTHORIZED_COMFY_URL or lifecycle.OLLAMA_URL != AUTHORIZED_OLLAMA_URL
                or lifecycle.AUTHORIZED_COMFY_MAIN != AUTHORIZED_COMFY_MAIN
                or lifecycle.AUTHORIZED_COMFY_PYTHON != AUTHORIZED_COMFY_PYTHON):
            raise CheckpointError("LIFECYCLE_TARGET_BINDING_MISMATCH", LIFECYCLE_RELATIVE)
        if (args.sample_sha256 != AUTHORIZED_SAMPLE_SHA256
                or sha256(Path(args.sample).read_bytes()).hexdigest() != AUTHORIZED_SAMPLE_SHA256):
            raise CheckpointError("AUTHORIZED_SAMPLE_HASH_MISMATCH", "sample")
        base = Path(tempfile.mkdtemp(prefix="lvw-s1-checkpoint-", dir=args.temp_parent))
        for name in ("input", "output", "temp", "custom_nodes"):
            (base / name).mkdir()
        shutil.copytree(repo / "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge",
                        base / "custom_nodes/lvw_v0_bridge")
        expected_artifacts=result["identity"]["product_artifact_sha256"]
        for relative, expected_hash in expected_artifacts.items():
            if not relative.endswith(".py"):
                continue
            copied=base/"custom_nodes/lvw_v0_bridge"/Path(relative).name
            if not copied.is_file() or sha256(copied.read_bytes()).hexdigest()!=expected_hash:
                raise CheckpointError("RUN_COPY_ARTIFACT_IDENTITY_MISMATCH",relative)
        workflow_path=repo/"LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json"
        workflow_bytes=workflow_path.read_bytes()
        if sha256(workflow_bytes).hexdigest()!=expected_artifacts["LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json"]:
            raise CheckpointError("RUN_WORKFLOW_ARTIFACT_IDENTITY_MISMATCH","image API")
        alias = "authorized-image.jpg"
        shutil.copyfile(args.sample, base / "input" / alias)
        driver = driver_factory(lifecycle, args, result)
        before = driver.target_hashes()
        result["preflight"] = driver.preflight()
        driver.start_ollama(base / "ollama.log")
        result["observed"]["ollama_starts"] = 1
        result["network_gate"] = driver.no_cloud_remote_gate()
        driver.start_comfy(base, base / "comfy.log")
        result["observed"]["comfy_starts"] = 1
        result["owned_listener_lineage"] = driver.ownership_summary()
        missing = sorted(lifecycle.REQUIRED_NODES - set(driver.registry()))
        if missing:
            raise CheckpointError("REQUIRED_PUBLIC_NODE_MISSING", ",".join(missing))
        result["model_identity"] = driver.verify_model()
        if result["model_identity"].get("digest") != AUTHORIZED_MODEL_DIGEST:
            raise CheckpointError("AUTHORIZED_MODEL_DIGEST_MISMATCH", "local model")

        # A01: one public graph also routes controlled metadata to a registered output owner.
        graph = json.loads(workflow_bytes)
        graph["1"]["inputs"]["image_reference"] = alias
        graph["3"] = manual_public_graph({"natural_zh": ["1", 1]}, "preview_json", "metadata")["1"]
        result["observed"].update(image_attempts=1, model_calls=1)
        a01_id = driver.submit(graph)
        a01_history = driver.history(a01_id)
        image_text = lifecycle.workflow_oracle(a01_history, a01_id, "2")
        metadata_text = lifecycle.workflow_oracle(a01_history, a01_id, "3")
        image_oracle = lifecycle.validate_image_result(image_text)
        metadata_payload = _manual_payload(metadata_text)
        metadata = json.loads(metadata_payload["draft"]["natural_zh"])
        if metadata.get("source_sha256") != AUTHORIZED_SAMPLE_SHA256 or max(metadata.get("output_dimensions", [9999])) > 1024:
            raise CheckpointError("CONTROLLED_PREPROCESS_METADATA_INVALID", "A01")
        result["case_facts"]["V0-A01"] = {"subslot": "a01", "prompt_id": a01_id,
            "submission_sequence": 1,
            "graph_sha256": value_hash(graph), "history_ui_text": image_text,
            "metadata_history_ui_text": metadata_text, "metadata": metadata, "image_oracle": image_oracle}
        result["model_call_ledger"] = [{"sequence": 1, "case_id": "V0-A01", "prompt_id": a01_id,
                                         "raw_sha256": image_oracle["raw_sha256"],
                                         "suggestion_sha256": image_oracle["suggestion_sha256"]}]
        result["image_runtime_guard"] = driver.runtime_guard()
        result["model_cleanup"] = driver.unload()
        suggestion = json.loads(image_text[1])

        # A03: three public CPU views; JSON/TXT are derived from the single A01 result.
        values = {"natural_zh": suggestion.get("text_zh", ""), "natural_en": suggestion.get("text_en", ""),
                  "image_prompt": suggestion.get("text_en", ""), "video_prompt": suggestion.get("text_en", ""),
                  "tags": ",".join(suggestion.get("tags", [])), "negative": suggestion.get("negative", ""),
                  "edit_instruction": ""}
        a03_traces, a03_texts = [], []
        for action in ("preview_json", "export_json", "export_txt"):
            trace, text = _success_trace(lifecycle, driver, manual_public_graph(values, action, "a03"))
            a03_traces.append(trace); a03_texts.append(text)
        a03_json = _manual_payload(a03_texts[1])
        _schema(repo).validate(a03_json)
        a03_txt = a03_texts[2][1]
        if not a03_txt.startswith("## Natural Chinese"):
            raise CheckpointError("A03_TXT_INVALID", "TXT")
        result["case_facts"]["V0-A03"] = {"subslot": "a03", "traces": a03_traces,
            "four_output_sha256": {key: sha256(str(a03_json["draft"][key]).encode()).hexdigest()
            for key in ("natural_zh", "natural_en", "image_prompt", "video_prompt")},
            "json_sha256": sha256(a03_texts[1][1].encode()).hexdigest(),
            "txt_sha256": sha256(a03_txt.encode()).hexdigest(),
            "json_reread_sha256": sha256((base / "output/lvw_manual/a03.json").read_bytes()).hexdigest(),
            "txt_reread_sha256": sha256((base / "output/lvw_manual/a03.txt").read_bytes()).hexdigest(),
            "model_calls_before": 1, "model_calls_after": 1, "source_raw_sha256": image_oracle["raw_sha256"]}

        driver.stop_ollama()
        ollama_stop_fact = dict(driver.listener_terminal_states.get("11434", {}))

        # A04: exact 20k, copy/export, and deterministic os.replace failure via owned target directory.
        exact = "稿" * MAX_DRAFT_CHARACTERS
        manual_values = _node_inputs(text=exact)
        a04_traces = []
        for action in ("preview_json", "copy_json", "copy_txt", "export_json", "export_txt"):
            trace, _ = _success_trace(lifecycle, driver, manual_public_graph(manual_values, action, "a04"))
            a04_traces.append(trace)
        failure_target = base / "output/lvw_manual/a04-failure.json"
        failure_target.mkdir(parents=True)
        failure_trace = _failure_trace(driver, manual_public_graph(manual_values, "export_json", "a04-failure"), "DISK_FULL")
        export_root = base / "output/lvw_manual"
        exports = {name: {"sha256": sha256((export_root / name).read_bytes()).hexdigest(),
                          "reread_bytes": (export_root / name).stat().st_size}
                   for name in ("a04.json", "a04.txt")}
        result["case_facts"]["V0-A04"] = {"subslot": "a04", "ollama_stop_fact": ollama_stop_fact,
            "draft_characters": len(exact), "draft_sha256": sha256(exact.encode()).hexdigest(),
            "success_traces": a04_traces, "failure_trace": failure_trace, "exports": exports,
            "failure_target_still_directory": failure_target.is_dir(),
            "owned_temp_file_count": len(list(export_root.glob(".lvw-manual-*.tmp")))}

        # A05: all callbacks go through public /prompt/history; no model retry is attempted.
        token = args.run_id + "-state"
        draft_payload = canonical({"natural_zh": "kept bytes", "natural_en": "", "image_prompt": "",
            "video_prompt": "", "tags": [], "negative": "", "edit_instruction": ""}).decode()
        setup = []
        trace, text = _success_trace(lifecycle, driver, state_public_graph("", "start_run", token)); setup.append(trace); started=text[0]
        trace, text = _success_trace(lifecycle, driver, state_public_graph(started, "model_success", token,
                                      raw=image_text[0], suggestion=image_text[1])); setup.append(trace); succeeded=text[0]
        trace, text = _success_trace(lifecycle, driver, state_public_graph(succeeded, "adopt", token,
                                      draft=draft_payload)); setup.append(trace); adopted=text[0]
        baseline = json.loads(adopted); baseline_hash = value_hash(baseline["draft"]); negatives=[]
        for name, action, error, callback_token, suggestion_payload, expected_error in (
            ("invalid_json", "model_success", "", token+"-next", "{", "PARSE_PARTIAL"),
            ("explicit_refusal", "model_failure", "MODEL_REFUSAL", token+"-next", "", None),
            ("timeout", "model_failure", "MODEL_TIMEOUT", token+"-next", "", None),
            ("oom", "model_failure", "GPU_OOM", token+"-next", "", None),
            ("stale_token", "model_success", "", "stale", "{}", "ATTEMPT_STALE")):
            next_token = token + "-next"
            start_trace, start_text = _success_trace(lifecycle, driver, state_public_graph(adopted, "start_run", next_token))
            running = start_text[0]
            graph = state_public_graph(running, action, callback_token, raw="safe raw",
                                       suggestion=suggestion_payload, error=error)
            if expected_error:
                callback_trace = _failure_trace(driver, graph, expected_error)
                final = json.loads(running)
            else:
                callback_trace, callback_text = _success_trace(lifecycle, driver, graph)
                final = json.loads(callback_text[0])
            if value_hash(final["draft"]) != baseline_hash or final["draft_epoch"] != baseline["draft_epoch"] or final["retry_count"] != 0:
                raise CheckpointError("A05_DRAFT_OR_RETRY_ORACLE_FAILED", name)
            negatives.append({"name": name, "start_trace": start_trace, "callback_trace": callback_trace,
                              "draft_sha256": baseline_hash, "draft_epoch": final["draft_epoch"],
                              "retry_count": final["retry_count"], "analysis_status": final["analysis_status"]})
        result["case_facts"]["V0-A05"] = {"subslot": "a05", "setup_traces": setup,
            "baseline_draft_sha256": baseline_hash, "baseline_epoch": baseline["draft_epoch"],
            "negatives": negatives, "automatic_retry_count": 0}

        # A08: one public empty export; production input keys prove no approval/content-note gate.
        empty = {key: "" for key in ("natural_zh", "natural_en", "image_prompt", "video_prompt",
                                      "tags", "negative", "edit_instruction")}
        a08_trace, a08_text = _success_trace(lifecycle, driver, manual_public_graph(empty, "export_json", "a08-empty"))
        a08_payload = _manual_payload(a08_text); _schema(repo).validate(a08_payload)
        expected_tuple = ["manual", None, "not_requested", None]
        actual_tuple = [a08_payload["source_type"], a08_payload["run_id"],
                        a08_payload["analysis_status"], a08_payload["suggestion"]]
        if actual_tuple != expected_tuple:
            raise CheckpointError("A08_CONTRACT_TUPLE_INVALID", repr(actual_tuple))
        result["case_facts"]["V0-A08"] = {"subslot": "a08", "trace": a08_trace,
            "contract_tuple": actual_tuple, "manual_input_keys": sorted(empty),
            "export_sha256": sha256((export_root / "a08-empty.json").read_bytes()).hexdigest(),
            "model_calls_before": 1, "model_calls_after": 1}

        result["observed"]["public_submissions"] = driver.submissions
        if driver.submissions != PLANNED_PUBLIC_SUBMISSIONS:
            raise CheckpointError("PUBLIC_SUBMISSION_PLAN_MISMATCH", str(driver.submissions))
        result["runtime_guard"] = driver.runtime_guard()
        result["product_acceptance"] = {key: "PASS_CANDIDATE_FOR_REVIEW" for key in CASE_IDS}
        result["decision"] = "READY_FOR_REVIEW"
        result["exact_stop_reason"] = "S1_FIXED_DENOMINATOR_CHECKPOINT_COMPLETE"
    except CheckpointError as exc:
        result["decision"] = "NO_GO"
        result["exact_stop_reason"] = exc.code
        result["failure"] = str(exc)
    except Exception as exc:
        if lifecycle is not None and isinstance(exc, lifecycle.StopProbe):
            result["decision"] = "NO_GO"; result["exact_stop_reason"] = exc.reason
            result["failure"] = str(exc)
        else:
            result["decision"] = "BLOCKED"; result["exact_stop_reason"] = "UNEXPECTED_HARNESS_EXCEPTION"
            result["failure"] = type(exc).__name__
    finally:
        if driver is not None:
            result["observed"]["public_submissions"] = driver.submissions
            try:
                cleanup = driver.cleanup(); after = driver.target_hashes() if before is not None else None
                result["target_integrity"] = {"pre": before, "post": after, "equal": before == after and before is not None}
                cleanup["target_integrity"] = "PASS" if result["target_integrity"]["equal"] else "FAIL"
                cleanup["proven"] = cleanup["proven"] and result["target_integrity"]["equal"]
                result["cleanup"] = cleanup
            except Exception as exc:
                result["cleanup"] = {"proven": False, "secondary_cleanup_failure": type(exc).__name__}
        if base is not None:
            ollama_log_path=base/"ollama.log"; comfy_log_path=base/"comfy.log"
            ollama_text=ollama_log_path.read_text(encoding="utf-8",errors="replace") if ollama_log_path.exists() else ""
            comfy_text=comfy_log_path.read_text(encoding="utf-8",errors="replace") if comfy_log_path.exists() else ""
            facts=service_log_facts(ollama_text,comfy_text)
            result["service_log_facts"]=facts
            result["model_http_ledger"]={
                "chat_200":facts["ollama_http_200"]["chat"],
                "generate_200":facts["ollama_http_200"]["generate"],
                "ps_200":facts["ollama_http_200"]["ps"],
            }
            if facts["rejected_diagnostic_count"]:
                if result["decision"]=="READY_FOR_REVIEW":
                    result["decision"]="NO_GO"
                    result["exact_stop_reason"]="SERVICE_LOG_FORBIDDEN_DIAGNOSTIC"
                else:
                    result["secondary_privacy_stop"]="SERVICE_LOG_FORBIDDEN_DIAGNOSTIC"
            del ollama_text,comfy_text
            try:
                shutil.rmtree(base); result["cleanup"]["run_owned_temp_removed"] = not base.exists()
            except Exception as exc:
                result["cleanup"]["run_owned_temp_removed"] = False
                result["cleanup"]["secondary_temp_cleanup_failure"] = type(exc).__name__
            result["cleanup"]["proven"] = result["cleanup"].get("proven", False) and not base.exists()
        if driver is not None and base is not None:
            try:
                snapshot = driver.post_cleanup_snapshot(base); result["post_cleanup_snapshot"] = snapshot
                clean = snapshot == {"target_listener_count": 0, "target_process_match_count": 0,
                                     "run_temp_absent": True}
                result["cleanup"]["proven"] = result["cleanup"].get("proven", False) and clean
            except Exception as exc:
                result["cleanup"]["proven"] = False
                result["cleanup"]["secondary_post_cleanup_failure"] = type(exc).__name__
        if result["decision"] == "READY_FOR_REVIEW" and not result["cleanup"].get("proven"):
            result["decision"] = "NO_GO"; result["exact_stop_reason"] = "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN"
        result["authorization_status"] = "EXPIRED_TERMINAL"
    return (0 if result["decision"] == "READY_FOR_REVIEW" else 2), result


def verify_machine_facts(summary: dict, repo: Path) -> dict:
    """Recompute product Oracles from raw machine facts; ignore summary PASS flags."""
    _privacy_scan(summary)
    if "service_logs" in summary:
        raise CheckpointError("RAW_SERVICE_LOG_PERSISTENCE_FORBIDDEN","service_logs")
    verify_denominator()
    if summary.get("schema_version") != "lvw.s1-stage-checkpoint-live/1" or summary.get("acceptance_hash") != ACCEPTANCE_HASH:
        raise CheckpointError("MACHINE_SUMMARY_BINDING_INVALID", "schema/denominator")
    if (summary.get("run_id") != AUTHORIZED_RUN_ID
            or summary.get("bindings", {}).get("run_id") != AUTHORIZED_RUN_ID
            or summary.get("bindings", {}).get("evidence_relative") != AUTHORIZED_EVIDENCE_RELATIVE
            or summary.get("authorization_status") != "EXPIRED_TERMINAL"):
        raise CheckpointError("MACHINE_SUMMARY_BINDING_INVALID", "run/evidence/terminal")
    identity = summary.get("identity", {})
    if identity.get("product_candidate") != PRODUCT_CANDIDATE or identity.get("product_artifact_sha256") != bind_candidate(repo):
        raise CheckpointError("MACHINE_IDENTITY_INVALID", "product artifacts")
    harness_relative = Path(__file__).resolve().relative_to(repo).as_posix()
    harness_hash = identity.get("harness_sha256")
    if (not re.fullmatch(r"[a-f0-9]{64}", str(harness_hash))
            or sha256(_commit_blob(repo, identity.get("harness_candidate", ""), harness_relative)).hexdigest() != harness_hash
            or sha256(Path(__file__).read_bytes()).hexdigest() != harness_hash):
        raise CheckpointError("MACHINE_IDENTITY_INVALID", "harness")
    lifecycle_hash=identity.get("lifecycle_sha256")
    if (identity.get("lifecycle_relative")!=LIFECYCLE_RELATIVE
            or not re.fullmatch(r"[a-f0-9]{64}",str(lifecycle_hash))
            or sha256((repo/LIFECYCLE_RELATIVE).read_bytes()).hexdigest()!=lifecycle_hash
            or sha256(_commit_blob(repo,identity.get("harness_candidate",""),LIFECYCLE_RELATIVE)).hexdigest()!=lifecycle_hash):
        raise CheckpointError("MACHINE_IDENTITY_INVALID","lifecycle")
    authority = summary.get("authority", {})
    authority_blobs={}
    for relative_key, hash_key in (("request_relative", "request_sha256"),
                                   ("authorization_relative", "authorization_sha256")):
        relative = authority.get(relative_key, "")
        blob=_commit_blob(repo, authority.get("authorization_commit", ""), relative) if isinstance(relative,str) else b""
        if (not isinstance(relative, str) or not relative.startswith("reports/v0-s1/")
                or sha256(blob).hexdigest()!=authority.get(hash_key)):
            raise CheckpointError("MACHINE_AUTHORITY_INVALID", relative_key)
        authority_blobs[relative_key]=blob
    try:
        request=json.loads(authority_blobs["request_relative"])
        authorization=json.loads(authority_blobs["authorization_relative"])
    except (KeyError,json.JSONDecodeError) as exc:
        raise CheckpointError("MACHINE_AUTHORITY_INVALID","JSON") from exc
    expected_authority={"product_candidate":PRODUCT_CANDIDATE,
        "harness_candidate":identity.get("harness_candidate"),"harness_sha256":harness_hash,
        "lifecycle_relative":LIFECYCLE_RELATIVE,"lifecycle_sha256":lifecycle_hash,
        "run_id":AUTHORIZED_RUN_ID,"evidence_relative":AUTHORIZED_EVIDENCE_RELATIVE,
        "sample_sha256":AUTHORIZED_SAMPLE_SHA256,"model_digest":AUTHORIZED_MODEL_DIGEST,
        "budget":ONE_SHOT_BUDGET,"acceptance_hash":ACCEPTANCE_HASH,"target_bindings":target_bindings()}
    validate_authority_documents(request,authorization,expected=expected_authority,
        request_hash=authority.get("request_sha256",""),authorization_id=authority.get("authorization_id",""))
    if summary.get("bindings",{}).get("target_bindings_sha256")!=value_hash(target_bindings()):
        raise CheckpointError("MACHINE_SUMMARY_BINDING_INVALID","targets")
    if summary.get("bindings",{}).get("ollama_executable_identity")!={
            "alias":AUTHORIZED_OLLAMA_EXE_ALIAS,"basename":AUTHORIZED_OLLAMA_EXE_BASENAME,
            "sha256":AUTHORIZED_OLLAMA_EXE_SHA256}:
        raise CheckpointError("MACHINE_SUMMARY_BINDING_INVALID","ollama executable identity")
    if summary.get("budget") != ONE_SHOT_BUDGET or summary.get("observed") != {
        "image_attempts": 1, "model_calls": 1, "comfy_starts": 1, "ollama_starts": 1,
        "public_submissions": PLANNED_PUBLIC_SUBMISSIONS}:
        raise CheckpointError("MACHINE_BUDGET_INVALID", "observed")
    if summary.get("network_gate", {}).get("ollama_no_cloud") is not True:
        raise CheckpointError("MACHINE_NETWORK_GATE_INVALID", "no-cloud")
    samples = summary.get("network_gate", {}).get("samples", [])
    if len(samples) < 5 or any(item.get("nonloopback_count") != 0 for item in samples):
        raise CheckpointError("MACHINE_NETWORK_GATE_INVALID", "remote sample")
    preflight=summary.get("preflight", {})
    if (not isinstance(preflight.get("gpu_count"),int) or preflight.get("gpu_count",0)<1
            or preflight.get("max_used_mib",4097)>4096 or preflight.get("process_match_count")!=0
            or preflight.get("target_listener_count")!=0):
        raise CheckpointError("MACHINE_PREFLIGHT_INVALID","GPU/process/port")
    if (summary.get("model_identity",{}).get("model")!="gemma4:26b"
            or summary.get("model_identity",{}).get("local_exact_match_count")!=1
            or summary.get("model_identity",{}).get("digest")!=AUTHORIZED_MODEL_DIGEST):
        raise CheckpointError("MACHINE_MODEL_IDENTITY_INVALID","exact local model")
    lineage=summary.get("owned_listener_lineage", {})
    if any(lineage.get(port,{}).get("lineage_proven") is not True for port in ("11434","8191")):
        raise CheckpointError("MACHINE_OWNERSHIP_INVALID","listener lineage")
    for key in ("image_runtime_guard","runtime_guard"):
        guard=summary.get(key,{})
        if guard.get("nonloopback_count")!=0 or guard.get("max_gpu_used_mib",23552)>=23552:
            raise CheckpointError("MACHINE_RUNTIME_GUARD_INVALID",key)
    facts = summary.get("case_facts", {})
    if set(facts) != set(CASE_IDS):
        raise CheckpointError("FIXED_DENOMINATOR_INCOMPLETE", "case facts")
    prompt_ids = []
    sequences = []
    def trace(value):
        if not isinstance(value, dict) or not isinstance(value.get("prompt_id"), str) or not value["prompt_id"]:
            raise CheckpointError("PUBLIC_TRACE_INVALID", "prompt id")
        if "history_ui_text" not in value and "error_facts" not in value:
            raise CheckpointError("PUBLIC_TRACE_INVALID", value["prompt_id"])
        prompt_ids.append(value["prompt_id"])
        sequences.append(value.get("submission_sequence"))
    a01 = facts["V0-A01"]; lifecycle = _load_proven_lifecycle(repo)
    trace({"prompt_id": a01.get("prompt_id"), "submission_sequence": a01.get("submission_sequence"),
           "history_ui_text": a01.get("history_ui_text")})
    image = lifecycle.validate_image_result(a01["history_ui_text"])
    metadata_payload = _manual_payload(a01["metadata_history_ui_text"]); metadata=json.loads(metadata_payload["draft"]["natural_zh"])
    if metadata != a01.get("metadata") or metadata.get("source_sha256") != AUTHORIZED_SAMPLE_SHA256 or max(metadata["output_dimensions"]) > 1024:
        raise CheckpointError("A01_FACT_RECOMPUTE_FAILED", "metadata")
    if image != a01.get("image_oracle"):
        raise CheckpointError("A01_FACT_RECOMPUTE_FAILED", "raw/suggestion")
    expected_a01=json.loads((repo/"LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json").read_text())
    expected_a01["1"]["inputs"]["image_reference"]="authorized-image.jpg"
    expected_a01["3"]=manual_public_graph({"natural_zh":["1",1]},"preview_json","metadata")["1"]
    if a01.get("graph_sha256") != value_hash(expected_a01):
        raise CheckpointError("A01_FACT_RECOMPUTE_FAILED", "graph hash")
    a03=facts["V0-A03"]
    for item in a03.get("traces", []): trace(item)
    if len(a03.get("traces", [])) != 3 or a03.get("model_calls_before") != a03.get("model_calls_after"):
        raise CheckpointError("A03_FACT_RECOMPUTE_FAILED", "traces/model")
    json_payload=_manual_payload(a03["traces"][1]["history_ui_text"]); _schema(repo).validate(json_payload)
    suggestion=json.loads(a01["history_ui_text"][1])
    a03_values={"natural_zh":suggestion.get("text_zh",""),"natural_en":suggestion.get("text_en",""),
        "image_prompt":suggestion.get("text_en",""),"video_prompt":suggestion.get("text_en",""),
        "tags":",".join(suggestion.get("tags",[])),"negative":suggestion.get("negative",""),"edit_instruction":""}
    expected_a03=[value_hash(manual_public_graph(a03_values,action,"a03"))
                  for action in ("preview_json","export_json","export_txt")]
    four_hashes={key:sha256(str(json_payload["draft"][key]).encode()).hexdigest()
                 for key in ("natural_zh","natural_en","image_prompt","video_prompt")}
    if (sha256(a03["traces"][1]["history_ui_text"][1].encode()).hexdigest()!=a03.get("json_sha256")
            or [item.get("graph_sha256") for item in a03["traces"]] != expected_a03
            or a03.get("four_output_sha256") != four_hashes
            or any(json_payload["draft"][key] != a03_values[key] for key in
                   ("natural_zh","natural_en","image_prompt","video_prompt"))
            or a03.get("source_raw_sha256") != image["raw_sha256"]
            or a03.get("json_reread_sha256") != a03.get("json_sha256")
            or not a03["traces"][2]["history_ui_text"][1].startswith("## Natural Chinese")
            or sha256(a03["traces"][2]["history_ui_text"][1].encode()).hexdigest()!=a03.get("txt_sha256")
            or a03.get("txt_reread_sha256") != a03.get("txt_sha256")):
        raise CheckpointError("A03_FACT_RECOMPUTE_FAILED", "exports")
    a04=facts["V0-A04"]
    for item in a04.get("success_traces", []): trace(item)
    trace(a04.get("failure_trace"))
    codes={fact.get("code") for fact in a04["failure_trace"].get("error_facts", [])}
    stop_fact=a04.get("ollama_stop_fact", {})
    exact="稿"*MAX_DRAFT_CHARACTERS; manual_values=_node_inputs(text=exact)
    expected_a04=[value_hash(manual_public_graph(manual_values,action,"a04")) for action in
                  ("preview_json","copy_json","copy_txt","export_json","export_txt")]
    if (len(a04.get("success_traces", [])) != 5 or stop_fact.get("lineage_reproven") is not True
            or stop_fact.get("stop_requested") is not True or stop_fact.get("terminal_absent") is not True
            or a04.get("draft_characters") != 20000 or "DISK_FULL" not in codes
            or a04.get("draft_sha256") != sha256(exact.encode()).hexdigest()
            or [item.get("graph_sha256") for item in a04.get("success_traces",[])] != expected_a04
            or a04.get("failure_trace",{}).get("graph_sha256") != value_hash(
                manual_public_graph(manual_values,"export_json","a04-failure"))
            or a04.get("failure_target_still_directory") is not True or a04.get("owned_temp_file_count") != 0):
        raise CheckpointError("A04_FACT_RECOMPUTE_FAILED", "manual/write failure")
    for name, index in (("a04.json", 3), ("a04.txt", 4)):
        if a04.get("exports", {}).get(name, {}).get("sha256") != sha256(
                a04["success_traces"][index]["history_ui_text"][1].encode()).hexdigest():
            raise CheckpointError("A04_FACT_RECOMPUTE_FAILED", name)
    a05=facts["V0-A05"]
    for item in a05.get("setup_traces", []): trace(item)
    if len(a05.get("setup_traces",[])) != 3:
        raise CheckpointError("A05_FACT_RECOMPUTE_FAILED","setup count")
    started_state=json.loads(a05["setup_traces"][0]["history_ui_text"][0])
    succeeded_state=json.loads(a05["setup_traces"][1]["history_ui_text"][0])
    adopted_state=json.loads(a05["setup_traces"][2]["history_ui_text"][0])
    token=started_state.get("run_token")
    adopted_json=a05["setup_traces"][2]["history_ui_text"][0]
    expected_setup=[
        value_hash(state_public_graph("","start_run",token)),
        value_hash(state_public_graph(a05["setup_traces"][0]["history_ui_text"][0],"model_success",token,
                                      raw=a01["history_ui_text"][0],suggestion=a01["history_ui_text"][1])),
        value_hash(state_public_graph(a05["setup_traces"][1]["history_ui_text"][0],"adopt",token,
                                      draft=canonical(adopted_state["draft"]).decode())),
    ]
    if ([item.get("graph_sha256") for item in a05["setup_traces"]] != expected_setup
            or started_state.get("analysis_status")!="running" or started_state.get("draft_epoch")!=0
            or succeeded_state.get("analysis_status")!="succeeded" or succeeded_state.get("draft_epoch")!=0
            or succeeded_state.get("raw_response")!=a01["history_ui_text"][0]
            or succeeded_state.get("suggestion")!=json.loads(a01["history_ui_text"][1])
            or adopted_state.get("draft_epoch")!=1
            or value_hash(adopted_state.get("draft"))!=a05.get("baseline_draft_sha256")):
        raise CheckpointError("A05_FACT_RECOMPUTE_FAILED","setup states")
    negative_specs={
        "invalid_json":("model_success","","{","PARSE_PARTIAL"),
        "explicit_refusal":("model_failure","MODEL_REFUSAL","",None),
        "timeout":("model_failure","MODEL_TIMEOUT","",None),
        "oom":("model_failure","GPU_OOM","",None),
        "stale_token":("model_success","","{}","ATTEMPT_STALE"),
    }
    for item in a05.get("negatives", []):
        trace(item.get("start_trace")); trace(item.get("callback_trace"))
        name=item.get("name"); action,error,suggestion_payload,expected_error=negative_specs.get(name,(None,None,None,None))
        running=json.loads(item["start_trace"]["history_ui_text"][0]); next_token=running.get("run_token")
        if item["start_trace"].get("graph_sha256") != value_hash(state_public_graph(adopted_json,"start_run",next_token)):
            raise CheckpointError("A05_FACT_RECOMPUTE_FAILED",name+":start graph")
        callback_token="stale" if name=="stale_token" else next_token
        expected_callback=value_hash(state_public_graph(item["start_trace"]["history_ui_text"][0],action,
            callback_token,raw="safe raw",suggestion=suggestion_payload,error=error))
        if item["callback_trace"].get("graph_sha256") != expected_callback:
            raise CheckpointError("A05_FACT_RECOMPUTE_FAILED",name+":callback graph")
        if expected_error:
            if expected_error not in {fact.get("code") for fact in item["callback_trace"].get("error_facts",[])}:
                raise CheckpointError("A05_FACT_RECOMPUTE_FAILED",name+":error code")
            final=running
        else:
            final=json.loads(item["callback_trace"]["history_ui_text"][0])
            if final.get("failure_code")!=error or final.get("analysis_status")!="failed":
                raise CheckpointError("A05_FACT_RECOMPUTE_FAILED",name+":failure state")
        if (value_hash(final.get("draft")) != a05.get("baseline_draft_sha256")
                or final.get("draft_epoch") != a05.get("baseline_epoch") or final.get("retry_count") != 0
                or item.get("draft_sha256") != a05.get("baseline_draft_sha256")
                or item.get("draft_epoch") != a05.get("baseline_epoch") or item.get("retry_count") != 0):
            raise CheckpointError("A05_FACT_RECOMPUTE_FAILED", item.get("name", "negative"))
    if {item.get("name") for item in a05.get("negatives", [])} != {"invalid_json","explicit_refusal","timeout","oom","stale_token"}:
        raise CheckpointError("A05_FACT_RECOMPUTE_FAILED", "negative set")
    if a05.get("automatic_retry_count") != 0:
        raise CheckpointError("A05_FACT_RECOMPUTE_FAILED", "automatic retry")
    a08=facts["V0-A08"]; trace(a08.get("trace")); payload=_manual_payload(a08["trace"]["history_ui_text"]); _schema(repo).validate(payload)
    expected_manual_keys={"natural_zh","natural_en","image_prompt","video_prompt","tags","negative","edit_instruction"}
    if ([payload["source_type"],payload["run_id"],payload["analysis_status"],payload["suggestion"]]
            != ["manual",None,"not_requested",None] or a08.get("model_calls_before") != a08.get("model_calls_after")
            or set(a08.get("manual_input_keys", [])) != expected_manual_keys
            or a08["trace"].get("graph_sha256") != value_hash(manual_public_graph(
                {key:"" for key in expected_manual_keys},"export_json","a08-empty"))
            or a08.get("export_sha256") != sha256(a08["trace"]["history_ui_text"][1].encode()).hexdigest()):
        raise CheckpointError("A08_FACT_RECOMPUTE_FAILED", "manual contract")
    if len(prompt_ids) != PLANNED_PUBLIC_SUBMISSIONS or len(set(prompt_ids)) != len(prompt_ids):
        raise CheckpointError("PUBLIC_TRACE_COUNT_INVALID", str(len(prompt_ids)))
    if sequences != list(range(1, PLANNED_PUBLIC_SUBMISSIONS + 1)):
        raise CheckpointError("PUBLIC_TRACE_ORDER_INVALID", repr(sequences))
    ledger=summary.get("model_call_ledger", [])
    if len(ledger)!=1 or ledger[0].get("raw_sha256")!=image["raw_sha256"] or summary.get("model_cleanup",{}).get("cleanup_http_status")!=200:
        raise CheckpointError("MODEL_LEDGER_INVALID", "model/cleanup")
    http_ledger=summary.get("model_http_ledger", {})
    if http_ledger != {"chat_200":1,"generate_200":2,"ps_200":1}:
        raise CheckpointError("MODEL_HTTP_LEDGER_INVALID", repr(http_ledger))
    log_facts=summary.get("service_log_facts",{})
    if (log_facts.get("ollama_http_200")!={"chat":1,"generate":2,"ps":1}
            or log_facts.get("comfy_got_prompt_count")!=PLANNED_PUBLIC_SUBMISSIONS
            or log_facts.get("ollama_no_cloud_marker_count",0)<1
            or log_facts.get("loopback_marker_count",0)<1
            or any(log_facts.get(key)!=0 for key in ("traceback_count","current_inputs_count",
                "secret_assignment_count","long_base64_count","rejected_diagnostic_count"))):
        raise CheckpointError("SERVICE_LOG_FACTS_INVALID","minimal ledger")
    integrity=summary.get("target_integrity", {})
    cleanup=summary.get("cleanup", {}); snapshot=summary.get("post_cleanup_snapshot", {})
    derived_cleanup=(integrity.get("pre")==integrity.get("post") and integrity.get("equal") is True
        and cleanup.get("final_target_listener_count")==0 and not cleanup.get("failures")
        and all(item.get("terminal_absent") for item in cleanup.get("owned_listener_terminal_states", []))
        and all(item.get("exited") for item in cleanup.get("owned_wrapper_terminal_states", []))
        and cleanup.get("run_owned_temp_removed") is True
        and snapshot=={"target_listener_count":0,"target_process_match_count":0,"run_temp_absent":True})
    if not derived_cleanup:
        raise CheckpointError("CLEANUP_FACT_RECOMPUTE_FAILED", "cleanup")
    return {"case_statuses": {key:"PASS_CANDIDATE_FOR_REVIEW" for key in CASE_IDS},
            "test_counts":{"denominator":5,"pass":5,"fail":0,"blocked":0,"skipped":0,"not_run":0},
            "ready_for_independent_review":True,"stage_pass_claim":False}


def verify_evidence_root(root: Path, repo: Path) -> dict:
    summary_path=root/"run-summary.json"; manifest_path=root/"artifact-manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    expected={"run-summary.json":summary_path,"implementation-receipt.json":root/"implementation-receipt.json"}
    if set(manifest)!=set(expected):
        raise CheckpointError("ARTIFACT_MANIFEST_MISMATCH","artifact set")
    for name,path in expected.items():
        if not path.is_file() or manifest.get(name)!=sha256(path.read_bytes()).hexdigest():
            raise CheckpointError("ARTIFACT_MANIFEST_MISMATCH",name)
    return verify_machine_facts(json.loads(summary_path.read_text(encoding="utf-8")), repo)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Identity-bound V0-S1 fixed-denominator checkpoint")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-check", action="store_true")
    group.add_argument("--plan", action="store_true")
    group.add_argument("--verify-evidence", type=Path, metavar="EVIDENCE_ROOT")
    group.add_argument("--execute-live", action="store_true")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--authorization-record", default="")
    parser.add_argument("--authorization-sha256", default="")
    parser.add_argument("--authorization-commit", default="")
    parser.add_argument("--request-record", default="")
    parser.add_argument("--request-sha256", default="")
    parser.add_argument("--product-candidate", default="")
    parser.add_argument("--harness-candidate", default="")
    parser.add_argument("--harness-sha256", default="")
    parser.add_argument("--lifecycle-sha256", default="")
    parser.add_argument("--sample", default="")
    parser.add_argument("--sample-sha256", default=AUTHORIZED_SAMPLE_SHA256)
    parser.add_argument("--comfy-main", default="")
    parser.add_argument("--comfy-python", default="")
    parser.add_argument("--ollama-exe", default="")
    parser.add_argument("--powershell", default="powershell.exe")
    parser.add_argument("--comfy-url", default=AUTHORIZED_COMFY_URL)
    parser.add_argument("--ollama-url", default=AUTHORIZED_OLLAMA_URL)
    parser.add_argument("--temp-parent", default="")
    parser.add_argument("--evidence-root", default=AUTHORIZED_EVIDENCE_RELATIVE)
    parser.add_argument("--run-id", default=AUTHORIZED_RUN_ID)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.self_check:
            output = run_offline_prechecks(args.repo.resolve())
        elif args.plan:
            verify_denominator()
            output = {"product_candidate": PRODUCT_CANDIDATE, "acceptance_ids": list(CASE_IDS),
                      "acceptance_hash": ACCEPTANCE_HASH, "one_shot_budget": ONE_SHOT_BUDGET,
                      "lifecycle": {"relative": LIFECYCLE_RELATIVE,
                                    "sha256": sha256((args.repo.resolve()/LIFECYCLE_RELATIVE).read_bytes()).hexdigest()},
                      "target_bindings": target_bindings(), "authorization_status_required": "GRANTED_ONCE",
                      "authorization_expiry_required": AUTH_EXPIRY,
                      "live_requirements": LIVE_REQUIREMENTS, "external_actions_now": 0,
                      "exact_stop_reason": "WAIT_AUTH_S1_FIXED_DENOMINATOR_NOT_RUN"}
        elif args.verify_evidence:
            output = verify_evidence_root(args.verify_evidence, args.repo.resolve())
        else:
            required = (args.authorization_id, args.authorization_record, args.authorization_sha256,
                        args.authorization_commit, args.request_record, args.request_sha256,
                        args.product_candidate, args.harness_candidate, args.harness_sha256,
                        args.lifecycle_sha256,
                        args.sample, args.comfy_main, args.comfy_python, args.ollama_exe, args.temp_parent)
            if not all(required):
                raise CheckpointError("LIVE_ARGUMENT_REQUIRED", "all identity/authority/target arguments")
            repo = args.repo.resolve(strict=True)
            # All byte/authority/path gates execute before the evidence reservation and before driver creation.
            validate_authority(args, repo)
            validate_live_identity(args, repo)
            validate_live_paths(args, repo, reserve=True)
            code, result = execute_live(args)
            if result.get("decision") == "READY_FOR_REVIEW":
                try:
                    result["independent_recompute"] = verify_machine_facts(result, repo)
                except CheckpointError as exc:
                    result["decision"] = "NO_GO"
                    result["exact_stop_reason"] = exc.code
                    result["independent_recompute_failure"] = str(exc)
                    code = 2
            lifecycle = _load_proven_lifecycle(repo)
            aliases = {str(repo): "REPO", str(Path(args.sample).resolve()): "TEST_SOURCE/image-sample",
                       str(Path(args.temp_parent).resolve()): "RUN_TEMP_PARENT",
                       str(Path(args.comfy_main)): "COMFY_ROOT/main.py",
                       str(Path(args.comfy_python)): "COMFY_PYTHON",
                       str(args.ollama_exe): AUTHORIZED_OLLAMA_EXE_ALIAS,
                       str(Path(args.ollama_exe).resolve()): AUTHORIZED_OLLAMA_EXE_ALIAS,
                       normalized_windows_path(args.ollama_exe): AUTHORIZED_OLLAMA_EXE_ALIAS}
            sanitized = lifecycle.redact_value(result, aliases)
            root = Path(args.evidence_root)
            summary_path = root / "run-summary.json"
            summary_path.write_text(json.dumps(sanitized, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                    encoding="utf-8")
            receipt = {"schema_version": "lvw.implementation-receipt/1", "project_id": "lvw-prompt-service",
                "stage_id": "V0-S1", "workpack_id": "WP-S1-04-CHECKPOINT-LIVE",
                "candidate_sha": args.product_candidate, "harness_candidate": args.harness_candidate,
                "harness_sha256": args.harness_sha256, "authorization_id": args.authorization_id,
                "lifecycle_relative": LIFECYCLE_RELATIVE, "lifecycle_sha256": args.lifecycle_sha256,
                "authorization_status": "EXPIRED_TERMINAL", "run_id": args.run_id,
                "acceptance_hash": ACCEPTANCE_HASH, "decision": result["decision"],
                "exact_stop_reason": result["exact_stop_reason"], "test_counts":
                ({"denominator":5,"pass":5,"fail":0,"blocked":0,"skipped":0,"not_run":0}
                 if result["decision"]=="READY_FOR_REVIEW" else
                 {"denominator":5,"pass":0,"fail":0,"blocked":5,"skipped":0,"not_run":0}),
                "product_acceptance": result["product_acceptance"], "observed": result["observed"],
                "cleanup": result["cleanup"], "stage_pass_claim": False,
                "raw_artifact_refs": [AUTHORIZED_EVIDENCE_RELATIVE+"/run-summary.json"]}
            receipt_path = root / "implementation-receipt.json"
            receipt_path.write_text(json.dumps(lifecycle.redact_value(receipt, aliases), ensure_ascii=False,
                                               sort_keys=True, indent=2)+"\n", encoding="utf-8")
            manifest = {path.name: sha256(path.read_bytes()).hexdigest() for path in
                        (summary_path, receipt_path)}
            (root / "artifact-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2)+"\n",
                                                         encoding="utf-8")
            print(json.dumps({"decision":result["decision"],"exact_stop_reason":result["exact_stop_reason"],
                              "authorization_status":"EXPIRED_TERMINAL"}, sort_keys=True))
            return code
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
