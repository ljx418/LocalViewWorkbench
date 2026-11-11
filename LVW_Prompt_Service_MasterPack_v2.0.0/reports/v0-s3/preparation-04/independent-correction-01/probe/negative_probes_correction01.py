#!/usr/bin/env python3
"""independent-correction-01 独审：针对 correction-01 候选的独立负例复算。

本脚本由独审者独立编写，**不复用**实现者的 `implementation/correction-01/probe/negative_probes.py`。
它复用独审 independent-01 自己写过的驱动骨架（`run()` / `make_sandbox()` / `tree_snapshot()`），
但全部 oracle 都是本轮新写的、按 correction-01 合同重新表述的判据。

覆盖：

  P01 F-01 收据 owned.files[].install_path 路径穿越   -> 必须拒绝，外部 victim 零删除、整树不变
  P02 F-02 收据 staging.path 指向任意目录             -> 必须拒绝，victim 目录零删除
  P03 M-01 同名不同沙箱的跨目标回滚                   -> 必须拒绝，另一沙箱整树不变
  P04 收据 owned.directories 路径穿越                  -> 必须拒绝，零删除
  P05 收据 owned.created_directories 路径穿越          -> 必须拒绝，零删除
  P06 收据 preimage.files[].path 路径穿越             -> 必须拒绝，零删除
  P07 收据 session_id 与本地所有权记录不符             -> 必须拒绝，零删除
  P08 目标内所有权记录缺失                            -> 必须拒绝，零删除
  P09 目标内所有权记录被改写（owned 清单）             -> 必须拒绝，零删除
  P10 目标内所有权记录被改写且攻击者重算 install_hash  -> 必须被外部收据交叉核对拦下，零删除
  P11 沙箱 marker 缺失                                -> 必须拒绝，零删除
  P12 沙箱 marker 内容被改                            -> 必须拒绝，零删除
  P13 收据 target 被改绑到另一沙箱                    -> 必须拒绝，零删除
  P14 晚失败：staging 残留仍在                       -> 必须失败，且不得 rmtree 该残留
  P15 晚失败：owned 文件被用户改写（29 项中的一项）    -> 必须失败，其余 28 项也必须零删除
  P16 脱敏收据 + 显式 --target                        -> 必须成功回滚
  P17 脱敏收据 + 显式 --target 指向别的目标           -> 必须拒绝，零删除
  P18 脱敏收据 + 不给 --target                        -> 必须 BAD_INPUT
  P19 Windows 段尾随点 / 段尾随空格 / 保留设备名      -> 必须 PATH_REJECTED
  P20 外部 --manifest 非法 JSON / 不可读              -> 必须 BAD_INPUT
  P21 回滚绝不 rmtree 任何外部收据指向的目录           -> victim 目录内容必须原样存在

全部写入都在自有 TemporaryDirectory 内合成，不触碰真实宿主、用户路径或真实媒体。
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
TOOL_NAME = "v0_incremental_package.py"
OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"

EXIT_CODES = {
    "OK": 0,
    "BAD_INPUT": 2,
    "INTEGRITY_MISMATCH": 3,
    "PATH_REJECTED": 4,
    "SIZE_LIMIT": 5,
    "CONFLICT": 6,
    "INSTALL_FAILED": 7,
    "ROLLBACK_CONFLICT": 8,
    "INTERNAL_ERROR": 9,
}

RESULTS = []
RAW_DIR = None
_SEQ = [0]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(argv, cwd=None):
    """黑盒调用 CLI；原始 stdout/stderr/exit 逐条落到 raw/probes/。"""
    proc = subprocess.run(
        [sys.executable, str(TOOL)] + [str(a) for a in argv],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or REPO_ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        payload = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        payload = None
    if RAW_DIR is not None:
        _SEQ[0] += 1
        stem = "probe-%02d" % _SEQ[0]
        (RAW_DIR / (stem + ".command.log")).write_text(
            "python3 " + " ".join(str(a) for a in argv) + "\n", encoding="utf-8"
        )
        (RAW_DIR / (stem + ".stdout.log")).write_bytes(proc.stdout)
        (RAW_DIR / (stem + ".stderr.log")).write_bytes(proc.stderr)
        (RAW_DIR / (stem + ".exit.log")).write_text(
            "%d\n" % proc.returncode, encoding="utf-8"
        )
    return proc.returncode, payload, proc.stdout, proc.stderr


def record(probe, expectation, observed, ok):
    RESULTS.append(
        {
            "probe": probe,
            "expectation": expectation,
            "observed": observed,
            "matches_expectation": bool(ok),
        }
    )
    print("[%s] expect=%s observed=%s" % (probe, expectation, observed))
    return observed


def tree_snapshot(root: Path):
    """对整棵树做 (相对路径, 类型, 内容 sha256) 快照，用于"零写入零删除"判定。"""
    entries = []
    if not root.exists():
        return entries
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(dirnames):
            full = Path(dirpath) / name
            entries.append(
                (full.relative_to(root).as_posix(), "dir", None)
            )
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                entries.append((rel, "symlink", os.readlink(str(full))))
            else:
                entries.append((rel, "file", sha256_bytes(full.read_bytes())))
    entries.sort()
    return entries


def make_sandbox(root: Path, name="隔离 沙箱根", target_name="隔离 目标 目录", marker=True):
    sandbox = root / name
    target = sandbox / target_name
    sandbox.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    if marker:
        (sandbox / MARKER_NAME).write_text(
            json.dumps({"magic": MARKER_MAGIC, "tool": TOOL_NAME}), encoding="utf-8"
        )
    sentinel = target / "哨兵 文件.txt"
    sentinel.write_bytes(b"SENTINEL-ORIGINAL-BYTES\n")
    return sandbox, target, sentinel


def install_ok(package, sandbox, target, receipt_path, *extra):
    code, payload, so, se = run(
        [
            "install",
            "--package", str(package),
            "--sandbox-parent", str(sandbox),
            "--target", str(target),
            "--receipt-out", str(receipt_path),
        ]
        + list(extra)
    )
    assert code == EXIT_CODES["OK"], (code, so, se)
    return payload


def read_receipt(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_receipt(path, receipt):
    Path(path).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_package(root: Path, repo: str, name="pkg.zip"):
    out = root / name
    code, payload, so, se = run(
        ["build", "--repo", str(repo), "--commit", CANDIDATE, "--out", str(out)]
    )
    assert code == 0, (code, so, se)
    return out


def rejected(probe, expectation, code, payload, tree_before, tree_after,
             extra=None, expect_code=None):
    """统一的"拒绝且零副作用"判定。"""
    observed = {
        "exit_code": code,
        "error_code": (payload or {}).get("error_code"),
        "target_tree_unchanged": tree_before == tree_after,
        "removed_files": ((payload or {}).get("detail") or {}).get("removed_files"),
    }
    if extra:
        observed.update(extra)
    ok = code != 0 and observed["target_tree_unchanged"]
    if expect_code is not None:
        ok = ok and code == expect_code
    return record(probe, expectation, observed, ok)


# --------------------------------------------------------------------------- #
# P01 / F-01
# --------------------------------------------------------------------------- #
def p01_f01_receipt_path_traversal(tmp, package):
    sub = tmp
    sandbox, target, sentinel = make_sandbox(sub)
    victim = sub / "victim.txt"
    victim_bytes = b"VICTIM-NOT-OWNED-DO-NOT-DELETE\n"
    victim.write_bytes(victim_bytes)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["owned"]["files"][0] = {
        "install_path": "../../victim.txt",
        "sha256": sha256_bytes(victim_bytes),
        "length": len(victim_bytes),
    }
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_still_exists": victim.exists(),
        "victim_bytes_unchanged": victim.exists()
        and sha256_bytes(victim.read_bytes()) == sha256_bytes(victim_bytes),
        "sentinel_unchanged": sha256_bytes(sentinel.read_bytes())
        == sha256_bytes(b"SENTINEL-ORIGINAL-BYTES\n"),
    }
    observed = rejected(
        "P01-F01-receipt-owned-install-path-traversal",
        "exit=4(PATH_REJECTED) 且 目标整树不变 且 外部 victim 存在且字节不变",
        code, payload, before, after, extra,
        expect_code=EXIT_CODES["PATH_REJECTED"],
    )
    ok = (
        observed["target_tree_unchanged"]
        and observed["victim_still_exists"]
        and observed["victim_bytes_unchanged"]
        and observed["sentinel_unchanged"]
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] == EXIT_CODES["PATH_REJECTED"]
        and observed["target_tree_unchanged"]
        and observed["victim_still_exists"]
        and observed["victim_bytes_unchanged"]
        and observed["sentinel_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P02 / F-02
# --------------------------------------------------------------------------- #
def p02_f02_receipt_staging_path(tmp, package):
    sub = tmp
    sandbox, target, sentinel = make_sandbox(sub)
    victim_dir = sub / "victim_dir"
    (victim_dir / "sub").mkdir(parents=True)
    (victim_dir / "sub" / "keep.txt").write_bytes(b"KEEP-NOT-OWNED\n")
    victim_before = tree_snapshot(victim_dir)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["staging"] = {"path": str(victim_dir), "removed": False}
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    victim_after = tree_snapshot(victim_dir)
    extra = {
        "victim_dir_still_exists": victim_dir.exists(),
        "victim_dir_tree_unchanged": victim_before == victim_after,
        "victim_file_still_present": (victim_dir / "sub" / "keep.txt").exists(),
    }
    observed = rejected(
        "P02-F02-receipt-staging-path-arbitrary-rmtree",
        "exit!=0 且 目标整树不变 且 外部 victim 目录及其内容原样存在",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_dir_still_exists"]
        and observed["victim_dir_tree_unchanged"]
        and observed["victim_file_still_present"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P03 / M-01
# --------------------------------------------------------------------------- #
def p03_m01_cross_sandbox(tmp, package):
    sub = tmp
    sandbox_a, target_a, _s1 = make_sandbox(sub, "沙箱 A", "同一 目标")
    sandbox_b, target_b, _s2 = make_sandbox(sub, "沙箱 B", "同一 目标")
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox_a, target_a, receipt_path)
    install_ok(package, sandbox_b, target_b, sub / "receipt-b.json")
    marker = target_b / "非 owned 标记.txt"
    marker.write_bytes(b"USER\n")

    b_before = tree_snapshot(target_b)
    a_before = tree_snapshot(target_a)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target_b)]
    )
    b_after = tree_snapshot(target_b)
    a_after = tree_snapshot(target_a)
    extra = {
        "sandbox_b_tree_unchanged": b_before == b_after,
        "sandbox_a_tree_unchanged": a_before == a_after,
        "non_owned_marker_still_exists": marker.exists(),
        "b_owned_file_count_before": len([e for e in b_before if e[1] == "file"]),
        "b_owned_file_count_after": len([e for e in b_after if e[1] == "file"]),
    }
    observed = rejected(
        "P03-M01-cross-sandbox-same-basename-rollback",
        "exit!=0 且 沙箱B 整树不变（含其 owned 文件与非 owned 标记）且 沙箱A 整树不变",
        code, payload, b_before, b_after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["sandbox_b_tree_unchanged"]
        and observed["sandbox_a_tree_unchanged"]
        and observed["non_owned_marker_still_exists"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P04 / P05 / P06  其它收据路径字段
# --------------------------------------------------------------------------- #
def p04_owned_directories_traversal(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim_dir = sub / "victim_dir"
    victim_dir.mkdir(parents=True)
    (victim_dir / "keep.txt").write_bytes(b"KEEP\n")
    victim_before = tree_snapshot(victim_dir)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["owned"]["directories"] = ["../../victim_dir"]
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_dir_tree_unchanged": victim_before == tree_snapshot(victim_dir),
        "victim_dir_still_exists": victim_dir.exists(),
    }
    observed = rejected(
        "P04-receipt-owned-directories-traversal",
        "exit!=0 且 目标整树不变 且 外部 victim 目录原样存在",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_dir_tree_unchanged"]
        and observed["victim_dir_still_exists"]
    )
    return observed


def p05_created_directories_traversal(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim_dir = sub / "victim_dir"
    victim_dir.mkdir()
    (victim_dir / "keep.txt").write_bytes(b"KEEP\n")
    victim_before = tree_snapshot(victim_dir)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["owned"]["created_directories"] = ["../../victim_dir"]
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_dir_tree_unchanged": victim_before == tree_snapshot(victim_dir),
        "victim_dir_still_exists": victim_dir.exists(),
    }
    observed = rejected(
        "P05-receipt-owned-created-directories-traversal",
        "exit!=0 且 目标整树不变 且 外部 victim 目录原样存在",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_dir_tree_unchanged"]
        and observed["victim_dir_still_exists"]
    )
    return observed


def p06_preimage_path_traversal(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim = sub / "victim.txt"
    victim_bytes = b"VICTIM\n"
    victim.write_bytes(victim_bytes)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["preimage"]["files"].append(
        {
            "path": "../../victim.txt",
            "kind": "file",
            "length": len(victim_bytes),
            "sha256": sha256_bytes(victim_bytes),
        }
    )
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_still_exists": victim.exists(),
        "victim_bytes_unchanged": victim.exists()
        and sha256_bytes(victim.read_bytes()) == sha256_bytes(victim_bytes),
    }
    observed = rejected(
        "P06-receipt-preimage-path-traversal",
        "exit!=0 且 目标整树不变 且 外部 victim 存在且字节不变",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_still_exists"]
        and observed["victim_bytes_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P07 session 不符
# --------------------------------------------------------------------------- #
def p07_session_mismatch(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["session_id"] = "sess-0000000000000000000000000000dead"
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {"ownership_record_still_present": (target / OWNERSHIP_FILE_NAME).exists()}
    observed = rejected(
        "P07-receipt-session-mismatch",
        "exit=8(ROLLBACK_CONFLICT) 且 目标整树不变（零删除）",
        code, payload, before, after, extra,
        expect_code=EXIT_CODES["ROLLBACK_CONFLICT"],
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] == EXIT_CODES["ROLLBACK_CONFLICT"]
        and observed["target_tree_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P08 所有权记录缺失
# --------------------------------------------------------------------------- #
def p08_ownership_record_missing(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)
    (target / OWNERSHIP_FILE_NAME).unlink()

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    observed = rejected(
        "P08-ownership-record-missing",
        "exit=8(ROLLBACK_CONFLICT) 且 目标整树不变（零删除）",
        code, payload, before, after,
        expect_code=EXIT_CODES["ROLLBACK_CONFLICT"],
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] == EXIT_CODES["ROLLBACK_CONFLICT"]
        and observed["target_tree_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P09 所有权记录被改写（owned 清单）
# --------------------------------------------------------------------------- #
def p09_ownership_record_tampered(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim = sub / "victim.txt"
    victim_bytes = b"VICTIM\n"
    victim.write_bytes(victim_bytes)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    record_path = target / OWNERSHIP_FILE_NAME
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["owned"]["files"][0] = {
        "install_path": "../../victim.txt",
        "sha256": sha256_bytes(victim_bytes),
        "length": len(victim_bytes),
    }
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_still_exists": victim.exists(),
        "victim_bytes_unchanged": victim.exists()
        and sha256_bytes(victim.read_bytes()) == sha256_bytes(victim_bytes),
    }
    observed = rejected(
        "P09-ownership-record-tampered-owned-list",
        "exit!=0 且 目标整树不变 且 外部 victim 存在且字节不变",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_still_exists"]
        and observed["victim_bytes_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P10 同权限攻击者改写记录并重算 install_hash
#     合同只要求"有限威胁边界"，但仍不得借此重绑到外部 victim：
#     外部收据交叉核对必须独立拦下。
# --------------------------------------------------------------------------- #
def p10_ownership_record_rewritten_with_recomputed_hash(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim = sub / "victim.txt"
    victim_bytes = b"VICTIM\n"
    victim.write_bytes(victim_bytes)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    record_path = target / OWNERSHIP_FILE_NAME
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["owned"]["files"][0] = {
        "install_path": "../../victim.txt",
        "sha256": sha256_bytes(victim_bytes),
        "length": len(victim_bytes),
    }
    # 攻击者按工具同一算法重算 install_hash（有限威胁边界内的最强尝试）
    core = {
        "schema_version": record["schema_version"],
        "session_id": record["session_id"],
        "target_identity": record["target_identity"],
        "sandbox_parent": record["sandbox_parent"],
        "sandbox_marker_sha256": record["sandbox_marker"]["sha256"],
        "source_commit": record["source_commit"],
        "manifest_sha256": record["manifest_sha256"],
        "package_sha256": record["package_sha256"],
        "payload_fingerprint_sha256": record["payload_fingerprint_sha256"],
        "owned": {
            "files": [
                {
                    "install_path": e["install_path"],
                    "sha256": e["sha256"],
                    "length": e["length"],
                }
                for e in record["owned"]["files"]
            ],
            "directories": list(record["owned"]["directories"]),
            "created_directories": list(record["owned"]["created_directories"]),
        },
        "installed_top_level": list(record["installed_top_level"]),
        "created_target_root": bool(record["created_target_root"]),
        "staging_path_sha256": record["staging"]["path_sha256"],
    }
    canonical = json.dumps(
        core, ensure_ascii=False, indent=2, sort_keys=True, default=str
    ) + "\n"
    record["install_hash"] = sha256_bytes(canonical.encode("utf-8"))
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_still_exists": victim.exists(),
        "victim_bytes_unchanged": victim.exists()
        and sha256_bytes(victim.read_bytes()) == sha256_bytes(victim_bytes),
        "install_hash_recomputed_by_attacker": True,
    }
    observed = rejected(
        "P10-ownership-record-rewritten-with-recomputed-install-hash",
        "exit!=0（外部收据交叉核对必须拦下重绑）且 目标整树不变 且 外部 victim 存在且字节不变",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["victim_still_exists"]
        and observed["victim_bytes_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P11 / P12 沙箱 marker
# --------------------------------------------------------------------------- #
def p11_marker_missing(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)
    (sandbox / MARKER_NAME).unlink()

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    observed = rejected(
        "P11-sandbox-marker-missing",
        "exit!=0 且 目标整树不变（零删除）",
        code, payload, before, after,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0 and observed["target_tree_unchanged"]
    )
    return observed


def p12_marker_content_changed(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)
    (sandbox / MARKER_NAME).write_text(
        json.dumps({"magic": MARKER_MAGIC, "tool": "OTHER-TOOL"}), encoding="utf-8"
    )

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    observed = rejected(
        "P12-sandbox-marker-content-changed",
        "exit!=0 且 目标整树不变（零删除）",
        code, payload, before, after,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0 and observed["target_tree_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P13 收据 target 被改绑到另一沙箱
# --------------------------------------------------------------------------- #
def p13_receipt_target_rebound(tmp, package):
    sub = tmp
    sandbox_a, target_a, _s1 = make_sandbox(sub, "沙箱 A", "同一 目标")
    sandbox_b, target_b, _s2 = make_sandbox(sub, "沙箱 B", "同一 目标")
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox_a, target_a, receipt_path)
    install_ok(package, sandbox_b, target_b, sub / "receipt-b.json")
    marker = target_b / "非 owned 标记.txt"
    marker.write_bytes(b"USER\n")

    receipt = read_receipt(receipt_path)
    receipt["target"] = str(target_b)
    write_receipt(receipt_path, receipt)

    a_before = tree_snapshot(target_a)
    b_before = tree_snapshot(target_b)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target_a)]
    )
    a_after = tree_snapshot(target_a)
    b_after = tree_snapshot(target_b)
    extra = {
        "sandbox_a_tree_unchanged": a_before == a_after,
        "sandbox_b_tree_unchanged": b_before == b_after,
        "non_owned_marker_still_exists": marker.exists(),
    }
    observed = rejected(
        "P13-receipt-target-rebound-to-other-sandbox",
        "exit!=0 且 两个沙箱整树都不变（不得借改绑跨沙箱删除）",
        code, payload, a_before, a_after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["sandbox_a_tree_unchanged"]
        and observed["sandbox_b_tree_unchanged"]
        and observed["non_owned_marker_still_exists"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P14 晚失败：staging 残留
# --------------------------------------------------------------------------- #
def p14_residual_staging_is_never_rmtree(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    # 造一个"残留的 staging"：名字带本工具前缀、位于沙箱内、内容非空
    residual = sandbox / (".lvw-v0-stage-residual")
    (residual / "sub").mkdir(parents=True)
    (residual / "sub" / "keep.txt").write_bytes(b"RESIDUAL-KEEP\n")
    residual_before = tree_snapshot(residual)

    record_path = target / OWNERSHIP_FILE_NAME
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["staging"] = {
        "path": str(residual),
        "path_sha256": sha256_bytes(str(residual).encode("utf-8")),
        "removed": False,
    }
    # 重算 install_hash，让本地记录自洽（否则只会被 install_hash 检查拦下，
    # 那样就测不到 staging 终态分支）。
    core = {
        "schema_version": record["schema_version"],
        "session_id": record["session_id"],
        "target_identity": record["target_identity"],
        "sandbox_parent": record["sandbox_parent"],
        "sandbox_marker_sha256": record["sandbox_marker"]["sha256"],
        "source_commit": record["source_commit"],
        "manifest_sha256": record["manifest_sha256"],
        "package_sha256": record["package_sha256"],
        "payload_fingerprint_sha256": record["payload_fingerprint_sha256"],
        "owned": {
            "files": [
                {
                    "install_path": e["install_path"],
                    "sha256": e["sha256"],
                    "length": e["length"],
                }
                for e in record["owned"]["files"]
            ],
            "directories": list(record["owned"]["directories"]),
            "created_directories": list(record["owned"]["created_directories"]),
        },
        "installed_top_level": list(record["installed_top_level"]),
        "created_target_root": bool(record["created_target_root"]),
        "staging_path_sha256": record["staging"]["path_sha256"],
    }
    canonical = json.dumps(
        core, ensure_ascii=False, indent=2, sort_keys=True, default=str
    ) + "\n"
    record["install_hash"] = sha256_bytes(canonical.encode("utf-8"))
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # 外部收据同步 staging 绑定，才能走到 staging 终态检查
    receipt = read_receipt(receipt_path)
    receipt["staging"] = {
        "path": str(residual),
        "path_sha256": sha256_bytes(str(residual).encode("utf-8")),
        "removed": False,
    }
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "residual_staging_still_exists": residual.exists(),
        "residual_staging_tree_unchanged": residual_before
        == tree_snapshot(residual),
        "residual_file_still_present": (residual / "sub" / "keep.txt").exists(),
    }
    observed = rejected(
        "P14-late-failure-residual-staging-not-rmtree",
        "exit!=0 且 目标整树不变（零删除）且 残留 staging 目录与其内容必须原样存在（不得 rmtree）",
        code, payload, before, after, extra,
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] != 0
        and observed["target_tree_unchanged"]
        and observed["residual_staging_still_exists"]
        and observed["residual_staging_tree_unchanged"]
        and observed["residual_file_still_present"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P15 晚失败：用户改写了一个 owned 文件（29 项中的 1 项）
# --------------------------------------------------------------------------- #
def p15_late_failure_user_modified_owned_file(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    edited = target / "custom_nodes/lvw_v0_bridge/core.py"
    edited.write_bytes(b"# USER EDITED\n")
    edited_sha = sha256_bytes(edited.read_bytes())

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    owned_file_count = len(
        [e for e in before if e[1] == "file" and e[0].startswith("custom_nodes/")]
    )
    extra = {
        "edited_bytes_unchanged": edited.exists()
        and sha256_bytes(edited.read_bytes()) == edited_sha,
        "owned_file_count_before": owned_file_count,
        "owned_files_after": len(
            [e for e in after if e[1] == "file" and e[0].startswith("custom_nodes/")]
        ),
    }
    observed = rejected(
        "P15-late-failure-user-modified-owned-file-zero-deletion",
        "exit=8(ROLLBACK_CONFLICT) 且 目标整树不变（其余 owned 文件也必须零删除，不得先删 28 项再报错）",
        code, payload, before, after, extra,
        expect_code=EXIT_CODES["ROLLBACK_CONFLICT"],
    )
    RESULTS[-1]["matches_expectation"] = bool(
        observed["exit_code"] == EXIT_CODES["ROLLBACK_CONFLICT"]
        and observed["target_tree_unchanged"]
        and observed["edited_bytes_unchanged"]
    )
    return observed


# --------------------------------------------------------------------------- #
# P16 / P17 / P18 脱敏收据
# --------------------------------------------------------------------------- #
def p16_redacted_receipt_with_explicit_target(tmp, package):
    sub = tmp
    sandbox, target, sentinel = make_sandbox(sub)
    receipt_path = sub / "redacted-receipt.json"
    install_ok(
        package, sandbox, target, receipt_path,
        "--redact-root", str(sandbox),
    )
    receipt = read_receipt(receipt_path)
    redacted_target = receipt["target"]
    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    owned_after = [e for e in after if e[0].startswith("custom_nodes/")]
    extra = {
        "receipt_target_is_redacted": "<redacted-root>" in redacted_target,
        "owned_files_remaining_after_rollback": len(owned_after),
        "ownership_record_present_after": (target / OWNERSHIP_FILE_NAME).exists(),
        "sentinel_unchanged": sentinel.exists()
        and sha256_bytes(sentinel.read_bytes())
        == sha256_bytes(b"SENTINEL-ORIGINAL-BYTES\n"),
    }
    ok = (
        code == EXIT_CODES["OK"]
        and extra["receipt_target_is_redacted"]
        and extra["owned_files_remaining_after_rollback"] == 0
        and not extra["ownership_record_present_after"]
        and extra["sentinel_unchanged"]
    )
    record(
        "P16-redacted-receipt-with-explicit-target-rolls-back",
        "exit=0 且 收据 target 确为脱敏串 且 owned 文件全部移除 且 所有权记录被移除 且 哨兵不变",
        {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            **extra,
        },
        ok,
    )
    return {"exit_code": code, **extra}


def p17_redacted_receipt_with_wrong_explicit_target(tmp, package):
    sub = tmp
    sandbox_a, target_a, _s1 = make_sandbox(sub, "沙箱 A", "同一 目标")
    sandbox_b, target_b, _s2 = make_sandbox(sub, "沙箱 B", "同一 目标")
    receipt_path = sub / "redacted-receipt.json"
    install_ok(package, sandbox_a, target_a, receipt_path, "--redact-root", str(sandbox_a))
    install_ok(package, sandbox_b, target_b, sub / "receipt-b.json")
    marker = target_b / "非 owned 标记.txt"
    marker.write_bytes(b"USER\n")

    a_before = tree_snapshot(target_a)
    b_before = tree_snapshot(target_b)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target_b)]
    )
    a_after = tree_snapshot(target_a)
    b_after = tree_snapshot(target_b)
    extra = {
        "sandbox_a_tree_unchanged": a_before == a_after,
        "sandbox_b_tree_unchanged": b_before == b_after,
        "non_owned_marker_still_exists": marker.exists(),
    }
    ok = (
        code != 0
        and extra["sandbox_a_tree_unchanged"]
        and extra["sandbox_b_tree_unchanged"]
        and extra["non_owned_marker_still_exists"]
    )
    record(
        "P17-redacted-receipt-with-wrong-explicit-target-rejected",
        "exit!=0 且 两个沙箱整树都不变（脱敏不得成为重绑借口）",
        {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            **extra,
        },
        ok,
    )
    return {"exit_code": code, **extra}


def p18_redacted_receipt_without_target(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    receipt_path = sub / "redacted-receipt.json"
    install_ok(package, sandbox, target, receipt_path, "--redact-root", str(sandbox))
    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path)]
    )
    after = tree_snapshot(target)
    extra = {"target_tree_unchanged": before == after}
    ok = code == EXIT_CODES["BAD_INPUT"] and extra["target_tree_unchanged"]
    record(
        "P18-redacted-receipt-without-target-is-bad-input",
        "exit=2(BAD_INPUT) 且 目标整树不变",
        {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            **extra,
        },
        ok,
    )
    return {"exit_code": code, **extra}


# --------------------------------------------------------------------------- #
# P19 Windows 段尾随点 / 尾随空格 / 保留设备名
# --------------------------------------------------------------------------- #
def _craft_zip_with_member(base_package: Path, out: Path, extra_member: str):
    """在真实包基础上追加一个成员，并在 manifest 中如实登记它。"""
    with zipfile.ZipFile(base_package) as zf:
        members = [(i.filename, zf.read(i.filename)) for i in zf.infolist()]
    manifest = json.loads(dict(members)["meta/manifest.json"].decode("utf-8"))
    content = b"print('x')\n"
    rel = extra_member[len("payload/"):]
    manifest["items"].append(
        {
            "install_path": rel,
            "package_path": extra_member,
            "source_path": rel,
            "source_blob_id": "0" * 40,
            "source_mode": "100644",
            "length": len(content),
            "sha256": sha256_bytes(content),
        }
    )
    manifest["payload_item_count"] = len(manifest["items"])
    manifest["payload_expanded_bytes"] = sum(i["length"] for i in manifest["items"])
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    members = [(n, manifest_bytes if n == "meta/manifest.json" else d) for n, d in members]
    members.append((extra_member, content))
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100644) << 16
            info.create_system = 3
            zf.writestr(info, data)


def p19_windows_name_semantics(tmp, package):
    sub = tmp
    cases = [
        ("payload/custom_nodes/lvw_v0_bridge/zz.py.", "trailing_dot"),
        ("payload/custom_nodes/lvw_v0_bridge/zz.py ", "trailing_space"),
        ("payload/custom_nodes/lvw_v0_bridge/NUL", "reserved_device_name"),
        ("payload/custom_nodes/lvw_v0_bridge/con.py", "reserved_stem_con"),
    ]
    observed_all = []
    ok_all = True
    for index, (member, label) in enumerate(cases):
        crafted = sub / ("crafted-%d.zip" % index)
        _craft_zip_with_member(package, crafted, member)
        code, payload, _so, _se = run(["diagnose", "--package", str(crafted)])
        observed = {
            "case": label,
            "member": member,
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
        }
        observed_all.append(observed)
        if not (code == EXIT_CODES["PATH_REJECTED"]
                and observed["error_code"] == "PATH_REJECTED"):
            ok_all = False
    record(
        "P19-windows-trailing-dot-space-reserved-names-rejected",
        "每个案例都必须 exit=4(PATH_REJECTED)",
        observed_all,
        ok_all,
    )
    return observed_all


# --------------------------------------------------------------------------- #
# P20 外部 --manifest 坏输入
# --------------------------------------------------------------------------- #
def p20_external_manifest_bad_input(tmp, package):
    sub = tmp
    bad_json = sub / "bad-manifest.json"
    bad_json.write_text("{ this is not json ]", encoding="utf-8")
    code_json, payload_json, _so, _se = run(
        ["diagnose", "--package", str(package), "--manifest", str(bad_json)]
    )
    missing = sub / "does-not-exist.json"
    code_missing, payload_missing, _so, _se = run(
        ["diagnose", "--package", str(package), "--manifest", str(missing)]
    )
    observed = {
        "invalid_json": {
            "exit_code": code_json,
            "error_code": (payload_json or {}).get("error_code"),
        },
        "unreadable": {
            "exit_code": code_missing,
            "error_code": (payload_missing or {}).get("error_code"),
        },
    }
    ok = (
        observed["invalid_json"]["exit_code"] == EXIT_CODES["BAD_INPUT"]
        and observed["invalid_json"]["error_code"] == "BAD_INPUT"
        and observed["unreadable"]["exit_code"] == EXIT_CODES["BAD_INPUT"]
        and observed["unreadable"]["error_code"] == "BAD_INPUT"
    )
    record(
        "P20-external-manifest-bad-input-is-stable-bad-input",
        "两种坏输入都必须 exit=2(BAD_INPUT)",
        observed,
        ok,
    )
    return observed


# --------------------------------------------------------------------------- #
# P21 回滚绝不 rmtree 外部收据指向的目录（含位于沙箱内的目录）
# --------------------------------------------------------------------------- #
def p21_no_rmtree_of_any_receipt_named_directory(tmp, package):
    sub = tmp
    sandbox, target, _sentinel = make_sandbox(sub)
    victim_dir = sandbox / "外部 目录"
    (victim_dir / "sub").mkdir(parents=True)
    (victim_dir / "sub" / "keep.txt").write_bytes(b"KEEP\n")
    victim_before = tree_snapshot(victim_dir)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)

    receipt = read_receipt(receipt_path)
    receipt["staging"] = {"path": str(victim_dir), "removed": False}
    receipt["owned"]["directories"] = ["../外部 目录"]
    receipt["owned"]["created_directories"] = ["../外部 目录"]
    write_receipt(receipt_path, receipt)

    before = tree_snapshot(target)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(target)]
    )
    after = tree_snapshot(target)
    extra = {
        "victim_dir_still_exists": victim_dir.exists(),
        "victim_dir_tree_unchanged": victim_before == tree_snapshot(victim_dir),
    }
    ok = (
        code != 0
        and before == after
        and extra["victim_dir_still_exists"]
        and extra["victim_dir_tree_unchanged"]
    )
    record(
        "P21-rollback-never-rmtrees-a-receipt-named-directory",
        "exit!=0 且 目标整树不变 且 被收据点名的目录（哪怕在沙箱内）原样存在",
        {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            "target_tree_unchanged": before == after,
            **extra,
        },
        ok,
    )
    return {"exit_code": code, **extra}


# --------------------------------------------------------------------------- #
# P22 目标根本没有安装过
# --------------------------------------------------------------------------- #
def p22_rollback_on_target_without_install(tmp, package):
    sub = tmp
    sandbox, target, sentinel = make_sandbox(sub)
    receipt_path = sub / "install-receipt.json"
    install_ok(package, sandbox, target, receipt_path)
    # 换一个完全没装过的目标
    other = sandbox / "另一个 目标"
    other.mkdir()
    (other / "用户 文件.txt").write_bytes(b"USER\n")
    before = tree_snapshot(other)
    code, payload, _so, _se = run(
        ["rollback", "--receipt", str(receipt_path), "--target", str(other)]
    )
    after = tree_snapshot(other)
    ok = code != 0 and before == after
    record(
        "P22-rollback-on-target-without-install-rejected",
        "exit!=0 且 目标整树不变",
        {
            "exit_code": code,
            "error_code": (payload or {}).get("error_code"),
            "target_tree_unchanged": before == after,
        },
        ok,
    )
    return {"exit_code": code}


def main():
    global RAW_DIR
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    RAW_DIR = out_dir / "raw" / "probes"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix="lvw-indep-c01-probe-") as td:
        tmp = Path(td)
        package = build_package(tmp, repo)

        def sub(name):
            d = tmp / name
            d.mkdir(parents=True, exist_ok=True)
            return d

        p01_f01_receipt_path_traversal(sub("P01"), package)
        p02_f02_receipt_staging_path(sub("P02"), package)
        p03_m01_cross_sandbox(sub("P03"), package)
        p04_owned_directories_traversal(sub("P04"), package)
        p05_created_directories_traversal(sub("P05"), package)
        p06_preimage_path_traversal(sub("P06"), package)
        p07_session_mismatch(sub("P07"), package)
        p08_ownership_record_missing(sub("P08"), package)
        p09_ownership_record_tampered(sub("P09"), package)
        p10_ownership_record_rewritten_with_recomputed_hash(sub("P10"), package)
        p11_marker_missing(sub("P11"), package)
        p12_marker_content_changed(sub("P12"), package)
        p13_receipt_target_rebound(sub("P13"), package)
        p14_residual_staging_is_never_rmtree(sub("P14"), package)
        p15_late_failure_user_modified_owned_file(sub("P15"), package)
        p16_redacted_receipt_with_explicit_target(sub("P16"), package)
        p17_redacted_receipt_with_wrong_explicit_target(sub("P17"), package)
        p18_redacted_receipt_without_target(sub("P18"), package)
        p19_windows_name_semantics(sub("P19"), package)
        p20_external_manifest_bad_input(sub("P20"), package)
        p21_no_rmtree_of_any_receipt_named_directory(sub("P21"), package)
        p22_rollback_on_target_without_install(sub("P22"), package)
        leftover = sorted(p.name for p in tmp.iterdir())

    passed = sum(1 for r in RESULTS if r["matches_expectation"])
    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_NEGATIVE_PROBES",
        "candidate_commit": CANDIDATE,
        "probe_author": "independent reviewer (not the implementer)",
        "oracle": "本轮独审新写；不复用实现者的 negative_probes.py 判据",
        "probe_count": len(RESULTS),
        "probe_passed": passed,
        "probe_failed": len(RESULTS) - passed,
        "probes": RESULTS,
        "temp_root_removed_after_run": True,
        "temp_root_leftover_entries": leftover,
        "product_runtime_calls": 0,
        "network_calls": 0,
        "model_gpu_calls": 0,
        "media_reads": 0,
    }
    (out_dir / "negative-probes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
