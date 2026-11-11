#!/usr/bin/env python3
"""independent-correction-01 独审：宿主 /tmp 历史残留的**只披露**记录。

按 correction-01 合同：
  "仅核实由本实现者此前创建且能以记录证明的精确临时根，才清理；不扫删 /tmp 前缀或未知目录，
   不能删除审查失败证据。无法证明所有权的遗留目录记限制即可，不阻止本轮代码安全修复。"

因此本脚本**只读取并记录**这些目录，绝不删除它们。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1]

RESIDUE_NAMES = [
    "lvw smoke 沙箱.McucN0",
    "lvw smoke 沙箱.tj7KZA",
    "lvw 离线包链路 15ar1jkf",
    "lvw 离线包链路 iupsl92p",
    "lvw 离线包链路 qcjychxp",
]


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE
    entries = []
    for name in RESIDUE_NAMES:
        path = Path("/tmp") / name
        if not path.exists():
            entries.append({"name": name, "exists": False})
            continue
        files = []
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames.sort()
            for filename in sorted(filenames):
                full = Path(dirpath, filename)
                files.append({
                    "relative_path": full.relative_to(path).as_posix(),
                    "size_bytes": full.stat().st_size,
                    "sha256": hashlib.sha256(full.read_bytes()).hexdigest(),
                })
        stat = path.stat()
        entries.append({
            "name": name,
            "exists": True,
            "file_count": len(files),
            "dir_count": sum(1 for p in path.rglob("*") if p.is_dir()),
            "total_bytes": sum(f["size_bytes"] for f in files),
            "mtime_epoch": int(stat.st_mtime),
            "mode": oct(stat.st_mode & 0o777),
            "files": files,
        })
    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_TMP_RESIDUE_DISCLOSURE",
        "disclosure_only": True,
        "deleted_by_independent_reviewer": False,
        "blocking_candidate": False,
        "rationale": (
            "这些是实现者此前链路执行器遗留的宿主 /tmp 目录。独审无法以记录证明其所有权"
            "（原 independent-01 的 m-02 已记录同一根因：清理是 execute() 的最后一句，"
            "异常路径会跳过）。按 correction-01 合同「仅核实由本实现者此前创建且能以记录证明的"
            "精确临时根，才清理；不扫删 /tmp 前缀或未知目录」，本轮只披露、不删除、不阻断候选。"
        ),
        "count": len(entries),
        "entries": entries,
    }
    (out_dir / "tmp-residue-disclosure.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "count": len(entries),
        "entries": [{"name": e["name"], "file_count": e.get("file_count"),
                     "total_bytes": e.get("total_bytes")} for e in entries],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
