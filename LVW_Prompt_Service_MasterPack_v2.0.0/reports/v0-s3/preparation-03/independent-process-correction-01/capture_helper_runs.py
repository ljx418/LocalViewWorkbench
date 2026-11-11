#!/usr/bin/env python3
"""Capture raw, reproducible evidence of the corrected helper's CLI behaviour.

Three cases are executed against *synthetic* fixtures inside an owned
TemporaryDirectory:

1. ``positive``          - every preflight check passes and the three
                           synthetic files verify against an independent
                           sha256 oracle;
2. ``metadata_drift``    - a candidate code file drifts away from the bound
                           commit, so the preflight must fail closed with
                           zero source reads and a non-zero exit;
3. ``production_root``   - the child points at the production media root,
                           which is hard disabled.

The exact command line, exit code, stdout and stderr of each run are kept
verbatim under ``raw/``.  No real media is touched by any case.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
HELPER = HERE / "helper" / "hash_child_recheck_correction.py"

sys.path.insert(0, str(HERE / "helper"))
sys.path.insert(0, str(HERE / "tests"))
import test_hash_child_recheck_correction as suite  # noqa: E402


def run_case(name, fix, out_path, expected_child_sha256, anchor_commit, allow_roots):
    command = [
        sys.executable,
        str(HELPER),
        "--child", str(fix.child_path),
        "--out", str(out_path),
        "--expected-child-sha256", expected_child_sha256,
        "--expected-child-commit", anchor_commit,
    ]
    for root in allow_roots:
        command += ["--allow-source-root", str(root)]
    started = time.monotonic()
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = round(time.monotonic() - started, 3)
    (RAW / ("helper-run-%s.stdout.log" % name)).write_text(proc.stdout, encoding="utf-8")
    (RAW / ("helper-run-%s.stderr.log" % name)).write_text(proc.stderr, encoding="utf-8")
    (RAW / ("helper-run-%s.exit.log" % name)).write_text("%d\n" % proc.returncode, encoding="utf-8")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    return {
        "case": name,
        "command": command,
        "exit_code": proc.returncode,
        "elapsed_seconds": elapsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "result_payload_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
        "decision": payload.get("decision"),
        "preflight_validated_before_source_access": payload.get(
            "preflight_validated_before_source_access"),
        "source_phase_entered": payload.get("source_phase_entered"),
        "counters": payload.get("counters"),
        "preflight_rejection": payload.get("preflight_rejection"),
        "guard": payload.get("guard"),
        "results": [
            {
                "relative_path": r.get("relative_path"),
                "result": r.get("result"),
                "actual_sha256": r.get("actual_sha256"),
                "expected_sha256": r.get("expected_sha256"),
            }
            for r in payload.get("results", [])
        ],
    }


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="lvw-helper-capture-") as parent:
        parent_path = Path(parent)
        fix = suite.Fixture(parent_path)
        fix.package.mkdir(parents=True)
        fix.source.mkdir(parents=True)
        (parent_path / "outside").mkdir(parents=True)

        suite.git(fix.repo, "init", "-q", "-b", "main")
        (fix.package / "README.md").write_text("synthetic fixture package\n", encoding="utf-8")
        fix.source_commit = fix.commit_all("synthetic: base commit")
        (fix.package / "tools").mkdir(parents=True, exist_ok=True)
        (fix.package / "tools" / "alpha.py").write_text("ALPHA = 'candidate-alpha'\n",
                                                        encoding="utf-8")
        (fix.package / "tools" / "beta.py").write_text("BETA = 'candidate-beta'\n", encoding="utf-8")
        fix.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        fix.receipt_path.write_text(
            json.dumps({"kind": "SYNTHETIC_INVENTORY_RECEIPT", "items": []}) + "\n",
            encoding="utf-8")
        fix.code_commit = fix.commit_all("synthetic: candidate code and receipt")
        for name in ("alpha.bin", "beta.bin", "gamma.bin"):
            (fix.source / name).write_bytes(bytes(range(256)) * 2 + name.encode("utf-8"))
        fix.source_files = ["alpha.bin", "beta.bin", "gamma.bin"]
        (fix.source / suite.helper.FIXTURE_MARKER_NAME).write_text(
            suite.helper.FIXTURE_MARKER_CONTENT, encoding="utf-8")
        fix.outside_file.write_bytes(b"outside-the-fixture-root-bytes")
        fix.write_child()
        fix.anchor_commit = fix.commit_all("synthetic: fixture child authority")

        source_digests = {
            name: suite.oracle_sha256(fix.source / name) for name in fix.source_files
        }

        cases.append(run_case("positive", fix, parent_path / "positive.json",
                               fix.child_sha256, fix.anchor_commit, [fix.source]))

        # case 2: the candidate code file drifts away from the bound commit
        (fix.package / "tools" / "beta.py").write_text("BETA = 'drifted'\n", encoding="utf-8")
        cases.append(run_case("metadata-drift", fix, parent_path / "drift.json",
                              fix.child_sha256, fix.anchor_commit, [fix.source]))
        (fix.package / "tools" / "beta.py").write_text("BETA = 'candidate-beta'\n", encoding="utf-8")

        # case 3: the child points at the production media root
        fix.write_child(source_root="/mnt/c/workSpace/videoWorkLine/testSource")
        fix.anchor_commit = fix.commit_all("synthetic: repoint the child at production")
        cases.append(run_case("production-root", fix, parent_path / "production.json",
                              fix.child_sha256, fix.anchor_commit, [fix.source]))

        payload = {
            "kind": "S3_PREP_INDEPENDENT_PROCESS_CORRECTION_HELPER_CAPTURE",
            "helper": str(HELPER),
            "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(),
            "owned_parent": str(parent_path),
            "source_digests_oracle": source_digests,
            "git_commits": {
                "source_candidate": fix.source_commit,
                "implementation_code_candidate": fix.code_commit,
                "child_anchor_commit": fix.anchor_commit,
            },
            "cases": cases,
        }
    payload["owned_parent_exists_after_exit"] = parent_path.is_dir()
    (RAW / "helper-runs.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
