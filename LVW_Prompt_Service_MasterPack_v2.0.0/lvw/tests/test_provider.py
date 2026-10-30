from __future__ import annotations

import pytest

from app.errors import AppError
from app.provider import OllamaProvider, parse_ollama_response, validate_endpoint


def model_envelope(**updates):
    content = {
        "observations": ["A blue ceramic cup sits on a wooden table."],
        "inferences": ["The scene may be a quiet breakfast setting."],
        "unknowns": ["The location is unknown."],
        "prompt_zh": "木桌上的蓝色陶瓷杯，柔和窗光，特写摄影",
        "prompt": "Blue ceramic cup on a wooden table, soft window light, close-up photograph",
        "negative": "blur, watermark, distorted cup",
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


def test_readiness_requires_exact_configured_model(monkeypatch):
    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"models": [{"name": "other:latest"}, {"name": "gemma4:26b"}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return None
        async def get(self, url):
            assert url == "http://127.0.0.1:11434/api/tags"
            return Response()

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: Client())
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30)
    result = __import__("asyncio").run(provider.readiness())
    assert result == {"ready": True, "model": "gemma4:26b", "reason": None}


def test_readiness_reports_missing_model_and_unreachable_ollama(monkeypatch):
    class MissingResponse:
        @staticmethod
        def raise_for_status(): return None
        @staticmethod
        def json(): return {"models": [{"name": "other:latest"}]}

    class MissingClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return None
        async def get(self, _url): return MissingResponse()

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: MissingClient())
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30)
    assert __import__("asyncio").run(provider.readiness())["reason"] == "MODEL_NOT_INSTALLED"

    class OfflineClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return None
        async def get(self, _url): raise __import__("httpx").ConnectError("offline")

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: OfflineClient())
    assert __import__("asyncio").run(provider.readiness()) == {
        "ready": False, "model": "gemma4:26b", "reason": "OLLAMA_UNAVAILABLE"}


def test_parse_keeps_observation_inference_unknown_separate():
    spec = parse_ollama_response(model_envelope(), mode="realistic")
    assert spec.domains.observation == ["A blue ceramic cup sits on a wooden table."]
    assert spec.domains.inference == ["The scene may be a quiet breakfast setting."]
    assert spec.domains.unknowns == ["The location is unknown."]
    assert spec.text_en.startswith("Blue ceramic cup")
    assert spec.text_zh.startswith("木桌上的蓝色陶瓷杯")
    assert spec.negative == "blur, watermark, distorted cup"


def test_parse_rejects_extra_or_incomplete_fields():
    with pytest.raises(AppError) as caught:
        parse_ollama_response(model_envelope(extra="not allowed"), mode="realistic")
    assert caught.value.code == "PARSE_PARTIAL"
    incomplete = model_envelope()
    incomplete["done"] = False
    with pytest.raises(AppError):
        parse_ollama_response(incomplete, mode="realistic")


@pytest.mark.parametrize("field", ["prompt_zh", "prompt", "negative"])
def test_parse_rejects_missing_or_blank_four_output_fields(field):
    envelope = model_envelope()
    content = __import__("json").loads(envelope["message"]["content"])
    content[field] = ""
    envelope["message"]["content"] = __import__("json").dumps(content)

    with pytest.raises(AppError) as caught:
        parse_ollama_response(envelope, mode="realistic")

    assert caught.value.code == "PARSE_PARTIAL"


def test_provider_ledger_is_atomic_and_contains_no_source_path(tmp_path):
    ledger = tmp_path / "provider.jsonl"
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30,
                              ledger_path=ledger)
    provider._record("provider_call_started", "call_test", input_sha256="a" * 64)
    record = __import__("json").loads(ledger.read_text(encoding="utf-8"))
    assert record["event"] == "provider_call_started"
    assert record["call_id"] == "call_test"
    assert record["input_sha256"] == "a" * 64
    assert str(tmp_path) not in ledger.read_text(encoding="utf-8")


def test_analyze_ledger_counts_real_provider_boundary_once(tmp_path, monkeypatch):
    envelope = model_envelope()

    class Response:
        text = __import__("json").dumps(envelope)

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return envelope

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: Client())
    image = tmp_path / "analysis.png"
    image.write_bytes(b"fixed-image-bytes")
    ledger = tmp_path / "provider.jsonl"
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30,
                              ledger_path=ledger)
    __import__("asyncio").run(provider.analyze(image, mode="realistic"))
    events = [__import__("json").loads(line)["event"] for line in ledger.read_text().splitlines()]
    assert events == ["provider_call_started", "provider_call_completed"]
