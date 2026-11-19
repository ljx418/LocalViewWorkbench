"""Read-only GPU evidence used by the local model lease; no process discovery/kill."""
from __future__ import annotations
import asyncio
from pathlib import Path
import shutil
from .errors import AppError
from .video_kernel import process_module, core


async def snapshot() -> dict:
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise AppError("RESOURCE_BUSY", "GPU状态探测不可用，未启动推理", status_code=503)
    try:
        result = await asyncio.to_thread(process_module.run_bounded, [executable,
            "--query-gpu=memory.used,memory.free,memory.total", "--format=csv,noheader,nounits"],
            timeout_seconds=3, output_limit=65536)
        rows = result.stdout.decode("ascii").strip().splitlines()
        if len(rows) != 1:
            raise ValueError("one local GPU required")
        used, free, total = map(int, rows[0].split(","))
        available = int(next(line for line in Path("/proc/meminfo").read_text().splitlines()
                             if line.startswith("MemAvailable:")).split()[1]) // 1024
        if min(used, free, total, available) < 0 or total <= 0 or used + free > total:
            raise ValueError("invalid telemetry")
        return {"gpu_used_mib": used, "gpu_free_mib": free, "gpu_total_mib": total,
                "available_ram_mib": available}
    except (core.BridgeError, OSError, ValueError, StopIteration) as error:
        raise AppError("RESOURCE_BUSY", "GPU/RAM状态无法确认，未启动新推理", status_code=503) from error
