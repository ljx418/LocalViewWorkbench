#!/usr/bin/env python3
"""Run the corrected-helper test suite inside an owned TemporaryDirectory parent.

The runner exists so that the test run has a *recorded* cleanup story:

* the pytest ``--basetemp`` is placed inside a fresh ``TemporaryDirectory``
  that this runner owns,
* the exact command line, exit code, stdout, stderr and wall time are
  captured verbatim into ``raw/``,
* after the ``TemporaryDirectory`` context has exited, the runner records
  whether the parent directory still exists.

No pre-existing or shared pytest root is deleted.  The runner only ever
removes the temporary directory that it created itself.

Usage::

    python3 run_tests.py            # run the suite once
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"
RAW = HERE / "raw"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    summary = {
        "kind": "S3_PREP_INDEPENDENT_PROCESS_CORRECTION_TEST_RUN",
        "runner": str(Path(__file__).resolve()),
        "python": sys.version,
        "pytest_root": str(TESTS),
    }
    with tempfile.TemporaryDirectory(prefix="lvw-process-correction-") as parent:
        parent_path = Path(parent)
        basetemp = parent_path / "pytest-base"
        command = [
            sys.executable,
            "-m",
            "pytest",
            str(TESTS),
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(basetemp),
        ]
        summary["command"] = command
        summary["basetemp_parent"] = str(parent_path)
        summary["basetemp"] = str(basetemp)
        summary["parent_exists_during_run"] = parent_path.is_dir()
        started = time.monotonic()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
        elapsed = round(time.monotonic() - started, 3)
        summary["exit_code"] = proc.returncode
        summary["elapsed_seconds"] = elapsed
        (RAW / "pytest.stdout.log").write_text(proc.stdout, encoding="utf-8")
        (RAW / "pytest.stderr.log").write_text(proc.stderr, encoding="utf-8")
        (RAW / "pytest.exit.log").write_text("%d\n" % proc.returncode, encoding="utf-8")
        (RAW / "pytest.time").write_text("%.3f\n" % elapsed, encoding="utf-8")
        summary["environment_overrides"] = {"PYTHONDONTWRITEBYTECODE": "1"}
        summary["pytest_argv_semantics"] = (
            "-q (quiet) -p no:cacheprovider (no .pytest_cache in the report tree) "
            "--basetemp <owned TemporaryDirectory>/pytest-base"
        )
        summary["stdout_bytes"] = len(proc.stdout.encode("utf-8"))
        summary["stderr_bytes"] = len(proc.stderr.encode("utf-8"))
    # the TemporaryDirectory context has exited here: the owned parent is gone
    summary["parent_exists_after_exit"] = parent_path.is_dir()
    summary["shared_pytest_roots_touched"] = []
    summary["old_pytest_roots_deleted"] = False
    (RAW / "test-run-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
