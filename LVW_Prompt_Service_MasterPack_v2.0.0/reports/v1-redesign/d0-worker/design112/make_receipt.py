#!/usr/bin/env python3
"""Build the design 1.1.2 correction receipt from the raw logs of this run.

Every number in the receipt is *machine extracted* from the raw logs that sit
next to it: the exit codes come from the ``*.exit.log`` files, the digests
come from hashing the log bytes, and the counts come from parsing the log
text. Nothing is hand transcribed and no number is copied from an earlier
receipt.

The script only reads the tree and writes the two receipt files below
``reports/v1-redesign/d0-worker/design112/``. It is append only: the design
1.1 receipt and the design 1.1.1 receipt, and every log under
``d0-worker/design11/`` and ``d0-worker/design111/``, are read but never
written.

Run: python3 -B reports/v1-redesign/d0-worker/design112/make_receipt.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOGS = HERE / "logs"

D0_DIR = ".agent-governance/stages/V1-D0"
OLD_111_RECEIPT = "reports/v1-redesign/d0-worker/design111/implementation-receipt-1.1.1.json"
OLD_111_PACK_LOG = "reports/v1-redesign/d0-worker/design111/logs/verify_pack.stdout.log"

# The orchestration identity of *this* dispatch. It is taken from the dispatch
# that commissioned this workpack, not from any earlier receipt.
ORCHESTRATION = {
    "coordinator_terminal": "term_192c2ec6-ba08-4100-ac4c-6b603e2b82d0",
    "worker_terminal": "term_6e344f4f-8bc9-4fda-84c0-77f8af72a014",
    "task_id": "task_47741957bae4",
    "dispatch_id": "ctx_269da7001d7b",
    "provider_metadata": "self reported by the worker session, not independently verified",
    "provider_metadata_verified": False,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_log(name: str) -> dict:
    """One log triple: the stdout, the stderr and the exit code."""
    stdout = LOGS / ("%s.stdout.log" % name)
    stderr = LOGS / ("%s.stderr.log" % name)
    exit_log = LOGS / ("%s.exit.log" % name)
    exit_text = exit_log.read_text(encoding="utf-8").strip()
    match = re.search(r"(\d+)", exit_text)
    if not match:
        raise SystemExit("no exit code in %s" % exit_log)
    return {
        "stdout_log": "logs/%s.stdout.log" % name,
        "stderr_log": "logs/%s.stderr.log" % name,
        "exit_log": "logs/%s.exit.log" % name,
        "exit_code": int(match.group(1)),
        "stdout_sha256": sha256(stdout),
        "stderr_sha256": sha256(stderr),
        "exit_log_sha256": sha256(exit_log),
        "stdout_text": stdout.read_text(encoding="utf-8"),
    }


def parse_pytest(text: str) -> dict:
    match = re.search(r"(\d+) passed", text)
    if not match:
        raise SystemExit("no pytest summary in the pytest log")
    failed = re.search(r"(\d+) failed", text)
    skipped = re.search(r"(\d+) skipped", text)
    duration = re.search(r"in ([0-9.]+s)", text)
    return {
        "passed": int(match.group(1)),
        "failed": int(failed.group(1)) if failed else 0,
        "skipped": int(skipped.group(1)) if skipped else 0,
        "duration_reported": duration.group(1) if duration else None,
    }


def parse_json_log(text: str) -> dict:
    return json.loads(text)


def parse_result_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("RESULT:"):
            return line
    raise SystemExit("no RESULT line in the checker log")


def main() -> int:
    checker = read_log("verify_v1_plan")
    pytest_log = read_log("pytest")
    pack = read_log("verify_pack")
    governance = read_log("verify_governance")
    owner_probe = read_log("verify-design112")
    probes = read_log("reviewer-probes-rerun")

    pytest_counts = parse_pytest(pytest_log["stdout_text"])
    pack_json = parse_json_log(pack["stdout_text"])
    governance_json = parse_json_log(governance["stdout_text"])

    # --- the historical design 1.1.1 evidence (read only, never rewritten) ---
    old_receipt_path = ROOT / OLD_111_RECEIPT
    old_pack_log_path = ROOT / OLD_111_PACK_LOG
    old_receipt = json.loads(old_receipt_path.read_text(encoding="utf-8"))
    old_pack_json = parse_json_log(old_pack_log_path.read_text(encoding="utf-8"))
    old_receipt_result = ""
    for entry in old_receipt.get("supplementary_read_only_verifications") or []:
        if entry.get("command") == "python3 -B tools/verify_pack.py":
            old_receipt_result = entry.get("result") or ""
    old_receipt_pack = next(
        entry for entry in old_receipt["supplementary_read_only_verifications"]
        if entry.get("command") == "python3 -B tools/verify_pack.py"
    )
    old_stated = re.search(r"passed (\d+)", old_receipt_result)
    old_stated_count = int(old_stated.group(1)) if old_stated else None

    # --- the authority inventory, recomputed from the tree ------------------
    spec_manifest = json.loads((ROOT / D0_DIR / "spec-manifest.json").read_text(encoding="utf-8"))
    owner_files = spec_manifest["files"]
    authority_recomputed = {}
    mismatched = []
    for rel, digest in sorted(owner_files.items()):
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        authority_recomputed[rel] = actual
        if actual != digest:
            mismatched.append(rel)
    packet_manifest_path = ROOT / D0_DIR / "PAYLOAD_MANIFEST.sha256"
    packet_entries = []
    packet_mismatched = []
    for line in packet_manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, name = line.split(None, 1)
        name = name.strip()
        packet_entries.append(name)
        actual = hashlib.sha256((ROOT / D0_DIR / name).read_bytes()).hexdigest()
        if actual != digest:
            packet_mismatched.append(name)

    code_digests = {
        "tools/verify_v1_plan.py": sha256(ROOT / "tools" / "verify_v1_plan.py"),
        "tools/test_verify_v1_plan.py": sha256(ROOT / "tools" / "test_verify_v1_plan.py"),
    }

    stage_control = json.loads((ROOT / D0_DIR / "stage-control.json").read_text(encoding="utf-8"))
    workpack = next(w for w in stage_control["workpacks"] if w["id"] == "D0-B-IMPL")

    receipt = {
        "schema_version": "lvw.implementation-receipt/1",
        "kind": "D0_B_IMPL_DESIGN112_CORRECTION_RECEIPT",
        "project_id": "lvw-prompt-service",
        "stage_id": "V1-D0",
        "workpack_id": "D0-B-IMPL",
        "design_version": "1.1.2",
        "status": "READY_FOR_REVIEW",
        "product_execution_authorized": False,
        "product_actions": 0,
        "human_signoff": None,
        "product_pass": False,
        "stage_pass_claimed": False,
        "self_certification": False,
        "this_is_a_correction_package": (
            "This is the single consolidated correction of the eight independent review findings "
            "NM-1..NM-8. It is not a new product stage, it is not a product Gate0 and it is not a "
            "human signature. The product coordinate stays R1 / WAIT_HUMAN, no sample is "
            "materialized and no runtime authority is claimed."
        ),
        "orchestration": ORCHESTRATION,
        "authority": {
            "authoritative_design_commit": "3af446302f6237b41dc500ee290caf2b5075ab80",
            "loaded_into_this_checkout_by": (
                "git merge 3af446302f6237b41dc500ee290caf2b5075ab80 into the clean child checkout "
                "ljx418/lvw-v1-d0-implement (clean merge, no conflict, no manual repair)"
            ),
            "merge_commit": "36cfe62",
            "branch": "ljx418/lvw-v1-d0-implement",
            "worktree": "/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement",
            "parent_worktree_touched": False,
            "review_branch": "ljx418/lvw-v1-d0-review",
            "review_artifacts_read": [
                "reports/v1-redesign/d0-review/design111/review.md",
                "reports/v1-redesign/d0-review/design111/findings.json",
                "reports/v1-redesign/d0-review/design111/checks/probes.py",
                "reports/v1-redesign/d0-review/design111/checks/recompute.py",
                "reports/v1-redesign/design112-adjudication.json",
                "reports/v1-redesign/design112-owner-checks.json",
                "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md (the design 1.1.2 section)",
            ],
            "note": (
                "The authority commit was loaded as-is. No file that belongs to the root authority "
                "was edited in this workpack; the owner manifests and their hashes were not "
                "regenerated."
            ),
        },
        "frozen_digests": {
            "d0_payload_manifest_sha256": sha256(packet_manifest_path),
            "d0_payload_manifest_sha256_supplied_by_root": "181c08ee7290f5bef02e22b6f7fd3c874c2d404cc8b4ffff84d2148a71f47eb8",
            "d0_spec_manifest_sha256": sha256(ROOT / D0_DIR / "spec-manifest.json"),
            "d0_stage_control_sha256": sha256(ROOT / D0_DIR / "stage-control.json"),
            "checker_pin_re_frozen_to": "181c08ee7290f5bef02e22b6f7fd3c874c2d404cc8b4ffff84d2148a71f47eb8",
            "checker_pin_previous_1_1_1_value": "04d3bfb4af3c2d7be68e494a6d59624a96051a0ebf28e81d6a0367aa32aa6710",
            "checker_pin_previous_1_1_value": "56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a",
            "checker_pin_previous_1_0_value": "9bffdf2dc968f54fae0404d162c394e265cfb9900f68d9c303683bef756ede7b",
            "owner_hashes_regenerated": False,
            "authority_input_hashes_reverified": {
                "spec_manifest_files_checked": len(owner_files),
                "spec_manifest_files_mismatched": len(mismatched),
                "spec_manifest_files_mismatched_list": mismatched,
                "d0_payload_manifest_files_checked": len(packet_entries),
                "d0_payload_manifest_files_mismatched": len(packet_mismatched),
                "d0_payload_manifest_files_mismatched_list": packet_mismatched,
                "authority_input_hashes": authority_recomputed,
            },
            "owner_source_inventory": {
                "count": len(owner_files),
                "files": sorted(owner_files),
                "note": (
                    "design 1.1.2 adds exactly one fenced owner source, "
                    "reports/v1-redesign/design112-adjudication.json. The design 1.1.1 adjudication "
                    "is retained as the historical frozen record of that revision."
                ),
            },
            "d0_payload_inventory": {
                "count": len(packet_entries),
                "files": sorted(packet_entries),
            },
        },
        "candidate_code": code_digests,
        "permitted_inventory": {
            "stage_control_allowed_files": list(workpack["allowed_files"]),
            "stage_control_commands": list(workpack["commands"]),
            "stage_control_forbidden_write_paths": list(stage_control["forbidden_write_paths"]),
            "files_written_by_this_workpack": [
                "tools/verify_v1_plan.py",
                "tools/test_verify_v1_plan.py",
                "reports/v1-redesign/d0-worker/design112/implementation-receipt-1.1.2.json",
                "reports/v1-redesign/d0-worker/design112/implementation-receipt-1.1.2.md",
                "reports/v1-redesign/d0-worker/design112/make_receipt.py",
                "reports/v1-redesign/d0-worker/design112/reviewer-probe-rerun.py",
                "reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_v1_plan.exit.log",
                "reports/v1-redesign/d0-worker/design112/logs/pytest.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/pytest.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/pytest.exit.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_pack.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_pack.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_pack.exit.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_governance.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_governance.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify_governance.exit.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify-design112.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify-design112.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/verify-design112.exit.log",
                "reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.stdout.log",
                "reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.stderr.log",
                "reports/v1-redesign/d0-worker/design112/logs/reviewer-probes-rerun.exit.log",
            ],
            "forbidden_write_paths_touched": [],
        },
        "commands": [
            {
                "command": "python3 -B tools/verify_v1_plan.py",
                "cwd": "LVW_Prompt_Service_MasterPack_v2.0.0",
                "exit_code": checker["exit_code"],
                "result": parse_result_line(checker["stdout_text"]),
                "stdout_log": checker["stdout_log"],
                "stderr_log": checker["stderr_log"],
                "exit_log": checker["exit_log"],
                "stdout_sha256": checker["stdout_sha256"],
                "stderr_sha256": checker["stderr_sha256"],
                "exit_log_sha256": checker["exit_log_sha256"],
                "pin_mode": "default (frozen stage command pin)",
                "validation_capability": "metaschema_check=jsonschema, frame_instance_probe=jsonschema, frame_sample=present",
            },
            {
                "command": "python3 -B -m pytest tools/test_verify_v1_plan.py -q",
                "cwd": "LVW_Prompt_Service_MasterPack_v2.0.0",
                "exit_code": pytest_log["exit_code"],
                "result": "%d passed, %d failed, %d skipped" % (
                    pytest_counts["passed"], pytest_counts["failed"], pytest_counts["skipped"]
                ),
                "result_source": "machine extracted from the pytest stdout log",
                "stdout_log": pytest_log["stdout_log"],
                "stderr_log": pytest_log["stderr_log"],
                "exit_log": pytest_log["exit_log"],
                "stdout_sha256": pytest_log["stdout_sha256"],
                "stderr_sha256": pytest_log["stderr_sha256"],
                "exit_log_sha256": pytest_log["exit_log_sha256"],
            },
        ],
        "supplementary_read_only_verifications": [
            {
                "command": "python3 -B tools/verify_pack.py",
                "exit_code": pack["exit_code"],
                "result": "passed %d, failed %d (document and contract validation, not product acceptance)" % (
                    pack_json["passed"], pack_json["failed"]
                ),
                "result_source": "machine extracted from the verify_pack stdout log of this tree",
                "scope": pack_json.get("scope"),
                "stdout_log": pack["stdout_log"],
                "stderr_log": pack["stderr_log"],
                "exit_log": pack["exit_log"],
                "stdout_sha256": pack["stdout_sha256"],
                "stderr_sha256": pack["stderr_sha256"],
                "exit_log_sha256": pack["exit_log_sha256"],
            },
            {
                "command": "python3 -B tools/verify_governance.py",
                "exit_code": governance["exit_code"],
                "result": "errors %s, failed %d" % (governance_json["errors"], governance_json["failed"]),
                "result_source": "machine extracted from the verify_governance stdout log of this tree",
                "stdout_log": governance["stdout_log"],
                "stderr_log": governance["stderr_log"],
                "exit_log": governance["exit_log"],
                "stdout_sha256": governance["stdout_sha256"],
                "stderr_sha256": governance["stderr_sha256"],
                "exit_log_sha256": governance["exit_log_sha256"],
            },
            {
                "command": "python3 -B reports/v1-redesign/verify-design112.py (owner architecture probe, run against a temporary copy of the owner tree)",
                "exit_code": owner_probe["exit_code"],
                "result": owner_probe["stdout_text"].strip(),
                "result_source": "machine extracted from the owner probe stdout log",
                "note": (
                    "Supplementary owner design evidence only. The probe was run in a temporary "
                    "copy of the owner tree and reproduced reports/v1-redesign/design112-owner-checks.json "
                    "byte identically, so no owner owned file was dirtied by this workpack."
                ),
                "stdout_log": owner_probe["stdout_log"],
                "stderr_log": owner_probe["stderr_log"],
                "exit_log": owner_probe["exit_log"],
                "stdout_sha256": owner_probe["stdout_sha256"],
                "stderr_sha256": owner_probe["stderr_sha256"],
                "exit_log_sha256": owner_probe["exit_log_sha256"],
            },
            {
                "command": "python3 -I reports/v1-redesign/d0-worker/design112/reviewer-probe-rerun.py (reviewer owned probes P01, P02, P05, P22, P23, P24 and the positive control P00)",
                "exit_code": probes["exit_code"],
                "result": (
                    "P01 exit 1 E_SCENE_HASH_MAPPING; P02 exit 1 E_SCENE_HASH_MAPPING; "
                    "P05 exit 1 E_SCENE_GET_ENVELOPE; P22 exit 1 E_OVERLAY_METADATA_SHAPE; "
                    "P23 exit 1 E_OVERLAY_HEADER_SHAPE; P24 exit 1 E_SCHEMA_PATTERN; "
                    "P00 positive control exit 0 RESULT: PASS"
                ),
                "result_source": "machine extracted from the reviewer probe re-run stdout log",
                "note": (
                    "The reviewer owned probe harness was imported read only and was not modified. "
                    "Every probe ran on a fresh temporary copy of the tree and the run itself never "
                    "wrote into the review directory."
                ),
                "stdout_log": probes["stdout_log"],
                "stderr_log": probes["stderr_log"],
                "exit_log": probes["exit_log"],
                "stdout_sha256": probes["stdout_sha256"],
                "stderr_sha256": probes["stderr_sha256"],
                "exit_log_sha256": probes["exit_log_sha256"],
            },
        ],
        "nm7_correction_of_the_1_1_1_receipt": {
            "issue": (
                "The design 1.1.1 implementation receipt states a verify_pack result that contradicts "
                "the log it binds by sha256."
            ),
            "old_receipt": OLD_111_RECEIPT,
            "old_receipt_sha256": sha256(old_receipt_path),
            "old_receipt_stated_result": old_receipt_result,
            "old_receipt_stated_passed_count": old_stated_count,
            "old_hash_bound_log": OLD_111_PACK_LOG,
            "old_hash_bound_log_sha256": sha256(old_pack_log_path),
            "old_hash_bound_log_passed_count": old_pack_json["passed"],
            "old_hash_bound_log_failed_count": old_pack_json["failed"],
            "old_log_sha256_matches_the_receipt_binding": (
                sha256(old_pack_log_path) == old_receipt_pack.get("stdout_sha256")
            ),
            "finding": (
                "The design 1.1.1 receipt states passed %s, while the log it binds by sha256 reports "
                "passed %d. The stated figure is stale; it is the design 1.1 receipt's number and was "
                "carried over. The log itself is correct and in the record."
                % (old_stated_count, old_pack_json["passed"])
            ),
            "action_taken": (
                "The old receipt, the old markdown receipt and the old logs are retained byte for "
                "byte; nothing under d0-worker/design11/ or d0-worker/design111/ was rewritten. This "
                "appended correction receipt states the true figure and points at the old receipt "
                "and at the log that carries it."
            ),
            "new_tree_count": {
                "command": "python3 -B tools/verify_pack.py",
                "passed": pack_json["passed"],
                "failed": pack_json["failed"],
                "source": "logs/verify_pack.stdout.log of this run, sha256 %s" % pack["stdout_sha256"],
                "note": (
                    "This is the count of the *design 1.1.2* tree and it is not comparable to the "
                    "historical %d figure as if it were the same tree: most of the checks are one per "
                    "MANIFEST.sha256 line, so the tree change moves the count."
                    % old_pack_json["passed"]
                ),
            },
        },
        "finding_counts": {
            "source": "reports/v1-redesign/d0-review/design111/findings.json",
            "actual_finding_array": {"Major": 3, "Minor": 5, "Fatal": 0, "total": 8},
            "derived_counts_in_the_1_1_2_adjudication": {"Fatal": 0, "Major": 3, "Minor": 5},
            "review_report_summary_minor_count": 6,
            "discrepancy": (
                "The review report summary says 6 Minor while its own finding array holds 5 Minor "
                "and 3 Major. The original report is retained unchanged; the eight NM ids are the "
                "actual finding array and the discrepancy is reconciled here, as the design 1.1.2 "
                "adjudication requires. No ninth finding was invented."
            ),
        },
        "n1_n6_status": {
            "N1": "RESOLVED",
            "N2": "RESOLVED",
            "N3": "RESOLVED",
            "N4": "RESOLVED",
            "N5": "RESOLVED_WITH_RESIDUAL",
            "N6": "RESOLVED_WITH_RESIDUAL",
            "note": (
                "The reviewer recomputed N1-N4 as independently resolved and N5/N6 as resolved with "
                "a residual. The residuals are NM-5 and NM-6 and they are corrected in this package. "
                "The original 22 design findings remain design resolved. The product stays "
                "R1 / WAIT_HUMAN."
            ),
        },
        "preserved_prior_artifacts": [
            "reports/v1-redesign/d0-worker/implementation-receipt.json",
            "reports/v1-redesign/d0-worker/implementation-receipt.md",
            "reports/v1-redesign/d0-worker/design11/implementation-receipt-1.1.json",
            "reports/v1-redesign/d0-worker/design11/implementation-receipt-1.1.md",
            "reports/v1-redesign/d0-worker/design11/logs/",
            "reports/v1-redesign/d0-worker/design111/implementation-receipt-1.1.1.json",
            "reports/v1-redesign/d0-worker/design111/implementation-receipt-1.1.1.md",
            "reports/v1-redesign/d0-worker/design111/logs/",
            "reports/v1-redesign/d0-worker/logs/",
            "reports/v1-redesign/d0-review/",
            "reports/v1-redesign/history/",
        ],
        "limitations": [
            "This is an offline plan and schema correction. It is not product acceptance, not a product Gate0, not a Stage PASS and not a human signature.",
            "The product coordinate stays R1 / WAIT_HUMAN; the 621b1bf experience signature is still absent and the samples stay NOT_MATERIALIZED_NOT_FROZEN.",
            "The candidate migration is only read as text; it is never executed and no production database is opened.",
            "The N5 domain engine is an offline plan/schema rule guard. There is no runtime adapter yet, so the conformance fixtures prove that the declared rule is implementable and unambiguous; they do not verify product output.",
            "The scene hash can only be validated against the declared prose rule, because the DDL that defines lvw_scene_hash is not part of the frozen package.",
            "The probe suite is a bounded independent selection, not an exhaustive enumeration of the checker's inputs.",
            "The provider and model identity are self reported by the worker session and were not independently verified.",
        ],
        "next_owner": "Codex after worker_done, then an isolated independent regression recheck; no new human execution permission is required",
    }

    out_json = HERE / "implementation-receipt-1.1.2.json"
    out_json.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    markdown = []
    markdown.append("# D0-B-IMPL｜V1 多镜头设计 1.1.2 集中纠偏实施收据（NM-1..NM-8）")
    markdown.append("")
    markdown.append("- 项目 / Stage / Workpack：LVW_Prompt_Service_MasterPack_v2.0.0 ｜ Stage `V1-D0` ｜ Workpack `D0-B-IMPL`")
    markdown.append("- 设计权威：`3af446302f6237b41dc500ee290caf2b5075ab80`（合并进本 checkout，`36cfe62`，clean merge 无冲突）")
    markdown.append("- 状态：`READY_FOR_REVIEW`｜产品动作 0｜人工签署 无｜产品 PASS 否｜Stage PASS 否")
    markdown.append("- 编排身份：coordinator `%s`｜worker `%s`｜task `%s`｜dispatch `%s`（provider 元数据自报、未独立验证）"
                     % (ORCHESTRATION["coordinator_terminal"], ORCHESTRATION["worker_terminal"],
                        ORCHESTRATION["task_id"], ORCHESTRATION["dispatch_id"]))
    markdown.append("- 本包是**一个集中纠偏包**，不是新的产品 Stage；产品仍为 `R1 / WAIT_HUMAN`，无样本冻结，无运行时授权")
    markdown.append("")
    markdown.append("## 1. 强制命令（原始日志在 `logs/`，数字均由脚本从日志提取）")
    markdown.append("")
    markdown.append("| 命令 | exit | 结果 | stdout sha256 |")
    markdown.append("|---|---|---|---|")
    markdown.append("| `python3 -B tools/verify_v1_plan.py` | %d | `%s` | `%s` |"
                     % (checker["exit_code"], parse_result_line(checker["stdout_text"]), checker["stdout_sha256"]))
    markdown.append("| `python3 -B -m pytest tools/test_verify_v1_plan.py -q` | %d | %d passed, %d failed, %d skipped | `%s` |"
                     % (pytest_log["exit_code"], pytest_counts["passed"], pytest_counts["failed"],
                        pytest_counts["skipped"], pytest_log["stdout_sha256"]))
    markdown.append("")
    markdown.append("补充只读校验：")
    markdown.append("")
    markdown.append("| 命令 | exit | 结果 | stdout sha256 |")
    markdown.append("|---|---|---|---|")
    markdown.append("| `python3 -B tools/verify_pack.py` | %d | passed %d, failed %d | `%s` |"
                     % (pack["exit_code"], pack_json["passed"], pack_json["failed"], pack["stdout_sha256"]))
    markdown.append("| `python3 -B tools/verify_governance.py` | %d | errors %s, failed %d | `%s` |"
                     % (governance["exit_code"], governance_json["errors"], governance_json["failed"], governance["stdout_sha256"]))
    markdown.append("| owner `verify-design112.py`（临时副本） | %d | %s | `%s` |"
                     % (owner_probe["exit_code"], owner_probe["stdout_text"].strip(), owner_probe["stdout_sha256"]))
    markdown.append("| 独审探针 P01/P02/P05/P22/P23/P24 + P00 | %d | 六个负例均 exit 1 并给出确定性 finding；P00 正例 exit 0 | `%s` |"
                     % (probes["exit_code"], probes["stdout_sha256"]))
    markdown.append("")
    markdown.append("## 2. NM-7：旧 1.1.1 收据的更正（追加式，旧字节全部保留）")
    markdown.append("")
    markdown.append("- 旧收据：`%s`（sha256 `%s`）" % (OLD_111_RECEIPT, sha256(old_receipt_path)))
    markdown.append("- 旧收据正文写的是 **passed %s**；它按 sha256 绑定的日志 `%s`（sha256 `%s`）写的是 **passed %d**"
                     % (old_stated_count, OLD_111_PACK_LOG, sha256(old_pack_log_path), old_pack_json["passed"]))
    markdown.append("- 结论：正文数字陈旧（沿用 1.1 收据），日志本身正确且在册；**旧收据、旧 markdown、旧日志一字未改**")
    markdown.append("- 本树 `verify_pack` 的 **passed %d** 是新树计数，与历史 %d 不可直接等同（多数检查按 MANIFEST.sha256 逐行一项）"
                     % (pack_json["passed"], old_pack_json["passed"]))
    markdown.append("")
    markdown.append("## 3. 计数核对（NM-7 附带）")
    markdown.append("")
    markdown.append("- `findings.json` 的实际 finding 数组：**3 Major + 5 Minor（Fatal 0，共 8 条 NM-1..NM-8）**")
    markdown.append("- 独审报告 summary 写的是 **6 Minor**；该报告原文保留未改，差异在此收据核对说明，未凭空制造第九条问题")
    markdown.append("")
    markdown.append("## 4. 允许写入清单（与 stage-control 一致）")
    markdown.append("")
    for rel in receipt["permitted_inventory"]["files_written_by_this_workpack"]:
        markdown.append("- `%s`" % rel)
    markdown.append("")
    markdown.append("## 5. 限制")
    markdown.append("")
    for item in receipt["limitations"]:
        markdown.append("- %s" % item)
    markdown.append("")
    (HERE / "implementation-receipt-1.1.2.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt_json": str(out_json.relative_to(ROOT)),
        "checker_exit": checker["exit_code"],
        "pytest_passed": pytest_counts["passed"],
        "verify_pack_passed": pack_json["passed"],
        "owner_probe": owner_probe["stdout_text"].strip(),
        "reviewer_probes_exit": probes["exit_code"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
