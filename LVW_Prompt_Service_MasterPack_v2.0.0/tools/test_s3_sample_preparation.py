#!/usr/bin/env python3
"""Tests for tools/s3_sample_preparation.py (S3-PREP-C preparation only).

The suite never touches the approved local media root.  Every test builds a
fresh synthetic package root, a synthetic source root and synthetic media
under pytest's ``tmp_path`` and drives the tool through its public entry
points with injected fixtures.

A process wide audit hook records every ``open`` / ``os.scandir`` under the
real approved media root so the suite can *prove* that no test ever reaches
the real 32 candidates.

Run: python3 -B -m pytest tools/test_s3_sample_preparation.py -q
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

import s3_sample_preparation as s3prep  # noqa: E402

REAL_MEDIA_MARKER = "/mnt/c/workSpace/videoWorkLine"
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

_ACCESS: list = []
_REAL_OPEN = builtins.open
_REAL_SCANDIR = os.scandir
_installed = False


def _audit_open(file, *args, **kwargs):
    try:
        text = os.fspath(file)
    except TypeError:
        text = ""
    if isinstance(text, str) and text.startswith(REAL_MEDIA_MARKER):
        _ACCESS.append(text)
    return _REAL_OPEN(file, *args, **kwargs)


def _audit_scandir(path="."):
    try:
        text = os.fspath(path)
    except TypeError:
        text = ""
    if isinstance(text, str) and text.startswith(REAL_MEDIA_MARKER):
        _ACCESS.append(text)
    return _REAL_SCANDIR(path)


@pytest.fixture(autouse=True)
def _audit_guard():
    global _installed
    if not _installed:
        builtins.open = _audit_open
        os.scandir = _audit_scandir
        _installed = True
    before = len(_ACCESS)
    yield
    assert _ACCESS[before:] == [], "the suite must never reach the real media root"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_jpeg(path: Path, size=(64, 48), color=(190, 70, 60)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(str(path), format="JPEG", quality=90)


def make_png(path: Path, size=(48, 64), color=(60, 60, 190)) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(str(path), format="PNG")


def make_mp4(path: Path, *, seconds=4.0, size="320x192", rate=12, source="testsrc2") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    separator = ":" if source.startswith("color=") else "="
    argv = [
        FFMPEG, "-nostdin", "-v", "error", "-y",
        "-f", "lavfi", "-i", "%s%s%s:r=%d:d=%s" % (source, separator, size, rate, seconds),
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1",
        "-preset", "ultrafast", "-crf", "35", str(path),
    ]
    subprocess.run(argv, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def stub_guard(_root):
    return {
        "decision": "HANDOFF_READINESS_VERIFIED",
        "authority": "FIXTURE_NON_AUTHORITY",
        "summary": {"checks": 139, "passed": 139, "failed": 0},
        "checks": [],
    }


class Package:
    """A synthetic package root with a synthetic source root."""

    def __init__(self, root: Path):
        self.root = root
        self.source = root / "source"
        self.source.mkdir(parents=True, exist_ok=True)
        self.entries = []

    def add(self, relative_path: str, media_kind: str, *, override_sha: str = None,
            override_bytes: int = None) -> dict:
        target = self.source / relative_path
        entry = {
            "file_id": sha256_bytes(("id:%s" % relative_path).encode("utf-8")),
            "relative_path": relative_path,
            "extension": Path(relative_path).suffix,
            "bytes": override_bytes if override_bytes is not None else target.stat().st_size,
            "sha256": override_sha if override_sha is not None else sha256_path(target),
            "origin": "unknown",
            "rights": "unknown",
            "labels": "unknown",
            "media_kind": media_kind,
        }
        self.entries.append(entry)
        return entry

    def write_documents(self, *, limits=None, holdout_count=11, selection=None,
                        child_mutator=None, catalog_mutator=None) -> dict:
        selection = self.entries if selection is None else selection
        limits = dict(s3prep.EXPECTED_LIMITS) if limits is None else dict(limits)
        holdout_hashes = [
            sha256_bytes(("holdout:%d" % index).encode("utf-8")) for index in range(holdout_count)
        ]
        freeze_own = sha256_bytes(b"freeze-manifest-self-hash")
        assets_manifest = sha256_bytes(b"freeze-assets-manifest-hash")
        child = {
            "kind": s3prep.EXPECTED_CHILD_KIND,
            "child_id": s3prep.EXPECTED_CHILD_ID,
            "state": "AUTHORIZED_PENDING_CANDIDATE_AND_TOOL_PREFLIGHT",
            "source_root": str(self.source),
            "catalog": s3prep.CATALOG_REL,
            "catalog_sha256": None,
            "holdout_manifest": s3prep.HOLDOUT_REL,
            "holdout_manifest_sha256": None,
            "holdout_content_sha256": holdout_hashes + [freeze_own, assets_manifest],
            "selected_files": selection,
            "limits": limits,
            "quality_frozen": False,
        }
        if child_mutator is not None:
            child_mutator(child)
        catalog = {
            "kind": "DERIVED_S3_PREPARATION_CANDIDATE_CATALOG_NOT_QUALITY_FREEZE",
            "sample_selection_frozen": False,
            "sample_labels_verified": False,
            "origin_and_rights_verified": False,
            "model_execution_authorized_by_catalog": False,
            "excluded_private_labelled_ids": [],
            "excluded_private_labelled_sha256": [],
            "items": [dict(entry) for entry in selection],
        }
        if catalog_mutator is not None:
            catalog_mutator(catalog)
        catalog_path = self.root / s3prep.CATALOG_REL
        write_json(catalog_path, catalog)
        child["catalog_sha256"] = sha256_path(catalog_path)
        holdout_path = self.root / s3prep.HOLDOUT_REL
        write_json(
            holdout_path,
            {
                "kind": "PRE_INFERENCE_HOLDOUT_FREEZE",
                "expected_sha256": freeze_own,
                "assets_manifest_sha256": assets_manifest,
                "videos": [
                    {"id": "V%02d" % (index + 1), "video_sha256": value}
                    for index, value in enumerate(holdout_hashes)
                ],
            },
        )
        child["holdout_manifest_sha256"] = sha256_path(holdout_path)
        packet = self.root / s3prep.PACKET_REL
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text("# synthetic packet\n", encoding="utf-8")
        for relative in (s3prep.SCRIPT_REL, s3prep.TEST_REL, s3prep.BRIDGE_RUNNER_REL):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        child_path = self.root / s3prep.CHILD_REL
        write_json(child_path, child)
        return {"child": child, "child_path": child_path}

    def runtime_root(self, name="run-01") -> Path:
        return self.root / s3prep.RUNTIME_REL / name


def blob_reader(package_root: Path):
    def reader(_sha, relative):
        path = Path(package_root) / relative
        return path.read_bytes() if path.is_file() else b""

    return reader


def run_preflight(package: Package, *, candidate="a" * 40, runtime_root=None, **kwargs):
    runtime_root = runtime_root or package.runtime_root()
    return s3prep.build_preflight(
        package_root=package.root,
        child_path=package.root / s3prep.CHILD_REL,
        candidate_sha=candidate,
        runtime_root=runtime_root,
        guard_evaluator=stub_guard,
        blob_reader=blob_reader(package.root),
        commit_exists_reader=lambda _sha: True,
        **kwargs,
    )


def real_adapter() -> s3prep.MediaAdapter:
    return s3prep.MediaAdapter(Path(FFMPEG), Path(FFPROBE))


def run_prepare(package: Package, *, limits=None, clock=None, receipt_name="receipt.json"):
    limits = dict(s3prep.EXPECTED_LIMITS) if limits is None else dict(limits)
    child = json.loads((package.root / s3prep.CHILD_REL).read_text(encoding="utf-8"))
    child["limits"] = limits
    runtime_root = package.runtime_root()
    receipt_path = package.root / s3prep.REPORT_ROOT_REL / receipt_name
    receipt = s3prep.prepare(
        package_root=package.root,
        child=child,
        runtime_root=runtime_root,
        adapter=real_adapter(),
        receipt_path=receipt_path,
        clock=clock or _normal_clock(),
    )
    return receipt, runtime_root


def _normal_clock():
    import time

    return time.monotonic


# ---------------------------------------------------------------------------
# path policy
# ---------------------------------------------------------------------------
def test_path_policy_refuses_symlink_traversal_and_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (root / "inside.txt").write_text("inside", encoding="utf-8")
    os.symlink(str(outside), str(root / "escape.link"))

    with pytest.raises(s3prep.PolicyError):
        s3prep.resolve_source_path(root, "escape.link")
    with pytest.raises(s3prep.PolicyError):
        s3prep.resolve_source_path(root, "../outside.txt")
    with pytest.raises(s3prep.PolicyError):
        s3prep.resolve_source_path(root, "/etc/hostname")
    with pytest.raises(s3prep.PolicyError):
        s3prep.resolve_source_path(root, "C:/Windows")
    resolved = s3prep.resolve_source_path(root, "inside.txt")
    assert resolved.read_text(encoding="utf-8") == "inside"


def test_policy_self_check_is_measured_and_cleans_up():
    result = s3prep.policy_self_check()
    assert result["all_passed"] is True
    assert result["temporary_root_removed"] is True
    assert result["symlink_escape_rejected"] is True
    assert result["traversal_rejected"] is True


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def _standard_package(tmp_path, images=20, videos=12):
    package = Package(tmp_path / "pkg")
    for index in range(images):
        make_jpeg(
            package.source / ("img-%02d.jpg" % index),
            size=(32 + index, 24 + index),
            color=(index * 3 % 250, 40 + index, 60),
        )
        package.add("img-%02d.jpg" % index, "image")
    for index in range(videos):
        make_mp4(
            package.source / ("vid-%02d.mp4" % index),
            seconds=2.0 + index * 0.1,
            size="320x%d" % (192 + index),
        )
        package.add("vid-%02d.mp4" % index, "video")
    return package


def test_preflight_accepts_exactly_the_frozen_selection(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_PASSED", preflight["checks"]
    assert preflight["summary"]["failed"] == 0
    assert preflight["selection"]["count"] == 32
    assert preflight["selection"]["images"] == 20
    assert preflight["selection"]["videos"] == 12


def test_preflight_rejects_one_over_the_frozen_selection(tmp_path):
    package = _standard_package(tmp_path)
    make_jpeg(package.source / "extra.jpg")
    extra = package.add("extra.jpg", "image")
    package.write_documents(selection=package.entries + [extra])
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "child.selection_count" in failed


def test_preflight_rejects_one_under_the_frozen_selection(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents(selection=package.entries[:-1])
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "child.selection_count" in failed


def test_preflight_rejects_child_limit_drift(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    child_path = package.root / s3prep.CHILD_REL
    child = json.loads(child_path.read_text(encoding="utf-8"))
    child["limits"]["wall_seconds"] = 999999
    write_json(child_path, child)
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "child.limits_frozen" in failed


def test_preflight_rejects_catalog_drift(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    catalog_path = package.root / s3prep.CATALOG_REL
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["items"][0]["bytes"] = 1
    write_json(catalog_path, catalog)
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "catalog.sha256" in failed


def test_preflight_rejects_candidate_drift(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    preflight = s3prep.build_preflight(
        package_root=package.root,
        child_path=package.root / s3prep.CHILD_REL,
        candidate_sha="b" * 40,
        runtime_root=package.runtime_root(),
        guard_evaluator=stub_guard,
        blob_reader=lambda _sha, _rel: b"",
        commit_exists_reader=lambda _sha: True,
    )
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "code.script_in_candidate" in failed
    assert "code.test_in_candidate" in failed
    assert "code.working_tree_matches_candidate" in failed


def test_preflight_rejects_a_holdout_overlap(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents(
        child_mutator=lambda child: child["holdout_content_sha256"].append(
            child["selected_files"][0]["sha256"]
        )
    )
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "holdout.no_selected_overlap" in failed


def test_preflight_rejects_a_missing_runtime_parent(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    outside = tmp_path / "not-the-ignored-root"
    preflight = run_preflight(package, runtime_root=outside)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "runtime.under_ignored_root" in failed


def test_preflight_rejects_a_guard_rejection(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    preflight = s3prep.build_preflight(
        package_root=package.root,
        child_path=package.root / s3prep.CHILD_REL,
        candidate_sha="a" * 40,
        runtime_root=package.runtime_root(),
        guard_evaluator=lambda _root: {"decision": "HANDOFF_READINESS_REJECTED",
                                       "summary": {"failed": 1}, "checks": []},
        blob_reader=blob_reader(package.root),
        commit_exists_reader=lambda _sha: True,
    )
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "guard.handoff_readiness" in failed


def test_preflight_refuses_to_overwrite_an_existing_file(tmp_path, monkeypatch):
    package = _standard_package(tmp_path)
    package.write_documents()
    target = package.root / s3prep.REPORT_ROOT_REL / "preflight.json"
    write_json(target, {"decision": "PREFLIGHT_PASSED"})
    args = type("Args", (), {})()
    args.child = str(package.root / s3prep.CHILD_REL)
    args.candidate = "a" * 40
    args.preflight = str(target)
    args.runtime_output = str(package.runtime_root())
    assert s3prep.command_preflight(args, package_root=package.root) == 1
    assert json.loads(target.read_text(encoding="utf-8"))["decision"] == "PREFLIGHT_PASSED"


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def _small_package(tmp_path, **kwargs):
    package = Package(tmp_path / "pkg")
    make_jpeg(package.source / "a.jpg")
    package.add("a.jpg", "image")
    make_mp4(package.source / "b.mp4")
    package.add("b.mp4", "video")
    package.write_documents(**kwargs)
    return package


def test_run_produces_previews_and_conserves_the_counts(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    assert receipt["decision"] == "PREPARATION_COMPLETE_READY_FOR_REVIEW"
    assert receipt["counts"]["selected_total"] == 2
    assert receipt["counts"]["eligible"] == 2
    assert receipt["counts"]["not_eligible"] == 0
    assert receipt["counts"]["not_run"] == 0
    assert receipt["counts"]["conservation_ok"] is True
    assert receipt["budget"]["source_files_hashed"] == 2
    assert receipt["budget"]["image_decode_calls"] == 1
    assert receipt["budget"]["ffprobe_calls"] == 1
    assert receipt["budget"]["ffmpeg_frame_calls"] == 4
    assert receipt["budget"]["model_actions"] == 0
    assert receipt["budget"]["gpu_actions"] == 0
    assert receipt["budget"]["network_calls"] == 0
    assert receipt["budget"]["full_product_checkpoints"] == 0
    assert receipt["budget"]["decoder_disk_io_bytes"] == "NOT_MEASURED_NOT_CLAIMED"
    assert (runtime_root / "index.html").is_file()
    image_entry = receipt["candidates"][0]
    assert (runtime_root / "previews" / ("%s.jpg" % image_entry["file_id"])).is_file()
    assert (runtime_root / "contactsheets").is_dir()
    assert (runtime_root / "runtime-receipt.json").is_file()
    assert receipt["runtime"]["retained"] is True
    assert receipt["runtime"]["is_zero_residue"] is False


def test_run_cleans_the_staging_directory_and_measures_it(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    assert receipt["cleanup"]["staging_removed"] is True
    assert receipt["cleanup"]["staging_residual_entries"] == 0
    assert receipt["cleanup"]["temporary_directories_removed"] == 1
    assert receipt["cleanup"]["source_files_modified"] == 0
    assert receipt["cleanup"]["source_files_deleted"] == 0
    assert not (runtime_root / "staging").exists()
    assert receipt["cleanup"]["subprocesses_started"] == 5


def test_run_does_not_modify_the_source(tmp_path):
    package = _small_package(tmp_path)
    before = {
        path.name: (sha256_path(path), path.stat().st_mtime_ns)
        for path in sorted(package.source.rglob("*"))
        if path.is_file()
    }
    run_prepare(package)
    after = {
        path.name: (sha256_path(path), path.stat().st_mtime_ns)
        for path in sorted(package.source.rglob("*"))
        if path.is_file()
    }
    assert before == after


def test_changed_source_is_terminal_for_the_whole_run(tmp_path):
    package = Package(tmp_path / "pkg")
    make_jpeg(package.source / "a.jpg")
    package.add("a.jpg", "image")
    make_jpeg(package.source / "b.jpg")
    package.add("b.jpg", "image", override_sha="f" * 64)
    make_jpeg(package.source / "c.jpg")
    package.add("c.jpg", "image")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    assert receipt["decision"] == "SOURCE_CHANGED_TERMINAL"
    assert receipt["counts"]["eligible"] == 1
    assert receipt["counts"]["not_eligible"] == 1
    assert receipt["counts"]["not_run"] == 1
    assert receipt["counts"]["conservation_ok"] is True
    reasons = receipt["counts"]["not_run_by_reason"]
    assert reasons.get("source_changed_terminal") == 1
    changed = [item for item in receipt["candidates"] if item.get("reason") == "SOURCE_CHANGED"]
    assert len(changed) == 1


def test_corrupt_media_is_not_eligible(tmp_path):
    package = Package(tmp_path / "pkg")
    broken = package.source / "broken.jpg"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"NOT-A-JPEG" * 32)
    package.add("broken.jpg", "image")
    broken_video = package.source / "broken.mp4"
    broken_video.write_bytes(b"NOT-AN-MP4" * 64)
    package.add("broken.mp4", "video")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    assert receipt["counts"]["eligible"] == 0
    assert receipt["counts"]["not_eligible"] == 2
    assert receipt["counts"]["conservation_ok"] is True
    reasons = receipt["counts"]["not_eligible_by_reason"]
    assert "image_decode_failed:UnidentifiedImageError" in reasons
    assert "video_probe_failed" in reasons


def test_symlinked_candidate_is_refused(tmp_path):
    package = Package(tmp_path / "pkg")
    make_jpeg(package.source / "real.jpg")
    os.symlink(str(package.source / "real.jpg"), str(package.source / "link.jpg"))
    entry = package.add("link.jpg", "image")
    entry["bytes"] = (package.source / "real.jpg").stat().st_size
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    assert receipt["counts"]["eligible"] == 0
    assert receipt["counts"]["not_eligible"] == 1
    assert "source_path_symlink_rejected" in receipt["counts"]["not_eligible_by_reason"]


def test_short_video_gets_fewer_independent_sample_points(tmp_path):
    package = Package(tmp_path / "pkg")
    make_mp4(package.source / "short.mp4", seconds=0.4, rate=12)
    package.add("short.mp4", "video")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    candidate = receipt["candidates"][0]
    assert candidate["status"] == "eligible"
    offsets = candidate["sampling"]["requested_offsets_seconds"]
    assert len(offsets) < 4
    assert any(
        warning.startswith("sample_point_dropped_not_independent")
        for warning in candidate["warnings"]
    )


def test_static_video_discloses_duplicate_frames(tmp_path):
    package = Package(tmp_path / "pkg")
    make_mp4(package.source / "static.mp4", seconds=4.0, rate=5, source="color=c=navy")
    package.add("static.mp4", "video")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    candidate = receipt["candidates"][0]
    assert candidate["status"] == "eligible"
    frames = candidate["sampling"]["frames"]
    assert len(frames) == 4
    assert candidate["sampling"]["distinct_frame_hashes"] == 1
    assert any(
        warning.startswith("duplicate_frame_content_matches") for warning in candidate["warnings"]
    )


def test_video_over_the_duration_limit_is_not_eligible(tmp_path):
    package = Package(tmp_path / "pkg")
    make_mp4(package.source / "long.mp4", seconds=61.0, rate=2)
    package.add("long.mp4", "video")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    assert receipt["candidates"][0]["status"] == "not_eligible"
    assert receipt["candidates"][0]["reason"] == "video_duration_over_limit"


def test_image_over_the_pixel_limit_is_not_eligible(tmp_path):
    package = Package(tmp_path / "pkg")
    from PIL import Image

    big = package.source / "big.jpg"
    big.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (6400, 6400), (10, 20, 30)).save(str(big), format="JPEG", quality=20)
    package.add("big.jpg", "image")
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    assert receipt["candidates"][0]["status"] == "not_eligible"
    assert receipt["candidates"][0]["reason"] == "image_pixels_over_limit"


def test_wall_budget_marks_the_remaining_candidates_not_run(tmp_path):
    package = _small_package(tmp_path)

    class Clock:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            return 0.0 if self.calls == 1 else 100000.0

    receipt, _runtime = run_prepare(package, clock=Clock())
    assert receipt["counts"]["eligible"] == 0
    assert receipt["counts"]["not_run"] == 2
    assert receipt["counts"]["conservation_ok"] is True
    assert receipt["counts"]["not_run_by_reason"].get("wall_budget_exhausted") == 2
    assert receipt["budget"]["source_files_hashed"] == 0


def test_output_budget_stops_the_run(tmp_path):
    package = _small_package(tmp_path)
    limits = dict(s3prep.EXPECTED_LIMITS)
    limits["output_bytes"] = 512
    receipt, _runtime = run_prepare(package, limits=limits)
    assert receipt["counts"]["conservation_ok"] is True
    assert receipt["counts"]["not_run"] >= 1
    assert receipt["counts"]["not_run_by_reason"].get("output_budget_exhausted") == 1
    assert receipt["decision"] == "PREPARATION_FAILED_OUTPUT_BUDGET_EXCEEDED"


def test_terminal_receipt_is_never_overwritten(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    child = json.loads((package.root / s3prep.CHILD_REL).read_text(encoding="utf-8"))
    receipt_path = package.root / s3prep.REPORT_ROOT_REL / "receipt.json"
    with pytest.raises(s3prep.PreflightError):
        s3prep.prepare(
            package_root=package.root,
            child=child,
            runtime_root=runtime_root,
            adapter=real_adapter(),
            receipt_path=receipt_path,
        )


def test_run_refuses_an_existing_runtime_root(tmp_path):
    package = _small_package(tmp_path)
    package.runtime_root().mkdir(parents=True)
    child = json.loads((package.root / s3prep.CHILD_REL).read_text(encoding="utf-8"))
    with pytest.raises(s3prep.PreflightError):
        s3prep.prepare(
            package_root=package.root,
            child=child,
            runtime_root=package.runtime_root(),
            adapter=real_adapter(),
            receipt_path=package.root / s3prep.REPORT_ROOT_REL / "receipt.json",
        )


# ---------------------------------------------------------------------------
# CLI level refusals
# ---------------------------------------------------------------------------
def _cli_args(package, **overrides):
    args = type("Args", (), {})()
    args.child = str(package.root / s3prep.CHILD_REL)
    args.candidate = "a" * 40
    args.preflight = str(package.root / s3prep.REPORT_ROOT_REL / "preflight.json")
    args.runtime_output = str(package.runtime_root())
    args.receipt = str(package.root / s3prep.REPORT_ROOT_REL / "receipt.json")
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_cli_refuses_a_rejected_preflight_without_touching_a_source(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    write_json(
        package.root / s3prep.REPORT_ROOT_REL / "preflight.json",
        {"decision": "PREFLIGHT_REJECTED", "candidate": {"sha": "a" * 40}},
    )
    calls = []
    monkeypatch.setattr(
        s3prep.MediaAdapter, "probe_video", lambda self, *a, **k: calls.append(a)
    )
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert calls == []
    assert not package.runtime_root().exists()
    assert not (package.root / s3prep.REPORT_ROOT_REL / "receipt.json").exists()


def test_cli_refuses_candidate_drift(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    write_json(
        package.root / s3prep.REPORT_ROOT_REL / "preflight.json",
        {"decision": "PREFLIGHT_PASSED", "candidate": {"sha": "c" * 40}},
    )
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert not package.runtime_root().exists()


def test_cli_refuses_child_drift(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    write_json(
        package.root / s3prep.REPORT_ROOT_REL / "preflight.json",
        {
            "decision": "PREFLIGHT_PASSED",
            "candidate": {"sha": "a" * 40},
            "child": {"sha256": "0" * 64},
        },
    )
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert not package.runtime_root().exists()


def test_cli_refuses_catalog_drift(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    write_json(
        package.root / s3prep.REPORT_ROOT_REL / "preflight.json",
        {
            "decision": "PREFLIGHT_PASSED",
            "candidate": {"sha": "a" * 40},
            "child": {"sha256": sha256_path(package.root / s3prep.CHILD_REL)},
            "catalog": {"sha256": "1" * 64},
        },
    )
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert not package.runtime_root().exists()


def test_cli_refuses_an_existing_terminal_receipt(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    receipt_path = package.root / s3prep.REPORT_ROOT_REL / "receipt.json"
    write_json(receipt_path, {"decision": "PREPARATION_COMPLETE_READY_FOR_REVIEW"})
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["decision"] == (
        "PREPARATION_COMPLETE_READY_FOR_REVIEW"
    )


# ---------------------------------------------------------------------------
# artefact discipline
# ---------------------------------------------------------------------------
def test_preview_index_declares_the_boundary_and_uses_relative_links(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    index = (runtime_root / "index.html").read_text(encoding="utf-8")
    assert "独立预标前素材预览" in index
    assert "不是项目识别输出" in index
    assert 'href="contactsheets/' in index
    assert 'href="previews/' in index
    assert str(package.root) not in index
    assert str(runtime_root) not in index


def test_committed_receipt_carries_no_absolute_path_and_no_exif(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    text = json.dumps(receipt, ensure_ascii=False)
    assert str(package.source) not in text
    assert str(runtime_root) not in text
    assert "exif" not in text.lower() or "exif_orientation_applied" in text
    assert receipt["runtime"]["absolute_path_recorded_in"].endswith("runtime-receipt.json")


def test_runtime_receipt_keeps_the_absolute_local_paths(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    runtime_receipt = json.loads(
        (runtime_root / "runtime-receipt.json").read_text(encoding="utf-8")
    )
    assert runtime_receipt["absolute_runtime_root"] == str(runtime_root)
    assert runtime_receipt["absolute_source_root"] == str(package.source)
    assert runtime_receipt["absolute_preview_index"] == str(runtime_root / "index.html")


def test_no_semantic_answer_is_generated(tmp_path):
    package = _small_package(tmp_path)
    receipt, runtime_root = run_prepare(package)
    semantic_words = ("person", "scene", "action", "人物", "场景", "动作", "标签",
                      "caption", "description")
    for candidate in receipt["candidates"]:
        text = json.dumps(candidate, ensure_ascii=False)
        for word in semantic_words:
            assert word not in text
    index = (runtime_root / "index.html").read_text(encoding="utf-8")
    for word in semantic_words:
        assert word not in index
    assert receipt["quality_claim"] == "NONE_ELIGIBILITY_IS_NOT_QUALITY_EVIDENCE"
    assert receipt["stage_pass_claim"] is False
    assert receipt["product_gate0"] is False
    assert receipt["prelabel_stage_complete"] is False


# ---------------------------------------------------------------------------
# full scale rehearsal and the end to end CLI
# ---------------------------------------------------------------------------
def test_full_scale_rehearsal_over_32_synthetic_candidates(tmp_path):
    """The closest rehearsal of the real run: 20 images + 12 videos."""
    package = _standard_package(tmp_path)
    package.write_documents()
    receipt, runtime_root = run_prepare(package)
    assert receipt["counts"]["selected_total"] == 32
    assert receipt["counts"]["conservation_ok"] is True
    assert receipt["counts"]["eligible"] == 32
    assert receipt["counts"]["not_eligible"] == 0
    assert receipt["counts"]["not_run"] == 0
    assert receipt["budget"]["source_files_hashed"] == 32
    assert receipt["budget"]["image_decode_calls"] == 20
    assert receipt["budget"]["ffprobe_calls"] == 12
    assert receipt["budget"]["ffmpeg_frame_calls"] == 48
    assert receipt["budget"]["output_bytes_retained"] <= receipt["budget"]["output_bytes_limit"]
    assert receipt["budget"]["wall_seconds_used"] < receipt["budget"]["wall_seconds_limit"]
    assert receipt["decision"] == "PREPARATION_COMPLETE_READY_FOR_REVIEW"
    assert receipt["runtime"]["file_count"] > 32
    for item in receipt["runtime"]["files"]:
        assert item["bytes"] >= 0
        assert len(item["sha256"]) == 64
        assert item["path"].startswith(s3prep.RUNTIME_REL)


def test_cli_preflight_then_run_end_to_end(tmp_path, monkeypatch):
    package = _standard_package(tmp_path)
    package.write_documents()
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    monkeypatch.setattr(
        s3prep, "git_blob", lambda _root, _sha, rel: (package.root / rel).read_bytes()
    )
    monkeypatch.setattr(s3prep, "git_commit_exists", lambda _root, _sha: True)

    preflight_args = type("Args", (), {})()
    preflight_args.child = str(package.root / s3prep.CHILD_REL)
    preflight_args.candidate = "a" * 40
    preflight_args.preflight = str(package.root / s3prep.REPORT_ROOT_REL / "preflight.json")
    preflight_args.runtime_output = str(package.runtime_root())
    assert s3prep.command_preflight(preflight_args, package_root=package.root) == 0
    preflight = json.loads(Path(preflight_args.preflight).read_text(encoding="utf-8"))
    assert preflight["decision"] == "PREFLIGHT_PASSED"
    assert preflight["summary"]["failed"] == 0
    assert preflight["runtime"]["relative_path"] == (
        ".agent-governance/runtime/receipts/s3-preview-c01/run-01"
    )

    run_args = type("Args", (), {})()
    run_args.child = preflight_args.child
    run_args.candidate = preflight_args.candidate
    run_args.preflight = preflight_args.preflight
    run_args.runtime_output = preflight_args.runtime_output
    run_args.receipt = str(package.root / s3prep.REPORT_ROOT_REL / "receipt.json")
    assert s3prep.command_run(run_args, package_root=package.root) == 0

    receipt = json.loads(Path(run_args.receipt).read_text(encoding="utf-8"))
    assert receipt["decision"] == "PREPARATION_COMPLETE_READY_FOR_REVIEW"
    assert receipt["counts"]["selected_total"] == 32
    assert receipt["counts"]["conservation_ok"] is True
    assert receipt["preflight"]["decision"] == "PREFLIGHT_PASSED"
    assert receipt["handoff_guard"]["decision"] == "HANDOFF_READINESS_VERIFIED"
    raw_copy = package.root / s3prep.REPORT_ROOT_REL / "raw"
    assert raw_copy.is_dir()
    assert list(raw_copy.iterdir())
    for path in raw_copy.iterdir():
        text = path.read_text(encoding="utf-8")
        assert str(package.source) not in text
        assert str(package.runtime_root()) not in text
    assert "<SOURCE_ROOT>" in "".join(
        path.read_text(encoding="utf-8") for path in raw_copy.iterdir()
    )


def test_cli_refuses_a_runtime_root_drift(tmp_path, monkeypatch):
    package = _small_package(tmp_path)
    write_json(
        package.root / s3prep.REPORT_ROOT_REL / "preflight.json",
        {
            "decision": "PREFLIGHT_PASSED",
            "candidate": {"sha": "a" * 40},
            "child": {"sha256": sha256_path(package.root / s3prep.CHILD_REL)},
            "catalog": {"sha256": sha256_path(package.root / s3prep.CATALOG_REL)},
            "holdout_manifest": {"sha256": sha256_path(package.root / s3prep.HOLDOUT_REL)},
            "runtime": {"relative_path": ".agent-governance/runtime/receipts/other/run-01"},
        },
    )
    monkeypatch.setattr(s3prep, "HANDOFF_GUARD", stub_guard)
    monkeypatch.setattr(
        s3prep, "git_blob", lambda _root, _sha, rel: (package.root / rel).read_bytes()
    )
    assert s3prep.command_run(_cli_args(package), package_root=package.root) == 1
    assert not package.runtime_root().exists()


def test_preflight_fails_when_a_required_tool_is_missing(tmp_path, monkeypatch):
    package = _standard_package(tmp_path)
    package.write_documents()
    monkeypatch.setattr(
        s3prep,
        "resolve_executable",
        lambda name, explicit=None: {"name": name, "resolved": False, "reason": "not_found_on_path"},
    )
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "tool.ffmpeg" in failed
    assert "tool.ffprobe" in failed


def test_preflight_fails_when_the_bounded_runner_is_missing(tmp_path, monkeypatch):
    package = _standard_package(tmp_path)
    package.write_documents()
    monkeypatch.setattr(s3prep, "BRIDGE_RUNNER_AVAILABLE", False)
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "tool.bounded_runner_available" in failed


def test_admitted_bytes_are_counted_and_bounded(tmp_path):
    package = _small_package(tmp_path)
    receipt, _runtime = run_prepare(package)
    assert receipt["counts"]["admitted"] == 2
    assert receipt["counts"]["admitted_bytes"] == sum(
        item["source_bytes"] for item in receipt["candidates"] if item.get("source_sha256_verified")
    )
    assert receipt["budget"]["admitted_source_bytes"] <= (
        receipt["budget"]["admitted_source_bytes_limit"]
    )


def test_probe_and_frame_budgets_are_never_exceeded(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents()
    receipt, _runtime = run_prepare(package)
    budget = receipt["budget"]
    assert budget["ffprobe_calls"] <= 12 * budget["ffprobe_limit_per_video"]
    assert budget["ffmpeg_frame_calls"] <= 12 * budget["ffmpeg_frame_limit_per_video"]
    assert budget["image_decode_calls"] <= 20 * budget["image_decode_limit_per_image"]
    for candidate in receipt["candidates"]:
        frames = candidate.get("sampling", {}).get("frames", [])
        assert len(frames) <= 4


def test_preflight_rejects_a_holdout_list_that_drops_a_protected_video(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents(
        child_mutator=lambda child: child["holdout_content_sha256"].pop(0)
    )
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "holdout.content_sha256_covers_every_video" in failed


def test_preflight_rejects_an_unknown_holdout_list_entry(tmp_path):
    package = _standard_package(tmp_path)
    package.write_documents(
        child_mutator=lambda child: child["holdout_content_sha256"].append("9" * 64)
    )
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_REJECTED"
    failed = [item["id"] for item in preflight["checks"] if not item["passed"]]
    assert "holdout.content_sha256_no_unknown_entry" in failed


def test_preflight_accepts_the_child_holdout_list_of_the_real_freeze_shape(tmp_path):
    """The real child lists the 11 videos plus the freeze manifest's own hashes."""
    package = _standard_package(tmp_path)
    package.write_documents()
    preflight = run_preflight(package)
    assert preflight["decision"] == "PREFLIGHT_PASSED", [
        item for item in preflight["checks"] if not item["passed"]
    ]
    assert preflight["holdout_manifest"]["content_sha256_count"] == 11
    assert preflight["holdout_manifest"]["child_listed_count"] == 13
