"""Stop only LVW's original native handle; never send an unbound model-unload POST."""
from __future__ import annotations

import asyncio
import re
import uuid

from . import resources
from .errors import AppError


async def sample() -> dict:
    try:
        async with asyncio.timeout(4):
            return {"values": await resources.snapshot(), "error": None}
    except Exception:
        return {"values": None, "error": "RESOURCE_TELEMETRY_UNAVAILABLE"}


async def inventory(provider) -> list:
    rows = await provider._inventory()
    if not isinstance(rows, list):
        raise ValueError("Invalid inventory")
    names = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("name"), str)
                or not row["name"].strip() or row["name"] != row["name"].strip()
                or row.get("model", row["name"]) != row["name"]
                or row["name"] in names
                or not isinstance(row.get("digest"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["digest"])
                or type(row.get("size_vram")) is not int or row["size_vram"] < 0):
            raise ValueError("Ambiguous model identity")
        names.add(row["name"])
    return rows


def new_result() -> dict:
    return {"operation_id": "cleanup_" + uuid.uuid4().hex, "status": "unknown",
            "actions": [], "before": {"values": None, "error": "NOT_OBSERVED"},
            "after": {"values": None, "error": "NOT_OBSERVED"}, "verified": False,
            "reason": "RESOURCE_RELEASE_PENDING", "runtime": None,
            "runtime_error": "NOT_OBSERVED", "verification_scope": "original_service_exit_and_resource_bound"}


async def cleanup(runtime) -> dict:
    """One deadline includes lock wait, original-handle stop, observations and final commit."""
    from .native_runtime import proof
    result = new_result()
    provider = runtime.provider
    try:
        async with asyncio.timeout(43):
            async with runtime._lock:
                result["before"] = await sample()
                pending = runtime._cleanup_pending
                lease = getattr(provider, "_lease", None)
                completed = runtime._cleanup_completed
                if completed is not None and lease is None and runtime._native is None and not runtime._owned():
                    if proof(completed["native"]) == completed["identity"]:
                        result["runtime"] = await runtime.status()
                        result["runtime_error"] = None
                        if not result["runtime"]["ollama"]["reachable"]:
                            result["after"] = await sample()
                            result.update(status="noop", verified=True, reason="NO_LVW_SERVICE_RUNNING")
                            return result
                if pending is None:
                    rows = await inventory(provider)
                    target = [row for row in rows if row["name"] == provider.model]
                    if any(row["name"] != provider.model for row in rows):
                        result.update(status="blocked", reason="EXTERNAL_MODEL_PRESENT")
                    elif not target and lease is None:
                        result.update(status="noop", verified=True, reason="NO_LVW_MODEL_LOADED")
                    elif not runtime._native or not runtime._owned():
                        result.update(status="blocked", reason="RUNTIME_NOT_OWNED")
                    else:
                        native = runtime._native
                        identity = proof(native)
                        # This record identifies the original handle only. It never authorizes
                        # a POST to whichever listener happens to be on the old port.
                        if not identity or identity.get("state") not in {"starting", "listening"}:
                            result.update(status="blocked", reason="NATIVE_CUSTODY_UNPROVEN")
                        elif result["before"]["values"] is not None:
                            before_used = result["before"]["values"]["gpu_used_mib"]
                            target_mib = (target[0]["size_vram"] + 1048575) // 1048576 if target else 0
                            bound = max(0, before_used - target_mib) + 1024
                            if lease is not None:
                                baseline = lease[1].get("gpu_used_mib")
                                if type(baseline) is not int or baseline < 0:
                                    raise ValueError("Lease baseline unavailable")
                                bound = min(bound, baseline + 1024)
                            pending = {"native": native, "identity": identity, "lease": lease,
                                       "gpu_max_mib": bound}
                            runtime._cleanup_pending = pending
                            result["actions"].append("stop_original_lvw_model_service")
                            await runtime._stop_owned()
                if pending is not None:
                    if runtime._native is pending["native"]:
                        result["actions"].append("reconcile_original_lvw_model_service")
                        await runtime._stop_owned()
                    identity = proof(pending["native"])
                    expected = pending["identity"]
                    exited = (identity.get("state") == "exited"
                              and identity.get("pid") == expected.get("pid")
                              and identity.get("birth_ticks") == expected.get("birth_ticks")
                              and identity.get("listener_owned") is False)
                    if not exited or runtime._owned() or runtime._native is not None:
                        raise AppError("RESOURCE_RELEASE_PENDING", "Original native exit unproven")
                    for _ in range(3):
                        result["after"] = await sample()
                        values = result["after"]["values"]
                        if values is None or values["gpu_used_mib"] > pending["gpu_max_mib"]:
                            raise AppError("RESOURCE_RELEASE_PENDING", "Resource bound unproven")
                        await asyncio.sleep(0.25)
                else:
                    result["after"] = await sample()
                result["runtime"] = await runtime.status()
                result["runtime_error"] = None
                if pending is not None:
                    # A replacement daemon is never stopped or sent an unload.
                    if result["runtime"]["ollama"]["reachable"]:
                        raise AppError("RESOURCE_RELEASE_PENDING", "Replacement listener present")
                    if getattr(provider, "_lease", None) is not pending["lease"]:
                        raise AppError("RESOURCE_RELEASE_PENDING", "Lease changed during cleanup")
                    # No fallible observation follows this single reconciliation commit.
                    provider._lease = None
                    provider._sent = False
                    runtime._cleanup_completed = {"native": pending["native"], "identity": identity}
                    runtime._cleanup_pending = None
                    runtime.last_error = None
                    result.update(status="released", verified=True, reason=None)
    except TimeoutError:
        result.update(status="unknown", verified=False, reason="RESOURCE_CLEANUP_TIMEOUT")
    except Exception:
        result.update(status="unknown", verified=False, reason="RESOURCE_RELEASE_PENDING")
    if result["runtime"] is None:
        result["runtime_error"] = result["reason"]
    if result["before"]["values"] is None and result["before"]["error"] == "NOT_OBSERVED":
        result["before"]["error"] = result["reason"]
    if result["after"]["values"] is None and result["after"]["error"] == "NOT_OBSERVED":
        result["after"]["error"] = result["reason"]
    return result
