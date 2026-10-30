from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Mode = Literal["documentary", "realistic", "scifi", "science", "cinematic", "stylized"]
ContentProfile = Literal["standard", "faithful", "adult-art", "medical"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameRef(StrictModel):
    index: int = Field(ge=0)
    pts: int | None = None
    time_base_num: int | None = None
    time_base_den: int | None = None
    time_seconds: float | None = None
    sha256: str


class MediaRef(StrictModel):
    id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    kind: Literal["image", "video"]
    display_name: str
    bytes: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    duration_seconds: float | None
    source_root_id: str | None
    relative_path: str | None
    availability: Literal["available", "missing", "permission_revoked"]
    frames: list[FrameRef]


class AnalyzeRequest(StrictModel):
    media_ref_id: str = Field(min_length=1, max_length=128)
    shot_id: str | None = Field(default=None, max_length=128)
    mode: Mode
    config_profile: str = Field(min_length=1, max_length=128)
    content_profile: ContentProfile = "standard"
    custom_guidance: str = Field(default="", max_length=800)


class Job(StrictModel):
    id: str
    kind: Literal["analyze", "segment", "batch", "generate"] = "analyze"
    status: Literal["queued", "preparing", "running", "partial", "succeeded", "failed", "cancelling", "cancelled", "interrupted", "submission_unknown"]
    resource_state: Literal["unknown", "busy", "releasing", "released"]
    attempt_id: str | None
    cancel_epoch: int = Field(ge=0)
    progress_done: int = Field(ge=0)
    progress_total: int = Field(ge=0)
    result_ref: str | None
    error_code: str | None


class Domains(StrictModel):
    observation: list[str]
    inference: list[str]
    user_evidence: list[dict[str, Any]]
    creative_intent: list[str]
    unknowns: list[str]


class Technical(StrictModel):
    duration_seconds: float | None
    aspect_ratio: str
    fps_intent: float | None
    camera_motion: str
    subject_action: str
    lighting: str
    composition: str
    style_notes: str
    beats: list[str]


class PromptSpec(StrictModel):
    schema_version: Literal["lvw.prompt/1"] = "lvw.prompt/1"
    mode: Mode
    domains: Domains
    technical: Technical
    locked_fields: list[str]
    text_zh: str
    text_en: str
    tags: list[str]
    negative: str
    template_id: str
    template_version: str


class ModelRun(StrictModel):
    id: str
    job_id: str
    attempt_id: str
    model_tag: str
    model_digest: str | None
    status: Literal["succeeded", "partial", "failed", "cancelled"]
    input_sha256: str
    template_sha256: str
    config_sha256: str
    raw_response: str
    parsed_spec: PromptSpec | None
    error_code: str | None
    frames: list[FrameRef]


class ErrorBody(StrictModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any]


class ErrorEnvelope(StrictModel):
    error: ErrorBody
    request_id: str
