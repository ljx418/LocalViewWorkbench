"""Independent stdlib-only audit: git blobs, raw files, read-only SQLite; no product imports."""
import hashlib,json,sqlite3,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parent;L=R/'reports/unified-media/live-09'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(n):return json.loads((L/n).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
a=read('authorization.json');t=read('authorization.terminal.json');r=read('receipt.json');b=read('browser-result.json')
assert a['candidate_sha']=='fd9044e29ea923d4b1c7e1a1d9f5af47b35b9a81'
prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=R,text=True).strip()
def blob(p):return subprocess.run(['git','show',a['candidate_sha']+':'+prefix+p],cwd=R,capture_output=True)
checks=[]
for x in a['frozen_files']+a['samples']:
 p=R/x['path'];q=blob(x['path']); git_hash=hashlib.sha256(q.stdout).hexdigest() if q.returncode==0 else None
 if git_hash!=x['sha256'] and x['path'].endswith('.cmd') and q.returncode==0:git_hash=hashlib.sha256(q.stdout.replace(b'\n',b'\r\n')).hexdigest()
 checks.append({**x,'working_hash':sha(p),'candidate_git_hash':git_hash,'git_tracked':q.returncode==0})
assert all(c['working_hash']==c['sha256'] and (not c['git_tracked'] or c['candidate_git_hash']==c['sha256']) for c in checks)
assert sha(R/a['program'])==a['program_sha256'];grant=json.loads((R/a['program']).read_text());assert grant['decision']=='APPROVED'
assert sha(R/grant['request'])==grant['request_sha256']==a['program_request_sha256']
assert a['harness_sha256']==sha(R/'reports/unified-media/live_checkpoint.py')
for x in read('bindings.json').values():assert sha(x['path'])==x['sha256']
files=list((R/'lvw/backend/app').glob('*.py'))+list((R/'lvw/frontend/dist').rglob('*'))+[R/'templates/analysis_system_zh.txt']+[R/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge'/n for n in ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']]
h=hashlib.sha256()
for p in sorted(p for p in files if p.is_file()):h.update(str(p.relative_to(R)).encode()+b'\0'+p.read_bytes()+b'\0')
assert h.hexdigest()==r['source_build_id']==read('windows-health.json')['data']['build_id']
events=[json.loads(x) for x in (L/'runtime-evidence/provider.jsonl').read_text().splitlines()]
assert len(events)==1 and events[0]['event']=='admission_snapshot' and events[0]['lease_job_id'] is None
baseline=events[0]['baseline'];assert baseline['gpu_free_mib']==18515<19047
assert not any(x['event'] in ('provider_call_started','lease_acquired') for x in events)
jobs=read('cleanup-job-terminals.json');assert len(jobs)==1
j=next(iter(jobs.values()));assert j['status']=='failed' and j['error_code']=='RESOURCE_BUSY' and j['result_ref'] is None and j['resource_state']=='released'
assert read('negative-0.json')['error']['details']['subcode']=='VIDEO_DURATION_LIMIT'
assert read('negative-1.json')['error']['code']=='MEDIA_INVALID'
assert not read('cleanup-stop-response.json')['data']['ollama']['reachable']
owner=json.loads(next((L/'runtime-evidence').glob('*.owner.json')).read_text());assert owner['state']=='exited' and owner['listener_owned'] is False
native='\n'.join(p.read_text(errors='replace') for p in (L/'runtime-evidence').glob('*.stderr.log'));assert 'OLLAMA_NO_CLOUD:true' in native and 'OLLAMA_HOST:http://127.0.0.1:11434' in native
launch=(L/'launcher.log').read_text();assert f"Finished server process [{r['api_process']['pid']}]" in launch and 'Run-owned temporary files were removed' in launch
assert b['browser_closed'] and not b['external_requests'] and not b['page_errors']
assert all(r[k] for k in ['run_root_removed','api_listener_absent','ollama_listener_absent']) and t['status']=='EXPIRED_NO_GO'
db=sqlite3.connect('file:'+a['budget_ledger']+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
rows=[dict(x) for x in db.execute('select * from children')];db.close();row=next(x for x in rows if x['run']=='live-09')
assert row['active']==row['calls']==row['checkpoint']==0 and row['elapsed']==12 and row['cap']==8 and row['seconds']==1800
assert row['child_hash']==sha(L/'authorization.json') and row['bindings_hash']==sha(L/'bindings.json')
# Preserve historical program02 rows; independently recompute all actual and reserved totals.
carry=json.loads((R/'reports/unified-media/complete03-ledger-carry-forward.json').read_text())['rows']
for old in carry:assert next(x for x in rows if x['run']==old['run'])==old
actual={'model_actions':sum(x['calls'] for x in rows),'effective_full_checkpoints':sum(x['checkpoint'] for x in rows),'production_seconds':sum(x['elapsed'] for x in rows if not x['cpu'])}
reserved={'model_actions':sum(x['cap'] if x['active'] else x['calls'] for x in rows),'effective_full_checkpoints':sum(x['full'] if x['active'] else x['checkpoint'] for x in rows),'production_seconds':sum(x['seconds'] if x['active'] else x['elapsed'] for x in rows if not x['cpu'])}
assert reserved['model_actions']<=1024 and reserved['effective_full_checkpoints']<=24 and reserved['production_seconds']<=172800
save('recomputed.json',{'scope':'live-09 only; later resource children may appear in ledger snapshot','snapshot_utc_epoch':time.time(),'frozen_checks':checks,'build_id':h.hexdigest(),'raw_provider_events':events,'calls':0,'lease_acquired':False,'resource_threshold_free_mib':19047,'baseline':baseline,'native_owner':owner,'live09_ledger':row,'ledger_rows':rows,'global_actual':actual,'global_including_active_reservations':reserved,'historical_rows_unchanged':True,'cleanup':'PASS_ORIGINAL_RAW_EXIT_AND_TERMINAL_WITNESSES','no_new_media_probe_decode_service_model_browser':True})
paths=[p for p in L.rglob('*') if p.is_file()]+[R/a['program'],R/grant['request'],R/'reports/unified-media/complete03-ledger-carry-forward.json']
(O/'raw-hashes.sha256').write_text(''.join(sha(p)+'  '+str(p.relative_to(R))+'\n' for p in sorted(paths)))
print(json.dumps({'result':'NO_GO_WAIT_RESOURCE','calls':0,'baseline':baseline,'frozen_files_checked':len(checks),'global_actual':actual,'global_reserved':reserved,'cleanup':'PASS'},ensure_ascii=False))
