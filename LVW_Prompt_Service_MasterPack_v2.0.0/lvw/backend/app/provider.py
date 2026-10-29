from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
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
        "prompt": {"type": "string", "minLength": 1, "maxLength": 800},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    },
    "required": ["observations", "inferences", "unknowns", "prompt", "tags"],
    "additionalProperties": False,
}
TEMPLATE_TEXT = (
    "Analyze this single image. Return only compact JSON matching the supplied schema. "
    "observations must be visible facts; keep inferences and unknowns separate. "
    "The prompt must be a concrete English generation prompt grounded in the image."
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
    expected = {"observations", "inferences", "unknowns", "prompt", "tags"}
    if not isinstance(content, dict) or set(content) != expected:
        raise AppError("PARSE_PARTIAL", "模型字段与合同不一致", status_code=503)
    observations = _strings(content["observations"], "observations", required=True, max_items=6)
    inferences = _strings(content["inferences"], "inferences", required=False, max_items=4)
    unknowns = _strings(content["unknowns"], "unknowns", required=False, max_items=4)
    tags = _strings(content["tags"], "tags", required=False, max_items=8)
    prompt = content["prompt"]
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.strip()) > 800:
        raise AppError("PARSE_PARTIAL", "prompt 格式无效", status_code=503)
    return PromptSpec(
        mode=mode,
        domains=Domains(observation=observations, inference=inferences, user_evidence=[],
                        creative_intent=[], unknowns=unknowns),
        technical=Technical(duration_seconds=None, aspect_ratio="", fps_intent=None,
                            camera_motion="", subject_action="", lighting="",
                            composition="", style_notes="", beats=[]),
        locked_fields=[], text_zh="", text_en=prompt.strip(), tags=tags, negative="",
        template_id="lvw-r1a-image", template_version="1.0.0",
    )


class OllamaProvider:
    def __init__(self, endpoint: str, model: str, timeout_seconds: int):
        validate_endpoint(endpoint)
        self.endpoint = endpoint
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def analyze(self, image_path: Path, *, mode: Mode) -> tuple[str, PromptSpec]:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
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
            raise AppError("MODEL_TIMEOUT", "本地模型响应超时", status_code=503, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AppError("MODEL_UNAVAILABLE", "无法连接本地模型", status_code=503, retryable=True) from exc
        raw = response.text
        try:
            envelope = response.json()
        except json.JSONDecodeError as exc:
            raise AppError("PARSE_PARTIAL", "模型响应不是 JSON", status_code=503) from exc
        return raw, parse_ollama_response(envelope, mode=mode)
