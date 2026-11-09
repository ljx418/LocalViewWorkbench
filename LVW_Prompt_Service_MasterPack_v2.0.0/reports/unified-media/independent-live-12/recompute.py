"""Read-only live12 audit. CPU/image/gitblob/SQLite only; no probes or services."""
from pathlib import Path
from io import BytesIO
import json,hashlib,subprocess,sqlite3,sys
from PIL import Image,ImageChops
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
LIVE=ROOT/'reports/unified-media/live-12'
sha=lambda x:hashlib.sha256(x).hexdigest()
load=lambda p:json.loads(p.read_text())
a=load(LIVE/'authorization.json');r=load(LIVE/'receipt.json');b=load(LIVE/'browser-result.json')
v=load(LIVE/'video-model-run.json');im=load(LIVE/'image-model-run.json')
events=[json.loads(x) for x in (LIVE/'runtime-evidence/provider.jsonl').read_text().splitlines()]
calls=[x for x in events if x['event']=='provider_call_started'];assert len(calls)==3
vc=next(x for x in calls if x['lease_job_id']==v['job_id'])
prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=ROOT,text=True).strip()
blob=lambda p:subprocess.check_output(['git','show',a['candidate_sha']+':'+prefix+p],cwd=ROOT)
frozen=[{'path':x['path'],'matches_candidate':sha(blob(x['path']))==x['sha256'] or (x['path']=='START_LVW.cmd' and blob(x['path']).replace(b'\r\n',b'\n')==(ROOT/x['path']).read_bytes().replace(b'\r\n',b'\n')),'matches_disk':sha((ROOT/x['path']).read_bytes())==x['sha256']} for x in a['frozen_files']]
assert all(x['matches_candidate'] and x['matches_disk'] for x in frozen)
samples=[{'path':x['path'],'sha_matches':sha((ROOT/x['path']).read_bytes())==x['sha256']} for x in a['samples']];assert all(x['sha_matches'] for x in samples)
rawhash={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(LIVE.rglob('*')) if p.is_file()}
(OUT/'raw-hashes.json').write_text(json.dumps(rawhash,indent=2)+'\n')
# Reconstruct the exact PPM payloads from existing lossless PNG pixels. No video decode.
images=[];payloads=[];geometry=[]
for i,f in enumerate(v['frames']):
 p=ROOT/f'reports/unified-media/independent-live-03/frame-{i}.png';image=Image.open(p).convert('RGB');images.append(image)
 stream=BytesIO();image.save(stream,format='PPM');payload=stream.getvalue();payloads.append(payload);assert sha(payload)==f['sha256']
 red=[(x,y) for y in range(image.height) for x in range(image.width) if (lambda c:c[0]>180 and c[1]<70 and c[2]<70)(image.getpixel((x,y)))]
 bright=[x for x in range(image.width) if min(image.getpixel((x,20)))>160]
 groups=[]
 for x in bright:
  if not groups or x>groups[-1][-1]+1:groups.append([x])
  else:groups[-1].append(x)
 geometry.append({'png_path':str(p.relative_to(ROOT)),'png_sha256':sha(p.read_bytes()),'reconstructed_ppm_sha256':sha(payload),'red_bbox':[min(x for x,y in red),min(y for x,y in red),max(x for x,y in red),max(y for x,y in red)],'vertical_grid_x_at_y20':[round(sum(g)/len(g),3) for g in groups],'pts_seconds':f['source_pts']*f['time_base_num']/f['time_base_den']})
# Independently calculate all integer scores on a common window.
metrics=[];pixels=[]
for index,(left,right) in enumerate(zip(images,images[1:]),1):
 diff=ImageChops.difference(left,right);values=list(diff.getdata());changed=sum(any(v) for v in values)
 pixels.append({'from_frame':index,'to_frame':index+1,'changed_pixel_count':changed,'frame_pixel_count':len(values),'different_pixel_percent':round(changed*100/len(values),4),'mean_absolute_rgb_delta':round(sum(sum(v) for v in values)/(3*len(values)),6)})
 p=left.convert('L');n=right.convert('L');p.thumbnail((128,128),Image.Resampling.LANCZOS);n.thumbnail((128,128),Image.Resampling.LANCZOS)
 w,h=p.size;rad=min(10,(min(w,h)-1)//4);window=(rad,rad,w-rad,h-rad);ref=p.crop(window);scores=[]
 for dy in range(-rad,rad+1):
  for dx in range(-rad,rad+1):
   shifted=n.crop((rad-dx,rad-dy,w-rad-dx,h-rad-dy));hist=ImageChops.difference(ref,shifted).histogram();score=sum(i*count for i,count in enumerate(hist));scores.append((score,dx*dx+dy*dy,dy,dx))
 best=min(scores);base=next(x[0] for x in scores if x[2:]==(0,0));area=(w-2*rad)*(h-2*rad)
 metrics.append({'from_frame':index,'to_frame':index+1,'usable':True,'analysis_size':[w,h],'search_radius_px':rad,'next_to_previous_alignment_offset_px':{'x':best[3],'y':best[2]},'unaligned_mean_luma_error':round(base/area,6),'best_aligned_mean_luma_error':round(best[0]/area,6),'relative_error_reduction':round((base-best[0])/base,6) if base else 0,'equally_best_offsets':sum(x[0]==best[0] for x in scores)})
assert metrics==vc['alignment_measurements'];assert pixels==vc['pixel_measurements']
assert vc['source_frame_hashes']==[f['sha256'] for f in v['frames']]
# Execute only the candidate's pure image sheet builder; CPU oracle above was independent.
sys.path.insert(0,str(OUT/'candidate-source/lvw/backend'))
from app.provider import build_temporal_sheet,VIDEO_TEMPLATE_SHA256
from types import SimpleNamespace
sheet=build_temporal_sheet(SimpleNamespace(frames=payloads,manifest=[{'time_seconds':x['pts_seconds']} for x in geometry]));assert sha(sheet)==vc['input_sha256']
assert v['template_sha256']==VIDEO_TEMPLATE_SHA256
(OUT/'reconstructed-live12-sheet.png').write_bytes(sheet)
raw=load(LIVE/'video-model-run.json')['raw_response'];envelope=json.loads(raw);content=json.loads(envelope['message']['content'])
assert envelope['done'] is True and envelope['done_reason']=='stop'
assert content['observations']==v['parsed_spec']['domains']['observation'] and content['inferences']==v['parsed_spec']['domains']['inference']
assert content['camera_motion']==v['parsed_spec']['technical']['camera_motion'] and content['subject_action']==v['parsed_spec']['technical']['subject_action']
# Join exact export ownership and cancelled terminal.
drafts={name:load(LIVE/(name+'.json')) for name in ['image-draft','before-video-adopt','video-adopted','after-cancel','offline-draft']}
assert drafts['before-video-adopt']['source']['model_run_id']==im['id']
assert drafts['video-adopted']['source']['model_run_id']==v['id']
assert drafts['after-cancel']['source']['model_run_id']==v['id'] and drafts['after-cancel']['outputs']['natural_zh']=='AFTER_ADOPT_MANUAL_KEEP'
assert drafts['offline-draft']['outputs']['video_prompt']=='OFFLINE_EDIT_AND_EXPORT'
assert 'OFFLINE_EDIT_AND_EXPORT' in (LIVE/'offline-draft.txt').read_text()
jobs=load(LIVE/'cleanup-job-terminals.json');assert len(jobs)==3 and all(j['resource_state']=='released' for j in jobs.values())
cancel=[j for j in jobs.values() if j['status']=='cancelled'];assert len(cancel)==1 and cancel[0]['result_ref'] is None
assert len([x for x in calls if x['lease_job_id']==cancel[0]['id']])==1
releases=[]
for acquired in (x for x in events if x['event']=='lease_acquired'):
 job=acquired['call_id'];released=next(x for x in events if x['event']=='lease_released' and x['call_id']==job)
 rows=[x for x in events if x['event']=='lease_release_sample' and x['call_id']==job and x['time_ns']<released['time_ns']]
 assert len(rows)>=3 and all(x['inventory_empty'] and x['gpu_used_mib']<=acquired['baseline']['gpu_used_mib']+1024 for x in rows[-3:])
 releases.append({'job_id':job,'samples':len(rows),'last_three_proven':True,'seconds_to_release':round((released['time_ns']-rows[0]['time_ns'])/1e9,3)})
samples_running=[x for x in events if x['event']=='running_resource_sample'];peak=max(x['gpu_used_mib'] for x in samples_running);ram=min(x['available_ram_mib'] for x in samples_running);assert peak<23552 and ram>=2048
owners=[load(p) for p in (LIVE/'runtime-evidence').glob('*.owner.json')];assert len(owners)==1;owner=owners[0];assert owner['state']=='exited' and owner['listener_owned'] is False and owner['pid']==load(LIVE/'runtime-start.json')['ollama']['pid']
assert owner['nonce'] in next((LIVE/'runtime-evidence').glob('*.owner.json')).name and owner['birth_ticks']>0
logs='\n'.join(p.read_text(errors='replace') for p in (LIVE/'runtime-evidence').glob('*.stderr.log'));assert 'OLLAMA_NO_CLOUD:true' in logs and '127.0.0.1:11434' in logs
assert b['browser_closed'] and not b['external_requests'] and not b['page_errors']
assert r['run_root_removed'] and r['api_listener_absent'] and r['ollama_listener_absent']
assert 'Finished server process ['+str(r['api_process']['pid'])+']' in (LIVE/'launcher.log').read_text()
assert 'Run-owned temporary files were removed' in (LIVE/'launcher.log').read_text()
# Read-only /proc identity and listening socket tables, no connect or runtime query.
pidpath=Path('/proc')/str(r['api_process']['pid'])/'stat';api_original_absent=not pidpath.exists() or pidpath.read_text().split()[21]!=r['api_process']['birth'];assert api_original_absent
ports=[]
for p in [Path('/proc/net/tcp'),Path('/proc/net/tcp6')]:
 for line in p.read_text().splitlines()[1:]:
  col=line.split()
  if col[3]=='0A' and int(col[1].split(':')[1],16) in (18780,11434):ports.append(col[1])
assert not ports
bindings=load(LIVE/'bindings.json');tool_checks=[]
for name,value in bindings.items():
 path=Path(value['path']);tool_checks.append({'name':name,'path':str(path),'sha_matches':sha(path.read_bytes())==value['sha256']})
assert all(x['sha_matches'] for x in tool_checks)
conn=sqlite3.connect('file:'+a['budget_ledger']+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
child=dict(conn.execute('select * from children where run=?',('live-12',)).fetchone());total=dict(conn.execute('select sum(calls) model_actions,sum(checkpoint) effective_full_checkpoints,sum(elapsed) production_seconds,sum(active) active_children from children').fetchone());conn.close()
assert child['calls']==len(calls)==3 and child['checkpoint']==1 and child['active']==0 and child['elapsed']==56
assert child['child_hash']==sha((LIVE/'authorization.json').read_bytes()) and child['bindings_hash']==sha((LIVE/'bindings.json').read_bytes())
assert total['model_actions']<=1024 and total['effective_full_checkpoints']<=24 and total['production_seconds']<=172800
assert total['active_children']==0
terminal=load(LIVE/'authorization.terminal.json');assert terminal['status']!='ACTIVE_ONE_SHOT'
result={'candidate_sha':a['candidate_sha'],'frozen_files':frozen,'samples':samples,'tool_bindings':tool_checks,'model_identity':load(LIVE/'actual-model-identity.json'),'model_calls':len(calls),'completed_calls':sum(x['event']=='provider_call_completed' for x in events),'cancelled_attempt_count':len(cancel),'leases':releases,'peak_gpu_mib':peak,'minimum_ram_mib':ram,'owner':owner,'api_original_absent':api_original_absent,'listeners_absent_proc':True,'budget_child':child,'budget_global':total,'geometry':geometry,'pixel_measurements':pixels,'alignment_measurements':metrics,'sheet_sha256':sha(sheet),'raw_model_content':content,'raw_response_sha256':sha(raw.encode()),'exports_source_verified':True,'raw_artifact_count':len(rawhash),'cpu_results':(OUT/'cpu-results.txt').read_text()}
(OUT/'recomputed.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:result[k] for k in ['model_calls','completed_calls','peak_gpu_mib','minimum_ram_mib','budget_global','geometry']},ensure_ascii=False,indent=2))
