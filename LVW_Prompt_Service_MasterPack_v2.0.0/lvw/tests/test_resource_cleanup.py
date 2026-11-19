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
    async def listener_state(self):
        return {"state": "responding" if self.online else "absent", "reason": "fixture"}
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
    [{k: v for k, v in model_row().items() if k != "model"}], [model_row(size_vram=-1)], [model_row(size_vram=True)], [model_row(), model_row()]])
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
    provider._lease_generation = runtime.current_generation()
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
    provider._lease_generation = runtime.current_generation()
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
    provider._lease_generation = runtime.current_generation()
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
        assert (await task)["status"] == "released"
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
    assert result["before"] == {"values": None, "error": "RESOURCE_TELEMETRY_UNAVAILABLE"}
    assert result["after"] == {"values": None, "error": "SKIPPED_AFTER_RESOURCE_TELEMETRY_UNAVAILABLE"}
    assert runtime.process.stop_calls == 0


def test_resource_failure_after_stop_does_not_clear_lease(setup, monkeypatch):
    provider, runtime, _, client = setup
    provider._lease = ("owned_job", {"gpu_used_mib": 0})
    provider._lease_generation = runtime.current_generation()
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
            assert result["before"]["error"] == "RESOURCE_CLEANUP_TIMEOUT"
            assert result["after"]["error"] == result["runtime_error"] == "SKIPPED_AFTER_RESOURCE_CLEANUP_TIMEOUT"
            assert not app.state.analysis._controller_busy
        finally: runtime._lock.release()
    asyncio.run(scenario())


def test_new_start_refused_while_cleanup_unresolved(setup):
    _, runtime, _, _ = setup
    runtime._cleanup_pending = {"pending": True}
    with pytest.raises(AppError) as error: asyncio.run(runtime.start())
    assert error.value.code == "RESOURCE_RELEASE_PENDING"


@pytest.mark.parametrize('generation', [None, {'nonce': 'old', 'pid': 987, 'birth_ticks': 1}])
def test_unbound_or_previous_generation_lease_cannot_stop_current_daemon(setup, generation):
    provider, runtime, _, client = setup
    lease = ('older_job', {'gpu_used_mib': 400})
    provider._lease = lease
    provider._lease_generation = generation
    result = post(client).json()['data']
    assert result['status'] == 'blocked' and result['reason'] == 'LEASE_GENERATION_UNBOUND'
    assert provider._lease is lease and runtime.process.stop_calls == 0


def test_empty_external_service_is_blocked_not_verified_noop(setup):
    provider, runtime, _, client = setup
    provider.rows = []
    runtime.process = None
    runtime._native = None
    result = post(client).json()['data']
    assert result['status'] == 'blocked' and not result['verified']
    assert result['reason'] == 'RUNTIME_NOT_OWNED'


@pytest.mark.parametrize('observation', ['responding', 'indeterminate'])
def test_protocol_unavailable_does_not_prove_listener_absent(setup, observation):
    provider, runtime, _, client = setup
    provider._lease = ('owned_job', {'gpu_used_mib': 400})
    provider._lease_generation = runtime.current_generation()
    async def state(): return {'state': observation, 'reason': 'HTTP error or timeout fixture'}
    provider.listener_state = state
    result = post(client).json()['data']
    # readiness says unavailable after native exit, but the dedicated observer contradicts it.
    assert result['runtime']['ollama']['reachable'] is False
    assert result['status'] == 'unknown' and not result['verified']
    assert provider._lease is not None and runtime._cleanup_pending is not None
    assert result['listener_observation']['state'] == observation


@pytest.mark.parametrize('failure', ['refused', 'timeout', 'connected'])
def test_production_listener_observer_distinguishes_errors(monkeypatch, failure):
    from app.provider import OllamaProvider
    calls = []
    class Writer:
        closed = False
        def close(self): self.closed = True
        async def wait_closed(self): pass
    writer = Writer()
    async def connect(host, port):
        calls.append((host, port))
        if failure == 'refused': raise ConnectionRefusedError()
        if failure == 'timeout': raise TimeoutError()
        return object(), writer
    monkeypatch.setattr(asyncio, 'open_connection', connect)
    provider = OllamaProvider('http://127.0.0.1:11434/api/chat', 'gemma4:26b', 5)
    result = asyncio.run(provider.listener_state())
    assert result['state'] == {'refused': 'absent', 'timeout': 'indeterminate', 'connected': 'responding'}[failure]
    assert calls == [('127.0.0.1', 11434)]
    if failure == 'connected': assert writer.closed


def test_http500_on_real_provider_readiness_still_counts_as_listener(setup, monkeypatch):
    from app.provider import OllamaProvider
    provider, runtime, _, client = setup
    provider._lease = ('owned_job', {'gpu_used_mib': 400})
    provider._lease_generation = runtime.current_generation()
    actual = OllamaProvider('http://127.0.0.1:11434/api/chat', 'gemma4:26b', 5)
    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: client_type(transport=httpx.MockTransport(lambda _: httpx.Response(500)), **kw))
    class Writer:
        def close(self): pass
        async def wait_closed(self): pass
    async def connect(*_): return object(), Writer()
    monkeypatch.setattr(asyncio, 'open_connection', connect)
    provider.readiness = actual.readiness
    provider.listener_state = actual.listener_state
    result = post(client).json()['data']
    assert result['status'] == 'unknown' and result['reason'] == 'REPLACEMENT_LISTENER_PRESENT'
    assert runtime._cleanup_pending is not None and provider._lease is not None


def test_pending_without_lease_blocks_public_job_and_readiness(setup, png_bytes):
    provider, runtime, app, client = setup
    runtime._cleanup_pending = {'unresolved': True}
    media = client.post('/api/v1/media', headers={'Idempotency-Key': 'pending-upload'},
                        files={'file': ('sample.png', png_bytes, 'image/png')}).json()['data']
    result = client.post('/api/v1/jobs/analyze', headers={'Idempotency-Key': 'pending-analysis'},
        json={'media_ref_id': media['id'], 'shot_id': None, 'mode': 'realistic', 'config_profile': 'local-default'})
    assert result.status_code == 409 and result.json()['error']['code'] == 'RESOURCE_RELEASE_PENDING'
    assert not app.state.analysis.jobs and provider._lease is None
    status = client.get('/api/v1/runtime/status').json()['data']
    assert not any(status['actions'].values()) and not status['ollama']['model_ready']
    assert not client.get('/api/v1/readiness').json()['data']['ready']


def test_retained_lease_blocks_every_lifecycle_before_operation(setup):
    provider, runtime, app, _ = setup
    provider._lease = ('old_job', {'gpu_used_mib': 400})
    invoked = []
    async def operation(): invoked.append('called')
    async def scenario():
        with pytest.raises(AppError) as error: await app.state.analysis.runtime_control(operation)
        assert error.value.code == 'RESOURCE_RELEASE_PENDING'
        for action in [runtime.start, runtime.reset, runtime.stop]:
            with pytest.raises(AppError) as error: await action()
            assert error.value.code == 'RESOURCE_RELEASE_PENDING'
    asyncio.run(scenario())
    assert not invoked and runtime.process.stop_calls == 0 and provider._lease is not None


def test_real_provider_acquisition_seals_generation(setup):
    from app.provider import OllamaProvider
    _, runtime, _, _ = setup
    provider = OllamaProvider('http://127.0.0.1:11434/api/chat', 'gemma4:26b', 5)
    async def empty(): return []
    provider._inventory = empty
    provider._generation_getter = runtime.current_generation
    expected = runtime.current_generation()
    asyncio.run(provider.acquire('acquired_job'))
    assert provider._lease_generation == expected and provider._lease[0] == 'acquired_job'


def test_non_object_native_owner_proof_is_unknown(setup):
    from app.native_runtime import proof
    _, runtime, _, _ = setup
    runtime._native['owner'].write_text('[]')
    assert proof(runtime._native) == {}


def test_already_queued_job_does_not_acquire_after_pending_cleanup(setup, png_bytes):
    from app.models import AnalyzeRequest
    provider, runtime, app, client = setup
    media = client.post('/api/v1/media', headers={'Idempotency-Key': 'queued-upload'},
        files={'file': ('sample.png', png_bytes, 'image/png')}).json()['data']
    request = AnalyzeRequest(media_ref_id=media['id'], shot_id=None, mode='realistic', config_profile='local-default')
    job = app.state.analysis.submit(request, 'queued-analysis')
    runtime._cleanup_pending = {'unresolved': True}
    asyncio.run(app.state.analysis.run(job.id, request))
    terminal = app.state.analysis.get_job(job.id)
    assert terminal.status == 'failed' and terminal.error_code == 'RESOURCE_RELEASE_PENDING'
    assert terminal.result_ref is None and provider._lease is None and not app.state.analysis.runs


@pytest.mark.parametrize('after_used,accepted', [(1024, True), (1025, False)])
def test_release_resource_bound_exact_and_one_over(setup, monkeypatch, after_used, accepted):
    provider, runtime, _, client = setup
    provider._lease = ('owned_job', {'gpu_used_mib': 0})
    provider._lease_generation = runtime.current_generation()
    count = 0
    async def snapshot():
        nonlocal count
        count += 1
        used = 400 if count == 1 else after_used
        return dict(gpu_used_mib=used, gpu_free_mib=24400-used, gpu_total_mib=24400, available_ram_mib=8000)
    monkeypatch.setattr(owner.resources, 'snapshot', snapshot)
    result = post(client).json()['data']
    assert result['verified'] is accepted
    assert result['status'] == ('released' if accepted else 'unknown')
    assert (provider._lease is None) is accepted
    assert (runtime._cleanup_pending is None) is accepted
