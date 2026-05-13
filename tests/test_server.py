from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kgent.server import create_app
from kgent.settings import Settings


@pytest.fixture
def app_client(tmp_path: Path):
    settings = Settings(
        store_kind="json",
        store_path=tmp_path / "index.json",
        db_url=f"sqlite:///{tmp_path / 'chat.db'}",
    )
    return TestClient(create_app(settings))


def _seed_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Project\nKgent indexes documentation.", encoding="utf-8")
    (repo / "guide.md").write_text("# Guide\nFollow these steps.", encoding="utf-8")
    return repo


def test_health(app_client: TestClient):
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_store_info_empty(app_client: TestClient):
    resp = app_client.get("/api/store/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["has_graph"] is False


def test_ingest_invalid_path(app_client: TestClient, tmp_path: Path):
    missing = tmp_path / "ghost"
    resp = app_client.post("/api/ingest", json={"path": str(missing)})
    assert resp.status_code == 400


def test_ingest_then_info_and_conversation(app_client: TestClient, tmp_path: Path):
    repo = _seed_repo(tmp_path)
    resp = app_client.post("/api/ingest", json={"path": str(repo), "replace": True})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["documents"] == 2
    assert payload["chunks_added"] >= 2

    info = app_client.get("/api/store/info").json()
    assert info["count"] >= 2
    assert info["active_repo"] == str(repo.resolve())

    created = app_client.post("/api/conversations", json={"title": "test"}).json()
    fetched = app_client.get(f"/api/conversations/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "test"

    deleted = app_client.delete(f"/api/conversations/{created['id']}")
    assert deleted.status_code == 200
    assert app_client.get(f"/api/conversations/{created['id']}").status_code == 404


def test_ask_rejects_when_store_empty(app_client: TestClient):
    resp = app_client.post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 400


def test_providers_endpoint_lists_known_providers(app_client: TestClient):
    body = app_client.get("/api/providers").json()
    names = {p["name"] for p in body["providers"]}
    assert {"ollama", "openai", "anthropic", "groq"}.issubset(names)
