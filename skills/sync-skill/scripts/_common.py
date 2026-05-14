"""Shared helpers for sync-skill scripts. Stdlib only."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path


_TOML_LINE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"((?:[^"\\]|\\.)*)"\s*$')


def _load_simple_toml(path: Path) -> dict:
    """Parse a flat key = "value" config. Sufficient for our config.toml."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _TOML_LINE.match(line)
        if not m:
            sys.exit(f"cannot parse config line: {line!r}")
        out[m.group(1)] = m.group(2).encode("utf-8").decode("unicode_escape")
    return out


CONFIG_DIR = Path(os.environ.get("SYNC_SKILL_CONFIG_DIR", Path.home() / ".config" / "sync-skill"))
CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_CACHE = Path.home() / ".cache" / "sync-skill" / "repo"
DEFAULT_TARGET = Path.home() / ".claude" / "skills"


@dataclass
class Config:
    server_url: str
    repo_url: str
    target_dir: str
    machine_id: str
    hostname: str
    runtime: str
    cache_repo_dir: str

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_PATH.exists():
            sys.exit(f"No config at {CONFIG_PATH}. Run init.py first.")
        return cls(**_load_simple_toml(CONFIG_PATH))

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lines = []
        for k, v in asdict(self).items():
            lines.append(f'{k} = "{v}"')
        CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def git(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, check=False,
    )
    if check and res.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


def ensure_clone(repo_url: str, clone_dir: Path) -> None:
    if (clone_dir / ".git").exists():
        return
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    git(["clone", repo_url, str(clone_dir)])


def pull_repo(clone_dir: Path) -> None:
    git(["fetch", "--all", "--prune"], cwd=clone_dir)
    git(["reset", "--hard", "origin/HEAD"], cwd=clone_dir)


def head_sha_for_path(clone_dir: Path, rel: str) -> str:
    return git(["log", "-n", "1", "--pretty=format:%H", "--", rel], cwd=clone_dir, check=False).strip()


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 10.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} from {url}: {body_text}")
    except urllib.error.URLError as e:
        raise SystemExit(f"cannot reach {url}: {e.reason}")


def send_heartbeat(cfg: Config) -> None:
    cache = Path(cfg.cache_repo_dir)
    target = Path(cfg.target_dir)
    installed = []
    if target.exists():
        for d in sorted(target.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                sha = ""
                if cache.exists():
                    sha = head_sha_for_path(cache, f"skills/{d.name}")
                installed.append({"name": d.name, "commit_sha": sha})
    payload = {
        "hostname": cfg.hostname,
        "os": platform.platform(),
        "runtime": cfg.runtime,
        "installed": installed,
    }
    http_json("POST", f"{cfg.server_url}/machines/{cfg.machine_id}/heartbeat", payload)
