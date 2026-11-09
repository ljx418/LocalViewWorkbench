"""CPU only: retained PNG pixels, independent NumPy registration, hash fences.
Run python3 -B reports/unified-media/independent-live-13/recompute.py from package root.
No service, model, ffmpeg, network or source mutation.
"""
from pathlib import Path
from io import BytesIO
import ast, hashlib, json, subprocess, sqlite3
import numpy as np
from PIL import Image, ImageChops, ImageDraw
ROOT=Path.cwd(); OUT=ROOT/'reports/unified-media/independent-live-13'; LIVE=ROOT/'reports/unified-media/live-13'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
auth=read(LIVE/'authorization.json'); run=read(LIVE/'video-model-run.json')
result={'candidate':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), 'frames':[], 'binding_errors':[]}
for item in auth['frozen_files']+auth['samples']:
    p=ROOT/item['path']; actual=sha(p.read_bytes())
    if actual!=item['sha256']:result['binding_errors'].append({'path':item['path'],'actual':actual,'expected':item['sha256']})
for item in auth['frozen_files']:
    blob=subprocess.run(['git','show',auth['candidate_sha']+':'+item['path']],capture_output=True)
    if blob.returncode==0 and sha(blob.stdout)!=item['sha256']:result['binding_errors'].append({'candidate_blob_mismatch':item['path']})
result['harness_bound']=sha((ROOT/'reports/unified-media/live_checkpoint.py').read_bytes())==auth['harness_sha256']
result['program_bound']=sha((ROOT/auth['program']).read_bytes())==auth['program_sha256']
result['tools']={key:sha(Path(item['path']).read_bytes())==item['sha256'] for key,item in read(LIVE/'bindings.json').items()}
ims=[]; payload=[]
for n in range(4):
    p=ROOT/f'reports/unified-media/independent-live-03/frame-{n}.png'; im=Image.open(p).convert('RGB'); ims.append(im)
    ppm=f'P6\n{im.width} {im.height}\n255\n'.encode()+im.tobytes(); payload.append(ppm)
    result['frames'].append({'index':n,'retained_png_sha256':sha(p.read_bytes()),'ppm_sha256':sha(ppm),'exact_live_frame_match':sha(ppm)==run['frames'][n]['sha256'],'size':im.size})
def register(a,b):
    a=np.asarray(a,dtype=np.int16);b=np.asarray(b,dtype=np.int16);h,w=a.shape;r=10
    ref=a[r:h-r,r:w-r];scores=[]
    for dy in range(-r,r+1):
        for dx in range(-r,r+1):
            err=int(np.abs(ref-b[r-dy:h-r-dy,r-dx:w-r-dx]).sum())
            scores.append((err,dx*dx+dy*dy,dy,dx))
    e,_,dy,dx=min(scores); z=next(v[0] for v in scores if v[2:]==(0,0)); area=ref.size
    return {'offset':[dx,dy],'zero_error':round(z/area,6),'best_error':round(e/area,6),'reduction':round((z-e)/z,6) if z else 0,'ties':sum(v[0]==e for v in scores)}
components=[]
for im in ims:
    luma=im.convert('L');luma.thumbnail((128,128),Image.Resampling.LANCZOS)
    rgb=im.copy();rgb.thumbnail((128,128),Image.Resampling.LANCZOS);a=np.asarray(rgb,dtype=np.int16)
    # Pillow opponent operation truncates, then clips.
    channels=[Image.fromarray(np.clip(np.floor((a[:,:,i]-a[:,:,j])/2+128),0,255).astype('uint8')) for i,j in [(0,1),(1,2),(2,0)]]
    components.append([luma]+channels)
result['independent_alignment']=[]; result['pixel_differences']=[];result['landmarks']=[]
for i,im in enumerate(ims):
    a=np.asarray(im);red=(a[:,:,0]>200)&(a[:,:,1]<60)&(a[:,:,2]<60);ys,xs=np.nonzero(red)
    white=(a[:,:,0]>200)&(a[:,:,1]>200)&(a[:,:,2]>200)
    # Source row 50 is clear of red subject and horizontal grid lines.
    ids=np.flatnonzero(white[50]);groups=np.split(ids,np.flatnonzero(np.diff(ids)>1)+1)
    result['landmarks'].append({'frame':i+1,'red_bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'red_center':[float(xs.mean()),float(ys.mean())],'vertical_white_grid_centers_row50':[float(g.mean()) for g in groups if len(g)]})
for i in range(3):
    d=np.abs(np.asarray(ims[i],dtype=np.int16)-np.asarray(ims[i+1],dtype=np.int16));changed=int(np.any(d!=0,axis=2).sum())
    result['pixel_differences'].append({'from':i+1,'to':i+2,'changed':changed,'percent':round(100*changed/(ims[i].width*ims[i].height),4),'mean_rgb_delta':round(float(d.mean()),6)})
    result['independent_alignment'].append({name:register(a,b) for name,a,b in zip(['luma','R-G','G-B','B-R'],components[i],components[i+1])})
ledger=[json.loads(s) for s in (LIVE/'runtime-evidence/provider.jsonl').read_text().splitlines()]
calls=[s for s in ledger if s['event']=='provider_call_started']; video=next(s for s in calls if s.get('frame_count')==4)
result['alignment_matches_live']=[]
for actual,logged in zip(result['independent_alignment'],video['alignment_measurements']):
    checks=[actual['luma']['offset']==list(logged['next_to_previous_alignment_offset_px'].values()), actual['luma']['best_error']==logged['best_aligned_mean_luma_error']]
    for c in logged['colour_components']:
        v=actual[c['component']]; checks.extend([v['offset']==list(c['offset_px'].values()),v['zero_error']==c['zero_error'],v['best_error']==c['best_error'],round(100*v['reduction'],4)==c['error_reduction_percent']])
    result['alignment_matches_live'].append(all(checks))
# Rebuild only the inspected pure sheet builder via AST, without importing candidate module.
tree=ast.parse((ROOT/'lvw/backend/app/provider.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_temporal_sheet')
ns={'Image':Image,'ImageChops':ImageChops,'ImageDraw':ImageDraw,'BytesIO':BytesIO};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<inspected sheet function>','exec'),ns)
class Decoded:pass
decoded=Decoded();decoded.frames=payload;decoded.manifest=[{'time_seconds':n} for n in [1,3,5,7]]
sheet=ns['build_temporal_sheet'](decoded);(OUT/'rebuilt-sheet.png').write_bytes(sheet)
result['sheet_sha256']=sha(sheet);result['sheet_matches_live']=sha(sheet)==video['input_sha256']
result['provider_calls']=len(calls);result['lease_releases']=sum(s['event']=='lease_released' for s in ledger)
samples=[s for s in ledger if s['event']=='running_resource_sample'];result['peak_gpu_mib']=max(s['gpu_used_mib'] for s in samples);result['min_ram_mib']=min(s['available_ram_mib'] for s in samples)
result['api_original_pid_still_exists']=Path('/proc/3530826').exists()
result['run_state_exists']=(ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified/live-13').exists()
state=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified/live-13'
result['remaining_state_entries']=[str(p.relative_to(state)) for p in state.rglob('*')]
result['cpu_negative_checks']={}
rng=np.random.default_rng(37); a=rng.integers(0,256,(77,128),dtype=np.uint8); b=np.zeros_like(a);b[:,:-4]=a[:,4:]
result['cpu_negative_checks']['static_offset_zero']=register(Image.fromarray(a),Image.fromarray(a))['offset']==[0,0]
result['cpu_negative_checks']['synthetic_next_left_four_aligns_right_four']=register(Image.fromarray(a),Image.fromarray(b))['offset']==[4,0]
files=list((ROOT/'lvw/backend/app').glob('*.py'))+list((ROOT/'lvw/frontend/dist').rglob('*'))+[ROOT/'templates/analysis_system_zh.txt']
files += [ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge'/name for name in ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']]
digest=hashlib.sha256()
for p in sorted(x for x in files if x.is_file()):digest.update(str(p.relative_to(ROOT)).encode()+b'\0'+p.read_bytes()+b'\0')
result['recomputed_build_id']=digest.hexdigest();result['build_matches_live']=digest.hexdigest()==read(LIVE/'receipt.json')['source_build_id']
result['global_ledger_tables']=[]
db=Path('/mnt/c/workSpace/videoWorkLine/.lvw-runtime/lvw-prompt-service/program02.sqlite')
with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
    result['global_ledger_tables']=conn.execute("select name from sqlite_master where type='table'").fetchall()
    for table in ['runs','children','model_actions','events']:
        if (table,) in result['global_ledger_tables']:
            cols=[r[1] for r in conn.execute('pragma table_info('+table+')')]
            result['ledger_'+table+'_columns']=cols
            if 'run_id' in cols:result['ledger_'+table]=[dict(zip(cols,row)) for row in conn.execute('select * from '+table+' where run_id=?',('live-13',))]
            if 'run' in cols:result['ledger_'+table]=[dict(zip(cols,row)) for row in conn.execute('select * from '+table+' where run=?',('live-13',))]
    result['global_accounting']=list(conn.execute('select sum(calls),sum(checkpoint),sum(elapsed),sum(active) from children').fetchone())
result['raw_evidence_sha256']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in LIVE.rglob('*') if p.is_file()}
(OUT/'recomputed.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['raw_evidence_sha256','tools','frames','ledger_events']},indent=2))
