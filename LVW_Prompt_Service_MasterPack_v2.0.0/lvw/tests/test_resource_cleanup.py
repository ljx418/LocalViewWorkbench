from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import resource_cleanup as owner
from app.config import Settings
from app.errors import AppError
from app.main import create_app
from app.provider import OllamaProvider
from app.runtime import OllamaRuntime


class Provider:
    model = "gemma4:26b"

    def __init__(self):
        self.rows = [{"name": self.model}]
        self._lease = None
        self.calls = []
        self.release_ok = True

    async def readiness(self):
        return dict(ready=True, model=self.model, reason=None, loaded=bool(self.rows))

    async def _inventory(self):
        return self.rows

    async def unload_idle_model(self):
        self.calls.append("unload")
        self.rows = []

    async def release(self, job):
        self.calls.append(("release", job))
        if self.release_ok:
            self._lease = None
            self.rows = []
        return self.release_ok


@pytest.fixture
def setup(tmp_path, monkeypatch):
    async def snapshot():
        return dict(gpu_used_mib=400, gpu_free_mib=24000, gpu_total_mib=24400, available_ram_mib=8000)
    monkeypatch.setattr(owner.resources, "snapshot", snapshot)
    monkeypatch.setattr("app.native_runtime.proof", lambda _: {"listener_owned": True})
    provider = Provider()
    runtime = OllamaRuntime(provider, None, tmp_path)
    runtime.process = SimpleNamespace(returncode=None, pid=123)
    runtime._native = {"test": True}
    app = create_app(Settings(data_root=tmp_path), provider=provider, runtime=runtime)
    client = TestClient(app)
    return provider, runtime, app, client


def post(client, **kwargs):
    return client.post("/api/v1/runtime/resources/cleanup", headers={"X-LVW-Control": "local-ui"}, **kwargs)


def test_public_cleanup_uses_owner_and_confirms_absence(setup):
    provider, _, app, client = setup
    app.state.analysis.runs["keep"] = "manual history sentinel"
    response = post(client)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "released" and result["verified"] is True
    assert result["actions"] == ["unload_configured_model"]
    assert result["before"]["values"]["gpu_used_mib"] == 400
    assert result["after"]["values"]["available_ram_mib"] == 8000
    assert provider.calls == ["unload"]
    assert app.state.analysis.runs["keep"] == "manual history sentinel"
    assert post(client).json()["data"]["status"] == "noop"
    assert provider.calls == ["unload"]


@pytest.mark.parametrize("rows", [None, {}, [None], [{}], [{"name": ""}], [{"name": "x", "model": 1}]])
def test_invalid_inventory_never_claims_success(setup, rows):
    provider, _, _, client = setup
    provider.rows = rows
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and result["verified"] is False
    assert not provider.calls


@pytest.mark.parametrize("external", [True, False])
def test_external_service_or_other_model_left_untouched(setup, external):
    provider, runtime, _, client = setup
    if external:
        runtime.process = None
    else:
        provider.rows.append({"name": "other-model:latest"})
    assert post(client).json()["data"]["status"] == "blocked"
    assert not provider.calls


def test_no_native_custody_is_not_ownership(setup):
    provider, runtime, _, client = setup
    runtime._native = None
    assert post(client).json()["data"]["reason"] == "RUNTIME_NOT_OWNED"
    assert not provider.calls


@pytest.mark.parametrize("success", [True, False])
def test_lease_release_truth_is_preserved_without_second_release(setup, success):
    provider, _, _, client = setup
    provider._lease = ("job_owned", {})
    provider.release_ok = success
    result = post(client).json()["data"]
    assert result["status"] == ("released" if success else "unknown")
    assert provider.calls == [("release", "job_owned")]
    assert (provider._lease is None) is success


@pytest.mark.parametrize("busy", ["active", "queued", "controller"])
def test_busy_api_never_mutates(setup, busy):
    provider, _, app, client = setup
    service = app.state.analysis
    if busy == "active": service._active = "active-job"
    if busy == "queued": service.jobs["queued"] = SimpleNamespace(status="queued")
    if busy == "controller": service._controller_busy = True
    response = post(client)
    assert response.status_code == 409 and response.json()["error"]["code"] == "RESOURCE_BUSY"
    assert not provider.calls


def test_concurrent_cleanup_rejected_and_lock_recovers(setup):
    provider, runtime, app, _ = setup
    async def scenario():
        entered, resume = asyncio.Event(), asyncio.Event()
        async def inventory():
            entered.set()
            await resume.wait()
            return []
        provider._inventory = inventory
        service = app.state.analysis
        task = asyncio.create_task(service.runtime_control(runtime.cleanup_resources, release_remaining=False))
        await entered.wait()
        with pytest.raises(AppError) as error:
            await service.runtime_control(runtime.cleanup_resources, release_remaining=False)
        assert error.value.code == "RESOURCE_BUSY"
        resume.set()
        assert (await task)["status"] == "noop"
        assert not service._controller_busy
    asyncio.run(scenario())


def test_control_header_origin_and_parameter_rejection(setup):
    provider, _, _, client = setup
    url = "/api/v1/runtime/resources/cleanup"
    assert client.post(url).status_code == 403
    assert client.post(url, headers={"Origin": "http://evil.example", "X-LVW-Control": "local-ui"}).status_code == 403
    assert post(client, json={"pid": 1}).status_code == 422
    assert client.post(url + "?path=/etc", headers={"X-LVW-Control": "local-ui"}).status_code == 422
    assert not provider.calls


def test_transport_failure_unknown_then_retry(setup):
    provider, _, app, client = setup
    original = provider.unload_idle_model
    async def fail(): raise httpx.ConnectError("fixture")
    provider.unload_idle_model = fail
    assert post(client).json()["data"]["status"] == "unknown"
    assert not app.state.analysis._controller_busy
    provider.unload_idle_model = original
    assert post(client).json()["data"]["status"] == "released"


def test_unload_ack_is_not_proof(setup, monkeypatch):
    provider, _, _, client = setup
    async def no_effect(): provider.calls.append("ack-only")
    async def no_sleep(_): pass
    provider.unload_idle_model = no_effect
    monkeypatch.setattr(owner.asyncio, "sleep", no_sleep)
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and not result["verified"]


def test_telemetry_failure_not_fabricated(setup, monkeypatch):
    _, _, _, client = setup
    async def fail(): raise AppError("RESOURCE_BUSY", "unavailable", status_code=503)
    monkeypatch.setattr(owner.resources, "snapshot", fail)
    result = post(client).json()["data"]
    assert result["status"] == "released" and result["verified"]
    assert result["before"] == result["after"] == {"values": None, "error": "RESOURCE_TELEMETRY_UNAVAILABLE"}


def test_deadline_leaves_lease_intact(setup, monkeypatch):
    provider, _, _, client = setup
    provider._lease = ("job_owned", {})
    original_timeout = asyncio.timeout
    monkeypatch.setattr(owner.asyncio, "timeout", lambda _: original_timeout(0.02))
    async def slow(_): await asyncio.sleep(1)
    provider.release = slow
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and provider._lease is not None


def test_real_provider_unload_wire_contract(monkeypatch):
    calls = []
    def handler(request):
        calls.append((str(request.url), request.read()))
        return httpx.Response(200, json={"done": True})
    actual = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: actual(transport=httpx.MockTransport(handler), **kw))
    asyncio.run(OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 10).unload_idle_model())
    import json
    assert calls[0][0] == "http://127.0.0.1:11434/api/generate"
    assert json.loads(calls[0][1]) == {"model": "gemma4:26b", "keep_alive": 0}
