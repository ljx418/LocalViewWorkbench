"""Independent stdlib-only audit: git blobs, raw files, read-only SQLite; no product imports."""
import hashlib,json,sqlite3,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parent;L=R/'reports/unified-media/live-11'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(n):return json.loads((L/n).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
a=read('authorization.json');t=read('authorization.terminal.json');r=read('receipt.json');b=read('browser-result.json')
assert a['candidate_sha']=='d3b4ddde5311299083e398dfe08c1ab9c4e38ea8'
prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=R,text=True).strip()
def blob(p):return subprocess.run(['git','show',a['candidate_sha']+':'+prefix+p],cwd=R,capture_output=True)
checks=[]
for x in a['frozen_files']+a['samples']:
 p=R/x['path'];q=blob(x['path']); git_hash=hashlib.sha256(q.stdout).hexdigest() if q.returncode==0 else None
 if git_hash!=x['sha256'] and x['path'].endswith('.cmd') and q.returncode==0:git_hash=hashlib.sha256(q.stdout.replace(b'\n',b'\r\n')).hexdigest()
 checks.append({**x,'working_hash':sha(p),'candidate_git_hash':git_hash,'git_tracked':q.returncode==0})
assert all(c['git_tracked'] and c['candidate_git_hash']==c['sha256'] for c in checks) # Later working-tree correction must not alter reviewed source authority
assert sha(R/a['program'])==a['program_sha256'];grant=json.loads((R/a['program']).read_text());assert grant['decision']=='APPROVED'
assert sha(R/grant['request'])==grant['request_sha256']==a['program_request_sha256']
assert a['harness_sha256']==hashlib.sha256(blob('reports/unified-media/live_checkpoint.py').stdout).hexdigest()
for x in read('bindings.json').values():assert sha(x['path'])==x['sha256']
build_paths=[c['path'] for c in checks if (c['path'].startswith('lvw/backend/app/') and c['path'].endswith('.py')) or c['path'].startswith('lvw/frontend/dist/') or c['path']=='templates/analysis_system_zh.txt' or c['path'] in ['LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'+n for n in ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']]]
h=hashlib.sha256()
for rel in sorted(build_paths):h.update(rel.encode()+b'\0'+blob(rel).stdout+b'\0')
assert h.hexdigest()==r['source_build_id']==read('windows-health.json')['data']['build_id']
from PIL import Image,ImageChops,ImageDraw,ImageStat
from io import BytesIO
v=read('video-model-run.json');i=read('image-model-run.json');events=[json.loads(x) for x in (L/'runtime-evidence/provider.jsonl').read_text().splitlines()]
calls=[x for x in events if x['event']=='provider_call_started'];assert len(calls)==3 and [x['frame_count'] for x in calls]==[1,4,4]
assert all(x['payload_image_count']==1 for x in calls)
assert v['input_sha256']==a['samples'][1]['sha256'];assert i['input_sha256']==a['samples'][0]['sha256']
frames=[];images=[]
for n,f in enumerate(v['frames']):
 im=Image.open(R/f'reports/unified-media/independent-live-03/frame-{n}.png').convert('RGB');images.append(im)
 raw=f'P6\n{im.width} {im.height}\n255\n'.encode()+im.tobytes();assert hashlib.sha256(raw).hexdigest()==f['sha256']
 assert f['source_pts']*f['time_base_num']/f['time_base_den']==f['target_seconds']==1+2*n
 frames.append({**f,'recipe_source_n':12*f['target_seconds'],'crop_x':20+24*f['target_seconds'],'grid_phase_mod40':(20+24*f['target_seconds'])%40,'red_box_xywh':[135,65,50,60],'existing_png_ppm_rgb_hash_match':True})
assert len({x['grid_phase_mod40'] for x in frames})==4
# Independent construction from existing lossless PNG RGB, not video decode or product imports.
canvas=Image.new('RGB',(768,768),'#161b25');draw=ImageDraw.Draw(canvas)
def panel(im,x,y,w,label,outline):
 t=im.copy();t.thumbnail((w-8,224),Image.Resampling.LANCZOS);canvas.paste(t,(x+(w-t.width)//2,y+28+(224-t.height)//2));draw.rectangle((x,y,x+w-1,y+255),outline=outline,width=2);draw.text((x+8,y+8),label,fill='white')
for n,im in enumerate(images):panel(im,(n%2)*384,(n//2)*256,384,f'F{n+1} | {1+2*n:.3f}s','#8896aa')
measurements=[]
for n,(left,right) in enumerate(zip(images,images[1:]),1):
 d=ImageChops.difference(left,right);panel(d,(n-1)*256,512,256,f'D{n}->{n+1} DERIVED abs RGB','#ceaa68')
 rr,gg,bb=d.split();changed=left.width*left.height-ImageChops.lighter(ImageChops.lighter(rr,gg),bb).histogram()[0];total=left.width*left.height
 measurements.append(dict(from_frame=n,to_frame=n+1,changed_pixel_count=changed,frame_pixel_count=total,different_pixel_percent=round(100*changed/total,4),mean_absolute_rgb_delta=round(sum(ImageStat.Stat(d).mean)/3,6)))
buf=BytesIO();canvas.save(buf,format='PNG');wire_sha=hashlib.sha256(buf.getvalue()).hexdigest()
# Independent bytewise registration error oracle; no product function import.
alignment=[]
gray=[]
for im in images:
 g=im.convert('L');g.thumbnail((128,128),Image.Resampling.LANCZOS);gray.append(g)
for n,(left,right) in enumerate(zip(gray,gray[1:]),1):
 w,hh=left.size;radius=min(10,(min(w,hh)-1)//4);area=(w-2*radius)*(hh-2*radius)
 pp=list(left.getdata());nn=list(right.getdata());scores=[]
 for dy in range(-radius,radius+1):
  for dx in range(-radius,radius+1):
   error=sum(abs(pp[y*w+x]-nn[(y-dy)*w+x-dx]) for y in range(radius,hh-radius) for x in range(radius,w-radius))
   scores.append((error,dx*dx+dy*dy,dy,dx))
 best=min(scores);zero=next(x[0] for x in scores if x[2:]==(0,0))
 alignment.append({'from_frame':n,'to_frame':n+1,'usable':True,'analysis_size':[w,hh],'search_radius_px':radius,'next_to_previous_alignment_offset_px':{'x':best[3],'y':best[2]},'unaligned_mean_luma_error':round(zero/area,6),'best_aligned_mean_luma_error':round(best[0]/area,6),'relative_error_reduction':round((zero-best[0])/zero,6) if zero else 0,'equally_best_offsets':sum(x[0]==best[0] for x in scores)})
save('registration-recomputed.json',{'method':'independent bytewise exhaustive sum(abs(gray_previous-gray_next_shifted)) common central window; no product function import','measurements':alignment})
for c in calls[1:]:
 assert c['source_frame_hashes']==[f['sha256'] for f in frames] and c['presentation']=='temporal-sheet/3-alignment'
 assert c['input_sha256']==wire_sha and c['pixel_measurements']==measurements and c['alignment_measurements']==alignment
releases=[]
for c in calls:
 job=c['lease_job_id'];base=next(x['baseline'] for x in events if x['event']=='lease_acquired' and x['call_id']==job)
 assert base['gpu_free_mib']>=19047 and base['gpu_used_mib']<23552 and base['available_ram_mib']>=2048
 samples=[x for x in events if x['event']=='lease_release_sample' and x['lease_job_id']==job]
 assert len(samples)>=3 and all(x['inventory_empty'] and x['gpu_used_mib']<=base['gpu_used_mib']+1024 for x in samples[-3:])
 assert len([x for x in events if x['event']=='lease_released' and x['call_id']==job])==1
 releases.append(dict(job=job,baseline=base,release_last_three=samples[-3:]))
samples=[x for x in events if x['event']=='running_resource_sample'];peak=max(x['gpu_used_mib'] for x in samples);ram=min(x['available_ram_mib'] for x in samples);assert peak<23552 and ram>=2048
jobs=read('cleanup-job-terminals.json');assert len(jobs)==3
for run in (i,v):assert jobs[run['job_id']]['result_ref']==run['id'] and jobs[run['job_id']]['status']=='succeeded'
cancelled=[x for x in jobs.values() if x['status']=='cancelled'];assert len(cancelled)==1 and cancelled[0]['result_ref'] is None and cancelled[0]['resource_state']=='released' and cancelled[0]['cancel_epoch']==1
assert not any(x['event']=='provider_call_completed' and x['lease_job_id']==cancelled[0]['id'] for x in events)
image=read('image-draft.json');before=read('before-video-adopt.json');adopted=read('video-adopted.json');after=read('after-cancel.json');offline=read('offline-draft.json')
assert image['source']['type']=='model_adopted' and image['source']['model_run_id']==before['source']['model_run_id']==i['id']
assert adopted['source']['type']=='model_adopted' and adopted['source']['model_run_id']==after['source']['model_run_id']==offline['source']['model_run_id']==v['id']
assert adopted['source']['frames']==after['source']['frames']==v['frames'] and after['outputs']['natural_zh']=='AFTER_ADOPT_MANUAL_KEEP'
assert offline['outputs']['video_prompt']=='OFFLINE_EDIT_AND_EXPORT' and 'OFFLINE_EDIT_AND_EXPORT' in (L/'offline-draft.txt').read_text()
assert not read('runtime-stop.json')['ollama']['reachable'] and not read('cleanup-stop-response.json')['data']['ollama']['reachable']
assert read('negative-0.json')['error']['details']['subcode']=='VIDEO_DURATION_LIMIT' and read('negative-1.json')['error']['code']=='MEDIA_INVALID'
owner=json.loads(next((L/'runtime-evidence').glob('*.owner.json')).read_text());assert owner['state']=='exited' and not owner['listener_owned']
native='\n'.join(p.read_text(errors='replace') for p in (L/'runtime-evidence').glob('*.stderr.log'));assert 'OLLAMA_NO_CLOUD:true' in native and 'OLLAMA_HOST:http://127.0.0.1:11434' in native
launch=(L/'launcher.log').read_text();assert f"Finished server process [{r['api_process']['pid']}]" in launch and 'Run-owned temporary files were removed' in launch
assert b['browser_closed'] and not b['external_requests'] and not b['page_errors'];assert all(r[k] for k in ['run_root_removed','api_listener_absent','ollama_listener_absent']) and t['status']=='EXPIRED_REAL_CHECKPOINT_COMPLETE_INDEPENDENT_REVIEW_PENDING'
model=read('actual-model-identity.json');assert model['name']=='gemma4:26b' and len(model['digest'])==64
content=json.loads(json.loads(v['raw_response'])['message']['content'])
# Terminal semantic evaluation appended after original output is available.
semantic={'decision':'PENDING_MANUAL_CONTENT_REVIEW','frames':frames,'wire_png_sha256':wire_sha,'raw_content':content,'alignment_measurements_independent':alignment,'derived_D_not_extra_frames':True,'measurements_independently_recomputed':measurements}
save('semantic-review.json',semantic)
db=sqlite3.connect('file:'+a['budget_ledger']+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;rows=[dict(x) for x in db.execute('select * from children')];db.close();row=next(x for x in rows if x['run']=='live-11')
assert row['calls']==3 and row['checkpoint']==1 and row['active']==0 and row['elapsed']<=1800 and row['cap']==8 and row['seconds']==1800
assert row['child_hash']==sha(L/'authorization.json') and row['bindings_hash']==sha(L/'bindings.json')
carry=json.loads((R/'reports/unified-media/complete03-ledger-carry-forward.json').read_text())['rows']
for old in carry:assert next(x for x in rows if x['run']==old['run'])==old
actual={'model_actions':sum(x['calls'] for x in rows),'effective_full_checkpoints':sum(x['checkpoint'] for x in rows),'production_seconds':sum(x['elapsed'] for x in rows if not x['cpu'])}
reserved={'model_actions':sum(x['cap'] if x['active'] else x['calls'] for x in rows),'effective_full_checkpoints':sum(x['full'] if x['active'] else x['checkpoint'] for x in rows),'production_seconds':sum(x['seconds'] if x['active'] else x['elapsed'] for x in rows if not x['cpu'])}
assert reserved['model_actions']<=1024 and reserved['effective_full_checkpoints']<=24 and reserved['production_seconds']<=172800
save('recomputed.json',{'scope':'live-11','frozen_checks':checks,'build_id':h.hexdigest(),'calls':calls,'release_checks':releases,'peak_gpu_mib':peak,'minimum_ram_mib':ram,'native_owner':owner,'model_identity':model,'live10_ledger':row,'ledger_rows':rows,'global_actual':actual,'global_including_reservations':reserved,'historical_carry_rows_unchanged':True,'semantic_result':semantic['decision'],'no_new_media_probe_decode_service_model_browser':True})
paths=[p for p in L.rglob('*') if p.is_file()]+[R/a['program'],R/grant['request'],R/'tools/v0_s2_fixtures.py',R/'reports/unified-media/complete03-ledger-carry-forward.json']+[R/f'reports/unified-media/independent-live-03/frame-{n}.png' for n in range(4)]
(O/'raw-hashes.sha256').write_text(''.join(sha(p)+'  '+str(p.relative_to(R))+'\n' for p in sorted(paths)))
print(json.dumps({'decision':'CPU_EVIDENCE_RECOMPUTED_SEMANTICS_PENDING','calls':3,'seconds':row['elapsed'],'global_actual':actual,'peak_gpu':peak,'minimum_ram':ram,'wire_sha':wire_sha,'source_bindings':len(checks),'cleanup':'PASS'}))
