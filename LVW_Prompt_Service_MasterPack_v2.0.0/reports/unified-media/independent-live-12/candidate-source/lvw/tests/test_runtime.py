from __future__ import annotations

import asyncio

import pytest

from app.errors import AppError
from app.runtime import OllamaRuntime


class Provider:
    model = "gemma4:26b"

    def __init__(self, ready=False, reason="OLLAMA_UNAVAILABLE"):
        self.ready = ready
        self.reason = reason

    async def readiness(self):
        return {"ready": self.ready, "model": self.model,
                "reason": None if self.ready else self.reason, "loaded": False}


class Process:
    pid = 321

    def __init__(self, provider):
        self.provider = provider
        self.returncode = None

    def terminate(self):
        self.returncode = 0
        self.provider.ready = False

    def kill(self):
        self.terminate()

    async def wait(self):
        return self.returncode


def configured_runtime(tmp_path, provider):
    executable = tmp_path / "ollama.exe"
    executable.write_bytes(b"fixture")

    async def spawn():
        provider.ready = True
        return Process(provider)

    return OllamaRuntime(provider, executable, tmp_path, spawn=spawn)


def test_managed_runtime_start_status_and_stop(tmp_path):
    provider = Provider()
    runtime = configured_runtime(tmp_path, provider)
    started = asyncio.run(runtime.start())
    assert started["protocol"] == "lvw.runtime/1"
    assert started["ollama"]["state"] == "ready"
    assert started["ollama"]["managed"] is True
    assert started["actions"] == {"can_start": False, "can_reset": True, "can_stop": True}
    stopped = asyncio.run(runtime.stop())
    assert stopped["ollama"]["state"] == "stopped"
    assert stopped["ollama"]["managed"] is False


def test_external_runtime_cannot_be_reset_or_stopped(tmp_path):
    runtime = configured_runtime(tmp_path, Provider(ready=True))
    assert asyncio.run(runtime.status())["ollama"]["state"] == "external"
    with pytest.raises(AppError, match="not started by LVW") as stopped:
        asyncio.run(runtime.stop())
    assert stopped.value.code == "RUNTIME_NOT_OWNED"
    with pytest.raises(AppError, match="LVW-managed") as reset:
        asyncio.run(runtime.reset())
    assert reset.value.code == "RUNTIME_NOT_OWNED"


def test_reachable_external_runtime_with_missing_model_cannot_be_started(tmp_path):
    runtime = configured_runtime(tmp_path, Provider(reason="MODEL_NOT_INSTALLED"))
    status = asyncio.run(runtime.status())
    assert status["ollama"]["state"] == "external"
    assert status["actions"]["can_start"] is False
    with pytest.raises(AppError, match="external Ollama") as started:
        asyncio.run(runtime.start())
    assert started.value.code == "RUNTIME_NOT_OWNED"


def test_runtime_rejects_unconfigured_or_wrong_executable(tmp_path):
    for executable in (None, tmp_path / "other.exe", tmp_path / "ollama.exe"):
        runtime = OllamaRuntime(Provider(), executable, tmp_path)
        with pytest.raises(AppError) as raised:
            asyncio.run(runtime.start())
        assert raised.value.code == "RUNTIME_NOT_CONFIGURED"


def test_dead_wrapper_never_clears_unproven_native_process(tmp_path):
    import json
    provider = Provider()
    runtime = configured_runtime(tmp_path, provider)
    process = Process(provider)
    process.returncode = 1
    runtime.process = process
    owner = tmp_path / "owner.json"
    owner.write_text(json.dumps({"nonce":"n", "pid":123, "birth_ticks":456,
                                 "state":"starting", "listener_owned":False}))
    runtime._native = {"nonce":"n", "owner":owner, "stop":tmp_path / "stop"}
    assert asyncio.run(runtime.status())["actions"]["can_start"] is False
    for action in (runtime.close, runtime.start, runtime.stop):
        with pytest.raises(AppError) as raised:
            asyncio.run(action())
        assert raised.value.code == "RESOURCE_RELEASE_PENDING"
        assert runtime.process is process and runtime._native is not None
    owner.write_text(json.dumps({"nonce":"n", "pid":123, "birth_ticks":456,
                                 "state":"exited", "listener_owned":False}))
    asyncio.run(runtime.close())
    assert runtime.process is None and runtime._native is None
