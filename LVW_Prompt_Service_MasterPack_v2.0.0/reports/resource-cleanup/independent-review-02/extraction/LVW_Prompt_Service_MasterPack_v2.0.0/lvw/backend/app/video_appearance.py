"""Strict internal frame appearance contract. No temporal inference or external I/O."""
from __future__ import annotations
import json
from .errors import AppError
from .models import Domains, PromptSpec, Technical

TEMPLATE_ID='lvw-video-frame-appearance'
TEMPLATE_VERSION='1.8.0'


def appearance_schema(count: int) -> dict:
    if type(count) is not int or not 1<=count<=4:
        raise AppError('PARSE_PARTIAL','实际视频帧数量无效',status_code=503)
    return {'type':'object','properties':{
        'frame_appearances':{'type':'array','minItems':count,'maxItems':count,'items':{
            'type':'object','properties':{'frame_id':{'type':'integer','enum':list(range(1,count+1))},
                'description_zh':{'type':'string','minLength':1,'maxLength':80},
                'description_en':{'type':'string','minLength':1,'maxLength':160}},
            'required':['frame_id','description_zh','description_en'],'additionalProperties':False}},
        'prompt_zh':{'type':'string','minLength':1,'maxLength':400},
        'prompt':{'type':'string','minLength':1,'maxLength':600},
        'negative':{'type':'string','minLength':1,'maxLength':400},
        'tags':{'type':'array','maxItems':8,'items':{'type':'string','minLength':1,'maxLength':100}},
        'unknowns':{'type':'array','maxItems':4,'items':{'type':'string','minLength':1,'maxLength':400}}},
        'required':['frame_appearances','prompt_zh','prompt','negative','tags','unknowns'],'additionalProperties':False}


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate model field')
        result[key]=value
    return result


def _text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('invalid appearance text')
    return value


def parse_appearance(envelope: dict, *, mode, frame_times: list[float]) -> PromptSpec:
    count=len(frame_times);schema=appearance_schema(count)
    try:
        if envelope.get('done') is not True or envelope.get('done_reason')!='stop':raise ValueError('incomplete response')
        content=json.loads(envelope['message']['content'],object_pairs_hook=_unique_object)
        if not isinstance(content,dict) or set(content)!=set(schema['required']):raise ValueError('appearance fields differ')
        frames=content['frame_appearances']
        if not isinstance(frames,list) or len(frames)!=count:raise ValueError('missing actual frames')
        observations=[]
        for expected,frame in enumerate(frames,1):
            if (not isinstance(frame,dict) or set(frame)!={'frame_id','description_zh','description_en'}
                    or type(frame['frame_id']) is not int or frame['frame_id']!=expected):
                raise ValueError('frame identity/order differs')
            zh=_text(frame['description_zh'],80);_text(frame['description_en'],160)
            observations.append(f'F{expected} @ {frame_times[expected-1]:.3f}s（模型外观）：{zh}')
        zh=_text(content['prompt_zh'],400);en=_text(content['prompt'],600);negative=_text(content['negative'],400)
        tags=content['tags'];unknowns=content['unknowns']
        if not isinstance(tags,list) or len(tags)>8 or not isinstance(unknowns,list) or len(unknowns)>4:
            raise ValueError('appearance arrays differ')
        for value in tags:_text(value,100)
        for value in unknowns:_text(value,400)
        return PromptSpec(mode=mode,domains=Domains(observation=observations,inference=[],user_evidence=[],
            creative_intent=[],unknowns=[*unknowns,f'仅观察{count}个实际采样帧，未采样事件、连续运动与音频未经验证。']),
            technical=Technical(duration_seconds=None,aspect_ratio='',fps_intent=None,
                camera_motion='Physical camera motion unverified.',subject_action='Continuous subject action unverified.',
                lighting='',composition='',style_notes='',beats=[]),locked_fields=[],text_zh=zh,text_en=en,
            tags=tags,negative=negative,template_id=TEMPLATE_ID,template_version=TEMPLATE_VERSION)
    except (ValueError,KeyError,TypeError,AttributeError) as error:
        raise AppError('PARSE_PARTIAL','逐帧外观响应与实际源帧合同不一致',status_code=503) from error
