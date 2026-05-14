#!/usr/bin/env python3
"""Pull skills (no args = all)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import Config, ensure_clone, pull_repo, send_heartbeat


def main() -> None:
    names = sys.argv[1:]
    cfg = Config.load()
    cache = Path(cfg.cache_repo_dir)
    ensure_clone(cfg.repo_url, cache)
    pull_repo(cache)
    skills_dir = cache / "skills"
    if not skills_dir.exists():
        sys.exit("repo has no skills/ directory")
    available = {
        d.name for d in skills_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    }
    if names:
        missing = set(names) - available
        if missing:
            sys.exit(f"not found: {', '.join(sorted(missing))}")
        chosen = list(names)
    else:
        chosen = sorted(available)
    target = Path(cfg.target_dir)
    target.mkdir(parents=True, exist_ok=True)
    for n in chosen:
        src = skills_dir / n
        dst = target / n
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"  installed {n}")
    try:
        send_heartbeat(cfg)
    except SystemExit as e:
        print(f"warning: heartbeat failed: {e}", file=sys.stderr)
    print(f"Pulled {len(chosen)} skill(s) into {target}")


if __name__ == "__main__":
    main()
