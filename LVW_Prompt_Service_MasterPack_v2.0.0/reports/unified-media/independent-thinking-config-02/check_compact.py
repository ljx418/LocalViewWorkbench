import asyncio,base64,hashlib,json,os,random,sys
from pathlib import Path
from types import SimpleNamespace
R=Path.cwd();O=R/'reports/unified-media/independent-thinking-config-02';sys.path[:0]=[str(R),str(R/'lvw/backend')]
for key in ['LVW_REQUIRE_BUDGET','LVW_PROVIDER_LEDGER','LVW_AUTHORIZATION_CHILD']:os.environ.pop(key,None)
import httpx
import app.provider as p
rng=random.Random(8761)
a=bytes(rng.randrange(256) for _ in range(32*24*3));frames=[b'P6\n32 24\n255\n'+a,b'P6\n32 24\n255\n'+a[3:]+a[:3],b'P6\n32 24\n255\n'+bytes([48,48,48])*768,b'P6\n32 24\n255\n'+bytes([48,48,48])*768]
decoded=SimpleNamespace(frames=frames,manifest=[{'time_seconds':v} for v in (.1,.7,1.9,3.2)])
full=p.temporal_alignment_measurements(frames)
def reconstruct(compact):
    assert compact['gray_columns']==['offset_x_px','offset_y_px','zero_error','best_error','reduction_fraction_0_to1','ties']
    assert compact['colour_columns']==['component','offset_x_px','offset_y_px','zero_error','best_error','reduction_percent_0_to100','ties']
    result=[]
    for row in compact['pairs']:
        item={'from_frame':row['from_frame'],'to_frame':row['to_frame']}
        if 'gray' in row:
            x,y,zero,best,reduction,ties=row['gray']
            item.update(usable=True,analysis_size=row['analysis_size'],search_radius_px=row['search_radius_px'],next_to_previous_alignment_offset_px={'x':x,'y':y},unaligned_mean_luma_error=zero,best_aligned_mean_luma_error=best,relative_error_reduction=reduction,equally_best_offsets=ties)
        else:item.update(usable=False,reason=row['gray_unusable_reason'])
        item['colour_components']=[]
        for v in row['colour']:
            if isinstance(v,dict):c={'component':v['component'],'usable':False,'reason':v['unusable_reason']}
            else:
                label,x,y,zero,best,reduction,ties=v
                c={'component':label,'usable':True,'offset_px':{'x':x,'y':y},'zero_error':zero,'best_error':best,'error_reduction_percent':reduction,'equally_best_offsets':ties}
            item['colour_components'].append(c)
        result.append(item)
    return result
assert reconstruct(p.compact_alignment_metadata(full))==full
body={'observations':['Synthetic pixels.'],'inferences':[],'unknowns':['Cause unknown.'],'prompt_zh':'合成画面','prompt':'Synthetic scene','negative':'blur','tags':[],'camera_motion':'unknown','subject_action':'unknown'}
raw=json.dumps({'done':True,'done_reason':'stop','message':{'content':json.dumps(body),'thinking':'synthetic-private-placeholder'}},indent=2)
events=[];calls=[];real=httpx.AsyncClient
async def handler(req):
    events.append(req.url.path)
    if req.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['thinking']})
    calls.append(json.loads(req.content));return httpx.Response(200,content=raw.encode())
p.httpx.AsyncClient=lambda **kw:real(**kw,transport=httpx.MockTransport(handler))
provider=p.OllamaProvider('http://127.0.0.1:11434/api/chat','synthetic',30);records=[];provider._record=lambda event,call,**kw:records.append({'event':event,**kw})
returned,spec=asyncio.run(provider.analyze_video(decoded,mode='realistic',thinking=True,compact_video=True,video_probe_tokens=1536))
assert returned==raw and spec.template_version=='1.6.0'
assert events==['/api/show','/api/chat'] and len(calls)==1
payload=calls[0];assert payload['options']=={'num_ctx':4096,'num_predict':1536,'temperature':.2}
user=payload['messages'][-1];assert base64.b64decode(user['images'][0])==p.build_temporal_sheet(decoded)
compact=json.loads(user['content'].split('Measured image registration (not physical camera motion): ',1)[1].split('\nMeasured adjacent-frame',1)[0]);assert reconstruct(compact)==full
start=next(x for x in records if x['event']=='provider_call_started');assert start['alignment_measurements']==full
assert start['request_payload_sha256']==hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert next(x for x in records if x['event']=='provider_response_received')['wire_response_sha256']==hashlib.sha256(raw.encode()).hexdigest()
expected=hashlib.sha256((p.TEMPLATE_SHA256+p.VIDEO_SYSTEM_PROMPT+p.VIDEO_COMPACT_TASK+p.VIDEO_PRESENTATION_VERSION+json.dumps(p.VIDEO_SCHEMA,sort_keys=True)).encode()).hexdigest()
assert start['request_template_sha256']==p.VIDEO_COMPACT_TEMPLATE_SHA256==expected
assert 'synthetic-private-placeholder' not in json.dumps(records)
# Every rejected option must fail before opening HTTP; include type/image boundaries.
p.httpx.AsyncClient=lambda **kw:(_ for _ in ()).throw(AssertionError('transport opened'))
invalid=[{'compact_video':True},{'compact_video':'yes'},{'thinking':True,'video_probe_tokens':1537},{'thinking':True,'video_probe_tokens':True},{'thinking':True,'compact_video':True,'frames':None},{'thinking':True,'video_probe_tokens':1536,'frames':None}]
for options in invalid:
    kw={'frames':[],**options}
    try:asyncio.run(provider._analyze_images([b'CPU'],mode='realistic',content_profile='standard',custom_guidance='',**kw))
    except p.AppError:pass
    else:raise AssertionError(options)
summary={'lossless_actual_metadata_roundtrip':True,'explicit_fraction_percent_units':True,'same_source_png':True,'one_chat_after_capability':True,'raw_exact':True,'in_memory_evidence_hashes':True,'template_version':spec.template_version,'compact_template_sha256':expected,'guards_rejected_before_transport':len(invalid),'hidden_reasoning_in_records':False,'real_model_network_ledger_actions':0}
(O/'compact-request.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(O/'compact-checks.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
