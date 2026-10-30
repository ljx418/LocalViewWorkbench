from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Awaitable, Callable

from .errors import AppError


class OllamaRuntime:
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
        if readiness["ready"]:
            state = "ready" if owned else "external"
        elif owned:
            state = "starting"
        elif readiness["reason"] != "OLLAMA_UNAVAILABLE":
            state = "external"
        elif self.last_error:
            state = "error"
        else:
            state = "stopped"
        return {
            "lvw": {"state": "ready"},
            "ollama": {
                "state": state,
                "reachable": readiness["reason"] != "OLLAMA_UNAVAILABLE",
                "model": readiness["model"],
                "model_ready": readiness["ready"],
                "model_loaded": readiness.get("loaded", False),
                "managed": owned,
                "pid": self.process.pid if owned else None,
                "reason": readiness["reason"],
                "last_error": self.last_error,
            },
            "actions": {
                "can_start": readiness["reason"] == "OLLAMA_UNAVAILABLE" and not owned,
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
        return await asyncio.create_subprocess_exec(str(executable), "serve", stdin=asyncio.subprocess.DEVNULL,
            stdout=self._log, stderr=asyncio.subprocess.STDOUT, env=env)

    async def start(self) -> dict:
        async with self._lock:
            current = await self.status()
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
                if readiness["ready"]:
                    return await self.status()
                await asyncio.sleep(0.5)
            self.last_error = "OLLAMA_START_TIMEOUT"
            await self._stop_owned()
            raise AppError("RUNTIME_START_FAILED", "Ollama startup timed out", status_code=503,
                           details={"reason": self.last_error})

    async def _stop_owned(self) -> None:
        process = self.process
        if process is None or process.returncode is not None:
            self.process = None
            if self._log:
                self._log.close()
                self._log = None
            return
        process.terminate()
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
            if not self._owned():
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
