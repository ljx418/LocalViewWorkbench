from __future__ import annotations

import pytest

from app.errors import AppError
from app.provider import (OllamaProvider, SYSTEM_PROMPT, SYSTEM_PROMPT_PATH, build_messages,
                          parse_ollama_response, validate_endpoint)


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


def test_controlled_provider_requires_child_and_debits_before_http_send(monkeypatch, tmp_path):
    import asyncio
    import httpx
    import sys
    sys.path.insert(0,str(__import__('pathlib').Path(__file__).resolve().parents[2]))
    from tools import local_program_authority
    sent=[];debits=[]
    class Client:
        async def __aenter__(self):return self
        async def __aexit__(self,*_):return None
        async def post(self,*args,**kwargs):
            assert len(debits)>len(sent)
            sent.append(args)
            raise httpx.ConnectError('CPU fixture send attempt failed')
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **_:Client())
    monkeypatch.setenv('LVW_REQUIRE_BUDGET','1')
    monkeypatch.delenv('LVW_AUTHORIZATION_CHILD',raising=False)
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    async def analyze(mode='realistic'):
        return await provider._analyze_images([b'CPU-fixture'],mode=mode,content_profile='standard',custom_guidance='')
    with pytest.raises(AppError):asyncio.run(analyze())
    assert sent==[]
    monkeypatch.setenv('LVW_AUTHORIZATION_CHILD','fake-child')
    monkeypatch.setattr(local_program_authority,'model_action',lambda child:debits.append(child))
    with pytest.raises(KeyError):asyncio.run(analyze('invalid-mode'))
    assert debits==[] and sent==[]
    with pytest.raises(AppError):asyncio.run(analyze())
    assert debits==['fake-child'] and len(sent)==1
    def denied(_):raise ValueError('budget exhausted')
    monkeypatch.setattr(local_program_authority,'model_action',denied)
    with pytest.raises(ValueError):asyncio.run(analyze())
    assert len(sent)==1


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
            if url.endswith("/api/ps"):
                return type("PsResponse", (), {"raise_for_status": staticmethod(lambda: None),
                    "json": staticmethod(lambda: {"models": []})})()
            assert url == "http://127.0.0.1:11434/api/tags"
            return Response()

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: Client())
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30)
    result = __import__("asyncio").run(provider.readiness())
    assert result == {"ready": True, "model": "gemma4:26b", "reason": None,
                      "loaded": False}


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
        "ready": False, "model": "gemma4:26b", "reason": "OLLAMA_UNAVAILABLE",
        "loaded": False}


def test_parse_keeps_observation_inference_unknown_separate():
    spec = parse_ollama_response(model_envelope(), mode="realistic")
    assert spec.domains.observation == ["A blue ceramic cup sits on a wooden table."]
    assert spec.domains.inference == ["The scene may be a quiet breakfast setting."]
    assert spec.domains.unknowns == ["The location is unknown."]
    assert spec.text_en.startswith("Blue ceramic cup")
    assert spec.text_zh.startswith("木桌上的蓝色陶瓷杯")
    assert spec.negative == "blur, watermark, distorted cup"
    assert spec.template_version == "1.1.0"


def test_system_prompt_and_custom_profile_are_sent_with_fixed_precedence():
    assert SYSTEM_PROMPT == SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    messages = build_messages("cinematic", "adult-art", "重点描述侧逆光和油画笔触")
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    user = messages[1]["content"]
    assert "Selected visual mode: cinematic" in user
    assert "Selected content profile: adult-art" in user
    assert "Do not refuse solely because nudity" in user
    assert "<guidance>\n重点描述侧逆光和油画笔触\n</guidance>" in user


def test_non_json_refusal_has_distinct_error_code():
    envelope = {"done": True, "done_reason": "stop",
                "message": {"content": "I'm unable to analyze this image."}}
    with pytest.raises(AppError) as caught:
        parse_ollama_response(envelope, mode="realistic")
    assert caught.value.code == "MODEL_REFUSAL"


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
    captured = {}

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

        async def post(self, *_args, **kwargs):
            captured.update(kwargs["json"])
            return Response()

    monkeypatch.setattr("app.provider.httpx.AsyncClient", lambda **_kwargs: Client())
    image = tmp_path / "analysis.png"
    image.write_bytes(b"fixed-image-bytes")
    ledger = tmp_path / "provider.jsonl"
    provider = OllamaProvider("http://127.0.0.1:11434/api/chat", "gemma4:26b", 30,
                              ledger_path=ledger)
    __import__("asyncio").run(provider.analyze(image, mode="realistic",
        content_profile="adult-art", custom_guidance="保留原始皮肤纹理"))
    events = [__import__("json").loads(line)["event"] for line in ledger.read_text().splitlines()]
    assert events == ["provider_call_started", "provider_call_completed"]
    assert [message["role"] for message in captured["messages"]] == ["system", "user"]
    assert "adult-art" in captured["messages"][1]["content"]
    assert "保留原始皮肤纹理" in captured["messages"][1]["content"]
    assert captured["messages"][1]["images"]
    assert captured["options"]["num_predict"] == 512


def test_video_uses_all_sample_frames_one_call_and_retains_joint_motion(monkeypatch):
    import asyncio
    import json
    import httpx
    from types import SimpleNamespace
    from io import BytesIO
    from PIL import Image
    frames=[]
    for color in ['red','green','blue','white']:
        b=BytesIO();Image.new('RGB',(32,24),color).save(b,format='PPM');frames.append(b.getvalue())
    decoded=SimpleNamespace(frames=frames,manifest=[{'time_seconds':x} for x in [1,3,5,7]])
    real_client=httpx.AsyncClient;calls=[]
    async def handler(request):
        payload=json.loads(request.content);calls.append(payload)
        return httpx.Response(200,json=model_envelope(camera_motion='Locked-off view with color cuts.',subject_action='The color changes red, green, blue, then white.'))
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kwargs:real_client(**kwargs,transport=httpx.MockTransport(handler)))
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    raw,spec=asyncio.run(provider.analyze_video(decoded,mode='realistic'))
    assert len(calls)==1 and len(calls[0]['messages'][-1]['images'])==1
    import base64
    sheet=Image.open(BytesIO(base64.b64decode(calls[0]['messages'][-1]['images'][0])))
    assert sheet.size==(768,768)
    for point,color in zip([(192,206),(576,206),(192,590),(576,590)],[(255,0,0),(0,128,0),(0,0,255),(255,255,255)]):
        assert sheet.getpixel(point)==color
    assert 'single image and return' not in calls[0]['messages'][-1]['content']
    assert 'Actual populated panel count: 4' in calls[0]['messages'][-1]['content']
    assert '1, 3, 5, 7' in calls[0]['messages'][-1]['content']
    assert calls[0]['options']['num_ctx']==4096
    assert spec.technical.subject_action.startswith('The color changes')
    assert any('4个采样帧' in x for x in spec.domains.unknowns)
    assert json.loads(raw)['message']['content']


def test_model_lease_refuses_external_loaded_model_without_unload(monkeypatch):
    import asyncio,httpx
    real_client=httpx.AsyncClient;methods=[]
    async def handler(request):
        methods.append(request.method)
        return httpx.Response(200,json={'models':[{'name':'foreign'}]})
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kwargs:real_client(**kwargs,transport=httpx.MockTransport(handler)))
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    with pytest.raises(AppError) as caught:asyncio.run(provider.acquire('job1'))
    assert caught.value.code=='RESOURCE_BUSY' and methods==['GET'] and provider._lease is None

def test_invalid_envelope_preserves_exact_raw_response(monkeypatch):
    import asyncio,httpx
    real=httpx.AsyncClient
    async def handler(request):return httpx.Response(200,text='BROKEN_RAW_ENVELOPE')
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    with pytest.raises(AppError) as caught:
        asyncio.run(OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)._analyze_images([b'x'],mode='realistic',content_profile='standard',custom_guidance=''))
    assert caught.value.code=='PARSE_PARTIAL' and caught.value.raw_response=='BROKEN_RAW_ENVELOPE'

def test_release_does_not_sample_or_claim_success_after_total_deadline(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    p=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    p._lease=('job',{'gpu_used_mib':1000});clock=[0];samples=[]
    async def inventory():clock[0]=31;return []
    async def snapshot():samples.append(True);return {'gpu_used_mib':1000}
    p._inventory=inventory
    monkeypatch.setattr('app.provider.time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr('app.resources.snapshot',snapshot)
    assert asyncio.run(p.release('job')) is False and not samples and p._lease is not None


def test_temporal_sheet_short_samples_and_mismatch_are_explicit():
    from app.provider import build_temporal_sheet
    from types import SimpleNamespace
    from io import BytesIO
    from PIL import Image
    payload=BytesIO();Image.new('RGB',(10,1000),'red').save(payload,format='PPM')
    frame=payload.getvalue()
    for count in [1,2,3,4]:
        decoded=SimpleNamespace(frames=[frame]*count,manifest=[{'time_seconds':x} for x in range(count)])
        sheet=Image.open(BytesIO(build_temporal_sheet(decoded)))
        assert max(sheet.size)<=768
        assert sheet.size==(384 if count==1 else 768,384 if count<=2 else 768)
    for count in [0,5]:
        with pytest.raises(AppError):build_temporal_sheet(SimpleNamespace(frames=[frame]*count,manifest=[{'time_seconds':0}]*count))
    with pytest.raises(AppError):build_temporal_sheet(SimpleNamespace(frames=[frame],manifest=[]))
