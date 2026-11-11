#!/usr/bin/env python3
"""Tests for tools/s3_asset_inventory.py (V0-S3 preparation, bounded inventory).

The suite never touches the approved local media root.  Every test builds
fresh temporary fixture roots under pytest's ``tmp_path`` and drives the
inventory through its public entry point with an injected fixture root, an
injected child authorisation and an injected pin set.  Those injections are
reported as ``FIXTURE_NON_AUTHORITY`` by the tool itself.

A process wide audit hook records every ``open`` / ``os.scandir`` so the
suite can *prove* that a refused run reads zero bytes of media and that no
test ever reaches the real approved root.

Run: python3 -B -m pytest tools/test_s3_asset_inventory.py -q
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import s3_asset_inventory as inventory  # noqa: E402
import verify_s3_handoff as guard  # noqa: E402

REAL_MEDIA_MARKER = "/mnt/c/workSpace/videoWorkLine"
PACKET_REL = ".agent-governance/stages/V0-S3"
CHILD_REL = "reports/v0-s3/preparation-03/asset-inventory-child.json"

_ACCESS: list = []


def _audit(event, args):
    if event in ("open", "os.scandir", "os.listdir") and args:
        target = args[0]
        if isinstance(target, bytes):
            target = target.decode("utf-8", "ignore")
        if isinstance(target, str):
            _ACCESS.append((event, target))


sys.addaudithook(_audit)


@pytest.fixture(autouse=True)
def no_real_media_access():
    """The suite must never read the approved local media root."""
    before = len(_ACCESS)
    yield
    leaked = [item for item in _ACCESS[before:] if item[1].startswith(REAL_MEDIA_MARKER)]
    assert not leaked, "the test suite must not touch the approved media root: %r" % (leaked,)


def access_under(prefix: str) -> list:
    return [item for item in _ACCESS if item[1].startswith(prefix)]


def access_since(index: int, prefix: str) -> list:
    """Media accesses recorded after ``index`` (the fixture setup is excluded)."""
    return [item for item in _ACCESS[index:] if item[1].startswith(prefix)]


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def write_media(root: Path, files: dict) -> dict:
    """Create fixture media files and return an independent hash oracle."""
    oracle = {}
    for relative, payload in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        oracle[relative] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
    return oracle


def make_child(path: Path, media_root: Path, limits: dict = None, extensions=None) -> Path:
    """Write a synthetic child authorisation pointing at a fixture root."""
    child = json.loads((ROOT / CHILD_REL).read_text(encoding="utf-8"))
    child["allowed_roots"] = [
        {
            "alias": "testSource",
            "wsl_path": str(media_root),
            "permission": "fixture only; not an authority grant",
        }
    ]
    if limits is not None:
        child["limits"] = limits
    if extensions is not None:
        child["allowed_extensions"] = extensions
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(child, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_binding(path: Path, child_path: Path, pins: dict, candidate: str = "a" * 40) -> Path:
    binding = {
        "kind": "S3_PREPARATION_PREFLIGHT_BINDING",
        "candidate_sha": candidate,
        "inventory_script_sha256": guard.sha256_file(ROOT / inventory.INVENTORY_REL),
        "handoff_script_sha256": guard.sha256_file(ROOT / inventory.HANDOFF_REL),
        "inventory_child_sha256": guard.sha256_file(child_path),
        "scope_approval_sha256": pins["proofs"]["scope_approval"]["sha256"],
        "frozen_proof_hashes": pins["proofs"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fixture_pins(child_path: Path) -> dict:
    return {
        "child": {"path": CHILD_REL, "sha256": guard.sha256_file(child_path)},
        "proofs": dict(guard.PROOF_PINS),
    }


def small_limits(**overrides) -> dict:
    limits = dict(inventory.EXPECTED_LIMITS)
    limits.update(overrides)
    return limits


def run_and_watch(*args, **kwargs):
    """Run the inventory and return the receipt plus the access-log offset."""
    before = len(_ACCESS)
    receipt = inventory.run_inventory(*args, **kwargs)
    return receipt, before


def authority_tree(root: Path) -> Path:
    """A synthetic copy of the frozen authority, used as a guard root."""
    files = set(
        json.loads((ROOT / PACKET_REL / "spec-manifest.json").read_text(encoding="utf-8"))["files"]
    )
    for line in (ROOT / PACKET_REL / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            files.add(PACKET_REL + "/" + line.split("  ", 1)[1].strip())
    files.add(PACKET_REL + "/PAYLOAD_MANIFEST.sha256")
    files.add("plans/execution-control.json")
    files.add("reports/unified-media/independent-live-15/receipt.json")
    for relative in sorted(files):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


# --------------------------------------------------------------------------
# positive path with the real owner authority
# --------------------------------------------------------------------------


def test_positive_inventory_reports_independently_verified_hashes(tmp_path):
    media = tmp_path / "media"
    payload = {
        "a.jpg": b"first-image-bytes" * 7,
        "b.PNG": b"second-image-bytes" * 11,
        "c.mp4": b"third-video-bytes" * 13,
        "sub/d.jpg": b"nested-image-bytes" * 3,
        "notes.txt": b"not a media asset",
    }
    oracle = write_media(media, payload)
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )

    assert receipt["decision"] == "INVENTORY_COMPLETE", receipt.get("refusal")
    assert receipt["guard"]["decision"] == "HANDOFF_READINESS_VERIFIED"
    assert receipt["guard"]["summary"]["failed"] == 0
    assert receipt["authority"] == "FIXTURE_NON_AUTHORITY"
    assert receipt["counts"]["eligible"] == 4
    assert receipt["counts"]["skipped"] == 1
    assert receipt["counts"]["skipped_by_reason"] == {"unsupported_extension": 1}

    found = {item["relative_path"]: item for item in receipt["items"]}
    assert set(found) == {"a.jpg", "b.PNG", "c.mp4", "sub/d.jpg"}
    for relative, expected in oracle.items():
        if relative == "notes.txt":
            continue
        assert found[relative]["sha256"] == expected["sha256"], relative
        assert found[relative]["bytes"] == expected["bytes"], relative
        assert found[relative]["file_id"]
        assert found[relative]["origin"] == "unknown"
        assert found[relative]["rights"] == "unknown"
        assert found[relative]["labels"] == "unknown"
    # the source extension casing is preserved even though matching is case insensitive
    assert found["b.PNG"]["extension"] == ".PNG"
    assert receipt["skipped_items"][0]["relative_path"] == "notes.txt"
    assert receipt["skipped_items"][0]["reason"] == "unsupported_extension"

    # nothing in the receipt leaks an absolute source path
    assert str(media) not in json.dumps(receipt, ensure_ascii=False)
    assert receipt["product_gate0"] is False
    assert receipt["samples_frozen"] is False
    assert receipt["quality_claim"] == "NONE_INVENTORY_IS_NOT_QUALITY_EVIDENCE"


def test_inventory_never_claims_quality_or_a_frozen_sample(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"x" * 32})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["samples_frozen"] is False
    assert receipt["stage_pass_claim"] is False
    assert receipt["budgets"] == {
        "model_actions": 0,
        "effective_full_checkpoints": 0,
        "product_runtime_seconds": 0,
        "service_starts": 0,
        "network_calls": 0,
        "subprocess_starts": 0,
    }
    assert receipt["cleanup"]["source_files_modified"] == 0
    assert receipt["cleanup"]["source_files_deleted"] == 0
    assert any("origin" in item for item in receipt["unknown_coverage"])
    assert any("rights" in item for item in receipt["unknown_coverage"])


# --------------------------------------------------------------------------
# refusals before any media access
# --------------------------------------------------------------------------


def test_a_rejected_guard_reads_zero_media_bytes(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"secret-media-bytes" * 4})
    broken = authority_tree(tmp_path / "authority")
    (broken / "reports/unified-media/independent-live-15/coverage.json").write_text(
        "{ not json", encoding="utf-8"
    )
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=broken,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )

    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "handoff_guard_rejected"
    assert receipt["media_access"]["media_bytes_read"] == 0
    assert receipt["media_access"]["files_hashed"] == 0
    assert receipt["items"] == []
    assert not access_since(_before, str(media)), access_since(_before, str(media))


def test_a_missing_root_is_refused_without_media_access(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", tmp_path / "does-not-exist", small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "root_missing"
    assert receipt["media_access"]["media_bytes_read"] == 0
    assert not access_since(_before, str(media))


def test_a_binding_without_the_required_fields_is_refused(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    del binding["frozen_proof_hashes"]
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "binding_missing_fields"
    assert not access_since(_before, str(media))


def test_a_binding_with_a_wrong_script_hash_is_refused(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["handoff_script_sha256"] = "0" * 64
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "binding_mismatch"
    assert not access_since(_before, str(media))


def test_a_binding_with_wrong_frozen_proof_hashes_is_refused(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["frozen_proof_hashes"] = dict(pins["proofs"])
    binding["frozen_proof_hashes"]["scope_approval"] = {
        "path": binding["frozen_proof_hashes"]["scope_approval"]["path"],
        "sha256": "0" * 64,
    }
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "binding_mismatch"
    assert not access_since(_before, str(media))


def test_a_terminal_receipt_is_never_overwritten(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt_path = tmp_path / "reports" / "receipt.json"
    first = inventory.run_inventory(
        binding_path=binding_path,
        receipt_path=receipt_path,
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert first["decision"] == "INVENTORY_COMPLETE"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("previous terminal receipt", encoding="utf-8")

    second = inventory.run_inventory(
        binding_path=binding_path,
        receipt_path=receipt_path,
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert second["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert second["refusal"]["reason"] == "terminal_receipt_already_exists"
    assert second["write_receipt"] is False
    assert receipt_path.read_text(encoding="utf-8") == "previous terminal receipt"


def test_a_receipt_outside_the_report_root_is_refused(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    outside = tmp_path / "outside" / "receipt.json"

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=outside,
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
    assert receipt["refusal"]["reason"] == "receipt_outside_report_root"
    assert receipt["write_receipt"] is False
    assert not outside.exists()


# --------------------------------------------------------------------------
# bounded behaviour
# --------------------------------------------------------------------------


def test_the_hash_budget_boundary_is_exact(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 10, "b.jpg": b"b" * 10, "c.jpg": b"c" * 10})
    child_path = make_child(tmp_path / "child.json", media, small_limits(max_files_hashed=2))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 2
    assert receipt["counts"]["skipped_by_reason"] == {"hash_budget_exhausted": 1}
    assert receipt["media_access"]["files_hashed"] == 2


def test_one_over_the_hash_budget_is_reported_not_hashed(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 10, "b.jpg": b"b" * 10, "c.jpg": b"c" * 10})
    child_path = make_child(tmp_path / "child.json", media, small_limits(max_files_hashed=1))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 1
    assert receipt["counts"]["skipped_by_reason"] == {"hash_budget_exhausted": 2}
    assert receipt["decision"] == "INVENTORY_COMPLETE"


def test_the_total_byte_budget_boundary_is_exact(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 10, "b.jpg": b"b" * 20})
    exact = small_limits(max_total_bytes_hashed=30)
    child_path = make_child(tmp_path / "child.json", media, exact)
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 2
    assert receipt["media_access"]["total_bytes_hashed"] == 30


def test_one_over_the_total_byte_budget_is_skipped(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 10, "b.jpg": b"b" * 20})
    child_path = make_child(tmp_path / "child.json", media, small_limits(max_total_bytes_hashed=29))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 1
    assert receipt["counts"]["skipped_by_reason"] == {"total_bytes_budget_exhausted": 1}


def test_one_over_the_single_file_budget_is_skipped(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 10})
    child_path = make_child(tmp_path / "child.json", media, small_limits(max_single_file_bytes=9))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 0
    assert receipt["counts"]["skipped_by_reason"] == {"single_file_over_budget": 1}
    assert receipt["media_access"]["media_bytes_read"] == 0


def test_the_directory_entry_budget_stops_the_walk(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 8, "b.jpg": b"b" * 8, "c.jpg": b"c" * 8})
    child_path = make_child(tmp_path / "child.json", media, small_limits(max_directory_entries=2))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["media_access"]["traversal_stop_reason"] == "directory_entry_budget_exhausted"
    assert receipt["decision"] == "INVENTORY_PARTIAL_BUDGET_EXHAUSTED"
    assert receipt["media_access"]["entries_examined"] == 2


def test_the_wall_budget_trips_inside_hashing(tmp_path):
    media = tmp_path / "media"
    payload = b"a" * (3 * 1024 * 1024)
    write_media(media, {"big.mp4": payload})

    class FakeClock:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            value = self.now
            self.now += 1.0
            return value

    child_path = make_child(
        tmp_path / "child.json", media, small_limits(wall_seconds=2, read_chunk_bytes=1024 * 1024)
    )
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
        clock=FakeClock(),
    )
    assert receipt["media_access"]["traversal_stop_reason"] == "wall_budget_exhausted_during_hashing"
    assert receipt["decision"] == "INVENTORY_PARTIAL_BUDGET_EXHAUSTED"
    assert receipt["media_access"]["files_hashed"] == 0
    assert receipt["counts"]["eligible"] == 0


def test_reads_use_the_declared_chunk_size(tmp_path, monkeypatch):
    media = tmp_path / "media"
    chunk = 1024 * 1024
    payload = b"z" * (2 * chunk + 17)
    write_media(media, {"big.mp4": payload})
    child_path = make_child(tmp_path / "child.json", media, small_limits(read_chunk_bytes=chunk))
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    reads = []
    real_open = builtins.open

    def spy(file, *args, **kwargs):
        handle = real_open(file, *args, **kwargs)
        if str(file) == str(media / "big.mp4"):
            class Wrapper:
                def __init__(self, inner):
                    self._inner = inner

                def read(self, size=-1):
                    reads.append(size)
                    return self._inner.read(size)

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return self._inner.__exit__(*exc)

                def __getattr__(self, name):
                    return getattr(self._inner, name)

            return Wrapper(handle)
        return handle

    monkeypatch.setattr(builtins, "open", spy)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    monkeypatch.undo()
    assert receipt["counts"]["eligible"] == 1
    assert receipt["items"][0]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert reads and set(reads) == {chunk}
    assert len(reads) == 4  # three full chunks plus the terminating empty read
    assert receipt["media_access"]["read_chunk_bytes"] == chunk


# --------------------------------------------------------------------------
# filesystem safety and immutability
# --------------------------------------------------------------------------


def test_a_symlink_escaping_the_approved_root_is_rejected(tmp_path):
    media = tmp_path / "media"
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside-secret-bytes")
    write_media(media, {"a.jpg": b"inside-bytes"})
    os.symlink(outside, media / "escape.jpg")
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["counts"]["eligible"] == 1
    assert receipt["counts"]["skipped_by_reason"] == {"symlink_escape_rejected": 1}
    outside_sha = hashlib.sha256(b"outside-secret-bytes").hexdigest()
    assert all(item["sha256"] != outside_sha for item in receipt["items"])
    assert not access_since(_before, str(outside))


def test_a_file_changed_during_the_inventory_is_excluded(tmp_path, monkeypatch):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"original-bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    real_hash = inventory.sha256_file

    def mutating_hash(path, chunk_bytes, deadline, clock, already=0, max_total=None):
        result = real_hash(path, chunk_bytes, deadline, clock, already, max_total)
        Path(path).write_bytes(b"changed-after-the-read")
        return result

    monkeypatch.setattr(inventory, "sha256_file", mutating_hash)
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    monkeypatch.undo()
    assert receipt["counts"]["eligible"] == 0
    assert receipt["counts"]["skipped_by_reason"] == {"changed_during_inventory": 1}
    assert receipt["media_access"]["files_hashed"] == 0


def test_the_inventory_never_mutates_the_source(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"a" * 32, "b.mp4": b"b" * 64, "sub/c.png": b"c" * 16})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)

    def snapshot():
        state = {}
        for path in sorted(media.rglob("*")):
            if path.is_file():
                info = path.stat()
                state[str(path)] = (
                    info.st_size,
                    info.st_mtime_ns,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
        return state

    before = snapshot()
    receipt, _before = run_and_watch(
        binding_path=binding_path,
        receipt_path=tmp_path / "reports" / "receipt.json",
        package_root=ROOT,
        guard_root=ROOT,
        child_path=child_path,
        pins=pins,
        report_root=tmp_path / "reports",
    )
    assert receipt["decision"] == "INVENTORY_COMPLETE"
    assert snapshot() == before
    assert receipt["cleanup"]["source_files_modified"] == 0
    assert receipt["cleanup"]["deletions_performed"] == 0


# --------------------------------------------------------------------------
# the public command line
# --------------------------------------------------------------------------


def test_the_cli_exposes_only_the_binding_and_the_receipt():
    process = subprocess.run(
        [sys.executable, "-B", "tools/s3_asset_inventory.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stderr
    assert "--binding" in process.stdout
    assert "--receipt" in process.stdout
    for forbidden in ("--root", "--limits", "--pins", "--override"):
        assert forbidden not in process.stdout


def test_the_cli_refuses_a_broken_binding_without_reading_media(tmp_path):
    media = tmp_path / "media"
    write_media(media, {"a.jpg": b"bytes"})
    child_path = make_child(tmp_path / "child.json", media, small_limits())
    pins = fixture_pins(child_path)
    binding_path = make_binding(tmp_path / "preflight.json", child_path, pins)
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["scope_approval_sha256"] = "0" * 64
    binding_path.write_text(json.dumps(binding), encoding="utf-8")

    # the receipt has to live under the tool's own report root, so the CLI test
    # uses a self-created sub directory there and removes exactly that file.
    receipt_rel = ROOT / inventory.REPORT_ROOT_REL / "selftest-cli" / "receipt.json"
    assert not receipt_rel.exists()
    before = len(_ACCESS)
    try:
        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "tools/s3_asset_inventory.py",
                "--binding",
                str(binding_path),
                "--receipt",
                str(receipt_rel),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert process.returncode == 1, process.stdout
        assert "refusal" in process.stderr
        payload = json.loads(receipt_rel.read_text(encoding="utf-8"))
        assert payload["decision"] == "INVENTORY_REFUSED_PRE_MEDIA_ACCESS"
        assert payload["refusal"]["reason"] == "binding_mismatch"
        assert payload["media_access"]["media_bytes_read"] == 0
        assert payload["items"] == []
    finally:
        if receipt_rel.exists():
            receipt_rel.unlink()
        if receipt_rel.parent.exists():
            receipt_rel.parent.rmdir()
    assert not access_since(before, str(media)), access_since(before, str(media))
