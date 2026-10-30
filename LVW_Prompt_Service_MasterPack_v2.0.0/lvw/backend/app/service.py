from __future__ import annotations

import asyncio
import hashlib
import json
import uuid

from .errors import AppError
from .media import MediaStore
from .models import AnalyzeRequest, Job, ModelRun
from .provider import OllamaProvider, TEMPLATE_SHA256


class AnalysisService:
    def __init__(self, media: MediaStore, provider: OllamaProvider):
        self.media = media
        self.provider = provider
        self.jobs: dict[str, Job] = {}
        self.runs: dict[str, ModelRun] = {}
        self.idempotency: dict[str, tuple[str, str]] = {}
        self._worker = asyncio.Lock()

    def submit(self, request: AnalyzeRequest, key: str) -> Job:
        payload_hash = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        previous = self.idempotency.get(key)
        if previous:
            old_hash, job_id = previous
            if old_hash != payload_hash:
                raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求", status_code=409)
            return self.jobs[job_id]
        self.media.get(request.media_ref_id)
        job_id = "job_" + uuid.uuid4().hex
        job = Job(id=job_id, status="queued", resource_state="unknown", attempt_id=None,
                  cancel_epoch=0, progress_done=0, progress_total=1, result_ref=None, error_code=None)
        self.jobs[job_id] = job
        self.idempotency[key] = (payload_hash, job_id)
        return job

    async def run(self, job_id: str, request: AnalyzeRequest) -> None:
        job = self.jobs[job_id]
        async with self._worker:
            attempt_id = "att_" + uuid.uuid4().hex
            self.jobs[job_id] = job.model_copy(update={"status": "running", "resource_state": "busy",
                                                       "attempt_id": attempt_id})
            media, path = self.media.get(request.media_ref_id)
            try:
                raw, spec = await self.provider.analyze(path, mode=request.mode,
                    content_profile=request.content_profile,
                    custom_guidance=request.custom_guidance)
                run_id = "run_" + uuid.uuid4().hex
                config_hash = hashlib.sha256(json.dumps({"mode": request.mode,
                    "profile": request.config_profile, "content_profile": request.content_profile,
                    "custom_guidance": request.custom_guidance}, ensure_ascii=False,
                    sort_keys=True).encode()).hexdigest()
                run = ModelRun(id=run_id, job_id=job_id, attempt_id=attempt_id,
                    model_tag=self.provider.model, model_digest=None, status="succeeded",
                    input_sha256=media.sha256, template_sha256=TEMPLATE_SHA256,
                    config_sha256=config_hash, raw_response=raw, parsed_spec=spec,
                    error_code=None, frames=[])
                self.runs[run_id] = run
                self.jobs[job_id] = self.jobs[job_id].model_copy(update={
                    "status": "succeeded", "resource_state": "released", "progress_done": 1,
                    "result_ref": run_id, "error_code": None})
            except AppError as exc:
                self.jobs[job_id] = self.jobs[job_id].model_copy(update={
                    "status": "failed", "resource_state": "released", "progress_done": 1,
                    "error_code": exc.code})
            except Exception:
                self.jobs[job_id] = self.jobs[job_id].model_copy(update={
                    "status": "failed", "resource_state": "released", "progress_done": 1,
                    "error_code": "MODEL_UNAVAILABLE"})

    def get_job(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise AppError("ATTEMPT_STALE", "找不到分析任务", status_code=404)
        return self.jobs[job_id]

    def get_run(self, run_id: str) -> ModelRun:
        if run_id not in self.runs:
            raise AppError("ATTEMPT_STALE", "找不到模型结果", status_code=404)
        return self.runs[run_id]
