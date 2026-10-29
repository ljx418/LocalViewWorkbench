#!/usr/bin/env python3
"""One-shot, fail-closed R1a local Ollama + same-origin browser acceptance harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
MODEL = "gemma4:26b"
OLLAMA_EXE = Path("/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe")
TEST_SOURCE = Path("/mnt/c/workSpace/videoWorkLine/testSource")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ps(script: str) -> str:
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=60)
    if result.returncode:
        raise RuntimeError("POWERSHELL_COMMAND_FAILED")
    return result.stdout.strip()


def listener(port: int) -> list[int]:
    raw = ps(f"$x=Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue;"
             "@($x | Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress")
    value = json.loads(raw) if raw else []
    if isinstance(value, int):
        return [value]
    return [int(item) for item in value]


def wait_url(url: str, timeout: int = 60) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.read()
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("SERVICE_START_TIMEOUT")


def find_sample() -> Path:
    matches = [path for path in TEST_SOURCE.rglob("*") if path.is_file() and sha(path) == SAMPLE_SHA256]
    if len(matches) != 1:
        raise RuntimeError("AUTHORIZED_SAMPLE_IDENTITY_MISMATCH")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--harness-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.execute_live:
        raise SystemExit("live execution requires --execute-live")
    auth = json.loads((ROOT / args.authorization).read_text(encoding="utf-8"))
    if not (auth.get("approval", {}).get("decision") == "APPROVED"
            and auth.get("product_candidate") == args.candidate
            and auth.get("run_id") == args.run_id
            and auth.get("harness_sha256") == args.harness_sha256):
        raise SystemExit("authorization identity mismatch")
    git_root = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], text=True).strip()
    prefix = str(ROOT.relative_to(Path(git_root))).replace("\\", "/")
    harness_rel = f"{prefix}/tools/r1a_live_acceptance.py"
    blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{args.candidate}:{harness_rel}"])
    if hashlib.sha256(blob).hexdigest() != args.harness_sha256 or sha(Path(__file__)) != args.harness_sha256:
        raise SystemExit("harness identity mismatch")
    if listener(11434) or listener(8765):
        raise SystemExit("target port already in use")
    sample = find_sample()
    evidence = ROOT / "reports" / "r1a" / args.run_id
    if evidence.exists():
        raise SystemExit("evidence slot already exists")
    evidence.mkdir(parents=True)
    runtime = Path(tempfile.mkdtemp(prefix="lvw-r1a-"))
    backend = ollama = None
    streams = []
    terminal = {"backend_stopped": False, "ollama_stopped": False, "ports_empty": False,
                "runtime_removed": False, "model_unloaded": False}
    result = {"run_id": args.run_id, "candidate_sha": args.candidate, "sample_alias": "TEST_SOURCE/image-sample",
              "sample_sha256": SAMPLE_SHA256, "model": MODEL, "attempts": 0, "model_calls": 0,
              "browser_runs": 0, "decision": "NO_GO", "stage_pass_claim": False}
    try:
        wrapper = runtime / "ollama.ps1"
        win_exe = subprocess.check_output(["wslpath", "-w", str(OLLAMA_EXE)], text=True).strip()
        escaped_exe = win_exe.replace("'", "''")
        wrapper.write_text("$env:OLLAMA_HOST='127.0.0.1:11434'\n$env:OLLAMA_NO_CLOUD='1'\n"
                           "$env:NO_PROXY='127.0.0.1,localhost'\n"
                           f"& '{escaped_exe}' serve\n", encoding="utf-8")
        win_wrapper = subprocess.check_output(["wslpath", "-w", str(wrapper)], text=True).strip()
        ollama_log = (runtime / "ollama.log").open("w", encoding="utf-8")
        streams.append(ollama_log)
        ollama = subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", win_wrapper],
                                  stdout=ollama_log, stderr=subprocess.STDOUT, text=True)
        wait_url("http://127.0.0.1:11434/api/version")
        pids = listener(11434)
        if len(pids) != 1:
            raise RuntimeError("OLLAMA_LISTENER_IDENTITY_UNPROVEN")
        process_json = ps(f"Get-CimInstance Win32_Process -Filter \"ProcessId={pids[0]}\" | "
                          "Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress")
        process = json.loads(process_json)
        if not str(process.get("ExecutablePath", "")).lower().replace("\\", "/").endswith("/ollama.exe"):
            raise RuntimeError("OLLAMA_EXECUTABLE_IDENTITY_MISMATCH")
        backend_log = (runtime / "backend.log").open("w", encoding="utf-8")
        streams.append(backend_log)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        backend = subprocess.Popen([sys.executable, "lvw/run_local.py"], cwd=ROOT, env=env,
                                   stdout=backend_log, stderr=subprocess.STDOUT, text=True)
        wait_url("http://127.0.0.1:8765/health")
        node_path = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
        browser_env = {**os.environ, "NODE_PATH": node_path}
        browser = subprocess.run(["node", "tools/r1a_browser_acceptance.cjs", "--url", "http://127.0.0.1:8765",
                                  "--sample", str(sample), "--evidence", str(evidence)], cwd=ROOT,
                                 env=browser_env, capture_output=True, text=True, timeout=210)
        result["attempts"] = 1
        result["model_calls"] = 1
        result["browser_runs"] = 1
        result["browser_exit_code"] = browser.returncode
        result["browser_stdout_sha256"] = hashlib.sha256(browser.stdout.encode()).hexdigest()
        result["browser_stderr_tail"] = browser.stderr[-1200:]
        if browser.returncode:
            raise RuntimeError("BROWSER_PRODUCT_PATH_FAILED")
        browser_result = json.loads((evidence / "browser-result.json").read_text(encoding="utf-8"))
        if not browser_result.get("passed") or browser_result.get("non_loopback_requests"):
            raise RuntimeError("BROWSER_NETWORK_ORACLE_FAILED")
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as response:
            running = json.loads(response.read())
        terminal["model_unloaded"] = running.get("models") == []
        if not terminal["model_unloaded"]:
            raise RuntimeError("MODEL_UNLOAD_NOT_PROVEN")
        result["decision"] = "READY_FOR_INDEPENDENT_REVIEW"
    except Exception as exc:
        result["error"] = type(exc).__name__ + ":" + str(exc)
    finally:
        if backend is not None:
            backend.terminate()
            try: backend.wait(timeout=15)
            except subprocess.TimeoutExpired: backend.kill(); backend.wait(timeout=5)
            terminal["backend_stopped"] = backend.poll() is not None
        pids = listener(11434)
        if len(pids) == 1:
            ps(f"Stop-Process -Id {pids[0]} -Force -ErrorAction Stop")
        if ollama is not None:
            try: ollama.wait(timeout=15)
            except subprocess.TimeoutExpired: ollama.terminate(); ollama.wait(timeout=5)
            terminal["ollama_stopped"] = ollama.poll() is not None
        for stream in streams: stream.close()
        terminal["ports_empty"] = not listener(11434) and not listener(8765)
        shutil.rmtree(runtime, ignore_errors=False)
        terminal["runtime_removed"] = not runtime.exists()
        result["terminal"] = terminal
        if not all(terminal.values()):
            result["decision"] = "NO_GO_CLEANUP_UNPROVEN"
        (evidence / "live-receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "terminal": terminal}, ensure_ascii=False))
    return 0 if result["decision"] == "READY_FOR_INDEPENDENT_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
