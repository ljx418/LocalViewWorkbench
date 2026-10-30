from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import AppError
from app.main import create_app
from app.models import Domains, PromptSpec, Technical


class FakeProvider:
    model = "gemma4:26b"

    def __init__(self, fail: bool = False, ready: bool = True):
        self.calls = 0
        self.fail = fail
        self.ready = ready

    async def readiness(self):
        return {"ready": self.ready, "model": self.model,
                "reason": None if self.ready else "OLLAMA_UNAVAILABLE", "loaded": False}

    async def analyze(self, image_path, *, mode):
        self.calls += 1
        if self.fail:
            raise AppError("MODEL_UNAVAILABLE", "offline", status_code=503, retryable=True)
        spec = PromptSpec(mode=mode,
            domains=Domains(observation=["A cobalt square fills the frame."], inference=[],
                            user_evidence=[], creative_intent=[], unknowns=[]),
            technical=Technical(duration_seconds=None, aspect_ratio="", fps_intent=None,
                                camera_motion="", subject_action="", lighting="",
                                composition="centered", style_notes="", beats=[]),
            locked_fields=[], text_zh="画面中央的钴蓝色方块", text_en="Cobalt square, centered composition",
            tags=["cobalt", "geometric"], negative="blur, watermark", template_id="lvw-r1a-image",
            template_version="1.0.0")
        return json.dumps({"message": {"content": "fixture"}}), spec


class FakeRuntime:
    def __init__(self):
        self.calls = []
        self.value = {"lvw": {"state": "ready"},
            "ollama": {"state": "stopped", "reachable": False, "model": "gemma4:26b",
                       "model_ready": False, "model_loaded": False, "managed": False,
                       "pid": None, "reason": "OLLAMA_UNAVAILABLE", "last_error": None},
            "actions": {"can_start": True, "can_reset": False, "can_stop": False}}

    async def status(self): return self.value
    async def start(self): self.calls.append("start"); return self.value
    async def reset(self): self.calls.append("reset"); return self.value
    async def stop(self): self.calls.append("stop"); return self.value
    async def close(self): return None

def make_client(tmp_path, provider, runtime=None):
    app = create_app(Settings.local(data_root=tmp_path), provider=provider, runtime=runtime)
    return TestClient(app)


def upload(client, payload, key="upload-1", name="sample.png"):
    return client.post("/api/v1/media", headers={"Idempotency-Key": key},
                       files={"file": (name, payload, "image/png")})


def test_health_and_security_headers(tmp_path):
    client = make_client(tmp_path, FakeProvider())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"]["scope"] == "R1a"
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert "127.0.0.1:11434" not in response.headers["content-security-policy"]


def test_readiness_distinguishes_live_service_from_unavailable_model(tmp_path):
    client = make_client(tmp_path, FakeProvider(ready=False))
    assert client.get("/health").status_code == 200
    response = client.get("/api/v1/readiness")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "ready": False, "model": "gemma4:26b", "reason": "OLLAMA_UNAVAILABLE",
        "loaded": False}


def test_runtime_control_requires_local_ui_header(tmp_path):
    runtime = FakeRuntime()
    client = make_client(tmp_path, FakeProvider(ready=False), runtime)
    assert client.get("/api/v1/runtime/status").json()["data"] == runtime.value
    for action in ("start", "reset", "stop"):
        response = client.post(f"/api/v1/runtime/ollama/{action}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "RUNTIME_CONTROL_FORBIDDEN"
    assert runtime.calls == []


def test_runtime_control_routes_only_fixed_actions(tmp_path):
    runtime = FakeRuntime()
    client = make_client(tmp_path, FakeProvider(ready=False), runtime)
    for action in ("start", "reset", "stop"):
        response = client.post(f"/api/v1/runtime/ollama/{action}",
                               headers={"X-LVW-Control": "local-ui"})
        assert response.status_code == 200
    assert runtime.calls == ["start", "reset", "stop"]


def test_analyze_fails_closed_before_job_when_model_is_not_ready(tmp_path, png_bytes):
    provider = FakeProvider(ready=False)
    client = make_client(tmp_path, provider)
    media = upload(client, png_bytes).json()["data"]
    response = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "not-ready"},
        json={"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
              "config_profile": "local-default"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert response.json()["error"]["details"]["reason"] == "OLLAMA_UNAVAILABLE"
    assert provider.calls == 0


def test_public_upload_job_poll_and_result_path(tmp_path, png_bytes):
    provider = FakeProvider()
    client = make_client(tmp_path, provider)
    uploaded = upload(client, png_bytes)
    assert uploaded.status_code == 201
    media = uploaded.json()["data"]
    submitted = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "analysis-1"},
        json={"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
              "config_profile": "local-default"})
    assert submitted.status_code == 202
    job_id = submitted.json()["data"]["id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()["data"]
    assert job["status"] == "succeeded"
    run = client.get(f"/api/v1/model-runs/{job['result_ref']}").json()["data"]
    assert run["input_sha256"] == media["sha256"]
    assert run["parsed_spec"]["domains"]["observation"] == ["A cobalt square fills the frame."]
    assert run["parsed_spec"]["text_zh"]
    assert run["parsed_spec"]["text_en"]
    assert run["parsed_spec"]["negative"]
    assert run["parsed_spec"]["tags"]
    assert provider.calls == 1


def test_analyze_idempotency_does_not_call_model_twice(tmp_path, png_bytes):
    provider = FakeProvider()
    client = make_client(tmp_path, provider)
    media = upload(client, png_bytes).json()["data"]
    body = {"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
            "config_profile": "local-default"}
    first = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "same"}, json=body)
    second = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "same"}, json=body)
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert provider.calls == 1
    changed = {**body, "mode": "cinematic"}
    assert client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "same"}, json=changed).status_code == 409


def test_model_failure_is_explicit_and_released(tmp_path, png_bytes):
    client = make_client(tmp_path, FakeProvider(fail=True))
    media = upload(client, png_bytes).json()["data"]
    response = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "failure"},
        json={"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
              "config_profile": "local-default"})
    job = client.get(f"/api/v1/jobs/{response.json()['data']['id']}").json()["data"]
    assert job["status"] == "failed"
    assert job["error_code"] == "MODEL_UNAVAILABLE"
    assert job["resource_state"] == "released"


def test_upload_rejects_corrupt_and_idempotency_conflict(tmp_path, png_bytes):
    client = make_client(tmp_path, FakeProvider())
    assert upload(client, b"not-an-image", key="bad").status_code == 422
    assert upload(client, png_bytes, key="stable").status_code == 201
    other = bytearray(png_bytes)
    other[-1] ^= 1
    assert upload(client, bytes(other), key="stable").status_code in {409, 422}


def test_upload_rejects_one_over_byte_limit_without_decode(tmp_path):
    client = make_client(tmp_path, FakeProvider())
    response = upload(client, b"x" * (20 * 1024 * 1024 + 1), key="too-large")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MEDIA_LIMIT_EXCEEDED"


def test_missing_idempotency_key_is_rejected(tmp_path, png_bytes):
    client = make_client(tmp_path, FakeProvider())
    response = client.post("/api/v1/media", files={"file": ("x.png", png_bytes, "image/png")})
    assert response.status_code == 422


def test_built_react_is_served_same_origin(tmp_path):
    static_root = __import__("pathlib").Path(__file__).resolve().parents[1] / "frontend" / "dist"
    app = create_app(Settings.local(data_root=tmp_path, static_root=static_root), provider=FakeProvider())
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "LVW 本地图像提示词工作台" in response.text
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
