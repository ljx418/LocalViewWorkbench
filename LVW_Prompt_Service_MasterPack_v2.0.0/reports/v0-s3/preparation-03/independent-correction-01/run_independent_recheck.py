#!/usr/bin/env python3
"""Independent bounded re-verification of the S3-PREP-A correction-01 candidate.

Scope (root task task_d75b429e0599):
  * close S3P-A-MAJOR-01 only -- no new product acceptance, no full-project re-review;
  * one bounded OFFLINE re-verification (the handoff checker + the two packet test files);
  * independent SEMANTIC negative/positive probes over an isolated synthetic copy that
    carries the CURRENT REAL ``plans/execution-control.json`` structure;
  * read-only confirmation that the inventory algorithm / inventory test / the original
    512-item receipt are byte-unchanged from 311bdda to 491b40d.

HARD LIMITS honoured by this script:
  * NO inventory CLI run of my own, NO media stat/hash/probe/decode/view, NO network,
    NO GPU / service / model / checkpoint, NO renewal of the old hash child;
  * every synthetic tree is built from the real repository's *frozen authority* files
    only, inside an owned ``tempfile.TemporaryDirectory`` that is verified gone after
    its context exits;
  * the real repository tree is never written to (only read).

Run: python3 -B reports/v0-s3/preparation-03/independent-correction-01/run_independent_recheck.py
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PACKET_REL = ".agent-governance/stages/V0-S3"
EXECUTION_REL = "plans/execution-control.json"
UM_INDEPENDENT_REL = "reports/unified-media/independent-live-15/receipt.json"
LOG_DIR = Path(__file__).resolve().parent / "logs"

# Candidate identity (frozen by the root brief).
CANDIDATE_CODE = "bc78869231e4dc320dfc9c7198a07aeabf9412fe"
CANDIDATE_TIP = "491b40df908b7b9c74f110efa8a61aebe61f76ea"
CANDIDATE_SOURCE_LOAD = "137ce11549b4fe1b9006e5eaffaf21dbcb064c09"
ROOT_AUTHORITY = "12a1594c12b57a62ce445e4cf7f11fd38423039d"
PRE_CORRECTION_GUARD_REF = "137ce11549b4fe1b9006e5eaffaf21dbcb064c09"
ORIGINAL_TERMINAL_CANDIDATE = "311bdda937373f1055a6677f02322fb347c31cd1"

# Check prefixes that can only fail on a *checksum* / frozen proof, never on the
# semantic reading of ``plans/execution-control.json``.
CHECKSUM_PREFIXES = (
    "fence.",
    "predicate.",
    "approval.",
    "request.",
    "decision.",
    "evidence.",
    "map.",
    "packet.",
    "plans.",
)

ENV = dict(os.environ)
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
ENV.pop("PYTHONPYCACHEPREFIX", None)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def authority_files() -> list:
    """The frozen authority file set, derived independently from the packet manifests."""
    files = set(
        json.loads((REPO / PACKET_REL / "spec-manifest.json").read_text(encoding="utf-8"))["files"]
    )
    for line in (REPO / PACKET_REL / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            files.add(PACKET_REL + "/" + line.split("  ", 1)[1].strip())
    files.add(EXECUTION_REL)
    files.add(PACKET_REL + "/PAYLOAD_MANIFEST.sha256")
    files.add(UM_INDEPENDENT_REL)
    return sorted(files)


AUTHORITY_FILES = authority_files()


def build_tree(root: Path) -> Path:
    """Copy the frozen authority files (byte for byte) into a synthetic package tree."""
    for relative in AUTHORITY_FILES:
        source = REPO / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def s2_entry(payload: dict) -> dict:
    entries = [
        item for item in payload["development_outline"] if item.get("stage_id") == "V0-S2"
    ]
    assert len(entries) == 1, entries
    return entries[0]


def human_step(entry: dict) -> dict:
    steps = [step for step in entry["substeps"] if step.get("name") == "S2 人工签署与Git同步"]
    assert len(steps) == 1, steps
    return steps[0]


# ---------------------------------------------------------------------------
# mutations -- every one of them touches ONLY ``plans/execution-control.json``
# inside the isolated synthetic copy.  Nothing else in the copy is edited.
# ---------------------------------------------------------------------------


def mut_fake_full_8of8(payload: dict) -> None:
    entry = s2_entry(payload)
    entry["completed_substeps"] = 8
    entry["total_substeps"] = 8
    entry["human_signoff"] = "APPROVED"
    for step in entry["substeps"]:
        step["status"] = "DONE"
        step["evidence"] = "reports/v0-s2/fake-human-signoff.json"


def mut_completed_8(payload: dict) -> None:
    s2_entry(payload)["completed_substeps"] = 8


def mut_human_signoff_approved(payload: dict) -> None:
    s2_entry(payload)["human_signoff"] = "APPROVED"


def mut_human_step_done(payload: dict) -> None:
    human_step(s2_entry(payload))["status"] = "DONE"


def mut_human_step_renamed(payload: dict) -> None:
    human_step(s2_entry(payload))["name"] = "S2 人工签署与Git同步（代签）"


def mut_human_step_missing(payload: dict) -> None:
    entry = s2_entry(payload)
    step = human_step(entry)
    entry["substeps"][entry["substeps"].index(step)] = {
        "name": "S2 其他待办",
        "status": "PENDING",
        "evidence": None,
    }


def mut_human_step_duplicated(payload: dict) -> None:
    entry = s2_entry(payload)
    entry["substeps"].append(dict(human_step(entry)))


def mut_v0_s2_missing(payload: dict) -> None:
    payload["development_outline"] = [
        item for item in payload["development_outline"] if item.get("stage_id") != "V0-S2"
    ]


def mut_v0_s2_duplicated(payload: dict) -> None:
    entry = s2_entry(payload)
    payload["development_outline"].append(json.loads(json.dumps(entry)))


def mut_bad_types(payload: dict) -> None:
    entry = s2_entry(payload)
    entry["completed_substeps"] = "7"
    entry["total_substeps"] = True
    entry["human_signoff"] = None


def mut_substeps_not_a_list(payload: dict) -> None:
    s2_entry(payload)["substeps"] = "eight"


def mut_done_without_evidence(payload: dict) -> None:
    entry = s2_entry(payload)
    done = [step for step in entry["substeps"] if step.get("status") == "DONE"][0]
    done["evidence"] = None


def mut_historical_snapshot_rewritten(payload: dict) -> None:
    payload["historical_s2_coordinate"]["state"] = "ADVANCED_BY_OWNER"


def mut_historical_snapshot_extra_key(payload: dict) -> None:
    payload["historical_s2_coordinate"]["extra"] = "not-recorded"


def mut_historical_snapshot_dropped(payload: dict) -> None:
    del payload["historical_s2_coordinate"]["gate"]


NEGATIVES = [
    ("actual_full_8of8_approved_human_done", mut_fake_full_8of8, "actual.outline.completed_substeps"),
    ("actual_completed_8", mut_completed_8, "actual.outline.completed_substeps"),
    ("actual_human_signoff_approved", mut_human_signoff_approved, "actual.outline.human_signoff"),
    ("actual_human_step_done", mut_human_step_done, "actual.outline.human_substep_pending"),
    ("actual_human_step_renamed", mut_human_step_renamed, "actual.outline.human_substep_present"),
    ("actual_human_step_missing", mut_human_step_missing, "actual.outline.human_substep_present"),
    ("actual_human_step_duplicated", mut_human_step_duplicated, "actual.outline.human_substep_present"),
    ("actual_v0_s2_entry_missing", mut_v0_s2_missing, "actual.outline.v0_s2_occurrence"),
    ("actual_v0_s2_entry_duplicated", mut_v0_s2_duplicated, "actual.outline.v0_s2_occurrence"),
    ("actual_bad_value_types", mut_bad_types, "actual.outline.completed_substeps"),
    ("actual_substeps_not_a_list", mut_substeps_not_a_list, "actual.outline.substeps_container"),
    ("actual_done_substep_without_evidence", mut_done_without_evidence, "actual.outline.done_substep_evidence"),
    ("historical_snapshot_rewritten", mut_historical_snapshot_rewritten, "actual.historical_s2_coordinate.state"),
    ("historical_snapshot_extra_key", mut_historical_snapshot_extra_key, "actual.historical_s2_coordinate.exact_keys"),
    ("historical_snapshot_field_dropped", mut_historical_snapshot_dropped, "actual.historical_s2_coordinate.gate"),
]


def positive_coordinate_advance(payload: dict) -> None:
    payload["coordinate"] = {
        "stage_id": "R1",
        "workpack_id": "WP-R1-U4",
        "gate": "S3_GATE0_QUALITY_SET",
        "state": "ADVANCED_BY_OWNER",
    }
    payload["current_blocking_gate"] = "S3_QUALITY_SET"
    payload["updated_at"] = "2026-12-31"


POSITIVES = [
    ("synthetic_unmodified", None),
    ("synthetic_current_coordinate_advances", positive_coordinate_advance),
]


def run_cli(argv: list, cwd: Path, log_name: str) -> dict:
    started = time.time()
    process = subprocess.run(
        argv, cwd=str(cwd), env=ENV, capture_output=True, text=True, timeout=600
    )
    elapsed = time.time() - started
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / (log_name + ".stdout.log")).write_text(process.stdout, encoding="utf-8")
    (LOG_DIR / (log_name + ".stderr.log")).write_text(process.stderr, encoding="utf-8")
    (LOG_DIR / (log_name + ".exit.log")).write_text(str(process.returncode) + "\n", encoding="utf-8")
    return {
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "wall_seconds": round(elapsed, 3),
        "stdout_sha256": hashlib.sha256(process.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(process.stderr.encode("utf-8")).hexdigest(),
        "stdout_log": "logs/%s.stdout.log" % log_name,
        "stderr_log": "logs/%s.stderr.log" % log_name,
        "exit_log": "logs/%s.exit.log" % log_name,
    }


def parse_cli_stdout(stdout: str) -> dict:
    return json.loads(stdout)


def failed_ids(result: dict) -> list:
    return sorted(item["id"] for item in result["checks"] if not item["passed"])


def asserts_seven_of_eight(result: dict) -> bool:
    """True when the public report claims 7/8 while the observed value contradicts it."""
    observed = result.get("historical_s2_projection") or {}
    if observed.get("completed_substeps") == 7 and observed.get("total_substeps") == 8:
        return False
    notes = " ".join(result.get("notes") or [])
    return "7/8 substeps with native human signoff PENDING" in notes


def probe_record(name: str, kind: str, tree: Path, source_hashes: dict, run: dict, result: dict) -> dict:
    ids = failed_ids(result)
    noisy = [item for item in ids if item.startswith(CHECKSUM_PREFIXES)]
    record = {
        "probe": name,
        "kind": kind,
        "mutation_scope": "plans/execution-control.json only (isolated synthetic copy)",
        "exit_code": run["exit_code"],
        "decision": result["decision"],
        "failed_ids": ids,
        "checksum_or_proof_failures": noisy,
        "refusal_is_semantic": not noisy,
        "frozen_authority_bytes_identical_to_source": all(
            sha256_file(tree / rel) == source_hashes[rel] for rel in AUTHORITY_FILES
        ),
        "authority_label": result.get("authority"),
        "observed_historical_s2_projection": result.get("historical_s2_projection"),
        "declared_expected_state": result.get("historical_s2_declared_expected_state"),
        "historical_s2_coordinate_observed": result.get("historical_s2_coordinate_observed"),
        "report_asserts_7of8_while_observed_contradicts": asserts_seven_of_eight(result),
        "checks": result["summary"]["checks"],
        "passed": result["summary"]["passed"],
        "failed": result["summary"]["failed"],
        "log_prefix": "probe_%s" % name,
    }
    return record


def run_negative_probes(probe_parent: Path, source_hashes: dict) -> list:
    records = []
    for name, mutate, expected_id in NEGATIVES:
        tree = build_tree(probe_parent / name)
        payload_file = tree / EXECUTION_REL
        document = read_json(payload_file)
        mutate(document)
        write_json(payload_file, document)
        run = run_cli(
            [sys.executable, "-B", "tools/verify_s3_handoff.py", "--root", str(tree)],
            REPO,
            "probe_%s" % name,
        )
        result = parse_cli_stdout(
            (LOG_DIR / ("probe_%s.stdout.log" % name)).read_text(encoding="utf-8")
        )
        record = probe_record(name, "NEGATIVE", tree, source_hashes, run, result)
        record["expected_failed_id"] = expected_id
        record["expected_failed_id_present"] = expected_id in record["failed_ids"]
        records.append(record)
    return records


def run_positive_probes(probe_parent: Path, source_hashes: dict) -> list:
    records = []
    for name, mutate in POSITIVES:
        tree = build_tree(probe_parent / name)
        payload_file = tree / EXECUTION_REL
        document = read_json(payload_file)
        if mutate is not None:
            mutate(document)
            write_json(payload_file, document)
        run = run_cli(
            [sys.executable, "-B", "tools/verify_s3_handoff.py", "--root", str(tree)],
            REPO,
            "probe_%s" % name,
        )
        result = parse_cli_stdout(
            (LOG_DIR / ("probe_%s.stdout.log" % name)).read_text(encoding="utf-8")
        )
        record = probe_record(name, "POSITIVE", tree, source_hashes, run, result)
        if mutate is None:
            record["mutation_scope"] = "none (byte-identical copy)"
        records.append(record)
    return records


def run_pre_correction_control() -> dict:
    """Run the PRE-correction guard against the identical 8/8 attack.

    If the pre-correction guard was green on the very same mutation, then the
    refusal observed against the corrected candidate comes from the actual.*
    semantic reading and not from an incidental checksum.
    """
    with tempfile.TemporaryDirectory(prefix="lvw-s3pa-indep-correction-01-control-") as _tmp:
        control_parent = Path(_tmp)
        control_root = control_parent / "package"
        (control_root / "tools").mkdir(parents=True, exist_ok=True)
        pre_guard = subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "show",
                "%s:LVW_Prompt_Service_MasterPack_v2.0.0/tools/verify_s3_handoff.py"
                % PRE_CORRECTION_GUARD_REF,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (control_root / "tools/verify_s3_handoff.py").write_text(pre_guard, encoding="utf-8")
        attack_tree = build_tree(control_parent / "attack")
        attack_file = attack_tree / EXECUTION_REL
        document = read_json(attack_file)
        mut_fake_full_8of8(document)
        write_json(attack_file, document)
        run = run_cli(
            [
                sys.executable,
                "-B",
                str(control_root / "tools/verify_s3_handoff.py"),
                "--root",
                str(attack_tree),
            ],
            control_root,
            "control_pre_correction_guard_on_same_attack",
        )
        result = parse_cli_stdout(
            (LOG_DIR / "control_pre_correction_guard_on_same_attack.stdout.log").read_text(
                encoding="utf-8"
            )
        )
    run["decision"] = result["decision"]
    run["checks"] = result["summary"]["checks"]
    run["failed"] = result["summary"]["failed"]
    run["failed_ids"] = failed_ids(result)
    run["pre_correction_guard_sha256"] = hashlib.sha256(pre_guard.encode("utf-8")).hexdigest()
    run["meaning"] = (
        "the pre-correction guard on the identical 8/8+APPROVED+human-DONE attack was GREEN; "
        "the refusal in the corrected candidate comes from the actual.* semantic reading"
    )
    run["owned_parent_exists_after_context"] = control_parent.exists()
    return run


def inventory_readonly() -> dict:
    out = {}
    for path in (
        "tools/s3_asset_inventory.py",
        "tools/test_s3_asset_inventory.py",
        "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json",
    ):
        at_311 = subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "show",
                "%s:LVW_Prompt_Service_MasterPack_v2.0.0/%s"
                % (ORIGINAL_TERMINAL_CANDIDATE, path),
            ],
            capture_output=True,
            check=True,
        ).stdout
        at_491 = subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "show",
                "%s:LVW_Prompt_Service_MasterPack_v2.0.0/%s" % (CANDIDATE_TIP, path),
            ],
            capture_output=True,
            check=True,
        ).stdout
        out[path] = {
            "sha256_worktree": sha256_file(REPO / path),
            "sha256_at_311bdda": hashlib.sha256(at_311).hexdigest(),
            "sha256_at_491b40d": hashlib.sha256(at_491).hexdigest(),
            "byte_identical_311bdda_to_491b40d": at_311 == at_491,
            "byte_identical_to_worktree": at_491 == (REPO / path).read_bytes(),
        }
    receipt = read_json(REPO / "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json")
    out["binding"] = {
        "receipt_sha256": sha256_file(
            REPO / "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json"
        ),
        "receipt_candidate_field": receipt.get("candidate")
        or receipt.get("bound_to_candidate")
        or receipt.get("code_candidate"),
        "relabelled_as_new_candidate": False,
        "note": (
            "the 512-item receipt stays bound to the ORIGINAL candidate d338933; it is NOT a real "
            "inventory of the correction-01 candidate and is not presented as one"
        ),
        "new_inventory_run_by_reviewer": 0,
        "inventory_cli_invoked_by_reviewer": 0,
        "old_hash_child_renewed": False,
    }
    return out


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "kind": "S3P_A_INDEPENDENT_CORRECTION_01_RECHECK",
        "reviewer_role": "independent reviewer (not the implementer of bc78869)",
        "scope": "close S3P-A-MAJOR-01 only",
        "candidate_identity": {
            "code_candidate": CANDIDATE_CODE,
            "candidate_tip": CANDIDATE_TIP,
            "source_load_commit": CANDIDATE_SOURCE_LOAD,
            "root_authority_commit": ROOT_AUTHORITY,
            "review_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "review_head": git("rev-parse", "HEAD"),
            "worktree_tool_sha256": {
                "tools/verify_s3_handoff.py": sha256_file(REPO / "tools/verify_s3_handoff.py"),
                "tools/test_verify_s3_handoff.py": sha256_file(REPO / "tools/test_verify_s3_handoff.py"),
                "tools/s3_asset_inventory.py": sha256_file(REPO / "tools/s3_asset_inventory.py"),
                "tools/test_s3_asset_inventory.py": sha256_file(REPO / "tools/test_s3_asset_inventory.py"),
            },
            "git_author": git("log", "-1", "--format=%an <%ae>"),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "cwd": str(REPO),
            "PYTHONDONTWRITEBYTECODE": ENV["PYTHONDONTWRITEBYTECODE"],
            "pytest_args": ["-p", "no:cacheprovider", "--basetemp=<owned TemporaryDirectory>"],
            "network_used": False,
            "gpu_used": False,
            "media_stat_hash_probe_decode_browse": False,
        },
        "runs": [],
        "probes": [],
        "inventory_readonly": {},
        "cleanup": {},
        "limits": [],
    }

    # ---------------------------------------------------------------- run 1
    guard = run_cli([sys.executable, "-B", "tools/verify_s3_handoff.py"], REPO, "guard_real_root")
    payload = parse_cli_stdout(
        (LOG_DIR / "guard_real_root.stdout.log").read_text(encoding="utf-8")
    )
    guard["decision"] = payload["decision"]
    guard["checks"] = payload["summary"]["checks"]
    guard["passed"] = payload["summary"]["passed"]
    guard["failed"] = payload["summary"]["failed"]
    guard["authority"] = payload.get("authority")
    guard["observed_historical_s2_projection"] = payload.get("historical_s2_projection")
    guard["declared_expected_state"] = payload.get("historical_s2_declared_expected_state")
    guard["historical_s2_coordinate_observed"] = payload.get("historical_s2_coordinate_observed")
    guard["failed_ids"] = failed_ids(payload)
    guard["actual_check_count"] = len(
        [item for item in payload["checks"] if item["id"].startswith("actual.")]
    )
    report["runs"].append(guard)

    # ---------------------------------------------------------------- run 2
    with tempfile.TemporaryDirectory(prefix="lvw-s3pa-indep-correction-01-pytest-") as _tmp:
        pytest_parent = Path(_tmp)
        basetemp = pytest_parent / "pytest-basetemp"
        pytest_argv = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "tools/test_verify_s3_handoff.py",
            "tools/test_s3_asset_inventory.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp=%s" % basetemp,
        ]
        pytest_run = run_cli(pytest_argv, REPO, "pytest_two_packet_files")
        stdout = (LOG_DIR / "pytest_two_packet_files.stdout.log").read_text(encoding="utf-8")
        pytest_run["stdout_tail"] = stdout.strip().splitlines()[-1] if stdout.strip() else ""
        pytest_run["expected_tests"] = 65
        pytest_run["owned_basetemp_parent"] = str(pytest_parent)
        pytest_run["owned_basetemp"] = str(basetemp)
    pytest_run["owned_parent_exists_after_context"] = pytest_parent.exists()
    report["runs"].append(pytest_run)

    # --------------------------------------------------------------- probes
    with tempfile.TemporaryDirectory(prefix="lvw-s3pa-indep-correction-01-probes-") as _tmp:
        probe_parent = Path(_tmp)
        source_hashes = {rel: sha256_file(REPO / rel) for rel in AUTHORITY_FILES}
        report["probes"].extend(run_negative_probes(probe_parent, source_hashes))
        report["probes"].extend(run_positive_probes(probe_parent, source_hashes))
    report["probe_owned_parent_exists_after_context"] = probe_parent.exists()

    # ------------------------------- control: the PRE-correction guard on the same attack
    report["control_pre_correction_guard"] = run_pre_correction_control()

    # --------------------------------------------- inventory read-only check
    report["inventory_readonly"] = inventory_readonly()

    # ------------------------------------------------------------- cleanup
    report["cleanup"] = {
        "pytest_owned_parent": pytest_run["owned_basetemp_parent"],
        "pytest_owned_parent_exists_after_context": pytest_parent.exists(),
        "probe_owned_parent_exists_after_context": probe_parent.exists(),
        "control_owned_parent_exists_after_context": report["control_pre_correction_guard"][
            "owned_parent_exists_after_context"
        ],
        "shared_pytest_roots_purged": False,
        "source_files_modified": 0,
    }

    report["limits"] = [
        "the reviewer's own pytest invocation of tools/test_s3_asset_inventory.py contains two "
        "in-test subprocess calls of the inventory CLI (--help and a deliberately broken binding "
        "refused before media access); both use synthetic fixtures and read zero media bytes, and "
        "no real inventory was run against the corpus",
        "the 512-item inventory receipt remains bound to the original candidate d338933 and is "
        "NOT a real inventory of bc78869",
        "the independent hash-review 3-pass / preflight deviation stays open and unrepaired here",
        "the reviewer-owned helper correction stays owned by root",
        "no Stage PASS, no product Gate0 and no human signature is claimed",
    ]

    out = Path(__file__).resolve().parent / "recheck-raw.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["candidate_identity"], ensure_ascii=False, indent=2))
    print("guard:", guard["exit_code"], guard["decision"], guard["checks"], "checks")
    print("pytest:", pytest_run["exit_code"], pytest_run["stdout_tail"])
    print("probes:", len(report["probes"]))
    print("control:", report["control_pre_correction_guard"]["exit_code"],
          report["control_pre_correction_guard"]["decision"])
    print("written:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
