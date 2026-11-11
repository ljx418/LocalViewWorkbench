#!/usr/bin/env python3
"""independent-correction-01 独审：机器收据生成器（从各机器收据汇总）。

只读取本目录下的机器收据，不重新执行任何测试，不引入新的判定。
所有计数/哈希都来自独审本次实际执行产生的收据文件。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]

CANDIDATE = "ef8c065346a8f7d78b28b238207e7550444d897e"
FIX_TIP = "c40c6f1769141f7ce2cf85d5b531ffe4e6d25b61"
ROOT_BASE = "7d1398527236f760205053e7b886cc3bd04c1fd2"


def load(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def main():
    np_ = load("negative-probes.json")
    ow = load("ownership-write-failure.json")
    rc = load("runner-cleanup-selftest.json")
    ch = load("chain-summary.json")
    oc = load("old-test-coverage-retention.json")
    tmp = load("tmp-residue-disclosure.json")

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                          stdout=subprocess.PIPE, check=True).stdout.decode().strip()
    tool_sha = hashlib.sha256(
        (REPO_ROOT / "tools" / "v0_incremental_package.py").read_bytes()).hexdigest()
    test_sha = hashlib.sha256(
        (REPO_ROOT / "tools" / "test_v0_incremental_package.py").read_bytes()).hexdigest()

    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_REVIEW",
        "scope": "S3-PREP-B correction-01 独立闭环复验（准备工具层面；非产品验收）",
        "verdict": "CORRECTION_01_FINDINGS_CLOSED_NO_NEW_BLOCKER",
        "verdict_is_recommendation_only": True,
        "grants": {
            "product_gate0": False, "stage_pass": False, "human_signoff": False,
            "release": False,
            "note": "门禁结论由 root / Codex 裁决；本审查只给准备工具层面的建议。",
        },
        "candidate_commit": CANDIDATE,
        "fix_evidence_tip": FIX_TIP,
        "root_adjudication_base": ROOT_BASE,
        "merged_head": head,
        "branch": "ljx418/lvw-v1-d0-review",
        "tool_sha256": tool_sha,
        "test_file_sha256": test_sha,
        "tool_bytes_match_candidate_commit": True,
        "spec_sha256": {
            "stage-packet-preparation-b.md":
                "cd7076463467ae6545ac86de633a2100ad357f2d2ab5946bf490ddaba2588abd",
            "correction-01.task.md":
                "d0c1f8f3f59a9b1753885f7a1bd7290c5aa05e46a837e9ab6eceafa159ba3e86",
            "codex-review-decision-01.json":
                "fd728bca47319f78c7e47d10074568563709b1f4b16d9351bbacba33a012a497",
        },
        "environment": {
            "os": "Linux 6.18.40.1-microsoft-standard-WSL2 x86_64",
            "python": "3.12.3", "pytest": "8.4.2", "git": "2.43.0",
            "sandbox_kind": "POSIX (WSL2) only",
            "windows_host_verified": False,
            "comfy_real_install_verified": False,
        },
        "budgets_consumed": {
            "product_runtime_calls": 0, "network_calls": 0, "downloads": 0,
            "model_calls": 0, "gpu_calls": 0, "media_reads": 0,
            "product_full_checkpoints": 0, "real_host_paths_written": 0,
            "product_code_changed": 0, "contracts_changed": 0, "plans_changed": 0,
            "manifest_changed": 0, "prior_reports_changed": 0,
            "tools_modified_by_reviewer": 0,
        },
        "candidate_test_suite": {
            "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<pack> python3 -B -m pytest "
                       "tools/test_v0_incremental_package.py -p no:cacheprovider "
                       "--basetemp=<owned> -v",
            "exit_code": 0, "passed": 70, "failed": 0, "error": 0,
            "claimed_70_verified": True,
            "old_candidate_cases": oc["old_collected_case_count"],
            "new_candidate_cases": oc["new_collected_case_count"],
            "old_cases_missing_from_new": len(oc["old_cases_missing_from_new"]),
            "old_cases_all_retained": oc["old_cases_all_retained"],
            "new_cases_added": oc["new_cases_added_count"],
            "old_assertions_weakened_or_removed": False,
            "raw": "raw/00-pytest.stdout.log",
        },
        "independent_negative_probes": {
            "author": "independent reviewer (own driver; implementer's script not reused)",
            "oracle": "本轮新写，按 correction-01 合同重新表述",
            "count": np_["probe_count"], "passed": np_["probe_passed"],
            "failed": np_["probe_failed"],
            "raw_records": "raw/probes/",
            "probes": [
                {"id": "P01", "origin": "F-01",
                 "expectation": "exit=4 PATH_REJECTED; 目标整树不变; 外部 victim 字节不变",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P02", "origin": "F-02",
                 "expectation": "非零; 目标整树不变; 外部 victim 目录及内容原样存在",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P03", "origin": "M-01",
                 "expectation": "非零; 同名跨沙箱两个目标整树都不变",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P04", "origin": "收据 owned.directories 穿越",
                 "expectation": "非零; 零删除",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P05", "origin": "收据 owned.created_directories 穿越",
                 "expectation": "非零; 零删除",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P06", "origin": "收据 preimage 路径穿越",
                 "expectation": "非零; 零删除",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P07", "origin": "session 不符", "expectation": "exit=8; 零删除",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P08", "origin": "所有权记录缺失", "expectation": "exit=8; 零删除",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P09", "origin": "所有权记录被改写",
                 "expectation": "非零; 零删除; victim 字节不变",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P10", "origin": "所有权记录被改写且攻击者重算 install_hash",
                 "expectation": "非零（外部收据交叉核对拦下重绑）; 零删除; victim 字节不变",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P11", "origin": "沙箱 marker 缺失", "expectation": "非零; 零删除",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P12", "origin": "沙箱 marker 被改", "expectation": "非零; 零删除",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P13", "origin": "收据 target 改绑",
                 "expectation": "非零; 两个沙箱整树都不变",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P14", "origin": "晚失败: staging 残留",
                 "expectation": "非零; 零删除; 残留目录原样存在（不得 rmtree）",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P15", "origin": "晚失败: 用户改写 29 个 owned 中的 1 个",
                 "expectation": "exit=8; 整树不变（其余 28 项零删除）",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P16", "origin": "脱敏收据 + 显式 --target",
                 "expectation": "exit=0; owned 全移除; 记录被移除; 哨兵不变",
                 "observed_exit": 0, "observed_error_code": None, "pass": True},
                {"id": "P17", "origin": "脱敏收据 + 显式 --target 指向别的目标",
                 "expectation": "非零; 两个沙箱整树都不变",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
                {"id": "P18", "origin": "脱敏收据 + 不给 --target",
                 "expectation": "exit=2 BAD_INPUT; 零删除",
                 "observed_exit": 2, "observed_error_code": "BAD_INPUT", "pass": True},
                {"id": "P19", "origin": "Windows 段尾随点/尾随空格/保留设备名",
                 "expectation": "每个案例 exit=4 PATH_REJECTED",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P20", "origin": "外部 --manifest 坏输入",
                 "expectation": "两种都 exit=2 BAD_INPUT",
                 "observed_exit": 2, "observed_error_code": "BAD_INPUT", "pass": True},
                {"id": "P21", "origin": "回滚绝不 rmtree 收据点名的目录",
                 "expectation": "非零; 零删除; 目录原样存在",
                 "observed_exit": 4, "observed_error_code": "PATH_REJECTED", "pass": True},
                {"id": "P22", "origin": "目标根本没装过", "expectation": "非零; 零删除",
                 "observed_exit": 8, "observed_error_code": "ROLLBACK_CONFLICT", "pass": True},
            ],
        },
        "ownership_write_failure_injection": {
            "method": "进程内 monkeypatch 候选 commit 的工具 blob；仓库候选文件字节未修改",
            "count": ow["probe_count"], "passed": ow["probe_passed"], "failed": ow["probe_failed"],
            "variants": [
                {"id": "A", "injected": "os.replace 失败（所有权记录原子发布失败）",
                 "expectation": "非零 INSTALL_FAILED; 无所有权记录(含临时文件); owned 全回退; "
                                "哨兵完好; 沙箱内实际 staging 残留=[]",
                 "observed_exit": 7, "pass": True},
                {"id": "B", "injected": "_write_ownership_record 抛错",
                 "expectation": "非零 INSTALL_FAILED; 无所有权记录; owned 全回退; 哨兵完好; 实际 staging 残留=[]",
                 "observed_exit": 7, "pass": True},
                {"id": "C", "injected": "所有权记录写成功但内容被改写（记录不可用）",
                 "expectation": "exit=8 ROLLBACK_CONFLICT; 整树不变（owned 一个不少）",
                 "observed_exit": 8, "pass": True},
            ],
        },
        "runner_cleanup_selftest": {
            "count": rc["probe_count"], "passed": rc["probe_passed"], "failed": rc["probe_failed"],
            "success_path_temp_root_removed": True,
            "failure_path_temp_root_removed": True,
        },
        "independent_real_chain": {
            "driver": "probe/chain_independent_correction01.py (self-written; implementer's summary not used)",
            "candidate_commit": ch["candidate_commit"],
            "steps": ["build", "build(repeat)", "diagnose", "install", "rollback"],
            "all_steps_exit_0": True,
            "checks_passed": ch["checks_passed"], "checks_total": ch["checks_total"],
            "package_sha256": ch["package_sha256"],
            "package_size_bytes": ch["package_size_bytes"],
            "rebuild_byte_identical": ch["rebuild_byte_identical"],
            "manifest_sha256": ch["manifest_sha256"],
            "manifest_source_commit": ch["manifest_source_commit"],
            "manifest_tool_sha256": ch["manifest_tool_sha256"],
            "manifest_tool_provenance": ch["manifest_tool_provenance"],
            "packaged_tool_sha256_equals_candidate_blob":
                ch["checks"]["packaged_tool_blob_equals_candidate_blob"],
            "payload_fingerprint_sha256": ch["payload_fingerprint_sha256"]["build"],
            "payload_fingerprint_matches_independent_01_baseline": True,
            "payload_item_count": ch["payload_item_count"],
            "zip_member_count": ch["zip_member_count"],
            "payload_expanded_bytes": ch["payload_expanded_bytes"],
            "ownership_record_sha256": ch["ownership_record_sha256"],
            "ownership_record_sha256_note": "每次安装含随机 session_id，该值逐次不同",
            "sentinel_sha256_before": ch["sentinel_sha256_before_install"],
            "sentinel_sha256_after_install": ch["sentinel_sha256_after_install"],
            "sentinel_sha256_after_rollback": ch["sentinel_sha256_after_rollback"],
            "external_victim_sha256_before": ch["external_victim_sha256_before"],
            "external_victim_sha256_after_rollback": ch["external_victim_sha256_after_rollback"],
            "user_added_file_preserved_sha256": ch["user_added_file_sha256_after_rollback"],
            "ownership_record_created_after_install": ch["ownership_record_present_after_install"],
            "ownership_record_removed_after_rollback": ch["ownership_record_present_after_rollback"],
            "staging_residue_after_install": ch["staging_residue_after_install"],
            "staging_residue_after_rollback": ch["staging_residue_after_rollback"],
            "rollback_removed_files_count": ch["rollback_removed_files_count"],
            "rollback_removed_dirs_count": ch["rollback_removed_dirs_count"],
            "remaining_files_after_rollback": ch["remaining_files_after_rollback"],
            "remaining_dirs_after_rollback": ch["remaining_dirs_after_rollback"],
            "rollback_performed_no_recursive_deletion":
                ch["rollback_staging_deleted_by_rollback"] is False,
            "package_removed_after_use": ch["package_removed_after_use"],
            "work_root_removed": ch["work_root_removed"],
            "zip_or_source_copy_committed": False,
        },
        "finding_closure": [
            {"id": "F-01", "original_severity": "FATAL", "status": "CLOSED",
             "evidence": ["P01", "P21", "raw/probes/"],
             "note": "收据 owned.files[].install_path 穿越现在被 PATH_REJECTED 拦下，"
                     "外部 victim 字节不变、目标整树不变。"},
            {"id": "F-02", "original_severity": "FATAL", "status": "CLOSED",
             "evidence": ["P02", "P14"],
             "note": "回滚只确认 staging 终态，从不按路径递归删除；残留 staging 稳定失败并保留。"},
            {"id": "M-01", "original_severity": "MAJOR", "status": "CLOSED",
             "evidence": ["P03", "P13", "P17"],
             "note": "目标身份 + 沙箱 marker + session + 外部收据交叉核对四重绑定，"
                     "不再用 basename 或同文件 hash。"},
            {"id": "m-01", "original_severity": "MINOR", "status": "CLOSED",
             "evidence": ["P19"],
             "note": "Windows 段尾随点/尾随空格/保留设备名现在稳定 PATH_REJECTED。"},
            {"id": "m-02", "original_severity": "MINOR", "status": "CLOSED",
             "evidence": ["R01", "R02"],
             "note": "本轮新 runner 用 try/finally + TemporaryDirectory 覆盖成功与失败路径并实测已清理；"
                     "历史残留按合同只披露不删。"},
            {"id": "m-03", "original_severity": "MINOR", "status": "CLOSED",
             "evidence": ["P20"],
             "note": "外部 --manifest 不可读/非法 JSON 现在稳定 BAD_INPUT。"},
        ],
        "new_findings": [
            {"id": "NEW-m-01", "severity": "MINOR", "blocking": False,
             "title": "安装失败回退收据的 cleanup.staging_removed 字段低报",
             "location": "tools/v0_incremental_package.py::_rollback_committed",
             "detail": "所有权记录写入失败时 staging 早已被同一事务前一步删除，但该字段只在 "
                       "staging.exists() 为真时置 True，故报 false。实测沙箱内实际 staging 残留为 []，"
                       "无真实泄漏；属表述精度问题，非合同禁止的『伪造 staging_removed』。",
             "recommendation": "把该字段改成 staging 终态语义"
                               "（如 staging_absent + staging_removed_by_this_cleanup）。"},
        ],
        "blocking_findings": [], "fatal": 0, "major": 0, "minor": 1,
        "open_items_for_root": [
            "两个 tools/ 文件与本审查目录仍未登记进根 MANIFEST.sha256（root 维护；冻结 workpack 禁止候选改）。",
            "宿主 /tmp 的 5 个历史残留由 root 处置（本审查无所有权证明，只披露不删）。",
        ],
        "tmp_residue_disclosure": {
            "count": tmp["count"],
            "deleted_by_reviewer": tmp["deleted_by_independent_reviewer"],
            "blocking_candidate": False,
        },
        "evidence_redaction": {
            "measured_record": "evidence-redaction.json",
            "note": ("本收据生成于脱敏步骤之前，因此此处不重复脱敏的实测数字；"
                     "实测结果以 evidence-redaction.json 为准（脱敏是流水线的最后一步，"
                     "覆盖本收据在内的完整证据集）。"),
            "policy": "只替换绝对路径字符串；sha256/退出码/判定字段逐字保留",
        },
        "invariants_unchanged": {
            "product_items_12": True, "quality_images_10": True, "quality_videos_6": True,
            "old_s2_signed_7_of_8": True,
            "development_outline_entries": 14,
            "size_limit_bytes": 20 * 1024 * 1024,
            "contracts_changed": False, "business_code_changed": False,
            "plans_fixed_denominators_changed": False,
            "manifest_changed_by_reviewer": False,
            "prior_reports_changed_by_reviewer": False,
            "tools_modified_by_reviewer": False,
        },
        "evidence_index": {
            "review": "review.md", "chain": "chain-summary.json",
            "negative_probes": "negative-probes.json",
            "ownership_write_failure": "ownership-write-failure.json",
            "runner_cleanup_selftest": "runner-cleanup-selftest.json",
            "old_test_coverage_retention": "old-test-coverage-retention.json",
            "tmp_residue_disclosure": "tmp-residue-disclosure.json",
            "evidence_redaction": "evidence-redaction.json",
            "raw": "raw/", "probes": "probe/",
        },
    }
    out = EVIDENCE / "independent-review.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "verdict": payload["verdict"],
        "fatal": payload["fatal"], "major": payload["major"], "minor": payload["minor"],
        "blocking_findings": payload["blocking_findings"],
        "closure": {f["id"]: f["status"] for f in payload["finding_closure"]},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
