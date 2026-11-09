from __future__ import annotations

from pathlib import Path

import pytest

from lvw.run_local import configured_port


def test_default_and_explicit_loopback_server_port(monkeypatch):
    monkeypatch.delenv("LVW_PORT", raising=False)
    assert configured_port() == 8765
    monkeypatch.setenv("LVW_PORT", "18765")
    assert configured_port() == 18765


@pytest.mark.parametrize("value", ["abc", "0", "1023", "65536"])
def test_invalid_server_port_fails_closed(monkeypatch, value):
    monkeypatch.setenv("LVW_PORT", value)
    with pytest.raises(SystemExit):
        configured_port()


def test_windows_launcher_binds_ollama_without_arbitrary_process_control():
    root = Path(__file__).resolve().parents[2]
    launcher = root / "START_LVW.cmd"
    raw = launcher.read_bytes()
    source = raw.decode("ascii").lower()
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert "where ollama.exe" in source
    assert "lvw_ollama_exe=" in source
    assert "/api/v1/capabilities" in source
    assert "expected_build" in source
    assert "print_build_id.py" in source
    assert "for /l %%p in (18765,1,18775)" in source
    assert "lvw_no_browser" in source
    assert "getactivetcplisteners" in source
    assert "-encodedcommand" not in source
    assert "executionpolicy" not in source
    assert "taskkill" not in source
    browser_helper = (root / "tools" / "open_lvw_browser.cmd").read_text(encoding="ascii")
    assert "/api/v1/runtime/status" in browser_helper
    assert "lvw.runtime/1" in browser_helper


def test_build_identity_invalidates_stale_server_after_video_policy_change(tmp_path, monkeypatch):
    from app import build_info
    root=tmp_path/'pack';app=root/'lvw/backend/app';app.mkdir(parents=True)
    templates=root/'templates';templates.mkdir()
    (app/'build_info.py').write_text('fixed provider source')
    (templates/'analysis_system_zh.txt').write_text('common policy')
    video=templates/'analysis_video_system_zh.txt';video.write_text('video policy v1')
    monkeypatch.setattr(build_info,'__file__',str(app/'build_info.py'))
    before=build_info.build_id()
    assert build_info.build_id()==before
    video.write_text('video policy v2')
    assert build_info.build_id()!=before
