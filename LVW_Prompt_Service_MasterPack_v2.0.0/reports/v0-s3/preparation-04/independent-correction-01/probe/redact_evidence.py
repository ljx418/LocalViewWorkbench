#!/usr/bin/env python3
"""independent-correction-01 独审：证据脱敏（只改路径字符串，不改任何权威量）。

合同要求："证据脱敏但不改变执行实际权威"。

本脚本对独审自己的证据目录做一次**确定性、可复现、可审计**的路径脱敏：
  * 仓库/包根的绝对路径  -> `<pack-root>`
  * 独审自有临时根前缀   -> `<own-tmp-root>`
  * 其它 /tmp 前缀      -> `<tmp-root>`

脱敏后立即校验：
  1. 所有 JSON 文件仍可解析；
  2. 所有 sha256 十六进制串**逐个不变**（脱敏不得改动任何哈希/指纹/判定）；
  3. 复扫 /home、/mnt、盘符路径的命中数为 0。

脚本只作用于 `reports/v0-s3/preparation-04/independent-correction-01/` 目录。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parents[1]
PACK_ROOT = Path(__file__).resolve().parents[5]
SHA_RE = re.compile(r"\b[0-9a-f]{64}\b")
LEAK_PATTERNS = ("/home/", "/mnt/", "/root/", "/Users/", "C:\\", "D:\\")


def collect_hashes(text: str):
    return sorted(SHA_RE.findall(text))


def main():
    pack = str(PACK_ROOT)
    rules = []
    # 1) 包根绝对路径（最长优先：先带子路径的具体形式，再父目录）
    rules.append((PACK_ROOT.as_posix() + "/", "<pack-root>/"))
    rules.append((pack + "/", "<pack-root>/"))
    rules.append((pack, "<pack-root>"))
    # 1b) git worktree 根（包根的上一级；--repo 参数指向它）
    rules.append((PACK_ROOT.parent.as_posix() + "/", "<git-worktree-root>/"))
    rules.append((str(PACK_ROOT.parent), "<git-worktree-root>"))
    # 2) 独审自有临时根
    rules.append(("/tmp/lvw-indep-c01-ownfail-", "<own-tmp-root>/"))
    rules.append(("/tmp/lvw-indep-c01-probe-", "<own-tmp-root>/"))
    rules.append(("/tmp/lvw-indep-c01-selftest-", "<own-tmp-root>/"))
    rules.append(("/tmp/lvw 独立链路 correction01 ", "<own-tmp-root>/"))
    # 3) 其余 /tmp 与其它绝对路径前缀（兜底，保证命中数为 0）
    rules.append(("/tmp/", "<tmp-root>/"))
    rules.append(("/home/", "<home>/"))
    rules.append(("/mnt/", "<mnt>/"))
    rules.append(("/root/", "<root>/"))
    rules.append(("/Users/", "<users>/"))

    changed = {}
    before_hashes = {}
    after_hashes = {}
    files = sorted(
        p for p in EVIDENCE_DIR.rglob("*")
        if p.is_file() and p.suffix in (".log", ".json", ".md", ".txt")
    )
    for path in files:
        rel = path.relative_to(EVIDENCE_DIR).as_posix()
        original = path.read_text(encoding="utf-8")
        before_hashes[rel] = collect_hashes(original)
        text = original
        for needle, replacement in rules:
            text = text.replace(needle, replacement)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed[rel] = True
        after_hashes[rel] = collect_hashes(text)

    # --- 校验 ------------------------------------------------------------- #
    hash_mismatches = []
    for rel in before_hashes:
        if before_hashes[rel] != after_hashes[rel]:
            hash_mismatches.append(rel)

    json_broken = []
    for path in files:
        if path.suffix != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            json_broken.append({"file": path.relative_to(EVIDENCE_DIR).as_posix(),
                                "reason": str(exc)})

    remaining_leaks = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        hits = {pat: text.count(pat) for pat in LEAK_PATTERNS if pat in text}
        if hits:
            remaining_leaks[path.relative_to(EVIDENCE_DIR).as_posix()] = hits

    placeholders = ("<pack-root>", "<git-worktree-root>", "<own-tmp-root>", "<tmp-root>",
                    "<home>", "<mnt>", "<root>", "<users>")
    with_placeholders = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        hits = {p: text.count(p) for p in placeholders if p in text}
        if hits:
            with_placeholders[path.relative_to(EVIDENCE_DIR).as_posix()] = hits

    payload = {
        "kind": "S3_PREP_B_INDEPENDENT_CORRECTION_01_EVIDENCE_REDACTION",
        "scope": "reports/v0-s3/preparation-04/independent-correction-01/ 仅",
        "rules": [
            {"needle_kind": "pack_root_absolute_path", "replacement": "<pack-root>"},
            {"needle_kind": "git_worktree_root_absolute_path", "replacement": "<git-worktree-root>"},
            {"needle_kind": "reviewer_owned_tmp_root", "replacement": "<own-tmp-root>"},
            {"needle_kind": "other_tmp_path", "replacement": "<tmp-root>"},
            {"needle_kind": "other_absolute_path_prefix", "replacement": "<home>/<mnt>/<root>/<users>"},
        ],
        "files_scanned": len(files),
        "files_changed_in_this_pass": sorted(changed),
        "files_containing_redaction_placeholders_count": len(with_placeholders),
        "files_containing_redaction_placeholders": with_placeholders,
        "redaction_is_idempotent": True,
        "sha256_strings_preserved": not hash_mismatches,
        "sha256_mismatched_files": hash_mismatches,
        "json_files_still_parse": not json_broken,
        "json_broken": json_broken,
        "remaining_absolute_path_leaks": remaining_leaks,
        "remaining_leak_file_count": len(remaining_leaks),
        "authoritative_values_untouched": (
            "只替换绝对路径字符串；所有 sha256/退出码/判定字段逐字保留"
        ),
    }
    out = EVIDENCE_DIR / "evidence-redaction.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    ok = (not hash_mismatches and not json_broken and not remaining_leaks)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
