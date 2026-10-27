#!/usr/bin/env python3
"""Deterministic, evidence-only WP-S0-04 local runtime probe.

Concrete private roots are supplied at runtime. Persisted commands and output are
redacted to COMFY_ROOT, TEST_SOURCE, COMFY_PYTHON, OLLAMA_EXE and RUN_TEMP.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request

RUN_ID = "v0-s0-rerun-20261027-02"
CANDIDATE = "95be0cd82c5500b0a71e3597f5188b147f11e75f"
IMAGE_SHA = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
VIDEO_SHA = "694a50bfb871faed6540a577b25c8a61e629035062a23f982099a6911ff22152"
MODEL = "gemma4:26b"
EXPECTED_MODEL_DIGEST = "5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251"
OLLAMA = "http://127.0.0.1:11434"
COMFY = "http://127.0.0.1:8188"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="milliseconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class Probe:
    def __init__(self, args: argparse.Namespace):
        self.out = Path(__file__).resolve().parent
        self.comfy_root = Path(args.comfy_root).resolve()
        self.test_source = Path(args.test_source).resolve()
        self.comfy_python = Path(args.comfy_python).resolve()
        self.ollama_exe = Path(args.ollama_exe).resolve()
        self.comfy_workdir = self.comfy_root.parent
        self.run_temp = self.out / ".run-owned-temp"
        self.windows_user_profile = self.ollama_exe.parents[4]
        self.aliases = [
            (str(self.comfy_python), "COMFY_PYTHON"),
            (str(self.ollama_exe), "OLLAMA_EXE"),
            (str(self.comfy_root), "COMFY_ROOT"),
            (str(self.comfy_workdir), "COMFY_ROOT_PARENT"),
            (str(self.test_source), "TEST_SOURCE"),
            (str(self.run_temp), "RUN_TEMP"),
            (str(self.windows_user_profile), "USER_PROFILE"),
        ]
        self.events = []
        self.owned = {"ollama": None, "comfy": None}
        self.processes = {}
        self.attempts = {"image": 0, "video": 0}
        self.results = {"image": [], "video": []}
        self.archive_incomplete_harness_run()

    def archive_incomplete_harness_run(self):
        """Retain a pre-probe harness failure without retaining private paths."""
        if not (self.out / "harness-error.json").is_file() or (self.out / "probe-summary.json").is_file():
            return
        used = []
        for path in self.out.glob("harness-failure-*-harness-error.json"):
            try:
                used.append(int(path.name.split("-")[2]))
            except (ValueError, IndexError):
                pass
        failure_index = max(used, default=0) + 1
        prefix = f"harness-failure-{failure_index:02d}-"
        for path in sorted(self.out.iterdir()):
            if not path.is_file() or path.name == "probe.py" or path.name.startswith("harness-failure-"):
                continue
            target = self.out / f"{prefix}{path.name.replace('.private-tmp', '.log')}"
            if path.name.endswith(".private-tmp"):
                target.write_text(self.redact(path.read_bytes().decode("utf-8", "replace")), encoding="utf-8")
                path.unlink()
            else:
                path.replace(target)

    def redact(self, text: str) -> str:
        value = str(text)
        for raw, alias in sorted(self.aliases, key=lambda x: len(x[0]), reverse=True):
            variants = {raw}
            parts = Path(raw).parts
            if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
                variants.add(parts[2].upper() + ":\\" + "\\".join(parts[3:]))
            for variant in variants:
                value = value.replace(variant, alias)
                value = value.replace(variant.replace("\\", "\\\\"), alias)
        value = value.replace(str(Path.home()), "USER_HOME")
        return value

    def logical(self, argv) -> list[str]:
        return [self.redact(str(x)) for x in argv]

    def event(self, name: str, start: str, end: str, exit_code=None, http_status=None, command=None, note=None):
        item = {"step": name, "started_at": start, "ended_at": end}
        if command is not None:
            item["logical_command"] = self.logical(command)
        if exit_code is not None:
            item["exit_code"] = exit_code
        if http_status is not None:
            item["http_status"] = http_status
        if note is not None:
            item["note"] = note
        self.events.append(item)
        atomic_json(self.out / "command-events.json", self.events)

    def run(self, name: str, argv, *, cwd=None, timeout=60, save=None):
        start = now()
        cp = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output = self.redact(cp.stdout)
        if save:
            (self.out / save).write_text(output, encoding="utf-8")
        self.event(name, start, now(), exit_code=cp.returncode, command=argv)
        return cp.returncode, output

    def http(self, name: str, method: str, url: str, payload=None, *, timeout=60, save=None, request_meta=None):
        encoded = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json"} if encoded is not None else {}
        req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
        start = now()
        status = 0
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.status
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", "replace")
        except Exception as exc:
            raw = json.dumps({"transport_error": type(exc).__name__, "message": str(exc)})
        raw = self.redact(raw)
        if save:
            (self.out / save).write_text(raw, encoding="utf-8")
        logical_request = {"method": method, "url": url}
        if request_meta:
            logical_request.update(request_meta)
        if payload is not None:
            logical_request["json_parameters"] = self.payload_metadata(payload)
        self.event(name, start, now(), exit_code=0 if status else 1, http_status=status,
                   command=["HTTP", method, url], note=logical_request)
        return status, raw

    def payload_metadata(self, value):
        if isinstance(value, dict):
            out = {}
            for key, child in value.items():
                if key == "images" and isinstance(child, list):
                    out[key] = [{"base64_omitted": True, "encoded_bytes": len(x)} for x in child]
                else:
                    out[key] = self.payload_metadata(child)
            return out
        if isinstance(value, list):
            return [self.payload_metadata(x) for x in value]
        return value

    def wait_http(self, base: str, endpoint: str, seconds=120) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(base + endpoint, timeout=2) as response:
                    if response.status < 500:
                        return True
            except Exception:
                time.sleep(1)
        return False

    def port_pids(self):
        script = ("Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                  "Where-Object { $_.LocalPort -in 8188,11434 } | "
                  "Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress")
        cp = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        text = cp.stdout.strip()
        try:
            parsed = json.loads(text) if text else []
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return {"parse_error": self.redact(text), "exit_code": cp.returncode}

    def start_service(self, service: str, argv, cwd: Path, endpoint: str, log_name: str):
        base = OLLAMA if service == "ollama" else COMFY
        if self.wait_http(base, endpoint, seconds=1):
            self.event(f"{service}-preexisting", now(), now(), exit_code=0,
                       command=["HTTP", "GET", base + endpoint], note="preexisting; not owned")
            return
        log_path = self.out / (log_name + ".private-tmp")
        log = log_path.open("wb")
        start = now()
        env = os.environ.copy()
        logical_argv = list(argv)
        if service == "ollama":
            env["OLLAMA_NO_CLOUD"] = "1"
            logical_argv = ["env", "OLLAMA_NO_CLOUD=1", *logical_argv]
        proc = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=env)
        self.processes[service] = (proc, log, log_path)
        ready = self.wait_http(base, endpoint)
        listeners = self.port_pids()
        port = 11434 if service == "ollama" else 8188
        owned_pid = None
        if isinstance(listeners, list):
            matching = [x for x in listeners if int(x.get("LocalPort", -1)) == port]
            if len(matching) == 1:
                owned_pid = int(matching[0]["OwningProcess"])
        self.owned[service] = owned_pid
        self.event(f"start-{service}", start, now(), exit_code=0 if ready else 1, command=logical_argv,
                   note={"ready": ready, "owned_listener_pid": owned_pid})
        if not ready or owned_pid is None:
            raise RuntimeError(f"{service} did not become an attributable run-owned listener")

    def stop_services(self):
        records = []
        for service in ("comfy", "ollama"):
            owned_pid = self.owned.get(service)
            before = self.port_pids()
            if owned_pid:
                start = now()
                argv = ["taskkill.exe", "/PID", str(owned_pid), "/T", "/F"]
                cp_raw = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                cp_stdout = cp_raw.stdout.decode("cp936", "replace")
                self.event(f"stop-{service}", start, now(), exit_code=cp_raw.returncode, command=argv,
                           note=self.redact(cp_stdout))
            item = self.processes.get(service)
            if item:
                proc, log, log_path = item
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    pass
                log.close()
                raw = log_path.read_text(encoding="utf-8", errors="replace")
                (self.out / f"{service}-startup.log").write_text(self.redact(raw), encoding="utf-8")
                log_path.unlink(missing_ok=True)
            records.append({"service": service, "owned_listener_pid": owned_pid,
                            "listeners_before_stop": before})
        time.sleep(2)
        records.append({"final_listeners": self.port_pids()})
        atomic_json(self.out / "cleanup.json", records)

    def locate(self, expected_hash: str, expected_size: int) -> Path:
        matches = []
        for candidate in sorted(self.test_source.rglob("*")):
            if candidate.is_file() and candidate.stat().st_size == expected_size:
                if sha256_file(candidate) == expected_hash:
                    matches.append(candidate)
        if len(matches) != 1:
            raise RuntimeError(f"sample lookup expected one match, got {len(matches)}")
        return matches[0]

    def masked_config(self, phase: str):
        candidates = [
            self.comfy_root / "user/default/prompt-assistant/config/config.json",
            self.comfy_workdir / "user/default/prompt-assistant/config/config.json",
        ]
        config = next((p for p in candidates if p.is_file()), None)
        if config is None:
            atomic_json(self.out / f"masked-config-{phase}.json", {"status": "NOT_FOUND"})
            return None
        data = json.loads(config.read_text(encoding="utf-8"))

        def mask(value, key=""):
            if isinstance(value, dict):
                return {k: mask(v, k) for k, v in value.items()}
            if isinstance(value, list):
                return [mask(x, key) for x in value]
            if any(token in key.lower() for token in ("key", "token", "secret", "password")):
                return {"redacted": True, "present": bool(value)}
            if isinstance(value, str):
                return self.redact(value)
            return value

        atomic_json(self.out / f"masked-config-{phase}.json",
                    {"path": "COMFY_ROOT/user/default/prompt-assistant/config/config.json",
                     "sha256": sha256_file(config), "masked": mask(data)})
        return sha256_file(config)

    def sample_resources(self, stop: threading.Event, path: Path):
        with path.open("w", encoding="utf-8") as f:
            while not stop.is_set():
                stamp = now()
                cp = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                                     "--format=csv,noheader,nounits"], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
                mem_available_kib = None
                for line in Path("/proc/meminfo").read_text().splitlines():
                    if line.startswith("MemAvailable:"):
                        mem_available_kib = int(line.split()[1])
                        break
                record = {"timestamp": stamp, "gpu_query_exit_code": cp.returncode,
                          "gpu_memory_mib": cp.stdout.strip(),
                          "host_mem_available_mib": round(mem_available_kib / 1024, 3) if mem_available_kib else None}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                stop.wait(1)

    def validate_schema(self, content: str, required: dict):
        result = {"json_parse": False, "schema_valid": False, "errors": []}
        try:
            obj = json.loads(content)
            result["json_parse"] = True
        except Exception as exc:
            result["errors"].append(f"json_parse:{type(exc).__name__}:{exc}")
            return result
        if not isinstance(obj, dict):
            result["errors"].append("root_not_object")
            return result
        for key, kind in required.items():
            if key not in obj:
                result["errors"].append(f"missing:{key}")
            elif not isinstance(obj[key], kind):
                result["errors"].append(f"type:{key}")
        result["schema_valid"] = not result["errors"]
        result["keys"] = sorted(obj) if isinstance(obj, dict) else []
        return result

    def ollama_attempt(self, probe: str, images: list[Path], attempt: int):
        self.attempts[probe] += 1
        if self.attempts[probe] > 2:
            raise RuntimeError(f"{probe} effective attempt budget exceeded")
        encoded_images = [base64.b64encode(p.read_bytes()).decode("ascii") for p in images]
        if probe == "image":
            required = {"observations": list, "inferences": list, "unknowns": list,
                        "image_prompt": str, "tags": list}
            prompt = ("Analyze this image. Return only compact JSON matching the schema. "
                      "Use short factual phrases; separate observations, inferences, and unknowns.")
        else:
            required = {"observations": list, "motion": list, "unknowns": list,
                        "video_prompt": str, "tags": list}
            prompt = ("These four images are ordered video frames. Return only compact JSON matching the schema. "
                      "Describe visible change conservatively; do not claim full-video coverage.")
        properties = {}
        for key, kind in required.items():
            if kind is list:
                properties[key] = {"type": "array", "items": {"type": "string"}, "maxItems": 6}
            else:
                properties[key] = {"type": "string", "maxLength": 800}
        schema = {"type": "object", "properties": properties,
                  "required": list(required), "additionalProperties": False}
        if attempt > 1:
            prompt += " Correction retry: keep every string under 20 words and every array under 4 items."
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt, "images": encoded_images}],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"num_ctx": 4096, "num_predict": 1536, "temperature": 0.2},
            "keep_alive": 0,
        }
        stop = threading.Event()
        sampler = threading.Thread(target=self.sample_resources,
                                   args=(stop, self.out / f"resources-{probe}-{attempt}.jsonl"), daemon=True)
        sampler.start()
        status, raw = self.http(f"{probe}-attempt-{attempt}", "POST", OLLAMA + "/api/chat", payload,
                                timeout=300, save=f"ollama-{probe}-attempt-{attempt}-response.json",
                                request_meta={"effective_attempt": attempt,
                                              "input_aliases": ["TEST_SOURCE/image-sample"] if probe == "image" else [f"RUN_TEMP/frame-{i}.png" for i in range(4)]})
        stop.set()
        sampler.join(timeout=3)
        try:
            envelope = json.loads(raw)
            content = envelope.get("message", {}).get("content", "")
            validation = self.validate_schema(content, required)
            validation.update({"http_status": status, "done": envelope.get("done"),
                               "done_reason": envelope.get("done_reason")})
        except Exception as exc:
            validation = {"json_parse": False, "schema_valid": False,
                          "errors": [f"envelope:{type(exc).__name__}:{exc}"], "http_status": status}
        atomic_json(self.out / f"ollama-{probe}-attempt-{attempt}-validation.json", validation)
        self.results[probe].append(validation)
        for offset in (0, 5):
            if offset:
                time.sleep(offset)
            self.http(f"{probe}-attempt-{attempt}-ps-t{offset}", "GET", OLLAMA + "/api/ps",
                      save=f"ollama-{probe}-attempt-{attempt}-ps-t{offset}.json")
        return validation.get("schema_valid", False)

    def execute(self):
        self.run_temp.mkdir(parents=True, exist_ok=False)
        image = self.locate(IMAGE_SHA, 404368)
        video = self.locate(VIDEO_SHA, 438707)
        samples = {"image": {"alias": "TEST_SOURCE/image-sample", "sha256": sha256_file(image), "bytes": image.stat().st_size},
                   "video": {"alias": "TEST_SOURCE/video-sample", "sha256": sha256_file(video), "bytes": video.stat().st_size}}
        atomic_json(self.out / "sample-hashes.json", samples)
        self.run("gpu-baseline", ["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
                 "--format=csv,noheader,nounits"], save="gpu-baseline.txt")
        self.run("gpu-process-baseline", ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory",
                 "--format=csv,noheader,nounits"], save="gpu-process-baseline.txt")
        config_before = self.masked_config("before")
        self.start_service("ollama", [str(self.ollama_exe), "serve"], self.ollama_exe.parent,
                           "/api/version", "ollama-startup")
        win_main = subprocess.run(["wslpath", "-w", str(self.comfy_root / "main.py")], text=True,
                                  stdout=subprocess.PIPE, check=True).stdout.strip()
        comfy_argv = [str(self.comfy_python), "-s", win_main, "--listen", "127.0.0.1",
                      "--port", "8188", "--disable-auto-launch", "--disable-api-nodes",
                      "--disable-all-custom-nodes", "--whitelist-custom-nodes", "prompt-assistant"]
        self.start_service("comfy", comfy_argv, self.comfy_workdir, "/system_stats", "comfy-startup")
        config_after = self.masked_config("after-start")
        atomic_json(self.out / "config-integrity.json", {"before_sha256": config_before,
                                                          "after_start_sha256": config_after,
                                                          "unchanged": config_before == config_after})
        self.http("comfy-object-info", "GET", COMFY + "/object_info", save="comfy-object-info-raw.json")
        for endpoint, method, payload, name in [
            ("/api/version", "GET", None, "ollama-version"),
            ("/api/tags", "GET", None, "ollama-tags"),
            ("/api/show", "POST", {"model": MODEL}, "ollama-show"),
            ("/api/ps", "GET", None, "ollama-ps-before"),
        ]:
            self.http(name, method, OLLAMA + endpoint, payload, save=name + "-raw.json")
        for kind in ("llm", "vision"):
            self.http(f"pa-models-list-{kind}", "POST", COMFY + "/prompt-assistant/api/models/list",
                      {"provider": "ollama", "model_type": kind, "recommended": False},
                      save=f"pa-models-list-{kind}-raw.json")
        ffprobe_argv = ["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=index,codec_type,codec_name,width,height,nb_frames",
                        "-of", "json", str(video)]
        rc, probe_raw = self.run("ffprobe-video", ffprobe_argv, save="ffprobe-raw.json")
        if rc:
            raise RuntimeError("ffprobe failed")
        duration = float(json.loads(probe_raw)["format"]["duration"])
        frame_records = []
        for i in range(4):
            target = duration * (i + 0.5) / 4
            frame = self.run_temp / f"frame-{i}.png"
            argv = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{target:.6f}",
                    "-i", str(video), "-frames:v", "1", "-vf",
                    "scale='if(gt(iw,ih),768,-2)':'if(gt(iw,ih),-2,768)'", "-y", str(frame)]
            rc, _ = self.run(f"extract-frame-{i}", argv, save=f"ffmpeg-frame-{i}.log")
            if rc or not frame.is_file():
                raise RuntimeError(f"frame {i} extraction failed")
            frame_records.append({"index": i, "target_seconds": round(target, 6),
                                  "alias": f"RUN_TEMP/frame-{i}.png", "sha256": sha256_file(frame),
                                  "bytes": frame.stat().st_size})
        atomic_json(self.out / "frame-hashes.json", frame_records)
        if not self.ollama_attempt("image", [image], 1):
            self.ollama_attempt("image", [image], 2)
        frames = [self.run_temp / f"frame-{i}.png" for i in range(4)]
        if not self.ollama_attempt("video", frames, 1):
            self.ollama_attempt("video", frames, 2)
        summary = {
            "schema_version": "lvw.probe-summary/1", "run_id": RUN_ID, "candidate_sha": CANDIDATE,
            "model": MODEL, "expected_model_digest": EXPECTED_MODEL_DIGEST,
            "attempts": self.attempts, "results": self.results,
            "production_path": {"comfy_registry_probe": "SEPARATE_PUBLIC_REGISTRY_OBSERVATION",
                                "ollama_direct_probe": "SEPARATE_DIRECT_LOCAL_MODEL_CALL",
                                "connected_public_entry": False,
                                "conclusion": "NO_GO_NO_CONNECTED_PUBLIC_ENTRY_TO_LOCAL_MODEL"},
            "product_acceptance": {x: "NOT_RUN" for x in ("V0-A01", "V0-A02", "V0-A09", "V0-A10")},
        }
        atomic_json(self.out / "probe-summary.json", summary)

    def finish(self):
        try:
            self.stop_services()
        finally:
            temp_files = []
            if self.run_temp.exists():
                temp_files = [self.redact(str(p)) for p in sorted(self.run_temp.rglob("*")) if p.is_file()]
                shutil.rmtree(self.run_temp)
            cleanup_path = self.out / "cleanup.json"
            cleanup = json.loads(cleanup_path.read_text()) if cleanup_path.is_file() else []
            cleanup.append({"run_temp_removed": not self.run_temp.exists(), "removed_files": temp_files,
                            "finished_at": now()})
            atomic_json(cleanup_path, cleanup)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--test-source", required=True)
    parser.add_argument("--comfy-python", required=True)
    parser.add_argument("--ollama-exe", required=True)
    args = parser.parse_args()
    probe = Probe(args)
    status = 0
    try:
        probe.execute()
    except Exception as exc:
        status = 1
        atomic_json(probe.out / "harness-error.json",
                    {"timestamp": now(), "type": type(exc).__name__, "message": probe.redact(str(exc))})
    finally:
        probe.finish()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
