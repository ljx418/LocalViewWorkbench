"""Independent stdlib-only recomputation; never imports production/harness code."""
import hashlib,json,sqlite3,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
LIVE=ROOT/'reports/unified-media/live-07'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def read(n):return json.loads((LIVE/n).read_text())
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
a=read('authorization.json');t=read('authorization.terminal.json');v=read('video-model-run.json');i=read('image-model-run.json')
assert a['candidate_sha']=='d9759decaa760eb81479db5434ff9206b18b3327'
# The working tree may now contain a separate authorized correction; candidate git blobs are authoritative.
PREFIX=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=ROOT,text=True).strip()
def blob(path):return subprocess.check_output(['git','show',a['candidate_sha']+':'+PREFIX+path],cwd=ROOT)
def frozen_bytes(path):
 q=subprocess.run(['git','show',a['candidate_sha']+':'+PREFIX+path],cwd=ROOT,capture_output=True)
 if q.returncode==0:
  expected=next((x['sha256'] for x in a['frozen_files'] if x['path']==path),None)
  if path.endswith('.cmd') and hashlib.sha256(q.stdout).hexdigest()!=expected and hashlib.sha256(q.stdout.replace(b'\n',b'\r\n')).hexdigest()==expected:return q.stdout.replace(b'\n',b'\r\n')
  return q.stdout
 return (ROOT/path).read_bytes()
checks=[]
for item in a['frozen_files']+a['samples']:
 p=ROOT/item['path'];actual=hashlib.sha256(frozen_bytes(item['path'])).hexdigest();checks.append(dict(item,actual_sha256=actual,match=actual==item['sha256']))
assert all(x['match'] for x in checks), [x for x in checks if not x['match']]
assert sha(ROOT/a['program'])==a['program_sha256']
assert sha(ROOT/'reports/authorization-program-v1-local-02.request.json')==a['program_request_sha256']
assert hashlib.sha256(blob('reports/unified-media/live_checkpoint.py')).hexdigest()==a['harness_sha256']
for item in read('bindings.json').values():assert sha(Path(item['path']))==item['sha256']
# Every tracked production/frozen path is compared with the specified candidate, where tracked.
tracked=[]
for item in a['frozen_files']:
 q=subprocess.run(['git','show',a['candidate_sha']+':'+PREFIX+item['path']],cwd=ROOT,capture_output=True)
 if q.returncode==0:
  ok=hashlib.sha256(frozen_bytes(item['path'])).hexdigest()==item['sha256'];tracked.append({'path':item['path'],'matches_candidate':ok});assert ok
files=list((ROOT/'lvw/backend/app').glob('*.py'))+list((ROOT/'lvw/frontend/dist').rglob('*'))+[ROOT/'templates/analysis_system_zh.txt']
files += [ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge'/n for n in ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']]
h=hashlib.sha256()
for p in sorted(x for x in files if x.is_file()):h.update(str(p.relative_to(ROOT)).encode()+b'\0'+frozen_bytes(str(p.relative_to(ROOT)))+b'\0')
assert h.hexdigest()==read('windows-health.json')['data']['build_id']
frames=[]
for n,f in enumerate(v['frames']):
 p=ROOT/f'reports/unified-media/independent-live-03/frame-{n}.png'
 stored=json.loads((ROOT/'reports/unified-media/independent-live-03/independent-decoder-recompute.json').read_text())
 assert stored['source_sha256']==v['input_sha256']
 assert stored['frames'][n]['sha256']==f['sha256']
 assert stored['frames'][n]['pts']==f['source_pts']
 assert f['source_pts']*f['time_base_num']/f['time_base_den']==f['target_seconds']==1+2*n
 # Recipe crop x=20+2*n at 12fps; grid period 40. Red box is applied AFTER crop.
 source_n=int(f['target_seconds']*12);crop_x=20+2*source_n
 frames.append({'frame':n+1,'seconds':f['target_seconds'],'existing_png':str(p.relative_to(ROOT)),'source_frame_sha256':f['sha256'],'visualization_png_sha256':sha(p),'recipe_frame_n':source_n,'crop_x':crop_x,'grid_phase_mod40':crop_x%40,'red_box_xywh':[135,65,50,60]})
assert len({x['source_frame_sha256'] for x in frames})==4
assert len({x['grid_phase_mod40'] for x in frames})==4
ledger=[json.loads(s) for s in (LIVE/'runtime-evidence/provider.jsonl').read_text().splitlines()]
calls=[r for r in ledger if r['event']=='provider_call_started'];assert len(calls)==3
assert [r['frame_count'] for r in calls]==[1,4,4]
assert calls[1]['source_frame_hashes']==[f['sha256'] for f in v['frames']]
for r in calls[1:]:assert r['payload_image_count']==1 and r['presentation']=='temporal-sheet/1'
releases=[]
for job in {r['lease_job_id'] for r in calls}:
 base=next(r['baseline'] for r in ledger if r['event']=='lease_acquired' and r['lease_job_id']==job)
 samples=[r for r in ledger if r['event']=='lease_release_sample' and r['lease_job_id']==job]
 assert len(samples)>=3 and all(r['inventory_empty'] and r['gpu_used_mib']<=base['gpu_used_mib']+1024 for r in samples[-3:])
 assert len([r for r in ledger if r['event']=='lease_released' and r['call_id']==job])==1
 releases.append({'job':job,'baseline':base,'samples':samples})
samples=[r for r in ledger if r['event']=='running_resource_sample']
peak=max(r['gpu_used_mib'] for r in samples);ram=min(r['available_ram_mib'] for r in samples)
assert peak<23552 and ram>=2048
jobs=read('cleanup-job-terminals.json');cancel=[r for r in jobs.values() if r['status']=='cancelled'];assert len(cancel)==1
assert cancel[0]['result_ref'] is None and cancel[0]['resource_state']=='released'
after=read('after-cancel.json');adopted=read('video-adopted.json');before=read('before-video-adopt.json');image=read('image-draft.json');offline=read('offline-draft.json')
assert before['source']['model_run_id']==i['id']==image['source']['model_run_id']
assert adopted['source']['model_run_id']==v['id']==after['source']['model_run_id']==offline['source']['model_run_id']
assert after['outputs']['natural_zh']=='AFTER_ADOPT_MANUAL_KEEP'
assert offline['outputs']['video_prompt']=='OFFLINE_EDIT_AND_EXPORT'
assert 'OFFLINE_EDIT_AND_EXPORT' in (LIVE/'offline-draft.txt').read_text()
assert not read('runtime-stop.json')['ollama']['reachable']
owner=json.loads(next((LIVE/'runtime-evidence').glob('*.owner.json')).read_text());assert owner['state']=='exited' and owner['listener_owned'] is False
native='\n'.join(p.read_text(errors='replace') for p in (LIVE/'runtime-evidence').glob('*.stderr.log'))
assert 'OLLAMA_NO_CLOUD:true' in native and 'OLLAMA_HOST:http://127.0.0.1:11434' in native
launch=(LIVE/'launcher.log').read_text();assert 'Finished server process [2327292]' in launch and 'Run-owned temporary files were removed' in launch
browser=read('browser-result.json');assert browser['external_requests']==[] and browser['page_errors']==[] and browser['browser_closed']
db=sqlite3.connect('file:'+a['budget_ledger']+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
rows=[dict(r) for r in db.execute('select * from children')];db.close();row=next(r for r in rows if r['run']=='live-07')
assert row['calls']==len(calls)==3 and row['checkpoint']==1 and row['active']==0 and row['elapsed']==63
assert row['child_hash']==sha(LIVE/'authorization.json') and row['bindings_hash']==sha(LIVE/'bindings.json')
assert t['status']!='ACTIVE_ONE_SHOT';assert row['cap']==8 and row['seconds']==1800
pixel_metadata=calls[1]['pixel_measurements']
assert pixel_metadata==calls[2]['pixel_measurements']
for m in pixel_metadata:
 assert 0<=m['different_pixel_percent']<=100 and 0<=m['mean_absolute_rgb_delta']<=255
 assert round(100*m['changed_pixel_count']/m['frame_pixel_count'],4)==m['different_pixel_percent']
assert next(x for x in browser['checks'] if x['id']=='UM-04')['status']=='BLOCKED'
save('pixel-metadata.json',{'raw':pixel_metadata,'percentages':[x['different_pixel_percent'] for x in pixel_metadata],'model_percent_claim':'approximately 33-34%; correct scale','source':'actual decoded.frames -> temporal_pixel_measurements -> identical message metadata and provider_call_started ledger in frozen provider.py','note':'No new actual-frame pixel decode; actual statistical values not independently regenerated from media.'})
save('recomputed.json',{'candidate':a['candidate_sha'],'frozen_file_checks':checks,'candidate_git_checks':tracked,'build_id':h.hexdigest(),'frames':frames,'provider_call_count':len(calls),'peak_gpu_mib':peak,'minimum_ram_mib':ram,'lease_releases':releases,'native_owner':owner,'program02_children':rows,'terminal_status':t['status'],'raw_video_content':json.loads(v['raw_response'])['message']['content'],'no_new_services_models_browser_media_probe_or_decode':True})
paths=list(LIVE.rglob('*'))+[ROOT/'tools/v0_s2_fixtures.py',ROOT/'reports/authorization-program-v1-local-02.request.json',ROOT/'reports/authorization-program-v1-local-02.approval.json']
paths += [ROOT/f'reports/unified-media/independent-live-03/frame-{n}.png' for n in range(4)]
paths += [ROOT/x['path'] for x in a['samples']]
(OUT/'candidate-hashes.sha256').write_text(''.join(x['actual_sha256']+'  '+a['candidate_sha']+':'+x['path']+'\n' for x in checks))
for extra in ['reports/unified-media/authorization-runtime-transition-01.request.json','reports/unified-media/independent-live-03/independent-decoder-recompute.json','reports/unified-media/independent-live-03/supplementary-decoder.py','reports/unified-media/independent-live-03/four-frames.png']:
 paths.append(ROOT/extra)
regroot=ROOT/'reports/unified-media/program02-offline-02'
reg=json.loads((regroot/'receipt.json').read_text())
for n,c in enumerate(reg['checks']):
 assert sha(regroot/f'{n}.stdout.log')==c['stdout_sha256']
 assert sha(regroot/f'{n}.stderr.log')==c['stderr_sha256']
 assert c['exit_code']==0
paths += list(regroot.glob('*'))
for rel in ['lvw/tests/test_unified_video.py','lvw/tests/test_provider.py','LVW_V0_RuntimePatch/tests/test_s2_video_input.py','LVW_V0_RuntimePatch/tests/test_s2_video_files.py','LVW_V0_RuntimePatch/tests/test_s2_video_decoder.py']:
 p=OUT/'candidate-tests'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob(rel))
paths += [Path(a['budget_ledger'])]
(OUT/'raw-hashes.sha256').write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)+'\n' for p in sorted(set(paths)) if p.is_file()))
print(json.dumps({'cpu_recomputation':'PASS','frozen_files':len(checks),'candidate_git_checks':len(tracked),'frames':frames,'calls':len(calls),'peak_gpu':peak,'minimum_ram':ram,'ledger_calls':row['calls'],'ledger_active':row['active']},ensure_ascii=False))
