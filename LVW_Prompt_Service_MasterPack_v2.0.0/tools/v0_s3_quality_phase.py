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

Send boundary
-------------
Every controlled driver accessor - the submission counter, the public
submission limit and the submit callable itself - and every controlled
callback is resolved *before* the final bounded source verification of a row.
That verification is made against the *sealed original* five component
descriptor identity that was written into the exclusive source seal before
the first public submission, so an accessor that changes the content, the
identity or the path of a prepared source produces zero sends, zero charges
and zero reserved provider calls.  The single coherent admission - the
ownership check, the one final monotonic clock sample, the typed parent
proof and the remaining capacity - then decides the send, and nothing
unchecked happens between that admission and the cached submit callable.

Scoring boundary
----------------
The scoring entry point reads the *actually published* canonical receipt
through a strict, descriptor relative artifact boundary: the run root, the
``temp`` directory and the phase directory are opened with
``O_DIRECTORY|O_NOFOLLOW``, so a renamed ancestor that was replaced by a
symlink is refused instead of being resolved away.  The canonical document is
the authority.  A supplied receipt may only restrict it: the permitted
verdict overlay is a closed enumeration and every other published field is an
actual execution fact that has to be reproduced exactly.
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

# The internal bound of the named custody that one quality evaluation holds.
#
# The frozen contract fixes sixteen rows.  One evaluation consumes at most
# the canonical receipt, the source seal and one raw leaf per row, and it
# walks at most the shared ``rows`` directory plus one row directory per
# row.  The bound below is a conservative multiple of that frozen shape, so
# a genuine evaluation can never reach it.
#
# The bound is *internal* and fail-closed.  It is not a public threshold, it
# is not a platform limit and it is never widened to let a run pass: an
# evaluation that would need more custody than this refuses instead of
# growing its descriptor use without bound.
_CUSTODY_ENTRY_LIMIT = 4 * (FIXED_TOTAL + 2)

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

# The original source identity seal.  It is written once, exclusively, under
# the owned phase directory before the first public submission and it binds the
# run, the candidate, the child authorization and the projection together with
# the original descriptor identity of all sixteen sources.  It is internal
# evidence, not a public product contract, and it changes no threshold, no
# denominator and no public schema.
SOURCE_PLAN_NAME = "qd-source-plan.json"
SOURCE_PLAN_SCHEMA_VERSION = "lvw.s3-quality-source-plan/1"
SOURCE_PLAN_ROW_KEYS = frozenset({
    "ordinal", "asset_id", "media_kind", "input_reference",
    "source_bytes", "source_sha256", "path", "identity",
})

# The permitted verdict overlay of the scoring entry point.
#
# The canonical receipt that is *actually published* on disk is the authority.
# A supplied receipt may only restrict that authority: it can downgrade a
# row, but it can never improve a verdict, it can never replace an actually
# observed execution fact and it can never turn an unknown published failure
# into a known one.
#
# These two sets are the *closed* enumeration of the fields in which a
# supplied document may differ from the published one.  Every other field of
# the published document is an actual execution fact - the run context, the
# counters, the baseline, the accounting, the assurances and the per row
# attempt, counter, artifact and observation content - and it has to be
# reproduced exactly.  The comparison is therefore exhaustive by
# construction: a fact that is not named here can never be forged, and a new
# fact that the execution starts to record is bound automatically.
#
# Monotone semantics of the overlay:
#   * ``execution_status`` / ``error_code`` / ``quality_status``: the
#     effective verdict is derived from the supplied *and* the published
#     document together.  A published unknown failure is never replaced by a
#     supplied known failure, and a published known failure is never upgraded
#     by a supplied pass.
#   * ``source_evidence`` / ``release_evidence`` / ``video_snapshot_residue``:
#     the evidence declarations.  A declaration only ever completes a row
#     when it is complete for the supplied document *and* for the published
#     document, when it reproduces the sealed original source descriptor and
#     when it is the published observation itself.  A missing, invalid or
#     contradicting declaration is unknown, never a pass.
#   * ``storage_unproven`` / ``cleanup_unproven``: the uncertainty flags.
#     The effective value is the stricter of the two documents.
#   * ``cleanup_diagnostics`` / ``stage``: the recorded diagnostics of the
#     failure.  They never decide a verdict.
QS_RECEIPT_OVERLAY_FIELDS = frozenset({
    "rows",
    "storage_unproven",
    "cleanup_unproven",
})
QS_ROW_OVERLAY_FIELDS = frozenset({
    "execution_status",
    "error_code",
    "quality_status",
    "source_evidence",
    "release_evidence",
    "video_snapshot_residue",
    "storage_unproven",
    "cleanup_unproven",
    "cleanup_diagnostics",
    "stage",
})

# The closed key sets of the two evidence declarations of one row.
#
# The source evidence and the release evidence are actual execution facts
# that a verdict depends on.  A caller may not extend them with an own
# fact: a declaration that carries a key outside these sets is malformed,
# and a malformed declaration is unknown - it is never a pass and it never
# silently completes a row.
#
# The release evidence may carry the optional native proof fields of the
# public release path.  They belong to the same bounded declaration and they
# are never an own fact of the caller.
QS_SOURCE_EVIDENCE_KEYS = frozenset({
    "path", "bytes", "sha256", "identity",
})
QS_RELEASE_EVIDENCE_KEYS = frozenset({
    "proven", "loaded_models", "elapsed_seconds", "baseline_gpu_mib",
    "gpu_samples",
    "run_token", "model", "owner_pid", "owner_start_ticks",
    "unload_acknowledged",
})
QS_GPU_SAMPLE_KEYS = frozenset({
    "monotonic_seconds", "gpu_used_mib",
})


def _is_typed_run_root(value):
    """A bound run root is a non empty path string."""
    return isinstance(value, str) and bool(value.strip())


def _is_typed_baseline(value):
    """A bound baseline is a non negative integer.  ``bool`` is not one."""
    return _is_int(value) and value >= 0


# The two bound contexts of the receipt.  A *mistyped* context is an invalid
# declaration, not a fact: the per row evidence validation makes the row
# unknown and the mistyped value is never compared and never accepted.  A
# *well typed* context is an actual execution fact and has to reproduce the
# canonical one exactly.
QS_RECEIPT_TYPED_CONTEXTS = {
    "run_root": _is_typed_run_root,
    "parent_budget_baseline_gpu_mib": _is_typed_baseline,
}

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
    "SOURCE_PLAN_PERSISTENCE_FAILED",
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
    "SOURCE_PLAN_PERSISTENCE_FAILED",
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


def _json_fact_equal(left, right):
    """Type aware equality of one JSON fact.

    Python's ``==`` accepts ``True == 1`` and ``1 == 1.0``, so a plain
    comparison of an authoritative fact would accept a boolean where the
    canonical document records an integer and an integer where it records
    a float.  An actual execution fact has to reproduce the canonical value
    *exactly*, including its JSON type:

    * a boolean is never an integer and never a float;
    * an integer is never a float;
    * the comparison recurses into nested objects and into the elements of
      a list, so a typed substitution inside a nested fact is a difference
      too.

    Only JSON facts are compared.  This is not a claim against arbitrary
    hostile Python objects and not a claim against a total forgery of the
    trusted originals.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if left is None or right is None:
        return left is None and right is None
    if _is_int(left) or _is_int(right):
        return _is_int(left) and _is_int(right) and left == right
    if isinstance(left, float) or isinstance(right, float):
        if not (isinstance(left, float) and isinstance(right, float)):
            return False
        return math.isfinite(left) and math.isfinite(right) and left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        if not (isinstance(left, list) and isinstance(right, list)):
            return False
        if len(left) != len(right):
            return False
        return all(_json_fact_equal(one, other) for one, other in zip(left, right))
    if isinstance(left, dict) or isinstance(right, dict):
        if not (isinstance(left, dict) and isinstance(right, dict)):
            return False
        if set(left) != set(right):
            return False
        return all(_json_fact_equal(left[key], right[key]) for key in left)
    # An object that is not a JSON fact is never an authoritative fact.
    return False


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
                              input_reference, run_root, sealed=None):
    """Validate one row's source evidence.

    The same pure validator is used by the execution phase and by the scoring
    entry point, so a row that the execution could not prove is unknown in
    both.  Missing, null or malformed evidence is unknown; it is never
    defaulted to a pass.

    The bound run root is a mandatory typed context: an absent, null, empty
    or non string context never disables the path binding.  When ``sealed``
    is supplied the evidence must additionally reproduce the sealed original
    descriptor identity, size and hash exactly.  The live source file is
    never re-stat'ed here and never has to be retained after the run.
    """
    if not isinstance(evidence, dict):
        return False, "SOURCE_EVIDENCE_MISSING"
    identity = evidence.get("identity")
    if (not isinstance(identity, list) or len(identity) != 5
            or any(not _is_int(value) or value < 0 for value in identity)):
        return False, "SOURCE_IDENTITY_INVALID"
    if sealed is not None:
        # The sealed original descriptor is the authority.  The evidence must
        # reproduce its identity, its size, its hash and its path exactly.
        if list(identity) != list(sealed.get("identity") or []):
            return False, "SOURCE_SEAL_IDENTITY_MISMATCH"
        if evidence.get("bytes") != sealed.get("source_bytes"):
            return False, "SOURCE_SEAL_BYTES_MISMATCH"
        if evidence.get("sha256") != sealed.get("source_sha256"):
            return False, "SOURCE_SEAL_HASH_MISMATCH"
        if evidence.get("path") != sealed.get("path"):
            return False, "SOURCE_SEAL_PATH_MISMATCH"
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
    if not isinstance(run_root, str) or not run_root:
        return False, "SOURCE_RUN_ROOT_INVALID"
    if Path(path) != Path(run_root) / "input" / input_reference:
        return False, "SOURCE_PATH_FOREIGN"
    if set(evidence) - QS_SOURCE_EVIDENCE_KEYS:
        # The declaration is closed: a key outside the closed set is an own
        # fact of the caller and never a proven observation.  A malformed
        # declaration is unknown, never a pass.
        return False, "SOURCE_EVIDENCE_UNEXPECTED_FIELD"
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
    # The bound baseline is a mandatory typed context: an absent, null,
    # floating point or boolean context never disables the baseline binding.
    if not _is_int(baseline_gpu_mib) or baseline_gpu_mib < 0:
        return False, "RELEASE_EVIDENCE_BASELINE_INVALID"
    if baseline != baseline_gpu_mib:
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
                 parent_budget, clock=None, sleep=None, progress_sink=None):
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
        # The optional progress sink of the S3 parent supervision.  It is
        # closed by default, so the accepted behaviour, the verification, the
        # scoring, the thresholds, the retention caps and the original
        # evidence of this phase stay exactly as they are.  A sink may only
        # observe; it never changes a result, a deadline or a sample.
        if progress_sink is not None and not callable(progress_sink):
            raise QualityContractError("QUALITY_PROGRESS_SINK_INVALID")
        self.progress_sink = progress_sink
        self._history_wait_emitted = set()
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
        self._source_plan = None
        # The original five component descriptor identity of every source,
        # retained in memory from the moment the exclusive seal was written.
        # The final bounded source verification of a row is made against this
        # sealed original identity, so a controlled accessor can never
        # invalidate the sealed source behind the final send admission.
        self._sealed_identities = {}

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
        if capacity > MAX_TOTAL_PROVIDER_CALLS:
            # The admitted capacity can never exceed the frozen provider call
            # ceiling: a proof that claims more is not a usable proof.
            raise QualityContractError("PARENT_BUDGET_CAPACITY_INVALID")
        self.parent_budget_capacity = capacity

    def _send_admission_guard(self, row, expected_calls):
        """The final local send-admission guard.

        It runs after every controlled preparation, authorization, source and
        driver callback and directly before the local reservation, the attempt
        charge and the submit itself, so nothing unchecked happens in
        between.  It revalidates the original ownership, and it takes exactly
        ONE final latest trusted monotonic sample.  That single sample decides
        the phase deadline *and* the parent proof interval, so a later clock
        read can never invalidate a deadline that was already checked.

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
        admission_error = self._parent_proof_is_fresh(now=now)
        if admission_error:
            raise QualityContractError(admission_error)
        admitted = min(self.parent_budget_capacity, MAX_TOTAL_PROVIDER_CALLS)
        if self._provider_calls_reserved + expected_calls > admitted:
            raise QualityContractError("PARENT_BUDGET_CAPACITY_INSUFFICIENT")

    def _parent_proof_is_fresh(self, now=None):
        """The proof must still be inside its validity interval.

        The caller may pass the one final clock sample it already took; then
        this function never reads the clock again.
        """
        try:
            self._validate_parent_proof(self.parent_budget)
        except QualityContractError as error:
            return str(error)
        if now is None:
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

    def _resolve_driver_state(self):
        """Resolve every controlled driver value before the final guard.

        The public submission counter, the public submission limit and the
        submit callable itself are read and bound *before* the final
        admission guard.  A dynamic accessor therefore cannot change the
        admitted capacity or the clock behind the back of the guard, and no
        ``getattr``, property, authorize, observer or clock read happens
        between the final admission and the send.
        """
        try:
            raw_submissions = getattr(self.driver, "submissions", 0)
            raw_limit = getattr(self.driver, "max_public_submissions", MAX_PUBLIC_SUBMISSIONS)
            submit = getattr(self.driver, "submit", None)
        except Exception as error:  # noqa: BLE001 - an unreadable driver state is a refusal
            raise QualityContractError("PUBLIC_SUBMISSION_STATE_UNAVAILABLE:"
                                       + type(error).__name__) from error
        if not _is_int(raw_submissions) or raw_submissions < 0:
            raise QualityContractError("PUBLIC_SUBMISSION_COUNT_INVALID")
        if not _is_int(raw_limit) or raw_limit < 0:
            raise QualityContractError("PUBLIC_SUBMISSION_LIMIT_INVALID")
        if not callable(submit):
            raise QualityContractError("QUALITY_DRIVER_PROTOCOL_INCOMPLETE:submit")
        return {"submissions": raw_submissions, "limit": raw_limit, "submit": submit}

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

    def _emit(self, event, payload):
        """Send one bounded progress fact to the optional progress sink.

        The sink is closed by default.  When it is open, it only observes:
        it cannot change a result, a deadline or a sample.  A failing sink is
        an explicit failure of the phase, never a silently dropped fact.
        """
        if self.progress_sink is None:
            return
        try:
            self.progress_sink(event, dict(payload))
        except QualityContractError:
            raise
        except Exception as error:  # noqa: BLE001 - the failure stays visible
            raise QualityContractError("PROGRESS_SINK_FAILED:" + type(error).__name__) from error

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

    def _validate_source(self, row, previous=None, sealed=None):
        """Re-derive one source file with a bounded read and a stable identity.

        The read never runs past the frozen byte count, so a file that grows
        while it is read is detected instead of being silently followed to EOF.
        The identity tuple proves the very same object is still in place, and
        the descriptor identity is compared with the path identity *after* the
        read, so a replacement during the read cannot pass unnoticed.

        When the sealed original identity is supplied, the observed identity
        must reproduce it exactly.  That is the identity that was written into
        the exclusive source seal before the first public submission, so a
        controlled accessor that changes the size, the mode or the timestamps
        of a prepared source is refused instead of being adopted.

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
        if sealed is not None and list(sealed) != self._identity(after):
            # The sealed original identity is the authority for this row.  A
            # source whose descriptor identity changed after the seal - a
            # replaced file, a changed size or changed timestamps - is refused
            # here and never certified by the final send admission.
            raise QualityContractError("SOURCE_REPLACED")
        if digest.hexdigest() != row["source_sha256"]:
            raise QualityContractError("SOURCE_HASH_MISMATCH")
        evidence = {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest(),
                    "identity": self._identity(after)}
        # The very same pure validator that the scoring entry point uses is
        # applied here, so the execution and the scoring can never disagree
        # about what a proven source looks like.
        valid, reason = validate_source_evidence(
            evidence,
            source_sha256=row["source_sha256"],
            source_bytes=row["source_bytes"],
            input_reference=row["input_reference"],
            run_root=str(self.root))
        if not valid:
            raise QualityContractError(reason)
        return evidence

    # -- source seal ----------------------------------------------------
    def _persist_source_plan(self, rows):
        """Seal the original source identity of all sixteen rows.

        The seal is written once, exclusively, under the owned phase
        directory, after the initial bounded source validation and before the
        first public submission.  It binds this run, candidate, child
        authorization and projection and records the original five component
        descriptor identity of every source file.

        Nothing here is fabricated: the identity is the one that the bounded
        read actually observed, and the file is written with the same
        exclusive, bounded and descriptor relative primitive as every other
        artifact.
        """
        document = {
            "schema_version": SOURCE_PLAN_SCHEMA_VERSION,
            "run_id": self.run_id,
            "candidate_sha": self.candidate_sha,
            "authorization_sha256": self.authorization_sha256,
            "projection_sha256": self.projection_sha256,
            "rows": [],
        }
        sealed_identities = {}
        for row in rows:
            evidence = row.get("source_evidence")
            if not isinstance(evidence, dict):
                raise QualityContractError("SOURCE_PLAN_EVIDENCE_MISSING")
            identity = evidence.get("identity")
            if (not isinstance(identity, list) or len(identity) != 5
                    or any(not _is_int(value) or value < 0 for value in identity)):
                raise QualityContractError("SOURCE_PLAN_IDENTITY_INVALID")
            document["rows"].append({
                "ordinal": row["ordinal"],
                "asset_id": row["asset_id"],
                "media_kind": row["media_kind"],
                "input_reference": row["input_reference"],
                "source_bytes": row["source_bytes"],
                "source_sha256": row["source_sha256"],
                "path": evidence.get("path"),
                "identity": list(identity),
            })
            sealed_identities[row["asset_id"]] = list(identity)
        raw = canonical_json(document).encode("utf-8")
        artifact = self._artifact(SOURCE_PLAN_NAME, raw)
        # The seal exists on disk now, so the original identities are retained
        # in memory as well: the final bounded source verification of every
        # row is made against this sealed original identity and never against
        # a value that a controlled accessor could have produced.
        self._sealed_identities = sealed_identities
        self._source_plan = {
            "path": artifact["path"],
            "bytes": artifact["bytes"],
            "sha256": artifact["sha256"],
            "schema_version": SOURCE_PLAN_SCHEMA_VERSION,
            "rows": len(document["rows"]),
        }
        return self._source_plan

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
            # same object, same hash, bounded read, and the same sealed
            # original identity that was written into the exclusive seal
            # before the first public submission.
            result["source_evidence"] = self._validate_source(
                row, previous=(row.get("source_evidence") or {}).get("identity"),
                sealed=self._sealed_identities.get(row["asset_id"]))
            graph, expected_node = self._build_graph(row, workflows)
            result["graph_sha256"] = sha256_bytes(canonical_json(graph).encode("utf-8"))
            stage = "submit"
            self._authorize("quality_public_submit", row["asset_id"])
            # Every controlled driver value and the submit callable itself are
            # resolved *before* the final bounded source verification, so a
            # dynamic accessor cannot change the admitted capacity, the clock
            # or the sealed source identity behind the final admission guard.
            driver_state = self._resolve_driver_state()
            if driver_state["submissions"] >= driver_state["limit"]:
                raise QualityContractError("PUBLIC_SUBMISSION_BUDGET_EXCEEDED")
            # The final bounded source verification against the sealed
            # ORIGINAL identity.  It happens after every controlled callback
            # and after every controlled accessor, so a source whose content,
            # identity or path changed in one of them produces zero sends and
            # zero charges for this row.
            result["source_evidence"] = self._validate_source(
                row, previous=result["source_evidence"]["identity"],
                sealed=self._sealed_identities.get(row["asset_id"]))
            # The final local send-admission guard: the original ownership,
            # the phase deadline and the exact typed parent proof with its
            # current remaining capacity.  Nothing unchecked happens between
            # this guard and the submit.
            self._send_admission_guard(row, expected_calls)
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
            prompt_id = driver_state["submit"](graph)
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
        # The history start is announced once per row and *before* the first
        # possibly blocking history wait, so the parent can fix the history
        # deadline of this row at its first announcement.  A repeated
        # announcement is not sent: it could only look like a deadline reset.
        if row["asset_id"] not in self._history_wait_emitted:
            self._history_wait_emitted.add(row["asset_id"])
            self._emit("HISTORY_WAIT_STARTED", {"asset_id": row["asset_id"],
                                                "ordinal": row["ordinal"],
                                                "prompt_id": prompt_id})
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
            "source_plan": copy.deepcopy(self._source_plan),
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
        # The publication bookkeeping of the staged entry is part of the
        # published document itself, so that the returned receipt and the
        # published document carry exactly the same fields.  A consumer can
        # therefore close the top level key set without an exception for the
        # two fields that the publication itself records.  The staged entry
        # holds exactly the published payload, so its length is the length of
        # the published receipt.
        document["staged_receipt_retained"] = True
        document["staged_receipt_bytes"] = 0
        document[RECEIPT_PADDING_KEY] = ""
        assumed = len(canonical_json(document).encode("utf-8")) + 64
        for _ in range(RECEIPT_FIXED_POINT_ITERATIONS):
            document["receipt_bytes"] = assumed
            document["staged_receipt_bytes"] = assumed
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

        # ---- the original source identity is sealed before the first send --
        # A seal that cannot be persisted is a storage failure: the batch
        # produces zero sends and all sixteen rows stay terminal.
        try:
            self._persist_source_plan(rows)
        except QualityContractError as error:
            code = error_base_code(error)
            self._storage_unproven = True
            for row in rows:
                row["execution_status"] = "BLOCKED"
                row["quality_status"] = QUALITY_NOT_RUN
                row["error_code"] = "SOURCE_PLAN_PERSISTENCE_FAILED"
                row["storage_unproven"] = True
            return self._finish(rows, "QUALITY_EXECUTION_BLOCKED",
                                {"error_code": "SOURCE_PLAN_PERSISTENCE_FAILED:" + code,
                                 "public_submissions": 0,
                                 "storage_unproven": True})

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
            self._emit("ROW_STARTED", {"asset_id": row["asset_id"],
                                       "ordinal": row["ordinal"],
                                       "media_kind": row["media_kind"]})
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
            self._emit("ROW_FINISHED", {"asset_id": outcome.get("asset_id"),
                                        "ordinal": outcome.get("ordinal"),
                                        "execution_status": outcome.get("execution_status"),
                                        "quality_status": outcome.get("quality_status"),
                                        "error_code": outcome.get("error_code")})
            self._emit("PROGRESS", {"rows_finished": len(results),
                                    "rows_total": len(rows),
                                    "public_submissions": self._submissions,
                                    "provider_calls_reserved": self._provider_calls_reserved})
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


def _close_owned_descriptor(descriptor):
    """Close one owned descriptor exactly once.

    The descriptor is closed here and it is closed nowhere else: the owner
    of a descriptor is always exactly one place, so a descriptor is never
    closed twice and a number that the operating system handed out again
    later is never closed by mistake.  A close that the operating system
    refuses is not retried - the descriptor is not valid any more and a
    second close could hit an unrelated descriptor.
    """
    try:
        os.close(descriptor)
    except OSError:
        pass


class _NamedCustody:
    """The bounded custody of every named entry that one evaluation consumed.

    The custody is owned by the boundary and it lives for the whole
    evaluation.  Every directory and every leaf that was opened for a read
    stays pinned, so the *current* name of an entry that was consumed long
    ago can still be compared with the very object that was actually read.

    A name is taken into the custody once.  A repeated read of the same name
    reuses the pinned descriptor instead of opening a second one, so the
    descriptor use of an evaluation is bounded by the number of *distinct*
    names it consumed and never by the number of reads it performed.

    The bound is internal and fail-closed: it is not a public threshold, it
    is not a platform limit and it is never widened to make a run pass.  An
    evaluation that would need more custody than the bound allows refuses.
    """

    def __init__(self, limit=_CUSTODY_ENTRY_LIMIT):
        self._limit = limit
        self._entries = {}
        self._fds = []
        self._reservations = {}

    def find(self, parent_fd, name):
        """The custody entry of one name below one pinned parent, if any."""
        return self._entries.get((parent_fd, str(name)))

    def reserve(self, parent_fd, name):
        """Reserve one custody slot before the entry is opened.

        The reservation is the *capacity* of the custody and not an entry:
        it holds no descriptor and it is taken **before** the descriptor of
        the name is opened.  A name that does not fit into the internal
        bound is therefore refused without opening anything at all, so the
        descriptor use of a refused evaluation never rises above the bound.

        A reservation is released again as soon as the open, the metadata
        validation or the insertion of the entry fails.  A refused
        reservation never consumes a slot and it never disables an entry
        that was taken earlier.
        """
        key = (parent_fd, str(name))
        if key in self._entries or key in self._reservations:
            return key
        if len(self._entries) + len(self._reservations) >= self._limit:
            raise QualityContractError(
                "QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:" + str(name))
        self._reservations[key] = True
        return key

    def release(self, reservation):
        """Give a reserved slot back; it was never consumed."""
        if reservation is not None:
            self._reservations.pop(reservation, None)

    def take(self, parent_fd, name, identity, kind, descriptor, reservation=None):
        """Take custody of one named entry and of its pinned descriptor.

        The caller hands the ownership of the descriptor over to this
        method: the descriptor is closed again when the name is already in
        the custody - the pinned descriptor of the first acquisition stays
        the only descriptor of that name - it is closed again when the
        custody refuses the name and it is transferred into the custody
        only when the entry was really inserted.  The descriptor is
        therefore closed exactly once on every refusal and it is never left
        behind.
        """
        key = (parent_fd, str(name))
        try:
            existing = self._entries.get(key)
            if existing is not None:
                _close_owned_descriptor(descriptor)
                return existing
            if reservation is None or reservation not in self._reservations:
                _close_owned_descriptor(descriptor)
                raise QualityContractError(
                    "QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:" + str(name))
            entry = {
                "parent_fd": parent_fd,
                "name": str(name),
                "identity": identity,
                "kind": kind,
                "fd": descriptor,
            }
            try:
                self._entries[key] = entry
                self._fds.append(descriptor)
            except BaseException:
                # The entry was not inserted: the custody does not own the
                # descriptor and it does not know the name either.
                self._entries.pop(key, None)
                _close_owned_descriptor(descriptor)
                raise
            return entry
        finally:
            self.release(reservation)

    def entries(self):
        """Every custody entry, in the order in which it was acquired."""
        return list(self._entries.values())

    def count(self):
        return len(self._entries)

    def reserved(self):
        """The number of slots that are reserved but not filled yet."""
        return len(self._reservations)

    def close(self):
        """Close every owned descriptor exactly once."""
        for descriptor in reversed(self._fds):
            _close_owned_descriptor(descriptor)
        self._fds = []
        self._entries = {}
        self._reservations = {}


class _ArtifactBoundary:
    """The strict artifact-root boundary of the scoring entry point.

    The run root, the ``temp`` directory and the phase directory are opened
    against their own pinned parent with ``O_DIRECTORY|O_NOFOLLOW``.  The
    trusted parent of the run root is pinned once, and every level is
    recorded as the triple ``(parent_fd, child_name, pinned identity)``.

    The recorded triple is not only checked when the entry is opened: the
    *current* named entry is verified with a no-follow, parent relative
    ``stat`` against the pinned handle and against the original identity -
    before a read, after a read and before a successful completion.  A
    renamed ancestor that was replaced by a symlink, by another directory or
    by another file is therefore refused even when the pinned descriptors
    would still read the original genuine bytes: the selected path has to
    keep naming the pinned hierarchy.

    The same rule applies to every directory and to the leaf that is opened
    for a read below the phase directory.  Nothing is ever resolved, adopted
    or followed away, and every descriptor that this boundary opens is
    closed again on the ordinary path and on every error path.

    Every successful open has exactly one owner from the very first
    ``os.open`` until the descriptor is closed: the level openers hand the
    descriptor to the boundary, the child and leaf openers own it until the
    metadata of the entry was validated and the custody has taken it over.
    A metadata error, a missing name, a wrong type, a replaced identity, a
    refused admission or a failed insertion therefore closes the descriptor
    exactly once, and a descriptor is never closed twice and never left
    behind outside the finite custody.

    The custody of the consumed names is *not* read-local.  Every directory
    and every leaf that this boundary opened for a read stays pinned in the
    boundary-owned ``_NamedCustody`` until the boundary is closed, so the
    current name of an entry that was consumed long ago is still compared
    with the very object that was actually read - before a later handoff and
    before a successful completion.  A canonical receipt, a source seal or a
    raw artifact that is renamed, replaced, redirected or removed after it
    was read therefore refuses the evaluation instead of being silently
    consumed.  The custody is bounded and deduplicated by name, so repeated
    reads cannot grow the descriptor use without bound.

    Every evidence type - the canonical receipt, the source seal and the raw
    artifacts - is read through this one boundary, so no evidence type can
    have a weaker ancestry rule than another.

    Accepted limitation: this is an in-process inode and name observation
    inside the existing audited Python/filesystem trust model.  It is a
    cooperative, finite observation.  It does not claim immunity against a
    hostile kernel, against a native Windows reparse point, against a
    filesystem that moves inodes underneath the process or against a
    universal concurrency guarantee.
    """

    def __init__(self, artifact_root):
        if isinstance(artifact_root, bool) or not isinstance(artifact_root, (str, os.PathLike)):
            raise QualityContractError("QS_ARTIFACT_ROOT_INVALID")
        literal = Path(artifact_root)
        if literal.name != "s3-quality" or literal.parent.name != "temp":
            raise QualityContractError("QS_ARTIFACT_ROOT_LOCATION_INVALID")
        self.run_root_path = literal.parent.parent
        self._fds = []
        self._levels = []
        self._custody = _NamedCustody()
        self._root_parent_fd = None
        try:
            self._root_parent_fd = self._open_trusted_parent(self.run_root_path.parent)
            self._run_fd, self.run_root_identity = self._open_directory(
                self.run_root_path.name, self._root_parent_fd)
            self._temp_fd, self._temp_identity = self._open_directory("temp", self._run_fd)
            self._phase_fd, self._phase_identity = self._open_directory(
                "s3-quality", self._temp_fd)
        except BaseException:
            self.close()
            raise

    # -- opening ---------------------------------------------------------
    def _open_trusted_parent(self, path):
        """Pin the trusted parent of the run root.

        The parent is the anchor of the trust model: it is opened as a
        directory and it is only ever used to open the run root *by name*.
        It is never used to resolve an artifact path and it never grants a
        fallback to an absolute path.
        """
        try:
            descriptor = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
        except OSError as error:
            if error.errno == errno.ENOENT:
                raise QualityContractError(
                    "QS_ARTIFACT_ROOT_MISSING:" + str(path)) from error
            raise QualityContractError(
                "QS_ARTIFACT_ROOT_UNAVAILABLE:" + str(path)) from error
        # The ownership of the descriptor is transferred to the boundary
        # here, before any metadata is read.  A transfer that fails must not
        # leave the descriptor behind.
        try:
            self._fds.append(descriptor)
        except BaseException:
            _close_owned_descriptor(descriptor)
            raise
        return descriptor

    def _open_directory(self, name, parent_fd):
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise QualityContractError(
                    "QS_ARTIFACT_ROOT_REDIRECT_FORBIDDEN:" + str(name)) from error
            if error.errno == errno.ENOENT:
                raise QualityContractError(
                    "QS_ARTIFACT_ROOT_MISSING:" + str(name)) from error
            raise QualityContractError(
                "QS_ARTIFACT_ROOT_UNAVAILABLE:" + str(name)) from error
        # The ownership of the descriptor is transferred to the boundary
        # here, before any metadata is read, so a metadata failure below can
        # never leave the descriptor behind.
        try:
            self._fds.append(descriptor)
        except BaseException:
            _close_owned_descriptor(descriptor)
            raise
        info = os.fstat(descriptor)
        identity = (info.st_dev, info.st_ino)
        # The entry is inspected relative to its pinned parent and without
        # following a symlink, so a replaced ancestor is detected instead of
        # being adopted.
        try:
            entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            raise QualityContractError(
                "QS_ARTIFACT_ROOT_MISSING:" + str(name)) from error
        if not stat.S_ISDIR(entry.st_mode):
            raise QualityContractError(
                "QS_ARTIFACT_ROOT_REDIRECT_FORBIDDEN:" + str(name))
        if (entry.st_dev, entry.st_ino) != identity:
            raise QualityContractError(
                "QS_ARTIFACT_ROOT_REPLACED:" + str(name))
        # The level is recorded so that the *named* entry can be verified
        # again against the pinned handle later on.
        self._levels.append({
            "fd": descriptor,
            "parent_fd": parent_fd,
            "name": str(name),
            "identity": identity,
        })
        return descriptor, identity

    def _open_child_directory(self, parent_fd, name):
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(name, flags, dir_fd=parent_fd)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise QualityContractError(
                    "SCORE_ARTIFACT_REDIRECT_FORBIDDEN:" + name) from error
            if error.errno == errno.ENOENT:
                raise QualityContractError(
                    "SCORE_ARTIFACT_MISSING:" + name) from error
            raise QualityContractError(
                "SCORE_ARTIFACT_UNAVAILABLE:" + name) from error
        # The descriptor is owned by this method from the very first
        # successful open until the custody has taken it over.  Every
        # failure below - a metadata error, a missing name, a wrong type or
        # a replaced identity - closes it exactly once and hands the
        # failure on unchanged.
        try:
            info = os.fstat(descriptor)
            identity = (info.st_dev, info.st_ino)
            try:
                entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError as error:
                raise QualityContractError(
                    "SCORE_ARTIFACT_MISSING:" + name) from error
            if (not stat.S_ISDIR(entry.st_mode)
                    or (entry.st_dev, entry.st_ino) != identity):
                raise QualityContractError(
                    "SCORE_ARTIFACT_REDIRECT_FORBIDDEN:" + name)
        except BaseException:
            _close_owned_descriptor(descriptor)
            raise
        return descriptor, identity

    def _open_leaf(self, parent_fd, name):
        try:
            descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                                 dir_fd=parent_fd)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise QualityContractError(
                    "SCORE_ARTIFACT_REDIRECT_FORBIDDEN:" + name) from error
            if error.errno == errno.ENOENT:
                raise QualityContractError(
                    "SCORE_ARTIFACT_MISSING:" + name) from error
            raise QualityContractError(
                "SCORE_ARTIFACT_UNAVAILABLE:" + name) from error
        # The descriptor is owned by this method from the very first
        # successful open until the custody has taken it over; see
        # ``_open_child_directory``.
        try:
            info = os.fstat(descriptor)
            identity = (info.st_dev, info.st_ino)
            try:
                entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except OSError as error:
                raise QualityContractError(
                    "SCORE_ARTIFACT_MISSING:" + name) from error
            if (not stat.S_ISREG(entry.st_mode)
                    or (entry.st_dev, entry.st_ino) != identity):
                raise QualityContractError(
                    "SCORE_ARTIFACT_REDIRECT_FORBIDDEN:" + name)
        except BaseException:
            _close_owned_descriptor(descriptor)
            raise
        return descriptor, identity

    # -- identity --------------------------------------------------------
    def _verify_named_entry(self, parent_fd, name, identity, kind, prefix):
        """The named entry must still be the very object that was pinned.

        The observation is a no-follow, parent relative ``stat``: it looks
        at the *current* directory entry and compares it with the pinned
        handle and with the identity that was recorded when the entry was
        opened.  A renamed entry that was replaced by a symlink, by another
        directory or by another file is refused here; it is never resolved,
        adopted or followed away.
        """
        try:
            entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as error:
            raise QualityContractError(prefix + "_MISSING:" + str(name)) from error
        if kind == "dir":
            if not stat.S_ISDIR(entry.st_mode):
                raise QualityContractError(prefix + "_REDIRECT_FORBIDDEN:" + str(name))
        elif not stat.S_ISREG(entry.st_mode):
            raise QualityContractError(prefix + "_REDIRECT_FORBIDDEN:" + str(name))
        if (entry.st_dev, entry.st_ino) != identity:
            raise QualityContractError(prefix + "_REPLACED:" + str(name))

    def verify(self):
        """Every level and every consumed name must still name the same object.

        The pinned handle of every level is checked against its own recorded
        identity and the *current* named entry is checked against the pinned
        handle, so a renamed ancestor that was replaced is refused instead
        of being adopted.

        The same rule is applied to every entry of the custody: a directory
        or a leaf that was consumed by an *earlier* read of this evaluation
        is verified here as well, so a name that stopped naming the pinned
        object after its read refuses the evaluation instead of being
        silently consumed.
        """
        for level in self._levels:
            descriptor = level["fd"]
            if descriptor is None:
                raise QualityContractError("QS_ARTIFACT_ROOT_UNAVAILABLE:" + level["name"])
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != level["identity"]:
                raise QualityContractError("QS_ARTIFACT_ROOT_REPLACED:" + level["name"])
            self._verify_named_entry(level["parent_fd"], level["name"], level["identity"],
                                     "dir", "QS_ARTIFACT_ROOT")
        for entry in self._custody.entries():
            self._verify_custody_entry(entry, "QS_ARTIFACT_CUSTODY")

    def _verify_custody_entry(self, entry, prefix):
        """One custody entry must still be the very object that was read.

        The pinned handle is compared with the recorded identity - so the
        handle is never a stale or reused descriptor - and the *current*
        named entry is compared with the same identity.  A missing entry, a
        symlink and a plain replacement are all refused; none of them is
        ever resolved, adopted or reopened as authority.
        """
        descriptor = entry["fd"]
        try:
            info = os.fstat(descriptor)
        except OSError as error:
            raise QualityContractError(
                prefix + "_UNAVAILABLE:" + entry["name"]) from error
        if (info.st_dev, info.st_ino) != entry["identity"]:
            raise QualityContractError(prefix + "_REPLACED:" + entry["name"])
        self._verify_named_entry(entry["parent_fd"], entry["name"], entry["identity"],
                                 entry["kind"], prefix)

    # -- custody ---------------------------------------------------------
    def _retain_directory(self, parent_fd, name):
        """Open one child directory and take custody of its name.

        A directory that is already in the custody is *reused*: its pinned
        descriptor is verified against its own recorded identity and against
        the current named entry before it is used again, and no second
        descriptor is opened.  The custody therefore never grows with the
        number of reads.

        A directory that is *not* in the custody gets its custody slot
        reserved **before** the descriptor is opened.  A name that does not
        fit into the internal bound is therefore refused without opening
        anything, and a failed open or a failed metadata validation gives
        the reserved slot back instead of consuming it.
        """
        entry = self._custody.find(parent_fd, name)
        if entry is not None:
            self._verify_custody_entry(entry, "SCORE_ARTIFACT")
            return entry["fd"], entry["identity"]
        reservation = self._custody.reserve(parent_fd, name)
        try:
            descriptor, identity = self._open_child_directory(parent_fd, name)
        except BaseException:
            self._custody.release(reservation)
            raise
        # The custody takes the ownership of the descriptor here: it closes
        # it on every refusal and it transfers it on success.
        entry = self._custody.take(parent_fd, name, identity, "dir", descriptor,
                                    reservation=reservation)
        return entry["fd"], entry["identity"]

    def _retain_leaf(self, parent_fd, name):
        """Open one leaf and take custody of its name.

        A leaf that is already in the custody is *reused* in the same way as
        a directory: the pinned descriptor is verified against the recorded
        identity and against the current named entry, and no second
        descriptor is opened.  The bytes are then read from the very object
        that was pinned before.

        The custody slot is reserved before the leaf is opened, so an
        excess leaf is refused without opening it at all.
        """
        entry = self._custody.find(parent_fd, name)
        if entry is not None:
            self._verify_custody_entry(entry, "SCORE_ARTIFACT")
            return entry["fd"], entry["identity"]
        reservation = self._custody.reserve(parent_fd, name)
        try:
            descriptor, identity = self._open_leaf(parent_fd, name)
        except BaseException:
            self._custody.release(reservation)
            raise
        # The custody takes the ownership of the descriptor here: it closes
        # it on every refusal and it transfers it on success.
        entry = self._custody.take(parent_fd, name, identity, "file", descriptor,
                                    reservation=reservation)
        return entry["fd"], entry["identity"]

    # -- reading ---------------------------------------------------------
    def read(self, relative, max_bytes):
        """Read one artifact below the phase directory, anchored and bounded.

        The read is descriptor relative: every directory level is opened
        against the pinned handle of its parent with
        ``O_DIRECTORY|O_NOFOLLOW`` and the file itself is opened against the
        pinned handle of its own directory.  Nothing is ever resolved, so a
        redirected ancestor can never be followed away.

        Every opened directory and the leaf itself are recorded in the
        boundary-owned custody as the quadruple ``(parent_fd, child_name,
        pinned identity, kind)``, and the current named entries are verified
        against them *while the handles are still held*.  A renamed or
        replaced entry is therefore refused even when the pinned descriptors
        would still read the original genuine bytes.

        The custody outlives this read: the very same names are verified
        again on every later handoff and before a successful completion, so
        an entry that is replaced *after* it was read refuses the evaluation
        as well.
        """
        if not isinstance(relative, str) or not relative:
            raise QualityContractError("SCORE_ARTIFACT_PATH_INVALID")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise QualityContractError("SCORE_ARTIFACT_PATH_INVALID")
        current = self._phase_fd
        chain = []
        for part in pure.parts[:-1]:
            descriptor, identity = self._retain_directory(current, part)
            chain.append((current, part, identity))
            current = descriptor
        descriptor, identity = self._retain_leaf(current, pure.parts[-1])
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise QualityContractError("SCORE_ARTIFACT_NOT_PLAIN_FILE")
        if info.st_size > max_bytes:
            raise QualityContractError("SCORE_ARTIFACT_TOO_LARGE")
        # The pinned descriptor is read from its own beginning: a reused
        # descriptor is never read from a stale offset.
        os.lseek(descriptor, 0, os.SEEK_SET)
        remaining = max_bytes + 1
        chunks = []
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        # The named entries are verified again while the handles are
        # still held: the leaf must still be this very file inside
        # its pinned directory and every directory level must still
        # be this very directory inside its pinned parent.
        self._verify_named_entry(current, pure.parts[-1], identity,
                                 "file", "SCORE_ARTIFACT")
        for parent, name, child_identity in chain:
            self._verify_named_entry(parent, name, child_identity,
                                     "dir", "SCORE_ARTIFACT")
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise QualityContractError("SCORE_ARTIFACT_TOO_LARGE")
        # The identity of the whole boundary is checked again after the read.
        self.verify()
        return raw

    def close(self):
        """Close every owned descriptor exactly once.

        The custody is closed first, so the pinned leaves and the pinned
        directories of the consumed names are released before the levels
        that anchor them.  The method is idempotent: a second call closes
        nothing again.
        """
        self._custody.close()
        for descriptor in reversed(self._fds):
            _close_owned_descriptor(descriptor)
        self._fds = []
        self._levels = []
        self._root_parent_fd = None
        self._run_fd = None
        self._temp_fd = None
        self._phase_fd = None


def _boundary_error_code(error, *, missing, redirect, too_large, unreadable):
    """Translate one boundary failure into the caller's own vocabulary."""
    code = str(error)
    if code.startswith("SCORE_ARTIFACT_PATH_INVALID"):
        return "SCORE_ARTIFACT_PATH_INVALID"
    if (code.startswith("SCORE_ARTIFACT_MISSING")
            or code.startswith("QS_ARTIFACT_ROOT_MISSING")
            or code.startswith("QS_ARTIFACT_CUSTODY_MISSING")):
        return missing
    if (code.startswith("SCORE_ARTIFACT_REDIRECT_FORBIDDEN")
            or code.startswith("SCORE_ARTIFACT_REPLACED")
            or code.startswith("QS_ARTIFACT_ROOT_REDIRECT_FORBIDDEN")
            or code.startswith("QS_ARTIFACT_ROOT_REPLACED")
            or code.startswith("QS_ARTIFACT_CUSTODY_REDIRECT_FORBIDDEN")
            or code.startswith("QS_ARTIFACT_CUSTODY_REPLACED")):
        return redirect
    if code.startswith("SCORE_ARTIFACT_TOO_LARGE"):
        return too_large
    return unreadable


def load_canonical_receipt(directory, *, max_bytes=MAX_ARTIFACT_BYTES, boundary=None):
    """Load the authoritative terminal receipt.

    Only the canonical name is authority.  A staged file, even with identical
    bytes, is explicitly non-authoritative and is rejected here, so an
    unpublished staging can never be consumed as a terminal receipt.

    The read is bounded: at most ``max_bytes`` bytes are accepted and at most
    ``max_bytes + 1`` bytes are ever read, so a huge or substituted file can
    never be pulled into the consumer.  The read is descriptor relative
    through the strict artifact boundary, so a redirected directory or a
    symlinked receipt is refused instead of being followed.
    """
    owned = None
    if boundary is None:
        boundary = owned = _ArtifactBoundary(directory)
    try:
        try:
            raw = boundary.read(CANONICAL_RECEIPT_NAME, max_bytes)
        except QualityContractError as error:
            code = _boundary_error_code(
                error, missing="CANONICAL_RECEIPT_ABSENT",
                redirect="CANONICAL_RECEIPT_REDIRECT_FORBIDDEN",
                too_large="CANONICAL_RECEIPT_TOO_LARGE",
                unreadable="CANONICAL_RECEIPT_UNREADABLE")
            raise QualityContractError(code + ":" + str(error)) from error
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
    finally:
        if owned is not None:
            owned.close()


def _verify_run_root_binding(declared, boundary):
    """The published run root must be this very run root.

    The declared path is compared literally first.  A different literal path
    is only accepted when it names the very same directory object; a
    redirected (symlinked) run root is never adopted.

    A literal equality is never a shortcut past the boundary verification:
    the pinned hierarchy is verified in both branches, so a run root that was
    renamed and replaced between the construction of the boundary and this
    check is refused here as well.
    """
    literal = Path(declared)
    if literal == boundary.run_root_path:
        boundary.verify()
        return
    try:
        entry = os.lstat(str(literal))
    except OSError as error:
        raise QualityContractError("QS_CANONICAL_RECEIPT_RUN_ROOT_INVALID") from error
    if not stat.S_ISDIR(entry.st_mode):
        raise QualityContractError("QS_CANONICAL_RECEIPT_RUN_ROOT_REDIRECTED")
    if (entry.st_dev, entry.st_ino) != boundary.run_root_identity:
        raise QualityContractError("QS_CANONICAL_RECEIPT_RUN_ROOT_MISMATCH")
    boundary.verify()


def load_published_execution_receipt(artifact_root, *, boundary=None):
    """Load the *actually published* canonical receipt of this artifact root.

    A consumer may never trust the publication flags that a caller supplies
    in memory.  This loader reads the real canonical document from the real
    artifact root and refuses everything that is not authority: a missing, a
    corrupt, a staged-only or a foreign document, a redirected directory and
    a root that is not the actual ``<run root>/temp/s3-quality`` location of
    this run.

    The strict artifact boundary is established first: the run root, the
    ``temp`` directory and the phase directory must all be real directories
    of this run.  A renamed ancestor that was replaced by a symlink is
    refused here and never resolved away.
    """
    owned = None
    if boundary is None:
        boundary = owned = _ArtifactBoundary(artifact_root)
    try:
        document = load_canonical_receipt(artifact_root, boundary=boundary)
        if document.get("kind") != QD_RECEIPT_KIND:
            raise QualityContractError("QS_CANONICAL_RECEIPT_KIND_INVALID")
        run_root = document.get("run_root")
        if not isinstance(run_root, str) or not run_root:
            raise QualityContractError("QS_CANONICAL_RECEIPT_RUN_ROOT_INVALID")
        _verify_run_root_binding(run_root, boundary)
        return document
    finally:
        if owned is not None:
            owned.close()


def _verify_seal_row_alignment(sealed, canonical, index):
    """One sealed row must describe the very same canonical execution row.

    The seal binds the original source identity of the sixteen rows.  Every
    label of a sealed row - the ordinal, the asset, the media kind, the
    input reference, the size, the hash, the path and the full five
    component descriptor identity - must reproduce the corresponding
    canonical execution row.  A seal that contradicts the execution row it
    claims to seal can never certify that row, even when its own artifact
    hash and length binding is consistent.
    """
    for field in ("ordinal", "asset_id", "media_kind", "input_reference",
                  "source_bytes", "source_sha256"):
        if not _json_fact_equal(sealed.get(field), canonical.get(field)):
            raise QualityContractError(
                "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:" + field + ":" + str(index))
    evidence = canonical.get("source_evidence")
    if not isinstance(evidence, dict):
        raise QualityContractError(
            "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:source_evidence:" + str(index))
    if not _json_fact_equal(sealed.get("identity"), evidence.get("identity")):
        raise QualityContractError(
            "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:identity:" + str(index))
    if not _json_fact_equal(sealed.get("path"), evidence.get("path")):
        raise QualityContractError(
            "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:path:" + str(index))


def load_source_plan(artifact_root, receipt, *, boundary=None):
    """Load and verify the sealed original source plan.

    The seal is read from the same owned artifact root as the canonical
    receipt, through the same strict artifact boundary.  Its actual bytes
    must match the length and the hash that the receipt binds, its binding
    must be this run, and its sixteen ordered rows must reproduce the
    original source descriptors *and* the corresponding canonical execution
    rows.  The live source media is never re-stat'ed and never has to be
    retained after the run.
    """
    binding = receipt.get("source_plan")
    if not isinstance(binding, dict):
        raise QualityContractError("QS_SOURCE_PLAN_MISSING")
    relative = binding.get("path")
    if not isinstance(relative, str) or not relative:
        raise QualityContractError("QS_SOURCE_PLAN_PATH_INVALID")
    owned = None
    if boundary is None:
        boundary = owned = _ArtifactBoundary(artifact_root)
    try:
        try:
            raw = boundary.read(relative, MAX_ARTIFACT_BYTES)
        except QualityContractError as error:
            code = _boundary_error_code(
                error, missing="QS_SOURCE_PLAN_MISSING",
                redirect="QS_SOURCE_PLAN_REDIRECT_FORBIDDEN",
                too_large="QS_SOURCE_PLAN_TOO_LARGE",
                unreadable="QS_SOURCE_PLAN_UNREADABLE")
            raise QualityContractError(code + ":" + str(error)) from error
    finally:
        if owned is not None:
            owned.close()
    if not _is_int(binding.get("bytes")) or len(raw) != binding["bytes"]:
        raise QualityContractError("QS_SOURCE_PLAN_LENGTH_MISMATCH")
    if sha256_bytes(raw) != binding.get("sha256"):
        raise QualityContractError("QS_SOURCE_PLAN_HASH_MISMATCH")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QualityContractError("QS_SOURCE_PLAN_UNREADABLE") from error
    if not isinstance(document, dict):
        raise QualityContractError("QS_SOURCE_PLAN_UNREADABLE")
    if document.get("schema_version") != SOURCE_PLAN_SCHEMA_VERSION:
        raise QualityContractError("QS_SOURCE_PLAN_SCHEMA_INVALID")
    for key in ("run_id", "candidate_sha", "authorization_sha256", "projection_sha256"):
        if document.get(key) != receipt.get(key):
            raise QualityContractError("QS_SOURCE_PLAN_BINDING_MISMATCH:" + key)
    rows = document.get("rows")
    if not isinstance(rows, list) or len(rows) != FIXED_TOTAL:
        raise QualityContractError("QS_SOURCE_PLAN_ROW_COUNT_INVALID")
    published_rows = receipt.get("rows")
    if not isinstance(published_rows, list) or len(published_rows) != FIXED_TOTAL:
        raise QualityContractError("QS_SOURCE_PLAN_ROW_COUNT_INVALID")
    # The fixed admitted order of the canonical execution rows: the ordinals
    # are the frozen ones and every asset appears exactly once.
    seen_assets = set()
    for index, canonical in enumerate(published_rows):
        if not _is_int(canonical.get("ordinal")) or canonical.get("ordinal") != index + 1:
            raise QualityContractError(
                "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:ordinal:" + str(index))
        asset_id = canonical.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id or asset_id in seen_assets:
            raise QualityContractError(
                "QS_SOURCE_PLAN_ROW_ALIGNMENT_MISMATCH:asset_id:" + str(index))
        seen_assets.add(asset_id)
    sealed = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != SOURCE_PLAN_ROW_KEYS:
            raise QualityContractError("QS_SOURCE_PLAN_ROW_INVALID")
        if not _is_int(row.get("ordinal")) or row.get("ordinal") != index + 1:
            raise QualityContractError("QS_SOURCE_PLAN_ORDER_INVALID")
        identity = row.get("identity")
        if (not isinstance(identity, list) or len(identity) != 5
                or any(not _is_int(value) or value < 0 for value in identity)):
            raise QualityContractError("QS_SOURCE_PLAN_IDENTITY_INVALID")
        if not _is_int(row.get("source_bytes")) or row["source_bytes"] <= 0:
            raise QualityContractError("QS_SOURCE_PLAN_BYTES_INVALID")
        if not _is_hex(row.get("source_sha256"), 64):
            raise QualityContractError("QS_SOURCE_PLAN_HASH_INVALID")
        if not isinstance(row.get("path"), str) or not row["path"]:
            raise QualityContractError("QS_SOURCE_PLAN_PATH_INVALID")
        _verify_seal_row_alignment(row, published_rows[index], index)
        sealed.append(row)
    return sealed


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


def _row_evidence_complete(row, receipt, *, sealed=None, canonical=None):
    """Validate the source, storage and cleanup evidence of one row.

    Every row is checked, whether its execution passed or failed.  The same
    pure validators that the execution phase uses are applied here, so a row
    that the execution could not prove is unknown in both.  A missing, null
    or malformed declaration is unknown: the uncertainty flags must be the
    literal boolean False, and nothing is ever defaulted to a pass.

    When the sealed original source descriptor is supplied, the evidence must
    reproduce it exactly: the full five component identity, the size and the
    hash.  The live source file is never re-stat'ed here.

    When the canonical row is supplied, the release proof of this row must be
    the release proof that the canonical document actually recorded.  The
    release proof is an observation - a bounded GPU sample vector, a bound
    baseline and an elapsed time - and a well typed but different observation
    is a fabricated observation, never a proof.
    """
    valid, reason = validate_source_evidence(
        row.get("source_evidence"),
        source_sha256=row.get("source_sha256"),
        source_bytes=row.get("source_bytes"),
        input_reference=row.get("input_reference"),
        run_root=receipt.get("run_root"),
        sealed=sealed)
    if not valid:
        return False, reason
    valid, reason = validate_release_evidence(
        row.get("release_evidence"),
        baseline_gpu_mib=receipt.get("parent_budget_baseline_gpu_mib"))
    if not valid:
        return False, reason
    release = row.get("release_evidence")
    if set(release) - QS_RELEASE_EVIDENCE_KEYS:
        # The declaration is closed: a key outside the closed set is an own
        # fact of the caller.  A malformed declaration is unknown.
        return False, "RELEASE_EVIDENCE_UNEXPECTED_FIELD"
    for sample in release.get("gpu_samples") or []:
        if set(sample) - QS_GPU_SAMPLE_KEYS:
            return False, "RELEASE_EVIDENCE_GPU_SAMPLES_INVALID"
    if canonical is not None:
        # The two evidence declarations of the supplied row must be the
        # observations that the published document actually recorded.  The
        # comparison is type aware: a boolean is never an integer and an
        # integer is never a float, so a typed substitution inside a nested
        # fact is a difference too.
        if not _json_fact_equal(release, canonical.get("release_evidence")):
            return False, "RELEASE_EVIDENCE_NOT_CANONICAL"
        if not _json_fact_equal(row.get("source_evidence"), canonical.get("source_evidence")):
            return False, "SOURCE_EVIDENCE_NOT_CANONICAL"
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


def _verify_published_binding(supplied, published):
    """The supplied receipt must be bound to the actually published document.

    A consumer may not score a document that belongs to another run, another
    candidate, another child authorization, another projection or another
    row set.  The publication flags that the caller supplies in memory are
    never authority; the published document is.
    """
    for key in ("run_id", "candidate_sha", "authorization_sha256", "projection_sha256"):
        if supplied.get(key) != published.get(key):
            raise QualityContractError("QS_EXECUTION_RECEIPT_BINDING_MISMATCH:" + key)
    if supplied.get("fixed_denominator") != published.get("fixed_denominator"):
        raise QualityContractError("QS_EXECUTION_RECEIPT_BINDING_MISMATCH:fixed_denominator")
    supplied_rows = supplied.get("rows")
    published_rows = published.get("rows")
    if not isinstance(supplied_rows, list) or not isinstance(published_rows, list):
        raise QualityContractError("QS_EXECUTION_RECEIPT_BINDING_MISMATCH:rows")
    if [row.get("asset_id") for row in supplied_rows] != [row.get("asset_id") for row in published_rows]:
        raise QualityContractError("QS_EXECUTION_RECEIPT_BINDING_MISMATCH:rows")


def _verify_execution_content(supplied, published):
    """The supplied execution content must reproduce the published document.

    Every field of the published document that is not part of the closed
    verdict overlay is an actual execution fact: the run context, the
    counters, the bound baseline, the accounting, the recorded assurances,
    the source seal binding and every per row attempt, counter, artifact and
    observation content.  Such a fact has to be identical in the supplied
    receipt and in the actually published canonical document.  A mismatch
    means the supplied document is not the published one and the whole
    verdict is refused.

    The comparison is exhaustive over the published document: a fact that is
    not named in the overlay can never be forged, and a fact that the
    execution starts to record later is bound automatically.  A supplied row
    may not even carry an extra fact that the published row does not have.

    The comparison is *type aware*: a fact has to reproduce the canonical
    value exactly, including its JSON type.  Python's ``==`` would accept a
    boolean where the canonical document records an integer and an integer
    where it records a float; an authoritative fact may not be substituted
    that way, neither at the top level nor inside a nested fact.

    The key sets are closed on both levels: the supplied document may not
    carry a field that the published document does not have, and the
    supplied row may not carry a field that the published row does not have.
    The only fields in which the two may differ are the closed verdict
    overlay and the evidence declarations inside it, and those declarations
    have their own closed key sets.

    The verdict fields themselves are deliberately *not* compared here: they
    are evaluated for both documents together, so that a forged verdict can
    only ever make a row stricter, never usable.
    """
    extra = sorted(set(supplied) - set(published) - QS_RECEIPT_OVERLAY_FIELDS)
    if extra:
        raise QualityContractError("QS_EXECUTION_CONTENT_MISMATCH:" + extra[0])
    for field, value in published.items():
        if field in QS_RECEIPT_OVERLAY_FIELDS:
            continue
        typed = QS_RECEIPT_TYPED_CONTEXTS.get(field)
        if typed is not None and not typed(supplied.get(field)):
            # A mistyped bound context is an invalid declaration, not a fact.
            # The per row evidence validation makes every row unknown, so the
            # mistyped value is never compared and never accepted.
            continue
        if field not in supplied or not _json_fact_equal(supplied[field], value):
            raise QualityContractError("QS_EXECUTION_CONTENT_MISMATCH:" + field)
    supplied_rows = supplied.get("rows") or []
    published_rows = published.get("rows") or []
    for index, published_row in enumerate(published_rows):
        supplied_row = supplied_rows[index]
        for field, value in published_row.items():
            if field in QS_ROW_OVERLAY_FIELDS:
                continue
            if field not in supplied_row or not _json_fact_equal(supplied_row[field], value):
                raise QualityContractError(
                    "QS_EXECUTION_CONTENT_MISMATCH:" + field + ":"
                    + str(published_row.get("asset_id")))
        extra = sorted(set(supplied_row) - set(published_row) - QS_ROW_OVERLAY_FIELDS)
        if extra:
            raise QualityContractError(
                "QS_EXECUTION_CONTENT_MISMATCH:" + extra[0] + ":"
                + str(published_row.get("asset_id")))


def _effective_failure_verdict(supplied_row, published_row):
    """The effective verdict of one row, derived from both documents.

    The canonical document is the authority.  A supplied document may only be
    stricter, so the resolution of a failure is decided conservatively from
    the published *and* the supplied state and error:

    * a published failure is never replaced by a supplied pass;
    * a published unknown failure is never resolved by a supplied known
      failure - the canonical error stays unknown;
    * a published pass that is downgraded by a supplied known failure keeps
      the existing resolved but not usable obligation;
    * a published known failure that is supplied as a pass stays resolved
      and never usable.

    The returned tuple is the effective execution status, the effective error
    code and whether the failure is a *known* ordinary failure at all.
    """
    supplied_status = supplied_row.get("execution_status")
    published_status = published_row.get("execution_status")
    supplied_failed = supplied_status != "PASS"
    published_failed = published_status != "PASS"
    if not supplied_failed and not published_failed:
        return "PASS", None, False
    if published_failed and not supplied_failed:
        # The canonical failure is the verdict; a supplied pass cannot hide it.
        error = published_row.get("error_code")
        known = error_base_code(error or "") in KNOWN_EXECUTION_FAILURE_CODES
        return "FAIL", error, known
    if supplied_failed and not published_failed:
        # The canonical pass is downgraded by the supplied document.  The
        # downgrade only resolves when it names a known ordinary failure.
        error = supplied_row.get("error_code")
        known = error_base_code(error or "") in KNOWN_EXECUTION_FAILURE_CODES
        return "FAIL", error, known
    # Both documents record a failure.  The failure is known only when both
    # of them name a known ordinary failure: an unknown canonical error is
    # never resolved by a known supplied error.
    published_error = published_row.get("error_code")
    supplied_error = supplied_row.get("error_code")
    published_known = error_base_code(published_error or "") in KNOWN_EXECUTION_FAILURE_CODES
    supplied_known = error_base_code(supplied_error or "") in KNOWN_EXECUTION_FAILURE_CODES
    return "FAIL", published_error, published_known and supplied_known


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

    # ---- the strict artifact boundary of this run ----------------------
    # The run root, the temp directory and the phase directory are opened
    # once, without following a redirect, and every evidence type below is
    # read through that one boundary.
    boundary = _ArtifactBoundary(artifact_root)
    try:
        # ---- the actually published document is the authority -----------
        # A missing, corrupt, foreign, staged-only or redirected canonical
        # receipt is refused here, before any score is looked at.
        published = load_published_execution_receipt(artifact_root, boundary=boundary)
        _verify_published_binding(execution_receipt, published)
        published_rows = published.get("rows")
        if not isinstance(published_rows, list) or len(published_rows) != FIXED_TOTAL:
            raise QualityContractError("QS_ROW_COUNT_INVALID")
        # ---- the sealed original source identity is loaded from the same root
        # and is cross-checked against the canonical execution rows.
        sealed_rows = load_source_plan(artifact_root, published, boundary=boundary)
        result = _recompute_bound_scores(
            execution_receipt, published, published_rows, sealed_rows, boundary,
            score_receipts, independence=independence,
            implementer_identity=implementer_identity)
        # The pinned hierarchy is verified once more before the verdict is
        # returned: a run root, a temp directory or a phase directory that
        # was renamed and replaced while the evidence was read never yields
        # a successful completion.
        boundary.verify()
        return result
    finally:
        boundary.close()


def _recompute_bound_scores(execution_receipt, published, published_rows, sealed_rows,
                            boundary, score_receipts, *, independence=None,
                            implementer_identity=None):
    """The scoring of the sixteen bound rows inside the strict boundary.

    The caller has already established the strict artifact boundary, loaded
    the actually published canonical document and loaded the sealed original
    source plan.  This function is the pure validation and aggregation part:
    it never executes a model, never matches keywords and never invents a
    semantic judgement.
    """
    rows = execution_receipt.get("rows")
    run_id = execution_receipt.get("run_id")
    candidate_sha = execution_receipt.get("candidate_sha")
    projection_sha256 = execution_receipt.get("projection_sha256")

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
    for index, row in enumerate(rows):
        asset_id = row["asset_id"]
        media_kind = row.get("media_kind")
        published_row = published_rows[index]
        sealed_row = sealed_rows[index]
        effective_status, effective_error, failure_known = _effective_failure_verdict(
            row, published_row)
        entry = {
            "asset_id": asset_id,
            "media_kind": media_kind,
            "execution_status": effective_status,
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
        execution_passed = effective_status == "PASS"
        # The evidence must be complete for the supplied document *and* for
        # the actually published document, and it must reproduce the sealed
        # original source descriptor in both.  A declaration that is only
        # favourable in the supplied dictionary can never complete a row, and
        # a release proof that is not the published observation can never
        # complete a row either.
        supplied_complete, supplied_reason = _row_evidence_complete(
            row, execution_receipt, sealed=sealed_row, canonical=published_row)
        published_complete, published_reason = _row_evidence_complete(
            published_row, published, sealed=sealed_row)
        evidence_complete = supplied_complete and published_complete
        evidence_reason = supplied_reason or published_reason
        cleanup_proven = evidence_complete
        entry["cleanup_proven"] = cleanup_proven
        entry["evidence_complete"] = evidence_complete
        entry["evidence_reason"] = evidence_reason
        # The raw evidence is verified for every applicable row: a row with an
        # independent score must have a preserved raw whose hash *and* byte
        # length match both the execution record and the scoring record.
        raw = None
        if row.get("raw_preserved") is True and row.get("raw_artifact"):
            # The raw is read through the same strict boundary as the
            # canonical receipt and the seal, so a redirected ancestor can
            # never serve a different artifact.
            try:
                raw = boundary.read(row.get("raw_artifact"), MAX_ARTIFACT_BYTES)
            except QualityContractError as error:
                code = _boundary_error_code(
                    error, missing="QS_RAW_ARTIFACT_UNREADABLE",
                    redirect="QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN",
                    too_large="QS_RAW_ARTIFACT_TOO_LARGE",
                    unreadable="QS_RAW_ARTIFACT_UNREADABLE")
                raise QualityContractError(code + ":" + asset_id + ":" + str(error)) from error
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
            if failure_known and evidence_complete:
                entry["resolved"] = True
                entry["reason"] = "KNOWN_EXECUTION_FAILURE_RESOLVED_NOT_USABLE"
            elif not evidence_complete:
                entry["resolved"] = False
                entry["reason"] = "EVIDENCE_UNKNOWN:" + str(evidence_reason)
            else:
                entry["resolved"] = False
                entry["reason"] = "UNKNOWN_EXECUTION_FAILURE"
        computed.append(entry)

    # ---- the supplied execution content must be the published content ---
    # This runs after the per row verification, so a malformed artifact or a
    # wrong raw length is reported with its own precise reason first.
    _verify_execution_content(execution_receipt, published)

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
            "canonical_document_is_the_authority": True,
            "supplied_receipt_may_only_restrict": True,
            "verdict_overlay_fields": sorted(QS_RECEIPT_OVERLAY_FIELDS | QS_ROW_OVERLAY_FIELDS),
            "published_unknown_failure_is_never_resolved_by_a_supplied_known_error": True,
            "failed_row_with_verified_raw": (
                "The independent score identity, raw hash and raw length are validated and its "
                "critical findings contribute to the global total. The row stays a quality FAIL. "
                "A known ordinary refusal or structure failure with verified raw and proven "
                "cleanup is resolved without being usable. The known failure is decided from the "
                "published and the supplied document together: a published unknown failure is "
                "never resolved by a supplied known error."),
            "unknown_source_storage_cleanup_or_review": (
                "Cannot aggregate PASS. A missing raw or a missing review is not a known zero "
                "critical count."),
            "authority": "reports/v0-s3/product-gate0/p3b-correction-01.adjudication.json",
            "aggregate_correction_authority": (
                "reports/v0-s3/product-gate0/p3b-correction-05.adjudication.json"),
        },
        "limitations": [
            "Four sampled frames cannot prove full motion continuity or physical camera movement.",
            "Semantic judgements come only from the independent scoring receipts.",
            "The supplied reviewer identities are a schema and binding check; genuine independent "
            "provenance remains parent coordinator evidence.",
            "This verdict covers only the bound sixteen rows of this run.",
            "The artifact boundary is an in-process inode observation of the existing audited "
            "Python/filesystem trust model. It does not claim immunity against a hostile kernel, "
            "against a native Windows reparse point or against a filesystem that moves inodes "
            "underneath the process.",
            "Before a real consumer run the parent has to bind the selected owned archive or root "
            "to the retained original artifacts or an independent attestation. That integration is "
            "not proven by this component.",
        ],
        "stage_pass_claim": False,
        "product_gate0": False,
        "scoring_source": "INDEPENDENT_SCORING_RECEIPTS_ONLY",
        "model_called": False,
        "keyword_scoring": False,
        "automatic_semantic_scoring": False,
        "frame_continuity_claimed": False,
    }
