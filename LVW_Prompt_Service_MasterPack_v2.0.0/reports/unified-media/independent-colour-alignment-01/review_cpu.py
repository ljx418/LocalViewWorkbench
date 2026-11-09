"""Reproduce from repository root: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lvw/backend python3 reports/unified-media/independent-colour-alignment-01/review_cpu.py
No network, model, media decode, service, ledger or product writes.
"""
import asyncio, hashlib, io, json, os, random
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
import httpx
from app import provider as p
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
FILES=['lvw/backend/app/provider.py','lvw/tests/test_provider.py','.agent-governance/stages/R1/stage-control.json','.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256','contracts/openapi.yaml','plans/acceptance_cases.json','plans/release_gates.json']
def hashes():
 return {f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES if (ROOT/f).exists()}
initial=hashes();checks=[];evidence={}
def check(label,condition,detail=None):
 checks.append({'name':label,'pass':bool(condition),'detail':detail})
 if not condition: raise AssertionError(label)
def encode(im):
 out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
def image(w,h,values):
 im=Image.new('RGB',(w,h));im.putdata(values);return im
def translate(im,dx,dy):
 w,h=im.size;data=list(im.getdata());return image(w,h,[data[((y-dy)%h)*w+(x-dx)%w] for y in range(h) for x in range(w)])
def opponent(im,k):
 # Independent signed integer arithmetic, not ImageChops or production helper.
 a,b=((0,1),(1,2),(2,0))[k]
 return [max(0,min(255,(rgb[a]-rgb[b]+256)//2)) for rgb in im.getdata()]
def oracle(a,b,w,h):
 r=min(10,(min(w,h)-1)//4)
 if r<1:return {'usable':False,'reason':'analysis_too_narrow'}
 coords=[(x,y) for y in range(r,h-r) for x in range(r,w-r)]
 vals=[a[y*w+x] for x,y in coords]
 if len(set(vals))==1:return {'usable':False,'reason':'reference_has_no_texture'}
 scores=[]
 for dy in range(-r,r+1):
  for dx in range(-r,r+1):
   total=sum(abs(a[y*w+x]-b[(y-dy)*w+x-dx]) for x,y in coords)
   scores.append((total,dx*dx+dy*dy,dy,dx))
 best=min(scores);zero=next(t[0] for t in scores if t[2:]==(0,0));area=len(coords)
 return dict(usable=True,offset_px={'x':best[3],'y':best[2]},zero_error=round(zero/area,6),best_error=round(best[0]/area,6),error_reduction_percent=round(100*round((zero-best[0])/zero,6),4) if zero else 0,equally_best_offsets=sum(s[0]==best[0] for s in scores))
def compare(name,a,b):
 inputs=[encode(a),encode(b)];before=inputs.copy();result=p.temporal_alignment_measurements(inputs)[0]
 for k,c in enumerate(result['colour_components']):
  expected=oracle(opponent(a,k),opponent(b,k),*a.size)
  actual={key:value for key,value in c.items() if key!='component'}
  check(name+'/'+c['component'],actual==expected,{'actual':actual,'oracle':expected})
 check(name+'/immutable',inputs==before)
 evidence[name]=result
 return result
rng=random.Random(971321)
a=image(36,28,[tuple(rng.randrange(256) for _ in range(3)) for _ in range(36*28)])
# Exhaustive 65,536 ordered channel pairs; odd negative differences verify truncation.
from PIL import ImageChops
first=Image.new('L',(256,256));second=Image.new('L',(256,256))
first.putdata([i for i in range(256) for j in range(256)]);second.putdata([j for i in range(256) for j in range(256)])
actual=list(ImageChops.subtract(first,second,scale=2,offset=128).getdata())
expected=[(i-j+256)//2 for i in range(256) for j in range(256)]
check('all_65536_opponent_channel_pairs',actual==expected,{'count':65536,'range':[min(actual),max(actual)]})
compare('static',a,a)
for dx,dy in [(3,-2),(-3,2),(0,4),(5,0),(-6,-6)]:
 result=compare('direction_%s_%s'%(dx,dy),a,translate(a,dx,dy))
 check('direction_expected_%s_%s'%(dx,dy),all(c['offset_px']=={'x':-dx,'y':-dy} for c in result['colour_components']))
# Equal Pillow luminance but moving colour texture.
equal=image(36,28,[(255,0,0) if rng.randrange(2) else (0,129,0) for _ in range(36*28)])
result=compare('equal_luma_motion',equal,translate(equal,-3,2))
check('equal_luma_inconclusive',not result['usable'])
check('equal_luma_colour_direction',all(c['offset_px']=={'x':3,'y':-2} for c in result['colour_components']))
# Independent random grey background with fixed chromatic region.
grey=image(48,40,[(v,v,v) for v in [rng.randrange(30,220) for _ in range(48*40)]])
bg=translate(grey,3,-2)
for im in (grey,bg):
 for y in range(15,25):
  for x in range(19,29): im.putpixel((x,y),(211,23,23))
result=compare('background_motion_fixed_chroma',grey,bg)
check('background_direction',result['next_to_previous_alignment_offset_px']=={'x':-3,'y':2})
check('fixed_chroma_zero',all(c.get('offset_px',{'x':0,'y':0})=={'x':0,'y':0} for c in result['colour_components']))
period=image(36,28,[(200,20,100) if x%2 else (20,200,30) for y in range(28) for x in range(36)])
result=compare('periodic_alias',period,translate(period,1,0))
check('alias_disclosed',all(c['equally_best_offsets']>1 for c in result['colour_components']))
compare('flat',Image.new('RGB',(24,24),(99,40,0)),Image.new('RGB',(24,24),(110,60,3)))
compare('narrow',Image.new('RGB',(3,3)),Image.new('RGB',(3,3),'red'))
# Central-window and bounded search deliberately cannot see all image changes.
edge=a.copy();edge.putpixel((0,0),(255,0,255))
result=compare('edge_only_change',a,edge)
check('edge_change_not_seen_by_registration',all(c['zero_error']==0 for c in result['colour_components']))
pixels=p.temporal_pixel_measurements([encode(a),encode(edge)])[0]
check('edge_seen_by_full_pixel_measurement',pixels['changed_pixel_count']==1)
compare('out_of_search_radius',a,translate(a,9,0))
# Mismatched sizes remain rejected.
try:p.temporal_alignment_measurements([encode(a),encode(Image.new('RGB',(37,28)))])
except p.AppError as error:check('mismatched_size_rejected',error.code=='PARSE_PARTIAL')
else:check('mismatched_size_rejected',False)
check('single_frame_empty',p.temporal_alignment_measurements([encode(a)])==[])
# Capture real httpx.Request serialization using in-process MockTransport only.
# Authorization env is cleared solely in this process; no ledger configured/debited.
for key in ('LVW_AUTHORIZATION_CHILD','LVW_REQUIRE_BUDGET'):os.environ.pop(key,None)
content={'observations':['Colour regions change.'],'inferences':['Cause unknown.'],'unknowns':['Audio unknown.'],'prompt_zh':'彩色纹理画面','prompt':'A textured colour image','negative':'blur','tags':['texture'],'camera_motion':'Unknown camera motion.','subject_action':'Positions uncertain; sampled pixels differ.'}
envelope={'done':True,'done_reason':'stop','message':{'content':json.dumps(content)}}
raw_expected=json.dumps(envelope,ensure_ascii=False,separators=(',',':'))
requests=[]
async def handler(request):
 requests.append({'method':request.method,'url':str(request.url),'json':json.loads(request.content)})
 return httpx.Response(200,content=raw_expected.encode(),headers={'content-type':'application/json'})
real_client=httpx.AsyncClient
p.httpx.AsyncClient=lambda **kwargs:real_client(**kwargs,transport=httpx.MockTransport(handler))
inputs=[encode(a),encode(translate(a,3,-2))];before=inputs.copy()
try:
 raw,spec=asyncio.run(p.OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30).analyze_video(SimpleNamespace(frames=inputs,manifest=[{'time_seconds':0},{'time_seconds':1}]),mode='realistic'))
finally:p.httpx.AsyncClient=real_client
check('one_httpx_request',len(requests)==1)
check('raw_http_body_preserved_exactly',raw==raw_expected)
check('technical_not_rewritten',spec.technical.camera_motion==content['camera_motion'] and spec.technical.subject_action==content['subject_action'])
request=requests[0];payload=request['json'];text=payload['messages'][-1]['content']
reg=json.loads(text.split('Measured image registration (not physical camera motion): ',1)[1].split('\nMeasured adjacent-frame',1)[0])
check('http_metadata_matches_recompute',reg==p.temporal_alignment_measurements(inputs))
check('one_sheet_one_post',request['method']=='POST' and len(payload['messages'][-1]['images'])==1)
check('video_schema_unchanged',payload['format']==p.VIDEO_SCHEMA)
check('http_source_immutable',inputs==before)
# Retain serialized request metadata without large image base64.
payload['messages'][-1]['images']=[{'base64_length':len(payload['messages'][-1]['images'][0])}]
evidence['request']=request
final=hashes();check('source_hashes_stable',initial==final)
output={'checks':checks,'count':len(checks),'passed':sum(c['pass'] for c in checks),'source_before':initial,'source_after':final,'evidence':evidence,'network':False,'model_calls':0,'new_media_decode':False,'http_transport':'httpx.MockTransport; one serialized Request; no socket/service'}
(OUT/'cpu-evidence.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':output['passed'],'count':output['count'],'hashes':final},indent=2))
