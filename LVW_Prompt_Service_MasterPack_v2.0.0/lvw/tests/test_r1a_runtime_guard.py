from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.r1a_runtime_guard import (
    linux_identity_matches,
    may_stop_windows_listener,
    parse_windows_listener_json,
    windows_identity_matches,
    wsl_listener_pids,
)
from tools.r1a_live_acceptance import assert_ports_free


def _fake_proc(tmp_path: Path, port: int = 18765, pid: int = 321, inode: str = "777") -> Path:
    proc = tmp_path / "proc"
    (proc / "net").mkdir(parents=True)
    (proc / "net" / "tcp").write_text(
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        f"   0: 0100007F:{port:04X} 00000000:0000 0A 00000000:00000000 00:00000000 "
        f"00000000 1000 0 {inode} 1 0000000000000000\n",
        encoding="ascii",
    )
    (proc / "net" / "tcp6").write_text(
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n",
        encoding="ascii",
    )
    (proc / str(pid) / "fd").mkdir(parents=True)
    os.symlink(f"socket:[{inode}]", proc / str(pid) / "fd" / "3")
    (proc / str(pid) / "stat").write_text(
        f"{pid} (python worker) S " + " ".join(["0"] * 18 + ["12345"] + ["0"] * 4),
        encoding="ascii",
    )
    return proc


def test_windows_listener_parser_is_strict():
    assert parse_windows_listener_json("") == []
    assert parse_windows_listener_json("42") == [42]
    assert parse_windows_listener_json("[42,42,7]") == [7, 42]
    with pytest.raises(ValueError):
        parse_windows_listener_json('["42"]')


def test_wsl_only_listener_is_detected(tmp_path: Path):
    proc = _fake_proc(tmp_path)
    assert wsl_listener_pids(18765, proc) == [321]
    assert wsl_listener_pids(11434, proc) == []


def test_linux_identity_rejects_pid_reuse(tmp_path: Path):
    proc = _fake_proc(tmp_path)
    assert linux_identity_matches({"pid": 321, "start_ticks": 12345}, proc)
    assert not linux_identity_matches({"pid": 321, "start_ticks": 99999}, proc)


def test_windows_cleanup_rejects_non_owned_or_replaced_listener():
    expected = {"pid": 44, "start_filetime_utc": "100", "executable_path": "C:/Ollama/ollama.exe"}
    current = dict(expected)
    assert windows_identity_matches(expected, current)
    assert may_stop_windows_listener(expected, current, [44])
    assert not may_stop_windows_listener(expected, current, [45])
    assert not may_stop_windows_listener(expected, {**current, "start_filetime_utc": "101"}, [44])
    assert not may_stop_windows_listener(expected, {**current, "executable_path": "C:/Other/ollama.exe"}, [44])


@pytest.mark.parametrize("domain", ["windows", "wsl"])
def test_preflight_rejects_listener_in_either_runtime_domain(domain):
    snapshot = {
        "windows": {"18765": 0, "11434": 0},
        "wsl": {"18765": 0, "11434": 0},
    }
    snapshot[domain]["18765"] = 1
    with pytest.raises(RuntimeError, match="PREEXISTING_CROSS_DOMAIN_LISTENER"):
        assert_ports_free(snapshot)
