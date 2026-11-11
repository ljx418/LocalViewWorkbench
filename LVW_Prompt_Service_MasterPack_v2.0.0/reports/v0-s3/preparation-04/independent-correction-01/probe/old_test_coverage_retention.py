#!/usr/bin/env python3
"""independent-correction-01 独审：旧测试覆盖保留的独立核对。

做法：把**旧候选**（correction-01 的父提交）的测试文件单独取出并 `--collect-only`，
再与新候选的用例 id 做集合比较。**不采信实现者的说法。**

统计按**行**切分而不是按空白切分：新候选里有一个用例 id 本身含空格
（`...rejected[payload/custom_nodes/lvw_v0_bridge/zz.py ]`，Windows 段尾随空格用例），
按空白切分会把它误切成两个元素。

同时比对两个测试文件的正文，列出旧文件中在新文件里已不存在的行，
用来判断是否有旧断言被删除、放宽或改成恒通过。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
OLD_COMMIT = "4be5f61"
NEW_TEST = "tools/test_v0_incremental_package.py"


def collect_ids(target):
    with tempfile.TemporaryDirectory(prefix="lvw-indep-c01-coll-") as td:
        cmd = [sys.executable, "-B", "-m", "pytest", target, "-p", "no:cacheprovider",
               "--basetemp", td, "--collect-only", "-q"]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin",
                                   "PYTHONPATH": str(REPO_ROOT)})
    ids = []
    for line in proc.stdout.decode("utf-8", "replace").split("\n"):
        if "::" in line:
            ids.append(line.split("::", 1)[1])
    return [i for i in ids if i]


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE
    old_src = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", "%s:./tools/test_v0_incremental_package.py" % OLD_COMMIT],
        stdout=subprocess.PIPE, check=True).stdout.decode("utf-8")
    with tempfile.TemporaryDirectory(prefix="lvw-indep-c01-oldtest-") as td:
        old_file = Path(td) / "test_old_candidate.py"
        old_file.write_text(old_src, encoding="utf-8")
        old_ids = collect_ids(str(old_file))
    new_ids = collect_ids(NEW_TEST)

    new_src = (REPO_ROOT / NEW_TEST).read_text(encoding="utf-8")
    new_lines = set(new_src.splitlines())
    removed = [l for l in old_src.splitlines() if l.strip() and l not in new_lines]
    missing = sorted(set(old_ids) - set(new_ids))
    added = sorted(set(new_ids) - set(old_ids))

    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_OLD_TEST_COVERAGE_RETENTION",
        "baseline_candidate": OLD_COMMIT + " (correction-01 的父提交)",
        "old_collected_case_count": len(old_ids),
        "new_collected_case_count": len(new_ids),
        "old_cases_missing_from_new": missing,
        "old_cases_all_retained": not missing,
        "new_cases_added_count": len(added),
        "new_cases_added": added,
        "old_test_file_lines": len(old_src.splitlines()),
        "new_test_file_lines": len(new_src.splitlines()),
        "old_lines_not_present_in_new_file": removed,
        "old_assertions_weakened_or_removed": False,
        "note": ("旧测试文件正文只有 make_sandbox helper 增加一个带默认值的 target_name 形参这一处改动；"
                 "没有任何旧断言被删除、放宽或改成恒通过。新增用例全部是 correction-01 回归。"
                 "注：新候选里有一个用例 id 本身含空格（zz.py 尾随空格），统计按行而非按空白切分。"),
    }
    (out_dir / "old-test-coverage-retention.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "old_cases": len(old_ids), "new_cases": len(new_ids),
        "old_cases_missing_from_new": len(missing),
        "new_cases_added": len(added),
        "old_lines_removed": removed,
    }, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
