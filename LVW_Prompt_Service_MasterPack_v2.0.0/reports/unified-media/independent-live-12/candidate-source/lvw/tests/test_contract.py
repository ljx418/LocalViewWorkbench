from __future__ import annotations

import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.config import Settings
from app.main import create_app
from test_api import FakeProvider, upload

ROOT = Path(__file__).resolve().parents[2]
API = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))


def local_refs(value):
    if isinstance(value, dict):
        return {key: (item.replace("#/components/schemas/", "#/$defs/")
                      if key == "$ref" and isinstance(item, str) else local_refs(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [local_refs(item) for item in value]
    return value


def validate_response(path: str, method: str, status: str, payload: dict) -> None:
    schema = API["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    root = {"$ref": "#/$defs/Response", "$defs": {
        **{name: local_refs(value) for name, value in API["components"]["schemas"].items()},
        "Response": local_refs(schema),
    }}
    Draft202012Validator(root).validate(payload)


def test_r1a_uses_exact_frozen_public_paths(tmp_path, png_bytes):
    app = create_app(Settings.local(data_root=tmp_path), provider=FakeProvider())
    paths = set(app.openapi()["paths"])
    assert {"/api/v1/media", "/api/v1/jobs/analyze", "/api/v1/jobs/{id}",
            "/api/v1/model-runs/{id}"} <= paths
    assert "/api/v1/jobs/{job_id}" not in paths

    client = TestClient(app)
    media_response = upload(client, png_bytes)
    validate_response("/api/v1/media", "post", "201", media_response.json())
    media = media_response.json()["data"]
    submitted = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "contract"},
        json={"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
              "config_profile": "local-default"})
    validate_response("/api/v1/jobs/analyze", "post", "202", submitted.json())
    job = client.get(f"/api/v1/jobs/{submitted.json()['data']['id']}")
    validate_response("/api/v1/jobs/{id}", "get", "200", job.json())
    run = client.get(f"/api/v1/model-runs/{job.json()['data']['result_ref']}")
    validate_response("/api/v1/model-runs/{id}", "get", "200", run.json())


def test_runtime_dist_has_no_remote_assets():
    dist = ROOT / "lvw" / "frontend" / "dist"
    index = (dist / "index.html").read_text(encoding="utf-8")
    texts = "\n".join(path.read_text(encoding="utf-8", errors="ignore")
                      for path in dist.rglob("*") if path.is_file())
    assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://', index, re.I)
    assert "11434" not in texts
    assert "/api/chat" not in texts
    assert "localhost" not in texts
