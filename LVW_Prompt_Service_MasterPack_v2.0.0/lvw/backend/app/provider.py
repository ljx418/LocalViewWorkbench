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
from PIL import Image, ImageDraw, ImageChops, ImageStat

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
VIDEO_PRESENTATION_VERSION = "temporal-sheet/4-colour-alignment"
VIDEO_TASK = (
    "Analyze ONE sampled VIDEO. The attached sheet has full source frames F1, F2, ... in "
    "timestamp order, and DERIVED D adjacent absolute RGB differences (black=unchanged pixels). "
    "F labels/times and D maps are metadata, not scene content. Compare EVERY F panel: subject "
    "placement and background landmarks separately. A fixed subject does not imply a fixed background. "
    "Report the scene, not the sheet layout. Only sampled frames were seen; audio, intervening events "
    "and continuous motion remain unverified. Return compact schema JSON with Chinese prompt_zh "
    "and English prompt. Keep observations, inferences and unknowns separate.\n"
    "GROUNDING: use the supplied measurements, computed from actual decoded pixels, alongside "
    "the image. Nonzero pixel differences rule out identical frames but alone do not establish motion. "
    "different_pixel_percent is already 0..100, not a fraction. Image registration finds translations "
    "of NEXT toward PREVIOUS on a bounded common window. Nonzero offsets with reduced error show "
    "apparent spatial differences, not physical camera movement. Periodic patterns can alias. "
    "Colour-component registration applies the same search to R-G, G-B and B-R projections. "
    "These are pixel components, not object labels. Distinct informative components can align "
    "differently: do not assume one rigid translation describes the whole scene. Untextured "
    "components and tied offsets are inconclusive.\n"
    "Before returning, remove unsupported temporal claims from ALL fields: 'appears stationary' "
    "or 'positions are consistent' is still a claim. If visual inspection cannot resolve measured "
    "spatial differences, state the measured change and leave its cause/direction unknown. Do not "
    "assert an unchanged background, nor invent lighting/compression/noise explanations. Include "
    "supported temporal differences in the reconstruction prompts; negative is only unwanted "
    "generation defects, never observed changes. camera_motion and subject_action may explicitly "
    "state uncertainty. Do not confuse measured pixel alignment direction with physical camera direction."
)
VIDEO_TEMPLATE_SHA256 = hashlib.sha256((TEMPLATE_SHA256 + VIDEO_TASK +
    VIDEO_PRESENTATION_VERSION + json.dumps(VIDEO_SCHEMA, sort_keys=True)).encode()).hexdigest()


def build_temporal_sheet(decoded) -> bytes:
    """Complete source panels plus explicitly derived residuals; one <=768px PNG."""
    count = len(decoded.frames)
    if not 1 <= count <= 4 or len(decoded.manifest) != count:
        raise AppError("PARSE_PARTIAL", "视频实际帧与时间元数据不匹配", status_code=503)
    cols = min(count, 2)
    rows = (count + cols - 1) // cols
    width = cols * 384
    source_height = rows * 256
    canvas = Image.new("RGB", (width, source_height + (256 if count > 1 else 0)), "#161b25")
    draw = ImageDraw.Draw(canvas)
    sources = []

    def panel(image, x, y, panel_width, label, outline):
        # Thumbnail only: never crop, stretch, replace or duplicate a source frame.
        thumbnail = image.copy()
        thumbnail.thumbnail((panel_width - 8, 224), Image.Resampling.LANCZOS)
        canvas.paste(thumbnail, (x + (panel_width - thumbnail.width) // 2,
                                y + 28 + (224 - thumbnail.height) // 2))
        draw.rectangle((x, y, x + panel_width - 1, y + 255), outline=outline, width=2)
        draw.text((x + 8, y + 8), label, fill="white")

    for index, payload in enumerate(decoded.frames):
        with Image.open(BytesIO(payload)) as source:
            image = source.convert("RGB")
        if sources and image.size != sources[0].size:
            raise AppError("PARSE_PARTIAL", "视频采样帧尺寸不一致", status_code=503)
        sources.append(image)
        seconds = float(decoded.manifest[index]["time_seconds"])
        panel(image, (index % cols) * 384, (index // cols) * 256, 384,
              f"F{index + 1} | {seconds:.3f}s", "#8896aa")

    if count > 1:
        residual_width = width // (count - 1)
        for index, (left, right) in enumerate(zip(sources, sources[1:])):
            panel(ImageChops.difference(left, right), index * residual_width,
                  source_height, residual_width,
                  f"D{index + 1}->{index + 2} DERIVED abs RGB", "#ceaa68")
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def temporal_pixel_measurements(images: list[bytes]) -> list[dict]:
    """Measured metadata only: no motion direction/class or sample-specific answers."""
    decoded=[]
    for payload in images:
        with Image.open(BytesIO(payload)) as image:
            decoded.append(image.convert('RGB'))
    result=[]
    for index,(left,right) in enumerate(zip(decoded,decoded[1:]),1):
        if left.size != right.size:
            raise AppError('PARSE_PARTIAL','视频采样帧尺寸不一致',status_code=503)
        difference=ImageChops.difference(left,right)
        red,green,blue=difference.split()
        nonzero=ImageChops.lighter(ImageChops.lighter(red,green),blue)
        changed=left.width*left.height-nonzero.histogram()[0]
        result.append({'from_frame':index,'to_frame':index+1,
            'changed_pixel_count':changed,'frame_pixel_count':left.width*left.height,
            'different_pixel_percent':round(100*changed/(left.width*left.height),4),
            'mean_absolute_rgb_delta':round(sum(ImageStat.Stat(difference).mean)/3,6)})
    return result


def _register_component(previous: Image.Image, next_image: Image.Image) -> dict:
    """Same bounded, fixed-area registration for any scalar pixel component."""
    width,height=previous.size
    radius=min(10,(min(width,height)-1)//4)
    if radius<1:
        return {'usable':False,'reason':'analysis_too_narrow'}
    window=(radius,radius,width-radius,height-radius)
    reference=previous.crop(window)
    if ImageStat.Stat(reference).stddev[0]==0:
        return {'usable':False,'reason':'reference_has_no_texture'}
    scores=[]
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            shifted=next_image.crop((window[0]-dx,window[1]-dy,window[2]-dx,window[3]-dy))
            error=int(ImageStat.Stat(ImageChops.difference(reference,shifted)).sum[0])
            scores.append((error,dx*dx+dy*dy,dy,dx))
    best=min(scores)
    unaligned=next(value[0] for value in scores if value[2]==0 and value[3]==0)
    area=reference.width*reference.height
    return {'usable':True,'analysis_size':[width,height],'search_radius_px':radius,
        'next_to_previous_alignment_offset_px':{'x':best[3],'y':best[2]},
        'unaligned_mean_luma_error':round(unaligned/area,6),
        'best_aligned_mean_luma_error':round(best[0]/area,6),
        'relative_error_reduction':round((unaligned-best[0])/unaligned,6) if unaligned else 0,
        'equally_best_offsets':sum(value[0]==best[0] for value in scores)}


def temporal_alignment_measurements(images: list[bytes]) -> list[dict]:
    """Generic luma + colour-component registration, never object/camera labels.

    Opponent components are (first-second)/2+128, truncated/clamped by Pillow.
    Thumbnail filtering, central-window/search limits and aliases apply to all.
    Component differences do not identify semantic regions or physical causes.
    """
    decoded=[]
    original_size=None
    for payload in images:
        with Image.open(BytesIO(payload)) as source:
            if original_size is not None and source.size!=original_size:
                raise AppError('PARSE_PARTIAL','视频采样帧尺寸不一致',status_code=503)
            original_size=source.size
            # Preserve the previous luma calculation exactly; colour is additional evidence.
            luma=source.convert('L')
            luma.thumbnail((128,128),Image.Resampling.LANCZOS)
            rgb=source.convert('RGB')
            rgb.thumbnail((128,128),Image.Resampling.LANCZOS)
            red,green,blue=rgb.split()
            decoded.append((luma,[ImageChops.subtract(first,second,scale=2,offset=128)
                for first,second in [(red,green),(green,blue),(blue,red)]]))
    result=[]
    for index,((previous,previous_colour),(next_image,next_colour)) in enumerate(zip(decoded,decoded[1:]),1):
        measurement={'from_frame':index,'to_frame':index+1,**_register_component(previous,next_image)}
        components=[]
        for name,left,right in zip(('R-G','G-B','B-R'),previous_colour,next_colour):
            registered=_register_component(left,right)
            component={'component':name,'usable':registered['usable']}
            if registered['usable']:
                component.update(offset_px=registered['next_to_previous_alignment_offset_px'],
                    zero_error=registered['unaligned_mean_luma_error'],
                    best_error=registered['best_aligned_mean_luma_error'],
                    error_reduction_percent=round(100*registered['relative_error_reduction'],4),
                    equally_best_offsets=registered['equally_best_offsets'])
            else:
                component['reason']=registered['reason']
            components.append(component)
        measurement['colour_components']=components
        result.append(measurement)
    return result



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
        self._record("admission_snapshot", job_id, baseline=baseline)
        if (baseline["gpu_used_mib"] >= 23552 or baseline["gpu_free_mib"] < 19047
                or baseline["available_ram_mib"] < 2048):
            raise AppError("RESOURCE_BUSY", "可用GPU/RAM容量不足，未启动本轮模型", status_code=503,
                           details=baseline)
        self._lease = (job_id, baseline)
        self._sent = False
        self._record("lease_acquired", job_id, baseline=baseline)

    async def release(self, job_id: str) -> bool:
        try:
            async with asyncio.timeout(30):
                return await self._release_bounded(job_id)
        except TimeoutError:
            self._record("lease_release_unproven", job_id)
            return False

    async def _release_bounded(self, job_id: str) -> bool:
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
                if time.monotonic() >= deadline:
                    break
                sample = await resources.snapshot()
                if time.monotonic() >= deadline:
                    break
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
        try:
            async with asyncio.timeout(5):
                return await self._readiness_bounded()
        except TimeoutError:
            return {"ready": False, "model": self.model, "reason": "OLLAMA_UNAVAILABLE", "loaded": False}

    async def _readiness_bounded(self) -> dict:
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
                   "model": self.model, "lease_job_id": self._lease[0] if self._lease else None, **fields}
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
        sheet = build_temporal_sheet(decoded)
        return await self._analyze_images([sheet], mode=mode, content_profile=content_profile,
            custom_guidance=custom_guidance, frames=decoded.manifest,
            source_frame_hashes=[hashlib.sha256(value).hexdigest() for value in decoded.frames],
            pixel_measurements=temporal_pixel_measurements(decoded.frames),
            alignment_measurements=temporal_alignment_measurements(decoded.frames))

    async def _analyze_images(self, images: list[bytes], *, mode: Mode,
                              content_profile: ContentProfile, custom_guidance: str,
                              frames=None, source_frame_hashes=None, pixel_measurements=None,
                              alignment_measurements=None):
        call_id = "call_" + uuid.uuid4().hex
        messages: list[dict[str, object]] = build_messages(mode, content_profile, custom_guidance)
        if frames is not None:
            messages[-1]["content"] = str(messages[-1]["content"]).replace(TEMPLATE_TEXT, VIDEO_TASK)
            messages[-1]["content"] += f"\nActual populated SOURCE panel count: {len(frames)}. Actual frame times (seconds): " + json.dumps([
                value["time_seconds"] for value in frames])
            messages[-1]["content"] += '\nMeasured image registration (not physical camera motion): '+json.dumps(alignment_measurements)
            messages[-1]["content"] += '\nMeasured adjacent-frame pixel differences (not motion estimates): '+json.dumps(pixel_measurements)
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
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                child = os.environ.get("LVW_AUTHORIZATION_CHILD")
                if os.environ.get("LVW_REQUIRE_BUDGET") == "1" and not child:
                    raise AppError("MODEL_UNAVAILABLE", "受控验证缺少预算子授权", status_code=503)
                self._record("provider_call_started", call_id,
                             frame_count=len(frames) if frames is not None else len(images),
                             payload_image_count=len(images), source_frame_hashes=source_frame_hashes,
                     pixel_measurements=pixel_measurements,
                     alignment_measurements=alignment_measurements,
                             presentation=VIDEO_PRESENTATION_VERSION if frames is not None else "single-image",
                             input_sha256=hashlib.sha256(b"".join(images)).hexdigest())
                if child:
                    from tools.local_program_authority import model_action
                    model_action(child)
                self._sent = True
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
            error = AppError("PARSE_PARTIAL", "模型响应不是 JSON", status_code=503)
            error.raw_response = raw
            raise error from exc
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
                parsed.template_version = "1.4.0"
        except (AppError, ValueError, KeyError, TypeError) as error:
            self._record("provider_call_failed", call_id, outcome="invalid_content")
            if not isinstance(error, AppError):
                error = AppError("PARSE_PARTIAL", "视频模型响应无法解析", status_code=503)
            error.raw_response = raw
            raise error
        self._record("provider_call_completed", call_id, outcome="success")
        return raw, parsed
