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

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'.agent-governance/runtime/receipts/s3-p2b-01'
CHILD = 'reports/v0-s3/product-gate0/runtime-binding-child-01.json'
CONTRACT = 'reports/v0-s3/product-gate0/p2-binding-contract.md'
PROTOCOL = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
CORE = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py'
HARNESS = 'tools/v0_s3_runtime_binding.py'
SOURCES = [HARNESS, PROTOCOL, CORE, 'tools/v0_s3_budget_authority.py',
           'tools/local_program_authority.py',
           'reports/authorization-program-v1-local-02.request.json',
           'reports/authorization-program-v1-local-02.approval.json',
           'reports/authorization-program-v1-complete-03.request.json',
           'reports/authorization-program-v1-complete-03.approval.json']
FIXED = {
 'windows_python':'/mnt/c/ComfyUI-aki-v2/python/python.exe',
 'wsl':'/mnt/c/Windows/System32/wsl.exe',
 'comfy_main':'/mnt/c/ComfyUI-aki-v2/ComfyUI/main.py',
 'comfy_nodes':'/mnt/c/ComfyUI-aki-v2/ComfyUI/nodes.py',
 'ollama':'/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe',
 'python':'/usr/bin/python3', 'ffmpeg':'/usr/bin/ffmpeg',
 'ffprobe':'/usr/bin/ffprobe', 'node':'/usr/bin/node'}
LIMITS = {'wall_seconds':1200, 'process_starts':64,'per_command_seconds':30,
          'metadata_hash_files':24,'metadata_hash_bytes':268435456,
          'output_bytes':16777216,'synthetic_debits':16}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''): h.update(block)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


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
    def take(self,key,n):
        if type(n) is not int or n<0 or self.used[key]+n>LIMITS[key]: raise ValueError('budget '+key)
        self.used[key]+=n
        self.check()
    def check(self):
        self.used['wall_seconds']=time.monotonic()-self.started
        if self.used['wall_seconds']>LIMITS['wall_seconds']: raise ValueError('wall budget')
    def run(self,command,process_cost=1,observe=None):
        if command[0] not in self.seals or digest(command[0])!=self.seals[command[0]]:raise ValueError('installed executable drift')
        self.take('process_starts',process_cost)
        # Every caller supplies a literal/frozen internal command. No public argv API.
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        record={'command':command,'pid':p.pid,'birth':protocol(ROOT).process_birth(p.pid,p),
                'process_start_reservation':process_cost}
        self.commands.append(record)
        buffers=[bytearray(),bytearray()];overflow=threading.Event()
        def drain(i,pipe):
            while True:
                chunk=pipe.read(4096)
                if not chunk:break
                if len(buffers[i])+len(chunk)>1048576:overflow.set();break
                buffers[i].extend(chunk)
        threads=[threading.Thread(target=drain,args=(i,pipe)) for i,pipe in enumerate((p.stdout,p.stderr))]
        for t in threads:t.start()
        start=time.monotonic()
        try:
            while p.poll() is None:
                if observe:observe(time.monotonic()-start)
                if overflow.is_set() or time.monotonic()-start>=30:
                    p.kill();record['error']='OUTPUT_LIMIT' if overflow.is_set() else 'TIMEOUT';break
                time.sleep(.05)
        finally:
            record['exit_code']=p.wait(timeout=1)
            for t in threads:t.join(timeout=1)
            record['threads_joined']=not any(t.is_alive() for t in threads)
            if record['threads_joined']:
                p.stdout.close();p.stderr.close()
            record['pipe_closed']=[p.stdout.closed,p.stderr.closed]
            for b in buffers:self.take('output_bytes',len(b))
            record['stdout']=buffers[0].decode('utf-8',errors='replace')
            record['stderr']=buffers[1].decode('utf-8',errors='replace')
            record['elapsed']=time.monotonic()-start
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
    BASE.mkdir(parents=True,exist_ok=True)
    if (BASE/'consumed.json').exists():raise ValueError('batch already consumed')
    value={'candidate':candidate,'child_sha256':digest(ROOT/CHILD),'contract_sha256':digest(ROOT/CONTRACT),
           'source_hashes':{s:digest(ROOT/s) for s in SOURCES},'tools':FIXED,'output_root':str(BASE),
           'limits':LIMITS,'distribution':'Ubuntu-24.04',
           'fixture_parent':'/tmp','unc_prefix':r'\\wsl.localhost\Ubuntu-24.04',
           'cleanup':'Only temporary fixture after confirmed remote exit; unknown retains reservation and root; no remote kill protocol',
           'real_machine_accesses':0}
    write(BASE/'preflight.json',value)
    return value


def make_fixture(root,pre):
    root.mkdir();(root/'.s3-synthetic-fixture').touch()
    for name in SOURCES:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
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
    if set(plan)!= {'binding','phase','candidate','source_hashes'} or plan['phase'] not in ('normal','timeout'):raise ValueError('plan')
    for source,seal in plan['source_hashes'].items():
        if source not in SOURCES or digest(ROOT/source)!=seal:raise ValueError('driver source seal')
    b=protocol(ROOT);cfg,_=b.load_binding(plan['binding']);out=[]
    if cfg['candidate_sha']!=plan['candidate']:raise ValueError('candidate mismatch')
    def action(label,ref):
        try:value=b.authorize_model_action('chat',b'{"model":"synthetic-no-model"}',binding=ref)
        except Exception as e:value={'exception':type(e).__name__,'details':getattr(e,'details',{}),'message':str(e)}
        out.append({'case':label,'result':value,'model_sends':0})
        write(ROOT/'windows-result.json',{'os_name':os.name,'python':sys.executable,'cases':out})
    action(plan['phase'],plan['binding'])
    if plan['phase']=='normal':
        action('bad-binding-hash',dict(plan['binding'],sha256='0'*64))
        child=ROOT/'child.json';held=ROOT/'child.held';child.rename(held)
        try:action('missing-child',plan['binding'])
        finally:held.rename(child)


def owners(root):
    result=[]
    for path in sorted((root/'.s3-owned-requests').glob('*.json')):
        value=json.loads(path.read_text());pid=value['pid']
        try:
            birth=protocol(ROOT).process_birth(pid)
            value['observed_birth']=birth;value['same_birth_alive']=birth==value['birth']
        except FileNotFoundError:value['same_birth_alive']=False
        result.append(value)
    return result


def run():
    pre=json.loads((BASE/'preflight.json').read_text())
    if pre['output_root']!=str(BASE) or pre['tools']!=FIXED or pre['limits']!=LIMITS:raise ValueError('preflight identity')
    if pre['child_sha256']!=digest(ROOT/CHILD) or pre['contract_sha256']!=digest(ROOT/CONTRACT):raise ValueError('grant drift')
    if set(pre['source_hashes'])!=set(SOURCES):raise ValueError('source set')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=pre['candidate']:raise ValueError('HEAD drift')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT):raise ValueError('dirty candidate')
    for s,h in pre['source_hashes'].items():
        if digest(ROOT/s)!=h:raise ValueError('candidate tool drift')
    # Exclusive durable consumption occurs BEFORE any fixed installed-tool access.
    with (BASE/'consumed.json').open('x') as f:json.dump({'status':'RUNNING','candidate':pre['candidate'],'preflight_sha256':digest(BASE/'preflight.json')},f)
    meter=Meter();installed={};life={'status':'BLOCKED','model_sends':0,'real_ledger_accesses':0,
        'real_checkpoints':0,'synthetic_debits':0,'cleanup':[],'gaps':[]};fixture=None
    try:
        for role,path in FIXED.items():
            p=Path(path);record={'path':path,'exists':p.is_file(),'version':None};installed[role]=record
            if p.is_file():
                record['realpath']=str(p.resolve());size=p.stat().st_size
                meter.take('metadata_hash_files',1);meter.take('metadata_hash_bytes',size)
                record['sha256']=digest(p);record['bytes']=size
        if not all(installed[r]['exists'] for r in ('windows_python','wsl','python')):
            raise ValueError('fixed Windows/WSL required tools missing; no path search')
        meter.seals={v['path']:v['sha256'] for v in installed.values() if 'sha256' in v}
        write(BASE/'installed-seal.json',{'candidate':pre['candidate'],'preflight_sha256':digest(BASE/'preflight.json'),'tools':installed})
        life['installed_seal_sha256']=digest(BASE/'installed-seal.json')
        commands=[ [FIXED['windows_python'],'-I','-B','-c',"import os,sys,importlib.metadata as m,json\npackages={}\nfor n in ('Pillow','numpy','av'):\n try: packages[n]=m.version(n)\n except m.PackageNotFoundError: packages[n]=None\nprint(json.dumps({'os':os.name,'version':sys.version,'packages':packages}))"],
                  [FIXED['python'],'--version'],[FIXED['ffmpeg'],'-version'],[FIXED['ffprobe'],'-version'],[FIXED['node'],'--version']]
        for command in commands:
            if Path(command[0]).is_file():meter.run(command)
        # The temporary directory is on the actual WSL filesystem, not /mnt/c.
        fixture=Path(tempfile.mkdtemp(prefix='lvw-s3-p2b-中文 Space-',dir='/tmp'));fixture.rmdir()
        cfg,plan=make_fixture(fixture,pre);life['binding']=cfg
        driver=[FIXED['windows_python'],'-I','-B',protocol(ROOT).fixture_unc(str(fixture/HARNESS)),'--windows']
        record=meter.run(driver,process_cost=5)
        if record['exit_code']!=0:raise ValueError('Windows driver failed')
        normal=json.loads((fixture/'windows-result.json').read_text(encoding='utf-8'));life['normal']=normal
        life['normal_owners']=owners(fixture)
        if normal['os_name']!='nt' or normal['cases'][0]['result'].get('status')!='DEBITED':raise ValueError('no actual Windows debit')
        with sqlite3.connect(fixture/'fixture.sqlite') as db:
            calls=db.execute('SELECT calls FROM children').fetchone()[0]
        life['calls_after_normal']=calls
        if calls!=1 or any(x['result'].get('status')=='DEBITED' for x in normal['cases'][1:]):raise ValueError('negative debit boundary')
        # Lock causes actual authority wait without changing production policy.
        lock=sqlite3.connect(fixture/'fixture.sqlite',check_same_thread=False);lock.execute('BEGIN IMMEDIATE')
        released=threading.Event()
        def release():
            try:lock.rollback();lock.close()
            finally:released.set()
        timer=threading.Timer(20,release);timer.start()
        plan['phase']='timeout';write(fixture/'driver-plan.json',plan)
        samples=[];seen=set()
        def observe(elapsed):
            second=int(elapsed)
            if second in (1,11,13,19) and second not in seen:
                seen.add(second);samples.append({'elapsed':elapsed,'owners':owners(fixture)})
        try:record=meter.run(driver,process_cost=3,observe=observe)
        finally:timer.join(timeout=21)
        life['timeout_command']=record;life['timeout_observations']=samples
        life['timeout']=json.loads((fixture/'windows-result.json').read_text(encoding='utf-8'))
        life['final_owners']=owners(fixture)
        with sqlite3.connect(fixture/'fixture.sqlite') as db:
            life['synthetic_debits']=db.execute('SELECT calls FROM children').fetchone()[0]
        meter.take('synthetic_debits',life['synthetic_debits'])
        # Unknown result is NEVER refunded or settled as zero, even if it later exits.
        a=module('_p2b_close',fixture/'tools/local_program_authority.py')
        a.close_retaining_reservation(cfg['run_id'],ledger=fixture/'fixture.sqlite')
        life['reservation']='retained; no refund or settle0'
        detail=life['timeout']['cases'][0]['result'].get('details',{})
        life['status']='READY_FOR_REVIEW' if detail.get('error')=='TIMEOUT' and not any(x['same_birth_alive'] for x in life['final_owners']) else 'BLOCKED'
        life['timeout_outcome']='UNKNOWN_RETAINED'
        life['remote_kills']=0
        life['gaps']=['Bad receipt is covered only by P1 synthetic tests, not a real cross-OS bad-receipt helper',
                      'No production ledger access or model/service/network isolation claim',
                      'Remote cleanup protocol not implemented; natural bounded lock release observed']
    except Exception as e:
        life['error']={'type':type(e).__name__,'message':str(e)}
    finally:
        if fixture is not None:
            live=owners(fixture);life['final_owner_observation']=live
            # Keep the synthetic reservation/database as evidence on any uncertain run.
            life['cleanup'].append({'fixture':str(fixture),'state':'FAILED_RETAINED','owners':live,
                                    'reason':'Retain unknown reservation and source copies for coordinator; no remote kill'})
        meter.check();life['counters']=meter.used;life['commands']=meter.commands
        life['preflight_sha256']=digest(BASE/'preflight.json');life['candidate']=pre['candidate']
        write(BASE/'installed-bindings.json',installed);write(BASE/'cross-os-lifecycle.json',life)
        write(BASE/'consumed.json',{'status':'EXPIRED','result':life['status'],'candidate':pre['candidate']})
    return life


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--preflight':print(json.dumps(preflight(sys.argv[2])))
    elif sys.argv[1:]==['--run']:print(json.dumps(run(),ensure_ascii=False))
    elif sys.argv[1:]==['--windows']:windows()
    else:raise SystemExit('fixed modes only')
