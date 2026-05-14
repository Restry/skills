#!/usr/bin/env python3
"""Show local installed skills and staleness vs server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Config, head_sha_for_path, http_json


def main() -> None:
    cfg = Config.load()
    target = Path(cfg.target_dir)
    cache = Path(cfg.cache_repo_dir)
    local = sorted(d.name for d in target.iterdir()
                   if target.exists() and d.is_dir() and (d / "SKILL.md").exists()) if target.exists() else []

    remote: dict[str, str] = {}
    try:
        data = http_json("GET", f"{cfg.server_url}/skills")
        remote = {s["name"]: s.get("latest_commit", "") for s in data.get("skills", [])}
    except SystemExit as e:
        print(f"warning: server unreachable: {e}", file=sys.stderr)

    print(f"target: {target}")
    print(f"installed: {len(local)} skill(s)")
    for n in local:
        local_sha = head_sha_for_path(cache, f"skills/{n}") if cache.exists() else ""
        latest = remote.get(n, "")
        marker = ""
        if latest and local_sha and latest != local_sha:
            marker = "  (stale)"
        elif remote and n not in remote:
            marker = "  (not on server)"
        print(f"  {n}  {local_sha[:8]}{marker}")


if __name__ == "__main__":
    main()
