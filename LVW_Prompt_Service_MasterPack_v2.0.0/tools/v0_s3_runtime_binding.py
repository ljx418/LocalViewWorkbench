"""One-shot P2B CPU evidence. Fixed commands only; no service/model/ledger access.

CLI: --preflight <committed SHA>, then --run. Windows --windows is internal,
requires the marker and the frozen plan beside this copied candidate script.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'.agent-governance/runtime/receipts/s3-p2b-correction-01'
CHILD = 'reports/v0-s3/product-gate0/runtime-binding-correction-01.child.json'
CONTRACT = 'reports/v0-s3/product-gate0/p2-binding-correction-01.contract.md'
PROTOCOL = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
CORE = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py'
HARNESS = 'tools/v0_s3_runtime_binding.py'
SOURCES = [HARNESS, PROTOCOL, CORE, 'tools/v0_s3_budget_authority.py',
           'tools/local_program_authority.py',
           'reports/authorization-program-v1-local-02.request.json',
           'reports/authorization-program-v1-local-02.approval.json',
           'reports/authorization-program-v1-complete-03.request.json',
           'reports/authorization-program-v1-complete-03.approval.json']
FIXED = {'windows_python':'/mnt/c/ComfyUI-aki-v2/python/python.exe',
         'wsl':'/mnt/c/Windows/System32/wsl.exe', 'python':'/usr/bin/python3'}
LIMITS = {'wall_seconds':1200, 'process_starts':64,'per_command_seconds':30,
          'metadata_hash_files':3,'metadata_hash_bytes':67108864,
          'output_bytes':16777216,'synthetic_debits':16}
CHILD_ID = 'S3-P2B-CORRECTION-01'
CLAIM = Path('/mnt/c/workSpace/videoWorkLine/.lvw-runtime/lvw-prompt-service/cpu-verification-claims/S3-P2B-CORRECTION-01.claim.json')
OLD_SEAL = 'reports/v0-s3/product-gate0/implementation-p2-binding/installed-seal.json'
TERMINAL_RESERVE = 65536
ACTIVE_METER = None


def safe_parent(path):
    for part in [path, *path.parents]:
        if part.is_symlink(): raise ValueError('symlink forbidden')


def claim_path(child):
    historical=json.loads((ROOT/'reports/unified-media/live-15/authorization.json').read_text())
    expected=Path(historical['budget_ledger']).parent/'cpu-verification-claims'/(CHILD_ID+'.claim.json')
    if child['child_id']!=CHILD_ID or Path(child['consumption_owner'])!=CLAIM or str(CLAIM).casefold()!=str(expected).casefold():
        raise ValueError('fixed consumption owner required; old child expired')
    safe_parent(CLAIM)
    if not CLAIM.parent.parent.samefile(expected.parent.parent):raise ValueError('shared owner directory identity')
    return CLAIM


def claim_once(path, pre):
    safe_parent(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    safe_parent(path)
    value=dict(status='RUNNING',child_id=CHILD_ID,child_sha256=pre['child_sha256'],
               candidate=pre['candidate'],preflight_sha256=digest(BASE/'preflight.json'),
               output_root=str(BASE),pid=os.getpid(),birth=protocol(ROOT).process_birth(os.getpid()),time=time.time())
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(value,f);f.flush();os.fsync(f.fileno())
    return value


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()


def write(path, value):
    data=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    if len(data)>32768: raise ValueError('bounded JSON output')
    if ACTIVE_METER is not None: ACTIVE_METER.take('output_bytes',len(data))
    temporary=path.with_name(path.name+'.writing')
    with temporary.open('wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value
    spec.loader.exec_module(value)
    return value


def protocol(root):
    # Namespace only: no Comfy __init__ or optional dependency import.
    package=types.ModuleType('_p2b_bridge');package.__path__=[str((root/PROTOCOL).parent)]
    sys.modules['_p2b_bridge']=package
    module('_p2b_bridge.core',root/CORE)
    return module('_p2b_bridge.program_budget',root/PROTOCOL)


class Meter:
    def __init__(self):
        self.started=time.monotonic()
        self.used={key:0 for key in LIMITS}
        self.commands=[]
        self.seals={}
        self.failures=[]
    def take(self,key,n):
        if type(n) is not int or n<0 or self.used[key]+n>LIMITS[key]:
            self.failures.append('budget '+key);raise ValueError('budget '+key)
        self.used[key]+=n
        self.check()
    def check(self):
        self.used['wall_seconds']=time.monotonic()-self.started
        if self.used['wall_seconds']>LIMITS['wall_seconds']:
            self.failures.append('wall budget');raise ValueError('wall budget')
        if self.failures: raise ValueError(self.failures[0])
    def run(self,command,process_cost=1,observe=None):
        if command[0] not in self.seals: raise ValueError('unsealed executable')
        self.take('process_starts',process_cost)
        cap=min(1048576,(LIMITS['output_bytes']-self.used['output_bytes']-TERMINAL_RESERVE)//2)
        if cap<=0: raise ValueError('capture budget')
        # Reserve both pipes including any truncated overflow; no refund.
        self.take('output_bytes',2*cap)
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        record={'command':command,'interop_pid':p.pid,'interop_birth':protocol(ROOT).process_birth(p.pid,p),
                'process_start_reservation':process_cost,'capture_cap_per_pipe':cap}
        self.commands.append(record)
        buffers=[bytearray(),bytearray()];overflow=threading.Event();errors=[]
        def drain(i,pipe):
            try:
                while True:
                    chunk=pipe.read(4096)
                    if not chunk:break
                    room=cap-len(buffers[i]);buffers[i].extend(chunk[:room])
                    if len(chunk)>room:overflow.set();break
            except Exception as e:errors.append(type(e).__name__)
        threads=[threading.Thread(target=drain,args=(i,pipe),daemon=True) for i,pipe in enumerate((p.stdout,p.stderr))]
        for t in threads:t.start()
        start=time.monotonic()
        try:
            while p.poll() is None or any(t.is_alive() for t in threads):
                if observe:observe(time.monotonic()-start)
                if overflow.is_set() or errors or time.monotonic()-start>=30:
                    record['error']='OUTPUT_LIMIT' if overflow.is_set() else ('PIPE_ERROR' if errors else 'TIMEOUT')
                    break
                time.sleep(.02)
        finally:
            if p.poll() is None:p.kill()  # only our direct Popen, never a remote PID
            record['exit_code']=p.wait(timeout=1)
            for t in threads:t.join(timeout=1)
            record['threads_joined']=not any(t.is_alive() for t in threads)
            if record['threads_joined']:p.stdout.close();p.stderr.close()
            record['pipe_closed']=[p.stdout.closed,p.stderr.closed]
            record['stdout']=buffers[0].decode('utf-8',errors='replace')
            record['stderr']=buffers[1].decode('utf-8',errors='replace')
            record['elapsed']=time.monotonic()-start
            record['reader_errors']=errors
            if overflow.is_set():record['error']='OUTPUT_LIMIT'
            elif errors:record['error']='PIPE_ERROR'
            elif not record['threads_joined'] or not all(record['pipe_closed']):record['error']='PIPE_NOT_CLOSED'
        if record.get('error') or record['exit_code']!=0:
            self.failures.append(record.get('error','PROCESS_EXIT'))
            raise ValueError(self.failures[-1])
        return record


def preflight(candidate):
    if len(candidate)!=40 or any(c not in '0123456789abcdef' for c in candidate):raise ValueError('candidate')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if actual!=candidate:raise ValueError('candidate HEAD')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise ValueError('dirty candidate')
    child=json.loads((ROOT/CHILD).read_text())
    if digest(ROOT/CONTRACT)!=child['contract_sha256']:raise ValueError('contract seal')
    if digest(ROOT/child['parent_approval'])!=child['parent_approval_sha256']:raise ValueError('parent seal')
    if any(child['limits'][k]!=v for k,v in LIMITS.items()):raise ValueError('budget drift')
    owner=claim_path(child)
    safe_parent(BASE)
    BASE.mkdir(parents=True,exist_ok=True)
    if owner.exists() or (BASE/'consumed.json').exists():raise ValueError('batch already consumed')
    value={'candidate':candidate,'child_sha256':digest(ROOT/CHILD),'contract_sha256':digest(ROOT/CONTRACT),
           'source_hashes':{s:digest(ROOT/s) for s in SOURCES},'tools':FIXED,'output_root':str(BASE),
           'historical_authorization_sha256':digest(ROOT/'reports/unified-media/live-15/authorization.json'),
           'old_installed_seal_sha256':digest(ROOT/OLD_SEAL),'claim_path':str(owner),'limits':LIMITS,'distribution':'Ubuntu-24.04',
           'fixture_parent':'/tmp','unc_prefix':r'\\wsl.localhost\Ubuntu-24.04',
           'cleanup':'Only temporary fixture after confirmed remote exit; unknown retains reservation and root; no remote kill protocol',
           'real_machine_accesses':0}
    write(BASE/'preflight.json',value)
    return value


def make_fixture(root,pre):
    root.mkdir();(root/'.s3-synthetic-fixture').touch()
    for name in SOURCES:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        if ACTIVE_METER:ACTIVE_METER.take('output_bytes',(ROOT/name).stat().st_size)
        shutil.copyfile(ROOT/name,path)
    b=protocol(root);a=module('_p2b_authority',root/'tools/local_program_authority.py')
    ledger=root/'fixture.sqlite';child=root/'child.json';binding=root/'binding 中文 Space.json';execution=root/'execution.json'
    a.reserve('synthetic-p2b','V0-S3',{'model_calls':16,'full_checkpoints':1},600,True,ledger=ledger,root=root)
    def role(path):return {'path':str(path),'client_path':b.fixture_unc(str(path)),'sha256':digest(path)}
    roles={'authority':role(root/'tools/local_program_authority.py'),'shim':role(root/'tools/v0_s3_budget_authority.py'),
           'python':role(Path('/usr/bin/python3')),'wsl':{'path':FIXED['wsl'],'client_path':r'C:\Windows\System32\wsl.exe','sha256':digest(FIXED['wsl'])}}
    ex={'s3_'+k:{'path':v['path'],'sha256':v['sha256']} for k,v in roles.items()}
    ex['s3_protocol']={'path':str(root/PROTOCOL),'sha256':digest(root/PROTOCOL)};write(execution,ex)
    now=time.time()
    cfg={'schema':'lvw.s3-budget/1','program':b.PROGRAM,'approval_sha256':digest(root/a.COMPLETE_APPROVAL),
         'run_id':'synthetic-p2b','stage_id':'V0-S3','candidate_sha':pre['candidate'],'child_path':str(child),'child_sha256':'0'*64,
         'ledger_path':str(ledger),'execution_path':str(execution),'execution_sha256':digest(execution),'authority_root':str(root),
         'tools':roles,'issued_at':now,'expires_at':now+500,'transport':'wsl-fixture','harness_transport':'local-fixture',
         'distribution':'Ubuntu-24.04','binding_path':str(binding),'client_binding_path':b.fixture_unc(str(binding)),
         'model':'synthetic-no-model','model_digest':'b'*64,'ollama_pid':1,'ollama_start_ticks':1}
    ch={'run_id':cfg['run_id'],'stage_id':'V0-S3','candidate_sha':pre['candidate'],'budget_ledger':str(ledger),
        'program':a.COMPLETE_APPROVAL,'program_sha256':cfg['approval_sha256'],
        'frozen_files':[{'path':PROTOCOL,'sha256':digest(root/PROTOCOL)}],'execution_bindings_required':True,
        's3_budget':{k:v for k,v in cfg.items() if k!='child_sha256'}}
    write(child,ch);cfg['child_sha256']=digest(child)
    a.bind(cfg['run_id'],child,ledger=ledger);a.bind_execution(cfg['run_id'],execution,ledger=ledger)
    b.validate_config(cfg);write(binding,cfg)
    plan={'binding':{'path':cfg['client_binding_path'],'sha256':digest(binding)},'phase':'normal',
          'candidate':pre['candidate'],'source_hashes':pre['source_hashes']}
    write(root/'driver-plan.json',plan)
    return cfg,plan


def windows():
    if os.name!='nt' or not (ROOT/'.s3-synthetic-fixture').is_file():raise ValueError('actual Windows fixture required')
    plan=json.loads((ROOT/'driver-plan.json').read_text(encoding='utf-8'))
    if set(plan)!= {'binding','phase','candidate','source_hashes'} or plan['phase'] not in ('normal','timeout','bad-receipt'):raise ValueError('plan')
    for source,seal in plan['source_hashes'].items():
        if source not in SOURCES or digest(ROOT/source)!=seal:raise ValueError('driver source seal')
    b=protocol(ROOT)
    import ctypes
    handle=ctypes.WinDLL('kernel32').GetCurrentProcess
    handle.restype=ctypes.c_void_p
    native={'pid':os.getpid(),'birth':b.process_birth(os.getpid(),types.SimpleNamespace(_handle=handle())),
            'os_name':os.name,'started_at':time.time()}
    write(ROOT/('native-'+plan['phase']+'.json'),native)
    cfg,_=b.load_binding(plan['binding']);out=[]
    if cfg['candidate_sha']!=plan['candidate']:raise ValueError('candidate mismatch')
    def action(label,ref):
        try:value=b.authorize_model_action('chat',b'{"model":"synthetic-no-model"}',binding=ref)
        except Exception as e:value={'exception':type(e).__name__,'details':getattr(e,'details',{}),'message':str(e)}
        out.append({'case':label,'result':value,'model_sends':0})
        write(ROOT/'windows-result.json',{'os_name':os.name,'native_identity':native,'python':sys.executable,'cases':out})
    action(plan['phase'],plan['binding'])
    if plan['phase']=='normal':
        action('bad-binding-hash',dict(plan['binding'],sha256='0'*64))


def owners(root):
    result=[]
    directory=root/'.s3-owned-requests'
    if directory.is_symlink():raise ValueError('journal symlink')
    for path in sorted(directory.glob('*.json')):
        if len(result)>=4 or path.is_symlink() or path.stat().st_size>4096:raise ValueError('journal bounds')
        value=json.loads(path.read_text());pid=value['pid']
        if str(uuid.UUID(path.stem))!=path.stem or value['request_id']!=path.stem:raise ValueError('request journal identity')
        if type(pid) is not int or pid<=0 or set(value['birth'])!={'linux_start_ticks'}:raise ValueError('remote identity')
        try:
            birth=protocol(ROOT).process_birth(pid)
            value['observed_birth']=birth;value['same_birth_alive']=birth==value['birth']
        except FileNotFoundError:value['same_birth_alive']=False
        result.append(value)
    return result


class Observer:
    """Only fresh UUID journals inside this marker fixture; no signal capability."""
    def __init__(self,root,binding_hash,exclude=()):
        if not (root/'.s3-synthetic-fixture').is_file():raise ValueError('observer marker')
        self.root=root;self.binding_hash=binding_hash;self.exclude=set(exclude)
        self.samples=[];self.times=[];self.error=None;self.started=time.monotonic();self.stop=threading.Event()
        self.identities={};self.absent={};self.entered=set()
        self.thread=threading.Thread(target=self.observe,daemon=True)
    def observe(self):
        try:
            for i in range(160):
                elapsed=time.monotonic()-self.started
                if elapsed>=30:break
                values=[]
                for v in owners(self.root):
                    rid=v['request_id']
                    if rid in self.exclude:continue
                    if v['binding_sha256']!=self.binding_hash:raise ValueError('journal binding mismatch')
                    identity=(v['pid'],v['birth']['linux_start_ticks'])
                    if rid in self.identities and self.identities[rid]!=identity:raise ValueError('journal identity drift')
                    self.identities[rid]=identity
                    if v['state']=='ENTERED':self.entered.add(rid)
                    self.absent[rid]=0 if v['same_birth_alive'] else self.absent.get(rid,0)+1
                    values.append(v)
                self.times.append(elapsed)
                if not self.samples or self.samples[-1]['owners']!=values:
                    self.samples.append({'elapsed':elapsed,'owners':values})
                if self.stop.is_set() and self.identities and all(n>=2 for n in self.absent.values()):break
                time.sleep(.1)
        except Exception as e:self.error=type(e).__name__+': '+str(e)
    def finish(self):
        self.stop.set();self.thread.join(timeout=max(0,30-(time.monotonic()-self.started))+1)
        gaps=[b-a for a,b in zip(self.times,self.times[1:])]
        return {'samples':self.samples,'sampling_times':self.times,'started_monotonic':self.started,'sample_count':len(self.times),'max_interval':max(gaps,default=0),
                'elapsed':time.monotonic()-self.started,'error':self.error,'joined':not self.thread.is_alive(),
                'entered':sorted(self.entered),'two_absences':bool(self.identities) and all(n>=2 for n in self.absent.values())}


def terminal(pre,meter,life,installed,fixture,claim):
    """Every failing stage is isolated; never gate persistence on observation/check."""
    global ACTIVE_METER
    ACTIVE_METER=None
    errors=[]
    def attempt(label,fn):
        try:return fn()
        except Exception as e:
            errors.append(label+': '+type(e).__name__+': '+str(e)[:200]);life['status']='BLOCKED'
    if fixture is not None:
        live=attempt('owners',lambda:owners(fixture))
        life['cleanup'].append({'fixture':str(fixture),'state':'AUDIT_RETAINED' if life['status']=='READY_FOR_REVIEW' else 'FAILED_RETAINED',
                                'owners':live,'reason':'Registered synthetic reservation/journals retained; no refund/settle0 or remote kill'})
    attempt('budget',meter.check)
    life.update(counters=meter.used,commands=meter.commands,candidate=pre['candidate'],terminal_errors=errors)
    life['preflight_sha256']=attempt('preflight hash',lambda:digest(BASE/'preflight.json'))
    attempt('installed',lambda:write(BASE/'installed-bindings.json',installed))
    attempt('terminal',lambda:write(BASE/'cross-os-lifecycle.json',life))
    expired=dict(claim,status='EXPIRED',result=life['status'],terminal_errors=list(errors))
    attempt('claim terminal',lambda:write(Path(pre['claim_path']),expired))
    attempt('local terminal',lambda:write(BASE/'consumed.json',expired))
    if errors:
        life['status']='BLOCKED'
        attempt('terminal retry',lambda:write(BASE/'cross-os-lifecycle.json',life))
        sys.stderr.write('BLOCKED terminal errors: '+json.dumps(errors)[:2000]+'\n')
    life['terminal_persisted']=not any(x.startswith(('terminal:', 'terminal retry:')) for x in errors)
    return life


def bad_helper(root,cfg):
    # Explicit fixture-only wrong-receipt process, never a debit shim.
    helper=root/'tools/bad_receipt_fixture.py'
    code="""import sys,json,os,time,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'.s3-synthetic-fixture').is_file() or not str(root).startswith('/tmp/lvw-s3-p2b-'):raise SystemExit(2)
r=json.loads(sys.stdin.buffer.read(32769))
if str(uuid.UUID(r['request_id']))!=r['request_id']:raise SystemExit(2)
birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
d=root/'.s3-owned-requests';d.mkdir(exist_ok=True)
j=d/(r['request_id']+'.json')
v=dict(request_id=r['request_id'],binding_sha256=r['binding_sha256'],pid=os.getpid(),birth={'linux_start_ticks':birth},state='ENTERED')
tmp=j.with_suffix('.writing')
with tmp.open('x') as f:json.dump(v,f)
os.link(tmp,j);tmp.unlink()
time.sleep(.3)
v['state']='FAULT_HELPER_RETURNED';tmp.write_text(json.dumps(v));os.replace(tmp,j)
r['request_id']='00000000-0000-0000-0000-000000000000'
print(json.dumps(r))
"""
    if ACTIVE_METER:ACTIVE_METER.take('output_bytes',len(code.encode()))
    helper.write_text(code)
    bad=json.loads(json.dumps(cfg));b=protocol(ROOT)
    bad['tools']['shim']={'path':str(helper),'client_path':b.fixture_unc(str(helper)),'sha256':digest(helper)}
    path=root/'bad-binding.json';bad['binding_path']=str(path);bad['client_binding_path']=b.fixture_unc(str(path))
    write(path,bad)
    return {'path':bad['client_binding_path'],'sha256':digest(path)}


def run():
    global ACTIVE_METER
    pre=json.loads((BASE/'preflight.json').read_text())
    child=json.loads((ROOT/CHILD).read_text());owner=claim_path(child)
    if pre['claim_path']!=str(owner) or pre['output_root']!=str(BASE) or pre['tools']!=FIXED or pre['limits']!=LIMITS:raise ValueError('preflight identity')
    if pre['child_sha256']!=digest(ROOT/CHILD) or pre['contract_sha256']!=digest(ROOT/CONTRACT):raise ValueError('grant drift')
    if set(pre['source_hashes'])!=set(SOURCES):raise ValueError('source set')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=pre['candidate']:raise ValueError('HEAD drift')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise ValueError('dirty candidate')
    for source,seal in pre['source_hashes'].items():
        if digest(ROOT/source)!=seal:raise ValueError('candidate tool drift')
    if pre['historical_authorization_sha256']!=digest(ROOT/'reports/unified-media/live-15/authorization.json') or pre['old_installed_seal_sha256']!=digest(ROOT/OLD_SEAL):raise ValueError('history seal drift')
    claim=claim_once(owner,pre)
    meter=Meter();installed={};life={'status':'BLOCKED','model_sends':0,'real_ledger_accesses':0,
        'real_checkpoints':0,'synthetic_debits':0,'cleanup':[],'gaps':[]};fixture=None
    try:
        # Owner, preflight/run Python+git, native/interoperability duplication conservatively reserved.
        meter.take('process_starts',10)
        # Reserve terminal independently of future budget/owner failure.
        meter.take('output_bytes',TERMINAL_RESERVE)
        ACTIVE_METER=meter
        old=json.loads((ROOT/OLD_SEAL).read_text())['tools']
        for role,path in FIXED.items():
            p=Path(path);size=p.stat().st_size
            meter.take('metadata_hash_files',1);meter.take('metadata_hash_bytes',size)
            seal=digest(p)
            installed[role]={'path':path,'sha256':seal,'bytes':size,'old_seal_match':seal==old[role]['sha256']}
            if not installed[role]['old_seal_match']:raise ValueError('installed tool changed')
        meter.seals={v['path']:v['sha256'] for v in installed.values()}
        write(BASE/'installed-seal.json',installed)
        # Internal fixed fixture writers (SQLite pages/journal, Windows results/native,
        # shim journals and pipe buffers) have one nonrefundable envelope per 3 drivers.
        # 3*1MiB exceeds 16*128KiB SQLite writes + 12*32KiB JSON + 6*32KiB pipes.
        meter.take('output_bytes',3*1048576)
        fixture=Path(tempfile.mkdtemp(prefix='lvw-s3-p2b-中文 Space-',dir='/tmp'));fixture.rmdir()
        cfg,plan=make_fixture(fixture,pre);life['binding']=cfg
        driver=[FIXED['windows_python'],'-I','-B',protocol(ROOT).fixture_unc(str(fixture/HARNESS)),'--windows']
        meter.take('synthetic_debits',16)  # reserved ceiling, actual separately queried
        normal_observer=Observer(fixture,plan['binding']['sha256']);normal_observer.thread.start()
        try:meter.run(driver,process_cost=8)
        finally:life['normal_observer']=normal_observer.finish()
        normal=json.loads((fixture/'windows-result.json').read_text(encoding='utf-8'));life['normal']=normal
        if normal['os_name']!='nt' or normal['cases'][0]['result'].get('status')!='DEBITED':raise ValueError('no actual Windows debit')
        with sqlite3.connect(fixture/'fixture.sqlite') as db:calls=db.execute('SELECT calls FROM children').fetchone()[0]
        life['calls_after_normal']=calls
        if calls!=1 or any(x['result'].get('status')=='DEBITED' for x in normal['cases'][1:]):raise ValueError('negative debit boundary')
        original_binding=plan['binding']
        plan['binding']=bad_helper(fixture,cfg);plan['phase']='bad-receipt';write(fixture/'driver-plan.json',plan)
        old_ids=[v['request_id'] for v in owners(fixture)]
        observer=Observer(fixture,plan['binding']['sha256'],old_ids);observer.thread.start()
        try:meter.run(driver,process_cost=4)
        finally:life['bad_observer']=observer.finish()
        life['bad_receipt']=json.loads((fixture/'windows-result.json').read_text(encoding='utf-8'))
        bad=life['bad_receipt']['cases'][0]['result']
        if bad.get('details',{}).get('exit_code')!=0 or bad.get('details',{}).get('subcode')!='S3_BRIDGE_RECEIPT_INVALID':raise ValueError('bad helper not rejected as receipt')
        plan['binding']=original_binding;plan['phase']='timeout';write(fixture/'driver-plan.json',plan)
        lock=sqlite3.connect(fixture/'fixture.sqlite',check_same_thread=False);lock.execute('BEGIN IMMEDIATE')
        life['lock']={'acquired_monotonic':time.monotonic()}
        def release():
            try:lock.rollback();lock.close()
            finally:life['lock']['released_monotonic']=time.monotonic()
        timer=threading.Timer(13,release);timer.start()
        old_ids=[v['request_id'] for v in owners(fixture)]
        observer=Observer(fixture,original_binding['sha256'],old_ids);observer.thread.start()
        try:
            meter.run(driver,process_cost=4)
            life['wrapper_return_monotonic']=time.monotonic()
        finally:
            life['timeout_observer']=observer.finish()
            timer.join(timeout=1)
        life['timeout']=json.loads((fixture/'windows-result.json').read_text(encoding='utf-8'))
        with sqlite3.connect(fixture/'fixture.sqlite') as db:life['synthetic_debits']=db.execute('SELECT calls FROM children').fetchone()[0]
        detail=life['timeout']['cases'][0]['result'].get('details',{})
        if detail.get('error')!='TIMEOUT':raise ValueError('timeout not witnessed')
        for name in ('normal_observer','bad_observer','timeout_observer'):
            o=life[name]
            if o['error'] or not o['joined'] or not o['two_absences'] or o['max_interval']>.25:raise ValueError('UNKNOWN_CLEANUP '+name)
        if not life['timeout_observer']['entered']:raise ValueError('missing ENTERED boundary')
        a=module('_p2b_close',fixture/'tools/local_program_authority.py')
        a.close_retaining_reservation(cfg['run_id'],ledger=fixture/'fixture.sqlite')
        life['reservation']='UNKNOWN_ACK retained; no refund or settle0'
        life['timeout_outcome']='EXPECTED_FAILCLOSED_UNKNOWN_ACK_REMOTE_EXIT_OBSERVED'
        life['remote_kills']=0;life['status']='READY_FOR_REVIEW'
        life['gaps']=['CPU fixture only; no product/production/quality or remote numeric exit claim',
                      'Other historical metadata reused without revalidation']
    except Exception as e:
        life['status']='BLOCKED';life['error']={'type':type(e).__name__,'message':str(e)}
    finally:terminal(pre,meter,life,installed,fixture,claim)
    return life


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--preflight':
        value=preflight(sys.argv[2]);print(json.dumps({'status':'PREFLIGHT','sha256':digest(BASE/'preflight.json')}))
    elif sys.argv[1:]==['--run']:
        value=run();print(json.dumps({'status':value['status'],'terminal_persisted':value.get('terminal_persisted')}))
        sys.exit(0 if value['status']=='READY_FOR_REVIEW' and value.get('terminal_persisted') else 1)
    elif sys.argv[1:]==['--windows']:windows()
    else:raise SystemExit('fixed modes only')
