from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture
def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 40), (42, 91, 212)).save(output, format="PNG")
    return output.getvalue()
