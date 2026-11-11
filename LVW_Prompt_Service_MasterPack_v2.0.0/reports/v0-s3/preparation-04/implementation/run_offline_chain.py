#!/usr/bin/env python3
"""run_offline_chain.py — S3-PREP-B 真实离线包链路执行器。

从本工具候选 commit 执行**一次**真实仓库 payload 的离线链路：
build → diagnose → 隔离沙箱 install → rollback。

把每一步的原始命令、stdout、stderr、退出码、候选 SHA、工具 SHA、固定集合
fingerprint、包 hash/大小、安装前后哨兵 hash 与真实清理测量写入证据目录。

边界：纯离线。无媒体、无模型、无 GPU、无宿主配置、无服务、无网络、无下载。
包与临时副本不进入 Git；证据写入时对绝对路径脱敏。

用法：
    python3 run_offline_chain.py --repo <repo-root> --candidate <commit-sha> \
        --evidence-dir <dir> [--work-dir <dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

TOOL_RELATIVE_PATH = "tools/v0_incremental_package.py"
SANDBOX_MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
SANDBOX_MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
TOOL_NAME = "v0_incremental_package.py"

#: 隔离沙箱与目标目录都带中文与空格，覆盖路径可执行性。
SANDBOX_DIR_NAME = "隔离 沙箱根"
TARGET_DIR_NAME = "隔离 目标 目录"
SENTINEL_NAME = "哨兵 文件.txt"
SENTINEL_BYTES = b"SENTINEL-ORIGINAL-BYTES\n"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout


def git_probe(repo, *args):
    """执行 git 并允许失败（返回 (returncode, stdout)）。"""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return proc.returncode, proc.stdout


class ChainRunner:
    def __init__(self, repo, candidate, evidence_dir, work_dir=None):
        self.repo = Path(repo).resolve()
        self.candidate = candidate
        self.evidence_dir = Path(evidence_dir).resolve()
        self.raw_dir = self.evidence_dir / "raw"
        self.steps = []
        self.owns_work_dir = work_dir is None
        if work_dir is None:
            self.work_dir = Path(
                tempfile.mkdtemp(prefix="lvw 离线包链路 ", dir=os.environ.get("TMPDIR", "/tmp"))
            ).resolve()
        else:
            self.work_dir = Path(work_dir).resolve()
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # -- 执行 ------------------------------------------------------------- #

    def run_step(self, index, label, args, cwd=None):
        """执行一条 CLI 命令，保留原始命令/stdout/stderr/退出码。"""
        command = [sys.executable, str(self.tool_path), *args]
        printable = "python3 " + " ".join(
            self._redact_text(arg) for arg in command[1:]
        )
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd or self.repo),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout_text = proc.stdout.decode("utf-8", "replace")
        stderr_text = proc.stderr.decode("utf-8", "replace")
        stem = f"{index:02d}-{label}"
        (self.raw_dir / f"{stem}.stdout.log").write_text(stdout_text, encoding="utf-8")
        (self.raw_dir / f"{stem}.stderr.log").write_text(stderr_text, encoding="utf-8")
        (self.raw_dir / f"{stem}.exit.log").write_text(
            f"{proc.returncode}\n", encoding="utf-8"
        )
        (self.raw_dir / f"{stem}.command.log").write_text(printable + "\n", encoding="utf-8")
        try:
            payload = json.loads(stdout_text)
        except ValueError:
            payload = None
        step = {
            "index": index,
            "label": label,
            "command": printable,
            "exit_code": proc.returncode,
            "stdout_json": payload,
            "raw": {
                "stdout": f"raw/{stem}.stdout.log",
                "stderr": f"raw/{stem}.stderr.log",
                "exit": f"raw/{stem}.exit.log",
                "command": f"raw/{stem}.command.log",
            },
        }
        self.steps.append(step)
        return step

    def _redact_text(self, text):
        """把工作目录与仓库根的绝对路径替换为占位符。"""
        value = str(text)
        for needle, token in (
            (str(self.work_dir), "<work-dir>"),
            (str(getattr(self, "repo_root", "")), "<repo-root>"),
        ):
            if needle:
                value = value.replace(needle, token)
        return value

    # -- 主流程 ----------------------------------------------------------- #

    def execute(self):
        tool_rel = self._tool_relative_path()
        self.repo_root = Path(
            git(self.repo, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        ).resolve()
        self.tool_path = self.repo_root / tool_rel
        tool_bytes = Path(self.tool_path).read_bytes()
        committed_tool = git(self.repo, "cat-file", "blob", f"{self.candidate}:{tool_rel}")
        tool_sha = sha256_bytes(tool_bytes)
        tool_bound = sha256_bytes(committed_tool)
        if tool_sha != tool_bound:
            raise SystemExit(
                "执行用的工具字节与候选 commit 中的工具字节不一致，拒绝继续"
            )

        sandbox_parent = self.work_dir / SANDBOX_DIR_NAME
        target = sandbox_parent / TARGET_DIR_NAME
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        (sandbox_parent / SANDBOX_MARKER_NAME).write_text(
            json.dumps({"magic": SANDBOX_MARKER_MAGIC, "tool": TOOL_NAME}),
            encoding="utf-8",
        )
        sentinel = target / SENTINEL_NAME
        sentinel.write_bytes(SENTINEL_BYTES)
        sentinel_sha_before = sha256_file(sentinel)

        package = self.work_dir / "LVW_V0 增量包.zip"
        build_receipt = self.evidence_dir / "build-receipt.json"
        diagnose_receipt = self.evidence_dir / "diagnose-receipt.json"
        install_receipt = self.evidence_dir / "install-receipt.json"
        rollback_receipt = self.evidence_dir / "rollback-receipt.json"

        build = self.run_step(
            1,
            "build",
            [
                "build",
                "--repo", str(self.repo),
                "--commit", self.candidate,
                "--out", str(package),
                "--receipt-out", str(build_receipt),
                "--redact-root", str(self.work_dir),
                "--redact-root", str(self.repo_root),
            ],
        )
        if build["exit_code"] != 0:
            raise SystemExit(f"build 失败，退出码 {build['exit_code']}")

        diagnose = self.run_step(
            2,
            "diagnose",
            [
                "diagnose",
                "--package", str(package),
                "--target", str(target),
                "--sandbox-parent", str(sandbox_parent),
                "--receipt-out", str(diagnose_receipt),
                "--redact-root", str(self.work_dir),
                "--redact-root", str(self.repo_root),
            ],
        )
        if diagnose["exit_code"] != 0:
            raise SystemExit(f"diagnose 失败，退出码 {diagnose['exit_code']}")

        install = self.run_step(
            3,
            "install",
            [
                "install",
                "--package", str(package),
                "--sandbox-parent", str(sandbox_parent),
                "--target", str(target),
                "--receipt-out", str(install_receipt),
                "--redact-root", str(self.work_dir),
                "--redact-root", str(self.repo_root),
            ],
        )
        if install["exit_code"] != 0:
            raise SystemExit(f"install 失败，退出码 {install['exit_code']}")

        sentinel_sha_after_install = sha256_file(sentinel)
        installed_files = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        )

        rollback = self.run_step(
            4,
            "rollback",
            [
                "rollback",
                "--receipt", str(install_receipt),
                "--target", str(target),
                "--receipt-out", str(rollback_receipt),
                "--redact-root", str(self.work_dir),
                "--redact-root", str(self.repo_root),
            ],
        )
        if rollback["exit_code"] != 0:
            raise SystemExit(f"rollback 失败，退出码 {rollback['exit_code']}")

        sentinel_sha_after_rollback = sha256_file(sentinel)
        sentinel_bytes_after_rollback = sentinel.read_bytes()
        remaining_files = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        )
        staging_leftovers = sorted(
            entry.name
            for entry in sandbox_parent.iterdir()
            if entry.name.startswith(".lvw-v0-stage-")
        )

        # -- 包与 manifest 的可复算量 ------------------------------------ #
        package_sha = sha256_file(package)
        package_size = package.stat().st_size
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read("meta/manifest.json").decode("utf-8"))
            members = sorted(info.filename for info in archive.infolist())
        manifest_bytes = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8") + b"\n"
        fingerprint = hashlib.sha256()
        for item in sorted(manifest["items"], key=lambda entry: entry["install_path"]):
            fingerprint.update(
                f"{item['install_path']}:{item['sha256']}\n".encode("utf-8")
            )
        (self.evidence_dir / "package-manifest.json").write_bytes(manifest_bytes)

        # -- 清理测量 ------------------------------------------------------ #
        if self.owns_work_dir:
            shutil.rmtree(self.work_dir, ignore_errors=True)
            work_dir_removed = not self.work_dir.exists()
            work_dir_disposition = "removed_by_runner"
        else:
            work_dir_removed = not self.work_dir.exists()
            work_dir_disposition = "not_removed_by_runner"

        summary = {
            "kind": "S3_PREP_B_OFFLINE_PACKAGE_CHAIN_EVIDENCE",
            "scope": "offline preparation only; not product Gate0, not a Stage PASS",
            "candidate_commit": self.candidate,
            "candidate_commit_resolved": git(
                self.repo, "rev-parse", "--verify", f"{self.candidate}^{{commit}}"
            ).decode("utf-8").strip(),
            "tool_path_in_repo": tool_rel,
            "tool_sha256": tool_sha,
            "tool_matches_candidate_commit": tool_sha == tool_bound,
            "package": {
                "sha256": package_sha,
                "size_bytes": package_size,
                "member_count": len(members),
                "members": members,
            },
            "manifest_sha256": sha256_bytes(manifest_bytes),
            "payload_fingerprint_sha256": fingerprint.hexdigest(),
            "payload_item_count": manifest["payload_item_count"],
            "payload_expanded_bytes": manifest["payload_expanded_bytes"],
            "steps": [
                {
                    "index": step["index"],
                    "label": step["label"],
                    "command": step["command"],
                    "exit_code": step["exit_code"],
                    "raw": step["raw"],
                }
                for step in self.steps
            ],
            "sentinel": {
                "path": f"<work-dir>/{SANDBOX_DIR_NAME}/{TARGET_DIR_NAME}/{SENTINEL_NAME}",
                "sha256_before_install": sentinel_sha_before,
                "sha256_after_install": sentinel_sha_after_install,
                "sha256_after_rollback": sentinel_sha_after_rollback,
                "unchanged_by_install": sentinel_sha_before == sentinel_sha_after_install,
                "unchanged_by_rollback": sentinel_sha_before == sentinel_sha_after_rollback,
                "bytes_after_rollback_match": sentinel_bytes_after_rollback == SENTINEL_BYTES,
            },
            "installed_file_count": len(installed_files),
            "remaining_file_count_after_rollback": len(remaining_files),
            "remaining_files_after_rollback": remaining_files,
            "staging_leftovers": staging_leftovers,
            "work_dir_removed": work_dir_removed,
            "work_dir_disposition": work_dir_disposition,
            "product_runtime_calls": 0,
        }
        (self.raw_dir / "chain-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return summary

    def _tool_relative_path(self):
        prefix = "LVW_Prompt_Service_MasterPack_v2.0.0"
        for candidate in (f"{prefix}/{TOOL_RELATIVE_PATH}", TOOL_RELATIVE_PATH):
            code, stdout = git_probe(
                self.repo, "cat-file", "blob", f"{self.candidate}:{candidate}"
            )
            if code == 0 and stdout:
                return candidate
        raise SystemExit(
            f"{TOOL_RELATIVE_PATH} not found in candidate commit {self.candidate}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--work-dir")
    args = parser.parse_args(argv)
    runner = ChainRunner(
        repo=args.repo,
        candidate=args.candidate,
        evidence_dir=args.evidence_dir,
        work_dir=args.work_dir,
    )
    summary = runner.execute()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
