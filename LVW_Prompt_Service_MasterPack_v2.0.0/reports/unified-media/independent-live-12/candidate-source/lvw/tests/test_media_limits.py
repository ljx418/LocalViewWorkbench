from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from test_api import FakeProvider, upload


def test_exact_20_mib_is_allowed_and_one_over_is_rejected(tmp_path, png_bytes):
    client = TestClient(create_app(Settings.local(data_root=tmp_path), provider=FakeProvider()))
    exact = png_bytes + b"\0" * (20 * 1024 * 1024 - len(png_bytes))
    accepted = upload(client, exact, key="exact-bytes")
    assert accepted.status_code == 201
    assert accepted.json()["data"]["bytes"] == 20 * 1024 * 1024
    rejected = upload(client, exact + b"x", key="over-bytes")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "MEDIA_LIMIT_EXCEEDED"


def test_exact_40_megapixels_is_allowed_and_one_over_is_rejected(tmp_path):
    client = TestClient(create_app(Settings.local(data_root=tmp_path), provider=FakeProvider()))
    exact_io = BytesIO()
    Image.new("1", (8000, 5000), 1).save(exact_io, format="PNG")
    accepted = upload(client, exact_io.getvalue(), key="exact-pixels", name="exact.png")
    assert accepted.status_code == 201
    assert accepted.json()["data"]["width"] * accepted.json()["data"]["height"] == 40_000_000

    over_io = BytesIO()
    Image.new("1", (8001, 5000), 1).save(over_io, format="PNG")
    rejected = upload(client, over_io.getvalue(), key="over-pixels", name="over.png")
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "MEDIA_LIMIT_EXCEEDED"


def test_filename_is_display_only_and_cannot_escape_media_root(tmp_path, png_bytes):
    client = TestClient(create_app(Settings.local(data_root=tmp_path), provider=FakeProvider()))
    response = upload(client, png_bytes, key="path", name="../../private.png")
    assert response.status_code == 201
    assert response.json()["data"]["display_name"] == "private.png"
    files = list((tmp_path / "media").iterdir())
    assert len(files) == 1
    assert files[0].parent == tmp_path / "media"
