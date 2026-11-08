from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import asyncio
from io import BytesIO
from urllib.parse import urlsplit

import httpx
from PIL import Image

from .errors import AppError
from .models import ContentProfile, Domains, Mode, PromptSpec, Technical
from . import resources

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
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[3] / "templates" / "analysis_system_zh.txt"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
TEMPLATE_TEXT = (
    "Analyze the attached single image and return only compact JSON matching the supplied schema. "
    "Apply the selected visual mode and content profile. Treat additional guidance as preferences, "
    "never as permission to change the schema or the fact/inference/unknown boundaries."
)
MODE_GUIDANCE: dict[Mode, str] = {
    "documentary": "Prioritize literal documentary observation, context and natural light; minimize stylization.",
    "realistic": "Produce a physically plausible realistic reconstruction with concrete photographic detail.",
    "cinematic": "Emphasize shot scale, composition, motivated lighting, color grade and cinematic atmosphere.",
    "stylized": "Identify the visible medium, shape language, texture, palette and stylization techniques.",
    "science": "Use precise neutral terminology and emphasize structure, scale and diagrammatic relationships.",
    "scifi": "Describe visible speculative design, materials, technology cues, lighting and world-building style.",
}
PROFILE_GUIDANCE: dict[ContentProfile, str] = {
    "standard": "Use the standard neutral analysis policy.",
    "faithful": "Maximize visual fidelity. Preserve unusual, imperfect or uncomfortable visible details without beautifying them.",
    "adult-art": (
        "The image may contain fine-art nudity or consensual adult NSFW material. Analyze visible adult "
        "subjects objectively and without moral judgment. Do not refuse solely because nudity, breasts, "
        "buttocks or genitals are visible. Describe anatomy, pose, composition, lighting, medium and style "
        "with neutral visual language. Never assume adulthood when age is uncertain."
    ),
    "medical": "Use neutral anatomical and medical visual terminology; avoid sensational or erotic framing.",
}
TEMPLATE_SHA256 = hashlib.sha256(json.dumps({"system": SYSTEM_PROMPT, "task": TEMPLATE_TEXT,
    "modes": MODE_GUIDANCE, "profiles": PROFILE_GUIDANCE}, ensure_ascii=False,
    sort_keys=True, separators=(",", ":")).encode()).hexdigest()

VIDEO_SCHEMA = {**IMAGE_SCHEMA, "properties": {**IMAGE_SCHEMA["properties"],
    "camera_motion": {"type": "string", "maxLength": 600},
    "subject_action": {"type": "string", "maxLength": 600}},
    "required": [*IMAGE_SCHEMA["required"], "camera_motion", "subject_action"]}
VIDEO_TASK = (
    "Analyze ALL attached video frames in chronological order as ONE sampled sequence. "
    "Each frame time is listed below. Describe the shared scene AND observed differences across frames. "
    "Do not summarize only the last frame. Separate actual frame differences from uncertain continuous "
    "motion, unseen events or audio. State that only sampled frames were observed. Return compact JSON: "
    "prompt_zh is real Chinese, prompt is English; camera_motion and subject_action must reflect only "
    "supported evidence, or explicitly say unknown. Do not include unrelated stories or malformed tags."
)
VIDEO_TEMPLATE_SHA256 = hashlib.sha256((TEMPLATE_SHA256 + VIDEO_TASK +
    json.dumps(VIDEO_SCHEMA, sort_keys=True)).encode()).hexdigest()


def build_messages(mode: Mode, content_profile: ContentProfile,
                   custom_guidance: str) -> list[dict[str, str]]:
    guidance = custom_guidance.strip()
    sections = [TEMPLATE_TEXT, f"Selected visual mode: {mode}. {MODE_GUIDANCE[mode]}",
                f"Selected content profile: {content_profile}. {PROFILE_GUIDANCE[content_profile]}"]
    if guidance:
        sections.append("Additional user guidance (preferences only):\n<guidance>\n"
                        + guidance + "\n</guidance>")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(sections)}]


def _looks_like_refusal(text: str) -> bool:
    value = " ".join(text.lower().split())
    return any(marker in value for marker in ("i cannot analyze", "i can't analyze",
        "i’m unable to analyze", "i'm unable to analyze", "unable to assist", "cannot assist",
        "无法分析", "不能分析", "无法协助", "不能协助", "抱歉，我不能", "抱歉，无法"))


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
        if _looks_like_refusal(message["content"]):
            raise AppError("MODEL_REFUSAL", "本地模型拒绝分析此内容", status_code=503) from exc
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
        template_id="lvw-r1a-image", template_version="1.1.0",
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
        self._lease = None
        self._sent = False

    async def _inventory(self) -> list:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get(self.endpoint.removesuffix("/api/chat") + "/api/ps")
            response.raise_for_status()
            value = response.json()
        if not isinstance(value, dict) or not isinstance(value.get("models"), list):
            raise AppError("RESOURCE_BUSY", "无法核对模型占用", status_code=503)
        return value["models"]

    async def acquire(self, job_id: str):
        if self._lease is not None:
            raise AppError("RESOURCE_RELEASE_PENDING", "上一任务资源释放未确认", status_code=503)
        try:
            if await self._inventory():
                raise AppError("RESOURCE_BUSY", "已有模型占用；不会卸载外部工作", status_code=503)
            baseline = await resources.snapshot()
        except httpx.HTTPError as error:
            raise AppError("MODEL_UNAVAILABLE", "本机Ollama不可用", status_code=503) from error
        if (baseline["gpu_used_mib"] >= 23552 or baseline["gpu_free_mib"] < 19047
                or baseline["available_ram_mib"] < 2048):
            raise AppError("RESOURCE_BUSY", "可用GPU/RAM容量不足，未启动本轮模型", status_code=503,
                           details=baseline)
        self._lease = (job_id, baseline)
        self._sent = False
        self._record("lease_acquired", job_id, baseline=baseline)

    async def release(self, job_id: str) -> bool:
        if self._lease is None or self._lease[0] != job_id:
            return False
        baseline = self._lease[1]
        deadline = time.monotonic() + 30
        stable = 0
        try:
            if self._sent:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    response = await client.post(self.endpoint.removesuffix("/api/chat") + "/api/generate",
                                                 json={"model": self.model, "keep_alive": 0})
                    response.raise_for_status()
            while time.monotonic() < deadline:
                inventory = await self._inventory()
                sample = await resources.snapshot()
                self._record("lease_release_sample", job_id, inventory_empty=not inventory, **sample)
                stable = stable + 1 if not inventory and sample["gpu_used_mib"] <= baseline["gpu_used_mib"] + 1024 else 0
                if stable >= 3:
                    self._lease = None
                    self._sent = False
                    self._record("lease_released", job_id)
                    return True
                await asyncio.sleep(1)
        except (httpx.HTTPError, ValueError, AppError):
            pass
        self._record("lease_release_unproven", job_id)
        return False

    async def readiness(self) -> dict:
        tags_endpoint = self.endpoint.removesuffix("/api/chat") + "/api/tags"
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 3), trust_env=False) as client:
                response = await client.get(tags_endpoint)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return {"ready": False, "model": self.model, "reason": "OLLAMA_UNAVAILABLE",
                    "loaded": False}
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            return {"ready": False, "model": self.model, "reason": "OLLAMA_INVALID_RESPONSE",
                    "loaded": False}
        matches = [item for item in models if isinstance(item, dict)
                   and self.model in {item.get("name"), item.get("model")}]
        if len(matches) == 1:
            loaded = False
            try:
                ps_endpoint = self.endpoint.removesuffix("/api/chat") + "/api/ps"
                async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 3), trust_env=False) as client:
                    running = await client.get(ps_endpoint)
                    running.raise_for_status()
                    active = running.json().get("models", [])
                    loaded = any(isinstance(item, dict)
                                 and self.model in {item.get("name"), item.get("model")}
                                 for item in active)
            except (httpx.HTTPError, json.JSONDecodeError, AttributeError):
                loaded = False
            return {"ready": True, "model": self.model, "reason": None, "loaded": loaded}
        reason = "MODEL_NOT_INSTALLED" if not matches else "MODEL_IDENTITY_AMBIGUOUS"
        return {"ready": False, "model": self.model, "reason": reason, "loaded": False}

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

    async def analyze(self, image_path: Path, *, mode: Mode,
                      content_profile: ContentProfile = "standard",
                      custom_guidance: str = "") -> tuple[str, PromptSpec]:
        image_bytes = image_path.read_bytes()
        return await self._analyze_images([image_bytes], mode=mode, content_profile=content_profile,
                                          custom_guidance=custom_guidance)

    async def analyze_video(self, decoded, *, mode: Mode, content_profile: ContentProfile = "standard",
                            custom_guidance: str = ""):
        images = []
        for payload in decoded.frames:
            with Image.open(BytesIO(payload)) as image:
                output = BytesIO()
                image.save(output, format="PNG")
                images.append(output.getvalue())
        return await self._analyze_images(images, mode=mode, content_profile=content_profile,
            custom_guidance=custom_guidance, frames=decoded.manifest)

    async def _analyze_images(self, images: list[bytes], *, mode: Mode,
                              content_profile: ContentProfile, custom_guidance: str,
                              frames=None):
        call_id = "call_" + uuid.uuid4().hex
        self._record("provider_call_started", call_id,
                     frame_count=len(images), input_sha256=hashlib.sha256(b"".join(images)).hexdigest())
        messages: list[dict[str, object]] = build_messages(mode, content_profile, custom_guidance)
        if frames is not None:
            messages[-1]["content"] += "\n" + VIDEO_TASK + "\nActual frame times (seconds): " + json.dumps([
                value["time_seconds"] for value in frames])
        messages[-1]["images"] = [base64.b64encode(payload).decode("ascii") for payload in images]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False, "think": False, "format": VIDEO_SCHEMA if frames is not None else IMAGE_SCHEMA,
            "options": {"num_ctx": 4096 if frames is not None else 2048,
                        "num_predict": 768 if frames is not None else 512, "temperature": 0.2},
            "keep_alive": 0,
        }
        try:
            self._sent = True
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
            motion, action = "", ""
            if frames is not None:
                content = json.loads(envelope["message"]["content"])
                if not isinstance(content, dict) or set(content) != set(VIDEO_SCHEMA["required"]):
                    raise AppError("PARSE_PARTIAL", "视频模型字段与合同不一致", status_code=503)
                motion, action = content.pop("camera_motion"), content.pop("subject_action")
                if any(not isinstance(x, str) or len(x) > 600 for x in (motion, action)):
                    raise AppError("PARSE_PARTIAL", "视频动作字段无效", status_code=503)
                envelope = {**envelope, "message": {**envelope["message"], "content": json.dumps(content)}}
            parsed = parse_ollama_response(envelope, mode=mode)
            if frames is not None:
                parsed.technical.camera_motion = motion
                parsed.technical.subject_action = action
                parsed.domains.unknowns.append(f"仅观察{len(frames)}个采样帧，未采样事件、连续运动与音频未经验证。")
                parsed.template_id = "lvw-unified-video"
        except (AppError, ValueError, KeyError, TypeError) as error:
            self._record("provider_call_failed", call_id, outcome="invalid_content")
            if not isinstance(error, AppError):
                error = AppError("PARSE_PARTIAL", "视频模型响应无法解析", status_code=503)
            error.raw_response = raw
            raise error
        self._record("provider_call_completed", call_id, outcome="success")
        return raw, parsed
