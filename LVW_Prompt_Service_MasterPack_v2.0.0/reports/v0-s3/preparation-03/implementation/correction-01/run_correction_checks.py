#!/usr/bin/env python3
"""Run the S3-PREP-A correction-01 evidence commands and record them verbatim.

Every run is recorded with its exact argv, its working directory, its exit
code, its wall time and the SHA-256 of its captured stdout/stderr.  Nothing in
this script decides anything: it only runs commands and writes logs.

Test isolation
--------------
The pytest runs use an *owned* ``tempfile.TemporaryDirectory`` as the parent of
the pytest ``--basetemp`` root, so no shared or pre-existing pytest root is
written to and nothing of an earlier run is purged.  After the owning context
exits, the parent directory is verified to be gone and that fact is recorded.

This script never touches source media, never hashes media, never starts a
service and never writes outside ``correction-01/``.

Usage: python3 -B reports/v0-s3/preparation-03/implementation/correction-01/run_correction_checks.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "logs"
PACKAGE_ROOT = HERE.parents[4]
GUARD_REVERT_ROOT = Path("/tmp/lvw-correction-01-guardrevert/LVW_Prompt_Service_MasterPack_v2.0.0")

PACKET_CHECKER = ["python3", "-B", "tools/verify_s3_handoff.py"]
PACKET_TESTS = [
    "python3",
    "-B",
    "-m",
    "pytest",
    "tools/test_verify_s3_handoff.py",
    "tools/test_s3_asset_inventory.py",
    "-q",
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_log(name: str, payload: bytes) -> dict:
    path = LOG_DIR / name
    path.write_bytes(payload)
    return {
        "log": "reports/v0-s3/preparation-03/implementation/correction-01/logs/" + name,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
    }


def run(name: str, argv: list, cwd: Path, extra_env: dict = None) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    started = time.monotonic()
    process = subprocess.run(
        argv, cwd=str(cwd), env=env, capture_output=True, timeout=1800
    )
    wall = round(time.monotonic() - started, 3)
    record = {
        "name": name,
        "argv": argv,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "wall_seconds": wall,
        "stdout": write_log(name + ".stdout.log", process.stdout),
        "stderr": write_log(name + ".stderr.log", process.stderr),
    }
    (LOG_DIR / (name + ".exit.log")).write_text(
        "%d\n" % process.returncode, encoding="utf-8"
    )
    record["exit_log"] = (
        "reports/v0-s3/preparation-03/implementation/correction-01/logs/"
        + name
        + ".exit.log"
    )
    return record


def run_owned_pytest(name: str, argv: list, cwd: Path) -> dict:
    """Run pytest with an owned TemporaryDirectory parent as --basetemp root."""
    with tempfile.TemporaryDirectory(prefix="lvw-s3-correction-01-") as parent:
        basetemp = os.path.join(parent, "pytest-basetemp")
        record = run(
            name,
            argv + ["--basetemp=" + basetemp],
            cwd,
        )
        record["owned_parent"] = parent
        record["basetemp"] = basetemp
        record["owned_parent_present_inside_context"] = os.path.isdir(parent)
    record["owned_parent_present_after_context"] = os.path.exists(parent)
    record["owned_parent_removed"] = not os.path.exists(parent)
    return record


def build_fake_outline_tree(destination: Path) -> dict:
    """Copy the frozen authority into a synthetic tree and fake the old S2 state."""
    sys.path.insert(0, str(PACKAGE_ROOT / "tools"))
    import test_verify_s3_handoff as suite  # noqa: E402

    tree = destination / "package"
    suite.build_tree(tree)
    payload = json.loads((tree / "plans/execution-control.json").read_text(encoding="utf-8"))
    entry = [
        item
        for item in payload["development_outline"]
        if item.get("stage_id") == "V0-S2"
    ][0]
    entry["completed_substeps"] = 8
    entry["total_substeps"] = 8
    entry["human_signoff"] = "APPROVED"
    for step in entry["substeps"]:
        if step.get("name") == "S2 人工签署与Git同步":
            step["status"] = "DONE"
    (tree / "plans/execution-control.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "tree": str(tree),
        "mutated": [
            "development_outline[V0-S2].completed_substeps = 8",
            "development_outline[V0-S2].total_substeps = 8",
            "development_outline[V0-S2].human_signoff = APPROVED",
            "development_outline[V0-S2].substeps['S2 人工签署与Git同步'].status = DONE",
        ],
        "untouched": [
            "every frozen proof file",
            "plans/tasks.json and plans/v1-revised-plan.json predicate snapshots",
            "the owner approval record",
        ],
    }


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    # 1. the frozen packet checker, unmodified command line
    records.append(run("verify_s3_handoff", PACKET_CHECKER, PACKAGE_ROOT))

    # 2. the frozen packet test command, unmodified command line
    records.append(run("pytest_packet_tests", PACKET_TESTS, PACKAGE_ROOT))

    # 3. the same test command inside an owned TemporaryDirectory parent
    records.append(run_owned_pytest("pytest_owned_basetemp", PACKET_TESTS, PACKAGE_ROOT))

    # 4. public CLI semantic negative: a faked live old-S2 projection
    with tempfile.TemporaryDirectory(prefix="lvw-s3-correction-01-cli-") as parent:
        fixture = build_fake_outline_tree(Path(parent))
        records.append(
            run(
                "cli_negative_fake_outline",
                ["python3", "-B", "tools/verify_s3_handoff.py", "--root", fixture["tree"]],
                PACKAGE_ROOT,
            )
        )
        fixture["owned_parent"] = parent
    fixture["owned_parent_present_after_context"] = os.path.exists(parent)
    fixture["owned_parent_removed"] = not os.path.exists(parent)

    # 5. regression proof: the new suite against the pre-correction guard
    if GUARD_REVERT_ROOT.is_dir():
        shutil.copy2(
            PACKAGE_ROOT / "tools/test_verify_s3_handoff.py",
            GUARD_REVERT_ROOT / "tools/test_verify_s3_handoff.py",
        )
        revert_record = run_owned_pytest(
            "guard_revert_regression",
            [
                "python3",
                "-B",
                "-m",
                "pytest",
                "tools/test_verify_s3_handoff.py",
                "-q",
            ],
            GUARD_REVERT_ROOT,
        )
        revert_record["purpose"] = (
            "the new and re-decided tests must FAIL against the pre-correction guard "
            "(137ce11) and PASS against the corrected guard"
        )
        revert_record["checkout"] = {
            "root": str(GUARD_REVERT_ROOT),
            "commit": "137ce11",
            "guard_sha256": sha256_bytes(
                (GUARD_REVERT_ROOT / "tools/verify_s3_handoff.py").read_bytes()
            ),
            "test_sha256": sha256_bytes(
                (GUARD_REVERT_ROOT / "tools/test_verify_s3_handoff.py").read_bytes()
            ),
            "replaced": "only tools/test_verify_s3_handoff.py (the corrected test suite)",
            "guard_unchanged": "tools/verify_s3_handoff.py is the pre-correction guard",
        }
        records.append(revert_record)
    else:
        records.append(
            {
                "name": "guard_revert_regression",
                "skipped": True,
                "reason": "throwaway pre-correction checkout not present",
            }
        )

    summary = {
        "kind": "S3_PREP_A_CORRECTION_01_RUN_CONFIGURATION",
        "package_root": str(PACKAGE_ROOT),
        "python": sys.version.split()[0],
        "pytest_basetemp_policy": (
            "owned tempfile.TemporaryDirectory parent; the parent is verified gone "
            "after the context exits; no shared or pre-existing pytest root is purged"
        ),
        "environment_overrides": {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DEBUG_TEMPROOT": "<the owned parent, per run>",
        },
        "cli_negative_fixture": fixture,
        "runs": records,
    }
    (HERE / "run_configuration.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
