#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import sys

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT.parent))


def configured_port() -> int:
    raw = os.environ.get("LVW_PORT", "8765")
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit("LVW_PORT must be an integer") from exc
    if not 1024 <= port <= 65535:
        raise SystemExit("LVW_PORT must be between 1024 and 65535")
    return port


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=configured_port(), log_level="info")
