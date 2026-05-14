"""SQLite layer for sync-skill backend."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
  name TEXT PRIMARY KEY,
  description TEXT,
  tags_json TEXT,
  latest_commit TEXT,
  updated_at TEXT,
  readme_md TEXT
);
CREATE TABLE IF NOT EXISTS skill_versions (
  name TEXT,
  commit_sha TEXT,
  committed_at TEXT,
  message TEXT,
  PRIMARY KEY (name, commit_sha)
);
CREATE TABLE IF NOT EXISTS machines (
  id TEXT PRIMARY KEY,
  hostname TEXT,
  os TEXT,
  runtime TEXT,
  last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS installs (
  machine_id TEXT,
  skill_name TEXT,
  commit_sha TEXT,
  installed_at TEXT,
  PRIMARY KEY (machine_id, skill_name)
);
"""


class DB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def upsert_skill(self, name: str, description: str, tags: list[str],
                     latest_commit: str, updated_at: str, readme_md: str) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO skills(name, description, tags_json, latest_commit, updated_at, readme_md)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(name) DO UPDATE SET
                     description=excluded.description,
                     tags_json=excluded.tags_json,
                     latest_commit=excluded.latest_commit,
                     updated_at=excluded.updated_at,
                     readme_md=excluded.readme_md""",
                (name, description, json.dumps(tags), latest_commit, updated_at, readme_md),
            )

    def upsert_version(self, name: str, sha: str, committed_at: str, message: str) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT OR IGNORE INTO skill_versions(name, commit_sha, committed_at, message)
                   VALUES(?,?,?,?)""",
                (name, sha, committed_at, message),
            )

    def delete_missing_skills(self, present: Iterable[str]) -> None:
        present_list = list(present)
        with self.connect() as c:
            placeholders = ",".join("?" * len(present_list)) or "''"
            c.execute(f"DELETE FROM skills WHERE name NOT IN ({placeholders})", present_list)
            c.execute(f"DELETE FROM skill_versions WHERE name NOT IN ({placeholders})", present_list)

    def list_skills(self, q: str | None = None, tag: str | None = None) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("SELECT name, description, tags_json, latest_commit, updated_at FROM skills ORDER BY name").fetchall()
        out = []
        for r in rows:
            tags = json.loads(r["tags_json"] or "[]")
            if q and q.lower() not in r["name"].lower() and q.lower() not in (r["description"] or "").lower():
                continue
            if tag and tag not in tags:
                continue
            out.append({
                "name": r["name"], "description": r["description"], "tags": tags,
                "latest_commit": r["latest_commit"], "updated_at": r["updated_at"],
            })
        # install counts
        with self.connect() as c:
            counts = dict(c.execute(
                "SELECT skill_name, COUNT(*) FROM installs GROUP BY skill_name"
            ).fetchall())
        for s in out:
            s["install_count"] = counts.get(s["name"], 0)
        return out

    def get_skill(self, name: str) -> dict | None:
        with self.connect() as c:
            r = c.execute("SELECT * FROM skills WHERE name=?", (name,)).fetchone()
            if not r:
                return None
            versions = [dict(v) for v in c.execute(
                "SELECT commit_sha, committed_at, message FROM skill_versions WHERE name=? ORDER BY committed_at DESC",
                (name,),
            ).fetchall()]
            installs = [dict(i) for i in c.execute(
                """SELECT m.id AS machine_id, m.hostname, m.runtime, i.commit_sha, i.installed_at
                   FROM installs i JOIN machines m ON m.id=i.machine_id
                   WHERE i.skill_name=? ORDER BY i.installed_at DESC""",
                (name,),
            ).fetchall()]
        return {
            "name": r["name"],
            "description": r["description"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "latest_commit": r["latest_commit"],
            "updated_at": r["updated_at"],
            "readme_md": r["readme_md"],
            "versions": versions,
            "installs": installs,
        }

    def upsert_machine(self, mid: str, hostname: str, os_name: str, runtime: str, ts: str) -> None:
        with self.connect() as c:
            c.execute(
                """INSERT INTO machines(id, hostname, os, runtime, last_seen_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     hostname=excluded.hostname, os=excluded.os,
                     runtime=excluded.runtime, last_seen_at=excluded.last_seen_at""",
                (mid, hostname, os_name, runtime, ts),
            )

    def replace_installs(self, mid: str, items: list[dict], ts: str) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM installs WHERE machine_id=?", (mid,))
            for it in items:
                c.execute(
                    """INSERT INTO installs(machine_id, skill_name, commit_sha, installed_at)
                       VALUES(?,?,?,?)""",
                    (mid, it["name"], it.get("commit_sha", ""), ts),
                )

    def list_machines(self) -> list[dict]:
        with self.connect() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM machines ORDER BY hostname").fetchall()]
            counts = dict(c.execute(
                "SELECT machine_id, COUNT(*) FROM installs GROUP BY machine_id"
            ).fetchall())
            latest = dict(c.execute("SELECT name, latest_commit FROM skills").fetchall())
            stale_counts: dict[str, int] = {}
            for r in c.execute("SELECT machine_id, skill_name, commit_sha FROM installs").fetchall():
                if latest.get(r["skill_name"]) and latest[r["skill_name"]] != r["commit_sha"]:
                    stale_counts[r["machine_id"]] = stale_counts.get(r["machine_id"], 0) + 1
        for r in rows:
            r["installed_count"] = counts.get(r["id"], 0)
            r["stale_count"] = stale_counts.get(r["id"], 0)
        return rows
