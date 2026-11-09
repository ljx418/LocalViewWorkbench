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
    assert events == ["provider_call_started", "provider_response_received", "provider_call_completed"]
    rows=[__import__("json").loads(line) for line in ledger.read_text().splitlines()]
    assert rows[1]['wire_response_sha256']==__import__('hashlib').sha256(Response.text.encode()).hexdigest()
    assert rows[0]['request_payload_sha256']==__import__('hashlib').sha256(
        __import__('json').dumps(captured,sort_keys=True,separators=(',',':')).encode()).hexdigest()
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
    for point,color in zip([(192,140),(576,140),(192,396),(576,396)],[(255,0,0),(0,128,0),(0,0,255),(255,255,255)]):
        assert sheet.getpixel(point)==color
    for point,color in zip([(128,652),(384,652),(640,652)],[(255,128,0),(0,128,255),(255,255,0)]):
        assert sheet.getpixel(point)==color  # Exact residuals, not fabricated motion labels.
    from app.provider import VIDEO_SYSTEM_PROMPT, VIDEO_SYSTEM_PROMPT_PATH
    assert calls[0]['messages'][0]=={'role':'system','content':VIDEO_SYSTEM_PROMPT}
    assert VIDEO_SYSTEM_PROMPT==SYSTEM_PROMPT+'\n\n'+VIDEO_SYSTEM_PROMPT_PATH.read_text(encoding='utf-8').strip()
    assert 'single image and return' not in calls[0]['messages'][-1]['content']
    assert 'Actual populated SOURCE panel count: 4' in calls[0]['messages'][-1]['content']
    assert '1, 3, 5, 7' in calls[0]['messages'][-1]['content']
    measured=json.loads(calls[0]['messages'][-1]['content'].split('Measured adjacent-frame pixel differences (not motion estimates): ',1)[1])
    assert len(measured)==3 and all(x['different_pixel_percent']==100 for x in measured)
    assert measured[0]['mean_absolute_rgb_delta']==127.666667
    assert calls[0]['options']['num_ctx']==4096
    assert spec.technical.subject_action.startswith('The color changes')
    assert spec.template_version=='1.5.0'
    registration=json.loads(calls[0]['messages'][-1]['content'].split('Measured image registration (not physical camera motion): ',1)[1].split('\nMeasured adjacent-frame',1)[0])
    assert len(registration)==3 and all(not item['usable'] for item in registration)
    assert any('4个采样帧' in x for x in spec.domains.unknowns)
    assert json.loads(raw)['message']['content']


def test_pixel_metadata_static_one_pixel_and_single_frame_have_exact_oracles():
    from io import BytesIO
    from PIL import Image
    from app.provider import temporal_pixel_measurements
    def encode(image):
        out=BytesIO();image.save(out,format='PNG');return out.getvalue()
    black=Image.new('RGB',(2,2),'black');changed=black.copy();changed.putpixel((0,0),(12,24,36))
    first=encode(black);second=encode(changed)
    assert temporal_pixel_measurements([first])==[]
    assert temporal_pixel_measurements([first,first])==[{'from_frame':1,'to_frame':2,'changed_pixel_count':0,'frame_pixel_count':4,'different_pixel_percent':0,'mean_absolute_rgb_delta':0}]
    assert temporal_pixel_measurements([first,second])==[{'from_frame':1,'to_frame':2,'changed_pixel_count':1,'frame_pixel_count':4,'different_pixel_percent':25,'mean_absolute_rgb_delta':6}]
    with pytest.raises(AppError):temporal_pixel_measurements([first,encode(Image.new('RGB',(3,2)))])


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
        assert sheet.size==(384 if count==1 else 768,{1:256,2:512,3:768,4:768}[count])
    for count in [0,5]:
        with pytest.raises(AppError):build_temporal_sheet(SimpleNamespace(frames=[frame]*count,manifest=[{'time_seconds':0}]*count))
    with pytest.raises(AppError):build_temporal_sheet(SimpleNamespace(frames=[frame],manifest=[]))


def test_residual_panels_match_independent_pixel_oracle_and_keep_source_corners():
    from io import BytesIO
    from types import SimpleNamespace
    from PIL import Image
    from app.provider import build_temporal_sheet
    def encode(image):
        output=BytesIO();image.save(output,format='PNG');return output.getvalue()
    source=Image.new('RGB',(16,16),'black')
    for point,color in [((0,0),'red'),((15,0),'green'),((0,15),'blue'),((15,15),'yellow')]:
        source.putpixel(point,Image.new('RGB',(1,1),color).getpixel((0,0)))
    variants=[source.copy(),Image.new('RGB',(16,16),(25,50,75)),source.copy(),source.copy()]
    # Source motion, global illumination and a local change; no inference of their causes.
    variants[2].putpixel((8,8),(255,0,0))
    variants[3].putpixel((9,8),(255,0,0))
    for original,target in [(source,variants[0]),(source,variants[1]),(source,variants[2]),(variants[2],variants[3])]:
        inputs=[encode(original),encode(target)]
        sheet=Image.open(BytesIO(build_temporal_sheet(SimpleNamespace(frames=inputs,manifest=[{'time_seconds':1},{'time_seconds':3}]))))
        # Both full 16x16 originals survive, including all four corners.
        for index,panel_source in enumerate([original,target]):
            for y in range(16):
                for x in range(16):assert sheet.getpixel((index*384+184+x,132+y))==panel_source.getpixel((x,y))
        for y in range(16):
            for x in range(16):
                expected=tuple(abs(a-b) for a,b in zip(original.getpixel((x,y)),target.getpixel((x,y))))
                assert sheet.getpixel((376+x,388+y))==expected
        assert inputs==[encode(original),encode(target)]


def test_registration_translation_static_light_and_aliases_are_measurements_only():
    from app.provider import temporal_alignment_measurements
    from PIL import Image, ImageChops
    from io import BytesIO
    import random
    def encode(image):
        b=BytesIO();image.save(b,format='PNG');return b.getvalue()
    rng=random.Random(211)
    source=Image.new('L',(64,48));source.putdata([rng.randrange(180) for _ in range(64*48)])
    original=encode(source)
    shifted=encode(ImageChops.offset(source,3,-2))
    result=temporal_alignment_measurements([original,shifted])[0]
    assert result['next_to_previous_alignment_offset_px']=={'x':-3,'y':2}
    assert result['best_aligned_mean_luma_error']==0 and result['relative_error_reduction']==1
    assert result['equally_best_offsets']==1
    static=temporal_alignment_measurements([original,original])[0]
    assert static['next_to_previous_alignment_offset_px']=={'x':0,'y':0}
    assert static['unaligned_mean_luma_error']==0 and static['relative_error_reduction']==0
    light=temporal_alignment_measurements([original,encode(source.point(lambda p:p+15))])[0]
    assert light['next_to_previous_alignment_offset_px']=={'x':0,'y':0}
    assert light['unaligned_mean_luma_error']==15
    stripes=Image.new('L',(64,48));stripes.putdata([200 if x%8<4 else 0 for y in range(48) for x in range(64)])
    repeated=temporal_alignment_measurements([encode(stripes),encode(ImageChops.offset(stripes,2,0))])[0]
    assert repeated['equally_best_offsets']>1 and repeated['best_aligned_mean_luma_error']==0
    blank=encode(Image.new('RGB',(32,32),'red'))
    assert temporal_alignment_measurements([blank,blank])[0]['reason']=='reference_has_no_texture'
    narrow=encode(Image.new('RGB',(1,128),'red'))
    assert temporal_alignment_measurements([narrow,narrow])[0]['reason']=='analysis_too_narrow'
    assert temporal_alignment_measurements([original])==[]
    with pytest.raises(AppError):temporal_alignment_measurements([original,blank])
    assert original==encode(source)


def test_colour_registration_separates_moving_texture_from_fixed_colour_patch():
    from app.provider import temporal_alignment_measurements
    from PIL import Image, ImageChops, ImageDraw
    from io import BytesIO
    import random
    def encode(image):
        output=BytesIO();image.save(output,format='PNG');return output.getvalue()
    rng=random.Random(425)
    background=Image.new('L',(96,72))
    background.putdata([rng.randrange(30,210) for _ in range(96*72)])
    first=background.convert('RGB');second=ImageChops.offset(background,4,-3).convert('RGB')
    for frame in (first,second):ImageDraw.Draw(frame).rectangle((39,27,56,44),fill=(220,20,20))
    inputs=[encode(first),encode(second)];before=inputs.copy()
    result=temporal_alignment_measurements(inputs)[0]
    assert result['next_to_previous_alignment_offset_px']=={'x':-4,'y':3}
    colour={x['component']:x for x in result['colour_components']}
    for name in ('R-G','B-R'):
        assert colour[name]['usable']
        assert colour[name]['offset_px']=={'x':0,'y':0}
        assert colour[name]['zero_error']==colour[name]['best_error']==0
        assert colour[name]['equally_best_offsets']==1
    assert not colour['G-B']['usable']  # Equal G/B has no texture; never an offset claim.
    assert inputs==before


def test_colour_registration_recovers_equal_luma_motion_and_static_negative():
    from app.provider import temporal_alignment_measurements
    from PIL import Image, ImageChops
    from io import BytesIO
    import random
    def encode(image):
        output=BytesIO();image.save(output,format='PNG');return output.getvalue()
    rng=random.Random(426)
    source=Image.new('RGB',(64,48))
    source.putdata([(255,0,0) if rng.randrange(2) else (0,129,0) for _ in range(64*48)])
    assert len(set(source.convert('L').getdata()))==1
    result=temporal_alignment_measurements([encode(source),encode(ImageChops.offset(source,-2,1))])[0]
    assert not result['usable']
    for component in result['colour_components']:
        assert component['usable'] and component['offset_px']=={'x':2,'y':-1}
        assert component['error_reduction_percent']==100 and component['best_error']==0
        assert component['equally_best_offsets']==1
    static=temporal_alignment_measurements([encode(source)]*2)[0]
    for component in static['colour_components']:
        assert component['usable'] and component['offset_px']=={'x':0,'y':0}
        assert component['zero_error']==component['best_error']==0


def test_private_thinking_opt_in_requires_live_show_support_before_inference(monkeypatch):
    import asyncio,httpx,json
    real=httpx.AsyncClient;paths=[];supported=[None]
    envelope=model_envelope();envelope['message']['thinking']='CPU fixture, not a real reasoning result'
    raw=json.dumps(envelope)
    async def handler(request):
        paths.append(request.url.path)
        if request.url.path=='/api/show':
            return httpx.Response(200,json={'capabilities':supported[0]})
        assert request.url.path=='/api/chat' and json.loads(request.content)['think'] is True
        return httpx.Response(200,text=raw)
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    async def call(thinking=True):
        return await provider._analyze_images([b'CPU-only'],mode='realistic',content_profile='standard',custom_guidance='',thinking=thinking)
    for invalid in (None,'not-thinking',{'thinking':True},[1,'thinking'],[]):
        supported[0]=invalid
        with pytest.raises(AppError):asyncio.run(call())
        assert all(path=='/api/show' for path in paths)
    before=paths.copy()
    with pytest.raises(AppError):asyncio.run(call('yes'))
    assert paths==before
    supported[0]=['thinking']
    returned,_=asyncio.run(call())
    assert paths==before+['/api/show','/api/chat'] and returned==raw


def test_compact_alignment_retains_numeric_values_units_aliases_and_unusable_reasons():
    from app.provider import compact_alignment_metadata
    measured=[{'from_frame':1,'to_frame':2,'usable':True,'analysis_size':[64,48],
        'search_radius_px':10,'next_to_previous_alignment_offset_px':{'x':-4,'y':2},
        'unaligned_mean_luma_error':20.25,'best_aligned_mean_luma_error':3.75,
        'relative_error_reduction':0.814815,'equally_best_offsets':2,
        'colour_components':[{'component':'R-G','usable':True,'offset_px':{'x':0,'y':0},
            'zero_error':0,'best_error':0,'error_reduction_percent':0,'equally_best_offsets':3},
            {'component':'G-B','usable':False,'reason':'reference_has_no_texture'}]},
        {'from_frame':2,'to_frame':3,'usable':False,'reason':'analysis_too_narrow',
            'colour_components':[{'component':'B-R','usable':False,'reason':'analysis_too_narrow'}]}]
    compact=compact_alignment_metadata(measured)
    row=compact['pairs'][0]
    decoded=dict(zip(compact['gray_columns'],row['gray'],strict=True))
    assert decoded=={'offset_x_px':-4,'offset_y_px':2,'zero_error':20.25,'best_error':3.75,
        'reduction_fraction_0_to1':0.814815,'ties':2}
    assert dict(zip(compact['colour_columns'],row['colour'][0],strict=True))=={
        'component':'R-G','offset_x_px':0,'offset_y_px':0,'zero_error':0,'best_error':0,
        'reduction_percent_0_to100':0,'ties':3}
    assert row['analysis_size']==[64,48] and row['search_radius_px']==10
    assert row['colour'][1]=={'component':'G-B','unusable_reason':'reference_has_no_texture'}
    assert compact['pairs'][1]=={'from_frame':2,'to_frame':3,'gray_unusable_reason':'analysis_too_narrow',
        'colour':[{'component':'B-R','unusable_reason':'analysis_too_narrow'}]}


def test_private_compact1536_probe_uses_same_source_sheet_and_one_guarded_chat(monkeypatch,tmp_path):
    import asyncio,httpx,json,base64,hashlib
    from types import SimpleNamespace
    from io import BytesIO
    from PIL import Image
    from app.provider import build_temporal_sheet, VIDEO_COMPACT_TEMPLATE_SHA256
    frame=BytesIO();Image.new('RGB',(16,16),'blue').save(frame,format='PPM')
    decoded=SimpleNamespace(frames=[frame.getvalue()]*4,manifest=[{'time_seconds':t} for t in (1,3,5,7)])
    real=httpx.AsyncClient;captured=[]
    async def handler(request):
        if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['thinking','vision']})
        assert request.url.path=='/api/chat';captured.append(json.loads(request.content))
        return httpx.Response(200,json=model_envelope(camera_motion='unknown',subject_action='unknown'))
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    ledger=tmp_path/'ledger.jsonl'
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30,ledger_path=ledger)
    _,spec=asyncio.run(provider.analyze_video(decoded,mode='realistic',thinking=True,compact_video=True,video_probe_tokens=1536))
    assert len(captured)==1
    payload=captured[0]
    assert payload['think'] is True and payload['options']=={'num_ctx':4096,'num_predict':1536,'temperature':0.2}
    assert base64.b64decode(payload['messages'][-1]['images'][0])==build_temporal_sheet(decoded)
    registration=json.loads(payload['messages'][-1]['content'].split('Measured image registration (not physical camera motion): ',1)[1].split('\nMeasured adjacent-frame',1)[0])
    assert len(registration['pairs'])==3 and all('gray_unusable_reason' in item for item in registration['pairs'])
    assert spec.template_version=='1.6.0'
    rows=[json.loads(line) for line in ledger.read_text().splitlines()]
    started=next(row for row in rows if row['event']=='provider_call_started')
    assert started['request_template_sha256']==VIDEO_COMPACT_TEMPLATE_SHA256
    assert started['request_payload_sha256']==hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert any(row['event']=='provider_response_received' for row in rows)


def test_private_probe_configuration_failures_do_not_open_transport(monkeypatch):
    import asyncio
    def forbidden(**kwargs):raise AssertionError('invalid configuration opened transport')
    monkeypatch.setattr('app.provider.httpx.AsyncClient',forbidden)
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    for options in ({'compact_video':True},{'video_probe_tokens':1536},
                    {'thinking':True,'video_probe_tokens':1537},{'thinking':True,'video_probe_tokens':True}):
        with pytest.raises(AppError):
            asyncio.run(provider._analyze_images([b'CPU'],mode='realistic',content_profile='standard',custom_guidance='',frames=[],**options))
