#!/usr/bin/env python3
"""Publish a local skill directory."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Config, ensure_clone, pull_repo, git, http_json


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: publish.py <skill-dir> [-m message]")
    skill_dir = Path(sys.argv[1]).expanduser().resolve()
    message = None
    if "-m" in sys.argv:
        i = sys.argv.index("-m")
        message = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
        sys.exit(f"{skill_dir} has no SKILL.md")

    cfg = Config.load()
    cache = Path(cfg.cache_repo_dir)
    ensure_clone(cfg.repo_url, cache)
    pull_repo(cache)
    name = skill_dir.name
    dest = cache / "skills" / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill_dir, dest)
    git(["add", "-A"], cwd=cache)
    status = git(["status", "--porcelain"], cwd=cache).strip()
    if not status:
        print(f"no changes to publish for {name}")
        return
    git(["commit", "-m", message or f"publish {name}"], cwd=cache)
    git(["push"], cwd=cache)
    try:
        http_json("POST", f"{cfg.server_url}/refresh", body={})
    except Exception as e:
        print(f"warning: server refresh failed (server will auto-reindex within 60s): {type(e).__name__}: {e}", file=sys.stderr)
    print(f"Published {name}")


if __name__ == "__main__":
    main()
