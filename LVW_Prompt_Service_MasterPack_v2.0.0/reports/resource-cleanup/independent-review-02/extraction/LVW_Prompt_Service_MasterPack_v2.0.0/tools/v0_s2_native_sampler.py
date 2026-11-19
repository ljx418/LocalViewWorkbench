"""Low-level native telemetry worker; caller must bind/authorize before launch.

No model or service starts. The only child is the pinned nvidia-smi executable.
The Stage runner owns the stop marker, output root and declared process set.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time


def parse_gpu(line):
    values=line.decode('ascii').strip().split(',')
    if len(values)!=2 or values[0].strip()!='0' or not values[1].strip().isdigit():
        raise ValueError('GPU_SAMPLE_INVALID_OR_MULTIPLE_DEVICES')
    return int(values[1].strip())


class WindowsMemory:
    """Pin read-only process handles once; never reopen a recycled PID."""
    def __init__(self,pids):
        if os.name!='nt':raise ValueError('NATIVE_WINDOWS_REQUIRED')
        from ctypes import wintypes as w
        class MemoryStatus(ctypes.Structure):
            _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(name,ctypes.c_ulonglong) for name in
                ('total_phys','available_phys','total_page','available_page','total_virtual','available_virtual','extended')]
        class Counters(ctypes.Structure):
            _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(name,ctypes.c_size_t) for name in
                ('peak_working','working','quota_peak_paged','quota_paged','quota_peak_nonpaged',
                 'quota_nonpaged','pagefile','peak_pagefile','private')]
        self.status_type=MemoryStatus;self.counters_type=Counters
        self.kernel=ctypes.windll.kernel32;self.psapi=ctypes.windll.psapi
        self.kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.kernel.OpenProcess.restype=w.HANDLE
        self.kernel.CloseHandle.argtypes=[w.HANDLE];self.kernel.CloseHandle.restype=w.BOOL
        self.kernel.GetProcessTimes.argtypes=[w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4
        self.kernel.GetProcessTimes.restype=w.BOOL
        self.psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Counters),w.DWORD]
        self.psapi.GetProcessMemoryInfo.restype=w.BOOL
        self.handles={};self.start_ticks={}
        try:
            for pid in pids:
                handle=self.kernel.OpenProcess(0x0410,False,pid)
                if not handle:raise ValueError('PRIVATE_PROCESS_HANDLE_UNAVAILABLE')
                self.handles[pid]=handle
                creation,exit_time,kernel_time,user_time=(w.FILETIME() for _ in range(4))
                if not self.kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in (creation,exit_time,kernel_time,user_time)]):
                    raise ValueError('PRIVATE_PROCESS_BIRTH_UNAVAILABLE')
                self.start_ticks[str(pid)]=(creation.dwHighDateTime<<32)|creation.dwLowDateTime
        except BaseException:self.close();raise

    def snapshot(self):
        status=self.status_type();status.length=ctypes.sizeof(status)
        if not self.kernel.GlobalMemoryStatusEx(ctypes.byref(status)):raise ValueError('RAM_SAMPLE_FAILED')
        private={}
        for pid,handle in self.handles.items():
            counters=self.counters_type();counters.cb=ctypes.sizeof(counters)
            if not self.psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),ctypes.sizeof(counters)):
                raise ValueError('PRIVATE_PROCESS_SAMPLE_FAILED')
            private[str(pid)]=int(counters.private)
        return int(status.available_phys//(1024*1024)),private

    def close(self):
        for handle in self.handles.values():self.kernel.CloseHandle(handle)
        self.handles.clear()


def sample_stream(process,*,stopped,memory,emit,max_seconds,clock=time.monotonic):
    """No dropped samples: gaps, parse failures and an overrun are terminal."""
    entries=queue.Queue(maxsize=2);reader_error=[];closing=threading.Event()
    def read():
        try:
            while not closing.is_set():
                line=process.stdout.readline(256)
                if not line:
                    if not closing.is_set():reader_error.append('GPU_STREAM_ENDED')
                    return
                if len(line)>=256 or not line.endswith(b'\n'):raise ValueError('GPU_LINE_LIMIT')
                entry=(clock(),parse_gpu(line))
                entries.put(entry,timeout=.5)
        except Exception as error:
            if not closing.is_set():reader_error.append(type(error).__name__)
    started=clock();last=None;count=0
    reader=threading.Thread(target=read,daemon=True)
    try:
        reader.start()
        while True:
            if stopped():return {'samples':count,'stopped_by_owner':True}
            if clock()-started>max_seconds:raise ValueError('SAMPLER_DEADLINE')
            if reader_error:raise ValueError('GPU_STREAM_FAILED')
            try:observed,gpu=entries.get(timeout=.1)
            except queue.Empty:continue
            if last is not None and (observed<=last or observed-last>1.5):raise ValueError('RESOURCE_SAMPLE_GAP')
            ram,private=memory.snapshot()
            emit({'sample_index':count,'monotonic_seconds':observed,'gpu_used_mib':gpu,
                  'available_ram_mib':ram,'private_bytes':private})
            if gpu>=23552 or ram<2048:raise ValueError('RESOURCE_THRESHOLD_EXCEEDED')
            last=observed;count+=1
            if count>7202:raise ValueError('SAMPLER_SAMPLE_LIMIT')
    finally:
        closing.set()
        try:
            if process.poll() is None:
                try:process.terminate();process.wait(timeout=3)
                except (OSError,subprocess.TimeoutExpired):
                    if process.poll() is None:process.kill();process.wait(timeout=3)
        finally:
            if reader.ident is not None:reader.join(timeout=2)
            process.stdout.close()
            memory.close()
        if reader.is_alive():raise ValueError('SAMPLER_READER_CLEANUP_UNPROVEN')


def execute(args):
    root=Path(args.run_root).resolve(strict=True)
    if not root.is_dir() or any(p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400 for p in (root,*root.parents)):
        raise ValueError('SAMPLER_ROOT_INVALID')
    binary=Path(args.nvidia_smi)
    if (not binary.is_absolute() or binary.name.lower()!='nvidia-smi.exe' or binary.is_symlink()
            or not binary.is_file() or binary.stat().st_size>64*1024*1024
            or not re.fullmatch('[0-9a-f]{64}',args.binary_sha256)
            or hashlib.sha256(binary.read_bytes()).hexdigest()!=args.binary_sha256):
        raise ValueError('SAMPLER_EXECUTABLE_IDENTITY_MISMATCH')
    if (type(args.max_seconds) is not int or not 1<=args.max_seconds<=7200 or not 1<=len(args.private_pids)<=16
            or len(set(args.private_pids))!=len(args.private_pids)
            or any(type(pid) is not int or not 0<pid<=0xffffffff for pid in args.private_pids)):
        raise ValueError('SAMPLER_BUDGET_INVALID')
    stop=root/'resource-sampler.stop'
    if stop.exists() or stop.is_symlink():raise ValueError('SAMPLER_STOP_SLOT_NOT_FRESH')
    receipt=root/'resource-sampler.receipt.json'
    if receipt.exists() or receipt.is_symlink():raise ValueError('SAMPLER_RECEIPT_SLOT_NOT_FRESH')
    with (root/'resource-sampler.pid').open('x',encoding='ascii') as handle:handle.write(str(os.getpid()))
    memory=None;process=None;result={'decision':'NO_GO','stage_pass_claim':False,'nvidia_binary_sha256':args.binary_sha256}
    with (root/'resource-trace.jsonl').open('x',encoding='utf-8') as output:
        try:
            memory=WindowsMemory(args.private_pids)
            result.update(private_process_start_ticks=memory.start_ticks,
                          private_birth_basis='windows_filetime_100ns_since1601',private_process_set=args.private_pids)
            process=subprocess.Popen([str(binary),'--query-gpu=index,memory.used','--format=csv,noheader,nounits',
                '--loop-ms=1000'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False)
            def emit(value):
                text=json.dumps(value,separators=(',',':'))+'\n'
                if output.tell()+len(text.encode())>8*1024*1024:raise ValueError('SAMPLER_OUTPUT_LIMIT')
                output.write(text);output.flush()
            summary=sample_stream(process,stopped=stop.exists,memory=memory,emit=emit,max_seconds=args.max_seconds)
            result.update(summary)
            if summary['samples']<2:raise ValueError('SAMPLER_INSUFFICIENT_SAMPLES')
            result['nvidia_binary_sha256_after']=hashlib.sha256(binary.read_bytes()).hexdigest()
            if result['nvidia_binary_sha256_after']!=args.binary_sha256:raise ValueError('SAMPLER_EXECUTABLE_CHANGED_DURING_RUN')
            result['decision']='RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'
        except Exception as error:result['error_type']=type(error).__name__;result['error_code']=str(error) if isinstance(error,ValueError) else 'SAMPLER_FAILED'
        finally:
            if memory is not None:memory.close()
            result['owned_gpu_query_exited']=process is None or process.poll() is not None
            if not result['owned_gpu_query_exited']:result['decision']='NO_GO'
            with receipt.open('x',encoding='utf-8') as handle:handle.write(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute-sampler',action='store_true')
    parser.add_argument('--run-root',required=True);parser.add_argument('--nvidia-smi',required=True)
    parser.add_argument('--binary-sha256',required=True);parser.add_argument('--private-pids',type=int,nargs='+',required=True)
    parser.add_argument('--max-seconds',type=int,required=True);args=parser.parse_args()
    if not args.execute_sampler:parser.error('parent authorization and explicit execution flag required')
    result=execute(args);print(json.dumps({'decision':result['decision']}))
    raise SystemExit(0 if result['decision']=='RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE' else 1)
