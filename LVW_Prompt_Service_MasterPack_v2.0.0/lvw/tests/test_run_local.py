from __future__ import annotations

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
