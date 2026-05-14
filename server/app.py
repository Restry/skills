"""FastAPI app for sync-skill."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import DB
from . import indexer


DATA_DIR = Path(os.environ.get("SYNC_SKILL_DATA", "/data"))
REPO_URL = os.environ.get("SYNC_SKILL_REPO", "")
CLONE_DIR = DATA_DIR / "repo"
DB_PATH = DATA_DIR / "sync-skill.db"
WEB_DIST = Path(os.environ.get("SYNC_SKILL_WEB", "/app/web"))

db = DB(DB_PATH)
app = FastAPI(title="sync-skill")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class InstalledItem(BaseModel):
    name: str
    commit_sha: str = ""


class Heartbeat(BaseModel):
    hostname: str
    os: str = ""
    runtime: str = ""
    installed: list[InstalledItem] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/api/skills")
def api_skills(q: str | None = None, tag: str | None = None):
    return {"skills": db.list_skills(q=q, tag=tag)}


@app.get("/api/skills/{name}")
def api_skill(name: str):
    s = db.get_skill(name)
    if not s:
        raise HTTPException(404, "skill not found")
    return s


@app.get("/api/machines")
def api_machines():
    return {"machines": db.list_machines()}


@app.post("/api/machines/{mid}/heartbeat")
def api_heartbeat(mid: str, hb: Heartbeat):
    ts = _now()
    db.upsert_machine(mid, hb.hostname, hb.os, hb.runtime, ts)
    db.replace_installs(mid, [i.model_dump() for i in hb.installed], ts)
    return {"ok": True}


@app.post("/api/refresh")
def api_refresh():
    n = indexer.refresh(db, REPO_URL, CLONE_DIR)
    return {"ok": True, "skills": n}


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve web build if present
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")


_scheduler = BackgroundScheduler()


@app.on_event("startup")
def _startup():
    try:
        indexer.refresh(db, REPO_URL, CLONE_DIR)
    except Exception as e:
        print(f"[startup] initial refresh failed: {e}")
    _scheduler.add_job(
        lambda: indexer.refresh(db, REPO_URL, CLONE_DIR),
        "interval", seconds=60, id="reindex", max_instances=1,
    )
    _scheduler.start()


@app.on_event("shutdown")
def _shutdown():
    _scheduler.shutdown(wait=False)
