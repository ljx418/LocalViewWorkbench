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


def wait_file(path: Path, phase: str, timeout: int = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size:
            return
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
    identity_ok = (
        auth.get("status") == "ACTIVE_ONE_SHOT"
        and auth.get("approval", {}).get("decision") == "APPROVED"
        and auth.get("product_candidate") == args.candidate
        and auth.get("run_id") == args.run_id
        and auth.get("harness_sha256") == args.harness_sha256
        and auth.get("backend_port") == BACKEND_PORT
        and auth.get("model") == MODEL
        and auth.get("sample_sha256") == SAMPLE_SHA256
        and auth.get("browser_harness_sha256") == sha(browser_path)
        and auth.get("runtime_guard_sha256") == sha(guard_path)
    )
    if not identity_ok:
        raise SystemExit("authorization identity mismatch")
    if sha(Path(__file__)) != args.harness_sha256:
        raise SystemExit("working harness identity mismatch")
    for relative, expected in (
        ("tools/r1a_live_acceptance.py", args.harness_sha256),
        ("tools/r1a_browser_acceptance.cjs", auth["browser_harness_sha256"]),
        ("tools/r1a_runtime_guard.py", auth["runtime_guard_sha256"]),
    ):
        if git_blob_sha(args.candidate, relative) != expected:
            raise SystemExit(f"candidate blob identity mismatch: {relative}")

    evidence = ROOT / "reports" / "r1a" / args.run_id
    if evidence.exists():
        raise SystemExit("evidence slot already exists")
    evidence.mkdir(parents=True)
    runtime = Path(tempfile.mkdtemp(prefix="lvw-r1a-"))
    backend = ollama_wrapper = None
    backend_identity = ollama_identity = None
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
        "sample_alias": "TEST_SOURCE/image-sample", "sample_sha256": SAMPLE_SHA256,
        "model": MODEL, "backend_port": BACKEND_PORT, "started_at": utc_now(),
        "attempts": 0, "model_calls": 0, "browser_runs": 0, "phase": phase,
        "decision": "NO_GO", "stage_pass_claim": False,
        "fixed_denominator": {
            "A01": "PENDING", "A02": "PENDING", "A03": "PENDING", "A05": "PENDING",
            "F01": "PENDING", "Q01": "PENDING", "X01": "PENDING",
        },
    }
    log_paths = {
        "ollama_stdout": runtime / "ollama.stdout.log",
        "ollama_stderr": runtime / "ollama.stderr.log",
        "backend": runtime / "backend.log",
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
        wrapper = runtime / "ollama.ps1"
        win_exe = subprocess.check_output(["wslpath", "-w", str(OLLAMA_EXE)], text=True).strip()
        win_owner = subprocess.check_output(["wslpath", "-w", str(owner_path)], text=True).strip()
        win_out = subprocess.check_output(["wslpath", "-w", str(log_paths["ollama_stdout"])], text=True).strip()
        win_err = subprocess.check_output(["wslpath", "-w", str(log_paths["ollama_stderr"])], text=True).strip()
        quote = lambda value: value.replace("'", "''")
        wrapper.write_text(
            "$env:OLLAMA_HOST='127.0.0.1:11434'\n$env:OLLAMA_NO_CLOUD='1'\n"
            "$env:NO_PROXY='127.0.0.1,localhost'\n"
            f"$p=Start-Process -FilePath '{quote(win_exe)}' -ArgumentList @('serve') -PassThru -WindowStyle Hidden "
            f"-RedirectStandardOutput '{quote(win_out)}' -RedirectStandardError '{quote(win_err)}'\n"
            "$o=[pscustomobject]@{pid=$p.Id;start_filetime_utc=$p.StartTime.ToFileTimeUtc().ToString();"
            "executable_path=$p.Path}\n$u=New-Object System.Text.UTF8Encoding($false)\n"
            f"[IO.File]::WriteAllText('{quote(win_owner)}',($o|ConvertTo-Json -Compress),$u)\n"
            "$p.WaitForExit()\nexit $p.ExitCode\n",
            encoding="utf-8",
        )
        win_wrapper = subprocess.check_output(["wslpath", "-w", str(wrapper)], text=True).strip()
        ollama_wrapper = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", win_wrapper],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        wait_file(owner_path, "OLLAMA")
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
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LVW_PORT": str(BACKEND_PORT)}
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
        result["model_calls"] = submissions
        result["browser_exit_code"] = browser.returncode
        result["browser_stdout_sha256"] = hashlib.sha256(browser.stdout.encode()).hexdigest()
        result["browser_stderr_tail"] = re.sub(
            r"(?i)[A-Z]:[\\/][^\r\n\t ]+", "<redacted-path>", browser.stderr[-1200:]
        )
        if browser.returncode:
            raise RuntimeError("BROWSER_PRODUCT_PATH_FAILED")
        browser_result = json.loads((evidence / "browser-result.json").read_text(encoding="utf-8"))
        if not browser_result.get("passed") or browser_result.get("non_loopback_requests"):
            raise RuntimeError("BROWSER_NETWORK_ORACLE_FAILED")

        phase = "MODEL_UNLOAD"
        running = json.loads(wait_url(f"http://127.0.0.1:{OLLAMA_PORT}/api/ps", "OLLAMA_PS"))
        if running.get("models") != []:
            raise RuntimeError("MODEL_UNLOAD_NOT_PROVEN")
        terminal["model"] = "UNLOADED"
        result["fixed_denominator"] = {
            "A01": "PASS", "A02": "PASS", "A03": "PASS", "A05": "PASS",
            "F01": "PASS", "Q01": "WAIT_INDEPENDENT_REVIEW", "X01": "PASS",
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
                result["model_calls"] = max(result["model_calls"], submissions)
            except Exception:
                result["ledger_status"] = "UNPROVEN"
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
            if ollama_identity is not None:
                current = windows_process(int(ollama_identity["pid"]))
                if current is None:
                    terminal["ollama"] = "STOPPED"
                elif windows_identity_matches(ollama_identity, current):
                    ps(f"Stop-Process -Id {ollama_identity['pid']} -Force -ErrorAction Stop")
                    terminal["ollama"] = (
                        "STOPPED" if windows_process(int(ollama_identity["pid"])) is None else "UNPROVEN"
                    )
                else:
                    terminal["ollama"] = "REFUSED_NON_OWNED_IDENTITY"
        except Exception as exc:
            terminal["ollama"] = "UNPROVEN"
            cleanup_errors.append("OLLAMA_CLEANUP:" + type(exc).__name__)
        try:
            if ollama_wrapper is not None:
                try:
                    ollama_wrapper.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    ollama_wrapper.terminate()
                    ollama_wrapper.wait(timeout=5)
        except Exception as exc:
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
            "backend_tail": sanitized_tail(log_paths["backend"]),
        }
        try:
            shutil.rmtree(runtime, ignore_errors=False)
        except Exception as exc:
            cleanup_errors.append("RUNTIME_REMOVAL:" + type(exc).__name__)
        terminal["runtime"] = "REMOVED" if not runtime.exists() else "PRESENT"
        result["cleanup_errors"] = cleanup_errors
        result["terminal"] = terminal
        cleanup_ok = (
            terminal["backend"] in {"NOT_STARTED", "STOPPED"}
            and terminal["ollama"] in {"NOT_STARTED", "STOPPED"}
            and terminal["model"] in {"NOT_LOADED", "UNLOADED"}
            and terminal["ports"] == "EMPTY"
            and terminal["runtime"] == "REMOVED"
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
