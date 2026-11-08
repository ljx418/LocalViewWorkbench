"""One finite real checkpoint: Windows command -> actual FastAPI/React -> native Ollama."""
from pathlib import Path
import asyncio,json,os,signal,socket,subprocess,sys,time,uuid,shutil,hashlib
from .authority import ROOT,create,terminal,sha
import requests
RUN=sys.argv[1] if len(sys.argv)>1 else 'live-01'
assert RUN in {'live-01','live-02'}
SELF=Path(__file__);SAMPLES=[ROOT/'reports/unified-media/dev-image.png',ROOT/'reports/v0-s2/fixture-preparation-02/fixtures/tracking.mov',ROOT/'reports/v0-s2/fixture-preparation-02/fixtures/over-duration.mp4',ROOT/'reports/v0-s2/fixture-preparation-02/fixtures/corrupt.mp4']
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
 r=session.request(method,'http://127.0.0.1:18780'+path,timeout=15,**kw);return r
try:
 assert not alive(18780) and not alive(11434),'required port has an existing service; no foreign process will be touched'
 (state/'native-temp').mkdir()
 bindings={n:{'path':p,'sha256':sha(p)} for n,p in {'powershell':ps,'ffmpeg':'/usr/bin/ffmpeg','ffprobe':'/usr/bin/ffprobe','node':'/usr/bin/node','browser':'/home/administrator/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome','launcher':str(ROOT/'START_LVW.cmd'),'native_icon':str(ROOT/'LVW.exe')}.items()}
 (out/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
 script="$ErrorActionPreference='Stop';$env:TEMP="+q(win(state/'native-temp'))+";$env:TMP=$env:TEMP;$env:LVW_NO_BROWSER='1';$env:LVW_NO_PAUSE='1';$env:LVW_PORT_OVERRIDE='18780';$env:LVW_LAUNCH_TOKEN="+q(nonce)+";& "+q(win(ROOT/'START_LVW.cmd'))+";exit $LASTEXITCODE"
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
    assert api is None,'ambiguous server ownership';api={'pid':int(p.name),'birth':(p/'stat').read_text().split()[21]}
    value=next(x.split(b'=',1)[1] for x in env if x.startswith(b'LVW_DATA_ROOT='));runroot=Path(value.decode())
  except (OSError,ProcessLookupError):continue
 assert api and runroot and str(runroot.resolve()).casefold().startswith(str(state.resolve()).casefold()+'/'),'run-owned server process/root binding failed'
 result['api_process']=api;result['source_build_id']=api_call('GET','/health').json()['data']['build_id']
 # Actual public invalid files: no provider can run before the model is started.
 for i,p in enumerate(SAMPLES[2:]):
  with p.open('rb') as f:r=api_call('POST','/api/v1/media',headers={'Idempotency-Key':'negative-'+str(i)},files={'file':(p.name,f,'video/mp4')})
  assert r.status_code==422,(p.name,r.text)
  (out/('negative-'+str(i)+'.json')).write_text(json.dumps(r.json(),indent=2)+'\n')
 result['checks']['UM-02']={'status':'PASS','oracle':'real public duration/corrupt rejection before model start; full negative matrix in offline checks'}
 auth['bindings_sha256']=sha(out/'bindings.json')
 stage_consumed=True;result['stage_checkpoint_consumed']=True
 node=subprocess.run(['node',str(SELF.with_name('live_browser.cjs')),str(out)],cwd=ROOT,capture_output=True,timeout=1200)
 (out/'browser.stdout.log').write_bytes(node.stdout);(out/'browser.stderr.log').write_bytes(node.stderr)
 browser=json.loads((out/'browser-result.json').read_text())
 for c in browser['checks']:result['checks'][c['id']]=c
 if node.returncode:raise RuntimeError('real browser sequence failed: '+browser.get('error','see logs'))
 # Join original model source and real server lease telemetry.
 video=json.loads((out/'video-model-run.json').read_text());assert video['input_sha256']==sha(SAMPLES[1])
 ledger=[json.loads(x) for x in (runroot/'provider.jsonl').read_text().splitlines()]
 calls=[x for x in ledger if x['event']=='provider_call_started'];assert len(calls)<=8 and len(calls)>=3
 assert any(x.get('frame_count')==4 for x in calls)
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
 if runroot and runroot.exists():
  # Preserve only this run's known logs before the production command removes its temporary root.
  archive=out/'runtime-evidence';archive.mkdir(exist_ok=True)
  for p in [runroot/'provider.jsonl',*(runroot/'runtime').glob('*')]:
   if p.is_file():shutil.copyfile(p,archive/p.name)
 if api:
  try:
   # Cancel only this run's known current jobs before shutdown if a browser step failed.
   ledger=runroot/'provider.jsonl' if runroot else None
   if ledger and ledger.exists():
    jobs={x.get('lease_job_id') for x in map(json.loads,ledger.read_text().splitlines()) if x.get('lease_job_id')}
    for job in jobs:
     try:api_call('POST','/api/v1/jobs/'+job+'/cancel',headers={'Idempotency-Key':'cleanup','X-LVW-Control':'local-ui'})
     except requests.RequestException:pass
   stat=Path('/proc')/str(api['pid'])/'stat'
   if stat.exists() and stat.read_text().split()[21]==api['birth']:os.kill(api['pid'],signal.SIGTERM)
  except Exception as e:result['cleanup_error']=str(e)
 if launcher:
  try:launcher.wait(timeout=55)
  except subprocess.TimeoutExpired:result['cleanup_error']='original launcher has not terminated; no unrelated process killed'
 if runroot:
  result['run_root_removed']=not runroot.exists()
 result['api_listener_absent']=not alive(18780);result['ollama_listener_absent']=not alive(11434)
 result['stage_checkpoint_consumed']=stage_consumed
 if not result['api_listener_absent'] or not result['ollama_listener_absent'] or (runroot and not result.get('run_root_removed')):
  result['decision']='NO_GO';result['cleanup_error']=result.get('cleanup_error','run cleanup incomplete')
 terminal(out,auth,result)
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(0 if result['decision']=='REAL_CHECKPOINT_COMPLETE_INDEPENDENT_REVIEW_PENDING' else 1)
