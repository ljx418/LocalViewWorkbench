"""Independent synthetic-only review. No services, processes, GPU or media decoder."""
from pathlib import Path
import sys, shutil, tempfile, types, hashlib, json, socket, subprocess, os, base64, ast, resource
from io import BytesIO
from PIL import Image
import httpx
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
TEMP=Path(tempfile.mkdtemp(prefix='lvw-independent-residual-'))
for name in ['provider.py','models.py','errors.py']:
    dest=TEMP/'lvw/backend/app'/name;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'lvw/backend/app'/name,dest)
(TEMP/'templates').mkdir();shutil.copy2(ROOT/'templates/analysis_system_zh.txt',TEMP/'templates/analysis_system_zh.txt')
sys.path.insert(0,str(TEMP/'lvw/backend'))
# The GPU/resource module is excluded: this review never executes its functions.
sys.modules['app.resources']=types.ModuleType('app.resources')
import app.provider as p
blocked=[]
def deny(*args,**kwargs):
    blocked.append('attempted_external_operation');raise AssertionError('external operation forbidden')
socket.socket=deny;socket.create_connection=deny;subprocess.Popen=deny;subprocess.run=deny;os.system=deny
results=[]
def check(name,condition,**detail):
    assert condition,(name,detail)
    results.append({'check':name,'pass':True,**detail})
def encode(im):
    b=BytesIO();im.save(b,format='PNG');return b.getvalue()
def sources(w,h,n):
    # Nonuniform edge/corner and interior markers; source identities differ everywhere.
    return [Image.frombytes('RGB',(w,h),bytes(v for y in range(h) for x in range(w) for v in ((x*7+i*47)%256,(y*11+i*61)%256,(x+y+i*79)%256))) for i in range(n)]
def decoded(ims):return types.SimpleNamespace(frames=[encode(x) for x in ims],manifest=[{'time_seconds':i*1.125+.25} for i in range(len(ims))])
for count in range(1,5):
    for w,h in [(19,13),(768,432),(432,768),(768,768),(768,1),(1,768)]:
        ims=sources(w,h,count);d=decoded(ims);before=list(d.frames)
        payload=p.build_temporal_sheet(d);sheet=Image.open(BytesIO(payload)).convert('RGB')
        cols=min(count,2);rows=(count+cols-1)//cols;sh=rows*256
        check('layout',sheet.size==(cols*384,sh+(256 if count>1 else 0)),count=count,source_size=[w,h],output_size=list(sheet.size))
        for i,im in enumerate(ims):
            reference=im.copy();reference.thumbnail((376,224),Image.Resampling.LANCZOS)
            x=(i%cols)*384+(384-reference.width)//2;y=(i//cols)*256+28+(224-reference.height)//2
            check('whole_source_thumbnail_pixels',sheet.crop((x,y,x+reference.width,y+reference.height)).tobytes()==reference.tobytes(),count=count,index=i,source_size=[w,h],thumbnail_size=list(reference.size))
        if count>1:
            rw=sheet.width//(count-1)
            for i in range(count-1):
                # Independent byte arithmetic; no ImageChops difference in oracle.
                ref=Image.frombytes('RGB',(w,h),bytes(abs(a-b) for a,b in zip(ims[i].tobytes(),ims[i+1].tobytes())))
                ref.thumbnail((rw-8,224),Image.Resampling.LANCZOS)
                x=i*rw+(rw-ref.width)//2;y=sh+28+(224-ref.height)//2
                check('absolute_rgb_residual_pixels',sheet.crop((x,y,x+ref.width,y+ref.height)).tobytes()==ref.tobytes(),count=count,pair=[i+1,i+2],source_size=[w,h])
        check('input_bytes_immutable',before==d.frames,count=count,source_size=[w,h])
        if (w,h)==(768,432):sheet.save(OUT/f'preview-{count}-source-panels.png')
for n,m in [(0,0),(5,5),(1,0)]:
    try:p.build_temporal_sheet(types.SimpleNamespace(frames=[encode(Image.new('RGB',(2,2)))]*n,manifest=[{'time_seconds':0}]*m))
    except p.AppError:check('invalid_count_or_manifest_rejected',True,frames=n,manifest=m)
    else:raise AssertionError('invalid accepted')
try:p.build_temporal_sheet(decoded([Image.new('RGB',(2,2)),Image.new('RGB',(3,2))]))
except p.AppError:check('size_mismatch_rejected',True)
else:raise AssertionError('mismatch accepted')
# Exact small-scale numeric oracle: 1 of 6 pixels changed, delta (12,24,36).
a=Image.new('RGB',(3,2));b=a.copy();b.putpixel((1,1),(12,24,36))
measure=p.temporal_pixel_measurements([encode(a),encode(b)])[0]
check('numeric_measurement',measure=={'from_frame':1,'to_frame':2,'changed_pixel_count':1,'frame_pixel_count':6,'different_pixel_percent':16.6667,'mean_absolute_rgb_delta':4.0},observed=measure)
check('static_measurement_zero',p.temporal_pixel_measurements([encode(a),encode(a)])[0]['changed_pixel_count']==0)
# Invoke actual analyze_video and _analyze_images with only an in-memory HTTP client.
calls=[]
content={'observations':['Synthetic patterned panels.'],'inferences':[],'unknowns':['Cause unknown.'],'prompt_zh':'合成图案。','prompt':'Synthetic pattern.','negative':'blur','tags':['pattern'],'camera_motion':'Unknown.','subject_action':'Unknown.'}
envelope={'done':True,'done_reason':'stop','message':{'content':json.dumps(content)}}
class MemoryClient:
    def __init__(self,**kw):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def post(self,url,*,json):
        calls.append({'url':url,'payload':json})
        return httpx.Response(200,json=envelope,request=httpx.Request('POST',url))
p.httpx.AsyncClient=MemoryClient
os.environ.pop('LVW_AUTHORIZATION_CHILD',None);os.environ.pop('LVW_REQUIRE_BUDGET',None)
d=decoded(sources(41,23,4))
ledger=OUT/'raw/production-ledger.jsonl'
ledger.unlink(missing_ok=True)
provider=p.OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30,ledger_path=ledger)
coro=provider.analyze_video(d,mode='realistic')
try:coro.send(None)
except StopIteration as done:raw,spec=done.value
else:raise AssertionError('unexpected external async wait')
wire=calls[0]['payload'];message=wire['messages'][-1]
check('one_request_one_wire_png',len(calls)==1 and len(message['images'])==1 and base64.b64decode(message['images'][0]).startswith(b'\x89PNG'))
check('all_source_time_metadata',all(str(x['time_seconds']) in message['content'] for x in d.manifest))
check('derived_not_source_prompt',all(s in message['content'] for s in ['DERIVED absolute RGB','not extra video frames','Actual populated SOURCE panel count: 4']))
check('fixed_options',wire['options']=={'num_ctx':4096,'num_predict':768,'temperature':0.2} and wire['keep_alive']==0 and wire['stream'] is False and wire['think'] is False)
check('raw_preserved',json.loads(raw)==envelope)
check('template_version',spec.template_version=='1.2.0' and p.VIDEO_PRESENTATION_VERSION=='temporal-sheet/2-residual')
events=[json.loads(line) for line in ledger.read_text().splitlines()]
check('ledger_source_and_wire_counts',events[0]['frame_count']==4 and events[0]['payload_image_count']==1 and events[0]['source_frame_hashes']==[hashlib.sha256(x).hexdigest() for x in d.frames])
check('no_external_attempts',not blocked)
(OUT/'raw/wire-request.json').write_text(json.dumps(calls,indent=2))
(OUT/'raw/check-results.json').write_text(json.dumps({'checks':results,'total':len(results),'source_sha256':hashlib.sha256((ROOT/'lvw/backend/app/provider.py').read_bytes()).hexdigest(),'snapshot_sha256':hashlib.sha256((TEMP/'lvw/backend/app/provider.py').read_bytes()).hexdigest(),'isolated_path':str(TEMP),'synthetic_only':True,'blocked_external_attempts':blocked,'process_maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'gpu_resource_module_stubbed':True},indent=2))
print(json.dumps({'checks_passed':len(results),'external_attempts':blocked,'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
