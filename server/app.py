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


@app.delete("/api/skills/{name}")
def api_delete_skill(name: str):
    root = _skill_root(name)
    import shutil
    shutil.rmtree(root)
    cwd = CLONE_DIR
    try:
        subprocess_run(["git", "add", "-A", f"skills/{name}"], cwd)
        subprocess_run(["git", "-c", "user.name=sync-skill", "-c", "user.email=sync-skill@local",
                        "commit", "-m", f"delete {name}"], cwd)
        subprocess_run(["git", "push", "origin", "HEAD"], cwd)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    indexer.refresh(db, REPO_URL, CLONE_DIR)
    return {"ok": True, "deleted": name}


def subprocess_run(args, cwd):
    import subprocess
    res = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


@app.get("/api/health")
def health():
    return {"ok": True}


def _skill_root(name: str) -> Path:
    if not name or "/" in name or name.startswith(".") or name in ("..",):
        raise HTTPException(400, "bad name")
    root = (CLONE_DIR / "skills" / name).resolve()
    base = (CLONE_DIR / "skills").resolve()
    if not str(root).startswith(str(base) + os.sep) and root != base:
        raise HTTPException(400, "bad name")
    if not root.is_dir():
        raise HTTPException(404, "skill not found")
    return root


_TEXT_EXT = {
    ".md", ".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".txt", ".rst", ".html", ".css", ".csv", ".tsv", ".dot", ".sql",
    ".env", ".gitignore", ".gitattributes", "",
}


@app.get("/api/skills/{name}/files")
def api_skill_files(name: str):
    root = _skill_root(name)
    out = []
    for p in sorted(root.rglob("*")):
        rel_parts = p.relative_to(root).parts
        if any(part == ".git" or (part.startswith(".") and part not in (".gitignore", ".gitattributes", ".env.example")) for part in rel_parts):
            continue
        if any("Zone.Identifier" in part for part in rel_parts):
            continue
        if p.is_dir():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        rel = p.relative_to(root).as_posix()
        out.append({"path": rel, "size": size, "is_text": p.suffix.lower() in _TEXT_EXT})
    return {"name": name, "files": out}


@app.get("/api/skills/{name}/file")
def api_skill_file(name: str, path: str):
    root = _skill_root(name)
    target = (root / path).resolve()
    if not str(target).startswith(str(root) + os.sep):
        raise HTTPException(400, "bad path")
    if not target.is_file():
        raise HTTPException(404, "not found")
    size = target.stat().st_size
    if size > 512 * 1024:
        return {"path": path, "size": size, "truncated": True, "content": ""}
    try:
        content = target.read_text(encoding="utf-8")
        is_text = True
    except UnicodeDecodeError:
        content = ""
        is_text = False
    return {"path": path, "size": size, "truncated": False, "is_text": is_text, "content": content}


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
