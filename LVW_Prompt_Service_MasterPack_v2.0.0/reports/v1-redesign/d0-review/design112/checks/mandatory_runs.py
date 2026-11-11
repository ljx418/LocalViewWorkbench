#!/usr/bin/env python3
"""Mandatory runs of the D0 checker and of the candidate test suite.

Both runs happen in a fresh ``tempfile.TemporaryDirectory`` root: the audited
tree is copied read only into the temporary root and every command runs
inside the copy. The audited tree is never used as a writable root.

The raw stdout, the raw stderr, the exit code and the sha256 of each are
written next to this script so that the receipt can bind them.

Usage:
    python3 -I mandatory_runs.py <package-root> <out-dir>
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(name, argv, cwd, out_dir):
    stdout_path = os.path.join(out_dir, "%s.stdout.log" % name)
    stderr_path = os.path.join(out_dir, "%s.stderr.log" % name)
    exit_path = os.path.join(out_dir, "%s.exit.log" % name)
    completed = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with open(stdout_path, "wb") as handle:
        handle.write(completed.stdout)
    with open(stderr_path, "wb") as handle:
        handle.write(completed.stderr)
    with open(exit_path, "w", encoding="utf-8") as handle:
        handle.write("%d\n" % completed.returncode)
    return {
        "command": " ".join(argv),
        "cwd": cwd,
        "exit_code": completed.returncode,
        "stdout_log": os.path.basename(stdout_path),
        "stderr_log": os.path.basename(stderr_path),
        "exit_log": os.path.basename(exit_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "exit_log_sha256": sha256_file(exit_path),
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
    }


def main(argv):
    if len(argv) < 3:
        sys.stderr.write("usage: mandatory_runs.py <package-root> <out-dir>\n")
        return 2
    source = os.path.abspath(argv[1])
    out_dir = os.path.abspath(argv[2])
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    results = []

    # 1. The frozen checker command, default pin, full capabilities.
    with tempfile.TemporaryDirectory(prefix="lvw-d0-review-checker-") as tmp:
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(source, pkg, symlinks=True)
        results.append(run(
            "mandatory-checker",
            [sys.executable, "-B", "tools/verify_v1_plan.py"],
            pkg,
            out_dir,
        ))

    # 2. The candidate test suite, in its own fresh root.
    with tempfile.TemporaryDirectory(prefix="lvw-d0-review-pytest-") as tmp:
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(source, pkg, symlinks=True)
        results.append(run(
            "mandatory-pytest",
            [sys.executable, "-B", "-m", "pytest", "tools/test_verify_v1_plan.py", "-q"],
            pkg,
            out_dir,
        ))

    for item in results:
        item["cwd"] = item["cwd"].replace(os.path.dirname(source), "<temp-root>")
    for item in results:
        sys.stdout.write("%s\n" % item["command"])
        sys.stdout.write("  exit=%d stdout_sha256=%s stderr_sha256=%s\n" % (
            item["exit_code"], item["stdout_sha256"], item["stderr_sha256"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
