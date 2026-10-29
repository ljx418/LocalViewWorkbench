from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_root: Path
    static_root: Path | None = None
    ollama_endpoint: str = "http://127.0.0.1:11434/api/chat"
    model: str = "gemma4:26b"
    request_timeout_seconds: int = 120

    @classmethod
    def local(cls, data_root: Path | None = None, static_root: Path | None = None) -> "Settings":
        root = data_root or Path.cwd() / ".lvw-runtime"
        return cls(data_root=root.resolve(), static_root=static_root.resolve() if static_root else None)
