from pathlib import Path

from tools.r1a_offline_checkpoint import allowed_runtime_url, runtime_scan


ROOT = Path(__file__).resolve().parents[2]


def test_browser_copy_oracle_is_scoped_to_english_draft_field():
    source = (ROOT / "tools" / "r1a_browser_acceptance.cjs").read_text(encoding="utf-8")

    assert 'getByRole("button", { name: "复制 English prompt", exact: true })' in source
    assert 'getByRole("button", { name: "复制", exact: true }).nth(1)' not in source
    assert "Object.values(adopted).some(value => !value.trim())" in source
    assert 'selectOption(selectedContentProfile)' in source
    assert 'getByTestId("custom-guidance").fill(customGuidance)' in source
    assert 'runtime_ownership: "external"' in source
    assert "externally owned Ollama exposed enabled control" in source


def test_live_harness_binds_backend_data_to_run_owned_runtime():
    source = (ROOT / "tools" / "r1a_live_acceptance.py").read_text(encoding="utf-8")

    assert '"LVW_DATA_ROOT": str(runtime / "data")' in source
    assert '"OLLAMA_PS_CLEANUP", timeout=10' in source
    assert 'result["browser_stderr_tail"] = sanitized_text' in source
    assert '"executable_path": "OLLAMA_EXE"' in source


def test_offline_runtime_scan_allows_only_literal_loopback_urls():
    assert allowed_runtime_url("http://127.0.0.1:11434/api/chat")
    assert allowed_runtime_url("http://[::1]:18765/api/v1/runtime/status")
    assert not allowed_runtime_url("http://localhost:11434/api/chat")
    assert not allowed_runtime_url("https://example.com/api")
    assert runtime_scan()["passed"] is True
