"""Bounded, owned, temporary warm measurements; ordinary launches stay cold."""
from .resource_policy import valid_baseline
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import threading
import time

from . import core
from .core import BridgeError
from .video_process import run_bounded
from .video_resources import resource_preflight


def refused(reason):
    return BridgeError('RESOURCE_BUSY', 'owned warm benchmark admission refused', subcode=reason)


def validate_binding(binding, now):
    if not isinstance(binding, dict):raise refused('BENCHMARK_BINDING_INVALID')
    for key, count in [('candidate_sha',40),('authorization_sha256',64),('model_digest',64)]:
        if not isinstance(binding.get(key),str) or not re.fullmatch('[0-9a-f]{'+str(count)+'}',binding[key]):
            raise refused('BENCHMARK_BINDING_INVALID')
    if (binding.get('program_authorization_id')!='AUTH-PROGRAM-V1-LOCAL-01'
            or binding.get('scope')!='V0_S2_WARM_BENCHMARK'
            or type(binding.get('baseline_gpu_mib')) is not int or not valid_baseline(binding['baseline_gpu_mib'])
            or type(binding.get('max_requests')) is not int or binding['max_requests']!=20
            or any(type(binding.get(key)) is not int or binding[key]<=0 for key in ('ollama_pid','ollama_start_ticks'))):
        raise refused('BENCHMARK_BINDING_INVALID')
    issued, expires = binding.get('issued_at'), binding.get('expires_at')
    if (any(type(value) not in (int,float) or not math.isfinite(value) for value in (issued,expires,now))
            or not 0 < expires-issued <= 7200 or not issued <= now < expires):
        raise refused('BENCHMARK_BINDING_EXPIRED')


def validate_lineage(document, binding, compute_pids, owner_pid):
    """Validate native listener PID, birth time and bounded GPU PID ancestry."""
    root=binding['ollama_pid']; ticks=binding['ollama_start_ticks']
    if (type(owner_pid) is not int or owner_pid<=0 or not isinstance(document,dict)
            or type(document.get('listener_pid')) is not int or document['listener_pid']!=root
            or document.get('listener_address')!='127.0.0.1' or type(document.get('listener_port')) is not int
            or document['listener_port']!=11434):
        raise refused('BENCHMARK_LISTENER_OWNERSHIP_LOST')
    rows=document.get('processes')
    if not isinstance(rows,list) or len(rows)>600:raise refused('BENCHMARK_LINEAGE_INVALID')
    processes={}
    for row in rows:
        if (not isinstance(row,dict) or any(type(row.get(k)) is not int for k in ('pid','parent_pid','start_ticks'))
                or min(row['pid'],row['start_ticks'])<=0 or row['parent_pid']<0 or not isinstance(row.get('name'),str)):
            raise refused('BENCHMARK_LINEAGE_INVALID')
        if row['pid'] in processes and processes[row['pid']]!=row:
            raise refused('BENCHMARK_LINEAGE_INVALID')
        processes[row['pid']]=row
    anchor=processes.get(root)
    if anchor is None or anchor['start_ticks']!=ticks or anchor['name'].lower()!='ollama.exe':
        raise refused('BENCHMARK_ROOT_PID_REUSED')
    for pid in compute_pids:
        if type(pid) is not int or pid<=0:raise refused('BENCHMARK_GPU_PID_INVALID')
        if pid==owner_pid:continue
        seen=set(); cursor=pid
        for _ in range(9):
            row=processes.get(cursor)
            if cursor in seen or row is None or row['start_ticks']<ticks:break
            seen.add(cursor)
            if cursor==root:break
            parent=processes.get(row['parent_pid'])
            if parent is None or parent['start_ticks']>row['start_ticks']:break
            cursor=row['parent_pid']
        if cursor!=root:raise refused('GPU_FOREIGN_COMPUTE_PROCESS')
    return tuple(compute_pids)


def native_lineage(binding, compute_pids, *, with_evidence=False):
    if os.name!='nt':raise refused('NATIVE_WINDOWS_RESOURCE_PROBE_REQUIRED')
    if len(compute_pids)>64 or any(type(pid) is not int or pid<=0 for pid in compute_pids):
        raise refused('BENCHMARK_GPU_PID_INVALID')
    executable=shutil.which('powershell.exe')
    if not executable:raise refused('POWERSHELL_UNAVAILABLE')
    root=binding['ollama_pid']
    # Integers from a validated binding/telemetry only; no user command text,
    # executable paths, command lines or arbitrary process termination.
    ids=','.join(str(pid) for pid in {root,*(pid for pid in compute_pids if pid!=os.getpid())})
    script=("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        "$listeners=@(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction Stop);"
        "if($listeners.Count -ne 1 -or $listeners[0].LocalAddress -ne '127.0.0.1'){throw 'listener'};"
        "$rows=@{};"
        f"foreach($start in @({ids})){{$current=[int]$start;for($depth=0;$depth -lt 9;$depth++){{"
        "if($current -le 0){break};$p=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$current);if(!$p -or !$p.CreationDate){break};"
        "$rows[[string]$current]=[ordered]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;"
        "start_ticks=[long]$p.CreationDate.ToUniversalTime().Ticks;name=[string]$p.Name};"
        f"if($current -eq {root}){{break}};$current=[int]$p.ParentProcessId}}}};"
        "[ordered]@{listener_pid=[int]$listeners[0].OwningProcess;listener_address=[string]$listeners[0].LocalAddress;"
        "listener_port=[int]$listeners[0].LocalPort;processes=@($rows.Values)}|ConvertTo-Json -Depth 5 -Compress")
    result=run_bounded([executable,'-NoProfile','-NonInteractive','-Command',script],
                       timeout_seconds=10,output_limit=256*1024)
    document=json.loads(result.stdout.decode('utf-8-sig'))
    verified=validate_lineage(document,binding,compute_pids,os.getpid())
    return {'snapshot':document,'verified_compute_pids':list(verified)} if with_evidence else verified


class WarmBenchmark:
    def __init__(self,binding,*,check_root,admission,sink,check_binding=lambda:None,clock=time.monotonic,wall=time.time):
        validate_binding(binding,wall())
        self.binding=dict(binding);self.check_root=check_root;self._admission=admission
        self.admission=self._admit_resource
        self.sink=sink;self.check_binding=check_binding;self.clock=clock;self.wall=wall
        self.requests=0;self.active=False;self.calls=0;self.awaiting_response=False
        self.kind_counts={1:0,4:0}

    def ensure_current(self):
        self.check_binding();validate_binding(self.binding,self.wall())

    def _admit_resource(self):
        self.ensure_current()
        if self.requests>=20 and not self.active:raise refused('BENCHMARK_REQUEST_BUDGET_OR_MODEL_INVALID')
        return self._admission()

    def _event(self,event,**value):
        now=self.clock()
        self.sink({'event':event,'request_number':self.requests,'elapsed_seconds':now-self.started,'monotonic_seconds':now,
                   'wall_seconds':self.wall(),
                   'candidate_sha':self.binding['candidate_sha'],'authorization_sha256':self.binding['authorization_sha256'],**value})

    @contextmanager
    def request(self,transport,model,timeout,expected_calls,*,absolute_deadline=None):
        self.ensure_current()
        if (self.active or self.requests>=20 or model!=core.DEFAULT_MODEL or type(expected_calls) is not int
                or expected_calls not in (1,4) or self.kind_counts[expected_calls]>=10):
            raise refused('BENCHMARK_REQUEST_BUDGET_OR_MODEL_INVALID')
        self.requests+=1;self.active=True;self.calls=0;self.awaiting_response=False
        self.expected_calls=expected_calls
        self.kind_counts[expected_calls]+=1
        self.transport=transport;self.started=self.clock()
        primary=None;cleanup_error=None
        try:
            transport.bind_resource_baseline(self.binding['baseline_gpu_mib'])
            root=self.check_root()
            self._event('request_started',expected_calls=expected_calls,kind='image' if expected_calls==1 else 'video',root_proof=root)
            yield
            self.ensure_current()
            if self.calls!=expected_calls or self.awaiting_response:
                raise refused('BENCHMARK_CALL_DENOMINATOR_INVALID')
        except BaseException as error:
            primary=error
            raise
        finally:
            already_pending=core._RESOURCE_RELEASE_PENDING.is_set()
            core._RESOURCE_RELEASE_PENDING.set()
            restored=False
            try:
                release_deadline=self.clock()+30
                if absolute_deadline is not None:release_deadline=min(release_deadline,absolute_deadline)
                # An expired measurement may still release its owned model.
                # Reprove the cached root birth/listener; never trust a PID alone.
                root=self.check_root()
                transport.cleanup(model,timeout,release_deadline=release_deadline)
                if getattr(transport,'release_evidence',{}).get('state')!='released':
                    raise refused('GPU_RELEASE_UNPROVEN')
                self._event('request_finished',outcome='failed' if primary else 'succeeded',restored_unloaded=True,root_proof=root,
                            resource_release=getattr(transport,'release_evidence',None))
                restored=True
            except Exception as error:
                cleanup_error=error;core._RESOURCE_RELEASE_PENDING.set()
            finally:
                self.active=False
                if restored and not already_pending:core._RESOURCE_RELEASE_PENDING.clear()
            if cleanup_error is not None:
                raise BridgeError('RESOURCE_RELEASE_PENDING','warm profile restoration unproven',
                    subcode='BENCHMARK_RESTORE_UNPROVEN',details={'cleanup_error':type(cleanup_error).__name__,
                    'primary_error':type(primary).__name__ if primary else None}) from cleanup_error

    def before_call(self,payload):
        self.ensure_current()
        if not self.active or self.awaiting_response or self.calls>=self.expected_calls:raise refused('BENCHMARK_CALL_ORDER_INVALID')
        if payload.get('keep_alive')!=300 or payload.get('model')!=core.DEFAULT_MODEL:
            raise refused('BENCHMARK_PAYLOAD_INVALID')
        resource=self.admission()
        state=self.transport._control_request('GET','/api/ps',None,5)
        models=state.get('models')
        if not isinstance(models,list) or len(models)!=1 or not isinstance(models[0],dict):
            raise refused('BENCHMARK_MODEL_NOT_RESIDENT')
        model=models[0]
        if (model.get('model',model.get('name'))!=core.DEFAULT_MODEL or model.get('digest')!=self.binding['model_digest']
                or type(model.get('size_vram')) is not int or model['size_vram']<=0):
            raise refused('BENCHMARK_MODEL_NOT_RESIDENT')
        self.ensure_current()
        wire=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
        self._event('before_call',call_index=self.calls,api_ps=state,resource_admission=resource,
                    request_payload_sha256=hashlib.sha256(wire).hexdigest())
        self.awaiting_response=True
        self.ensure_current()
        return self.binding['expires_at']-self.wall()

    def after_call(self,raw):
        if not self.active or not self.awaiting_response:raise refused('BENCHMARK_CALL_ORDER_INVALID')
        self._event('after_call',call_index=self.calls,provider_raw_sha256=hashlib.sha256(raw.encode()).hexdigest())
        self.calls+=1;self.awaiting_response=False


_PROFILE=None
_PROFILE_GUARD=threading.Lock()


def configured_profile():
    if not os.environ.get('LVW_WARM_BENCHMARK'):return None
    if os.environ['LVW_WARM_BENCHMARK']!='run-owned-v1':raise refused('BENCHMARK_MODE_INVALID')
    global _PROFILE
    with _PROFILE_GUARD:
        if _PROFILE is not None:return _PROFILE
        import folder_paths
        directory=Path(folder_paths.get_temp_directory())
        try:
            for path in (directory,*directory.parents):
                if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400:
                    raise refused('BENCHMARK_TEMP_REPARSE_FORBIDDEN')
        except OSError as error:raise refused('BENCHMARK_BINDING_UNAVAILABLE') from error
        path=directory/'lvw-warm-profile.json'
        def read():
            try:
                if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400 or path.stat().st_size>4096:
                    raise refused('BENCHMARK_BINDING_INVALID')
                raw=path.read_bytes()
            except OSError as error:raise refused('BENCHMARK_BINDING_UNAVAILABLE') from error
            if len(raw)>4096:raise refused('BENCHMARK_BINDING_INVALID')
            return raw
        raw=read();binding=json.loads(raw);validate_binding(binding,time.time())
        def unchanged():
            if read()!=raw:raise refused('BENCHMARK_BINDING_CHANGED')
        root=lambda:native_lineage(binding,[],with_evidence=True)
        def admit():
            unchanged();validate_binding(binding,time.time())
            proof={}
            def check(csv):
                result=native_lineage(binding,[int(line.strip()) for line in csv.splitlines() if line.strip()],with_evidence=True)
                proof.update(result)
                return result['verified_compute_pids']
            resources=resource_preflight(warm=True,owned_pid_checker=check)
            resources['native_lineage']=proof
            return resources
        log=directory/'lvw-warm-events.jsonl'
        try:
            with log.open('x',encoding='utf-8'):pass
        except OSError as error:raise refused('BENCHMARK_LOG_SLOT_UNAVAILABLE') from error
        def sink(value):
            if log.is_symlink() or getattr(log.stat(),'st_file_attributes',0)&0x400:
                raise refused('BENCHMARK_LOG_REPARSE_FORBIDDEN')
            encoded=json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n'
            if log.stat().st_size+len(encoded.encode())>16*1024*1024:raise refused('BENCHMARK_LOG_LIMIT')
            with log.open('a',encoding='utf-8') as handle:handle.write(encoded)
        _PROFILE=WarmBenchmark(binding,check_root=root,admission=admit,sink=sink,check_binding=unchanged)
        return _PROFILE


def runtime_bridge(*,encoder=None,interruptible=False):
    benchmark=configured_profile()
    if benchmark is not None or interruptible:
        from .video_transport import InterruptibleOllamaTransport
        return core.BridgeOwner(transport=InterruptibleOllamaTransport(require_gpu_release=True),encoder=encoder,benchmark=benchmark)
    return core.BridgeOwner(encoder=encoder)
