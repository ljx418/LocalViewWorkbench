from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import resource_cleanup as owner
from app.config import Settings
from app.errors import AppError
from app.main import create_app
from app.runtime import OllamaRuntime


def model_row(name="gemma4:26b", **changes):
    return {"name": name, "model": name, "digest": "a" * 64, "size_vram": 400 * 1048576, **changes}


class Provider:
    model = "gemma4:26b"
    def __init__(self):
        self.rows = [model_row()]
        self._lease = None
        self.online = True
        self.calls = []
    async def readiness(self):
        return dict(ready=self.online, model=self.model,
                    reason=None if self.online else "OLLAMA_UNAVAILABLE", loaded=bool(self.rows) if self.online else False)
    async def _inventory(self):
        if not self.online: raise httpx.ConnectError("offline")
        return self.rows
    async def release(self, _):
        raise AssertionError("Cleanup must not call unbound HTTP lease release")


class NativeProcess:
    pid = 321
    returncode = None
    def __init__(self, native, provider):
        self.native, self.provider = native, provider
        self.write_exit = True
        self.stop_calls = 0
    async def wait(self):
        self.stop_calls += 1
        assert self.native["stop"].read_text() == self.native["nonce"]
        self.returncode = 0
        if self.write_exit:
            self.native["owner"].write_text(json.dumps(dict(nonce=self.native["nonce"], pid=987,
                birth_ticks=12345, state="exited", listener_owned=False)))
        self.provider.online = False
        self.provider.rows = []
        return 0


@pytest.fixture
def setup(tmp_path, monkeypatch):
    async def snapshot():
        return dict(gpu_used_mib=400, gpu_free_mib=24000, gpu_total_mib=24400, available_ram_mib=8000)
    monkeypatch.setattr(owner.resources, "snapshot", snapshot)
    provider = Provider()
    runtime = OllamaRuntime(provider, None, tmp_path)
    native = dict(nonce="fixture_nonce", owner=tmp_path / "owner.json", stop=tmp_path / "stop")
    native["owner"].write_text(json.dumps(dict(nonce=native["nonce"], pid=987, birth_ticks=12345,
                                                state="listening", listener_owned=True)))
    runtime._native = native
    runtime.process = NativeProcess(native, provider)
    app = create_app(Settings(data_root=tmp_path), provider=provider, runtime=runtime)
    return provider, runtime, app, TestClient(app)


def post(client, **kwargs):
    return client.post("/api/v1/runtime/resources/cleanup", headers={"X-LVW-Control": "local-ui"}, **kwargs)


def test_public_cleanup_stops_only_original_handle_and_preserves_history(setup):
    provider, runtime, app, client = setup
    original = runtime.process
    app.state.analysis.runs["keep"] = "manual history sentinel"
    result = post(client).json()["data"]
    assert result["status"] == "released" and result["verified"]
    assert result["actions"] == ["stop_original_lvw_model_service"]
    assert result["before"]["values"]["gpu_used_mib"] == 400
    assert result["after"]["values"]["available_ram_mib"] == 8000
    assert result["runtime"]["ollama"]["state"] == "stopped"
    assert result["runtime_error"] is None and original.stop_calls == 2
    assert app.state.analysis.runs["keep"] == "manual history sentinel"
    assert post(client).json()["data"]["status"] == "noop"
    assert original.stop_calls == 2 and not provider.calls


@pytest.mark.parametrize("rows", [None, {}, [None], [{}], [{"name": ""}],
    [model_row(name=" ")], [model_row(model="foreign")], [model_row(digest="?")],
    [model_row(size_vram=-1)], [model_row(size_vram=True)], [model_row(), model_row()]])
def test_ambiguous_inventory_never_mutates(setup, rows):
    provider, runtime, _, client = setup
    original = runtime.process
    provider.rows = rows
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and not result["verified"]
    assert original.stop_calls == 0 and runtime._cleanup_pending is None


@pytest.mark.parametrize("retained_lease", [False, True])
def test_external_service_including_same_model_retained_lease_not_touched(setup, retained_lease):
    provider, runtime, _, client = setup
    runtime.process = None
    runtime._native = None
    if retained_lease: provider._lease = ("old_job", {"gpu_used_mib": 400})
    result = post(client).json()["data"]
    assert result["status"] == "blocked" and result["reason"] == "RUNTIME_NOT_OWNED"
    assert (provider._lease is not None) is retained_lease


@pytest.mark.parametrize("only_foreign", [False, True])
def test_foreign_models_prevent_stop(setup, only_foreign):
    provider, runtime, _, client = setup
    provider.rows = [model_row("foreign")] + ([] if only_foreign else [model_row()])
    result = post(client).json()["data"]
    assert result["status"] == "blocked" and runtime.process.stop_calls == 0


def test_missing_custody_does_not_authorize_stop(setup):
    _, runtime, _, client = setup
    runtime._native["owner"].unlink()
    assert post(client).json()["data"]["reason"] == "NATIVE_CUSTODY_UNPROVEN"
    assert runtime.process.stop_calls == 0


def test_retained_lease_reconciled_only_after_final_observations(setup):
    provider, runtime, _, client = setup
    provider._lease = ("owned_job", {"gpu_used_mib": 400})
    original_status = runtime.status
    async def fail(): raise httpx.ConnectError("status failure")
    runtime.status = fail
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and provider._lease is not None
    assert runtime._cleanup_pending is not None and result["runtime_error"]
    runtime.status = original_status
    assert post(client).json()["data"]["status"] == "released"
    assert provider._lease is None and runtime._cleanup_pending is None


def test_replacement_listener_never_unloaded_and_lease_retained(setup):
    provider, runtime, _, client = setup
    provider._lease = ("owned_job", {"gpu_used_mib": 400})
    original_wait = runtime.process.wait
    async def replace():
        value = await original_wait()
        provider.online = True
        provider.rows = [model_row()]
        return value
    runtime.process.wait = replace
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and not result["verified"]
    assert provider.online and provider.rows and provider._lease is not None
    assert runtime._cleanup_pending is not None and not provider.calls


def test_stale_listener_positive_never_authorizes_any_http_mutation(setup):
    provider, runtime, _, client = setup
    # The only permitted mutation uses the nonce held by the original native process.
    runtime._native["owner"].write_text(json.dumps(dict(nonce="fixture_nonce", pid=987,
        birth_ticks=12345, state="listening", listener_owned=True)))
    assert post(client).json()["data"]["status"] == "released"
    assert not provider.calls


def test_unproven_native_exit_retains_recovery_record(setup):
    provider, runtime, _, client = setup
    process = runtime.process
    process.write_exit = False
    provider._lease = ("owned_job", {"gpu_used_mib": 400})
    assert post(client).json()["data"]["status"] == "unknown"
    assert runtime._native is not None and provider._lease is not None
    process.write_exit = True
    assert post(client).json()["data"]["status"] == "released"


@pytest.mark.parametrize("busy", ["active", "queued", "controller"])
def test_busy_api_never_mutates(setup, busy):
    _, runtime, app, client = setup
    service = app.state.analysis
    if busy == "active": service._active = "active-job"
    if busy == "queued": service.jobs["queued"] = SimpleNamespace(status="queued")
    if busy == "controller": service._controller_busy = True
    response = post(client)
    assert response.status_code == 409 and response.json()["error"]["code"] == "RESOURCE_BUSY"
    assert runtime.process.stop_calls == 0


def test_concurrent_cleanup_rejected_and_lock_recovers(setup):
    provider, runtime, app, _ = setup
    async def scenario():
        entered, resume = asyncio.Event(), asyncio.Event()
        async def inventory():
            entered.set(); await resume.wait(); return []
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
    _, runtime, _, client = setup
    url = "/api/v1/runtime/resources/cleanup"
    assert client.post(url).status_code == 403
    assert client.post(url, headers={"Origin": "http://evil.example", "X-LVW-Control": "local-ui"}).status_code == 403
    assert post(client, json={"pid": 1}).status_code == 422
    assert client.post(url + "?path=/etc", headers={"X-LVW-Control": "local-ui"}).status_code == 422
    assert runtime.process.stop_calls == 0


def test_production_peer_and_host_negative_case(setup):
    _, runtime, app, _ = setup
    async def scenario():
        for peer, host in [("127.0.0.1", "evil.example"), ("192.0.2.1", "127.0.0.1")]:
            transport = httpx.ASGITransport(app=app, client=(peer, 1234))
            async with httpx.AsyncClient(transport=transport, base_url="http://" + host) as client:
                result = await client.post("/api/v1/runtime/resources/cleanup", headers={"X-LVW-Control": "local-ui"})
                assert result.status_code == 403 and result.json()["error"]["code"] == "ORIGIN_FORBIDDEN"
    asyncio.run(scenario())
    assert runtime.process.stop_calls == 0


def test_telemetry_failure_never_stops_service_or_fabricates_values(setup, monkeypatch):
    _, runtime, _, client = setup
    async def fail(): raise AppError("RESOURCE_BUSY", "unavailable", status_code=503)
    monkeypatch.setattr(owner.resources, "snapshot", fail)
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and not result["verified"]
    assert result["before"] == result["after"] == {"values": None, "error": "RESOURCE_TELEMETRY_UNAVAILABLE"}
    assert runtime.process.stop_calls == 0


def test_resource_failure_after_stop_does_not_clear_lease(setup, monkeypatch):
    provider, runtime, _, client = setup
    provider._lease = ("owned_job", {"gpu_used_mib": 0})
    call = 0
    async def snapshot():
        nonlocal call
        call += 1
        return dict(gpu_used_mib=400 if call == 1 else 9000, gpu_free_mib=10000,
                    gpu_total_mib=24400, available_ram_mib=8000)
    monkeypatch.setattr(owner.resources, "snapshot", snapshot)
    result = post(client).json()["data"]
    assert result["status"] == "unknown" and provider._lease is not None
    assert runtime._cleanup_pending is not None and runtime.process is None


def test_deadline_covers_lock_wait_and_reports_missing_observations(setup, monkeypatch):
    _, runtime, app, _ = setup
    original_timeout = asyncio.timeout
    monkeypatch.setattr(owner.asyncio, "timeout", lambda _: original_timeout(0.03))
    async def scenario():
        await runtime._lock.acquire()
        try:
            result = await app.state.analysis.runtime_control(runtime.cleanup_resources, release_remaining=False)
            assert result["status"] == "unknown" and result["reason"] == "RESOURCE_CLEANUP_TIMEOUT"
            assert result["before"]["error"] == result["after"]["error"] == result["runtime_error"]
            assert not app.state.analysis._controller_busy
        finally: runtime._lock.release()
    asyncio.run(scenario())


def test_new_start_refused_while_cleanup_unresolved(setup):
    _, runtime, _, _ = setup
    runtime._cleanup_pending = {"pending": True}
    with pytest.raises(AppError) as error: asyncio.run(runtime.start())
    assert error.value.code == "RESOURCE_RELEASE_PENDING"
