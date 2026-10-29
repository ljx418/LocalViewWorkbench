from pathlib import Path

from app.config import Settings


def test_local_settings_use_isolated_environment_root(monkeypatch, tmp_path):
    isolated = tmp_path / "run-owned-data"
    monkeypatch.setenv("LVW_DATA_ROOT", str(isolated))

    settings = Settings.local()

    assert settings.data_root == isolated.resolve()


def test_explicit_data_root_takes_precedence_over_environment(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("LVW_DATA_ROOT", str(tmp_path / "environment"))

    settings = Settings.local(data_root=explicit)

    assert settings.data_root == explicit.resolve()


def test_local_settings_keep_repository_default_without_override(monkeypatch, tmp_path):
    monkeypatch.delenv("LVW_DATA_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings.local()

    assert settings.data_root == (Path(tmp_path) / ".lvw-runtime").resolve()
