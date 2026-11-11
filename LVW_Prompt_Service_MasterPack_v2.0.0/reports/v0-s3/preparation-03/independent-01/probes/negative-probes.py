#!/usr/bin/env python3
"""Independent negative probes for the S3-PREP-A candidate.

Every probe runs against a *synthetic* copy of the frozen authority in a fresh
owned TemporaryDirectory.  No probe touches the approved local media root.
Results are written as JSON for the independent review report.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path("/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-review/LVW_Prompt_Service_MasterPack_v2.0.0")
sys.path.insert(0, str(REPO / "tools"))

import s3_asset_inventory as inv  # noqa: E402
import verify_s3_handoff as checker  # noqa: E402

PACKET_REL = ".agent-governance/stages/V0-S3"
APPROVAL_REL = "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.approval.json"
REQUEST_REL = "reports/v1-next-stage-readiness/change-v1-s2-handoff-01.request.json"
S2_MACHINE_REL = "reports/v0-s2/full-v0-auto-08/receipt.json"
S2_INDEP_REL = "reports/v0-s2/full-v0-auto-08/independent-review.json"
UM_COVERAGE_REL = "reports/unified-media/independent-live-15/coverage.json"
UM_SIGN_REL = "reports/unified-media/human-signoff-live15.json"
CAPABILITY_MAP_REL = "reports/v0-s3/handoff-capability-map-01.json"
EXECUTION_REL = "plans/execution-control.json"
TASKS_REL = "plans/tasks.json"
V1PLAN_REL = "plans/v1-revised-plan.json"
CHILD_REL = "reports/v0-s3/preparation-03/asset-inventory-child.json"

RESULTS = []


def authority_files():
    files = set(json.loads((REPO / PACKET_REL / "spec-manifest.json").read_text(encoding="utf-8"))["files"])
    for line in (REPO / PACKET_REL / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            files.add(PACKET_REL + "/" + line.split("  ", 1)[1].strip())
    files.add(EXECUTION_REL)
    files.add(PACKET_REL + "/PAYLOAD_MANIFEST.sha256")
    files.add("reports/unified-media/independent-live-15/receipt.json")
    return sorted(files)


AUTHORITY_FILES = authority_files()


def build_tree(root: Path) -> Path:
    for relative in AUTHORITY_FILES:
        source = REPO / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def read_json(root: Path, relative: str):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def write_json(root: Path, relative: str, payload) -> None:
    (root / relative).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def failed_ids(result):
    return sorted(item["id"] for item in result["checks"] if not item["passed"])


def record(probe_id, kind, decision, ids, extra=None, note=None):
    entry = {
        "probe_id": probe_id,
        "kind": kind,
        "decision": decision,
        "failed_check_ids": ids,
    }
    if extra:
        entry.update(extra)
    if note:
        entry["note"] = note
    RESULTS.append(entry)
    print("%-28s %-28s %s" % (probe_id, decision, ids[:6]))


# ---------------------------------------------------------------------------
# guard probes (semantic, on synthetic authority copies)
# ---------------------------------------------------------------------------


def probe_baseline(tmp):
    tree = build_tree(tmp / "package")
    result = checker.evaluate(tree)
    record("guard.baseline_copy", "semantic", result["decision"], failed_ids(result),
           {"authority": result["authority"], "checks": result["summary"]["checks"]},
           "an untouched synthetic copy of the frozen authority must verify")


def probe_lead_development_outline(tmp):
    """The coordinator's lead: change ONLY the live development_outline entry."""
    tree = build_tree(tmp / "package")
    payload = read_json(tree, EXECUTION_REL)
    changed = []
    for entry in payload["development_outline"]:
        if entry.get("stage_id") == "V0-S2":
            entry["completed_substeps"] = 8
            entry["human_signoff"] = "APPROVED"
            entry["summary"] = "S2 fully signed"
            for sub in entry.get("substeps", []):
                if sub.get("name", "").startswith("S2 "):
                    sub["status"] = "DONE"
                    sub["evidence"] = "reports/v0-s2/full-v0-auto-08/receipt.json"
            changed.append(entry["stage_id"])
    write_json(tree, EXECUTION_REL, payload)
    result = checker.evaluate(tree)
    fence_failed = [i for i in failed_ids(result) if i.startswith("fence.")]
    record(
        "guard.live_s2_outline_8of8",
        "semantic",
        result["decision"],
        failed_ids(result),
        {
            "authority": result["authority"],
            "changed_stages": changed,
            "fence_failures": fence_failed,
            "reported_historical_s2_projection": result["historical_s2_projection"],
            "actual_development_outline_s2": {
                "completed_substeps": 8,
                "human_signoff": "APPROVED",
            },
        },
        "ONLY the live execution-control development_outline V0-S2 entry was changed; "
        "every immutable proof, the declared predicate snapshot in all three plans and "
        "the approval record were left untouched",
    )


def probe_lead_development_outline_with_substep_evidence(tmp):
    """Same lead, but also flip the last S2 substep to DONE with real evidence."""
    tree = build_tree(tmp / "package")
    payload = read_json(tree, EXECUTION_REL)
    for entry in payload["development_outline"]:
        if entry.get("stage_id") == "V0-S2":
            entry["substeps"][-1]["status"] = "DONE"
            entry["substeps"][-1]["evidence"] = "reports/v0-s2/full-v0-auto-08/receipt.json"
            entry["completed_substeps"] = 8
            entry["human_signoff"] = "APPROVED"
    write_json(tree, EXECUTION_REL, payload)
    result = checker.evaluate(tree)
    record(
        "guard.live_s2_outline_8of8_substep_done",
        "semantic",
        result["decision"],
        failed_ids(result),
        {"authority": result["authority"],
         "fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
        "last S2 substep marked DONE with the historical machine receipt as evidence",
    )


def probe_historical_s2_coordinate(tmp):
    """A legitimately mutable coordinate must keep verifying."""
    tree = build_tree(tmp / "package")
    payload = read_json(tree, EXECUTION_REL)
    payload["coordinate"] = {"stage_id": "R1", "workpack_id": "WP-R1-U3",
                             "gate": "S3_GATE0", "state": "ADVANCED"}
    payload["current_blocking_gate"] = "OTHER"
    payload["updated_at"] = "2026-12-31"
    write_json(tree, EXECUTION_REL, payload)
    result = checker.evaluate(tree)
    record("guard.mutable_coordinates_advance", "semantic", result["decision"], failed_ids(result),
           {"execution_coordinates_frozen": result["execution_coordinates_frozen"]},
           "a true current mutable execution coordinate may advance")


def probe_wrong_alias(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, TASKS_REL)
    alias = dict(payload["dependency_gate_overrides"][0])
    alias["id"] = "GENERIC_V1_HANDOFF"
    payload["dependency_gate_overrides"].append(alias)
    write_json(tree, TASKS_REL, payload)
    result = checker.evaluate(tree)
    record("guard.unsanctioned_alias", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "an extra unsanctioned dependency-gate alias")


def probe_wrong_purpose(tmp):
    tree = build_tree(tmp / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["purpose"] = "V1_FULL_ACCEPTANCE"
        else:
            payload["v1_only_s2_handoff"]["purpose"] = "V1_FULL_ACCEPTANCE"
        write_json(tree, relative, payload)
    result = checker.evaluate(tree)
    record("guard.wrong_purpose", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "purpose widened to V1_FULL_ACCEPTANCE in all three plans")


def probe_wrong_proof_in_predicate(tmp):
    """Predicate proof hash differs from the frozen owner pin (semantic)."""
    tree = build_tree(tmp / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["proofs"]["scope_approval"]["sha256"] = "0" * 64
        else:
            payload["v1_only_s2_handoff"]["proofs"]["scope_approval"]["sha256"] = "0" * 64
        write_json(tree, relative, payload)
    result = checker.evaluate(tree)
    record("guard.wrong_proof_pin_in_predicate", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "predicate proof hash replaced with zeros in all three plans")


def probe_tampered_proof_file(tmp):
    """A frozen proof FILE is edited (generic checksum rejection)."""
    tree = build_tree(tmp / "package")
    path = tree / CAPABILITY_MAP_REL
    payload = read_json(tree, CAPABILITY_MAP_REL)
    payload["historical_s2_signed"] = True
    write_json(tree, CAPABILITY_MAP_REL, payload)
    result = checker.evaluate(tree)
    record("guard.tampered_proof_file", "generic_checksum", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the capability map file bytes were edited")


def probe_fake_old_s2_human_declared(tmp):
    """The DECLARED predicate claims an 8/8 signed old S2 (semantic)."""
    tree = build_tree(tmp / "package")
    fake = {"completed_substeps": 8, "total_substeps": 8, "human_signoff": "SIGNED"}
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["historical_s2_required_state"] = copy.deepcopy(fake)
        else:
            payload["v1_only_s2_handoff"]["historical_s2_required_state"] = copy.deepcopy(fake)
        write_json(tree, relative, payload)
    result = checker.evaluate(tree)
    record("guard.fake_old_s2_declared", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the declared predicate snapshot claims an 8/8 SIGNED historical S2")


def probe_approval_claims_old_s2_signature(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, APPROVAL_REL)
    payload["historical_s2_native_human_approved"] = True
    payload["historical_s2_completed_substeps"] = 8
    write_json(tree, APPROVAL_REL, payload)
    result = checker.evaluate(tree)
    record("guard.approval_claims_s2_signature", "generic_checksum", result["decision"],
           failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the approval record claims an old S2 native human signature")


def probe_missing_um_case(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, UM_COVERAGE_REL)
    payload["rows"] = [row for row in payload["rows"] if row.get("id") != "UM-05"]
    write_json(tree, UM_COVERAGE_REL, payload)
    result = checker.evaluate(tree)
    record("guard.missing_um_case", "generic_checksum", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "UM-05 removed from the unified-media coverage")


def probe_missing_s2_case(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, S2_MACHINE_REL)
    payload["cases"].pop("V0-A07")
    write_json(tree, S2_MACHINE_REL, payload)
    result = checker.evaluate(tree)
    record("guard.missing_s2_case", "generic_checksum", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "V0-A07 removed from the historical S2 machine receipt")


def probe_missing_case_semantic_shrunk_list(tmp):
    tree = build_tree(tmp / "package")
    for relative in (TASKS_REL, V1PLAN_REL, EXECUTION_REL):
        payload = read_json(tree, relative)
        if relative == TASKS_REL:
            payload["dependency_gate_overrides"][0]["required_s2_case_ids"].remove("V0-A07")
        else:
            payload["v1_only_s2_handoff"]["required_s2_case_ids"].remove("V0-A07")
        write_json(tree, relative, payload)
    result = checker.evaluate(tree)
    record("guard.shrunk_required_case_list", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the required S2 case list is shrunk in all three plans")


def probe_malformed_plan_json(tmp):
    tree = build_tree(tmp / "package")
    (tree / TASKS_REL).write_text("{ this is not json", encoding="utf-8")
    result = checker.evaluate(tree)
    record("guard.malformed_plan_json", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "plans/tasks.json is not valid JSON")


def probe_malformed_payload_manifest(tmp):
    tree = build_tree(tmp / "package")
    (tree / PACKET_REL / "PAYLOAD_MANIFEST.sha256").write_text("garbage\n", encoding="utf-8")
    result = checker.evaluate(tree)
    record("guard.malformed_payload_manifest", "generic_checksum", result["decision"],
           failed_ids(result), {}, "the packet payload manifest line is malformed")


def probe_missing_approval(tmp):
    tree = build_tree(tmp / "package")
    (tree / APPROVAL_REL).unlink()
    result = checker.evaluate(tree)
    record("guard.missing_approval", "generic_checksum", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the owner approval file is absent")


def probe_missing_um_signoff(tmp):
    tree = build_tree(tmp / "package")
    (tree / UM_SIGN_REL).unlink()
    result = checker.evaluate(tree)
    record("guard.missing_um_signoff", "generic_checksum", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the unified-media human signature file is absent")


def probe_predicate_divergence(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, EXECUTION_REL)
    payload["v1_only_s2_handoff"]["s2_machine_candidate"] = "0" * 40
    write_json(tree, EXECUTION_REL, payload)
    result = checker.evaluate(tree)
    record("guard.predicate_divergence", "semantic", result["decision"], failed_ids(result),
           {"fence_failures": [i for i in failed_ids(result) if i.startswith("fence.")]},
           "the execution-control predicate snapshot differs from the other two plans")


def probe_capability_map_quality_inherited(tmp):
    tree = build_tree(tmp / "package")
    payload = read_json(tree, CAPABILITY_MAP_REL)
    payload["quality_coverage_inherited"] = True
    write_json(tree, CAPABILITY_MAP_REL, payload)
    result = checker.evaluate(tree)
    record("guard.map_claims_inherited_quality", "generic_checksum", result["decision"],
           failed_ids(result), {}, "the capability map claims inherited quality coverage")


# ---------------------------------------------------------------------------
# inventory probes (synthetic fixture media only)
# ---------------------------------------------------------------------------


def small_limits(**overrides):
    limits = dict(inv.EXPECTED_LIMITS)
    limits.update(overrides)
    return limits


def make_child(path: Path, media_root: Path, limits=None, extensions=None) -> Path:
    child = json.loads((REPO / CHILD_REL).read_text(encoding="utf-8"))
    child["allowed_roots"] = [{
        "alias": "testSource",
        "wsl_path": str(media_root),
        "permission": "fixture only; not an authority grant",
    }]
    if limits is not None:
        child["limits"] = limits
    if extensions is not None:
        child["allowed_extensions"] = extensions
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(child, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_binding(path: Path, child_path: Path, pins: dict, candidate="a" * 40) -> Path:
    binding = {
        "kind": "S3_PREPARATION_PREFLIGHT_BINDING",
        "candidate_sha": candidate,
        "inventory_script_sha256": checker.sha256_file(REPO / inv.INVENTORY_REL),
        "handoff_script_sha256": checker.sha256_file(REPO / inv.HANDOFF_REL),
        "inventory_child_sha256": checker.sha256_file(child_path),
        "scope_approval_sha256": pins["proofs"]["scope_approval"]["sha256"],
        "frozen_proof_hashes": pins["proofs"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fixture_pins(child_path: Path) -> dict:
    return {
        "child": {"path": CHILD_REL, "sha256": checker.sha256_file(child_path)},
        "proofs": dict(checker.PROOF_PINS),
    }


def write_media(root: Path, files: dict) -> dict:
    oracle = {}
    for relative, payload in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        oracle[relative] = {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    return oracle


def probe_guard_denied_zero_media_reads(tmp):
    media = tmp / "media"
    write_media(media, {"a.jpg": b"secret-media-bytes" * 4})
    broken = build_tree(tmp / "authority")
    (broken / UM_COVERAGE_REL).write_text("{ not json", encoding="utf-8")
    child_path = make_child(tmp / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins)

    access = []
    real_open = open

    class Spy:
        def __init__(self, inner):
            self._inner = inner

        def read(self, *a, **k):
            access.append(("read", str(self._inner.name)))
            return self._inner.read(*a, **k)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return self._inner.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    import builtins
    original_open = builtins.open

    def spy_open(file, *a, **k):
        handle = original_open(file, *a, **k)
        try:
            if str(file).startswith(str(media)):
                return Spy(handle)
        except Exception:
            pass
        return handle

    builtins.open = spy_open
    try:
        receipt = inv.run_inventory(
            binding_path=binding_path,
            receipt_path=tmp / "reports" / "receipt.json",
            package_root=REPO,
            guard_root=broken,
            child_path=child_path,
            pins=pins,
            report_root=tmp / "reports",
        )
    finally:
        builtins.open = original_open
    record(
        "inventory.guard_denied_zero_media_reads",
        "semantic",
        receipt["decision"],
        [receipt["refusal"]["reason"]] if receipt.get("refusal") else [],
        {
            "refusal": receipt.get("refusal"),
            "media_bytes_read": receipt["media_access"]["media_bytes_read"],
            "files_hashed": receipt["media_access"]["files_hashed"],
            "items": len(receipt["items"]),
            "observed_media_opens": access,
        },
        "the guard refuses before any source byte is read",
    )


def probe_budget_exact_and_one_over(tmp):
    media = tmp / "media"
    write_media(media, {"a.jpg": b"a" * 10, "b.jpg": b"b" * 10, "c.jpg": b"c" * 10})
    results = {}
    for label, max_files in (("exact", 2), ("one_over", 1)):
        child_path = make_child(tmp / ("child_%s.json" % label), media, small_limits(max_files_hashed=max_files))
        pins = fixture_pins(child_path)
        binding_path = make_binding(tmp / ("preflight_%s.json" % label), child_path, pins)
        receipt = inv.run_inventory(
            binding_path=binding_path,
            receipt_path=tmp / ("reports_%s" % label) / "receipt.json",
            package_root=REPO,
            guard_root=REPO,
            child_path=child_path,
            pins=pins,
            report_root=tmp / ("reports_%s" % label),
        )
        results[label] = {
            "eligible": receipt["counts"]["eligible"],
            "skipped_by_reason": receipt["counts"]["skipped_by_reason"],
            "files_hashed": receipt["media_access"]["files_hashed"],
            "decision": receipt["decision"],
        }
    record("inventory.hash_budget_exact_vs_one_over", "semantic",
           "exact=%d one_over=%d" % (results["exact"]["eligible"], results["one_over"]["eligible"]),
           [], {"exact": results["exact"], "one_over": results["one_over"]},
           "hash budget boundary: exactly N is hashed, N+1 is reported as a skip and never read")


def probe_source_escape(tmp):
    media = tmp / "media"
    outside = tmp / "outside.jpg"
    outside.write_bytes(b"outside-secret-bytes")
    write_media(media, {"a.jpg": b"inside-bytes"})
    os.symlink(outside, media / "escape.jpg")
    child_path = make_child(tmp / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins)
    receipt = inv.run_inventory(
        binding_path=binding_path,
        receipt_path=tmp / "reports" / "receipt.json",
        package_root=REPO,
        guard_root=REPO,
        child_path=child_path,
        pins=pins,
        report_root=tmp / "reports",
    )
    outside_sha = hashlib.sha256(b"outside-secret-bytes").hexdigest()
    record(
        "inventory.symlink_escape_rejected",
        "semantic",
        receipt["decision"],
        [],
        {
            "eligible": receipt["counts"]["eligible"],
            "skipped_by_reason": receipt["counts"]["skipped_by_reason"],
            "outside_sha_present": any(i["sha256"] == outside_sha for i in receipt["items"]),
        },
        "a symlink pointing outside the approved root is never followed",
    )


def probe_existing_receipt(tmp):
    media = tmp / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins)
    receipt_path = tmp / "reports" / "receipt.json"
    first = inv.run_inventory(
        binding_path=binding_path,
        receipt_path=receipt_path,
        package_root=REPO,
        guard_root=REPO,
        child_path=child_path,
        pins=pins,
        report_root=tmp / "reports",
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("previous terminal receipt", encoding="utf-8")
    second = inv.run_inventory(
        binding_path=binding_path,
        receipt_path=receipt_path,
        package_root=REPO,
        guard_root=REPO,
        child_path=child_path,
        pins=pins,
        report_root=tmp / "reports",
    )
    record(
        "inventory.existing_receipt_not_overwritten",
        "semantic",
        second["decision"],
        [second["refusal"]["reason"]] if second.get("refusal") else [],
        {
            "first_decision": first["decision"],
            "write_receipt": second["write_receipt"],
            "file_unchanged": receipt_path.read_text(encoding="utf-8") == "previous terminal receipt",
        },
        "an existing terminal receipt is never overwritten",
    )


def probe_changed_source_file(tmp):
    media = tmp / "media"
    write_media(media, {"a.jpg": b"original-bytes"})
    child_path = make_child(tmp / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins)
    real_hash = inv.sha256_file

    def mutating(path, chunk_bytes, deadline, clock, already=0, max_total=None):
        result = real_hash(path, chunk_bytes, deadline, clock, already, max_total)
        Path(path).write_bytes(b"changed-after-the-read")
        return result

    inv.sha256_file = mutating
    try:
        receipt = inv.run_inventory(
            binding_path=binding_path,
            receipt_path=tmp / "reports" / "receipt.json",
            package_root=REPO,
            guard_root=REPO,
            child_path=child_path,
            pins=pins,
            report_root=tmp / "reports",
        )
    finally:
        inv.sha256_file = real_hash
    record(
        "inventory.changed_during_inventory_excluded",
        "semantic",
        receipt["decision"],
        [],
        {
            "eligible": receipt["counts"]["eligible"],
            "skipped_by_reason": receipt["counts"]["skipped_by_reason"],
            "files_hashed": receipt["media_access"]["files_hashed"],
        },
        "a file changed between the before-stat and the after-stat is excluded",
    )


def probe_binding_candidate_not_a_commit(tmp):
    media = tmp / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins, candidate="not-a-sha")
    receipt = inv.run_inventory(
        binding_path=binding_path,
        receipt_path=tmp / "reports" / "receipt.json",
        package_root=REPO,
        guard_root=REPO,
        child_path=child_path,
        pins=pins,
        report_root=tmp / "reports",
    )
    record(
        "inventory.binding_candidate_must_be_a_sha",
        "semantic",
        receipt["decision"],
        [receipt["refusal"]["reason"]] if receipt.get("refusal") else [],
        {"refusal_detail": (receipt.get("refusal") or {}).get("detail"),
         "media_bytes_read": receipt["media_access"]["media_bytes_read"]},
        "the binding candidate_sha must be a 40 character git object id",
    )


def probe_fixture_child_cannot_widen_budget(tmp):
    """A NON-canonical (fixture) child may declare a wider budget."""
    media = tmp / "media"
    write_media(media, {"a.jpg": b"bytes"})
    wide = small_limits(max_files_hashed=999999, max_total_bytes_hashed=999999999999)
    child_path = make_child(tmp / "child.json", media, wide)
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp / "preflight.json", child_path, pins)
    receipt = inv.run_inventory(
        binding_path=binding_path,
        receipt_path=tmp / "reports" / "receipt.json",
        package_root=REPO,
        guard_root=REPO,
        child_path=child_path,
        pins=pins,
        report_root=tmp / "reports",
    )
    record(
        "inventory.fixture_child_widened_budget",
        "semantic",
        receipt["decision"],
        [],
        {
            "authority": receipt["authority"],
            "limits_honoured": receipt["child_binding"]["limits"],
            "note": "a non-canonical fixture child may widen the budget; the run is labelled "
                    "FIXTURE_NON_AUTHORITY and the CLI never accepts a fixture child",
        },
        "child limit enforcement is gated on the canonical child",
    )


def probe_real_child_limits_are_enforced(tmp):
    """The canonical child limits must be exactly the frozen values."""
    child = json.loads((REPO / CHILD_REL).read_text(encoding="utf-8"))
    record(
        "inventory.canonical_child_limits",
        "fact",
        "MATCH" if child["limits"] == inv.EXPECTED_LIMITS else "MISMATCH",
        [],
        {
            "child_limits": child["limits"],
            "expected_limits": inv.EXPECTED_LIMITS,
            "child_extensions": child["allowed_extensions"],
            "expected_extensions": list(inv.EXPECTED_EXTENSIONS),
            "child_kind": child["kind"],
            "expected_kind": inv.EXPECTED_CHILD_KIND,
        },
        "the frozen child authorisation must carry exactly the frozen limits and extensions",
    )


def main() -> int:
    guards = [
        probe_baseline,
        probe_lead_development_outline,
        probe_lead_development_outline_with_substep_evidence,
        probe_historical_s2_coordinate,
        probe_wrong_alias,
        probe_wrong_purpose,
        probe_wrong_proof_in_predicate,
        probe_tampered_proof_file,
        probe_fake_old_s2_human_declared,
        probe_approval_claims_old_s2_signature,
        probe_missing_um_case,
        probe_missing_s2_case,
        probe_missing_case_semantic_shrunk_list,
        probe_malformed_plan_json,
        probe_malformed_payload_manifest,
        probe_missing_approval,
        probe_missing_um_signoff,
        probe_predicate_divergence,
        probe_capability_map_quality_inherited,
        probe_real_child_limits_are_enforced,
    ]
    inventories = [
        probe_guard_denied_zero_media_reads,
        probe_budget_exact_and_one_over,
        probe_source_escape,
        probe_existing_receipt,
        probe_changed_source_file,
        probe_binding_candidate_not_a_commit,
        probe_fixture_child_cannot_widen_budget,
    ]
    with tempfile.TemporaryDirectory(prefix="lvw-s3prep-probes-") as tmpdir:
        tmp = Path(tmpdir)
        for index, probe in enumerate(guards):
            d = tmp / ("g%02d" % index); d.mkdir(parents=True, exist_ok=True); probe(d)
        for index, probe in enumerate(inventories):
            d = tmp / ("i%02d" % index); d.mkdir(parents=True, exist_ok=True); probe(d)
    out = Path(sys.argv[1])
    out.write_text(json.dumps({"probes": RESULTS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written", out, len(RESULTS), "probes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
