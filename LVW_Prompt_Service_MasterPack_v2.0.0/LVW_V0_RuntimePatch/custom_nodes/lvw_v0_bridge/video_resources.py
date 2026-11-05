"""Read-only native Windows resource admission for the V0 video owner."""
import ctypes
import http.client
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
import re
import hashlib

from .core import BridgeError, DEFAULT_MODEL, MAX_NUM_CTX
from .resource_policy import PolicyError, admit, profile
from .video_process import run_bounded


def busy(reason):
    return BridgeError("RESOURCE_BUSY", "video resource admission refused", subcode=reason)


def validate_snapshot(gpu_csv, process_csv, available_ram_mib, *, owner_pid, warm=False, owned_compute_pids=(), driver_model=None):
    try:
        rows = [[int(v.strip()) for v in line.split(",")] for line in gpu_csv.splitlines() if line.strip()]
        if len(rows) != 1 or len(rows[0]) != 3:
            raise ValueError()
        total, used, free = rows[0]
        if min(total, used, free) < 0 or total == 0 or used > total or free > total or used + free > total:
            raise ValueError()
        pids = [int(line.strip()) for line in process_csv.splitlines() if line.strip()]
        if len(pids)>64 or len(pids)!=len(set(pids)) or driver_model not in (None,'WDDM','TCC'):raise ValueError()
        if (any(pid <= 0 for pid in pids) or type(available_ram_mib) is not int or available_ram_mib < 0
                or type(owner_pid) is not int or owner_pid <= 0):
            raise ValueError()
        if (type(warm) is not bool or not isinstance(owned_compute_pids, tuple)
                or any(type(pid) is not int or pid <= 0 for pid in owned_compute_pids)
                or (owned_compute_pids and not warm)):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise busy("RESOURCE_TELEMETRY_INVALID") from exc
    try:policy=admit([[0,total,used,free]],warm=warm)
    except PolicyError as error:raise busy(error.reason) from error
    if available_ram_mib < 2048:
        raise busy("HOST_RAM_BELOW_LIMIT")
    unowned=[pid for pid in pids if pid not in {owner_pid,*owned_compute_pids}]
    if unowned and driver_model!='WDDM':
        raise busy("GPU_FOREIGN_COMPUTE_PROCESS")
    return {"gpu_count":1,"gpu_total_mib":total,"gpu_used_mib":used,"gpu_free_mib":free,
            "available_ram_mib":available_ram_mib,"foreign_compute_processes":len(unowned),
            "owner_pid":owner_pid,"compute_pids":pids,"resource_policy":policy,
            "driver_model":driver_model,"gpu_process_admission":"SHARED_CAPACITY" if driver_model=='WDDM' else "STRICT_COMPUTE",
            "owned_compute_pids":[pid for pid in pids if pid in {owner_pid,*owned_compute_pids}],"unowned_compute_pids":unowned}


def parse_native_snapshot(raw):
    if len(raw)>262144:raise busy('RESOURCE_TELEMETRY_INVALID')
    try:
        gpus=ET.fromstring(raw).findall('gpu')
        if len(gpus)!=1:raise ValueError()
        gpu=gpus[0];mode=gpu.findtext('driver_model/current_dm')
        if mode not in {'WDDM','TCC'}:raise ValueError()
        memory=[]
        for field in ('total','used','free'):
            value=gpu.findtext('fb_memory_usage/'+field,'')
            if not re.fullmatch('[0-9]+ MiB',value):raise ValueError()
            memory.append(int(value.split()[0]))
        pids=[]
        for process in gpu.findall('processes/process_info'):
            value=process.findtext('pid','')
            if not value.isdigit() or int(value)<=0:raise ValueError()
            pids.append(int(value))
        if len(pids)>64 or len(pids)!=len(set(pids)):raise ValueError()
        if gpu.find('processes') is None:raise ValueError()
        return mode,memory,pids
    except (ET.ParseError,ValueError,TypeError) as error:raise busy('RESOURCE_TELEMETRY_INVALID') from error


def probe_identity(executable):
    with open(executable,'rb') as stream:
        before=os.fstat(stream.fileno());digest=hashlib.sha256()
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        after=os.fstat(stream.fileno())
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise busy('RESOURCE_TELEMETRY_INVALID')
    return digest.hexdigest()


def recompute_probe(probe):
    """Pure reparse of retained raw evidence, shared by production and review."""
    try:
        csv=probe['gpu_csv'];xml=probe['xml']
        if (not isinstance(csv,str) or not isinstance(xml,str) or len(csv.encode())>65536
                or not re.fullmatch('[0-9a-f]{64}',probe['nvidia_binary_sha256'])
                or hashlib.sha256(xml.encode('utf-8')).hexdigest()!=probe['xml_sha256']):raise ValueError()
        mode,memory,pids=parse_native_snapshot(xml.encode('utf-8'))
        first=[[int(v.strip()) for v in row.split(',')] for row in csv.splitlines() if row.strip()]
        if len(first)!=1 or len(first[0])!=3 or first[0][0]!=memory[0]:raise ValueError()
        for row in (first[0],memory):
            if min(row)<0 or row[0]<=0 or row[1]+row[2]>row[0]:raise ValueError()
        conservative=[memory[0],max(first[0][1],memory[1]),min(first[0][2],memory[2])]
        return mode,conservative,pids
    except (KeyError,TypeError,ValueError,UnicodeError) as error:raise busy('RESOURCE_TELEMETRY_INVALID') from error


def windows_available_ram_mib():
    if os.name != "nt":
        raise busy("NATIVE_WINDOWS_RESOURCE_PROBE_REQUIRED")
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length",ctypes.c_ulong),("load",ctypes.c_ulong)] + [
            (name,ctypes.c_ulonglong) for name in ("total_phys","available_phys","total_page",
                "available_page","total_virtual","available_virtual","extended")]
    value = MemoryStatus(); value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise busy("NATIVE_RAM_PROBE_FAILED")
    return value.available_phys // (1024 * 1024)


def host_resource_preflight():
    available = windows_available_ram_mib()
    if type(available) is not int or available < 2048:
        raise busy("HOST_RAM_BELOW_LIMIT")
    return {"available_ram_mib": available}


def gpu_used_mib(deadline):
    remaining=deadline-time.monotonic()
    executable=shutil.which('nvidia-smi')
    if not executable or remaining<=0:raise busy('GPU_RELEASE_PROBE_UNAVAILABLE')
    value=run_bounded([executable,'--query-gpu=memory.used','--format=csv,noheader,nounits'],
                      timeout_seconds=min(5,remaining),output_limit=65536)
    rows=value.stdout.decode('ascii').splitlines()
    if len(rows)!=1 or not rows[0].strip().isdigit():raise busy('GPU_RELEASE_TELEMETRY_INVALID')
    return int(rows[0].strip())


def verify_model_profile():
    """One bounded literal-loopback catalog read; no inference or retries."""
    connection=http.client.HTTPConnection('127.0.0.1',11434,timeout=2)
    try:
        deadline=time.monotonic()+2
        connection.request('GET','/api/tags');sock=connection.sock;response=connection.getresponse()
        if response.status!=200:raise ValueError('catalog unavailable')
        raw=bytearray()
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('catalog deadline')
            if sock is not None:sock.settimeout(remaining)
            part=response.read1(min(8192,1024*1024-len(raw)+1))
            if not part:break
            raw.extend(part)
            if len(raw)>1024*1024:raise ValueError('catalog limit')
        values=json.loads(raw);models=values.get('models')
        if not isinstance(models,list):raise ValueError('catalog shape')
        matched=[m for m in models if isinstance(m,dict) and (m.get('name')==DEFAULT_MODEL or m.get('model')==DEFAULT_MODEL)]
        if len(matched)!=1:raise ValueError('catalog identity')
        return profile(model=DEFAULT_MODEL,digest=matched[0].get('digest'),num_ctx=MAX_NUM_CTX)
    except (OSError,http.client.HTTPException,ValueError,TypeError,RecursionError) as error:
        raise busy('GPU_MODEL_PROFILE_UNVERIFIED') from error
    finally:connection.close()


def resource_preflight(*, warm=False, owned_pid_checker=None):
    if warm and not callable(owned_pid_checker):
        raise busy('WARM_OWNERSHIP_PROOF_REQUIRED')
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise busy("NVIDIA_SMI_UNAVAILABLE")
    if not warm:verify_model_profile()
    try:
        identity=probe_identity(executable)
        gpu = run_bounded([executable,"--query-gpu=memory.total,memory.used,memory.free",
                           "--format=csv,noheader,nounits"], timeout_seconds=5, output_limit=65536)
        observed = run_bounded([executable,'-q','-x'],timeout_seconds=5,output_limit=262144)
        if probe_identity(executable)!=identity:raise busy('RESOURCE_TELEMETRY_INVALID')
        probe={'gpu_csv':gpu.stdout.decode('ascii'),'xml':observed.stdout.decode('utf-8'),
               'xml_sha256':hashlib.sha256(observed.stdout).hexdigest(),'nvidia_binary_sha256':identity}
        mode,conservative,pids=recompute_probe(probe)
        process_csv='\n'.join(str(pid) for pid in pids)
        owned=tuple(owned_pid_checker(process_csv,shared_gpu=True) if mode=='WDDM' else owned_pid_checker(process_csv)) if warm else ()
        result=validate_snapshot(','.join(map(str,conservative)), process_csv,
                                 windows_available_ram_mib(), owner_pid=os.getpid(), warm=warm, owned_compute_pids=owned,driver_model=mode)
        result['native_probe']=probe
        return result
    except (BridgeError, OSError, UnicodeError, ValueError, TypeError) as exc:
        raise busy("RESOURCE_PREFLIGHT_UNPROVEN") from exc
