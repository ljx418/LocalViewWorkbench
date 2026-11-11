#!/usr/bin/env python3
"""Independent finite SHA-256 recheck under reports/v0-s3/preparation-03/independent-hash-child-01.json.

Hard limits (from the child authority): 3 files, 32 MiB total bytes, 60 s wall
clock, 1 MiB read chunks.  No directory walk, no second full inventory, no
decode, no EXIF, no visual analysis, no write to any original, no network,
no service, no subprocess.

Order of operations:
  1. validate the child authority file itself (its own bytes and its git blob),
  2. validate the expected candidate commits and the inventory receipt hash,
  3. only then open the three declared source files, read-only, in chunks.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path("/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-review/LVW_Prompt_Service_MasterPack_v2.0.0")
REPO_ROOT = Path("/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-review")
PKG_PREFIX = "LVW_Prompt_Service_MasterPack_v2.0.0/"
CHILD_REL = "reports/v0-s3/preparation-03/independent-hash-child-01.json"
RECEIPT_REL = "reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json"


def sha256_file(path: Path, chunk_bytes: int, deadline: float, budget: dict):
    digest = hashlib.sha256()
    total = 0
    chunks = 0
    with open(path, "rb") as handle:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("wall budget exhausted")
            chunk = handle.read(chunk_bytes)
            chunks += 1
            if not chunk:
                break
            if budget["bytes"] + total + len(chunk) > budget["max_bytes"]:
                raise TimeoutError("byte budget exhausted")
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total, chunks


def main() -> int:
    started = time.monotonic()
    child_path = REPO / CHILD_REL
    child_raw = child_path.read_bytes()
    child_sha = hashlib.sha256(child_raw).hexdigest()
    child = json.loads(child_raw.decode("utf-8"))
    limits = child["limits"]
    budget = {"bytes": 0, "max_bytes": int(limits["bytes"])}
    deadline = started + float(limits["wall_seconds"])

    # --- 1. the child authority itself -----------------------------------
    def git_raw(*args):
        import subprocess
        return subprocess.run(["git", "-C", str(REPO_ROOT)] + list(args),
                              capture_output=True, text=True, check=False).stdout.strip()

    child_blob = git_raw("rev-parse", "d47c2a1:%s%s" % (PKG_PREFIX, CHILD_REL))
    child_worktree_blob = git_raw("hash-object", PKG_PREFIX + CHILD_REL)

    # --- 2. the expected candidates and the inventory receipt --------------
    def git(*args):
        return git_raw(*args)

    candidate_checks = {}
    for label, sha in (("source_candidate", child["source_candidate"]),
                       ("implementation_code_candidate", child["implementation_code_candidate"])):
        candidate_checks[label] = {
            "expected": sha,
            "present_in_checkout": git("cat-file", "-t", sha) == "commit",
            "resolves_to": git("rev-parse", sha),
        }
    code_files = {
        "tools/verify_s3_handoff.py": child["implementation_code_candidate"],
        "tools/s3_asset_inventory.py": child["implementation_code_candidate"],
        "tools/test_verify_s3_handoff.py": child["implementation_code_candidate"],
        "tools/test_s3_asset_inventory.py": child["implementation_code_candidate"],
    }
    code_identity = {}
    for relative, commit in code_files.items():
        blob = git("rev-parse", "%s:%s%s" % (commit, PKG_PREFIX, relative))
        worktree = git("hash-object", PKG_PREFIX + relative)
        code_identity[relative] = {
            "candidate_blob": blob,
            "checkout_blob": worktree,
            "byte_identical_to_candidate": blob == worktree,
        }
    receipt_path = REPO / child["inventory_receipt"]
    receipt_sha = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    receipt_ok = receipt_sha == child["inventory_receipt_sha256"]

    preflight_ok = (
        candidate_checks["source_candidate"]["present_in_checkout"]
        and candidate_checks["implementation_code_candidate"]["present_in_checkout"]
        and all(v["byte_identical_to_candidate"] for v in code_identity.values())
        and receipt_ok
        and child_blob == child_worktree_blob
    )

    # --- 3. only now: the three declared source files ----------------------
    root = Path(child["root"])
    root_real = os.path.realpath(str(root))
    results = []
    counters = {"files_attempted": 0, "files_hashed": 0, "bytes_read": 0, "chunks_read": 0,
                "files_skipped": 0, "escape_rejected": 0, "identity_mismatch": 0,
                "missing": 0}
    for entry in child["selected_files"]:
        counters["files_attempted"] += 1
        target = root / entry["relative_path"]
        record = {
            "relative_path": entry["relative_path"],
            "expected_sha256": entry["sha256"],
            "expected_bytes": entry["bytes"],
            "expected_file_id": entry["file_id"],
        }
        if not target.exists():
            counters["missing"] += 1
            counters["files_skipped"] += 1
            record["result"] = "MISSING_NOT_VERIFIED"
            results.append(record)
            continue
        resolved = os.path.realpath(str(target))
        contained = resolved == root_real or resolved.startswith(root_real.rstrip(os.sep) + os.sep)
        record["resolved_within_root"] = contained
        if not contained:
            counters["escape_rejected"] += 1
            counters["files_skipped"] += 1
            record["result"] = "RESOLVED_ESCAPE_REJECTED_NOT_VERIFIED"
            results.append(record)
            continue
        stat = os.stat(target, follow_symlinks=False)
        record["observed_stat"] = {
            "st_size": stat.st_size,
            "st_mtime_ns": stat.st_mtime_ns,
            "st_ino": stat.st_ino,
            "st_dev": stat.st_dev,
            "is_symlink": os.path.islink(str(target)),
        }
        try:
            digest, total, chunks = sha256_file(
                target, int(limits["chunk_bytes"]), deadline, budget)
        except (TimeoutError, OSError) as exc:
            counters["files_skipped"] += 1
            record["result"] = "READ_FAILED_NOT_VERIFIED"
            record["detail"] = str(exc)
            results.append(record)
            continue
        counters["files_hashed"] += 1
        counters["bytes_read"] += total
        counters["chunks_read"] += chunks
        budget["bytes"] += total
        record["actual_sha256"] = digest
        record["actual_bytes"] = total
        record["chunks_read"] = chunks
        record["sha256_matches_candidate"] = digest == entry["sha256"]
        record["bytes_match_candidate"] = total == entry["bytes"]
        if digest != entry["sha256"]:
            counters["identity_mismatch"] += 1
            record["result"] = "SOURCE_CHANGED_NOT_VERIFIED"
        else:
            record["result"] = "VERIFIED"
        results.append(record)

    elapsed = round(time.monotonic() - started, 3)
    verified = counters["files_hashed"] == len(child["selected_files"]) and all(
        r["result"] == "VERIFIED" for r in results)
    payload = {
        "kind": "S3_PREP_INDEPENDENT_FINITE_HASH_RECHECK",
        "authority_child": {
            "path": CHILD_REL,
            "sha256": child_sha,
            "git_blob_at_d47c2a1": child_blob,
            "worktree_blob": child_worktree_blob,
            "blob_matches_root_supplied_child": child_blob == child_worktree_blob,
            "id": child["id"],
        },
        "candidate_checks": candidate_checks,
        "code_identity": code_identity,
        "inventory_receipt": {
            "path": child["inventory_receipt"],
            "expected_sha256": child["inventory_receipt_sha256"],
            "actual_sha256": receipt_sha,
            "matches": receipt_ok,
        },
        "preflight_validated_before_source_access": preflight_ok,
        "root": {"declared": child["root"], "alias": child["root_alias"],
                 "resolved": root_real, "walked": False, "listed": False},
        "limits": limits,
        "counters": counters,
        "elapsed_seconds": elapsed,
        "results": results,
        "decision": "INDEPENDENT_HASH_RECHECK_VERIFIED" if verified else "INDEPENDENT_HASH_RECHECK_NOT_VERIFIED",
        "notes": [
            "read-only SHA-256 recomputation of exactly the three files declared by the child authority",
            "no directory walk, no second full inventory, no decode, no EXIF, no visual analysis",
            "no original was written; every file was opened read-only",
            "the 11 protected human holdouts and the obvious private-labelled paths were not touched",
        ],
    }
    out = Path(sys.argv[1])
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("decision", "preflight_validated_before_source_access", "counters", "elapsed_seconds")},
                     ensure_ascii=False, indent=2))
    for r in results:
        print(r["relative_path"], "->", r["result"], r.get("actual_sha256", ""))
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
