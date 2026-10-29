from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_browser_copy_oracle_is_scoped_to_english_draft_field():
    source = (ROOT / "tools" / "r1a_browser_acceptance.cjs").read_text(encoding="utf-8")

    assert 'getByRole("button", { name: "复制 English prompt", exact: true })' in source
    assert 'getByRole("button", { name: "复制", exact: true }).nth(1)' not in source
    assert "Object.values(adopted).some(value => !value.trim())" in source


def test_live_harness_binds_backend_data_to_run_owned_runtime():
    source = (ROOT / "tools" / "r1a_live_acceptance.py").read_text(encoding="utf-8")

    assert '"LVW_DATA_ROOT": str(runtime / "data")' in source
    assert '"OLLAMA_PS_CLEANUP", timeout=10' in source
    assert 'result["browser_stderr_tail"] = sanitized_text' in source
    assert '"executable_path": "OLLAMA_EXE"' in source
