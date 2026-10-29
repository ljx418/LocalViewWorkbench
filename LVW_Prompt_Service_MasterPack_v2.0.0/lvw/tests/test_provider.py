from __future__ import annotations

import pytest

from app.errors import AppError
from app.provider import parse_ollama_response, validate_endpoint


def model_envelope(**updates):
    content = {
        "observations": ["A blue ceramic cup sits on a wooden table."],
        "inferences": ["The scene may be a quiet breakfast setting."],
        "unknowns": ["The location is unknown."],
        "prompt": "Blue ceramic cup on a wooden table, soft window light, close-up photograph",
        "tags": ["ceramic cup", "soft light"],
    }
    content.update(updates)
    return {"done": True, "done_reason": "stop", "message": {"content": __import__("json").dumps(content)}}


def test_endpoint_is_literal_loopback_only():
    validate_endpoint("http://127.0.0.1:11434/api/chat")
    for endpoint in ["http://localhost:11434/api/chat", "https://127.0.0.1:11434/api/chat",
                     "http://127.0.0.1:11434/api/chat?x=1", "http://example.com/api/chat"]:
        with pytest.raises(AppError) as caught:
            validate_endpoint(endpoint)
        assert caught.value.code == "ORIGIN_FORBIDDEN"


def test_parse_keeps_observation_inference_unknown_separate():
    spec = parse_ollama_response(model_envelope(), mode="realistic")
    assert spec.domains.observation == ["A blue ceramic cup sits on a wooden table."]
    assert spec.domains.inference == ["The scene may be a quiet breakfast setting."]
    assert spec.domains.unknowns == ["The location is unknown."]
    assert spec.text_en.startswith("Blue ceramic cup")
    assert spec.text_zh == ""
    assert spec.negative == ""


def test_parse_rejects_extra_or_incomplete_fields():
    with pytest.raises(AppError) as caught:
        parse_ollama_response(model_envelope(extra="not allowed"), mode="realistic")
    assert caught.value.code == "PARSE_PARTIAL"
    incomplete = model_envelope()
    incomplete["done"] = False
    with pytest.raises(AppError):
        parse_ollama_response(incomplete, mode="realistic")
