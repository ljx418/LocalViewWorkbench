"""Independent CPU/synthetic registration oracle + production mock boundary audit."""
import asyncio, base64, hashlib, importlib, io, json, os, random, socket, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace, ModuleType
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
# Fail closed: these tests cannot launch processes or establish network sockets.
def forbidden(*a,**kw):raise AssertionError('network/process execution prohibited in independent CPU review')
socket.socket.connect=forbidden
subprocess.Popen=forbidden
os.environ.pop('LVW_AUTHORIZATION_CHILD',None)
os.environ.pop('LVW_REQUIRE_BUDGET',None)
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'lvw/backend'))
from app import provider as p

def enc(im):
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def oracle(a,b):
    # Pure list/int oracle. No ImageStat, ImageChops, crops or implementation helper.
    aa=Image.open(io.BytesIO(a)).convert('L');bb=Image.open(io.BytesIO(b)).convert('L')
    aa.thumbnail((128,128),Image.Resampling.LANCZOS);bb.thumbnail((128,128),Image.Resampling.LANCZOS)
    w,h=aa.size;r=min(10,(min(w,h)-1)//4)
    if r<1:return {'usable':False,'reason':'analysis_too_narrow'}
    A=list(aa.getdata());B=list(bb.getdata());points=[(x,y) for y in range(r,h-r) for x in range(r,w-r)]
    if len({A[y*w+x] for x,y in points})==1:return {'usable':False,'reason':'reference_has_no_texture'}
    costs={}
    for sx in range(-r,r+1):
        for sy in range(-r,r+1):
            # Move pixel (x-sx,y-sy) in next to fixed coordinate (x,y) in prev.
            costs[sx,sy]=sum(abs(A[y*w+x]-B[(y-sy)*w+x-sx]) for x,y in points)
    sx,sy=min(costs,key=lambda k:(costs[k],k[0]**2+k[1]**2,k[1],k[0]))
    e0=costs[0,0];eb=costs[sx,sy]
    return {'usable':True,'analysis_size':[w,h],'search_radius_px':r,
      'next_to_previous_alignment_offset_px':{'x':sx,'y':sy},
      'unaligned_mean_luma_error':round(e0/len(points),6),'best_aligned_mean_luma_error':round(eb/len(points),6),
      'relative_error_reduction':round((e0-eb)/e0,6) if e0 else 0,
      'equally_best_offsets':sum(v==eb for v in costs.values())}

def check(name,a,b):
    before=(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest())
    got=p.temporal_alignment_measurements([a,b])[0]
    expected=oracle(a,b)
    assert {k:v for k,v in got.items() if k not in ('from_frame','to_frame')}==expected,(name,got,expected)
    assert before==(hashlib.sha256(a).hexdigest(),hashlib.sha256(b).hexdigest())
    results.append({'case':name,'result':got})
    return got
rng=random.Random(902117)
def noise(w,h):
    im=Image.new('L',(w,h));im.putdata([rng.randrange(256) for _ in range(w*h)]);return im

def move(im,dx,dy):
    # Independent spatial shift with zero border; never wrap.
    dst=Image.new(im.mode,im.size);dst.paste(im,(dx,dy));return dst
results=[]
for dx,dy in [(7,-4),(-8,5),(0,9),(10,-10),(-10,10)]:
    im=noise(56,48);g=check(f'translation_{dx}_{dy}',enc(im),enc(move(im,dx,dy)))
    assert g['next_to_previous_alignment_offset_px']=={'x':-dx,'y':-dy} and g['best_aligned_mean_luma_error']==0
im=noise(45,43);check('static',enc(im),enc(im))
for w,h in [(1,128),(4,90),(5,5),(13,9),(64,11),(29,37)]:
    im=noise(w,h);check(f'boundary_{w}_{h}',enc(im),enc(move(im,1,1)))
for i in range(7):
    w,h=rng.randrange(8,50),rng.randrange(8,50);check(f'independent_noise_{i}',enc(noise(w,h)),enc(noise(w,h)))
im=noise(31,27); altered=im.copy()
for x in range(31):altered.putpixel((x,0),255-altered.getpixel((x,0)))
g=check('change_only_outside_reference_window',enc(im),enc(altered));assert g['unaligned_mean_luma_error']==0
im=Image.new('L',(48,40));im.putdata([255 if x%6<3 else 0 for y in range(40) for x in range(48)])
g=check('repeated_stripes',enc(im),enc(move(im,2,0)));assert g['equally_best_offsets']>1
blank=enc(Image.new('RGB',(30,30),'red'));check('no_texture',blank,blank)
# RGB red and dark green map to the same integer luma in Pillow (76).
a=Image.new('RGB',(30,30));a.putdata([(255,0,0) if x%2 else (0,130,0) for y in range(30) for x in range(30)])
b=move(a,1,0);g=check('isoluminant_chromatic_structure',enc(a),enc(b));assert not g['usable']
# Reducing a 768 square to 128 yields a bounded analysis raster.
im=noise(768,768);payloads=[enc(im)]*4
t0=time.perf_counter();perf=p.temporal_alignment_measurements(payloads);elapsed=time.perf_counter()-t0
assert len(perf)==3 and all(x['analysis_size']==[128,128] for x in perf)
assert p.temporal_alignment_measurements([])==[] and p.temporal_alignment_measurements([blank])==[]
try:p.temporal_alignment_measurements([blank,enc(Image.new('L',(29,30)))])
except p.AppError as e:assert e.code=='PARSE_PARTIAL'
else:raise AssertionError('dimension mismatch accepted')

async def boundary():
    import httpx
    import types
    calls=[];debits=[];events=[]
    content={'observations':['Synthetic pattern changes.'],'inferences':[],'unknowns':['Motion cause is unknown.'],
      'prompt_zh':'测试图像','prompt':'Synthetic pattern','negative':'text','tags':['pattern'],
      'camera_motion':'Unknown.','subject_action':'Unknown.'}
    envelope={'done':True,'done_reason':'stop','message':{'content':json.dumps(content)}}
    raw=json.dumps(envelope)
    original_client=httpx.AsyncClient
    async def handler(request):
        assert len(debits)==1 and len(calls)==0
        calls.append(json.loads(request.content));return httpx.Response(200,content=raw)
    p.httpx.AsyncClient=lambda **kw:original_client(**kw,transport=httpx.MockTransport(handler))
    fake=ModuleType('tools.local_program_authority');fake.model_action=lambda child:debits.append(child)
    tools_package=ModuleType('tools');tools_package.__path__=[]
    sys.modules['tools']=tools_package;sys.modules['tools.local_program_authority']=fake
    os.environ['LVW_REQUIRE_BUDGET']='1';os.environ['LVW_AUTHORIZATION_CHILD']='independent-fake-child'
    frames=[enc(move(im,dx,dy)) for dx,dy in [(0,0),(1,2),(-2,3),(3,-1)]]
    manifest=[{'time_seconds':v,'frame_id':f'f{i}','pts':17+i*31} for i,v in enumerate([.25,1.5,2.75,4.0])]
    before=json.dumps(manifest,sort_keys=True)
    decoded=SimpleNamespace(frames=tuple(frames),manifest=manifest)
    obj=p.OllamaProvider('http://127.0.0.1:11434/api/chat','synthetic-review',30)
    # Memory collector: no production or real authority ledger is touched.
    obj._record=lambda event,call_id,**fields:events.append({'event':event,'call_id':call_id,**fields})
    returned,spec=await obj.analyze_video(decoded,mode='realistic')
    assert returned==raw and spec.template_version=='1.3.0'
    assert json.dumps(manifest,sort_keys=True)==before and tuple(frames)==decoded.frames
    assert len(calls)==len(debits)==1 and len(events)==2
    req=calls[0];msg=req['messages'][-1];start=events[0]
    assert len(msg['images'])==1 and req['format']==p.VIDEO_SCHEMA
    assert start['source_frame_hashes']==[hashlib.sha256(f).hexdigest() for f in frames]
    assert start['alignment_measurements']==p.temporal_alignment_measurements(frames)
    assert start['pixel_measurements']==p.temporal_pixel_measurements(frames)
    assert start['presentation']==p.VIDEO_PRESENTATION_VERSION
    assert start['frame_count']==4 and start['payload_image_count']==1
    sheet=base64.b64decode(msg['images'][0]);assert hashlib.sha256(sheet).hexdigest()==start['input_sha256']
    assert Image.open(io.BytesIO(sheet)).size==(768,768)
    measurements=json.loads(msg['content'].split('Measured image registration (not physical camera motion): ')[1].split('\nMeasured adjacent-frame')[0])
    assert measurements==start['alignment_measurements']
    assert all(str(v) in msg['content'] for v in [.25,1.5,2.75,4.0])
    assert 'repeated patterns can alias' in msg['content']
    # Raw response has untouched camera/action original text, separate parsed fields.
    assert json.loads(returned)['message']['content']==envelope['message']['content']
    return {'calls':len(calls),'debits':debits,'events':events,'raw_exact':True,'manifest_unchanged':True,'sheet_size':[768,768]}
# Use small pattern for production wiring CPU audit.
im=noise(56,48)
wiring=asyncio.run(boundary())
output={'oracle_cases':len(results),'cases':results,'max_analysis_4frame_seconds':elapsed,'production_mock':wiring,
 'guards':'socket.connect and subprocess.Popen fail closed; no services/model/media decode/GPU/authority ledger',
 'source_sha256':hashlib.sha256((ROOT/'lvw/backend/app/provider.py').read_bytes()).hexdigest()}
(OUT/'raw.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({'oracle_cases':len(results),'production_mock_calls':wiring['calls'],'four_768_frames_seconds':elapsed,'result':'PASS'}))
