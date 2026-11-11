#!/usr/bin/env python3
"""Reviewer-owned source fence for the D0-B-REVIEW design 1.1.2 recheck.

The fence covers, read only:

  * the 25 owner source files that the owner spec manifest fences
    (.agent-governance/stages/V1-D0/spec-manifest.json),
  * the 10 files of the D0 payload inventory
    (.agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256),
  * the two candidate code files (tools/verify_v1_plan.py and
    tools/test_verify_v1_plan.py),
  * the old R1 payload manifest and the three canonical contracts.

The tool never writes to the audited tree. It prints one
"<sha256>  <relative path>" line per fenced file, in a stable order, so that
two runs can be compared with a plain diff.

Usage:
    python3 -I fence.py <package-root> [output-file]
"""

import hashlib
import json
import os
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: fence.py <package-root> [output-file]\n")
        return 2
    root = os.path.abspath(argv[1])
    out_path = argv[2] if len(argv) > 2 else None

    spec_manifest_path = os.path.join(root, ".agent-governance/stages/V1-D0/spec-manifest.json")
    spec_manifest = json.loads(read_text(spec_manifest_path))
    owner_files = sorted(spec_manifest["files"].keys())

    d0_dir = ".agent-governance/stages/V1-D0"
    payload_manifest_path = os.path.join(root, d0_dir, "PAYLOAD_MANIFEST.sha256")
    payload_files = []
    for line in read_text(payload_manifest_path).splitlines():
        line = line.strip()
        if not line:
            continue
        payload_files.append("%s/%s" % (d0_dir, line.split(None, 1)[1].strip()))

    candidate_code = ["tools/verify_v1_plan.py", "tools/test_verify_v1_plan.py"]

    legacy = [".agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256"]
    canonical = ["contracts/openapi.json", "contracts/lvw.schema.json", "contracts/storage.sql"]

    # The owner inventory already carries the old R1 payload manifest and the
    # three canonical contracts; the extra lists above name them again so that
    # the fence states which surface it protects, but a file is hashed once.
    ordered = []
    for relative in owner_files + payload_files + candidate_code + legacy + canonical:
        if relative not in ordered:
            ordered.append(relative)

    lines = []
    missing = []
    for relative in ordered:
        absolute = os.path.join(root, relative)
        if not os.path.isfile(absolute):
            missing.append(relative)
            lines.append("MISSING  %s" % relative)
            continue
        lines.append("%s  %s" % (sha256_file(absolute), relative))

    text = "\n".join(lines) + "\n"
    if out_path:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    sys.stderr.write(
        "fence: owner=%d payload=%d candidate_code=%d legacy=%d canonical=%d missing=%d\n"
        % (len(owner_files), len(payload_files), len(candidate_code), len(legacy), len(canonical), len(missing))
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
