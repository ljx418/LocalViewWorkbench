#!/usr/bin/env python3
"""independent-correction-01 独审：本轮 runner 的失败路径清理自检。

correction-01 合同："新增本轮runner必须try/finally/TemporaryDirectory覆盖所有失败。"

本自检把独审自己的探针驱动（`ownership_write_failure.py`）当作被测 runner：
  1) 正常路径运行 -> 驱动必须 exit 0，且自有临时根已被删除
  2) 失败路径运行（注入强制异常）-> 驱动必须 exit != 0，
     且**自有临时根仍必须已被删除**（finally/上下文管理器覆盖失败路径）

被测 runner 与被测工具都在自有临时目录内运行，不触碰真实宿主或用户路径。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[5]
DRIVER = PACK_ROOT / "reports" / "v0-s3" / "preparation-04" / "independent-correction-01" \
    / "probe" / "ownership_write_failure.py"

RESULTS = []


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


def run_driver(out_dir: Path, fail_after_setup: bool):
    with tempfile.TemporaryDirectory(prefix="lvw-indep-c01-selftest-") as td:
        td_path = Path(td)
        tmproot_file = td_path / "tmproot.txt"
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        env["LVW_INDEP_TMPROOT_FILE"] = str(tmproot_file)
        if fail_after_setup:
            env["LVW_INDEP_FAIL_AFTER_SETUP"] = "1"
        proc = subprocess.run(
            [sys.executable, "-B", str(DRIVER), str(out_dir)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            cwd=str(PACK_ROOT),
        )
        recorded = tmproot_file.read_text(encoding="utf-8").strip() if tmproot_file.exists() else None
        root_still_exists = bool(recorded) and Path(recorded).exists()
        return {
            "exit_code": proc.returncode,
            "stderr_tail": proc.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
            if proc.stderr else [],
            "recorded_temp_root": recorded,
            "temp_root_still_exists_after_run": root_still_exists,
        }


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

    ok_path = run_driver(out_dir, fail_after_setup=False)
    record(
        "R01-runner-success-path-cleans-its-temp-root",
        "exit=0 且 自有临时根已被删除",
        ok_path,
        ok_path["exit_code"] == 0 and not ok_path["temp_root_still_exists_after_run"],
    )

    fail_path = run_driver(out_dir, fail_after_setup=True)
    record(
        "R02-runner-failure-path-cleans-its-temp-root",
        "exit!=0 且 自有临时根**仍然**已被删除（finally/上下文管理器覆盖失败路径）",
        fail_path,
        fail_path["exit_code"] != 0 and not fail_path["temp_root_still_exists_after_run"],
    )

    passed = sum(1 for r in RESULTS if r["matches_expectation"])
    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_RUNNER_CLEANUP_SELFTEST",
        "driver_under_test": "probe/ownership_write_failure.py",
        "probe_count": len(RESULTS),
        "probe_passed": passed,
        "probe_failed": len(RESULTS) - passed,
        "probes": RESULTS,
        "product_runtime_calls": 0,
    }
    (out_dir / "runner-cleanup-selftest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
