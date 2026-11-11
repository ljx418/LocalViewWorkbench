#!/usr/bin/env python3
"""S3-PREP-C: one bounded candidate eligibility probe and local preview preparation.

This tool implements ONE finite preparation run for the frozen child
``reports/v0-s3/preparation-05/sample-preparation-child-01.json``.

It probes at most the 32 already frozen, non private ``testSource``
candidates for *eligibility* only:

* exactly one SHA-256 pass per source file,
* exactly one container probe (``ffprobe``) per video,
* at most four single frame extractions (``ffmpeg``) per video,
* exactly one Pillow decode per image,

and it renders local, non semantic previews (thumbnail, frame strip and a
static ``index.html``) that the NEXT, independent prelabel step needs.

It does NOT

* run a model, touch a GPU, start a service, download anything or consume a
  full product checkpoint,
* call LVW or any product analysis path,
* produce a semantic label, an "expected answer" or a quality verdict,
* copy, modify, move or delete a source file,
* send any media byte to a remote provider.

Only three paths may be added by this work: ``tools/s3_sample_preparation.py``,
``tools/test_s3_sample_preparation.py`` and text evidence below
``reports/v0-s3/preparation-05/implementation/``.  Every real media artefact
stays inside the git ignored runtime root
``.agent-governance/runtime/receipts/s3-preview-c01/``.

Usage (two explicit steps, in this order)::

    python3 -B tools/s3_sample_preparation.py preflight \\
        --child reports/v0-s3/preparation-05/sample-preparation-child-01.json \\
        --candidate <40 hex code candidate sha> \\
        --preflight reports/v0-s3/preparation-05/implementation/run-01/preflight.json \\
        --runtime-output <absolute runtime root>

    python3 -B tools/s3_sample_preparation.py run \\
        --child reports/v0-s3/preparation-05/sample-preparation-child-01.json \\
        --candidate <40 hex code candidate sha> \\
        --preflight reports/v0-s3/preparation-05/implementation/run-01/preflight.json \\
        --runtime-output <absolute runtime root> \\
        --receipt reports/v0-s3/preparation-05/implementation/run-01/receipt.json

The preflight is a *global* gate: if any preflight check fails, not a single
selected media file is stat'ed, hashed, probed or decoded.  The preflight file
and the terminal receipt are two separate, non overwritable artefacts.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# never write bytecode into the package tree
sys.dont_write_bytecode = True

from PIL import Image, ImageDraw, ImageFont, ImageOps  # noqa: E402

try:  # the project already owns a bounded, direct child process runner
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import (  # noqa: E402
        run_bounded,
    )

    BRIDGE_RUNNER_AVAILABLE = True
except Exception:  # pragma: no cover - reported as BLOCKED by the preflight
    run_bounded = None
    BRIDGE_RUNNER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Frozen constants.  These mirror the frozen stage packet and the frozen
# child.  They are never derived from a chat message or from a runtime
# observation, and the preflight refuses a child whose own limits differ.
# ---------------------------------------------------------------------------
CHILD_REL = "reports/v0-s3/preparation-05/sample-preparation-child-01.json"
CATALOG_REL = "reports/v0-s3/preparation-03/candidate-catalog-filtered-01.json"
HOLDOUT_REL = "人工验收视频集/FREEZE.json"
PACKET_REL = "reports/v0-s3/preparation-05/stage-packet-preparation-c.md"
REPORT_ROOT_REL = "reports/v0-s3/preparation-05/implementation"
RUNTIME_REL = ".agent-governance/runtime/receipts/s3-preview-c01"
SCRIPT_REL = "tools/s3_sample_preparation.py"
TEST_REL = "tools/test_s3_sample_preparation.py"
BRIDGE_RUNNER_REL = "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_process.py"

EXPECTED_CHILD_KIND = "S3_QUALITY_CANDIDATE_PREPARATION_CHILD_NOT_INFERENCE"
EXPECTED_CHILD_ID = "S3-PREP-C-01"
EXPECTED_LIMITS = {
    "runs": 1,
    "wall_seconds": 1200,
    "distinct_source_files": 32,
    "admitted_source_bytes": 1073741824,
    "hash_passes_per_file": 1,
    "image_decodes_per_image": 1,
    "ffprobe_calls_per_video": 1,
    "frame_extractions_per_video": 4,
    "output_bytes": 83886080,
    "image_max_pixels": 40000000,
    "video_max_source_pixels": 8294400,
    "video_max_duration_seconds": 60,
    "preview_long_edge": 640,
    "model_actions": 0,
    "gpu_actions": 0,
    "services": 0,
    "network": 0,
    "full_product_checkpoints": 0,
}
EXPECTED_SELECTION_COUNT = 32
EXPECTED_IMAGE_COUNT = 20
EXPECTED_VIDEO_COUNT = 12
EXPECTED_HOLDOUT_COUNT = 11

# Per file ceilings stated by the frozen stage packet (line 11 of
# ``stage-packet-preparation-c.md``).  They are not in the child limits block
# and are therefore bound here as frozen tool criteria.
IMAGE_MAX_BYTES = 20 * 1024 * 1024
VIDEO_MAX_BYTES = 256 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
ALLOWED_VIDEO_EXTENSIONS = (".mp4", ".mov")
SUPPORTED_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "BMP", "MPO")

SAMPLE_FRACTIONS = (0.10, 0.35, 0.65, 0.90)
MIN_SAMPLE_SPACING_SECONDS = 0.25
PROBE_TIMEOUT_SECONDS = 20
FRAME_TIMEOUT_SECONDS = 45
HASH_CHUNK_BYTES = 1024 * 1024
CONTACT_TILE_HEIGHT = 220
CONTACT_TILE_WIDTH = 320
CONTACT_BANNER_HEIGHT = 26

PREVIEW_BANNER = (
    "独立预标前素材预览，不是项目识别输出。 / Pre-prelabel material preview. "
    "This is NOT LVW or project recognition output, NOT an annotation and NOT a quality verdict."
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
class PolicyError(Exception):
    """A source path policy refusal (symlink, traversal or escape)."""


class PreflightError(Exception):
    """A global preflight refusal.  No media may be touched afterwards."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, deadline: float = None, clock=time.monotonic) -> tuple:
    """Hash one file in bounded chunks; returns (hex digest, bytes read)."""
    digest = hashlib.sha256()
    total = 0
    with open(path, "rb") as handle:
        while True:
            if deadline is not None and clock() > deadline:
                raise TimeoutError("wall budget exhausted while hashing")
            chunk = handle.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def relative_to_package(path: Path, package_root: Path) -> str:
    """Project relative POSIX path, or a redacted marker when outside."""
    try:
        return Path(path).resolve().relative_to(Path(package_root).resolve()).as_posix()
    except ValueError:
        return "<OUTSIDE_PACKAGE>"


# ---------------------------------------------------------------------------
# Source path policy
# ---------------------------------------------------------------------------
def resolve_source_path(root: Path, relative: str) -> Path:
    """Resolve one relative source path under ``root`` or refuse it.

    Refuses absolute paths, drive letters, ``..`` traversal, every symlink
    component and every real path that escapes the root.
    """
    if not isinstance(relative, str) or not relative.strip():
        raise PolicyError("source_path_empty")
    if relative != relative.strip():
        raise PolicyError("source_path_whitespace_padded")
    normalised = relative.replace("\\", "/")
    if normalised.startswith("/"):
        raise PolicyError("source_path_absolute_rejected")
    if len(normalised) > 1 and normalised[1] == ":":
        raise PolicyError("source_path_drive_letter_rejected")
    parts = [part for part in normalised.split("/") if part != ""]
    if not parts:
        raise PolicyError("source_path_empty")
    if any(part == ".." for part in parts):
        raise PolicyError("source_path_traversal_rejected")
    if any(part == "." for part in parts):
        raise PolicyError("source_path_dot_segment_rejected")

    root_real = os.path.realpath(str(root))
    current = Path(root)
    for part in parts:
        current = current / part
        try:
            if os.path.islink(str(current)):
                raise PolicyError("source_path_symlink_rejected")
        except OSError as exc:  # pragma: no cover - defensive
            raise PolicyError("source_path_stat_failed:%s" % type(exc).__name__)
    real = os.path.realpath(str(current))
    if real != root_real and not real.startswith(root_real.rstrip(os.sep) + os.sep):
        raise PolicyError("source_path_escape_rejected")
    return Path(real)


def policy_self_check() -> dict:
    """Prove the path policy refuses escapes, on a synthetic fixture only."""
    base = Path(tempfile.mkdtemp(prefix="lvw-s3prep-policy-"))
    result = {"temporary_root": None, "temporary_root_removed": False}
    try:
        root = base / "root"
        root.mkdir()
        outside = base / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (root / "inside.txt").write_text("inside", encoding="utf-8")
        os.symlink(str(outside), str(root / "escape.link"))
        checks = {}
        for label, relative, expect_refusal in (
            ("symlink_escape_rejected", "escape.link", True),
            ("traversal_rejected", "../outside.txt", True),
            ("absolute_rejected", "/etc/hostname", True),
            ("inside_allowed", "inside.txt", False),
        ):
            try:
                resolve_source_path(root, relative)
                refused = False
            except PolicyError:
                refused = True
            checks[label] = (refused == expect_refusal)
        result.update(checks)
        result["all_passed"] = all(checks.values())
    finally:
        shutil.rmtree(str(base), ignore_errors=False)
        result["temporary_root_removed"] = not base.exists()
    return result


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------
def _version_of(argv: list) -> str:
    try:
        proc = subprocess.run(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "UNAVAILABLE:%s" % type(exc).__name__
    text = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    return text[0].strip() if text else "UNKNOWN"


def resolve_executable(name: str, explicit: str = None) -> dict:
    """Resolve one real executable; never assume an alias is a version."""
    candidate = explicit or shutil.which(name)
    if not candidate:
        return {"name": name, "resolved": False, "reason": "not_found_on_path"}
    path = Path(candidate)
    try:
        real = Path(os.path.realpath(str(path)))
    except OSError as exc:  # pragma: no cover - defensive
        return {"name": name, "resolved": False, "reason": "realpath_failed:%s" % exc}
    if not real.is_file():
        return {"name": name, "resolved": False, "reason": "resolved_path_is_not_a_file"}
    if not os.access(str(real), os.X_OK):
        return {"name": name, "resolved": False, "reason": "resolved_path_is_not_executable"}
    return {
        "name": name,
        "resolved": True,
        "invoked_as": str(path),
        "real_path": str(real),
        "bytes": real.stat().st_size,
        "sha256": sha256_file(real)[0],
        "version": _version_of([str(real), "-version"]),
    }


def pillow_binding() -> dict:
    try:
        import PIL  # noqa: WPS433 - local import for a precise binding
        from PIL import Image as _image  # noqa: F401
    except Exception as exc:  # pragma: no cover - reported as BLOCKED
        return {"name": "pillow", "resolved": False, "reason": "import_failed:%s" % exc}
    module = Path(PIL.__file__).resolve()
    image_module = (module.parent / "Image.py").resolve()
    return {
        "name": "pillow",
        "resolved": True,
        "version": getattr(PIL, "__version__", "unknown"),
        "package_path": str(module),
        "image_module_sha256": sha256_file(image_module)[0] if image_module.is_file() else None,
    }


def python_binding() -> dict:
    executable = Path(sys.executable).resolve()
    return {
        "name": "python",
        "resolved": True,
        "real_path": str(executable),
        "sha256": sha256_file(executable)[0] if executable.is_file() else None,
        "version": sys.version.split()[0],
        "version_string": sys.version.replace("\n", " "),
    }


# ---------------------------------------------------------------------------
# Git binding
# ---------------------------------------------------------------------------
def git_prefix(package_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(package_root), "rev-parse", "--show-prefix"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def git_blob(package_root: Path, sha: str, relative: str) -> bytes:
    """Read one blob out of a commit; returns b"" when it is not present."""
    prefix = git_prefix(package_root)
    spec = "%s%s" % (prefix, relative)
    try:
        proc = subprocess.run(
            ["git", "-C", str(package_root), "cat-file", "blob", "%s:%s" % (sha, spec)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return b""
    if proc.returncode != 0:
        return b""
    return proc.stdout


def git_head(package_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(package_root), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("ascii", "replace").strip()


def git_commit_exists(package_root: Path, sha: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(package_root), "cat-file", "-e", "%s^{commit}" % sha],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
class Ledger:
    """Ordered check ledger with stable identifiers."""

    def __init__(self) -> None:
        self.checks: list = []

    def add(self, identifier: str, passed: bool, detail: str = "") -> bool:
        self.checks.append({"id": identifier, "passed": bool(passed), "detail": str(detail)})
        return bool(passed)

    @property
    def failed(self) -> list:
        return [item for item in self.checks if not item["passed"]]


def build_preflight(
    *,
    package_root: Path,
    child_path: Path,
    candidate_sha: str,
    runtime_root: Path,
    guard_evaluator=None,
    blob_reader=None,
    commit_exists_reader=None,
) -> dict:
    """Evaluate every global gate.  Nothing here touches selected media."""
    package_root = Path(package_root)
    child_path = Path(child_path)
    runtime_root = Path(runtime_root)
    started = time.monotonic()
    ledger = Ledger()

    preflight = {
        "kind": "S3_PREP_C_CANDIDATE_PREPARATION_PREFLIGHT",
        "scope": "PREPARATION_ELIGIBILITY_AND_PREVIEW_ONLY",
        "product_gate0": False,
        "stage_pass_claim": False,
        "quality_claim": "NONE_ELIGIBILITY_IS_NOT_QUALITY_EVIDENCE",
        "generated_at": now_iso(),
        "checks": [],
    }

    # -- 1. the child -------------------------------------------------------
    if not child_path.is_file():
        raise PreflightError("child_missing:%s" % child_path)
    child_raw = child_path.read_bytes()
    child_sha = sha256_bytes(child_raw)
    try:
        child = json.loads(child_raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PreflightError("child_malformed_json:%s" % exc)
    ledger.add("child.present", True, relative_to_package(child_path, package_root))
    ledger.add(
        "child.kind",
        child.get("kind") == EXPECTED_CHILD_KIND,
        "kind=%r (expected %r)" % (child.get("kind"), EXPECTED_CHILD_KIND),
    )
    ledger.add(
        "child.id",
        child.get("child_id") == EXPECTED_CHILD_ID,
        "child_id=%r (expected %r)" % (child.get("child_id"), EXPECTED_CHILD_ID),
    )
    ledger.add(
        "child.limits_frozen",
        child.get("limits") == EXPECTED_LIMITS,
        "the child limits must be identical to the frozen tool criteria",
    )
    ledger.add(
        "child.quality_not_frozen",
        child.get("quality_frozen") is False,
        "quality_frozen=%r (must be False)" % (child.get("quality_frozen"),),
    )
    ledger.add(
        "child.no_model_actions",
        int(child.get("limits", {}).get("model_actions", -1)) == 0
        and int(child.get("limits", {}).get("gpu_actions", -1)) == 0
        and int(child.get("limits", {}).get("services", -1)) == 0
        and int(child.get("limits", {}).get("network", -1)) == 0
        and int(child.get("limits", {}).get("full_product_checkpoints", -1)) == 0,
        "model/gpu/service/network/checkpoint budgets must all be 0",
    )

    selected = child.get("selected_files")
    ledger.add(
        "child.selection_container",
        isinstance(selected, list),
        "selected_files is %s" % type(selected).__name__,
    )
    selected = selected if isinstance(selected, list) else []
    kinds = {}
    for entry in selected:
        if isinstance(entry, dict):
            kinds[entry.get("media_kind")] = kinds.get(entry.get("media_kind"), 0) + 1
    ledger.add(
        "child.selection_count",
        len(selected) == EXPECTED_SELECTION_COUNT,
        "selected=%d (expected exactly %d)" % (len(selected), EXPECTED_SELECTION_COUNT),
    )
    ledger.add(
        "child.selection_kinds",
        kinds.get("image") == EXPECTED_IMAGE_COUNT and kinds.get("video") == EXPECTED_VIDEO_COUNT,
        "kinds=%r (expected %d images and %d videos)"
        % (kinds, EXPECTED_IMAGE_COUNT, EXPECTED_VIDEO_COUNT),
    )
    file_ids = [entry.get("file_id") for entry in selected if isinstance(entry, dict)]
    sha_values = [entry.get("sha256") for entry in selected if isinstance(entry, dict)]
    paths = [entry.get("relative_path") for entry in selected if isinstance(entry, dict)]
    ledger.add(
        "child.selection_unique_ids",
        len(set(file_ids)) == len(file_ids) and len(file_ids) == EXPECTED_SELECTION_COUNT,
        "unique file ids=%d of %d" % (len(set(file_ids)), len(file_ids)),
    )
    ledger.add(
        "child.selection_unique_content",
        len(set(sha_values)) == len(sha_values) and len(sha_values) == EXPECTED_SELECTION_COUNT,
        "unique content hashes=%d of %d" % (len(set(sha_values)), len(sha_values)),
    )
    ledger.add(
        "child.selection_unique_paths",
        len(set(paths)) == len(paths),
        "unique relative paths=%d of %d" % (len(set(paths)), len(paths)),
    )
    sum_bytes = sum(int(entry.get("bytes", 0)) for entry in selected if isinstance(entry, dict))
    ledger.add(
        "child.admitted_bytes_budget",
        sum_bytes <= int(EXPECTED_LIMITS["admitted_source_bytes"]),
        "selected bytes=%d (limit %d)" % (sum_bytes, EXPECTED_LIMITS["admitted_source_bytes"]),
    )

    # -- 2. the catalog -----------------------------------------------------
    catalog_path = package_root / CATALOG_REL
    if not catalog_path.is_file():
        raise PreflightError("catalog_missing:%s" % CATALOG_REL)
    catalog_sha = sha256_file(catalog_path)[0]
    ledger.add(
        "catalog.sha256",
        catalog_sha == child.get("catalog_sha256"),
        "%s expected=%s actual=%s" % (CATALOG_REL, child.get("catalog_sha256"), catalog_sha),
    )
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PreflightError("catalog_malformed_json:%s" % exc)
    catalog_by_sha = {}
    for item in catalog.get("items", []) if isinstance(catalog.get("items"), list) else []:
        if isinstance(item, dict) and item.get("sha256"):
            catalog_by_sha.setdefault(item["sha256"], []).append(item)
    mismatched = []
    for entry in selected:
        matches = catalog_by_sha.get(entry.get("sha256"), [])
        if not any(
            item.get("bytes") == entry.get("bytes")
            and item.get("relative_path") == entry.get("relative_path")
            and item.get("file_id") == entry.get("file_id")
            for item in matches
        ):
            mismatched.append(entry.get("relative_path"))
    ledger.add(
        "catalog.selected_exact_subset",
        not mismatched,
        "every selected candidate is present in the frozen catalog with identical "
        "id/path/bytes/hash" if not mismatched else "not in the catalog: %r" % (mismatched,),
    )
    excluded_ids = set(catalog.get("excluded_private_labelled_ids") or [])
    excluded_sha = set(catalog.get("excluded_private_labelled_sha256") or [])
    overlap_excluded = [e.get("relative_path") for e in selected if e.get("file_id") in excluded_ids
                        or e.get("sha256") in excluded_sha]
    ledger.add(
        "catalog.no_private_labelled_overlap",
        not overlap_excluded,
        "no selected candidate is private labelled" if not overlap_excluded
        else "overlap: %r" % (overlap_excluded,),
    )
    ledger.add(
        "catalog.sample_labels_not_frozen",
        catalog.get("sample_selection_frozen") is False
        and catalog.get("model_execution_authorized_by_catalog") is False,
        "sample_selection_frozen=%r model_execution_authorized_by_catalog=%r"
        % (catalog.get("sample_selection_frozen"), catalog.get("model_execution_authorized_by_catalog")),
    )

    # -- 3. the holdout freeze ---------------------------------------------
    holdout_path = package_root / HOLDOUT_REL
    if not holdout_path.is_file():
        raise PreflightError("holdout_manifest_missing:%s" % HOLDOUT_REL)
    holdout_sha = sha256_file(holdout_path)[0]
    ledger.add(
        "holdout.manifest_sha256",
        holdout_sha == child.get("holdout_manifest_sha256"),
        "%s expected=%s actual=%s" % (HOLDOUT_REL, child.get("holdout_manifest_sha256"), holdout_sha),
    )
    try:
        holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PreflightError("holdout_manifest_malformed:%s" % exc)
    observed_holdouts = [
        item.get("video_sha256") for item in holdout.get("videos", []) if isinstance(item, dict)
    ]
    ledger.add(
        "holdout.count",
        len(observed_holdouts) == EXPECTED_HOLDOUT_COUNT,
        "holdout videos=%d (expected %d)" % (len(observed_holdouts), EXPECTED_HOLDOUT_COUNT),
    )
    child_holdout_list = list(child.get("holdout_content_sha256") or [])
    manifest_hashes = {
        value
        for value in (holdout.get("expected_sha256"), holdout.get("assets_manifest_sha256"))
        if value
    }
    ledger.add(
        "holdout.content_sha256_covers_every_video",
        set(observed_holdouts) <= set(child_holdout_list),
        "every protected holdout video hash must be listed in the child",
    )
    ledger.add(
        "holdout.content_sha256_no_unknown_entry",
        set(child_holdout_list) - set(observed_holdouts) == manifest_hashes,
        "the child may only list the protected videos plus the freeze manifest's own "
        "declared hashes; extras=%r"
        % (sorted(set(child_holdout_list) - set(observed_holdouts)),),
    )
    overlap_holdout = [
        e.get("relative_path") for e in selected if e.get("sha256") in set(child_holdout_list)
    ]
    ledger.add(
        "holdout.no_selected_overlap",
        not overlap_holdout,
        "no selected candidate is one of the 11 protected human holdouts"
        if not overlap_holdout else "overlap: %r" % (overlap_holdout,),
    )

    # -- 4. the frozen stage packet ----------------------------------------
    packet_path = package_root / PACKET_REL
    packet_sha = sha256_file(packet_path)[0] if packet_path.is_file() else None
    ledger.add("packet.present", packet_sha is not None, PACKET_REL)

    # -- 5. the code candidate ---------------------------------------------
    ledger.add(
        "code.candidate_format",
        isinstance(candidate_sha, str) and len(candidate_sha) == 40
        and all(char in "0123456789abcdef" for char in candidate_sha),
        "candidate=%r" % (candidate_sha,),
    )
    reader = blob_reader or (lambda sha, rel: git_blob(package_root, sha, rel))
    script_blob = reader(candidate_sha, SCRIPT_REL)
    test_blob = reader(candidate_sha, TEST_REL)
    bridge_blob = reader(candidate_sha, BRIDGE_RUNNER_REL)
    ledger.add(
        "code.script_in_candidate",
        bool(script_blob),
        "the tool script must exist as a blob in the candidate commit",
    )
    ledger.add(
        "code.test_in_candidate",
        bool(test_blob),
        "the test script must exist as a blob in the candidate commit",
    )
    ledger.add(
        "code.bridge_runner_in_candidate",
        bool(bridge_blob),
        "the borrowed bounded process runner must exist in the candidate commit",
    )
    script_disk = package_root / SCRIPT_REL
    test_disk = package_root / TEST_REL
    script_disk_sha = sha256_file(script_disk)[0] if script_disk.is_file() else None
    test_disk_sha = sha256_file(test_disk)[0] if test_disk.is_file() else None
    ledger.add(
        "code.working_tree_matches_candidate",
        bool(script_blob) and sha256_bytes(script_blob) == script_disk_sha
        and bool(test_blob) and sha256_bytes(test_blob) == test_disk_sha,
        "the working tree script and test bytes must equal the candidate blobs",
    )
    ledger.add(
        "code.commit_exists",
        (commit_exists_reader or (lambda sha: git_commit_exists(package_root, sha)))(
            candidate_sha
        ),
        "candidate commit must exist in this repository",
    )

    # -- 6. the local tools -------------------------------------------------
    python_tool = python_binding()
    pillow_tool = pillow_binding()
    ffmpeg_tool = resolve_executable("ffmpeg")
    ffprobe_tool = resolve_executable("ffprobe")
    for label, tool in (
        ("tool.python", python_tool),
        ("tool.pillow", pillow_tool),
        ("tool.ffmpeg", ffmpeg_tool),
        ("tool.ffprobe", ffprobe_tool),
    ):
        ledger.add(
            label,
            bool(tool.get("resolved")),
            "%s resolved=%r version=%r" % (label, tool.get("resolved"), tool.get("version")),
        )
    ledger.add(
        "tool.bounded_runner_available",
        BRIDGE_RUNNER_AVAILABLE,
        "the borrowed bounded direct child runner must be importable",
    )
    bridge_disk = package_root / BRIDGE_RUNNER_REL
    bridge_disk_sha = sha256_file(bridge_disk)[0] if bridge_disk.is_file() else None
    ledger.add(
        "tool.bounded_runner_matches_candidate",
        bool(bridge_blob) and sha256_bytes(bridge_blob) == bridge_disk_sha,
        "the borrowed runner bytes must equal the candidate blob",
    )

    # -- 7. the public handoff guard ---------------------------------------
    evaluator = guard_evaluator or (lambda root: _guard_for_run(root))
    guard_result = evaluator(package_root)
    ledger.add(
        "guard.handoff_readiness",
        guard_result.get("decision") == "HANDOFF_READINESS_VERIFIED",
        "decision=%r summary=%r" % (guard_result.get("decision"), guard_result.get("summary")),
    )

    # -- 8. the runtime root ------------------------------------------------
    runtime_abs = Path(os.path.abspath(str(runtime_root)))
    package_abs = Path(os.path.abspath(str(package_root)))
    runtime_rel = relative_to_package(runtime_abs, package_abs)
    ledger.add(
        "runtime.under_ignored_root",
        runtime_rel.startswith(RUNTIME_REL),
        "the runtime root must live under the git ignored %s" % RUNTIME_REL,
    )
    ledger.add(
        "runtime.unique_and_absent",
        not runtime_abs.exists(),
        "the runtime root must not exist yet (absolute path is kept out of this file)",
    )
    ledger.add(
        "runtime.not_inside_package_tracked",
        not runtime_abs.exists(),
        "the runtime root is created by this run and stays untracked",
    )

    # -- 9. the budgets -----------------------------------------------------
    limits = EXPECTED_LIMITS
    ledger.add(
        "budget.wall_monotonic",
        0 < limits["wall_seconds"] <= 1200,
        "wall_seconds=%d" % limits["wall_seconds"],
    )
    ledger.add(
        "budget.output_monotonic",
        0 < limits["output_bytes"] <= 83886080,
        "output_bytes=%d" % limits["output_bytes"],
    )
    ledger.add(
        "budget.hash_passes_single",
        limits["hash_passes_per_file"] == 1,
        "hash_passes_per_file=%d" % limits["hash_passes_per_file"],
    )
    ledger.add(
        "budget.probe_limits_single",
        limits["image_decodes_per_image"] == 1
        and limits["ffprobe_calls_per_video"] == 1
        and limits["frame_extractions_per_video"] == 4,
        "decode/probe/frame limits=%r/%r/%r"
        % (
            limits["image_decodes_per_image"],
            limits["ffprobe_calls_per_video"],
            limits["frame_extractions_per_video"],
        ),
    )
    ledger.add(
        "budget.global_deadline_governs",
        limits["wall_seconds"] < 12 * (PROBE_TIMEOUT_SECONDS + 4 * FRAME_TIMEOUT_SECONDS),
        "the per process timeouts can exceed the wall budget, so the global deadline governs",
    )

    # -- 10. the source root directory (never a selected media file) -------
    source_root = Path(str(child.get("source_root", "")))
    ledger.add(
        "source_root.declared_absolute",
        source_root.is_absolute(),
        "the source root must be an absolute path",
    )
    ledger.add(
        "source_root.is_directory",
        source_root.is_dir(),
        "the source root directory must exist on this machine",
    )
    ledger.add(
        "source_root.not_a_symlink",
        not source_root.is_symlink(),
        "the source root itself must not be a symbolic link",
    )

    # -- 11. the path policy capability ------------------------------------
    policy = policy_self_check()
    ledger.add(
        "policy.self_check",
        bool(policy.get("all_passed")) and bool(policy.get("temporary_root_removed")),
        "synthetic path policy self check: %r" % (policy,),
    )

    preflight.update(
        {
            "child": {
                "path": relative_to_package(child_path, package_root),
                "sha256": child_sha,
                "kind": child.get("kind"),
                "child_id": child.get("child_id"),
                "state": child.get("state"),
                "selected_count": len(selected),
                "selected_bytes": sum_bytes,
            },
            "catalog": {
                "path": CATALOG_REL,
                "sha256": catalog_sha,
                "expected_sha256": child.get("catalog_sha256"),
            },
            "holdout_manifest": {
                "path": HOLDOUT_REL,
                "sha256": holdout_sha,
                "expected_sha256": child.get("holdout_manifest_sha256"),
                "content_sha256_count": len(observed_holdouts),
                "child_listed_count": len(child_holdout_list),
            },
            "stage_packet": {"path": PACKET_REL, "sha256": packet_sha},
            "candidate": {
                "sha": candidate_sha,
                "git_head_at_preflight": git_head(package_root),
                "script": {
                    "path": SCRIPT_REL,
                    "blob_sha256": sha256_bytes(script_blob) if script_blob else None,
                    "working_tree_sha256": script_disk_sha,
                },
                "test": {
                    "path": TEST_REL,
                    "blob_sha256": sha256_bytes(test_blob) if test_blob else None,
                    "working_tree_sha256": test_disk_sha,
                },
                "borrowed_runner": {
                    "path": BRIDGE_RUNNER_REL,
                    "blob_sha256": sha256_bytes(bridge_blob) if bridge_blob else None,
                    "working_tree_sha256": bridge_disk_sha,
                },
            },
            "tools": {
                "python": python_tool,
                "pillow": pillow_tool,
                "ffmpeg": ffmpeg_tool,
                "ffprobe": ffprobe_tool,
            },
            "handoff_guard": {
                "decision": guard_result.get("decision"),
                "authority": guard_result.get("authority"),
                "summary": guard_result.get("summary"),
                "failed_checks": [
                    item.get("id")
                    for item in (guard_result.get("checks") or [])
                    if not item.get("passed")
                ],
            },
            "selection": {
                "count": len(selected),
                "images": kinds.get("image", 0),
                "videos": kinds.get("video", 0),
                "sum_bytes": sum_bytes,
                "catalog_exact": not mismatched,
                "private_labelled_overlap": len(overlap_excluded),
                "holdout_overlap": len(overlap_holdout),
            },
            "source_root": {
                "declared_in_child": True,
                "is_directory": source_root.is_dir(),
                "is_symlink": source_root.is_symlink(),
                "absolute_path_kept_in": "the runtime receipt only",
            },
            "runtime": {
                "relative_path": runtime_rel,
                "exists": runtime_abs.exists(),
                "absolute_path_kept_in": "the runtime receipt only",
            },
            "budgets": dict(EXPECTED_LIMITS),
            "policy_self_check": policy,
            "checks": ledger.checks,
            "summary": {
                "checks": len(ledger.checks),
                "passed": len(ledger.checks) - len(ledger.failed),
                "failed": len(ledger.failed),
            },
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    )
    failed = ledger.failed
    preflight["decision"] = "PREFLIGHT_PASSED" if not failed else "PREFLIGHT_REJECTED"
    if failed:
        preflight["refusal"] = {
            "reason": "global_preflight_failed",
            "failed_checks": [{"id": item["id"], "detail": item["detail"]} for item in failed],
            "media_access": {
                "selected_files_stat": 0,
                "selected_files_hashed": 0,
                "selected_files_probed": 0,
                "selected_files_decoded": 0,
            },
        }
    return preflight


#: Test hook.  ``None`` means "use the real public handoff guard".
HANDOFF_GUARD = None


def _guard_for_run(package_root: Path) -> dict:
    if HANDOFF_GUARD is not None:
        return HANDOFF_GUARD(package_root)
    return _run_handoff_guard(package_root)


def _run_handoff_guard(package_root: Path) -> dict:
    sys.path.insert(0, str(HERE))
    try:
        import verify_s3_handoff as guard  # noqa: WPS433 - local import for the public guard
    except Exception as exc:  # pragma: no cover - defensive
        return {"decision": "HANDOFF_GUARD_IMPORT_FAILED", "summary": {"error": str(exc)}}
    return guard.evaluate(package_root)


# ---------------------------------------------------------------------------
# Media adapter
# ---------------------------------------------------------------------------
class MediaAdapter:
    """Everything that touches real media.  Tests replace it with a fake."""

    def __init__(self, ffmpeg: Path, ffprobe: Path, run_log=None) -> None:
        self.ffmpeg = str(ffmpeg)
        self.ffprobe = str(ffprobe)
        self.run_log = run_log if run_log is not None else []

    # -- process plumbing ---------------------------------------------------
    def _run(self, kind: str, argv: list, timeout: int, label: str) -> dict:
        entry = {
            "kind": kind,
            "label": label,
            "argv": list(argv),
            "timeout_seconds": timeout,
            "exit_code": None,
            "stdout_bytes": 0,
            "stderr_bytes": 0,
            "stdout_sha256": None,
            "stderr_sha256": None,
            "error": None,
        }
        captured = {}

        def on_result(result) -> None:
            captured["stdout"] = result.stdout
            captured["stderr"] = result.stderr
            entry["exit_code"] = result.returncode

        try:
            run_bounded(argv, timeout_seconds=timeout, output_limit=4 * 1024 * 1024,
                        on_result=on_result)
        except Exception as exc:
            entry["error"] = "%s:%s" % (type(exc).__name__, getattr(exc, "code", "") or "")
        stdout = captured.get("stdout", b"")
        stderr = captured.get("stderr", b"")
        entry["stdout_bytes"] = len(stdout)
        entry["stderr_bytes"] = len(stderr)
        entry["stdout_sha256"] = sha256_bytes(stdout)
        entry["stderr_sha256"] = sha256_bytes(stderr)
        entry["stdout_text"] = stdout.decode("utf-8", "replace")
        entry["stderr_text"] = stderr.decode("utf-8", "replace")
        self.run_log.append(entry)
        return entry

    # -- media operations ---------------------------------------------------
    def probe_video(self, path: Path, label: str) -> tuple:
        argv = [
            self.ffprobe, "-v", "error",
            "-enable_drefs", "0", "-protocol_whitelist", "file,pipe",
            "-show_entries",
            "format=format_name,duration,nb_streams:stream=index,codec_type,codec_name,width,height,duration",
            "-of", "json", str(path),
        ]
        entry = self._run("ffprobe", argv, PROBE_TIMEOUT_SECONDS, label)
        if entry["exit_code"] != 0:
            return entry, None
        try:
            document = json.loads(entry["stdout_text"])
        except ValueError:
            return entry, None
        return entry, document

    def extract_frame(self, path: Path, offset: float, output: Path, label: str) -> dict:
        argv = [
            self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
            "-hwaccel", "none", "-threads", "1", "-filter_threads", "1",
            "-ss", "%.3f" % offset,
            "-enable_drefs", "0", "-protocol_whitelist", "file,pipe",
            "-i", str(path),
            "-map", "0:v:0", "-an", "-sn", "-dn", "-frames:v", "1",
            "-vf", "scale=w=min(640\\,iw):h=min(640\\,ih):force_original_aspect_ratio=decrease",
            "-q:v", "3", "-f", "image2", "-y", str(output),
        ]
        entry = self._run("ffmpeg", argv, FRAME_TIMEOUT_SECONDS, label)
        entry["offset_seconds"] = offset
        entry["output"] = str(output)
        return entry


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------
def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


def render_thumbnail(source: Path, target: Path, long_edge: int, max_pixels: int = None,
                    on_decode=None) -> dict:
    """One Pillow decode, EXIF transposition, RGB conversion, <=640 thumbnail.

    The pixel ceiling is checked on the header, before the single decode, so an
    oversized candidate is refused without decoding it.
    """
    with Image.open(str(source)) as image:
        fmt = image.format
        width, height = image.size
        if fmt not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError("image_format_unsupported:%s" % fmt)
        if max_pixels is not None and width * height > max_pixels:
            raise ValueError("image_pixels_over_limit:%d" % (width * height))
        image.load()
        if on_decode is not None:
            on_decode()
        try:
            orientation = image.getexif().get(274)
        except Exception:
            orientation = None
        oriented = ImageOps.exif_transpose(image)
        rgb = oriented.convert("RGB")
        rgb.thumbnail((long_edge, long_edge), Image.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(str(target), format="JPEG", quality=90)
        return {
            "source_format": fmt,
            "source_width": width,
            "source_height": height,
            "exif_orientation_applied": bool(orientation),
            "thumbnail_width": rgb.size[0],
            "thumbnail_height": rgb.size[1],
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target)[0],
        }


def render_contact_sheet(tiles: list, target: Path, caption: str) -> dict:
    """Compose a non semantic contact sheet out of already rendered tiles."""
    if not tiles:
        raise ValueError("no tiles")
    banner = _font(14)
    cell_w = CONTACT_TILE_WIDTH
    cell_h = CONTACT_TILE_HEIGHT
    canvas = Image.new("RGB", (cell_w * len(tiles), cell_h + CONTACT_BANNER_HEIGHT), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((6, 6), caption[:120], font=banner, fill="black")
    for index, tile in enumerate(tiles):
        with Image.open(str(tile)) as image:
            image = image.convert("RGB")
            image.thumbnail((cell_w - 8, cell_h - 8), Image.LANCZOS)
            offset_x = index * cell_w + (cell_w - image.size[0]) // 2
            offset_y = CONTACT_BANNER_HEIGHT + (cell_h - image.size[1]) // 2
            canvas.paste(image, (offset_x, offset_y))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(target), format="JPEG", quality=88)
    return {"bytes": target.stat().st_size, "sha256": sha256_file(target)[0]}


def render_index(path: Path, entries: list, summary: dict) -> None:
    """Static, offline, relative link preview index.  No semantic labels."""
    rows = []
    for entry in entries:
        links = []
        if entry.get("contact_sheet"):
            links.append(
                '<a href="%s">contact sheet</a>' % html.escape(entry["contact_sheet"], quote=True)
            )
        for frame in entry.get("frames", []) or []:
            links.append(
                '<a href="%s">frame %s</a>'
                % (html.escape(frame["path"], quote=True), html.escape(frame["name"], quote=True))
            )
        if entry.get("thumbnail"):
            links.append(
                '<a href="%s">thumbnail</a>' % html.escape(entry["thumbnail"], quote=True)
            )
        probe = entry.get("probe") or {}
        if probe:
            if probe.get("duration_seconds") is not None:
                probe_text = "%sx%s, %.3fs" % (
                    probe.get("width"),
                    probe.get("height"),
                    probe.get("duration_seconds"),
                )
            else:
                probe_text = "%sx%s" % (probe.get("width"), probe.get("height"))
        else:
            probe_text = "-"
        sampling = entry.get("sampling") or {}
        offsets = sampling.get("requested_offsets_seconds") or []
        rows.append(
            "<tr><td>" + html.escape(entry.get("candidate_ref") or "-") + "</td>"
            "<td><code>" + html.escape(entry.get("file_id", "")) + "</code></td>"
            "<td>" + html.escape(entry.get("media_kind", "")) + "</td>"
            "<td>" + html.escape(entry.get("relative_path", "")) + "</td>"
            "<td>" + html.escape(entry.get("status", "")) + "</td>"
            "<td>" + html.escape(probe_text) + "</td>"
            "<td>" + html.escape(", ".join("%.3f" % value for value in offsets) if offsets else "-")
            + "</td>"
            "<td>" + html.escape(entry.get("reason") or "-") + "</td>"
            "<td>" + (" ".join(links) if links else "-") + "</td></tr>"
        )
    document = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>S3-PREP-C candidate material preview</title>
<style>
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:24px;color:#111;background:#fff}
.banner{border:2px solid #b45309;background:#fff7ed;padding:12px 16px;margin:16px 0}
.banner p{margin:4px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #d4d4d8;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f4f4f5}
code{font-size:12px}
.note{color:#52525b;font-size:12px}
</style>
</head>
<body>
<h1>S3-PREP-C candidate material preview</h1>
<div class="banner">
<p><strong>__BANNER__</strong></p>
<p>Preview index for the NEXT independent prelabel step. Nothing here is an annotation,
an expected answer, a model output or a quality result. Eligibility only.</p>
<p class="note">selected=__SELECTED__ images=__IMAGES__ videos=__VIDEOS__
eligible=__ELIGIBLE__ not_eligible=__NOT_ELIGIBLE__ not_run=__NOT_RUN__</p>
</div>
<table>
<thead><tr><th>ref</th><th>asset id</th><th>kind</th><th>relative path</th><th>status</th>
<th>probed size / duration</th><th>sample offsets (s)</th><th>reason</th><th>preview</th></tr></thead>
<tbody>
__ROWS__
</tbody>
</table>
<p class="note">Source paths are relative to the approved source root. No absolute path and no
EXIF payload is stored here. Probed size and duration are container facts; they are not a proof
that a full decode happened.</p>
</body>
</html>
"""
    replacements = {
        "__BANNER__": html.escape(PREVIEW_BANNER),
        "__SELECTED__": str(summary.get("selected", 0)),
        "__IMAGES__": str(summary.get("images", 0)),
        "__VIDEOS__": str(summary.get("videos", 0)),
        "__ELIGIBLE__": str(summary.get("eligible", 0)),
        "__NOT_ELIGIBLE__": str(summary.get("not_eligible", 0)),
        "__NOT_RUN__": str(summary.get("not_run", 0)),
        "__ROWS__": "\n".join(rows),
    }
    for token, value in replacements.items():
        document = document.replace(token, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


class OutputAccountant:
    """Counts every byte this run writes, temporary and retained."""

    def __init__(self) -> None:
        self.retained_bytes = 0
        self.staging_bytes = 0

    def add_retained(self, size: int) -> None:
        self.retained_bytes += int(size)

    def add_staging(self, size: int) -> None:
        self.staging_bytes += int(size)

    @property
    def total(self) -> int:
        return self.retained_bytes + self.staging_bytes


def _prepare_image(entry, path: Path, previews: Path, accountant, counters, long_edge: int) -> dict:
    result = {"status": "not_eligible", "reason": None, "probe": {}, "sampling": {}, "warnings": []}
    size_bytes = path.stat().st_size
    if size_bytes > IMAGE_MAX_BYTES:
        result["reason"] = "image_bytes_over_limit"
        result["probe"] = {"bytes": size_bytes}
        return result
    extension = Path(entry["relative_path"]).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        result["reason"] = "image_extension_not_allowed"
        result["probe"] = {"bytes": size_bytes}
        return result
    target = previews / ("%s.jpg" % entry["file_id"])

    def _count_decode():
        counters["image_decode_calls"] += 1

    try:
        info = render_thumbnail(
            path,
            target,
            long_edge,
            max_pixels=int(EXPECTED_LIMITS["image_max_pixels"]),
            on_decode=_count_decode,
        )
    except ValueError as exc:
        text = str(exc)
        if text.startswith("image_pixels_over_limit"):
            result["reason"] = text.split(":")[0]
            result["probe"] = {"bytes": size_bytes, "pixels": None}
        else:
            result["reason"] = "image_decode_failed:%s" % type(exc).__name__
            result["probe"] = {"bytes": size_bytes}
        return result
    except Exception as exc:
        result["reason"] = "image_decode_failed:%s" % type(exc).__name__
        result["probe"] = {"bytes": size_bytes}
        return result
    accountant.add_retained(info["bytes"])
    result["status"] = "eligible"
    result["probe"] = {
        "bytes": size_bytes,
        "format": info["source_format"],
        "width": info["source_width"],
        "height": info["source_height"],
        "pixels": info["source_width"] * info["source_height"],
        "exif_orientation_applied": info["exif_orientation_applied"],
        "thumbnail_width": info["thumbnail_width"],
        "thumbnail_height": info["thumbnail_height"],
    }
    result["thumbnail"] = "previews/%s.jpg" % entry["file_id"]
    result["thumbnail_sha256"] = info["sha256"]
    result["thumbnail_bytes"] = info["bytes"]
    result["sampling"] = {
        "requested_offsets_seconds": [],
        "frames": [],
        "note": "an image contributes exactly one thumbnail and no sampled frame",
    }
    return result


def _prepare_video(entry, path: Path, previews: Path, staging: Path, accountant, counters,
                   adapter, long_edge: int) -> dict:
    result = {"status": "not_eligible", "reason": None, "probe": {}, "sampling": {}, "warnings": []}
    size_bytes = path.stat().st_size
    if size_bytes > VIDEO_MAX_BYTES:
        result["reason"] = "video_bytes_over_limit"
        result["probe"] = {"bytes": size_bytes}
        return result
    extension = Path(entry["relative_path"]).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        result["reason"] = "video_extension_not_allowed"
        result["probe"] = {"bytes": size_bytes}
        return result
    counters["ffprobe_calls"] += 1
    probe_entry, document = adapter.probe_video(path, "probe-%s" % entry["file_id"])
    if probe_entry.get("exit_code") != 0 or not isinstance(document, dict):
        result["reason"] = "video_probe_failed"
        result["probe"] = {"bytes": size_bytes}
        return result
    formats = str((document.get("format") or {}).get("format_name") or "")
    containers = [part.strip() for part in formats.split(",") if part.strip()]
    video_streams = [
        stream
        for stream in (document.get("streams") or [])
        if isinstance(stream, dict) and stream.get("codec_type") == "video"
    ]
    result["probe"] = {
        "bytes": size_bytes,
        "container": ",".join(containers),
        "container_format_name": formats,
    }
    if not video_streams:
        result["reason"] = "video_stream_missing"
        return result
    if "mov" not in containers and "mp4" not in containers:
        result["reason"] = "video_container_not_mp4_or_mov"
        return result
    stream = video_streams[0]
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    duration_raw = (document.get("format") or {}).get("duration")
    if duration_raw in (None, "N/A"):
        duration_raw = stream.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError):
        duration = None
    result["probe"].update(
        {
            "width": width,
            "height": height,
            "pixels": width * height,
            "codec_name": stream.get("codec_name"),
            "duration_seconds": duration,
        }
    )
    if width <= 0 or height <= 0:
        result["reason"] = "video_dimensions_unknown"
        return result
    if duration is None or duration <= 0:
        result["reason"] = "video_duration_unknown"
        return result
    if duration > EXPECTED_LIMITS["video_max_duration_seconds"]:
        result["reason"] = "video_duration_over_limit"
        return result
    if width * height > EXPECTED_LIMITS["video_max_source_pixels"]:
        result["reason"] = "video_source_pixels_over_limit"
        return result

    # Independent sample points, reduced when the clip is too short for them.
    offsets = []
    for fraction in SAMPLE_FRACTIONS:
        offset = duration * fraction
        if offsets and (offset - offsets[-1]) < MIN_SAMPLE_SPACING_SECONDS:
            result["warnings"].append(
                "sample_point_dropped_not_independent:%.3f" % offset
            )
            continue
        offsets.append(offset)
    frames = []
    seen_hashes = {}
    for frame_index, offset in enumerate(offsets):
        counters["ffmpeg_frame_calls"] += 1
        staged = staging / "frames" / entry["file_id"] / ("frame-%02d.jpg" % (frame_index + 1))
        staged.parent.mkdir(parents=True, exist_ok=True)
        frame_entry = adapter.extract_frame(
            path, offset, staged, "frame-%s-%02d" % (entry["file_id"], frame_index + 1)
        )
        if frame_entry.get("exit_code") != 0 or not staged.is_file():
            result["warnings"].append("frame_extraction_failed_at:%.3f" % offset)
            continue
        accountant.add_staging(staged.stat().st_size)
        target = previews / entry["file_id"] / ("frame-%02d.jpg" % (frame_index + 1))
        try:
            info = render_thumbnail(staged, target, long_edge)
        except Exception as exc:
            result["warnings"].append("frame_render_failed:%s" % type(exc).__name__)
            continue
        accountant.add_retained(info["bytes"])
        duplicate_of = seen_hashes.get(info["sha256"])
        if duplicate_of:
            result["warnings"].append(
                "duplicate_frame_content_matches:%s" % duplicate_of
            )
        else:
            seen_hashes[info["sha256"]] = "frame-%02d" % (frame_index + 1)
        frames.append(
            {
                "name": "frame-%02d" % (frame_index + 1),
                "path": "previews/%s/frame-%02d.jpg" % (entry["file_id"], frame_index + 1),
                "requested_offset_seconds": offset,
                "sha256": info["sha256"],
                "bytes": info["bytes"],
                "width": info["thumbnail_width"],
                "height": info["thumbnail_height"],
                "duplicate_of": duplicate_of,
            }
        )
    if not frames:
        result["reason"] = "video_not_decodable"
        return result
    result["status"] = "eligible"
    result["sampling"] = {
        "requested_offsets_seconds": offsets,
        "frames": frames,
        "distinct_frame_hashes": len(seen_hashes),
        "note": "offsets are requested sample points; actual presentation timestamps are "
                "not proven by a full decode",
    }
    return result


def prepare(
    *,
    package_root: Path,
    child: dict,
    runtime_root: Path,
    adapter: MediaAdapter,
    receipt_path: Path,
    source_root: Path = None,
    clock=time.monotonic,
) -> dict:
    """Execute the single bounded preparation run and build the terminal receipt."""
    package_root = Path(package_root)
    runtime_root = Path(os.path.abspath(str(runtime_root)))
    receipt_path = Path(receipt_path)
    started = clock()
    limits = child["limits"]
    deadline = started + float(limits["wall_seconds"])

    if receipt_path.exists():
        raise PreflightError("terminal_receipt_already_exists:%s" % receipt_path)
    if runtime_root.exists():
        raise PreflightError("runtime_root_already_exists:%s" % runtime_root)

    source_root = Path(source_root if source_root is not None else child["source_root"])
    accountant = OutputAccountant()
    counters = {
        "source_files_hashed": 0,
        "source_bytes_hashed": 0,
        "admitted_files": 0,
        "admitted_bytes": 0,
        "image_decode_calls": 0,
        "ffprobe_calls": 0,
        "ffmpeg_frame_calls": 0,
        "not_eligible": 0,
        "eligible": 0,
        "not_run": 0,
        "source_changed": False,
        "internal_error": None,
    }
    reasons = {}
    run_reasons = {}
    candidates = []
    index_entries = []
    staging = runtime_root / "staging"
    cleanup = {
        "staging_path": relative_to_package(staging, package_root),
        "staging_removed": False,
        "staging_residual_entries": None,
        "temporary_directories_created": 0,
        "temporary_directories_removed": 0,
        "subprocesses_started": 0,
        "owned_pids_only": True,
        "source_files_modified": 0,
        "source_files_deleted": 0,
    }

    runtime_root.mkdir(parents=True, exist_ok=False)
    cleanup["temporary_directories_created"] = 1
    previews = runtime_root / "previews"
    contacts = runtime_root / "contactsheets"
    raw_dir = runtime_root / "raw"
    for directory in (previews, contacts, raw_dir):
        directory.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)

    selected = child["selected_files"]

    def index_row(record, probe=None, sampling=None, thumbnail=None, frames=None, sheet=None):
        return {
            "candidate_ref": record.get("candidate_ref"),
            "file_id": record.get("file_id"),
            "media_kind": record.get("media_kind"),
            "relative_path": record.get("relative_path"),
            "status": record.get("status"),
            "reason": record.get("reason"),
            "probe": probe if probe is not None else {},
            "sampling": sampling if sampling is not None else {},
            "thumbnail": thumbnail,
            "frames": frames or [],
            "contact_sheet": sheet,
        }

    def mark_not_run(entry, reason):
        counters["not_run"] += 1
        run_reasons[reason] = run_reasons.get(reason, 0) + 1
        record = {
            "candidate_ref": None,
            "file_id": entry.get("file_id"),
            "relative_path": entry.get("relative_path"),
            "media_kind": entry.get("media_kind"),
            "status": "not_run",
            "reason": reason,
        }
        candidates.append(record)
        index_entries.append(index_row(record))

    def mark_not_eligible(record, reason):
        record["status"] = "not_eligible"
        record["reason"] = reason
        counters["not_eligible"] += 1
        reasons[reason] = reasons.get(reason, 0) + 1
        candidates.append(record)
        index_entries.append(index_row(record))

    try:
        for index, entry in enumerate(selected):
            if clock() > deadline:
                mark_not_run(entry, "wall_budget_exhausted")
                continue
            record = {
                "candidate_ref": "C%02d" % (index + 1),
                "file_id": entry.get("file_id"),
                "relative_path": entry.get("relative_path"),
                "media_kind": entry.get("media_kind"),
                "status": None,
                "reason": None,
                "source_bytes": entry.get("bytes"),
                "source_sha256_verified": False,
            }
            # 1. path policy: symlink, traversal and escape are refused.
            try:
                resolved = resolve_source_path(source_root, entry["relative_path"])
            except PolicyError as exc:
                mark_not_eligible(record, str(exc))
                continue
            # 2. stat identity against the frozen size.
            try:
                stat_result = resolved.stat()
            except OSError as exc:
                mark_not_eligible(record, "source_stat_failed:%s" % type(exc).__name__)
                continue
            if not os.path.isfile(str(resolved)):
                mark_not_eligible(record, "source_not_a_regular_file")
                continue
            if stat_result.st_size != int(entry["bytes"]):
                record["observed_bytes"] = stat_result.st_size
                mark_not_eligible(record, "source_size_mismatch")
                continue

            # 3. exactly one hash pass per source file.
            try:
                digest, read_bytes = sha256_file(resolved, deadline=deadline, clock=clock)
            except TimeoutError:
                record["status"] = "not_run"
                record["reason"] = "wall_budget_exhausted_during_hash"
                counters["not_run"] += 1
                run_reasons[record["reason"]] = run_reasons.get(record["reason"], 0) + 1
                candidates.append(record)
                index_entries.append(index_row(record))
                continue
            except OSError as exc:
                mark_not_eligible(record, "source_read_failed:%s" % type(exc).__name__)
                continue
            counters["source_files_hashed"] += 1
            counters["source_bytes_hashed"] += read_bytes
            record["source_sha256_observed"] = digest

            # 4. a content change is a terminal state for the whole run.
            if digest != entry["sha256"]:
                counters["source_changed"] = True
                mark_not_eligible(record, "SOURCE_CHANGED")
                for pending in selected[index + 1:]:
                    mark_not_run(pending, "source_changed_terminal")
                break

            record["source_sha256_verified"] = True
            counters["admitted_files"] += 1
            counters["admitted_bytes"] += int(entry["bytes"])

            # 5. the media probe / decode.
            if entry["media_kind"] == "image":
                outcome = _prepare_image(
                    entry,
                    resolved,
                    previews,
                    accountant,
                    counters,
                    int(limits["preview_long_edge"]),
                )
            else:
                outcome = _prepare_video(
                    entry,
                    resolved,
                    previews,
                    staging,
                    accountant,
                    counters,
                    adapter,
                    int(limits["preview_long_edge"]),
                )
            record["status"] = outcome["status"]
            record["reason"] = outcome["reason"]
            record["probe"] = outcome.get("probe", {})
            record["sampling"] = outcome.get("sampling", {})
            record["warnings"] = outcome.get("warnings", [])
            if outcome.get("thumbnail"):
                record["thumbnail"] = outcome["thumbnail"]
                record["thumbnail_sha256"] = outcome.get("thumbnail_sha256")
            if outcome.get("sampling", {}).get("frames"):
                record["frames"] = outcome["sampling"]["frames"]

            sheet_relative = None
            if outcome["status"] == "eligible":
                counters["eligible"] += 1
                if outcome.get("thumbnail"):
                    tiles = [previews / ("%s.jpg" % entry["file_id"])]
                else:
                    tiles = [
                        previews / entry["file_id"] / ("frame-%02d.jpg" % (number + 1))
                        for number in range(len(outcome.get("sampling", {}).get("frames", [])))
                    ]
                if tiles:
                    sheet = contacts / ("%s.jpg" % entry["file_id"])
                    try:
                        sheet_info = render_contact_sheet(
                            tiles, sheet, "%s %s" % (entry["file_id"], entry["media_kind"])
                        )
                        accountant.add_retained(sheet_info["bytes"])
                        sheet_relative = "contactsheets/%s.jpg" % entry["file_id"]
                        record["contact_sheet"] = sheet_relative
                        record["contact_sheet_sha256"] = sheet_info["sha256"]
                    except Exception as exc:
                        record.setdefault("warnings", []).append(
                            "contact_sheet_failed:%s" % type(exc).__name__
                        )
            else:
                counters["not_eligible"] += 1
                reasons[outcome["reason"]] = reasons.get(outcome["reason"], 0) + 1
            candidates.append(record)
            index_entries.append(
                index_row(
                    record,
                    probe=record.get("probe", {}),
                    sampling=record.get("sampling", {}),
                    thumbnail=record.get("thumbnail"),
                    frames=[
                        {"name": frame["name"], "path": frame["path"]}
                        for frame in record.get("frames", []) or []
                    ],
                    sheet=sheet_relative,
                )
            )
            if accountant.total > int(limits["output_bytes"]):
                for pending in selected[index + 1:]:
                    mark_not_run(pending, "output_budget_exhausted")
                break
    except Exception as exc:  # a failure is a terminal state, never a retry
        counters["internal_error"] = "%s:%s" % (type(exc).__name__, exc)
        processed = len(candidates)
        for pending in selected[processed:]:
            mark_not_run(pending, "internal_error_terminal")
    finally:
        # staging is always removed and the removal is measured
        try:
            shutil.rmtree(str(staging), ignore_errors=False)
        except OSError:
            pass
        cleanup["staging_removed"] = not staging.exists()
        cleanup["staging_residual_entries"] = (
            len(list(staging.iterdir())) if staging.exists() else 0
        )
        cleanup["temporary_directories_removed"] = 1 if cleanup["staging_removed"] else 0
        cleanup["subprocesses_started"] = len(adapter.run_log)

    # -- raw command evidence ------------------------------------------------
    raw_entries = []
    for number, entry in enumerate(list(adapter.run_log), start=1):
        label = entry.get("label", "step")
        command_text = " ".join(entry.get("argv", []))
        stdout_text = entry.get("stdout_text", "")
        stderr_text = entry.get("stderr_text", "")
        item = {
            "index": number,
            "label": label,
            "kind": entry.get("kind"),
            "exit_code": entry.get("exit_code"),
            "timeout_seconds": entry.get("timeout_seconds"),
            "stdout_bytes": entry.get("stdout_bytes"),
            "stderr_bytes": entry.get("stderr_bytes"),
            "stdout_sha256": entry.get("stdout_sha256"),
            "stderr_sha256": entry.get("stderr_sha256"),
            "error": entry.get("error"),
            "command_sha256": sha256_bytes(command_text.encode("utf-8")),
        }
        raw_entries.append(item)
        (raw_dir / ("%03d-%s.command.log" % (number, label))).write_text(
            command_text + "\n", encoding="utf-8"
        )
        (raw_dir / ("%03d-%s.stdout.log" % (number, label))).write_text(
            stdout_text, encoding="utf-8"
        )
        (raw_dir / ("%03d-%s.stderr.log" % (number, label))).write_text(
            stderr_text, encoding="utf-8"
        )
        (raw_dir / ("%03d-%s.exit.log" % (number, label))).write_text(
            "%s\n" % (entry.get("exit_code") if entry.get("exit_code") is not None else "NONE"),
            encoding="utf-8",
        )

    # -- preview index --------------------------------------------------------
    summary = {
        "selected": len(selected),
        "images": sum(1 for item in selected if item.get("media_kind") == "image"),
        "videos": sum(1 for item in selected if item.get("media_kind") == "video"),
        "eligible": counters["eligible"],
        "not_eligible": counters["not_eligible"],
        "not_run": counters["not_run"],
    }
    index_path = runtime_root / "index.html"
    render_index(index_path, index_entries, summary)

    conservation = (
        counters["eligible"] + counters["not_eligible"] + counters["not_run"] == len(selected)
    )

    # -- runtime receipt (absolute local paths stay here) ---------------------
    runtime_candidates = []
    for item in candidates:
        absolute = None
        if item.get("status") != "not_run":
            try:
                absolute = str(resolve_source_path(source_root, item["relative_path"]))
            except PolicyError:
                absolute = None
        runtime_candidates.append(dict(item, absolute_source_path=absolute))
    runtime_receipt = {
        "kind": "S3_PREP_C_RUNTIME_RECEIPT",
        "authority": "LOCAL_RUNTIME_ARTEFACT",
        "run_id": runtime_root.name,
        "generated_at": now_iso(),
        "absolute_runtime_root": str(runtime_root),
        "absolute_source_root": str(source_root),
        "absolute_preview_index": str(index_path),
        "counts": dict(counters),
        "summary": summary,
        "candidates": runtime_candidates,
        "budget": {
            "source_files_hashed": counters["source_files_hashed"],
            "source_bytes_hashed": counters["source_bytes_hashed"],
            "admitted_source_bytes": counters["admitted_bytes"],
            "image_decode_calls": counters["image_decode_calls"],
            "ffprobe_calls": counters["ffprobe_calls"],
            "ffmpeg_frame_calls": counters["ffmpeg_frame_calls"],
            "output_bytes_retained": accountant.retained_bytes,
            "output_bytes_staging": accountant.staging_bytes,
            "decoder_disk_io_bytes": "NOT_MEASURED_NOT_CLAIMED",
        },
        "cleanup": dict(cleanup),
        "note": "absolute local paths stay in this runtime receipt; the committed receipt "
                "keeps project relative paths only",
    }
    runtime_receipt_path = runtime_root / "runtime-receipt.json"
    write_json(runtime_receipt_path, runtime_receipt)

    # -- retained tree --------------------------------------------------------
    tree = []
    for path in sorted(runtime_root.rglob("*")):
        if path.is_file():
            tree.append(
                {
                    "path": relative_to_package(path, package_root),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path)[0],
                }
            )
    retained_bytes = sum(item["bytes"] for item in tree)

    decision = "PREPARATION_COMPLETE_READY_FOR_REVIEW"
    if counters["internal_error"]:
        decision = "PREPARATION_FAILED_INTERNAL_ERROR"
    elif counters["source_changed"]:
        decision = "SOURCE_CHANGED_TERMINAL"
    elif not cleanup["staging_removed"]:
        decision = "PREPARATION_FAILED_CLEANUP_NOT_PROVEN"
    elif not conservation:
        decision = "PREPARATION_FAILED_COUNT_NOT_CONSERVED"
    elif retained_bytes > int(limits["output_bytes"]):
        decision = "PREPARATION_FAILED_OUTPUT_BUDGET_EXCEEDED"

    receipt = {
        "kind": "S3_PREP_C_CANDIDATE_PREPARATION_TERMINAL_RECEIPT",
        "scope": "PREPARATION_ELIGIBILITY_AND_PREVIEW_ONLY",
        "authority": "AUTHORITATIVE",
        "run_id": runtime_root.name,
        "decision": decision,
        "product_gate0": False,
        "stage_pass_claim": False,
        "quality_claim": "NONE_ELIGIBILITY_IS_NOT_QUALITY_EVIDENCE",
        "quality_set_frozen": False,
        "prelabel_stage_complete": False,
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "finished_at": now_iso(),
        "counts": {
            "selected_total": len(selected),
            "images_selected": summary["images"],
            "videos_selected": summary["videos"],
            "eligible": counters["eligible"],
            "not_eligible": counters["not_eligible"],
            "not_run": counters["not_run"],
            "conservation_ok": conservation,
            "conservation_formula": "selected_total == eligible + not_eligible + not_run",
            "admitted": counters["admitted_files"],
            "admitted_bytes": counters["admitted_bytes"],
            "not_eligible_by_reason": reasons,
            "not_run_by_reason": run_reasons,
            "internal_error": counters["internal_error"],
        },
        "candidates": candidates,
        "budget": {
            "wall_seconds_limit": limits["wall_seconds"],
            "wall_seconds_used": round(clock() - started, 3),
            "source_files_hashed": counters["source_files_hashed"],
            "hash_passes_per_file": limits["hash_passes_per_file"],
            "source_bytes_hashed": counters["source_bytes_hashed"],
            "admitted_source_bytes": counters["admitted_bytes"],
            "admitted_source_bytes_limit": limits["admitted_source_bytes"],
            "image_decode_calls": counters["image_decode_calls"],
            "image_decode_limit_per_image": limits["image_decodes_per_image"],
            "ffprobe_calls": counters["ffprobe_calls"],
            "ffprobe_limit_per_video": limits["ffprobe_calls_per_video"],
            "ffmpeg_frame_calls": counters["ffmpeg_frame_calls"],
            "ffmpeg_frame_limit_per_video": limits["frame_extractions_per_video"],
            "output_bytes_retained": retained_bytes,
            "output_bytes_staging": accountant.staging_bytes,
            "output_bytes_limit": limits["output_bytes"],
            "decoder_disk_io_bytes": "NOT_MEASURED_NOT_CLAIMED",
            "model_actions": 0,
            "gpu_actions": 0,
            "services": 0,
            "network_calls": 0,
            "downloads": 0,
            "full_product_checkpoints": 0,
            "browser_sessions": 0,
        },
        "runtime": {
            "relative_path": relative_to_package(runtime_root, package_root),
            "absolute_path_recorded_in": relative_to_package(runtime_receipt_path, package_root),
            "index_entry": relative_to_package(index_path, package_root),
            "retained": True,
            "retained_reason": "registered retained artefact for the next independent prelabel step",
            "is_zero_residue": False,
            "file_count": len(tree),
            "total_bytes": retained_bytes,
            "files": tree,
        },
        "cleanup": dict(cleanup),
        "raw_evidence": {
            "committed": relative_to_package(receipt_path.parent / "raw", package_root),
            "exact_raw": relative_to_package(raw_dir, package_root),
            "redaction": "the committed copy replaces the absolute source root and the "
                         "absolute runtime root; the exact copy stays in the runtime root",
            "commands": raw_entries,
        },
        "limitations": [
            "eligibility only: no model, no GPU, no service, no download and no full product "
            "checkpoint was used",
            "no LVW or product analysis call was made and no semantic label, expected answer "
            "or quality verdict was produced",
            "probed size and duration are container facts, not a proof that a full decode ran",
            "requested sample offsets are not a proof of the actual presentation timestamps",
            "decoder disk IO was not measured and is not claimed",
            "the retained preview is material for the next independent prelabel step and is "
            "not a quality result",
            "the source was read only; no source file was copied, modified or deleted",
        ],
    }
    return receipt

def redact_text(text: str, replacements: list) -> tuple:
    out = text
    hits = 0
    for needle, token in replacements:
        if needle:
            hits += out.count(needle)
            out = out.replace(needle, token)
    return out, hits


def write_redacted_raw(receipt: dict, package_root: Path, target: Path) -> dict:
    """Copy the exact raw logs into the committed report with paths redacted."""
    source_root = receipt.get("_absolute_source_root")
    runtime_root = receipt.get("_absolute_runtime_root")
    replacements = []
    if source_root:
        replacements.append((str(source_root), "<SOURCE_ROOT>"))
    if runtime_root:
        replacements.append((str(runtime_root), "<RUNTIME_ROOT>"))
    target.mkdir(parents=True, exist_ok=True)
    hits = 0
    written = 0
    raw_root = Path(runtime_root) / "raw" if runtime_root else None
    if raw_root and raw_root.is_dir():
        for path in sorted(raw_root.iterdir()):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            redacted, count = redact_text(text, replacements)
            hits += count
            (target / path.name).write_text(redacted, encoding="utf-8")
            written += 1
    return {"files": written, "redactions": hits, "directory": relative_to_package(target, package_root)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _child_from_path(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def command_preflight(args, package_root: Path = None) -> int:
    package_root = Path(package_root) if package_root is not None else ROOT
    child_path = Path(args.child)
    if not child_path.is_absolute():
        child_path = package_root / child_path
    preflight_path = Path(args.preflight)
    if not preflight_path.is_absolute():
        preflight_path = package_root / preflight_path
    runtime_root = Path(args.runtime_output)
    if not runtime_root.is_absolute():
        print(json.dumps({"decision": "PREFLIGHT_REJECTED",
                          "reason": "runtime_output_must_be_absolute"}, indent=2),
              file=sys.stderr)
        return 1
    if preflight_path.exists():
        print(json.dumps({"decision": "PREFLIGHT_REJECTED",
                          "reason": "preflight_file_already_exists",
                          "preflight": str(args.preflight)}, indent=2), file=sys.stderr)
        return 1
    try:
        preflight = build_preflight(
            package_root=package_root,
            child_path=child_path,
            candidate_sha=args.candidate,
            runtime_root=runtime_root,
        )
    except PreflightError as exc:
        print(json.dumps({"decision": "PREFLIGHT_REJECTED", "reason": str(exc)}, indent=2),
              file=sys.stderr)
        return 1
    write_json(preflight_path, preflight)
    summary = {
        "decision": preflight["decision"],
        "summary": preflight["summary"],
        "failed_checks": [item["id"] for item in preflight["checks"] if not item["passed"]],
        "preflight": str(args.preflight),
        "runtime_relative_path": preflight["runtime"]["relative_path"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if preflight["decision"] == "PREFLIGHT_PASSED" else 1


def command_run(args, package_root: Path = None) -> int:
    package_root = Path(package_root) if package_root is not None else ROOT
    child_path = Path(args.child)
    if not child_path.is_absolute():
        child_path = package_root / child_path
    preflight_path = Path(args.preflight)
    if not preflight_path.is_absolute():
        preflight_path = package_root / preflight_path
    receipt_path = Path(args.receipt)
    if not receipt_path.is_absolute():
        receipt_path = package_root / receipt_path
    runtime_root = Path(os.path.abspath(str(args.runtime_output)))
    if not Path(args.runtime_output).is_absolute():
        print(json.dumps({"decision": "REFUSED", "reason": "runtime_output_must_be_absolute"},
                         indent=2), file=sys.stderr)
        return 1

    if receipt_path.exists():
        print(json.dumps({"decision": "REFUSED", "reason": "terminal_receipt_already_exists"},
                         indent=2), file=sys.stderr)
        return 1
    if not preflight_path.is_file():
        print(json.dumps({"decision": "REFUSED", "reason": "preflight_missing"}, indent=2),
              file=sys.stderr)
        return 1
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("decision") != "PREFLIGHT_PASSED":
        print(json.dumps({"decision": "REFUSED", "reason": "preflight_not_passed"}, indent=2),
              file=sys.stderr)
        return 1
    if preflight.get("candidate", {}).get("sha") != args.candidate:
        print(json.dumps({"decision": "REFUSED", "reason": "candidate_drift"}, indent=2),
              file=sys.stderr)
        return 1
    child = _child_from_path(child_path)
    if sha256_bytes(child_path.read_bytes()) != preflight.get("child", {}).get("sha256"):
        print(json.dumps({"decision": "REFUSED", "reason": "child_drift"}, indent=2), file=sys.stderr)
        return 1
    catalog_path = package_root / CATALOG_REL
    if not catalog_path.is_file():
        print(json.dumps({"decision": "REFUSED", "reason": "catalog_missing"}, indent=2),
              file=sys.stderr)
        return 1
    if sha256_file(catalog_path)[0] != preflight.get("catalog", {}).get("sha256"):
        print(json.dumps({"decision": "REFUSED", "reason": "catalog_drift"}, indent=2),
              file=sys.stderr)
        return 1
    holdout_path = package_root / HOLDOUT_REL
    if not holdout_path.is_file() or sha256_file(holdout_path)[0] != preflight.get(
        "holdout_manifest", {}
    ).get("sha256"):
        print(json.dumps({"decision": "REFUSED", "reason": "holdout_manifest_drift"}, indent=2),
              file=sys.stderr)
        return 1
    for relative in (SCRIPT_REL, TEST_REL, BRIDGE_RUNNER_REL):
        blob = git_blob(package_root, args.candidate, relative)
        disk = package_root / relative
        if not blob or not disk.is_file() or sha256_bytes(blob) != sha256_file(disk)[0]:
            print(json.dumps({"decision": "REFUSED", "reason": "code_candidate_drift:%s" % relative},
                             indent=2), file=sys.stderr)
            return 1
    if runtime_root.exists():
        print(json.dumps({"decision": "REFUSED", "reason": "runtime_root_already_exists"},
                         indent=2), file=sys.stderr)
        return 1
    if preflight.get("runtime", {}).get("relative_path") != relative_to_package(
        runtime_root, package_root
    ):
        print(json.dumps({"decision": "REFUSED", "reason": "runtime_drift"}, indent=2),
              file=sys.stderr)
        return 1
    guard_result = _guard_for_run(package_root)
    if guard_result.get("decision") != "HANDOFF_READINESS_VERIFIED":
        print(json.dumps({"decision": "REFUSED", "reason": "handoff_guard_rejected"}, indent=2),
              file=sys.stderr)
        return 1

    ffmpeg = Path(preflight["tools"]["ffmpeg"]["real_path"])
    ffprobe = Path(preflight["tools"]["ffprobe"]["real_path"])
    adapter = MediaAdapter(ffmpeg, ffprobe)
    try:
        receipt = prepare(
            package_root=package_root,
            child=child,
            runtime_root=runtime_root,
            adapter=adapter,
            receipt_path=receipt_path,
        )
    except PreflightError as exc:
        print(json.dumps({"decision": "REFUSED", "reason": str(exc)}, indent=2), file=sys.stderr)
        return 1
    receipt["_absolute_source_root"] = str(child["source_root"])
    receipt["_absolute_runtime_root"] = str(runtime_root)
    redacted = write_redacted_raw(receipt, package_root, receipt_path.parent / "raw")
    receipt["raw_evidence"]["redacted_copy"] = redacted
    receipt["handoff_guard"] = {
        "decision": guard_result.get("decision"),
        "authority": guard_result.get("authority"),
        "summary": guard_result.get("summary"),
    }
    receipt["preflight"] = {
        "path": relative_to_package(preflight_path, package_root),
        "sha256": sha256_file(preflight_path)[0],
        "decision": preflight.get("decision"),
    }
    receipt["child"] = {
        "path": relative_to_package(child_path, package_root),
        "sha256": preflight["child"]["sha256"],
        "child_id": preflight["child"]["child_id"],
    }
    receipt["catalog"] = preflight["catalog"]
    receipt["holdout_manifest"] = preflight["holdout_manifest"]
    receipt["candidate"] = preflight["candidate"]
    receipt["tools"] = preflight["tools"]
    for key in ("_absolute_source_root", "_absolute_runtime_root"):
        receipt.pop(key, None)
    write_json(receipt_path, receipt)
    print(
        json.dumps(
            {
                "decision": receipt["decision"],
                "counts": receipt["counts"],
                "budget": receipt["budget"],
                "runtime_index_entry": receipt["runtime"]["index_entry"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if receipt["decision"] == "PREPARATION_COMPLETE_READY_FOR_REVIEW" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="S3-PREP-C bounded candidate eligibility probe and local preview preparation."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight", help="evaluate the global preflight gate")
    pre.add_argument("--child", required=True, help="frozen child JSON")
    pre.add_argument("--candidate", required=True, help="40 hex code candidate commit sha")
    pre.add_argument("--preflight", required=True, help="preflight artefact to write")
    pre.add_argument("--runtime-output", required=True, help="absolute runtime output root")
    pre.set_defaults(func=command_preflight)

    run = sub.add_parser("run", help="execute the single bounded preparation run")
    run.add_argument("--child", required=True, help="frozen child JSON")
    run.add_argument("--candidate", required=True, help="40 hex code candidate commit sha")
    run.add_argument("--preflight", required=True, help="preflight artefact to read")
    run.add_argument("--runtime-output", required=True, help="absolute runtime output root")
    run.add_argument("--receipt", required=True, help="terminal receipt JSON to write")
    run.set_defaults(func=command_run)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
