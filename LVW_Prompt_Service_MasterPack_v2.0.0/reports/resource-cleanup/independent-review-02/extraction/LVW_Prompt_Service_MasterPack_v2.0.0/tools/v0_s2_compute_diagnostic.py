"""One finite zero-inference owner diagnosis under the persistent V0 program."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace

from tools import v0_verification_authority as authority
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_runtime import NativeRuntime,base
from tools.v0_s2_driver import comfy_wrapper
from tools.v0_s2_browser_owner import birth
from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_execution_bindings import plain
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources import validate_snapshot
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import admit
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import run_bounded

REQUEST='reports/v0-s2/authorization-s2-compute-owner-diagnostic-01.request.json'
HARNESS='tools/v0_s2_compute_diagnostic.py'
RUN='compute-owner-diagnostic-01'
PAYLOAD=['tools','LVW_V0_RuntimePatch',authority.PROGRAM,REQUEST,'.agent-governance/stages/V0-S2',
         'reports/v0-s1/wp-s1-03-phase-a/live_probe.py']


def classify(pids,rows,roots):
    """Birth-aware labels only; never changes the product allowlist."""
    if len(pids)>64 or len(rows)>512:raise ValueError('diagnostic PID bound')
    indexed={r['pid']:r for r in rows};labels=[]
    for pid in pids:
        current=pid;seen=set();label='UNRESOLVED_OR_UNOWNED';child_birth=None
        for _ in range(8):
            if current in seen:break
            seen.add(current);row=indexed.get(current)
            if row is None or type(row.get('process_start_ticks')) is not int or row['process_start_ticks']<=0:break
            birth=row['process_start_ticks']
            if child_birth is not None and birth>child_birth:break
            matches=[name for name,proof in roots.items() if proof['pid']==current and proof['start_ticks']==birth]
            if matches:label=matches[0] if current==pid else matches[0]+'_DESCENDANT';break
            current=row['parent_pid'];child_birth=birth
        labels.append({'pid':pid,'classification':label})
    return labels


class Driver(NativeRuntime):
    def __init__(self,args,evidence,directory,child):
        super().__init__(args,evidence);self.directory=directory;self.child=child;self.program_hash=child['program_sha256']
        self.cleanup_mode=False;self.commands=[];self.nvidia_calls=0;self.groups=0;self.wsl_calls=0
        self.starts={'ollama':0,'comfy':0}
        self.launches=[];self.command_release_unproven=False

    def guard(self):
        if self.cleanup_mode:return
        authority.validate(cp.repository_json(authority.PROGRAM),'V0-S2')
        if cp.file_hash(cp.ROOT/authority.PROGRAM)!=self.program_hash or time.time()>=self.child['expires_at']:
            raise ValueError('verification child revoked or expired')

    def command(self,argv,kind):
        self.guard()
        expected=self.child['command_executables'].get(argv[0])
        if expected is None or cp.file_hash(plain(Path(argv[0])))!=expected:raise ValueError('command executable identity changed')
        if len(self.commands)>=(128 if self.cleanup_mode else 96):raise ValueError('reserved diagnostic command budget')
        if kind=='wsl':
            if self.wsl_calls>=4:raise ValueError('WSL query budget')
            self.wsl_calls+=1
        ordinal=len(self.commands)+1;row={'ordinal':ordinal,'kind':kind,'argv':argv,'wall_seconds':time.time()};self.commands.append(row)
        cp.write_new(self.directory/f'command-{ordinal:03d}.json',row)
        collected=[]
        def record(p):
            collected.append(p);row['exit_code']=p.returncode
            for stream,data in [('stdout',p.stdout),('stderr',p.stderr)]:
                (self.directory/f'command-{ordinal:03d}.{stream}.log').write_bytes(data)
                row[stream+'_sha256']=hashlib.sha256(data).hexdigest()
        try:
            p=run_bounded(argv,timeout_seconds=30,output_limit=262144,on_result=record)
            return p.stdout.decode('utf-8-sig').strip()
        except BaseException as error:
            row['error_type']=type(error).__name__;row['error_code']=getattr(error,'code',None)
            if not collected:self.command_release_unproven=True
            raise
        finally:cp.write_new(self.directory/f'command-{ordinal:03d}.result.json',row)

    def _windows_path(self,value,*,expected=None):
        # These frozen tools/roots are on C:. No PATH-based wslpath execution.
        if value.startswith('/mnt/c/'):
            result='C:\\'+value[len('/mnt/c/'):].replace('/','\\')
        elif len(value)>3 and value[1:3] in (':\\',':/'):
            result=value
        else:raise ValueError('diagnostic path is outside bound Windows drive')
        if expected is not None and base.normalized_windows_path(result).casefold()!=base.normalized_windows_path(expected).casefold():
            raise ValueError('diagnostic path does not match frozen tool')
        return result

    def launch_owned(self,name,wrapper,log):
        self.guard()
        for key in ('powershell','comfy_python','comfy_main','ollama_exe','ffmpeg_exe'):
            row=self.child['tool_bindings'][key]
            if cp.file_hash(plain(Path(row['path'])))!=row['sha256']:raise ValueError('service tool changed')
        argv=[self.args.powershell,'-NoProfile','-NonInteractive','-File',self._windows_path(str(wrapper))]
        row={'owner':name,'argv':argv,'wrapper_sha256':cp.file_hash(wrapper),'wall_seconds':time.time()}
        ordinal=len(self.launches)+1;self.launches.append(row)
        cp.write_new(self.directory/f'launch-{ordinal}.json',row)
        stream=log.open('x',encoding='utf-8')
        try:process=subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT)
        except BaseException:stream.close();raise
        self.owned.append((name,process,stream));pid_file=wrapper.with_suffix('.pid')
        self._wrapper_handles[str(pid_file)]=process
        row['parent_handle_birth']=birth(process.pid)
        cp.write_new(self.directory/f'launch-{ordinal}.started.json',row)
        return pid_file

    def _powershell(self,script):
        prefix="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        return self.command([self.args.powershell,'-NoProfile','-NonInteractive','-Command',prefix+script],'native')

    def _json_request(self,url,*,payload=None,timeout=20,observer=None):
        self.guard()
        allowed={base.OLLAMA_URL+p for p in ('/api/version','/api/tags','/api/ps')}|{base.COMFY_URL+'/object_info'}
        if payload is not None or url not in allowed:raise ValueError('diagnostic permits metadata GET only')
        return super()._json_request(url,timeout=timeout,observer=observer)

    def submit(self,*args):raise ValueError('zero public submissions in diagnostic')

    def start_ollama(self,*args):
        self.guard()
        if self.starts['ollama']:raise ValueError('single Ollama start only')
        self.starts['ollama']+=1
        log=Path(args[0]);self.ollama_log=log;wrapper=log.parent/'ollama-wrapper.ps1';pid_file=wrapper.with_suffix('.pid')
        wrapper.write_text(base.ollama_wrapper_text(self._windows_path(self.args.ollama_exe),self._windows_path(str(pid_file))),encoding='utf-8-sig')
        self.ollama_wrapper_pid_file=self.launch_owned('ollama_wrapper',wrapper,log)

    def start_comfy(self,*args):
        self.guard()
        if self.starts['comfy']:raise ValueError('single Comfy start only')
        self.starts['comfy']+=1
        root,log=args;(root/'user').mkdir(exist_ok=False)
        wrapper=root/'comfy-wrapper.ps1';pid_file=wrapper.with_suffix('.pid')
        wrapper.write_text(comfy_wrapper(self._windows_path(self.args.comfy_python,expected=base.AUTHORIZED_COMFY_PYTHON),
            self._windows_path(self.args.comfy_main,expected=base.AUTHORIZED_COMFY_MAIN),self._windows_path(str(root)),
            self._windows_path(str(pid_file)),self._windows_path(self.args.ffmpeg_exe),None,warm=False,audit=False),encoding='utf-8-sig')
        self.launch_owned('comfy',wrapper,Path(log))
        self.wait_json(base.COMFY_URL+'/object_info',timeout=120)
        self._prove_listener_owned(8191,pid_file,'python.exe')

    def snapshot(self,label,roots):
        self.guard()
        if self.groups>=2:raise ValueError('two sample groups only')
        self.groups+=1;self.nvidia_calls+=2
        if cp.file_hash(Path(self.args.nvidia_exe))!=self.child['tool_bindings']['nvidia_exe']['sha256']:
            raise ValueError('NVIDIA binary changed')
        binary=base.ps_quote(self._windows_path(self.args.nvidia_exe))
        script=(f'$g=@(& {binary} --query-gpu=memory.total,memory.used,memory.free --format=csv,noheader,nounits);if($LASTEXITCODE -ne 0){{throw "GPU_QUERY"}};'
            f'$c=@(& {binary} --query-compute-apps=pid --format=csv,noheader,nounits);if($LASTEXITCODE -ne 0){{throw "PID_QUERY"}};'
            '$ids=@($c|Where-Object {$_ -match "^\\s*[0-9]+\\s*$"}|ForEach-Object {[int]$_.Trim()});'
            'if($ids.Count -gt 64){throw "PID_LIMIT"};$rows=@{};'
            'foreach($start in $ids){$cur=[int]$start;for($depth=0;$depth -lt 8;$depth++){if($cur -le 0 -or $rows.ContainsKey([string]$cur)){break};'
            '$p=Get-CimInstance Win32_Process -Filter ("ProcessId = "+$cur);if(!$p){break};$gp=Get-Process -Id $cur -ErrorAction SilentlyContinue;if(!$gp){break};'
            'try{$bt=$null;$ct=$null;try{$st=$gp.StartTime;if($st){$bt=[long]$st.ToUniversalTime().Ticks}}catch{};if($p.CreationDate){$ct=[long]$p.CreationDate.ToUniversalTime().Ticks};'
            '$rows[[string]$cur]=[ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;name=[string]$p.Name;executable=[string]$p.ExecutablePath;process_start_ticks=$bt;creation_ticks=$ct}}finally{$gp.Dispose()};$cur=[int]$p.ParentProcessId}};'
            '[ordered]@{gpu_csv=($g -join "`n");compute_csv=($c -join "`n");processes=@($rows.Values);ram_available_mib=[long][Math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024.0);wall_ticks=[long][datetime]::UtcNow.Ticks}|ConvertTo-Json -Depth 6 -Compress')
        value=json.loads(self._powershell(script))
        pids=[int(line.strip()) for line in value['compute_csv'].splitlines() if line.strip()]
        rows=value['processes'];rows=[rows] if isinstance(rows,dict) else rows
        value.update(label=label,compute_pids=pids,classification=classify(pids,rows,roots),owned_roots=roots)
        wsl='/usr/lib/wsl/lib/nvidia-smi'
        value['wsl_gpu_csv']=self.command([wsl,'--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],'wsl')
        value['wsl_compute_csv']=self.command([wsl,'--query-compute-apps=pid','--format=csv,noheader,nounits'],'wsl')
        if 'COMFY' in roots:
            try:value['production_validator']=validate_snapshot(value['gpu_csv'],value['compute_csv'],value['ram_available_mib'],owner_pid=roots['COMFY']['pid'])
            except Exception as error:value['production_validator_error']={'type':type(error).__name__,'code':getattr(error,'code',None),'details':getattr(error,'details',None)}
        cp.write_new(self.directory/(label+'.json'),value);return value


def run(candidate,run_id=RUN):
    if not re.fullmatch('compute-owner-diagnostic-[0-9]{2}',run_id):raise ValueError('diagnostic run identity invalid')
    request=cp.repository_json(REQUEST);program=cp.repository_json(authority.PROGRAM)
    authority.validate(program,'V0-S2');identity=seal_candidate(cp.ROOT,candidate,PAYLOAD)
    # Existing terminal evidence supplies expected identities only. Fresh critical
    # binary/entrypoint checks below are diagnostic binding, not full Stage seals.
    historical=cp.repository_json('reports/v0-s2/full-profile-lifecycle-correction-01/receipt.json')
    old=cp.STATE_ROOT/'full-profile-lifecycle-correction-01/terminal.json'
    if cp.file_hash(old)!=historical['raw_terminal_sha256']:raise ValueError('terminal reference changed')
    previous=json.loads(old.read_bytes())['runtime_evidence']['default']
    tools=previous['binding_proof']['tool_bindings']
    def verify_tools():
        for row in tools.values():
            if cp.file_hash(plain(Path(row['path'])))!=row['sha256']:raise ValueError('installed critical identity changed')
    verify_tools()
    child=authority.child(program,stage='V0-S2',run_id=run_id,candidate=candidate,harness_sha256=cp.file_hash(cp.ROOT/HARNESS),
        program_sha256=cp.file_hash(cp.ROOT/authority.PROGRAM),budget=request['budget'],max_seconds=request['max_seconds'])
    child.update(source_payload_sha256=identity['payload_sha256'],request=REQUEST,request_sha256=cp.file_hash(cp.ROOT/REQUEST),
                 tool_bindings=tools,ports=[8191,11434],cleanup_policy='original registered roots and original owned PID/birth only')
    from tools.v0_s2_resource_admission import expected_tools
    wsl=expected_tools(cp)['wsl_nvidia']
    child['command_executables']={tools['powershell']['path']:tools['powershell']['sha256'],wsl['path']:wsl['sha256']}
    directory=cp.STATE_ROOT/run_id;directory.mkdir(exist_ok=False)
    cp.write_new(directory/'active-child.json',child);(directory/'lease.closed').write_bytes(b'0')
    root=None;driver=None;context=None;archive=OwnedArchive(directory,run_id=run_id,candidate_sha=candidate,
        authorization_sha256=hashlib.sha256(cp.canonical(child)).hexdigest(),authorize=lambda *args:None)
    result={'run_id':run_id,'candidate_sha':candidate,'decision':'NO_GO','stage_pass_claim':False,'provider_calls':0,'media_reads':0,'browser_starts':0,'complete_stage_checkpoints':0}
    try:
        root=Path(tempfile.mkdtemp(prefix='lvw-compute-diag-',dir=directory)).resolve();archive.register(root,'default')
        for name in ['input','output','temp','custom_nodes']:(root/name).mkdir()
        args=SimpleNamespace(run_id=run_id,max_public_submissions=1,max_loopback_requests=256,max_native_clock_reads=16,
            warm_benchmark=False,native_audit=False,ffprobe_exe=None,
            **{name:tools[name]['path'] for name in ('powershell','comfy_python','comfy_main','ollama_exe','ffmpeg_exe','nvidia_exe')})
        evidence={'owned_run_root':str(root)};driver=Driver(args,evidence,directory,child)
        context=SimpleNamespace(root=root,driver=driver,binding={'candidate_sha':candidate,'authorization_sha256':archive.auth})
        source=cp.ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge';target=root/'custom_nodes/lvw_v0_bridge'
        shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        prefix='LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
        expected={p[len(prefix):]:d for p,d in identity['execution_artifact_sha256'].items() if p.startswith(prefix)}
        if {p.relative_to(target).as_posix():cp.file_hash(p) for p in target.rglob('*') if p.is_file()}!=expected:raise ValueError('deployed code changed')
        # Preflight checks ports/processes before any owned service starts.
        driver._powershell("$x=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in 8191,11434};if(@($x).Count){throw 'PORT_BUSY'};$p=Get-CimInstance Win32_Process|Where-Object {($_.Name -match 'ollama') -or (($_.Name -match 'python') -and ($_.CommandLine -match 'ComfyUI'))};if(@($p).Count){throw 'PROCESS_BUSY'}")
        result['before']=driver.snapshot('before-services',{})
        before=result['before']
        if before['ram_available_mib']<2048:raise ValueError('host RAM below existing minimum')
        gpu=[int(v.strip()) for v in before['gpu_csv'].split(',')];admit([[0,*gpu]])
        driver.start_ollama(root/'ollama.log');result['no_cloud']=driver.no_cloud_remote_gate();result['model']=driver.verify_model()
        if result['model']['digest']!=previous['model']['digest']:raise ValueError('selected model metadata changed')
        driver.start_comfy(root,root/'comfy.log');result['registry_nodes']=sorted(driver.registry())
        roots={label:{'pid':proof['listener_pid'],'start_ticks':proof['listener_process_start_ticks']}
               for label,port in [('COMFY',8191),('OLLAMA',11434)] for proof in [driver.listener_births[port]]}
        result['after']=driver.snapshot('after-services',roots)
        if driver._json_request(base.OLLAMA_URL+'/api/ps')[1].get('models')!=[]:raise ValueError('diagnostic unexpectedly resident model')
        verify_tools()
        if seal_candidate(cp.ROOT,candidate,PAYLOAD)!=identity:raise ValueError('diagnostic source drift')
        result['decision']='COMPUTE_OWNER_DIAGNOSTIC_COMPLETE_NOT_PRODUCT_ACCEPTANCE'
    except BaseException as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        if driver is not None:
            driver.cleanup_mode=True
            try:
                result['cleanup']=driver.cleanup()
                if driver.command_release_unproven:result['cleanup']['proven']=False
                if result['cleanup']['proven']:result['archive']=archive(context,result['cleanup'])
                else:result['decision']='NO_GO'
            except Exception as error:result.update(decision='NO_GO',cleanup_error=type(error).__name__+':'+str(error))
            result['commands']=driver.commands;result['request_ledger']=driver.request_ledger
            result['launches']=driver.launches
            for row in result['launches']:
                handle=next((p for name,p,stream in driver.owned if name==row['owner']),None)
                row['exit_code']=handle.poll() if handle is not None else None
        result['program_remains_active']=cp.repository_json(authority.PROGRAM)['status']=='ACTIVE'
        result['root_retained']=root is not None and root.exists()
        cp.write_new(directory/'terminal.json',result)
        with (directory/'lease.closed').open('r+b') as stream:stream.write(b'1');stream.flush();os.fsync(stream.fileno())
        cp.write_new(directory/'terminal-child.json',authority.expire(child,'COMPLETE' if result['decision'].startswith('COMPUTE_OWNER') else 'NO_GO','terminal.json'))
        report=cp.ROOT/'reports/v0-s2'/run_id;report.mkdir(exist_ok=False)
        # No unrelated executable paths, command lines or raw PIDs in source repo.
        public={k:result[k] for k in ('run_id','candidate_sha','decision','stage_pass_claim','provider_calls','media_reads','browser_starts','complete_stage_checkpoints','program_remains_active','root_retained')}
        for label in ('before','after'):
            if label in result:
                sample=result[label];public[label]={'gpu_csv':sample['gpu_csv'],'compute_count':len(sample['compute_pids']),
                    'classification':[v['classification'] for v in sample['classification']],
                    'production_validator_error':sample.get('production_validator_error')}
        public.update(error_code=(result.get('error_code') or '').split(':',1)[0] or None,cleanup_proven=result.get('cleanup',{}).get('proven',False),
            raw_terminal_sha256=cp.file_hash(directory/'terminal.json'),command_count=len(result.get('commands',[])),
            installed_binding_scope='critical executables/entrypoints and exact deployed source; not a full Stage dependency seal')
        cp.write_new(report/'receipt.json',public)
    return public


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--run-id',default=RUN);a=p.parse_args()
    r=run(a.candidate,a.run_id);print(json.dumps(r));raise SystemExit(r['decision']=='NO_GO')
