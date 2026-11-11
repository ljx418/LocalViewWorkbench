#!/usr/bin/env python3
"""correction-01：沿用 independent-01 独审负例的适配副本（不改历史证据），
并补齐本轮所有权记录相关的负例。

覆盖：
  N1 篡改 install receipt 的 owned.files[].install_path -> rollback 路径穿越删除非 owned 文件
  N2 篡改 install receipt 的 staging.path            -> rollback 递归删除任意目录
  N3 跨目标回滚（同名不同目录）                        -> rollback 是否只按 basename 绑定
  N4 zip bomb（谎报 zip 头部 file_size）               -> diagnose/install 的上限与炸弹判定
  N5 已有非 owned 冲突                                  -> install 必须 0 写入
  N6 诊断失败                                          -> target 零写入（不留空目录）
  N7 脏工作树                                          -> build 仍从 commit 读字节

全部写入都在自有 TemporaryDirectory 内合成，不触碰真实宿主或用户路径。

correction-01 追加：
  N12 目标内所有权记录缺失          -> 拒绝，owned 文件零删除
  N13 目标内所有权记录被改写        -> 拒绝，owned 文件零删除
  N14 收据 session 与记录不符       -> 拒绝，owned 文件零删除
  N15 收据全部路径字段被篡改        -> 逐项非零拒绝，目标整树不变
  N16 预检失败时整树零写入零删除    -> 外部 victim 与哨兵字节不变
  N17 脱敏收据 + 显式 --target      -> 仍可正常回滚
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[6]
REPO_ROOT = PACK_ROOT
TOOL_REL = "tools/v0_incremental_package.py"
TOOL = PACK_ROOT / TOOL_REL
CANDIDATE = "ef8c065346a8f7d78b28b238207e7550444d897e"
MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
TOOL_NAME = "v0_incremental_package.py"

RESULTS = []


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


RAW_DIR = None
_RAW_SEQ = [0]


#: 证据脱敏根（临时根、仓库根与工具路径）；写入磁盘的原文一律先脱敏。
REDACT_ROOTS = []


def _redact_text(text):
    value = str(text)
    for root in REDACT_ROOTS:
        if root:
            value = value.replace(str(root), "<redacted-root>")
    return value


def run(argv, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + argv,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    stdout_text = _redact_text(proc.stdout.decode("utf-8", "replace"))
    stderr_text = _redact_text(proc.stderr.decode("utf-8", "replace"))
    try:
        payload = json.loads(stdout_text)
    except ValueError:
        payload = None
    if RAW_DIR is not None:
        _RAW_SEQ[0] += 1
        stem = "probe-%02d" % _RAW_SEQ[0]
        (RAW_DIR / (stem + ".command.log")).write_text(
            _redact_text("python3 " + " ".join(str(a) for a in argv)) + "\n",
            encoding="utf-8")
        (RAW_DIR / (stem + ".stdout.log")).write_text(stdout_text, encoding="utf-8")
        (RAW_DIR / (stem + ".stderr.log")).write_text(stderr_text, encoding="utf-8")
        (RAW_DIR / (stem + ".exit.log")).write_text(
            "%d\n" % proc.returncode, encoding="utf-8")
    return proc.returncode, payload, stdout_text, stderr_text


def record(probe, expectation, observed, ok, detail=None):
    RESULTS.append({
        "probe": probe,
        "expectation": expectation,
        "observed": observed,
        "matches_expectation": ok,
        "detail": detail or {},
    })
    print("[%s] expect=%s observed=%s" % (probe, expectation, observed))


OWNED_PREFIXES = ("custom_nodes/lvw_v0_bridge/", "workflows/lvw/")


def _installed_owned_files(target):
    """目标内由本工具安装出来的 owned 文件（不含所有权记录与用户文件）。"""
    target = Path(target)
    return sorted(
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
        and path.relative_to(target).as_posix().startswith(OWNED_PREFIXES)
    )


def make_sandbox(root, name="隔离 沙箱根", target_name="隔离 目标 目录"):
    sandbox = root / name
    target = sandbox / target_name
    sandbox.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    (sandbox / MARKER_NAME).write_text(
        json.dumps({"magic": MARKER_MAGIC, "tool": TOOL_NAME}), encoding="utf-8")
    return sandbox, target


def build_package(root, repo, commit, name="pkg.zip"):
    out = root / name
    code, payload, so, se = run([
        "build", "--repo", str(repo), "--commit", commit, "--out", str(out)])
    assert code == 0, (code, so, se)
    return out


# --------------------------------------------------------------------------- #
def n1_path_traversal_in_receipt(tmp, repo, package):
    """篡改 install receipt 的 install_path 指向 target 之外。"""
    sandbox, target = make_sandbox(tmp)
    victim = tmp / "victim.txt"
    victim_bytes = b"VICTIM-NOT-OWNED-DO-NOT-DELETE\n"
    victim.write_bytes(victim_bytes)
    receipt_path = tmp / "install-receipt.json"
    code, _, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target), "--receipt-out", str(receipt_path)])
    assert code == 0, (code, so, se)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    owned = receipt["owned"]["files"]
    owned[0] = {
        "install_path": "../../victim.txt",
        "sha256": sha256_bytes(victim_bytes),
        "length": len(victim_bytes),
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    observed = {
        "exit_code": code,
        "victim_still_exists": victim.exists(),
        "error_code": (payload or {}).get("error_code"),
        "removed_files": ((payload or {}).get("detail") or {}).get("removed_files"),
    }
    record("N1-rollback-receipt-path-traversal",
           "victim_still_exists=True (越界文件不得被删除)",
           "victim_still_exists=%s" % observed["victim_still_exists"],
           observed["victim_still_exists"] is True,
           observed)
    return observed


def n2_staging_path_rmtree(tmp, repo, package):
    """篡改 install receipt 的 staging.path -> rollback 递归删除任意目录。"""
    sandbox, target = make_sandbox(tmp)
    victim_dir = tmp / "victim_dir"
    (victim_dir / "sub").mkdir(parents=True)
    (victim_dir / "sub" / "keep.txt").write_bytes(b"KEEP\n")
    receipt_path = tmp / "install-receipt.json"
    code, _, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target), "--receipt-out", str(receipt_path)])
    assert code == 0, (code, so, se)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["staging"] = {"path": str(victim_dir), "removed": False}
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    observed = {
        "exit_code": code,
        "victim_dir_still_exists": victim_dir.exists(),
        "error_code": (payload or {}).get("error_code"),
    }
    record("N2-rollback-staging-path-arbitrary-rmtree",
           "victim_dir_still_exists=True (收据字段不得驱动任意 rmtree)",
           "victim_dir_still_exists=%s" % observed["victim_dir_still_exists"],
           observed["victim_dir_still_exists"] is True,
           observed)
    return observed


def n3_cross_target_rollback(tmp, repo, package):
    """同名不同目录的跨目标回滚。"""
    sandbox_a, target_a = make_sandbox(tmp, "沙箱 A", "同一 目标")
    sandbox_b, target_b = make_sandbox(tmp, "沙箱 B", "同一 目标")
    receipt_path = tmp / "install-receipt.json"
    code, _, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox_a),
        "--target", str(target_a), "--receipt-out", str(receipt_path)])
    assert code == 0, (code, so, se)

    # 在 B 目标里放同名同内容（模拟另一份安装）
    code, _, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox_b),
        "--target", str(target_b)])
    assert code == 0, (code, so, se)
    b_files_before = _installed_owned_files(target_b)
    marker = target_b / "非 owned 标记.txt"
    marker.write_bytes(b"USER\n")

    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target_b)])
    b_files_after = _installed_owned_files(target_b)
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "b_files_before": len(b_files_before),
        "b_files_after": len(b_files_after),
        "b_installed_files_removed": len(b_files_before) - len(b_files_after),
        "non_owned_marker_still_exists": marker.exists(),
    }
    record("N3-rollback-cross-target-same-basename",
           "b_installed_files_removed=0 且不得删除另一沙箱的 owned 文件",
           "b_installed_files_removed=%d" % observed["b_installed_files_removed"],
           observed["b_installed_files_removed"] == 0,
           observed)
    return observed


def n4_zip_bomb_lying_header(tmp, repo, package):
    """谎报 zip 头 file_size 的炸弹：真实展开远大于声明。"""
    bomb = tmp / "bomb.zip"
    # 50 MiB 全零：真实展开 50 MiB，但我们在中央目录里谎报 file_size
    raw = b"\x00" * (50 * 1024 * 1024)
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("payload/x.bin", raw)
    data = bytearray(bomb.read_bytes())
    # 找到中央目录里该成员的 file_size 字段并改成 100
    idx = data.find(b"payload/x.bin")
    # 中央目录头：偏移 42 之后是 crc(4) csize(4) usize(4)
    cd = data.rfind(b"PK\x01\x02")
    assert cd > 0
    usize_off = cd + 24
    struct.pack_into("<I", data, usize_off, 100)
    bomb.write_bytes(bytes(data))

    with zipfile.ZipFile(bomb) as zf:
        info = zf.getinfo("payload/x.bin")
        declared = info.file_size
        compressed = info.compress_size

    code, payload, so, se = run(["diagnose", "--package", str(bomb)])
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "declared_file_size": declared,
        "actual_compress_size": compressed,
        "real_expanded_bytes": len(raw),
        "package_size_bytes": bomb.stat().st_size,
    }
    record("N4-zip-bomb-lying-header",
           "必须以非零退出码拒绝 (INTEGRITY_MISMATCH 或 SIZE_LIMIT)",
           "exit=%s error_code=%s" % (code, observed["error_code"]),
           code != 0, observed)
    return observed


def n5_existing_unowned_conflict(tmp, repo, package):
    """已有非 owned 冲突 -> install 必须 0 写入。"""
    sandbox, target = make_sandbox(tmp)
    conflict = target / "custom_nodes" / "lvw_v0_bridge"
    conflict.mkdir(parents=True)
    (conflict / "既有 用户 文件.txt").write_bytes(b"USER\n")
    before = sorted(str(p.relative_to(target)) for p in target.rglob("*"))
    code, payload, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target)])
    after = sorted(str(p.relative_to(target)) for p in target.rglob("*"))
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_unchanged": before == after,
        "files_after": after,
    }
    record("N5-existing-unowned-conflict-zero-write",
           "exit!=0 且 tree_unchanged=True",
           "exit=%s tree_unchanged=%s" % (code, observed["tree_unchanged"]),
           code != 0 and observed["tree_unchanged"], observed)
    return observed


def n6_diagnose_failure_zero_write(tmp, repo, package):
    """诊断失败 -> target 零写入（不得留下空安装目录）。"""
    sandbox, target = make_sandbox(tmp)
    bad = tmp / "bad.zip"
    shutil.copyfile(package, bad)
    # 破坏一个 payload 成员
    with zipfile.ZipFile(bad, "a") as zf:
        zf.writestr("payload/evil.py", b"x")
    code, payload, so, se = run([
        "diagnose", "--package", str(bad), "--target", str(target),
        "--sandbox-parent", str(sandbox)])
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "target_entries": sorted(p.name for p in target.iterdir()),
        "target_empty": not any(target.iterdir()),
    }
    record("N6-diagnose-failure-zero-write",
           "exit!=0 且 target_empty=True",
           "exit=%s target_empty=%s" % (code, observed["target_empty"]),
           code != 0 and observed["target_empty"], observed)
    return observed


def n7_build_reads_git_objects(tmp, repo):
    """脏工作树：build 仍必须从 commit 读字节。"""
    clone = tmp / "clone"
    subprocess.run(["git", "clone", "--local", "--no-hardlinks", str(repo), str(clone)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    subprocess.run(["git", "-C", str(clone), "checkout", CANDIDATE],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    victim = (clone / "LVW_Prompt_Service_MasterPack_v2.0.0/LVW_V0_RuntimePatch"
              / "custom_nodes/lvw_v0_bridge/core.py")
    victim.write_text("# DIRTY WORKTREE MARKER\nprint('dirty')\n", encoding="utf-8")
    dirty_sha = sha256_bytes(victim.read_bytes())
    out = tmp / "dirty-pkg.zip"
    clone_tool = (clone / "LVW_Prompt_Service_MasterPack_v2.0.0" / "tools"
                  / "v0_incremental_package.py")
    proc = subprocess.run(
        [sys.executable, str(clone_tool), "build", "--repo", str(clone),
         "--commit", CANDIDATE, "--out", str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(clone))
    code = proc.returncode
    so, se = proc.stdout, proc.stderr
    payload = None
    try:
        payload = json.loads(so.decode("utf-8"))
    except ValueError:
        payload = None
    assert code == 0, (code, so, se)
    with zipfile.ZipFile(out) as zf:
        member = zf.read("payload/custom_nodes/lvw_v0_bridge/core.py")
    built_sha = sha256_bytes(member)
    # commit 中的原始字节
    blob = subprocess.run(
        ["git", "-C", str(clone), "cat-file", "blob",
         "%s:LVW_Prompt_Service_MasterPack_v2.0.0/LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py"
         % CANDIDATE], stdout=subprocess.PIPE, check=True).stdout
    observed = {
        "exit_code": code,
        "dirty_worktree_sha256": dirty_sha,
        "built_payload_sha256": built_sha,
        "commit_blob_sha256": sha256_bytes(blob),
        "built_matches_commit_blob": built_sha == sha256_bytes(blob),
        "built_matches_dirty_worktree": built_sha == dirty_sha,
        "worktree_dirty_path_count": payload.get("worktree_dirty_path_count"),
    }
    record("N7-build-reads-git-objects-not-dirty-worktree",
           "built_matches_commit_blob=True 且 built_matches_dirty_worktree=False",
           "built_matches_commit_blob=%s built_matches_dirty_worktree=%s"
           % (observed["built_matches_commit_blob"], observed["built_matches_dirty_worktree"]),
           observed["built_matches_commit_blob"] and not observed["built_matches_dirty_worktree"],
           observed)
    return observed


def n8_windows_name_semantics(tmp, repo, package):
    """Windows 语义：尾随点/尾随空格在 Windows 上归一化为同一文件名，工具是否拒绝。"""
    sandbox, target = make_sandbox(tmp)
    # 以真实包为底，加入 "zz.py" 与 "zz.py." 两个成员，并在 manifest 中如实登记两者。
    with zipfile.ZipFile(package) as zf:
        members = [(i.filename, zf.read(i.filename)) for i in zf.infolist()]
    manifest = json.loads(dict(members)["meta/manifest.json"].decode("utf-8"))
    content = b"print('x')\n"
    base = "payload/custom_nodes/lvw_v0_bridge/zz.py"
    dotted = "payload/custom_nodes/lvw_v0_bridge/zz.py."
    for name in (base, dotted):
        members.append((name, content))
        rel = name[len("payload/"):]
        manifest["items"].append({
            "install_path": rel,
            "package_path": name,
            "source_path": rel,
            "source_blob_id": "0" * 40,
            "source_mode": "100644",
            "length": len(content),
            "sha256": sha256_bytes(content),
        })
    manifest["payload_item_count"] = len(manifest["items"])
    manifest["payload_expanded_bytes"] = sum(
        i["length"] for i in manifest["items"])
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n").encode("utf-8")
    members = [(n, manifest_bytes if n == "meta/manifest.json" else d)
               for n, d in members]
    crafted = tmp / "windows-norm.zip"
    with zipfile.ZipFile(crafted, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100644) << 16
            info.create_system = 3
            zf.writestr(info, data)
    code, payload, so, se = run(["diagnose", "--package", str(crafted)])
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "rejected": code != 0,
        "message": (payload or {}).get("message"),
    }
    record("N8-windows-trailing-dot-space-normalization",
           "必须被拒绝 (Windows 上 'zz.py' 与 'zz.py.' 是同一文件名)",
           "exit=%s error_code=%s" % (code, observed["error_code"]),
           code != 0, observed)
    return observed


def n10_user_modified_owned_file_blocks_rollback(tmp, repo, package):
    """用户改写 owned 文件后回滚必须拒绝且字节不变。"""
    sandbox, target = make_sandbox(tmp)
    receipt_path = tmp / "install-receipt.json"
    code, _, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target), "--receipt-out", str(receipt_path)])
    assert code == 0, (code, so, se)
    edited = target / "custom_nodes/lvw_v0_bridge/core.py"
    edited.write_bytes(b"# USER EDITED\n")
    edited_sha = sha256_bytes(edited.read_bytes())
    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "bytes_unchanged": edited.exists()
        and sha256_bytes(edited.read_bytes()) == edited_sha,
        "file_still_present": edited.exists(),
    }
    record("N10-user-modified-owned-file-rollback-refusal",
           "exit=8 (ROLLBACK_CONFLICT) 且 bytes_unchanged=True",
           "exit=%s error_code=%s bytes_unchanged=%s"
           % (code, observed["error_code"], observed["bytes_unchanged"]),
           code == 8 and observed["bytes_unchanged"], observed)
    return observed


def n11_install_midway_failure_reverts(tmp, repo, package):
    """安装中途失败必须精确回退已提交 owned 项，并保留原有字节。"""
    sandbox, target = make_sandbox(tmp)
    # 预置一个同名文件，使 workflows/lvw 的 rename 在提交阶段失败
    (target / "workflows").write_bytes(b"NOT A DIRECTORY\n")
    before = sorted(p.relative_to(target).as_posix() for p in target.rglob("*"))
    code, payload, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target)])
    after = sorted(p.relative_to(target).as_posix() for p in target.rglob("*"))
    detail = (payload or {}).get("detail") or {}
    cleanup = detail.get("cleanup") or {}
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_after": after,
        "pre_existing_file_intact": (target / "workflows").exists()
        and (target / "workflows").read_bytes() == b"NOT A DIRECTORY\n",
        "no_owned_bridge_dir": not (target / "custom_nodes/lvw_v0_bridge").exists(),
        "removed_owned_paths": cleanup.get("removed_owned_paths"),
        "staging_removed": cleanup.get("staging_removed"),
        "original_failure_preserved": bool(detail.get("original_failure")),
    }
    record("N11-install-midway-failure-precise-revert",
           "exit!=0 且 pre_existing_file_intact=True 且 no_owned_bridge_dir=True",
           "exit=%s error_code=%s intact=%s no_owned=%s"
           % (code, observed["error_code"], observed["pre_existing_file_intact"],
              observed["no_owned_bridge_dir"]),
           code != 0 and observed["pre_existing_file_intact"]
           and observed["no_owned_bridge_dir"], observed)
    return observed


def n9_install_symlink_parent_escape(tmp, repo, package):
    """父目录 symlink 逃逸：target 指向 sandbox 之外必须被拒绝。"""
    sandbox, _ = make_sandbox(tmp)
    outside = tmp / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    link = sandbox / "link"
    link.symlink_to(outside, target_is_directory=True)
    target = link / "目标"
    code, payload, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target)])
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "outside_entries": sorted(p.name for p in outside.iterdir()),
        "escape_rejected": code != 0 and not any(outside.iterdir()),
    }
    record("N9-install-symlink-parent-escape",
           "escape_rejected=True (target 经 symlink 逃出 sandbox 必须拒绝且 0 写入)",
           "exit=%s error_code=%s outside_empty=%s"
           % (code, observed["error_code"], not any(outside.iterdir())),
           observed["escape_rejected"], observed)
    return observed



# --------------------------------------------------------------------------- #
# correction-01 追加：所有权记录与收据路径字段负例
# --------------------------------------------------------------------------- #

OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"


def _tree_snapshot(root):
    """目标内所有文件（含所有权记录）的相对路径 -> sha256。"""
    out = {}
    root = Path(root)
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = sha256_bytes(path.read_bytes())
    return out


def _install(tmp, package, sandbox, target, receipt_path):
    code, payload, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target), "--receipt-out", str(receipt_path)])
    assert code == 0, (code, so, se)
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def n12_ownership_record_missing(tmp, repo, package):
    """目标内所有权记录缺失：必须拒绝且 owned 文件零删除。"""
    sandbox, target = make_sandbox(tmp)
    receipt_path = tmp / "install-receipt.json"
    _install(tmp, package, sandbox, target, receipt_path)
    record_path = target / OWNERSHIP_FILE_NAME
    assert record_path.is_file()
    installed_owned = _installed_owned_files(target)
    record_path.unlink()

    before = _tree_snapshot(target)
    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    after = _tree_snapshot(target)
    owned_remaining = _installed_owned_files(target)
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_unchanged": before == after,
        "owned_files_preserved": len(owned_remaining),
        "owned_files_before": len(installed_owned),
    }
    record("N12-rollback-missing-ownership-record",
           "exit!=0 且 owned 文件一个都没被删",
           "exit=%s owned_files_preserved=%d/%d"
           % (code, len(owned_remaining), len(installed_owned)),
           code != 0 and owned_remaining == installed_owned, observed)
    return observed


def n13_ownership_record_tampered(tmp, repo, package):
    """目标内所有权记录被改写：必须拒绝且 owned 文件零删除。"""
    sandbox, target = make_sandbox(tmp)
    receipt_path = tmp / "install-receipt.json"
    _install(tmp, package, sandbox, target, receipt_path)
    record_path = target / OWNERSHIP_FILE_NAME
    ownership = json.loads(record_path.read_text(encoding="utf-8"))
    ownership["owned"]["files"][0]["sha256"] = "0" * 64
    record_path.write_text(json.dumps(ownership, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    before = _tree_snapshot(target)
    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    after = _tree_snapshot(target)
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_unchanged": before == after,
    }
    record("N13-rollback-tampered-ownership-record",
           "exit!=0 且 tree_unchanged=True",
           "exit=%s tree_unchanged=%s" % (code, observed["tree_unchanged"]),
           code != 0 and observed["tree_unchanged"], observed)
    return observed


def n14_session_mismatch(tmp, repo, package):
    """收据 session 与目标内记录不符：必须拒绝且 owned 文件零删除。"""
    sandbox, target = make_sandbox(tmp)
    receipt_path = tmp / "install-receipt.json"
    receipt = _install(tmp, package, sandbox, target, receipt_path)
    receipt["session_id"] = "sess-00000000000000000000000000000000"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    before = _tree_snapshot(target)
    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    after = _tree_snapshot(target)
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_unchanged": before == after,
    }
    record("N14-rollback-session-mismatch",
           "exit!=0 且 tree_unchanged=True",
           "exit=%s tree_unchanged=%s" % (code, observed["tree_unchanged"]),
           code != 0 and observed["tree_unchanged"], observed)
    return observed


def _mutations():
    """收据中全部可篡改的路径/身份字段。"""
    return {
        "owned_files_install_path": lambda r: r["owned"]["files"][0].__setitem__(
            "install_path", "../../victim.txt"),
        "owned_files_install_path_absolute": lambda r: r["owned"]["files"][0].__setitem__(
            "install_path", "/etc/passwd"),
        "owned_files_install_path_drive": lambda r: r["owned"]["files"][0].__setitem__(
            "install_path", "C:/Windows/system32/x.dll"),
        "owned_files_install_path_backslash": lambda r: r["owned"]["files"][0].__setitem__(
            "install_path", "..\\..\\victim.txt"),
        "owned_directories": lambda r: r["owned"].__setitem__(
            "directories", ["../../外部 目录"]),
        "owned_created_directories": lambda r: r["owned"].__setitem__(
            "created_directories", ["../../外部 目录"]),
        "preimage_path": lambda r: r["preimage"]["files"][0].__setitem__(
            "path", "../../victim.txt"),
        "staging_path": lambda r: r["staging"].__setitem__(
            "path", "../../外部 目录"),
        "target": lambda r: r.__setitem__("target", "../../外部 目录"),
        "session_id": lambda r: r.__setitem__(
            "session_id", "sess-deadbeefdeadbeefdeadbeefdeadbeef"),
    }


def n15_every_tampered_receipt_field_is_rejected(tmp, repo, package):
    """收据的每一个路径/身份字段被篡改都必须非零拒绝，且整树不变、victim 不动。"""
    sandbox, target = make_sandbox(tmp)
    (target / "哨兵 文件.txt").write_bytes(b"SENTINEL\n")
    victim = tmp / "victim.txt"
    victim_bytes = b"VICTIM-NOT-OWNED-DO-NOT-DELETE\n"
    victim.write_bytes(victim_bytes)
    receipt_path = tmp / "install-receipt.json"
    original = _install(tmp, package, sandbox, target, receipt_path)

    baseline = _tree_snapshot(target)
    results = {}
    all_rejected = True
    all_unchanged = True
    for label, mutate in _mutations().items():
        receipt = json.loads(json.dumps(original))
        mutate(receipt)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        code, payload, so, se = run([
            "rollback", "--receipt", str(receipt_path), "--target", str(target)])
        unchanged = _tree_snapshot(target) == baseline
        victim_ok = victim.exists() and victim.read_bytes() == victim_bytes
        results[label] = {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            "tree_unchanged": unchanged,
            "victim_unchanged": victim_ok,
        }
        if code == 0 or not unchanged or not victim_ok:
            all_rejected = False
            all_unchanged = False
    observed = {
        "mutations": results,
        "all_rejected": all_rejected,
        "all_unchanged": all_unchanged,
        "victim_still_exists": victim.exists(),
    }
    record("N15-every-tampered-receipt-field-rejected",
           "全部字段 exit!=0 且整树不变且 victim 不变",
           "all_rejected=%s all_unchanged=%s"
           % (observed["all_rejected"], observed["all_unchanged"]),
           all_rejected and all_unchanged, observed)
    return observed


def n16_precheck_failure_leaves_whole_tree_untouched(tmp, repo, package):
    """预检失败：目标整树、外部 victim、哨兵都零写入零删除。"""
    sandbox, target = make_sandbox(tmp)
    (target / "哨兵 文件.txt").write_bytes(b"SENTINEL\n")
    victim = tmp / "victim.txt"
    victim_bytes = b"VICTIM\n"
    victim.write_bytes(victim_bytes)
    receipt_path = tmp / "install-receipt.json"
    receipt = _install(tmp, package, sandbox, target, receipt_path)
    receipt["owned"]["files"][0]["install_path"] = "../../victim.txt"
    receipt["owned"]["files"][0]["sha256"] = sha256_bytes(victim_bytes)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    before = _tree_snapshot(target)
    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    after = _tree_snapshot(target)
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "tree_unchanged": before == after,
        "victim_unchanged": victim.exists() and victim.read_bytes() == victim_bytes,
        "sentinel_unchanged": sha256_bytes((target / "哨兵 文件.txt").read_bytes()),
    }
    record("N16-precheck-failure-zero-write-zero-delete",
           "exit!=0 且 tree_unchanged=True 且 victim_unchanged=True",
           "exit=%s tree_unchanged=%s victim_unchanged=%s"
           % (code, observed["tree_unchanged"], observed["victim_unchanged"]),
           code != 0 and observed["tree_unchanged"] and observed["victim_unchanged"],
           observed)
    return observed


def n17_redacted_receipt_with_explicit_target(tmp, repo, package):
    """脱敏收据 + 显式 --target：仍可正常回滚（不因脱敏放宽身份）。"""
    sandbox, target = make_sandbox(tmp)
    (target / "哨兵 文件.txt").write_bytes(b"SENTINEL\n")
    receipt_path = tmp / "install-receipt.json"
    code, payload, so, se = run([
        "install", "--package", str(package), "--sandbox-parent", str(sandbox),
        "--target", str(target), "--receipt-out", str(receipt_path),
        "--redact-root", str(tmp)])
    assert code == 0, (code, so, se)
    receipt_text = receipt_path.read_text(encoding="utf-8")
    redacted = "<redacted-root>" in receipt_text
    absolute_leak = str(tmp) in receipt_text

    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target)])
    remaining = sorted(p.relative_to(target).as_posix()
                       for p in target.rglob("*") if p.is_file())
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "receipt_redacted": redacted,
        "absolute_path_leaked": absolute_leak,
        "remaining_files": remaining,
    }
    record("N17-redacted-receipt-with-explicit-target",
           "exit=0 且收据已脱敏且回滚后只剩哨兵",
           "exit=%s redacted=%s remaining=%d"
           % (code, redacted, len(remaining)),
           code == 0 and redacted and remaining == ["哨兵 文件.txt"], observed)
    return observed


def main():
    global RAW_DIR
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    RAW_DIR = out_dir / "raw" / "probes"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(REPO_ROOT),
                          stdout=subprocess.PIPE, check=True).stdout.decode().strip()
    global REDACT_ROOTS
    with tempfile.TemporaryDirectory(prefix="lvw-corr01-probe-") as td:
        tmp = Path(td)
        REDACT_ROOTS = [str(tmp), str(repo), str(TOOL)]
        package = build_package(tmp, repo, CANDIDATE)

        def sub(name):
            d = tmp / name
            d.mkdir(parents=True, exist_ok=True)
            return d

        n1_path_traversal_in_receipt(sub("N1"), repo, package)
        n2_staging_path_rmtree(sub("N2"), repo, package)
        n3_cross_target_rollback(sub("N3"), repo, package)
        n4_zip_bomb_lying_header(sub("N4"), repo, package)
        n5_existing_unowned_conflict(sub("N5"), repo, package)
        n6_diagnose_failure_zero_write(sub("N6"), repo, package)
        n7_build_reads_git_objects(sub("N7"), repo)
        n8_windows_name_semantics(sub("N8"), repo, package)
        n10_user_modified_owned_file_blocks_rollback(sub("N10"), repo, package)
        n11_install_midway_failure_reverts(sub("N11"), repo, package)
        n9_install_symlink_parent_escape(sub("N9"), repo, package)
        n12_ownership_record_missing(sub("N12"), repo, package)
        n13_ownership_record_tampered(sub("N13"), repo, package)
        n14_session_mismatch(sub("N14"), repo, package)
        n15_every_tampered_receipt_field_is_rejected(sub("N15"), repo, package)
        n16_precheck_failure_leaves_whole_tree_untouched(sub("N16"), repo, package)
        n17_redacted_receipt_with_explicit_target(sub("N17"), repo, package)
        leftover = sorted(p.name for p in tmp.iterdir())
    payload = {
        "kind": "S3_PREP_B_CORRECTION_01_NEGATIVE_PROBES",
        "candidate_commit": CANDIDATE,
        "adapted_from": "reports/v0-s3/preparation-04/independent-01/probe/negative_probes.py",
        "probes": RESULTS,
        "temp_root_removed_after_run": True,
        "temp_root_leftover_entries": leftover,
        "product_runtime_calls": 0,
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (out_dir / "negative-probes.json").write_text(
        _redact_text(payload_text), encoding="utf-8")
    print(_redact_text(payload_text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
