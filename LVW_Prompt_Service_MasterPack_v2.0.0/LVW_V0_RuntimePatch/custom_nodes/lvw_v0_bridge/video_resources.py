"""Read-only native Windows resource admission for the V0 video owner."""
import ctypes
import os
import shutil

from .core import BridgeError
from .video_process import run_bounded


def busy(reason):
    return BridgeError("RESOURCE_BUSY", "video resource admission refused", subcode=reason)


def validate_snapshot(gpu_csv, process_csv, available_ram_mib, *, owner_pid):
    try:
        rows = [[int(v.strip()) for v in line.split(",")] for line in gpu_csv.splitlines() if line.strip()]
        if len(rows) != 1 or len(rows[0]) != 3:
            raise ValueError()
        total, used, free = rows[0]
        if min(total, used, free) < 0 or total == 0 or used > total or free > total or abs(total - used - free) > 256:
            raise ValueError()
        pids = [int(line.strip()) for line in process_csv.splitlines() if line.strip()]
        if (any(pid <= 0 for pid in pids) or type(available_ram_mib) is not int or available_ram_mib < 0
                or type(owner_pid) is not int or owner_pid <= 0):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise busy("RESOURCE_TELEMETRY_INVALID") from exc
    if total < 23 * 1024:
        raise busy("GPU_CAPACITY_INSUFFICIENT")
    if used > 4096:
        raise busy("GPU_PREFLIGHT_USED_MEMORY_EXCEEDED")
    if available_ram_mib < 2048:
        raise busy("HOST_RAM_BELOW_LIMIT")
    if any(pid != owner_pid for pid in pids):
        raise busy("GPU_FOREIGN_COMPUTE_PROCESS")
    return {"gpu_count":1,"gpu_total_mib":total,"gpu_used_mib":used,"gpu_free_mib":free,
            "available_ram_mib":available_ram_mib,"foreign_compute_processes":0}


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


def resource_preflight():
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise busy("NVIDIA_SMI_UNAVAILABLE")
    try:
        gpu = run_bounded([executable,"--query-gpu=memory.total,memory.used,memory.free",
                           "--format=csv,noheader,nounits"], timeout_seconds=5, output_limit=65536)
        processes = run_bounded([executable,"--query-compute-apps=pid","--format=csv,noheader,nounits"],
                                timeout_seconds=5, output_limit=65536)
        return validate_snapshot(gpu.stdout.decode("ascii"), processes.stdout.decode("ascii"),
                                 windows_available_ram_mib(), owner_pid=os.getpid())
    except (BridgeError, UnicodeError) as exc:
        raise busy("RESOURCE_PREFLIGHT_UNPROVEN") from exc
