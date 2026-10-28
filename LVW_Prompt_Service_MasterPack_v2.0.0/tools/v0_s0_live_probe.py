#!/usr/bin/env python3
"""Reusable V0-S0 Windows-native public-Comfy live probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

MODEL = "gemma4:26b"
MODEL_DIGEST = "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"
IMAGE_HASH = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
VIDEO_HASH = "694a50bfb871faed6540a577b25c8a61e629035062a23f982099a6911ff22152"
GPU_STOP_MIB = 23552
PREFLIGHT_GPU_MAX_USED_MIB = 4096
PREFLIGHT_GPU_SAMPLE_TOLERANCE_MIB = 128


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, value) -> None:
    path.write_text(canonical(value), encoding="utf-8")


def parse_gpu_csv(raw: str):
    rows = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        values = [int(value.strip()) for value in line.split(",")]
        if len(values) != 3:
            raise ValueError("GPU_PREFLIGHT_NATIVE_PARSE_FAILED")
        rows.append({"total_mib": values[0], "used_mib": values[1], "free_mib": values[2]})
    if not rows:
        raise ValueError("GPU_PREFLIGHT_NATIVE_EMPTY")
    return rows


def evaluate_windows_preflight(native_gpu, wsl_gpu, processes, listeners, *, comfy_python_win, ollama_win):
    reasons = []
    if any(row["used_mib"] > PREFLIGHT_GPU_MAX_USED_MIB for row in native_gpu):
        reasons.append("GPU_PREFLIGHT_USED_ABOVE_4096_MIB")
    gpu_deltas = []
    if len(native_gpu) == len(wsl_gpu):
        for index, (native, wsl) in enumerate(zip(native_gpu, wsl_gpu)):
            gpu_deltas.append({
                "gpu_index": index,
                "total_matches": native["total_mib"] == wsl["total_mib"],
                "used_delta_mib": abs(native["used_mib"] - wsl["used_mib"]),
                "free_delta_mib": abs(native["free_mib"] - wsl["free_mib"]),
            })
    gpu_samples_match = (len(native_gpu) == len(wsl_gpu) and all(
        row["total_matches"] and row["used_delta_mib"] <= PREFLIGHT_GPU_SAMPLE_TOLERANCE_MIB and
        row["free_delta_mib"] <= PREFLIGHT_GPU_SAMPLE_TOLERANCE_MIB for row in gpu_deltas))
    if not gpu_samples_match:
        reasons.append("GPU_PREFLIGHT_WINDOWS_WSL_MISMATCH")
    target_processes = []
    comfy_norm = comfy_python_win.casefold()
    ollama_norm = ollama_win.casefold()
    for process in processes:
        executable = str(process.get("ExecutablePath") or "").casefold()
        name = str(process.get("Name") or "").casefold()
        command = str(process.get("CommandLine") or "").casefold()
        if executable == ollama_norm or name.startswith("ollama"):
            target_processes.append({"process_id": process.get("ProcessId"), "match_kind": "OLLAMA_TARGET"})
        elif executable == comfy_norm or (
                name in {"python.exe", "pythonw.exe"} and "comfyui" in command and "main.py" in command):
            target_processes.append({"process_id": process.get("ProcessId"), "match_kind": "COMFY_TARGET"})
    if target_processes:
        reasons.append("GPU_PREFLIGHT_TARGET_PROCESS_PRESENT")
    if listeners:
        reasons.append("GPU_PREFLIGHT_AUTHORIZED_PORT_LISTENER_PRESENT")
    return {
        "passed": not reasons,
        "maximum_allowed_used_mib": PREFLIGHT_GPU_MAX_USED_MIB,
        "windows_native_gpu": native_gpu,
        "wsl_gpu": wsl_gpu,
        "windows_wsl_sample_tolerance_mib": PREFLIGHT_GPU_SAMPLE_TOLERANCE_MIB,
        "windows_wsl_per_gpu_deltas": gpu_deltas,
        "windows_wsl_match": gpu_samples_match,
        "windows_process_count": len(processes),
        "target_process_count": len(target_processes),
        "target_processes": target_processes,
        "authorized_port_listeners": [{"local_port": row.get("LocalPort"),
                                        "owning_process": row.get("OwningProcess")} for row in listeners],
        "stop_reasons": reasons,
        "service_starts": 0,
    }


def history_primary_failure(history):
    messages = (history or {}).get("status", {}).get("messages", [])
    for message in messages:
        if not isinstance(message, list) or len(message) != 2 or message[0] != "execution_error":
            continue
        detail = message[1] if isinstance(message[1], dict) else {}
        raw = str(detail.get("exception_message") or "").strip()
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            parsed = {}
        code = parsed.get("code")
        subcode = parsed.get("details", {}).get("subcode") if isinstance(parsed.get("details"), dict) else None
        if code:
            label = code + (("/" + subcode) if subcode else "")
            message_text = parsed.get("message") or raw
            return {"code": code, "subcode": subcode, "failure": f"{label}: {message_text}"}
        return {"code": None, "subcode": None, "failure": raw or "COMFY_EXECUTION_ERROR"}
    return None


def evaluate_request_trace(log_text: str, *, planned_calls: int, terminal_ps_empty: bool,
                           final_cleanup_proven: bool):
    trace = []
    for index, line in enumerate(log_text.splitlines()):
        if 'POST     "/api/chat"' in line:
            kind = "visual_chat"
        elif 'POST     "/api/generate"' in line:
            kind = "keep_alive_zero_cleanup"
        else:
            continue
        status_match = re.search(r"\|\s*(\d{3})\s*\|", line)
        trace.append({"sequence": len(trace) + 1, "kind": kind, "log_line_index": index + 1,
                      "http_status": int(status_match.group(1)) if status_match else None,
                      "raw_log_line": line})
    chats = [item for item in trace if item["kind"] == "visual_chat"]
    cleanups = [item for item in trace if item["kind"] == "keep_alive_zero_cleanup"]
    cleanup_200_count = sum(item["http_status"] == 200 for item in cleanups)
    completion_order = [item["kind"] for item in trace]
    strict_order = completion_order == [kind for _ in range(len(chats))
                                        for kind in ("visual_chat", "keep_alive_zero_cleanup")]
    cleaned = (planned_calls > 0 and 0 < len(chats) <= planned_calls and
               len(chats) == len(cleanups) == cleanup_200_count and
               terminal_ps_empty and final_cleanup_proven)
    return {
        "raw_completion_order": trace,
        "visual_chat_count": len(chats),
        "cleanup_count": len(cleanups),
        "cleanup_http_200_count": cleanup_200_count,
        "planned_visual_and_cleanup_pairs": planned_calls,
        "observed_started_visual_calls": len(chats),
        "strict_completion_order_chat_then_cleanup": strict_order,
        "terminal_api_ps_empty": terminal_ps_empty,
        "final_cleanup_proven": final_cleanup_proven,
        "all_started_calls_cleaned": cleaned,
    }


def derive_cleanup_proven(*, owned_resources_absent: bool,
                          target_integrity_comparison: str,
                          secondary_cleanup_failures) -> bool:
    """Return the sole authoritative cleanup proof from terminal substates."""
    return (owned_resources_absent and
            target_integrity_comparison == "PASS" and
            not secondary_cleanup_failures)


def observable_check_statuses(*, reached_checks, identity_matched, preflight_passed,
                              no_cloud_passed, remote_passed, path_passed,
                              image_passed, video_passed, cleanup_proven,
                              owned_service_started, owned_resources_absent,
                              target_integrity_comparison):
    def status(name, passed):
        return "NOT_REACHED" if name not in reached_checks else ("PASS" if passed else "FAIL")

    cleanup_reached = (owned_service_started or not owned_resources_absent or
                       target_integrity_comparison != "NOT_REACHED")
    return {
        "harness_runtime_identity": status("harness_identity", identity_matched),
        "windows_native_service_preflight": status("service_preflight", preflight_passed),
        "windows_native_no_cloud_server_raw": status("no_cloud", no_cloud_passed),
        "pre_model_remote_tcp_gate": status("remote_tcp", remote_passed),
        "comfy_main_and_cwd_windows_path_conversion": status("path_conversion", path_passed),
        "public_comfy_image_route": status("image_route", image_passed),
        "public_comfy_video_route": status("video_route", video_passed),
        "cleanup_and_target_integrity": ("PASS" if cleanup_proven else "FAIL") if cleanup_reached else "NOT_REACHED",
    }


class Probe:
    def __init__(self, args):
        self.a = args
        self.root = Path.cwd().resolve()
        self.run_id = args.run_id
        self.candidate = args.candidate_sha
        self.authorization_commit = args.authorization_commit
        self.harness_candidate_sha = args.harness_candidate_sha
        self.ev = (self.root / (args.evidence_dir or ".")).resolve()
        self.receipt_path = (self.root / (args.receipt_path or "receipt.json")).resolve()
        if not args.self_check:
            self.ev.mkdir(parents=True, exist_ok=True)
        self.events = []
        self.commands = []
        self.attempts = {"image": [], "video": []}
        self.stop_event = threading.Event()
        self.resource_stop = False
        self.remote_stop = False
        self.samples = {}
        self.temp_u = None
        self.temp_w = None
        self.ollama_win = None
        self.ollama_proc = None
        self.comfy_proc = None
        self.ollama_pid = None
        self.ollama_wrapper_pid = None
        self.comfy_pid = None
        self.comfy_wrapper_pid = None
        self.comfy_main_win = None
        self.comfy_cwd_win = None
        self.comfy_python_win = None
        self.sampler = None
        self.resource_samples = []
        self.remote_samples = []
        self.cleanup = {}
        self.no_cloud_reported_true = False
        self.pre_model_gate = {}
        self.harness_identity = {}
        self.reached_checks = set()
        self.decision = "BLOCKED"
        self.exact_stop_reason = "HARNESS_NOT_COMPLETED"
        self.started = utc()
        self.aliases = {}

    def redact(self, text):
        text = str(text)
        pairs = sorted(((str(k), v) for k, v in self.aliases.items()), key=lambda x: -len(x[0]))
        for raw, alias in pairs:
            for variant in {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}:
                if variant:
                    text = re.sub(re.escape(variant), alias, text, flags=re.IGNORECASE)
        # Windows Python may reinterpret a WSL /mnt/<drive>/... argument as
        # C:/mnt/<drive>/...; collapse that malformed target-main form without
        # embedding any user or installation-specific absolute path.
        text = re.sub(r"(?i)[A-Z]:[\\/]+mnt[\\/]+[a-z][\\/]+(?:[^\\/\s\"]+[\\/]+)*ComfyUI[\\/]+main\.py",
                      "COMFY_ROOT/main.py", text)
        text = re.sub(r"(?i)USER_PROFILE[\\/]+\.ollama[\\/]+models[\\/]+blobs[\\/]+sha256-[0-9a-f]+",
                      "OLLAMA_MODEL_BLOB", text)
        text = re.sub(r"(?i)[A-Z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\\/\s\"]+", "USER_PROFILE", text)
        text = re.sub(r"/mnt/[a-z]/+Users/+[^/\s\"]+", "USER_PROFILE", text)
        text = re.sub(r"(?i)USER_PROFILE[\\/]+\.ollama[\\/]+models[\\/]+blobs[\\/]+sha256-[0-9a-f]+",
                      "OLLAMA_MODEL_BLOB", text)
        text = re.sub(r"(?i)\b[A-Z]:[\\/]+[^\s\"']+", "WINDOWS_ABSOLUTE_PATH", text)
        text = re.sub(r"(?i)/mnt/[a-z]/[^\s\"']+", "WSL_ABSOLUTE_PATH", text)
        return text

    def redact_value(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self.redact_value(item) for key, item in value.items()}
        return value

    def emit(self, name, value):
        write_json(self.ev / name, self.redact_value(value))

    def record(self, name, cmd, logical, timeout=120, cwd=None, env=None):
        start = utc()
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, check=False)
        rec = {"name": name, "logical_command": logical, "started_at": start, "ended_at": utc(),
               "exit_code": p.returncode, "output": self.redact(p.stdout)}
        self.commands.append(rec)
        return p

    def http(self, method, url, payload=None, timeout=10):
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                return r.status, raw
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def ps_json(self, script):
        utf8_script = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
                       "$OutputEncoding=[Console]::OutputEncoding;" + script)
        try:
            p = subprocess.run([self.a.powershell, "-NoProfile", "-Command", utf8_script,
                                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
        except Exception as error:
            return {"error_code": "WINDOWS_OWNER_ENUMERATION_FAILED",
                    "subcode": type(error).__name__, "exit_code": None}
        try:
            text = p.stdout.decode("utf-8", "strict").strip().lstrip("\ufeff")
        except UnicodeDecodeError as error:
            return {"error_code": "WINDOWS_OWNER_ENUMERATION_FAILED",
                    "subcode": "POWERSHELL_UTF8_DECODE_FAILED", "exit_code": p.returncode,
                    "raw_bytes": len(p.stdout), "raw_sha256": hashlib.sha256(p.stdout).hexdigest(),
                    "decode_start": error.start, "decode_end": error.end}
        if not text:
            return []
        try:
            result = json.loads(text)
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            return {"error_code": "WINDOWS_OWNER_ENUMERATION_FAILED",
                    "subcode": "POWERSHELL_JSON_PARSE_FAILED", "exit_code": p.returncode,
                    "raw_bytes": len(p.stdout), "raw_sha256": hashlib.sha256(p.stdout).hexdigest()}

    def listeners(self, ports=(8191, 11434)):
        joined = ",".join(map(str, ports))
        return self.ps_json("$x=Get-NetTCPConnection -State Listen -LocalPort " + joined +
                            " -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess;"
                            "$x | ConvertTo-Json -Compress")

    def windows_native_preflight(self):
        self.reached_checks.add("service_preflight")
        query = "--query-gpu=memory.total,memory.used,memory.free"
        native = self.record(
            "windows_native_gpu_preflight",
            [self.a.windows_nvidia_smi, query, "--format=csv,noheader,nounits"],
            "WINDOWS_NVIDIA_SMI query total,used,free before any service start",
        )
        wsl = self.record(
            "wsl_gpu_preflight",
            [self.a.wsl_nvidia_smi, query, "--format=csv,noheader,nounits"],
            "WSL_NVIDIA_SMI query total,used,free before any service start",
        )
        if native.returncode or wsl.returncode:
            self.emit("preflight-baseline.json", {"passed": False, "service_starts": 0,
                                                   "stop_reasons": ["GPU_PREFLIGHT_QUERY_FAILED"],
                                                   "windows_native_raw": native.stdout, "wsl_raw": wsl.stdout})
            raise RuntimeError("GPU_PREFLIGHT_QUERY_FAILED")
        self.emit("preflight-baseline.json", {"passed": False, "service_starts": 0,
                                               "status": "OWNER_ENUMERATION_IN_PROGRESS",
                                               "stop_reasons": ["WINDOWS_OWNER_ENUMERATION_NOT_COMPLETE"],
                                               "windows_native_raw": native.stdout, "wsl_raw": wsl.stdout})
        try:
            processes = self.ps_json(
                "$x=Get-CimInstance Win32_Process | Select-Object Name,ProcessId,ParentProcessId,ExecutablePath,CommandLine;"
                "$x | ConvertTo-Json -Compress"
            )
            listeners = self.listeners()
        except Exception as error:
            self.emit("preflight-baseline.json", {"passed": False, "service_starts": 0,
                                                   "stop_reasons": ["WINDOWS_OWNER_ENUMERATION_FAILED"],
                                                   "failure_subcode": type(error).__name__})
            raise RuntimeError("WINDOWS_OWNER_ENUMERATION_FAILED") from error
        if not isinstance(processes, list) or not isinstance(listeners, list):
            self.emit("preflight-baseline.json", {"passed": False, "service_starts": 0,
                                                   "stop_reasons": ["WINDOWS_OWNER_ENUMERATION_FAILED"],
                                                   "process_enumeration_error": (processes.get("error_code")
                                                                                 if isinstance(processes, dict) else None),
                                                   "listener_enumeration_error": (listeners.get("error_code")
                                                                                  if isinstance(listeners, dict) else None)})
            raise RuntimeError("WINDOWS_OWNER_ENUMERATION_FAILED")
        self.comfy_python_win = self.to_windows_path(Path(self.a.comfy_python))
        self.ollama_win = self.to_windows_path(Path(self.a.ollama))
        try:
            result = evaluate_windows_preflight(
                parse_gpu_csv(native.stdout), parse_gpu_csv(wsl.stdout), processes, listeners,
                comfy_python_win=self.comfy_python_win, ollama_win=self.ollama_win,
            )
        except ValueError as error:
            self.emit("preflight-baseline.json", {"passed": False, "service_starts": 0,
                                                   "stop_reasons": [str(error)],
                                                   "windows_native_raw": native.stdout, "wsl_raw": wsl.stdout})
            raise RuntimeError(str(error)) from error
        result["logical_commands"] = [
            "WINDOWS_NVIDIA_SMI query total,used,free",
            "WSL_NVIDIA_SMI query total,used,free",
            "POWERSHELL Get-CimInstance Win32_Process with command line",
            "POWERSHELL Get-NetTCPConnection listeners 8191,11434 with owning PID",
        ]
        self.emit("preflight-baseline.json", result)
        if not result["passed"]:
            raise RuntimeError("WINDOWS_NATIVE_PREFLIGHT_FAILED:" + ",".join(result["stop_reasons"]))
        return result

    def verify_harness_identity(self):
        self.reached_checks.add("harness_identity")
        repo_path = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s0_live_probe.py"
        spec = f"{self.harness_candidate_sha}:{repo_path}"
        started = utc()
        blob = subprocess.run(["git", "show", spec], cwd=self.root.parent, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, check=False)
        object_id = subprocess.run(["git", "rev-parse", spec], cwd=self.root.parent, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        executed_path = Path(__file__).resolve()
        blob_sha256 = hashlib.sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None
        file_sha256 = sha(executed_path)
        matched = (blob.returncode == 0 and object_id.returncode == 0 and blob_sha256 == file_sha256)
        self.commands.append({"name": "verify_harness_identity",
                              "logical_command": "git show/rev-parse HARNESS_CANDIDATE:tools/v0_s0_live_probe.py; sha256 executed __file__",
                              "started_at": started, "ended_at": utc(),
                              "exit_code": 0 if matched else 1})
        self.harness_identity = {
            "harness_candidate_commit": self.harness_candidate_sha,
            "git_blob_object_id": object_id.stdout.strip() if object_id.returncode == 0 else None,
            "git_blob_sha256": blob_sha256,
            "executed_file_sha256": file_sha256,
            "matched": matched,
            "service_starts": 0,
        }
        self.emit("harness-identity.json", self.harness_identity)
        if not matched:
            raise RuntimeError("HARNESS_IDENTITY_MISMATCH")
        return self.harness_identity

    def locate_sample(self, expected_hash, expected_bytes):
        matches = []
        for p in Path(self.a.test_source).rglob("*"):
            if p.is_file() and p.stat().st_size == expected_bytes and sha(p) == expected_hash:
                matches.append(p)
        if len(matches) != 1:
            raise RuntimeError(f"sample hash match count={len(matches)} expected=1")
        return matches[0]

    def target_integrity(self):
        files = [Path(self.a.comfy_root) / x for x in
                 ("main.py", "folder_paths.py", "nodes.py", "comfy/cli_args.py", "extra_model_paths.yaml")]
        files.append(Path(self.a.comfy_python))
        out = []
        for p in files:
            if p.exists():
                st = p.stat()
                out.append({"path": self.redact(p), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha(p)})
        return out

    def create_temp(self):
        name = "lvw-v0-s0-c06-" + uuid.uuid4().hex
        script = "$p=Join-Path ([IO.Path]::GetTempPath()) '" + name + "';New-Item -ItemType Directory -Path $p -ErrorAction Stop|Out-Null;[Console]::Write($p)"
        p = self.record("create_windows_temp", [self.a.powershell, "-NoProfile", "-Command", script],
                        "POWERSHELL create RUN_TEMP under Windows GetTempPath")
        if p.returncode:
            raise RuntimeError("failed to create Windows temp")
        self.temp_w = p.stdout.strip().lstrip("\ufeff")
        q = subprocess.run(["wslpath", "-u", self.temp_w], text=True, stdout=subprocess.PIPE, check=True)
        self.temp_u = Path(q.stdout.strip())
        self.aliases[self.temp_w] = "RUN_TEMP"
        self.aliases[str(self.temp_u)] = "RUN_TEMP"

    def copy_candidate(self):
        dest = self.temp_u / "custom_nodes/lvw_v0_bridge"
        dest.mkdir(parents=True)
        base = "LVW_Prompt_Service_MasterPack_v2.0.0/LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/"
        copied = []
        for name in ("__init__.py", "core.py", "nodes.py"):
            spec = f"{self.candidate}:{base}{name}"
            p = subprocess.run(["git", "show", spec], cwd=self.root.parent, stdout=subprocess.PIPE, check=False)
            if p.returncode:
                raise RuntimeError("cannot materialize sealed candidate")
            (dest / name).write_bytes(p.stdout)
            copied.append({"path": f"RUN_TEMP/custom_nodes/lvw_v0_bridge/{name}", "sha256": sha(dest / name)})
        self.emit("candidate-materialization.json", {"candidate_sha": self.candidate, "files": copied})

    def derive_media(self):
        inp = self.temp_u / "input"
        inp.mkdir(parents=True)
        image = self.samples["image"]
        video = self.samples["video"]
        p = self.record("derive_image", ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(image),
                         "-vf", "scale=384:384:force_original_aspect_ratio=decrease", "-frames:v", "1", str(inp / "image.png")],
                        "ffmpeg -i TEST_SOURCE/image-sample -vf scale<=384 -frames:v 1 RUN_TEMP/input/image.png")
        if p.returncode:
            raise RuntimeError("image derivation failed")
        probe = self.record("probe_video_frames", ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(video)],
                           "ffprobe count TEST_SOURCE/video-sample")
        n = int(probe.stdout.strip())
        # Four ordered bin centers; never duplicate endpoints as extra evidence.
        indices = [round((i + 0.5) * n / 4 - 0.5) for i in range(4)]
        expr = "+".join(f"eq(n\\,{i})" for i in indices)
        p = self.record("derive_video_frames", ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                         "-vf", f"select='{expr}',scale=384:384:force_original_aspect_ratio=decrease", "-vsync", "0",
                         str(inp / "frame-%02d.png")],
                        "ffmpeg -i TEST_SOURCE/video-sample -vf select=four_ordered_frames,scale<=384 RUN_TEMP/input/frame-%02d.png")
        frames = sorted(inp.glob("frame-*.png"))
        if p.returncode or len(frames) != 4:
            raise RuntimeError(f"video derivation produced {len(frames)} frames")
        from PIL import Image
        derived = []
        for pth in [inp / "image.png", *frames]:
            with Image.open(pth) as im:
                dims = list(im.size)
            if max(dims) > 384:
                raise RuntimeError("derived media dimension limit violated")
            derived.append({"alias": "RUN_TEMP/input/" + pth.name, "sha256": sha(pth), "bytes": pth.stat().st_size,
                            "dimensions": dims})
        self.emit("media-derivatives.json", {"source_hashes": {"image": IMAGE_HASH, "video": VIDEO_HASH},
                                              "frame_source_indices": indices, "derivatives": derived,
                                              "original_media_packaged": False})

    def wait_port(self, port, timeout=90):
        end = time.time() + timeout
        while time.time() < end:
            ls = self.listeners((port,))
            if isinstance(ls, list) and ls:
                return int(ls[0]["OwningProcess"])
            time.sleep(1)
        raise RuntimeError(f"port {port} did not listen")

    def sampler_loop(self):
        next_sample = time.monotonic()
        while not self.stop_event.is_set():
            delay = next_sample - time.monotonic()
            if delay > 0 and self.stop_event.wait(delay):
                break
            next_sample += 1.0
            stamp = utc()
            p = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
            gpu = []
            for line in p.stdout.splitlines():
                try:
                    used, total = [int(x.strip()) for x in line.split(",")]
                    gpu.append({"used_mib": used, "total_mib": total})
                    if used >= GPU_STOP_MIB:
                        self.resource_stop = True
                except Exception:
                    pass
            mem = {}
            try:
                for line in Path("/proc/meminfo").read_text().splitlines():
                    if line.startswith(("MemAvailable:", "MemTotal:")):
                        k, v = line.split(":", 1); mem[k] = int(v.split()[0]) // 1024
            except Exception:
                pass
            self.resource_samples.append({"at": stamp, "gpu": gpu, "host_ram_mib": mem})
            if self.ollama_pid:
                rows = self.ps_json("$x=Get-NetTCPConnection -OwningProcess " + str(self.ollama_pid) +
                                    " -ErrorAction SilentlyContinue | Select-Object State,LocalAddress,LocalPort,RemoteAddress,RemotePort;"
                                    "$x | ConvertTo-Json -Compress")
                self.remote_samples.append({"at": stamp, "owned_ollama_pid": self.ollama_pid, "connections": rows})
                if isinstance(rows, list):
                    for row in rows:
                        remote = str(row.get("RemoteAddress", ""))
                        rport = int(row.get("RemotePort") or 0)
                        if rport and remote not in {"127.0.0.1", "::1", "0.0.0.0", "::", ""}:
                            self.remote_stop = True
            # The next iteration targets an absolute one-second cadence.  Slow
            # Windows queries are visible as missed cadence, never concealed.

    def windows_wrapper_script(self):
        pid_file = self.temp_w.rstrip("\\/") + "\\ollama-wrapper-pid.txt"
        escaped_pid_file = pid_file.replace("'", "''")
        escaped_ollama = str(self.ollama_win).replace("'", "''")
        return (
            "$ErrorActionPreference='Stop';"
            "$env:OLLAMA_HOST='127.0.0.1:11434';"
            "$env:OLLAMA_NO_CLOUD='1';"
            "$env:NO_PROXY='127.0.0.1,localhost';"
            f"[IO.File]::WriteAllText('{escaped_pid_file}',[string]$PID);"
            f"& '{escaped_ollama}' serve; exit $LASTEXITCODE"
        )

    def read_wrapper_pid(self, timeout=30):
        path = self.temp_u / "ollama-wrapper-pid.txt"
        end = time.time() + timeout
        while time.time() < end:
            if path.exists() and path.read_text(encoding="utf-8").strip().isdigit():
                return int(path.read_text(encoding="utf-8").strip())
            time.sleep(0.25)
        raise RuntimeError("Windows wrapper PID was not recorded")

    def wait_for_no_cloud_raw(self, timeout=30):
        self.reached_checks.add("no_cloud")
        path = self.ev / "ollama-live.raw.log"
        end = time.time() + timeout
        while time.time() < end:
            text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
            if re.search(r"OLLAMA_NO_CLOUD:true", text) or re.search(r"Ollama cloud disabled:\s*true", text):
                self.no_cloud_reported_true = True
                return
            if re.search(r"OLLAMA_NO_CLOUD:false", text) or re.search(r"Ollama cloud disabled:\s*false", text):
                raise RuntimeError("OLLAMA_NO_CLOUD_NOT_REPORTED_TRUE")
            time.sleep(0.25)
        raise RuntimeError("OLLAMA_NO_CLOUD_TRUE_NOT_OBSERVED_IN_SERVER_RAW")

    def enforce_pre_model_network_gate(self):
        self.reached_checks.add("remote_tcp")
        gate_start = time.monotonic()
        start_index = len(self.remote_samples)
        while True:
            elapsed = time.monotonic() - gate_start
            samples = self.remote_samples[start_index:]
            if self.remote_stop:
                raise RuntimeError("PRE_MODEL_NON_LOOPBACK_REMOTE_TCP")
            if self.resource_stop:
                raise RuntimeError("PRE_MODEL_GPU_THRESHOLD_REACHED")
            if elapsed >= 10.0 and len(samples) >= 5:
                break
            if elapsed > 45:
                raise RuntimeError("PRE_MODEL_NETWORK_GATE_INSUFFICIENT_SAMPLES")
            time.sleep(0.1)
        self.pre_model_gate = {"passed": True, "minimum_seconds": 10, "observed_seconds": elapsed,
                               "minimum_samples": 5, "sample_count": len(samples),
                               "non_loopback_count": 0, "no_cloud_reported_true": self.no_cloud_reported_true}
        self.emit("pre-model-gate.json", self.pre_model_gate)

    def to_windows_path(self, path):
        converted = subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
        if not re.match(r"^[A-Za-z]:\\", converted) or "/mnt/" in converted.lower() or "\\mnt\\" in converted.lower():
            raise RuntimeError("COMFY_WINDOWS_PATH_CONVERSION_INVALID")
        return converted

    def prepare_comfy_windows_paths(self, *, save_evidence):
        self.reached_checks.add("path_conversion")
        self.comfy_main_win = self.to_windows_path(Path(self.a.comfy_root) / "main.py")
        self.comfy_cwd_win = self.to_windows_path(Path(self.a.comfy_root).parent)
        self.comfy_python_win = self.to_windows_path(Path(self.a.comfy_python))
        check = {
            "source_main_alias": "COMFY_ROOT/main.py",
            "source_cwd_alias": "COMFY_INSTALL_PARENT",
            "converted_main_alias": "COMFY_ROOT_WIN/main.py",
            "converted_cwd_alias": "COMFY_INSTALL_PARENT_WIN",
            "main_matches_windows_drive_pattern": bool(re.match(r"^[A-Za-z]:\\", self.comfy_main_win)),
            "cwd_matches_windows_drive_pattern": bool(re.match(r"^[A-Za-z]:\\", self.comfy_cwd_win)),
            "python_matches_windows_drive_pattern": bool(re.match(r"^[A-Za-z]:\\", self.comfy_python_win)),
            "converted_values_contain_wsl_mnt": any("/mnt/" in value.lower() or "\\mnt\\" in value.lower()
                                                   for value in (self.comfy_main_win, self.comfy_cwd_win, self.comfy_python_win)),
            "conversion_tool": "wslpath -w",
        }
        if not all((check["main_matches_windows_drive_pattern"], check["cwd_matches_windows_drive_pattern"],
                    check["python_matches_windows_drive_pattern"])) or check["converted_values_contain_wsl_mnt"]:
            raise RuntimeError("COMFY_WINDOWS_PATH_CONVERSION_SELF_CHECK_FAILED")
        if save_evidence:
            self.emit("comfy-path-conversion.json", check)
        return check

    def comfy_wrapper_script(self):
        pid_file = self.temp_w.rstrip("\\/") + "\\comfy-wrapper-pid.txt"
        quote = lambda value: str(value).replace("'", "''")
        args = ["-s", self.comfy_main_win, "--base-directory", self.temp_w, "--listen", "127.0.0.1",
                "--port", "8191", "--disable-auto-launch", "--disable-api-nodes", "--disable-all-custom-nodes",
                "--whitelist-custom-nodes", "lvw_v0_bridge"]
        args_literal = ",".join("'" + quote(value) + "'" for value in args)
        return ("$ErrorActionPreference='Stop';"
                f"[IO.File]::WriteAllText('{quote(pid_file)}',[string]$PID);"
                f"Set-Location -LiteralPath '{quote(self.comfy_cwd_win)}';"
                f"$comfyArgs=@({args_literal}); & '{quote(self.comfy_python_win)}' @comfyArgs; exit $LASTEXITCODE")

    def read_pid_file(self, name, timeout=30):
        path = self.temp_u / name
        end = time.time() + timeout
        while time.time() < end:
            if path.exists() and path.read_text(encoding="utf-8").strip().isdigit():
                return int(path.read_text(encoding="utf-8").strip())
            time.sleep(0.25)
        raise RuntimeError(f"Windows wrapper PID was not recorded: {name}")

    def start_services(self):
        env = os.environ.copy()
        env.update({"NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
        ollama_log = (self.ev / "ollama-live.raw.log").open("wb")
        self.ollama_win = subprocess.check_output(["wslpath", "-w", self.a.ollama], text=True).strip()
        wrapper_script = self.windows_wrapper_script()
        self.commands.append({"name": "start_ollama_windows_native_wrapper",
                              "logical_command": "POWERSHELL -NoProfile -Command set process OLLAMA_HOST=127.0.0.1:11434; set process OLLAMA_NO_CLOUD=1; set process NO_PROXY=127.0.0.1,localhost; write wrapper PID; OLLAMA_EXE serve",
                              "started_at": utc(), "exit_code": None})
        self.ollama_proc = subprocess.Popen([self.a.powershell, "-NoProfile", "-Command", wrapper_script],
                                            stdout=ollama_log, stderr=subprocess.STDOUT, env=env)
        self.ollama_wrapper_pid = self.read_wrapper_pid()
        self.ollama_pid = self.wait_port(11434, 60)
        if self.ollama_wrapper_pid == self.ollama_pid:
            raise RuntimeError("wrapper and listener PIDs unexpectedly identical")
        self.sampler = threading.Thread(target=self.sampler_loop, daemon=True)
        self.sampler.start()
        self.wait_for_no_cloud_raw()
        self.enforce_pre_model_network_gate()
        for endpoint, name in (("/api/version", "version"), ("/api/tags", "tags"), ("/api/ps", "ps_start")):
            status, raw = self.http("GET", "http://127.0.0.1:11434" + endpoint)
            self.emit(f"ollama-{name}.json", {"http_status": status, "raw_response": raw,
                                               "parsed": json.loads(raw) if raw else None})
        status, raw = self.http("POST", "http://127.0.0.1:11434/api/show", {"model": MODEL}, 30)
        parsed = json.loads(raw)
        self.emit("ollama-show.json", {"http_status": status, "request": {"model": MODEL},
                                        "raw_response": raw, "parsed": parsed})
        digest = None
        status2, tags_raw = self.http("GET", "http://127.0.0.1:11434/api/tags")
        for item in json.loads(tags_raw).get("models", []):
            if item.get("name") == MODEL:
                digest = item.get("digest")
        if status != 200 or digest != MODEL_DIGEST:
            raise RuntimeError(f"model digest mismatch status={status} digest={digest}")
        if self.remote_stop or self.resource_stop:
            raise RuntimeError("STOP_CONDITION_AFTER_MODEL_PREFLIGHT")
        self.prepare_comfy_windows_paths(save_evidence=True)
        comfy_log = (self.ev / "comfy-live.raw.log").open("wb")
        comfy_script = self.comfy_wrapper_script()
        self.commands.append({"name": "start_comfy_windows_path_wrapper", "logical_command":
                              "POWERSHELL write wrapper PID; Set-Location COMFY_INSTALL_PARENT_WIN; COMFY_PYTHON_WIN -s COMFY_ROOT_WIN/main.py --base-directory RUN_TEMP --listen 127.0.0.1 --port 8191 --disable-auto-launch --disable-api-nodes --disable-all-custom-nodes --whitelist-custom-nodes lvw_v0_bridge",
                              "started_at": utc(), "ended_at": None, "exit_code": None})
        self.comfy_proc = subprocess.Popen([self.a.powershell, "-NoProfile", "-Command", comfy_script],
                                           stdout=comfy_log, stderr=subprocess.STDOUT, env=env)
        self.comfy_wrapper_pid = self.read_pid_file("comfy-wrapper-pid.txt")
        self.comfy_pid = self.wait_port(8191, 120)
        end = time.time() + 60
        while time.time() < end:
            status, raw = self.http("GET", "http://127.0.0.1:8191/object_info", timeout=10)
            if status == 200:
                obj = json.loads(raw)
                public = {k: obj.get(k) for k in ("LoadImage", "ImageBatch", "LVWImagePromptBridge", "LVWVideoFramesPromptBridge")}
                self.emit("comfy-object-info.json", {"http_status": status, "raw_selected_public_object_info": public})
                if (all(public.values()) and public["LVWImagePromptBridge"].get("output_node") is True and
                        public["LVWVideoFramesPromptBridge"].get("output_node") is True):
                    return
            time.sleep(1)
        raise RuntimeError("Comfy object_info readiness/registration failed")

    def workflow(self, kind):
        common = {"model": MODEL, "user_instruction": "Describe only visible evidence for prompt assistance.",
                  "mode": "realistic", "timeout_seconds": 120}
        if kind == "image":
            return {"1": {"class_type": "LoadImage", "inputs": {"image": "image.png"}},
                    "2": {"class_type": "LVWImagePromptBridge", "inputs": {"image": ["1", 0], **common}}}, "2"
        wf = {}
        for i in range(4):
            wf[str(i + 1)] = {"class_type": "LoadImage", "inputs": {"image": f"frame-{i+1:02d}.png"}}
        wf["5"] = {"class_type": "ImageBatch", "inputs": {"image1": ["1", 0], "image2": ["2", 0]}}
        wf["6"] = {"class_type": "ImageBatch", "inputs": {"image1": ["5", 0], "image2": ["3", 0]}}
        wf["7"] = {"class_type": "ImageBatch", "inputs": {"image1": ["6", 0], "image2": ["4", 0]}}
        wf["8"] = {"class_type": "LVWVideoFramesPromptBridge", "inputs": {"frames": ["7", 0], **common}}
        return wf, "8"

    def oracle(self, kind, raw_text, suggestion_text):
        raw = json.loads(raw_text)
        suggestion = json.loads(suggestion_text)
        if kind == "image":
            envelopes = [raw]
            expected = 1
        else:
            envelopes = [json.loads(x) for x in raw.get("frame_raw_responses", [])]
            expected = 4
            if len(envelopes) != 4:
                raise ValueError("video raw lacks four ordered frame responses")
            motion = suggestion.get("technical", {}).get("camera_motion", "")
            if not isinstance(motion, str) or not motion.strip():
                raise ValueError("video suggestion has no camera_motion")
        for envelope in envelopes:
            if envelope.get("done") is not True or envelope.get("done_reason") != "stop":
                raise ValueError("model response not complete stop")
            content = json.loads(envelope["message"]["content"])
            if not content.get("observations"):
                raise ValueError("empty observations")
            instruction = "describe only visible evidence for prompt assistance"
            values = content.get("observations", []) + content.get("inferences", []) + content.get("unknowns", []) + [content.get("prompt", "")]
            norm = lambda x: " ".join(re.sub(r"[^\w]+", " ", x.casefold()).split())
            if any(norm(v) == instruction for v in values):
                raise ValueError("prompt echo")
        if not suggestion.get("domains", {}).get("observation"):
            raise ValueError("suggestion lacks observation")
        return {"pass": True, "envelope_count": len(envelopes), "expected_model_calls": expected,
                "semantic_observations_nonempty": True, "prompt_echo": False}

    def attempt(self, kind, number):
        self.reached_checks.add(kind + "_route")
        wf, out_node = self.workflow(kind)
        prompt_payload = {"prompt": wf, "client_id": self.run_id}
        rec = {"attempt": number, "kind": kind, "started_at": utc(), "route": "Comfy public /prompt",
               "prompt_payload": prompt_payload}
        status, raw = self.http("POST", "http://127.0.0.1:8191/prompt", prompt_payload, 30)
        rec["prompt_http_status"] = status
        rec["prompt_raw_response"] = raw
        if status != 200:
            rec.update({"ended_at": utc(), "pass": False, "failure": "PROMPT_POST_FAILED"})
            self.attempts[kind].append(rec); self.emit(f"attempt-{kind}-{number}.json", rec); return False
        prompt_id = json.loads(raw)["prompt_id"]
        rec["prompt_id"] = prompt_id
        end = time.time() + 720
        history = None
        while time.time() < end:
            if self.resource_stop or self.remote_stop:
                break
            hs, hr = self.http("GET", f"http://127.0.0.1:8191/history/{prompt_id}", timeout=15)
            if hs == 200:
                candidate = json.loads(hr)
                if prompt_id in candidate:
                    history = candidate[prompt_id]
                    break
            time.sleep(1)
        rec["history_http_status"] = 200 if history is not None else None
        rec["history"] = history
        try:
            primary = history_primary_failure(history)
            if primary:
                rec.update({"failure_code": primary["code"], "failure_subcode": primary["subcode"]})
                raise RuntimeError(primary["failure"])
            output = history["outputs"][out_node]["text"]
            raw_text, suggestion_text = output[0], output[1]
            rec["history_ui"] = {"raw_response": raw_text, "suggestion": suggestion_text}
            rec["oracle"] = self.oracle(kind, raw_text, suggestion_text)
            rec["pass"] = True
        except Exception as e:
            rec["pass"] = False
            rec["failure"] = str(e) if primary else type(e).__name__ + ": " + str(e)
        ps_observations = []
        for delay_seconds in (0, 5):
            if delay_seconds:
                time.sleep(delay_seconds)
            ps_status, ps_raw = self.http("GET", "http://127.0.0.1:11434/api/ps")
            ps_observations.append({"delay_seconds": delay_seconds, "http_status": ps_status,
                                    "raw_response": ps_raw, "parsed": json.loads(ps_raw)})
        rec["resource_release_observations"] = ps_observations
        if ps_observations[-1]["http_status"] != 200 or ps_observations[-1]["parsed"].get("models"):
            rec["pass"] = False
            rec["cleanup_failure"] = "RESOURCE_RELEASE_PENDING: /api/ps not empty at t+5s"
            rec.setdefault("failure", rec["cleanup_failure"])
        rec["ended_at"] = utc()
        self.attempts[kind].append(rec)
        self.emit(f"attempt-{kind}-{number}.json", rec)
        self.emit(f"ollama-ps-after-{kind}-{number}.json", {"observations": ps_observations})
        return rec["pass"]

    def stop_owned(self, pid, label):
        if not pid:
            return {"label": label, "pid": None, "stop_attempted": False}
        before = self.ps_json(f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; $p|Select-Object Id,ProcessName,Path|ConvertTo-Json -Compress")
        p = subprocess.run([self.a.powershell, "-NoProfile", "-Command",
                            f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
        time.sleep(2)
        after = self.ps_json(f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; $p|Select-Object Id,ProcessName,Path|ConvertTo-Json -Compress")
        return {"label": label, "pid": pid, "before": before, "stop_exit_code": p.returncode, "after": after}

    def settle_owned_popen(self, proc, label, failures):
        state = {"label": label, "assigned": proc is not None, "terminate_attempted": False,
                 "kill_attempted": False, "returncode": None, "exited": proc is None}
        if proc is None:
            return state

        def fail(code):
            detail = code + ":" + label
            if detail not in failures:
                failures.append(detail)
                self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fail("OWNED_POPEN_WAIT_TIMEOUT")
        except Exception:
            fail("OWNED_POPEN_WAIT_FAILED")
        try:
            running = proc.poll() is None
        except Exception:
            fail("OWNED_POPEN_POLL_FAILED")
            running = True
        if running:
            state["terminate_attempted"] = True
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                fail("OWNED_POPEN_TERMINATE_TIMEOUT")
            except Exception:
                fail("OWNED_POPEN_TERMINATE_FAILED")
            try:
                running = proc.poll() is None
            except Exception:
                fail("OWNED_POPEN_POLL_FAILED")
                running = True
        if running:
            state["kill_attempted"] = True
            try:
                proc.kill()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                fail("OWNED_POPEN_KILL_TIMEOUT")
            except Exception:
                fail("OWNED_POPEN_KILL_FAILED")
            try:
                running = proc.poll() is None
            except Exception:
                fail("OWNED_POPEN_POLL_FAILED")
                running = True
        if running:
            fail("OWNED_POPEN_STILL_RUNNING")
        else:
            try:
                state["returncode"] = proc.poll()
                state["exited"] = state["returncode"] is not None
            except Exception:
                fail("OWNED_POPEN_POLL_FAILED")
        return state

    def sanitize_logs(self):
        for stem in ("ollama-live", "comfy-live"):
            raw = self.ev / (stem + ".raw.log")
            if raw.exists():
                text = raw.read_text(encoding="utf-8", errors="replace")
                (self.ev / (stem + ".log")).write_text(self.redact(text), encoding="utf-8")
                raw.unlink()
            else:
                cooked = self.ev / (stem + ".log")
                if cooked.exists():
                    cooked.write_text(self.redact(cooked.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")

    def emit_request_trace(self):
        log = self.ev / "ollama-live.log"
        log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
        planned_pairs = sum((1 if item.get("kind") == "image" else 4) for values in self.attempts.values()
                            for item in values)
        ps_path = self.ev / "ollama-ps-final-before-stop.json"
        ps = json.loads(ps_path.read_text(encoding="utf-8")) if ps_path.exists() else {}
        terminal_ps_empty = ps.get("http_status") == 200 and not ps.get("parsed", {}).get("models")
        final_cleanup_proven = self.cleanup.get("proven", False)
        document = evaluate_request_trace(log_text, planned_calls=planned_pairs,
                                          terminal_ps_empty=terminal_ps_empty,
                                          final_cleanup_proven=final_cleanup_proven)
        observed_pairs = document["visual_chat_count"]
        document["video_four_ordered_single_image_calls"] = (not self.attempts["video"] or
                                                               observed_pairs >= 5 and document["all_started_calls_cleaned"])
        self.emit("ollama-request-trace.json", document)
        return document

    def manifest(self):
        files = []
        for p in sorted(self.ev.rglob("*")):
            if p.is_file() and p.name != "artifact-manifest.json":
                files.append({"path": p.relative_to(self.root).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)})
        write_json(self.ev / "artifact-manifest.json", {"schema_version": "lvw.artifact-manifest/1", "run_id": self.run_id,
                                                         "generated_at": utc(), "algorithm": "sha256", "files": files})

    def offline_self_check(self):
        self.temp_w = r"C:\Temp\RUN_TOKEN"
        self.ollama_win = r"C:\Authorized\ollama.exe"
        script = self.windows_wrapper_script()
        required = ["OLLAMA_HOST='127.0.0.1:11434'", "OLLAMA_NO_CLOUD='1'",
                    "NO_PROXY='127.0.0.1,localhost'", "ollama.exe' serve"]
        assert all(value in script for value in required)
        assert script.index("OLLAMA_NO_CLOUD='1'") < script.index("ollama.exe' serve")
        self.comfy_main_win = r"C:\ComfyUI\ComfyUI\main.py"
        self.comfy_cwd_win = r"C:\ComfyUI"
        self.comfy_python_win = r"C:\ComfyUI\python\python.exe"
        path_check = {"offline_fixture": True, "windows_paths": True}
        comfy_script = self.comfy_wrapper_script()
        assert self.comfy_main_win in comfy_script and self.comfy_cwd_win in comfy_script
        assert "Set-Location -LiteralPath" in comfy_script
        image, image_owner = self.workflow("image")
        video, video_owner = self.workflow("video")
        assert image_owner == "2" and image["2"]["class_type"] == "LVWImagePromptBridge"
        assert video_owner == "8" and video["8"]["class_type"] == "LVWVideoFramesPromptBridge"
        assert sum(node["class_type"] == "LoadImage" for node in video.values()) == 4
        assert self.redact_value({"escaped": "a\\\"b"}) == {"escaped": "a\\\"b"}
        assert self.redact(r"C:\\mnt\\c\\neutral\\ComfyUI\\main.py") == "COMFY_ROOT/main.py"
        clean = evaluate_windows_preflight(
            [{"total_mib": 24564, "used_mib": 1530, "free_mib": 22609}],
            [{"total_mib": 24564, "used_mib": 1530, "free_mib": 22609}], [], [],
            comfy_python_win=self.comfy_python_win, ollama_win=self.ollama_win)
        assert clean["passed"] and clean["service_starts"] == 0
        print(canonical({"self_check": "PASS", "service_started": False,
                         "windows_native_wrapper_env_order": "PASS", "image_owner": image_owner,
                         "video_owner": video_owner, "video_load_image_count": 4,
                         "comfy_path_conversion": path_check}), end="")
        return 0

    def run(self):
        pre_integrity = None
        primary_stop_reason = None
        try:
            self.aliases.update({str(Path(self.a.comfy_root).resolve()): "COMFY_ROOT",
                                 str(Path(self.a.comfy_python).resolve()): "COMFY_PYTHON",
                                 str(Path(self.a.ollama).resolve()): "OLLAMA_EXE",
                                 str(Path(self.a.test_source).resolve()): "TEST_SOURCE"})
            head = self.record("verify_authorization_commit", ["git", "cat-file", "-t", self.authorization_commit],
                               "git cat-file -t AUTHORIZATION_COMMIT", cwd=self.root.parent)
            cand = self.record("verify_candidate_commit", ["git", "cat-file", "-t", self.candidate],
                               "git cat-file -t CANDIDATE_SHA", cwd=self.root.parent)
            if head.returncode or cand.returncode:
                raise RuntimeError("authorization or candidate commit unavailable")
            self.verify_harness_identity()
            self.windows_native_preflight()
            self.samples = {"image": self.locate_sample(IMAGE_HASH, 404368), "video": self.locate_sample(VIDEO_HASH, 438707)}
            self.emit("sample-verification.json", {k: {"alias": f"TEST_SOURCE/{k}-sample", "sha256": sha(v), "bytes": v.stat().st_size}
                                                   for k, v in self.samples.items()})
            pre_integrity = self.target_integrity()
            self.create_temp(); self.copy_candidate(); self.derive_media(); self.start_services()
            for kind in ("image", "video"):
                if self.resource_stop or self.remote_stop:
                    break
                route_pass = self.attempt(kind, 1)
                if not route_pass or self.resource_stop or self.remote_stop:
                    break
            passes = all(any(a.get("pass") for a in self.attempts[k]) for k in ("image", "video"))
            if self.resource_stop:
                self.decision = "NO_GO"; self.exact_stop_reason = "GPU_MEMORY_REACHED_OR_EXCEEDED_23552_MIB"
            elif self.remote_stop:
                self.decision = "NO_GO"; self.exact_stop_reason = "OWNED_OLLAMA_PID_NON_LOOPBACK_REMOTE_CONNECTION"
            elif passes:
                self.decision = "READY_FOR_REVIEW"; self.exact_stop_reason = "AUTHORIZED_LIVE_PROBE_COMPLETE"
            elif (self.attempts["video"] and
                  "PROMPT_ECHO" in canonical(self.attempts["video"][-1].get("history", {}))):
                self.decision = "NO_GO"; self.exact_stop_reason = "VIDEO_SEMANTIC_ORACLE_PROMPT_ECHO"
            else:
                self.decision = "NO_GO"; self.exact_stop_reason = "PUBLIC_COMFY_ROUTE_FAILED_WITHIN_ATTEMPT_BUDGET"
        except Exception as e:
            reason = str(e)
            mandatory_no_go = ("NO_CLOUD" in reason or "NON_LOOPBACK" in reason or
                               "GPU_THRESHOLD" in reason or "GPU_PREFLIGHT" in reason or
                               "STOP_CONDITION" in reason)
            self.decision = "NO_GO" if mandatory_no_go else "BLOCKED"
            self.exact_stop_reason = reason if mandatory_no_go or reason in {
                "WINDOWS_OWNER_ENUMERATION_FAILED", "HARNESS_IDENTITY_MISMATCH"} else type(e).__name__ + ": " + reason
            primary_stop_reason = self.exact_stop_reason
            self.events.append({"at": utc(), "event": "terminal_exception", "detail": self.exact_stop_reason})
        finally:
            if self.ollama_pid:
                try:
                    s, r = self.http("GET", "http://127.0.0.1:11434/api/ps", timeout=10)
                    self.emit("ollama-ps-final-before-stop.json", {"http_status": s, "raw_response": r,
                                                                    "parsed": json.loads(r)})
                except Exception as e:
                    self.events.append({"at": utc(), "event": "final_ps_error", "detail": str(e)})
            self.stop_event.set()
            if self.sampler:
                self.sampler.join(timeout=5)
            stops = [self.stop_owned(self.comfy_pid, "owned_comfy_listener"),
                     self.stop_owned(self.comfy_wrapper_pid, "owned_comfy_windows_wrapper"),
                     self.stop_owned(self.ollama_pid, "owned_ollama_listener"),
                     self.stop_owned(self.ollama_wrapper_pid, "owned_windows_wrapper")]
            secondary_cleanup_failures = []
            popen_states = [self.settle_owned_popen(self.comfy_proc, "owned_comfy_popen",
                                                    secondary_cleanup_failures),
                            self.settle_owned_popen(self.ollama_proc, "owned_ollama_popen",
                                                    secondary_cleanup_failures)]
            try:
                final_ports = self.listeners()
                if not isinstance(final_ports, list):
                    raise RuntimeError("FINAL_PORT_ENUMERATION_INVALID")
            except Exception as error:
                detail = self.redact("FINAL_PORT_ENUMERATION_FAILED: " + type(error).__name__ + ": " + str(error))
                secondary_cleanup_failures.append(detail)
                self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})
                final_ports = {"error_code": "FINAL_PORT_ENUMERATION_FAILED"}
            try:
                post_integrity = self.target_integrity()
            except Exception as error:
                detail = self.redact("TARGET_INTEGRITY_CAPTURE_FAILED: " + type(error).__name__ + ": " + str(error))
                secondary_cleanup_failures.append(detail)
                self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})
                post_integrity = None
            integrity_equal = pre_integrity is not None and pre_integrity == post_integrity
            try:
                exists_before = bool(self.temp_u and self.temp_u.exists())
            except Exception as error:
                detail = self.redact("RUN_TEMP_STATE_FAILED: " + type(error).__name__ + ": " + str(error))
                secondary_cleanup_failures.append(detail)
                self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})
                exists_before = True
            temp_remove = {"attempted": bool(self.temp_w), "exists_before": exists_before}
            if self.temp_w:
                try:
                    p = subprocess.run([self.a.powershell, "-NoProfile", "-Command",
                                        "Remove-Item -LiteralPath '" + self.temp_w.replace("'", "''") + "' -Recurse -Force -ErrorAction SilentlyContinue"],
                                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=60)
                    temp_remove.update({"exit_code": p.returncode, "output": self.redact(p.stdout)})
                except Exception as error:
                    detail = self.redact("RUN_TEMP_REMOVAL_FAILED: " + type(error).__name__ + ": " + str(error))
                    secondary_cleanup_failures.append(detail)
                    self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})
                    temp_remove.update({"exit_code": None, "error_code": "RUN_TEMP_REMOVAL_FAILED"})
            try:
                temp_remove["exists_after"] = bool(self.temp_u and self.temp_u.exists())
            except Exception as error:
                detail = self.redact("RUN_TEMP_FINAL_STATE_FAILED: " + type(error).__name__ + ": " + str(error))
                secondary_cleanup_failures.append(detail)
                self.events.append({"at": utc(), "event": "secondary_cleanup_failure", "detail": detail})
                temp_remove["exists_after"] = True
            owned_service_started = any((self.ollama_proc, self.comfy_proc, self.ollama_pid,
                                         self.ollama_wrapper_pid, self.comfy_pid, self.comfy_wrapper_pid))
            resource_cleanup_failures = any(detail.startswith(("FINAL_PORT_", "RUN_TEMP_"))
                                            for detail in secondary_cleanup_failures)
            integrity_capture_failed = any(detail.startswith("TARGET_INTEGRITY_CAPTURE_FAILED")
                                           for detail in secondary_cleanup_failures)
            owned_resources_absent = (isinstance(final_ports, list) and not final_ports and
                                      not temp_remove["exists_after"] and
                                      all(not stop.get("after") for stop in stops) and
                                      all(state["exited"] for state in popen_states) and
                                      not resource_cleanup_failures)
            target_integrity_comparison = ("FAIL" if integrity_capture_failed else
                                           "NOT_REACHED" if pre_integrity is None else
                                           "PASS" if integrity_equal else "FAIL")
            cleanup_proven = derive_cleanup_proven(
                owned_resources_absent=owned_resources_absent,
                target_integrity_comparison=target_integrity_comparison,
                secondary_cleanup_failures=secondary_cleanup_failures,
            )
            self.cleanup = {"owned_process_stops": stops, "owned_popen_terminal_states": popen_states,
                            "final_authorized_port_listeners": final_ports,
                            "target_integrity_pre": pre_integrity, "target_integrity_post": post_integrity,
                            "target_integrity_equal": integrity_equal, "run_temp_removal": temp_remove,
                            "owned_resources_absent": owned_resources_absent,
                            "target_integrity_comparison": target_integrity_comparison,
                            "secondary_cleanup_failures": secondary_cleanup_failures,
                            "proven": cleanup_proven}
            if not self.cleanup["proven"]:
                if primary_stop_reason:
                    self.events.append({"at": utc(), "event": "secondary_cleanup_failure",
                                        "detail": "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN"})
                else:
                    self.decision = "NO_GO"; self.exact_stop_reason = "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN"
            self.emit("commands.json", {"commands": self.commands})
            self.emit("events.json", {"events": self.events})
            self.emit("resource-samples.json", {"gpu_stop_threshold_mib": GPU_STOP_MIB, "samples": self.resource_samples})
            self.emit("owned-ollama-remote-tcp.json", {"non_loopback_seen": self.remote_stop, "samples": self.remote_samples})
            if not self.pre_model_gate:
                self.pre_model_gate = {"passed": False, "minimum_seconds": 10, "minimum_samples": 5,
                                       "sample_count": len(self.remote_samples),
                                       "non_loopback_seen": self.remote_stop,
                                       "no_cloud_reported_true": self.no_cloud_reported_true,
                                       "status": ("FAIL" if {"no_cloud", "remote_tcp"} & self.reached_checks
                                                  else "NOT_REACHED"),
                                       "stop_reason": self.exact_stop_reason}
                self.emit("pre-model-gate.json", self.pre_model_gate)
            self.emit("cleanup.json", self.cleanup)
            self.sanitize_logs()
            request_trace_document = self.emit_request_trace()
            if any(self.attempts.values()) and not request_trace_document["all_started_calls_cleaned"]:
                if primary_stop_reason:
                    self.events.append({"at": utc(), "event": "secondary_cleanup_failure",
                                        "detail": "OLLAMA_REQUEST_CLEANUP_CORRELATION_FAILED"})
                    self.emit("events.json", {"events": self.events})
                else:
                    self.decision = "NO_GO"
                    self.exact_stop_reason = "OLLAMA_REQUEST_CLEANUP_CORRELATION_FAILED"
            summary = {"schema_version": "lvw.live-probe/1", "run_id": self.run_id, "candidate_sha": self.candidate,
                       "authorization_commit": self.authorization_commit, "started_at": self.started, "ended_at": utc(),
                       "decision": self.decision, "stage_pass_claim": False, "exact_stop_reason": self.exact_stop_reason,
                       "effective_attempts": {k: len(v) for k, v in self.attempts.items()},
                       "attempt_results": {k: [a.get("pass", False) for a in v] for k, v in self.attempts.items()},
                       "resource_stop": self.resource_stop, "non_loopback_remote_seen": self.remote_stop,
                       "no_cloud_reported_true": self.no_cloud_reported_true,
                       "pre_model_gate": self.pre_model_gate,
                       "cleanup_proven": self.cleanup["proven"]}
            self.emit("run-summary.json", summary)
            self.manifest()
            ev_rel = self.ev.relative_to(self.root).as_posix().rstrip("/") + "/"
            trace_refs = [ev_rel + f"attempt-{kind}-1.json" for kind in ("image", "video")
                          if (self.ev / f"attempt-{kind}-1.json").exists()]
            production_status = ("PUBLIC_COMFY_IMAGE_AND_VIDEO_TRACE_COMPLETE_READY_FOR_REVIEW"
                                 if self.decision == "READY_FOR_REVIEW" else
                                 "NOT_RUN_STOP_CONDITION_BEFORE_COMFY_START" if not trace_refs else
                                 "PARTIAL_OR_FAILED_PUBLIC_COMFY_TRACE")
            request_trace = json.loads((self.ev / "ollama-request-trace.json").read_text(encoding="utf-8"))
            correction_files = sorted(p.relative_to(self.root).as_posix() for p in self.ev.iterdir() if p.is_file())
            receipt_rel = self.receipt_path.relative_to(self.root).as_posix()
            preflight_path = self.ev / "preflight-baseline.json"
            try:
                preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.exists() else {
                    "passed": False, "status": "NOT_REACHED", "stop_reasons": [self.exact_stop_reason]}
            except (OSError, json.JSONDecodeError) as error:
                preflight = {"passed": False, "status": "ARTIFACT_UNREADABLE",
                             "stop_reasons": ["WINDOWS_OWNER_ENUMERATION_FAILED"],
                             "failure_subcode": type(error).__name__}
            check_statuses = observable_check_statuses(
                reached_checks=self.reached_checks,
                identity_matched=self.harness_identity.get("matched", False),
                preflight_passed=preflight.get("passed", False),
                no_cloud_passed=self.no_cloud_reported_true,
                remote_passed=self.pre_model_gate.get("passed", False),
                path_passed=(self.ev / "comfy-path-conversion.json").exists(),
                image_passed=any(x.get("pass") for x in self.attempts["image"]),
                video_passed=any(x.get("pass") for x in self.attempts["video"]),
                cleanup_proven=self.cleanup["proven"],
                owned_service_started=bool(owned_service_started),
                owned_resources_absent=owned_resources_absent,
                target_integrity_comparison=target_integrity_comparison,
            )
            raw_refs = [ev_rel + name for name in
                        ("ollama-live.log", "comfy-live.log", "ollama-version.json", "ollama-tags.json",
                         "ollama-show.json", "ollama-ps_start.json", "ollama-ps-final-before-stop.json",
                         "owned-ollama-remote-tcp.json", "resource-samples.json", "pre-model-gate.json")
                        if (self.ev / name).exists()]
            receipt = {
                "schema_version": "lvw.implementation-receipt/1", "spec_version": self.a.spec_version,
                "project_id": "lvw-prompt-service", "stage_id": "V0-S0", "workpack_id": self.a.workpack_id,
                "run_id": self.run_id, "implementation_owner_role": "codex_isolated_implementer",
                "implementation_session": "/root/s0_rerun_implementer", "candidate_sha": self.candidate,
                "authorization_commit": self.authorization_commit,
                "harness_candidate_sha": self.harness_candidate_sha,
                "harness_identity": self.harness_identity,
                "evidence_commit": "0000000000000000000000000000000000000000",
                "evidence_commit_status": "PENDING_ROOT_SEALING",
                "acceptance_hash": "78b158e135be4da756e27ced9f57c74e78feb926bcaf95eda2e2a6992c9a7b42",
                "acceptance_hash_binding": {"algorithm": "sha256", "target": "sorted fixed acceptance IDs V0-A01,V0-A02,V0-A09,V0-A10 joined by LF with a trailing LF",
                                            "source": ".agent-governance/stages/V0-S0/04-acceptance-matrix.md"},
                "gate_version": "lvw-gate/1", "decision": self.decision, "stage_pass_claim": False,
                "exact_stop_reason": self.exact_stop_reason,
                "changed_files": correction_files + [receipt_rel], "contract_changes": "none",
                "target_configuration_changes": "none",
                "environment": {"ollama_start": "Windows-native PowerShell per-process environment wrapper",
                                "service_preflight_gpu_max_used_mib": PREFLIGHT_GPU_MAX_USED_MIB,
                                "required_no_cloud_observed": self.no_cloud_reported_true,
                                "comfy_main_and_cwd_conversion": "wslpath -w with Windows-drive-pattern and no-/mnt self-check",
                                "comfy_bind": "127.0.0.1:8191", "ollama_endpoint": "http://127.0.0.1:11434",
                                "model": MODEL, "model_digest": MODEL_DIGEST},
                "effective_attempts": {k: len(v) for k, v in self.attempts.items()},
                "live_route_counts": {k: {"pass": sum(bool(x.get("pass")) for x in v), "total": len(v)}
                                      for k, v in self.attempts.items()},
                "test_counts": {"denominator": 4, "pass": 0, "fail": 0, "blocked": 0, "skipped": 0, "not_run": 4},
                "product_acceptance": {"V0-A01": "NOT_RUN", "V0-A02": "NOT_RUN", "V0-A09": "NOT_RUN", "V0-A10": "NOT_RUN"},
                "production_path_status": production_status, "public_end_to_end_trace_refs": trace_refs,
                "pre_model_gate": self.pre_model_gate,
                "resource": {"gpu_stop_threshold_mib": GPU_STOP_MIB,
                             "peak_gpu_used_mib": max((g["used_mib"] for s in self.resource_samples for g in s["gpu"]), default=None),
                             "minimum_host_available_ram_mib": min((s["host_ram_mib"].get("MemAvailable") for s in self.resource_samples if s["host_ram_mib"].get("MemAvailable") is not None), default=None)},
                "network": {"owned_ollama_non_loopback_remote_seen": self.remote_stop,
                            "evidence": ev_rel + "owned-ollama-remote-tcp.json"},
                "external_actions": {"ollama_process_starts": int(self.ollama_proc is not None),
                                     "comfyui_process_starts": int(self.comfy_proc is not None),
                                     "model_calls": request_trace["visual_chat_count"], "downloads_or_upgrades": 0,
                                     "target_install_writes": 0, "visible_browser_runs": 0, "external_cost": 0},
                "cleanup": {"proven": self.cleanup["proven"],
                            "owned_resources_absent": owned_resources_absent,
                            "target_integrity_comparison": target_integrity_comparison,
                            "details": ev_rel + "cleanup.json"},
                "check_results": [
                    {"check": name, "status": check_statuses[name], **(
                        {"details": self.harness_identity} if name == "harness_runtime_identity" else
                        {"details": preflight} if name == "windows_native_service_preflight" else {})}
                    for name in check_statuses],
                "artifact_manifest": ev_rel + "artifact-manifest.json",
                "artifact_refs": [ev_rel + name for name in
                                  ("run-summary.json", "cleanup.json", "preflight-baseline.json", "pre-model-gate.json",
                                   "harness-identity.json", "comfy-path-conversion.json", "owned-ollama-remote-tcp.json", "resource-samples.json",
                                   "ollama-request-trace.json", "artifact-manifest.json")
                                  if (self.ev / name).exists()],
                "raw_artifact_refs": raw_refs,
                "risks": ["Live semantic output remains model- and sample-specific; this receipt is not a Stage PASS.",
                          "The four fixed product acceptance cases remain NOT_RUN."]}
            write_json(self.receipt_path, receipt)
        return 0 if self.decision == "READY_FOR_REVIEW" else 2


def main():
    p = argparse.ArgumentParser(description="Reusable bounded V0-S0 live probe")
    p.add_argument("--run-id"); p.add_argument("--candidate-sha"); p.add_argument("--authorization-commit")
    p.add_argument("--harness-candidate-sha")
    p.add_argument("--evidence-dir"); p.add_argument("--receipt-path")
    p.add_argument("--spec-version", default="2.4.0"); p.add_argument("--workpack-id", default="WP-S0-20")
    p.add_argument("--comfy-root"); p.add_argument("--comfy-python")
    p.add_argument("--ollama"); p.add_argument("--test-source")
    p.add_argument("--powershell", default="powershell.exe")
    p.add_argument("--windows-nvidia-smi", default="nvidia-smi.exe")
    p.add_argument("--wsl-nvidia-smi", default="nvidia-smi")
    p.add_argument("--self-check", action="store_true")
    args = p.parse_args()
    required = ("run_id", "candidate_sha", "authorization_commit", "harness_candidate_sha", "evidence_dir", "receipt_path",
                "comfy_root", "comfy_python", "ollama", "test_source")
    if not args.self_check:
        missing = [name for name in required if not getattr(args, name)]
        if missing:
            p.error("live mode requires: " + ", ".join("--" + name.replace("_", "-") for name in missing))
    probe = Probe(args)
    if args.self_check:
        return probe.offline_self_check()
    return probe.run()


if __name__ == "__main__":
    sys.exit(main())


