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

Driver protocol (implemented by the future production driver and by the bounded
synthetic driver used by the offline tests)::

    driver.submit(graph) -> prompt_id
    driver.chat_log_snapshot() -> {'raw_log','chat_calls','source_log_bytes','source_log_sha256'}
    driver.resource_observer() -> None
    driver._json_request(url, *, payload=None, timeout=..., observer=...) -> (status, value)
    driver.owned_listener_birth(port) -> {'pid','start_ticks','name', ...}
    driver.release_resources(kind, binding, reference) -> release evidence
    driver.submissions -> int
    driver.max_public_submissions -> int

The phase validates every one of those facts itself.  A driver cannot assert a
pass by returning a favourable string: the phase recomputes the provider chat
count from the raw log bytes, re-reads every persisted artifact, and re-hashes
every source file.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import time
from pathlib import Path, PurePosixPath

from tools.v0_s2_cancel_evidence import count as provider_chat_count
from tools.v0_s2_checkpoint_oracles import EvidenceError, public_video_oracle
from tools.v0_s2_measurements import spec_validator

ROOT = Path(__file__).resolve().parents[1]
COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_DIR = ROOT / "LVW_V0_RuntimePatch" / "workflows"
IMAGE_WORKFLOW = "image_reverse_prompt_v0.api.json"
VIDEO_WORKFLOW = "video_reverse_prompt_v0.api.json"
LEGACY_GRAPH_HELPERS = ROOT / "reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py"

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

MODEL_TAG = "gemma4:26b"
PROMPT_MODE = "realistic"
PROMPT_USER_INSTRUCTION = ""
PROMPT_TIMEOUT_SECONDS = 120

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})

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


def load_projection_bytes(path) -> bytes:
    """Read the frozen projection file as exact bytes.

    The caller binds the returned bytes to the registered SHA; this helper never
    parses or relaxes the projection.
    """
    raw = Path(path).read_bytes()
    return raw


_GRAPH_HELPERS = None


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


class QualityPhase:
    """QD: fixed sixteen-row public quality execution.

    The phase owns no process, no budget and no ledger.  The parent owns the
    real profile, the model digest, the media staging, the child authorization,
    the single GPU, the original process ownership and the later archive.
    """

    def __init__(self, driver, run_root, *, run_id, candidate_sha, authorization_sha256,
                 projection, projection_sha256, source_identity, authorize, binding=None,
                 clock=None, sleep=None):
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

        for name in ("submit", "chat_log_snapshot", "owned_listener_birth", "release_resources"):
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
        self._provider_calls = 0
        self._submissions = 0
        self._artifact_bytes = 0
        self._artifact_files = 0
        self._halted = False
        self._halt_reason = None

    # -- projection ------------------------------------------------------
    def _parse_projection(self):
        """Validate the frozen projection structure.  Raises on any deviation."""
        try:
            document = json.loads(self.projection_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise QualityContractError("PROJECTION_NOT_JSON") from error
        if not isinstance(document, dict):
            raise QualityContractError("PROJECTION_NOT_OBJECT")
        if document.get("schema_version") != PROJECTION_SCHEMA_VERSION:
            raise QualityContractError("PROJECTION_SCHEMA_VERSION_INVALID")
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

    def _validate_source(self, row):
        """Stream one source file and re-derive its size and SHA."""
        path = self._source_path(row["input_reference"])
        size = path.stat().st_size
        if size != row["source_bytes"]:
            raise QualityContractError("SOURCE_SIZE_MISMATCH")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(SOURCE_READ_CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
        if digest.hexdigest() != row["source_sha256"]:
            raise QualityContractError("SOURCE_HASH_MISMATCH")
        return {"path": str(path), "bytes": size, "sha256": digest.hexdigest()}

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
        """Persist one artifact under the owned phase directory."""
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise QualityContractError("ARTIFACT_TOO_LARGE:" + relative)
        if self._artifact_files + 1 > MAX_ARTIFACT_FILES:
            raise QualityContractError("ARTIFACT_FILE_BUDGET_EXCEEDED")
        if self._artifact_bytes + len(raw) > MAX_TOTAL_ARTIFACT_BYTES:
            raise QualityContractError("ARTIFACT_TOTAL_BUDGET_EXCEEDED")
        target = self.directory / relative
        resolved_parent = target.parent
        if resolved_parent.is_symlink():
            raise QualityContractError("ARTIFACT_REDIRECT_FORBIDDEN")
        resolved_parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self._artifact_files += 1
        self._artifact_bytes += len(raw)
        return {"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)}

    # -- provider --------------------------------------------------------
    def _provider_snapshot(self, label):
        self.authorize("quality_provider_" + label, self.run_id)
        self.driver.resource_observer()
        snapshot = self.driver.chat_log_snapshot()
        observed = provider_chat_count(snapshot)
        if not isinstance(snapshot.get("raw_log"), str):
            raise QualityContractError("PROVIDER_SNAPSHOT_INVALID")
        return {
            "label": label,
            "raw_log": snapshot["raw_log"],
            "chat_calls": observed,
            "source_log_bytes": snapshot["source_log_bytes"],
            "source_log_sha256": snapshot["source_log_sha256"],
        }

    def _listener_identity(self):
        identity = {}
        for port in (8191, 11434):
            proof = self.driver.owned_listener_birth(port)
            if (not isinstance(proof, dict) or not _is_int(proof.get("pid")) or proof["pid"] <= 0
                    or not _is_int(proof.get("start_ticks")) or proof["start_ticks"] <= 0):
                raise QualityContractError("LISTENER_IDENTITY_INVALID")
            identity[str(port)] = {"pid": proof["pid"], "start_ticks": proof["start_ticks"]}
        return identity

    # -- release ---------------------------------------------------------
    def _release_evidence(self, row):
        """Require proven release evidence; never fabricate a release marker."""
        evidence = self.driver.release_resources(row["media_kind"], self.binding, row["input_reference"])
        if not isinstance(evidence, dict):
            raise QualityContractError("RELEASE_EVIDENCE_MISSING")
        if evidence.get("proven") is not True or evidence.get("model_inventory_empty") is not True:
            raise QualityContractError("RELEASE_EVIDENCE_UNPROVEN")
        if evidence.get("loaded_models") != 0:
            raise QualityContractError("RELEASE_EVIDENCE_MODEL_RESIDENT")
        residual = evidence.get("residual_snapshots")
        if not isinstance(residual, list) or residual:
            raise QualityContractError("RELEASE_EVIDENCE_SNAPSHOT_RESIDUE")
        samples = evidence.get("gpu_samples")
        if not isinstance(samples, list) or not 3 <= len(samples) <= 32:
            raise QualityContractError("RELEASE_EVIDENCE_GPU_SAMPLES_INVALID")
        elapsed = evidence.get("elapsed_seconds")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0 or elapsed > 30:
            raise QualityContractError("RELEASE_EVIDENCE_ELAPSED_INVALID")
        baseline = self.binding.get("baseline_gpu_mib")
        previous = None
        for sample in samples:
            if not isinstance(sample, dict):
                raise QualityContractError("RELEASE_EVIDENCE_GPU_SAMPLES_INVALID")
            moment = sample.get("elapsed_seconds")
            used = sample.get("gpu_used_mib")
            if (not isinstance(moment, (int, float)) or isinstance(moment, bool) or moment < 0
                    or not _is_int(used) or used < 0):
                raise QualityContractError("RELEASE_EVIDENCE_GPU_SAMPLES_INVALID")
            if previous is not None and moment <= previous:
                raise QualityContractError("RELEASE_EVIDENCE_GPU_CADENCE_INVALID")
            previous = moment
        if _is_int(baseline) and any(sample["gpu_used_mib"] > baseline + 1024 for sample in samples[-3:]):
            raise QualityContractError("RELEASE_EVIDENCE_GPU_STABILITY_INVALID")
        return {
            "proven": True,
            "loaded_models": 0,
            "model_inventory_empty": True,
            "residual_snapshots": [],
            "gpu_samples": len(samples),
            "elapsed_seconds": elapsed,
        }

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
            "prompt_id": None,
            "provider_calls": 0,
            "graph_sha256": None,
            "raw_sha256": None,
            "suggestion_sha256": None,
            "metadata_sha256": None,
            "history_sha256": None,
            "raw_artifact": None,
            "raw_preserved": False,
            "automatic_retries": 0,
            "listener_before": None,
            "listener_after": None,
            "release_evidence": None,
            "halt": False,
        }
        before = None
        graph = None
        try:
            self.authorize("quality_row_begin", row["asset_id"])
            before = self._provider_snapshot("before")
            result["listener_before"] = self._listener_identity()
            graph, expected_node = self._build_graph(row, workflows)
            result["graph_sha256"] = sha256_bytes(canonical_json(graph).encode("utf-8"))
            self.authorize("quality_public_submit", row["asset_id"])
            driver_submissions = int(getattr(self.driver, "submissions", 0))
            driver_limit = int(getattr(self.driver, "max_public_submissions", MAX_PUBLIC_SUBMISSIONS))
            if driver_submissions >= driver_limit:
                raise QualityContractError("PUBLIC_SUBMISSION_BUDGET_EXCEEDED")
            if self._provider_calls + expected_calls > MAX_TOTAL_PROVIDER_CALLS:
                raise QualityContractError("PROVIDER_CALL_BUDGET_EXCEEDED")
            prompt_id = self.driver.submit(graph)
            self._submissions += 1
            if (not isinstance(prompt_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", prompt_id)):
                raise QualityContractError("PROMPT_ID_INVALID")
            result["prompt_id"] = prompt_id
            history = self._await_history(row, prompt_id, deadline)
            after = self._provider_snapshot("after")
            result["listener_after"] = self._listener_identity()
            if result["listener_after"] != result["listener_before"]:
                raise QualityContractError("LISTENER_IDENTITY_DRIFT")
            if not after["raw_log"].startswith(before["raw_log"]):
                raise QualityContractError("PROVIDER_LOG_REWRITTEN")
            calls = after["chat_calls"] - before["chat_calls"]
            result["provider_calls"] = calls
            if calls != expected_calls:
                raise QualityContractError("PROVIDER_CALL_COUNT_MISMATCH")
            self._provider_calls += calls
            record = history[prompt_id]
            # ---- persist the actual raw bytes BEFORE structural validation
            self._persist_row(row, graph, record, expected_node, result)
            # ---- now validate the structure
            self._validate_row(row, record, expected_node, result, graph,
                               before["chat_calls"], after["chat_calls"])
            result["execution_status"] = "PASS"
        except QualityContractError as error:
            result["error_code"] = str(error)
            if str(error) in HALT_ERROR_CODES:
                result["halt"] = True
        except Exception as error:  # noqa: BLE001 - the failure must be recorded, never hidden
            result["error_code"] = type(error).__name__ + ":" + str(error)[:200]
        finally:
            # Release evidence is required for every attempted row.  When it is
            # not proven, no further submission may happen.
            try:
                result["release_evidence"] = self._release_evidence(row)
            except QualityContractError as error:
                result["release_evidence"] = {"proven": False, "error": str(error)}
                result["halt"] = True
                if result["execution_status"] == "PASS":
                    result["execution_status"] = "FAIL"
                result["error_code"] = result["error_code"] or str(error)
            except Exception as error:  # noqa: BLE001
                result["release_evidence"] = {"proven": False, "error": type(error).__name__}
                result["halt"] = True
                result["execution_status"] = "FAIL"
                result["error_code"] = result["error_code"] or type(error).__name__
        if result["error_code"] in ("PUBLIC_SUBMISSION_BUDGET_EXCEEDED", "PROVIDER_CALL_BUDGET_EXCEEDED"):
            result["halt"] = True
        return result

    def _await_history(self, row, prompt_id, phase_deadline):
        """Poll the public history endpoint under the frozen sample bounds."""
        deadline = min(self.clock() + SAMPLE_HISTORY_TIMEOUT_SECONDS, phase_deadline)
        while True:
            if self._polls >= MAX_HISTORY_POLLS:
                raise QualityContractError("HISTORY_POLL_BUDGET_EXCEEDED")
            self.authorize("quality_public_history", row["asset_id"])
            status, history = self.driver._json_request(
                COMFY_URL + "/history/" + prompt_id, timeout=2, observer=self.driver.resource_observer)
            self._polls += 1
            if status == 200 and isinstance(history, dict) and prompt_id in history:
                return history
            if self.clock() > deadline:
                raise QualityContractError("HISTORY_TIMEOUT")
            self.sleep(HISTORY_POLL_INTERVAL_SECONDS)

    def _persist_row(self, row, graph, record, expected_node, result):
        """Save raw, suggestion and metadata as separate UTF-8 artifacts."""
        directory = "rows/" + row["asset_id"]
        self._artifact(directory + "/graph.json", canonical_json(graph).encode("utf-8"))
        history_raw = canonical_json(record).encode("utf-8")
        result["history_sha256"] = sha256_bytes(history_raw)
        self._artifact(directory + "/history.json", history_raw)
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
            metadata_text = self._image_metadata(record)
            frames = []
        else:
            if len(text) < 3:
                raise QualityContractError("PUBLIC_VIDEO_OUTPUT_INCOMPLETE")
            raw_text, suggestion_text, metadata_text = text[0], text[1], text[2]
            frames = self._video_frame_raws(raw_text)
        raw_artifact = self._artifact(directory + "/raw.txt", raw_text.encode("utf-8"))
        result["raw_artifact"] = raw_artifact["path"]
        result["raw_sha256"] = raw_artifact["sha256"]
        result["raw_bytes"] = raw_artifact["bytes"]
        result["raw_preserved"] = True
        suggestion_artifact = self._artifact(directory + "/suggestion.txt", suggestion_text.encode("utf-8"))
        result["suggestion_sha256"] = suggestion_artifact["sha256"]
        metadata_artifact = self._artifact(directory + "/metadata.txt", metadata_text.encode("utf-8"))
        result["metadata_sha256"] = metadata_artifact["sha256"]
        for index, frame_raw in enumerate(frames):
            self._artifact(directory + "/frames/frame-%d.txt" % index, frame_raw.encode("utf-8"))
        result["frame_raw_sha256"] = [sha256_bytes(item.encode("utf-8")) for item in frames]

    def _image_metadata(self, record):
        """Read the controlled image metadata through the public manual node."""
        helper = _legacy_graph_helpers()
        outputs = record.get("outputs")
        if not isinstance(outputs, dict) or not isinstance(outputs.get("3"), dict):
            raise QualityContractError("IMAGE_METADATA_NODE_MISSING")
        text = outputs["3"].get("text")
        if not isinstance(text, list) or len(text) != 2 or not all(isinstance(item, str) for item in text):
            raise QualityContractError("IMAGE_METADATA_NODE_MISSING")
        payload = helper._manual_payload(text)
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

    def _validate_row(self, row, record, expected_node, result, graph, chat_before, chat_after):
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
            self._validate_video(row, record, text, result, chat_before, chat_after)

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
        if (metadata.get("source_sha256") != row["source_sha256"]
                or metadata.get("source_bytes") != row["source_bytes"]
                or not _is_hex(metadata.get("output_rgb_sha256"), 64)
                or not isinstance(metadata.get("output_dimensions"), list)
                or not metadata["output_dimensions"]
                or any(not _is_int(value) or value <= 0 for value in metadata["output_dimensions"])):
            raise QualityContractError("IMAGE_METADATA_BINDING_INVALID")
        result["image_metadata"] = metadata

    def _validate_video(self, row, record, text, result, chat_before, chat_after):
        submitted = record["prompt"][2]
        if (submitted.get("1", {}).get("class_type") != "LVWVideoPromptOwner"
                or submitted.get("1", {}).get("inputs", {}).get("video_reference") != row["input_reference"]):
            raise QualityContractError("VIDEO_PUBLIC_PATH_BYPASSED")
        public_video_oracle(
            record, result["prompt_id"],
            source_sha256=row["source_sha256"], expected_model=MODEL_TAG,
            chat_calls_before=chat_before, chat_calls_after=chat_after,
        )
        try:
            suggestion = json.loads(text[1])
        except json.JSONDecodeError as error:
            raise QualityContractError("VIDEO_SUGGESTION_NOT_JSON") from error
        _validate_prompt_spec(suggestion)

    # -- orchestration ---------------------------------------------------
    def _empty_rows(self):
        return [{"asset_id": None, "media_kind": None, "ordinal": index + 1,
                 "execution_status": "BLOCKED", "quality_status": QUALITY_NOT_RUN,
                 "error_code": "PROJECTION_INVALID", "source_sha256": None,
                 "source_bytes": None, "input_reference": None, "prompt_id": None,
                 "provider_calls": 0, "graph_sha256": None, "raw_sha256": None,
                 "suggestion_sha256": None, "metadata_sha256": None, "history_sha256": None,
                 "raw_artifact": None, "raw_preserved": False, "automatic_retries": 0,
                 "listener_before": None, "listener_after": None, "release_evidence": None}
                for index in range(FIXED_TOTAL)]

    def _finalize(self, rows, decision, extra=None):
        statuses = [row["execution_status"] for row in rows]
        receipt = {
            "kind": QD_RECEIPT_KIND,
            "phase": PHASE_KIND,
            "run_id": self.run_id,
            "candidate_sha": self.candidate_sha,
            "authorization_sha256": self.authorization_sha256,
            "projection_sha256": self.projection_sha256,
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
            "provider_calls": self._provider_calls,
            "history_polls": self._polls,
            "artifact_files": self._artifact_files,
            "artifact_bytes": self._artifact_bytes,
            "decision": decision,
            "stage_pass_claim": False,
            "product_gate0": False,
            "quality_pass_claim": False,
            "scoring_executed": False,
            "real_execution_performed": False,
        }
        if extra:
            receipt.update(extra)
        self.receipt = receipt
        return receipt

    def run(self):
        """Execute the fixed sixteen rows once.  Never called twice."""
        if self._ran:
            raise QualityContractError("QUALITY_PHASE_ALREADY_EXECUTED")
        self._ran = True
        started = self.clock()
        try:
            self.directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            rows = self._empty_rows()
            for row in rows:
                row["error_code"] = "PHASE_DIRECTORY_EXISTS"
            receipt = self._finalize(rows, "QUALITY_EXECUTION_BLOCKED",
                                     {"error_code": "PHASE_DIRECTORY_EXISTS"})
            self._write_receipt(receipt)
            return receipt
        except OSError as error:
            rows = self._empty_rows()
            for row in rows:
                row["error_code"] = "PHASE_DIRECTORY_UNAVAILABLE"
            receipt = self._finalize(rows, "QUALITY_EXECUTION_BLOCKED",
                                     {"error_code": "PHASE_DIRECTORY_UNAVAILABLE:" + type(error).__name__})
            self._write_receipt(receipt)
            return receipt

        try:
            rows = self._parse_projection()
        except QualityContractError as error:
            rows = self._empty_rows()
            for row in rows:
                row["error_code"] = str(error)
            receipt = self._finalize(rows, "QUALITY_EXECUTION_BLOCKED", {"error_code": str(error)})
            self._write_receipt(receipt)
            return receipt

        # ---- every source is validated before the first submission --------
        source_failure = None
        for row in rows:
            try:
                row["source_evidence"] = self._validate_source(row)
            except QualityContractError as error:
                source_failure = (row, str(error))
                break
            except OSError as error:
                source_failure = (row, "SOURCE_UNAVAILABLE:" + type(error).__name__)
                break
        if source_failure is not None:
            failed_row, code = source_failure
            for row in rows:
                if row is failed_row:
                    row["execution_status"] = "FAIL"
                    row["error_code"] = code
                else:
                    row["execution_status"] = "BLOCKED"
                    row["error_code"] = "SOURCE_PRECONDITION_FAILED"
            receipt = self._finalize(rows, "QUALITY_EXECUTION_BLOCKED",
                                     {"error_code": code, "public_submissions": 0})
            self._write_receipt(receipt)
            return receipt

        try:
            workflows = self._load_workflows()
        except QualityContractError as error:
            for row in rows:
                row["execution_status"] = "BLOCKED"
                row["error_code"] = str(error)
            receipt = self._finalize(rows, "QUALITY_EXECUTION_BLOCKED", {"error_code": str(error)})
            self._write_receipt(receipt)
            return receipt

        results = []
        for index, row in enumerate(rows):
            if self.clock() - started > PHASE_TIMEOUT_SECONDS:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PHASE_DEADLINE_EXCEEDED"
                break
            if self._submissions >= MAX_PUBLIC_SUBMISSIONS:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PUBLIC_SUBMISSION_BUDGET_EXCEEDED"
                break
            if self._provider_calls >= MAX_TOTAL_PROVIDER_CALLS:
                for pending in rows[index:]:
                    pending["execution_status"] = "BLOCKED"
                    pending["error_code"] = "PROVIDER_CALL_BUDGET_EXCEEDED"
                break
            outcome = self._execute_row(row, workflows)
            results.append(outcome)
            if outcome["halt"]:
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
        receipt = self._finalize(merged, decision)
        self._write_receipt(receipt)
        return receipt

    def _write_receipt(self, receipt):
        try:
            raw = canonical_json(receipt).encode("utf-8")
            if len(raw) <= MAX_ARTIFACT_BYTES and self._artifact_files < MAX_ARTIFACT_FILES:
                with (self.directory / "qd-receipt.json").open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._artifact_files += 1
                self._artifact_bytes += len(raw)
        except (OSError, ValueError):
            # The receipt is returned in memory; a failed write is reported by
            # the caller through the returned document.
            pass


# ======================================================================
# QS: independent score recomputation
# ======================================================================

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


def verify_independence(independence, *, implementer_identity=None):
    """Prove reviewer separation from an isolation receipt.

    A reviewer identity string alone proves nothing; the isolation receipt is
    the only accepted proof of independence.
    """
    if not isinstance(independence, dict):
        raise QualityContractError("INDEPENDENCE_RECEIPT_MISSING")
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
    if len(set(identities)) != len(identities) or len(set(sessions)) != len(sessions):
        raise QualityContractError("INDEPENDENCE_REVIEWER_NOT_UNIQUE")
    return {
        "reviewer_ids": sorted(set(identities)),
        "session_ids": sorted(set(sessions)),
        "separation": dict(separation),
    }


def _validate_score_document(score):
    """Validate one independent scoring receipt."""
    if not isinstance(score, dict):
        raise QualityContractError("SCORE_RECEIPT_NOT_OBJECT")
    for key in ("run_id", "candidate_sha", "projection_sha256", "asset_id",
                "source_sha256", "raw_sha256", "reviewer_id", "session_id"):
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
    denominator = execution_receipt.get("fixed_denominator")
    if (not isinstance(denominator, dict) or denominator.get("total") != FIXED_TOTAL
            or denominator.get("images") != FIXED_IMAGES or denominator.get("videos") != FIXED_VIDEOS):
        raise QualityContractError("QS_DENOMINATOR_INVALID")
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
    independence_evidence = verify_independence(independence, implementer_identity=implementer_identity)
    known_reviewers = set(independence_evidence["reviewer_ids"])

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
        if score["reviewer_id"] not in known_reviewers:
            raise QualityContractError("QS_SCORE_REVIEWER_NOT_INDEPENDENT:" + asset_id)
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
            "reason": None,
            "total": None,
            "critical_hallucinations": None,
            "dimensions": None,
            "reviewer_id": None,
            "raw_sha256": row.get("raw_sha256"),
            "raw_bytes": None,
            "raw_artifact": row.get("raw_artifact"),
        }
        score = scores.get(asset_id)
        if row.get("execution_status") != "PASS":
            entry["reason"] = "EXECUTION_NOT_PASS"
            computed.append(entry)
            continue
        if score is None:
            entry["reason"] = "MISSING_SCORE"
            computed.append(entry)
            continue
        artifact = _safe_artifact_path(artifact_root, row.get("raw_artifact"))
        raw = artifact.read_bytes()
        if sha256_bytes(raw) != row.get("raw_sha256"):
            raise QualityContractError("QS_RAW_ARTIFACT_HASH_MISMATCH:" + asset_id)
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
        entry["raw_bytes"] = len(raw)
        usable = total >= PER_SAMPLE_TOTAL_MIN and critical <= CRITICAL_HALLUCINATIONS_MAX
        if usable:
            entry["quality_status"] = "PASS"
            entry["reason"] = "USABLE"
        else:
            entry["reason"] = ("CRITICAL_HALLUCINATION" if critical > CRITICAL_HALLUCINATIONS_MAX
                               else "TOTAL_BELOW_THRESHOLD")
        computed.append(entry)

    images_usable = sum(1 for entry in computed
                         if entry["media_kind"] == "image" and entry["quality_status"] == "PASS")
    videos_usable = sum(1 for entry in computed
                         if entry["media_kind"] == "video" and entry["quality_status"] == "PASS")
    total_critical = sum(entry["critical_hallucinations"] or 0 for entry in computed)
    unresolved = [entry["asset_id"] for entry in computed
                  if entry["execution_status"] != "PASS" or entry["reason"] == "MISSING_SCORE"]
    thresholds_met = (images_usable >= IMAGE_USABLE_MIN and videos_usable >= VIDEO_USABLE_MIN
                      and total_critical <= CRITICAL_HALLUCINATIONS_MAX)
    all_rows_resolved = not unresolved
    aggregate_pass = bool(thresholds_met and all_rows_resolved)
    if aggregate_pass:
        decision = "QUALITY_THRESHOLDS_MET_FOR_THIS_BOUND_RUN"
    elif not all_rows_resolved:
        decision = "QUALITY_INCOMPLETE_UNRESOLVED_ROWS"
    else:
        decision = "QUALITY_THRESHOLDS_NOT_MET"

    return {
        "kind": QS_RECEIPT_KIND,
        "phase": PHASE_KIND,
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
            "per_sample_total_min": PER_SAMPLE_TOTAL_MIN,
            "dimension_max": DIMENSION_MAX,
        },
        "thresholds_met": thresholds_met,
        "all_rows_resolved": all_rows_resolved,
        "unresolved_rows": unresolved,
        "aggregate_pass": aggregate_pass,
        "decision": decision,
        "independence": independence_evidence,
        "stage_pass_claim": False,
        "product_gate0": False,
        "scoring_source": "INDEPENDENT_SCORING_RECEIPTS_ONLY",
        "model_called": False,
        "keyword_scoring": False,
    }
