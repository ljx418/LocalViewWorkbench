#!/usr/bin/env python3
"""independent-correction-01 独审：所有权记录写失败的确定性故障注入。

correction-01 合同第 4 条要求：
  "所有权记录的创建/提交/错误回退须与安装同一事务边界；不可留下已安装但无法安全回滚的
   无记录终态并报OK。"

该失败分支无法用黑盒 CLI 稳定触发（预检查会先拦下同名记录），因此本探针用**进程内故障注入**
复现：把候选 commit 的工具字节导入本进程，只 monkeypatch 工具模块里的
`os.replace` / `_write_ownership_record`，其余逻辑与候选字节逐字一致。

**候选文件本身不被修改**：工具是从 git blob `ef8c065…` 抽出到自有临时目录后导入的，
仓库里的 `tools/v0_incremental_package.py` 一个字节都没有被本审查改动。

变体：
  A  `os.replace` 失败            -> 所有权记录的原子发布失败（临时文件必须被清掉）
  B  `_write_ownership_record` 抛错 -> 所有权记录整体写失败
  C  所有权记录写成功但内容被改写   -> 回滚必须拒绝（记录不可用），且零删除

全部在自有 TemporaryDirectory 内合成。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[5]
REPO_ROOT = PACK_ROOT
CANDIDATE = "ef8c065346a8f7d78b28b238207e7550444d897e"
MARKER_NAME = ".lvw_v0_incremental_sandbox.json"
MARKER_MAGIC = "lvw.v0-incremental-sandbox/1"
OWNERSHIP_FILE_NAME = ".lvw_v0_incremental_ownership.json"

RESULTS = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_snapshot(root: Path):
    entries = []
    if not root.exists():
        return entries
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(dirnames):
            entries.append((Path(dirpath, name).relative_to(root).as_posix(), "dir", None))
        for name in sorted(filenames):
            full = Path(dirpath, name)
            rel = full.relative_to(root).as_posix()
            if full.is_symlink():
                entries.append((rel, "symlink", os.readlink(str(full))))
            else:
                entries.append((rel, "file", sha256_bytes(full.read_bytes())))
    entries.sort()
    return entries


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


def load_candidate_module(tmp: Path):
    """从候选 commit 的 blob 抽出工具字节并导入；不触碰仓库工作树。"""
    blob = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "cat-file", "blob",
         "%s:./tools/v0_incremental_package.py" % CANDIDATE],
        stdout=subprocess.PIPE, check=True,
    ).stdout
    tool_path = tmp / "candidate_tool.py"
    tool_path.write_bytes(blob)
    spec = importlib.util.spec_from_file_location("lvw_candidate_tool", str(tool_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sha256_bytes(blob)


def make_sandbox(root: Path, name="隔离 沙箱根", target_name="隔离 目标 目录"):
    sandbox = root / name
    target = sandbox / target_name
    sandbox.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    (sandbox / MARKER_NAME).write_text(
        json.dumps({"magic": MARKER_MAGIC, "tool": "v0_incremental_package.py"}),
        encoding="utf-8",
    )
    sentinel = target / "哨兵 文件.txt"
    sentinel.write_bytes(b"SENTINEL-ORIGINAL-BYTES\n")
    return sandbox, target, sentinel


def build_package(root: Path, repo: str):
    out = root / "pkg.zip"
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "v0_incremental_package.py"),
         "build", "--repo", str(repo), "--commit", CANDIDATE, "--out", str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    return out


def run_install(module, package, sandbox, target, receipt_path=None):
    args = argparse.Namespace(
        package=str(package),
        sandbox_parent=str(sandbox),
        target=str(target),
        manifest=None,
        session_id=None,
        receipt_out=str(receipt_path) if receipt_path else None,
        redact_root=[],
    )
    try:
        module.command_install(args)
        return None, None
    except module.PackageError as exc:
        return exc.code, exc.to_dict()
    except BaseException as exc:  # noqa: BLE001
        return "UNEXPECTED", {"error_code": "UNEXPECTED", "message": str(exc)}


def variant_a_replace_failure(module, package, tmp):
    """A: 所有权记录的原子发布（os.replace）失败。"""
    sandbox, target, sentinel = make_sandbox(tmp / "A")
    before = tree_snapshot(target)
    original_replace = module.os.replace

    def failing_replace(src, dst):
        if str(dst).endswith(OWNERSHIP_FILE_NAME):
            raise OSError("simulated atomic publish failure")
        return original_replace(src, dst)

    module.os.replace = failing_replace
    try:
        code, detail = run_install(module, package, sandbox, target)
    finally:
        module.os.replace = original_replace
    after = tree_snapshot(target)
    leftovers = [e for e in after if OWNERSHIP_FILE_NAME in e[0]]
    cleanup = (detail or {}).get("detail", {}).get("cleanup") or {}
    staging_residue = sorted(
        p.name for p in sandbox.iterdir() if p.name.startswith(module.STAGING_DIR_PREFIX)
    )
    observed = {
        "exit_code": module.EXIT_CODES.get(code, -1),
        "error_code": code,
        "ownership_record_present": (target / OWNERSHIP_FILE_NAME).exists(),
        "ownership_temp_leftovers": leftovers,
        "owned_payload_remaining": [
            e[0] for e in after if e[0].startswith(("custom_nodes/", "workflows/"))
        ],
        "sentinel_intact": sentinel.exists()
        and sha256_bytes(sentinel.read_bytes()) == sha256_bytes(b"SENTINEL-ORIGINAL-BYTES\n"),
        "cleanup_report_staging_removed_field": cleanup.get("staging_removed"),
        "actual_staging_residue_in_sandbox": staging_residue,
        "original_failure_preserved": bool(
            ((detail or {}).get("detail") or {}).get("original_failure")
        ),
        "target_tree_back_to_preimage": before == after,
    }
    ok = (
        code == "INSTALL_FAILED"
        and not observed["ownership_record_present"]
        and not observed["ownership_temp_leftovers"]
        and not observed["owned_payload_remaining"]
        and observed["sentinel_intact"]
        and not staging_residue
        and observed["original_failure_preserved"]
    )
    record(
        "F01-ownership-record-atomic-publish-failure",
        "exit!=0(INSTALL_FAILED) 且 无所有权记录(含临时文件) 且 owned 全部回退 且 哨兵完好 且 staging 已清",
        observed,
        ok,
    )


def variant_b_write_function_failure(module, package, tmp):
    """B: 整个所有权记录写入函数抛错。"""
    sandbox, target, sentinel = make_sandbox(tmp / "B")
    before = tree_snapshot(target)
    original = module._write_ownership_record

    def failing_write(target_path, rec):
        raise OSError("simulated ownership record write failure")

    module._write_ownership_record = failing_write
    try:
        code, detail = run_install(module, package, sandbox, target)
    finally:
        module._write_ownership_record = original
    after = tree_snapshot(target)
    cleanup = (detail or {}).get("detail", {}).get("cleanup") or {}
    staging_residue = sorted(
        p.name for p in sandbox.iterdir() if p.name.startswith(module.STAGING_DIR_PREFIX)
    )
    observed = {
        "exit_code": module.EXIT_CODES.get(code, -1),
        "error_code": code,
        "ownership_record_present": (target / OWNERSHIP_FILE_NAME).exists(),
        "owned_payload_remaining": [
            e[0] for e in after if e[0].startswith(("custom_nodes/", "workflows/"))
        ],
        "sentinel_intact": sentinel.exists()
        and sha256_bytes(sentinel.read_bytes()) == sha256_bytes(b"SENTINEL-ORIGINAL-BYTES\n"),
        "cleanup_report_staging_removed_field": cleanup.get("staging_removed"),
        "actual_staging_residue_in_sandbox": staging_residue,
        "original_failure_preserved": bool(
            ((detail or {}).get("detail") or {}).get("original_failure")
        ),
        "target_tree_back_to_preimage": before == after,
    }
    ok = (
        code == "INSTALL_FAILED"
        and not observed["ownership_record_present"]
        and not observed["owned_payload_remaining"]
        and observed["sentinel_intact"]
        and not staging_residue
    )
    record(
        "F02-ownership-record-write-function-failure",
        "exit!=0(INSTALL_FAILED) 且 无所有权记录 且 owned 全部回退 且 哨兵完好 且 staging 已清",
        observed,
        ok,
    )


def variant_c_unusable_record(module, package, tmp):
    """C: 所有权记录写成功但内容被改写 -> 回滚必须拒绝且零删除。"""
    sandbox, target, sentinel = make_sandbox(tmp / "C")
    receipt = tmp / "C" / "install-receipt.json"
    code, detail = run_install(module, package, sandbox, target, receipt)
    assert code is None, (code, detail)
    record_path = target / OWNERSHIP_FILE_NAME
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["owned"]["files"] = []
    record_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    before = tree_snapshot(target)
    rollback_args = argparse.Namespace(
        receipt=str(receipt), target=str(target), receipt_out=None, redact_root=[]
    )
    try:
        module.command_rollback(rollback_args)
        rcode, rdetail = None, None
    except module.PackageError as exc:
        rcode, rdetail = exc.code, exc.to_dict()
    after = tree_snapshot(target)
    observed = {
        "rollback_error_code": rcode,
        "rollback_exit_code": module.EXIT_CODES.get(rcode, -1),
        "target_tree_unchanged": before == after,
        "owned_files_still_present": len(
            [e for e in after if e[0].startswith("custom_nodes/") and e[1] == "file"]
        ),
        "sentinel_intact": sentinel.exists(),
    }
    ok = (
        rcode == "ROLLBACK_CONFLICT"
        and observed["target_tree_unchanged"]
        and observed["owned_files_still_present"] > 0
    )
    record(
        "F03-unusable-ownership-record-blocks-rollback",
        "exit=8(ROLLBACK_CONFLICT) 且 目标整树不变（owned 文件一个都不能少）",
        observed,
        ok,
    )


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE, check=True,
    ).stdout.decode().strip()
    with tempfile.TemporaryDirectory(prefix="lvw-indep-c01-ownfail-") as td:
        tmp = Path(td)
        # 自检钩子：把自有临时根路径写出去，供 runner 清理自检在失败路径上复检。
        marker_file = os.environ.get("LVW_INDEP_TMPROOT_FILE")
        if marker_file:
            Path(marker_file).write_text(str(tmp), encoding="utf-8")
        module, blob_sha = load_candidate_module(tmp)
        package = build_package(tmp, repo)
        # 自检钩子：在临时根建立后强制失败，用于证明失败路径也会清理自有临时根。
        if os.environ.get("LVW_INDEP_FAIL_AFTER_SETUP"):
            raise RuntimeError("simulated runner failure after setup")
        variant_a_replace_failure(module, package, tmp)
        variant_b_write_function_failure(module, package, tmp)
        variant_c_unusable_record(module, package, tmp)
        leftover = sorted(p.name for p in tmp.iterdir())

    passed = sum(1 for r in RESULTS if r["matches_expectation"])
    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_OWNERSHIP_WRITE_FAILURE",
        "candidate_commit": CANDIDATE,
        "candidate_tool_blob_sha256": blob_sha,
        "injection": "进程内 monkeypatch；仓库中的候选文件字节未被修改",
        "probe_count": len(RESULTS),
        "probe_passed": passed,
        "probe_failed": len(RESULTS) - passed,
        "probes": RESULTS,
        "temp_root_removed_after_run": True,
        "temp_root_leftover_entries": leftover,
        "product_runtime_calls": 0,
    }
    (out_dir / "ownership-write-failure.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
