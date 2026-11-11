#!/usr/bin/env python3
"""independent-01 独审：自建真实四步离线链路执行器（不复用实现者的 runner）。

与 reports/v0-s3/preparation-04/implementation/run_offline_chain.py 的差异：
  * 不复用实现者的 runner，只复用被审 CLI 本身；
  * 目标沙箱父目录/目标目录/哨兵/包名全部使用中文与空格；
  * 执行用的工具字节强制等于候选 commit 中的 blob 字节，否则拒绝执行；
  * 链路结束后删除工作根（含包 ZIP），并实测删除结果；
  * 每一步保留真实命令、退出码、stdout、stderr 原始字节。

用法:
  python3 chain_independent.py --repo <repo-root> --candidate <sha> \
      --work-root <owned tmp dir> --out-dir <evidence dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

TOOL_REL = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_incremental_package.py"
MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
TOOL_NAME = "v0_incremental_package.py"

SANDBOX_DIR = "隔离 沙箱根"
TARGET_DIR = "隔离 目标 目录"
SENTINEL_NAME = "哨兵 文件.txt"
SENTINEL_BYTES = "哨兵原始字节-不得改动\n".encode("utf-8")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_out(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise SystemExit(
            "git %s failed: %s" % (" ".join(args), proc.stderr.decode("utf-8", "replace"))
        )
    return proc.stdout


def redact(text, roots):
    out = str(text)
    for root in roots:
        if root:
            out = out.replace(str(root), "<redacted-root>")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--work-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    candidate = args.candidate
    work_root = Path(args.work_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(git_out(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    resolved = git_out(repo, "rev-parse", "--verify", candidate + "^{commit}").decode().strip()
    committed_tool = git_out(repo, "cat-file", "blob", "%s:%s" % (candidate, TOOL_REL))
    tool_path = repo_root / TOOL_REL
    tool_bytes = Path(tool_path).read_bytes()
    tool_sha = sha256_bytes(tool_bytes)
    bound_sha = sha256_bytes(committed_tool)
    if tool_sha != bound_sha:
        raise SystemExit("执行工具字节 != 候选 commit blob 字节，拒绝执行")

    # 自有工作根（不含任何用户路径）
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    sandbox_parent = work_root / SANDBOX_DIR
    target = sandbox_parent / TARGET_DIR
    sandbox_parent.mkdir(parents=True)
    target.mkdir(parents=True)
    (sandbox_parent / MARKER_NAME).write_text(
        json.dumps({"magic": MARKER_MAGIC, "tool": TOOL_NAME}), encoding="utf-8"
    )
    sentinel = target / SENTINEL_NAME
    sentinel.write_bytes(SENTINEL_BYTES)
    sentinel_before = sha256_file(sentinel)

    package = work_root / "LVW_V0 增量包.zip"
    steps = []
    redact_roots = [str(work_root), str(repo_root)]

    def run_step(index, label, argv):
        cmd = [sys.executable, str(tool_path)] + argv
        printable = "python3 " + " ".join(redact(a, redact_roots) for a in cmd[1:])
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(repo_root), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stem = "%02d-%s" % (index, label)
        (raw_dir / (stem + ".stdout.log")).write_bytes(proc.stdout)
        (raw_dir / (stem + ".stderr.log")).write_bytes(proc.stderr)
        (raw_dir / (stem + ".exit.log")).write_text("%d\n" % proc.returncode, encoding="utf-8")
        (raw_dir / (stem + ".command.log")).write_text(printable + "\n", encoding="utf-8")
        step = {
            "index": index, "label": label, "command": printable,
            "exit_code": proc.returncode,
            "stdout_sha256": sha256_bytes(proc.stdout),
            "stderr_sha256": sha256_bytes(proc.stderr),
            "raw": {
                "stdout": "raw/%s.stdout.log" % stem,
                "stderr": "raw/%s.stderr.log" % stem,
                "exit": "raw/%s.exit.log" % stem,
                "command": "raw/%s.command.log" % stem,
            },
        }
        try:
            step["stdout_json"] = json.loads(proc.stdout.decode("utf-8"))
        except ValueError:
            step["stdout_json"] = None
        steps.append(step)
        return step

    build = run_step(1, "build", [
        "build", "--repo", str(repo), "--commit", candidate,
        "--out", str(package),
        "--receipt-out", str(out_dir / "build-receipt.json"),
        "--redact-root", str(work_root), "--redact-root", str(repo_root),
    ])
    if build["exit_code"] != 0:
        raise SystemExit("build 失败 exit=%d" % build["exit_code"])

    package_sha = sha256_file(package)
    package_size = package.stat().st_size

    # 重复构建一次，验证同候选字节可复算（输出到不同文件名）
    package2 = work_root / "LVW_V0 增量包 复算.zip"
    build2 = run_step(5, "build-repro", [
        "build", "--repo", str(repo), "--commit", candidate,
        "--out", str(package2),
        "--receipt-out", str(out_dir / "build-receipt-repro.json"),
        "--redact-root", str(work_root), "--redact-root", str(repo_root),
    ])
    repro_sha = sha256_file(package2) if build2["exit_code"] == 0 else None

    diagnose = run_step(2, "diagnose", [
        "diagnose", "--package", str(package),
        "--target", str(target), "--sandbox-parent", str(sandbox_parent),
        "--receipt-out", str(out_dir / "diagnose-receipt.json"),
        "--redact-root", str(work_root), "--redact-root", str(repo_root),
    ])
    if diagnose["exit_code"] != 0:
        raise SystemExit("diagnose 失败 exit=%d" % diagnose["exit_code"])

    install = run_step(3, "install", [
        "install", "--package", str(package),
        "--sandbox-parent", str(sandbox_parent), "--target", str(target),
        "--receipt-out", str(out_dir / "install-receipt.json"),
        "--redact-root", str(work_root), "--redact-root", str(repo_root),
    ])
    if install["exit_code"] != 0:
        raise SystemExit("install 失败 exit=%d" % install["exit_code"])

    sentinel_after_install = sha256_file(sentinel)
    installed_files = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()
    )
    staging_leftovers_after_install = sorted(
        e.name for e in sandbox_parent.iterdir() if e.name.startswith(".lvw-v0-stage-")
    )

    rollback = run_step(4, "rollback", [
        "rollback", "--receipt", str(out_dir / "install-receipt.json"),
        "--target", str(target),
        "--receipt-out", str(out_dir / "rollback-receipt.json"),
        "--redact-root", str(work_root), "--redact-root", str(repo_root),
    ])
    if rollback["exit_code"] != 0:
        raise SystemExit("rollback 失败 exit=%d" % rollback["exit_code"])

    sentinel_after_rollback = sha256_file(sentinel)
    remaining_files = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()
    )
    remaining_dirs = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_dir()
    )
    staging_leftovers = sorted(
        e.name for e in sandbox_parent.iterdir() if e.name.startswith(".lvw-v0-stage-")
    )

    with zipfile.ZipFile(package) as archive:
        manifest_bytes = archive.read("meta/manifest.json")
        members = sorted(i.filename for i in archive.infolist())
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    canonical = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                 + "\n").encode("utf-8")
    fingerprint = hashlib.sha256()
    for item in sorted(manifest["items"], key=lambda e: e["install_path"]):
        fingerprint.update(("%s:%s\n" % (item["install_path"], item["sha256"])).encode())

    # --- 包使用后删除 + 工作根清理实测 --------------------------------- #
    package_sha_before_delete = package_sha
    package2.unlink(missing_ok=True)
    package.unlink(missing_ok=True)
    package_removed = not package.exists() and not package2.exists()
    work_root_removed = False
    work_root_disposition = "pending"
    shutil.rmtree(work_root, ignore_errors=True)
    work_root_removed = not work_root.exists()
    work_root_disposition = "removed_by_runner"

    summary = {
        "kind": "S3_PREP_B_INDEPENDENT_OFFLINE_CHAIN",
        "scope": "independent offline preparation review; not product Gate0, not a Stage PASS",
        "repo_root": str(repo_root),
        "candidate_commit": candidate,
        "candidate_commit_resolved": resolved,
        "tool_path_in_repo": TOOL_REL,
        "tool_sha256": tool_sha,
        "tool_matches_candidate_commit_blob": tool_sha == bound_sha,
        "package_sha256": package_sha_before_delete,
        "package_size_bytes": package_size,
        "package_sha256_rebuild": repro_sha,
        "package_byte_reproducible": repro_sha is not None and repro_sha == package_sha,
        "member_count": len(members),
        "members": members,
        "manifest_sha256": sha256_bytes(canonical),
        "manifest_sha256_of_raw_member": sha256_bytes(manifest_bytes),
        "payload_fingerprint_sha256": fingerprint.hexdigest(),
        "payload_item_count": manifest["payload_item_count"],
        "payload_expanded_bytes": manifest["payload_expanded_bytes"],
        "manifest_source_commit": manifest.get("source_commit"),
        "manifest_tool_sha256": manifest.get("tool", {}).get("sha256"),
        "manifest_tool_provenance": manifest.get("tool", {}).get("provenance"),
        "steps": [
            {"index": s["index"], "label": s["label"], "command": s["command"],
             "exit_code": s["exit_code"], "stdout_sha256": s["stdout_sha256"],
             "stderr_sha256": s["stderr_sha256"], "raw": s["raw"]}
            for s in steps
        ],
        "sentinel": {
            "sha256_before_install": sentinel_before,
            "sha256_after_install": sentinel_after_install,
            "sha256_after_rollback": sentinel_after_rollback,
            "unchanged_by_install": sentinel_before == sentinel_after_install,
            "unchanged_by_rollback": sentinel_before == sentinel_after_rollback,
        },
        "installed_file_count": len(installed_files),
        "installed_files": installed_files,
        "remaining_files_after_rollback": remaining_files,
        "remaining_dirs_after_rollback": remaining_dirs,
        "staging_leftovers_after_install": staging_leftovers_after_install,
        "staging_leftovers_after_rollback": staging_leftovers,
        "package_removed_after_use": package_removed,
        "work_root_removed": work_root_removed,
        "work_root_disposition": work_root_disposition,
        "product_runtime_calls": 0,
    }
    (out_dir / "chain-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
