#!/usr/bin/env python3
"""Corrected independent finite hash recheck helper (reviewer-owned harness).

This file is a *process correction* of

    reports/v0-s3/preparation-03/independent-01/hash-recheck/hash-child-recheck.py

It is reviewer-owned test harness, NOT the application candidate and NOT a
product service.  It is not signed off as a Stage PASS by its author; the
root Codex reviewer inspects this code independently.

Why the original needed correction
-----------------------------------
The original helper computed ``preflight_ok`` and then wrote it into the
report as ``preflight_validated_before_source_access``, but the source read
loop was **not** gated on it.  Two of the three retained source passes
therefore hashed 11 009 275 real-media bytes each while their own preflight
was false (see ``independent-hash-process-deviation-01.json``).  On top of
that, every ``git`` call ran with ``check=False`` and never inspected the
process return code, and some paths were passed to ``git`` without the
repository package prefix, so a failed ``git rev-parse`` was silently
compared against the echoed argument instead of an object id.

What this copy changes
----------------------
* Every ``git`` invocation is checked for its **actual return code**; only a
  zero exit status plus a syntactically valid object id is accepted as
  evidence.
* Every repository-relative path handed to ``git`` must carry the
  ``LVW_Prompt_Service_MasterPack_v2.0.0/`` package prefix.
* **All** preflight checks (child anchor sha256, child git blob binding,
  candidate commit ids, code-file blob binding, inventory receipt sha256)
  must pass **before** the source phase starts.  The failure path returns
  immediately: the source phase is unreachable, the adapter is never
  touched, and the decision is a stable ``REJECTED``.
* A ``VERIFIED`` decision can only be produced from a passed preflight *and*
  a fully verified source set.  Hash equality alone can never produce
  ``VERIFIED``.
* The fail-closed condition is **control flow**, not a report field: the
  preflight verdict decides whether the source phase is entered at all.
* No broad ``except`` ever turns into success.  Unexpected exceptions are
  reported as ``REJECTED_INTERNAL_ERROR`` with a non-zero exit code.
* The production media root is **hard disabled**.  The helper has no default
  source root, refuses any root inside the production tree, refuses any root
  that is not explicitly allow-listed by the caller, and requires the root to
  carry the synthetic fixture marker file.  This worker has no external real
  media authority, so real media is out of reach by construction.
* All budget accounting (file count, byte budget, wall clock, chunk size),
  the changed-identity check and the symlink-escape check are exercised on
  synthetic fixtures only.

Exit codes
----------
0  verified (preflight passed and every selected file verified)
2  rejected (preflight failure, budget failure, escape, identity mismatch)
3  guard rejection (production root, missing allow-list, missing marker)
4  rejected (unexpected internal error)
5  usage error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat as stat_module
import subprocess
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

#: Repository-relative prefix of the packaged work tree.  Every path that is
#: handed to ``git`` inside this helper must start with it.
REPO_PACKAGE_PREFIX = "LVW_Prompt_Service_MasterPack_v2.0.0/"

#: The production media root (and its parent) are never addressable here.
PRODUCTION_REAL_ROOTS = (
    "/mnt/c/workSpace/videoWorkLine/testSource",
    "/mnt/c/workSpace/videoWorkLine",
)

#: Marker file that a synthetic fixture root must contain.
FIXTURE_MARKER_NAME = ".lvw-synthetic-fixture-root"

#: The fixture marker content that proves intent.
FIXTURE_MARKER_CONTENT = "synthetic-fixture-root\n"

#: Object ids we accept from ``git``: sha1 (40) or sha256 (64) hex.
OBJECT_ID_LENGTHS = (40, 64)

EXIT_VERIFIED = 0
EXIT_REJECTED = 2
EXIT_GUARD = 3
EXIT_INTERNAL = 4
EXIT_USAGE = 5

DECISION_VERIFIED = "S3_PREP_INDEPENDENT_HASH_RECHECK_VERIFIED"
DECISION_REJECTED_PREFLIGHT = "S3_PREP_INDEPENDENT_HASH_RECHECK_REJECTED_PREFLIGHT"
DECISION_REJECTED_SOURCE = "S3_PREP_INDEPENDENT_HASH_RECHECK_NOT_VERIFIED"
DECISION_REJECTED_GUARD = "S3_PREP_INDEPENDENT_HASH_RECHECK_REJECTED_GUARD"
DECISION_REJECTED_INTERNAL = "S3_PREP_INDEPENDENT_HASH_RECHECK_REJECTED_INTERNAL_ERROR"


def zero_counters():
    """The counter set used whenever the source phase was never entered."""
    return {
        "files_attempted": 0,
        "files_hashed": 0,
        "bytes_read": 0,
        "chunks_read": 0,
        "files_skipped": 0,
        "escape_rejected": 0,
        "identity_mismatch": 0,
        "missing": 0,
        "budget_exceeded": 0,
        "adapter_resolve_calls": 0,
        "adapter_stat_calls": 0,
        "adapter_open_calls": 0,
    }


class PreflightRejected(Exception):
    """Raised when a preflight check fails.  Carries the failed check name."""


class GuardRejected(Exception):
    """Raised when the production-root / fixture-only guard refuses to run."""


# --------------------------------------------------------------------------
# git access (return code is always checked)
# --------------------------------------------------------------------------


def run_git(repo_root: Path, args):
    """Run a git command and return ``(returncode, stdout, stderr)``.

    The return code is *never* ignored.  ``stdout`` is returned verbatim so
    that the caller can reject an echoed argument, which is what a failed
    ``git rev-parse`` prints.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def is_object_id(text: str) -> bool:
    """True when ``text`` is a bare sha1/sha256 object id."""
    if not text or len(text) not in OBJECT_ID_LENGTHS:
        return False
    return all(ch in "0123456789abcdef" for ch in text.lower())


def git_type(repo_root: Path, object_id: str) -> str:
    """Return the object type of ``object_id``; fails closed on a bad exit."""
    code, out, err = run_git(repo_root, ["cat-file", "-t", object_id])
    if code != 0:
        raise PreflightRejected(
            "git cat-file -t %s exited %d (expected 0): %s"
            % (object_id, code, err.strip()[:200])
        )
    if not out:
        raise PreflightRejected("git cat-file -t %s produced no object type" % object_id)
    return out


def git_object_id(repo_root: Path, args, what: str) -> str:
    """Return the object id produced by ``git <args>``.

    Fails closed: a non-zero return code, an empty output or an output that
    is not a valid object id is a preflight failure.
    """
    code, out, err = run_git(repo_root, args)
    if code != 0:
        raise PreflightRejected(
            "git %s exited %d (expected 0): %s" % (" ".join(args), code, err.strip()[:200])
        )
    if not is_object_id(out):
        raise PreflightRejected(
            "git %s did not return a valid object id: %r" % (" ".join(args), out[:120])
        )
    return out.lower()


# --------------------------------------------------------------------------
# source adapter (the only component allowed to touch source bytes)
# --------------------------------------------------------------------------


class LocalSourceAdapter:
    """Read-only adapter over a source root.

    Every filesystem touch on the source side goes through this class, so a
    test can substitute a spy and prove that a rejected run performed zero
    source resolves, stats or opens.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.calls = []

    # -- instrumentation --------------------------------------------------
    def call_count(self, op: str) -> int:
        return sum(1 for name, _ in self.calls if name == op)

    def counters(self):
        return {
            "adapter_resolve_calls": self.call_count("resolve"),
            "adapter_stat_calls": self.call_count("stat"),
            "adapter_open_calls": self.call_count("open_read"),
        }

    # -- operations -------------------------------------------------------
    def resolve(self, relative_path: str) -> Path:
        self.calls.append(("resolve", relative_path))
        return self.root / relative_path

    def stat(self, path: Path):
        self.calls.append(("stat", str(path)))
        return os.stat(str(path), follow_symlinks=False)

    def open_read(self, path: Path):
        self.calls.append(("open_read", str(path)))
        return open(str(path), "rb")


# --------------------------------------------------------------------------
# guard: fixture-only, production root hard disabled
# --------------------------------------------------------------------------


def _norm(path) -> str:
    return os.path.normpath(os.path.abspath(str(path)))


def _is_inside(candidate: str, parent: str) -> bool:
    candidate = candidate.rstrip(os.sep)
    parent = parent.rstrip(os.sep)
    return candidate == parent or candidate.startswith(parent + os.sep)


def guard_source_root(source_root: Path, allowed_roots, repo_root: Path):
    """Refuse anything that is not an explicitly allow-listed fixture root.

    The check is purely lexical: no filesystem access is performed on the
    production paths, so the guard itself can never read real media.
    """
    root = _norm(source_root)
    for denied in PRODUCTION_REAL_ROOTS:
        denied_norm = _norm(denied)
        if _is_inside(root, denied_norm):
            raise GuardRejected(
                "source root %s is inside the production media root %s; the "
                "production root is hard disabled in this helper" % (root, denied_norm)
            )
    repo_norm = _norm(repo_root)
    if _is_inside(root, repo_norm):
        raise GuardRejected(
            "source root %s is inside the review repository %s; only synthetic "
            "fixture roots are addressable" % (root, repo_norm)
        )
    if not allowed_roots:
        raise GuardRejected("no fixture allow-list was supplied")
    matched = None
    for allowed in allowed_roots:
        allowed_norm = _norm(allowed)
        if _is_inside(root, allowed_norm):
            matched = allowed_norm
            break
    if matched is None:
        raise GuardRejected(
            "source root %s is not inside any allow-listed fixture root" % root
        )
    marker = Path(root) / FIXTURE_MARKER_NAME
    if not marker.is_file():
        raise GuardRejected(
            "source root %s does not carry the synthetic fixture marker %s"
            % (root, FIXTURE_MARKER_NAME)
        )
    try:
        content = marker.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive
        raise GuardRejected("fixture marker %s is unreadable: %s" % (marker, exc))
    if content != FIXTURE_MARKER_CONTENT:
        raise GuardRejected(
            "fixture marker %s does not carry the expected synthetic content" % marker
        )
    return matched


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------


def _package_git_path(package_relative: str) -> str:
    """Compose the repository-relative git path for a package-relative path."""
    if package_relative.startswith("/") or ".." in Path(package_relative).parts:
        raise PreflightRejected(
            "package-relative path %r is not a plain relative path" % package_relative
        )
    git_path = REPO_PACKAGE_PREFIX + package_relative
    if not git_path.startswith(REPO_PACKAGE_PREFIX):
        raise PreflightRejected(
            "git path %r does not carry the %s prefix" % (git_path, REPO_PACKAGE_PREFIX)
        )
    return git_path


def run_preflight(child, child_path: Path, child_sha256: str, expected_child_sha256: str,
                  expected_child_commit: str, repo_root: Path, checks=None):
    """Run every metadata check.

    Returns ``(checks, detail)``.  ``checks`` maps a check name to a dict
    with ``ok`` and ``detail``.  Any failure raises ``PreflightRejected`` and
    the source phase must not be entered.  The caller passes the ``checks``
    dict in so that a rejected run can still report the checks that did run.
    """
    checks = {} if checks is None else checks

    def record(name, ok, detail):
        checks[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            raise PreflightRejected("%s: %s" % (name, detail))

    # -- 0. structural guard on the package prefix ------------------------
    declared_prefix = child.get("repo_package_prefix")
    record(
        "package_prefix_declared",
        declared_prefix == REPO_PACKAGE_PREFIX,
        "declared=%r required=%r" % (declared_prefix, REPO_PACKAGE_PREFIX),
    )

    # -- 1. the child authority file itself --------------------------------
    record(
        "child_sha256_matches_out_of_band_anchor",
        child_sha256 == expected_child_sha256,
        "observed=%s expected=%s" % (child_sha256, expected_child_sha256),
    )
    child_sha = hashlib.sha256(child_path.read_bytes()).hexdigest()
    record(
        "child_sha256_self_consistent",
        child_sha == child_sha256,
        "recomputed=%s reported=%s" % (child_sha, child_sha256),
    )

    child_git_path = _package_git_path(child["child_rel_path"])
    anchor_kind = git_type(repo_root, expected_child_commit)
    record(
        "child_anchor_is_commit",
        anchor_kind == "commit",
        "cat-file -t=%s" % anchor_kind,
    )
    anchor_resolved = git_object_id(
        repo_root, ["rev-parse", expected_child_commit], "child anchor"
    )
    record(
        "child_anchor_resolves_to_itself",
        anchor_resolved == expected_child_commit.lower(),
        "rev-parse=%s expected=%s" % (anchor_resolved, expected_child_commit.lower()),
    )
    child_blob_at_commit = git_object_id(
        repo_root, ["rev-parse", "%s:%s" % (expected_child_commit, child_git_path)],
        "child blob",
    )
    child_worktree_blob = git_object_id(
        repo_root, ["hash-object", child_git_path], "child worktree blob"
    )
    record(
        "child_git_blob_matches_worktree",
        child_blob_at_commit == child_worktree_blob,
        "commit_blob=%s worktree_blob=%s path=%s"
        % (child_blob_at_commit, child_worktree_blob, child_git_path),
    )

    # -- 2. the candidate commits -------------------------------------------
    for label in ("source_candidate", "implementation_code_candidate"):
        sha = child[label]
        if not is_object_id(sha):
            record("%s_is_object_id" % label, False, "%r is not a valid object id" % sha)
        kind = git_type(repo_root, sha)
        record("%s_is_commit" % label, kind == "commit", "cat-file -t=%s" % kind)
        resolved = git_object_id(repo_root, ["rev-parse", sha], label)
        record(
            "%s_resolves_to_itself" % label,
            resolved == sha.lower(),
            "rev-parse=%s expected=%s" % (resolved, sha.lower()),
        )

    # -- 3. the code files must be byte identical to the candidate ---------
    impl = child["implementation_code_candidate"]
    code_identity = {}
    for relative in child["code_files"]:
        git_path = _package_git_path(relative)
        candidate_blob = git_object_id(
            repo_root, ["rev-parse", "%s:%s" % (impl, git_path)], "code blob"
        )
        worktree_blob = git_object_id(repo_root, ["hash-object", git_path], "code worktree blob")
        code_identity[relative] = {
            "git_path": git_path,
            "candidate_blob": candidate_blob,
            "checkout_blob": worktree_blob,
            "byte_identical_to_candidate": candidate_blob == worktree_blob,
        }
    record(
        "code_files_byte_identical_to_candidate",
        all(v["byte_identical_to_candidate"] for v in code_identity.values()),
        json.dumps(code_identity, sort_keys=True),
    )

    # -- 4. the inventory receipt ------------------------------------------
    receipt_path = Path(child["inventory_receipt"])
    record("inventory_receipt_exists", receipt_path.is_file(), str(receipt_path))
    receipt_sha = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    record(
        "inventory_receipt_sha256_matches",
        receipt_sha == child["inventory_receipt_sha256"],
        "observed=%s expected=%s" % (receipt_sha, child["inventory_receipt_sha256"]),
    )

    return checks, code_identity


# --------------------------------------------------------------------------
# source phase
# --------------------------------------------------------------------------


class BudgetExceeded(Exception):
    pass


def hash_file(adapter, path: Path, chunk_bytes: int, deadline: float, budget: dict):
    digest = hashlib.sha256()
    total = 0
    chunks = 0
    handle = adapter.open_read(path)
    with handle:
        while True:
            if time.monotonic() > deadline:
                raise BudgetExceeded("wall budget exhausted")
            chunk = handle.read(chunk_bytes)
            chunks += 1
            if not chunk:
                break
            if budget["bytes"] + total + len(chunk) > budget["max_bytes"]:
                raise BudgetExceeded("byte budget exhausted")
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total, chunks


def run_source_phase(child, adapter, limits, started):
    """Read the selected files.  Only reachable after a passed preflight."""
    deadline = started + float(limits["wall_seconds"])
    budget = {"bytes": 0, "max_bytes": int(limits["bytes"])}
    root = Path(child["source_root"])
    root_real = _norm(root)
    counters = {
        "files_attempted": 0,
        "files_hashed": 0,
        "bytes_read": 0,
        "chunks_read": 0,
        "files_skipped": 0,
        "escape_rejected": 0,
        "identity_mismatch": 0,
        "missing": 0,
        "budget_exceeded": 0,
    }
    results = []
    for entry in child["selected_files"]:
        counters["files_attempted"] += 1
        relative = entry["relative_path"]
        record = {
            "relative_path": relative,
            "expected_sha256": entry["sha256"],
            "expected_bytes": entry["bytes"],
            "expected_file_id": entry.get("file_id"),
        }
        if os.path.isabs(relative) or ".." in Path(relative).parts:
            counters["files_skipped"] += 1
            record["result"] = "UNSAFE_RELATIVE_PATH_REJECTED"
            results.append(record)
            continue
        target = adapter.resolve(relative)
        try:
            observed = adapter.stat(target)
        except OSError:
            counters["missing"] += 1
            counters["files_skipped"] += 1
            record["result"] = "MISSING_NOT_VERIFIED"
            results.append(record)
            continue
        if stat_module.S_ISLNK(observed.st_mode):
            counters["escape_rejected"] += 1
            counters["files_skipped"] += 1
            record["result"] = "SYMLINK_ESCAPE_REJECTED_NOT_VERIFIED"
            results.append(record)
            continue
        resolved = _norm(target)
        if not _is_inside(resolved, root_real):
            counters["escape_rejected"] += 1
            counters["files_skipped"] += 1
            record["result"] = "RESOLVED_ESCAPE_REJECTED_NOT_VERIFIED"
            results.append(record)
            continue
        record["observed_stat"] = {
            "st_size": observed.st_size,
            "st_mtime_ns": observed.st_mtime_ns,
            "st_ino": observed.st_ino,
            "st_dev": observed.st_dev,
        }
        if observed.st_size != entry["bytes"]:
            counters["identity_mismatch"] += 1
            counters["files_skipped"] += 1
            record["result"] = "SOURCE_CHANGED_NOT_VERIFIED"
            record["detail"] = "size %s != expected %s" % (observed.st_size, entry["bytes"])
            results.append(record)
            continue
        try:
            digest, total, chunks = hash_file(
                adapter, target, int(limits["chunk_bytes"]), deadline, budget
            )
        except BudgetExceeded as exc:
            counters["budget_exceeded"] += 1
            counters["files_skipped"] += 1
            record["result"] = "BUDGET_EXCEEDED_NOT_VERIFIED"
            record["detail"] = str(exc)
            results.append(record)
            continue
        except OSError as exc:
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
        if entry.get("mtime_ns") is not None:
            record["mtime_matches_candidate"] = observed.st_mtime_ns == entry["mtime_ns"]
            if not record["mtime_matches_candidate"]:
                counters["identity_mismatch"] += 1
                record["result"] = "SOURCE_CHANGED_NOT_VERIFIED"
                results.append(record)
                continue
        if digest != entry["sha256"] or total != entry["bytes"]:
            counters["identity_mismatch"] += 1
            record["result"] = "SOURCE_CHANGED_NOT_VERIFIED"
        else:
            record["result"] = "VERIFIED"
        results.append(record)
    return counters, results


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def default_repo_root() -> Path:
    # <repo>/LVW_.../reports/v0-s3/preparation-03/independent-process-correction-01/helper/<file>
    return Path(__file__).resolve().parents[6]


def build_payload(kind, decision, **extra):
    payload = {"kind": kind, "decision": decision}
    payload.update(extra)
    return payload


def run(child_path, out_path, expected_child_sha256, expected_child_commit,
        allowed_source_roots, repo_root=None, adapter_factory=None):
    """Run the corrected helper.

    Returns ``(exit_code, payload)``.  ``payload`` is always written to
    ``out_path`` when ``out_path`` is not ``None``.
    """
    started = time.monotonic()
    child_path = Path(child_path)
    try:
        child_raw = child_path.read_bytes()
    except OSError as exc:
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_PREFLIGHT,
            preflight_validated_before_source_access=False,
            preflight_checks={"child_readable": {"ok": False, "detail": str(exc)}},
            source_phase_entered=False,
            counters=zero_counters(),
        )
        payload["exit_code"] = EXIT_REJECTED
        _write(out_path, payload)
        return EXIT_REJECTED, payload

    child_sha256 = hashlib.sha256(child_raw).hexdigest()
    try:
        child = json.loads(child_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_PREFLIGHT,
            preflight_validated_before_source_access=False,
            preflight_checks={"child_parses_as_json": {"ok": False, "detail": str(exc)}},
            source_phase_entered=False,
            counters=zero_counters(),
        )
        payload["exit_code"] = EXIT_REJECTED
        _write(out_path, payload)
        return EXIT_REJECTED, payload

    repo_root = Path(repo_root) if repo_root else Path(child.get("repo_root") or default_repo_root())
    adapter_factory = adapter_factory or LocalSourceAdapter

    # ---- guard (before anything else) -------------------------------------
    try:
        guard_source_root(Path(child["source_root"]), allowed_source_roots, repo_root)
    except GuardRejected as exc:
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_GUARD,
            preflight_validated_before_source_access=False,
            source_phase_entered=False,
            guard={"ok": False, "detail": str(exc),
                   "production_roots_hard_disabled": list(PRODUCTION_REAL_ROOTS),
                   "fixture_marker_required": FIXTURE_MARKER_NAME},
            preflight_checks={},
            counters=zero_counters(),
        )
        payload["exit_code"] = EXIT_GUARD
        _write(out_path, payload)
        return EXIT_GUARD, payload

    # ---- preflight (control flow: the source phase is below this gate) ----
    checks = {}
    try:
        checks, code_identity = run_preflight(
            child, child_path, child_sha256, expected_child_sha256,
            expected_child_commit, repo_root, checks,
        )
    except PreflightRejected as exc:
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_PREFLIGHT,
            preflight_validated_before_source_access=False,
            preflight_rejection=str(exc),
            preflight_checks=checks,
            source_phase_entered=False,
            child_sha256=child_sha256,
            counters=zero_counters(),
        )
        payload["exit_code"] = EXIT_REJECTED
        _write(out_path, payload)
        return EXIT_REJECTED, payload
    except (KeyError, TypeError, ValueError, OSError) as exc:
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_PREFLIGHT,
            preflight_validated_before_source_access=False,
            preflight_rejection="malformed child authority: %r" % (exc,),
            preflight_checks=checks,
            source_phase_entered=False,
            counters=zero_counters(),
        )
        payload["exit_code"] = EXIT_REJECTED
        _write(out_path, payload)
        return EXIT_REJECTED, payload

    # ---- source phase (only reachable with a fully passed preflight) ------
    limits = child["limits"]
    adapter = adapter_factory(Path(child["source_root"]))
    try:
        if len(child["selected_files"]) > int(limits["files"]):
            raise BudgetExceeded(
                "selected file count %d exceeds the limit %s"
                % (len(child["selected_files"]), limits["files"])
            )
        counters, results = run_source_phase(child, adapter, limits, started)
    except BudgetExceeded as exc:
        counters = zero_counters()
        counters["budget_exceeded"] = 1
        results = []
        counters.update(adapter.counters())
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_SOURCE,
            preflight_validated_before_source_access=True,
            preflight_checks=checks,
            source_phase_entered=False,
            budget_rejection=str(exc),
            counters=counters,
            results=results,
        )
        payload["exit_code"] = EXIT_REJECTED
        _write(out_path, payload)
        return EXIT_REJECTED, payload
    except Exception as exc:  # fail closed, never success
        counters = zero_counters()
        counters.update(adapter.counters())
        payload = build_payload(
            "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
            DECISION_REJECTED_INTERNAL,
            preflight_validated_before_source_access=True,
            preflight_checks=checks,
            source_phase_entered=True,
            internal_error="%s: %s" % (type(exc).__name__, exc),
            counters=counters,
        )
        payload["exit_code"] = EXIT_INTERNAL
        _write(out_path, payload)
        return EXIT_INTERNAL, payload

    counters.update(adapter.counters())
    verified = (
        counters["files_hashed"] == len(child["selected_files"])
        and all(r["result"] == "VERIFIED" for r in results)
    )
    payload = build_payload(
        "S3_PREP_INDEPENDENT_HASH_RECHECK_CORRECTION",
        DECISION_VERIFIED if verified else DECISION_REJECTED_SOURCE,
        preflight_validated_before_source_access=True,
        preflight_checks=checks,
        source_phase_entered=True,
        child_sha256=child_sha256,
        code_identity=code_identity,
        limits=limits,
        counters=counters,
        results=results,
        elapsed_seconds=round(time.monotonic() - started, 3),
        notes=[
            "corrected reviewer-owned harness; synthetic fixture roots only",
            "the production media root is hard disabled; no real media was read by this run",
            "preflight verdict controls flow: a failed preflight never enters the source phase",
            "a VERIFIED decision requires a passed preflight and a fully verified source set",
        ],
    )
    payload["exit_code"] = EXIT_VERIFIED if verified else EXIT_REJECTED
    _write(out_path, payload)
    return payload["exit_code"], payload


def _write(out_path, payload):
    if out_path is None:
        return
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    Path(out_path).write_text(text, encoding="utf-8")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Corrected independent finite hash recheck (synthetic fixtures only)."
    )
    parser.add_argument("--child", required=True, help="path of the child authority JSON")
    parser.add_argument("--out", required=True, help="path of the JSON result to write")
    parser.add_argument(
        "--expected-child-sha256",
        required=True,
        help="out-of-band sha256 anchor for the child authority file",
    )
    parser.add_argument(
        "--expected-child-commit",
        required=True,
        help="out-of-band commit anchor that must contain the child authority blob",
    )
    parser.add_argument(
        "--allow-source-root",
        action="append",
        default=[],
        help="fixture root allow-list entry (repeatable); required",
    )
    parser.add_argument("--repo-root", default=None, help="git repository root to bind against")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.allow_source_root:
        sys.stderr.write(
            "guard: --allow-source-root is required; this helper has no default source root\n"
        )
        return EXIT_GUARD
    code, payload = run(
        args.child,
        args.out,
        args.expected_child_sha256,
        args.expected_child_commit,
        args.allow_source_root,
        repo_root=args.repo_root,
    )
    print(json.dumps({
        "decision": payload["decision"],
        "exit_code": code,
        "preflight_validated_before_source_access": payload.get(
            "preflight_validated_before_source_access"),
        "source_phase_entered": payload.get("source_phase_entered"),
        "counters": payload.get("counters"),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
