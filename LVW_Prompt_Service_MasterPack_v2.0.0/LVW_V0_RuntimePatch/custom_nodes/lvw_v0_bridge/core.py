"""Pure-Python transport, input limits, and response oracle for LVW V0.

The module intentionally has no ComfyUI import so its safety boundary can be
tested offline.  The only production network target is the literal loopback
Ollama endpoint.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import json
import re
import threading
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CHAT_ENDPOINT = "http://127.0.0.1:11434/api/chat"
MAX_LONG_EDGE = 384
MAX_VIDEO_FRAMES = 4
MAX_NUM_CTX = 2048
MAX_NUM_PREDICT = 768
MAX_TIMEOUT_SECONDS = 120
DEFAULT_MODEL = "gemma4:26b"

FROZEN_ERROR_CODES = frozenset({
    "MODEL_UNAVAILABLE", "MODEL_REFUSAL", "NO_USABLE_OUTPUT", "MODEL_TIMEOUT", "GPU_OOM",
    "RESOURCE_BUSY", "RESOURCE_RELEASE_PENDING", "PARSE_PARTIAL", "MEDIA_INVALID",
    "MEDIA_LIMIT_EXCEEDED", "PATH_FORBIDDEN", "AUTH_REQUIRED", "ORIGIN_FORBIDDEN",
    "REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT", "JOB_CANCELLED", "ATTEMPT_STALE",
    "CONTRACT_UNSUPPORTED", "PEER_UNAVAILABLE", "SCOPE_FORBIDDEN", "WORKFLOW_NOT_ALLOWED",
    "SUBMISSION_UNKNOWN", "CANCEL_UNSAFE", "PACKAGE_INVALID", "DISK_FULL",
})

_INFERENCE_LOCK = threading.Lock()


class BridgeError(RuntimeError):
    """Fail-closed bridge error with a stable machine code."""

    def __init__(self, code: str, message: str, *, subcode: str, details: dict | None = None):
        if code not in FROZEN_ERROR_CODES:
            raise ValueError(f"unfrozen public error code: {code}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = {"subcode": subcode, **(details or {})}

    def __str__(self) -> str:
        """Render current evidence details for Comfy exception/history capture."""
        return json.dumps(
            {"code": self.code, "message": self.message, "details": self.details},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )


def validate_loopback_endpoint(endpoint: str) -> None:
    try:
        parsed = urllib.parse.urlsplit(endpoint)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise BridgeError("ORIGIN_FORBIDDEN", "invalid Ollama endpoint", subcode="INVALID_OLLAMA_ENDPOINT") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port != 11434
        or parsed.path != "/api/chat"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BridgeError("ORIGIN_FORBIDDEN", "Ollama endpoint must be literal loopback port 11434 /api/chat",
                          subcode="NON_LOOPBACK_OLLAMA_ENDPOINT")


def _normalized(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _nonempty_string(value, field: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BridgeError("PARSE_PARTIAL", f"{field} must be a non-empty string", subcode="SCHEMA_EMPTY_STRING")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise BridgeError("PARSE_PARTIAL", f"{field} exceeds maxLength={max_length}", subcode="SCHEMA_STRING_LIMIT")
    return cleaned


def _string_list(value, field: str, *, require_nonempty: bool, max_items: int, max_item_length: int = 400) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise BridgeError("PARSE_PARTIAL", f"{field} must be an array of non-empty strings",
                          subcode="SCHEMA_STRING_ARRAY")
    cleaned = [item.strip() for item in value]
    if require_nonempty and not cleaned:
        raise BridgeError("NO_USABLE_OUTPUT", f"{field} must contain at least one item",
                          subcode="EMPTY_OBSERVATIONS")
    if len(cleaned) > max_items or any(len(item) > max_item_length for item in cleaned):
        raise BridgeError("PARSE_PARTIAL", f"{field} exceeds frozen array or string limits",
                          subcode="SCHEMA_ARRAY_LIMIT")
    return cleaned


def _response_schema(video: bool) -> dict:
    properties = {
        "observations": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 6},
        "inferences": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 4},
        "unknowns": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 4},
        "prompt": {"type": "string", "minLength": 1, "maxLength": 800},
        "tags": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 8},
    }
    if video:
        properties["change"] = {"type": "string", "minLength": 1, "maxLength": 400}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


IMAGE_RESPONSE_SCHEMA = _response_schema(False)
VIDEO_FRAME_RESPONSE_SCHEMA = _response_schema(True)


def _request_instruction(*, video: bool, frame_index: int | None, previous_observations: list[str], user_instruction: str) -> str:
    if video:
        previous = "; ".join(previous_observations[-3:]) if previous_observations else "none; this is the baseline frame"
        base = (
            f"Analyze ordered video frame {frame_index + 1}. Return only compact JSON matching the supplied schema. "
            "observations must contain visible facts. change must explicitly state the visible change, or explicitly "
            f"state that no visible change can be established. Previous accepted observations: {previous}."
        )
    else:
        base = (
            "Analyze this single image. Return only compact JSON matching the supplied schema. "
            "observations must contain visible facts; separate inferences and unknowns."
        )
    if user_instruction.strip():
        base += f" Additional analysis constraint (not prompt content): {user_instruction.strip()}"
    base += (
        " The prompt field must be a concrete generation prompt grounded only in visible facts from the current "
        "image or frame, such as its subject, setting, action, composition, lighting, and color. Do not copy, "
        "quote, paraphrase, summarize, translate, or otherwise rewrite any part of this request or the user "
        "instruction into the prompt field."
    )
    return base


def build_chat_payload(*, model: str, encoded_image: str, instruction: str, video: bool) -> dict:
    if model != DEFAULT_MODEL:
        raise BridgeError("CONTRACT_UNSUPPORTED", f"model must be exactly {DEFAULT_MODEL}",
                          subcode="MODEL_TAG_NOT_ALLOWED")
    return {
        "model": model,
        "messages": [{"role": "user", "content": instruction, "images": [encoded_image]}],
        "stream": False,
        "think": False,
        "format": VIDEO_FRAME_RESPONSE_SCHEMA if video else IMAGE_RESPONSE_SCHEMA,
        "options": {"num_ctx": MAX_NUM_CTX, "num_predict": MAX_NUM_PREDICT, "temperature": 0.2},
        "keep_alive": 0,
    }


def parse_response(raw_response: str, *, instruction: str, user_instruction: str, video: bool) -> dict:
    try:
        envelope = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BridgeError("PARSE_PARTIAL", "Ollama response envelope is not valid JSON",
                          subcode="INVALID_ENVELOPE_JSON") from exc
    if not isinstance(envelope, dict):
        raise BridgeError("PARSE_PARTIAL", "Ollama response envelope must be an object",
                          subcode="INVALID_ENVELOPE_SCHEMA")
    if envelope.get("done_reason") == "length":
        raise BridgeError("PARSE_PARTIAL", "done_reason=length is not usable", subcode="DONE_REASON_LENGTH")
    if envelope.get("done") is not True or envelope.get("done_reason") != "stop":
        raise BridgeError("PARSE_PARTIAL", "Ollama response must finish with done_reason=stop",
                          subcode="INCOMPLETE_MODEL_OUTPUT")
    message = envelope.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise BridgeError("PARSE_PARTIAL", "response message.content must be a JSON string",
                          subcode="MISSING_MESSAGE_CONTENT")
    try:
        content = json.loads(message["content"])
    except json.JSONDecodeError as exc:
        raise BridgeError("PARSE_PARTIAL", "message.content is not strict JSON",
                          subcode="INVALID_CONTENT_JSON") from exc
    required = {"observations", "inferences", "unknowns", "prompt", "tags"}
    if video:
        required.add("change")
    if not isinstance(content, dict) or set(content) != required:
        raise BridgeError("PARSE_PARTIAL", "response fields do not exactly match the frozen response schema",
                          subcode="RESPONSE_SCHEMA_MISMATCH")
    parsed = {
        "observations": _string_list(content["observations"], "observations", require_nonempty=True, max_items=6),
        "inferences": _string_list(content["inferences"], "inferences", require_nonempty=False, max_items=4),
        "unknowns": _string_list(content["unknowns"], "unknowns", require_nonempty=False, max_items=4),
        "prompt": _nonempty_string(content["prompt"], "prompt", max_length=800),
        "tags": _string_list(content["tags"], "tags", require_nonempty=False, max_items=8, max_item_length=100),
    }
    if video:
        parsed["change"] = _nonempty_string(content["change"], "change", max_length=400)
    echo_candidates = {_normalized(instruction)}
    if user_instruction.strip():
        echo_candidates.add(_normalized(user_instruction))
    semantic_strings = parsed["observations"] + parsed["inferences"] + parsed["unknowns"] + [parsed["prompt"]]
    if video:
        semantic_strings.append(parsed["change"])
    if any(_normalized(value) in echo_candidates for value in semantic_strings):
        raise BridgeError("NO_USABLE_OUTPUT", "model output echoed the normalized request instruction",
                          subcode="PROMPT_ECHO")
    return parsed


def split_frames(value) -> list:
    shape = getattr(value, "shape", None)
    if shape is not None:
        if len(shape) == 4:
            return [value[index] for index in range(int(shape[0]))]
        if len(shape) == 3:
            return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    raise BridgeError("MEDIA_INVALID", "expected an HWC frame or NHWC image batch",
                      subcode="INVALID_IMAGE_BATCH_SHAPE")


def frame_dimensions(frame) -> tuple[int, int]:
    shape = getattr(frame, "shape", None)
    if shape is None or len(shape) != 3:
        raise BridgeError("MEDIA_INVALID", "each frame must have HWC shape", subcode="INVALID_FRAME_SHAPE")
    height, width, channels = (int(shape[0]), int(shape[1]), int(shape[2]))
    if height < 1 or width < 1 or channels not in {1, 3, 4}:
        raise BridgeError("MEDIA_INVALID", "frame dimensions or channels are invalid",
                          subcode="INVALID_FRAME_DIMENSIONS")
    if max(height, width) > MAX_LONG_EDGE:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", f"frame longest edge must be <= {MAX_LONG_EDGE}",
                          subcode="FRAME_LONG_EDGE_LIMIT")
    return width, height


def encode_comfy_frame(frame) -> str:
    """Encode one already-bounded Comfy HWC tensor as PNG in memory."""
    frame_dimensions(frame)
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # Available in Comfy; explicit failure outside it.
        raise BridgeError("MODEL_UNAVAILABLE", "numpy and Pillow are required inside ComfyUI",
                          subcode="FRAME_ENCODER_UNAVAILABLE") from exc
    value = frame.detach().cpu().numpy() if hasattr(frame, "detach") else np.asarray(frame)
    if value.dtype.kind == "f":
        value = (np.clip(value, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    else:
        value = np.clip(value, 0, 255).astype(np.uint8)
    if value.shape[2] == 1:
        image = Image.fromarray(value[:, :, 0], mode="L").convert("RGB")
    elif value.shape[2] == 4:
        rgba = Image.fromarray(value, mode="RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        image = background.convert("RGB")
    else:
        image = Image.fromarray(value, mode="RGB")
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return base64.b64encode(output.getvalue()).decode("ascii")


class OllamaLoopbackTransport:
    """Small no-proxy stdlib HTTP transport restricted to literal loopback."""

    def __init__(self, endpoint: str = CHAT_ENDPOINT):
        self.endpoint = endpoint
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post(self, url: str, payload: dict, timeout_seconds: int) -> str:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", "strict")
                if response.status != 200:
                    raise BridgeError("MODEL_UNAVAILABLE", f"Ollama returned HTTP {response.status}",
                                      subcode="OLLAMA_HTTP_STATUS")
                return raw
        except BridgeError:
            raise
        except TimeoutError as exc:
            raise BridgeError("MODEL_TIMEOUT", "Ollama request timed out", subcode="OLLAMA_TIMEOUT") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise BridgeError("MODEL_TIMEOUT", "Ollama request timed out", subcode="OLLAMA_TIMEOUT") from exc
            raise BridgeError("MODEL_UNAVAILABLE", "Ollama loopback request failed",
                              subcode="OLLAMA_TRANSPORT_ERROR") from exc
        except UnicodeDecodeError as exc:
            raise BridgeError("PARSE_PARTIAL", "Ollama response is not UTF-8",
                              subcode="INVALID_RESPONSE_ENCODING") from exc

    def chat(self, payload: dict, timeout_seconds: int) -> str:
        validate_loopback_endpoint(self.endpoint)
        return self._post(self.endpoint, payload, timeout_seconds)

    def cleanup(self, model: str, timeout_seconds: int) -> None:
        validate_loopback_endpoint(self.endpoint)
        parsed = urllib.parse.urlsplit(self.endpoint)
        unload_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/api/generate", "", ""))
        self._post(unload_url, {"model": model, "keep_alive": 0}, min(timeout_seconds, 15))


@dataclass(frozen=True)
class FrameCall:
    raw_response: str
    parsed: dict


def call_one_frame(*, transport, encoder, frame, model: str, timeout_seconds: int, video: bool,
                   frame_index: int | None, previous_observations: list[str], user_instruction: str) -> FrameCall:
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise BridgeError("CONTRACT_UNSUPPORTED", f"timeout_seconds must be 1..{MAX_TIMEOUT_SECONDS}",
                          subcode="TIMEOUT_LIMIT")
    validate_loopback_endpoint(getattr(transport, "endpoint", ""))
    frame_dimensions(frame)
    encoded = encoder(frame)
    instruction = _request_instruction(video=video, frame_index=frame_index,
                                       previous_observations=previous_observations,
                                       user_instruction=user_instruction)
    payload = build_chat_payload(model=model, encoded_image=encoded, instruction=instruction, video=video)
    primary_error = None
    raw = None
    parsed = None
    try:
        try:
            raw = transport.chat(payload, timeout_seconds)
            parsed = parse_response(raw, instruction=instruction, user_instruction=user_instruction, video=video)
        except BaseException as exc:  # Preserve the primary oracle/transport failure through cleanup.
            primary_error = exc
    finally:
        cleanup_error = None
        try:
            transport.cleanup(model, timeout_seconds)
        except Exception as exc:
            cleanup_error = exc
    if primary_error is not None:
        if isinstance(primary_error, BridgeError):
            if raw is not None:
                primary_error.details["raw_response"] = raw
            if cleanup_error is not None:
                primary_error.details["cleanup_error"] = str(cleanup_error)
        raise primary_error
    if cleanup_error is not None:
        raise BridgeError("RESOURCE_RELEASE_PENDING", "model cleanup failed", subcode="OLLAMA_UNLOAD_FAILED",
                          details={"cause": str(cleanup_error), "raw_response": raw})
    return FrameCall(raw_response=raw, parsed=parsed)


def prompt_spec(*, mode: str, observations: list[str], inferences: list[str], unknowns: list[str],
                creative_prompt: str, tags: list[str], changes: list[str] | None = None) -> dict:
    if mode not in {"documentary", "realistic", "scifi", "science", "cinematic", "stylized"}:
        raise BridgeError("CONTRACT_UNSUPPORTED", "unsupported prompt mode", subcode="PROMPT_MODE_UNSUPPORTED")
    return {
        "schema_version": "lvw.prompt/1",
        "mode": mode,
        "domains": {
            "observation": observations,
            "inference": inferences,
            "user_evidence": [],
            "creative_intent": [creative_prompt],
            "unknowns": unknowns,
        },
        "technical": {
            "duration_seconds": None,
            "aspect_ratio": "",
            "fps_intent": None,
            "camera_motion": "; ".join(changes or []),
            "subject_action": "",
            "lighting": "",
            "composition": "",
            "style_notes": "",
            "beats": [],
        },
        "locked_fields": [],
        "text_zh": "",
        "text_en": creative_prompt,
        "tags": tags,
        "negative": "",
        "template_id": "lvw-v0-bridge-compact",
        "template_version": "1.0.0",
    }


class BridgeOwner:
    """Shared owner invoked only through the registered public node classes."""

    def __init__(self, transport=None, encoder=None):
        self.transport = transport or OllamaLoopbackTransport()
        self.encoder = encoder or encode_comfy_frame

    def analyze_image(self, image, *, model: str, user_instruction: str, mode: str, timeout_seconds: int):
        frames = split_frames(image)
        if len(frames) != 1:
            raise BridgeError("MEDIA_LIMIT_EXCEEDED", "image analysis requires exactly one image",
                              subcode="IMAGE_COUNT_LIMIT")
        if not _INFERENCE_LOCK.acquire(blocking=False):
            raise BridgeError("RESOURCE_BUSY", "another LVW bridge request is active", subcode="LVW_BRIDGE_LOCKED")
        try:
            call = call_one_frame(transport=self.transport, encoder=self.encoder, frame=frames[0], model=model,
                                  timeout_seconds=timeout_seconds, video=False, frame_index=None,
                                  previous_observations=[], user_instruction=user_instruction)
            parsed = call.parsed
            suggestion = prompt_spec(mode=mode, observations=parsed["observations"],
                                     inferences=parsed["inferences"], unknowns=parsed["unknowns"],
                                     creative_prompt=parsed["prompt"], tags=parsed["tags"])
            return call.raw_response, json.dumps(suggestion, ensure_ascii=False, separators=(",", ":"))
        finally:
            _INFERENCE_LOCK.release()

    def analyze_video(self, frames_value, *, model: str, user_instruction: str, mode: str, timeout_seconds: int):
        frames = split_frames(frames_value)
        if not 1 <= len(frames) <= MAX_VIDEO_FRAMES:
            raise BridgeError("MEDIA_LIMIT_EXCEEDED", f"video analysis requires 1..{MAX_VIDEO_FRAMES} ordered frames",
                              subcode="VIDEO_FRAME_COUNT_LIMIT")
        if not _INFERENCE_LOCK.acquire(blocking=False):
            raise BridgeError("RESOURCE_BUSY", "another LVW bridge request is active", subcode="LVW_BRIDGE_LOCKED")
        try:
            calls = []
            previous = []
            for index, frame in enumerate(frames):
                try:
                    call = call_one_frame(transport=self.transport, encoder=self.encoder, frame=frame, model=model,
                                          timeout_seconds=timeout_seconds, video=True, frame_index=index,
                                          previous_observations=previous, user_instruction=user_instruction)
                except BridgeError as exc:
                    exc.details["prior_frame_raw_responses"] = [item.raw_response for item in calls]
                    raise
                calls.append(call)
                previous.extend(call.parsed["observations"])
            observations = [item for call in calls for item in call.parsed["observations"]]
            inferences = [item for call in calls for item in call.parsed["inferences"]]
            unknowns = [item for call in calls for item in call.parsed["unknowns"]]
            changes = [call.parsed["change"] for call in calls]
            tags = list(dict.fromkeys(item for call in calls for item in call.parsed["tags"]))
            creative_prompt = calls[-1].parsed["prompt"]
            suggestion = prompt_spec(mode=mode, observations=observations, inferences=inferences,
                                     unknowns=unknowns, creative_prompt=creative_prompt, tags=tags,
                                     changes=changes)
            raw = json.dumps({"frame_raw_responses": [call.raw_response for call in calls]},
                             ensure_ascii=False, separators=(",", ":"))
            return raw, json.dumps(suggestion, ensure_ascii=False, separators=(",", ":"))
        finally:
            _INFERENCE_LOCK.release()
