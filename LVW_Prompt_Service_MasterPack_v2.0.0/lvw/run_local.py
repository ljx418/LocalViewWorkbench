#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, log_level="info")
