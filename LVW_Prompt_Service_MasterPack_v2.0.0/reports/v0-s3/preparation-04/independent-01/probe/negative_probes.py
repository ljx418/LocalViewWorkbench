#!/usr/bin/env python3
"""independent-01 独审：代表性独立负例复算（少量、有代表性）。

覆盖：
  N1 篡改 install receipt 的 owned.files[].install_path -> rollback 路径穿越删除非 owned 文件
  N2 篡改 install receipt 的 staging.path            -> rollback 递归删除任意目录
  N3 跨目标回滚（同名不同目录）                        -> rollback 是否只按 basename 绑定
  N4 zip bomb（谎报 zip 头部 file_size）               -> diagnose/install 的上限与炸弹判定
  N5 已有非 owned 冲突                                  -> install 必须 0 写入
  N6 诊断失败                                          -> target 零写入（不留空目录）
  N7 脏工作树                                          -> build 仍从 commit 读字节

全部写入都在自有 TemporaryDirectory 内合成，不触碰真实宿主或用户路径。
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

PACK_ROOT = Path(__file__).resolve().parents[5]
REPO_ROOT = PACK_ROOT
TOOL_REL = "tools/v0_incremental_package.py"
TOOL = PACK_ROOT / TOOL_REL
CANDIDATE = "1c09cd651478beeb4c1bca026505364051a72892"
MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
TOOL_NAME = "v0_incremental_package.py"

RESULTS = []


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


RAW_DIR = None
_RAW_SEQ = [0]


def run(argv, cwd=None):
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + argv,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        payload = None
    if RAW_DIR is not None:
        _RAW_SEQ[0] += 1
        stem = "probe-%02d" % _RAW_SEQ[0]
        (RAW_DIR / (stem + ".command.log")).write_text(
            "python3 " + " ".join(str(a) for a in argv) + "\n", encoding="utf-8")
        (RAW_DIR / (stem + ".stdout.log")).write_bytes(proc.stdout)
        (RAW_DIR / (stem + ".stderr.log")).write_bytes(proc.stderr)
        (RAW_DIR / (stem + ".exit.log")).write_text(
            "%d\n" % proc.returncode, encoding="utf-8")
    return proc.returncode, payload, proc.stdout, proc.stderr


def record(probe, expectation, observed, ok, detail=None):
    RESULTS.append({
        "probe": probe,
        "expectation": expectation,
        "observed": observed,
        "matches_expectation": ok,
        "detail": detail or {},
    })
    print("[%s] expect=%s observed=%s" % (probe, expectation, observed))


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
    b_files_before = sorted(p.relative_to(target_b).as_posix() for p in target_b.rglob("*") if p.is_file())
    marker = target_b / "非 owned 标记.txt"
    marker.write_bytes(b"USER\n")

    code, payload, so, se = run([
        "rollback", "--receipt", str(receipt_path), "--target", str(target_b)])
    b_files_after = sorted(p.relative_to(target_b).as_posix() for p in target_b.rglob("*") if p.is_file())
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


def main():
    global RAW_DIR
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    RAW_DIR = out_dir / "raw" / "probes"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(REPO_ROOT),
                          stdout=subprocess.PIPE, check=True).stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix="lvw-indep-01-probe-") as td:
        tmp = Path(td)
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
        leftover = sorted(p.name for p in tmp.iterdir())
    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_NEGATIVE_PROBES",
        "candidate_commit": CANDIDATE,
        "probes": RESULTS,
        "temp_root_removed_after_run": True,
        "temp_root_leftover_entries": leftover,
        "product_runtime_calls": 0,
    }
    (out_dir / "negative-probes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
