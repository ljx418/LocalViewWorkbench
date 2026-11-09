import asyncio,hashlib,json,os,shutil,sys,types
from pathlib import Path
R=Path.cwd();O=R/'reports/unified-media/independent-source-frames-03';sys.path[:0]=[str(R),str(R/'lvw/backend')]
m=types.ModuleType('source_probe_review');m.__file__=str(R/'reports/unified-media/source_frames_probe.py')
exec(compile((O/'harness.py.txt').read_text(),m.__file__,'exec'),m.__dict__)
scenario=os.environ['REVIEW_SCENARIO'];fake=(O/'lifecycle-final'/scenario/'pack').resolve();(fake/'reports/unified-media/live-14').mkdir(parents=True)
(fake/'reports/unified-media/independent-live-14').mkdir()
exe=fake/'ollama.exe';exe.write_bytes(b'fake')
binding={n:{'path':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()} for n in ('native_ollama','powershell')}
(fake/'reports/unified-media/live-14/bindings.json').write_text(json.dumps(binding));(fake/'reports/unified-media/live-14/actual-model-identity.json').write_text('{"digest":"fake"}')
for i in range(4):(fake/f'reports/unified-media/independent-live-14/frame-{i}.ppm').write_bytes(b'synthetic')
for p in ('request.json','approval.json'):(fake/p).write_text('{}')
script=fake/'reports/unified-media/source_frames_probe.py';script.write_text('fake identity')
m.ROOT=fake;m.__file__=str(script);m.listening=lambda:False;m.uuid=types.SimpleNamespace(uuid4=lambda:types.SimpleNamespace(hex='review-owned-'+scenario))
temp=fake.parent.parent/('.lvw-runtime/lvw-prompt-service/thinking-review-owned-'+scenario)
assert temp.is_relative_to(O.resolve())
if scenario=='root_collision':temp.mkdir(parents=True);(temp/'sentinel.txt').write_text('foreign')
calls=[]
m.program=types.SimpleNamespace(reserve=lambda *a:calls.append('reserve'),program_paths=lambda:('request.json','approval.json'),bind=lambda *a:calls.append('bind'),bind_execution=lambda *a:calls.append('bind_execution'),settle=lambda run,count:(calls.append('settle0') or {'actual_model_actions':count}),close_retaining_reservation=lambda *a:calls.append('retain'),LEDGER='never-used')
m.subprocess=types.SimpleNamespace(check_output=lambda args,**kw:'fake-head\n' if args[1]=='rev-parse' else '',run=lambda *a,**kw:types.SimpleNamespace(returncode=0))
m.shutil=types.SimpleNamespace(which=lambda _:None if scenario=='setup_failure' else str(exe),rmtree=shutil.rmtree,copytree=shutil.copytree)
class Provider:
    def __init__(self,*a,**kw):self._lease=None
    async def acquire(self,*a):calls.append('acquire');raise m.AppError('RESOURCE_BUSY','synthetic rejection',status_code=503)
class Runtime:
    def __init__(self,*a):self.process=None;self._native={'fixture':True}
    async def start(self):calls.append('start');return {'ollama':{'managed':True}}
    async def close(self):calls.append('close');self._native=None
m.OllamaProvider=Provider;m.OllamaRuntime=Runtime
import app.native_runtime
app.native_runtime.proof=lambda _: {'listener_owned':True}
class Client:
    def __init__(self,**kw):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def get(self,*a):return types.SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'models':[{'name':'gemma4:26b','digest':'fake'}]})
m.httpx=types.SimpleNamespace(AsyncClient=Client)
asyncio.run(m.main())
receipt=json.loads((fake/'reports/unified-media/source-frames-probe-03/receipt.json').read_text())
assert receipt['decision']=='NO_GO' and receipt['cleanup_proven'] and calls[-1]=='settle0'
if scenario=='root_collision':assert not receipt['run_root_claimed'] and (temp/'sentinel.txt').read_text()=='foreign'
else:assert receipt['run_root_claimed'] and not temp.exists()
if scenario=='lease_failure':assert calls==['reserve','bind','bind_execution','start','acquire','close','settle0']
print(json.dumps({'scenario':scenario,'calls':calls,'root_claimed':receipt['run_root_claimed'],'root_removed':receipt['run_root_removed'],'foreign_collision_untouched':scenario=='root_collision','real_runtime_network_gpu_ledger_actions':0},indent=2))
