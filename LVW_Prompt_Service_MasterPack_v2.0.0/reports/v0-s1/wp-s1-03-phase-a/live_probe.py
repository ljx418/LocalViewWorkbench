#!/usr/bin/env python3
"""Identity-bound one-shot WP-S1-03 live probe.

Default execution is offline-only.  External actions require --execute-live,
the frozen authorization id, a sealed candidate SHA, and a harness blob/hash
match.  Evidence contains hashes, aliases, aggregate process/connection facts,
and redacted diagnostics; it never stores source media bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

AUTHORIZATION_ID = "AUTH-V0-S1-2026-10-28-05"
AUTHORIZED_START = "64ec38c22b6d200f18ca5c0d85f91faa1fadf206"
PHASE_A_BASELINE = "0dcf693128fe0b8e8215407b7e628970f798e595"
AUTHORIZED_SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
MODEL = "gemma4:26b"
COMFY_URL = "http://127.0.0.1:8191"
OLLAMA_URL = "http://127.0.0.1:11434"
GPU_PRESTART_MAX_MIB = 4096
GPU_ABORT_MIB = 23552
MAX_PUBLIC_SUBMISSIONS = 8
REQUIRED_NODES = {"LVWControlledImageInput", "LVWImagePromptBridge", "LVWDraftStateOwner", "LVWManualPromptOwner"}
ALLOWED_PREFIXES = ("LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/", "LVW_V0_RuntimePatch/tests/", "reports/v0-s1/")
ALLOWED_EXACT = {
    "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.ui.json",
    "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json",
}
PRODUCT_CASES = {key: "NOT_RUN" for key in ("V0-A01", "V0-A03", "V0-A04", "V0-A05", "V0-A08")}
PROMPT_SPEC_KEYS = {"schema_version", "mode", "domains", "technical", "locked_fields", "text_zh", "text_en",
                    "tags", "negative", "template_id", "template_version"}
DOMAIN_KEYS = {"observation", "inference", "user_evidence", "creative_intent", "unknowns"}
AUTHORIZED_COMFY_MAIN = "C:/ComfyUI-aki-v2/ComfyUI/main.py"
AUTHORIZED_COMFY_PYTHON = "C:/ComfyUI-aki-v2/python/python.exe"
AUTHORIZED_EVIDENCE_RELATIVE = "reports/v0-s1/wp-s1-03-live-05"
AUTHORIZED_RUN_ID = "v0-s1-wp-s1-03-live-05"


class StopProbe(RuntimeError):
    def __init__(self, reason: str, *, evidence: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.evidence = evidence or {}


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact(value: str, aliases: dict[str, str]) -> str:
    result = str(value)
    for private, alias in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if private:
            result = result.replace(private, alias).replace(private.replace("\\", "/"), alias)
    result = re.sub(r"(?i)(authorization|bearer|token|password|api[_-]?key)\s*[:=]\s*[^\s,;]+", r"\1=<REDACTED>", result)
    result = re.sub(r"(?i)[A-Z]:[/\\](?:[^\s\"']+[/\\])*[^\s\"']+", "<PRIVATE_WINDOWS_PATH>", result)
    result = re.sub(r"/mnt/[a-z]/(?:[^\s\"']+/)*[^\s\"']+", "<PRIVATE_WSL_PATH>", result)
    return result


def redact_value(value, aliases: dict[str, str]):
    """Redact JSON-compatible values without modifying JSON escape syntax.

    Applying path regexes to an already serialized JSON document can consume a
    backslash that belongs to JSON escaping and make the terminal evidence
    unparsable.  Redact string leaves first, then let json.dumps encode them.
    """
    if isinstance(value, str):
        return redact(value, aliases)
    if isinstance(value, dict):
        return {redact(key, aliases) if isinstance(key, str) else key: redact_value(item, aliases)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item, aliases) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item, aliases) for item in value]
    return value


def normalized_windows_path(value: str) -> str:
    path = str(value).replace("\\", "/")
    match = re.fullmatch(r"/mnt/([a-zA-Z])/(.+)", path)
    if match:
        path = f"{match.group(1).upper()}:/{match.group(2)}"
    path = re.sub(r"/+", "/", path).rstrip("/")
    return path


def validate_live_boundaries(args, *, reserve_evidence: bool) -> dict:
    repo = Path(args.repo).resolve(strict=True)
    evidence = Path(args.evidence_root)
    expected = repo / AUTHORIZED_EVIDENCE_RELATIVE
    if evidence.resolve(strict=False) != expected:
        raise StopProbe("EVIDENCE_ROOT_OUTSIDE_AUTHORIZED_BOUNDARY")
    if args.run_id != AUTHORIZED_RUN_ID:
        raise StopProbe("AUTHORIZED_RUN_ID_MISMATCH")
    if normalized_windows_path(args.comfy_main).casefold() != AUTHORIZED_COMFY_MAIN.casefold():
        raise StopProbe("AUTHORIZED_COMFY_MAIN_MISMATCH")
    if normalized_windows_path(args.comfy_python).casefold() != AUTHORIZED_COMFY_PYTHON.casefold():
        raise StopProbe("AUTHORIZED_COMFY_PYTHON_MISMATCH")
    temp_parent = Path(args.temp_parent)
    temp_resolved = temp_parent.resolve() if temp_parent.exists() else temp_parent
    temp_windows = normalized_windows_path(str(temp_resolved)).casefold()
    if (not temp_parent.is_dir() or temp_parent.is_symlink()
            or not temp_resolved.as_posix().casefold().startswith("/mnt/c/")
            or temp_windows.startswith("c:/comfyui/")
            or temp_resolved == repo or repo in temp_resolved.parents):
        raise StopProbe("RUN_TEMP_PARENT_FORBIDDEN")
    if reserve_evidence:
        try:
            evidence.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise StopProbe("EVIDENCE_ROOT_ALREADY_EXISTS") from exc
    elif not evidence.is_dir():
        raise StopProbe("EVIDENCE_ROOT_NOT_RESERVED")
    return {"comfy_main": AUTHORIZED_COMFY_MAIN, "comfy_python": AUTHORIZED_COMFY_PYTHON,
            "evidence_root": "REPO/" + AUTHORIZED_EVIDENCE_RELATIVE,
            "run_id": AUTHORIZED_RUN_ID, "temp_parent_valid": True}


def ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def ollama_wrapper_text(exe: str, pid_file: str) -> str:
    return (f"$PID | Set-Content -LiteralPath {ps_quote(pid_file)} -Encoding ascii\n"
            "$env:OLLAMA_HOST='127.0.0.1:11434'\n$env:OLLAMA_NO_CLOUD='1'\n"
            "$env:NO_PROXY='127.0.0.1,localhost'\nWrite-Output 'OLLAMA_NO_CLOUD=true'\n"
            f"& {ps_quote(exe)} serve\nexit $LASTEXITCODE\n")


def comfy_wrapper_text(python: str, main: str, base: str, pid_file: str) -> str:
    return (f"$PID | Set-Content -LiteralPath {ps_quote(pid_file)} -Encoding ascii\n"
            f"& {ps_quote(python)} -s -B {ps_quote(main)} --listen 127.0.0.1 --port 8191 "
            f"--base-directory {ps_quote(base)} --disable-auto-launch --disable-api-nodes "
            "--disable-all-custom-nodes --whitelist-custom-nodes lvw_v0_bridge\nexit $LASTEXITCODE\n")


def run_local(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=60)


def candidate_identity(repo: Path, candidate: str, harness_relative: str, expected_harness_hash: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}", candidate):
        raise StopProbe("CANDIDATE_SHA_INVALID")
    top = run_local(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    if top.returncode != 0:
        raise StopProbe("GIT_ROOT_UNAVAILABLE")
    git_root = Path(top.stdout.strip()).resolve()
    try:
        pack_prefix = repo.resolve().relative_to(git_root).as_posix()
    except ValueError as exc:
        raise StopProbe("REPO_OUTSIDE_GIT_ROOT") from exc
    ancestor = run_local(["git", "merge-base", "--is-ancestor", AUTHORIZED_START, candidate], cwd=repo)
    if ancestor.returncode != 0:
        raise StopProbe("CANDIDATE_NOT_AUTHORIZED_DESCENDANT")
    baseline = run_local(["git", "merge-base", "--is-ancestor", PHASE_A_BASELINE, candidate], cwd=repo)
    if baseline.returncode != 0:
        raise StopProbe("CANDIDATE_NOT_PHASE_A_DESCENDANT")
    changed = run_local(["git", "diff", "--name-only", f"{AUTHORIZED_START}..{candidate}"], cwd=repo)
    if changed.returncode != 0:
        raise StopProbe("CANDIDATE_CHANGED_FILES_UNAVAILABLE")
    git_files = [line for line in changed.stdout.splitlines() if line]
    prefix = pack_prefix + "/" if pack_prefix else ""
    if any(prefix and not path.startswith(prefix) for path in git_files):
        raise StopProbe("CANDIDATE_CHANGED_FILE_OUTSIDE_ALLOWLIST")
    files = [path[len(prefix):] if prefix else path for path in git_files]
    if any(not (path in ALLOWED_EXACT or path.startswith(ALLOWED_PREFIXES)) for path in files):
        raise StopProbe("CANDIDATE_CHANGED_FILE_OUTSIDE_ALLOWLIST")
    file_hashes = {}
    for relative, git_path in zip(files, git_files):
        blob = subprocess.run(["git", "show", f"{candidate}:{git_path}"], cwd=repo, capture_output=True, timeout=60)
        local = repo / relative
        if blob.returncode != 0 or not local.is_file() or sha256_bytes(blob.stdout) != sha256_file(local):
            raise StopProbe("CANDIDATE_FILE_IDENTITY_MISMATCH")
        file_hashes[relative] = sha256_bytes(blob.stdout)
    harness_git_path = prefix + harness_relative
    blob = subprocess.run(["git", "show", f"{candidate}:{harness_git_path}"], cwd=repo, capture_output=True, timeout=60)
    if blob.returncode != 0:
        raise StopProbe("HARNESS_BLOB_MISSING")
    blob_hash = sha256_bytes(blob.stdout)
    file_hash = sha256_file(Path(__file__).resolve())
    if blob_hash != expected_harness_hash or file_hash != expected_harness_hash:
        raise StopProbe("HARNESS_IDENTITY_MISMATCH")
    return {"candidate_sha": candidate, "changed_file_count": len(files), "file_sha256": file_hashes,
            "harness_sha256": file_hash, "identity_match": True}


def workflow_oracle(history: dict, prompt_id: str, node_id: str) -> list[str]:
    record = history.get(prompt_id)
    if not isinstance(record, dict):
        raise StopProbe("PUBLIC_HISTORY_PROMPT_MISSING")
    if record.get("status", {}).get("status_str") not in {"success", "completed"}:
        messages = record.get("status", {}).get("messages", [])
        facts = []
        for item in messages if isinstance(messages, list) else []:
            if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str)):
                continue
            fact = {"event": item[0]}
            payload = item[1]
            if isinstance(payload, dict):
                for key in ("node_id", "node_type"):
                    if isinstance(payload.get(key), str):
                        fact[key] = payload[key]
                try:
                    error = json.loads(payload.get("exception_message", "").strip())
                except (AttributeError, json.JSONDecodeError):
                    error = {}
                if isinstance(error, dict) and isinstance(error.get("code"), str):
                    fact["code"] = error["code"]
                    details = error.get("details")
                    if isinstance(details, dict) and isinstance(details.get("subcode"), str):
                        fact["subcode"] = details["subcode"]
            facts.append(fact)
        raise StopProbe("PUBLIC_COMFY_ROUTE_FAILED:" + canonical_json({"events": facts}))
    text = record.get("outputs", {}).get(node_id, {}).get("text")
    if not isinstance(text, list) or not all(isinstance(item, str) for item in text):
        raise StopProbe("PUBLIC_HISTORY_UI_TEXT_MISSING")
    return text


def validate_image_result(text: list[str]) -> dict:
    if len(text) < 2:
        raise StopProbe("PUBLIC_IMAGE_UI_RAW_SUGGESTION_MISSING")
    try:
        raw = json.loads(text[0])
        suggestion = json.loads(text[1])
    except json.JSONDecodeError as exc:
        raise StopProbe("PUBLIC_IMAGE_UI_JSON_INVALID") from exc
    if not isinstance(raw, dict) or not isinstance(suggestion, dict):
        raise StopProbe("PUBLIC_IMAGE_UI_SCHEMA_INVALID")
    domains = suggestion.get("domains")
    if (set(suggestion) != PROMPT_SPEC_KEYS or suggestion.get("schema_version") != "lvw.prompt/1"
            or not isinstance(domains, dict) or set(domains) != DOMAIN_KEYS
            or not isinstance(domains.get("observation"), list) or not domains["observation"]
            or not all(isinstance(item, str) and item.strip() for item in domains["observation"])
            or not isinstance(suggestion.get("text_en"), str) or not suggestion["text_en"].strip()):
        raise StopProbe("PUBLIC_IMAGE_SEMANTIC_ORACLE_FAILED")
    return {"raw_sha256": sha256_bytes(text[0].encode()), "suggestion_sha256": sha256_bytes(text[1].encode())}


class SystemDriver:
    """Narrow loopback/Windows-native driver.  Created only after live gates pass."""

    def __init__(self, args, evidence):
        self.args = args
        self.evidence = evidence
        self.submissions = 0
        self.started_model_calls = 0
        self.owned = []
        self.listener_pids = set()
        self.listener_proofs = {}
        self.owned_listener_evidence = {}
        self.ollama_log = None

    def _json_request(self, url: str, *, payload=None, timeout=20):
        if not (url.startswith(COMFY_URL + "/") or url.startswith(OLLAMA_URL + "/")):
            raise StopProbe("NON_LOOPBACK_URL_FORBIDDEN")
        body = canonical_json(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", errors="strict"))

    def _powershell(self, script: str) -> str:
        result = subprocess.run([self.args.powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=60)
        if result.returncode != 0:
            raise StopProbe("WINDOWS_PREFLIGHT_COMMAND_FAILED")
        return result.stdout.strip()

    def _windows_path(self, value: str, *, expected: str | None = None) -> str:
        result = run_local(["wslpath", "-w", value])
        if result.returncode != 0 or not result.stdout.strip():
            raise StopProbe("WINDOWS_PATH_CONVERSION_FAILED")
        converted = normalized_windows_path(result.stdout.strip())
        if expected is not None and converted.casefold() != expected.casefold():
            raise StopProbe("AUTHORIZED_TARGET_PATH_CONVERSION_MISMATCH")
        return result.stdout.strip()

    def _prove_listener_owned(self, port: int, wrapper_pid_file: Path, executable_name: str) -> int:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not wrapper_pid_file.exists():
            time.sleep(0.25)
        if not wrapper_pid_file.exists():
            raise StopProbe("OWNED_WRAPPER_PID_MISSING")
        wrapper_pid = int(wrapper_pid_file.read_text(encoding="ascii").strip())
        listener_pid = self._listener_pid(port)
        current = listener_pid
        executable_ok = False
        lineage = set()
        for _ in range(8):
            raw = self._powershell(
                f"$x=Get-CimInstance Win32_Process -Filter \"ProcessId={current}\" -ErrorAction SilentlyContinue;"
                "$x | Select-Object ProcessId,ParentProcessId,ExecutablePath | ConvertTo-Json -Compress")
            if not raw:
                break
            row = json.loads(raw)
            lineage.add(int(row["ProcessId"]))
            if current == listener_pid:
                executable_ok = normalized_windows_path(row.get("ExecutablePath", "")).casefold().endswith("/" + executable_name.casefold())
            parent = int(row.get("ParentProcessId") or 0)
            if wrapper_pid in {current, parent}:
                lineage.add(wrapper_pid)
                break
            current = parent
        wrapper_raw = self._powershell(
            f"$x=Get-CimInstance Win32_Process -Filter \"ProcessId={wrapper_pid}\" -ErrorAction SilentlyContinue;"
            "$x | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
        wrapper_row = json.loads(wrapper_raw) if wrapper_raw else {}
        wrapper_executable = normalized_windows_path(wrapper_row.get("ExecutablePath", "")).casefold()
        wrapper_ok = wrapper_executable.endswith("/powershell.exe") or wrapper_executable.endswith("/pwsh.exe")
        if wrapper_pid not in lineage or not executable_ok or not wrapper_ok:
            raise StopProbe("LISTENER_OWNERSHIP_NOT_PROVEN")
        self.listener_pids.add(listener_pid)
        self.listener_proofs[port] = {"wrapper_pid_file": wrapper_pid_file, "executable_name": executable_name}
        self.owned_listener_evidence[str(port)] = {"listener_pid": listener_pid, "wrapper_pid": wrapper_pid,
                                                    "lineage_proven": True}
        return listener_pid

    def ownership_summary(self) -> dict:
        return dict(self.owned_listener_evidence)

    def preflight(self) -> dict:
        gpu_native = self._powershell("& nvidia-smi --query-gpu=index,memory.total,memory.used,memory.free --format=csv,noheader,nounits")
        gpu_wsl = run_local(["nvidia-smi", "--query-gpu=index,memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"])
        if gpu_wsl.returncode != 0:
            raise StopProbe("GPU_PREFLIGHT_WSL_FAILED")
        def parse(value):
            return [[int(part.strip()) for part in line.split(",")] for line in value.splitlines() if line.strip()]
        native, wsl = parse(gpu_native), parse(gpu_wsl.stdout)
        if len(native) != len(wsl) or any(a[:2] != b[:2] or max(abs(a[2]-b[2]), abs(a[3]-b[3])) > 128 for a, b in zip(native, wsl)):
            raise StopProbe("GPU_PREFLIGHT_WINDOWS_WSL_MISMATCH")
        gpu_evidence = {"gpu_count": len(native), "max_used_mib": max(row[2] for row in native),
                        "limit_mib": GPU_PRESTART_MAX_MIB}
        if gpu_evidence["max_used_mib"] > GPU_PRESTART_MAX_MIB:
            raise StopProbe("GPU_PREFLIGHT_USED_MEMORY_EXCEEDED", evidence={"preflight": gpu_evidence})
        listener_raw = self._powershell(
            "$x=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in 8191,11434};"
            "@($x | Select-Object LocalAddress,LocalPort,OwningProcess) | ConvertTo-Json -Compress")
        listeners = json.loads(listener_raw) if listener_raw else []
        if listeners:
            raise StopProbe("PREFLIGHT_TARGET_PORT_OWNED")
        matches = int(self._powershell(
            "$x=Get-CimInstance Win32_Process | Where-Object {($_.Name -match 'ollama') -or "
            "(($_.Name -match 'python') -and ($_.CommandLine -match 'ComfyUI'))}; @($x).Count"))
        if matches:
            raise StopProbe("PREFLIGHT_TARGET_PROCESS_PRESENT")
        return {"gpu_count": len(native), "max_used_mib": max(row[2] for row in native),
                "process_match_count": matches, "target_listener_count": 0}

    def start_ollama(self, log_path: Path):
        self.ollama_log = log_path
        base = log_path.parent
        wrapper = base / "ollama-wrapper.ps1"
        pid_file = base / "ollama-wrapper.pid"
        win_exe = self._windows_path(self.args.ollama_exe)
        if not normalized_windows_path(win_exe).casefold().endswith("/ollama.exe"):
            raise StopProbe("OLLAMA_EXECUTABLE_PATH_INVALID")
        wrapper.write_text(ollama_wrapper_text(win_exe, self._windows_path(str(pid_file))), encoding="utf-8")
        stream = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen([self.args.powershell, "-NoProfile", "-NonInteractive", "-File",
                                    self._windows_path(str(wrapper))], stdout=stream, stderr=subprocess.STDOUT, text=True)
        self.owned.append(("ollama_wrapper", process, stream))
        self.ollama_wrapper_pid_file = pid_file

    def wait_json(self, url, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return self._json_request(url)
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                time.sleep(1)
        raise StopProbe("SERVICE_START_TIMEOUT")

    def no_cloud_remote_gate(self) -> dict:
        self.wait_json(OLLAMA_URL + "/api/version")
        if self.ollama_log is None or "OLLAMA_NO_CLOUD=true" not in self.ollama_log.read_text(encoding="utf-8", errors="strict"):
            raise StopProbe("OLLAMA_NO_CLOUD_NOT_OBSERVED")
        self._prove_listener_owned(11434, self.ollama_wrapper_pid_file, "ollama.exe")
        samples = []
        for _ in range(5):
            raw = self._powershell(
                "$x=Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | "
                "Where-Object {$_.LocalPort -eq 11434 -or $_.RemotePort -eq 11434};"
                "@($x | Select-Object LocalAddress,RemoteAddress,OwningProcess) | ConvertTo-Json -Compress")
            rows = json.loads(raw) if raw else []
            rows = rows if isinstance(rows, list) else [rows]
            remote = [row for row in rows if row.get("RemoteAddress") not in {"127.0.0.1", "::1"}]
            samples.append({"connection_count": len(rows), "nonloopback_count": len(remote)})
            if remote:
                raise StopProbe("OLLAMA_NON_LOOPBACK_CONNECTION")
            time.sleep(2)
        return {"ollama_no_cloud": True, "duration_seconds_min": 10, "samples": samples}

    def _listener_pid_values(self, port: int) -> list[int]:
        raw = self._powershell(
            f"$x=Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue;"
            "@($x | Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress")
        values = json.loads(raw) if raw else []
        values = values if isinstance(values, list) else [values]
        return [int(value) for value in values]

    def _listener_pid(self, port: int) -> int:
        values = self._listener_pid_values(port)
        if len(values) != 1:
            raise StopProbe("OWNED_LISTENER_PID_AMBIGUOUS")
        return values[0]

    def start_comfy(self, base: Path, log_path: Path):
        win_main = self._windows_path(self.args.comfy_main, expected=AUTHORIZED_COMFY_MAIN)
        win_python = self._windows_path(self.args.comfy_python, expected=AUTHORIZED_COMFY_PYTHON)
        win_base = self._windows_path(str(base))
        wrapper = base / "comfy-wrapper.ps1"
        pid_file = base / "comfy-wrapper.pid"
        wrapper.write_text(comfy_wrapper_text(win_python, win_main, win_base, self._windows_path(str(pid_file))),
                           encoding="utf-8")
        stream = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen([self.args.powershell, "-NoProfile", "-NonInteractive", "-File",
                                    self._windows_path(str(wrapper))], stdout=stream, stderr=subprocess.STDOUT, text=True)
        self.owned.append(("comfy", process, stream))
        self.wait_json(COMFY_URL + "/object_info", timeout=120)
        self._prove_listener_owned(8191, pid_file, "python.exe")

    def registry(self) -> dict:
        return self._json_request(COMFY_URL + "/object_info")[1]

    def verify_model(self) -> dict:
        tags = self._json_request(OLLAMA_URL + "/api/tags")[1].get("models", [])
        matches = [item for item in tags if item.get("name") == MODEL or item.get("model") == MODEL]
        if len(matches) != 1:
            raise StopProbe("AUTHORIZED_MODEL_NOT_LOCALLY_PRESENT")
        return {"model": MODEL, "local_exact_match_count": 1,
                "digest": matches[0].get("digest")}

    def submit(self, graph: dict) -> str:
        if self.submissions >= MAX_PUBLIC_SUBMISSIONS:
            raise StopProbe("PUBLIC_API_SUBMISSION_BUDGET_EXCEEDED")
        self.submissions += 1
        status, value = self._json_request(COMFY_URL + "/prompt", payload={"prompt": graph, "client_id": self.args.run_id})
        if status != 200 or not isinstance(value.get("prompt_id"), str):
            raise StopProbe("PUBLIC_PROMPT_SUBMISSION_FAILED")
        return value["prompt_id"]

    def history(self, prompt_id: str) -> dict:
        deadline = time.monotonic() + 480
        while time.monotonic() < deadline:
            value = self._json_request(COMFY_URL + "/history/" + prompt_id, timeout=30)[1]
            if prompt_id in value:
                return value
            time.sleep(1)
        raise StopProbe("PUBLIC_HISTORY_TIMEOUT")

    def unload(self):
        status, _ = self._json_request(OLLAMA_URL + "/api/generate", payload={"model": MODEL, "keep_alive": 0})
        if status != 200:
            raise StopProbe("PER_CALL_UNLOAD_FAILED")
        ps = self._json_request(OLLAMA_URL + "/api/ps")[1]
        if ps.get("models"):
            raise StopProbe("TERMINAL_OLLAMA_PS_NOT_EMPTY")
        return {"cleanup_http_status": status, "terminal_api_ps_model_count": 0}

    def runtime_guard(self) -> dict:
        used = self._powershell("& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")
        values = [int(line.strip()) for line in used.splitlines() if line.strip()]
        if not values or max(values) >= GPU_ABORT_MIB:
            raise StopProbe("GPU_RUNTIME_ABORT_THRESHOLD_REACHED")
        raw = self._powershell(
            "$x=Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | "
            "Where-Object {$_.LocalPort -eq 11434 -or $_.RemotePort -eq 11434};"
            "@($x | Select-Object RemoteAddress,OwningProcess) | ConvertTo-Json -Compress")
        rows = json.loads(raw) if raw else []
        rows = rows if isinstance(rows, list) else [rows]
        if any(row.get("RemoteAddress") not in {"127.0.0.1", "::1"} for row in rows):
            raise StopProbe("OLLAMA_NON_LOOPBACK_CONNECTION")
        return {"max_gpu_used_mib": max(values), "nonloopback_count": 0}

    def stop_ollama(self):
        proof = self.listener_proofs.get(11434)
        if proof is None:
            raise StopProbe("OLLAMA_LISTENER_OWNERSHIP_LOST")
        pid = self._prove_listener_owned(11434, proof["wrapper_pid_file"], proof["executable_name"])
        self._powershell(f"Stop-Process -Id {pid} -Force -ErrorAction Stop")
        self.listener_pids.discard(pid)
        for _ in range(20):
            count = int(self._powershell(
                "$x=Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue; @($x).Count") or "0")
            if count == 0:
                self.listener_proofs.pop(11434, None)
                return
            time.sleep(0.5)
        raise StopProbe("OLLAMA_STOP_NOT_PROVEN_BEFORE_MANUAL_ROUTE")

    def target_hashes(self) -> dict:
        root = Path(self.args.comfy_main).parent
        files = {
            "main.py": root / "main.py", "folder_paths.py": root / "folder_paths.py",
            "nodes.py": root / "nodes.py", "comfy/cli_args.py": root / "comfy/cli_args.py",
            "extra_model_paths.yaml": root / "extra_model_paths.yaml",
        }
        result = {name: (sha256_file(path) if path.is_file() else "MISSING") for name, path in files.items()}
        forbidden = root / "custom_nodes/prompt-assistant"
        entries = []
        if forbidden.is_dir():
            for item in sorted(path for path in forbidden.rglob("*") if path.is_file()):
                entries.append(item.relative_to(forbidden).as_posix() + ":" + sha256_file(item))
        result["prompt_assistant_state"] = {
            "exists": forbidden.exists(),
            "file_count": len(entries),
            "tree_sha256": sha256_bytes("\n".join(entries).encode()) if entries else None,
        }
        return result

    def cleanup(self) -> dict:
        failures = []
        for port, proof in sorted(self.listener_proofs.items()):
            try:
                if not self._listener_pid_values(port):
                    continue
                pid = self._prove_listener_owned(port, proof["wrapper_pid_file"], proof["executable_name"])
                self._powershell(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
            except Exception as exc:
                failures.append({"owner": f"listener_{port}", "error": type(exc).__name__})
        for name, process, stream in reversed(self.owned):
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)
            except Exception as exc:
                failures.append({"owner": name, "error": type(exc).__name__})
            finally:
                stream.close()
        raw = self._powershell(
            "$x=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in 8191,11434};"
            "@($x).Count")
        listeners = int(raw or "0")
        return {"owned_count": len(self.owned), "failures": failures, "final_target_listener_count": listeners,
                "proven": not failures and listeners == 0}


def state_graph(state: str, action: str, token: str, raw="", suggestion="", draft="", error="") -> dict:
    return {"1": {"class_type": "LVWDraftStateOwner", "inputs": {
        "state": state, "action": action, "run_token": token, "raw_response": raw,
        "suggestion_payload": suggestion, "draft_payload": draft, "error_code": error}}}


def manual_graph() -> dict:
    return {"1": {"class_type": "LVWManualPromptOwner", "inputs": {
        "natural_zh": "离线人工稿", "natural_en": "", "image_prompt": "", "video_prompt": "",
        "tags": "", "negative": "", "edit_instruction": "", "action": "preview_json", "filename": "lvw-manual"}}}


def execute(args, driver_factory=SystemDriver) -> tuple[int, dict]:
    result = {"schema_version": "lvw.wp-s1-03-live/1", "run_id": args.run_id, "authorization": AUTHORIZATION_ID,
              "decision": "BLOCKED", "exact_stop_reason": None, "authorization_status": "ACTIVE",
              "attempts": {"image": 0, "model_calls": 0}, "service_starts": {"ollama": 0, "comfy": 0},
              "public_submissions": 0, "product_acceptance": PRODUCT_CASES.copy(), "stage_pass_claim": False,
              "evidence": {}, "cleanup": {"proven": False}, "external_cost": 0}
    base = None
    driver = None
    before = None
    try:
        result["evidence"]["authorized_boundaries"] = validate_live_boundaries(args, reserve_evidence=False)
        if args.authorization_id != AUTHORIZATION_ID:
            raise StopProbe("AUTHORIZATION_ID_MISMATCH")
        identity = candidate_identity(Path(args.repo), args.candidate_sha, args.harness_relative, args.harness_sha256)
        result["evidence"]["identity"] = identity
        if sha256_file(Path(args.sample)) != AUTHORIZED_SAMPLE_SHA256 or args.sample_sha256 != AUTHORIZED_SAMPLE_SHA256:
            raise StopProbe("AUTHORIZED_SAMPLE_HASH_MISMATCH")
        base = Path(tempfile.mkdtemp(prefix="lvw-s1-03-", dir=args.temp_parent))
        for name in ("input", "output", "temp", "custom_nodes"):
            (base / name).mkdir()
        shutil.copytree(Path(args.repo) / "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge",
                        base / "custom_nodes/lvw_v0_bridge")
        alias = "authorized-image" + Path(args.sample).suffix.lower()
        shutil.copyfile(args.sample, base / "input" / alias)
        driver = driver_factory(args, result)
        before = driver.target_hashes()
        result["evidence"]["preflight"] = driver.preflight()
        driver.start_ollama(base / "ollama.log")
        result["service_starts"]["ollama"] = 1
        result["evidence"]["network_gate"] = driver.no_cloud_remote_gate()
        driver.start_comfy(base, base / "comfy.log")
        result["service_starts"]["comfy"] = 1
        result["evidence"]["owned_listener_lineage"] = driver.ownership_summary()
        registry = driver.registry()
        missing = sorted(REQUIRED_NODES - set(registry))
        if missing:
            raise StopProbe("REQUIRED_PUBLIC_NODE_MISSING:" + ",".join(missing))
        result["evidence"]["model_identity"] = driver.verify_model()
        graph = json.loads((Path(args.repo) / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json").read_text())
        graph["1"]["inputs"]["image_reference"] = alias
        result["attempts"]["image"] = 1
        result["attempts"]["model_calls"] = 1
        image_text = None
        try:
            prompt_id = driver.submit(graph)
            image_history = driver.history(prompt_id)
            image_text = workflow_oracle(image_history, prompt_id, "2")
            result["evidence"]["image_oracle"] = validate_image_result(image_text)
            result["evidence"]["public_image_trace"] = {
                "prompt_id": prompt_id, "prompt": graph, "history_ui_text": image_text
            }
            result["evidence"]["runtime_guard"] = driver.runtime_guard()
        finally:
            result["evidence"]["model_cleanup"] = driver.unload()
        if image_text is None:
            raise StopProbe("PUBLIC_IMAGE_RESULT_MISSING")
        token = args.run_id + "-image"
        start_id = driver.submit(state_graph("", "start_run", token))
        started = workflow_oracle(driver.history(start_id), start_id, "1")[0]
        success_id = driver.submit(state_graph(started, "model_success", token, raw=image_text[0], suggestion=image_text[1]))
        succeeded = workflow_oracle(driver.history(success_id), success_id, "1")[0]
        state = json.loads(succeeded)
        if (state["draft_epoch"] != 0 or any(state["draft"].values()) or state["raw_response"] != image_text[0]
                or state["suggestion"] != json.loads(image_text[1]) or state["raw_response"] == image_text[1]):
            raise StopProbe("LIVE_STATE_ISOLATION_FAILED")
        adopted_payload = canonical_json({"natural_zh": "人工采纳", "natural_en": "", "image_prompt": "",
                                          "video_prompt": "", "tags": [], "negative": "", "edit_instruction": ""})
        adopt_id = driver.submit(state_graph(succeeded, "adopt", token, draft=adopted_payload))
        adopted = json.loads(workflow_oracle(driver.history(adopt_id), adopt_id, "1")[0])
        if adopted["draft_epoch"] != 1 or adopted["draft"]["natural_zh"] != "人工采纳":
            raise StopProbe("LIVE_EXPLICIT_ADOPT_FAILED")
        driver.stop_ollama()
        manual_id = driver.submit(manual_graph())
        manual_text = workflow_oracle(driver.history(manual_id), manual_id, "1")
        if not manual_text or "not_requested" not in "".join(manual_text):
            raise StopProbe("LIVE_MANUAL_CPU_ROUTE_FAILED")
        result["evidence"]["state_oracle"] = {"draft_epoch_before": 0, "draft_epoch_after": 1,
                                                "automatic_draft_write": False}
        result["evidence"]["manual_cpu_oracle"] = {"ollama_stopped": True, "history_ui_text": manual_text}
        result["decision"] = "READY_FOR_REVIEW"
        result["exact_stop_reason"] = "WP_S1_03_LIVE_ROUTE_COMPLETE"
    except StopProbe as exc:
        result["decision"] = "NO_GO"
        result["exact_stop_reason"] = exc.reason.split(":", 1)[0]
        result["evidence"].update(exc.evidence)
        result["evidence"]["failure"] = str(exc)
    except Exception as exc:
        result["decision"] = "BLOCKED"
        result["exact_stop_reason"] = "UNEXPECTED_HARNESS_EXCEPTION"
        result["evidence"]["failure"] = type(exc).__name__ + ":" + str(exc)
    finally:
        if base is not None:
            aliases = {str(base): "RUN_TEMP", str(Path(args.repo).resolve()): "REPO",
                       str(Path(args.sample).resolve()) if args.sample else "": "TEST_SOURCE/image-sample",
                       str(args.comfy_main): "COMFY_ROOT/main.py", str(args.comfy_python): "COMFY_PYTHON",
                       str(args.ollama_exe): "OLLAMA_EXE"}
            logs = {}
            for name in ("ollama.log", "comfy.log"):
                path = base / name
                if path.exists():
                    logs[name] = redact(path.read_text(encoding="utf-8", errors="replace"), aliases)
            result["evidence"]["service_logs"] = logs
        if driver is not None:
            result["public_submissions"] = driver.submissions
            try:
                cleanup = driver.cleanup()
                after = driver.target_hashes() if before is not None else None
                cleanup["target_integrity"] = "PASS" if before == after else "FAIL"
                cleanup["proven"] = cleanup["proven"] and before == after
                result["cleanup"] = cleanup
            except Exception as exc:
                result["cleanup"] = {"proven": False, "secondary_cleanup_failure": type(exc).__name__}
        if base is not None:
            try:
                shutil.rmtree(base, ignore_errors=False)
                result["cleanup"]["run_owned_temp_removed"] = not base.exists()
                result["cleanup"]["proven"] = result["cleanup"].get("proven", False) and not base.exists()
            except Exception as exc:
                result["cleanup"]["run_owned_temp_removed"] = False
                result["cleanup"]["secondary_temp_cleanup_failure"] = type(exc).__name__
                result["cleanup"]["proven"] = False
        if not result["cleanup"].get("proven", False) and result["decision"] == "READY_FOR_REVIEW":
            result["decision"] = "NO_GO"
            result["exact_stop_reason"] = "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN"
        result["authorization_status"] = "EXPIRED_TERMINAL"
    return (0 if result["decision"] == "READY_FOR_REVIEW" else 2), result


def self_check() -> dict:
    ui = json.loads((Path(__file__).parents[3] / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.ui.json").read_text())
    api = json.loads((Path(__file__).parents[3] / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json").read_text())
    classes = {node["type"] for node in ui["nodes"]}
    api_classes = {node["class_type"] for node in api.values()}
    if classes != api_classes or classes != {"LVWControlledImageInput", "LVWImagePromptBridge"}:
        raise StopProbe("WORKFLOW_UI_API_CLASS_MISMATCH")
    if api["2"]["inputs"]["image"] != ["1", 0] or ui["links"] != [[1, 1, 0, 2, 0, "IMAGE"]]:
        raise StopProbe("WORKFLOW_IMAGE_LINK_MISMATCH")
    return {"offline_only": True, "workflow_classes": sorted(classes), "live_actions": 0,
            "authorization": AUTHORIZATION_ID,
            "authorized_targets": {"comfy_main": AUTHORIZED_COMFY_MAIN, "comfy_python": AUTHORIZED_COMFY_PYTHON},
            "authorized_evidence_relative": AUTHORIZED_EVIDENCE_RELATIVE,
            "authorized_run_id": AUTHORIZED_RUN_ID,
            "budgets": {"image": 1, "model_calls": 1, "submissions": 8}}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="WP-S1-03 identity-bound one-shot live probe")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authorization-id", default="")
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--harness-sha256", default="")
    parser.add_argument("--harness-relative", default="reports/v0-s1/wp-s1-03-phase-a/live_probe.py")
    parser.add_argument("--repo", default=str(Path(__file__).parents[3]))
    parser.add_argument("--sample", default="")
    parser.add_argument("--sample-sha256", default=AUTHORIZED_SAMPLE_SHA256)
    parser.add_argument("--comfy-main", default="")
    parser.add_argument("--comfy-python", default="")
    parser.add_argument("--ollama-exe", default="")
    parser.add_argument("--powershell", default="powershell.exe")
    parser.add_argument("--temp-parent", default="")
    parser.add_argument("--evidence-root", default=AUTHORIZED_EVIDENCE_RELATIVE)
    parser.add_argument("--run-id", default=AUTHORIZED_RUN_ID)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.self_check:
        print(canonical_json(self_check()))
        return 0
    if not args.execute_live:
        print(canonical_json({"decision": "BLOCKED", "exact_stop_reason": "LIVE_FLAG_REQUIRED", "external_actions": 0}))
        return 2
    required = (args.candidate_sha, args.harness_sha256, args.sample, args.comfy_main, args.comfy_python,
                args.ollama_exe, args.temp_parent)
    if not all(required):
        print(canonical_json({"decision": "BLOCKED", "exact_stop_reason": "LIVE_ARGUMENT_REQUIRED", "external_actions": 0}))
        return 2
    try:
        validate_live_boundaries(args, reserve_evidence=True)
    except StopProbe as exc:
        print(canonical_json({"decision": "NO_GO", "exact_stop_reason": exc.reason, "external_actions": 0}))
        return 2
    code, result = execute(args)
    root = Path(args.evidence_root)
    aliases = {str(Path(args.repo).resolve()): "REPO", str(Path(args.sample).resolve()): "TEST_SOURCE/image-sample",
               str(Path(args.temp_parent).resolve()): "RUN_TEMP_PARENT"}
    sanitized = redact_value(result, aliases)
    (root / "run-summary.json").write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {path.name: sha256_file(path) for path in sorted(root.iterdir()) if path.name != "artifact-manifest.json"}
    (root / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(canonical_json({"decision": result["decision"], "exact_stop_reason": result["exact_stop_reason"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
