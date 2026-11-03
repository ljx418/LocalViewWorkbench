"""Actual native lifecycle/sampling adapter for the authorized S2 coordinator.

Construction does not grant authorization. The parent must finish candidate,
target, sample, port and budget bindings before any method starts a process.
"""
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess
import time

from tools.v0_s2_driver import S2SystemDriver,ROOT,base


def read_jsonl(path,*,limit):
    """Read only complete records while the native writer may be appending."""
    path=Path(path)
    if path.is_symlink():raise base.StopProbe('RUNTIME_ARTIFACT_SYMLINK')
    if not path.exists():return []
    if path.stat().st_size>limit:raise base.StopProbe('RUNTIME_ARTIFACT_LIMIT')
    with path.open('rb') as handle:raw=handle.read(limit+1)
    if len(raw)>limit:raise base.StopProbe('RUNTIME_ARTIFACT_LIMIT')
    end=raw.rfind(b'\n')
    if end<0:return []
    values=[json.loads(line) for line in raw[:end].splitlines() if line]
    if any(not isinstance(value,dict) for value in values):raise base.StopProbe('RUNTIME_ARTIFACT_SHAPE')
    return values


class NativeRuntime(S2SystemDriver):
    def __init__(self,args,evidence):
        super().__init__(args,evidence)
        self.clock_reads=0;self.workers=[]
        self.preloads=0
        self.clock_limit=getattr(args,'max_native_clock_reads',64)
        if type(self.clock_limit) is not int or not 1<=self.clock_limit<=128:
            raise base.StopProbe('NATIVE_CLOCK_BUDGET_INVALID')

    def native_clock(self):
        if self.clock_reads>=self.clock_limit:raise base.StopProbe('NATIVE_CLOCK_BUDGET_EXCEEDED')
        self.clock_reads+=1
        python=self._windows_path(self.args.comfy_python,expected=base.AUTHORIZED_COMFY_PYTHON)
        script=self._windows_path(str(ROOT/'tools/v0_s2_native_clock.py'))
        value=json.loads(self._powershell(f'& {base.ps_quote(python)} -I -B {base.ps_quote(script)}'))
        if (value.get('platform')!='win32' or value.get('clock_basis')!='native_python_monotonic'
                or any(type(value.get(k)) not in (int,float) or not math.isfinite(value[k]) or value[k]<0
                       for k in ('monotonic_seconds','wall_seconds'))):
            raise base.StopProbe('NATIVE_CLOCK_INVALID')
        return value

    def owned_listener_birth(self,port):
        proof=self.listener_proofs.get(port)
        if proof is None:raise base.StopProbe('RUNTIME_LISTENER_NOT_OWNED')
        pid=self._prove_listener_owned(port,proof['wrapper_pid_file'],proof['executable_name'])
        raw=self._powershell(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}';"
            "[ordered]@{pid=[int]$p.ProcessId;start_ticks=[long]$p.CreationDate.ToUniversalTime().Ticks;name=[string]$p.Name}|ConvertTo-Json -Compress")
        value=json.loads(raw)
        if (value.get('pid')!=pid or type(value.get('start_ticks')) is not int or value['start_ticks']<=0
                or value.get('name','').lower()!=proof['executable_name'].lower()):
            raise base.StopProbe('RUNTIME_LISTENER_BIRTH_INVALID')
        return value

    def write_warm_binding(self,run_root,*,candidate_sha,authorization_sha256,model_digest,nvidia_sha256,baseline_gpu_mib):
        for value,length in ((candidate_sha,40),(authorization_sha256,64),(model_digest,64),(nvidia_sha256,64)):
            if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',value):
                raise base.StopProbe('RUNTIME_WARM_BINDING_INVALID')
        if type(baseline_gpu_mib) is not int or not 0<=baseline_gpu_mib<=4096:
            raise base.StopProbe('RUNTIME_COLD_BASELINE_INVALID')
        root=self.owned_listener_birth(11434)
        clock=self.native_clock()
        value={'candidate_sha':candidate_sha,'authorization_sha256':authorization_sha256,
            'program_authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','scope':'V0_S2_WARM_BENCHMARK',
            'model_digest':model_digest,'nvidia_smi_sha256':nvidia_sha256,'max_requests':20,
            'baseline_gpu_mib':baseline_gpu_mib,
            'ollama_pid':root['pid'],'ollama_start_ticks':root['start_ticks'],
            'issued_at':clock['wall_seconds'],'expires_at':clock['wall_seconds']+7200}
        path=Path(run_root)/'temp/lvw-warm-profile.json'
        with path.open('x',encoding='utf-8') as handle:json.dump(value,handle,separators=(',',':'))
        return value

    def start_ollama(self,log_path):
        # Reuse the frozen launch policy, but PS 5.1 needs BOM for Unicode paths.
        self.ollama_log=Path(log_path);directory=self.ollama_log.parent
        wrapper=directory/'ollama-wrapper.ps1';pid_file=directory/'ollama-wrapper.pid'
        exe=self._windows_path(self.args.ollama_exe)
        if not base.normalized_windows_path(exe).lower().endswith('/ollama.exe'):
            raise base.StopProbe('OLLAMA_EXECUTABLE_PATH_INVALID')
        wrapper.write_text(base.ollama_wrapper_text(exe,self._windows_path(str(pid_file))),encoding='utf-8-sig')
        stream=self.ollama_log.open('x',encoding='utf-8')
        try:
            process=subprocess.Popen([self.args.powershell,'-NoProfile','-NonInteractive','-File',
                self._windows_path(str(wrapper))],stdout=stream,stderr=subprocess.STDOUT)
        except BaseException:stream.close();raise
        self.owned.append(('ollama_wrapper',process,stream));self.ollama_wrapper_pid_file=pid_file

    def start_sampler(self,run_root,*,nvidia_exe,nvidia_sha256,max_seconds=7200):
        # Fresh subdirectory prevents old logs, stop markers or PID leases.
        directory=Path(run_root)/'temp/resource-sampler';directory.mkdir(exist_ok=False)
        owners=[self.owned_listener_birth(port)['pid'] for port in (8191,11434)]
        worker=SamplerWorker(self,directory,nvidia_exe,nvidia_sha256,max_seconds,owners)
        self.workers.append(worker)  # Preserve cleanup even when startup fails.
        worker.start()
        return worker

    def preload(self,model):
        # Caller records/precharges this separate setup action; never include it
        # as a measured provider call or subtract it from measured latency.
        if model!=base.MODEL or self.preloads>=20:raise base.StopProbe('MODEL_PRELOAD_BUDGET_OR_TAG_INVALID')
        self.preloads+=1
        status,value=self._json_request(base.OLLAMA_URL+'/api/generate',
            payload={'model':model,'stream':False,'keep_alive':300},timeout=120)
        if status!=200 or value.get('done') is not True:raise base.StopProbe('MODEL_PRELOAD_FAILED')
        return value

    def chat_log_count(self):
        if self.ollama_log is None:raise base.StopProbe('OLLAMA_LOG_UNAVAILABLE')
        if self.ollama_log.stat().st_size>16*1024*1024:raise base.StopProbe('OLLAMA_LOG_LIMIT')
        text=self.ollama_log.read_text(encoding='utf-8',errors='strict')
        return sum('POST' in line and '"/api/chat"' in line for line in text.splitlines())

    def cleanup(self):
        workers=[]
        for worker in reversed(self.workers):
            try:workers.append(worker.stop())
            except Exception as error:workers.append({'proven':False,'error_type':type(error).__name__})
        services=super().cleanup()
        return {**services,'sampler_workers':workers,'proven':services['proven'] and all(w['proven'] for w in workers)}


class SamplerWorker:
    def __init__(self,driver,directory,binary,digest,max_seconds,pids):
        if (type(max_seconds) is not int or not 1<=max_seconds<=7200
                or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)
                or not 1<=len(pids)<=16 or len(set(pids))!=len(pids)
                or any(type(pid) is not int or not 0<pid<=0xffffffff for pid in pids)):
            raise base.StopProbe('SAMPLER_WORKER_BINDING_INVALID')
        self.driver=driver;self.directory=Path(directory);self.binary=str(binary);self.digest=digest
        self.max_seconds=max_seconds;self.pids=list(pids);self.process=None;self.stream=None;self.proof=None
        self.wrapper_pid=self.directory/'sampler-wrapper.pid'

    def start(self):
        driver=self.driver
        python=driver._windows_path(driver.args.comfy_python,expected=base.AUTHORIZED_COMFY_PYTHON)
        script=driver._windows_path(str(ROOT/'tools/v0_s2_native_sampler.py'))
        wrapper=self.directory/'sampler-wrapper.ps1'
        command=(f"$PID|Set-Content -LiteralPath {base.ps_quote(driver._windows_path(str(self.wrapper_pid)))} -Encoding ascii\n"
            f"& {base.ps_quote(python)} -I -B {base.ps_quote(script)} --execute-sampler "
            f"--run-root {base.ps_quote(driver._windows_path(str(self.directory)))} "
            f"--nvidia-smi {base.ps_quote(driver._windows_path(self.binary))} --binary-sha256 {base.ps_quote(self.digest)} "
            f"--private-pids {' '.join(str(pid) for pid in self.pids)} --max-seconds {self.max_seconds}\nexit $LASTEXITCODE\n")
        wrapper.write_text(command,encoding='utf-8-sig')
        self.stream=(self.directory/'sampler-wrapper.log').open('x',encoding='utf-8')
        self.process=subprocess.Popen([driver.args.powershell,'-NoProfile','-NonInteractive','-File',
            driver._windows_path(str(wrapper))],stdout=self.stream,stderr=subprocess.STDOUT)
        self.wait_point(after=None,timeout=30)
        self.proof=self._prove()

    def _prove(self):
        pidfile=self.directory/'resource-sampler.pid'
        if not pidfile.exists() or not self.wrapper_pid.exists():raise base.StopProbe('SAMPLER_PID_LEASE_MISSING')
        pid=int(pidfile.read_text(encoding='ascii'));wrapper=int(self.wrapper_pid.read_text(encoding='ascii'))
        if pid<=0 or wrapper<=0:raise base.StopProbe('SAMPLER_PID_LEASE_INVALID')
        raw=self.driver._powershell(f"$rows=@();$current={pid};for($i=0;$i -lt 8;$i++){{"
            "$p=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$current);if(!$p){break};"
            "$rows+=[ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;"
            "start_ticks=[long]$p.CreationDate.ToUniversalTime().Ticks;executable=[string]$p.ExecutablePath};"
            f"if($current -eq {wrapper}){{break}};$current=[int]$p.ParentProcessId}};@($rows)|ConvertTo-Json -Compress")
        rows=json.loads(raw);rows=rows if isinstance(rows,list) else [rows]
        expected=base.AUTHORIZED_COMFY_PYTHON.casefold()
        if (not rows or rows[0]['pid']!=pid or rows[-1]['pid']!=wrapper
                or base.normalized_windows_path(rows[0]['executable']).casefold()!=expected
                or not base.normalized_windows_path(rows[-1]['executable']).lower().endswith('/powershell.exe')):
            raise base.StopProbe('SAMPLER_LINEAGE_UNPROVEN')
        proof={'pid':pid,'start_ticks':rows[0]['start_ticks'],'lineage':rows}
        if self.proof is not None and (proof['pid'],proof['start_ticks'])!=(self.proof['pid'],self.proof['start_ticks']):
            raise base.StopProbe('SAMPLER_PID_REUSED')
        return proof

    def points(self):return read_jsonl(self.directory/'resource-trace.jsonl',limit=8*1024*1024)

    def wait_point(self,*,after,timeout=3):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.process is not None and self.process.poll() is not None:raise base.StopProbe('SAMPLER_EXITED_EARLY')
            values=self.points()
            if values:
                point=values[-1]
                if (type(point.get('gpu_used_mib')) is not int or not 0<=point['gpu_used_mib']<23552
                        or type(point.get('available_ram_mib')) is not int or point['available_ram_mib']<2048):
                    raise base.StopProbe('SAMPLER_RESOURCE_LIMIT')
                if after is None or point['monotonic_seconds']>after:return point
            time.sleep(.05)
        raise base.StopProbe('SAMPLER_COVERAGE_TIMEOUT')

    def stop(self):
        if self.process is None:
            if self.stream is not None:self.stream.close()
            return {'proven':True,'never_started':True}
        marker=self.directory/'resource-sampler.stop'
        if not marker.exists():
            with marker.open('x',encoding='ascii') as handle:handle.write('owner stop\n')
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            # No blind kill of a Windows PID or its wrapper. Preserve proof and
            # report unproven cleanup for the parent to stop the Stage safely.
            return {'proven':False,'error_code':'SAMPLER_STOP_TIMEOUT','ownership':self.proof}
        finally:
            if self.process.poll() is not None and self.stream is not None:self.stream.close()
        path=self.directory/'resource-sampler.receipt.json'
        receipt=json.loads(path.read_text()) if path.exists() else None
        absent=False
        lease=self.directory/'resource-sampler.pid'
        pid=self.proof['pid'] if self.proof is not None else int(lease.read_text(encoding='ascii')) if lease.exists() else None
        if pid is not None and type(pid) is int and pid>0:
            count=int(self.driver._powershell(f"@((Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}')).Count"))
            absent=count==0
        proven=self.process.returncode is not None and receipt is not None and receipt.get('owned_gpu_query_exited') is True and absent
        return {'proven':proven,'wrapper_exit_code':self.process.returncode,'native_worker_absent':absent,'receipt':receipt}
