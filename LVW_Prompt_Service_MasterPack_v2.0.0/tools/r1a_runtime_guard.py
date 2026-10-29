#!/usr/bin/env python3
"""Pure/runtime helpers for cross-domain listener and ownership checks."""

from __future__ import annotations

import json
import os
from pathlib import Path


def parse_windows_listener_json(raw: str) -> list[int]:
    if not raw.strip():
        return []
    value = json.loads(raw)
    if value is None:
        return []
    if isinstance(value, int):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, int) for item in value):
        raise ValueError("INVALID_WINDOWS_LISTENER_RESULT")
    return sorted(set(value))


def _listener_inodes(port: int, proc_root: Path) -> set[str]:
    wanted = f"{port:04X}"
    inodes: set[str] = set()
    for name in ("tcp", "tcp6"):
        table = proc_root / "net" / name
        if not table.is_file():
            continue
        for line in table.read_text(encoding="ascii", errors="strict").splitlines()[1:]:
            fields = line.split()
            if len(fields) < 10:
                continue
            local = fields[1]
            state = fields[3]
            if local.rsplit(":", 1)[-1].upper() == wanted and state == "0A":
                inodes.add(fields[9])
    return inodes


def wsl_listener_pids(port: int, proc_root: Path = Path("/proc")) -> list[int]:
    inodes = _listener_inodes(port, proc_root)
    if not inodes:
        return []
    owners: set[int] = set()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        fd_root = entry / "fd"
        try:
            fds = list(fd_root.iterdir())
        except (FileNotFoundError, PermissionError):
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except (FileNotFoundError, PermissionError, OSError):
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                owners.add(int(entry.name))
                break
    return sorted(owners)


def linux_process_identity(pid: int, proc_root: Path = Path("/proc")) -> dict[str, int] | None:
    stat = proc_root / str(pid) / "stat"
    try:
        raw = stat.read_text(encoding="ascii", errors="strict")
    except (FileNotFoundError, PermissionError):
        return None
    close = raw.rfind(")")
    fields = raw[close + 2:].split()
    if close < 0 or len(fields) < 20:
        return None
    return {"pid": pid, "start_ticks": int(fields[19])}


def linux_identity_matches(expected: dict[str, int], proc_root: Path = Path("/proc")) -> bool:
    current = linux_process_identity(expected["pid"], proc_root)
    return current == {"pid": expected["pid"], "start_ticks": expected["start_ticks"]}


def windows_identity_matches(expected: dict, current: dict | None) -> bool:
    if not current:
        return False
    expected_path = str(expected.get("executable_path", "")).replace("\\", "/").lower()
    current_path = str(current.get("executable_path", "")).replace("\\", "/").lower()
    return (
        int(current.get("pid", -1)) == int(expected.get("pid", -2))
        and str(current.get("start_filetime_utc", "")) == str(expected.get("start_filetime_utc", "!"))
        and current_path == expected_path
        and bool(expected_path)
    )


def may_stop_windows_listener(expected: dict, current: dict | None, listener_pids: list[int]) -> bool:
    return windows_identity_matches(expected, current) and listener_pids == [int(expected["pid"])]
