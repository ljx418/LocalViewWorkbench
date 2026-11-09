"""One finite real checkpoint: Windows command -> actual FastAPI/React -> native Ollama."""
from pathlib import Path
import asyncio,json,os,signal,socket,subprocess,sys,time,uuid,shutil,hashlib,re
from .authority import ROOT,create,terminal,sha
import requests
RUN=sys.argv[1] if len(sys.argv)>1 else 'live-01'
assert re.fullmatch(r'live-(?:0[1-9]|[1-9][0-9]+)',RUN)
from .acceptance_recipe import load as load_recipe
from .checkpoint_checks import negative_uploads,verify_configs
from tools.local_program_authority import approved
RECIPE=load_recipe(ROOT,approved())
SELF=Path(__file__);SAMPLES=[ROOT/item['path'] for item in RECIPE['samples']]
out,auth=create(RUN,SELF,{'api_starts':1,'ollama_starts':1,'headless_browser_starts':1,'provider_calls':8,'full_checkpoints':1,'model_calls':8,'downloads':0,'cloud_calls':0,'paid_calls':0,'holdout_model_calls':0},port=18780,samples=SAMPLES,seconds=1800,full=True)
state=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified'/RUN;state.mkdir(parents=True,exist_ok=False)
nonce=uuid.uuid4().hex;launcher=None;api=None;runroot=None;stage_consumed=False
result={'kind':'REAL_UNIFIED_CHECKPOINT_NOT_HUMAN_OR_FULL_R1_ACCEPTANCE','candidate_sha':auth['candidate_sha'],'decision':'NO_GO','checks':{},'stage_checkpoint_consumed':False,'stage_pass_claim':False,'human_signoff':None}
session=requests.Session();session.trust_env=False
win=lambda p:subprocess.check_output(['wslpath','-w',str(p)],text=True).strip()
ps='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
q=lambda x:"'"+str(x).replace("'","''")+"'"
def alive(port):
 with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))==0
def api_call(method,path,**kw):
 kw.setdefault('timeout',15)
 r=session.request(method,'http://127.0.0.1:18780'+path,**kw);return r
try:
 assert not alive(18780) and not alive(11434),'required port has an existing service; no foreign process will be touched'
 (state/'native-temp').mkdir()
 bindings={n:{'path':p,'sha256':sha(p)} for n,p in {'powershell':ps,'ffmpeg':'/usr/bin/ffmpeg','ffprobe':'/usr/bin/ffprobe','node':'/usr/bin/node','browser':'/home/administrator/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome','launcher':str(ROOT/'START_LVW.cmd'),'native_icon':str(ROOT/'LVW.exe')}.items()}
 native_query=subprocess.run([ps,'-NoProfile','-NonInteractive','-Command',"$ErrorActionPreference='Stop';(Get-Command ollama.exe -CommandType Application -ErrorAction Stop).Source"],capture_output=True,timeout=15)
 assert native_query.returncode==0,'installed native Ollama not found'
 native_exe=Path(subprocess.check_output(['wslpath','-u',native_query.stdout.decode().strip()],text=True).strip())
 bindings['native_ollama']={'path':str(native_exe),'sha256':sha(native_exe)}
 bindings['python']={'path':sys.executable,'sha256':sha(sys.executable)}
 (out/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
 if auth.get('budget_ledger'):
  from tools.local_program_authority import bind_execution
  bind_execution(RUN,out/'bindings.json',ledger=auth['budget_ledger'])
 script="$ErrorActionPreference='Stop';$env:TEMP="+q(win(state/'native-temp'))+";$env:TMP=$env:TEMP;$env:LVW_NO_BROWSER='1';$env:LVW_NO_PAUSE='1';$env:LVW_PORT_OVERRIDE='18780';$env:LVW_REQUIRE_BUDGET='1';$env:LVW_AUTHORIZATION_CHILD="+q(str(out/'authorization.json'))+";$env:LVW_LAUNCH_TOKEN="+q(nonce)+";& "+q(win(ROOT/'START_LVW.cmd'))+";exit $LASTEXITCODE"
 log=(out/'launcher.log').open('wb');launcher=subprocess.Popen([ps,'-NoProfile','-NonInteractive','-Command',script],stdout=log,stderr=subprocess.STDOUT)
 for _ in range(90):
  if alive(18780):break
  if launcher.poll() is not None:raise RuntimeError('Windows launcher exited before API; inspect launcher.log')
  time.sleep(.3)
 assert alive(18780),'API boot timeout'
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   env=(p/'environ').read_bytes().split(b'\0');cmd=(p/'cmdline').read_bytes()
   if ('LVW_LAUNCH_TOKEN='+nonce).encode() in env and b'lvw/run_local.py' in cmd:
    assert api is None,'ambiguous server ownership';owned_env=env;api={'pid':int(p.name),'birth':(p/'stat').read_text().split()[21]}
    value=next(x.split(b'=',1)[1] for x in env if x.startswith(b'LVW_DATA_ROOT='));runroot=Path(value.decode())
  except (OSError,ProcessLookupError):continue
 assert api and runroot and str(runroot.resolve()).casefold().startswith(str(state.resolve()).casefold()+'/'),'run-owned server process/root binding failed'
 assert b'LVW_REQUIRE_BUDGET=1' in owned_env and ('LVW_AUTHORIZATION_CHILD='+str(out/'authorization.json')).encode() in owned_env,'controlled API budget guard environment missing'
 assert next(x.split(b'=',1)[1].decode() for x in owned_env if x.startswith(b'LVW_OLLAMA_EXE='))==str(native_exe),'launcher selected different native executable'
 result['api_process']=api;result['source_build_id']=api_call('GET','/health').json()['data']['build_id']
 win_probe=subprocess.run(['/mnt/c/Windows/System32/curl.exe','--noproxy','*','-fsS','--max-time','5','http://127.0.0.1:18780/health'],capture_output=True,timeout=8)
 (out/'windows-health.json').write_bytes(win_probe.stdout);assert win_probe.returncode==0,'Windows browser loopback cannot reach actual WSL API'
 # Actual public invalid files: no provider can run before the model is started.
 negative_uploads(runroot,api['pid'],RECIPE['negative_cases'],api_call,out,ROOT)
 result['checks']['UM-02']={'status':'PASS','oracle':'all seven real public rejects with exact stable codes, zero model calls, media/temp/spooled FDs back to baseline','evidence':'negative-results.json'}
 auth['bindings_sha256']=sha(out/'bindings.json')
 stage_consumed=True;result['stage_checkpoint_consumed']=True
 result['cleanup_error']='browser lifecycle not yet proved; retain reservation if its harness exits without a close receipt'
 node=subprocess.run(['node',str(SELF.with_name('live_browser.cjs')),str(out)],cwd=ROOT,capture_output=True,timeout=1200)
 (out/'browser.stdout.log').write_bytes(node.stdout);(out/'browser.stderr.log').write_bytes(node.stderr)
 browser=json.loads((out/'browser-result.json').read_text())
 assert browser.get('browser_closed') is True,'browser close receipt missing'
 result.pop('cleanup_error',None)
 for c in browser['checks']:result['checks'][c['id']]=c
 if node.returncode:raise RuntimeError('real browser sequence failed: '+browser.get('error','see logs'))
 # Join original model source and real server lease telemetry.
 video=json.loads((out/'video-model-run.json').read_text());assert video['input_sha256']==sha(SAMPLES[1])
 ledger=[json.loads(x) for x in (runroot/'provider.jsonl').read_text().splitlines()]
 calls=[x for x in ledger if x['event']=='provider_call_started'];assert len(calls)<=8 and len(calls)>=3
 video_calls=[x for x in calls if x.get('lease_job_id')==video['job_id'] and x.get('event')=='provider_call_started']
 assert len(video_calls)==1 and video_calls[0]['frame_count']==4 and video_calls[0]['presentation']=='source-frames/appearance-1'
 evidence=[x for x in ledger if x['event']=='temporal_evidence_prepared' and x.get('lease_job_id')==video['job_id']]
 assert len(evidence)==1 and evidence[0]['source_sha256']==video['input_sha256']
 assert evidence[0]['evidence']['source_frame_sha256']==[frame['sha256'] for frame in video['frames']]
 assert len(evidence[0]['evidence']['pixel_pairs'])==len(evidence[0]['evidence']['alignment_pairs'])==3
 cancellations=json.loads((out/'cancellation-results.json').read_text())['cases']
 assert len(cancellations)==3 and {row['phase'] for row in cancellations}=={'queued','preparing','running'}
 for row in cancellations:
  if row['phase']!='running':
   assert not any(call.get('lease_job_id')==row['job_id'] for call in calls),'pre-inference cancelled job sent model call'
  assert row['terminal']['result_ref'] is None and row['terminal']['resource_state']=='released'

 requests_rows=[json.loads(line) for line in (out/'public-analysis-requests.jsonl').read_text().splitlines()]
 configs=verify_configs(requests_rows,[json.loads((out/'image-model-run.json').read_text()),video])
 (out/'configuration-recomputation.json').write_text(json.dumps(configs,ensure_ascii=False,indent=2)+'\n')
 leases=[x for x in ledger if x['event']=='lease_released'];assert len(leases)>=3
 samples=[x for x in ledger if x['event']=='running_resource_sample'];assert samples and max(x['gpu_used_mib'] for x in samples)<23552 and min(x['available_ram_mib'] for x in samples)>=2048
 native_logs='\n'.join(p.read_text(errors='replace') for p in (runroot/'runtime').glob('*.stderr.log'))
 assert 'OLLAMA_NO_CLOUD:true' in native_logs and ('OLLAMA_HOST:http://127.0.0.1:11434' in native_logs or 'OLLAMA_HOST:http://127.0.0.1:11434]' in native_logs),'native environment witness missing'
 owners=[json.loads(p.read_text()) for p in (runroot/'runtime').glob('*.owner.json')];assert len(owners)==1 and owners[0]['state']=='exited' and owners[0]['listener_owned'] is False
 assert not alive(11434),'native Ollama listener remains after product stop'
 result['checks']['UM-08']={'status':'PASS','provider_calls':len(calls),'lease_releases':len(leases),'peak_gpu_mib':max(x['gpu_used_mib'] for x in samples),'minimum_ram_mib':min(x['available_ram_mib'] for x in samples),'native_owner':owners[0],'no_cloud_witness':True}
 result['decision']='REAL_CHECKPOINT_COMPLETE_INDEPENDENT_REVIEW_PENDING'
except Exception as error:result['error']=type(error).__name__+': '+str(error)
finally:
 if api and runroot and runroot.exists():
  try:
   jobs=set()
   ledger=runroot/'provider.jsonl'
   if ledger.exists():jobs.update(x['lease_job_id'] for x in map(json.loads,ledger.read_text().splitlines()) if x.get('lease_job_id'))
   public=out/'public-jobs.jsonl'
   if public.exists():jobs.update(x['id'] for x in map(json.loads,public.read_text().splitlines()))
   for job in jobs:
    response=api_call('POST','/api/v1/jobs/'+job+'/cancel',headers={'Idempotency-Key':'cleanup','X-LVW-Control':'local-ui'})
    if response.status_code != 200:raise RuntimeError('cancel receipt missing')
   deadline=time.monotonic()+35
   pending=set(jobs)
   terminal_jobs={}
   while pending and time.monotonic()<deadline:
    for job in list(pending):
     response=api_call('GET','/api/v1/jobs/'+job)
     if response.status_code!=200:raise RuntimeError('job terminal receipt missing')
     state_value=response.json()['data']
     if state_value['status'] not in {'queued','preparing','running','cancelling'}:
      terminal_jobs[job]=state_value;pending.remove(job)
    if pending:time.sleep(.2)
   (out/'cleanup-job-terminals.json').write_text(json.dumps(terminal_jobs,indent=2)+'\n')
   if pending:raise RuntimeError('active tasks did not reach terminal before runtime stop')
   stopped=api_call('POST','/api/v1/runtime/ollama/stop',headers={'X-LVW-Control':'local-ui','Idempotency-Key':'terminal-stop'})
   (out/'cleanup-stop-response.json').write_text(json.dumps(stopped.json(),indent=2)+'\n')
   if stopped.status_code != 200:result['cleanup_error']='owned runtime stop not confirmed before archive'
  except Exception as e:result['cleanup_error']='runtime stop proof: '+str(e)
 if runroot and runroot.exists():
  # Preserve only this run's known logs before the production command removes its temporary root.
  archive=out/'runtime-evidence';archive.mkdir(exist_ok=True)
  for p in [runroot/'provider.jsonl',*(runroot/'runtime').glob('*')]:
   if p.is_file():shutil.copyfile(p,archive/p.name)
 if api:
  try:
   stat=Path('/proc')/str(api['pid'])/'stat'
   if stat.exists() and stat.read_text().split()[21]==api['birth']:os.kill(api['pid'],signal.SIGTERM)
  except Exception as e:result['cleanup_error']=str(e)
 if launcher:
  try:launcher.wait(timeout=55)
  except subprocess.TimeoutExpired:result['cleanup_error']='original launcher has not terminated; no unrelated process killed'
 if runroot:
  result['run_root_removed']=not runroot.exists()
 result['api_listener_absent']=not alive(18780);result['ollama_listener_absent']=not alive(11434)
 result['checkpoint_sequence_attempted']=stage_consumed
 # terminal() obtains effective consumption from the guarded model-action ledger.
 if result.get('cleanup_error') or not result['api_listener_absent'] or not result['ollama_listener_absent'] or (runroot and not result.get('run_root_removed')):
  result['decision']='NO_GO';result['cleanup_error']=result.get('cleanup_error','run cleanup incomplete')
 terminal(out,auth,result)
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result['decision']=='REAL_CHECKPOINT_COMPLETE_INDEPENDENT_REVIEW_PENDING' else 1)
