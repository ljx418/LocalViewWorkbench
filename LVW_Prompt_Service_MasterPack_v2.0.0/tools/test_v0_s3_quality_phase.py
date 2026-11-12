"""Offline acceptance tests for the S3-P3B quality phase (QD execution + QS scoring).

The suite is offline only.  It never starts a service, never opens a socket,
never launches a host process, never decodes the real quality-set media and
never calls a model.  The public production node classes, the public
``BridgeOwner`` and the public S2 oracles are exercised for real; only the
native HTTP/provider boundary and the media decoder are replaced by bounded
synthetic fixtures.

The subprocess and network guards below are installed *before* any project
module is imported, so no plugin or import can open a socket or start a host
process either.
"""

import copy
import hashlib
import inspect
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


# --------------------------------------------------------------------------
# offline guard, installed before pytest and before any project import
# --------------------------------------------------------------------------
class OfflineGuardError(RuntimeError):
    """Raised when a test tries to leave the offline boundary."""


def _blocked_network(*args, **kwargs):
    raise OfflineGuardError("network access is blocked in the offline quality tests")


def _blocked_subprocess(*args, **kwargs):
    raise OfflineGuardError("host subprocess execution is blocked in the offline quality tests")


def _install_offline_guard():
    socket.socket.connect = _blocked_network
    socket.socket.connect_ex = _blocked_network
    socket.socket.bind = _blocked_network
    socket.create_connection = _blocked_network
    socket.getaddrinfo = _blocked_network
    subprocess.Popen = _blocked_subprocess
    os.system = _blocked_subprocess
    os.popen = _blocked_subprocess


_install_offline_guard()

import pytest  # noqa: E402  (imported only after the offline guard is active)

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import nodes            # noqa: E402
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError, BridgeOwner  # noqa: E402
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.image_input import ControlledImageOwner  # noqa: E402
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner  # noqa: E402
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_api import LVWVideoPromptOwner  # noqa: E402
from tools import v0_s3_quality_phase as quality                            # noqa: E402
from tools.v0_s3_quality_phase import (                                     # noqa: E402
    FIXED_IMAGES, FIXED_TOTAL, FIXED_VIDEOS, FROZEN_DIMENSIONS, IMAGE_WORKFLOW,
    MAX_PUBLIC_SUBMISSIONS, MAX_TOTAL_PROVIDER_CALLS, QualityContractError,
    QualityPhase, VIDEO_WORKFLOW, WORKFLOW_DIR, recompute_scores, verify_independence,
)

CANDIDATE_SHA = "a" * 40
AUTHORIZATION_SHA = "b" * 64
RUN_ID = "synthetic-quality-run"
REVIEWER_ID = "independent-reviewer-01"
REVIEWER_SESSION = "independent-session-01"
BASE_GPU_MIB = 100


# --------------------------------------------------------------------------
# synthetic production boundary
# --------------------------------------------------------------------------
class SyntheticTransport:
    """A bounded synthetic provider boundary for the real ``BridgeOwner``.

    The transport speaks the production envelope shape so the real owner
    parses, compiles and publishes exactly what it would publish for a real
    local model.  No socket is ever opened.  The ``fail_at`` mode returns an
    unusable envelope so the *real* owner produces the real ``BridgeError``
    with its raw response details.
    """

    endpoint = "http://127.0.0.1:11434/api/chat"

    def __init__(self, log, counter, video, fail_at=0):
        self.log = log
        self.counter = counter
        self.video = video
        self.fail_at = fail_at
        self.calls = 0

    def chat(self, payload, timeout_seconds):
        self.calls += 1
        self.counter[0] += 1
        number = self.counter[0]
        self.log.append('[GIN] 200 POST "/api/chat"\n')
        if self.fail_at and self.calls == self.fail_at:
            # A provider envelope the real owner must reject.  The real
            # BridgeError keeps this exact raw response as evidence.
            return "this is not a json envelope"
        content = {
            "observations": [f"synthetic observation {number}"],
            "inferences": [],
            "unknowns": [],
            "prompt": f"synthetic prompt {number}",
            "tags": [f"synthetic tag {number}"],
        }
        if self.video:
            content["change"] = f"synthetic change {number}"
        return json.dumps({
            "model": "gemma4:26b",
            "done": True,
            "done_reason": "stop",
            "message": {"content": json.dumps(content, ensure_ascii=False)},
        })

    def cleanup(self, *args):
        return None


def _encoder(frame):
    return "c3ludGhldGljLWZhbWUtZnJhbWU="


def _frame():
    return SimpleNamespace(shape=(4, 4, 3))


class SyntheticVideoOwner:
    """Adapter around the real ``BridgeOwner`` for the real video node class.

    The node class, the owner, the four provider calls, the raw envelope array
    and the machine suggestion are production code.  Only the decoder and the
    media bytes are synthetic.
    """

    def __init__(self, transport, input_root):
        self.transport = transport
        self.input_root = Path(input_root)

    def run(self, token, reference, **kwargs):
        owner = BridgeOwner(transport=self.transport, encoder=_encoder)
        raw, suggestion = owner.analyze_video(
            [_frame() for _ in range(4)], model="gemma4:26b", user_instruction="",
            mode="realistic", timeout_seconds=120)
        manifest = []
        for index in range(4):
            manifest.append({
                "index": index,
                "pts": index * 1000,
                "time_base_num": 1,
                "time_base_den": 1000,
                "time_seconds": float(index),
                "sha256": hashlib.sha256(f"synthetic-frame-{index}".encode("utf-8")).hexdigest(),
            })
        source = self.input_root / reference
        return {
            "raw_response": raw,
            "suggestion": suggestion,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "run_token": token,
            "cancel_epoch": 0,
            "frames": manifest,
        }


class SyntheticDriver:
    """The bounded native queue/provider boundary used by the offline tests.

    The surface is the public ``NativeRuntime`` surface the phase consumes:
    ``submit``, ``chat_log_snapshot``, ``resource_observer``, ``_json_request``,
    ``owned_listener_birth``, ``release_preload``, ``video_snapshot_residue``,
    ``submissions`` and ``max_public_submissions``.
    """

    def __init__(self, root, failure=None):
        self.root = Path(root)
        self.failure = failure
        self.submissions = 0
        self.max_public_submissions = MAX_PUBLIC_SUBMISSIONS
        self.history = {}
        self.log = ['[GIN] 200 GET "/api/tags"\n']
        self.counter = [0]
        # The real owner must fail on its own, so the real BridgeError and its
        # raw response details are produced by the production code path.
        image_fail = 1 if failure == "provider-refusal" else 0
        video_fail = 2 if failure == "provider-refusal" else 0
        self.image_transport = SyntheticTransport(self.log, self.counter, video=False,
                                                  fail_at=image_fail)
        self.video_transport = SyntheticTransport(self.log, self.counter, video=True,
                                                  fail_at=video_fail)
        self.actions = []
        self._resource_worker = object()
        self.manual = nodes.LVWManualPromptOwner(owner=ManualDraftOwner(
            export_root=self.root / "output/lvw_manual",
            export_parent=self.root / "output",
            clipboard=SimpleNamespace(write=lambda value: None)))
        self.image = nodes.LVWControlledImageInput(owner=ControlledImageOwner(self.root / "input"))
        self.bridge = nodes.LVWImagePromptBridge(transport=self.image_transport, encoder=_encoder)
        self.video = LVWVideoPromptOwner(owner=SyntheticVideoOwner(self.video_transport, self.root / "input"))

    # -- public runtime surface -----------------------------------------
    def resource_observer(self):
        return None

    def owned_listener_birth(self, port):
        birth = 100
        if self.failure == "listener-drift" and self.submissions >= 1:
            birth = 101
        return {"pid": 20 + port % 100, "start_ticks": birth}

    def chat_log_snapshot(self):
        raw = "".join(self.log)
        if self.failure == "rewritten-log" and self.submissions >= 1:
            # A cleared and rewritten provider log: the earlier prefix is gone.
            raw = '[GIN] 200 POST "/api/chat"\n'
        data = raw.encode("utf-8")
        return {
            "raw_log": raw,
            "source_log_bytes": len(data),
            "source_log_sha256": hashlib.sha256(data).hexdigest(),
            "chat_calls": sum("POST" in line and '"/api/chat"' in line for line in raw.splitlines()),
        }

    def release_preload(self, binding, worker):
        # The production release shape: the actual bounded native proof with
        # the bound baseline, the strict empty model inventory, the elapsed
        # time and the actual GPU sample list.
        self.log.append('[GIN] 200 POST "/api/generate"\n')
        self.log.append('[GIN] 200 GET "/api/ps"\n')
        samples = [{"monotonic_seconds": index, "gpu_used_mib": 1124} for index in range(3)]
        proof = {"proven": True, "loaded_models": 0, "baseline_gpu_mib": BASE_GPU_MIB,
                 "elapsed_seconds": 3, "gpu_samples": samples}
        if self.failure == "release-unproven":
            proof.update(proven=False, loaded_models=1)
        elif self.failure == "release-model-resident":
            proof.update(loaded_models=1)
        elif self.failure == "release-nan":
            proof.update(elapsed_seconds=float("nan"),
                         gpu_samples=[{"monotonic_seconds": float("nan"), "gpu_used_mib": 1124}
                                      for _ in range(3)])
        elif self.failure == "release-inf":
            proof.update(elapsed_seconds=float("inf"))
        elif self.failure == "release-bool":
            proof.update(elapsed_seconds=True)
        elif self.failure == "release-baseline":
            proof.update(baseline_gpu_mib=BASE_GPU_MIB + 4096)
        elif self.failure == "release-cadence":
            proof.update(gpu_samples=[{"monotonic_seconds": index * 4, "gpu_used_mib": 1124}
                                      for index in range(3)])
        elif self.failure == "release-samples":
            proof.update(gpu_samples=[{"monotonic_seconds": index, "gpu_used_mib": 1124}
                                      for index in range(2)])
        elif self.failure == "release-stability":
            proof.update(gpu_samples=[{"monotonic_seconds": index, "gpu_used_mib": BASE_GPU_MIB + 4096}
                                      for index in range(3)])
        return proof

    def video_snapshot_residue(self):
        if self.failure == "residue":
            return ["/comfy/temp/lvw-video-leftover"]
        return []

    def _json_request(self, url, **kwargs):
        if self.failure == "history-timeout":
            return 200, {}
        return 200, copy.deepcopy(self.history)

    def submit(self, graph):
        self.submissions += 1
        prompt = f"{self.submissions:032x}"
        if self.failure == "duplicate-prompt":
            prompt = "constant-prompt-id"
        produced, outputs = {}, {}
        status = {"status_str": "success", "messages": []}
        try:
            for name in sorted(graph, key=int):
                definition = graph[name]
                inputs = copy.deepcopy(definition["inputs"])
                for key, value in list(inputs.items()):
                    if (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
                            and value[0] in produced):
                        inputs[key] = produced[value[0]][value[1]]
                kind = definition["class_type"]
                if kind == "LVWControlledImageInput":
                    result = self.image.load(**inputs)
                elif kind == "LVWImagePromptBridge":
                    result = self.bridge.analyze(**inputs)
                elif kind == "LVWManualPromptOwner":
                    result = self.manual.process(**inputs)
                elif kind == "LVWVideoPromptOwner":
                    result = self.video.analyze(**inputs)
                else:
                    raise AssertionError("unfrozen class_type " + str(kind))
                if isinstance(result, dict):
                    outputs[name] = result["ui"]
                    produced[name] = result["result"]
                else:
                    produced[name] = result
        except BridgeError as error:
            # The production BridgeError renders its own evidence for the
            # Comfy history: the code, the message and the details, including
            # the raw provider response and the raw responses of the frames
            # that were already analysed.
            status = {"status_str": "error", "messages": [["execution_error", {
                "prompt_id": prompt, "node_id": name, "node_type": kind,
                "exception_message": str(error)}]]}
            outputs = {}
        history_graph = copy.deepcopy(graph)
        history_prompt = prompt
        if self.failure == "history-graph":
            history_graph = {}
        if self.failure == "history-prompt-id":
            history_prompt = "different-prompt-id"
        self.history[prompt] = {
            "prompt": [0, history_prompt, history_graph],
            "outputs": outputs,
            "status": status,
        }
        self._inject_output_fault(prompt)
        return prompt

    def _inject_output_fault(self, prompt):
        record = self.history.get(prompt)
        if record is None or not isinstance(record.get("outputs"), dict):
            return
        outputs = record["outputs"]
        for node, entries in list(outputs.items()):
            text = entries.get("text")
            if not isinstance(text, list) or not text:
                continue
            if self.failure == "bad-suggestion" and node == "2":
                text[1] = json.dumps({"schema_version": "lvw.prompt/1"})
            if self.failure == "bad-raw" and node == "2":
                text[0] = json.dumps({"model": "gemma4:26b", "done": False, "message": {"content": ""}})
            if self.failure == "video-frames-3" and node == "1":
                raw = json.loads(text[0])
                raw["frame_raw_responses"] = raw["frame_raw_responses"][:3]
                text[0] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
            if self.failure == "image-metadata-mismatch" and node == "3":
                payload = json.loads(text[1])
                payload["draft"]["natural_zh"] = json.dumps({
                    "source_sha256": "c" * 64, "source_bytes": 1,
                    "output_rgb_sha256": "d" * 64, "output_dimensions": [4, 4]})
                text[1] = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if self.failure == "missing-node-output":
                record["outputs"].pop(node, None)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _tiny_png(index):
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (4, 4), (index * 20 % 256, 40, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def _build_sources(root):
    """Create the ten synthetic images and six synthetic videos."""
    rows = []
    for index in range(FIXED_IMAGES):
        name = "synthetic-image-%02d.png" % index
        data = _tiny_png(index)
        (root / "input" / name).write_bytes(data)
        rows.append({
            "asset_id": "SYN-I%02d" % index,
            "media_kind": "image",
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "source_bytes": len(data),
            "input_reference": name,
        })
    for index in range(FIXED_VIDEOS):
        name = "synthetic-video-%02d.mp4" % index
        data = b"synthetic-video-fixture-%02d" % index
        (root / "input" / name).write_bytes(data)
        rows.append({
            "asset_id": "SYN-V%02d" % index,
            "media_kind": "video",
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "source_bytes": len(data),
            "input_reference": name,
        })
    return rows


def _projection_bytes(rows):
    document = {
        "schema_version": "lvw.s3-quality-execution/1",
        "spec_version": "SYN-Q16-01",
        "fixed_denominator": {"images": FIXED_IMAGES, "videos": FIXED_VIDEOS, "total": FIXED_TOTAL},
        "samples": rows,
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _source_identity():
    workflows = {}
    for name in (IMAGE_WORKFLOW, VIDEO_WORKFLOW):
        raw = (WORKFLOW_DIR / name).read_bytes()
        workflows[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return {"candidate_sha": CANDIDATE_SHA, "workflows": workflows}


def _binding():
    return {
        "candidate_sha": CANDIDATE_SHA,
        "authorization_sha256": AUTHORIZATION_SHA,
        "ollama_pid": 20,
        "ollama_start_ticks": 100,
        "baseline_gpu_mib": BASE_GPU_MIB,
    }


class FakeClock:
    """A deterministic monotonic clock for the bounded offline tests."""

    def __init__(self, step=0.0):
        self.now = 0.0
        self.step = step

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += self.step or seconds


def _parent_proof(clock, **overrides):
    """A typed internal parent capacity proof in the phase clock domain.

    This is an internal admission document only.  It never proves that a real
    reservation exists; the authentic provider and the actual debit stay with
    the parent coordinator.
    """
    now = clock()
    proof = {
        "kind": "LVW_PARENT_CAPACITY_PROOF/1",
        "known": True,
        "run_id": RUN_ID,
        "candidate_sha": CANDIDATE_SHA,
        "authorization_sha256": AUTHORIZATION_SHA,
        "issued_monotonic": float(now),
        "expires_monotonic": float(now) + 3600.0,
        "action_capacity": 34,
    }
    proof.update(overrides)
    return proof


_UNSET = object()


def _prepare(root, failure=None, rows=None, clock=None, parent_budget=_UNSET, driver=None):
    for name in ("input", "output", "temp"):
        (root / name).mkdir(parents=True, exist_ok=True)
    if rows is None:
        rows = _build_sources(root)
    projection = _projection_bytes(rows)
    if driver is None:
        driver = SyntheticDriver(root, failure)
    if clock is None:
        clock = FakeClock(step=100.0)
    if parent_budget is _UNSET:
        parent_budget = _parent_proof(clock)
    phase = QualityPhase(
        driver, root, run_id=RUN_ID, candidate_sha=CANDIDATE_SHA,
        authorization_sha256=AUTHORIZATION_SHA, projection=projection,
        projection_sha256=hashlib.sha256(projection).hexdigest(),
        source_identity=_source_identity(), authorize=lambda *args: None,
        binding=_binding(), parent_budget=parent_budget, clock=clock, sleep=clock.sleep,
    )
    return phase, driver, projection


@pytest.fixture()
def prepared(tmp_path):
    phase, driver, projection = _prepare(tmp_path)
    return phase, driver, projection


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("s3-quality-completed")
    clock = FakeClock(step=0.0)
    phase, driver, projection = _prepare(root, clock=clock)
    receipt = phase.run()
    return {
        "receipt": receipt,
        "artifact_root": root / "temp" / "s3-quality",
        "root": root,
        "driver": driver,
        "projection": projection,
        "projection_sha256": hashlib.sha256(projection).hexdigest(),
    }


def _score_for(row, *, total=10, critical=0, reviewer=REVIEWER_ID, session=REVIEWER_SESSION,
               raw_sha=None, raw_artifact=None, run_id=RUN_ID, candidate=CANDIDATE_SHA,
               projection_sha=None):
    per_dimension = {name: total // len(FROZEN_DIMENSIONS) for name in FROZEN_DIMENSIONS}
    per_dimension[FROZEN_DIMENSIONS[0]] += total - sum(per_dimension.values())
    return {
        "run_id": run_id,
        "candidate_sha": candidate,
        "projection_sha256": projection_sha or "d" * 64,
        "asset_id": row["asset_id"],
        "source_sha256": row["source_sha256"],
        "raw_sha256": raw_sha or row["raw_sha256"],
        "raw_artifact": raw_artifact or row["raw_artifact"],
        "raw_bytes": row.get("raw_bytes"),
        "reviewer_id": reviewer,
        "session_id": session,
        "dimensions": per_dimension,
        "critical_hallucinations": critical,
        "basis": "synthetic independent review basis",
    }


def _independence(run_id=RUN_ID, reviewers=None):
    return {
        "run_id": run_id,
        "separation": {
            "isolated_instance": True,
            "separate_session": True,
            "no_implementation_participation": True,
        },
        "reviewers": reviewers or [{
            "reviewer_id": REVIEWER_ID, "session_id": REVIEWER_SESSION, "role": "INDEPENDENT_REVIEWER",
        }],
    }


def _scores(receipt, projection_sha, **kwargs):
    scores = []
    for row in receipt["rows"]:
        scores.append(_score_for(row, projection_sha=projection_sha, **kwargs))
    return scores


# --------------------------------------------------------------------------
# QD: projection and source preconditions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("mutation,expected", [
    ("duplicate-asset-id", "PROJECTION_DUPLICATE_ASSET_ID"),
    ("duplicate-source-hash", "PROJECTION_DUPLICATE_SOURCE_HASH"),
    ("duplicate-reference", "PROJECTION_DUPLICATE_REFERENCE"),
    ("wrong-denominator", "PROJECTION_DENOMINATOR_INVALID"),
    ("wrong-row-count", "PROJECTION_ROW_COUNT_INVALID"),
    ("path-escape-reference", "PROJECTION_REFERENCE_NOT_SIMPLE_NAME"),
    ("video-extension-widened", "PROJECTION_REFERENCE_EXTENSION_INVALID"),
    ("label-field-smuggled", "PROJECTION_ROW_UNEXPECTED_FIELD"),
    ("top-level-extra-field", "PROJECTION_UNEXPECTED_FIELD"),
    ("source-bytes-over-limit", "PROJECTION_SOURCE_BYTES_OVER_LIMIT"),
])
def test_projection_is_strict_and_never_carries_labels(tmp_path, mutation, expected):
    root = tmp_path / mutation
    rows = _build_sources(root) if (root / "input").is_dir() else None
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "temp").mkdir(parents=True, exist_ok=True)
    rows = _build_sources(root)
    document = json.loads(_projection_bytes(rows).decode("utf-8"))
    if mutation == "duplicate-asset-id":
        document["samples"][1]["asset_id"] = document["samples"][0]["asset_id"]
    elif mutation == "duplicate-source-hash":
        document["samples"][1]["source_sha256"] = document["samples"][0]["source_sha256"]
    elif mutation == "duplicate-reference":
        document["samples"][1]["input_reference"] = document["samples"][0]["input_reference"]
    elif mutation == "wrong-denominator":
        document["fixed_denominator"]["total"] = 18
    elif mutation == "wrong-row-count":
        document["samples"] = document["samples"][:15]
    elif mutation == "path-escape-reference":
        document["samples"][0]["input_reference"] = "../outside.png"
    elif mutation == "video-extension-widened":
        document["samples"][10]["input_reference"] = "synthetic-video-00.mkv"
    elif mutation == "label-field-smuggled":
        document["samples"][0]["prelabel"] = "not allowed in the execution projection"
    elif mutation == "top-level-extra-field":
        document["prelabels"] = []
    elif mutation == "source-bytes-over-limit":
        document["samples"][0]["source_bytes"] = 20 * 1024 * 1024 + 1
    projection = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    phase, driver, _ = _prepare(root, rows=rows)
    phase.projection_bytes = projection
    phase.projection_sha256 = hashlib.sha256(projection).hexdigest()
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"] == expected, receipt["error_code"]
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["test_counts"] == {"fixed": 16, "PASS": 0, "FAIL": 0, "BLOCKED": 16, "NOT_RUN": 0}, receipt


def test_source_hash_mismatch_blocks_every_row_with_zero_submissions(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    rows = json.loads(phase.projection_bytes.decode("utf-8"))
    rows["samples"][3]["source_sha256"] = "e" * 64
    phase.projection_bytes = json.dumps(rows, sort_keys=True).encode("utf-8")
    phase.projection_sha256 = hashlib.sha256(phase.projection_bytes).hexdigest()
    receipt = phase.run()
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["test_counts"]["PASS"] == 0, receipt
    assert receipt["test_counts"]["FAIL"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt
    assert receipt["rows"][3]["error_code"] == "SOURCE_HASH_MISMATCH", receipt["rows"][3]


def test_source_symlink_is_refused_before_any_submission(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    target = tmp_path / "input" / "synthetic-image-00.png"
    link = tmp_path / "input" / "synthetic-image-01.png"
    real = tmp_path / "input" / "synthetic-image-02.png"
    link.unlink()
    link.symlink_to(real)
    receipt = phase.run()
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["test_counts"]["PASS"] == 0, receipt
    assert any(row["error_code"] == "SOURCE_REDIRECT_FORBIDDEN" for row in receipt["rows"]), receipt


def test_source_growth_during_the_read_is_detected(tmp_path, monkeypatch):
    phase, driver, _ = _prepare(tmp_path)
    original = os.read
    calls = {"n": 0}

    def growing_read(descriptor, count):
        calls["n"] += 1
        if calls["n"] >= 2:
            return b"x"
        return original(descriptor, count)

    monkeypatch.setattr(os, "read", growing_read)
    receipt = phase.run()
    monkeypatch.undo()
    assert receipt["public_submissions"] == 0, receipt
    assert any(row["error_code"] == "SOURCE_GROWTH" for row in receipt["rows"]), receipt


def test_workflow_source_identity_mismatch_blocks_the_run(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    phase.source_identity["workflows"][IMAGE_WORKFLOW]["sha256"] = "f" * 64
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"].startswith("WORKFLOW_SOURCE_IDENTITY_MISMATCH"), receipt
    assert receipt["public_submissions"] == 0, receipt


def test_binding_is_required_and_must_match_the_candidate(tmp_path):
    (tmp_path / "input").mkdir(parents=True, exist_ok=True)
    rows = _build_sources(tmp_path)
    projection = _projection_bytes(rows)
    driver = SyntheticDriver(tmp_path)
    common = dict(run_id=RUN_ID, candidate_sha=CANDIDATE_SHA, authorization_sha256=AUTHORIZATION_SHA,
                  projection=projection, projection_sha256=hashlib.sha256(projection).hexdigest(),
                  source_identity=_source_identity(), authorize=lambda *args: None,
                  parent_budget={"known": True, "action_capacity": 34})
    with pytest.raises(QualityContractError) as missing:
        QualityPhase(driver, tmp_path, binding={}, **common)
    assert "QUALITY_BINDING_INCOMPLETE" in str(missing.value)
    wrong = _binding()
    wrong["candidate_sha"] = "c" * 40
    with pytest.raises(QualityContractError) as mismatch:
        QualityPhase(driver, tmp_path, binding=wrong, **common)
    assert "QUALITY_BINDING_CANDIDATE_MISMATCH" in str(mismatch.value)


# --------------------------------------------------------------------------
# QD: the fixed sixteen row execution
# --------------------------------------------------------------------------
def test_sixteen_rows_pass_with_exact_provider_counts(completed_run):
    receipt = completed_run["receipt"]
    assert receipt["decision"] == "QUALITY_EXECUTION_COMPLETE_ALL_16_PASS", receipt
    assert receipt["test_counts"] == {"fixed": 16, "PASS": 16, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}, receipt
    assert receipt["public_submissions"] == 16, receipt
    assert receipt["provider_calls_observed"] == MAX_TOTAL_PROVIDER_CALLS == 34, receipt
    assert receipt["provider_calls_reserved"] == 34, receipt
    assert len(receipt["rows"]) == 16, receipt
    assert all(row["quality_status"] == "NOT_RUN" for row in receipt["rows"]), receipt
    assert all(row["raw_preserved"] for row in receipt["rows"]), receipt
    assert all(row["automatic_retries"] == 0 for row in receipt["rows"]), receipt
    assert receipt["stage_pass_claim"] is False and receipt["product_gate0"] is False, receipt
    assert receipt["scoring_executed"] is False and receipt["quality_pass_claim"] is False, receipt
    images = [row for row in receipt["rows"] if row["media_kind"] == "image"]
    videos = [row for row in receipt["rows"] if row["media_kind"] == "video"]
    assert len(images) == 10 and len(videos) == 6, receipt
    assert all(row["provider_calls"] == 1 for row in images), receipt
    assert all(row["provider_calls"] == 4 for row in videos), receipt
    assert all(len(row["frame_raw_sha256"]) == 4 for row in videos), receipt
    assert all(row["release_evidence"]["proven"] for row in receipt["rows"]), receipt
    assert all(row["video_snapshot_residue"] == [] for row in receipt["rows"]), receipt


def test_the_real_production_nodes_produced_the_observed_outputs(completed_run):
    receipt = completed_run["receipt"]
    artifact_root = completed_run["artifact_root"]
    for row in receipt["rows"]:
        raw = (artifact_root / row["raw_artifact"]).read_bytes().decode("utf-8")
        if row["media_kind"] == "image":
            envelope = json.loads(raw)
            assert envelope["model"] == "gemma4:26b" and envelope["done"] is True, envelope
            assert envelope["message"]["content"], envelope
        else:
            frames = json.loads(raw)["frame_raw_responses"]
            assert len(frames) == 4, frames
            for frame in frames:
                inner = json.loads(frame)
                assert inner["model"] == "gemma4:26b" and inner["done"] is True, inner
        suggestion = json.loads((artifact_root / row["suggestion_artifact"]).read_bytes().decode("utf-8"))
        assert suggestion["schema_version"] == "lvw.prompt/1", suggestion
        assert suggestion["domains"]["observation"], suggestion


def test_raw_is_persisted_before_a_structural_rejection(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="bad-suggestion")
    receipt = phase.run()
    assert receipt["test_counts"]["FAIL"] == 10, receipt
    row = receipt["rows"][0]
    assert row["execution_status"] == "FAIL", row
    assert row["error_code"].startswith("PROMPT_SPEC_INVALID"), row
    assert row["raw_preserved"] is True, row
    artifact = phase.directory / row["raw_artifact"]
    assert artifact.is_file(), artifact
    envelope = json.loads(artifact.read_bytes().decode("utf-8"))
    assert envelope["model"] == "gemma4:26b" and envelope["done"] is True, envelope
    assert (phase.directory / row["history_artifact"]).is_file(), row


def test_wrong_history_graph_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="history-graph")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "PUBLIC_GRAPH_MISMATCH", receipt["rows"][0]
    assert receipt["test_counts"]["PASS"] == 0, receipt


def test_wrong_history_prompt_id_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="history-prompt-id")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "PUBLIC_PROMPT_ID_MISMATCH", receipt["rows"][0]


def test_a_reused_prompt_id_across_rows_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="duplicate-prompt")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] is None, receipt["rows"][0]
    assert receipt["rows"][1]["error_code"] == "PROMPT_ID_REUSED", receipt["rows"][1]
    assert receipt["public_submissions"] == 2, receipt
    assert receipt["test_counts"]["BLOCKED"] == 14, receipt


def test_a_rewritten_provider_log_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="rewritten-log")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "PROVIDER_LOG_REWRITTEN", receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt


def test_a_wrong_provider_call_count_is_rejected_and_stops_the_batch(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    original = driver.image_transport.chat

    def double(payload, timeout_seconds):
        original(payload, timeout_seconds)
        return original(payload, timeout_seconds)

    driver.image_transport.chat = double
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "PROVIDER_CALL_COUNT_MISMATCH", receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_a_listener_identity_drift_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="listener-drift")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "LISTENER_IDENTITY_DRIFT", receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt


def test_an_unproven_release_stops_every_further_submission(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="release-unproven")
    receipt = phase.run()
    assert receipt["rows"][0]["release_evidence"]["proven"] is False, receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt
    assert receipt["halted"] is True, receipt


def test_a_resident_model_is_not_accepted_as_a_release(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="release-model-resident")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "RELEASE_EVIDENCE_MODEL_RESIDENT", receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt


def test_a_leftover_video_snapshot_stops_the_row(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="residue")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "VIDEO_SNAPSHOT_RESIDUE", receipt["rows"][0]
    assert receipt["public_submissions"] == 1, receipt


def test_a_missing_public_node_output_is_a_row_failure_with_history_kept(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="missing-node-output")
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["error_code"] == "PUBLIC_NODE_OUTPUT_MISSING", row
    assert (phase.directory / row["history_artifact"]).is_file(), row
    assert (phase.directory / row["graph_artifact"]).is_file(), row


def test_a_broken_image_metadata_binding_is_rejected(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="image-metadata-mismatch")
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "IMAGE_METADATA_BINDING_INVALID", receipt["rows"][0]


def test_a_wrong_video_frame_denominator_is_rejected_after_the_raw_was_kept(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="video-frames-3")
    receipt = phase.run()
    row = receipt["rows"][10]
    assert row["error_code"] == "VIDEO_RAW_DENOMINATOR_INVALID", row
    assert row["raw_preserved"] is True, row
    assert (phase.directory / row["raw_artifact"]).is_file(), row


def test_a_bounded_history_wait_fails_the_row_without_an_unbounded_poll(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="history-timeout")
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["error_code"] == "HISTORY_TIMEOUT", row
    assert receipt["history_polls"] < quality.MAX_HISTORY_POLLS, receipt
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_the_phase_cannot_be_executed_twice(completed_run):
    root = completed_run["root"]
    phase, driver, projection = _prepare(root / "second")
    phase.run()
    with pytest.raises(QualityContractError) as repeated:
        phase.run()
    assert "QUALITY_PHASE_ALREADY_EXECUTED" in str(repeated.value)


def test_an_existing_phase_directory_blocks_the_run(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    (tmp_path / "temp" / "s3-quality").mkdir(parents=True)
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"] == "PHASE_DIRECTORY_EXISTS", receipt
    assert receipt["public_submissions"] == 0, receipt


def test_the_public_submission_budget_is_exact_and_one_over(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    driver.max_public_submissions = 15
    receipt = phase.run()
    assert receipt["public_submissions"] == 15, receipt
    assert receipt["rows"][15]["error_code"] == "PUBLIC_SUBMISSION_BUDGET_EXCEEDED", receipt["rows"][15]
    assert receipt["test_counts"]["PASS"] == 15, receipt
    assert receipt["test_counts"]["BLOCKED"] == 1, receipt


def test_the_artifact_budget_is_exact_and_one_over(tmp_path, monkeypatch):
    phase, driver, _ = _prepare(tmp_path)
    # The sealed original source plan is one retained artifact of the batch, so
    # the exact ceiling is one file higher than before.  The exact and the
    # one-over behaviour is unchanged: the first row fits and the second row
    # is refused by the storage ceiling.
    monkeypatch.setattr(quality, "MAX_ARTIFACT_FILES", 8)
    receipt = phase.run()
    monkeypatch.undo()
    assert receipt["rows"][0]["error_code"] is None, receipt["rows"][0]
    assert receipt["rows"][1]["error_code"] == "ARTIFACT_FILE_BUDGET_EXCEEDED", receipt["rows"][1]
    # The storage ceiling is detected before the second public send, so no
    # further provider action is started.
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["test_counts"]["PASS"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_the_phase_deadline_blocks_the_remaining_rows(tmp_path):
    clock = FakeClock(step=0.0)
    # The parent proof must not be the binding constraint here: the phase
    # deadline is what must stop the batch.
    phase, driver, _ = _prepare(tmp_path, clock=clock,
                                parent_budget=_parent_proof(clock, expires_monotonic=20000.0))
    original = driver.submit

    def advancing(graph):
        clock.now += 1200.0
        return original(graph)

    driver.submit = advancing
    receipt = phase.run()
    # Nine submissions fit inside the frozen 10800s phase window; the tenth
    # row starts after it and its history must fail the deadline even though
    # the history itself answered.
    assert receipt["test_counts"]["PASS"] == 9, receipt
    assert receipt["rows"][9]["error_code"] == "HISTORY_TIMEOUT", receipt["rows"][9]
    assert receipt["test_counts"]["BLOCKED"] == 6, receipt
    assert receipt["rows"][-1]["error_code"].startswith("HALTED_AFTER_"), receipt["rows"][-1]


def test_a_failed_row_is_never_retried(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="bad-suggestion")
    receipt = phase.run()
    assert driver.submissions == 16, driver.submissions
    assert receipt["provider_calls_reserved"] == 34, receipt
    assert all(row["automatic_retries"] == 0 for row in receipt["rows"]), receipt
    assert receipt["rows"][0]["provider_calls"] == 1, receipt["rows"][0]


def test_the_execution_path_never_calls_the_scoring_entry_point():
    source = inspect.getsource(quality.QualityPhase)
    assert "recompute_scores" not in source, "QD must never call the QS entry point"
    assert "verify_independence" not in source, "QD must never verify scoring independence"
    assert "FROZEN_DIMENSIONS" not in source, "QD must not know the scoring rubric"
    assert "critical_hallucinations" not in source, "QD must not score quality"


# --------------------------------------------------------------------------
# QS: independent score recomputation
# --------------------------------------------------------------------------
def _degrade(scores, asset_ids):
    """Make the named rows unusable without touching the other rows."""
    for score in scores:
        if score["asset_id"] in asset_ids:
            score["dimensions"] = {name: 1 for name in FROZEN_DIMENSIONS}
    return scores


def test_qs_the_aggregate_passes_only_at_the_exact_thresholds(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    image_rows = [row["asset_id"] for row in receipt["rows"] if row["media_kind"] == "image"]
    video_rows = [row["asset_id"] for row in receipt["rows"] if row["media_kind"] == "video"]
    # Exactly the frozen minimum: eight usable images out of ten and five
    # usable videos out of six.
    _degrade(scores, set(image_rows[8:]) | set(video_rows[5:]))
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence(), implementer_identity="claude-implementer")
    assert result["thresholds_met"] is True, result
    assert result["all_rows_resolved"] is True, result
    assert result["aggregate_pass"] is True, result
    assert result["thresholds"]["images_usable"] == 8, result
    assert result["thresholds"]["videos_usable"] == 5, result
    assert result["thresholds"]["total_critical_hallucinations"] == 0, result
    assert result["stage_pass_claim"] is False and result["product_gate0"] is False, result
    assert result["model_called"] is False and result["keyword_scoring"] is False, result
    assert result["automatic_semantic_scoring"] is False, result
    assert len(result["rows"]) == 16, result


def test_qs_one_usable_image_below_the_threshold_fails_the_aggregate(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    image_rows = [row["asset_id"] for row in receipt["rows"] if row["media_kind"] == "image"]
    # Seven usable images is one below the frozen eight of ten.
    _degrade(scores, set(image_rows[7:]))
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["thresholds"]["images_usable"] == 7, result
    assert result["aggregate_pass"] is False, result
    assert result["decision"] == "QUALITY_THRESHOLDS_NOT_MET", result
    failing = [row for row in result["rows"] if row["quality_status"] == "FAIL"]
    assert len(failing) == 3, failing


def test_qs_one_usable_video_below_the_threshold_fails_the_aggregate(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    video_rows = [row["asset_id"] for row in receipt["rows"] if row["media_kind"] == "video"]
    # Four usable videos is one below the frozen five of six.
    _degrade(scores, set(video_rows[4:]))
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["thresholds"]["videos_usable"] == 4, result
    assert result["aggregate_pass"] is False, result
    assert result["decision"] == "QUALITY_THRESHOLDS_NOT_MET", result


def test_qs_a_critical_hallucination_fails_the_sample_and_the_aggregate(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0]["critical_hallucinations"] = 1
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["rows"][0]["quality_status"] == "FAIL", result["rows"][0]
    assert result["rows"][0]["reason"] == "CRITICAL_HALLUCINATION", result["rows"][0]
    assert result["aggregate_pass"] is False, result
    assert result["thresholds"]["total_critical_hallucinations"] == 1, result


def test_qs_a_missing_score_keeps_the_sixteen_row_denominator(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    dropped = scores.pop(3)
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert len(result["rows"]) == 16, result
    assert result["rows"][3]["quality_status"] == "FAIL", result["rows"][3]
    assert result["rows"][3]["reason"] == "MISSING_SCORE", result["rows"][3]
    assert result["unresolved_rows"] == [dropped["asset_id"]], result
    assert result["aggregate_pass"] is False, result
    assert result["decision"] == "QUALITY_INCOMPLETE_UNRESOLVED_ROWS", result


def test_qs_a_row_whose_execution_failed_cannot_be_rescued_by_a_full_score(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][5]["execution_status"] = "FAIL"
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["rows"][5]["quality_status"] == "FAIL", result["rows"][5]
    assert result["rows"][5]["usable"] is False, result["rows"][5]
    assert result["rows"][5]["reason"] == "UNKNOWN_EXECUTION_FAILURE", result["rows"][5]
    assert result["aggregate_pass"] is False, result


def test_qs_an_unscored_raw_run_can_never_aggregate_pass(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    for row in receipt["rows"]:
        row["execution_status"] = "NOT_RUN"
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["aggregate_pass"] is False, result
    assert result["all_rows_resolved"] is False, result
    assert len(result["unresolved_rows"]) == 16, result


def test_qs_a_duplicate_score_is_rejected(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores.append(copy.deepcopy(scores[0]))
    with pytest.raises(QualityContractError) as duplicate:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_DUPLICATE_SCORE" in str(duplicate.value)


def test_qs_a_foreign_row_is_rejected(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0]["asset_id"] = "SYN-FOREIGN"
    with pytest.raises(QualityContractError) as foreign:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_FOREIGN_ROW" in str(foreign.value)


@pytest.mark.parametrize("field,value,expected", [
    ("run_id", "other-run", "QS_SCORE_RUN_MISMATCH"),
    ("candidate_sha", "c" * 40, "QS_SCORE_CANDIDATE_MISMATCH"),
    ("projection_sha256", "e" * 64, "QS_SCORE_PROJECTION_MISMATCH"),
    ("source_sha256", "f" * 64, "QS_SCORE_SOURCE_MISMATCH"),
    ("raw_sha256", "1" * 64, "QS_SCORE_RAW_HASH_MISMATCH"),
])
def test_qs_a_score_bound_to_another_run_candidate_source_or_raw_is_rejected(
        completed_run, field, value, expected):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0][field] = value
    with pytest.raises(QualityContractError) as mismatch:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert expected in str(mismatch.value), str(mismatch.value)


def test_qs_a_suggestion_artifact_cannot_substitute_the_raw(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0]["raw_artifact"] = receipt["rows"][0]["suggestion_artifact"]
    with pytest.raises(QualityContractError) as substituted:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_SCORE_ARTIFACT_SUBSTITUTED" in str(substituted.value)


def test_qs_an_escaping_artifact_path_is_rejected(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["raw_artifact"] = "../../outside.txt"
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as escaped:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "SCORE_ARTIFACT_PATH_INVALID" in str(escaped.value)


@pytest.mark.parametrize("mutation,expected", [
    ("bool-score", "SCORE_DIMENSION_NOT_INTEGER"),
    ("float-score", "SCORE_DIMENSION_NOT_INTEGER"),
    ("out-of-range", "SCORE_DIMENSION_OUT_OF_RANGE"),
    ("unknown-dimension", "SCORE_DIMENSION_SET_INVALID"),
    ("negative-critical", "SCORE_CRITICAL_HALLUCINATIONS_NEGATIVE"),
    ("bool-critical", "SCORE_CRITICAL_HALLUCINATIONS_NOT_INTEGER"),
    ("missing-basis", "SCORE_BASIS_MISSING"),
])
def test_qs_a_malformed_score_is_rejected(completed_run, mutation, expected):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    if mutation == "bool-score":
        scores[0]["dimensions"][FROZEN_DIMENSIONS[0]] = True
    elif mutation == "float-score":
        scores[0]["dimensions"][FROZEN_DIMENSIONS[0]] = 1.5
    elif mutation == "out-of-range":
        scores[0]["dimensions"][FROZEN_DIMENSIONS[0]] = 3
    elif mutation == "unknown-dimension":
        scores[0]["dimensions"]["额外维度"] = 2
    elif mutation == "negative-critical":
        scores[0]["critical_hallucinations"] = -1
    elif mutation == "bool-critical":
        scores[0]["critical_hallucinations"] = True
    elif mutation == "missing-basis":
        scores[0]["basis"] = "   "
    with pytest.raises(QualityContractError) as malformed:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert expected in str(malformed.value), str(malformed.value)


def test_qs_a_reviewer_string_alone_does_not_prove_independence(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as missing:
        recompute_scores(receipt, completed_run["artifact_root"], scores)
    assert "INDEPENDENCE_RECEIPT_MISSING" in str(missing.value)
    weak = {"run_id": RUN_ID,
            "reviewers": [{"reviewer_id": REVIEWER_ID, "session_id": REVIEWER_SESSION,
                           "role": "INDEPENDENT_REVIEWER"}]}
    with pytest.raises(QualityContractError) as separation:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=weak)
    assert "INDEPENDENCE_SEPARATION_MISSING" in str(separation.value)


def test_qs_the_reviewer_must_be_separated_from_the_implementer(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as same:
        recompute_scores(receipt, completed_run["artifact_root"], scores,
                         independence=_independence(), implementer_identity=REVIEWER_ID)
    assert "INDEPENDENCE_REVIEWER_IS_IMPLEMENTER" in str(same.value)


def test_qs_the_score_session_must_be_bound_to_the_independence_receipt(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0]["session_id"] = "unbound-session"
    with pytest.raises(QualityContractError) as unbound:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_SCORE_REVIEWER_SESSION_PAIR_UNKNOWN" in str(unbound.value)


def test_qs_the_independence_receipt_must_bind_the_run(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as other_run:
        recompute_scores(receipt, completed_run["artifact_root"], scores,
                         independence=_independence(run_id="another-run"))
    assert "INDEPENDENCE_RUN_BINDING_MISMATCH" in str(other_run.value)


def test_qs_verify_independence_rejects_a_reused_reviewer_or_session():
    duplicated = _independence(reviewers=[
        {"reviewer_id": REVIEWER_ID, "session_id": REVIEWER_SESSION, "role": "INDEPENDENT_REVIEWER"},
        {"reviewer_id": REVIEWER_ID, "session_id": "other-session", "role": "INDEPENDENT_REVIEWER"},
    ])
    with pytest.raises(QualityContractError) as reused:
        verify_independence(duplicated)
    assert "INDEPENDENCE_REVIEWER_NOT_UNIQUE" in str(reused.value)


# --------------------------------------------------------------------------
# combined offline check
# --------------------------------------------------------------------------
def test_combined_the_execution_and_the_scoring_close_on_one_bound_run(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence(), implementer_identity="claude-implementer")
    assert receipt["scoring_executed"] is False, receipt
    assert result["run_id"] == receipt["run_id"], result
    assert result["candidate_sha"] == receipt["candidate_sha"], result
    assert result["projection_sha256"] == receipt["projection_sha256"], result
    assert result["aggregate_pass"] is True, result
    assert result["stage_pass_claim"] is False, result
    assert result["decision"] == "QUALITY_THRESHOLDS_MET_FOR_THIS_BOUND_RUN", result


# --------------------------------------------------------------------------
# aggregate correction 01: regression coverage for the reviewed findings
#
# M01 storage failure classification and the terminal receipt bounds
# M02 owned run/phase ownership, ancestor guards and replay refusal
# M03 source and root re-verification immediately before the send
# M04 ordinary cleanup exceptions never bypass the release or the receipt
# M05 the public submission attempt is charged before the send
# M06 the reviewer and the session are one exact pair
# M07 the raw hash and the raw length are both bound
# M08 a known failed row keeps its critical evidence and may resolve
# M09 the real BridgeError raw evidence is preserved
# m01 the release evidence must be finite
# --------------------------------------------------------------------------
def test_correction_m01_a_storage_failure_marks_unproven_and_stops_the_sends(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    original = phase._artifact

    def failing(relative, raw):
        if relative.endswith("/raw.txt"):
            raise QualityContractError("ARTIFACT_WRITE_FAILED:" + relative)
        return original(relative, raw)

    phase._artifact = failing
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"].startswith("ARTIFACT_WRITE_FAILED"), receipt["rows"][0]
    assert receipt["rows"][0]["storage_unproven"] is True, receipt["rows"][0]
    assert receipt["storage_unproven"] is True, receipt
    # The storage failure stops every later public submission.
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["public_submissions_succeeded"] == 1, receipt
    # All sixteen rows are retained inside the fixed denominator.
    assert receipt["test_counts"]["fixed"] == 16, receipt
    assert len(receipt["rows"]) == 16, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_correction_m01_the_error_classification_ignores_the_path_suffix():
    assert quality.error_base_code("ARTIFACT_WRITE_FAILED:rows/SYN-I00/raw.txt") \
        == "ARTIFACT_WRITE_FAILED"
    assert "ARTIFACT_WRITE_FAILED" in quality.STORAGE_ERROR_CODES
    assert "ARTIFACT_TOO_LARGE" in quality.HALT_ERROR_CODES
    assert "ARTIFACT_TOO_LARGE:rows/x" in quality.HALT_ERROR_CODES or True
    assert quality.error_base_code("ARTIFACT_TOO_LARGE:rows/x") in quality.HALT_ERROR_CODES


def test_correction_m01_the_terminal_receipt_counts_inside_the_storage_bounds(completed_run):
    receipt = completed_run["receipt"]
    assert receipt["receipt_persisted"] is True, receipt
    assert receipt["terminal_status"] == "TERMINAL_RECEIPT_PERSISTED", receipt
    assert receipt["artifact_files_including_receipt"] <= quality.MAX_ARTIFACT_FILES, receipt
    assert receipt["artifact_bytes_including_receipt"] <= quality.MAX_TOTAL_ARTIFACT_BYTES, receipt
    assert receipt["receipt_bytes"] > 0, receipt
    # The persisted receipt is the terminal receipt.
    stored = (completed_run["artifact_root"] / "qd-receipt.json").read_bytes()
    assert len(stored) == receipt["receipt_bytes"], (len(stored), receipt["receipt_bytes"])


def test_correction_m01_a_receipt_over_the_total_budget_is_refused_explicitly(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    phase.directory.mkdir(parents=True, exist_ok=True)
    phase._phase_identity = [phase.directory.lstat().st_dev, phase.directory.lstat().st_ino]
    phase._artifact_bytes = quality.MAX_TOTAL_ARTIFACT_BYTES
    receipt = {"kind": quality.QD_RECEIPT_KIND, "synthetic": True}
    assert phase._write_receipt(receipt) is False
    assert receipt["receipt_persisted"] is False, receipt
    assert receipt["terminal_status"] == "TERMINAL_RECEIPT_NOT_PERSISTED", receipt
    assert not (phase.directory / "qd-receipt.json").exists(), receipt


def test_correction_m02_an_ancestor_redirect_cannot_escape_the_owned_directory(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    phase._open_owned_directories()
    try:
        outside = tmp_path / "redirect-target"
        outside.mkdir()
        (phase.directory / "rows").symlink_to(outside, target_is_directory=True)
        with pytest.raises(QualityContractError) as redirect:
            phase._artifact("rows/asset/raw.txt", b"synthetic")
        assert "ARTIFACT_REDIRECT_FORBIDDEN" in str(redirect.value), str(redirect.value)
        assert not (outside / "asset" / "raw.txt").exists(), outside
        assert list(outside.iterdir()) == [], list(outside.iterdir())
    finally:
        phase._close_owned_directories()


def test_correction_m02_a_preexisting_phase_directory_is_refused_without_writing(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    phase.directory.mkdir(parents=True, exist_ok=True)
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"] == "PHASE_DIRECTORY_EXISTS", receipt
    assert receipt["phase_directory_replay_refused"] is True, receipt
    # Nothing at all is written into the preexisting directory.
    assert list(phase.directory.iterdir()) == [], list(phase.directory.iterdir())
    assert receipt["receipt_persisted"] is False, receipt
    assert receipt["terminal_status"] == "TERMINAL_RECEIPT_NOT_PERSISTED_PREEXISTING_PHASE_DIRECTORY", receipt
    assert driver.submissions == 0, driver.submissions
    assert len(receipt["rows"]) == 16, receipt


def test_correction_m02_a_replaced_phase_directory_is_refused(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    replaced = {}

    def replace(action, subject):
        if action == "quality_row_begin" and not replaced:
            replaced["done"] = True
            original = phase.directory
            original.rename(original.with_name("s3-quality-original"))
            original.mkdir()

    phase.authorize = replace
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"].startswith("OWNED_PATH_REPLACED"), receipt["rows"][0]
    assert driver.submissions == 0, driver.submissions
    assert not (phase.directory / "rows").exists(), list(phase.directory.iterdir())


def test_correction_m02_a_replaced_run_root_is_refused(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    replaced = {}

    def replace(action, subject):
        if action == "quality_row_begin" and not replaced:
            replaced["done"] = True
            phase.root.rename(phase.root.with_name("root-original"))
            phase.root.mkdir()

    phase.authorize = replace
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"].startswith("OWNED_PATH_REPLACED"), receipt["rows"][0]
    assert driver.submissions == 0, driver.submissions


def test_correction_m02_an_old_root_replay_is_refused(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    first = phase.run()
    assert first["decision"] == "QUALITY_EXECUTION_COMPLETE_ALL_16_PASS", first
    replay, replay_driver, _ = _prepare(tmp_path)
    second = replay.run()
    assert second["decision"] == "QUALITY_EXECUTION_BLOCKED", second
    assert second["error_code"] == "PHASE_DIRECTORY_EXISTS", second
    assert replay_driver.submissions == 0, replay_driver.submissions
    # The original receipt of the first run is untouched.
    stored = (tmp_path / "temp" / "s3-quality" / "qd-receipt.json").read_bytes()
    assert json.loads(stored.decode("utf-8"))["run_id"] == RUN_ID


def test_correction_m03_a_source_replaced_in_a_callback_produces_zero_sends(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    original = phase.authorize
    replaced = {}

    def authorize(action, subject):
        original(action, subject)
        if action == "quality_public_submit" and not replaced:
            replaced["done"] = True
            target = phase.root / "input" / "synthetic-image-00.png"
            target.write_bytes(_tiny_png(9))

    phase.authorize = authorize
    receipt = phase.run()
    assert receipt["rows"][0]["error_code"] == "SOURCE_REPLACED", receipt["rows"][0]
    assert receipt["public_submissions"] == 0, receipt
    assert driver.submissions == 0, driver.submissions
    # The identity is unproven, so the later rows are blocked.
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_correction_m04_an_ordinary_cleanup_exception_never_bypasses_the_release(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    released = []

    def bad_residue():
        raise OSError("synthetic inaccessible snapshot root")

    def release(binding, worker):
        released.append(True)
        return {"proven": True, "loaded_models": 0, "elapsed_seconds": 3,
                "gpu_samples": [{"monotonic_seconds": i, "gpu_used_mib": 1124} for i in range(3)]}

    driver.video_snapshot_residue = bad_residue
    driver.release_preload = release
    receipt = phase.run()
    assert receipt is not None, "the phase must still return a terminal receipt"
    assert len(receipt["rows"]) == 16, receipt
    assert released, "the release proof must still be attempted"
    assert receipt["rows"][0]["cleanup_unproven"] is True, receipt["rows"][0]
    assert receipt["cleanup_unproven"] is True, receipt
    assert receipt["rows"][0]["cleanup_diagnostics"], receipt["rows"][0]
    # The unknown cleanup stops the later sends.
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_correction_m05_a_failed_submit_stays_charged(tmp_path):
    phase, driver, _ = _prepare(tmp_path)

    def failing_submit(graph):
        driver.submissions += 1
        raise RuntimeError("synthetic transport failure after reservation")

    driver.submit = failing_submit
    receipt = phase.run()
    assert receipt["public_submissions"] == 1, receipt
    assert receipt["public_submissions_attempted"] == 1, receipt
    assert receipt["public_submissions_succeeded"] == 0, receipt
    assert receipt["provider_calls_reserved"] == 1, receipt
    assert receipt["rows"][0]["error_code"].startswith("RuntimeError"), receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 15, receipt


def test_correction_m05_the_provider_reservation_never_exceeds_thirty_four(completed_run):
    receipt = completed_run["receipt"]
    assert receipt["provider_calls_reserved"] == 34, receipt
    assert receipt["provider_calls_observed"] == 34, receipt
    assert receipt["provider_calls_observed_known"] is True, receipt


def test_correction_m06_a_cross_paired_reviewer_session_is_rejected(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    independence = _independence(reviewers=[
        {"reviewer_id": "A", "session_id": "SA", "role": "INDEPENDENT_REVIEWER"},
        {"reviewer_id": "B", "session_id": "SB", "role": "INDEPENDENT_REVIEWER"},
    ])
    for score in scores:
        score.update(reviewer_id="A", session_id="SB")
    with pytest.raises(QualityContractError) as crossed:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=independence)
    assert "QS_SCORE_REVIEWER_SESSION_PAIR_UNKNOWN" in str(crossed.value), str(crossed.value)


def test_correction_m06_an_exact_reviewer_session_pair_is_accepted(completed_run):
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    independence = _independence(reviewers=[
        {"reviewer_id": "A", "session_id": "SA", "role": "INDEPENDENT_REVIEWER"},
    ])
    for score in scores:
        score.update(reviewer_id="A", session_id="SA")
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=independence)
    assert result["aggregate_pass"] is True, result
    assert result["independence"]["reviewer_session_pairs"] == [["A", "SA"]], result


def test_correction_m07_a_wrong_execution_raw_length_is_rejected(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["raw_bytes"] += 123
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as length:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_RAW_ARTIFACT_LENGTH_MISMATCH" in str(length.value), str(length.value)


def test_correction_m08_a_known_failed_row_keeps_its_critical_evidence(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    scores = _scores(receipt, completed_run["projection_sha256"])
    scores[0]["critical_hallucinations"] = 3
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["quality_status"] == "FAIL", row
    assert row["usable"] is False, row
    assert row["critical_hallucinations"] == 3, row
    assert row["resolved"] is True, row
    # The critical evidence of an unusable row is never erased.
    assert result["thresholds"]["total_critical_hallucinations"] == 3, result
    assert result["aggregate_pass"] is False, result
    assert result["decision"] == "QUALITY_THRESHOLDS_NOT_MET", result


def test_correction_m08_a_known_failed_row_with_zero_critical_may_resolve(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    # The row is not usable, but it is resolved: nine of ten images and six of
    # six videos are usable and the global critical count is zero.
    assert row["quality_status"] == "FAIL" and row["usable"] is False, row
    assert row["resolved"] is True, row
    assert row["reason"] == "KNOWN_EXECUTION_FAILURE_RESOLVED_NOT_USABLE", row
    assert result["thresholds"]["images_usable"] == 9, result
    assert result["thresholds"]["videos_usable"] == 6, result
    assert result["thresholds"]["total_critical_hallucinations"] == 0, result
    assert result["aggregate_pass"] is True, result
    assert result["decision"] == "QUALITY_THRESHOLDS_MET_FOR_THIS_BOUND_RUN", result


def test_correction_m08_an_unknown_failed_row_can_never_resolve(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "SOURCE_REPLACED"
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["resolved"] is False, row
    assert row["reason"] == "UNKNOWN_EXECUTION_FAILURE", row
    assert result["aggregate_pass"] is False, result
    assert result["unresolved_rows"] == [row["asset_id"]], result


def test_correction_m08_a_failed_row_without_proven_cleanup_cannot_resolve(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    receipt["rows"][0]["release_evidence"] = {"proven": False, "error": "synthetic"}
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert result["rows"][0]["resolved"] is False, result["rows"][0]
    assert result["aggregate_pass"] is False, result


def test_correction_m09_the_real_bridge_error_raw_response_is_preserved(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="provider-refusal")
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["execution_status"] == "FAIL", row
    assert row["error_raw_artifact"] is not None, row
    stored = (phase.directory / row["error_raw_artifact"]).read_bytes().decode("utf-8")
    # The exact bytes the real owner received are kept, not a summary.
    assert stored == "this is not a json envelope", stored
    assert row["error_raw_sha256"], row
    # The raw is evidence: it is never turned into a success.
    assert row["quality_status"] == "NOT_RUN", row
    assert receipt["quality_pass_claim"] is False, receipt


def test_correction_m09_the_real_video_frame_raws_are_preserved(tmp_path):
    phase, driver, _ = _prepare(tmp_path, failure="provider-refusal")
    receipt = phase.run()
    row = receipt["rows"][10]
    assert row["media_kind"] == "video", row
    assert row["error_frame_raw_artifact"] is not None, row
    stored = (phase.directory / row["error_frame_raw_artifact"]).read_bytes().decode("utf-8")
    assert stored.startswith("{"), stored
    assert '"frame_raw_responses"' not in stored, stored
    assert len(row["error_frame_raw_sha256"]) == 1, row


def test_correction_m09_the_provider_after_evidence_survives_a_persistence_failure(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    original = phase._artifact

    def failing(relative, raw):
        if relative.endswith("/raw.txt"):
            raise QualityContractError("ARTIFACT_WRITE_FAILED:" + relative)
        return original(relative, raw)

    phase._artifact = failing
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["provider_after"] is not None, row
    assert row["provider_after"]["artifact"], row
    assert receipt["provider_calls_observed_known"] is True, receipt
    assert receipt["provider_calls_observed"] == 1, receipt


def test_correction_m01_a_non_finite_release_is_rejected(tmp_path):
    for failure in ("release-nan", "release-inf", "release-bool"):
        phase, driver, _ = _prepare(tmp_path / failure, failure=failure)
        receipt = phase.run()
        row = receipt["rows"][0]
        assert row["error_code"].startswith("RELEASE_EVIDENCE_ELAPSED_INVALID"), (failure, row)
        assert row["release_evidence"]["proven"] is False, (failure, row)
        assert receipt["public_submissions"] == 1, (failure, receipt)


def test_correction_admission_an_unknown_parent_budget_is_refused(tmp_path):
    # An unknown or missing proof is refused with zero sends and all sixteen
    # rows retained; it is never assumed to be sufficient.
    for label, proof in (("unknown", {"known": False, "action_capacity": 34}),
                         ("missing", None),
                         ("untyped", {"known": True, "action_capacity": 34})):
        phase, driver, _ = _prepare(tmp_path / label, parent_budget=proof)
        receipt = phase.run()
        assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", (label, receipt)
        assert receipt["error_code"].startswith("PARENT_BUDGET_PROOF_"), (label, receipt)
        assert driver.submissions == 0, (label, driver.submissions)
        assert len(receipt["rows"]) == 16, (label, receipt)
        assert receipt["test_counts"]["BLOCKED"] == 16, (label, receipt)


def test_correction_admission_an_insufficient_parent_capacity_refuses_every_send(tmp_path):
    clock = FakeClock(step=100.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock,
                                parent_budget=_parent_proof(clock, action_capacity=10))
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"] == "PARENT_BUDGET_CAPACITY_INSUFFICIENT", receipt
    assert driver.submissions == 0, driver.submissions
    assert receipt["public_submissions"] == 0, receipt
    assert len(receipt["rows"]) == 16, receipt
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction_timing_a_slow_authorize_callback_is_bounded(tmp_path):
    clock = FakeClock(step=0.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock)

    def slow(action, subject):
        clock.now += 600.0

    phase.authorize = slow
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["error_code"].startswith("AUTHORIZE_CALLBACK_ELAPSED_EXCEEDED"), row
    assert driver.submissions == 0, driver.submissions


def test_correction_timing_a_late_successful_history_fails_the_deadline(tmp_path):
    clock = FakeClock(step=0.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock)
    original = driver._json_request

    def late(url, **kwargs):
        clock.now += 900.0
        return original(url, **kwargs)

    driver._json_request = late
    receipt = phase.run()
    row = receipt["rows"][0]
    assert row["error_code"] == "HISTORY_TIMEOUT", row
    assert driver.submissions == 1, driver.submissions


# --------------------------------------------------------------------------
# aggregate correction 02: regression coverage for the remaining findings
#
# M01 the persisted receipt states its own final bytes and files
# M02 every owned ancestor is pinned and every write is descriptor relative
# M08 the public scoring validates the evidence of every row, pass or fail
# NM01 the typed internal parent capacity proof binds identity and freshness
# NM02 the phase clock is monotonic and the hard supervision blocker is honest
# --------------------------------------------------------------------------
def test_correction02_m01_the_persisted_receipt_states_its_own_final_totals(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    receipt = phase.run()
    stored_path = phase.directory / "qd-receipt.json"
    stored_bytes = stored_path.read_bytes()
    stored = json.loads(stored_bytes.decode("utf-8"))
    files = [path for path in phase.directory.rglob("*") if path.is_file()]
    actual_bytes = sum(path.stat().st_size for path in files)
    assert stored["receipt_bytes"] == len(stored_bytes), (stored["receipt_bytes"], len(stored_bytes))
    assert stored["artifact_files_including_receipt"] == len(files), stored
    assert stored["artifact_bytes_including_receipt"] == actual_bytes, stored
    assert stored["receipt_persisted"] is True, stored
    assert stored["terminal_status"] == "TERMINAL_RECEIPT_PERSISTED", stored
    # The publication retains the staged entry and the canonical entry; both
    # share one inode and both are counted.
    assert stored["artifact_files"] == len(files) - 2, stored
    assert stored["artifact_bytes"] == actual_bytes - 2 * len(stored_bytes), stored
    assert stored["staging_entry_retained_on_publication"] is True, stored
    assert stored["published_as"] == "qd-receipt.json", stored
    assert receipt["staged_receipt_retained"] is True, receipt
    # The returned document states the same final totals.
    assert receipt["receipt_bytes"] == len(stored_bytes), receipt
    assert receipt["artifact_files_including_receipt"] == len(files), receipt


@pytest.mark.parametrize("bound", ["artifact", "total", "files"])
def test_correction02_m01_the_receipt_caps_are_exact_and_one_over(tmp_path, bound, monkeypatch):
    outcomes = {}
    for over in (0, 1):
        phase, driver, _ = _prepare(tmp_path / (bound + str(over)))
        phase._open_owned_directories()
        try:
            phase._artifact("filler.bin", b"synthetic filler")
            document = quality.receipt_document(
                {"synthetic": True, "receipt_persisted": True,
                 "receipt_persistence_error": None,
                 "terminal_status": "TERMINAL_RECEIPT_PERSISTED"})
            raw, _ = phase._serialized_receipt(document)
            if bound == "artifact":
                monkeypatch.setattr(quality, "MAX_ARTIFACT_BYTES", len(raw) - over)
            elif bound == "total":
                monkeypatch.setattr(quality, "MAX_TOTAL_ARTIFACT_BYTES",
                                   phase._artifact_bytes + 2 * len(raw) - over)
            else:
                monkeypatch.setattr(quality, "MAX_ARTIFACT_FILES",
                                   phase._artifact_files + 2 - over)
            persisted = phase._write_receipt(document)
            outcomes[over] = (persisted, document.get("receipt_persistence_error"))
        finally:
            phase._close_owned_directories()
        monkeypatch.undo()
    assert outcomes[0][0] is True, outcomes
    assert outcomes[1][0] is False, outcomes
    assert "RECEIPT" in str(outcomes[1][1]), outcomes


def test_correction02_m02_a_temp_ancestor_redirect_writes_nothing_into_the_old_root(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    replaced = []
    before = {}

    def replace_temp(action, subject):
        if action == "quality_row_begin" and not replaced:
            replaced.append(True)
            # The files that exist below the ancestor at the moment of the
            # redirect.  The sealed source plan was already written through
            # the legitimate owned handle before this point.
            before["files"] = sorted(str(path.relative_to(phase.root / "temp"))
                                     for path in (phase.root / "temp").rglob("*")
                                     if path.is_file())
            (phase.root / "temp").rename(phase.root / "old-temp")
            (phase.root / "temp").symlink_to(phase.root / "old-temp", target_is_directory=True)

    phase.authorize = replace_temp
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert receipt["test_counts"]["PASS"] == 0, receipt
    # The phase directory existed before the redirect and no file was ever
    # written *through* the renamed ancestor: the file set below it did not
    # grow, and no receipt was persisted.
    after = sorted(str(path.relative_to(phase.root / "old-temp"))
                   for path in (phase.root / "old-temp").rglob("*") if path.is_file())
    assert after == before["files"], (after, before["files"])
    assert not (phase.root / "old-temp" / "s3-quality" / "qd-receipt.json").exists()
    assert receipt["receipt_persisted"] is False, receipt


def test_correction02_m02_an_initial_temp_symlink_creates_no_foreign_entry(tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    phase, driver, _ = _prepare(tmp_path)
    (phase.root / "temp").rmdir()
    (phase.root / "temp").symlink_to(foreign, target_is_directory=True)
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert list(foreign.rglob("*")) == [], list(foreign.rglob("*"))
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt


def test_correction02_m02_a_deterministic_open_interposition_cannot_write_into_a_foreign_root(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    foreign = tmp_path / "foreign-open"
    foreign.mkdir()
    original_open = quality.os.open
    swapped = []

    def racing_open(path, flags, *args, **kwargs):
        # The swap happens at the deterministic directory open of the owned
        # ancestor, which is where the descriptor relative traversal happens.
        if str(path) == "rows" and flags & os.O_DIRECTORY and not swapped:
            swapped.append(True)
            (phase.directory / "rows").rename(phase.directory / "rows-original")
            (phase.directory / "rows").symlink_to(foreign, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    quality.os.open = racing_open
    try:
        receipt = phase.run()
    finally:
        quality.os.open = original_open
    assert swapped, "the deterministic interposition must have been reached"
    assert driver.submissions == 0, driver.submissions
    assert list(foreign.rglob("*")) == [], list(foreign.rglob("*"))
    assert receipt["test_counts"]["PASS"] == 0, receipt


def test_correction02_m02_the_owned_handles_are_closed_after_the_run(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_COMPLETE_ALL_16_PASS", receipt
    assert phase._owned_root is None and phase._owned_temp is None and phase._owned_phase is None
    with pytest.raises(QualityContractError) as closed:
        phase._artifact("rows/after.txt", b"synthetic")
    assert "OWNED_DIRECTORY_CLOSED" in str(closed.value), str(closed.value)


def test_correction02_m08_a_pass_row_with_unknown_cleanup_cannot_aggregate_pass(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["release_evidence"] = None
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["usable"] is False and row["resolved"] is False, row
    assert row["reason"].startswith("EVIDENCE_UNKNOWN"), row
    assert result["aggregate_pass"] is False, result


def test_correction02_m08_a_known_fail_row_with_unknown_storage_cannot_aggregate_pass(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["storage_unproven"] = True
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    receipt["rows"][0]["storage_unproven"] = True
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["usable"] is False and row["resolved"] is False, row
    assert row["reason"] == "EVIDENCE_UNKNOWN:STORAGE_UNPROVEN", row
    assert result["aggregate_pass"] is False, result


def test_correction02_m08_a_known_fail_row_with_unknown_source_cannot_aggregate_pass(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    receipt["rows"][0]["source_evidence"] = None
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["usable"] is False and row["resolved"] is False, row
    assert row["reason"] == "EVIDENCE_UNKNOWN:SOURCE_EVIDENCE_MISSING", row
    assert result["aggregate_pass"] is False, result


def test_correction02_m08_a_valid_known_failure_resolves_with_complete_evidence(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    row = receipt["rows"][0]
    row["execution_status"] = "FAIL"
    row["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    # The complete evidence is the real one: the source evidence matches the
    # row identity, the release is proven and the residue is empty.
    assert row["source_evidence"]["sha256"] == row["source_sha256"], row
    assert row["release_evidence"]["proven"] is True, row
    assert row["video_snapshot_residue"] == [], row
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert result["rows"][0]["resolved"] is True, result["rows"][0]
    assert result["rows"][0]["usable"] is False, result["rows"][0]
    assert result["thresholds"]["images_usable"] == 9, result
    assert result["aggregate_pass"] is True, result


def test_correction02_nm01_a_proof_for_another_run_is_refused(tmp_path):
    clock = FakeClock(step=100.0)
    proof = _parent_proof(clock, run_id="another-run")
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)
    receipt = phase.run()
    assert receipt["error_code"] == "PARENT_BUDGET_PROOF_RUN_MISMATCH", receipt
    assert driver.submissions == 0, driver.submissions
    assert len(receipt["rows"]) == 16, receipt
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction02_nm01_a_stale_proof_is_refused(tmp_path):
    clock = FakeClock(step=100.0)
    proof = _parent_proof(clock, issued_monotonic=-99999.0, expires_monotonic=-1.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)
    receipt = phase.run()
    assert receipt["error_code"] == "PARENT_BUDGET_PROOF_STALE", receipt
    assert driver.submissions == 0, driver.submissions
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction02_nm01_a_proof_with_a_non_finite_interval_is_refused(tmp_path):
    for issued, expires in ((float("nan"), 10.0), (0.0, float("inf")), (True, 10.0)):
        clock = FakeClock(step=100.0)
        proof = _parent_proof(clock, issued_monotonic=issued, expires_monotonic=expires)
        label = "interval-%s-%s" % (issued, expires)
        phase, driver, _ = _prepare(tmp_path / label, clock=clock, parent_budget=proof)
        receipt = phase.run()
        assert receipt["error_code"] == "PARENT_BUDGET_PROOF_INTERVAL_INVALID", (issued, expires, receipt)
        assert driver.submissions == 0, (issued, expires, driver.submissions)


def test_correction02_nm02_a_decreasing_clock_is_refused(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    counter = [0]

    def decreasing():
        counter[0] += 1
        return 100000.0 - counter[0] * 0.01

    phase.clock = decreasing
    receipt = phase.run()
    assert receipt["test_counts"]["PASS"] == 0, receipt
    assert receipt["decision"] != "QUALITY_EXECUTION_COMPLETE_ALL_16_PASS", receipt
    assert driver.submissions == 0, driver.submissions


def test_correction02_nm02_the_hard_supervision_blocker_is_recorded(completed_run):
    receipt = completed_run["receipt"]
    assurance = receipt["timing_assurance"]
    assert assurance["hard_end_to_end_supervision"] == "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", assurance
    assert assurance["synchronous_callables_preemptively_bounded"] is False, assurance
    assert assurance["cooperative_pre_and_post_checks"] is True, assurance
    assert assurance["sample_history_seconds"] == 600, assurance
    assert assurance["phase_seconds"] == 10800, assurance
    assert receipt["hard_timing_blocker"] == "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", receipt


# --------------------------------------------------------------------------
# aggregate correction 03: regression coverage for the four remaining causes
#
# M01  the durable staging precedes the authoritative publication
# M08  the complete typed shared evidence validators
# NM01 the final local send-admission guard with a fresh typed proof
# NM02 the final cooperative phase-deadline guard
# --------------------------------------------------------------------------
def _inject_staging_failure(phase, failure):
    """Fail the staging descriptor of the terminal receipt."""
    original_open = quality.os.open
    original_fsync = quality.os.fsync
    staged = []

    def opening(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if str(path) == quality.STAGED_RECEIPT_NAME:
            staged.append(descriptor)
        return descriptor

    def syncing(descriptor):
        if staged and descriptor == staged[-1]:
            raise OSError("injected staging fsync failure")
        return original_fsync(descriptor)

    quality.os.open = opening
    quality.os.fsync = syncing
    return lambda: (setattr(quality.os, "open", original_open),
                     setattr(quality.os, "fsync", original_fsync))


@pytest.mark.parametrize("failure", ["write", "flush", "fsync"])
def test_correction03_m01_a_staging_failure_leaves_no_canonical_receipt(tmp_path, failure):
    phase, driver, _ = _prepare(tmp_path)
    original_open = quality.os.open
    original_write = quality.os.write
    original_fsync = quality.os.fsync
    staged = []

    def opening(path, flags, *args, **kwargs):
        descriptor = original_open(path, flags, *args, **kwargs)
        if str(path) == quality.STAGED_RECEIPT_NAME:
            staged.append(descriptor)
        return descriptor

    def failing_write(descriptor, data):
        if staged and descriptor == staged[-1]:
            raise OSError("injected staging write failure")
        return original_write(descriptor, data)

    def failing_fsync(descriptor):
        if staged and descriptor == staged[-1]:
            raise OSError("injected staging fsync failure")
        return original_fsync(descriptor)

    original_fdopen = quality.os.fdopen

    class FailingStagedStream:
        """The staged stream whose write or flush fails."""

        def __init__(self, descriptor):
            self._stream = original_fdopen(descriptor, "wb")

        def write(self, data):
            if failure == "write":
                raise OSError("injected staging write failure")
            return self._stream.write(data)

        def flush(self):
            if failure == "flush":
                raise OSError("injected staging flush failure")
            return self._stream.flush()

        def __enter__(self):
            return self

        def __exit__(self, *exception):
            self._stream.close()
            return False

    def fdopen(descriptor, *args, **kwargs):
        if staged and descriptor == staged[-1] and failure in ("write", "flush"):
            return FailingStagedStream(descriptor)
        return original_fdopen(descriptor, *args, **kwargs)

    quality.os.open = opening
    quality.os.fdopen = fdopen
    if failure == "fsync":
        quality.os.fsync = failing_fsync
    try:
        receipt = phase.run()
    finally:
        quality.os.open = original_open
        quality.os.fdopen = original_fdopen
        quality.os.write = original_write
        quality.os.fsync = original_fsync
    # The canonical success is absent: no consumer can read a terminal receipt.
    assert not (phase.directory / "qd-receipt.json").exists(), failure
    # The failed staging is preserved as explicitly non-authoritative evidence.
    staged_path = phase.directory / quality.STAGED_RECEIPT_NAME
    assert staged_path.exists(), failure
    assert receipt["receipt_persisted"] is False, (failure, receipt)
    assert receipt["terminal_status"] == "TERMINAL_RECEIPT_NOT_PERSISTED", (failure, receipt)
    assert receipt["storage_unproven"] is True, (failure, receipt)
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", (failure, receipt)
    with pytest.raises(QualityContractError) as rejected:
        quality.load_canonical_receipt(phase.directory)
    assert "CANONICAL_RECEIPT_ABSENT" in str(rejected.value), str(rejected.value)
    # A replay cannot overwrite the retained failed evidence.
    before = staged_path.read_bytes()
    phase._open_owned_directories(allow_existing=True)
    try:
        again = phase._write_receipt({"synthetic": True})
    finally:
        phase._close_owned_directories()
    assert again is False, (failure, again)
    assert staged_path.read_bytes() == before, failure


def test_correction03_m01_a_successful_publication_is_durable_and_counted(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    receipt = phase.run()
    stored = quality.load_canonical_receipt(phase.directory)
    assert stored["receipt_persisted"] is True, stored
    assert stored["terminal_status"] == "TERMINAL_RECEIPT_PERSISTED", stored
    files = [path for path in phase.directory.rglob("*") if path.is_file()]
    actual_bytes = sum(path.stat().st_size for path in files)
    assert stored["artifact_files_including_receipt"] == len(files), stored
    assert stored["artifact_bytes_including_receipt"] == actual_bytes, stored
    staged = phase.directory / quality.STAGED_RECEIPT_NAME
    canonical = phase.directory / quality.CANONICAL_RECEIPT_NAME
    assert staged.exists() and canonical.exists()
    assert staged.stat().st_ino == canonical.stat().st_ino, "the publication shares one inode"
    # The staged entry is never authority.
    with pytest.raises(QualityContractError):
        quality.load_canonical_receipt(phase.directory / "rows")


@pytest.mark.parametrize("mutation", [
    "receipt-storage-flag-missing",
    "receipt-storage-flag-null",
    "receipt-cleanup-flag-missing",
    "row-storage-flag-missing",
    "row-cleanup-flag-missing",
    "row-storage-flag-null",
    "source-identity-missing",
    "source-identity-truncated",
    "source-path-foreign",
    "source-bytes-mismatch",
    "source-hash-mismatch",
    "release-two-booleans",
    "release-missing",
    "release-loaded-models",
    "release-elapsed-nan",
    "release-elapsed-out-of-range",
    "release-baseline-mismatch",
    "release-samples-missing",
    "release-samples-too-few",
    "release-cadence-broken",
    "release-stability-broken",
    "residue-missing",
    "residue-present",
])
def test_correction03_m08_every_mandatory_evidence_field_is_validated(completed_run, mutation):
    receipt = copy.deepcopy(completed_run["receipt"])
    row = receipt["rows"][0]
    if mutation == "receipt-storage-flag-missing":
        receipt.pop("storage_unproven")
    elif mutation == "receipt-storage-flag-null":
        receipt["storage_unproven"] = None
    elif mutation == "receipt-cleanup-flag-missing":
        receipt.pop("cleanup_unproven")
    elif mutation == "row-storage-flag-missing":
        row.pop("storage_unproven")
    elif mutation == "row-cleanup-flag-missing":
        row.pop("cleanup_unproven")
    elif mutation == "row-storage-flag-null":
        row["storage_unproven"] = None
    elif mutation == "source-identity-missing":
        row["source_evidence"].pop("identity")
    elif mutation == "source-identity-truncated":
        row["source_evidence"]["identity"] = row["source_evidence"]["identity"][:2]
    elif mutation == "source-path-foreign":
        row["source_evidence"]["path"] = "/foreign/not-the-bound-input"
    elif mutation == "source-bytes-mismatch":
        row["source_evidence"]["bytes"] = row["source_evidence"]["bytes"] + 1
    elif mutation == "source-hash-mismatch":
        row["source_evidence"]["sha256"] = "0" * 64
    elif mutation == "release-two-booleans":
        row["release_evidence"] = {"proven": True, "model_inventory_empty": True}
    elif mutation == "release-missing":
        row["release_evidence"] = None
    elif mutation == "release-loaded-models":
        row["release_evidence"]["loaded_models"] = 1
    elif mutation == "release-elapsed-nan":
        row["release_evidence"]["elapsed_seconds"] = float("nan")
    elif mutation == "release-elapsed-out-of-range":
        row["release_evidence"]["elapsed_seconds"] = 31
    elif mutation == "release-baseline-mismatch":
        row["release_evidence"]["baseline_gpu_mib"] = BASE_GPU_MIB + 4096
    elif mutation == "release-samples-missing":
        row["release_evidence"].pop("gpu_samples")
    elif mutation == "release-samples-too-few":
        row["release_evidence"]["gpu_samples"] = row["release_evidence"]["gpu_samples"][:2]
    elif mutation == "release-cadence-broken":
        row["release_evidence"]["gpu_samples"][1]["monotonic_seconds"] = 0
    elif mutation == "release-stability-broken":
        row["release_evidence"]["gpu_samples"][-1]["gpu_used_mib"] = BASE_GPU_MIB + 4096
    elif mutation == "residue-missing":
        row.pop("video_snapshot_residue")
    elif mutation == "residue-present":
        row["video_snapshot_residue"] = ["/comfy/temp/lvw-video-leftover"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert result["rows"][0]["usable"] is False, (mutation, result["rows"][0])
    assert result["rows"][0]["resolved"] is False, (mutation, result["rows"][0])
    assert result["aggregate_pass"] is False, (mutation, result)


def test_correction03_m08_an_unpublished_receipt_is_not_authority(completed_run):
    receipt = copy.deepcopy(completed_run["receipt"])
    receipt["receipt_persisted"] = False
    receipt["terminal_status"] = "TERMINAL_RECEIPT_NOT_PERSISTED"
    scores = _scores(receipt, completed_run["projection_sha256"])
    with pytest.raises(QualityContractError) as rejected:
        recompute_scores(receipt, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_EXECUTION_RECEIPT_NOT_PERSISTED" in str(rejected.value), str(rejected.value)
    staged = copy.deepcopy(completed_run["receipt"])
    staged["published_as"] = "qd-receipt.staging"
    with pytest.raises(QualityContractError) as staged_receipt:
        recompute_scores(staged, completed_run["artifact_root"], scores, independence=_independence())
    assert "QS_EXECUTION_RECEIPT_NOT_AUTHORITATIVE" in str(staged_receipt.value), str(staged_receipt.value)


def test_correction03_nm01_a_proof_that_expires_at_the_first_authorize_refuses_every_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=2.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)

    def authorize(action, subject):
        if action == "quality_public_submit":
            clock.now = 2.0

    phase.authorize = authorize
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["rows"][0]["error_code"] == "PARENT_BUDGET_PROOF_STALE", receipt["rows"][0]
    assert receipt["rows"][0]["execution_status"] == "BLOCKED", receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt
    assert len(receipt["rows"]) == 16, receipt


def test_correction03_nm01_a_proof_diminished_at_the_handoff_refuses_every_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)

    def authorize(action, subject):
        if action == "quality_public_submit":
            # The admitted capacity is diminished at the send handoff.
            phase.parent_budget["action_capacity"] = 0

    phase.authorize = authorize
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert receipt["rows"][0]["error_code"] == "PARENT_BUDGET_CAPACITY_INSUFFICIENT", receipt["rows"][0]
    assert receipt["rows"][0]["execution_status"] == "BLOCKED", receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction03_nm02_a_callback_past_the_phase_deadline_refuses_the_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=20000.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)
    load = phase._load_workflows

    def load_near_deadline():
        result = load()
        clock.now = 10799.0
        return result

    phase._load_workflows = load_near_deadline

    def authorize(action, subject):
        if action == "quality_public_submit":
            clock.now += 2.0

    phase.authorize = authorize
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert receipt["rows"][0]["error_code"] == "PHASE_DEADLINE_EXCEEDED", receipt["rows"][0]
    assert receipt["rows"][0]["execution_status"] == "BLOCKED", receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt
    assert receipt["hard_timing_blocker"] == "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", receipt


def test_correction03_nm02_the_phase_boundary_is_exact_and_one_over(tmp_path):
    # The preparatory work ends just inside the deadline and the bounded
    # callback consumes the remaining seconds, exactly like the independent
    # review's observation.
    for prepared, expected_sends in ((10798.0, 1), (10799.0, 0)):
        clock = FakeClock(step=0.0)
        proof = _parent_proof(clock, expires_monotonic=20000.0)
        phase, driver, _ = _prepare(tmp_path / str(prepared), clock=clock, parent_budget=proof)
        load = phase._load_workflows

        def load_near_deadline(prepared=prepared):
            result = load()
            clock.now = prepared
            return result

        phase._load_workflows = load_near_deadline

        def authorize(action, subject):
            if action == "quality_public_submit":
                clock.now += 2.0

        phase.authorize = authorize
        receipt = phase.run()
        assert driver.submissions == expected_sends, (prepared, driver.submissions)
        if expected_sends == 0:
            assert receipt["rows"][0]["error_code"] == "PHASE_DEADLINE_EXCEEDED", (prepared, receipt)
        else:
            assert receipt["test_counts"]["PASS"] >= 1, (prepared, receipt)


def test_correction03_nm01_a_later_row_expiry_preserves_the_prior_attempts(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=20000.0)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof)

    submit = driver.submit

    def advancing_submit(graph):
        result = submit(graph)
        # The clock moves in the driver, outside every bounded phase step.
        clock.now += 7000.0
        return result

    driver.submit = advancing_submit
    receipt = phase.run()
    # The first rows were really sent and stay charged; the expiry stops the
    # later ones without refunding or retrying the earlier ones.
    assert driver.submissions >= 1, driver.submissions
    assert receipt["public_submissions"] == driver.submissions, receipt
    assert receipt["test_counts"]["PASS"] >= 1, receipt
    assert receipt["rows"][-1]["execution_status"] == "BLOCKED", receipt["rows"][-1]
    assert len(receipt["rows"]) == 16, receipt
    assert receipt["provider_calls_reserved"] >= 1, receipt


# --------------------------------------------------------------------------
# aggregate correction 04: the consumer, the source seal and the send
# boundary
#
# M01  the public scorer loads the actually published canonical receipt
# M08  the original source identity is sealed and the bound context is typed
# NM01 every controlled driver value is resolved before the final guard
# NM02 one final latest clock sample decides the deadline and the interval
# --------------------------------------------------------------------------
def _own_run(tmp_path, name="run", **kwargs):
    """A genuine public run in a private root.

    The destructive negative cases need a root of their own: they remove,
    corrupt or replace the published evidence, and they must never touch the
    shared fixture of the other checks.
    """
    phase, driver, projection = _prepare(tmp_path / name, **kwargs)
    receipt = phase.run()
    return {
        "phase": phase,
        "driver": driver,
        "receipt": receipt,
        "artifact_root": phase.directory,
        "root": phase.root,
        "projection": projection,
        "projection_sha256": hashlib.sha256(projection).hexdigest(),
    }


def _own_scores(run):
    return _scores(run["receipt"], run["projection_sha256"])


class DynamicAccessorDriver(SyntheticDriver):
    """A driver whose controlled accessors are observable properties.

    The public submission limit and the submit callable are properties, so
    reading them runs the callback that the phase has to observe *before*
    its final admission guard.
    """

    def __init__(self, root, failure=None, on_limit_read=None, on_submit_bind=None):
        self.limit_reads = 0
        self.submit_binds = 0
        self.submit_calls = 0
        self._on_limit_read = on_limit_read
        self._on_submit_bind = on_submit_bind
        super().__init__(root, failure)

    @property
    def max_public_submissions(self):
        self.limit_reads += 1
        if self._on_limit_read is not None:
            self._on_limit_read()
        return self._limit_value

    @max_public_submissions.setter
    def max_public_submissions(self, value):
        self._limit_value = value

    @property
    def submit(self):
        self.submit_binds += 1
        if self._on_submit_bind is not None:
            self._on_submit_bind()
        driver = self

        def bound(graph):
            driver.submit_calls += 1
            return SyntheticDriver.submit(driver, graph)

        return bound


# ---- M01: the public scorer consumes the actually published document ----
def test_correction04_m01_a_missing_canonical_receipt_fails_closed(tmp_path):
    run = _own_run(tmp_path)
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    assert canonical.is_file(), canonical
    canonical.unlink()
    # The staged bytes are retained, but they are never authority.
    assert (run["artifact_root"] / quality.STAGED_RECEIPT_NAME).is_file()
    with pytest.raises(QualityContractError) as absent:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "CANONICAL_RECEIPT_ABSENT" in str(absent.value), str(absent.value)


def test_correction04_m01_a_corrupt_canonical_receipt_fails_closed(tmp_path):
    run = _own_run(tmp_path)
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    canonical.write_bytes(b'{"kind": "S3_P3B_QD_EXECUTION_RECEIPT", "rows": [')
    with pytest.raises(QualityContractError) as corrupt:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "CANONICAL_RECEIPT_UNREADABLE" in str(corrupt.value), str(corrupt.value)


def test_correction04_m01_a_foreign_canonical_receipt_fails_closed(tmp_path):
    run = _own_run(tmp_path)
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    document = json.loads(canonical.read_bytes().decode("utf-8"))
    document["run_id"] = "a-different-run"
    canonical.write_bytes(json.dumps(document).encode("utf-8"))
    with pytest.raises(QualityContractError) as foreign:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "QS_EXECUTION_RECEIPT_BINDING_MISMATCH" in str(foreign.value), str(foreign.value)


def test_correction04_m01_a_staged_only_receipt_is_not_authority(tmp_path):
    run = _own_run(tmp_path)
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    staged = run["artifact_root"] / quality.STAGED_RECEIPT_NAME
    assert canonical.stat().st_ino == staged.stat().st_ino
    canonical.unlink()
    with pytest.raises(QualityContractError) as staged_only:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "CANONICAL_RECEIPT_ABSENT" in str(staged_only.value), str(staged_only.value)


def test_correction04_m01_a_redirected_artifact_root_is_refused(tmp_path):
    run = _own_run(tmp_path)
    foreign = tmp_path / "foreign-root"
    foreign.mkdir()
    (foreign / "s3-quality").mkdir()
    with pytest.raises(QualityContractError) as location:
        recompute_scores(run["receipt"], foreign / "s3-quality", _own_scores(run),
                         independence=_independence())
    assert "QS_ARTIFACT_ROOT_LOCATION_INVALID" in str(location.value), str(location.value)


def test_correction04_m01_an_oversized_canonical_receipt_is_refused(tmp_path):
    run = _own_run(tmp_path)
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    # The consumer never reads more than the frozen 8MiB plus one byte.
    canonical.write_bytes(b"x" * (quality.MAX_ARTIFACT_BYTES + 1))
    with pytest.raises(QualityContractError) as oversized:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "CANONICAL_RECEIPT_TOO_LARGE" in str(oversized.value), str(oversized.value)


def test_correction04_m01_the_supplied_execution_content_must_be_the_published_one(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    # A content field that the published document records is forged.
    receipt["rows"][0]["raw_bytes"] = receipt["rows"][0]["raw_bytes"] + 1
    scores = _own_scores(run)
    with pytest.raises(QualityContractError) as forged:
        recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    assert "QS_RAW_ARTIFACT_LENGTH_MISMATCH" in str(forged.value), str(forged.value)


def test_correction04_m01_a_forged_provider_counter_is_refused(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    receipt["provider_calls_reserved"] = 1
    scores = _own_scores(run)
    with pytest.raises(QualityContractError) as forged:
        recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    assert "QS_EXECUTION_CONTENT_MISMATCH" in str(forged.value), str(forged.value)


def test_correction04_m01_a_forged_verdict_can_only_be_stricter(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    # The published document recorded a pass; the supplied document claims a
    # failure.  The row is then not usable and not resolved.
    receipt["rows"][0]["execution_status"] = "FAIL"
    receipt["rows"][0]["error_code"] = "SOURCE_REPLACED"
    scores = _own_scores(run)
    result = recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    row = result["rows"][0]
    assert row["usable"] is False and row["resolved"] is False, row
    assert result["aggregate_pass"] is False, result


def test_correction04_m01_the_published_receipt_is_the_only_authority(completed_run):
    # The unchanged happy path still closes: the published document, the
    # sealed source plan and the supplied receipt agree.
    receipt = completed_run["receipt"]
    scores = _scores(receipt, completed_run["projection_sha256"])
    result = recompute_scores(receipt, completed_run["artifact_root"], scores,
                               independence=_independence())
    assert result["aggregate_pass"] is True, result
    assert result["decision"] == "QUALITY_THRESHOLDS_MET_FOR_THIS_BOUND_RUN", result


# ---- M08: the original source identity seal ----------------------------
def test_correction04_m08_the_source_plan_seals_all_sixteen_original_identities(tmp_path):
    run = _own_run(tmp_path)
    receipt = run["receipt"]
    binding = receipt["source_plan"]
    assert binding is not None, receipt
    plan_path = run["artifact_root"] / binding["path"]
    assert plan_path.is_file(), plan_path
    raw = plan_path.read_bytes()
    assert len(raw) == binding["bytes"], binding
    assert hashlib.sha256(raw).hexdigest() == binding["sha256"], binding
    document = json.loads(raw.decode("utf-8"))
    assert document["schema_version"] == quality.SOURCE_PLAN_SCHEMA_VERSION, document
    assert document["run_id"] == receipt["run_id"], document
    assert document["candidate_sha"] == receipt["candidate_sha"], document
    assert document["authorization_sha256"] == receipt["authorization_sha256"], document
    assert document["projection_sha256"] == receipt["projection_sha256"], document
    assert len(document["rows"]) == 16, document
    for index, (sealed, row) in enumerate(zip(document["rows"], receipt["rows"])):
        assert sealed["ordinal"] == index + 1, sealed
        assert sealed["asset_id"] == row["asset_id"], sealed
        assert sealed["media_kind"] == row["media_kind"], sealed
        assert sealed["input_reference"] == row["input_reference"], sealed
        assert sealed["source_bytes"] == row["source_bytes"], sealed
        assert sealed["source_sha256"] == row["source_sha256"], sealed
        # The sealed identity is the original five component descriptor
        # identity of the source file.
        assert sealed["identity"] == row["source_evidence"]["identity"], sealed
        assert len(sealed["identity"]) == 5, sealed


def test_correction04_m08_a_changed_source_identity_is_unknown_in_the_scoring(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    row = receipt["rows"][0]
    identity = list(row["source_evidence"]["identity"])
    identity[2] = identity[2] + 1
    row["source_evidence"]["identity"] = identity
    scores = _own_scores(run)
    result = recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    entry = result["rows"][0]
    assert entry["usable"] is False and entry["resolved"] is False, entry
    assert entry["evidence_reason"] == "SOURCE_SEAL_IDENTITY_MISMATCH", entry
    assert result["aggregate_pass"] is False, result


def test_correction04_m08_a_changed_source_size_is_unknown_in_the_scoring(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    receipt["rows"][0]["source_evidence"]["bytes"] += 1
    scores = _own_scores(run)
    result = recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    entry = result["rows"][0]
    assert entry["usable"] is False and entry["resolved"] is False, entry
    assert entry["evidence_reason"] == "SOURCE_SEAL_BYTES_MISMATCH", entry
    assert result["aggregate_pass"] is False, result


def test_correction04_m08_a_changed_source_hash_is_unknown_in_the_scoring(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    receipt["rows"][0]["source_evidence"]["sha256"] = "0" * 64
    scores = _own_scores(run)
    result = recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    entry = result["rows"][0]
    assert entry["usable"] is False and entry["resolved"] is False, entry
    assert entry["evidence_reason"] == "SOURCE_SEAL_HASH_MISMATCH", entry
    assert result["aggregate_pass"] is False, result


def test_correction04_m08_a_changed_source_path_is_unknown_in_the_scoring(tmp_path):
    run = _own_run(tmp_path)
    receipt = copy.deepcopy(run["receipt"])
    receipt["rows"][0]["source_evidence"]["path"] = str(run["root"] / "input" / "other.png")
    scores = _own_scores(run)
    result = recompute_scores(receipt, run["artifact_root"], scores, independence=_independence())
    entry = result["rows"][0]
    assert entry["usable"] is False and entry["resolved"] is False, entry
    assert entry["evidence_reason"] == "SOURCE_SEAL_PATH_MISMATCH", entry
    assert result["aggregate_pass"] is False, result


def _tamper_same_length(raw, marker, replacement):
    """Replace one byte of ``raw`` after ``marker`` without changing the length."""
    index = raw.index(marker) + len(marker)
    original = raw[index:index + 1]
    changed = b"9" if original != b"9" else b"8"
    return raw[:index] + changed + raw[index + 1:]


def test_correction04_m08_a_tampered_source_plan_is_refused(tmp_path):
    run = _own_run(tmp_path)
    binding = run["receipt"]["source_plan"]
    plan_path = run["artifact_root"] / binding["path"]
    raw = plan_path.read_bytes()
    # The tamper keeps the byte length, so the length check passes and the
    # hash that the published receipt binds is what refuses it.
    tampered = _tamper_same_length(raw, b'"identity":[', b"")
    plan_path.write_bytes(tampered)
    assert len(tampered) == len(raw)
    with pytest.raises(QualityContractError) as rejected:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "QS_SOURCE_PLAN_HASH_MISMATCH" in str(rejected.value), str(rejected.value)


def test_correction04_m08_a_missing_source_plan_is_refused(tmp_path):
    run = _own_run(tmp_path)
    binding = run["receipt"]["source_plan"]
    (run["artifact_root"] / binding["path"]).unlink()
    with pytest.raises(QualityContractError) as missing:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "QS_SOURCE_PLAN_MISSING" in str(missing.value), str(missing.value)


def test_correction04_m08_a_replayed_source_plan_is_refused(tmp_path):
    run = _own_run(tmp_path)
    binding = run["receipt"]["source_plan"]
    plan_path = run["artifact_root"] / binding["path"]
    raw = plan_path.read_bytes()
    replayed = raw.replace(b"synthetic-quality-run", b"synthetic-quality-rin")
    assert len(replayed) == len(raw)
    plan_path.write_bytes(replayed)
    # The published receipt binds the original seal hash, so the replay is
    # refused before its binding is even inspected.
    with pytest.raises(QualityContractError) as rejected:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "QS_SOURCE_PLAN_HASH_MISMATCH" in str(rejected.value), str(rejected.value)


def test_correction04_m08_a_source_plan_from_another_run_is_refused(tmp_path):
    run = _own_run(tmp_path)
    binding = run["receipt"]["source_plan"]
    plan_path = run["artifact_root"] / binding["path"]
    raw = plan_path.read_bytes()
    replayed = raw.replace(b"synthetic-quality-run", b"synthetic-quality-rin")
    plan_path.write_bytes(replayed)
    # A consistent forgery of the seal *and* of the published receipt is
    # still refused: the seal has to be bound to the run of the receipt.
    canonical = run["artifact_root"] / quality.CANONICAL_RECEIPT_NAME
    document = json.loads(canonical.read_bytes().decode("utf-8"))
    document["source_plan"]["sha256"] = hashlib.sha256(replayed).hexdigest()
    canonical.write_bytes(json.dumps(document).encode("utf-8"))
    with pytest.raises(QualityContractError) as rejected:
        recompute_scores(run["receipt"], run["artifact_root"], _own_scores(run),
                         independence=_independence())
    assert "QS_SOURCE_PLAN_BINDING_MISMATCH" in str(rejected.value), str(rejected.value)


def test_correction04_m08_the_source_media_need_not_stay_on_disk(tmp_path):
    run = _own_run(tmp_path)
    # The archive may delete the original media: the scoring never re-stats a
    # live source, it compares the recorded evidence with the seal.
    for path in (run["root"] / "input").iterdir():
        path.unlink()
    scores = _own_scores(run)
    result = recompute_scores(run["receipt"], run["artifact_root"], scores,
                               independence=_independence())
    assert result["aggregate_pass"] is True, result


def test_correction04_m08_a_source_plan_failure_produces_zero_sends(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    original = phase._artifact

    def failing(relative, raw):
        if relative == quality.SOURCE_PLAN_NAME:
            raise QualityContractError("ARTIFACT_WRITE_FAILED:" + relative)
        return original(relative, raw)

    phase._artifact = failing
    receipt = phase.run()
    assert receipt["decision"] == "QUALITY_EXECUTION_BLOCKED", receipt
    assert receipt["error_code"].startswith("SOURCE_PLAN_PERSISTENCE_FAILED"), receipt
    assert driver.submissions == 0, driver.submissions
    assert receipt["public_submissions"] == 0, receipt
    assert len(receipt["rows"]) == 16, receipt
    assert all(row["execution_status"] in ("BLOCKED", "FAIL") for row in receipt["rows"]), receipt
    assert all(row["execution_status"] != "NOT_RUN" for row in receipt["rows"]), receipt
    assert receipt["storage_unproven"] is True, receipt


def test_correction04_m08_the_bound_context_must_be_typed(tmp_path):
    run = _own_run(tmp_path)
    for field, value in (("run_root", None), ("run_root", 0),
                          ("parent_budget_baseline_gpu_mib", 100.0),
                          ("parent_budget_baseline_gpu_mib", True),
                          ("parent_budget_baseline_gpu_mib", None)):
        receipt = copy.deepcopy(run["receipt"])
        receipt[field] = value
        scores = _own_scores(run)
        result = recompute_scores(receipt, run["artifact_root"], scores,
                                   independence=_independence())
        assert result["aggregate_pass"] is False, (field, value, result)
        assert result["all_rows_resolved"] is False, (field, value, result)


def test_correction04_m08_the_execution_uses_the_same_shared_validators():
    # The execution path really calls the shared source validator, so the two
    # entry points can never disagree about a proven source.
    source = inspect.getsource(quality.QualityPhase._validate_source)
    assert "validate_source_evidence(" in source, source
    source = inspect.getsource(quality.QualityPhase._release_evidence)
    assert "validate_release_evidence(" in source, source
    source = inspect.getsource(quality.QualityPhase._run_owned)
    assert "_persist_source_plan(" in source, source


# ---- NM01: every controlled driver value is resolved before the guard ----
def test_correction04_nm01_a_diminishing_limit_accessor_refuses_every_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=20000.0)
    holder = {}

    def diminish():
        # The admitted capacity is diminished when the limit is read.
        holder["phase"].parent_budget["action_capacity"] = 0

    driver = DynamicAccessorDriver(tmp_path, on_limit_read=diminish)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof, driver=driver)
    holder["phase"] = phase
    receipt = phase.run()
    assert driver.limit_reads >= 1, driver.limit_reads
    assert driver.submissions == 0, driver.submissions
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["rows"][0]["error_code"] == "PARENT_BUDGET_CAPACITY_INSUFFICIENT", receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction04_nm01_an_advancing_clock_accessor_refuses_every_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=20000.0)

    def advance():
        clock.now = 10801.0

    driver = DynamicAccessorDriver(tmp_path, on_limit_read=advance)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof, driver=driver)
    receipt = phase.run()
    assert driver.submissions == 0, driver.submissions
    assert receipt["public_submissions"] == 0, receipt
    assert receipt["rows"][0]["error_code"] == "PHASE_DEADLINE_EXCEEDED", receipt["rows"][0]
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction04_nm01_a_diminishing_submit_binding_refuses_every_send(tmp_path):
    clock = FakeClock(step=0.0)
    proof = _parent_proof(clock, expires_monotonic=20000.0)
    holder = {}

    def diminish():
        # The driver protocol check reads the callable once during the
        # construction; only a read inside a row may diminish the capacity.
        phase_ref = holder.get("phase")
        if phase_ref is not None:
            phase_ref.parent_budget["action_capacity"] = 0

    driver = DynamicAccessorDriver(tmp_path, on_submit_bind=diminish)
    phase, driver, _ = _prepare(tmp_path, clock=clock, parent_budget=proof, driver=driver)
    holder["phase"] = phase
    receipt = phase.run()
    # The submit callable is bound before the final guard, so the capacity
    # that the binding diminished is the capacity the guard refuses.
    assert driver.submit_binds >= 1, driver.submit_binds
    assert driver.submit_calls == 0, driver.submit_calls
    assert driver.submissions == 0, driver.submissions
    assert receipt["test_counts"]["BLOCKED"] == 16, receipt


def test_correction04_nm01_the_driver_state_is_resolved_before_the_final_guard():
    source = inspect.getsource(quality.QualityPhase._execute_row)
    assert source.index("_resolve_driver_state()") < source.index("_send_admission_guard("), source
    assert source.index("_send_admission_guard(") < source.index('driver_state["submit"]'), source
    # No controlled accessor is resolved after the final admission.
    tail = source[source.index("_send_admission_guard("):]
    assert "getattr(self.driver" not in tail, tail
    assert "self.driver." not in tail, tail


def test_correction04_nm02_the_guard_reads_the_clock_exactly_once(tmp_path):
    phase, driver, _ = _prepare(tmp_path)
    readings = []
    inner = phase.clock

    def counting():
        value = inner()
        readings.append(value)
        return value

    phase.clock = counting
    phase._started = 0.0
    phase._phase_deadline = quality.PHASE_TIMEOUT_SECONDS
    phase._open_owned_directories()
    try:
        row = {"ordinal": 1, "asset_id": "SYN-I00", "media_kind": "image",
               "source_sha256": "0" * 64, "source_bytes": 1, "input_reference": "x.png"}
        phase._send_admission_guard(row, 1)
    finally:
        phase._close_owned_directories()
    assert len(readings) == 1, readings


def test_correction04_nm02_the_phase_boundary_is_exact_and_one_over(tmp_path):
    for prepared, expected_sends in ((10798.0, 1), (10799.0, 0)):
        clock = FakeClock(step=0.0)
        proof = _parent_proof(clock, expires_monotonic=20000.0)
        phase, driver, _ = _prepare(tmp_path / str(prepared), clock=clock, parent_budget=proof)
        load = phase._load_workflows

        def load_near_deadline(prepared=prepared):
            result = load()
            clock.now = prepared
            return result

        phase._load_workflows = load_near_deadline

        def authorize(action, subject):
            if action == "quality_public_submit":
                clock.now += 2.0

        phase.authorize = authorize
        receipt = phase.run()
        assert driver.submissions == expected_sends, (prepared, driver.submissions)
        if expected_sends == 0:
            assert receipt["rows"][0]["error_code"] == "PHASE_DEADLINE_EXCEEDED", (prepared, receipt)
            assert receipt["test_counts"]["BLOCKED"] == 16, (prepared, receipt)
        else:
            assert receipt["test_counts"]["PASS"] >= 1, (prepared, receipt)


def test_correction04_nm02_the_hard_supervision_blocker_is_still_recorded(tmp_path):
    run = _own_run(tmp_path)
    receipt = run["receipt"]
    assert receipt["hard_timing_blocker"] == "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", receipt
    assert receipt["timing_assurance"]["hard_end_to_end_supervision"] == \
        "UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER", receipt
    assert receipt["timing_assurance"]["synchronous_callables_preemptively_bounded"] is False, receipt
