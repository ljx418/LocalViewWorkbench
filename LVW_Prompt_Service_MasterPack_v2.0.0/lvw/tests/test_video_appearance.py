from __future__ import annotations
import asyncio,base64,copy,hashlib,json
from io import BytesIO
from types import SimpleNamespace
import httpx
import pytest
from PIL import Image
from app.errors import AppError
from app.provider import OllamaProvider,VIDEO_APPEARANCE_TEMPLATE_SHA256
from app.video_appearance import appearance_schema,parse_appearance,TEMPLATE_ID,TEMPLATE_VERSION


def appearance_envelope(count=4):
    body={'frame_appearances':[{'frame_id':i,'description_zh':f'合成夹具外观{i}',
        'description_en':f'Synthetic fixture appearance{i}'} for i in range(1,count+1)],
        'prompt_zh':'合成夹具汇总','prompt':'Synthetic fixture summary','negative':'blur',
        'tags':['fixture'],'unknowns':['CPU fixture, not model quality evidence']}
    return {'done':True,'done_reason':'stop','message':{'content':json.dumps(body,ensure_ascii=False)}}


def parse(body,count=4):
    envelope=appearance_envelope(count);envelope['message']['content']=json.dumps(body,ensure_ascii=False)
    return parse_appearance(envelope,mode='realistic',frame_times=list(range(count)))


@pytest.mark.parametrize('count',[1,2,3,4])
def test_actual_frame_denominator_is_strict_and_source_metadata_is_code_owned(count):
    envelope=appearance_envelope(count);before=copy.deepcopy(envelope)
    spec=parse_appearance(envelope,mode='realistic',frame_times=list(range(count)))
    assert len(spec.domains.observation)==count and all(text.startswith(f'F{i} @ ') for i,text in enumerate(spec.domains.observation,1))
    assert envelope==before and spec.template_id==TEMPLATE_ID and spec.template_version==TEMPLATE_VERSION
    assert appearance_schema(count)['properties']['frame_appearances']['minItems']==count
    assert 'unverified' in spec.technical.camera_motion


@pytest.mark.parametrize('count',[0,5,True])
def test_no_reduced_or_expanded_frame_denominator(count):
    with pytest.raises(AppError):appearance_schema(count)


@pytest.mark.parametrize('change',[
    lambda b:b['frame_appearances'].pop(),
    lambda b:b['frame_appearances'].append(b['frame_appearances'][0].copy()),
    lambda b:b['frame_appearances'][1].update(frame_id=1),
    lambda b:b['frame_appearances'].reverse(),
    lambda b:b['frame_appearances'][0].update(frame_id=True),
    lambda b:b['frame_appearances'][0].update(frame_id=5),
    lambda b:b['frame_appearances'][0].update(description_zh=' '*3),
    lambda b:b['frame_appearances'][0].update(description_zh='字'*81),
    lambda b:b['frame_appearances'][0].update(description_en='x'*161),
    lambda b:b['frame_appearances'][0].update(camera_motion='none'),
    lambda b:b.update(camera_motion='none'),
    lambda b:b.update(prompt_zh='字'*401),
    lambda b:b.update(prompt='x'*601),
    lambda b:b.update(tags=['x']*9),
    lambda b:b.update(unknowns=['x']*5),
    lambda b:b.update(negative=None),
])
def test_incomplete_identity_extra_motion_fields_and_invalid_text_fail_closed(change):
    body=json.loads(appearance_envelope()['message']['content']);change(body)
    with pytest.raises(AppError) as caught:parse(body)
    assert caught.value.code=='PARSE_PARTIAL'


def test_exact_character_edges_preserve_verbatim_words_and_one_over_rejects():
    body=json.loads(appearance_envelope()['message']['content'])
    body['frame_appearances'][0]['description_zh']='字'*80
    body['frame_appearances'][0]['description_en']='x'*160
    body['prompt_zh']='字'*400;body['prompt']='e'*600;body['negative']='n'*400
    body['tags']=['t'*100]*8;body['unknowns']=['u'*400]*4
    spec=parse(body);assert spec.text_zh==body['prompt_zh'] and spec.text_en==body['prompt'] and spec.negative==body['negative']
    body['negative']+='n'
    with pytest.raises(AppError):parse(body)


def test_duplicate_model_keys_and_truncated_envelopes_are_not_accepted():
    envelope=appearance_envelope();content=envelope['message']['content']
    envelope['message']['content']=content[:-1]+',"prompt":"duplicate"}'
    with pytest.raises(AppError):parse_appearance(envelope,mode='realistic',frame_times=[1,3,5,7])
    for change in ({'done':False},{'done_reason':'length'}):
        envelope=appearance_envelope();envelope.update(change)
        with pytest.raises(AppError):parse_appearance(envelope,mode='realistic',frame_times=[1,3,5,7])


def test_default_production_video_request_uses_every_full_source_and_keeps_raw_exact(monkeypatch):
    frames=[]
    for color in ('red','green','blue','white'):
        stream=BytesIO();Image.new('RGB',(32,24),color).save(stream,format='PPM');frames.append(stream.getvalue())
    decoded=SimpleNamespace(frames=frames,manifest=[{'time_seconds':t} for t in (1,3,5,7)])
    wire=json.dumps(appearance_envelope(),ensure_ascii=False,indent=2);sent=[];events=[];real=httpx.AsyncClient
    async def handler(request):
        assert request.url.path=='/api/chat';sent.append(json.loads(request.content))
        return httpx.Response(200,text=wire)
    monkeypatch.setattr('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler)))
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    monkeypatch.setattr(provider,'_record',lambda event,call,**fields:events.append({'event':event,**fields}))
    raw,spec=asyncio.run(provider.analyze_video(decoded,mode='realistic'))
    assert raw==wire and len(sent)==1 and len(sent[0]['messages'][-1]['images'])==4
    payload=sent[0];assert payload['think'] is False and payload['options']=={'num_ctx':4096,'num_predict':768,'temperature':0.2}
    assert payload['format']==appearance_schema(4)
    content=payload['messages'][-1]['content']
    assert 'Measured image registration' not in content and 'Measured adjacent-frame' not in content
    for source,encoded in zip(frames,payload['messages'][-1]['images'],strict=True):
        assert Image.open(BytesIO(source)).tobytes()==Image.open(BytesIO(base64.b64decode(encoded))).tobytes()
    started=next(row for row in events if row['event']=='provider_call_started')
    assert started['appearance_only'] is True and started['presentation']=='source-frames/appearance-1'
    assert started['request_template_sha256']==VIDEO_APPEARANCE_TEMPLATE_SHA256
    assert spec.template_id==TEMPLATE_ID and len(spec.domains.observation)==4
    assert next(row for row in events if row['event']=='provider_response_received')['wire_response_sha256']==hashlib.sha256(wire.encode()).hexdigest()


def test_appearance_template_cannot_mislabel_contact_sheet_as_full_source_frames(monkeypatch):
    def forbidden(**kwargs):raise AssertionError('invalid appearance source opened transport')
    monkeypatch.setattr('app.provider.httpx.AsyncClient',forbidden)
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30)
    with pytest.raises(AppError):
        asyncio.run(provider._analyze_images([b'one-contact-sheet'],mode='realistic',content_profile='standard',
            custom_guidance='',frames=[{'time_seconds':t} for t in (1,3,5,7)],appearance_only=True))
