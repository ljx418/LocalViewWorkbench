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
        self.preloads=0;self.resource_observer=None;self.resource_abort_latched=False;self._emergency_done=False
        self.clock_limit=getattr(args,'max_native_clock_reads',64)
        if type(self.clock_limit) is not int or not 1<=self.clock_limit<=128:
            raise base.StopProbe('NATIVE_CLOCK_BUDGET_INVALID')

    def _latch_resource_abort(self,error):
        self.resource_abort_latched=True
        self.evidence['resource_abort']={'error_type':type(error).__name__,
            'reason':getattr(error,'reason',None),'new_model_work_forbidden':True}

    def _emergency_cleanup(self):
        if self._emergency_done:return
        self._emergency_done=True
        try:self.evidence['resource_abort_cleanup']=self.cleanup()
        except BaseException as error:
            self.evidence['resource_abort_cleanup']={'proven':False,'error_type':type(error).__name__}
            if isinstance(error,(KeyboardInterrupt,SystemExit)):raise

    def observe_resources(self):
        if self.resource_abort_latched:raise base.StopProbe('RESOURCE_ABORT_LATCHED')
        try:return self._resource_worker.observe()
        except BaseException as error:
            self._latch_resource_abort(error)
            raise

    def guard_point(self,*,after,timeout=3):
        if self.resource_abort_latched:raise base.StopProbe('RESOURCE_ABORT_LATCHED')
        try:return self._resource_worker.wait_point(after=after,timeout=timeout)
        except BaseException as error:
            self._latch_resource_abort(error);self._emergency_cleanup()
            raise

    def _json_request(self,url,*,payload=None,timeout=20,observer=None):
        try:return super()._json_request(url,payload=payload,timeout=timeout,observer=observer)
        except BaseException:
            # The HTTP observer first interrupts/joins only its owned socket.
            # A disconnected request is not proof that model work stopped.
            # Cleanup revalidates process lineage before stopping owned services.
            if self.resource_abort_latched and observer is not None:self._emergency_cleanup()
            raise

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
        birth=self.listener_births[port]
        return {'pid':pid,'start_ticks':birth['listener_start_ticks'],'name':proof['executable_name']}

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

    def write_native_binding(self,run_root,*,candidate_sha,authorization_sha256,model_digest,max_runs):
        for value,length in ((candidate_sha,40),(authorization_sha256,64),(model_digest,64)):
            if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',value):raise base.StopProbe('NATIVE_BINDING_ID_INVALID')
        if type(max_runs) is not int or not 1<=max_runs<=64:raise base.StopProbe('NATIVE_RUN_BUDGET_INVALID')
        root=self.owned_listener_birth(11434);clock=self.native_clock()
        value={'candidate_sha':candidate_sha,'authorization_sha256':authorization_sha256,'model_digest':model_digest,
            'program_authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','scope':'V0_S2_NATIVE_CHECKPOINT',
            'max_runs':max_runs,'ollama_pid':root['pid'],'ollama_start_ticks':root['start_ticks'],
            'issued_at':clock['wall_seconds'],'expires_at':clock['wall_seconds']+7200}
        with (Path(run_root)/'temp/lvw-native-profile.json').open('x',encoding='utf-8') as stream:json.dump(value,stream,separators=(',',':'))
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
        self._wrapper_handles[str(pid_file)]=process

    def start_sampler(self,run_root,*,nvidia_exe,nvidia_sha256,max_seconds=7200,fault_only=False):
        if type(fault_only) is not bool or (fault_only and (self.warm_benchmark or not self.native_audit)):
            raise base.StopProbe('FAULT_SAMPLER_SCOPE_INVALID')
        # Fresh subdirectory prevents old logs, stop markers or PID leases.
        directory=Path(run_root)/('temp/fault-resource-sampler' if fault_only else 'temp/resource-sampler');directory.mkdir(exist_ok=False)
        owners=[self.owned_listener_birth(port)['pid'] for port in ((8191,) if fault_only else (8191,11434))]
        worker=SamplerWorker(self,directory,nvidia_exe,nvidia_sha256,max_seconds,owners)
        worker.scope='COMFY_ONLY_FAULT' if fault_only else 'COMFY_AND_OLLAMA'
        self.workers.append(worker)  # Preserve cleanup even when startup fails.
        worker.start()
        self._resource_worker=worker;self.resource_observer=self.observe_resources
        return worker

    def prepare_fault_sampler(self,run_root,*,nvidia_exe,nvidia_sha256,max_seconds=7200):
        # Preserve total GPU/RAM coverage while retiring the old Ollama private
        # handle BEFORE its intentional death. Never reopen a recycled PID or
        # invent zero private bytes for an exited process. Warm mode is excluded.
        if (self.warm_benchmark or not self.native_audit or getattr(self,'_fault_sampler_activated',False)
                or not hasattr(self,'_resource_worker') or self._resource_worker.scope!='COMFY_AND_OLLAMA'):
            raise base.StopProbe('FAULT_SAMPLER_TRANSITION_INVALID')
        self.observe_resources();previous=self._resource_worker
        current=self.start_sampler(run_root,nvidia_exe=nvidia_exe,nvidia_sha256=nvidia_sha256,
            max_seconds=max_seconds,fault_only=True)
        try:
            terminal=previous.stop()
            if (terminal.get('proven') is not True or (terminal.get('receipt') or {}).get('decision')
                    !='RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'):
                raise base.StopProbe('PREVIOUS_SAMPLER_TERMINAL_UNPROVEN')
            self.observe_resources()
            old_points=previous.points();new_points=current.points()
            if (not isinstance(old_points,list) or len(old_points)<2 or not isinstance(new_points,list) or not new_points
                    or any(type(p.get('monotonic_seconds')) not in (int,float) or not math.isfinite(p['monotonic_seconds'])
                           for p in (old_points[0],old_points[-1],new_points[0],new_points[-1]))
                    or new_points[0]['monotonic_seconds']<old_points[0]['monotonic_seconds']
                    or new_points[0]['monotonic_seconds']-old_points[-1]['monotonic_seconds']>1.5
                    or old_points[-1]['monotonic_seconds']-new_points[-1]['monotonic_seconds']>1.5):
                raise base.StopProbe('FAULT_SAMPLER_HANDOFF_GAP')
            self._fault_sampler_activated=True
            self.evidence['fault_sampler_transition']={'previous_terminal':terminal,'previous_scope':previous.scope,
                'current_scope':current.scope,'current_pids':list(current.pids),'current_ownership':current.proof,
                'whole_gpu_and_host_ram_continue':True,'ollama_private_bytes_after_stop_claimed':False,
                'previous_last_point':old_points[-1],'current_first_point':new_points[0],'current_last_point':new_points[-1],
                'handoff_gap_seconds':max(0,new_points[0]['monotonic_seconds']-old_points[-1]['monotonic_seconds'])}
            return current
        except BaseException as error:
            self._latch_resource_abort(error);self._emergency_cleanup();raise

    def preload(self,model):
        # Caller records/precharges this separate setup action; never include it
        # as a measured provider call or subtract it from measured latency.
        if self.resource_abort_latched:raise base.StopProbe('RESOURCE_ABORT_LATCHED')
        if self.resource_observer is None:raise base.StopProbe('RESOURCE_MONITOR_REQUIRED')
        if model!=base.MODEL or self.preloads>=20:raise base.StopProbe('MODEL_PRELOAD_BUDGET_OR_TAG_INVALID')
        self.preloads+=1
        status,value=self._json_request(base.OLLAMA_URL+'/api/generate',
            payload={'model':model,'stream':False,'keep_alive':300},timeout=120,observer=self.resource_observer)
        if status!=200 or value.get('done') is not True:raise base.StopProbe('MODEL_PRELOAD_FAILED')
        return value

    def release_preload(self,binding,worker):
        """Recover only this run's owned preload after preparation/failure.

        No provider retry. Root proof, unload, inventory and physical stability
        share one thirty-second budget; samples retain their native clock.
        """
        if self.resource_abort_latched:raise base.StopProbe('RESOURCE_ABORT_REQUIRES_POSTSTOP_PROOF')
        deadline=time.monotonic()+30
        root=self.owned_listener_birth(11434)
        if (root['pid'],root['start_ticks'])!=(binding['ollama_pid'],binding['ollama_start_ticks']):
            raise base.StopProbe('PRELOAD_OWNER_CHANGED')
        baseline=binding['baseline_gpu_mib']
        if type(baseline) is not int or not 0<=baseline<=4096:raise base.StopProbe('PRELOAD_BASELINE_INVALID')
        def remaining(cap):
            left=deadline-time.monotonic()
            if left<=0:raise base.StopProbe('PRELOAD_RELEASE_TIMEOUT')
            return min(cap,left)
        status,value=self._json_request(base.OLLAMA_URL+'/api/generate',
            payload={'model':base.MODEL,'keep_alive':0},timeout=remaining(15),observer=self.resource_observer)
        if status!=200 or value.get('done') is not True:raise base.StopProbe('PRELOAD_UNLOAD_UNACKNOWLEDGED')
        while True:
            _,state=self._json_request(base.OLLAMA_URL+'/api/ps',timeout=remaining(2),observer=self.resource_observer)
            if state.get('models')==[]:break
            if not isinstance(state.get('models'),list):raise base.StopProbe('PRELOAD_INVENTORY_INVALID')
            time.sleep(min(.1,remaining(.1)))
        observed=self.native_clock()['monotonic_seconds'];remaining(1)
        samples=[];stable=0
        while True:
            point=worker.wait_point(after=observed,timeout=remaining(3))
            observed=point['monotonic_seconds'];remaining(1)
            samples.append(point)
            stable=stable+1 if point['gpu_used_mib']<=baseline+1024 else 0
            if stable>=3:return {'proven':True,'loaded_models':0,'baseline_gpu_mib':baseline,
                'gpu_samples':samples,'elapsed_seconds':30-(deadline-time.monotonic())}

    def chat_log_snapshot(self):
        if self.ollama_log is None:raise base.StopProbe('OLLAMA_LOG_UNAVAILABLE')
        if self.ollama_log.is_symlink() or self.ollama_log.stat().st_size>16*1024*1024:raise base.StopProbe('OLLAMA_LOG_LIMIT')
        with self.ollama_log.open('rb') as stream:raw=stream.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:raise base.StopProbe('OLLAMA_LOG_LIMIT')
        # Only complete lines can attest a completed server request. Retain the
        # exact prefix so an independent review can recompute the count.
        prefix=raw[:raw.rfind(b'\n')+1];text=prefix.decode('utf-8','strict')
        return {'source_log_bytes':len(prefix),'source_log_sha256':hashlib.sha256(prefix).hexdigest(),
            'raw_log':text,'chat_calls':sum('POST' in line and '"/api/chat"' in line for line in text.splitlines()),
            'observed_bytes':len(raw)}

    def chat_log_count(self):return self.chat_log_snapshot()['chat_calls']

    def cleanup(self):
        workers=[]
        for worker in reversed(self.workers):
            try:workers.append(worker.stop())
            except Exception as error:workers.append({'proven':False,'error_type':type(error).__name__})
        services=super().cleanup()
        pending={endpoint:client.reap_pending() for endpoint,client in self.clients.items()}
        return {**services,'sampler_workers':workers,'http_workers_pending':pending,
            'proven':services['proven'] and all(w['proven'] for w in workers) and not any(pending.values())}


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
        self._observed_stamp=None;self._observed_progress=None

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
        self.observe()
        self.proof=self._prove()
        self.observe()

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

    def observe(self):
        point=self.wait_point(after=None,timeout=.05)
        stamp=point['monotonic_seconds'];now=time.monotonic()
        if type(stamp) not in (int,float) or not math.isfinite(stamp):raise base.StopProbe('SAMPLER_CLOCK_INVALID')
        if self._observed_stamp is not None and stamp<self._observed_stamp:raise base.StopProbe('SAMPLER_CLOCK_REVERSED')
        if stamp!=self._observed_stamp:
            self._observed_stamp=stamp;self._observed_progress=now
        elif now-self._observed_progress>3:raise base.StopProbe('SAMPLER_STALE')
        return point

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
