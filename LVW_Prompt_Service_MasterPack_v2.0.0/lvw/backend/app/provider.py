from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit

import httpx

from .errors import AppError
from .models import Domains, Mode, PromptSpec, Technical

IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
        "inferences": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "unknowns": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "prompt_zh": {"type": "string", "minLength": 1, "maxLength": 800},
        "prompt": {"type": "string", "minLength": 1, "maxLength": 800},
        "negative": {"type": "string", "minLength": 1, "maxLength": 400},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    },
    "required": ["observations", "inferences", "unknowns", "prompt_zh", "prompt", "negative", "tags"],
    "additionalProperties": False,
}
TEMPLATE_TEXT = (
    "Analyze this single image. Return only compact JSON matching the supplied schema. "
    "observations must be visible facts; keep inferences and unknowns separate. "
    "prompt_zh and prompt must be concrete Chinese and English generation prompts grounded in the image. "
    "negative must contain concise generation constraints for defects not supported by the image."
)
TEMPLATE_SHA256 = hashlib.sha256(TEMPLATE_TEXT.encode()).hexdigest()


def validate_endpoint(endpoint: str) -> None:
    parsed = urlsplit(endpoint)
    if not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}
            and parsed.port == 11434 and parsed.path == "/api/chat"
            and not parsed.query and not parsed.fragment and not parsed.username):
        raise AppError("ORIGIN_FORBIDDEN", "Ollama 只能使用本机 11434 端口", status_code=503)


def _strings(value: object, field: str, *, required: bool, max_items: int) -> list[str]:
    if not isinstance(value, list) or len(value) > max_items:
        raise AppError("PARSE_PARTIAL", f"{field} 格式无效", status_code=503)
    result = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if len(result) != len(value) or (required and not result):
        raise AppError("PARSE_PARTIAL", f"{field} 格式无效", status_code=503)
    return result


def parse_ollama_response(envelope: dict, *, mode: Mode) -> PromptSpec:
    if envelope.get("done") is not True or envelope.get("done_reason") != "stop":
        raise AppError("PARSE_PARTIAL", "模型输出没有完整结束", status_code=503)
    message = envelope.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise AppError("PARSE_PARTIAL", "模型输出缺少正文", status_code=503)
    try:
        content = json.loads(message["content"])
    except json.JSONDecodeError as exc:
        raise AppError("PARSE_PARTIAL", "模型输出不是严格 JSON", status_code=503) from exc
    expected = {"observations", "inferences", "unknowns", "prompt_zh", "prompt", "negative", "tags"}
    if not isinstance(content, dict) or set(content) != expected:
        raise AppError("PARSE_PARTIAL", "模型字段与合同不一致", status_code=503)
    observations = _strings(content["observations"], "observations", required=True, max_items=6)
    inferences = _strings(content["inferences"], "inferences", required=False, max_items=4)
    unknowns = _strings(content["unknowns"], "unknowns", required=False, max_items=4)
    tags = _strings(content["tags"], "tags", required=False, max_items=8)
    prompt = content["prompt"]
    prompt_zh = content["prompt_zh"]
    negative = content["negative"]
    for field, value, limit in (("prompt_zh", prompt_zh, 800), ("prompt", prompt, 800),
                                ("negative", negative, 400)):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise AppError("PARSE_PARTIAL", f"{field} 格式无效", status_code=503)
    return PromptSpec(
        mode=mode,
        domains=Domains(observation=observations, inference=inferences, user_evidence=[],
                        creative_intent=[], unknowns=unknowns),
        technical=Technical(duration_seconds=None, aspect_ratio="", fps_intent=None,
                            camera_motion="", subject_action="", lighting="",
                            composition="", style_notes="", beats=[]),
        locked_fields=[], text_zh=prompt_zh.strip(), text_en=prompt.strip(), tags=tags,
        negative=negative.strip(),
        template_id="lvw-r1a-image", template_version="1.0.0",
    )


class OllamaProvider:
    def __init__(self, endpoint: str, model: str, timeout_seconds: int,
                 ledger_path: Path | None = None):
        validate_endpoint(endpoint)
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds
        configured = os.environ.get("LVW_PROVIDER_LEDGER")
        self.ledger_path = ledger_path or (Path(configured) if configured else None)

    async def readiness(self) -> dict:
        tags_endpoint = self.endpoint.removesuffix("/api/chat") + "/api/tags"
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 3), trust_env=False) as client:
                response = await client.get(tags_endpoint)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return {"ready": False, "model": self.model, "reason": "OLLAMA_UNAVAILABLE"}
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            return {"ready": False, "model": self.model, "reason": "OLLAMA_INVALID_RESPONSE"}
        matches = [item for item in models if isinstance(item, dict)
                   and self.model in {item.get("name"), item.get("model")}]
        if len(matches) == 1:
            return {"ready": True, "model": self.model, "reason": None}
        reason = "MODEL_NOT_INSTALLED" if not matches else "MODEL_IDENTITY_AMBIGUOUS"
        return {"ready": False, "model": self.model, "reason": reason}

    def _record(self, event: str, call_id: str, **fields) -> None:
        if self.ledger_path is None:
            return
        payload = {"event": event, "call_id": call_id, "time_ns": time.time_ns(),
                   "model": self.model, **fields}
        line = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
        descriptor = os.open(self.ledger_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)

    async def analyze(self, image_path: Path, *, mode: Mode) -> tuple[str, PromptSpec]:
        call_id = "call_" + uuid.uuid4().hex
        image_bytes = image_path.read_bytes()
        self._record("provider_call_started", call_id,
                     input_sha256=hashlib.sha256(image_bytes).hexdigest())
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": TEMPLATE_TEXT, "images": [encoded]}],
            "stream": False, "think": False, "format": IMAGE_SCHEMA,
            "options": {"num_ctx": 2048, "num_predict": 768, "temperature": 0.2},
            "keep_alive": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._record("provider_call_failed", call_id, outcome="timeout")
            raise AppError("MODEL_TIMEOUT", "本地模型响应超时", status_code=503, retryable=True) from exc
        except httpx.HTTPError as exc:
            self._record("provider_call_failed", call_id, outcome="http_error")
            raise AppError("MODEL_UNAVAILABLE", "无法连接本地模型", status_code=503, retryable=True) from exc
        raw = response.text
        try:
            envelope = response.json()
        except json.JSONDecodeError as exc:
            self._record("provider_call_failed", call_id, outcome="invalid_envelope")
            raise AppError("PARSE_PARTIAL", "模型响应不是 JSON", status_code=503) from exc
        try:
            parsed = parse_ollama_response(envelope, mode=mode)
        except AppError:
            self._record("provider_call_failed", call_id, outcome="invalid_content")
            raise
        self._record("provider_call_completed", call_id, outcome="success")
        return raw, parsed
