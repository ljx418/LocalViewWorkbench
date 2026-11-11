#!/usr/bin/env python3
"""Hash fence over the reviewed source set (read-only).

Usage: python3 -B hash_fence.py <output-file> <label>

Fences every file declared in .agent-governance/stages/V1-D0/spec-manifest.json
(17 pre-existing review files + 6 design1.1 additions = 23) plus the V1-D0
payload manifest and the canonical contract triple.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    out_file = Path(sys.argv[1])
    label = sys.argv[2]
    spec = json.loads((ROOT / ".agent-governance/stages/V1-D0/spec-manifest.json").read_text(encoding="utf-8"))
    lines = [f"# {label}", f"# generated_by reports/v1-redesign/d0-review/design11/checks/hash_fence.py", ""]
    mismatch = 0
    for rel, expected in spec["files"].items():
        actual = sha256_file(ROOT / rel)
        ok = actual == expected
        mismatch += 0 if ok else 1
        lines.append(f"{'OK  ' if ok else 'DIFF'} {actual}  {rel}")
    payload = ROOT / ".agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256"
    payload_sha = sha256_file(payload)
    lines.append(f"PAYLOAD_MANIFEST {payload_sha}  .agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256")
    legacy = json.loads((ROOT / "reports/v1-redesign/legacy-gates-before-change.json").read_text(encoding="utf-8"))
    for rel, expected in legacy["canonical_contract_hashes"].items():
        actual = sha256_file(ROOT / rel)
        ok = actual == expected
        mismatch += 0 if ok else 1
        lines.append(f"{'OK  ' if ok else 'DIFF'} {actual}  {rel}")
    lines.append("")
    lines.append(f"FENCED_FILES {len(spec['files'])}")
    lines.append(f"MISMATCH_COUNT {mismatch}")
    (OUT / out_file.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
