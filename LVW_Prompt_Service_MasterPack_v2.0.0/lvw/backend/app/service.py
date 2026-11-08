from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import uuid

from .errors import AppError
from .media import MediaStore
from .models import AnalyzeRequest, FrameRef, Job, ModelRun
from .provider import OllamaProvider, TEMPLATE_SHA256, VIDEO_TEMPLATE_SHA256
from . import resources


class AnalysisService:
    """One serialized inference owner, explicit cancellation and terminal publication."""
    def __init__(self, media: MediaStore, provider: OllamaProvider):
        self.media, self.provider = media, provider
        self.jobs: dict[str, Job] = {}
        self.runs: dict[str, ModelRun] = {}
        self.idempotency: dict[str, tuple[str, str]] = {}
        self._worker = asyncio.Lock()
        self._cancels: dict[str, threading.Event] = {}
        self._provider_tasks: dict[str, asyncio.Task] = {}
        self._active: str | None = None
        self._controller_busy = False
        self._tasks: set[asyncio.Task] = set()

    def submit(self, request: AnalyzeRequest, key: str) -> Job:
        if self._controller_busy:
            raise AppError("RESOURCE_BUSY", "模型服务正在切换，请稍后重试", status_code=409)
        payload_hash = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        previous = self.idempotency.get(key)
        if previous:
            old_hash, job_id = previous
            if old_hash != payload_hash:
                raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求", status_code=409)
            return self.jobs[job_id]
        if len(self.jobs) >= 128:
            raise AppError("RESOURCE_BUSY", "本次会话任务已达上限，请先导出再重启工作台", status_code=409)
        media, _ = self.media.get(request.media_ref_id)
        job_id = "job_" + uuid.uuid4().hex
        job = Job(id=job_id, status="queued", resource_state="unknown", attempt_id=None,
            cancel_epoch=0, progress_done=0, progress_total=5 if media.kind == "video" else 1,
            result_ref=None, error_code=None)
        self.jobs[job_id] = job
        self._cancels[job_id] = threading.Event()
        self.idempotency[key] = (payload_hash, job_id)
        return job

    def update(self, job_id, **changes):
        self.jobs[job_id] = self.jobs[job_id].model_copy(update=changes)

    def cancel(self, job_id: str) -> Job:
        job = self.get_job(job_id)
        if job.status in {"queued", "preparing", "running", "cancelling"} and not self._cancels[job_id].is_set():
            self._cancels[job_id].set()
            queued = job.status == "queued"
            self.update(job_id, cancel_epoch=job.cancel_epoch + 1,
                status="cancelled" if queued else "cancelling",
                resource_state="released" if queued else "releasing", error_code="JOB_CANCELLED")
            task = self._provider_tasks.get(job_id)
            if task and not task.done():
                task.cancel()
        return self.jobs[job_id]

    async def _monitor(self, job_id: str, errors: list):
        while True:
            try:
                sample = await resources.snapshot()
                self.provider._record("running_resource_sample", job_id, **sample)
                if sample["gpu_used_mib"] >= 23552 or sample["available_ram_mib"] < 2048:
                    raise AppError("RESOURCE_BUSY", "运行资源触及边界，已停止本轮分析", status_code=503)
            except Exception as error:
                if not isinstance(error, AppError):
                    error = AppError("RESOURCE_BUSY", "资源监测未能完成，已停止本轮分析", status_code=503)
                errors.append(error)
                self._cancels[job_id].set()
                task = self._provider_tasks.get(job_id)
                if task and not task.done():
                    task.cancel()
                return
            await asyncio.sleep(1)

    async def run(self, job_id: str, request: AnalyzeRequest) -> None:
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._worker:
                if self._cancels[job_id].is_set() or self.jobs[job_id].status != "queued":
                    return
                self._active = job_id
                attempt_id = "att_" + uuid.uuid4().hex
                self.update(job_id, status="preparing", resource_state="busy", attempt_id=attempt_id)
                lease = False
                monitor = None
                raw, spec, frames, failure = "", None, [], None
                resource_errors = []
                media = self.media.refs[request.media_ref_id]
                try:
                    media, path = self.media.get(request.media_ref_id)
                    if hasattr(self.provider, "acquire"):
                        await self.provider.acquire(job_id)
                        lease = True
                        monitor = asyncio.create_task(self._monitor(job_id, resource_errors))
                    if self._cancels[job_id].is_set():
                        raise AppError("JOB_CANCELLED", "本次分析已取消")
                    options = {"mode": request.mode, "content_profile": request.content_profile,
                               "custom_guidance": request.custom_guidance}
                    if media.kind == "video":
                        decoded = await asyncio.to_thread(self.media.video.decode, path, self._cancels[job_id])
                        if decoded.source_sha256 != media.sha256:
                            raise AppError("MEDIA_INVALID", "视频在上传后发生改变", status_code=422)
                        targets = {}
                        for target in [decoded.duration_seconds * (2 * i + 1) / 8 for i in range(4)]:
                            value = next((v for v in decoded.manifest if v["time_seconds"] >= target), None)
                            if value is None and not targets:
                                value = decoded.manifest[0]
                            if value is not None:
                                targets.setdefault(value["index"], target)
                        frames = [FrameRef(index=value["index"], target_seconds=targets[value["index"]],
                            source_pts=value["pts"], time_base_num=value["time_base_num"],
                            time_base_den=value["time_base_den"], sha256=value["sha256"],
                            time_basis="decoded_pts") for value in decoded.manifest]
                        self.update(job_id, progress_done=len(frames), progress_total=len(frames) + 1)
                        operation = lambda: self.provider.analyze_video(decoded, **options)
                    else:
                        operation = lambda: self.provider.analyze(path, **options)
                    if self._cancels[job_id].is_set():
                        raise AppError("JOB_CANCELLED", "本次分析已取消")
                    self.update(job_id, status="running")
                    provider_task = asyncio.create_task(operation())
                    self._provider_tasks[job_id] = provider_task
                    raw, spec = await asyncio.wait_for(provider_task, timeout=420)
                except asyncio.CancelledError:
                    failure = AppError("JOB_CANCELLED", "本次分析已取消")
                except asyncio.TimeoutError:
                    failure = AppError("MODEL_TIMEOUT", "本轮分析超过总时限", status_code=503)
                except AppError as error:
                    failure = error
                    raw = getattr(error, "raw_response", "")
                except Exception:
                    failure = AppError("MODEL_UNAVAILABLE", "本轮分析未能完成", status_code=503)
                finally:
                    if monitor:
                        monitor.cancel()
                        await asyncio.gather(monitor, return_exceptions=True)
                    self._provider_tasks.pop(job_id, None)
                    self.update(job_id, resource_state="releasing")
                    released = not (not lease and getattr(self.provider, "_lease", None) is not None)
                    if lease:
                        try:
                            released = await self.provider.release(job_id)
                        except Exception:
                            released = False
                    if resource_errors:
                        failure = resource_errors[0]
                    cancelled = self._cancels[job_id].is_set() and not resource_errors
                    if cancelled:
                        failure = AppError("JOB_CANCELLED", "本次分析已取消")
                        raw, spec = "", None
                    if not released:
                        failure = AppError("RESOURCE_RELEASE_PENDING", "资源释放未能确认，请导出人工稿后重置本轮模型服务", status_code=503)
                        spec = None
                    result_ref = None
                    if not cancelled and (spec is not None or raw):
                        result_ref = "run_" + uuid.uuid4().hex
                        config_hash = hashlib.sha256(json.dumps({**request.model_dump(),
                            "video_num_ctx": 4096 if media.kind == "video" else None}, sort_keys=True).encode()).hexdigest()
                        self.runs[result_ref] = ModelRun(id=result_ref, job_id=job_id, attempt_id=attempt_id,
                            model_tag=self.provider.model, model_digest=None,
                            status="succeeded" if not failure else "failed", input_sha256=media.sha256,
                            template_sha256=VIDEO_TEMPLATE_SHA256 if media.kind == "video" else TEMPLATE_SHA256,
                            config_sha256=config_hash, raw_response=raw, parsed_spec=spec if not failure else None,
                            error_code=failure.code if failure else None, frames=frames)
                    self.update(job_id, status="cancelled" if cancelled else "failed" if failure else "succeeded",
                        resource_state="released" if released else "unknown", result_ref=result_ref,
                        error_code=failure.code if failure else None,
                        progress_done=self.jobs[job_id].progress_total if not failure else self.jobs[job_id].progress_done)
                    self._active = None
        finally:
            self._tasks.discard(task)

    async def runtime_control(self, operation):
        if self._active or any(x.status == "queued" for x in self.jobs.values()) or self._controller_busy:
            raise AppError("RESOURCE_BUSY", "请先取消分析并等待释放，再切换模型服务", status_code=409)
        self._controller_busy = True
        try:
            result = await operation()
            if getattr(self.provider, "_lease", None) is not None:
                await self.provider.release(self.provider._lease[0])
            return result
        finally:
            self._controller_busy = False

    async def close(self):
        for job_id in self.jobs:
            self.cancel(job_id)
        pending = [task for task in self._tasks if task is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def get_job(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise AppError("ATTEMPT_STALE", "找不到分析任务", status_code=404)
        return self.jobs[job_id]

    def get_run(self, run_id: str) -> ModelRun:
        if run_id not in self.runs:
            raise AppError("ATTEMPT_STALE", "找不到模型结果", status_code=404)
        return self.runs[run_id]
