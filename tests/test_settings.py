
from kgent.settings import Settings, get_settings


def test_defaults_when_env_unset(monkeypatch):
    for key in [
        "KGENT_HOST",
        "KGENT_PORT",
        "KGENT_STORE",
        "KGENT_DB_URL",
        "KGENT_LOG_LEVEL",
        "KGENT_CORS_ORIGINS",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.port == 8088
    assert s.store_kind == "auto"
    assert s.log_level == "INFO"
    assert "http://localhost:5173" in s.cors_origins


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("KGENT_HOST", "0.0.0.0")
    monkeypatch.setenv("KGENT_PORT", "9090")
    monkeypatch.setenv("KGENT_STORE", "chroma")
    monkeypatch.setenv("KGENT_LOG_LEVEL", "debug")
    monkeypatch.setenv("KGENT_CORS_ORIGINS", "https://a.example, https://b.example")
    s = get_settings()
    assert s.host == "0.0.0.0"
    assert s.port == 9090
    assert s.store_kind == "chroma"
    assert s.log_level == "DEBUG"
    assert s.cors_origins == ["https://a.example", "https://b.example"]
