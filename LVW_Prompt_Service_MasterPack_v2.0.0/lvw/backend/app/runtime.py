from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Awaitable, Callable

from .errors import AppError


class OllamaRuntime:
    PROTOCOL_VERSION = "lvw.runtime/1"

    def __init__(self, provider, executable: Path | None, data_root: Path,
                 spawn: Callable[[], Awaitable[asyncio.subprocess.Process]] | None = None):
        self.provider = provider
        self.executable = executable
        self.data_root = data_root
        self.process: asyncio.subprocess.Process | None = None
        self.last_error: str | None = None
        self._lock = asyncio.Lock()
        self._spawn_override = spawn
        self._log = None
        self._native = None

    def _validate_executable(self) -> Path:
        executable = self.executable
        if executable is None or not executable.is_absolute() or executable.name.lower() != "ollama.exe":
            raise AppError("RUNTIME_NOT_CONFIGURED", "Ollama executable is not configured",
                           status_code=503)
        if not executable.is_file() or executable.is_symlink():
            raise AppError("RUNTIME_NOT_CONFIGURED", "Configured Ollama executable is unavailable",
                           status_code=503)
        return executable

    def _owned(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def status(self) -> dict:
        readiness = await self.provider.readiness()
        owned = self._owned()
        from .native_runtime import proof
        native = proof(self._native)
        unresolved = bool(self._native) and native.get("state") != "exited" and not owned
        native_ready = not self._native or native.get("listener_owned") is True
        if unresolved:
            state = "error"
        elif readiness["ready"]:
            state = "ready" if owned and native_ready else "starting" if owned else "external"
        elif owned:
            state = "starting"
        elif readiness["reason"] != "OLLAMA_UNAVAILABLE":
            state = "external"
        elif self.last_error:
            state = "error"
        else:
            state = "stopped"
        return {
            "protocol": self.PROTOCOL_VERSION,
            "lvw": {"state": "ready"},
            "ollama": {
                "state": state,
                "reachable": readiness["reason"] != "OLLAMA_UNAVAILABLE",
                "model": readiness["model"],
                "model_ready": readiness["ready"],
                "model_loaded": readiness.get("loaded", False),
                "managed": owned,
                "pid": native.get("pid", self.process.pid) if owned else None,
                "reason": readiness["reason"],
                "last_error": "RESOURCE_RELEASE_PENDING" if unresolved else self.last_error,
            },
            "actions": {
                "can_start": readiness["reason"] == "OLLAMA_UNAVAILABLE" and not owned and not unresolved,
                "can_reset": owned,
                "can_stop": owned,
            },
        }

    async def _spawn(self) -> asyncio.subprocess.Process:
        if self._spawn_override:
            return await self._spawn_override()
        executable = self._validate_executable()
        log_root = self.data_root / "runtime"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / "ollama.log"
        self._log = open(log_path, "ab", buffering=0)
        os.chmod(log_path, 0o600)
        env = os.environ.copy()
        env.update({"OLLAMA_HOST": "http://127.0.0.1:11434", "OLLAMA_NO_CLOUD": "true",
                    "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
        # A Win32 executable does not inherit arbitrary Linux env values.
        # /w forwards these process-local values from WSL to Windows; no registry/config writes.
        forwarded = {"OLLAMA_HOST", "OLLAMA_NO_CLOUD", "NO_PROXY"}
        entries = [value for value in env.get("WSLENV", "").split(":")
                   if value and value.split("/", 1)[0].upper() not in forwarded]
        env["WSLENV"] = ":".join(entries + [name + "/w" for name in sorted(forwarded)])
        from .native_runtime import prepare
        self._native = prepare(log_root, executable)
        return await asyncio.create_subprocess_exec(*self._native["argv"], stdin=asyncio.subprocess.DEVNULL,
            stdout=self._log, stderr=asyncio.subprocess.STDOUT, env=env)


    async def start(self) -> dict:
        async with self._lock:
            current = await self.status()
            if self._native and not self._owned():
                await self._stop_owned()
            if current["ollama"]["model_ready"]:
                return current
            if self._owned():
                raise AppError("RUNTIME_STARTING", "Ollama is already starting", status_code=409,
                               retryable=True)
            if current["ollama"]["reachable"]:
                raise AppError("RUNTIME_NOT_OWNED", "An external Ollama already owns the port",
                               status_code=409, details={"reason": current["ollama"]["reason"]})
            self._validate_executable()
            self.last_error = None
            self.process = await self._spawn()
            for _ in range(60):
                if self.process.returncode is not None:
                    self.last_error = f"OLLAMA_EXITED_{self.process.returncode}"
                    await self._stop_owned()
                    raise AppError("RUNTIME_START_FAILED", "Ollama exited during startup",
                                   status_code=503, details={"reason": self.last_error})
                readiness = await self.provider.readiness()
                from .native_runtime import proof
                if readiness["ready"] and (not self._native or proof(self._native).get("listener_owned") is True):
                    return await self.status()
                await asyncio.sleep(0.5)
            self.last_error = "OLLAMA_START_TIMEOUT"
            await self._stop_owned()
            raise AppError("RUNTIME_START_FAILED", "Ollama startup timed out", status_code=503,
                           details={"reason": self.last_error})

    async def _stop_owned(self) -> None:
        process = self.process
        if self._native:
            self._native["stop"].write_text(self._native["nonce"])
            try:
                if process is not None:
                    await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError as error:
                raise AppError("RESOURCE_RELEASE_PENDING", "本轮Windows模型进程退出未确认", status_code=503) from error
            from .native_runtime import proof
            if proof(self._native).get("state") != "exited":
                raise AppError("RESOURCE_RELEASE_PENDING", "本轮Windows原进程终态证明缺失", status_code=503)
            self._native = None
        elif process is not None and process.returncode is None:
            process.terminate()
        if process is None:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
        self.process = None
        if self._log:
            self._log.close()
            self._log = None

    async def stop(self) -> dict:
        async with self._lock:
            if not self._owned() and not self._native:
                readiness = await self.provider.readiness()
                if readiness["ready"]:
                    raise AppError("RUNTIME_NOT_OWNED", "Ollama was not started by LVW",
                                   status_code=409)
                return await self.status()
            await self._stop_owned()
            self.last_error = None
            for _ in range(20):
                readiness = await self.provider.readiness()
                if readiness["reason"] == "OLLAMA_UNAVAILABLE":
                    break
                await asyncio.sleep(0.25)
            return await self.status()

    async def reset(self) -> dict:
        async with self._lock:
            if not self._owned():
                raise AppError("RUNTIME_NOT_OWNED", "Only an LVW-managed Ollama can be reset",
                               status_code=409)
            await self._stop_owned()
            self.last_error = None
        return await self.start()

    async def close(self) -> None:
        async with self._lock:
            await self._stop_owned()
