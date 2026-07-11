import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kgent.server import create_app
from kgent.settings import Settings


def _wait_for_ingest(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/ingest/status/{job_id}").json()
        if status["state"] in ("completed", "failed"):
            return status
        time.sleep(0.05)
    raise AssertionError(f"ingest job {job_id} did not finish in time")


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


def test_ingest_status_unknown_job(app_client: TestClient):
    resp = app_client.get("/api/ingest/status/does-not-exist")
    assert resp.status_code == 404


def test_ingest_then_info_and_conversation(app_client: TestClient, tmp_path: Path):
    repo = _seed_repo(tmp_path)
    resp = app_client.post("/api/ingest", json={"path": str(repo), "replace": True})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    status = _wait_for_ingest(app_client, job_id)
    assert status["state"] == "completed", status
    assert status["documents"] == 2
    assert status["chunks"] >= 2

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


def test_graph_empty_when_no_graph(app_client: TestClient):
    body = app_client.get("/api/graph").json()
    assert body == {"nodes": [], "edges": [], "has_graph": False}


def test_graph_returns_nodes_after_ingest(tmp_path: Path):
    settings = Settings(
        store_kind="json",
        store_path=tmp_path / "index.json",
        db_url=f"sqlite:///{tmp_path / 'chat.db'}",
        graph_mode="cooccurrence",
    )
    client = TestClient(create_app(settings))

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "notes.md").write_text(
        "Alpha Beta Alpha Beta Alpha Beta Gamma Alpha Beta Gamma",
        encoding="utf-8",
    )
    job_id = client.post(
        "/api/ingest", json={"path": str(repo), "replace": True}
    ).json()["job_id"]
    _wait_for_ingest(client, job_id)

    body = client.get("/api/graph").json()
    assert body["has_graph"] is True
    labels = {n["label"] for n in body["nodes"]}
    assert "Alpha" in labels
    assert "Beta" in labels
    assert all({"src", "dst", "weight"} <= e.keys() for e in body["edges"])
