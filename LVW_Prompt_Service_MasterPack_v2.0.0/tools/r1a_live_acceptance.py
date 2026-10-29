#!/usr/bin/env python3
"""One-shot, fail-closed R1a local Ollama + same-origin browser acceptance harness."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

try:
    from r1a_runtime_guard import (
        linux_identity_matches, linux_process_identity, parse_windows_listener_json,
        windows_identity_matches, wsl_listener_pids,
    )
except ModuleNotFoundError:  # Imported as tools.r1a_live_acceptance by offline tests.
    from tools.r1a_runtime_guard import (
        linux_identity_matches, linux_process_identity, parse_windows_listener_json,
        windows_identity_matches, wsl_listener_pids,
    )

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"
MODEL = "gemma4:26b"
BACKEND_PORT = 18765
OLLAMA_PORT = 11434
OLLAMA_EXE = Path("/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe")
TEST_SOURCE = Path("/mnt/c/workSpace/videoWorkLine/testSource")
WINDOWS_TEMP = Path("/mnt/c/Temp")
OLLAMA_WRAPPER = ROOT / "tools" / "r1a_ollama_wrapper.ps1"
ACCEPTANCE_HASH = "82a3736ab77ee98e301d7e055a78b160774c9c09692288db89c5a2768bfe39ab"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitized_tail(path: Path, limit: int = 1600) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")[-limit:]
    text = re.sub(r"(?i)[A-Z]:[\\/][^\r\n\t ]+", "<redacted-path>", text)
    return re.sub(r"/mnt/[a-zA-Z]/[^\r\n\t ]+", "<redacted-path>", text)


def ps(script: str, timeout: int = 60) -> str:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("POWERSHELL_COMMAND_FAILED")
    return result.stdout.strip()


def windows_listeners(port: int) -> list[int]:
    raw = ps(
        f"$x=Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue;"
        "@($x | Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress"
    )
    return parse_windows_listener_json(raw)


def windows_process(pid: int) -> dict | None:
    raw = ps(
        f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
        "if($null -ne $p){[pscustomobject]@{pid=$p.Id;"
        "start_filetime_utc=$p.StartTime.ToFileTimeUtc().ToString();"
        "executable_path=$p.Path}|ConvertTo-Json -Compress}"
    )
    if not raw:
        return None
    value = json.loads(raw)
    return {
        "pid": int(value["pid"]),
        "start_filetime_utc": str(value["start_filetime_utc"]),
        "executable_path": str(value["executable_path"]),
    }


def wait_url(url: str, phase: str, timeout: int = 90) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.read()
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"{phase}_START_TIMEOUT")


def wait_file(path: Path, phase: str, process=None, timeout: int = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"{phase}_WRAPPER_EXITED_{process.returncode}")
        time.sleep(0.25)
    raise RuntimeError(f"{phase}_OWNER_RECORD_TIMEOUT")


def find_sample() -> Path:
    matches = [path for path in TEST_SOURCE.rglob("*") if path.is_file() and sha(path) == SAMPLE_SHA256]
    if len(matches) != 1:
        raise RuntimeError("AUTHORIZED_SAMPLE_IDENTITY_MISMATCH")
    return matches[0]


def git_blob_sha(candidate: str, relative: str) -> str:
    git_root = Path(subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], text=True
    ).strip())
    prefix = ROOT.relative_to(git_root).as_posix()
    blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{candidate}:{prefix}/{relative}"])
    return hashlib.sha256(blob).hexdigest()


def port_snapshot() -> dict:
    return {
        "windows": {
            str(BACKEND_PORT): len(windows_listeners(BACKEND_PORT)),
            str(OLLAMA_PORT): len(windows_listeners(OLLAMA_PORT)),
        },
        "wsl": {
            str(BACKEND_PORT): len(wsl_listener_pids(BACKEND_PORT)),
            str(OLLAMA_PORT): len(wsl_listener_pids(OLLAMA_PORT)),
        },
    }


def assert_ports_free(snapshot: dict) -> None:
    if any(snapshot[domain][str(port)] for domain in ("windows", "wsl") for port in (BACKEND_PORT, OLLAMA_PORT)):
        raise RuntimeError("PREEXISTING_CROSS_DOMAIN_LISTENER")


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

    auth_path = ROOT / args.authorization
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    browser_path = ROOT / "tools/r1a_browser_acceptance.cjs"
    guard_path = ROOT / "tools/r1a_runtime_guard.py"
    offline_checkpoint = ROOT / "reports/r1a/offline-checkpoint.json"
    identity_ok = (
        auth.get("status") == "ACTIVE_ONE_SHOT"
        and auth.get("approval", {}).get("decision") == "APPROVED"
        and auth.get("product_candidate") == args.candidate
        and auth.get("run_id") == args.run_id
        and auth.get("harness_sha256") == args.harness_sha256
        and auth.get("backend_port") == BACKEND_PORT
        and auth.get("model") == MODEL
        and auth.get("sample_sha256") == SAMPLE_SHA256
        and auth.get("acceptance_hash") == ACCEPTANCE_HASH
        and auth.get("browser_harness_sha256") == sha(browser_path)
        and auth.get("runtime_guard_sha256") == sha(guard_path)
        and auth.get("ollama_wrapper_sha256") == sha(OLLAMA_WRAPPER)
        and auth.get("offline_checkpoint_sha256") == sha(offline_checkpoint)
    )
    if not identity_ok:
        raise SystemExit("authorization identity mismatch")
    if sha(Path(__file__)) != args.harness_sha256:
        raise SystemExit("working harness identity mismatch")
    for relative, expected in (
        ("tools/r1a_live_acceptance.py", args.harness_sha256),
        ("tools/r1a_browser_acceptance.cjs", auth["browser_harness_sha256"]),
        ("tools/r1a_runtime_guard.py", auth["runtime_guard_sha256"]),
        ("tools/r1a_ollama_wrapper.ps1", auth["ollama_wrapper_sha256"]),
    ):
        if git_blob_sha(args.candidate, relative) != expected:
            raise SystemExit(f"candidate blob identity mismatch: {relative}")

    evidence = ROOT / "reports" / "r1a" / args.run_id
    if evidence.exists():
        raise SystemExit("evidence slot already exists")
    evidence.mkdir(parents=True)
    if not WINDOWS_TEMP.is_dir():
        raise SystemExit("bound Windows temp parent is missing")
    runtime = Path(tempfile.mkdtemp(prefix="lvw-r1a-", dir=WINDOWS_TEMP))
    backend = ollama_wrapper = None
    backend_identity = ollama_identity = None
    owner_path = terminal_path = stop_path = None
    streams = []
    phase = "PREFLIGHT"
    terminal = {
        "backend": "NOT_STARTED", "ollama": "NOT_STARTED", "model": "NOT_LOADED",
        "ports": "UNPROVEN", "runtime": "PRESENT",
    }
    result = {
        "schema_version": "lvw.live-receipt/2",
        "run_id": args.run_id,
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": sha(auth_path),
        "candidate_sha": args.candidate,
        "harness_sha256": args.harness_sha256,
        "browser_harness_sha256": auth["browser_harness_sha256"],
        "runtime_guard_sha256": auth["runtime_guard_sha256"],
        "ollama_wrapper_sha256": auth["ollama_wrapper_sha256"],
        "offline_checkpoint_sha256": auth["offline_checkpoint_sha256"],
        "acceptance_hash": ACCEPTANCE_HASH,
        "sample_alias": "TEST_SOURCE/image-sample", "sample_sha256": SAMPLE_SHA256,
        "model": MODEL, "backend_port": BACKEND_PORT, "started_at": utc_now(),
        "attempts": 0, "model_calls": 0, "browser_runs": 0, "phase": phase,
        "decision": "NO_GO", "stage_pass_claim": False,
        "fixed_denominator": {
            "R1A-M01": "PENDING", "R1A-M02": "PENDING", "R1A-M03": "PENDING",
            "R1A-M04": "PENDING", "R1A-M05": "PENDING", "R1A-M06": "PENDING",
            "R1A-M07": "PENDING",
        },
    }
    log_paths = {
        "ollama_stdout": runtime / "ollama.stdout.log",
        "ollama_stderr": runtime / "ollama.stderr.log",
        "wrapper": runtime / "wrapper.log",
        "wrapper_error": runtime / "wrapper-error.txt",
        "backend": runtime / "backend.log",
        "provider": runtime / "provider-ledger.jsonl",
    }
    try:
        if not OLLAMA_EXE.is_file() or auth.get("ollama_exe_sha256") != sha(OLLAMA_EXE):
            raise RuntimeError("OLLAMA_EXECUTABLE_IDENTITY_MISMATCH")
        sample = find_sample()
        before = port_snapshot()
        result["preflight_ports"] = before
        assert_ports_free(before)

        phase = "OLLAMA_START"
        owner_path = runtime / "ollama-owner.json"
        terminal_path = runtime / "ollama-terminal.json"
        stop_path = runtime / "ollama-stop.request"
        win_exe = subprocess.check_output(["wslpath", "-w", str(OLLAMA_EXE)], text=True).strip()
        win_owner = subprocess.check_output(["wslpath", "-w", str(owner_path)], text=True).strip()
        win_terminal = subprocess.check_output(["wslpath", "-w", str(terminal_path)], text=True).strip()
        win_stop = subprocess.check_output(["wslpath", "-w", str(stop_path)], text=True).strip()
        win_out = subprocess.check_output(["wslpath", "-w", str(log_paths["ollama_stdout"])], text=True).strip()
        win_err = subprocess.check_output(["wslpath", "-w", str(log_paths["ollama_stderr"])], text=True).strip()
        win_wrapper_error = subprocess.check_output(
            ["wslpath", "-w", str(log_paths["wrapper_error"])], text=True
        ).strip()
        win_wrapper = subprocess.check_output(["wslpath", "-w", str(OLLAMA_WRAPPER)], text=True).strip()
        wrapper_log = log_paths["wrapper"].open("w", encoding="utf-8")
        streams.append(wrapper_log)
        terminal["ollama"] = "START_ATTEMPTED_OWNER_UNPROVEN"
        ollama_wrapper = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", win_wrapper,
             "-Exe", win_exe, "-Owner", win_owner, "-Terminal", win_terminal,
             "-StopRequest", win_stop, "-StdoutLog", win_out, "-StderrLog", win_err,
             "-ErrorLog", win_wrapper_error, "-MaxSeconds", "420"],
            stdout=wrapper_log, stderr=subprocess.STDOUT, text=True,
        )
        wait_file(owner_path, "OLLAMA", process=ollama_wrapper)
        ollama_identity = json.loads(owner_path.read_text(encoding="utf-8-sig"))
        ollama_identity["pid"] = int(ollama_identity["pid"])
        if not windows_identity_matches(ollama_identity, windows_process(ollama_identity["pid"])):
            raise RuntimeError("OLLAMA_PROCESS_IDENTITY_UNPROVEN")
        wait_url(f"http://127.0.0.1:{OLLAMA_PORT}/api/version", "OLLAMA")
        if windows_listeners(OLLAMA_PORT) != [ollama_identity["pid"]]:
            raise RuntimeError("OLLAMA_LISTENER_OWNERSHIP_UNPROVEN")
        terminal["ollama"] = "RUNNING_OWNED"

        tags = json.loads(wait_url(f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", "OLLAMA_TAGS"))
        models = {item.get("name"): item.get("digest") for item in tags.get("models", [])}
        if models.get(MODEL) != auth.get("model_digest"):
            raise RuntimeError("OLLAMA_MODEL_DIGEST_MISMATCH")

        phase = "BACKEND_START"
        backend_log = log_paths["backend"].open("w", encoding="utf-8")
        streams.append(backend_log)
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "LVW_PORT": str(BACKEND_PORT),
            "LVW_PROVIDER_LEDGER": str(log_paths["provider"]),
        }
        backend = subprocess.Popen(
            [sys.executable, "lvw/run_local.py"], cwd=ROOT, env=env,
            stdout=backend_log, stderr=subprocess.STDOUT, text=True,
        )
        backend_identity = linux_process_identity(backend.pid)
        if backend_identity is None:
            raise RuntimeError("BACKEND_PROCESS_IDENTITY_UNPROVEN")
        wait_url(f"http://127.0.0.1:{BACKEND_PORT}/health", "BACKEND")
        if wsl_listener_pids(BACKEND_PORT) != [backend.pid] or windows_listeners(BACKEND_PORT):
            raise RuntimeError("BACKEND_LISTENER_OWNERSHIP_UNPROVEN")
        terminal["backend"] = "RUNNING_OWNED"

        phase = "BROWSER_PRODUCT_PATH"
        node_path = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
        browser_env = {**os.environ, "NODE_PATH": node_path}
        result["browser_runs"] = 1
        browser = subprocess.run(
            ["node", "tools/r1a_browser_acceptance.cjs", "--url", f"http://127.0.0.1:{BACKEND_PORT}",
             "--sample", str(sample), "--evidence", str(evidence)],
            cwd=ROOT, env=browser_env, capture_output=True, text=True, timeout=240,
        )
        ledger_path = evidence / "browser-ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
        submissions = int(ledger.get("analysis_submissions", 0))
        result["attempts"] = submissions
        result["browser_exit_code"] = browser.returncode
        result["browser_stdout_sha256"] = hashlib.sha256(browser.stdout.encode()).hexdigest()
        result["browser_stderr_tail"] = re.sub(
            r"(?i)[A-Z]:[\\/][^\r\n\t ]+", "<redacted-path>", browser.stderr[-1200:]
        )
        if browser.returncode:
            raise RuntimeError("BROWSER_PRODUCT_PATH_FAILED")
        browser_result = json.loads((evidence / "browser-result.json").read_text(encoding="utf-8"))
        if not browser_result.get("passed") or browser_result.get("blocked_non_loopback_requests"):
            raise RuntimeError("BROWSER_NETWORK_ORACLE_FAILED")
        provider_entries = [json.loads(line) for line in log_paths["provider"].read_text(
            encoding="utf-8").splitlines() if line.strip()]
        provider_calls = [item for item in provider_entries if item.get("event") == "provider_call_started"]
        provider_success = [item for item in provider_entries if item.get("event") == "provider_call_completed"]
        result["model_calls"] = len(provider_calls)
        result["provider_ledger"] = provider_entries
        if len(provider_calls) != 1 or len(provider_success) != 1 or submissions != 1:
            raise RuntimeError("PROVIDER_CALL_DENOMINATOR_MISMATCH")

        phase = "MODEL_UNLOAD"
        running = json.loads(wait_url(f"http://127.0.0.1:{OLLAMA_PORT}/api/ps", "OLLAMA_PS"))
        if running.get("models") != []:
            raise RuntimeError("MODEL_UNLOAD_NOT_PROVEN")
        terminal["model"] = "UNLOADED"
        result["fixed_denominator"] = {
            "R1A-M01": "PASS_OFFLINE_BOUNDARIES", "R1A-M02": "PASS",
            "R1A-M03": "PASS", "R1A-M04": "PASS", "R1A-M05": "PASS",
            "R1A-M06": "WAIT_INDEPENDENT_REVIEW", "R1A-M07": "PASS",
        }
        result["decision"] = "READY_FOR_INDEPENDENT_REVIEW"
    except Exception as exc:
        result["error"] = type(exc).__name__ + ":" + str(exc)
    finally:
        result["phase"] = phase
        ledger_path = evidence / "browser-ledger.json"
        if ledger_path.is_file():
            try:
                ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
                submissions = int(ledger.get("analysis_submissions", 0))
                result["attempts"] = max(result["attempts"], submissions)
            except Exception:
                result["ledger_status"] = "UNPROVEN"
        if log_paths["provider"].is_file():
            try:
                provider_entries = [json.loads(line) for line in log_paths["provider"].read_text(
                    encoding="utf-8").splitlines() if line.strip()]
                result["provider_ledger"] = provider_entries
                result["model_calls"] = sum(
                    item.get("event") == "provider_call_started" for item in provider_entries
                )
            except Exception:
                result["provider_ledger_status"] = "UNPROVEN"
        if result["model_calls"] > 0 and terminal["model"] == "NOT_LOADED":
            terminal["model"] = "LOAD_ATTEMPTED_UNLOAD_UNPROVEN"
        cleanup_errors: list[str] = []
        try:
            if backend is not None:
                if backend.poll() is not None:
                    terminal["backend"] = "STOPPED"
                elif backend_identity and linux_identity_matches(backend_identity):
                    backend.terminate()
                    try:
                        backend.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        if linux_identity_matches(backend_identity):
                            backend.kill()
                            backend.wait(timeout=5)
                    terminal["backend"] = "STOPPED" if backend.poll() is not None else "UNPROVEN"
                else:
                    terminal["backend"] = "REFUSED_NON_OWNED_IDENTITY"
        except Exception as exc:
            terminal["backend"] = "UNPROVEN"
            cleanup_errors.append("BACKEND_CLEANUP:" + type(exc).__name__)

        try:
            if ollama_wrapper is not None:
                if ollama_wrapper.poll() is None and stop_path is not None:
                    stop_path.write_text("stop\n", encoding="ascii")
                try:
                    ollama_wrapper.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    cleanup_errors.append("WRAPPER_STOP_TIMEOUT")
                wrapper_terminal = None
                if terminal_path is not None and terminal_path.is_file():
                    wrapper_terminal = json.loads(terminal_path.read_text(encoding="utf-8-sig"))
                    result["wrapper_terminal"] = wrapper_terminal
                    if wrapper_terminal.get("lease_expired") is True:
                        cleanup_errors.append("WRAPPER_LEASE_EXPIRED")
                if wrapper_terminal and wrapper_terminal.get("child_exited") is True:
                    terminal_pid = wrapper_terminal.get("pid")
                    owner_pid = ollama_identity.get("pid") if ollama_identity else None
                    if terminal_pid is None:
                        terminal["ollama"] = "START_FAILED_NO_CHILD"
                    elif owner_pid is None or int(terminal_pid) == int(owner_pid):
                        terminal["ollama"] = "STOPPED"
                    else:
                        terminal["ollama"] = "UNPROVEN"
                        cleanup_errors.append("WRAPPER_TERMINAL_IDENTITY_MISMATCH")
                else:
                    terminal["ollama"] = "UNPROVEN"
                    cleanup_errors.append("WRAPPER_TERMINAL_MISSING_OR_INCOMPLETE")
                result["wrapper_exit_code"] = ollama_wrapper.poll()
        except Exception as exc:
            terminal["ollama"] = "UNPROVEN"
            cleanup_errors.append("WRAPPER_CLEANUP:" + type(exc).__name__)
        for stream in streams:
            try:
                stream.close()
            except Exception as exc:
                cleanup_errors.append("STREAM_CLEANUP:" + type(exc).__name__)

        try:
            after = port_snapshot()
            result["cleanup_ports"] = after
            terminal["ports"] = "EMPTY" if not any(
                after[domain][str(port)]
                for domain in ("windows", "wsl")
                for port in (BACKEND_PORT, OLLAMA_PORT)
            ) else "NOT_EMPTY"
        except Exception as exc:
            terminal["ports"] = "UNPROVEN"
            cleanup_errors.append("PORT_AUDIT:" + type(exc).__name__)
        result["diagnostics"] = {
            "ollama_stdout_tail": sanitized_tail(log_paths["ollama_stdout"]),
            "ollama_stderr_tail": sanitized_tail(log_paths["ollama_stderr"]),
            "wrapper_tail": sanitized_tail(log_paths["wrapper"]),
            "wrapper_error": sanitized_tail(log_paths["wrapper_error"]),
            "backend_tail": sanitized_tail(log_paths["backend"]),
        }
        if ollama_wrapper is None or ollama_wrapper.poll() is not None:
            try:
                shutil.rmtree(runtime, ignore_errors=False)
            except Exception as exc:
                cleanup_errors.append("RUNTIME_REMOVAL:" + type(exc).__name__)
        else:
            cleanup_errors.append("RUNTIME_RETAINED_FOR_LIVE_WRAPPER")
        terminal["runtime"] = "REMOVED" if not runtime.exists() else "PRESENT"
        result["cleanup_errors"] = cleanup_errors
        result["terminal"] = terminal
        cleanup_ok = (
            terminal["backend"] in {"NOT_STARTED", "STOPPED"}
            and terminal["ollama"] in {"NOT_STARTED", "START_FAILED_NO_CHILD", "STOPPED"}
            and terminal["model"] in {"NOT_LOADED", "UNLOADED"}
            and terminal["ports"] == "EMPTY"
            and terminal["runtime"] == "REMOVED"
            and not cleanup_errors
        )
        if not cleanup_ok:
            result["decision"] = "NO_GO_CLEANUP_UNPROVEN"
        result["finished_at"] = utc_now()
        (evidence / "live-receipt.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"decision": result["decision"], "phase": phase, "terminal": terminal}, ensure_ascii=False))
    return 0 if result["decision"] == "READY_FOR_INDEPENDENT_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
