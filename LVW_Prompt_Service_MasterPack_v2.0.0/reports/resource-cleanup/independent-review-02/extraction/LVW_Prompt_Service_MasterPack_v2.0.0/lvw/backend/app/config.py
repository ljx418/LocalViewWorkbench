from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    static_root: Path | None = None
    ollama_endpoint: str = "http://127.0.0.1:11434/api/chat"
    model: str = "gemma4:26b"
    request_timeout_seconds: int = 120
    ollama_executable: Path | None = None

    @classmethod
    def local(cls, data_root: Path | None = None, static_root: Path | None = None) -> "Settings":
        configured_root = os.environ.get("LVW_DATA_ROOT") if data_root is None else None
        root = data_root or (Path(configured_root) if configured_root else Path.cwd() / ".lvw-runtime")
        configured_ollama = os.environ.get("LVW_OLLAMA_EXE")
        return cls(data_root=root.resolve(), static_root=static_root.resolve() if static_root else None,
                   ollama_executable=Path(configured_ollama).resolve() if configured_ollama else None)
