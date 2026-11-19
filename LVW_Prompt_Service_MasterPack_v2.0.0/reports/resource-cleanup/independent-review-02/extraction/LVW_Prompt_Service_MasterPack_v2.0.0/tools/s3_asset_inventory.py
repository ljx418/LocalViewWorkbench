#!/usr/bin/env python3
"""Bounded, authorised local asset inventory for the V0-S3 preparation window.

The inventory is a *read-only metadata* pass over the single approved local
root declared by ``reports/v0-s3/preparation-03/asset-inventory-child.json``.
It performs ``stat`` + SHA-256 + relative path + extension only.  It never
decodes media, never extracts EXIF, never launches a subprocess, never uses a
model, a provider, the network, a browser or a decoder, and never writes to
the source root.

Order of operations is a hard requirement:

1. validate the preflight binding (candidate / script / child / approval /
   frozen proof hashes) against the *actual* files,
2. run the real handoff guard (``tools/verify_s3_handoff.py``) - any refusal
   happens **before** a single byte of source media is stat'ed or read,
3. only then walk and hash the approved root, under hard budgets.

Usage (frozen by ``.agent-governance/stages/V0-S3/stage-control.json``)::

    python3 -B tools/s3_asset_inventory.py \\
        --binding reports/v0-s3/preparation-03/implementation/inventory-01/preflight.json \\
        --receipt reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json

The CLI exposes no root, no limit and no pin override: those exist only as
library arguments used by the test suite and are reported as non-authority
when they differ from the frozen production values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import verify_s3_handoff as guard  # noqa: E402

ROOT = HERE.parent

CHILD_REL = "reports/v0-s3/preparation-03/asset-inventory-child.json"
REPORT_ROOT_REL = "reports/v0-s3/preparation-03/implementation"
HOLDOUT_REL = "人工验收视频集/FREEZE.json"
HANDOFF_REL = "tools/verify_s3_handoff.py"
INVENTORY_REL = "tools/s3_asset_inventory.py"

# Frozen copy of the child authorisation limits and extension allow-list.  The
# inventory re-checks the child file against these values so that a tampered
# child cannot widen the budget or the file types it accepts.
EXPECTED_LIMITS = {
    "wall_seconds": 180,
    "max_regular_files_examined": 2048,
    "max_files_hashed": 512,
    "max_total_bytes_hashed": 8589934592,
    "max_single_file_bytes": 536870912,
    "read_chunk_bytes": 1048576,
    "max_directory_entries": 8192,
}
EXPECTED_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".webm", ".avi",
)
EXPECTED_CHILD_KIND = "BOUNDED_S3_PREPARATION_CHILD_DERIVED_FROM_EXISTING_COMPLETE03"
REQUIRED_PREFLIGHT_FIELDS = (
    "candidate_sha",
    "inventory_script_sha256",
    "handoff_script_sha256",
    "inventory_child_sha256",
    "scope_approval_sha256",
    "frozen_proof_hashes",
)

PRODUCTION_PINS = {
    "child": dict(guard.CHILD_PIN),
    "proofs": dict(guard.PROOF_PINS),
}


class WallBudgetExceeded(Exception):
    """Raised when the wall-clock budget is exhausted, including inside hashing."""


class TotalBytesExceeded(Exception):
    """Raised when the total hashed byte budget would be exceeded."""


def sha256_file(path: Path, chunk_bytes: int, deadline: float, clock, already: int = 0,
                max_total: int = None) -> tuple:
    """Hash one file in bounded chunks, honouring the wall clock inside the read."""
    digest = hashlib.sha256()
    total = 0
    with open(path, "rb") as handle:
        while True:
            if clock() > deadline:
                raise WallBudgetExceeded(path.name)
            chunk = handle.read(chunk_bytes)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
            if max_total is not None and already + total > max_total:
                raise TotalBytesExceeded(path.name)
    return digest.hexdigest(), total


def within(path: str, root: str) -> bool:
    """True when ``path`` is the root itself or lives under it."""
    if path == root:
        return True
    return path.startswith(root.rstrip(os.sep) + os.sep)


def file_identity(relative_path: str, sha256: str) -> str:
    """Stable, content and path addressed identifier for one inventoried file."""
    payload = "lvw.s3.inventory.v1|%s|%s" % (relative_path, sha256)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_holdouts(package_root: Path) -> dict:
    """Read the 11 protected human holdout hashes (metadata only, no media read)."""
    path = package_root / HOLDOUT_REL
    if not path.is_file():
        return {"available": False, "reason": "holdout freeze file not present"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": "holdout freeze file unreadable: %s" % exc}
    videos = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(videos, list):
        return {"available": False, "reason": "holdout freeze file has no videos list"}
    return {
        "available": True,
        "freeze_file_sha256": guard.sha256_file(path),
        "holdouts": [
            {"id": item.get("id"), "sha256": item.get("video_sha256")}
            for item in videos
            if isinstance(item, dict)
        ],
    }


def collect(root: Path, limits: dict, extensions, clock, deadline: float) -> dict:
    """Walk and hash the approved root under hard budgets."""
    state = {
        "entries_examined": 0,
        "regular_files_examined": 0,
        "files_hashed": 0,
        "total_bytes_hashed": 0,
        "stop_reason": None,
    }
    eligible = []
    skipped = []
    reasons = {}

    def skip(relative: str, reason: str, detail: str = "") -> None:
        reasons[reason] = reasons.get(reason, 0) + 1
        record = {"relative_path": relative, "reason": reason}
        if detail:
            record["detail"] = detail
        skipped.append(record)

    root_real = os.path.realpath(root)
    stack = [str(root)]
    while stack:
        if clock() > deadline:
            state["stop_reason"] = "wall_budget_exhausted_during_traversal"
            break
        current = stack.pop()
        try:
            scanner = os.scandir(current)
        except OSError as exc:
            skip(os.path.relpath(current, root), "unreadable_directory", str(exc))
            continue
        with scanner:
            for entry in scanner:
                if clock() > deadline:
                    state["stop_reason"] = "wall_budget_exhausted_during_traversal"
                    break
                if state["entries_examined"] >= limits["max_directory_entries"]:
                    state["stop_reason"] = "directory_entry_budget_exhausted"
                    break
                state["entries_examined"] += 1
                path = entry.path
                relative = os.path.relpath(path, root)
                if entry.is_symlink():
                    target = os.path.realpath(path)
                    reason = (
                        "symlink_escape_rejected"
                        if not within(target, root_real)
                        else "symlink_not_followed"
                    )
                    skip(relative, reason)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    skip(relative, "unsupported_file_type")
                    continue
                if state["regular_files_examined"] >= limits["max_regular_files_examined"]:
                    state["stop_reason"] = "regular_file_budget_exhausted"
                    break
                state["regular_files_examined"] += 1
                extension = os.path.splitext(entry.name)[1].lower()
                if extension not in extensions:
                    skip(relative, "unsupported_extension")
                    continue
                try:
                    before = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    skip(relative, "stat_failed", str(exc))
                    continue
                if before.st_size > limits["max_single_file_bytes"]:
                    skip(relative, "single_file_over_budget")
                    continue
                if state["files_hashed"] >= limits["max_files_hashed"]:
                    skip(relative, "hash_budget_exhausted")
                    continue
                if (
                    state["total_bytes_hashed"] + before.st_size
                    > limits["max_total_bytes_hashed"]
                ):
                    skip(relative, "total_bytes_budget_exhausted")
                    continue
                if not within(os.path.realpath(path), root_real):
                    skip(relative, "path_escape_rejected")
                    continue
                try:
                    digest, read_bytes = sha256_file(
                        Path(path),
                        limits["read_chunk_bytes"],
                        deadline,
                        clock,
                        already=state["total_bytes_hashed"],
                        max_total=limits["max_total_bytes_hashed"],
                    )
                except WallBudgetExceeded:
                    state["stop_reason"] = "wall_budget_exhausted_during_hashing"
                    break
                except TotalBytesExceeded:
                    skip(relative, "total_bytes_budget_exhausted")
                    continue
                except OSError as exc:
                    skip(relative, "read_failed", str(exc))
                    continue
                try:
                    after = os.stat(path, follow_symlinks=False)
                except OSError as exc:
                    skip(relative, "stat_failed_after_read", str(exc))
                    continue
                before_state = (before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev)
                after_state = (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev)
                if before_state != after_state:
                    skip(relative, "changed_during_inventory")
                    continue
                state["files_hashed"] += 1
                state["total_bytes_hashed"] += read_bytes
                eligible.append(
                    {
                        "file_id": file_identity(relative, digest),
                        "relative_path": relative,
                        "extension": os.path.splitext(entry.name)[1],
                        "bytes": read_bytes,
                        "sha256": digest,
                        "origin": "unknown",
                        "rights": "unknown",
                        "labels": "unknown",
                    }
                )
        if state["stop_reason"]:
            break

    return {
        "state": state,
        "eligible": eligible,
        "skipped": skipped,
        "skipped_by_reason": reasons,
    }


def _reject(receipt: dict, reason: str, detail: str) -> dict:
    receipt["decision"] = "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    receipt["refusal"] = {"reason": reason, "detail": detail}
    receipt["media_access"] = {
        "entries_examined": 0,
        "regular_files_examined": 0,
        "files_hashed": 0,
        "total_bytes_hashed": 0,
        "media_bytes_read": 0,
        "traversal_stop_reason": None,
    }
    receipt["counts"] = {"eligible": 0, "skipped": 0, "skipped_by_reason": {}, "eligible_bytes": 0}
    receipt["items"] = []
    receipt["skipped_items"] = []
    return receipt


def run_inventory(*, binding_path, receipt_path, package_root: Path = ROOT,
                  guard_root: Path = None, child_path: Path = None, pins: dict = None,
                  report_root: Path = None, clock=time.monotonic) -> dict:
    """Execute one bounded inventory attempt and build the terminal receipt."""
    package_root = Path(package_root)
    pins = pins if pins is not None else PRODUCTION_PINS
    child_path = Path(child_path) if child_path else package_root / CHILD_REL
    guard_root = Path(guard_root) if guard_root else package_root
    report_root = Path(report_root) if report_root else package_root / REPORT_ROOT_REL
    binding_path = Path(binding_path)
    receipt_path = Path(receipt_path)

    started = clock()
    receipt = {
        "kind": "S3_BOUNDED_ASSET_INVENTORY_TERMINAL_RECEIPT",
        "scope": "HANDOFF_READINESS_ONLY",
        "authority": "AUTHORITATIVE",
        "product_gate0": False,
        "stage_pass_claim": False,
        "samples_frozen": False,
        "quality_claim": "NONE_INVENTORY_IS_NOT_QUALITY_EVIDENCE",
        "media_analysis": "stat_and_sha256_only_no_decode_no_exif_no_probe",
        "budgets": {
            "model_actions": 0,
            "effective_full_checkpoints": 0,
            "product_runtime_seconds": 0,
            "service_starts": 0,
            "network_calls": 0,
            "subprocess_starts": 0,
        },
        "code_binding": {},
        "child_binding": {},
        "guard": {},
    }
    canonical = (
        Path(os.path.abspath(str(child_path)))
        == Path(os.path.abspath(str(package_root / CHILD_REL)))
        and Path(os.path.abspath(str(guard_root))) == Path(os.path.abspath(str(package_root)))
        and pins == PRODUCTION_PINS
    )
    receipt["authority"] = "AUTHORITATIVE" if canonical else "FIXTURE_NON_AUTHORITY"

    # 0. the receipt is a terminal artefact: never overwrite or reuse one.
    receipt_abs = Path(os.path.abspath(str(receipt_path)))
    report_root_abs = Path(os.path.abspath(str(report_root)))
    receipt["write_receipt"] = True
    if receipt_abs.exists():
        receipt = _reject(
            receipt,
            "terminal_receipt_already_exists",
            "refusing to overwrite an existing terminal receipt: %s" % receipt_path,
        )
        receipt["write_receipt"] = False
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    try:
        receipt_abs.relative_to(report_root_abs)
    except ValueError:
        receipt = _reject(
            receipt,
            "receipt_outside_report_root",
            "receipt must stay under %s" % report_root,
        )
        receipt["write_receipt"] = False
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt

    # 1. preflight binding.
    if not binding_path.is_file():
        receipt = _reject(receipt, "binding_missing", "no binding file at %s" % binding_path)
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        receipt = _reject(receipt, "binding_malformed_json", str(exc))
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not isinstance(binding, dict):
        receipt = _reject(receipt, "binding_malformed_container", "binding is not a JSON object")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    missing = [field for field in REQUIRED_PREFLIGHT_FIELDS if field not in binding]
    if missing:
        receipt = _reject(
            receipt, "binding_missing_fields", "missing required fields: %r" % (missing,)
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt

    receipt["code_binding"] = {
        "candidate_sha": binding.get("candidate_sha"),
        "inventory_script_sha256": binding.get("inventory_script_sha256"),
        "handoff_script_sha256": binding.get("handoff_script_sha256"),
    }

    # 2. bind the current code, the child and the approval before any media access.
    inventory_script = package_root / INVENTORY_REL
    handoff_script = package_root / HANDOFF_REL
    actual = {
        "inventory_script_sha256": guard.sha256_file(inventory_script)
        if inventory_script.is_file()
        else None,
        "handoff_script_sha256": guard.sha256_file(handoff_script)
        if handoff_script.is_file()
        else None,
        "inventory_child_sha256": guard.sha256_file(child_path)
        if child_path.is_file()
        else None,
        "scope_approval_sha256": guard.sha256_file(package_root / pins["proofs"]["scope_approval"]["path"])
        if (package_root / pins["proofs"]["scope_approval"]["path"]).is_file()
        else None,
    }
    expected = {
        "inventory_script_sha256": binding.get("inventory_script_sha256"),
        "handoff_script_sha256": binding.get("handoff_script_sha256"),
        "inventory_child_sha256": pins["child"]["sha256"],
        "scope_approval_sha256": pins["proofs"]["scope_approval"]["sha256"],
    }
    mismatched = [
        "%s expected=%s actual=%s" % (key, expected[key], actual[key])
        for key in sorted(expected)
        if actual[key] != expected[key]
    ]
    if not re.fullmatch(r"[0-9a-f]{40}", str(binding.get("candidate_sha") or "")):
        mismatched.append("candidate_sha is not a 40 character git object id")
    if binding.get("inventory_child_sha256") != actual["inventory_child_sha256"]:
        mismatched.append("binding.inventory_child_sha256 does not match the child file")
    if binding.get("scope_approval_sha256") != actual["scope_approval_sha256"]:
        mismatched.append("binding.scope_approval_sha256 does not match the approval file")
    if binding.get("frozen_proof_hashes") != pins["proofs"]:
        mismatched.append("binding.frozen_proof_hashes does not match the frozen proof pins")
    if mismatched:
        receipt = _reject(receipt, "binding_mismatch", "; ".join(mismatched))
        receipt["code_binding"]["observed"] = actual
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    receipt["code_binding"]["observed"] = actual

    # 3. the real handoff guard runs BEFORE any stat/read of source media.
    guard_pins = {
        "proofs": pins["proofs"],
        "decision": guard.DECISION_PIN,
        "child": pins["child"],
        "spec_manifest": guard.PRODUCTION_PINS["spec_manifest"],
        "payload_manifest": guard.PRODUCTION_PINS["payload_manifest"],
    }
    guard_result = guard.evaluate(guard_root, pins=guard_pins)
    receipt["guard"] = {
        "decision": guard_result["decision"],
        "authority": guard_result["authority"],
        "summary": guard_result["summary"],
        "failed_checks": [item["id"] for item in guard_result["checks"] if not item["passed"]],
    }
    if guard_result["decision"] != "HANDOFF_READINESS_VERIFIED":
        receipt = _reject(
            receipt,
            "handoff_guard_rejected",
            "handoff guard did not verify: %r" % receipt["guard"]["failed_checks"],
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt

    # 4. the child authorisation: exact root, exact limits, exact extensions.
    try:
        child = json.loads(child_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        receipt = _reject(receipt, "child_malformed_json", str(exc))
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not isinstance(child, dict) or child.get("kind") != EXPECTED_CHILD_KIND:
        receipt = _reject(receipt, "child_kind_mismatch", "unexpected child kind")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    limits = child.get("limits")
    extensions = child.get("allowed_extensions")
    roots = child.get("allowed_roots")
    # The canonical child must carry the frozen limits and extension allow-list.
    # A fixture child (non canonical tree, injected pins) may carry smaller
    # budgets; such a run is reported as non-authority.
    if canonical and limits != EXPECTED_LIMITS:
        receipt = _reject(
            receipt, "child_limits_mismatch", "child limits differ from the frozen child limits"
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if canonical and tuple(extensions or ()) != EXPECTED_EXTENSIONS:
        receipt = _reject(
            receipt, "child_extensions_mismatch", "child extension allow-list differs"
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not isinstance(limits, dict) or not isinstance(extensions, list) or not extensions:
        receipt = _reject(receipt, "child_limits_mismatch", "child limits or extensions are unusable")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if child.get("scope_approval_sha256") != pins["proofs"]["scope_approval"]["sha256"]:
        receipt = _reject(receipt, "child_approval_mismatch", "child scope approval pin differs")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not isinstance(roots, list) or len(roots) != 1:
        receipt = _reject(
            receipt, "child_roots_mismatch", "the child must declare exactly one approved root"
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    root_entry = roots[0]
    receipt["child_binding"] = {
        "child_sha256": actual["inventory_child_sha256"],
        "scope_approval_sha256": actual["scope_approval_sha256"],
        "root_alias": root_entry.get("alias"),
        "permission": root_entry.get("permission"),
        "limits": limits,
        "allowed_extensions": list(extensions),
    }

    source_root = Path(root_entry.get("wsl_path", ""))
    if not source_root.is_absolute():
        receipt = _reject(receipt, "root_not_absolute", "the approved root must be an absolute path")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not source_root.exists():
        receipt = _reject(
            receipt, "root_missing", "the approved root does not exist on this machine"
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    if not source_root.is_dir():
        receipt = _reject(receipt, "root_not_a_directory", "the approved root is not a directory")
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt
    root_real = Path(os.path.realpath(source_root))
    if os.path.islink(str(source_root)):
        receipt = _reject(
            receipt, "root_is_symlink", "the approved root itself is a symbolic link"
        )
        receipt["elapsed_seconds"] = round(clock() - started, 3)
        return receipt

    # 5. the bounded walk.
    deadline = started + float(limits["wall_seconds"])
    outcome = collect(root_real, limits, set(extensions), clock, deadline)
    state = outcome["state"]
    eligible = outcome["eligible"]
    skipped = outcome["skipped"]

    holdouts = load_holdouts(package_root)
    holdout_by_sha = {}
    if holdouts.get("available"):
        for holdout in holdouts["holdouts"]:
            if holdout.get("sha256"):
                holdout_by_sha.setdefault(holdout["sha256"], []).append(holdout.get("id"))
    overlaps = [
        {"relative_path": item["relative_path"], "sha256": item["sha256"], "holdout_ids": holdout_by_sha[item["sha256"]]}
        for item in eligible
        if item["sha256"] in holdout_by_sha
    ]

    receipt["media_access"] = {
        "entries_examined": state["entries_examined"],
        "regular_files_examined": state["regular_files_examined"],
        "files_hashed": state["files_hashed"],
        "total_bytes_hashed": state["total_bytes_hashed"],
        "media_bytes_read": state["total_bytes_hashed"],
        "traversal_stop_reason": state["stop_reason"],
        "wall_budget_seconds": limits["wall_seconds"],
        "read_chunk_bytes": limits["read_chunk_bytes"],
        "extension_match": "case_insensitive_source_casing_preserved",
    }
    receipt["counts"] = {
        "eligible": len(eligible),
        "skipped": len(skipped),
        "skipped_by_reason": outcome["skipped_by_reason"],
        "eligible_bytes": sum(item["bytes"] for item in eligible),
    }
    receipt["items"] = eligible
    receipt["skipped_items"] = skipped
    receipt["holdout_overlap"] = {
        "holdouts_checked": len(holdout_by_sha),
        "freeze_file_sha256": holdouts.get("freeze_file_sha256"),
        "sha256_matches": overlaps,
        "note": "11 protected human holdouts are compared by hash only; no holdout media was "
                "read and no holdout was fed to any model.",
    }
    receipt["unknown_coverage"] = [
        "origin of every inventoried file is unknown (no EXIF or provenance metadata is read)",
        "rights and redistribution licence are unknown; user supplied non-private test use "
        "authority is not a redistribution licence",
        "content labels, quality scores and sample usability are unknown; an inventory entry is "
        "never a quality PASS",
        "no sample is frozen by this inventory and no disjointness against the future S3 quality "
        "set, V1 Q01 set or MS sets is proven",
        "only %s was inspected; every other local root stays unread" % root_real.name,
    ]
    receipt["cleanup"] = {
        "source_files_modified": 0,
        "source_files_deleted": 0,
        "temporary_directories_created": 0,
        "deletions_performed": 0,
        "policy": "read-only source; the inventory creates no temporary directory and never "
                  "deletes anything; only owned test TemporaryDirectory fixtures are cleaned",
    }
    receipt["limitations"] = [
        "stat + SHA-256 + relative path + extension only; no decode, no EXIF, no visual analysis",
        "no model, provider, GPU, network, download, service, browser or decoder was used",
        "a partial or budget-exhausted inventory is still a terminal receipt and is not retried",
    ]
    receipt["elapsed_seconds"] = round(clock() - started, 3)
    receipt["decision"] = (
        "INVENTORY_COMPLETE"
        if state["stop_reason"] is None
        else "INVENTORY_PARTIAL_BUDGET_EXHAUSTED"
    )
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded authorised local asset inventory (V0-S3 preparation only)."
    )
    parser.add_argument("--binding", required=True, help="preflight binding JSON")
    parser.add_argument("--receipt", required=True, help="terminal receipt JSON to write")
    args = parser.parse_args(argv)

    receipt = run_inventory(
        binding_path=Path(args.binding),
        receipt_path=Path(args.receipt),
    )
    receipt_path = Path(args.receipt)
    if receipt.get("write_receipt", True):
        try:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            print("failed to write terminal receipt: %s" % exc, file=sys.stderr)
            return 1
    summary = {
        "decision": receipt.get("decision"),
        "authority": receipt.get("authority"),
        "elapsed_seconds": receipt.get("elapsed_seconds"),
        "counts": receipt.get("counts"),
        "media_access": receipt.get("media_access"),
        "guard": receipt.get("guard"),
        "receipt": str(args.receipt),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if receipt.get("decision") in (None, "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"):
        print("refusal: %s" % json.dumps(receipt.get("refusal"), ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
