"""Bounded, non-destructive cleanup of an idle LVW model, never arbitrary processes."""
from __future__ import annotations

import asyncio
import uuid

from . import resources
from .errors import AppError


async def sample() -> dict:
    try:
        async with asyncio.timeout(4):
            return {"values": await resources.snapshot(), "error": None}
    except (AppError, OSError, ValueError, TimeoutError):
        return {"values": None, "error": "RESOURCE_TELEMETRY_UNAVAILABLE"}


async def inventory(provider) -> list:
    rows = await provider._inventory()
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("name"), str)
        or not row["name"] or ("model" in row and not isinstance(row["model"], str))
        for row in rows
    ):
        raise ValueError("Unverifiable model inventory")
    return rows


def has_target(rows: list, model: str) -> bool:
    return any(model in {row["name"], row.get("model")} for row in rows)


async def cleanup(runtime) -> dict:
    """Caller holds both analysis-control and runtime locks for this entire operation."""
    result = {"operation_id": "cleanup_" + uuid.uuid4().hex, "status": "unknown",
              "actions": [], "before": None, "after": None, "verified": False,
              "reason": "RESOURCE_RELEASE_PENDING"}
    provider = runtime.provider
    try:
        async with asyncio.timeout(43):
            result["before"] = await sample()
            lease = getattr(provider, "_lease", None)
            if lease is not None:
                result["actions"].append("release_lvw_lease")
                released = await provider.release(lease[0])
                # A failed release retains the provider's lease for explicit later recovery.
                if released is True and not has_target(await inventory(provider), provider.model):
                    result.update(status="released", verified=True, reason=None)
            else:
                rows = await inventory(provider)
                if not has_target(rows, provider.model):
                    result.update(status="noop", verified=True, reason="NO_LVW_MODEL_LOADED")
                elif not runtime._owned() or not owned_listener(runtime):
                    result.update(status="blocked", reason="RUNTIME_NOT_OWNED")
                elif any(provider.model not in {row["name"], row.get("model")} for row in rows):
                    result.update(status="blocked", reason="EXTERNAL_MODEL_PRESENT")
                else:
                    # Recheck immediately before mutation; no externally managed daemon is stopped.
                    if not runtime._owned() or not owned_listener(runtime):
                        result.update(status="blocked", reason="RUNTIME_NOT_OWNED")
                    else:
                        result["actions"].append("unload_configured_model")
                        await provider.unload_idle_model()
                        stable = 0
                        for _ in range(12):
                            stable = stable + 1 if not has_target(await inventory(provider), provider.model) else 0
                            if stable >= 3:
                                result.update(status="released", verified=True, reason=None)
                                break
                            await asyncio.sleep(0.5)
            result["after"] = await sample()
    except (AppError, OSError, ValueError, TimeoutError):
        result.update(status="unknown", verified=False, reason="RESOURCE_RELEASE_PENDING")
    except Exception:
        # Transport/protocol failure must never become a success or expose native paths.
        result.update(status="unknown", verified=False, reason="RESOURCE_RELEASE_PENDING")
    return result


def owned_listener(runtime) -> bool:
    if not runtime._native:
        # The ordinary Windows launcher always supplies a native custody record.
        # No-native processes are injectable test doubles, not production custody proof.
        return False
    from .native_runtime import proof
    return proof(runtime._native).get("listener_owned") is True
