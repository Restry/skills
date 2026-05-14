"""Git repo indexer. Walks skills/* and writes to DB."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .db import DB


def _run(args: list[str], cwd: Path) -> str:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"git failed: {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def ensure_clone(repo_url: str, clone_dir: Path) -> None:
    if (clone_dir / ".git").exists():
        return
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", repo_url, str(clone_dir)], check=True)


def pull(clone_dir: Path) -> None:
    if not (clone_dir / ".git").exists():
        return
    _run(["git", "fetch", "--all", "--prune"], clone_dir)
    _run(["git", "reset", "--hard", "origin/HEAD"], clone_dir)


def _parse_skill_md(path: Path) -> tuple[str, str, list[str], str]:
    """Return (name, description, tags, full_md)."""
    text = path.read_text(encoding="utf-8")
    name = path.parent.name
    description = ""
    tags: list[str] = []
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
                name = meta.get("name", name)
                description = meta.get("description", "") or ""
                t = meta.get("tags", [])
                if isinstance(t, list):
                    tags = [str(x) for x in t]
            except yaml.YAMLError:
                pass
    return name, description, tags, text


def reindex(db: DB, clone_dir: Path) -> int:
    skills_dir = clone_dir / "skills"
    if not skills_dir.exists():
        db.delete_missing_skills([])
        return 0
    found: list[str] = []
    for entry in sorted(skills_dir.iterdir()):
        skill_md = entry / "SKILL.md"
        if not entry.is_dir() or not skill_md.exists():
            continue
        name, description, tags, readme = _parse_skill_md(skill_md)
        rel = f"skills/{entry.name}"
        log = _run(
            ["git", "log", "--pretty=format:%H|%cI|%s", "--", rel],
            clone_dir,
        ).strip()
        latest_commit = ""
        updated_at = datetime.now(timezone.utc).isoformat()
        if log:
            for line in log.splitlines():
                sha, when, msg = (line.split("|", 2) + ["", ""])[:3]
                db.upsert_version(name, sha, when, msg)
                if not latest_commit:
                    latest_commit = sha
                    updated_at = when
        db.upsert_skill(name, description, tags, latest_commit, updated_at, readme)
        found.append(name)
    db.delete_missing_skills(found)
    return len(found)


def refresh(db: DB, repo_url: str, clone_dir: Path) -> int:
    if repo_url:
        ensure_clone(repo_url, clone_dir)
        pull(clone_dir)
    return reindex(db, clone_dir)
