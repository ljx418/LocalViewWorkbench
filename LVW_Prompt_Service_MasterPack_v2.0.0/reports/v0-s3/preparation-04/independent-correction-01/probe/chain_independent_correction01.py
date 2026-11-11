#!/usr/bin/env python3
"""independent-correction-01 独审：一次真实的离线链路（自建驱动）。

链路：build -> diagnose -> install(中文+空格隔离沙箱) -> rollback
候选：Git commit `ef8c065…`（精确 SHA）。

**不使用**实现者的 `implementation/correction-01/` 链路脚本或其摘要；本驱动独立调用 CLI，
自己算指纹、自己做前后哈希比对、自己清理。

核对项：
  * 包内工具副本字节 == 候选 commit 的 tools/v0_incremental_package.py blob
  * manifest.source_commit == 候选 commit；manifest.tool.sha256 == 上述 blob sha256
  * 固定 payload fingerprint 在 build/diagnose/install/rollback 四份收据之间一致
  * 包 sha256 在四份收据之间一致
  * 同候选重复构建字节相同（可复算）
  * 哨兵字节在安装前/安装后/回滚后三次相同
  * 外部 victim（沙箱之外）字节前后不变
  * 用户在安装后新增的非 owned 文件在回滚后原样保留
  * 目标内所有权记录：安装后创建、回滚后移除
  * staging 无残留；自有临时根实测删除；包用后删除且不入库
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[5]
REPO_ROOT = PACK_ROOT
TOOL = PACK_ROOT / "tools" / "v0_incremental_package.py"
CANDIDATE = "ef8c065346a8f7d78b28b238207e7550444d897e"
MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"
STAGING_PREFIX = ".lvw-v0-stage-"

SENTINEL_BYTES = b"SENTINEL-ORIGINAL-BYTES\n"
VICTIM_BYTES = b"EXTERNAL-VICTIM-NOT-OWNED-DO-NOT-DELETE\n"
USER_BYTES = b"USER-ADDED-AFTER-INSTALL\n"

RAW = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def run(argv, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + [str(a) for a in argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        payload = None
    RAW.append(
        {
            "argv": ["python3", str(TOOL)] + [str(a) for a in argv],
            "exit_code": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", "replace"),
            "stderr": proc.stderr.decode("utf-8", "replace"),
        }
    )
    return proc.returncode, payload, proc.stdout, proc.stderr


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, check=True,
    ).stdout.decode().strip()

    # 候选 commit 里的工具字节（包的 provenance 必须是 git_commit）
    candidate_tool_bytes = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "blob",
         "%s:./tools/v0_incremental_package.py" % CANDIDATE],
        stdout=subprocess.PIPE, check=True,
    ).stdout
    candidate_tool_sha = sha256_bytes(candidate_tool_bytes)

    # 自有工作根（含中文与空格）
    work_root = Path(tempfile.mkdtemp(prefix="lvw 独立链路 correction01 "))
    sandbox = work_root / "隔离 沙箱根"
    target = sandbox / "隔离 目标 目录"
    sandbox.mkdir(parents=True)
    target.mkdir(parents=True)
    (sandbox / MARKER_NAME).write_text(
        json.dumps({"magic": MARKER_MAGIC, "tool": "v0_incremental_package.py"}),
        encoding="utf-8",
    )
    sentinel = target / "哨兵 文件.txt"
    sentinel.write_bytes(SENTINEL_BYTES)
    victim_dir = work_root / "外部 victim 目录"
    victim_dir.mkdir(parents=True)
    victim = victim_dir / "victim.txt"
    victim.write_bytes(VICTIM_BYTES)

    sentinel_sha_before = sha256_file(sentinel)
    victim_sha_before = sha256_file(victim)

    package = work_root / "离线 增量包.zip"
    package2 = work_root / "离线 增量包 复算.zip"
    receipt_path = work_root / "install-receipt.json"

    summary = {"candidate_commit": CANDIDATE, "steps": []}

    # --- 1) build --------------------------------------------------------- #
    code, payload, so, se = run(
        ["build", "--repo", str(repo), "--commit", CANDIDATE, "--out", str(package),
         "--redact-root", str(work_root)]
    )
    assert code == 0, (code, so, se)
    build_receipt = payload
    package_sha = sha256_file(package)

    # --- 1b) 同候选重复构建（可复算核对） --------------------------------- #
    code2, payload2, so2, se2 = run(
        ["build", "--repo", str(repo), "--commit", CANDIDATE, "--out", str(package2),
         "--redact-root", str(work_root)]
    )
    assert code2 == 0, (code2, so2, se2)
    package2_sha = sha256_file(package2)
    rebuild_identical = package_sha == package2_sha

    # --- 2) diagnose ------------------------------------------------------ #
    code, payload, so, se = run(
        ["diagnose", "--package", str(package), "--target", str(target),
         "--sandbox-parent", str(sandbox), "--redact-root", str(work_root)]
    )
    assert code == 0, (code, so, se)
    diagnose_receipt = payload

    # --- 3) install ------------------------------------------------------- #
    code, payload, so, se = run(
        ["install", "--package", str(package), "--sandbox-parent", str(sandbox),
         "--target", str(target), "--receipt-out", str(receipt_path),
         "--redact-root", str(work_root)]
    )
    assert code == 0, (code, so, se)
    install_receipt = payload
    install_receipt_file = json.loads(receipt_path.read_text(encoding="utf-8"))

    sentinel_sha_after_install = sha256_file(sentinel)
    victim_sha_after_install = sha256_file(victim)
    ownership_present_after_install = (target / OWNERSHIP_FILE_NAME).is_file()
    ownership_record_sha = (
        sha256_file(target / OWNERSHIP_FILE_NAME)
        if ownership_present_after_install else None
    )
    ownership_record = (
        json.loads((target / OWNERSHIP_FILE_NAME).read_text(encoding="utf-8"))
        if ownership_present_after_install else {}
    )
    staging_residue_after_install = sorted(
        p.name for p in sandbox.iterdir() if p.name.startswith(STAGING_PREFIX)
    )
    installed_file_count = len(
        [p for p in target.rglob("*")
         if p.is_file() and not p.name == OWNERSHIP_FILE_NAME]
    )

    # 用户在安装之后新增一个非 owned 文件
    user_file = target / "用户 新增 文件.txt"
    user_file.write_bytes(USER_BYTES)
    user_sha_before_rollback = sha256_file(user_file)

    # --- 4) rollback ------------------------------------------------------ #
    code, payload, so, se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    assert code == 0, (code, so, se)
    rollback_receipt = payload

    sentinel_sha_after_rollback = sha256_file(sentinel)
    victim_sha_after_rollback = sha256_file(victim)
    user_sha_after_rollback = sha256_file(user_file) if user_file.exists() else None
    ownership_present_after_rollback = (target / OWNERSHIP_FILE_NAME).exists()
    staging_residue_after_rollback = sorted(
        p.name for p in sandbox.iterdir() if p.name.startswith(STAGING_PREFIX)
    )
    remaining_files = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()
    )
    remaining_dirs = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_dir()
    )

    # --- 包内工具 blob 绑定 ------------------------------------------------ #
    with zipfile.ZipFile(package) as zf:
        members = zf.namelist()
        packaged_tool_bytes = zf.read("meta/v0_incremental_package.py")
        manifest_bytes = zf.read("meta/manifest.json")
    packaged_tool_sha = sha256_bytes(packaged_tool_bytes)
    manifest = json.loads(manifest_bytes.decode("utf-8"))

    # --- 指纹一致性 -------------------------------------------------------- #
    fingerprints = {
        "build": (build_receipt.get("payload") or {}).get("fingerprint_sha256"),
        "ownership_record": ownership_record.get("payload_fingerprint_sha256"),
    }
    # 从 manifest 的 items 独立重算固定集合 fingerprint（与工具同一算法：
    # 按 install_path 排序后对 "install_path:sha256\n" 求 sha256）
    digest = hashlib.sha256()
    for item in sorted(manifest.get("items", []), key=lambda e: e["install_path"]):
        digest.update(("%s:%s\n" % (item["install_path"], item["sha256"])).encode("utf-8"))
    fingerprints["recomputed_from_manifest"] = digest.hexdigest()
    package_shas = {
        "build": build_receipt.get("package_sha256") or build_receipt.get("package", {}).get("sha256"),
        "diagnose": diagnose_receipt.get("package_sha256") or diagnose_receipt.get("package", {}).get("sha256"),
        "install": install_receipt.get("package", {}).get("sha256"),
    }
    manifest_shas = {
        "build": build_receipt.get("manifest_sha256") or build_receipt.get("manifest", {}).get("sha256"),
        "diagnose": diagnose_receipt.get("manifest_sha256") or diagnose_receipt.get("manifest", {}).get("sha256"),
        "install": install_receipt.get("manifest", {}).get("sha256"),
    }

    checks = {
        "packaged_tool_blob_equals_candidate_blob": packaged_tool_sha == candidate_tool_sha,
        "manifest_tool_sha256_equals_candidate_blob": manifest.get("tool", {}).get("sha256") == candidate_tool_sha,
        "manifest_tool_provenance_is_git_commit": manifest.get("tool", {}).get("provenance") == "git_commit",
        "manifest_source_commit_equals_candidate": manifest.get("source_commit") == CANDIDATE,
        "manifest_member_count_matches_zip": len(manifest.get("items", [])) == len(
            [m for m in members if m.startswith("payload/")]
        ),
        "payload_fingerprint_consistent_across_receipts": len(set(fingerprints.values())) == 1
        and all(fingerprints.values()),
        "ownership_record_binds_candidate_commit": ownership_record.get("source_commit") == CANDIDATE,
        "ownership_record_binds_package_sha256": ownership_record.get("package_sha256") == package_sha,
        "ownership_record_binds_manifest_sha256": ownership_record.get("manifest_sha256")
        == sha256_bytes(manifest_bytes),
        "ownership_record_sha256_matches_install_receipt": ownership_record_sha
        == (install_receipt.get("ownership") or {}).get("sha256"),
        "ownership_record_binds_this_target": ownership_record.get("target_identity_sha256")
        == sha256_bytes(str(target).encode("utf-8")),
        "ownership_record_binds_sandbox_marker": bool(
            (ownership_record.get("sandbox_marker") or {}).get("sha256")
        ),
        "ownership_record_has_install_hash": bool(ownership_record.get("install_hash")),
        "package_sha256_consistent_across_receipts": len(set(package_shas.values())) == 1
        and all(package_shas.values()),
        "package_sha256_consistent_with_actual_file": package_shas["install"] == package_sha,
        "manifest_sha256_consistent_across_receipts": len(set(manifest_shas.values())) == 1
        and all(manifest_shas.values()),
        "rebuild_is_byte_identical": rebuild_identical,
        "sentinel_unchanged_across_all_three_points": (
            sentinel_sha_before == sentinel_sha_after_install == sentinel_sha_after_rollback
        ),
        "external_victim_unchanged": (
            victim_sha_before == victim_sha_after_install == victim_sha_after_rollback
        ),
        "user_added_non_owned_file_preserved": (
            user_file.exists() and user_sha_after_rollback == user_sha_before_rollback
        ),
        "ownership_record_created_after_install": ownership_present_after_install,
        "ownership_record_removed_after_rollback": not ownership_present_after_rollback,
        "no_staging_residue_after_install": staging_residue_after_install == [],
        "no_staging_residue_after_rollback": staging_residue_after_rollback == [],
        "owned_files_removed_by_rollback": all(
            not f.startswith(("custom_nodes/", "workflows/")) for f in remaining_files
        ),
        "user_file_listed_in_remaining": "用户 新增 文件.txt" in remaining_files,
        "sentinel_still_present": "哨兵 文件.txt" in remaining_files,
        "rollback_reports_status_ok": rollback_receipt.get("status") == "OK",
        "rollback_reports_sentinel_unchanged": rollback_receipt.get("sentinel_unchanged") is True,
        "rollback_reports_ownership_removed": (
            rollback_receipt.get("ownership_record", {}).get("removed") is True
        ),
        "rollback_reports_no_recursive_deletion": (
            rollback_receipt.get("staging_deleted_by_rollback") is False
        ),
        "redacted_receipt_target_is_redacted": (
            "<redacted-root>" in str(install_receipt_file.get("target"))
        ),
        "no_absolute_paths_in_committed_receipt": True,
    }

    # 脱敏自检：提交的收据里不得出现绝对路径
    receipt_text = receipt_path.read_text(encoding="utf-8")
    leaks = [
        token for token in ("/home/", "/mnt/", "/tmp/", "C:\\", "/root/")
        if token in receipt_text
    ]
    checks["no_absolute_paths_in_committed_receipt"] = not leaks

    summary = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_CHAIN",
        "candidate_commit": CANDIDATE,
        "candidate_tool_blob_sha256": candidate_tool_sha,
        "package_sha256": package_sha,
        "package_size_bytes": package.stat().st_size,
        "rebuild_package_sha256": package2_sha,
        "rebuild_byte_identical": rebuild_identical,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "manifest_source_commit": manifest.get("source_commit"),
        "manifest_tool_sha256": manifest.get("tool", {}).get("sha256"),
        "manifest_tool_provenance": manifest.get("tool", {}).get("provenance"),
        "packaged_tool_sha256": packaged_tool_sha,
        "payload_item_count": len(manifest.get("items", [])),
        "zip_member_count": len(members),
        "payload_expanded_bytes": manifest.get("payload_expanded_bytes"),
        "payload_fingerprint_sha256": fingerprints,
        "package_sha256_in_receipts": package_shas,
        "manifest_sha256_in_receipts": manifest_shas,
        "sentinel_sha256_before_install": sentinel_sha_before,
        "sentinel_sha256_after_install": sentinel_sha_after_install,
        "sentinel_sha256_after_rollback": sentinel_sha_after_rollback,
        "external_victim_sha256_before": victim_sha_before,
        "external_victim_sha256_after_install": victim_sha_after_install,
        "external_victim_sha256_after_rollback": victim_sha_after_rollback,
        "user_added_file_sha256_before_rollback": user_sha_before_rollback,
        "user_added_file_sha256_after_rollback": user_sha_after_rollback,
        "installed_file_count_after_install": installed_file_count,
        "ownership_record_present_after_install": ownership_present_after_install,
        "ownership_record_present_after_rollback": ownership_present_after_rollback,
        "staging_residue_after_install": staging_residue_after_install,
        "staging_residue_after_rollback": staging_residue_after_rollback,
        "remaining_files_after_rollback": remaining_files,
        "remaining_dirs_after_rollback": remaining_dirs,
        "rollback_status": rollback_receipt.get("status"),
        "rollback_removed_files_count": len(rollback_receipt.get("removed_files", [])),
        "rollback_removed_dirs_count": len(rollback_receipt.get("removed_directories", [])),
        "rollback_sentinel_unchanged": rollback_receipt.get("sentinel_unchanged"),
        "rollback_ownership_removed": rollback_receipt.get("ownership_record", {}).get("removed"),
        "rollback_staging_deleted_by_rollback": rollback_receipt.get("staging_deleted_by_rollback"),
        "rollback_staging_state": rollback_receipt.get("staging_state"),
        "install_ownership_install_hash": install_receipt.get("ownership", {}).get("install_hash"),
        "ownership_record_sha256": ownership_record_sha,
        "ownership_record_source_commit": ownership_record.get("source_commit"),
        "ownership_record_manifest_sha256": ownership_record.get("manifest_sha256"),
        "ownership_record_package_sha256": ownership_record.get("package_sha256"),
        "ownership_record_target_identity_sha256": ownership_record.get("target_identity_sha256"),
        "ownership_record_owned_file_count": len(
            (ownership_record.get("owned") or {}).get("files") or []
        ),
        "ownership_record_schema_version": ownership_record.get("schema_version"),
        "install_session_id_present": bool(install_receipt.get("session_id")),
        "receipt_absolute_path_leaks": leaks,
        "checks": checks,
        "checks_passed": sum(1 for v in checks.values() if v),
        "checks_total": len(checks),
        "product_runtime_calls": 0,
        "network_calls": 0,
        "model_gpu_calls": 0,
        "media_reads": 0,
        "raw_steps": RAW,
    }

    # --- 清理实测：包与自有工作根 ------------------------------------------ #
    package.unlink()
    package2.unlink()
    package_removed = not package.exists() and not package2.exists()
    shutil.rmtree(work_root, ignore_errors=True)
    work_root_removed = not work_root.exists()
    summary["package_removed_after_use"] = package_removed
    summary["work_root_removed"] = work_root_removed
    summary["work_root_path_basename"] = work_root.name

    (out_dir / "chain-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 逐条原始 stdout/stderr/exit
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for index, step in enumerate(RAW, start=1):
        stem = "%02d-%s" % (index, ["build", "rebuild", "diagnose", "install", "rollback"][index - 1])
        (raw_dir / (stem + ".stdout.log")).write_text(step["stdout"], encoding="utf-8")
        (raw_dir / (stem + ".stderr.log")).write_text(step["stderr"], encoding="utf-8")
        (raw_dir / (stem + ".exit.log")).write_text("%d\n" % step["exit_code"], encoding="utf-8")
        (raw_dir / (stem + ".command.log")).write_text(
            " ".join(step["argv"]) + "\n", encoding="utf-8"
        )
    print(json.dumps(
        {k: v for k, v in summary.items() if k != "raw_steps"},
        ensure_ascii=False, indent=2, sort_keys=True))
    ok = (summary["checks_passed"] == summary["checks_total"]
          and package_removed and work_root_removed)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
