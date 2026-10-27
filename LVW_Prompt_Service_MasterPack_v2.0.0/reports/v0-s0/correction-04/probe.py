#!/usr/bin/env python3
"""WP-S0-10 Windows-native no-cloud public-Comfy live probe."""

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

RUN_ID = "v0-s0-correction-04-live-20261027-01"
CANDIDATE = "078b51aab02fbfbcfd0efcfc7d38a2c9c6381f68"
AUTHORIZATION_COMMIT = "7de2cc5896c8fea198701afbdcd45d45f728b87a"
MODEL = "gemma4:26b"
MODEL_DIGEST = "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"
IMAGE_HASH = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
VIDEO_HASH = "694a50bfb871faed6540a577b25c8a61e629035062a23f982099a6911ff22152"
GPU_STOP_MIB = 23552


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


class Probe:
    def __init__(self, args):
        self.a = args
        self.root = Path.cwd().resolve()
        self.ev = (self.root / "reports/v0-s0/correction-04").resolve()
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
        self.sampler = None
        self.resource_samples = []
        self.remote_samples = []
        self.cleanup = {}
        self.no_cloud_reported_true = False
        self.pre_model_gate = {}
        self.decision = "BLOCKED"
        self.exact_stop_reason = "HARNESS_NOT_COMPLETED"
        self.started = utc()
        self.aliases = {}

    def redact(self, text):
        text = str(text).replace("\\", "/")
        pairs = sorted(((str(k).replace("\\", "/"), v) for k, v in self.aliases.items()), key=lambda x: -len(x[0]))
        for raw, alias in pairs:
            if raw:
                text = text.replace(raw, alias)
                text = text.replace(raw.lower(), alias)
        # Windows Python may reinterpret a WSL /mnt/<drive>/... argument as
        # C:/mnt/<drive>/...; collapse that malformed target-main form without
        # embedding any user or installation-specific absolute path.
        text = re.sub(r"(?i)[A-Z]:/+mnt/+[a-z]/+(?:[^/\s\"]+/+)*ComfyUI/+main\.py",
                      "COMFY_ROOT/main.py", text)
        text = re.sub(r"(?i)[A-Z]:/+(?:Users|Documents and Settings)/+[^/\s\"]+", "USER_PROFILE", text)
        text = re.sub(r"/mnt/[a-z]/+Users/+[^/\s\"]+", "USER_PROFILE", text)
        text = re.sub(r"(?i)(?:[A-Z]:)?/+[^\s\"]*?/+\.ollama/+models/+blobs/+sha256-[0-9a-f]+", "OLLAMA_MODEL_BLOB", text)
        text = re.sub(r"(?i)USER_PROFILE/+\.ollama/+models/+blobs/+sha256-[0-9a-f]+",
                      "OLLAMA_MODEL_BLOB", text)
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
        p = subprocess.run([self.a.powershell, "-NoProfile", "-Command", script], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
        text = p.stdout.strip().lstrip("\ufeff")
        if not text:
            return []
        try:
            result = json.loads(text)
            return result if isinstance(result, list) else [result]
        except json.JSONDecodeError:
            return {"parse_error": self.redact(text), "exit_code": p.returncode}

    def listeners(self, ports=(8191, 11434)):
        joined = ",".join(map(str, ports))
        return self.ps_json("$x=Get-NetTCPConnection -State Listen -LocalPort " + joined +
                            " -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess;"
                            "$x | ConvertTo-Json -Compress")

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
        name = "lvw-v0-s0-c03-" + uuid.uuid4().hex
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
            spec = f"{CANDIDATE}:{base}{name}"
            p = subprocess.run(["git", "show", spec], cwd=self.root.parent, stdout=subprocess.PIPE, check=False)
            if p.returncode:
                raise RuntimeError("cannot materialize sealed candidate")
            (dest / name).write_bytes(p.stdout)
            copied.append({"path": f"RUN_TEMP/custom_nodes/lvw_v0_bridge/{name}", "sha256": sha(dest / name)})
        self.emit("candidate-materialization.json", {"candidate_sha": CANDIDATE, "files": copied})

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
        comfy_log = (self.ev / "comfy-live.raw.log").open("wb")
        cmd = [self.a.comfy_python, "-s", str(Path(self.a.comfy_root) / "main.py"), "--base-directory", self.temp_w,
               "--listen", "127.0.0.1", "--port", "8191", "--disable-auto-launch", "--disable-api-nodes",
               "--disable-all-custom-nodes", "--whitelist-custom-nodes", "lvw_v0_bridge"]
        self.commands.append({"name": "start_comfy", "logical_command":
                              "COMFY_PYTHON -s COMFY_ROOT/main.py --base-directory RUN_TEMP --listen 127.0.0.1 --port 8191 --disable-auto-launch --disable-api-nodes --disable-all-custom-nodes --whitelist-custom-nodes lvw_v0_bridge",
                              "started_at": utc(), "ended_at": None, "exit_code": None})
        self.comfy_proc = subprocess.Popen(cmd, cwd=str(Path(self.a.comfy_root).parent), stdout=comfy_log, stderr=subprocess.STDOUT, env=env)
        self.comfy_pid = self.wait_port(8191, 120)
        end = time.time() + 60
        while time.time() < end:
            status, raw = self.http("GET", "http://127.0.0.1:8191/object_info", timeout=10)
            if status == 200:
                obj = json.loads(raw)
                public = {k: obj.get(k) for k in ("LoadImage", "ImageBatch", "LVWImagePromptBridge", "LVWVideoFramesPromptBridge")}
                self.emit("comfy-object-info.json", {"http_status": status, "raw_selected_public_object_info": public})
                if all(public.values()) and public["LVWImagePromptBridge"].get("output_node") is True:
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
            motion = suggestion.get("technical", {}).get("camera_motion", [])
            if not isinstance(motion, list) or not motion:
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
        wf, out_node = self.workflow(kind)
        prompt_payload = {"prompt": wf, "client_id": RUN_ID}
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
            output = history["outputs"][out_node]["text"]
            raw_text, suggestion_text = output[0], output[1]
            rec["history_ui"] = {"raw_response": raw_text, "suggestion": suggestion_text}
            rec["oracle"] = self.oracle(kind, raw_text, suggestion_text)
            rec["pass"] = True
        except Exception as e:
            rec["pass"] = False
            rec["failure"] = type(e).__name__ + ": " + str(e)
        rec["ended_at"] = utc()
        self.attempts[kind].append(rec)
        self.emit(f"attempt-{kind}-{number}.json", rec)
        ps_status, ps_raw = self.http("GET", "http://127.0.0.1:11434/api/ps")
        self.emit(f"ollama-ps-after-{kind}-{number}.json", {"http_status": ps_status, "raw": json.loads(ps_raw)})
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
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []
        trace = []
        for index, line in enumerate(lines):
            if 'POST     "/api/chat"' in line:
                trace.append({"sequence": len(trace) + 1, "kind": "visual_chat", "log_line_index": index + 1,
                              "raw_log_line": line})
            elif 'POST     "/api/generate"' in line:
                trace.append({"sequence": len(trace) + 1, "kind": "keep_alive_zero_cleanup",
                              "log_line_index": index + 1, "raw_log_line": line})
        self.emit("ollama-request-trace.json", {"ordered_trace": trace,
                                                 "visual_chat_count": sum(x["kind"] == "visual_chat" for x in trace),
                                                 "cleanup_count": sum(x["kind"] == "keep_alive_zero_cleanup" for x in trace)})

    def manifest(self):
        files = []
        for p in sorted(self.ev.rglob("*")):
            if p.is_file() and p.name != "artifact-manifest.json":
                files.append({"path": p.relative_to(self.root).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)})
        write_json(self.ev / "artifact-manifest.json", {"schema_version": "lvw.artifact-manifest/1", "run_id": RUN_ID,
                                                         "generated_at": utc(), "algorithm": "sha256", "files": files})

    def offline_self_check(self):
        self.temp_w = r"C:\Temp\RUN_TOKEN"
        self.ollama_win = r"C:\Authorized\ollama.exe"
        script = self.windows_wrapper_script()
        required = ["OLLAMA_HOST='127.0.0.1:11434'", "OLLAMA_NO_CLOUD='1'",
                    "NO_PROXY='127.0.0.1,localhost'", "ollama.exe' serve"]
        assert all(value in script for value in required)
        assert script.index("OLLAMA_NO_CLOUD='1'") < script.index("ollama.exe' serve")
        image, image_owner = self.workflow("image")
        video, video_owner = self.workflow("video")
        assert image_owner == "2" and image["2"]["class_type"] == "LVWImagePromptBridge"
        assert video_owner == "8" and video["8"]["class_type"] == "LVWVideoFramesPromptBridge"
        assert sum(node["class_type"] == "LoadImage" for node in video.values()) == 4
        assert self.redact_value({"escaped": "a\\\"b"}) == {"escaped": "a/\"b"}
        assert self.redact(r"C:\\mnt\\c\\neutral\\ComfyUI\\main.py") == "COMFY_ROOT/main.py"
        print(canonical({"self_check": "PASS", "service_started": False,
                         "windows_native_wrapper_env_order": "PASS", "image_owner": image_owner,
                         "video_owner": video_owner, "video_load_image_count": 4}), end="")
        return 0

    def offline_resanitize_and_seal(self):
        """Pre-seal privacy repair only; never starts or queries a service."""
        self.aliases.update({str(Path(self.a.comfy_root).resolve()): "COMFY_ROOT",
                             str(Path(self.a.comfy_python).resolve()): "COMFY_PYTHON",
                             str(Path(self.a.ollama).resolve()): "OLLAMA_EXE",
                             str(Path(self.a.test_source).resolve()): "TEST_SOURCE"})
        self.sanitize_logs()
        for path in self.ev.glob("*.json"):
            if path.name in {"artifact-manifest.json", "run-summary.json"}:
                continue
            write_json(path, self.redact_value(json.loads(path.read_text(encoding="utf-8"))))
        summary_path = self.ev / "run-summary.json"
        receipt_path = self.root / "reports/v0-s0/implementation-receipt-correction-04-live.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["runtime_exception"] = summary["exact_stop_reason"]
        receipt["exact_stop_reason"] = "COMFY_WINDOWS_MAIN_PATH_CONVERSION_FAILED"
        receipt["production_path_status"] = "NOT_RUN_STOP_CONDITION_BEFORE_COMFY_START"
        correction_files = sorted(p.relative_to(self.root).as_posix() for p in self.ev.iterdir()
                                  if p.is_file() and p.name != "artifact-manifest.json")
        # manifest() adds itself after hashing every other evidence file.
        self.manifest()
        manifest_rel = "reports/v0-s0/correction-04/artifact-manifest.json"
        receipt_rel = "reports/v0-s0/implementation-receipt-correction-04-live.json"
        receipt["changed_files"] = sorted(correction_files + [manifest_rel, receipt_rel])
        write_json(receipt_path, receipt)
        print(canonical({"offline_resanitize": "PASS", "service_started": False,
                         "stable_stop_reason": receipt["exact_stop_reason"],
                         "runtime_exception": receipt["runtime_exception"]}), end="")
        return 0

    def run(self):
        pre_integrity = None
        try:
            self.aliases.update({str(Path(self.a.comfy_root).resolve()): "COMFY_ROOT",
                                 str(Path(self.a.comfy_python).resolve()): "COMFY_PYTHON",
                                 str(Path(self.a.ollama).resolve()): "OLLAMA_EXE",
                                 str(Path(self.a.test_source).resolve()): "TEST_SOURCE"})
            head = self.record("verify_authorization_commit", ["git", "cat-file", "-t", AUTHORIZATION_COMMIT],
                               "git cat-file -t AUTHORIZATION_COMMIT", cwd=self.root.parent)
            cand = self.record("verify_candidate_commit", ["git", "cat-file", "-t", CANDIDATE],
                               "git cat-file -t CANDIDATE_SHA", cwd=self.root.parent)
            if head.returncode or cand.returncode:
                raise RuntimeError("authorization or candidate commit unavailable")
            baseline = {"ports": self.listeners(), "gpu_compute_apps": subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False).stdout}
            self.emit("preflight-baseline.json", baseline)
            if isinstance(baseline["ports"], list) and baseline["ports"]:
                raise RuntimeError("authorized port is not empty")
            if baseline["gpu_compute_apps"].strip():
                raise RuntimeError("unknown existing GPU compute owner")
            self.samples = {"image": self.locate_sample(IMAGE_HASH, 404368), "video": self.locate_sample(VIDEO_HASH, 438707)}
            self.emit("sample-verification.json", {k: {"alias": f"TEST_SOURCE/{k}-sample", "sha256": sha(v), "bytes": v.stat().st_size}
                                                   for k, v in self.samples.items()})
            pre_integrity = self.target_integrity()
            self.create_temp(); self.copy_candidate(); self.derive_media(); self.start_services()
            for kind in ("image", "video"):
                if self.resource_stop or self.remote_stop:
                    break
                self.attempt(kind, 1)
                if self.resource_stop or self.remote_stop:
                    break
            passes = all(any(a.get("pass") for a in self.attempts[k]) for k in ("image", "video"))
            if self.resource_stop:
                self.decision = "NO_GO"; self.exact_stop_reason = "GPU_MEMORY_REACHED_OR_EXCEEDED_23552_MIB"
            elif self.remote_stop:
                self.decision = "NO_GO"; self.exact_stop_reason = "OWNED_OLLAMA_PID_NON_LOOPBACK_REMOTE_CONNECTION"
            elif passes:
                self.decision = "READY_FOR_REVIEW"; self.exact_stop_reason = "AUTHORIZED_LIVE_PROBE_COMPLETE"
            else:
                self.decision = "NO_GO"; self.exact_stop_reason = "PUBLIC_COMFY_ROUTE_FAILED_WITHIN_ATTEMPT_BUDGET"
        except Exception as e:
            reason = str(e)
            mandatory_no_go = ("NO_CLOUD" in reason or "NON_LOOPBACK" in reason or
                               "GPU_THRESHOLD" in reason or "STOP_CONDITION" in reason)
            self.decision = "NO_GO" if mandatory_no_go else "BLOCKED"
            self.exact_stop_reason = reason if mandatory_no_go else type(e).__name__ + ": " + reason
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
                     self.stop_owned(self.ollama_pid, "owned_ollama_listener"),
                     self.stop_owned(self.ollama_wrapper_pid, "owned_windows_wrapper")]
            if self.comfy_proc:
                try: self.comfy_proc.wait(timeout=5)
                except Exception: pass
            if self.ollama_proc:
                try: self.ollama_proc.wait(timeout=5)
                except Exception: pass
            final_ports = self.listeners()
            post_integrity = self.target_integrity()
            integrity_equal = pre_integrity is not None and pre_integrity == post_integrity
            temp_remove = {"attempted": bool(self.temp_w), "exists_before": bool(self.temp_u and self.temp_u.exists())}
            if self.temp_w:
                p = subprocess.run([self.a.powershell, "-NoProfile", "-Command",
                                    "Remove-Item -LiteralPath '" + self.temp_w.replace("'", "''") + "' -Recurse -Force -ErrorAction SilentlyContinue"],
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=60)
                temp_remove.update({"exit_code": p.returncode, "output": self.redact(p.stdout)})
            temp_remove["exists_after"] = bool(self.temp_u and self.temp_u.exists())
            self.cleanup = {"owned_process_stops": stops, "final_authorized_port_listeners": final_ports,
                            "target_integrity_pre": pre_integrity, "target_integrity_post": post_integrity,
                            "target_integrity_equal": integrity_equal, "run_temp_removal": temp_remove}
            if final_ports or temp_remove["exists_after"] or (pre_integrity is not None and not integrity_equal):
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
                                       "stop_reason": self.exact_stop_reason}
                self.emit("pre-model-gate.json", self.pre_model_gate)
            self.emit("cleanup.json", self.cleanup)
            self.sanitize_logs()
            self.emit_request_trace()
            summary = {"schema_version": "lvw.live-probe/1", "run_id": RUN_ID, "candidate_sha": CANDIDATE,
                       "authorization_commit": AUTHORIZATION_COMMIT, "started_at": self.started, "ended_at": utc(),
                       "decision": self.decision, "stage_pass_claim": False, "exact_stop_reason": self.exact_stop_reason,
                       "effective_attempts": {k: len(v) for k, v in self.attempts.items()},
                       "attempt_results": {k: [a.get("pass", False) for a in v] for k, v in self.attempts.items()},
                       "resource_stop": self.resource_stop, "non_loopback_remote_seen": self.remote_stop,
                       "no_cloud_reported_true": self.no_cloud_reported_true,
                       "pre_model_gate": self.pre_model_gate,
                       "cleanup_proven": not bool(self.cleanup.get("final_authorized_port_listeners")) and
                                         not self.cleanup.get("run_temp_removal", {}).get("exists_after", True) and
                                         self.cleanup.get("target_integrity_equal", False)}
            self.emit("run-summary.json", summary)
            self.manifest()
            ev_rel = "reports/v0-s0/correction-04/"
            trace_refs = [ev_rel + f"attempt-{kind}-1.json" for kind in ("image", "video")
                          if (self.ev / f"attempt-{kind}-1.json").exists()]
            production_status = ("PUBLIC_COMFY_IMAGE_AND_VIDEO_TRACE_COMPLETE_READY_FOR_REVIEW"
                                 if self.decision == "READY_FOR_REVIEW" else
                                 "NOT_RUN_STOP_CONDITION_BEFORE_COMFY_START" if not trace_refs else
                                 "PARTIAL_OR_FAILED_PUBLIC_COMFY_TRACE")
            request_trace = json.loads((self.ev / "ollama-request-trace.json").read_text(encoding="utf-8"))
            correction_files = sorted(p.relative_to(self.root).as_posix() for p in self.ev.iterdir() if p.is_file())
            receipt_rel = "reports/v0-s0/implementation-receipt-correction-04-live.json"
            raw_refs = [ev_rel + name for name in
                        ("ollama-live.log", "comfy-live.log", "ollama-version.json", "ollama-tags.json",
                         "ollama-show.json", "ollama-ps_start.json", "ollama-ps-final-before-stop.json",
                         "owned-ollama-remote-tcp.json", "resource-samples.json", "pre-model-gate.json")
                        if (self.ev / name).exists()]
            receipt = {
                "schema_version": "lvw.implementation-receipt/1", "spec_version": "1.8.0",
                "project_id": "lvw-prompt-service", "stage_id": "V0-S0", "workpack_id": "WP-S0-10",
                "run_id": RUN_ID, "implementation_owner_role": "codex_isolated_implementer",
                "implementation_session": "/root/s0_rerun_implementer", "candidate_sha": CANDIDATE,
                "authorization_commit": AUTHORIZATION_COMMIT,
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
                                "required_no_cloud_observed": self.no_cloud_reported_true,
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
                "external_actions": {"ollama_process_starts": int(self.ollama_wrapper_pid is not None),
                                     "comfyui_process_starts": int(self.comfy_pid is not None),
                                     "model_calls": request_trace["visual_chat_count"], "downloads_or_upgrades": 0,
                                     "target_install_writes": 0, "visible_browser_runs": 0, "external_cost": 0},
                "cleanup": {"proven": summary["cleanup_proven"], "details": ev_rel + "cleanup.json"},
                "check_results": [
                    {"check": "windows_native_no_cloud_server_raw", "status": "PASS" if self.no_cloud_reported_true else "FAIL"},
                    {"check": "pre_model_remote_tcp_gate", "status": "PASS" if self.pre_model_gate.get("passed") else "FAIL"},
                    {"check": "public_comfy_image_route", "status": "PASS" if any(x.get("pass") for x in self.attempts["image"]) else "NOT_RUN_OR_FAIL"},
                    {"check": "public_comfy_video_route", "status": "PASS" if any(x.get("pass") for x in self.attempts["video"]) else "NOT_RUN_OR_FAIL"},
                    {"check": "cleanup_and_target_integrity", "status": "PASS" if summary["cleanup_proven"] else "FAIL"}],
                "artifact_manifest": ev_rel + "artifact-manifest.json",
                "artifact_refs": [ev_rel + "run-summary.json", ev_rel + "cleanup.json", ev_rel + "pre-model-gate.json",
                                  ev_rel + "owned-ollama-remote-tcp.json", ev_rel + "resource-samples.json",
                                  ev_rel + "ollama-request-trace.json", ev_rel + "artifact-manifest.json"],
                "raw_artifact_refs": raw_refs,
                "risks": ["Live semantic output remains model- and sample-specific; this receipt is not a Stage PASS.",
                          "The four fixed product acceptance cases remain NOT_RUN."]}
            write_json(self.root / receipt_rel, receipt)
        return 0 if self.decision == "READY_FOR_REVIEW" else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--comfy-root", required=True); p.add_argument("--comfy-python", required=True)
    p.add_argument("--ollama", required=True); p.add_argument("--test-source", required=True)
    p.add_argument("--powershell", default="powershell.exe")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--offline-resanitize-and-seal", action="store_true")
    args = p.parse_args()
    probe = Probe(args)
    if args.self_check:
        return probe.offline_self_check()
    if args.offline_resanitize_and_seal:
        return probe.offline_resanitize_and_seal()
    return probe.run()


if __name__ == "__main__":
    sys.exit(main())

