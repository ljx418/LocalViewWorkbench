"""S2 lifecycle adapter; constructing it does not authorize or start services.

Reuse the recorded S1 process ownership/terminal checks without changing its
historical Harness. S2 replaces HTTP, localized PowerShell output handling,
submission accounting, and the transient decoder configuration.
"""
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import threading

from tools.v0_s2_http import LoopbackClient,ControlError
import time

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'
spec = importlib.util.spec_from_file_location('lvw_s2_lifecycle_base', LEGACY)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def comfy_wrapper(python, main, directory, pid_file, ffmpeg, ffprobe, *, warm=False,audit=False):
    # Process environment only, never user/machine environment or PATH writes.
    environment=("foreach($name in @('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','PYTHONINSPECT','PYTHONUSERBASE',"
        "'PYTHONOPTIMIZE','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')){Remove-Item ('Env:'+$name) -ErrorAction SilentlyContinue}\n"
        "$env:PYTHONDONTWRITEBYTECODE='1'\n$env:PYTHONNOUSERSITE='1'\n"
        "$env:HF_HUB_OFFLINE='1'\n$env:TRANSFORMERS_OFFLINE='1'\n$env:HF_DATASETS_OFFLINE='1'\n"
        "$env:NO_PROXY='127.0.0.1,localhost'\n")
    temporary=directory.rstrip('\\/')+'/temp/service-os'
    environment+=(f"$lvwTemporary={base.ps_quote(temporary)}\n"
        "New-Item -ItemType Directory -Path $lvwTemporary -Force -ErrorAction Stop | Out-Null\n"
        "$env:TEMP=$lvwTemporary\n$env:TMP=$lvwTemporary\n"
        "$env:TORCH_HOME=($lvwTemporary+'/torch')\n$env:HF_HOME=($lvwTemporary+'/huggingface')\n"
        "$env:XDG_CACHE_HOME=($lvwTemporary+'/cache')\n")
    probe=(f"$env:LVW_FFPROBE_EXE={base.ps_quote(ffprobe)}\n$env:LVW_VIDEO_PROBE_BACKEND='cli'\n" if ffprobe else
           "Remove-Item Env:LVW_FFPROBE_EXE -ErrorAction SilentlyContinue\n$env:LVW_VIDEO_PROBE_BACKEND='pyav'\n")
    if type(warm) is not bool or type(audit) is not bool or (warm and audit):raise ValueError('BENCHMARK_MODE_INVALID')
    benchmark=("$env:LVW_WARM_BENCHMARK='run-owned-v1'\n" if warm else
               "Remove-Item Env:LVW_WARM_BENCHMARK -ErrorAction SilentlyContinue\n")
    native=("$env:LVW_NATIVE_CHECKPOINT='run-owned-v1'\n" if audit else "Remove-Item Env:LVW_NATIVE_CHECKPOINT -ErrorAction SilentlyContinue\n")
    launch=base.comfy_wrapper_text(python,main,directory,pid_file)
    if launch.count('--disable-auto-launch')!=1:raise ValueError('COMFY_LAUNCH_TEMPLATE_CHANGED')
    user_directory=directory.rstrip('\\/')+'/user'
    launch=launch.replace('--disable-auto-launch',f"--user-directory {base.ps_quote(user_directory)} --disable-auto-launch",1)
    return (environment+f"$env:LVW_FFMPEG_EXE={base.ps_quote(ffmpeg)}\n"+probe+benchmark+native
            + launch)


class S2SystemDriver(base.SystemDriver):
    def __init__(self, args, evidence):
        super().__init__(args,evidence)
        if type(args.max_public_submissions) is not int or not 1 <= args.max_public_submissions <= 64:
            raise base.StopProbe('PUBLIC_SUBMISSION_BUDGET_INVALID')
        self.max_public_submissions = args.max_public_submissions
        self.warm_benchmark=getattr(args,'warm_benchmark',False)
        self.native_audit=getattr(args,'native_audit',False)
        if type(self.native_audit) is not bool or (self.native_audit and self.warm_benchmark):raise base.StopProbe('NATIVE_AUDIT_MODE_INVALID')
        if type(self.warm_benchmark) is not bool:raise base.StopProbe('BENCHMARK_MODE_INVALID')
        self.request_limit=getattr(args,'max_loopback_requests',1024)
        if type(self.request_limit) is not int or not 1<=self.request_limit<=8192:
            raise base.StopProbe('LOOPBACK_REQUEST_BUDGET_INVALID')
        self.request_ledger=[];self._wrapper_handles={};self.listener_births={};self._cleanup_descendants={}
        self._submission_guard=threading.Lock()
        self.clients = {url:LoopbackClient(url) for url in (base.COMFY_URL,base.OLLAMA_URL)}

    def _reparse_paths(self, root):
        root=Path(root)
        if (not root.is_absolute() or str(root)!=self.evidence.get('owned_run_root')
                or root.resolve(strict=True)!=root
                or (root/'input').resolve(strict=True)!=root/'input'
                or (root/'outside-input').resolve(strict=True)!=root/'outside-input'):
            raise base.StopProbe('REPARSE_ROOT_NOT_BOUND')
        return root/'input/redirect',root/'outside-input'

    def verify_reparse_fixture(self, root):
        """Read actual Windows junction metadata, never infer it from WSL stat."""
        link,target=self._reparse_paths(root)
        checks=self.evidence.setdefault('owned_reparse_fixture_checks',[])
        if len(checks)>=16:raise base.StopProbe('REPARSE_METADATA_BUDGET_EXCEEDED')
        expected_link=base.normalized_windows_path(self._windows_path(str(link))).casefold()
        expected_target=base.normalized_windows_path(self._windows_path(str(target))).casefold()
        raw=self._powershell('$item=Get-Item -LiteralPath '+base.ps_quote(self._windows_path(str(link)))
            +' -Force -ErrorAction Stop;[ordered]@{path=[string]$item.FullName;attributes=[int]$item.Attributes;'
            +'link_type=[string]$item.LinkType;targets=@($item.Target)}|ConvertTo-Json -Compress')
        proof=json.loads(raw);checks.append(proof)
        if (type(proof.get('attributes')) is not int or not proof['attributes']&0x400
                or proof.get('link_type')!='Junction' or not isinstance(proof.get('targets'),list)
                or len(proof['targets'])!=1 or not isinstance(proof['targets'][0],str)
                or base.normalized_windows_path(proof.get('path','')).casefold()!=expected_link
                or base.normalized_windows_path(proof['targets'][0]).casefold()!=expected_target):
            raise base.StopProbe('REPARSE_NATIVE_IDENTITY_MISMATCH')
        return {'proven':True,'native_metadata':proof,'target_within_owned_root':True,'target_outside_input':True}

    def remove_owned_reparse_fixture(self, root):
        before=self.verify_reparse_fixture(root);link,target=self._reparse_paths(root)
        # Directory.Delete(false) removes the verified Windows junction itself;
        # it does not recursively delete its target or invoke an extra shell.
        value=json.loads(self._powershell('[System.IO.Directory]::Delete('
            +base.ps_quote(self._windows_path(str(link)))+',$false);[ordered]@{link_absent= -not (Test-Path -LiteralPath '
            +base.ps_quote(self._windows_path(str(link)))+');target_exists=(Test-Path -LiteralPath '
            +base.ps_quote(self._windows_path(str(target)))+')}|ConvertTo-Json -Compress'))
        if value.get('link_absent') is not True or value.get('target_exists') is not True:
            raise base.StopProbe('REPARSE_LINK_CLEANUP_UNPROVEN')
        return {'proven':True,'before':before,'after':value,'recursive_delete':False}

    def _prove_listener_owned(self,port,wrapper_pid_file,executable_name):
        if port not in (8191,11434):raise base.StopProbe('LISTENER_PORT_FORBIDDEN')
        handle=self._wrapper_handles.get(str(wrapper_pid_file))
        if handle is None or handle.poll() is not None:raise base.StopProbe('OWNED_WRAPPER_HANDLE_NOT_LIVE')
        pid=super()._prove_listener_owned(port,wrapper_pid_file,executable_name)
        wrapper=int(Path(wrapper_pid_file).read_text(encoding='ascii'))
        raw=self._powershell(f"$a=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}';"
            f"$b=Get-CimInstance Win32_Process -Filter 'ProcessId = {wrapper}';"
            f"$lp=Get-Process -Id {pid};$wp=Get-Process -Id {wrapper};"
            "try{$null=$lp.SafeHandle;$null=$wp.SafeHandle;"
            "[ordered]@{listener_pid=[int]$a.ProcessId;wrapper_pid=[int]$b.ProcessId;"
            "listener_start_ticks=[long]$a.CreationDate.ToUniversalTime().Ticks;"
            "wrapper_start_ticks=[long]$b.CreationDate.ToUniversalTime().Ticks;"
            "executable=[string]$a.ExecutablePath;listener_process_start_ticks=[long]$lp.StartTime.ToUniversalTime().Ticks;"
            "wrapper_process_start_ticks=[long]$wp.StartTime.ToUniversalTime().Ticks}|ConvertTo-Json -Compress}"
            "finally{$lp.Dispose();$wp.Dispose()}")
        proof=json.loads(raw)
        target=self.args.comfy_python if port==8191 else self.args.ollama_exe
        expected=base.normalized_windows_path(self._windows_path(target)).casefold()
        if (proof.get('listener_pid')!=pid or proof.get('wrapper_pid')!=wrapper
                or any(type(proof.get(k)) is not int or proof[k]<=0 for k in ('listener_start_ticks','wrapper_start_ticks','listener_process_start_ticks','wrapper_process_start_ticks'))
                or base.normalized_windows_path(proof.get('executable','')).casefold()!=expected):
            raise base.StopProbe('LISTENER_BIRTH_PROOF_INVALID')
        if port in self.listener_births and self.listener_births[port]!=proof:
            raise base.StopProbe('LISTENER_OR_WRAPPER_PID_REUSED')
        self.listener_births[port]=proof
        self.owned_listener_evidence[str(port)].update(proof)
        return pid

    def _kill_bound(self,pid,start_ticks,*,allow_absent=False):
        if any(type(v) is not int or v<=0 for v in (pid,start_ticks)) or type(allow_absent) is not bool:
            raise base.StopProbe('STOP_BIRTH_INVALID')
        # Opening SafeHandle pins the object; a recycled PID cannot be killed.
        absent=("[ordered]@{state='ABSENT';original_absent=$true;termination_requested=$false}" if allow_absent else "throw 'OWNED_PROCESS_ALREADY_GONE'")
        replaced=("[ordered]@{state='REPLACED';original_absent=$true;termination_requested=$false}" if allow_absent else "throw 'PID_REUSED'")
        raw=self._powershell(f"$p=Get-Process -Id {pid} -ErrorAction SilentlyContinue;"
            "$result=if(!$p){"+absent+"}else{try{$null=$p.SafeHandle;"
            f"if([long]$p.StartTime.ToUniversalTime().Ticks -ne {start_ticks}){{"+replaced+"}else{"
            "$requested=([datetime]::UtcNow.Ticks-621355968000000000)/10000000.0;"
            "$p.Kill();if(!$p.WaitForExit(5000)){throw 'OWNED_STOP_TIMEOUT'};"
            "[ordered]@{state='STOPPED';original_absent=$true;termination_requested=$true;"
            "stop_requested_wall_seconds=$requested;exit_confirmed_wall_seconds=([datetime]::UtcNow.Ticks-621355968000000000)/10000000.0}"
            "}}finally{$p.Dispose()}};"
            f"$result['pid']={pid};$result['target_start_ticks']={start_ticks};$result|ConvertTo-Json -Compress")
        value=json.loads(raw)
        if (type(value.get('pid')) is not int or type(value.get('target_start_ticks')) is not int
                or value.get('pid')!=pid or value.get('target_start_ticks')!=start_ticks or value.get('original_absent') is not True
                or type(value.get('termination_requested')) is not bool or value.get('state') not in ('STOPPED','ABSENT','REPLACED')
                or (not allow_absent and value.get('state')!='STOPPED')):raise base.StopProbe('OWNED_STOP_RECEIPT_INVALID')
        if value['termination_requested']!=(value['state']=='STOPPED'):raise base.StopProbe('OWNED_STOP_RECEIPT_INVALID')
        if value['termination_requested']:
            requested=value.get('stop_requested_wall_seconds');confirmed=value.get('exit_confirmed_wall_seconds')
            if (any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in (requested,confirmed))
                    or confirmed<requested):raise base.StopProbe('OWNED_STOP_CLOCK_INVALID')
        return value

    def _snapshot_descendants(self,pid,start_ticks):
        if any(type(v) is not int or v<=0 for v in (pid,start_ticks)):raise base.StopProbe('SNAPSHOT_ROOT_INVALID')
        raw=self._powershell(f"$root=Get-Process -Id {pid};$handles=@($root);try{{$null=$root.SafeHandle;"
            f"if([long]$root.StartTime.ToUniversalTime().Ticks -ne {start_ticks}){{throw 'SNAPSHOT_ROOT_REUSED'}};"
            f"$rows=@(Get-CimInstance Win32_Process);$rootRows=@($rows|Where-Object {{$_.ProcessId -eq {pid}}});"
            f"if($rootRows.Count -ne 1 -or {start_ticks} -lt [long]$rootRows[0].CreationDate.ToUniversalTime().Ticks "
            f"-or ({start_ticks}-[long]$rootRows[0].CreationDate.ToUniversalTime().Ticks) -ge 10){{throw 'SNAPSHOT_ROOT_CIM_MISMATCH'}};"
            f"$ids=@({pid});$out=@();"
            "for($i=0;$i -lt 8;$i++){$next=@($rows|Where-Object {"
            "($_.ParentProcessId -in $ids) -and ($_.ProcessId -notin $ids)});if(!$next.Count){break};"
            "$ids+=@($next.ProcessId);if($ids.Count -gt 17){throw 'DESCENDANT_LIMIT'};"
            "foreach($row in $next){$p=Get-Process -Id $row.ProcessId;$handles+=@($p);$null=$p.SafeHandle;"
            "$ticks=[long]$p.StartTime.ToUniversalTime().Ticks;$ct=[long]$row.CreationDate.ToUniversalTime().Ticks;"
            "$parent=@($rows|Where-Object {$_.ProcessId -eq $row.ParentProcessId});"
            "if($parent.Count -ne 1 -or $ct -lt [long]$parent[0].CreationDate.ToUniversalTime().Ticks "
            "-or $ticks -lt $ct -or ($ticks-$ct) -ge 10){throw 'DESCENDANT_BIRTH_UNPROVEN'};"
            "$out+=@([ordered]@{pid=[int]$row.ProcessId;parent_pid=[int]$row.ParentProcessId;"
            "start_ticks=$ct;process_start_ticks=$ticks})}};"
            "if(@($rows|Where-Object {($_.ParentProcessId -in $ids) -and ($_.ProcessId -notin $ids)}).Count)"
            "{throw 'DESCENDANT_DEPTH_LIMIT'};ConvertTo-Json -InputObject @($out) -Compress"
            "}finally{foreach($h in $handles){$h.Dispose()}}")
        values=json.loads(raw);known={pid}
        if not isinstance(values,list) or len(values)>16:raise base.StopProbe('DESCENDANT_SNAPSHOT_INVALID')
        for child in values:
            if (not isinstance(child,dict) or any(type(child.get(k)) is not int or child[k]<=0 for k in
                    ('pid','parent_pid','start_ticks','process_start_ticks')) or child['parent_pid'] not in known
                    or child['pid'] in known or not 0<=child['process_start_ticks']-child['start_ticks']<10):
                raise base.StopProbe('DESCENDANT_SNAPSHOT_INVALID')
            known.add(child['pid'])
        return values

    def _stop_snapshot_descendants(self,children):
        states=[]
        for child in reversed(children):
            try:
                if type(child.get('process_start_ticks')) is not int:raise base.StopProbe('DESCENDANT_NATIVE_BIRTH_MISSING')
                states.append(self._kill_bound(child['pid'],child['process_start_ticks'],allow_absent=True))
            except Exception as error:
                states.append({'pid':child.get('pid'),'original_absent':False,'error_type':type(error).__name__,
                               'reason':getattr(error,'reason',None)})
        return states

    def _assert_no_new_descendants(self,pid,start_ticks,children):
        # Children born in the snapshot/stop gap are never silently forgotten.
        # An unbound child (including a recycled parent's new child) is reported,
        # not killed by guessing ownership from ParentProcessId alone.
        ids=[pid]+[v['pid'] for v in children]
        if type(start_ticks) is not int or start_ticks<=0 or any(type(v) is not int or v<=0 for v in ids):
            raise base.StopProbe('DESCENDANT_EXIT_BINDING_INVALID')
        values=','.join(str(v) for v in ids)
        count=int(self._powershell(f"$ids=@({values});@(Get-CimInstance Win32_Process|Where-Object {{"
            f"($_.ParentProcessId -in $ids) -and ($_.ProcessId -notin $ids) -and "
            f"([long]$_.CreationDate.ToUniversalTime().Ticks -ge {start_ticks})}}).Count"))
        if count:raise base.StopProbe('NEW_DESCENDANT_OWNERSHIP_UNPROVEN')

    def cleanup(self):
        failures=[];listeners=[];wrappers=[]
        for port,proof in sorted(self.listener_proofs.items()):
            state={'port':port,'lineage_reproven':False,'stop_requested':False,'terminal_absent':False}
            try:
                if self._listener_pid_values(port):
                    pid=self._prove_listener_owned(port,proof['wrapper_pid_file'],proof['executable_name'])
                    birth=self.listener_births[port]
                    state.update(owned_listener_pid=pid,lineage_reproven=True,stop_requested=True)
                    descendants=self._snapshot_descendants(pid,self.listener_births[port]['listener_process_start_ticks'])
                    state['descendants_before_stop']=descendants
                    self._cleanup_descendants[port]=descendants
                    state['root_stop']=self._kill_bound(pid,birth['listener_process_start_ticks'])
                if port not in self._cleanup_descendants:raise base.StopProbe('DESCENDANT_EXIT_BASELINE_MISSING')
                descendant_states=self._stop_snapshot_descendants(self._cleanup_descendants[port])
                state['descendant_terminal_states']=descendant_states
                survivor_pids=[v['pid'] for v in descendant_states if v.get('original_absent') is not True]
                state['descendant_pids_still_present']=survivor_pids
                if survivor_pids:raise base.StopProbe('DESCENDANT_EXIT_UNPROVEN')
                birth=self.listener_births[port]
                self._assert_no_new_descendants(birth.get('listener_pid',state.get('owned_listener_pid')),
                    birth['listener_process_start_ticks'],self._cleanup_descendants[port])
                state['unknown_descendants_absent']=True
                state['terminal_absent']=not self._listener_pid_values(port)
                if not state['terminal_absent']:raise base.StopProbe('LISTENER_STILL_PRESENT')
            except Exception as error:failures.append({'port':port,'error_type':type(error).__name__,'reason':getattr(error,'reason',None)})
            listeners.append(state)
        # Native wrapper identity was captured while its launch handle was live.
        # A wrapper not captured (partial startup) is never blindly PID-killed.
        for name,process,stream in reversed(self.owned):
            state={'owner':name,'pid':getattr(process,'pid',None),'exited':False,'native_wrapper_absent':False}
            try:
                births=[v for port,v in self.listener_births.items()
                    if (port==8191 and name=='comfy') or (port==11434 and name=='ollama_wrapper')]
                if births:
                    birth=births[0];pid=birth['wrapper_pid']
                    count=int(self._powershell(f"@(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').Count"))
                    if count:self._kill_bound(pid,birth['wrapper_process_start_ticks'])
                    state['native_wrapper_absent']=int(self._powershell(
                        f"@(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').Count"))==0
                if process.poll() is None:
                    process.terminate();process.wait(timeout=20)
                state['exited']=process.poll() is not None
                if not state['exited'] or not state['native_wrapper_absent']:
                    raise base.StopProbe('WRAPPER_EXIT_UNPROVEN')
            except Exception as error:failures.append({'owner':name,'error_type':type(error).__name__,'reason':getattr(error,'reason',None)})
            finally:stream.close();wrappers.append(state)
        count=int(self._powershell("@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
            "Where-Object {$_.LocalPort -in 8191,11434}).Count") or '0')
        return {'proven':not failures and count==0,'owned_count':len(self.owned),'failures':failures,
            'final_target_listener_count':count,'owned_listener_terminal_states':listeners,
            'owned_wrapper_terminal_states':wrappers}

    def stop_ollama(self):
        proof=self.listener_proofs.get(11434)
        if proof is None:raise base.StopProbe('OLLAMA_LISTENER_OWNERSHIP_LOST')
        pid=self._prove_listener_owned(11434,proof['wrapper_pid_file'],proof['executable_name'])
        descendants=self._snapshot_descendants(pid,self.listener_births[11434]['listener_process_start_ticks'])
        self._cleanup_descendants[11434]=descendants
        stopped=self._kill_bound(pid,self.listener_births[11434]['listener_process_start_ticks'])
        child_states=self._stop_snapshot_descendants(descendants)
        if any(v.get('original_absent') is not True for v in child_states):raise base.StopProbe('DESCENDANT_EXIT_UNPROVEN')
        self._assert_no_new_descendants(pid,self.listener_births[11434]['listener_process_start_ticks'],descendants)
        if self._listener_pid_values(11434):raise base.StopProbe('OLLAMA_STOP_UNPROVEN')
        self.listener_terminal_states['11434']={'port':11434,'owned_listener_pid':pid,'lineage_reproven':True,
            'stop_requested':True,'terminal_absent':True,'root_stop':stopped,'descendants_before_stop':descendants,
            'descendant_terminal_states':child_states,'unknown_descendants_absent':True}
        self.listener_pids.discard(pid)
        # Keep birth/proof records for final native-wrapper cleanup.
        return self.listener_terminal_states['11434']

    def _json_request(self, url, *, payload=None, timeout=20,observer=None):
        for endpoint,client in self.clients.items():
            if url.startswith(endpoint+'/'):
                if len(self.request_ledger)>=self.request_limit:raise base.StopProbe('LOOPBACK_REQUEST_BUDGET_EXCEEDED')
                entry={'endpoint':endpoint,'path':url[len(endpoint):],'status':None}
                self.request_ledger.append(entry)
                try:
                    options={'payload':payload,'timeout':timeout}
                    if observer is not None:options['observer']=observer
                    status,value=client.request('POST' if payload is not None else 'GET',url[len(endpoint):],**options)
                    entry['status']=status
                    return status,value
                except Exception as exc:
                    entry['error_type']=type(exc).__name__
                    raise
        raise base.StopProbe('NON_LOOPBACK_URL_FORBIDDEN')

    def _powershell(self, script):
        prefix = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        result = subprocess.run([self.args.powershell,'-NoProfile','-NonInteractive','-Command',prefix+script],
                                capture_output=True,timeout=60)
        if result.returncode:
            raise base.StopProbe('WINDOWS_PREFLIGHT_COMMAND_FAILED')
        return result.stdout.decode('utf-8-sig','strict').strip()

    def wait_json(self,url,timeout=60):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            try:return self._json_request(url,timeout=min(5,remaining))
            except (OSError,ControlError):time.sleep(min(.25,max(0,deadline-time.monotonic())))
        raise base.StopProbe('SERVICE_START_TIMEOUT')

    def reserve_public_submission(self):
        """Precharge either an adapter POST or an observed browser POST."""
        with self._submission_guard:
            if self.submissions >= self.max_public_submissions:
                raise base.StopProbe('PUBLIC_API_SUBMISSION_BUDGET_EXCEEDED')
            self.submissions += 1  # Failed/aborted permitted sends consume budget.
            return self.submissions

    def submit(self, graph):
        self.reserve_public_submission()
        status,value=self._json_request(base.COMFY_URL+'/prompt',payload={'prompt':graph,'client_id':self.args.run_id},
            observer=getattr(self,'resource_observer',None))
        if status != 200 or not isinstance(value.get('prompt_id'),str) or not value['prompt_id']:
            raise base.StopProbe('PUBLIC_PROMPT_SUBMISSION_FAILED')
        return value['prompt_id']

    def start_comfy(self, directory, log_path):
        # Caller must finish candidate/target hash checks and child authorization
        # before invoking any lifecycle operation on this low-level adapter.
        (directory/'user').mkdir(exist_ok=False)
        win_main=self._windows_path(self.args.comfy_main,expected=base.AUTHORIZED_COMFY_MAIN)
        win_python=self._windows_path(self.args.comfy_python,expected=base.AUTHORIZED_COMFY_PYTHON)
        win_directory=self._windows_path(str(directory))
        wrapper=directory/'comfy-wrapper.ps1';pid_file=directory/'comfy-wrapper.pid'
        wrapper.write_text(comfy_wrapper(win_python,win_main,win_directory,self._windows_path(str(pid_file)),
            self._windows_path(self.args.ffmpeg_exe),self._windows_path(self.args.ffprobe_exe) if self.args.ffprobe_exe else None,
            warm=self.warm_benchmark,audit=self.native_audit),encoding='utf-8-sig')
        stream=log_path.open('w',encoding='utf-8')
        try:
            process=subprocess.Popen([self.args.powershell,'-NoProfile','-NonInteractive','-File',
                self._windows_path(str(wrapper))],stdout=stream,stderr=subprocess.STDOUT,text=True)
        except BaseException:
            stream.close()
            raise
        self.owned.append(('comfy',process,stream));self._wrapper_handles[str(pid_file)]=process
        self.wait_json(base.COMFY_URL+'/object_info',timeout=120)
        self._prove_listener_owned(8191,pid_file,'python.exe')
