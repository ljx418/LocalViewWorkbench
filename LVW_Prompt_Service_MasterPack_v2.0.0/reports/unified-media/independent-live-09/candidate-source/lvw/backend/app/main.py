from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import BackgroundTasks, FastAPI, Header, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .build_info import build_id
from .errors import AppError
from .media import MediaStore
from .models import AnalyzeRequest
from .provider import OllamaProvider
from .runtime import OllamaRuntime
from .service import AnalysisService
from .body_limit import RequestBodyLimit, MAX_UPLOAD_REQUEST_BYTES, BodyLimitExceeded
from urllib.parse import urlsplit

SCHEMA_VERSION = "lvw.api/1"


def envelope(data, request_id: str) -> dict:
    value = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
    return {"data": value, "request_id": request_id, "schema_version": SCHEMA_VERSION}


def create_app(settings: Settings | None = None, provider=None, runtime=None) -> FastAPI:
    identity = build_id()
    settings = settings or Settings.local()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    media = MediaStore(settings.data_root)
    provider = provider or OllamaProvider(settings.ollama_endpoint, settings.model,
                                          settings.request_timeout_seconds)
    runtime = runtime or OllamaRuntime(provider, settings.ollama_executable, settings.data_root)
    service = AnalysisService(media, provider)
    app = FastAPI(title="LVW Prompt Service", version="0.1.0", docs_url=None, redoc_url=None)
    app.add_middleware(RequestBodyLimit, upload_limit=MAX_UPLOAD_REQUEST_BYTES)
    app.state.media = media
    app.state.analysis = service
    app.state.runtime = runtime
    app.state.upload_keys = {}
    app.router.add_event_handler("shutdown", service.close)
    app.router.add_event_handler("shutdown", runtime.close)

    @app.middleware("http")
    async def local_security_headers(request: Request, call_next):
        # TestClient is an in-process transport, never a production network identity.
        host = urlsplit("http://" + request.headers.get("host", ""))
        if request.client and request.client.host != "testclient":
            if request.client.host not in {"127.0.0.1", "::1"} or host.hostname not in {"127.0.0.1", "::1"}:
                return JSONResponse(status_code=403, content={"error": {"code": "ORIGIN_FORBIDDEN",
                    "message": "仅允许本机地址", "retryable": False, "details": {}}, "request_id": uuid.uuid4().hex})
        origin = request.headers.get("origin")
        if origin and (origin != "http://" + request.headers.get("host", "")):
            return JSONResponse(status_code=403, content={"error": {"code": "ORIGIN_FORBIDDEN",
                "message": "仅允许同源访问", "retryable": False, "details": {}}, "request_id": uuid.uuid4().hex})
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        return JSONResponse(status_code=exc.status_code, content={"error": {
            "code": exc.code, "message": exc.message, "retryable": exc.retryable,
            "details": exc.details}, "request_id": request_id})

    @app.exception_handler(BodyLimitExceeded)
    async def handle_body_limit(request: Request, exc: BodyLimitExceeded):
        return await handle_app_error(request, AppError("MEDIA_LIMIT_EXCEEDED", exc.detail, status_code=422))

    @app.get("/health")
    async def health(request: Request):
        return envelope({"status": "ok", "model": settings.model, "scope": "R1-unified", "build_id": identity},
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/capabilities")
    async def capabilities(request: Request):
        return envelope({"media": ["image", "video"], "modes": ["documentary", "realistic", "scifi",
                         "science", "cinematic", "stylized"], "targets": ["natural", "image", "video"],
                         "stage": "R1-unified", "build_id": identity}, request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/readiness")
    async def readiness(request: Request):
        return envelope(await provider.readiness(),
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/runtime/status")
    async def runtime_status(request: Request):
        return envelope(await runtime.status(),
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    def require_runtime_control(request: Request) -> None:
        if request.headers.get("X-LVW-Control") != "local-ui":
            raise AppError("RUNTIME_CONTROL_FORBIDDEN", "Runtime control requires the local UI",
                           status_code=403)

    @app.post("/api/v1/runtime/ollama/start")
    async def runtime_start(request: Request):
        require_runtime_control(request)
        return envelope(await service.runtime_control(runtime.start),
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.post("/api/v1/runtime/ollama/reset")
    async def runtime_reset(request: Request):
        require_runtime_control(request)
        return envelope(await service.runtime_control(runtime.reset),
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.post("/api/v1/runtime/ollama/stop")
    async def runtime_stop(request: Request):
        require_runtime_control(request)
        return envelope(await service.runtime_control(runtime.stop),
                        request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.post("/api/v1/media", status_code=201)
    async def upload_media(request: Request, file: UploadFile,
                           idempotency_key: str = Header(min_length=1, max_length=128)):
        ref = await media.ingest(file)
        existing = app.state.upload_keys.get(idempotency_key)
        if existing:
            if existing.sha256 != ref.sha256:
                media.discard(ref.id)
                raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他媒体", status_code=409)
            media.discard(ref.id)
            return envelope(existing, request.headers.get("X-Request-ID") or uuid.uuid4().hex)
        app.state.upload_keys[idempotency_key] = ref
        return envelope(ref, request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.post("/api/v1/jobs/analyze", status_code=202)
    async def analyze(body: AnalyzeRequest, request: Request, background_tasks: BackgroundTasks,
                      idempotency_key: str = Header(min_length=1, max_length=128)):
        ready = await provider.readiness()
        if not ready["ready"]:
            raise AppError("MODEL_UNAVAILABLE", "本地视觉模型尚未就绪", status_code=503,
                           retryable=True, details={"model": ready["model"],
                                                    "reason": ready["reason"]})
        job = service.submit(body, idempotency_key)
        if job.status == "queued":
            background_tasks.add_task(service.run, job.id, body)
        return envelope(job, request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/jobs/{id}")
    async def get_job(id: str, request: Request):
        return envelope(service.get_job(id), request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.post("/api/v1/jobs/{id}/cancel")
    async def cancel_job(id: str, request: Request,
                         idempotency_key: str = Header(min_length=1, max_length=128)):
        require_runtime_control(request)
        return envelope(service.cancel(id), request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/media/{id}")
    async def get_media(id: str, request: Request):
        ref, _ = media.get(id)
        return envelope(ref, request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    @app.get("/api/v1/model-runs/{id}")
    async def get_run(id: str, request: Request):
        return envelope(service.get_run(id), request.headers.get("X-Request-ID") or uuid.uuid4().hex)

    static_root = settings.static_root
    if static_root and (static_root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_root, html=True), name="frontend")
    return app


def default_app() -> FastAPI:
    package_root = Path(__file__).resolve().parents[2]
    return create_app(Settings.local(static_root=package_root / "frontend" / "dist"))


app = default_app()
