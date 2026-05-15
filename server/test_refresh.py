"""Tests for the async /api/refresh endpoint."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server import app as app_module
from server.app import app


@pytest.fixture(autouse=True)
def _reset_state():
    # Wait for any in-flight refresh from a previous test to finish.
    for _ in range(100):
        if not app_module._refresh_lock.locked():
            break
        time.sleep(0.05)
    app_module._refresh_state.update({
        "running": False,
        "last_started_at": None,
        "last_finished_at": None,
        "last_ok": None,
        "last_error": None,
        "last_count": None,
    })
    yield


def test_refresh_returns_202_immediately(monkeypatch):
    def slow_refresh(db, repo, clone):
        time.sleep(2)
        return 5
    monkeypatch.setattr(app_module.indexer, "refresh", slow_refresh)

    client = TestClient(app)
    t0 = time.monotonic()
    resp = client.post("/api/refresh")
    elapsed = time.monotonic() - t0

    assert elapsed < 1.0, f"endpoint blocked for {elapsed:.2f}s"
    assert resp.status_code == 202
    body = resp.json()
    assert body["ok"] is True
    assert body["queued"] is True


def test_concurrent_refresh_returns_already_running(monkeypatch):
    call_count = {"n": 0}

    def slow_refresh(db, repo, clone):
        call_count["n"] += 1
        time.sleep(1.5)
        return 3
    monkeypatch.setattr(app_module.indexer, "refresh", slow_refresh)

    client = TestClient(app)
    r1 = client.post("/api/refresh")
    assert r1.status_code == 202
    assert r1.json()["queued"] is True

    # Second hit while first is still running
    time.sleep(0.1)
    r2 = client.post("/api/refresh")
    assert r2.status_code == 200
    body = r2.json()
    assert body["queued"] is False
    assert body["reason"] == "already running"

    # Let the first finish
    time.sleep(2.0)
    assert call_count["n"] == 1


def test_refresh_state_updates_after_completion(monkeypatch):
    def fast_refresh(db, repo, clone):
        return 5
    monkeypatch.setattr(app_module.indexer, "refresh", fast_refresh)

    client = TestClient(app)
    r = client.post("/api/refresh")
    assert r.status_code == 202

    # Wait for the daemon thread to finish
    for _ in range(50):
        if app_module._refresh_state["last_ok"] is True:
            break
        time.sleep(0.05)

    assert app_module._refresh_state["last_ok"] is True
    assert app_module._refresh_state["last_count"] == 5
    assert app_module._refresh_state["running"] is False
