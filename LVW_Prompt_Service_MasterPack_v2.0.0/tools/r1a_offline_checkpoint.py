#!/usr/bin/env python3
"""Run R1a offline gates and write candidate-bound evidence; never starts product services."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "r1a" / "offline-checkpoint.json"


def run(name: str, command: list[str], cwd: Path = ROOT) -> dict:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False,
                             env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd.relative_to(ROOT)) or ".",
        "exit_code": process.returncode,
        "stdout_sha256": hashlib.sha256(process.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr.encode()).hexdigest(),
        "stdout_tail": process.stdout[-2000:],
        "stderr_tail": process.stderr[-2000:],
    }


def runtime_scan() -> dict:
    source_files = [
        *sorted((ROOT / "lvw" / "backend").rglob("*.py")),
        *sorted((ROOT / "lvw" / "frontend" / "src").rglob("*.*")),
        ROOT / "lvw" / "frontend" / "index.html",
    ]
    findings: list[dict] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in [
            (r"https?://(?!127\.0\.0\.1:11434/api/chat)", "non_loopback_url"),
            (r"fetch\s*\(\s*[`\"']https?://", "browser_absolute_fetch"),
            (r"\b(?:gradio|nicegui)\b", "forbidden_ui_framework"),
            (r"localStorage", "forbidden_local_storage_database"),
        ]:
            for match in re.finditer(pattern, text, flags=re.I):
                findings.append({"file": str(path.relative_to(ROOT)), "kind": label,
                                 "offset": match.start()})
    dist_index = (ROOT / "lvw" / "frontend" / "dist" / "index.html").read_text(encoding="utf-8")
    remote_asset = bool(re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://', dist_index, re.I))
    return {"passed": not findings and not remote_asset, "findings": findings,
            "remote_runtime_asset": remote_asset, "files_scanned": len(source_files)}


def main() -> int:
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False).returncode != 0:
        print("candidate worktree has tracked changes; commit before checkpoint", file=sys.stderr)
        return 2
    candidate = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    wrapper_win = subprocess.check_output(
        ["wslpath", "-w", str(ROOT / "tools" / "r1a_ollama_wrapper.ps1")], text=True
    ).strip().replace("'", "''")
    commands = [
        run("backend_unit_api_contract", [sys.executable, "-m", "pytest", "lvw/tests", "-q"]),
        run("frontend_offline_lock_install", ["npm", "ci", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"], ROOT / "lvw" / "frontend"),
        run("frontend_domain_tests", ["npm", "run", "test"], ROOT / "lvw" / "frontend"),
        run("frontend_typecheck", ["npm", "run", "typecheck"], ROOT / "lvw" / "frontend"),
        run("frontend_production_build", ["npm", "run", "build"], ROOT / "lvw" / "frontend"),
        run("python_harness_syntax", [sys.executable, "-c",
            "compile(open('tools/r1a_live_acceptance.py',encoding='utf-8').read(),'r1a_live_acceptance.py','exec')"]),
        run("browser_harness_syntax", ["node", "--check", "tools/r1a_browser_acceptance.cjs"]),
        run("powershell_wrapper_syntax", ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('"
            + wrapper_win + "',[ref]$t,[ref]$e)>$null;if($e.Count){$e|ForEach-Object{$_.Message};exit 1}"]),
        run("v0_regression", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "LVW_V0_RuntimePatch/tests", "-p", "test_*.py"]),
        run("pack_schema", [sys.executable, "tools/verify_pack.py", "--schema"]),
        run("governance_negative_tests", [sys.executable, "tools/verify_governance.py", "--self-test"]),
    ]
    scan = runtime_scan()
    dist_files = []
    for path in sorted((ROOT / "lvw" / "frontend" / "dist").rglob("*")):
        if path.is_file():
            dist_files.append({"path": str(path.relative_to(ROOT)),
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "bytes": path.stat().st_size})
    all_passed = all(item["exit_code"] == 0 for item in commands) and scan["passed"]
    result = {
        "schema_version": "lvw.r1a.offline-checkpoint/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_sha": candidate,
        "stage_id": "R1a",
        "acceptance_hash": "82a3736ab77ee98e301d7e055a78b160774c9c09692288db89c5a2768bfe39ab",
        "scope": "OFFLINE_ONLY_NO_OLLAMA_NO_BROWSER_NO_REAL_MEDIA",
        "commands": commands,
        "runtime_scan": scan,
        "dist_artifacts": dist_files,
        "fixed_case_disposition": {
            "R1A-M01": "PASS_OFFLINE_BOUNDARIES",
            "R1A-M02": "WAIT_AUTH_REAL_MODEL",
            "R1A-M03": "WAIT_AUTH_BROWSER_MANUAL_ZERO_CALL",
            "R1A-M04": "WAIT_AUTH_BROWSER_ADOPTION_EXPORT",
            "R1A-M05": "WAIT_AUTH_BROWSER_EXPERIENCE",
            "R1A-M06": "WAIT_AUTH_INDEPENDENT_QUALITY",
            "R1A-M07": "WAIT_AUTH_REAL_FAILURE_AND_CLEANUP",
        },
        "decision": "READY_FOR_LIVE_AUTH" if all_passed else "CHANGES_REQUIRED",
        "stage_pass_claim": False,
        "product_tests_executed": False,
        "target_runtime_touched": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_sha": candidate, "decision": result["decision"],
                      "commands_passed": sum(item["exit_code"] == 0 for item in commands),
                      "commands_total": len(commands), "runtime_scan": scan["passed"]},
                     ensure_ascii=False, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
