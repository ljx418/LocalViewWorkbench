"""S3-P3B offline quality execution (QD) and independent score recomputation (QS).

This module is a composable internal phase.  It has no CLI, it never starts or
stops a service, it never downloads anything, it never mutates the authority
ledger and it never announces a Stage or product verdict.  It implements the
frozen internal contract ``reports/v0-s3/product-gate0/p3b-quality-contract.md``
(read fully by the implementer before this file was written).

Two independent entry points live here:

``QualityPhase.run()``
    QD.  Executes the fixed sixteen S3 quality rows through the existing public
    S2 driver path (``submit`` -> Comfy ``/prompt`` -> ``/history``), persists
    the actual raw bytes *before* any structural validation and produces a
    sixteen-row execution receipt.  It never scores quality and it never calls
    the QS entry point.

``recompute_scores()``
    QS.  A pure validation/aggregation entry point.  It consumes a QD execution
    receipt, the actual artifact root and independently supplied scoring
    receipts.  It never executes a model, never keyword-matches a raw response
    and never fabricates a semantic judgement.  The QD path never calls it.

Driver protocol
---------------

The phase owns no process, no budget and no ledger.  The parent coordinator
owns the real profile, the model digest, the media staging, the child
authorization, the single GPU, the original process ownership and the later
archive.  The phase consumes the *existing public* ``NativeRuntime`` surface
(``tools/v0_s2_runtime.py``); every method below already exists in that
runtime except one read-only residue accessor that the parent supplies as a
thin adapter when it stages the real runtime::

    driver.submit(graph) -> str                       # existing public submit
    driver.chat_log_snapshot() -> dict                # existing public snapshot
    driver.resource_observer() -> None                # existing public observer
    driver._json_request(url, *, payload=None,
                          timeout=..., observer=...)  # existing public JSON call
    driver.owned_listener_birth(port) -> dict         # existing public ownership
    driver.release_preload(binding, worker) -> dict   # existing public release
    driver.video_snapshot_residue() -> list          # owned video snapshot residue
    driver.submissions -> int
    driver.max_public_submissions -> int

``release_preload`` is the accepted default image release path; it is reused
unchanged so that no release marker is ever fabricated by this phase.  The
``video_snapshot_residue`` accessor must enumerate the owned ``lvw-video-*``
snapshot directories that the public video owner would have created below the
Comfy temporary parent; a non-empty list is a cleanup failure and stops the
phase.  No owner, source or product file is modified to provide it.

The phase validates every one of those facts itself.  A driver cannot assert a
pass by returning a favourable string: the phase recomputes the provider chat
count from the raw log bytes, re-reads every persisted artifact, and re-hashes
every source file.
"""

from __future__ import annotations

import copy
import errno
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath

from tools.v0_s2_cancel_evidence import count as provider_chat_count
from tools.v0_s2_checkpoint_oracles import EvidenceError, public_video_oracle
from tools.v0_s2_driver import ROOT, base
from tools.v0_s2_measurements import spec_validator

WORKFLOW_DIR = ROOT / "LVW_V0_RuntimePatch" / "workflows"
IMAGE_WORKFLOW = "image_reverse_prompt_v0.api.json"
VIDEO_WORKFLOW = "video_reverse_prompt_v0.api.json"
LEGACY_GRAPH_HELPERS = ROOT / "reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py"

COMFY_URL = base.COMFY_URL
MODEL_TAG = base.MODEL
COMFY_PORT = 8191
OLLAMA_PORT = 11434

# --- frozen S3 quality execution bounds (contract section "QD") -------------
PHASE_KIND = "S3_P3B_OFFLINE_QUALITY_PHASE"
QD_RECEIPT_KIND = "S3_P3B_QD_EXECUTION_RECEIPT"
QS_RECEIPT_KIND = "S3_P3B_QS_SCORE_RECEIPT"
PROJECTION_SCHEMA_VERSION = "lvw.s3-quality-execution/1"

FIXED_IMAGES = 10
FIXED_VIDEOS = 6
FIXED_TOTAL = 16

IMAGE_PROVIDER_CALLS = 1
VIDEO_PROVIDER_CALLS = 4
MAX_TOTAL_PROVIDER_CALLS = 34
MAX_PUBLIC_SUBMISSIONS = 16

SAMPLE_HISTORY_TIMEOUT_SECONDS = 600
PHASE_TIMEOUT_SECONDS = 10800
HISTORY_POLL_INTERVAL_SECONDS = 0.1
MAX_HISTORY_POLLS = 6000

MAX_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_ARTIFACT_FILES = 256
SOURCE_READ_CHUNK_BYTES = 1024 * 1024

IMAGE_SOURCE_MAX_BYTES = 20 * 1024 * 1024
VIDEO_SOURCE_MAX_BYTES = 256 * 1024 * 1024

PROMPT_MODE = "realistic"
PROMPT_USER_INSTRUCTION = ""
PROMPT_TIMEOUT_SECONDS = 120
IMAGE_LONG_EDGE = 1024

# The public controlled image owner accepts JPEG/PNG/WebP; the public video
# owner accepts MP4/MOV only.  The projection may not widen either set.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov"})

PROJECTION_TOP_LEVEL_KEYS = frozenset({"schema_version", "spec_version", "fixed_denominator", "samples"})
PROJECTION_ROW_KEYS = frozenset({"asset_id", "media_kind", "source_sha256", "source_bytes", "input_reference"})

# The parent capacity proof is a typed internal input.  It is not a ledger API
# and a document like this never proves that a real reservation exists; the
# authentic provider and the actual debit stay with the parent coordinator.
PARENT_PROOF_KIND = "LVW_PARENT_CAPACITY_PROOF/1"

# The receipt states its own serialized size.  The padding field absorbs the
# difference between the assumed and the actual length so that the fixed point
# is exact.
RECEIPT_PADDING_KEY = "receipt_padding"
RECEIPT_FIXED_POINT_ITERATIONS = 64

# The canonical receipt name is the only authoritative terminal receipt.  The
# staged name carries the same bytes but is never authority: a consumer that
# loads it must reject it.
CANONICAL_RECEIPT_NAME = "qd-receipt.json"
STAGED_RECEIPT_NAME = "qd-receipt.staging"

# The mandatory hard end-to-end process supervision is not implemented in this
# offline component.  It belongs to the thin parent coordinator and must be
# demonstrated before a real run or the product Gate0.  The frozen 600s and
# 10800s limits are unchanged.
TIMING_ASSURANCE = {
    "cooperative_pre_and_post_checks": True,
    "synchronous_callables_preemptively_bounded": False,
    "hard_end_to_end_supervision": "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER",
    "hard_supervision_owner": "parent coordinator thin watchdog",
    "sample_history_seconds": SAMPLE_HISTORY_TIMEOUT_SECONDS,
    "phase_seconds": PHASE_TIMEOUT_SECONDS,
    "note": ("A synchronous callable cannot be preemptively bounded by a post-return elapsed "
             "check.  The phase performs cooperative pre and post checks and records the "
             "mandatory parent process supervision as an unimplemented product Gate0 blocker."),
}

# --- bounded elapsed ceilings for the controlled phases of one row ----------
# The frozen 600s/10800s/6000 ceilings bound the whole run; these bound the
# individual controlled steps so one slow callback, observation, persistence
# or release can never silently consume the whole phase budget.
CALLBACK_MAX_SECONDS = 30.0
OBSERVATION_MAX_SECONDS = 30.0
PERSISTENCE_MAX_SECONDS = 60.0
RELEASE_MAX_SECONDS = 60.0

# A row failure that must stop every later public submission.  The codes are
# compared as the stable base of an error string: production errors may carry
# a ``:<path>`` or ``:<detail>`` suffix and must still classify identically.
HALT_ERROR_CODES = frozenset({
    # frozen action budgets
    "PUBLIC_SUBMISSION_BUDGET_EXCEEDED",
    "PROVIDER_CALL_BUDGET_EXCEEDED",
    "HISTORY_POLL_BUDGET_EXCEEDED",
    "PHASE_DEADLINE_EXCEEDED",
    "PARENT_BUDGET_CAPACITY_INSUFFICIENT",
    # uncertain public state: fail closed, never send again
    "PROVIDER_SNAPSHOT_INVALID",
    "PROVIDER_AFTER_SNAPSHOT_FAILED",
    "PROVIDER_LOG_REWRITTEN",
    "PROVIDER_CALL_COUNT_MISMATCH",
    "PROMPT_ID_INVALID",
    "PROMPT_ID_REUSED",
    "LISTENER_IDENTITY_INVALID",
    "LISTENER_IDENTITY_DRIFT",
    "SOURCE_REPLACED",
    "SOURCE_GROWTH",
    "SOURCE_TRUNCATED",
    "RUN_ROOT_REPLACED",
    "RUN_ROOT_REDIRECT",
    "RUN_ROOT_UNAVAILABLE",
    "PHASE_DIRECTORY_REPLACED",
    "PHASE_DIRECTORY_MISSING",
    "PHASE_DIRECTORY_REDIRECT",
    "PHASE_DIRECTORY_EXISTS",
    "OWNED_DIRECTORY_CLOSED",
    "OWNED_DIRECTORY_REPLACED",
    "OWNED_PATH_REPLACED",
    "OWNED_PATH_MISSING",
    "OWNED_CHILD_DIRECTORY_MISSING",
    "OWNED_CHILD_DIRECTORY_UNAVAILABLE",
    "OWNED_CHILD_FILE_UNAVAILABLE",
    "OWNED_MKDIR_FAILED",
    "CLOCK_NOT_MONOTONIC",
    "RECEIPT_FIXED_POINT_UNREACHED",
    "PARENT_BUDGET_PROOF_MISSING",
    "PARENT_BUDGET_PROOF_UNKNOWN",
    "PARENT_BUDGET_PROOF_KIND_INVALID",
    "PARENT_BUDGET_PROOF_RUN_MISMATCH",
    "PARENT_BUDGET_PROOF_CANDIDATE_MISMATCH",
    "PARENT_BUDGET_PROOF_AUTHORIZATION_MISMATCH",
    "PARENT_BUDGET_PROOF_INTERVAL_INVALID",
    "PARENT_BUDGET_PROOF_NOT_YET_VALID",
    "PARENT_BUDGET_PROOF_STALE",
    "PARENT_BUDGET_CAPACITY_INVALID",
    # bounded elapsed ceilings
    "AUTHORIZE_CALLBACK_ELAPSED_EXCEEDED",
    "OBSERVATION_ELAPSED_EXCEEDED",
    "PERSISTENCE_ELAPSED_EXCEEDED",
    "RELEASE_ELAPSED_EXCEEDED",
    "CLOCK_NOT_FINITE",
    # storage failures
    "ARTIFACT_TOO_LARGE",
    "ARTIFACT_TOTAL_BUDGET_EXCEEDED",
    "ARTIFACT_FILE_BUDGET_EXCEEDED",
    "ARTIFACT_WRITE_FAILED",
    "ARTIFACT_REPLAY_FORBIDDEN",
    "ARTIFACT_REDIRECT_FORBIDDEN",
    "ARTIFACT_PATH_INVALID",
    "RECEIPT_PERSISTENCE_FAILED",
    # cleanup / ownership uncertainty
    "RELEASE_EVIDENCE_MISSING",
    "RELEASE_EVIDENCE_UNPROVEN",
    "RELEASE_EVIDENCE_MODEL_RESIDENT",
    "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID",
    "RELEASE_EVIDENCE_GPU_CADENCE_INVALID",
    "RELEASE_EVIDENCE_GPU_STABILITY_INVALID",
    "RELEASE_EVIDENCE_ELAPSED_INVALID",
    "RELEASE_WORKER_MISSING",
    "VIDEO_SNAPSHOT_RESIDUE",
    "VIDEO_SNAPSHOT_RESIDUE_INVALID",
    "VIDEO_SNAPSHOT_RESIDUE_UNKNOWN",
    "RELEASE_EVIDENCE_UNKNOWN",
})

# The stages in which a failure leaves the public provider state unknown.
UNCERTAIN_STAGES = frozenset({"submit", "history", "observe"})

# A row that was never publicly started is BLOCKED, never a FAIL: it stays in
# the fixed denominator without pretending that an execution happened.
NOT_ATTEMPTED_ERROR_CODES = frozenset({
    "PUBLIC_SUBMISSION_BUDGET_EXCEEDED",
    "PROVIDER_CALL_BUDGET_EXCEEDED",
    "ARTIFACT_FILE_BUDGET_EXCEEDED",
    "ARTIFACT_TOTAL_BUDGET_EXCEEDED",
    "ARTIFACT_TOO_LARGE",
    "PARENT_BUDGET_CAPACITY_INSUFFICIENT",
    "PARENT_BUDGET_PROOF_STALE",
    "PARENT_BUDGET_PROOF_NOT_YET_VALID",
    "PARENT_BUDGET_PROOF_RUN_MISMATCH",
    "PARENT_BUDGET_PROOF_CANDIDATE_MISMATCH",
    "PARENT_BUDGET_PROOF_AUTHORIZATION_MISMATCH",
    "PARENT_BUDGET_PROOF_INTERVAL_INVALID",
    "PARENT_BUDGET_PROOF_UNKNOWN",
    "PARENT_BUDGET_PROOF_KIND_INVALID",
    "PARENT_BUDGET_PROOF_MISSING",
    "PHASE_DEADLINE_EXCEEDED",
    "OWNED_DIRECTORY_CLOSED",
    "OWNED_DIRECTORY_REPLACED",
    "OWNED_PATH_REPLACED",
    "OWNED_PATH_MISSING",
    "CLOCK_NOT_MONOTONIC",
    "CLOCK_NOT_FINITE",
})

# A storage failure means the evidence is not proven to exist.  It is reported
# explicitly and it stops every later public submission.
STORAGE_ERROR_CODES = frozenset({
    "ARTIFACT_TOO_LARGE",
    "ARTIFACT_TOTAL_BUDGET_EXCEEDED",
    "ARTIFACT_FILE_BUDGET_EXCEEDED",
    "ARTIFACT_WRITE_FAILED",
    "ARTIFACT_REPLAY_FORBIDDEN",
    "ARTIFACT_REDIRECT_FORBIDDEN",
    "ARTIFACT_PATH_INVALID",
    "RECEIPT_PERSISTENCE_FAILED",
    "PERSISTENCE_ELAPSED_EXCEEDED",
})

# A cleanup failure means the resource state is unknown.  It is reported
# explicitly and it stops every later public submission.
CLEANUP_ERROR_CODES = frozenset({
    "RELEASE_EVIDENCE_MISSING",
    "RELEASE_EVIDENCE_UNPROVEN",
    "RELEASE_EVIDENCE_MODEL_RESIDENT",
    "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID",
    "RELEASE_EVIDENCE_GPU_CADENCE_INVALID",
    "RELEASE_EVIDENCE_GPU_STABILITY_INVALID",
    "RELEASE_EVIDENCE_ELAPSED_INVALID",
    "RELEASE_WORKER_MISSING",
    "RELEASE_ELAPSED_EXCEEDED",
    "VIDEO_SNAPSHOT_RESIDUE",
    "VIDEO_SNAPSHOT_RESIDUE_INVALID",
    "VIDEO_SNAPSHOT_RESIDUE_UNKNOWN",
    "RELEASE_EVIDENCE_UNKNOWN",
})

# Determined, ordinary refusal or structure failures.  A row that failed this
# way, and whose raw is verified and independently reviewed, and whose cleanup
# is proven, may be resolved without being usable (root adjudication
# ``p3b-correction-01.adjudication.json``).  Every other failure leaves the
# evidence unknown and can never pass.
KNOWN_EXECUTION_FAILURE_CODES = frozenset({
    "PUBLIC_EXECUTION_NOT_SUCCESSFUL",
    "PUBLIC_NODE_OUTPUT_MISSING",
    "PUBLIC_IMAGE_OUTPUT_INCOMPLETE",
    "PUBLIC_VIDEO_OUTPUT_INCOMPLETE",
    "PUBLIC_PROMPT_RECORD_INVALID",
    "PUBLIC_PROMPT_ID_MISMATCH",
    "PUBLIC_GRAPH_MISMATCH",
    "IMAGE_RAW_NOT_JSON",
    "IMAGE_RAW_NOT_OBJECT",
    "IMAGE_PROVIDER_RESPONSE_INCOMPLETE",
    "IMAGE_SUGGESTION_NOT_JSON",
    "IMAGE_METADATA_MISSING",
    "IMAGE_METADATA_NOT_JSON",
    "IMAGE_METADATA_NOT_OBJECT",
    "IMAGE_METADATA_BINDING_INVALID",
    "VIDEO_RAW_NOT_JSON",
    "VIDEO_RAW_SHAPE_INVALID",
    "VIDEO_RAW_DENOMINATOR_INVALID",
    "VIDEO_RAW_NOT_STRING",
    "VIDEO_SUGGESTION_NOT_JSON",
    "PROMPT_SPEC_INVALID",
    "PROMPT_SPEC_NOT_OBJECT",
    "VIDEO_PUBLIC_ORACLE_FAILED",
    "VIDEO_PUBLIC_PATH_BYPASSED",
    "IMAGE_PUBLIC_PATH_BYPASSED",
    "IMAGE_REFERENCE_MISMATCH",
})

# --- frozen S3 quality scoring bounds (contract section "QS") --------------
# The five dimensions are the frozen quality-set rubric.  They are embedded as
# constants on purpose: the execution and scoring code must never read the
# frozen quality set or the prelabels.
FROZEN_DIMENSIONS = (
    "主体/环境",
    "光线/构图/风格",
    "动作/时间或静图不虚构",
    "事实/创作分离",
    "Prompt可用性",
)
DIMENSION_MAX = 2
DIMENSION_MIN = 0
PER_SAMPLE_TOTAL_MIN = 8
IMAGE_USABLE_MIN = 8
VIDEO_USABLE_MIN = 5
CRITICAL_HALLUCINATIONS_MAX = 0
INDEPENDENT_REVIEWER_ROLE = "INDEPENDENT_REVIEWER"

TERMINAL_EXECUTION_STATES = ("PASS", "FAIL", "BLOCKED", "NOT_RUN")
QUALITY_NOT_RUN = "NOT_RUN"

CONTRACT_PATH = "reports/v0-s3/product-gate0/p3b-quality-contract.md"


class QualityContractError(ValueError):
    """Frozen-contract violation in a caller supplied input."""


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_int(value) -> bool:
    """Strict integer test.  ``bool`` is an ``int`` subclass and is rejected."""
    return type(value) is int


def _is_hex(value, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def error_base_code(value) -> str:
    """The stable classification of an error string.

    Production errors may carry a ``:<path>`` or ``:<detail>`` suffix.  The
    classification must never depend on that suffix, so every comparison uses
    this base code.
    """
    return str(value).split(":", 1)[0]


def _is_finite_number(value) -> bool:
    """A finite real number.  ``bool`` is not a number here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _cleanup_detail(prefix, error) -> str:
    """One stable cleanup diagnostic.

    A contract error keeps its own stable base code, so the classification of
    the row does not change because the cleanup path wrapped it.  An ordinary
    exception is reported with the explicit unknown-cleanup prefix.
    """
    if isinstance(error, QualityContractError):
        return str(error)
    return prefix + ":" + type(error).__name__ + ":" + str(error)[:160]


def load_projection_bytes(path) -> bytes:
    """Read the frozen projection file as exact bytes.

    The caller binds the returned bytes to the registered SHA; this helper never
    parses or relaxes the projection.
    """
    return Path(path).read_bytes()


_GRAPH_HELPERS = None
_SPEC_VALIDATOR = None


def _legacy_graph_helpers():
    """Load the existing public manual-graph helper without modifying it."""
    global _GRAPH_HELPERS
    if _GRAPH_HELPERS is None:
        spec = importlib.util.spec_from_file_location("lvw_s3_quality_graph_helpers", LEGACY_GRAPH_HELPERS)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise QualityContractError("LEGACY_GRAPH_HELPERS_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _GRAPH_HELPERS = module
    return _GRAPH_HELPERS


def _prompt_spec_validator():
    global _SPEC_VALIDATOR
    if _SPEC_VALIDATOR is None:
        _SPEC_VALIDATOR = spec_validator()
    return _SPEC_VALIDATOR


def _validate_prompt_spec(suggestion):
    """Validate one machine suggestion against the frozen PromptSpec schema."""
    if not isinstance(suggestion, dict):
        raise QualityContractError("PROMPT_SPEC_NOT_OBJECT")
    try:
        _prompt_spec_validator().validate(suggestion)
    except Exception as error:  # noqa: BLE001 - every schema failure is a contract failure
        raise QualityContractError("PROMPT_SPEC_INVALID:" + type(error).__name__) from error


def receipt_document(receipt):
    """The document that the publication stage writes.

    The pre-publication fields are applied here, so the exact serialized
    length of the terminal receipt can be computed before it is written.
    """
    document = dict(receipt)
    document["receipt_persisted"] = False
    document["receipt_persistence_error"] = None
    document["terminal_status"] = "TERMINAL_RECEIPT_NOT_PERSISTED"
    document["published_as"] = CANONICAL_RECEIPT_NAME
    document["staged_as"] = STAGED_RECEIPT_NAME
    document["staging_entry_retained_on_publication"] = True
    document["durability_limit"] = (
        "A file fsync and a successful no-overwrite publication do not prove the crash "
        "durability of the parent directory entry.")
    return document


def validate_source_evidence(evidence, *, source_sha256, source_bytes,
                              input_reference, run_root):
    """Validate one row's source evidence.

    The same pure validator is used by the execution phase and by the scoring
    entry point, so a row that the execution could not prove is unknown in
    both.  Missing, null or malformed evidence is unknown; it is never
    defaulted to a pass.
    """
    if not isinstance(evidence, dict):
        return False, "SOURCE_EVIDENCE_MISSING"
    identity = evidence.get("identity")
    if (not isinstance(identity, list) or len(identity) != 5
            or any(not _is_int(value) or value < 0 for value in identity)):
        return False, "SOURCE_IDENTITY_INVALID"
    if not _is_int(evidence.get("bytes")) or evidence["bytes"] <= 0:
        return False, "SOURCE_BYTES_INVALID"
    if evidence["bytes"] != source_bytes:
        return False, "SOURCE_BYTES_MISMATCH"
    if not _is_hex(evidence.get("sha256"), 64):
        return False, "SOURCE_HASH_INVALID"
    if evidence["sha256"] != source_sha256:
        return False, "SOURCE_HASH_MISMATCH"
    path = evidence.get("path")
    if not isinstance(path, str) or not path:
        return False, "SOURCE_PATH_INVALID"
    if not isinstance(input_reference, str) or not input_reference:
        return False, "SOURCE_REFERENCE_INVALID"
    if run_root is not None:
        if not isinstance(run_root, str) or not run_root:
            return False, "SOURCE_RUN_ROOT_INVALID"
        if Path(path) != Path(run_root) / "input" / input_reference:
            return False, "SOURCE_PATH_FOREIGN"
    return True, None


def validate_release_evidence(evidence, *, baseline_gpu_mib):
    """Validate the actual bounded release proof.

    The proof is the native evidence itself: the proven flag, a strict integer
    empty model inventory, the actual bounded GPU sample list, the finite
    elapsed time, the bound baseline, the monotone cadence and the last three
    samples back at the baseline.  No sample and no PID evidence is ever
    fabricated here.
    """
    if not isinstance(evidence, dict):
        return False, "RELEASE_EVIDENCE_MISSING"
    if evidence.get("proven") is not True:
        return False, "RELEASE_EVIDENCE_UNPROVEN"
    loaded = evidence.get("loaded_models")
    if not _is_int(loaded) or loaded != 0:
        return False, "RELEASE_EVIDENCE_MODEL_RESIDENT"
    elapsed = evidence.get("elapsed_seconds")
    if not _is_finite_number(elapsed) or elapsed < 0 or elapsed > 30:
        return False, "RELEASE_EVIDENCE_ELAPSED_INVALID"
    baseline = evidence.get("baseline_gpu_mib")
    if not _is_int(baseline) or baseline < 0:
        return False, "RELEASE_EVIDENCE_BASELINE_INVALID"
    if baseline_gpu_mib is not None and baseline != baseline_gpu_mib:
        return False, "RELEASE_EVIDENCE_BASELINE_MISMATCH"
    samples = evidence.get("gpu_samples")
    if not isinstance(samples, list) or not 3 <= len(samples) <= 32:
        return False, "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID"
    previous = None
    for sample in samples:
        if not isinstance(sample, dict):
            return False, "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID"
        moment = sample.get("monotonic_seconds")
        used = sample.get("gpu_used_mib")
        if not _is_finite_number(moment) or moment < 0:
            return False, "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID"
        if not _is_int(used) or used < 0:
            return False, "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID"
        if previous is not None:
            if moment <= previous:
                return False, "RELEASE_EVIDENCE_GPU_CADENCE_INVALID"
            if moment - previous > 1.5:
                return False, "RELEASE_EVIDENCE_GPU_CADENCE_INVALID"
        previous = moment
    if any(sample["gpu_used_mib"] > baseline + 1024 for sample in samples[-3:]):
        return False, "RELEASE_EVIDENCE_GPU_STABILITY_INVALID"
    return True, None


class _OwnedDirectory:
    """One pinned owned directory.

    Every access below is *descriptor relative*: the child is opened or
    created against the pinned handle of its parent, never against an
    absolute path.  The handle and the original path must keep naming the
    same object, and the identity is compared again after every controlled
    callback, before a send and before the cleanup handoff.

    Accepted limitation: this is an in-process inode observation.  It does not
    claim immunity against a hostile kernel or a filesystem that moves inodes
    underneath the process; it claims that a renamed or replaced ancestor is
    detected and never silently adopted.
    """

    def __init__(self, path, fd, identity, parent=None, name=None):
        self.path = Path(path)
        self.fd = fd
        self.identity = tuple(identity)
        self.parent = parent
        self.name = name
        self.closed = False

    @staticmethod
    def identity_of(info):
        return (info.st_dev, info.st_ino)

    def verify(self):
        """The handle and the original path must still name one object."""
        if self.closed or self.fd is None:
            raise QualityContractError("OWNED_DIRECTORY_CLOSED:" + str(self.path))
        try:
            info = os.fstat(self.fd)
        except OSError as error:
            raise QualityContractError("OWNED_DIRECTORY_CLOSED:" + str(self.path)) from error
        if self.identity_of(info) != self.identity:
            raise QualityContractError("OWNED_DIRECTORY_REPLACED:" + str(self.path))
        try:
            # The entry is inspected relative to its pinned parent and without
            # following a symlink, exactly like the accepted protected
            # directory pattern: a renamed ancestor that was replaced by a
            # symlink to the very same object is still detected, because the
            # phase must never write through such a symlink.
            if self.parent is not None and self.name is not None:
                path_info = os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
            else:
                path_info = os.lstat(str(self.path))
        except OSError as error:
            raise QualityContractError("OWNED_PATH_MISSING:" + str(self.path)) from error
        if not stat.S_ISDIR(path_info.st_mode):
            raise QualityContractError("OWNED_PATH_REPLACED:" + str(self.path))
        if self.identity_of(path_info) != self.identity:
            raise QualityContractError("OWNED_PATH_REPLACED:" + str(self.path))
        return info

    def open_child_directory(self, name):
        """Open one child directory relative to this handle."""
        self.verify()
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(name, flags, dir_fd=self.fd)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise QualityContractError("ARTIFACT_REDIRECT_FORBIDDEN:" + name) from error
            if error.errno == errno.ENOENT:
                raise QualityContractError("OWNED_CHILD_DIRECTORY_MISSING:" + name) from error
            raise QualityContractError("OWNED_CHILD_DIRECTORY_UNAVAILABLE:" + name
                                       + ":" + type(error).__name__) from error
        info = os.fstat(fd)
        return _OwnedDirectory(self.path / name, fd, self.identity_of(info),
                               parent=self, name=name)

    def open_child_file(self, name, flags, mode=0o600):
        """Open one child file relative to this handle."""
        self.verify()
        try:
            return os.open(name, flags | getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=self.fd)
        except FileExistsError:
            raise
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise QualityContractError("ARTIFACT_REDIRECT_FORBIDDEN:" + name) from error
            raise QualityContractError("OWNED_CHILD_FILE_UNAVAILABLE:" + name
                                       + ":" + type(error).__name__) from error

    def mkdir_child(self, name):
        """Create one child directory relative to this handle."""
        self.verify()
        try:
            os.mkdir(name, 0o700, dir_fd=self.fd)
        except FileExistsError:
            return False
        except OSError as error:
            raise QualityContractError("OWNED_MKDIR_FAILED:" + name
                                       + ":" + type(error).__name__) from error
        return True

    def close(self):
        if not self.closed and self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.closed = True
        self.fd = None


class QualityPhase:
    """QD: fixed sixteen-row public quality execution.

    The phase owns no process, no budget and no ledger.  The parent owns the
    real profile, the model digest, the media staging, the child authorization,
    the single GPU, the original process ownership and the later archive.
    """

    def __init__(self, driver, run_root, *, run_id, candidate_sha, authorization_sha256,
                 projection, projection_sha256, source_identity, authorize, binding,
                 parent_budget, clock=None, sleep=None):
        self.driver = driver
        self.root = Path(run_root).resolve(strict=True)
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.projection_sha256 = projection_sha256
        self.source_identity = copy.deepcopy(source_identity)
        self.authorize = authorize
        self.binding = copy.deepcopy(binding) if binding else {}
        self.directory = self.root / "temp" / "s3-quality"

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", str(run_id)):
            raise QualityContractError("QUALITY_RUN_ID_INVALID")
        if not _is_hex(candidate_sha, 40):
            raise QualityContractError("QUALITY_CANDIDATE_SHA_INVALID")
        if not _is_hex(authorization_sha256, 64):
            raise QualityContractError("QUALITY_AUTHORIZATION_SHA_INVALID")
        if not _is_hex(projection_sha256, 64):
            raise QualityContractError("QUALITY_PROJECTION_SHA_INVALID")
        if not callable(authorize):
            raise QualityContractError("QUALITY_AUTHORIZE_MISSING")
        if not isinstance(self.source_identity, dict):
            raise QualityContractError("QUALITY_SOURCE_IDENTITY_INVALID")
        if self.source_identity.get("candidate_sha") != candidate_sha:
            raise QualityContractError("QUALITY_SOURCE_IDENTITY_CANDIDATE_MISMATCH")
        workflows = self.source_identity.get("workflows")
        if not isinstance(workflows, dict) or set(workflows) != {IMAGE_WORKFLOW, VIDEO_WORKFLOW}:
            raise QualityContractError("QUALITY_SOURCE_IDENTITY_WORKFLOWS_INVALID")
        for name, entry in workflows.items():
            if (not isinstance(entry, dict) or not _is_hex(entry.get("sha256"), 64)
                    or not _is_int(entry.get("bytes")) or entry["bytes"] <= 0):
                raise QualityContractError("QUALITY_SOURCE_IDENTITY_WORKFLOW_INVALID")
        if not isinstance(projection, (bytes, bytearray)):
            raise QualityContractError("QUALITY_PROJECTION_MUST_BE_BYTES")
        self.projection_bytes = bytes(projection)
        if sha256_bytes(self.projection_bytes) != projection_sha256:
            raise QualityContractError("QUALITY_PROJECTION_SHA_MISMATCH")

        # The child identity has to be bound before a single public action; a
        # missing binding must never skip the release proof.
        for key in ("candidate_sha", "authorization_sha256", "ollama_pid",
                    "ollama_start_ticks", "baseline_gpu_mib"):
            if key not in self.binding:
                raise QualityContractError("QUALITY_BINDING_INCOMPLETE:" + key)
        if self.binding["candidate_sha"] != candidate_sha:
            raise QualityContractError("QUALITY_BINDING_CANDIDATE_MISMATCH")
        if self.binding["authorization_sha256"] != authorization_sha256:
            raise QualityContractError("QUALITY_BINDING_AUTHORIZATION_MISMATCH")
        if not _is_int(self.binding["ollama_pid"]) or self.binding["ollama_pid"] <= 0:
            raise QualityContractError("QUALITY_BINDING_OLLAMA_PID_INVALID")
        if not _is_int(self.binding["ollama_start_ticks"]) or self.binding["ollama_start_ticks"] <= 0:
            raise QualityContractError("QUALITY_BINDING_OLLAMA_BIRTH_INVALID")
        if not _is_int(self.binding["baseline_gpu_mib"]) or self.binding["baseline_gpu_mib"] < 0:
            raise QualityContractError("QUALITY_BINDING_BASELINE_INVALID")

        # Parent capacity admission.  The parent owns the budget; the phase may
        # never pretend that an unknown parent budget is sufficient.  The proof
        # is a typed internal document that binds this exact run, candidate
        # and child authorization, and carries a finite validity interval in
        # the phase monotonic clock.  It is not a ledger API and it never proves
        # that a real reservation exists: the authentic provider and the actual
        # debit stay with the parent coordinator.
        self.parent_budget = copy.deepcopy(parent_budget) if isinstance(parent_budget, dict) else None
        self.parent_budget_capacity = 0
        self._admission_error = None
        try:
            self._validate_parent_proof(self.parent_budget)
        except QualityContractError as error:
            self._admission_error = str(error)

        for name in ("submit", "chat_log_snapshot", "owned_listener_birth",
                     "release_preload", "video_snapshot_residue"):
            if not callable(getattr(driver, name, None)):
                raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:" + name)
        if not callable(getattr(driver, "resource_observer", None)):
            raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:resource_observer")
        if not callable(getattr(driver, "_json_request", None)):
            raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:_json_request")

        self.rows = []
        self.receipt = None
        self._ran = False
        self._polls = 0
        self._provider_calls_observed = 0
        self._provider_calls_observed_known = True
        self._provider_calls_reserved = 0
        self._submissions = 0
        self._submissions_succeeded = 0
        self._artifact_bytes = 0
        self._artifact_files = 0
        self._halted = False
        self._halt_reason = None
        self._seen_prompt_ids = set()
        self._phase_deadline = None
        self._started = None
        self._storage_unproven = False
        self._cleanup_unproven = False
        self._owned_root = None
        self._owned_temp = None
        self._owned_phase = None
        self._root_identity = self._object_identity(self.root.lstat())
        self._last_clock = None

    # -- ownership -------------------------------------------------------
    @staticmethod
    def _object_identity(info):
        """The inode identity of a directory.  Its size and times change with
        every legitimate child creation, so only the object identity pins it."""
        return [info.st_dev, info.st_ino]

    def _open_owned_directories(self, allow_existing=False):
        """Open and pin the owned run root, temp directory and phase directory.

        Every directory is opened relative to its pinned parent handle with
        O_DIRECTORY|O_NOFOLLOW, so a redirected ancestor is refused before any
        foreign entry can be created.
        """
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            root_fd = os.open(str(self.root), flags)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise QualityContractError("RUN_ROOT_REDIRECT:" + type(error).__name__) from error
            raise QualityContractError("RUN_ROOT_UNAVAILABLE:" + type(error).__name__) from error
        root_identity = _OwnedDirectory.identity_of(os.fstat(root_fd))
        if list(root_identity) != list(self._root_identity):
            os.close(root_fd)
            raise QualityContractError("RUN_ROOT_REPLACED")
        self._owned_root = _OwnedDirectory(self.root, root_fd, root_identity)
        try:
            temp = self._owned_root.open_child_directory("temp")
        except QualityContractError as error:
            # The preparation directory is owned by the parent.  A missing one
            # may be created under the pinned root handle; a redirected one is
            # refused before anything is created.
            if "OWNED_CHILD_DIRECTORY_MISSING" not in str(error):
                raise
            self._owned_root.mkdir_child("temp")
            temp = self._owned_root.open_child_directory("temp")
        self._owned_temp = temp
        created = self._owned_temp.mkdir_child("s3-quality")
        if not created and not allow_existing:
            # A preexisting phase directory is a replay of an older root.  It
            # is refused and nothing at all is written into it.
            raise QualityContractError("PHASE_DIRECTORY_EXISTS")
        self._owned_phase = self._owned_temp.open_child_directory("s3-quality")

    def _close_owned_directories(self):
        """Close every owned handle, also on a failure or a refused replay."""
        for handle in (self._owned_phase, self._owned_temp, self._owned_root):
            if handle is not None:
                handle.close()
        self._owned_phase = None
        self._owned_temp = None
        self._owned_root = None

    def _verify_owned(self):
        """Compare the original path and handle identities of every owner.

        This runs after every controlled callback, before a send and before
        the cleanup handoff, so a renamed or replaced ancestor is detected
        instead of being adopted.
        """
        if self._owned_root is None:
            raise QualityContractError("OWNED_DIRECTORY_CLOSED:" + str(self.root))
        self._owned_root.verify()
        if self._owned_temp is not None:
            self._owned_temp.verify()
        if self._owned_phase is not None:
            self._owned_phase.verify()

    def _validate_parent_proof(self, proof):
        """Validate the typed internal parent capacity proof."""
        if not isinstance(proof, dict):
            raise QualityContractError("PARENT_BUDGET_PROOF_MISSING")
        if proof.get("kind") != PARENT_PROOF_KIND:
            raise QualityContractError("PARENT_BUDGET_PROOF_KIND_INVALID")
        if proof.get("known") is not True:
            raise QualityContractError("PARENT_BUDGET_PROOF_UNKNOWN")
        if proof.get("run_id") != self.run_id:
            raise QualityContractError("PARENT_BUDGET_PROOF_RUN_MISMATCH")
        if proof.get("candidate_sha") != self.candidate_sha:
            raise QualityContractError("PARENT_BUDGET_PROOF_CANDIDATE_MISMATCH")
        if proof.get("authorization_sha256") != self.authorization_sha256:
            raise QualityContractError("PARENT_BUDGET_PROOF_AUTHORIZATION_MISMATCH")
        issued = proof.get("issued_monotonic")
        expires = proof.get("expires_monotonic")
        if not _is_finite_number(issued) or not _is_finite_number(expires):
            raise QualityContractError("PARENT_BUDGET_PROOF_INTERVAL_INVALID")
        if expires <= issued:
            raise QualityContractError("PARENT_BUDGET_PROOF_INTERVAL_INVALID")
        capacity = proof.get("action_capacity")
        if not _is_int(capacity) or capacity < 0:
            raise QualityContractError("PARENT_BUDGET_CAPACITY_INVALID")
        self.parent_budget_capacity = capacity

    def _send_admission_guard(self, row, expected_calls):
        """The final local send-admission guard.

        It runs after every controlled preparation, authorization and source
        callback and directly before the local reservation, the attempt charge
        and the submit itself, so nothing unchecked happens in between.  It
        revalidates the original ownership, the finite non boolean
        non decreasing clock and the phase deadline, and the exact typed
        parent proof with its validity interval and the current sufficient
        remaining capacity.

        This is a cooperative local guard.  It does not preempt a synchronous
        callback that never returns; that remains the mandatory parent
        watchdog obligation and stays UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER.
        """
        self._verify_owned()
        now = self._now()
        if not _is_finite_number(now):
            raise QualityContractError("CLOCK_NOT_FINITE")
        if self._started is None or now - self._started > PHASE_TIMEOUT_SECONDS:
            raise QualityContractError("PHASE_DEADLINE_EXCEEDED")
        admission_error = self._parent_proof_is_fresh()
        if admission_error:
            raise QualityContractError(admission_error)
        admitted = min(self.parent_budget_capacity, MAX_TOTAL_PROVIDER_CALLS)
        if self._provider_calls_reserved + expected_calls > admitted:
            raise QualityContractError("PARENT_BUDGET_CAPACITY_INSUFFICIENT")

    def _parent_proof_is_fresh(self):
        """The proof must still be inside its validity interval."""
        try:
            self._validate_parent_proof(self.parent_budget)
        except QualityContractError as error:
            return str(error)
        now = self._now()
        issued = self.parent_budget["issued_monotonic"]
        expires = self.parent_budget["expires_monotonic"]
        if now < issued:
            return "PARENT_BUDGET_PROOF_NOT_YET_VALID"
        if now >= expires:
            return "PARENT_BUDGET_PROOF_STALE"
        if self.parent_budget_capacity < MAX_TOTAL_PROVIDER_CALLS:
            return "PARENT_BUDGET_CAPACITY_INSUFFICIENT"
        return None

    # -- bounded controlled steps ----------------------------------------
    def _now(self):
        """The phase monotonic clock.

        A finite but decreasing reading is refused: a clock that moves
        backwards cannot prove a deadline.  The observation is cooperative; it
        does not preempt a call that never returns.
        """
        value = self.clock()
        if not _is_finite_number(value):
            raise QualityContractError("CLOCK_NOT_FINITE")
        value = float(value)
        if self._last_clock is not None and value < self._last_clock:
            raise QualityContractError("CLOCK_NOT_MONOTONIC")
        self._last_clock = value
        return value

    def _authorize(self, action, subject):
        """Run one controlled authorization callback under a bounded elapsed.

        The owned path and handle identities are compared again after the
        callback, so a redirected or replaced ancestor is detected instead of
        being adopted.  The elapsed check is a cooperative post-return check:
        a callback that never returns cannot be preempted here.
        """
        start = self._now()
        self.authorize(action, subject)
        elapsed = self._now() - start
        if elapsed > CALLBACK_MAX_SECONDS:
            raise QualityContractError("AUTHORIZE_CALLBACK_ELAPSED_EXCEEDED:" + action)
        self._verify_owned()

    def _observe(self, label, function, *args, **kwargs):
        """Run one observation under a bounded elapsed."""
        return self._bounded(label, OBSERVATION_MAX_SECONDS,
                             "OBSERVATION_ELAPSED_EXCEEDED", function, *args, **kwargs)

    def _bounded(self, label, ceiling, code, function, *args, **kwargs):
        """Run one controlled step under an explicit elapsed ceiling."""
        start = self._now()
        try:
            return function(*args, **kwargs)
        finally:
            elapsed = self._now() - start
            if elapsed > ceiling:
                raise QualityContractError(code + ":" + label)

    # -- projection ------------------------------------------------------
    def _parse_projection(self):
        """Validate the frozen projection structure.  Raises on any deviation."""
        try:
            document = json.loads(self.projection_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise QualityContractError("PROJECTION_NOT_JSON") from error
        if not isinstance(document, dict):
            raise QualityContractError("PROJECTION_NOT_OBJECT")
        if set(document) - PROJECTION_TOP_LEVEL_KEYS:
            raise QualityContractError("PROJECTION_UNEXPECTED_FIELD")
        if document.get("schema_version") != PROJECTION_SCHEMA_VERSION:
            raise QualityContractError("PROJECTION_SCHEMA_VERSION_INVALID")
        if not isinstance(document.get("spec_version"), str) or not document["spec_version"].strip():
            raise QualityContractError("PROJECTION_SPEC_VERSION_INVALID")
        denominator = document.get("fixed_denominator")
        if (not isinstance(denominator, dict)
                or denominator.get("images") != FIXED_IMAGES
                or denominator.get("videos") != FIXED_VIDEOS
                or denominator.get("total") != FIXED_TOTAL):
            raise QualityContractError("PROJECTION_DENOMINATOR_INVALID")
        samples = document.get("samples")
        if not isinstance(samples, list) or len(samples) != FIXED_TOTAL:
            raise QualityContractError("PROJECTION_ROW_COUNT_INVALID")

        rows = []
        seen_ids = set()
        seen_hashes = set()
        seen_names = set()
        for index, sample in enumerate(samples):
            if not isinstance(sample, dict):
                raise QualityContractError("PROJECTION_ROW_NOT_OBJECT")
            if set(sample) != PROJECTION_ROW_KEYS:
                raise QualityContractError("PROJECTION_ROW_UNEXPECTED_FIELD")
            asset_id = sample.get("asset_id")
            media_kind = sample.get("media_kind")
            source_sha = sample.get("source_sha256")
            source_bytes = sample.get("source_bytes")
            reference = sample.get("input_reference")
            if not isinstance(asset_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", asset_id):
                raise QualityContractError("PROJECTION_ASSET_ID_INVALID")
            if asset_id in seen_ids:
                raise QualityContractError("PROJECTION_DUPLICATE_ASSET_ID")
            seen_ids.add(asset_id)
            if media_kind not in ("image", "video"):
                raise QualityContractError("PROJECTION_MEDIA_KIND_INVALID")
            if not _is_hex(source_sha, 64):
                raise QualityContractError("PROJECTION_SOURCE_SHA_INVALID")
            if source_sha in seen_hashes:
                raise QualityContractError("PROJECTION_DUPLICATE_SOURCE_HASH")
            seen_hashes.add(source_sha)
            if not _is_int(source_bytes) or source_bytes <= 0:
                raise QualityContractError("PROJECTION_SOURCE_BYTES_INVALID")
            if not isinstance(reference, str) or not reference:
                raise QualityContractError("PROJECTION_REFERENCE_INVALID")
            if reference in seen_names:
                raise QualityContractError("PROJECTION_DUPLICATE_REFERENCE")
            seen_names.add(reference)
            pure = PurePosixPath(reference)
            if (pure.is_absolute() or len(pure.parts) != 1 or pure.parts[0] in ("", ".", "..")
                    or "\\" in reference or "/" in reference):
                raise QualityContractError("PROJECTION_REFERENCE_NOT_SIMPLE_NAME")
            extension = pure.suffix.lower()
            allowed = IMAGE_EXTENSIONS if media_kind == "image" else VIDEO_EXTENSIONS
            if extension not in allowed:
                raise QualityContractError("PROJECTION_REFERENCE_EXTENSION_INVALID")
            limit = IMAGE_SOURCE_MAX_BYTES if media_kind == "image" else VIDEO_SOURCE_MAX_BYTES
            if source_bytes > limit:
                raise QualityContractError("PROJECTION_SOURCE_BYTES_OVER_LIMIT")
            rows.append({
                "ordinal": index + 1,
                "asset_id": asset_id,
                "media_kind": media_kind,
                "source_sha256": source_sha,
                "source_bytes": source_bytes,
                "input_reference": reference,
            })
        kinds = [row["media_kind"] for row in rows]
        if kinds.count("image") != FIXED_IMAGES or kinds.count("video") != FIXED_VIDEOS:
            raise QualityContractError("PROJECTION_MEDIA_KIND_COUNTS_INVALID")
        return rows

    # -- sources ---------------------------------------------------------
    def _source_path(self, reference):
        """Resolve one prepared source file inside the owned run root."""
        candidate = self.root / "input" / reference
        for ancestor in (candidate, *candidate.parents):
            if ancestor == self.root:
                break
            if ancestor.is_symlink():
                raise QualityContractError("SOURCE_REDIRECT_FORBIDDEN")
            info = ancestor.lstat()
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise QualityContractError("SOURCE_REDIRECT_FORBIDDEN")
        if candidate.is_symlink():
            raise QualityContractError("SOURCE_REDIRECT_FORBIDDEN")
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise QualityContractError("SOURCE_UNAVAILABLE") from error
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise QualityContractError("SOURCE_OUTSIDE_RUN_ROOT") from error
        if resolved != candidate or not candidate.is_file():
            raise QualityContractError("SOURCE_NOT_PLAIN_FILE")
        return candidate

    @staticmethod
    def _identity(info):
        return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]

    def _validate_source(self, row, previous=None):
        """Re-derive one source file with a bounded read and a stable identity.

        The read never runs past the frozen byte count, so a file that grows
        while it is read is detected instead of being silently followed to EOF.
        The identity tuple proves the very same object is still in place, and
        the descriptor identity is compared with the path identity *after* the
        read, so a replacement during the read cannot pass unnoticed.

        This is a bounded, in-process observation of one path.  It is not a
        universal guarantee against a hostile racing filesystem, and it does
        not claim to be one.
        """
        self._verify_owned()
        path = self._source_path(row["input_reference"])
        descriptor = None
        try:
            descriptor = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            before = os.fstat(descriptor)
            if not os.path.samestat(before, os.stat(str(path))):
                raise QualityContractError("SOURCE_REPLACED")
            if before.st_size != row["source_bytes"]:
                raise QualityContractError("SOURCE_SIZE_MISMATCH")
            digest = hashlib.sha256()
            remaining = row["source_bytes"]
            while remaining > 0:
                chunk = os.read(descriptor, min(SOURCE_READ_CHUNK_BYTES, remaining))
                if not chunk:
                    raise QualityContractError("SOURCE_TRUNCATED")
                digest.update(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise QualityContractError("SOURCE_GROWTH")
            after = os.fstat(descriptor)
            # The descriptor and the path must still name the same object
            # after the bounded read.
            path_after = os.stat(str(path))
            if not os.path.samestat(after, path_after):
                raise QualityContractError("SOURCE_REPLACED")
        except OSError as error:
            raise QualityContractError("SOURCE_UNAVAILABLE:" + type(error).__name__) from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if self._identity(before) != self._identity(after):
            raise QualityContractError("SOURCE_REPLACED")
        if previous is not None and list(previous) != self._identity(after):
            raise QualityContractError("SOURCE_REPLACED")
        if digest.hexdigest() != row["source_sha256"]:
            raise QualityContractError("SOURCE_HASH_MISMATCH")
        return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest(),
                "identity": self._identity(after)}

    # -- workflows -------------------------------------------------------
    def _load_workflows(self):
        workflows = {}
        for name in (IMAGE_WORKFLOW, VIDEO_WORKFLOW):
            expected = self.source_identity["workflows"][name]
            raw = (WORKFLOW_DIR / name).read_bytes()
            if len(raw) != expected["bytes"] or sha256_bytes(raw) != expected["sha256"]:
                raise QualityContractError("WORKFLOW_SOURCE_IDENTITY_MISMATCH:" + name)
            document = json.loads(raw.decode("utf-8"))
            if not isinstance(document, dict) or not document:
                raise QualityContractError("WORKFLOW_DOCUMENT_INVALID:" + name)
            workflows[name] = {"document": document, "sha256": expected["sha256"], "bytes": expected["bytes"]}
        image = workflows[IMAGE_WORKFLOW]["document"]
        if (image.get("1", {}).get("class_type") != "LVWControlledImageInput"
                or image.get("2", {}).get("class_type") != "LVWImagePromptBridge"
                or image.get("2", {}).get("inputs", {}).get("image") != ["1", 0]):
            raise QualityContractError("IMAGE_WORKFLOW_NODES_CHANGED")
        video = workflows[VIDEO_WORKFLOW]["document"]
        if video.get("1", {}).get("class_type") != "LVWVideoPromptOwner":
            raise QualityContractError("VIDEO_WORKFLOW_NODES_CHANGED")
        return workflows

    def _build_graph(self, row, workflows):
        """Build the public graph for one row without touching product owners."""
        if row["media_kind"] == "image":
            graph = copy.deepcopy(workflows[IMAGE_WORKFLOW]["document"])
            graph["1"]["inputs"]["image_reference"] = row["input_reference"]
            bridge = graph["2"]["inputs"]
            helper = _legacy_graph_helpers()
            # The controlled image metadata is observed exactly the way the
            # existing cumulative phase observes it: a public manual node that
            # reads node 1 output 1.  No product graph or owner is modified.
            graph["3"] = helper.manual_public_graph({"natural_zh": ["1", 1]}, "preview_json", "metadata")["1"]
            expected_node = "2"
        else:
            graph = copy.deepcopy(workflows[VIDEO_WORKFLOW]["document"])
            graph["1"]["inputs"]["video_reference"] = row["input_reference"]
            bridge = graph["1"]["inputs"]
            expected_node = "1"
        if (bridge.get("model") != MODEL_TAG or bridge.get("mode") != PROMPT_MODE
                or bridge.get("user_instruction") != PROMPT_USER_INSTRUCTION
                or bridge.get("timeout_seconds") != PROMPT_TIMEOUT_SECONDS):
            raise QualityContractError("WORKFLOW_MODEL_PROFILE_CHANGED")
        return graph, expected_node

    # -- artifacts -------------------------------------------------------
    def _artifact(self, relative, raw: bytes):
        """Persist one artifact under the owned phase directory.

        The write is descriptor relative: every directory level is opened
        against the pinned handle of its parent with O_DIRECTORY|O_NOFOLLOW and
        the file itself is created exclusively against the pinned handle of its
        own directory.  Nothing is ever written outside the originally owned
        directory, and an existing file is never overwritten.
        """
        if not isinstance(relative, str) or not relative:
            raise QualityContractError("ARTIFACT_PATH_INVALID")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise QualityContractError("ARTIFACT_PATH_INVALID")
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise QualityContractError("ARTIFACT_TOO_LARGE:" + relative)
        if self._artifact_files + 1 > MAX_ARTIFACT_FILES:
            raise QualityContractError("ARTIFACT_FILE_BUDGET_EXCEEDED")
        if self._artifact_bytes + len(raw) > MAX_TOTAL_ARTIFACT_BYTES:
            raise QualityContractError("ARTIFACT_TOTAL_BUDGET_EXCEEDED")
        if self._owned_phase is None:
            raise QualityContractError("OWNED_DIRECTORY_CLOSED:" + str(self.directory))
        self._verify_owned()
        handles = []
        try:
            current = self._owned_phase
            for part in pure.parts[:-1]:
                current.mkdir_child(part)
                current = current.open_child_directory(part)
                handles.append(current)
            try:
                descriptor = current.open_child_file(
                    pure.parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError as error:
                raise QualityContractError("ARTIFACT_REPLAY_FORBIDDEN:" + relative) from error
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as error:
                raise QualityContractError("ARTIFACT_WRITE_FAILED:" + relative) from error
        finally:
            for handle in reversed(handles):
                handle.close()
        self._artifact_files += 1
        self._artifact_bytes += len(raw)
        return {"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)}

    # -- provider --------------------------------------------------------
    def _provider_snapshot(self, label, relative=None):
        self._authorize("quality_provider_" + label, self.run_id)
        self.driver.resource_observer()
        snapshot = self._observe("chat_log_snapshot", self.driver.chat_log_snapshot)
        if not isinstance(snapshot, dict):
            raise QualityContractError("PROVIDER_SNAPSHOT_INVALID")
        try:
            observed = provider_chat_count(snapshot)
        except (ValueError, KeyError, TypeError) as error:
            raise QualityContractError("PROVIDER_SNAPSHOT_INVALID:" + type(error).__name__) from error
        if not isinstance(snapshot.get("raw_log"), str):
            raise QualityContractError("PROVIDER_SNAPSHOT_INVALID")
        evidence = {
            "label": label,
            "chat_calls": observed,
            "source_log_bytes": snapshot["source_log_bytes"],
            "source_log_sha256": snapshot["source_log_sha256"],
            "raw_log": snapshot["raw_log"],
        }
        if relative is not None:
            artifact = self._artifact(relative, snapshot["raw_log"].encode("utf-8"))
            evidence["artifact"] = artifact["path"]
            evidence["artifact_sha256"] = artifact["sha256"]
            evidence["artifact_bytes"] = artifact["bytes"]
        return evidence

    def _listener_identity(self):
        identity = {}
        for port in (COMFY_PORT, OLLAMA_PORT):
            proof = self._observe("owned_listener_birth", self.driver.owned_listener_birth, port)
            if (not isinstance(proof, dict) or not _is_int(proof.get("pid")) or proof["pid"] <= 0
                    or not _is_int(proof.get("start_ticks")) or proof["start_ticks"] <= 0):
                raise QualityContractError("LISTENER_IDENTITY_INVALID")
            identity[str(port)] = {"pid": proof["pid"], "start_ticks": proof["start_ticks"]}
        return identity

    # -- release ---------------------------------------------------------
    def _release_worker(self):
        accessor = getattr(self.driver, "resource_worker", None)
        if callable(accessor):
            worker = accessor()
            if worker is not None:
                return worker
        worker = getattr(self.driver, "_resource_worker", None)
        if worker is None:
            raise QualityContractError("RELEASE_WORKER_MISSING")
        return worker

    def _release_evidence(self, row):
        """Require proven release evidence; never fabricate a release marker.

        The public ``release_preload`` path is reused unchanged.  The accepted
        release semantics are the ones the cumulative phase already enforces:
        a proven release, an empty model inventory, monotone gap-bounded GPU
        samples and the last three samples back at the baseline.
        """
        self._authorize("quality_release", row["asset_id"])
        worker = self._release_worker()
        binding = dict(self.binding)
        evidence = self._bounded("release_preload", RELEASE_MAX_SECONDS,
                                 "RELEASE_ELAPSED_EXCEEDED",
                                 self.driver.release_preload, binding, worker)
        baseline = self.binding["baseline_gpu_mib"]
        # The same pure validator that the scoring entry point uses.
        valid, reason = validate_release_evidence(evidence, baseline_gpu_mib=baseline)
        if not valid:
            raise QualityContractError(reason)
        # The actual native proof is retained as it is; no sample, count or
        # PID evidence is ever fabricated here.
        proof = {
            "proven": True,
            "loaded_models": evidence["loaded_models"],
            "elapsed_seconds": evidence["elapsed_seconds"],
            "baseline_gpu_mib": evidence["baseline_gpu_mib"],
            "gpu_samples": copy.deepcopy(evidence["gpu_samples"]),
        }
        for key in ("run_token", "model", "owner_pid", "owner_start_ticks", "unload_acknowledged"):
            if key in evidence:
                proof[key] = evidence[key]
        return proof

    def _video_residue(self, row):
        self._authorize("quality_residue", row["asset_id"])
        residue = self._observe("video_snapshot_residue", self.driver.video_snapshot_residue)
        if not isinstance(residue, list):
            raise QualityContractError("VIDEO_SNAPSHOT_RESIDUE_INVALID")
        if residue:
            raise QualityContractError("VIDEO_SNAPSHOT_RESIDUE")
        return []

    # -- execution -------------------------------------------------------
    def _execute_row(self, row, workflows):
        """Execute one row.  Returns a result dict with ``halt`` semantics."""
        kind = row["media_kind"]
        expected_calls = IMAGE_PROVIDER_CALLS if kind == "image" else VIDEO_PROVIDER_CALLS
        result = {
            "asset_id": row["asset_id"],
            "media_kind": kind,
            "ordinal": row["ordinal"],
            "source_sha256": row["source_sha256"],
            "source_bytes": row["source_bytes"],
            "input_reference": row["input_reference"],
            "execution_status": "FAIL",
            "quality_status": QUALITY_NOT_RUN,
            "error_code": None,
            "stage": None,
            "prompt_id": None,
            "provider_calls": 0,
            "provider_calls_observed_known": True,
            "provider_calls_reserved": 0,
            "graph_sha256": None,
            "graph_artifact": None,
            "raw_sha256": None,
            "raw_bytes": None,
            "raw_artifact": None,
            "raw_preserved": False,
            "suggestion_sha256": None,
            "suggestion_artifact": None,
            "metadata_sha256": None,
            "metadata_artifact": None,
            "frame_raw_sha256": [],
            "history_sha256": None,
            "history_artifact": None,
            "error_raw_sha256": None,
            "error_raw_artifact": None,
            "error_frame_raw_sha256": [],
            "provider_before": None,
            "provider_after": None,
            "source_evidence": None,
            "listener_before": None,
            "listener_after": None,
            "release_evidence": None,
            "video_snapshot_residue": None,
            "storage_unproven": False,
            "cleanup_unproven": False,
            "cleanup_diagnostics": [],
            "automatic_retries": 0,
            "halt": False,
        }
        stage = "prepare"
        try:
            self._authorize("quality_row_begin", row["asset_id"])
            before = self._provider_snapshot(
                "before", "rows/" + row["asset_id"] + "/provider-before.log")
            result["provider_before"] = _log_evidence(before)
            result["listener_before"] = self._listener_identity()
            # The critical source is re-verified immediately before the send:
            # same object, same hash, bounded read.
            result["source_evidence"] = self._validate_source(
                row, previous=(row.get("source_evidence") or {}).get("identity"))
            graph, expected_node = self._build_graph(row, workflows)
            result["graph_sha256"] = sha256_bytes(canonical_json(graph).encode("utf-8"))
            stage = "submit"
            self._authorize("quality_public_submit", row["asset_id"])
            # After every controlled callback the source and the owned root
            # are re-verified immediately before the send.  A changed source
            # produces zero sends and zero charges for this row.
            result["source_evidence"] = self._validate_source(
                row, previous=result["source_evidence"]["identity"])
            # The final local send-admission guard: the original ownership,
            # the phase deadline and the exact typed parent proof with its
            # current remaining capacity.  Nothing unchecked happens between
            # this guard and the submit.
            self._send_admission_guard(row, expected_calls)
            driver_submissions = int(getattr(self.driver, "submissions", 0))
            driver_limit = int(getattr(self.driver, "max_public_submissions", MAX_PUBLIC_SUBMISSIONS))
            if driver_submissions >= driver_limit:
                raise QualityContractError("PUBLIC_SUBMISSION_BUDGET_EXCEEDED")
            # The provider budget is reserved before the attempt, so a failed or
            # unknown submission can never be under-counted and re-sent.
            if self._provider_calls_reserved + expected_calls > MAX_TOTAL_PROVIDER_CALLS:
                raise QualityContractError("PROVIDER_CALL_BUDGET_EXCEEDED")
            self._provider_calls_reserved += expected_calls
            result["provider_calls_reserved"] = expected_calls
            # The public submission attempt is charged before the call, so a
            # failed or unknown outcome stays charged.  It is never refunded
            # and never retried.
            self._submissions += 1
            result["public_submission_attempted"] = True
            prompt_id = self.driver.submit(graph)
            if (not isinstance(prompt_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", prompt_id)):
                raise QualityContractError("PROMPT_ID_INVALID")
            self._submissions_succeeded += 1
            if prompt_id in self._seen_prompt_ids:
                raise QualityContractError("PROMPT_ID_REUSED")
            self._seen_prompt_ids.add(prompt_id)
            result["prompt_id"] = prompt_id
            stage = "history"
            history = self._await_history(row, prompt_id)
            record = history[prompt_id]
            stage = "observe"
            # The provider-after evidence is taken before the persistence, so
            # it exists even when the persistence or the parsing fails.
            after = None
            after_failure = None
            try:
                after = self._provider_snapshot(
                    "after", "rows/" + row["asset_id"] + "/provider-after.log")
                result["provider_after"] = _log_evidence(after)
                # The observed provider count is derived from the evidence
                # itself, so it is known even when a later step fails.
                calls = after["chat_calls"] - before["chat_calls"]
                result["provider_calls"] = calls
                if calls >= 0:
                    self._provider_calls_observed += calls
            except Exception as error:  # noqa: BLE001 - the evidence gap is recorded
                after_failure = ("PROVIDER_AFTER_SNAPSHOT_FAILED:"
                                 + type(error).__name__ + ":" + str(error)[:160])
                result["provider_after"] = None
                result["provider_calls_observed_known"] = False
                self._provider_calls_observed_known = False
            stage = "persist"
            # ---- the actual raw bytes are persisted BEFORE any validation
            persistence_failure = None
            persistence_started = self._now()
            try:
                self._persist_row(row, graph, record, expected_node, result)
            except QualityContractError as error:
                persistence_failure = error
            except Exception as error:  # noqa: BLE001
                persistence_failure = QualityContractError(
                    "ARTIFACT_WRITE_FAILED:" + type(error).__name__)
            if self._now() - persistence_started > PERSISTENCE_MAX_SECONDS:
                persistence_failure = QualityContractError("PERSISTENCE_ELAPSED_EXCEEDED")
            if after_failure is not None:
                raise QualityContractError(after_failure)
            if persistence_failure is not None:
                raise persistence_failure
            stage = "observe"
            result["listener_after"] = self._listener_identity()
            if result["listener_after"] != result["listener_before"]:
                raise QualityContractError("LISTENER_IDENTITY_DRIFT")
            if not after["artifact_sha256"] or after["source_log_sha256"] != after["artifact_sha256"]:
                raise QualityContractError("PROVIDER_SNAPSHOT_INVALID")
            # The before log must remain the exact original prefix of the
            # after log: a cleared or rewritten provider log is never accepted.
            if not after["raw_log"].startswith(before["raw_log"]):
                raise QualityContractError("PROVIDER_LOG_REWRITTEN")
            if result["provider_calls"] != expected_calls:
                raise QualityContractError("PROVIDER_CALL_COUNT_MISMATCH")
            stage = "validate"
            self._validate_row(row, history, record, expected_node, result, graph,
                               before["chat_calls"], after["chat_calls"])
            result["execution_status"] = "PASS"
        except QualityContractError as error:
            result["error_code"] = str(error)
            result["stage"] = stage
            base = error_base_code(error)
            if base in NOT_ATTEMPTED_ERROR_CODES:
                result["execution_status"] = "BLOCKED"
            if base in STORAGE_ERROR_CODES:
                self._storage_unproven = True
                result["storage_unproven"] = True
            if base in CLEANUP_ERROR_CODES:
                self._cleanup_unproven = True
                result["cleanup_unproven"] = True
            if stage in UNCERTAIN_STAGES or base in HALT_ERROR_CODES:
                result["halt"] = True
        except Exception as error:  # noqa: BLE001 - the failure must be recorded, never hidden
            result["error_code"] = type(error).__name__ + ":" + str(error)[:200]
            result["stage"] = stage
            if stage in UNCERTAIN_STAGES:
                result["halt"] = True
        finally:
            # Cleanup never bypasses the release proof and never escapes the
            # row: an ordinary exception is recorded as a cleanup diagnostic
            # and stops every later public submission.
            try:
                # The cleanup handoff compares the owned identities again.
                # A failed comparison is recorded, but it never skips the
                # release proof itself.
                self._verify_owned()
            except Exception as error:  # noqa: BLE001 - the ownership gap is recorded
                result["cleanup_diagnostics"].append(
                    "OWNED_IDENTITY_CHECK_FAILED:" + type(error).__name__ + ":" + str(error)[:160])
                result["halt"] = True
            try:
                result["video_snapshot_residue"] = self._video_residue(row)
            except Exception as error:  # noqa: BLE001 - the cleanup gap is recorded
                detail = _cleanup_detail("VIDEO_SNAPSHOT_RESIDUE_UNKNOWN", error)
                result["video_snapshot_residue"] = {"proven": False, "error": detail}
                result["cleanup_diagnostics"].append(detail)
                result["halt"] = True
                self._cleanup_unproven = True
                result["cleanup_unproven"] = True
                if result["execution_status"] == "PASS":
                    result["execution_status"] = "FAIL"
                result["error_code"] = result["error_code"] or detail
            try:
                result["release_evidence"] = self._release_evidence(row)
            except Exception as error:  # noqa: BLE001 - the cleanup gap is recorded
                detail = _cleanup_detail("RELEASE_EVIDENCE_UNKNOWN", error)
                result["release_evidence"] = {"proven": False, "error": detail}
                result["cleanup_diagnostics"].append(detail)
                result["halt"] = True
                self._cleanup_unproven = True
                result["cleanup_unproven"] = True
                if result["execution_status"] == "PASS":
                    result["execution_status"] = "FAIL"
                result["error_code"] = result["error_code"] or detail
        if error_base_code(result["error_code"] or "") in (
                "PUBLIC_SUBMISSION_BUDGET_EXCEEDED", "PROVIDER_CALL_BUDGET_EXCEEDED"):
            result["halt"] = True
        return result

    def _await_history(self, row, prompt_id):
        """Poll the public history endpoint under the frozen sample bounds.

        A late but successful history is still a deadline failure: the sample
        window is checked again after the response arrived.
        """
        deadline = min(self._now() + SAMPLE_HISTORY_TIMEOUT_SECONDS, self._phase_deadline)
        while True:
            if self._polls >= MAX_HISTORY_POLLS:
                raise QualityContractError("HISTORY_POLL_BUDGET_EXCEEDED")
            self._authorize("quality_public_history", row["asset_id"])
            status, history = self.driver._json_request(
                COMFY_URL + "/history/" + prompt_id, timeout=2, observer=self.driver.resource_observer)
            self._polls += 1
            if status == 200 and isinstance(history, dict) and prompt_id in history:
                if self._now() > deadline:
                    raise QualityContractError("HISTORY_TIMEOUT")
                return history
            if self._now() > deadline:
                raise QualityContractError("HISTORY_TIMEOUT")
            self.sleep(HISTORY_POLL_INTERVAL_SECONDS)

    def _persist_row(self, row, graph, record, expected_node, result):
        """Save raw, suggestion and metadata as separate UTF-8 artifacts.

        The actual raw string is written *before* any structural judgement, so
        a rejected row still keeps the exact bytes the public owner produced.
        A failed public execution carries its own raw evidence in the
        serialized ``BridgeError``; those exact envelopes and frame strings
        are kept as evidence too, independently of any parse success.
        """
        directory = "rows/" + row["asset_id"]
        graph_artifact = self._artifact(directory + "/graph.json", canonical_json(graph).encode("utf-8"))
        result["graph_artifact"] = graph_artifact["path"]
        history_raw = canonical_json(record).encode("utf-8")
        result["history_sha256"] = sha256_bytes(history_raw)
        history_artifact = self._artifact(directory + "/history.json", history_raw)
        result["history_artifact"] = history_artifact["path"]
        # The exact error raw evidence is kept before anything else, so a
        # failed execution never loses the bytes the owner actually received.
        self._persist_error_raw(directory, record, result)
        outputs = record.get("outputs")
        if not isinstance(outputs, dict) or not isinstance(outputs.get(expected_node), dict):
            raise QualityContractError("PUBLIC_NODE_OUTPUT_MISSING")
        text = outputs[expected_node].get("text")
        if not isinstance(text, list) or not all(isinstance(item, str) for item in text):
            raise QualityContractError("PUBLIC_NODE_OUTPUT_MISSING")
        if row["media_kind"] == "image":
            if len(text) < 2:
                raise QualityContractError("PUBLIC_IMAGE_OUTPUT_INCOMPLETE")
            raw_text, suggestion_text = text[0], text[1]
        else:
            if len(text) < 3:
                raise QualityContractError("PUBLIC_VIDEO_OUTPUT_INCOMPLETE")
            raw_text, suggestion_text = text[0], text[1]
        # ---- the raw bytes are persisted first, unconditionally
        raw_artifact = self._artifact(directory + "/raw.txt", raw_text.encode("utf-8"))
        result["raw_artifact"] = raw_artifact["path"]
        result["raw_sha256"] = raw_artifact["sha256"]
        result["raw_bytes"] = raw_artifact["bytes"]
        result["raw_preserved"] = True
        suggestion_artifact = self._artifact(directory + "/suggestion.txt", suggestion_text.encode("utf-8"))
        result["suggestion_artifact"] = suggestion_artifact["path"]
        result["suggestion_sha256"] = suggestion_artifact["sha256"]
        # ---- the controlled metadata is resolved after the raw was kept
        if row["media_kind"] == "image":
            metadata_text = self._image_metadata(record)
        else:
            metadata_text = text[2]
        metadata_artifact = self._artifact(directory + "/metadata.txt", metadata_text.encode("utf-8"))
        result["metadata_artifact"] = metadata_artifact["path"]
        result["metadata_sha256"] = metadata_artifact["sha256"]
        if row["media_kind"] == "video":
            frames = self._video_frame_raws(raw_text)
            for index, frame_raw in enumerate(frames):
                self._artifact(directory + "/frames/frame-%d.txt" % index, frame_raw.encode("utf-8"))
            result["frame_raw_sha256"] = [sha256_bytes(item.encode("utf-8")) for item in frames]

    @staticmethod
    def _error_facts(record):
        """The public execution-error facts of one history record."""
        facts = []
        status = record.get("status")
        if not isinstance(status, dict):
            return facts
        for item in status.get("messages") or []:
            if not (isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], dict)):
                continue
            if item[0] != "execution_error":
                continue
            facts.append(item[1])
        return facts

    def _persist_error_raw(self, directory, record, result):
        """Keep the exact raw evidence of a failed public execution.

        The production ``BridgeError`` serializes the received raw response
        and the raw responses of the frames that were already analysed.  Those
        are evidence: they are kept verbatim, never sanitised into a success
        and never dropped because a later parse failed.
        """
        raw_payloads = []
        frame_payloads = []
        for fact in self._error_facts(record):
            message = fact.get("exception_message")
            if not isinstance(message, str):
                continue
            try:
                payload = json.loads(message)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            details = payload.get("details")
            if not isinstance(details, dict):
                continue
            raw_response = details.get("raw_response")
            if isinstance(raw_response, str) and raw_response not in raw_payloads:
                raw_payloads.append(raw_response)
            prior = details.get("prior_frame_raw_responses")
            if isinstance(prior, list):
                for item in prior:
                    if isinstance(item, str) and item not in frame_payloads:
                        frame_payloads.append(item)
        if not raw_payloads and not frame_payloads:
            return
        if raw_payloads:
            artifact = self._artifact(directory + "/error-raw.txt",
                                     "\n".join(raw_payloads).encode("utf-8"))
            result["error_raw_artifact"] = artifact["path"]
            result["error_raw_sha256"] = artifact["sha256"]
            result["error_raw_count"] = len(raw_payloads)
        if frame_payloads:
            artifact = self._artifact(directory + "/error-frames.txt",
                                     "\n".join(frame_payloads).encode("utf-8"))
            result["error_frame_raw_artifact"] = artifact["path"]
            result["error_frame_raw_sha256"] = [sha256_bytes(item.encode("utf-8"))
                                                for item in frame_payloads]

    def _image_metadata(self, record):
        """Read the controlled image metadata through the public manual node."""
        outputs = record.get("outputs")
        if not isinstance(outputs, dict) or not isinstance(outputs.get("3"), dict):
            raise QualityContractError("IMAGE_METADATA_NODE_MISSING")
        text = outputs["3"].get("text")
        if not isinstance(text, list) or len(text) != 2 or not all(isinstance(item, str) for item in text):
            raise QualityContractError("IMAGE_METADATA_NODE_MISSING")
        helper = _legacy_graph_helpers()
        try:
            payload = helper._manual_payload(text)
        except Exception as error:  # noqa: BLE001 - any legacy failure is a contract failure
            raise QualityContractError("IMAGE_METADATA_NOT_JSON:" + type(error).__name__) from error
        if not isinstance(payload, dict):
            raise QualityContractError("IMAGE_METADATA_NOT_OBJECT")
        draft = payload.get("draft")
        if not isinstance(draft, dict) or not isinstance(draft.get("natural_zh"), str):
            raise QualityContractError("IMAGE_METADATA_MISSING")
        return draft["natural_zh"]

    def _video_frame_raws(self, raw_text):
        try:
            document = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise QualityContractError("VIDEO_RAW_NOT_JSON") from error
        if not isinstance(document, dict) or set(document) != {"frame_raw_responses"}:
            raise QualityContractError("VIDEO_RAW_SHAPE_INVALID")
        frames = document["frame_raw_responses"]
        if not isinstance(frames, list) or len(frames) != VIDEO_PROVIDER_CALLS:
            raise QualityContractError("VIDEO_RAW_DENOMINATOR_INVALID")
        if not all(isinstance(item, str) for item in frames):
            raise QualityContractError("VIDEO_RAW_NOT_STRING")
        return frames

    def _validate_row(self, row, history, record, expected_node, result, graph, chat_before, chat_after):
        """Structural validation of the actual public history record."""
        prompt_id = result["prompt_id"]
        status = record.get("status")
        if not isinstance(status, dict) or status.get("status_str") not in ("success", "completed"):
            raise QualityContractError("PUBLIC_EXECUTION_NOT_SUCCESSFUL")
        submitted = record.get("prompt")
        if not isinstance(submitted, list) or len(submitted) < 3:
            raise QualityContractError("PUBLIC_PROMPT_RECORD_INVALID")
        if submitted[1] != prompt_id:
            raise QualityContractError("PUBLIC_PROMPT_ID_MISMATCH")
        if submitted[2] != graph:
            raise QualityContractError("PUBLIC_GRAPH_MISMATCH")
        outputs = record.get("outputs")
        if not isinstance(outputs, dict) or not isinstance(outputs.get(expected_node), dict):
            raise QualityContractError("PUBLIC_NODE_OUTPUT_MISSING")
        text = outputs[expected_node]["text"]
        if row["media_kind"] == "image":
            self._validate_image(row, record, text, result)
        else:
            self._validate_video(row, history, record, text, result, chat_before, chat_after)

    def _validate_image(self, row, record, text, result):
        submitted = record["prompt"][2]
        if (submitted.get("1", {}).get("class_type") != "LVWControlledImageInput"
                or submitted.get("2", {}).get("class_type") != "LVWImagePromptBridge"
                or submitted.get("2", {}).get("inputs", {}).get("image") != ["1", 0]):
            raise QualityContractError("IMAGE_PUBLIC_PATH_BYPASSED")
        if submitted.get("1", {}).get("inputs", {}).get("image_reference") != row["input_reference"]:
            raise QualityContractError("IMAGE_REFERENCE_MISMATCH")
        raw_text, suggestion_text = text[0], text[1]
        try:
            envelope = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise QualityContractError("IMAGE_RAW_NOT_JSON") from error
        if not isinstance(envelope, dict):
            raise QualityContractError("IMAGE_RAW_NOT_OBJECT")
        if envelope.get("model") != MODEL_TAG or envelope.get("done") is not True:
            raise QualityContractError("IMAGE_PROVIDER_RESPONSE_INCOMPLETE")
        content = envelope.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise QualityContractError("IMAGE_PROVIDER_RESPONSE_INCOMPLETE")
        try:
            suggestion = json.loads(suggestion_text)
        except json.JSONDecodeError as error:
            raise QualityContractError("IMAGE_SUGGESTION_NOT_JSON") from error
        _validate_prompt_spec(suggestion)
        try:
            metadata = json.loads(self._image_metadata(record))
        except json.JSONDecodeError as error:
            raise QualityContractError("IMAGE_METADATA_NOT_JSON") from error
        if not isinstance(metadata, dict):
            raise QualityContractError("IMAGE_METADATA_NOT_OBJECT")
        dimensions = metadata.get("output_dimensions")
        if (metadata.get("source_sha256") != row["source_sha256"]
                or metadata.get("source_bytes") != row["source_bytes"]
                or not _is_hex(metadata.get("output_rgb_sha256"), 64)
                or not isinstance(dimensions, list) or not dimensions
                or any(not _is_int(value) or value <= 0 for value in dimensions)
                or max(dimensions) > IMAGE_LONG_EDGE):
            raise QualityContractError("IMAGE_METADATA_BINDING_INVALID")
        result["image_metadata"] = metadata

    def _validate_video(self, row, history, record, text, result, chat_before, chat_after):
        submitted = record["prompt"][2]
        if (submitted.get("1", {}).get("class_type") != "LVWVideoPromptOwner"
                or submitted.get("1", {}).get("inputs", {}).get("video_reference") != row["input_reference"]):
            raise QualityContractError("VIDEO_PUBLIC_PATH_BYPASSED")
        try:
            public_video_oracle(
                history, result["prompt_id"],
                source_sha256=row["source_sha256"], expected_model=MODEL_TAG,
                chat_calls_before=chat_before, chat_calls_after=chat_after,
            )
        except EvidenceError as error:
            raise QualityContractError("VIDEO_PUBLIC_ORACLE_FAILED:" + str(error)) from error
        try:
            suggestion = json.loads(text[1])
        except json.JSONDecodeError as error:
            raise QualityContractError("VIDEO_SUGGESTION_NOT_JSON") from error
        _validate_prompt_spec(suggestion)

    # -- orchestration ---------------------------------------------------
    def _empty_rows(self, code):
        return [{"asset_id": None, "media_kind": None, "ordinal": index + 1,
                 "execution_status": "BLOCKED", "quality_status": QUALITY_NOT_RUN,
                 "error_code": code, "source_sha256": None,
                 "source_bytes": None, "input_reference": None, "prompt_id": None,
                 "provider_calls": 0, "provider_calls_reserved": 0,
                 "graph_sha256": None, "raw_sha256": None,
                 "suggestion_sha256": None, "metadata_sha256": None, "history_sha256": None,
                 "raw_artifact": None, "raw_preserved": False, "automatic_retries": 0,
                 "listener_before": None, "listener_after": None, "release_evidence": None,
                 "video_snapshot_residue": None, "storage_unproven": False,
                 "cleanup_unproven": False, "halt": False}
                for index in range(FIXED_TOTAL)]

    def _finalize(self, rows, decision, extra=None):
        statuses = [row["execution_status"] for row in rows]
        receipt = {
            "kind": QD_RECEIPT_KIND,
            "phase": PHASE_KIND,
            "contract": CONTRACT_PATH,
            "run_id": self.run_id,
            "candidate_sha": self.candidate_sha,
            "authorization_sha256": self.authorization_sha256,
            "projection_sha256": self.projection_sha256,
            "run_root": str(self.root),
            "published_as": CANONICAL_RECEIPT_NAME,
            "staged_as": STAGED_RECEIPT_NAME,
            "source_identity_sha256": sha256_bytes(canonical_json(self.source_identity).encode("utf-8")),
            "fixed_denominator": {"images": FIXED_IMAGES, "videos": FIXED_VIDEOS, "total": FIXED_TOTAL},
            "rows": rows,
            "test_counts": {
                "fixed": FIXED_TOTAL,
                "PASS": statuses.count("PASS"),
                "FAIL": statuses.count("FAIL"),
                "BLOCKED": statuses.count("BLOCKED"),
                "NOT_RUN": statuses.count("NOT_RUN"),
            },
            "public_submissions": self._submissions,
            "public_submissions_succeeded": self._submissions_succeeded,
            "public_submissions_attempted": self._submissions,
            "provider_calls_observed": (self._provider_calls_observed
                                        if self._provider_calls_observed_known else None),
            "provider_calls_observed_known": self._provider_calls_observed_known,
            "provider_calls_reserved": self._provider_calls_reserved,
            "history_polls": self._polls,
            "artifact_files": self._artifact_files,
            "artifact_bytes": self._artifact_bytes,
            "storage_unproven": self._storage_unproven,
            "cleanup_unproven": self._cleanup_unproven,
            "parent_budget_capacity": self.parent_budget_capacity,
            "parent_budget_required_actions": MAX_TOTAL_PROVIDER_CALLS,
            "parent_budget_baseline_gpu_mib": self.binding["baseline_gpu_mib"],
            "bounds": {
                "max_public_submissions": MAX_PUBLIC_SUBMISSIONS,
                "max_provider_calls": MAX_TOTAL_PROVIDER_CALLS,
                "sample_history_timeout_seconds": SAMPLE_HISTORY_TIMEOUT_SECONDS,
                "phase_timeout_seconds": PHASE_TIMEOUT_SECONDS,
                "max_history_polls": MAX_HISTORY_POLLS,
                "max_artifact_bytes": MAX_ARTIFACT_BYTES,
                "max_total_artifact_bytes": MAX_TOTAL_ARTIFACT_BYTES,
                "max_artifact_files": MAX_ARTIFACT_FILES,
                "image_source_max_bytes": IMAGE_SOURCE_MAX_BYTES,
                "video_source_max_bytes": VIDEO_SOURCE_MAX_BYTES,
                "callback_max_seconds": CALLBACK_MAX_SECONDS,
                "observation_max_seconds": OBSERVATION_MAX_SECONDS,
                "persistence_max_seconds": PERSISTENCE_MAX_SECONDS,
                "release_max_seconds": RELEASE_MAX_SECONDS,
                "automatic_retries": 0,
            },
            "decision": decision,
            "stage_pass_claim": False,
            "product_gate0": False,
            "quality_pass_claim": False,
            "scoring_executed": False,
            "real_execution_performed": False,
            "receipt_persisted": None,
            "receipt_persistence_error": None,
            "terminal_status": None,
            "timing_assurance": copy.deepcopy(TIMING_ASSURANCE),
            "hard_timing_blocker": TIMING_ASSURANCE["hard_end_to_end_supervision"],
            "ownership_assurance": {
                "descriptor_relative_writes": True,
                "all_ancestors_pinned": ["run_root", "temp", "phase", "nested artifact directories"],
                "identity_checked_after_callbacks": True,
                "identity_checked_before_send": True,
                "identity_checked_before_cleanup_handoff": True,
                "exclusive_single_write": True,
                "accepted_limitation": (
                    "This is an in-process inode observation of the owned "
                    "directories.  It detects a renamed, replaced or symlinked "
                    "ancestor and refuses to write through it.  It does not "
                    "claim immunity against a hostile kernel or a filesystem "
                    "that moves inodes underneath the process."),
            },
        }
        if extra:
            receipt.update(extra)
        self.receipt = receipt
        return receipt

    def _serialized_receipt(self, receipt):
        """Serialize the receipt so that it states its own final size exactly.

        The receipt states its own byte count and its own file count, so the
        document grows when those fields are filled in.  The size is computed
        to a bounded fixed point: the fields are filled with the assumed
        length, the document is serialized, and a padding field absorbs the
        remaining difference so that the serialized length is exactly the
        recorded value.  The iteration is bounded; a document that cannot
        reach a fixed point is an explicit failure, never a silent truncation.

        The publication creates two retained directory entries: the staged
        file and the canonical hard link to it.  Both are counted honestly.
        """
        document = dict(receipt)
        document["receipt_persisted"] = True
        document["receipt_persistence_error"] = None
        document["terminal_status"] = "TERMINAL_RECEIPT_PERSISTED"
        document["published_as"] = CANONICAL_RECEIPT_NAME
        document["staged_as"] = STAGED_RECEIPT_NAME
        document["artifact_files_including_receipt"] = self._artifact_files + 2
        document["artifact_bytes_including_receipt"] = self._artifact_bytes
        document["receipt_bytes"] = 0
        document[RECEIPT_PADDING_KEY] = ""
        assumed = len(canonical_json(document).encode("utf-8")) + 64
        for _ in range(RECEIPT_FIXED_POINT_ITERATIONS):
            document["receipt_bytes"] = assumed
            document["artifact_bytes_including_receipt"] = self._artifact_bytes + 2 * assumed
            document["artifact_files_including_receipt"] = self._artifact_files + 2
            raw = canonical_json(document).encode("utf-8")
            actual = len(raw)
            if actual == assumed:
                return raw, document
            if actual < assumed:
                document[RECEIPT_PADDING_KEY] = "x" * (assumed - actual)
                padded = canonical_json(document).encode("utf-8")
                if len(padded) == assumed:
                    return padded, document
                assumed = len(padded)
                continue
            assumed = actual
        raise QualityContractError("RECEIPT_FIXED_POINT_UNREACHED")

    def _stage_receipt(self, raw):
        """Write the payload to an exclusive staged file and make it durable.

        The staged file is created relative to the pinned phase handle, it is
        flushed and fsynced, and it is never published under the canonical
        name.  A failed staging is retained as explicitly non-authoritative
        evidence; it is never deleted and never overwritten.
        """
        descriptor = self._owned_phase.open_child_file(
            STAGED_RECEIPT_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        staged = {"name": STAGED_RECEIPT_NAME, "bytes": len(raw)}
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            # The staged bytes stay on disk as non-authoritative evidence.
            staged["durable"] = False
            raise
        staged["durable"] = True
        return staged

    def _publish_receipt(self):
        """Publish the staged bytes under the canonical name without overwrite.

        A hard link is the supported no-overwrite publication primitive: it
        fails when the canonical name already exists, so a prior receipt is
        never overwritten.  There is no rename-overwrite and no absolute path
        fallback.
        """
        try:
            os.link(STAGED_RECEIPT_NAME, CANONICAL_RECEIPT_NAME,
                    src_dir_fd=self._owned_phase.fd, dst_dir_fd=self._owned_phase.fd,
                    follow_symlinks=False)
        except FileExistsError as error:
            raise QualityContractError("ARTIFACT_REPLAY_FORBIDDEN:" + CANONICAL_RECEIPT_NAME) from error
        except OSError as error:
            raise QualityContractError("RECEIPT_PUBLICATION_FAILED:" + type(error).__name__) from error

    def _write_receipt(self, receipt):
        """Persist the terminal receipt.

        The order is fixed: the bounded canonical payload is prepared, it is
        written to an exclusive staged file under the pinned descriptor parent
        and flushed and fsynced there, and only a successful durable staging
        is published under the canonical name with a no-overwrite primitive.
        Staged bytes are never authority: while they are unpublished, no
        canonical receipt exists, so no consumer can read them as a terminal
        receipt.

        The terminal receipt is itself an artifact: its own bytes and file
        count are inside the frozen 8MiB / 128MiB / 256 bounds, the totals
        reported are the honest post-write totals that agree with the files on
        disk, and an impossible receipt is reported as an explicit
        non-persisted terminal status instead of being truncated, overwritten
        or erased.
        """
        receipt.update(receipt_document(receipt))
        try:
            raw, document = self._serialized_receipt(receipt)
            if len(raw) > MAX_ARTIFACT_BYTES:
                raise QualityContractError("RECEIPT_OVER_ARTIFACT_CAP")
            if self._artifact_files + 2 > MAX_ARTIFACT_FILES:
                raise QualityContractError("RECEIPT_FILE_BUDGET_EXCEEDED")
            if self._artifact_bytes + 2 * len(raw) > MAX_TOTAL_ARTIFACT_BYTES:
                raise QualityContractError("RECEIPT_TOTAL_BUDGET_EXCEEDED")
            if self._owned_phase is None:
                raise QualityContractError("OWNED_DIRECTORY_CLOSED:" + str(self.directory))
            self._verify_owned()
            staged = self._stage_receipt(raw)
            receipt["staged_receipt_retained"] = True
            self._publish_receipt()
            # The staged entry and the published entry are both retained and
            # both counted; they share one inode.
            self._artifact_files += 2
            self._artifact_bytes += 2 * len(raw)
            receipt.update(document)
            receipt["receipt_persisted"] = True
            receipt["receipt_persistence_error"] = None
            receipt["terminal_status"] = "TERMINAL_RECEIPT_PERSISTED"
            receipt["staged_receipt_retained"] = True
            receipt["staged_receipt_bytes"] = staged["bytes"]
            return True
        except Exception as error:  # noqa: BLE001 - the failure must be visible
            receipt["receipt_persisted"] = False
            receipt["receipt_persistence_error"] = type(error).__name__ + ":" + str(error)[:200]
            receipt["terminal_status"] = "TERMINAL_RECEIPT_NOT_PERSISTED"
            receipt["storage_unproven"] = True
            self._storage_unproven = True
            return False

    def _finish(self, rows, decision, extra=None, persist=True):
        receipt = self._finalize(rows, decision, extra)
        if persist and not self._write_receipt(receipt):
            receipt["decision"] = "QUALITY_EXECUTION_BLOCKED"
            receipt["error_code"] = "RECEIPT_PERSISTENCE_FAILED"
            receipt["storage_unproven"] = True
        elif not persist:
            receipt["receipt_persisted"] = False
            receipt["receipt_persistence_error"] = "RECEIPT_WRITE_REFUSED_PREEXISTING_PHASE_DIRECTORY"
            receipt["terminal_status"] = "TERMINAL_RECEIPT_NOT_PERSISTED_PREEXISTING_PHASE_DIRECTORY"
        return receipt

    def run(self):
        """Execute the fixed sixteen rows once.  Never called twice."""
        if self._ran:
            raise QualityContractError("QUALITY_PHASE_ALREADY_EXECUTED")
        self._ran = True
        try:
            self._started = self._now()
        except QualityContractError as error:
            # A clock that is not finite or not monotonic cannot prove a
            # deadline, so the run is refused before any public action.
            rows = self._empty_rows(str(error))
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                {"error_code": str(error)}, persist=False)
        self._phase_deadline = self._started + PHASE_TIMEOUT_SECONDS
        try:
            self._open_owned_directories()
        except QualityContractError as error:
            # The refusal happens before any owned entry can be created, so a
            # redirected ancestor never receives a foreign file.
            rows = self._empty_rows(str(error))
            receipt = self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                   {"error_code": str(error),
                                    "owned_directories_closed": True,
                                    "phase_directory_replay_refused":
                                        str(error) == "PHASE_DIRECTORY_EXISTS"},
                                   persist=False)
            self._close_owned_directories()
            return receipt
        except OSError as error:
            rows = self._empty_rows("PHASE_DIRECTORY_UNAVAILABLE")
            receipt = self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                   {"error_code": "PHASE_DIRECTORY_UNAVAILABLE:" + type(error).__name__},
                                   persist=False)
            self._close_owned_directories()
            return receipt
        try:
            return self._run_owned()
        finally:
            # Every owned handle is closed, also on a failure or a replay, and
            # no write can happen after the root closure.
            self._close_owned_directories()

    def _run_owned(self):
        """The sixteen row execution with the owned directories pinned."""
        # ---- parent capacity admission before the first public action ----
        try:
            admission_error = self._admission_error or self._parent_proof_is_fresh()
        except QualityContractError as error:
            admission_error = str(error)
        if admission_error:
            rows = self._empty_rows(admission_error)
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                {"error_code": admission_error,
                                 "parent_budget_capacity": self.parent_budget_capacity,
                                 "parent_budget_required_actions": MAX_TOTAL_PROVIDER_CALLS})

        try:
            rows = self._parse_projection()
        except QualityContractError as error:
            rows = self._empty_rows(str(error))
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED", {"error_code": str(error)})

        # ---- every source is validated before the first submission --------
        source_failures = []
        for row in rows:
            try:
                row["source_evidence"] = self._validate_source(row)
            except QualityContractError as error:
                source_failures.append((row, str(error)))
            except OSError as error:
                source_failures.append((row, "SOURCE_UNAVAILABLE:" + type(error).__name__))
        if source_failures:
            failed = {id(row) for row, _ in source_failures}
            codes = {id(row): code for row, code in source_failures}
            for row in rows:
                if id(row) in failed:
                    row["execution_status"] = "FAIL"
                    row["error_code"] = codes[id(row)]
                else:
                    row["execution_status"] = "BLOCKED"
                    row["error_code"] = "SOURCE_PRECONDITION_FAILED"
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                {"error_code": sorted(set(codes.values()))[0],
                                 "public_submissions": 0})

        try:
            workflows = self._load_workflows()
        except QualityContractError as error:
            for row in rows:
                row["execution_status"] = "BLOCKED"
                row["error_code"] = str(error)
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED", {"error_code": str(error)})

        results = []
        for index, row in enumerate(rows):
            try:
                expired = self._now() - self._started > PHASE_TIMEOUT_SECONDS
            except QualityContractError as error:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = str(error)
                break
            if expired:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PHASE_DEADLINE_EXCEEDED"
                break
            if self._submissions >= MAX_PUBLIC_SUBMISSIONS:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PUBLIC_SUBMISSION_BUDGET_EXCEEDED"
                break
            if self._provider_calls_reserved >= MAX_TOTAL_PROVIDER_CALLS:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PROVIDER_CALL_BUDGET_EXCEEDED"
                break
            try:
                outcome = self._execute_row(row, workflows)
            except Exception as error:  # noqa: BLE001 - one row may never abort the phase
                outcome = {
                    "asset_id": row["asset_id"], "media_kind": row["media_kind"],
                    "ordinal": row["ordinal"], "source_sha256": row["source_sha256"],
                    "source_bytes": row["source_bytes"], "input_reference": row["input_reference"],
                    "execution_status": "FAIL", "quality_status": QUALITY_NOT_RUN,
                    "error_code": "ROW_EXECUTION_UNEXPECTED:" + type(error).__name__
                                  + ":" + str(error)[:160],
                    "stage": "unexpected", "prompt_id": None, "provider_calls": 0,
                    "provider_calls_observed_known": False, "provider_calls_reserved": 0,
                    "graph_sha256": None, "graph_artifact": None, "raw_sha256": None,
                    "raw_bytes": None, "raw_artifact": None, "raw_preserved": False,
                    "suggestion_sha256": None, "suggestion_artifact": None,
                    "metadata_sha256": None, "metadata_artifact": None,
                    "frame_raw_sha256": [], "history_sha256": None, "history_artifact": None,
                    "error_raw_sha256": None, "error_raw_artifact": None,
                    "error_frame_raw_sha256": [], "provider_before": None, "provider_after": None,
                    "source_evidence": None, "listener_before": None, "listener_after": None,
                    "release_evidence": None, "video_snapshot_residue": None,
                    "cleanup_diagnostics": ["ROW_EXECUTION_UNEXPECTED:" + type(error).__name__],
                    "automatic_retries": 0, "halt": True,
                }
                self._cleanup_unproven = True
            results.append(outcome)
            if outcome["halt"]:
                self._halted = True
                self._halt_reason = outcome["error_code"]
                for pending in rows[index + 1:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "HALTED_AFTER_" + (outcome["error_code"] or "UNKNOWN")
                break

        merged = []
        for index, row in enumerate(rows):
            if index < len(results):
                merged.append(results[index])
            else:
                blocked = dict(row)
                blocked["execution_status"] = "BLOCKED"
                blocked["quality_status"] = QUALITY_NOT_RUN
                merged.append(blocked)

        statuses = [row["execution_status"] for row in merged]
        if statuses.count("PASS") == FIXED_TOTAL:
            decision = "QUALITY_EXECUTION_COMPLETE_ALL_16_PASS"
        elif statuses.count("BLOCKED") == FIXED_TOTAL:
            decision = "QUALITY_EXECUTION_BLOCKED"
        else:
            decision = "QUALITY_EXECUTION_PARTIAL"
        extra = {"halted": self._halted, "halt_reason": self._halt_reason}
        return self._finish(merged, decision, extra)


# ======================================================================
# QS: independent score recomputation
# ======================================================================

def _log_evidence(snapshot):
    """The receipt keeps the hashes and counts, never the whole provider log."""
    return {key: value for key, value in snapshot.items() if key != "raw_log"}


def load_canonical_receipt(directory):
    """Load the authoritative terminal receipt.

    Only the canonical name is authority.  A staged file, even with identical
    bytes, is explicitly non-authoritative and is rejected here, so an
    unpublished staging can never be consumed as a terminal receipt.
    """
    root = Path(directory)
    candidate = root / CANONICAL_RECEIPT_NAME
    if candidate.is_symlink() or not candidate.is_file():
        raise QualityContractError("CANONICAL_RECEIPT_ABSENT")
    raw = candidate.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QualityContractError("CANONICAL_RECEIPT_UNREADABLE") from error
    if not isinstance(document, dict):
        raise QualityContractError("CANONICAL_RECEIPT_UNREADABLE")
    if document.get("published_as") != CANONICAL_RECEIPT_NAME:
        raise QualityContractError("CANONICAL_RECEIPT_NOT_AUTHORITATIVE")
    if document.get("receipt_persisted") is not True:
        raise QualityContractError("CANONICAL_RECEIPT_NOT_PERSISTED")
    if document.get("terminal_status") != "TERMINAL_RECEIPT_PERSISTED":
        raise QualityContractError("CANONICAL_RECEIPT_NOT_PERSISTED")
    return document


def _safe_artifact_path(artifact_root, relative):
    """Resolve one artifact path without escaping the owned artifact root."""
    root = Path(artifact_root).resolve(strict=True)
    if not isinstance(relative, str) or not relative:
        raise QualityContractError("SCORE_ARTIFACT_PATH_INVALID")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise QualityContractError("SCORE_ARTIFACT_PATH_INVALID")
    candidate = root / relative
    for ancestor in (candidate, *candidate.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise QualityContractError("SCORE_ARTIFACT_REDIRECT_FORBIDDEN")
    if candidate.is_symlink():
        raise QualityContractError("SCORE_ARTIFACT_REDIRECT_FORBIDDEN")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise QualityContractError("SCORE_ARTIFACT_OUTSIDE_ROOT") from error
    if resolved != candidate or not candidate.is_file():
        raise QualityContractError("SCORE_ARTIFACT_NOT_PLAIN_FILE")
    return candidate


def verify_independence(independence, *, implementer_identity=None, run_id=None):
    """Prove reviewer separation from an isolation receipt.

    A reviewer identity string alone proves nothing; the isolation receipt is
    the only accepted proof of independence.
    """
    if not isinstance(independence, dict):
        raise QualityContractError("INDEPENDENCE_RECEIPT_MISSING")
    if run_id is not None and independence.get("run_id") != run_id:
        raise QualityContractError("INDEPENDENCE_RUN_BINDING_MISMATCH")
    separation = independence.get("separation")
    if not isinstance(separation, dict):
        raise QualityContractError("INDEPENDENCE_SEPARATION_MISSING")
    for key in ("isolated_instance", "separate_session", "no_implementation_participation"):
        if separation.get(key) is not True:
            raise QualityContractError("INDEPENDENCE_SEPARATION_UNPROVEN:" + key)
    reviewers = independence.get("reviewers")
    if not isinstance(reviewers, list) or not reviewers:
        raise QualityContractError("INDEPENDENCE_REVIEWERS_MISSING")
    identities = []
    sessions = []
    pairs = []
    for entry in reviewers:
        if not isinstance(entry, dict):
            raise QualityContractError("INDEPENDENCE_REVIEWER_INVALID")
        reviewer_id = entry.get("reviewer_id")
        session_id = entry.get("session_id")
        role = entry.get("role")
        if (not isinstance(reviewer_id, str) or not reviewer_id.strip()
                or not isinstance(session_id, str) or not session_id.strip()
                or role != INDEPENDENT_REVIEWER_ROLE):
            raise QualityContractError("INDEPENDENCE_REVIEWER_INVALID")
        if implementer_identity is not None and reviewer_id == implementer_identity:
            raise QualityContractError("INDEPENDENCE_REVIEWER_IS_IMPLEMENTER")
        identities.append(reviewer_id)
        sessions.append(session_id)
        pairs.append((reviewer_id, session_id))
    if len(set(identities)) != len(identities) or len(set(sessions)) != len(sessions):
        raise QualityContractError("INDEPENDENCE_REVIEWER_NOT_UNIQUE")
    if len(set(pairs)) != len(pairs):
        raise QualityContractError("INDEPENDENCE_REVIEWER_PAIR_REUSED")
    return {
        "reviewer_ids": sorted(set(identities)),
        "session_ids": sorted(set(sessions)),
        # The reviewer and the session are only ever accepted as the exact
        # pair that the isolation receipt lists.  Separate membership sets
        # would accept a cross pair such as reviewer A with session B.
        "reviewer_session_pairs": sorted([list(pair) for pair in set(pairs)]),
        "separation": dict(separation),
    }


def _row_evidence_complete(row, receipt):
    """Validate the source, storage and cleanup evidence of one row.

    Every row is checked, whether its execution passed or failed.  The same
    pure validators that the execution phase uses are applied here, so a row
    that the execution could not prove is unknown in both.  A missing, null
    or malformed declaration is unknown: the uncertainty flags must be the
    literal boolean False, and nothing is ever defaulted to a pass.
    """
    valid, reason = validate_source_evidence(
        row.get("source_evidence"),
        source_sha256=row.get("source_sha256"),
        source_bytes=row.get("source_bytes"),
        input_reference=row.get("input_reference"),
        run_root=receipt.get("run_root"))
    if not valid:
        return False, reason
    valid, reason = validate_release_evidence(
        row.get("release_evidence"),
        baseline_gpu_mib=receipt.get("parent_budget_baseline_gpu_mib"))
    if not valid:
        return False, reason
    residue = row.get("video_snapshot_residue")
    if not isinstance(residue, list):
        return False, "RESIDUE_EVIDENCE_MISSING"
    if residue:
        return False, "RESIDUE_EVIDENCE_PRESENT"
    if row.get("storage_unproven") is not False:
        return False, "STORAGE_UNPROVEN"
    if receipt.get("storage_unproven") is not False:
        return False, "STORAGE_UNPROVEN"
    if row.get("cleanup_unproven") is not False:
        return False, "CLEANUP_UNPROVEN"
    if receipt.get("cleanup_unproven") is not False:
        return False, "CLEANUP_UNPROVEN"
    return True, None


def _validate_score_document(score):
    """Validate one independent scoring receipt."""
    if not isinstance(score, dict):
        raise QualityContractError("SCORE_RECEIPT_NOT_OBJECT")
    for key in ("run_id", "candidate_sha", "projection_sha256", "asset_id",
                "source_sha256", "raw_sha256", "raw_artifact", "reviewer_id", "session_id"):
        value = score.get(key)
        if not isinstance(value, str) or not value.strip():
            raise QualityContractError("SCORE_RECEIPT_FIELD_MISSING:" + key)
    if not _is_hex(score["candidate_sha"], 40):
        raise QualityContractError("SCORE_CANDIDATE_SHA_INVALID")
    if not _is_hex(score["projection_sha256"], 64):
        raise QualityContractError("SCORE_PROJECTION_SHA_INVALID")
    if not _is_hex(score["source_sha256"], 64):
        raise QualityContractError("SCORE_SOURCE_SHA_INVALID")
    if not _is_hex(score["raw_sha256"], 64):
        raise QualityContractError("SCORE_RAW_SHA_INVALID")
    dimensions = score.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(FROZEN_DIMENSIONS):
        raise QualityContractError("SCORE_DIMENSION_SET_INVALID")
    for name, value in dimensions.items():
        if not _is_int(value):
            raise QualityContractError("SCORE_DIMENSION_NOT_INTEGER:" + name)
        if value < DIMENSION_MIN or value > DIMENSION_MAX:
            raise QualityContractError("SCORE_DIMENSION_OUT_OF_RANGE:" + name)
    critical = score.get("critical_hallucinations")
    if not _is_int(critical):
        raise QualityContractError("SCORE_CRITICAL_HALLUCINATIONS_NOT_INTEGER")
    if critical < 0:
        raise QualityContractError("SCORE_CRITICAL_HALLUCINATIONS_NEGATIVE")
    basis = score.get("basis")
    if not isinstance(basis, str) or not basis.strip():
        raise QualityContractError("SCORE_BASIS_MISSING")
    return score


def recompute_scores(execution_receipt, artifact_root, score_receipts, *,
                     independence=None, implementer_identity=None):
    """QS: recompute the independent quality verdict for the fixed sixteen rows.

    This entry point is pure validation and aggregation.  It never executes a
    model, never matches keywords and never invents a semantic judgement.
    """
    if not isinstance(execution_receipt, dict) or execution_receipt.get("kind") != QD_RECEIPT_KIND:
        raise QualityContractError("QS_EXECUTION_RECEIPT_INVALID")
    # Only a published canonical receipt is authority.  A staged or failed
    # terminal receipt is rejected here, at the consumer loading boundary.
    if execution_receipt.get("published_as") != CANONICAL_RECEIPT_NAME:
        raise QualityContractError("QS_EXECUTION_RECEIPT_NOT_AUTHORITATIVE")
    if execution_receipt.get("receipt_persisted") is not True:
        raise QualityContractError("QS_EXECUTION_RECEIPT_NOT_PERSISTED")
    if execution_receipt.get("terminal_status") != "TERMINAL_RECEIPT_PERSISTED":
        raise QualityContractError("QS_EXECUTION_RECEIPT_NOT_PERSISTED")
    denominator = execution_receipt.get("fixed_denominator")
    if (not isinstance(denominator, dict) or denominator.get("total") != FIXED_TOTAL
            or denominator.get("images") != FIXED_IMAGES or denominator.get("videos") != FIXED_VIDEOS):
        raise QualityContractError("QS_DENOMATOR_INVALID")
    rows = execution_receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != FIXED_TOTAL:
        raise QualityContractError("QS_ROW_COUNT_INVALID")
    run_id = execution_receipt.get("run_id")
    candidate_sha = execution_receipt.get("candidate_sha")
    projection_sha256 = execution_receipt.get("projection_sha256")
    if not isinstance(run_id, str) or not _is_hex(candidate_sha, 40) or not _is_hex(projection_sha256, 64):
        raise QualityContractError("QS_EXECUTION_RECEIPT_IDENTITY_INVALID")

    by_asset = {}
    for row in rows:
        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise QualityContractError("QS_ROW_ASSET_ID_INVALID")
        if asset_id in by_asset:
            raise QualityContractError("QS_DUPLICATE_ROW:" + asset_id)
        by_asset[asset_id] = row

    if isinstance(score_receipts, dict):
        score_receipts = score_receipts.get("scores")
    if not isinstance(score_receipts, list):
        raise QualityContractError("QS_SCORE_RECEIPTS_INVALID")
    independence_evidence = verify_independence(
        independence, implementer_identity=implementer_identity, run_id=run_id)
    # The reviewer and the session are only ever accepted as the exact pair
    # the isolation receipt lists.  A cross pair such as reviewer A with the
    # session of reviewer B is not an independent reviewer.
    known_pairs = {tuple(pair) for pair in independence_evidence["reviewer_session_pairs"]}

    scores = {}
    for document in score_receipts:
        score = _validate_score_document(document)
        asset_id = score["asset_id"]
        if asset_id not in by_asset:
            raise QualityContractError("QS_FOREIGN_ROW:" + asset_id)
        if asset_id in scores:
            raise QualityContractError("QS_DUPLICATE_SCORE:" + asset_id)
        if score["run_id"] != run_id:
            raise QualityContractError("QS_SCORE_RUN_MISMATCH:" + asset_id)
        if score["candidate_sha"] != candidate_sha:
            raise QualityContractError("QS_SCORE_CANDIDATE_MISMATCH:" + asset_id)
        if score["projection_sha256"] != projection_sha256:
            raise QualityContractError("QS_SCORE_PROJECTION_MISMATCH:" + asset_id)
        row = by_asset[asset_id]
        if score["source_sha256"] != row.get("source_sha256"):
            raise QualityContractError("QS_SCORE_SOURCE_MISMATCH:" + asset_id)
        if (score["reviewer_id"], score["session_id"]) not in known_pairs:
            raise QualityContractError("QS_SCORE_REVIEWER_SESSION_PAIR_UNKNOWN:" + asset_id)
        scores[asset_id] = score

    computed = []
    for row in rows:
        asset_id = row["asset_id"]
        media_kind = row.get("media_kind")
        entry = {
            "asset_id": asset_id,
            "media_kind": media_kind,
            "execution_status": row.get("execution_status"),
            "quality_status": "FAIL",
            "usable": False,
            "resolved": False,
            "reason": None,
            "total": None,
            "critical_hallucinations": None,
            "dimensions": None,
            "reviewer_id": None,
            "session_id": None,
            "raw_sha256": row.get("raw_sha256"),
            "raw_bytes": None,
            "raw_artifact": row.get("raw_artifact"),
            "cleanup_proven": False,
        }
        score = scores.get(asset_id)
        execution_passed = row.get("execution_status") == "PASS"
        evidence_complete, evidence_reason = _row_evidence_complete(row, execution_receipt)
        cleanup_proven = evidence_complete
        entry["cleanup_proven"] = cleanup_proven
        entry["evidence_complete"] = evidence_complete
        entry["evidence_reason"] = evidence_reason
        # The raw evidence is verified for every applicable row: a row with an
        # independent score must have a preserved raw whose hash *and* byte
        # length match both the execution record and the scoring record.
        raw = None
        if row.get("raw_preserved") is True and row.get("raw_artifact"):
            artifact = _safe_artifact_path(artifact_root, row.get("raw_artifact"))
            raw = artifact.read_bytes()
            if sha256_bytes(raw) != row.get("raw_sha256"):
                raise QualityContractError("QS_RAW_ARTIFACT_HASH_MISMATCH:" + asset_id)
            declared = row.get("raw_bytes")
            if not _is_int(declared) or declared != len(raw):
                raise QualityContractError("QS_RAW_ARTIFACT_LENGTH_MISMATCH:" + asset_id)
            entry["raw_bytes"] = len(raw)
        if score is None:
            entry["reason"] = "MISSING_SCORE"
            computed.append(entry)
            continue
        if raw is None:
            raise QualityContractError("QS_SCORE_RAW_NOT_PRESERVED:" + asset_id)
        if score["raw_artifact"] != row.get("raw_artifact"):
            raise QualityContractError("QS_SCORE_ARTIFACT_SUBSTITUTED:" + asset_id)
        if sha256_bytes(raw) != score["raw_sha256"]:
            raise QualityContractError("QS_SCORE_RAW_HASH_MISMATCH:" + asset_id)
        expected_bytes = score.get("raw_bytes")
        if expected_bytes is not None:
            if not _is_int(expected_bytes) or expected_bytes != len(raw):
                raise QualityContractError("QS_SCORE_RAW_LENGTH_MISMATCH:" + asset_id)
        total = sum(score["dimensions"][name] for name in FROZEN_DIMENSIONS)
        critical = score["critical_hallucinations"]
        entry["total"] = total
        entry["critical_hallucinations"] = critical
        entry["dimensions"] = dict(score["dimensions"])
        entry["reviewer_id"] = score["reviewer_id"]
        entry["session_id"] = score["session_id"]
        if execution_passed:
            if not evidence_complete:
                # A passed execution whose source, storage or cleanup
                # evidence is unknown can never become usable or resolved.
                entry["resolved"] = False
                entry["usable"] = False
                entry["reason"] = "EVIDENCE_UNKNOWN:" + str(evidence_reason)
            else:
                usable = total >= PER_SAMPLE_TOTAL_MIN and critical <= CRITICAL_HALLUCINATIONS_MAX
                entry["resolved"] = True
                if usable:
                    entry["quality_status"] = "PASS"
                    entry["usable"] = True
                    entry["reason"] = "USABLE"
                else:
                    entry["reason"] = ("CRITICAL_HALLUCINATION"
                                       if critical > CRITICAL_HALLUCINATIONS_MAX
                                       else "TOTAL_BELOW_THRESHOLD")
        else:
            # An execution failure stays a quality FAIL inside the fixed
            # sixteen row denominator.  Its verified, independently reviewed
            # raw evidence still contributes its critical findings; it is
            # never erased.  A known ordinary refusal or structure failure
            # with verified raw and proven cleanup may be resolved without
            # being usable; an unknown source, storage or cleanup state can
            # never be resolved.
            entry["quality_status"] = "FAIL"
            entry["usable"] = False
            base = error_base_code(row.get("error_code") or "")
            if base in KNOWN_EXECUTION_FAILURE_CODES and evidence_complete:
                entry["resolved"] = True
                entry["reason"] = "KNOWN_EXECUTION_FAILURE_RESOLVED_NOT_USABLE"
            elif not evidence_complete:
                entry["resolved"] = False
                entry["reason"] = "EVIDENCE_UNKNOWN:" + str(evidence_reason)
            else:
                entry["resolved"] = False
                entry["reason"] = "UNKNOWN_EXECUTION_FAILURE"
        computed.append(entry)

    images_usable = sum(1 for entry in computed
                         if entry["media_kind"] == "image" and entry["usable"])
    videos_usable = sum(1 for entry in computed
                         if entry["media_kind"] == "video" and entry["usable"])
    resolved_critical = [entry["critical_hallucinations"] for entry in computed
                         if entry["critical_hallucinations"] is not None]
    total_critical = sum(resolved_critical)
    critical_known = len(resolved_critical) == FIXED_TOTAL
    unresolved = [entry["asset_id"] for entry in computed if not entry["resolved"]]
    thresholds_met = (images_usable >= IMAGE_USABLE_MIN and videos_usable >= VIDEO_USABLE_MIN
                      and total_critical <= CRITICAL_HALLUCINATIONS_MAX)
    all_rows_resolved = not unresolved
    aggregate_pass = bool(thresholds_met and all_rows_resolved and critical_known)
    if aggregate_pass:
        decision = "QUALITY_THRESHOLDS_MET_FOR_THIS_BOUND_RUN"
    elif not all_rows_resolved:
        decision = "QUALITY_INCOMPLETE_UNRESOLVED_ROWS"
    else:
        decision = "QUALITY_THRESHOLDS_NOT_MET"

    return {
        "kind": QS_RECEIPT_KIND,
        "phase": PHASE_KIND,
        "contract": CONTRACT_PATH,
        "run_id": run_id,
        "candidate_sha": candidate_sha,
        "projection_sha256": projection_sha256,
        "fixed_denominator": {"images": FIXED_IMAGES, "videos": FIXED_VIDEOS, "total": FIXED_TOTAL},
        "rows": computed,
        "thresholds": {
            "images_usable": images_usable,
            "images_required": IMAGE_USABLE_MIN,
            "videos_usable": videos_usable,
            "videos_required": VIDEO_USABLE_MIN,
            "total_critical_hallucinations": total_critical,
            "critical_hallucinations_max": CRITICAL_HALLUCINATIONS_MAX,
            "critical_hallucinations_known": critical_known,
            "per_sample_total_min": PER_SAMPLE_TOTAL_MIN,
            "dimension_max": DIMENSION_MAX,
            "scored_rows": len(resolved_critical),
        },
        "thresholds_met": thresholds_met,
        "all_rows_resolved": all_rows_resolved,
        "unresolved_rows": unresolved,
        "aggregate_pass": aggregate_pass,
        "decision": decision,
        "independence": independence_evidence,
        "scoring_policy": {
            "execution_failure_is_usable": False,
            "all_technical_rows_pass_required": False,
            "all_rows_evidence_resolved_required": True,
            "failed_row_with_verified_raw": (
                "The independent score identity, raw hash and raw length are validated and its "
                "critical findings contribute to the global total. The row stays a quality FAIL. "
                "A known ordinary refusal or structure failure with verified raw and proven "
                "cleanup is resolved without being usable."),
            "unknown_source_storage_cleanup_or_review": (
                "Cannot aggregate PASS. A missing raw or a missing review is not a known zero "
                "critical count."),
            "authority": "reports/v0-s3/product-gate0/p3b-correction-01.adjudication.json",
        },
        "limitations": [
            "Four sampled frames cannot prove full motion continuity or physical camera movement.",
            "Semantic judgements come only from the independent scoring receipts.",
            "The supplied reviewer identities are a schema and binding check; genuine independent "
            "provenance remains parent coordinator evidence.",
            "This verdict covers only the bound sixteen rows of this run.",
        ],
        "stage_pass_claim": False,
        "product_gate0": False,
        "scoring_source": "INDEPENDENT_SCORING_RECEIPTS_ONLY",
        "model_called": False,
        "keyword_scoring": False,
        "automatic_semantic_scoring": False,
        "frame_continuity_claimed": False,
    }
