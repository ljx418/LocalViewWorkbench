#!/usr/bin/env python3
"""correction-01 真实离线包链路执行器。

从**修复工具候选 commit** 执行一次真实仓库 payload 的离线链路：
build → diagnose → 中文/空格隔离沙箱 install → rollback。

与 preparation-04/implementation/run_offline_chain.py 的差别（correction-01 要求）：

* ``try/finally`` + 自有临时根：任何失败路径都会清理本轮自建的临时根并实测清理
  结果；不再有「异常时跳过清理」的泄漏路径。
* 只清理本轮自己创建、且路径可证明的临时根；不扫删 /tmp 前缀或任何未知目录，
  也不触碰独审的历史失败证据。
* 额外记录本轮**本地所有权生命周期**：目标内所有权记录的落盘、install_hash、
  回滚后的安全移除，以及暂存目录终态。
* 预先固定哨兵 / 非 owned 内容 / 外部 victim 的哈希，回滚后逐一复核。

边界：纯离线。无媒体、无模型、无 GPU、无宿主配置、无服务、无网络、无下载。
包与临时副本不进入 Git；证据写入时对绝对路径脱敏。

用法：
    python3 run_offline_chain.py --repo <repo-root> --candidate <commit-sha> \
        --evidence-dir <dir>
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
OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"

#: 隔离沙箱与目标目录都带中文与空格，覆盖路径可执行性。
SANDBOX_DIR_NAME = "隔离 沙箱根"
TARGET_DIR_NAME = "隔离 目标 目录"
SENTINEL_NAME = "哨兵 文件.txt"
SENTINEL_BYTES = b"SENTINEL-ORIGINAL-BYTES\n"
NON_OWNED_NAME = "用户 原有 文件.txt"
NON_OWNED_BYTES = b"PRE-EXISTING-NON-OWNED-BYTES\n"
VICTIM_NAME = "外部 victim.txt"
VICTIM_BYTES = b"EXTERNAL-VICTIM-MUST-NEVER-BE-TOUCHED\n"

#: 本轮自有临时根前缀（只清理本轮自己创建的、路径可证明的那一个）。
WORK_DIR_PREFIX = "lvw-corr01-离线包链路 "


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc.stdout


class ChainRunner:
    """自有临时根 + try/finally 的链路执行器。"""

    def __init__(self, repo, candidate, evidence_dir):
        self.repo = Path(repo).resolve()
        self.candidate = candidate
        self.evidence_dir = Path(evidence_dir).resolve()
        self.raw_dir = self.evidence_dir / "raw"
        self.steps = []
        self.work_dir = Path(
            tempfile.mkdtemp(prefix=WORK_DIR_PREFIX, dir=os.environ.get("TMPDIR", "/tmp"))
        ).resolve()
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.tool_path = None
        self.repo_root = None

    # -- 执行器原语 ------------------------------------------------------- #

    def _redact(self, text):
        """把工作根与仓库根的绝对路径替换成占位符（证据必须脱敏）。"""
        value = str(text)
        for needle, token in (
            (str(self.work_dir), "<work-dir>"),
            (str(self.repo_root), "<repo-root>"),
        ):
            if needle:
                value = value.replace(needle, token)
        return value

    def run_step(self, index, label, args, redact_roots=()):
        command = [sys.executable, str(self.tool_path), *args]
        printable = self._redact("python3 " + " ".join(str(arg) for arg in command[1:]))
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.repo_root),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        stdout_text = self._redact(proc.stdout.decode("utf-8", "replace"))
        stderr_text = self._redact(proc.stderr.decode("utf-8", "replace"))
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

    # -- 主流程 ----------------------------------------------------------- #

    def execute(self):
        self.repo_root = Path(
            git(self.repo, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        ).resolve()
        tool_rel = self._tool_relative_path()
        self.tool_path = self.repo_root / tool_rel

        tool_bytes = Path(self.tool_path).read_bytes()
        committed_tool = git(self.repo, "cat-file", "blob", f"{self.candidate}:{tool_rel}")
        tool_sha = sha256_bytes(tool_bytes)
        tool_bound = sha256_bytes(committed_tool)
        if tool_sha != tool_bound:
            raise RuntimeError(
                "执行用的工具字节与候选 commit 中的工具字节不一致，拒绝继续"
            )

        candidate_resolved = (
            git(self.repo, "rev-parse", "--verify", f"{self.candidate}^{{commit}}")
            .decode("utf-8")
            .strip()
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
        non_owned = target / NON_OWNED_NAME
        non_owned.write_bytes(NON_OWNED_BYTES)
        # 外部 victim：在目标与沙箱之外，任何回滚都不得触碰它。
        victim = self.work_dir / VICTIM_NAME
        victim.write_bytes(VICTIM_BYTES)

        fixed_hashes = {
            "sentinel_sha256": sha256_file(sentinel),
            "non_owned_sha256": sha256_file(non_owned),
            "external_victim_sha256": sha256_file(victim),
        }

        package = self.work_dir / "LVW_V0 增量包.zip"
        redact = ["--redact-root", str(self.work_dir), "--redact-root", str(self.repo_root)]
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
                *redact,
            ],
        )
        if build["exit_code"] != 0:
            raise RuntimeError(f"build 失败，退出码 {build['exit_code']}")

        diagnose = self.run_step(
            2,
            "diagnose",
            [
                "diagnose",
                "--package", str(package),
                "--target", str(target),
                "--sandbox-parent", str(sandbox_parent),
                "--receipt-out", str(diagnose_receipt),
                *redact,
            ],
        )
        if diagnose["exit_code"] != 0:
            raise RuntimeError(f"diagnose 失败，退出码 {diagnose['exit_code']}")

        install = self.run_step(
            3,
            "install",
            [
                "install",
                "--package", str(package),
                "--sandbox-parent", str(sandbox_parent),
                "--target", str(target),
                "--receipt-out", str(install_receipt),
                *redact,
            ],
        )
        if install["exit_code"] != 0:
            raise RuntimeError(f"install 失败，退出码 {install['exit_code']}")

        # --- 本轮本地所有权生命周期：安装后 -------------------------------- #
        ownership_path = target / OWNERSHIP_FILE_NAME
        ownership_present = ownership_path.is_file()
        ownership_record = None
        if ownership_present:
            ownership_record = json.loads(ownership_path.read_text(encoding="utf-8"))
        installed_files = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        )
        staging_leftovers_after_install = sorted(
            entry.name
            for entry in sandbox_parent.iterdir()
            if entry.name.startswith(".lvw-v0-stage-")
        )

        rollback = self.run_step(
            4,
            "rollback",
            [
                "rollback",
                "--receipt", str(install_receipt),
                "--target", str(target),
                "--receipt-out", str(rollback_receipt),
                *redact,
            ],
        )
        if rollback["exit_code"] != 0:
            raise RuntimeError(f"rollback 失败，退出码 {rollback['exit_code']}")

        # --- 回滚后复核 ---------------------------------------------------- #
        remaining_files = sorted(
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        )
        staging_leftovers_after_rollback = sorted(
            entry.name
            for entry in sandbox_parent.iterdir()
            if entry.name.startswith(".lvw-v0-stage-")
        )
        ownership_present_after_rollback = (target / OWNERSHIP_FILE_NAME).exists()

        # --- 可复算量 -------------------------------------------------------- #
        package_sha = sha256_file(package)
        package_size = package.stat().st_size
        with zipfile.ZipFile(package) as archive:
            manifest = json.loads(archive.read("meta/manifest.json").decode("utf-8"))
            members = sorted(info.filename for info in archive.infolist())
            packaged_tool_sha = sha256_bytes(archive.read(f"meta/{TOOL_NAME}"))
        manifest_bytes = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8") + b"\n"
        fingerprint = hashlib.sha256()
        for item in sorted(manifest["items"], key=lambda entry: entry["install_path"]):
            fingerprint.update(
                f"{item['install_path']}:{item['sha256']}\n".encode("utf-8")
            )
        (self.evidence_dir / "package-manifest.json").write_bytes(manifest_bytes)

        summary = {
            "kind": "S3_PREP_B_CORRECTION_01_OFFLINE_PACKAGE_CHAIN_EVIDENCE",
            "scope": (
                "offline preparation only; not product Gate0, not a Stage PASS, "
                "not a real-host acceptance"
            ),
            "candidate_commit": self.candidate,
            "candidate_commit_resolved": candidate_resolved,
            "tool_path_in_repo": tool_rel,
            "tool_sha256": tool_sha,
            "tool_matches_candidate_commit": tool_sha == tool_bound,
            "packaged_tool_sha256": packaged_tool_sha,
            "packaged_tool_matches_candidate_commit": packaged_tool_sha == tool_bound,
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
            "manifest_source_commit": manifest["source_commit"],
            "receipt_schema_version": install["stdout_json"]["schema_version"],
            "ownership_schema_version": install["stdout_json"]["ownership_schema_version"],
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
            "fixed_hashes_before_chain": fixed_hashes,
            "fixed_hashes_after_chain": {
                "sentinel_sha256": sha256_file(sentinel),
                "non_owned_sha256": sha256_file(non_owned),
                "external_victim_sha256": sha256_file(victim),
            },
            "fixed_hashes_unchanged": (
                fixed_hashes["sentinel_sha256"] == sha256_file(sentinel)
                and fixed_hashes["non_owned_sha256"] == sha256_file(non_owned)
                and fixed_hashes["external_victim_sha256"] == sha256_file(victim)
            ),
            "ownership_lifecycle": {
                "record_file_name": OWNERSHIP_FILE_NAME,
                "present_after_install": ownership_present,
                "install_hash": (ownership_record or {}).get("install_hash"),
                "session_id": (ownership_record or {}).get("session_id"),
                "target_identity": "<work-dir>/"
                + SANDBOX_DIR_NAME
                + "/"
                + TARGET_DIR_NAME,
                "receipt_ownership_sha256": (
                    install["stdout_json"].get("ownership") or {}
                ).get("sha256"),
                "present_after_rollback": ownership_present_after_rollback,
                "rollback_report_removed": (
                    (rollback["stdout_json"].get("ownership_record") or {}).get("removed")
                ),
            },
            "sentinel": {
                "path": f"<work-dir>/{SANDBOX_DIR_NAME}/{TARGET_DIR_NAME}/{SENTINEL_NAME}",
                "sha256_before_install": fixed_hashes["sentinel_sha256"],
                "sha256_after_install": sha256_file(sentinel),
                "sha256_after_rollback": sha256_file(sentinel),
                "bytes_after_rollback_match": sentinel.read_bytes() == SENTINEL_BYTES,
            },
            "installed_file_count": len(installed_files),
            "remaining_file_count_after_rollback": len(remaining_files),
            "remaining_files_after_rollback": remaining_files,
            "staging_leftovers_after_install": staging_leftovers_after_install,
            "staging_leftovers_after_rollback": staging_leftovers_after_rollback,
            "product_runtime_calls": 0,
            "note": (
                "本轮 runner 用 try/finally 覆盖所有失败路径；只清理本轮自建的临时根。"
            ),
        }
        return summary

    def _tool_relative_path(self):
        prefix = "LVW_Prompt_Service_MasterPack_v2.0.0"
        for candidate in (f"{prefix}/{TOOL_RELATIVE_PATH}", TOOL_RELATIVE_PATH):
            try:
                blob = git(self.repo, "cat-file", "blob", f"{self.candidate}:{candidate}")
            except RuntimeError:
                continue
            if blob:
                return candidate
        raise RuntimeError(
            f"{TOOL_RELATIVE_PATH} not found in candidate commit {self.candidate}"
        )

    def cleanup(self):
        """只删除本轮自建的临时根；不存在或已被删除都如实记录。"""
        existed = self.work_dir.exists()
        removed = False
        reason = ""
        if existed:
            try:
                shutil.rmtree(self.work_dir)
                removed = not self.work_dir.exists()
            except OSError as exc:
                reason = str(exc)
        else:
            reason = "already_absent"
        return {
            "work_dir_prefix": WORK_DIR_PREFIX,
            "existed_before_cleanup": existed,
            "removed": removed,
            "reason": reason,
            "exists_after_cleanup": self.work_dir.exists(),
            "cleanup_scope": (
                "only the single temporary root created by this runner; no /tmp prefix "
                "sweep and no unknown directory is touched"
            ),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args(argv)

    runner = ChainRunner(
        repo=args.repo,
        candidate=args.candidate,
        evidence_dir=args.evidence_dir,
    )
    summary = None
    failure = None
    try:
        summary = runner.execute()
    except Exception as exc:  # noqa: BLE001
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup = runner.cleanup()
        summary = summary or {}
        summary["temp_root_cleanup"] = cleanup
        summary["failure"] = failure
        (runner.evidence_dir / "chain-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
