# sync-skill — Skill Synchronization System

**Date:** 2026-05-14
**Status:** Approved design

## Problem

The user runs multiple agent runtimes (OpenClaw, Hermes, Claude Code, ...) across many machines. Useful skills authored on one machine cannot easily be shared to all other machines. A central place to publish/browse skills and a one-shot sync command on each machine are needed.

## Constraints (locked from brainstorming)

- Skill format is uniform (`SKILL.md` + sibling files), no per-runtime conversion required.
- Source of truth: a single GitHub repo. Web UI is read-only over a small backend.
- Sync trigger: CLI command, manual. Parameterized: no args = all, args = specific names.
- Auth: none (trusted intranet).
- Deploy: GitHub for the repo, self-hosted backend + web on user's own server.

## Architecture

Three components, single responsibility each:

1. **GitHub repo** — `skills/<name>/SKILL.md` + sibling files. Versioned by git. Source of truth for skill content.
2. **Backend service** (FastAPI + SQLite) — keeps a local clone of the repo, periodically pulls + reindexes, stores machine telemetry, exposes REST API.
3. **Web UI** (Vite + React) — pure read client over the backend API.
4. **CLI `sync-skill`** — on each machine. Owns local filesystem at `~/.claude/skills/` (or configurable). Reports installed state to backend.

```
GitHub repo ──pull──> Backend ──REST──> Web UI
                          ▲
                          │ heartbeat
                          │
                       CLI on each machine ──git pull──> ~/.claude/skills/
```

CLI does its own `git pull` for content (no skill bytes flow through the backend); backend only tells CLI which skills exist and receives an installed-state report.

## Data model (SQLite)

```sql
CREATE TABLE skills (
  name TEXT PRIMARY KEY,
  description TEXT,
  tags_json TEXT,         -- JSON array from SKILL.md frontmatter
  latest_commit TEXT,
  updated_at TIMESTAMP,
  readme_md TEXT
);

CREATE TABLE skill_versions (
  name TEXT,
  commit_sha TEXT,
  committed_at TIMESTAMP,
  message TEXT,
  PRIMARY KEY (name, commit_sha)
);

CREATE TABLE machines (
  id TEXT PRIMARY KEY,     -- uuid set by `sync-skill init`
  hostname TEXT,
  os TEXT,
  runtime TEXT,            -- "claude" | "openclaw" | "hermes" | ...
  last_seen_at TIMESTAMP
);

CREATE TABLE installs (
  machine_id TEXT,
  skill_name TEXT,
  commit_sha TEXT,         -- which version is installed
  installed_at TIMESTAMP,
  PRIMARY KEY (machine_id, skill_name)
);
```

`skills` and `skill_versions` are derived from the git repo and can be rebuilt at any time. `machines` and `installs` are the only authoritative tables.

## REST API

```
GET  /api/skills                        list (?q=, ?tag=)
GET  /api/skills/{name}                 detail: readme, tags, version history, installs[]
GET  /api/machines                      dashboard
POST /api/machines/{id}/heartbeat       body: { hostname, os, runtime, installed: [{name, commit_sha}] }
POST /api/refresh                       manual git-pull + reindex (also runs every 60s)
```

No authentication. CORS open to backend's own origin.

## CLI commands

Config file: `~/.config/sync-skill/config.toml`

```toml
server_url   = "http://skills.example/api"
repo_url     = "https://github.com/<user>/skills.git"
target_dir   = "~/.claude/skills"
machine_id   = "<uuid>"
hostname     = "host-a"
runtime      = "claude"
```

Commands:

| command | behavior |
|---|---|
| `sync-skill init` | create config, generate uuid, register first heartbeat |
| `sync-skill list` | `GET /api/skills`, print table |
| `sync-skill pull` | git pull local clone, copy ALL `skills/*` into `target_dir`, send heartbeat |
| `sync-skill pull <name>...` | same but only specified skills (validates against server) |
| `sync-skill publish <dir>` | copy local skill dir into local clone of repo, commit (message `publish <name>`), push |
| `sync-skill status` | local installed list + per-skill comparison vs `latest_commit` from server |

The CLI keeps its own working clone at `~/.cache/sync-skill/repo` so `publish` and `pull` are git operations from the same place.

## Web UI

Pages:

- `/` — skill grid; cards show name, description, tags, install count, last updated. Top bar has search + tag filter.
- `/skills/:name` — rendered README, version history (commit list with messages), table of machines with which commit they have.
- `/machines` — table: hostname, runtime, last_seen, # installed skills, # stale (vs latest).

Stack: Vite + React + TypeScript + Tailwind. No SSR. `react-router`. Markdown rendered with `react-markdown`.

## Backend internals

- FastAPI app under `server/app.py`.
- `server/indexer.py`: shells `git -C <clone> pull`, walks `skills/`, parses `SKILL.md` YAML frontmatter for name/description/tags, reads commit log per skill path. Writes to SQLite in a transaction.
- `APScheduler` triggers indexer every 60s; `/api/refresh` invokes it on demand.
- `server/db.py`: thin SQLAlchemy core, migrations as plain `CREATE TABLE IF NOT EXISTS`.

## Repo layout

```
sync-skill/
├── server/
│   ├── app.py
│   ├── indexer.py
│   ├── db.py
│   ├── models.py
│   ├── requirements.txt
│   └── Dockerfile
├── cli/
│   ├── sync_skill/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── config.py
│   │   └── git_ops.py
│   ├── pyproject.toml
│   └── README.md
├── web/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── README.md
└── docs/superpowers/specs/2026-05-14-sync-skill-design.md
```

## Out of scope (YAGNI)

- Authentication / per-user permissions.
- Skill ratings / favorites (mentioned in brainstorm but defer — needs a write path and login).
- Background daemon / webhook push sync.
- Per-runtime skill format conversion.
- Skill dependency resolution.

## Success criteria

1. From machine A: author a skill dir, `sync-skill publish ./my-skill`, see it appear on the Web UI within 60s.
2. From machine B: `sync-skill pull my-skill`, the skill lands in `~/.claude/skills/my-skill/`, and the Web UI machine page shows machine B with that skill installed.
3. From machine B: `sync-skill pull` (no args) installs all published skills.
4. Web UI `/machines` shows both A and B with last_seen timestamps and installed counts.
